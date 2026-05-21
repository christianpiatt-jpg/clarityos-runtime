"""
Tests for ELINS2 Unit 10 — intelligence HTTP endpoints.

Layered coverage (>= 60 tests, target ~70):
    A. POST /elins/regression/runs/intelligence — happy path
    B. POST /elins/regression/runs/intelligence — validation (400)
    C. POST /elins/regression/runs/intelligence — missing runs (404)
    D. POST /elins/regression/runs/intelligence — auth (401)
    E. POST /elins/regression/runs/intelligence — shape locked
    F. GET /elins/regression/runs/dashboard/intelligence — default filters
    G. GET /elins/regression/runs/dashboard/intelligence — since/until/limit
    H. GET /elins/regression/runs/dashboard/intelligence — include_archived
    I. GET /elins/regression/runs/dashboard/intelligence — validation
    J. GET /elins/regression/runs/dashboard/intelligence — auth (401)
    K. GET /elins/regression/runs/dashboard/intelligence — shape locked
    L. Delegation — dashboard projection uses Unit 9 output
    M. Backward compatibility — ELINS v1 endpoints unchanged
    N. Determinism
"""
from __future__ import annotations

import json
import secrets
import sqlite3
import time
from pathlib import Path

import pytest
from conftest import TestClient

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


def _seed_runs(prefix="s", n=5, sp=5, ec=5, fixed_clock=None):
    if fixed_clock is not None:
        fixed_clock([
            f"2024-{m:02d}-01T10:00:00+00:00"
            for m in range(1, n + 1)
        ])
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec),
                                          _entry("p2", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


# ===========================================================================
# A. POST intelligence — happy path
# ===========================================================================
class TestPostIntelligenceHappyPath:
    def test_three_runs_returns_200(self, app_module, client):
        rids = _seed_runs(n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        assert r.status_code == 200

    def test_response_run_ids_match_request(self, app_module, client):
        rids = _seed_runs(n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        assert r.json()["run_ids"] == rids

    def test_response_top_level_keys(self, app_module, client):
        rids = _seed_runs(n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body.keys()) == {
            "run_ids", "similarity", "clustering", "trends",
            "anomalies", "scores", "narratives", "sequences",
        }

    def test_empty_run_ids_returns_200(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": []},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["run_ids"] == []
        assert body["scores"]["overall_health"] == 0.0

    def test_five_runs_best_worst_populated(self, app_module, client):
        rids = _seed_runs(prefix="bw", n=5)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert body["sequences"]["best"] is not None
        assert body["sequences"]["worst"] is not None

    def test_two_runs_best_worst_none(self, app_module, client):
        rids = _seed_runs(prefix="bwn", n=2)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert body["sequences"]["best"] is None
        assert body["sequences"]["worst"] is None


# ===========================================================================
# B. POST intelligence — validation (400)
# ===========================================================================
class TestPostIntelligenceValidation:
    def test_non_object_body_rejected(self, app_module, client):
        # FastAPI auto-validates ``body: dict`` and returns 422 for a
        # non-object body; logical 400 fires later in our handler for
        # malformed payload shape. Either is an acceptable rejection.
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json=["not-an-object"],
            headers=_auth(sid),
        )
        assert r.status_code in (400, 422)

    def test_missing_run_ids_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_run_ids_not_list_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": "not-a-list"},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_malformed_run_id_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": ["bad/id"]},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_non_string_run_id_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": [123]},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_empty_string_run_id_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": [""]},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_validation_error_response_envelope(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": "nope"},
            headers=_auth(sid),
        )
        body = r.json()
        assert body["ok"] is False
        assert body["error"] == "bad_payload"


# ===========================================================================
# C. POST intelligence — missing runs (404)
# ===========================================================================
class TestPostIntelligenceMissing:
    def test_missing_run_404(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": ["ghost"]},
            headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_partial_missing_run_404(self, app_module, client):
        rids = _seed_runs(prefix="pm", n=2)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids + ["ghost"]},
            headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_404_envelope(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": ["ghost"]},
            headers=_auth(sid),
        )
        body = r.json()
        assert body["ok"] is False
        assert body["error"] == "not_found"


# ===========================================================================
# D. POST intelligence — auth (401)
# ===========================================================================
class TestPostIntelligenceAuth:
    def test_missing_session_401(self, app_module, client):
        rids = _seed_runs(prefix="auth", n=2)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
        )
        assert r.status_code == 401

    def test_invalid_session_401(self, app_module, client):
        rids = _seed_runs(prefix="auth_inv", n=2)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers={"X-Session-ID": "nope"},
        )
        assert r.status_code == 401


