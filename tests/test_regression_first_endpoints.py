"""
Tests for V76 — ProblemSolver.REGRESSION_FIRST HTTP endpoints.

Coverage:
    A. Happy path: start → step → get → list → tag → close
    B. Session enforcement (401 anonymous; cross-user 404)
    C. Unknown chain id → 404
    D. Invalid request bodies (status, layer_index, oversized strings,
       empty title) → 400 via v29_hardening validator
    E. Closed-chain mutation lockout (step/tag/double-close → 400)
    F. Tag merge semantics over HTTP
    G. /health version locked at 4.23
    H. Routes manifest exposes the new endpoints
"""
from __future__ import annotations

import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures (same shape as v47 / v74 endpoint tests)
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(username, cohort="founder"):
    import bcrypt
    import sessions_store
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(
        sid, username, expires_at=time.time() + 3600,
    )
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ===========================================================================
# A. Happy path
# ===========================================================================
class TestHappyPath:
    def test_full_lifecycle(self, client):
        _, sid = _make_user("alice")

        # /start
        r = client.post(
            "/me/regression_first/start",
            json={"title": "Deploy hangs", "notes": "step 3 of auth"},
            headers=_auth(sid),
        )
        assert r.status_code == 200, r.text
        chain = r.json()
        chain_id = chain["chain_id"]
        assert chain["title"] == "Deploy hangs"
        assert chain["notes"] == "step 3 of auth"
        assert chain["layers"] == []
        assert chain["tags"] == {}
        assert chain["closed_at"] is None

        # /step — first layer
        r = client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={
                "layer_index": 0,
                "status": "ok",
                "notes": "build artifact present",
            },
            headers=_auth(sid),
        )
        assert r.status_code == 200, r.text
        chain = r.json()
        assert len(chain["layers"]) == 1
        assert chain["layers"][0]["status"] == "ok"

        # /step — second layer at a higher index (auto-sort proven)
        r = client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={
                "layer_index": 2,
                "status": "issue",
                "notes": "auth handler returns 500",
            },
            headers=_auth(sid),
        )
        assert r.status_code == 200
        chain = r.json()
        assert [L["layer_index"] for L in chain["layers"]] == [0, 2]

        # /step — overwrite layer 0
        r = client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={
                "layer_index": 0,
                "status": "issue",
                "notes": "build artifact stale",
            },
            headers=_auth(sid),
        )
        assert r.status_code == 200
        chain = r.json()
        assert len(chain["layers"]) == 2
        layer_0 = next(L for L in chain["layers"] if L["layer_index"] == 0)
        assert layer_0["status"] == "issue"
        assert layer_0["notes"] == "build artifact stale"

        # /tag
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"area": "deploy", "severity": "high"}},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        chain = r.json()
        assert chain["tags"] == {"area": "deploy", "severity": "high"}

        # /tag merge (overwrite severity, add surface)
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"severity": "medium", "surface": "api"}},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        chain = r.json()
        assert chain["tags"] == {
            "area": "deploy", "severity": "medium", "surface": "api",
        }

        # /list
        r = client.get("/me/regression_first", headers=_auth(sid))
        assert r.status_code == 200
        body = r.json()
        assert len(body["chains"]) == 1
        assert body["chains"][0]["chain_id"] == chain_id

        # /get
        r = client.get(
            f"/me/regression_first/{chain_id}", headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json()["chain_id"] == chain_id

        # /close with closing notes
        r = client.post(
            f"/me/regression_first/{chain_id}/close",
            json={"notes": "fixed auth handler — root cause: stale config"},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        chain = r.json()
        assert chain["closed_at"] is not None
        assert chain["closed_at"] >= chain["created_at"]
        assert chain["notes"].startswith("fixed auth handler")

    def test_list_newest_first(self, client):
        _, sid = _make_user("alice")
        ids = []
        for n in range(3):
            r = client.post(
                "/me/regression_first/start",
                json={"title": f"chain {n}"},
                headers=_auth(sid),
            )
            assert r.status_code == 200
            ids.append(r.json()["chain_id"])
        r = client.get("/me/regression_first", headers=_auth(sid))
        assert r.status_code == 200
        listed = [c["chain_id"] for c in r.json()["chains"]]
        # Newest first → reverse insertion order.
        assert listed == list(reversed(ids))


# ===========================================================================
# B. Session enforcement
# ===========================================================================
class TestSession:
    def test_start_requires_session(self, client):
        r = client.post(
            "/me/regression_first/start", json={"title": "x"},
        )
        assert r.status_code == 401

    def test_step_requires_session(self, client):
        r = client.post(
            "/me/regression_first/step?chain_id=any",
            json={"layer_index": 0, "status": "ok"},
        )
        assert r.status_code == 401

    def test_list_requires_session(self, client):
        r = client.get("/me/regression_first")
        assert r.status_code == 401

    def test_get_requires_session(self, client):
        r = client.get("/me/regression_first/any-id")
        assert r.status_code == 401

    def test_close_requires_session(self, client):
        r = client.post("/me/regression_first/any-id/close", json={})
        assert r.status_code == 401

    def test_tag_requires_session(self, client):
        r = client.post(
            "/me/regression_first/any-id/tag",
            json={"tags": {"a": "b"}},
        )
        assert r.status_code == 401

    def test_invalid_session_rejected(self, client):
        r = client.post(
            "/me/regression_first/start",
            json={"title": "x"},
            headers={"X-Session-ID": "definitely-not-real"},
        )
        assert r.status_code == 401

    def test_cross_user_chain_returns_404(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")

        # Alice opens a chain.
        r = client.post(
            "/me/regression_first/start",
            json={"title": "alice's chain"},
            headers=_auth(alice_sid),
        )
        chain_id = r.json()["chain_id"]

        # Bob tries to read it → 404 (existence not leaked).
        r = client.get(
            f"/me/regression_first/{chain_id}", headers=_auth(bob_sid),
        )
        assert r.status_code == 404

        # Bob tries to step it → 404.
        r = client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "ok"},
            headers=_auth(bob_sid),
        )
        assert r.status_code == 404

        # Bob tries to close it → 404.
        r = client.post(
            f"/me/regression_first/{chain_id}/close",
            json={},
            headers=_auth(bob_sid),
        )
        assert r.status_code == 404

        # Bob tries to tag it → 404.
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"a": "b"}},
            headers=_auth(bob_sid),
        )
        assert r.status_code == 404

        # Bob's list doesn't include it.
        r = client.get("/me/regression_first", headers=_auth(bob_sid))
        assert r.json()["chains"] == []

        # Alice's list does.
        r = client.get(
            "/me/regression_first", headers=_auth(alice_sid),
        )
        assert any(c["chain_id"] == chain_id for c in r.json()["chains"])


