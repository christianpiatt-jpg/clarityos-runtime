"""
Tests for ELINS12 Unit 31 — multi-regime temporal fusion engine.

Layered coverage (>= 60 tests, target ~75):
    A. Top-level shape / locked keys
    B. Trajectory — start / end / counts / dominant_direction
    C. Oscillation — is_oscillating, count, span
    D. Whipsaw detection
    E. Cumulative risk — counts + weighted score + level
    F. Long-arc assessment (priority-ordered)
    G. Summary string content
    H. Empty / single-entry edges
    I. History pass-through
    J. Determinism
    K. Validation
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_regime_fusion as rf_mod


# ===========================================================================
# Fixtures — synthetic Unit 29 comparison objects
# ===========================================================================
def _comparison(regime_delta: str = "same",
                risk: str = "low",
                baseline_regime: str = "stable",
                candidate_regime: str = "stable") -> dict:
    """Minimal Unit 29 comparison dict for fusion-engine tests.
    Only the keys Unit 31 reads are surfaced; the rest of the Unit 29
    contract is irrelevant here."""
    return {
        "regime_delta":    regime_delta,
        "risk_assessment": risk,
        "baseline":        {"regime_class": baseline_regime},
        "candidate":       {"regime_class": candidate_regime},
    }


def _degraded_history(n: int = 5,
                       risk_pattern=None) -> list:
    """A monotonically-degrading history. `risk_pattern` defaults to
    medium across the board."""
    risks = risk_pattern or ["medium"] * n
    return [
        _comparison("degraded", risks[i], "stable", "transition")
        for i in range(n)
    ]


def _improved_history(n: int = 5,
                       risk_pattern=None) -> list:
    risks = risk_pattern or ["low"] * n
    return [
        _comparison("improved", risks[i], "unstable", "transition")
        for i in range(n)
    ]


def _oscillating_history(deltas: list,
                          risk: str = "medium") -> list:
    return [_comparison(d, risk) for d in deltas]


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        out = rf_mod.fuse_regime_history([_comparison()])
        assert set(out.keys()) == {
            "history", "trajectory", "oscillation",
            "cumulative_risk", "long_arc_assessment", "summary",
        }

    def test_trajectory_keys_locked(self):
        out = rf_mod.fuse_regime_history([_comparison()])
        assert set(out["trajectory"].keys()) == {
            "start_regime", "end_regime",
            "dominant_direction", "regime_delta_counts",
        }

    def test_oscillation_keys_locked(self):
        out = rf_mod.fuse_regime_history([_comparison()])
        assert set(out["oscillation"].keys()) == {
            "is_oscillating", "oscillation_count",
            "max_back_and_forth_span", "whipsaw",
        }

    def test_cumulative_risk_keys_locked(self):
        out = rf_mod.fuse_regime_history([_comparison()])
        assert set(out["cumulative_risk"].keys()) == {
            "low_count", "medium_count", "high_count",
            "risk_score", "risk_level",
        }

    def test_long_arc_assessment_in_locked_vocab(self):
        out = rf_mod.fuse_regime_history([_comparison()])
        assert out["long_arc_assessment"] in (
            "stabilizing", "persistent_degradation",
            "persistent_risk", "oscillating_regime", "benign",
        )


# ===========================================================================
# B. Trajectory — start / end / counts / dominant_direction
# ===========================================================================
class TestTrajectory:
    def test_start_regime_from_first_baseline(self):
        history = [
            _comparison("degraded", baseline_regime="stable",
                         candidate_regime="transition"),
            _comparison("degraded", baseline_regime="transition",
                         candidate_regime="unstable"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["start_regime"] == "stable"

    def test_end_regime_from_last_candidate(self):
        history = [
            _comparison("degraded", baseline_regime="stable",
                         candidate_regime="transition"),
            _comparison("degraded", baseline_regime="transition",
                         candidate_regime="unstable"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["end_regime"] == "unstable"

    def test_regime_delta_counts_summed(self):
        history = [
            _comparison("same"),
            _comparison("improved"),
            _comparison("improved"),
            _comparison("degraded"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["regime_delta_counts"] == {
            "same": 1, "improved": 2, "degraded": 1,
        }

    def test_dominant_direction_degrading(self):
        history = _degraded_history(4)
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["dominant_direction"] == "degrading"

    def test_dominant_direction_improving(self):
        history = _improved_history(4)
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["dominant_direction"] == "improving"

    def test_dominant_direction_flat_on_all_same(self):
        history = [_comparison("same") for _ in range(5)]
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["dominant_direction"] == "flat"

    def test_dominant_direction_oscillating_when_balanced(self):
        history = [
            _comparison("improved"),
            _comparison("degraded"),
            _comparison("improved"),
            _comparison("degraded"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["dominant_direction"] == "oscillating"

    def test_dominant_direction_oscillating_when_below_min(self):
        # Only one degraded — below the dominant minimum (2).
        history = [
            _comparison("improved"),
            _comparison("degraded"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["dominant_direction"] == "oscillating"

    def test_dominant_direction_single_degraded_with_sames(self):
        history = [
            _comparison("same"), _comparison("same"),
            _comparison("degraded"),
        ]
        out = rf_mod.fuse_regime_history(history)
        # 1 degraded, 0 improved → below dominant minimum → oscillating.
        assert out["trajectory"]["dominant_direction"] == "oscillating"


# ===========================================================================
# C. Oscillation
# ===========================================================================
class TestOscillation:
    def test_no_oscillation_in_degraded_run(self):
        history = _degraded_history(5)
        out = rf_mod.fuse_regime_history(history)
        assert out["oscillation"]["is_oscillating"] is False

    def test_oscillation_fires_on_alternation_3(self):
        history = _oscillating_history(["improved", "degraded", "improved"])
        out = rf_mod.fuse_regime_history(history)
        assert out["oscillation"]["is_oscillating"] is True

    def test_no_oscillation_on_alternation_2(self):
        history = _oscillating_history(["improved", "degraded"])
        out = rf_mod.fuse_regime_history(history)
        assert out["oscillation"]["is_oscillating"] is False

    def test_oscillation_count(self):
        history = _oscillating_history(
            ["improved", "degraded", "improved", "degraded",
             "improved", "degraded"],
        )
        out = rf_mod.fuse_regime_history(history)
        # Single maximal alternating run of length 6.
        assert out["oscillation"]["oscillation_count"] == 1

    def test_max_span_correct(self):
        history = _oscillating_history(
            ["improved", "degraded", "improved", "degraded"],
        )
        out = rf_mod.fuse_regime_history(history)
        assert out["oscillation"]["max_back_and_forth_span"] == 4

    def test_same_entries_ignored_for_oscillation(self):
        # "same" deltas are filtered out — pattern alternates either side.
        history = _oscillating_history(
            ["improved", "same", "degraded", "same", "improved"],
        )
        out = rf_mod.fuse_regime_history(history)
        # Filtered sequence is [improved, degraded, improved] → run of 3.
        assert out["oscillation"]["is_oscillating"] is True
        assert out["oscillation"]["max_back_and_forth_span"] == 3

    def test_multiple_runs_counted(self):
        # Two separate alternating runs broken by a repeat.
        history = _oscillating_history(
            ["improved", "degraded", "improved",
             "improved",
             "degraded", "improved", "degraded"],
        )
        out = rf_mod.fuse_regime_history(history)
        assert out["oscillation"]["oscillation_count"] == 2


# ===========================================================================
# D. Whipsaw detection
# ===========================================================================
class TestWhipsaw:
    def test_whipsaw_fires_at_span_4(self):
        history = _oscillating_history(
            ["improved", "degraded", "improved", "degraded"],
        )
        out = rf_mod.fuse_regime_history(history)
        assert out["oscillation"]["whipsaw"] is True

    def test_no_whipsaw_at_span_3(self):
        history = _oscillating_history(
            ["improved", "degraded", "improved"],
        )
        out = rf_mod.fuse_regime_history(history)
        assert out["oscillation"]["whipsaw"] is False

    def test_no_whipsaw_without_oscillation(self):
        history = _degraded_history(5)
        out = rf_mod.fuse_regime_history(history)
        assert out["oscillation"]["whipsaw"] is False


# ===========================================================================
# E. Cumulative risk
# ===========================================================================
class TestCumulativeRisk:
    def test_counts_by_risk_tier(self):
        history = [
            _comparison(risk="low"),
            _comparison(risk="low"),
            _comparison(risk="medium"),
            _comparison(risk="high"),
        ]
        out = rf_mod.fuse_regime_history(history)
        cr = out["cumulative_risk"]
        assert cr["low_count"]    == 2
        assert cr["medium_count"] == 1
        assert cr["high_count"]   == 1

    def test_risk_score_mean_weighted(self):
        history = [
            _comparison(risk="low"),    # 1
            _comparison(risk="medium"), # 2
            _comparison(risk="high"),   # 3
        ]
        out = rf_mod.fuse_regime_history(history)
        # mean = 6/3 = 2.0
        assert out["cumulative_risk"]["risk_score"] == pytest.approx(2.0)

    def test_all_low_yields_low_level(self):
        history = [_comparison(risk="low") for _ in range(5)]
        out = rf_mod.fuse_regime_history(history)
        assert out["cumulative_risk"]["risk_level"] == "low"

    def test_three_or_more_high_yields_high_level(self):
        history = [
            _comparison(risk="high"),
            _comparison(risk="high"),
            _comparison(risk="high"),
            _comparison(risk="low"),
            _comparison(risk="low"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["cumulative_risk"]["risk_level"] == "high"

    def test_score_above_2_3_yields_high(self):
        # 3 highs + 1 medium → score = (3+3+3+2)/4 = 2.75.
        history = [_comparison(risk="high") for _ in range(3)] + [
            _comparison(risk="medium"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["cumulative_risk"]["risk_level"] == "high"

    def test_medium_band(self):
        history = [
            _comparison(risk="low"),
            _comparison(risk="medium"),
            _comparison(risk="medium"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["cumulative_risk"]["risk_level"] == "medium"

    def test_single_high_is_not_high_level(self):
        # high_count == 1, score = (1+1+3)/3 ≈ 1.67 → medium.
        history = [
            _comparison(risk="low"),
            _comparison(risk="low"),
            _comparison(risk="high"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["cumulative_risk"]["risk_level"] == "medium"

    def test_low_threshold_score_boundary(self):
        # All lows → score 1.0 ≤ 1.3 → low.
        history = [_comparison(risk="low") for _ in range(3)]
        out = rf_mod.fuse_regime_history(history)
        assert out["cumulative_risk"]["risk_level"] == "low"


# ===========================================================================
# F. Long-arc assessment (priority-ordered)
# ===========================================================================
class TestLongArcAssessment:
    def test_persistent_degradation_when_degrading_non_low(self):
        history = _degraded_history(
            5, risk_pattern=["medium"] * 5,
        )
        out = rf_mod.fuse_regime_history(history)
        assert out["long_arc_assessment"] == "persistent_degradation"

    def test_stabilizing_when_improving_and_low(self):
        history = _improved_history(
            4, risk_pattern=["low"] * 4,
        )
        out = rf_mod.fuse_regime_history(history)
        assert out["long_arc_assessment"] == "stabilizing"

    def test_oscillating_regime_on_whipsaw(self):
        history = _oscillating_history(
            ["improved", "degraded", "improved", "degraded",
             "improved", "degraded"],
            risk="low",
        )
        out = rf_mod.fuse_regime_history(history)
        assert out["long_arc_assessment"] == "oscillating_regime"

    def test_persistent_risk_on_high_flat(self):
        # All same regime + all high risk → flat direction, high risk.
        history = [_comparison("same", "high") for _ in range(4)]
        out = rf_mod.fuse_regime_history(history)
        assert out["long_arc_assessment"] == "persistent_risk"

    def test_benign_default(self):
        # Improving direction + medium risk → falls through to benign.
        history = _improved_history(
            3, risk_pattern=["medium"] * 3,
        )
        out = rf_mod.fuse_regime_history(history)
        assert out["long_arc_assessment"] == "benign"

    def test_persistent_degradation_takes_priority_over_oscillating(self):
        # 4 degraded + 1 improved → direction "degrading" (priority).
        history = [
            _comparison("degraded"),
            _comparison("degraded"),
            _comparison("degraded"),
            _comparison("degraded"),
            _comparison("improved"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert out["trajectory"]["dominant_direction"] == "degrading"


# ===========================================================================
# G. Summary string content
# ===========================================================================
class TestSummary:
    def test_summary_non_empty(self):
        out = rf_mod.fuse_regime_history([_comparison()])
        assert out["summary"].strip() != ""

    def test_summary_mentions_assessment(self):
        history = _degraded_history(5)
        out = rf_mod.fuse_regime_history(history)
        assert "persistent degradation" in out["summary"].lower()

    def test_summary_mentions_risk_level(self):
        history = _degraded_history(5, risk_pattern=["high"] * 5)
        out = rf_mod.fuse_regime_history(history)
        assert "high risk" in out["summary"].lower()

    def test_summary_mentions_segment_count(self):
        history = _degraded_history(5)
        out = rf_mod.fuse_regime_history(history)
        assert "5 comparisons" in out["summary"]

    def test_summary_mentions_whipsaw(self):
        history = _oscillating_history(
            ["improved", "degraded", "improved", "degraded"],
        )
        out = rf_mod.fuse_regime_history(history)
        assert "whipsaw" in out["summary"].lower()

    def test_summary_mentions_oscillation_without_whipsaw(self):
        history = _oscillating_history(
            ["improved", "degraded", "improved"],
        )
        out = rf_mod.fuse_regime_history(history)
        assert "oscillating" in out["summary"].lower()


# ===========================================================================
# H. Empty / single-entry edges
# ===========================================================================
class TestEmptyAndSmall:
    def test_empty_history_returns_well_formed(self):
        out = rf_mod.fuse_regime_history([])
        assert set(out.keys()) == {
            "history", "trajectory", "oscillation",
            "cumulative_risk", "long_arc_assessment", "summary",
        }

    def test_empty_history_is_benign(self):
        out = rf_mod.fuse_regime_history([])
        assert out["long_arc_assessment"] == "benign"

    def test_empty_history_zero_counts(self):
        out = rf_mod.fuse_regime_history([])
        assert out["trajectory"]["regime_delta_counts"] == {
            "same": 0, "improved": 0, "degraded": 0,
        }
        assert out["cumulative_risk"]["low_count"] == 0
        assert out["oscillation"]["oscillation_count"] == 0

    def test_single_entry_returns_well_formed(self):
        out = rf_mod.fuse_regime_history([_comparison()])
        assert out["trajectory"]["start_regime"] == "stable"
        assert out["oscillation"]["is_oscillating"] is False


# ===========================================================================
# I. History pass-through
# ===========================================================================
class TestHistoryPassthrough:
    def test_history_echoed(self):
        history = _degraded_history(3)
        out = rf_mod.fuse_regime_history(history)
        assert out["history"] == history

    def test_history_order_preserved(self):
        history = [
            _comparison("improved", baseline_regime="unstable"),
            _comparison("same",      baseline_regime="transition"),
            _comparison("degraded",  baseline_regime="stable"),
        ]
        out = rf_mod.fuse_regime_history(history)
        assert [e["regime_delta"] for e in out["history"]] == [
            "improved", "same", "degraded",
        ]


# ===========================================================================
# J. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        history = _degraded_history(5)
        a = rf_mod.fuse_regime_history(history)
        b = rf_mod.fuse_regime_history(history)
        assert a == b

    def test_byte_equal_empty(self):
        a = rf_mod.fuse_regime_history([])
        b = rf_mod.fuse_regime_history([])
        assert a == b

    def test_byte_equal_complex(self):
        history = _oscillating_history(
            ["improved", "degraded", "same", "improved", "degraded"],
            risk="medium",
        )
        a = rf_mod.fuse_regime_history(history)
        b = rf_mod.fuse_regime_history(history)
        assert a == b


# ===========================================================================
# K. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            rf_mod.fuse_regime_history("nope")

    def test_dict_input_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            rf_mod.fuse_regime_history({})

    def test_non_dict_entry_raises(self):
        with pytest.raises(ValueError, match="dict"):
            rf_mod.fuse_regime_history(["nope"])

    def test_missing_regime_delta_raises(self):
        bad = {"risk_assessment": "low", "baseline": {}, "candidate": {}}
        with pytest.raises(ValueError, match="regime_delta"):
            rf_mod.fuse_regime_history([bad])

    def test_missing_risk_assessment_raises(self):
        bad = {"regime_delta": "same", "baseline": {}, "candidate": {}}
        with pytest.raises(ValueError, match="risk_assessment"):
            rf_mod.fuse_regime_history([bad])

    def test_invalid_regime_delta_raises(self):
        bad = _comparison()
        bad["regime_delta"] = "maybe"
        with pytest.raises(ValueError, match="regime_delta"):
            rf_mod.fuse_regime_history([bad])

    def test_invalid_risk_assessment_raises(self):
        bad = _comparison()
        bad["risk_assessment"] = "extreme"
        with pytest.raises(ValueError, match="risk_assessment"):
            rf_mod.fuse_regime_history([bad])


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(rf_mod.fuse_regime_history)

    def test_risk_thresholds_locked(self):
        assert rf_mod._RISK_HIGH_SCORE == 2.3
        assert rf_mod._RISK_LOW_SCORE  == 1.3
        assert rf_mod._RISK_HIGH_COUNT == 3

    def test_oscillation_thresholds_locked(self):
        assert rf_mod._OSCILLATION_MIN_RUN == 3
        assert rf_mod._WHIPSAW_MIN_RUN     == 4

    def test_dominant_min_locked(self):
        assert rf_mod._DOMINANT_MIN == 2

    def test_assessment_vocabulary_locked(self):
        assert rf_mod._LA_PERSISTENT_DEGRADATION == "persistent_degradation"
        assert rf_mod._LA_STABILIZING            == "stabilizing"
        assert rf_mod._LA_OSCILLATING_REGIME     == "oscillating_regime"
        assert rf_mod._LA_PERSISTENT_RISK        == "persistent_risk"
        assert rf_mod._LA_BENIGN                 == "benign"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(rf_mod)

    def _code_only(self) -> str:
        import re as _re
        src = self._src()
        src = _re.sub(r'"""[\s\S]*?"""', "", src)
        src = _re.sub(r"'''[\s\S]*?'''", "", src)
        return src

    def test_no_logging(self):
        src = self._code_only()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_network(self):
        src = self._code_only()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket"):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._code_only()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src

    def test_no_llm_imports(self):
        src = self._code_only()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_persistence_imports(self):
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "load_comparison_result",
            "save_comparison_result",
        ):
            assert forbidden not in src
