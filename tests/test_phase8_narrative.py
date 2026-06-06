# tests/test_phase8_narrative.py
#
# CARD 8.9 — unified causal narrative: a deterministic text template
# synthesizing the strongest chain + motifs + influence highlights + 8.6 deltas
# + 8.7 stability, plus endpoint integration.
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
from phase8_narrative import generate_causal_narrative
from phase7_endpoint import OPERATOR_ID


def _curr():
    return {
        "influence": {"drift_velocity": 0.6, "narrative": 0.4},
        "centrality": {"drift_velocity": 1.0},
        "motifs": {
            "feedback_loops": [["a", "b"]],
            "bottlenecks": ["drift_velocity"],
            "attractors": ["narrative"],
        },
        "chains": [
            {
                "nodes": [
                    {"id": "drift_velocity", "label": "Drift velocity: 0.60"},
                    {"id": "narrative", "label": "Causal Narrative"},
                ],
                "edges": [],
                "score": 0.78,
                "motifs": {},
            },
        ],
    }


def _deltas():
    return {
        "influence_delta": {"drift_velocity": 0.3},
        "centrality_delta": {},
        "motif_delta": {
            "new_loops": [["a", "b"]],
            "resolved_loops": [],
            "new_bottlenecks": ["drift_velocity"],
            "resolved_bottlenecks": [],
            "new_attractors": [],
            "resolved_attractors": [],
        },
        "chain_delta": {"new_chains": [], "resolved_chains": [], "score_shift": 0.15},
    }


def _stability():
    return {
        "stability_score": 0.75,
        "trend": "destabilizing",
        "drivers": {
            "rising_influence": ["drift_velocity"],
            "falling_influence": [],
            "new_bottlenecks": ["drift_velocity"],
            "resolved_bottlenecks": [],
            "new_loops": [["a", "b"]],
            "resolved_loops": [],
            "chain_strengthening": [],
            "chain_weakening": [],
        },
    }


# ---------------------------------------------------------------------------
# Section rendering
# ---------------------------------------------------------------------------

def test_primary_chain_rendering():
    text = generate_causal_narrative(_curr(), _deltas(), _stability())
    assert "Primary Causal Chain:" in text
    assert "- Drift velocity: 0.60 → Causal Narrative" in text
    assert "- Chain score: 0.78" in text


def test_motif_rendering():
    text = generate_causal_narrative(_curr(), _deltas(), _stability())
    assert "Structural Motifs:" in text
    assert "- Feedback loops: a → b" in text
    assert "- Bottlenecks: drift_velocity" in text
    assert "- Attractors: narrative" in text


def test_influence_highlights_rendering():
    text = generate_causal_narrative(_curr(), _deltas(), _stability())
    assert "Influence Highlights:" in text
    assert "- Rising: drift_velocity" in text
    assert "- Falling: none" in text


def test_causal_changes_rendering():
    text = generate_causal_narrative(_curr(), _deltas(), _stability())
    assert "Causal Changes Since Last Snapshot:" in text
    assert "- New motifs: loops: a → b; bottlenecks: drift_velocity; attractors: none" in text
    assert "- Resolved motifs: loops: none; bottlenecks: none; attractors: none" in text
    assert "- Chain score shift: 0.15" in text


def test_stability_rendering():
    text = generate_causal_narrative(_curr(), _deltas(), _stability())
    assert "Stability Forecast:" in text
    assert "- Score: 0.75" in text
    assert "- Trend: destabilizing" in text
    assert (
        "- Drivers: rising influence (1), falling influence (0), "
        "new bottlenecks (1), resolved bottlenecks (0), new loops (1), "
        "resolved loops (0), chain strengthening (0), chain weakening (0)"
    ) in text


# ---------------------------------------------------------------------------
# Formatting + sorting
# ---------------------------------------------------------------------------

def test_numbers_two_decimals():
    curr = _curr()
    curr["chains"][0]["score"] = 0.5
    deltas = _deltas()
    deltas["chain_delta"]["score_shift"] = -0.3
    stability = _stability()
    stability["stability_score"] = 0.4
    text = generate_causal_narrative(curr, deltas, stability)
    assert "- Chain score: 0.50" in text
    assert "- Chain score shift: -0.30" in text
    assert "- Score: 0.40" in text


def test_lists_sorted():
    curr = _curr()
    curr["motifs"]["bottlenecks"] = ["z", "a", "m"]
    stability = _stability()
    stability["drivers"]["rising_influence"] = ["z", "a", "m"]
    text = generate_causal_narrative(curr, _deltas(), stability)
    assert "- Bottlenecks: a, m, z" in text
    assert "- Rising: a, m, z" in text


# ---------------------------------------------------------------------------
# Fallbacks + determinism + serialization
# ---------------------------------------------------------------------------

def test_fallback_empty_inputs():
    text = generate_causal_narrative({}, {}, {})
    assert "- (no causal chain detected)" in text
    assert "- Chain score: 0.00" in text
    assert "- Feedback loops: none" in text
    assert "- Bottlenecks: none" in text
    assert "- Attractors: none" in text
    assert "- Rising: none" in text
    assert "- Falling: none" in text
    assert "- New motifs: loops: none; bottlenecks: none; attractors: none" in text
    assert "- Chain score shift: 0.00" in text
    assert "- Score: 0.00" in text
    assert "- Trend: steady" in text
    assert "chain weakening (0)" in text


def test_deterministic():
    args = (_curr(), _deltas(), _stability())
    assert generate_causal_narrative(*args) == generate_causal_narrative(*deepcopy(args))


def test_returns_string_and_json_serializable():
    text = generate_causal_narrative(_curr(), _deltas(), _stability())
    assert isinstance(text, str)
    json.dumps({"causal_narrative": text})            # must not raise


def test_section_order():
    text = generate_causal_narrative(_curr(), _deltas(), _stability())
    order = [
        "Primary Causal Chain:",
        "Structural Motifs:",
        "Influence Highlights:",
        "Causal Changes Since Last Snapshot:",
        "Stability Forecast:",
    ]
    positions = [text.index(h) for h in order]
    assert positions == sorted(positions)             # sections appear in order


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


def test_endpoint_returns_causal_narrative(client):
    _seed(0.1, 0.7, 0.0)
    _seed(0.3, 0.5, 1.0)
    _seed(0.85, 0.15, 2.0)
    body = client.get("/operator/telemetry").json()

    assert "causal_narrative" in body
    narrative = body["causal_narrative"]
    assert isinstance(narrative, str)
    for header in (
        "Primary Causal Chain:", "Structural Motifs:", "Influence Highlights:",
        "Causal Changes Since Last Snapshot:", "Stability Forecast:",
    ):
        assert header in narrative
    json.dumps(narrative)

    # Distinct from the Phase 7.9 narrative field.
    assert body["narrative"] != narrative

    # Exactly what the engine produces from the curr state + deltas + stability
    # the endpoint also returns.
    curr_state = {
        "influence": body["causal_influence"],
        "centrality": body["causal_centrality"],
        "motifs": body["causal_motifs"],
        "chains": body["causal_chains"],
    }
    assert narrative == generate_causal_narrative(
        curr_state, body["causal_deltas"], body["causal_stability"]
    )


def test_endpoint_empty_history_narrative_is_steady_fallback(client):
    body = client.get("/operator/telemetry").json()
    narrative = body["causal_narrative"]
    assert "Primary Causal Chain:" in narrative
    assert "- Trend: steady" in narrative
    assert "- Score: 1.00" in narrative                # no previous snapshot → score 1.0
