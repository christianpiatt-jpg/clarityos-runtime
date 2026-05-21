"""
Tests for v50 — Thread summaries.

Covers:

threads_vault:
  * ThreadMeta now carries summary + summary_ts_ms (default None)
  * update_thread_summary round-trip + clearing semantics
  * Existing rename / append flows preserve the summary fields
  * get_thread_meta success + KeyError on missing thread

intelligence_kernel:
  * summarize_thread on an empty thread clears the summary
  * summarize_thread on a populated thread routes through the model
    router + writes summary + bumps summary_ts_ms
  * Model resolved with task="thread_summary" (default model surfaces)
  * KeyError on missing thread bubbles for the app-layer 404

Endpoints:
  * GET /me/threads/{id}/summary returns meta with cached summary
  * POST /me/threads/{id}/summarize generates summary (force=True)
  * Recent summary skip-if-not-forced shortcut returns cached meta
  * 404 paths
  * /health version 4.4
"""
from __future__ import annotations

import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(app_module, username, cohort="founder"):
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


# ===========================================================================
# threads_vault — meta shape + summary helpers
# ===========================================================================
def test_create_thread_default_summary_is_none(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", "x")
    assert meta["summary"] is None
    assert meta["summary_ts_ms"] is None


def test_get_thread_meta_returns_meta_only(reset_stores):
    import threads_vault as tv
    created = tv.create_thread("alice", "x")
    fetched = tv.get_thread_meta("alice", created["thread_id"])
    assert fetched["thread_id"] == created["thread_id"]
    assert fetched["summary"] is None


def test_get_thread_meta_missing_raises_key_error(reset_stores):
    import threads_vault as tv
    with pytest.raises(KeyError):
        tv.get_thread_meta("alice", "no_such_thread")


def test_update_thread_summary_round_trip(reset_stores):
    import threads_vault as tv
    created = tv.create_thread("alice", "x")
    out = tv.update_thread_summary(
        "alice", created["thread_id"], "we discussed the q4 plan", 12345,
    )
    assert out["summary"] == "we discussed the q4 plan"
    assert out["summary_ts_ms"] == 12345
    fetched = tv.get_thread_meta("alice", created["thread_id"])
    assert fetched["summary"] == "we discussed the q4 plan"
    assert fetched["summary_ts_ms"] == 12345


def test_update_thread_summary_clears_with_none(reset_stores):
    import threads_vault as tv
    created = tv.create_thread("alice", "x")
    tv.update_thread_summary("alice", created["thread_id"], "first pass", 100)
    cleared = tv.update_thread_summary("alice", created["thread_id"], None, 200)
    assert cleared["summary"] is None
    assert cleared["summary_ts_ms"] is None


def test_update_thread_summary_strips_whitespace_only(reset_stores):
    import threads_vault as tv
    created = tv.create_thread("alice", "x")
    out = tv.update_thread_summary("alice", created["thread_id"], "   ", 1)
    assert out["summary"] is None
    assert out["summary_ts_ms"] is None


def test_update_thread_summary_missing_raises_key_error(reset_stores):
    import threads_vault as tv
    with pytest.raises(KeyError):
        tv.update_thread_summary("alice", "no_such_thread", "x", 1)


def test_rename_preserves_summary(reset_stores):
    """Renaming a thread must not drop the previously-stored summary."""
    import threads_vault as tv
    created = tv.create_thread("alice", "old")
    tv.update_thread_summary(
        "alice", created["thread_id"], "the user is planning q4", 555,
    )
    renamed = tv.rename_thread("alice", created["thread_id"], "new")
    assert renamed["summary"] == "the user is planning q4"
    assert renamed["summary_ts_ms"] == 555


def test_append_message_preserves_summary(reset_stores):
    import threads_vault as tv
    created = tv.create_thread("alice", "x")
    tv.update_thread_summary("alice", created["thread_id"], "stable", 99)
    meta_after, _ = tv.append_message(
        "alice", created["thread_id"],
        {"role": "user", "content": "another turn"},
    )
    assert meta_after["summary"] == "stable"
    assert meta_after["summary_ts_ms"] == 99


def test_list_threads_carries_summary(reset_stores):
    import threads_vault as tv
    a = tv.create_thread("alice", "first")
    b = tv.create_thread("alice", "second")
    tv.update_thread_summary("alice", a["thread_id"], "summary A", 100)
    metas = tv.list_threads("alice")
    by_id = {m["thread_id"]: m for m in metas}
    assert by_id[a["thread_id"]]["summary"] == "summary A"
    assert by_id[b["thread_id"]]["summary"] is None


# ===========================================================================
# intelligence_kernel — summarize_thread
# ===========================================================================
def test_summarize_thread_empty_clears_summary(reset_stores):
    """An empty thread → summary cleared (no model call needed)."""
    import intelligence_kernel as ik
    import threads_vault as tv
    created = tv.create_thread("alice", "x")
    out = ik.summarize_thread("alice", created["thread_id"])
    assert out["meta"]["summary"] is None
    assert out["meta"]["summary_ts_ms"] is None


def test_summarize_thread_populated_writes_summary(reset_stores):
    """A populated thread → summary populated + summary_ts_ms set."""
    import intelligence_kernel as ik
    import threads_vault as tv
    created = tv.create_thread("alice", "x")
    ik.run_thread_message("alice", created["thread_id"], "i need to plan q4")
    out = ik.summarize_thread("alice", created["thread_id"])
    assert isinstance(out["meta"]["summary"], str) and out["meta"]["summary"]
    assert isinstance(out["meta"]["summary_ts_ms"], int)
    assert out["meta"]["summary_ts_ms"] > 0


def test_summarize_thread_routes_through_model_router(
    reset_stores, monkeypatch,
):
    """The kernel resolves a model_id with task='thread_summary' and
    calls model_router.route_request. We monkeypatch the handler so
    we can assert on the model_id + on the prompt format."""
    import intelligence_kernel as ik
    import model_router as mr
    import threads_vault as tv

    captured = {"model_id": None, "prompt": None}

    def fake_handler(model_id, prompt, *, temperature, max_tokens):
        captured["model_id"] = model_id
        captured["prompt"] = prompt
        return {
            "ok": True, "model_id": model_id, "provider": "anthropic",
            "text": "FAKE SUMMARY: q4 planning conversation",
            "mock": False, "ts": 0.0,
        }

    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "anthropic", fake_handler)

    created = tv.create_thread("alice", "x")
    ik.run_thread_message("alice", created["thread_id"], "kick off planning")
    out = ik.summarize_thread("alice", created["thread_id"])

    assert captured["model_id"] == mr.TASK_DEFAULTS["thread_summary"]
    # System instruction must be in the prompt the kernel built.
    assert "SYSTEM:" in captured["prompt"]
    assert "Summarize this conversation" in captured["prompt"]
    # The summary the kernel persisted is exactly what the handler returned.
    assert out["meta"]["summary"] == "FAKE SUMMARY: q4 planning conversation"


