"""#59 — a paid Stripe checkout must SEAT the buyer, not just bill them.

Before this, the webhook did six of eight steps: it created the user,
bound the Stripe customer id, set billing_state="active", recorded the
transaction and sent the magic link — but never called
``membership_store.add_member`` or ``users_store.set_membership``.

``add_member`` is the only thing that increments the cohort counter, so
every webhook buyer had active billing and no seat. That is the measured
cause of #57: ``/public/cohort_status`` reads the cohort blob and
``app.py:3033`` counts user docs, and the two legitimately diverged.
#57 closes as resolved-by-#59 rather than as its own item — the three
cohort-count surfaces all read one derived value and cannot drift from
each other.

Cohort is the FOUNDING_COHORT default. CT-1 ruling A, 2026-08-25.
"""

import time

import pytest

from conftest import TestClient


@pytest.fixture
def client(reset_stores):
    import app as app_mod
    return TestClient(app_mod.app)


def _event(evt_id: str, email: str, amount: int = 5000) -> dict:
    return {
        "id": evt_id,
        "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_" + evt_id,
            "payment_status": "paid",
            "amount_total": amount,
            "customer_details": {"email": email},
            "metadata": {"plan": "founding"},
        }},
    }


def _post(client, event):
    return client.post(
        "/billing/webhook",
        json=event,
        headers={"Stripe-Signature": "t=0,v1=unused-in-mock-mode"},
    )


def test_paid_checkout_seats_the_buyer(client, monkeypatch):
    """1 — a paid checkout increments the cohort by exactly one."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import membership_store

    before = membership_store.get_cohort_state(
        membership_store.FOUNDING_COHORT)["active_count"]

    r = _post(client, _event("evt_seat_1", "seat1@example.com"))
    assert r.status_code == 200, r.json()

    after = membership_store.get_cohort_state(
        membership_store.FOUNDING_COHORT)["active_count"]
    assert after == before + 1, (
        f"cohort did not increment: {before} -> {after}. add_member is the "
        f"only thing that seats a buyer; if this fails the #59 regression "
        f"is back and paid customers are billed without a seat."
    )
    assert membership_store.is_member("seat1@example.com")


def test_paid_checkout_sets_membership_fields(client, monkeypatch):
    """2 — the user doc carries an active membership at the founding tier."""
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import membership_store
    import users_store

    r = _post(client, _event("evt_seat_2", "seat2@example.com", amount=5000))
    assert r.status_code == 200, r.json()

    doc = users_store.get_user("seat2@example.com") or {}
    assert doc.get("membership_status") == "active"
    assert doc.get("membership_tier") == membership_store.FOUNDING_COHORT
    assert doc.get("membership_price") == pytest.approx(50.0)
    assert doc.get("membership_started_ts")


def test_replay_does_not_double_seat(client, monkeypatch):
    """3 — idempotency. The same buyer seated twice stays at one seat.

    Two mechanisms protect this: the event-id dedup fast-path above the
    handler, and ``add_member`` raising ``already_member`` which the
    handler catches. This asserts the outcome, not which one fired — a
    second purchase by the same address uses a NEW event id and must
    still not double-seat.
    """
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import membership_store

    before = membership_store.get_cohort_state(
        membership_store.FOUNDING_COHORT)["active_count"]

    assert _post(client, _event("evt_replay_a", "dup@example.com")).status_code == 200
    mid = membership_store.get_cohort_state(
        membership_store.FOUNDING_COHORT)["active_count"]
    assert mid == before + 1

    # Distinct event id, same address — the event-id dedup does NOT
    # cover this; the already_member catch does.
    assert _post(client, _event("evt_replay_b", "dup@example.com")).status_code == 200
    after = membership_store.get_cohort_state(
        membership_store.FOUNDING_COHORT)["active_count"]
    assert after == mid, f"double-seated: {mid} -> {after}"


def test_renewal_matches_the_activate_path(client, monkeypatch):
    """5 — the webhook and /founder/membership/activate agree on renewal.

    ★ THIS TEST IS TRIVIALLY GREEN TODAY AND THAT IS NOT A REASON TO
      DELETE IT. Both paths currently compute the same 30 days:
        app.py (pre-#59)  time.time() + 30 * 24 * 3600.0   hardcoded
        billing_intents   ts + RENEWAL_PERIOD_DAYS * 86400  (= 30)
      The fold at #59 replaced the literal with the shared function, so
      the two can no longer diverge. This guards the FUTURE change to
      RENEWAL_PERIOD_DAYS, not a present defect. If someone edits that
      constant and only one path moves, this is what catches it.
    """
    monkeypatch.setenv("CLARITYOS_BILLING_MODE", "mock")
    import billing_intents
    import users_store

    t0 = time.time()
    r = _post(client, _event("evt_renew", "renew@example.com"))
    assert r.status_code == 200, r.json()

    doc = users_store.get_user("renew@example.com") or {}
    got = doc.get("billing_renewal_ts") or doc.get("renewal_ts")
    assert got, f"no renewal timestamp on the user doc: {sorted(doc)}"

    started = doc.get("membership_started_ts") or t0
    expected = billing_intents.calculate_next_renewal_ts(started)
    assert got == pytest.approx(expected, abs=5.0), (
        "webhook renewal_ts diverged from calculate_next_renewal_ts — the "
        "hardcoded 30-day literal is back, or RENEWAL_PERIOD_DAYS moved "
        "and only one path followed it."
    )
