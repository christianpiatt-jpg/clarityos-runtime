"""
surfaces_unification.py — Phase 10 read-only coherence layer.

Pure stdlib. Two public functions:

    summarize_surfaces(records) -> dict
        Per-surface counts, last-run timestamps, declared surface set.

    compute_surface_coherence(records) -> dict
        A single 0..100 coherence score plus the three component deltas
        that produced it (timing, trust, identity).

Contract per tests/acceptance/surfaces_unification.md:
    - read-only;
    - never raises (returns empty/neutral structures on failure);
    - never modifies records;
    - never persists.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timezone
from typing import Any


_SURFACES_DECLARED = ("PHONE", "WEB", "OPERATOR")


def _safe_iso_to_dt(s: Any):
    if not isinstance(s, str) or not s:
        return None
    try:
        if s.endswith("Z"):
            s2 = s[:-1] + "+00:00"
        else:
            s2 = s
        return datetime.fromisoformat(s2)
    except Exception:
        return None


def _max_iso(records: list, surface: str) -> str | None:
    best = None
    best_dt = None
    for r in records:
        if not isinstance(r, dict):
            continue
        if r.get("surface") != surface:
            continue
        ts = r.get("timestamp") or r.get("ts") or r.get("ingested_at")
        dt = _safe_iso_to_dt(ts)
        if dt is None:
            continue
        if best_dt is None or dt > best_dt:
            best_dt = dt
            best = ts
    return best


def _coerce_records(records: Any) -> list:
    if not isinstance(records, list):
        return []
    return [r for r in records if isinstance(r, dict)]


def summarize_surfaces(records) -> dict:
    """Bucket acceptance records by their declared `surface` field.

    Returns a structure with:
      - declared:   the canonical surface set the OS knows about
      - present:    surfaces actually observed in `records`
      - counts:     per-surface record count (declared surfaces + 'unknown')
      - last_runs:  per-surface most-recent timestamp (or None)
      - n_records:  total record count examined
    """
    try:
        recs = _coerce_records(records)
        counts: dict[str, int] = {s: 0 for s in _SURFACES_DECLARED}
        counts["unknown"] = 0
        for r in recs:
            s = r.get("surface")
            if isinstance(s, str) and s in counts:
                counts[s] += 1
            else:
                counts["unknown"] += 1
        last_runs: dict[str, Any] = {}
        for s in _SURFACES_DECLARED:
            last_runs[s] = _max_iso(recs, s)
        present = sorted(s for s in _SURFACES_DECLARED if counts.get(s, 0) > 0)
        return {
            "declared":  list(_SURFACES_DECLARED),
            "present":   present,
            "counts":    counts,
            "last_runs": last_runs,
            "n_records": len(recs),
        }
    except Exception:
        return {
            "declared":  list(_SURFACES_DECLARED),
            "present":   [],
            "counts":    {s: 0 for s in _SURFACES_DECLARED} | {"unknown": 0},
            "last_runs": {s: None for s in _SURFACES_DECLARED},
            "n_records": 0,
        }


def _hours_since(iso: str | None, now: datetime) -> float | None:
    dt = _safe_iso_to_dt(iso)
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600.0


def _per_surface_score(records: list, surface: str, key: str) -> float | None:
    """Mean of a numeric scalar field across the most recent N records of a surface."""
    vals: list[float] = []
    for r in records:
        if r.get("surface") != surface:
            continue
        v = r.get(key)
        if isinstance(v, (int, float)):
            vals.append(float(v))
    if not vals:
        return None
    return statistics.fmean(vals[-5:])


def compute_surface_coherence(records) -> dict:
    """Compute a 0..100 coherence score from three signal deltas.

    Components (each contributes up to ~33 points; clipped to 0..100):
      - timing_delta_score:    how synchronized are the surfaces' last-run
                                timestamps (lower spread = higher score).
      - trust_delta_score:     spread of `trust_signal` / `trust_score` across
                                surfaces (lower = higher score).
      - identity_delta_score:  spread of `identity_coherence` across surfaces
                                (lower = higher score).
    """
    try:
        recs = _coerce_records(records)
        if not recs:
            return {
                "coherence_score": 0,
                "components": {
                    "timing_delta_score":   0,
                    "trust_delta_score":    0,
                    "identity_delta_score": 0,
                },
                "deltas": {},
                "interpretation": "no records",
            }

        now = datetime.now(timezone.utc)
        last_run_hours: dict[str, float | None] = {}
        for s in _SURFACES_DECLARED:
            last_run_hours[s] = _hours_since(_max_iso(recs, s), now)
        active = [v for v in last_run_hours.values() if v is not None]
        if len(active) >= 2:
            timing_spread = max(active) - min(active)
            timing_delta_score = max(0.0, 1.0 - min(1.0, timing_spread / 168.0))
        elif len(active) == 1:
            timing_delta_score = 0.5
        else:
            timing_delta_score = 0.0

        trust_per_surface: dict[str, float | None] = {}
        for s in _SURFACES_DECLARED:
            v = _per_surface_score(recs, s, "trust_score")
            if v is None:
                v = _per_surface_score(recs, s, "trust_signal")
            trust_per_surface[s] = v
        trust_active = [v for v in trust_per_surface.values() if v is not None]
        if len(trust_active) >= 2:
            trust_spread = max(trust_active) - min(trust_active)
            trust_delta_score = max(0.0, 1.0 - min(1.0, trust_spread))
        elif len(trust_active) == 1:
            trust_delta_score = 0.5
        else:
            trust_delta_score = 0.0

        id_per_surface: dict[str, float | None] = {}
        for s in _SURFACES_DECLARED:
            id_per_surface[s] = _per_surface_score(recs, s, "identity_coherence")
        id_active = [v for v in id_per_surface.values() if v is not None]
        if len(id_active) >= 2:
            id_spread = max(id_active) - min(id_active)
            identity_delta_score = max(0.0, 1.0 - min(1.0, id_spread))
        elif len(id_active) == 1:
            identity_delta_score = 0.5
        else:
            identity_delta_score = 0.0

        score_0_1 = (
            0.34 * timing_delta_score
            + 0.33 * trust_delta_score
            + 0.33 * identity_delta_score
        )
        score = int(round(max(0.0, min(1.0, score_0_1)) * 100))

        if score >= 80:
            interp = "surfaces operationally unified"
        elif score >= 50:
            interp = "surfaces aligned with one or more deltas worth review"
        elif score >= 20:
            interp = "surfaces partially diverged"
        else:
            interp = "no coherent surface picture"

        return {
            "coherence_score": score,
            "components": {
                "timing_delta_score":   round(timing_delta_score, 3),
                "trust_delta_score":    round(trust_delta_score, 3),
                "identity_delta_score": round(identity_delta_score, 3),
            },
            "deltas": {
                "last_run_hours_per_surface": {
                    s: (round(v, 2) if isinstance(v, (int, float)) else None)
                    for s, v in last_run_hours.items()
                },
                "trust_per_surface": {
                    s: (round(v, 4) if isinstance(v, (int, float)) else None)
                    for s, v in trust_per_surface.items()
                },
                "identity_per_surface": {
                    s: (round(v, 4) if isinstance(v, (int, float)) else None)
                    for s, v in id_per_surface.items()
                },
            },
            "interpretation": interp,
        }
    except Exception:
        return {
            "coherence_score": 0,
            "components": {
                "timing_delta_score":   0,
                "trust_delta_score":    0,
                "identity_delta_score": 0,
            },
            "deltas": {},
            "interpretation": "compute failure (returned neutral)",
        }