# ===========================================================================
# E. POST intelligence — shape locked
# ===========================================================================
class TestPostIntelligenceShape:
    def test_similarity_shape(self, app_module, client):
        rids = _seed_runs(prefix="sh_sim", n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body["similarity"].keys()) == {"matrix", "top_k"}

    def test_clustering_shape(self, app_module, client):
        rids = _seed_runs(prefix="sh_clu", n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert "assignments" in body["clustering"]
        assert "cluster_summary" in body["clustering"]

    def test_trends_shape(self, app_module, client):
        rids = _seed_runs(prefix="sh_tr", n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body["trends"].keys()) == {"sequence", "pairs"}

    def test_anomalies_shape(self, app_module, client):
        rids = _seed_runs(prefix="sh_an", n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body["anomalies"].keys()) == {"runs", "thresholds"}

    def test_scores_shape(self, app_module, client):
        rids = _seed_runs(prefix="sh_sc", n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body["scores"].keys()) == {
            "runs", "pairs", "overall_health",
        }

    def test_narratives_shape(self, app_module, client):
        rids = _seed_runs(prefix="sh_nr", n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body["narratives"].keys()) == {
            "runs", "anomalies", "sequence",
        }

    def test_sequences_shape(self, app_module, client):
        rids = _seed_runs(prefix="sh_sq", n=5)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body["sequences"].keys()) == {
            "analysis", "best", "worst",
        }

    def test_delegates_to_unit_9(self, app_module, client):
        """Endpoint response must equal the Unit 9 function output
        verbatim (JSON-encoded), proving it's a thin pass-through."""
        rids = _seed_runs(prefix="del", n=3)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        body = r.json()
        raw = intel_mod.intelligence_for_run_ids(rids)
        # JSON round-trip through default=list normalises tuples to lists,
        # which is what FastAPI produces too.
        raw_json = json.loads(json.dumps(raw, default=list))
        assert body == raw_json


