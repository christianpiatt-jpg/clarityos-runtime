"""
Membership store — Founding Cohort cap, waitlist, and transaction history.

Tracks two kinds of state:

1. Cohort-wide:
     {
       "founding_500": {
         "active_count": int,
         "members": list[str],            # active usernames
         "waitlist": list[{username, ts}],
       },
     }
   Stored as a single document so the cap check is one read.

2. Per-user transactions (one record per credit purchase / membership
   activation / membership cancel):
     {
       "user": str,
       "type": "membership_activate" | "membership_cancel"
              | "g_buy_single" | "g_buy_pack_20" | "g_consume",
       "amount": float,                   # USD; 0 for consume
       "credits_delta": int,              # +1, +20, -1, 0
       "metadata": dict,                  # {description, billing_id, etc.}
       "ts": float,
     }
   Per-user list bounded at MAX_TX_PER_USER (1000) to avoid unbounded
   growth; oldest dropped past the cap.

Backends: in-memory + Firestore, mirrors the rest of ClarityOS. The
membership user-document fields (membership_tier, membership_price,
membership_started_ts, membership_status, g_credits, g_credit_history)
live in `users_store` — this module is only the cohort-level state.

NEVER stores: scenario text, prompts, conversation content. Caller is
responsible for never passing such data; this module's metadata schema
is fixed (description / billing_id / source).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger("clarityos.membership_store")

_COHORT_COLL = "membership_cohorts"
_TX_COLL = "membership_transactions"
_INTENT_COLL = "membership_payment_intents"  # v31

# Founding cohort caps + price.
FOUNDING_COHORT = "founding_500"
FOUNDING_CAP = 500
FOUNDING_PRICE_LOCKED = 50.00
FOUNDING_FULL_PRICE = 150.00

MAX_TX_PER_USER = 1000


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


_MEMORY_COHORTS: dict[str, dict] = {}
_MEMORY_TX: dict[str, list] = {}
_MEMORY_INTENTS: dict[str, dict] = {}  # v31 — keyed by intent_id (global)
_firestore_client = None


def _get_firestore():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "CLARITYOS_BACKEND=firestore but google-cloud-firestore is not installed."
        ) from e
    _firestore_client = firestore.Client()
    logger.info("membership_store firestore client initialised")
    return _firestore_client


def _cohort_doc(name: str):
    return _get_firestore().collection(_COHORT_COLL).document(name)


def _tx_doc(user: str):
    return _get_firestore().collection(_TX_COLL).document(user)


def _empty_cohort() -> dict:
    return {"active_count": 0, "members": [], "waitlist": []}


def _load_cohort(name: str) -> dict:
    if _backend() == "firestore":
        doc = _cohort_doc(name).get()
        if doc.exists:
            data = doc.to_dict() or {}
            return {
                "active_count": int(data.get("active_count") or 0),
                "members": list(data.get("members") or []),
                "waitlist": list(data.get("waitlist") or []),
            }
        return _empty_cohort()
    return dict(_MEMORY_COHORTS.get(name) or _empty_cohort())


def _save_cohort(name: str, blob: dict) -> None:
    if _backend() == "firestore":
        _cohort_doc(name).set(blob)
    else:
        _MEMORY_COHORTS[name] = dict(blob)


# ---------------------------------------------------------------------------
# Cohort-level operations
# ---------------------------------------------------------------------------
def get_cohort_state(name: str = FOUNDING_COHORT) -> dict:
    """Return the cohort summary. Read-only."""
    blob = _load_cohort(name)
    return {
        "cohort": name,
        "active_count": blob["active_count"],
        "cap": FOUNDING_CAP if name == FOUNDING_COHORT else None,
        "remaining": (FOUNDING_CAP - blob["active_count"]) if name == FOUNDING_COHORT else None,
        "waitlist_count": len(blob["waitlist"]),
        "is_full": (name == FOUNDING_COHORT and blob["active_count"] >= FOUNDING_CAP),
    }


def is_cohort_full(name: str = FOUNDING_COHORT) -> bool:
    return get_cohort_state(name)["is_full"]


def add_member(user: str, name: str = FOUNDING_COHORT) -> dict:
    """Add user to cohort. Raises ValueError if full or already a member.
    Returns the updated cohort state."""
    blob = _load_cohort(name)
    if user in blob["members"]:
        raise ValueError("already_member")
    if name == FOUNDING_COHORT and blob["active_count"] >= FOUNDING_CAP:
        raise ValueError("cohort_full")
    blob["members"].append(user)
    blob["active_count"] = len(blob["members"])
    # Drop them off the waitlist if present.
    blob["waitlist"] = [w for w in blob["waitlist"] if w.get("username") != user]
    _save_cohort(name, blob)
    return get_cohort_state(name)


def remove_member(user: str, name: str = FOUNDING_COHORT) -> dict:
    """Remove user from cohort (cancellation). Idempotent."""
    blob = _load_cohort(name)
    if user not in blob["members"]:
        return get_cohort_state(name)
    blob["members"] = [u for u in blob["members"] if u != user]
    blob["active_count"] = len(blob["members"])
    _save_cohort(name, blob)
    return get_cohort_state(name)


def is_member(user: str, name: str = FOUNDING_COHORT) -> bool:
    return user in _load_cohort(name)["members"]


def add_to_waitlist(user: str, name: str = FOUNDING_COHORT) -> dict:
    """Append the user to the waitlist if they aren't already on it.
    Idempotent. Returns updated cohort state."""
    blob = _load_cohort(name)
    if any(w.get("username") == user for w in blob["waitlist"]):
        return get_cohort_state(name)
    blob["waitlist"].append({"username": user, "ts": time.time()})
    _save_cohort(name, blob)
    return get_cohort_state(name)


def waitlist_position(user: str, name: str = FOUNDING_COHORT) -> Optional[int]:
    """1-indexed position in the waitlist, or None if not on it."""
    blob = _load_cohort(name)
    for i, w in enumerate(blob["waitlist"]):
        if w.get("username") == user:
            return i + 1
    return None


# ---------------------------------------------------------------------------
# Per-user transaction history
# ---------------------------------------------------------------------------
def _load_tx(user: str) -> list:
    if _backend() == "firestore":
        doc = _tx_doc(user).get()
        if doc.exists:
            data = doc.to_dict() or {}
            return list(data.get("transactions") or [])
        return []
    return list(_MEMORY_TX.get(user) or [])


def _save_tx(user: str, txs: list) -> None:
    if _backend() == "firestore":
        _tx_doc(user).set({"transactions": txs})
    else:
        _MEMORY_TX[user] = list(txs)


def record_transaction(
    user: str,
    *,
    type: str,
    amount: float,
    credits_delta: int,
    metadata: Optional[dict] = None,
) -> dict:
    """Append a transaction. Returns the stored record."""
    txs = _load_tx(user)
    # Force strictly-monotonic ts (Windows time.time() resolution can return
    # equal floats for back-to-back calls; without this, "newest first"
    # ordering ties to insertion order and the contract becomes flaky).
    now = time.time()
    if txs:
        last_ts = float(txs[-1].get("ts", 0.0) or 0.0)
        if now <= last_ts:
            now = last_ts + 1e-6
    record = {
        "user": user,
        "type": str(type),
        "amount": float(amount),
        "credits_delta": int(credits_delta),
        "metadata": dict(metadata or {}),
        "ts": now,
    }
    txs.append(record)
    if len(txs) > MAX_TX_PER_USER:
        txs = txs[-MAX_TX_PER_USER:]
    _save_tx(user, txs)
    return record


def list_transactions(user: str, *, limit: int = 100) -> list:
    txs = _load_tx(user)
    txs = sorted(txs, key=lambda r: float(r.get("ts", 0.0)), reverse=True)
    return txs[: max(1, int(limit))]


# ---------------------------------------------------------------------------
# v31 — PaymentIntent storage
# ---------------------------------------------------------------------------
# Keyed globally by intent_id (PaymentIntents are unique per Stripe;
# our mock ids are also globally unique). Each record holds the user,
# kind, amount, status, and side-effect-applied flag for idempotency.
#
# Structure:
#   {
#     "intent_id": str,
#     "user": str,
#     "kind": str,                 # membership_activation | membership_renewal
#                                  # | g_credit_single | g_credit_pack
#     "amount": float,
#     "description": str,
#     "metadata": dict,
#     "status": str,               # requires_payment_method | processing
#                                  # | succeeded | failed | canceled
#     "client_secret": str | None, # mock secret or real Stripe one
#     "mode": str,                 # mock | stripe
#     "created_ts": float,
#     "confirmed_ts": float?,
#     "failed_ts": float?,
#     "side_effect_applied": bool, # idempotency guard
#   }
def _intent_doc(intent_id: str):
    return _get_firestore().collection(_INTENT_COLL).document(intent_id)


def record_intent(intent_record: dict) -> dict:
    """Persist a new PaymentIntent record (or replace if same id)."""
    intent_id = intent_record.get("intent_id")
    if not intent_id:
        raise ValueError("intent_id required")
    if _backend() == "firestore":
        _intent_doc(intent_id).set(intent_record)
    else:
        _MEMORY_INTENTS[intent_id] = dict(intent_record)
    return intent_record


def get_intent(intent_id: str) -> Optional[dict]:
    if not intent_id:
        return None
    if _backend() == "firestore":
        doc = _intent_doc(intent_id).get()
        return doc.to_dict() if doc.exists else None
    rec = _MEMORY_INTENTS.get(intent_id)
    return dict(rec) if rec is not None else None


def update_intent(intent_id: str, updates: dict) -> Optional[dict]:
    """Merge `updates` into the existing intent. Returns the updated record."""
    existing = get_intent(intent_id)
    if existing is None:
        return None
    existing.update(updates)
    if _backend() == "firestore":
        _intent_doc(intent_id).set(existing)
    else:
        _MEMORY_INTENTS[intent_id] = dict(existing)
    return existing


def list_intents_for_user(user: str, *, limit: int = 50) -> list:
    """Return this user's intents, most recent first."""
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        coll = _get_firestore().collection(_INTENT_COLL)
        q = coll.where(filter=FieldFilter("user", "==", user)).limit(int(limit) * 4)
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = [dict(r) for r in _MEMORY_INTENTS.values() if r.get("user") == user]
    rows.sort(key=lambda r: float(r.get("created_ts", 0.0)), reverse=True)
    return rows[: max(1, int(limit))]


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_memory_for_tests() -> None:
    _MEMORY_COHORTS.clear()
    _MEMORY_TX.clear()
    _MEMORY_INTENTS.clear()
