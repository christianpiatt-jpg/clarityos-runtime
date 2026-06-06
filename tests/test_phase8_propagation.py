# tests/test_phase8_propagation.py
#
# CARD 8.2 — multi-hop causal propagation (influence / centrality / ranked
# explanations), plus endpoint integration.
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
from phase8_propagation import (
    compute_node_centrality,
    propagate_influence,
    rank_causal_explanations,
)
from phase7_endpoint import OPERATOR_ID

NONE_FACTOR = {"action": "none", "correlation": 0.0, "contribution": 0.0}


def _analytics(trajectory="Stable", v=0.0, a=0.0, c=0.0, sf=0.0):
    return {
        "drift_velocity": v,
        "drift_acceleration": a,
        "coherence_trend": c,
        "stability_forecast": sf,
        "trajectory": trajectory,
    }


# ---------------------------------------------------------------------------
# Intrinsic weights + propagation
# ---------------------------------------------------------------------------

def test_intrinsic_weight_from_label():
    # drift_velocity has no inbound edges, so its influence == intrinsic.
    g = build_phase7_graph([], _analytics("Stable", v=0.5), [], [NONE_FACTOR])
    inf = propagate_influence(g)
    assert inf["drift_velocity"] == pytest.approx(0.5)


def test_intrinsic_uses_absolute_value():
    g = build_phase7_graph([], _analytics("Stable", c=-0.4), [], [NONE_FACTOR])
    inf = propagate_influence(g)
    assert inf["coherence_trend"] == pytest.approx(0.4)


def test_propagation_accumulates_and_clamps():
    g = build_graph(
        [make_node("a", "drift", "Drift velocity: 0.50"),
         make_node("z", "narrative", "Causal Narrative")],
        [make_edge("a", "z", 0.5)],
    )
    inf = propagate_influence(g)
    assert inf["a"] == pytest.approx(0.5)   # no inbound → intrinsic 0.5
    # z: 0.3 + 3 × (0.5 × 0.5) = 1.05 → clamped to 1.0
    assert inf["z"] == pytest.approx(1.0)


def test_multi_hop_reaches_distant_node():
    # b starts at 0; c only rises because influence flows a → b → c over steps.
    g = build_graph(
        [make_node("a", "drift", "Drift velocity: 0.40"),
         make_node("b", "action", "mid (contribution: 0.00)"),
         make_node("c", "narrative", "Causal Narrative")],
        [make_edge("a", "b", 0.5), make_edge("b", "c", 0.5)],
    )
    inf = propagate_influence(g)
    assert inf["a"] == pytest.approx(0.4)
    assert inf["c"] == pytest.approx(0.6)   # boosted past the 0.3 intrinsic via multi-hop


def test_influence_clamped_to_unit_interval():
    g = build_phase7_graph(
        [], _analytics("Diverging", 1.0, 1.0, -1.0, 0.0),
        ["High drift detected", "Coherence declining", "Rapid drift"],
        [{"action": "x", "correlation": 0.9, "contribution": 0.9}],
    )
    for v in propagate_influence(g).values():
        assert 0.0 <= v <= 1.0


def test_influence_deterministic_and_sorted():
    args = ([], _analytics("Diverging", 0.3),
            ["High drift detected", "Coherence declining"],
            [{"action": "prune", "correlation": 0.5, "contribution": 0.4}])
    g1 = build_phase7_graph(*args)
    g2 = build_phase7_graph(*deepcopy(args))
    assert propagate_influence(g1) == propagate_influence(g2)
    assert list(propagate_influence(g1).keys()) == sorted(g1.nodes.keys())


# ---------------------------------------------------------------------------
# Phase 8.2a — structured value preferred over label parsing
# ---------------------------------------------------------------------------

def test_intrinsic_prefers_value_over_label():
    # value 0.50, but label says 0.99 → influence uses value (no inbound edges).
    g = build_graph([make_node("a", "drift", "Drift velocity: 0.99", value=0.5)], [])
    assert propagate_influence(g)["a"] == pytest.approx(0.5)


