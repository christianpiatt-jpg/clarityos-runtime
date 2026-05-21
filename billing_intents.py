"""
v31 — PaymentIntent abstraction with idempotent webhook handling.

Three public functions:

    create_payment_intent(user_id, amount, description, kind, metadata=None) -> dict
        Creates a PaymentIntent (real Stripe in stripe mode; synthesized in
        mock mode) and persists it via membership_store.record_intent. The
        caller surfaces ``intent_id`` + ``client_secret`` to the client; the
        client confirms (Stripe.js or test helper) and the side-effect
        (credits, cohort add, etc.) is applied by the webhook handler.

    confirm_payment_intent(intent_id) -> dict
        Mock-only test helper. Synthesizes a ``payment_intent.succeeded``
        event and routes it through ``handle_payment_webhook``. In stripe
        mode this raises BillingError because confirmation is client-driven.

    handle_payment_webhook(event) -> dict
        Idempotent dispatcher. Looks up the intent by id, applies the
        appropriate side-effect on succeeded/failed, and updates the intent
        record. Re-running the same event is safe (returns the cached row).

Side effects per kind:

    "membership_activation": adds the user to the cohort, sets
                             membership_tier/price/status/started_ts,
                             billing_state=active, renewal_ts=now+30d.
    "membership_renewal":    extends renewal_ts by 30d, resets retry count.
    "g_credit_single":       adds 1 #G credit + tx record.
    "g_credit_pack":         adds 20 #G credits + tx record.

Failures don't mutate user state beyond the intent record + a
"failed_payment" transaction, except for ``membership_renewal`` which
walks the past_due / grace_period / cancelled state machine.

Environment:

    CLARITYOS_BILLING_MODE          "mock" (default) | "stripe"
    CLARITYOS_MOCK_AUTO_CONFIRM     "1" (default) | "0"
        When set to "1" in mock mode, ``create_payment_intent`` immediately
        synthesizes the success webhook and returns ``status: succeeded`` so
        legacy callers (v30 tests) get synchronous balance updates. Set to
        "0" to test the real async flow.

Logs are structured (event=value; no user content). Stripe signing is
delegated to ``billing.verify_webhook``; this module only consumes the
parsed event dict.
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

logger = logging.getLogger("clarityos.billing_intents")


VALID_KINDS = (
    "membership_activation",
    "membership_renewal",
    "g_credit_single",
    "g_credit_pack",
)

# Renewal cadence + retry policy. Module-level so tests can monkey-patch.
RENEWAL_PERIOD_DAYS = 30
RENEWAL_RETRY_HOURS = 24       # gap between retries
MAX_RENEWAL_RETRIES = 3
GRACE_PERIOD_HOURS = 24


class BillingError(Exception):
    """Raised on validation or stripe failures. Caller maps to HTTP code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------------------
# Mode helpers
# ---------------------------------------------------------------------------
def _mode() -> str:
    return os.environ.get("CLARITYOS_BILLING_MODE", "mock").lower()


def _mock_auto_confirm() -> bool:
    return os.environ.get("CLARITYOS_MOCK_AUTO_CONFIRM", "1") == "1"


def _new_mock_intent_id() -> str:
    return "pi_mock_" + secrets.token_urlsafe(12)


