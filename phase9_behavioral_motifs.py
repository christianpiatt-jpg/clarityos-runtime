# phase9_behavioral_motifs.py
"""
Phase 9.4 — Behavioral Motif Detection (habits, triggers, action loops).

The action-layer analogue of Phase 8.3: where 8.3 saw the causal graph as a
*shape*, 9.4 sees operator *behaviour* as geometry — loops, triggers, habits,
bottlenecks, attractors over the action stream + action-augmented causal graph.

    detect_action_loops(actions) -> list[list[str]]
    detect_trigger_chains(graph) -> list[list[str]]
    detect_habits(actions) -> list[str]
    detect_action_bottlenecks(graph, influence, centrality) -> list[str]
    detect_action_attractors(graph, influence) -> list[str]
    analyze_behavioral_motifs(actions, graph, influence, centrality) -> dict

Reconciliation with the real model (as in 9.2/9.3): an action is a
``CausalNode(type="action")``; its recurring identity (for loops/habits) is the
``label`` (event ids are unique). A *causal-factor* node is the Phase-8.1
``factor_*`` node (also ``type="action"``), distinguished by id prefix.

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the 8.0 primitive + the stdlib — nothing from the CI-gated runtime spine,
vault, or operator_state.

See ``phase9_spec.md`` ("Phase 9.4 — Behavioral Motif Detection").
"""
import statistics

from phase8_structures import ACTION_NODE_TYPE, CausalGraph

# Loop bounds (mirror Phase 8.3).
MIN_LOOP_LEN = 2
MAX_LOOP_LEN = 6
MAX_LOOPS = 10

MAX_TRIGGER_CHAINS = 10

# Habit criteria.
HABIT_MIN_OCCURRENCES = 3
HABIT_SPACING_CV = 0.2       # stddev(spacing) must be < 20% of mean spacing
TOP_K = 5

# Bottleneck / attractor thresholds (mirror Phase 8.3, action-filtered).
BOTTLENECK_CENTRALITY = 0.6
BOTTLENECK_MIN_DEGREE = 3
ATTRACTOR_INFLUENCE = 0.7

# Phase-8.1 causal-factor node id prefix (factor nodes are type "action" too).
FACTOR_ID_PREFIX = "factor_"


def _is_factor_node(node) -> bool:
    """A Phase-8.1 causal-factor node (``factor_*``)."""
    return node.id.startswith(FACTOR_ID_PREFIX)


def _is_action_node(node) -> bool:
    """An operator action node — ``type == "action"`` but NOT a causal factor."""
    return node.type == ACTION_NODE_TYPE and not _is_factor_node(node)


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


def _canonical_rotation(seq) -> tuple:
    """The lexicographically smallest rotation of ``seq`` (cycle canonical
    form), so equivalent loops collapse to one representative."""
    rotations = [tuple(seq[k:]) + tuple(seq[:k]) for k in range(len(seq))]
    return min(rotations)


def detect_action_loops(actions) -> list:
    """Repeated action sequences (cycles) over the timestamp-ordered action
    *labels*.

    A loop of length ``L`` (2–6) exists where a label recurs after ``L`` steps
    (``labels[i] == labels[i+L]``) and the ``L`` intervening labels are distinct
    (a simple cycle). Each loop is canonicalized to its lexicographically
    smallest rotation; loops are de-duplicated, sorted lexicographically, and
    capped at ``MAX_LOOPS``. Deterministic.
    """
    ordered = sorted(actions, key=lambda a: (a.timestamp, a.id))
    labels = [a.label for a in ordered]
    found = set()
    for i in range(len(labels)):
        for length in range(MIN_LOOP_LEN, MAX_LOOP_LEN + 1):
            j = i + length
            if j >= len(labels):
                break
            if labels[i] != labels[j]:
                continue
            body = labels[i:j]
            if len(set(body)) == length:          # simple cycle (distinct)
                found.add(_canonical_rotation(body))
    loops = sorted(found)
    return [list(loop) for loop in loops[:MAX_LOOPS]]


