"""
Tests for v31 — Billing Finalization + PaymentIntents.

Covers:
* PaymentIntent creation (mock mode, manual-confirm)
* Webhook success → side-effect lands (cohort add, credits, renewal_ts set)
* Webhook failure → state machine transitions (past_due → grace → cancelled)
* Idempotency: re-running the same webhook event is a no-op
* Renewal scheduler picks up due users, drives the lifecycle
* Membership cancellation flips billing_state to cancelled
* /elins/g/run still works after credits land via webhook
* /billing/{intent, webhook, history} endpoints
"""
from __future__ import annotations

import json
import time

import pytest


@pytest.fixture
def stub_embedder(monkeypatch):
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
    import secrets
    import users_store, sessions_store, bcrypt
    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
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


# ---------------------------------------------------------------------------
# billing_intents — pure-Python unit tests (no FastAPI)
# ---------------------------------------------------------------------------
def test_create_intent_validation(reset_stores):
    import billing_intents as bi
    with pytest.raises(bi.BillingError) as exc:
        bi.create_payment_intent("", 50.0, "test", kind="g_credit_single")
    assert exc.value.code == "bad_user"

    with pytest.raises(bi.BillingError) as exc:
        bi.create_payment_intent("u1", -1.0, "test", kind="g_credit_single")
    assert exc.value.code == "bad_amount"

    with pytest.raises(bi.BillingError) as exc:
        bi.create_payment_intent("u1", 0.10, "test", kind="g_credit_single")
    assert exc.value.code == "bad_amount"

    with pytest.raises(bi.BillingError) as exc:
        bi.create_payment_intent("u1", 1.0, "", kind="g_credit_single")
    assert exc.value.code == "bad_description"

    with pytest.raises(bi.BillingError) as exc:
        bi.create_payment_intent("u1", 1.0, "test", kind="not_a_kind")
    assert exc.value.code == "bad_kind"


def test_create_intent_auto_confirm_default(reset_stores):
    """In default mock mode the intent immediately reports succeeded."""
    import billing_intents as bi
    intent = bi.create_payment_intent("u1", 1.0, "single", kind="g_credit_single")
    assert intent["status"] == "succeeded"
    assert intent["side_effect_applied"] is True


def test_create_intent_pending_when_manual(reset_stores, manual_confirm):
    import billing_intents as bi
    intent = bi.create_payment_intent("u1", 1.0, "single", kind="g_credit_single")
    assert intent["status"] == "requires_payment_method"
    assert intent["side_effect_applied"] is False


def test_confirm_payment_intent_lands_credits(reset_stores, manual_confirm):
    import billing_intents as bi
    import users_store
    users_store.create_user("u2", b"x", "", "free", time.time())
    intent = bi.create_payment_intent("u2", 1.0, "single", kind="g_credit_single")
    assert users_store.get_g_credit_balance("u2") == 0
    confirmed = bi.confirm_payment_intent(intent["intent_id"])
    assert confirmed["status"] == "succeeded"
    assert users_store.get_g_credit_balance("u2") == 1


def test_confirm_is_idempotent(reset_stores, manual_confirm):
    import billing_intents as bi
    import users_store
    users_store.create_user("u3", b"x", "", "free", time.time())
    intent = bi.create_payment_intent("u3", 20.0, "pack", kind="g_credit_pack")
    bi.confirm_payment_intent(intent["intent_id"])
    bi.confirm_payment_intent(intent["intent_id"])  # second call: no-op
    assert users_store.get_g_credit_balance("u3") == 20


def test_failed_intent_transitions_membership_renewal(reset_stores, manual_confirm):
    import billing_intents as bi
    import users_store
    users_store.create_user("u4", b"x", "", "free", time.time())
    users_store.set_membership(
        "u4", tier="founding_500", price=50.0, status="active",
        started_ts=time.time(),
    )
    users_store.set_billing_state(
        "u4", billing_state="active",
        renewal_ts=time.time() - 60.0,
    )
    intent = bi.create_payment_intent("u4", 50.0, "renew u4", kind="membership_renewal")
    bi.fail_payment_intent(intent["intent_id"])
    state = users_store.get_billing_state("u4")
    assert state == "past_due"
    doc = users_store.get_user("u4")
    assert int(doc.get("renewal_retry_count") or 0) == 1


def test_three_failed_renewals_enter_grace(reset_stores, manual_confirm):
    import billing_intents as bi
    import users_store
    users_store.create_user("u5", b"x", "", "free", time.time())
    users_store.set_membership(
        "u5", tier="founding_500", price=50.0, status="active",
        started_ts=time.time(),
    )
    users_store.set_billing_state(
        "u5", billing_state="active",
        renewal_ts=time.time() - 60.0,
        renewal_retry_count=2,  # next failure will be the 3rd
    )
    intent = bi.create_payment_intent("u5", 50.0, "renew u5", kind="membership_renewal")
    bi.fail_payment_intent(intent["intent_id"])
    assert users_store.get_billing_state("u5") == "grace_period"
    doc = users_store.get_user("u5")
    assert doc.get("renewal_grace_until_ts") is not None