def _new_mock_client_secret(intent_id: str) -> str:
    return f"{intent_id}_secret_" + secrets.token_urlsafe(8)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate_inputs(user_id: str, amount: float, description: str, kind: str) -> tuple[str, float, str, str]:
    if not isinstance(user_id, str) or not user_id.strip():
        raise BillingError("bad_user", "user_id must be non-empty")
    try:
        amount = float(amount)
    except (TypeError, ValueError):
        raise BillingError("bad_amount", "amount must be a number")
    if amount < 0.50:
        # Stripe minimum charge in USD is $0.50; reject earlier so the
        # error message is actionable.
        raise BillingError("bad_amount", "amount must be >= 0.50")
    if not isinstance(description, str) or not description.strip():
        raise BillingError("bad_description", "description must be non-empty")
    if kind not in VALID_KINDS:
        raise BillingError("bad_kind", f"kind must be one of {sorted(VALID_KINDS)!r}")
    return user_id.strip(), float(amount), description.strip(), kind


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_payment_intent(
    user_id: str,
    amount: float,
    description: str,
    kind: str,
    metadata: Optional[dict] = None,
) -> dict:
    """Create a PaymentIntent. Returns a record dict containing
    ``intent_id``, ``client_secret``, ``status``, ``amount``, ``mode``,
    and the input ``kind`` + ``metadata``."""
    user_id, amount, description, kind = _validate_inputs(user_id, amount, description, kind)
    md = dict(metadata or {})
    md["user_id"] = user_id
    md["kind"] = kind

    record: dict = {
        "user": user_id,
        "amount": amount,
        "description": description,
        "kind": kind,
        "metadata": md,
        "status": "requires_payment_method",
        "side_effect_applied": False,
        "created_ts": time.time(),
        "mode": _mode(),
    }

    if _mode() == "stripe":
        # v42 — refuse early when no key is configured. Earlier versions
        # only raised when stripe.PaymentIntent.create rejected, which
        # leaked low-level errors to clients. The kernel/UI now surfaces
        # a clean 'billing_disabled' instead.
        try:
            import billing_config as _bc
        except ImportError:  # pragma: no cover (defensive)
            _bc = None
        stripe_key = (_bc.get_secret_key() if _bc else None) or os.environ.get("STRIPE_SECRET_KEY")
        if not stripe_key:
            raise BillingError(
                "billing_disabled",
                "Stripe is not configured. Set CLARITYOS_STRIPE_SECRET_KEY or STRIPE_SECRET_KEY.",
            )
        try:
            import stripe  # type: ignore
        except ImportError as e:
            raise BillingError("stripe_not_installed", "stripe SDK not installed") from e
        stripe.api_key = stripe_key
        # v42 — attach environment + cohort context to every intent so
        # webhook reconciliation can verify origin server-side.
        md["environment"] = _bc.get_stripe_mode() if _bc else "test"
        try:
            user_doc = users_store.get_user(user_id) or {}
            cohort = user_doc.get("cohort")
            if cohort:
                md["cohort"] = str(cohort)
            email = user_doc.get("email")
        except Exception:  # pragma: no cover (defensive)
            email = None
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(round(amount * 100)),  # cents
                currency="usd",
                metadata=md,
                description=description,
                automatic_payment_methods={"enabled": True},
                **({"receipt_email": email} if email else {}),
            )
        except Exception as e:  # pragma: no cover — exercised in stripe-mode integration
            raise BillingError("stripe_create_failed", f"Stripe rejected the intent: {e}")
        record["intent_id"] = intent.id
        record["client_secret"] = intent.client_secret
        record["status"] = intent.status
        record["environment"] = md.get("environment")
    else:
        record["intent_id"] = _new_mock_intent_id()
        record["client_secret"] = _new_mock_client_secret(record["intent_id"])
        record["environment"] = "mock"

    membership_store.record_intent(record)
    v29_hardening.log_event(
        "billing_intent_created",
        user=user_id,
        kind=kind,
        amount=amount,
        intent_id=record["intent_id"],
        mode=record["mode"],
        success=True,
    )

    if _mode() != "stripe" and _mock_auto_confirm():
        # Legacy auto-confirm — fire the synthetic webhook before returning so
        # callers get the side-effect immediately. The returned record is the
        # post-confirm version (status=succeeded, side_effect_applied=True).
        return confirm_payment_intent(record["intent_id"])

    return record


def confirm_payment_intent(intent_id: str) -> dict:
    """Synthesize a `payment_intent.succeeded` webhook for the given mock
    intent. Refuses in stripe mode (real confirmation happens client-side
    or via Stripe's own backend)."""
    intent = membership_store.get_intent(intent_id)
    if intent is None:
        raise BillingError("not_found", f"intent {intent_id!r} not found")
    if intent.get("status") == "succeeded":
        return intent  # idempotent
    if _mode() == "stripe":
        raise BillingError(
            "stripe_mode",
            "Cannot confirm intents server-side in stripe mode; use Stripe.js",
        )
    event = _build_synthetic_event(intent_id, "payment_intent.succeeded")
    return handle_payment_webhook(event)


