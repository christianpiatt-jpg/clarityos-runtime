"""
Tests for ELINS2 Unit 7 — narrative extraction.

Layered coverage (>= 40 tests, target ~50):
    A. Structural / shape contract
    B. High-health narrative tone
    C. Low-health narrative tone
    D. Anomaly mentions
    E. Top volatile pairs surfaced
    F. Cluster narratives (per label)
    G. Cluster representative + size handling
    H. Anomaly inventory narratives
    I. Top-N + reason grouping
    J. Legacy handling
    K. Validation
    L. Determinism
    M. Source-code purity / module surface
    N. Consistency with underlying signals
"""
from __future__ import annotations

import inspect
import json
import re
import sqlite3
from pathlib import Path

import pytest

import elins_anomalies as anom_mod
import elins_clustering as clust_mod
import elins_narratives as narr_mod
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


def _seed_upward(prefix="u"):
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 7, 9), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_downward(prefix="d"):
    rids: list = []
    for i, sp in enumerate((9, 7, 5, 3, 1), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp,
                                                sp_band="Fails core logic",
                                                ec_band="Fails core logic")])
        rids.append(rid)
    return rids


def _seed_volatile(prefix="v"):
    rids: list = []
    for i, sp in enumerate((1, 9, 1, 9, 1), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_outlier_set():
    """Stable universe + a clear singleton outlier."""
    stable = _seed_stable(prefix="ost", n=5, sp=5)
    ep.save_comparison_result(
        "ost_outlier",
        [_entry("p9", sp=0, ec=0,
                 sp_band="Fails core logic",
                 ec_band="Fails core logic")],
    )
    return stable + ["ost_outlier"]


# ===========================================================================
# A. Structural / shape contract
# ===========================================================================
class TestRunsShape:
    def test_top_level_keys(self):
        rids = _seed_stable(n=4)
        out = narr_mod.summarize_runs(rids)
        assert set(out.keys()) == {"headline", "bullets", "details"}

    def test_headline_is_non_empty_string(self):
        rids = _seed_stable(n=4)
        out = narr_mod.summarize_runs(rids)
        assert isinstance(out["headline"], str)
        assert out["headline"].strip() != ""

    def test_bullets_is_non_empty_list(self):
        rids = _seed_stable(n=4)
        out = narr_mod.summarize_runs(rids)
        assert isinstance(out["bullets"], list)
        assert len(out["bullets"]) > 0

    def test_no_empty_bullets(self):
        rids = _seed_stable(n=4)
        out = narr_mod.summarize_runs(rids)
        for bullet in out["bullets"]:
            assert isinstance(bullet, str)
            assert bullet.strip() != ""

    def test_details_keys_locked(self):
        rids = _seed_stable(n=4)
        out = narr_mod.summarize_runs(rids)
        assert set(out["details"].keys()) == {
            "overall_health", "num_runs", "num_anomalies",
            "dominant_trend", "dominant_cluster_label",
        }

    def test_empty_returns_well_formed(self):
        out = narr_mod.summarize_runs([])
        assert set(out.keys()) == {"headline", "bullets", "details"}
        assert out["details"]["num_runs"] == 0
        assert out["details"]["overall_health"] == 0.0

    def test_empty_has_non_empty_headline_and_bullets(self):
        out = narr_mod.summarize_runs([])
        assert out["headline"].strip() != ""
        assert len(out["bullets"]) >= 1
        for b in out["bullets"]:
            assert b.strip() != ""


# ===========================================================================
# B. High-health narrative tone
# ===========================================================================
class TestHighHealth:
    def test_upward_sequence_high_health_word(self):
        rids = _seed_upward()
        out = narr_mod.summarize_runs(rids)
        # Health bullet should mention "high" tone.
        joined = " ".join(out["bullets"]).lower()
        assert "high" in joined

    def test_upward_overall_health_at_or_above_threshold(self):
        rids = _seed_upward()
        out = narr_mod.summarize_runs(rids)
        assert out["details"]["overall_health"] >= 0.7

    def test_high_health_headline_mentions_healthy(self):
        rids = _seed_upward()
        out = narr_mod.summarize_runs(rids)
        assert "healthy" in out["headline"].lower()

    def test_stable_sequence_emphasizes_stability_not_anomalies(self):
        rids = _seed_stable(n=5, sp=5)
        out = narr_mod.summarize_runs(rids)
        # No anomalies in a clean stable universe.
        assert out["details"]["num_anomalies"] == 0
        joined = " ".join(out["bullets"]).lower()
        assert "no anomalous runs" in joined


# ===========================================================================
# C. Low-health narrative tone
# ===========================================================================
class TestLowHealth:
    def test_downward_overall_health_below_threshold(self):
        rids = _seed_downward()
        out = narr_mod.summarize_runs(rids)
        assert out["details"]["overall_health"] <= 0.4

    def test_downward_headline_mentions_stress(self):
        rids = _seed_downward()
        out = narr_mod.summarize_runs(rids)
        assert "stress" in out["headline"].lower()

    def test_high_and_low_headlines_differ(self):
        high_rids = _seed_upward(prefix="up_diff")
        low_rids  = _seed_downward(prefix="dn_diff")
        high_out = narr_mod.summarize_runs(high_rids)
        low_out  = narr_mod.summarize_runs(low_rids)
        assert high_out["headline"] != low_out["headline"]

    def test_low_health_bullet_includes_health_value(self):
        rids = _seed_downward(prefix="dn_val")
        out = narr_mod.summarize_runs(rids)
        # First bullet is the health phrase: "Overall health is X (Y.YY)."
        assert "Overall health is" in out["bullets"][0]


# ===========================================================================
# D. Anomaly mentions
# ===========================================================================
class TestAnomalyMentions:
    def test_anomaly_heavy_set_mentions_anomalies(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_runs(rids)
        joined = " ".join(out["bullets"]).lower()
        assert "anomalous" in joined

    def test_anomaly_heavy_set_records_count(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_runs(rids)
        assert out["details"]["num_anomalies"] >= 1

    def test_stable_set_has_no_anomalies(self):
        rids = _seed_stable(n=5, sp=5)
        out = narr_mod.summarize_runs(rids)
        assert out["details"]["num_anomalies"] == 0


# ===========================================================================
# E. Top volatile pairs surfaced
# ===========================================================================
class TestVolatilePairs:
    def test_top_volatile_pair_in_bullets(self):
        # Seed two pairs — p_calm stays at 5, p_wild oscillates.
        for i, sp in enumerate((1, 9, 1, 9, 1), 1):
            rid = f"vp_{i:02d}"
            ep.save_comparison_result(
                rid,
                [
                    _entry("p_calm", sp=5,  ec=5),
                    _entry("p_wild", sp=sp, ec=sp),
                ],
            )
        rids = [f"vp_{i:02d}" for i in range(1, 6)]
        out = narr_mod.summarize_runs(rids)
        joined = " ".join(out["bullets"])
        assert "p_wild" in joined

    def test_volatile_pair_bullet_at_most_two(self):
        # Default top_n is 2 — even if many pairs are volatile we surface
        # at most 2 entries.
        for i, sp in enumerate((1, 9, 1, 9, 1), 1):
            rid = f"vp_n_{i:02d}"
            ep.save_comparison_result(
                rid,
                [_entry(f"px_{k}", sp=sp, ec=sp) for k in range(5)],
            )
        rids = [f"vp_n_{i:02d}" for i in range(1, 6)]
        out = narr_mod.summarize_runs(rids)
        # The volatile-pairs bullet text should mention at most two pairs.
        # We probe by counting the comma-separated entries in that bullet.
        volatile_bullet = next(
            b for b in out["bullets"] if "Top volatile pairs" in b
        )
        # "Top volatile pairs: a (...), b (...)."  →  exactly 2 entries.
        parts = [p for p in volatile_bullet.split(",") if "(" in p]
        assert len(parts) <= 2


# ===========================================================================
# F. Cluster narratives — per label
# ===========================================================================
class TestClusterNarratives:
    def test_stable_label_headline(self):
        info = {"members": ["s_00", "s_01", "s_02"],
                "label": "stable",
                "size": 3}
        out = narr_mod.summarize_cluster("c0", info)
        assert "stable" in out["headline"].lower()

    def test_upward_label_headline(self):
        info = {"members": ["u_00", "u_01", "u_02"],
                "label": "upward drift",
                "size": 3}
        out = narr_mod.summarize_cluster("c1", info)
        assert "upward" in out["headline"].lower()

    def test_downward_label_headline(self):
        info = {"members": ["d_00", "d_01"],
                "label": "downward drift",
                "size": 2}
        out = narr_mod.summarize_cluster("c2", info)
        assert "downward" in out["headline"].lower()

    def test_oscillation_label_headline(self):
        info = {"members": ["o_00", "o_01"],
                "label": "oscillation",
                "size": 2}
        out = narr_mod.summarize_cluster("c3", info)
        assert "oscillat" in out["headline"].lower()

    def test_anomaly_label_headline(self):
        info = {"members": ["a_00"], "label": "anomaly", "size": 1}
        out = narr_mod.summarize_cluster("c4", info)
        assert "anomalous" in out["headline"].lower()

    def test_cluster_shape_keys_locked(self):
        info = {"members": ["s_00"], "label": "stable", "size": 1}
        out = narr_mod.summarize_cluster("c0", info)
        assert set(out.keys()) == {"headline", "bullets", "details"}
        assert set(out["details"].keys()) == {
            "cluster_id", "label", "size",
            "representative_run", "mostly_anomalous",
        }


# ===========================================================================
# G. Cluster representative + size handling
# ===========================================================================
class TestClusterRepresentative:
    def test_explicit_representative_surfaced(self):
        info = {
            "members": ["s_00", "s_01", "s_02"],
            "label":   "stable",
            "size":    3,
            "representative": "s_01",
        }
        out = narr_mod.summarize_cluster("c0", info)
        assert out["details"]["representative_run"] == "s_01"
        assert any("s_01" in b for b in out["bullets"])

    def test_missing_representative_falls_back_alpha(self):
        info = {
            "members": ["s_02", "s_00", "s_01"],
            "label":   "stable",
            "size":    3,
        }
        out = narr_mod.summarize_cluster("c0", info)
        assert out["details"]["representative_run"] == "s_00"

    def test_missing_size_derives_from_members(self):
        info = {"members": ["a", "b", "c"], "label": "stable"}
        out = narr_mod.summarize_cluster("c0", info)
        assert out["details"]["size"] == 3

    def test_singleton_is_mostly_anomalous(self):
        info = {"members": ["only"], "label": "stable", "size": 1}
        out = narr_mod.summarize_cluster("c0", info)
        # Even when the label says "stable", a singleton is treated as
        # an outlier by the narrative layer.
        assert out["details"]["mostly_anomalous"] is True

    def test_non_singleton_stable_not_mostly_anomalous(self):
        info = {"members": ["a", "b", "c"], "label": "stable", "size": 3}
        out = narr_mod.summarize_cluster("c0", info)
        assert out["details"]["mostly_anomalous"] is False

    def test_anomaly_label_is_mostly_anomalous(self):
        info = {"members": ["a", "b"], "label": "anomaly", "size": 2}
        out = narr_mod.summarize_cluster("c0", info)
        assert out["details"]["mostly_anomalous"] is True

    def test_unit_2_output_round_trips(self):
        # Pass an actual cluster_summary entry through directly.
        rids = _seed_stable(n=4, sp=5)
        result = clust_mod.cluster_runs(rids)
        cid, info = next(iter(result["cluster_summary"].items()))
        out = narr_mod.summarize_cluster(cid, info)
        assert out["details"]["cluster_id"] == cid
        assert out["details"]["label"] == info["label"]
        assert out["details"]["size"] == info["size"]


# ===========================================================================
# H. Anomaly inventory narratives
# ===========================================================================
class TestAnomalyNarratives:
    def test_shape_keys_locked(self):
        rids = _seed_stable(n=5, sp=5)
        out = narr_mod.summarize_anomalies(rids)
        assert set(out.keys()) == {"headline", "bullets", "details"}
        assert set(out["details"].keys()) == {
            "num_runs", "num_anomalous", "top_anomalies", "reason_counts",
        }

    def test_clean_universe_headline_mentions_no_anomalies(self):
        rids = _seed_stable(n=5, sp=5)
        out = narr_mod.summarize_anomalies(rids)
        assert "no anomalies" in out["headline"].lower()

    def test_clean_universe_no_top_anomalies(self):
        rids = _seed_stable(n=5, sp=5)
        out = narr_mod.summarize_anomalies(rids)
        assert out["details"]["top_anomalies"] == []
        assert out["details"]["num_anomalous"] == 0

    def test_outlier_appears_in_top_anomalies(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_anomalies(rids)
        flagged_ids = {entry["run_id"] for entry in out["details"]["top_anomalies"]}
        assert "ost_outlier" in flagged_ids

    def test_outlier_headline_counts_runs(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_anomalies(rids)
        # Headline must mention the universe size.
        assert str(len(rids)) in out["headline"]


# ===========================================================================
# I. Top-N + reason grouping
# ===========================================================================
class TestTopNAndReasons:
    def test_top_anomalies_capped_at_five(self):
        # Seed 4 stable + 6 outliers → 6 should flag, but we only surface 5.
        stable = _seed_stable(prefix="cap_s", n=4, sp=5)
        outliers: list = []
        for i in range(6):
            rid = f"cap_out_{i}"
            ep.save_comparison_result(
                rid,
                [_entry("p_off", sp=0, ec=0,
                         sp_band="Fails core logic",
                         ec_band="Fails core logic")],
            )
            outliers.append(rid)
        rids = stable + outliers
        out = narr_mod.summarize_anomalies(rids)
        assert len(out["details"]["top_anomalies"]) <= 5

    def test_top_anomalies_sorted_score_desc(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_anomalies(rids)
        scores = [entry["score"] for entry in out["details"]["top_anomalies"]]
        assert scores == sorted(scores, reverse=True)

    def test_reason_counts_populated(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_anomalies(rids)
        assert isinstance(out["details"]["reason_counts"], dict)
        # Outlier is in a singleton cluster → at least one reason category.
        assert sum(out["details"]["reason_counts"].values()) >= 1

    def test_reason_bullets_one_per_category(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_anomalies(rids)
        # Count distinct reason phrases mentioned.
        phrases = list(narr_mod._REASON_PHRASE.values())
        mentioned = [p for p in phrases if any(p in b for b in out["bullets"])]
        # We expect at least one reason bullet for the outlier set.
        assert len(mentioned) >= 1

    def test_top_anomalies_have_required_keys(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_anomalies(rids)
        for entry in out["details"]["top_anomalies"]:
            assert set(entry.keys()) == {"run_id", "score", "level", "reasons"}


# ===========================================================================
# J. Legacy handling
# ===========================================================================
class TestLegacyHandling:
    def test_legacy_run_flagged_in_summarize_anomalies(
        self, _runs_dir_isolation,
    ):
        rids = _seed_stable(n=3, sp=5)
        _write_legacy(_runs_dir_isolation, "leg_1", [_entry("p1")])
        out = narr_mod.summarize_anomalies(rids + ["leg_1"])
        flagged_ids = {entry["run_id"] for entry in out["details"]["top_anomalies"]}
        assert "leg_1" in flagged_ids

    def test_legacy_run_reason_in_counts(self, _runs_dir_isolation):
        rids = _seed_stable(n=3, sp=5)
        _write_legacy(_runs_dir_isolation, "leg_x", [_entry("p1")])
        out = narr_mod.summarize_anomalies(rids + ["leg_x"])
        assert out["details"]["reason_counts"].get("legacy_run", 0) >= 1

    def test_legacy_in_summarize_runs_count_only_modern(
        self, _runs_dir_isolation,
    ):
        rids = _seed_stable(n=3, sp=5)
        _write_legacy(_runs_dir_isolation, "leg_n", [_entry("p1")])
        out = narr_mod.summarize_runs(rids + ["leg_n"])
        # num_runs is the input length; num_anomalies includes legacy.
        assert out["details"]["num_runs"] == len(rids) + 1
        assert out["details"]["num_anomalies"] >= 1


# ===========================================================================
# K. Validation
# ===========================================================================
class TestValidation:
    def test_summarize_runs_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            narr_mod.summarize_runs("nope")

    def test_summarize_runs_malformed_id_raises(self):
        with pytest.raises(ValueError):
            narr_mod.summarize_runs(["bad/id"])

    def test_summarize_runs_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            narr_mod.summarize_runs(["ghost"])

    def test_summarize_anomalies_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            narr_mod.summarize_anomalies("nope")

    def test_summarize_anomalies_malformed_id_raises(self):
        with pytest.raises(ValueError):
            narr_mod.summarize_anomalies(["bad/id"])

    def test_summarize_anomalies_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            narr_mod.summarize_anomalies(["ghost"])

    def test_summarize_cluster_empty_id_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            narr_mod.summarize_cluster("", {"members": ["a"], "label": "stable"})

    def test_summarize_cluster_non_string_id_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            narr_mod.summarize_cluster(123, {"members": ["a"], "label": "stable"})

    def test_summarize_cluster_non_dict_info_raises(self):
        with pytest.raises(ValueError, match="dict"):
            narr_mod.summarize_cluster("c0", "nope")

    def test_summarize_cluster_missing_members_raises(self):
        with pytest.raises(ValueError, match="members"):
            narr_mod.summarize_cluster("c0", {"label": "stable"})

    def test_summarize_cluster_missing_label_raises(self):
        with pytest.raises(ValueError, match="members.*label|label"):
            narr_mod.summarize_cluster("c0", {"members": ["a"]})

    def test_summarize_cluster_members_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            narr_mod.summarize_cluster("c0", {"members": "a", "label": "stable"})


# ===========================================================================
# L. Determinism
# ===========================================================================
class TestDeterminism:
    def test_summarize_runs_byte_equal(self):
        rids = _seed_stable(n=5, sp=5)
        a = narr_mod.summarize_runs(rids)
        b = narr_mod.summarize_runs(rids)
        assert a == b

    def test_summarize_anomalies_byte_equal(self):
        rids = _seed_outlier_set()
        a = narr_mod.summarize_anomalies(rids)
        b = narr_mod.summarize_anomalies(rids)
        assert a == b

    def test_summarize_cluster_byte_equal(self):
        info = {"members": ["a", "b", "c"], "label": "stable", "size": 3,
                "representative": "b"}
        a = narr_mod.summarize_cluster("c0", info)
        b = narr_mod.summarize_cluster("c0", info)
        assert a == b


# ===========================================================================
# M. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            narr_mod.summarize_runs,
            narr_mod.summarize_cluster,
            narr_mod.summarize_anomalies,
        ):
            assert callable(fn)

    def test_health_thresholds_locked(self):
        assert narr_mod._HEALTH_HIGH   == 0.7
        assert narr_mod._HEALTH_MEDIUM == 0.4

    def test_top_anomalies_n_locked(self):
        assert narr_mod._TOP_ANOMALIES_N == 5

    def test_top_volatile_pairs_n_locked(self):
        assert narr_mod._TOP_VOLATILE_PAIRS_N == 2

    def test_reason_phrase_vocabulary_locked(self):
        # All five Unit 5 reason strings are mapped.
        for r in ("low_similarity", "singleton_cluster",
                  "extreme_trend", "volatile_pairs", "legacy_run"):
            assert r in narr_mod._REASON_PHRASE


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(narr_mod)

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
        """Narrative is pure composition; verify every upstream unit
        appears in the source."""
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
# N. Consistency with underlying signals
# ===========================================================================
class TestConsistency:
    def test_num_runs_equals_input_length(self):
        rids = _seed_stable(n=5, sp=5)
        out = narr_mod.summarize_runs(rids)
        assert out["details"]["num_runs"] == len(rids)

    def test_health_matches_scoring_module(self):
        rids = _seed_upward(prefix="cons_up")
        out = narr_mod.summarize_runs(rids)
        assert out["details"]["overall_health"] == pytest.approx(
            score_mod.overall_health_score(rids),
        )

    def test_anomalies_count_matches_unit_5(self):
        rids = _seed_outlier_set()
        out = narr_mod.summarize_runs(rids)
        anom = anom_mod.detect_run_anomalies(rids)
        flagged = sum(
            1 for info in anom["runs"].values()
            if info["level"] != "none"
        )
        assert out["details"]["num_anomalies"] == flagged

    def test_dominant_cluster_label_in_locked_vocab(self):
        rids = _seed_stable(n=5, sp=5)
        out = narr_mod.summarize_runs(rids)
        assert out["details"]["dominant_cluster_label"] in (
            narr_mod._VALID_CLUSTER_LABELS
        )

    def test_dominant_trend_in_locked_vocab(self):
        rids = _seed_upward(prefix="cons_tr")
        out = narr_mod.summarize_runs(rids)
        assert out["details"]["dominant_trend"] in narr_mod._TREND_HEADLINE

    def test_health_value_within_unit_interval(self):
        for seeder in (_seed_stable, _seed_upward, _seed_downward,
                       _seed_volatile):
            # Use a unique prefix per call so seeded run_ids don't collide.
            rids = seeder(prefix=f"unit_{seeder.__name__[-5:]}") \
                if seeder is not _seed_stable else seeder(prefix="unit_stb",
                                                          n=3, sp=5)
            out = narr_mod.summarize_runs(rids)
            assert 0.0 <= out["details"]["overall_health"] <= 1.0

    def test_health_bullet_value_matches_details(self):
        rids = _seed_stable(prefix="hbm", n=5, sp=5)
        out = narr_mod.summarize_runs(rids)
        health = out["details"]["overall_health"]
        # The health bullet always uses two decimal places.
        rendered = f"{health:.2f}"
        assert any(rendered in b for b in out["bullets"])

    def test_anomaly_inventory_counts_match_runs(self):
        rids = _seed_outlier_set()
        a_out = narr_mod.summarize_anomalies(rids)
        r_out = narr_mod.summarize_runs(rids)
        assert a_out["details"]["num_anomalous"] == \
               r_out["details"]["num_anomalies"]
