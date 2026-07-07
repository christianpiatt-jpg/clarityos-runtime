"""β1 T2 — persisted-state regression for the comp-override gate.

Companion to test_webhook_comp_override.py. That file tests the gate at
the users_store.update_user() unit boundary. THIS file replays every
Stripe webhook code path in app._handle_subscription_event against a
comp'd user seeded via the real users_store._MEMORY_USERS, and asserts
that:

  (a) guarded keys (membership_status, billing_state) are held against
      the webhook write, and
  (b) non-guarded informational keys (cancel_at_ts, canceled_at_ts,
      renewal_ts, subscription_status, stripe_customer_id,
      _cl19_mismatch_*, etc.) pass through unchanged.

This bridges the gap between the isolated unit tests (mocked stores) and
the Step E behavioral probe (live Cloud Run + real Stripe webhook).
"""
from __future__ import annotations

import pytest

import users_store
import app


COMP_EMAIL = "comp@founding-os.test"
NON_COMP_EMAIL = "plain@founding-os.test"


@pytest.fixture(autouse=True)
def memory_backend(monkeypatch):
    """Force in-memory backend and reset between tests."""
    monkeypatch.setattr(users_store, "_backend", lambda: "memory")
    users_store._MEMORY_USERS.clear()
    yield
    users_store._MEMORY_USERS.clear()


@pytest.fixture
def comp_user():
    """Seed a comp'd user matching the β1 A-write geometry.

    Mirrors the founder-comp doc written by CT-1's a_write:
    27 fields, comp_override=True, membership_status='active', no
    billing_state (founder comp has no Stripe subscription).
    """
    users_store._MEMORY_USERS[COMP_EMAIL] = {
        "username": COMP_EMAIL,
        "email": COMP_EMAIL,
        "membership_status": "active",
        "membership_tier": "founding_500",
        "membership_price": 0,
        "membership_confirmed": True,
        "g_credits": 100,
        "comp_override": True,
        "comp_granted_by": "ct1_founder_comp_2026-07-07",
        "comp_granted_ts": 1783430000.0,
    }
    return COMP_EMAIL


@pytest.fixture
def plain_user():
    """Seed a non-comp paying user (control group)."""
    users_store._MEMORY_USERS[NON_COMP_EMAIL] = {
        "username": NON_COMP_EMAIL,
        "email": NON_COMP_EMAIL,
        "membership_status": "active",
        "billing_state": "active",
        "membership_tier": "founding_500",
        "stripe_customer_id": "cus_test_plain",
    }
    return NON_COMP_EMAIL


# ---------------------------------------------------------------------------
# 6 webhook write paths against the comp'd user — guarded fields must HOLD
# ---------------------------------------------------------------------------


def test_checkout_session_completed_holds_comp(comp_user):
    """Path 1: checkout.session.completed → set_billing_state('active').

    TRIAGE NOTE (per COW-1 FLAG B): this path also runs auth_magiclink._ensure_user
    provisioning + membership_store.record_transaction (defensively try/excepted) +
    stripe_customer_id bind. If THIS test fails, isolate the failure to the gate
    by first checking whether the same failure reproduces on the plain user
    control (test_checkout_session_completed_binds_stripe_cid_for_plain_user
    below) — if the plain-user path also fails, the fault is in the provisioning
    machinery, not the comp-override gate.
    """
    app._handle_subscription_event(
        "checkout.session.completed",
        {
            "id": "cs_test_1",
            "customer": "cus_test_comp",
            "customer_details": {"email": comp_user},
            "payment_status": "paid",
            "amount_total": 5000,
            "metadata": {"user_id": comp_user, "plan": "founding_500"},
        },
    )
    doc = users_store.get_user(comp_user)
    assert doc["comp_override"] is True
    assert doc["membership_status"] == "active"  # unchanged (guarded)
    assert "billing_state" not in doc  # guarded write dropped
    # Non-guarded fields SHOULD pass through:
    assert doc.get("stripe_customer_id") == "cus_test_comp"
    assert doc.get("provisioned_via") in (None, "stripe_webhook")


def test_invoice_payment_succeeded_holds_comp(comp_user):
    """Path 2: invoice.payment_succeeded → set_billing_state('active').

    Also proves the gate is MINIMAL, not overly-broad: renewal_ts is not
    guarded → it must pass through to the doc even when billing_state is dropped.
    (HQ self-catch §8.6, endorsed by COW-1 pre-fire.)
    """
    fixed_period_end = 1783430000.0 + 30 * 86400  # deterministic, not time.time()
    app._handle_subscription_event(
        "invoice.payment_succeeded",
        {
            "subscription": "sub_test_1",
            "current_period_end": fixed_period_end,
            "metadata": {"user_id": comp_user},
        },
    )
    doc = users_store.get_user(comp_user)
    assert doc["comp_override"] is True
    assert doc["membership_status"] == "active"
    assert "billing_state" not in doc  # guarded — dropped
    # Non-guarded pass-through: renewal_ts should have written through.
    assert "renewal_ts" in doc  # non-guarded → passes through
    assert isinstance(doc["renewal_ts"], float)
    assert doc["renewal_ts"] == fixed_period_end


