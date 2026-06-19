"""D1 patch tests — membership gate + transactional credit debit.

Assumes CLARITYOS_BACKEND=memory (non-atomic fallback path) for unit speed;
concurrency/atomicity is covered separately against a Firestore emulator.
Harness-wired APPLIED form (D1-APPLY-01.AMEND.1 §3): _mk_session parameterized
to the repo helpers, conftest.TestClient (httpx>=0.28-compat), reset_stores
isolation + _MEMORY_DEBITS clear, @skip removed. Each test maps to brief §5.
"""
import os
import uuid
import time
import secrets
import pytest

os.environ.setdefault("CLARITYOS_BACKEND", "memory")

import bcrypt                          # noqa: E402
from conftest import TestClient        # noqa: E402  AppClient (httpx>=0.28 compat), NOT fastapi.testclient
import app as appmod                   # noqa: E402
import users_store                     # noqa: E402
import sessions_store                  # noqa: E402

client = TestClient(appmod.app)


def _mk_session(user, *, active=True, credits=0, cohort="founder"):
    """Create a user (+ optional active membership + N credits); return a session id.
    Wired to repo helpers per D1-APPLY-01.AMEND.1 §3.1 (mirrors test_v30_membership._make_user)."""
    users_store.create_user(
        username=user,
        password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
        salt="",
        tier="free",
        created_at=time.time(),
    )
    users_store.update_user(user, {"cohort": cohort})  # g_credits_enabled is founder-cohort gated
    if active:
        users_store.set_membership(user, tier="founding", price=50.0, status="active")
    if credits:
        users_store.add_g_credits(user, credits)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return sid


def _hdr(session_id, idem=None):
    h = {"X-Session-ID": session_id}
    if idem:
        h["Idempotency-Key"] = idem
    return h


@pytest.fixture(autouse=True)
def _reset(reset_stores):
    """Per-test isolation (§3.4): reset_stores (conftest) wipes users/sessions/etc;
    additionally clear the D1 in-memory debit-idempotency ledger."""
    if hasattr(users_store, "_MEMORY_DEBITS"):
        try:
            users_store._MEMORY_DEBITS.clear()
        except Exception:
            pass
    yield


class TestD1:
    def test_1_inactive_membership_403(self):
        sid = _mk_session("u_inactive", active=False)  # membership not active
        r = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, uuid.uuid4().hex))
        assert r.status_code == 403
        assert r.json()["error"] == "inactive_entitlement"

    def test_2_active_zero_credits_402(self):
        sid = _mk_session("u_zero", active=True, credits=0)  # active membership, 0 credits
        r = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, uuid.uuid4().hex))
        assert r.status_code == 402
        assert r.json()["error"] == "no_credits"

    def test_3_active_with_credits_200_and_debit(self):
        sid = _mk_session("u_ok", active=True, credits=5)  # active, N credits
        before = users_store.get_g_credit_balance("u_ok")
        r = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, uuid.uuid4().hex))
        assert r.status_code == 200
        assert users_store.get_g_credit_balance("u_ok") == before - 1
        assert r.headers.get("X-Remaining-Credits") == str(before - 1)

    def test_4_replay_same_key_no_double_charge(self):
        sid = _mk_session("u_replay", active=True, credits=5)
        key = uuid.uuid4().hex
        client.post("/markov", json={"text": "x"}, headers=_hdr(sid, key))
        mid = users_store.get_g_credit_balance("u_replay")
        client.post("/markov", json={"text": "x"}, headers=_hdr(sid, key))  # replay
        assert users_store.get_g_credit_balance("u_replay") == mid  # unchanged

    def test_5_compute_failure_refunds(self, monkeypatch):
        sid = _mk_session("u_fail", active=True, credits=5)
        before = users_store.get_g_credit_balance("u_fail")
        monkeypatch.setattr(appmod, "markov_adapter",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        r = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, uuid.uuid4().hex))
        assert r.status_code >= 500
        assert users_store.get_g_credit_balance("u_fail") == before  # refunded

    def test_6_missing_idempotency_key_400(self):
        sid = _mk_session("u_nokey", active=True, credits=5)
        r = client.post("/markov", json={"text": "x"}, headers=_hdr(sid))  # no key
        assert r.status_code == 400
        assert r.json()["error"] == "missing_idempotency_key"

    def test_7_tier2_write_membership_only_no_debit(self):
        sid = _mk_session("u_writer", active=True, credits=0)  # active, Tier-2 needs no credits
        before = users_store.get_g_credit_balance("u_writer")
        client.post("/vault/write", json={"key": "k", "value": "v"}, headers=_hdr(sid))
        assert users_store.get_g_credit_balance("u_writer") == before  # no debit on Tier-2


@pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Firestore emulator required: set FIRESTORE_EMULATOR_HOST=host:port",
)
def test_concurrent_same_balance_distinct_keys():
    """Two parallel calls, balance=1, distinct Idempotency-Keys.
    Expected: exactly one 200, exactly one 402, balance never negative.
    Validates Firestore-transactional consume_g_credit_tx atomicity (D1_SPEC.md §4.3).
    Skip-gated on FIRESTORE_EMULATOR_HOST per D1-APPLY-01.AMEND.1 Ruling 2 (Path C)."""
    import threading
    sid = _mk_session("u_conc", active=True, credits=1)
    results = []

    def _call():
        r = client.post("/markov", json={"text": "x"}, headers=_hdr(sid, uuid.uuid4().hex))
        results.append(r.status_code)

    t1 = threading.Thread(target=_call)
    t2 = threading.Thread(target=_call)
    t1.start(); t2.start(); t1.join(); t2.join()
    assert sorted(results) == [200, 402], f"expected one 200 + one 402, got {sorted(results)}"
    assert users_store.get_g_credit_balance("u_conc") == 0  # never negative
