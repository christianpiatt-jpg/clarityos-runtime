"""
stability_math.py — pure-stdlib longitudinal metrics for the acceptance
harness.

Phase 5B. Located at repo root rather than `backend/acceptance/` because
Phase 1's path adaptation established that backend Python modules live
at the repo root (no `backend/` directory exists; existing modules
like `incident_store.py` and `acceptance_dashboard.py` live alongside
`app.py`).

Three exported functions, each pure (no I/O, no side effects, no
mutation of inputs):

    compute_stability_curve(records)  -> dict
    compute_timing_drift(records)     -> dict
    compute_surface_health(records)   -> dict

Each accepts the list of dicts read from
`tests/acceptance/reports/acceptance_runs.jsonl` (one dict per run,
written by `post_run_ingest.py`). Each function tolerates partial /
missing fields and never raises.

No third-party imports. Imports limited to `math` and `statistics`.
"""
from __future__ import annotations

import math
import statistics
from typing import Any


# ---------------------------------------------------------------------------
# Helpers — internal
# ---------------------------------------------------------------------------

def _stability_block(record: dict) -> dict | None:
    """Pull the stability block written by post_run_ingest.py."""
    block = record.get("stability") if isinstance(record, dict) else None
    return block if isinstance(block, dict) else None


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float)) and not (
        isinstance(x, float) and (math.isnan(x) or math.isinf(x))
    )


def _safe_mean(xs: list[float]) -> float | None:
    if not xs:
        return None
    return statistics.fmean(xs)


def _safe_stdev(xs: list[float]) -> float | None:
    if len(xs) < 2:
        return 0.0 if xs else None
    return statistics.stdev(xs)


# ---------------------------------------------------------------------------
# 1. Stability curve — per-run time-series points
# ---------------------------------------------------------------------------

def compute_stability_curve(records: list[dict]) -> dict:
    """Reduce JSONL records to a per-run time-series of stability metrics.

    Output shape:
        {
          "n_runs": int,
          "n_with_stability": int,
          "points": [
            {
              "run_id": str | None,
              "ts_finished": str | None,
              "monotonicity_pass": bool | None,
              "mean_ms": float | None,
              "max_ms": int | None,
              "stddev_ms": float | None,
            },
            ...
          ],
          "summary": {
            "monotonicity_pass_count": int,
            "monotonicity_fail_count": int,
            "monotonicity_pass_rate": float | None,
          },
        }

    Order: oldest first → newest last (chronological for the chart).
    """
    if not isinstance(records, list):
        records = []

    points: list[dict] = []
    pass_count = 0
    fail_count = 0

    # Records arrive in JSONL order — oldest first because
    # post_run_ingest.py appends. Preserve that order.
    for r in records:
        if not isinstance(r, dict):
            continue
        block = _stability_block(r)
        point = {
            "run_id":            r.get("run_id"),
            "ts_finished":       r.get("finished_at"),
            "monotonicity_pass": None,
            "mean_ms":           None,
            "max_ms":            None,
            "stddev_ms":         None,
        }
        if block is not None:
            mp = block.get("monotonicity_pass")
            if isinstance(mp, bool):
                point["monotonicity_pass"] = mp
                if mp:
                    pass_count += 1
                else:
                    fail_count += 1
            for src, dst in (
                ("mean_ms",   "mean_ms"),
                ("max_ms",    "max_ms"),
                ("stddev_ms", "stddev_ms"),
            ):
                v = block.get(src)
                if _is_number(v):
                    point[dst] = v
        points.append(point)

    n_with_stability = pass_count + fail_count
    pass_rate: float | None = None
    if n_with_stability > 0:
        pass_rate = pass_count / n_with_stability

    return {
        "n_runs": len(points),
        "n_with_stability": n_with_stability,
        "points": points,
        "summary": {
            "monotonicity_pass_count": pass_count,
            "monotonicity_fail_count": fail_count,
            "monotonicity_pass_rate":  pass_rate,
        },
    }


# ---------------------------------------------------------------------------
# 2. Timing drift — baseline vs current, plus simple linear slope
# ---------------------------------------------------------------------------

_DEFAULT_WINDOW = 5