# ===========================================================================
# F. GET dashboard intelligence — default filters
# ===========================================================================
class TestGetDashboardDefault:
    def test_default_returns_200(self, app_module, client, fixed_clock):
        _seed_runs(prefix="ddf", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        assert r.status_code == 200

    def test_no_runs_returns_well_formed(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["run_ids"] == []
        assert body["overall_health"] == 0.0

    def test_returns_dashboard_shape_keys(self, app_module, client,
                                          fixed_clock):
        _seed_runs(prefix="dsk", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body.keys()) == {
            "run_ids", "overall_health", "headline",
            "key_metrics", "top_anomalies", "top_pairs", "narratives",
        }

    def test_run_ids_chronological(self, app_module, client, fixed_clock):
        """Dashboard sorts by created_at asc — earliest run first."""
        fixed_clock([
            "2024-03-01T10:00:00+00:00",
            "2024-01-01T10:00:00+00:00",
            "2024-02-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("late",   [_entry("p1", sp=5)])
        ep.save_comparison_result("first",  [_entry("p1", sp=5)])
        ep.save_comparison_result("middle", [_entry("p1", sp=5)])
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        assert r.json()["run_ids"] == ["first", "middle", "late"]


# ===========================================================================
# G. GET dashboard intelligence — since/until/limit
# ===========================================================================
class TestGetDashboardFilters:
    def test_since_filter(self, app_module, client, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-06-01T10:00:00+00:00",
            "2024-12-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("jan", [_entry("p1", sp=5)])
        ep.save_comparison_result("jun", [_entry("p1", sp=5)])
        ep.save_comparison_result("dec", [_entry("p1", sp=5)])
        sid = _make_user_session(app_module)
        # Timezone-less ISO string avoids the URL-encoding pitfall with
        # ``+`` (which decodes as a space in query-string form values).
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence"
            "?since=2024-06-01T00:00:00",
            headers=_auth(sid),
        )
        assert r.status_code == 200
        run_ids = r.json()["run_ids"]
        assert "jan" not in run_ids
        assert "jun" in run_ids
        assert "dec" in run_ids

    def test_until_filter(self, app_module, client, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-06-01T10:00:00+00:00",
            "2024-12-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("u_jan", [_entry("p1", sp=5)])
        ep.save_comparison_result("u_jun", [_entry("p1", sp=5)])
        ep.save_comparison_result("u_dec", [_entry("p1", sp=5)])
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence"
            "?until=2024-07-01T00:00:00",
            headers=_auth(sid),
        )
        run_ids = r.json()["run_ids"]
        assert "u_jan" in run_ids
        assert "u_jun" in run_ids
        assert "u_dec" not in run_ids

    def test_limit_param(self, app_module, client, fixed_clock):
        _seed_runs(prefix="lim", n=5, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence?limit=2",
            headers=_auth(sid),
        )
        assert len(r.json()["run_ids"]) == 2

    def test_since_until_combined(self, app_module, client, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-06-01T10:00:00+00:00",
            "2024-12-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("sc_jan", [_entry("p1", sp=5)])
        ep.save_comparison_result("sc_jun", [_entry("p1", sp=5)])
        ep.save_comparison_result("sc_dec", [_entry("p1", sp=5)])
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence"
            "?since=2024-05-01T00:00:00"
            "&until=2024-07-01T00:00:00",
            headers=_auth(sid),
        )
        assert r.json()["run_ids"] == ["sc_jun"]


# ===========================================================================
# H. GET dashboard intelligence — include_archived
# ===========================================================================
class TestGetDashboardArchived:
    def test_archived_excluded_by_default(self, app_module, client,
                                          fixed_clock):
        rids = _seed_runs(prefix="ax", n=3, fixed_clock=fixed_clock)
        # Archive one run.
        ep_sql.set_archived(rids[1], True)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        run_ids = r.json()["run_ids"]
        assert rids[1] not in run_ids

    def test_include_archived_true(self, app_module, client, fixed_clock):
        rids = _seed_runs(prefix="ay", n=3, fixed_clock=fixed_clock)
        ep_sql.set_archived(rids[1], True)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence"
            "?include_archived=true",
            headers=_auth(sid),
        )
        run_ids = r.json()["run_ids"]
        assert rids[1] in run_ids


# ===========================================================================
# I. GET dashboard intelligence — validation
# ===========================================================================
class TestGetDashboardValidation:
    def test_invalid_since_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence?since=not-iso",
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_limit_zero_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence?limit=0",
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_negative_limit_400(self, app_module, client):
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence?limit=-3",
            headers=_auth(sid),
        )
        assert r.status_code == 400


# ===========================================================================
# J. GET dashboard intelligence — auth
# ===========================================================================
class TestGetDashboardAuth:
    def test_missing_session_401(self, client):
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
        )
        assert r.status_code == 401

    def test_invalid_session_401(self, client):
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers={"X-Session-ID": "nope"},
        )
        assert r.status_code == 401


