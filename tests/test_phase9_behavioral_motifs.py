# tests/test_phase9_behavioral_motifs.py
#
# CARD 9.4 — behavioral motif detection: action loops, trigger chains, habits,
# action bottlenecks, action attractors (the action-layer analogue of 8.3),
# plus endpoint integration.
#
# Runs under TESTING=1 (tests/conftest.py) → phase7_storage in-memory backend.
import json

import pytest

from phase6_contracts import (
    SuperCoherenceState,
    SuperEssenceState,
    SuperIdentityState,
    SuperIntegrationState,
    SuperPatternState,
    SuperstructureState,
)
import phase7_storage
from phase7_storage import TelemetryRecord
from phase8_structures import build_graph, make_edge, make_node
from phase9_actions import ActionEvent
from phase9_behavioral_motifs import (
    analyze_behavioral_motifs,
    detect_action_attractors,
    detect_action_bottlenecks,
    detect_action_loops,
    detect_habits,
    detect_trigger_chains,
)
from phase7_endpoint import OPERATOR_ID
import phase9_ingest


def _ev(id, label, ts, mag=None):
    return ActionEvent(id=id, label=label, timestamp=ts, magnitude=mag)


# ---------------------------------------------------------------------------
# Action loops
# ---------------------------------------------------------------------------

def test_loop_a_b_a():
    loops = detect_action_loops([_ev("1", "prune", 1.0), _ev("2", "edit", 2.0), _ev("3", "prune", 3.0)])
    assert loops == [["edit", "prune"]]            # canonical (smallest rotation)


def test_loop_a_b_c_a():
    loops = detect_action_loops([
        _ev("1", "prune", 1.0), _ev("2", "edit", 2.0),
        _ev("3", "save", 3.0), _ev("4", "prune", 4.0),
    ])
    assert loops == [["edit", "save", "prune"]]


def test_no_loop_when_labels_distinct():
    assert detect_action_loops([_ev("1", "a", 1.0), _ev("2", "b", 2.0), _ev("3", "c", 3.0)]) == []


def test_loops_deduplicated_and_sorted():
    # Two prune→edit→prune occurrences collapse to one canonical loop.
    actions = [
        _ev("1", "prune", 1.0), _ev("2", "edit", 2.0), _ev("3", "prune", 3.0),
        _ev("4", "edit", 4.0), _ev("5", "prune", 5.0),
    ]
    assert detect_action_loops(actions) == [["edit", "prune"]]


def test_loops_empty_for_no_actions():
    assert detect_action_loops([]) == []


# ---------------------------------------------------------------------------
# Trigger chains (action -> factor -> action)
# ---------------------------------------------------------------------------

def test_trigger_chain_detected():
    graph = build_graph(
        [make_node("act_a", "action", "A"), make_node("factor_0", "action", "F"),
         make_node("act_b", "action", "B")],
        [make_edge("act_a", "factor_0", 0.5), make_edge("factor_0", "act_b", 0.5)],
    )
    assert detect_trigger_chains(graph) == [["act_a", "factor_0", "act_b"]]


def test_trigger_chain_ignores_non_positive_edges():
    graph = build_graph(
        [make_node("act_a", "action", "A"), make_node("factor_0", "action", "F"),
         make_node("act_b", "action", "B")],
        [make_edge("act_a", "factor_0", -0.5), make_edge("factor_0", "act_b", 0.5)],
    )
    assert detect_trigger_chains(graph) == []


def test_trigger_chain_requires_factor_in_middle():
    # action -> action -> action (no factor) is NOT a trigger chain.
    graph = build_graph(
        [make_node("act_a", "action", "A"), make_node("act_m", "action", "M"),
         make_node("act_b", "action", "B")],
        [make_edge("act_a", "act_m", 0.5), make_edge("act_m", "act_b", 0.5)],
    )
    assert detect_trigger_chains(graph) == []


# ---------------------------------------------------------------------------
# Habits
# ---------------------------------------------------------------------------

def test_habit_regular_spacing():
    actions = [_ev(f"p{i}", "prune", float(10 * (i + 1))) for i in range(3)]  # ts 10,20,30
    assert detect_habits(actions) == ["prune"]


def test_no_habit_below_three_occurrences():
    assert detect_habits([_ev("1", "prune", 10.0), _ev("2", "prune", 20.0)]) == []


def test_no_habit_high_spacing_variance():
    # spacings 100 then 5 → stddev ≫ 20% of mean → not a habit.
    actions = [_ev("1", "x", 0.0), _ev("2", "x", 100.0), _ev("3", "x", 105.0)]
    assert detect_habits(actions) == []


def test_habits_top_5_by_frequency():
    actions = []
    for label, count in (("a", 6), ("b", 5), ("c", 4), ("d", 3), ("e", 3), ("f", 3)):
        for i in range(count):
            actions.append(_ev(f"{label}{i}", label, float(10 * i)))  # regular spacing
    habits = detect_habits(actions)
    assert len(habits) == 5
    assert habits[0] == "a"          # highest frequency first
    assert "f" not in habits         # 6th (tie with d/e at 3) dropped


# ---------------------------------------------------------------------------
# Bottlenecks + attractors (action-filtered)
# ---------------------------------------------------------------------------

