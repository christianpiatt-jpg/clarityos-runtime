"""
trust_center_math.py — composite trust telemetry for the founder layer.

Phase 7A. Located at repo root per Phase 1's path adaptation.
Pure stdlib + sibling repo-root imports (stability_math, run_quality,
cadence_math). Never raises.

Three exported functions:
    compute_trust_signal(records)   -> dict
    compute_alignment(records)      -> dict
    compute_warning_levels(records) -> dict

The thresholds and weights are documented in
`tests/acceptance/trust_center_telemetry.md`.
"""
from __future__ import annotations

import statistics
from typing import Any

import stability_math
import run_quality
import cadence_math


# Composite weights — must sum to 1.0
WEIGHTS: dict[str, float] = {
    "quality_mean":   0.40,
    "stability":      0.30,
    "cadence_health": 0.30,
}

# Levels
LEVEL_STABLE     = "stable"
LEVEL_DEGRADING  = "degrading"
LEVEL_CRITICAL   = "critical"

# Thresholds
THRESHOLD_STABLE_AT     = 75
THRESHOLD_DEGRADING_AT  = 50

# Cadence classification → cadence_health score
_CADENCE_SCORE_BY_CLASS = {
    "regular":   90.0,
    "clustered": 70.0,
    "erratic":   50.0,
    "insufficient data": 60.0,
}


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _drift_scaling(drift_pct: Any) -> float:
    """Drift scaling factor applied to the monotonicity pass rate."""
    if not isinstance(drift_pct, (int, float)):
        return 1.0
    d = float(drift_pct)
    if d > 0.30:
        return 0.50
    if d > 0.15:
        return 0.75
    if d > 0.05:
        return 0.90
    return 1.0


def compute_trust_signal(records: list[dict]) -> dict:
    """Composite 0–100 trust signal + level."""
    if not isinstance(records, list):
        records = []

    qual = run_quality.score_series(records)
    drift = stability_math.compute_timing_drift(records)
    curve = stability_math.compute_stability_curve(records)
    cad = cadence_math.compute_cadence(records)

    # Quality component
    quality_score = qual["summary"]["mean"]
    if not isinstance(quality_score, (int, float)):
        quality_score = 50.0

    # Stability component: monotonicity pass rate × drift scaling
    pass_rate = curve["summary"].get("monotonicity_pass_rate")
    if isinstance(pass_rate, (int, float)):
        stability_score = float(pass_rate) * 100.0
    else:
        stability_score = 50.0
    stability_score *= _drift_scaling(drift.get("drift_pct"))
    stability_score = _clip(stability_score)

    # Cadence component
    cadence_score = _CADENCE_SCORE_BY_CLASS.get(
        cad.get("classification") or "insufficient data",
        60.0,
    )

    components = {
        "quality_mean":   quality_score,
        "stability":      stability_score,
        "cadence_health": cadence_score,
    }
    signal_score = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
    signal_score = _clip(signal_score)

    if signal_score >= THRESHOLD_STABLE_AT:
        level = LEVEL_STABLE
    elif signal_score >= THRESHOLD_DEGRADING_AT:
        level = LEVEL_DEGRADING
    else:
        level = LEVEL_CRITICAL

    return {
        "signal_score": round(signal_score, 1),
        "level": level,
        "components": {k: round(v, 1) for k, v in components.items()},
        "weights": dict(WEIGHTS),
        "thresholds": {
            "stable_at":    THRESHOLD_STABLE_AT,
            "degrading_at": THRESHOLD_DEGRADING_AT,
        },
        "inputs": {
            "drift_pct": drift.get("drift_pct"),
            "monotonicity_pass_rate": pass_rate,
            "cadence_classification": cad.get("classification"),
        },
    }


def compute_alignment(records: list[dict]) -> dict:
    """Cross-surface alignment derived from per-scenario pass rates."""
    if not isinstance(records, list):
        records = []
    health = stability_math.compute_surface_health(records)
    sc = health.get("scenario_health") or {}
    if not isinstance(sc, dict) or not sc:
        return {
            "alignment_score":  None,
            "surface_variance": None,
            "n_scenarios":      0,
            "scenario_pass_rates": {},
        }
    rates: list[float] = []
    rate_map: dict[str, float] = {}
    for sid, s in sc.items():
        if not isinstance(s, dict):
            continue
        r = s.get("pass_rate")
        if isinstance(r, (int, float)):
            rates.append(float(r))
            rate_map[sid] = float(r)

    if len(rates) == 0:
        return {
            "alignment_score":  None,
            "surface_variance": None,
            "n_scenarios":      0,
            "scenario_pass_rates": {},
        }
    if len(rates) == 1:
        return {
            "alignment_score":  round(rates[0] * 100.0, 1),
            "surface_variance": 0.0,
            "n_scenarios":      1,
            "scenario_pass_rates": rate_map,
        }
    var = statistics.variance(rates)
    alignment = _clip(100.0 * (1.0 - 4.0 * var))
    return {
        "alignment_score":  round(alignment, 1),
        "surface_variance": round(var, 4),
        "n_scenarios":      len(rates),
        "scenario_pass_rates": rate_map,
    }


def compute_warning_levels(records: list[dict]) -> dict:
    """Band counts pass-through from run_quality.score_series.summary."""
    qual = run_quality.score_series(records)
    summary = qual["summary"]
    return {
        "n_runs":          qual["n_runs"],
        "n_critical_fail": summary.get("n_critical_fail", 0),
        "n_warning":       summary.get("n_warning", 0),
        "n_healthy":       summary.get("n_healthy", 0),
        "trend":           summary.get("trend", "insufficient data"),
    }
