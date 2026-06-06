# phase8_propagation.py
"""
Phase 8.2 — Multi-Hop Causal Propagation (weighted influence engine).

The first *reasoning* layer over the 8.1 causal graph: it propagates influence
across edges, scores node centrality, and ranks causal explanations. This is
where ClarityOS reasons across the graph rather than only building it. Deeper
structure (motifs, multi-chain) is 8.3–8.4.

    propagate_influence(graph) -> dict[node_id, float]          # influence in [0, 1]
    compute_node_centrality(graph, influence) -> dict[node_id, float]
    rank_causal_explanations(graph, influence, centrality) -> list[dict]

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the 8.0 primitive types + stdlib — nothing from the CI-gated runtime spine.

Note on intrinsic weights: ``propagate_influence`` takes only the graph, so the
numeric magnitude for analytics / factor nodes is parsed from the node label
(8.1 formats these deterministically). Alerts/narrative use fixed weights by
type.

See ``phase8_spec.md`` ("Phase 8.2 — Multi-Hop Causal Propagation").
"""
import re

from phase8_structures import CausalGraph

# Propagation depth.
MAX_STEPS = 3

# Fixed intrinsic weights by node type.
ALERT_INTRINSIC = 0.5
NARRATIVE_INTRINSIC = 0.3

_FLOAT_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _parse_last_float(text: str):
    """Last numeric token in ``text`` (e.g. the value/contribution 8.1 writes
    into a node label), or ``None`` when there is none."""
    matches = _FLOAT_RE.findall(text)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def _intrinsic_weight(node) -> float:
    """A node's starting influence, in [0, 1].

    Precedence (Phase 8.2a):
      1. ``node.value`` when present — the structured normalized magnitude
         (preferred; no coupling to label text).
      2. type-fixed weights: alert → 0.5, narrative → 0.3.
      3. DEPRECATED fallback — parse the magnitude from the label (legacy /
         hand-built nodes that carry no ``value``); a label with no number
         (e.g. "Trajectory: Diverging") → 0.0.
    """
    if node.value is not None:
        return _clamp(abs(node.value), 0.0, 1.0)
    if node.type == "alert":
        return ALERT_INTRINSIC
    if node.type == "narrative":
        return NARRATIVE_INTRINSIC
    parsed = _parse_last_float(node.label)
    if parsed is None:
        return 0.0
    return _clamp(abs(parsed), 0.0, 1.0)


def propagate_influence(graph: CausalGraph) -> dict:
    """Deterministic weighted propagation over the graph.

    Each node starts at its intrinsic weight; for ``MAX_STEPS`` iterations,
    ``influence[target] += influence[source] * edge.weight`` (computed
    synchronously from the start-of-step values, so the result is independent of
    edge order), clamped to [0, 1] after each step. Returns a dict in sorted
    node-id order.
    """
    node_ids = sorted(graph.nodes.keys())
    influence = {nid: _intrinsic_weight(graph.nodes[nid]) for nid in node_ids}

    for _ in range(MAX_STEPS):
        delta = {nid: 0.0 for nid in node_ids}
        for edge in graph.edges:
            if edge.source in influence and edge.target in delta:
                delta[edge.target] += influence[edge.source] * edge.weight
        influence = {
            nid: _clamp(influence[nid] + delta[nid], 0.0, 1.0) for nid in node_ids
        }

    return {nid: influence[nid] for nid in node_ids}


def compute_node_centrality(graph: CausalGraph, influence: dict) -> dict:
    """Causal importance per node, in [0, 1].

    raw = inbound influence (Σ influence[source] over edges into the node)
        + outbound influence (Σ influence[target] over edges out of the node)
        + intrinsic weight
    normalized by the maximum raw value across nodes (→ [0, 1]); all zeros when
    no node has any.
    """
    node_ids = sorted(graph.nodes.keys())
    # Single pass over the edge list accumulates inbound / outbound influence per
    # node (vs a per-node rescan of every edge — O(N·E) → O(N+E)). The
    # accumulation order for each node matches the previous edge-iteration order,
    # so the float results are byte-identical.
    inbound = {nid: 0.0 for nid in node_ids}
    outbound = {nid: 0.0 for nid in node_ids}
    for edge in graph.edges:
        if edge.target in inbound:
            inbound[edge.target] += influence.get(edge.source, 0.0)
        if edge.source in outbound:
            outbound[edge.source] += influence.get(edge.target, 0.0)
    raw = {
        nid: inbound[nid] + outbound[nid] + _intrinsic_weight(graph.nodes[nid])
        for nid in node_ids
    }

    max_raw = max(raw.values()) if raw else 0.0
    if max_raw <= 0.0:
        return {nid: 0.0 for nid in node_ids}
    return {nid: _clamp(raw[nid] / max_raw, 0.0, 1.0) for nid in node_ids}


def rank_causal_explanations(graph: CausalGraph, influence: dict, centrality: dict) -> list:
    """Per-node explanation entries, sorted by score (mean of influence +
    centrality) descending. Ties keep sorted-node-id order (stable sort)."""
    explanations = []
    for nid in sorted(graph.nodes.keys()):
        node = graph.nodes[nid]
        inf = influence.get(nid, 0.0)
        cen = centrality.get(nid, 0.0)
        explanations.append({
            "node": nid,
            "label": node.label,
            "influence": inf,
            "centrality": cen,
            "score": (inf + cen) / 2.0,
        })
    explanations.sort(key=lambda entry: entry["score"], reverse=True)
    return explanations