def detect_trigger_chains(graph: CausalGraph) -> list:
    """``action -> causal_factor -> action`` chains over positive-weight edges.

    Only edges with ``weight > 0`` are followed. Chains are sorted
    lexicographically, de-duplicated, and capped at ``MAX_TRIGGER_CHAINS``.
    Deterministic. (With no ``action -> factor`` edges in the graph this is
    ``[]``.)
    """
    pos = {}
    for edge in graph.edges:
        if edge.weight > 0 and edge.source in graph.nodes and edge.target in graph.nodes:
            pos.setdefault(edge.source, set()).add(edge.target)

    chains = []
    seen = set()
    for action_id in sorted(pos):
        if not _is_action_node(graph.nodes[action_id]):
            continue
        for factor_id in sorted(pos.get(action_id, ())):
            if not _is_factor_node(graph.nodes[factor_id]):
                continue
            for target_id in sorted(pos.get(factor_id, ())):
                if not _is_action_node(graph.nodes[target_id]):
                    continue
                key = (action_id, factor_id, target_id)
                if key in seen:
                    continue
                seen.add(key)
                chains.append([action_id, factor_id, target_id])
    chains.sort()
    return chains[:MAX_TRIGGER_CHAINS]


def detect_habits(actions) -> list:
    """Action labels that recur ``>= 3`` times with low timing variance —
    ``stddev(inter-event spacing) < 20% of mean spacing`` (population stddev).
    Returns the top ``TOP_K`` by occurrence count (ties by label). Deterministic.
    """
    by_label = {}
    for action in actions:
        by_label.setdefault(action.label, []).append(action.timestamp)

    habits = []
    for label, timestamps in by_label.items():
        if len(timestamps) < HABIT_MIN_OCCURRENCES:
            continue
        ordered = sorted(timestamps)
        spacings = [ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)]
        mean_spacing = statistics.mean(spacings)
        if mean_spacing <= 0:
            continue
        if statistics.pstdev(spacings) < HABIT_SPACING_CV * mean_spacing:
            habits.append((label, len(timestamps)))

    habits.sort(key=lambda item: (-item[1], item[0]))
    return [label for label, _ in habits[:TOP_K]]


def detect_action_bottlenecks(graph: CausalGraph, influence: dict, centrality: dict) -> list:
    """Action nodes with ``centrality > 0.6`` AND total degree ``>= 3``. Top
    ``TOP_K`` by centrality (ties by node id). Action-filtered analogue of 8.3."""
    degrees = _all_degrees(graph)
    candidates = []
    for node_id, node in graph.nodes.items():
        if not _is_action_node(node):
            continue
        inbound, outbound = degrees[node_id]
        if centrality.get(node_id, 0.0) > BOTTLENECK_CENTRALITY and (inbound + outbound) >= BOTTLENECK_MIN_DEGREE:
            candidates.append(node_id)
    candidates.sort(key=lambda nid: (-centrality.get(nid, 0.0), nid))
    return candidates[:TOP_K]


def detect_action_attractors(graph: CausalGraph, influence: dict) -> list:
    """Action nodes with ``influence > 0.7`` AND more inbound than outbound
    edges. Top ``TOP_K`` by influence (ties by node id). Action-filtered
    analogue of 8.3."""
    degrees = _all_degrees(graph)
    candidates = []
    for node_id, node in graph.nodes.items():
        if not _is_action_node(node):
            continue
        inbound, outbound = degrees[node_id]
        if influence.get(node_id, 0.0) > ATTRACTOR_INFLUENCE and inbound > outbound:
            candidates.append(node_id)
    candidates.sort(key=lambda nid: (-influence.get(nid, 0.0), nid))
    return candidates[:TOP_K]


def analyze_behavioral_motifs(actions, graph: CausalGraph, influence: dict, centrality: dict) -> dict:
    """All five behavioral-motif families in one read-only dict."""
    return {
        "action_loops": detect_action_loops(actions),
        "trigger_chains": detect_trigger_chains(graph),
        "habits": detect_habits(actions),
        "action_bottlenecks": detect_action_bottlenecks(graph, influence, centrality),
        "action_attractors": detect_action_attractors(graph, influence),
    }
