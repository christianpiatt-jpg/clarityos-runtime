"""C1 / A+D Step 1+2a — subscription data-model + renewal-freeze tests.

Covers the additive slice landed first: per-user Stripe-subscription fields on
``users_store`` and the ``billing_renewal`` guard that keeps the legacy
PaymentIntent scheduler from renewing subscription-backed members. Pure store
+ scheduler logic — no Stripe SDK, no HTTP. Mock/memory backend (conftest).
"""
from __future__ import annotations

import pytest

import users_store
import billing_renewal


@pytest.fixture
def user(reset_stores):
    users_store.create_user("sub_user", b"pw_hash_placeholder", "", "free", 0.0)
    return "sub_user"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
def test_set_subscription_writes_all_fields(user):
    users_store.set_subscription(
        user, customer_id="cus_x", subscription_id="sub_x",
        status="active", current_period_end=1893456000, cancel_at_period_end=False,
    )
    view = users_store.get_subscription_view(user)
    assert view["stripe_customer_id"] == "cus_x"
    assert view["stripe_subscription_id"] == "sub_x"
    assert view["subscription_status"] == "active"
    assert view["current_period_end_ts"] == 1893456000
    assert view["cancel_at_period_end"] is False
    assert view["payment_action_required"] is False


def test_invalid_status_rejected(user):
    with pytest.raises(ValueError):
        users_store.set_subscription(
            user, customer_id="cus_x", subscription_id="sub_x", status="bogus",
        )
    with pytest.raises(ValueError):
        users_store.update_subscription_status(user, status="not_a_status")


def test_update_subscription_status_is_partial(user):
    users_store.set_subscription(
        user, customer_id="cus_x", subscription_id="sub_x",
        status="active", current_period_end=100,
    )
    users_store.update_subscription_status(user, cancel_at_period_end=True)
    view = users_store.get_subscription_view(user)
    assert view["cancel_at_period_end"] is True
    assert view["subscription_status"] == "active"     # untouched
    assert view["current_period_end_ts"] == 100          # untouched


def test_mark_canceled_and_payment_action_required(user):
    users_store.set_subscription(
        user, customer_id="cus_x", subscription_id="sub_x",
        status="active", cancel_at_period_end=True,
    )
    users_store.mark_payment_action_required(user, True)
    users_store.mark_subscription_canceled(user)
    view = users_store.get_subscription_view(user)
    assert view["subscription_status"] == "canceled"
    assert view["cancel_at_period_end"] is False         # cleared by cancel
    assert view["payment_action_required"] is True        # NOT cleared by cancel


def test_find_user_by_stripe_customer_id(user):
    users_store.set_subscription(
        user, customer_id="cus_lookup", subscription_id="sub_x", status="active",
    )
    assert users_store.find_user_by_stripe_customer_id("cus_lookup") == user
    assert users_store.find_user_by_stripe_customer_id("cus_missing") is None
    assert users_store.find_user_by_stripe_customer_id("") is None


# ---------------------------------------------------------------------------
# Renewal freeze guard
# ---------------------------------------------------------------------------
class TestRenewalFreezeGuard:
    def test_scheduler_skips_subscription_member(self, user):
        # A subscription-backed member who is long past due must be skipped:
        # Stripe drives their renewal, not the legacy scheduler.
        users_store.set_membership(user, tier="founding_500", price=50.0, status="active")
        users_store.set_billing_state(user, billing_state="active", renewal_ts=1.0)
        users_store.set_subscription(
            user, customer_id="cus_x", subscription_id="sub_x", status="active",
        )
        result = billing_renewal.renew_membership(user, now_ts=1_000_000.0)
        assert result["action"] == "no_op"
        assert result["reason"] == "stripe_canonical"

    def test_scheduler_still_renews_non_subscription_member(self, user):
        # A legacy PaymentIntent member (no stripe_subscription_id) is still
        # renewed by the scheduler — the guard must not over-reach.
        users_store.set_membership(user, tier="founding_500", price=50.0, status="active")
        users_store.set_billing_state(user, billing_state="active", renewal_ts=1.0)
        result = billing_renewal.renew_membership(user, now_ts=1_000_000.0)
        assert result["action"] == "intent_created"
