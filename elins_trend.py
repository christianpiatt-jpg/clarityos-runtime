"""
elins_trend.py — ELINS9 Unit 25.

Cross-batch temporal trend engine. Reads a time-ordered list of
``(timestamp, Unit 21 output)`` tuples and emits per-metric slopes,
directional verdicts, temporal events, and a deterministic English
summary.

ROLE
----
First temporal-intelligence primitive at the BATCH level. The earlier
trend module (`elins_trends.py`, Unit 3) classifies the per-run
sequence; this module classifies the per-batch sequence across time.
Pure composition over Unit 21 outputs — no I/O, no persistence, no
randomness.

SLOPE FORMULA (locked)
----------------------
Linear-regression slope of each metric series against integer
time-index ``i = 0..n-1``::

    mean_x = (n - 1) / 2
    mean_y = sum(y) / n
    num    = sum((i - mean_x) * (y_i - mean_y))
    den    = sum((i - mean_x) ** 2)
    slope  = num / den  if den > 0 else 0

For N=2 the formula collapses to ``slope = y_1 - y_0`` (the bare
delta), which matches the spec.

DIRECTION CUTOFFS (locked)
--------------------------
    slope > +0.01   →  "up"
    slope < -0.01   →  "down"
    otherwise        →  "flat"

EVENT VOCABULARY (locked)
-------------------------
    health_deteriorating       — health direction == "down"
    health_improving           — health direction == "up"
    anomaly_rising             — anomaly direction == "up"
    anomaly_falling            — anomaly direction == "down"
    regressions_increasing     — regressions direction == "up"
    regressions_decreasing     — regressions direction == "down"
    insufficient_data          — N < 2

Events list is alpha-sorted for deterministic operator rendering.

OUTPUT SHAPE (LOCKED)
---------------------
::

    {
      "timeline": [
        {
          "timestamp": str,
          "mean_health": float,
          "mean_anomaly_fraction": float,
          "total_regressions": int,
          "group_count": int,
        },
        ...
      ],
      "trend_vectors": {
        "health":      {"slope": float, "direction": "up|down|flat"},
        "anomaly":     {"slope": float, "direction": "up|down|flat"},
        "regressions": {"slope": float, "direction": "up|down|flat"},
      },
      "events":  list[str],
      "summary": str,
    }

PUBLIC API
----------
    analyze_trends(timeline) -> dict
"""
from __future__ import annotations


# Locked direction-cutoff thresholds.
_DIRECTION_EPSILON: float = 0.01

# Locked direction vocabulary.
_DIR_UP:   str = "up"
_DIR_DOWN: str = "down"
_DIR_FLAT: str = "flat"

# Locked event vocabulary.
_EV_HEALTH_DETERIORATING:    str = "health_deteriorating"
_EV_HEALTH_IMPROVING:        str = "health_improving"
_EV_ANOMALY_RISING:          str = "anomaly_rising"
_EV_ANOMALY_FALLING:         str = "anomaly_falling"
_EV_REGRESSIONS_INCREASING:  str = "regressions_increasing"
_EV_REGRESSIONS_DECREASING:  str = "regressions_decreasing"
_EV_INSUFFICIENT_DATA:       str = "insufficient_data"


def _validate_timeline(timeline) -> None:
    if not isinstance(timeline, list):
        raise ValueError(
            f"analyze_trends expected a list, "
            f"got {type(timeline).__name__}"
        )
    for i, entry in enumerate(timeline):
        if not isinstance(entry, tuple) and not isinstance(entry, list):
            raise ValueError(
                f"timeline[{i}] must be a (timestamp, batch_output) "
                f"tuple/list, got {type(entry).__name__}"
            )
        if len(entry) != 2:
            raise ValueError(
                f"timeline[{i}] must be of length 2, got {len(entry)}"
            )
        ts, payload = entry[0], entry[1]
        if not isinstance(ts, str) or not ts:
            raise ValueError(
                f"timeline[{i}] timestamp must be a non-empty string, "
                f"got {ts!r}"
            )
        if not isinstance(payload, dict):
            raise ValueError(
                f"timeline[{i}] payload must be a dict (Unit 21 output), "
                f"got {type(payload).__name__}"
            )
        if "groups" not in payload:
            raise ValueError(
                f"timeline[{i}] payload missing 'groups' key — "
                f"expected a Unit 21 evaluate_batch output"
            )


def _batch_aggregates(payload: dict) -> dict:
    """Per-batch numeric aggregates needed for trend slope math."""
    groups = payload.get("groups", {}) or {}
    healths:    list = []
    anomalies:  list = []
    regressions: int = 0
    for data in groups.values():
        metrics = data.get("metrics", {}) or {}
        healths.append(float(metrics.get("health", 0.0)))
        anomalies.append(float(metrics.get("anomaly_fraction", 0.0)))
        regressions += int(metrics.get("regressions", 0))
    return {
        "mean_health":           (
            sum(healths) / len(healths) if healths else 0.0
        ),
        "mean_anomaly_fraction": (
            sum(anomalies) / len(anomalies) if anomalies else 0.0
        ),
        "total_regressions":    regressions,
        "group_count":          len(groups),
    }


