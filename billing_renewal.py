"""
v31 — Daily renewal scheduler.

Runs in the background (lazy daemon thread) and once every 24h scans for
users whose `renewal_ts <= now` and `billing_state in {active, past_due,
grace_period}`. For each due user:

* If `billing_state == "grace_period"` and `renewal_grace_until_ts <= now`:
  the grace window has ended without recovery — flip to terminal cancelled.
  ``membership_status`` is also set to "cancelled" + the user is removed from
  the cohort.
* Otherwise: create a `membership_renewal` PaymentIntent at the locked price.
  In mock mode + auto-confirm the side-effect lands inline; in real Stripe
  the webhook drives the rest of the state machine.

Public API:

    renew_membership(user_id, *, now_ts=None) -> dict
        Drive a single user's renewal lifecycle. Returns a small status
        dict (kind, action, intent_id?). Used by the scheduler and by tests.

    _renewal_one_pass(now_ts=None) -> dict
        Scan + drive every due user once. Returns counts. Tests call this
        directly without spawning the daemon.

    _ensure_renewal_scheduler_started()
        Lazy boot. Idempotent. Spawns one daemon thread per process.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional

import billing_intents
import membership_store
import users_store
import v29_hardening

logger = logging.getLogger("clarityos.billing_renewal")


# Tick cadence — 24h by default, overridable for tests.
RENEWAL_TICK_SECONDS = float(os.environ.get("CLARITYOS_RENEWAL_TICK_SECONDS", str(24 * 3600)))


_scheduler_started = False
_scheduler_lock: Optional[threading.Lock] = None


def calculate_next_renewal_ts(ts: float) -> float:
    """Re-export so callers don't need to import billing_intents."""
    return billing_intents.calculate_next_renewal_ts(ts)


def renew_membership(user_id: str, *, now_ts: Optional[float] = None) -> dict:
    """Drive a single user's renewal lifecycle. Returns a status dict.
    Idempotent in the sense that calling it on an up-to-date user is a
    no-op (returns ``{action: "no_op"}``)."""
    now = float(now_ts if now_ts is not None else time.time())
    doc = users_store.get_user(user_id) or {}

    # C1 / A+D — Stripe Subscriptions are the canonical renewal engine. A
    # subscription-backed member must NOT be renewed by this legacy scheduler;
    # Stripe's invoice.* webhooks drive their lifecycle. The PaymentIntent
    # renewal path below remains for any non-subscription members.
    if doc.get("stripe_subscription_id"):
        return {"user": user_id, "action": "no_op", "reason": "stripe_canonical"}

    state = doc.get("billing_state")
    rts = doc.get("renewal_ts")
    price = doc.get("membership_price")

    if state in (None, "cancelled", "failed"):
        return {"user": user_id, "action": "no_op", "reason": "not_renewable"}

    # Grace window expired?
    if state == "grace_period":
        grace_until = doc.get("renewal_grace_until_ts")
        if grace_until is not None and float(grace_until) <= now:
            _terminate_membership(user_id, reason="grace_expired")
            v29_hardening.log_event(
                "billing_renewal_terminated",
                user=user_id, reason="grace_expired", success=True,
            )
            return {"user": user_id, "action": "terminated", "reason": "grace_expired"}

    if rts is None or float(rts) > now:
        return {"user": user_id, "action": "no_op", "reason": "not_due"}

    if price is None or float(price) <= 0:
        return {"user": user_id, "action": "no_op", "reason": "no_price"}

    try:
        intent = billing_intents.create_payment_intent(
            user_id,
            float(price),
            f"Founding tier renewal ({user_id})",
            kind="membership_renewal",
            metadata={"renewal_due_ts": rts},
        )
    except billing_intents.BillingError as e:
        v29_hardening.log_event(
            "billing_renewal_create_failed",
            user=user_id, success=False, error=e.code,
        )
        return {"user": user_id, "action": "create_failed", "error": e.code}

    v29_hardening.log_event(
        "billing_renewal_intent_created",
        user=user_id, intent_id=intent["intent_id"],
        amount=intent["amount"], status=intent.get("status"),
        success=True,
    )
    return {
        "user": user_id,
        "action": "intent_created",
        "intent_id": intent["intent_id"],
        "status": intent.get("status"),
    }


def _terminate_membership(user_id: str, *, reason: str) -> None:
    """End-of-life transition: billing_state=cancelled, membership_status=
    cancelled, removed from cohort, transaction recorded."""
    users_store.set_membership(
        user_id,
        tier=(users_store.get_user(user_id) or {}).get("membership_tier"),
        price=(users_store.get_user(user_id) or {}).get("membership_price"),
        status="cancelled",
        cancelled_ts=time.time(),
    )
    users_store.set_billing_state(user_id, billing_state="cancelled")
    membership_store.remove_member(user_id)
    membership_store.record_transaction(
        user_id, type="membership_cancel", amount=0.0, credits_delta=0,
        metadata={"reason": reason, "automated": True},
    )


def _renewal_one_pass(now_ts: Optional[float] = None) -> dict:
    """Run the scheduler once. Returns counts. Public so tests can drive
    without spawning the daemon thread."""
    now = float(now_ts if now_ts is not None else time.time())
    due_users = users_store.list_users_due_for_renewal(now)
    summary = {"due": len(due_users), "intents": 0, "terminated": 0, "no_op": 0}
    for user in due_users:
        result = renew_membership(user, now_ts=now)
        action = result.get("action")
        if action == "intent_created":
            summary["intents"] += 1
        elif action == "terminated":
            summary["terminated"] += 1
        else:
            summary["no_op"] += 1
    if summary["intents"] or summary["terminated"]:
        logger.info(
            "renewal pass due=%d intents=%d terminated=%d no_op=%d at=%.0f",
            summary["due"], summary["intents"], summary["terminated"],
            summary["no_op"], now,
        )
    return summary


def _renewal_loop():  # pragma: no cover (spawned in a daemon thread)
    while True:
        try:
            _renewal_one_pass()
        except Exception as e:
            logger.warning("renewal scheduler tick failed err=%s", e)
        try:
            time.sleep(RENEWAL_TICK_SECONDS)
        except Exception:
            return


def _ensure_renewal_scheduler_started() -> None:
    """Lazy boot. Daemon thread; one per process; idempotent."""
    global _scheduler_started, _scheduler_lock
    if _scheduler_started:
        return
    if _scheduler_lock is None:
        _scheduler_lock = threading.Lock()
    with _scheduler_lock:
        if _scheduler_started:
            return
        t = threading.Thread(
            target=_renewal_loop,
            name="billing-renewal-scheduler",
            daemon=True,
        )
        t.start()
        _scheduler_started = True
        logger.info("billing renewal scheduler started (tick=%.0fs)", RENEWAL_TICK_SECONDS)


def _reset_for_tests() -> None:
    """Stop signalling the scheduler as started so tests can re-init."""
    global _scheduler_started
    _scheduler_started = False
