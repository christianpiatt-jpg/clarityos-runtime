"""
operator_mode.py — Phase 11 descriptive operator-posture layer.

Pure stdlib. Two public functions:

    derive_operator_posture(telemetry, identity, quality) -> dict
        Returns {posture, reasons[]} where posture is one of:
        steady | cautious | corrective | degraded | offline.

    summarize_operator_state(records) -> dict
        Reads the most-recent acceptance records, derives the four
        descriptive signals (last_run, last_quality, last_trust,
        last_identity), and combines them via derive_operator_posture.

Contract per tests/acceptance/operator_mode.md:
    - read-only;
    - never raises (returns neutral 'offline' on failure);
    - never persists;
    - no enforcement, no automation, no state changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


# Severity ordering — higher = more degraded. Used to collapse three
# per-signal votes to one final posture (§ 3.4 of the spec).
_POSTURES = ("steady", "cautious", "corrective", "degraded", "offline")
_SEVERITY = {p: i for i, p in enumerate(_POSTURES)}


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


def _telemetry_vote(telemetry: Any) -> tuple[str, str]:
    if not isinstance(telemetry, dict) or not telemetry:
        return "offline", "no telemetry payload"
    trust = telemetry.get("trust_signal")
    drift = telemetry.get("drift")
    if isinstance(trust, dict):
        level = trust.get("level")
    else:
        level = trust if isinstance(trust, str) else None
    drifting = False
    if isinstance(drift, dict):
        drifting = bool(drift.get("drifting"))
    elif isinstance(drift, str):
        drifting = (drift.lower() == "drifting")
    if level == "stable" and not drifting:
        return "steady", "trust=stable, drift=stable"
    if level == "critical":
        if telemetry.get("known_recovery"):
            return "corrective", "trust=critical with known recovery"
        return "degraded", "trust=critical, no known recovery"
    if level == "degrading" or drifting:
        return "cautious", f"trust={level!s}, drift={'drifting' if drifting else 'stable'}"
    if level is None:
        return "offline", "telemetry payload present but trust signal missing"
    return "cautious", f"trust={level!s} (unrecognised band)"


def _identity_vote(identity: Any) -> tuple[str, str]:
    if not isinstance(identity, dict) or not identity:
        return "offline", "no identity payload"
    score = identity.get("identity_coherence")
    if score is None:
        score = identity.get("coherence")
    if not isinstance(score, (int, float)):
        return "offline", "identity payload present but coherence missing"
    s = float(score)
    if s >= 0.80:
        return "steady", f"identity_coherence={s:.2f} (>=0.80)"
    if s >= 0.60:
        return "cautious", f"identity_coherence={s:.2f} (0.60-0.80)"
    if s >= 0.40:
        return "corrective", f"identity_coherence={s:.2f} (0.40-0.60)"
    return "degraded", f"identity_coherence={s:.2f} (<0.40)"


def _quality_vote(quality: Any) -> tuple[str, str]:
    if not isinstance(quality, dict) or not quality:
        return "offline", "no quality payload"
    score = quality.get("quality_score")
    if score is None:
        score = quality.get("score")
    if not isinstance(score, (int, float)):
        return "offline", "quality payload present but score missing"
    monotonicity = bool(quality.get("monotonicity_pass"))
    n_recent = quality.get("n_recent_runs")
    s = float(score)
    if s >= 0.80 and monotonicity and isinstance(n_recent, (int, float)) and n_recent >= 3:
        return "steady", f"quality={s:.2f}, monotonicity_pass, n_recent={n_recent}"
    if s >= 0.60:
        return "cautious", f"quality={s:.2f}"
    if 0.40 <= s < 0.60:
        return "corrective", f"quality={s:.2f}"
    return "degraded", f"quality={s:.2f}"


def derive_operator_posture(telemetry, identity, quality) -> dict:
    """Combine three signal votes into a single posture.

    Returns:
        {
            "posture": <one of steady/cautious/corrective/degraded/offline>,
            "reasons": [<str>, ...],   # one per signal vote
            "votes":   {"telemetry": ..., "identity": ..., "quality": ...},
        }
    """
    try:
        t_vote, t_reason = _telemetry_vote(telemetry)
        i_vote, i_reason = _identity_vote(identity)
        q_vote, q_reason = _quality_vote(quality)
        votes = {"telemetry": t_vote, "identity": i_vote, "quality": q_vote}
        # § 3.4: collapse to the most-degraded vote.
        worst = max(votes.values(), key=lambda p: _SEVERITY.get(p, 99))
        return {
            "posture": worst,
            "reasons": [
                f"telemetry → {t_vote}: {t_reason}",
                f"identity → {i_vote}: {i_reason}",
                f"quality → {q_vote}: {q_reason}",
            ],
            "votes": votes,
        }
    except Exception:
        return {
            "posture": "offline",
            "reasons": ["derive failure (returned neutral)"],
            "votes": {"telemetry": "offline", "identity": "offline", "quality": "offline"},
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


def _stale_offline(records: list, hours: float = 24.0) -> bool:
    """Spec § 5.1 — stale signal decays to offline after a window."""
    last = _last_record(records)
    if last is None:
        return True
    ts = last.get("timestamp") or last.get("ts") or last.get("ingested_at")
    dt = _safe_iso_to_dt(ts)
    if dt is None:
        return True
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_h = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
    return age_h > hours


def summarize_operator_state(records) -> dict:
    """Read the most recent record set, derive descriptive signals,
    and produce the combined posture.

    Returns:
        {
            "last_run":         <iso str or None>,
            "last_quality":     {...} or None,
            "last_trust":       {...} or None,
            "last_identity":    {...} or None,
            "posture":          <label>,
            "reasons":          [...],
            "votes":            {...},
            "stale":            <bool>,
        }
    """
    try:
        if not isinstance(records, list):
            records = []
        last = _last_record(records)
        if last is None or _stale_offline(records):
            posture = derive_operator_posture(None, None, None)
            return {
                "last_run":      None if last is None else (
                    last.get("timestamp") or last.get("ts") or last.get("ingested_at")
                ),
                "last_quality":  None,
                "last_trust":    None,
                "last_identity": None,
                "stale":         True,
                **posture,
            }
        telemetry = {
            "trust_signal":  last.get("trust_signal"),
            "drift":         last.get("drift"),
            "known_recovery": last.get("known_recovery"),
        }
        identity = last.get("identity") if isinstance(last.get("identity"), dict) else {
            "identity_coherence": last.get("identity_coherence"),
        }
        quality = last.get("quality") if isinstance(last.get("quality"), dict) else {
            "quality_score":      last.get("quality_score"),
            "monotonicity_pass":  last.get("monotonicity_pass"),
            "n_recent_runs":      last.get("n_recent_runs"),
        }
        posture = derive_operator_posture(telemetry, identity, quality)
        return {
            "last_run":      last.get("timestamp") or last.get("ts") or last.get("ingested_at"),
            "last_quality":  quality,
            "last_trust":    telemetry,
            "last_identity": identity,
            "stale":         False,
            **posture,
        }
    except Exception:
        return {
            "last_run":      None,
            "last_quality":  None,
            "last_trust":    None,
            "last_identity": None,
            "stale":         True,
            "posture":       "offline",
            "reasons":       ["summarize failure (returned neutral)"],
            "votes":         {"telemetry": "offline", "identity": "offline", "quality": "offline"},
        }
