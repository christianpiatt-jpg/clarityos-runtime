"""
daily_personal_elins.py — DAILY PERSONAL ELINS composer (Phase 2 Unit 3).

Per-user, per-day intelligence envelope that fuses three signal streams
into a macro → meso → micro mix:

    * MACRO  — latest macro ELINS run for the date (from elins_project)
    * MESO   — news basin + email dash aggregates (from ingestion_bus)
    * MICRO  — operator_state history (elins + g_runs) for the date

The output is template/lexical — no LLM calls. Identical inputs produce
an identical envelope, modulo the ``generated_at`` timestamp (which is
parametrisable for deterministic tests).

ARCHITECTURE:
    * Reads from ELINS.ingestion_bus.list_packets (news_basin + email_ep_dash)
    * Reads from ELINS.elins_project.list_macro_runs
    * Reads from operator_state.get_operator_state (history)
    * Writes one packet to ELINS.ingestion_bus.write_packet
    * Writes one JSON file to <library_dir>/<user_id>/<YYYY-MM-DD>.json

DEGRADES GRACEFULLY:
    * No news / no email / no micro / no macro — sections still present
      but with zeroed counts and empty lists. The envelope still writes.
    * Completely empty (all four sources empty) — short-circuit: return
      ``{type, user, date, empty: True}`` with NO bus / library writes.
    * Missing modules (operator_state import error, etc.) — collectors
      return [] and log a warning; the composer continues.

CONFIG:
    Archive dir:  ClarityOS_Library/daily_elins
        Files at  <dir>/<user_id>/<YYYY-MM-DD>.json
        Override with CLARITYOS_DAILY_ELINS_DIR.

PUBLIC API:
    collect_news_signals(user_id, since)            -> list[dict]
    collect_email_signals(user_id, since)           -> list[dict]
    collect_micro_signals(user_id, since)           -> list[dict]
    build_daily_elins_envelope(user_id, date,
                               news, emails, micro,
                               *, macro=None,
                               generated_at=None)   -> dict
    write_to_ingestion_bus(envelope)                -> str
    write_to_library(envelope)                      -> str
    run_daily_personal_elins(user_id, date=None)    -> dict   # entrypoint
"""
from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("clarityos.daily_personal_elins")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ENVELOPE_TYPE:       str = "daily_personal_elins"
DEFAULT_LIBRARY_DIR: str = "ClarityOS_Library/daily_elins"

# Cap for bus polling. The bus FIFO-drops at 1000 entries; we ask for
# everything in one shot and post-filter.
_BUS_POLL_LIMIT: int = 1000

# Cap for macro-run polling. The macro scheduler runs once per cadence
# tick; 100 covers months of history.
_MACRO_POLL_LIMIT: int = 100


# ---------------------------------------------------------------------------
# Path + date helpers
# ---------------------------------------------------------------------------
def _resolve_library_dir() -> Path:
    """Resolve the daily-elins archive directory.

    Honors ``CLARITYOS_DAILY_ELINS_DIR``; falls back to
    ``DEFAULT_LIBRARY_DIR`` relative to the current working directory.
    """
    override = (os.environ.get("CLARITYOS_DAILY_ELINS_DIR") or "").strip()
    return Path(override) if override else Path(DEFAULT_LIBRARY_DIR)


def _day_window_utc(d: date_cls) -> tuple[datetime, datetime]:
    """Return [start, end) datetimes for the given date in UTC."""
    start = datetime.combine(d, time.min, tzinfo=timezone.utc)
    end   = start + timedelta(days=1)
    return start, end


def _parse_iso(s: Any) -> Optional[datetime]:
    """Best-effort ISO 8601 parse. Returns timezone-aware UTC datetime,
    or None on failure. Naive inputs are coerced to UTC."""
    if not isinstance(s, str) or not s.strip():
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coerce_date(value: Any) -> date_cls:
    """Coerce ``value`` to a date. Accepts date, datetime, ISO string,
    or None (→ today UTC). Raises ValueError on unparseable input."""
    if value is None:
        return datetime.now(timezone.utc).date()
    if isinstance(value, date_cls) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, str):
        try:
            return date_cls.fromisoformat(value)
        except ValueError as e:
            raise ValueError(f"unparseable date: {value!r}") from e
    raise ValueError(f"unsupported date type: {type(value).__name__}")


