"""
DEWEY v3 embedding cache. Single Firestore collection: `embeddings_cache`.
Keyed by sha256(text). Documents never expire.

Document shape (per spec):
    {
        "vector":     list[float],   # L2-normalized
        "created_at": float,         # POSIX seconds
    }

This module follows the same backend-switch pattern as the rest of the
stores (memory mode for local dev, Firestore for prod). Failures on read
or write are logged and degrade to "cache miss" — DEWEY must never fail
a request because the cache is unhappy.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("clarityos.embeddings_cache_store")

_COLL = "embeddings_cache"


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
    logger.info("embeddings_cache_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


# ---------- Public API ------------------------------------------------------
def get(key: str) -> Optional[list[float]]:
    """Return the cached vector for `key`, or None if missing or on error."""
    if not key:
        return None
    try:
        if _backend() == "firestore":
            doc = _coll().document(key).get()
            if not doc.exists:
                return None
            data = doc.to_dict() or {}
            v = data.get("vector")
            return list(v) if v else None
        rec = _MEMORY.get(key)
        if rec and rec.get("vector"):
            return list(rec["vector"])
        return None
    except Exception as e:
        logger.warning("embeddings_cache get failed key=%s err=%s", key[:12], e)
        return None


def put(key: str, vector: list[float], created_at: float) -> None:
    """Store a cache entry. Failures logged but not raised."""
    if not key or not vector:
        return
    payload = {"vector": list(vector), "created_at": float(created_at)}
    try:
        if _backend() == "firestore":
            _coll().document(key).set(payload)
        else:
            _MEMORY[key] = payload
    except Exception as e:
        logger.warning("embeddings_cache put failed key=%s err=%s", key[:12], e)


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
