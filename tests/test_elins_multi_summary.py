"""
Tests for ELINS2 Unit 4 — multi-run summary tables.

Layered coverage (>= 40 tests, target ~50):
    A. Pair-level shape + alignment
    B. Magnitude trajectory (missing pairs → zero)
    C. Direction (band) trajectory
    D. Severity per-transition
    E. Stability + volatility scores
    F. Trend direction (upward / downward / flat)
    G. Pair-level accessors (stability / volatility / direction_over_time)
    H. Edge cases — single run, legacy filtering, empty result
    I. Determinism + validation
    J. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_multi_summary as ms_mod
import elins_persistence as ep
import elins_persistence_sqlite as ep_sql


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _runs_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runs_dir = tmp_path / "elins_runs"
    monkeypatch.setenv(ep._RUNS_DIR_ENV_VAR, str(runs_dir))
    yield runs_dir


def _entry(pid, *, sp=5, ec=5,
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


# ===========================================================================
# A. Pair-level shape + alignment
# ===========================================================================
class TestPairShape:
    def test_top_level_keys_locked(self):
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        out = ms_mod.multi_run_summary(["a", "b"])
        assert set(out.keys()) == {"pair_summaries", "run_ids"}

    def test_pair_summary_keys_locked(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        out = ms_mod.multi_run_summary(["a", "b"])
        keys = set(out["pair_summaries"]["p1"].keys())
        assert keys == {
            "direction_over_time", "magnitude_over_time",
            "severity_over_time", "stability_score",
            "volatility_score", "trend_direction",
        }

    def test_run_ids_field_lists_filtered_ids(self):
        ep.save_comparison_result("r1", [_entry("p1")])
        ep.save_comparison_result("r2", [_entry("p1")])
        out = ms_mod.multi_run_summary(["r1", "r2"])
        assert out["run_ids"] == ["r1", "r2"]

    def test_all_pair_ids_present_in_output(self):
        ep.save_comparison_result("a", [_entry("p1"), _entry("p2")])
        ep.save_comparison_result("b", [_entry("p1"), _entry("p2"), _entry("p3")])
        out = ms_mod.multi_run_summary(["a", "b"])
        assert set(out["pair_summaries"].keys()) == {"p1", "p2", "p3"}

    def test_pair_ids_alphabetically_ordered(self):
        ep.save_comparison_result("a", [_entry("zeta"), _entry("alpha"), _entry("mid")])
        ep.save_comparison_result("b", [_entry("zeta"), _entry("alpha"), _entry("mid")])
        out = ms_mod.multi_run_summary(["a", "b"])
        assert list(out["pair_summaries"].keys()) == ["alpha", "mid", "zeta"]

    def test_magnitude_length_matches_run_count(self):
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("c", [_entry("p1")])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert len(out["pair_summaries"]["p1"]["magnitude_over_time"]) == 3

    def test_direction_length_matches_run_count(self):
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("c", [_entry("p1")])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert len(out["pair_summaries"]["p1"]["direction_over_time"]) == 3

    def test_severity_length_is_run_count_minus_one(self):
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("c", [_entry("p1")])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert len(out["pair_summaries"]["p1"]["severity_over_time"]) == 2


# ===========================================================================
# B. Magnitude trajectory
# ===========================================================================
class TestMagnitudeTrajectory:
    def test_magnitudes_are_composite_means(self):
        # sp=5 ec=7 → composite = 6.0
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=7)])
        ep.save_comparison_result("b", [_entry("p1", sp=5, ec=7)])
        out = ms_mod.multi_run_summary(["a", "b"])
        assert out["pair_summaries"]["p1"]["magnitude_over_time"] == [6.0, 6.0]

    def test_missing_pair_treated_as_zero(self):
        ep.save_comparison_result("a", [_entry("p1", sp=8)])
        ep.save_comparison_result("b", [_entry("p2", sp=4)])
        out = ms_mod.multi_run_summary(["a", "b"])
        # p1 appears only in a → second slot is 0.
        assert out["pair_summaries"]["p1"]["magnitude_over_time"][0] > 0
        assert out["pair_summaries"]["p1"]["magnitude_over_time"][1] == 0.0
        # p2 appears only in b → first slot is 0.
        assert out["pair_summaries"]["p2"]["magnitude_over_time"][0] == 0.0
        assert out["pair_summaries"]["p2"]["magnitude_over_time"][1] > 0

    def test_increasing_magnitudes(self):
        ep.save_comparison_result("a", [_entry("p1", sp=1, ec=1)])
        ep.save_comparison_result("b", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("c", [_entry("p1", sp=9, ec=9)])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert out["pair_summaries"]["p1"]["magnitude_over_time"] == [1.0, 5.0, 9.0]


# ===========================================================================
# C. Direction (band) trajectory
# ===========================================================================
class TestDirectionTrajectory:
    def test_worse_band_picked_per_run(self):
        ep.save_comparison_result(
            "a",
            [_entry("p1", sp_band="Strong", ec_band="Weak")],
        )
        ep.save_comparison_result(
            "b",
            [_entry("p1", sp_band="Acceptable", ec_band="Strong")],
        )
        out = ms_mod.multi_run_summary(["a", "b"])
        # Worse of {Strong, Weak} = Weak; worse of {Acceptable, Strong} = Acceptable.
        assert out["pair_summaries"]["p1"]["direction_over_time"] == [
            "Weak", "Acceptable",
        ]

    def test_missing_pair_yields_absent_sentinel(self):
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p2")])
        out = ms_mod.multi_run_summary(["a", "b"])
        assert out["pair_summaries"]["p1"]["direction_over_time"] == [
            "Acceptable", "absent",
        ]

    def test_fails_core_logic_band_is_worst(self):
        ep.save_comparison_result(
            "a",
            [_entry("p1", sp_band="Strong",
                     ec_band="Fails core logic")],
        )
        ep.save_comparison_result(
            "b",
            [_entry("p1", sp_band="Strong",
                     ec_band="Fails core logic")],
        )
        out = ms_mod.multi_run_summary(["a", "b"])
        assert out["pair_summaries"]["p1"]["direction_over_time"] == [
            "Fails core logic", "Fails core logic",
        ]


# ===========================================================================
# D. Severity per-transition
# ===========================================================================
class TestSeverityTransitions:
    def test_zero_delta_yields_none(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=5, ec=5)])
        out = ms_mod.multi_run_summary(["a", "b"])
        assert out["pair_summaries"]["p1"]["severity_over_time"] == ["none"]

    def test_small_delta_yields_weak(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=7, ec=7)])
        out = ms_mod.multi_run_summary(["a", "b"])
        # magnitude delta = 7 - 5 = 2 → "weak"
        assert out["pair_summaries"]["p1"]["severity_over_time"] == ["weak"]

    def test_moderate_delta(self):
        ep.save_comparison_result("a", [_entry("p1", sp=2, ec=2)])
        ep.save_comparison_result("b", [_entry("p1", sp=6, ec=6)])
        out = ms_mod.multi_run_summary(["a", "b"])
        # delta = 4 → "moderate"
        assert out["pair_summaries"]["p1"]["severity_over_time"] == ["moderate"]

    def test_large_delta_yields_strong(self):
        ep.save_comparison_result("a", [_entry("p1", sp=1, ec=1)])
        ep.save_comparison_result("b", [_entry("p1", sp=9, ec=9)])
        out = ms_mod.multi_run_summary(["a", "b"])
        # delta = 8 → "strong"
        assert out["pair_summaries"]["p1"]["severity_over_time"] == ["strong"]

    def test_negative_delta_severity_uses_absolute_value(self):
        ep.save_comparison_result("a", [_entry("p1", sp=9, ec=9)])
        ep.save_comparison_result("b", [_entry("p1", sp=1, ec=1)])
        out = ms_mod.multi_run_summary(["a", "b"])
        # |delta| = 8 → "strong"
        assert out["pair_summaries"]["p1"]["severity_over_time"] == ["strong"]


# ===========================================================================
# E. Stability + volatility scores
# ===========================================================================
class TestStabilityVolatility:
    def test_constant_pair_high_stability(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("c", [_entry("p1", sp=5, ec=5)])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert out["pair_summaries"]["p1"]["stability_score"] == 1.0
        assert out["pair_summaries"]["p1"]["volatility_score"] == 0.0

    def test_oscillating_pair_low_stability(self):
        ep.save_comparison_result("a", [_entry("p1", sp=2, ec=2)])
        ep.save_comparison_result("b", [_entry("p1", sp=9, ec=9)])
        ep.save_comparison_result("c", [_entry("p1", sp=2, ec=2)])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert out["pair_summaries"]["p1"]["stability_score"] < 0.5
        assert out["pair_summaries"]["p1"]["volatility_score"] > 0.5

    def test_stability_plus_volatility_equals_one(self):
        ep.save_comparison_result("a", [_entry("p1", sp=2)])
        ep.save_comparison_result("b", [_entry("p1", sp=5)])
        out = ms_mod.multi_run_summary(["a", "b"])
        s = out["pair_summaries"]["p1"]["stability_score"]
        v = out["pair_summaries"]["p1"]["volatility_score"]
        assert s + v == pytest.approx(1.0)

    def test_stability_in_valid_range(self):
        ep.save_comparison_result("a", [_entry("p1", sp=1)])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        out = ms_mod.multi_run_summary(["a", "b"])
        s = out["pair_summaries"]["p1"]["stability_score"]
        assert 0.0 <= s <= 1.0

    def test_volatility_in_valid_range(self):
        ep.save_comparison_result("a", [_entry("p1", sp=1)])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        out = ms_mod.multi_run_summary(["a", "b"])
        v = out["pair_summaries"]["p1"]["volatility_score"]
        assert 0.0 <= v <= 1.0


# ===========================================================================
# F. Trend direction
# ===========================================================================
class TestTrendDirection:
    def test_upward_trend(self):
        ep.save_comparison_result("a", [_entry("p1", sp=1)])
        ep.save_comparison_result("b", [_entry("p1", sp=5)])
        ep.save_comparison_result("c", [_entry("p1", sp=9)])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert out["pair_summaries"]["p1"]["trend_direction"] == "upward"

    def test_downward_trend(self):
        ep.save_comparison_result("a", [_entry("p1", sp=9)])
        ep.save_comparison_result("b", [_entry("p1", sp=5)])
        ep.save_comparison_result("c", [_entry("p1", sp=1)])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert out["pair_summaries"]["p1"]["trend_direction"] == "downward"

    def test_flat_trend(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=5)])
        ep.save_comparison_result("c", [_entry("p1", sp=5)])
        out = ms_mod.multi_run_summary(["a", "b", "c"])
        assert out["pair_summaries"]["p1"]["trend_direction"] == "flat"


# ===========================================================================
# G. Pair-level accessors
# ===========================================================================
class TestPairLevelAccessors:
    def test_pair_stability_subset(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5), _entry("p2", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=5), _entry("p2", sp=9)])
        out = ms_mod.pair_stability(["a", "b"])
        assert set(out.keys()) == {"p1", "p2"}
        assert all(isinstance(v, float) for v in out.values())

    def test_pair_volatility_subset(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=5)])
        out = ms_mod.pair_volatility(["a", "b"])
        assert out["p1"] == 0.0

    def test_pair_direction_over_time_subset(self):
        # Both dimensions explicitly set to make the "worse" pick
        # unambiguous: a = worse(Weak, Weak)=Weak; b = worse(Strong,
        # Strong)=Strong.
        ep.save_comparison_result(
            "a", [_entry("p1", sp_band="Weak", ec_band="Weak")],
        )
        ep.save_comparison_result(
            "b", [_entry("p1", sp_band="Strong", ec_band="Strong")],
        )
        out = ms_mod.pair_direction_over_time(["a", "b"])
        assert out["p1"] == ["Weak", "Strong"]

    def test_accessors_agree_with_full_summary(self):
        ep.save_comparison_result("a", [_entry("p1", sp=2)])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        full = ms_mod.multi_run_summary(["a", "b"])["pair_summaries"]["p1"]
        assert ms_mod.pair_stability(["a", "b"])["p1"] == full["stability_score"]
        assert ms_mod.pair_volatility(["a", "b"])["p1"] == full["volatility_score"]
        assert (
            ms_mod.pair_direction_over_time(["a", "b"])["p1"]
            == full["direction_over_time"]
        )


# ===========================================================================
# H. Edge cases
# ===========================================================================
class TestEdgeCases:
    def test_single_run_returns_empty(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = ms_mod.multi_run_summary(["solo"])
        assert out == {"pair_summaries": {}, "run_ids": ["solo"]}

    def test_zero_runs_returns_empty(self):
        out = ms_mod.multi_run_summary([])
        assert out == {"pair_summaries": {}, "run_ids": []}

    def test_legacy_runs_dropped(self, _runs_dir_isolation):
        ep.save_comparison_result("modern", [_entry("p1")])
        _write_legacy(_runs_dir_isolation, "legacy", [_entry("p1")])
        out = ms_mod.multi_run_summary(["modern", "legacy"])
        # 1 non-legacy → empty summary.
        assert out["pair_summaries"] == {}
        assert "legacy" not in out["run_ids"]
        assert out["run_ids"] == ["modern"]

    def test_two_non_legacy_after_filter_yields_summary(
        self, _runs_dir_isolation,
    ):
        # Set both dimensions so composite magnitude is exact.
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8, ec=8)])
        _write_legacy(_runs_dir_isolation, "leg",
                      [_entry("p1", sp=99, ec=99)])
        out = ms_mod.multi_run_summary(["leg", "a", "b"])
        assert out["pair_summaries"]["p1"]["magnitude_over_time"] == [5.0, 8.0]
        assert out["run_ids"] == ["a", "b"]

    def test_empty_run_payload_handled(self):
        ep.save_comparison_result("e1", [])
        ep.save_comparison_result("e2", [])
        out = ms_mod.multi_run_summary(["e1", "e2"])
        assert out["pair_summaries"] == {}
        assert out["run_ids"] == ["e1", "e2"]


# ===========================================================================
# I. Determinism + validation
# ===========================================================================
class TestDeterminism:
    def test_repeated_calls_byte_equal(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        first  = ms_mod.multi_run_summary(["a", "b"])
        second = ms_mod.multi_run_summary(["a", "b"])
        assert first == second

    def test_accessors_repeatable(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        assert ms_mod.pair_stability(["a", "b"]) == ms_mod.pair_stability(["a", "b"])


class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            ms_mod.multi_run_summary("nope")

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            ms_mod.multi_run_summary(["bad/id", "good"])

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            ms_mod.multi_run_summary(["ghost1", "ghost2"])

    def test_pair_stability_validates(self):
        with pytest.raises(ValueError):
            ms_mod.pair_stability("nope")

    def test_pair_volatility_validates(self):
        with pytest.raises(ValueError):
            ms_mod.pair_volatility("nope")

    def test_pair_direction_validates(self):
        with pytest.raises(ValueError):
            ms_mod.pair_direction_over_time("nope")


# ===========================================================================
# J. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_all_public_callable(self):
        for fn in (
            ms_mod.multi_run_summary,
            ms_mod.pair_stability,
            ms_mod.pair_volatility,
            ms_mod.pair_direction_over_time,
        ):
            assert callable(fn)

    def test_severity_bucket_constants_locked(self):
        assert ms_mod._SEVERITY_NONE_MAX     == 0.0
        assert ms_mod._SEVERITY_WEAK_MAX     == 2.0
        assert ms_mod._SEVERITY_MODERATE_MAX == 4.0

    def test_trend_direction_constants_locked(self):
        assert ms_mod._TREND_UP   == "upward"
        assert ms_mod._TREND_DOWN == "downward"
        assert ms_mod._TREND_FLAT == "flat"

    def test_absent_sentinel_locked(self):
        assert ms_mod._ABSENT_BAND == "absent"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(ms_mod)

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

    def test_delegates_to_trends_helpers(self):
        """Unit 4 reuses Unit 3's OLS slope + stddev helpers — no
        parallel re-implementation."""
        src = self._code_only()
        assert "_ordinary_least_squares_slope" in src
        assert "_stddev_of_deltas" in src