def _ols_slope(values: list) -> float:
    """Ordinary-least-squares slope against an integer time index. Zero
    when fewer than 2 points are present."""
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    num = sum((i - mean_x) * (values[i] - mean_y) for i in range(n))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def _classify_direction(slope: float) -> str:
    if slope > _DIRECTION_EPSILON:
        return _DIR_UP
    if slope < -_DIRECTION_EPSILON:
        return _DIR_DOWN
    return _DIR_FLAT


def _events_from_directions(health_dir: str,
                            anomaly_dir: str,
                            regressions_dir: str) -> list:
    events: set = set()
    if health_dir == _DIR_DOWN:
        events.add(_EV_HEALTH_DETERIORATING)
    elif health_dir == _DIR_UP:
        events.add(_EV_HEALTH_IMPROVING)
    if anomaly_dir == _DIR_UP:
        events.add(_EV_ANOMALY_RISING)
    elif anomaly_dir == _DIR_DOWN:
        events.add(_EV_ANOMALY_FALLING)
    if regressions_dir == _DIR_UP:
        events.add(_EV_REGRESSIONS_INCREASING)
    elif regressions_dir == _DIR_DOWN:
        events.add(_EV_REGRESSIONS_DECREASING)
    return sorted(events)


def _direction_phrase(dir_label: str,
                      slope: float,
                      noun: str) -> str:
    """One short phrase for the summary. Shape:
        ``"<noun> trending upward (+0.03)"``  /
        ``"<noun> trending downward (-0.05)"``  /
        ``"<noun> flat"``.
    """
    if dir_label == _DIR_UP:
        return f"{noun} trending upward ({slope:+.2f})"
    if dir_label == _DIR_DOWN:
        return f"{noun} trending downward ({slope:+.2f})"
    return f"{noun} flat"


def _build_summary(health_dir: str,  health_slope: float,
                   anomaly_dir: str, anomaly_slope: float,
                   regressions_dir: str, regressions_slope: float) -> str:
    parts = [
        _direction_phrase(health_dir,      health_slope,      "Health"),
        _direction_phrase(anomaly_dir,     anomaly_slope,     "anomalies"),
        _direction_phrase(regressions_dir, regressions_slope, "regressions"),
    ]
    return "; ".join(parts) + "."


def _insufficient_data_response(timeline: list) -> dict:
    """Locked-shape response when there are fewer than 2 batches —
    slopes are zero, every direction is ``flat``, and the events list
    contains only ``insufficient_data``."""
    aggregates: list = []
    for ts, payload in timeline:
        agg = _batch_aggregates(payload)
        agg_with_ts = {"timestamp": ts}
        agg_with_ts.update(agg)
        aggregates.append(agg_with_ts)
    return {
        "timeline": aggregates,
        "trend_vectors": {
            "health":      {"slope": 0.0, "direction": _DIR_FLAT},
            "anomaly":     {"slope": 0.0, "direction": _DIR_FLAT},
            "regressions": {"slope": 0.0, "direction": _DIR_FLAT},
        },
        "events":  [_EV_INSUFFICIENT_DATA],
        "summary": "Insufficient data to derive a temporal trend.",
    }


def analyze_trends(timeline) -> dict:
    """Compute cross-batch temporal trend vectors.

    Args:
        timeline: time-ordered list of ``(timestamp, Unit 21 output)``
            tuples / 2-element lists. Caller is responsible for
            chronological ordering — entries are processed in input
            order. Timestamps are opaque strings (used only as labels).

    Returns:
        Locked-shape dict — see module docstring for the full schema.

    Raises:
        ValueError on a malformed timeline.
    """
    _validate_timeline(timeline)

    # Normalise tuple-or-list entries to tuples so downstream iteration
    # is uniform.
    normalised: list = [(entry[0], entry[1]) for entry in timeline]

    if len(normalised) < 2:
        return _insufficient_data_response(normalised)

    timeline_section: list = []
    health_series:      list = []
    anomaly_series:     list = []
    regressions_series: list = []
    for ts, payload in normalised:
        agg = _batch_aggregates(payload)
        timeline_section.append({
            "timestamp":              ts,
            "mean_health":            agg["mean_health"],
            "mean_anomaly_fraction":  agg["mean_anomaly_fraction"],
            "total_regressions":      agg["total_regressions"],
            "group_count":            agg["group_count"],
        })
        health_series.append(agg["mean_health"])
        anomaly_series.append(agg["mean_anomaly_fraction"])
        regressions_series.append(float(agg["total_regressions"]))

    health_slope      = _ols_slope(health_series)
    anomaly_slope     = _ols_slope(anomaly_series)
    regressions_slope = _ols_slope(regressions_series)

    health_dir      = _classify_direction(health_slope)
    anomaly_dir     = _classify_direction(anomaly_slope)
    regressions_dir = _classify_direction(regressions_slope)

    events = _events_from_directions(health_dir, anomaly_dir, regressions_dir)
    summary = _build_summary(
        health_dir, health_slope,
        anomaly_dir, anomaly_slope,
        regressions_dir, regressions_slope,
    )

    return {
        "timeline": timeline_section,
        "trend_vectors": {
            "health":      {"slope": health_slope,      "direction": health_dir},
            "anomaly":     {"slope": anomaly_slope,     "direction": anomaly_dir},
            "regressions": {"slope": regressions_slope, "direction": regressions_dir},
        },
        "events":  events,
        "summary": summary,
    }
