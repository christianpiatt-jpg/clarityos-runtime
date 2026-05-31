# tests/test_phase8_inference.py
#
# CARD 8.1 — first-order causal chain generation from Phase 7 signals, plus
# endpoint integration (causal_graph + primary_chain on /operator/telemetry).
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
from phase8_inference import build_phase7_graph, extract_primary_chain
from phase8_structures import chain_to_dict, graph_to_dict
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
# Graph nodes
# ---------------------------------------------------------------------------

def test_graph_has_all_analytics_and_narrative_nodes():
    g = build_phase7_graph([], _analytics(), ["No alerts — operator trajectory stable"], [NONE_FACTOR])
    for nid in (
        "drift_velocity", "drift_acceleration", "coherence_trend",
        "stability_forecast", "trajectory", "narrative",
    ):
        assert nid in g.nodes
    assert "alert_0" in g.nodes
    # The "none" sentinel produces no factor node.
    assert not any(nid.startswith("factor_") for nid in g.nodes)


def test_real_factor_creates_action_node():
    g = build_phase7_graph([], _analytics("Diverging"), ["x"], [
        {"action": "prune", "correlation": 0.5, "contribution": 0.4},
    ])
    assert "factor_0" in g.nodes
    assert g.nodes["factor_0"].type == "action"
    assert g.nodes["factor_0"].label.startswith("prune")


def test_nodes_carry_structured_value():
    # Phase 8.2a: analytics + factor nodes carry a normalized magnitude;
    # categorical/structural nodes leave value None.
    g = build_phase7_graph(
        [], _analytics("Diverging", v=0.5, c=-0.4), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.6}],
    )
    assert g.nodes["drift_velocity"].value == pytest.approx(0.5)   # abs(0.5)
    assert g.nodes["coherence_trend"].value == pytest.approx(0.4)  # abs(-0.4)
    assert g.nodes["factor_0"].value == pytest.approx(0.6)         # contribution
    assert g.nodes["trajectory"].value is None                    # categorical
    assert g.nodes["alert_0"].value is None                       # 8.2 injects 0.5 by type
    assert g.nodes["narrative"].value is None                     # 8.2 injects 0.3 by type


# ---------------------------------------------------------------------------
# Edges + deterministic weights
# ---------------------------------------------------------------------------

def test_drift_alert_edge_from_drift_velocity():
    g = build_phase7_graph(
        [], _analytics("Diverging"),
        ["High drift detected — operator identity destabilizing"], [NONE_FACTOR],
    )
    assert any(
        e.source == "drift_velocity" and e.target == "alert_0" and e.weight == 0.5
        for e in g.edges
    )


def test_coherence_alert_edge_from_coherence_trend():
    g = build_phase7_graph(
        [], _analytics(),
        ["Coherence declining — structural alignment weakening"], [NONE_FACTOR],
    )
    assert any(
        e.source == "coherence_trend" and e.target == "alert_0" and e.weight == 0.5
        for e in g.edges
    )


def test_unrelated_alert_has_no_analytics_edge():
    g = build_phase7_graph(
        [], _analytics(),
        ["Low stability forecast — consider reviewing recent operator actions"], [NONE_FACTOR],
    )
    assert not any(e.target == "alert_0" for e in g.edges)


def test_factor_edges_weighted_by_contribution():
    g = build_phase7_graph([], _analytics("Diverging"), ["x"], [
        {"action": "prune", "correlation": 0.5, "contribution": 0.4},
    ])
    # factor -> narrative weight = contribution
    assert any(
        e.source == "factor_0" and e.target == "narrative" and e.weight == pytest.approx(0.4)
        for e in g.edges
    )
    # contribution 0.4 > 0.1 -> drift_velocity -> factor_0 (weight = contribution)
    assert any(
        e.source == "drift_velocity" and e.target == "factor_0" and e.weight == pytest.approx(0.4)
        for e in g.edges
    )


def test_low_contribution_factor_has_no_analytics_edge():
    g = build_phase7_graph([], _analytics(), ["x"], [
        {"action": "tiny", "correlation": 0.05, "contribution": 0.05},  # not > 0.1
    ])
    assert any(e.source == "factor_0" and e.target == "narrative" for e in g.edges)
    assert not any(e.source == "drift_velocity" and e.target == "factor_0" for e in g.edges)


def test_analytics_to_narrative_edge_always_present():
    g = build_phase7_graph([], _analytics(), ["x"], [NONE_FACTOR])
    assert any(
        e.source == "drift_velocity" and e.target == "narrative" and e.weight == 0.3
        for e in g.edges
    )


# ---------------------------------------------------------------------------
# Primary chain extraction
# ---------------------------------------------------------------------------

def test_primary_chain_starts_from_strongest_factor():
    g = build_phase7_graph([], _analytics("Diverging"), ["x"], [
        {"action": "weak", "correlation": 0.2, "contribution": 0.2},
        {"action": "strong", "correlation": 0.6, "contribution": 0.6},
    ])
    chain = extract_primary_chain(g)
    assert [n.id for n in chain.nodes] == ["factor_1", "narrative"]
    assert chain.nodes[0].label.startswith("strong")
    assert chain.score == pytest.approx(0.6)


def test_primary_chain_fallback_when_no_factors():
    g = build_phase7_graph([], _analytics(), ["x"], [NONE_FACTOR])
    chain = extract_primary_chain(g)
    assert [n.id for n in chain.nodes] == ["drift_velocity", "narrative"]
    assert chain.score == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Determinism + serialization
# ---------------------------------------------------------------------------

def test_deterministic():
    args = ([], _analytics("Diverging", 0.3), ["High drift detected"], [
        {"action": "prune", "correlation": 0.5, "contribution": 0.4},
    ])
    g1 = build_phase7_graph(*args)
    g2 = build_phase7_graph(*deepcopy(args))
    assert graph_to_dict(g1) == graph_to_dict(g2)
    assert chain_to_dict(extract_primary_chain(g1)) == chain_to_dict(extract_primary_chain(g2))


def test_graph_and_chain_json_serializable():
    g = build_phase7_graph(
        [], _analytics("Diverging"), ["High drift detected"],
        [{"action": "prune", "correlation": 0.5, "contribution": 0.4}],
    )
    json.dumps(graph_to_dict(g))             # must not raise
    json.dumps(chain_to_dict(extract_primary_chain(g)))


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


def test_endpoint_returns_graph_and_chain(client):
    _seed(0.2, 0.6, 0.0)
    _seed(0.8, 0.2, 1.0)
    body = client.get("/operator/telemetry").json()

    assert "causal_graph" in body and "primary_chain" in body
    assert set(body["causal_graph"].keys()) == {"nodes", "edges"}
    assert set(body["primary_chain"].keys()) == {"nodes", "edges", "score"}

    # The endpoint's graph/chain are exactly what build/extract produce from the
    # analytics / alerts / causal_factors it also returns (history is unused).
    g = build_phase7_graph([], body["analytics"], body["alerts"], body["causal_factors"])
    assert body["causal_graph"] == graph_to_dict(g)
    assert body["primary_chain"] == chain_to_dict(extract_primary_chain(g))


def test_endpoint_empty_history_primary_chain_is_fallback(client):
    body = client.get("/operator/telemetry").json()
    # No action source → fallback analytics→narrative chain.
    assert [n["id"] for n in body["primary_chain"]["nodes"]] == ["drift_velocity", "narrative"]
    assert body["primary_chain"]["score"] == pytest.approx(0.3)