def compute_timing_drift(
    records: list[dict],
    *,
    baseline_window: int = _DEFAULT_WINDOW,
    current_window: int = _DEFAULT_WINDOW,
) -> dict:
    """Compute per-iteration mean drift between a baseline and current
    window, plus a simple linear-regression slope across all runs.

    Output shape:
        {
          "n_runs_with_timing": int,
          "baseline_window": int,
          "current_window": int,
          "baseline_ms": float | None,
          "current_ms": float | None,
          "drift_pct": float | None,
          "slope_ms_per_run": float | None,
          "interpretation": str,
        }

    Interpretation buckets (mirror tests/acceptance/stability_curves.md):
        drift_pct ≤ +0.05  → "stable"
        +0.05 < drift_pct ≤ +0.15 → "mild drift"
        +0.15 < drift_pct ≤ +0.30 → "meaningful slowdown"
        drift_pct > +0.30 → "severe slowdown"
        drift_pct < -0.05 → "improving"
    """
    if not isinstance(records, list):
        records = []
    if baseline_window < 1:
        baseline_window = _DEFAULT_WINDOW
    if current_window < 1:
        current_window = _DEFAULT_WINDOW

    means: list[float] = []
    for r in records:
        block = _stability_block(r) or {}
        v = block.get("mean_ms")
        if _is_number(v):
            means.append(float(v))

    n = len(means)
    if n == 0:
        return {
            "n_runs_with_timing": 0,
            "baseline_window": baseline_window,
            "current_window": current_window,
            "baseline_ms": None,
            "current_ms": None,
            "drift_pct": None,
            "slope_ms_per_run": None,
            "interpretation": "insufficient data",
        }

    bw = min(baseline_window, n)
    cw = min(current_window, n)
    baseline = _safe_mean(means[:bw])
    current  = _safe_mean(means[-cw:])

    drift_pct: float | None = None
    if baseline is not None and baseline > 0 and current is not None:
        drift_pct = (current - baseline) / baseline

    # Simple linear regression: y = a*x + b across (run_index, mean_ms).
    slope: float | None = None
    if n >= 2:
        xs = list(range(n))
        x_mean = statistics.fmean(xs)
        y_mean = statistics.fmean(means)
        num = sum((xs[i] - x_mean) * (means[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        if den > 0:
            slope = num / den

    interp = "insufficient data"
    if drift_pct is None:
        interp = "insufficient data" if n < 2 else "stable"
    else:
        if drift_pct < -0.05:
            interp = "improving"
        elif drift_pct <= 0.05:
            interp = "stable"
        elif drift_pct <= 0.15:
            interp = "mild drift"
        elif drift_pct <= 0.30:
            interp = "meaningful slowdown"
        else:
            interp = "severe slowdown"

    return {
        "n_runs_with_timing": n,
        "baseline_window": bw,
        "current_window": cw,
        "baseline_ms": baseline,
        "current_ms": current,
        "drift_pct": drift_pct,
        "slope_ms_per_run": slope,
        "interpretation": interp,
    }


# ---------------------------------------------------------------------------
# 3. Surface health — per-scenario pass rate as a surface proxy
# ---------------------------------------------------------------------------

_SURFACE_HEALTH_WINDOW = 20


def compute_surface_health(
    records: list[dict],
    *,
    window: int = _SURFACE_HEALTH_WINDOW,
) -> dict:
    """Per-scenario health over the last `window` runs.

    JSONL records do not carry per-surface timings; this function
    therefore returns scenario-level metrics as a surface proxy. The
    caller is told via `surface_proxy_note`.

    Output shape:
        {
          "n_runs_examined": int,
          "window": int,
          "scenario_health": {
            "01_onboarding_per_surface": {
              "pass_rate": float,    # 0.0..1.0
              "n_pass": int,
              "n_total": int,
              "mean_duration_ms": float | None,
            },
            ...
          },
          "surface_proxy_note": str,
        }
    """
    if not isinstance(records, list):
        records = []
    if window < 1:
        window = _SURFACE_HEALTH_WINDOW

    examined = records[-window:] if len(records) > window else list(records)
    n_examined = len(examined)

    scenario_pass: dict[str, int] = {}
    scenario_total: dict[str, int] = {}
    scenario_durations: dict[str, list[float]] = {}

    for r in examined:
        if not isinstance(r, dict):
            continue
        scenarios = r.get("scenarios")
        if not isinstance(scenarios, dict):
            continue
        for sid, payload in scenarios.items():
            if not isinstance(sid, str) or not isinstance(payload, dict):
                continue
            p = payload.get("pass")
            if not isinstance(p, bool):
                continue
            scenario_total[sid] = scenario_total.get(sid, 0) + 1
            if p:
                scenario_pass[sid] = scenario_pass.get(sid, 0) + 1
            d = payload.get("duration_ms")
            if _is_number(d):
                scenario_durations.setdefault(sid, []).append(float(d))

    health: dict[str, dict] = {}
    for sid, total in scenario_total.items():
        n_pass = scenario_pass.get(sid, 0)
        durations = scenario_durations.get(sid, [])
        health[sid] = {
            "pass_rate": (n_pass / total) if total > 0 else 0.0,
            "n_pass": n_pass,
            "n_total": total,
            "mean_duration_ms": _safe_mean(durations),
        }

    return {
        "n_runs_examined": n_examined,
        "window": window,
        "scenario_health": health,
        "surface_proxy_note": (
            "true per-surface granularity requires re-ingesting the full "
            "report.json files. This function reports scenario-level "
            "health as a proxy for surface health: scenarios that exercise "
            "all three surfaces (01, 04) approximate global surface health; "
            "scenarios that only exercise web (02, 03) approximate web/"
            "backend health."
        ),
    }
