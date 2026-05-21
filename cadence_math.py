"""
cadence_math.py — analyze run-spacing patterns from acceptance_runs.jsonl.

Phase 6C. Located at repo root per Phase 1's path adaptation.
Pure stdlib (math, statistics, datetime). Never raises.

Two exported functions:
    compute_cadence(records)         -> dict
    detect_irregularities(records)   -> dict

Records are expected oldest-first (post_run_ingest.py appends so the
JSONL is naturally chronological). Each record's `finished_at` field
is the primary timestamp; `started_at` is the fallback.
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from typing import Any


# Classification thresholds (coefficient of variation = stddev/mean).
CV_REGULAR_AT   = 0.5    # CV <= 0.5  → regular
CV_CLUSTERED_AT = 1.0    # 0.5 < CV <= 1.0 → clustered; > 1.0 → erratic

# Outlier rule: gap > 3 × median is an outlier.
OUTLIER_MULTIPLE = 3.0

# Cluster rule: gap < median / 2 contributes to a cluster run.
CLUSTER_FRACTION = 0.5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ts(s: Any) -> float | None:
    """ISO 8601 → epoch seconds, or None on parse failure."""
    if not isinstance(s, str) or not s:
        return None
    try:
        # datetime.fromisoformat handles "2026-05-12T09:30:41.012+00:00"
        # but not the trailing "Z". Convert "Z" → "+00:00".
        candidate = s[:-1] + "+00:00" if s.endswith("Z") else s
        dt = datetime.fromisoformat(candidate)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, AttributeError):
        return None


def _record_timestamp(record: Any) -> float | None:
    """Pick `finished_at`, fallback to `started_at`."""
    if not isinstance(record, dict):
        return None
    t = _parse_ts(record.get("finished_at"))
    if t is not None:
        return t
    return _parse_ts(record.get("started_at"))


def _gaps_minutes(records: list[dict]) -> list[float]:
    """Compute consecutive-gap minutes between sorted timestamps."""
    if not isinstance(records, list):
        return []
    times: list[float] = []
    for r in records:
        t = _record_timestamp(r)
        if t is not None:
            times.append(t)
    if len(times) < 2:
        return []
    times.sort()  # defensive: ensure chronological even if input was reordered
    gaps: list[float] = []
    for i in range(1, len(times)):
        d = times[i] - times[i - 1]
        if d > 0:
            gaps.append(d / 60.0)
    return gaps


def _classify(cv: float | None) -> str:
    if cv is None:
        return "insufficient data"
    if cv <= CV_REGULAR_AT:
        return "regular"
    if cv <= CV_CLUSTERED_AT:
        return "clustered"
    return "erratic"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_cadence(records: list[dict]) -> dict:
    """Run-spacing stats in minutes."""
    if not isinstance(records, list):
        records = []
    gaps = _gaps_minutes(records)
    if not gaps:
        return {
            "n_runs": len(records),
            "n_gaps": 0,
            "avg_spacing_minutes":      None,
            "median_spacing_minutes":   None,
            "longest_gap_minutes":      None,
            "shortest_gap_minutes":     None,
            "stddev_minutes":           None,
            "coefficient_of_variation": None,
            "classification": "insufficient data",
        }
    avg = statistics.fmean(gaps)
    med = statistics.median(gaps)
    sd = statistics.stdev(gaps) if len(gaps) >= 2 else 0.0
    cv: float | None = (sd / avg) if avg > 0 else None
    return {
        "n_runs": len(records),
        "n_gaps": len(gaps),
        "avg_spacing_minutes":      avg,
        "median_spacing_minutes":   med,
        "longest_gap_minutes":      max(gaps),
        "shortest_gap_minutes":     min(gaps),
        "stddev_minutes":           sd,
        "coefficient_of_variation": cv,
        "classification":           _classify(cv),
    }


def detect_irregularities(records: list[dict]) -> dict:
    """Identify outlier gaps and burst clusters."""
    if not isinstance(records, list):
        records = []
    gaps = _gaps_minutes(records)
    if len(gaps) < 3:
        return {
            "n_gaps": len(gaps),
            "median_minutes": None,
            "outlier_gaps": [],
            "cluster_count": 0,
            "classification": "insufficient data",
        }
    med = statistics.median(gaps)

    outliers: list[dict] = []
    if med > 0:
        for i, g in enumerate(gaps):
            if g > OUTLIER_MULTIPLE * med:
                outliers.append({
                    "gap_index": i,
                    "gap_minutes": g,
                    "multiple_of_median": g / med,
                })

    cluster_count = 0
    in_cluster = False
    cluster_threshold = (med * CLUSTER_FRACTION) if med > 0 else 0
    for g in gaps:
        if med > 0 and g < cluster_threshold:
            if not in_cluster:
                cluster_count += 1
                in_cluster = True
        else:
            in_cluster = False

    cad = compute_cadence(records)
    return {
        "n_gaps": len(gaps),
        "median_minutes": med,
        "outlier_gaps": outliers,
        "cluster_count": cluster_count,
        "classification": cad["classification"],
    }
