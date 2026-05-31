# tests/test_phase9_propagation.py
#
# CARD 9.3 — influence propagation: deterministic, single-hop influence from
# action nodes (9.2) to the variables they point at, recorded as InfluenceRecord
# snapshots in continuity. No inference, no graph mutation (those guarantees are
# the point of 9.3); motifs/UI are 9.4/9.5.
import json
from copy import deepcopy
from dataclasses import asdict

import pytest

from phase8_structures import build_graph, graph_to_dict, make_edge, make_node
from phase8_inference import build_phase7_graph
from phase9_ingest import ingest_action, store_action
from phase9_integration import integrate_recent_actions
from phase9_influence import (
    InfluenceRecord,
    compute_influence_weight,
    propagate_action_influence,
    propagate_recent_actions,
)


def _analytics(v=0.5, a=0.0, c=-0.3, sf=0.4, trajectory="Stable"):
    return {
        "drift_velocity": v, "drift_acceleration": a, "coherence_trend": c,
        "stability_forecast": sf, "trajectory": trajectory,
    }


def _action_node(id="act_1", mag=0.7, ts=100.0):
    return make_node(id, "action", "Adjusted X", timestamp=ts, value=mag)


def _graph_with_action(id="act_1", mag=0.7, ts=100.0):
    """A real Phase-8 graph with one 9.2-integrated action (→ 5 variable edges)."""
    graph = build_phase7_graph(
        [], _analytics(), [], [{"action": "none", "correlation": 0.0, "contribution": 0.0}],
    )
    continuity = {}
    store_action(ingest_action({"id": id, "label": "Adjusted X", "timestamp": ts, "magnitude": mag}), continuity)
    integrate_recent_actions(continuity, graph, now=ts, window=10.0)
    return graph, continuity


# ---------------------------------------------------------------------------
# compute_influence_weight
# ---------------------------------------------------------------------------

def test_weight_is_magnitude():
    assert compute_influence_weight(_action_node(mag=0.7)) == pytest.approx(0.7)
    assert compute_influence_weight(_action_node(mag=-0.4)) == pytest.approx(-0.4)


def test_weight_none_magnitude_is_zero():
    assert compute_influence_weight(_action_node(mag=None)) == 0.0


def test_weight_clamped():
    assert compute_influence_weight(_action_node(mag=2.0)) == 1.0
    assert compute_influence_weight(_action_node(mag=-2.0)) == -1.0


def test_weight_ignores_variable():
    # No cross-variable effects — weight is identical regardless of the variable.
    node = _action_node(mag=0.6)
    assert compute_influence_weight(node, "drift_velocity") == compute_influence_weight(node, "coherence_trend")


# ---------------------------------------------------------------------------
# InfluenceRecord
# ---------------------------------------------------------------------------

def test_influence_record_frozen_and_fields():
    rec = InfluenceRecord(action_id="a", variable_id="v", weight=0.5, timestamp=1.0)
    assert (rec.action_id, rec.variable_id, rec.weight, rec.timestamp) == ("a", "v", 0.5, 1.0)
    with pytest.raises(Exception):
        rec.weight = 0.9        # frozen


# ---------------------------------------------------------------------------
# propagate_action_influence
# ---------------------------------------------------------------------------

def test_propagate_creates_record_per_outgoing_edge():
    graph, continuity = _graph_with_action(mag=0.7)
    created = propagate_action_influence(graph.nodes["act_1"], graph, continuity)
    # 9.2 linked the action to the 5 system variables → 5 influence records.
    assert len(created) == 5
    assert continuity["influence"] == created
    for rec in created:
        assert rec.action_id == "act_1"
        assert rec.weight == pytest.approx(0.7)
        assert rec.timestamp == 100.0


def test_propagate_sorted_by_timestamp_action_variable():
    graph, continuity = _graph_with_action()
    propagate_action_influence(graph.nodes["act_1"], graph, continuity)
    keys = [(r.timestamp, r.action_id, r.variable_id) for r in continuity["influence"]]
    assert keys == sorted(keys)


