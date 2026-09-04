"""
#23 W2 -- a relationship shows what it saved.

WHAT THESE PIN. The first read-back of a prior store: every run on a
relationship writes a turn record, and GET /me/relationships/{id}/turns is
the first thing that reads one. Ownership first (a foreign thread is 404,
never 403); the records are served RAW and carry no member text; the trust
signal is the module's own three-kind return -- "no_prior_yet" at n=0,
"value" with no "direction" at n=1, never a bare 0.0; the window belongs
to the reader.
"""
from __future__ import annotations

import json
import secrets
import time

import pytest

from conftest import TestClient

import memory_vault
import sessions_store
import threads_vault
import turn_record as tr
import users_store

import app as _app


@pytest.fixture(autouse=True)
def _clean(reset_stores):
    memory_vault._reset_for_tests()
    tr._reset_seq_for_tests()
    yield


@pytest.fixture
def client():
    return TestClient(_app.app)


def _session(username: str = "member_a"):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    # active founding member on the legacy string: the flags re-arm for it
    users_store.update_user(username, {
        "cohort": "founding_500", "membership_status": "active",
        "membership_tier": "founding_500",
    })
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid}


def _relationship(user: str, title: str = "Copilot-me-system_install") -> str:
    return threads_vault.create_thread(user, title, project_id="relationships")["thread_id"]


def _run(client, headers, thread_id: str, text: str):
    """One run on the relationship through the deterministic route (no
    vendor behind /elins/v2/run); the hook records the turn first."""
    r = client.post(
        "/elins/v2/run",
        json={"region": None, "input": {"raw_text": text}, "thread_id": thread_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    return r


# --------------------------------------------------------------------------
# ownership
# --------------------------------------------------------------------------
def test_a_foreign_thread_is_404_not_403(client):
    owner, _ = _session("owner_x")
    tid = _relationship(owner)
    _, other = _session("other_y")
    r = client.get(f"/me/relationships/{tid}/turns", headers=other)
    assert r.status_code == 404
    assert r.status_code != 403


def test_an_unknown_thread_is_404_and_no_session_is_401(client):
    _, h = _session()
    assert client.get("/me/relationships/no-such-thread/turns", headers=h).status_code == 404
    assert client.get("/me/relationships/no-such-thread/turns").status_code == 401


# --------------------------------------------------------------------------
# n = 0 -- a different kind of thing, never a number
# --------------------------------------------------------------------------
def test_an_empty_relationship_has_turn_count_0_and_no_prior_yet(client):
    user, h = _session()
    tid = _relationship(user)
    body = client.get(f"/me/relationships/{tid}/turns", headers=h).json()
    assert body["thread_id"] == tid
    assert body["turn_count"] == 0 and body["turns"] == []
    sig = body["trust_signal"]
    assert sig["status"] == "no_prior_yet"
    assert "value" not in sig and "direction" not in sig
    assert not isinstance(sig.get("value"), (int, float))
    assert sig["theta_floor"] == tr.THETA_FLOOR_TURNS


# --------------------------------------------------------------------------
# two runs -> two turns; the second observed the first's seal
# --------------------------------------------------------------------------
def test_two_runs_make_two_turns_and_the_second_observes_the_first(client):
    user, h = _session()
    tid = _relationship(user)
    _run(client, h, tid, "The ridge is contested and the pressure is rising.")
    _run(client, h, tid, "The ridge is held today and the pressure eased.")
    body = client.get(f"/me/relationships/{tid}/turns", headers=h).json()
    assert body["turn_count"] == 2 and len(body["turns"]) == 2
    first, second = body["turns"]
    assert first["turn_index"] == 0 and second["turn_index"] == 1
    # the second run OBSERVED the first's seal: ts_observed landed on turn 0
    assert first["ts_sealed"] and first["ts_observed"] is not None
    assert first["observation"] is not None
    # the newest turn is sealed and waiting for a return it has not seen
    assert second["ts_observed"] is None and second["observation"] is None
    # one scored turn: a value or undefined, and NO direction (two points needed)
    sig = body["trust_signal"]
    assert sig["status"] in ("value", "undefined")
    assert "direction" not in sig


def test_a_run_without_a_thread_id_records_nothing(client):
    user, h = _session()
    tid = _relationship(user)
    r = client.post("/elins/v2/run", json={"region": None, "input": {"raw_text": "no relationship named"}},
                    headers=h)
    assert r.status_code == 200
    assert client.get(f"/me/relationships/{tid}/turns", headers=h).json()["turn_count"] == 0


# --------------------------------------------------------------------------
# n = 1 -- a value, no direction
# --------------------------------------------------------------------------
def test_one_scored_turn_gives_a_value_and_no_direction_key(client):
    user, h = _session()
    tid = _relationship(user)
    k = tr.seal_expectation(user, tid, 0, {"boundary": "clear"})
    tr.observe_return(user, k, {"boundary": "clear"})
    sig = client.get(f"/me/relationships/{tid}/turns", headers=h).json()["trust_signal"]
    assert sig["status"] == "value" and sig["value"] == 1.0
    assert "direction" not in sig


def test_two_scored_turns_give_a_direction(client):
    user, h = _session()
    tid = _relationship(user)
    k1 = tr.seal_expectation(user, tid, 0, {"boundary": "clear"})
    tr.observe_return(user, k1, {"boundary": "clear"})
    k2 = tr.seal_expectation(user, tid, 1, {"boundary": "clear"})
    tr.observe_return(user, k2, {"boundary": "soft"})
    sig = client.get(f"/me/relationships/{tid}/turns", headers=h).json()["trust_signal"]
    assert sig["status"] == "value" and sig["direction"] == "falling"


# --------------------------------------------------------------------------
# the window is the reader's
# --------------------------------------------------------------------------
def test_window_slices_the_turns_but_not_the_count(client):
    user, h = _session()
    tid = _relationship(user)
    for i in range(3):
        _run(client, h, tid, f"turn number {i} on the ridge.")
    body = client.get(f"/me/relationships/{tid}/turns?window=2", headers=h).json()
    assert body["turn_count"] == 3
    assert [t["turn_index"] for t in body["turns"]] == [1, 2]
    assert client.get(f"/me/relationships/{tid}/turns?window=0", headers=h).status_code == 422


# --------------------------------------------------------------------------
# privacy -- the records carry no member text
# --------------------------------------------------------------------------
def test_the_payload_carries_no_member_text(client):
    user, h = _session()
    tid = _relationship(user)
    marker = "MARKER-4b1e-the-member-wrote-this"
    _run(client, h, tid, f"{marker} and the pressure is rising.")
    _run(client, h, tid, f"{marker} again, the ridge held.")
    dumped = json.dumps(client.get(f"/me/relationships/{tid}/turns", headers=h).json())
    assert marker not in dumped
    assert "MARKER" not in dumped
