# tests/test_phase7_analytics.py
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
from phase7_storage import TelemetryRecord
from phase7_analytics import (
    RECOVERING_THRESHOLD,
    STABLE_THRESHOLD,
    WOBBLING_THRESHOLD,
    classify_trajectory,
    compute_coherence_trend,
    compute_drift_acceleration,
    compute_drift_velocity,
    compute_stability_forecast,
)


def _state() -> SuperstructureState:
    """A trivial SuperstructureState — analytics never reads it, only the
    record's drift / coherence_health fields."""
    return SuperstructureState(
        pattern=SuperPatternState("p", 0.0, 0.0, 0.0, "p"),
        integration=SuperIntegrationState(0.0, 0.0, "i"),
        coherence=SuperCoherenceState(0.0, 0.0, 0.0, "c"),
        essence=SuperEssenceState(0.0, "e", 0.0),
        identity=SuperIdentityState("o", 0.0, 0.0, 0.0),
    )


def _rec(drift, coherence, ts: float = 0.0) -> TelemetryRecord:
    return TelemetryRecord(
        timestamp=ts,
        superstructure=_state(),
        drift=drift,
        coherence_health=coherence,
        trust_band="HIGH",
    )


def _history(drifts, coherences=None):
    """Build a chronological history from a list of drift values (and optional
    matching coherence values; defaults to a flat 0.5)."""
    if coherences is None:
        coherences = [0.5] * len(drifts)
    return [_rec(d, c, float(i)) for i, (d, c) in enumerate(zip(drifts, coherences))]


# ---------------------------------------------------------------------------
# Determinism (Phase 6 deepcopy idiom)
# ---------------------------------------------------------------------------

def test_drift_velocity_deterministic():
    h = _history([0.1, 0.2, 0.3])
    assert compute_drift_velocity(h) == compute_drift_velocity(deepcopy(h))


def test_drift_acceleration_deterministic():
    h = _history([0.1, 0.25, 0.55, 1.0])
    assert compute_drift_acceleration(h) == compute_drift_acceleration(deepcopy(h))


def test_coherence_trend_deterministic():
    h = _history([0.3, 0.3, 0.3], [0.2, 0.5, 0.9])
    assert compute_coherence_trend(h) == compute_coherence_trend(deepcopy(h))


def test_forecast_and_classify_deterministic():
    assert compute_stability_forecast(0.3, -0.2, 0.4) == compute_stability_forecast(0.3, -0.2, 0.4)
    assert classify_trajectory(0.6) == classify_trajectory(0.6)


# ---------------------------------------------------------------------------
# Range checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("drifts", [
    [0.0], [1.0, 0.0], [0.0, 0.5, 1.0], [1.0, 0.75, 0.5, 0.25, 0.0],
    [0.2, 0.9, 0.1, 0.8, 0.3], [0.0, 1.0, 0.0, 1.0, 0.0],
])
def test_velocity_and_acceleration_in_range(drifts):
    h = _history(drifts)
    assert -1.0 <= compute_drift_velocity(h) <= 1.0
    assert -1.0 <= compute_drift_acceleration(h) <= 1.0


@pytest.mark.parametrize("coherences", [
    [0.0], [0.0, 1.0], [1.0, 0.0], [0.1, 0.4, 0.7, 1.0], [0.5, 0.5, 0.5],
])
def test_coherence_trend_in_range(coherences):
    h = _history([0.3] * len(coherences), coherences)
    assert -1.0 <= compute_coherence_trend(h) <= 1.0


def test_forecast_in_range_for_extreme_inputs():
    for v in (-1.0, 0.0, 1.0):
        for a in (-1.0, 0.0, 1.0):
            for c in (-1.0, 0.0, 1.0):
                assert 0.0 <= compute_stability_forecast(v, a, c) <= 1.0


# ---------------------------------------------------------------------------
# Slope signs
# ---------------------------------------------------------------------------

def test_velocity_positive_for_increasing_drift():
    assert compute_drift_velocity(_history([0.1, 0.2, 0.3, 0.4, 0.5])) > 0.0


def test_velocity_negative_for_decreasing_drift():
    assert compute_drift_velocity(_history([0.5, 0.4, 0.3, 0.2, 0.1])) < 0.0


def test_velocity_zero_for_flat_drift():
    assert compute_drift_velocity(_history([0.3, 0.3, 0.3, 0.3, 0.3])) == 0.0


def test_coherence_trend_positive_when_improving():
    h = _history([0.3] * 5, [0.1, 0.3, 0.5, 0.7, 0.9])
    assert compute_coherence_trend(h) > 0.0


def test_coherence_trend_negative_when_worsening():
    h = _history([0.3] * 5, [0.9, 0.7, 0.5, 0.3, 0.1])
    assert compute_coherence_trend(h) < 0.0


# ---------------------------------------------------------------------------
# Acceleration signs (second derivative)
# ---------------------------------------------------------------------------

def test_acceleration_positive_for_accelerating_drift():
    # first differences 0.25, 0.50 → rising → positive acceleration
    assert compute_drift_acceleration(_history([0.0, 0.25, 0.75])) > 0.0


def test_acceleration_negative_for_decelerating_drift():
    # first differences 0.50, 0.25 → falling → negative acceleration
    assert compute_drift_acceleration(_history([0.0, 0.5, 0.75])) < 0.0


