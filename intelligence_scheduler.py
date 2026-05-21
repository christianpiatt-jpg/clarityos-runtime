"""
intelligence_scheduler.py — real cadence orchestrator (Phase 2 Unit 4).

The "movement-through-time" engine for ClarityOS. Coordinates the
three intelligence producers built in Units 1–3:

    * personal_news_basin   — 2×/day (default 09:00 + 21:00 UTC)
    * email_ep_dash         — on-demand by default; optional 13:00 UTC
                              scheduled mode (env-var gated)
    * daily_personal_elins  — 1×/day per UTC day

This module emits no intelligence itself. It loads a tiny JSON state
file, evaluates per-user cadence triggers against the current time,
invokes the underlying producers, collects their envelopes, and
persists the new state. The entire surface is deterministic — same
``now`` + same starting state → same envelopes + same final state.

Architecture:
    * Stateless module-level functions. No threads, no daemons, no
      background loops. The cron / K8s job calls ``tick()`` on a
      timer (every minute is a reasonable default). Idempotent: an
      extra tick within a cadence window is a no-op.
    * State file at $CLARITYOS_SCHEDULER_STATE (default
      ``.clarityos_scheduler_state.json``). Atomic writes via
      tempfile + os.replace.
    * News-time list at $CLARITYOS_NEWS_TIMES (default "09:00,21:00").
    * Email scheduled mode gated by $CLARITYOS_EMAIL_EP_SCHEDULED.
    * Underlying-module failures are caught and logged; state still
      advances so we don't burn cycles retrying every tick.

Public API:
    register_user(user_id)                   -> dict
    unregister_user(user_id)                 -> bool
    get_state()                              -> dict
    run_daily_personal_elins_once(uid, date) -> dict | None
    run_news_basin_once(uid)                 -> dict | None
    run_email_ep_dash_once(raw, uid)         -> dict | None
    run_scheduled_tasks(now=None)            -> list[dict]
    tick(now=None)                           -> list[dict]

Production entrypoint:
    python -m intelligence_scheduler        # one tick, prints envelopes
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("clarityos.intelligence_scheduler")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_STATE_PATH:        str  = ".clarityos_scheduler_state.json"
DEFAULT_NEWS_TIMES:        str  = "09:00,21:00"
EMAIL_SCHEDULED_TIME:      time = time(13, 0)
_TRUTHY: tuple = ("1", "true", "True", "yes", "YES", "on", "ON")


# ---------------------------------------------------------------------------
# Env / path resolution
# ---------------------------------------------------------------------------
def _resolve_state_path() -> Path:
    """Resolve the scheduler-state JSON path. Env-var overridable."""
    override = (os.environ.get("CLARITYOS_SCHEDULER_STATE") or "").strip()
    return Path(override) if override else Path(DEFAULT_STATE_PATH)


def _get_news_times() -> list[time]:
    """Parse ``CLARITYOS_NEWS_TIMES`` (HH:MM,HH:MM,...) → sorted unique times.

    Invalid entries are skipped with a warning. If every entry is
    invalid, falls back to the spec defaults [09:00, 21:00] UTC.
    """
    raw = (os.environ.get("CLARITYOS_NEWS_TIMES") or DEFAULT_NEWS_TIMES).strip()
    if not raw:
        raw = DEFAULT_NEWS_TIMES
    out: set[time] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            h_s, _, m_s = part.partition(":")
            h, m = int(h_s), int(m_s)
            out.add(time(h, m))
        except (ValueError, AttributeError):
            logger.warning(
                "intelligence_scheduler: skipping invalid news time: %r", part,
            )
    if not out:
        return [time(9, 0), time(21, 0)]
    return sorted(out)


def _email_scheduled_enabled() -> bool:
    """True iff CLARITYOS_EMAIL_EP_SCHEDULED is set to a truthy value."""
    val = (os.environ.get("CLARITYOS_EMAIL_EP_SCHEDULED") or "").strip()
    return val in _TRUTHY


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------
def _load_state() -> dict:
    """Load the scheduler state file. Returns empty state on missing
    file. Returns empty state on whole-file corruption. Drops invalid
    per-user entries silently (reset that user only)."""
    path = _resolve_state_path()
    if not path.exists():
        return {"users": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.warning("intelligence_scheduler: state load failed: %s", e)
        return {"users": {}}
    if not isinstance(data, dict):
        return {"users": {}}
    users = data.get("users")
    if not isinstance(users, dict):
        data = {"users": {}}
        return data
    # Reset any non-dict / non-str-keyed user entries.
    cleaned: dict = {}
    for uid, ustate in users.items():
        if isinstance(uid, str) and uid and isinstance(ustate, dict):
            cleaned[uid] = ustate
    data["users"] = cleaned
    return data


def _save_state(state: dict) -> None:
    """Atomic write: temp file in same dir → os.replace."""
    path = _resolve_state_path()
    parent = path.parent if str(path.parent) else Path(".")
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=".scheduler_", suffix=".tmp", dir=str(parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, default=str)
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _get_user_state(state: dict, user_id: str) -> dict:
    """Return the per-user sub-dict, creating an empty one if needed."""
    users = state.setdefault("users", {})
    if user_id not in users or not isinstance(users.get(user_id), dict):
        users[user_id] = {}
    return users[user_id]


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def _normalize_now(now: Optional[datetime]) -> datetime:
    """Coerce ``now`` to a tz-aware UTC datetime."""
    if now is None:
        return datetime.now(timezone.utc)
    if not isinstance(now, datetime):
        raise TypeError("now must be a datetime or None")
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _parse_iso(s: Any) -> Optional[datetime]:
    """Best-effort ISO 8601 → UTC datetime, or None."""
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _next_news_time(now: datetime, news_times: list[time]) -> datetime:
    """Compute the next news run time >= now (UTC)."""
    today = now.date()
    for t in news_times:
        candidate = datetime.combine(today, t, tzinfo=timezone.utc)
        if candidate >= now:
            return candidate
    tomorrow = today + timedelta(days=1)
    return datetime.combine(tomorrow, news_times[0], tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Trigger evaluation
# ---------------------------------------------------------------------------
def _should_run_daily(user_state: dict, today: date_cls) -> bool:
    """True if the daily-ELINS hasn't yet run for ``today`` UTC."""
    last = user_state.get("last_daily_elins")
    if not isinstance(last, str):
        return True
    try:
        last_date = date_cls.fromisoformat(last)
    except ValueError:
        return True
    return last_date < today


