"""
Tests for ELINS2 Unit 12 — operator intelligence actions
(helper module + HTTP endpoints).

Layered coverage (>= 50 tests, target ~65):
    A. flag_anomalous_runs — helper
    B. pin_best_sequence — helper
    C. tag_cluster_runs — helper
    D. Dedup + tag preservation invariants
    E. POST /flag-anomalies endpoint
    F. POST /pin-best-sequence endpoint
    G. POST /tag-cluster endpoint
    H. Validation (400) across endpoints
    I. Missing runs (404)
    J. Auth (401)
    K. Backward compat — existing operator endpoints unchanged
    L. Determinism / source-code purity
"""
from __future__ import annotations

import inspect
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_operator_intel as op_mod
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


def _entry(pid="p1", *, sp=5, ec=5,
           sp_band="Acceptable", ec_band="Acceptable") -> dict:
    return {
        "pair_id": pid,
        "single_party_score": sp,
        "economic_coercion_score": ec,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _seed_stable(prefix="s", n=5, sp=5, ec=5):
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec),
                                          _entry("p2", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


def _seed_outlier_set(prefix="o", n_stable=5):
    """Stable universe + a clear singleton outlier — outlier reliably
    fires at medium/high anomaly level."""
    stable = _seed_stable(prefix=prefix, n=n_stable, sp=5)
    out_rid = f"{prefix}_outlier"
    ep.save_comparison_result(
        out_rid,
        [_entry("p9", sp=0, ec=0,
                 sp_band="Fails core logic",
                 ec_band="Fails core logic")],
    )
    return stable + [out_rid]


# ===========================================================================
# A. flag_anomalous_runs — helper
# ===========================================================================
class TestFlagAnomalousHelper:
    def test_clean_universe_no_flagged(self):
        rids = _seed_stable(n=5, sp=5)
        out = op_mod.flag_anomalous_runs(rids)
        assert out["flagged"] == []
        # All runs end up in skipped because anomaly level is "none".
        assert set(out["skipped"]) == set(rids)

    def test_outlier_flagged(self):
        rids = _seed_outlier_set(prefix="of")
        out = op_mod.flag_anomalous_runs(rids)
        assert "of_outlier" in out["flagged"]

    def test_flagged_tag_present_after_call(self):
        rids = _seed_outlier_set(prefix="fp")
        op_mod.flag_anomalous_runs(rids)
        # Outlier carries the anomaly tag.
        assert "anomaly" in ep_sql.get_tags("fp_outlier")

    def test_flagged_excludes_stable_runs(self):
        rids = _seed_outlier_set(prefix="ex")
        out = op_mod.flag_anomalous_runs(rids)
        for rid in rids[:5]:
            assert "anomaly" not in ep_sql.get_tags(rid)
            assert rid in out["skipped"]

    def test_response_shape(self):
        rids = _seed_stable(n=2, sp=5)
        out = op_mod.flag_anomalous_runs(rids)
        assert set(out.keys()) == {"flagged", "skipped"}
        assert isinstance(out["flagged"], list)
        assert isinstance(out["skipped"], list)

    def test_empty_run_ids_well_formed(self):
        out = op_mod.flag_anomalous_runs([])
        assert out == {"flagged": [], "skipped": []}

    def test_already_tagged_run_appears_in_skipped(self):
        rids = _seed_outlier_set(prefix="dup")
        # Pre-tag the outlier — first flag call should now skip it.
        ep_sql.set_tags("dup_outlier", ["anomaly"])
        out = op_mod.flag_anomalous_runs(rids)
        assert "dup_outlier" not in out["flagged"]
        assert "dup_outlier" in out["skipped"]
        # The tag is preserved (not duplicated).
        assert ep_sql.get_tags("dup_outlier") == ["anomaly"]


# ===========================================================================
# B. pin_best_sequence — helper
# ===========================================================================
class TestPinBestSequenceHelper:
    def test_pinned_subset_of_input(self):
        rids = _seed_stable(prefix="pb", n=5, sp=5)
        out = op_mod.pin_best_sequence(rids, window=3)
        assert isinstance(out["pinned"], list)
        for rid in out["pinned"]:
            assert rid in rids

    def test_pinned_size_matches_window(self):
        rids = _seed_stable(prefix="pw", n=5, sp=5)
        out = op_mod.pin_best_sequence(rids, window=3)
        # Window=3 means up to 3 runs get the tag in this call.
        assert len(out["pinned"]) <= 3

    def test_pinned_runs_carry_tag(self):
        rids = _seed_stable(prefix="pt", n=5, sp=5)
        out = op_mod.pin_best_sequence(rids, window=3)
        for rid in out["pinned"]:
            assert "pinned_sequence" in ep_sql.get_tags(rid)

    def test_input_smaller_than_window_returns_empty(self):
        rids = _seed_stable(prefix="sm", n=3, sp=5)
        out = op_mod.pin_best_sequence(rids, window=5)
        assert out["pinned"] == []

    def test_empty_input_returns_empty(self):
        out = op_mod.pin_best_sequence([], window=3)
        assert out == {"pinned": []}

    def test_existing_pin_tag_preserved(self):
        rids = _seed_stable(prefix="ep", n=5, sp=5)
        # Pre-pin one of the runs that will be in the best window.
        ep_sql.set_tags(rids[0], ["pinned_sequence", "other_tag"])
        op_mod.pin_best_sequence(rids, window=3)
        tags = ep_sql.get_tags(rids[0])
        assert tags.count("pinned_sequence") == 1
        assert "other_tag" in tags


# ===========================================================================
# C. tag_cluster_runs — helper
# ===========================================================================
class TestTagClusterHelper:
    def test_tag_applied_to_all_members(self):
        rids = _seed_stable(prefix="tc", n=3, sp=5)
        op_mod.tag_cluster_runs(
            "c0",
            {"members": rids, "label": "stable", "size": 3},
            "regression_cluster",
        )
        for rid in rids:
            assert "regression_cluster" in ep_sql.get_tags(rid)

    def test_response_shape(self):
        rids = _seed_stable(prefix="tr", n=2, sp=5)
        out = op_mod.tag_cluster_runs(
            "c0",
            {"members": rids, "label": "stable"},
            "my_tag",
        )
        assert set(out.keys()) == {
            "cluster_id", "tag", "run_ids", "applied",
        }
        assert out["cluster_id"] == "c0"
        assert out["tag"] == "my_tag"
        assert sorted(out["run_ids"]) == sorted(rids)

    def test_existing_tags_preserved(self):
        rids = _seed_stable(prefix="ep_c", n=2, sp=5)
        ep_sql.set_tags(rids[0], ["existing_tag"])
        op_mod.tag_cluster_runs(
            "c0", {"members": rids, "label": "stable"}, "new_tag",
        )
        tags = ep_sql.get_tags(rids[0])
        assert "existing_tag" in tags
        assert "new_tag" in tags

    def test_no_duplicate_on_repeat_call(self):
        rids = _seed_stable(prefix="rep", n=2, sp=5)
        op_mod.tag_cluster_runs(
            "c0", {"members": rids, "label": "stable"}, "my_tag",
        )
        op_mod.tag_cluster_runs(
            "c0", {"members": rids, "label": "stable"}, "my_tag",
        )
        for rid in rids:
            assert ep_sql.get_tags(rid).count("my_tag") == 1

    def test_applied_reports_only_first_mutation(self):
        rids = _seed_stable(prefix="ap", n=2, sp=5)
        first = op_mod.tag_cluster_runs(
            "c0", {"members": rids, "label": "stable"}, "t",
        )
        second = op_mod.tag_cluster_runs(
            "c0", {"members": rids, "label": "stable"}, "t",
        )
        assert sorted(first["applied"]) == sorted(rids)
        assert second["applied"] == []  # second call is a no-op


# ===========================================================================
# D. Validation invariants — helpers
# ===========================================================================
class TestHelperValidation:
    def test_flag_anomalous_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            op_mod.flag_anomalous_runs("nope")

    def test_flag_anomalous_malformed_id_raises(self):
        with pytest.raises(ValueError):
            op_mod.flag_anomalous_runs(["bad/id"])

    def test_flag_anomalous_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            op_mod.flag_anomalous_runs(["ghost"])

    def test_pin_best_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            op_mod.pin_best_sequence("nope")

    def test_pin_best_missing_run_raises(self):
        # All-missing run_ids — pin_best_sequence short-circuits to
        # {"pinned": []} when len < window. Use a window that fits.
        with pytest.raises(FileNotFoundError):
            op_mod.pin_best_sequence(["g1", "g2"], window=2)

    def test_tag_cluster_empty_id_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            op_mod.tag_cluster_runs("", {"members": []}, "tag")

    def test_tag_cluster_non_string_id_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            op_mod.tag_cluster_runs(123, {"members": []}, "tag")

    def test_tag_cluster_non_dict_info_raises(self):
        with pytest.raises(ValueError, match="dict"):
            op_mod.tag_cluster_runs("c0", "nope", "tag")

    def test_tag_cluster_empty_tag_raises(self):
        with pytest.raises(ValueError, match="non-empty"):
            op_mod.tag_cluster_runs("c0", {"members": []}, "")

    def test_tag_cluster_members_non_list_raises(self):
        with pytest.raises(ValueError, match="list"):
            op_mod.tag_cluster_runs("c0", {"members": "x"}, "tag")


# ===========================================================================
# E. POST /flag-anomalies endpoint
# ===========================================================================
class TestFlagAnomaliesEndpoint:
    PATH = "/elins/regression/runs/intelligence/flag-anomalies"

    def test_happy_path_200(self, app_module, client):
        rids = _seed_outlier_set(prefix="fa_h")
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH, json={"run_ids": rids}, headers=_auth(sid),
        )
        assert r.status_code == 200

    def test_response_shape(self, app_module, client):
        rids = _seed_outlier_set(prefix="fa_s")
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH, json={"run_ids": rids}, headers=_auth(sid),
        )
        body = r.json()
        assert set(body.keys()) == {"flagged", "skipped"}

    def test_outlier_in_flagged(self, app_module, client):
        rids = _seed_outlier_set(prefix="fa_o")
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH, json={"run_ids": rids}, headers=_auth(sid),
        )
        assert "fa_o_outlier" in r.json()["flagged"]

    def test_empty_run_ids_well_formed(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH, json={"run_ids": []}, headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json() == {"flagged": [], "skipped": []}

    def test_missing_run_ids_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(self.PATH, json={}, headers=_auth(sid))
        assert r.status_code == 400

    def test_run_ids_not_list_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH, json={"run_ids": "nope"}, headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_malformed_id_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH, json={"run_ids": ["bad/id"]}, headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_missing_run_404(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH, json={"run_ids": ["ghost"]}, headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_missing_session_401(self, client):
        r = client.post(self.PATH, json={"run_ids": []})
        assert r.status_code == 401


# ===========================================================================
# F. POST /pin-best-sequence endpoint
# ===========================================================================
class TestPinBestSequenceEndpoint:
    PATH = "/elins/regression/runs/intelligence/pin-best-sequence"

    def test_happy_path_200(self, app_module, client):
        rids = _seed_stable(prefix="ps_h", n=5, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"run_ids": rids, "window": 3},
            headers=_auth(sid),
        )
        assert r.status_code == 200

    def test_response_shape(self, app_module, client):
        rids = _seed_stable(prefix="ps_s", n=5, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"run_ids": rids, "window": 3},
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body.keys()) == {"pinned"}

    def test_pinned_runs_tagged(self, app_module, client):
        rids = _seed_stable(prefix="ps_t", n=5, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"run_ids": rids, "window": 3},
            headers=_auth(sid),
        )
        for rid in r.json()["pinned"]:
            assert "pinned_sequence" in ep_sql.get_tags(rid)

    def test_default_window_used_when_omitted(self, app_module, client):
        rids = _seed_stable(prefix="ps_d", n=5, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"run_ids": rids},  # no window key → defaults to 5
            headers=_auth(sid),
        )
        assert r.status_code == 200
        # 5 runs, window 5 → pinned all 5.
        assert len(r.json()["pinned"]) == 5

    def test_window_below_min_400(self, app_module, client):
        rids = _seed_stable(prefix="ps_l", n=3, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"run_ids": rids, "window": 1},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_window_non_int_400(self, app_module, client):
        rids = _seed_stable(prefix="ps_n", n=3, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"run_ids": rids, "window": "3"},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_smaller_than_window_returns_empty(self, app_module, client):
        rids = _seed_stable(prefix="ps_sm", n=3, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"run_ids": rids, "window": 5},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json() == {"pinned": []}

    def test_missing_run_404(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"run_ids": ["g1", "g2"], "window": 2},
            headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_missing_session_401(self, client):
        r = client.post(self.PATH, json={"run_ids": []})
        assert r.status_code == 401


