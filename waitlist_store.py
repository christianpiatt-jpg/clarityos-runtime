"""
v32 — Public waitlist store.

Tracks pre-signup interest captured from the public website (or imported
manually by a founder). Distinct from ``membership_store``'s in-cohort
waitlist (which only tracks AUTHENTICATED users who tried to activate
when the cap was full); this store is the upstream funnel — emails from
people who haven't signed up yet.

Schema:
    {
        "id":          str   ("wl_<token>"),
        "email":       str   (lowercased, validated)
        "name":        str | None,
        "source":      "website" | "linkedin" | "facebook" | "manual",
        "created_ts":  float,
        "updated_ts":  float | None,
        "status":      "waiting" | "contacted" | "converted" | "dropped",
        "note":        str | None,
        "user_id":     str | None,    # set when status = "converted"
        "contacted_ts": float | None,
        "converted_ts": float | None,
    }

Caps:
* MAX_NOTE_LEN = 1000          (longer notes truncated server-side at write)
* MAX_NAME_LEN = 200
* MAX_EMAIL_LEN = 320          (RFC 5321 max)

NEVER stores: free-form content beyond the fields above. The ``note``
field is for short founder annotations only and is sized accordingly.

In-memory + Firestore backends. Keyed globally by ``id``.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
import time
from typing import Optional

logger = logging.getLogger("clarityos.waitlist_store")

_COLL = "waitlist"

VALID_SOURCES = ("website", "linkedin", "facebook", "manual")
VALID_STATUSES = ("waiting", "contacted", "converted", "dropped")

MAX_NOTE_LEN = 1000
MAX_NAME_LEN = 200
MAX_EMAIL_LEN = 320

# RFC 5322 simplified — covers practical email shapes; intentionally permissive
# (we don't bounce real users on edge-case TLDs). Strict validation belongs
# to the email-sender layer downstream.
_EMAIL_RE = re.compile(r"^[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}$", re.IGNORECASE)


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
    _firestore_client = firestore.Client()
    logger.info("waitlist_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def normalize_email(email: str) -> str:
    """Lowercase + strip; raises ValueError on bad shape or length."""
    if not isinstance(email, str):
        raise ValueError("email must be a string")
    e = email.strip().lower()
    if not e:
        raise ValueError("email is required")
    if len(e) > MAX_EMAIL_LEN:
        raise ValueError(f"email exceeds {MAX_EMAIL_LEN}-character cap")
    if not _EMAIL_RE.match(e):
        raise ValueError("email format is invalid")
    return e


def _normalize_name(name: Optional[str]) -> Optional[str]:
    if name is None:
        return None
    if not isinstance(name, str):
        raise ValueError("name must be a string")
    n = name.strip()
    if not n:
        return None
    return n[:MAX_NAME_LEN]


def _normalize_source(source: Optional[str]) -> str:
    if source is None or source == "":
        return "website"
    if not isinstance(source, str):
        raise ValueError("source must be a string")
    s = source.strip().lower()
    if s not in VALID_SOURCES:
        raise ValueError(
            f"source must be one of {VALID_SOURCES!r}, got {s!r}"
        )
    return s


def _normalize_note(note: Optional[str]) -> Optional[str]:
    if note is None:
        return None
    if not isinstance(note, str):
        raise ValueError("note must be a string")
    n = note.strip()
    if not n:
        return None
    return n[:MAX_NOTE_LEN]


def new_waitlist_id() -> str:
    return "wl_" + secrets.token_urlsafe(12)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------
def _save(record: dict) -> dict:
    if _backend() == "firestore":
        _coll().document(record["id"]).set(record)
    else:
        _MEMORY[record["id"]] = dict(record)
    return record


def _load(record_id: str) -> Optional[dict]:
    if _backend() == "firestore":
        doc = _coll().document(record_id).get()
        return doc.to_dict() if doc.exists else None
    rec = _MEMORY.get(record_id)
    return dict(rec) if rec is not None else None


def get_waitlist_entry(record_id: str) -> Optional[dict]:
    """Read a single entry by id. Returns None if no such id."""
    if not record_id:
        return None
    return _load(record_id)


def find_by_email(email: str) -> Optional[dict]:
    """Look up an entry by normalized email. Returns the most recent
    matching record (or None)."""
    e = normalize_email(email)
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = _coll().where(filter=FieldFilter("email", "==", e)).limit(1)
        for doc in q.stream():
            return doc.to_dict()
        return None
    matches = [r for r in _MEMORY.values() if r.get("email") == e]
    if not matches:
        return None
    matches.sort(key=lambda r: float(r.get("created_ts") or 0.0), reverse=True)
    return dict(matches[0])


def list_waitlist(*, status: Optional[str] = None, limit: int = 500) -> list[dict]:
    """List all entries, newest first. Optionally filter by status."""
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES!r}")
    if _backend() == "firestore":
        coll = _coll()
        if status:
            from google.cloud.firestore_v1 import FieldFilter  # type: ignore
            q = coll.where(filter=FieldFilter("status", "==", status))
        else:
            q = coll
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = list(_MEMORY.values())
        if status:
            rows = [r for r in rows if r.get("status") == status]
        rows = [dict(r) for r in rows]
    rows.sort(key=lambda r: float(r.get("created_ts") or 0.0), reverse=True)
    return rows[: max(1, int(limit))]


def count_waitlist(*, status: Optional[str] = None) -> int:
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES!r}")
    if _backend() == "firestore":
        return len(list_waitlist(status=status, limit=10_000))
    if status:
        return sum(1 for r in _MEMORY.values() if r.get("status") == status)
    return len(_MEMORY)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------
def add_waitlist_entry(
    email: str,
    name: Optional[str] = None,
    source: Optional[str] = None,
    ts: Optional[float] = None,
    note: Optional[str] = None,
) -> dict:
    """Create a new waitlist entry. Idempotent on email — if an entry for
    the same email already exists with status != 'dropped', returns it
    untouched (so retries from the public form don't create duplicates).
    Returns the stored record."""
    e = normalize_email(email)
    n = _normalize_name(name)
    s = _normalize_source(source)
    note_clean = _normalize_note(note)
    now = float(ts if ts is not None else time.time())

    existing = find_by_email(e)
    if existing and existing.get("status") != "dropped":
        return existing

    record = {
        "id": new_waitlist_id(),
        "email": e,
        "name": n,
        "source": s,
        "created_ts": now,
        "updated_ts": None,
        "status": "waiting",
        "note": note_clean,
        "user_id": None,
        "contacted_ts": None,
        "converted_ts": None,
    }
    return _save(record)


def update_status(
    record_id: str,
    *,
    status: str,
    note: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[dict]:
    """Transition an existing entry to a new status. Returns the updated
    record, or None if no such id."""
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES!r}")
    rec = _load(record_id)
    if rec is None:
        return None
    rec["status"] = status
    rec["updated_ts"] = float(time.time())
    if note is not None:
        rec["note"] = _normalize_note(note)
    if status == "contacted":
        rec["contacted_ts"] = rec["updated_ts"]
    elif status == "converted":
        rec["converted_ts"] = rec["updated_ts"]
        # Require a non-empty user_id when transitioning to converted; the
        # store is the source of truth for this invariant so callers can't
        # silently drop the link to the user record.
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id is required when transitioning to converted")
        rec["user_id"] = user_id.strip()
    return _save(rec)


def mark_contacted(record_id: str, *, note: Optional[str] = None) -> Optional[dict]:
    return update_status(record_id, status="contacted", note=note)


def mark_converted(record_id: str, user_id: str, *, note: Optional[str] = None) -> Optional[dict]:
    return update_status(record_id, status="converted", user_id=user_id, note=note)


def mark_dropped(record_id: str, *, note: Optional[str] = None) -> Optional[dict]:
    return update_status(record_id, status="dropped", note=note)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
