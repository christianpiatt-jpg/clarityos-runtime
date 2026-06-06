# tests/test_phase9_integration.py
#
# CARD 9.2 — action -> causal graph integration: ActionEvent -> CausalNode
# (type "action") folded into the EXISTING Phase-8 CausalGraph with ordinary
# action -> variable CausalEdges. Pure structure — no propagation, no inference
# (those are 9.3/9.4).
import json
from copy import deepcopy

import pytest

from phase8_structures import CausalNode, build_graph, graph_to_dict, make_edge, make_node
from phase8_inference import build_phase7_graph
from phase8_propagation import propagate_influence
from phase9_actions import ActionEvent
from phase9_ingest import ingest_action, store_action
from phase9_integration import (
    ACTION_EDGE_WEIGHT,
    SYSTEM_VARIABLE_IDS,
    action_event_to_causal_node,
    integrate_action_node,
    integrate_recent_actions,
    link_action_to_variables,
    resolve_action_targets,
)


def _analytics(v=0.5, a=0.0, c=-0.3, sf=0.4, trajectory="Stable"):
    return {
        "drift_velocity": v, "drift_acceleration": a, "coherence_trend": c,
        "stability_forecast": sf, "trajectory": trajectory,
    }


def _base_graph():
    """The real Phase-8 first-order graph (5 analytics variables + narrative)."""
    return build_phase7_graph(
        [], _analytics(), [], [{"action": "none", "correlation": 0.0, "contribution": 0.0}],
    )


def _event(id="act_1", label="Adjusted parameter X", ts=100.0, mag=0.7):
    return ActionEvent(id=id, label=label, timestamp=ts, magnitude=mag)


# ---------------------------------------------------------------------------
# ActionEvent -> CausalNode (no parallel node type)
# ---------------------------------------------------------------------------

def test_action_event_to_causal_node():
    node = action_event_to_causal_node(_event(mag=0.7))
    assert isinstance(node, CausalNode)
    assert node.type == "action"
    assert node.id == "act_1"
    assert node.label == "Adjusted parameter X"
    assert node.timestamp == 100.0
    assert node.value == 0.7        # magnitude -> value (no payload)


# ---------------------------------------------------------------------------
# Node insertion
# ---------------------------------------------------------------------------

def test_integrate_action_node_inserts_into_shared_nodes():
    graph = _base_graph()
    before = len(graph.nodes)
    integrate_action_node(action_event_to_causal_node(_event()), graph)
    assert "act_1" in graph.nodes
    assert graph.nodes["act_1"].type == "action"
    assert len(graph.nodes) == before + 1


def test_integration_does_not_mutate_existing_nodes():
    graph = _base_graph()
    narrative_before = deepcopy(graph.nodes["narrative"])
    integrate_action_node(action_event_to_causal_node(_event()), graph)
    assert graph.nodes["narrative"] == narrative_before   # untouched


def test_no_node_deletion():
    graph = _base_graph()
    original_ids = set(graph.nodes)
    integrate_action_node(action_event_to_causal_node(_event()), graph)
    assert original_ids <= set(graph.nodes)               # nothing removed


# ---------------------------------------------------------------------------
# Target resolution + edges
# ---------------------------------------------------------------------------

def test_resolve_action_targets_present_subset_sorted():
    graph = _base_graph()
    targets = resolve_action_targets(action_event_to_causal_node(_event()), graph)
    assert targets == sorted(SYSTEM_VARIABLE_IDS)          # all 5 present, sorted


def test_resolve_targets_only_present_variables():
    # A graph with only two of the registry variables → only those are targeted.
    graph = build_graph(
        [make_node("drift_velocity", "drift", "d", value=0.5),
         make_node("coherence_trend", "coherence", "c", value=0.3)],
        [],
    )
    targets = resolve_action_targets(action_event_to_causal_node(_event()), graph)
    assert targets == ["coherence_trend", "drift_velocity"]


