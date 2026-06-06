"""
monitoring_alerts.py — Phase 5 launch-sprint alert aggregators.

Pure, read-side, deterministic alert computation. Mirrors founder_analytics:
the repo has NO outbound delivery (no SMTP / Slack / push), and the
established pattern is compute -> surface in the founder console. So alerts are
computed here and rendered via GET /founder/alerts.

Content-safe by construction: counts, severities, types, and levels ONLY —
never anomaly ``message`` text, reply content, or account identifiers (matching
founder_analytics' counts-only ethos; founders drill into specifics via the
dedicated per-operator founder endpoints).

Public API:
    stripe_webhook_failure_alerts(now_ts=None, window_hours=24) -> dict  # module 18
    kernel_anomaly_alerts(now_ts=None, window_hours=24) -> dict   # module 19
    membership_churn_alerts(now_ts=None, window_days=7) -> dict   # module 20
    get_alerts_summary(now_ts=None) -> dict
    ALERTS_VERSION

Module 18 reads billing_config's webhook-failure ring buffer (populated by the
/billing/webhook handler on missing/bad signature). Content-free: reason codes
+ counts only — no secrets or payloads, consistent with the triage logging.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import billing_config
import users_store
from el_ins import anomaly_store

logger = logging.getLogger("clarityos.monitoring_alerts")

ALERTS_VERSION = "monitoring_alerts.v1.1"

_HOUR_S = 3600.0
_DAY_S = 86400.0
_HIGH_SEVERITY = 4          # anomaly severity (1..5) at/above which it's "high"
_RED_COUNT = 10            # total count at/above which level escalates to red


def _level(total: int, high: int) -> str:
    """Deterministic, content-free alert level."""
    if high > 0 or total >= _RED_COUNT:
        return "red"
    if total > 0:
        return "amber"
    return "green"


def kernel_anomaly_alerts(
    now_ts: Optional[float] = None, window_hours: float = 24,
) -> dict:
    """Aggregate stored EL/INS anomalies across operators in the window.
    Counts/severities/types only — never the anomaly message text."""
    now = float(now_ts if now_ts is not None else time.time())
    cutoff = now - float(window_hours) * _HOUR_S

    total = 0
    high = 0
    operators_affected = 0
    by_severity: dict[int, int] = {s: 0 for s in range(1, 6)}
    by_type: dict[str, int] = {}

    for op in users_store.list_all_usernames() or []:
        try:
            anoms = anomaly_store.list_anomalies_since(op, cutoff) or []
        except Exception:  # pragma: no cover (defensive)
            anoms = []
        if not anoms:
            continue
        operators_affected += 1
        for a in anoms:
            total += 1
            sev = int(a.get("severity") or 0)
            if 1 <= sev <= 5:
                by_severity[sev] += 1
            if sev >= _HIGH_SEVERITY:
                high += 1
            t = str(a.get("type") or "unknown")
            by_type[t] = by_type.get(t, 0) + 1

    return {
        "level": _level(total, high),
        "window_hours": float(window_hours),
        "total": total,
        "high_severity": high,
        "operators_affected": operators_affected,
        "by_severity": {str(k): v for k, v in by_severity.items()},
        "by_type": by_type,
    }


def membership_churn_alerts(
    now_ts: Optional[float] = None, window_days: float = 7,
) -> dict:
    """Aggregate billing-state churn signals. Counts only."""
    now = float(now_ts if now_ts is not None else time.time())
    grace_window_end = now + float(window_days) * _DAY_S

    cancelled = failed = past_due = grace_period = grace_expiring_soon = 0

    for op in users_store.list_all_usernames() or []:
        try:
            doc = users_store.get_user(op) or {}
        except Exception:  # pragma: no cover (defensive)
            doc = {}
        bs = doc.get("billing_state")
        ms = doc.get("membership_status")
        if bs == "cancelled" or ms == "cancelled":
            cancelled += 1
        elif bs == "failed":
            failed += 1
        elif bs == "past_due":
            past_due += 1
        elif bs == "grace_period":
            grace_period += 1
            gu = doc.get("renewal_grace_until_ts")
            if isinstance(gu, (int, float)) and now <= float(gu) <= grace_window_end:
                grace_expiring_soon += 1

    at_risk = cancelled + failed + past_due + grace_period
    hard_churn = cancelled + failed
    return {
        "level": _level(at_risk, hard_churn),
        "window_days": float(window_days),
        "cancelled": cancelled,
        "failed": failed,
        "past_due": past_due,
        "grace_period": grace_period,
        "grace_expiring_soon": grace_expiring_soon,
        "at_risk_total": at_risk,
    }


def stripe_webhook_failure_alerts(
    now_ts: Optional[float] = None, window_hours: float = 24,
) -> dict:
    """Aggregate Stripe webhook rejections in the window (module 18). Reads the
    content-free failure ring buffer in billing_config — counts + reason codes
    only, never secrets/payloads. Any signature failure means payments aren't
    being processed, so a small sustained count escalates to red."""
    now = float(now_ts if now_ts is not None else time.time())
    stats = billing_config.webhook_failure_stats(
        window_s=float(window_hours) * _HOUR_S, now_ts=now,
    )
    total = int(stats.get("total") or 0)
    high = total if total >= 5 else 0   # red at sustained failures, amber on any
    return {
        "level": _level(total, high),
        "window_hours": float(window_hours),
        "total": total,
        "by_reason": dict(stats.get("by_reason") or {}),
        "last_ts": stats.get("last_ts"),
    }


def get_alerts_summary(now_ts: Optional[float] = None) -> dict:
    """Combined founder-console alert payload (modules 18 + 19 + 20)."""
    now = float(now_ts if now_ts is not None else time.time())
    anomalies = kernel_anomaly_alerts(now)
    churn = membership_churn_alerts(now)
    webhook = stripe_webhook_failure_alerts(now)
    levels = (anomalies["level"], churn["level"], webhook["level"])
    overall = "red" if "red" in levels else ("amber" if "amber" in levels else "green")
    return {
        "overall_level": overall,
        "kernel_anomalies": anomalies,
        "membership_churn": churn,
        "stripe_webhook_failures": webhook,
        "ts": now,
        "version": ALERTS_VERSION,
    }
