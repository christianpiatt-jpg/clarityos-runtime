"""
Tests for ELINS8 Unit 24 — operator cross-batch actions.

Layered coverage (>= 60 tests, target ~70):
    A. apply_cross_batch — happy path + verdict propagation
    B. apply_cross_batch — winner/loser/tie detection
    C. tag_cross_batch — happy path
    D. tag_cross_batch — validation
    E. tag_cross_batch — idempotency invariants
    F. generate_cross_batch_report — shape locked
    G. generate_cross_batch_report — content delegation
    H. generate_cross_batch_report — headline content
    I. generate_cross_batch_report — alerts + pairs aggregates
    J. Empty / single batch
    K. Determinism
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_cross_batch as xb_mod
import elins_operator_cross_batch as opxb_mod


# ===========================================================================
# Fixtures
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


def _batch_payload(groups: dict, comparisons: dict = None) -> dict:
    return {
        "groups":      groups,
        "comparisons": comparisons or {},
    }


def _healthy_batch(name_prefix="g", n_groups=3) -> dict:
    groups = {
        f"{name_prefix}{i}": _group_payload("allow", 0.85, 0.05, 0)
        for i in range(n_groups)
    }
    return _batch_payload(groups)


def _unhealthy_batch(name_prefix="g", n_groups=3) -> dict:
    groups = {
        f"{name_prefix}{i}": _group_payload(
            "block", 0.20, 0.30, 2, reasons=["health_drop_block"],
        )
        for i in range(n_groups)
    }
    # Add a within-batch comparison with regressions so the alerts /
    # pairs aggregates have something to surface.
    comparisons = {
        f"{name_prefix}0_vs_{name_prefix}1": {
            "health_delta": -0.5,
            "anomaly_delta": 0.2,
            "cluster_shift": "more_downward",
            "trend_shift":   "toward_volatility",
            "pair_regressions": ["p1", "p2"],
            "winner": f"{name_prefix}0",
        }
    }
    return _batch_payload(groups, comparisons)


def _mixed_batch(name_prefix="g") -> dict:
    return _batch_payload({
        f"{name_prefix}0": _group_payload("allow", 0.80, 0.05, 0),
        f"{name_prefix}1": _group_payload("warn",  0.55, 0.15, 1,
                                            reasons=["low_pair_stability"]),
        f"{name_prefix}2": _group_payload("block", 0.20, 0.35, 3,
                                            reasons=["health_drop_block"]),
    })


# ===========================================================================
# A. apply_cross_batch — happy path + verdict propagation
# ===========================================================================
class TestApplyCrossBatchHappy:
    def test_response_shape(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.apply_cross_batch(batches)
        assert set(out.keys()) == {"batches"}

    def test_batches_keys_match_input(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.apply_cross_batch(batches)
        assert set(out["batches"].keys()) == set(batches.keys())

    def test_per_batch_keys_locked(self):
        batches = {"a": _healthy_batch()}
        out = opxb_mod.apply_cross_batch(batches)
        assert set(out["batches"]["a"].keys()) == {"decision", "tags"}

    def test_decision_in_locked_vocab(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.apply_cross_batch(batches)
        for data in out["batches"].values():
            assert data["decision"] in ("winner", "loser", "tie")

    def test_tag_matches_decision(self):
        batches = {"a": _healthy_batch(), "b": _unhealthy_batch()}
        out = opxb_mod.apply_cross_batch(batches)
        for data in out["batches"].values():
            verdict = data["decision"]
            expected_tag = {
                "winner": "cross_batch_winner",
                "loser":  "cross_batch_loser",
                "tie":    "cross_batch_tie",
            }[verdict]
            assert expected_tag in data["tags"]


# ===========================================================================
# B. apply_cross_batch — winner/loser/tie detection
# ===========================================================================
class TestVerdictDetection:
    def test_healthy_a_beats_unhealthy_b(self):
        batches = {"a": _healthy_batch(), "b": _unhealthy_batch()}
        out = opxb_mod.apply_cross_batch(batches)
        assert out["batches"]["a"]["decision"] == "winner"
        assert out["batches"]["b"]["decision"] == "loser"

    def test_unhealthy_a_loses_to_healthy_b(self):
        batches = {"a": _unhealthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.apply_cross_batch(batches)
        assert out["batches"]["a"]["decision"] == "loser"
        assert out["batches"]["b"]["decision"] == "winner"

    def test_identical_batches_all_ties(self):
        batch = _healthy_batch()
        batches = {"a": batch, "b": batch}
        out = opxb_mod.apply_cross_batch(batches)
        assert out["batches"]["a"]["decision"] == "tie"
        assert out["batches"]["b"]["decision"] == "tie"

    def test_single_batch_is_tie(self):
        # No comparisons → every batch defaults to tie.
        batches = {"only": _healthy_batch()}
        out = opxb_mod.apply_cross_batch(batches)
        assert out["batches"]["only"]["decision"] == "tie"

    def test_three_way_partial_order(self):
        # Healthy > mixed > unhealthy → top has net 2 wins, bottom has
        # net -2 wins, mid is tie or moves toward middle.
        batches = {
            "best":  _healthy_batch(),
            "mid":   _mixed_batch(),
            "worst": _unhealthy_batch(),
        }
        out = opxb_mod.apply_cross_batch(batches)
        assert out["batches"]["best"]["decision"] == "winner"
        assert out["batches"]["worst"]["decision"] == "loser"


# ===========================================================================
# C. tag_cross_batch — happy path
# ===========================================================================
class TestTagCrossBatchHappy:
    def test_response_shape(self):
        batches = {"a": _healthy_batch()}
        out = opxb_mod.tag_cross_batch(batches, {"a": "winner"})
        assert set(out.keys()) == {"applied", "tagged"}

    def test_applied_always_true(self):
        batches = {"a": _healthy_batch()}
        out = opxb_mod.tag_cross_batch(batches, {"a": "tie"})
        assert out["applied"] is True

    def test_tagged_keys_match_batches(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.tag_cross_batch(
            batches, {"a": "winner", "b": "loser"},
        )
        assert set(out["tagged"].keys()) == set(batches.keys())

    def test_winner_tag_applied(self):
        batches = {"a": _healthy_batch()}
        out = opxb_mod.tag_cross_batch(batches, {"a": "winner"})
        assert out["tagged"]["a"] == ["cross_batch_winner"]

    def test_loser_tag_applied(self):
        batches = {"a": _healthy_batch()}
        out = opxb_mod.tag_cross_batch(batches, {"a": "loser"})
        assert out["tagged"]["a"] == ["cross_batch_loser"]

    def test_tie_tag_applied(self):
        batches = {"a": _healthy_batch()}
        out = opxb_mod.tag_cross_batch(batches, {"a": "tie"})
        assert out["tagged"]["a"] == ["cross_batch_tie"]


# ===========================================================================
# D. tag_cross_batch — validation
# ===========================================================================
class TestTagCrossBatchValidation:
    def test_invalid_verdict_raises(self):
        batches = {"a": _healthy_batch()}
        with pytest.raises(ValueError, match="must be one of"):
            opxb_mod.tag_cross_batch(batches, {"a": "maybe"})

    def test_decisions_non_dict_raises(self):
        batches = {"a": _healthy_batch()}
        with pytest.raises(ValueError, match="decisions"):
            opxb_mod.tag_cross_batch(batches, "nope")

    def test_missing_decision_raises(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        with pytest.raises(ValueError, match="exactly the same batch names"):
            opxb_mod.tag_cross_batch(batches, {"a": "winner"})

    def test_extra_decision_raises(self):
        batches = {"a": _healthy_batch()}
        with pytest.raises(ValueError, match="exactly the same batch names"):
            opxb_mod.tag_cross_batch(
                batches, {"a": "winner", "b": "loser"},
            )

    def test_non_dict_batches_raises(self):
        with pytest.raises(ValueError, match="dict"):
            opxb_mod.tag_cross_batch("nope", {})

    def test_non_dict_payload_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            opxb_mod.tag_cross_batch({"a": "nope"}, {"a": "winner"})

    def test_empty_args_no_error(self):
        out = opxb_mod.tag_cross_batch({}, {})
        assert out["applied"] is True
        assert out["tagged"] == {}


# ===========================================================================
# E. tag_cross_batch — idempotency invariants
# ===========================================================================
class TestTagCrossBatchIdempotency:
    def test_repeated_calls_equal(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        decisions = {"a": "winner", "b": "loser"}
        a = opxb_mod.tag_cross_batch(batches, decisions)
        b = opxb_mod.tag_cross_batch(batches, decisions)
        assert a == b

    def test_tagged_list_never_duplicates(self):
        batches = {"a": _healthy_batch()}
        out = opxb_mod.tag_cross_batch(batches, {"a": "winner"})
        # Each batch carries exactly one tag for its verdict.
        assert len(out["tagged"]["a"]) == 1


# ===========================================================================
# F. generate_cross_batch_report — shape locked
# ===========================================================================
class TestCrossBatchReportShape:
    def test_top_level_keys(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert set(out.keys()) == {
            "headline", "batches", "comparisons",
            "alerts", "pairs", "diffs",
        }

    def test_alerts_keyed_by_batch(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert set(out["alerts"].keys()) == set(batches.keys())

    def test_pairs_keyed_by_batch(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert set(out["pairs"].keys()) == set(batches.keys())

    def test_diffs_match_comparisons(self):
        batches = {
            "a": _healthy_batch(),
            "b": _healthy_batch(),
            "c": _healthy_batch(),
        }
        out = opxb_mod.generate_cross_batch_report(batches)
        assert set(out["diffs"].keys()) == set(out["comparisons"].keys())


# ===========================================================================
# G. generate_cross_batch_report — content delegation
# ===========================================================================
class TestReportDelegation:
    def test_batches_match_unit_23(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        xb = xb_mod.compare_batches(batches)
        assert out["batches"] == xb["batches"]

    def test_comparisons_match_unit_23(self):
        batches = {"a": _mixed_batch(), "b": _unhealthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        xb = xb_mod.compare_batches(batches)
        assert out["comparisons"] == xb["comparisons"]

    def test_diffs_mirror_comparisons_payload(self):
        batches = {"a": _mixed_batch(), "b": _unhealthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert out["diffs"] == out["comparisons"]


# ===========================================================================
# H. generate_cross_batch_report — headline content
# ===========================================================================
class TestReportHeadline:
    def test_headline_non_empty(self):
        batches = {"a": _healthy_batch(), "b": _unhealthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert isinstance(out["headline"], str)
        assert out["headline"].strip() != ""

    def test_headline_names_winner_in_single_comparison(self):
        batches = {"a": _healthy_batch(), "b": _unhealthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        # Single comparison: a beats b → headline mentions "a wins over b".
        assert "wins over" in out["headline"]
        assert "a" in out["headline"]
        assert "b" in out["headline"]

    def test_headline_calls_out_tie(self):
        batch = _healthy_batch()
        batches = {"a": batch, "b": batch}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert "tie" in out["headline"].lower()

    def test_headline_handles_single_batch(self):
        batches = {"only": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        # No comparisons → headline still well-formed.
        assert isinstance(out["headline"], str)
        assert out["headline"].strip() != ""


# ===========================================================================
# I. generate_cross_batch_report — alerts + pairs aggregates
# ===========================================================================
class TestReportAggregates:
    def test_block_groups_surface_as_alerts(self):
        batches = {"a": _unhealthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        types = [a["type"] for a in out["alerts"]["a"]]
        assert "blocked_group" in types

    def test_warn_groups_surface_as_alerts(self):
        batches = {"a": _mixed_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        types = [a["type"] for a in out["alerts"]["a"]]
        assert "warned_group" in types

    def test_alert_entry_keys_locked(self):
        batches = {"a": _unhealthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        if out["alerts"]["a"]:
            entry = out["alerts"]["a"][0]
            assert set(entry.keys()) == {
                "type", "severity", "group", "reasons",
            }

    def test_healthy_batch_no_alerts(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert out["alerts"]["a"] == []
        assert out["alerts"]["b"] == []

    def test_pairs_aggregate_from_within_batch_comparisons(self):
        batches = {"a": _unhealthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        # _unhealthy_batch carries pair_regressions ["p1", "p2"] in
        # its synthetic within-batch comparison.
        assert "p1" in out["pairs"]["a"]
        assert "p2" in out["pairs"]["a"]

    def test_pairs_alpha_sorted(self):
        batches = {"a": _unhealthy_batch(), "b": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert out["pairs"]["a"] == sorted(out["pairs"]["a"])


# ===========================================================================
# J. Empty / single batch
# ===========================================================================
class TestEmptyAndSingle:
    def test_apply_empty(self):
        out = opxb_mod.apply_cross_batch({})
        assert out == {"batches": {}}

    def test_report_empty(self):
        out = opxb_mod.generate_cross_batch_report({})
        assert set(out.keys()) == {
            "headline", "batches", "comparisons",
            "alerts", "pairs", "diffs",
        }
        assert out["batches"] == {}
        assert out["comparisons"] == {}
        assert out["diffs"] == {}

    def test_report_single_batch_no_diffs(self):
        batches = {"only": _healthy_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        assert out["diffs"] == {}

    def test_single_batch_alerts_still_populated(self):
        batches = {"only": _mixed_batch()}
        out = opxb_mod.generate_cross_batch_report(batches)
        # Mixed batch has block + warn groups → alerts present.
        assert len(out["alerts"]["only"]) >= 1


# ===========================================================================
# K. Determinism
# ===========================================================================
class TestDeterminism:
    def test_apply_byte_equal(self):
        batches = {"a": _mixed_batch(), "b": _mixed_batch()}
        a = opxb_mod.apply_cross_batch(batches)
        b = opxb_mod.apply_cross_batch(batches)
        assert a == b

    def test_tag_byte_equal(self):
        batches = {"a": _healthy_batch()}
        decisions = {"a": "winner"}
        a = opxb_mod.tag_cross_batch(batches, decisions)
        b = opxb_mod.tag_cross_batch(batches, decisions)
        assert a == b

    def test_report_byte_equal(self):
        batches = {"a": _mixed_batch(), "b": _unhealthy_batch()}
        a = opxb_mod.generate_cross_batch_report(batches)
        b = opxb_mod.generate_cross_batch_report(batches)
        assert a == b


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            opxb_mod.apply_cross_batch,
            opxb_mod.tag_cross_batch,
            opxb_mod.generate_cross_batch_report,
        ):
            assert callable(fn)

    def test_tag_vocabulary_locked(self):
        assert opxb_mod.TAG_CROSS_BATCH_WINNER == "cross_batch_winner"
        assert opxb_mod.TAG_CROSS_BATCH_LOSER  == "cross_batch_loser"
        assert opxb_mod.TAG_CROSS_BATCH_TIE    == "cross_batch_tie"

    def test_verdict_tag_map_complete(self):
        for v in ("winner", "loser", "tie"):
            assert v in opxb_mod._VERDICT_TAG_MAP


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(opxb_mod)

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

    def test_composes_unit_23(self):
        src = self._code_only()
        assert "compare_batches" in src

    def test_no_persistence_imports(self):
        # Cross-batch operates on aggregates — must not touch the runs
        # persistence layer.
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "load_comparison_result",
            "save_comparison_result", "set_tags", "get_tags",
        ):
            assert forbidden not in src
