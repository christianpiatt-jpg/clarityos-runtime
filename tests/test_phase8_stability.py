# tests/test_phase8_stability.py
#
# CARD 8.7 — causal stability forecast: stability score + trend classification
# + drivers, derived from the 8.6 deltas + current causal state, plus endpoint
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
from phase8_stability import compute_causal_stability
from phase7_endpoint import OPERATOR_ID

_MOTIF_KEYS = (
    "new_loops", "resolved_loops", "new_bottlenecks",
    "resolved_bottlenecks", "new_attractors", "resolved_attractors",
)


def _motif(**kwargs):
    """A motif_delta block with all six families present (empty by default)."""
    return {key: kwargs.get(key, []) for key in _MOTIF_KEYS}


def _deltas(influence=None, centrality=None, motif=None, score_shift=0.0,
            new_chains=None, resolved_chains=None):
    return {
        "influence_delta": influence or {},
        "centrality_delta": centrality or {},
        "motif_delta": motif or _motif(),
        "chain_delta": {
            "new_chains": new_chains or [],
            "resolved_chains": resolved_chains or [],
            "score_shift": score_shift,
        },
    }


def _chain(node_ids):
    return {"nodes": [{"id": nid} for nid in node_ids], "edges": [], "score": 0.5}


# ---------------------------------------------------------------------------
# Stability score
# ---------------------------------------------------------------------------

def test_influence_and_centrality_components():
    # influence vol = mean(|0.4|, |0.0|) = 0.2 → influence_score 0.8;
    # centrality vol = 0.6 → centrality_score 0.4; motif 1.0; chain 1.0.
    out = compute_causal_stability(
        _deltas(influence={"a": 0.4, "b": 0.0}, centrality={"a": 0.6}), {})
    assert out["stability_score"] == pytest.approx((0.8 + 0.4 + 1.0 + 1.0) / 4.0)


def test_motif_component_scales_by_ten():
    # 5 motif events → motif_score = 1 - 5/10 = 0.5.
    out = compute_causal_stability(
        _deltas(motif=_motif(new_bottlenecks=["a", "b"], resolved_attractors=["c", "d", "e"])),
        {},
    )
    # influence/centrality empty → 1.0 each; chain shift 0 → 1.0; motif 0.5.
    assert out["stability_score"] == pytest.approx((1.0 + 1.0 + 0.5 + 1.0) / 4.0)


def test_chain_component_from_score_shift():
    out = compute_causal_stability(_deltas(score_shift=0.3), {})
    # chain_score = 1 - 0.3 = 0.7; others 1.0.
    assert out["stability_score"] == pytest.approx((1.0 + 1.0 + 1.0 + 0.7) / 4.0)


