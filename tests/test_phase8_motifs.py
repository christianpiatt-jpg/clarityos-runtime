# tests/test_phase8_motifs.py
#
# CARD 8.3 — structural motif detection (feedback loops, bottlenecks,
# attractors), plus endpoint integration.
#
# Runs under TESTING=1 (tests/conftest.py) → phase7_storage in-memory backend.
import json
from copy import deepcopy

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
from phase8_inference import build_phase7_graph
from phase8_propagation import compute_node_centrality, propagate_influence
from phase8_motifs import (
    analyze_motifs,
    detect_attractors,
    detect_bottlenecks,
    detect_feedback_loops,
)
from phase7_endpoint import OPERATOR_ID

NONE_FACTOR = {"action": "none", "correlation": 0.0, "contribution": 0.0}


def _analytics(trajectory="Stable", v=0.0, a=0.0, c=0.0, sf=0.0):
    return {
        "drift_velocity": v, "drift_acceleration": a, "coherence_trend": c,
        "stability_forecast": sf, "trajectory": trajectory,
    }


def _nodes(*ids):
    return [make_node(i, "x", i) for i in ids]


# ---------------------------------------------------------------------------
# Feedback loops
# ---------------------------------------------------------------------------

def test_detect_2_cycle():
    g = build_graph(_nodes("a", "b"), [make_edge("a", "b", 0.5), make_edge("b", "a", 0.5)])
    assert detect_feedback_loops(g) == [["a", "b"]]


def test_detect_3_cycle():
    g = build_graph(_nodes("a", "b", "c"),
                    [make_edge("a", "b", 0.5), make_edge("b", "c", 0.5), make_edge("c", "a", 0.5)])
    assert detect_feedback_loops(g) == [["a", "b", "c"]]


def test_dag_has_no_loops():
    g = build_graph(_nodes("a", "b", "c"), [make_edge("a", "b", 0.5), make_edge("b", "c", 0.5)])
    assert detect_feedback_loops(g) == []


def test_rotated_loops_deduplicated():
    # The single 3-cycle is reported once (min-rooted), not as rotations.
    g = build_graph(_nodes("a", "b", "c"),
                    [make_edge("a", "b", 0.5), make_edge("b", "c", 0.5), make_edge("c", "a", 0.5)])
    loops = detect_feedback_loops(g)
    assert loops == [["a", "b", "c"]]


def test_loop_length_6_detected():
    ids = [f"k{i}" for i in range(6)]
    edges = [make_edge(ids[i], ids[(i + 1) % 6], 0.5) for i in range(6)]
    g = build_graph(_nodes(*ids), edges)
    assert detect_feedback_loops(g) == [ids]


def test_loop_length_7_not_detected():
    ids = [f"k{i}" for i in range(7)]
    edges = [make_edge(ids[i], ids[(i + 1) % 7], 0.5) for i in range(7)]
    g = build_graph(_nodes(*ids), edges)
    assert detect_feedback_loops(g) == []  # exceeds MAX_LOOP_LEN (6)


def test_max_loops_capped_at_10():
    nodes, edges = [], []
    for i in range(12):  # 12 disjoint 2-cycles
        x, y = f"n{i:02d}a", f"n{i:02d}b"
        nodes += _nodes(x, y)
        edges += [make_edge(x, y, 0.5), make_edge(y, x, 0.5)]
    loops = detect_feedback_loops(build_graph(nodes, edges))
    assert len(loops) == 10
    assert loops == sorted(loops)  # lexicographic


# ---------------------------------------------------------------------------
# Bottlenecks
# ---------------------------------------------------------------------------

def test_bottleneck_detection():
    g = build_graph(_nodes("hub", "a", "b", "c"),
                    [make_edge("a", "hub", 0.5), make_edge("hub", "b", 0.5), make_edge("hub", "c", 0.5)])
    centrality = {"hub": 0.8, "a": 0.2, "b": 0.2, "c": 0.2}
    influence = {nid: 0.5 for nid in g.nodes}
    assert detect_bottlenecks(g, influence, centrality) == ["hub"]


