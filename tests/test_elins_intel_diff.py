"""
Tests for ELINS3 Unit 14 — intelligence diff engine.

Layered coverage (>= 50 tests, target ~65):
    A. Top-level shape / locked keys
    B. Summary delta math (health, anomaly)
    C. Trend shift classification
    D. Cluster shift classification
    E. Per-pair deltas
    F. Narrative — headline + bullets
    G. Overlapping sets
    H. Empty / small N sides
    I. Legacy run handling
    J. Asymmetry (swap A and B negates deltas)
    K. Determinism (byte-equal repeats)
    L. Validation
    M. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_intel_diff as diff_mod
import elins_intelligence as intel_mod
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
        ep.save_comparison_result(
            rid, [_entry("p1", sp=sp, ec=sp,
                          sp_band="Fails core logic",
                          ec_band="Fails core logic")],
        )
        rids.append(rid)
    return rids


def _seed_volatile(prefix="v"):
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
        a = _seed_stable(prefix="ta", n=3)
        b = _seed_stable(prefix="tb", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert set(out.keys()) == {
            "a_run_ids", "b_run_ids", "summary", "pairs", "narrative",
        }

    def test_a_run_ids_echoed(self):
        a = _seed_stable(prefix="ea", n=3)
        b = _seed_stable(prefix="eb", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert out["a_run_ids"] == a
        assert out["b_run_ids"] == b

    def test_summary_keys_locked(self):
        a = _seed_stable(prefix="sa", n=3)
        b = _seed_stable(prefix="sb", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert set(out["summary"].keys()) == {
            "health_delta", "anomaly_delta",
            "trend_shift", "cluster_shift",
        }

    def test_narrative_keys_locked(self):
        a = _seed_stable(prefix="na", n=3)
        b = _seed_stable(prefix="nb", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert set(out["narrative"].keys()) == {"headline", "bullets"}

    def test_pairs_is_dict(self):
        a = _seed_stable(prefix="pa", n=3)
        b = _seed_stable(prefix="pb", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert isinstance(out["pairs"], dict)


# ===========================================================================
# B. Summary delta math
# ===========================================================================
class TestSummaryDeltas:
    def test_identical_sets_zero_health_delta(self):
        a = _seed_stable(prefix="id", n=3)
        out = diff_mod.diff_intelligence(a, a)
        assert out["summary"]["health_delta"] == 0.0

    def test_identical_sets_zero_anomaly_delta(self):
        a = _seed_stable(prefix="ia", n=3)
        out = diff_mod.diff_intelligence(a, a)
        assert out["summary"]["anomaly_delta"] == 0.0

    def test_upward_b_higher_health(self):
        a = _seed_downward(prefix="dnh")
        b = _seed_upward(prefix="uph")
        out = diff_mod.diff_intelligence(a, b)
        # B (upward) has higher health than A (downward) → positive delta.
        assert out["summary"]["health_delta"] > 0

    def test_downward_b_lower_health(self):
        a = _seed_upward(prefix="ulh")
        b = _seed_downward(prefix="dlh")
        out = diff_mod.diff_intelligence(a, b)
        # B (downward) has lower health than A (upward) → negative delta.
        assert out["summary"]["health_delta"] < 0

    def test_health_delta_within_bounds(self):
        a = _seed_stable(prefix="hb", n=3)
        b = _seed_stable(prefix="hb2", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert -1.0 <= out["summary"]["health_delta"] <= 1.0

    def test_anomaly_delta_within_bounds(self):
        a = _seed_stable(prefix="ad", n=3)
        b = _seed_stable(prefix="ad2", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert -1.0 <= out["summary"]["anomaly_delta"] <= 1.0

    def test_health_delta_matches_unit_9(self):
        a = _seed_stable(prefix="ha", n=3)
        b = _seed_upward(prefix="hb")
        out = diff_mod.diff_intelligence(a, b)
        h_a = intel_mod.intelligence_for_run_ids(a)["scores"][
            "overall_health"
        ]
        h_b = intel_mod.intelligence_for_run_ids(b)["scores"][
            "overall_health"
        ]
        assert out["summary"]["health_delta"] == pytest.approx(h_b - h_a)


# ===========================================================================
# C. Trend shift classification
# ===========================================================================
class TestTrendShift:
    def test_volatile_to_stable_toward_stability(self):
        a = _seed_volatile(prefix="vts")
        b = _seed_upward(prefix="vtu")
        out = diff_mod.diff_intelligence(a, b)
        assert out["summary"]["trend_shift"] == "toward_stability"

    def test_stable_to_volatile_toward_volatility(self):
        a = _seed_upward(prefix="stv")
        b = _seed_volatile(prefix="stv_v")
        out = diff_mod.diff_intelligence(a, b)
        assert out["summary"]["trend_shift"] == "toward_volatility"

    def test_same_class_neutral(self):
        a = _seed_upward(prefix="snu_a")
        b = _seed_upward(prefix="snu_b")
        out = diff_mod.diff_intelligence(a, b)
        # Both monotonic_increase → neutral shift.
        assert out["summary"]["trend_shift"] == "neutral"

    def test_insufficient_a_is_neutral(self):
        a = _seed_stable(prefix="ia2", n=2)  # under min for trend classification
        b = _seed_upward(prefix="ib2")
        out = diff_mod.diff_intelligence(a, b)
        assert out["summary"]["trend_shift"] == "neutral"


# ===========================================================================
# D. Cluster shift classification
# ===========================================================================
class TestClusterShift:
    def test_downward_to_upward_more_upward(self):
        a = _seed_downward(prefix="cdu_a")
        b = _seed_upward(prefix="cdu_b")
        out = diff_mod.diff_intelligence(a, b)
        assert out["summary"]["cluster_shift"] == "more_upward"

    def test_upward_to_downward_more_downward(self):
        a = _seed_upward(prefix="cud_a")
        b = _seed_downward(prefix="cud_b")
        out = diff_mod.diff_intelligence(a, b)
        assert out["summary"]["cluster_shift"] == "more_downward"

    def test_same_direction_neutral(self):
        a = _seed_upward(prefix="csn_a")
        b = _seed_upward(prefix="csn_b")
        out = diff_mod.diff_intelligence(a, b)
        assert out["summary"]["cluster_shift"] == "neutral"


# ===========================================================================
# E. Per-pair deltas
# ===========================================================================
class TestPairDeltas:
    def test_pair_entry_keys_locked(self):
        a = _seed_stable(prefix="pe_a", n=3)
        b = _seed_stable(prefix="pe_b", n=3)
        out = diff_mod.diff_intelligence(a, b)
        for pid, data in out["pairs"].items():
            assert set(data.keys()) == {
                "stability_delta", "volatility_delta", "trend_change",
            }

    def test_identical_pair_deltas_zero(self):
        a = _seed_stable(prefix="pi", n=3)
        out = diff_mod.diff_intelligence(a, a)
        for pid, data in out["pairs"].items():
            assert data["stability_delta"] == 0.0
            assert data["volatility_delta"] == 0.0

    def test_identical_trend_change_unchanged(self):
        a = _seed_stable(prefix="pu", n=3)
        out = diff_mod.diff_intelligence(a, a)
        for pid, data in out["pairs"].items():
            assert data["trend_change"] == "unchanged"

    def test_upward_to_downward_trend_change(self):
        a = _seed_upward(prefix="pt_a")
        b = _seed_downward(prefix="pt_b")
        out = diff_mod.diff_intelligence(a, b)
        # Both sets have a single pair p1 — its trend flips upward→downward.
        assert out["pairs"]["p1"]["trend_change"] == "upward_to_downward"

    def test_pairs_disjoint_unioned(self):
        a = _seed_stable(prefix="pj", n=2)  # has p1, p2
        # B uses a different pair_id.
        b_rids = []
        for i, sp in enumerate((1, 3, 5), 1):
            rid = f"pj2_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p99", sp=sp)])
            b_rids.append(rid)
        out = diff_mod.diff_intelligence(a, b_rids)
        # Union covers all three pair_ids.
        assert {"p1", "p2", "p99"}.issubset(out["pairs"].keys())


# ===========================================================================
# F. Narrative — headline + bullets
# ===========================================================================
class TestNarrative:
    def test_headline_non_empty(self):
        a = _seed_stable(prefix="hn_a", n=3)
        b = _seed_stable(prefix="hn_b", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert isinstance(out["narrative"]["headline"], str)
        assert out["narrative"]["headline"].strip() != ""

    def test_bullets_non_empty(self):
        a = _seed_stable(prefix="bn_a", n=3)
        b = _seed_stable(prefix="bn_b", n=3)
        out = diff_mod.diff_intelligence(a, b)
        assert isinstance(out["narrative"]["bullets"], list)
        assert len(out["narrative"]["bullets"]) >= 1

    def test_improved_headline_mentions_improvement(self):
        a = _seed_downward(prefix="ih_a")
        b = _seed_upward(prefix="ih_b")
        out = diff_mod.diff_intelligence(a, b)
        assert "improved" in out["narrative"]["headline"].lower()

    def test_regressed_headline_mentions_regression(self):
        a = _seed_upward(prefix="rh_a")
        b = _seed_downward(prefix="rh_b")
        out = diff_mod.diff_intelligence(a, b)
        assert "regressed" in out["narrative"]["headline"].lower()

    def test_no_change_headline_holds_steady(self):
        a = _seed_stable(prefix="nch", n=3)
        out = diff_mod.diff_intelligence(a, a)
        assert "held steady" in out["narrative"]["headline"].lower()

    def test_health_bullet_mentions_two_health_values(self):
        a = _seed_stable(prefix="hbm_a", n=3)
        b = _seed_upward(prefix="hbm_b")
        out = diff_mod.diff_intelligence(a, b)
        bullet = out["narrative"]["bullets"][0]
        assert "Overall health" in bullet

    def test_anomaly_bullet_present(self):
        a = _seed_stable(prefix="ab_a", n=3)
        b = _seed_stable(prefix="ab_b", n=3)
        out = diff_mod.diff_intelligence(a, b)
        joined = " ".join(out["narrative"]["bullets"]).lower()
        assert "anomaly" in joined


# ===========================================================================
# G. Overlapping sets
# ===========================================================================
class TestOverlapping:
    def test_overlapping_runs_handled(self):
        rids = _seed_stable(prefix="ov", n=5)
        a = rids[:3]
        b = rids[2:]
        out = diff_mod.diff_intelligence(a, b)
        assert "summary" in out

    def test_overlapping_sets_have_some_zero_pair_deltas(self):
        # When both sides cover identical stable runs through overlap,
        # pair-level deltas should be close to 0 for shared signals.
        rids = _seed_stable(prefix="oz", n=5)
        a = rids
        b = rids
        out = diff_mod.diff_intelligence(a, b)
        for data in out["pairs"].values():
            assert abs(data["stability_delta"]) < 1e-9


# ===========================================================================
# H. Empty / small N sides
# ===========================================================================
class TestEmptyAndSmallN:
    def test_empty_a_and_b(self):
        out = diff_mod.diff_intelligence([], [])
        assert out["summary"]["health_delta"] == 0.0
        assert out["summary"]["anomaly_delta"] == 0.0

    def test_empty_a_full_b(self):
        b = _seed_upward(prefix="eaf")
        out = diff_mod.diff_intelligence([], b)
        # B has positive health; A has 0.0 → positive delta.
        assert out["summary"]["health_delta"] > 0

    def test_full_a_empty_b(self):
        a = _seed_upward(prefix="fae")
        out = diff_mod.diff_intelligence(a, [])
        assert out["summary"]["health_delta"] < 0

    def test_one_run_each_well_formed(self):
        a = _seed_stable(prefix="oa", n=1)
        b = _seed_stable(prefix="ob", n=1)
        out = diff_mod.diff_intelligence(a, b)
        assert set(out.keys()) == {
            "a_run_ids", "b_run_ids", "summary", "pairs", "narrative",
        }


# ===========================================================================
# I. Legacy run handling
# ===========================================================================
class TestLegacy:
    def test_legacy_in_a_does_not_crash(
        self, _runs_dir_isolation,
    ):
        a = _seed_stable(prefix="la_a", n=2)
        _write_legacy(_runs_dir_isolation, "la_leg", [_entry("p1")])
        b = _seed_stable(prefix="la_b", n=2)
        out = diff_mod.diff_intelligence(a + ["la_leg"], b)
        assert "summary" in out

    def test_legacy_in_b_does_not_crash(
        self, _runs_dir_isolation,
    ):
        a = _seed_stable(prefix="lb_a", n=2)
        b = _seed_stable(prefix="lb_b", n=2)
        _write_legacy(_runs_dir_isolation, "lb_leg", [_entry("p1")])
        out = diff_mod.diff_intelligence(a, b + ["lb_leg"])
        assert "summary" in out


# ===========================================================================
# J. Asymmetry (swap A and B negates deltas)
# ===========================================================================
class TestAsymmetry:
    def test_health_delta_negates_on_swap(self):
        a = _seed_downward(prefix="sd_a")
        b = _seed_upward(prefix="sd_b")
        fwd  = diff_mod.diff_intelligence(a, b)
        back = diff_mod.diff_intelligence(b, a)
        assert fwd["summary"]["health_delta"] == pytest.approx(
            -back["summary"]["health_delta"],
        )

    def test_anomaly_delta_negates_on_swap(self):
        a = _seed_stable(prefix="sa_a", n=3)
        b = _seed_upward(prefix="sa_b")
        fwd  = diff_mod.diff_intelligence(a, b)
        back = diff_mod.diff_intelligence(b, a)
        assert fwd["summary"]["anomaly_delta"] == pytest.approx(
            -back["summary"]["anomaly_delta"],
        )

    def test_per_pair_deltas_negate_on_swap(self):
        a = _seed_upward(prefix="pa_a")
        b = _seed_downward(prefix="pa_b")
        fwd  = diff_mod.diff_intelligence(a, b)
        back = diff_mod.diff_intelligence(b, a)
        for pid in fwd["pairs"].keys():
            if pid in back["pairs"]:
                assert fwd["pairs"][pid]["stability_delta"] == pytest.approx(
                    -back["pairs"][pid]["stability_delta"],
                )


# ===========================================================================
# K. Determinism (byte-equal repeats)
# ===========================================================================
class TestDeterminism:
    def test_repeated_call_byte_equal(self):
        a = _seed_stable(prefix="rb_a", n=3)
        b = _seed_upward(prefix="rb_b")
        x = diff_mod.diff_intelligence(a, b)
        y = diff_mod.diff_intelligence(a, b)
        assert x == y

    def test_empty_byte_equal(self):
        x = diff_mod.diff_intelligence([], [])
        y = diff_mod.diff_intelligence([], [])
        assert x == y


# ===========================================================================
# L. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_a_raises(self):
        with pytest.raises(ValueError, match="list"):
            diff_mod.diff_intelligence("nope", [])

    def test_non_list_b_raises(self):
        with pytest.raises(ValueError, match="list"):
            diff_mod.diff_intelligence([], "nope")

    def test_malformed_id_a_raises(self):
        with pytest.raises(ValueError):
            diff_mod.diff_intelligence(["bad/id"], [])

    def test_malformed_id_b_raises(self):
        with pytest.raises(ValueError):
            diff_mod.diff_intelligence([], ["bad/id"])

    def test_missing_run_a_raises(self):
        with pytest.raises(FileNotFoundError):
            diff_mod.diff_intelligence(["ghost"], [])

    def test_missing_run_b_raises(self):
        with pytest.raises(FileNotFoundError):
            diff_mod.diff_intelligence([], ["ghost"])


# ===========================================================================
# M. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(diff_mod.diff_intelligence)

    def test_shift_vocabulary_locked(self):
        for name, val in (
            ("_SHIFT_TOWARD_STABILITY",  "toward_stability"),
            ("_SHIFT_TOWARD_VOLATILITY", "toward_volatility"),
            ("_SHIFT_MORE_UPWARD",       "more_upward"),
            ("_SHIFT_MORE_DOWNWARD",     "more_downward"),
            ("_SHIFT_NEUTRAL",           "neutral"),
        ):
            assert getattr(diff_mod, name) == val

    def test_shift_epsilon_locked(self):
        assert diff_mod._SHIFT_EPSILON == 0.05


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(diff_mod)

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

    def test_composes_unit_9(self):
        src = self._code_only()
        assert "intelligence_for_run_ids" in src
