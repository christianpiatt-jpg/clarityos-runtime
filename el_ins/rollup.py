"""
el_ins/rollup.py — Unit 81 / v72.

Per-operator EL/INS roll-up over rolling time windows. Pure
deterministic aggregation of stored records — no LLM, no I/O beyond
calling the existing ``el_ins_store`` getters.

Three canonical windows (per spec): 24h / 7d / 30d. Endpoints expose
each window as its own URL; the helper accepts any ``timedelta``.

Reasoning-mode distribution
---------------------------
Records don't carry a ``reasoning_mode`` field (the v70 store
constraint kept it absent — TSI is the only derived value stored
per record). To compute the distribution at roll-up time we recompute
``select_reasoning_mode(el, ins, tsi)`` per record. This is pure +
deterministic and stays consistent with the cockpit indicator.

Public surface
--------------
    RollupResult                              (TypedDict)
    compute_rollup(operator_id, window) -> RollupResult
    ROLLUP_WINDOWS                            (24h / 7d / 30d in seconds)
"""
from __future__ import annotations

import time
from datetime import timedelta
from typing import TypedDict, Union

from .el_ins_store import get_macro_el_ins


# Locked canonical windows the HTTP endpoints expose. The helper
# accepts arbitrary ``timedelta`` / float-seconds; tests verify both
# named windows and ad-hoc windows.
ROLLUP_WINDOWS: dict[str, float] = {
    "24h": 60 * 60 * 24,
    "7d":  60 * 60 * 24 * 7,
    "30d": 60 * 60 * 24 * 30,
}


class RollupResult(TypedDict):
    avg_el:                       float
    avg_ins:                      float
    avg_tsi:                      int            # rounded
    reasoning_mode_distribution:  dict           # mode → count
    record_count:                 int
    window_start:                 float          # unix seconds
    window_end:                   float          # unix seconds


def _coerce_window_seconds(window: Union[float, int, timedelta, str]) -> float:
    """Accept the canonical window names (``"24h"`` / ``"7d"`` / ``"30d"``),
    a ``timedelta``, or a raw number of seconds. Returns a positive
    float-seconds value; raises ``ValueError`` for non-positive or
    unknown inputs.
    """
    if isinstance(window, str):
        if window not in ROLLUP_WINDOWS:
            raise ValueError(
                f"window must be one of {sorted(ROLLUP_WINDOWS)} or a "
                f"timedelta / numeric seconds, got {window!r}"
            )
        return ROLLUP_WINDOWS[window]
    if isinstance(window, timedelta):
        secs = window.total_seconds()
    else:
        try:
            secs = float(window)
        except (TypeError, ValueError) as e:
            raise ValueError(
                f"window must be a string / timedelta / number, got {window!r}"
            ) from e
    if secs <= 0:
        raise ValueError("window must be positive")
    return secs


def compute_rollup(
    operator_id: str,
    window: Union[float, int, timedelta, str],
    *,
    now: Union[float, None] = None,
) -> RollupResult:
    """Aggregate the authed operator's EL/INS records over the most
    recent ``window``.

    ``window`` may be:
        * ``"24h"`` / ``"7d"`` / ``"30d"``     — canonical names
        * ``timedelta``                        — caller-defined
        * raw float seconds                    — caller-defined

    ``now`` defaults to ``time.time()`` — tests inject a fixed value
    so window math is reproducible.

    When the operator has no records in the window, returns a fully
    shaped result with zeroed averages, empty distribution dict, and
    ``record_count = 0``.
    """
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")

    secs = _coerce_window_seconds(window)
    now_ts = float(now) if now is not None else time.time()
    window_start = now_ts - secs
    window_end = now_ts

    # Lazy import to avoid a circular dep — intelligence_kernel imports
    # el_ins, and this module shouldn't pull it eagerly at module-load.
    import intelligence_kernel as _ik

    rows = get_macro_el_ins(operator_id, since=window_start)
    # Trim records past `window_end` defensively (in case a clock skew
    # let a future-stamped record through).
    rows = [r for r in rows if r.get("timestamp") and r["timestamp"] <= window_end]

    if not rows:
        return {
            "avg_el":                      0.0,
            "avg_ins":                     0.0,
            "avg_tsi":                     0,
            "reasoning_mode_distribution": {},
            "record_count":                0,
            "window_start":                window_start,
            "window_end":                  window_end,
        }

    el_sum = 0.0
    ins_sum = 0.0
    tsi_sum = 0
    tsi_count = 0
    mode_counts: dict[str, int] = {}
    for r in rows:
        analysis = (r.get("result") or {}).get("analysis", {})
        el = float(analysis.get("el_score") or 0.0)
        ins = float(analysis.get("ins_score") or 0.0)
        el_sum += el
        ins_sum += ins
        t = r.get("tsi")
        if isinstance(t, int):
            tsi_sum += t
            tsi_count += 1
        mode = _ik.select_reasoning_mode(
            el, ins, t if isinstance(t, int) else None,
        )
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

    n = len(rows)
    return {
        "avg_el":                      round(el_sum / n, 2),
        "avg_ins":                     round(ins_sum / n, 2),
        "avg_tsi":                     int(round(tsi_sum / tsi_count)) if tsi_count else 0,
        "reasoning_mode_distribution": mode_counts,
        "record_count":                n,
        "window_start":                window_start,
        "window_end":                  window_end,
    }