def test_propagate_does_not_mutate_graph():
    graph, continuity = _graph_with_action()
    before = graph_to_dict(graph)
    propagate_action_influence(graph.nodes["act_1"], graph, continuity)
    assert graph_to_dict(graph) == before          # nodes + edges untouched


def test_propagate_single_hop_only():
    # Records only ever go action → variable; never variable→variable or
    # action→action (the action's only out-edges are to variables).
    graph, continuity = _graph_with_action()
    propagate_action_influence(graph.nodes["act_1"], graph, continuity)
    for rec in continuity["influence"]:
        assert rec.action_id == "act_1"
        assert graph.nodes[rec.variable_id].type != "action"


def test_propagate_idempotent():
    graph, continuity = _graph_with_action()
    propagate_action_influence(graph.nodes["act_1"], graph, continuity)
    n = len(continuity["influence"])
    propagate_action_influence(graph.nodes["act_1"], graph, continuity)   # again
    assert len(continuity["influence"]) == n        # no duplicate snapshots


def test_propagate_none_magnitude_zero_weight_records():
    graph, continuity = _graph_with_action(mag=None)
    created = propagate_action_influence(graph.nodes["act_1"], graph, continuity)
    assert len(created) == 5
    assert all(rec.weight == 0.0 for rec in created)


# ---------------------------------------------------------------------------
# propagate_recent_actions — window logic + multi-action
# ---------------------------------------------------------------------------

def _graph_with_actions(*specs):
    """specs: (id, mag, ts). Returns a graph with all actions 9.2-integrated."""
    graph = build_phase7_graph(
        [], _analytics(), [], [{"action": "none", "correlation": 0.0, "contribution": 0.0}],
    )
    continuity = {}
    for aid, mag, ts in specs:
        store_action(ingest_action({"id": aid, "label": aid, "timestamp": ts, "magnitude": mag}), continuity)
    integrate_recent_actions(continuity, graph, now=max(s[2] for s in specs), window=1e9)
    return graph, continuity


def test_propagate_recent_respects_window():
    graph, continuity = _graph_with_actions(("old", 0.5, 10.0), ("new", 0.5, 95.0))
    created = propagate_recent_actions(continuity, graph, now=100.0, window=30.0)  # cutoff 70
    action_ids = {r.action_id for r in created}
    assert action_ids == {"new"}                    # "old" is outside the window


def test_propagate_recent_multi_action_sorted():
    graph, continuity = _graph_with_actions(("b", 0.5, 100.0), ("a", 0.5, 90.0))
    propagate_recent_actions(continuity, graph, now=100.0, window=60.0)
    keys = [(r.timestamp, r.action_id, r.variable_id) for r in continuity["influence"]]
    assert keys == sorted(keys)
    assert {r.action_id for r in continuity["influence"]} == {"a", "b"}


def test_propagate_recent_idempotent():
    graph, continuity = _graph_with_actions(("a", 0.5, 90.0))
    propagate_recent_actions(continuity, graph, now=100.0, window=60.0)
    n = len(continuity["influence"])
    propagate_recent_actions(continuity, graph, now=100.0, window=60.0)
    assert len(continuity["influence"]) == n


# ---------------------------------------------------------------------------
# Determinism + serialization
# ---------------------------------------------------------------------------

def test_deterministic():
    g1, c1 = _graph_with_actions(("a", 0.5, 90.0), ("b", 0.3, 100.0))
    g2, c2 = _graph_with_actions(("a", 0.5, 90.0), ("b", 0.3, 100.0))
    propagate_recent_actions(c1, g1, now=100.0, window=60.0)
    propagate_recent_actions(c2, g2, now=100.0, window=60.0)
    assert c1["influence"] == c2["influence"]


def test_influence_records_json_serializable():
    graph, continuity = _graph_with_action()
    propagate_action_influence(graph.nodes["act_1"], graph, continuity)
    json.dumps([asdict(rec) for rec in continuity["influence"]])
