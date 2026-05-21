"""
v38 — ELINS interactive dashboard aggregator.

Builds a single composite snapshot from every persisted ELINS surface
(global daily run, six regional runs, latest macro pass, latest
entity-graph snapshot) so the cockpit can render the full intelligence
picture from one round-trip.

Pure with respect to the contents of the persistence layer at call
time: same underlying data → same output. No network, no model.

Public API:
    get_dashboard_snapshot(user) -> dict
    get_dashboard_for_date(user, date_str) -> dict
    get_founder_overview() -> dict        # founder-only summary
    SNAPSHOT_VERSION

Snapshot shape (the dict the endpoints return verbatim):

    {
      "ts":   float,
      "date": "YYYY-MM-DD",
      "global": {
        "scenario_id": str | None,
        "ep_mean": float,
        "domains": {domain_key: float, ...},
        "top_primitives": [{key, intensity}, ...],
        "forecast": [float, ...],          # multi_envelope from forecast_engine
        "has_eso": bool,
        "user": str,
        "day": str,
        "available": bool
      },
      "regional": {
        "<region>": {
          "scenario_id": str | None,
          "ep_mean": float,
          "domains": {...},
          "top_primitives": [...],
          "forecast": [float, ...],
          "has_eso": bool,
          "day": str,
          "available": bool
        },
        ...
      },
      "macro": {
        "last_run_id": str | None,
        "last_run_ts": float | None,
        "ep_mean": float | None,
        "regions_count": int | None,
        "external_signal_mode": str | None
      },
      "entity_graph": {
        "entity_count": int,
        "edge_count":   int,
        "updated_ts":   float,
        "top_entities": [{name, degree, ep_mean, top_domains}, ...],
        "available":    bool
      },
      "version": "elins_dashboard.v38.1"
    }
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from ELINS import elins_project, forecast_engine, regional_elins
import elins_entity_graph
import elins_scheduler_config
import operator_state

logger = logging.getLogger("clarityos.elins_dashboard")

SNAPSHOT_VERSION: str = "elins_dashboard.v39.1"

_TOP_PRIMITIVES_LIMIT: int = 4
_TOP_ENTITIES_LIMIT: int = 6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _empty_section() -> dict:
    return {
        "scenario_id": None,
        "ep_mean": 0.0,
        "domains": {},
        "top_primitives": [],
        "forecast": [],
        "has_eso": False,
        "available": False,
    }


def _has_eso(run_record: dict) -> bool:
    """Detect whether the ELINS payload had an ESO blended in."""
    if not isinstance(run_record, dict):
        return False
    obj = run_record.get("elins") or {}
    ext = obj.get("external_signals") or {}
    return bool(ext.get("present"))


def _intensities_of(run_record: dict) -> dict:
    obj = run_record.get("elins") or {}
    return (obj.get("primitives") or {}).get("intensities") or run_record.get("primitives") or {}


def _domain_scores_of(run_record: dict) -> dict:
    obj = run_record.get("elins") or {}
    scores = (obj.get("domain_mapping") or {}).get("scores")
    if scores:
        return scores
    return run_record.get("domain_scores") or {}


def _ep_mean_of(run_record: dict) -> float:
    ep = (run_record.get("elins") or {}).get("ep_field_summary") or run_record.get("ep_field_summary") or {}
    try:
        return float(ep.get("intensity_mean") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _forecast_of(run_record: dict) -> list[float]:
    """Return the multi-envelope. Falls back to recomputing it from
    primitives if the embedded forecast block is missing (older
    persisted records may pre-date v34)."""
    obj = run_record.get("elins") or {}
    fe = obj.get("forecast_engine") or {}
    me = fe.get("multi_envelope")
    if isinstance(me, list) and me:
        return [round(float(v), 6) for v in me]
    intensities = _intensities_of(run_record)
    if not intensities:
        return []
    edges = (obj.get("causal_chain") or {}).get("edges") or []
    block = forecast_engine.compute_forecast_block(intensities, edges=edges, days=5)
    return [round(float(v), 6) for v in (block.get("multi_envelope") or [])]


def _top_primitives(intensities: dict, limit: int = _TOP_PRIMITIVES_LIMIT) -> list[dict]:
    if not isinstance(intensities, dict):
        return []
    items = sorted(
        intensities.items(),
        key=lambda kv: (-float(kv[1] or 0.0), kv[0]),
    )
    out = []
    for k, v in items[: max(1, int(limit))]:
        try:
            out.append({"key": str(k), "intensity": round(float(v or 0.0), 4)})
        except (TypeError, ValueError):
            continue
    return out


def _section_from_run(run_record: Optional[dict], *, day: str) -> dict:
    section = _empty_section()
    section["day"] = day
    if not run_record:
        return section
    obj = run_record.get("elins") or {}
    intensities = _intensities_of(run_record)
    section.update({
        "scenario_id": (
            (obj.get("output_object") or {}).get("scenario_id")
            or run_record.get("scenario_id")
        ),
        "ep_mean": round(_ep_mean_of(run_record), 4),
        "domains": _domain_scores_of(run_record),
        "top_primitives": _top_primitives(intensities),
        "forecast": _forecast_of(run_record),
        "has_eso": _has_eso(run_record),
        "available": True,
    })
    return section


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------
def _global_section(user: str, *, date_str: Optional[str] = None) -> dict:
    """Latest (or for-date) global ELINS run for the user. Falls back
    to the scheduler's system_user run when the caller has no global
    run of their own — that way regular users see the system view."""
    target_user = user
    target_day = date_str
    rec = None
    if target_day:
        rec = elins_project.get_run(_user_day_id(target_user, target_day))
    else:
        runs = elins_project.list_runs_for_user(target_user, limit=1)
        rec = runs[0] if runs else None
    if rec is None:
        # Fallback to the scheduler's system user.
        sys_user = (elins_scheduler_config.get_config() or {}).get("system_user") or "scheduler"
        if target_day:
            rec = elins_project.get_run(_user_day_id(sys_user, target_day))
        else:
            sys_runs = elins_project.list_runs_for_user(sys_user, limit=1)
            rec = sys_runs[0] if sys_runs else None
        target_user = sys_user
    section = _section_from_run(rec, day=(rec or {}).get("day") or (target_day or _today_utc()))
    section["user"] = target_user
    return section


def _user_day_id(user: str, day: str) -> str:
    safe_user = user.replace("/", "_")
    return f"{safe_user}_{day}"


def _regional_section(*, date_str: Optional[str] = None) -> dict:
    """Per-region snapshot. ``date_str`` pins to a specific day; else
    we use the most-recent persisted run per region."""
    out: dict[str, dict] = {}
    for region in regional_elins.REGION_CODES:
        if date_str:
            rec = elins_project.load_regional_run(region, day=date_str)
        else:
            rec = elins_project.latest_regional_run(region)
        section = _section_from_run(rec, day=(rec or {}).get("day") or (date_str or _today_utc()))
        out[region] = section
    return out


def _macro_section() -> dict:
    rows = elins_project.list_macro_runs(limit=1)
    if not rows:
        return {
            "last_run_id": None,
            "last_run_ts": None,
            "ep_mean": None,
            "regions_count": None,
            "external_signal_mode": None,
        }
    rec = rows[0]
    detail = elins_project.get_macro_run_with_constituents(rec["run_id"]) or {}
    global_run = (detail.get("global_run") or {}) if isinstance(detail.get("global_run"), dict) else {}
    ep_mean = None
    if global_run:
        ep_mean = round(_ep_mean_of(global_run), 4)
    return {
        "last_run_id": rec.get("run_id"),
        "last_run_ts": rec.get("ts"),
        "ep_mean": ep_mean,
        "regions_count": len(rec.get("regions") or []),
        "external_signal_mode": rec.get("external_signal_mode"),
    }


def _entity_graph_section(*, top_n: int = _TOP_ENTITIES_LIMIT) -> dict:
    snap = elins_project.load_latest_entity_graph()
    if snap is None:
        return {
            "entity_count": 0,
            "edge_count": 0,
            "updated_ts": 0.0,
            "top_entities": [],
            "available": False,
        }
    graph = snap.get("graph") or {}
    entities = graph.get("entities") or {}
    edges = graph.get("edges") or {}
    # Top entities by degree desc, name asc tie-break.
    items = sorted(
        entities.items(),
        key=lambda kv: (-int((kv[1] or {}).get("degree") or 0), kv[0]),
    )
    top_entities: list[dict] = []
    for name, rec in items[: max(1, int(top_n))]:
        domains = (rec or {}).get("domains") or {}
        top_domains = [
            k for k, _ in sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        ]
        top_entities.append({
            "name": name,
            "degree": int((rec or {}).get("degree") or 0),
            "ep_mean": float(((rec or {}).get("ep_stats") or {}).get("mean") or 0.0),
            "top_domains": top_domains,
        })
    return {
        "entity_count": int(snap.get("entity_count") or len(entities)),
        "edge_count": int(snap.get("edge_count") or len(edges)),
        "updated_ts": float(graph.get("updated_ts") or snap.get("ts") or 0.0),
        "top_entities": top_entities,
        "available": True,
    }


# ---------------------------------------------------------------------------
# Public — get_dashboard_snapshot / get_dashboard_for_date
# ---------------------------------------------------------------------------
def get_dashboard_snapshot(user: str) -> dict:
    if not isinstance(user, str) or not user:
        raise ValueError("user must be a non-empty string")
    return _build_snapshot(user, date_str=None)


def get_dashboard_for_date(user: str, date_str: str) -> dict:
    if not isinstance(user, str) or not user:
        raise ValueError("user must be a non-empty string")
    if not isinstance(date_str, str) or not date_str:
        raise ValueError("date_str must be a non-empty YYYY-MM-DD string")
    # Cheap shape validation — exactly 10 chars, 4-2-2 form.
    if len(date_str) != 10 or date_str[4] != "-" or date_str[7] != "-":
        raise ValueError("date_str must be YYYY-MM-DD")
    return _build_snapshot(user, date_str=date_str)


def _build_snapshot(user: str, *, date_str: Optional[str]) -> dict:
    now = time.time()
    g = _global_section(user, date_str=date_str)
    r = _regional_section(date_str=date_str)
    m = _macro_section()
    e = _entity_graph_section()
    # v39 — continuity slice (metadata-only). Cheap to compute since
    # operator_state is per-user + already memoised in memory.
    try:
        continuity = operator_state.continuity_section(user)
    except Exception:  # pragma: no cover (defensive)
        continuity = {
            "last_topics": [],
            "preferred_domains": [],
            "preferred_regions": [],
            "external_signal_mode": "cloud_only",
            "history_count": 0, "g_count": 0,
        }
    return {
        "ts": now,
        "date": date_str or _today_utc(),
        "global": g,
        "regional": r,
        "macro": m,
        "entity_graph": e,
        "continuity": continuity,
        "version": SNAPSHOT_VERSION,
    }


# ---------------------------------------------------------------------------
# Founder-only — overview (counts + coverage)
# ---------------------------------------------------------------------------
def get_founder_overview() -> dict:
    macro_runs = elins_project.list_macro_runs(limit=200)
    snapshots = elins_project.list_entity_graph_snapshots(limit=200)
    coverage: dict[str, dict] = {}
    for region in regional_elins.REGION_CODES:
        runs = elins_project.list_regional_runs(region, limit=200)
        coverage[region] = {
            "runs": len(runs),
            "latest_day": (runs[0].get("day") if runs else None),
        }
    latest_date: Optional[str] = None
    if macro_runs:
        try:
            latest_date = datetime.fromtimestamp(
                float(macro_runs[0].get("ts") or 0.0), tz=timezone.utc,
            ).strftime("%Y-%m-%d")
        except Exception:  # pragma: no cover (defensive)
            latest_date = None
    return {
        "latest_date": latest_date,
        "macro_runs_count": len(macro_runs),
        "entity_graph_snapshots": len(snapshots),
        "regional_coverage": coverage,
        "scheduler_config": elins_scheduler_config.get_config(),
        "version": SNAPSHOT_VERSION,
    }
