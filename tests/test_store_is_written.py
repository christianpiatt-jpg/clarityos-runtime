"""
#140 B · #191 · #71 -- the store is written.

WHAT THESE PIN. The member message route writes ONE Markov state per turn
(state_index 0, 1, ...; class markov_state_thread; ts_sealed; a normalised
vector; no text), so GET /markov/envelope/latest (the MQC cell) answers 200
and GET /sessions lists the thread; a write failure is a WARNING with a
hash and a type name and the reply is unchanged; a magic-link login writes
one durable row under session_records.{session_id} (ids and a number, no
text) that GET /operator/sessions lists as login_sessions -- with a session
REF, never the id -- and a login-row failure never costs the click.
"""
from __future__ import annotations

import json
import logging
import math
import secrets
import time

import pytest

from conftest import TestClient, seed_controller

import auth_magiclink as am
import dewey_pipeline
import markov_states_store
import memory_vault
import model_router as mr
import runtime_http as rh
import runtime_privacy
import sessions_store
import threads_vault
import users_store

import app as _app

REPLY = "The deposit clause is clause 7."
TEXT_1 = "Which clause of the lease governs the deposit?"
TEXT_2 = "no, that's wrong: it is clause 7"


class FakeRouter:
    def __init__(self, outputs):
        self._outputs = list(outputs)

    def __call__(self, model_id, prompt, **kwargs):
        text = self._outputs.pop(0) if self._outputs else "(exhausted)"
        return {"ok": True, "model_id": model_id, "provider": "fake",
                "text": text, "mock": True, "ts": time.time()}


@pytest.fixture(autouse=True)
def _isolate(reset_stores, monkeypatch):
    memory_vault._reset_for_tests()
    if hasattr(markov_states_store, "_reset_memory_for_tests"):
        markov_states_store._reset_memory_for_tests()
    monkeypatch.setattr(mr, "route_request", FakeRouter([REPLY, REPLY, REPLY]))
    yield


@pytest.fixture
def client():
    return TestClient(_app.app)


def _member(username: str = "writer@example.com"):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    users_store.set_membership(username, tier="founding_500", price=50.0, status="active")
    seed_controller(username)   # unlimited on the meter; the route is metered
    # a minted op_ id, as the magic-link path writes: the runtime store's id
    # regex refuses an address, and the conftest wrapper would backfill one
    users_store.update_user(username, {"operator_id": "op_" + secrets.token_urlsafe(12)})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid, "Idempotency-Key": secrets.token_hex(8)}


def _post(client, headers, tid, text):
    h = dict(headers); h["Idempotency-Key"] = secrets.token_hex(8)
    r = client.post(f"/me/threads/{tid}/message", json={"content": text}, headers=h)
    assert r.status_code == 200, r.text
    return r


# --------------------------------------------------------------------------
# #140 B -- one state per turn
# --------------------------------------------------------------------------
def test_one_state_per_turn_index_increments_and_the_readers_answer(client):
    user, h = _member()
    tid = threads_vault.create_thread(user, title="lease")["thread_id"]
    assert client.get(f"/markov/envelope/latest?session_id={tid}", headers=h).status_code == 404  # before: no_state

    r1 = _post(client, h, tid, TEXT_1)
    s1 = markov_states_store.latest_for(user, tid)
    assert s1 is not None and s1["state_index"] == 0
    assert s1["class"] == "markov_state_thread" and isinstance(s1["ts_sealed"], float)
    assert s1["ts_sealed"] == s1["timestamp"]
    v1 = s1["state_vector"]
    assert len(v1) == len(dewey_pipeline.embed_text_cached(TEXT_1)) and abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-6
    assert s1["qc_envelope"] == _app._IDENTITY_QC_ENVELOPE

    r2 = _post(client, h, tid, TEXT_2)
    s2 = markov_states_store.latest_for(user, tid)
    assert s2["state_index"] == 1 and s2["state_vector"] != v1
    assert abs(math.sqrt(sum(x * x for x in s2["state_vector"])) - 1.0) < 1e-6
    # the reply is what the router said, both turns: the write changed no text
    assert r1.json()["assistant_message"]["content"] == REPLY
    assert r2.json()["assistant_message"]["content"] == REPLY

    # #71 -- the MQC cell's read answers now
    r = client.get(f"/markov/envelope/latest?session_id={tid}", headers=h)
    assert r.status_code == 200 and r.json()["state_vector"] == s2["state_vector"]
    assert r.json()["qc_envelope"] == _app._IDENTITY_QC_ENVELOPE
    # and /sessions lists the thread
    r = client.get("/sessions", headers=h)
    assert r.status_code == 200
    rows = {x["session_id"]: x for x in r.json()["sessions"]}
    assert tid in rows and rows[tid]["state_count"] == 2 and rows[tid]["latest_state_index"] == 1
    # the state carries no text
    assert TEXT_1 not in json.dumps(s1) and TEXT_2 not in json.dumps(s2) and REPLY not in json.dumps(s2)


