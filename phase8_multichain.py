# phase8_multichain.py
"""
Phase 8.4 — Multi-Chain Causal Explanations.

The card that turns the Phase-8 causal stack (8.0 primitives, 8.1 graph, 8.2
propagation, 8.3 motifs) into a *ranked set* of structured explanations. Where
8.1 extracts the single most-influential chain, 8.4 enumerates several distinct,
structurally-valid causal paths to the narrative — each scored by strength and
annotated with the motif context (bottleneck / attractor / feedback-loop
involvement) it passes through.

    generate_causal_chains(graph, influence, centrality, motifs=None) -> list[dict]
    scored_chains_to_dicts(scored_chains) -> list[dict]   # JSON-serialisable

**Output shape (documented choice).** The card offered two options — extend the
8.0 ``CausalChain`` with a ``metadata`` dict, or return a parallel
``list[dict]``. This module takes the second: ``generate_causal_chains`` returns
``[{"chain": CausalChain, "score": float, "motifs": {...}}, ...]``. The 8.0
``CausalChain`` primitive is left untouched; the built chain carries the 8.4
influence-aware ``score`` in its ``.score`` field, so ``scored_chains_to_dicts``
is just ``chain_to_dict`` (which already emits ``{nodes, edges, score}``) plus a
``"motifs"`` key.

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the 8.0 primitive types + stdlib — nothing from the CI-gated runtime spine.

See ``phase8_spec.md`` ("Phase 8.4 — Multi-Chain Causal Explanations").
"""
from phase8_structures import CausalChain, CausalGraph, chain_to_dict

# Terminal (summary) node: prefer a node tagged with this type; fall back to the
# conventional id when no node carries the type.
NARRATIVE_TYPE = "narrative"
NARRATIVE_ID = "narrative"

# Search bounds.
TOP_N_STARTS = 5         # candidate start nodes (by influence + centrality)
MAX_PATHS_PER_START = 3  # K — simple paths collected per start, in DFS order
MAX_PATH_DEPTH = 6       # maximum number of edges (hops) in a path


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _find_target(graph: CausalGraph):
    """The terminal summary node: the lexicographically-smallest node whose
    ``type`` is ``"narrative"``; else the node with id ``"narrative"``; else
    ``None`` (no target → no chains)."""
    narrative_ids = sorted(
        nid for nid, node in graph.nodes.items() if node.type == NARRATIVE_TYPE
    )
    if narrative_ids:
        return narrative_ids[0]
    if NARRATIVE_ID in graph.nodes:
        return NARRATIVE_ID
    return None


def _adjacency(graph: CausalGraph) -> dict:
    """source -> sorted, de-duplicated list of targets (deterministic), over
    edges whose endpoints are both real nodes."""
    adj = {nid: [] for nid in graph.nodes}
    for edge in graph.edges:
        if edge.source in adj and edge.target in graph.nodes:
            adj[edge.source].append(edge.target)
    return {nid: sorted(set(targets)) for nid, targets in adj.items()}


def _edge_lookup(graph: CausalGraph) -> dict:
    """(source, target) -> the strongest ``CausalEdge`` for that pair (max
    weight; deterministic). Collapses parallel edges so a node sequence maps to
    exactly one chain."""
    lookup = {}
    for edge in graph.edges:
        if edge.source not in graph.nodes or edge.target not in graph.nodes:
            continue
        key = (edge.source, edge.target)
        if key not in lookup or edge.weight > lookup[key].weight:
            lookup[key] = edge
    return lookup


def _start_score(nid: str, influence: dict, centrality: dict) -> float:
    """A node's importance as a chain start — the same mean used by 8.2's
    ``rank_causal_explanations`` (``(influence + centrality) / 2``)."""
    return (influence.get(nid, 0.0) + centrality.get(nid, 0.0)) / 2.0


def _select_starts(graph: CausalGraph, influence: dict, centrality: dict, target: str) -> list:
    """Top ``TOP_N_STARTS`` nodes by start score (desc), excluding the target.
    Ties break by node id (ascending) for determinism."""
    candidates = [nid for nid in graph.nodes if nid != target]
    candidates.sort(key=lambda nid: (-_start_score(nid, influence, centrality), nid))
    return candidates[:TOP_N_STARTS]


def _find_paths(adj: dict, start: str, target: str) -> list:
    """Up to ``MAX_PATHS_PER_START`` deterministic simple paths ``start ->
    target``, each using at most ``MAX_PATH_DEPTH`` edges.

    DFS explores neighbours in ascending node-id order (``adj`` is sorted) and
    never revisits a node in the current path; collection stops once the
    per-start cap is reached, so the kept paths are the first ``K`` in DFS
    order.
    """
    paths = []

    def dfs(current: str, path: list):
        if len(paths) >= MAX_PATHS_PER_START:
            return
        if current == target:
            paths.append(list(path))
            return
        # ``len(path) - 1`` edges used so far; stop if we can't add another.
        if len(path) - 1 >= MAX_PATH_DEPTH:
            return
        for nxt in adj.get(current, []):
            if nxt in path:
                continue
            path.append(nxt)
            dfs(nxt, path)
            path.pop()
            if len(paths) >= MAX_PATHS_PER_START:
                return

    dfs(start, [start])
    return paths


