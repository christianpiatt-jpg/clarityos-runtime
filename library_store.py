"""
ClarityOS library storage. Per-user authored entries (titled, taggable,
updatable). Distinct from the engine-owned GCS-backed /library route which
reads a global content bucket — that one is unchanged.

Document shape (collection: `library_user`, keyed by library_id):
    {
        "id":         <str>,
        "user":       <str>,
        "title":      <str>,
        "content":    <str>,
        "tags":       [<str>],
        "metadata":   <dict>,
        "size_bytes": <int>,
        "created_at": <float>,
        "updated_at": <float>,
    }

Backend selection follows the house pattern (CLARITYOS_BACKEND).
The collection is named `library_user` to avoid colliding with any future
top-level `library` collection that mirrors the GCS bucket index.
"""
from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Optional

logger = logging.getLogger("clarityos.library_store")

_COLL = "library_user"


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
    logger.info("library_store firestore client initialised")
    return _firestore_client


def _coll():
    return _get_firestore().collection(_COLL)


# ---------- Public API ------------------------------------------------------
def new_id() -> str:
    return "l_" + secrets.token_urlsafe(16)


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


def update(item_id: str, payload: dict) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).set(payload)
    else:
        _MEMORY[item_id] = dict(payload)


def delete(item_id: str) -> None:
    if _backend() == "firestore":
        _coll().document(item_id).delete()
    else:
        _MEMORY.pop(item_id, None)


def list_for_user(user: str, limit: int = 100) -> list[dict]:
    """Return this user's library entries, newest first. Firestore mode
    requires a composite index on (user ASC, created_at DESC)."""
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


# ---------- #138 -- provenance: the basis column on the engine's own ledger --
# Five fields at the TOP LEVEL of ``metadata``, on every library write, all
# nullable. The server stamps ``created_ts`` (always; a client value is
# overwritten) and ``origin_route`` (the write site's own word). A client may
# name only the two origins a server cannot know -- "personal" (the Personal
# composer, with the relationship's thread id) and "thread_footer" (an ELINS
# tab footer, with its thread id) -- and may supply the three ids. Any other
# client word for origin_route is refused (ValueError; the routes answer 400):
# a paste must not be able to claim it was a feed or a brief. Existing items
# carry none of the five and are not backfilled; the reader renders "—".
ORIGIN_ROUTES: tuple = (
    "library_write", "ingest_manual", "feed", "elins_brief", "personal", "thread_footer",
)
CLIENT_ORIGIN_ROUTES: tuple = ("personal", "thread_footer")
PROVENANCE_FIELDS: tuple = (
    "created_ts", "origin_route", "origin_thread_id", "origin_turn_id", "run_id",
)
ABSENT: str = "—"          # #110 -- a null renders a dash, never "", never "unknown"
_ID_MAX: int = 200


def _opt_id(v) -> Optional[str]:
    """A client id, stripped and capped; blank or non-string is an ABSENCE."""
    if not isinstance(v, str):
        return None
    s = v.strip()
    return s[:_ID_MAX] if s else None


def check_origin_claim(route: str, claimed) -> str:
    """The ONE rule for a client's origin_route claim, callable before any
    work is spent: returns the word that will be stamped, or raises
    ValueError with a fixed message that never echoes the claim. A
    non-string claim is refused, not coerced (a bare ``5`` or ``["feed"]``
    is not an absence). Absent or blank -> the route's own word; the
    route's own word -> itself; one of CLIENT_ORIGIN_ROUTES -> honoured;
    anything else -> refused."""
    if route not in ORIGIN_ROUTES:
        raise ValueError(f"route must be one of {ORIGIN_ROUTES}")
    if claimed is not None and not isinstance(claimed, str):
        raise ValueError("origin_route must be a string")
    word = _opt_id(claimed)
    if word is None or word == route:
        return route
    if word in CLIENT_ORIGIN_ROUTES:
        return word
    raise ValueError(
        "origin_route is stamped by the server on this route; a client may name only "
        + " | ".join(CLIENT_ORIGIN_ROUTES)
    )


def stamp_provenance(
    metadata: Optional[dict],
    route: str,
    *,
    origin_route: Optional[str] = None,
    origin_thread_id: Optional[str] = None,
    origin_turn_id: Optional[str] = None,
    run_id: Optional[str] = None,
) -> dict:
    """Return a copy of ``metadata`` with the five fields stamped.

    ``route`` is the write site's own word (one of ORIGIN_ROUTES). A client's
    claim arrives either as the ``origin_route`` kwarg or inside
    ``metadata["origin_route"]``; absent or equal to the route, the route's
    word stands; one of CLIENT_ORIGIN_ROUTES is honoured; anything else
    raises ValueError (the message never echoes the client's string).
    ``created_ts`` is the server's clock, always -- a client value is
    overwritten. The three ids: the kwargs win, else the metadata's own,
    each stripped, capped, blank -> None.
    """
    md = dict(metadata or {})
    word = check_origin_claim(
        route, origin_route if origin_route is not None else md.get("origin_route"),
    )
    md["created_ts"] = time.time()
    md["origin_route"] = word
    md["origin_thread_id"] = _opt_id(
        origin_thread_id if origin_thread_id is not None else md.get("origin_thread_id"))
    md["origin_turn_id"] = _opt_id(
        origin_turn_id if origin_turn_id is not None else md.get("origin_turn_id"))
    md["run_id"] = _opt_id(run_id if run_id is not None else md.get("run_id"))
    return md


def carry_provenance(existing: Optional[dict], incoming: Optional[dict]) -> dict:
    """For an UPDATE that replaces ``metadata``: the server's two fields
    (created_ts, origin_route) are carried from the existing item and can
    neither be overridden nor planted (an item that predates #138 stays
    without them -- no backfill); the three ids are the incoming values when
    the incoming dict names them, else the existing ones."""
    old = dict(existing or {})
    new = dict(incoming or {})
    for k in ("created_ts", "origin_route"):
        if k in old:
            new[k] = old[k]
        else:
            new.pop(k, None)
    for k in ("origin_thread_id", "origin_turn_id", "run_id"):
        if k in new:
            new[k] = _opt_id(new[k])
        elif k in old:
            new[k] = old[k]
    return new


def provenance_view(item: Optional[dict]) -> dict:
    """The reader's render of the five fields: a null, blank or missing
    field is ABSENT ("—"), never "" and never "unknown" (#110). The raw
    ``metadata`` keeps its nulls -- this is the render, not the substrate."""
    md = (item or {}).get("metadata") or {}
    out: dict = {}
    for k in PROVENANCE_FIELDS:
        v = md.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            out[k] = ABSENT
        else:
            out[k] = v
    return out


def _reset_memory_for_tests() -> None:
    _MEMORY.clear()
