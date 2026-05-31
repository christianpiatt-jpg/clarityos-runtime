# phase9_influence.py
"""
Phase 9.3 — Influence Propagation.

The first flow of *behavioral* influence through the causal graph: each action
node (9.2) exerts a deterministic, single-hop influence on the variables it
points at, recorded as ``InfluenceRecord`` snapshots in the continuity log. This
is the first time operator behaviour has quantitative impact inside the engine.

    compute_influence_weight(action, variable=None) -> float
    InfluenceRecord(action_id, variable_id, weight, timestamp)
    propagate_action_influence(node, graph, continuity) -> list[InfluenceRecord]
    propagate_recent_actions(continuity, graph, now, window) -> list[InfluenceRecord]

Intentionally conservative — **plumbing, not semantics**: weight is just the
action magnitude (clamped); influence is **single-hop only** (action -> variable,
no variable->variable, no action->action, no multi-hop); the graph is **never
mutated** (records go only to ``continuity["influence"]``). No inference, motif
detection (9.4), or UI (9.5). Deterministic: no randomness, no wall-clock (the
caller supplies ``now``).

Imports only the 8.0 primitives + stdlib — nothing from the CI-gated runtime
spine, vault, or operator_state.

See ``phase9_spec.md`` ("Phase 9.3 — Influence Propagation").
"""
from dataclasses import dataclass

from phase8_structures import ACTION_NODE_TYPE, CausalGraph, CausalNode


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_influence_weight(action: CausalNode, variable=None) -> float:
    """Deterministic, local influence weight: the action's magnitude
    (``CausalNode.value``) clamped to ``[-1, 1]``, or ``0.0`` when the action has
    no magnitude.

    ``variable`` is accepted for signature stability but unused — 9.3 has **no
    cross-variable effects**; weight depends only on the action.
    """
    if action.value is None:
        return 0.0
    return _clamp(float(action.value), -1.0, 1.0)


@dataclass(frozen=True)
class InfluenceRecord:
    """One single-hop influence snapshot: action ``action_id`` influenced
    variable ``variable_id`` with ``weight`` at ``timestamp`` (the action's
    time). Immutable + hashable, so the continuity log de-duplicates cleanly."""
    action_id: str
    variable_id: str
    weight: float
    timestamp: float


def _outgoing_targets(node: CausalNode, graph: CausalGraph) -> list:
    """Sorted, de-duplicated variable ids the action node points at — its 9.2
    ``action -> variable`` edges."""
    return sorted({edge.target for edge in graph.edges if edge.source == node.id})


def propagate_action_influence(node: CausalNode, graph: CausalGraph, continuity: dict) -> list:
    """Single-hop influence from one action node to each variable it points at.

    For each outgoing ``node -> variable`` edge (9.2), compute the weight and
    append an ``InfluenceRecord`` to ``continuity["influence"]`` — deduplicated
    (re-propagation never adds a duplicate snapshot) and kept sorted by
    ``(timestamp, action_id, variable_id)``. The graph is **not** mutated (no
    node/edge attribute changes, no new edges). Returns the records created this
    call.
    """
    log = continuity.setdefault("influence", [])
    existing = set(log)
    timestamp = node.timestamp if node.timestamp is not None else 0.0
    created = []
    for variable_id in _outgoing_targets(node, graph):
        weight = compute_influence_weight(node, graph.nodes.get(variable_id))
        record = InfluenceRecord(
            action_id=node.id, variable_id=variable_id, weight=weight, timestamp=timestamp,
        )
        if record in existing:
            continue
        log.append(record)
        existing.add(record)
        created.append(record)
    log.sort(key=lambda r: (r.timestamp, r.action_id, r.variable_id))
    return created


def propagate_recent_actions(continuity: dict, graph: CausalGraph, now: float, window: float) -> list:
    """Propagate influence for every recent action node in the graph.

    Recent = action nodes (``type == "action"``) with ``timestamp >= now -
    window``, processed in ``(timestamp, id)`` order; each runs through
    ``propagate_action_influence``, appending to ``continuity["influence"]``.
    ``now`` is caller-supplied (no wall-clock). Single-hop, no inference, no graph
    mutation. Returns the records created this call.
    """
    cutoff = now - window
    recent = [
        node for node in graph.nodes.values()
        if node.type == ACTION_NODE_TYPE
        and node.timestamp is not None
        and node.timestamp >= cutoff
    ]
    recent.sort(key=lambda node: (node.timestamp, node.id))
    created = []
    for node in recent:
        created.extend(propagate_action_influence(node, graph, continuity))
    return created
