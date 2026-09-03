"""
ClarityOS user storage layer.

Two backends, selected via the CLARITYOS_BACKEND environment variable:

    CLARITYOS_BACKEND=memory      (default) — in-process dict, wiped on restart
    CLARITYOS_BACKEND=firestore   — Google Cloud Firestore, persistent

Public API (the rest of the app never touches the backing store directly):

    get_user(username)        -> dict | None
    create_user(username, password_hash, salt, tier, created_at) -> None
    user_exists(username)     -> bool
    update_user(username, data) -> None

Document shape (memory dict and Firestore alike):

    {
        "username":      <str>,
        "password_hash": <bytes>   # bcrypt hash; salt is embedded
        "salt":          <str>     # reserved for non-bcrypt schemes; empty for bcrypt
        "tier":          <str>     # "free" | "paid" | ...
        "created_at":    <float>   # POSIX seconds
    }

google-cloud-firestore is imported lazily so memory mode keeps working
without the package installed.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional


def _uref(username: str) -> str:
    """A log-safe reference for a username. Usernames are EMAIL ADDRESSES
    for every magic-link account, and auth_magiclink's invariant is that
    the raw address never reaches a log line (#150 found this module's
    \"user created username=\" line breaking it on every birth). 16 hex of
    sha256, the same shape auth_magiclink._email_hash logs."""
    import hashlib
    return hashlib.sha256(str(username).encode("utf-8")).hexdigest()[:16]

logger = logging.getLogger("clarityos.users_store")

_USERS_COLLECTION = "users"


def _backend() -> str:
    """Read backend mode each time so tests can monkey-patch the env var."""
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


# ---------------------------------------------------------------------------
# In-memory backend (legacy behavior, wiped on restart)
# ---------------------------------------------------------------------------
_MEMORY_USERS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Firestore backend (lazy-init)
# ---------------------------------------------------------------------------
_firestore_client = None  # type: ignore


def _get_firestore():
    """Initialise the Firestore client on first use."""
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "CLARITYOS_BACKEND=firestore but google-cloud-firestore is not installed. "
            "Add `google-cloud-firestore` to requirements.txt or set CLARITYOS_BACKEND=memory."
        ) from e
    try:
        _firestore_client = firestore.Client()
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            f"Could not initialise Firestore client: {e}. "
            "On Cloud Run, attach a service account with roles/datastore.user. "
            "Locally, run `gcloud auth application-default login`."
        ) from e
    logger.info("users_store firestore client initialised")
    return _firestore_client


def _users_collection():
    return _get_firestore().collection(_USERS_COLLECTION)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_user(username: str) -> Optional[dict]:
    """Return the user document or None if no such user."""
    if _backend() == "firestore":
        doc = _users_collection().document(username).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY_USERS.get(username)


def create_user(
    username: str,
    password_hash,
    salt: str,
    tier: str,
    created_at: float,
) -> None:
    """
    Create a new user document. Caller is responsible for duplicate-checking
    via user_exists() first; this function will overwrite an existing doc
    if called twice for the same username.
    """
    payload = {
        "username": username,
        "password_hash": password_hash,
        "salt": salt,
        "tier": tier,
        "created_at": created_at,
    }
    if _backend() == "firestore":
        _users_collection().document(username).set(payload)
    else:
        _MEMORY_USERS[username] = payload
    logger.info(
        "user created user_ref=%s tier=%s backend=%s", _uref(username), tier, _backend()
    )


def user_exists(username: str) -> bool:
    if _backend() == "firestore":
        return _users_collection().document(username).get().exists
    return username in _MEMORY_USERS


# ---------------------------------------------------------------------------
# β1 — Comp-override gate (webhook_comp_override_durability)
# ---------------------------------------------------------------------------
# When a user document carries ``comp_override = True``, writes into
# ``update_user`` are inspected for keys that would mutate the founder comp
# grant. Guarded keys are dropped from the payload before merge; all other
# keys pass through unchanged. This holds the grant against Stripe webhook
# events (invoice.payment_failed, customer.subscription.deleted, etc.) while
# still letting the doc reflect Stripe's ground truth on informational
# fields (canceled_at_ts, cancel_at_ts, subscription_status, renewal_ts,
# stripe_customer_id, _cl19_mismatch_*, etc.).
#
# Guarded set is intentionally MINIMAL — only the two fields the entitlement
# read path uses to gate access.
COMP_OVERRIDE_GUARDED_KEYS = frozenset({"membership_status", "billing_state"})


def update_user(username: str, data: dict) -> None:
    """Merge `data` into the existing user document. No-op if user not found.

    β1 comp-override gate: if the target user carries ``comp_override = True``
    and ``data`` includes any key in ``COMP_OVERRIDE_GUARDED_KEYS``, those
    guarded keys are dropped from the merge (logged, not raised). Ungated
    keys pass through unchanged; empty resulting payload is a no-op.
    """
    if not isinstance(data, dict):
        # Defensive: preserve prior contract (dict merge only).
        raise TypeError(
            f"update_user expected dict, got {type(data).__name__}"
        )

    # Gate: inspect only when the payload could mutate guarded fields.
    guarded_hit = COMP_OVERRIDE_GUARDED_KEYS.intersection(data.keys())
    if guarded_hit:
        existing = get_user(username) or {}
        if bool(existing.get("comp_override")):
            filtered = {k: v for k, v in data.items()
                        if k not in COMP_OVERRIDE_GUARDED_KEYS}
            logger.warning(
                "update_user comp_override_hold user_ref=%s dropped_keys=%s "
                "dropped_values=%s remaining_keys=%s",
                _uref(username),
                sorted(guarded_hit),
                {k: data[k] for k in sorted(guarded_hit)},
                sorted(filtered.keys()),
            )
            data = filtered
            if not data:
                # All keys were guarded; nothing left to merge.
                return

    if _backend() == "firestore":
        ref = _users_collection().document(username)
        if not ref.get().exists:
            logger.warning("update_user no such user user_ref=%s", _uref(username))
            return
        ref.set(data, merge=True)
        return
    if username in _MEMORY_USERS:
        _MEMORY_USERS[username].update(data)
    else:
        logger.warning("update_user no such user user_ref=%s", _uref(username))


# ---------------------------------------------------------------------------
# v30 — Membership + #G credit helpers
# ---------------------------------------------------------------------------
# These add fields to the existing user document; firestore takes new keys
# transparently and memory dicts do too. The schema is:
#
#     membership_tier         str   ("founding_500", None)
#     membership_price        float (locked at activation; never increases)
#     membership_started_ts   float
#     membership_status       str   ("active", "cancelled", None)
#     membership_cancelled_ts float (when status flipped to cancelled)
#     balance_micro           int   (current balance in MICRO-DOLLARS, never < 0)
#     g_credits               int   FROZEN. The retired cent-resolution field.
#                                   Never read, never written by this module.
#                                   No conversion code exists or may be added:
#                                   the two live balances were set by hand under
#                                   CT-1 before the unit change landed.
#     g_credit_history        list  (compact metadata; full history is in
#                                    membership_store)
#
# "g_credit_history" on the user doc is a tail of the last ~50 events for
# fast UI render; the full history lives in membership_store transactions.
USER_DOC_HISTORY_TAIL = 50


def get_g_credit_balance(user: str) -> int:
    """Return the current balance in MICRO-DOLLARS (0 for unknown users).

    Reads ``balance_micro`` and nothing else. There is deliberately NO
    fallback to the retired ``g_credits`` field and no multiply anywhere in
    this module: with no conversion code, no code path exists that can
    inflate a balance. An account whose balance was never set reads zero --
    visible, recoverable, one ``add_g_credits`` away -- rather than silently
    reading 10,000x low or high.
    """
    doc = get_user(user) or {}
    try:
        return int(doc.get("balance_micro") or 0)
    except (TypeError, ValueError):
        return 0


def add_g_credits(user: str, amount: int, *, history_entry: Optional[dict] = None) -> int:
    """Increment the balance and append a compact history record. Negative
    amounts are allowed for refunds; the consume_g_credit helper enforces
    the no-negative-balance invariant separately."""
    if not isinstance(amount, int):
        amount = int(amount)
    doc = get_user(user) or {}
    current = int(doc.get("balance_micro") or 0)
    new_balance = current + amount
    history = list(doc.get("g_credit_history") or [])
    if history_entry is not None:
        history.append(dict(history_entry))
    if len(history) > USER_DOC_HISTORY_TAIL:
        history = history[-USER_DOC_HISTORY_TAIL:]
    update_user(user, {"balance_micro": new_balance, "g_credit_history": history})
    return new_balance


def consume_g_credit(user: str, *, history_entry: Optional[dict] = None) -> int:
    """Decrement the balance by 1. Raises ValueError if the balance is 0."""
    doc = get_user(user) or {}
    current = int(doc.get("balance_micro") or 0)
    if current <= 0:
        raise ValueError("no_credits")
    new_balance = current - 1
    history = list(doc.get("g_credit_history") or [])
    if history_entry is not None:
        history.append(dict(history_entry))
    if len(history) > USER_DOC_HISTORY_TAIL:
        history = history[-USER_DOC_HISTORY_TAIL:]
    update_user(user, {"balance_micro": new_balance, "g_credit_history": history})
    return new_balance


# ---------------------------------------------------------------------------
# Signup grant — CT-1 2026-08-26.
#
# 1500 credits at account creation. "One credit is one penny paid", so 1500
# credits is $15.00, which is 15,000,000 micro-dollars.
# ---------------------------------------------------------------------------
SIGNUP_GRANT_MICRO = 15_000_000


def grant_signup_credits(user: str, *, source: str = "account_creation") -> int:
    """Idempotently grant the signup balance. Returns the balance after.

    ★ The guard is the DATA, not a flag we have to remember to set: the
    grant writes ``signup_grant_ts`` in the same update as the balance, and
    a second call sees that field and no-ops. There is no version marker to
    forget and no script that can be re-run by accident -- the same shape
    CT-1 required of the (now deleted) conversion path.
    """
    doc = get_user(user) or {}
    if doc.get("signup_grant_ts"):
        return int(doc.get("balance_micro") or 0)
    current = int(doc.get("balance_micro") or 0)
    history = list(doc.get("g_credit_history") or [])
    history.append({
        "type": "signup_grant",
        "credits_delta": SIGNUP_GRANT_MICRO,
        "source": source,
        "ts": time.time(),
    })
    if len(history) > USER_DOC_HISTORY_TAIL:
        history = history[-USER_DOC_HISTORY_TAIL:]
    update_user(user, {
        "balance_micro": current + SIGNUP_GRANT_MICRO,
        "signup_grant_ts": time.time(),
        "g_credit_history": history,
    })
    # #154 -- a hash reference, never the address (usernames are emails)
    logger.info("signup grant user_ref=%s micro=%d source=%s",
                _uref(user), SIGNUP_GRANT_MICRO, source)
    return current + SIGNUP_GRANT_MICRO


_DEBITS_COLLECTION = "g_debits"
_MEMORY_DEBITS: dict = {}   # dev/test only; the firestore path is authoritative


def consume_g_credit_tx(user: str, request_id: str, *, cost: int = 1) -> dict:
    """Atomic, idempotent debit of ``cost`` credits keyed by ``request_id``.

    Returns ``{"remaining": int, "replay": bool, "terminal": bool}``. Raises
    ``ValueError("no_credits")`` when balance < cost and this request_id has
    not already been charged. Firestore path is transactional
    (concurrency-safe, no double-spend, no double-charge on replay); the
    memory path is a non-atomic dev/test fallback.

    D2 (R5) — terminality: a debit that has been *refunded* is terminal. A
    replay on a refunded ``request_id`` never re-charges; it returns
    ``{"replay": True, "terminal": True}`` so the caller can reject the reused
    key (HTTP 409) rather than silently re-billing. ``terminal`` is ``False`` on
    a fresh debit and on an ordinary (still-``charged``) replay. Both backends
    behave identically.
    """
    if not request_id:
        raise ValueError("missing_request_id")

    if _backend() != "firestore":
        rec = _MEMORY_DEBITS.get(request_id)
        if rec and rec.get("status") == "charged":
            return {"remaining": get_g_credit_balance(user), "replay": True, "terminal": False}
        if rec and rec.get("status") == "refunded":
            return {"remaining": get_g_credit_balance(user), "replay": True, "terminal": True}
        bal = get_g_credit_balance(user)
        if bal < cost:
            raise ValueError("no_credits")
        update_user(user, {"balance_micro": bal - cost})
        _MEMORY_DEBITS[request_id] = {"user": user, "cost": cost, "status": "charged"}
        return {"remaining": bal - cost, "replay": False, "terminal": False}

    from google.cloud import firestore  # lazy import, matches module convention
    client = _get_firestore()
    user_ref = _users_collection().document(user)
    debit_ref = client.collection(_DEBITS_COLLECTION).document(request_id)

    @firestore.transactional
    def _txn(txn):
        debit_snap = debit_ref.get(transaction=txn)   # all reads before writes
        user_snap = user_ref.get(transaction=txn)
        bal = int((user_snap.to_dict() or {}).get("balance_micro") or 0)
        if debit_snap.exists:
            status = (debit_snap.to_dict() or {}).get("status")
            if status == "charged":
                return {"remaining": bal, "replay": True, "terminal": False}   # idempotent no-op
            if status == "refunded":
                return {"remaining": bal, "replay": True, "terminal": True}    # R5 — terminal key
        if bal < cost:
            raise ValueError("no_credits")
        txn.update(user_ref, {"balance_micro": bal - cost})
        txn.set(debit_ref, {
            "user": user, "cost": cost, "status": "charged",
            "request_id": request_id, "ts": time.time(),
        })
        return {"remaining": bal - cost, "replay": False, "terminal": False}

    return _txn(client.transaction())


def peek_debit(request_id: str) -> dict:
    """READ-ONLY view of a debit key. Never writes, never claims.

    ★ Exists because claiming the key twice is a money bug. The metered
    dependency runs before the handler and needs to know whether a key is
    fresh, already charged, or terminal -- but if it *claims* the key with a
    zero-cost debit, the handler's later reserve sees ``replay: True`` and
    silently debits NOTHING, while settle still refunds against a reserve
    that was never taken. Net effect: every metered call PAYS the member.
    Measured before this existed: -48,780 micro-dollars per call.

    Returns ``{"exists": bool, "replay": bool, "terminal": bool}``.
    """
    if not request_id:
        return {"exists": False, "replay": False, "terminal": False}
    if _backend() != "firestore":
        rec = _MEMORY_DEBITS.get(request_id)
        if not rec:
            return {"exists": False, "replay": False, "terminal": False}
        st = rec.get("status")
        return {"exists": True, "replay": True, "terminal": st == "refunded"}
    client = _get_firestore()
    snap = client.collection(_DEBITS_COLLECTION).document(request_id).get()
    if not snap.exists:
        return {"exists": False, "replay": False, "terminal": False}
    st = (snap.to_dict() or {}).get("status")
    return {"exists": True, "replay": True, "terminal": st == "refunded"}


def refund_g_credit_tx(user: str, request_id: str, *, cost: int = 1) -> None:
    """Void a prior debit after a failed compute call. Idempotent: only a
    ``charged`` debit is refunded, then flipped to ``refunded`` so it can
    never refund twice.
    """
    if not request_id:
        return

    if _backend() != "firestore":
        rec = _MEMORY_DEBITS.get(request_id)
        if rec and rec.get("status") == "charged":
            update_user(user, {"balance_micro": get_g_credit_balance(user) + cost})
            rec["status"] = "refunded"
        return

    from google.cloud import firestore
    client = _get_firestore()
    user_ref = _users_collection().document(user)
    debit_ref = client.collection(_DEBITS_COLLECTION).document(request_id)

    @firestore.transactional
    def _txn(txn):
        debit_snap = debit_ref.get(transaction=txn)
        user_snap = user_ref.get(transaction=txn)
        if not debit_snap.exists or (debit_snap.to_dict() or {}).get("status") != "charged":
            return
        bal = int((user_snap.to_dict() or {}).get("balance_micro") or 0)
        txn.update(user_ref, {"balance_micro": bal + cost})
        txn.update(debit_ref, {"status": "refunded", "refunded_ts": time.time()})

    _txn(client.transaction())


# #123 -- "leave this field alone". The old default was None with an
# `is not None` guard, so the docstring's "pass None to clear" could never
# happen: a re-activation left membership_cancelled_ts standing (the
# founder's own doc read active + cancelled_ts set). A private sentinel
# separates "not passed" from "passed None".
_UNSET: Any = object()


def set_membership(
    user: str,
    *,
    tier: Optional[str],
    price: Optional[float],
    status: Optional[str],
    started_ts: Any = _UNSET,
    cancelled_ts: Any = _UNSET,
) -> None:
    """Apply membership fields. Atomic from the caller's perspective (one
    update_user call).

    started_ts / cancelled_ts: OMIT the argument to leave the stored field
    untouched; pass None EXPLICITLY to clear it (written as null, so a
    reader sees None); pass a float to set it. Every activation writer
    passes cancelled_ts=None so a re-activated member does not carry the
    timestamp of a cancellation that no longer holds (#123)."""
    payload: dict = {
        "membership_tier": tier,
        "membership_price": price,
        "membership_status": status,
    }
    if started_ts is not _UNSET:
        payload["membership_started_ts"] = None if started_ts is None else float(started_ts)
    if cancelled_ts is not _UNSET:
        payload["membership_cancelled_ts"] = None if cancelled_ts is None else float(cancelled_ts)
    update_user(user, payload)


def get_membership_view(user: str) -> dict:
    """Read-only view of the user's membership state, suitable for client
    rendering. Always returns a dict (never None) so the cockpit can
    render unconditionally."""
    doc = get_user(user) or {}
    return {
        "tier": doc.get("membership_tier"),
        "price": doc.get("membership_price"),
        "status": doc.get("membership_status"),
        "started_ts": doc.get("membership_started_ts"),
        "cancelled_ts": doc.get("membership_cancelled_ts"),
        "balance_micro": int(doc.get("balance_micro") or 0),
        # v31 — billing state machine fields
        "billing_state": doc.get("billing_state"),
        "renewal_ts": doc.get("renewal_ts"),
        "renewal_retry_count": int(doc.get("renewal_retry_count") or 0),
        "renewal_grace_until_ts": doc.get("renewal_grace_until_ts"),
    }


# ---------------------------------------------------------------------------
# v31 — Billing state machine helpers
# ---------------------------------------------------------------------------
# billing_state values:
#   "active"        — paid up; renewal_ts is the next charge date
#   "past_due"      — last renewal failed; in retry window (3 attempts / 72h)
#   "grace_period"  — retries exhausted; brief window for manual recovery
#   "cancelled"     — terminal (also flips membership_status to "cancelled")
#   "failed"        — initial activation never succeeded; rare
VALID_BILLING_STATES = ("active", "past_due", "grace_period", "cancelled", "failed")


def set_billing_state(
    user: str,
    *,
    billing_state: Optional[str] = None,
    renewal_ts: Optional[float] = None,
    renewal_retry_count: Optional[int] = None,
    renewal_grace_until_ts: Optional[float] = None,
) -> None:
    """Write any subset of the billing-state fields. Use `update_user` so
    other fields stay intact."""
    if billing_state is not None and billing_state not in VALID_BILLING_STATES:
        raise ValueError(
            f"billing_state must be one of {VALID_BILLING_STATES!r}, got {billing_state!r}"
        )
    payload: dict = {}
    if billing_state is not None:
        payload["billing_state"] = billing_state
    if renewal_ts is not None:
        payload["renewal_ts"] = float(renewal_ts)
    if renewal_retry_count is not None:
        payload["renewal_retry_count"] = int(renewal_retry_count)
    if renewal_grace_until_ts is not None:
        payload["renewal_grace_until_ts"] = float(renewal_grace_until_ts)
    if payload:
        update_user(user, payload)


def get_billing_state(user: str) -> Optional[str]:
    doc = get_user(user) or {}
    return doc.get("billing_state")


# ---------------------------------------------------------------------------
# C1 / A+D — Stripe Subscription fields (per-user; Stripe is the canonical
# renewal engine once a subscription exists).
# ---------------------------------------------------------------------------
# These coexist with the v31 billing_state machine. The renewal scheduler
# skips any user that carries a ``stripe_subscription_id`` (see
# billing_renewal.renew_membership) — Stripe's invoice.* webhooks drive that
# user's lifecycle instead.
#
#   stripe_customer_id      str   — Stripe Customer id  (cus_...)
#   stripe_subscription_id  str   — Stripe Subscription id (sub_...)
#   subscription_status     str   — mirrors Stripe (VALID_SUBSCRIPTION_STATUSES)
#   current_period_end_ts   int   — unix ts of period end ("renews on")
#   cancel_at_period_end    bool  — scheduled-cancellation flag
#   payment_action_required bool  — off-session SCA / recovery flag
VALID_SUBSCRIPTION_STATUSES = (
    "active", "trialing", "past_due", "unpaid",
    "canceled", "incomplete", "incomplete_expired",
)


def set_subscription(
    user: str,
    *,
    customer_id: Optional[str],
    subscription_id: Optional[str],
    status: Optional[str],
    current_period_end: Optional[int] = None,
    cancel_at_period_end: bool = False,
) -> None:
    """Write the full Stripe-subscription field set onto the user doc (first
    create / full sync). ``status`` is validated against
    VALID_SUBSCRIPTION_STATUSES (None allowed to leave it unset)."""
    if status is not None and status not in VALID_SUBSCRIPTION_STATUSES:
        raise ValueError(
            f"subscription_status must be one of {VALID_SUBSCRIPTION_STATUSES!r}, got {status!r}"
        )
    payload: dict = {
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": subscription_id,
        "subscription_status": status,
        "cancel_at_period_end": bool(cancel_at_period_end),
    }
    if current_period_end is not None:
        payload["current_period_end_ts"] = int(current_period_end)
    update_user(user, payload)


def update_subscription_status(
    user: str,
    *,
    status: Optional[str] = None,
    current_period_end: Optional[int] = None,
    cancel_at_period_end: Optional[bool] = None,
) -> None:
    """Partial subscription-field update (webhook sync). Only the fields
    passed are written; the rest stay intact."""
    if status is not None and status not in VALID_SUBSCRIPTION_STATUSES:
        raise ValueError(
            f"subscription_status must be one of {VALID_SUBSCRIPTION_STATUSES!r}, got {status!r}"
        )
    payload: dict = {}
    if status is not None:
        payload["subscription_status"] = status
    if current_period_end is not None:
        payload["current_period_end_ts"] = int(current_period_end)
    if cancel_at_period_end is not None:
        payload["cancel_at_period_end"] = bool(cancel_at_period_end)
    if payload:
        update_user(user, payload)


def mark_subscription_canceled(user: str) -> None:
    """Terminal cancellation (Stripe ``customer.subscription.deleted``):
    subscription_status=canceled + clear cancel_at_period_end. Stripe ids are
    kept for audit."""
    update_user(user, {
        "subscription_status": "canceled",
        "cancel_at_period_end": False,
    })


def mark_payment_action_required(user: str, required: bool) -> None:
    """Flag/unflag the off-session SCA recovery state surfaced to the UI."""
    update_user(user, {"payment_action_required": bool(required)})


def get_subscription_view(user: str) -> dict:
    """Read-only subscription snapshot for client rendering. Always a dict."""
    doc = get_user(user) or {}
    return {
        "stripe_customer_id": doc.get("stripe_customer_id"),
        "stripe_subscription_id": doc.get("stripe_subscription_id"),
        "subscription_status": doc.get("subscription_status"),
        "current_period_end_ts": doc.get("current_period_end_ts"),
        "cancel_at_period_end": bool(doc.get("cancel_at_period_end") or False),
        "payment_action_required": bool(doc.get("payment_action_required") or False),
    }


def find_user_by_stripe_customer_id(customer_id: str) -> Optional[str]:
    """Resolve a Stripe customer id back to a username. Used by the webhook
    handlers to map a Stripe object → our user. Returns None if unknown."""
    if not customer_id:
        return None
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        coll = _users_collection()
        q = coll.where(
            filter=FieldFilter("stripe_customer_id", "==", str(customer_id))
        ).limit(1)
        for doc in q.stream():
            data = doc.to_dict() or {}
            return data.get("username") or doc.id
        return None
    for username, data in _MEMORY_USERS.items():
        if data.get("stripe_customer_id") == customer_id:
            return username
    return None


def list_all_usernames() -> list[str]:
    """v43 — return every known username. Memory backend iterates the
    in-memory dict; Firestore backend streams the users collection.
    Used by the founder analytics aggregator."""
    if _backend() == "firestore":
        coll = _users_collection()
        out: list[str] = []
        for doc in coll.stream():
            data = doc.to_dict() or {}
            name = data.get("username") or doc.id
            if name:
                out.append(str(name))
        return out
    return list(_MEMORY_USERS.keys())


# ---------------------------------------------------------------------------
# #124 -- citizens are numbered, cohort is a range, the founder is a controller
#
# Six cohort strings read by four gates; paid members counted, not numbered.
# Now: every account that ever signed in holds a member_number from ONE
# global counter (minted at first login, never on create alone); `cohort` is
# a label DERIVED at read from the number (1-500 "founding", else "all",
# controller "controller"); citizenship is derived (active founding
# membership that was PAID, not granted); the founder is doc.controller.
# Writers stop writing cohort strings. A one-deploy SHIM lets the gates also
# accept the old strings -- delete next deploy.
# ---------------------------------------------------------------------------
FOUNDING_NUMBER_MAX = 500
FOUNDING_TIER = "founding_500"   # membership_store.FOUNDING_COHORT (literal: that module cannot be imported here without a cycle risk)
# one-deploy shim -- the old founder-like strings still open the gates
_LEGACY_CONTROLLER_COHORTS = frozenset({"founder", "founder_exception", "admin"})
_COUNTER_COLLECTION = "_meta"
_COUNTER_DOC = "member_counter"
_MEMORY_COUNTER: dict = {"next": 1}
_COUNTER_LOCK = threading.RLock()  # re-entrant: assign holds it while it mints
# The one-time numbering pass leaves a marker so it never numbers a doc born
# AFTER the migration (rule 1: those wait for their owner's first click).
_MARKER_DOC = "member_numbering"
_MEMORY_MARKER: dict = {"done_at": None}


def next_member_number() -> int:
    """Take the next number from the ONE global counter. Firestore: a
    transaction on _meta/member_counter; memory: a lock."""
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        client = _get_firestore()
        ref = client.collection(_COUNTER_COLLECTION).document(_COUNTER_DOC)

        @firestore.transactional
        def _take(tx):
            snap = ref.get(transaction=tx)
            nxt = int(((snap.to_dict() or {}).get("next") or 1)) if snap.exists else 1
            tx.set(ref, {"next": nxt + 1})
            return nxt

        return int(_take(client.transaction()))
    with _COUNTER_LOCK:
        n = int(_MEMORY_COUNTER["next"])
        _MEMORY_COUNTER["next"] = n + 1
        return n


def assign_member_number(username: str) -> Optional[int]:
    """Idempotent AND atomic: the doc's number if it has one, else mint the
    next and write it -- the check and the write are one transaction
    (Firestore: one tx over the user doc and the counter; memory: the
    counter lock held across the whole check-and-set), so two concurrent
    first logins for one address cannot burn a number. None when there is
    no doc. Called at FIRST LOGIN (verify_magic_link) and by the one-time
    deploy pass -- never on create."""
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        client = _get_firestore()
        counter_ref = client.collection(_COUNTER_COLLECTION).document(_COUNTER_DOC)
        user_ref = _users_collection().document(username)

        @firestore.transactional
        def _assign(tx):
            usnap = user_ref.get(transaction=tx)
            if not usnap.exists:
                return (None, False)
            have = (usnap.to_dict() or {}).get("member_number")
            if have:
                return (int(have), False)
            csnap = counter_ref.get(transaction=tx)
            nxt = int(((csnap.to_dict() or {}).get("next") or 1)) if csnap.exists else 1
            tx.set(counter_ref, {"next": nxt + 1})
            tx.update(user_ref, {"member_number": nxt})
            return (nxt, True)

        n, minted = _assign(client.transaction())
    else:
        with _COUNTER_LOCK:
            doc = get_user(username)
            if doc is None:
                return None
            have = doc.get("member_number")
            if have:
                return int(have)
            n = next_member_number()
            update_user(username, {"member_number": n})
            minted = True
    if minted and n is not None:
        logger.info("member_number.assigned user_ref=%s number=%d", _uref(username), n)
    return n


def is_controller(doc: Optional[dict]) -> bool:
    """The founder. doc.controller is the field; the legacy founder-like
    cohort strings are accepted for ONE deploy (shim) so nothing that opens
    today closes before the docs are flagged. Delete the shim next deploy."""
    d = doc or {}
    return bool(d.get("controller")) or (d.get("cohort") in _LEGACY_CONTROLLER_COHORTS)


def is_citizen(doc: Optional[dict]) -> bool:
    """CITIZEN = an active founding membership that was PAID for. A founder
    grant (membership_granted) does not confer citizenship (#124 rule 7)."""
    d = doc or {}
    return (d.get("membership_status") == "active"
            and d.get("membership_tier") == FOUNDING_TIER
            and not bool(d.get("membership_granted"))
            and not bool(d.get("comp_override")))  # a beta comp is a grant too


def derive_cohort(doc: Optional[dict]) -> str:
    """The label, derived at read: controller -> "controller"; number 1-500
    -> "founding" (the price lock); everything else -> "all"."""
    d = doc or {}
    if is_controller(d):
        return "controller"
    n = d.get("member_number")
    try:
        n = int(n) if n is not None else None
    except (TypeError, ValueError):
        n = None
    if n is not None and 1 <= n <= FOUNDING_NUMBER_MAX:
        return "founding"
    return "all"


_SUFFIX_OK = frozenset("abcdefghijklmnopqrstuvwxyz0123456789")


def citz_suffix(username: Optional[str]) -> str:
    """The first 3 chars of the email local part, lowercase; any char outside
    [a-z0-9] becomes "0" in place; shorter than 3 pads with "0". Display
    only, derived, never stored."""
    local = str(username or "").split("@", 1)[0].lower()
    first3 = local[:3].ljust(3, "0")
    return "".join(c if c in _SUFFIX_OK else "0" for c in first3)


def _number_of(doc: Optional[dict]) -> Optional[int]:
    """The doc's member number as an int, or None -- a malformed value is
    treated as unnumbered, never a 500."""
    n = (doc or {}).get("member_number")
    try:
        n = int(n) if n is not None else None
    except (TypeError, ValueError):
        return None
    return n if n and n > 0 else None


def citz_id(doc: Optional[dict]) -> Optional[str]:
    d = doc or {}
    n = _number_of(d)
    if not n:
        return None
    return f"citz-{n:06d}{citz_suffix(d.get('username'))}"


def identity_view(doc: Optional[dict]) -> dict:
    """What /me, /membership/state and the founder rows carry."""
    d = doc or {}
    n = _number_of(d)
    return {
        "member_number": n,
        "citizen":       is_citizen(d),
        "controller":    is_controller(d),
        "citz_id":       citz_id(d),
        "cohort":        derive_cohort(d),
    }


def numbering_done_at() -> Optional[float]:
    """When the one-time numbering pass first completed, or None."""
    if _backend() == "firestore":
        snap = _get_firestore().collection(_COUNTER_COLLECTION).document(_MARKER_DOC).get()
        return (snap.to_dict() or {}).get("done_at") if snap.exists else None
    return _MEMORY_MARKER.get("done_at")


def _set_numbering_done_at(ts: float) -> None:
    if _backend() == "firestore":
        _get_firestore().collection(_COUNTER_COLLECTION).document(_MARKER_DOC).set({"done_at": float(ts)})
    else:
        _MEMORY_MARKER["done_at"] = float(ts)


def _all_user_docs() -> list[dict]:
    if _backend() == "firestore":
        docs = []
        for doc in _users_collection().stream():
            data = doc.to_dict() or {}
            data.setdefault("username", doc.id)
            docs.append(data)
        return docs
    return [dict(d, username=d.get("username") or u) for u, d in _MEMORY_USERS.items()]


def number_existing_users(*, first=(), controllers=(), now: Optional[float] = None) -> list[tuple[str, int]]:
    """The ONE-TIME migration at deploy (rule 6), safe on every boot.

    Order of work, each step independent so a failure in one cannot leave
    the founder locked out by another:
      1. controllers flagged (controller=True) -- FIRST, before any numbering;
      2. legacy founder-like cohort strings migrated to the flag, so the
         one-deploy string shim can actually be deleted next deploy;
      3. numbering: `first` docs take the lowest numbers in order (the
         Outlook doc -> 1 on a fresh counter), then every unnumbered doc
         in created_at order -- but ONLY docs that existed when the pass
         first completed (the marker). A doc born after that waits for its
         owner's first click (rule 1), however many cold starts happen.
    A `first` / `controllers` entry with no doc is logged, not skipped
    silently. Returns [(username, number)] assigned THIS run; each
    assignment is logged as user_ref + number."""
    now = time.time() if now is None else float(now)
    assigned: list[tuple[str, int]] = []
    # 1. controllers, first and on their own
    for u in controllers:
        if not u:
            continue
        try:
            doc = get_user(u)
            if doc is None:
                logger.warning("controller.missing_doc user_ref=%s", _uref(u))
                continue
            if not doc.get("controller"):
                update_user(u, {"controller": True})
                logger.info("controller.flagged user_ref=%s", _uref(u))
        except Exception as exc:  # noqa: BLE001 -- one doc must not stop the rest
            logger.warning("controller.flag_failed user_ref=%s err=%s", _uref(u), type(exc).__name__)
    done_at = numbering_done_at()
    docs = _all_user_docs()
    # 2. legacy strings -> the flag (existing docs only; writers no longer write them)
    for d in docs:
        u = d.get("username")
        if u and d.get("cohort") in _LEGACY_CONTROLLER_COHORTS and not d.get("controller"):
            try:
                update_user(u, {"controller": True})
                logger.info("controller.migrated_from_cohort user_ref=%s", _uref(u))
            except Exception as exc:  # noqa: BLE001
                logger.warning("controller.migrate_failed user_ref=%s err=%s", _uref(u), type(exc).__name__)
    # 3. numbering
    for u in first:
        if not u:
            continue
        doc = get_user(u)
        if doc is None:
            logger.warning("member_numbering.first_missing_doc user_ref=%s", _uref(u))
            continue
        if not doc.get("member_number"):
            n = assign_member_number(u)
            if n:
                assigned.append((u, n))
    cutoff = done_at  # None on the first run: every existing doc qualifies
    already = {u for u, _ in assigned}  # the snapshot predates the `first` mints
    docs.sort(key=lambda d: float(d.get("created_at") or 0.0))
    for d in docs:
        u = d.get("username")
        if not u or d.get("member_number") or u in already:
            continue
        if cutoff is not None and float(d.get("created_at") or 0.0) >= cutoff:
            continue  # born after the migration: waits for the first click
        n = assign_member_number(u)
        if n:
            assigned.append((u, n))
    if done_at is None:
        _set_numbering_done_at(now)
    return assigned


def list_users(limit: int = 50, offset: int = 0) -> list[dict]:
    """#150 — a page of user docs, newest first by created_at. The founder
    console's members list. Memory backend sorts the dict; Firestore
    orders by the single field created_at (no composite index needed).
    Callers project the doc -- this returns it whole, secrets included,
    so never hand it to a client unprojected."""
    limit = max(1, int(limit))
    offset = max(0, int(offset))
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        q = (
            _users_collection()
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .offset(offset)
            .limit(limit)
        )
        out: list[dict] = []
        for doc in q.stream():
            data = doc.to_dict() or {}
            data.setdefault("username", doc.id)
            out.append(data)
        return out
    docs = [dict(d, username=d.get("username") or u) for u, d in _MEMORY_USERS.items()]
    docs.sort(key=lambda d: float(d.get("created_at") or 0.0), reverse=True)
    return docs[offset:offset + limit]


def list_users_due_for_renewal(now_ts: float) -> list[str]:
    """Memory-backend scan; firestore version uses a where clause."""
    out = []
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        coll = _users_collection()
        q = coll.where(filter=FieldFilter("renewal_ts", "<=", float(now_ts)))
        for doc in q.stream():
            data = doc.to_dict() or {}
            if data.get("billing_state") in ("active", "past_due", "grace_period"):
                out.append(data.get("username") or doc.id)
        return out
    for username, data in _MEMORY_USERS.items():
        rts = data.get("renewal_ts")
        bs = data.get("billing_state")
        if rts is None or bs not in ("active", "past_due", "grace_period"):
            continue
        if float(rts) <= float(now_ts):
            out.append(username)
    return out


# Test helper: clear in-memory state. Not used in production.
def _reset_memory_for_tests() -> None:
    _MEMORY_USERS.clear()
    _MEMORY_COUNTER["next"] = 1  # #124 -- the counter starts over with the users
    _MEMORY_MARKER["done_at"] = None
