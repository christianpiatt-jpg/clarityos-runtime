"""C1 / A+D Step 3 — subscription endpoints + webhook integration tests.

Webhook handlers are driven through the real ``/billing/webhook`` route in
mock mode (unsigned synthetic events). Synthetic events carry ``customer``
(no metadata), so they resolve via ``find_user_by_stripe_customer_id`` and the
legacy ``_handle_subscription_event`` (metadata-resolution) cleanly no-ops —
exactly the additive coexistence the cutover relies on. Endpoint tests seed a
founder-cohort session so the feature gates pass.
"""
from __future__ import annotations

import time

import pytest

import app as app_mod
import users_store
import sessions_store
import membership_store
from conftest import TestClient


@pytest.fixture
def app_client(reset_stores):
    return TestClient(app_mod.app)


@pytest.fixture
def client_and_user(app_client):
    users_store.create_user("subm", b"pw", "", "free", 0.0)
    # simulate a started (incomplete) subscription with a known customer id
    users_store.set_subscription(
        "subm", customer_id="cus_t", subscription_id="sub_t", status="incomplete",
    )
    return app_client, "subm"


@pytest.fixture
def client_and_authed(app_client):
    user = "subm"
    users_store.create_user(user, b"pw", "", "free", 0.0)
    users_store.update_user(user, {"cohort": "founder"})  # founder flags enabled in reset_stores
    sid = "sess_subm"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return app_client, user, {"X-Session-ID": sid}


def _post_event(client, etype, obj, eid="evt_test"):
    return client.post(
        "/billing/webhook", json={"id": eid, "type": etype, "data": {"object": obj}},
    )


# ---------------------------------------------------------------------------
# Webhook handlers
# ---------------------------------------------------------------------------
def test_invoice_paid_activates_member(client_and_user):
    client, user = client_and_user
    r = _post_event(client, "invoice.paid", {"customer": "cus_t", "period_end": 1893456000})
    assert r.status_code == 200

    view = users_store.get_subscription_view(user)
    assert view["subscription_status"] == "active"
    assert view["current_period_end_ts"] == 1893456000
    assert view["payment_action_required"] is False

    mv = users_store.get_membership_view(user)
    assert mv["billing_state"] == "active"
    assert mv["status"] == "active"
    assert membership_store.is_member(user)


def test_invoice_paid_is_idempotent_on_replay(client_and_user):
    client, user = client_and_user
    # two distinct event ids (past the webhook's seen-event dedup), same effect
    _post_event(client, "invoice.paid", {"customer": "cus_t", "period_end": 100}, eid="evt_a")
    _post_event(client, "invoice.paid", {"customer": "cus_t", "period_end": 100}, eid="evt_b")
    assert membership_store.get_cohort_state()["active_count"] == 1   # not double-added
    assert users_store.get_membership_view(user)["status"] == "active"


def test_invoice_payment_failed_flags_action_required(client_and_user):
    client, user = client_and_user
    _post_event(client, "invoice.payment_failed", {"customer": "cus_t"})
    view = users_store.get_subscription_view(user)
    assert view["subscription_status"] == "past_due"
    assert view["payment_action_required"] is True
    assert users_store.get_billing_state(user) == "past_due"


def test_subscription_updated_syncs_fields(client_and_user):
    client, user = client_and_user
    _post_event(
        client, "customer.subscription.updated",
        {"customer": "cus_t", "status": "active", "current_period_end": 222, "cancel_at_period_end": True},
    )
    view = users_store.get_subscription_view(user)
    assert view["cancel_at_period_end"] is True
    assert view["current_period_end_ts"] == 222
    assert view["subscription_status"] == "active"
    assert users_store.get_billing_state(user) == "active"


def test_subscription_deleted_cancels_and_drops_cohort(client_and_user):
    client, user = client_and_user
    users_store.set_membership(user, tier="founding_500", price=50.0, status="active")
    membership_store.add_member(user)
    _post_event(client, "customer.subscription.deleted", {"customer": "cus_t", "status": "canceled"})
    view = users_store.get_subscription_view(user)
    assert view["subscription_status"] == "canceled"
    assert users_store.get_billing_state(user) == "cancelled"
    assert not membership_store.is_member(user)


def test_unknown_customer_is_noop(client_and_user):
    client, user = client_and_user
    r = _post_event(client, "invoice.paid", {"customer": "cus_unknown", "period_end": 100})
    assert r.status_code == 200            # never raises out of the webhook
    assert users_store.get_billing_state(user) is None   # our user untouched


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def test_subscription_start_endpoint(client_and_authed):
    client, user, headers = client_and_authed
    r = client.post("/billing/subscription/start", json={"price_id": "price_x"}, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["client_secret"] and "_secret_" in body["client_secret"]
    assert body["subscription_id"].startswith("sub_mock_")
    assert users_store.get_subscription_view(user)["stripe_subscription_id"] == body["subscription_id"]


def test_subscription_start_requires_auth(app_client):
    r = app_client.post("/billing/subscription/start", json={"price_id": "price_x"})
    assert r.status_code == 401


def test_subscription_cancel_endpoint(client_and_authed):
    client, user, headers = client_and_authed
    client.post("/billing/subscription/start", json={}, headers=headers)
    r = client.post("/billing/subscription/cancel", json={"mode": "period_end"}, headers=headers)
    assert r.status_code == 200, r.text
    assert users_store.get_subscription_view(user)["cancel_at_period_end"] is True


def test_subscription_cancel_bad_mode(client_and_authed):
    client, user, headers = client_and_authed
    client.post("/billing/subscription/start", json={}, headers=headers)
    r = client.post("/billing/subscription/cancel", json={"mode": "whenever"}, headers=headers)
    assert r.status_code == 400
