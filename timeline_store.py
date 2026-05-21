"""
ClarityOS timeline storage. Append-only per-user event log.

Document shape (collection: `timeline`, keyed by event_id):
    {
        "id":         <str>,
        "user":       <str>,
        "kind":       <str>,    # event class, e.g. "session", "ingestion", "note"
        "ref":        <str>,    # optional reference (vault_id, library_id, ...)
        "summary":    <str>,    # short human-readable description
        "ts":         <float>,  # event time (caller-supplied, may be backdated)
        "data":       <dict>,   # passthrough payload
        "size_bytes": <int>,
        "created_at": <float>,  # server write time
    }

Backend selection follows the house pattern (CLARITYOS_BACKEND).
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("clarityos.timeline_store")

_COLL = "timeline"


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


# ---------- In-memory backend -----------------------------------------------
_MEMORY: dict[str, dict] = {}


# ---------- Firestore backend (lazy-init) -----------------------------------
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
    try:
        _firestore_client = firestore.Client()
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"Could not initialise Firestore client: {e}") from e
    logger.info("timeline_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


# ---------- Public API ------------------------------------------------------
def new_id() -> str:
    return "t_" + secrets.token_urlsafe(16)


def create(event_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(event_id).set(payload)
    else:
        _MEMORY[event_id] = dict(payload)


def get(event_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _coll().document(event_id).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY.get(event_id)


def update(event_id: str, payload: dict) -> None:
    """Set semantics — same as create. Added for v3 backfill paths that
    need to write `object_vector` onto pre-existing timeline events."""
    if _backend() == "firestore":
        _coll().document(event_id).set(payload)
    else:
        _MEMORY[event_id] = dict(payload)


def list_for_user(
    user: str,
    kind: Optional[str] = None,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 100,
) -> list[dict]:
    """Return this user's timeline events, newest first.

    Filters (kind, since, until) are applied in Python AFTER fetching by
    user — that way only one composite index (user ASC, created_at DESC)
    is needed regardless of which filter combination the caller uses.
    Over-fetches when filters are present so the post-filter result still
    has a chance of returning `limit` entries.
    """
    fetch_limit = max(limit * 5, 500) if (kind or since is not None or until is not None) else limit
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = (
            _coll()
            .where(filter=FieldFilter("user", "==", user))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(fetch_limit)
        )
        items = [doc.to_dict() for doc in q.stream()]
    else:
        items = [d for d in _MEMORY.values() if d.get("user") == user]
        items.sort(key=lambda d: d.get("created_at", 0), reverse=True)
        items = items[:fetch_limit]
    if kind:
        items = [d for d in items if d.get("kind") == kind]
    if since is not None:
        items = [d for d in items if d.get("created_at", 0) >= since]
    if until is not None:
        items = [d for d in items if d.get("created_at", 0) <= until]
    return items[:limit]


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