def test_action_bottleneck_detected():
    graph = build_graph(
        [make_node("act_1", "action", "A"), make_node("v1", "drift", "x"),
         make_node("v2", "drift", "x"), make_node("v3", "drift", "x")],
        [make_edge("act_1", "v1", 0.5), make_edge("act_1", "v2", 0.5), make_edge("act_1", "v3", 0.5)],
    )
    centrality = {"act_1": 0.8, "v1": 0.2, "v2": 0.2, "v3": 0.2}
    assert detect_action_bottlenecks(graph, {}, centrality) == ["act_1"]


def test_bottleneck_ignores_non_action_nodes():
    # A high-centrality, high-degree NON-action node is not a behavioral bottleneck.
    graph = build_graph(
        [make_node("hub", "drift", "x"), make_node("a", "drift", "x"),
         make_node("b", "drift", "x"), make_node("c", "drift", "x")],
        [make_edge("a", "hub", 0.5), make_edge("hub", "b", 0.5), make_edge("hub", "c", 0.5)],
    )
    assert detect_action_bottlenecks(graph, {}, {"hub": 0.9}) == []


def test_action_attractor_detected():
    graph = build_graph(
        [make_node("act_sink", "action", "S"), make_node("a", "drift", "x"),
         make_node("b", "drift", "x")],
        [make_edge("a", "act_sink", 0.5), make_edge("b", "act_sink", 0.5)],
    )
    assert detect_action_attractors(graph, {"act_sink": 0.9, "a": 0.2, "b": 0.2}) == ["act_sink"]


def test_attractor_requires_inbound_gt_outbound():
    # An action with only outbound edges (the 9.2 default) is never an attractor.
    graph = build_graph(
        [make_node("act_src", "action", "S"), make_node("v", "drift", "x")],
        [make_edge("act_src", "v", 0.5)],
    )
    assert detect_action_attractors(graph, {"act_src": 0.9}) == []


# ---------------------------------------------------------------------------
# analyze_behavioral_motifs + determinism + fallback
# ---------------------------------------------------------------------------

def test_analyze_shape_and_json():
    result = analyze_behavioral_motifs([], build_graph([], []), {}, {})
    assert set(result.keys()) == {
        "action_loops", "trigger_chains", "habits",
        "action_bottlenecks", "action_attractors",
    }
    json.dumps(result)


def test_fallback_no_actions_all_empty():
    result = analyze_behavioral_motifs([], build_graph([], []), {}, {})
    assert all(v == [] for v in result.values())


def test_deterministic():
    actions = [_ev("1", "prune", 1.0), _ev("2", "edit", 2.0), _ev("3", "prune", 3.0)]
    graph = build_graph([make_node("act_1", "action", "A")], [])
    assert analyze_behavioral_motifs(actions, graph, {}, {}) == analyze_behavioral_motifs(actions, graph, {}, {})


# ---------------------------------------------------------------------------
# Endpoint integration
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    import app
    from conftest import TestClient
    return TestClient(app.app)


@pytest.fixture(autouse=True)
def _reset_state():
    phase7_storage.reset()
    phase9_ingest._reset_for_tests()
    yield
    phase7_storage.reset()
    phase9_ingest._reset_for_tests()


def _state() -> SuperstructureState:
    return SuperstructureState(
        pattern=SuperPatternState("p", 0.0, 0.0, 0.0, "p"),
        integration=SuperIntegrationState(0.0, 0.0, "i"),
        coherence=SuperCoherenceState(0.0, 0.0, 0.0, "c"),
        essence=SuperEssenceState(0.0, "e", 0.0),
        identity=SuperIdentityState("o", 0.0, 0.0, 0.0),
    )


def _seed(drift, coherence, ts):
    phase7_storage.append_record(
        OPERATOR_ID,
        TelemetryRecord(timestamp=ts, superstructure=_state(),
                        drift=drift, coherence_health=coherence, trust_band="HIGH"),
    )


def test_endpoint_empty_behavioral_motifs(client):
    body = client.get("/operator/telemetry").json()
    assert "behavioral_motifs" in body
    bm = body["behavioral_motifs"]
    assert set(bm.keys()) == {
        "action_loops", "trigger_chains", "habits",
        "action_bottlenecks", "action_attractors",
    }
    assert all(v == [] for v in bm.values())       # no actions posted


def test_endpoint_detects_loop_from_posted_actions(client):
    _seed(0.2, 0.6, 0.0)
    for i, label in enumerate(["prune", "edit", "prune"]):
        client.post("/operator/action", json={"id": f"a{i}", "label": label, "timestamp": float(i + 1), "magnitude": 0.5})
    bm = client.get("/operator/telemetry").json()["behavioral_motifs"]
    assert bm["action_loops"] == [["edit", "prune"]]
    json.dumps(bm)


def test_endpoint_detects_habit_from_posted_actions(client):
    for i in range(3):
        client.post("/operator/action", json={"id": f"h{i}", "label": "prune", "timestamp": float(10 * (i + 1)), "magnitude": 0.5})
    bm = client.get("/operator/telemetry").json()["behavioral_motifs"]
    assert "prune" in bm["habits"]
