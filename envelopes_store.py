"""
Envelope Base Layer — one Firestore doc per user.

Document shape (collection: `envelopes`, doc id = username):
    {
        "user":            str,
        "elins_briefs":    list[dict],   # each: {brief_id, object_vector, decay_rate, last_reference_timestamp}
        "envelope_vector": list[float] | None,
        "updated_at":      float,
    }

Mutation policy: callers overwrite the whole doc (`set` semantics) per spec.
No decay logic in this layer — that lands in a later block.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("clarityos.envelopes_store")

_COLL = "envelopes"


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
    logger.info("envelopes_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


def get(user: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _coll().document(user).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY.get(user)


def set_envelope(user: str, payload: dict) -> None:
    """Overwrite the entire envelope doc. Caller is responsible for any
    field-level merge logic (this layer is plain set semantics per spec)."""
    if _backend() == "firestore":
        _coll().document(user).set(payload)
    else:
        _MEMORY[user] = dict(payload)


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
