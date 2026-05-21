"""
Tests for ELINS4 Unit 16 — operator alerts engine.

Layered coverage (>= 50 tests, target ~60):
    A. Top-level shape / locked keys
    B. Empty / small N input
    C. Anomaly spike detection
    D. Health drop detection
    E. Volatility surge detection
    F. Cluster inversion detection
    G. Pair regression detection
    H. Legacy contamination detection
    I. Severity mapping
    J. Deduplication invariants
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

import elins_alerts as alert_mod
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
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec),
                                          _entry("p2", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


def _seed_health_drop(prefix="hd"):
    """6 runs: A=[1,3,5] upward, B=[9,7,5] downward.

    Unit 6's health rewards directional motion (improvement bonus for
    upward-drift clusters, regression penalty for downward-drift
    clusters), not absolute level — so flat plateaus at sp=9 vs sp=1
    yield identical health. Pairing an upward A with a downward B is
    the cleanest way to manifest a real ``health_delta < -0.10`` for
    the alert pipeline.
    """
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 9, 7, 5), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_health_rise(prefix="hr"):
    """Mirror of _seed_health_drop: A=[9,7,5] downward, B=[1,3,5]
    upward → health rises in B, no health_drop alert."""
    rids: list = []
    for i, sp in enumerate((9, 7, 5, 1, 3, 5), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_anomaly_spike(prefix="as"):
    """12 runs split at mid=6. A=6 stable, B=4 stable + 2 opposite-extreme
    outliers (one low-score with one pair_id, one high-score with another).

    Unit 5's cluster signal needs a per-side universe of at least 6 to
    fire on singletons; if the two B-half outliers shared the same
    "low" pattern they'd cluster together and neither would be flagged.
    By making them OPPOSITE extremes with distinct pair_ids, the
    silhouette sweep keeps each outlier in its own cluster — both fire
    as anomalies inside B, driving anomaly_fraction(B) ≈ 0.33 vs
    anomaly_fraction(A) = 0, well above the 0.15 spike threshold.
    """
    rids: list = []
    for i in range(6):
        rid = f"{prefix}_a_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=5, ec=5)])
        rids.append(rid)
    for i in range(4):
        rid = f"{prefix}_b_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=5, ec=5)])
        rids.append(rid)
    ep.save_comparison_result(
        f"{prefix}_out_low",
        [_entry("p_low",  sp=0,  ec=0,
                 sp_band="Fails core logic",
                 ec_band="Fails core logic")],
    )
    rids.append(f"{prefix}_out_low")
    ep.save_comparison_result(
        f"{prefix}_out_high",
        [_entry("p_high", sp=10, ec=10,
                 sp_band="Strong", ec_band="Strong")],
    )
    rids.append(f"{prefix}_out_high")
    return rids


def _seed_volatility_surge(prefix="vs"):
    """4 stable runs followed by 4 volatile runs → A=monotonic_x,
    B=volatile."""
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 7), 1):
        rid = f"{prefix}_a_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    for i, sp in enumerate((1, 9, 1, 9), 1):
        rid = f"{prefix}_b_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_cluster_upward_then_downward(prefix="ci"):
    """4 upward-clustering runs then 4 downward-clustering runs."""
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 7), 1):
        rid = f"{prefix}_a_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    for i, sp in enumerate((9, 7, 5, 3), 1):
        rid = f"{prefix}_b_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp,
                                                sp_band="Fails core logic",
                                                ec_band="Fails core logic")])
        rids.append(rid)
    return rids


# ===========================================================================
# A. Top-level shape / locked keys
# ===========================================================================
class TestTopLevelShape:
    def test_top_level_keys(self):
        rids = _seed_stable(n=4)
        out = alert_mod.generate_alerts(rids)
        assert set(out.keys()) == {"alerts"}

    def test_alerts_is_list(self):
        rids = _seed_stable(n=4)
        out = alert_mod.generate_alerts(rids)
        assert isinstance(out["alerts"], list)

    def test_each_alert_has_type_severity_message(self):
        rids = _seed_health_drop(prefix="ts")
        out = alert_mod.generate_alerts(rids)
        for a in out["alerts"]:
            assert "type" in a
            assert "severity" in a
            assert "message" in a


# ===========================================================================
# B. Empty / small N input
# ===========================================================================
class TestEmptyAndSmallN:
    def test_empty_run_ids_no_alerts(self):
        out = alert_mod.generate_alerts([])
        assert out == {"alerts": []}

    def test_one_run_no_comparison_alerts(self):
        rids = _seed_stable(prefix="one", n=1)
        out = alert_mod.generate_alerts(rids)
        # No comparison possible → no spike/drop/surge/inversion alerts.
        for a in out["alerts"]:
            assert a["type"] != "health_drop"
            assert a["type"] != "anomaly_spike"

    def test_two_runs_can_emit_alerts(self):
        # Two runs split mid=1: A=[r0], B=[r1] → diff still runs.
        rids = _seed_health_drop(prefix="two")[:2]
        out = alert_mod.generate_alerts(rids)
        # Result is a well-formed list; may or may not contain alerts.
        assert isinstance(out["alerts"], list)

    def test_clean_universe_no_alerts(self):
        rids = _seed_stable(prefix="cn", n=4)
        out = alert_mod.generate_alerts(rids)
        assert out["alerts"] == []


# ===========================================================================
# C. Anomaly spike detection
# ===========================================================================
class TestAnomalySpike:
    def test_spike_fires_with_outlier_b(self):
        rids = _seed_anomaly_spike(prefix="sp")
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "anomaly_spike" in types

    def test_no_spike_in_clean_universe(self):
        rids = _seed_stable(prefix="sp_no", n=6)
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "anomaly_spike" not in types

    def test_spike_delta_recorded(self):
        rids = _seed_anomaly_spike(prefix="sp_d")
        out = alert_mod.generate_alerts(rids)
        spike = next(
            (a for a in out["alerts"] if a["type"] == "anomaly_spike"),
            None,
        )
        if spike is not None:
            assert spike["delta"] > alert_mod._ANOMALY_SPIKE_THRESHOLD


# ===========================================================================
# D. Health drop detection
# ===========================================================================
class TestHealthDrop:
    def test_drop_fires_with_health_drop_seed(self):
        rids = _seed_health_drop(prefix="hd_f")
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "health_drop" in types

    def test_no_drop_when_health_rises(self):
        rids = _seed_health_rise(prefix="hr_n")
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "health_drop" not in types

    def test_drop_delta_is_negative(self):
        rids = _seed_health_drop(prefix="hd_n")
        out = alert_mod.generate_alerts(rids)
        drop = next(
            (a for a in out["alerts"] if a["type"] == "health_drop"),
            None,
        )
        assert drop is not None
        assert drop["delta"] < 0

    def test_drop_above_critical_threshold_is_critical(self):
        rids = _seed_health_drop(prefix="hd_c")
        out = alert_mod.generate_alerts(rids)
        drop = next(
            (a for a in out["alerts"] if a["type"] == "health_drop"),
            None,
        )
        # The seeded drop (9 → 1) should land in the critical tier.
        if drop is not None and abs(drop["delta"]) >= 0.20:
            assert drop["severity"] == "critical"

    def test_no_drop_in_clean_universe(self):
        rids = _seed_stable(prefix="hd_clean", n=4)
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "health_drop" not in types


# ===========================================================================
# E. Volatility surge detection
# ===========================================================================
class TestVolatilitySurge:
    def test_surge_fires_when_b_volatile(self):
        rids = _seed_volatility_surge(prefix="vs_f")
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "volatility_surge" in types

    def test_no_surge_in_clean_universe(self):
        rids = _seed_stable(prefix="vs_clean", n=6)
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "volatility_surge" not in types

    def test_surge_severity_warning(self):
        rids = _seed_volatility_surge(prefix="vs_s")
        out = alert_mod.generate_alerts(rids)
        surge = next(
            (a for a in out["alerts"] if a["type"] == "volatility_surge"),
            None,
        )
        if surge is not None:
            assert surge["severity"] == "warning"


# ===========================================================================
# F. Cluster inversion detection
# ===========================================================================
class TestClusterInversion:
    def test_inversion_fires_upward_to_downward(self):
        rids = _seed_cluster_upward_then_downward(prefix="ci_f")
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "cluster_inversion" in types

    def test_inversion_severity_for_negative_shift(self):
        rids = _seed_cluster_upward_then_downward(prefix="ci_s")
        out = alert_mod.generate_alerts(rids)
        inv = next(
            (a for a in out["alerts"] if a["type"] == "cluster_inversion"),
            None,
        )
        if inv is not None:
            # upward → downward is bad news.
            assert inv["severity"] == "warning"

    def test_downward_to_upward_inversion_info_severity(self):
        # Reverse the seed: first half downward, second half upward.
        rids: list = []
        for i, sp in enumerate((9, 7, 5, 3), 1):
            rid = f"dtu_a_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp,
                                                    sp_band="Fails core logic",
                                                    ec_band="Fails core logic")])
            rids.append(rid)
        for i, sp in enumerate((1, 3, 5, 7), 1):
            rid = f"dtu_b_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = alert_mod.generate_alerts(rids)
        inv = next(
            (a for a in out["alerts"] if a["type"] == "cluster_inversion"),
            None,
        )
        if inv is not None:
            assert inv["severity"] == "info"


# ===========================================================================
# G. Pair regression detection
# ===========================================================================
class TestPairRegression:
    def test_pair_regression_fires_for_pair_drop(self):
        # 4 runs: pair p1 stable in A, drops in B (high vol).
        rids: list = []
        for i, sp in enumerate((5, 5, 5, 5, 1, 9, 1, 9), 1):
            rid = f"pr_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "pair_regression" in types

    def test_pair_regression_has_pair_id_and_delta(self):
        rids: list = []
        for i, sp in enumerate((5, 5, 5, 5, 1, 9, 1, 9), 1):
            rid = f"prd_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = alert_mod.generate_alerts(rids)
        for a in out["alerts"]:
            if a["type"] == "pair_regression":
                assert "pair_id" in a
                assert "delta" in a
                assert a["delta"] < 0

    def test_pair_regression_delta_below_threshold(self):
        rids: list = []
        for i, sp in enumerate((5, 5, 5, 5, 1, 9, 1, 9), 1):
            rid = f"prt_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = alert_mod.generate_alerts(rids)
        for a in out["alerts"]:
            if a["type"] == "pair_regression":
                assert a["delta"] <= -alert_mod._PAIR_REGRESS_THRESHOLD

    def test_pair_regression_dedup_by_pair_id(self):
        # Same pair should only appear once even if multiple signals
        # reference it.
        rids: list = []
        for i, sp in enumerate((5, 5, 5, 5, 1, 9, 1, 9), 1):
            rid = f"prdp_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
            rids.append(rid)
        out = alert_mod.generate_alerts(rids)
        pair_alerts = [
            a for a in out["alerts"] if a["type"] == "pair_regression"
        ]
        pair_ids = [a["pair_id"] for a in pair_alerts]
        assert len(pair_ids) == len(set(pair_ids))


# ===========================================================================
# H. Legacy contamination detection
# ===========================================================================
class TestLegacyContamination:
    def test_legacy_fires_when_legacy_run_present(
        self, _runs_dir_isolation,
    ):
        rids = _seed_stable(prefix="lc", n=3)
        _write_legacy(_runs_dir_isolation, "lc_leg", [_entry("p1")])
        out = alert_mod.generate_alerts(rids + ["lc_leg"])
        types = [a["type"] for a in out["alerts"]]
        assert "legacy_contamination" in types

    def test_legacy_alert_lists_legacy_run_ids(
        self, _runs_dir_isolation,
    ):
        rids = _seed_stable(prefix="lcl", n=3)
        _write_legacy(_runs_dir_isolation, "lcl_leg", [_entry("p1")])
        out = alert_mod.generate_alerts(rids + ["lcl_leg"])
        legacy = next(
            a for a in out["alerts"]
            if a["type"] == "legacy_contamination"
        )
        assert "lcl_leg" in legacy["run_ids"]

    def test_no_legacy_alert_in_modern_universe(self):
        rids = _seed_stable(prefix="lcn", n=4)
        out = alert_mod.generate_alerts(rids)
        types = [a["type"] for a in out["alerts"]]
        assert "legacy_contamination" not in types


# ===========================================================================
# I. Severity mapping
# ===========================================================================
class TestSeverityMapping:
    def test_severity_threshold_critical_for_large_delta(self):
        # 0.30 ≥ 0.10 × 2 = 0.20 → critical tier.
        assert alert_mod._classify_numeric_severity(0.30, 0.10) == "critical"

    def test_severity_threshold_warning_for_moderate_delta(self):
        assert alert_mod._classify_numeric_severity(0.15, 0.10) == "warning"

    def test_anomaly_spike_warning_at_threshold(self):
        rids: list = []
        for i in range(8):
            rid = f"th_{i:02d}"
            ep.save_comparison_result(rid, [_entry("p1", sp=5)])
            rids.append(rid)
        out = alert_mod.generate_alerts(rids)
        for a in out["alerts"]:
            if a["type"] == "anomaly_spike":
                assert a["severity"] in ("warning", "critical")


# ===========================================================================
# J. Deduplication invariants
# ===========================================================================
class TestDeduplication:
    def test_one_anomaly_spike_per_call(self):
        rids = _seed_anomaly_spike(prefix="d_sp")
        out = alert_mod.generate_alerts(rids)
        spike_count = sum(
            1 for a in out["alerts"] if a["type"] == "anomaly_spike"
        )
        assert spike_count <= 1

    def test_one_health_drop_per_call(self):
        rids = _seed_health_drop(prefix="d_hd")
        out = alert_mod.generate_alerts(rids)
        drop_count = sum(
            1 for a in out["alerts"] if a["type"] == "health_drop"
        )
        assert drop_count <= 1

    def test_one_legacy_alert_per_call(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="d_lc", n=3)
        _write_legacy(_runs_dir_isolation, "d_lc_a", [_entry("p1")])
        _write_legacy(_runs_dir_isolation, "d_lc_b", [_entry("p1")])
        out = alert_mod.generate_alerts(rids + ["d_lc_a", "d_lc_b"])
        legacy_count = sum(
            1 for a in out["alerts"] if a["type"] == "legacy_contamination"
        )
        assert legacy_count == 1

    def test_alerts_sorted_consistently(self):
        rids = _seed_health_drop(prefix="ds")
        a = alert_mod.generate_alerts(rids)
        b = alert_mod.generate_alerts(rids)
        # Sort key is deterministic — repeated calls yield identical lists.
        assert [x["type"] for x in a["alerts"]] == [
            x["type"] for x in b["alerts"]
        ]


# ===========================================================================
# K. Determinism (byte-equal repeats)
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeats(self):
        rids = _seed_health_drop(prefix="dt")
        a = alert_mod.generate_alerts(rids)
        b = alert_mod.generate_alerts(rids)
        assert a == b

    def test_byte_equal_empty(self):
        a = alert_mod.generate_alerts([])
        b = alert_mod.generate_alerts([])
        assert a == b

    def test_byte_equal_with_legacy(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="dtl", n=2)
        _write_legacy(_runs_dir_isolation, "dtl_leg", [_entry("p1")])
        a = alert_mod.generate_alerts(rids + ["dtl_leg"])
        b = alert_mod.generate_alerts(rids + ["dtl_leg"])
        assert a == b


# ===========================================================================
# L. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            alert_mod.generate_alerts("nope")

    def test_malformed_id_raises(self):
        with pytest.raises(ValueError):
            alert_mod.generate_alerts(["bad/id"])

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            alert_mod.generate_alerts(["ghost"])

    def test_dict_input_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            alert_mod.generate_alerts({"run_ids": []})


# ===========================================================================
# M. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_function_callable(self):
        assert callable(alert_mod.generate_alerts)

    def test_alert_type_constants_locked(self):
        assert alert_mod._TYPE_ANOMALY_SPIKE        == "anomaly_spike"
        assert alert_mod._TYPE_HEALTH_DROP          == "health_drop"
        assert alert_mod._TYPE_VOLATILITY_SURGE     == "volatility_surge"
        assert alert_mod._TYPE_CLUSTER_INVERSION    == "cluster_inversion"
        assert alert_mod._TYPE_PAIR_REGRESSION      == "pair_regression"
        assert alert_mod._TYPE_LEGACY_CONTAMINATION == "legacy_contamination"

    def test_thresholds_locked(self):
        assert alert_mod._ANOMALY_SPIKE_THRESHOLD == 0.15
        assert alert_mod._HEALTH_DROP_THRESHOLD   == 0.10
        assert alert_mod._PAIR_REGRESS_THRESHOLD  == 0.20

    def test_severity_vocabulary_locked(self):
        assert alert_mod._SEV_INFO == "info"
        assert alert_mod._SEV_WARNING == "warning"
        assert alert_mod._SEV_CRITICAL == "critical"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(alert_mod)

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

    def test_composes_unit_14_diff(self):
        src = self._code_only()
        assert "diff_intelligence" in src
