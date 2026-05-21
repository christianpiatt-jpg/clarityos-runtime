"""
el_ins/org_timeline.py — Unit 83 / v73.

Org-level aggregated timeline. Read-only view that walks every
operator's per-operator timeline and emits a sanitised, summarised
list — same chronological ordering, but with strict isolation:

    * operator_id        → masked to the last 6 chars only
    * raw payload        → replaced by ``payload_summary``
    * thread_id          → never surfaced
    * cross-operator     → never leaked (the masking is one-way)

Three rolling windows: ``"24h"``, ``"7d"``, ``"30d"``.

Authz
-----
This module is purely a compute helper — it walks the in-memory
``_MEM`` map from ``timeline.py`` and emits a sanitised list. The
HTTP layer is where founder-cohort gating happens; this module
trusts the caller.

Summary contracts (locked)
--------------------------
``record``  → ``{"el": float, "ins": float, "tsi": int|None}``
``anomaly`` → ``{"severity": int, "rule": str}``      # "rule" = anomaly type
``rollup``  → ``{"window": str, "avg_el": float, "avg_ins": float}``
``system``  → ``{}`` (placeholder — no raw payload)
"""
from __future__ import annotations

import time
from datetime import timedelta
from typing import Any, Optional, TypedDict, Union

from . import timeline as _tl


ORG_TIMELINE_WINDOWS: dict[str, float] = {
    "24h": 60 * 60 * 24,
    "7d":  60 * 60 * 24 * 7,
    "30d": 60 * 60 * 24 * 30,
}

# Number of trailing characters to surface from an operator_id.
# Spec: "operator_id (masked: last 6 chars only)".
_OPERATOR_MASK_TAIL: int = 6


class OrgTimelineEntry(TypedDict):
    timestamp_ms:    int
    operator_id:     str       # masked to last 6 chars
    event_type:      str
    payload_summary: dict


def _coerce_window_seconds(window: Union[str, float, int, timedelta]) -> float:
    if isinstance(window, str):
        if window not in ORG_TIMELINE_WINDOWS:
            raise ValueError(
                f"window must be one of {sorted(ORG_TIMELINE_WINDOWS)} or a "
                f"timedelta / numeric seconds, got {window!r}",
            )
        return ORG_TIMELINE_WINDOWS[window]
    if isinstance(window, timedelta):
        secs = window.total_seconds()
    else:
        try:
            secs = float(window)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"window must be a string / timedelta / number, got {window!r}",
            ) from e
    if secs <= 0:
        raise ValueError("window must be positive")
    return secs


def _mask_operator(op: str) -> str:
    """Return the last ``_OPERATOR_MASK_TAIL`` chars of ``op``. Short
    ids return as-is — anything ≤ 6 chars wouldn't be masked anyway."""
    s = str(op or "")
    if len(s) <= _OPERATOR_MASK_TAIL:
        return s
    return s[-_OPERATOR_MASK_TAIL:]


def _summarise_payload(event_type: str, payload: dict) -> dict:
    """Strict per-event_type payload reduction. NO raw fields beyond
    the locked summary contract."""
    p = payload or {}
    if event_type == "record":
        return {
            "el":  float(p.get("el") or 0.0),
            "ins": float(p.get("ins") or 0.0),
            "tsi": int(p.get("tsi")) if isinstance(p.get("tsi"), int) else None,
        }
    if event_type == "anomaly":
        return {
            "severity": int(p.get("severity") or 0),
            "rule":     str(p.get("type") or ""),
        }
    if event_type == "rollup":
        return {
            "window":  str(p.get("window") or ""),
            "avg_el":  float(p.get("avg_el") or 0.0),
            "avg_ins": float(p.get("avg_ins") or 0.0),
        }
    # ``system`` and any unknown type → empty summary, never raw.
    return {}


def compute_org_timeline(
    window: Union[str, float, int, timedelta],
    *,
    now: Optional[float] = None,
) -> list[OrgTimelineEntry]:
    """Walk every operator's timeline and return newest-first sanitised
    entries falling inside the rolling window.

    ``now`` defaults to ``time.time()`` — tests inject a fixed value
    for reproducibility.

    Returns an empty list when no operator has any events in the
    window. Cross-operator leakage is structurally impossible: every
    entry carries a masked operator_id and a summarised payload.
    """
    secs = _coerce_window_seconds(window)
    now_ts = float(now) if now is not None else time.time()
    cutoff_ms = int((now_ts - secs) * 1000)
    end_ms = int(now_ts * 1000)

    out: list[OrgTimelineEntry] = []
    for op, bucket in (_tl._MEM or {}).items():
        for ev in bucket:
            ts = int(ev.get("timestamp_ms") or 0)
            if ts < cutoff_ms or ts > end_ms:
                continue
            out.append({
                "timestamp_ms":    ts,
                "operator_id":     _mask_operator(op),
                "event_type":      str(ev.get("event_type") or ""),
                "payload_summary": _summarise_payload(
                    str(ev.get("event_type") or ""),
                    ev.get("payload") or {},
                ),
            })
    out.sort(key=lambda e: e["timestamp_ms"], reverse=True)
    return out