# ---------------------------------------------------------------------------
# 1. collect_news_signals
# ---------------------------------------------------------------------------
def collect_news_signals(
    user_id: str,
    since: Optional[datetime] = None,
    *,
    until: Optional[datetime] = None,
) -> list[dict]:
    """Flatten news-basin envelopes for ``user_id`` into individual items.

    Reads from ``ELINS.ingestion_bus.list_packets(type_filter="news_basin")``.
    Filters envelopes by:
        * ``user`` == user_id
        * ``generated_at`` >= since (if since is not None)
        * ``generated_at`` <  until (if until is not None)

    Returns the flattened ``items`` list — each item is a news headline
    packet (the canonical shape from ``personal_news_basin.normalize_headline``).

    Never raises. Missing bus module / no packets / malformed entries
    all degrade to an empty list.
    """
    try:
        from ELINS import ingestion_bus
    except ImportError as e:
        logger.warning("daily_personal_elins: ingestion_bus unavailable: %s", e)
        return []

    packets = ingestion_bus.list_packets(
        type_filter="news_basin", limit=_BUS_POLL_LIMIT,
    )
    return _flatten_packets_for_user(packets, user_id, since=since, until=until)


# ---------------------------------------------------------------------------
# 2. collect_email_signals
# ---------------------------------------------------------------------------
def collect_email_signals(
    user_id: str,
    since: Optional[datetime] = None,
    *,
    until: Optional[datetime] = None,
) -> list[dict]:
    """Flatten email-dash envelopes for ``user_id`` into individual items.

    Same filtering + flattening discipline as ``collect_news_signals``,
    but reads ``type_filter="email_ep_dash"``. Each returned item is an
    email packet (the canonical shape from
    ``email_ep_dash.normalize_email``).
    """
    try:
        from ELINS import ingestion_bus
    except ImportError as e:
        logger.warning("daily_personal_elins: ingestion_bus unavailable: %s", e)
        return []

    packets = ingestion_bus.list_packets(
        type_filter="email_ep_dash", limit=_BUS_POLL_LIMIT,
    )
    return _flatten_packets_for_user(packets, user_id, since=since, until=until)


def _flatten_packets_for_user(
    packets: list,
    user_id: str,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
) -> list[dict]:
    """Shared implementation for collect_news_signals + collect_email_signals."""
    if not isinstance(packets, list):
        return []
    out: list[dict] = []
    for pkt in packets:
        if not isinstance(pkt, dict):
            continue
        if pkt.get("user") != user_id:
            continue
        gen_at = _parse_iso(pkt.get("generated_at"))
        if since is not None:
            if gen_at is None or gen_at < since:
                continue
        if until is not None:
            if gen_at is None or gen_at >= until:
                continue
        items = pkt.get("items") or []
        if not isinstance(items, list):
            continue
        for it in items:
            if isinstance(it, dict):
                out.append(it)
    return out


# ---------------------------------------------------------------------------
# 3. collect_micro_signals
# ---------------------------------------------------------------------------
def collect_micro_signals(
    user_id: str,
    since: Optional[datetime] = None,
    *,
    until: Optional[datetime] = None,
) -> list[dict]:
    """Return per-day operator-state events for ``user_id``.

    Reads ``operator_state.get_operator_state(user_id)`` and pulls
    ``elins_history`` + ``g_history`` entries whose ``ts`` lies in the
    given window. Each returned dict carries a ``kind`` key
    (``"elins"`` or ``"g_run"``) plus all the original entry fields.

    Never raises. Missing operator_state module → empty list.
    """
    try:
        import operator_state
    except ImportError as e:
        logger.warning("daily_personal_elins: operator_state unavailable: %s", e)
        return []

    try:
        state = operator_state.get_operator_state(user_id)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("daily_personal_elins: operator_state read failed: %s", e)
        return []

    since_ts = since.timestamp() if since is not None else None
    until_ts = until.timestamp() if until is not None else None

    out: list[dict] = []
    for kind_label, key in (("elins", "elins_history"), ("g_run", "g_history")):
        for entry in (state.get(key) or []):
            if not isinstance(entry, dict):
                continue
            ts = entry.get("ts")
            if not isinstance(ts, (int, float)):
                continue
            if since_ts is not None and ts < since_ts:
                continue
            if until_ts is not None and ts >= until_ts:
                continue
            row = {"kind": kind_label}
            row.update(entry)
            out.append(row)
    return out


