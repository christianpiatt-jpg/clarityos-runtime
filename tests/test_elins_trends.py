"""
Tests for ELINS2 Unit 3 — long-arc trend detection.

Layered coverage (>= 40 tests, target ~50):
    A. Monotonic increase
    B. Monotonic decrease
    C. Plateau
    D. Oscillation
    E. Volatile
    F. Insufficient data + legacy filtering
    G. Slope / volatility / score arithmetic
    H. Determinism
    I. Validation
    J. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
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


def _save_sequence(prefix: str, sp_values: list, ec_value: int = 5) -> list:
    """Save N runs with a single pair p1 whose sp_score follows
    sp_values across the sequence. Returns the run_ids in chrono
    order."""
    rids: list = []
    for i, sp in enumerate(sp_values):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec_value)])
        rids.append(rid)
    return rids


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


# ===========================================================================
# A. Monotonic increase
# ===========================================================================
class TestMonotonicIncrease:
    def test_strict_increase_three_runs(self):
        rids = _save_sequence("inc3", [1, 5, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "monotonic_increase"

    def test_slope_positive(self):
        rids = _save_sequence("inc_slope", [1, 5, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["slope"] > 0

    def test_low_volatility(self):
        rids = _save_sequence("inc_vol", [1, 5, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["volatility"] < 1.0

    def test_five_run_increase(self):
        rids = _save_sequence("inc5", [1, 3, 5, 7, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "monotonic_increase"

    def test_score_in_valid_range(self):
        rids = _save_sequence("inc_score", [1, 5, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert 0.0 <= out["score"] <= 1.0

    def test_run_ids_passed_through(self):
        rids = _save_sequence("inc_ids", [1, 5, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["run_ids"] == rids


# ===========================================================================
# B. Monotonic decrease
# ===========================================================================
class TestMonotonicDecrease:
    def test_strict_decrease_three_runs(self):
        rids = _save_sequence("dec3", [9, 5, 1])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "monotonic_decrease"

    def test_slope_negative(self):
        rids = _save_sequence("dec_slope", [9, 5, 1])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["slope"] < 0

    def test_low_volatility(self):
        rids = _save_sequence("dec_vol", [9, 5, 1])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["volatility"] < 1.0

    def test_five_run_decrease(self):
        rids = _save_sequence("dec5", [9, 7, 5, 3, 1])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "monotonic_decrease"


# ===========================================================================
# C. Plateau
# ===========================================================================
class TestPlateau:
    def test_constant_sequence_is_plateau(self):
        rids = _save_sequence("plat", [5, 5, 5])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "plateau"

    def test_plateau_slope_zero(self):
        rids = _save_sequence("plat_slope", [5, 5, 5])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["slope"] == 0

    def test_plateau_volatility_zero(self):
        rids = _save_sequence("plat_vol", [5, 5, 5])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["volatility"] == 0

    def test_plateau_score_zero(self):
        rids = _save_sequence("plat_score", [5, 5, 5])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["score"] == 0

    def test_minor_jitter_still_plateau(self):
        # All within the epsilon band — should still classify as plateau.
        rids = _save_sequence("plat_jitter", [5, 5, 5, 5, 5, 5])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "plateau"


# ===========================================================================
# D. Oscillation
# ===========================================================================
class TestOscillation:
    def test_odd_length_oscillation(self):
        # Odd-length pure oscillation: slope = 0 by symmetry.
        rids = _save_sequence("osc_odd", [2, 9, 2, 9, 2])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "oscillation"

    def test_oscillation_high_volatility(self):
        rids = _save_sequence("osc_vol", [2, 9, 2, 9, 2])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["volatility"] >= 1.0

    def test_oscillation_slope_near_zero(self):
        rids = _save_sequence("osc_slope", [2, 9, 2, 9, 2])
        out = trends_mod.trend_for_run_sequence(rids)
        assert abs(out["slope"]) < trends_mod._EPSILON_SLOPE

    def test_oscillation_score_zero(self):
        rids = _save_sequence("osc_score", [2, 9, 2, 9, 2])
        out = trends_mod.trend_for_run_sequence(rids)
        # |slope| < ε → normalised slope = 0 → score = 0.
        assert out["score"] == 0


# ===========================================================================
# E. Volatile
# ===========================================================================
class TestVolatile:
    def test_volatile_combines_slope_and_swing(self):
        # Net upward but huge inter-run swing.
        rids = _save_sequence("vol_combo", [1, 8, 4, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "volatile"

    def test_volatile_high_volatility(self):
        rids = _save_sequence("vol_high", [1, 8, 4, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["volatility"] >= 1.0

    def test_volatile_slope_above_epsilon(self):
        rids = _save_sequence("vol_slope", [1, 8, 4, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert abs(out["slope"]) >= trends_mod._EPSILON_SLOPE


# ===========================================================================
# F. Insufficient data + legacy filtering
# ===========================================================================
class TestInsufficientAndLegacy:
    def test_zero_runs_returns_insufficient(self):
        out = trends_mod.trend_for_run_sequence([])
        assert out["trend"] == "insufficient_data"

    def test_one_run_returns_insufficient(self):
        rids = _save_sequence("one", [5])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "insufficient_data"

    def test_two_runs_returns_insufficient(self):
        rids = _save_sequence("two", [3, 7])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] == "insufficient_data"

    def test_three_runs_classifies(self):
        rids = _save_sequence("three", [3, 5, 7])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["trend"] != "insufficient_data"

    def test_legacy_runs_dropped(self, _runs_dir_isolation):
        # 2 modern + 1 legacy → 2 non-legacy → insufficient.
        rids = _save_sequence("leg_mix", [3, 7])
        _write_legacy(_runs_dir_isolation, "legacy_one", [_entry("p1")])
        out = trends_mod.trend_for_run_sequence(
            rids + ["legacy_one"],
        )
        # Only 2 non-legacy runs remain → insufficient.
        assert out["trend"] == "insufficient_data"

    def test_legacy_skipped_then_classified(self, _runs_dir_isolation):
        rids = _save_sequence("leg_inc", [1, 5, 9])
        _write_legacy(_runs_dir_isolation, "legacy_two", [_entry("p1")])
        # 3 modern + 1 legacy → 3 non-legacy → classify.
        out = trends_mod.trend_for_run_sequence(rids + ["legacy_two"])
        assert out["trend"] == "monotonic_increase"
        assert "legacy_two" not in out["run_ids"]

    def test_insufficient_zero_metrics(self):
        rids = _save_sequence("ins_metrics", [5, 5])
        out = trends_mod.trend_for_run_sequence(rids)
        assert out["slope"] == 0
        assert out["volatility"] == 0
        assert out["score"] == 0


# ===========================================================================
# G. Slope / volatility / score arithmetic
# ===========================================================================
class TestArithmetic:
    def test_score_in_valid_range_for_all_classes(self):
        for seq in (
            [1, 5, 9],          # increase
            [9, 5, 1],          # decrease
            [5, 5, 5],          # plateau
            [2, 9, 2, 9, 2],    # oscillation
            [1, 8, 4, 9],       # volatile
        ):
            rids = _save_sequence(f"sc{abs(hash(tuple(seq)))%10000}", seq)
            out = trends_mod.trend_for_run_sequence(rids)
            assert 0.0 <= out["score"] <= 1.0

    def test_steeper_increase_has_higher_score(self):
        steep = _save_sequence("steep", [1, 5, 9])
        gentle = _save_sequence("gentle", [4, 5, 6])
        s_steep  = trends_mod.trend_for_run_sequence(steep)["score"]
        s_gentle = trends_mod.trend_for_run_sequence(gentle)["score"]
        assert s_steep > s_gentle

    def test_volatility_penalty_lowers_score(self):
        clean = _save_sequence("clean", [1, 5, 9])
        noisy = _save_sequence("noisy", [1, 9, 5, 9])
        s_clean = trends_mod.trend_for_run_sequence(clean)["score"]
        s_noisy = trends_mod.trend_for_run_sequence(noisy)["score"]
        assert s_clean > s_noisy

    def test_ols_slope_helper_two_points(self):
        assert trends_mod._ordinary_least_squares_slope([0, 10]) == 10.0

    def test_ols_slope_helper_horizontal(self):
        assert trends_mod._ordinary_least_squares_slope([5, 5, 5]) == 0.0

    def test_ols_slope_helper_negative(self):
        slope = trends_mod._ordinary_least_squares_slope([10, 5, 0])
        assert slope < 0

    def test_stddev_helper_constant_input_zero(self):
        assert trends_mod._stddev_of_deltas([5, 5, 5, 5]) == 0.0

    def test_stddev_helper_handles_short_input(self):
        assert trends_mod._stddev_of_deltas([5]) == 0.0
        assert trends_mod._stddev_of_deltas([]) == 0.0


# ===========================================================================
# H. Determinism
# ===========================================================================
class TestDeterminism:
    def test_repeated_calls_byte_equal(self):
        rids = _save_sequence("det", [1, 5, 9])
        a = trends_mod.trend_for_run_sequence(rids)
        b = trends_mod.trend_for_run_sequence(rids)
        assert a == b

    def test_detect_trends_alias_byte_equal(self):
        rids = _save_sequence("alias", [1, 5, 9])
        assert (
            trends_mod.detect_trends(rids)
            == trends_mod.trend_for_run_sequence(rids)
        )

    def test_trend_score_matches_full_score(self):
        rids = _save_sequence("score_alias", [1, 5, 9])
        full = trends_mod.trend_for_run_sequence(rids)
        helper = trends_mod.trend_score(rids)
        assert full["score"] == helper


# ===========================================================================
# I. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            trends_mod.trend_for_run_sequence("nope")

    def test_malformed_run_id_raises(self):
        with pytest.raises(ValueError):
            trends_mod.trend_for_run_sequence(["bad/id"])

    def test_missing_run_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            trends_mod.trend_for_run_sequence(["ghost1", "ghost2", "ghost3"])

    def test_trend_score_validates_too(self):
        with pytest.raises(ValueError):
            trends_mod.trend_score("nope")


# ===========================================================================
# J. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            trends_mod.detect_trends,
            trends_mod.trend_for_run_sequence,
            trends_mod.trend_score,
        ):
            assert callable(fn)

    def test_detect_trends_is_alias(self):
        assert trends_mod.detect_trends is trends_mod.trend_for_run_sequence

    def test_threshold_constants_locked(self):
        assert trends_mod._EPSILON_SLOPE        == 0.5
        assert trends_mod._VOLATILITY_THRESHOLD == 1.0
        assert trends_mod._MIN_RUNS_FOR_TREND   == 3

    def test_trend_class_constants_locked(self):
        assert trends_mod._TREND_INSUFFICIENT_DATA == "insufficient_data"
        assert trends_mod._TREND_MONOTONIC_INCREASE == "monotonic_increase"
        assert trends_mod._TREND_MONOTONIC_DECREASE == "monotonic_decrease"
        assert trends_mod._TREND_PLATEAU            == "plateau"
        assert trends_mod._TREND_OSCILLATION        == "oscillation"
        assert trends_mod._TREND_VOLATILE           == "volatile"

    def test_response_keys_locked(self):
        rids = _save_sequence("shape", [1, 5, 9])
        out = trends_mod.trend_for_run_sequence(rids)
        assert set(out.keys()) == {
            "trend", "slope", "volatility", "score", "run_ids",
        }


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(trends_mod)

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
