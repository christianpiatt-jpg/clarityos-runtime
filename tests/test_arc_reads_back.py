"""
#163 / #33 -- the arc reads back: enums only, loudly.

WHAT THESE PIN. The felt-gap reader's record carries labels and a seq and
NO text (the two v0.1 text keys are gone from the builder; a drift guard
pins the key tuple); made_turn is the assistant_seq the arc was made on;
a reader step that fails is named at WARNING with refs and a type name --
never the text, never an address -- and the member's turn completes;
GET /me/relationships/{thread_id}/arc serves the rows enums-only after the
ownership gate (a foreign thread is 404, never 403), strips a v0.1 row's
text server-side and backfills its made_turn, carries now_turn in TURNS,
and says why it is ABSENT (flag off / no pair yet). The flag is read,
never set: these tests set the process env, not the service.
"""
from __future__ import annotations

import json
import logging
import secrets
import time

import pytest

from conftest import TestClient

import felt_gap_reader as fgr
import intelligence_kernel as ik
import memory_vault
import model_router as mr
import sessions_store
import threads_vault
import users_store

import app as _app

LOGGER = "clarityos.intelligence_kernel"
FLAG = "CLARITYOS_FELT_GAP_READER_ENABLED"
PROMPT_1 = "Which clause of the lease governs the deposit?"
REPLY_1 = "Clause 4 governs the deposit; it is refundable within thirty days."
PROMPT_2 = "no, that's wrong -- clause 7 is the deposit clause"
REPLY_2 = "You are right: clause 7 governs the deposit."


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
    monkeypatch.delenv("CLARITYOS_FELT_GAP_ALLOWLIST", raising=False)
    yield


@pytest.fixture
def client():
    return TestClient(_app.app)


def _session(username: str = "member_arc"):
    import bcrypt
    users_store.create_user(
        username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="", tier="free", created_at=time.time(),
    )
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid}


def _two_turns(monkeypatch, user: str) -> str:
    """Two member turns on one thread: after the second, the prior pair
    (seq 0/1) is completable and the reader seals one arc on seq 1."""
    monkeypatch.setattr(mr, "route_request", FakeRouter([REPLY_1, REPLY_2]))
    tid = threads_vault.create_thread(user, title="lease")["thread_id"]
    ik.run_thread_message(user, tid, PROMPT_1)
    ik.run_thread_message(user, tid, PROMPT_2)
    return tid


# --------------------------------------------------------------------------
# the record
# --------------------------------------------------------------------------
def test_the_record_carries_no_text_and_made_turn_is_the_seq():
    rec = fgr.build_arc_record(
        user_id="u", thread_id="t", assistant_seq=7,
        user_prompt_text=PROMPT_1, assistant_reply_text=REPLY_1,
        user_next_reply_text=PROMPT_2, user_next_reply_present=True,
    )
    assert set(rec) == set(fgr.ARC_RECORD_KEYS)
    assert "e_t_user_prompt" not in rec and "y_t_assistant_reply" not in rec
    blob = json.dumps(rec)
    for text in (PROMPT_1, REPLY_1, PROMPT_2, "clause", "deposit"):
        assert text not in blob
    assert rec["class"] == "arc_record"
    assert rec["made_turn"] == 7 and rec["assistant_seq"] == 7
    assert rec["correction_type"] == "correct" and rec["felt_gap"] == "misaligned" and rec["confidence"] == "dropped"
    assert rec["reader_version"] == fgr.READER_VERSION == "v0.2_enums_only"
    assert isinstance(rec["ts_sealed"], float) and rec["ts_sealed"] > 0


def test_drift_guard_no_key_names_text_and_the_route_serves_a_subset():
    for k in fgr.ARC_RECORD_KEYS:
        assert not any(w in k for w in ("text", "prompt", "reply_text", "e_t_", "y_t_")), k
    assert set(_app._ARC_ROW_KEYS) <= set(fgr.ARC_RECORD_KEYS)
    assert "made_turn" in _app._ARC_ROW_KEYS and "assistant_seq" in _app._ARC_ROW_KEYS
    assert _app._ARC_RECORD_PREFIX == ik._ARC_RECORD_PREFIX == "arc_records."


