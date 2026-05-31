# phase8_inference.py
"""
Phase 8.1 — First-Order Causal Chain Generation.

Transforms Phase 7 telemetry signals into a structural ``CausalGraph`` (built
from the 8.0 primitives) and extracts the most influential ``CausalChain``.
First-order ONLY — a shallow, deterministic mapping; deeper inference
(multi-hop, weighted propagation, motifs) is 8.2–8.4.

    build_phase7_graph(history, analytics, alerts, causal_factors) -> CausalGraph
    extract_primary_chain(graph) -> CausalChain

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the 8.0 primitives + the Phase 7 record type — nothing from the CI-gated
runtime spine.

See ``phase8_spec.md`` ("Phase 8.1 — First-Order Causal Chain Generation").
"""
from phase7_storage import TelemetryRecord  # noqa: F401  (signature/type only)
from phase8_structures import (
    CausalChain,
    CausalGraph,
    build_chain,
    build_graph,
    make_edge,
    make_node,
)

NARRATIVE_ID = "narrative"
DRIFT_VELOCITY_ID = "drift_velocity"
COHERENCE_TREND_ID = "coherence_trend"

# Deterministic edge weights for the first-order rules.
ALERT_EDGE_WEIGHT = 0.5
ANALYTICS_NARRATIVE_WEIGHT = 0.3
FACTOR_EDGE_MIN_CONTRIBUTION = 0.1  # analytics -> factor only above this

# (node_id, node_type, label-prefix) for the five analytics nodes.
_ANALYTICS_NODES = (
    (DRIFT_VELOCITY_ID, "drift", "Drift velocity"),
    ("drift_acceleration", "drift", "Drift acceleration"),
    (COHERENCE_TREND_ID, "coherence", "Coherence trend"),
    ("stability_forecast", "forecast", "Stability forecast"),
    ("trajectory", "trajectory", "Trajectory"),
)


def _fmt(value) -> str:
    return f"{float(value):.2f}"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _is_real_factor(factor) -> bool:
    """A real contributing action — not the Phase 7.7 ``none`` sentinel."""
    return factor.get("action") != "none"


def build_phase7_graph(history, analytics, alerts, causal_factors) -> CausalGraph:
    """Assemble a first-order causal graph from the Phase 7 signals.

    ``history`` is accepted for signature stability / future multi-hop
    inference (8.2+); the first-order rules derive only from ``analytics``,
    ``alerts``, and ``causal_factors``.

    Nodes: the five analytics signals, one per alert, one per *real* causal
    factor (the ``none`` sentinel is skipped), and a narrative node.
    Edges (deterministic):
      * analytics -> alert: ``drift_velocity -> alert`` (weight 0.5) when the
        alert text references "drift"; ``coherence_trend -> alert`` (0.5) when
        it references "coherence".
      * analytics -> factor: ``drift_velocity -> factor`` (weight =
        contribution) when contribution > 0.1.
      * factor -> narrative: weight = contribution.
      * analytics -> narrative: ``drift_velocity -> narrative`` (weight 0.3).
    """
    nodes = []

    # Analytics nodes (always all five). Phase 8.2a: carry the normalized
    # magnitude on the node so 8.2 reads it structurally (no label parsing).
    for node_id, node_type, prefix in _ANALYTICS_NODES:
        if node_id == "trajectory":
            label = f"Trajectory: {analytics.get('trajectory', 'Stable')}"
            value = None  # categorical — no numeric magnitude
        else:
            metric = float(analytics.get(node_id, 0.0))
            label = f"{prefix}: {_fmt(metric)}"
            value = _clamp(abs(metric), 0.0, 1.0)
        nodes.append(make_node(node_id, node_type, label, value=value))

    # Alert nodes.
    for i, alert in enumerate(alerts):
        nodes.append(make_node(f"alert_{i}", "alert", alert))

    # Causal-factor nodes (real factors only).
    real_factors = [f for f in causal_factors if _is_real_factor(f)]
    for slot, factor in enumerate(real_factors):
        contribution = float(factor.get("contribution", 0.0))
        label = f"{factor.get('action')} (contribution: {_fmt(contribution)})"
        nodes.append(make_node(
            f"factor_{slot}", "action", label, value=_clamp(contribution, 0.0, 1.0),
        ))

    # Narrative node.
    nodes.append(make_node(NARRATIVE_ID, "narrative", "Causal Narrative"))

    edges = []

    # analytics -> alerts
    for i, alert in enumerate(alerts):
        text = alert.lower()
        if "drift" in text:
            edges.append(make_edge(DRIFT_VELOCITY_ID, f"alert_{i}", ALERT_EDGE_WEIGHT))
        if "coherence" in text:
            edges.append(make_edge(COHERENCE_TREND_ID, f"alert_{i}", ALERT_EDGE_WEIGHT))

    # analytics -> factors  and  factors -> narrative
    for slot, factor in enumerate(real_factors):
        contribution = float(factor.get("contribution", 0.0))
        fid = f"factor_{slot}"
        if contribution > FACTOR_EDGE_MIN_CONTRIBUTION:
            edges.append(make_edge(DRIFT_VELOCITY_ID, fid, contribution))
        edges.append(make_edge(fid, NARRATIVE_ID, contribution))

    # analytics -> narrative
    edges.append(make_edge(DRIFT_VELOCITY_ID, NARRATIVE_ID, ANALYTICS_NARRATIVE_WEIGHT))

    return build_graph(nodes, edges)


def extract_primary_chain(graph: CausalGraph) -> CausalChain:
    """Extract the most influential path to the narrative.

    Starts from the strongest causal factor — the ``action`` node whose edge to
    the narrative has the highest weight (= contribution) — and follows it
    forward to the narrative. With no causal factors, falls back to the
    analytics -> narrative edge (``drift_velocity -> narrative``). First-order
    chains are single-hop; multi-hop traversal arrives in 8.2+.

    Score is the mean absolute edge weight (8.0 ``build_chain``); since
    first-order weights are non-negative this equals the average edge weight.
    """
    factor_edges = [
        edge for edge in graph.edges
        if edge.target == NARRATIVE_ID
        and edge.source in graph.nodes
        and graph.nodes[edge.source].type == "action"
    ]
    if factor_edges:
        strongest = max(factor_edges, key=lambda e: e.weight)
        nodes = [graph.nodes[strongest.source], graph.nodes[NARRATIVE_ID]]
        return build_chain(nodes, [strongest])

    # Fallback: analytics -> narrative.
    fallback_edges = [
        edge for edge in graph.edges
        if edge.source == DRIFT_VELOCITY_ID and edge.target == NARRATIVE_ID
    ]
    nodes = [graph.nodes[DRIFT_VELOCITY_ID], graph.nodes[NARRATIVE_ID]]
    return build_chain(nodes, fallback_edges)
