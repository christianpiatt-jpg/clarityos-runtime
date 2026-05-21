"""
narrative_drift.py — detect drift in acceptance metrics across runs.

Phase 7B. Located at repo root per Phase 1's path adaptation.
Pure stdlib + sibling repo-root imports (run_quality, stability_math).
Never raises.

Two exported functions:
    detect_drift(records)  -> dict
    drift_score(records)   -> float

Documented in `tests/acceptance/narrative_drift.md`.
"""
from __future__ import annotations

import statistics
from typing import Any

import run_quality
import stability_math


# Detection thresholds (mirror tests/acceptance/narrative_drift.md).
TIMING_DRIFT_FLAG_AT     = 0.15   # drift_pct > 15% → flag
QUALITY_DELTA_FLAG_AT    = -10.0  # late half mean is ≥10 points below
SCENARIO_RATE_DROP_AT    = -0.10  # recent quarter dropped ≥10 percentage points

MIN_RUNS_FOR_DETECTION   = 4


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _split_halves(values: list[float]) -> tuple[list[float], list[float]]:
    if not values:
        return [], []
    if len(values) == 1:
        return values, values
    mid = len(values) // 2
    return values[:mid], values[mid:]


def _per_scenario_pass_rates(records: list[dict]) -> dict[str, float]:
    counts: dict[str, list[int]] = {}
    for r in records:
        if not isinstance(r, dict):
            continue
        scenarios = r.get("scenarios")
        if not isinstance(scenarios, dict):
            continue
        for sid, s in scenarios.items():
            if not isinstance(sid, str) or not isinstance(s, dict):
                continue
            p = s.get("pass")
            if isinstance(p, bool):
                counts.setdefault(sid, []).append(1 if p else 0)
    return {sid: statistics.fmean(vs) for sid, vs in counts.items() if vs}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_drift(records: list[dict]) -> dict:
    """Detect drifting component-level signals + early per-scenario signals."""
    if not isinstance(records, list):
        records = []

    if len(records) < MIN_RUNS_FOR_DETECTION:
        return {
            "drifting": False,
            "drift_components": [],
            "early_signals": [],
            "n_runs": len(records),
            "note": (
                f"need >= {MIN_RUNS_FOR_DETECTION} runs for drift detection; "
                f"have {len(records)}"
            ),
        }

    drifting: list[dict] = []
    early_signals: list[dict] = []

    # 1. Timing drift via stability_math
    drift_block = stability_math.compute_timing_drift(records)
    drift_pct = drift_block.get("drift_pct")
    if isinstance(drift_pct, (int, float)) and drift_pct > TIMING_DRIFT_FLAG_AT:
        drifting.append({
            "signal":         "iteration_mean_ms",
            "drift_pct":      drift_pct,
            "interpretation": drift_block.get("interpretation"),
        })

    # 2. Quality score drift (early half vs late half)
    qual_series = run_quality.score_series(records)
    score_values: list[float] = [
        s["score"] for s in qual_series.get("scores") or []
        if isinstance(s, dict) and isinstance(s.get("score"), (int, float))
    ]
    if len(score_values) >= MIN_RUNS_FOR_DETECTION:
        early, late = _split_halves(score_values)
        if early and late:
            e_mean = statistics.fmean(early)
            l_mean = statistics.fmean(late)
            diff = l_mean - e_mean
            if diff < QUALITY_DELTA_FLAG_AT:
                drifting.append({
                    "signal":     "run_quality_score",
                    "early_mean": round(e_mean, 1),
                    "late_mean":  round(l_mean, 1),
                    "delta":      round(diff, 1),
                })

    # 3. Per-scenario pass-rate drift in the most recent quarter
    n = len(records)
    quarter = max(1, n // 4)
    recent = records[-quarter:]
    prior = records[:-quarter] if n > quarter else []
    if prior and recent:
        prior_rates = _per_scenario_pass_rates(prior)
        recent_rates = _per_scenario_pass_rates(recent)
        for sid, recent_rate in recent_rates.items():
            prior_rate = prior_rates.get(sid)
            if prior_rate is None:
                continue
            delta = recent_rate - prior_rate
            if delta < SCENARIO_RATE_DROP_AT:
                early_signals.append({
                    "signal": f"scenario_pass_rate:{sid}",
                    "prior":  round(prior_rate, 3),
                    "recent": round(recent_rate, 3),
                    "delta":  round(delta, 3),
                })

    return {
        "drifting":         len(drifting) > 0,
        "drift_components": drifting,
        "early_signals":    early_signals,
        "n_runs":           len(records),
    }


def drift_score(records: list[dict]) -> float:
    """Composite 0.0–1.0 drift severity. 0.0 = no drift; 1.0 = severe."""
    if not isinstance(records, list) or len(records) < MIN_RUNS_FOR_DETECTION:
        return 0.0

    detected = detect_drift(records)

    base = min(1.0, 0.25 * len(detected.get("drift_components") or []))
    early = min(0.25, 0.05 * len(detected.get("early_signals") or []))

    drift_block = stability_math.compute_timing_drift(records)
    drift_pct = drift_block.get("drift_pct")
    timing_contrib = 0.0
    if isinstance(drift_pct, (int, float)):
        d = float(drift_pct)
        if d > 0.30:
            timing_contrib = 0.30
        elif d > 0.15:
            timing_contrib = 0.15
        elif d > 0.05:
            timing_contrib = 0.05

    score = min(1.0, base + early + timing_contrib)
    return round(score, 3)
