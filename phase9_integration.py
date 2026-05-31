# phase9_integration.py
"""
Phase 9.2 — Action -> Causal Graph Integration.

Takes ingested ``ActionEvent``s (9.1) and folds them into the **existing**
Phase-8 ``CausalGraph`` as ``CausalNode``s of type ``"action"`` (9.0), wired to
the system variables they influence with ordinary ``CausalEdge``s. There is no
parallel "action graph": actions become first-class citizens of the one graph
that 8.2 propagation, 8.3 motifs, 8.4 multi-chains, 8.6 deltas, 8.7 stability,
and 8.10 narrative already read.

    action_event_to_causal_node(event) -> CausalNode      # = make_action_node (9.0)
    resolve_action_targets(node, graph) -> list[str]      # variable registry ∩ graph
    integrate_action_node(node, graph) -> None            # insert into graph.nodes
    link_action_to_variables(node, graph) -> list[CausalEdge]
    integrate_recent_actions(continuity, graph, now, window) -> None

9.2 is **pure structure**: it inserts nodes + edges. No propagation, no influence
inference, no motif detection (9.3/9.4), no operator_state writes, no UI (9.5).
Edges carry a structural placeholder weight (``ACTION_EDGE_WEIGHT``); 9.3
replaces it with real influence weights. Deterministic: no randomness, no
wall-clock (the caller supplies ``now``).

Imports only the 8.0 primitives + the 9.0/9.1 modules + stdlib — nothing from
the CI-gated runtime spine, vault, or operator_state.

See ``phase9_spec.md`` ("Phase 9.2 — Action -> Causal Graph Integration").
"""
from phase8_structures import CausalGraph, CausalNode, make_edge
from phase9_actions import ActionEvent, make_action_node
from phase9_ingest import load_recent_actions

# The Phase-8 system-variable registry: the analytics node ids an action
# structurally influences (drift / coherence / forecast / trajectory). An action
# is linked to whichever of these are present in the graph.
SYSTEM_VARIABLE_IDS = (
    "drift_velocity",
    "drift_acceleration",
    "coherence_trend",
    "stability_forecast",
    "trajectory",
)

# Structural placeholder weight for action -> variable edges. 9.2 encodes the
# edge *structure* only; 9.3 replaces this with real influence weights.
ACTION_EDGE_WEIGHT = 1.0


def action_event_to_causal_node(event: ActionEvent) -> CausalNode:
    """Map an ``ActionEvent`` to a ``CausalNode`` of type ``"action"``.

    A thin alias over the 9.0 primitive (``make_action_node``) so there is one
    mapping and no parallel node type — ``magnitude`` lands in ``value``,
    ``timestamp`` passes through. Deterministic; no inference.
    """
    return make_action_node(event)


def resolve_action_targets(node: CausalNode, graph: CausalGraph) -> list:
    """The variable node ids an action connects to: the ``SYSTEM_VARIABLE_IDS``
    registry intersected with the nodes actually present in ``graph``, sorted.
    Deterministic, no inference (``node`` is accepted for signature stability /
    future per-action targeting)."""
    present = set(graph.nodes)
    return sorted(vid for vid in SYSTEM_VARIABLE_IDS if vid in present)


def integrate_action_node(node: CausalNode, graph: CausalGraph) -> None:
    """Insert an action node into the shared ``CausalGraph`` (keyed by id).

    Idempotent on id — re-integrating the same action overwrites its own entry
    and never mutates *other* nodes. No deletion.
    """
    graph.nodes[node.id] = node


def link_action_to_variables(node: CausalNode, graph: CausalGraph) -> list:
    """Create structural ``action -> variable`` edges and append them to
    ``graph.edges``.

    One ``CausalEdge(node.id, variable, ACTION_EDGE_WEIGHT)`` per resolved
    target, skipping any ``(source, target)`` pair already present (so repeated
    integration is idempotent and never accumulates duplicate edges). The edge
    list is kept deterministically sorted by ``(source, target)``. Returns the
    edges created this call. Only ``action -> variable`` edges are made — never
    the reverse (directionality per 9.0 §3.5; reverse/weighted edges are 9.3).
    """
    existing = {(edge.source, edge.target) for edge in graph.edges}
    created = []
    for target_id in resolve_action_targets(node, graph):
        key = (node.id, target_id)
        if key in existing:
            continue
        edge = make_edge(node.id, target_id, ACTION_EDGE_WEIGHT)
        graph.edges.append(edge)
        created.append(edge)
        existing.add(key)
    graph.edges.sort(key=lambda edge: (edge.source, edge.target))
    return created


def integrate_recent_actions(continuity, graph: CausalGraph, now: float, window: float) -> None:
    """Pull recent actions from the 9.1 continuity log, convert each to a
    ``CausalNode(type="action")``, insert it, and link it to the system
    variables.

    Actions are processed in ``(timestamp, id)`` order for determinism. ``now``
    is caller-supplied (no wall-clock). No propagation, no inference — structure
    only.
    """
    events = load_recent_actions(continuity, now, window)
    for event in sorted(events, key=lambda e: (e.timestamp, e.id)):
        node = action_event_to_causal_node(event)
        integrate_action_node(node, graph)
        link_action_to_variables(node, graph)
