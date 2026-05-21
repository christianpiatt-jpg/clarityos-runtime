"""
Tests for v70 / Unit 76 — EL/INS drift detection + Thread Stability Index.

Covers:
    A. _variance + _slope helpers
    B. _classify_drift rules (oscillating / drifting_el / drifting_ins / stable)
    C. _compute_tsi penalty math + clamping
    D. compute_thread_stability public surface (empty, single-sample, multi-sample)
    E. store_el_ins_record stamps tsi on the record
    F. Edge cases (no thread_id → no TSI stamp; bad inputs raise)
"""
from __future__ import annotations

import pytest

import el_ins
from el_ins.el_ins_store import (
    STABILITY_DEFAULT_WINDOW,
    _classify_drift,
    _classify_trend,
    _compute_tsi,
    _reset_for_tests,
    _slope,
    _variance,
    compute_thread_stability,
    store_el_ins_record,
    get_thread_el_ins,
)


def _mk(cls: str, el: float, ins: float, mode: str = "normal") -> dict:
    if mode == "normal" and cls != "balanced":
        mode = "stabilize" if cls == "high_el" else "expand"
    return {
        "analysis": {
            "el_components": [], "ins_components": [],
            "el_score": el, "ins_score": ins,
            "ratio_classification": cls,
        },
        "reasoning_mode": mode,
        "regression_chain": {
            "projection": None, "drivers": [], "precedents": [],
            "principle_stack": [], "invariant": None,
        },
        "stability_notes": None,
    }


@pytest.fixture(autouse=True)
def _isolate():
    _reset_for_tests()
    yield
    _reset_for_tests()


# ===========================================================================
# A. Variance + slope helpers
# ===========================================================================
class TestStatsHelpers:
    def test_variance_empty_is_zero(self):
        assert _variance([]) == 0.0

    def test_variance_single_sample_is_zero(self):
        assert _variance([5.0]) == 0.0

    def test_variance_constant_series_is_zero(self):
        assert _variance([3.0, 3.0, 3.0, 3.0]) == 0.0

    def test_variance_known_value(self):
        # Population variance of [1, 2, 3, 4] = 1.25
        assert _variance([1.0, 2.0, 3.0, 4.0]) == pytest.approx(1.25)

    def test_slope_empty_is_zero(self):
        assert _slope([]) == 0.0

    def test_slope_single_sample_is_zero(self):
        assert _slope([5.0]) == 0.0

    def test_slope_constant_is_zero(self):
        assert _slope([2.0, 2.0, 2.0]) == 0.0

    def test_slope_strictly_increasing(self):
        assert _slope([1.0, 2.0, 3.0, 4.0]) == pytest.approx(1.0)

    def test_slope_strictly_decreasing(self):
        assert _slope([4.0, 3.0, 2.0, 1.0]) == pytest.approx(-1.0)


