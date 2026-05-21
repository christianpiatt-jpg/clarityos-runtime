"""
runtime_intelligence_wiring.py — Runtime Intelligence Wiring Layer (Phase 3 Unit 1).

Single read-only interface that the PHONE, WEB, and CLOUD surfaces call
to consume the four Phase-2 intelligence producers as one cohesive
runtime snapshot per user per UTC day.

Connects to:
    * ELINS.ingestion_bus.list_packets — preferred source for all three
      packet types (news_basin / email_ep_dash / daily_personal_elins).
    * Library archives — fallback for daily ELINS only
      (<CLARITYOS_DAILY_ELINS_DIR>/<user_id>/<YYYY-MM-DD>.json).
    * operator_state.get_operator_state — source for micro signals
      (elins_history + g_history, filtered to today's UTC window).

DESIGN COMMITMENTS:
    * Read-only. No mutation of bus, archives, or operator_state.
    * Pure stdlib. No LLM calls. No network calls.
    * Deterministic. Same input state → identical snapshot (deep equality).
    * Sorted. All list outputs are ascending by timestamp.
    * Normalized. All packet timestamps emitted as ISO 8601 UTC strings.
    * Graceful. Every failure path returns an empty list / None /
      empty-dict — never raises out of the public API.

PUBLIC API (per Phase 3 Unit 1 spec):
    get_today_elins(user_id)               -> dict | None
    get_latest_news(user_id)               -> list[dict]
    get_latest_email_signals(user_id)      -> list[dict]
    get_latest_micro_signals(user_id)      -> list[dict]
    get_intelligence_snapshot(user_id)     -> dict
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("clarityos.runtime_intelligence_wiring")

# ---------------------------------------------------------------------------
# Env vars + defaults — match the producer modules exactly
# ---------------------------------------------------------------------------

_NEWS_BASIN_DIR_ENV:  str = "CLARITYOS_NEWS_BASIN_DIR"
_EMAIL_DASH_DIR_ENV:  str = "CLARITYOS_EMAIL_EP_DASH_DIR"
_DAILY_ELINS_DIR_ENV: str = "CLARITYOS_DAILY_ELINS_DIR"

_DEFAULT_NEWS_BASIN_DIR:  str = "ClarityOS_Library/news_basin"
_DEFAULT_EMAIL_DASH_DIR:  str = "ClarityOS_Library/email_ep_dash"
_DEFAULT_DAILY_ELINS_DIR: str = "ClarityOS_Library/daily_elins"

# Bus FIFO drops at 1000; ask for everything and post-filter.
_BUS_POLL_LIMIT: int = 1000

# Snapshot schema — exact, no missing keys, no None lists.
_SNAPSHOT_KEYS: tuple = (
    "date", "daily_elins", "news", "email", "micro", "macro",
)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------
def _today_utc() -> date_cls:
    """Today's UTC date. Patch this in tests to fix the date window."""
    return datetime.now(timezone.utc).date()


def _utc_window(d: date_cls) -> tuple[datetime, datetime]:
    """[start, end) UTC datetimes for ``d``."""
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    return start, start + timedelta(days=1)


def _parse_iso(s: Any) -> Optional[datetime]:
    """Best-effort ISO 8601 → UTC datetime. None on failure."""
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Path + bus access
# ---------------------------------------------------------------------------
def _resolve_dir(env_var: str, default: str) -> Path:
    override = (os.environ.get(env_var) or "").strip()
    return Path(override) if override else Path(default)


def _safe_list_packets(type_filter: str) -> list[dict]:
    """Pull packets from the bus. Returns [] on any failure (import,
    bus-method exception, non-list result)."""
    try:
        from ELINS import ingestion_bus
    except ImportError as e:
        logger.warning(
            "runtime_intelligence_wiring: ingestion_bus unavailable: %s", e,
        )
        return []
    try:
        packets = ingestion_bus.list_packets(
            type_filter=type_filter, limit=_BUS_POLL_LIMIT,
        )
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning(
            "runtime_intelligence_wiring: bus poll failed for %s: %s",
            type_filter, e,
        )
        return []
    if not isinstance(packets, list):
        return []
    return [p for p in packets if isinstance(p, dict)]