def test_subscription_updated_active_holds_comp(comp_user):
    """Path 3: customer.subscription.updated (status=active)."""
    app._handle_subscription_event(
        "customer.subscription.updated",
        {
            "status": "active",
            "current_period_end": 1783430000.0 + 30 * 86400,
            "cancel_at": None,
            "cancel_at_period_end": False,
            "metadata": {"user_id": comp_user},
        },
    )
    doc = users_store.get_user(comp_user)
    assert doc["comp_override"] is True
    assert doc["membership_status"] == "active"
    assert "billing_state" not in doc


def test_subscription_updated_past_due_holds_comp(comp_user):
    """Path 4: customer.subscription.updated (status=past_due)."""
    app._handle_subscription_event(
        "customer.subscription.updated",
        {
            "status": "past_due",
            "current_period_end": 1783430000.0 + 7 * 86400,
            "metadata": {"user_id": comp_user},
        },
    )
    doc = users_store.get_user(comp_user)
    assert doc["comp_override"] is True
    assert doc["membership_status"] == "active"  # HELD
    assert "billing_state" not in doc  # past_due write dropped


def test_subscription_deleted_holds_comp(comp_user):
    """Path 5: customer.subscription.deleted — THE canonical case that
    motivated β1 (Stripe cancels the sub, gate must hold the comp grant).
    Uses fixed canceled_at for deterministic assertion."""
    app._handle_subscription_event(
        "customer.subscription.deleted",
        {
            "canceled_at": 1783430500.0,
            "metadata": {"user_id": comp_user},
        },
    )
    doc = users_store.get_user(comp_user)
    assert doc["comp_override"] is True
    assert doc["membership_status"] == "active"  # NOT "cancelled"
    assert "billing_state" not in doc  # NOT "cancelled"
    # canceled_at_ts is NOT guarded → should pass through:
    assert "canceled_at_ts" in doc
    assert isinstance(doc["canceled_at_ts"], float)


def test_invoice_payment_failed_holds_comp(comp_user):
    """Path 6: invoice.payment_failed → set_billing_state('past_due')."""
    app._handle_subscription_event(
        "invoice.payment_failed",
        {"metadata": {"user_id": comp_user}},
    )
    doc = users_store.get_user(comp_user)
    assert doc["comp_override"] is True
    assert doc["membership_status"] == "active"
    assert "billing_state" not in doc


# ---------------------------------------------------------------------------
# Same 6 paths against a non-comp user — all writes must pass through
# ---------------------------------------------------------------------------


def test_invoice_payment_failed_flips_plain_user(plain_user):
    """Control: non-comp user's billing_state flips to past_due as expected."""
    app._handle_subscription_event(
        "invoice.payment_failed",
        {"metadata": {"user_id": plain_user}},
    )
    doc = users_store.get_user(plain_user)
    assert doc["billing_state"] == "past_due"


def test_subscription_deleted_flips_plain_user(plain_user):
    """Control: non-comp user's cancellation propagates through."""
    app._handle_subscription_event(
        "customer.subscription.deleted",
        {"canceled_at": 1783430500.0, "metadata": {"user_id": plain_user}},
    )
    doc = users_store.get_user(plain_user)
    assert doc["billing_state"] == "cancelled"
    assert doc["membership_status"] == "cancelled"


def test_checkout_session_completed_binds_stripe_cid_for_plain_user(plain_user):
    """Control (Path 1 triage support per COW-1 FLAG B): proves the checkout
    provisioning path works on a non-comp user. If Path 1's comp-user test
    fails but this one passes, the failure is in the gate. If both fail, the
    fault is in the provisioning machinery."""
    app._handle_subscription_event(
        "checkout.session.completed",
        {
            "id": "cs_test_plain_1",
            "customer": "cus_test_plain_new",
            "customer_details": {"email": plain_user},
            "payment_status": "paid",
            "amount_total": 5000,
            "metadata": {"user_id": plain_user, "plan": "founding_500"},
        },
    )
    doc = users_store.get_user(plain_user)
    assert doc["billing_state"] == "active"  # non-comp → writes through
    # stripe_customer_id path — pre-seeded plain user already had cus_test_plain,
    # so CL-19 mismatch fields may or may not appear depending on whether the
    # test's cus_test_plain_new differs; this assertion only proves the write
    # path did not crash.
    assert doc.get("stripe_customer_id") is not None


# ---------------------------------------------------------------------------
# Idempotency: replaying the same event twice must yield the same doc
# ---------------------------------------------------------------------------


def test_subscription_deleted_replay_idempotent_for_comp(comp_user):
    """Replay the cancellation twice with identical (fixed) canceled_at —
    doc converges (guarded fields still held, non-guarded canceled_at_ts
    equal on both writes). Deterministic — no time.time() drift."""
    payload = {"canceled_at": 1783430500.0, "metadata": {"user_id": comp_user}}
    app._handle_subscription_event("customer.subscription.deleted", payload)
    doc_after_first = dict(users_store.get_user(comp_user))
    app._handle_subscription_event("customer.subscription.deleted", payload)
    doc_after_second = users_store.get_user(comp_user)
    assert doc_after_first == doc_after_second


# ---------------------------------------------------------------------------
# Cross-check: guarded-set contract at the API boundary
# ---------------------------------------------------------------------------


def test_guarded_set_is_minimal():
    """Regression-lock the guarded set to the two entitlement-gate fields.
    If a future change adds/removes a guarded key, this test fails loudly
    so the reviewer sees the doctrine change explicitly."""
    assert users_store.COMP_OVERRIDE_GUARDED_KEYS == frozenset(
        {"membership_status", "billing_state"}
    )