def test_the_two_older_writers_are_untouched(client):
    """The v3 writers pass no `extra`: their docs carry no class / ts_sealed."""
    user, h = _member("older@example.com")
    idx, ts = _app._persist_markov_state(user, "sess-x", [1.0, 0.0], {"qc_stability": 1.0})
    doc = markov_states_store.latest_for(user, "sess-x")
    assert idx == 0 and "class" not in doc and "ts_sealed" not in doc and doc["timestamp"] == ts


def test_a_dimension_change_restarts_the_chain_from_the_observation(client, monkeypatch):
    user, h = _member("dims@example.com")
    tid = threads_vault.create_thread(user, title="d")["thread_id"]
    _post(client, h, tid, TEXT_1)
    n = len(markov_states_store.latest_for(user, tid)["state_vector"])
    monkeypatch.setattr(dewey_pipeline, "embed_text_cached", lambda text: [1.0] + [0.0] * n)  # n+1 dims
    _post(client, h, tid, TEXT_2)
    s = markov_states_store.latest_for(user, tid)
    assert s["state_index"] == 1 and len(s["state_vector"]) == n + 1 and s["state_vector"][0] == 1.0


def test_a_write_failure_is_a_warning_and_the_reply_is_unchanged(client, monkeypatch, caplog):
    user, h = _member("ab@x.io")   # a short address: the line must carry a hash, not a prefix
    tid = threads_vault.create_thread(user, title="w")["thread_id"]

    def boom(text):
        raise RuntimeError("vertex down " + text + " ab@x.io")

    monkeypatch.setattr(dewey_pipeline, "embed_text_cached", boom)
    caplog.set_level(logging.WARNING, logger="clarityos")
    r = _post(client, h, tid, TEXT_1)
    assert r.json()["assistant_message"]["content"] == REPLY
    assert markov_states_store.latest_for(user, tid) is None
    lines = [rec.getMessage() for rec in caplog.records if rec.getMessage().startswith("markov write FAILED")]
    assert len(lines) == 1, [rec.getMessage() for rec in caplog.records]
    line = lines[0]
    assert line == f"markov write FAILED user={users_store._uref(user)} thread={runtime_privacy.session_ref(tid)} err=RuntimeError"
    assert "@" not in line and "vertex" not in line and TEXT_1 not in line and tid not in line


def test_the_write_log_line_carries_index_and_qc_keys_only(client, caplog):
    user, h = _member("log@example.com")
    tid = threads_vault.create_thread(user, title="l")["thread_id"]
    caplog.set_level(logging.INFO, logger="clarityos")   # app.py logs as "clarityos"; conftest pins it WARNING
    _post(client, h, tid, TEXT_1)
    lines = [rec.getMessage() for rec in caplog.records if rec.getMessage().startswith("markov write user=")]
    assert len(lines) == 1
    line = lines[0]
    assert "state_index=0" in line and "qc_keys=['qc_drift', 'qc_predictive', 'qc_pressure', 'qc_stability']" in line
    assert "dim_reset=False" in line and "@" not in line and TEXT_1 not in line and "1.0" not in line


# --------------------------------------------------------------------------
# #191 -- the login row
# --------------------------------------------------------------------------
def _login(email: str) -> dict:
    box: dict = {}
    am.EMAIL_SENDER = lambda e, link, ctx: box.__setitem__("link", link) or True
    am.request_magic_link(email, "test", "app", f"ip-{email}", "ua")
    token = box["link"].split("token=", 1)[1]
    r = am.verify_magic_link(token, f"ip-{email}", "ua")
    assert r["status"] == "ok", r
    return r


