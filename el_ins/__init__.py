"""
ClarityOS EL/INS kernel module — v69 / Unit 74-75.

Reasoning-stability operator that scores text by the ratio of
Emotive Language (EL) to Institutional Signal (INS) and emits a
deterministic JSON shape (see ``skills_export/el_ins/schema.json``).

Two modes:
    * LLM-driven   — prepends the canonical system prompt and calls
                     model_router, parses structured JSON output.
    * Deterministic — pure Python heuristic over keyword vocabularies.
                      Used when LLM unavailable, when explicitly
                      requested, or on phone-runtime / offline paths.

Public surface re-exported here so callers can do:

    from el_ins import analyze_text, analyze_thread, ElInsResult
    from el_ins import store_el_ins_record, get_thread_el_ins, ...
"""
from __future__ import annotations

from .el_ins_analyzer import (
    analyze_text,
    analyze_thread,
    ElInsResult,
    PROVIDER_MODES,
    SYSTEM_PROMPT_PATH,
)
from .el_ins_store import (
    ElInsRecord,
    store_el_ins_record,
    get_thread_el_ins,
    get_recent_el_ins,
    get_macro_el_ins,
    compute_thread_stability,
    compute_operator_summary,
    STABILITY_DEFAULT_WINDOW,
    _reset_for_tests,
)
from .el_ins_export import (
    build_json_export,
    build_pdf_export,
)
from .anomaly import (
    Anomaly,
    ANOMALY_TYPES,
    detect_anomalies,
)
from .anomaly_store import (
    store_anomalies,
    get_anomaly,
    list_anomalies,
    list_anomalies_since,
    _reset_for_tests as _reset_anomalies_for_tests,
)
from .rollup import (
    RollupResult,
    compute_rollup,
    ROLLUP_WINDOWS,
)
from .timeline import (
    TimelineEvent,
    TimelineEventType,
    TIMELINE_EVENT_TYPES,
    DEFAULT_TIMELINE_LIMIT,
    store_event,
    list_events,
    list_events_since,
    get_event,
    build_record_event,
    build_anomaly_event,
    build_rollup_event,
    # v78 — Regression-First chain events.
    build_regression_chain_started_event,
    build_regression_chain_layer_updated_event,
    build_regression_chain_closed_event,
    build_regression_chain_archived_event,
    _reset_for_tests as _reset_timeline_for_tests,
)
from .org_timeline import (
    ORG_TIMELINE_WINDOWS,
    OrgTimelineEntry,
    compute_org_timeline,
)

# Composite reset for tests that need every store cleaned.
def _reset_all_for_tests() -> None:
    from .el_ins_store import _reset_for_tests as _r1
    _r1()
    _reset_anomalies_for_tests()
    _reset_timeline_for_tests()


__all__ = [
    "analyze_text",
    "analyze_thread",
    "ElInsResult",
    "PROVIDER_MODES",
    "SYSTEM_PROMPT_PATH",
    "ElInsRecord",
    "store_el_ins_record",
    "get_thread_el_ins",
    "get_recent_el_ins",
    "get_macro_el_ins",
    "compute_thread_stability",
    "compute_operator_summary",
    "STABILITY_DEFAULT_WINDOW",
    "build_json_export",
    "build_pdf_export",
    # v72 / Unit 80 — anomalies
    "Anomaly",
    "ANOMALY_TYPES",
    "detect_anomalies",
    "store_anomalies",
    "get_anomaly",
    "list_anomalies",
    "list_anomalies_since",
    # v72 / Unit 81 — rollup
    "RollupResult",
    "compute_rollup",
    "ROLLUP_WINDOWS",
    # v73 / Unit 82 — operator timeline
    "TimelineEvent",
    "TimelineEventType",
    "TIMELINE_EVENT_TYPES",
    "DEFAULT_TIMELINE_LIMIT",
    "store_event",
    "list_events",
    "list_events_since",
    "get_event",
    "build_record_event",
    "build_anomaly_event",
    "build_rollup_event",
    # v78 — Regression-First chain events
    "build_regression_chain_started_event",
    "build_regression_chain_layer_updated_event",
    "build_regression_chain_closed_event",
    # v81 — Regression-First archive event
    "build_regression_chain_archived_event",
    # v73 / Unit 83 — org timeline
    "ORG_TIMELINE_WINDOWS",
    "OrgTimelineEntry",
    "compute_org_timeline",
    "_reset_for_tests",
    "_reset_anomalies_for_tests",
    "_reset_timeline_for_tests",
    "_reset_all_for_tests",
]