def test_summarize_thread_missing_raises_key_error(reset_stores):
    import intelligence_kernel as ik
    with pytest.raises(KeyError):
        ik.summarize_thread("alice", "no_such_thread")


def test_summarize_thread_emits_log_line(reset_stores, caplog):
    """summarize_thread emits a kernel_run log line with kind=
    'summarize_thread' + model_id + summary_len."""
    import json
    import intelligence_kernel as ik
    import threads_vault as tv
    caplog.set_level("INFO", logger="clarityos.kernel.runs")

    created = tv.create_thread("alice", "x")
    ik.run_thread_message("alice", created["thread_id"], "hi")
    ik.summarize_thread("alice", created["thread_id"])

    found = []
    for rec in caplog.records:
        if rec.message.startswith("kernel_run "):
            payload = json.loads(rec.message.split(" ", 1)[1])
            if payload.get("kind") == "summarize_thread":
                found.append(payload)
    assert found, "expected a summarize_thread kernel log line"
    assert found[-1]["meta"]["summary_len"] > 0
    assert found[-1]["meta"]["model_id"]


# ===========================================================================
# Endpoints — /me/threads/{id}/summary + /summarize
# ===========================================================================
def test_endpoint_get_summary_returns_meta(app_module, client):
    user, sid = _make_user(app_module, "smy_a", cohort="founder")
    cr = client.post("/me/threads", headers=_auth(sid), json={"title": "x"})
    tid = cr.json()["thread_id"]

    r = client.get(f"/me/threads/{tid}/summary", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["meta"]["thread_id"] == tid
    assert body["meta"]["summary"] is None
    assert body["meta"]["summary_ts_ms"] is None


def test_endpoint_get_summary_404_on_missing(app_module, client):
    user, sid = _make_user(app_module, "smy_b", cohort="founder")
    r = client.get("/me/threads/no_such_thread/summary", headers=_auth(sid))
    assert r.status_code == 404


def test_endpoint_summarize_round_trip(app_module, client):
    user, sid = _make_user(app_module, "smy_c", cohort="founder")
    cr = client.post("/me/threads", headers=_auth(sid), json={"title": "chat"})
    tid = cr.json()["thread_id"]
    # Add a turn so the summariser has something to chew on.
    client.post(
        f"/me/threads/{tid}/message", headers=_auth(sid),
        json={"content": "draft the kickoff doc"},
    )
    r = client.post(
        f"/me/threads/{tid}/summarize", headers=_auth(sid),
        json={"force": True},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert isinstance(body["meta"]["summary"], str) and body["meta"]["summary"]
    assert isinstance(body["meta"]["summary_ts_ms"], int)


def test_endpoint_summarize_skip_when_recent_without_force(
    app_module, client, monkeypatch,
):
    """If the existing summary is < 10 min old and force is not set,
    the kernel call is skipped — we verify by counting kernel calls."""
    import intelligence_kernel as ik

    user, sid = _make_user(app_module, "smy_d", cohort="founder")
    cr = client.post("/me/threads", headers=_auth(sid), json={"title": "x"})
    tid = cr.json()["thread_id"]
    client.post(
        f"/me/threads/{tid}/message", headers=_auth(sid),
        json={"content": "hello"},
    )

    # First summarize call (force=True): real kernel call.
    r1 = client.post(
        f"/me/threads/{tid}/summarize", headers=_auth(sid),
        json={"force": True},
    )
    first_summary = r1.json()["meta"]["summary"]
    assert first_summary

    # Wrap summarize_thread so we can detect a second invocation.
    calls = {"n": 0}
    real_summarize = ik.summarize_thread

    def counting_summarize(*args, **kwargs):
        calls["n"] += 1
        return real_summarize(*args, **kwargs)

    monkeypatch.setattr(ik, "summarize_thread", counting_summarize)

    # Second call without force — should short-circuit.
    r2 = client.post(
        f"/me/threads/{tid}/summarize", headers=_auth(sid), json={},
    )
    assert r2.status_code == 200
    assert calls["n"] == 0   # no new kernel call
    assert r2.json()["meta"]["summary"] == first_summary

    # Third call with force=True — should re-run.
    r3 = client.post(
        f"/me/threads/{tid}/summarize", headers=_auth(sid),
        json={"force": True},
    )
    assert r3.status_code == 200
    assert calls["n"] == 1


def test_endpoint_summarize_404_on_missing(app_module, client):
    user, sid = _make_user(app_module, "smy_e", cohort="founder")
    r = client.post(
        "/me/threads/no_such_thread/summarize",
        headers=_auth(sid), json={"force": True},
    )
    assert r.status_code == 404


def test_endpoint_summarize_400_on_dotted_thread_id(app_module, client):
    """Path-level thread_id validator still applies to the v50 routes."""
    user, sid = _make_user(app_module, "smy_f", cohort="founder")
    r = client.post(
        "/me/threads/has.dot.id/summarize",
        headers=_auth(sid), json={"force": True},
    )
    assert r.status_code == 400


def test_endpoint_summarize_persists_into_list(app_module, client):
    """After a summarize call, /me/threads list should carry the
    summary on the matching meta — confirms list_threads preserves
    the field."""
    user, sid = _make_user(app_module, "smy_g", cohort="founder")
    cr = client.post("/me/threads", headers=_auth(sid), json={"title": "x"})
    tid = cr.json()["thread_id"]
    client.post(
        f"/me/threads/{tid}/message", headers=_auth(sid),
        json={"content": "anything"},
    )
    client.post(
        f"/me/threads/{tid}/summarize", headers=_auth(sid),
        json={"force": True},
    )
    list_resp = client.get("/me/threads", headers=_auth(sid)).json()
    found = [t for t in list_resp["threads"] if t["thread_id"] == tid]
    assert found and isinstance(found[0]["summary"], str) and found[0]["summary"]


# ===========================================================================
# /health version
# ===========================================================================
def test_health_version_4_4(app_module, client):
    """v50 set health to 4.4; later versions bump further. Either is
    OK — the v50 contract didn't include the literal version string."""
    r = client.get("/health")
    assert r.json()["version"].startswith("4.")