def test_a_login_writes_one_durable_row_and_the_history_route_lists_a_ref(client):
    r = _login("first@example.com")
    sid = r["session_id"]
    assert r["member_number"] == 1
    entries = memory_vault.vault_list("first@example.com")
    keys = [k for k in entries if k.startswith("session_records.")]
    # the sub-key is a HASH of the id: a vault key is plaintext at rest and the
    # founder inspector lists raw keys -- a raw id there would be a live token
    assert keys == [f"session_records.{am.login_record_ref(sid)}"]
    assert sid not in keys[0] and sid[:8] not in keys[0] and len(am.login_record_ref(sid)) == 16
    row = entries[keys[0]]
    assert row == {"class": "session_login", "member_number": 1,
                   "operator_id": users_store.get_user("first@example.com")["operator_id"],
                   "ts_sealed": row["ts_sealed"], "turn": 0}
    assert isinstance(row["ts_sealed"], float)

    h = {"X-Session-ID": sid}
    body = client.get("/operator/sessions", headers=h).json()
    assert set(body) == {"operator_id", "sessions", "login_sessions"}
    assert body["sessions"] == []                      # runtime_persistence: nothing yet
    assert len(body["login_sessions"]) == 1
    login = body["login_sessions"][0]
    assert set(login) == {"session_ref", "current", "member_number", "operator_id", "ts_sealed", "turn"}
    assert login["session_ref"] == am.login_record_ref(sid) and login["current"] is True
    assert login["member_number"] == 1 and login["turn"] == 0 and login["operator_id"] == body["operator_id"]
    # the id is a bearer token: the wire carries the hash, never the id nor a prefix of it
    assert sid not in json.dumps(body) and sid[:8] not in json.dumps(body)


def test_two_logins_are_two_rows_newest_first_and_only_the_asking_one_is_current(client):
    a = _login("twice@example.com")["session_id"]
    time.sleep(0.01)
    b = _login("twice@example.com")["session_id"]
    body = client.get("/operator/sessions", headers={"X-Session-ID": a}).json()
    refs = [(x["session_ref"], x["current"]) for x in body["login_sessions"]]
    assert refs == [(am.login_record_ref(b), False), (am.login_record_ref(a), True)]
    assert all(x["member_number"] == 1 for x in body["login_sessions"])


def test_a_login_row_failure_is_a_warning_and_the_login_stands(monkeypatch, caplog):
    def boom(user, key, value):
        raise RuntimeError("vault down first@example.com")

    monkeypatch.setattr(memory_vault, "vault_put", boom)
    caplog.set_level(logging.WARNING, logger="clarityos.auth_magiclink")
    r = _login("nowrite@example.com")
    assert sessions_store.get_session(r["session_id"]) is not None
    lines = [rec.getMessage() for rec in caplog.records if "session_record.write_failed" in rec.getMessage()]
    assert len(lines) == 1
    assert "err=RuntimeError" in lines[0] and "@" not in lines[0] and "vault down" not in lines[0]
    assert "nowrite" not in lines[0]


def test_the_history_route_still_401s_without_a_session_and_serves_an_empty_pair(client):
    assert client.get("/operator/sessions").status_code == 401
    user, h = _member("empty@example.com")
    body = client.get("/operator/sessions", headers=h).json()
    assert body["sessions"] == [] and body["login_sessions"] == []   # the page reads "no prior sessions" only now


def test_another_members_login_rows_never_cross(client):
    _login("one@example.com")
    two = _login("two@example.com")["session_id"]
    body = client.get("/operator/sessions", headers={"X-Session-ID": two}).json()
    assert len(body["login_sessions"]) == 1 and body["login_sessions"][0]["current"] is True


def test_a_malformed_stamp_is_served_absent_not_a_500(client):
    sid = _login("stamp@example.com")["session_id"]
    memory_vault.vault_put("stamp@example.com", "session_records.deadbeefdeadbeef",
                           {"class": "session_login", "member_number": 1, "ts_sealed": "not-a-number", "turn": 0})
    body = client.get("/operator/sessions", headers={"X-Session-ID": sid}).json()
    assert len(body["login_sessions"]) == 2
    bad = [x for x in body["login_sessions"] if x["session_ref"] == "deadbeefdeadbeef"][0]
    assert bad["ts_sealed"] is None and bad["current"] is False


def test_drift_guards():
    assert "session_records" in memory_vault.ALLOWED_NAMESPACES
    assert rh.LOGIN_RECORD_PREFIX == am.LOGIN_RECORD_PREFIX == "session_records."
    assert _app.MARKOV_THREAD_STATE_CLASS == "markov_state_thread"
