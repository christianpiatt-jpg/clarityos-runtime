"""
el_ins/el_ins_store.py — Unit 74 / v69, Unit 76 / v70.

Per-operator EL/INS analysis store. Mirrors the macro_scheduler_store
+ users_store pattern: ``memory`` backend with a Firestore-eligible
hook, ``_reset_for_tests`` exposed.

Records are append-only. Keys are (operator_id, thread_id, ts_ms) so
the same operator can have multiple threads each with their own
ordered history.

v70 / Unit 76 — Added Thread Stability Index (TSI) + drift
detection. Each record carries an optional ``tsi`` field stamped at
store time (snapshot of the thread's stability score including this
record). ``compute_thread_stability(operator_id, thread_id, window)``
computes the current stability classification + TSI for a thread.

v70 / Unit 77 — Added ``compute_operator_summary(operator_id,
sample_size)`` for the macro dashboard. Returns the recent
classification distribution, average TSI, and a deterministic
trend slope.

Public surface
--------------
    ElInsRecord                              (TypedDict, optional tsi)
    store_el_ins_record(record) -> None
    get_thread_el_ins(operator_id, thread_id) -> list[ElInsRecord]
    get_recent_el_ins(operator_id, limit=100) -> list[ElInsRecord]
    get_macro_el_ins(operator_id, since=None) -> list[ElInsRecord]
    compute_thread_stability(operator_id, thread_id, *, window=10) -> dict
    compute_operator_summary(operator_id, *, sample_size=20) -> dict
    _reset_for_tests()
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Literal, Optional, TypedDict

logger = logging.getLogger("clarityos.el_ins.store")

# In-memory state.
#   _MEM: dict[operator_id, list[ElInsRecord]]   — newest-first per key
#
# Records sorted newest-first so the common "recent" reads are O(N)
# linear without re-sorting.
_MEM: dict[str, list["ElInsRecord"]] = {}


class ElInsRecord(TypedDict, total=False):
    operator_id: str
    thread_id: Optional[str]
    timestamp: float            # unix seconds, float
    source: str                 # on_demand | per_turn | macro
    result: dict                # ElInsResult (kept as dict for store-portability)
    tsi: Optional[int]          # v70 / Unit 76 — Thread Stability Index 0..100, stamped at store time


VALID_SOURCES: tuple = ("on_demand", "per_turn", "macro")

# v70 / Unit 76 — Drift classification + TSI tuning constants.
#
# Stability thresholds — chosen so a "balanced healthy thread" with
# a steady classification + small score wobble lands above the
# OSCILLATING threshold and gets the "stable" label. Tunable here,
# locked by tests.
STABILITY_DEFAULT_WINDOW: int = 10

# A thread is "oscillating" when its classification changes at least
# this fraction of times across the window. floor(n * fraction).
_OSCILLATION_FRACTION: float = 0.34

# A thread is "drifting" along EL or INS when the per-step slope of
# that score exceeds this absolute value. Slopes are reported in
# score-units-per-step, where each unit is 1/10 of the 0..10 score.
_DRIFT_SLOPE_THRESHOLD: float = 0.25

# TSI penalty weights. The score starts at 100 and is reduced by:
#   - variance of EL scores      → cap 30
#   - variance of INS scores     → cap 30
#   - classification changes     → cap 20
#   - reasoning_mode changes     → cap 10
# Final score clamped to [0, 100].
_TSI_VAR_WEIGHT: float = 5.0
_TSI_CLS_CHANGE_WEIGHT: float = 5.0
_TSI_MODE_CHANGE_WEIGHT: float = 3.0

# Operator-summary trend thresholds. Slope is computed on TSI over
# the sampled records (oldest→newest). A slope above this in either
# direction tips the classification.
_TREND_SLOPE_THRESHOLD: float = 0.5


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


def _validate(record: dict) -> ElInsRecord:
    """Defensive normalisation. Raises ValueError on bad input so the
    caller HTTP layer can surface a 400 cleanly."""
    if not isinstance(record, dict):
        raise ValueError("record must be a dict")
    operator_id = record.get("operator_id")
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    thread_id = record.get("thread_id")
    if thread_id is not None and (not isinstance(thread_id, str) or not thread_id):
        raise ValueError("thread_id must be None or a non-empty string")
    ts = record.get("timestamp")
    if ts is None:
        ts = time.time()
    try:
        ts_f = float(ts)
    except (TypeError, ValueError) as e:
        raise ValueError(f"timestamp must be a number, got {ts!r}") from e
    source = record.get("source") or "on_demand"
    if source not in VALID_SOURCES:
        raise ValueError(
            f"source must be one of {VALID_SOURCES}, got {source!r}"
        )
    result = record.get("result")
    if not isinstance(result, dict):
        raise ValueError("result must be a dict matching ElInsResult")
    # ElInsResult is structurally validated by the analyzer; we don't
    # re-validate here to keep store-side overhead minimal. The HTTP
    # layer enforces that the result came from analyze_text().
    out: dict = {
        "operator_id": operator_id,
        "thread_id":   thread_id,
        "timestamp":   ts_f,
        "source":      source,
        "result":      result,
    }
    # v70 / Unit 76 — preserve an explicitly-supplied tsi (e.g. from
    # a migration) but coerce to int + clamp to [0, 100]. New records
    # without an inbound tsi get stamped by store_el_ins_record after
    # insertion.
    raw_tsi = record.get("tsi")
    if raw_tsi is not None:
        try:
            out["tsi"] = max(0, min(100, int(raw_tsi)))
        except (TypeError, ValueError):
            pass  # silently drop bad tsi rather than reject the whole record
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def store_el_ins_record(record: dict) -> None:
    """Append a validated record to the operator's history. Newest-first
    insertion so reads stay O(N) without re-sort.

    v70 / Unit 76 — After insertion, when ``thread_id`` is set, compute
    the thread's Thread Stability Index (TSI) including this new
    record and stamp it on the record under ``tsi``. Records without
    a thread_id (None) carry no TSI — TSI is a per-thread concept.
    """
    coerced = _validate(record)
    op = coerced["operator_id"]
    bucket = _MEM.setdefault(op, [])
    # Insert at index 0 so the most recent record is always first.
    bucket.insert(0, coerced)
    # Stamp TSI on the just-inserted record. Skipped when there is
    # no thread_id (TSI is a per-thread metric).
    tid = coerced.get("thread_id")
    if isinstance(tid, str) and tid:
        try:
            stability = compute_thread_stability(
                op, tid, window=STABILITY_DEFAULT_WINDOW,
            )
            coerced["tsi"] = int(stability.get("tsi") or 0)
        except Exception:  # pragma: no cover (defensive — never break store on TSI)
            logger.debug("tsi stamping failed; record stored without tsi", exc_info=True)


def get_thread_el_ins(
    operator_id: str, thread_id: str,
) -> list[ElInsRecord]:
    """All records for ``(operator_id, thread_id)`` newest-first.
    Returns an empty list when the operator has no records or none
    match the thread."""
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    if not isinstance(thread_id, str) or not thread_id:
        raise ValueError("thread_id must be a non-empty string")
    bucket = _MEM.get(operator_id) or []
    return [r for r in bucket if r.get("thread_id") == thread_id]


def get_recent_el_ins(
    operator_id: str, limit: int = 100,
) -> list[ElInsRecord]:
    """Most recent ``limit`` records for the operator across all threads.
    Newest-first. ``limit`` is clamped to ``[1, 1000]``."""
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    try:
        n = int(limit)
    except (TypeError, ValueError):
        n = 100
    n = max(1, min(1000, n))
    bucket = _MEM.get(operator_id) or []
    return list(bucket[:n])


def get_macro_el_ins(
    operator_id: str, since: Optional[float] = None,
) -> list[ElInsRecord]:
    """Records for the operator newer than ``since`` (unix seconds). When
    ``since`` is None, returns every record (newest-first)."""
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    bucket = _MEM.get(operator_id) or []
    if since is None:
        return list(bucket)
    try:
        cutoff = float(since)
    except (TypeError, ValueError) as e:
        raise ValueError(f"since must be a number, got {since!r}") from e
    return [r for r in bucket if r["timestamp"] >= cutoff]


# ---------------------------------------------------------------------------
# v70 / Unit 76 — Drift detection + Thread Stability Index
# ---------------------------------------------------------------------------
def _variance(xs: list[float]) -> float:
    """Population variance. Returns 0.0 for empty / single-sample input."""
    n = len(xs)
    if n < 2:
        return 0.0
    mean = sum(xs) / n
    return sum((x - mean) ** 2 for x in xs) / n


def _slope(xs: list[float]) -> float:
    """Least-squares slope of ``xs`` against the integer index 0..n-1.

    Used for drift direction (positive = increasing, negative =
    decreasing). Returns 0.0 for fewer than two samples. Closed-form
    OLS for x = 0..n-1.
    """
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(xs) / n
    num = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(xs))
    den = sum((i - mean_x) ** 2 for i in range(n))
    if den == 0:
        return 0.0
    return num / den


def _classify_drift(
    el_scores: list[float],
    ins_scores: list[float],
    classifications: list[str],
) -> str:
    """Return one of stable / drifting_el / drifting_ins / oscillating.

    Rules, checked in order:
      1. classification changes >= floor(n * _OSCILLATION_FRACTION) -> oscillating
      2. |EL slope| > threshold and dominates |INS slope|           -> drifting_el
      3. |INS slope| > threshold                                    -> drifting_ins
      4. else                                                       -> stable
    """
    n = len(classifications)
    if n < 2:
        return "stable"
    cls_changes = sum(
        1 for i in range(1, n) if classifications[i] != classifications[i - 1]
    )
    osc_threshold = max(1, int(n * _OSCILLATION_FRACTION))
    if cls_changes >= osc_threshold:
        return "oscillating"
    el_s = _slope(el_scores)
    ins_s = _slope(ins_scores)
    if abs(el_s) > _DRIFT_SLOPE_THRESHOLD and abs(el_s) >= abs(ins_s):
        return "drifting_el"
    if abs(ins_s) > _DRIFT_SLOPE_THRESHOLD:
        return "drifting_ins"
    return "stable"


def _compute_tsi(
    el_scores: list[float],
    ins_scores: list[float],
    classifications: list[str],
    modes: list[str],
) -> int:
    """Deterministic 0-100 Thread Stability Index.

    Starts at 100 and applies four capped penalties so no single
    dimension can collapse the whole score. Final value clamped to
    [0, 100].
    """
    n = len(el_scores)
    if n < 2:
        return 100
    el_var = _variance(el_scores)
    ins_var = _variance(ins_scores)
    cls_changes = sum(
        1 for i in range(1, n) if classifications[i] != classifications[i - 1]
    )
    mode_changes = sum(
        1 for i in range(1, n) if modes[i] != modes[i - 1]
    )
    tsi = 100.0
    tsi -= min(30.0, el_var * _TSI_VAR_WEIGHT)
    tsi -= min(30.0, ins_var * _TSI_VAR_WEIGHT)
    tsi -= min(20.0, cls_changes * _TSI_CLS_CHANGE_WEIGHT)
    tsi -= min(10.0, mode_changes * _TSI_MODE_CHANGE_WEIGHT)
    return max(0, min(100, int(round(tsi))))


def compute_thread_stability(
    operator_id: str,
    thread_id: str,
    *,
    window: int = STABILITY_DEFAULT_WINDOW,
) -> dict:
    """Return the thread stability classification + TSI for the most
    recent ``window`` records on ``(operator_id, thread_id)``.

    Shape::

        {
          "thread_id": str,
          "stability": "stable" | "drifting_el" | "drifting_ins" | "oscillating",
          "tsi":       int (0..100),
          "window":    int    # actual sample size used
        }

    Empty / single-sample windows return ``stable`` with TSI=100 —
    "we don't yet know" maps to "presumed stable" rather than a
    confidence interval, on the principle of least surprise for new
    operators.
    """
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    if not isinstance(thread_id, str) or not thread_id:
        raise ValueError("thread_id must be a non-empty string")
    try:
        n = int(window)
    except (TypeError, ValueError):
        n = STABILITY_DEFAULT_WINDOW
    n = max(1, min(100, n))

    bucket = _MEM.get(operator_id) or []
    thread_rows = [r for r in bucket if r.get("thread_id") == thread_id]
    sampled = thread_rows[:n]  # newest-first
    if not sampled:
        return {
            "thread_id": thread_id,
            "stability": "stable",
            "tsi":       100,
            "window":    0,
        }

    # Reverse to chronological so slopes carry the right sign.
    series = list(reversed(sampled))
    el_scores = [
        float(r["result"]["analysis"].get("el_score") or 0.0)
        for r in series
    ]
    ins_scores = [
        float(r["result"]["analysis"].get("ins_score") or 0.0)
        for r in series
    ]
    classifications = [
        str(r["result"]["analysis"].get("ratio_classification") or "balanced")
        for r in series
    ]
    modes = [
        str(r["result"].get("reasoning_mode") or "normal")
        for r in series
    ]

    return {
        "thread_id": thread_id,
        "stability": _classify_drift(el_scores, ins_scores, classifications),
        "tsi":       _compute_tsi(el_scores, ins_scores, classifications, modes),
        "window":    len(series),
    }


# ---------------------------------------------------------------------------
# v70 / Unit 77 — Operator-level summary + trend
# ---------------------------------------------------------------------------
def _classify_trend(tsis: list[int]) -> str:
    """Return improving / declining / stable based on TSI slope in
    chronological order."""
    if len(tsis) < 2:
        return "stable"
    s = _slope([float(t) for t in tsis])
    if s > _TREND_SLOPE_THRESHOLD:
        return "improving"
    if s < -_TREND_SLOPE_THRESHOLD:
        return "declining"
    return "stable"


def compute_operator_summary(
    operator_id: str,
    *,
    sample_size: int = 20,
) -> dict:
    """Operator-level macro view for the EL/INS dashboard.

    Looks at the most recent ``sample_size`` records across all
    threads (newest-first) and returns the classification
    distribution, average TSI, and a deterministic trend slope.

    Shape::

        {
          "recent_classification_distribution": {
            "high_el":  int,
            "high_ins": int,
            "balanced": int
          },
          "avg_tsi":     int (0..100),
          "trend":       "improving" | "declining" | "stable",
          "sample_size": int     # actual sample size used
        }

    Records without a TSI (e.g. analyses stored without thread_id)
    are still counted toward the distribution but excluded from the
    TSI average + trend.
    """
    if not isinstance(operator_id, str) or not operator_id:
        raise ValueError("operator_id must be a non-empty string")
    try:
        n = int(sample_size)
    except (TypeError, ValueError):
        n = 20
    n = max(1, min(1000, n))

    bucket = _MEM.get(operator_id) or []
    sampled = bucket[:n]
    counts = {"high_el": 0, "high_ins": 0, "balanced": 0}
    tsis: list[int] = []
    for r in sampled:
        cls = (r.get("result") or {}).get("analysis", {}).get("ratio_classification")
        if cls in counts:
            counts[cls] += 1
        t = r.get("tsi")
        if isinstance(t, int):
            tsis.append(t)

    if tsis:
        avg_tsi = int(round(sum(tsis) / len(tsis)))
    else:
        avg_tsi = 0
    # Chronological order for trend slope (records were newest-first).
    tsis_chrono = list(reversed(tsis))
    trend = _classify_trend(tsis_chrono)

    return {
        "recent_classification_distribution": counts,
        "avg_tsi":     avg_tsi,
        "trend":       trend,
        "sample_size": len(sampled),
    }


# ---------------------------------------------------------------------------
# Test hook
# ---------------------------------------------------------------------------
def _reset_for_tests() -> None:
    _MEM.clear()
