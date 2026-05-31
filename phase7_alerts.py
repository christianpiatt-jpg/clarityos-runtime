# phase7_alerts.py
"""
Phase 7.6 — Temporal Alerts & Stability Thresholds (operator guidance layer).

Pure, deterministic mapping from the Phase 7.3 analytics signals to a list of
operator-facing stability alerts. This is GUIDANCE ONLY — read-only text the
console surfaces; it changes no behavior, writes nothing, mutates nothing.

    compute_alerts(analytics: dict) -> list[str]

No I/O, no wall-clock, no randomness, no persistence, and no imports beyond the
stdlib — nothing from the CI-gated runtime spine.

See ``phase7_spec.md`` ("Phase 7.6 — Temporal Alerts").
"""

# --- Thresholds (module constants) ------------------------------------------
FORECAST_ALERT_THRESHOLD = 0.40        # stability_forecast strictly below → alert
VELOCITY_ALERT_THRESHOLD = 0.20        # drift_velocity strictly above → alert
ACCELERATION_ALERT_THRESHOLD = 0.15    # drift_acceleration strictly above → alert
COHERENCE_DECLINE_THRESHOLD = -0.10    # coherence_trend strictly below → alert
DIVERGING_TRAJECTORY = "Diverging"

# --- Alert messages (constants so the endpoint, console, and tests agree) ---
ALERT_DIVERGING = "High drift detected — operator identity destabilizing"
ALERT_LOW_FORECAST = "Low stability forecast — consider reviewing recent operator actions"
ALERT_RAPID_DRIFT = "Rapid drift — identity moving faster than expected"
ALERT_DRIFT_ACCELERATION = "Drift acceleration rising — potential instability"
ALERT_COHERENCE_DECLINE = "Coherence declining — structural alignment weakening"
ALERT_NONE = "No alerts — operator trajectory stable"


def compute_alerts(analytics: dict) -> list[str]:
    """Map an analytics block to operator-facing stability alerts.

    Each rule is evaluated independently (any number may fire); the alerts are
    returned in a fixed, deterministic order. When no rule fires, the single
    neutral ``ALERT_NONE`` message is returned. Missing keys fall back to
    no-alert defaults so a partial analytics block never raises.
    """
    trajectory = analytics.get("trajectory", "Stable")
    stability_forecast = analytics.get("stability_forecast", 1.0)
    drift_velocity = analytics.get("drift_velocity", 0.0)
    drift_acceleration = analytics.get("drift_acceleration", 0.0)
    coherence_trend = analytics.get("coherence_trend", 0.0)

    alerts: list[str] = []
    if trajectory == DIVERGING_TRAJECTORY:
        alerts.append(ALERT_DIVERGING)
    if stability_forecast < FORECAST_ALERT_THRESHOLD:
        alerts.append(ALERT_LOW_FORECAST)
    if drift_velocity > VELOCITY_ALERT_THRESHOLD:
        alerts.append(ALERT_RAPID_DRIFT)
    if drift_acceleration > ACCELERATION_ALERT_THRESHOLD:
        alerts.append(ALERT_DRIFT_ACCELERATION)
    if coherence_trend < COHERENCE_DECLINE_THRESHOLD:
        alerts.append(ALERT_COHERENCE_DECLINE)

    if not alerts:
        return [ALERT_NONE]
    return alerts
