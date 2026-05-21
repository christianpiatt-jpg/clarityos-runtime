"""
v33 — ELINS persistence layer.

Maps the canonical ``elins_project/`` substructure onto the project's
existing two-backend (memory + Firestore) pattern. Five logical
collections:

    runs/                   per-day per-user ELINS runs
    primitives/             rolling primitive intensity index
    domains/                rolling domain history
    baseline/               EP baseline averages
    config/                 module-level config (currently just
                            "version" + "thresholds")

Public helpers (the only API consumers should use):

    save_daily_run(user, run, *, day=None) -> str
    load_previous_run(user, *, day=None) -> dict | None
    update_global_primitive_index(run) -> dict
    update_domain_history(user, run) -> dict
    update_ep_baseline(user, run) -> dict
    get_baseline(user) -> dict
    list_runs_for_user(user, *, limit=30) -> list[dict]
    get_run(run_id) -> dict | None
    list_primitive_index(*, limit=200) -> list[dict]
    list_domain_history(user, *, limit=200) -> list[dict]

NEVER stores raw text outside ``runs[*].input_text`` (which is the
ELINS scenario the user explicitly submitted via /elins/g/run or
/elins/preview). Everything else is metadata: counts, intensities,
timestamps, scenario_ids.

Backend: in-memory + Firestore. Idempotent on day-id collisions
(``runs/{user}_{YYYY-MM-DD}`` keys) so re-saving the same day's run
overwrites instead of duplicating.
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("clarityos.elins.elins_project")

_RUNS_COLL = "elins_project_runs"
_PRIMS_COLL = "elins_project_primitives"
_DOMAINS_COLL = "elins_project_domains"
_BASELINE_COLL = "elins_project_baseline"
_CONFIG_COLL = "elins_project_config"
_REGIONAL_COLL = "elins_project_regional"   # v35 — regional runs
_MACRO_COLL = "elins_project_macro_runs"    # v36 — macro-ELINS run log
_ENTITY_GRAPH_COLL = "elins_project_entity_graph"  # v37 — entity graph snapshots

_REGIONAL_REGIONS: tuple = ("US", "EU", "MEA", "APAC", "Markets", "Tech")


def _backend() -> str:
    return os.environ.get("CLARITYOS_BACKEND", "memory").lower()


# In-memory state. Tests reset via ``_reset_memory_for_tests``.
_MEM_RUNS: dict[str, dict] = {}        # run_id -> record
_MEM_PRIMS: list[dict] = []            # rolling appended snapshots
_MEM_DOMAINS: dict[str, list] = {}     # per-user list of {domain, count, ts}
_MEM_BASELINE: dict[str, dict] = {}    # per-user baseline averages
_MEM_REGIONAL: dict[str, dict] = {}    # v35 — region/date -> regional run record
_MEM_MACRO: dict[str, dict] = {}       # v36 — run_id -> macro run record
_MEM_ENTITY_GRAPH: dict[str, dict] = {}  # v37 — snapshot_id -> entity graph record

_firestore_client = None


def _get_firestore():
    global _firestore_client
    if _firestore_client is not None:
        return _firestore_client
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "CLARITYOS_BACKEND=firestore but google-cloud-firestore is not installed."
        ) from e
    _firestore_client = firestore.Client()
    logger.info("elins_project firestore client initialised")
    return _firestore_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _run_id(user: str, day: str) -> str:
    safe_user = user.replace("/", "_")
    return f"{safe_user}_{day}"


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
def save_daily_run(user: str, run: dict, *, day: Optional[str] = None) -> str:
    """Persist a single ELINS run for the user. Idempotent: re-saving
    on the same day overwrites."""
    if not user or not isinstance(user, str):
        raise ValueError("user must be a non-empty string")
    if not isinstance(run, dict):
        raise ValueError("run must be a dict")
    day_str = day or _today_utc()
    run_id = _run_id(user, day_str)
    record = {
        "id": run_id,
        "user": user,
        "day": day_str,
        "saved_ts": time.time(),
        "scenario_id": (run.get("output_object") or {}).get("scenario_id"),
        "summary": (run.get("output_object") or {}).get("summary") or {},
        "primitives": (run.get("primitives") or {}).get("intensities") or {},
        "domain_top": (run.get("domain_mapping") or {}).get("effective_top"),
        # v38 — preserve the full ELINS payload (forecast block + domain
        # mapping + ESO presence) so the dashboard can reconstruct the
        # global section without re-running the pipeline. Older readers
        # ignore the extra field.
        "domain_scores": (run.get("domain_mapping") or {}).get("scores") or {},
        "ep_field_summary": run.get("ep_field_summary") or {},
        "elins": run,
        # Don't store the raw text again — it's already in run.input_phase.text
        # if the caller persists the run object. Here we just keep the metadata.
        "input_word_count": (run.get("input_phase") or {}).get("word_count", 0),
        "version": (run.get("output_object") or {}).get("version") or "elins.v33.1",
    }
    if _backend() == "firestore":
        _get_firestore().collection(_RUNS_COLL).document(run_id).set(record)
    else:
        _MEM_RUNS[run_id] = dict(record)
    return run_id


def load_previous_run(user: str, *, day: Optional[str] = None) -> Optional[dict]:
    """Return the user's most recent run before ``day`` (defaults to
    today). Returns None if no prior runs exist."""
    cutoff_day = day or _today_utc()
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = (
            _get_firestore().collection(_RUNS_COLL)
            .where(filter=FieldFilter("user", "==", user))
            .where(filter=FieldFilter("day", "<", cutoff_day))
        )
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = [r for r in _MEM_RUNS.values()
                if r.get("user") == user and (r.get("day") or "") < cutoff_day]
    if not rows:
        return None
    rows.sort(key=lambda r: (r.get("day") or "", float(r.get("saved_ts", 0.0))), reverse=True)
    return dict(rows[0])


def get_run(run_id: str) -> Optional[dict]:
    if not run_id:
        return None
    if _backend() == "firestore":
        doc = _get_firestore().collection(_RUNS_COLL).document(run_id).get()
        return doc.to_dict() if doc.exists else None
    rec = _MEM_RUNS.get(run_id)
    return dict(rec) if rec is not None else None


def list_runs_for_user(user: str, *, limit: int = 30) -> list[dict]:
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = _get_firestore().collection(_RUNS_COLL).where(
            filter=FieldFilter("user", "==", user),
        )
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = [dict(r) for r in _MEM_RUNS.values() if r.get("user") == user]
    rows.sort(key=lambda r: float(r.get("saved_ts", 0.0)), reverse=True)
    return rows[: max(1, int(limit))]


# ---------------------------------------------------------------------------
# Primitive index
# ---------------------------------------------------------------------------
def update_global_primitive_index(run: dict) -> dict:
    """Append a snapshot of the run's primitive intensities to the
    rolling index. The snapshot is metadata-only (intensities + ts +
    scenario_id); no input text. Returns the snapshot."""
    if not isinstance(run, dict):
        raise ValueError("run must be a dict")
    snap = {
        "ts": time.time(),
        "scenario_id": (run.get("output_object") or {}).get("scenario_id"),
        "intensities": (run.get("primitives") or {}).get("intensities") or {},
        "domain_top": (run.get("domain_mapping") or {}).get("effective_top"),
        "user": (run.get("input_phase") or {}).get("user"),
    }
    if _backend() == "firestore":
        # One doc per snapshot; id is timestamp + scenario_id so collisions
        # would be a same-input-second-collision, which we accept.
        sid = snap.get("scenario_id") or "unk"
        doc_id = f"{int(snap['ts']*1000)}_{sid}"
        _get_firestore().collection(_PRIMS_COLL).document(doc_id).set(snap)
    else:
        _MEM_PRIMS.append(dict(snap))
    return snap


def list_primitive_index(*, limit: int = 200) -> list[dict]:
    if _backend() == "firestore":
        rows = [
            doc.to_dict()
            for doc in _get_firestore().collection(_PRIMS_COLL).stream()
            if doc.exists
        ]
    else:
        rows = [dict(r) for r in _MEM_PRIMS]
    rows.sort(key=lambda r: float(r.get("ts", 0.0)), reverse=True)
    return rows[: max(1, int(limit))]


# ---------------------------------------------------------------------------
# Domain history
# ---------------------------------------------------------------------------
def update_domain_history(user: str, run: dict) -> dict:
    """Append the run's top domain to the user's rolling history.
    Returns ``{user, domain, ts}``."""
    if not user:
        raise ValueError("user is required")
    domain = (run.get("domain_mapping") or {}).get("effective_top")
    record = {"user": user, "domain": domain, "ts": time.time(),
              "scenario_id": (run.get("output_object") or {}).get("scenario_id")}
    if _backend() == "firestore":
        coll = _get_firestore().collection(_DOMAINS_COLL)
        doc_id = f"{user}_{int(record['ts']*1000)}"
        coll.document(doc_id).set(record)
    else:
        _MEM_DOMAINS.setdefault(user, []).append(dict(record))
    return record


def list_domain_history(user: str, *, limit: int = 200) -> list[dict]:
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = _get_firestore().collection(_DOMAINS_COLL).where(
            filter=FieldFilter("user", "==", user),
        )
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = list(_MEM_DOMAINS.get(user) or [])
        rows = [dict(r) for r in rows]
    rows.sort(key=lambda r: float(r.get("ts", 0.0)), reverse=True)
    return rows[: max(1, int(limit))]


# ---------------------------------------------------------------------------
# EP baseline
# ---------------------------------------------------------------------------
def update_ep_baseline(user: str, run: dict, *, alpha: float = 0.2) -> dict:
    """Exponentially-weighted average of the EP field summary per user.
    ``alpha`` is the weight given to the new observation. Returns the
    updated baseline dict."""
    if not user:
        raise ValueError("user is required")
    ep = run.get("ep_field_summary") or {}
    new_obs = {
        "stress_total": float(ep.get("stress_total") or 0.0),
        "relief_total": float(ep.get("relief_total") or 0.0),
        "net": float(ep.get("net") or 0.0),
        "intensity_mean": float(ep.get("intensity_mean") or 0.0),
    }
    if _backend() == "firestore":
        ref = _get_firestore().collection(_BASELINE_COLL).document(user)
        existing = ref.get().to_dict() if ref.get().exists else None
    else:
        existing = _MEM_BASELINE.get(user)
    if not existing:
        existing = dict(new_obs)
        existing["sample_count"] = 1
        existing["last_ts"] = time.time()
    else:
        for k in ("stress_total", "relief_total", "net", "intensity_mean"):
            existing[k] = round(
                (1.0 - alpha) * float(existing.get(k, 0.0)) + alpha * new_obs[k],
                4,
            )
        existing["sample_count"] = int(existing.get("sample_count") or 0) + 1
        existing["last_ts"] = time.time()
    if _backend() == "firestore":
        _get_firestore().collection(_BASELINE_COLL).document(user).set(existing)
    else:
        _MEM_BASELINE[user] = dict(existing)
    return existing


def get_baseline(user: str) -> Optional[dict]:
    if _backend() == "firestore":
        ref = _get_firestore().collection(_BASELINE_COLL).document(user).get()
        return ref.to_dict() if ref.exists else None
    rec = _MEM_BASELINE.get(user)
    return dict(rec) if rec is not None else None


# ---------------------------------------------------------------------------
# v35 — Regional runs
#
# Logical layout (mirrors the spec):
#
#     elins_project/
#       regional/
#         US/2026-05-06.json
#         EU/2026-05-06.json
#         ...
#
# In memory backend, the keys are ``{region}/{date}``; in Firestore the
# document id is ``{region}_{date}``. ``save_regional_run`` is idempotent
# on day collisions (same region+date overwrites). The stored record is
# the full ELINS object plus a few derived fields for fast listing.
# ---------------------------------------------------------------------------
def _regional_doc_id(region_code: str, day: str) -> str:
    return f"{region_code}_{day}"


def _regional_mem_key(region_code: str, day: str) -> str:
    return f"{region_code}/{day}"


def save_regional_run(
    region_code: str,
    day: Optional[str],
    elins_object: dict,
) -> str:
    if region_code not in _REGIONAL_REGIONS:
        raise ValueError(f"unknown region_code {region_code!r}")
    if not isinstance(elins_object, dict) or not elins_object:
        raise ValueError("elins_object must be a non-empty dict")
    day_str = day or _today_utc()
    record = {
        "id": _regional_doc_id(region_code, day_str),
        "region_code": region_code,
        "day": day_str,
        "saved_ts": time.time(),
        "scenario_id": (elins_object.get("output_object") or {}).get("scenario_id"),
        "summary": (elins_object.get("output_object") or {}).get("summary") or {},
        "primitives": (elins_object.get("primitives") or {}).get("intensities") or {},
        "domain_top": (elins_object.get("domain_mapping") or {}).get("effective_top"),
        "external_present": bool(
            (elins_object.get("external_signals") or {}).get("present")
        ),
        "external_anchors": list(
            (elins_object.get("external_signals") or {}).get("anchors") or []
        ),
        "elins": elins_object,    # full payload for replay
        "version": (elins_object.get("output_object") or {}).get("version") or "elins.regional.v35.1",
    }
    if _backend() == "firestore":
        _get_firestore().collection(_REGIONAL_COLL).document(record["id"]).set(record)
    else:
        _MEM_REGIONAL[_regional_mem_key(region_code, day_str)] = dict(record)
    return record["id"]


def load_regional_run(region_code: str, day: Optional[str] = None) -> Optional[dict]:
    if region_code not in _REGIONAL_REGIONS:
        raise ValueError(f"unknown region_code {region_code!r}")
    day_str = day or _today_utc()
    doc_id = _regional_doc_id(region_code, day_str)
    if _backend() == "firestore":
        doc = _get_firestore().collection(_REGIONAL_COLL).document(doc_id).get()
        return doc.to_dict() if doc.exists else None
    rec = _MEM_REGIONAL.get(_regional_mem_key(region_code, day_str))
    return dict(rec) if rec is not None else None


def latest_regional_run(region_code: str) -> Optional[dict]:
    """Return the most recent saved regional run for the region, or None."""
    if region_code not in _REGIONAL_REGIONS:
        raise ValueError(f"unknown region_code {region_code!r}")
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = _get_firestore().collection(_REGIONAL_COLL).where(
            filter=FieldFilter("region_code", "==", region_code),
        )
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = [
            dict(r) for r in _MEM_REGIONAL.values()
            if r.get("region_code") == region_code
        ]
    if not rows:
        return None
    rows.sort(key=lambda r: (r.get("day") or "", float(r.get("saved_ts") or 0.0)),
              reverse=True)
    return rows[0]


def list_regional_runs(region_code: str, *, limit: int = 30) -> list[dict]:
    if region_code not in _REGIONAL_REGIONS:
        raise ValueError(f"unknown region_code {region_code!r}")
    if _backend() == "firestore":
        from google.cloud.firestore_v1 import FieldFilter  # type: ignore
        q = _get_firestore().collection(_REGIONAL_COLL).where(
            filter=FieldFilter("region_code", "==", region_code),
        )
        rows = [doc.to_dict() for doc in q.stream() if doc.exists]
    else:
        rows = [
            dict(r) for r in _MEM_REGIONAL.values()
            if r.get("region_code") == region_code
        ]
    rows.sort(key=lambda r: (r.get("day") or "", float(r.get("saved_ts") or 0.0)),
              reverse=True)
    return rows[: max(1, int(limit))]


# ---------------------------------------------------------------------------
# v36 — Macro-ELINS run log
#
# A macro run is a single scheduler tick: one global ELINS + N regional
# ELINS runs, persisted under their own keys. The macro_runs entry here
# is a thin summary that lets the founder console find the constituents.
# ---------------------------------------------------------------------------
def record_macro_run(
    *,
    ts: float,
    run_id: str,
    regions: list[str],
    global_run_ref: Optional[dict] = None,
    notes: Optional[str] = None,
    region_run_ids: Optional[dict] = None,
    external_signal_mode: Optional[str] = None,
) -> dict:
    if not run_id:
        raise ValueError("run_id is required")
    record = {
        "run_id": run_id,
        "ts": float(ts),
        "regions": list(regions or []),
        "global_run_ref": dict(global_run_ref or {}),
        "region_run_ids": dict(region_run_ids or {}),
        "external_signal_mode": external_signal_mode,
        "notes": notes,
    }
    if _backend() == "firestore":
        _get_firestore().collection(_MACRO_COLL).document(run_id).set(record)
    else:
        _MEM_MACRO[run_id] = dict(record)
    return record


def list_macro_runs(*, limit: int = 20) -> list[dict]:
    if _backend() == "firestore":
        rows = [
            doc.to_dict()
            for doc in _get_firestore().collection(_MACRO_COLL).stream()
            if doc.exists
        ]
    else:
        rows = [dict(r) for r in _MEM_MACRO.values()]
    rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    return rows[: max(1, int(limit))]


def get_macro_run(run_id: str) -> Optional[dict]:
    if not run_id:
        return None
    if _backend() == "firestore":
        doc = _get_firestore().collection(_MACRO_COLL).document(run_id).get()
        return doc.to_dict() if doc.exists else None
    rec = _MEM_MACRO.get(run_id)
    return dict(rec) if rec is not None else None


def get_macro_run_with_constituents(run_id: str) -> Optional[dict]:
    """Macro-run record + the constituent global + regional run records.
    Used by the /founder/elins/macro/run/{run_id} endpoint."""
    rec = get_macro_run(run_id)
    if rec is None:
        return None
    out = dict(rec)
    global_ref = rec.get("global_run_ref") or {}
    if global_ref.get("run_id"):
        out["global_run"] = get_run(global_ref["run_id"])
    region_ids = rec.get("region_run_ids") or {}
    regional_runs: dict[str, Optional[dict]] = {}
    for region, region_run_id in region_ids.items():
        # The regional run id is "{region}_{day}" — load via region+day.
        # We accept either id form and fall back to scanning.
        if "_" in region_run_id:
            day = region_run_id.split("_", 1)[1]
            regional_runs[region] = load_regional_run(region, day)
        else:
            regional_runs[region] = None
    out["regional_runs"] = regional_runs
    return out


# ---------------------------------------------------------------------------
# v37 — Entity graph snapshots
#
# A snapshot is one full ``elins_entity_graph`` dict, persisted alongside
# a snapshot_id (timestamp-based) so callers can load the latest or pin
# to a specific historical graph. The schema mirrors what
# elins_entity_graph emits: entities, edges, version, updated_ts.
# ---------------------------------------------------------------------------
def _entity_graph_doc_id(ts: float) -> str:
    return f"graph_{int(float(ts) * 1000)}"


def save_entity_graph(graph: dict, ts: float) -> str:
    """Persist a snapshot of the entity graph. Returns the snapshot id.
    Idempotent on collision — a second call with the same ts overwrites
    the existing snapshot."""
    if not isinstance(graph, dict):
        raise ValueError("graph must be a dict")
    if "entities" not in graph or "edges" not in graph:
        raise ValueError("graph is missing required keys")
    snap_id = _entity_graph_doc_id(ts)
    record = {
        "id": snap_id,
        "ts": float(ts),
        "graph": graph,
        "entity_count": len(graph.get("entities") or {}),
        "edge_count": len(graph.get("edges") or {}),
        "version": graph.get("version") or "entity_graph.v37.1",
    }
    if _backend() == "firestore":
        _get_firestore().collection(_ENTITY_GRAPH_COLL).document(snap_id).set(record)
    else:
        _MEM_ENTITY_GRAPH[snap_id] = dict(record)
    return snap_id


def load_latest_entity_graph() -> Optional[dict]:
    """Return the most-recent entity graph snapshot dict, or None."""
    if _backend() == "firestore":
        rows = [
            doc.to_dict()
            for doc in _get_firestore().collection(_ENTITY_GRAPH_COLL).stream()
            if doc.exists
        ]
    else:
        rows = [dict(r) for r in _MEM_ENTITY_GRAPH.values()]
    if not rows:
        return None
    rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    return dict(rows[0])


def load_entity_graph_at(ts: float) -> Optional[dict]:
    """Return the snapshot saved at ``ts`` (millisecond-resolved id),
    or None."""
    snap_id = _entity_graph_doc_id(ts)
    if _backend() == "firestore":
        doc = _get_firestore().collection(_ENTITY_GRAPH_COLL).document(snap_id).get()
        return doc.to_dict() if doc.exists else None
    rec = _MEM_ENTITY_GRAPH.get(snap_id)
    return dict(rec) if rec is not None else None


def list_entity_graph_snapshots(*, limit: int = 30) -> list[dict]:
    """Return summary records (no graph payload) for recent snapshots,
    newest first. Used by the founder console to populate a picker."""
    if _backend() == "firestore":
        rows = [
            doc.to_dict()
            for doc in _get_firestore().collection(_ENTITY_GRAPH_COLL).stream()
            if doc.exists
        ]
    else:
        rows = [dict(r) for r in _MEM_ENTITY_GRAPH.values()]
    rows.sort(key=lambda r: float(r.get("ts") or 0.0), reverse=True)
    summaries: list[dict] = []
    for r in rows[: max(1, int(limit))]:
        summaries.append({
            "id": r.get("id"),
            "ts": r.get("ts"),
            "entity_count": r.get("entity_count"),
            "edge_count": r.get("edge_count"),
            "version": r.get("version"),
        })
    return summaries


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_memory_for_tests() -> None:
    _MEM_RUNS.clear()
    _MEM_PRIMS.clear()
    _MEM_DOMAINS.clear()
    _MEM_BASELINE.clear()
    _MEM_REGIONAL.clear()
    _MEM_MACRO.clear()
    _MEM_ENTITY_GRAPH.clear()
