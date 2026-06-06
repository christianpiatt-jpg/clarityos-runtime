"""
A30 — directives + directive_metadata are forwarded over HTTP.

A28 put directives/directive_metadata on the run_thread_message return dict;
A30 forwards them through POST /me/threads/{id}/message (additive fields on
V47PostMessageResponse) so the web/phone chat can render directive badges.
grounding_status (A19) is retained for back-compat.
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
    def _route(model_id, prompt, **kwargs):
        return {"ok": True, "model_id": model_id, "provider": "fake",
                "text": text, "mock": True, "ts": 0.0}
    return _route


def _post(client, sid, tid, content):
    return client.post(
        f"/me/threads/{tid}/message",
        json={"content": content},
        headers=_auth(sid),
    )


def test_structure_directive_forwarded(client, monkeypatch):
    import model_router
    import threads_vault as tv
    user, sid = _make_user()
    tid = tv.create_thread(user, "chat")["thread_id"]
    monkeypatch.setattr(model_router, "route_request",
                        _fixed_router("* a\n\n\n* b"))
    body = _post(client, sid, tid, "#structure format this").json()
    assert body["directives"] == ["structure"]
    assert body["directive_metadata"]["structure"]["status"] == "formatted"
    assert body["assistant_message"]["content"] == "- a\n\n- b"   # transformed
    assert body["grounding_status"] is None


def test_non_directive_turn_has_empty_surface(client, monkeypatch):
    import model_router
    import threads_vault as tv
    user, sid = _make_user()
    tid = tv.create_thread(user, "chat")["thread_id"]
    monkeypatch.setattr(model_router, "route_request", _fixed_router("hello"))
    body = _post(client, sid, tid, "just chatting").json()
    assert body["directives"] == []
    assert body["directive_metadata"] == {}
    assert body["grounding_status"] is None
    assert body["assistant_message"]["content"] == "hello"


def test_cite_backcompat_alongside_directive_surface(client, monkeypatch):
    import model_router
    import threads_vault as tv
    user, sid = _make_user()
    tid = tv.create_thread(user, "chat")["thread_id"]
    monkeypatch.setattr(
        model_router, "route_request",
        _fixed_router("According to the official report, all is summarized."),
    )
    body = _post(client, sid, tid, "#cite summarize").json()
    # A19 back-compat field still present…
    assert body["grounding_status"] == "grounded"
    # …and the unified surface mirrors it.
    assert body["directives"] == ["cite"]
    assert body["directive_metadata"]["cite"]["status"] == "grounded"


def test_operator_directive_transforms_and_reports(client, monkeypatch):
    import model_router
    import threads_vault as tv
    user, sid = _make_user()
    tid = tv.create_thread(user, "chat")["thread_id"]
    monkeypatch.setattr(
        model_router, "route_request",
        _fixed_router("We should ship now. There is a risk of delay."),
    )
    body = _post(client, sid, tid, "#operator brief").json()
    assert body["directives"] == ["operator"]
    assert body["directive_metadata"]["operator"]["status"] == "operator_synthesized"
    assert body["assistant_message"]["content"].startswith("# Operator Brief")