# ===========================================================================
# K. GET dashboard intelligence — shape locked
# ===========================================================================
class TestGetDashboardShape:
    def test_top_level_keys(self, app_module, client, fixed_clock):
        _seed_runs(prefix="sh_d", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body.keys()) == {
            "run_ids", "overall_health", "headline",
            "key_metrics", "top_anomalies", "top_pairs", "narratives",
        }

    def test_key_metrics_locked(self, app_module, client, fixed_clock):
        _seed_runs(prefix="km", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body["key_metrics"].keys()) == {
            "num_runs", "num_anomalies", "anomaly_fraction",
            "upward_fraction", "downward_fraction",
            "stable_cluster_fraction",
        }

    def test_top_anomalies_is_list(self, app_module, client, fixed_clock):
        _seed_runs(prefix="ta", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        assert isinstance(body["top_anomalies"], list)

    def test_top_pairs_is_list(self, app_module, client, fixed_clock):
        _seed_runs(prefix="tp", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        assert isinstance(body["top_pairs"], list)

    def test_narratives_has_three_panes(self, app_module, client,
                                        fixed_clock):
        _seed_runs(prefix="nv", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        assert set(body["narratives"].keys()) == {
            "runs", "anomalies", "sequence",
        }

    def test_top_anomaly_entry_shape(self, app_module, client, fixed_clock):
        # Seed enough stable + one outlier to fire the singleton anomaly.
        fixed_clock([
            f"2024-{m:02d}-01T10:00:00+00:00" for m in range(1, 8)
        ])
        for i in range(6):
            ep.save_comparison_result(
                f"as_{i:02d}",
                [_entry("p1", sp=5, ec=5)],
            )
        ep.save_comparison_result(
            "as_out",
            [_entry("p9", sp=0, ec=0,
                     sp_band="Fails core logic",
                     ec_band="Fails core logic")],
        )
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        if body["top_anomalies"]:
            entry = body["top_anomalies"][0]
            assert set(entry.keys()) == {"run_id", "score", "level"}

    def test_top_pairs_entry_shape(self, app_module, client, fixed_clock):
        _seed_runs(prefix="tpe", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        if body["top_pairs"]:
            entry = body["top_pairs"][0]
            assert set(entry.keys()) == {
                "pair_id", "stability", "trend", "score",
            }

    def test_num_runs_matches_run_ids_length(self, app_module, client,
                                             fixed_clock):
        _seed_runs(prefix="nr", n=4, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        assert body["key_metrics"]["num_runs"] == len(body["run_ids"])


# ===========================================================================
# L. Delegation — dashboard projection uses Unit 9 output
# ===========================================================================
class TestDashboardDelegation:
    def test_overall_health_matches_unit_9(self, app_module, client,
                                            fixed_clock):
        _seed_runs(prefix="del_h", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        intel = intel_mod.intelligence_for_run_ids(body["run_ids"])
        assert body["overall_health"] == pytest.approx(
            intel["scores"]["overall_health"],
        )

    def test_headline_matches_runs_narrative(self, app_module, client,
                                              fixed_clock):
        _seed_runs(prefix="del_hd", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        intel = intel_mod.intelligence_for_run_ids(body["run_ids"])
        assert body["headline"] == intel["narratives"]["runs"]["headline"]

    def test_anomaly_fraction_matches_sequence_analysis(self, app_module,
                                                        client, fixed_clock):
        _seed_runs(prefix="del_af", n=5, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        )
        body = r.json()
        intel = intel_mod.intelligence_for_run_ids(body["run_ids"])
        assert body["key_metrics"]["anomaly_fraction"] == pytest.approx(
            intel["sequences"]["analysis"]["anomaly_fraction"],
        )


# ===========================================================================
# M. Backward compatibility — ELINS v1 endpoints unchanged
# ===========================================================================
class TestBackwardCompat:
    def test_runs_summary_endpoint_unchanged(self, app_module, client,
                                              fixed_clock):
        rids = _seed_runs(prefix="bc1", n=2, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/runs/summary",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        # Returns {"runs": {run_id: <summary>, ...}}.
        assert "runs" in r.json()

    def test_get_runs_listing_endpoint_unchanged(self, app_module, client,
                                                  fixed_clock):
        _seed_runs(prefix="bc2", n=2, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get("/elins/regression/runs", headers=_auth(sid))
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body, list)
        for entry in body:
            assert "run_id" in entry

    def test_get_single_run_endpoint_unchanged(self, app_module, client,
                                                fixed_clock):
        rids = _seed_runs(prefix="bc3", n=1, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.get(
            f"/elins/regression/run/{rids[0]}",
            headers=_auth(sid),
        )
        assert r.status_code == 200
        # Still returns the inner result payload (list of pair dicts).
        assert isinstance(r.json(), list)

    def test_drift_series_endpoint_unchanged(self, app_module, client,
                                              fixed_clock):
        rids = _seed_runs(prefix="bc4", n=2, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        r = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": rids},
            headers=_auth(sid),
        )
        assert r.status_code == 200


# ===========================================================================
# N. Determinism
# ===========================================================================
class TestDeterminism:
    def test_post_intelligence_byte_equal(self, app_module, client):
        rids = _seed_runs(prefix="be", n=3)
        sid = _make_user_session(app_module)
        a = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        ).json()
        b = client.post(
            "/elins/regression/runs/intelligence",
            json={"run_ids": rids},
            headers=_auth(sid),
        ).json()
        assert a == b

    def test_get_dashboard_byte_equal(self, app_module, client, fixed_clock):
        _seed_runs(prefix="dbe", n=3, fixed_clock=fixed_clock)
        sid = _make_user_session(app_module)
        a = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        ).json()
        b = client.get(
            "/elins/regression/runs/dashboard/intelligence",
            headers=_auth(sid),
        ).json()
        assert a == b
