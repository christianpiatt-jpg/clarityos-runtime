# phase7_analytics.py
"""
Phase 7.3 — Temporal Analytics & Stability Forecasting.

Pure, deterministic analytics over a Phase 7.1 telemetry history
(``list[TelemetryRecord]``). Produces forward-looking stability signals:

  * compute_drift_velocity(history)     -> float  in [-1, 1]
  * compute_drift_acceleration(history) -> float  in [-1, 1]
  * compute_coherence_trend(history)    -> float  in [-1, 1]
  * compute_stability_forecast(v, a, c) -> float  in [0, 1]
  * classify_trajectory(forecast)       -> "Stable"|"Recovering"|"Wobbling"|"Diverging"

No I/O, no wall-clock, no randomness, no side effects. The only import is the
Phase 7 record type (``phase7_storage.TelemetryRecord``) — nothing from the
CI-gated runtime spine.

See ``phase7_spec.md`` ("Phase 7.3 — Temporal Analytics & Forecasting").
"""
from phase7_storage import TelemetryRecord

# Regression window: the most-recent N telemetry points feed every slope.
WINDOW = 5

# Stability-forecast term weights (sum to 1.0).
FORECAST_VELOCITY_WEIGHT = 0.4
FORECAST_ACCELERATION_WEIGHT = 0.3
FORECAST_COHERENCE_WEIGHT = 0.3

# Trajectory classification thresholds on the forecast (inclusive lower bounds).
STABLE_THRESHOLD = 0.75
RECOVERING_THRESHOLD = 0.50
WOBBLING_THRESHOLD = 0.25


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _slope(values: list[float]) -> float:
    """Least-squares slope of ``values`` against their position indices
    (0, 1, ..., n-1). Fewer than 2 points has no slope → 0.0."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    num = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0.0:
        return 0.0
    return num / den


def _recent_series(history: list[TelemetryRecord], attr: str) -> list[float]:
    """The most-recent ``WINDOW`` records' ``attr`` values, in chronological
    order, with missing (``None``) values skipped."""
    out: list[float] = []
    for record in history[-WINDOW:]:
        value = getattr(record, attr)
        if value is not None:
            out.append(value)
    return out


def compute_drift_velocity(history: list[TelemetryRecord]) -> float:
    """Slope of drift over the recent window, clamped to [-1, 1].

    Fewer than 2 usable drift points → 0.0. Positive = drift rising
    (destabilizing); negative = drift falling.
    """
    series = _recent_series(history, "drift")
    if len(series) < 2:
        return 0.0
    return _clamp(_slope(series), -1.0, 1.0)


def compute_drift_acceleration(history: list[TelemetryRecord]) -> float:
    """Second derivative of drift: the slope of drift's first differences
    (local velocity) over the recent window, clamped to [-1, 1].

    Fewer than 3 usable drift points → 0.0. Positive = drift accelerating;
    negative = drift decelerating.
    """
    series = _recent_series(history, "drift")
    if len(series) < 3:
        return 0.0
    first_diffs = [series[i + 1] - series[i] for i in range(len(series) - 1)]
    return _clamp(_slope(first_diffs), -1.0, 1.0)


def compute_coherence_trend(history: list[TelemetryRecord]) -> float:
    """Slope of coherence-health over the recent window, clamped to [-1, 1].

    Fewer than 2 usable points → 0.0. Positive = coherence improving
    (stabilizing); negative = coherence eroding.
    """
    series = _recent_series(history, "coherence_health")
    if len(series) < 2:
        return 0.0
    return _clamp(_slope(series), -1.0, 1.0)


def compute_stability_forecast(
    velocity: float,
    acceleration: float,
    coherence_trend: float,
) -> float:
    """Forward-looking stability score in [0, 1].

        forecast = 0.4 * (1 - |velocity|)          # steadier drift  → higher
                 + 0.3 * (-acceleration + 1) / 2   # not accelerating → higher
                 + 0.3 * (coherence_trend + 1) / 2 # coherence rising → higher

    Inputs are expected in their natural ranges (velocity / acceleration /
    coherence_trend ∈ [-1, 1]); the result is clamped to [0, 1].
    """
    forecast = (
        FORECAST_VELOCITY_WEIGHT * (1.0 - abs(velocity))
        + FORECAST_ACCELERATION_WEIGHT * (-acceleration + 1.0) / 2.0
        + FORECAST_COHERENCE_WEIGHT * (coherence_trend + 1.0) / 2.0
    )
    return _clamp(forecast, 0.0, 1.0)


def classify_trajectory(forecast: float) -> str:
    """Map a stability forecast to a trajectory label (inclusive lower bounds)."""
    if forecast >= STABLE_THRESHOLD:
        return "Stable"
    if forecast >= RECOVERING_THRESHOLD:
        return "Recovering"
    if forecast >= WOBBLING_THRESHOLD:
        return "Wobbling"
    return "Diverging"
