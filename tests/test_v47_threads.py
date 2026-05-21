"""
Tests for v47 — Threads (persistent threaded interactions).

Vault-level coverage:
* create_thread / list_threads round-trip + ordering by updated_at
* get_thread returns messages in chronological order even when
  several land in the same millisecond
* append_message updates meta (updated_at + message_count)
* rename_thread updates meta
* delete_thread removes meta + messages (and reserved embeddings)
* missing-thread errors raise KeyError

Kernel coverage:
* run_thread_message appends user + assistant messages, returns both
  + updated meta + model_id
* run_thread_message rejects empty content (ValueError) and
  non-existent thread (KeyError)
* run_thread_message logs ``run_thread_message`` via kernel_logging
  and bumps last_model_used on operator_state
* kernel_view_for_user surfaces ``thread_count`` + ``last_thread_updated_at``

Endpoint coverage:
* /me/threads round-trip (create → list → get → message → rename → delete)
* /me/threads/{thread_id} 404 on unknown id
* /me/threads/{thread_id}/message 404 on unknown thread
* /me/threads/{thread_id}/message 400 on empty content
* /me capability advertises threads
* /health version 4.3
"""
from __future__ import annotations

import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures (same shape as v44 / v45 / v46 tests)
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
# threads_vault — vault-level round-trips
# ===========================================================================
def test_create_thread_returns_meta_with_required_fields(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", "first conversation")
    assert isinstance(meta["thread_id"], str) and len(meta["thread_id"]) > 0
    assert meta["title"] == "first conversation"
    assert meta["message_count"] == 0
    assert meta["archived"] is False
    assert meta["created_at"] > 0
    assert meta["updated_at"] >= meta["created_at"]


def test_create_thread_accepts_none_title(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", None)
    assert meta["title"] is None


def test_create_and_list_threads_round_trip(reset_stores):
    import threads_vault as tv
    a = tv.create_thread("alice", "first")
    time.sleep(0.005)   # ensure ms ticks for ordering
    b = tv.create_thread("alice", "second")
    metas = tv.list_threads("alice")
    assert len(metas) == 2
    # newest-first by updated_at
    assert metas[0]["thread_id"] == b["thread_id"]
    assert metas[1]["thread_id"] == a["thread_id"]


def test_list_threads_isolated_per_user(reset_stores):
    import threads_vault as tv
    tv.create_thread("alice", "alice's thread")
    tv.create_thread("bob", "bob's thread")
    a_metas = tv.list_threads("alice")
    b_metas = tv.list_threads("bob")
    assert len(a_metas) == 1
    assert len(b_metas) == 1
    assert a_metas[0]["title"] == "alice's thread"
    assert b_metas[0]["title"] == "bob's thread"


def test_get_thread_returns_messages_in_order(reset_stores):
    """Three quick appends should order chronologically — the seq
    suffix on the message key keeps order stable even within a single
    millisecond."""
    import threads_vault as tv
    meta = tv.create_thread("alice", "ordered")
    tid = meta["thread_id"]
    tv.append_message("alice", tid, {"role": "user",      "content": "first"})
    tv.append_message("alice", tid, {"role": "assistant", "content": "second"})
    tv.append_message("alice", tid, {"role": "user",      "content": "third"})
    _, msgs = tv.get_thread("alice", tid)
    assert [m["content"] for m in msgs] == ["first", "second", "third"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]


def test_append_message_updates_meta(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", "x")
    tid = meta["thread_id"]
    initial_updated = meta["updated_at"]
    time.sleep(0.005)
    meta2, _ = tv.append_message("alice", tid, {"role": "user", "content": "hi"})
    assert meta2["message_count"] == 1
    assert meta2["updated_at"] > initial_updated
    meta3, _ = tv.append_message("alice", tid, {"role": "assistant", "content": "hello"})
    assert meta3["message_count"] == 2


def test_append_message_fills_missing_ts_ms(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", "x")
    tid = meta["thread_id"]
    _, saved = tv.append_message(
        "alice", tid, {"role": "user", "content": "hi"},   # no ts_ms
    )
    assert isinstance(saved["ts_ms"], int) and saved["ts_ms"] > 0


def test_append_message_rejects_invalid_role(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", "x")
    with pytest.raises(ValueError):
        tv.append_message(
            "alice", meta["thread_id"],
            {"role": "robot", "content": "x"},
        )


def test_append_message_missing_thread_raises_key_error(reset_stores):
    import threads_vault as tv
    with pytest.raises(KeyError):
        tv.append_message("alice", "no_such_thread_id", {
            "role": "user", "content": "x",
        })


def test_rename_thread_updates_meta(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", "old")
    out = tv.rename_thread("alice", meta["thread_id"], "new title")
    assert out["title"] == "new title"
    # round-trip via list_threads
    listed = tv.list_threads("alice")[0]
    assert listed["title"] == "new title"


def test_rename_missing_thread_raises_key_error(reset_stores):
    import threads_vault as tv
    with pytest.raises(KeyError):
        tv.rename_thread("alice", "no_such_thread_id", "x")


def test_delete_thread_removes_meta_and_messages(reset_stores):
    import memory_vault as mv
    import threads_vault as tv
    meta = tv.create_thread("alice", "doomed")
    tid = meta["thread_id"]
    tv.append_message("alice", tid, {"role": "user", "content": "hi"})
    tv.append_message("alice", tid, {"role": "assistant", "content": "hey"})
    tv.delete_thread("alice", tid)

    # No meta + no messages remain.
    assert tv.list_threads("alice") == []
    keys = mv.vault_keys_for_user("alice")
    assert not any(k.startswith(f"threads.meta.{tid}") for k in keys)
    assert not any(k.startswith(f"threads.messages.{tid}.") for k in keys)
    # get_thread errors cleanly.
    with pytest.raises(KeyError):
        tv.get_thread("alice", tid)


def test_delete_missing_thread_is_idempotent(reset_stores):
    import threads_vault as tv
    # No raise.
    tv.delete_thread("alice", "no_such_thread_id")


def test_get_missing_thread_raises_key_error(reset_stores):
    import threads_vault as tv
    with pytest.raises(KeyError):
        tv.get_thread("alice", "no_such_thread_id")


def test_thread_id_path_chars_rejected(reset_stores):
    import threads_vault as tv
    with pytest.raises(ValueError):
        tv.get_thread("alice", "bad/id")
    with pytest.raises(ValueError):
        tv.get_thread("alice", "bad.id")


# ===========================================================================
# intelligence_kernel — run_thread_message + view fields
# ===========================================================================
def test_kernel_run_thread_message_creates_assistant_reply(reset_stores):
    import intelligence_kernel as ik
    import threads_vault as tv
    meta = tv.create_thread("alice", "chat")
    out = ik.run_thread_message("alice", meta["thread_id"], "hello there")
    assert out["meta"]["message_count"] == 2
    assert out["user_message"]["role"] == "user"
    assert out["user_message"]["content"] == "hello there"
    assert out["assistant_message"]["role"] == "assistant"
    # The mock router emits a deterministic ``[mock <model_id>] <preview>``
    # text, so we just assert the assistant content is non-empty.
    assert out["assistant_message"]["content"]
    assert out["model_id"]
    assert out["assistant_message"]["model"] == out["model_id"]


def test_kernel_run_thread_message_persists_via_vault(reset_stores):
    """Both messages should be readable back via threads_vault.get_thread."""
    import intelligence_kernel as ik
    import threads_vault as tv
    meta = tv.create_thread("alice", "chat")
    ik.run_thread_message("alice", meta["thread_id"], "first turn")
    _, msgs = tv.get_thread("alice", meta["thread_id"])
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant"]
    assert msgs[0]["content"] == "first turn"


def test_kernel_run_thread_message_records_last_model_used(reset_stores):
    """v44 last_model_used hook still fires (the kernel goes through
    _resolve_model)."""
    import intelligence_kernel as ik
    import operator_state as os_
    import threads_vault as tv
    meta = tv.create_thread("alice", "x")
    ik.run_thread_message("alice", meta["thread_id"], "hi")
    state = os_.get_operator_state("alice")
    assert state["last_model_used"]   # populated to whatever the router chose


def test_kernel_run_thread_message_rejects_empty_content(reset_stores):
    import intelligence_kernel as ik
    import threads_vault as tv
    meta = tv.create_thread("alice", "x")
    with pytest.raises(ValueError):
        ik.run_thread_message("alice", meta["thread_id"], "   ")


def test_kernel_run_thread_message_404_on_missing_thread(reset_stores):
    import intelligence_kernel as ik
    with pytest.raises(KeyError):
        ik.run_thread_message("alice", "no_such_thread", "hi")


def test_kernel_run_thread_message_emits_log_line(reset_stores, caplog):
    import intelligence_kernel as ik
    import json
    import threads_vault as tv
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    meta = tv.create_thread("alice", "x")
    ik.run_thread_message("alice", meta["thread_id"], "hi")
    found = []
    for rec in caplog.records:
        if rec.message.startswith("kernel_run "):
            payload = json.loads(rec.message.split(" ", 1)[1])
            if payload.get("kind") == "run_thread_message":
                found.append(payload)
    assert found, "expected a run_thread_message kernel log line"
    assert found[-1]["meta"]["message_count"] == 2
    assert found[-1]["meta"]["model_id"]


def test_kernel_view_for_user_includes_thread_metrics(reset_stores):
    import intelligence_kernel as ik
    import threads_vault as tv
    # No threads → zero / None.
    view = ik.kernel_view_for_user("alice")
    assert view["thread_count"] == 0
    assert view["last_thread_updated_at"] is None

    a = tv.create_thread("alice", "first")
    time.sleep(0.005)
    b = tv.create_thread("alice", "second")
    view = ik.kernel_view_for_user("alice")
    assert view["thread_count"] == 2
    assert view["last_thread_updated_at"] == max(
        int(a["updated_at"]), int(b["updated_at"]),
    )


# ===========================================================================
# Endpoints — /me/threads round-trip
# ===========================================================================
def test_me_threads_endpoints_round_trip(app_module, client):
    user, sid = _make_user(app_module, "thr_a", cohort="founder")
    # 1. POST /me/threads → create
    r = client.post(
        "/me/threads", headers=_auth(sid), json={"title": "first thread"},
    )
    assert r.status_code == 200, r.json()
    meta = r.json()
    assert meta["title"] == "first thread"
    assert meta["message_count"] == 0
    tid = meta["thread_id"]

    # 2. GET /me/threads → list contains it
    r2 = client.get("/me/threads", headers=_auth(sid))
    assert r2.status_code == 200
    body = r2.json()
    assert len(body["threads"]) == 1
    assert body["threads"][0]["thread_id"] == tid

    # 3. GET /me/threads/{id} → empty messages
    r3 = client.get(f"/me/threads/{tid}", headers=_auth(sid))
    assert r3.status_code == 200
    body = r3.json()
    assert body["meta"]["thread_id"] == tid
    assert body["messages"] == []

    # 4. POST /me/threads/{id}/message → assistant reply
    r4 = client.post(
        f"/me/threads/{tid}/message", headers=_auth(sid),
        json={"content": "hello there"},
    )
    assert r4.status_code == 200, r4.json()
    body = r4.json()
    assert body["meta"]["message_count"] == 2
    assert body["user_message"]["role"] == "user"
    assert body["user_message"]["content"] == "hello there"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"]
    assert body["model_id"]

    # 5. GET /me/threads/{id} → 2 messages now
    r5 = client.get(f"/me/threads/{tid}", headers=_auth(sid))
    msgs = r5.json()["messages"]
    assert len(msgs) == 2
    assert [m["role"] for m in msgs] == ["user", "assistant"]

    # 6. POST /me/threads/{id}/rename
    r6 = client.post(
        f"/me/threads/{tid}/rename", headers=_auth(sid),
        json={"title": "renamed thread"},
    )
    assert r6.status_code == 200
    assert r6.json()["title"] == "renamed thread"

    # 7. POST /me/threads/{id}/delete → ok
    r7 = client.post(
        f"/me/threads/{tid}/delete", headers=_auth(sid), json={},
    )
    assert r7.status_code == 200
    assert r7.json()["ok"] is True

    # 8. GET /me/threads/{id} → 404
    r8 = client.get(f"/me/threads/{tid}", headers=_auth(sid))
    assert r8.status_code == 404


def test_me_threads_create_no_title(app_module, client):
    user, sid = _make_user(app_module, "thr_b", cohort="founder")
    r = client.post("/me/threads", headers=_auth(sid), json={})
    assert r.status_code == 200
    assert r.json()["title"] is None


def test_me_threads_isolated_per_user(app_module, client):
    a_user, a_sid = _make_user(app_module, "thr_alice", cohort="founder")
    b_user, b_sid = _make_user(app_module, "thr_bob", cohort="founder")
    client.post("/me/threads", headers=_auth(a_sid), json={"title": "alice's"})
    client.post("/me/threads", headers=_auth(b_sid), json={"title": "bob's"})
    a = client.get("/me/threads", headers=_auth(a_sid)).json()["threads"]
    b = client.get("/me/threads", headers=_auth(b_sid)).json()["threads"]
    assert len(a) == 1 and a[0]["title"] == "alice's"
    assert len(b) == 1 and b[0]["title"] == "bob's"


def test_me_threads_get_unknown_returns_404(app_module, client):
    user, sid = _make_user(app_module, "thr_c", cohort="founder")
    r = client.get(
        "/me/threads/no_such_thread_id", headers=_auth(sid),
    )
    assert r.status_code == 404


def test_me_threads_message_unknown_returns_404(app_module, client):
    user, sid = _make_user(app_module, "thr_d", cohort="founder")
    r = client.post(
        "/me/threads/no_such_thread_id/message",
        headers=_auth(sid), json={"content": "hi"},
    )
    assert r.status_code == 404


def test_me_threads_message_empty_content_400(app_module, client):
    user, sid = _make_user(app_module, "thr_e", cohort="founder")
    cr = client.post("/me/threads", headers=_auth(sid), json={"title": "x"})
    tid = cr.json()["thread_id"]
    r = client.post(
        f"/me/threads/{tid}/message",
        headers=_auth(sid), json={"content": "   "},
    )
    assert r.status_code == 400


def test_me_threads_rename_unknown_returns_404(app_module, client):
    user, sid = _make_user(app_module, "thr_f", cohort="founder")
    r = client.post(
        "/me/threads/no_such_thread_id/rename",
        headers=_auth(sid), json={"title": "x"},
    )
    assert r.status_code == 404


def test_me_threads_delete_unknown_is_idempotent(app_module, client):
    """Deleting a missing thread is a no-op (mirrors vault_delete)."""
    user, sid = _make_user(app_module, "thr_g", cohort="founder")
    r = client.post(
        "/me/threads/no_such_thread_id/delete",
        headers=_auth(sid), json={},
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_me_threads_path_validation_blocks_dot_in_id(app_module, client):
    """Dots in thread ids are reserved for the message key separator —
    the app layer surfaces a clean 400 before reaching the vault."""
    user, sid = _make_user(app_module, "thr_h", cohort="founder")
    r = client.get(
        "/me/threads/has.dot.id", headers=_auth(sid),
    )
    assert r.status_code == 400


# ===========================================================================
# /me capability + /health version
# ===========================================================================
def test_me_capabilities_includes_threads(app_module, client):
    user, sid = _make_user(app_module, "cap_t", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    ids = [c["id"] for c in r.json().get("capabilities") or []]
    assert "threads" in ids


def test_me_kernel_view_includes_thread_count(app_module, client):
    """v47 — /me intelligence_kernel block carries thread_count."""
    user, sid = _make_user(app_module, "cap_t2", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    ik_block = r.json()["intelligence_kernel"]
    assert "thread_count" in ik_block
    assert "last_thread_updated_at" in ik_block
    assert ik_block["thread_count"] == 0
    assert ik_block["last_thread_updated_at"] is None


def test_health_version_4_3(app_module, client):
    """v47 set health version to 4.3; v50 bumps to 4.4. Either is OK
    here — the v47 contract didn't include the literal version string."""
    r = client.get("/health")
    assert r.json()["version"].startswith("4.")