def test_link_creates_action_to_variable_edges():
    graph = _base_graph()
    node = action_event_to_causal_node(_event())
    integrate_action_node(node, graph)
    created = link_action_to_variables(node, graph)

    assert len(created) == len(SYSTEM_VARIABLE_IDS)
    for edge in created:
        assert edge.source == "act_1"
        assert edge.target in SYSTEM_VARIABLE_IDS
        assert edge.weight == ACTION_EDGE_WEIGHT == 1.0
    # No reverse edges: nothing targets the action node.
    assert not any(e.target == "act_1" for e in graph.edges)


def test_edges_sorted_by_source_target():
    graph = _base_graph()
    node = action_event_to_causal_node(_event())
    integrate_action_node(node, graph)
    link_action_to_variables(node, graph)
    keys = [(e.source, e.target) for e in graph.edges]
    assert keys == sorted(keys)


# ---------------------------------------------------------------------------
# Batch integration + determinism + idempotency
# ---------------------------------------------------------------------------

def _continuity_with(*events):
    continuity = {}
    for e in events:
        store_action(e, continuity)
    return continuity


def test_integrate_recent_actions_batch():
    continuity = _continuity_with(
        _event(id="a", ts=90.0), _event(id="b", ts=100.0), _event(id="c", ts=50.0),
    )
    graph = _base_graph()
    integrate_recent_actions(continuity, graph, now=100.0, window=60.0)
    # window 60 → cutoff 40 → all three actions integrated.
    for aid in ("a", "b", "c"):
        assert aid in graph.nodes and graph.nodes[aid].type == "action"
        assert any(e.source == aid for e in graph.edges)


def test_integrate_recent_actions_respects_window():
    continuity = _continuity_with(_event(id="old", ts=10.0), _event(id="new", ts=95.0))
    graph = _base_graph()
    integrate_recent_actions(continuity, graph, now=100.0, window=30.0)  # cutoff 70
    assert "new" in graph.nodes
    assert "old" not in graph.nodes


def test_integration_is_idempotent():
    continuity = _continuity_with(_event(id="a", ts=90.0))
    graph = _base_graph()
    integrate_recent_actions(continuity, graph, now=100.0, window=60.0)
    nodes_after_first, edges_after_first = len(graph.nodes), len(graph.edges)
    # Re-integrating the same window must not duplicate nodes or edges.
    integrate_recent_actions(continuity, graph, now=100.0, window=60.0)
    assert len(graph.nodes) == nodes_after_first
    assert len(graph.edges) == edges_after_first


def test_deterministic_across_graphs():
    events = (_event(id="a", ts=90.0), _event(id="b", ts=100.0))
    g1, g2 = _base_graph(), _base_graph()
    integrate_recent_actions(_continuity_with(*events), g1, now=100.0, window=60.0)
    integrate_recent_actions(_continuity_with(*events), g2, now=100.0, window=60.0)
    assert graph_to_dict(g1) == graph_to_dict(g2)


# ---------------------------------------------------------------------------
# First-class in the EXISTING Phase-8 machinery (the whole point of 9.2)
# ---------------------------------------------------------------------------

def test_actions_visible_to_phase8_propagation():
    graph = _base_graph()
    integrate_recent_actions(_continuity_with(_event(id="act_1", mag=0.7)), graph, now=100.0, window=60.0)
    influence = propagate_influence(graph)
    # The action node is a first-class node the 8.2 engine sees; with no inbound
    # edges its influence is its intrinsic magnitude.
    assert "act_1" in influence
    assert influence["act_1"] == pytest.approx(0.7)


def test_no_propagation_side_effects_in_integration():
    # 9.2 only mutates nodes + edges — it computes no influence/centrality and
    # returns None.
    graph = _base_graph()
    assert integrate_recent_actions(_continuity_with(_event()), graph, now=100.0, window=60.0) is None
    assert set(vars(graph).keys()) == {"nodes", "edges"}   # no new graph attributes


def test_graph_json_serializable_after_integration():
    graph = _base_graph()
    integrate_recent_actions(_continuity_with(_event()), graph, now=100.0, window=60.0)
    json.dumps(graph_to_dict(graph))     # must not raise