# ---------------------------------------------------------------------------
# Renewal scheduler
# ---------------------------------------------------------------------------
def test_calculate_next_renewal_ts():
    import billing_intents
    base = 1700000000.0
    out = billing_intents.calculate_next_renewal_ts(base)
    assert out == base + 30 * 86400.0


def test_renewal_scheduler_picks_up_due_users(reset_stores):
    """Auto-confirm mode — the renewal pass creates an intent which
    immediately succeeds, extending renewal_ts by 30 days."""
    import billing_renewal, users_store
    users_store.create_user("u6", b"x", "", "free", time.time())
    users_store.set_membership(
        "u6", tier="founding_500", price=50.0, status="active",
        started_ts=time.time(),
    )
    overdue_ts = time.time() - 60.0
    users_store.set_billing_state(
        "u6", billing_state="active", renewal_ts=overdue_ts,
    )

    summary = billing_renewal._renewal_one_pass(now_ts=time.time())
    assert summary["due"] == 1
    assert summary["intents"] == 1
    # Auto-confirm landed: renewal_ts pushed out, retry count zeroed.
    doc = users_store.get_user("u6")
    assert float(doc.get("renewal_ts") or 0) > overdue_ts + 28 * 86400
    assert int(doc.get("renewal_retry_count") or 0) == 0


def test_renewal_scheduler_terminates_after_grace(reset_stores, manual_confirm):
    """User in grace_period whose grace window has elapsed should be
    transitioned to cancelled by the scheduler."""
    import billing_renewal, users_store, membership_store
    users_store.create_user("u7", b"x", "", "free", time.time())
    users_store.set_membership(
        "u7", tier="founding_500", price=50.0, status="active",
        started_ts=time.time(),
    )
    membership_store.add_member("u7")  # currently in cohort
    past_grace = time.time() - 60.0
    users_store.set_billing_state(
        "u7", billing_state="grace_period",
        renewal_ts=time.time() - 1,
        renewal_retry_count=3,
        renewal_grace_until_ts=past_grace,
    )
    summary = billing_renewal._renewal_one_pass(now_ts=time.time())
    assert summary["terminated"] == 1
    assert users_store.get_billing_state("u7") == "cancelled"
    assert membership_store.is_member("u7") is False
    doc = users_store.get_user("u7")
    assert doc.get("membership_status") == "cancelled"


def test_renewal_scheduler_skips_not_due(reset_stores):
    import billing_renewal, users_store
    users_store.create_user("u8", b"x", "", "free", time.time())
    users_store.set_membership(
        "u8", tier="founding_500", price=50.0, status="active",
        started_ts=time.time(),
    )
    users_store.set_billing_state(
        "u8", billing_state="active",
        renewal_ts=time.time() + 86400.0 * 5,  # not due
    )
    summary = billing_renewal._renewal_one_pass(now_ts=time.time())
    assert summary["due"] == 0


# ---------------------------------------------------------------------------
# /membership/activate — async flow
# ---------------------------------------------------------------------------
def test_activate_returns_pending_in_manual_mode(app_module, client, manual_confirm):
    user, sid = _make_user(app_module, "alice31", cohort="founder")
    r = client.post(
        "/membership/activate", headers=_auth(sid), json={"accept_terms": True},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["pending"] is True
    assert body["intent"]["intent_id"].startswith("pi_")
    # Membership not active yet — webhook hasn't fired.
    assert body["state"]["membership"]["status"] is None


def test_activate_then_webhook_lands_membership(app_module, client, manual_confirm):
    user, sid = _make_user(app_module, "amy31", cohort="founder")
    r = client.post(
        "/membership/activate", headers=_auth(sid), json={"accept_terms": True},
    )
    intent_id = r.json()["intent"]["intent_id"]

    # Fire the synthetic webhook.
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": intent_id}},
    }
    wh = client.post("/billing/webhook", json=event)
    assert wh.status_code == 200, wh.json()

    # Membership is now active + cohort joined.
    state = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    assert state["membership"]["status"] == "active"
    assert state["billing"]["state"] == "active"
    assert state["billing"]["renewal_ts"] is not None
    assert state["cohort"]["active_count"] == 1


def test_activate_then_failed_webhook_records_failed(app_module, client, manual_confirm):
    user, sid = _make_user(app_module, "anya31", cohort="founder")
    r = client.post(
        "/membership/activate", headers=_auth(sid), json={"accept_terms": True},
    )
    intent_id = r.json()["intent"]["intent_id"]

    event = {
        "type": "payment_intent.payment_failed",
        "data": {"object": {
            "id": intent_id,
            "last_payment_error": {"code": "card_declined"},
        }},
    }
    client.post("/billing/webhook", json=event)

    state = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    assert state["billing"]["state"] == "failed"
    assert state["membership"]["status"] is None  # never activated


def test_webhook_idempotent_on_duplicate_event(app_module, client, manual_confirm):
    user, sid = _make_user(app_module, "ada31", cohort="founder")
    r = client.post(
        "/membership/activate", headers=_auth(sid), json={"accept_terms": True},
    )
    intent_id = r.json()["intent"]["intent_id"]
    event = {"type": "payment_intent.succeeded", "data": {"object": {"id": intent_id}}}

    # Fire it twice.
    client.post("/billing/webhook", json=event)
    client.post("/billing/webhook", json=event)

    state = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    # Cohort active_count must be 1, not 2 — second event was a no-op.
    assert state["cohort"]["active_count"] == 1


