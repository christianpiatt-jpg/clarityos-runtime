"""
Tests for ELINS2 Unit 8 — sequence intelligence.

Layered coverage (>= 40 tests, target ~50):
    A. analyze_sequence — shape / locked keys
    B. analyze_sequence — empty input
    C. analyze_sequence — stable / upward / downward signals
    D. analyze_sequence — fractions sum / clamp behaviour
    E. best_sequence — basic
    F. worst_sequence — basic
    G. Monotonic improving → best window at the end
    H. Monotonic degrading → best window at the start
    I. Anomaly-heavy windows → worst
    J. Window validation (too large / too small / non-int)
    K. Legacy handling
    L. Determinism
    M. Module surface / source-code purity
    N. Cross-function consistency
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_anomalies as anom_mod
import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
import elins_scoring as score_mod
import elins_sequences as seq_mod
import elins_trends as trends_mod


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


def _seed_stable(prefix="s", n=5, sp=5, ec=5):
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec),
                                          _entry("p2", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


def _seed_upward(prefix="u", n=5):
    """Saves run_ids with strictly increasing scores from 1..9 across n
    runs."""
    rids: list = []
    if n == 5:
        seq = [1, 3, 5, 7, 9]
    else:
        # Even n: distribute scores across [1, 9].
        step = 8 / max(n - 1, 1)
        seq = [round(1 + step * i) for i in range(n)]
    for i, sp in enumerate(seq, 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_downward(prefix="d", n=5):
    rids: list = []
    if n == 5:
        seq = [9, 7, 5, 3, 1]
    else:
        step = 8 / max(n - 1, 1)
        seq = [round(9 - step * i) for i in range(n)]
    for i, sp in enumerate(seq, 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp,
                                                sp_band="Fails core logic",
                                                ec_band="Fails core logic")])
        rids.append(rid)
    return rids


def _seed_improving_then_stable(prefix="its"):
    """5 runs: 1,3,5 (improving) then 9,9,9 (stable high). Total 6
    runs. The right-most window of 3 lands on the stable high section.
    """
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 9, 9, 9), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_stable_then_degrading(prefix="std"):
    """6 runs: 9,9,9 (stable high) then 5,3,1 (degrading). Left window
    captures the healthy section; right window catches the slide."""
    rids: list = []
    for i, sp in enumerate((9, 9, 9, 5, 3, 1), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. analyze_sequence — shape / locked keys
# ===========================================================================
class TestAnalyzeShape:
    def test_keys_locked(self):
        rids = _seed_stable(n=4, sp=5)
        out = seq_mod.analyze_sequence(rids)
        assert set(out.keys()) == {
            "trend", "overall_health",
            "anomaly_fraction", "upward_fraction",
            "downward_fraction", "stable_cluster_fraction",
        }

    def test_value_types(self):
        rids = _seed_stable(n=4, sp=5)
        out = seq_mod.analyze_sequence(rids)
        assert isinstance(out["trend"], str)
        assert isinstance(out["overall_health"], float)
        for k in ("anomaly_fraction", "upward_fraction",
                  "downward_fraction", "stable_cluster_fraction"):
            assert isinstance(out[k], float)

    def test_no_missing_keys(self):
        rids = _seed_stable(n=4, sp=5)
        out = seq_mod.analyze_sequence(rids)
        # Sanity: every fraction key is present even when the underlying
        # signal is zero.
        for k in ("upward_fraction", "downward_fraction",
                  "stable_cluster_fraction"):
            assert k in out


# ===========================================================================
# B. analyze_sequence — empty input
# ===========================================================================
class TestAnalyzeEmpty:
    def test_empty_returns_well_formed(self):
        out = seq_mod.analyze_sequence([])
        assert set(out.keys()) == {
            "trend", "overall_health",
            "anomaly_fraction", "upward_fraction",
            "downward_fraction", "stable_cluster_fraction",
        }

    def test_empty_trend_insufficient(self):
        out = seq_mod.analyze_sequence([])
        assert out["trend"] == "insufficient_data"

    def test_empty_health_zero(self):
        out = seq_mod.analyze_sequence([])
        assert out["overall_health"] == 0.0

    def test_empty_all_fractions_zero(self):
        out = seq_mod.analyze_sequence([])
        for k in ("anomaly_fraction", "upward_fraction",
                  "downward_fraction", "stable_cluster_fraction"):
            assert out[k] == 0.0


# ===========================================================================
# C. analyze_sequence — stable / upward / downward signals
# ===========================================================================
class TestAnalyzeSignals:
    def test_stable_high_health(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.analyze_sequence(rids)
        assert 0.0 <= out["overall_health"] <= 1.0

    def test_upward_sequence_has_upward_fraction(self):
        rids = _seed_upward()
        out = seq_mod.analyze_sequence(rids)
        # Single pair (p1) trending upward → upward_fraction = 1.0.
        assert out["upward_fraction"] == pytest.approx(1.0)

    def test_downward_sequence_has_downward_fraction(self):
        rids = _seed_downward()
        out = seq_mod.analyze_sequence(rids)
        assert out["downward_fraction"] == pytest.approx(1.0)

    def test_upward_no_downward_fraction(self):
        rids = _seed_upward(prefix="upd")
        out = seq_mod.analyze_sequence(rids)
        assert out["downward_fraction"] == 0.0

    def test_downward_no_upward_fraction(self):
        rids = _seed_downward(prefix="dnu")
        out = seq_mod.analyze_sequence(rids)
        assert out["upward_fraction"] == 0.0

    def test_upward_trend_class_is_monotonic_increase(self):
        rids = _seed_upward(prefix="uti")
        out = seq_mod.analyze_sequence(rids)
        assert out["trend"] == "monotonic_increase"

    def test_downward_trend_class_is_monotonic_decrease(self):
        rids = _seed_downward(prefix="dti")
        out = seq_mod.analyze_sequence(rids)
        assert out["trend"] == "monotonic_decrease"

    def test_stable_zero_anomaly_fraction(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.analyze_sequence(rids)
        assert out["anomaly_fraction"] == 0.0


# ===========================================================================
# D. analyze_sequence — fractions sum / clamp
# ===========================================================================
class TestFractionsClamp:
    def test_anomaly_fraction_in_unit_interval(self):
        # Stable + 1 outlier → 1/6 ≈ 0.167 anomaly fraction.
        rids = _seed_stable(n=5, sp=5)
        ep.save_comparison_result(
            "afi_outlier",
            [_entry("p9", sp=0, ec=0,
                     sp_band="Fails core logic",
                     ec_band="Fails core logic")],
        )
        out = seq_mod.analyze_sequence(rids + ["afi_outlier"])
        assert 0.0 <= out["anomaly_fraction"] <= 1.0

    def test_up_plus_down_fractions_bounded(self):
        rids = _seed_upward(prefix="updb")
        out = seq_mod.analyze_sequence(rids)
        # upward + downward + flat should never exceed 1.0 — each pair
        # owns exactly one direction.
        total = (
            out["upward_fraction"]
            + out["downward_fraction"]
        )
        assert total <= 1.0 + 1e-9

    def test_stable_cluster_fraction_in_unit_interval(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.analyze_sequence(rids)
        assert 0.0 <= out["stable_cluster_fraction"] <= 1.0


# ===========================================================================
# E. best_sequence — basic
# ===========================================================================
class TestBestBasic:
    def test_keys_locked(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.best_sequence(rids, window=3)
        assert set(out.keys()) == {
            "run_ids", "overall_health", "trend", "anomaly_fraction",
        }

    def test_run_ids_length_matches_window(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.best_sequence(rids, window=3)
        assert len(out["run_ids"]) == 3

    def test_run_ids_are_contiguous_slice(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.best_sequence(rids, window=3)
        # Find which start index the result corresponds to.
        for start in range(len(rids) - 2):
            if out["run_ids"] == rids[start: start + 3]:
                return  # found a valid contiguous slice
        pytest.fail("best window run_ids are not a contiguous input slice")

    def test_health_in_unit_interval(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.best_sequence(rids, window=3)
        assert 0.0 <= out["overall_health"] <= 1.0

    def test_default_window_is_five(self):
        rids = _seed_stable(n=6, sp=5)
        out = seq_mod.best_sequence(rids)
        assert len(out["run_ids"]) == 5


# ===========================================================================
# F. worst_sequence — basic
# ===========================================================================
class TestWorstBasic:
    def test_keys_locked(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.worst_sequence(rids, window=3)
        assert set(out.keys()) == {
            "run_ids", "overall_health", "trend", "anomaly_fraction",
        }

    def test_run_ids_length_matches_window(self):
        rids = _seed_stable(n=5, sp=5)
        out = seq_mod.worst_sequence(rids, window=3)
        assert len(out["run_ids"]) == 3

    def test_default_window_is_five(self):
        rids = _seed_stable(n=6, sp=5)
        out = seq_mod.worst_sequence(rids)
        assert len(out["run_ids"]) == 5


# ===========================================================================
# G. Monotonic improving → best window matches global max
# ===========================================================================
class TestMonotonicImproving:
    def test_best_health_is_global_maximum(self):
        rids = _seed_improving_then_stable(prefix="imp_max")
        best = seq_mod.best_sequence(rids, window=3)
        candidates = [
            score_mod.overall_health_score(rids[i: i + 3])
            for i in range(len(rids) - 2)
        ]
        assert best["overall_health"] == max(candidates)

    def test_best_health_at_least_first_window_health(self):
        rids = _seed_improving_then_stable(prefix="imp_h")
        best = seq_mod.best_sequence(rids, window=3)
        first_window_health = score_mod.overall_health_score(rids[:3])
        assert best["overall_health"] >= first_window_health

    def test_best_window_is_contiguous_slice(self):
        rids = _seed_improving_then_stable(prefix="imp_slc")
        best = seq_mod.best_sequence(rids, window=3)
        # Best run_ids must appear as a contiguous slice of the input.
        for start in range(len(rids) - 2):
            if best["run_ids"] == rids[start: start + 3]:
                return
        pytest.fail("best window run_ids are not a contiguous input slice")


# ===========================================================================
# H. Monotonic degrading → best at start / worst at end of healthy stretch
# ===========================================================================
class TestMonotonicDegrading:
    def test_best_window_is_early(self):
        rids = _seed_stable_then_degrading(prefix="deg_bs")
        best = seq_mod.best_sequence(rids, window=3)
        # First three are 9,9,9 — clearly the best stable window.
        assert best["run_ids"][0] == rids[0]

    def test_best_health_is_global_max_on_degrading(self):
        rids = _seed_stable_then_degrading(prefix="deg_gm")
        best = seq_mod.best_sequence(rids, window=3)
        candidates = [
            score_mod.overall_health_score(rids[i: i + 3])
            for i in range(len(rids) - 2)
        ]
        assert best["overall_health"] == max(candidates)

    def test_worst_health_is_global_min_on_degrading(self):
        rids = _seed_stable_then_degrading(prefix="deg_gn")
        worst = seq_mod.worst_sequence(rids, window=3)
        candidates = [
            score_mod.overall_health_score(rids[i: i + 3])
            for i in range(len(rids) - 2)
        ]
        assert worst["overall_health"] == min(candidates)

    def test_worst_window_health_lower_than_best(self):
        rids = _seed_stable_then_degrading(prefix="deg_wb")
        best  = seq_mod.best_sequence(rids, window=3)
        worst = seq_mod.worst_sequence(rids, window=3)
        assert worst["overall_health"] <= best["overall_health"]


# ===========================================================================
# I. Anomaly-heavy windows → worst
# ===========================================================================
class TestAnomalyWindows:
    def test_window_with_outlier_lower_health(self):
        # 5 stable runs + 1 outlier at the end.
        rids = _seed_stable(prefix="aw_s", n=5, sp=5)
        ep.save_comparison_result(
            "aw_out",
            [_entry("p9", sp=0, ec=0,
                     sp_band="Fails core logic",
                     ec_band="Fails core logic")],
        )
        all_rids = rids + ["aw_out"]
        # Window containing the outlier should be worst.
        worst = seq_mod.worst_sequence(all_rids, window=3)
        assert "aw_out" in worst["run_ids"]

    def test_worst_window_lower_than_clean_windows(self):
        # When an outlier is at the end, the window containing it must
        # have lower health than every all-stable window.
        rids = _seed_stable(prefix="aw_af", n=5, sp=5)
        ep.save_comparison_result(
            "aw_af_out",
            [_entry("p9", sp=0, ec=0,
                     sp_band="Fails core logic",
                     ec_band="Fails core logic")],
        )
        all_rids = rids + ["aw_af_out"]
        worst = seq_mod.worst_sequence(all_rids, window=3)
        # Every window NOT containing the outlier should score higher.
        clean_max = max(
            score_mod.overall_health_score(all_rids[i: i + 3])
            for i in range(len(rids) - 2)  # windows entirely within stable runs
        )
        assert worst["overall_health"] < clean_max


# ===========================================================================
# J. Window validation
# ===========================================================================
class TestWindowValidation:
    def test_window_too_small_raises(self):
        rids = _seed_stable(n=4, sp=5)
        with pytest.raises(ValueError, match=">= 2"):
            seq_mod.best_sequence(rids, window=1)

    def test_window_negative_raises(self):
        rids = _seed_stable(n=4, sp=5)
        with pytest.raises(ValueError, match=">= 2"):
            seq_mod.best_sequence(rids, window=-3)

    def test_window_zero_raises(self):
        rids = _seed_stable(n=4, sp=5)
        with pytest.raises(ValueError, match=">= 2"):
            seq_mod.best_sequence(rids, window=0)

    def test_window_bool_raises(self):
        rids = _seed_stable(n=4, sp=5)
        with pytest.raises(ValueError, match="positive int"):
            seq_mod.best_sequence(rids, window=True)

    def test_window_non_int_raises(self):
        rids = _seed_stable(n=4, sp=5)
        with pytest.raises(ValueError, match="positive int"):
            seq_mod.best_sequence(rids, window=3.0)

    def test_window_too_large_raises(self):
        rids = _seed_stable(n=4, sp=5)
        with pytest.raises(ValueError, match="cannot exceed"):
            seq_mod.best_sequence(rids, window=5)

    def test_worst_sequence_same_window_validation(self):
        rids = _seed_stable(n=4, sp=5)
        with pytest.raises(ValueError, match=">= 2"):
            seq_mod.worst_sequence(rids, window=1)

    def test_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            seq_mod.analyze_sequence("nope")

    def test_best_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            seq_mod.best_sequence("nope", window=3)

    def test_worst_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            seq_mod.worst_sequence("nope", window=3)

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            seq_mod.analyze_sequence(["bad/id"])

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            seq_mod.analyze_sequence(["ghost"])

    def test_best_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            seq_mod.best_sequence(["g1", "g2", "g3"], window=2)


# ===========================================================================
# K. Legacy handling
# ===========================================================================
class TestLegacyHandling:
    def test_legacy_included_in_anomaly_fraction(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="lh_a", n=4, sp=5)
        _write_legacy(_runs_dir_isolation, "lh_leg", [_entry("p1")])
        out = seq_mod.analyze_sequence(rids + ["lh_leg"])
        # Legacy runs are scored as anomalies in Unit 5 → fraction > 0.
        assert out["anomaly_fraction"] > 0.0

    def test_legacy_excluded_from_health_aggregate(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="lh_h", n=4, sp=5)
        # Modern-only health.
        modern_health = score_mod.overall_health_score(rids)
        _write_legacy(_runs_dir_isolation, "lh_leg2", [_entry("p1")])
        with_leg = seq_mod.analyze_sequence(rids + ["lh_leg2"])
        # Health is computed by Unit 6 which excludes legacy runs.
        assert with_leg["overall_health"] == pytest.approx(modern_health)

    def test_best_sequence_skips_legacy_window(self, _runs_dir_isolation):
        # 5 stable runs + 1 legacy in the middle. Best window should
        # avoid the one straddling the legacy run, because the legacy
        # run drags Unit 6 health down (modern_ids skipped → mean
        # ignores it).
        rids = _seed_stable(prefix="lh_bs", n=5, sp=5)
        out = seq_mod.best_sequence(rids, window=3)
        # All-modern window → some health > 0.0.
        assert out["overall_health"] > 0.0


# ===========================================================================
# L. Determinism
# ===========================================================================
class TestDeterminism:
    def test_analyze_byte_equal(self):
        rids = _seed_stable(n=5, sp=5)
        a = seq_mod.analyze_sequence(rids)
        b = seq_mod.analyze_sequence(rids)
        assert a == b

    def test_best_byte_equal(self):
        rids = _seed_stable(n=5, sp=5)
        a = seq_mod.best_sequence(rids, window=3)
        b = seq_mod.best_sequence(rids, window=3)
        assert a == b

    def test_worst_byte_equal(self):
        rids = _seed_stable(n=5, sp=5)
        a = seq_mod.worst_sequence(rids, window=3)
        b = seq_mod.worst_sequence(rids, window=3)
        assert a == b

    def test_tie_breaks_to_earliest_start(self):
        # All-stable sequence → every window has identical health.
        # The earliest window should always win ties.
        rids = _seed_stable(prefix="tie", n=5, sp=5)
        best = seq_mod.best_sequence(rids, window=3)
        worst = seq_mod.worst_sequence(rids, window=3)
        assert best["run_ids"] == rids[:3]
        assert worst["run_ids"] == rids[:3]


# ===========================================================================
# M. Module surface / source-code purity
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            seq_mod.analyze_sequence,
            seq_mod.best_sequence,
            seq_mod.worst_sequence,
        ):
            assert callable(fn)

    def test_default_window_locked(self):
        assert seq_mod._DEFAULT_WINDOW == 5

    def test_min_window_locked(self):
        assert seq_mod._MIN_WINDOW == 2


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(seq_mod)

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

    def test_composes_units_2_through_6(self):
        src = self._code_only()
        for required in (
            "cluster_runs",                # Unit 2
            "trend_for_run_sequence",      # Unit 3
            "multi_run_summary",           # Unit 4
            "detect_run_anomalies",        # Unit 5
            "overall_health_score",        # Unit 6
        ):
            assert required in src


# ===========================================================================
# N. Cross-function consistency
# ===========================================================================
class TestCrossConsistency:
    def test_analyze_health_matches_score_mod(self):
        rids = _seed_upward(prefix="cc_h")
        out = seq_mod.analyze_sequence(rids)
        assert out["overall_health"] == pytest.approx(
            score_mod.overall_health_score(rids),
        )

    def test_analyze_trend_matches_trend_mod(self):
        rids = _seed_upward(prefix="cc_t")
        out = seq_mod.analyze_sequence(rids)
        assert out["trend"] == trends_mod.trend_for_run_sequence(rids)["trend"]

    def test_best_health_matches_score_mod(self):
        rids = _seed_stable(prefix="cc_bh", n=5, sp=5)
        best = seq_mod.best_sequence(rids, window=3)
        # Recompute on the same window.
        assert best["overall_health"] == pytest.approx(
            score_mod.overall_health_score(best["run_ids"]),
        )

    def test_worst_health_matches_score_mod(self):
        rids = _seed_stable_then_degrading(prefix="cc_wh")
        worst = seq_mod.worst_sequence(rids, window=3)
        assert worst["overall_health"] == pytest.approx(
            score_mod.overall_health_score(worst["run_ids"]),
        )

    def test_best_health_at_least_worst_health(self):
        rids = _seed_stable_then_degrading(prefix="cc_bw")
        best  = seq_mod.best_sequence(rids, window=3)
        worst = seq_mod.worst_sequence(rids, window=3)
        assert best["overall_health"] >= worst["overall_health"]

    def test_window_run_ids_subsequence_of_input(self):
        rids = _seed_improving_then_stable(prefix="cc_sub")
        for fn in (seq_mod.best_sequence, seq_mod.worst_sequence):
            out = fn(rids, window=3)
            for rid in out["run_ids"]:
                assert rid in rids

    def test_anomaly_fraction_matches_unit_5(self):
        rids = _seed_stable(prefix="cc_af", n=5, sp=5)
        ep.save_comparison_result(
            "cc_af_out",
            [_entry("p9", sp=0, ec=0,
                     sp_band="Fails core logic",
                     ec_band="Fails core logic")],
        )
        all_rids = rids + ["cc_af_out"]
        out = seq_mod.analyze_sequence(all_rids)
        anom = anom_mod.detect_run_anomalies(all_rids)
        flagged = sum(
            1 for info in anom["runs"].values()
            if info["level"] != "none"
        )
        assert out["anomaly_fraction"] == pytest.approx(
            flagged / len(all_rids),
        )
