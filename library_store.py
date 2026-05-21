"""
ClarityOS library storage. Per-user authored entries (titled, taggable,
updatable). Distinct from the engine-owned GCS-backed /library route which
reads a global content bucket — that one is unchanged.

Document shape (collection: `library_user`, keyed by library_id):
    {
        "id":         <str>,
        "user":       <str>,
        "title":      <str>,
        "content":    <str>,
        "tags":       [<str>],
        "metadata":   <dict>,
        "size_bytes": <int>,
        "created_at": <float>,
        "updated_at": <float>,
    }

Backend selection follows the house pattern (CLARITYOS_BACKEND).
The collection is named `library_user` to avoid colliding with any future
top-level `library` collection that mirrors the GCS bucket index.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("clarityos.library_store")

_COLL = "library_user"


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
    logger.info("library_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


# ---------- Public API ------------------------------------------------------
def new_id() -> str:
    return "l_" + secrets.token_urlsafe(16)


def create(item_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).set(payload)
    else:
        _MEMORY[item_id] = dict(payload)


def get(item_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _coll().document(item_id).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY.get(item_id)


def update(item_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).set(payload)
    else:
        _MEMORY[item_id] = dict(payload)


def delete(item_id: str) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).delete()
    else:
        _MEMORY.pop(item_id, None)


def list_for_user(user: str, limit: int = 100) -> list[dict]:
    """Return this user's library entries, newest first. Firestore mode
    requires a composite index on (user ASC, created_at DESC)."""
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