def test_acceleration_zero_for_linear_drift():
    # constant first differences (0.25 each) → zero acceleration
    assert compute_drift_acceleration(_history([0.0, 0.25, 0.5, 0.75])) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Short-history behaviour
# ---------------------------------------------------------------------------

def test_empty_history_all_zero():
    assert compute_drift_velocity([]) == 0.0
    assert compute_drift_acceleration([]) == 0.0
    assert compute_coherence_trend([]) == 0.0


def test_single_point_all_zero():
    # A first snapshot carries drift=None; one point yields no slopes.
    h = [_rec(None, 0.5)]
    assert compute_drift_velocity(h) == 0.0
    assert compute_drift_acceleration(h) == 0.0
    assert compute_coherence_trend(h) == 0.0


def test_two_points_velocity_but_no_acceleration():
    h = _history([0.1, 0.3], [0.2, 0.4])
    assert compute_drift_velocity(h) == pytest.approx(0.2)   # 0.3 - 0.1
    assert compute_coherence_trend(h) == pytest.approx(0.2)  # 0.4 - 0.2
    assert compute_drift_acceleration(h) == 0.0              # < 3 drift points


def test_none_drift_is_skipped():
    # Realistic history: first record drift=None, then 0.0, 0.25, 0.5.
    h = _history([None, 0.0, 0.25, 0.5])
    # usable drift series [0.0, 0.25, 0.5] → slope 0.25
    assert compute_drift_velocity(h) == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Regression window (last N=5)
# ---------------------------------------------------------------------------

def test_only_last_five_points_used():
    # 7 points; the first two (0.9, 0.9) would skew the slope if included.
    h = _history([0.9, 0.9, 0.0, 0.25, 0.5, 0.75, 1.0])
    # last 5 = [0.0, 0.25, 0.5, 0.75, 1.0] → slope 0.25
    assert compute_drift_velocity(h) == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# Stability forecast formula
# ---------------------------------------------------------------------------

def test_forecast_best_case_is_one():
    # steady drift (v=0), decelerating (a=-1), coherence rising (c=+1)
    assert compute_stability_forecast(0.0, -1.0, 1.0) == pytest.approx(1.0)


def test_forecast_worst_case_is_zero():
    # max velocity, max acceleration, falling coherence
    assert compute_stability_forecast(1.0, 1.0, -1.0) == pytest.approx(0.0)


def test_forecast_matches_formula():
    v, a, c = 0.2, -0.4, 0.6
    expected = 0.4 * (1 - abs(v)) + 0.3 * ((-a + 1) / 2) + 0.3 * ((c + 1) / 2)
    assert compute_stability_forecast(v, a, c) == pytest.approx(expected)


def test_forecast_neutral_inputs():
    # v=0, a=0, c=0 → 0.4 + 0.15 + 0.15 = 0.7
    assert compute_stability_forecast(0.0, 0.0, 0.0) == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Trajectory classification boundaries
# ---------------------------------------------------------------------------

def test_classify_inclusive_lower_bounds():
    assert classify_trajectory(STABLE_THRESHOLD) == "Stable"
    assert classify_trajectory(0.90) == "Stable"
    assert classify_trajectory(RECOVERING_THRESHOLD) == "Recovering"
    assert classify_trajectory(0.74) == "Recovering"
    assert classify_trajectory(WOBBLING_THRESHOLD) == "Wobbling"
    assert classify_trajectory(0.49) == "Wobbling"
    assert classify_trajectory(WOBBLING_THRESHOLD - 0.01) == "Diverging"
    assert classify_trajectory(0.0) == "Diverging"


def test_classify_returns_one_of_four_labels():
    for f in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        assert classify_trajectory(f) in {"Stable", "Recovering", "Wobbling", "Diverging"}


# ---------------------------------------------------------------------------
# End-to-end pipeline
# ---------------------------------------------------------------------------

def test_pipeline_flat_neutral_history_is_recovering():
    # Flat drift + flat coherence → v=0, a=0, trend=0 → forecast 0.7 → Recovering.
    h = _history([0.2, 0.2, 0.2, 0.2, 0.2], [0.6, 0.6, 0.6, 0.6, 0.6])
    v = compute_drift_velocity(h)
    a = compute_drift_acceleration(h)
    c = compute_coherence_trend(h)
    f = compute_stability_forecast(v, a, c)
    assert (v, a, c) == (0.0, 0.0, 0.0)
    assert f == pytest.approx(0.7)
    assert classify_trajectory(f) == "Recovering"


def test_pipeline_diverging_history_classifies_low():
    # A maximal drift jump (velocity → 1, clamped) with collapsing coherence
    # drives the forecast to its floor. (Velocity is window-bounded, so this
    # needs a sharp 2-point move rather than a gentle 5-point ramp.)
    h = _history([0.0, 1.0], [1.0, 0.0])
    v = compute_drift_velocity(h)        # slope 1.0 → clamp 1.0
    a = compute_drift_acceleration(h)    # < 3 drift points → 0.0
    c = compute_coherence_trend(h)       # slope -1.0
    f = compute_stability_forecast(v, a, c)
    assert v == pytest.approx(1.0)
    assert c == pytest.approx(-1.0)
    # forecast = 0.4*0 + 0.3*0.5 + 0.3*0 = 0.15 → Diverging
    assert f == pytest.approx(0.15)
    assert classify_trajectory(f) == "Diverging"
