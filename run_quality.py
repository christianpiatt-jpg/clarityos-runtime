"""
run_quality.py — score acceptance runs on a 0–100 rubric.

Phase 6A. Located at repo root alongside other backend modules per
Phase 1's path adaptation (no `backend/` directory exists).

Two exported functions, each pure (no I/O, no side effects, no
mutation of inputs, never raises):

    score_run(record)     -> dict
    score_series(records) -> dict

Components and bands are documented in
`tests/acceptance/run_quality.md`. Imports limited to stdlib `math`
and `statistics`.
"""
from __future__ import annotations

import math
import statistics
from typing import Any


# Component weights — must sum to 1.0
WEIGHTS: dict[str, float] = {
    "timing_stability":  0.20,
    "monotonicity":      0.20,
    "drift_proxy":       0.20,
    "surface_health":    0.20,
    "scenario_variance": 0.20,
}

BAND_HEALTHY_AT = 80
BAND_WARNING_AT = 50  # below this = critical_fail


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not (
        isinstance(x, float) and (math.isnan(x) or math.isinf(x))
    )


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _stability_block(record: dict) -> dict:
    block = record.get("stability") if isinstance(record, dict) else None
    return block if isinstance(block, dict) else {}


def _scenarios_block(record: dict) -> dict:
    block = record.get("scenarios") if isinstance(record, dict) else None
    return block if isinstance(block, dict) else {}


# ---------------------------------------------------------------------------
# Per-component scorers — each returns (score, optional reason)
# ---------------------------------------------------------------------------

def _score_timing_stability(stability: dict) -> tuple[float, str | None]:
    mean = stability.get("mean_ms")
    stddev = stability.get("stddev_ms")
    if not (_is_number(mean) and _is_number(stddev)) or mean <= 0:
        return 50.0, "no timing data (stability block absent or zero mean)"
    cv = stddev / mean
    if cv <= 0.05:
        return 100.0, None
    if cv >= 0.50:
        return 0.0, f"high within-run timing CV ({cv:.2f})"
    # linear from 100 at 0.05 down to 0 at 0.50
    score = _clip(100.0 * (0.50 - cv) / 0.45)
    if cv > 0.30:
        return score, f"elevated within-run timing CV ({cv:.2f})"
    return score, None


def _score_monotonicity(stability: dict) -> tuple[float, str | None]:
    mp = stability.get("monotonicity_pass")
    if mp is True:
        return 100.0, None
    if mp is False:
        return 0.0, "monotonicity broken (artifact count decreased between iterations)"
    return 50.0, "no monotonicity data"


def _score_drift_proxy(stability: dict) -> tuple[float, str | None]:
    mean = stability.get("mean_ms")
    max_ms = stability.get("max_ms")
    if not (_is_number(mean) and _is_number(max_ms)) or mean <= 0:
        return 50.0, None
    ratio = max_ms / mean
    if ratio <= 1.0:
        return 100.0, None
    if ratio >= 2.0:
        return 0.0, f"max/mean ratio {ratio:.2f} (in-run spike)"
    score = _clip(100.0 * (2.0 - ratio))
    if ratio > 1.5:
        return score, f"max/mean ratio {ratio:.2f} suggests in-run slowdown"
    return score, None


def _score_surface_health(scenarios: dict) -> tuple[float, str | None]:
    if not scenarios:
        return 50.0, "no scenario data"
    total = 0
    passed = 0
    failed: list[str] = []
    for sid, s in scenarios.items():
        if not isinstance(s, dict):
            continue
        p = s.get("pass")
        if isinstance(p, bool):
            total += 1
            if p:
                passed += 1
            else:
                failed.append(str(sid))
    if total == 0:
        return 50.0, "no scenario pass/fail recorded"
    rate = passed / total
    score = _clip(rate * 100.0)
    if failed:
        return score, "failed: " + ", ".join(failed)
    return score, None


