"""
v40 — Intelligence Kernel v1.0.

Single coherent entry point that unifies #c, #G, ELINS, ESO,
operator_state, and the macro scheduler into one module. Endpoints in
``app.py`` and the macro scheduler in ``elins_scheduler`` route through
this kernel; ESO resolution, operator_state recording, S_ELINS QC, and
ELINS persistence happen here in one place.

Public API:
    KERNEL_VERSION

    run_c(user, input, *, mode="default", external_signal_mode=None) -> dict
    run_G(user, input, *, runner, mode="default", external_signal_mode=None) -> dict
    run_ELINS(user, text, *, region=None, external_signal_mode=None,
              domain_hint=None, kind=None, topic_hint=None,
              persist=True, update_indexes=True) -> dict
    run_regional_ELINS(user, region_code, *, topic_hint=None,
                       external_signal_mode=None, persist=True) -> dict
    run_macro_ELINS(system_user, *, now_ts=None,
                    external_signal_mode=None) -> dict

    kernel_status() -> dict
    kernel_view_for_user(user_id) -> dict      # /me embed

Each ``run_*`` is deterministic with respect to the persistence layer
state at call time. ``run_G`` accepts a ``runner`` callable so the
heavyweight #G analyser (lives in app.py to avoid circular imports)
can be injected without the kernel needing a back-import.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from ELINS import (
    elins_project,
    elins_v2_view,                 # v53 — Path-C view adapter for ELINS v2
    forecast_engine,
    ingestion_bus,                 # v54 — RSS/Atom + manual ingestion
    regional_elins,
    standard_elins,
)
import comment_generator
import directive_engine             # A21/A28 — unified directive engine
import elins_entity_graph
import elins_scheduler_config
import kernel_logging
import local_model_runtime           # v45 — on-device inference runtime
import memory_vault                  # v46 — encrypted local KV store
import model_router
import operator_state
import perplexity_oracle
import problem_solver                # v79 — ProblemSolver.REGRESSION_FIRST kernel task
import projects_vault                # v51 — project layer
import runtime_privacy               # PASS-4 FIX-P5 — log redaction helpers
import threads_vault                 # v47 — threaded interaction substrate
import users_store

logger = logging.getLogger("clarityos.intelligence_kernel")

KERNEL_VERSION: str = "kernel.v1.0"
VALID_SIGNAL_MODES: tuple = operator_state.VALID_SIGNAL_MODES


# ---------------------------------------------------------------------------
# Internal helpers — ESO resolution + operator state mirror
# ---------------------------------------------------------------------------
def _resolve_external_signal_mode(
    user: Optional[str],
    override: Optional[str],
) -> str:
    """Resolve the effective ESO mode for a call.

    Precedence:
        1. explicit override (must be in VALID_SIGNAL_MODES)
        2. ``users_store.get_user(user).external_signal_mode``
        3. ``operator_state.get_operator_state(user).external_signal_mode``
        4. fallback ``"cloud_only"``
    """
    if isinstance(override, str) and override in VALID_SIGNAL_MODES:
        return override
    if user:
        user_doc = users_store.get_user(user) or {}
        u_mode = user_doc.get("external_signal_mode")
        if u_mode in VALID_SIGNAL_MODES:
            return u_mode
        try:
            state = operator_state.get_operator_state(user)
            s_mode = (state or {}).get("external_signal_mode")
            if s_mode in VALID_SIGNAL_MODES:
                return s_mode
        except Exception:  # pragma: no cover (defensive)
            pass
    return "cloud_only"


def _maybe_fetch_eso(
    mode: str,
    *,
    region_code: Optional[str] = None,
    user: Optional[str] = None,
) -> Optional[dict]:
    """Pull + sanitise an ESO when the resolved mode says so.

    Contract:
        * mode != "cloud_perplexity" → return None (no oracle call)
        * unknown region → return None (no oracle call)
        * oracle raises (timeout, HTTP, JSON, etc.) → log + return None
        * success → return the sanitised ESO with an explicit
          ``source`` tag in {"mock", "perplexity"}
    """
    if mode != "cloud_perplexity":
        return None
    if not region_code:
        return None
    try:
        eso = perplexity_oracle.fetch_basin_signals(region_code, user=user)
    except ValueError:
        # Unknown region — bubble back to caller as a "no ESO" outcome.
        return None
    except Exception as e:
        # Any other oracle failure (HTTP, JSON, RuntimeError) is a
        # graceful degradation: log + record + continue without ESO.
        try:
            perplexity_oracle._record_error(str(e))
        except Exception:  # pragma: no cover (defensive)
            pass
        logger.warning(
            "kernel ESO fetch failed region=%s err=%s", region_code, e,
        )
        return None
    if eso is None:
        return None
    # Sanitise BEFORE handing to ELINS / #G — strips HTML, drops
    # body-style fields, truncates long strings.
    eso = perplexity_oracle.sanitize_eso(eso) or {}
    if not eso.get("source"):
        eso["source"] = "mock" if eso.get("mock") else "perplexity"
    return eso


def _eso_source(mode: str, eso: Optional[dict]) -> str:
    """Resolve the public ``eso_source`` tag for a single run."""
    if mode != "cloud_perplexity":
        return "none"
    if not eso:
        return "none"
    src = eso.get("source")
    if src in ("mock", "perplexity"):
        return src
    return "mock" if eso.get("mock") else "perplexity"


def _apply_signal_mode_override(
    user: Optional[str], override: Optional[str],
) -> None:
    """Persist a per-call override onto operator_state + mirror onto
    users_store so the regional ESO resolver picks it up immediately.
    No-op when override is None or invalid."""
    if not user or not override:
        return
    if override not in VALID_SIGNAL_MODES:
        return
    try:
        operator_state.set_external_signal_mode(user, override)
    except Exception:  # pragma: no cover (defensive)
        return
    try:
        users_store.update_user(user, {"external_signal_mode": override})
    except Exception:  # pragma: no cover (defensive)
        pass


# ---------------------------------------------------------------------------
# Internal helper — model selection wrapper
# ---------------------------------------------------------------------------
def _resolve_model(
    user: Optional[str],
    *,
    task: str,
    override: Optional[str] = None,
) -> str:
    """Thin wrapper around model_router.select_model that records the
    chosen model_id onto operator_state.last_model_used (when a user
    is given). Returns the resolved model_id.

    v45: when the resolved model is the local on-device id, the per-user
    ``local_model_usage_count`` is bumped via ``operator_state.bump_local_model_usage``.
    """
    try:
        model_id = model_router.select_model(user, task=task, override=override)
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("model_router.select_model failed err=%s", e)
        # Fall back to the deterministic ELINS default so the kernel
        # never bubbles a router exception up to the request path.
        model_id = model_router.TASK_DEFAULTS.get("ELINS")
    if user and isinstance(model_id, str):
        try:
            operator_state.record_model_used(user, model_id)
        except Exception:  # pragma: no cover (defensive)
            pass
        if model_id == model_router.LOCAL_MODEL_ID:
            try:
                operator_state.bump_local_model_usage(user)
            except Exception:  # pragma: no cover (defensive)
                pass
    return model_id


# ---------------------------------------------------------------------------
# Internal helper — S_ELINS QC attached to an ELINS object
# ---------------------------------------------------------------------------
def _run_s_elins_qc(elins_obj: dict) -> Optional[dict]:
    """Run S_ELINS over the just-built ELINS object. Returns the QC dict
    on success; logs + returns None on failure (caller continues with
    persistence regardless)."""
    try:
        return standard_elins.generate_S_ELINS(elins_obj)
    except Exception as e:
        logger.warning("kernel S_ELINS QC failed err=%s", e)
        return None


# ---------------------------------------------------------------------------
# Internal helper — global scenario scaffold (used by run_macro_ELINS)
# ---------------------------------------------------------------------------
def _global_scenario_text() -> str:
    return (
        "Global system pressure is rising across institutions; trust between "
        "partners is uneven and tension is sustained across major basins. "
        "Drift in posture and contradiction in policy persist."
    )


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _make_macro_run_id(now: float, seq: Optional[int] = None) -> str:
    if seq is None:
        return f"macro_{int(now * 1000)}"
    return f"macro_{int(now * 1000)}_{seq}"


# ---------------------------------------------------------------------------
# Public — run_c (#c cloud engine)
# ---------------------------------------------------------------------------
def run_c(
    user: str,
    input: str,
    *,
    mode: str = "default",
    external_signal_mode: Optional[str] = None,
) -> dict:
    """#c entry point. Today the only routed mode is ``"comment"``
    (mode="default" resolves to "comment"). The kernel applies any
    ESO-mode override (persisted onto operator_state + users_store) but
    the comment generator itself is purely lexical, so the override has
    no effect on the returned content."""
    actual_mode = mode if mode and mode != "default" else "comment"
    if actual_mode != "comment":
        raise ValueError(f"unsupported mode {actual_mode!r}")
    started = time.perf_counter()
    _apply_signal_mode_override(user, external_signal_mode)
    resolved_mode = _resolve_external_signal_mode(user, external_signal_mode)
    model_id = _resolve_model(user, task="c")
    ok = False
    err: Optional[str] = None
    try:
        result = comment_generator.generate_comment(input)
        ok = True
        return {
            "ok": True, "mode": actual_mode, "result": result,
            "model_id": model_id,
        }
    except Exception as e:
        err = str(e)
        raise
    finally:
        kernel_logging.log_kernel_run(
            kind="run_c",
            user_id=user,
            external_signal_mode=resolved_mode,
            eso_source="none",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            ok=ok,
            error=err,
            meta={"mode": actual_mode, "model_id": model_id},
        )


# ---------------------------------------------------------------------------
# Public — run_G (#G analyser wrapper)
# ---------------------------------------------------------------------------
def run_G(
    user: str,
    input: str,
    *,
    runner: Callable[[str, str], dict],
    mode: str = "default",
    external_signal_mode: Optional[str] = None,
) -> dict:
    """Wrap a #G runner with kernel pre/post handling.

    ``runner`` is the heavyweight #G analyser (currently ``_run_g_elins``
    in ``app.py``). Pre-call: persist any ESO mode override. Post-call:
    record a metadata-only #G run on operator_state.
    """
    started = time.perf_counter()
    _apply_signal_mode_override(user, external_signal_mode)
    resolved_mode = _resolve_external_signal_mode(user, external_signal_mode)
    model_id = _resolve_model(user, task="G")
    ok = False
    err: Optional[str] = None
    pressure_meta: Optional[float] = None
    try:
        result = runner(input, user)
        ok = bool(result.get("ok"))
        if ok:
            try:
                analysis = result.get("analysis") or {}
                qc_summary = analysis.get("qc_summary") or {}
                pressure_meta = float(qc_summary.get("pressure") or 0.0)
                topic_label = f"#G · pressure {round(pressure_meta, 3)}"
                operator_state.record_g_run(
                    user, str(analysis.get("persisted_membership_id") or ""),
                    context={"mode": "G", "topic": topic_label},
                )
            except Exception as e:  # pragma: no cover (defensive)
                logger.warning(
                    "kernel run_G operator_state record failed err=%s", e,
                )
        else:
            err = str(result.get("error") or "")
        if isinstance(result, dict):
            result.setdefault("model_id", model_id)
        return result
    except Exception as e:
        err = str(e)
        raise
    finally:
        meta: dict = {"model_id": model_id}
        if pressure_meta is not None:
            meta["pressure"] = pressure_meta
        kernel_logging.log_kernel_run(
            kind="run_G",
            user_id=user,
            external_signal_mode=resolved_mode,
            # #G doesn't currently consume ESO; tag as "none" so the
            # logging contract stays consistent with the run shape.
            eso_source="none",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            ok=ok,
            error=err,
            meta=meta,
        )


# ---------------------------------------------------------------------------
# Public — run_ELINS (canonical pipeline + S_ELINS + persist)
# ---------------------------------------------------------------------------
def run_ELINS(
    user: str,
    text: str,
    *,
    region: Optional[str] = None,
    external_signal_mode: Optional[str] = None,
    domain_hint: Optional[str] = None,
    kind: Optional[str] = None,
    topic_hint: Optional[str] = None,
    persist: bool = True,
    update_indexes: bool = True,
) -> dict:
    """Canonical ELINS run.

    If ``region`` is given, delegates to :func:`run_regional_ELINS`.
    Otherwise runs the canonical 10-layer pipeline on ``text``, attaches
    an S_ELINS QC block, and (when ``persist=True``) saves the run via
    ``elins_project.save_daily_run`` + the index helpers.

    Returns ``{"elins", "run_id", "qc", "baseline"}``. ``run_id`` is
    None when persist=False.
    """
    if region is not None:
        return run_regional_ELINS(
            user, region, topic_hint=text,
            external_signal_mode=external_signal_mode,
            persist=persist,
        )
    started = time.perf_counter()
    _apply_signal_mode_override(user, external_signal_mode)
    resolved_mode = _resolve_external_signal_mode(user, external_signal_mode)
    model_id = _resolve_model(user, task="ELINS")
    ok = False
    err: Optional[str] = None
    ep_mean: Optional[float] = None
    try:
        elins_obj = standard_elins.generate_ELINS(
            text, domain_hint=domain_hint, user=user,
        )
        qc = _run_s_elins_qc(elins_obj)
        if qc is not None:
            elins_obj["qc"] = qc

        run_id: Optional[str] = None
        baseline: Optional[dict] = None
        if persist:
            try:
                run_id = elins_project.save_daily_run(user, elins_obj)
            except Exception as e:
                logger.warning(
                    "kernel save_daily_run failed user=%s err=%s",
                    runtime_privacy.user_ref(user), e,
                )
            if update_indexes:
                try:
                    elins_project.update_global_primitive_index(elins_obj)
                    elins_project.update_domain_history(user, elins_obj)
                    baseline = elins_project.update_ep_baseline(user, elins_obj)
                except Exception as e:  # pragma: no cover (defensive)
                    logger.warning(
                        "kernel update_indexes failed user=%s err=%s",
                        runtime_privacy.user_ref(user), e,
                    )

        # operator_state — analysis-derived topic so raw text never leaks.
        try:
            syn = elins_obj.get("synthesis") or {}
            domain = (elins_obj.get("domain_mapping") or {}).get("effective_top")
            topic_label = " · ".join(x for x in (syn.get("top_primitive"), domain) if x)
            record_id = run_id or (
                (elins_obj.get("output_object") or {}).get("scenario_id") or ""
            )
            operator_state.record_elins_interaction(
                user, record_id,
                context={
                    "topic": topic_label,
                    "region": None,
                    "kind": kind or ("global" if persist else "preview"),
                    "domain": domain,
                },
            )
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning("kernel run_ELINS operator_state record failed err=%s", e)

        ep = elins_obj.get("ep_field_summary") or {}
        try:
            ep_mean = float(ep.get("intensity_mean") or 0.0)
        except (TypeError, ValueError):
            ep_mean = None
        ok = True
        return {
            "ok": True,
            "elins": elins_obj,
            "run_id": run_id,
            "qc": qc,
            "baseline": baseline,
            "model_id": model_id,
        }
    except Exception as e:
        err = str(e)
        raise
    finally:
        kernel_logging.log_kernel_run(
            kind="run_ELINS",
            user_id=user,
            external_signal_mode=resolved_mode,
            eso_source="none",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            ok=ok,
            error=err,
            meta={
                "kind": kind or ("global" if persist else "preview"),
                "ep_mean": ep_mean,
                "has_eso": False,
                "persist": persist,
                "model_id": model_id,
            },
        )


# ---------------------------------------------------------------------------
# Public — run_regional_ELINS
# ---------------------------------------------------------------------------
def run_regional_ELINS(
    user: str,
    region_code: str,
    *,
    topic_hint: Optional[str] = None,
    external_signal_mode: Optional[str] = None,
    persist: bool = True,
) -> dict:
    """Region-aware ELINS run: resolves ESO via the kernel, runs the
    regional pipeline, attaches S_ELINS QC, persists, and records an
    operator_state interaction."""
    started = time.perf_counter()
    _apply_signal_mode_override(user, external_signal_mode)
    mode = _resolve_external_signal_mode(user, external_signal_mode)
    eso = _maybe_fetch_eso(mode, region_code=region_code, user=user)
    eso_source_tag = _eso_source(mode, eso)
    model_id = _resolve_model(user, task="regional")
    ok = False
    err: Optional[str] = None
    ep_mean: Optional[float] = None
    try:
        previous = elins_project.latest_regional_run(region_code)
        previous_elins = (previous or {}).get("elins") if previous else None

        elins_obj = regional_elins.run_regional_elins(
            region_code, user=user,
            topic_hint=topic_hint, eso=eso, previous_run=previous_elins,
        )
        qc = _run_s_elins_qc(elins_obj)
        if qc is not None:
            elins_obj["qc"] = qc

        run_id: Optional[str] = None
        if persist:
            try:
                run_id = elins_project.save_regional_run(region_code, None, elins_obj)
            except Exception as e:
                logger.warning(
                    "kernel save_regional_run failed region=%s err=%s",
                    region_code, e,
                )

        try:
            domain = (elins_obj.get("domain_mapping") or {}).get("effective_top")
            operator_state.record_elins_interaction(
                user, run_id or "",
                context={
                    "topic": (topic_hint or "")[:80],
                    "region": region_code, "kind": "regional",
                    "domain": domain,
                },
            )
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning(
                "kernel run_regional_ELINS operator_state record failed err=%s", e,
            )

        ep = elins_obj.get("ep_field_summary") or {}
        try:
            ep_mean = float(ep.get("intensity_mean") or 0.0)
        except (TypeError, ValueError):
            ep_mean = None
        ok = True
        return {
            "ok": True,
            "elins": elins_obj,
            "run_id": run_id,
            "region_code": region_code,
            "eso_present": bool(eso),
            "eso_source": eso_source_tag,
            "qc": qc,
            "model_id": model_id,
        }
    except Exception as e:
        err = str(e)
        raise
    finally:
        kernel_logging.log_kernel_run(
            kind="run_regional_ELINS",
            user_id=user,
            external_signal_mode=mode,
            eso_source=eso_source_tag,
            duration_ms=(time.perf_counter() - started) * 1000.0,
            ok=ok,
            error=err,
            meta={
                "region": region_code,
                "ep_mean": ep_mean,
                "has_eso": bool(eso),
                "model_id": model_id,
            },
        )


# ---------------------------------------------------------------------------
# Public — run_macro_ELINS (one full macro pass)
# ---------------------------------------------------------------------------
def run_macro_ELINS(
    system_user: str,
    *,
    now_ts: Optional[float] = None,
    external_signal_mode: Optional[str] = None,
) -> dict:
    """One macro-ELINS pass: global ELINS + every regional ELINS +
    macro-run summary + entity-graph merge. No cadence gating — the
    scheduler is responsible for that. Always runs the full pass.

    The ``run_id`` format uses a short per-process counter to avoid
    collisions when two passes land in the same millisecond.
    """
    started = time.perf_counter()
    now = float(now_ts if now_ts is not None else time.time())
    if external_signal_mode is None:
        cfg = elins_scheduler_config.get_config() or {}
        external_signal_mode = cfg.get("external_signal_mode") or "cloud_only"
    macro_model_id = _resolve_model(system_user, task="macro")

    # Global ELINS via the kernel's run_ELINS — picks up S_ELINS + persistence.
    global_result = run_ELINS(
        system_user, _global_scenario_text(),
        domain_hint=None, kind="macro_global",
        external_signal_mode=external_signal_mode,
        persist=True, update_indexes=True,
    )
    global_obj = global_result["elins"]
    global_run_id = global_result.get("run_id")

    day_str = _today_utc()
    pass_runs: list[dict] = [global_obj]
    regions_done: list[str] = []
    region_run_ids: dict[str, str] = {}

    for region in regional_elins.REGION_CODES:
        try:
            rr = run_regional_ELINS(
                system_user, region,
                topic_hint=None,
                external_signal_mode=external_signal_mode,
                persist=True,
            )
            rid = rr.get("run_id")
            if rid:
                region_run_ids[region] = rid
            regions_done.append(region)
            pass_runs.append(rr["elins"])
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning(
                "kernel macro region run failed region=%s err=%s", region, e,
            )

    # Macro-run record. Use a unique-per-call id (counter prevents collisions).
    seq = _next_macro_seq()
    run_id = _make_macro_run_id(now, seq=seq)
    macro_record = elins_project.record_macro_run(
        ts=now,
        run_id=run_id,
        regions=regions_done,
        global_run_ref={
            "run_id": global_run_id,
            "scenario_id": (global_obj.get("output_object") or {}).get("scenario_id"),
        },
        notes=f"kernel.v1.0 eso={external_signal_mode}",
        region_run_ids=region_run_ids,
        external_signal_mode=external_signal_mode,
    )

    # Entity graph merge (build_and_merge handles missing existing).
    entity_graph_id: Optional[str] = None
    entity_count = 0
    edge_count = 0
    try:
        latest = elins_project.load_latest_entity_graph()
        existing = (latest or {}).get("graph") if latest else None
        merged = elins_entity_graph.build_and_merge(existing, pass_runs)
        merged["updated_ts"] = now
        entity_graph_id = elins_project.save_entity_graph(merged, ts=now)
        entity_count = len(merged.get("entities") or {})
        edge_count = len(merged.get("edges") or {})
    except Exception as e:  # pragma: no cover (defensive)
        logger.warning("kernel entity graph update failed err=%s", e)

    logger.info(
        "macro pass run_id=%s regions=%d global=%s eso=%s entities=%d edges=%d at=%.0f",
        run_id, len(regions_done), global_run_id, external_signal_mode,
        entity_count, edge_count, now,
    )
    summary = {
        "ran": True,
        "run_id": run_id,
        "ts": now,
        "regions": regions_done,
        "region_run_ids": region_run_ids,
        "global_run_id": global_run_id,
        "external_signal_mode": external_signal_mode,
        "macro_record": macro_record,
        "entity_graph_id": entity_graph_id,
        "entity_count": entity_count,
        "edge_count": edge_count,
        "model_id": macro_model_id,
    }
    # Macro-level kernel log (per-region logs already emitted by the
    # constituent run_regional_ELINS / run_ELINS calls above).
    eso_source_macro = (
        "perplexity"
        if (external_signal_mode == "cloud_perplexity"
            and perplexity_oracle._cloud_provider_active())
        else ("mock" if external_signal_mode == "cloud_perplexity" else "none")
    )
    kernel_logging.log_kernel_run(
        kind="run_macro_ELINS",
        user_id=system_user,
        external_signal_mode=external_signal_mode,
        eso_source=eso_source_macro,
        duration_ms=(time.perf_counter() - started) * 1000.0,
        ok=True,
        meta={
            "regions": len(regions_done),
            "entity_count": entity_count,
            "edge_count": edge_count,
            "has_eso": eso_source_macro != "none",
            "model_id": macro_model_id,
        },
    )
    return summary


# ---------------------------------------------------------------------------
# Public — run_thread_message (v47 threaded interaction)
# ---------------------------------------------------------------------------
# Cap how many recent messages we feed back as context. Keeps the
# prompt bounded + the mock-router preview line predictable.
THREAD_CONTEXT_MESSAGES: int = 8
THREAD_CONTEXT_CHAR_BUDGET: int = 6_000


def _format_thread_context(messages: list, *, latest: str) -> str:
    """Render the recent conversation as a prompt-ready string. We
    build a compact ``role: content`` transcript trimmed to the last
    ``THREAD_CONTEXT_MESSAGES`` entries + a tail char budget.
    """
    tail = list(messages or [])[-THREAD_CONTEXT_MESSAGES:]
    lines: list[str] = []
    for m in tail:
        role = m.get("role") or "user"
        content = (m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    transcript = "\n".join(lines)
    # Always end with the freshest user input even if it was already
    # appended — keeps the rendered prompt focused on what to answer.
    if latest and (not lines or not lines[-1].startswith("user: ")):
        transcript = (transcript + "\nuser: " + latest).strip()
    if len(transcript) > THREAD_CONTEXT_CHAR_BUDGET:
        # Drop from the front; the most recent turn is what matters.
        transcript = transcript[-THREAD_CONTEXT_CHAR_BUDGET:]
    return transcript


def _resolve_project_routing(
    user_id: str,
    project_id: Optional[str],
) -> tuple[Optional[str], Optional[list[str]]]:
    """v51 — resolve the (default_model, allowed_models) pair from a
    project's stored meta. Returns (None, None) when ``project_id``
    is empty or the project doesn't exist (graceful fallback to the
    normal task default). Aliases on default_model + allowed_models
    are resolved through ``model_router.resolve_model_alias``.

    The kernel calls this before ``_resolve_model`` so the project's
    preference enters as an ``override`` when valid.
    """
    if not project_id:
        return None, None
    try:
        meta = projects_vault.get_project(user_id, project_id)
    except (KeyError, ValueError):
        return None, None

    default_model: Optional[str] = None
    raw_default = meta.get("default_model")
    if raw_default:
        resolved = model_router.resolve_model_alias(raw_default)
        if resolved and model_router.is_valid_model(resolved):
            default_model = resolved

    allowed_models: Optional[list[str]] = None
    raw_allowed = meta.get("allowed_models")
    if isinstance(raw_allowed, list) and raw_allowed:
        cleaned: list[str] = []
        for entry in raw_allowed:
            resolved = model_router.resolve_model_alias(entry)
            if resolved and model_router.is_valid_model(resolved):
                cleaned.append(resolved)
        if cleaned:
            allowed_models = cleaned

    return default_model, allowed_models


def _apply_project_routing(
    chosen: str,
    default_model: Optional[str],
    allowed_models: Optional[list[str]],
) -> str:
    """Reconcile the resolved model_id against the project's
    allowed_models list. If the project's ``default_model`` is set
    and in ``allowed_models``, it wins. If only ``allowed_models`` is
    set and ``chosen`` isn't in it, fall back to the first allowed
    model. Otherwise ``chosen`` passes through.
    """
    if default_model:
        if not allowed_models or default_model in allowed_models:
            return default_model
    if allowed_models and chosen not in allowed_models:
        return allowed_models[0]
    return chosen


def run_thread_message(
    user_id: str,
    thread_id: str,
    content: str,
    *,
    project_id: Optional[str] = None,
) -> dict:
    """Append ``content`` as a user message, route it through the
    model router, append the assistant reply, and return both
    messages plus the updated thread meta.

    v51: when ``project_id`` is supplied AND the thread carries a
    matching ``project_id``, the kernel consults the project's
    ``default_model`` / ``allowed_models`` to override the standard
    task-default routing. If the supplied ``project_id`` doesn't
    match the thread's stored project_id, ``ValueError`` is raised
    so the app layer can map to 400.

    A28: when ``content`` begins with a directive run (#cite, #structure,
    #primitives, #regression, #compare, #reduce, #operator) the tokens are
    stripped (consumed this turn only) and routed through the unified
    ``directive_engine``: pre-enforcement may rewrite the prompt;
    post-enforcement may transform the reply and (for #cite) trigger one
    capped re-query. The return dict carries ``directives`` +
    ``directive_metadata``; ``#cite`` additionally surfaces
    ``grounding_status`` ("grounded"/"incomplete") for A18/A19/A20
    back-compat. Non-directive turns are unaffected.

    Returns::

        {
            "meta":              ThreadMeta,
            "user_message":      Message,
            "assistant_message": Message,
            "model_id":          str,
        }

    Raises:
        KeyError: ``thread_id`` doesn't exist for ``user_id``.
        ValueError: ``content`` isn't a non-empty string, or
                    ``project_id`` mismatches the thread's stored
                    project_id.
    """
    if not isinstance(content, str):
        raise ValueError("content must be a string")
    text = content.strip()
    if not text:
        raise ValueError("content must be a non-empty string after stripping")

    # A28 — unified directive engine. Detect + strip the leading directive
    # run BEFORE we persist or build context, so directives are consumed this
    # turn only (word-bounded + one-shot) and never stored or re-fired on a
    # later turn. Pre-enforcement may rewrite the prompt text (no-op for all
    # current directives). Non-directive turns are wholly untouched.
    directives = directive_engine.parse_directives(text)
    if directives.active:
        text = directives.text.strip()
        if not text:
            raise ValueError(
                "content must be a non-empty string after stripping the directive",
            )
        text = directive_engine.apply_pre_enforcement(directives, text)

    started = time.perf_counter()

    # v51 — validate the project_id against the thread's stored field
    # before doing any work. Must be a cheap meta-only read.
    if project_id:
        try:
            thread_meta_pre = threads_vault.get_thread_meta(user_id, thread_id)
        except KeyError:
            raise   # bubble for 404 mapping
        thread_project = thread_meta_pre.get("project_id")
        if thread_project and thread_project != project_id:
            raise ValueError(
                f"thread {thread_id!r} belongs to project "
                f"{thread_project!r}, not {project_id!r}",
            )

    # 1. Persist the user turn first so the assistant call sees it in
    #    context. ``threads_vault.append_message`` raises KeyError if
    #    the thread doesn't exist; we let that bubble for the app
    #    layer to map to 404.
    user_msg: dict = {
        "role":    "user",
        "content": text,
        "ts_ms":   int(time.time() * 1000),
        "model":   None,
    }
    meta_after_user, user_msg_saved = threads_vault.append_message(
        user_id, thread_id, user_msg,
    )

    # 2. Resolve the model. _resolve_model already records on
    #    operator_state.last_model_used + bumps local-model usage when
    #    relevant, so we get the same telemetry as ELINS / #G runs.
    #    v51: when ``project_id`` is supplied and resolves to a real
    #    project meta, that project's default_model becomes the
    #    routing override; allowed_models constrains the choice.
    project_default, project_allowed = _resolve_project_routing(user_id, project_id)
    model_id = _resolve_model(
        user_id, task="thread",
        override=project_default,    # None when no project / no default
    )
    model_id = _apply_project_routing(model_id, project_default, project_allowed)
    if user_id and project_default and model_id != project_default:
        # _resolve_model already recorded the override under
        # last_model_used; if allowed_models forced a different
        # choice, re-record so telemetry matches what was actually
        # called.
        try:
            operator_state.record_model_used(user_id, model_id)
        except Exception:  # pragma: no cover (defensive)
            pass

    # 3. Build conversation context + dispatch. We pull the canonical
    #    transcript from the vault (cheaper + correct than relying on
    #    the in-memory list) and pass it as the prompt body.
    try:
        _, full_messages = threads_vault.get_thread(user_id, thread_id)
    except KeyError:
        # Race: thread deleted between our two calls. Surface to the
        # caller — append_message above has already been undone if
        # this happened, but in practice we just re-raise.
        raise
    prompt = _format_thread_context(full_messages, latest=text)

    response = model_router.route_request(model_id, prompt)
    assistant_text = str(response.get("text") or "").strip()

    # A28 — unified directive post-enforcement. The engine validates/transforms
    # the reply per active directive and signals at most one capped re-query
    # (today only #cite retries). Non-directive turns skip this entirely.
    #   directive_metadata : per-directive results (functional payload)
    #   retry_used         : did the single capped re-query fire? (A20 telemetry)
    #   grounding_status   : derived from the #cite directive (A18/A19/A20
    #                        back-compat — preserved on the return dict + log)
    directive_metadata: dict = {}
    retry_used = False
    grounding_status: Optional[str] = None
    if directives.active:
        final_output, dmeta = directive_engine.apply_post_enforcement(
            directives, assistant_text,
        )
        if dmeta.retry_needed:
            retry_used = True
            retry_prompt = prompt
            if dmeta.retry_instruction:
                retry_prompt = f"{prompt}\n\n{dmeta.retry_instruction}"
            retry_response = model_router.route_request(model_id, retry_prompt)
            retry_output = str(retry_response.get("text") or "").strip() or final_output
            final_output, dmeta = directive_engine.apply_post_enforcement(
                directives, retry_output, retry_used=True,
            )
        assistant_text = final_output
        directive_metadata = dmeta.to_dict()
        cite_meta = directive_metadata.get("cite")
        if cite_meta:
            grounding_status = cite_meta.get("status")

    if not assistant_text:
        # Defence-in-depth: never persist an empty assistant turn —
        # tag explicitly so the UI can surface "no reply".
        assistant_text = "(no reply)"

    # 4. Persist the assistant turn.
    assistant_msg: dict = {
        "role":    "assistant",
        "content": assistant_text,
        "ts_ms":   int(time.time() * 1000),
        "model":   model_id,
    }
    meta_final, assistant_msg_saved = threads_vault.append_message(
        user_id, thread_id, assistant_msg,
    )

    # 5. v69 / Unit 74 — Optional EL/INS per-turn analysis hook.
    #    Off by default; users opt in via operator_state.el_ins_per_turn.
    #    We deliberately use the deterministic mode here to avoid
    #    doubling the per-turn LLM cost. Operators who want full
    #    semantic analysis hit /el_ins/analyze with provider_mode=auto.
    #    Failures are swallowed — analysis is a diagnostic, never
    #    allowed to break the chat response path.
    #
    #    v71 / Unit 79 — When the analysis lands, compute the
    #    reasoning_mode signal via select_reasoning_mode(el, ins, tsi)
    #    so consumers (Langbridg Interpreter, cockpit, kernel log)
    #    can read it. The Langbridg Interpreter call itself is not
    #    yet in the runtime — when it lands, it'll consume this
    #    signal. For now we surface it on the return dict and in the
    #    kernel log meta. When the per-turn flag is off, reasoning_mode
    #    stays None and nothing else changes (back-compat).
    reasoning_mode: Optional[str] = None
    anomalies_emitted: list[dict] = []  # v72 / Unit 80 — additive on return dict
    if user_id:
        try:
            if operator_state.get_el_ins_per_turn(user_id):
                import el_ins as _el_ins
                _result = _el_ins.analyze_text(text, provider_mode="deterministic")
                _el_ins.store_el_ins_record({
                    "operator_id": user_id,
                    "thread_id":   thread_id,
                    "timestamp":   time.time(),
                    "source":      "per_turn",
                    "result":      dict(_result),
                })
                # v71 — read the stamped record back to pick up TSI.
                _rows = _el_ins.get_thread_el_ins(user_id, thread_id)
                if _rows:
                    _latest = _rows[0]
                    _analysis = (_latest.get("result") or {}).get("analysis", {})
                    reasoning_mode = select_reasoning_mode(
                        float(_analysis.get("el_score") or 0.0),
                        float(_analysis.get("ins_score") or 0.0),
                        _latest.get("tsi") if isinstance(_latest.get("tsi"), int) else None,
                    )
                    # v72 / Unit 80 — detect anomalies on the just-stored
                    # record (with the immediately prior record on the same
                    # thread, if any, for the quadrant-jump rule). Store
                    # them and surface on the return dict. Failures swallow
                    # — anomalies are diagnostic, never allowed to break
                    # the chat path.
                    try:
                        _prior = _rows[1] if len(_rows) > 1 else None
                        _new_anoms = _el_ins.detect_anomalies(_latest, prior_record=_prior)
                        if _new_anoms:
                            _el_ins.store_anomalies(list(_new_anoms))
                            anomalies_emitted = [dict(a) for a in _new_anoms]
                    except Exception:  # pragma: no cover (defensive)
                        logger.debug("el_ins anomaly hook failed; ignoring", exc_info=True)
                    # v73 / Unit 82 — emit timeline events for the record
                    # + each anomaly. Same fail-soft pattern: timeline is
                    # a diagnostic surface and must never break the chat
                    # path.
                    try:
                        _rec_ev = _el_ins.build_record_event(
                            user_id,
                            el=float(_analysis.get("el_score") or 0.0),
                            ins=float(_analysis.get("ins_score") or 0.0),
                            tsi=_latest.get("tsi") if isinstance(_latest.get("tsi"), int) else None,
                            reasoning_mode=reasoning_mode,
                            thread_id=thread_id,
                        )
                        _el_ins.store_event(_rec_ev)
                        for _a in anomalies_emitted:
                            _anom_ev = _el_ins.build_anomaly_event(
                                user_id,
                                anomaly_id=str(_a.get("id") or ""),
                                anomaly_type=str(_a.get("type") or ""),
                                severity=int(_a.get("severity") or 0),
                                message=str(_a.get("message") or ""),
                            )
                            _el_ins.store_event(_anom_ev)
                    except Exception:  # pragma: no cover (defensive)
                        logger.debug("el_ins timeline hook failed; ignoring", exc_info=True)
        except Exception:  # pragma: no cover (defensive)
            logger.debug("el_ins per-turn hook failed; ignoring", exc_info=True)

    # 6. Structured kernel log line — same shape as the ELINS / #G
    #    paths. ``meta`` strips raw text via kernel_logging.safe_meta,
    #    so we only emit lengths + model_id.
    kernel_logging.log_kernel_run(
        kind="run_thread_message",
        user_id=user_id,
        external_signal_mode=_resolve_external_signal_mode(user_id, None),
        eso_source="none",
        duration_ms=(time.perf_counter() - started) * 1000.0,
        ok=True,
        meta={
            "thread_id":         thread_id,
            "project_id":        project_id,
            "model_id":          model_id,
            "message_count":     int(meta_final.get("message_count") or 0),
            "user_content_len":  len(user_msg_saved.get("content") or ""),
            "assistant_content_len": len(assistant_msg_saved.get("content") or ""),
            "reasoning_mode":    reasoning_mode,  # v71 / Unit 79 — None when per-turn off
            "grounding_status":  grounding_status,  # A18/A19 — derived from #cite
            "retry_used":        retry_used,        # A20 — capped re-query fired this turn
            # A28 — directive NAMES only (content-free). The full
            # directive_metadata is deliberately NOT logged: e.g. #compare's
            # metadata carries target names (content), and telemetry stays
            # content-free per A20/A24/A25.
            "directives":        directives.directives,
        },
    )

    return {
        "meta":              meta_final,
        "user_message":      user_msg_saved,
        "assistant_message": assistant_msg_saved,
        "model_id":          model_id,
        # v71 / Unit 79 — additive. None when EL/INS per-turn is off.
        "reasoning_mode":    reasoning_mode,
        # v72 / Unit 80 — additive. Empty list when no anomalies fired
        # or when EL/INS per-turn is off.
        "anomalies":         anomalies_emitted,
        # A18/A19 — additive. None unless this turn carried a #cite directive;
        # "grounded"/"incomplete" otherwise. Derived from the engine's #cite
        # metadata (the bespoke inline grounding path was retired in A28).
        "grounding_status":  grounding_status,
        # A28 — additive. Active directive names + per-directive metadata
        # (functional payload; [] / {} on non-directive turns).
        "directives":        directives.directives,
        "directive_metadata": directive_metadata,
    }


# ---------------------------------------------------------------------------
# v71 / Unit 79 — EL/INS-aware reasoning-mode selector
#
# Pure deterministic mapping from (el, ins, tsi) → reasoning_mode.
# Currently consumed by ``run_thread_message`` (stashed on the
# return dict + kernel log) and by ``/el_ins/operator/reasoning_mode``
# (cockpit indicator label across web/desktop/phone).
#
# When a Langbridg Interpreter module lands in the runtime, this is
# the signal it reads — the integration point is "wherever a
# downstream consumer needs to know what reasoning posture to take".
# We deliberately keep the function pure + reversible so the routing
# behaviour can be unit-tested without any kernel state.
# ---------------------------------------------------------------------------
REASONING_MODES: tuple = (
    "grounding",              # high EL, low INS — narrative inflation, needs facts
    "analysis",               # low EL, high INS — structural rigidity, expand
    "structured_reflection",  # high EL, high INS — both axes loaded; integrate
    "stabilization",          # low EL, low INS — under-expression; or TSI < 40
    "extended_reasoning",     # TSI > 80 — high stability, allowed to range
    "normal",                 # default fallback
)

# Score threshold for "high" vs "low" on the 0..10 EL/INS scale.
# Mirrors the analyzer's drift threshold (1.0 anchor) but skewed up
# slightly so noisy 1-2-score readings don't trip a mode switch.
_RM_SCORE_HIGH: float = 3.0

# TSI bracket constants per spec §1.
_TSI_FORCE_STABILIZATION: int = 40
_TSI_ALLOW_EXTENDED: int = 80


def select_reasoning_mode(
    el: float,
    ins: float,
    tsi: Optional[int] = None,
) -> str:
    """Map ``(el, ins, tsi)`` to a reasoning-mode label.

    Rules (checked in order — TSI gates dominate the EL/INS quadrant):

      1. ``tsi`` < 40   →  ``stabilization``  (force, regardless of scores)
      2. ``tsi`` > 80   →  ``extended_reasoning``  (allowed, regardless of scores)
      3. ``el`` ≥ 3 and ``ins`` < 3  →  ``grounding``
      4. ``el`` < 3 and ``ins`` ≥ 3  →  ``analysis``
      5. ``el`` ≥ 3 and ``ins`` ≥ 3  →  ``structured_reflection``
      6. ``el`` < 3 and ``ins`` < 3  →  ``stabilization``  (under-expression)
      7. else                         →  ``normal``  (unreachable in practice)

    ``tsi`` is optional — pass ``None`` when no TSI is available
    (e.g. records without a thread_id). In that case the function
    falls through directly to the EL/INS quadrant rules.

    Pure function — no I/O, no module state. Deterministic and
    reversible: same input always produces same output.
    """
    if not isinstance(el, (int, float)) or not isinstance(ins, (int, float)):
        raise ValueError("el and ins must be numeric")
    el_f = float(el)
    ins_f = float(ins)
    # 1. TSI gates dominate.
    if isinstance(tsi, int):
        if tsi < _TSI_FORCE_STABILIZATION:
            return "stabilization"
        if tsi > _TSI_ALLOW_EXTENDED:
            return "extended_reasoning"
    # 2. EL/INS quadrant.
    el_high = el_f >= _RM_SCORE_HIGH
    ins_high = ins_f >= _RM_SCORE_HIGH
    if el_high and not ins_high:
        return "grounding"
    if not el_high and ins_high:
        return "analysis"
    if el_high and ins_high:
        return "structured_reflection"
    if not el_high and not ins_high:
        return "stabilization"
    return "normal"  # pragma: no cover (unreachable; every quadrant is covered)


# ---------------------------------------------------------------------------
# Public — summarize_thread (v50 per-thread summary)
# ---------------------------------------------------------------------------
# Cap how many of the most recent messages we feed into the summary
# prompt + a hard char ceiling so the model call stays bounded.
SUMMARY_CONTEXT_MESSAGES: int = 20
SUMMARY_CONTEXT_CHAR_BUDGET: int = 8_000

# System-style instruction that prefixes the transcript. The kernel
# pre-pends it so the prompt is self-explanatory whether we're hitting
# a real LLM or the deterministic mock.
SUMMARY_SYSTEM_INSTRUCTION: str = (
    "Summarize this conversation in 1-2 sentences, "
    "user-centric, no model names."
)


def _format_summary_prompt(messages: list) -> str:
    """Render the recent transcript + the system instruction into one
    string suitable for ``model_router.route_request``. Last
    ``SUMMARY_CONTEXT_MESSAGES`` only; total clamped to
    ``SUMMARY_CONTEXT_CHAR_BUDGET``.
    """
    tail = list(messages or [])[-SUMMARY_CONTEXT_MESSAGES:]
    lines: list[str] = []
    for m in tail:
        role = m.get("role") or "user"
        content = (m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    transcript = "\n".join(lines)
    prompt = f"SYSTEM: {SUMMARY_SYSTEM_INSTRUCTION}\n\n{transcript}".rstrip()
    if len(prompt) > SUMMARY_CONTEXT_CHAR_BUDGET:
        # Drop from the front of the transcript, keep system + tail.
        keep = prompt[-SUMMARY_CONTEXT_CHAR_BUDGET:]
        prompt = f"SYSTEM: {SUMMARY_SYSTEM_INSTRUCTION}\n\n{keep}".rstrip()
    return prompt


def summarize_thread(user_id: str, thread_id: str) -> dict:
    """Generate or refresh a summary for ``thread_id`` and persist it
    onto the thread meta. Returns ``{"meta": ThreadMeta}``.

    When the thread has no messages, the stored summary (if any) is
    cleared — the UI shows "no summary yet" instead of stale text.

    Raises :class:`KeyError` when the thread doesn't exist.
    """
    started = time.perf_counter()

    # Pull the canonical (meta, messages). KeyError bubbles for the
    # app-layer 404 mapping; same shape as run_thread_message.
    meta, messages = threads_vault.get_thread(user_id, thread_id)

    # Empty-thread shortcut. Don't bother routing; just clear.
    if not messages:
        cleared = threads_vault.update_thread_summary(
            user_id, thread_id, None, int(time.time() * 1000),
        )
        kernel_logging.log_kernel_run(
            kind="summarize_thread",
            user_id=user_id,
            external_signal_mode=_resolve_external_signal_mode(user_id, None),
            eso_source="none",
            duration_ms=(time.perf_counter() - started) * 1000.0,
            ok=True,
            meta={
                "thread_id":     thread_id,
                "model_id":      None,
                "message_count": 0,
                "summary_len":   0,
                "cleared":       True,
            },
        )
        return {"meta": cleared}

    # Resolve the model + dispatch. _resolve_model bumps last_model_used
    # the same way the conversational turn does.
    model_id = _resolve_model(user_id, task="thread_summary")
    prompt = _format_summary_prompt(messages)
    response = model_router.route_request(model_id, prompt)
    summary_text = str(response.get("text") or "").strip()

    # Defence-in-depth: never persist an empty summary. The mock path
    # always returns a non-empty preview so this is mostly belt-and-braces.
    if not summary_text:
        summary_text = "(no summary)"

    now_ms = int(time.time() * 1000)
    updated = threads_vault.update_thread_summary(
        user_id, thread_id, summary_text, now_ms,
    )

    kernel_logging.log_kernel_run(
        kind="summarize_thread",
        user_id=user_id,
        external_signal_mode=_resolve_external_signal_mode(user_id, None),
        eso_source="none",
        duration_ms=(time.perf_counter() - started) * 1000.0,
        ok=True,
        meta={
            "thread_id":     thread_id,
            "model_id":      model_id,
            "message_count": int(meta.get("message_count") or 0),
            "summary_len":   len(summary_text),
            "cleared":       False,
        },
    )
    return {"meta": updated}


# ---------------------------------------------------------------------------
# v79 — ProblemSolver.REGRESSION_FIRST task entry point
# ---------------------------------------------------------------------------
# Thin kernel wrapper around ``problem_solver.analyze_packet`` so the
# regression_first flow is a first-class task in the kernel surface
# alongside ``run_thread_message``, ``summarize_thread``,
# ``run_emotional_physics``, etc.
#
# The kernel here intentionally does NOT drive an LLM call — packets
# are already emitted upstream under the canonical bundle prompt
# (``skills_export/regression_first/system_prompt.md``). What the
# kernel adds on top of ``analyze_packet``:
#   * model_id resolution (via ``_resolve_model`` with task
#     ``"regression_first"``) so ``operator_state.last_model_used``
#     stays in sync with the rest of the kernel runs;
#   * structured ``kernel_logging.log_kernel_run`` telemetry with the
#     ``run_regression_first`` kind tag;
#   * a uniform call shape callers (and ``model_router.call_regression_first``)
#     can target without poking into ``problem_solver`` directly.
#
# Storage is pluggable via ``store=``. The endpoint layer in
# ``app.py`` passes a ``VaultBackedRegressionChainStore(user_id)``
# per request (V80+); the kernel itself stays user-agnostic and
# never touches the vault directly.
# ---------------------------------------------------------------------------
def run_regression_first(
    packet,
    *,
    user_id: Optional[str] = None,
    model_id: Optional[str] = None,
    store=None,
) -> dict:
    """Dispatch a unified packet through the regression_first
    pipeline. Returns the kernel-shape result dict::

        {
            "packet":    <CognitivePacket>,  # parsed packet (or None when raw fails)
            "chain":     <RegressionChain>,  # the chain analyze_packet built, or None
            "model_id":  str,                # resolved model_id, recorded on operator_state
            "ok":        bool,               # True iff the packet parsed
        }

    Behaviour:
        * If ``packet`` cannot be parsed (malformed JSON / missing
          required fields / out-of-range scores), ``packet`` and
          ``chain`` are both ``None`` and ``ok`` is ``False``. A
          ``kernel_run`` log line is still emitted so degraded calls
          show up in telemetry.
        * The ``model_id`` is resolved even on parse failure so
          ``operator_state.last_model_used`` reflects intent.
        * Never raises — graceful degrade is the contract (matches
          ``run_emotional_physics``).
    """
    started = time.perf_counter()
    resolved_model = _resolve_model(
        user_id, task="regression_first", override=model_id,
    )

    parsed = problem_solver.analyze_packet(packet, store=store)
    ok = parsed is not None
    chain = parsed.get("chain") if ok else None

    kernel_logging.log_kernel_run(
        kind="run_regression_first",
        user_id=user_id,
        external_signal_mode=_resolve_external_signal_mode(user_id, None),
        eso_source="none",
        duration_ms=(time.perf_counter() - started) * 1000.0,
        ok=ok,
        meta={
            "model_id":            resolved_model,
            "chain_id":            chain["chain_id"] if chain else None,
            "regression_required": (
                bool(parsed.get("regression_required")) if ok else None
            ),
            "classification": (
                parsed.get("classification") if ok else None
            ),
        },
    )

    return {
        "packet":   parsed,
        "chain":    chain,
        "model_id": resolved_model,
        "ok":       ok,
    }


# ---------------------------------------------------------------------------
# v52 — Emotional Physics (structural-not-sentimental analysis)
# ---------------------------------------------------------------------------
# Single task-level reasoning mode. Returns a four-layer structured
# JSON object. Model selection is task-level via ``model_router``
# (task key ``emotional_physics`` → ``TASK_DEFAULTS``); no per-stage
# vendor pinning. Graceful degrade on parse errors — never raises 5xx.
#
# Architecturally this lives in the kernel (per ARCHITECTURE.md
# "Pointers for future passes": OS-level reasoning modes go in the
# kernel as ordinary Python functions, NOT as skill manifests). The
# prompt is inline below; nothing is imported from /skills_export/.
EMOTIONAL_PHYSICS_TASK: str = "emotional_physics"

# The four top-level keys the response MUST carry. Missing keys are
# filled with an empty dict in the skeleton + the ``_meta.parse_error``
# flag is set so the surface can render a degraded state.
_EMOTIONAL_PHYSICS_KEYS: tuple = (
    "field_curvature",
    "edge_pressure",
    "relational_primitives",
    "external_expression",
)

# Hard cap on the user's text so an over-long input can't blow the
# prompt budget. Truncation is silent — the call still succeeds.
EMOTIONAL_PHYSICS_INPUT_CHAR_CAP: int = 6_000

# Inline prompt — the JSON contract from the v52 spec, verbatim. The
# kernel embeds this so the model always sees the schema alongside the
# user's situation, and so the file is the single source of truth for
# the contract. Never imported from /skills_export/.
_EMOTIONAL_PHYSICS_PROMPT: str = """SYSTEM: You are running the emotional_physics reasoning mode for ClarityOS.

Given the user's text describing a situation, produce a four-layer structural analysis. Output a single JSON object — no prose before or after, no markdown fences. The object must have exactly these four top-level keys:

  1. field_curvature        — internal state pattern (NOT feelings or diagnoses)
  2. edge_pressure          — externally legible signal pattern (how it lands on others)
  3. relational_primitives  — underlying relational structure (cross-cultural units)
  4. external_expression    — stabilised communication and action guidance

LAYER 1 — field_curvature
{
  "intensity": "low | medium | high",
  "gradient_direction": "inward | outward | mixed | unclear",
  "stability": "stable | unstable | oscillating",
  "dominant_forces": [
    // subset of: "uncertainty", "time_pressure", "role_confusion",
    //   "conflict_avoidance", "over_responsibility"
    // include only what fits; do not force-fit
  ],
  "notes": "short plain-language description of the internal pattern"
}

LAYER 2 — edge_pressure
{
  "signal_clarity": "clear | mixed | unclear",
  "signal_intensity": "low | medium | high",
  "coherence": "coherent | fragmented | contradictory",
  "perceived_posture": [
    // subset of: "pursuing", "withdrawing", "defensive",
    //   "compliant", "confrontational", "ambivalent"
  ],
  "risk_of_misread": "low | medium | high",
  "notes": "how this is likely to land on the other party"
}

LAYER 3 — relational_primitives
{
  "trust": "low | medium | high | fluctuating | unclear",
  "alignment": "aligned | partially_aligned | misaligned | unclear",
  "boundary": "clear | soft | collapsed | rigid | contested",
  "agency": "full | partial | constrained | outsourced",
  "distance": "close | moderate | distant | increasing | decreasing",
  "dominant_pattern": [
    // subset of: "pressure_asymmetry", "boundary_uncertainty",
    //   "role_confusion", "narrative_drift", "identity_compression",
    //   "avoidance_cycle", "pursuit_cycle"
  ],
  "notes": "plain-language summary of the structural pattern"
}

LAYER 4 — external_expression
{
  "recommended_posture": [
    // subset of: "clarify_intent", "slow_down", "set_boundary",
    //   "ask_for_specifics", "name_the_constraint", "acknowledge_impact"
  ],
  "message_guidance": [
    "one to three short bullet points of how to phrase things"
  ],
  "friction_reduction_moves": [
    "specific small actions that reduce pressure or confusion"
  ],
  "risk_if_unchanged": "short description of what likely happens if nothing changes",
  "next_step": "one clear, low-friction next move"
}

Output contract:
  * Return a single JSON object with exactly the four top-level keys above.
  * All notes fields must be short, concrete, and non-clinical.
  * No clinical or diagnostic language. No personality labels.
  * No provider names, no model names, no references to routing or infrastructure.
  * No markdown fences, no prose, no commentary. JSON only.
"""


# Fence-tolerant JSON extraction. Mirrors the v41 perplexity_oracle
# strategy: try direct parse → strip ```json fences → grab the first
# brace block. Kept local to the kernel to avoid coupling. Never
# raises — returns (None, error_message) on failure.
_FENCE_RE: re.Pattern = re.compile(
    r"```(?:json)?\s*(.+?)```", re.DOTALL | re.IGNORECASE,
)
_BRACE_RE: re.Pattern = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> tuple[Optional[dict], Optional[str]]:
    """Best-effort fence-tolerant JSON parser.

    Returns ``(parsed_dict, error_message)``. ``parsed_dict`` is ``None``
    on failure and ``error_message`` is ``None`` on success.

    Strategies, in order:
      1. Direct ``json.loads`` of the trimmed string.
      2. Extract content from the first ```json … ``` (or bare ``` … ```) fence.
      3. Greedy match of the first ``{ … }`` block.
    """
    if not isinstance(text, str):
        return None, "response was not a string"
    s = text.strip()
    if not s:
        return None, "response was empty"

    # 1. Direct parse.
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed, None
        return None, "response was JSON but not an object"
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Fenced block.
    m = _FENCE_RE.search(s)
    if m:
        inner = m.group(1).strip()
        try:
            parsed = json.loads(inner)
            if isinstance(parsed, dict):
                return parsed, None
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. First brace block.
    m = _BRACE_RE.search(s)
    if m:
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, dict):
                return parsed, None
        except (json.JSONDecodeError, ValueError):
            pass

    return None, "could not parse JSON from model response"


def _emotional_physics_skeleton() -> dict:
    """Empty four-layer skeleton. Returned (with the parse_error meta
    populated) when the model output can't be parsed, so the response
    shape is stable regardless of model behaviour."""
    return {k: {} for k in _EMOTIONAL_PHYSICS_KEYS}


def run_emotional_physics(user_id: str, text: str) -> dict:
    """v52 — structural-not-sentimental analysis of a situation.

    Given a user's free-text description, returns a four-layer
    structured JSON object:

      * ``field_curvature``       — internal state pattern
      * ``edge_pressure``         — externally legible signal pattern
      * ``relational_primitives`` — underlying relational structure
      * ``external_expression``   — stabilised communication guidance

    Model selection is task-level via ``model_router`` with task
    ``emotional_physics`` (default ``anthropic:claude-3.7``). No
    vendor pinning; users override via ``operator_state.preferred_model``.

    Graceful degrade contract: parse failures return a four-key
    skeleton with ``_meta.parse_error`` populated — never raises 5xx.

    Returns::

        {
            "field_curvature":       {...},
            "edge_pressure":         {...},
            "relational_primitives": {...},
            "external_expression":   {...},
            "_meta": {
                "model_id":    "anthropic:claude-3.7",
                "ts_ms":       1715300000000,
                "parse_error": None,   # or str on degrade
            },
        }

    Raises:
        ValueError: ``text`` is missing / empty / whitespace-only.
    """
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("text must be a non-empty string after stripping")
    if len(cleaned) > EMOTIONAL_PHYSICS_INPUT_CHAR_CAP:
        cleaned = cleaned[:EMOTIONAL_PHYSICS_INPUT_CHAR_CAP]

    started = time.perf_counter()

    # 1. Resolve model. _resolve_model records onto
    #    operator_state.last_model_used + bumps local-model usage when
    #    relevant — same telemetry as ELINS / #G / thread paths.
    model_id = _resolve_model(user_id, task=EMOTIONAL_PHYSICS_TASK)

    # 2. Build prompt + dispatch. The prompt embeds the full JSON
    #    contract so the model can produce a schema-valid response
    #    without needing any out-of-band context.
    prompt = _EMOTIONAL_PHYSICS_PROMPT + "\nSITUATION:\n" + cleaned
    response = model_router.route_request(model_id, prompt)
    raw_text = str(response.get("text") or "").strip()

    # 3. Parse with graceful degrade. We always emit the four
    #    top-level keys; missing keys remain empty dicts.
    parsed, parse_error = _extract_json(raw_text)
    result_body = _emotional_physics_skeleton()
    if isinstance(parsed, dict):
        missing: list[str] = []
        for k in _EMOTIONAL_PHYSICS_KEYS:
            v = parsed.get(k)
            if isinstance(v, dict):
                result_body[k] = v
            else:
                missing.append(k)
        if missing and not parse_error:
            parse_error = "missing or invalid keys: " + ",".join(missing)

    now_ms = int(time.time() * 1000)
    out = {
        **result_body,
        "_meta": {
            "model_id":    model_id,
            "ts_ms":       now_ms,
            "parse_error": parse_error,
        },
    }

    # 4. Structured kernel log line. safe_meta strips any raw-text
    #    keys defensively (we already only pass scalars).
    kernel_logging.log_kernel_run(
        kind="emotional_physics",
        user_id=user_id,
        external_signal_mode=_resolve_external_signal_mode(user_id, None),
        eso_source="none",
        duration_ms=(time.perf_counter() - started) * 1000.0,
        ok=parse_error is None,
        meta={
            "model_id":    model_id,
            "input_len":   len(cleaned),
            "raw_len":     len(raw_text),
            "parse_error": parse_error,
        },
        error=parse_error,
    )

    return out


# ---------------------------------------------------------------------------
# v53 — ELINS v2 (Path-C view adapter)
# ---------------------------------------------------------------------------
def run_elins_v2(
    user_id: str,
    raw_text: str,
    *,
    region: Optional[str] = None,
    request_input: Optional[dict] = None,
    external_signal_mode: Optional[str] = None,
) -> dict:
    """v53 — ELINS v2 view-adapter run.

    Runs the existing v33-v34 ``standard_elins.generate_ELINS`` pipeline,
    optionally augments with ``regional_elins.run_regional_elins`` when
    a region is supplied, then projects everything into the v2.0
    response envelope via ``elins_v2_view.build_v2_envelope``.

    Path C: NO new generative work. Pure view adapter over existing
    deterministic pipeline output. NO model calls beyond what
    standard_elins / regional_elins already do (and those are also
    deterministic — no LLM dispatch).

    Returns the v2.0 response dict::

        {
          "elins_version": "elins.v2.0",
          "region":        "us | eu | ... | None",
          "input":         <echoed request input>,
          "pipeline":      { L1_ingest .. L10_signature },
          "outputs":       { collapse_state, attractor, state_distribution,
                             P0_P8, geography_tier, timeline, multiplier },
          "meta":          { engine, view_kind, warnings, notes },
        }

    Raises:
        ValueError: ``raw_text`` is empty / not a string, or ``region``
                    is rejected by ``regional_elins`` validation.
    """
    if not isinstance(raw_text, str):
        raise ValueError("raw_text must be a string")
    text = raw_text.strip()
    if not text:
        raise ValueError("raw_text must be a non-empty string after stripping")

    started = time.perf_counter()

    # 1. Existing 10-layer pipeline (deterministic + lexical).
    elins_object = standard_elins.generate_ELINS(text, user=user_id)

    # 2. Optional regional augmentation. regional_elins.run_regional_elins
    #    validates the region; bad codes raise ValueError that the
    #    caller maps to 400.
    regional_object: Optional[dict] = None
    eso_source = "none"
    if region:
        mode = _resolve_external_signal_mode(user_id, external_signal_mode)
        eso = _maybe_fetch_eso(mode, region_code=region, user=user_id)
        regional_object = regional_elins.run_regional_elins(
            region, user_id, eso=eso,
        )
        if eso:
            eso_source = str(eso.get("source") or "mock")

    # 3. Path-C view adapter. Pure function over fields generated above.
    envelope = elins_v2_view.build_v2_envelope(
        elins_object,
        region=region,
        regional_object=regional_object,
        request_input=request_input,
    )

    # 4. Structured kernel log line. safe_meta strips raw-text fields.
    kernel_logging.log_kernel_run(
        kind="elins_v2",
        user_id=user_id,
        external_signal_mode=_resolve_external_signal_mode(
            user_id, external_signal_mode,
        ),
        eso_source=eso_source,
        duration_ms=(time.perf_counter() - started) * 1000.0,
        ok=True,
        meta={
            "region":         region,
            "attractor":      envelope["outputs"]["attractor"],
            "collapse_state": envelope["outputs"]["collapse_state"],
            "multiplier":     envelope["outputs"]["multiplier"],
            "geography_tier": envelope["outputs"]["geography_tier"],
            "input_len":      len(text),
        },
    )

    return envelope


# ---------------------------------------------------------------------------
# v54 — Ingestion (manual + RSS/Atom feeds)
# ---------------------------------------------------------------------------
def run_manual_ingestion(
    user_id: str,
    raw_text: str,
    *,
    source: str = "manual",
    region: Optional[str] = None,
) -> dict:
    """v54 — manual text ingestion.

    User-pasted content → ELINS v2 → library. No HTTP fetches, no
    parsing. ``source`` is a free-text label (e.g. "FT_2026-05-10",
    "transcript", "operator_note") stored on the library entry.

    Returns::

        {
            "library_id": "<library_store id>",
            "envelope":   <full v2 envelope>,
        }

    Raises:
        ValueError: ``raw_text`` is empty / not a string.
    """
    if not isinstance(raw_text, str):
        raise ValueError("raw_text must be a string")
    text = raw_text.strip()
    if not text:
        raise ValueError("raw_text must be a non-empty string after stripping")

    started = time.perf_counter()

    envelope = run_elins_v2(
        user_id, text,
        region=region,
        request_input={
            "raw_text":     text,
            "source_type":  "manual",
            "manual_label": source,
        },
    )
    library_id = ingestion_bus.persist_to_library(
        user_id,
        source=source,
        region=region,
        raw_text=text,
        envelope=envelope,
        item_meta={"kind": "manual"},
        visibility="private",
    )

    kernel_logging.log_kernel_run(
        kind="ingestion_manual",
        user_id=user_id,
        external_signal_mode="none",
        eso_source="none",
        duration_ms=(time.perf_counter() - started) * 1000.0,
        ok=True,
        meta={
            "source":     source,
            "region":     region,
            "library_id": library_id,
            "attractor":  envelope["outputs"]["attractor"],
            "input_len":  len(text),
        },
    )
    return {
        "library_id": library_id,
        "envelope":   envelope,
    }


def run_feed_ingestion(
    user_id: str,
    feed_id: str,
) -> dict:
    """v54 — fetch + parse + dispatch one registered RSS/Atom feed.

    Up to ``ingestion_bus.ITEMS_PER_FEED_PER_RUN`` (5) items per run.
    Each item is independently processed through ``run_elins_v2`` and
    persisted to ``library_store``. Per-item errors are silently
    skipped; feed-level fetch errors are captured in the return dict
    (never raised — the caller orchestrates retry).

    Returns::

        {
            "feed_id":     <str>,
            "feed_name":   <str>,
            "fetched_at":  <float epoch>,
            "items":       <int>,
            "stored":      <int>,
            "library_ids": [<str>, ...],
            "fetch_error": <str | None>,
        }

    Raises:
        KeyError: ``feed_id`` not registered for this user.
    """
    feed = ingestion_bus.get_feed(user_id, feed_id)
    if feed is None:
        raise KeyError(feed_id)

    started = time.perf_counter()
    fetched_at = time.time()
    items: list[dict] = []
    fetch_error: Optional[str] = None
    library_ids: list[str] = []

    try:
        raw = ingestion_bus.fetch_feed_bytes(feed["url"])
        items = ingestion_bus.parse_feed_items(raw)
    except ValueError as e:
        fetch_error = str(e)

    for item in items:
        item_text = ingestion_bus.item_text_for_elins(item)
        if not item_text:
            continue
        try:
            env = run_elins_v2(
                user_id, item_text,
                region=feed.get("region"),
                request_input={
                    "raw_text":     item_text,
                    "source_type":  "rss_feed",
                    "feed_name":    feed["name"],
                    "feed_url":     feed["url"],
                    "item_link":    item.get("link"),
                    "item_title":   item.get("title"),
                    "published_at": item.get("published_at"),
                },
            )
        except ValueError:
            continue
        library_id = ingestion_bus.persist_to_library(
            user_id,
            source=f"feed:{feed['name']}",
            region=feed.get("region"),
            raw_text=item_text,
            envelope=env,
            item_meta={
                "kind":         "feed_item",
                "feed_id":      feed_id,
                "feed_name":    feed["name"],
                "feed_url":     feed["url"],
                "item_link":    item.get("link"),
                "item_title":   item.get("title"),
                "published_at": item.get("published_at"),
            },
            visibility="private",
        )
        library_ids.append(library_id)

    kernel_logging.log_kernel_run(
        kind="ingestion_feed",
        user_id=user_id,
        external_signal_mode="none",
        eso_source="none",
        duration_ms=(time.perf_counter() - started) * 1000.0,
        ok=fetch_error is None,
        meta={
            "feed_id":     feed_id,
            "feed_name":   feed["name"],
            "item_count":  len(items),
            "stored":      len(library_ids),
            "fetch_error": fetch_error,
        },
        error=fetch_error,
    )
    return {
        "feed_id":     feed_id,
        "feed_name":   feed["name"],
        "fetched_at":  fetched_at,
        "items":       len(items),
        "stored":      len(library_ids),
        "library_ids": library_ids,
        "fetch_error": fetch_error,
    }


def run_ingestion_cycle(user_id: str) -> dict:
    """v54 — run all registered feeds for a user.

    Per-feed errors are captured per-result; never raises. Returns
    an aggregate summary.
    """
    feeds = ingestion_bus.list_feeds(user_id)
    results: list[dict] = []
    for feed in feeds:
        try:
            r = run_feed_ingestion(user_id, feed["feed_id"])
        except Exception as e:  # pragma: no cover (defensive — get_feed/list_feeds are consistent)
            r = {
                "feed_id":     feed["feed_id"],
                "feed_name":   feed["name"],
                "fetched_at":  time.time(),
                "items":       0,
                "stored":      0,
                "library_ids": [],
                "fetch_error": str(e),
            }
        results.append(r)
    return {
        "user_id":      user_id,
        "feed_count":   len(feeds),
        "results":      results,
        "total_stored": sum(r.get("stored", 0) for r in results),
    }


# ---------------------------------------------------------------------------
# Status / view
# ---------------------------------------------------------------------------
def kernel_status() -> dict:
    """Founder-facing kernel snapshot. Static + persisted bits only —
    no per-user fields.

    v45: ``local_model`` summarises the on-device runtime — whether it
    is configured, the path it would load, and (when warm) the loaded
    flag + memory footprint.
    """
    cfg = elins_scheduler_config.get_config() or {}
    rt = local_model_runtime.get_runtime_status()
    return {
        "version": KERNEL_VERSION,
        "eso_default_mode": cfg.get("external_signal_mode") or "cloud_only",
        "scheduler_enabled": bool(cfg.get("enabled")),
        "macro_cadence": cfg.get("cadence") or "off",
        "last_macro_run_ts": float(cfg.get("last_run_ts") or 0.0) or None,
        "valid_signal_modes": list(VALID_SIGNAL_MODES),
        "regions": list(regional_elins.REGION_CODES),
        # v41 — perplexity provider visibility for the founder console.
        "perplexity": perplexity_oracle.provider_status(),
        # v44 — model router visibility (providers + supported models +
        # active founder-default override).
        "models": model_router.get_router_status(),
        # v45 — on-device runtime block (configured / loaded / path /
        # backend / inference_count / memory_footprint_mb).
        "local_model": {
            "configured": bool(rt.get("configured")),
            "path":       rt.get("path"),
            "loaded":     bool(rt.get("loaded")),
            "backend":    rt.get("backend"),
            "mock":       bool(rt.get("mock")),
            "memory_footprint_mb": float(rt.get("memory_footprint_mb") or 0.0),
            "inference_count":     int(rt.get("inference_count") or 0),
            "loaded_at":  rt.get("loaded_at"),
            "last_error": rt.get("last_error"),
            "version":    rt.get("version"),
        },
        # v46 — memory vault block. Visible to founders so a misconfigured
        # encryption secret / unwritable vault dir is debuggable from the
        # console without SSH.
        "vault": _kernel_vault_summary(),
    }


def _kernel_vault_summary() -> dict:
    """Founder-facing vault snapshot embedded in ``kernel_status``."""
    vs = memory_vault.vault_status()
    return {
        "enabled":   bool(vs.get("enabled")),
        "backend":   vs.get("backend"),
        "encrypted": bool(vs.get("encrypted")),
        "keys":      int(vs.get("keys") or 0),
        "users":     int(vs.get("users") or 0),
        "namespaces": vs.get("namespaces") or [],
        "version":   vs.get("version"),
    }


def kernel_view_for_user(user_id: str) -> dict:
    """Per-user kernel embed for ``/me``. Read-only metadata snapshot."""
    state = operator_state.get_operator_state(user_id) if user_id else {}
    mode = (state or {}).get("external_signal_mode") or "cloud_only"
    if mode == "cloud_only":
        eso_source = "none"
    else:
        eso_source = (
            "perplexity" if perplexity_oracle._cloud_provider_active() else "mock"
        )
    # v46 — vault per-user counts (cheap read; mock backend in tests is
    # an in-memory dict).
    vault_keys = 0
    notes_count = 0
    embeddings_count = 0
    if user_id:
        try:
            vault_keys = memory_vault.vault_count_for_user(user_id)
            notes_count = memory_vault.vault_count_for_user(user_id, "notes")
            embeddings_count = memory_vault.vault_count_for_user(user_id, "embeddings")
        except Exception:  # pragma: no cover (defensive)
            pass

    # v47 — thread metrics. Counts every ``threads.meta.*`` entry and
    # picks the freshest ``updated_at`` so the UI can show "last
    # activity" without round-tripping the full thread list.
    thread_count = 0
    last_thread_updated_at: Optional[int] = None
    if user_id:
        try:
            metas = threads_vault.list_threads(user_id)
            thread_count = len(metas)
            if metas:
                last_thread_updated_at = max(int(m.get("updated_at") or 0) for m in metas)
        except Exception:  # pragma: no cover (defensive)
            pass

    return {
        "version": KERNEL_VERSION,
        "external_signal_mode": mode,
        "eso_source": eso_source,
        "preferred_domains": (state or {}).get("preferred_domains") or {},
        "preferred_regions": (state or {}).get("preferred_regions") or {},
        # v44 — model router fields.
        "preferred_model": (state or {}).get("preferred_model"),
        "last_model_used": (state or {}).get("last_model_used"),
        # v45 — per-user local model usage counter.
        "local_model_usage_count": int((state or {}).get("local_model_usage_count") or 0),
        # v46 — per-user vault counts.
        "vault_keys":       vault_keys,
        "notes_count":      notes_count,
        "embeddings_count": embeddings_count,
        # v47 — thread metrics.
        "thread_count":           thread_count,
        "last_thread_updated_at": last_thread_updated_at,
    }


# ---------------------------------------------------------------------------
# Internal — counter for macro_run_id (mirrors the v36 pattern)
#
# PASS-4 B2 — The lock is pre-allocated at module import time so the
# first concurrent callers of ``_next_macro_seq`` cannot race on lazy
# initialisation. The old code held ``_macro_seq_lock = None`` until
# the first call and then did ``if _macro_seq_lock is None:
# _macro_seq_lock = threading.Lock()``, which is a TOCTOU window —
# two threads could both observe None and each install a new Lock,
# only one of which would actually be used, so the other's
# ``_macro_seq += 1`` could race. With the lock allocated at import,
# every caller observes the same Lock instance and serialises on it.
# ---------------------------------------------------------------------------
import threading

_macro_seq: int = 0
_macro_seq_lock: threading.Lock = threading.Lock()


def _next_macro_seq() -> int:
    global _macro_seq
    with _macro_seq_lock:
        _macro_seq += 1
        return _macro_seq


def _reset_for_tests() -> None:
    # PASS-4 B2 — keep the pre-allocated lock; only zero the counter.
    # Tests are typically single-threaded between cases, but we still
    # acquire the lock so a stray macro pass from a previous test does
    # not race with the reset.
    global _macro_seq
    with _macro_seq_lock:
        _macro_seq = 0
