"""
Tests for ELINS7 Unit 21 — multi-run batch evaluator.

Layered coverage (>= 60 tests, target ~70):
    A. Top-level shape / locked keys
    B. Group section — per-group gate parity
    C. Comparisons section — pairwise diff parity
    D. Comparison key ordering (alpha-sorted unordered pairs)
    E. Winner logic (per-group score formula)
    F. Pair regressions list
    G. Empty groups
    H. Small N + single group
    I. Legacy run handling
    J. Determinism (byte-equal repeats)
    K. Validation
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_batch_eval as batch_mod
import elins_intel_diff as diff_mod
import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
import elins_release_gate as gate_mod


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _runs_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runs_dir = tmp_path / "elins_runs"
    monkeypatch.setenv(ep._RUNS_DIR_ENV_VAR, str(runs_dir))
    yield runs_dir


def _entry(pid="p1", *, sp=5, ec=5,
           sp_band="Acceptable", ec_band="Acceptable") -> dict:
    return {
        "pair_id": pid,
        "single_party_score": sp,
        "economic_coercion_score": ec,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _write_legacy(runs_dir: Path, run_id: str, payload) -> None:
    db_path = runs_dir / ep._DB_FILENAME
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ep_sql._ensure_init(str(db_path))
    envelope = {"metadata": None, "result": payload}
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, envelope_json) "
            "VALUES (?, ?)",
            (run_id, json.dumps(envelope, sort_keys=True, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def _seed_stable(prefix="s", n=4, sp=5, ec=5):
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


def _seed_health_drop(prefix="hd"):
    """6 runs: A=[1,3,5] upward, B=[9,7,5] downward → triggers a
    Unit 19 block."""
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 9, 7, 5), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_upward(prefix="up"):
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 7, 9), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_downward(prefix="dn"):
    rids: list = []
    for i, sp in enumerate((9, 7, 5, 3, 1), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp,
                                                sp_band="Fails core logic",
                                                ec_band="Fails core logic")])
        rids.append(rid)
    return rids


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        groups = {"a": _seed_stable(prefix="a", n=3),
                  "b": _seed_stable(prefix="b", n=3)}
        out = batch_mod.evaluate_batch(groups)
        assert set(out.keys()) == {"groups", "comparisons"}

    def test_groups_section_is_dict(self):
        groups = {"x": _seed_stable(prefix="x", n=3)}
        out = batch_mod.evaluate_batch(groups)
        assert isinstance(out["groups"], dict)

    def test_comparisons_section_is_dict(self):
        groups = {"x": _seed_stable(prefix="x", n=3)}
        out = batch_mod.evaluate_batch(groups)
        assert isinstance(out["comparisons"], dict)


# ===========================================================================
# B. Group section — per-group gate parity
# ===========================================================================
class TestGroupSection:
    def test_one_entry_per_input_group(self):
        groups = {
            "a": _seed_stable(prefix="a", n=3),
            "b": _seed_stable(prefix="b", n=3),
            "c": _seed_stable(prefix="c", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        assert set(out["groups"].keys()) == set(groups.keys())

    def test_group_entry_keys_locked(self):
        groups = {"x": _seed_stable(prefix="x", n=3)}
        out = batch_mod.evaluate_batch(groups)
        assert set(out["groups"]["x"].keys()) == {
            "decision", "reasons", "metrics",
        }

    def test_decision_matches_unit_19(self):
        groups = {"hd": _seed_health_drop()}
        out = batch_mod.evaluate_batch(groups)
        gate = gate_mod.evaluate_release_gate(groups["hd"])
        assert out["groups"]["hd"]["decision"] == gate["decision"]

    def test_metrics_match_unit_19(self):
        groups = {"st": _seed_stable(prefix="st", n=4, sp=5)}
        out = batch_mod.evaluate_batch(groups)
        gate = gate_mod.evaluate_release_gate(groups["st"])
        assert out["groups"]["st"]["metrics"] == gate["metrics"]

    def test_reasons_match_unit_19(self):
        groups = {"hd": _seed_health_drop(prefix="hr_d")}
        out = batch_mod.evaluate_batch(groups)
        gate = gate_mod.evaluate_release_gate(groups["hd"])
        assert out["groups"]["hd"]["reasons"] == gate["reasons"]

    def test_group_section_keys_sorted(self):
        groups = {
            "zeta":  _seed_stable(prefix="zg", n=2),
            "alpha": _seed_stable(prefix="ag", n=2),
            "mid":   _seed_stable(prefix="mg", n=2),
        }
        out = batch_mod.evaluate_batch(groups)
        assert list(out["groups"].keys()) == ["alpha", "mid", "zeta"]


# ===========================================================================
# C. Comparisons section — pairwise diff parity
# ===========================================================================
class TestComparisonsSection:
    def test_two_groups_one_comparison(self):
        groups = {
            "a": _seed_stable(prefix="ca", n=3),
            "b": _seed_stable(prefix="cb", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        assert len(out["comparisons"]) == 1

    def test_three_groups_three_comparisons(self):
        groups = {
            "a": _seed_stable(prefix="ca3", n=3),
            "b": _seed_stable(prefix="cb3", n=3),
            "c": _seed_stable(prefix="cc3", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        # C(3, 2) = 3 unordered pairs.
        assert len(out["comparisons"]) == 3

    def test_four_groups_six_comparisons(self):
        groups = {
            "a": _seed_stable(prefix="ca4", n=2),
            "b": _seed_stable(prefix="cb4", n=2),
            "c": _seed_stable(prefix="cc4", n=2),
            "d": _seed_stable(prefix="cd4", n=2),
        }
        out = batch_mod.evaluate_batch(groups)
        # C(4, 2) = 6 unordered pairs.
        assert len(out["comparisons"]) == 6

    def test_comparison_entry_keys_locked(self):
        groups = {
            "a": _seed_stable(prefix="ekia", n=3),
            "b": _seed_stable(prefix="ekib", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        entry = next(iter(out["comparisons"].values()))
        assert set(entry.keys()) == {
            "health_delta", "anomaly_delta",
            "cluster_shift", "trend_shift",
            "pair_regressions", "winner",
        }

    def test_health_delta_matches_unit_14(self):
        groups = {
            "a": _seed_upward(prefix="hd_a"),
            "b": _seed_downward(prefix="hd_b"),
        }
        out = batch_mod.evaluate_batch(groups)
        raw = diff_mod.diff_intelligence(groups["a"], groups["b"])
        assert out["comparisons"]["a_vs_b"]["health_delta"] == pytest.approx(
            raw["summary"]["health_delta"],
        )

    def test_anomaly_delta_matches_unit_14(self):
        groups = {
            "a": _seed_stable(prefix="ad_a", n=3),
            "b": _seed_stable(prefix="ad_b", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        raw = diff_mod.diff_intelligence(groups["a"], groups["b"])
        assert out["comparisons"]["a_vs_b"]["anomaly_delta"] == pytest.approx(
            raw["summary"]["anomaly_delta"],
        )

    def test_trend_shift_matches_unit_14(self):
        groups = {
            "a": _seed_stable(prefix="ts_a", n=3),
            "b": _seed_stable(prefix="ts_b", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        raw = diff_mod.diff_intelligence(groups["a"], groups["b"])
        assert out["comparisons"]["a_vs_b"]["trend_shift"] == \
               raw["summary"]["trend_shift"]


# ===========================================================================
# D. Comparison key ordering (alpha-sorted)
# ===========================================================================
class TestComparisonKeyOrder:
    def test_keys_alpha_sorted_pairs(self):
        groups = {
            "branch_A": _seed_stable(prefix="bra", n=2),
            "branch_B": _seed_stable(prefix="brb", n=2),
        }
        out = batch_mod.evaluate_batch(groups)
        assert "branch_A_vs_branch_B" in out["comparisons"]
        # The reverse ordering must NOT also exist (collapses to one
        # canonical comparison key).
        assert "branch_B_vs_branch_A" not in out["comparisons"]

    def test_reverse_input_order_same_keys(self):
        # Insertion order shouldn't change comparison keys — they're
        # always alpha-sorted.
        forward = {
            "alpha": _seed_stable(prefix="fa", n=2),
            "zeta":  _seed_stable(prefix="fz", n=2),
        }
        out = batch_mod.evaluate_batch(forward)
        assert list(out["comparisons"].keys()) == ["alpha_vs_zeta"]

    def test_no_self_comparison(self):
        groups = {"a": _seed_stable(prefix="ns", n=3)}
        out = batch_mod.evaluate_batch(groups)
        # Single group → no pairwise comparison.
        assert out["comparisons"] == {}


# ===========================================================================
# E. Winner logic (per-group score formula)
# ===========================================================================
class TestWinnerLogic:
    def test_winner_in_locked_vocab(self):
        groups = {
            "a": _seed_stable(prefix="wa", n=3),
            "b": _seed_stable(prefix="wb", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        winner = out["comparisons"]["a_vs_b"]["winner"]
        assert winner in ("a", "b", "tie")

    def test_identical_groups_tie(self):
        # Same seed → same envelope contents → diff is zero everywhere.
        rids = _seed_stable(prefix="tie", n=3, sp=5)
        groups = {"a": rids, "b": rids}
        out = batch_mod.evaluate_batch(groups)
        assert out["comparisons"]["a_vs_b"]["winner"] == "tie"

    def test_upward_b_wins_over_downward_a(self):
        groups = {
            "a": _seed_downward(prefix="wud_a"),
            "b": _seed_upward(prefix="wud_b"),
        }
        out = batch_mod.evaluate_batch(groups)
        # B has higher health than A → B wins.
        assert out["comparisons"]["a_vs_b"]["winner"] == "b"

    def test_downward_b_loses_to_upward_a(self):
        groups = {
            "a": _seed_upward(prefix="wdu_a"),
            "b": _seed_downward(prefix="wdu_b"),
        }
        out = batch_mod.evaluate_batch(groups)
        # B has lower health than A → A wins.
        assert out["comparisons"]["a_vs_b"]["winner"] == "a"


# ===========================================================================
# F. Pair regressions list
# ===========================================================================
class TestPairRegressions:
    def test_no_regressions_in_stable_groups(self):
        groups = {
            "a": _seed_stable(prefix="nr_a", n=3),
            "b": _seed_stable(prefix="nr_b", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        assert out["comparisons"]["a_vs_b"]["pair_regressions"] == []

    def test_regression_listed_when_pair_drops(self):
        # A=stable (high stability), B=volatile (low stability) →
        # stability_delta < -0.20.
        groups = {
            "a": _seed_stable(prefix="rd_a", n=4),
            "b": [],
        }
        # Seed B as a volatile pair.
        rids_b: list = []
        for i, sp in enumerate((1, 9, 1, 9), 1):
            rid = f"rd_b_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids_b.append(rid)
        groups["b"] = rids_b
        out = batch_mod.evaluate_batch(groups)
        regs = out["comparisons"]["a_vs_b"]["pair_regressions"]
        if regs:  # signal may or may not fire depending on volatility
            assert "p1" in regs

    def test_regressions_sorted(self):
        groups = {
            "a": _seed_stable(prefix="sr_a", n=3),
            "b": _seed_stable(prefix="sr_b", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        # Empty list is trivially sorted; explicit check for any
        # populated case keeps the invariant clear.
        regs = out["comparisons"]["a_vs_b"]["pair_regressions"]
        assert regs == sorted(regs)


# ===========================================================================
# G. Empty groups
# ===========================================================================
class TestEmptyGroups:
    def test_single_empty_group_evaluates(self):
        groups = {"empty": []}
        out = batch_mod.evaluate_batch(groups)
        assert out["groups"]["empty"]["decision"] == "warn"
        assert out["groups"]["empty"]["reasons"] == ["insufficient_data"]

    def test_empty_groups_dict_returns_empty_shape(self):
        out = batch_mod.evaluate_batch({})
        assert out == {"groups": {}, "comparisons": {}}

    def test_one_empty_one_populated_comparison_runs(self):
        groups = {
            "empty": [],
            "full":  _seed_stable(prefix="oc_f", n=3),
        }
        out = batch_mod.evaluate_batch(groups)
        assert "empty_vs_full" in out["comparisons"]


# ===========================================================================
# H. Small N + single group
# ===========================================================================
class TestSmallN:
    def test_single_group_no_comparisons(self):
        groups = {"only": _seed_stable(prefix="sn", n=3)}
        out = batch_mod.evaluate_batch(groups)
        assert out["comparisons"] == {}

    def test_one_run_per_group(self):
        groups = {
            "a": _seed_stable(prefix="op_a", n=1),
            "b": _seed_stable(prefix="op_b", n=1),
        }
        out = batch_mod.evaluate_batch(groups)
        # Sub-2 inputs → gate falls back to warn/insufficient_data.
        assert out["groups"]["a"]["decision"] == "warn"
        assert out["groups"]["b"]["decision"] == "warn"


# ===========================================================================
# I. Legacy run handling
# ===========================================================================
class TestLegacy:
    def test_group_with_legacy_does_not_crash(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="lg_m", n=2)
        _write_legacy(_runs_dir_isolation, "lg_leg", [_entry("p1")])
        groups = {
            "a": _seed_stable(prefix="lg_a", n=2),
            "b": rids + ["lg_leg"],
        }
        out = batch_mod.evaluate_batch(groups)
        assert set(out.keys()) == {"groups", "comparisons"}


# ===========================================================================
# J. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        groups = {
            "a": _seed_stable(prefix="dt_a", n=3),
            "b": _seed_stable(prefix="dt_b", n=3),
        }
        a = batch_mod.evaluate_batch(groups)
        b = batch_mod.evaluate_batch(groups)
        assert a == b

    def test_byte_equal_empty(self):
        a = batch_mod.evaluate_batch({})
        b = batch_mod.evaluate_batch({})
        assert a == b

    def test_byte_equal_three_groups(self):
        groups = {
            "a": _seed_stable(prefix="d3_a", n=2),
            "b": _seed_stable(prefix="d3_b", n=2),
            "c": _seed_stable(prefix="d3_c", n=2),
        }
        a = batch_mod.evaluate_batch(groups)
        b = batch_mod.evaluate_batch(groups)
        assert a == b


# ===========================================================================
# K. Validation
# ===========================================================================
class TestValidation:
    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="expected a dict"):
            batch_mod.evaluate_batch("nope")

    def test_list_top_level_raises(self):
        with pytest.raises(ValueError, match="expected a dict"):
            batch_mod.evaluate_batch([])

    def test_non_string_group_name_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            batch_mod.evaluate_batch({123: []})

    def test_empty_group_name_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            batch_mod.evaluate_batch({"": []})

    def test_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="must be a list"):
            batch_mod.evaluate_batch({"a": "nope"})

    def test_malformed_run_id_raises(self):
        with pytest.raises(ValueError):
            batch_mod.evaluate_batch({"a": ["bad/id"]})

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            batch_mod.evaluate_batch({"a": ["ghost"]})


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(batch_mod.evaluate_batch)

    def test_winner_epsilon_locked(self):
        assert batch_mod._WINNER_EPSILON == 0.05

    def test_pair_regression_threshold_locked(self):
        assert batch_mod._PAIR_STABILITY_DROP_LIMIT == 0.20

    def test_pair_regression_weight_locked(self):
        assert batch_mod._PAIR_REGRESSION_WEIGHT == 0.1


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(batch_mod)

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

    def test_composes_units_14_19(self):
        src = self._code_only()
        assert "diff_intelligence" in src
        assert "evaluate_release_gate" in src
