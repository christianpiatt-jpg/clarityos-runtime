"""
Per-call vendor usage records — the billing audit trail.

One document per metered call (collection: ``usage_records``). This is the
only durable evidence of what a member was charged and why, so it records
the vendor's reported tokens, the rates in force at the time, and both
sides of the reserve/settle pair.

★ NAME NOTE: this is NOT ``usage_store``. That module is the per-user
STORAGE-BYTES quota counter (vault/library object bytes) and has nothing to
do with token billing. Two different meters, two different modules; the
near-collision is deliberate to keep apart.

Record shape:

    {
      "request_id":       str    idempotency key of the originating call
      "user":             str
      "endpoint":         str    e.g. "/me/threads/{id}/message"
      "model_id":         str    e.g. "openai:gpt-5.4"
      "provider":         str
      "prompt_tokens":    int    UNCACHED prompt tokens
      "cached_tokens":    int    prompt tokens served from vendor cache
      "completion_tokens":int
      "calls":            int    vendor calls folded into this turn (retries)
      "estimated":        bool   True if tokens were guessed, not reported
      "reserve_micro":    int
      "settle_micro":     int
      "delta_micro":      int    settle - reserve
      "vendor_micro":     int    vendor tokens only
      "service_micro":    int    our cost to serve
      "total_cost_micro": int    vendor + service  (the invariant denominator)
      "rates_micro_per_million": dict
      "ts":               float
    }

Two backends, matching every other store in this codebase:
``CLARITYOS_BACKEND=memory`` (default) or ``firestore``.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger("clarityos.usage_records")

_COLL = "usage_records"


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


_MEMORY: list[dict] = []
_firestore_client = None


def _get_firestore():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    from google.cloud import firestore  # type: ignore
    _firestore_client = firestore.Client()
    logger.info("usage_records firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


def record(
    *,
    request_id: str,
    user: str,
    endpoint: str,
    breakdown: dict,
    reserve_micro: int,
    calls: int = 1,
) -> dict:
    """Persist one settled call. ``breakdown`` is usage_billing.describe().

    ★ Best-effort by design: a storage failure must never fail a call the
    member already paid for and already received. The debit is
    transactional; this record is the audit trail beside it, and losing a
    row is a reporting problem, not a money problem. Failures are logged
    loudly so they can be reconciled from the debit ledger.
    """
    doc = {
        "request_id": request_id,
        "user": user,
        "endpoint": endpoint,
        "model_id": breakdown.get("model_id"),
        "provider": breakdown.get("provider"),
        "prompt_tokens": int(breakdown.get("prompt_tokens") or 0),
        "cached_tokens": int(breakdown.get("cached_tokens") or 0),
        "completion_tokens": int(breakdown.get("completion_tokens") or 0),
        "calls": int(calls),
        "estimated": bool(breakdown.get("estimated")),
        "reserve_micro": int(reserve_micro),
        "settle_micro": int(breakdown.get("debited_micro") or 0),
        "delta_micro": int(breakdown.get("debited_micro") or 0) - int(reserve_micro),
        "vendor_micro": int(breakdown.get("vendor_micro") or 0),
        "service_micro": int(breakdown.get("service_micro") or 0),
        "total_cost_micro": int(breakdown.get("total_cost_micro") or 0),
        "line_items_micro": dict(breakdown.get("line_items_micro") or {}),
        "rates_micro_per_million": dict(breakdown.get("rates_micro_per_million") or {}),
        "invariant_holds": bool(breakdown.get("invariant_holds")),
        "ts": time.time(),
    }
    try:
        if _backend() == "firestore":
            # Keyed by request_id so a replayed settle overwrites rather than
            # duplicating — matches the debit ledger's idempotency.
            _coll().document(request_id).set(doc)
        else:
            _MEMORY[:] = [d for d in _MEMORY if d["request_id"] != request_id]
            _MEMORY.append(doc)
    except Exception as e:  # pragma: no cover — defensive
        logger.warning("usage_records persist failed request_id=%s err=%s", request_id, e)
    return doc


def get(request_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        snap = _coll().document(request_id).get()
        return snap.to_dict() if snap.exists else None
    for d in _MEMORY:
        if d["request_id"] == request_id:
            return d
    return None


def list_for_user(user: str, limit: int = 50) -> list[dict]:
    """Newest-first usage rows for one member."""
    if _backend() == "firestore":
        q = _coll().where("user", "==", user).order_by(
            "ts", direction="DESCENDING").limit(int(limit))
        return [d.to_dict() for d in q.stream()]
    rows = [d for d in _MEMORY if d.get("user") == user]
    rows.sort(key=lambda d: d.get("ts") or 0.0, reverse=True)
    return rows[:int(limit)]


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
