"""
Tests for ELINS2 Unit 2 — multi-run drift clustering.

Layered coverage (>= 40 tests, target ~50):
    A. Single & two-run edge cases
    B. Two-cluster separation
    C. Multi-cluster discovery
    D. Cluster labels (drift / stable / anomaly)
    E. Centroid / medoid selection
    F. Silhouette-based k selection
    G. Determinism + reordering
    H. Validation
    I. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import elins_clustering as cl_mod
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


def _seed_two_tight_clusters(fixed_clock):
    """Two tight 'low score' runs and two tight 'high score' runs."""
    fixed_clock([f"2024-01-{i:02d}T10:00:00+00:00" for i in range(1, 5)])
    ep.save_comparison_result("low1",  [_entry("p1", sp=2), _entry("p2", sp=3)])
    ep.save_comparison_result("low2",  [_entry("p1", sp=2), _entry("p2", sp=3)])
    ep.save_comparison_result("high1", [_entry("p1", sp=9), _entry("p2", sp=8)])
    ep.save_comparison_result("high2", [_entry("p1", sp=9), _entry("p2", sp=8)])


# ===========================================================================
# A. Single & two-run edge cases
# ===========================================================================
class TestEdgeCases:
    def test_single_run_one_cluster(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        res = cl_mod.cluster_runs(["solo"])
        assert res["k"] == 1
        assert res["assignments"] == {"solo": "c0"}
        assert res["cluster_summary"]["c0"]["label"] == "anomaly"

    def test_single_run_centroid_is_self(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        res = cl_mod.cluster_runs(["solo"])
        assert res["cluster_centroids"]["c0"] == "solo"

    def test_two_identical_runs_one_cluster_with_k_none(self, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-01-02T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=5)])
        # When all runs are identical, silhouette sweep degenerates.
        # The sweep still picks SOME k in [2, n-1]; with n=2 the only
        # candidate is k=2 (two singletons).
        res = cl_mod.cluster_runs(["a", "b"])
        assert res["k"] in (1, 2)

    def test_two_runs_explicit_k_2(self, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-01-02T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=1)])
        res = cl_mod.cluster_runs(["a", "b"], k=2)
        assert res["k"] == 2
        assert len(res["cluster_summary"]) == 2


# ===========================================================================
# B. Two-cluster separation
# ===========================================================================
class TestTwoClusterSeparation:
    def test_low_high_split_into_two_clusters(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        # Two clusters expected.
        cluster_groups = {}
        for rid, cid in res["assignments"].items():
            cluster_groups.setdefault(cid, set()).add(rid)
        assert len(cluster_groups) == 2

    def test_lows_grouped_together(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        assert res["assignments"]["low1"] == res["assignments"]["low2"]

    def test_highs_grouped_together(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        assert res["assignments"]["high1"] == res["assignments"]["high2"]

    def test_lows_and_highs_in_different_clusters(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        assert res["assignments"]["low1"] != res["assignments"]["high1"]

    def test_perfect_separation_silhouette_one(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"], k=2)
        assert res["silhouette"] == pytest.approx(1.0)


# ===========================================================================
# C. Multi-cluster discovery
# ===========================================================================
class TestMultiClusterDiscovery:
    def test_three_groups_yields_three_clusters(self, fixed_clock):
        fixed_clock([f"2024-01-{i:02d}T10:00:00+00:00" for i in range(1, 7)])
        # Group A
        ep.save_comparison_result("a1", [_entry("p1", sp=1)])
        ep.save_comparison_result("a2", [_entry("p1", sp=1)])
        # Group B
        ep.save_comparison_result("b1", [_entry("p1", sp=5)])
        ep.save_comparison_result("b2", [_entry("p1", sp=5)])
        # Group C
        ep.save_comparison_result("c1", [_entry("p1", sp=10)])
        ep.save_comparison_result("c2", [_entry("p1", sp=10)])
        res = cl_mod.cluster_runs(
            ["a1", "a2", "b1", "b2", "c1", "c2"], k=3,
        )
        # Each (a, b, c) pair should land in the same cluster.
        a = res["assignments"]
        assert a["a1"] == a["a2"]
        assert a["b1"] == a["b2"]
        assert a["c1"] == a["c2"]
        # ... and across-group ids differ.
        assert a["a1"] != a["b1"]
        assert a["b1"] != a["c1"]
        assert a["a1"] != a["c1"]

    def test_explicit_k_n_yields_n_singletons(self, fixed_clock):
        fixed_clock([f"2024-01-{i:02d}T10:00:00+00:00" for i in range(1, 5)])
        for i, sp in enumerate((1, 4, 7, 10), 1):
            ep.save_comparison_result(f"r{i}", [_entry("p1", sp=sp)])
        res = cl_mod.cluster_runs(
            ["r1", "r2", "r3", "r4"], k=4,
        )
        sizes = [s["size"] for s in res["cluster_summary"].values()]
        assert sizes == [1, 1, 1, 1]


# ===========================================================================
# D. Cluster labels
# ===========================================================================
class TestClusterLabels:
    def test_singleton_labeled_anomaly(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        res = cl_mod.cluster_runs(["solo"])
        assert res["cluster_summary"]["c0"]["label"] == "anomaly"

    def test_trending_up_cluster_labeled_upward(self, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-01-02T10:00:00+00:00",
            "2024-01-03T10:00:00+00:00",
        ])
        # Three runs with strictly-increasing single-party score on p1.
        ep.save_comparison_result("u1", [_entry("p1", sp=2)])
        ep.save_comparison_result("u2", [_entry("p1", sp=5)])
        ep.save_comparison_result("u3", [_entry("p1", sp=9)])
        res = cl_mod.cluster_runs(["u1", "u2", "u3"], k=1)
        # Single cluster containing all three — sequence is trending_up.
        label = res["cluster_summary"]["c0"]["label"]
        assert label == "upward drift"

    def test_trending_down_cluster_labeled_downward(self, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-01-02T10:00:00+00:00",
            "2024-01-03T10:00:00+00:00",
        ])
        ep.save_comparison_result("d1", [_entry("p1", sp=9)])
        ep.save_comparison_result("d2", [_entry("p1", sp=5)])
        ep.save_comparison_result("d3", [_entry("p1", sp=2)])
        res = cl_mod.cluster_runs(["d1", "d2", "d3"], k=1)
        label = res["cluster_summary"]["c0"]["label"]
        assert label == "downward drift"

    def test_stable_cluster_labeled_stable(self, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-01-02T10:00:00+00:00",
        ])
        ep.save_comparison_result("s1", [_entry("p1", sp=5)])
        ep.save_comparison_result("s2", [_entry("p1", sp=5)])
        res = cl_mod.cluster_runs(["s1", "s2"], k=1)
        assert res["cluster_summary"]["c0"]["label"] == "stable"

    def test_label_field_in_summary(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        for cid, summary in res["cluster_summary"].items():
            assert "label" in summary
            assert summary["label"] in (
                "stable", "upward drift", "downward drift",
                "oscillation", "anomaly",
            )

    def test_size_field_in_summary(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        for cid, summary in res["cluster_summary"].items():
            assert summary["size"] == len(summary["members"])


# ===========================================================================
# E. Centroid / medoid selection
# ===========================================================================
class TestCentroids:
    def test_centroids_returned_per_cluster(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        for cid in res["cluster_summary"].keys():
            assert cid in res["cluster_centroids"]

    def test_centroid_is_member_of_cluster(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        for cid, summary in res["cluster_summary"].items():
            assert res["cluster_centroids"][cid] in summary["members"]

    def test_singleton_centroid_is_only_member(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        res = cl_mod.cluster_runs(["solo"], k=1)
        assert res["cluster_centroids"]["c0"] == "solo"

    def test_tied_centroid_breaks_alphabetically(self, fixed_clock):
        """Two identical members → both have equal distance to each
        other → alphabetically-smaller wins."""
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-01-02T10:00:00+00:00",
        ])
        ep.save_comparison_result("z_id", [_entry("p1", sp=5)])
        ep.save_comparison_result("a_id", [_entry("p1", sp=5)])
        res = cl_mod.cluster_runs(["z_id", "a_id"], k=1)
        assert res["cluster_centroids"]["c0"] == "a_id"


# ===========================================================================
# F. Silhouette-based k selection
# ===========================================================================
class TestSilhouetteSelection:
    def test_well_separated_picks_k_2(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        assert res["k"] == 2

    def test_silhouette_value_in_range(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(
            ["low1", "low2", "high1", "high2"], k=2,
        )
        assert -1.0 <= res["silhouette"] <= 1.0

    def test_silhouette_none_for_single_run(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        res = cl_mod.cluster_runs(["solo"])
        assert res["silhouette"] is None

    def test_three_well_separated_groups_picks_k_3(self, fixed_clock):
        fixed_clock([f"2024-01-{i:02d}T10:00:00+00:00" for i in range(1, 7)])
        for sp, pair in zip((1, 1, 5, 5, 9, 9),
                             ("a1", "a2", "b1", "b2", "c1", "c2")):
            ep.save_comparison_result(pair, [_entry("p1", sp=sp)])
        res = cl_mod.cluster_runs(
            ["a1", "a2", "b1", "b2", "c1", "c2"],
        )
        assert res["k"] == 3


# ===========================================================================
# G. Determinism + reordering
# ===========================================================================
class TestDeterminism:
    def test_repeated_calls_byte_equal(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        first  = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        second = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        assert first == second

    def test_input_order_does_not_affect_output(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        a = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        b = cl_mod.cluster_runs(["high2", "low2", "low1", "high1"])
        assert a == b

    def test_cluster_ids_alphabetically_ordered_by_member(
        self, fixed_clock,
    ):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        # c0's smallest member should be alphabetically smaller than
        # c1's smallest member.
        c0_min = min(res["cluster_summary"]["c0"]["members"])
        c1_min = min(res["cluster_summary"]["c1"]["members"])
        assert c0_min < c1_min

    def test_assignments_keys_match_input(self, fixed_clock):
        _seed_two_tight_clusters(fixed_clock)
        res = cl_mod.cluster_runs(["low1", "low2", "high1", "high2"])
        assert set(res["assignments"].keys()) == {
            "low1", "low2", "high1", "high2",
        }


# ===========================================================================
# H. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            cl_mod.cluster_runs("nope")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            cl_mod.cluster_runs([])

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            cl_mod.cluster_runs(["bad/id"])

    def test_zero_k_raises(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match=">= 1"):
            cl_mod.cluster_runs(["r"], k=0)

    def test_negative_k_raises(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match=">= 1"):
            cl_mod.cluster_runs(["r"], k=-2)

    def test_k_greater_than_n_raises(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match="cannot exceed"):
            cl_mod.cluster_runs(["r"], k=5)

    def test_bool_k_raises(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match="positive int"):
            cl_mod.cluster_runs(["r"], k=True)

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            cl_mod.cluster_runs(["ghost"])


# ===========================================================================
# I. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_cluster_runs_callable(self):
        assert callable(cl_mod.cluster_runs)

    def test_response_top_level_keys(self):
        ep.save_comparison_result("r", [])
        res = cl_mod.cluster_runs(["r"])
        assert set(res.keys()) == {
            "assignments", "cluster_summary", "cluster_centroids",
            "silhouette", "k",
        }

    def test_drift_label_map_locked(self):
        assert cl_mod._DRIFT_LABEL_MAP == {
            "stable":         "stable",
            "trending_up":    "upward drift",
            "trending_down":  "downward drift",
            "volatile":       "oscillation",
        }

    def test_max_k_constant(self):
        assert cl_mod._MAX_K == 8


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(cl_mod)

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

    def test_delegates_to_similarity_engine(self):
        src = self._code_only()
        assert "similarity_matrix" in src