# ===========================================================================
# G. POST /tag-cluster endpoint
# ===========================================================================
class TestTagClusterEndpoint:
    PATH = "/elins/regression/runs/intelligence/tag-cluster"

    def test_happy_path_200(self, app_module, client):
        rids = _seed_stable(prefix="tc_h", n=3, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={
                "cluster_id": "c0",
                "tag":        "regression_cluster",
                "run_ids":    rids,
            },
            headers=_auth(sid),
        )
        assert r.status_code == 200

    def test_response_shape(self, app_module, client):
        rids = _seed_stable(prefix="tc_s", n=2, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={
                "cluster_id": "c0",
                "tag":        "my_tag",
                "run_ids":    rids,
            },
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body.keys()) == {
            "cluster_id", "tag", "run_ids", "applied",
        }

    def test_tag_applied_to_all_members(self, app_module, client):
        rids = _seed_stable(prefix="tc_a", n=3, sp=5)
        sid = _make_user_session(app_module)
        client.post(
            self.PATH,
            json={
                "cluster_id": "c0",
                "tag":        "regression_cluster",
                "run_ids":    rids,
            },
            headers=_auth(sid),
        )
        for rid in rids:
            assert "regression_cluster" in ep_sql.get_tags(rid)

    def test_missing_cluster_id_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"tag": "t", "run_ids": []},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_empty_cluster_id_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"cluster_id": "", "tag": "t", "run_ids": []},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_missing_tag_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"cluster_id": "c0", "run_ids": []},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_empty_tag_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"cluster_id": "c0", "tag": "", "run_ids": []},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_run_ids_not_list_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={"cluster_id": "c0", "tag": "t", "run_ids": "x"},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_missing_run_404(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            self.PATH,
            json={
                "cluster_id": "c0",
                "tag":        "t",
                "run_ids":    ["ghost"],
            },
            headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_missing_session_401(self, client):
        r = client.post(
            self.PATH,
            json={"cluster_id": "c0", "tag": "t", "run_ids": []},
        )
        assert r.status_code == 401


# ===========================================================================
# K. Backward compat — existing operator endpoints unchanged
# ===========================================================================
class TestBackwardCompat:
    def test_runs_listing_endpoint_unchanged(self, app_module, client):
        _seed_stable(prefix="bc1", n=2, sp=5)
        sid = _make_user_session(app_module)
        r = client.get("/elins/regression/runs", headers=_auth(sid))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_intelligence_post_unchanged(self, app_module, client):
        rids = _seed_stable(prefix="bc2", n=2, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        assert "run_ids" in r.json()

    def test_dashboard_intelligence_unchanged(self, app_module, client):
        _seed_stable(prefix="bc3", n=3, sp=5)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        assert r.status_code == 200

    def test_runs_summary_endpoint_unchanged(self, app_module, client):
        rids = _seed_stable(prefix="bc4", n=2, sp=5)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/summary",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        assert r.status_code == 200


# ===========================================================================
# L. Determinism / source-code purity
# ===========================================================================
class TestDeterminism:
    def test_flag_anomalous_repeat_no_extra_tags(self):
        rids = _seed_outlier_set(prefix="dt_f")
        op_mod.flag_anomalous_runs(rids)
        op_mod.flag_anomalous_runs(rids)
        # Second call doesn't add a duplicate "anomaly" tag.
        assert ep_sql.get_tags("dt_f_outlier").count("anomaly") == 1

    def test_pin_best_repeat_no_extra_tags(self):
        rids = _seed_stable(prefix="dt_p", n=5, sp=5)
        op_mod.pin_best_sequence(rids, window=3)
        op_mod.pin_best_sequence(rids, window=3)
        for rid in rids:
            assert ep_sql.get_tags(rid).count("pinned_sequence") <= 1


class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            op_mod.flag_anomalous_runs,
            op_mod.pin_best_sequence,
            op_mod.tag_cluster_runs,
        ):
            assert callable(fn)

    def test_tag_constants_locked(self):
        assert op_mod.TAG_ANOMALY == "anomaly"
        assert op_mod.TAG_PINNED_SEQUENCE == "pinned_sequence"

    def test_flagged_levels_locked(self):
        assert op_mod._FLAGGED_LEVELS == ("medium", "high")


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(op_mod)

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

    def test_composes_units_5_and_8(self):
        src = self._code_only()
        for required in (
            "detect_run_anomalies",  # Unit 5
            "best_sequence",          # Unit 8
            "get_tags",               # Unit 27/28
            "set_tags",               # Unit 27/28
        ):
            assert required in src
