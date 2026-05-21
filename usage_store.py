"""
ClarityOS per-user storage usage counter.

One document per user (collection: `usage`, keyed by username):
    {
        "user":       <str>,
        "bytes_used": <int>,    # may briefly drift on concurrent writes;
                                # high quota ceilings make that acceptable
        "updated_at": <float>,
    }

Public API:

    get_bytes(user)         -> int   (returns 0 if no doc yet)
    add_bytes(user, delta)  -> int   (atomic in firestore mode; returns
                                      best-effort post-update value)
    set_bytes(user, value)  -> None  (admin reset; not used by routes today)

Counter is kept in a single doc per user — Firestore's atomic Increment
takes care of the common case where two writes from the same user race.
We do NOT use a transaction for the read-then-write pattern in `assert_quota`;
under the 500 MB / 1 GB ceilings, occasional drift of a few KB is fine.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger("clarityos.usage_store")

_COLL = "usage"


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


# ---------- In-memory backend -----------------------------------------------
_MEMORY: dict[str, dict] = {}


# ---------- Firestore backend (lazy-init) -----------------------------------
_firestore_client = None
_firestore_module = None


def _get_firestore():
    global _firestore_client, _firestore_module
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
        _firestore_module = firestore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"Could not initialise Firestore client: {e}") from e
    logger.info("usage_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


# ---------- Public API ------------------------------------------------------
def get_bytes(user: str) -> int:
    if _backend() == "firestore":
        doc = _coll().document(user).get()
        if not doc.exists:
            return 0
        return int((doc.to_dict() or {}).get("bytes_used", 0))
    rec = _MEMORY.get(user)
    return int(rec.get("bytes_used", 0)) if rec else 0


def add_bytes(user: str, delta: int) -> int:
    """Increment (or decrement, with negative delta) the user's counter."""
    if _backend() == "firestore":
        _get_firestore()  # populate _firestore_module
        ref = _coll().document(user)
        snap = ref.get()
        if not snap.exists:
            initial = max(0, int(delta))
            ref.set({"user": user, "bytes_used": initial, "updated_at": time.time()})
            return initial
        ref.update({
            "bytes_used": _firestore_module.Increment(int(delta)),  # type: ignore[union-attr]
            "updated_at": time.time(),
        })
        # Best-effort post-update read; not strictly atomic with the increment
        # above, but good enough for response payloads.
        post = ref.get().to_dict() or {}
        used = int(post.get("bytes_used", 0))
        if used < 0:
            ref.update({"bytes_used": 0})
            used = 0
        return used
    rec = _MEMORY.get(user) or {"user": user, "bytes_used": 0, "updated_at": 0.0}
    rec["bytes_used"] = max(0, int(rec.get("bytes_used", 0)) + int(delta))
    rec["updated_at"] = time.time()
    _MEMORY[user] = rec
    return int(rec["bytes_used"])


def set_bytes(user: str, value: int) -> None:
    payload = {"user": user, "bytes_used": max(0, int(value)), "updated_at": time.time()}
    if _backend() == "firestore":
        _coll().document(user).set(payload)
    else:
        _MEMORY[user] = payload


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
