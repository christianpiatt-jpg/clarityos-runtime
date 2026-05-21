"""
elins_intelligence_cache.py — ELINS2 Unit 11.

SQLite-backed cache for ``intelligence_for_run_ids`` (Unit 9) payloads.
Same DB file as the runs table so the cache lives alongside the data it
describes; cache rows are independent though (no FK), so trimming or
wiping the cache is safe.

KEY
---
``run_set_hash`` = ``sha256(json.dumps(run_ids, sort_keys=False, ensure_ascii=False))``
hex digest. ORDER MATTERS — ``[a, b]`` and ``[b, a]`` hash differently
because sequence intelligence (Unit 8) reads order. Callers that want
order-insensitive caching must sort first.

TTL
---
``store_intelligence`` accepts ``ttl_seconds`` per-entry. On read,
``get_cached_intelligence`` computes ``age = now - created_at`` and
discards (deletes) the row if ``age > ttl_seconds``.

PUBLIC API
----------
    get_cached_intelligence(run_ids) -> dict | None
    store_intelligence(run_ids, payload, ttl_seconds) -> None
    invalidate_intelligence(run_ids) -> None

ALSO EXPOSED (for tests / Unit 9 integration)
    DEFAULT_TTL_SECONDS — int
    _run_set_hash(run_ids) -> str
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone

from elins_persistence_sqlite import _open, _validate_run_id


# Default TTL for fresh cache writes from Unit 9 — 5 minutes. Long
# enough to absorb dashboard refresh storms, short enough that operator
# actions (Unit 12) that mutate tags don't surface stale narratives.
DEFAULT_TTL_SECONDS: int = 300


def _validate_run_ids(run_ids) -> None:
    if not isinstance(run_ids, list):
        raise ValueError(
            f"cache expected a list, got {type(run_ids).__name__}"
        )
    for rid in run_ids:
        _validate_run_id(rid)


def _run_set_hash(run_ids: list) -> str:
    """Deterministic SHA-256 hex of the ordered run_ids list, encoded
    as compact JSON so equivalent lists always hash the same way."""
    body = json.dumps(run_ids, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str) -> datetime:
    """Robust ISO-8601 parse — accepts naive or aware, treats naive as
    UTC."""
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def get_cached_intelligence(run_ids) -> dict | None:
    """Return the cached intelligence payload for `run_ids`, or
    ``None`` if there's no entry or it's past TTL.

    Expired rows are deleted as a side effect so subsequent calls
    don't repeatedly re-check the same stale entry.

    Raises:
        ValueError on a malformed run_ids list.
    """
    _validate_run_ids(run_ids)
    h = _run_set_hash(run_ids)
    conn = _open()
    try:
        row = conn.execute(
            "SELECT payload, created_at, ttl_seconds "
            "FROM intelligence_cache WHERE run_set_hash = ?",
            (h,),
        ).fetchone()
        if row is None:
            return None
        payload_json, created_at, ttl_seconds = row
        try:
            created_dt = _parse_iso(created_at)
        except ValueError:
            # Corrupt timestamp → treat as expired.
            conn.execute(
                "DELETE FROM intelligence_cache WHERE run_set_hash = ?",
                (h,),
            )
            conn.commit()
            return None
        age = (datetime.now(timezone.utc) - created_dt).total_seconds()
        if age > float(ttl_seconds):
            conn.execute(
                "DELETE FROM intelligence_cache WHERE run_set_hash = ?",
                (h,),
            )
            conn.commit()
            return None
    finally:
        conn.close()
    try:
        return json.loads(payload_json)
    except json.JSONDecodeError:
        # Corrupt row → treat as miss; cache will be repopulated by
        # the caller's next compute.
        return None


def store_intelligence(run_ids, payload, ttl_seconds: int) -> None:
    """Upsert a cache row for `run_ids`.

    Args:
        run_ids: validated list of run_ids — order-sensitive.
        payload: any JSON-serialisable dict (typically the full Unit 9
            output).
        ttl_seconds: positive integer.

    Raises:
        ValueError on a malformed input.
    """
    _validate_run_ids(run_ids)
    if not isinstance(payload, dict):
        raise ValueError(
            f"payload must be a dict, got {type(payload).__name__}"
        )
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int):
        raise ValueError(
            f"ttl_seconds must be a positive int, "
            f"got {type(ttl_seconds).__name__}"
        )
    if ttl_seconds < 1:
        raise ValueError(
            f"ttl_seconds must be >= 1, got {ttl_seconds}"
        )

    h = _run_set_hash(run_ids)
    run_ids_json = json.dumps(
        run_ids, ensure_ascii=False, separators=(",", ":"),
    )
    payload_json = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, default=list,
    )
    created_at = _now_iso()
    conn = _open()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO intelligence_cache "
            "(run_set_hash, run_ids, payload, created_at, ttl_seconds) "
            "VALUES (?, ?, ?, ?, ?)",
            (h, run_ids_json, payload_json, created_at, ttl_seconds),
        )
        conn.commit()
    finally:
        conn.close()


def invalidate_intelligence(run_ids) -> None:
    """Delete the cache row for `run_ids` if present. Idempotent — no
    error when the row doesn't exist.

    Raises:
        ValueError on a malformed run_ids list.
    """
    _validate_run_ids(run_ids)
    h = _run_set_hash(run_ids)
    conn = _open()
    try:
        conn.execute(
            "DELETE FROM intelligence_cache WHERE run_set_hash = ?",
            (h,),
        )
        conn.commit()
    finally:
        conn.close()
