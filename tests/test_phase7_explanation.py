# tests/test_phase7_explanation.py
#
# CARD 7.9 — deterministic causal-narrative synthesis from analytics + alerts +
# causal factors, plus endpoint integration (the `narrative` field).
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
from phase7_storage import TelemetryRecord
from phase7_explanation import INTERPRETATIONS, generate_causal_narrative
from phase7_endpoint import OPERATOR_ID


def _analytics(trajectory="Stable", v=0.0, a=0.0, c=0.0, sf=0.0):
    return {
        "drift_velocity": v,
        "drift_acceleration": a,
        "coherence_trend": c,
        "stability_forecast": sf,
        "trajectory": trajectory,
    }


# ---------------------------------------------------------------------------
# Determinism + structure
# ---------------------------------------------------------------------------

def test_deterministic():
    an = _analytics("Recovering", 0.1, 0.0, 0.2, 0.6)
    alerts = ["Rapid drift — identity moving faster than expected"]
    cf = [{"action": "edit", "correlation": 0.3, "contribution": 0.2}]
    assert generate_causal_narrative(an, alerts, cf) == generate_causal_narrative(
        an, list(alerts), list(cf)
    )


def test_all_sections_present():
    out = generate_causal_narrative(_analytics(), ["x"], [])
    for header in (
        "Identity Movement Summary:",
        "Key Alerts:",
        "Likely Contributing Actions:",
        "Overall Interpretation:",
    ):
        assert header in out


def test_summary_formatting():
    out = generate_causal_narrative(_analytics("Stable", 0.3, -0.1, 0.25, 0.7), [], [])
    assert "- Drift velocity: 0.30" in out
    assert "- Drift acceleration: -0.10" in out
    assert "- Coherence trend: 0.25" in out
    assert "- Stability forecast: 0.70" in out
    assert "- Trajectory classification: Stable" in out


# ---------------------------------------------------------------------------
# Paragraph selection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("traj", ["Diverging", "Wobbling", "Recovering", "Stable"])
def test_paragraph_selection(traj):
    out = generate_causal_narrative(
        _analytics(traj),
        ["No alerts — operator trajectory stable"],
        [{"action": "none", "correlation": 0.0, "contribution": 0.0}],
    )
    assert out.rstrip().endswith(INTERPRETATIONS[traj])


def test_unknown_trajectory_falls_back_to_stable():
    out = generate_causal_narrative(_analytics("Mystery"), ["x"], [])
    assert out.rstrip().endswith(INTERPRETATIONS["Stable"])


# ---------------------------------------------------------------------------
# Alerts + causal-factor sections
# ---------------------------------------------------------------------------

def test_no_alerts_renders_none():
    out = generate_causal_narrative(_analytics(), [], [])
    assert "Key Alerts:\n- None" in out


def test_alerts_listed_in_order():
    out = generate_causal_narrative(_analytics(), ["alert one", "alert two"], [])
    assert "Key Alerts:\n- alert one\n- alert two" in out


def test_none_sentinel_causal_factors():
    out = generate_causal_narrative(
        _analytics(), ["x"], [{"action": "none", "correlation": 0.0, "contribution": 0.0}]
    )
    assert "Likely Contributing Actions:\n- No significant contributing actions detected" in out


def test_empty_causal_factors():
    out = generate_causal_narrative(_analytics(), ["x"], [])
    assert "- No significant contributing actions detected" in out


def test_real_causal_factors_listed():
    cf = [
        {"action": "aggressive_prune", "correlation": 0.6, "contribution": 0.41},
        {"action": "rapid_edit", "correlation": -0.2, "contribution": 0.12},
    ]
    out = generate_causal_narrative(_analytics("Diverging"), ["x"], cf)
    assert "- aggressive_prune (contribution: 0.41)" in out
    assert "- rapid_edit (contribution: 0.12)" in out


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
        TelemetryRecord(
            timestamp=ts, superstructure=_state(),
            drift=drift, coherence_health=coherence, trust_band="HIGH",
        ),
    )


def test_endpoint_returns_narrative(client):
    _seed(0.2, 0.6, 0.0)
    _seed(0.8, 0.2, 1.0)
    body = client.get("/operator/telemetry").json()
    assert "narrative" in body
    assert isinstance(body["narrative"], str)
    assert "Identity Movement Summary:" in body["narrative"]
    assert "Overall Interpretation:" in body["narrative"]
    # The endpoint's narrative is exactly generate_causal_narrative of the
    # analytics / alerts / causal_factors it also returns.
    assert body["narrative"] == generate_causal_narrative(
        body["analytics"], body["alerts"], body["causal_factors"]
    )


def test_endpoint_narrative_empty_history(client):
    body = client.get("/operator/telemetry").json()
    assert "narrative" in body
    assert "Trajectory classification: Stable" in body["narrative"]
