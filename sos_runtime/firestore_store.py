"""
Firestore client wrapper for SOS Runtime.

Backends:
    ``firestore`` — real ``google-cloud-firestore`` client. Used in
                    production (Cloud Run with ADC / service account).
    ``memory``    — in-process dict-backed stub. Used in tests, local
                    dev without GCP credentials, and any path where
                    Firestore isn't reachable.

Backend selection:
    1. ``SOS_FIRESTORE_BACKEND`` env var (``firestore`` | ``memory``)
       if set.
    2. ``memory`` when ``SOS_BACKEND=memory`` (test convention).
    3. ``firestore`` otherwise.

Collections (per spec § 2):
    sessions/{session_id}  — user_id, created_at, updated_at, metadata
    events/{auto_id}       — session_id, user_id, type, payload,
                              model_response?, created_at
    states/{user_id}       — current_state, last_transition,
                              continuity, updated_at

All timestamps stored as int ms epoch (matches the rest of the
ClarityOS surfaces — vault, threads, projects all use int ms).
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from threading import RLock
from typing import Any, Optional

logger = logging.getLogger("sos_runtime.firestore_store")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
COLLECTION_SESSIONS = "sessions"
COLLECTION_EVENTS   = "events"
COLLECTION_STATES   = "states"

VALID_EVENT_TYPES: tuple = ("engage", "elins", "continuity", "state")


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------
def _backend_name() -> str:
    explicit = (os.environ.get("SOS_FIRESTORE_BACKEND") or "").strip().lower()
    if explicit in ("firestore", "memory"):
        return explicit
    if (os.environ.get("SOS_BACKEND") or "").lower() == "memory":
        return "memory"
    return "firestore"


def _now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------------------------------------------------------
# In-memory backend
# ---------------------------------------------------------------------------
class _MemoryBackend:
    """Process-local dict-backed Firestore stand-in. Same surface as
    the real client wrapper below."""

    __slots__ = ("_lock", "_sessions", "_events", "_states")

    def __init__(self) -> None:
        self._lock = RLock()
        self._sessions: dict[str, dict] = {}
        self._events: list[dict] = []
        self._states: dict[str, dict] = {}

    # ----- sessions -----
    def upsert_session(
        self, session_id: str, user_id: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        with self._lock:
            now = _now_ms()
            existing = self._sessions.get(session_id)
            if existing is None:
                doc = {
                    "id":         session_id,
                    "user_id":    user_id,
                    "created_at": now,
                    "updated_at": now,
                    "metadata":   dict(metadata or {}),
                }
                self._sessions[session_id] = doc
                return doc
            existing["updated_at"] = now
            if metadata:
                merged = {**existing.get("metadata", {}), **metadata}
                existing["metadata"] = merged
            return existing

    def get_session(self, session_id: str) -> Optional[dict]:
        with self._lock:
            doc = self._sessions.get(session_id)
            return dict(doc) if doc is not None else None

    # ----- events -----
    def append_event(
        self,
        *,
        session_id: str, user_id: str, type: str,
        payload: dict, model_response: Optional[dict] = None,
    ) -> dict:
        if type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"event type must be one of {VALID_EVENT_TYPES}, got {type!r}"
            )
        with self._lock:
            doc = {
                "id":             uuid.uuid4().hex,
                "session_id":     session_id,
                "user_id":        user_id,
                "type":           type,
                "payload":        dict(payload),
                "model_response": dict(model_response) if model_response else None,
                "created_at":     _now_ms(),
            }
            self._events.append(doc)
            return doc

    def list_events_for_session(
        self, session_id: str, *, limit: int = 100,
    ) -> list[dict]:
        with self._lock:
            matched = [e for e in self._events if e["session_id"] == session_id]
            matched.sort(key=lambda e: e["created_at"], reverse=True)
            return [dict(e) for e in matched[:limit]]

    def list_events_for_user(
        self, user_id: str, *, limit: int = 100,
    ) -> list[dict]:
        with self._lock:
            matched = [e for e in self._events if e["user_id"] == user_id]
            matched.sort(key=lambda e: e["created_at"], reverse=True)
            return [dict(e) for e in matched[:limit]]

    # ----- states -----
    def get_state(self, user_id: str) -> Optional[dict]:
        with self._lock:
            doc = self._states.get(user_id)
            return dict(doc) if doc is not None else None

    def set_state(
        self, user_id: str, *,
        current_state: Any = None,
        continuity: Optional[dict] = None,
        transition: bool = True,
    ) -> dict:
        with self._lock:
            now = _now_ms()
            existing = self._states.get(user_id) or {
                "id":              user_id,
                "current_state":   None,
                "last_transition": None,
                "continuity":      {},
                "updated_at":      now,
            }
            if current_state is not None:
                existing["current_state"] = current_state
                if transition:
                    existing["last_transition"] = now
            if continuity is not None:
                merged = {**existing.get("continuity", {}), **continuity}
                existing["continuity"] = merged
            existing["updated_at"] = now
            self._states[user_id] = existing
            return dict(existing)

    # ----- test hook -----
    def reset_for_tests(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._events.clear()
            self._states.clear()


# ---------------------------------------------------------------------------
# Firestore-backed implementation
# ---------------------------------------------------------------------------
class _FirestoreBackend:
    """Real Firestore client wrapper. Lazy-imports
    ``google-cloud-firestore`` so the package stays usable when the
    SDK isn't installed (tests + dev paths use ``_MemoryBackend``)."""

    def __init__(self) -> None:
        try:
            from google.cloud import firestore   # type: ignore
        except ImportError as e:  # pragma: no cover (env without SDK)
            raise RuntimeError(
                "google-cloud-firestore not installed; set "
                "SOS_FIRESTORE_BACKEND=memory for local/test use."
            ) from e
        self._client = firestore.Client()
        self._firestore = firestore

    def upsert_session(
        self, session_id: str, user_id: str,
        metadata: Optional[dict] = None,
    ) -> dict:                                  # pragma: no cover (live GCP)
        ref = self._client.collection(COLLECTION_SESSIONS).document(session_id)
        snap = ref.get()
        now = _now_ms()
        if not snap.exists:
            doc = {
                "id":         session_id,
                "user_id":    user_id,
                "created_at": now,
                "updated_at": now,
                "metadata":   dict(metadata or {}),
            }
            ref.set(doc)
            return doc
        update: dict = {"updated_at": now}
        if metadata:
            merged = {**(snap.get("metadata") or {}), **metadata}
            update["metadata"] = merged
        ref.update(update)
        out = snap.to_dict() or {}
        out.update(update)
        out["id"] = session_id
        return out

    def get_session(self, session_id: str) -> Optional[dict]:  # pragma: no cover
        ref = self._client.collection(COLLECTION_SESSIONS).document(session_id)
        snap = ref.get()
        if not snap.exists:
            return None
        d = snap.to_dict() or {}
        d["id"] = session_id
        return d

    def append_event(
        self, *, session_id: str, user_id: str, type: str,
        payload: dict, model_response: Optional[dict] = None,
    ) -> dict:                                  # pragma: no cover (live GCP)
        if type not in VALID_EVENT_TYPES:
            raise ValueError(
                f"event type must be one of {VALID_EVENT_TYPES}, got {type!r}"
            )
        doc = {
            "session_id":     session_id,
            "user_id":        user_id,
            "type":           type,
            "payload":        dict(payload),
            "model_response": dict(model_response) if model_response else None,
            "created_at":     _now_ms(),
        }
        _, ref = self._client.collection(COLLECTION_EVENTS).add(doc)
        doc["id"] = ref.id
        return doc

    def list_events_for_session(
        self, session_id: str, *, limit: int = 100,
    ) -> list[dict]:                            # pragma: no cover (live GCP)
        q = (
            self._client.collection(COLLECTION_EVENTS)
            .where("session_id", "==", session_id)
            .order_by("created_at", direction=self._firestore.Query.DESCENDING)
            .limit(limit)
        )
        out: list[dict] = []
        for snap in q.stream():
            d = snap.to_dict() or {}
            d["id"] = snap.id
            out.append(d)
        return out

    def list_events_for_user(
        self, user_id: str, *, limit: int = 100,
    ) -> list[dict]:                            # pragma: no cover (live GCP)
        q = (
            self._client.collection(COLLECTION_EVENTS)
            .where("user_id", "==", user_id)
            .order_by("created_at", direction=self._firestore.Query.DESCENDING)
            .limit(limit)
        )
        out: list[dict] = []
        for snap in q.stream():
            d = snap.to_dict() or {}
            d["id"] = snap.id
            out.append(d)
        return out

    def get_state(self, user_id: str) -> Optional[dict]:  # pragma: no cover
        ref = self._client.collection(COLLECTION_STATES).document(user_id)
        snap = ref.get()
        if not snap.exists:
            return None
        d = snap.to_dict() or {}
        d["id"] = user_id
        return d

    def set_state(
        self, user_id: str, *,
        current_state: Any = None,
        continuity: Optional[dict] = None,
        transition: bool = True,
    ) -> dict:                                  # pragma: no cover (live GCP)
        ref = self._client.collection(COLLECTION_STATES).document(user_id)
        snap = ref.get()
        now = _now_ms()
        if snap.exists:
            existing = snap.to_dict() or {}
        else:
            existing = {
                "id":              user_id,
                "current_state":   None,
                "last_transition": None,
                "continuity":      {},
                "updated_at":      now,
            }
        if current_state is not None:
            existing["current_state"] = current_state
            if transition:
                existing["last_transition"] = now
        if continuity is not None:
            merged = {**(existing.get("continuity") or {}), **continuity}
            existing["continuity"] = merged
        existing["updated_at"] = now
        existing["id"] = user_id
        ref.set(existing, merge=True)
        return existing

    def reset_for_tests(self) -> None:          # pragma: no cover
        # No-op for the real backend. Tests use memory.
        pass


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------
_BACKEND: Optional[Any] = None


def get_store() -> Any:
    """Return the singleton backend instance. Selection rules above."""
    global _BACKEND
    if _BACKEND is None:
        name = _backend_name()
        if name == "memory":
            _BACKEND = _MemoryBackend()
        else:
            _BACKEND = _FirestoreBackend()
    return _BACKEND


def reset_for_tests() -> None:
    """Drop the singleton + force re-selection on next ``get_store``.
    Used by the pytest fixture so the backend can flip between tests."""
    global _BACKEND
    if _BACKEND is not None and hasattr(_BACKEND, "reset_for_tests"):
        _BACKEND.reset_for_tests()
    _BACKEND = None
