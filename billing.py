"""
Stripe wrapper. Every entry point is gated on env-var presence; if the
Stripe environment is incomplete, calls raise BillingNotConfigured and
the routes return 503 to clients.

Required env (all four):
    STRIPE_SECRET_KEY          sk_live_... or sk_test_...
    STRIPE_PRICE_ONETIME       price_...   ($50 one-time)
    STRIPE_PRICE_RECURRING     price_...   ($50/mo recurring)
    STRIPE_WEBHOOK_SECRET      whsec_...   (set when the webhook endpoint is registered)

The flow this module supports:
    1. create_checkout_session(...) — invoked by /invite/{token}/checkout.
       Returns a Stripe-hosted checkout URL.
    2. retrieve_session(session_id) — invoked by /invite/{token}/finalize
       after Stripe redirects back; verifies the session was paid before
       the backend creates the user account.
    3. verify_webhook(payload, sig) — invoked by /billing/webhook for
       subscription lifecycle events (cancellation, payment failures).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("clarityos.billing")


class BillingNotConfigured(Exception):
    pass


def is_configured() -> bool:
    """v42 — secret key may now come from CLARITYOS_STRIPE_SECRET_KEY
    (preferred) or the legacy STRIPE_SECRET_KEY. Price ids are still
    required for the legacy invite/checkout flow."""
    import billing_config
    return bool(
        billing_config.get_secret_key()
        and os.environ.get("STRIPE_PRICE_ONETIME")
        and os.environ.get("STRIPE_PRICE_RECURRING")
    )


def is_webhook_configured() -> bool:
    """v42 — webhook secret may also come from
    CLARITYOS_STRIPE_WEBHOOK_SECRET. Price ids are NOT required for
    webhook validation; the new ``billing_config.is_billing_enabled()``
    is the source-of-truth for whether a key is present."""
    import billing_config
    return bool(billing_config.get_secret_key()) and bool(billing_config.get_webhook_secret())


def _stripe():
    import billing_config
    secret = billing_config.get_secret_key()
    if not secret or not is_configured():
        raise BillingNotConfigured(
            "Stripe is not configured. Set CLARITYOS_STRIPE_SECRET_KEY (or "
            "STRIPE_SECRET_KEY), STRIPE_PRICE_ONETIME, STRIPE_PRICE_RECURRING."
        )
    try:
        import stripe  # type: ignore
    except ImportError as e:
        raise BillingNotConfigured(
            "stripe SDK not installed. Add `stripe` to requirements.txt and redeploy."
        ) from e
    stripe.api_key = secret
    return stripe


def create_checkout_session(
    invite_id: str,
    username: str,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout Session and return its URL.

    plan: 'onetime' for $50 one-time (30-day access), 'recurring' for $50/mo subscription.
    """
    stripe = _stripe()
    if plan == "onetime":
        price_id = os.environ["STRIPE_PRICE_ONETIME"]
        mode = "payment"
    elif plan == "recurring":
        price_id = os.environ["STRIPE_PRICE_RECURRING"]
        mode = "subscription"
    else:
        raise ValueError(f"unknown plan: {plan!r}")

    session = stripe.checkout.Session.create(
        mode=mode,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url + ("&" if "?" in success_url else "?") + "session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
        client_reference_id=invite_id,
        metadata={"invite_id": invite_id, "username": username, "plan": plan},
    )
    return session.url


def create_membership_checkout_session(
    email: str, price_id: str, plan: str,
    success_url: str, cancel_url: str,
) -> str:
    """Public, email-only Stripe Checkout Session for the WP -> Stripe
    pipeline (C2). Subscription mode, Founding price.

    Inits Stripe via ``billing_config.get_secret_key()`` — deliberately
    NOT ``_stripe()``, whose ``is_configured()`` gate also requires the
    legacy ``STRIPE_PRICE_ONETIME``/``STRIPE_PRICE_RECURRING`` env vars
    and would raise ``BillingNotConfigured`` for the wrong reason.
    Explicit 503 path on a missing secret key.
    """
    import billing_config
    import stripe  # type: ignore
    secret = billing_config.get_secret_key()
    if not secret:
        raise BillingNotConfigured("Stripe secret key not configured")
    stripe.api_key = secret
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=email,
        client_reference_id=email,
        metadata={
            "user_id": email,
            "plan": plan,
            "source": "wp_button",
        },
        success_url=success_url + (
            "&" if "?" in success_url else "?"
        ) + "session_id={CHECKOUT_SESSION_ID}",
        cancel_url=cancel_url,
    )
    return session.url


def retrieve_session(session_id: str) -> dict:
    """Fetch a Checkout Session. Raises if Stripe rejects."""
    stripe = _stripe()
    return stripe.checkout.Session.retrieve(session_id)


def session_is_paid(session: dict) -> bool:
    """True iff the session's payment_status is 'paid' or it's a subscription
    that's now active."""
    status = session.get("payment_status")
    if status == "paid":
        return True
    # For subscription mode, payment_status may be 'no_payment_required' on the
    # initial session if the subscription is on a free trial. We don't currently
    # offer trials, so treat anything other than 'paid' as unpaid.
    return False


def verify_webhook(payload: bytes, sig_header: str) -> Optional[dict]:
    """Verify a Stripe webhook signature and return the parsed event.

    Returns None on signature mismatch. Raises BillingNotConfigured if
    the webhook secret isn't set.
    """
    import billing_config
    # C3 — webhook validation needs only the secret key (to init the SDK) and
    # the webhook signing secret. It must NOT route through _stripe(), whose
    # is_configured() gate also demands the legacy STRIPE_PRICE_ONETIME /
    # STRIPE_PRICE_RECURRING env vars (removed under Doctrine #74 LAD) and would
    # raise BillingNotConfigured for the wrong reason. Mirrors
    # create_membership_checkout_session (see the note at lines ~112-116).
    secret_key = billing_config.get_secret_key()
    if not secret_key:
        raise BillingNotConfigured("Stripe secret key not configured")
    try:
        import stripe  # type: ignore
    except ImportError as e:
        raise BillingNotConfigured(
            "stripe SDK not installed. Add `stripe` to requirements.txt and redeploy."
        ) from e
    stripe.api_key = secret_key
    secret = billing_config.get_webhook_secret()
    if not secret:
        raise BillingNotConfigured(
            "Webhook signing secret not set. Configure CLARITYOS_STRIPE_WEBHOOK_SECRET "
            "(or legacy STRIPE_WEBHOOK_SECRET) with the value from Stripe Dashboard.",
        )
    if not sig_header:
        # Empty/missing header is a rejection, not a configuration error.
        return None
    try:
        return stripe.Webhook.construct_event(payload, sig_header, secret)
    except Exception as e:
        # Log a NON-sensitive fingerprint so a live bad_signature can be triaged
        # without exposing the secret or payload. A wrong/quoted secret shows up
        # as an off secret_prefix/secret_len or a secret_fp that differs from the
        # endpoint's expected fingerprint; an empty payload or missing sig points
        # at a body/middleware problem instead (not the case for this handler).
        import hashlib
        secret_fp = hashlib.sha256(secret.encode("utf-8")).hexdigest()[:9] if secret else "none"
        logger.warning(
            "stripe webhook signature verification failed: %s "
            "(payload_len=%d sig_present=%s secret_len=%d secret_prefix=%r secret_fp=%s)",
            e, len(payload or b""), bool(sig_header), len(secret), secret[:6], secret_fp,
        )
        return None