# --------------------------------------------------------------------------
# the seam: sealed on the second turn, enums only in the vault
# --------------------------------------------------------------------------
def test_the_second_turn_seals_one_enums_only_arc_on_the_prior_pair(monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    user = "arc_writer"
    tid = _two_turns(monkeypatch, user)
    entries = memory_vault.vault_list(user)
    keys = sorted(k for k in entries if k.startswith(f"arc_records.{tid}."))
    assert keys == [f"arc_records.{tid}.000001"]
    row = entries[keys[0]]
    assert set(row) == set(fgr.ARC_RECORD_KEYS)
    assert row["made_turn"] == 1 and row["correction_type"] == "correct"
    assert PROMPT_1 not in json.dumps(row) and REPLY_1 not in json.dumps(row)


def test_flag_off_seals_nothing(monkeypatch):
    monkeypatch.setenv(FLAG, "0")
    user = "arc_off"
    tid = _two_turns(monkeypatch, user)
    assert not [k for k in memory_vault.vault_list(user) if k.startswith(f"arc_records.{tid}.")]


# --------------------------------------------------------------------------
# #33 -- a failed step is named at WARNING; the turn completes
# --------------------------------------------------------------------------
@pytest.mark.parametrize("target,step", [
    ("_lookup_prior_completable_pair", "lookup_prior_completable_pair"),
    ("build_arc_record", "build_arc_record"),
    ("_write_arc_record", "write_arc_record"),
])
def test_a_failed_step_is_named_at_warning_and_the_turn_completes(monkeypatch, caplog, target, step):
    monkeypatch.setenv(FLAG, "1")
    real_lookup = ik._lookup_prior_completable_pair
    # a SHORT local part: an 8-char prefix of this address would be the
    # whole address, so the line must carry a hash, not a prefix
    user = "ab@x.io"

    def boom(*a, **k):
        # the lookup runs on the FIRST turn too (and finds no pair): only
        # fail it once the pair is completable, so exactly one step fails
        if target == "_lookup_prior_completable_pair" and real_lookup(*a, **k) is None:
            return None
        raise RuntimeError("boom " + PROMPT_2 + " " + user)

    monkeypatch.setattr(fgr if target == "build_arc_record" else ik, target, boom)
    caplog.set_level(logging.WARNING, logger=LOGGER)
    monkeypatch.setattr(mr, "route_request", FakeRouter([REPLY_1, REPLY_2]))
    tid = threads_vault.create_thread(user, title="lease")["thread_id"]
    ik.run_thread_message(user, tid, PROMPT_1)
    out = ik.run_thread_message(user, tid, PROMPT_2)          # the turn completes
    assert out["assistant_message"]["content"] == REPLY_2
    lines = [r.getMessage() for r in caplog.records
             if r.levelno == logging.WARNING and r.getMessage().startswith("felt_gap_reader step=")]
    assert len(lines) == 1, lines
    line = lines[0]
    assert line.startswith(f"felt_gap_reader step={step} skipped user=")
    assert " thread=" in line and line.endswith(" err=RuntimeError")
    # refs and a type name only: never the text, never the address, never the message
    assert "boom" not in line and PROMPT_2 not in line and user not in line
    assert "@" not in line and "x.io" not in line and "ab@" not in line and tid not in line
    assert users_store._uref(user) in line
    assert not [k for k in memory_vault.vault_list(user) if k.startswith(f"arc_records.{tid}.")]


def test_a_step_failure_on_get_thread_is_named(monkeypatch, caplog):
    monkeypatch.setenv(FLAG, "1")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    real = threads_vault.get_thread
    state = {"calls": 0}

    def flaky(user_id, thread_id):
        state["calls"] += 1
        raise KeyError("gone")

    monkeypatch.setattr(ik.threads_vault, "get_thread", flaky)
    caplog.clear()
    ik._run_felt_gap_reader("arc_w2", "thread-x", PROMPT_2)
    monkeypatch.setattr(ik.threads_vault, "get_thread", real)
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("felt_gap_reader step=")]
    assert lines == [f"felt_gap_reader step=get_thread skipped user={users_store._uref('arc_w2')} "
                     f"thread={ik.runtime_privacy.session_ref('thread-x')} err=KeyError"]


def test_the_first_exchange_has_no_pair_and_logs_nothing(monkeypatch, caplog):
    monkeypatch.setenv(FLAG, "1")
    caplog.set_level(logging.WARNING, logger=LOGGER)
    user = "arc_first"
    monkeypatch.setattr(mr, "route_request", FakeRouter([REPLY_1]))
    tid = threads_vault.create_thread(user, title="lease")["thread_id"]
    ik.run_thread_message(user, tid, PROMPT_1)
    assert not [r for r in caplog.records if "felt_gap_reader" in r.getMessage()]
    assert not [k for k in memory_vault.vault_list(user) if k.startswith("arc_records.")]


