"""
Tests for ELINS10 Unit 28 — operator structural actions.

Layered coverage (>= 60 tests, target ~70):
    A. apply_structural_analysis — shape + decision rules
    B. apply_structural_analysis — tag vocabulary
    C. apply_structural_analysis — signal propagation
    D. tag_structural_decisions — happy path
    E. tag_structural_decisions — validation
    F. tag_structural_decisions — idempotency
    G. generate_structural_report — shape locked
    H. generate_structural_report — content delegation
    I. generate_structural_report — headline content
    J. generate_structural_report — alerts + pairs aggregates
    K. Small-N / empty
    L. Determinism
    M. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_operator_structural as ops_mod
import elins_structural_trend as st_mod


# ===========================================================================
# Fixtures
# ===========================================================================
def _group_payload(decision: str = "allow",
                   health: float = 0.8,
                   anomaly: float = 0.0,
                   regressions: int = 0,
                   reasons=None) -> dict:
    return {
        "decision": decision,
        "reasons":  list(reasons) if reasons else [],
        "metrics": {
            "health":           health,
            "anomaly_fraction": anomaly,
            "trend_shift":      "neutral",
            "cluster_shift":    "neutral",
            "regressions":      regressions,
            "promoted_pairs":   [],
        },
    }


def _batch(health: float = 0.8,
           anomaly: float = 0.0,
           regressions: int = 0,
           decision: str = "allow",
           with_within_batch_diff: bool = False) -> dict:
    groups = {
        "g0": _group_payload(
            decision, health, anomaly, regressions,
            reasons=["health_drop_block"] if decision == "block" else None,
        ),
    }
    comparisons = {}
    if with_within_batch_diff:
        comparisons = {
            "g0_vs_g1": {
                "health_delta":     -0.3,
                "anomaly_delta":     0.2,
                "cluster_shift":    "more_downward",
                "trend_shift":      "toward_volatility",
                "pair_regressions": ["pA", "pB"],
                "winner":           "g0",
            },
        }
    return {"groups": groups, "comparisons": comparisons}


def _series(prefix="t",
            healths=None,
            anomalies=None,
            regressions=None) -> list:
    n = max(
        len(healths or []),
        len(anomalies or []),
        len(regressions or []),
    )
    healths = healths or [0.8] * n
    anomalies = anomalies or [0.0] * n
    regressions = regressions or [0] * n
    return [
        (f"{prefix}_{i:02d}", _batch(healths[i], anomalies[i], regressions[i]))
        for i in range(n)
    ]


def _stable_timeline() -> list:
    return _series(healths=[0.80, 0.80, 0.80, 0.80])


def _transition_timeline() -> list:
    """Single spike → at least one breakpoint, moderate variance →
    transition regime."""
    return _series(healths=[0.80, 0.80, 0.80, 0.80, 0.20])


def _unstable_timeline() -> list:
    """High variance + multiple breakpoints → unstable regime."""
    return _series(
        healths=[0.80] * 6,
        anomalies=[0.05, 0.50, 0.05, 0.50, 0.05, 0.50],
        regressions=[0, 4, 0, 4, 0, 4],
    )


# ===========================================================================
# A. apply_structural_analysis — shape + decision rules
# ===========================================================================
class TestApplyShape:
    def test_response_shape(self):
        out = ops_mod.apply_structural_analysis(_stable_timeline())
        assert set(out.keys()) == {
            "decision", "tags",
            "regime_class", "volatility_variance",
            "breakpoints", "structural_events",
        }

    def test_decision_in_locked_vocab(self):
        out = ops_mod.apply_structural_analysis(_stable_timeline())
        assert out["decision"] in ("allow", "warn", "block")

    def test_tags_is_list(self):
        out = ops_mod.apply_structural_analysis(_stable_timeline())
        assert isinstance(out["tags"], list)

    def test_regime_class_propagates(self):
        timeline = _stable_timeline()
        out = ops_mod.apply_structural_analysis(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["regime_class"] == structural["regime_class"]


class TestApplyDecisionRules:
    def test_stable_regime_allows(self):
        out = ops_mod.apply_structural_analysis(_stable_timeline())
        assert out["decision"] == "allow"

    def test_unstable_regime_blocks(self):
        out = ops_mod.apply_structural_analysis(_unstable_timeline())
        if out["regime_class"] == "unstable":
            assert out["decision"] == "block"

    def test_transition_regime_warns(self):
        out = ops_mod.apply_structural_analysis(_transition_timeline())
        if out["regime_class"] == "transition":
            assert out["decision"] == "warn"


# ===========================================================================
# B. apply_structural_analysis — tag vocabulary
# ===========================================================================
class TestApplyTags:
    def test_stable_regime_tag_fires(self):
        out = ops_mod.apply_structural_analysis(_stable_timeline())
        assert "regime_stable" in out["tags"]

    def test_unstable_regime_tag_fires(self):
        out = ops_mod.apply_structural_analysis(_unstable_timeline())
        if out["regime_class"] == "unstable":
            assert "regime_unstable" in out["tags"]

    def test_volatility_low_tag_fires_on_stable(self):
        out = ops_mod.apply_structural_analysis(_stable_timeline())
        assert "volatility_low" in out["tags"]

    def test_volatility_high_tag_fires_on_unstable(self):
        out = ops_mod.apply_structural_analysis(_unstable_timeline())
        if out["volatility_variance"] >= 0.02:
            assert "volatility_high" in out["tags"]

    def test_no_breakpoints_tag_fires_on_stable(self):
        out = ops_mod.apply_structural_analysis(_stable_timeline())
        assert "no_breakpoints" in out["tags"]

    def test_breakpoints_present_tag_fires_on_spike(self):
        out = ops_mod.apply_structural_analysis(_transition_timeline())
        if out["breakpoints"]:
            assert "breakpoints_present" in out["tags"]

    def test_tags_alpha_sorted(self):
        out = ops_mod.apply_structural_analysis(_unstable_timeline())
        assert out["tags"] == sorted(out["tags"])

    def test_tag_count_locked(self):
        # Exactly one regime tag + one volatility tag + one breakpoint
        # tag → always 3 tags.
        out = ops_mod.apply_structural_analysis(_stable_timeline())
        assert len(out["tags"]) == 3


# ===========================================================================
# C. apply_structural_analysis — signal propagation
# ===========================================================================
class TestApplySignalPropagation:
    def test_volatility_variance_matches_unit_27(self):
        timeline = _stable_timeline()
        out = ops_mod.apply_structural_analysis(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["volatility_variance"] == pytest.approx(
            structural["volatility_variance"],
        )

    def test_breakpoints_match_unit_27(self):
        timeline = _transition_timeline()
        out = ops_mod.apply_structural_analysis(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["breakpoints"] == structural["breakpoints"]

    def test_structural_events_match_unit_27(self):
        timeline = _unstable_timeline()
        out = ops_mod.apply_structural_analysis(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["structural_events"] == structural["structural_events"]


# ===========================================================================
# D. tag_structural_decisions — happy path
# ===========================================================================
class TestTagDecisionsHappy:
    def test_response_shape(self):
        out = ops_mod.tag_structural_decisions(
            _stable_timeline(), "allow",
        )
        assert set(out.keys()) == {"applied", "tags"}

    def test_applied_always_true(self):
        out = ops_mod.tag_structural_decisions(
            _stable_timeline(), "warn",
        )
        assert out["applied"] is True

    def test_allow_tag_is_regime_stable(self):
        out = ops_mod.tag_structural_decisions(
            _stable_timeline(), "allow",
        )
        assert out["tags"] == ["regime_stable"]

    def test_warn_tag_is_regime_transition(self):
        out = ops_mod.tag_structural_decisions(
            _stable_timeline(), "warn",
        )
        assert out["tags"] == ["regime_transition"]

    def test_block_tag_is_regime_unstable(self):
        out = ops_mod.tag_structural_decisions(
            _stable_timeline(), "block",
        )
        assert out["tags"] == ["regime_unstable"]


# ===========================================================================
# E. tag_structural_decisions — validation
# ===========================================================================
class TestTagDecisionsValidation:
    def test_invalid_decision_raises(self):
        with pytest.raises(ValueError, match="must be one of"):
            ops_mod.tag_structural_decisions(
                _stable_timeline(), "maybe",
            )

    def test_non_string_decision_raises(self):
        with pytest.raises(ValueError, match="must be one of"):
            ops_mod.tag_structural_decisions(_stable_timeline(), 123)

    def test_non_list_timeline_raises(self):
        with pytest.raises(ValueError, match="list"):
            ops_mod.tag_structural_decisions("nope", "allow")

    def test_malformed_payload_raises(self):
        # Bubbles up from Unit 27's validation.
        with pytest.raises(ValueError):
            ops_mod.tag_structural_decisions([("a", "nope")], "allow")


# ===========================================================================
# F. tag_structural_decisions — idempotency
# ===========================================================================
class TestTagDecisionsIdempotency:
    def test_repeat_call_byte_equal(self):
        timeline = _stable_timeline()
        a = ops_mod.tag_structural_decisions(timeline, "warn")
        b = ops_mod.tag_structural_decisions(timeline, "warn")
        assert a == b

    def test_single_tag_returned(self):
        out = ops_mod.tag_structural_decisions(
            _stable_timeline(), "warn",
        )
        assert len(out["tags"]) == 1


# ===========================================================================
# G. generate_structural_report — shape locked
# ===========================================================================
class TestReportShape:
    def test_top_level_keys(self):
        out = ops_mod.generate_structural_report(_stable_timeline())
        assert set(out.keys()) == {
            "headline", "regime_class",
            "volatility_variance", "breakpoints",
            "structural_events", "timeline",
            "alerts", "pairs", "diffs",
        }

    def test_alerts_keyed_by_timestamp(self):
        timeline = _stable_timeline()
        out = ops_mod.generate_structural_report(timeline)
        expected = {entry[0] for entry in timeline}
        assert set(out["alerts"].keys()) == expected

    def test_pairs_keyed_by_timestamp(self):
        timeline = _stable_timeline()
        out = ops_mod.generate_structural_report(timeline)
        expected = {entry[0] for entry in timeline}
        assert set(out["pairs"].keys()) == expected

    def test_diffs_keyed_by_timestamp(self):
        timeline = _stable_timeline()
        out = ops_mod.generate_structural_report(timeline)
        expected = {entry[0] for entry in timeline}
        assert set(out["diffs"].keys()) == expected


# ===========================================================================
# H. generate_structural_report — content delegation
# ===========================================================================
class TestReportDelegation:
    def test_regime_class_matches_unit_27(self):
        timeline = _transition_timeline()
        out = ops_mod.generate_structural_report(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["regime_class"] == structural["regime_class"]

    def test_volatility_variance_matches_unit_27(self):
        timeline = _stable_timeline()
        out = ops_mod.generate_structural_report(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["volatility_variance"] == pytest.approx(
            structural["volatility_variance"],
        )

    def test_breakpoints_match_unit_27(self):
        timeline = _transition_timeline()
        out = ops_mod.generate_structural_report(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["breakpoints"] == structural["breakpoints"]

    def test_structural_events_match_unit_27(self):
        timeline = _unstable_timeline()
        out = ops_mod.generate_structural_report(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["structural_events"] == structural["structural_events"]

    def test_timeline_matches_unit_27(self):
        timeline = _stable_timeline()
        out = ops_mod.generate_structural_report(timeline)
        structural = st_mod.analyze_structural_trends(timeline)
        assert out["timeline"] == structural["timeline"]


# ===========================================================================
# I. generate_structural_report — headline content
# ===========================================================================
class TestReportHeadline:
    def test_stable_headline_mentions_stable(self):
        out = ops_mod.generate_structural_report(_stable_timeline())
        assert "stable" in out["headline"].lower()

    def test_unstable_headline_calls_out_unstable(self):
        out = ops_mod.generate_structural_report(_unstable_timeline())
        if out["regime_class"] == "unstable":
            assert "unstable" in out["headline"].lower()

    def test_transition_headline_mentions_transition(self):
        out = ops_mod.generate_structural_report(_transition_timeline())
        if out["regime_class"] == "transition":
            assert "transition" in out["headline"].lower()

    def test_headline_non_empty(self):
        out = ops_mod.generate_structural_report(_stable_timeline())
        assert isinstance(out["headline"], str)
        assert out["headline"].strip() != ""

    def test_headline_includes_batch_count(self):
        out = ops_mod.generate_structural_report(_stable_timeline())
        assert "4" in out["headline"]

    def test_insufficient_headline(self):
        out = ops_mod.generate_structural_report(
            _series(healths=[0.8]),  # N=1, insufficient
        )
        assert "insufficient" in out["headline"].lower()


# ===========================================================================
# J. generate_structural_report — alerts + pairs aggregates
# ===========================================================================
class TestReportAggregates:
    def test_no_alerts_for_clean_batches(self):
        out = ops_mod.generate_structural_report(_stable_timeline())
        for ts_alerts in out["alerts"].values():
            assert ts_alerts == []

    def test_block_groups_surface_as_alerts(self):
        # Inject a block-decision group at one timestamp.
        timeline = [
            ("a", _batch(decision="block", health=0.2)),
            ("b", _batch()),
            ("c", _batch()),
        ]
        out = ops_mod.generate_structural_report(timeline)
        types = [a["type"] for a in out["alerts"]["a"]]
        assert "blocked_group" in types

    def test_pairs_aggregate_from_within_batch_diffs(self):
        timeline = [
            ("a", _batch(with_within_batch_diff=True)),
            ("b", _batch()),
            ("c", _batch()),
        ]
        out = ops_mod.generate_structural_report(timeline)
        assert "pA" in out["pairs"]["a"]
        assert "pB" in out["pairs"]["a"]

    def test_diffs_mirror_within_batch_comparisons(self):
        timeline = [
            ("a", _batch(with_within_batch_diff=True)),
            ("b", _batch()),
            ("c", _batch()),
        ]
        out = ops_mod.generate_structural_report(timeline)
        assert "g0_vs_g1" in out["diffs"]["a"]


# ===========================================================================
# K. Small-N / empty
# ===========================================================================
class TestSmallN:
    def test_empty_apply_returns_well_formed(self):
        out = ops_mod.apply_structural_analysis([])
        assert set(out.keys()) == {
            "decision", "tags",
            "regime_class", "volatility_variance",
            "breakpoints", "structural_events",
        }
        # Empty → Unit 27 reports stable (insufficient_data event) →
        # decision is allow.
        assert out["decision"] == "allow"

    def test_empty_report_returns_well_formed(self):
        out = ops_mod.generate_structural_report([])
        assert set(out.keys()) == {
            "headline", "regime_class",
            "volatility_variance", "breakpoints",
            "structural_events", "timeline",
            "alerts", "pairs", "diffs",
        }
        assert out["structural_events"] == ["insufficient_data"]
        assert out["timeline"] == []

    def test_single_entry_apply(self):
        timeline = _series(healths=[0.8])
        out = ops_mod.apply_structural_analysis(timeline)
        # Insufficient data → Unit 27 returns stable.
        assert out["decision"] == "allow"

    def test_two_entries_still_insufficient(self):
        timeline = _series(healths=[0.8, 0.9])
        out = ops_mod.apply_structural_analysis(timeline)
        assert out["structural_events"] == ["insufficient_data"]

    def test_three_entries_compute_real_regime(self):
        timeline = _series(healths=[0.8, 0.8, 0.8])
        out = ops_mod.apply_structural_analysis(timeline)
        assert out["structural_events"] != ["insufficient_data"]


# ===========================================================================
# L. Determinism
# ===========================================================================
class TestDeterminism:
    def test_apply_byte_equal(self):
        timeline = _transition_timeline()
        a = ops_mod.apply_structural_analysis(timeline)
        b = ops_mod.apply_structural_analysis(timeline)
        assert a == b

    def test_tag_decisions_byte_equal(self):
        timeline = _stable_timeline()
        a = ops_mod.tag_structural_decisions(timeline, "warn")
        b = ops_mod.tag_structural_decisions(timeline, "warn")
        assert a == b

    def test_report_byte_equal(self):
        timeline = _unstable_timeline()
        a = ops_mod.generate_structural_report(timeline)
        b = ops_mod.generate_structural_report(timeline)
        assert a == b


# ===========================================================================
# M. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            ops_mod.apply_structural_analysis,
            ops_mod.tag_structural_decisions,
            ops_mod.generate_structural_report,
        ):
            assert callable(fn)

    def test_tag_vocabulary_locked(self):
        assert ops_mod.TAG_REGIME_STABLE       == "regime_stable"
        assert ops_mod.TAG_REGIME_TRANSITION   == "regime_transition"
        assert ops_mod.TAG_REGIME_UNSTABLE     == "regime_unstable"
        assert ops_mod.TAG_VOLATILITY_LOW      == "volatility_low"
        assert ops_mod.TAG_VOLATILITY_MEDIUM   == "volatility_medium"
        assert ops_mod.TAG_VOLATILITY_HIGH     == "volatility_high"
        assert ops_mod.TAG_BREAKPOINTS_PRESENT == "breakpoints_present"
        assert ops_mod.TAG_NO_BREAKPOINTS      == "no_breakpoints"

    def test_decision_map_complete(self):
        for r in ("stable", "transition", "unstable"):
            assert r in ops_mod._REGIME_DECISION_MAP


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(ops_mod)

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

    def test_composes_unit_27(self):
        src = self._code_only()
        assert "analyze_structural_trends" in src
