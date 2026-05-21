"""
acceptance_dashboard.py — /founder/acceptance/* FastAPI router.

Mounted by app.py. Founder-only by intent; the existing app.py
auth/cohort guards apply per-endpoint at runtime (the router itself
does not enforce a founder check — the existing auth middleware in
app.py is the source of truth).

Exposes:
  GET  /founder/acceptance/incidents
  POST /founder/acceptance/incidents
  POST /founder/acceptance/incidents/{id}/resolve
  GET  /founder/acceptance/onboarding_timings/{user_id}
  GET  /founder/acceptance/runs
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import incident_store

acceptance_router = APIRouter(
    prefix="/founder/acceptance",
    tags=["founder", "acceptance"],
)

# Phase 6B — separate router for /founder/analytics/* (different prefix
# from the acceptance router; mount via include_router in app.py).
analytics_router = APIRouter(
    prefix="/founder/analytics",
    tags=["founder", "analytics"],
)

# Phase 7C — separate router for /founder/telemetry (different prefix
# from both above; mount via include_router in app.py).
telemetry_router = APIRouter(
    prefix="/founder/telemetry",
    tags=["founder", "telemetry"],
)

# Phase 8B — separate router for /founder/identity. Mount via
# include_router in app.py.
identity_router = APIRouter(
    prefix="/founder/identity",
    tags=["founder", "identity"],
)

# Phase 9C — separate router for /founder/console. Mount via
# include_router in app.py.
console_router = APIRouter(
    prefix="/founder/console",
    tags=["founder", "console"],
)

# Phase 10B — separate router for /founder/surfaces. Mount via
# include_router in app.py.
surfaces_router = APIRouter(
    prefix="/founder/surfaces",
    tags=["founder", "surfaces"],
)

# Phase 11B — separate router for /founder/operator. Mount via
# include_router in app.py.
operator_router = APIRouter(
    prefix="/founder/operator",
    tags=["founder", "operator"],
)

# Phase 12B — separate router for /founder/launch. Mount via
# include_router in app.py.
launch_router = APIRouter(
    prefix="/founder/launch",
    tags=["founder", "launch"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class IncidentInput(BaseModel):
    severity: incident_store.Severity
    surface: incident_store.Surface
    title: str
    os: Optional[str] = None
    detail: Optional[str] = None
    operator_id: Optional[str] = None


class IncidentsResponse(BaseModel):
    since_hours: float
    count: int
    by_severity: dict
    open_p0_p1: int
    stability_window_pass: bool
    incidents: list


class TimingsResponse(BaseModel):
    user_id: str
    surfaces: dict
    note: str | None = None


class RunSummary(BaseModel):
    run_id: str | None
    pass_: bool | None
    finished_at: str | None
    scenarios: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@acceptance_router.get("/incidents")
def get_incidents(open_only: bool = False, since_hours: float = 72.0) -> dict:
    """List incidents. open_only filters to unresolved; since_hours
    bounds the window for the stability gate computation."""
    since_ms = int(time.time() * 1000) - int(since_hours * 3_600_000)
    rows = [
        inc for inc in incident_store.list_incidents(open_only=open_only)
        if inc.created_at >= since_ms
    ]
    by_severity = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    open_p0_p1 = 0
    for r in rows:
        by_severity[r.severity] = by_severity.get(r.severity, 0) + 1
        if r.severity in ("P0", "P1") and r.resolved_at is None:
            open_p0_p1 += 1
    stability_pass = (
        open_p0_p1 == 0
        and by_severity["P0"] == 0
        and by_severity["P1"] == 0
    )
    return {
        "since_hours": since_hours,
        "count": len(rows),
        "by_severity": by_severity,
        "open_p0_p1": open_p0_p1,
        "stability_window_pass": stability_pass,
        "incidents": [r.model_dump() for r in rows],
    }


@acceptance_router.post("/incidents")
def post_incident(body: IncidentInput) -> dict:
    inc = incident_store.create_incident(
        severity=body.severity,
        surface=body.surface,
        title=body.title,
        os_name=body.os,
        detail=body.detail,
        operator_id=body.operator_id,
    )
    return {"id": inc.id, "created_at": inc.created_at}


@acceptance_router.post("/incidents/{incident_id}/resolve")
def resolve(incident_id: str) -> dict:
    ok = incident_store.resolve_incident(incident_id)
    if not ok:
        raise HTTPException(404, "incident not found or already resolved")
    return {"resolved": True, "id": incident_id}


@acceptance_router.get("/onboarding_timings/{user_id}")
def onboarding_timings(user_id: str) -> dict:
    """Per-surface onboarding timing for `user_id`.

    The acceptance harness writes timing markers to operator_state via
    the FSM `_ts_ms` deltas. This endpoint reads them back.

    NOTE: this is a stub-shape implementation. The actual read path
    depends on whichever vault store backs operator_state; it is wired
    up here against memory_vault if available, otherwise returns an
    empty surfaces map with a note so the dashboard renders safely.
    """
    surfaces: dict = {}
    note: str | None = None
    try:
        import memory_vault  # type: ignore
        # Best-effort read of per-panel timestamps.
        for panel in range(1, 7):
            key = f"operator_state.onboarding.panel_{panel}"
            if hasattr(memory_vault, "read"):
                try:
                    rec = memory_vault.read(user_id, key)  # type: ignore
                    if isinstance(rec, dict) and "_ts_ms" in rec:
                        surfaces[f"panel_{panel}_ts_ms"] = rec["_ts_ms"]
                except Exception:
                    pass
        # Started / completed markers from state record.
        try:
            state_rec = memory_vault.read(  # type: ignore
                user_id, "operator_state.onboarding.state",
            )
            if isinstance(state_rec, dict):
                if "_ts_ms_started" in state_rec:
                    surfaces["started_ts_ms"] = state_rec["_ts_ms_started"]
                if "_ts_ms_completed" in state_rec:
                    surfaces["completed_ts_ms"] = state_rec["_ts_ms_completed"]
        except Exception:
            pass
    except ImportError:
        note = "memory_vault not importable; surfaces empty"
    if not surfaces and not note:
        note = "no timing markers recorded for this user yet"
    return {"user_id": user_id, "surfaces": surfaces, "note": note}


@acceptance_router.get("/runs")
def list_runs() -> dict:
    """Read tests/acceptance/reports/*/report.json for run summaries."""
    base = Path(os.environ.get(
        "CLARITYOS_ACCEPTANCE_REPORTS",
        "tests/acceptance/reports",
    ))
    runs: list[dict] = []
    if base.exists() and base.is_dir():
        for run_dir in sorted(base.iterdir(), reverse=True):
            rpath = run_dir / "report.json"
            if not rpath.exists():
                continue
            try:
                data = json.loads(rpath.read_text("utf-8"))
            except Exception:
                continue
            scenarios = {
                k: {
                    "pass": v.get("pass"),
                    "duration_ms": v.get("duration_ms"),
                }
                for k, v in (data.get("scenarios") or {}).items()
            }
            runs.append({
                "run_id": data.get("run_id"),
                "pass": data.get("pass"),
                "finished_at": data.get("finished_at"),
                "scenarios": scenarios,
            })
    return {"runs": runs}


# ============================================================
# Phase 3C additions — additive endpoints; do NOT modify above.
# ============================================================

def _runs_jsonl_path() -> Path:
    """Path to acceptance_runs.jsonl, written by post_run_ingest.py."""
    base = Path(os.environ.get(
        "CLARITYOS_ACCEPTANCE_REPORTS",
        "tests/acceptance/reports",
    ))
    return base / "acceptance_runs.jsonl"


def _read_runs_jsonl() -> list[dict]:
    """Read all records from acceptance_runs.jsonl. File-absence-safe.
    All file I/O wrapped in try/except per Phase 3C C1 directive."""
    path = _runs_jsonl_path()
    out: list[dict] = []
    try:
        if not path.is_file():
            return out
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        # Defensive: any I/O failure returns an empty result rather
        # than 500-ing the dashboard.
        return []
    return out


@acceptance_router.get("/runs/recent")
def runs_recent(limit: int = 10) -> dict:
    """Last N records from tests/acceptance/reports/acceptance_runs.jsonl.

    The JSONL file is written by post_run_ingest.py; if no runs have
    been ingested yet, this returns an empty list with note=null. The
    file path is overridable via CLARITYOS_ACCEPTANCE_REPORTS.
    """
    if limit < 1:
        limit = 1
    if limit > 100:
        limit = 100
    records = _read_runs_jsonl()
    recent = records[-limit:][::-1]  # newest first
    return {
        "limit": limit,
        "count": len(recent),
        "available_total": len(records),
        "runs": recent,
        "note": (
            "no acceptance_runs.jsonl yet — run post_run_ingest.py at least once"
            if not records else None
        ),
    }


# ============================================================
# Phase 6B — Founder analytics router endpoints.
# ============================================================

@analytics_router.get("/quality")
def analytics_quality() -> dict:
    """Phase 6B — run-quality scoring summary.

    Loads acceptance_runs.jsonl, calls run_quality.score_series, and
    returns the scored series. File-absence-safe per Phase 3C C1.
    """
    try:
        records = _read_runs_jsonl()
    except Exception:
        records = []
    try:
        import run_quality  # repo-root module per Phase 1 adaptation
        return run_quality.score_series(records)
    except Exception as exc:
        return {
            "n_runs": 0,
            "scores": [],
            "summary": {
                "mean": None, "median": None, "latest": None,
                "trend": "error",
                "n_healthy": 0, "n_warning": 0, "n_critical_fail": 0,
            },
            "error": f"{type(exc).__name__}: {exc}",
        }


@analytics_router.get("/cadence")
def analytics_cadence() -> dict:
    """Phase 6C — run cadence + irregularities."""
    try:
        records = _read_runs_jsonl()
    except Exception:
        records = []
    try:
        import cadence_math
        return {
            "cadence": cadence_math.compute_cadence(records),
            "irregularities": cadence_math.detect_irregularities(records),
        }
    except Exception as exc:
        return {
            "cadence": {
                "n_runs": 0, "n_gaps": 0,
                "avg_spacing_minutes": None,
                "median_spacing_minutes": None,
                "longest_gap_minutes": None,
                "shortest_gap_minutes": None,
                "stddev_minutes": None,
                "coefficient_of_variation": None,
                "classification": "error",
            },
            "irregularities": {
                "n_gaps": 0, "outlier_gaps": [],
                "cluster_count": 0, "classification": "error",
            },
            "error": f"{type(exc).__name__}: {exc}",
        }


# ============================================================
# Phase 7C — Founder telemetry router endpoint.
# ============================================================

# ============================================================
# Phase 8B — Founder identity router endpoint.
# ============================================================

@identity_router.get("")
@identity_router.get("/")
def founder_identity() -> dict:
    """Phase 8B — descriptive identity coherence layer.

    Reads acceptance_runs.jsonl, groups by `surface` if records carry
    that field (today's records do not, so all land in "global"),
    and runs the identity_engine math on both the global view and the
    per-surface view. Returns `{profile, surfaces}`.
    """
    try:
        records = _read_runs_jsonl()
    except Exception:
        records = []
    try:
        import identity_engine
        # Global profile (every record).
        profile = identity_engine.compute_identity_profile(records)
        # Group by `surface` field if present. Records without the
        # field land in the "global" bucket. Today this means every
        # record → "global" — see identity_coherence.md "today's data
        # caveat".
        groups: dict[str, list[dict]] = {}
        for r in records:
            if not isinstance(r, dict):
                continue
            key = r.get("surface")
            if not isinstance(key, str) or not key:
                key = "global"
            groups.setdefault(key, []).append(r)
        surfaces = identity_engine.compare_surfaces(groups)
        return {
            "profile": profile,
            "surfaces": surfaces,
        }
    except Exception as exc:
        return {
            "profile": {},
            "surfaces": {},
            "error": f"{type(exc).__name__}: {exc}",
        }


# ============================================================
# Phase 13B — PIS / PISS dual-surface taxonomy endpoint.
# Read-only descriptive view per
# tests/acceptance/pis_piss_identity.md. Mounted on the existing
# identity_router (Phase 8B) so the URL is /founder/identity/pis-piss
# without introducing a parallel router.
# ============================================================

@identity_router.get("/pis-piss")
def founder_identity_pis_piss() -> dict:
    """Phase 13B — PIS / PISS taxonomic layer.

    Calls pis_piss_identity.summarize_pis_piss and returns the
    combined { pis, piss, relationship, notes } payload consumed by
    FounderPisPiss.tsx. Takes no records — the layer is purely
    taxonomic.

    All module calls wrapped in try/except per Phase 3C C1.
    """
    payload: dict = {}
    errors: dict = {}
    try:
        import pis_piss_identity  # repo-root module per Phase 1 adaptation
        payload = pis_piss_identity.summarize_pis_piss()
    except Exception as exc:
        errors["pis_piss_identity_error"] = f"{type(exc).__name__}: {exc}"
        payload = {
            "pis":          {},
            "piss":         {},
            "relationship": {},
            "notes":        ["module load failure"],
        }
    if errors:
        payload["errors"] = errors
    return payload


# ============================================================
# Phase 14B — category-definition + external-language endpoint.
# Read-only descriptive view per
# tests/acceptance/category_definition.md. Mounted on the existing
# identity_router (Phase 8B) so the URL is /founder/identity/category
# without introducing a parallel router.
# ============================================================

@identity_router.get("/category")
def founder_identity_category() -> dict:
    """Phase 14B — Inferential Discipline System category layer.

    Calls category_definition.summarize_category and returns the
    combined { category, example_statements, external_language, notes }
    payload consumed by FounderCategory.tsx. Takes no records — the
    layer is purely taxonomic.

    All module calls wrapped in try/except per Phase 3C C1.
    """
    payload: dict = {}
    errors: dict = {}
    try:
        import category_definition  # repo-root module per Phase 1 adaptation
        payload = category_definition.summarize_category()
    except Exception as exc:
        errors["category_definition_error"] = f"{type(exc).__name__}: {exc}"
        payload = {
            "category":           {},
            "example_statements": [],
            "external_language":  {"allowed": [], "disallowed": []},
            "notes":               ["module load failure"],
        }
    if errors:
        payload["errors"] = errors
    return payload


# ============================================================
# Phase 9C — Founder console summary endpoint (compact fan-out).
# ============================================================

@console_router.get("/summary")
def founder_console_summary() -> dict:
    """Phase 9C — compact summary widget for the founder console.

    Internal fan-out across existing math modules. Returns:
      last_run_at, last_quality_score, last_trust_level,
      last_identity_score
    All file/module access wrapped in try/except per Phase 3C C1.
    """
    try:
        records = _read_runs_jsonl()
    except Exception:
        return {
            "summary": {
                "last_run_at": None,
                "last_quality_score": None,
                "last_trust_level": None,
                "last_identity_score": None,
                "n_runs": 0,
            },
            "error": "could not read acceptance_runs.jsonl",
        }

    summary: dict = {
        "last_run_at": None,
        "last_quality_score": None,
        "last_trust_level": None,
        "last_identity_score": None,
        "n_runs": len(records),
    }

    # Last run timestamp (newest record).
    if records:
        last = records[-1]
        if isinstance(last, dict):
            summary["last_run_at"] = (
                last.get("finished_at") or last.get("started_at")
            )

    # Last quality score
    try:
        import run_quality
        qs = run_quality.score_series(records)
        scores = qs.get("scores") or []
        if scores and isinstance(scores[-1], dict):
            summary["last_quality_score"] = scores[-1].get("score")
    except Exception:
        pass

    # Last trust level
    try:
        import trust_center_math
        ts = trust_center_math.compute_trust_signal(records)
        summary["last_trust_level"] = ts.get("level")
        summary["last_trust_score"] = ts.get("signal_score")
    except Exception:
        pass

    # Last identity score
    try:
        import identity_engine
        ip = identity_engine.compute_identity_profile(records)
        summary["last_identity_score"] = ip.get("score")
    except Exception:
        pass

    return {"summary": summary}


# ============================================================
# Original telemetry router endpoint follows.
# ============================================================

@telemetry_router.get("")
@telemetry_router.get("/")
def founder_telemetry() -> dict:
    """Phase 7C — combined trust-center + narrative-drift payload.

    Loads the records once and runs both math layers in series. Each
    sub-call wrapped in try/except so a failure in one does not 500
    the entire endpoint.
    """
    try:
        records = _read_runs_jsonl()
    except Exception:
        records = []
    payload: dict = {}
    try:
        import trust_center_math
        payload["trust_signal"] = trust_center_math.compute_trust_signal(records)
        payload["alignment"]    = trust_center_math.compute_alignment(records)
        payload["warnings"]     = trust_center_math.compute_warning_levels(records)
    except Exception as exc:
        payload["trust_center_error"] = f"{type(exc).__name__}: {exc}"
        payload.setdefault("trust_signal", {})
        payload.setdefault("alignment", {})
        payload.setdefault("warnings", {})
    try:
        import narrative_drift
        payload["drift"]       = narrative_drift.detect_drift(records)
        payload["drift_score"] = narrative_drift.drift_score(records)
    except Exception as exc:
        payload["narrative_drift_error"] = f"{type(exc).__name__}: {exc}"
        payload.setdefault("drift", {})
        payload.setdefault("drift_score", 0.0)
    return payload


# ============================================================
# Original acceptance router endpoints continue below.
# ============================================================

@acceptance_router.get("/stability/curve")
def stability_curve() -> dict:
    """Phase 5C — longitudinal stability projection.

    Reads acceptance_runs.jsonl (try/except per Phase 3C C1 directive)
    and runs it through the three pure functions in stability_math.py:
    compute_stability_curve, compute_timing_drift, compute_surface_health.
    Returns the combined payload consumed by FounderAcceptanceCurve.tsx.
    """
    try:
        records = _read_runs_jsonl()
    except Exception:
        records = []
    try:
        import stability_math  # repo-root module per Phase 1 adaptation
        curve = stability_math.compute_stability_curve(records)
        drift = stability_math.compute_timing_drift(records)
        health = stability_math.compute_surface_health(records)
    except Exception as exc:
        # Defensive: any unexpected failure returns an empty payload
        # rather than 500-ing the dashboard.
        return {
            "curve": {"n_runs": 0, "n_with_stability": 0, "points": [], "summary": {}},
            "drift": {"n_runs_with_timing": 0, "interpretation": "insufficient data"},
            "surface_health": {"n_runs_examined": 0, "scenario_health": {}, "surface_proxy_note": ""},
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "curve": curve,
        "drift": drift,
        "surface_health": health,
    }


@acceptance_router.get("/stability")
def stability_aggregate() -> dict:
    """Aggregated stability metrics across all ingested runs.

    Reads acceptance_runs.jsonl, pulls each record's `stability` block
    (populated by post_run_ingest.py from scenario 05 details), and
    returns aggregate statistics. Returns empty defaults on file
    absence rather than erroring.
    """
    records = _read_runs_jsonl()
    stability_records = [
        r.get("stability") for r in records
        if isinstance(r.get("stability"), dict)
    ]
    if not stability_records:
        return {
            "runs_with_stability": 0,
            "monotonicity_pass_count": 0,
            "monotonicity_fail_count": 0,
            "iteration_mean_ms_avg": None,
            "iteration_max_ms_max": None,
            "iteration_stddev_ms_avg": None,
            "note": (
                "no stability data yet — scenario 05 must run + ingest at least once"
            ),
        }
    monotonicity_pass = sum(
        1 for s in stability_records if s.get("monotonicity_pass") is True
    )
    monotonicity_fail = sum(
        1 for s in stability_records if s.get("monotonicity_pass") is False
    )
    means = [s.get("mean_ms") for s in stability_records if isinstance(s.get("mean_ms"), (int, float))]
    maxes = [s.get("max_ms") for s in stability_records if isinstance(s.get("max_ms"), (int, float))]
    stddevs = [s.get("stddev_ms") for s in stability_records if isinstance(s.get("stddev_ms"), (int, float))]
    return {
        "runs_with_stability": len(stability_records),
        "monotonicity_pass_count": monotonicity_pass,
        "monotonicity_fail_count": monotonicity_fail,
        "iteration_mean_ms_avg": (sum(means) / len(means)) if means else None,
        "iteration_max_ms_max":  max(maxes) if maxes else None,
        "iteration_stddev_ms_avg": (sum(stddevs) / len(stddevs)) if stddevs else None,
        "note": None,
    }


# ============================================================
# Phase 10B — surfaces unification endpoint.
# Read-only descriptive view per tests/acceptance/surfaces_unification.md.
# ============================================================

@surfaces_router.get("/unified")
def surfaces_unified() -> dict:
    """Phase 10B — unified surfaces view.

    Reads acceptance_runs.jsonl, calls
    surfaces_unification.summarize_surfaces and .compute_surface_coherence,
    and returns the combined payload consumed by FounderSurfaces.tsx.

    All file I/O + module calls wrapped in try/except per Phase 3C C1.
    """
    payload: dict = {}
    errors: dict = {}
    try:
        records = _read_runs_jsonl()
    except Exception as exc:
        records = []
        errors["jsonl_read_error"] = f"{type(exc).__name__}: {exc}"
    try:
        import surfaces_unification  # repo-root module per Phase 1 adaptation
        payload["surfaces"]  = surfaces_unification.summarize_surfaces(records)
        payload["coherence"] = surfaces_unification.compute_surface_coherence(records)
    except Exception as exc:
        errors["surfaces_unification_error"] = f"{type(exc).__name__}: {exc}"
        payload.setdefault("surfaces", {
            "declared": ["PHONE", "WEB", "OPERATOR"],
            "present": [],
            "counts": {"PHONE": 0, "WEB": 0, "OPERATOR": 0, "unknown": 0},
            "last_runs": {"PHONE": None, "WEB": None, "OPERATOR": None},
            "n_records": 0,
        })
        payload.setdefault("coherence", {
            "coherence_score": 0,
            "components": {
                "timing_delta_score": 0,
                "trust_delta_score": 0,
                "identity_delta_score": 0,
            },
            "deltas": {},
            "interpretation": "compute failure (returned neutral)",
        })
    if errors:
        payload["errors"] = errors
    return payload


# ============================================================
# Phase 11B — operator-mode state endpoint.
# Read-only descriptive view per tests/acceptance/operator_mode.md.
# ============================================================

@operator_router.get("/state")
def operator_state() -> dict:
    """Phase 11B — operator posture state.

    Reads acceptance_runs.jsonl, calls
    operator_mode.summarize_operator_state, and returns the result
    consumed by FounderOperator.tsx.

    All file I/O + module calls wrapped in try/except per Phase 3C C1.
    """
    payload: dict = {}
    errors: dict = {}
    try:
        records = _read_runs_jsonl()
    except Exception as exc:
        records = []
        errors["jsonl_read_error"] = f"{type(exc).__name__}: {exc}"
    try:
        import operator_mode  # repo-root module per Phase 1 adaptation
        payload["state"] = operator_mode.summarize_operator_state(records)
    except Exception as exc:
        errors["operator_mode_error"] = f"{type(exc).__name__}: {exc}"
        payload["state"] = {
            "last_run":      None,
            "last_quality":  None,
            "last_trust":    None,
            "last_identity": None,
            "stale":         True,
            "posture":       "offline",
            "reasons":       ["module load failure"],
            "votes":         {"telemetry": "offline", "identity": "offline", "quality": "offline"},
        }
    if errors:
        payload["errors"] = errors
    return payload


# ============================================================
# Phase 12B — launch readiness endpoint.
# Read-only descriptive view per tests/acceptance/launch_readiness.md.
# ============================================================

@launch_router.get("/readiness")
def launch_readiness_state() -> dict:
    """Phase 12B — public launch readiness.

    Reads acceptance_runs.jsonl, calls
    launch_readiness.summarize_launch_readiness, and returns the
    composed payload consumed by FounderLaunch.tsx.

    All file I/O + module calls wrapped in try/except per Phase 3C C1.
    """
    payload: dict = {}
    errors: dict = {}
    try:
        records = _read_runs_jsonl()
    except Exception as exc:
        records = []
        errors["jsonl_read_error"] = f"{type(exc).__name__}: {exc}"
    try:
        import launch_readiness  # repo-root module per Phase 1 adaptation
        payload["readiness"] = launch_readiness.summarize_launch_readiness(records)
    except Exception as exc:
        errors["launch_readiness_error"] = f"{type(exc).__name__}: {exc}"
        payload["readiness"] = {
            "readiness": {
                "readiness_score": 0,
                "band": "red",
                "dimensions": {
                    "stability": 0.0, "trust": 0.0, "identity": 0.0,
                    "surfaces":  0.0, "operator": 0.0,
                },
                "weights": {
                    "stability": 0.20, "trust": 0.20, "identity": 0.20,
                    "surfaces":  0.20, "operator": 0.20,
                },
                "notes": ["module load failure"],
            },
            "last_run": None,
        }
    if errors:
        payload["errors"] = errors
    return payload
