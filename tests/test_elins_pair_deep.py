"""
Tests for ELINS5 Unit 17 — pair-level deep analytics.

Layered coverage (>= 50 tests, target ~60):
    A. Top-level shape / locked keys
    B. Trajectory shape + Unit 4 parity
    C. Spike detection
    D. Drop detection
    E. Volatility event detection
    F. Narrative content + tone
    G. pair_deep_all helper
    H. Missing pair handling
    I. Small-N + legacy handling
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

import elins_multi_summary as msum
import elins_pair_deep as pd_mod
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


def _seed_stable(prefix="s", n=4, sp=5, ec=5):
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


def _seed_upward_pair(prefix="up"):
    """5 runs with p1 magnitudes climbing 1→9 in even steps."""
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 7, 9), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_downward_pair(prefix="dn"):
    """5 runs with p1 magnitudes dropping 9→1."""
    rids: list = []
    for i, sp in enumerate((9, 7, 5, 3, 1), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_spike_pair(prefix="sp"):
    """5 runs where p1 jumps from 1 → 9 in a single transition,
    triggering a spike (delta = 8 > 4.0 threshold)."""
    rids: list = []
    for i, sp in enumerate((1, 1, 9, 9, 9), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_drop_pair(prefix="dp"):
    """Mirror — 5 runs where p1 plunges from 9 → 1 in one transition."""
    rids: list = []
    for i, sp in enumerate((9, 9, 1, 1, 1), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_volatile_pair(prefix="vp"):
    """5 runs oscillating 1, 9, 1, 9, 1 — multiple strong transitions."""
    rids: list = []
    for i, sp in enumerate((1, 9, 1, 9, 1), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_top_level_keys(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert set(out.keys()) == {
            "pair_id", "trajectory", "anomalies", "narrative",
        }

    def test_trajectory_keys_locked(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert set(out["trajectory"].keys()) == {
            "direction_over_time", "magnitude_over_time",
            "severity_over_time", "stability_score",
            "volatility_score", "trend_direction",
        }

    def test_anomalies_keys_locked(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert set(out["anomalies"].keys()) == {
            "spikes", "drops", "volatility_events",
        }

    def test_narrative_keys_locked(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert set(out["narrative"].keys()) == {"headline", "bullets"}

    def test_pair_id_echoed(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert out["pair_id"] == "p1"


# ===========================================================================
# B. Trajectory shape + Unit 4 parity
# ===========================================================================
class TestTrajectoryParity:
    def test_magnitude_series_matches_unit_4(self):
        rids = _seed_upward_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        raw = msum.multi_run_summary(rids)["pair_summaries"]["p1"]
        assert out["trajectory"]["magnitude_over_time"] == \
               raw["magnitude_over_time"]

    def test_direction_series_matches_unit_4(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        raw = msum.multi_run_summary(rids)["pair_summaries"]["p1"]
        assert out["trajectory"]["direction_over_time"] == \
               raw["direction_over_time"]

    def test_severity_series_matches_unit_4(self):
        rids = _seed_spike_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        raw = msum.multi_run_summary(rids)["pair_summaries"]["p1"]
        assert out["trajectory"]["severity_over_time"] == \
               raw["severity_over_time"]

    def test_stability_score_matches_unit_4(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        raw = msum.multi_run_summary(rids)["pair_summaries"]["p1"]
        assert out["trajectory"]["stability_score"] == pytest.approx(
            raw["stability_score"],
        )

    def test_volatility_score_matches_unit_4(self):
        rids = _seed_volatile_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        raw = msum.multi_run_summary(rids)["pair_summaries"]["p1"]
        assert out["trajectory"]["volatility_score"] == pytest.approx(
            raw["volatility_score"],
        )

    def test_trend_direction_matches_unit_4(self):
        rids = _seed_upward_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        raw = msum.multi_run_summary(rids)["pair_summaries"]["p1"]
        assert out["trajectory"]["trend_direction"] == raw["trend_direction"]


# ===========================================================================
# C. Spike detection
# ===========================================================================
class TestSpikes:
    def test_spike_fires_on_big_upward_jump(self):
        rids = _seed_spike_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert len(out["anomalies"]["spikes"]) >= 1

    def test_spike_entry_keys_locked(self):
        rids = _seed_spike_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        for entry in out["anomalies"]["spikes"]:
            assert set(entry.keys()) == {"run_id", "delta", "magnitude"}

    def test_spike_delta_positive(self):
        rids = _seed_spike_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        for entry in out["anomalies"]["spikes"]:
            assert entry["delta"] > 0

    def test_no_spike_on_stable_universe(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert out["anomalies"]["spikes"] == []

    def test_spike_threshold_locked(self):
        # 1 -> 9 is delta = 8 > threshold (4.0).
        rids = _seed_spike_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        spike = out["anomalies"]["spikes"][0]
        assert spike["delta"] > pd_mod._STRONG_SEVERITY_THRESHOLD


# ===========================================================================
# D. Drop detection
# ===========================================================================
class TestDrops:
    def test_drop_fires_on_big_downward_jump(self):
        rids = _seed_drop_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert len(out["anomalies"]["drops"]) >= 1

    def test_drop_entry_keys_locked(self):
        rids = _seed_drop_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        for entry in out["anomalies"]["drops"]:
            assert set(entry.keys()) == {"run_id", "delta", "magnitude"}

    def test_drop_delta_negative(self):
        rids = _seed_drop_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        for entry in out["anomalies"]["drops"]:
            assert entry["delta"] < 0

    def test_no_drop_on_stable_universe(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert out["anomalies"]["drops"] == []

    def test_no_drop_on_upward_pair(self):
        rids = _seed_upward_pair(prefix="up_nd")
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert out["anomalies"]["drops"] == []


# ===========================================================================
# E. Volatility event detection
# ===========================================================================
class TestVolatilityEvents:
    def test_events_fire_on_volatile_pair(self):
        rids = _seed_volatile_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert len(out["anomalies"]["volatility_events"]) >= 1

    def test_event_entry_keys_locked(self):
        rids = _seed_volatile_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        for entry in out["anomalies"]["volatility_events"]:
            assert set(entry.keys()) == {"run_id", "severity"}

    def test_event_severity_is_strong(self):
        rids = _seed_volatile_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        for entry in out["anomalies"]["volatility_events"]:
            assert entry["severity"] == "strong"

    def test_no_event_on_stable_universe(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert out["anomalies"]["volatility_events"] == []


# ===========================================================================
# F. Narrative content + tone
# ===========================================================================
class TestNarrative:
    def test_headline_mentions_pair_id(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert "p1" in out["narrative"]["headline"]

    def test_high_stability_headline(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        # Stable universe → stability = 1.0, high band → "improving".
        assert "improving" in out["narrative"]["headline"].lower()

    def test_low_stability_headline_or_moderate(self):
        # Volatile universe → low stability → "low stability" headline.
        rids = _seed_volatile_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert ("low" in out["narrative"]["headline"].lower()
                or "moderate" in out["narrative"]["headline"].lower())

    def test_bullets_non_empty(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        assert isinstance(out["narrative"]["bullets"], list)
        assert len(out["narrative"]["bullets"]) >= 1
        for b in out["narrative"]["bullets"]:
            assert isinstance(b, str)
            assert b.strip() != ""

    def test_bullets_mention_trend_direction(self):
        rids = _seed_upward_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        joined = " ".join(out["narrative"]["bullets"])
        assert "upward" in joined.lower()

    def test_bullets_mention_no_spikes_when_stable(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        joined = " ".join(out["narrative"]["bullets"]).lower()
        assert "no" in joined and "spike" in joined

    def test_bullets_mention_spike_counts_when_spiky(self):
        rids = _seed_spike_pair()
        out = pd_mod.pair_deep_analysis(rids, "p1")
        joined = " ".join(out["narrative"]["bullets"]).lower()
        assert "spike" in joined


# ===========================================================================
# G. pair_deep_all helper
# ===========================================================================
class TestPairDeepAll:
    def test_top_level_keys_locked(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_all(rids)
        assert set(out.keys()) == {"pairs", "run_ids"}

    def test_pairs_keyed_by_pair_id(self):
        # Add a second pair to verify the union behaviour.
        rids: list = []
        for i, sp in enumerate((1, 3, 5), 1):
            rid = f"two_p_{i:02d}"
            ep.save_comparison_result(
                rid, [_entry("p1", sp=sp), _entry("p2", sp=10 - sp)],
            )
            rids.append(rid)
        out = pd_mod.pair_deep_all(rids)
        assert set(out["pairs"].keys()) == {"p1", "p2"}

    def test_pair_entry_shape(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_all(rids)
        for pid, data in out["pairs"].items():
            assert set(data.keys()) == {
                "pair_id", "trajectory", "anomalies", "narrative",
            }

    def test_pairs_sorted_alphabetically(self):
        rids: list = []
        for i, sp in enumerate((1, 3, 5), 1):
            rid = f"ord_{i:02d}"
            ep.save_comparison_result(
                rid,
                [
                    _entry("zeta",  sp=sp),
                    _entry("alpha", sp=sp),
                    _entry("mid",   sp=sp),
                ],
            )
            rids.append(rid)
        out = pd_mod.pair_deep_all(rids)
        assert list(out["pairs"].keys()) == ["alpha", "mid", "zeta"]


# ===========================================================================
# H. Missing pair handling
# ===========================================================================
class TestMissingPair:
    def test_missing_pair_returns_empty_shape(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "no_such_pair")
        assert out["pair_id"] == "no_such_pair"
        assert out["trajectory"]["magnitude_over_time"] == []
        assert out["trajectory"]["stability_score"] == 0.0
        assert out["anomalies"]["spikes"] == []

    def test_missing_pair_narrative_mentions_insufficient(self):
        rids = _seed_stable(n=4)
        out = pd_mod.pair_deep_analysis(rids, "no_such_pair")
        assert "insufficient" in out["narrative"]["headline"].lower()


# ===========================================================================
# I. Small-N + legacy handling
# ===========================================================================
class TestSmallNAndLegacy:
    def test_empty_run_ids_returns_empty_shape(self):
        out = pd_mod.pair_deep_analysis([], "p1")
        assert out["pair_id"] == "p1"
        assert out["trajectory"]["magnitude_over_time"] == []

    def test_one_run_returns_empty_trajectory(self):
        rids = _seed_stable(prefix="sg", n=1)
        out = pd_mod.pair_deep_analysis(rids, "p1")
        # Unit 4 requires >= 2 modern runs; below that pair_summaries
        # is empty → we return the empty-pair shape.
        assert out["trajectory"]["magnitude_over_time"] == []

    def test_legacy_run_dropped_from_analysis(
        self, _runs_dir_isolation,
    ):
        rids = _seed_stable(prefix="lg", n=3)
        _write_legacy(_runs_dir_isolation, "lg_leg", [_entry("p1")])
        out = pd_mod.pair_deep_analysis(rids + ["lg_leg"], "p1")
        # 3 modern runs → magnitude_over_time length 3 (legacy dropped).
        assert len(out["trajectory"]["magnitude_over_time"]) == 3

    def test_pair_deep_all_empty_run_ids(self):
        out = pd_mod.pair_deep_all([])
        assert out == {"pairs": {}, "run_ids": []}


# ===========================================================================
# J. Determinism (byte-equal repeats)
# ===========================================================================
class TestDeterminism:
    def test_pair_deep_analysis_byte_equal(self):
        rids = _seed_spike_pair()
        a = pd_mod.pair_deep_analysis(rids, "p1")
        b = pd_mod.pair_deep_analysis(rids, "p1")
        assert a == b

    def test_pair_deep_all_byte_equal(self):
        rids = _seed_stable(n=4)
        a = pd_mod.pair_deep_all(rids)
        b = pd_mod.pair_deep_all(rids)
        assert a == b

    def test_missing_pair_byte_equal(self):
        rids = _seed_stable(n=4)
        a = pd_mod.pair_deep_analysis(rids, "ghost")
        b = pd_mod.pair_deep_analysis(rids, "ghost")
        assert a == b


# ===========================================================================
# K. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="list"):
            pd_mod.pair_deep_analysis("nope", "p1")

    def test_malformed_run_id_raises(self):
        with pytest.raises(ValueError):
            pd_mod.pair_deep_analysis(["bad/id"], "p1")

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            pd_mod.pair_deep_analysis(["ghost"], "p1")

    def test_empty_pair_id_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            pd_mod.pair_deep_analysis([], "")

    def test_non_string_pair_id_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            pd_mod.pair_deep_analysis([], 123)

    def test_pair_deep_all_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            pd_mod.pair_deep_all("nope")

    def test_pair_deep_all_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            pd_mod.pair_deep_all(["ghost"])


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            pd_mod.pair_deep_analysis,
            pd_mod.pair_deep_all,
        ):
            assert callable(fn)

    def test_strong_severity_threshold_locked(self):
        assert pd_mod._STRONG_SEVERITY_THRESHOLD == 4.0

    def test_stability_band_thresholds_locked(self):
        assert pd_mod._STABILITY_HIGH   == 0.85
        assert pd_mod._STABILITY_MEDIUM == 0.50


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(pd_mod)

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

    def test_composes_unit_4(self):
        src = self._code_only()
        assert "multi_run_summary" in src
