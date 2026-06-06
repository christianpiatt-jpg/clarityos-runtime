# tests/test_phase8_deltas.py
#
# CARD 8.6 — causal deltas (temporal change in causal structure): influence /
# centrality / motif / chain deltas between two snapshots, plus endpoint
# integration.
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
from phase7_telemetry import get_history
from phase8_deltas import compute_causal_deltas
from phase7_endpoint import DEFAULT_LIMIT, OPERATOR_ID, _causal_state


def _chain(node_ids, score):
    """A minimal chain dict in the 8.4 serialized shape (only the fields the
    delta engine reads: node ids + score)."""
    return {"nodes": [{"id": nid} for nid in node_ids], "edges": [], "score": score}


# ---------------------------------------------------------------------------
# Influence / centrality deltas
# ---------------------------------------------------------------------------

def test_influence_delta_basic():
    prev = {"influence": {"a": 0.2, "b": 0.5}}
    curr = {"influence": {"a": 0.5, "b": 0.5}}
    d = compute_causal_deltas(prev, curr)["influence_delta"]
    assert d["a"] == pytest.approx(0.3)
    assert d["b"] == pytest.approx(0.0)


def test_influence_delta_union_of_nodes():
    # A node only in prev declines to 0 (negative); only in curr rises from 0.
    prev = {"influence": {"a": 0.2, "b": 0.6}}
    curr = {"influence": {"a": 0.5, "c": 0.1}}
    d = compute_causal_deltas(prev, curr)["influence_delta"]
    assert list(d.keys()) == ["a", "b", "c"]            # sorted union
    assert d["a"] == pytest.approx(0.3)
    assert d["b"] == pytest.approx(-0.6)                # dropped out
    assert d["c"] == pytest.approx(0.1)                 # appeared


def test_scalar_deltas_clamped():
    prev = {"influence": {"a": -5.0}, "centrality": {"a": 5.0}}
    curr = {"influence": {"a": 5.0}, "centrality": {"a": -5.0}}
    out = compute_causal_deltas(prev, curr)
    assert out["influence_delta"]["a"] == 1.0           # +10 clamped
    assert out["centrality_delta"]["a"] == -1.0         # -10 clamped


def test_centrality_delta_independent_of_influence():
    prev = {"centrality": {"x": 0.4}}
    curr = {"centrality": {"x": 0.9}}
    out = compute_causal_deltas(prev, curr)
    assert out["centrality_delta"]["x"] == pytest.approx(0.5)
    assert out["influence_delta"] == {}                 # nothing supplied


# ---------------------------------------------------------------------------
# Motif deltas
# ---------------------------------------------------------------------------

def test_motif_delta_new_and_resolved():
    prev = {"motifs": {
        "feedback_loops": [["a", "b"]],
        "bottlenecks": ["x", "y"],
        "attractors": ["m"],
    }}
    curr = {"motifs": {
        "feedback_loops": [["a", "b"], ["c", "d"]],
        "bottlenecks": ["y", "z"],
        "attractors": [],
    }}
    md = compute_causal_deltas(prev, curr)["motif_delta"]
    assert md["new_loops"] == [["c", "d"]]
    assert md["resolved_loops"] == []
    assert md["new_bottlenecks"] == ["z"]
    assert md["resolved_bottlenecks"] == ["x"]
    assert md["new_attractors"] == []
    assert md["resolved_attractors"] == ["m"]


def test_motif_delta_outputs_sorted():
    prev = {"motifs": {"feedback_loops": [], "bottlenecks": [], "attractors": []}}
    curr = {"motifs": {"feedback_loops": [], "bottlenecks": ["z", "a", "m"], "attractors": []}}
    md = compute_causal_deltas(prev, curr)["motif_delta"]
    assert md["new_bottlenecks"] == ["a", "m", "z"]      # sorted


# ---------------------------------------------------------------------------
# Chain deltas
# ---------------------------------------------------------------------------

def test_chain_delta_new_resolved_and_score_shift():
    prev = {"chains": [_chain(["drift_velocity", "narrative"], 0.3)]}
    curr = {"chains": [
        _chain(["drift_velocity", "factor_0", "narrative"], 0.8),
        _chain(["drift_velocity", "narrative"], 0.5),
    ]}
    cd = compute_causal_deltas(prev, curr)["chain_delta"]
    assert cd["new_chains"] == [["drift_velocity", "factor_0", "narrative"]]
    assert cd["resolved_chains"] == []
    # avg(curr) = (0.8 + 0.5)/2 = 0.65; avg(prev) = 0.3; shift = 0.35.
    assert cd["score_shift"] == pytest.approx(0.35)


def test_chain_delta_resolved_and_empty_scores():
    prev = {"chains": [_chain(["a", "b"], 0.6)]}
    curr = {"chains": []}
    cd = compute_causal_deltas(prev, curr)["chain_delta"]
    assert cd["new_chains"] == []
    assert cd["resolved_chains"] == [["a", "b"]]
    assert cd["score_shift"] == pytest.approx(-0.6)     # 0.0 - 0.6


# ---------------------------------------------------------------------------
# Determinism + fallback + serialization
# ---------------------------------------------------------------------------

