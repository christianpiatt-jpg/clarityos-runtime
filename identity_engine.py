"""
identity_engine.py — descriptive identity-coherence layer.

Phase 8B. Located at repo root per Phase 1's path adaptation.
Pure stdlib + sibling repo-root imports (run_quality, cadence_math,
stability_math, trust_center_math). Never raises.

Two exported functions:
    compute_identity_profile(records)         -> dict
    compare_surfaces(records_by_surface)      -> dict

Documented in `tests/acceptance/identity_coherence.md`.

This module is intentionally descriptive. It introduces no new
measurements; it summarizes existing ones. See the doc for the
"what this model does NOT do" boundary (no personality typing, no
intent inference, no PII).
"""
from __future__ import annotations

import statistics
from typing import Any

import run_quality
import cadence_math
import stability_math
import trust_center_math


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def _is_number(x: Any) -> bool:
    return isinstance(x, (int, float))


# ---------------------------------------------------------------------------
# Per-dimension scorers — each returns (score, descriptor)
# ---------------------------------------------------------------------------

def _score_tone(records: list[dict]) -> tuple[float, str]:
    qual = run_quality.score_series(records)
    scores = [
        s.get("score") for s in (qual.get("scores") or [])
        if isinstance(s, dict) and _is_number(s.get("score"))
    ]
    if len(scores) < 2:
        return 50.0, "insufficient data"
    sd = statistics.stdev(scores)
    # stddev 0 → 100; stddev 30 → 0; linear in between.
    score = _clip(100.0 * (1.0 - sd / 30.0))
    if sd < 5:
        descriptor = "consistent"
    elif sd < 15:
        descriptor = "varied"
    else:
        descriptor = "erratic"
    return score, descriptor


def _score_timing(records: list[dict]) -> tuple[float, str]:
    cad = cadence_math.compute_cadence(records)
    drift = stability_math.compute_timing_drift(records)
    cv = cad.get("coefficient_of_variation")
    drift_pct = drift.get("drift_pct")

    cadence_part = 50.0
    if _is_number(cv):
        cadence_part = _clip(100.0 * (1.0 - float(cv)))

    drift_part = 50.0
    if _is_number(drift_pct):
        d = float(drift_pct)
        if d <= 0.05:
            drift_part = 100.0
        elif d <= 0.15:
            drift_part = 75.0
        elif d <= 0.30:
            drift_part = 50.0
        else:
            drift_part = 25.0

    score = _clip((cadence_part + drift_part) / 2.0)
    if score >= 80:
        descriptor = "steady"
    elif score >= 50:
        descriptor = "shifting"
    else:
        descriptor = "unsteady"
    return score, descriptor


def _score_decision_style(records: list[dict]) -> tuple[float, str]:
    if not records:
        return 50.0, "no data"
    fast = sum(1 for r in records if isinstance(r, dict) and r.get("mode") == "fast")
    full = sum(1 for r in records if isinstance(r, dict) and r.get("mode") == "full")
    total = fast + full
    if total == 0:
        return 50.0, "no mode data"
    p_fast = fast / total
    concentration = abs(p_fast - 0.5) * 2.0  # [0, 1]
    score = _clip(60.0 + concentration * 20.0)
    if concentration > 0.7:
        descriptor = "focused"
    elif concentration > 0.3:
        descriptor = "adaptive"
    else:
        descriptor = "balanced"
    return score, descriptor


def _score_escalation_style(records: list[dict]) -> tuple[float, str]:
    qual = run_quality.score_series(records)
    n = qual.get("n_runs", 0)
    if n == 0:
        return 50.0, "no data"
    summary = qual.get("summary") or {}
    n_critical = summary.get("n_critical_fail", 0)
    crit_rate = n_critical / n if n > 0 else 0.0
    score = _clip(100.0 * (1.0 - crit_rate / 0.20))
    if crit_rate < 0.02:
        descriptor = "restrained"
    elif crit_rate < 0.10:
        descriptor = "responsive"
    else:
        descriptor = "alarmed"
    return score, descriptor


