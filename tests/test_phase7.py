# tests/test_phase7.py
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
import phase7_telemetry
from phase7_drift import (
    DRIFT_LABEL_WEIGHT,
    DRIFT_NUMERIC_WEIGHT,
    TRUST_HIGH_THRESHOLD,
    TRUST_MEDIUM_THRESHOLD,
    compute_coherence_health,
    compute_drift,
    compute_trust_band,
)
from phase7_telemetry import get_history, record_snapshot


def _uniform_state(
    value: float,
    *,
    dominant: str = "stability",
    invariant: str = "inv",
    operator: str = "op",
) -> SuperstructureState:
    """A SuperstructureState whose every numeric field equals ``value``.

    A single ``value`` knob keeps drift / coherence arithmetic exact and
    easy to reason about; the identity anchors are independently settable so
    label-drift can be exercised in isolation.
    """
    return SuperstructureState(
        pattern=SuperPatternState(
            dominant_pattern=dominant,
            pattern_strength=value,
            pattern_stability=value,
            pattern_coherence=value,
            pattern_identity=f"{dominant}:{value:.2f}",
        ),
        integration=SuperIntegrationState(
            integration_strength=value,
            cross_layer_alignment=value,
            integration_identity=f"int:{value:.2f}",
        ),
        coherence=SuperCoherenceState(
            coherence_level=value,
            drift_resistance=value,
            load_resilience=value,
            coherence_identity=f"coh:{value:.2f}",
        ),
        essence=SuperEssenceState(
            essence_signal=value,
            invariant_identity=invariant,
            essence_clarity=value,
        ),
        identity=SuperIdentityState(
            operator_identity=operator,
            identity_strength=value,
            identity_stability=value,
            identity_projection=value,
        ),
    )


@pytest.fixture(autouse=True)
def _clean_telemetry():
    """Isolate every test from the module-level telemetry store."""
    phase7_telemetry.reset()
    yield
    phase7_telemetry.reset()


# ---------------------------------------------------------------------------
# Determinism (mirrors the Phase 6 deepcopy idiom)
# ---------------------------------------------------------------------------

def test_compute_drift_deterministic():
    a = _uniform_state(0.3, dominant="a")
    b = _uniform_state(0.7, dominant="b")
    assert compute_drift(a, b) == compute_drift(deepcopy(a), deepcopy(b))


def test_compute_coherence_health_deterministic():
    hist = [_uniform_state(0.2), _uniform_state(0.8), _uniform_state(0.5)]
    assert compute_coherence_health(hist) == compute_coherence_health(deepcopy(hist))


def test_compute_trust_band_deterministic():
    assert compute_trust_band(0.4, 0.6) == compute_trust_band(0.4, 0.6)


# ---------------------------------------------------------------------------
# Range checks (0–1)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("p,c", [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (0.3, 0.7), (0.5, 0.5)])
def test_drift_in_range(p, c):
    d = compute_drift(_uniform_state(p, dominant="a"), _uniform_state(c, dominant="b"))
    assert 0.0 <= d <= 1.0


@pytest.mark.parametrize("vals", [[0.0], [1.0], [0.0, 1.0], [0.3, 0.6, 0.9], []])
def test_coherence_in_range(vals):
    ch = compute_coherence_health([_uniform_state(v) for v in vals])
    assert 0.0 <= ch <= 1.0


# ---------------------------------------------------------------------------
# Drift values
# ---------------------------------------------------------------------------

def test_drift_zero_for_identical_states():
    s = _uniform_state(0.42, dominant="a", invariant="b", operator="c")
    assert compute_drift(s, deepcopy(s)) == 0.0


def test_drift_numeric_only():
    prev = _uniform_state(0.0, dominant="a", invariant="b", operator="c")
    curr = _uniform_state(1.0, dominant="a", invariant="b", operator="c")
    # numeric_drift == 1.0, label_drift == 0.0
    assert compute_drift(prev, curr) == pytest.approx(DRIFT_NUMERIC_WEIGHT)


def test_drift_label_only():
    prev = _uniform_state(0.5, dominant="a", invariant="b", operator="c")
    curr = _uniform_state(0.5, dominant="X", invariant="Y", operator="Z")
    # numeric_drift == 0.0, label_drift == 1.0
    assert compute_drift(prev, curr) == pytest.approx(DRIFT_LABEL_WEIGHT)


def test_drift_partial_labels():
    prev = _uniform_state(0.5, dominant="a", invariant="b", operator="c")
    curr = _uniform_state(0.5, dominant="X", invariant="b", operator="c")
    # one of three anchors changed
    assert compute_drift(prev, curr) == pytest.approx(DRIFT_LABEL_WEIGHT / 3)


def test_drift_max_when_everything_moves():
    prev = _uniform_state(0.0, dominant="a", invariant="b", operator="c")
    curr = _uniform_state(1.0, dominant="X", invariant="Y", operator="Z")
    assert compute_drift(prev, curr) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Coherence-health values
