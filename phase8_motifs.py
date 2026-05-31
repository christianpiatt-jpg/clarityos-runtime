# phase8_motifs.py
"""
Phase 8.3 — Structural Motif Detection (loops, bottlenecks, attractors).

The first time ClarityOS sees the causal graph as a *shape*, not just edges:

    detect_feedback_loops(graph) -> list[list[str]]            # cycles, length 2–6
    detect_bottlenecks(graph, influence, centrality) -> list[str]
    detect_attractors(graph, influence) -> list[str]
    analyze_motifs(graph, influence, centrality) -> dict

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the 8.0 primitive type + stdlib — nothing from the CI-gated runtime spine.

See ``phase8_spec.md`` ("Phase 8.3 — Structural Motif Detection").
"""
from phase8_structures import CausalGraph

# Loop detection bounds.
MIN_LOOP_LEN = 2
MAX_LOOP_LEN = 6
MAX_LOOPS = 10

# Motif thresholds.
BOTTLENECK_CENTRALITY = 0.6
BOTTLENECK_MIN_DEGREE = 3
ATTRACTOR_INFLUENCE = 0.7
TOP_K = 5


def _adjacency(graph: CausalGraph) -> dict:
    """source -> sorted, de-duplicated list of targets (deterministic)."""
    adj = {nid: [] for nid in graph.nodes}
    for edge in graph.edges:
        if edge.source in adj and edge.target in graph.nodes:
            adj[edge.source].append(edge.target)
    return {nid: sorted(set(targets)) for nid, targets in adj.items()}


def _all_degrees(graph: CausalGraph) -> dict:
    """``{node_id: (inbound_count, outbound_count)}`` for every node, computed in
    a single pass over the edge list (vs a per-node rescan — O(N·E) → O(N+E)).
    Integer counts, so the result is identical to the previous per-node form."""
    inbound = {nid: 0 for nid in graph.nodes}
    outbound = {nid: 0 for nid in graph.nodes}
    for edge in graph.edges:
        if edge.target in inbound:
            inbound[edge.target] += 1
        if edge.source in outbound:
            outbound[edge.source] += 1
    return {nid: (inbound[nid], outbound[nid]) for nid in graph.nodes}


def detect_feedback_loops(graph: CausalGraph) -> list:
    """Directed simple cycles of length 2–6, each as a list of node ids.

    Deterministic DFS rooted at each cycle's *minimum* node id (only nodes >
    the root are explored), so every cycle is found exactly once already in
    canonical (min-first) form — no rotational duplicates. Loops are sorted
    lexicographically and capped at ``MAX_LOOPS``.
    """
    adj = _adjacency(graph)
    found = set()
    loops = []

    def dfs(start, current, path):
        for nxt in adj[current]:
            if nxt == start:
                if len(path) >= MIN_LOOP_LEN:
                    key = tuple(path)
                    if key not in found:
                        found.add(key)
                        loops.append(list(path))
            elif nxt > start and nxt not in path and len(path) < MAX_LOOP_LEN:
                path.append(nxt)
                dfs(start, nxt, path)
                path.pop()

    for start in sorted(adj.keys()):
        dfs(start, start, [start])

    loops.sort()
    return loops[:MAX_LOOPS]


def detect_bottlenecks(graph: CausalGraph, influence: dict, centrality: dict) -> list:
    """Nodes with ``centrality > 0.6`` AND total degree (inbound + outbound) >=
    3. Returns the top ``TOP_K`` by centrality (ties broken by node id)."""
    degrees = _all_degrees(graph)
    candidates = []
    for nid in graph.nodes:
        inbound, outbound = degrees[nid]
        if centrality.get(nid, 0.0) > BOTTLENECK_CENTRALITY and (inbound + outbound) >= BOTTLENECK_MIN_DEGREE:
            candidates.append(nid)
    candidates.sort(key=lambda nid: (-centrality.get(nid, 0.0), nid))
    return candidates[:TOP_K]


def detect_attractors(graph: CausalGraph, influence: dict) -> list:
    """Nodes with ``influence > 0.7`` AND more inbound than outbound edges.
    Returns the top ``TOP_K`` by influence (ties broken by node id)."""
    degrees = _all_degrees(graph)
    candidates = []
    for nid in graph.nodes:
        inbound, outbound = degrees[nid]
        if influence.get(nid, 0.0) > ATTRACTOR_INFLUENCE and inbound > outbound:
            candidates.append(nid)
    candidates.sort(key=lambda nid: (-influence.get(nid, 0.0), nid))
    return candidates[:TOP_K]


def analyze_motifs(graph: CausalGraph, influence: dict, centrality: dict) -> dict:
    """All three motif families in one read-only dict."""
    return {
        "feedback_loops": detect_feedback_loops(graph),
        "bottlenecks": detect_bottlenecks(graph, influence, centrality),
        "attractors": detect_attractors(graph, influence),
    }
