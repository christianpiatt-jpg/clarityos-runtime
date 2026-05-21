"""
v43 — Founder analytics aggregator.

Pure read-side module that joins the existing stores into a single
metadata-only summary the founder console can render in one call.

Data sources:
    * users_store        — total user count, billing state, renewal_ts.
    * operator_state     — last_active_ts, ELINS / #G interaction history.
    * elins_project      — macro-run count + ESO mode per run.
    * billing_config     — current Stripe mode (test / live / disabled).

The summary is deterministic for a fixed snapshot of the underlying
stores and a fixed ``now_ts``. The function never mutates state.

Public API:
    get_founder_analytics_summary(now_ts=None) -> dict
    SUMMARY_VERSION
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import billing_config
import operator_state
import users_store
from ELINS import elins_project

logger = logging.getLogger("clarityos.founder_analytics")

SUMMARY_VERSION: str = "founder_analytics.v43.1"

_DAY_S: float = 86400.0
_WEEK_S: float = 7.0 * _DAY_S
_MONTH_S: float = 30.0 * _DAY_S


def get_founder_analytics_summary(now_ts: Optional[float] = None) -> dict:
    """Return the founder analytics summary dict.

    ``now_ts`` defaults to ``time.time()`` and bounds the rolling
    windows (active_7d / active_30d / runs_7d). Tests pin it to make
    counts deterministic.
    """
    now = float(now_ts if now_ts is not None else time.time())
    cutoff_7d = now - _WEEK_S
    cutoff_30d = now - _MONTH_S

    usernames = users_store.list_all_usernames() or []
    total_users = len(usernames)

    active_7d = 0
    active_30d = 0
    elins_runs_7d = 0
    g_runs_7d = 0
    active_subscriptions = 0
    past_due = 0
    canceled = 0

    for username in usernames:
        # ----- Activity counts -----
        try:
            state = operator_state.get_operator_state(username) or {}
        except Exception:  # pragma: no cover (defensive)
            state = {}
        last_active = float(state.get("last_active_ts") or 0.0)
        if last_active >= cutoff_7d:
            active_7d += 1
        if last_active >= cutoff_30d:
            active_30d += 1
        for entry in state.get("elins_history") or []:
            ts = entry.get("ts")
            if isinstance(ts, (int, float)) and float(ts) >= cutoff_7d:
                elins_runs_7d += 1
        for entry in state.get("g_history") or []:
            ts = entry.get("ts")
            if isinstance(ts, (int, float)) and float(ts) >= cutoff_7d:
                g_runs_7d += 1

        # ----- Billing counts -----
        try:
            user_doc = users_store.get_user(username) or {}
        except Exception:  # pragma: no cover (defensive)
            user_doc = {}
        bs = user_doc.get("billing_state")
        membership_status = user_doc.get("membership_status")
        if bs == "active":
            active_subscriptions += 1
        elif bs in ("past_due", "grace_period"):
            past_due += 1
        elif bs == "cancelled" or membership_status == "cancelled":
            canceled += 1

    # ----- Macro-run counts + ESO usage rate -----
    try:
        macro_runs = elins_project.list_macro_runs(limit=200) or []
    except Exception:  # pragma: no cover (defensive)
        macro_runs = []
    macro_in_window = [
        r for r in macro_runs
        if isinstance(r.get("ts"), (int, float)) and float(r["ts"]) >= cutoff_7d
    ]
    macro_runs_7d = len(macro_in_window)
    if macro_runs_7d > 0:
        eso_count = sum(
            1 for r in macro_in_window
            if r.get("external_signal_mode") == "cloud_perplexity"
        )
        eso_usage_rate = round(eso_count / macro_runs_7d, 4)
    else:
        eso_usage_rate = 0.0

    return {
        "users": {
            "total": total_users,
            "active_7d": active_7d,
            "active_30d": active_30d,
        },
        "billing": {
            "active_subscriptions": active_subscriptions,
            "past_due": past_due,
            "canceled": canceled,
            "mode": billing_config.get_stripe_mode(),
        },
        "intelligence": {
            "elins_runs_7d": elins_runs_7d,
            "g_runs_7d": g_runs_7d,
            "macro_runs_7d": macro_runs_7d,
            "eso_usage_rate_7d": eso_usage_rate,
        },
        "ts": now,
        "version": SUMMARY_VERSION,
    }
