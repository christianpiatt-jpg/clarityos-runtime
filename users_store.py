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
from typing import Optional

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
        "user created username=%s tier=%s backend=%s", username, tier, _backend()
    )


def user_exists(username: str) -> bool:
    if _backend() == "firestore":
        return _users_collection().document(username).get().exists
    return username in _MEMORY_USERS


def update_user(username: str, data: dict) -> None:
    """Merge `data` into the existing user document. No-op if user not found."""
    if _backend() == "firestore":
        ref = _users_collection().document(username)
        if not ref.get().exists:
            logger.warning("update_user no such user username=%s", username)
            return
        ref.set(data, merge=True)
        return
    if username in _MEMORY_USERS:
        _MEMORY_USERS[username].update(data)
    else:
        logger.warning("update_user no such user username=%s", username)


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
#     g_credits               int   (current balance, never < 0)
#     g_credit_history        list  (compact metadata; full history is in
#                                    membership_store)
#
# "g_credit_history" on the user doc is a tail of the last ~50 events for
# fast UI render; the full history lives in membership_store transactions.
USER_DOC_HISTORY_TAIL = 50


def get_g_credit_balance(user: str) -> int:
    """Return current balance (0 for unknown users)."""
    doc = get_user(user) or {}
    try:
        return int(doc.get("g_credits") or 0)
    except (TypeError, ValueError):
        return 0


def add_g_credits(user: str, amount: int, *, history_entry: Optional[dict] = None) -> int:
    """Increment the balance and append a compact history record. Negative
    amounts are allowed for refunds; the consume_g_credit helper enforces
    the no-negative-balance invariant separately."""
    if not isinstance(amount, int):
        amount = int(amount)
    doc = get_user(user) or {}
    current = int(doc.get("g_credits") or 0)
    new_balance = current + amount
    history = list(doc.get("g_credit_history") or [])
    if history_entry is not None:
        history.append(dict(history_entry))
    if len(history) > USER_DOC_HISTORY_TAIL:
        history = history[-USER_DOC_HISTORY_TAIL:]
    update_user(user, {"g_credits": new_balance, "g_credit_history": history})
    return new_balance


def consume_g_credit(user: str, *, history_entry: Optional[dict] = None) -> int:
    """Decrement the balance by 1. Raises ValueError if the balance is 0."""
    doc = get_user(user) or {}
    current = int(doc.get("g_credits") or 0)
    if current <= 0:
        raise ValueError("no_credits")
    new_balance = current - 1
    history = list(doc.get("g_credit_history") or [])
    if history_entry is not None:
        history.append(dict(history_entry))
    if len(history) > USER_DOC_HISTORY_TAIL:
        history = history[-USER_DOC_HISTORY_TAIL:]
    update_user(user, {"g_credits": new_balance, "g_credit_history": history})
    return new_balance


def set_membership(
    user: str,
    *,
    tier: Optional[str],
    price: Optional[float],
    status: Optional[str],
    started_ts: Optional[float] = None,
    cancelled_ts: Optional[float] = None,
) -> None:
    """Apply membership fields. Pass None to clear a field. Atomic from the
    caller's perspective (one update_user call)."""
    payload: dict = {
        "membership_tier": tier,
        "membership_price": price,
        "membership_status": status,
    }
    if started_ts is not None:
        payload["membership_started_ts"] = float(started_ts)
    if cancelled_ts is not None:
        payload["membership_cancelled_ts"] = float(cancelled_ts)
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
        "g_credits": int(doc.get("g_credits") or 0),
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
