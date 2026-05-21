"""
Tests for ELINS9 Unit 26 — operator trend actions.

Layered coverage (>= 60 tests, target ~70):
    A. apply_trend_analysis — shape + decision rules
    B. apply_trend_analysis — tag vocabulary
    C. tag_trend_decisions — happy path
    D. tag_trend_decisions — validation
    E. tag_trend_decisions — idempotency
    F. generate_trend_report — shape locked
    G. generate_trend_report — content delegation
    H. generate_trend_report — headline content
    I. generate_trend_report — alerts + pairs aggregates
    J. Small-N / empty
    K. Determinism
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_operator_trend as opt_mod
import elins_trend as tr_mod


# ===========================================================================
# Fixtures — synthetic Unit 21 outputs
# ===========================================================================
def _group_payload(decision: str,
                   health: float,
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
           anomaly: float = 0.05,
           regressions: int = 0,
           decision: str = "allow",
           with_within_batch_diff: bool = False) -> dict:
    """Build one Unit 21 evaluate_batch output."""
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


def _improving_timeline() -> list:
    return [
        ("2026-05-01", _batch(health=0.50)),
        ("2026-05-08", _batch(health=0.70)),
        ("2026-05-15", _batch(health=0.90)),
    ]


def _deteriorating_timeline() -> list:
    return [
        ("2026-05-01", _batch(health=0.90)),
        ("2026-05-08", _batch(health=0.70)),
        ("2026-05-15", _batch(health=0.50)),
    ]


def _flat_timeline() -> list:
    return [
        ("2026-05-01", _batch(health=0.80)),
        ("2026-05-08", _batch(health=0.80)),
        ("2026-05-15", _batch(health=0.80)),
    ]


def _anomaly_rising_timeline() -> list:
    return [
        ("2026-05-01", _batch(health=0.80, anomaly=0.05)),
        ("2026-05-08", _batch(health=0.80, anomaly=0.15)),
        ("2026-05-15", _batch(health=0.80, anomaly=0.30)),
    ]


# ===========================================================================
# A. apply_trend_analysis — shape + decision rules
# ===========================================================================
class TestApplyTrendShape:
    def test_response_shape(self):
        out = opt_mod.apply_trend_analysis(_improving_timeline())
        assert set(out.keys()) == {"decision", "tags", "trend_vectors"}

    def test_decision_in_locked_vocab(self):
        out = opt_mod.apply_trend_analysis(_improving_timeline())
        assert out["decision"] in ("allow", "warn", "block")

    def test_tags_is_list(self):
        out = opt_mod.apply_trend_analysis(_improving_timeline())
        assert isinstance(out["tags"], list)

    def test_trend_vectors_matches_unit_25(self):
        timeline = _improving_timeline()
        out = opt_mod.apply_trend_analysis(timeline)
        trend = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"] == trend["trend_vectors"]


class TestApplyTrendDecisionRules:
    def test_improving_health_allows(self):
        out = opt_mod.apply_trend_analysis(_improving_timeline())
        assert out["decision"] == "allow"

    def test_deteriorating_health_warns(self):
        out = opt_mod.apply_trend_analysis(_deteriorating_timeline())
        assert out["decision"] == "warn"

    def test_flat_universe_allows(self):
        out = opt_mod.apply_trend_analysis(_flat_timeline())
        assert out["decision"] == "allow"

    def test_anomaly_rising_warns(self):
        out = opt_mod.apply_trend_analysis(_anomaly_rising_timeline())
        assert out["decision"] == "warn"

    def test_regressions_rising_warns(self):
        timeline = [
            ("a", _batch(health=0.80, regressions=0)),
            ("b", _batch(health=0.80, regressions=2)),
            ("c", _batch(health=0.80, regressions=5)),
        ]
        out = opt_mod.apply_trend_analysis(timeline)
        assert out["decision"] == "warn"


# ===========================================================================
# B. apply_trend_analysis — tag vocabulary
# ===========================================================================
class TestApplyTrendTags:
    def test_health_up_tag_when_improving(self):
        out = opt_mod.apply_trend_analysis(_improving_timeline())
        assert "trend_health_up" in out["tags"]

    def test_health_down_tag_when_deteriorating(self):
        out = opt_mod.apply_trend_analysis(_deteriorating_timeline())
        assert "trend_health_down" in out["tags"]

    def test_flat_tag_when_all_directions_flat(self):
        out = opt_mod.apply_trend_analysis(_flat_timeline())
        assert out["tags"] == ["trend_flat"]

    def test_anomaly_up_tag_when_anomalies_rise(self):
        out = opt_mod.apply_trend_analysis(_anomaly_rising_timeline())
        assert "trend_anomaly_up" in out["tags"]

    def test_anomaly_down_tag_when_anomalies_fall(self):
        timeline = [
            ("a", _batch(health=0.8, anomaly=0.30)),
            ("b", _batch(health=0.8, anomaly=0.10)),
        ]
        out = opt_mod.apply_trend_analysis(timeline)
        assert "trend_anomaly_down" in out["tags"]

    def test_regressions_up_tag(self):
        timeline = [
            ("a", _batch(regressions=0)),
            ("b", _batch(regressions=2)),
            ("c", _batch(regressions=5)),
        ]
        out = opt_mod.apply_trend_analysis(timeline)
        assert "trend_regressions_up" in out["tags"]

    def test_regressions_down_tag(self):
        timeline = [
            ("a", _batch(regressions=5)),
            ("b", _batch(regressions=1)),
        ]
        out = opt_mod.apply_trend_analysis(timeline)
        assert "trend_regressions_down" in out["tags"]

    def test_tags_alpha_sorted(self):
        # Multiple signals firing simultaneously → tag list alpha-sorted.
        timeline = [
            ("a", _batch(health=0.9, anomaly=0.05, regressions=0)),
            ("b", _batch(health=0.5, anomaly=0.30, regressions=5)),
        ]
        out = opt_mod.apply_trend_analysis(timeline)
        assert out["tags"] == sorted(out["tags"])

    def test_flat_universe_only_flat_tag(self):
        out = opt_mod.apply_trend_analysis(_flat_timeline())
        assert out["tags"] == ["trend_flat"]


# ===========================================================================
# C. tag_trend_decisions — happy path
# ===========================================================================
class TestTagTrendDecisionsHappy:
    def test_response_shape(self):
        timeline = _improving_timeline()
        decisions = {"2026-05-01": "allow", "2026-05-08": "allow",
                     "2026-05-15": "allow"}
        out = opt_mod.tag_trend_decisions(timeline, decisions)
        assert set(out.keys()) == {"applied", "tags"}

    def test_applied_always_true(self):
        timeline = _improving_timeline()
        decisions = {"2026-05-01": "warn", "2026-05-08": "warn",
                     "2026-05-15": "warn"}
        out = opt_mod.tag_trend_decisions(timeline, decisions)
        assert out["applied"] is True

    def test_tags_keys_match_timestamps(self):
        timeline = _improving_timeline()
        decisions = {"2026-05-01": "allow", "2026-05-08": "allow",
                     "2026-05-15": "allow"}
        out = opt_mod.tag_trend_decisions(timeline, decisions)
        timestamps = {entry[0] for entry in timeline}
        assert set(out["tags"].keys()) == timestamps

    def test_allow_decision_tag_is_flat(self):
        timeline = [("a", _batch())]
        decisions = {"a": "allow"}
        out = opt_mod.tag_trend_decisions(timeline, decisions)
        assert out["tags"]["a"] == ["trend_flat"]

    def test_warn_decision_tag_is_health_down(self):
        timeline = [("a", _batch())]
        decisions = {"a": "warn"}
        out = opt_mod.tag_trend_decisions(timeline, decisions)
        assert out["tags"]["a"] == ["trend_health_down"]


# ===========================================================================
# D. tag_trend_decisions — validation
# ===========================================================================
class TestTagTrendDecisionsValidation:
    def test_invalid_decision_raises(self):
        timeline = [("a", _batch())]
        with pytest.raises(ValueError, match="must be one of"):
            opt_mod.tag_trend_decisions(timeline, {"a": "maybe"})

    def test_decisions_non_dict_raises(self):
        timeline = [("a", _batch())]
        with pytest.raises(ValueError, match="decisions"):
            opt_mod.tag_trend_decisions(timeline, "nope")

    def test_missing_decision_raises(self):
        timeline = _improving_timeline()
        with pytest.raises(ValueError, match="exactly the same timestamps"):
            opt_mod.tag_trend_decisions(timeline, {"2026-05-01": "allow"})

    def test_extra_decision_raises(self):
        timeline = [("a", _batch())]
        with pytest.raises(ValueError, match="exactly the same timestamps"):
            opt_mod.tag_trend_decisions(
                timeline, {"a": "allow", "b": "allow"},
            )

    def test_non_list_timeline_raises(self):
        with pytest.raises(ValueError, match="list"):
            opt_mod.tag_trend_decisions("nope", {})

    def test_malformed_timeline_payload_raises(self):
        # Invalid payload should bubble up from Unit 25 validation.
        with pytest.raises(ValueError):
            opt_mod.tag_trend_decisions([("a", "nope")], {"a": "allow"})


# ===========================================================================
# E. tag_trend_decisions — idempotency
# ===========================================================================
class TestTagTrendDecisionsIdempotency:
    def test_repeated_calls_byte_equal(self):
        timeline = _flat_timeline()
        decisions = {entry[0]: "allow" for entry in timeline}
        a = opt_mod.tag_trend_decisions(timeline, decisions)
        b = opt_mod.tag_trend_decisions(timeline, decisions)
        assert a == b

    def test_one_tag_per_timestamp(self):
        timeline = _flat_timeline()
        decisions = {entry[0]: "warn" for entry in timeline}
        out = opt_mod.tag_trend_decisions(timeline, decisions)
        for ts, tags in out["tags"].items():
            assert len(tags) == 1


# ===========================================================================
# F. generate_trend_report — shape locked
# ===========================================================================
class TestTrendReportShape:
    def test_top_level_keys(self):
        out = opt_mod.generate_trend_report(_improving_timeline())
        assert set(out.keys()) == {
            "headline", "trend_vectors", "events",
            "timeline", "alerts", "pairs", "diffs",
        }

    def test_alerts_keyed_by_timestamp(self):
        timeline = _improving_timeline()
        out = opt_mod.generate_trend_report(timeline)
        expected_timestamps = {entry[0] for entry in timeline}
        assert set(out["alerts"].keys()) == expected_timestamps

    def test_pairs_keyed_by_timestamp(self):
        timeline = _improving_timeline()
        out = opt_mod.generate_trend_report(timeline)
        expected_timestamps = {entry[0] for entry in timeline}
        assert set(out["pairs"].keys()) == expected_timestamps

    def test_diffs_keyed_by_timestamp(self):
        timeline = _improving_timeline()
        out = opt_mod.generate_trend_report(timeline)
        expected_timestamps = {entry[0] for entry in timeline}
        assert set(out["diffs"].keys()) == expected_timestamps


# ===========================================================================
# G. generate_trend_report — content delegation
# ===========================================================================
class TestReportDelegation:
    def test_trend_vectors_match_unit_25(self):
        timeline = _improving_timeline()
        out = opt_mod.generate_trend_report(timeline)
        trend = tr_mod.analyze_trends(timeline)
        assert out["trend_vectors"] == trend["trend_vectors"]

    def test_events_match_unit_25(self):
        timeline = _anomaly_rising_timeline()
        out = opt_mod.generate_trend_report(timeline)
        trend = tr_mod.analyze_trends(timeline)
        assert out["events"] == trend["events"]

    def test_timeline_matches_unit_25(self):
        timeline = _improving_timeline()
        out = opt_mod.generate_trend_report(timeline)
        trend = tr_mod.analyze_trends(timeline)
        assert out["timeline"] == trend["timeline"]


# ===========================================================================
# H. generate_trend_report — headline content
# ===========================================================================
class TestReportHeadline:
    def test_improving_headline(self):
        out = opt_mod.generate_trend_report(_improving_timeline())
        assert "improving" in out["headline"].lower()

    def test_deteriorating_headline(self):
        out = opt_mod.generate_trend_report(_deteriorating_timeline())
        assert "deteriorating" in out["headline"].lower()

    def test_flat_headline_mentions_stable(self):
        out = opt_mod.generate_trend_report(_flat_timeline())
        assert "stable" in out["headline"].lower()

    def test_mixed_trend_headline(self):
        # Health flat, anomalies rising → "Mixed trend ...".
        out = opt_mod.generate_trend_report(_anomaly_rising_timeline())
        assert "mixed" in out["headline"].lower()

    def test_headline_includes_batch_count(self):
        out = opt_mod.generate_trend_report(_improving_timeline())
        assert "3" in out["headline"]


# ===========================================================================
# I. generate_trend_report — alerts + pairs aggregates
# ===========================================================================
class TestReportAggregates:
    def test_no_alerts_for_clean_batches(self):
        out = opt_mod.generate_trend_report(_improving_timeline())
        for ts_alerts in out["alerts"].values():
            assert ts_alerts == []

    def test_block_groups_surface_as_alerts(self):
        timeline = [
            ("a", _batch(decision="block", health=0.2)),
            ("b", _batch()),
        ]
        out = opt_mod.generate_trend_report(timeline)
        types = [a["type"] for a in out["alerts"]["a"]]
        assert "blocked_group" in types

    def test_pairs_aggregate_from_within_batch_diffs(self):
        timeline = [
            ("a", _batch(with_within_batch_diff=True)),
            ("b", _batch()),
        ]
        out = opt_mod.generate_trend_report(timeline)
        assert "pA" in out["pairs"]["a"]
        assert "pB" in out["pairs"]["a"]

    def test_diffs_mirror_within_batch_comparisons(self):
        timeline = [
            ("a", _batch(with_within_batch_diff=True)),
            ("b", _batch()),
        ]
        out = opt_mod.generate_trend_report(timeline)
        assert "g0_vs_g1" in out["diffs"]["a"]


# ===========================================================================
# J. Small-N / empty
# ===========================================================================
class TestSmallN:
    def test_empty_apply_returns_well_formed(self):
        out = opt_mod.apply_trend_analysis([])
        assert set(out.keys()) == {"decision", "tags", "trend_vectors"}
        # Empty timeline → all flat → allow + ["trend_flat"].
        assert out["decision"] == "allow"
        assert out["tags"] == ["trend_flat"]

    def test_empty_report_returns_well_formed(self):
        out = opt_mod.generate_trend_report([])
        assert set(out.keys()) == {
            "headline", "trend_vectors", "events",
            "timeline", "alerts", "pairs", "diffs",
        }
        assert out["events"] == ["insufficient_data"]
        assert out["timeline"] == []

    def test_single_entry_apply(self):
        timeline = [("a", _batch())]
        out = opt_mod.apply_trend_analysis(timeline)
        # Single entry → Unit 25 returns insufficient_data + flat
        # vectors → decision allow.
        assert out["decision"] == "allow"

    def test_single_entry_report(self):
        timeline = [("a", _batch())]
        out = opt_mod.generate_trend_report(timeline)
        # Headline calls out insufficient data.
        assert "insufficient" in out["headline"].lower() or \
               "1" in out["headline"]


# ===========================================================================
# K. Determinism
# ===========================================================================
class TestDeterminism:
    def test_apply_byte_equal(self):
        timeline = _improving_timeline()
        a = opt_mod.apply_trend_analysis(timeline)
        b = opt_mod.apply_trend_analysis(timeline)
        assert a == b

    def test_tag_decisions_byte_equal(self):
        timeline = _flat_timeline()
        decisions = {entry[0]: "allow" for entry in timeline}
        a = opt_mod.tag_trend_decisions(timeline, decisions)
        b = opt_mod.tag_trend_decisions(timeline, decisions)
        assert a == b

    def test_report_byte_equal(self):
        timeline = _deteriorating_timeline()
        a = opt_mod.generate_trend_report(timeline)
        b = opt_mod.generate_trend_report(timeline)
        assert a == b


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            opt_mod.apply_trend_analysis,
            opt_mod.tag_trend_decisions,
            opt_mod.generate_trend_report,
        ):
            assert callable(fn)

    def test_tag_vocabulary_locked(self):
        assert opt_mod.TAG_TREND_HEALTH_UP        == "trend_health_up"
        assert opt_mod.TAG_TREND_HEALTH_DOWN      == "trend_health_down"
        assert opt_mod.TAG_TREND_ANOMALY_UP       == "trend_anomaly_up"
        assert opt_mod.TAG_TREND_ANOMALY_DOWN     == "trend_anomaly_down"
        assert opt_mod.TAG_TREND_REGRESSIONS_UP   == "trend_regressions_up"
        assert opt_mod.TAG_TREND_REGRESSIONS_DOWN == "trend_regressions_down"
        assert opt_mod.TAG_TREND_FLAT             == "trend_flat"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(opt_mod)

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

    def test_composes_unit_25(self):
        src = self._code_only()
        assert "analyze_trends" in src
