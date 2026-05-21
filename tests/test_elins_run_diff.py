"""
Tests for ELINS Unit 11 — run-to-run diff engine + wrapper + endpoint.

Layered coverage (≥ 60 tests):
    A. compare_runs core — added/removed/changed/unchanged + summary
    B. Change-field detection (per-field sensitivity)
    C. Backward compatibility — legacy runs without pair_id
    D. diff_runs wrapper — load + diff + error propagation
    E. Endpoint — 200 / 400 / 401 / 404 paths
    F. Determinism + ordering
    G. Purity
    H. pair_id presence in dashboard outputs (Unit 11 schema additions)
    I. End-to-end: store → store → diff
"""
from __future__ import annotations

import inspect
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_run_diff as diff_mod
import elins_timeline_dashboard as etd
from elins_regression_economic_coercion import (
    TimelineEconomic, TimePointEconomic,
)
from elins_regression_single_party import Timeline, TimePoint


# ===========================================================================
# Fixtures — runs-dir isolation
# ===========================================================================
@pytest.fixture(autouse=True)
def _runs_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runs_dir = tmp_path / "elins_runs"
    monkeypatch.setenv(ep._RUNS_DIR_ENV_VAR, str(runs_dir))
    yield runs_dir


# ===========================================================================
# Payload builders — concise dict shapes matching Unit 5/8 dashboard output
# ===========================================================================
def _entry(
    pair_id: str = "case01::ec01",
    *,
    sp_score: int = 9,
    ec_score: int = 7,
    sp_band: str = "Strong",
    ec_band: str = "Acceptable",
    score_delta: int = -2,
    band_delta: str = "down",
    extra_assertions_failed=None,
) -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp_score,
        "economic_coercion_score": ec_score,
        "score_delta": score_delta,
        "score_delta_label": f"single party fear +{abs(score_delta)} points",
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
        "band_delta": band_delta,
        "band_delta_label": "stub",
        "assertions_failed_single_party": extra_assertions_failed or [],
        "assertions_failed_economic": [],
        "scenario_results_single_party": {},
        "scenario_results_economic": {},
    }


def _legacy_entry(**kwargs) -> dict:
    """An entry without pair_id (pre-Unit-11 stored shape)."""
    e = _entry(**kwargs)
    del e["pair_id"]
    return e


# ===========================================================================
# Timeline helpers + endpoint fixtures
# ===========================================================================
def _sp_tp(*, t="t0", **overrides) -> TimePoint:
    base = dict(
        t=t, regime_competition=0.5, autocratization=0.5,
        repression_index=0.5, digital_repression=0.5,
        perceived_threat=0.5, fear_signal=0.5,
        dissent_capacity=0.5, normative_constraint=0.5,
        support_buffer=0.5, trigger_event=None,
    )
    base.update(overrides)
    return TimePoint(**base)


def _ec_tp(*, t="t0", **overrides) -> TimePointEconomic:
    base = dict(
        t=t, economic_pressure=0.5, material_insecurity=0.5,
        state_coercion=0.5, compliance_signal=0.5,
        resistance_capacity=0.5, support_buffer=0.5, trigger_event=None,
    )
    base.update(overrides)
    return TimePointEconomic(**base)


def _sp_tl(tid="sp_test") -> Timeline:
    return Timeline(timeline_id=tid, points=(_sp_tp(),))


def _ec_tl(tid="ec_test") -> TimelineEconomic:
    return TimelineEconomic(timeline_id=tid, points=(_ec_tp(),))


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _make_user_session(app_module, username="alice"):
    import bcrypt
    import sessions_store
    import users_store

    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ===========================================================================
