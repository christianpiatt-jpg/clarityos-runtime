# tests/test_phase8_multichain.py
#
# CARD 8.4 — multi-chain causal explanations (ranked, motif-annotated path
# sets), plus endpoint integration.
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
from phase8_motifs import analyze_motifs
from phase8_multichain import (
    MAX_PATHS_PER_START,
    MAX_PATH_DEPTH,
    generate_causal_chains,
    scored_chains_to_dicts,
)
from phase7_endpoint import OPERATOR_ID

NONE_FACTOR = {"action": "none", "correlation": 0.0, "contribution": 0.0}


def _analytics(trajectory="Stable", v=0.0, a=0.0, c=0.0, sf=0.0):
    return {
        "drift_velocity": v, "drift_acceleration": a, "coherence_trend": c,
        "stability_forecast": sf, "trajectory": trajectory,
    }


def _seqs(chains):
    """The node-id sequence of each scored chain, in result order."""
    return [tuple(n.id for n in entry["chain"].nodes) for entry in chains]


def _by_seq(chains):
    """Map node-id sequence -> scored-chain entry."""
    return {tuple(n.id for n in entry["chain"].nodes): entry for entry in chains}


def _phase7_stack(analytics, alerts, factors):
    """Build the 8.1 graph + 8.2 influence/centrality + 8.3 motifs from Phase 7
    signals — the inputs 8.4 consumes."""
    g = build_phase7_graph([], analytics, alerts, factors)
    inf = propagate_influence(g)
    cen = compute_node_centrality(g, inf)
    motifs = analyze_motifs(g, inf, cen)
    return g, inf, cen, motifs


# ---------------------------------------------------------------------------
# Multiple chains from a non-trivial graph
# ---------------------------------------------------------------------------

def test_multiple_chains_from_nontrivial_graph():
    g, inf, cen, motifs = _phase7_stack(
        _analytics("Diverging", 0.5), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.6}],
    )
    chains = generate_causal_chains(g, inf, cen, motifs)

    # drift_velocity→narrative, drift_velocity→factor_0→narrative, factor_0→narrative.
    assert len(chains) >= 2
    # Every chain is a structurally valid path ending at the narrative.
    assert all(seq[-1] == "narrative" for seq in _seqs(chains))
    # At least one multi-hop chain (drift_velocity → factor_0 → narrative).
    assert any(len(entry["chain"].nodes) == 3 for entry in chains)
    # No duplicate node sequences (deduplication invariant).
    assert len(_seqs(chains)) == len(set(_seqs(chains)))


# ---------------------------------------------------------------------------
# Ranking: sorted by score desc + deterministic / stable
# ---------------------------------------------------------------------------

def test_sorted_by_score_descending():
    g, inf, cen, motifs = _phase7_stack(
        _analytics("Diverging", 0.5), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.6}],
    )
    scores = [entry["score"] for entry in generate_causal_chains(g, inf, cen, motifs)]
    assert scores == sorted(scores, reverse=True)
    assert all(0.0 <= s <= 1.0 for s in scores)


def test_deterministic_across_independent_builds():
    args = (_analytics("Diverging", 0.5), ["High drift detected"],
            [{"action": "prune", "correlation": 0.5, "contribution": 0.6}])
    g1, i1, c1, m1 = _phase7_stack(*deepcopy(args))
    g2, i2, c2, m2 = _phase7_stack(*deepcopy(args))
    assert scored_chains_to_dicts(generate_causal_chains(g1, i1, c1, m1)) == \
        scored_chains_to_dicts(generate_causal_chains(g2, i2, c2, m2))


def test_ties_break_by_node_sequence_stable():
    # Symmetric diamond: S→a→narrative and S→b→narrative are score-identical;
    # with a→/b→narrative singletons all four chains tie, so ordering falls back
    # to node-id-sequence ascending.
    nodes = [make_node("S", "x", "S"), make_node("a", "x", "a"),
             make_node("b", "x", "b"), make_node("narrative", "narrative", "N")]
    edges = [make_edge("S", "a", 0.5), make_edge("a", "narrative", 0.5),
             make_edge("S", "b", 0.5), make_edge("b", "narrative", 0.5)]
    g = build_graph(nodes, edges)
    flat = {"S": 0.5, "a": 0.5, "b": 0.5, "narrative": 0.5}
    chains = generate_causal_chains(g, flat, dict(flat), None)

    assert all(entry["score"] == pytest.approx(0.625) for entry in chains)
    assert _seqs(chains) == [
        ("S", "a", "narrative"), ("S", "b", "narrative"),
        ("a", "narrative"), ("b", "narrative"),
    ]


# ---------------------------------------------------------------------------
# Depth limit + per-start K cap
# ---------------------------------------------------------------------------

