"""
Tests for ELINS8 Unit 23 — cross-batch intelligence engine.

Layered coverage (>= 60 tests, target ~70):
    A. Top-level shape / locked keys
    B. Batch summary content
    C. Comparison entry shape
    D. Group wins counting
    E. Decision counts per comparison
    F. Winner logic
    G. Aggregate deltas (mean health/anomaly, total regression)
    H. Alpha ordering invariants
    I. Partial-overlap batches (missing groups)
    J. Empty / single batch
    K. Determinism (byte-equal repeats)
    L. Validation
    M. Source-code purity / module surface
"""
from __future__ import annotations

import inspect

import pytest

import elins_cross_batch as xb_mod


# ===========================================================================
# Fixtures — synthetic Unit 21 outputs (no DB needed)
# ===========================================================================
def _group_payload(decision: str,
                   health: float,
                   anomaly: float = 0.0,
                   regressions: int = 0) -> dict:
    """Build one Unit 21 group entry."""
    return {
        "decision": decision,
        "reasons":  [],
        "metrics": {
            "health":           health,
            "anomaly_fraction": anomaly,
            "trend_shift":      "neutral",
            "cluster_shift":    "neutral",
            "regressions":      regressions,
            "promoted_pairs":   [],
        },
    }


def _batch_payload(groups: dict) -> dict:
    """Build one Unit 21 evaluate_batch output (groups + comparisons)."""
    return {
        "groups":      groups,
        "comparisons": {},
    }


def _healthy_batch(name_prefix="g", n_groups=3) -> dict:
    """All-allow batch with high health and no anomalies."""
    groups = {
        f"{name_prefix}{i}": _group_payload("allow", 0.85, 0.05, 0)
        for i in range(n_groups)
    }
    return _batch_payload(groups)


def _unhealthy_batch(name_prefix="g", n_groups=3) -> dict:
    """All-block batch with low health and many regressions."""
    groups = {
        f"{name_prefix}{i}": _group_payload("block", 0.20, 0.30, 2)
        for i in range(n_groups)
    }
    return _batch_payload(groups)


