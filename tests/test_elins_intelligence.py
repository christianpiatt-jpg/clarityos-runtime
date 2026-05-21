"""
Tests for ELINS2 Unit 9 — composite intelligence orchestrator.

Layered coverage (>= 40 tests, target ~55):
    A. Top-level shape / locked keys
    B. Happy path (3-5 runs)
    C. Small N: 0 / 1 / 2 runs
    D. Sub-section shapes (similarity, clustering, trends, anomalies,
       scores, narratives, sequences)
    E. Delegation — every sub-section matches the underlying unit
    F. Determinism (byte-equal repeats)
    G. Validation
    H. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_anomalies as anom_mod
import elins_clustering as clust_mod
import elins_intelligence as intel_mod
import elins_multi_summary as msum_mod
import elins_narratives as narr_mod
import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
import elins_scoring as score_mod
import elins_sequences as seq_mod
import elins_similarity as sim_mod
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


def _seed_runs(prefix="s", n=5, sp=5, ec=5):
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec),
                                          _entry("p2", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


def _seed_upward(prefix="u", n=5):
    rids: list = []
    seq = [1, 3, 5, 7, 9][:n] if n <= 5 else (
        [round(1 + 8 * i / (n - 1)) for i in range(n)]
    )
    for i, sp in enumerate(seq, 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_top_level_keys_locked(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out.keys()) == {
            "run_ids", "similarity", "clustering", "trends",
            "anomalies", "scores", "narratives", "sequences",
        }

    def test_run_ids_is_input_copy(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["run_ids"] == rids
        # Defensive copy: mutating the input doesn't affect the response.
        rids.append("never_seen")
        # No exception means the previous call captured a snapshot.
        assert out["run_ids"] != rids

    def test_sub_sections_are_dicts(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        for key in ("similarity", "clustering", "trends", "anomalies",
                    "scores", "narratives", "sequences"):
            assert isinstance(out[key], dict)


# ===========================================================================
# B. Happy path (3-5 runs)
# ===========================================================================
class TestHappyPath:
    def test_three_runs_returns_full_payload(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        # Spot-check a few critical leaves.
        assert "matrix" in out["similarity"]
        assert "assignments" in out["clustering"]
        assert "sequence" in out["trends"]
        assert "runs" in out["anomalies"]
        assert "overall_health" in out["scores"]
        assert "headline" in out["narratives"]["runs"]
        assert "analysis" in out["sequences"]

    def test_five_runs_best_and_worst_present(self):
        rids = _seed_runs(n=5, sp=5)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["sequences"]["best"] is not None
        assert out["sequences"]["worst"] is not None

    def test_five_runs_best_and_worst_are_dicts(self):
        rids = _seed_runs(n=5, sp=5)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert isinstance(out["sequences"]["best"], dict)
        assert isinstance(out["sequences"]["worst"], dict)

    def test_upward_sequence_high_health(self):
        rids = _seed_upward(n=5)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["scores"]["overall_health"] >= 0.7

    def test_overall_health_in_unit_interval(self):
        rids = _seed_runs(n=4)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert 0.0 <= out["scores"]["overall_health"] <= 1.0


# ===========================================================================
# C. Small N — 0 / 1 / 2 runs
# ===========================================================================
class TestSmallN:
    def test_zero_runs_top_level_keys(self):
        out = intel_mod.intelligence_for_run_ids([])
        assert set(out.keys()) == {
            "run_ids", "similarity", "clustering", "trends",
            "anomalies", "scores", "narratives", "sequences",
        }

    def test_zero_runs_empty_run_ids(self):
        out = intel_mod.intelligence_for_run_ids([])
        assert out["run_ids"] == []

    def test_zero_runs_empty_clustering(self):
        out = intel_mod.intelligence_for_run_ids([])
        assert out["clustering"]["assignments"] == {}
        assert out["clustering"]["cluster_summary"] == {}

    def test_zero_runs_zero_health(self):
        out = intel_mod.intelligence_for_run_ids([])
        assert out["scores"]["overall_health"] == 0.0

    def test_zero_runs_best_worst_none(self):
        out = intel_mod.intelligence_for_run_ids([])
        assert out["sequences"]["best"] is None
        assert out["sequences"]["worst"] is None

    def test_one_run_self_similarity(self):
        rids = _seed_runs(prefix="one", n=1)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["similarity"]["matrix"][rids[0]][rids[0]] == 1.0

    def test_one_run_top_k_empty(self):
        rids = _seed_runs(prefix="one_k", n=1)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["similarity"]["top_k"][rids[0]] == []

    def test_one_run_best_worst_none(self):
        rids = _seed_runs(prefix="one_bw", n=1)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["sequences"]["best"] is None
        assert out["sequences"]["worst"] is None

    def test_two_runs_best_worst_none(self):
        rids = _seed_runs(prefix="two", n=2)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["sequences"]["best"] is None
        assert out["sequences"]["worst"] is None

    def test_two_runs_matrix_symmetric(self):
        rids = _seed_runs(prefix="two_m", n=2)
        out = intel_mod.intelligence_for_run_ids(rids)
        a, b = rids
        assert out["similarity"]["matrix"][a][b] == \
               out["similarity"]["matrix"][b][a]


# ===========================================================================
# D. Sub-section shapes
# ===========================================================================
class TestSimilaritySection:
    def test_matrix_is_nested_dict(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert isinstance(out["similarity"]["matrix"], dict)
        for a in rids:
            assert isinstance(out["similarity"]["matrix"][a], dict)

    def test_matrix_covers_every_pair(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        for a in rids:
            assert set(out["similarity"]["matrix"][a].keys()) == set(rids)

    def test_matrix_diagonal_one(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        for rid in rids:
            assert out["similarity"]["matrix"][rid][rid] == 1.0

    def test_top_k_keys_match_run_ids(self):
        rids = _seed_runs(n=4)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["similarity"]["top_k"].keys()) == set(rids)

    def test_top_k_length_bounded(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        for rid, neighbours in out["similarity"]["top_k"].items():
            # n=3 means each run sees at most 2 neighbours (top-K=5 caps to n-1).
            assert len(neighbours) <= 2


class TestClusteringSection:
    def test_assignments_cover_all_runs(self):
        rids = _seed_runs(n=4)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["clustering"]["assignments"].keys()) == set(rids)

    def test_cluster_summary_has_label_and_size(self):
        rids = _seed_runs(n=4)
        out = intel_mod.intelligence_for_run_ids(rids)
        for cid, info in out["clustering"]["cluster_summary"].items():
            assert "label" in info
            assert "size" in info
            assert "members" in info

    def test_cluster_centroids_one_per_cluster(self):
        rids = _seed_runs(n=4)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["clustering"]["cluster_centroids"].keys()) == \
               set(out["clustering"]["cluster_summary"].keys())


class TestTrendsSection:
    def test_sequence_has_locked_keys(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["trends"]["sequence"].keys()) == {
            "trend", "slope", "volatility", "score", "run_ids",
        }

    def test_pairs_keys_are_pair_ids(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        # Stable seed uses p1, p2 → both should be present.
        assert set(out["trends"]["pairs"].keys()) == {"p1", "p2"}


class TestAnomaliesSection:
    def test_runs_keys_are_run_ids(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["anomalies"]["runs"].keys()) == set(rids)

    def test_thresholds_present(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["anomalies"]["thresholds"] == {"high": 0.7, "medium": 0.4}


class TestScoresSection:
    def test_keys_locked(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["scores"].keys()) == {
            "runs", "pairs", "overall_health",
        }

    def test_pairs_keys_match_pair_ids(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["scores"]["pairs"].keys()) == {"p1", "p2"}

    def test_runs_keys_match_input(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["scores"]["runs"].keys()) == set(rids)


class TestNarrativesSection:
    def test_keys_locked(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["narratives"].keys()) == {
            "runs", "anomalies", "sequence",
        }

    def test_each_narrative_has_required_keys(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        for pane in ("runs", "anomalies", "sequence"):
            assert set(out["narratives"][pane].keys()) == {
                "headline", "bullets", "details",
            }


class TestSequencesSection:
    def test_keys_locked(self):
        rids = _seed_runs(n=5)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["sequences"].keys()) == {
            "analysis", "best", "worst",
        }

    def test_analysis_keys_locked(self):
        rids = _seed_runs(n=5)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert set(out["sequences"]["analysis"].keys()) == {
            "trend", "overall_health",
            "anomaly_fraction", "upward_fraction",
            "downward_fraction", "stable_cluster_fraction",
        }

    def test_best_worst_keys_locked(self):
        rids = _seed_runs(n=5)
        out = intel_mod.intelligence_for_run_ids(rids)
        for key in ("best", "worst"):
            assert set(out["sequences"][key].keys()) == {
                "run_ids", "overall_health", "trend", "anomaly_fraction",
            }


# ===========================================================================
# E. Delegation — every sub-section matches the underlying unit
# ===========================================================================
class TestDelegation:
    def test_similarity_matrix_matches_unit_1(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = sim_mod.similarity_matrix(rids)
        for a in rids:
            for b in rids:
                assert out["similarity"]["matrix"][a][b] == \
                       raw[(a, b)]

    def test_clustering_matches_unit_2(self):
        rids = _seed_runs(n=4)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = clust_mod.cluster_runs(rids)
        assert out["clustering"]["assignments"] == raw["assignments"]
        assert out["clustering"]["k"] == raw["k"]

    def test_trends_sequence_matches_unit_3(self):
        rids = _seed_upward(prefix="del_t")
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = trends_mod.trend_for_run_sequence(rids)
        assert out["trends"]["sequence"] == raw

    def test_trends_pairs_match_unit_4(self):
        rids = _seed_runs(prefix="del_p", n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = msum_mod.multi_run_summary(rids)
        assert out["trends"]["pairs"] == raw["pair_summaries"]

    def test_anomalies_match_unit_5(self):
        rids = _seed_runs(prefix="del_a", n=4)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = anom_mod.detect_run_anomalies(rids)
        assert out["anomalies"] == raw

    def test_run_scores_match_unit_6(self):
        rids = _seed_runs(prefix="del_s", n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = score_mod.compute_run_scores(rids)
        assert out["scores"]["runs"] == raw["runs"]

    def test_pair_scores_match_unit_6(self):
        rids = _seed_runs(prefix="del_ps", n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = score_mod.compute_pair_scores(rids)
        assert out["scores"]["pairs"] == raw["pairs"]

    def test_overall_health_matches_unit_6(self):
        rids = _seed_runs(prefix="del_h", n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        assert out["scores"]["overall_health"] == pytest.approx(
            score_mod.overall_health_score(rids),
        )

    def test_runs_narrative_matches_unit_7(self):
        rids = _seed_runs(prefix="del_n", n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = narr_mod.summarize_runs(rids)
        assert out["narratives"]["runs"] == raw

    def test_anomalies_narrative_matches_unit_7(self):
        rids = _seed_runs(prefix="del_na", n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = narr_mod.summarize_anomalies(rids)
        assert out["narratives"]["anomalies"] == raw

    def test_sequence_analysis_matches_unit_8(self):
        rids = _seed_runs(prefix="del_seq", n=5)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = seq_mod.analyze_sequence(rids)
        assert out["sequences"]["analysis"] == raw

    def test_best_window_matches_unit_8(self):
        rids = _seed_runs(prefix="del_bw", n=6)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = seq_mod.best_sequence(rids, window=5)
        assert out["sequences"]["best"] == raw

    def test_worst_window_matches_unit_8(self):
        rids = _seed_runs(prefix="del_ww", n=6)
        out = intel_mod.intelligence_for_run_ids(rids)
        raw = seq_mod.worst_sequence(rids, window=5)
        assert out["sequences"]["worst"] == raw


# ===========================================================================
# F. Determinism
# ===========================================================================
class TestDeterminism:
    def test_repeated_call_byte_equal(self):
        rids = _seed_runs(n=4)
        a = intel_mod.intelligence_for_run_ids(rids)
        b = intel_mod.intelligence_for_run_ids(rids)
        assert a == b

    def test_repeated_call_byte_equal_empty(self):
        a = intel_mod.intelligence_for_run_ids([])
        b = intel_mod.intelligence_for_run_ids([])
        assert a == b

    def test_json_round_trip_preserved(self):
        rids = _seed_runs(n=3)
        out = intel_mod.intelligence_for_run_ids(rids)
        # tuple-of-tuples top_k entries serialize through JSON as lists;
        # they're still equivalent after round-trip.
        encoded = json.dumps(out, sort_keys=True, default=list)
        # Decoding succeeds without raising — that's the round-trip check.
        decoded = json.loads(encoded)
        assert decoded["run_ids"] == rids


# ===========================================================================
# G. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            intel_mod.intelligence_for_run_ids("nope")

    def test_dict_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            intel_mod.intelligence_for_run_ids({"run_ids": []})

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            intel_mod.intelligence_for_run_ids(["bad/id"])

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            intel_mod.intelligence_for_run_ids(["ghost"])

    def test_partial_missing_run_raises(self):
        rids = _seed_runs(prefix="pmr", n=2)
        with pytest.raises(FileNotFoundError):
            intel_mod.intelligence_for_run_ids(rids + ["ghost"])


# ===========================================================================
# H. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(intel_mod.intelligence_for_run_ids)

    def test_top_k_default_locked(self):
        assert intel_mod._TOP_K_DEFAULT == 5


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(intel_mod)

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

    def test_composes_units_1_through_8(self):
        src = self._code_only()
        for required in (
            "similarity_matrix",           # Unit 1
            "top_k_similar_runs",          # Unit 1
            "cluster_runs",                # Unit 2
            "trend_for_run_sequence",      # Unit 3
            "multi_run_summary",           # Unit 4
            "detect_run_anomalies",        # Unit 5
            "compute_run_scores",          # Unit 6
            "compute_pair_scores",         # Unit 6
            "overall_health_score",        # Unit 6
            "summarize_runs",              # Unit 7
            "summarize_anomalies",         # Unit 7
            "analyze_sequence",            # Unit 8
            "best_sequence",               # Unit 8
            "worst_sequence",              # Unit 8
        ):
            assert required in src
