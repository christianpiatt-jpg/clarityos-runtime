"""
el_ins/anomaly_store.py — Unit 80 / v72.

Per-operator anomaly store. Mirrors the ``el_ins_store`` shape:
in-memory backend (Firestore-eligible hook reserved), append-only,
newest-first.

Public surface
--------------
    store_anomalies(records: list[Anomaly]) -> None
    get_anomaly(operator_id, anomaly_id) -> Anomaly | None
    list_anomalies(operator_id, *, limit=100) -> list[Anomaly]
    list_anomalies_since(operator_id, since_ts) -> list[Anomaly]
    _reset_for_tests()
"""
from __future__ import annotations

import logging
from typing import Optional

from .anomaly import ANOMALY_TYPES, Anomaly

logger = logging.getLogger("clarityos.el_ins.anomaly_store")

# operator_id -> list[Anomaly] newest-first.
_MEM: dict[str, list[Anomaly]] = {}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _validate(a: dict) -> Anomaly:
    """Defensive normalisation. Raises ValueError on bad input."""
    if not isinstance(a, dict):
        raise ValueError("anomaly must be a dict")
    aid = a.get("id")
    if not isinstance(aid, str) or not aid:
        raise ValueError("anomaly id must be a non-empty string")
    operator_id = a.get("operator_id")
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("anomaly operator_id must be a non-empty string")
    anom_type = a.get("type")
    if anom_type not in ANOMALY_TYPES:
        raise ValueError(
            f"anomaly type must be one of {ANOMALY_TYPES}, got {anom_type!r}"
        )
    try:
        severity = int(a.get("severity") or 0)
    except (TypeError, ValueError) as e:
        raise ValueError(f"anomaly severity must be int, got {a.get('severity')!r}") from e
    if not (1 <= severity <= 5):
        raise ValueError(f"anomaly severity must be 1..5, got {severity}")
    try:
        ts = float(a.get("timestamp") or 0.0)
    except (TypeError, ValueError) as e:
        raise ValueError(f"anomaly timestamp must be numeric, got {a.get('timestamp')!r}") from e
    message = str(a.get("message") or "")
    record_id = str(a.get("record_id") or "")
    thread_id = a.get("thread_id")
    if thread_id is not None and (not isinstance(thread_id, str) or not thread_id):
        raise ValueError("anomaly thread_id must be None or non-empty string")
    coerced: Anomaly = {
        "id":          aid,
        "timestamp":   ts,
        "type":        anom_type,
        "severity":    severity,
        "message":     message,
        "record_id":   record_id,
        "operator_id": operator_id,
        "thread_id":   thread_id,
    }
    return coerced


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def store_anomalies(anomalies: list[dict]) -> None:
    """Append a list of validated anomalies to their owners' stacks.

    Newest-first insertion so reads stay O(N). Mixed-operator inputs
    are supported (the function dispatches per anomaly).
    """
    if not isinstance(anomalies, list):
        raise ValueError("anomalies must be a list")
    for a in anomalies:
        coerced = _validate(a)
        op = coerced["operator_id"]
        bucket = _MEM.setdefault(op, [])
        bucket.insert(0, coerced)


def list_anomalies(
    operator_id: str, *, limit: int = 100,
) -> list[Anomaly]:
    """Newest-first list for the operator. Limit clamped to ``[1, 1000]``."""
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 100
    n = max(1, min(1000, n))
    bucket = _MEM.get(operator_id) or []
    return list(bucket[:n])


def get_anomaly(
    operator_id: str, anomaly_id: str,
) -> Optional[Anomaly]:
    """Single-anomaly lookup scoped to the authed operator. Returns
    None when the id doesn't match a stored row (404 at the HTTP
    layer).
    """
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    if not isinstance(anomaly_id, str) or not anomaly_id:
        raise ValueError("anomaly_id must be a non-empty string")
    bucket = _MEM.get(operator_id) or []
    for a in bucket:
        if a.get("id") == anomaly_id:
            return a
    return None


def list_anomalies_since(
    operator_id: str, since_ts: float,
) -> list[Anomaly]:
    """Anomalies for ``operator_id`` newer than ``since_ts``
    (unix seconds). Used by the cockpit "new-anomaly red dot" badge.
    """
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    try:
        cutoff = float(since_ts)
    except (TypeError, ValueError) as e:
        raise ValueError(f"since_ts must be numeric, got {since_ts!r}") from e
    bucket = _MEM.get(operator_id) or []
    return [a for a in bucket if a["timestamp"] >= cutoff]


def _reset_for_tests() -> None:
    _MEM.clear()