def test_depth_limit_respected():
    # Linear c0→c1→…→c6→narrative — 7 edges from c0 (over the limit), 6 from c1.
    ids = [f"c{i}" for i in range(7)]
    nodes = [make_node(i, "x", i) for i in ids] + [make_node("narrative", "narrative", "N")]
    chain_ids = ids + ["narrative"]
    edges = [make_edge(chain_ids[i], chain_ids[i + 1], 0.5) for i in range(len(chain_ids) - 1)]
    g = build_graph(nodes, edges)
    # Make c0..c4 the five starts (descending influence).
    inf = {f"c{i}": 1.0 - i * 0.1 for i in range(7)}
    inf["narrative"] = 0.2

    chains = generate_causal_chains(g, inf, dict(inf), None)
    # c0 needs 7 edges to reach narrative → no chain starts at c0.
    assert not any(entry["chain"].nodes[0].id == "c0" for entry in chains)
    # c1's full path uses exactly MAX_PATH_DEPTH edges (→ MAX_PATH_DEPTH + 1 nodes).
    assert any(len(entry["chain"].nodes) == MAX_PATH_DEPTH + 1 for entry in chains)
    assert all(len(entry["chain"].nodes) <= MAX_PATH_DEPTH + 1 for entry in chains)


def test_at_most_k_paths_per_start():
    # S has five distinct simple paths to the narrative; only K are kept.
    nodes = [make_node("S", "x", "S"), make_node("narrative", "narrative", "N")]
    edges = [make_edge("S", "narrative", 0.5)]
    for i in range(4):
        mid = f"m{i}"
        nodes.append(make_node(mid, "x", mid))
        edges += [make_edge("S", mid, 0.5), make_edge(mid, "narrative", 0.5)]
    g = build_graph(nodes, edges)
    inf = {"S": 1.0, "m0": 0.5, "m1": 0.5, "m2": 0.5, "m3": 0.5, "narrative": 0.1}

    chains = generate_causal_chains(g, inf, dict(inf), None)
    from_s = [entry for entry in chains if entry["chain"].nodes[0].id == "S"]
    assert len(from_s) == MAX_PATHS_PER_START  # capped at K, not 5


# ---------------------------------------------------------------------------
# Deduplication of identical paths (parallel edges collapse, strongest kept)
# ---------------------------------------------------------------------------

def test_parallel_edges_collapse_to_single_chain():
    g = build_graph(
        [make_node("A", "x", "A"), make_node("B", "x", "B"),
         make_node("narrative", "narrative", "N")],
        [make_edge("A", "B", 0.4), make_edge("A", "B", 0.6),  # parallel A→B
         make_edge("B", "narrative", 0.5)],
    )
    inf = {"A": 0.8, "B": 0.6, "narrative": 0.4}
    chains = generate_causal_chains(g, inf, dict(inf), None)

    a_chains = [e for e in chains if _seqs([e])[0] == ("A", "B", "narrative")]
    assert len(a_chains) == 1                       # not double-counted
    a_to_b = a_chains[0]["chain"].edges[0]
    assert a_to_b.source == "A" and a_to_b.target == "B"
    assert a_to_b.weight == pytest.approx(0.6)      # strongest parallel edge


# ---------------------------------------------------------------------------
# Motif annotation
# ---------------------------------------------------------------------------

def _diamond():
    """start→mid→narrative and start→narrative (direct), with controlled
    influence so both paths surface."""
    nodes = [make_node("start", "x", "start"), make_node("mid", "x", "mid"),
             make_node("narrative", "narrative", "N")]
    edges = [make_edge("start", "mid", 0.5), make_edge("mid", "narrative", 0.5),
             make_edge("start", "narrative", 0.3)]
    g = build_graph(nodes, edges)
    inf = {"start": 1.0, "mid": 0.5, "narrative": 0.4}
    return g, inf


def test_motif_flags_bottleneck_and_attractor():
    g, inf = _diamond()
    motifs = {"bottlenecks": ["mid"], "attractors": ["narrative"], "feedback_loops": []}
    by_seq = _by_seq(generate_causal_chains(g, inf, dict(inf), motifs))

    # The multi-hop chain crosses the "mid" bottleneck and the "narrative" attractor.
    multi = by_seq[("start", "mid", "narrative")]["motifs"]
    assert multi["passes_bottleneck"] is True
    assert multi["passes_attractor"] is True
    assert multi["in_feedback_loop"] is False

    # The direct chain skips "mid" → no bottleneck, but still hits the attractor.
    direct = by_seq[("start", "narrative")]["motifs"]
    assert direct["passes_bottleneck"] is False
    assert direct["passes_attractor"] is True


def test_motif_flag_feedback_loop():
    g, inf = _diamond()
    motifs = {"bottlenecks": [], "attractors": [], "feedback_loops": [["mid", "other"]]}
    by_seq = _by_seq(generate_causal_chains(g, inf, dict(inf), motifs))

    assert by_seq[("start", "mid", "narrative")]["motifs"]["in_feedback_loop"] is True
    assert by_seq[("start", "narrative")]["motifs"]["in_feedback_loop"] is False


def test_no_motifs_all_flags_false():
    g, inf, cen, _ = _phase7_stack(
        _analytics("Diverging", 0.5), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.6}],
    )
    chains = generate_causal_chains(g, inf, cen, None)  # motifs omitted
    assert len(chains) >= 1
    for entry in chains:
        assert entry["motifs"] == {
            "passes_bottleneck": False,
            "passes_attractor": False,
            "in_feedback_loop": False,
        }


