"""
C1 / A+D — Stripe Subscription orchestration (backend-only, additive).

Create + cancel Stripe Subscriptions for Founding-tier membership. Stripe is
the canonical renewal engine once a subscription exists (``billing_renewal``
skips subscription-backed members). Mirrors ``billing_intents.py``: mock mode
synthesizes ids/secrets so tests + the mock launch path keep working; stripe
mode uses the real SDK, gated on a configured key.

Public API:
    get_or_create_stripe_customer_id(user_id) -> str
    create_membership_subscription(user_id, price_id) -> {subscription_id, client_secret, status}
    cancel_subscription_immediately(user_id) -> None
    cancel_subscription_at_period_end(user_id) -> None

Deliberately NOT in this module (they land in Step 3+):
    * HTTP endpoints (/billing/subscription/*)
    * webhook handlers (invoice.*, customer.subscription.*)
    * SCA / payment-method-update flows

Env:
    CLARITYOS_BILLING_MODE   "mock" (default) | "stripe"
    Stripe key resolves via ``billing_config.get_secret_key()`` (v42) with the
    legacy ``STRIPE_SECRET_KEY`` fallback.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Optional

import membership_store
import users_store
import v29_hardening

logger = logging.getLogger("clarityos.billing_subscriptions")


class SubscriptionError(Exception):
    """Raised on validation / Stripe failures. Caller maps to an HTTP code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _mode() -> str:
    return os.environ.get("CLARITYOS_BILLING_MODE", "mock").lower()


def _new_mock_id(prefix: str) -> str:
    return f"{prefix}_mock_" + secrets.token_urlsafe(12)


def _stripe():
    """Return the configured Stripe SDK, or raise SubscriptionError. Mirrors
    billing_intents' key resolution (v42 name preferred, legacy fallback)."""
    try:
        import billing_config as _bc
    except ImportError:  # pragma: no cover (defensive)
        _bc = None
    key = (_bc.get_secret_key() if _bc else None) or os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        raise SubscriptionError(
            "billing_disabled",
            "Stripe is not configured. Set CLARITYOS_STRIPE_SECRET_KEY or STRIPE_SECRET_KEY.",
        )
    try:
        import stripe  # type: ignore
    except ImportError as e:
        raise SubscriptionError("stripe_not_installed", "stripe SDK not installed") from e
    stripe.api_key = key
    return stripe