def fail_payment_intent(intent_id: str, *, code: str = "card_declined") -> dict:
    """Mock-only test helper to drive the failure path."""
    intent = membership_store.get_intent(intent_id)
    if intent is None:
        raise BillingError("not_found", f"intent {intent_id!r} not found")
    if intent.get("status") == "failed":
        return intent
    if _mode() == "stripe":
        raise BillingError("stripe_mode", "Cannot fail intents server-side in stripe mode")
    event = _build_synthetic_event(intent_id, "payment_intent.payment_failed", failure_code=code)
    return handle_payment_webhook(event)


def handle_payment_webhook(event: dict) -> dict:
    """Idempotent webhook dispatcher. Returns the updated intent record (or
    a synthetic ``{ok: False, error: ...}`` envelope if the intent isn't
    known)."""
    if not isinstance(event, dict):
        return {"ok": False, "error": "bad_event"}
    event_type = str(event.get("type") or "")
    obj = (event.get("data") or {}).get("object") or {}
    intent_id = obj.get("id")
    if not intent_id:
        return {"ok": False, "error": "no_intent_id"}

    intent = membership_store.get_intent(intent_id)
    if intent is None:
        v29_hardening.log_event(
            "billing_webhook_unknown_intent",
            intent_id=str(intent_id), event_type=event_type, success=False,
        )
        return {"ok": False, "error": "intent_not_found"}

    user = intent["user"]
    kind = intent["kind"]
    current_status = intent.get("status")

    # Idempotency — bail out if already in the same terminal state. The
    # stored intent + its side-effect flag are both checked so we never
    # double-apply credits even if Stripe redelivers an event.
    if event_type == "payment_intent.succeeded" and current_status == "succeeded":
        return intent
    if event_type == "payment_intent.payment_failed" and current_status == "failed":
        return intent

    if event_type == "payment_intent.succeeded":
        intent["status"] = "succeeded"
        intent["confirmed_ts"] = time.time()
        membership_store.update_intent(intent_id, intent)
        if not intent.get("side_effect_applied"):
            _apply_succeeded(user, kind, intent)
            intent["side_effect_applied"] = True
            membership_store.update_intent(intent_id, intent)
        v29_hardening.log_event(
            "billing_intent_succeeded",
            user=user, kind=kind, intent_id=intent_id, amount=intent["amount"],
            success=True,
        )
        return intent

    if event_type == "payment_intent.payment_failed":
        intent["status"] = "failed"
        intent["failed_ts"] = time.time()
        intent["failure_code"] = obj.get("last_payment_error", {}).get("code") or "unknown"
        membership_store.update_intent(intent_id, intent)
        if not intent.get("side_effect_applied"):
            _apply_failed(user, kind, intent)
            intent["side_effect_applied"] = True
            membership_store.update_intent(intent_id, intent)
        v29_hardening.log_event(
            "billing_intent_failed",
            user=user, kind=kind, intent_id=intent_id, amount=intent["amount"],
            success=False, failure_code=intent.get("failure_code"),
        )
        return intent

    # Other events (canceled, processing, requires_action, etc.) — log + ignore.
    v29_hardening.log_event(
        "billing_webhook_other",
        user=user, kind=kind, intent_id=intent_id, event_type=event_type,
        success=True,
    )
    return intent


# ---------------------------------------------------------------------------
# Synthetic events
# ---------------------------------------------------------------------------
def _build_synthetic_event(intent_id: str, event_type: str, *, failure_code: Optional[str] = None) -> dict:
    intent = membership_store.get_intent(intent_id) or {}
    obj = {
        "id": intent_id,
        "amount": int(round(float(intent.get("amount", 0.0)) * 100)),
        "metadata": {
            "user_id": intent.get("user", ""),
            "kind": intent.get("kind", ""),
            **(intent.get("metadata") or {}),
        },
    }
    if event_type == "payment_intent.payment_failed":
        obj["last_payment_error"] = {"code": failure_code or "card_declined"}
    return {
        "id": "evt_mock_" + secrets.token_urlsafe(8),
        "type": event_type,
        "data": {"object": obj},
    }


