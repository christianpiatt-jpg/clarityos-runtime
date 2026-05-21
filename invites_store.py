"""
Invite storage. Memory backend for local dev, Firestore for prod —
selected by CLARITYOS_BACKEND, same pattern as users_store / sessions_store.

Document shape:
    {
        "invite_id":        <str>,
        "cohort":           "founder_exception" | "terrace_1",
        "price":            <int>,        # 0 for founder_exception, 50 for terrace_1
        "billing_required": <bool>,
        "inviter":          <str>,        # username of admin who created it
        "status":           "unused" | "used",
        "created_at":       <float>,
        "expires_at":       <float>,
        "used_by":          <str|None>,
        "used_at":          <float|None>,
    }
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Optional

logger = logging.getLogger("clarityos.invites_store")

_COLL = "invites"


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
    logger.info("invites_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


# ---------- Public API ------------------------------------------------------
def new_invite_id() -> str:
    return secrets.token_urlsafe(16)


def create_invite(
    invite_id: str,
    cohort: str,
    price: int,
    billing_required: bool,
    inviter: str,
    expires_at: float,
) -> dict:
    payload = {
        "invite_id": invite_id,
        "cohort": cohort,
        "price": price,
        "billing_required": billing_required,
        "inviter": inviter,
        "status": "unused",
        "created_at": time.time(),
        "expires_at": expires_at,
        "used_by": None,
        "used_at": None,
    }
    if _backend() == "firestore":
        _coll().document(invite_id).set(payload)
    else:
        _MEMORY[invite_id] = payload
    return payload


def get_invite(invite_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _coll().document(invite_id).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY.get(invite_id)


def mark_used(invite_id: str, used_by: str) -> None:
    update = {
        "status": "used",
        "used_by": used_by,
        "used_at": time.time(),
    }
    if _backend() == "firestore":
        _coll().document(invite_id).set(update, merge=True)
    elif invite_id in _MEMORY:
        _MEMORY[invite_id].update(update)


def count_redeemed(cohort: str) -> int:
    """Number of invites in this cohort that have been redeemed (status='used')."""
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = (
            _coll()
            .where(filter=FieldFilter("cohort", "==", cohort))
            .where(filter=FieldFilter("status", "==", "used"))
        )
        return sum(1 for _ in q.stream())
    return sum(
        1
        for v in _MEMORY.values()
        if v.get("cohort") == cohort and v.get("status") == "used"
    )


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