# A. compare_runs core
# ===========================================================================
class TestCoreDiffLogic:
    def test_two_empty_runs_yield_zero_diff(self):
        r = diff_mod.compare_runs([], [])
        assert r == {
            "added": [], "removed": [], "changed": [], "unchanged": [],
            "summary": {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
        }

    def test_added_only(self):
        r = diff_mod.compare_runs([], [_entry("p::a")])
        assert r["added"] == ["p::a"]
        assert r["removed"] == []
        assert r["changed"] == []
        assert r["unchanged"] == []
        assert r["summary"]["added"] == 1

    def test_removed_only(self):
        r = diff_mod.compare_runs([_entry("p::a")], [])
        assert r["removed"] == ["p::a"]
        assert r["added"] == []
        assert r["summary"]["removed"] == 1

    def test_unchanged_only(self):
        e = _entry("p::a")
        r = diff_mod.compare_runs([e], [e])
        assert r["unchanged"] == ["p::a"]
        assert r["changed"] == []
        assert r["added"] == []
        assert r["removed"] == []

    def test_changed_only_score(self):
        a = _entry("p::a", sp_score=9)
        b = _entry("p::a", sp_score=8)
        r = diff_mod.compare_runs([a], [b])
        assert len(r["changed"]) == 1
        assert r["changed"][0]["pair_id"] == "p::a"
        assert r["changed"][0]["single_party_score_a"] == 9
        assert r["changed"][0]["single_party_score_b"] == 8
        assert r["unchanged"] == []

    def test_changed_band(self):
        a = _entry("p::a", sp_band="Strong")
        b = _entry("p::a", sp_band="Acceptable")
        r = diff_mod.compare_runs([a], [b])
        assert r["changed"][0]["single_party_band_a"] == "Strong"
        assert r["changed"][0]["single_party_band_b"] == "Acceptable"

    def test_mixed_added_removed_changed_unchanged(self):
        a = [
            _entry("p::a"),                 # unchanged
            _entry("p::b", sp_score=9),     # changed
            _entry("p::c"),                 # removed
        ]
        b = [
            _entry("p::a"),                 # unchanged (same)
            _entry("p::b", sp_score=8),     # changed (score diff)
            _entry("p::d"),                 # added
        ]
        r = diff_mod.compare_runs(a, b)
        assert r["added"] == ["p::d"]
        assert r["removed"] == ["p::c"]
        assert r["unchanged"] == ["p::a"]
        assert len(r["changed"]) == 1
        assert r["changed"][0]["pair_id"] == "p::b"

    def test_summary_counts(self):
        r = diff_mod.compare_runs(
            [_entry("a"), _entry("b", sp_score=9), _entry("c")],
            [_entry("a"), _entry("b", sp_score=8), _entry("d")],
        )
        assert r["summary"] == {
            "added": 1, "removed": 1, "changed": 1, "unchanged": 1,
        }

    def test_added_sorted_alphabetically(self):
        r = diff_mod.compare_runs(
            [],
            [_entry("zzz"), _entry("aaa"), _entry("mmm")],
        )
        assert r["added"] == ["aaa", "mmm", "zzz"]

    def test_removed_sorted_alphabetically(self):
        r = diff_mod.compare_runs(
            [_entry("zzz"), _entry("aaa"), _entry("mmm")],
            [],
        )
        assert r["removed"] == ["aaa", "mmm", "zzz"]

    def test_unchanged_sorted_alphabetically(self):
        e_z = _entry("zzz")
        e_a = _entry("aaa")
        e_m = _entry("mmm")
        r = diff_mod.compare_runs([e_z, e_a, e_m], [e_z, e_a, e_m])
        assert r["unchanged"] == ["aaa", "mmm", "zzz"]

    def test_changed_sorted_alphabetically_by_pair_id(self):
        r = diff_mod.compare_runs(
            [_entry("zz", sp_score=9), _entry("aa", sp_score=9), _entry("mm", sp_score=9)],
            [_entry("zz", sp_score=8), _entry("aa", sp_score=8), _entry("mm", sp_score=8)],
        )
        assert [c["pair_id"] for c in r["changed"]] == ["aa", "mm", "zz"]

    def test_order_invariance_added(self):
        """Order of input list shouldn't affect diff output."""
        r1 = diff_mod.compare_runs([], [_entry("a"), _entry("b")])
        r2 = diff_mod.compare_runs([], [_entry("b"), _entry("a")])
        assert r1 == r2

    def test_byte_equal_repeated_calls(self):
        a = [_entry("p::a"), _entry("p::b", sp_score=9)]
        b = [_entry("p::a"), _entry("p::b", sp_score=8), _entry("p::c")]
        r1 = diff_mod.compare_runs(a, b)
        r2 = diff_mod.compare_runs(a, b)
        assert r1 == r2

    def test_changed_entry_carries_all_six_field_pairs(self):
        a = _entry("p::a", sp_score=9, ec_score=7, sp_band="Strong",
                   ec_band="Acceptable", score_delta=-2, band_delta="down")
        b = _entry("p::a", sp_score=8, ec_score=6, sp_band="Acceptable",
                   ec_band="Weak", score_delta=-2, band_delta="down")
        r = diff_mod.compare_runs([a], [b])
        c = r["changed"][0]
        for fname in diff_mod._CHANGE_FIELDS:
            assert f"{fname}_a" in c
            assert f"{fname}_b" in c

    def test_inputs_not_mutated(self):
        a = [_entry("p::a")]
        b = [_entry("p::b")]
        before_a = repr(a)
        before_b = repr(b)
        diff_mod.compare_runs(a, b)
        assert repr(a) == before_a
        assert repr(b) == before_b


# ===========================================================================
# B. Per-field change detection
# ===========================================================================
class TestPerFieldChangeDetection:
    @pytest.mark.parametrize("fname", list(diff_mod._CHANGE_FIELDS))
    def test_each_change_field_triggers_changed(self, fname):
        a = _entry("p::a")
        b = _entry("p::a")
        # Mutate exactly one field to trigger.
        if fname == "single_party_score":
            b[fname] = a[fname] + 1
        elif fname == "economic_coercion_score":
            b[fname] = a[fname] + 1
        elif fname == "score_delta":
            b[fname] = a[fname] + 5
        elif fname == "single_party_band":
            b[fname] = "Different"
        elif fname == "economic_coercion_band":
            b[fname] = "Different"
        elif fname == "band_delta":
            b[fname] = "up"
        r = diff_mod.compare_runs([a], [b])
        assert len(r["changed"]) == 1
        assert r["unchanged"] == []

    def test_assertions_field_change_does_not_trigger(self):
        """assertions_failed_* are NOT in the change-detection set."""
        a = _entry("p::a", extra_assertions_failed=[])
        b = _entry("p::a", extra_assertions_failed=["assertion_x"])
        r = diff_mod.compare_runs([a], [b])
        assert r["unchanged"] == ["p::a"]
        assert r["changed"] == []

    def test_scenario_results_change_does_not_trigger(self):
        a = _entry("p::a")
        b = _entry("p::a")
        b["scenario_results_single_party"] = {"test_x": False}
        r = diff_mod.compare_runs([a], [b])
        assert r["unchanged"] == ["p::a"]

    def test_label_change_does_not_trigger(self):
        """score_delta_label / band_delta_label are presentation-only."""
        a = _entry("p::a")
        b = _entry("p::a")
        b["score_delta_label"] = "completely different label"
        b["band_delta_label"] = "also different"
        r = diff_mod.compare_runs([a], [b])
        assert r["unchanged"] == ["p::a"]


# ===========================================================================
# C. Backward compatibility — legacy entries without pair_id
# ===========================================================================
class TestBackwardCompatLegacyRuns:
    def test_legacy_entry_synthesises_pos_id(self):
        a = [_legacy_entry()]
        b = [_legacy_entry()]
        r = diff_mod.compare_runs(a, b)
        assert r["unchanged"] == ["pos_0"]

    def test_legacy_run_position_zero(self):
        a = [_legacy_entry()]
        r = diff_mod.compare_runs([], a)
        assert r["added"] == ["pos_0"]

    def test_legacy_multiple_entries_get_sequential_pos_ids(self):
        a = [_legacy_entry(), _legacy_entry(), _legacy_entry()]
        r = diff_mod.compare_runs([], a)
        assert r["added"] == ["pos_0", "pos_1", "pos_2"]

    def test_mixed_legacy_and_new_in_same_run(self):
        a = [_legacy_entry(), _entry("p::keep"), _legacy_entry()]
        r = diff_mod.compare_runs([], a)
        # pos_0 (legacy[0]), p::keep (new), pos_2 (legacy[2])
        assert sorted(r["added"]) == sorted(["pos_0", "p::keep", "pos_2"])

    def test_fresh_run_vs_legacy_run_treats_all_as_added_removed(self):
        """A fresh run with pair_id and a legacy run without share no
        ids → all of A is removed, all of B is added."""
        a = [_legacy_entry()]   # pos_0
        b = [_entry("p::brand_new")]
        r = diff_mod.compare_runs(a, b)
        assert r["removed"] == ["pos_0"]
        assert r["added"] == ["p::brand_new"]
        assert r["changed"] == []
        assert r["unchanged"] == []

    def test_legacy_with_changed_field_at_same_position(self):
        a = [_legacy_entry(sp_score=9)]
        b = [_legacy_entry(sp_score=8)]
        r = diff_mod.compare_runs(a, b)
        # Both synthesise to pos_0 → changed
        assert len(r["changed"]) == 1
        assert r["changed"][0]["pair_id"] == "pos_0"

    def test_empty_string_pair_id_falls_back_to_pos(self):
        a = _entry("")  # invalid pair_id
        r = diff_mod.compare_runs([], [a])
        assert r["added"] == ["pos_0"]

    def test_non_string_pair_id_falls_back_to_pos(self):
        a = _entry()
        a["pair_id"] = 42  # type: ignore[assignment]
        r = diff_mod.compare_runs([], [a])
        assert r["added"] == ["pos_0"]


# ===========================================================================
# D. compare_runs validation
# ===========================================================================
class TestCompareRunsValidation:
    def test_run_a_not_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            diff_mod.compare_runs("nope", [])  # type: ignore[arg-type]

    def test_run_b_not_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            diff_mod.compare_runs([], 42)  # type: ignore[arg-type]

    def test_entry_not_dict_raises(self):
        with pytest.raises(ValueError, match="not a dict"):
            diff_mod.compare_runs(["bad"], [])  # type: ignore[list-item]

    def test_entry_in_b_not_dict_raises(self):
        with pytest.raises(ValueError, match="not a dict"):
            diff_mod.compare_runs([], [None])  # type: ignore[list-item]


# ===========================================================================
# E. diff_runs wrapper
# ===========================================================================
class TestDiffRunsWrapper:
    def test_load_and_diff_byte_equal(self):
        ep.save_comparison_result("run_a", [_entry("p::a")])
        ep.save_comparison_result("run_b", [_entry("p::a"), _entry("p::b")])
        r = diff_mod.diff_runs("run_a", "run_b")
        assert r["added"] == ["p::b"]
        assert r["unchanged"] == ["p::a"]

    def test_propagation_matches_direct_compare(self):
        a_payload = [_entry("p::a"), _entry("p::b", sp_score=9)]
        b_payload = [_entry("p::a"), _entry("p::b", sp_score=8)]
        ep.save_comparison_result("wrap_a", a_payload)
        ep.save_comparison_result("wrap_b", b_payload)
        wrapped = diff_mod.diff_runs("wrap_a", "wrap_b")
        direct = diff_mod.compare_runs(a_payload, b_payload)
        assert wrapped == direct

    def test_missing_run_a_raises_filenotfound(self):
        ep.save_comparison_result("only_b", [])
        with pytest.raises(FileNotFoundError):
            diff_mod.diff_runs("missing", "only_b")

    def test_missing_run_b_raises_filenotfound(self):
        ep.save_comparison_result("only_a", [])
        with pytest.raises(FileNotFoundError):
            diff_mod.diff_runs("only_a", "missing")

    def test_malformed_run_id_a_raises_value_error(self):
        with pytest.raises(ValueError):
            diff_mod.diff_runs("bad/id", "anything")

    def test_malformed_run_id_b_raises_value_error(self):
        ep.save_comparison_result("good_a", [])
        with pytest.raises(ValueError):
            diff_mod.diff_runs("good_a", "bad/id")

    def test_empty_run_id_raises(self):
        with pytest.raises(ValueError):
            diff_mod.diff_runs("", "any")

    def test_two_empty_runs_via_wrapper(self):
        ep.save_comparison_result("e1", [])
        ep.save_comparison_result("e2", [])
        r = diff_mod.diff_runs("e1", "e2")
        assert r["summary"] == {
            "added": 0, "removed": 0, "changed": 0, "unchanged": 0,
        }


# ===========================================================================
# F. Endpoint behavior
# ===========================================================================
class TestEndpoint:
    def test_valid_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("e_a", [_entry("p::a")])
        ep.save_comparison_result("e_b", [_entry("p::a")])
        resp = client.get(
            "/elins/regression/diff?run_a=e_a&run_b=e_b",
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_shape(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a1", [_entry("p::a")])
        ep.save_comparison_result("b1", [_entry("p::a"), _entry("p::b")])
        resp = client.get(
            "/elins/regression/diff?run_a=a1&run_b=b1",
            headers=_auth(sid),
        )
        body = resp.json()
        for key in ("added", "removed", "changed", "unchanged", "summary"):
            assert key in body
        for sk in ("added", "removed", "changed", "unchanged"):
            assert sk in body["summary"]

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("present", [])
        resp = client.get(
            "/elins/regression/diff?run_a=present&run_b=ghost",
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_both_missing_runs_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            "/elins/regression/diff?run_a=ghost1&run_b=ghost2",
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_malformed_run_a_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            "/elins/regression/diff?run_a=bad$id&run_b=anything",
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_run_b_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("good", [])
        resp = client.get(
            "/elins/regression/diff?run_a=good&run_b=bad$id",
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_unauth_returns_401(self, client, app_module):
        resp = client.get("/elins/regression/diff?run_a=a&run_b=b")
        assert resp.status_code == 401

    def test_response_matches_direct_call(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("dr_a", [_entry("p::x", sp_score=9)])
        ep.save_comparison_result("dr_b", [_entry("p::x", sp_score=8)])
        direct = diff_mod.diff_runs("dr_a", "dr_b")
        resp = client.get(
            "/elins/regression/diff?run_a=dr_a&run_b=dr_b",
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("rep_a", [_entry("p::x")])
        ep.save_comparison_result("rep_b", [_entry("p::y")])
        r1 = client.get("/elins/regression/diff?run_a=rep_a&run_b=rep_b",
                        headers=_auth(sid))
        r2 = client.get("/elins/regression/diff?run_a=rep_a&run_b=rep_b",
                        headers=_auth(sid))
        assert r1.json() == r2.json()

    def test_missing_query_param_400_or_422(self, client, app_module):
        """FastAPI's required-query enforcement returns 422 by default
        for missing query params; either 422 or 400 acceptable."""
        sid = _make_user_session(app_module)
        resp = client.get("/elins/regression/diff?run_a=x", headers=_auth(sid))
        assert resp.status_code in (400, 422)


# ===========================================================================
# G. Determinism + ordering
# ===========================================================================
class TestDeterminism:
    def test_diff_byte_equal_repeated(self):
        a = [_entry("p::a"), _entry("p::b", sp_score=9)]
        b = [_entry("p::c"), _entry("p::a"), _entry("p::b", sp_score=8)]
        assert diff_mod.compare_runs(a, b) == diff_mod.compare_runs(a, b)

    def test_diff_runs_byte_equal_repeated(self):
        ep.save_comparison_result("d1", [_entry("p::a"), _entry("p::b")])
        ep.save_comparison_result("d2", [_entry("p::a")])
        assert diff_mod.diff_runs("d1", "d2") == diff_mod.diff_runs("d1", "d2")

    def test_added_list_is_sorted_strings(self):
        r = diff_mod.compare_runs([], [_entry(f"p::{c}") for c in "fdeacb"])
        assert r["added"] == sorted(r["added"])

    def test_changed_pair_id_field_is_alphabetical(self):
        a = [_entry(f"p::{c}", sp_score=9) for c in "fdeacb"]
        b = [_entry(f"p::{c}", sp_score=8) for c in "fdeacb"]
        r = diff_mod.compare_runs(a, b)
        ids = [c["pair_id"] for c in r["changed"]]
        assert ids == sorted(ids)


# ===========================================================================
# H. Purity / source-code invariants
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(diff_mod)

    def test_no_llm_imports(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_imports(self):
        src = self._src()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket",
                          "from urllib", "from http", "from requests"):
            assert forbidden not in src

    def test_no_logging(self):
        src = self._src()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._src()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src

    def test_no_subprocess_or_eval(self):
        src = self._src()
        for forbidden in ("subprocess", "exec(", "eval("):
            assert forbidden not in src

    def test_compare_runs_pure_no_open(self):
        """compare_runs has no file I/O — only diff_runs does (via
        the persistence layer)."""
        src = inspect.getsource(diff_mod.compare_runs)
        assert "open(" not in src

    def test_no_basin_inference_imports(self):
        src = self._src()
        for pattern in (
            "import elins_dashboard", "from elins_dashboard",
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
        ):
            assert pattern not in src


# ===========================================================================
# I. pair_id schema additions in dashboard outputs (Unit 11 schema)
# ===========================================================================
class TestPairIdInDashboardOutput:
    def test_single_pair_dashboard_includes_pair_id(self):
        out = etd.compare_regressions_dashboard(_sp_tl("alpha"), _ec_tl("beta"))
        assert out["pair_id"] == "alpha::beta"

    def test_batch_dashboard_includes_pair_id_per_element(self):
        pairs = [
            (_sp_tl("a1"), _ec_tl("b1")),
            (_sp_tl("a2"), _ec_tl("b2")),
        ]
        out = etd.compare_regressions_batch_dashboard(pairs)
        assert [e["pair_id"] for e in out] == ["a1::b1", "a2::b2"]

    def test_pair_id_is_composite_with_double_colon(self):
        out = etd.compare_regressions_dashboard(
            _sp_tl("foo"), _ec_tl("bar"))
        assert "::" in out["pair_id"]
        sp_part, ec_part = out["pair_id"].split("::")
        assert sp_part == "foo"
        assert ec_part == "bar"

    def test_pair_id_stable_across_calls(self):
        sp = _sp_tl("stable_sp")
        ec = _ec_tl("stable_ec")
        a = etd.compare_regressions_dashboard(sp, ec)
        b = etd.compare_regressions_dashboard(sp, ec)
        assert a["pair_id"] == b["pair_id"]


# ===========================================================================
# J. End-to-end: store via endpoint, store again, diff via endpoint
# ===========================================================================
class TestEndToEnd:
    def test_full_round_trip_via_endpoints(self, client, app_module):
        sid = _make_user_session(app_module)

        # Build a single-pair payload for the store endpoint.
        sp_payload = {
            "timeline_id": "case01_sp",
            "points": [
                {"t": "t0",
                 "regime_competition": 0.5, "autocratization": 0.5,
                 "repression_index": 0.5, "digital_repression": 0.5,
                 "perceived_threat": 0.5, "fear_signal": 0.5,
                 "dissent_capacity": 0.5, "normative_constraint": 0.5,
                 "support_buffer": 0.5},
            ],
        }
        ec_payload = {
            "timeline_id": "case01_ec",
            "points": [
                {"t": "t0",
                 "economic_pressure": 0.5, "material_insecurity": 0.5,
                 "state_coercion": 0.5, "compliance_signal": 0.5,
                 "resistance_capacity": 0.5, "support_buffer": 0.5},
            ],
        }
        store_body = {"pairs": [{
            "single_party_timeline": sp_payload,
            "economic_timeline":     ec_payload,
        }]}

        # Two stores under different ids.
        r1 = client.post("/elins/regression/store",
                         json={"run_id": "morning", **store_body},
                         headers=_auth(sid))
        r2 = client.post("/elins/regression/store",
                         json={"run_id": "evening", **store_body},
                         headers=_auth(sid))
        assert r1.status_code == 200 and r2.status_code == 200

        # Diff the two runs via endpoint.
        d = client.get(
            "/elins/regression/diff?run_a=morning&run_b=evening",
            headers=_auth(sid),
        )
        assert d.status_code == 200
        body = d.json()
        # Same pair_id in both → unchanged.
        assert body["unchanged"] == ["case01_sp::case01_ec"]
        assert body["added"] == []
        assert body["removed"] == []
        assert body["changed"] == []


# ===========================================================================
# K. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_compare_runs_callable(self):
        assert callable(diff_mod.compare_runs)

    def test_diff_runs_callable(self):
        assert callable(diff_mod.diff_runs)

    def test_change_fields_locked(self):
        assert diff_mod._CHANGE_FIELDS == (
            "single_party_score",
            "economic_coercion_score",
            "single_party_band",
            "economic_coercion_band",
            "score_delta",
            "band_delta",
        )