def test_deterministic():
    prev = {"influence": {"b": 0.1, "a": 0.2}, "centrality": {"a": 0.3},
            "motifs": {"feedback_loops": [], "bottlenecks": ["q"], "attractors": []},
            "chains": [_chain(["a", "b"], 0.4)]}
    curr = {"influence": {"a": 0.5, "b": 0.0}, "centrality": {"a": 0.9},
            "motifs": {"feedback_loops": [["a", "b"]], "bottlenecks": [], "attractors": ["a"]},
            "chains": [_chain(["a", "c", "b"], 0.7)]}
    assert compute_causal_deltas(prev, curr) == compute_causal_deltas(deepcopy(prev), deepcopy(curr))


def test_fallback_empty_and_none_inputs():
    for prev, curr in (({}, {}), (None, None)):
        out = compute_causal_deltas(prev, curr)
        assert out["influence_delta"] == {}
        assert out["centrality_delta"] == {}
        assert out["motif_delta"] == {
            "new_loops": [], "resolved_loops": [],
            "new_bottlenecks": [], "resolved_bottlenecks": [],
            "new_attractors": [], "resolved_attractors": [],
        }
        assert out["chain_delta"] == {"new_chains": [], "resolved_chains": [], "score_shift": 0.0}


def test_equal_snapshots_yield_zero_deltas():
    state = {"influence": {"a": 0.5}, "centrality": {"a": 0.7},
             "motifs": {"feedback_loops": [["a", "b"]], "bottlenecks": ["a"], "attractors": ["b"]},
             "chains": [_chain(["a", "b"], 0.6)]}
    out = compute_causal_deltas(state, deepcopy(state))
    assert all(v == 0.0 for v in out["influence_delta"].values())
    assert all(v == 0.0 for v in out["centrality_delta"].values())
    assert out["motif_delta"]["new_loops"] == [] and out["motif_delta"]["resolved_loops"] == []
    assert out["chain_delta"]["new_chains"] == [] and out["chain_delta"]["resolved_chains"] == []
    assert out["chain_delta"]["score_shift"] == 0.0


def test_output_json_serializable():
    prev = {"influence": {"a": 0.2}, "motifs": {"bottlenecks": ["x"]}, "chains": [_chain(["a", "b"], 0.3)]}
    curr = {"influence": {"a": 0.6}, "motifs": {"bottlenecks": ["y"]}, "chains": [_chain(["a", "c"], 0.7)]}
    json.dumps(compute_causal_deltas(prev, curr))       # must not raise


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


def test_endpoint_returns_causal_deltas(client):
    _seed(0.1, 0.7, 0.0)
    _seed(0.3, 0.5, 1.0)
    _seed(0.85, 0.15, 2.0)
    body = client.get("/operator/telemetry").json()

    assert "causal_deltas" in body
    deltas = body["causal_deltas"]
    assert set(deltas.keys()) == {"influence_delta", "centrality_delta", "motif_delta", "chain_delta"}
    assert set(deltas["motif_delta"].keys()) == {
        "new_loops", "resolved_loops", "new_bottlenecks",
        "resolved_bottlenecks", "new_attractors", "resolved_attractors",
    }
    assert set(deltas["chain_delta"].keys()) == {"new_chains", "resolved_chains", "score_shift"}
    json.dumps(deltas)                                  # JSON-serializable

    # Influence/centrality deltas stay in [-1, 1].
    for d in (deltas["influence_delta"], deltas["centrality_delta"]):
        for v in d.values():
            assert -1.0 <= v <= 1.0
    assert -1.0 <= deltas["chain_delta"]["score_shift"] <= 1.0

    # Exactly what the engine produces from prev (history[:-1]) vs curr (the
    # influence/centrality/motifs/chains the endpoint also returns).
    records = get_history(OPERATOR_ID, limit=DEFAULT_LIMIT)
    prev_state = _causal_state(records[:-1])
    curr_state = {
        "influence": body["causal_influence"],
        "centrality": body["causal_centrality"],
        "motifs": body["causal_motifs"],
        "chains": body["causal_chains"],
    }
    assert deltas == compute_causal_deltas(prev_state, curr_state)


def test_endpoint_empty_history_zero_deltas(client):
    body = client.get("/operator/telemetry").json()
    deltas = body["causal_deltas"]
    # No previous snapshot → every delta zero / empty.
    assert deltas["influence_delta"] == {} or all(v == 0.0 for v in deltas["influence_delta"].values())
    assert deltas["motif_delta"]["new_loops"] == []
    assert deltas["motif_delta"]["new_bottlenecks"] == []
    assert deltas["chain_delta"]["new_chains"] == []
    assert deltas["chain_delta"]["resolved_chains"] == []
    assert deltas["chain_delta"]["score_shift"] == 0.0


def test_endpoint_single_record_zero_deltas(client):
    # One record → records[:-1] is empty → no previous snapshot → zero deltas.
    _seed(0.5, 0.5, 0.0)
    deltas = client.get("/operator/telemetry").json()["causal_deltas"]
    assert all(v == 0.0 for v in deltas["influence_delta"].values())
    assert all(v == 0.0 for v in deltas["centrality_delta"].values())
    assert deltas["chain_delta"]["new_chains"] == []
    assert deltas["chain_delta"]["resolved_chains"] == []
    assert deltas["chain_delta"]["score_shift"] == 0.0
