"""
Tests for ELINS4 Unit 15 — intelligence feed engine.

Layered coverage (>= 50 tests, target ~60):
    A. Top-level shape / locked keys
    B. Per-entry shape
    C. Ordering — newest first
    D. Severity mapping
    E. Tag vocabulary
    F. Headline content (deterministic strings)
    G. Limit handling
    H. Signal extraction matches Unit 13 timeline
    I. Legacy run handling
    J. feed_entry_for_run single-run helper
    K. Determinism (byte-equal repeats)
    L. Validation
    M. Empty DB
    N. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_feed as feed_mod
import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
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


def _seed_outlier_set(prefix="o", fixed_clock=None):
    if fixed_clock is not None:
        fixed_clock([
            f"2024-{m:02d}-01T10:00:00+00:00" for m in range(1, 7)
        ])
    stable = []
    for i in range(5):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=5)])
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
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        assert set(out.keys()) == {"entries", "meta"}

    def test_meta_keys_locked(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        assert set(out["meta"].keys()) == {"limit", "count"}

    def test_meta_limit_default(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        assert out["meta"]["limit"] == 50

    def test_meta_count_matches_entries_length(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        assert out["meta"]["count"] == len(out["entries"])

    def test_entries_is_list(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        assert isinstance(out["entries"], list)


# ===========================================================================
# B. Per-entry shape
# ===========================================================================
class TestPerEntryShape:
    def test_entry_keys_locked(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        entry = out["entries"][0]
        assert set(entry.keys()) == {
            "run_id", "timestamp", "headline",
            "severity", "tags", "details",
        }

    def test_entry_details_keys_locked(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        details = out["entries"][0]["details"]
        assert set(details.keys()) == {
            "health", "anomaly_level", "cluster_label", "trend",
        }

    def test_entry_tags_is_list(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        for e in out["entries"]:
            assert isinstance(e["tags"], list)

    def test_entry_severity_in_locked_vocab(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        for e in out["entries"]:
            assert e["severity"] in ("info", "warning", "critical")

    def test_entry_headline_non_empty(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        for e in out["entries"]:
            assert isinstance(e["headline"], str)
            assert e["headline"].strip() != ""


# ===========================================================================
# C. Ordering — newest first
# ===========================================================================
class TestOrdering:
    def test_entries_newest_first(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        # The youngest-timestamp run is rids[-1] → should appear first
        # in the feed.
        ordered_ids = [e["run_id"] for e in out["entries"]]
        assert ordered_ids[0] == rids[-1]
        assert ordered_ids[-1] == rids[0]

    def test_legacy_runs_fall_to_end(
        self, _runs_dir_isolation, fixed_clock,
    ):
        modern = _seed_stable(prefix="ord_m", n=3, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "ord_leg", [_entry("p1")])
        out = feed_mod.build_intelligence_feed()
        ordered_ids = [e["run_id"] for e in out["entries"]]
        # Legacy run has no timestamp → query_runs sorts it last.
        assert ordered_ids[-1] == "ord_leg"
        for rid in modern:
            assert rid in ordered_ids


# ===========================================================================
# D. Severity mapping
# ===========================================================================
class TestSeverityMapping:
    def test_clean_universe_all_info(self, fixed_clock):
        _seed_stable(n=4, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        for e in out["entries"]:
            assert e["severity"] == "info"

    def test_outlier_at_least_warning(self, fixed_clock):
        _seed_outlier_set(fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        outlier_entry = next(e for e in out["entries"] if e["run_id"] == "o_out")
        # Outlier fires medium/high → warning/critical severity.
        assert outlier_entry["severity"] in ("warning", "critical")

    def test_high_anomaly_yields_critical(self):
        # Directly test the severity helper.
        assert feed_mod._severity_for_entry("high", "anomaly") == "critical"

    def test_medium_anomaly_yields_warning(self):
        assert feed_mod._severity_for_entry("medium", "stable") == "warning"

    def test_none_anomaly_yields_info(self):
        assert feed_mod._severity_for_entry("none", "stable") == "info"


# ===========================================================================
# E. Tag vocabulary
# ===========================================================================
class TestTags:
    def test_clean_stable_run_no_anomaly_tag(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        for e in out["entries"]:
            assert "anomaly" not in e["tags"]

    def test_outlier_has_anomaly_tag(self, fixed_clock):
        _seed_outlier_set(fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        outlier_entry = next(e for e in out["entries"] if e["run_id"] == "o_out")
        assert "anomaly" in outlier_entry["tags"]

    def test_legacy_run_has_legacy_tag(
        self, _runs_dir_isolation, fixed_clock,
    ):
        _seed_stable(prefix="lt", n=2, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "lt_leg", [_entry("p1")])
        out = feed_mod.build_intelligence_feed()
        leg = next(e for e in out["entries"] if e["run_id"] == "lt_leg")
        assert "legacy" in leg["tags"]

    def test_tags_sorted_alphabetically(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        for e in out["entries"]:
            assert e["tags"] == sorted(e["tags"])

    def test_upward_cluster_tag_when_label(self):
        # Helper-level: with cluster label "upward drift", we get the
        # locked tag.
        tags = feed_mod._tags_for_entry("none", "upward drift", False)
        assert "upward_cluster" in tags


# ===========================================================================
# F. Headline content
# ===========================================================================
class TestHeadlines:
    def test_clean_stable_headline_mentions_stable(self, fixed_clock):
        rids = _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        # At least one entry mentions "stable" in its headline.
        joined = " ".join(e["headline"] for e in out["entries"])
        assert "stable" in joined.lower() or "no significant signal" in joined.lower()

    def test_outlier_headline_mentions_anomaly(self, fixed_clock):
        _seed_outlier_set(fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        outlier = next(e for e in out["entries"] if e["run_id"] == "o_out")
        if outlier["details"]["anomaly_level"] != "none":
            assert "anomaly" in outlier["headline"].lower()

    def test_legacy_headline_mentions_legacy(
        self, _runs_dir_isolation, fixed_clock,
    ):
        _seed_stable(prefix="lh", n=2, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "lh_leg", [_entry("p1")])
        out = feed_mod.build_intelligence_feed()
        leg = next(e for e in out["entries"] if e["run_id"] == "lh_leg")
        assert "legacy" in leg["headline"].lower()

    def test_headline_mentions_run_id(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        for e in out["entries"]:
            assert e["run_id"] in e["headline"]


# ===========================================================================
# G. Limit handling
# ===========================================================================
class TestLimit:
    def test_limit_caps_entries(self, fixed_clock):
        _seed_stable(n=5, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed(limit=2)
        assert len(out["entries"]) == 2

    def test_limit_returned_in_meta(self, fixed_clock):
        _seed_stable(n=5, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed(limit=3)
        assert out["meta"]["limit"] == 3

    def test_limit_larger_than_universe_returns_all(self, fixed_clock):
        _seed_stable(n=3, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed(limit=100)
        assert out["meta"]["count"] == 3


# ===========================================================================
# H. Signal extraction matches Unit 13 timeline
# ===========================================================================
class TestSignalExtraction:
    def test_health_matches_timeline(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        timeline = tl_mod.build_intelligence_timeline(rids)
        timeline_by_id = {e["run_id"]: e for e in timeline["timeline"]}
        for entry in out["entries"]:
            tl_entry = timeline_by_id[entry["run_id"]]
            assert entry["details"]["health"] == pytest.approx(
                tl_entry["health"],
            )

    def test_cluster_label_matches_timeline(self, fixed_clock):
        rids = _seed_stable(n=4, fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        timeline = tl_mod.build_intelligence_timeline(rids)
        timeline_by_id = {e["run_id"]: e for e in timeline["timeline"]}
        for entry in out["entries"]:
            tl_entry = timeline_by_id[entry["run_id"]]
            assert entry["details"]["cluster_label"] == tl_entry["cluster_label"]

    def test_anomaly_level_matches_timeline(self, fixed_clock):
        _seed_outlier_set(fixed_clock=fixed_clock)
        out = feed_mod.build_intelligence_feed()
        # Universal universe — recompute via timeline over chronological order.
        chrono_ids = list(reversed([e["run_id"] for e in out["entries"]]))
        timeline = tl_mod.build_intelligence_timeline(chrono_ids)
        tl_by_id = {e["run_id"]: e for e in timeline["timeline"]}
        for entry in out["entries"]:
            assert entry["details"]["anomaly_level"] == \
                   tl_by_id[entry["run_id"]]["anomaly_level"]


# ===========================================================================
# I. Legacy run handling
# ===========================================================================
class TestLegacy:
    def test_legacy_entry_has_legacy_tag(
        self, _runs_dir_isolation, fixed_clock,
    ):
        _seed_stable(prefix="lg", n=2, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "lg_leg", [_entry("p1")])
        out = feed_mod.build_intelligence_feed()
        leg = next(e for e in out["entries"] if e["run_id"] == "lg_leg")
        assert "legacy" in leg["tags"]

    def test_legacy_entry_timestamp_none(
        self, _runs_dir_isolation, fixed_clock,
    ):
        _seed_stable(prefix="lt2", n=2, fixed_clock=fixed_clock)
        _write_legacy(_runs_dir_isolation, "lt2_leg", [_entry("p1")])
        out = feed_mod.build_intelligence_feed()
        leg = next(e for e in out["entries"] if e["run_id"] == "lt2_leg")
        assert leg["timestamp"] is None


# ===========================================================================
# J. feed_entry_for_run single-run helper
# ===========================================================================
class TestFeedEntryForRun:
    def test_returns_locked_entry_shape(self, fixed_clock):
        rids = _seed_stable(prefix="sg", n=1, fixed_clock=fixed_clock)
        out = feed_mod.feed_entry_for_run(rids[0])
        assert set(out.keys()) == {
            "run_id", "timestamp", "headline",
            "severity", "tags", "details",
        }

    def test_run_id_matches(self, fixed_clock):
        rids = _seed_stable(prefix="sm", n=1, fixed_clock=fixed_clock)
        out = feed_mod.feed_entry_for_run(rids[0])
        assert out["run_id"] == rids[0]

    def test_severity_info_for_clean_run(self, fixed_clock):
        rids = _seed_stable(prefix="si", n=1, fixed_clock=fixed_clock)
        out = feed_mod.feed_entry_for_run(rids[0])
        assert out["severity"] == "info"

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            feed_mod.feed_entry_for_run("ghost")

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            feed_mod.feed_entry_for_run("bad/id")


# ===========================================================================
# K. Determinism (byte-equal repeats)
# ===========================================================================
class TestDeterminism:
    def test_feed_byte_equal(self, fixed_clock):
        _seed_stable(n=4, fixed_clock=fixed_clock)
        a = feed_mod.build_intelligence_feed()
        b = feed_mod.build_intelligence_feed()
        assert a == b

    def test_entry_for_run_byte_equal(self, fixed_clock):
        rids = _seed_stable(prefix="dd", n=1, fixed_clock=fixed_clock)
        a = feed_mod.feed_entry_for_run(rids[0])
        b = feed_mod.feed_entry_for_run(rids[0])
        assert a == b

    def test_empty_byte_equal(self):
        a = feed_mod.build_intelligence_feed()
        b = feed_mod.build_intelligence_feed()
        assert a == b


# ===========================================================================
# L. Validation
# ===========================================================================
class TestValidation:
    def test_limit_zero_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            feed_mod.build_intelligence_feed(limit=0)

    def test_limit_negative_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            feed_mod.build_intelligence_feed(limit=-3)

    def test_limit_bool_raises(self):
        with pytest.raises(ValueError, match="positive int"):
            feed_mod.build_intelligence_feed(limit=True)

    def test_limit_float_raises(self):
        with pytest.raises(ValueError, match="positive int"):
            feed_mod.build_intelligence_feed(limit=5.0)

    def test_limit_string_raises(self):
        with pytest.raises(ValueError, match="positive int"):
            feed_mod.build_intelligence_feed(limit="five")


# ===========================================================================
# M. Empty DB
# ===========================================================================
class TestEmptyDB:
    def test_empty_db_returns_well_formed(self):
        out = feed_mod.build_intelligence_feed()
        assert out["entries"] == []
        assert out["meta"]["count"] == 0
        assert out["meta"]["limit"] == 50


# ===========================================================================
# N. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            feed_mod.build_intelligence_feed,
            feed_mod.feed_entry_for_run,
        ):
            assert callable(fn)

    def test_default_limit_locked(self):
        assert feed_mod.DEFAULT_LIMIT == 50

    def test_severity_vocabulary_locked(self):
        assert feed_mod._SEV_INFO == "info"
        assert feed_mod._SEV_WARNING == "warning"
        assert feed_mod._SEV_CRITICAL == "critical"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(feed_mod)

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

    def test_composes_unit_13_and_query_runs(self):
        src = self._code_only()
        assert "build_intelligence_timeline" in src
        assert "query_runs" in src
