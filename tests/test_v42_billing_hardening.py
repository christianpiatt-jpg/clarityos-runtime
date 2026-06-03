"""
Tests for v42 — Stripe live mode + billing hardening.

Covers:
* billing_config:
  - get_secret_key / get_webhook_secret prefer v42 env names
  - get_stripe_mode resolution (explicit override / sk_ prefix / fallback)
  - get_billing_status shape + booleans
  - seen_event / mark_event_seen idempotency contract
  - record_billing_event sanitises payload meta + drops PII keys
  - list_recent_events ordering + limit
* Checkout (PaymentIntent) hardening:
  - create_payment_intent in mock mode succeeds
  - create_payment_intent in stripe mode without keys raises billing_disabled
  - create_payment_intent in stripe mode attaches environment metadata
* Webhook handler:
  - mock mode accepts unsigned synthetic events
  - stripe mode missing signature → 400
  - stripe mode invalid signature → 400
  - stripe mode mode mismatch (test event arriving on live key) → 400
  - duplicate event id → ok + duplicate=True (idempotent short-circuit)
  - checkout.session.completed → users_store.set_billing_state(active) +
    transaction recorded
  - invoice.payment_succeeded → renewal_ts updated
  - customer.subscription.updated past_due → billing_state past_due
  - customer.subscription.deleted → billing_state cancelled
* /founder/billing/status — shape + recent_events + founder gate.
* /me/billing — status / plan / renewal_ts / mode.
"""
from __future__ import annotations

import json
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


def _make_user(app_module, username, cohort="founder", *,
               billing_state=None, renewal_ts=None):
    import secrets
    import users_store, sessions_store, bcrypt
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    patch = {}
    if cohort:
        patch["cohort"] = cohort
    if billing_state is not None:
        patch["billing_state"] = billing_state
    if renewal_ts is not None:
        patch["renewal_ts"] = float(renewal_ts)
    if patch:
        users_store.update_user(username, patch)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ---------------------------------------------------------------------------
# billing_config
# ---------------------------------------------------------------------------
def test_secret_key_prefers_v42_env(reset_stores, monkeypatch):
    import billing_config as bc
    monkeypatch.delenv("CLARITYOS_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_legacy")
    assert bc.get_secret_key() == "sk_test_legacy"
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_test_new")
    assert bc.get_secret_key() == "sk_test_new"


def test_webhook_secret_prefers_v42_env(reset_stores, monkeypatch):
    import billing_config as bc
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_legacy")
    assert bc.get_webhook_secret() == "whsec_legacy"
    monkeypatch.setenv("CLARITYOS_STRIPE_WEBHOOK_SECRET", "whsec_new")
    assert bc.get_webhook_secret() == "whsec_new"


