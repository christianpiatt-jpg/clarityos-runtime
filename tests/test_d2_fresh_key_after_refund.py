"""D2 patch tests — Idempotency-Key terminality (R5 / D2_SPEC v1.0 RATIFIED).

Scope A: ``consume_g_credit_tx`` terminality only. A refunded debit is terminal —
its ``request_id`` may never re-charge, and a fresh key after a refund must
still succeed. ``metered_compute`` surfaces the terminal replay as HTTP 409
``idempotency_key_terminal`` with the ``X-Remaining-Credits`` header preserved.

Backend: ``CLARITYOS_BACKEND=memory`` (non-atomic fallback) for unit speed,
matching tests/test_d1_entitlement_credit.py. The Firestore transactional path
is covered by the emulator-gated D2-T7 (skipif ``FIRESTORE_EMULATOR_HOST``),
mirroring the D1 suite's concurrency test.

Maps to D2_SPEC §7 (D2-T1…T7) and invariants §3:
  I1 — a refunded debit is terminal (same request_id never re-charges)
  I2 — a fresh Idempotency-Key after a refund succeeds (no key blocklist)
  I3 — double-refund on the same key is a no-op (regression guard)
"""
import os
import time
import secrets
import uuid

import pytest

os.environ.setdefault("CLARITYOS_BACKEND", "memory")

import bcrypt                          # noqa: E402
from conftest import TestClient        # noqa: E402  AppClient (httpx>=0.28 compat)
import app as appmod                   # noqa: E402
import users_store                     # noqa: E402
import sessions_store                  # noqa: E402

client = TestClient(appmod.app)


# ---------------------------------------------------------------------------
# Helpers — mirror tests/test_d1_entitlement_credit.py::_mk_session
# ---------------------------------------------------------------------------
def _mk_user(user, *, credits=5, cohort="founder", active=True):
    """Create a user (+ optional active membership + N credits); return username."""
    users_store.create_user(
        username=user,
        password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="",
        tier="free",
        created_at=time.time(),
    )
    users_store.update_user(user, {"cohort": cohort})  # g_credits is founder-cohort gated
    if active:
        users_store.set_membership(user, tier="founding", price=50.0, status="active")
    if credits:
        users_store.add_g_credits(user, credits)
    return user


def _session_for(user):
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return sid


def _hdr(session_id, idem):
    return {"X-Session-ID": session_id, "Idempotency-Key": idem}


@pytest.fixture(autouse=True)
def _reset(reset_stores):
    """Per-test isolation: reset_stores (conftest) wipes users/sessions/etc;
    additionally clear the in-memory debit-idempotency ledger (mirrors D1)."""
    if hasattr(users_store, "_MEMORY_DEBITS"):
        try:
            users_store._MEMORY_DEBITS.clear()
        except Exception:
            pass
    yield


# ---------------------------------------------------------------------------
# D2-T1…T4 — in-memory unit coverage of consume_g_credit_tx terminality
# ---------------------------------------------------------------------------
def test_same_key_after_refund_is_terminal_no_op():
    """D2-T1 / I1 — a refunded debit is terminal; its key never re-charges."""
    user = _mk_user("d2_t1", credits=5)
    key = uuid.uuid4().hex

    first = users_store.consume_g_credit_tx(user, key)
    assert first == {"remaining": 4, "replay": False, "terminal": False}

    users_store.refund_g_credit_tx(user, key)
    assert users_store.get_g_credit_balance(user) == 5  # credit returned

    replay = users_store.consume_g_credit_tx(user, key)
    assert replay["replay"] is True
    assert replay["terminal"] is True
    assert replay["remaining"] == 5                      # reported balance, no re-charge
    assert users_store.get_g_credit_balance(user) == 5   # balance unchanged


def test_new_key_after_refund_does_charge():
    """D2-T2 / I2 — a fresh Idempotency-Key after a refund charges normally."""
    user = _mk_user("d2_t2", credits=5)
    k1 = uuid.uuid4().hex
    users_store.consume_g_credit_tx(user, k1)        # 5 -> 4
    users_store.refund_g_credit_tx(user, k1)         # 4 -> 5
    assert users_store.get_g_credit_balance(user) == 5

    k2 = uuid.uuid4().hex
    fresh = users_store.consume_g_credit_tx(user, k2)
    assert fresh == {"remaining": 4, "replay": False, "terminal": False}
    assert users_store.get_g_credit_balance(user) == 4


