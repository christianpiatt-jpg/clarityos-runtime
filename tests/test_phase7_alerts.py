# tests/test_phase7_alerts.py
#
# CARD 7.6 — pure alert rules over the analytics block, plus endpoint
# integration (the `alerts` field on /operator/telemetry).
#
# Runs under TESTING=1 (tests/conftest.py) → phase7_storage in-memory backend.
from copy import deepcopy

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
from phase7_alerts import (
    ALERT_COHERENCE_DECLINE,
    ALERT_DIVERGING,
    ALERT_DRIFT_ACCELERATION,
    ALERT_LOW_FORECAST,
    ALERT_NONE,
    ALERT_RAPID_DRIFT,
    compute_alerts,
)
from phase7_endpoint import OPERATOR_ID


def _analytics(
    *,
    trajectory="Stable",
    stability_forecast=1.0,
    drift_velocity=0.0,
    drift_acceleration=0.0,
    coherence_trend=0.0,
):
    """A 'no rule fires' baseline; override one field per rule test."""
    return {
        "trajectory": trajectory,
        "stability_forecast": stability_forecast,
        "drift_velocity": drift_velocity,
        "drift_acceleration": drift_acceleration,
        "coherence_trend": coherence_trend,
    }


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def test_no_rule_fires_returns_neutral():
    assert compute_alerts(_analytics()) == [ALERT_NONE]


def test_diverging_rule():
    assert compute_alerts(_analytics(trajectory="Diverging")) == [ALERT_DIVERGING]


def test_low_forecast_rule():
    assert compute_alerts(_analytics(stability_forecast=0.39)) == [ALERT_LOW_FORECAST]


def test_rapid_drift_rule():
    assert compute_alerts(_analytics(drift_velocity=0.21)) == [ALERT_RAPID_DRIFT]


def test_drift_acceleration_rule():
    assert compute_alerts(_analytics(drift_acceleration=0.16)) == [ALERT_DRIFT_ACCELERATION]


def test_coherence_decline_rule():
    assert compute_alerts(_analytics(coherence_trend=-0.11)) == [ALERT_COHERENCE_DECLINE]


# ---------------------------------------------------------------------------
# Thresholds are strict (boundary values do NOT fire)
# ---------------------------------------------------------------------------

def test_thresholds_are_strict_at_boundary():
    boundary = _analytics(
        stability_forecast=0.40,    # not < 0.40
        drift_velocity=0.20,        # not > 0.20
        drift_acceleration=0.15,    # not > 0.15
        coherence_trend=-0.10,      # not < -0.10
    )
    assert compute_alerts(boundary) == [ALERT_NONE]


# ---------------------------------------------------------------------------
# Multiple rules + ordering
# ---------------------------------------------------------------------------

def test_all_rules_fire_in_order():
    analytics = _analytics(
        trajectory="Diverging",
        stability_forecast=0.1,
        drift_velocity=0.9,
        drift_acceleration=0.9,
        coherence_trend=-0.9,
    )
    assert compute_alerts(analytics) == [
        ALERT_DIVERGING,
        ALERT_LOW_FORECAST,
        ALERT_RAPID_DRIFT,
        ALERT_DRIFT_ACCELERATION,
        ALERT_COHERENCE_DECLINE,
    ]


def test_subset_of_rules_fire():
    analytics = _analytics(drift_velocity=0.5, coherence_trend=-0.5)
    assert compute_alerts(analytics) == [ALERT_RAPID_DRIFT, ALERT_COHERENCE_DECLINE]


# ---------------------------------------------------------------------------
# Robustness + determinism
# ---------------------------------------------------------------------------

def test_missing_keys_default_to_no_alert():
    assert compute_alerts({}) == [ALERT_NONE]


def test_deterministic():
    analytics = _analytics(trajectory="Diverging", drift_velocity=0.5)
    assert compute_alerts(analytics) == compute_alerts(deepcopy(analytics))


# ---------------------------------------------------------------------------
# Endpoint integration
# ---------------------------------------------------------------------------

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


def test_endpoint_returns_alerts_field(client):
    _seed(0.2, 0.6, 0.0)
    _seed(0.3, 0.7, 1.0)
    body = client.get("/operator/telemetry").json()
    assert "alerts" in body
    assert isinstance(body["alerts"], list)
    # alerts is always consistent with compute_alerts of the returned analytics.
    assert body["alerts"] == compute_alerts(body["analytics"])


def test_endpoint_diverging_history_emits_diverging_alert(client):
    # Maximal 2-point jump → trajectory "Diverging" + low forecast.
    _seed(0.0, 1.0, 0.0)
    _seed(1.0, 0.0, 1.0)
    body = client.get("/operator/telemetry").json()
    assert body["analytics"]["trajectory"] == "Diverging"
    assert ALERT_DIVERGING in body["alerts"]
    assert body["alerts"] == compute_alerts(body["analytics"])


def test_endpoint_empty_history_alerts_match_neutral_baseline(client):
    # Empty history → 7.4 neutral baseline analytics (forecast 0.0, "Stable").
    # Per the rules, forecast 0.0 < 0.40 trips the low-forecast alert; the
    # `alerts` field always equals compute_alerts(analytics).
    body = client.get("/operator/telemetry").json()
    assert body["analytics"]["stability_forecast"] == 0.0
    assert body["alerts"] == compute_alerts(body["analytics"])
    assert body["alerts"] == [ALERT_LOW_FORECAST]


def test_endpoint_alerts_is_read_only(client):
    _seed(0.2, 0.5, 0.0)
    before = phase7_storage.load_history(OPERATOR_ID)
    client.get("/operator/telemetry")
    client.get("/operator/telemetry")
    after = phase7_storage.load_history(OPERATOR_ID)
    assert len(before) == len(after) == 1
