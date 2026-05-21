"""
ClarityOS session storage layer.

Two backends, selected via the CLARITYOS_BACKEND environment variable:

    CLARITYOS_BACKEND=memory      (default) — in-process dict, wiped on restart
    CLARITYOS_BACKEND=firestore   — Google Cloud Firestore, persistent

Public API:

    create_session(session_id, username, expires_at) -> None
    get_session(session_id)                          -> dict | None
    delete_session(session_id)                       -> None

Document shape:

    {
        "user":       <str>,    # username this session belongs to
        "expires_at": <float>,  # POSIX seconds
    }

google-cloud-firestore is imported lazily so memory mode keeps working
without the package installed.

Note on cleanup: in-memory mode relies on require_session() in app.py
calling delete_session() when a session is found expired. Firestore mode
behaves the same way; for production you may also want to enable Firestore
TTL on the `sessions` collection's `expires_at` field to garbage-collect
abandoned sessions. That is deployment configuration, not code.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger("clarityos.sessions_store")

_SESSIONS_COLLECTION = "sessions"


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------
_MEMORY_SESSIONS: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Firestore backend (lazy-init)
# ---------------------------------------------------------------------------
_firestore_client = None  # type: ignore


def _get_firestore():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "CLARITYOS_BACKEND=firestore but google-cloud-firestore is not installed. "
            "Add `google-cloud-firestore` to requirements.txt or set CLARITYOS_BACKEND=memory."
        ) from e
    try:
        _firestore_client = firestore.Client()
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            f"Could not initialise Firestore client: {e}. "
            "On Cloud Run, attach a service account with roles/datastore.user. "
            "Locally, run `gcloud auth application-default login`."
        ) from e
    logger.info("sessions_store firestore client initialised")
    return _firestore_client


def _sessions_collection():
    return _get_firestore().collection(_SESSIONS_COLLECTION)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def create_session(session_id: str, username: str, expires_at: float) -> None:
    payload = {"user": username, "expires_at": expires_at}
    if _backend() == "firestore":
        _sessions_collection().document(session_id).set(payload)
    else:
        _MEMORY_SESSIONS[session_id] = payload


def get_session(session_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _sessions_collection().document(session_id).get()
        return doc.to_dict() if doc.exists else None
    return _MEMORY_SESSIONS.get(session_id)


def delete_session(session_id: str) -> None:
    if _backend() == "firestore":
        _sessions_collection().document(session_id).delete()
    else:
        _MEMORY_SESSIONS.pop(session_id, None)


# Test helper: clear in-memory state. Not used in production.
def _reset_memory_for_tests() -> None:
    _MEMORY_SESSIONS.clear()
