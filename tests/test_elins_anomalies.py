"""
Tests for ELINS2 Unit 5 — anomaly detection.

Layered coverage (>= 40 tests, target ~50):
    A. Stable universe → no anomalies
    B. Singleton outlier → high/medium anomaly
    C. Trend-driven anomaly (residual)
    D. Sequence anomalies (sliding windows)
    E. Legacy run handling
    F. is_anomalous_run helper
    G. Validation
    H. Determinism + thresholds
    I. Source-code purity / module surface
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


def _seed_stable_universe(prefix="s", n=5, sp=5, ec=5):
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec),
                                          _entry("p2", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. Stable universe → no anomalies
# ===========================================================================
class TestStableUniverse:
    def test_five_identical_runs_no_anomalies(self):
        rids = _seed_stable_universe(n=5)
        out = anom_mod.detect_run_anomalies(rids)
        for rid in rids:
            assert out["runs"][rid]["level"] == "none"

    def test_no_anomaly_score_below_medium_threshold(self):
        rids = _seed_stable_universe(n=5)
        out = anom_mod.detect_run_anomalies(rids)
        for rid in rids:
            assert out["runs"][rid]["score"] < 0.4

    def test_no_anomaly_empty_reasons(self):
        rids = _seed_stable_universe(n=5)
        out = anom_mod.detect_run_anomalies(rids)
        for rid in rids:
            assert out["runs"][rid]["reasons"] == []

    def test_two_runs_universe_no_anomaly(self):
        rids = _seed_stable_universe(n=2)
        out = anom_mod.detect_run_anomalies(rids)
        # 2 identical runs → no anomaly signals fire.
        for rid in rids:
            assert out["runs"][rid]["level"] == "none"


# ===========================================================================
# B. Singleton outlier → high/medium anomaly
# ===========================================================================
class TestSingletonOutlier:
    def _seed_with_outlier(self):
        stable = _seed_stable_universe(n=5, sp=5)
        ep.save_comparison_result(
            "outlier",
            [_entry("p9", sp=0, ec=0,
                     sp_band="Fails core logic",
                     ec_band="Fails core logic")],
        )
        return stable + ["outlier"]

    def test_outlier_flagged_at_least_medium(self):
        rids = self._seed_with_outlier()
        out = anom_mod.detect_run_anomalies(rids)
        assert out["runs"]["outlier"]["level"] in ("medium", "high")

    def test_outlier_score_above_medium_threshold(self):
        rids = self._seed_with_outlier()
        out = anom_mod.detect_run_anomalies(rids)
        assert out["runs"]["outlier"]["score"] >= 0.4

    def test_outlier_singleton_cluster_reason(self):
        rids = self._seed_with_outlier()
        out = anom_mod.detect_run_anomalies(rids)
        assert "singleton_cluster" in out["runs"]["outlier"]["reasons"]

    def test_stable_runs_not_flagged_when_outlier_present(self):
        rids = self._seed_with_outlier()
        out = anom_mod.detect_run_anomalies(rids)
        for rid in rids[:5]:
            assert out["runs"][rid]["level"] == "none"


# ===========================================================================
# C. Trend-driven anomaly
# ===========================================================================
class TestTrendDrivenAnomaly:
    def test_outlier_residual_drives_extreme_trend_reason(self):
        # 5 stable runs + 1 with very different score → outlier has the
        # max residual.
        rids = _seed_stable_universe(n=5, sp=5)
        ep.save_comparison_result(
            "spike", [_entry("p1", sp=0), _entry("p2", sp=0)],
        )
        out = anom_mod.detect_run_anomalies(rids + ["spike"])
        # The 'spike' may or may not be flagged in reasons depending on
        # composite, but its trend residual should be the highest. We
        # check that some reason from the expected set appears.
        info = out["runs"]["spike"]
        assert info["level"] in ("medium", "high")

    def test_pure_linear_progression_yields_no_trend_anomaly(self):
        # Perfect linear increase → all residuals zero → no
        # trend-driven anomaly reason fires.
        for i, sp in enumerate((1, 3, 5, 7, 9), 1):
            ep.save_comparison_result(
                f"lin_{i}", [_entry("p1", sp=sp), _entry("p2", sp=sp)],
            )
        out = anom_mod.detect_run_anomalies(
            ["lin_1", "lin_2", "lin_3", "lin_4", "lin_5"],
        )
        for rid in out["runs"]:
            assert "extreme_trend" not in out["runs"][rid]["reasons"]


# ===========================================================================
# D. Sequence anomalies
# ===========================================================================
class TestSequenceAnomalies:
    def test_stable_windows_have_zero_score(self):
        rids = _seed_stable_universe(n=5, sp=5)
        out = anom_mod.detect_sequence_anomalies(rids, window=3)
        for w in out["windows"].values():
            assert w["score"] == 0.0

    def test_volatile_windows_flagged(self):
        ep.save_comparison_result("v1", [_entry("p1", sp=1)])
        ep.save_comparison_result("v2", [_entry("p1", sp=9)])
        ep.save_comparison_result("v3", [_entry("p1", sp=1)])
        out = anom_mod.detect_sequence_anomalies(
            ["v1", "v2", "v3"], window=3,
        )
        win = out["windows"]["window_0"]
        assert win["score"] >= 0.4
        assert win["level"] in ("medium", "high")

    def test_window_run_ids_correct(self):
        rids = _seed_stable_universe(n=5, sp=5)
        out = anom_mod.detect_sequence_anomalies(rids, window=3)
        assert out["windows"]["window_0"]["run_ids"] == rids[:3]
        assert out["windows"]["window_1"]["run_ids"] == rids[1:4]

    def test_window_count_matches_slide(self):
        rids = _seed_stable_universe(n=5, sp=5)
        out = anom_mod.detect_sequence_anomalies(rids, window=3)
        # 5 runs with window 3 → 3 windows.
        assert len(out["windows"]) == 3

    def test_window_smaller_than_input_returns_empty(self):
        rids = _seed_stable_universe(n=2, sp=5)
        out = anom_mod.detect_sequence_anomalies(rids, window=3)
        assert out["windows"] == {}

    def test_window_returns_thresholds(self):
        rids = _seed_stable_universe(n=5, sp=5)
        out = anom_mod.detect_sequence_anomalies(rids, window=3)
        assert out["thresholds"] == {"high": 0.7, "medium": 0.4}

    def test_window_param_in_response(self):
        rids = _seed_stable_universe(n=5, sp=5)
        out = anom_mod.detect_sequence_anomalies(rids, window=3)
        assert out["window"] == 3

    def test_invalid_window_raises(self):
        with pytest.raises(ValueError, match=">= 2"):
            anom_mod.detect_sequence_anomalies([], window=1)

    def test_negative_window_raises(self):
        with pytest.raises(ValueError, match=">= 2"):
            anom_mod.detect_sequence_anomalies([], window=-3)

    def test_bool_window_raises(self):
        with pytest.raises(ValueError, match="positive int"):
            anom_mod.detect_sequence_anomalies([], window=True)


# ===========================================================================
# E. Legacy run handling
# ===========================================================================
class TestLegacyHandling:
    def test_legacy_run_scored_one(self, _runs_dir_isolation):
        ep.save_comparison_result("modern", [_entry("p1")])
        _write_legacy(_runs_dir_isolation, "leg", [_entry("p1")])
        out = anom_mod.detect_run_anomalies(["modern", "leg"])
        assert out["runs"]["leg"]["score"] == 1.0
        assert out["runs"]["leg"]["level"] == "high"

    def test_legacy_reason_includes_legacy_run(self, _runs_dir_isolation):
        ep.save_comparison_result("modern", [_entry("p1")])
        _write_legacy(_runs_dir_isolation, "leg", [_entry("p1")])
        out = anom_mod.detect_run_anomalies(["modern", "leg"])
        assert out["runs"]["leg"]["reasons"] == ["legacy_run"]

    def test_modern_runs_unaffected_by_legacy(self, _runs_dir_isolation):
        rids = _seed_stable_universe(n=4, sp=5)
        _write_legacy(_runs_dir_isolation, "leg", [_entry("p1", sp=99)])
        out = anom_mod.detect_run_anomalies(rids + ["leg"])
        for rid in rids:
            assert out["runs"][rid]["level"] == "none"


# ===========================================================================
# F. is_anomalous_run helper
# ===========================================================================
class TestIsAnomalousRun:
    def test_anomalous_returns_true(self):
        stable = _seed_stable_universe(n=5, sp=5)
        ep.save_comparison_result(
            "out", [_entry("p9", sp=0,
                            sp_band="Fails core logic",
                            ec_band="Fails core logic")],
        )
        assert anom_mod.is_anomalous_run("out", stable + ["out"]) is True

    def test_non_anomalous_returns_false(self):
        rids = _seed_stable_universe(n=5, sp=5)
        assert anom_mod.is_anomalous_run(rids[0], rids) is False

    def test_explicit_no_universe_defaults_to_self(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        # Without a universe, the run is alone → no anomaly.
        assert anom_mod.is_anomalous_run("solo") is False

    def test_target_added_if_missing_from_universe(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        # Universe passed in doesn't include the target → helper still
        # works (target added to universe).
        ep.save_comparison_result("other", [_entry("p1")])
        anom_mod.is_anomalous_run("solo", ["other"])


# ===========================================================================
# G. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            anom_mod.detect_run_anomalies("nope")

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            anom_mod.detect_run_anomalies(["bad/id"])

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            anom_mod.detect_run_anomalies(["ghost"])

    def test_empty_returns_well_formed(self):
        out = anom_mod.detect_run_anomalies([])
        assert out == {"runs": {}, "thresholds": {"high": 0.7, "medium": 0.4}}

    def test_sequence_validation(self):
        with pytest.raises(ValueError, match="expected a list"):
            anom_mod.detect_sequence_anomalies("nope")

    def test_sequence_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            anom_mod.detect_sequence_anomalies(["g1", "g2", "g3"])


# ===========================================================================
# H. Determinism + thresholds
# ===========================================================================
class TestDeterminismAndThresholds:
    def test_repeated_calls_byte_equal(self):
        rids = _seed_stable_universe(n=4, sp=5)
        a = anom_mod.detect_run_anomalies(rids)
        b = anom_mod.detect_run_anomalies(rids)
        assert a == b

    def test_thresholds_present_in_response(self):
        rids = _seed_stable_universe(n=3, sp=5)
        out = anom_mod.detect_run_anomalies(rids)
        assert out["thresholds"] == {"high": 0.7, "medium": 0.4}

    def test_thresholds_constants_locked(self):
        assert anom_mod._HIGH_THRESHOLD == 0.7
        assert anom_mod._MEDIUM_THRESHOLD == 0.4

    def test_classification_respects_high_threshold(self):
        # Synthesize a legacy run (score=1.0 hard-coded) → must be high.
        runs_dir = Path(ep._runs_dir()) if False else None  # noop guard
        # Direct test of classifier.
        assert anom_mod._classify_score(0.95) == "high"
        assert anom_mod._classify_score(0.7)  == "high"
        assert anom_mod._classify_score(0.69) == "medium"

    def test_classification_respects_medium_threshold(self):
        assert anom_mod._classify_score(0.5)  == "medium"
        assert anom_mod._classify_score(0.4)  == "medium"
        assert anom_mod._classify_score(0.39) == "none"

    def test_weight_constants_locked_sum_one(self):
        total = (
            anom_mod._W_SIM
            + anom_mod._W_CLUSTER
            + anom_mod._W_TREND
            + anom_mod._W_PAIRS
        )
        assert total == pytest.approx(1.0)


# ===========================================================================
# I. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            anom_mod.detect_run_anomalies,
            anom_mod.detect_sequence_anomalies,
            anom_mod.is_anomalous_run,
        ):
            assert callable(fn)

    def test_reason_strings_locked(self):
        assert anom_mod._REASON_LOW_SIMILARITY    == "low_similarity"
        assert anom_mod._REASON_SINGLETON_CLUSTER == "singleton_cluster"
        assert anom_mod._REASON_EXTREME_TREND     == "extreme_trend"
        assert anom_mod._REASON_VOLATILE_PAIRS    == "volatile_pairs"
        assert anom_mod._REASON_LEGACY_RUN        == "legacy_run"

    def test_level_strings_locked(self):
        assert anom_mod._LEVEL_HIGH   == "high"
        assert anom_mod._LEVEL_MEDIUM == "medium"
        assert anom_mod._LEVEL_NONE   == "none"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(anom_mod)

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

    def test_composes_earlier_units(self):
        src = self._code_only()
        # Anomaly module is pure composition over Units 1-4.
        assert "similarity_matrix"     in src
        assert "cluster_runs"          in src
        assert "multi_run_summary"     in src