def test_bottleneck_requires_degree_3():
    g = build_graph(_nodes("hub", "a", "b"),
                    [make_edge("a", "hub", 0.5), make_edge("hub", "b", 0.5)])  # degree 2
    centrality = {"hub": 0.9, "a": 0.1, "b": 0.1}
    assert detect_bottlenecks(g, {}, centrality) == []


def test_bottleneck_centrality_threshold_strict():
    g = build_graph(_nodes("hub", "a", "b", "c"),
                    [make_edge("a", "hub", 0.5), make_edge("hub", "b", 0.5), make_edge("hub", "c", 0.5)])
    centrality = {"hub": 0.6}  # not > 0.6
    assert detect_bottlenecks(g, {}, centrality) == []


# ---------------------------------------------------------------------------
# Attractors
# ---------------------------------------------------------------------------

def test_attractor_detection():
    g = build_graph(_nodes("sink", "a", "b"),
                    [make_edge("a", "sink", 0.5), make_edge("b", "sink", 0.5)])
    influence = {"sink": 0.9, "a": 0.3, "b": 0.3}
    assert detect_attractors(g, influence) == ["sink"]


def test_attractor_requires_inbound_gt_outbound():
    g = build_graph(_nodes("src", "a"), [make_edge("src", "a", 0.5)])  # src outbound > inbound
    influence = {"src": 0.9, "a": 0.2}
    assert detect_attractors(g, influence) == []


def test_attractors_top_5_by_influence():
    nodes = _nodes("feed")
    edges = []
    influence = {"feed": 0.1}
    for i in range(7):
        s = f"s{i}"
        nodes += _nodes(s)
        edges.append(make_edge("feed", s, 0.5))   # each sink: inbound 1 > outbound 0
        influence[s] = 0.71 + i * 0.01            # all > 0.7, increasing
    result = detect_attractors(build_graph(nodes, edges), influence)
    assert result == ["s6", "s5", "s4", "s3", "s2"]  # top 5 by influence desc


# ---------------------------------------------------------------------------
# analyze_motifs + determinism + serialization
# ---------------------------------------------------------------------------

def test_analyze_motifs_shape_on_phase7_graph():
    g = build_phase7_graph([], _analytics("Diverging", 0.5), ["High drift detected"],
                           [{"action": "prune", "correlation": 0.5, "contribution": 0.6}])
    inf = propagate_influence(g)
    cen = compute_node_centrality(g, inf)
    motifs = analyze_motifs(g, inf, cen)
    assert set(motifs.keys()) == {"feedback_loops", "bottlenecks", "attractors"}
    assert motifs["feedback_loops"] == []   # the 8.1 graph is a DAG
    json.dumps(motifs)


def test_analyze_motifs_deterministic():
    nodes = _nodes("a", "b", "c")
    edges = [make_edge("a", "b", 0.5), make_edge("b", "c", 0.5),
             make_edge("c", "a", 0.5), make_edge("b", "a", 0.5)]
    g = build_graph(nodes, edges)
    inf = {nid: 0.8 for nid in g.nodes}
    cen = {nid: 0.7 for nid in g.nodes}
    assert analyze_motifs(g, inf, cen) == analyze_motifs(
        build_graph(deepcopy(nodes), deepcopy(edges)), dict(inf), dict(cen)
    )


# ---------------------------------------------------------------------------
# Endpoint integration
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    import app
    from conftest import TestClient
    return TestClient(app.app)


@pytest.fixture(autouse=True)
def _reset_phase7():
    phase7_storage.reset()
    yield
    phase7_storage.reset()


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


def test_endpoint_returns_causal_motifs(client):
    _seed(0.2, 0.6, 0.0)
    _seed(0.8, 0.2, 1.0)
    body = client.get("/operator/telemetry").json()

    assert "causal_motifs" in body
    assert set(body["causal_motifs"].keys()) == {"feedback_loops", "bottlenecks", "attractors"}

    # Consistent with recomputing from the returned signals.
    g = build_phase7_graph([], body["analytics"], body["alerts"], body["causal_factors"])
    inf = propagate_influence(g)
    cen = compute_node_centrality(g, inf)
    assert body["causal_motifs"] == analyze_motifs(g, inf, cen)
    # The first-order graph is a DAG → no loops.
    assert body["causal_motifs"]["feedback_loops"] == []
