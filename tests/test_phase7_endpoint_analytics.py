# tests/test_phase7_endpoint_analytics.py
#
# CARD 7.4 — /operator/telemetry now returns an `analytics` block (Phase 7.3
# signals computed on the fly). Verifies the block is present, matches a direct
# computation over the same history, handles the empty-history baseline, stays
# read-only, and remains additive over the 7.2A shape.
#
# Runs under TESTING=1 (tests/conftest.py) → phase7_storage in-memory backend.
import pytest

from phase6_contracts import (
    SuperCoherenceState,
    SuperEssenceState,
    SuperIdentityState,
    SuperIntegrationState,
    SuperPatternState,
    SuperstructureState,
)
import phase7_storage
import phase7_telemetry
from phase7_analytics import (
    classify_trajectory,
    compute_coherence_trend,
    compute_drift_acceleration,
    compute_drift_velocity,
    compute_stability_forecast,
)
from phase7_endpoint import OPERATOR_ID

ANALYTICS_KEYS = {
    "drift_velocity",
    "drift_acceleration",
    "coherence_trend",
    "stability_forecast",
    "trajectory",
}


@pytest.fixture
def client():
    import app
    from conftest import TestClient
    return TestClient(app.app)


@pytest.fixture(autouse=True)
def _reset_phase7():
    phase7_storage.reset()
    yield
    phase7_storage.reset()


def _state() -> SuperstructureState:
    return SuperstructureState(
        pattern=SuperPatternState("p", 0.0, 0.0, 0.0, "p"),
        integration=SuperIntegrationState(0.0, 0.0, "i"),
        coherence=SuperCoherenceState(0.0, 0.0, 0.0, "c"),
        essence=SuperEssenceState(0.0, "e", 0.0),
        identity=SuperIdentityState("o", 0.0, 0.0, 0.0),
    )


def _seed(drift, coherence, ts):
    phase7_storage.append_record(
        OPERATOR_ID,
        phase7_storage.TelemetryRecord(
            timestamp=ts,
            superstructure=_state(),
            drift=drift,
            coherence_health=coherence,
            trust_band="HIGH",
        ),
    )


def test_empty_history_neutral_baseline(client):
    body = client.get("/operator/telemetry").json()
    assert body["history"] == []
    assert body["latest"] is None
    an = body["analytics"]
    assert an["drift_velocity"] == 0.0
    assert an["drift_acceleration"] == 0.0
    assert an["coherence_trend"] == 0.0
    assert an["stability_forecast"] == 0.0
    assert an["trajectory"] == "Stable"


def test_analytics_block_present_and_shaped(client):
    _seed(0.2, 0.6, 0.0)
    _seed(0.3, 0.7, 1.0)
    an = client.get("/operator/telemetry").json()["analytics"]
    assert set(an.keys()) == ANALYTICS_KEYS
    assert -1.0 <= an["drift_velocity"] <= 1.0
    assert -1.0 <= an["drift_acceleration"] <= 1.0
    assert -1.0 <= an["coherence_trend"] <= 1.0
    assert 0.0 <= an["stability_forecast"] <= 1.0
    assert an["trajectory"] in {"Stable", "Recovering", "Wobbling", "Diverging"}


def test_analytics_match_direct_computation(client):
    for i, (d, c) in enumerate([(0.1, 0.5), (0.2, 0.6), (0.3, 0.7), (0.4, 0.8), (0.5, 0.9)]):
        _seed(d, c, float(i))

    records = phase7_telemetry.get_history(OPERATOR_ID)
    velocity = compute_drift_velocity(records)
    acceleration = compute_drift_acceleration(records)
    coherence_trend = compute_coherence_trend(records)
    forecast = compute_stability_forecast(velocity, acceleration, coherence_trend)
    trajectory = classify_trajectory(forecast)

    an = client.get("/operator/telemetry").json()["analytics"]
    assert an["drift_velocity"] == pytest.approx(velocity)
    assert an["drift_acceleration"] == pytest.approx(acceleration)
    assert an["coherence_trend"] == pytest.approx(coherence_trend)
    assert an["stability_forecast"] == pytest.approx(forecast)
    assert an["trajectory"] == trajectory


def test_diverging_history_classifies(client):
    # Maximal 2-point drift jump + collapsing coherence → forecast 0.15.
    _seed(0.0, 1.0, 0.0)
    _seed(1.0, 0.0, 1.0)
    an = client.get("/operator/telemetry").json()["analytics"]
    assert an["drift_velocity"] == pytest.approx(1.0)
    assert an["coherence_trend"] == pytest.approx(-1.0)
    assert an["stability_forecast"] == pytest.approx(0.15)
    assert an["trajectory"] == "Diverging"


def test_endpoint_remains_additive(client):
    _seed(0.3, 0.5, 0.0)
    body = client.get("/operator/telemetry").json()
    # 7.2A fields still present, plus the new 7.4 block.
    assert "history" in body
    assert "latest" in body
    assert "analytics" in body
    assert len(body["history"]) == 1


def test_analytics_is_read_only(client):
    _seed(0.2, 0.5, 0.0)
    _seed(0.4, 0.6, 1.0)
    before = phase7_telemetry.get_history(OPERATOR_ID)
    client.get("/operator/telemetry")
    client.get("/operator/telemetry")
    after = phase7_telemetry.get_history(OPERATOR_ID)
    assert len(before) == len(after) == 2
    # History payload is unchanged across reads.
    body = client.get("/operator/telemetry").json()
    assert [r["timestamp"] for r in body["history"]] == [0.0, 1.0]