def _score_path(edge_weights: list, node_influences: list) -> float:
    """The 8.4 chain score, in ``[0, 1]``.

    ``edge_score`` = signed mean edge weight along the path, clamped to
    ``[-1, 1]`` (an edgeless path → 0.0). ``node_score`` = mean node influence
    along the path (already in ``[0, 1]``). The signed edge score is linearly
    remapped to ``[0, 1]`` (``(edge_score + 1) / 2``) and averaged with the node
    score, then clamped:

        chain_score = clamp( ((edge_score + 1) / 2 + node_score) / 2, 0, 1 )
    """
    if edge_weights:
        edge_score = _clamp(sum(edge_weights) / len(edge_weights), -1.0, 1.0)
    else:
        edge_score = 0.0
    node_score = sum(node_influences) / len(node_influences) if node_influences else 0.0
    normalized_edge = (edge_score + 1.0) / 2.0
    return _clamp((normalized_edge + node_score) / 2.0, 0.0, 1.0)


def _annotate_motifs(path: list, motifs) -> dict:
    """Motif context for a path: ``True`` when any node on the path is a
    detected bottleneck / attractor / member of a feedback loop. A ``None`` or
    empty ``motifs`` yields all ``False``."""
    motifs = motifs or {}
    bottlenecks = set(motifs.get("bottlenecks", []))
    attractors = set(motifs.get("attractors", []))
    loop_nodes = set()
    for loop in motifs.get("feedback_loops", []):
        loop_nodes.update(loop)
    path_nodes = set(path)
    return {
        "passes_bottleneck": bool(path_nodes & bottlenecks),
        "passes_attractor": bool(path_nodes & attractors),
        "in_feedback_loop": bool(path_nodes & loop_nodes),
    }


def _make_entry(path: list, graph: CausalGraph, lookup: dict, influence: dict, motifs) -> dict:
    """Build the scored-chain entry for a node-id ``path``.

    The chain's edges are the strongest edge for each consecutive pair; its
    ``CausalChain.score`` carries the 8.4 chain score (not the 8.0 structural
    mean-|weight|), so serialization needs no override.
    """
    chain_edges = [lookup[(path[i], path[i + 1])] for i in range(len(path) - 1)]
    chain_score = _score_path(
        [edge.weight for edge in chain_edges],
        [influence.get(nid, 0.0) for nid in path],
    )
    chain = CausalChain(
        nodes=[graph.nodes[nid] for nid in path],
        edges=chain_edges,
        score=chain_score,
    )
    return {"chain": chain, "score": chain_score, "motifs": _annotate_motifs(path, motifs)}


def _fallback_entry(graph: CausalGraph, lookup: dict, influence: dict, motifs, target: str):
    """The trivial single-edge explanation: the strongest edge into the target
    (ties by source id). On the first-order 8.1 graph this is the always-present
    ``drift_velocity -> narrative`` analytics→narrative edge. Returns ``None``
    when nothing points at the target."""
    incoming = [key for key in lookup if key[1] == target and key[0] in graph.nodes]
    if not incoming:
        return None
    incoming.sort(key=lambda key: (-lookup[key].weight, key[0]))
    source = incoming[0][0]
    return _make_entry([source, target], graph, lookup, influence, motifs)


def generate_causal_chains(graph: CausalGraph, influence: dict, centrality: dict, motifs=None) -> list:
    """Generate a ranked set of distinct, structurally-valid causal chains.

    For each of the top ``TOP_N_STARTS`` nodes (by ``(influence + centrality) /
    2``, excluding the narrative target), find up to ``MAX_PATHS_PER_START``
    simple paths to the narrative via deterministic depth-limited DFS. Each path
    becomes a scored ``CausalChain`` annotated with motif context. Chains with
    identical node sequences are merged (kept once). When no chain is produced
    (no strong start reaches the narrative — e.g. empty ``influence``), falls
    back to the strongest single edge into the narrative.

    Returns ``[{"chain": CausalChain, "score": float, "motifs": {...}}, ...]``
    sorted by ``score`` descending; ties keep node-id-sequence order (stable,
    deterministic).
    """
    influence = influence or {}
    centrality = centrality or {}

    target = _find_target(graph)
    if target is None:
        return []

    adj = _adjacency(graph)
    lookup = _edge_lookup(graph)

    scored = []
    seen = set()
    for start in _select_starts(graph, influence, centrality, target):
        for path in _find_paths(adj, start, target):
            key = tuple(path)
            if key in seen:  # merge identical node sequences
                continue
            seen.add(key)
            scored.append(_make_entry(path, graph, lookup, influence, motifs))

    if not scored:
        fallback = _fallback_entry(graph, lookup, influence, motifs, target)
        if fallback is not None:
            scored.append(fallback)

    scored.sort(key=lambda entry: (-entry["score"], tuple(n.id for n in entry["chain"].nodes)))
    return scored


def scored_chains_to_dicts(scored_chains: list) -> list:
    """JSON-serialisable form of ``generate_causal_chains`` output: each entry
    is ``chain_to_dict`` (``{nodes, edges, score}``) plus a ``"motifs"`` key —
    ``{nodes, edges, score, motifs}``."""
    return [
        {**chain_to_dict(entry["chain"]), "motifs": entry["motifs"]}
        for entry in scored_chains
    ]