def _collect_packets_for_user_today(
    type_filter: str,
    user_id: str,
    today: Optional[date_cls] = None,
) -> list[dict]:
    """Filter bus packets to (user_id, today's UTC window), normalize
    each packet's ``generated_at`` to ISO UTC, and return sorted
    ascending by that field.

    Each returned dict is a shallow copy of the bus packet with
    ``generated_at`` rewritten to the canonical ISO UTC form. All other
    fields (including bus-injected ``_packet_id`` + ``_received_at``)
    are preserved.
    """
    if today is None:
        today = _today_utc()
    start, end = _utc_window(today)

    out: list[dict] = []
    for p in _safe_list_packets(type_filter):
        if p.get("user") != user_id:
            continue
        gen_at = _parse_iso(p.get("generated_at"))
        if gen_at is None:
            continue
        if not (start <= gen_at < end):
            continue
        normalized = dict(p)
        normalized["generated_at"] = gen_at.isoformat()
        out.append(normalized)

    out.sort(key=lambda p: p.get("generated_at") or "")
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def get_today_elins(user_id: str) -> Optional[dict]:
    """Return today's daily ELINS envelope for ``user_id``, or None.

    Resolution order:
        1. Bus: latest daily_personal_elins packet within today's UTC
           window (preferred; lowest latency).
        2. Library archive: ``<CLARITYOS_DAILY_ELINS_DIR>/<user_id>/
           <YYYY-MM-DD>.json`` (fallback; survives bus restarts).
        3. None.

    Never raises. Returns None on any failure (missing file, corrupt
    JSON, unreadable, etc.).
    """
    today = _today_utc()

    bus_pkts = _collect_packets_for_user_today(
        "daily_personal_elins", user_id, today,
    )
    if bus_pkts:
        # Latest wins (sort is ascending; last entry is most recent).
        return bus_pkts[-1]

    archive_dir = _resolve_dir(
        _DAILY_ELINS_DIR_ENV, _DEFAULT_DAILY_ELINS_DIR,
    ) / user_id
    archive_path = archive_dir / f"{today.isoformat()}.json"
    if not archive_path.exists():
        return None
    try:
        text = archive_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.warning(
            "runtime_intelligence_wiring: archive read failed (%s): %s",
            archive_path, e,
        )
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(
            "runtime_intelligence_wiring: archive parse failed (%s): %s",
            archive_path, e,
        )
        return None
    return data if isinstance(data, dict) else None


def get_latest_news(user_id: str) -> list[dict]:
    """All ``news_basin`` packets for ``user_id`` within today's UTC
    window, sorted ascending by ``generated_at`` (normalized to ISO UTC).
    """
    return _collect_packets_for_user_today("news_basin", user_id)


def get_latest_email_signals(user_id: str) -> list[dict]:
    """All ``email_ep_dash`` packets for ``user_id`` within today's UTC
    window, sorted ascending by ``generated_at`` (normalized to ISO UTC).
    """
    return _collect_packets_for_user_today("email_ep_dash", user_id)


def get_latest_micro_signals(user_id: str) -> list[dict]:
    """Micro signals for ``user_id`` within today's UTC window.

    Extracts ``elins_history`` + ``g_history`` from
    ``operator_state.get_operator_state(user_id)``, filters by ts to the
    [start_of_day, end_of_day) UTC window, tags each entry with ``kind``
    and ``ts_iso``, sorts ascending by ``ts``.

    Each returned dict:
        * carries all original fields from the history entry
        * adds ``kind``    — "elins" or "g_run" (always wins over any
                             pre-existing key)
        * adds ``ts_iso``  — ts normalised to ISO 8601 UTC

    Never raises. Returns [] on any failure (import / read / shape).
    """
    try:
        import operator_state
    except ImportError as e:
        logger.warning(
            "runtime_intelligence_wiring: operator_state unavailable: %s", e,
        )
        return []
    try:
        state = operator_state.get_operator_state(user_id)
    except Exception as e:
        logger.warning(
            "runtime_intelligence_wiring: operator_state read failed: %s", e,
        )
        return []
    if not isinstance(state, dict):
        return []

    today = _today_utc()
    start, end = _utc_window(today)
    start_ts, end_ts = start.timestamp(), end.timestamp()

    out: list[dict] = []
    for kind_label, key in (("elins", "elins_history"), ("g_run", "g_history")):
        entries = state.get(key) or []
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            ts = entry.get("ts")
            if not isinstance(ts, (int, float)):
                continue
            if not (start_ts <= ts < end_ts):
                continue
            row = {**entry, "kind": kind_label}
            row["ts_iso"] = datetime.fromtimestamp(
                ts, tz=timezone.utc,
            ).isoformat()
            out.append(row)

    out.sort(key=lambda r: r.get("ts") or 0)
    return out


def get_intelligence_snapshot(user_id: str) -> dict:
    """Single read-only aggregate that the PHONE / WEB / CLOUD surfaces
    consume as one runtime view.

    Schema (always exactly these 6 keys; no None lists; no missing fields):

        {
            "date":        "YYYY-MM-DD",   # today's UTC date
            "daily_elins": <envelope|None>,
            "news":        [<news packet>, ...],
            "email":       [<email packet>, ...],
            "micro":       [<micro event>, ...],
            "macro":       <macro section of daily_elins, or {}>,
        }

    ``macro`` is the daily_elins envelope's ``macro`` sub-dict when
    available, else an empty dict. Useful for surfaces that want the
    macro band without unwrapping the full daily envelope.
    """
    today = _today_utc()
    daily = get_today_elins(user_id)

    macro: dict = {}
    if isinstance(daily, dict):
        m = daily.get("macro")
        if isinstance(m, dict):
            macro = m

    return {
        "date":        today.isoformat(),
        "daily_elins": daily,
        "news":        get_latest_news(user_id),
        "email":       get_latest_email_signals(user_id),
        "micro":       get_latest_micro_signals(user_id),
        "macro":       macro,
    }