# ---------------------------------------------------------------------------

def test_coherence_health_single_snapshot_equals_signal():
    assert compute_coherence_health([_uniform_state(0.8)]) == pytest.approx(0.8)


def test_coherence_health_is_rolling_mean():
    hist = [_uniform_state(0.0), _uniform_state(1.0)]
    assert compute_coherence_health(hist) == pytest.approx(0.5)


def test_coherence_health_empty_is_zero():
    assert compute_coherence_health([]) == 0.0


# ---------------------------------------------------------------------------
# Trust-band mapping
# ---------------------------------------------------------------------------

def test_trust_band_high_medium_low():
    assert compute_trust_band(0.0, 0.9) == "HIGH"    # 0.90
    assert compute_trust_band(0.5, 0.9) == "MEDIUM"  # 0.45
    assert compute_trust_band(0.9, 0.9) == "LOW"     # 0.09


def test_trust_band_thresholds_are_inclusive_lower_bounds():
    assert compute_trust_band(0.0, TRUST_HIGH_THRESHOLD) == "HIGH"
    assert compute_trust_band(0.0, TRUST_MEDIUM_THRESHOLD) == "MEDIUM"
    assert compute_trust_band(0.0, TRUST_MEDIUM_THRESHOLD - 0.05) == "LOW"


def test_trust_band_full_drift_forces_low():
    # Even perfect coherence collapses to LOW when drift is maximal.
    assert compute_trust_band(1.0, 1.0) == "LOW"


# ---------------------------------------------------------------------------
# Telemetry: append behaviour, first-record semantics, isolation, limits
# ---------------------------------------------------------------------------

def test_first_snapshot_has_no_drift_but_has_band():
    record_snapshot("op", _uniform_state(0.9), 1.0)
    rec = get_history("op")[0]
    assert rec.drift is None
    assert rec.coherence_health is not None
    assert rec.trust_band in {"LOW", "MEDIUM", "HIGH"}
    # High coherence + zero effective drift -> HIGH.
    assert rec.trust_band == "HIGH"


def test_second_snapshot_has_drift_in_range():
    record_snapshot("op", _uniform_state(0.8), 1.0)
    record_snapshot("op", _uniform_state(0.2), 2.0)
    rec = get_history("op")[1]
    assert rec.drift is not None
    assert 0.0 <= rec.drift <= 1.0


def test_record_metrics_consistent_with_compute_fns():
    s1 = _uniform_state(0.8)
    s2 = _uniform_state(0.4, dominant="shift")
    record_snapshot("op", s1, 1.0)
    record_snapshot("op", s2, 2.0)
    hist = get_history("op")

    assert hist[0].drift is None
    assert hist[0].coherence_health == pytest.approx(compute_coherence_health([s1]))
    assert hist[0].trust_band == compute_trust_band(0.0, compute_coherence_health([s1]))

    assert hist[1].drift == pytest.approx(compute_drift(s1, s2))
    assert hist[1].coherence_health == pytest.approx(compute_coherence_health([s1, s2]))
    assert hist[1].trust_band == compute_trust_band(
        compute_drift(s1, s2), compute_coherence_health([s1, s2])
    )


def test_append_does_not_mutate_prior_records():
    record_snapshot("op", _uniform_state(0.9), 1.0)
    first_view = get_history("op")
    assert len(first_view) == 1
    rec0 = first_view[0]
    snap = (rec0.timestamp, rec0.drift, rec0.coherence_health, rec0.trust_band)

    record_snapshot("op", _uniform_state(0.1), 2.0)
    record_snapshot("op", _uniform_state(0.5), 3.0)

    # The earlier-returned list is a copy: untouched by later appends.
    assert len(first_view) == 1
    # The first record object itself is unchanged.
    assert (rec0.timestamp, rec0.drift, rec0.coherence_health, rec0.trust_band) == snap
    # And the channel still has the original first record at index 0.
    full = get_history("op")
    assert full[0].timestamp == 1.0
    assert full[0].drift is None


def test_get_history_limit_returns_most_recent_in_order():
    for i in range(5):
        record_snapshot("op", _uniform_state(0.5), float(i))
    last3 = get_history("op", limit=3)
    assert [r.timestamp for r in last3] == [2.0, 3.0, 4.0]


def test_get_history_unknown_operator_is_empty():
    assert get_history("nobody") == []


def test_get_history_nonpositive_limit_is_empty():
    record_snapshot("op", _uniform_state(0.5), 1.0)
    assert get_history("op", limit=0) == []
    assert get_history("op", limit=-3) == []


def test_operators_are_isolated():
    record_snapshot("a", _uniform_state(0.2), 1.0)
    record_snapshot("b", _uniform_state(0.9), 1.0)
    record_snapshot("a", _uniform_state(0.25), 2.0)
    assert len(get_history("a")) == 2
    assert len(get_history("b")) == 1
    # b's lone record is a first snapshot, independent of a's history.
    assert get_history("b")[0].drift is None