# ===========================================================================
# B. Drift classification
# ===========================================================================
class TestClassifyDrift:
    def test_constant_balanced_is_stable(self):
        n = 6
        out = _classify_drift([2.0] * n, [2.0] * n, ["balanced"] * n)
        assert out == "stable"

    def test_rising_el_is_drifting_el(self):
        el = [4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        ins = [2.0] * 6
        cls = ["high_el"] * 6
        assert _classify_drift(el, ins, cls) == "drifting_el"

    def test_rising_ins_is_drifting_ins(self):
        el = [2.0] * 6
        ins = [4.0, 5.0, 6.0, 7.0, 8.0, 9.0]
        cls = ["high_ins"] * 6
        assert _classify_drift(el, ins, cls) == "drifting_ins"

    def test_classification_thrashing_is_oscillating(self):
        # 6 samples, 5 changes → 5/6 ≈ 0.83 > 0.34 → oscillating.
        el = [2.0] * 6
        ins = [2.0] * 6
        cls = ["high_el", "balanced", "high_ins", "balanced", "high_el", "high_ins"]
        assert _classify_drift(el, ins, cls) == "oscillating"

    def test_single_change_is_not_oscillating(self):
        # 6 samples, 1 change. floor(6 * 0.34) = 2, so 1 < 2 → not oscillating.
        cls = ["balanced"] * 5 + ["high_el"]
        out = _classify_drift([2.0] * 6, [2.0] * 6, cls)
        assert out != "oscillating"

    def test_flat_input_below_slope_threshold_is_stable(self):
        # Tiny step won't cross the slope threshold (0.25).
        el = [2.0, 2.05, 2.1, 2.15, 2.2]
        out = _classify_drift(el, [2.0] * 5, ["balanced"] * 5)
        assert out == "stable"


# ===========================================================================
# C. TSI math
# ===========================================================================
class TestComputeTSI:
    def test_constant_series_full_score(self):
        # Identical scores, identical classifications, identical modes.
        out = _compute_tsi(
            [5.0] * 5, [5.0] * 5,
            ["balanced"] * 5, ["normal"] * 5,
        )
        assert out == 100

    def test_high_variance_drops_score(self):
        # Same classification, but high variance in scores.
        out = _compute_tsi(
            [0.0, 10.0, 0.0, 10.0, 0.0],
            [0.0] * 5,
            ["high_el"] * 5,
            ["stabilize"] * 5,
        )
        # Variance is 25.0 (very high) → cap 30 penalty → tsi <= 70.
        assert out < 80

    def test_classification_changes_drop_score(self):
        out = _compute_tsi(
            [5.0] * 5, [5.0] * 5,
            ["balanced", "high_el", "balanced", "high_el", "balanced"],
            ["normal"] * 5,
        )
        # 4 classification changes * 5 = 20 → cap 20 → tsi <= 80.
        assert out <= 80
        assert out >= 70

    def test_tsi_clamped_to_zero(self):
        # Maximum penalty scenario.
        out = _compute_tsi(
            [0.0, 10.0, 0.0, 10.0, 0.0],
            [0.0, 10.0, 0.0, 10.0, 0.0],
            ["high_el", "high_ins", "high_el", "high_ins", "high_el"],
            ["stabilize", "expand", "stabilize", "expand", "stabilize"],
        )
        assert 0 <= out <= 100

    def test_single_sample_full_score(self):
        out = _compute_tsi([5.0], [5.0], ["balanced"], ["normal"])
        assert out == 100


# ===========================================================================
# D. compute_thread_stability public surface
# ===========================================================================
class TestComputeThreadStability:
    def test_empty_thread_returns_stable_default(self):
        out = compute_thread_stability("alice", "ghost")
        assert out["stability"] == "stable"
        assert out["tsi"] == 100
        assert out["window"] == 0
        assert out["thread_id"] == "ghost"

    def test_single_record_is_stable_tsi_100(self):
        store_el_ins_record({
            "operator_id": "alice", "thread_id": "t1",
            "timestamp": 1.0, "source": "on_demand",
            "result": _mk("balanced", 5.0, 5.0),
        })
        out = compute_thread_stability("alice", "t1")
        assert out["stability"] == "stable"
        assert out["tsi"] == 100
        assert out["window"] == 1

    def test_rising_el_classified_drifting_el(self):
        for i, el in enumerate([5.0, 6.0, 7.0, 8.0, 9.0, 10.0]):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": float(1000 + i),
                "source": "on_demand",
                "result": _mk("high_el", el, 1.0, "stabilize"),
            })
        out = compute_thread_stability("alice", "t1")
        assert out["stability"] == "drifting_el"
        assert out["window"] == 6

    def test_window_clamped_to_recent_n(self):
        # 20 records, ask for window=5 — only the most recent 5 sampled.
        for i in range(20):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": float(1000 + i),
                "source": "on_demand",
                "result": _mk("balanced", 2.0, 2.0),
            })
        out = compute_thread_stability("alice", "t1", window=5)
        assert out["window"] == 5

    def test_validates_arguments(self):
        with pytest.raises(ValueError):
            compute_thread_stability("", "t1")
        with pytest.raises(ValueError):
            compute_thread_stability("alice", "")

    def test_per_thread_isolation(self):
        # Two threads on the same operator — one drifting, one stable.
        for i in range(6):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "drifting",
                "timestamp": float(1000 + i),
                "source": "on_demand",
                "result": _mk("high_el", 4.0 + i, 1.0, "stabilize"),
            })
        for i in range(6):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "stable",
                "timestamp": float(2000 + i),
                "source": "on_demand",
                "result": _mk("balanced", 2.0, 2.0),
            })
        assert compute_thread_stability("alice", "drifting")["stability"] == "drifting_el"
        assert compute_thread_stability("alice", "stable")["stability"] == "stable"