def test_refunded_then_replay_then_new_key_sequence():
    """D2-T3 — full lifecycle: charge -> refund -> terminal replay -> fresh charge."""
    user = _mk_user("d2_t3", credits=10)
    k1 = uuid.uuid4().hex

    assert users_store.consume_g_credit_tx(user, k1)["terminal"] is False  # 10 -> 9
    assert users_store.get_g_credit_balance(user) == 9

    users_store.refund_g_credit_tx(user, k1)                               # 9 -> 10
    assert users_store.get_g_credit_balance(user) == 10

    replay = users_store.consume_g_credit_tx(user, k1)                     # terminal no-op
    assert replay["replay"] is True and replay["terminal"] is True
    assert users_store.get_g_credit_balance(user) == 10

    k2 = uuid.uuid4().hex
    fresh = users_store.consume_g_credit_tx(user, k2)                      # 10 -> 9
    assert fresh["replay"] is False and fresh["terminal"] is False
    assert users_store.get_g_credit_balance(user) == 9


def test_double_refund_same_key_is_no_op():
    """D2-T4 / I3 — refunding the same key twice credits once; key stays terminal."""
    user = _mk_user("d2_t4", credits=5)
    key = uuid.uuid4().hex
    users_store.consume_g_credit_tx(user, key)       # 5 -> 4
    users_store.refund_g_credit_tx(user, key)        # 4 -> 5
    users_store.refund_g_credit_tx(user, key)        # no-op (already refunded)
    assert users_store.get_g_credit_balance(user) == 5  # not double-credited (would be 6)

    replay = users_store.consume_g_credit_tx(user, key)
    assert replay["terminal"] is True
    assert users_store.get_g_credit_balance(user) == 5


# ---------------------------------------------------------------------------
# D2-T5…T6 — HTTP-level coverage via /markov (a metered_compute route)
# ---------------------------------------------------------------------------
def test_terminal_replay_returns_409_idempotency_key_terminal():
    """D2-T5 / R5 — replay of a refunded key returns 409 idempotency_key_terminal
    with the X-Remaining-Credits header preserved (D2_SPEC §9-Q1 resolution)."""
    user = _mk_user("d2_t5", credits=5)
    sid = _session_for(user)
    key = uuid.uuid4().hex

    r1 = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, key))
    assert r1.status_code == 200
    assert users_store.get_g_credit_balance(user) == 4

    users_store.refund_g_credit_tx(user, key)        # 4 -> 5; key now terminal
    assert users_store.get_g_credit_balance(user) == 5

    r2 = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, key))
    assert r2.status_code == 409
    assert r2.json()["error"] == "idempotency_key_terminal"
    assert r2.headers.get("X-Remaining-Credits") == "5"   # header survives the 409
    assert users_store.get_g_credit_balance(user) == 5    # no re-charge


def test_replay_active_charge_still_no_op_200():
    """D2-T6 — replaying a still-charged (not refunded) key is the existing
    idempotent no-op: 200, no second charge, terminal path not triggered."""
    user = _mk_user("d2_t6", credits=5)
    sid = _session_for(user)
    key = uuid.uuid4().hex

    r1 = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, key))
    assert r1.status_code == 200
    mid = users_store.get_g_credit_balance(user)     # 4

    r2 = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, key))  # replay
    assert r2.status_code == 200
    assert users_store.get_g_credit_balance(user) == mid          # unchanged, no double charge
    assert r2.headers.get("X-Remaining-Credits") == str(mid)


# ---------------------------------------------------------------------------
# D2-T7 — Firestore transactional terminality (emulator-gated, per rulings doc)
# ---------------------------------------------------------------------------
@pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Firestore emulator required: set FIRESTORE_EMULATOR_HOST=host:port",
)
def test_concurrency_refund_then_same_key_replay_no_double_charge():
    """D2-T7 — after a refund, concurrent replays of the same key are all terminal
    no-ops and the balance is never re-debited. Validates the Firestore
    transactional terminality path (D2_SPEC §6). Skip-gated per the rulings doc."""
    import threading

    user = _mk_user("d2_t7", credits=5)
    key = uuid.uuid4().hex

    users_store.consume_g_credit_tx(user, key)       # 5 -> 4
    users_store.refund_g_credit_tx(user, key)        # 4 -> 5; key terminal
    assert users_store.get_g_credit_balance(user) == 5

    results = []

    def _call():
        results.append(users_store.consume_g_credit_tx(user, key))

    threads = [threading.Thread(target=_call) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(r["terminal"] is True and r["replay"] is True for r in results)
    assert users_store.get_g_credit_balance(user) == 5   # never re-debited
