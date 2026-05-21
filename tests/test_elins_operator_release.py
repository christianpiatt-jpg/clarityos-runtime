"""
Tests for ELINS6 Unit 20 — operator release actions.

Layered coverage (>= 50 tests, target ~60):
    A. apply_release_gate — happy path, decision propagation, tagging
    B. apply_release_gate — idempotency + existing-tag preservation
    C. tag_release_decision — happy path
    D. tag_release_decision — idempotency invariants
    E. tag_release_decision — validation
    F. generate_release_report — shape + content
    G. generate_release_report — content delegation
    H. generate_release_report — small / empty / legacy
    I. Validation across all three
    J. Determinism (byte-equal repeats — within constraints)
    K. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_alerts as alert_mod
import elins_intel_diff as diff_mod
import elins_intelligence as intel_mod
import elins_operator_release as opr_mod
import elins_pair_deep as pd_mod
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
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 9, 7, 5), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


def _seed_volatile(prefix="vlt"):
    rids: list = []
    for i, sp in enumerate((1, 9, 1, 9, 1, 9), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. apply_release_gate — happy path, decision propagation, tagging
# ===========================================================================
class TestApplyReleaseGateHappy:
    def test_response_shape(self):
        rids = _seed_stable(n=4)
        out = opr_mod.apply_release_gate(rids)
        assert set(out.keys()) == {"decision", "tagged_runs"}

    def test_decision_propagates(self):
        rids = _seed_health_drop(prefix="dp")
        gate_decision = gate_mod.evaluate_release_gate(rids)["decision"]
        out = opr_mod.apply_release_gate(rids)
        assert out["decision"] == gate_decision

    def test_block_decision_tags_runs_with_blocked(self):
        rids = _seed_health_drop(prefix="bt")
        out = opr_mod.apply_release_gate(rids)
        if out["decision"] == "block":
            for rid in out["tagged_runs"]:
                assert "release_blocked" in ep_sql.get_tags(rid)

    def test_allow_decision_tags_runs_with_allowed(self):
        rids = _seed_stable(prefix="at", n=4, sp=5)
        out = opr_mod.apply_release_gate(rids)
        if out["decision"] == "allow":
            for rid in out["tagged_runs"]:
                assert "release_allowed" in ep_sql.get_tags(rid)

    def test_tagged_runs_alpha_sorted(self):
        rids = _seed_stable(prefix="ts", n=4, sp=5)
        out = opr_mod.apply_release_gate(rids)
        assert out["tagged_runs"] == sorted(out["tagged_runs"])


# ===========================================================================
# B. apply_release_gate — idempotency + existing-tag preservation
# ===========================================================================
class TestApplyReleaseGateIdempotency:
    def test_repeat_call_no_duplicate_tag(self):
        rids = _seed_stable(prefix="rp", n=4, sp=5)
        opr_mod.apply_release_gate(rids)
        opr_mod.apply_release_gate(rids)
        for rid in rids:
            tags = ep_sql.get_tags(rid)
            release_tags = [t for t in tags if t.startswith("release_")]
            for tag in set(release_tags):
                assert release_tags.count(tag) == 1

    def test_existing_tags_preserved(self):
        rids = _seed_stable(prefix="ex", n=4, sp=5)
        ep_sql.set_tags(rids[0], ["other_tag"])
        opr_mod.apply_release_gate(rids)
        assert "other_tag" in ep_sql.get_tags(rids[0])

    def test_second_call_tagged_runs_empty(self):
        rids = _seed_stable(prefix="rb", n=4, sp=5)
        opr_mod.apply_release_gate(rids)
        second = opr_mod.apply_release_gate(rids)
        # Second call adds nothing new — tagged_runs is empty.
        assert second["tagged_runs"] == []


# ===========================================================================
# C. tag_release_decision — happy path
# ===========================================================================
class TestTagReleaseDecisionHappy:
    def test_response_shape(self):
        rids = _seed_stable(n=2)
        out = opr_mod.tag_release_decision(rids, "allow")
        assert set(out.keys()) == {"decision", "applied", "tagged_runs"}

    def test_applied_always_true(self):
        rids = _seed_stable(n=2)
        out = opr_mod.tag_release_decision(rids, "warn")
        assert out["applied"] is True

    def test_decision_echoed(self):
        rids = _seed_stable(n=2)
        out = opr_mod.tag_release_decision(rids, "block")
        assert out["decision"] == "block"

    def test_block_decision_applies_blocked_tag(self):
        rids = _seed_stable(prefix="bk", n=2)
        opr_mod.tag_release_decision(rids, "block")
        for rid in rids:
            assert "release_blocked" in ep_sql.get_tags(rid)

    def test_warn_decision_applies_warn_tag(self):
        rids = _seed_stable(prefix="wn", n=2)
        opr_mod.tag_release_decision(rids, "warn")
        for rid in rids:
            assert "release_warn" in ep_sql.get_tags(rid)

    def test_allow_decision_applies_allowed_tag(self):
        rids = _seed_stable(prefix="al", n=2)
        opr_mod.tag_release_decision(rids, "allow")
        for rid in rids:
            assert "release_allowed" in ep_sql.get_tags(rid)


# ===========================================================================
# D. tag_release_decision — idempotency invariants
# ===========================================================================
class TestTagReleaseDecisionIdempotency:
    def test_repeat_call_no_duplicate(self):
        rids = _seed_stable(prefix="rt", n=2)
        opr_mod.tag_release_decision(rids, "warn")
        opr_mod.tag_release_decision(rids, "warn")
        for rid in rids:
            assert ep_sql.get_tags(rid).count("release_warn") == 1

    def test_repeat_call_second_tagged_runs_empty(self):
        rids = _seed_stable(prefix="rt2", n=2)
        opr_mod.tag_release_decision(rids, "warn")
        second = opr_mod.tag_release_decision(rids, "warn")
        assert second["tagged_runs"] == []

    def test_existing_tags_preserved(self):
        rids = _seed_stable(prefix="ext", n=2)
        ep_sql.set_tags(rids[0], ["other_tag"])
        opr_mod.tag_release_decision(rids, "allow")
        tags = ep_sql.get_tags(rids[0])
        assert "other_tag" in tags
        assert "release_allowed" in tags

    def test_different_decisions_coexist(self):
        rids = _seed_stable(prefix="dec", n=2)
        opr_mod.tag_release_decision(rids, "warn")
        opr_mod.tag_release_decision(rids, "block")
        # Both tags are present — tag_release_decision is purely additive.
        for rid in rids:
            tags = ep_sql.get_tags(rid)
            assert "release_warn" in tags
            assert "release_blocked" in tags


# ===========================================================================
# E. tag_release_decision — validation
# ===========================================================================
class TestTagReleaseDecisionValidation:
    def test_invalid_decision_raises(self):
        rids = _seed_stable(n=2)
        with pytest.raises(ValueError, match="decision"):
            opr_mod.tag_release_decision(rids, "maybe")

    def test_non_string_decision_raises(self):
        rids = _seed_stable(n=2)
        with pytest.raises(ValueError, match="decision"):
            opr_mod.tag_release_decision(rids, 123)

    def test_empty_decision_raises(self):
        rids = _seed_stable(n=2)
        with pytest.raises(ValueError, match="decision"):
            opr_mod.tag_release_decision(rids, "")

    def test_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="list"):
            opr_mod.tag_release_decision("nope", "allow")

    def test_malformed_run_id_raises(self):
        with pytest.raises(ValueError):
            opr_mod.tag_release_decision(["bad/id"], "allow")

    def test_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            opr_mod.tag_release_decision(["ghost"], "allow")

    def test_empty_run_ids_no_error(self):
        out = opr_mod.tag_release_decision([], "allow")
        assert out["applied"] is True
        assert out["tagged_runs"] == []


# ===========================================================================
# F. generate_release_report — shape + content
# ===========================================================================
class TestGenerateReleaseReportShape:
    def test_top_level_keys(self):
        rids = _seed_stable(prefix="sh", n=4, sp=5)
        out = opr_mod.generate_release_report(rids)
        assert set(out.keys()) == {
            "headline", "decision", "metrics",
            "alerts", "pairs", "diff",
        }

    def test_headline_non_empty(self):
        rids = _seed_stable(prefix="hd", n=4, sp=5)
        out = opr_mod.generate_release_report(rids)
        assert isinstance(out["headline"], str)
        assert out["headline"].strip() != ""

    def test_metrics_keys_locked(self):
        rids = _seed_stable(prefix="mk", n=4, sp=5)
        out = opr_mod.generate_release_report(rids)
        assert set(out["metrics"].keys()) == {
            "health", "anomaly_fraction",
            "trend_shift", "cluster_shift",
            "regressions", "promoted_pairs",
        }

    def test_alerts_is_list(self):
        rids = _seed_stable(prefix="al", n=4, sp=5)
        out = opr_mod.generate_release_report(rids)
        assert isinstance(out["alerts"], list)

    def test_pairs_has_unit_17_shape(self):
        rids = _seed_stable(prefix="ps", n=4, sp=5)
        out = opr_mod.generate_release_report(rids)
        assert set(out["pairs"].keys()) == {"pairs", "run_ids"}


# ===========================================================================
# G. generate_release_report — content delegation
# ===========================================================================
class TestReportDelegation:
    def test_decision_matches_gate(self):
        rids = _seed_health_drop(prefix="dg")
        out = opr_mod.generate_release_report(rids)
        gate = gate_mod.evaluate_release_gate(rids)
        assert out["decision"] == gate["decision"]

    def test_metrics_matches_gate(self):
        rids = _seed_stable(prefix="mg", n=4, sp=5)
        out = opr_mod.generate_release_report(rids)
        gate = gate_mod.evaluate_release_gate(rids)
        assert out["metrics"] == gate["metrics"]

    def test_alerts_matches_unit_16(self):
        rids = _seed_stable(prefix="am", n=4, sp=5)
        out = opr_mod.generate_release_report(rids)
        alerts = alert_mod.generate_alerts(rids)
        assert out["alerts"] == alerts["alerts"]

    def test_pairs_matches_unit_17(self):
        rids = _seed_stable(prefix="pm", n=4, sp=5)
        out = opr_mod.generate_release_report(rids)
        expected = pd_mod.pair_deep_all(rids)
        assert out["pairs"] == expected

    def test_diff_matches_unit_14(self):
        rids = _seed_health_drop(prefix="dm")
        out = opr_mod.generate_release_report(rids)
        mid = len(rids) // 2
        expected = diff_mod.diff_intelligence(rids[:mid], rids[mid:])
        assert out["diff"] == expected


# ===========================================================================
# H. generate_release_report — small / empty / legacy
# ===========================================================================
class TestReportSmallN:
    def test_empty_returns_well_formed(self):
        out = opr_mod.generate_release_report([])
        assert set(out.keys()) == {
            "headline", "decision", "metrics",
            "alerts", "pairs", "diff",
        }
        assert out["decision"] == "warn"
        assert out["diff"] is None
        assert out["alerts"] == []

    def test_one_run_diff_is_none(self):
        rids = _seed_stable(prefix="or", n=1)
        out = opr_mod.generate_release_report(rids)
        assert out["diff"] is None

    def test_two_runs_diff_present(self):
        rids = _seed_stable(prefix="tr", n=2)
        out = opr_mod.generate_release_report(rids)
        assert out["diff"] is not None

    def test_legacy_run_does_not_crash(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="lg", n=3, sp=5)
        _write_legacy(_runs_dir_isolation, "lg_leg", [_entry("p1")])
        out = opr_mod.generate_release_report(rids + ["lg_leg"])
        assert isinstance(out, dict)


# ===========================================================================
# I. Validation across all three
# ===========================================================================
class TestValidation:
    def test_apply_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            opr_mod.apply_release_gate("nope")

    def test_apply_malformed_id_raises(self):
        with pytest.raises(ValueError):
            opr_mod.apply_release_gate(["bad/id"])

    def test_apply_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            opr_mod.apply_release_gate(["ghost"])

    def test_report_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            opr_mod.generate_release_report("nope")

    def test_report_malformed_id_raises(self):
        with pytest.raises(ValueError):
            opr_mod.generate_release_report(["bad/id"])

    def test_report_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            opr_mod.generate_release_report(["ghost"])


# ===========================================================================
# J. Determinism
# ===========================================================================
class TestDeterminism:
    def test_apply_repeat_yields_same_decision(self):
        rids = _seed_stable(prefix="dt", n=4, sp=5)
        a = opr_mod.apply_release_gate(rids)
        b = opr_mod.apply_release_gate(rids)
        assert a["decision"] == b["decision"]

    def test_tag_repeat_decision_stable(self):
        rids = _seed_stable(prefix="td", n=2)
        a = opr_mod.tag_release_decision(rids, "warn")
        b = opr_mod.tag_release_decision(rids, "warn")
        assert a["decision"] == b["decision"]

    def test_report_byte_equal(self):
        rids = _seed_stable(prefix="rb", n=4, sp=5)
        a = opr_mod.generate_release_report(rids)
        b = opr_mod.generate_release_report(rids)
        assert a == b


# ===========================================================================
# K. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            opr_mod.apply_release_gate,
            opr_mod.tag_release_decision,
            opr_mod.generate_release_report,
        ):
            assert callable(fn)

    def test_tag_vocabulary_locked(self):
        assert opr_mod.TAG_RELEASE_BLOCKED == "release_blocked"
        assert opr_mod.TAG_RELEASE_WARN    == "release_warn"
        assert opr_mod.TAG_RELEASE_ALLOWED == "release_allowed"

    def test_decision_tag_map_complete(self):
        for d in ("allow", "warn", "block"):
            assert d in opr_mod._DECISION_TAG_MAP


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(opr_mod)

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

    def test_composes_units_9_14_16_17_19(self):
        src = self._code_only()
        for required in (
            "intelligence_for_run_ids",   # Unit 9
            "diff_intelligence",          # Unit 14
            "generate_alerts",            # Unit 16
            "pair_deep_all",              # Unit 17
            "evaluate_release_gate",      # Unit 19
        ):
            assert required in src
