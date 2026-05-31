# tests/test_phase7_causality.py
#
# CARD 7.7 — pure causal-drift mapping over (history, recent_actions), plus
# endpoint integration (the `causal_factors` field on /operator/telemetry).
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
from phase7_storage import TelemetryRecord
from phase7_causality import (
    CausalFactor,
    OperatorAction,
    compute_causal_factors,
)
from phase7_endpoint import OPERATOR_ID

NONE_FACTOR = CausalFactor("none", 0.0, 0.0)


def _state() -> SuperstructureState:
    return SuperstructureState(
        pattern=SuperPatternState("p", 0.0, 0.0, 0.0, "p"),
        integration=SuperIntegrationState(0.0, 0.0, "i"),
        coherence=SuperCoherenceState(0.0, 0.0, 0.0, "c"),
        essence=SuperEssenceState(0.0, "e", 0.0),
        identity=SuperIdentityState("o", 0.0, 0.0, 0.0),
    )


def _hist(points):
    """points: list of (timestamp, drift|None, coherence)."""
    return [
        TelemetryRecord(
            timestamp=ts, superstructure=_state(),
            drift=d, coherence_health=c, trust_band="HIGH",
        )
        for (ts, d, c) in points
    ]


def _act(name, ts):
    return OperatorAction(name, ts)


# ---------------------------------------------------------------------------
# Correlation signs
# ---------------------------------------------------------------------------

def test_correlation_positive_when_drift_rises_after_action():
    # Drift flat through t=2, then rising; coherence flat.
    hist = _hist([(0, None, 0.5), (1, 0.0, 0.5), (2, 0.0, 0.5), (3, 0.25, 0.5), (4, 0.5, 0.5)])
    factors = compute_causal_factors(hist, [_act("risky_edit", 2.0)])
    assert factors[0].action == "risky_edit"
    assert factors[0].correlation > 0.0
    assert factors[0].contribution == pytest.approx(0.125)  # (0.25 + 0) / 2


def test_correlation_negative_but_surfaced_via_coherence_fall():
    # Drift falls after t=2 (negative correlation) but coherence collapses,
    # so the factor still contributes to instability.
    hist = _hist([(0, None, 0.9), (1, 0.5, 0.9), (2, 0.5, 0.9), (3, 0.25, 0.6), (4, 0.0, 0.3)])
    factors = compute_causal_factors(hist, [_act("aggressive_prune", 2.0)])
    assert factors[0].action == "aggressive_prune"
    assert factors[0].correlation < 0.0
    assert factors[0].contribution == pytest.approx(0.15)  # (0 + 0.3) / 2


def test_stabilizing_action_filtered_to_none():
    # Drift falls AND coherence rises after t=2 → no destabilizing contribution.
    hist = _hist([(0, None, 0.3), (1, 0.5, 0.3), (2, 0.5, 0.3), (3, 0.25, 0.6), (4, 0.0, 0.9)])
    assert compute_causal_factors(hist, [_act("good_edit", 2.0)]) == [NONE_FACTOR]


# ---------------------------------------------------------------------------
# Thresholds + clamping
# ---------------------------------------------------------------------------

def test_subthreshold_contribution_filtered_to_none():
    # A tiny post-action drift rise → contribution well below 0.05.
    hist = _hist([(0, None, 0.5), (1, 0.0, 0.5), (2, 0.0, 0.5), (3, 0.0, 0.5), (4, 0.05, 0.5)])
    assert compute_causal_factors(hist, [_act("tiny", 2.0)]) == [NONE_FACTOR]


@pytest.mark.parametrize("points", [
    [(0, None, 0.5), (1, 1.0, 0.0), (2, 0.0, 1.0), (3, 1.0, 0.0)],
    [(0, None, 0.0), (1, 1.0, 1.0), (2, 0.0, 0.0), (3, 1.0, 1.0), (4, 0.0, 0.0)],
])
def test_outputs_stay_in_range(points):
    hist = _hist(points)
    actions = [_act("a", 0.5), _act("b", 1.5), _act("c", 2.5)]
    for f in compute_causal_factors(hist, actions):
        assert -1.0 <= f.correlation <= 1.0
        assert 0.0 <= f.contribution <= 1.0


# ---------------------------------------------------------------------------
# Empty inputs → neutral sentinel
# ---------------------------------------------------------------------------

def test_empty_action_log_returns_none():
    hist = _hist([(0, None, 0.5), (1, 0.2, 0.5), (2, 0.8, 0.5)])
    assert compute_causal_factors(hist, []) == [NONE_FACTOR]


def test_empty_history_returns_none():
    assert compute_causal_factors([], [_act("x", 1.0)]) == [NONE_FACTOR]


# ---------------------------------------------------------------------------
# Sorting + window
# ---------------------------------------------------------------------------

def test_factors_sorted_by_contribution_desc():
    # Drift rises only late; an action just before the rise sees a bigger shift
    # than one at the start.
    hist = _hist([(0, None, 0.5), (1, 0.0, 0.5), (2, 0.0, 0.5), (3, 0.5, 0.5), (4, 1.0, 0.5)])
    factors = compute_causal_factors(hist, [_act("early", 0.5), _act("late", 2.5)])
    assert [f.action for f in factors] == ["late", "early"]
    assert factors[0].contribution >= factors[1].contribution


def test_only_last_ten_actions_considered():
    hist = _hist([(0, None, 0.5), (1, 0.0, 0.5), (2, 0.0, 0.5), (3, 0.5, 0.5), (4, 1.0, 0.5)])
    actions = [_act(f"old{i}", 0.1) for i in range(3)] + [_act(f"recent{i}", 2.5) for i in range(10)]
    factors = compute_causal_factors(hist, actions)
    names = {f.action for f in factors}
    assert not any(n.startswith("old") for n in names)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_deterministic():
    hist = _hist([(0, None, 0.5), (1, 0.1, 0.6), (2, 0.3, 0.4), (3, 0.5, 0.5)])
    actions = [_act("a", 1.5), _act("b", 2.5)]
    assert compute_causal_factors(hist, actions) == compute_causal_factors(
        deepcopy(hist), deepcopy(actions)
    )


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


def _seed(drift, coherence, ts):
    phase7_storage.append_record(
        OPERATOR_ID,
        TelemetryRecord(
            timestamp=ts, superstructure=_state(),
            drift=drift, coherence_health=coherence, trust_band="HIGH",
        ),
    )


def test_endpoint_returns_causal_factors_field(client):
    _seed(0.2, 0.6, 0.0)
    _seed(0.8, 0.2, 1.0)
    body = client.get("/operator/telemetry").json()
    assert "causal_factors" in body
    assert isinstance(body["causal_factors"], list)
    # Backend has no operator-action log → the neutral sentinel.
    assert body["causal_factors"] == [
        {"action": "none", "correlation": 0.0, "contribution": 0.0}
    ]


def test_endpoint_causal_factors_empty_history(client):
    body = client.get("/operator/telemetry").json()
    assert body["causal_factors"] == [
        {"action": "none", "correlation": 0.0, "contribution": 0.0}
    ]