# ===========================================================================
# E. store_el_ins_record stamps TSI
# ===========================================================================
class TestTSIStamping:
    def test_records_with_thread_id_get_tsi(self):
        store_el_ins_record({
            "operator_id": "alice", "thread_id": "t1",
            "timestamp": 1.0, "source": "on_demand",
            "result": _mk("balanced", 5.0, 5.0),
        })
        rows = get_thread_el_ins("alice", "t1")
        assert len(rows) == 1
        assert "tsi" in rows[0]
        assert rows[0]["tsi"] == 100  # single record on a fresh thread

    def test_records_without_thread_id_have_no_tsi(self):
        store_el_ins_record({
            "operator_id": "alice", "thread_id": None,
            "timestamp": 1.0, "source": "on_demand",
            "result": _mk("balanced", 5.0, 5.0),
        })
        rows = el_ins.get_recent_el_ins("alice")
        assert len(rows) == 1
        # tsi key may be absent or None — both acceptable for thread-less records.
        assert rows[0].get("tsi") is None or "tsi" not in rows[0]

    def test_tsi_decreases_as_thread_becomes_volatile(self):
        # First record: perfect stability (single sample → 100).
        # Then add 6 more with massive swings — TSI should slide down.
        for i, (el, cls) in enumerate([
            (5.0, "balanced"),
            (10.0, "high_el"),
            (0.5, "high_ins"),
            (9.5, "high_el"),
            (0.2, "high_ins"),
        ]):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": float(1000 + i),
                "source": "on_demand",
                "result": _mk(cls, el, 10.0 - el),
            })
        rows = get_thread_el_ins("alice", "t1")  # newest-first
        first_stored = rows[-1]
        latest = rows[0]
        # Newest record sees full thread history → must have lower TSI
        # than the lone first record's stamped TSI (which saw n=1 → 100).
        assert latest["tsi"] < first_stored["tsi"]

    def test_tsi_clamped_to_int_range(self):
        for i in range(15):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": float(1000 + i),
                "source": "on_demand",
                "result": _mk("balanced", 2.0, 2.0),
            })
        rows = get_thread_el_ins("alice", "t1")
        for r in rows:
            t = r.get("tsi")
            assert isinstance(t, int)
            assert 0 <= t <= 100


# ===========================================================================
# F. _classify_trend (used by operator summary)
# ===========================================================================
class TestClassifyTrend:
    def test_rising_tsi_is_improving(self):
        # Reverse=False here — _classify_trend expects chronological order
        # (oldest→newest), which is how compute_operator_summary feeds it.
        assert _classify_trend([60, 70, 80, 90]) == "improving"

    def test_falling_tsi_is_declining(self):
        assert _classify_trend([90, 80, 70, 60]) == "declining"

    def test_flat_tsi_is_stable(self):
        assert _classify_trend([70, 70, 70, 70]) == "stable"

    def test_tiny_wobble_below_threshold_is_stable(self):
        # Slope of [50, 51] is 1.0 which is > 0.5, but on a 2-sample
        # input we're at the boundary. Use 3 samples with tiny wobble.
        assert _classify_trend([70, 71, 70]) == "stable"

    def test_empty_is_stable(self):
        assert _classify_trend([]) == "stable"

    def test_single_is_stable(self):
        assert _classify_trend([55]) == "stable"
