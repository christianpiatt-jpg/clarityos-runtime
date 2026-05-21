"""
DEWEY neighborhoods store. One Firestore collection: `dewey_neighborhoods`.

Document shape:
    {
        "id": str,                       # nb_<token>
        "user": str,
        "name": str,                     # human label
        "query": str,                    # query text (used to derive origin_vector)
        "filters": dict,                 # domain / tag / kind constraints
        "origin_vector": list[float],    # embedding of `query`
        "λ_window": float,
        "curvature_threshold": float,
        "created_at": float,
        "updated_at": float,
    }
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Optional

logger = logging.getLogger("clarityos.dewey_neighborhoods_store")

_COLL = "dewey_neighborhoods"


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
    logger.info("dewey_neighborhoods_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


def new_id() -> str:
    return "nb_" + secrets.token_urlsafe(12)


def create(item_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).set(payload)
    else:
        _MEMORY[item_id] = dict(payload)


def update(item_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).set(payload)
    else:
        _MEMORY[item_id] = dict(payload)


def get(item_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _coll().document(item_id).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY.get(item_id)


def list_for_user(user: str, limit: int = 200) -> list[dict]:
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