def _should_run_news_basin(
    user_state: dict,
    now: datetime,
    news_times: list[time],
) -> bool:
    """True if any of today's scheduled news times has elapsed since the
    last news run.

    Algorithm: for each scheduled time T today (sorted ascending) that
    has elapsed (T ≤ now), if last_run is None OR last_run < T, fire.
    This prevents firing twice for the same scheduled-T (because once
    the run completes, last_run = now ≥ T).
    """
    last_run = _parse_iso(user_state.get("last_news_basin"))
    today = now.date()
    for t in news_times:
        scheduled = datetime.combine(today, t, tzinfo=timezone.utc)
        if scheduled > now:
            continue  # Not yet
        if last_run is None or last_run < scheduled:
            return True
    return False


def _should_run_email_scheduled(user_state: dict, now: datetime) -> bool:
    """True iff scheduled mode is enabled AND 13:00 UTC has elapsed today
    AND we haven't already recorded a tick for today's 13:00."""
    if not _email_scheduled_enabled():
        return False
    scheduled = datetime.combine(now.date(), EMAIL_SCHEDULED_TIME, tzinfo=timezone.utc)
    if now < scheduled:
        return False
    last_tick = _parse_iso(user_state.get("last_email_scheduled_tick"))
    return last_tick is None or last_tick < scheduled


# ---------------------------------------------------------------------------
# Single-task runners (public)
# ---------------------------------------------------------------------------
def run_daily_personal_elins_once(
    user_id: str,
    date: Optional[date_cls] = None,
) -> Optional[dict]:
    """Run the daily ELINS composer for one user. Returns the envelope or
    None on failure / empty day. Failures are logged but do not raise."""
    try:
        import daily_personal_elins
        env = daily_personal_elins.run_daily_personal_elins(user_id, date)
        return env
    except Exception as e:
        logger.warning(
            "intelligence_scheduler: daily ELINS failed for %s: %s",
            user_id, e,
        )
        return None


