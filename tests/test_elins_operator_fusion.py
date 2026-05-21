"""
Tests for ELINS12 Unit 32 — operator fusion actions.

Layered coverage (>= 60 tests, target ~75):
    A. evaluate_long_arc — shape + decision rules
    B. evaluate_long_arc — tag vocabulary
    C. evaluate_long_arc — content delegation
    D. generate_long_arc_report — shape locked
    E. generate_long_arc_report — headline content
    F. generate_long_arc_report — content delegation
    G. tag_long_arc_decisions — happy path
    H. tag_long_arc_decisions — override paths
    I. tag_long_arc_decisions — validation
    J. tag_long_arc_decisions — idempotency
    K. Determinism
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_operator_fusion as opf_mod
import elins_regime_fusion as rf_mod


# ===========================================================================
# Fixtures
# ===========================================================================
def _comparison(regime_delta: str = "same",
                risk: str = "low",
                baseline_regime: str = "stable",
                candidate_regime: str = "stable") -> dict:
    return {
        "regime_delta":    regime_delta,
        "risk_assessment": risk,
        "baseline":        {"regime_class": baseline_regime},
        "candidate":       {"regime_class": candidate_regime},
    }


def _persistent_degradation_history() -> list:
    return [
        _comparison("degraded", "high", "stable", "transition"),
        _comparison("degraded", "high", "transition", "unstable"),
        _comparison("degraded", "medium", "unstable", "unstable"),
        _comparison("degraded", "high", "unstable", "unstable"),
    ]


def _stabilizing_history() -> list:
    return [
        _comparison("improved", "low", "unstable", "transition"),
        _comparison("improved", "low", "transition", "stable"),
        _comparison("improved", "low", "stable", "stable"),
    ]


def _whipsaw_history(risk: str = "high") -> list:
    return [
        _comparison("improved", risk),
        _comparison("degraded", risk),
        _comparison("improved", risk),
        _comparison("degraded", risk),
    ]


def _benign_history() -> list:
    return [
        _comparison("same", "low"),
        _comparison("same", "low"),
    ]


def _persistent_risk_history() -> list:
    return [
        _comparison("same", "high"),
        _comparison("same", "high"),
        _comparison("same", "high"),
        _comparison("same", "high"),
    ]


# ===========================================================================
# A. evaluate_long_arc — shape + decision rules
# ===========================================================================
class TestEvaluateShape:
    def test_response_shape(self):
        out = opf_mod.evaluate_long_arc(_stabilizing_history())
        assert set(out.keys()) == {"decision", "tags", "fusion"}

    def test_decision_in_locked_vocab(self):
        out = opf_mod.evaluate_long_arc(_stabilizing_history())
        assert out["decision"] in ("allow", "warn", "block")

    def test_tags_is_list(self):
        out = opf_mod.evaluate_long_arc(_stabilizing_history())
        assert isinstance(out["tags"], list)

    def test_fusion_matches_unit_31(self):
        history = _stabilizing_history()
        out = opf_mod.evaluate_long_arc(history)
        expected = rf_mod.fuse_regime_history(history)
        assert out["fusion"] == expected


class TestEvaluateDecisionRules:
    def test_persistent_degradation_blocks(self):
        out = opf_mod.evaluate_long_arc(_persistent_degradation_history())
        assert out["decision"] == "block"

    def test_persistent_risk_blocks(self):
        out = opf_mod.evaluate_long_arc(_persistent_risk_history())
        assert out["decision"] == "block"

    def test_high_risk_plus_whipsaw_blocks(self):
        history = _whipsaw_history(risk="high")
        out = opf_mod.evaluate_long_arc(history)
        assert out["decision"] == "block"

    def test_oscillating_regime_warns(self):
        # whipsaw without high risk → warns via the oscillating-regime
        # path (low-risk whipsaw → oscillating_regime → warn).
        history = _whipsaw_history(risk="low")
        out = opf_mod.evaluate_long_arc(history)
        # Per spec: whipsaw → oscillating_regime → warn (unless high
        # risk also fires, which is a block).
        assert out["decision"] == "warn"

    def test_medium_risk_warns(self):
        history = [
            _comparison("same", "medium"),
            _comparison("same", "medium"),
            _comparison("same", "medium"),
        ]
        out = opf_mod.evaluate_long_arc(history)
        assert out["decision"] == "warn"

    def test_stabilizing_allows(self):
        out = opf_mod.evaluate_long_arc(_stabilizing_history())
        assert out["decision"] == "allow"

    def test_benign_allows(self):
        out = opf_mod.evaluate_long_arc(_benign_history())
        assert out["decision"] == "allow"


# ===========================================================================
# B. evaluate_long_arc — tag vocabulary
# ===========================================================================
class TestEvaluateTags:
    def test_persistent_degradation_emits_la_tag(self):
        out = opf_mod.evaluate_long_arc(_persistent_degradation_history())
        assert "long_arc_persistent_degradation" in out["tags"]

    def test_stabilizing_emits_la_tag(self):
        out = opf_mod.evaluate_long_arc(_stabilizing_history())
        assert "long_arc_stabilizing" in out["tags"]

    def test_benign_emits_la_benign_tag(self):
        out = opf_mod.evaluate_long_arc(_benign_history())
        assert "long_arc_benign" in out["tags"]

    def test_trajectory_degrading_tag(self):
        out = opf_mod.evaluate_long_arc(_persistent_degradation_history())
        assert "trajectory_degrading" in out["tags"]

    def test_trajectory_improving_tag(self):
        out = opf_mod.evaluate_long_arc(_stabilizing_history())
        assert "trajectory_improving" in out["tags"]

    def test_trajectory_flat_tag(self):
        out = opf_mod.evaluate_long_arc(_benign_history())
        assert "trajectory_flat" in out["tags"]

    def test_trajectory_oscillating_tag(self):
        out = opf_mod.evaluate_long_arc(_whipsaw_history(risk="medium"))
        assert "trajectory_oscillating" in out["tags"]

    def test_risk_high_tag(self):
        out = opf_mod.evaluate_long_arc(_persistent_risk_history())
        assert "long_arc_risk_high" in out["tags"]

    def test_risk_low_tag(self):
        out = opf_mod.evaluate_long_arc(_stabilizing_history())
        assert "long_arc_risk_low" in out["tags"]

    def test_whipsaw_tag(self):
        out = opf_mod.evaluate_long_arc(_whipsaw_history(risk="medium"))
        assert "long_arc_whipsaw" in out["tags"]

    def test_oscillating_tag_present_when_oscillating(self):
        out = opf_mod.evaluate_long_arc(_whipsaw_history(risk="medium"))
        assert "long_arc_oscillating" in out["tags"]

    def test_no_oscillating_tag_on_clean_run(self):
        out = opf_mod.evaluate_long_arc(_stabilizing_history())
        assert "long_arc_oscillating" not in out["tags"]
        assert "long_arc_whipsaw" not in out["tags"]

    def test_tags_alpha_sorted(self):
        out = opf_mod.evaluate_long_arc(_persistent_degradation_history())
        assert out["tags"] == sorted(out["tags"])

    def test_tags_deduped(self):
        out = opf_mod.evaluate_long_arc(_whipsaw_history(risk="high"))
        assert len(out["tags"]) == len(set(out["tags"]))


# ===========================================================================
# C. evaluate_long_arc — content delegation
# ===========================================================================
class TestEvaluateDelegation:
    def test_fusion_matches_unit_31_output_exactly(self):
        history = _persistent_degradation_history()
        out = opf_mod.evaluate_long_arc(history)
        expected = rf_mod.fuse_regime_history(history)
        assert out["fusion"] == expected

    def test_decision_rule_priority(self):
        # persistent_degradation in assessment takes precedence over
        # oscillating_regime in the decision rules.
        history = _persistent_degradation_history()
        out = opf_mod.evaluate_long_arc(history)
        assert out["fusion"]["long_arc_assessment"] == \
               "persistent_degradation"
        assert out["decision"] == "block"


# ===========================================================================
# D. generate_long_arc_report — shape locked
# ===========================================================================
class TestReportShape:
    def test_top_level_keys(self):
        out = opf_mod.generate_long_arc_report(_stabilizing_history())
        assert set(out.keys()) == {
            "headline", "decision", "long_arc_assessment",
            "risk_level", "trajectory", "oscillation",
            "cumulative_risk", "fusion", "history",
        }

    def test_decision_in_locked_vocab(self):
        out = opf_mod.generate_long_arc_report(_stabilizing_history())
        assert out["decision"] in ("allow", "warn", "block")

    def test_risk_level_in_locked_vocab(self):
        out = opf_mod.generate_long_arc_report(_stabilizing_history())
        assert out["risk_level"] in ("low", "medium", "high")

    def test_long_arc_assessment_in_locked_vocab(self):
        out = opf_mod.generate_long_arc_report(_stabilizing_history())
        assert out["long_arc_assessment"] in (
            "stabilizing", "persistent_degradation",
            "persistent_risk", "oscillating_regime", "benign",
        )


# ===========================================================================
# E. generate_long_arc_report — headline content
# ===========================================================================
class TestReportHeadline:
    def test_block_headline_prefix(self):
        out = opf_mod.generate_long_arc_report(
            _persistent_degradation_history(),
        )
        assert out["headline"].startswith("BLOCK:")

    def test_warn_headline_prefix(self):
        history = [_comparison("same", "medium") for _ in range(3)]
        out = opf_mod.generate_long_arc_report(history)
        assert out["headline"].startswith("WARN:")

    def test_allow_headline_prefix(self):
        out = opf_mod.generate_long_arc_report(_stabilizing_history())
        assert out["headline"].startswith("ALLOW:")

    def test_headline_mentions_assessment(self):
        out = opf_mod.generate_long_arc_report(
            _persistent_degradation_history(),
        )
        assert "persistent degradation" in out["headline"].lower()

    def test_headline_mentions_risk_level(self):
        out = opf_mod.generate_long_arc_report(
            _persistent_degradation_history(),
        )
        assert "high" in out["headline"].lower()

    def test_headline_mentions_whipsaw_when_whipsaw(self):
        out = opf_mod.generate_long_arc_report(
            _whipsaw_history(risk="high"),
        )
        assert "whipsaw" in out["headline"].lower()

    def test_headline_mentions_segment_count(self):
        history = _persistent_degradation_history()
        out = opf_mod.generate_long_arc_report(history)
        assert str(len(history)) in out["headline"]

    def test_headline_mentions_high_count(self):
        out = opf_mod.generate_long_arc_report(
            _persistent_risk_history(),
        )
        # 4 high-risk segments.
        assert "4 high-risk segments" in out["headline"]

    def test_headline_non_empty(self):
        out = opf_mod.generate_long_arc_report(_stabilizing_history())
        assert out["headline"].strip() != ""


# ===========================================================================
# F. generate_long_arc_report — content delegation
# ===========================================================================
class TestReportDelegation:
    def test_fusion_matches_unit_31(self):
        history = _persistent_degradation_history()
        out = opf_mod.generate_long_arc_report(history)
        assert out["fusion"] == rf_mod.fuse_regime_history(history)

    def test_trajectory_matches_unit_31(self):
        history = _stabilizing_history()
        out = opf_mod.generate_long_arc_report(history)
        fusion = rf_mod.fuse_regime_history(history)
        assert out["trajectory"] == fusion["trajectory"]

    def test_oscillation_matches_unit_31(self):
        history = _whipsaw_history(risk="medium")
        out = opf_mod.generate_long_arc_report(history)
        fusion = rf_mod.fuse_regime_history(history)
        assert out["oscillation"] == fusion["oscillation"]

    def test_cumulative_risk_matches_unit_31(self):
        history = _persistent_risk_history()
        out = opf_mod.generate_long_arc_report(history)
        fusion = rf_mod.fuse_regime_history(history)
        assert out["cumulative_risk"] == fusion["cumulative_risk"]

    def test_history_echoed(self):
        history = _stabilizing_history()
        out = opf_mod.generate_long_arc_report(history)
        assert out["history"] == history

    def test_empty_history_well_formed(self):
        out = opf_mod.generate_long_arc_report([])
        assert set(out.keys()) == {
            "headline", "decision", "long_arc_assessment",
            "risk_level", "trajectory", "oscillation",
            "cumulative_risk", "fusion", "history",
        }
        assert out["decision"] == "allow"
        assert out["history"] == []


# ===========================================================================
# G. tag_long_arc_decisions — happy path
# ===========================================================================
class TestTagDecisionsHappy:
    def test_response_shape(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(fusion, {})
        assert set(out.keys()) == {"applied", "tags", "overrides"}

    def test_applied_always_true(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(fusion, {})
        assert out["applied"] is True

    def test_empty_decisions_uses_base_tags(self):
        history = _persistent_degradation_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(fusion, {})
        assert "long_arc_persistent_degradation" in out["tags"]
        assert "long_arc_risk_high" in out["tags"]
        assert out["overrides"] == {}

    def test_tags_alpha_sorted(self):
        history = _whipsaw_history(risk="high")
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(fusion, {})
        assert out["tags"] == sorted(out["tags"])

    def test_tags_deduped(self):
        history = _whipsaw_history(risk="high")
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(fusion, {})
        assert len(out["tags"]) == len(set(out["tags"]))


# ===========================================================================
# H. tag_long_arc_decisions — override paths
# ===========================================================================
class TestTagDecisionsOverrides:
    def test_override_decision_adds_audit_tag(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(
            fusion, {"override_decision": "block"},
        )
        assert "long_arc_override_decision" in out["tags"]

    def test_override_decision_adds_target_risk_tag(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(
            fusion, {"override_decision": "block"},
        )
        # Block → long_arc_risk_high should appear.
        assert "long_arc_risk_high" in out["tags"]

    def test_override_decision_echoed(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(
            fusion, {"override_decision": "warn"},
        )
        assert out["overrides"]["override_decision"] == "warn"

    def test_escalate_true_adds_escalation_tag(self):
        history = _persistent_degradation_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(
            fusion, {"escalate": True},
        )
        assert "long_arc_override_escalated" in out["tags"]

    def test_escalate_false_no_escalation_tag(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(
            fusion, {"escalate": False},
        )
        assert "long_arc_override_escalated" not in out["tags"]

    def test_audit_note_recorded(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(
            fusion, {"audit_note": "Operator manual review."},
        )
        assert out["overrides"]["audit_note"] == "Operator manual review."

    def test_combined_overrides(self):
        history = _persistent_degradation_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(
            fusion,
            {
                "override_decision": "warn",
                "escalate":          True,
                "audit_note":        "ops escalation",
            },
        )
        assert "long_arc_override_decision" in out["tags"]
        assert "long_arc_override_escalated" in out["tags"]
        assert "long_arc_risk_medium" in out["tags"]
        assert out["overrides"]["override_decision"] == "warn"
        assert out["overrides"]["escalate"] is True
        assert out["overrides"]["audit_note"] == "ops escalation"


# ===========================================================================
# I. tag_long_arc_decisions — validation
# ===========================================================================
class TestTagDecisionsValidation:
    def test_non_dict_fusion_raises(self):
        with pytest.raises(ValueError, match="dict"):
            opf_mod.tag_long_arc_decisions("nope", {})

    def test_missing_required_key_raises(self):
        bad = {"trajectory": {}}
        with pytest.raises(ValueError, match="Unit 31 key"):
            opf_mod.tag_long_arc_decisions(bad, {})

    def test_non_dict_decisions_raises(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        with pytest.raises(ValueError, match="decisions"):
            opf_mod.tag_long_arc_decisions(fusion, "nope")

    def test_invalid_override_decision_raises(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        with pytest.raises(ValueError, match="override_decision"):
            opf_mod.tag_long_arc_decisions(
                fusion, {"override_decision": "maybe"},
            )

    def test_non_bool_escalate_raises(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        with pytest.raises(ValueError, match="escalate"):
            opf_mod.tag_long_arc_decisions(
                fusion, {"escalate": "yes"},
            )

    def test_non_string_audit_note_raises(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        with pytest.raises(ValueError, match="audit_note"):
            opf_mod.tag_long_arc_decisions(
                fusion, {"audit_note": 42},
            )


# ===========================================================================
# J. tag_long_arc_decisions — idempotency
# ===========================================================================
class TestTagDecisionsIdempotency:
    def test_repeat_call_byte_equal(self):
        history = _whipsaw_history(risk="high")
        fusion = rf_mod.fuse_regime_history(history)
        a = opf_mod.tag_long_arc_decisions(
            fusion, {"override_decision": "block", "escalate": True},
        )
        b = opf_mod.tag_long_arc_decisions(
            fusion, {"override_decision": "block", "escalate": True},
        )
        assert a == b

    def test_no_duplicate_tags(self):
        history = _persistent_degradation_history()
        fusion = rf_mod.fuse_regime_history(history)
        out = opf_mod.tag_long_arc_decisions(
            fusion,
            {"override_decision": "block", "escalate": True},
        )
        assert len(out["tags"]) == len(set(out["tags"]))


# ===========================================================================
# K. Determinism
# ===========================================================================
class TestDeterminism:
    def test_evaluate_byte_equal(self):
        history = _persistent_degradation_history()
        a = opf_mod.evaluate_long_arc(history)
        b = opf_mod.evaluate_long_arc(history)
        assert a == b

    def test_report_byte_equal(self):
        history = _whipsaw_history(risk="high")
        a = opf_mod.generate_long_arc_report(history)
        b = opf_mod.generate_long_arc_report(history)
        assert a == b

    def test_tag_byte_equal_empty_decisions(self):
        history = _stabilizing_history()
        fusion = rf_mod.fuse_regime_history(history)
        a = opf_mod.tag_long_arc_decisions(fusion, {})
        b = opf_mod.tag_long_arc_decisions(fusion, {})
        assert a == b


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            opf_mod.evaluate_long_arc,
            opf_mod.generate_long_arc_report,
            opf_mod.tag_long_arc_decisions,
        ):
            assert callable(fn)

    def test_trajectory_tag_vocabulary_locked(self):
        assert opf_mod.TAG_TRAJECTORY_IMPROVING   == "trajectory_improving"
        assert opf_mod.TAG_TRAJECTORY_DEGRADING   == "trajectory_degrading"
        assert opf_mod.TAG_TRAJECTORY_FLAT        == "trajectory_flat"
        assert opf_mod.TAG_TRAJECTORY_OSCILLATING == "trajectory_oscillating"

    def test_assessment_tag_vocabulary_locked(self):
        assert opf_mod.TAG_LA_STABILIZING             == "long_arc_stabilizing"
        assert opf_mod.TAG_LA_PERSISTENT_DEGRADATION  == "long_arc_persistent_degradation"
        assert opf_mod.TAG_LA_PERSISTENT_RISK         == "long_arc_persistent_risk"
        assert opf_mod.TAG_LA_OSCILLATING_REGIME      == "long_arc_oscillating_regime"
        assert opf_mod.TAG_LA_BENIGN                  == "long_arc_benign"

    def test_risk_tag_vocabulary_locked(self):
        assert opf_mod.TAG_LA_RISK_LOW    == "long_arc_risk_low"
        assert opf_mod.TAG_LA_RISK_MEDIUM == "long_arc_risk_medium"
        assert opf_mod.TAG_LA_RISK_HIGH   == "long_arc_risk_high"

    def test_oscillation_tag_vocabulary_locked(self):
        assert opf_mod.TAG_LA_OSCILLATING == "long_arc_oscillating"
        assert opf_mod.TAG_LA_WHIPSAW     == "long_arc_whipsaw"

    def test_override_tag_vocabulary_locked(self):
        assert opf_mod.TAG_LA_OVERRIDE_DECISION  == "long_arc_override_decision"
        assert opf_mod.TAG_LA_OVERRIDE_ESCALATED == "long_arc_override_escalated"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(opf_mod)

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

    def test_composes_unit_31(self):
        src = self._code_only()
        assert "fuse_regime_history" in src
