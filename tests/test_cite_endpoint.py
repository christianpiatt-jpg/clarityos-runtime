"""
A19 — #cite grounding status is forwarded over HTTP.

A18 wired the grounding gate into the kernel (grounding_status on the
run_thread_message return dict). A19 surfaces it: POST
/me/threads/{id}/message now echoes grounding_status so the chat UI can
render a per-turn badge. The web/desktop/phone clients can only see what
the endpoint forwards, so these tests lock that API contract:

* a #cite turn whose reply stays ungrounded after the retry -> "incomplete"
* a #cite turn whose reply is grounded                       -> "grounded"
* a non-#cite turn                                           -> null (field
  present in the contract, but None)
"""
from __future__ import annotations

import secrets
import time

import pytest


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(username="alice", cohort="founder"):
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
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


def _fixed_router(text):
    """A route_request stand-in that always returns the same text."""
    def _route(model_id, prompt, **kwargs):
        return {
            "ok": True, "model_id": model_id, "provider": "fake",
            "text": text, "mock": True, "ts": 0.0,
        }
    return _route


def test_post_message_forwards_grounding_incomplete(client, monkeypatch):
    import model_router
    import threads_vault as tv
    user, sid = _make_user()
    tid = tv.create_thread(user, "chat")["thread_id"]
    # Ungrounded factual reply (bare number, no citation). Both the initial
    # call and the single retry return it -> still ungrounded -> incomplete.
    monkeypatch.setattr(model_router, "route_request",
                        _fixed_router("The value is 42."))
    resp = client.post(
        f"/me/threads/{tid}/message",
        json={"content": "#cite what is it?"},
        headers=_auth(sid),
    )
    assert resp.status_code == 200
    assert resp.json()["grounding_status"] == "incomplete"


def test_post_message_forwards_grounding_grounded(client, monkeypatch):
    import model_router
    import threads_vault as tv
    user, sid = _make_user()
    tid = tv.create_thread(user, "chat")["thread_id"]
    monkeypatch.setattr(
        model_router, "route_request",
        _fixed_router("According to the official report, all is well."),
    )
    resp = client.post(
        f"/me/threads/{tid}/message",
        json={"content": "#cite summarize"},
        headers=_auth(sid),
    )
    assert resp.status_code == 200
    assert resp.json()["grounding_status"] == "grounded"


def test_post_message_non_cite_grounding_is_null(client, monkeypatch):
    import model_router
    import threads_vault as tv
    user, sid = _make_user()
    tid = tv.create_thread(user, "chat")["thread_id"]
    # Same ungrounded text, but NO #cite directive -> gate never runs.
    monkeypatch.setattr(model_router, "route_request",
                        _fixed_router("The value is 42."))
    resp = client.post(
        f"/me/threads/{tid}/message",
        json={"content": "what is it?"},
        headers=_auth(sid),
    )
    assert resp.status_code == 200
    body = resp.json()
    # Field is part of the contract, but null on a non-#cite turn.
    assert "grounding_status" in body
    assert body["grounding_status"] is None