def _collect_macro_context(d: date_cls) -> Optional[dict]:
    """Find a macro ELINS run whose ts lies inside the given UTC date.

    Returns the matching macro-run record, or None when no run was
    captured that day (e.g., scheduler disabled).
    """
    try:
        from ELINS import elins_project
    except ImportError as e:
        logger.warning("daily_personal_elins: elins_project unavailable: %s", e)
        return None

    try:
        runs = elins_project.list_macro_runs(limit=_MACRO_POLL_LIMIT)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("daily_personal_elins: list_macro_runs failed: %s", e)
        return None

    if not isinstance(runs, list):
        return None
    start, end = _day_window_utc(d)
    start_ts, end_ts = start.timestamp(), end.timestamp()

    for run in runs:
        if not isinstance(run, dict):
            continue
        ts = run.get("ts")
        if isinstance(ts, (int, float)) and start_ts <= ts < end_ts:
            return run
    return None


# ---------------------------------------------------------------------------
# Aggregators — pure functions, deterministic
# ---------------------------------------------------------------------------
def _aggregate_news(news_items: list[dict]) -> dict:
    """Aggregate the ``meso.news`` section."""
    distribution = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    source_counter: Counter = Counter()
    region_counter: Counter = Counter()

    for it in news_items:
        if not isinstance(it, dict):
            continue
        src = it.get("source")
        if isinstance(src, str) and src.strip():
            source_counter[src.strip()] += 1
        region = it.get("region")
        if isinstance(region, str) and region.strip():
            region_counter[region.strip()] += 1
        pressure = it.get("pressure")
        if isinstance(pressure, str):
            key = pressure.upper().strip()
            if key in distribution:
                distribution[key] += 1

    return {
        "count":                 len(news_items),
        "top_sources":           [s for s, _ in source_counter.most_common(3)],
        "pressure_distribution": distribution,
        "regions":               dict(region_counter),
    }


def _aggregate_emails(email_items: list[dict]) -> dict:
    """Aggregate the ``meso.email`` section."""
    high_importance = 0
    with_deadlines  = 0
    thread_counter: Counter = Counter()

    for it in email_items:
        if not isinstance(it, dict):
            continue
        if it.get("importance") == "HIGH":
            high_importance += 1
        if bool(it.get("has_deadline")):
            with_deadlines += 1
        tk = it.get("thread_key")
        if isinstance(tk, str) and tk:
            thread_counter[tk] += 1

    return {
        "count":           len(email_items),
        "high_importance": high_importance,
        "with_deadlines":  with_deadlines,
        "threads":         dict(thread_counter),
    }


def _aggregate_micro(micro_items: list[dict]) -> dict:
    """Aggregate the ``micro`` section."""
    ep_counter:    Counter = Counter()
    kind_counter:  Counter = Counter()

    for it in micro_items:
        if not isinstance(it, dict):
            continue
        kind = it.get("kind")
        if isinstance(kind, str):
            kind_counter[kind] += 1
        flags = it.get("ep_flags") or []
        if isinstance(flags, list):
            for f in flags:
                if isinstance(f, str) and f.strip():
                    ep_counter[f.strip()] += 1

    notable = sorted(
        f"{k}_x{n}" for k, n in kind_counter.most_common(5)
    )

    return {
        "message_count":  len(micro_items),
        "ep_flags":       dict(ep_counter),
        "notable_events": notable,
    }


def _derive_macro_section(macro_run: Optional[dict],
                          news_agg: dict,
                          email_agg: dict) -> dict:
    """Compute the ``macro`` section.

    Uses macro-run regions as ``dominant_themes`` and derives
    ``field_weather`` + ``risk_zones`` from the aggregated meso data.
    """
    if not isinstance(macro_run, dict):
        return {
            "field_weather":   "unknown",
            "dominant_themes": [],
            "risk_zones":      _derive_risk_zones(news_agg, email_agg),
        }

    regions = macro_run.get("regions") or []
    if not isinstance(regions, list):
        regions = []

    return {
        "field_weather":   _derive_field_weather(news_agg, email_agg),
        "dominant_themes": [str(r) for r in regions if isinstance(r, str)],
        "risk_zones":      _derive_risk_zones(news_agg, email_agg),
    }


