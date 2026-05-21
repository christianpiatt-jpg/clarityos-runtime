"""
Tests for v30 — Founding Cohort membership + #G credit system.

Covers:
* /membership/state shape + flag gate
* /membership/activate happy path + waitlist when cap is full
* /membership/cancel + price-lock forfeit semantics
* /membership/g/buy_single + buy_pack_20 increment balance
* /elins/g/run consumes one credit per call; 402 on empty balance
* membership_store cap + waitlist invariants
* users_store add/consume_g_credit + balance never negative
"""
from __future__ import annotations

import time

import pytest


@pytest.fixture
def stub_embedder(monkeypatch):
    """Same fake embedder used by v28 tests so #G runs don't hit Vertex."""
    import dewey_pipeline

    def fake_embed(text):
        if not text or not str(text).strip():
            return None
        h = abs(hash(str(text)))
        return [((h >> (i * 4)) & 0xFF) / 255.0 for i in range(8)]

    monkeypatch.setattr(dewey_pipeline, "embed_text_cached", fake_embed)
    monkeypatch.setattr(dewey_pipeline, "embed_text", lambda t: fake_embed(t) or [])
    monkeypatch.setattr(dewey_pipeline, "embed_object", lambda o: fake_embed(str(o)) or [0.0] * 8)
    yield


@pytest.fixture
def app_module(reset_stores, stub_embedder):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(app_module, username, cohort="founder"):
    import secrets, time as _t
    import users_store, sessions_store, bcrypt
    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=_t.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=_t.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ---------------------------------------------------------------------------
# users_store helpers
# ---------------------------------------------------------------------------
def test_g_credit_balance_default_zero(reset_stores):
    import users_store
    users_store.create_user("u1", b"x", "", "free", time.time())
    assert users_store.get_g_credit_balance("u1") == 0


def test_add_g_credits_increments_and_appends_history(reset_stores):
    import users_store
    users_store.create_user("u1", b"x", "", "free", time.time())
    bal = users_store.add_g_credits(
        "u1", 20, history_entry={"type": "g_buy_pack_20", "credits_delta": 20},
    )
    assert bal == 20
    doc = users_store.get_user("u1")
    assert doc["g_credits"] == 20
    assert len(doc["g_credit_history"]) == 1


def test_consume_g_credit_blocks_when_zero(reset_stores):
    import users_store
    users_store.create_user("u1", b"x", "", "free", time.time())
    with pytest.raises(ValueError):
        users_store.consume_g_credit("u1")


def test_consume_g_credit_decrements(reset_stores):
    import users_store
    users_store.create_user("u1", b"x", "", "free", time.time())
    users_store.add_g_credits("u1", 3)
    assert users_store.consume_g_credit("u1") == 2
    assert users_store.consume_g_credit("u1") == 1
    assert users_store.consume_g_credit("u1") == 0
    with pytest.raises(ValueError):
        users_store.consume_g_credit("u1")


# ---------------------------------------------------------------------------
# membership_store
# ---------------------------------------------------------------------------
def test_cohort_state_default(reset_stores):
    import membership_store
    s = membership_store.get_cohort_state()
    assert s["cohort"] == "founding_500"
    assert s["active_count"] == 0
    assert s["cap"] == 500
    assert s["remaining"] == 500
    assert s["is_full"] is False


def test_add_member_idempotent_via_value_error(reset_stores):
    import membership_store
    membership_store.add_member("u1")
    with pytest.raises(ValueError) as exc:
        membership_store.add_member("u1")
    assert str(exc.value) == "already_member"


def test_cohort_full_pushes_to_waitlist(reset_stores, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "FOUNDING_CAP", 2)
    membership_store.add_member("u1")
    membership_store.add_member("u2")
    with pytest.raises(ValueError) as exc:
        membership_store.add_member("u3")
    assert str(exc.value) == "cohort_full"
    membership_store.add_to_waitlist("u3")
    pos = membership_store.waitlist_position("u3")
    assert pos == 1


