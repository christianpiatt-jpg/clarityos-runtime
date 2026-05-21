"""
Tests for ELINS11 Unit 30 — operator regime actions.

Layered coverage (>= 60 tests, target ~70):
    A. evaluate_regime_change — shape + decision rules
    B. evaluate_regime_change — tag vocabulary
    C. evaluate_regime_change — content delegation
    D. generate_regime_report — shape locked
    E. generate_regime_report — headline content
    F. generate_regime_report — content delegation
    G. tag_regime_decisions — happy path
    H. tag_regime_decisions — override paths
    I. tag_regime_decisions — validation
    J. tag_regime_decisions — idempotency
    K. Determinism
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_operator_regime as opr_mod
import elins_regime_comparison as rc_mod


# ===========================================================================
# Fixtures
# ===========================================================================
def _unit_27(regime_class: str = "stable",
             volatility_variance: float = 0.0,
             breakpoints=None,
             structural_events=None) -> dict:
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


def _degraded_pair() -> tuple:
    baseline  = _unit_27("stable")
    candidate = _unit_27("unstable", volatility_variance=0.05,
                          breakpoints=[_breakpoint(), _breakpoint(), _breakpoint()])
    return baseline, candidate


def _improved_pair() -> tuple:
    baseline  = _unit_27("transition", volatility_variance=0.005,
                          breakpoints=[_breakpoint()])
    candidate = _unit_27("stable", volatility_variance=0.001,
                          breakpoints=[])
    return baseline, candidate


def _stable_pair() -> tuple:
    baseline  = _unit_27("stable", volatility_variance=0.003)
    candidate = _unit_27("stable", volatility_variance=0.004)
    return baseline, candidate


# ===========================================================================
# A. evaluate_regime_change — shape + decision rules
# ===========================================================================
class TestEvaluateShape:
    def test_response_shape(self):
        b, c = _stable_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert set(out.keys()) == {"decision", "tags", "comparison"}

    def test_decision_in_locked_vocab(self):
        b, c = _stable_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert out["decision"] in ("allow", "warn", "block")

    def test_tags_is_list(self):
        b, c = _stable_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert isinstance(out["tags"], list)

    def test_comparison_is_unit_29_output(self):
        b, c = _stable_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        expected = rc_mod.compare_regimes(b, c)
        assert out["comparison"] == expected


class TestEvaluateDecisionRules:
    def test_high_risk_blocks(self):
        b, c = _degraded_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert out["comparison"]["risk_assessment"] == "high"
        assert out["decision"] == "block"

    def test_low_risk_allows(self):
        b, c = _improved_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert out["comparison"]["risk_assessment"] == "low"
        assert out["decision"] == "allow"

    def test_medium_risk_warns(self):
        b, c = _stable_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert out["comparison"]["risk_assessment"] == "medium"
        assert out["decision"] == "warn"


# ===========================================================================
# B. evaluate_regime_change — tag vocabulary
# ===========================================================================
class TestEvaluateTags:
    def test_degraded_emits_regime_degraded_tag(self):
        b, c = _degraded_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert "regime_degraded" in out["tags"]

    def test_improved_emits_regime_improved_tag(self):
        b, c = _improved_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert "regime_improved" in out["tags"]

    def test_same_emits_regime_same_tag(self):
        b, c = _stable_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert "regime_same" in out["tags"]

    def test_high_risk_emits_risk_high_tag(self):
        b, c = _degraded_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert "risk_high" in out["tags"]

    def test_low_risk_emits_risk_low_tag(self):
        b, c = _improved_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert "risk_low" in out["tags"]

    def test_volatility_increased_tag(self):
        b = _unit_27(volatility_variance=0.005)
        c = _unit_27(volatility_variance=0.025)
        out = opr_mod.evaluate_regime_change(b, c)
        assert "volatility_increased" in out["tags"]

    def test_volatility_decreased_tag(self):
        b = _unit_27(volatility_variance=0.030)
        c = _unit_27(volatility_variance=0.005)
        out = opr_mod.evaluate_regime_change(b, c)
        assert "volatility_decreased" in out["tags"]

    def test_volatility_stable_tag_within_epsilon(self):
        b = _unit_27(volatility_variance=0.003)
        c = _unit_27(volatility_variance=0.004)
        out = opr_mod.evaluate_regime_change(b, c)
        assert "volatility_stable" in out["tags"]

    def test_breakpoints_increased_tag(self):
        b = _unit_27(breakpoints=[])
        c = _unit_27(breakpoints=[_breakpoint()])
        out = opr_mod.evaluate_regime_change(b, c)
        assert "breakpoints_increased" in out["tags"]

    def test_breakpoints_decreased_tag(self):
        b = _unit_27(breakpoints=[_breakpoint(), _breakpoint()])
        c = _unit_27(breakpoints=[])
        out = opr_mod.evaluate_regime_change(b, c)
        assert "breakpoints_decreased" in out["tags"]

    def test_breakpoints_stable_tag_when_zero_delta(self):
        b = _unit_27(breakpoints=[_breakpoint()])
        c = _unit_27(breakpoints=[_breakpoint()])
        out = opr_mod.evaluate_regime_change(b, c)
        assert "breakpoints_stable" in out["tags"]

    def test_tags_alpha_sorted(self):
        b, c = _degraded_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert out["tags"] == sorted(out["tags"])

    def test_tag_count_locked_at_four(self):
        # Regime + risk + volatility + breakpoint = 4 tags.
        b, c = _stable_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert len(out["tags"]) == 4


# ===========================================================================
# C. evaluate_regime_change — content delegation
# ===========================================================================
class TestEvaluateDelegation:
    def test_decision_matches_risk_map(self):
        cases = [
            (_degraded_pair(), "block"),
            (_improved_pair(), "allow"),
            (_stable_pair(),   "warn"),
        ]
        for (b, c), expected in cases:
            out = opr_mod.evaluate_regime_change(b, c)
            assert out["decision"] == expected

    def test_comparison_matches_unit_29(self):
        b, c = _degraded_pair()
        out = opr_mod.evaluate_regime_change(b, c)
        assert out["comparison"] == rc_mod.compare_regimes(b, c)


# ===========================================================================
# D. generate_regime_report — shape locked
# ===========================================================================
class TestReportShape:
    def test_top_level_keys(self):
        b, c = _degraded_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert set(out.keys()) == {
            "headline", "decision", "risk_assessment",
            "regime_delta", "volatility_delta",
            "breakpoint_delta", "event_summary",
            "baseline", "candidate", "comparison",
        }

    def test_decision_in_locked_vocab(self):
        b, c = _stable_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert out["decision"] in ("allow", "warn", "block")

    def test_risk_assessment_in_locked_vocab(self):
        b, c = _stable_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert out["risk_assessment"] in ("low", "medium", "high")

    def test_regime_delta_in_locked_vocab(self):
        b, c = _stable_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert out["regime_delta"] in ("same", "improved", "degraded")


# ===========================================================================
# E. generate_regime_report — headline content
# ===========================================================================
class TestReportHeadline:
    def test_block_headline_prefix(self):
        b, c = _degraded_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert out["headline"].startswith("BLOCK:")

    def test_allow_headline_prefix(self):
        b, c = _improved_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert out["headline"].startswith("ALLOW:")

    def test_warn_headline_prefix(self):
        b, c = _stable_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert out["headline"].startswith("WARN:")

    def test_headline_mentions_regime_delta(self):
        b, c = _degraded_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert "degraded" in out["headline"].lower()

    def test_headline_mentions_candidate_regime(self):
        b, c = _degraded_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert "UNSTABLE" in out["headline"]

    def test_headline_mentions_volatility(self):
        b, c = _degraded_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert "volatility" in out["headline"].lower()

    def test_headline_mentions_breakpoints(self):
        b, c = _degraded_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert "breakpoints" in out["headline"].lower()

    def test_headline_non_empty(self):
        b, c = _stable_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert out["headline"].strip() != ""


# ===========================================================================
# F. generate_regime_report — content delegation
# ===========================================================================
class TestReportDelegation:
    def test_comparison_matches_unit_29(self):
        b, c = _degraded_pair()
        out = opr_mod.generate_regime_report(b, c)
        assert out["comparison"] == rc_mod.compare_regimes(b, c)

    def test_regime_delta_matches_unit_29(self):
        b, c = _improved_pair()
        out = opr_mod.generate_regime_report(b, c)
        comparison = rc_mod.compare_regimes(b, c)
        assert out["regime_delta"] == comparison["regime_delta"]

    def test_volatility_delta_matches_unit_29(self):
        b, c = _degraded_pair()
        out = opr_mod.generate_regime_report(b, c)
        comparison = rc_mod.compare_regimes(b, c)
        assert out["volatility_delta"] == comparison["volatility_delta"]

    def test_breakpoint_delta_matches_unit_29(self):
        b, c = _improved_pair()
        out = opr_mod.generate_regime_report(b, c)
        comparison = rc_mod.compare_regimes(b, c)
        assert out["breakpoint_delta"] == comparison["breakpoint_delta"]

    def test_event_summary_matches_unit_29(self):
        b = _unit_27(structural_events=["breakpoint_detected"])
        c = _unit_27(structural_events=["volatility_spike"])
        out = opr_mod.generate_regime_report(b, c)
        comparison = rc_mod.compare_regimes(b, c)
        assert out["event_summary"] == comparison["event_summary"]


# ===========================================================================
# G. tag_regime_decisions — happy path
# ===========================================================================
class TestTagRegimeDecisionsHappy:
    def test_response_shape(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(comparison, {})
        assert set(out.keys()) == {"applied", "tags", "overrides"}

    def test_applied_always_true(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(comparison, {})
        assert out["applied"] is True

    def test_empty_decisions_uses_base_tags(self):
        b, c = _degraded_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(comparison, {})
        # Base 4 tags should be present (no overrides).
        assert "regime_degraded" in out["tags"]
        assert "risk_high" in out["tags"]
        assert out["overrides"] == {}

    def test_tags_alpha_sorted(self):
        b, c = _degraded_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(comparison, {})
        assert out["tags"] == sorted(out["tags"])

    def test_tags_deduped(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(comparison, {})
        assert len(out["tags"]) == len(set(out["tags"]))


# ===========================================================================
# H. tag_regime_decisions — override paths
# ===========================================================================
class TestTagRegimeDecisionsOverrides:
    def test_override_decision_adds_override_tag(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison, {"override_decision": "block"},
        )
        assert "override_decision" in out["tags"]

    def test_override_decision_echoed_in_overrides(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison, {"override_decision": "block"},
        )
        assert out["overrides"]["override_decision"] == "block"

    def test_override_decision_adds_target_risk_tag(self):
        # When the underlying comparison is medium-risk and the
        # operator overrides to block, the high-risk tag should also
        # appear in the tag set.
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison, {"override_decision": "block"},
        )
        assert "risk_high" in out["tags"]

    def test_escalate_true_adds_escalation_tag(self):
        b, c = _degraded_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison, {"escalate": True},
        )
        assert "override_escalated" in out["tags"]

    def test_escalate_false_no_escalation_tag(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison, {"escalate": False},
        )
        assert "override_escalated" not in out["tags"]

    def test_audit_note_recorded_in_overrides(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison, {"audit_note": "Manual review by ops."},
        )
        assert out["overrides"]["audit_note"] == "Manual review by ops."

    def test_audit_note_does_not_add_tag(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison, {"audit_note": "note"},
        )
        # No audit-specific tag in the locked vocabulary.
        tag_set = set(out["tags"])
        assert "audit_note" not in tag_set

    def test_combined_overrides(self):
        b, c = _degraded_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison,
            {
                "override_decision": "warn",
                "escalate":          True,
                "audit_note":        "ops escalation",
            },
        )
        assert "override_decision" in out["tags"]
        assert "override_escalated" in out["tags"]
        assert "risk_medium" in out["tags"]
        assert out["overrides"]["override_decision"] == "warn"
        assert out["overrides"]["escalate"] is True
        assert out["overrides"]["audit_note"] == "ops escalation"


# ===========================================================================
# I. tag_regime_decisions — validation
# ===========================================================================
class TestTagRegimeDecisionsValidation:
    def test_non_dict_comparison_raises(self):
        with pytest.raises(ValueError, match="dict"):
            opr_mod.tag_regime_decisions("nope", {})

    def test_missing_required_key_raises(self):
        bad = {"regime_delta": "same"}
        with pytest.raises(ValueError, match="Unit 29 key"):
            opr_mod.tag_regime_decisions(bad, {})

    def test_non_dict_decisions_raises(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        with pytest.raises(ValueError, match="decisions"):
            opr_mod.tag_regime_decisions(comparison, "nope")

    def test_invalid_override_decision_raises(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        with pytest.raises(ValueError, match="override_decision"):
            opr_mod.tag_regime_decisions(
                comparison, {"override_decision": "maybe"},
            )

    def test_non_bool_escalate_raises(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        with pytest.raises(ValueError, match="escalate"):
            opr_mod.tag_regime_decisions(
                comparison, {"escalate": "yes"},
            )

    def test_non_string_audit_note_raises(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        with pytest.raises(ValueError, match="audit_note"):
            opr_mod.tag_regime_decisions(
                comparison, {"audit_note": 42},
            )


# ===========================================================================
# J. tag_regime_decisions — idempotency
# ===========================================================================
class TestTagRegimeDecisionsIdempotency:
    def test_repeat_call_byte_equal(self):
        b, c = _degraded_pair()
        comparison = rc_mod.compare_regimes(b, c)
        a = opr_mod.tag_regime_decisions(
            comparison, {"override_decision": "warn"},
        )
        d = opr_mod.tag_regime_decisions(
            comparison, {"override_decision": "warn"},
        )
        assert a == d

    def test_no_duplicate_tags_with_overrides(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        out = opr_mod.tag_regime_decisions(
            comparison,
            {"override_decision": "warn", "escalate": True},
        )
        assert len(out["tags"]) == len(set(out["tags"]))


# ===========================================================================
# K. Determinism
# ===========================================================================
class TestDeterminism:
    def test_evaluate_byte_equal(self):
        b, c = _degraded_pair()
        a = opr_mod.evaluate_regime_change(b, c)
        d = opr_mod.evaluate_regime_change(b, c)
        assert a == d

    def test_report_byte_equal(self):
        b, c = _improved_pair()
        a = opr_mod.generate_regime_report(b, c)
        d = opr_mod.generate_regime_report(b, c)
        assert a == d

    def test_tag_byte_equal_empty_decisions(self):
        b, c = _stable_pair()
        comparison = rc_mod.compare_regimes(b, c)
        a = opr_mod.tag_regime_decisions(comparison, {})
        d = opr_mod.tag_regime_decisions(comparison, {})
        assert a == d


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            opr_mod.evaluate_regime_change,
            opr_mod.generate_regime_report,
            opr_mod.tag_regime_decisions,
        ):
            assert callable(fn)

    def test_risk_decision_map_complete(self):
        for r in ("high", "medium", "low"):
            assert r in opr_mod._RISK_DECISION_MAP

    def test_tag_vocabulary_locked(self):
        assert opr_mod.TAG_REGIME_SAME           == "regime_same"
        assert opr_mod.TAG_REGIME_IMPROVED       == "regime_improved"
        assert opr_mod.TAG_REGIME_DEGRADED       == "regime_degraded"
        assert opr_mod.TAG_RISK_LOW              == "risk_low"
        assert opr_mod.TAG_RISK_MEDIUM           == "risk_medium"
        assert opr_mod.TAG_RISK_HIGH             == "risk_high"
        assert opr_mod.TAG_VOLATILITY_INCREASED  == "volatility_increased"
        assert opr_mod.TAG_VOLATILITY_DECREASED  == "volatility_decreased"
        assert opr_mod.TAG_VOLATILITY_STABLE     == "volatility_stable"
        assert opr_mod.TAG_BREAKPOINTS_INCREASED == "breakpoints_increased"
        assert opr_mod.TAG_BREAKPOINTS_DECREASED == "breakpoints_decreased"
        assert opr_mod.TAG_BREAKPOINTS_STABLE    == "breakpoints_stable"

    def test_volatility_tag_epsilon_locked(self):
        assert opr_mod._VOLATILITY_TAG_EPSILON == 0.005


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(opr_mod)

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
            "save_comparison_result", "set_tags", "get_tags",
        ):
            assert forbidden not in src

    def test_composes_unit_29(self):
        src = self._code_only()
        assert "compare_regimes" in src