def get_or_create_stripe_customer_id(user_id: str) -> str:
    """Return the user's Stripe customer id, creating one if missing.
    Idempotent: a user that already has ``stripe_customer_id`` returns it
    without a Stripe call."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise SubscriptionError("bad_user", "user_id must be non-empty")
    user_id = user_id.strip()
    doc = users_store.get_user(user_id) or {}
    existing = doc.get("stripe_customer_id")
    if existing:
        return str(existing)

    if _mode() == "stripe":
        stripe = _stripe()
        try:
            customer = stripe.Customer.create(
                metadata={"user_id": user_id},
                **({"email": doc.get("email")} if doc.get("email") else {}),
            )
        except Exception as e:  # pragma: no cover (stripe integration)
            raise SubscriptionError("stripe_customer_failed", f"Stripe rejected customer create: {e}")
        customer_id = customer.id
    else:
        customer_id = _new_mock_id("cus")

    users_store.update_user(user_id, {"stripe_customer_id": customer_id})
    v29_hardening.log_event(
        "stripe_customer_ensured", user=user_id, mode=_mode(), success=True,
    )
    return customer_id


def create_membership_subscription(user_id: str, price_id: str) -> dict:
    """Create a Stripe Subscription (SCA-ready via ``default_incomplete``) and
    persist the subscription fields onto the user doc. Returns
    ``{subscription_id, client_secret, status}``. The client confirms the
    returned ``client_secret`` (Stripe.js); activation to ``active`` happens
    later via the ``invoice.paid`` webhook (Step 3)."""
    if not isinstance(price_id, str) or not price_id.strip():
        raise SubscriptionError("bad_price", "price_id must be non-empty")
    price_id = price_id.strip()
    customer_id = get_or_create_stripe_customer_id(user_id)

    if _mode() == "stripe":
        stripe = _stripe()
        try:
            sub = stripe.Subscription.create(
                customer=customer_id,
                items=[{"price": price_id}],
                payment_behavior="default_incomplete",
                expand=["latest_invoice.payment_intent"],
                metadata={"user_id": user_id},
            )
        except Exception as e:  # pragma: no cover (stripe integration)
            raise SubscriptionError("stripe_subscription_failed", f"Stripe rejected subscription create: {e}")
        subscription_id = sub.id
        status = sub.status
        current_period_end = getattr(sub, "current_period_end", None)
        cancel_at_period_end = bool(getattr(sub, "cancel_at_period_end", False))
        # client_secret comes from the expanded latest_invoice.payment_intent.
        client_secret = None
        inv = getattr(sub, "latest_invoice", None)
        pi = getattr(inv, "payment_intent", None) if inv is not None else None
        if pi is not None:
            client_secret = getattr(pi, "client_secret", None)
    else:
        # Mock: default_incomplete-equivalent — the subscription stays
        # "incomplete" until the (mock) client_secret is confirmed. No
        # webhook yet, so nothing flips it to active in Step 2b.
        subscription_id = _new_mock_id("sub")
        status = "incomplete"
        current_period_end = None
        cancel_at_period_end = False
        client_secret = f"{_new_mock_id('pi')}_secret_" + secrets.token_urlsafe(8)

    users_store.set_subscription(
        user_id,
        customer_id=customer_id,
        subscription_id=subscription_id,
        status=status,
        current_period_end=current_period_end,
        cancel_at_period_end=cancel_at_period_end,
    )
    users_store.mark_payment_action_required(user_id, False)
    v29_hardening.log_event(
        "stripe_subscription_created", user=user_id, mode=_mode(),
        subscription_id=subscription_id, status=status, success=True,
    )
    return {
        "subscription_id": subscription_id,
        "client_secret": client_secret,
        "status": status,
    }


def _subscription_id_for(user_id: str) -> str:
    doc = users_store.get_user(user_id) or {}
    sid = doc.get("stripe_subscription_id")
    if not sid:
        raise SubscriptionError("no_subscription", "user has no Stripe subscription")
    return str(sid)


def cancel_subscription_immediately(user_id: str) -> None:
    """Cancel the subscription now (Stripe ``Subscription.delete``) and mark
    the user canceled. Stripe will also emit ``customer.subscription.deleted``;
    the webhook handler (Step 3) is idempotent against this local write."""
    sid = _subscription_id_for(user_id)
    if _mode() == "stripe":
        stripe = _stripe()
        try:
            stripe.Subscription.delete(sid)
        except Exception as e:  # pragma: no cover (stripe integration)
            raise SubscriptionError("stripe_cancel_failed", f"Stripe rejected cancel: {e}")
    users_store.mark_subscription_canceled(user_id)
    v29_hardening.log_event(
        "stripe_subscription_canceled", user=user_id, mode=_mode(),
        subscription_id=sid, immediate=True, success=True,
    )


def cancel_subscription_at_period_end(user_id: str) -> None:
    """Schedule cancellation at the period end (Stripe
    ``Subscription.modify(cancel_at_period_end=True)``). The membership stays
    active until ``current_period_end_ts``."""
    sid = _subscription_id_for(user_id)
    status = "active"
    current_period_end: Optional[int] = None
    if _mode() == "stripe":
        stripe = _stripe()
        try:
            sub = stripe.Subscription.modify(sid, cancel_at_period_end=True)
        except Exception as e:  # pragma: no cover (stripe integration)
            raise SubscriptionError("stripe_cancel_failed", f"Stripe rejected modify: {e}")
        status = getattr(sub, "status", "active")
        current_period_end = getattr(sub, "current_period_end", None)
    users_store.update_subscription_status(
        user_id, status=status, current_period_end=current_period_end,
        cancel_at_period_end=True,
    )
    v29_hardening.log_event(
        "stripe_subscription_cancel_scheduled", user=user_id, mode=_mode(),
        subscription_id=sid, success=True,
    )


# ---------------------------------------------------------------------------
# Webhook handlers (Step 3) — pure, idempotent state-sync from a Stripe event
# object onto the user doc. Stripe is canonical for subscription members, so
# each handler sets the new subscription fields AND mirrors the v31
# billing_state / membership so existing readers (entitlement_view,
# /me/billing, the membership UI) keep working. Users resolve by
# stripe_customer_id (invoices carry no metadata); subscription objects also
# carry metadata.user_id as a fallback. Unknown customer -> no-op (these must
# never raise out of the webhook).
# ---------------------------------------------------------------------------
_SUB_STATUS_TO_BILLING_STATE = {
    "active": "active",
    "trialing": "active",
    "past_due": "past_due",
    "unpaid": "past_due",
    "incomplete": "past_due",
    "incomplete_expired": "failed",
    "canceled": "cancelled",
}


def _resolve_user(obj: dict) -> Optional[str]:
    if not isinstance(obj, dict):
        return None
    customer = obj.get("customer")
    if customer:
        u = users_store.find_user_by_stripe_customer_id(str(customer))
        if u:
            return u
    md = obj.get("metadata") or {}
    uid = md.get("user_id")
    return str(uid) if uid else None


def _invoice_period_end(invoice: dict) -> Optional[int]:
    if not isinstance(invoice, dict):
        return None
    pe = invoice.get("period_end")
    if pe:
        return int(pe)
    lines = (invoice.get("lines") or {}).get("data") or []
    if lines:
        end = ((lines[0] or {}).get("period") or {}).get("end")
        if end:
            return int(end)
    return None


def handle_invoice_paid(invoice: dict) -> None:
    """``invoice.paid`` / ``invoice.payment_succeeded`` — the subscription is
    paid: activate (or renew) the member. Subscription fields -> active,
    billing_state -> active, membership + cohort ensured, action-required
    cleared. Idempotent on replay."""
    user = _resolve_user(invoice)
    if not user:
        logger.info("invoice.paid: unresolved customer=%s", (invoice or {}).get("customer"))
        return
    period_end = _invoice_period_end(invoice)
    users_store.update_subscription_status(user, status="active", current_period_end=period_end)
    users_store.mark_payment_action_required(user, False)
    users_store.set_billing_state(
        user, billing_state="active",
        renewal_ts=float(period_end) if period_end else None,
    )
    doc = users_store.get_user(user) or {}
    if doc.get("membership_status") != "active":
        users_store.set_membership(
            user, tier=membership_store.FOUNDING_COHORT,
            price=membership_store.FOUNDING_PRICE_LOCKED, status="active",
            started_ts=time.time(),
        )
        try:
            membership_store.add_member(user)
        except ValueError:
            pass  # already a member, or cap race — idempotent; operator audits
    v29_hardening.log_event("sub_invoice_paid", user=user, mode=_mode(), success=True)


def handle_invoice_payment_failed(invoice: dict) -> None:
    """``invoice.payment_failed`` — past_due + flag for attention. Crude
    off-session per the <=500-cohort scope: the operator resolves manually."""
    user = _resolve_user(invoice)
    if not user:
        return
    users_store.update_subscription_status(user, status="past_due")
    users_store.set_billing_state(user, billing_state="past_due")
    users_store.mark_payment_action_required(user, True)
    v29_hardening.log_event("sub_invoice_payment_failed", user=user, mode=_mode(), success=False)


def handle_subscription_updated(subscription: dict) -> None:
    """``customer.subscription.updated`` — mirror Stripe's truth (status,
    period end, cancel_at_period_end) onto the user + billing_state."""
    user = _resolve_user(subscription)
    if not user:
        return
    status = subscription.get("status")
    cpe = subscription.get("current_period_end")
    cape = subscription.get("cancel_at_period_end")
    cape_arg = bool(cape) if cape is not None else None
    try:
        users_store.update_subscription_status(
            user, status=status, current_period_end=cpe, cancel_at_period_end=cape_arg,
        )
    except ValueError:
        # Stripe status outside our enum — sync the rest, skip the status.
        users_store.update_subscription_status(
            user, current_period_end=cpe, cancel_at_period_end=cape_arg,
        )
    bs = _SUB_STATUS_TO_BILLING_STATE.get((status or "").lower())
    if bs is not None:
        kwargs: dict = {"billing_state": bs}
        if bs == "active" and cpe:
            kwargs["renewal_ts"] = float(cpe)
        users_store.set_billing_state(user, **kwargs)
    v29_hardening.log_event("sub_updated", user=user, mode=_mode(), success=True)


def handle_subscription_deleted(subscription: dict) -> None:
    """``customer.subscription.deleted`` — terminal cancellation: mark
    canceled, cancel membership, drop from the cohort."""
    user = _resolve_user(subscription)
    if not user:
        return
    users_store.mark_subscription_canceled(user)
    users_store.set_billing_state(user, billing_state="cancelled")
    doc = users_store.get_user(user) or {}
    users_store.set_membership(
        user, tier=doc.get("membership_tier"), price=doc.get("membership_price"),
        status="cancelled", cancelled_ts=time.time(),
    )
    try:
        membership_store.remove_member(user)
    except Exception:  # pragma: no cover (defensive)
        pass
    v29_hardening.log_event("sub_deleted", user=user, mode=_mode(), success=True)
