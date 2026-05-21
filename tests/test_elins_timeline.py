"""
Tests for ELINS3 Unit 13 — intelligence timeline engine.

Layered coverage (>= 50 tests, target ~60):
    A. Top-level shape / locked keys
    B. Per-entry shape
    C. Chronological ordering preservation
    D. Signal extraction — health / cluster / anomaly / trend
    E. Narrative — short, deterministic, descriptive
    F. Summary aggregation
    G. Small N (0, 1, 2 runs)
    H. Legacy run handling
    I. timeline_for_run single-run helper
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

import elins_anomalies as anom_mod
import elins_clustering as clust_mod
import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
import elins_scoring as score_mod
import elins_timeline as tl_mod


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


def _seed_stable(prefix="s", n=5, sp=5, ec=5, fixed_clock=None):
    if fixed_clock is not None:
        fixed_clock([
            f"2024-{m:02d}-01T10:00:00+00:00" for m in range(1, n + 1)
        ])
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec),
                                          _entry("p2", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


def _seed_upward(prefix="u", fixed_clock=None):
    if fixed_clock is not None:
        fixed_clock([
            f"2024-{m:02d}-01T10:00:00+00:00" for m in range(1, 6)
        ])
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 7, 9), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_outlier_set(prefix="o", fixed_clock=None):
    if fixed_clock is not None:
        fixed_clock([
            f"2024-{m:02d}-01T10:00:00+00:00" for m in range(1, 7)
        ])
    stable = []
    for i in range(5):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=5, ec=5)])
        stable.append(rid)
    ep.save_comparison_result(
        f"{prefix}_out",
        [_entry("p9", sp=0, ec=0,
                 sp_band="Fails core logic",
                 ec_band="Fails core logic")],
    )
    return stable + [f"{prefix}_out"]


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_top_level_keys(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert set(out.keys()) == {"timeline", "summary"}

    def test_timeline_is_list(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert isinstance(out["timeline"], list)

    def test_summary_is_dict(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert isinstance(out["summary"], dict)

    def test_summary_keys_locked(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert set(out["summary"].keys()) == {
            "num_runs", "num_anomalies",
            "dominant_trend", "dominant_cluster",
        }


# ===========================================================================
# B. Per-entry shape
# ===========================================================================
class TestPerEntryShape:
    def test_entry_keys_locked(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        entry = out["timeline"][0]
        assert set(entry.keys()) == {
            "run_id", "timestamp", "trend",
            "cluster", "cluster_label",
            "anomaly_level", "health",
            "is_legacy", "narrative",
        }

    def test_entry_run_id_matches_input(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert [e["run_id"] for e in out["timeline"]] == rids

    def test_entry_timestamp_iso_string(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            assert isinstance(e["timestamp"], str)
            assert "2024" in e["timestamp"]

    def test_entry_health_in_unit_interval(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            assert 0.0 <= e["health"] <= 1.0

    def test_entry_anomaly_level_in_vocab(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            assert e["anomaly_level"] in ("none", "medium", "high")

    def test_entry_is_legacy_bool(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            assert isinstance(e["is_legacy"], bool)


# ===========================================================================
# C. Chronological ordering preservation
# ===========================================================================
class TestOrdering:
    def test_order_preserved_alpha_input(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert [e["run_id"] for e in out["timeline"]] == rids

    def test_order_preserved_reverse_input(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        reversed_rids = list(reversed(rids))
        out = tl_mod.build_intelligence_timeline(reversed_rids)
        assert [e["run_id"] for e in out["timeline"]] == reversed_rids


# ===========================================================================
# D. Signal extraction — health / cluster / anomaly / trend
# ===========================================================================
class TestSignalExtraction:
    def test_health_matches_run_score(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        raw = score_mod.compute_run_scores(rids)["runs"]
        for e in out["timeline"]:
            assert e["health"] == pytest.approx(raw[e["run_id"]]["score"])

    def test_cluster_matches_assignment(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        raw = clust_mod.cluster_runs(rids)["assignments"]
        for e in out["timeline"]:
            assert e["cluster"] == raw[e["run_id"]]

    def test_cluster_label_in_locked_vocab(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        valid = {"stable", "upward drift", "downward drift",
                 "oscillation", "anomaly"}
        for e in out["timeline"]:
            assert e["cluster_label"] in valid

    def test_anomaly_level_matches_unit_5(self, fixed_clock):
        rids = _seed_outlier_set(prefix="ol", fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        raw = anom_mod.detect_run_anomalies(rids)["runs"]
        for e in out["timeline"]:
            assert e["anomaly_level"] == raw[e["run_id"]]["level"]

    def test_trend_insufficient_for_first_two(self, fixed_clock):
        rids = _seed_upward(fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert out["timeline"][0]["trend"] == "insufficient_data"
        assert out["timeline"][1]["trend"] == "insufficient_data"

    def test_trend_classifies_after_three(self, fixed_clock):
        rids = _seed_upward(fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        # By the 3rd run, trend should be a real class (not insufficient).
        assert out["timeline"][2]["trend"] != "insufficient_data"

    def test_outlier_anomaly_level_high_or_medium(self, fixed_clock):
        rids = _seed_outlier_set(prefix="os", fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        outlier_entry = next(
            e for e in out["timeline"] if e["run_id"] == "os_out"
        )
        assert outlier_entry["anomaly_level"] in ("medium", "high")


# ===========================================================================
# E. Narrative — short, deterministic, descriptive
# ===========================================================================
class TestNarrative:
    def test_narrative_non_empty_string(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            assert isinstance(e["narrative"], str)
            assert e["narrative"].strip() != ""

    def test_narrative_mentions_run_id(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            assert e["run_id"] in e["narrative"]

    def test_narrative_mentions_health_value(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            rendered = f"{e['health']:.2f}"
            assert rendered in e["narrative"]

    def test_narrative_mentions_cluster_label_modern(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            assert e["cluster_label"] in e["narrative"]

    def test_narrative_length_bounded(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            # Loose upper bound — narrative is a short summary, not prose.
            assert len(e["narrative"]) <= 200

    def test_anomaly_narrative_mentions_anomaly(self, fixed_clock):
        rids = _seed_outlier_set(prefix="an", fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        outlier = next(
            e for e in out["timeline"] if e["run_id"] == "an_out"
        )
        if outlier["anomaly_level"] != "none":
            assert "anomaly" in outlier["narrative"]


# ===========================================================================
# F. Summary aggregation
# ===========================================================================
class TestSummary:
    def test_num_runs_matches_timeline_length(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert out["summary"]["num_runs"] == len(out["timeline"])

    def test_clean_universe_zero_anomalies(self, fixed_clock):
        rids = _seed_stable(n=5, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert out["summary"]["num_anomalies"] == 0

    def test_outlier_set_at_least_one_anomaly(self, fixed_clock):
        rids = _seed_outlier_set(prefix="ag", fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert out["summary"]["num_anomalies"] >= 1

    def test_dominant_trend_upward_for_upward_seq(self, fixed_clock):
        rids = _seed_upward(prefix="udo", fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        # The prefix trends become 'monotonic_increase' from the 3rd run onward.
        assert out["summary"]["dominant_trend"] == "monotonic_increase"

    def test_dominant_cluster_in_locked_vocab(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        valid = {"stable", "upward drift", "downward drift",
                 "oscillation", "anomaly"}
        assert out["summary"]["dominant_cluster"] in valid


# ===========================================================================
# G. Small N (0, 1, 2 runs)
# ===========================================================================
class TestSmallN:
    def test_empty_input(self):
        out = tl_mod.build_intelligence_timeline([])
        assert out["timeline"] == []
        assert out["summary"]["num_runs"] == 0
        assert out["summary"]["num_anomalies"] == 0
        assert out["summary"]["dominant_trend"] == "insufficient_data"

    def test_one_run(self, fixed_clock):
        rids = _seed_stable(prefix="one", n=1, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        assert len(out["timeline"]) == 1
        assert out["timeline"][0]["trend"] == "insufficient_data"

    def test_two_runs_trend_still_insufficient(self, fixed_clock):
        rids = _seed_stable(prefix="two", n=2, fixed_clock=fixed_clock)
        out = tl_mod.build_intelligence_timeline(rids)
        for e in out["timeline"]:
            assert e["trend"] == "insufficient_data"


# ===========================================================================
# H. Legacy run handling
# ===========================================================================
class TestLegacy:
    def test_legacy_flagged_is_legacy_true(
        self, _runs_dir_isolation, fixed_clock,
    ):
        rids = _seed_stable(prefix="lg", n=3, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "lg_leg", [_entry("p1")])
        out = tl_mod.build_intelligence_timeline(rids + ["lg_leg"])
        leg_entry = next(
            e for e in out["timeline"] if e["run_id"] == "lg_leg"
        )
        assert leg_entry["is_legacy"] is True

    def test_legacy_timestamp_none(
        self, _runs_dir_isolation, fixed_clock,
    ):
        rids = _seed_stable(prefix="lt", n=3, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "lt_leg", [_entry("p1")])
        out = tl_mod.build_intelligence_timeline(rids + ["lt_leg"])
        leg_entry = next(
            e for e in out["timeline"] if e["run_id"] == "lt_leg"
        )
        assert leg_entry["timestamp"] is None

    def test_legacy_narrative_calls_out_legacy(
        self, _runs_dir_isolation, fixed_clock,
    ):
        rids = _seed_stable(prefix="ln", n=3, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "ln_leg", [_entry("p1")])
        out = tl_mod.build_intelligence_timeline(rids + ["ln_leg"])
        leg_entry = next(
            e for e in out["timeline"] if e["run_id"] == "ln_leg"
        )
        assert "legacy" in leg_entry["narrative"].lower()

    def test_legacy_appears_in_timeline_in_input_order(
        self, _runs_dir_isolation, fixed_clock,
    ):
        rids = _seed_stable(prefix="lo", n=2, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "lo_leg", [_entry("p1")])
        out = tl_mod.build_intelligence_timeline(
            [rids[0], "lo_leg", rids[1]],
        )
        # Input order preserved — legacy run sits in the middle.
        assert [e["run_id"] for e in out["timeline"]] == [
            rids[0], "lo_leg", rids[1],
        ]


# ===========================================================================
# I. timeline_for_run single-run helper
# ===========================================================================
class TestTimelineForRun:
    def test_returns_per_entry_shape(self, fixed_clock):
        rids = _seed_stable(prefix="sg", n=1, fixed_clock=fixed_clock)
        out = tl_mod.timeline_for_run(rids[0])
        assert set(out.keys()) == {
            "run_id", "timestamp", "trend",
            "cluster", "cluster_label",
            "anomaly_level", "health",
            "is_legacy", "narrative",
        }

    def test_run_id_matches_request(self, fixed_clock):
        rids = _seed_stable(prefix="sm", n=1, fixed_clock=fixed_clock)
        out = tl_mod.timeline_for_run(rids[0])
        assert out["run_id"] == rids[0]

    def test_single_run_trend_is_insufficient(self, fixed_clock):
        rids = _seed_stable(prefix="si", n=1, fixed_clock=fixed_clock)
        out = tl_mod.timeline_for_run(rids[0])
        assert out["trend"] == "insufficient_data"

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            tl_mod.timeline_for_run("ghost")

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            tl_mod.timeline_for_run("bad/id")


# ===========================================================================
# J. Determinism (byte-equal repeats)
# ===========================================================================
class TestDeterminism:
    def test_build_byte_equal(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        a = tl_mod.build_intelligence_timeline(rids)
        b = tl_mod.build_intelligence_timeline(rids)
        assert a == b

    def test_for_run_byte_equal(self, fixed_clock):
        rids = _seed_stable(prefix="dd", n=1, fixed_clock=fixed_clock)
        a = tl_mod.timeline_for_run(rids[0])
        b = tl_mod.timeline_for_run(rids[0])
        assert a == b

    def test_empty_byte_equal(self):
        a = tl_mod.build_intelligence_timeline([])
        b = tl_mod.build_intelligence_timeline([])
        assert a == b


# ===========================================================================
# K. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            tl_mod.build_intelligence_timeline("nope")

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            tl_mod.build_intelligence_timeline(["bad/id"])

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            tl_mod.build_intelligence_timeline(["ghost"])


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            tl_mod.build_intelligence_timeline,
            tl_mod.timeline_for_run,
        ):
            assert callable(fn)

    def test_health_thresholds_locked(self):
        assert tl_mod._HEALTH_HIGH   == 0.7
        assert tl_mod._HEALTH_MEDIUM == 0.4


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(tl_mod)

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

    def test_composes_units_2_3_5_6_7(self):
        src = self._code_only()
        for required in (
            "cluster_runs",            # Unit 2
            "trend_for_run_sequence",  # Unit 3
            "detect_run_anomalies",    # Unit 5
            "compute_run_scores",      # Unit 6
        ):
            assert required in src