def _score_scenario_variance(scenarios: dict) -> tuple[float, str | None]:
    durations: list[float] = []
    for s in scenarios.values():
        if not isinstance(s, dict):
            continue
        d = s.get("duration_ms")
        if _is_number(d) and d > 0:
            durations.append(float(d))
    if len(durations) < 2:
        return 50.0, "insufficient scenarios for variance check"
    mean = statistics.fmean(durations)
    if mean <= 0:
        return 50.0, None
    max_d = max(durations)
    ratio = max_d / mean
    if ratio <= 2.0:
        return 100.0, None
    if ratio >= 5.0:
        return 0.0, f"max/mean ratio {ratio:.1f} — one scenario dominates"
    score = _clip(100.0 * (5.0 - ratio) / 3.0)
    if ratio > 4.0:
        return score, f"one scenario dominates duration (max/mean={ratio:.1f})"
    return score, None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_run(record: dict) -> dict:
    """Score one run record (one entry from acceptance_runs.jsonl).

    Returns a dict with keys: run_id, score, band, components, weights,
    reasons. Never raises.
    """
    if not isinstance(record, dict):
        return {
            "run_id": None,
            "score": 0.0,
            "band": "critical_fail",
            "components": {},
            "weights": dict(WEIGHTS),
            "reasons": ["record is not a dict"],
        }

    stability = _stability_block(record)
    scenarios = _scenarios_block(record)

    components: dict[str, float] = {}
    reasons: list[str] = []

    for name, fn, src in (
        ("timing_stability",  _score_timing_stability,  stability),
        ("monotonicity",      _score_monotonicity,      stability),
        ("drift_proxy",       _score_drift_proxy,       stability),
        ("surface_health",    _score_surface_health,    scenarios),
        ("scenario_variance", _score_scenario_variance, scenarios),
    ):
        s, r = fn(src)
        components[name] = s
        if r:
            reasons.append(r)

    score = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)
    score = _clip(score)

    if score >= BAND_HEALTHY_AT:
        band = "healthy"
    elif score >= BAND_WARNING_AT:
        band = "warning"
    else:
        band = "critical_fail"

    # Run-level pass override — never report "healthy" if the run failed.
    if record.get("pass") is False and band == "healthy":
        band = "warning"
        reasons.append("run-level pass is False; capped at warning")

    return {
        "run_id": record.get("run_id"),
        "score": round(score, 1),
        "band": band,
        "components": {k: round(v, 1) for k, v in components.items()},
        "weights": dict(WEIGHTS),
        "reasons": reasons,
    }


def score_series(records: list[dict]) -> dict:
    """Score every run in `records`. Returns scores list + summary
    (mean, median, latest, trend, band counts). Never raises."""
    if not isinstance(records, list):
        records = []

    scores = [score_run(r) for r in records]
    if not scores:
        return {
            "n_runs": 0,
            "scores": [],
            "summary": {
                "mean": None, "median": None, "latest": None,
                "trend": "insufficient data",
                "n_healthy": 0, "n_warning": 0, "n_critical_fail": 0,
            },
        }

    values = [s["score"] for s in scores]
    n_healthy = sum(1 for s in scores if s["band"] == "healthy")
    n_warning = sum(1 for s in scores if s["band"] == "warning")
    n_critical = sum(1 for s in scores if s["band"] == "critical_fail")

    trend = "insufficient data"
    if len(values) >= 4:
        half = len(values) // 2
        early = statistics.fmean(values[:half])
        late = statistics.fmean(values[-half:])
        diff = late - early
        if diff > 5:
            trend = "improving"
        elif diff < -5:
            trend = "degrading"
        else:
            trend = "flat"
    elif len(values) >= 2:
        trend = "flat"

    return {
        "n_runs": len(scores),
        "scores": scores,
        "summary": {
            "mean": round(statistics.fmean(values), 1),
            "median": round(statistics.median(values), 1),
            "latest": values[-1],
            "trend": trend,
            "n_healthy": n_healthy,
            "n_warning": n_warning,
            "n_critical_fail": n_critical,
        },
    }
