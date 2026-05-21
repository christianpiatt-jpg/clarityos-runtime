"""
elins_structural_trend.py — ELINS10 Unit 27.

Structural trend engine. Detects regime-level structural shifts —
breakpoints, volatility variance, regime class — across a chronological
batch sequence. Sits between the linear-trend engine (Unit 25) and the
regime-comparison engine (Unit 29) in the ELINS arc.

ROLE
----
Long-arc structural-intelligence primitive at the BATCH level. While
Unit 25 reads slope direction, this module reads STRUCTURE — where
the series breaks, how volatile the regime is, whether the system is
in a stable, transitional, or unstable phase. Pure composition over
Unit 21 outputs — no I/O, no persistence, no randomness.

VOLATILITY PROXY (locked)
-------------------------
For each batch i::

    volatility[i] = anomaly_fraction[i] + 0.5 * total_regressions[i]

This is the spec's canonical volatility proxy — anomaly_fraction is
already normalised in [0, 1] and total_regressions is weighted at
half-strength so a single regression doesn't dominate a clean batch.
``volatility_variance`` is the population variance of the proxy
series.

BREAKPOINT DETECTION (locked)
-----------------------------
For each metric series (health, anomaly, regressions) and each index
``i >= 2``, the rolling std is computed over the **prior** window
``values[max(0, i-3):i]`` (excludes index ``i`` so a candidate value
isn't contaminating its own threshold). A breakpoint fires when::

    abs(value[i] - value[i-1]) > 2 * rolling_std

Index 1 can never fire (no prior context to derive a rolling std).
Constant windows yield std = 0; any non-zero delta then trips a
breakpoint — that matches operator intuition for "the series was
flat and suddenly moved."

REGIME CLASSIFICATION (locked)
------------------------------
    unstable     — breakpoints exist  AND  volatility_variance >= 0.02
    stable       — no breakpoints     AND  volatility_variance <  0.005
    transition   — anything in between

The transition bucket is the catch-all for mixed signals (e.g.
breakpoints + low variance, or no breakpoints + moderate variance).

STRUCTURAL EVENTS (locked)
--------------------------
    breakpoint_detected                       — at least one breakpoint
    volatility_spike                          — variance >  0.02
    regime_shift_stable_to_transition         — current regime is transition
    regime_shift_transition_to_unstable       — current regime is unstable
    structural_deterioration                  — health series sloping down
    structural_improvement                    — health series sloping up
    insufficient_data                         — N < 3

The two ``regime_shift_*`` events name the level the timeline has
shifted INTO, not the path taken — Unit 29 / 30 use them as level
markers.

PUBLIC API
----------
    analyze_structural_trends(timeline) -> dict

This is the canonical Unit 27 contract that Units 29 + 30 depend on:
the output dict's ``regime_class``, ``volatility_variance``,
``breakpoints``, and ``structural_events`` keys are locked.
"""
from __future__ import annotations

import math


# Locked thresholds.
_VAR_STABLE_MAX:   float = 0.005
_VAR_UNSTABLE_MIN: float = 0.02
_BREAKPOINT_MULTIPLIER: float = 2.0
_ROLLING_WINDOW: int = 3
_HEALTH_SLOPE_EPSILON: float = 0.01

# Locked regime vocabulary.
_REGIME_STABLE:     str = "stable"
_REGIME_TRANSITION: str = "transition"
_REGIME_UNSTABLE:   str = "unstable"

# Locked metric labels (mirror Unit 25).
_METRIC_HEALTH:      str = "health"
_METRIC_ANOMALY:     str = "anomaly"
_METRIC_REGRESSIONS: str = "regressions"

# Locked event vocabulary.
_EV_BREAKPOINT_DETECTED:                str = "breakpoint_detected"
_EV_VOLATILITY_SPIKE:                   str = "volatility_spike"
_EV_REGIME_SHIFT_STABLE_TO_TRANSITION:  str = "regime_shift_stable_to_transition"
_EV_REGIME_SHIFT_TRANSITION_TO_UNSTABLE: str = "regime_shift_transition_to_unstable"
_EV_STRUCTURAL_DETERIORATION:           str = "structural_deterioration"
_EV_STRUCTURAL_IMPROVEMENT:             str = "structural_improvement"
_EV_INSUFFICIENT_DATA:                  str = "insufficient_data"


def _validate_timeline(timeline) -> None:
    if not isinstance(timeline, list):
        raise ValueError(
            f"analyze_structural_trends expected a list, "
            f"got {type(timeline).__name__}"
        )
    for i, entry in enumerate(timeline):
        if not isinstance(entry, (tuple, list)):
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
                f"timeline[{i}] payload missing 'groups' key — expected "
                f"a Unit 21 evaluate_batch output"
            )


def _batch_aggregates(payload: dict) -> dict:
    """Per-batch aggregates needed for structural analysis (mirror
    Unit 25's signature)."""
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
        "total_regressions":     regressions,
    }


def _population_variance(values: list) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)


def _population_stddev(values: list) -> float:
    return math.sqrt(_population_variance(values))


def _detect_breakpoints_in_series(values: list,
                                  timestamps: list,
                                  metric: str) -> list:
    """Detect breakpoints in one metric series. Returns a list of
    ``{"timestamp", "metric", "delta"}`` entries — one per detected
    breakpoint, in chronological order."""
    out: list = []
    for i in range(1, len(values)):
        # Rolling-std window covers the PRIOR points (excludes i so
        # the candidate doesn't pollute its own threshold).
        start = max(0, i - _ROLLING_WINDOW)
        window = values[start:i]
        if len(window) < 2:
            continue
        rolling_std = _population_stddev(window)
        delta = values[i] - values[i - 1]
        if abs(delta) > _BREAKPOINT_MULTIPLIER * rolling_std:
            out.append({
                "timestamp": timestamps[i],
                "metric":    metric,
                "delta":     delta,
            })
    return out