def _mixed_batch(name_prefix="g") -> dict:
    """One allow / one warn / one block group."""
    return _batch_payload({
        f"{name_prefix}0": _group_payload("allow", 0.80, 0.05, 0),
        f"{name_prefix}1": _group_payload("warn",  0.55, 0.15, 1),
        f"{name_prefix}2": _group_payload("block", 0.20, 0.35, 3),
    })


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert set(out.keys()) == {"batches", "comparisons"}

    def test_batches_section_is_dict(self):
        batches = {"a": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert isinstance(out["batches"], dict)

    def test_comparisons_section_is_dict(self):
        batches = {"a": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert isinstance(out["comparisons"], dict)


# ===========================================================================
# B. Batch summary content
# ===========================================================================
class TestBatchSummary:
    def test_per_batch_entry_keys_locked(self):
        batches = {"x": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert set(out["batches"]["x"].keys()) == {
            "decision_counts", "mean_health",
            "mean_anomaly_fraction", "total_regressions",
            "group_count",
        }

    def test_decision_counts_match_groups(self):
        batches = {"x": _mixed_batch()}
        out = xb_mod.compare_batches(batches)
        counts = out["batches"]["x"]["decision_counts"]
        assert counts == {"allow": 1, "warn": 1, "block": 1}

    def test_group_count_matches_input(self):
        batches = {"x": _healthy_batch(n_groups=4)}
        out = xb_mod.compare_batches(batches)
        assert out["batches"]["x"]["group_count"] == 4

    def test_mean_health_correct(self):
        batches = {"x": _healthy_batch(n_groups=3)}
        out = xb_mod.compare_batches(batches)
        # All 3 groups have health=0.85.
        assert out["batches"]["x"]["mean_health"] == pytest.approx(0.85)

    def test_total_regressions_summed(self):
        batches = {"x": _mixed_batch()}
        out = xb_mod.compare_batches(batches)
        # 0 + 1 + 3 = 4.
        assert out["batches"]["x"]["total_regressions"] == 4

    def test_empty_batch_zero_summary(self):
        batches = {"x": _batch_payload({})}
        out = xb_mod.compare_batches(batches)
        summary = out["batches"]["x"]
        assert summary["decision_counts"] == {"allow": 0, "warn": 0, "block": 0}
        assert summary["mean_health"] == 0.0
        assert summary["mean_anomaly_fraction"] == 0.0
        assert summary["total_regressions"] == 0
        assert summary["group_count"] == 0


# ===========================================================================
# C. Comparison entry shape
# ===========================================================================
class TestComparisonEntryShape:
    def test_entry_keys_locked(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        entry = out["comparisons"]["a_vs_b"]
        assert set(entry.keys()) == {
            "group_wins", "decision_counts",
            "health_delta", "anomaly_delta",
            "regression_count_delta", "winner",
        }

    def test_two_batches_one_comparison(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert len(out["comparisons"]) == 1

    def test_three_batches_three_comparisons(self):
        batches = {
            "a": _healthy_batch(),
            "b": _healthy_batch(),
            "c": _healthy_batch(),
        }
        out = xb_mod.compare_batches(batches)
        assert len(out["comparisons"]) == 3

    def test_decision_counts_subkeys(self):
        batches = {"a": _mixed_batch(), "b": _mixed_batch()}
        out = xb_mod.compare_batches(batches)
        dc = out["comparisons"]["a_vs_b"]["decision_counts"]
        # Keyed by batch name with per-batch decision counts.
        assert set(dc.keys()) == {"a", "b"}
        for batch_name in ("a", "b"):
            assert set(dc[batch_name].keys()) == {"allow", "warn", "block"}


# ===========================================================================
# D. Group wins counting
# ===========================================================================
class TestGroupWins:
    def test_group_wins_keys_locked(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        wins = out["comparisons"]["a_vs_b"]["group_wins"]
        assert set(wins.keys()) == {"a", "b", "ties"}

    def test_identical_batches_all_ties(self):
        batch = _healthy_batch()
        batches = {"a": batch, "b": batch}
        out = xb_mod.compare_batches(batches)
        wins = out["comparisons"]["a_vs_b"]["group_wins"]
        assert wins["a"] == 0
        assert wins["b"] == 0
        assert wins["ties"] == 3

    def test_healthy_b_wins_all_groups_over_unhealthy_a(self):
        batches = {
            "a": _unhealthy_batch(),
            "b": _healthy_batch(),
        }
        out = xb_mod.compare_batches(batches)
        wins = out["comparisons"]["a_vs_b"]["group_wins"]
        # 3 common groups, b is better in all → b wins all 3.
        assert wins["b"] == 3
        assert wins["a"] == 0
        assert wins["ties"] == 0

    def test_unhealthy_b_loses_to_healthy_a(self):
        batches = {
            "a": _healthy_batch(),
            "b": _unhealthy_batch(),
        }
        out = xb_mod.compare_batches(batches)
        wins = out["comparisons"]["a_vs_b"]["group_wins"]
        assert wins["a"] == 3
        assert wins["b"] == 0


# ===========================================================================
# E. Decision counts per comparison
# ===========================================================================
class TestDecisionCounts:
    def test_decision_counts_restricted_to_common_groups(self):
        batch_a = _batch_payload({
            "g0": _group_payload("allow", 0.8),
            "g1": _group_payload("block", 0.2),
            "g_only_in_a": _group_payload("allow", 0.9),
        })
        batch_b = _batch_payload({
            "g0": _group_payload("warn", 0.6),
            "g1": _group_payload("allow", 0.85),
            "g_only_in_b": _group_payload("block", 0.1),
        })
        batches = {"a": batch_a, "b": batch_b}
        out = xb_mod.compare_batches(batches)
        dc = out["comparisons"]["a_vs_b"]["decision_counts"]
        # Only g0 and g1 are common.
        # A side: {g0: allow, g1: block}
        assert dc["a"] == {"allow": 1, "warn": 0, "block": 1}
        # B side: {g0: warn, g1: allow}
        assert dc["b"] == {"allow": 1, "warn": 1, "block": 0}


# ===========================================================================
# F. Winner logic
# ===========================================================================
class TestWinnerLogic:
    def test_winner_in_locked_vocab(self):
        batches = {"a": _healthy_batch(), "b": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert out["comparisons"]["a_vs_b"]["winner"] in ("a", "b", "tie")

    def test_identical_batches_tie(self):
        batch = _healthy_batch()
        batches = {"a": batch, "b": batch}
        out = xb_mod.compare_batches(batches)
        assert out["comparisons"]["a_vs_b"]["winner"] == "tie"

    def test_healthier_b_wins(self):
        batches = {"a": _unhealthy_batch(), "b": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert out["comparisons"]["a_vs_b"]["winner"] == "b"

    def test_healthier_a_wins(self):
        batches = {"a": _healthy_batch(), "b": _unhealthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert out["comparisons"]["a_vs_b"]["winner"] == "a"

    def test_close_metrics_tie(self):
        # Differ by less than the epsilon threshold (0.05).
        batches = {
            "a": _batch_payload({"g0": _group_payload("allow", 0.80, 0.10, 0)}),
            "b": _batch_payload({"g0": _group_payload("allow", 0.82, 0.10, 0)}),
        }
        out = xb_mod.compare_batches(batches)
        assert out["comparisons"]["a_vs_b"]["winner"] == "tie"


# ===========================================================================
# G. Aggregate deltas
# ===========================================================================
class TestAggregateDeltas:
    def test_mean_health_delta_correct(self):
        batches = {
            "a": _batch_payload({"g0": _group_payload("warn", 0.50)}),
            "b": _batch_payload({"g0": _group_payload("allow", 0.80)}),
        }
        out = xb_mod.compare_batches(batches)
        # Single common group → mean health delta = 0.30.
        assert out["comparisons"]["a_vs_b"]["health_delta"] == pytest.approx(0.30)

    def test_mean_anomaly_delta_correct(self):
        batches = {
            "a": _batch_payload({"g0": _group_payload("warn", 0.5, 0.20, 0)}),
            "b": _batch_payload({"g0": _group_payload("allow", 0.6, 0.10, 0)}),
        }
        out = xb_mod.compare_batches(batches)
        # B anomaly - A anomaly = -0.10.
        assert out["comparisons"]["a_vs_b"]["anomaly_delta"] == pytest.approx(-0.10)

    def test_total_regression_delta_correct(self):
        batches = {
            "a": _batch_payload({
                "g0": _group_payload("warn", 0.5, 0.0, 2),
                "g1": _group_payload("warn", 0.5, 0.0, 1),
            }),
            "b": _batch_payload({
                "g0": _group_payload("warn", 0.5, 0.0, 0),
                "g1": _group_payload("warn", 0.5, 0.0, 0),
            }),
        }
        out = xb_mod.compare_batches(batches)
        # B - A regression delta per group: (0-2) + (0-1) = -3.
        assert out["comparisons"]["a_vs_b"]["regression_count_delta"] == -3


# ===========================================================================
# H. Alpha ordering invariants
# ===========================================================================
class TestOrdering:
    def test_batches_section_keys_sorted(self):
        batches = {
            "zeta":  _healthy_batch(),
            "alpha": _healthy_batch(),
            "mid":   _healthy_batch(),
        }
        out = xb_mod.compare_batches(batches)
        assert list(out["batches"].keys()) == ["alpha", "mid", "zeta"]

    def test_comparison_keys_alpha_sorted_pairs(self):
        batches = {
            "branch_A": _healthy_batch(),
            "branch_B": _healthy_batch(),
        }
        out = xb_mod.compare_batches(batches)
        assert "branch_A_vs_branch_B" in out["comparisons"]
        assert "branch_B_vs_branch_A" not in out["comparisons"]

    def test_no_self_comparison(self):
        batches = {"a": _healthy_batch()}
        out = xb_mod.compare_batches(batches)
        assert out["comparisons"] == {}


# ===========================================================================
# I. Partial-overlap batches
# ===========================================================================
class TestPartialOverlap:
    def test_disjoint_groups_no_wins(self):
        batches = {
            "a": _batch_payload({"only_a": _group_payload("allow", 0.8)}),
            "b": _batch_payload({"only_b": _group_payload("allow", 0.9)}),
        }
        out = xb_mod.compare_batches(batches)
        wins = out["comparisons"]["a_vs_b"]["group_wins"]
        # No common groups → no wins or ties recorded.
        assert wins["a"] == 0
        assert wins["b"] == 0
        assert wins["ties"] == 0

    def test_disjoint_groups_winner_is_tie(self):
        batches = {
            "a": _batch_payload({"only_a": _group_payload("block", 0.1)}),
            "b": _batch_payload({"only_b": _group_payload("allow", 0.95)}),
        }
        out = xb_mod.compare_batches(batches)
        # No common groups means no comparison data → all deltas zero → tie.
        assert out["comparisons"]["a_vs_b"]["winner"] == "tie"

    def test_partial_overlap_uses_common_groups_only(self):
        batch_a = _batch_payload({
            "shared":  _group_payload("warn", 0.5),
            "a_only":  _group_payload("block", 0.1),
        })
        batch_b = _batch_payload({
            "shared":  _group_payload("allow", 0.85),
            "b_only":  _group_payload("allow", 0.9),
        })
        out = xb_mod.compare_batches({"a": batch_a, "b": batch_b})
        # Only "shared" is common; b is healthier on that one.
        wins = out["comparisons"]["a_vs_b"]["group_wins"]
        assert wins["b"] == 1
        assert wins["a"] == 0
        assert wins["ties"] == 0


# ===========================================================================
# J. Empty / single batch
# ===========================================================================
class TestEmptyAndSingle:
    def test_empty_batches_dict_returns_empty_shape(self):
        out = xb_mod.compare_batches({})
        assert out == {"batches": {}, "comparisons": {}}

    def test_single_batch_no_comparisons(self):
        out = xb_mod.compare_batches({"only": _healthy_batch()})
        assert out["comparisons"] == {}
        assert "only" in out["batches"]

    def test_one_empty_one_populated(self):
        batches = {
            "empty":  _batch_payload({}),
            "filled": _healthy_batch(),
        }
        out = xb_mod.compare_batches(batches)
        assert "empty_vs_filled" in out["comparisons"]
        # No common groups → tie verdict.
        assert out["comparisons"]["empty_vs_filled"]["winner"] == "tie"


# ===========================================================================
# K. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        batches = {"a": _mixed_batch(), "b": _mixed_batch()}
        a = xb_mod.compare_batches(batches)
        b = xb_mod.compare_batches(batches)
        assert a == b

    def test_byte_equal_empty(self):
        a = xb_mod.compare_batches({})
        b = xb_mod.compare_batches({})
        assert a == b

    def test_input_order_does_not_change_output(self):
        forward  = {"alpha": _healthy_batch(), "zeta": _healthy_batch()}
        reversed_ = {"zeta": _healthy_batch(), "alpha": _healthy_batch()}
        a = xb_mod.compare_batches(forward)
        b = xb_mod.compare_batches(reversed_)
        assert a == b


# ===========================================================================
# L. Validation
# ===========================================================================
class TestValidation:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="expected a dict"):
            xb_mod.compare_batches("nope")

    def test_list_top_level_raises(self):
        with pytest.raises(ValueError, match="expected a dict"):
            xb_mod.compare_batches([])

    def test_non_string_batch_name_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            xb_mod.compare_batches({123: _healthy_batch()})

    def test_empty_batch_name_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            xb_mod.compare_batches({"": _healthy_batch()})

    def test_non_dict_payload_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            xb_mod.compare_batches({"a": "nope"})

    def test_missing_groups_key_raises(self):
        with pytest.raises(ValueError, match="missing 'groups'"):
            xb_mod.compare_batches({"a": {"comparisons": {}}})

    def test_non_dict_groups_raises(self):
        with pytest.raises(ValueError, match="must be a dict"):
            xb_mod.compare_batches({"a": {"groups": "nope"}})


# ===========================================================================
# M. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(xb_mod.compare_batches)

    def test_winner_epsilon_locked(self):
        assert xb_mod._WINNER_EPSILON == 0.05

    def test_pair_regression_weight_locked(self):
        assert xb_mod._PAIR_REGRESSION_WEIGHT == 0.1


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(xb_mod)

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

    def test_pure_no_persistence_imports(self):
        # Unit 23 is a pure orchestrator over Unit 21 OUTPUTS — it
        # should not touch persistence or downstream Unit 9-22 modules
        # directly.
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "elins_intelligence",
            "load_comparison_result", "save_comparison_result",
        ):
            assert forbidden not in src
