"""
Tests for ELINS11 Unit 29 — regime comparison engine.

Layered coverage (>= 60 tests, target ~70):
    A. Top-level shape / locked keys
    B. Regime delta — same / improved / degraded
    C. Volatility delta (absolute + relative)
    D. Breakpoint delta math
    E. Event summary (new / resolved / persistent)
    F. Risk assessment thresholds
    G. Summary string content
    H. Empty / edge cases
    I. Baseline / candidate pass-through
    J. Determinism
    K. Validation
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_regime_comparison as rc_mod


# ===========================================================================
# Fixtures — synthetic Unit 27 outputs
# ===========================================================================
def _unit_27(regime_class: str = "stable",
             volatility_variance: float = 0.0,
             breakpoints=None,
             structural_events=None) -> dict:
    """Build one Unit 27 output dict with the locked contract keys."""
    return {
        "timeline":             [],
        "regime_class":         regime_class,
        "volatility_variance":  volatility_variance,
        "breakpoints":          breakpoints or [],
        "structural_events":    structural_events or [],
        "summary":              "",
    }


def _breakpoint(timestamp: str = "t01",
                metric: str = "health",
                delta: float = -0.5) -> dict:
    return {"timestamp": timestamp, "metric": metric, "delta": delta}


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert set(out.keys()) == {
            "baseline", "candidate", "regime_delta",
            "volatility_delta", "breakpoint_delta",
            "event_summary", "risk_assessment", "summary",
        }

    def test_volatility_delta_keys_locked(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert set(out["volatility_delta"].keys()) == {
            "absolute", "relative",
        }

    def test_breakpoint_delta_keys_locked(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert set(out["breakpoint_delta"].keys()) == {
            "baseline_count", "candidate_count", "delta",
        }

    def test_event_summary_keys_locked(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert set(out["event_summary"].keys()) == {
            "new_events", "resolved_events", "persistent_events",
        }

    def test_summary_is_string(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert isinstance(out["summary"], str)


# ===========================================================================
# B. Regime delta — same / improved / degraded
# ===========================================================================
class TestRegimeDelta:
    def test_same_regime_same_delta(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable"), _unit_27("stable"),
        )
        assert out["regime_delta"] == "same"

    def test_stable_to_transition_degraded(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable"), _unit_27("transition"),
        )
        assert out["regime_delta"] == "degraded"

    def test_stable_to_unstable_degraded(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable"), _unit_27("unstable"),
        )
        assert out["regime_delta"] == "degraded"

    def test_transition_to_unstable_degraded(self):
        out = rc_mod.compare_regimes(
            _unit_27("transition"), _unit_27("unstable"),
        )
        assert out["regime_delta"] == "degraded"

    def test_unstable_to_transition_improved(self):
        out = rc_mod.compare_regimes(
            _unit_27("unstable"), _unit_27("transition"),
        )
        assert out["regime_delta"] == "improved"

    def test_transition_to_stable_improved(self):
        out = rc_mod.compare_regimes(
            _unit_27("transition"), _unit_27("stable"),
        )
        assert out["regime_delta"] == "improved"

    def test_unstable_to_stable_improved(self):
        out = rc_mod.compare_regimes(
            _unit_27("unstable"), _unit_27("stable"),
        )
        assert out["regime_delta"] == "improved"

    def test_transition_to_transition_same(self):
        out = rc_mod.compare_regimes(
            _unit_27("transition"), _unit_27("transition"),
        )
        assert out["regime_delta"] == "same"

    def test_unstable_to_unstable_same(self):
        out = rc_mod.compare_regimes(
            _unit_27("unstable"), _unit_27("unstable"),
        )
        assert out["regime_delta"] == "same"


# ===========================================================================
# C. Volatility delta (absolute + relative)
# ===========================================================================
class TestVolatilityDelta:
    def test_zero_baseline_and_candidate_zero_absolute(self):
        out = rc_mod.compare_regimes(
            _unit_27(volatility_variance=0.0),
            _unit_27(volatility_variance=0.0),
        )
        assert out["volatility_delta"]["absolute"] == pytest.approx(0.0)

    def test_positive_absolute_delta(self):
        out = rc_mod.compare_regimes(
            _unit_27(volatility_variance=0.010),
            _unit_27(volatility_variance=0.030),
        )
        assert out["volatility_delta"]["absolute"] == pytest.approx(0.020)

    def test_negative_absolute_delta(self):
        out = rc_mod.compare_regimes(
            _unit_27(volatility_variance=0.030),
            _unit_27(volatility_variance=0.010),
        )
        assert out["volatility_delta"]["absolute"] == pytest.approx(-0.020)

    def test_relative_delta_correct(self):
        out = rc_mod.compare_regimes(
            _unit_27(volatility_variance=0.010),
            _unit_27(volatility_variance=0.020),
        )
        # rel = (0.020 - 0.010) / 0.010 = 1.0
        assert out["volatility_delta"]["relative"] == pytest.approx(1.0)

    def test_relative_delta_with_zero_baseline_uses_epsilon(self):
        out = rc_mod.compare_regimes(
            _unit_27(volatility_variance=0.0),
            _unit_27(volatility_variance=0.005),
        )
        # baseline=0 → relative is large but finite (not Inf / NaN).
        rel = out["volatility_delta"]["relative"]
        assert rel > 1000  # very large, finite

    def test_volatility_delta_sign_preserved(self):
        out = rc_mod.compare_regimes(
            _unit_27(volatility_variance=0.05),
            _unit_27(volatility_variance=0.02),
        )
        assert out["volatility_delta"]["absolute"] < 0


# ===========================================================================
# D. Breakpoint delta math
# ===========================================================================
class TestBreakpointDelta:
    def test_zero_breakpoints_both_sides(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert out["breakpoint_delta"] == {
            "baseline_count": 0,
            "candidate_count": 0,
            "delta": 0,
        }

    def test_more_breakpoints_in_candidate(self):
        out = rc_mod.compare_regimes(
            _unit_27(breakpoints=[]),
            _unit_27(breakpoints=[_breakpoint(), _breakpoint()]),
        )
        assert out["breakpoint_delta"]["delta"] == 2

    def test_fewer_breakpoints_in_candidate(self):
        out = rc_mod.compare_regimes(
            _unit_27(breakpoints=[_breakpoint(), _breakpoint(), _breakpoint()]),
            _unit_27(breakpoints=[_breakpoint()]),
        )
        assert out["breakpoint_delta"]["delta"] == -2

    def test_counts_accurate(self):
        out = rc_mod.compare_regimes(
            _unit_27(breakpoints=[_breakpoint()] * 3),
            _unit_27(breakpoints=[_breakpoint()] * 5),
        )
        assert out["breakpoint_delta"]["baseline_count"] == 3
        assert out["breakpoint_delta"]["candidate_count"] == 5
        assert out["breakpoint_delta"]["delta"] == 2


# ===========================================================================
# E. Event summary (new / resolved / persistent)
# ===========================================================================
class TestEventSummary:
    def test_no_events_empty_sections(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert out["event_summary"] == {
            "new_events": [],
            "resolved_events": [],
            "persistent_events": [],
        }

    def test_new_events_detected(self):
        out = rc_mod.compare_regimes(
            _unit_27(structural_events=[]),
            _unit_27(structural_events=["breakpoint_detected"]),
        )
        assert out["event_summary"]["new_events"] == ["breakpoint_detected"]

    def test_resolved_events_detected(self):
        out = rc_mod.compare_regimes(
            _unit_27(structural_events=["volatility_spike"]),
            _unit_27(structural_events=[]),
        )
        assert out["event_summary"]["resolved_events"] == ["volatility_spike"]

    def test_persistent_events_detected(self):
        out = rc_mod.compare_regimes(
            _unit_27(structural_events=["volatility_spike", "breakpoint_detected"]),
            _unit_27(structural_events=["volatility_spike"]),
        )
        assert out["event_summary"]["persistent_events"] == ["volatility_spike"]
        assert out["event_summary"]["resolved_events"] == ["breakpoint_detected"]

    def test_event_lists_alpha_sorted(self):
        out = rc_mod.compare_regimes(
            _unit_27(structural_events=["zzz", "aaa"]),
            _unit_27(structural_events=["aaa", "mmm"]),
        )
        assert out["event_summary"]["persistent_events"] == ["aaa"]
        assert out["event_summary"]["new_events"] == ["mmm"]
        assert out["event_summary"]["resolved_events"] == ["zzz"]

    def test_full_disjoint_events(self):
        out = rc_mod.compare_regimes(
            _unit_27(structural_events=["a", "b"]),
            _unit_27(structural_events=["c", "d"]),
        )
        assert set(out["event_summary"]["new_events"]) == {"c", "d"}
        assert set(out["event_summary"]["resolved_events"]) == {"a", "b"}
        assert out["event_summary"]["persistent_events"] == []


# ===========================================================================
# F. Risk assessment thresholds
# ===========================================================================
class TestRiskAssessment:
    def test_degraded_regime_is_high(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable"), _unit_27("transition"),
        )
        assert out["risk_assessment"] == "high"

    def test_high_volatility_is_high(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable", volatility_variance=0.0),
            _unit_27("stable", volatility_variance=0.025),
        )
        assert out["risk_assessment"] == "high"

    def test_two_more_breakpoints_is_high(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable", breakpoints=[]),
            _unit_27("stable", breakpoints=[_breakpoint(), _breakpoint()]),
        )
        assert out["risk_assessment"] == "high"

    def test_improved_with_low_vol_and_fewer_bp_is_low(self):
        out = rc_mod.compare_regimes(
            _unit_27("transition", volatility_variance=0.005,
                     breakpoints=[_breakpoint()]),
            _unit_27("stable",     volatility_variance=0.001,
                     breakpoints=[]),
        )
        assert out["risk_assessment"] == "low"

    def test_same_regime_minor_changes_is_medium(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable", volatility_variance=0.005),
            _unit_27("stable", volatility_variance=0.010),
        )
        assert out["risk_assessment"] == "medium"

    def test_improved_with_high_vol_still_high(self):
        # Improved regime but volatility jumped — high vol takes priority.
        out = rc_mod.compare_regimes(
            _unit_27("unstable", volatility_variance=0.001),
            _unit_27("stable",   volatility_variance=0.030),
        )
        assert out["risk_assessment"] == "high"

    def test_low_threshold_includes_exactly_0_005(self):
        # vol_abs == 0.005, improved regime, bp_delta = 0 → low.
        out = rc_mod.compare_regimes(
            _unit_27("transition", volatility_variance=0.005),
            _unit_27("stable",     volatility_variance=0.010),
        )
        # vol_abs = 0.005 — exactly at the low threshold.
        assert out["risk_assessment"] == "low"

    def test_high_threshold_includes_exactly_0_02(self):
        # vol_abs == 0.02, same regime, bp_delta = 0 → high.
        out = rc_mod.compare_regimes(
            _unit_27("stable", volatility_variance=0.0),
            _unit_27("stable", volatility_variance=0.020),
        )
        assert out["risk_assessment"] == "high"

    def test_improved_with_large_volatility_drop_is_medium(self):
        # v53 lock: a big NEGATIVE volatility delta on an improved
        # regime no longer auto-qualifies for low risk — the
        # magnitude must still sit within ±0.005 of zero.
        out = rc_mod.compare_regimes(
            _unit_27("transition", volatility_variance=0.030),
            _unit_27("stable",     volatility_variance=0.010),
        )
        # abs(-0.020) = 0.020 > 0.005 → medium, not low.
        assert out["risk_assessment"] == "medium"

    def test_improved_with_small_volatility_drop_still_low(self):
        # Magnitude within the epsilon — improved + low-vol-change +
        # fewer breakpoints → still low.
        out = rc_mod.compare_regimes(
            _unit_27("transition", volatility_variance=0.005),
            _unit_27("stable",     volatility_variance=0.002),
        )
        # abs(-0.003) = 0.003 <= 0.005 → low.
        assert out["risk_assessment"] == "low"


# ===========================================================================
# G. Summary string content
# ===========================================================================
class TestSummary:
    def test_summary_mentions_regime_delta(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable"), _unit_27("unstable"),
        )
        assert "degraded" in out["summary"]
        assert "stable" in out["summary"]
        assert "unstable" in out["summary"]

    def test_summary_mentions_volatility(self):
        out = rc_mod.compare_regimes(
            _unit_27(volatility_variance=0.010),
            _unit_27(volatility_variance=0.030),
        )
        assert "volatility" in out["summary"]
        assert "+0.020" in out["summary"]

    def test_summary_mentions_breakpoints(self):
        out = rc_mod.compare_regimes(
            _unit_27(breakpoints=[_breakpoint(), _breakpoint()]),
            _unit_27(breakpoints=[]),
        )
        assert "breakpoints" in out["summary"]
        assert "-2" in out["summary"]

    def test_summary_format_arrow(self):
        out = rc_mod.compare_regimes(
            _unit_27("stable"), _unit_27("transition"),
        )
        assert "stable → transition" in out["summary"]

    def test_summary_non_empty(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert out["summary"].strip() != ""


# ===========================================================================
# H. Empty / edge cases
# ===========================================================================
class TestEdgeCases:
    def test_identical_payloads_no_change(self):
        payload = _unit_27(
            "transition", volatility_variance=0.012,
            breakpoints=[_breakpoint()],
            structural_events=["breakpoint_detected"],
        )
        out = rc_mod.compare_regimes(payload, payload)
        assert out["regime_delta"] == "same"
        assert out["volatility_delta"]["absolute"] == pytest.approx(0.0)
        assert out["breakpoint_delta"]["delta"] == 0

    def test_completely_empty_unit_27_payloads(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert out["regime_delta"] == "same"
        assert out["risk_assessment"] == "medium"

    def test_no_breakpoints_either_side(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert out["breakpoint_delta"]["delta"] == 0

    def test_no_events_either_side(self):
        out = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert all(
            len(v) == 0 for v in out["event_summary"].values()
        )

    def test_baseline_zero_volatility_safe(self):
        # Should not raise on baseline=0 (relative uses epsilon floor).
        out = rc_mod.compare_regimes(
            _unit_27(volatility_variance=0.0),
            _unit_27(volatility_variance=0.5),
        )
        assert isinstance(out["volatility_delta"]["relative"], float)


# ===========================================================================
# I. Baseline / candidate pass-through
# ===========================================================================
class TestPassthrough:
    def test_baseline_echoed(self):
        baseline = _unit_27("stable", volatility_variance=0.003)
        candidate = _unit_27("transition", volatility_variance=0.015)
        out = rc_mod.compare_regimes(baseline, candidate)
        assert out["baseline"] is baseline or out["baseline"] == baseline

    def test_candidate_echoed(self):
        baseline = _unit_27("stable")
        candidate = _unit_27("transition")
        out = rc_mod.compare_regimes(baseline, candidate)
        assert out["candidate"] == candidate


# ===========================================================================
# J. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        b = _unit_27("stable", volatility_variance=0.005,
                     breakpoints=[_breakpoint()],
                     structural_events=["breakpoint_detected"])
        c = _unit_27("transition", volatility_variance=0.015,
                     breakpoints=[_breakpoint(), _breakpoint()],
                     structural_events=["breakpoint_detected", "volatility_spike"])
        a1 = rc_mod.compare_regimes(b, c)
        a2 = rc_mod.compare_regimes(b, c)
        assert a1 == a2

    def test_byte_equal_empty(self):
        a = rc_mod.compare_regimes(_unit_27(), _unit_27())
        b = rc_mod.compare_regimes(_unit_27(), _unit_27())
        assert a == b


# ===========================================================================
# K. Validation
# ===========================================================================
class TestValidation:
    def test_non_dict_baseline_raises(self):
        with pytest.raises(ValueError, match="baseline"):
            rc_mod.compare_regimes("nope", _unit_27())

    def test_non_dict_candidate_raises(self):
        with pytest.raises(ValueError, match="candidate"):
            rc_mod.compare_regimes(_unit_27(), "nope")

    def test_missing_regime_class_raises(self):
        bad = {"volatility_variance": 0.0, "breakpoints": [], "structural_events": []}
        with pytest.raises(ValueError, match="regime_class"):
            rc_mod.compare_regimes(bad, _unit_27())

    def test_missing_volatility_variance_raises(self):
        bad = {"regime_class": "stable", "breakpoints": [], "structural_events": []}
        with pytest.raises(ValueError, match="volatility_variance"):
            rc_mod.compare_regimes(_unit_27(), bad)

    def test_missing_breakpoints_raises(self):
        bad = {"regime_class": "stable", "volatility_variance": 0.0,
               "structural_events": []}
        with pytest.raises(ValueError, match="breakpoints"):
            rc_mod.compare_regimes(_unit_27(), bad)

    def test_invalid_regime_class_raises(self):
        bad = _unit_27()
        bad["regime_class"] = "maybe"
        with pytest.raises(ValueError, match="regime_class"):
            rc_mod.compare_regimes(bad, _unit_27())

    def test_non_list_breakpoints_raises(self):
        bad = _unit_27()
        bad["breakpoints"] = "nope"
        with pytest.raises(ValueError, match="breakpoints"):
            rc_mod.compare_regimes(bad, _unit_27())

    def test_non_list_structural_events_raises(self):
        bad = _unit_27()
        bad["structural_events"] = "nope"
        with pytest.raises(ValueError, match="structural_events"):
            rc_mod.compare_regimes(bad, _unit_27())


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(rc_mod.compare_regimes)

    def test_regime_order_locked(self):
        assert rc_mod._REGIME_ORDER == {
            "stable": 0, "transition": 1, "unstable": 2,
        }

    def test_risk_thresholds_locked(self):
        assert rc_mod._HIGH_VOLATILITY_ABS == 0.02
        assert rc_mod._LOW_VOLATILITY_ABS == 0.005
        assert rc_mod._HIGH_BREAKPOINT_DELTA == 2

    def test_delta_vocabulary_locked(self):
        assert rc_mod._DELTA_SAME     == "same"
        assert rc_mod._DELTA_IMPROVED == "improved"
        assert rc_mod._DELTA_DEGRADED == "degraded"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(rc_mod)

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
