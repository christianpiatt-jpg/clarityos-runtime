# phase8_structures.py
"""
Phase 8.0 — Structural Causal Primitives.

The foundational data model for Phase 8 causal reasoning — the "AST" that the
8.1–8.4 inference engine and the 8.5+ surfacing layers build on. This card
DEFINES the primitives only; it computes no inference.

Primitives:
  * CausalNode  — an event / action / state (id, type, label, timestamp)
  * CausalEdge  — a directional causal influence (source → target, weight ∈ [-1, 1])
  * CausalChain — a sequence of causally linked nodes + edges + a [0, 1] score
  * CausalGraph — nodes keyed by id + edges

Utilities: make_node, make_edge, build_chain, build_graph, graph_to_dict,
chain_to_dict (+ score_chain).

Pure / deterministic: no I/O, no wall-clock, no randomness, no side effects, and
no imports beyond the stdlib — nothing from the CI-gated runtime spine.

See ``phase8_spec.md`` ("Phase 8.0 — Structural Causal Primitives").
"""
from dataclasses import asdict, dataclass

# Phase 9.0 — canonical node type for operator actions, a first-class causal
# primitive. Action nodes are structurally ordinary CausalNodes but carry a
# *required* caller-supplied timestamp (actions are inherently temporal); build
# them deterministically via ``phase9_actions.make_action_node``.
ACTION_NODE_TYPE = "action"


@dataclass
class CausalNode:
    """An event, action, or state in the causal graph.

    ``type`` is a free tag (e.g. "action", "state", "drift", "coherence",
    "alert"); ``timestamp`` is caller-supplied (no wall-clock) and optional.
    ``value`` (Phase 8.2a) is the optional normalized intrinsic magnitude in
    [0, 1] that downstream reasoning reads directly — no label parsing.

    Phase 9.0: action nodes (``type == ACTION_NODE_TYPE``, i.e. ``"action"``)
    carry a *required* ``timestamp`` — actions are inherently temporal — plus an
    optional ``value`` (magnitude); ``phase9_actions.make_action_node`` builds them.
    """
    id: str
    type: str
    label: str
    timestamp: float | None = None
    value: float | None = None


@dataclass
class CausalEdge:
    """A directional causal influence ``source -> target``. ``weight`` is the
    signed strength of influence, in [-1, 1]."""
    source: str
    target: str
    weight: float


@dataclass
class CausalChain:
    """An ordered sequence of causally linked nodes + the edges between them,
    with an overall [0, 1] structural confidence ``score``."""
    nodes: list[CausalNode]
    edges: list[CausalEdge]
    score: float


@dataclass
class CausalGraph:
    """Nodes keyed by id + a flat edge list."""
    nodes: dict[str, CausalNode]
    edges: list[CausalEdge]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def make_node(
    id: str,
    type: str,
    label: str,
    timestamp: float | None = None,
    value: float | None = None,
) -> CausalNode:
    """Construct a CausalNode. ``timestamp`` is caller-supplied (no wall-clock);
    ``value`` is the optional normalized intrinsic magnitude in [0, 1]."""
    return CausalNode(id=id, type=type, label=label, timestamp=timestamp, value=value)


def make_edge(source: str, target: str, weight: float) -> CausalEdge:
    """Construct a CausalEdge, clamping ``weight`` to [-1, 1]."""
    return CausalEdge(source=source, target=target, weight=_clamp(float(weight), -1.0, 1.0))


def score_chain(edges: list[CausalEdge]) -> float:
    """Structural confidence of a chain: the mean absolute edge weight, in
    [0, 1]. An edgeless chain scores 0.0.

    This is a deterministic structural aggregate, not inference — real
    confidence inference arrives in 8.1–8.4.
    """
    if not edges:
        return 0.0
    return _clamp(sum(abs(e.weight) for e in edges) / len(edges), 0.0, 1.0)


def build_chain(nodes: list[CausalNode], edges: list[CausalEdge]) -> CausalChain:
    """Assemble a CausalChain from ordered nodes + edges, scoring it by the
    mean absolute edge weight."""
    return CausalChain(nodes=list(nodes), edges=list(edges), score=score_chain(edges))


def build_graph(nodes: list[CausalNode], edges: list[CausalEdge]) -> CausalGraph:
    """Assemble a CausalGraph, keying nodes by id (last write wins on a
    duplicate id) and preserving edge order."""
    return CausalGraph(nodes={node.id: node for node in nodes}, edges=list(edges))


def chain_to_dict(chain: CausalChain) -> dict:
    """JSON-serialisable dict for a CausalChain."""
    return {
        "nodes": [asdict(node) for node in chain.nodes],
        "edges": [asdict(edge) for edge in chain.edges],
        "score": chain.score,
    }


def graph_to_dict(graph: CausalGraph) -> dict:
    """JSON-serialisable dict for a CausalGraph (nodes keyed by id)."""
    return {
        "nodes": {node_id: asdict(node) for node_id, node in graph.nodes.items()},
        "edges": [asdict(edge) for edge in graph.edges],
    }
