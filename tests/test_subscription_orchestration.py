"""C1 / A+D Step 2b — Stripe subscription orchestration tests.

Mock-mode path is exercised directly (deterministic, no SDK). The stripe-mode
path is exercised with a fake `stripe` module injected via monkeypatch, to
verify the real code path calls the SDK and persists what Stripe returns —
without any network/keys. Backend-only; no endpoints, no webhooks.
"""
from __future__ import annotations

import sys
import types

import pytest

import users_store
import billing_subscriptions


@pytest.fixture
def user(reset_stores):
    users_store.create_user("sub_user", b"pw_hash_placeholder", "", "free", 0.0)
    return "sub_user"


# ---------------------------------------------------------------------------
# Mock mode (default)
# ---------------------------------------------------------------------------
def test_get_or_create_customer_creates_and_is_idempotent(user):
    cid = billing_subscriptions.get_or_create_stripe_customer_id(user)
    assert cid.startswith("cus_mock_")
    assert users_store.get_subscription_view(user)["stripe_customer_id"] == cid
    # second call returns the same id without re-creating
    assert billing_subscriptions.get_or_create_stripe_customer_id(user) == cid


def test_create_subscription_persists_fields(user):
    out = billing_subscriptions.create_membership_subscription(user, "price_founding")
    assert out["subscription_id"].startswith("sub_mock_")
    assert out["client_secret"] and "_secret_" in out["client_secret"]
    assert out["status"] == "incomplete"
    view = users_store.get_subscription_view(user)
    assert view["stripe_subscription_id"] == out["subscription_id"]
    assert view["stripe_customer_id"].startswith("cus_mock_")
    assert view["subscription_status"] == "incomplete"
    assert view["payment_action_required"] is False


def test_create_subscription_does_not_touch_v31_state(user):
    # Subscription fields are orthogonal to the v31 billing_state machine.
    billing_subscriptions.create_membership_subscription(user, "price_founding")
    mv = users_store.get_membership_view(user)
    assert mv["billing_state"] is None
    assert mv["status"] is None


def test_cancel_immediately(user):
    billing_subscriptions.create_membership_subscription(user, "price_founding")
    billing_subscriptions.cancel_subscription_immediately(user)
    assert users_store.get_subscription_view(user)["subscription_status"] == "canceled"


def test_cancel_at_period_end(user):
    billing_subscriptions.create_membership_subscription(user, "price_founding")
    billing_subscriptions.cancel_subscription_at_period_end(user)
    view = users_store.get_subscription_view(user)
    assert view["cancel_at_period_end"] is True
    assert view["subscription_status"] == "active"   # still active until period end


def test_cancel_without_subscription_raises(user):
    with pytest.raises(billing_subscriptions.SubscriptionError) as ei:
        billing_subscriptions.cancel_subscription_immediately(user)
    assert ei.value.code == "no_subscription"


# ---------------------------------------------------------------------------
# Stripe mode (mocked SDK)
# ---------------------------------------------------------------------------
def _fake_stripe():
    fake = types.ModuleType("stripe")
    fake.api_key = None

    class _Customer:
        @staticmethod
        def create(**kw):
            return types.SimpleNamespace(id="cus_fake_123")

    class _Subscription:
        @staticmethod
        def create(**kw):
            pi = types.SimpleNamespace(client_secret="pi_fake_secret_abc")
            inv = types.SimpleNamespace(payment_intent=pi)
            return types.SimpleNamespace(
                id="sub_fake_123", status="incomplete",
                current_period_end=1893456000, cancel_at_period_end=False,
                latest_invoice=inv,
            )

        @staticmethod
        def delete(sid):
            return types.SimpleNamespace(id=sid, status="canceled")

        @staticmethod
        def modify(sid, **kw):
            return types.SimpleNamespace(id=sid, status="active", current_period_end=1893456000)

    fake.Customer = _Customer
    fake.Subscription = _Subscription
    return fake


def test_stripe_mode_no_key_raises(monkeypatch, user):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "stripe")
    monkeypatch.delenv("CLARITYOS_STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    with pytest.raises(billing_subscriptions.SubscriptionError) as ei:
        billing_subscriptions.create_membership_subscription(user, "price_x")
    assert ei.value.code == "billing_disabled"


def test_stripe_mode_create_calls_sdk_and_persists(monkeypatch, user):
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "stripe")
    monkeypatch.setenv("CLARITYOS_STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setitem(sys.modules, "stripe", _fake_stripe())
    out = billing_subscriptions.create_membership_subscription(user, "price_x")
    assert out["subscription_id"] == "sub_fake_123"
    assert out["client_secret"] == "pi_fake_secret_abc"
    assert out["status"] == "incomplete"
    view = users_store.get_subscription_view(user)
    assert view["stripe_customer_id"] == "cus_fake_123"
    assert view["stripe_subscription_id"] == "sub_fake_123"
    assert view["current_period_end_ts"] == 1893456000
