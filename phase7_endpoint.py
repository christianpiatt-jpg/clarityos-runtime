# phase7_endpoint.py
"""
Phase 7 — read-only telemetry HTTP endpoint (CARD 7.2A).

Exposes the durable Phase 7 telemetry (Card 7.1) over HTTP so the
web / desktop / phone Operator Consoles can render drift / coherence-health /
trust-band / history-count. Read-only — the console never writes here; Phase
7.1 owns recording.

Mirrors the repo's Founder-telemetry pattern: a self-contained ``APIRouter``
that ``app.py`` mounts via ``include_router`` inside a try/except. Imports ONLY
the flat-root Phase 7 modules — nothing from the CI-gated runtime spine
(``operator_state`` / ``memory_vault`` / ``runtime_privacy``), no vault, no
auth. No wall-clock, no randomness.

    GET /operator/telemetry
        -> {"history": [record, ...], "latest": record | None,
            "analytics": {drift_velocity, drift_acceleration, coherence_trend,
                          stability_forecast, trajectory},
            "alerts": [str, ...],
            "causal_factors": [{action, correlation, contribution}, ...],
            "narrative": str,
            "causal_graph": {nodes, edges},
            "primary_chain": {nodes, edges, score},
            "causal_influence": {node_id: float},
            "causal_centrality": {node_id: float},
            "ranked_explanations": [{node, label, influence, centrality, score}, ...],
            "causal_motifs": {feedback_loops, bottlenecks, attractors},
            "causal_chains": [{nodes, edges, score, motifs}, ...],
            "causal_deltas": {influence_delta, centrality_delta,
                              motif_delta, chain_delta},
            "causal_stability": {stability_score, trend, drivers},
            "causal_narrative": str,
            "unified_narrative": str,
            "behavioral_motifs": {action_loops, trigger_chains, habits,
                                  action_bottlenecks, action_attractors}}

    POST /operator/action   (Phase 9.1)
        body {"id": str, "label": str, "timestamp": float, "magnitude": float|null}
        -> {"status": "ok"}   (400 on invalid action)
        Validates + normalizes the action (``phase9_ingest.ingest_action``) and
        appends it to the append-only action continuity log; does NOT yet enter
        the causal graph (that is Phase 9.2).

where each record is the JSON-serialisable dict from
``phase7_storage.record_to_dict``, ``analytics`` is the on-the-fly Phase 7.3
temporal analytics (CARD 7.4), ``alerts`` is the Phase 7.6 operator guidance
(CARD 7.6), ``causal_factors`` is the Phase 7.7 causal drift mapping (CARD 7.7),
``narrative`` is the Phase 7.9 deterministic causal narrative (CARD 7.9), and
``causal_graph`` / ``primary_chain`` are the Phase 8.1 first-order causal graph
+ most-influential chain (CARD 8.1); ``causal_influence`` / ``causal_centrality`` /
``ranked_explanations`` are the Phase 8.2 multi-hop propagation outputs (CARD 8.2),
``causal_motifs`` is the Phase 8.3 structural motif detection — feedback loops
/ bottlenecks / attractors (CARD 8.3) — and ``causal_chains`` is the Phase 8.4
ranked set of motif-annotated multi-chain explanations (CARD 8.4); and
``causal_deltas`` is the Phase 8.6 temporal change in the causal structure —
influence / centrality / motif / chain deltas between the current snapshot and
the previous one (CARD 8.6); and ``causal_stability`` is the Phase 8.7 causal
stability forecast — a ``stability_score`` + ``trend`` (stabilizing /
destabilizing / transitioning / steady) + ``drivers`` derived from those deltas
(CARD 8.7); and ``causal_narrative`` is the Phase 8.9 unified, deterministic
causal narrative synthesizing the strongest chain + motifs + influence
highlights + deltas + stability into one text block (CARD 8.9 — distinct from
the Phase 7.9 ``narrative`` field, which explains temporal drift); and
``unified_narrative`` is the Phase 8.10 fusion of the Phase 7.9 temporal
narrative + the Phase 8.9 causal narrative into a single block with an
Integrated Interpretation + a deterministic Overall Assessment (stable /
shifting / transitioning / destabilizing) (CARD 8.10); and ``behavioral_motifs``
is the Phase 9.4 action-layer motif detection — action loops / trigger chains /
habits / action bottlenecks / attractors over the ingested action stream + an
action-augmented copy of the graph (CARD 9.4; empty until actions are POSTed via
``/operator/action``). The action-augmented graph is computed separately, so the
``causal_*`` fields above remain action-free. The Phase-7.7 ``causal_factors``
attribution keeps no operator-action log, so
``causal_factors`` is the neutral ``[{"action": "none", ...}]`` sentinel,
``primary_chain`` is the analytics→narrative fallback, and ``causal_chains``
resolves to that single trivial chain until an action source is wired in a
later card.

The Phase 8.6 ``causal_deltas`` "previous snapshot" is the causal state
recomputed deterministically from the history minus its most recent record — no
new persistence (consistent with the no-vault / no-operator_state constraint).
With fewer than two records there is no previous snapshot, so every delta is
zero / empty and the Phase 8.7 ``causal_stability`` trend is "steady" at score 1.0.
"""
from dataclasses import asdict