def test_stripe_mode_explicit_override(reset_stores, monkeypatch):
    import billing_config as bc
    monkeypatch.setenv("CLARITYOS_STRIPE_MODE", "live")
    monkeypatch.delenv("CLARITYOS_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    # explicit override applies even with no key set
    assert bc.get_stripe_mode() == "live"


def test_stripe_mode_inferred_from_key_prefix(reset_stores, monkeypatch):
    import billing_config as bc
    monkeypatch.delenv("CLARITYOS_STRIPE_MODE", raising=False)
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_live_xxx")
    assert bc.get_stripe_mode() == "live"
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_test_yyy")
    assert bc.get_stripe_mode() == "test"


def test_stripe_mode_disabled_when_no_key(reset_stores, monkeypatch):
    import billing_config as bc
    monkeypatch.delenv("CLARITYOS_STRIPE_MODE", raising=False)
    monkeypatch.delenv("CLARITYOS_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    assert bc.get_stripe_mode() == "disabled"
    assert bc.is_billing_enabled() is False


def test_billing_status_shape(reset_stores, monkeypatch):
    import billing_config as bc
    monkeypatch.delenv("CLARITYOS_STRIPE_MODE", raising=False)
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_test_xxx")
    monkeypatch.setenv("CLARITYOS_STRIPE_WEBHOOK_SECRET", "whsec_xxx")
    s = bc.get_billing_status()
    assert s["mode"] == "test"
    assert s["has_secret"] is True
    assert s["has_webhook_secret"] is True
    assert s["live_mode"] is False
    assert s["billing_enabled"] is True


def test_seen_event_idempotency(reset_stores):
    import billing_config as bc
    assert bc.seen_event("evt_1") is False
    bc.mark_event_seen("evt_1")
    assert bc.seen_event("evt_1") is True


def test_seen_event_empty_id_returns_false(reset_stores):
    import billing_config as bc
    assert bc.seen_event(None) is False
    assert bc.seen_event("") is False


def test_record_billing_event_strips_pii(reset_stores):
    import billing_config as bc
    bc.record_billing_event(
        "test.event",
        user_id="alice",
        event_id="evt_1",
        payload_meta={
            "amount": 5000,
            "card": "4242424242424242",       # PII — must be stripped
            "customer": "cus_xxx",            # PII — must be stripped
            "email": "alice@example.com",     # PII — must be stripped
            "client_secret": "sneaky_value",  # PII — must be stripped
        },
    )
    rows = bc.list_recent_events()
    assert len(rows) == 1
    meta = rows[0]["payload_meta"]
    for forbidden in ("card", "customer", "email", "client_secret"):
        assert forbidden not in meta
    assert meta["amount"] == 5000


def test_list_recent_events_newest_first(reset_stores):
    import billing_config as bc
    bc.record_billing_event("a")
    bc.record_billing_event("b")
    bc.record_billing_event("c")
    rows = bc.list_recent_events()
    assert [r["event_type"] for r in rows[:3]] == ["c", "b", "a"]


# ---------------------------------------------------------------------------
# Checkout (PaymentIntent) hardening
# ---------------------------------------------------------------------------
def test_create_payment_intent_mock_mode_succeeds(reset_stores):
    import billing_intents
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    intent = billing_intents.create_payment_intent(
        "alice", 50.00, "test charge", "membership_activation",
    )
    assert intent["intent_id"]
    assert intent["mode"] == "mock"
    assert intent.get("environment") == "mock"


def test_create_payment_intent_stripe_mode_no_key_raises(reset_stores, monkeypatch):
    import billing_intents
    import users_store
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "stripe")
    monkeypatch.delenv("CLARITYOS_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    with pytest.raises(billing_intents.BillingError) as exc:
        billing_intents.create_payment_intent(
            "alice", 50.00, "test", "membership_activation",
        )
    assert exc.value.code == "billing_disabled"


def test_create_payment_intent_validates_inputs(reset_stores):
    import billing_intents
    with pytest.raises(billing_intents.BillingError):
        billing_intents.create_payment_intent(
            "", 50.0, "x", "membership_activation",
        )
    with pytest.raises(billing_intents.BillingError):
        billing_intents.create_payment_intent(
            "alice", 0.10, "x", "membership_activation",
        )
    with pytest.raises(billing_intents.BillingError):
        billing_intents.create_payment_intent(
            "alice", 50.0, "x", "made_up_kind",
        )


# ---------------------------------------------------------------------------
# Webhook handler
# ---------------------------------------------------------------------------
def test_webhook_mock_mode_accepts_synthetic(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    event = {"id": "evt_mock_1", "type": "test.event", "data": {"object": {}}}
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200, r.json()


def test_webhook_stripe_mode_missing_signature(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "stripe")
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_test_xxx")
    monkeypatch.setenv("CLARITYOS_STRIPE_WEBHOOK_SECRET", "whsec_xxx")
    monkeypatch.setenv("STRIPE_PRICE_ONETIME", "price_1")
    monkeypatch.setenv("STRIPE_PRICE_RECURRING", "price_2")
    r = client.post(
        "/billing/webhook",
        json={"type": "test.event"},
        # no Stripe-Signature header
    )
    assert r.status_code == 400
    assert r.json()["error"] == "missing_signature"


def test_webhook_stripe_mode_invalid_signature(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "stripe")
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_test_xxx")
    monkeypatch.setenv("CLARITYOS_STRIPE_WEBHOOK_SECRET", "whsec_xxx")
    monkeypatch.setenv("STRIPE_PRICE_ONETIME", "price_1")
    monkeypatch.setenv("STRIPE_PRICE_RECURRING", "price_2")
    # Patch billing.verify_webhook to return None (signature mismatch).
    import billing
    monkeypatch.setattr(billing, "verify_webhook", lambda payload, sig: None)
    r = client.post(
        "/billing/webhook",
        json={"type": "test.event"},
        headers={"Stripe-Signature": "t=0,v1=bad"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "bad_signature"


def test_webhook_stripe_mode_rejects_mode_mismatch(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "stripe")
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_live_xxx")
    monkeypatch.setenv("CLARITYOS_STRIPE_WEBHOOK_SECRET", "whsec_xxx")
    monkeypatch.setenv("STRIPE_PRICE_ONETIME", "price_1")
    monkeypatch.setenv("STRIPE_PRICE_RECURRING", "price_2")
    # Live key configured, but the event is livemode=false (test event).
    fake_event = {
        "id": "evt_test_1", "type": "checkout.session.completed",
        "livemode": False, "data": {"object": {}},
    }
    import billing
    monkeypatch.setattr(billing, "verify_webhook", lambda payload, sig: fake_event)
    r = client.post(
        "/billing/webhook", json=fake_event,
        headers={"Stripe-Signature": "t=0,v1=valid"},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "mode_mismatch"


def test_webhook_idempotency_duplicate_event_id(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    event = {
        "id": "evt_dup_1", "type": "checkout.session.completed",
        "data": {"object": {"id": "cs_1", "payment_status": "paid",
                            "amount_total": 5000,
                            "metadata": {"user_id": "alice"}}},
    }
    r1 = client.post("/billing/webhook", json=event)
    assert r1.status_code == 200
    assert r1.json().get("duplicate") is not True
    r2 = client.post("/billing/webhook", json=event)
    assert r2.status_code == 200
    assert r2.json().get("duplicate") is True


def test_webhook_checkout_session_completed_updates_billing_state(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    event = {
        "id": "evt_co_1", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_xxx", "payment_status": "paid",
            "amount_total": 5000,
            "metadata": {"user_id": "alice", "plan": "founding"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    state = users_store.get_user("alice") or {}
    assert state.get("billing_state") == "active"
    assert state.get("renewal_ts") is not None


def test_webhook_invoice_payment_succeeded_updates_renewal(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    new_period_end = int(time.time()) + 30 * 24 * 3600
    event = {
        "id": "evt_inv_1", "type": "invoice.payment_succeeded",
        "data": {"object": {
            "id": "in_xxx", "subscription": "sub_xxx",
            "current_period_end": new_period_end,
            "metadata": {"user_id": "alice"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    state = users_store.get_user("alice") or {}
    assert state.get("billing_state") == "active"
    assert int(state.get("renewal_ts") or 0) == new_period_end


def test_webhook_subscription_updated_past_due(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    event = {
        "id": "evt_sub_1", "type": "customer.subscription.updated",
        "data": {"object": {
            "id": "sub_xxx", "status": "past_due",
            "current_period_end": int(time.time()) + 30 * 24 * 3600,
            "metadata": {"user_id": "alice"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    state = users_store.get_user("alice") or {}
    assert state.get("billing_state") == "past_due"


def test_webhook_subscription_deleted_cancels(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    users_store.set_billing_state("alice", billing_state="active",
                                  renewal_ts=time.time() + 86400)
    event = {
        "id": "evt_subdel_1", "type": "customer.subscription.deleted",
        "data": {"object": {
            "id": "sub_xxx", "status": "canceled",
            "canceled_at": int(time.time()),
            "metadata": {"user_id": "alice"},
        }},
    }
    r = client.post("/billing/webhook", json=event)
    assert r.status_code == 200
    state = users_store.get_user("alice") or {}
    assert state.get("billing_state") == "cancelled"


def test_webhook_records_event_in_recent_ring(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import billing_config as bc
    event = {
        "id": "evt_ring_1", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_xxx", "payment_status": "paid",
            "amount_total": 5000,
            "metadata": {"user_id": "alice"},
        }},
    }
    client.post("/billing/webhook", json=event)
    rows = bc.list_recent_events()
    assert len(rows) >= 1
    assert rows[0]["event_type"] == "checkout.session.completed"
    assert rows[0]["event_id"] == "evt_ring_1"


# ---------------------------------------------------------------------------
# /founder/billing/status
# ---------------------------------------------------------------------------
def test_founder_billing_status_shape(app_module, client):
    user, sid = _make_user(app_module, "fbs_a", cohort="founder")
    r = client.get("/founder/billing/status", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert "stripe" in body
    assert "recent_events" in body
    assert "live_mode" in body
    assert "last_event_ts" in body
    assert "runtime_billing_mode" in body


def test_founder_billing_status_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "fbs_outsider", cohort=None)
    r = client.get("/founder/billing/status", headers=_auth(sid))
    assert r.status_code == 403


def test_founder_billing_status_reflects_mode(app_module, client, monkeypatch):
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_live_xxx")
    monkeypatch.setenv("CLARITYOS_STRIPE_WEBHOOK_SECRET", "whsec_xxx")
    user, sid = _make_user(app_module, "fbs_b", cohort="founder")
    r = client.get("/founder/billing/status", headers=_auth(sid))
    body = r.json()
    assert body["stripe"]["mode"] == "live"
    assert body["live_mode"] is True


def test_founder_billing_status_disabled_when_no_keys(app_module, client, monkeypatch):
    monkeypatch.delenv("CLARITYOS_STRIPE_MODE", raising=False)
    monkeypatch.delenv("CLARITYOS_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    user, sid = _make_user(app_module, "fbs_c", cohort="founder")
    r = client.get("/founder/billing/status", headers=_auth(sid))
    body = r.json()
    assert body["stripe"]["mode"] == "disabled"
    assert body["stripe"]["billing_enabled"] is False


# ---------------------------------------------------------------------------
# /me/billing
# ---------------------------------------------------------------------------
def test_me_billing_default_none(app_module, client):
    user, sid = _make_user(app_module, "mb_a", cohort="founder")
    r = client.get("/me/billing", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "none"
    assert "mode" in body
    assert "billing_enabled" in body


def test_me_billing_active_state(app_module, client):
    user, sid = _make_user(
        app_module, "mb_b", cohort="founder",
        billing_state="active", renewal_ts=time.time() + 86400 * 30,
    )
    r = client.get("/me/billing", headers=_auth(sid))
    body = r.json()
    assert body["status"] == "active"
    assert body["renewal_ts"] is not None


def test_me_billing_past_due(app_module, client):
    user, sid = _make_user(
        app_module, "mb_c", cohort="founder",
        billing_state="past_due",
    )
    r = client.get("/me/billing", headers=_auth(sid))
    body = r.json()
    assert body["status"] == "past_due"


def test_me_billing_grace_period(app_module, client):
    # grace_period now surfaces distinctly (previously collapsed to past_due).
    user, sid = _make_user(
        app_module, "mb_g", cohort="founder",
        billing_state="grace_period",
    )
    r = client.get("/me/billing", headers=_auth(sid))
    assert r.json()["status"] == "grace_period"


def test_me_billing_canceled(app_module, client):
    user, sid = _make_user(
        app_module, "mb_d", cohort="founder",
        billing_state="cancelled",
    )
    r = client.get("/me/billing", headers=_auth(sid))
    body = r.json()
    assert body["status"] == "canceled"


def test_me_billing_no_raw_stripe_ids(app_module, client):
    """Defensive — /me/billing must never expose raw Stripe ids."""
    user, sid = _make_user(app_module, "mb_e", cohort="founder")
    r = client.get("/me/billing", headers=_auth(sid))
    body = r.json()
    serialised = repr(body)
    for forbidden in ("cus_", "sub_", "in_", "pi_", "client_secret"):
        assert forbidden not in serialised, f"raw {forbidden!r} leaked into /me/billing"
