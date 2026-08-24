"""
resilience_pipe.py — the pipe from stored records to a resilience read.

SECOND CANON CONSUMER. Follows the shape set by canon.py:
declare the canon entry implemented, fail loud, never default.

WHAT IT DOES
------------
    records  ->  series  ->  resilience.assess()  ->  reading

It extracts a numeric series from stored EL/INS records (or any
record list with a comparable shape), runs the early-warning
assessment, and returns a reading that carries its own provenance:
which canon entry it implements, which field it read, how many
samples, and what it refused to report.

CANON
-----
Declares canon "120" — Collapse Mechanics:
    "Collapse occurs when pressure exceeds the stability envelope.
     The sequence begins with curvature, followed by drift, then
     acceleration, and finally jerk. Collapse is not random; it
     follows a mechanical progression. Operators intervene early by
     reducing gradients and restoring boundary integrity."

The declaration is a CLAIM THE OUTPUT CAN BE CHECKED AGAINST, not an
assertion of conformance. This module computes two derivatives of a
scalar series. Canon 120 describes a four-stage progression. The
divergence is visible by construction — that is the point of
declaring it.

NO MODEL CALL. NO NETWORK. NO #G. Runs inside the perimeter.
"""
from __future__ import annotations

from typing import Any, Optional, Sequence, TypedDict

import resilience

CANON_ENTRY = "120"

# Fields the pipe knows how to read out of an EL/INS record, in
# preference order. Each is a path of keys from the record root.
KNOWN_PATHS: tuple[tuple[str, ...], ...] = (
    ("result", "analysis", "el_score"),
    ("result", "analysis", "ins_score"),
    ("tsi",),
)


class PipeError(ValueError):
    """resilience_pipe's own failure type."""


class Reading(TypedDict):
    canon: str
    field: Optional[str]
    status: str
    n: int
    windows: int
    variance_trend: Optional[float]
    autocorr_trend: Optional[float]
    agreement: Optional[str]
    reason: Optional[str]
    line: str


def _dig(record: Any, path: Sequence[str]) -> Any:
    cur = record
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def extract_series(
    records: Sequence[dict],
    *,
    path: Optional[Sequence[str]] = None,
) -> tuple[list[float], str]:
    """Pull a numeric series out of a record list, OLDEST FIRST.

    Stores in this system return NEWEST FIRST (el_ins_store inserts at
    index 0). Trends are computed against increasing index, so the
    caller must not hand this function a newest-first list without
    saying so — this function reverses, and states that it does.

    Returns (series, field_label). Raises PipeError when no known
    field is present, rather than returning an empty series: an empty
    series and a series of unreadable records are different states.
    """
    if not isinstance(records, (list, tuple)):
        raise PipeError("records must be a list or tuple")
    if not records:
        raise PipeError("records is empty — nothing to read")

    candidates = (tuple(path),) if path else KNOWN_PATHS

    for p in candidates:
        vals: list[float] = []
        for r in records:
            v = _dig(r, p)
            if isinstance(v, (int, float)) and v == v:
                vals.append(float(v))
        if len(vals) == len(records):
            # complete coverage — reverse to chronological
            return list(reversed(vals)), ".".join(p)

    tried = " · ".join(".".join(p) for p in candidates)
    raise PipeError(
        f"no field present on ALL {len(records)} records. Tried: {tried}. "
        f"A partially-present field is refused: a gap would silently "
        f"shorten the series and shift every trend."
    )


def read(
    records: Sequence[dict],
    *,
    window: int = resilience.MIN_WINDOW_AUTOCORR,
    path: Optional[Sequence[str]] = None,
) -> Reading:
    """records -> Reading. Default window is the MEASURED minimum for
    the autocorrelation half, so the default call reports both signals
    or says why it cannot."""
    series, field = extract_series(records, path=path)
    a = resilience.assess(series, window=window)
    return {
        "canon": CANON_ENTRY,
        "field": field,
        "status": a["status"],
        "n": a["n"],
        "windows": a["windows"],
        "variance_trend": a["variance_trend"],
        "autocorr_trend": a["autocorr_trend"],
        "agreement": a["agreement"],
        "reason": a["reason"],
        "line": resilience.describe(a),
    }


def canon_text() -> Optional[dict]:
    """The canon entry this module declares, loaded at call time.

    Returns None when the canon is not on the path — this pipe does
    NOT require the canon to run, but a caller that wants to check the
    declaration against the source can get it here. Import-time
    coupling is deliberately avoided so a missing canon cannot take
    the runtime down.
    """
    try:
        import canon  # noqa: PLC0415 — deliberate late import
    except Exception:
        return None
    return canon.get(CANON_ENTRY)
