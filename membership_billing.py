"""
Membership billing abstraction.

Wraps the membership-related charging concerns (membership activation,
#G credit purchases) behind two functions that always succeed in mock
mode and route through the real Stripe path when configured.

Public API:

    charge(user_id, amount, description) -> dict
        Returns a billing record:
            {
              "ok": bool,
              "billing_id": str,    # stripe charge id, or "mock_..." in mock mode
              "amount": float,
              "description": str,
              "ts": float,
              "mode": "stripe" | "mock",
            }
        In mock mode this never fails. In stripe mode it raises
        BillingError on payment failure.

    record_transaction(user_id, amount, type, metadata) -> dict
        Persists a transaction row via membership_store. Thin shim so
        callers don't need to import membership_store directly.

This module never persists prompts, scenario text, or any user-generated
content — only billing metadata (description, billing id, amount).

CLARITYOS_BILLING_MODE controls behavior:
    "mock"   (default) — charge() returns a synthetic billing_id, real
                         money never moves.
    "stripe" — uses the existing billing.py Stripe wrapper. NOTE: the
                         Stripe wrapper's create_checkout_session is
                         hosted-checkout-only; one-tap charges aren't
                         implemented yet, so stripe mode currently raises
                         NotImplementedError (placeholder until v31).
"""
from __future__ import annotations

import logging
import os
import secrets
import time

import membership_store

logger = logging.getLogger("clarityos.membership_billing")


class BillingError(Exception):
    """Raised when a billing call fails. Caller maps to 402/503 etc."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _mode() -> str:
    return os.environ.get("CLARITYOS_BILLING_MODE", "mock").lower()


def _new_mock_billing_id() -> str:
    return "mock_" + secrets.token_urlsafe(10)


def charge(user_id: str, amount: float, description: str) -> dict:
    """Charge ``amount`` USD against the user's payment method.

    Mock mode:
        Always succeeds. Returns a billing record with a mock id. No
        money moves; suitable for test and the launch pre-payments path.

    Stripe mode:
        Currently raises ``NotImplementedError``. The full one-tap charge
        flow needs Stripe Customer + PaymentMethod plumbing that isn't
        in v30 scope; v30 ships with mock billing as the default."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise BillingError("bad_user", "user_id must be non-empty")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise BillingError("bad_amount", "amount must be a number")
    if amount < 0:
        raise BillingError("bad_amount", "amount must be non-negative")
    if not isinstance(description, str) or not description.strip():
        raise BillingError("bad_description", "description must be non-empty")

    mode = _mode()
    record = {
        "ok": True,
        "billing_id": _new_mock_billing_id() if mode != "stripe" else None,
        "amount": float(amount),
        "description": description,
        "ts": time.time(),
        "mode": mode,
    }

    if mode == "stripe":
        # Placeholder until v31 wires PaymentIntent.
        raise NotImplementedError(
            "Stripe one-tap charges require PaymentMethod plumbing not yet "
            "implemented. Set CLARITYOS_BILLING_MODE=mock for v30."
        )

    logger.info(
        "billing charge mode=%s user=%s amount=%.2f description=%s billing_id=%s",
        mode, user_id, amount, description, record["billing_id"],
    )
    return record


def record_transaction(
    user_id: str,
    *,
    amount: float,
    type: str,
    metadata: dict | None = None,
    credits_delta: int = 0,
) -> dict:
    """Persist a transaction row via membership_store. Returns the stored
    record for caller convenience (e.g. echoing the row back to the UI)."""
    return membership_store.record_transaction(
        user_id,
        type=type,
        amount=amount,
        credits_delta=credits_delta,
        metadata=metadata or {},
    )
