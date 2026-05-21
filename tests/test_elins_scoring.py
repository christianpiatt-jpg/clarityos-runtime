"""
Tests for ELINS2 Unit 6 — multi-run scoring.

Layered coverage (>= 40 tests, target ~50):
    A. Per-run scores — stable / upward / downward
    B. Per-pair scores — composite math
    C. Overall health — aggregation + bonuses
    D. Anomaly penalty pass-through
    E. Legacy handling
    F. Validation
    G. Determinism + clamping
    H. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
import elins_scoring as score_mod


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _runs_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runs_dir = tmp_path / "elins_runs"
    monkeypatch.setenv(ep._RUNS_DIR_ENV_VAR, str(runs_dir))
    yield runs_dir


class _StubDT:
    def __init__(self, iso_values):
        self._iter = iter(iso_values)

    def now(self, tz=None):
        v = next(self._iter)

        class _T:
            def __init__(self, iso): self._iso = iso
            def isoformat(self): return self._iso
        return _T(v)


@pytest.fixture
def fixed_clock(monkeypatch):
    def _install(values):
        monkeypatch.setattr(ep_sql, "datetime", _StubDT(list(values)))
    return _install


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


def _seed_stable(prefix="s", n=3, fixed_clock=None):
    fixed_clock([f"2024-01-{i:02d}T10:00:00+00:00" for i in range(1, n + 1)])
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i}"
        ep.save_comparison_result(rid,
                                   [_entry("p1", sp=5, ec=5),
                                    _entry("p2", sp=5, ec=5)])
        rids.append(rid)
    return rids


def _seed_upward(prefix="u", fixed_clock=None):
    fixed_clock([f"2024-01-{i:02d}T10:00:00+00:00" for i in range(1, 4)])
    rids: list = []
    for i, sp in enumerate((1, 5, 9), 1):
        rid = f"{prefix}_{i}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_downward(prefix="d", fixed_clock=None):
    fixed_clock([f"2024-01-{i:02d}T10:00:00+00:00" for i in range(1, 4)])
    rids: list = []
    for i, sp in enumerate((9, 5, 1), 1):
        rid = f"{prefix}_{i}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. Per-run scores — stable / upward / downward
# ===========================================================================
class TestRunScoresStable:
    def test_top_level_key(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        assert set(out.keys()) == {"runs"}

    def test_per_run_keys_locked(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        keys = set(out["runs"][rids[0]].keys())
        assert keys == {
            "stability", "improvement", "regression",
            "anomaly_penalty", "score",
        }

    def test_stable_run_stability_one(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        assert out["runs"][rids[0]]["stability"] == 1.0

    def test_stable_run_no_improvement_or_regression(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        for rid in rids:
            assert out["runs"][rid]["improvement"] == 0.0
            assert out["runs"][rid]["regression"] == 0.0

    def test_stable_run_score_in_valid_range(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        for rid in rids:
            assert 0.0 <= out["runs"][rid]["score"] <= 1.0


class TestRunScoresUpward:
    def test_at_least_one_upward_run_has_improvement(self, fixed_clock):
        """Three runs with strictly-increasing scores cluster into one
        upward-drift cluster + one anomaly singleton (k=2 chosen by
        silhouette). The members of the upward cluster carry
        improvement=1.0; the singleton lands in 'anomaly'."""
        rids = _seed_upward(fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        upward_count = sum(
            1 for rid in rids
            if out["runs"][rid]["improvement"] == 1.0
        )
        assert upward_count >= 1

    def test_upward_runs_no_regression(self, fixed_clock):
        rids = _seed_upward(fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        for rid in rids:
            assert out["runs"][rid]["regression"] == 0.0

    def test_mean_upward_run_score_above_half(self, fixed_clock):
        rids = _seed_upward(fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        mean_score = sum(
            out["runs"][rid]["score"] for rid in rids
        ) / len(rids)
        assert mean_score >= 0.5


class TestRunScoresDownward:
    def test_at_least_one_downward_run_has_regression(self, fixed_clock):
        """Mirror of the upward test: silhouette picks k=2, so the
        downward cluster carries members + 1 singleton anomaly."""
        rids = _seed_downward(fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        downward_count = sum(
            1 for rid in rids
            if out["runs"][rid]["regression"] == 1.0
        )
        assert downward_count >= 1

    def test_downward_runs_no_improvement(self, fixed_clock):
        rids = _seed_downward(fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        for rid in rids:
            assert out["runs"][rid]["improvement"] == 0.0

    def test_downward_run_score_low(self, fixed_clock):
        rids = _seed_downward(fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        for rid in rids:
            assert out["runs"][rid]["score"] <= 0.5


# ===========================================================================
# B. Per-pair scores — composite math
# ===========================================================================
class TestPairScores:
    def test_top_level_keys(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_pair_scores(rids)
        assert set(out.keys()) == {"pairs"}

    def test_per_pair_keys_locked(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_pair_scores(rids)
        keys = set(out["pairs"]["p1"].keys())
        assert keys == {"stability", "volatility", "trend", "score"}

    def test_stable_pair_score_high(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_pair_scores(rids)
        for pid, data in out["pairs"].items():
            assert data["score"] >= 0.5

    def test_upward_pair_trend(self, fixed_clock):
        rids = _seed_upward(fixed_clock=fixed_clock)
        out = score_mod.compute_pair_scores(rids)
        # p1 trajectory 1,5,9 → "upward"
        assert out["pairs"]["p1"]["trend"] == "upward"

    def test_downward_pair_trend(self, fixed_clock):
        rids = _seed_downward(fixed_clock=fixed_clock)
        out = score_mod.compute_pair_scores(rids)
        assert out["pairs"]["p1"]["trend"] == "downward"

    def test_upward_pair_score_higher_than_downward(self, fixed_clock):
        up_rids   = _seed_upward(prefix="up_t",   fixed_clock=fixed_clock)
        down_rids = _seed_downward(prefix="dn_t", fixed_clock=fixed_clock)
        up_pair   = score_mod.compute_pair_scores(up_rids)["pairs"]["p1"]
        down_pair = score_mod.compute_pair_scores(down_rids)["pairs"]["p1"]
        assert up_pair["score"] > down_pair["score"]

    def test_pair_score_in_valid_range(self, fixed_clock):
        rids = _seed_upward(fixed_clock=fixed_clock)
        out = score_mod.compute_pair_scores(rids)
        for data in out["pairs"].values():
            assert 0.0 <= data["score"] <= 1.0

    def test_empty_input_returns_empty_pairs(self):
        out = score_mod.compute_pair_scores([])
        assert out == {"pairs": {}}


# ===========================================================================
# C. Overall health — aggregation + bonuses
# ===========================================================================
class TestOverallHealth:
    def test_all_upward_high_health(self, fixed_clock):
        rids = _seed_upward(fixed_clock=fixed_clock)
        assert score_mod.overall_health_score(rids) >= 0.8

    def test_all_downward_low_health(self, fixed_clock):
        rids = _seed_downward(fixed_clock=fixed_clock)
        assert score_mod.overall_health_score(rids) <= 0.3

    def test_stable_health_in_middle(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        h = score_mod.overall_health_score(rids)
        assert 0.4 <= h <= 0.8

    def test_empty_input_zero_health(self):
        assert score_mod.overall_health_score([]) == 0.0

    def test_health_in_valid_range(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        assert 0.0 <= score_mod.overall_health_score(rids) <= 1.0

    def test_more_runs_dont_break_aggregation(self, fixed_clock):
        rids = _seed_stable(n=6, fixed_clock=fixed_clock)
        assert 0.0 <= score_mod.overall_health_score(rids) <= 1.0


# ===========================================================================
# D. Anomaly penalty pass-through
# ===========================================================================
class TestAnomalyPassThrough:
    def test_anomaly_penalty_present(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        for rid in rids:
            assert "anomaly_penalty" in out["runs"][rid]
            assert 0.0 <= out["runs"][rid]["anomaly_penalty"] <= 1.0

    def test_anomaly_lowers_run_score(self, fixed_clock):
        # Seed stable runs + one outlier → outlier has higher anomaly,
        # therefore its run_score should be lower than the stable runs'.
        # 6 clock values: 5 for the stable seed + 1 for the outlier save.
        fixed_clock([
            f"2024-01-{i:02d}T10:00:00+00:00" for i in range(1, 7)
        ])
        rids: list = []
        for i in range(5):
            rid = f"s_{i}"
            ep.save_comparison_result(
                rid, [_entry("p1", sp=5, ec=5),
                       _entry("p2", sp=5, ec=5)],
            )
            rids.append(rid)
        ep.save_comparison_result(
            "outlier",
            [_entry("p9", sp=0, ec=0,
                     sp_band="Fails core logic",
                     ec_band="Fails core logic")],
        )
        out = score_mod.compute_run_scores(rids + ["outlier"])
        stable_avg = sum(
            out["runs"][rid]["score"] for rid in rids
        ) / len(rids)
        assert out["runs"]["outlier"]["score"] <= stable_avg


# ===========================================================================
# E. Legacy handling
# ===========================================================================
class TestLegacyHandling:
    def test_legacy_run_zeroed(self, _runs_dir_isolation, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "leg", [_entry("p1")])
        out = score_mod.compute_run_scores(rids + ["leg"])
        assert out["runs"]["leg"]["score"] == 0.0
        assert out["runs"]["leg"]["stability"] == 0.0
        assert out["runs"]["leg"]["anomaly_penalty"] == 1.0

    def test_legacy_excluded_from_overall(
        self, _runs_dir_isolation, fixed_clock,
    ):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        # Mostly-stable health.
        without_leg = score_mod.overall_health_score(rids)
        _write_legacy(_runs_dir_isolation, "leg", [_entry("p1")])
        with_leg = score_mod.overall_health_score(rids + ["leg"])
        # Legacy runs are excluded from numeric aggregation → identical.
        assert with_leg == pytest.approx(without_leg)

    def test_all_legacy_health_zero(self, _runs_dir_isolation):
        _write_legacy(_runs_dir_isolation, "l1", [_entry("p1")])
        _write_legacy(_runs_dir_isolation, "l2", [_entry("p1")])
        assert score_mod.overall_health_score(["l1", "l2"]) == 0.0


# ===========================================================================
# F. Validation
# ===========================================================================
class TestValidation:
    def test_run_scores_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            score_mod.compute_run_scores("nope")

    def test_pair_scores_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            score_mod.compute_pair_scores("nope")

    def test_health_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            score_mod.overall_health_score("nope")

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            score_mod.compute_run_scores(["bad/id"])

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            score_mod.compute_run_scores(["ghost"])

    def test_pair_scores_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            score_mod.compute_pair_scores(["ghost"])

    def test_health_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            score_mod.overall_health_score(["ghost"])


# ===========================================================================
# G. Determinism + clamping
# ===========================================================================
class TestDeterminismAndClamping:
    def test_repeated_run_scores_byte_equal(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        a = score_mod.compute_run_scores(rids)
        b = score_mod.compute_run_scores(rids)
        assert a == b

    def test_repeated_pair_scores_byte_equal(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        a = score_mod.compute_pair_scores(rids)
        b = score_mod.compute_pair_scores(rids)
        assert a == b

    def test_repeated_health_byte_equal(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        a = score_mod.overall_health_score(rids)
        b = score_mod.overall_health_score(rids)
        assert a == b

    def test_run_scores_clamped(self, fixed_clock):
        rids = _seed_downward(fixed_clock=fixed_clock)
        out = score_mod.compute_run_scores(rids)
        for rid in rids:
            assert 0.0 <= out["runs"][rid]["score"] <= 1.0

    def test_clamp_unit_helper(self):
        assert score_mod._clamp_unit(-0.5) == 0.0
        assert score_mod._clamp_unit(1.5)  == 1.0
        assert score_mod._clamp_unit(0.7)  == 0.7


# ===========================================================================
# H. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            score_mod.compute_run_scores,
            score_mod.compute_pair_scores,
            score_mod.overall_health_score,
        ):
            assert callable(fn)

    def test_weight_constants_locked(self):
        assert score_mod._RUN_ALPHA == 0.5
        assert score_mod._RUN_BETA  == 0.5
        assert score_mod._RUN_GAMMA == 0.5
        assert score_mod._RUN_DELTA == 0.5
        assert score_mod._PAIR_W_STABILITY  == 0.5
        assert score_mod._PAIR_W_TREND      == 0.4
        assert score_mod._PAIR_W_VOLATILITY == 0.5

    def test_label_constants_locked(self):
        assert score_mod._LABEL_UPWARD   == "upward drift"
        assert score_mod._LABEL_DOWNWARD == "downward drift"

    def test_trend_numeric_locked(self):
        assert score_mod._TREND_NUMERIC == {
            "upward":   1.0,
            "flat":     0.5,
            "downward": 0.0,
        }


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(score_mod)

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

    def test_composes_units_2_through_5(self):
        """Scoring is pure composition; verify all 4 upstream units
        appear in the source."""
        src = self._code_only()
        for required in (
            "cluster_runs",         # Unit 2
            "multi_run_summary",    # Unit 4
            "detect_run_anomalies", # Unit 5
            "_stddev_of_deltas",    # Unit 3 helper
        ):
            assert required in src