# --------------------------------------------------------------------------
# the route
# --------------------------------------------------------------------------
def test_arc_route_serves_enums_only_with_made_turn_and_now_turn(monkeypatch, client):
    monkeypatch.setenv(FLAG, "1")
    user, h = _session("member_arc")
    tid = _two_turns(monkeypatch, user)
    r = client.get(f"/me/relationships/{tid}/arc", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"thread_id", "arc_count", "arcs", "now_turn", "reader", "reader_reason"}
    assert body["thread_id"] == tid and body["arc_count"] == 1
    assert body["reader"] == "PRESENT" and body["reader_reason"] is None
    assert body["now_turn"] == 3                     # four messages: the last index, in TURNS
    row = body["arcs"][0]
    assert set(row) == set(_app._ARC_ROW_KEYS)
    assert row["made_turn"] == 1 and row["assistant_seq"] == 1
    assert row["correction_type"] == "correct" and row["felt_gap"] == "misaligned" and row["confidence"] == "dropped"
    assert row["user_next_reply_present"] is True and row["reader_version"] == "v0.2_enums_only"
    for text in (PROMPT_1, REPLY_1, PROMPT_2, REPLY_2, "clause", "deposit"):
        assert text not in r.text


def test_a_v01_row_is_stripped_server_side_and_made_turn_backfilled(monkeypatch, client):
    monkeypatch.setenv(FLAG, "1")
    user, h = _session("member_old")
    tid = threads_vault.create_thread(user, title="old")["thread_id"]
    memory_vault.vault_init(user)
    memory_vault.vault_put(user, f"arc_records.{tid}.000003", {
        "e_t_user_prompt": PROMPT_1, "y_t_assistant_reply": REPLY_1,
        "correction_type": "accept", "felt_gap": "aligned", "confidence": "held",
        "delta_m": None, "arc": None, "reader_version": "v0.1_phase1_first_cut",
        "assistant_seq": 3, "user_next_reply_present": True,
    })
    r = client.get(f"/me/relationships/{tid}/arc", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["arc_count"] == 1 and body["reader"] == "PRESENT"
    row = body["arcs"][0]
    assert "e_t_user_prompt" not in row and "y_t_assistant_reply" not in row
    assert row["made_turn"] == 3 and row["assistant_seq"] == 3
    assert row["reader_version"] == "v0.1_phase1_first_cut" and "ts_sealed" not in row
    assert body["now_turn"] is None                  # an empty thread has no turn yet
    assert PROMPT_1 not in r.text and REPLY_1 not in r.text


def test_rows_are_sorted_by_seq(monkeypatch, client):
    monkeypatch.setenv(FLAG, "1")
    user, h = _session("member_sort")
    tid = threads_vault.create_thread(user, title="s")["thread_id"]
    memory_vault.vault_init(user)
    for seq in (11, 3, 7):
        memory_vault.vault_put(user, f"arc_records.{tid}.{seq:06d}",
                               {"correction_type": "accept", "assistant_seq": seq, "made_turn": seq})
    body = client.get(f"/me/relationships/{tid}/arc", headers=h).json()
    assert [a["made_turn"] for a in body["arcs"]] == [3, 7, 11]


def test_absent_reasons(monkeypatch, client):
    user, h = _session("member_absent")
    tid = threads_vault.create_thread(user, title="a")["thread_id"]
    monkeypatch.setenv(FLAG, "0")
    body = client.get(f"/me/relationships/{tid}/arc", headers=h).json()
    assert body["arc_count"] == 0 and body["arcs"] == []
    assert body["reader"] == "ABSENT" and body["reader_reason"] == "reader flag off"
    monkeypatch.setenv(FLAG, "1")
    body = client.get(f"/me/relationships/{tid}/arc", headers=h).json()
    assert body["reader"] == "ABSENT" and body["reader_reason"] == "no completable pair yet"
    assert body != {}


def test_ownership_first_foreign_404_unknown_404_no_session_401(monkeypatch, client):
    monkeypatch.setenv(FLAG, "1")
    owner, _ = _session("owner_arc")
    tid = threads_vault.create_thread(owner, title="mine")["thread_id"]
    _, other = _session("other_arc")
    r = client.get(f"/me/relationships/{tid}/arc", headers=other)
    assert r.status_code == 404 and r.status_code != 403
    assert client.get("/me/relationships/no-such-thread/arc", headers=other).status_code == 404
    assert client.get(f"/me/relationships/{tid}/arc").status_code == 401
    assert client.get("/me/relationships/bad.id/arc", headers=other).status_code == 400


def test_another_members_rows_never_leak_across_the_gate(monkeypatch, client):
    """The list is per member (the vault is per member); a same-named key in
    another vault is not this member's arc."""
    monkeypatch.setenv(FLAG, "1")
    a, ha = _session("member_a_arc")
    b, hb = _session("member_b_arc")
    tid = threads_vault.create_thread(a, title="a")["thread_id"]
    memory_vault.vault_init(b)
    memory_vault.vault_put(b, f"arc_records.{tid}.000001", {"correction_type": "accept", "assistant_seq": 1})
    body = client.get(f"/me/relationships/{tid}/arc", headers=ha).json()
    assert body["arc_count"] == 0
    assert client.get(f"/me/relationships/{tid}/arc", headers=hb).status_code == 404