# ===========================================================================
# C. Unknown chain id
# ===========================================================================
class TestUnknownChain:
    def test_get_unknown_404(self, client):
        _, sid = _make_user("alice")
        r = client.get(
            "/me/regression_first/00000000-0000-4000-8000-000000000000",
            headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_step_unknown_404(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/step?chain_id=00000000-0000-4000-8000-000000000000",
            json={"layer_index": 0, "status": "ok"},
            headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_close_unknown_404(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/00000000-0000-4000-8000-000000000000/close",
            json={},
            headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_tag_unknown_404(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/00000000-0000-4000-8000-000000000000/tag",
            json={"tags": {"a": "b"}},
            headers=_auth(sid),
        )
        assert r.status_code == 404


# ===========================================================================
# D. Invalid request bodies → 400
# ===========================================================================
class TestValidation:
    def test_start_empty_title_400(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/start",
            json={"title": "   "},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_start_oversized_title_400(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/start",
            json={"title": "x" * 201},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_step_invalid_status_400(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]
        r = client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "GREEN"},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_step_negative_layer_index_400(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]
        r = client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": -1, "status": "ok"},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_tag_oversized_value_400(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"k": "x" * 257}},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_tag_empty_key_400(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"   ": "v"}},
            headers=_auth(sid),
        )
        assert r.status_code == 400


# ===========================================================================
# E. Closed-chain mutation lockout
# ===========================================================================
class TestClosedChainLockout:
    def test_step_on_closed_400(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            f"/me/regression_first/{chain_id}/close", json={},
            headers=_auth(sid),
        )
        r = client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "ok"},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_tag_on_closed_400(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            f"/me/regression_first/{chain_id}/close", json={},
            headers=_auth(sid),
        )
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"a": "b"}},
            headers=_auth(sid),
        )
        assert r.status_code == 400

    def test_double_close_400(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]
        r1 = client.post(
            f"/me/regression_first/{chain_id}/close", json={},
            headers=_auth(sid),
        )
        assert r1.status_code == 200
        r2 = client.post(
            f"/me/regression_first/{chain_id}/close", json={},
            headers=_auth(sid),
        )
        assert r2.status_code == 400


# ===========================================================================
# F. Tag merge semantics over HTTP
# ===========================================================================
class TestTagMergeOverHttp:
    def test_merge_preserves_unmentioned_keys(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]

        client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"area": "wp", "severity": "high"}},
            headers=_auth(sid),
        )
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"severity": "low"}},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json()["tags"] == {"area": "wp", "severity": "low"}

    def test_empty_tags_is_noop(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start", json={"title": "x"},
            headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"area": "wp"}},
            headers=_auth(sid),
        )
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {}},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json()["tags"] == {"area": "wp"}


# ===========================================================================
# G. /health version + routes manifest
# ===========================================================================
class TestHealthAndManifest:
    def test_health_version_locked(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["version"] == "4.23"

    def test_root_manifest_lists_v76_routes(self, client):
        r = client.get("/")
        assert r.status_code == 200
        endpoints = r.json()["endpoints"]
        for route in (
            "POST /me/regression_first/start",
            "POST /me/regression_first/step",
            "GET  /me/regression_first/{chain_id}",
            "GET  /me/regression_first",
            "POST /me/regression_first/{chain_id}/close",
            "POST /me/regression_first/{chain_id}/tag",
        ):
            assert route in endpoints, f"missing route entry: {route!r}"
