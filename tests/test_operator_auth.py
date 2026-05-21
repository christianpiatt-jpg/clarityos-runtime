"""
Tests for v64 / Unit 66 — auth wall on /operator/* GETs.

Mounts ``runtime_router`` + ``operator_router`` on a private FastAPI
app and exercises the real ``require_operator`` dependency (no
override) by seeding ``sessions_store`` directly.

Layered coverage:
    A. Unauthed → 401 on the 3 v63 GETs
    B. Authed → 200 + ownership check
    C. Cross-operator → 404 (don't leak existence)
    D. Vault path-param is ignored; authed identity rules
    E. POST /start + /step still open (out of v66 scope)
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from conftest import TestClient

import model_router as mr
import runtime_http as rh_mod
import runtime_persistence as rp_mod
import session_loop as sl_mod
import sessions_store


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture
def app_and_client(monkeypatch):
    app = FastAPI()
    app.include_router(rh_mod.runtime_router)
    app.include_router(rh_mod.operator_router)

    # NB: no dependency override — these tests exercise the real
    # require_operator path against sessions_store.

    sid_counter = {"n": 0}
    def fake_make_session_id():
        sid_counter["n"] += 1
        return f"sess-auth-{sid_counter['n']:03d}"
    monkeypatch.setattr(sl_mod, "_make_session_id", fake_make_session_id)

    mr._reset_for_tests()
    rp_mod._reset_for_tests()
    yield app, TestClient(app)
    mr._reset_for_tests()
    rp_mod._reset_for_tests()


def _seed_auth(user: str) -> str:
    """Seed sessions_store with a valid session for ``user`` and
    return the X-Session-ID token. Mirrors what /login would do."""
    sid = f"auth-test-{user}"
    sessions_store.create_session(
        sid, user, expires_at=time.time() + 3600,
    )
    return sid


def _auth_header(user: str) -> dict[str, str]:
    """Convenience: seed + return ``{X-Session-ID: <token>}`` headers."""
    return {"X-Session-ID": _seed_auth(user)}


# ===========================================================================
# A. Unauthed → 401
# ===========================================================================
class TestUnauthenticated:
    def test_session_detail_requires_auth(self, app_and_client):
        _, c = app_and_client
        r = c.get("/operator/session/sess-anything")
        assert r.status_code == 401

    def test_session_list_requires_auth(self, app_and_client):
        _, c = app_and_client
        r = c.get("/operator/sessions")
        assert r.status_code == 401

    def test_vault_requires_auth(self, app_and_client):
        _, c = app_and_client
        r = c.get("/operator/vault/anything")
        assert r.status_code == 401

    def test_invalid_session_id_returns_401(self, app_and_client):
        _, c = app_and_client
        r = c.get(
            "/operator/sessions",
            headers={"X-Session-ID": "this-is-not-a-real-session-id"},
        )
        assert r.status_code == 401

    def test_expired_session_returns_401(self, app_and_client):
        _, c = app_and_client
        sid = "auth-test-expired"
        # Seed with a past expires_at to simulate expiry.
        sessions_store.create_session(
            sid, "op_zed", expires_at=time.time() - 60,
        )
        r = c.get(
            "/operator/sessions",
            headers={"X-Session-ID": sid},
        )
        assert r.status_code == 401


# ===========================================================================
# B. Authed → 200 + ownership check
# ===========================================================================
class TestAuthedSuccessPath:
    def test_authed_user_can_list_own_sessions(self, app_and_client):
        _, c = app_and_client
        alice = _auth_header("op_alice")
        # v68 — POST /start now requires auth; the seed call uses the
        # same auth header that the GET will use.
        c.post(
            "/operator/session/start",
            json={"operator_id": "ignored-by-server"},
            headers=alice,
        )
        r = c.get("/operator/sessions", headers=alice)
        assert r.status_code == 200
        body = r.json()
        assert body["operator_id"] == "op_alice"
        assert len(body["sessions"]) == 1

    def test_authed_user_can_read_own_session_detail(self, app_and_client):
        _, c = app_and_client
        alice = _auth_header("op_alice")
        s0 = c.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
            headers=alice,
        ).json()["session_state"]

        r = c.get(
            f"/operator/session/{s0['session_id']}",
            headers=alice,
        )
        assert r.status_code == 200
        assert r.json()["session_state"]["session_id"] == s0["session_id"]

    def test_authed_user_can_read_own_vault(self, app_and_client):
        _, c = app_and_client
        alice = _auth_header("op_alice")
        s0 = c.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
            headers=alice,
        ).json()["session_state"]
        c.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "build the vault"},
            headers=alice,
        )

        # Path operator_id is decorative; authed identity rules.
        r = c.get("/operator/vault/whatever", headers=alice)
        assert r.status_code == 200
        body = r.json()
        assert body["operator_id"] == "op_alice"
        assert body["vault"] is not None


# ===========================================================================
# C. Cross-operator → 404 (don't leak existence)
# ===========================================================================
class TestCrossOperatorIsolation:
    def test_other_operators_session_appears_as_404(self, app_and_client):
        _, c = app_and_client
        # Alice creates a session (using Alice's auth).
        alice = _auth_header("op_alice")
        alice_session = c.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
            headers=alice,
        ).json()["session_state"]

        # Bob tries to read Alice's session.
        bob = _auth_header("op_bob")
        r = c.get(
            f"/operator/session/{alice_session['session_id']}",
            headers=bob,
        )
        # 404 — not 403 — so Bob can't even confirm Alice's session_id exists.
        assert r.status_code == 404

    def test_other_operators_sessions_not_in_list(self, app_and_client):
        _, c = app_and_client
        alice = _auth_header("op_alice")
        bob   = _auth_header("op_bob")
        c.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
            headers=alice,
        )
        c.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
            headers=bob,
        )

        alice_resp = c.get("/operator/sessions", headers=alice).json()
        bob_resp   = c.get("/operator/sessions", headers=bob).json()

        assert len(alice_resp["sessions"]) == 1
        assert len(bob_resp["sessions"])   == 1
        assert alice_resp["sessions"][0]["operator_id"] == "op_alice"
        assert bob_resp["sessions"][0]["operator_id"]   == "op_bob"

    def test_other_operators_vault_returns_authed_users_vault(self, app_and_client):
        _, c = app_and_client
        # Alice builds a vault under her auth.
        alice = _auth_header("op_alice")
        s0 = c.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
            headers=alice,
        ).json()["session_state"]
        c.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "x"},
            headers=alice,
        )

        # Bob asks for /operator/vault/op_alice — path value ignored;
        # response carries Bob's empty vault, not Alice's.
        bob = _auth_header("op_bob")
        r = c.get("/operator/vault/op_alice", headers=bob)
        assert r.status_code == 200
        body = r.json()
        assert body["operator_id"] == "op_bob"   # NOT op_alice
        assert body["vault"] is None             # Bob has no vault

    def test_other_operators_step_returns_404(self, app_and_client):
        # v68 — NEW. Step ownership: Bob tries to step Alice's session.
        _, c = app_and_client
        alice = _auth_header("op_alice")
        s0 = c.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
            headers=alice,
        ).json()["session_state"]

        bob = _auth_header("op_bob")
        r = c.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "hijack attempt"},
            headers=bob,
        )
        assert r.status_code == 404

    def test_resume_rejects_other_operators_session_under_auth(self, app_and_client):
        # v68 — resume ownership now compares against AUTHED identity.
        _, c = app_and_client
        alice = _auth_header("op_alice")
        s0 = c.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
            headers=alice,
        ).json()["session_state"]

        bob = _auth_header("op_bob")
        r = c.post(
            "/operator/session/start",
            json={
                "operator_id": "ignored",
                "resume":      True,
                "session_id":  s0["session_id"],
            },
            headers=bob,
        )
        # Resume miss/mismatch silently falls through to a fresh
        # start — same posture as v61. Bob gets a NEW session of his
        # own, NOT Alice's.
        assert r.status_code == 200
        new_state = r.json()["session_state"]
        assert new_state["session_id"] != s0["session_id"]
        assert new_state["operator_id"] == "op_bob"


# ===========================================================================
# D. Vault path-param is ignored
# ===========================================================================
class TestVaultPathIgnored:
    def test_arbitrary_path_resolves_to_authed_vault(self, app_and_client):
        _, c = app_and_client
        sid = _seed_auth("op_alice")
        for path_value in ("op_alice", "op_bob", "op_carol", "spoofed"):
            r = c.get(
                f"/operator/vault/{path_value}",
                headers={"X-Session-ID": sid},
            )
            assert r.status_code == 200
            assert r.json()["operator_id"] == "op_alice"


# ===========================================================================
# E. POST /start + /step under v68 — now require auth
# ===========================================================================
class TestPostEndpointsLocked:
    def test_start_requires_auth(self, app_and_client):
        _, c = app_and_client
        r = c.post("/operator/session/start", json={"operator_id": "op_alice"})
        assert r.status_code == 401

    def test_step_requires_auth(self, app_and_client):
        _, c = app_and_client
        # Need an Alice session first to have a session_id to step.
        alice = _auth_header("op_alice")
        s0 = c.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
            headers=alice,
        ).json()["session_state"]
        # Then unauthed step → 401.
        r = c.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "step-one"},
        )
        assert r.status_code == 401

    def test_start_ignores_body_operator_id(self, app_and_client):
        # v68 — body operator_id is server-ignored; the resulting
        # session always belongs to the authed operator.
        _, c = app_and_client
        bob = _auth_header("op_bob")
        r = c.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},  # spoof attempt
            headers=bob,
        )
        assert r.status_code == 200
        assert r.json()["session_state"]["operator_id"] == "op_bob"

    def test_step_rewrites_operator_id_to_authed(self, app_and_client):
        # v68 — even if a v62-era client passes a session_state with
        # ``operator_id: "op_alice"``, the server uses the authed
        # identity for ownership decisions. (Alice IS the authed
        # operator here; testing the rewrite path with a
        # well-formed payload.)
        _, c = app_and_client
        alice = _auth_header("op_alice")
        s0 = c.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
            headers=alice,
        ).json()["session_state"]
        # Mutate the local session_state's operator_id to something
        # bogus — server should rewrite to authed before passing on.
        s0_spoofed = {**s0, "operator_id": "op_carol"}
        r = c.post(
            "/operator/session/step",
            json={"session_state": s0_spoofed, "text": "step-one"},
            headers=alice,
        )
        assert r.status_code == 200
        assert r.json()["session_state"]["operator_id"] == "op_alice"