# ---------------------------------------------------------------------------
# Side-effect helpers
# ---------------------------------------------------------------------------
def _apply_succeeded(user: str, kind: str, intent: dict) -> None:
    intent_id = intent["intent_id"]
    amount = float(intent["amount"])
    if kind == "g_credit_single":
        users_store.add_g_credits(user, 1, history_entry={
            "type": "g_credit_single",
            "credits_delta": 1,
            "amount": amount,
            "intent_id": intent_id,
            "ts": time.time(),
        })
        membership_store.record_transaction(
            user, type="g_credit_single", amount=amount, credits_delta=1,
            metadata={"intent_id": intent_id},
        )
        return
    if kind == "g_credit_pack":
        users_store.add_g_credits(user, 20, history_entry={
            "type": "g_credit_pack",
            "credits_delta": 20,
            "amount": amount,
            "intent_id": intent_id,
            "ts": time.time(),
        })
        membership_store.record_transaction(
            user, type="g_credit_pack", amount=amount, credits_delta=20,
            metadata={"intent_id": intent_id},
        )
        return
    if kind == "membership_activation":
        # The activation route stamps the user's membership fields after
        # creating the intent; the webhook only flips them to active and
        # joins the cohort. Keeping the cohort add here means the slot is
        # only consumed when a real payment lands.
        try:
            membership_store.add_member(user)
        except ValueError as e:
            # Race: cap filled between intent creation and webhook. Refund
            # is the right call but is out of v31 scope; record a failed
            # transaction so the operator can audit + manually refund.
            membership_store.record_transaction(
                user, type="failed_payment", amount=amount, credits_delta=0,
                metadata={"intent_id": intent_id, "reason": str(e), "race": True},
            )
            users_store.set_billing_state(user, billing_state="failed")
            return
        users_store.set_membership(
            user,
            tier=membership_store.FOUNDING_COHORT,
            price=amount,
            status="active",
            started_ts=time.time(),
        )
        users_store.set_billing_state(
            user,
            billing_state="active",
            renewal_ts=calculate_next_renewal_ts(time.time()),
            renewal_retry_count=0,
        )
        membership_store.record_transaction(
            user, type="membership_activation", amount=amount, credits_delta=0,
            metadata={"intent_id": intent_id, "cohort": membership_store.FOUNDING_COHORT},
        )
        return
    if kind == "membership_renewal":
        users_store.set_billing_state(
            user,
            billing_state="active",
            renewal_ts=calculate_next_renewal_ts(time.time()),
            renewal_retry_count=0,
        )
        membership_store.record_transaction(
            user, type="membership_renewal", amount=amount, credits_delta=0,
            metadata={"intent_id": intent_id},
        )
        return


def _apply_failed(user: str, kind: str, intent: dict) -> None:
    intent_id = intent["intent_id"]
    amount = float(intent["amount"])
    code = intent.get("failure_code") or "unknown"
    if kind in ("g_credit_single", "g_credit_pack"):
        membership_store.record_transaction(
            user, type="failed_payment", amount=amount, credits_delta=0,
            metadata={"intent_id": intent_id, "reason": code, "kind": kind},
        )
        return
    if kind == "membership_activation":
        membership_store.record_transaction(
            user, type="failed_payment", amount=amount, credits_delta=0,
            metadata={"intent_id": intent_id, "reason": code, "kind": kind},
        )
        users_store.set_billing_state(user, billing_state="failed")
        return
    if kind == "membership_renewal":
        # Walk the renewal state machine.
        doc = users_store.get_user(user) or {}
        retries = int(doc.get("renewal_retry_count") or 0) + 1
        membership_store.record_transaction(
            user, type="failed_payment", amount=amount, credits_delta=0,
            metadata={"intent_id": intent_id, "reason": code, "kind": kind, "retry": retries},
        )
        if retries < MAX_RENEWAL_RETRIES:
            users_store.set_billing_state(
                user,
                billing_state="past_due",
                renewal_ts=time.time() + RENEWAL_RETRY_HOURS * 3600,
                renewal_retry_count=retries,
            )
        else:
            users_store.set_billing_state(
                user,
                billing_state="grace_period",
                renewal_retry_count=retries,
                renewal_grace_until_ts=time.time() + GRACE_PERIOD_HOURS * 3600,
            )
        return


# ---------------------------------------------------------------------------
# Renewal helpers
# ---------------------------------------------------------------------------
def calculate_next_renewal_ts(ts: float) -> float:
    """Next renewal timestamp. Pure function so tests can compute without
    monkey-patching the clock."""
    return float(ts) + RENEWAL_PERIOD_DAYS * 86400.0