# ---------------------------------------------------------------------------
# Fallback behavior
# ---------------------------------------------------------------------------

def test_empty_influence_yields_trivial_analytics_narrative_chain():
    # Baseline graph (no alerts/factors): the only edge into the narrative is the
    # always-present drift_velocity→narrative. Empty influence → that one chain.
    g = build_phase7_graph([], _analytics(), [], [NONE_FACTOR])
    chains = generate_causal_chains(g, {}, {}, None)
    assert len(chains) == 1
    assert _seqs(chains) == [("drift_velocity", "narrative")]
    assert 0.0 <= chains[0]["score"] <= 1.0


def test_fallback_when_no_start_reaches_narrative():
    # Five drift alerts (which sort before "drift_velocity") crowd out the start
    # slots under empty influence, and alerts are sinks → no start reaches the
    # narrative → explicit fallback to the strongest edge into it.
    g = build_phase7_graph(
        [], _analytics(),
        ["High drift A", "High drift B", "High drift C", "High drift D", "High drift E"],
        [NONE_FACTOR],
    )
    chains = generate_causal_chains(g, {}, {}, None)
    assert _seqs(chains) == [("drift_velocity", "narrative")]


def test_no_target_returns_empty():
    # No narrative-type node and no "narrative" id → nothing to explain.
    g = build_graph([make_node("a", "x", "a"), make_node("b", "x", "b")],
                    [make_edge("a", "b", 0.5)])
    assert generate_causal_chains(g, {"a": 0.9, "b": 0.5}, {}, None) == []


# ---------------------------------------------------------------------------
# Scoring formula + range
# ---------------------------------------------------------------------------

def test_chain_score_formula_exact():
    # edge_score 0.5 → (0.5+1)/2 = 0.75; node_score (0.6+0.4)/2 = 0.5;
    # chain = (0.75 + 0.5) / 2 = 0.625.
    g = build_graph([make_node("a", "x", "a"), make_node("narrative", "narrative", "N")],
                    [make_edge("a", "narrative", 0.5)])
    chains = generate_causal_chains(g, {"a": 0.6, "narrative": 0.4}, {}, None)
    assert chains[0]["score"] == pytest.approx(0.625)
    assert chains[0]["chain"].score == pytest.approx(0.625)  # carried on the chain too


def test_negative_edge_score_stays_in_unit_interval():
    # A counteracting (negative) edge pulls the score down but never below 0.
    g = build_graph([make_node("a", "x", "a"), make_node("narrative", "narrative", "N")],
                    [make_edge("a", "narrative", -0.8)])
    chains = generate_causal_chains(g, {"a": 0.5, "narrative": 0.5}, {}, None)
    # edge_score -0.8 → (−0.8+1)/2 = 0.1; node 0.5; chain = (0.1+0.5)/2 = 0.3.
    assert chains[0]["score"] == pytest.approx(0.3)
    assert 0.0 <= chains[0]["score"] <= 1.0


def test_serialization_shape_and_json():
    g, inf, cen, motifs = _phase7_stack(
        _analytics("Diverging", 0.5), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.6}],
    )
    serialized = scored_chains_to_dicts(generate_causal_chains(g, inf, cen, motifs))
    json.dumps(serialized)  # must not raise
    for ch in serialized:
        assert set(ch.keys()) == {"nodes", "edges", "score", "motifs"}
        assert set(ch["motifs"].keys()) == {
            "passes_bottleneck", "passes_attractor", "in_feedback_loop",
        }
        assert 0.0 <= ch["score"] <= 1.0


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


def test_endpoint_returns_causal_chains(client):
    _seed(0.2, 0.6, 0.0)
    _seed(0.8, 0.2, 1.0)
    body = client.get("/operator/telemetry").json()

    assert "causal_chains" in body
    assert isinstance(body["causal_chains"], list)
    assert len(body["causal_chains"]) >= 1
    for ch in body["causal_chains"]:
        assert set(ch.keys()) == {"nodes", "edges", "score", "motifs"}
        assert 0.0 <= ch["score"] <= 1.0
        assert set(ch["motifs"].keys()) == {
            "passes_bottleneck", "passes_attractor", "in_feedback_loop",
        }
    json.dumps(body["causal_chains"])  # JSON-serializable

    # Exactly what the 8.4 pipeline produces from the signals the endpoint returns.
    g = build_phase7_graph([], body["analytics"], body["alerts"], body["causal_factors"])
    inf = propagate_influence(g)
    cen = compute_node_centrality(g, inf)
    motifs = analyze_motifs(g, inf, cen)
    assert body["causal_chains"] == scored_chains_to_dicts(
        generate_causal_chains(g, inf, cen, motifs)
    )


def test_endpoint_empty_history_single_trivial_chain(client):
    body = client.get("/operator/telemetry").json()
    # No action source → the single analytics→narrative fallback chain.
    assert len(body["causal_chains"]) == 1
    assert [n["id"] for n in body["causal_chains"][0]["nodes"]] == ["drift_velocity", "narrative"]
    assert 0.0 <= body["causal_chains"][0]["score"] <= 1.0