def _score_trust_posture(records: list[dict]) -> tuple[float, str]:
    if not records:
        return 50.0, "no data"
    sig = trust_center_math.compute_trust_signal(records)
    score_val = sig.get("signal_score")
    if not _is_number(score_val):
        score_val = 50.0
    level = sig.get("level", "degrading")
    descriptor_map = {
        "stable": "confident",
        "degrading": "guarded",
        "critical": "defensive",
    }
    descriptor = descriptor_map.get(level, "neutral")
    return _clip(float(score_val)), descriptor


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

DIMENSION_NAMES = (
    "tone", "timing", "decision_style", "escalation_style", "trust_posture",
)


def _empty_profile(n_runs: int, note: str | None) -> dict:
    notes = [note] if note else []
    return {
        "score": None,
        "dimensions": {
            name: {"score": None, "descriptor": "no data"}
            for name in DIMENSION_NAMES
        },
        "notes": notes,
        "n_runs": n_runs,
    }


def compute_identity_profile(records: list[dict]) -> dict:
    """Return a descriptive identity profile for the run series.

    Always returns a dict with keys: score, dimensions, notes, n_runs.
    Never raises; on bad/empty input, returns an empty/neutral profile.
    """
    if not isinstance(records, list):
        return _empty_profile(0, "input is not a list")
    if len(records) == 0:
        return _empty_profile(0, "no records ingested yet")

    notes: list[str] = []
    dimensions: dict[str, dict] = {}

    scorers = (
        ("tone",             _score_tone),
        ("timing",           _score_timing),
        ("decision_style",   _score_decision_style),
        ("escalation_style", _score_escalation_style),
        ("trust_posture",    _score_trust_posture),
    )
    for name, fn in scorers:
        try:
            s, desc = fn(records)
            dimensions[name] = {"score": round(s, 1), "descriptor": desc}
        except Exception as exc:  # defensive — never raise
            dimensions[name] = {
                "score": 50.0,
                "descriptor": f"error: {type(exc).__name__}",
            }
            notes.append(f"{name}: {type(exc).__name__}: {exc}")

    valid = [
        d["score"] for d in dimensions.values()
        if isinstance(d.get("score"), (int, float))
    ]
    composite = round(statistics.fmean(valid), 1) if valid else None

    return {
        "score": composite,
        "dimensions": dimensions,
        "notes": notes,
        "n_runs": len(records),
    }


def compare_surfaces(records_by_surface: dict) -> dict:
    """Per-surface profiles + cross-surface delta summary.

    Input: dict[surface_name -> list of records].
    Output: {per_surface, cross_surface_delta}.
    """
    if not isinstance(records_by_surface, dict):
        return {"per_surface": {}, "cross_surface_delta": None}

    per_surface: dict[str, dict] = {}
    for name, records in records_by_surface.items():
        if not isinstance(name, str):
            continue
        if not isinstance(records, list):
            records = []
        per_surface[name] = compute_identity_profile(records)

    if not per_surface:
        return {"per_surface": {}, "cross_surface_delta": None}

    overall_scores = [
        p.get("score") for p in per_surface.values()
        if isinstance(p.get("score"), (int, float))
    ]

    if not overall_scores:
        delta = {
            "n_surfaces": len(per_surface),
            "max_score": None,
            "min_score": None,
            "spread": None,
            "interpretation": "no scored surfaces yet",
        }
    elif len(overall_scores) == 1:
        delta = {
            "n_surfaces": len(per_surface),
            "max_score": overall_scores[0],
            "min_score": overall_scores[0],
            "spread": 0.0,
            "interpretation": "single surface — no cross-surface comparison",
        }
    else:
        max_s = max(overall_scores)
        min_s = min(overall_scores)
        spread = max_s - min_s
        if spread <= 5:
            interp = "aligned"
        elif spread <= 15:
            interp = "mild divergence"
        elif spread <= 30:
            interp = "noticeable divergence"
        else:
            interp = "significant divergence"
        delta = {
            "n_surfaces": len(per_surface),
            "max_score": round(max_s, 1),
            "min_score": round(min_s, 1),
            "spread": round(spread, 1),
            "interpretation": interp,
        }

    return {
        "per_surface": per_surface,
        "cross_surface_delta": delta,
    }
