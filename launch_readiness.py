"""
launch_readiness.py — Phase 12 read-only founder-facing readiness layer.

Pure stdlib. Two public functions:

    compute_readiness(stability, trust, identity, surfaces, operator) -> dict
        Combines five descriptive dimension dicts into a single
        readiness_score (0..100), band (green / yellow / red),
        per-dimension breakdown, and notes[] flagging any degraded
        dimension.

    summarize_launch_readiness(records) -> dict
        Loads each sibling module's public function, composes the five
        dimension dicts, and calls compute_readiness. Adds last_run.

Contract per tests/acceptance/launch_readiness.md:
    - read-only;
    - never raises (returns neutral readiness=0 on failure);
    - never persists;
    - no enforcement, no automation, no scheduling, no prediction.

A degraded sibling module simply produces a neutral 0.0 sub-score for
its dimension. The overall readiness gracefully reflects what is and
isn't observable.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# Band thresholds per spec §3.
_BAND_GREEN = 80
_BAND_YELLOW = 50

# Posture → 0..1 mapping for the operator dimension. Mirrors operator_mode
# severity ordering (lower index = better).
_POSTURE_SCORE = {
    "steady":     1.0,
    "cautious":   0.7,
    "corrective": 0.4,
    "degraded":   0.2,
    "offline":    0.0,
}

# Equal weights across five dimensions (spec §2 lists six but combines
# stability + run-quality-trend into the stability dimension; see
# summarize_launch_readiness for the merge).
_WEIGHTS = {
    "stability": 0.20,
    "trust":     0.20,
    "identity":  0.20,
    "surfaces":  0.20,
    "operator":  0.20,
}


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


def _clip01(x: Any) -> float:
    if not isinstance(x, (int, float)):
        return 0.0
    f = float(x)
    if f != f:  # NaN
        return 0.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def _extract_stability_score(stability: Any) -> float:
    if not isinstance(stability, dict) or not stability:
        return 0.0
    # Prefer a merged quality_score from run_quality.score_series, since
    # it already aggregates the timing / monotonicity / surface health
    # signals stability_math also reports.
    qseries = stability.get("quality_series")
    if isinstance(qseries, dict):
        avg = qseries.get("score_avg")
        if isinstance(avg, (int, float)):
            return _clip01(float(avg) / 100.0)
        # Fallback: latest record score
        last = qseries.get("latest_score")
        if isinstance(last, (int, float)):
            return _clip01(float(last) / 100.0)
    # Fallback: stability curve summary
    curve = stability.get("curve")
    if isinstance(curve, dict):
        n_runs = curve.get("n_runs_with_stability") or 0
        summary = curve.get("summary") if isinstance(curve.get("summary"), dict) else {}
        if isinstance(n_runs, (int, float)) and n_runs >= 3 and summary:
            mono = summary.get("monotonicity_pass_rate")
            if isinstance(mono, (int, float)):
                return _clip01(float(mono))
            return 0.6
        if isinstance(n_runs, (int, float)) and n_runs > 0:
            return 0.4
    return 0.0


def _extract_trust_score(trust: Any) -> float:
    if not isinstance(trust, dict) or not trust:
        return 0.0
    signal = trust.get("signal") if isinstance(trust.get("signal"), dict) else trust
    score = signal.get("signal_score") if isinstance(signal, dict) else None
    if isinstance(score, (int, float)):
        return _clip01(float(score) / 100.0)
    level = signal.get("level") if isinstance(signal, dict) else None
    if level == "stable":
        return 0.9
    if level == "degrading":
        return 0.55
    if level == "critical":
        return 0.15
    return 0.0


def _extract_identity_score(identity: Any) -> float:
    if not isinstance(identity, dict) or not identity:
        return 0.0
    for k in ("identity_coherence", "coherence", "global_coherence"):
        v = identity.get(k)
        if isinstance(v, (int, float)):
            return _clip01(float(v))
    profile = identity.get("profile") if isinstance(identity.get("profile"), dict) else None
    if isinstance(profile, dict):
        for k in ("identity_coherence", "coherence"):
            v = profile.get(k)
            if isinstance(v, (int, float)):
                return _clip01(float(v))
    return 0.0


def _extract_surfaces_score(surfaces: Any) -> float:
    if not isinstance(surfaces, dict) or not surfaces:
        return 0.0
    score = surfaces.get("coherence_score")
    if isinstance(score, (int, float)):
        return _clip01(float(score) / 100.0)
    return 0.0


def _extract_operator_score(operator: Any) -> float:
    if not isinstance(operator, dict) or not operator:
        return 0.0
    posture = operator.get("posture")
    if isinstance(posture, str) and posture in _POSTURE_SCORE:
        return _POSTURE_SCORE[posture]
    return 0.0


def compute_readiness(stability, trust, identity, surfaces, operator) -> dict:
    """Combine five dimension dicts into a single readiness payload."""
    try:
        stab = _extract_stability_score(stability)
        tru  = _extract_trust_score(trust)
        ide  = _extract_identity_score(identity)
        sur  = _extract_surfaces_score(surfaces)
        ope  = _extract_operator_score(operator)
        score_0_1 = (
            _WEIGHTS["stability"] * stab
            + _WEIGHTS["trust"]    * tru
            + _WEIGHTS["identity"] * ide
            + _WEIGHTS["surfaces"] * sur
            + _WEIGHTS["operator"] * ope
        )
        readiness_score = int(round(max(0.0, min(1.0, score_0_1)) * 100))
        if readiness_score >= _BAND_GREEN:
            band = "green"
        elif readiness_score >= _BAND_YELLOW:
            band = "yellow"
        else:
            band = "red"
        notes: list[str] = []
        for label, sub in (
            ("stability", stab), ("trust", tru), ("identity", ide),
            ("surfaces",  sur),  ("operator", ope),
        ):
            if sub <= 0.0:
                notes.append(f"{label}: no observable signal")
            elif sub < 0.5:
                notes.append(f"{label}: degraded ({sub:.2f})")
        if isinstance(operator, dict):
            posture = operator.get("posture")
            if isinstance(posture, str) and posture in {"degraded", "offline"}:
                notes.append(f"operator posture is {posture}")
        return {
            "readiness_score": readiness_score,
            "band":            band,
            "dimensions": {
                "stability": round(stab, 3),
                "trust":     round(tru, 3),
                "identity":  round(ide, 3),
                "surfaces":  round(sur, 3),
                "operator":  round(ope, 3),
            },
            "weights": dict(_WEIGHTS),
            "notes":   notes,
        }
    except Exception:
        return {
            "readiness_score": 0,
            "band":            "red",
            "dimensions": {
                "stability": 0.0, "trust": 0.0, "identity": 0.0,
                "surfaces":  0.0, "operator": 0.0,
            },
            "weights": dict(_WEIGHTS),
            "notes":   ["compute_readiness raised; returned neutral"],
        }


def _last_record(records: list) -> dict | None:
    if not isinstance(records, list):
        return None
    best = None
    best_dt = None
    for r in records:
        if not isinstance(r, dict):
            continue
        ts = r.get("timestamp") or r.get("ts") or r.get("ingested_at")
        dt = _safe_iso_to_dt(ts)
        if dt is None:
            continue
        if best_dt is None or dt > best_dt:
            best_dt = dt
            best = r
    return best


def summarize_launch_readiness(records) -> dict:
    """Compose readiness from sibling modules' public outputs.

    Each sibling module is loaded under try/except — a failure (e.g.,
    missing module, malformed records) yields an empty dict for that
    dimension, which produces a neutral 0.0 sub-score downstream.

    The "stability" dimension merges stability_math output with
    run_quality.score_series so the spec's "run quality trend" is
    folded into the same dimension consumed by compute_readiness.
    """
    try:
        if not isinstance(records, list):
            records = []
        last = _last_record(records)
        last_run = (
            last.get("timestamp") or last.get("ts") or last.get("ingested_at")
        ) if isinstance(last, dict) else None

        stability_summary: dict = {}
        try:
            import stability_math
            stability_summary["curve"] = stability_math.compute_stability_curve(records)
        except Exception:
            pass
        try:
            import run_quality
            if hasattr(run_quality, "score_series"):
                stability_summary["quality_series"] = run_quality.score_series(records)
        except Exception:
            pass

        trust_summary: dict = {}
        try:
            import trust_center_math
            trust_summary["signal"] = trust_center_math.compute_trust_signal(records)
        except Exception:
            pass

        identity_summary: dict = {}
        try:
            import identity_engine
            if hasattr(identity_engine, "compute_identity_profile"):
                identity_summary["profile"] = identity_engine.compute_identity_profile(records)
                p = identity_summary["profile"]
                if isinstance(p, dict):
                    for k in ("identity_coherence", "coherence", "global_coherence"):
                        if k in p:
                            identity_summary[k] = p[k]
                            break
        except Exception:
            pass

        surfaces_summary: dict = {}
        try:
            import surfaces_unification
            surfaces_summary = surfaces_unification.compute_surface_coherence(records)
        except Exception:
            surfaces_summary = {}

        operator_summary: dict = {}
        try:
            import operator_mode
            operator_summary = operator_mode.summarize_operator_state(records)
        except Exception:
            operator_summary = {}

        readiness = compute_readiness(
            stability_summary, trust_summary, identity_summary,
            surfaces_summary, operator_summary,
        )
        return {
            "readiness": readiness,
            "last_run":  last_run,
        }
    except Exception:
        return {
            "readiness": compute_readiness({}, {}, {}, {}, {}),
            "last_run":  None,
        }
