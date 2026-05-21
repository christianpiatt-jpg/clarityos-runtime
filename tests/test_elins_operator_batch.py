"""
Tests for ELINS7 Unit 22 — operator batch actions.

Layered coverage (>= 60 tests, target ~70):
    A. apply_batch_gate — happy path + decision propagation
    B. apply_batch_gate — idempotency + existing tag preservation
    C. tag_batch_decisions — happy path
    D. tag_batch_decisions — idempotency
    E. tag_batch_decisions — validation
    F. generate_batch_report — shape + content
    G. generate_batch_report — delegation
    H. generate_batch_report — small / empty / legacy
    I. Validation across all three
    J. Determinism (byte-equal repeats — within tag side-effect bounds)
    K. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import sqlite3
from pathlib import Path

import pytest

import elins_alerts as alert_mod
import elins_batch_eval as batch_mod
import elins_intel_diff as diff_mod
import elins_operator_batch as opb_mod
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


def _seed_health_drop(prefix="hd"):
    rids: list = []
    for i, sp in enumerate((1, 3, 5, 9, 7, 5), 1):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=sp)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. apply_batch_gate — happy path + decision propagation
# ===========================================================================
class TestApplyBatchGateHappy:
    def test_response_shape(self):
        groups = {
            "a": _seed_stable(prefix="aha", n=3),
            "b": _seed_stable(prefix="ahb", n=3),
        }
        out = opb_mod.apply_batch_gate(groups)
        assert set(out.keys()) == {"groups"}

    def test_groups_keys_match_input(self):
        groups = {
            "a": _seed_stable(prefix="gma", n=3),
            "b": _seed_stable(prefix="gmb", n=3),
        }
        out = opb_mod.apply_batch_gate(groups)
        assert set(out["groups"].keys()) == set(groups.keys())

    def test_group_entry_keys_locked(self):
        groups = {"x": _seed_stable(prefix="gek", n=3)}
        out = opb_mod.apply_batch_gate(groups)
        assert set(out["groups"]["x"].keys()) == {
            "decision", "tagged_runs",
        }

    def test_decision_propagates_from_unit_21(self):
        groups = {"hd": _seed_health_drop(prefix="dp")}
        out = opb_mod.apply_batch_gate(groups)
        batch = batch_mod.evaluate_batch(groups)
        assert out["groups"]["hd"]["decision"] == \
               batch["groups"]["hd"]["decision"]

    def test_block_decision_tags_with_blocked(self):
        groups = {"hd": _seed_health_drop(prefix="bk")}
        out = opb_mod.apply_batch_gate(groups)
        if out["groups"]["hd"]["decision"] == "block":
            for rid in out["groups"]["hd"]["tagged_runs"]:
                assert "batch_blocked" in ep_sql.get_tags(rid)

    def test_allow_decision_tags_with_allowed(self):
        groups = {"st": _seed_stable(prefix="ad", n=4, sp=5)}
        out = opb_mod.apply_batch_gate(groups)
        if out["groups"]["st"]["decision"] == "allow":
            for rid in out["groups"]["st"]["tagged_runs"]:
                assert "batch_allowed" in ep_sql.get_tags(rid)

    def test_tagged_runs_alpha_sorted(self):
        groups = {"st": _seed_stable(prefix="srt", n=4, sp=5)}
        out = opb_mod.apply_batch_gate(groups)
        assert out["groups"]["st"]["tagged_runs"] == \
               sorted(out["groups"]["st"]["tagged_runs"])


# ===========================================================================
# B. apply_batch_gate — idempotency + existing tag preservation
# ===========================================================================
class TestApplyBatchGateIdempotency:
    def test_repeat_call_no_duplicate_tag(self):
        groups = {"st": _seed_stable(prefix="rp", n=4, sp=5)}
        opb_mod.apply_batch_gate(groups)
        opb_mod.apply_batch_gate(groups)
        for rid in groups["st"]:
            tags = ep_sql.get_tags(rid)
            batch_tags = [t for t in tags if t.startswith("batch_")]
            for t in set(batch_tags):
                assert batch_tags.count(t) == 1

    def test_existing_tags_preserved(self):
        groups = {"st": _seed_stable(prefix="ex", n=3, sp=5)}
        ep_sql.set_tags(groups["st"][0], ["other_tag"])
        opb_mod.apply_batch_gate(groups)
        assert "other_tag" in ep_sql.get_tags(groups["st"][0])

    def test_second_call_tagged_runs_empty(self):
        groups = {"st": _seed_stable(prefix="rb", n=3, sp=5)}
        opb_mod.apply_batch_gate(groups)
        second = opb_mod.apply_batch_gate(groups)
        assert second["groups"]["st"]["tagged_runs"] == []


# ===========================================================================
# C. tag_batch_decisions — happy path
# ===========================================================================
class TestTagBatchDecisionsHappy:
    def test_response_shape(self):
        groups = {"a": _seed_stable(prefix="trsa", n=2)}
        out = opb_mod.tag_batch_decisions(groups, {"a": "allow"})
        assert set(out.keys()) == {"applied", "tagged"}

    def test_applied_always_true(self):
        groups = {"a": _seed_stable(prefix="atat", n=2)}
        out = opb_mod.tag_batch_decisions(groups, {"a": "warn"})
        assert out["applied"] is True

    def test_tagged_dict_keys_match_groups(self):
        groups = {
            "a": _seed_stable(prefix="tdm_a", n=2),
            "b": _seed_stable(prefix="tdm_b", n=2),
        }
        decisions = {"a": "allow", "b": "block"}
        out = opb_mod.tag_batch_decisions(groups, decisions)
        assert set(out["tagged"].keys()) == set(groups.keys())

    def test_block_decision_tags_with_blocked(self):
        groups = {"a": _seed_stable(prefix="bk_a", n=2)}
        opb_mod.tag_batch_decisions(groups, {"a": "block"})
        for rid in groups["a"]:
            assert "batch_blocked" in ep_sql.get_tags(rid)

    def test_warn_decision_tags_with_warn(self):
        groups = {"a": _seed_stable(prefix="wn_a", n=2)}
        opb_mod.tag_batch_decisions(groups, {"a": "warn"})
        for rid in groups["a"]:
            assert "batch_warn" in ep_sql.get_tags(rid)

    def test_allow_decision_tags_with_allowed(self):
        groups = {"a": _seed_stable(prefix="al_a", n=2)}
        opb_mod.tag_batch_decisions(groups, {"a": "allow"})
        for rid in groups["a"]:
            assert "batch_allowed" in ep_sql.get_tags(rid)

    def test_per_group_independent_decisions(self):
        groups = {
            "a": _seed_stable(prefix="pgi_a", n=2),
            "b": _seed_stable(prefix="pgi_b", n=2),
        }
        opb_mod.tag_batch_decisions(groups, {"a": "allow", "b": "block"})
        for rid in groups["a"]:
            assert "batch_allowed" in ep_sql.get_tags(rid)
            assert "batch_blocked" not in ep_sql.get_tags(rid)
        for rid in groups["b"]:
            assert "batch_blocked" in ep_sql.get_tags(rid)
            assert "batch_allowed" not in ep_sql.get_tags(rid)


# ===========================================================================
# D. tag_batch_decisions — idempotency
# ===========================================================================
class TestTagBatchDecisionsIdempotency:
    def test_repeat_call_no_duplicate(self):
        groups = {"a": _seed_stable(prefix="dt_a", n=2)}
        opb_mod.tag_batch_decisions(groups, {"a": "warn"})
        opb_mod.tag_batch_decisions(groups, {"a": "warn"})
        for rid in groups["a"]:
            assert ep_sql.get_tags(rid).count("batch_warn") == 1

    def test_repeat_call_second_tagged_empty(self):
        groups = {"a": _seed_stable(prefix="dt2_a", n=2)}
        opb_mod.tag_batch_decisions(groups, {"a": "warn"})
        second = opb_mod.tag_batch_decisions(groups, {"a": "warn"})
        assert second["tagged"]["a"] == []

    def test_existing_tags_preserved(self):
        groups = {"a": _seed_stable(prefix="ep_a", n=2)}
        ep_sql.set_tags(groups["a"][0], ["other_tag"])
        opb_mod.tag_batch_decisions(groups, {"a": "warn"})
        tags = ep_sql.get_tags(groups["a"][0])
        assert "other_tag" in tags
        assert "batch_warn" in tags

    def test_different_decisions_coexist(self):
        groups = {"a": _seed_stable(prefix="dc_a", n=2)}
        opb_mod.tag_batch_decisions(groups, {"a": "warn"})
        opb_mod.tag_batch_decisions(groups, {"a": "block"})
        for rid in groups["a"]:
            tags = ep_sql.get_tags(rid)
            assert "batch_warn" in tags
            assert "batch_blocked" in tags


# ===========================================================================
# E. tag_batch_decisions — validation
# ===========================================================================
class TestTagBatchDecisionsValidation:
    def test_invalid_decision_raises(self):
        groups = {"a": _seed_stable(prefix="iv_a", n=2)}
        with pytest.raises(ValueError, match="must be one of"):
            opb_mod.tag_batch_decisions(groups, {"a": "maybe"})

    def test_decisions_non_dict_raises(self):
        groups = {"a": _seed_stable(prefix="nd_a", n=2)}
        with pytest.raises(ValueError, match="decisions"):
            opb_mod.tag_batch_decisions(groups, "nope")

    def test_missing_decision_for_group_raises(self):
        groups = {
            "a": _seed_stable(prefix="md_a", n=2),
            "b": _seed_stable(prefix="md_b", n=2),
        }
        # decisions has only "a", not "b" — mismatched keys.
        with pytest.raises(ValueError, match="exactly the same group names"):
            opb_mod.tag_batch_decisions(groups, {"a": "allow"})

    def test_extra_decision_key_raises(self):
        groups = {"a": _seed_stable(prefix="ed_a", n=2)}
        with pytest.raises(ValueError, match="exactly the same group names"):
            opb_mod.tag_batch_decisions(
                groups, {"a": "allow", "b": "allow"},
            )

    def test_non_dict_groups_raises(self):
        with pytest.raises(ValueError, match="groups to be a dict"):
            opb_mod.tag_batch_decisions("nope", {})

    def test_empty_groups_and_decisions_no_error(self):
        out = opb_mod.tag_batch_decisions({}, {})
        assert out["applied"] is True
        assert out["tagged"] == {}


# ===========================================================================
# F. generate_batch_report — shape + content
# ===========================================================================
class TestBatchReportShape:
    def test_top_level_keys(self):
        groups = {
            "a": _seed_stable(prefix="brs_a", n=3),
            "b": _seed_stable(prefix="brs_b", n=3),
        }
        out = opb_mod.generate_batch_report(groups)
        assert set(out.keys()) == {
            "headline", "groups", "comparisons",
            "alerts", "pairs", "diffs",
        }

    def test_headline_non_empty(self):
        groups = {"a": _seed_stable(prefix="hl_a", n=3)}
        out = opb_mod.generate_batch_report(groups)
        assert isinstance(out["headline"], str)
        assert out["headline"].strip() != ""

    def test_alerts_is_dict_keyed_by_group(self):
        groups = {
            "a": _seed_stable(prefix="al_g_a", n=3),
            "b": _seed_stable(prefix="al_g_b", n=3),
        }
        out = opb_mod.generate_batch_report(groups)
        assert set(out["alerts"].keys()) == set(groups.keys())

    def test_pairs_is_dict_keyed_by_group(self):
        groups = {
            "a": _seed_stable(prefix="pr_g_a", n=3),
            "b": _seed_stable(prefix="pr_g_b", n=3),
        }
        out = opb_mod.generate_batch_report(groups)
        assert set(out["pairs"].keys()) == set(groups.keys())

    def test_diffs_keys_match_comparisons(self):
        groups = {
            "a": _seed_stable(prefix="df_a", n=2),
            "b": _seed_stable(prefix="df_b", n=2),
            "c": _seed_stable(prefix="df_c", n=2),
        }
        out = opb_mod.generate_batch_report(groups)
        assert set(out["diffs"].keys()) == set(out["comparisons"].keys())


# ===========================================================================
# G. generate_batch_report — delegation
# ===========================================================================
class TestBatchReportDelegation:
    def test_groups_match_unit_21(self):
        groups = {"a": _seed_stable(prefix="dl_g_a", n=3)}
        out = opb_mod.generate_batch_report(groups)
        batch = batch_mod.evaluate_batch(groups)
        assert out["groups"] == batch["groups"]

    def test_comparisons_match_unit_21(self):
        groups = {
            "a": _seed_stable(prefix="dl_c_a", n=3),
            "b": _seed_stable(prefix="dl_c_b", n=3),
        }
        out = opb_mod.generate_batch_report(groups)
        batch = batch_mod.evaluate_batch(groups)
        assert out["comparisons"] == batch["comparisons"]

    def test_alerts_match_unit_16(self):
        groups = {"a": _seed_stable(prefix="dl_a_a", n=3)}
        out = opb_mod.generate_batch_report(groups)
        expected = alert_mod.generate_alerts(groups["a"])["alerts"]
        assert out["alerts"]["a"] == expected

    def test_pairs_match_unit_17(self):
        groups = {"a": _seed_stable(prefix="dl_p_a", n=3)}
        out = opb_mod.generate_batch_report(groups)
        expected = pd_mod.pair_deep_all(groups["a"])
        assert out["pairs"]["a"] == expected

    def test_diffs_match_unit_14(self):
        groups = {
            "a": _seed_stable(prefix="dl_d_a", n=2),
            "b": _seed_stable(prefix="dl_d_b", n=2),
        }
        out = opb_mod.generate_batch_report(groups)
        expected = diff_mod.diff_intelligence(groups["a"], groups["b"])
        assert out["diffs"]["a_vs_b"] == expected


# ===========================================================================
# H. generate_batch_report — small / empty / legacy
# ===========================================================================
class TestBatchReportSmallN:
    def test_empty_groups_returns_well_formed(self):
        out = opb_mod.generate_batch_report({})
        assert set(out.keys()) == {
            "headline", "groups", "comparisons",
            "alerts", "pairs", "diffs",
        }
        assert out["groups"] == {}
        assert out["comparisons"] == {}
        assert out["diffs"] == {}

    def test_single_group_no_diffs(self):
        groups = {"only": _seed_stable(prefix="sgn", n=3)}
        out = opb_mod.generate_batch_report(groups)
        assert out["diffs"] == {}

    def test_one_empty_group_evaluates(self):
        groups = {"empty": []}
        out = opb_mod.generate_batch_report(groups)
        assert out["groups"]["empty"]["decision"] == "warn"

    def test_legacy_run_does_not_crash(self, _runs_dir_isolation):
        rids = _seed_stable(prefix="leg_m", n=2)
        _write_legacy(_runs_dir_isolation, "leg_l", [_entry("p1")])
        groups = {"a": rids + ["leg_l"]}
        out = opb_mod.generate_batch_report(groups)
        assert isinstance(out, dict)


# ===========================================================================
# I. Validation across all three
# ===========================================================================
class TestValidation:
    def test_apply_non_dict_raises(self):
        with pytest.raises(ValueError, match="dict"):
            opb_mod.apply_batch_gate("nope")

    def test_apply_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="list"):
            opb_mod.apply_batch_gate({"a": "nope"})

    def test_apply_malformed_id_raises(self):
        with pytest.raises(ValueError):
            opb_mod.apply_batch_gate({"a": ["bad/id"]})

    def test_apply_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            opb_mod.apply_batch_gate({"a": ["ghost"]})

    def test_report_non_dict_raises(self):
        with pytest.raises(ValueError, match="dict"):
            opb_mod.generate_batch_report("nope")

    def test_report_malformed_id_raises(self):
        with pytest.raises(ValueError):
            opb_mod.generate_batch_report({"a": ["bad/id"]})

    def test_report_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            opb_mod.generate_batch_report({"a": ["ghost"]})

    def test_tag_decisions_malformed_id_raises(self):
        with pytest.raises(ValueError):
            opb_mod.tag_batch_decisions(
                {"a": ["bad/id"]}, {"a": "allow"},
            )

    def test_tag_decisions_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            opb_mod.tag_batch_decisions(
                {"a": ["ghost"]}, {"a": "allow"},
            )


# ===========================================================================
# J. Determinism
# ===========================================================================
class TestDeterminism:
    def test_apply_repeat_yields_same_decision(self):
        groups = {"a": _seed_stable(prefix="ar_a", n=3, sp=5)}
        a = opb_mod.apply_batch_gate(groups)
        b = opb_mod.apply_batch_gate(groups)
        assert a["groups"]["a"]["decision"] == \
               b["groups"]["a"]["decision"]

    def test_report_byte_equal(self):
        groups = {
            "a": _seed_stable(prefix="rb_a", n=3),
            "b": _seed_stable(prefix="rb_b", n=3),
        }
        a = opb_mod.generate_batch_report(groups)
        b = opb_mod.generate_batch_report(groups)
        assert a == b


# ===========================================================================
# K. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            opb_mod.apply_batch_gate,
            opb_mod.tag_batch_decisions,
            opb_mod.generate_batch_report,
        ):
            assert callable(fn)

    def test_tag_vocabulary_locked(self):
        assert opb_mod.TAG_BATCH_BLOCKED == "batch_blocked"
        assert opb_mod.TAG_BATCH_WARN    == "batch_warn"
        assert opb_mod.TAG_BATCH_ALLOWED == "batch_allowed"

    def test_decision_tag_map_complete(self):
        for d in ("allow", "warn", "block"):
            assert d in opb_mod._DECISION_TAG_MAP


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(opb_mod)

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

    def test_composes_units_9_14_16_17_21(self):
        src = self._code_only()
        for required in (
            "intelligence_for_run_ids",   # Unit 9
            "diff_intelligence",          # Unit 14
            "generate_alerts",            # Unit 16
            "pair_deep_all",              # Unit 17
            "evaluate_batch",             # Unit 21
        ):
            assert required in src