from fastapi import APIRouter, Body, HTTPException

import phase7_storage
from phase7_alerts import compute_alerts
from phase7_analytics import (
    classify_trajectory,
    compute_coherence_trend,
    compute_drift_acceleration,
    compute_drift_velocity,
    compute_stability_forecast,
)
from phase7_causality import compute_causal_factors
from phase7_explanation import generate_causal_narrative
from phase7_telemetry import get_history
from phase8_deltas import compute_causal_deltas
from phase8_inference import build_phase7_graph, extract_primary_chain
from phase8_motifs import analyze_motifs
from phase8_multichain import generate_causal_chains, scored_chains_to_dicts
from phase8_narrative import (
    generate_causal_narrative as generate_phase8_causal_narrative,
)
from phase8_unified_narrative import generate_unified_narrative
from phase9_behavioral_motifs import analyze_behavioral_motifs
from phase9_ingest import get_action_continuity, ingest_action, store_action
from phase9_integration import (
    action_event_to_causal_node,
    integrate_action_node,
    link_action_to_variables,
)
from phase8_propagation import (
    compute_node_centrality,
    propagate_influence,
    rank_causal_explanations,
)
from phase8_stability import compute_causal_stability
from phase8_structures import chain_to_dict, graph_to_dict
from phase9_influence import propagate_action_influence
# Phase 10 (behavioral forecasting) + Phase 11 (recommendations) — the engines
# were complete + tested but never surfaced; this endpoint now emits them.
from phase10_forecast import compute_behavioral_forecast
from phase10_deltas import compute_behavioral_deltas
from phase10_stability import compute_behavioral_stability
from phase10_narrative import compute_behavioral_narrative
from phase11_recommendations import compute_action_recommendations
from phase11_narrative import compute_recommendation_narrative

# Same operator-identity seed the Phase 6 console wiring uses.
OPERATOR_ID = "clarityos-operator"

# Default history window returned to the consoles.
DEFAULT_LIMIT = 100

router = APIRouter(prefix="/operator", tags=["operator", "telemetry"])


def _telemetry_signals(records):
    """Phase 7.3/7.6/7.7 signals for a record list: ``(analytics, alerts,
    causal_factors)``. An empty list yields the neutral baseline (all ``0.0``,
    ``trajectory = "Stable"``). Pure — no I/O, wall-clock, or randomness."""
    if records:
        velocity = compute_drift_velocity(records)
        acceleration = compute_drift_acceleration(records)
        coherence_trend = compute_coherence_trend(records)
        forecast = compute_stability_forecast(velocity, acceleration, coherence_trend)
        trajectory = classify_trajectory(forecast)
    else:
        # Neutral baseline — no history to interpret yet.
        velocity = acceleration = coherence_trend = forecast = 0.0
        trajectory = "Stable"

    analytics = {
        "drift_velocity": velocity,
        "drift_acceleration": acceleration,
        "coherence_trend": coherence_trend,
        "stability_forecast": forecast,
        "trajectory": trajectory,
    }
    # Phase 7.6 — read-only operator guidance derived from the analytics.
    alerts = compute_alerts(analytics)
    # Phase 7.7 — causal drift mapping. The backend keeps no operator-action
    # log, so this resolves to the neutral "none" sentinel (recent_actions=[]).
    causal_factors = [
        asdict(factor)
        for factor in compute_causal_factors(records, recent_actions=[])
    ]
    return analytics, alerts, causal_factors


def _causal_state(records) -> dict:
    """The 8.2–8.4 causal state for a record list — ``{influence, centrality,
    motifs, chains}``. Used for the current snapshot and (on ``records[:-1]``)
    for the previous snapshot the Phase 8.6 deltas compare against. Pure."""
    analytics, alerts, causal_factors = _telemetry_signals(records)
    graph = build_phase7_graph(records, analytics, alerts, causal_factors)
    influence = propagate_influence(graph)
    centrality = compute_node_centrality(graph, influence)
    motifs = analyze_motifs(graph, influence, centrality)
    chains = scored_chains_to_dicts(
        generate_causal_chains(graph, influence, centrality, motifs)
    )
    return {
        "influence": influence,
        "centrality": centrality,
        "motifs": motifs,
        "chains": chains,
    }