def test_label_change_with_fixed_value_leaves_influence_unchanged():
    g1 = build_graph(
        [make_node("a", "drift", "Drift velocity: 0.10", value=0.6),
         make_node("z", "narrative", "Causal Narrative")],
        [make_edge("a", "z", 0.5)],
    )
    g2 = build_graph(
        [make_node("a", "drift", "Drift velocity: 0.95", value=0.6),  # label differs, value same
         make_node("z", "narrative", "Causal Narrative")],
        [make_edge("a", "z", 0.5)],
    )
    assert propagate_influence(g1) == propagate_influence(g2)


def test_legacy_label_fallback_when_value_none():
    # No value → deprecated label-parse fallback (legacy / hand-built node).
    g = build_graph([make_node("a", "drift", "Drift velocity: 0.30")], [])
    assert propagate_influence(g)["a"] == pytest.approx(0.30)


def test_alert_and_narrative_intrinsic_by_type_when_value_none():
    g = build_graph(
        [make_node("al", "alert", "Some alert text"),
         make_node("nar", "narrative", "Causal Narrative")],
        [],
    )
    inf = propagate_influence(g)
    assert inf["al"] == pytest.approx(0.5)
    assert inf["nar"] == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Centrality
# ---------------------------------------------------------------------------

def test_centrality_in_range_and_max_normalized():
    g = build_phase7_graph(
        [], _analytics("Diverging", 0.5), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.6}],
    )
    inf = propagate_influence(g)
    cen = compute_node_centrality(g, inf)
    assert set(cen.keys()) == set(g.nodes.keys())
    for v in cen.values():
        assert 0.0 <= v <= 1.0
    # max-normalized → the most central node is exactly 1.0
    assert max(cen.values()) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def test_ranked_explanations_shape_and_order():
    g = build_phase7_graph(
        [], _analytics("Diverging", 0.5), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.6}],
    )
    inf = propagate_influence(g)
    cen = compute_node_centrality(g, inf)
    ranked = rank_causal_explanations(g, inf, cen)

    assert len(ranked) == len(g.nodes)
    for entry in ranked:
        assert set(entry.keys()) == {"node", "label", "influence", "centrality", "score"}
        assert entry["score"] == pytest.approx((entry["influence"] + entry["centrality"]) / 2)
    scores = [e["score"] for e in ranked]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def test_outputs_json_serializable():
    g = build_phase7_graph(
        [], _analytics("Diverging", 0.5), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.6}],
    )
    inf = propagate_influence(g)
    cen = compute_node_centrality(g, inf)
    json.dumps(inf)
    json.dumps(cen)
    json.dumps(rank_causal_explanations(g, inf, cen))


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
        TelemetryRecord(
            timestamp=ts, superstructure=_state(),
            drift=drift, coherence_health=coherence, trust_band="HIGH",
        ),
    )


def test_endpoint_returns_propagation_fields(client):
    _seed(0.2, 0.6, 0.0)
    _seed(0.8, 0.2, 1.0)
    body = client.get("/operator/telemetry").json()

    assert "causal_influence" in body
    assert "causal_centrality" in body
    assert "ranked_explanations" in body
    assert isinstance(body["causal_influence"], dict)
    assert isinstance(body["causal_centrality"], dict)
    assert isinstance(body["ranked_explanations"], list)

    # Consistent with recomputing from the returned signals (history unused).
    g = build_phase7_graph([], body["analytics"], body["alerts"], body["causal_factors"])
    inf = propagate_influence(g)
    cen = compute_node_centrality(g, inf)
    assert body["causal_influence"] == inf
    assert body["causal_centrality"] == cen
    assert body["ranked_explanations"] == rank_causal_explanations(g, inf, cen)

    for v in body["causal_influence"].values():
        assert 0.0 <= v <= 1.0
