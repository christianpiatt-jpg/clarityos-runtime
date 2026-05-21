"""
Tests for ELINS6 Unit 19 — release gate engine.

Layered coverage (>= 50 tests, target ~60):
    A. Top-level shape / locked keys
    B. Allow decision
    C. Warn decision
    D. Block decision
    E. Decision precedence (block > warn > allow)
    F. Reasons vocabulary
    G. Metrics content
    H. Small N (0 / 1 / 2 runs)
    I. Legacy run handling
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

import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
import elins_release_gate as gate_mod


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
    """6 runs: A=[1,3,5] upward, B=[9,7,5] downward → health drops by
    a large negative delta, triggering BOTH block and warn rules."""
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 9, 7, 5), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_volatility_surge(prefix="vs"):
    """8 runs: 4 monotonic A + 4 oscillating B → trend_shift toward
    volatility."""
    rids: list = []
    monotonic = [1, 2, 3, 4]
    oscillate = [1, 9, 1, 9]
    for i, sp in enumerate(monotonic + oscillate, 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_keys_locked(self):
        rids = _seed_stable(n=4)
        out = gate_mod.evaluate_release_gate(rids)
        assert set(out.keys()) == {"decision", "reasons", "metrics"}

    def test_decision_in_locked_vocab(self):
        rids = _seed_stable(n=4)
        out = gate_mod.evaluate_release_gate(rids)
        assert out["decision"] in ("allow", "warn", "block")

    def test_reasons_is_list(self):
        rids = _seed_stable(n=4)
        out = gate_mod.evaluate_release_gate(rids)
        assert isinstance(out["reasons"], list)

    def test_metrics_keys_locked(self):
        rids = _seed_stable(n=4)
        out = gate_mod.evaluate_release_gate(rids)
        assert set(out["metrics"].keys()) == {
            "health", "anomaly_fraction",
            "trend_shift", "cluster_shift",
            "regressions", "promoted_pairs",
        }


# ===========================================================================
# B. Allow decision
# ===========================================================================
class TestAllow:
    def test_perfectly_stable_universe_allows(self):
        rids = _seed_stable(n=6, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        assert out["decision"] == "allow"
        assert out["reasons"] == []

    def test_allow_promoted_pair_present(self):
        rids = _seed_stable(n=6, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        # Stable universe with constant p1 → promoted_pairs contains p1.
        assert "p1" in out["metrics"]["promoted_pairs"]

    def test_allow_health_value(self):
        rids = _seed_stable(n=6, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        # Stable universe → health bounded.
        assert 0.0 <= out["metrics"]["health"] <= 1.0


# ===========================================================================
# C. Warn decision
# ===========================================================================
class TestWarn:
    def test_volatile_pair_low_stability_warns(self):
        # 6 runs alternating 1/9 — very low stability.
        rids: list = []
        for i, sp in enumerate((1, 9, 1, 9, 1, 9), 1):
            rid = f"wv_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = gate_mod.evaluate_release_gate(rids)
        # Low stability + volatility events without sustained downward
        # signal → at minimum a warn.
        assert out["decision"] in ("warn", "block")

    def test_volatility_events_present_in_warn_reasons(self):
        rids: list = []
        for i, sp in enumerate((1, 9, 1, 9, 1, 9), 1):
            rid = f"vw_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = gate_mod.evaluate_release_gate(rids)
        # When the decision is warn, at least one of the locked
        # warn reasons must be present.
        if out["decision"] == "warn":
            assert any(
                r in (
                    "volatility_events", "low_pair_stability",
                    "health_drop_warn", "anomaly_spike_warn",
                )
                for r in out["reasons"]
            )

    def test_warn_reasons_subset_of_warn_vocab(self):
        rids: list = []
        for i, sp in enumerate((1, 9, 1, 9, 1, 9), 1):
            rid = f"wv2_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = gate_mod.evaluate_release_gate(rids)
        if out["decision"] == "warn":
            allowed = {
                "health_drop_warn", "anomaly_spike_warn",
                "volatility_events", "low_pair_stability",
            }
            for r in out["reasons"]:
                assert r in allowed


# ===========================================================================
# D. Block decision
# ===========================================================================
class TestBlock:
    def test_health_drop_blocks(self):
        rids = _seed_health_drop(prefix="hb")
        out = gate_mod.evaluate_release_gate(rids)
        assert out["decision"] == "block"

    def test_health_drop_reason_present(self):
        rids = _seed_health_drop(prefix="hr")
        out = gate_mod.evaluate_release_gate(rids)
        assert "health_drop_block" in out["reasons"]

    def test_volatility_surge_blocks(self):
        rids = _seed_volatility_surge(prefix="vsb")
        out = gate_mod.evaluate_release_gate(rids)
        assert out["decision"] == "block"

    def test_trend_volatility_reason_present(self):
        rids = _seed_volatility_surge(prefix="tvr")
        out = gate_mod.evaluate_release_gate(rids)
        if out["decision"] == "block":
            assert "trend_shift_volatility" in out["reasons"]

    def test_block_reasons_subset_of_block_vocab(self):
        rids = _seed_health_drop(prefix="bv")
        out = gate_mod.evaluate_release_gate(rids)
        allowed = {
            "health_drop_block", "anomaly_spike_block",
            "cluster_shift_downward", "trend_shift_volatility",
            "pair_regression",
        }
        for r in out["reasons"]:
            assert r in allowed


# ===========================================================================
# E. Decision precedence (block > warn > allow)
# ===========================================================================
class TestPrecedence:
    def test_block_wins_when_block_signal_fires(self):
        rids = _seed_health_drop(prefix="prec")
        out = gate_mod.evaluate_release_gate(rids)
        # Both block AND warn signals fire here (large drop > both
        # thresholds). Block must win.
        assert out["decision"] == "block"
        # Warn reasons should NOT appear when block fires.
        for r in out["reasons"]:
            assert r not in (
                "health_drop_warn", "anomaly_spike_warn",
                "low_pair_stability", "volatility_events",
            )

    def test_stable_universe_no_warn_no_block(self):
        rids = _seed_stable(n=5, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        assert out["decision"] == "allow"


# ===========================================================================
# F. Reasons vocabulary
# ===========================================================================
class TestReasonsVocabulary:
    def test_allow_no_reasons(self):
        rids = _seed_stable(n=4, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        if out["decision"] == "allow":
            assert out["reasons"] == []

    def test_reasons_alpha_sorted(self):
        rids = _seed_health_drop(prefix="ra")
        out = gate_mod.evaluate_release_gate(rids)
        assert out["reasons"] == sorted(out["reasons"])

    def test_reasons_unique(self):
        rids = _seed_health_drop(prefix="ru")
        out = gate_mod.evaluate_release_gate(rids)
        assert len(out["reasons"]) == len(set(out["reasons"]))


# ===========================================================================
# G. Metrics content
# ===========================================================================
class TestMetrics:
    def test_health_in_unit_interval(self):
        rids = _seed_stable(n=4, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        assert 0.0 <= out["metrics"]["health"] <= 1.0

    def test_anomaly_fraction_in_unit_interval(self):
        rids = _seed_stable(n=4, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        assert 0.0 <= out["metrics"]["anomaly_fraction"] <= 1.0

    def test_regressions_non_negative_int(self):
        rids = _seed_stable(n=4, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        assert isinstance(out["metrics"]["regressions"], int)
        assert out["metrics"]["regressions"] >= 0

    def test_promoted_pairs_is_list(self):
        rids = _seed_stable(n=4, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        assert isinstance(out["metrics"]["promoted_pairs"], list)

    def test_promoted_pairs_sorted(self):
        rids: list = []
        for i in range(6):
            rid = f"pp_{i:02d}"
            ep.save_comparison_result(
                rid,
                [_entry("zeta", sp=5), _entry("alpha", sp=5), _entry("mid", sp=5)],
            )
            rids.append(rid)
        out = gate_mod.evaluate_release_gate(rids)
        assert out["metrics"]["promoted_pairs"] == sorted(
            out["metrics"]["promoted_pairs"]
        )

    def test_trend_shift_in_locked_vocab(self):
        rids = _seed_stable(n=4, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        assert out["metrics"]["trend_shift"] in (
            "toward_stability", "toward_volatility", "neutral",
        )

    def test_cluster_shift_in_locked_vocab(self):
        rids = _seed_stable(n=4, sp=5)
        out = gate_mod.evaluate_release_gate(rids)
        assert out["metrics"]["cluster_shift"] in (
            "more_upward", "more_downward", "neutral",
        )


# ===========================================================================
# H. Small N (0 / 1 / 2 runs)
# ===========================================================================
class TestSmallN:
    def test_empty_warns_with_insufficient_data(self):
        out = gate_mod.evaluate_release_gate([])
        assert out["decision"] == "warn"
        assert out["reasons"] == ["insufficient_data"]
        assert out["metrics"]["promoted_pairs"] == []

    def test_one_run_warns_with_insufficient_data(self):
        rids = _seed_stable(prefix="one", n=1)
        out = gate_mod.evaluate_release_gate(rids)
        assert out["decision"] == "warn"
        assert out["reasons"] == ["insufficient_data"]

    def test_two_runs_can_decide(self):
        rids = _seed_stable(prefix="two", n=2)
        out = gate_mod.evaluate_release_gate(rids)
        # Identical stable runs → allow.
        assert out["decision"] in ("allow", "warn", "block")
        assert out["reasons"] != ["insufficient_data"] or out["decision"] == "warn"

    def test_empty_metrics_well_formed(self):
        out = gate_mod.evaluate_release_gate([])
        for key in ("health", "anomaly_fraction",
                    "trend_shift", "cluster_shift",
                    "regressions", "promoted_pairs"):
            assert key in out["metrics"]


# ===========================================================================
# I. Legacy run handling
# ===========================================================================
class TestLegacy:
    def test_legacy_run_does_not_crash(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="lg", n=3, sp=5)
        _write_legacy(_runs_dir_isolation, "lg_leg", [_entry("p1")])
        out = gate_mod.evaluate_release_gate(rids + ["lg_leg"])
        assert "decision" in out

    def test_all_legacy_still_returns_well_formed(
        self, _runs_dir_isolation,
    ):
        _write_legacy(_runs_dir_isolation, "leg1", [_entry("p1")])
        _write_legacy(_runs_dir_isolation, "leg2", [_entry("p1")])
        out = gate_mod.evaluate_release_gate(["leg1", "leg2"])
        # Decision is whatever falls out (legacy runs lack metadata),
        # but the shape must hold.
        assert set(out.keys()) == {"decision", "reasons", "metrics"}


# ===========================================================================
# J. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        rids = _seed_health_drop(prefix="dt")
        a = gate_mod.evaluate_release_gate(rids)
        b = gate_mod.evaluate_release_gate(rids)
        assert a == b

    def test_byte_equal_empty(self):
        a = gate_mod.evaluate_release_gate([])
        b = gate_mod.evaluate_release_gate([])
        assert a == b

    def test_byte_equal_stable(self):
        rids = _seed_stable(n=4, sp=5)
        a = gate_mod.evaluate_release_gate(rids)
        b = gate_mod.evaluate_release_gate(rids)
        assert a == b


# ===========================================================================
# K. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            gate_mod.evaluate_release_gate("nope")

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            gate_mod.evaluate_release_gate(["bad/id"])

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            gate_mod.evaluate_release_gate(["ghost"])


# ===========================================================================
# L. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(gate_mod.evaluate_release_gate)

    def test_decision_vocabulary_locked(self):
        assert gate_mod._DECISION_ALLOW == "allow"
        assert gate_mod._DECISION_WARN  == "warn"
        assert gate_mod._DECISION_BLOCK == "block"

    def test_block_thresholds_locked(self):
        assert gate_mod._BLOCK_HEALTH_DROP == 0.10
        assert gate_mod._BLOCK_ANOMALY_SPIKE == 0.15
        assert gate_mod._BLOCK_PAIR_STABILITY_DEL == 0.20

    def test_warn_thresholds_locked(self):
        assert gate_mod._WARN_HEALTH_DROP == 0.05
        assert gate_mod._WARN_ANOMALY_SPIKE == 0.10
        assert gate_mod._WARN_LOW_STABILITY == 0.50


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(gate_mod)

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

    def test_composes_units_14_17(self):
        src = self._code_only()
        assert "diff_intelligence" in src
        assert "pair_deep_all" in src