def run_news_basin_once(user_id: str) -> Optional[dict]:
    """Run the news-basin collector for one user. Returns the envelope or
    None on failure. Failures are logged but do not raise."""
    try:
        import personal_news_basin
        return personal_news_basin.run_news_basin(user_id)
    except Exception as e:
        logger.warning(
            "intelligence_scheduler: news basin failed for %s: %s",
            user_id, e,
        )
        return None


def run_email_ep_dash_once(raw: str, user_id: str) -> Optional[dict]:
    """Run email EP dash on one raw blob. Returns the envelope or None
    on failure. On-demand — does NOT modify scheduler state.

    Note: scheduled mode (CLARITYOS_EMAIL_EP_SCHEDULED=1) only records a
    cadence marker in ``tick()`` — it does NOT auto-fetch raw blobs.
    Auto-fetch infrastructure is a future surface concern.
    """
    try:
        import email_ep_dash
        return email_ep_dash.run_email_ep_dash(raw, user_id)
    except Exception as e:
        logger.warning(
            "intelligence_scheduler: email dash failed for %s: %s",
            user_id, e,
        )
        return None


# ---------------------------------------------------------------------------
# User registration
# ---------------------------------------------------------------------------
def register_user(user_id: str) -> dict:
    """Register a user with the scheduler. Idempotent. Returns the user's
    current state dict (empty on first registration)."""
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("user_id must be a non-empty string")
    state = _load_state()
    _get_user_state(state, user_id)
    _save_state(state)
    return state["users"][user_id]


def unregister_user(user_id: str) -> bool:
    """Drop a user from scheduler tracking. Returns True if removed."""
    if not isinstance(user_id, str) or not user_id:
        return False
    state = _load_state()
    users = state.get("users") or {}
    if user_id not in users:
        return False
    del users[user_id]
    _save_state(state)
    return True


def get_state() -> dict:
    """Return a fresh snapshot of the scheduler state."""
    return _load_state()


def _list_known_users(state: dict) -> list[str]:
    """Return the registered user-ids, sorted for determinism."""
    users = state.get("users") or {}
    return sorted(uid for uid in users.keys() if isinstance(uid, str) and uid)


# ---------------------------------------------------------------------------
# Tick
# ---------------------------------------------------------------------------
def tick(now: Optional[datetime] = None) -> list[dict]:
    """Evaluate all per-user cadences against ``now`` and run triggered
    tasks. Returns the list of envelopes produced (in execution order).

    Execution order within each user: **news basin → email dash → daily
    ELINS** (per spec § 5). User iteration is sorted alphabetically by
    user_id for deterministic ordering across multi-user runs.

    State is updated regardless of envelope production (envelope=None
    still counts as "we tried at time T") so a persistently failing
    underlying module doesn't burn cycles retrying every minute.
    """
    now = _normalize_now(now)
    today = now.date()
    news_times = _get_news_times()
    email_scheduled = _email_scheduled_enabled()

    state = _load_state()
    users = _list_known_users(state)

    produced: list[dict] = []

    for user_id in users:
        user_state = _get_user_state(state, user_id)

        # 1. News basin
        if _should_run_news_basin(user_state, now, news_times):
            env = run_news_basin_once(user_id)
            if env is not None:
                produced.append(env)
            user_state["last_news_basin"] = now.isoformat()

        # 2. Email dash — scheduled mode only fires a cadence marker;
        # the actual processing requires an external raw blob, which
        # this surface does not synthesize.
        if email_scheduled and _should_run_email_scheduled(user_state, now):
            user_state["last_email_scheduled_tick"] = now.isoformat()
            # No envelope produced — see docstring of
            # run_email_ep_dash_once.

        # 3. Daily ELINS
        if _should_run_daily(user_state, today):
            env = run_daily_personal_elins_once(user_id, today)
            if env is not None:
                produced.append(env)
            user_state["last_daily_elins"] = today.isoformat()

        # 4. Update next-news pointer for visibility / dashboards.
        user_state["next_news_basin"] = _next_news_time(
            now + timedelta(seconds=1), news_times,
        ).isoformat()

    _save_state(state)
    return produced


def run_scheduled_tasks(now: Optional[datetime] = None) -> list[dict]:
    """Alias for ``tick(now)``. Matches the spec's API parity (§ 1)."""
    return tick(now)


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover (manual CLI smoke)
    envelopes = tick()
    for env in envelopes:
        print(json.dumps(env, indent=2, default=str))
