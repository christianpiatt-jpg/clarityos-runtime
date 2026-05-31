# tests/test_phase8_structures.py
#
# CARD 8.0 — foundational causal primitives (no inference yet).
from copy import deepcopy
import json

import pytest

from phase8_structures import (
    CausalChain,
    CausalEdge,
    CausalGraph,
    CausalNode,
    build_chain,
    build_graph,
    chain_to_dict,
    graph_to_dict,
    make_edge,
    make_node,
    score_chain,
)


# ---------------------------------------------------------------------------
# Node / edge creation
# ---------------------------------------------------------------------------

def test_make_node():
    n = make_node("n1", "action", "Risky edit", 12.0)
    assert isinstance(n, CausalNode)
    assert (n.id, n.type, n.label, n.timestamp) == ("n1", "action", "Risky edit", 12.0)


def test_make_node_default_timestamp_is_none():
    assert make_node("n2", "state", "Stable").timestamp is None


def test_make_edge():
    e = make_edge("a", "b", 0.5)
    assert isinstance(e, CausalEdge)
    assert (e.source, e.target, e.weight) == ("a", "b", 0.5)


@pytest.mark.parametrize("weight,expected", [
    (2.0, 1.0), (-3.0, -1.0), (1.0, 1.0), (-1.0, -1.0),
    (0.5, 0.5), (-0.5, -0.5), (0.0, 0.0),
])
def test_edge_weight_clamped(weight, expected):
    assert make_edge("a", "b", weight).weight == expected


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def test_build_graph():
    nodes = [make_node("a", "action", "A"), make_node("b", "state", "B")]
    edges = [make_edge("a", "b", 0.4)]
    g = build_graph(nodes, edges)
    assert isinstance(g, CausalGraph)
    assert set(g.nodes.keys()) == {"a", "b"}
    assert g.nodes["a"].label == "A"
    assert g.edges == edges


def test_build_graph_duplicate_id_last_wins():
    g = build_graph([make_node("a", "action", "first"), make_node("a", "state", "second")], [])
    assert len(g.nodes) == 1
    assert g.nodes["a"].label == "second"


# ---------------------------------------------------------------------------
# Chain assembly + scoring
# ---------------------------------------------------------------------------

def test_build_chain_and_score():
    nodes = [make_node("a", "action", "A"), make_node("b", "drift", "B")]
    edges = [make_edge("a", "b", 0.6), make_edge("b", "c", -0.4)]
    c = build_chain(nodes, edges)
    assert isinstance(c, CausalChain)
    assert c.nodes == nodes
    assert c.edges == edges
    # score = mean(|0.6|, |-0.4|) = 0.5
    assert c.score == pytest.approx(0.5)


def test_score_chain_empty_is_zero():
    assert score_chain([]) == 0.0
    assert build_chain([], []).score == 0.0


@pytest.mark.parametrize("weights", [[0.0], [1.0, -1.0], [0.3, 0.6, 0.9], [-0.2, 0.8]])
def test_score_in_range(weights):
    s = score_chain([make_edge("a", "b", w) for w in weights])
    assert 0.0 <= s <= 1.0


# ---------------------------------------------------------------------------
# Serialization (JSON-safe)
# ---------------------------------------------------------------------------

def test_chain_to_dict_json_serializable():
    c = build_chain(
        [make_node("a", "action", "A", 1.0), make_node("b", "drift", "B", 2.0)],
        [make_edge("a", "b", 0.5)],
    )
    d = chain_to_dict(c)
    json.dumps(d)  # must not raise
    assert d["score"] == pytest.approx(0.5)
    assert d["nodes"][0] == {"id": "a", "type": "action", "label": "A", "timestamp": 1.0, "value": None}
    assert d["edges"][0] == {"source": "a", "target": "b", "weight": 0.5}


def test_graph_to_dict_json_serializable():
    g = build_graph(
        [make_node("a", "action", "A"), make_node("b", "state", "B", 3.0)],
        [make_edge("a", "b", 0.7)],
    )
    d = graph_to_dict(g)
    json.dumps(d)  # must not raise
    assert d["nodes"]["a"] == {"id": "a", "type": "action", "label": "A", "timestamp": None, "value": None}
    assert d["nodes"]["b"]["timestamp"] == 3.0
    assert d["edges"][0]["weight"] == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Phase 8.2a — structured node value
# ---------------------------------------------------------------------------

def test_make_node_default_value_is_none():
    assert make_node("n", "state", "S").value is None


def test_node_value_round_trips_through_graph_and_chain():
    n = make_node("n", "drift", "Drift velocity: 0.50", 1.0, value=0.5)
    assert n.value == 0.5
    gd = graph_to_dict(build_graph([n], []))
    assert gd["nodes"]["n"]["value"] == 0.5
    json.dumps(gd)  # serializable
    cd = chain_to_dict(build_chain([n], []))
    assert cd["nodes"][0]["value"] == 0.5
    json.dumps(cd)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_deterministic():
    nodes = [make_node("a", "action", "A", 1.0), make_node("b", "drift", "B", 2.0)]
    edges = [make_edge("a", "b", 0.6)]
    assert build_chain(nodes, edges) == build_chain(deepcopy(nodes), deepcopy(edges))
    assert build_graph(nodes, edges) == build_graph(deepcopy(nodes), deepcopy(edges))
    assert graph_to_dict(build_graph(nodes, edges)) == graph_to_dict(
        build_graph(deepcopy(nodes), deepcopy(edges))
    )