def _classify_regime(breakpoints: list,
                     volatility_variance: float) -> str:
    has_breakpoints = bool(breakpoints)
    if has_breakpoints and volatility_variance >= _VAR_UNSTABLE_MIN:
        return _REGIME_UNSTABLE
    if not has_breakpoints and volatility_variance < _VAR_STABLE_MAX:
        return _REGIME_STABLE
    return _REGIME_TRANSITION


def _ols_slope(values: list) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    num = sum((i - mean_x) * (values[i] - mean_y) for i in range(n))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den if den > 0 else 0.0


def _build_events(regime: str,
                  breakpoints: list,
                  volatility_variance: float,
                  health_series: list) -> list:
    events: set = set()
    if breakpoints:
        events.add(_EV_BREAKPOINT_DETECTED)
    if volatility_variance > _VAR_UNSTABLE_MIN:
        events.add(_EV_VOLATILITY_SPIKE)
    if regime == _REGIME_TRANSITION:
        events.add(_EV_REGIME_SHIFT_STABLE_TO_TRANSITION)
    elif regime == _REGIME_UNSTABLE:
        events.add(_EV_REGIME_SHIFT_TRANSITION_TO_UNSTABLE)
    slope = _ols_slope(health_series)
    if slope > _HEALTH_SLOPE_EPSILON:
        events.add(_EV_STRUCTURAL_IMPROVEMENT)
    elif slope < -_HEALTH_SLOPE_EPSILON:
        events.add(_EV_STRUCTURAL_DETERIORATION)
    return sorted(events)


def _build_summary(regime: str,
                   breakpoints: list,
                   volatility_variance: float) -> str:
    plural = "s" if len(breakpoints) != 1 else ""
    return (
        f"Regime: {regime}. "
        f"{len(breakpoints)} breakpoint{plural} detected. "
        f"Volatility variance {volatility_variance:.3f}."
    )


def _insufficient_data_response(timeline_section: list) -> dict:
    """Locked-shape response for N < 3 — the regime is reported as
    ``stable`` (no signal to suggest otherwise) and the sole event is
    ``insufficient_data``."""
    return {
        "timeline":           timeline_section,
        "regime_class":       _REGIME_STABLE,
        "volatility_variance": 0.0,
        "breakpoints":        [],
        "structural_events":  [_EV_INSUFFICIENT_DATA],
        "summary":            "Insufficient data for structural analysis.",
    }


def analyze_structural_trends(timeline) -> dict:
    """Compute the structural-trend reading over a chronological batch
    sequence.

    Args:
        timeline: time-ordered list of ``(timestamp, Unit 21 output)``
            tuples / 2-element lists. Caller is responsible for
            chronological ordering. Timestamps are opaque strings.

    Returns:
        Locked-shape dict matching the Unit 27 contract documented in
        the module docstring. The exact key set is::

            {
              "timeline":            list[dict],
              "regime_class":        "stable | transition | unstable",
              "volatility_variance": float,
              "breakpoints":         list[{"timestamp", "metric", "delta"}],
              "structural_events":   list[str],   # alpha-sorted
              "summary":             str,
            }

    Raises:
        ValueError on a malformed timeline.
    """
    _validate_timeline(timeline)

    normalised: list = [(entry[0], entry[1]) for entry in timeline]
    timestamps  = [ts for ts, _ in normalised]

    timeline_section: list = []
    health_series:      list = []
    anomaly_series:     list = []
    regressions_series: list = []
    volatility_series:  list = []
    for ts, payload in normalised:
        agg = _batch_aggregates(payload)
        volatility = (
            agg["mean_anomaly_fraction"]
            + 0.5 * float(agg["total_regressions"])
        )
        timeline_section.append({
            "timestamp":              ts,
            "mean_health":            agg["mean_health"],
            "mean_anomaly_fraction":  agg["mean_anomaly_fraction"],
            "total_regressions":      agg["total_regressions"],
            "volatility":             volatility,
        })
        health_series.append(agg["mean_health"])
        anomaly_series.append(agg["mean_anomaly_fraction"])
        regressions_series.append(float(agg["total_regressions"]))
        volatility_series.append(volatility)

    if len(normalised) < 3:
        return _insufficient_data_response(timeline_section)

    volatility_variance = _population_variance(volatility_series)

    breakpoints: list = []
    breakpoints.extend(_detect_breakpoints_in_series(
        health_series, timestamps, _METRIC_HEALTH,
    ))
    breakpoints.extend(_detect_breakpoints_in_series(
        anomaly_series, timestamps, _METRIC_ANOMALY,
    ))
    breakpoints.extend(_detect_breakpoints_in_series(
        regressions_series, timestamps, _METRIC_REGRESSIONS,
    ))

    regime = _classify_regime(breakpoints, volatility_variance)
    events = _build_events(
        regime, breakpoints, volatility_variance, health_series,
    )
    summary = _build_summary(regime, breakpoints, volatility_variance)

    return {
        "timeline":            timeline_section,
        "regime_class":        regime,
        "volatility_variance": volatility_variance,
        "breakpoints":         breakpoints,
        "structural_events":   events,
        "summary":             summary,
    }
