"""
v33 — Manual DM (direct-message) tracker.

Stores founder-curated notes about conversations had outside the app —
inbound DMs from LinkedIn / Facebook / email, manual outreach, etc. The
store is metadata-only; conversation transcripts go through the existing
vault, not here.

Schema:
    dm/
      {dm_id}: {
        "id":          str   ("dm_<token>"),
        "user":        str | None,    # ClarityOS username if known
        "external_id": str | None,    # e.g. "linkedin:foobar"
        "channel":     "linkedin" | "facebook" | "email" | "manual",
        "subject":     str | None,
        "snippet":     str | None,    # short summary, ≤ 500 chars
        "ts":          float,
        "founder":     str,           # whichever founder logged it
      }

    dm_notes/
      {note_id}: {
        "id":          str   ("dmn_<token>"),
        "dm_id":       str,
        "founder":     str,
        "body":        str,           # ≤ 4000 chars
        "ts":          float,
      }

Public API:

    add_dm(*, user=None, external_id=None, channel="manual", subject=None,
            snippet=None, founder) -> dict
    list_dms(*, channel=None, limit=200) -> list[dict]
    list_dms_for_user(user, *, limit=200) -> list[dict]
    get_dm(dm_id) -> dict | None
    add_dm_note(dm_id, body, *, founder) -> dict | None
    get_dm_notes(dm_id) -> list[dict]

NEVER stores raw external transcripts beyond the bounded ``snippet``
+ ``body`` fields.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Optional

logger = logging.getLogger("clarityos.dm_store")

_DM_COLL = "founder_dms"
_NOTE_COLL = "founder_dm_notes"

VALID_CHANNELS = ("linkedin", "facebook", "email", "manual")

MAX_SUBJECT_LEN = 200
MAX_SNIPPET_LEN = 500
MAX_BODY_LEN = 4000


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


_MEM_DMS: dict[str, dict] = {}
_MEM_NOTES: dict[str, dict] = {}
_firestore_client = None
# Monotonic per-process counter — used to tie-break sort ordering when
# two notes land in the same clock tick (Windows ~15ms resolution).
_SEQ_COUNTER: int = 0


def _next_seq() -> int:
    global _SEQ_COUNTER
    _SEQ_COUNTER += 1
    return _SEQ_COUNTER


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
    _firestore_client = firestore.Client()
    logger.info("dm_store firestore client initialised")
    return _firestore_client


def _new_dm_id() -> str:
    return "dm_" + secrets.token_urlsafe(10)


def _new_note_id() -> str:
    return "dmn_" + secrets.token_urlsafe(10)


def _truncate(text: Optional[str], cap: int) -> Optional[str]:
    if text is None:
        return None
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    s = text.strip()
    if not s:
        return None
    return s[:cap]


# ---------------------------------------------------------------------------
# DMs
# ---------------------------------------------------------------------------
def add_dm(
    *,
    founder: str,
    user: Optional[str] = None,
    external_id: Optional[str] = None,
    channel: str = "manual",
    subject: Optional[str] = None,
    snippet: Optional[str] = None,
) -> dict:
    if not isinstance(founder, str) or not founder.strip():
        raise ValueError("founder is required")
    if channel not in VALID_CHANNELS:
        raise ValueError(f"channel must be one of {VALID_CHANNELS!r}")
    record = {
        "id": _new_dm_id(),
        "user": user.strip() if isinstance(user, str) and user.strip() else None,
        "external_id": external_id.strip() if isinstance(external_id, str) and external_id.strip() else None,
        "channel": channel,
        "subject": _truncate(subject, MAX_SUBJECT_LEN),
        "snippet": _truncate(snippet, MAX_SNIPPET_LEN),
        "ts": time.time(),
        "founder": founder.strip(),
    }
    if _backend() == "firestore":
        _get_firestore().collection(_DM_COLL).document(record["id"]).set(record)
    else:
        _MEM_DMS[record["id"]] = dict(record)
    return record


def get_dm(dm_id: str) -> Optional[dict]:
    if not dm_id:
        return None
    if _backend() == "firestore":
        doc = _get_firestore().collection(_DM_COLL).document(dm_id).get()
        return doc.to_dict() if doc.exists else None
    rec = _MEM_DMS.get(dm_id)
    return dict(rec) if rec is not None else None


def list_dms(*, channel: Optional[str] = None, limit: int = 200) -> list[dict]:
    if channel is not None and channel not in VALID_CHANNELS:
        raise ValueError(f"channel must be one of {VALID_CHANNELS!r}")
    if _backend() == "firestore":
        coll = _get_firestore().collection(_DM_COLL)
        if channel:
            from google.cloud.firestore_v1 import FieldFilter  # type: ignore
            q = coll.where(filter=FieldFilter("channel", "==", channel))
        else:
            q = coll
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = list(_MEM_DMS.values())
        if channel:
            rows = [r for r in rows if r.get("channel") == channel]
        rows = [dict(r) for r in rows]
    rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    return rows[: max(1, int(limit))]


def list_dms_for_user(user: str, *, limit: int = 200) -> list[dict]:
    if not user:
        return []
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = _get_firestore().collection(_DM_COLL).where(
            filter=FieldFilter("user", "==", user),
        )
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = [dict(r) for r in _MEM_DMS.values() if r.get("user") == user]
    rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    return rows[: max(1, int(limit))]


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------
def add_dm_note(dm_id: str, body: str, *, founder: str) -> Optional[dict]:
    if not isinstance(founder, str) or not founder.strip():
        raise ValueError("founder is required")
    if not isinstance(body, str) or not body.strip():
        raise ValueError("body must be a non-empty string")
    # Verify the DM exists.
    if get_dm(dm_id) is None:
        return None
    record = {
        "id": _new_note_id(),
        "dm_id": dm_id,
        "founder": founder.strip(),
        "body": body.strip()[:MAX_BODY_LEN],
        "ts": time.time(),
        "seq": _next_seq(),
    }
    if _backend() == "firestore":
        _get_firestore().collection(_NOTE_COLL).document(record["id"]).set(record)
    else:
        _MEM_NOTES[record["id"]] = dict(record)
    return record


def get_dm_notes(dm_id: str) -> list[dict]:
    if not dm_id:
        return []
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = _get_firestore().collection(_NOTE_COLL).where(
            filter=FieldFilter("dm_id", "==", dm_id),
        )
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = [dict(r) for r in _MEM_NOTES.values() if r.get("dm_id") == dm_id]
    # Sort by (ts DESC, seq DESC) so notes that land inside the same
    # clock tick still report newest-first by insertion order.
    rows.sort(
        key=lambda r: (float(r.get("ts") or 0.0), int(r.get("seq") or 0)),
        reverse=True,
    )
    return rows


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_memory_for_tests() -> None:
    global _SEQ_COUNTER
    _MEM_DMS.clear()
    _MEM_NOTES.clear()
    _SEQ_COUNTER = 0