def test_score_clamped_components():
    # Huge volatility + shift clamp each component to 0; many motif events → 0.
    out = compute_causal_stability(
        _deltas(influence={"a": 5.0}, centrality={"a": 5.0},
                motif=_motif(new_bottlenecks=[f"b{i}" for i in range(20)]),
                score_shift=5.0),
        {},
    )
    assert out["stability_score"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Trend classification
# ---------------------------------------------------------------------------

def test_trend_steady_on_no_movement():
    out = compute_causal_stability(_deltas(), {})       # all-zero deltas
    assert out["stability_score"] == pytest.approx(1.0)
    assert out["trend"] == "steady"


def test_trend_stabilizing():
    # Small influence movement, no motifs, tiny chain shift, high score.
    out = compute_causal_stability(
        _deltas(influence={"a": 0.05}, centrality={"a": 0.05}, score_shift=0.02), {})
    assert out["stability_score"] > 0.7
    assert out["trend"] == "stabilizing"


def test_trend_destabilizing_by_low_score():
    out = compute_causal_stability(
        _deltas(influence={"a": 1.0, "b": 1.0}, centrality={"a": 1.0}, score_shift=1.0), {})
    assert out["stability_score"] < 0.4
    assert out["trend"] == "destabilizing"


def test_trend_destabilizing_by_new_bottleneck_even_at_high_score():
    out = compute_causal_stability(
        _deltas(motif=_motif(new_bottlenecks=["drift_velocity"])), {})
    assert out["stability_score"] > 0.7        # high score …
    assert out["trend"] == "destabilizing"     # … but a new bottleneck forces destabilizing


def test_trend_destabilizing_by_new_loop():
    out = compute_causal_stability(
        _deltas(motif=_motif(new_loops=[["a", "b"]])), {})
    assert out["trend"] == "destabilizing"


def test_trend_transitioning():
    # Mid score (0.6) + a (non-loop, non-bottleneck) motif event.
    out = compute_causal_stability(
        _deltas(influence={"a": 0.6}, centrality={"a": 0.6},
                motif=_motif(resolved_bottlenecks=["x"]), score_shift=0.3),
        {},
    )
    assert 0.4 <= out["stability_score"] <= 0.7
    assert out["trend"] == "transitioning"


def test_trend_steady_mid_score_no_motifs():
    out = compute_causal_stability(
        _deltas(influence={"a": 0.5}, centrality={"a": 0.5}, score_shift=0.4), {})
    assert 0.4 <= out["stability_score"] <= 0.7
    assert out["trend"] == "steady"            # mid score, no motif events, not destabilizing


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------

def test_drivers_influence_and_motifs():
    out = compute_causal_stability(
        _deltas(
            influence={"up": 0.3, "down": -0.4, "tiny": 0.05, "ntiny": -0.05},
            motif=_motif(new_loops=[["a", "b"]], new_bottlenecks=["nb"], resolved_bottlenecks=["rb"]),
        ),
        {},
    )
    d = out["drivers"]
    assert d["rising_influence"] == ["up"]       # 0.05 / -0.05 below threshold
    assert d["falling_influence"] == ["down"]
    assert d["new_bottlenecks"] == ["nb"]
    assert d["resolved_bottlenecks"] == ["rb"]
    assert d["new_loops"] == [["a", "b"]]
    assert d["resolved_loops"] == []


def test_drivers_chain_strengthening_and_weakening():
    curr = {"chains": [_chain(["drift_velocity", "narrative"])]}
    strengthening = compute_causal_stability(_deltas(score_shift=0.2), curr)["drivers"]
    assert strengthening["chain_strengthening"] == [["drift_velocity", "narrative"]]
    assert strengthening["chain_weakening"] == []

    weakening = compute_causal_stability(_deltas(score_shift=-0.2), curr)["drivers"]
    assert weakening["chain_weakening"] == [["drift_velocity", "narrative"]]
    assert weakening["chain_strengthening"] == []

    # A shift inside ±0.1 moves neither.
    quiet = compute_causal_stability(_deltas(score_shift=0.05), curr)["drivers"]
    assert quiet["chain_strengthening"] == [] and quiet["chain_weakening"] == []


def test_drivers_sorted_deterministic():
    out = compute_causal_stability(
        _deltas(influence={"z": 0.5, "a": 0.5, "m": 0.5}), {})
    assert out["drivers"]["rising_influence"] == ["a", "m", "z"]


def test_deterministic():
    deltas = _deltas(influence={"b": 0.3, "a": 0.2}, centrality={"a": 0.4},
                     motif=_motif(new_bottlenecks=["q"]), score_shift=0.25)
    curr = {"chains": [_chain(["a", "b"])]}
    assert compute_causal_stability(deltas, curr) == compute_causal_stability(deepcopy(deltas), deepcopy(curr))


def test_output_json_serializable_and_shape():
    out = compute_causal_stability(_deltas(influence={"a": 0.3}, score_shift=0.2),
                                   {"chains": [_chain(["a", "b"])]})
    json.dumps(out)
    assert set(out.keys()) == {"stability_score", "trend", "drivers"}
    assert set(out["drivers"].keys()) == {
        "rising_influence", "falling_influence", "new_bottlenecks",
        "resolved_bottlenecks", "new_loops", "resolved_loops",
        "chain_strengthening", "chain_weakening",
    }


def test_fallback_empty_inputs():
    out = compute_causal_stability({}, {})
    assert out["stability_score"] == pytest.approx(1.0)
    assert out["trend"] == "steady"
    assert all(v == [] for v in out["drivers"].values())


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


def test_endpoint_returns_causal_stability(client):
    _seed(0.1, 0.7, 0.0)
    _seed(0.3, 0.5, 1.0)
    _seed(0.85, 0.15, 2.0)
    body = client.get("/operator/telemetry").json()

    assert "causal_stability" in body
    stability = body["causal_stability"]
    assert set(stability.keys()) == {"stability_score", "trend", "drivers"}
    assert 0.0 <= stability["stability_score"] <= 1.0
    assert stability["trend"] in {"stabilizing", "destabilizing", "transitioning", "steady"}
    assert set(stability["drivers"].keys()) == {
        "rising_influence", "falling_influence", "new_bottlenecks",
        "resolved_bottlenecks", "new_loops", "resolved_loops",
        "chain_strengthening", "chain_weakening",
    }
    json.dumps(stability)

    # Exactly what the engine produces from the deltas + current state the
    # endpoint also returns.
    curr_state = {
        "influence": body["causal_influence"],
        "centrality": body["causal_centrality"],
        "motifs": body["causal_motifs"],
        "chains": body["causal_chains"],
    }
    assert stability == compute_causal_stability(body["causal_deltas"], curr_state)


def test_endpoint_empty_history_steady_score_one(client):
    body = client.get("/operator/telemetry").json()
    assert body["causal_stability"]["stability_score"] == pytest.approx(1.0)
    assert body["causal_stability"]["trend"] == "steady"