# ---------------------------------------------------------------------------
# /billing/intent + /billing/intent/confirm + /billing/history
# ---------------------------------------------------------------------------
def test_billing_intent_endpoint(app_module, client):
    user, sid = _make_user(app_module, "ben31", cohort="founder")
    r = client.post(
        "/billing/intent", headers=_auth(sid),
        json={"amount": 1.0, "description": "single credit", "kind": "g_credit_single"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["intent"]["intent_id"].startswith("pi_")


def test_billing_intent_rejects_bad_kind(app_module, client):
    user, sid = _make_user(app_module, "bobby31", cohort="founder")
    r = client.post(
        "/billing/intent", headers=_auth(sid),
        json={"amount": 1.0, "description": "x", "kind": "totally_invalid"},
    )
    assert r.status_code == 400


def test_billing_confirm_belongs_to_user(app_module, client, manual_confirm):
    """Users can't confirm someone else's intent."""
    import billing_intents
    u1, sid1 = _make_user(app_module, "carl31", cohort="founder")
    u2, sid2 = _make_user(app_module, "dee31", cohort="founder")
    intent = billing_intents.create_payment_intent(
        u1, 1.0, "x", kind="g_credit_single",
    )
    r = client.post(
        "/billing/intent/confirm", headers=_auth(sid2),
        json={"intent_id": intent["intent_id"]},
    )
    assert r.status_code == 403


def test_billing_history_combines_transactions_and_intents(app_module, client):
    user, sid = _make_user(app_module, "ed31", cohort="founder")
    # Buy a single credit (auto-confirmed → both an intent + a tx).
    client.post("/membership/g/buy_single", headers=_auth(sid))
    r = client.get("/billing/history", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert len(body["intents"]) == 1
    assert any(t["type"] == "g_credit_single" for t in body["transactions"])


# ---------------------------------------------------------------------------
# /membership/g/buy_* — async flow
# ---------------------------------------------------------------------------
def test_buy_single_pending_until_webhook(app_module, client, manual_confirm):
    user, sid = _make_user(app_module, "fay31", cohort="founder")
    r = client.post("/membership/g/buy_single", headers=_auth(sid))
    body = r.json()
    assert body["pending"] is True
    assert body["balance"] == 0  # not landed yet

    intent_id = body["intent"]["intent_id"]
    event = {"type": "payment_intent.succeeded", "data": {"object": {"id": intent_id}}}
    client.post("/billing/webhook", json=event)

    state = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    assert state["g_credits"]["balance"] == 1


def test_buy_pack_pending_then_failed_keeps_balance_zero(app_module, client, manual_confirm):
    user, sid = _make_user(app_module, "gabe31", cohort="founder")
    r = client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    intent_id = r.json()["intent"]["intent_id"]
    event = {
        "type": "payment_intent.payment_failed",
        "data": {"object": {"id": intent_id, "last_payment_error": {"code": "insufficient_funds"}}},
    }
    client.post("/billing/webhook", json=event)
    state = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    assert state["g_credits"]["balance"] == 0
    # The failure is recorded as a transaction.
    history = client.get("/billing/history", headers=_auth(sid)).json()
    assert any(t["type"] == "failed_payment" for t in history["transactions"])


# ---------------------------------------------------------------------------
# /membership/cancel
# ---------------------------------------------------------------------------
def test_cancel_flips_billing_state(app_module, client):
    user, sid = _make_user(app_module, "harriet31", cohort="founder")
    client.post(
        "/membership/activate", headers=_auth(sid), json={"accept_terms": True},
    )
    state_before = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    assert state_before["billing"]["state"] == "active"

    client.post("/membership/cancel", headers=_auth(sid))
    state_after = client.get("/membership/state", headers=_auth(sid)).json()["state"]
    assert state_after["billing"]["state"] == "cancelled"
    assert state_after["membership"]["status"] == "cancelled"


# ---------------------------------------------------------------------------
# Auth + flag-gate contract
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path,method,body", [
    ("/billing/intent", "POST", {"amount": 1.0, "description": "x", "kind": "g_credit_single"}),
    ("/billing/intent/confirm", "POST", {"intent_id": "x"}),
    ("/billing/history", "GET", None),
])
def test_billing_endpoints_require_session(app_module, client, path, method, body):
    if method == "GET":
        r = client.get(path)
    else:
        r = client.post(path, json=body)
    assert r.status_code == 401, f"{path} returned {r.status_code}"


def test_webhook_rejects_non_dict_payload(app_module, client):
    """Webhook with a string payload (mock mode) returns 400, not 200."""
    r = client.post("/billing/webhook", json="not_an_object")
    assert r.status_code == 400


def test_webhook_unknown_intent_acks_anyway(app_module, client):
    """Unknown intent ids are logged but ack'd 200 so Stripe stops retrying."""
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"id": "pi_does_not_exist"}},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