def _derive_field_weather(news_agg: dict, email_agg: dict) -> str:
    """Map aggregated counts to a one-word weather descriptor.

    ``turbulent`` — any HIGH news or any HIGH email importance.
    ``mixed``     — any MEDIUM news / MEDIUM-ish email volume.
    ``stable``    — everything LOW or zero.
    """
    news_high = news_agg.get("pressure_distribution", {}).get("HIGH", 0)
    news_med  = news_agg.get("pressure_distribution", {}).get("MEDIUM", 0)
    email_high = email_agg.get("high_importance", 0)
    deadlines  = email_agg.get("with_deadlines", 0)

    if news_high > 0 or email_high > 0:
        return "turbulent"
    if news_med > 0 or deadlines > 0:
        return "mixed"
    return "stable"


def _derive_risk_zones(news_agg: dict, email_agg: dict) -> list[str]:
    """Deterministic risk-zone label set."""
    zones: list[str] = []
    if email_agg.get("with_deadlines", 0) > 0 or email_agg.get("high_importance", 0) > 0:
        zones.append("obligations")
    threads = email_agg.get("threads") or {}
    if isinstance(threads, dict) and len(threads) >= 3:
        zones.append("relationships")
    if news_agg.get("pressure_distribution", {}).get("HIGH", 0) > 0:
        zones.append("external_pressure")
    return zones


def _derive_summary(macro_section: dict,
                    meso_section: dict,
                    micro_section: dict) -> dict:
    """Template-driven one-line headline + ranked focus list."""
    news  = meso_section.get("news", {})
    email = meso_section.get("email", {})

    headline = (
        f"{news.get('count', 0)} news items "
        f"({news.get('pressure_distribution', {}).get('HIGH', 0)} HIGH) · "
        f"{email.get('count', 0)} emails "
        f"({email.get('with_deadlines', 0)} with deadlines) · "
        f"{micro_section.get('message_count', 0)} micro events"
    )

    focus: list[str] = []
    # 1. Obligations first if present
    if email.get("with_deadlines", 0) > 0:
        focus.append(f"deadlines:{email['with_deadlines']}")
    if email.get("high_importance", 0) > 0:
        focus.append(f"high_importance_email:{email['high_importance']}")
    # 2. External pressure
    if news.get("pressure_distribution", {}).get("HIGH", 0) > 0:
        focus.append(
            f"news_pressure:{news['pressure_distribution']['HIGH']}",
        )
    # 3. Top news region
    regions = news.get("regions") or {}
    if isinstance(regions, dict) and regions:
        top_region = max(regions.items(), key=lambda kv: (kv[1], kv[0]))[0]
        focus.append(f"region:{top_region}")
    # 4. Top ep_flag from micro
    micro_flags = micro_section.get("ep_flags") or {}
    if isinstance(micro_flags, dict) and micro_flags:
        top_flag = max(micro_flags.items(), key=lambda kv: (kv[1], kv[0]))[0]
        focus.append(f"ep:{top_flag}")
    # 5. Field weather (always last)
    fw = macro_section.get("field_weather")
    if isinstance(fw, str) and fw and fw != "unknown":
        focus.append(f"field:{fw}")

    return {
        "headline": headline,
        "focus":    focus[:5],
    }


# ---------------------------------------------------------------------------
# 4. build_daily_elins_envelope
# ---------------------------------------------------------------------------
def build_daily_elins_envelope(
    user_id: str,
    d: Any,
    news: list[dict],
    emails: list[dict],
    micro: list[dict],
    *,
    macro: Optional[dict] = None,
    generated_at: Optional[str] = None,
) -> dict:
    """Compose the per-user, per-day envelope.

    Pure-function: identical inputs (including ``generated_at`` and
    ``macro``) produce an identical envelope.

    Args:
        user_id:      caller's username.
        d:            target date (date / datetime / ISO string).
        news/emails/micro: pre-collected signal lists.
        macro:        optional macro-run record from
                      ``elins_project.get_macro_run``. None ⇒ field_weather
                      will be ``"unknown"`` and dominant_themes empty.
        generated_at: optional ISO 8601 string. Defaults to ``now``.

    Returns the full envelope. Does NOT touch the bus or library.
    """
    target_date = _coerce_date(d)

    news_agg  = _aggregate_news(news or [])
    email_agg = _aggregate_emails(emails or [])
    micro_agg = _aggregate_micro(micro or [])
    macro_section = _derive_macro_section(macro, news_agg, email_agg)
    meso_section  = {"news": news_agg, "email": email_agg}
    summary       = _derive_summary(macro_section, meso_section, micro_agg)

    return {
        "type":         ENVELOPE_TYPE,
        "user":         str(user_id) if user_id is not None else "system",
        "date":         target_date.isoformat(),
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "macro":        macro_section,
        "meso":         meso_section,
        "micro":        micro_agg,
        "summary":      summary,
    }