def test_remove_member_idempotent(reset_stores):
    import membership_store
    membership_store.add_member("u1")
    membership_store.remove_member("u1")
    membership_store.remove_member("u1")  # second call: no-op
    assert membership_store.is_member("u1") is False


def test_record_transaction_caps_at_max(reset_stores, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "MAX_TX_PER_USER", 5)
    for i in range(10):
        membership_store.record_transaction(
            "u1", type="g_consume", amount=0.0, credits_delta=-1,
            metadata={"i": i},
        )
    txs = membership_store.list_transactions("u1", limit=100)
    assert len(txs) == 5
    # The newest five (i=5..9) should remain.
    metadata_indices = sorted(int(t["metadata"]["i"]) for t in txs)
    assert metadata_indices == [5, 6, 7, 8, 9]


# ---------------------------------------------------------------------------
# /membership/state
# ---------------------------------------------------------------------------
def test_membership_state_default_for_founder(app_module, client):
    user, sid = _make_user(app_module, "minnie", cohort="founder")
    r = client.get("/membership/state", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    state = r.json()["state"]
    assert state["membership"]["status"] is None
    assert state["membership"]["next_price"] == 50.00
    assert state["g_credits"]["balance"] == 0
    assert state["cohort"]["active_count"] == 0


def test_membership_state_blocked_when_flag_off(app_module, client):
    user, sid = _make_user(app_module, "ghost", cohort=None)
    r = client.get("/membership/state", headers=_auth(sid))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# /membership/activate
# ---------------------------------------------------------------------------
def test_activate_requires_terms(app_module, client):
    user, sid = _make_user(app_module, "abby", cohort="founder")
    r = client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": False})
    assert r.status_code == 400
    assert r.json()["error"] == "terms_required"


def test_activate_happy_path(app_module, client):
    user, sid = _make_user(app_module, "alex", cohort="founder")
    r = client.post(
        "/membership/activate", headers=_auth(sid), json={"accept_terms": True},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    state = body["state"]
    # v31 — auto-confirm mock mode lands the membership immediately.
    assert state["membership"]["status"] == "active"
    assert state["membership"]["price_locked"] == 50.00
    assert state["cohort"]["active_count"] == 1
    # Intent metadata is part of the new contract.
    assert body["intent"]["mode"] == "mock"
    assert body["intent"]["intent_id"].startswith("pi_")


def test_activate_idempotent_when_already_active(app_module, client):
    user, sid = _make_user(app_module, "ari", cohort="founder")
    client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    r = client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    assert r.status_code == 200
    assert r.json().get("already_active") is True


def test_activate_when_cap_full_returns_waitlist(app_module, client, monkeypatch):
    import membership_store
    monkeypatch.setattr(membership_store, "FOUNDING_CAP", 2)
    u1, sid1 = _make_user(app_module, "first", cohort="founder")
    u2, sid2 = _make_user(app_module, "second", cohort="founder")
    u3, sid3 = _make_user(app_module, "third", cohort="founder")

    assert client.post("/membership/activate", headers=_auth(sid1), json={"accept_terms": True}).status_code == 200
    assert client.post("/membership/activate", headers=_auth(sid2), json={"accept_terms": True}).status_code == 200
    r = client.post("/membership/activate", headers=_auth(sid3), json={"accept_terms": True})
    assert r.status_code == 200
    body = r.json()
    assert body["waitlisted"] is True
    assert body["state"]["waitlist_position"] == 1
    # Cohort active_count never exceeded the cap.
    assert body["state"]["cohort"]["active_count"] == 2


# ---------------------------------------------------------------------------
# /membership/cancel — price-lock forfeit
# ---------------------------------------------------------------------------
def test_cancel_then_state_shows_full_price(app_module, client):
    user, sid = _make_user(app_module, "casey", cohort="founder")
    client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    r = client.post("/membership/cancel", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    state = r.json()["state"]
    assert state["membership"]["status"] == "cancelled"
    # next_price is full price after cancel.
    assert state["membership"]["next_price"] == 150.00
    assert state["membership"]["price_lock_forfeit"] is True
    assert state["cohort"]["active_count"] == 0


def test_reactivate_after_cancel_pays_full_price(app_module, client):
    user, sid = _make_user(app_module, "carla", cohort="founder")
    client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    client.post("/membership/cancel", headers=_auth(sid))
    r = client.post("/membership/activate", headers=_auth(sid), json={"accept_terms": True})
    assert r.status_code == 200, r.json()
    state = r.json()["state"]
    # The lock recorded at reactivation reflects the full price now.
    assert state["membership"]["price_locked"] == 150.00
    assert state["membership"]["status"] == "active"


def test_cancel_when_not_active_rejected(app_module, client):
    user, sid = _make_user(app_module, "noah", cohort="founder")
    r = client.post("/membership/cancel", headers=_auth(sid))
    assert r.status_code == 400
    assert r.json()["error"] == "not_active"


# ---------------------------------------------------------------------------
# #G credit purchases + history
# ---------------------------------------------------------------------------
def test_buy_single_increments_balance(app_module, client):
    user, sid = _make_user(app_module, "barry", cohort="founder")
    r = client.post("/membership/g/buy_single", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["balance"] == 1
    assert body["purchase"]["units"] == 1
    assert body["purchase"]["amount"] == 1.00


def test_buy_pack_20_increments_balance(app_module, client):
    user, sid = _make_user(app_module, "bea", cohort="founder")
    r = client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["balance"] == 20
    assert body["purchase"]["units"] == 20
    assert body["purchase"]["amount"] == 20.00


def test_buy_blocked_when_g_credits_disabled(app_module, client):
    user, sid = _make_user(app_module, "guest2", cohort=None)
    r = client.post("/membership/g/buy_single", headers=_auth(sid))
    assert r.status_code == 403


def test_history_returns_recent_first(app_module, client):
    user, sid = _make_user(app_module, "henri", cohort="founder")
    client.post("/membership/g/buy_single", headers=_auth(sid))
    client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    r = client.get("/membership/g/history", headers=_auth(sid))
    assert r.status_code == 200
    txs = r.json()["transactions"]
    types = [t["type"] for t in txs]
    # v31 — transaction types reflect PaymentIntent kinds, newest first.
    assert types[0] == "g_credit_pack"
    assert "g_credit_single" in types


# ---------------------------------------------------------------------------
# /elins/g/run + credit consumption
# ---------------------------------------------------------------------------
def test_g_run_blocks_with_402_when_no_credits(app_module, client):
    user, sid = _make_user(app_module, "rhea", cohort="founder")
    r = client.post(
        "/elins/g/run", headers=_auth(sid),
        json={"scenario_text": "scenario"},
    )
    assert r.status_code == 402
    assert r.json()["error"] == "no_credits"


def test_g_run_consumes_one_credit_on_success(app_module, client):
    user, sid = _make_user(app_module, "rin", cohort="founder")
    # Buy a pack first.
    client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    r = client.post(
        "/elins/g/run", headers=_auth(sid),
        json={"scenario_text": "scenario"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["g_credits_remaining"] == 19


def test_g_run_does_not_consume_credit_on_failure(app_module, client):
    user, sid = _make_user(app_module, "ria", cohort="founder")
    client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    r = client.post(
        "/elins/g/run", headers=_auth(sid),
        json={"scenario_text": ""},  # empty fails validation pre-credit check
    )
    assert r.status_code == 400
    # Balance unchanged.
    state = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    assert state["g_credits"]["balance"] == 20


# ---------------------------------------------------------------------------
# Auth contract — every membership endpoint requires a session
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path,method,body", [
    ("/membership/state", "GET", None),
    ("/membership/activate", "POST", {"accept_terms": True}),
    ("/membership/cancel", "POST", {}),
    ("/membership/g/buy_single", "POST", {}),
    ("/membership/g/buy_pack_20", "POST", {}),
    ("/membership/g/history", "GET", None),
])
def test_membership_endpoints_require_session(app_module, client, path, method, body):
    if method == "GET":
        r = client.get(path)
    else:
        r = client.post(path, json=body)
    assert r.status_code == 401, f"{path} returned {r.status_code}"
