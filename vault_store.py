"""
ClarityOS vault storage. Per-user notes/sessions stored on the backend.

Document shape (collection: `vault`, keyed by vault_id):
    {
        "id":         <str>,    # vault_id (urlsafe token)
        "user":       <str>,    # owner; enforced at the route layer
        "type":       <str>,    # "note" | "session"
        "content":    <str>,    # body
        "tags":       [<str>],
        "metadata":   <dict>,   # passthrough (provider, clarity payload, etc.)
        "size_bytes": <int>,    # serialized JSON size, cached so deletes can
                                # decrement usage without re-fetching the doc
        "created_at": <float>,
    }

Same backend switch as users_store / sessions_store: CLARITYOS_BACKEND ∈
{memory, firestore}. Memory mode is for local dev; Firestore is prod.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("clarityos.vault_store")

_COLL = "vault"


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
    logger.info("vault_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


# ---------- Public API ------------------------------------------------------
def new_id() -> str:
    return "v_" + secrets.token_urlsafe(16)


def create(item_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).set(payload)
    else:
        _MEMORY[item_id] = dict(payload)


def update(item_id: str, payload: dict) -> None:
    """Full replacement of the doc — `set` semantics, same as create()."""
    if _backend() == "firestore":
        _coll().document(item_id).set(payload)
    else:
        _MEMORY[item_id] = dict(payload)


def get(item_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _coll().document(item_id).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY.get(item_id)


def delete(item_id: str) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).delete()
    else:
        _MEMORY.pop(item_id, None)


def list_for_user(user: str, limit: int = 100) -> list[dict]:
    """Return this user's items, sorted by created_at descending.

    Firestore mode requires a composite index on (user ASC, created_at DESC).
    The first query against an empty index will fail with a console URL to
    create it; click through once and the query becomes free.
    """
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = (
            _coll()
            .where(filter=FieldFilter("user", "==", user))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [doc.to_dict() for doc in q.stream()]
    items = [d for d in _MEMORY.values() if d.get("user") == user]
    items.sort(key=lambda d: d.get("created_at", 0), reverse=True)
    return items[:limit]


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
