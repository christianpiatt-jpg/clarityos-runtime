"""
DEWEY memberships store. One Firestore collection: `dewey_memberships`.

Document shape:
    {
        "id":              str,    # mb_<token>
        "neighborhood_id": str,
        "object_id":       str,    # vault_id, library_id, or timeline_id
        "object_kind":     str,    # "vault" | "library" | "timeline"
        "user":            str,    # owner; redundant with neighborhood.user but lets us index by user without a join
        "similarity":      float,  # [0, 1]
        "created_at":      float,
    }
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("clarityos.dewey_memberships_store")

_COLL = "dewey_memberships"


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


_MEMORY: dict[str, dict] = {}
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
    logger.info("dewey_memberships_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


def new_id() -> str:
    return "mb_" + secrets.token_urlsafe(12)


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


def list_for_neighborhood(neighborhood_id: str, limit: int = 500) -> list[dict]:
    if _backend() == "firestore":
        from google.cloud import firestore  # type: ignore
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = (
            _coll()
            .where(filter=FieldFilter("neighborhood_id", "==", neighborhood_id))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [doc.to_dict() for doc in q.stream()]
    items = [d for d in _MEMORY.values() if d.get("neighborhood_id") == neighborhood_id]
    items.sort(key=lambda d: d.get("created_at", 0), reverse=True)
    return items[:limit]


def delete_for_neighborhood(neighborhood_id: str) -> int:
    """Remove all memberships for a neighborhood. Used by /refresh."""
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = _coll().where(filter=FieldFilter("neighborhood_id", "==", neighborhood_id))
        n = 0
        for doc in q.stream():
            doc.reference.delete()
            n += 1
        return n
    to_remove = [k for k, v in _MEMORY.items() if v.get("neighborhood_id") == neighborhood_id]
    for k in to_remove:
        _MEMORY.pop(k, None)
    return len(to_remove)


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