def _action_delta_window(actions) -> float:
    """Deterministic delta window for the Phase 10.1 behavioral deltas: half the
    action time-span, so the current and previous trailing windows (anchored at
    the latest action) split the stream into equal halves. Falls back to 1.0
    when there are fewer than two distinct timestamps — every delta is then
    empty/neutral anyway. Pure: action timestamps are the only temporal input
    (no wall-clock)."""
    times = sorted({float(a.timestamp) for a in (actions or [])})
    if len(times) < 2:
        return 1.0
    span = times[-1] - times[0]
    return span / 2.0 if span > 0 else 1.0


@router.get("/telemetry")
def operator_telemetry() -> dict:
    """Return the operator's Phase 7 telemetry: raw history + latest record +
    on-the-fly Phase 7.3 temporal analytics (CARD 7.4).

    ``history`` is chronological (oldest first), capped at the most recent
    ``DEFAULT_LIMIT`` records; ``latest`` is the newest record (or ``None``
    when no telemetry has been recorded yet). ``analytics`` carries the drift
    velocity / acceleration, coherence trend, stability forecast, and
    trajectory classification computed from ``history``. An empty history
    yields a neutral baseline (all 0.0, ``trajectory = "Stable"``).

    Read-only: nothing is mutated or persisted.
    """
    records = get_history(OPERATOR_ID, limit=DEFAULT_LIMIT)
    history = [phase7_storage.record_to_dict(record) for record in records]
    latest = history[-1] if history else None

    # Phase 7.3/7.6/7.7 — analytics, operator guidance, and causal factors for
    # the current snapshot (neutral baseline when there is no history yet).
    analytics, alerts, causal_factors = _telemetry_signals(records)
    # Phase 7.9 — deterministic, templated narrative over the signals above.
    narrative = generate_causal_narrative(analytics, alerts, causal_factors)
    # Phase 8.1 — first-order causal graph + the most-influential chain.
    graph = build_phase7_graph(records, analytics, alerts, causal_factors)
    primary_chain = extract_primary_chain(graph)
    # Phase 8.2 — multi-hop propagation: influence, centrality, ranked explanations.
    influence = propagate_influence(graph)
    centrality = compute_node_centrality(graph, influence)
    ranked_explanations = rank_causal_explanations(graph, influence, centrality)
    # Phase 8.3 — structural motifs (feedback loops / bottlenecks / attractors).
    causal_motifs = analyze_motifs(graph, influence, centrality)
    # Phase 8.4 — ranked multi-chain causal explanations (motif-annotated).
    causal_chains = scored_chains_to_dicts(
        generate_causal_chains(graph, influence, centrality, causal_motifs)
    )
    # Phase 8.6 — causal deltas vs the previous snapshot. The "previous"
    # snapshot is the causal state recomputed from the history minus its latest
    # record (deterministic, no new persistence — mirrors the governance-diff
    # pattern). With fewer than 2 records there is no previous snapshot, so the
    # current state is compared against itself and every delta is zero / empty.
    curr_state = {
        "influence": influence,
        "centrality": centrality,
        "motifs": causal_motifs,
        "chains": causal_chains,
    }
    prev_state = _causal_state(records[:-1]) if len(records) >= 2 else curr_state
    causal_deltas = compute_causal_deltas(prev_state, curr_state)
    # Phase 8.7 — causal stability forecast over the deltas + current state
    # (stability score + trend + drivers). With no previous snapshot the deltas
    # are all zero, so the trend is "steady" at score 1.0.
    causal_stability = compute_causal_stability(causal_deltas, curr_state)
    # Phase 8.9 — unified deterministic causal narrative synthesizing the
    # strongest chain + motifs + influence highlights + deltas + stability.
    causal_narrative = generate_phase8_causal_narrative(
        curr_state, causal_deltas, causal_stability
    )
    # Phase 8.10 — unified temporal-causal narrative fusing the Phase 7.9
    # temporal narrative + Phase 7 drift / coherence / trust with the Phase 8
    # causal narrative + chains / motifs / deltas / stability.
    unified_narrative = generate_unified_narrative(
        {
            "narrative": narrative,
            "drift": latest.get("drift") if latest else None,
            "coherence_trend": analytics["coherence_trend"],
            "trust_band": latest.get("trust_band") if latest else None,
        },
        {
            "narrative": causal_narrative,
            "chains": causal_chains,
            "motifs": causal_motifs,
            "deltas": causal_deltas,
            "stability": causal_stability,
        },
    )
    # Phase 9.4 — behavioral motifs (action loops / triggers / habits /
    # bottlenecks / attractors). Computed on an action-augmented COPY of the
    # graph so the action-free `causal_*` fields above stay unchanged; with no
    # stored actions every motif set is empty.
    actions = get_action_continuity().get("actions", [])
    influence_records: list = []
    if actions:
        behavioral_graph = build_phase7_graph(records, analytics, alerts, causal_factors)
        influence_continuity: dict = {"influence": []}
        for event in sorted(actions, key=lambda e: (e.timestamp, e.id)):
            action_node = action_event_to_causal_node(event)
            integrate_action_node(action_node, behavioral_graph)
            link_action_to_variables(action_node, behavioral_graph)
            # Phase 9.3 — single-hop action->variable influence records (the
            # stream the Phase 10.1 influence delta consumes).
            propagate_action_influence(action_node, behavioral_graph, influence_continuity)
        influence_records = influence_continuity["influence"]
        behavioral_influence = propagate_influence(behavioral_graph)
        behavioral_centrality = compute_node_centrality(behavioral_graph, behavioral_influence)
        behavioral_motifs = analyze_behavioral_motifs(
            actions, behavioral_graph, behavioral_influence, behavioral_centrality,
        )
    else:
        # No actions: reuse the action-free causal graph/influence/centrality so
        # the Phase 10/11 engines run on a neutral, empty action stream.
        behavioral_graph = graph
        behavioral_influence = influence
        behavioral_centrality = centrality
        behavioral_motifs = analyze_behavioral_motifs([], graph, influence, centrality)

    # Phase 10 — behavioral forecasting, surfaced as the 10.4 `behavioral_forecast`
    # envelope {forecast (10.0), stability (10.2), narrative (10.3)}. The 10.1
    # deltas feed stability + narrative + the Phase 11 recommendations below.
    behavioral_forecast_obj = compute_behavioral_forecast(
        actions, behavioral_motifs, behavioral_graph, behavioral_influence
    )
    behavioral_deltas = compute_behavioral_deltas(
        actions, influence_records, behavioral_centrality, _action_delta_window(actions)
    )
    behavioral_stability = compute_behavioral_stability(
        behavioral_deltas, behavioral_motifs, behavioral_forecast_obj
    )
    behavioral_narrative = compute_behavioral_narrative(
        behavioral_deltas, behavioral_motifs, behavioral_forecast_obj, behavioral_stability
    )
    behavioral_forecast = {
        "forecast": behavioral_forecast_obj,
        "stability": behavioral_stability,
        "narrative": behavioral_narrative,
    }
    # Phase 11 — action recommendations (11.0) + recommendation narrative (11.1),
    # surfaced as the 11.2 `recommendation_narrative` object (it embeds the
    # recommendations, the six driver buckets, and the stability context).
    recommendations = compute_action_recommendations(
        behavioral_deltas, behavioral_motifs, behavioral_stability, behavioral_forecast_obj
    )
    recommendation_narrative = compute_recommendation_narrative(
        recommendations, behavioral_deltas, behavioral_motifs, behavioral_stability
    )
    return {
        "history": history,
        "latest": latest,
        "analytics": analytics,
        "alerts": alerts,
        "causal_factors": causal_factors,
        "narrative": narrative,
        "causal_graph": graph_to_dict(graph),
        "primary_chain": chain_to_dict(primary_chain),
        "causal_influence": influence,
        "causal_centrality": centrality,
        "ranked_explanations": ranked_explanations,
        "causal_motifs": causal_motifs,
        "causal_chains": causal_chains,
        "causal_deltas": causal_deltas,
        "causal_stability": causal_stability,
        "causal_narrative": causal_narrative,
        "unified_narrative": unified_narrative,
        "behavioral_motifs": behavioral_motifs,
        "behavioral_forecast": behavioral_forecast,
        "recommendation_narrative": recommendation_narrative,
    }


@router.post("/action")
def operator_action(action: dict = Body(...)) -> dict:
    """Phase 9.1 — ingest one raw operator action.

    Validates + normalizes the body into an ``ActionEvent`` (``ingest_action``)
    and appends it to the process-wide action continuity log (``store_action``).
    Returns ``{"status": "ok"}``. Invalid actions → ``400``. The only side effect
    is the append-only continuity write; nothing else is mutated or persisted.
    This does NOT yet enter the causal graph — that is Phase 9.2.
    """
    try:
        event = ingest_action(action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    store_action(event, get_action_continuity())
    return {"status": "ok"}
