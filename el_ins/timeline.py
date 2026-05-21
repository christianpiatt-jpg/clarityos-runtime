"""
el_ins/timeline.py — Unit 82 / v73.

Per-operator chronological event log. Structured + queryable; this is
*not* a social feed. The store is write-only from system integration
points (kernel hook + rollup endpoints) — no client-side POST surface.

Event types
-----------
``record``    Emitted after each EL/INS analysis. Payload carries
              ``{el, ins, tsi, reasoning_mode}`` for the just-stored
              record. Lightweight — no raw text.

``anomaly``   Emitted once per detected anomaly. Payload carries
              ``{anomaly_id, type, severity, message}``.

``rollup``    Emitted when an operator hits a /el_ins/rollup/{window}
              endpoint. Payload carries ``{window, avg_el, avg_ins,
              avg_tsi}``. Side-effect on a GET endpoint, but matches
              the spec ("audit-trail of when operators reviewed").

``system``   Reserved for future use (e.g. config changes). Spec
              includes it as a type so the enum is locked from day 1.

Storage shape
-------------
``TimelineEvent`` is a TypedDict (deliberately not a frozen dataclass
— the existing el_ins stores already use TypedDicts for portability
and the surrounding code is built around dict-like access). Records
are stored newest-first per operator, same pattern as
``anomaly_store``.

Strict operator isolation
-------------------------
Every read enforces ``operator_id`` scoping; cross-operator lookups
return None / empty. The HTTP layer maps None to 404 on the
single-event endpoint to avoid leaking existence.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Literal, Optional, TypedDict

logger = logging.getLogger("clarityos.el_ins.timeline")

TimelineEventType = Literal[
    "record",
    "anomaly",
    "rollup",
    "system",
    # v78 — Regression-First protocol activity. Additive only.
    "regression_chain_started",
    "regression_chain_layer_updated",
    "regression_chain_closed",
    # v81 — visibility flag transition.
    "regression_chain_archived",
]

TIMELINE_EVENT_TYPES: tuple = (
    "record",
    "anomaly",
    "rollup",
    "system",
    # v78 — Regression-First protocol activity.
    "regression_chain_started",
    "regression_chain_layer_updated",
    "regression_chain_closed",
    # v81 — visibility flag transition.
    "regression_chain_archived",
)


class TimelineEvent(TypedDict, total=False):
    id:           str       # uuid4 hex
    timestamp_ms: int       # unix milliseconds — fine-grained for ordering
    event_type:   str       # one of TIMELINE_EVENT_TYPES
    payload:      dict      # strictly typed per event_type (see _validate_payload)
    operator_id:  str


# Default limits.
DEFAULT_TIMELINE_LIMIT: int = 200
MAX_TIMELINE_LIMIT: int = 1000


# In-memory storage. operator_id → list[TimelineEvent] newest-first.
_MEM: dict[str, list[TimelineEvent]] = {}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate(event: dict) -> TimelineEvent:
    """Defensive normalisation. Raises ValueError on bad input."""
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")
    operator_id = event.get("operator_id")
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("event operator_id must be a non-empty string")
    event_type = event.get("event_type")
    if event_type not in TIMELINE_EVENT_TYPES:
        raise ValueError(
            f"event_type must be one of {TIMELINE_EVENT_TYPES}, got {event_type!r}"
        )
    payload = event.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    # ts in milliseconds — coerce from seconds or accept ms directly.
    raw_ts = event.get("timestamp_ms")
    if raw_ts is None:
        ts_ms = int(time.time() * 1000)
    else:
        try:
            ts_ms = int(raw_ts)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"timestamp_ms must be an int, got {raw_ts!r}",
            ) from e
    eid = event.get("id") or uuid.uuid4().hex
    if not isinstance(eid, str) or not eid:
        raise ValueError("event id must be a non-empty string")
    return {
        "id":           eid,
        "timestamp_ms": ts_ms,
        "event_type":   event_type,
        "payload":      dict(payload),
        "operator_id":  operator_id,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def store_event(event: dict) -> TimelineEvent:
    """Append a validated event to the operator's stack. Returns the
    coerced event so callers can read back the stamped ``id`` and
    ``timestamp_ms``."""
    coerced = _validate(event)
    op = coerced["operator_id"]
    bucket = _MEM.setdefault(op, [])
    bucket.insert(0, coerced)
    return coerced


def list_events(
    operator_id: str, *, limit: int = DEFAULT_TIMELINE_LIMIT,
) -> list[TimelineEvent]:
    """Newest-first events for the operator. ``limit`` clamps to
    ``[1, MAX_TIMELINE_LIMIT]``."""
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = DEFAULT_TIMELINE_LIMIT
    n = max(1, min(MAX_TIMELINE_LIMIT, n))
    return list((_MEM.get(operator_id) or [])[:n])


def list_events_since(
    operator_id: str, timestamp_ms: int,
) -> list[TimelineEvent]:
    """Events newer than ``timestamp_ms`` (inclusive). Newest-first.

    Used by clients polling for "new since last seen" without server-
    side seen-state.
    """
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    try:
        cutoff = int(timestamp_ms)
    except (TypeError, ValueError) as e:
        raise ValueError(
            f"timestamp_ms must be an int, got {timestamp_ms!r}",
        ) from e
    return [
        e for e in (_MEM.get(operator_id) or [])
        if e["timestamp_ms"] >= cutoff
    ]


def get_event(operator_id: str, event_id: str) -> Optional[TimelineEvent]:
    """Single-event lookup scoped to the authed operator. Returns None
    on cross-operator (caller maps to 404 — no existence leak)."""
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    if not isinstance(event_id, str) or not event_id:
        raise ValueError("event_id must be a non-empty string")
    for e in _MEM.get(operator_id) or []:
        if e.get("id") == event_id:
            return e
    return None


# ---------------------------------------------------------------------------
# Event builders — used by the kernel + rollup endpoints
#
# Centralised here so payload shapes stay consistent across producers
# and the spec audit-checks against one place.
# ---------------------------------------------------------------------------
def build_record_event(
    operator_id: str,
    *,
    el: float,
    ins: float,
    tsi: Optional[int],
    reasoning_mode: Optional[str],
    thread_id: Optional[str] = None,
    timestamp_ms: Optional[int] = None,
) -> dict:
    """Build (but do not store) a ``record`` event. Caller stores via
    :func:`store_event` so failures can be swallowed defensively in
    the kernel hook."""
    return {
        "event_type":   "record",
        "operator_id":  operator_id,
        "timestamp_ms": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
        "payload": {
            "el":             float(el),
            "ins":            float(ins),
            "tsi":            int(tsi) if isinstance(tsi, int) else None,
            "reasoning_mode": reasoning_mode,
            "thread_id":      thread_id,
        },
    }


def build_anomaly_event(
    operator_id: str,
    *,
    anomaly_id: str,
    anomaly_type: str,
    severity: int,
    message: str,
    timestamp_ms: Optional[int] = None,
) -> dict:
    return {
        "event_type":   "anomaly",
        "operator_id":  operator_id,
        "timestamp_ms": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
        "payload": {
            "anomaly_id": anomaly_id,
            "type":       anomaly_type,
            "severity":   int(severity),
            "message":    message,
        },
    }


def build_rollup_event(
    operator_id: str,
    *,
    window: str,
    avg_el: float,
    avg_ins: float,
    avg_tsi: int,
    record_count: int,
    timestamp_ms: Optional[int] = None,
) -> dict:
    return {
        "event_type":   "rollup",
        "operator_id":  operator_id,
        "timestamp_ms": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
        "payload": {
            "window":       window,
            "avg_el":       float(avg_el),
            "avg_ins":      float(avg_ins),
            "avg_tsi":      int(avg_tsi),
            "record_count": int(record_count),
        },
    }


# ---------------------------------------------------------------------------
# v78 — Regression-First builders
#
# Emitted by ``app.py`` v76 endpoints after a successful kernel call.
# Payloads stay minimal — they index back into the chain via
# ``chain_id`` rather than duplicating the chain state, so timeline
# entries don't drift from the vault-stored chain.
# ---------------------------------------------------------------------------
def build_regression_chain_started_event(
    operator_id: str,
    *,
    chain_id: str,
    title: str,
    created_at_ms: int,
    timestamp_ms: Optional[int] = None,
) -> dict:
    return {
        "event_type":   "regression_chain_started",
        "operator_id":  operator_id,
        "timestamp_ms": (
            timestamp_ms if timestamp_ms is not None
            else int(time.time() * 1000)
        ),
        "payload": {
            "chain_id":      str(chain_id),
            "title":         str(title),
            "created_at_ms": int(created_at_ms),
        },
    }


def build_regression_chain_layer_updated_event(
    operator_id: str,
    *,
    chain_id: str,
    layer_index: int,
    status: str,
    updated_at_ms: int,
    timestamp_ms: Optional[int] = None,
) -> dict:
    return {
        "event_type":   "regression_chain_layer_updated",
        "operator_id":  operator_id,
        "timestamp_ms": (
            timestamp_ms if timestamp_ms is not None
            else int(time.time() * 1000)
        ),
        "payload": {
            "chain_id":      str(chain_id),
            "layer_index":   int(layer_index),
            "status":        str(status),
            "updated_at_ms": int(updated_at_ms),
        },
    }


def build_regression_chain_closed_event(
    operator_id: str,
    *,
    chain_id: str,
    closed_at_ms: int,
    timestamp_ms: Optional[int] = None,
) -> dict:
    return {
        "event_type":   "regression_chain_closed",
        "operator_id":  operator_id,
        "timestamp_ms": (
            timestamp_ms if timestamp_ms is not None
            else int(time.time() * 1000)
        ),
        "payload": {
            "chain_id":     str(chain_id),
            "closed_at_ms": int(closed_at_ms),
        },
    }


def build_regression_chain_archived_event(
    operator_id: str,
    *,
    chain_id: str,
    archived_at_ms: int,
    timestamp_ms: Optional[int] = None,
) -> dict:
    """v81 — visibility flag transition. Archived chains stay
    mutable; this event marks the operator's intent to hide the
    chain from default list views, not a lifecycle change.
    """
    return {
        "event_type":   "regression_chain_archived",
        "operator_id":  operator_id,
        "timestamp_ms": (
            timestamp_ms if timestamp_ms is not None
            else int(time.time() * 1000)
        ),
        "payload": {
            "chain_id":       str(chain_id),
            "archived_at_ms": int(archived_at_ms),
        },
    }


# ---------------------------------------------------------------------------
# Test hook
# ---------------------------------------------------------------------------
def _reset_for_tests() -> None:
    _MEM.clear()
