"""
Tests for ELINS2 Unit 1 — run similarity engine.

Layered coverage (>= 40 tests, target ~50):
    A. Identical / near-identical
    B. Diverging scores + bands
    C. Pair overlap (full / partial / disjoint)
    D. Metadata penalties
    E. Legacy run guards
    F. top_k_similar_runs
    G. similarity_matrix (symmetry, diagonal, reordering)
    H. Validation
    I. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
import elins_similarity as sim_mod


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
    """Insert a legacy-shape envelope (metadata=None) directly into the
    DB. Matches the Unit 25 test helper."""
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
# A. Identical / near-identical runs
# ===========================================================================
class TestIdenticalRuns:
    def test_self_similarity_is_one(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        assert sim_mod.compute_similarity("solo", "solo") == 1.0

    def test_two_runs_with_identical_data_score_one(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)], source="single")
        ep.save_comparison_result("b", [_entry("p1", sp=5)], source="single")
        assert sim_mod.compute_similarity("a", "b") == 1.0

    def test_two_empty_runs_score_one(self):
        ep.save_comparison_result("e1", [], source="single")
        ep.save_comparison_result("e2", [], source="single")
        assert sim_mod.compute_similarity("e1", "e2") == 1.0

    def test_three_pair_identical_runs(self):
        payload = [
            _entry("p1", sp=5), _entry("p2", sp=8), _entry("p3", sp=2),
        ]
        ep.save_comparison_result("x", payload, source="batch")
        ep.save_comparison_result("y", payload, source="batch")
        assert sim_mod.compute_similarity("x", "y") == 1.0

    def test_small_score_delta_yields_high_similarity(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)], source="single")
        ep.save_comparison_result("b", [_entry("p1", sp=6)], source="single")
        score = sim_mod.compute_similarity("a", "b")
        assert score > 0.95


# ===========================================================================
# B. Diverging scores + bands
# ===========================================================================
class TestDivergingScores:
    def test_max_score_delta_reduces_similarity(self):
        ep.save_comparison_result(
            "low", [_entry("p1", sp=0, ec=0,
                            sp_band="Fails core logic",
                            ec_band="Fails core logic")],
            source="single",
        )
        ep.save_comparison_result(
            "high", [_entry("p1", sp=10, ec=10,
                             sp_band="Strong", ec_band="Strong")],
            source="single",
        )
        score = sim_mod.compute_similarity("low", "high")
        assert score < 0.85

    def test_score_delta_strictly_decreases_similarity(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)], source="single")
        ep.save_comparison_result(
            "small_delta", [_entry("p1", sp=6)], source="single",
        )
        ep.save_comparison_result(
            "large_delta", [_entry("p1", sp=1)], source="single",
        )
        s_small = sim_mod.compute_similarity("a", "small_delta")
        s_large = sim_mod.compute_similarity("a", "large_delta")
        assert s_small > s_large

    def test_band_change_decreases_similarity(self):
        ep.save_comparison_result(
            "strong", [_entry("p1", sp=10, sp_band="Strong")],
            source="single",
        )
        ep.save_comparison_result(
            "fails", [_entry("p1", sp=10, sp_band="Fails core logic")],
            source="single",
        )
        # Same score but different band → lower similarity than identical.
        assert sim_mod.compute_similarity("strong", "fails") < 1.0

    def test_score_in_valid_range(self):
        ep.save_comparison_result(
            "a", [_entry("p1", sp=0)], source="single",
        )
        ep.save_comparison_result(
            "b", [_entry("p1", sp=10)], source="single",
        )
        s = sim_mod.compute_similarity("a", "b")
        assert 0.0 <= s <= 1.0


# ===========================================================================
# C. Pair overlap (full / partial / disjoint)
# ===========================================================================
class TestPairOverlap:
    def test_partial_overlap_lower_than_full(self):
        ep.save_comparison_result(
            "full", [_entry("p1"), _entry("p2")], source="single",
        )
        ep.save_comparison_result(
            "match", [_entry("p1"), _entry("p2")], source="single",
        )
        ep.save_comparison_result(
            "partial", [_entry("p1"), _entry("p9")], source="single",
        )
        s_full = sim_mod.compute_similarity("full", "match")
        s_partial = sim_mod.compute_similarity("full", "partial")
        assert s_full > s_partial

    def test_disjoint_lower_than_partial(self):
        ep.save_comparison_result(
            "a", [_entry("p1"), _entry("p2")], source="single",
        )
        ep.save_comparison_result(
            "partial", [_entry("p1"), _entry("p9")], source="single",
        )
        ep.save_comparison_result(
            "disjoint", [_entry("q1"), _entry("q2")], source="single",
        )
        s_partial = sim_mod.compute_similarity("a", "partial")
        s_disjoint = sim_mod.compute_similarity("a", "disjoint")
        assert s_partial > s_disjoint

    def test_disjoint_yields_strictly_less_than_one(self):
        ep.save_comparison_result(
            "a", [_entry("p1")], source="single",
        )
        ep.save_comparison_result(
            "b", [_entry("q1")], source="single",
        )
        s = sim_mod.compute_similarity("a", "b")
        assert s < 1.0


# ===========================================================================
# D. Metadata penalties
# ===========================================================================
class TestMetadataPenalty:
    def test_same_data_different_source_still_close(self):
        ep.save_comparison_result(
            "src_a", [_entry("p1", sp=5)], source="single",
        )
        ep.save_comparison_result(
            "src_b", [_entry("p1", sp=5)], source="batch",
        )
        # Same data → high similarity. Source differs → penalty present.
        s = sim_mod.compute_similarity("src_a", "src_b")
        assert s < 1.0
        assert s > 0.95

    def test_same_data_different_evidence_dir(self):
        ep.save_comparison_result(
            "ed_a", [_entry("p1")],
            source="directory", evidence_dir="/a",
        )
        ep.save_comparison_result(
            "ed_b", [_entry("p1")],
            source="directory", evidence_dir="/b",
        )
        s = sim_mod.compute_similarity("ed_a", "ed_b")
        assert s < 1.0

    def test_metadata_match_yields_higher_score_than_mismatch(self):
        ep.save_comparison_result(
            "match_a", [_entry("p1")], source="single",
        )
        ep.save_comparison_result(
            "match_b", [_entry("p1")], source="single",
        )
        ep.save_comparison_result(
            "mismatch_a", [_entry("p1")], source="single",
        )
        ep.save_comparison_result(
            "mismatch_b", [_entry("p1")], source="batch",
        )
        s_match = sim_mod.compute_similarity("match_a", "match_b")
        s_mismatch = sim_mod.compute_similarity("mismatch_a", "mismatch_b")
        assert s_match > s_mismatch


# ===========================================================================
# E. Legacy run guards
# ===========================================================================
class TestLegacyGuards:
    def test_legacy_vs_modern_returns_zero(
        self, _runs_dir_isolation,
    ):
        ep.save_comparison_result("modern", [_entry("p1")], source="single")
        _write_legacy(_runs_dir_isolation, "leg", [_entry("p1")])
        assert sim_mod.compute_similarity("modern", "leg") == 0.0

    def test_legacy_vs_legacy_returns_zero(self, _runs_dir_isolation):
        _write_legacy(_runs_dir_isolation, "leg1", [_entry("p1")])
        _write_legacy(_runs_dir_isolation, "leg2", [_entry("p1")])
        assert sim_mod.compute_similarity("leg1", "leg2") == 0.0

    def test_legacy_self_similarity_zero(self, _runs_dir_isolation):
        _write_legacy(_runs_dir_isolation, "leg", [_entry("p1")])
        assert sim_mod.compute_similarity("leg", "leg") == 0.0


# ===========================================================================
# F. top_k_similar_runs
# ===========================================================================
class TestTopK:
    def _setup(self):
        ep.save_comparison_result("target", [_entry("p1", sp=5)], source="single")
        ep.save_comparison_result(
            "near", [_entry("p1", sp=5)], source="single",
        )
        ep.save_comparison_result(
            "mid", [_entry("p1", sp=7)], source="single",
        )
        ep.save_comparison_result(
            "far", [_entry("p1", sp=1)], source="single",
        )

    def test_returns_list_of_tuples(self):
        self._setup()
        out = sim_mod.top_k_similar_runs("target", k=3)
        assert isinstance(out, list)
        assert all(
            isinstance(t, tuple) and len(t) == 2 for t in out
        )

    def test_excludes_self(self):
        self._setup()
        out = sim_mod.top_k_similar_runs("target", k=10)
        assert "target" not in [rid for rid, _ in out]

    def test_sorted_descending_by_score(self):
        self._setup()
        out = sim_mod.top_k_similar_runs("target", k=3)
        scores = [s for _, s in out]
        assert scores == sorted(scores, reverse=True)

    def test_nearest_first(self):
        self._setup()
        out = sim_mod.top_k_similar_runs("target", k=1)
        assert out[0][0] == "near"

    def test_k_truncates(self):
        self._setup()
        out = sim_mod.top_k_similar_runs("target", k=2)
        assert len(out) == 2

    def test_k_greater_than_available_returns_all(self):
        self._setup()
        out = sim_mod.top_k_similar_runs("target", k=50)
        # 3 other runs available besides target.
        assert len(out) == 3

    def test_alphabetical_tiebreak(self):
        ep.save_comparison_result("target", [_entry("p1", sp=5)], source="single")
        # Two identical runs to target.
        ep.save_comparison_result("z_tie", [_entry("p1", sp=5)], source="single")
        ep.save_comparison_result("a_tie", [_entry("p1", sp=5)], source="single")
        out = sim_mod.top_k_similar_runs("target", k=2)
        # Both score 1.0; a_tie comes first alphabetically.
        assert [rid for rid, _ in out] == ["a_tie", "z_tie"]

    def test_empty_universe_returns_empty(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = sim_mod.top_k_similar_runs("solo", k=5)
        assert out == []

    def test_invalid_k_raises(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match=">= 1"):
            sim_mod.top_k_similar_runs("r", k=0)

    def test_negative_k_raises(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match=">= 1"):
            sim_mod.top_k_similar_runs("r", k=-3)

    def test_bool_k_raises(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match="positive int"):
            sim_mod.top_k_similar_runs("r", k=True)

    def test_missing_target_raises(self):
        with pytest.raises(FileNotFoundError):
            sim_mod.top_k_similar_runs("ghost", k=3)


# ===========================================================================
# G. similarity_matrix
# ===========================================================================
class TestSimilarityMatrix:
    def _setup(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)], source="single")
        ep.save_comparison_result("b", [_entry("p1", sp=5)], source="single")
        ep.save_comparison_result("c", [_entry("p1", sp=1)], source="single")

    def test_returns_dict(self):
        self._setup()
        m = sim_mod.similarity_matrix(["a", "b", "c"])
        assert isinstance(m, dict)

    def test_keys_are_tuples(self):
        self._setup()
        m = sim_mod.similarity_matrix(["a", "b", "c"])
        for key in m.keys():
            assert isinstance(key, tuple)
            assert len(key) == 2

    def test_matrix_size(self):
        self._setup()
        m = sim_mod.similarity_matrix(["a", "b", "c"])
        # n×n = 9 entries.
        assert len(m) == 9

    def test_diagonal_is_one(self):
        self._setup()
        m = sim_mod.similarity_matrix(["a", "b", "c"])
        for rid in ("a", "b", "c"):
            assert m[(rid, rid)] == 1.0

    def test_symmetric(self):
        self._setup()
        m = sim_mod.similarity_matrix(["a", "b", "c"])
        for x in ("a", "b", "c"):
            for y in ("a", "b", "c"):
                assert m[(x, y)] == m[(y, x)]

    def test_stable_under_input_reordering(self):
        self._setup()
        m1 = sim_mod.similarity_matrix(["a", "b", "c"])
        m2 = sim_mod.similarity_matrix(["c", "b", "a"])
        assert m1 == m2

    def test_legacy_diagonal_is_zero(self, _runs_dir_isolation):
        _write_legacy(_runs_dir_isolation, "leg", [_entry("p1")])
        m = sim_mod.similarity_matrix(["leg"])
        assert m[("leg", "leg")] == 0.0

    def test_single_run_matrix(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        m = sim_mod.similarity_matrix(["solo"])
        assert m == {("solo", "solo"): 1.0}

    def test_empty_list_returns_empty_matrix(self):
        assert sim_mod.similarity_matrix([]) == {}

    def test_matches_compute_similarity_pairwise(self):
        self._setup()
        m = sim_mod.similarity_matrix(["a", "b", "c"])
        for x in ("a", "b", "c"):
            for y in ("a", "b", "c"):
                expected = sim_mod.compute_similarity(x, y)
                assert m[(x, y)] == pytest.approx(expected)


# ===========================================================================
# H. Validation
# ===========================================================================
class TestValidation:
    def test_compute_rejects_malformed_id(self):
        with pytest.raises(ValueError):
            sim_mod.compute_similarity("bad/id", "anything")

    def test_compute_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            sim_mod.compute_similarity("ghost1", "ghost2")

    def test_matrix_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            sim_mod.similarity_matrix("nope")

    def test_matrix_malformed_id_raises(self):
        with pytest.raises(ValueError):
            sim_mod.similarity_matrix(["good", "bad$id"])

    def test_matrix_missing_run_raises(self):
        ep.save_comparison_result("present", [])
        with pytest.raises(FileNotFoundError):
            sim_mod.similarity_matrix(["present", "ghost"])


# ===========================================================================
# I. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_compute_similarity_callable(self):
        assert callable(sim_mod.compute_similarity)

    def test_top_k_similar_runs_callable(self):
        assert callable(sim_mod.top_k_similar_runs)

    def test_similarity_matrix_callable(self):
        assert callable(sim_mod.similarity_matrix)

    def test_weight_constants_locked(self):
        assert sim_mod._W_DRIFT_MAGNITUDE == 0.30
        assert sim_mod._W_DRIFT_DIRECTION == 0.20
        assert sim_mod._W_SEVERITY        == 0.15
        assert sim_mod._W_SUMMARY         == 0.15
        assert sim_mod._W_PAIR_OVERLAP    == 0.15
        assert sim_mod._W_METADATA        == 0.05

    def test_max_score_locked(self):
        assert sim_mod._MAX_SCORE == 10.0


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(sim_mod)

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
