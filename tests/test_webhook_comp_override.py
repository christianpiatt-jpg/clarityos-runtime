"""β1 — comp-override gate at users_store.update_user.

Covers the six webhook / admin write paths that could mutate a comp'd user's
membership_status or billing_state, plus positive-case tests that ungated
keys still flow through, and negative-case tests that non-comp users are
unaffected.
"""
from __future__ import annotations

import pytest

import users_store


@pytest.fixture(autouse=True)
def memory_backend(monkeypatch):
    """Force in-memory backend for these tests."""
    monkeypatch.setattr(users_store, "_backend", lambda: "memory")
    users_store._MEMORY_USERS.clear()
    yield
    users_store._MEMORY_USERS.clear()


@pytest.fixture
def comp_user():
    """Seed a comp'd founder-comp user matching the β1 A-write geometry."""
    users_store._MEMORY_USERS["comp@example.com"] = {
        "username": "comp@example.com",
        "email": "comp@example.com",
        "membership_status": "active",
        "membership_tier": "founding_500",
        "membership_price": 0,
        "g_credits": 100,
        "membership_confirmed": True,
        "comp_override": True,
        "comp_granted_by": "ct1_founder_comp_2026-07-07",
    }
    return "comp@example.com"


@pytest.fixture
def plain_user():
    """Seed a normal paying user (no comp_override)."""
    users_store._MEMORY_USERS["plain@example.com"] = {
        "username": "plain@example.com",
        "email": "plain@example.com",
        "membership_status": "active",
        "billing_state": "active",
        "membership_tier": "founding_500",
    }
    return "plain@example.com"


# --- Comp-override HOLDS on guarded fields --------------------------------

def test_set_billing_state_cancelled_blocked_for_comp_user(comp_user):
    """customer.subscription.deleted → set_billing_state('cancelled')."""
    users_store.set_billing_state(comp_user, billing_state="cancelled")
    doc = users_store.get_user(comp_user)
    assert "billing_state" not in doc  # guarded write dropped
    assert doc["membership_status"] == "active"


def test_set_billing_state_past_due_blocked_for_comp_user(comp_user):
    """invoice.payment_failed → set_billing_state('past_due')."""
    users_store.set_billing_state(comp_user, billing_state="past_due")
    doc = users_store.get_user(comp_user)
    assert "billing_state" not in doc


def test_set_billing_state_active_blocked_for_comp_user(comp_user):
    """checkout.session.completed → set_billing_state('active').
    Even the 'friendly' active write is blocked — a comp grant is inert to
    Stripe, and we do not want set_billing_state to touch it either way."""
    users_store.set_billing_state(comp_user, billing_state="active")
    doc = users_store.get_user(comp_user)
    assert "billing_state" not in doc


def test_set_membership_cancelled_blocked_for_comp_user(comp_user):
    """membership/cancel endpoint → set_membership(status='cancelled')."""
    users_store.set_membership(
        comp_user,
        tier="founding_500",
        price=0,
        status="cancelled",
        cancelled_ts=1783420269.0,
    )
    doc = users_store.get_user(comp_user)
    assert doc["membership_status"] == "active"  # unchanged
    # Ungated fields DO flow through:
    assert doc["membership_tier"] == "founding_500"
    assert doc["membership_cancelled_ts"] == 1783420269.0


def test_direct_update_user_bypass_blocked_for_comp_user(comp_user):
    """customer.subscription.deleted direct update_user bypass (app.py:1968)."""
    users_store.update_user(comp_user, {
        "membership_status": "cancelled",
        "canceled_at_ts": 1783420269.0,
    })
    doc = users_store.get_user(comp_user)
    assert doc["membership_status"] == "active"  # guarded, held
    assert doc["canceled_at_ts"] == 1783420269.0  # ungated, flows through


# --- Ungated fields flow through even for comp users ----------------------

def test_ungated_fields_flow_through_for_comp_user(comp_user):
    """renewal_ts, canceled_at_ts, stripe_customer_id, cohort fields, etc.
    must still land on comp'd users so audit trails remain intact."""
    users_store.update_user(comp_user, {
        "renewal_ts": 1783420269.0,
        "stripe_customer_id": "cus_TEST",
        "_cl19_mismatch_observed_at": "2026-07-07T10:31:09.326918Z",
        "onboarding": {"step": 2},
    })
    doc = users_store.get_user(comp_user)
    assert doc["renewal_ts"] == 1783420269.0
    assert doc["stripe_customer_id"] == "cus_TEST"
    assert doc["_cl19_mismatch_observed_at"] == "2026-07-07T10:31:09.326918Z"
    assert doc["onboarding"] == {"step": 2}
    # Guarded fields still untouched:
    assert doc["membership_status"] == "active"


def test_mixed_payload_drops_guarded_keeps_ungated(comp_user):
    """A single payload with both guarded and ungated keys: guarded dropped,
    ungated kept, no exception."""
    users_store.update_user(comp_user, {
        "billing_state": "cancelled",   # guarded → dropped
        "membership_status": "cancelled",  # guarded → dropped
        "canceled_at_ts": 999.0,        # ungated → kept
        "renewal_ts": None,             # ungated → kept
    })
    doc = users_store.get_user(comp_user)
    assert "billing_state" not in doc
    assert doc["membership_status"] == "active"
    assert doc["canceled_at_ts"] == 999.0
    assert doc["renewal_ts"] is None


# --- Comp-override does NOT affect normal users ---------------------------

def test_plain_user_billing_state_writes_normally(plain_user):
    users_store.set_billing_state(plain_user, billing_state="cancelled")
    doc = users_store.get_user(plain_user)
    assert doc["billing_state"] == "cancelled"


def test_plain_user_membership_status_writes_normally(plain_user):
    users_store.update_user(plain_user, {"membership_status": "cancelled"})
    doc = users_store.get_user(plain_user)
    assert doc["membership_status"] == "cancelled"


def test_plain_user_direct_bypass_writes_normally(plain_user):
    """Simulate customer.subscription.deleted for a real paying customer."""
    users_store.update_user(plain_user, {
        "membership_status": "cancelled",
        "canceled_at_ts": 1783420269.0,
    })
    doc = users_store.get_user(plain_user)
    assert doc["membership_status"] == "cancelled"
    assert doc["canceled_at_ts"] == 1783420269.0


# --- Defensive contract ---------------------------------------------------

def test_update_user_rejects_non_dict():
    with pytest.raises(TypeError):
        users_store.update_user("comp@example.com", "not-a-dict")


def test_guarded_only_payload_is_full_noop_for_comp_user(comp_user):
    """If every key in the payload is guarded, update_user returns without
    touching the doc at all."""
    before = dict(users_store._MEMORY_USERS[comp_user])
    users_store.update_user(comp_user, {
        "membership_status": "cancelled",
        "billing_state": "cancelled",
    })
    after = users_store._MEMORY_USERS[comp_user]
    assert after == before  # byte-identical


def test_comp_override_false_does_not_gate():
    """comp_override present but False → gate does NOT engage."""
    users_store._MEMORY_USERS["former@example.com"] = {
        "username": "former@example.com",
        "membership_status": "active",
        "comp_override": False,  # explicit False
    }
    users_store.update_user("former@example.com", {"membership_status": "cancelled"})
    assert users_store._MEMORY_USERS["former@example.com"]["membership_status"] == "cancelled"
