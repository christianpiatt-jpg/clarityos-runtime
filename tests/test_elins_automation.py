"""
Tests for ELINS5 Unit 18 — operator automation hooks.

Layered coverage (>= 50 tests, target ~65):
    A. auto_flag_regressions — happy path + signal detection
    B. auto_flag_regressions — dedupe + existing-tag preservation
    C. auto_flag_regressions — small N
    D. auto_promote_stable_pairs — happy path + criteria filter
    E. auto_promote_stable_pairs — dedupe
    F. auto_promote_stable_pairs — multi-pair universe
    G. auto_generate_weekly_report — shape locked
    H. auto_generate_weekly_report — content delegation
    I. auto_generate_weekly_report — small / empty / legacy
    J. Validation across all three
    K. Determinism (byte-equal repeats — within constraints)
    L. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_alerts as alert_mod
import elins_automation as auto_mod
import elins_intel_diff as diff_mod
import elins_intelligence as intel_mod
import elins_pair_deep as pd_mod
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


def _seed_health_drop(prefix="hd"):
    """10 runs: 5 upward (A side) + 5 downward (B side) — diff produces
    cluster_shift == 'more_downward' so auto_flag_regressions fires
    on the last 5."""
    rids: list = []
    upward   = [1, 2, 3, 4, 5]
    downward = [9, 8, 7, 6, 5]
    for i, sp in enumerate(upward + downward, 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(
            rid, [_entry("p1", sp=sp, ec=sp,
                          sp_band="Fails core logic" if sp <= 4 and i >= 6 else "Acceptable",
                          ec_band="Fails core logic" if sp <= 4 and i >= 6 else "Acceptable")],
        )
        rids.append(rid)
    return rids


def _seed_volatility_surge(prefix="vs"):
    """10 runs: 5 monotonic + 5 oscillating → trend_shift toward_volatility."""
    rids: list = []
    monotonic = [1, 2, 3, 4, 5]
    oscillate = [1, 9, 1, 9, 1]
    for i, sp in enumerate(monotonic + oscillate, 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_stable_pair(prefix="sp"):
    """6 runs with p1 constant (perfectly stable, no volatility,
    trend = flat) — promotion criteria met."""
    rids: list = []
    for i in range(6):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=5, ec=5)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. auto_flag_regressions — happy path + signal detection
# ===========================================================================
class TestFlagRegressionsHappy:
    def test_response_shape(self):
        rids = _seed_stable(n=4)
        out = auto_mod.auto_flag_regressions(rids)
        assert set(out.keys()) == {"flagged", "skipped"}

    def test_clean_universe_nothing_flagged(self):
        rids = _seed_stable(n=10, sp=5)
        out = auto_mod.auto_flag_regressions(rids)
        assert out["flagged"] == []
        assert set(out["skipped"]) == set(rids)

    def test_downward_cluster_shift_fires(self):
        rids = _seed_health_drop()
        out = auto_mod.auto_flag_regressions(rids)
        # B half (last 5) should be flagged.
        last_five = rids[-5:]
        for rid in last_five:
            assert rid in out["flagged"]

    def test_flagged_runs_carry_regression_tag(self):
        rids = _seed_health_drop()
        auto_mod.auto_flag_regressions(rids)
        for rid in rids[-5:]:
            assert "regression_flag" in ep_sql.get_tags(rid)

    def test_a_half_not_flagged(self):
        rids = _seed_health_drop()
        out = auto_mod.auto_flag_regressions(rids)
        for rid in rids[:5]:
            assert rid not in out["flagged"]
            # Existing tags untouched.
            assert "regression_flag" not in ep_sql.get_tags(rid)

    def test_volatility_surge_triggers_flag(self):
        rids = _seed_volatility_surge()
        out = auto_mod.auto_flag_regressions(rids)
        last_five = rids[-5:]
        flagged_set = set(out["flagged"])
        assert any(rid in flagged_set for rid in last_five)


# ===========================================================================
# B. auto_flag_regressions — dedupe + existing-tag preservation
# ===========================================================================
class TestFlagRegressionsDedup:
    def test_existing_other_tags_preserved(self):
        rids = _seed_health_drop(prefix="ex")
        # Pre-tag a B-half run.
        ep_sql.set_tags(rids[-1], ["other_tag"])
        auto_mod.auto_flag_regressions(rids)
        tags = ep_sql.get_tags(rids[-1])
        assert "other_tag" in tags
        assert "regression_flag" in tags

    def test_repeat_call_does_not_duplicate_tag(self):
        rids = _seed_health_drop(prefix="rp")
        auto_mod.auto_flag_regressions(rids)
        auto_mod.auto_flag_regressions(rids)
        for rid in rids[-5:]:
            assert ep_sql.get_tags(rid).count("regression_flag") == 1

    def test_run_already_tagged_appears_in_skipped(self):
        rids = _seed_health_drop(prefix="at")
        ep_sql.set_tags(rids[-1], ["regression_flag"])
        out = auto_mod.auto_flag_regressions(rids)
        assert rids[-1] in out["skipped"]
        assert rids[-1] not in out["flagged"]


# ===========================================================================
# C. auto_flag_regressions — small N
# ===========================================================================
class TestFlagRegressionsSmallN:
    def test_empty_returns_empty(self):
        out = auto_mod.auto_flag_regressions([])
        assert out == {"flagged": [], "skipped": []}

    def test_one_run_no_diff(self):
        rids = _seed_stable(prefix="one", n=1)
        out = auto_mod.auto_flag_regressions(rids)
        assert out["flagged"] == []
        assert rids[0] in out["skipped"]

    def test_two_runs_split_works(self):
        # 2 runs: previous=[r0], last=[r1]; with stable values nothing
        # fires.
        rids = _seed_stable(prefix="tw", n=2)
        out = auto_mod.auto_flag_regressions(rids)
        assert out["flagged"] == []

    def test_four_runs_uses_smaller_window(self):
        # 4 runs → window=2; previous=[r0, r1], last=[r2, r3].
        rids = _seed_stable(prefix="fr", n=4)
        out = auto_mod.auto_flag_regressions(rids)
        # Stable universe → nothing flagged.
        assert out["flagged"] == []


# ===========================================================================
# D. auto_promote_stable_pairs — happy path + criteria filter
# ===========================================================================
class TestPromoteStablePairs:
    def test_response_shape(self):
        rids = _seed_stable_pair()
        out = auto_mod.auto_promote_stable_pairs(rids)
        assert set(out.keys()) == {"promoted", "tagged_runs"}

    def test_stable_pair_promoted(self):
        rids = _seed_stable_pair()
        out = auto_mod.auto_promote_stable_pairs(rids)
        assert "p1" in out["promoted"]

    def test_promotion_tags_runs(self):
        rids = _seed_stable_pair()
        out = auto_mod.auto_promote_stable_pairs(rids)
        for rid in out["tagged_runs"]:
            assert "stable_pair" in ep_sql.get_tags(rid)

    def test_low_stability_pair_not_promoted(self):
        # Volatile pair → fails stability > 0.85.
        rids: list = []
        for i, sp in enumerate((1, 9, 1, 9, 1, 9), 1):
            rid = f"vol_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = auto_mod.auto_promote_stable_pairs(rids)
        assert "p1" not in out["promoted"]

    def test_downward_pair_not_promoted(self):
        # Strictly downward → trend_direction == "downward" → excluded.
        rids: list = []
        for i, sp in enumerate((9, 7, 5, 3, 1, 0), 1):
            rid = f"dn_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = auto_mod.auto_promote_stable_pairs(rids)
        assert "p1" not in out["promoted"]


# ===========================================================================
# E. auto_promote_stable_pairs — dedupe
# ===========================================================================
class TestPromoteDedup:
    def test_repeat_call_no_duplicate_tag(self):
        rids = _seed_stable_pair(prefix="dp")
        auto_mod.auto_promote_stable_pairs(rids)
        auto_mod.auto_promote_stable_pairs(rids)
        for rid in rids:
            assert ep_sql.get_tags(rid).count("stable_pair") <= 1

    def test_existing_other_tags_preserved(self):
        rids = _seed_stable_pair(prefix="op")
        ep_sql.set_tags(rids[0], ["other_tag"])
        auto_mod.auto_promote_stable_pairs(rids)
        tags = ep_sql.get_tags(rids[0])
        assert "other_tag" in tags
        assert "stable_pair" in tags


# ===========================================================================
# F. auto_promote_stable_pairs — multi-pair universe
# ===========================================================================
class TestPromoteMultiPair:
    def test_mixed_promotion_only_stable_pairs(self):
        # Two pairs in every run: one stable, one volatile.
        rids: list = []
        for i in range(6):
            rid = f"mx_{i:02d}"
            ep.save_comparison_result(
                rid,
                [
                    _entry("stable_p", sp=5, ec=5),
                    _entry("volatile_p", sp=1 if i % 2 == 0 else 9,
                            ec=1 if i % 2 == 0 else 9),
                ],
            )
            rids.append(rid)
        out = auto_mod.auto_promote_stable_pairs(rids)
        assert "stable_p" in out["promoted"]
        assert "volatile_p" not in out["promoted"]


# ===========================================================================
# G. auto_generate_weekly_report — shape locked
# ===========================================================================
class TestWeeklyReportShape:
    def test_top_level_keys(self):
        rids = _seed_stable(prefix="ws", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        assert set(out.keys()) == {
            "headline", "health", "anomalies", "trends",
            "clusters", "pairs", "alerts", "timeline", "diff",
        }

    def test_health_in_unit_interval(self):
        rids = _seed_stable(prefix="wh", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        assert 0.0 <= out["health"] <= 1.0

    def test_alerts_is_list(self):
        rids = _seed_stable(prefix="wa", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        assert isinstance(out["alerts"], list)

    def test_timeline_is_list(self):
        rids = _seed_stable(prefix="wt", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        assert isinstance(out["timeline"], list)

    def test_headline_non_empty(self):
        rids = _seed_stable(prefix="whn", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        assert isinstance(out["headline"], str)
        assert out["headline"].strip() != ""


# ===========================================================================
# H. auto_generate_weekly_report — content delegation
# ===========================================================================
class TestWeeklyReportDelegation:
    def test_health_matches_intelligence_unit(self):
        rids = _seed_stable(prefix="dl_h", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        intel = intel_mod.intelligence_for_run_ids(rids)
        assert out["health"] == pytest.approx(
            intel["scores"]["overall_health"],
        )

    def test_anomalies_matches_intelligence_unit(self):
        rids = _seed_stable(prefix="dl_a", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        intel = intel_mod.intelligence_for_run_ids(rids)
        assert out["anomalies"] == intel["anomalies"]

    def test_timeline_matches_unit_13(self):
        rids = _seed_stable(prefix="dl_t", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        timeline = tl_mod.build_intelligence_timeline(rids)
        assert out["timeline"] == timeline["timeline"]

    def test_alerts_matches_unit_16(self):
        rids = _seed_stable(prefix="dl_al", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        alerts = alert_mod.generate_alerts(rids)
        assert out["alerts"] == alerts["alerts"]

    def test_diff_matches_unit_14(self):
        rids = _seed_health_drop(prefix="dl_d")
        out = auto_mod.auto_generate_weekly_report(rids)
        mid = len(rids) // 2
        expected = diff_mod.diff_intelligence(rids[:mid], rids[mid:])
        assert out["diff"] == expected

    def test_pairs_matches_unit_17(self):
        rids = _seed_stable(prefix="dl_p", n=5)
        out = auto_mod.auto_generate_weekly_report(rids)
        expected = pd_mod.pair_deep_all(rids)
        assert out["pairs"] == expected


# ===========================================================================
# I. auto_generate_weekly_report — small / empty / legacy
# ===========================================================================
class TestWeeklyReportSmallN:
    def test_empty_returns_well_formed(self):
        out = auto_mod.auto_generate_weekly_report([])
        assert set(out.keys()) == {
            "headline", "health", "anomalies", "trends",
            "clusters", "pairs", "alerts", "timeline", "diff",
        }
        assert out["health"] == 0.0
        assert out["timeline"] == []
        assert out["alerts"] == []
        assert out["diff"] is None

    def test_one_run_no_diff(self):
        rids = _seed_stable(prefix="wo", n=1)
        out = auto_mod.auto_generate_weekly_report(rids)
        assert out["diff"] is None

    def test_two_runs_has_diff(self):
        rids = _seed_stable(prefix="wtw", n=2)
        out = auto_mod.auto_generate_weekly_report(rids)
        assert out["diff"] is not None

    def test_legacy_run_does_not_crash(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="wleg", n=3)
        _write_legacy(_runs_dir_isolation, "wleg_l", [_entry("p1")])
        out = auto_mod.auto_generate_weekly_report(rids + ["wleg_l"])
        assert isinstance(out, dict)


# ===========================================================================
# J. Validation across all three
# ===========================================================================
class TestValidation:
    def test_flag_regressions_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            auto_mod.auto_flag_regressions("nope")

    def test_promote_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            auto_mod.auto_promote_stable_pairs("nope")

    def test_weekly_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            auto_mod.auto_generate_weekly_report("nope")

    def test_flag_malformed_id_raises(self):
        with pytest.raises(ValueError):
            auto_mod.auto_flag_regressions(["bad/id"])

    def test_promote_malformed_id_raises(self):
        with pytest.raises(ValueError):
            auto_mod.auto_promote_stable_pairs(["bad/id"])

    def test_weekly_malformed_id_raises(self):
        with pytest.raises(ValueError):
            auto_mod.auto_generate_weekly_report(["bad/id"])

    def test_flag_missing_run_raises(self):
        # 2 runs needed for diff path; ghost-id at least triggers
        # FileNotFoundError on first load.
        with pytest.raises(FileNotFoundError):
            auto_mod.auto_flag_regressions(["ghost", "ghost2"])

    def test_promote_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            auto_mod.auto_promote_stable_pairs(["ghost", "ghost2"])

    def test_weekly_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            auto_mod.auto_generate_weekly_report(["ghost"])


# ===========================================================================
# K. Determinism
# ===========================================================================
class TestDeterminism:
    def test_flag_regressions_repeat_idempotent(self):
        rids = _seed_health_drop(prefix="dt_f")
        a = auto_mod.auto_flag_regressions(rids)
        # Second call sees the tag already present — flagged is empty.
        b = auto_mod.auto_flag_regressions(rids)
        assert b["flagged"] == []
        # And the tagged runs in the first call match the input's B half.
        assert set(a["flagged"]) == set(rids[-5:])

    def test_promote_repeat_idempotent(self):
        rids = _seed_stable_pair(prefix="dt_p")
        a = auto_mod.auto_promote_stable_pairs(rids)
        b = auto_mod.auto_promote_stable_pairs(rids)
        # Promoted pair_id list is identical across calls.
        assert a["promoted"] == b["promoted"]

    def test_weekly_report_byte_equal(self):
        rids = _seed_stable(prefix="dt_w", n=5)
        a = auto_mod.auto_generate_weekly_report(rids)
        b = auto_mod.auto_generate_weekly_report(rids)
        assert a == b


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            auto_mod.auto_flag_regressions,
            auto_mod.auto_promote_stable_pairs,
            auto_mod.auto_generate_weekly_report,
        ):
            assert callable(fn)

    def test_tag_vocabulary_locked(self):
        assert auto_mod.TAG_REGRESSION_FLAG == "regression_flag"
        assert auto_mod.TAG_STABLE_PAIR == "stable_pair"

    def test_regression_thresholds_locked(self):
        assert auto_mod._REGRESSION_WINDOW == 5
        assert auto_mod._PAIR_STABILITY_DROP_LIMIT == 0.20

    def test_stable_pair_thresholds_locked(self):
        assert auto_mod._STABLE_PAIR_STABILITY_MIN == 0.85
        assert auto_mod._STABLE_PAIR_VOLATILITY_MAX == 0.10
        assert auto_mod._STABLE_PAIR_TREND_VOCAB == ("upward", "flat")


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(auto_mod)

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

    def test_composes_units_9_13_14_15_16_17(self):
        src = self._code_only()
        for required in (
            "intelligence_for_run_ids",       # Unit 9
            "build_intelligence_timeline",    # Unit 13
            "diff_intelligence",               # Unit 14
            "generate_alerts",                 # Unit 16
            "pair_deep_all",                   # Unit 17
        ):
            assert required in src