# ---------------------------------------------------------------------------
# 5. write_to_ingestion_bus
# ---------------------------------------------------------------------------
def write_to_ingestion_bus(envelope: dict) -> str:
    """Submit the daily envelope as a packet on the ingestion bus.

    Returns the packet_id. Propagates ValueError on shape problems.
    """
    from ELINS import ingestion_bus
    return ingestion_bus.write_packet(envelope)


# ---------------------------------------------------------------------------
# 6. write_to_library
# ---------------------------------------------------------------------------
def write_to_library(envelope: dict) -> str:
    """Persist a JSON copy at
    ``<library_dir>/<user_id>/<YYYY-MM-DD>.json``.

    Per-user subdirectory keeps the spec's literal ``YYYY-MM-DD.json``
    filename while still supporting multiple users per archive root.
    Overwrites prior copies for the same (user, date) — the daily
    envelope is the canonical view as of run time.

    Returns the absolute file path as a string.
    """
    if not isinstance(envelope, dict):
        raise ValueError("envelope must be a dict")
    user = envelope.get("user")
    if not isinstance(user, str) or not user:
        raise ValueError("envelope.user must be a non-empty string")
    date_s = envelope.get("date")
    if not isinstance(date_s, str) or not date_s:
        raise ValueError("envelope.date must be 'YYYY-MM-DD'")

    base = _resolve_library_dir() / user
    base.mkdir(parents=True, exist_ok=True)
    file_path = base / f"{date_s}.json"
    file_path.write_text(
        json.dumps(envelope, indent=2, default=str),
        encoding="utf-8",
    )
    return str(file_path)


# ---------------------------------------------------------------------------
# 7. run_daily_personal_elins (entrypoint)
# ---------------------------------------------------------------------------
def _is_envelope_empty(news: list, emails: list, micro: list,
                       macro: Optional[dict]) -> bool:
    """An envelope is empty when ALL four sources contributed nothing."""
    return (
        not news
        and not emails
        and not micro
        and macro is None
    )


def run_daily_personal_elins(
    user_id: str,
    d: Any = None,
) -> dict:
    """Main entrypoint. Collect → compose → write.

    Workflow:
        1. Resolve the target date (defaults to today UTC).
        2. Compute the [start, end) UTC window for that date.
        3. Collect news + email + micro signals in the window;
           pull the macro-run record (if any) for the date.
        4. If everything is empty → short-circuit to
           ``{type, user, date, empty: True}`` with NO writes.
        5. Otherwise build the envelope and write to bus + library
           (each best-effort; failures recorded as None on the
           returned envelope under leading-underscore meta keys).

    Returns the envelope.
    """
    target_date = _coerce_date(d)
    start, end = _day_window_utc(target_date)

    news   = collect_news_signals(user_id,  since=start, until=end)
    emails = collect_email_signals(user_id, since=start, until=end)
    micro  = collect_micro_signals(user_id, since=start, until=end)
    macro  = _collect_macro_context(target_date)

    if _is_envelope_empty(news, emails, micro, macro):
        logger.info(
            "daily_personal_elins: empty day for %s on %s — short-circuiting",
            user_id, target_date.isoformat(),
        )
        return {
            "type":  ENVELOPE_TYPE,
            "user":  str(user_id) if user_id is not None else "system",
            "date":  target_date.isoformat(),
            "empty": True,
        }

    envelope = build_daily_elins_envelope(
        user_id, target_date, news, emails, micro, macro=macro,
    )

    try:
        envelope["_bus_packet_id"] = write_to_ingestion_bus(envelope)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("daily_personal_elins: bus write failed: %s", e)
        envelope["_bus_packet_id"] = None

    try:
        envelope["_library_path"] = write_to_library(envelope)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("daily_personal_elins: library write failed: %s", e)
        envelope["_library_path"] = None

    return envelope
