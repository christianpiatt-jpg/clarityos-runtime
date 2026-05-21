"""
el_ins/anomaly.py — Unit 80 / v72.

Lightweight anomaly detection over EL/INS records. Pure deterministic;
no LLM. The four rules from the spec map a record (plus optionally the
operator's prior record) to zero or more ``Anomaly`` events.

Rules
-----
1. ``EL > 7.5``                                            → ``high_el``        severity 3
2. ``INS < 2.0``                                           → ``low_ins``        severity 3
3. ``TSI > 85``                                            → ``tsi_spike``      severity 4
4. Quadrant jump ≥ 2 vs prior record (i.e. diagonal)       → ``quadrant_jump``  severity 5

Quadrant numbering (from EL/INS scores against threshold 3.0):

    Q1  grounding              (EL high, INS low)
    Q2  analysis               (EL low,  INS high)
    Q3  structured_reflection  (EL high, INS high)
    Q4  stabilization          (EL low,  INS low)

Quadrant "distance" is Manhattan distance on the 2×2 lattice — diagonal
neighbours score 2, axis neighbours score 1, same quadrant scores 0.
A "jump ≥ 2" therefore means a diagonal transition between two
consecutive records on the same thread.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Literal, Optional, TypedDict

AnomalyType = Literal["high_el", "low_ins", "tsi_spike", "quadrant_jump"]

ANOMALY_TYPES: tuple = ("high_el", "low_ins", "tsi_spike", "quadrant_jump")

# Thresholds + severities, locked here so tests can read them.
_EL_HIGH_THRESHOLD: float = 7.5
_INS_LOW_THRESHOLD: float = 2.0
_TSI_SPIKE_THRESHOLD: int = 85
_QUADRANT_JUMP_DISTANCE: int = 2     # Manhattan distance on the 2×2 lattice
_QUADRANT_SCORE_HIGH: float = 3.0    # mirrors intelligence_kernel._RM_SCORE_HIGH

_SEVERITY: dict[str, int] = {
    "high_el":        3,
    "low_ins":        3,
    "tsi_spike":      4,
    "quadrant_jump":  5,
}


class Anomaly(TypedDict):
    id:          str        # uuid4 hex
    timestamp:   float      # unix seconds
    type:        str        # one of ANOMALY_TYPES
    severity:    int        # 1..5
    message:     str        # short human-readable
    record_id:   str        # "{thread_id}:{record_timestamp_ms}" — back-pointer
    operator_id: str        # owning operator
    thread_id:   Optional[str]


# ---------------------------------------------------------------------------
# Quadrant helpers
# ---------------------------------------------------------------------------
def _quadrant(el: float, ins: float) -> int:
    """Return 1..4 per the spec's quadrant numbering.

    Q1 grounding, Q2 analysis, Q3 structured_reflection, Q4 stabilization.
    """
    el_high = float(el) >= _QUADRANT_SCORE_HIGH
    ins_high = float(ins) >= _QUADRANT_SCORE_HIGH
    if el_high and not ins_high:
        return 1
    if not el_high and ins_high:
        return 2
    if el_high and ins_high:
        return 3
    return 4


# Manhattan distance between two quadrants on the 2x2 lattice.
# We hard-code instead of computing because the lattice is tiny and
# this lookup is the documented invariant the tests assert.
_QUADRANT_DISTANCE: dict[tuple[int, int], int] = {
    (1, 1): 0, (1, 2): 2, (1, 3): 1, (1, 4): 1,
    (2, 1): 2, (2, 2): 0, (2, 3): 1, (2, 4): 1,
    (3, 1): 1, (3, 2): 1, (3, 3): 0, (3, 4): 2,
    (4, 1): 1, (4, 2): 1, (4, 3): 2, (4, 4): 0,
}


def _quadrant_distance(q_a: int, q_b: int) -> int:
    return _QUADRANT_DISTANCE.get((q_a, q_b), 0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect_anomalies(
    record: dict,
    *,
    prior_record: Optional[dict] = None,
) -> list[Anomaly]:
    """Inspect ``record`` (plus optionally the prior record on the same
    thread) and return a list of anomalies.

    The function is pure: it never reads or writes the store. Caller
    (kernel integration or test harness) decides where the anomalies
    go.

    ``record`` shape: an ``ElInsRecord`` dict as stored in
    ``el_ins_store``. ``prior_record`` is the previous record on the
    same ``(operator_id, thread_id)`` newest-first stack, or None when
    this is the first record on the thread.
    """
    if not isinstance(record, dict):
        raise ValueError("record must be a dict")

    analysis = (record.get("result") or {}).get("analysis", {})
    el = float(analysis.get("el_score") or 0.0)
    ins = float(analysis.get("ins_score") or 0.0)
    tsi = record.get("tsi") if isinstance(record.get("tsi"), int) else None

    operator_id = str(record.get("operator_id") or "")
    thread_id = record.get("thread_id")
    timestamp = float(record.get("timestamp") or time.time())
    record_id = _record_id_for(record)

    anomalies: list[Anomaly] = []

    # Rule 1: high EL
    if el > _EL_HIGH_THRESHOLD:
        anomalies.append(_mk(
            "high_el", operator_id, thread_id, timestamp, record_id,
            f"EL score {el:.2f} exceeds threshold {_EL_HIGH_THRESHOLD}",
        ))

    # Rule 2: low INS
    if ins < _INS_LOW_THRESHOLD:
        anomalies.append(_mk(
            "low_ins", operator_id, thread_id, timestamp, record_id,
            f"INS score {ins:.2f} below threshold {_INS_LOW_THRESHOLD}",
        ))

    # Rule 3: TSI spike
    if isinstance(tsi, int) and tsi > _TSI_SPIKE_THRESHOLD:
        anomalies.append(_mk(
            "tsi_spike", operator_id, thread_id, timestamp, record_id,
            f"TSI {tsi}/100 exceeds spike threshold {_TSI_SPIKE_THRESHOLD}",
        ))

    # Rule 4: quadrant jump vs prior
    if prior_record is not None and isinstance(prior_record, dict):
        prior_analysis = (prior_record.get("result") or {}).get("analysis", {})
        prior_el = float(prior_analysis.get("el_score") or 0.0)
        prior_ins = float(prior_analysis.get("ins_score") or 0.0)
        q_now = _quadrant(el, ins)
        q_prior = _quadrant(prior_el, prior_ins)
        dist = _quadrant_distance(q_prior, q_now)
        if dist >= _QUADRANT_JUMP_DISTANCE:
            anomalies.append(_mk(
                "quadrant_jump", operator_id, thread_id, timestamp, record_id,
                f"Quadrant jump Q{q_prior}→Q{q_now} (distance {dist})",
            ))

    return anomalies


def _record_id_for(record: dict) -> str:
    """Stable back-pointer string for a stored record.

    Format: ``{thread_id}:{timestamp_ms}``. Records without thread_id
    use ``no_thread:{ts_ms}`` so the id remains unique within an
    operator's history.
    """
    tid = record.get("thread_id") or "no_thread"
    ts_ms = int(float(record.get("timestamp") or 0.0) * 1000)
    return f"{tid}:{ts_ms}"


def _mk(
    anom_type: AnomalyType,
    operator_id: str,
    thread_id: Optional[str],
    timestamp: float,
    record_id: str,
    message: str,
) -> Anomaly:
    return {
        "id":          uuid.uuid4().hex,
        "timestamp":   timestamp,
        "type":        anom_type,
        "severity":    _SEVERITY[anom_type],
        "message":     message,
        "record_id":   record_id,
        "operator_id": operator_id,
        "thread_id":   thread_id,
    }
