# tests/test_phase8_unified_narrative.py
#
# CARD 8.10 — unified temporal-causal narrative: fuses the Phase 7.9 temporal
# narrative + Phase 7 drift/coherence/trust with the Phase 8 causal narrative +
# chains/motifs/deltas/stability into one deterministic block with an Integrated
# Interpretation + Overall Assessment. Plus endpoint integration.
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
from phase8_unified_narrative import generate_unified_narrative
from phase7_endpoint import OPERATOR_ID

_EMPTY_MOTIF_DELTA = {
    "new_loops": [], "resolved_loops": [], "new_bottlenecks": [],
    "resolved_bottlenecks": [], "new_attractors": [], "resolved_attractors": [],
}


def _temporal(narrative="Temporal drift summary.", drift=0.2, coherence_trend=0.3, trust_band="HIGH"):
    return {"narrative": narrative, "drift": drift,
            "coherence_trend": coherence_trend, "trust_band": trust_band}


def _causal(narrative="Causal structure summary.", chains=None, motifs=None,
            deltas=None, stability=None):
    return {
        "narrative": narrative,
        "chains": chains if chains is not None else [
            {"nodes": [{"id": "drift_velocity", "label": "Drift velocity: 0.20"},
                       {"id": "narrative", "label": "Causal Narrative"}], "score": 0.5},
        ],
        "motifs": motifs if motifs is not None else {
            "feedback_loops": [], "bottlenecks": ["drift_velocity"], "attractors": [],
        },
        "deltas": deltas if deltas is not None else {
            "influence_delta": {"drift_velocity": 0.1}, "centrality_delta": {},
            "motif_delta": {**_EMPTY_MOTIF_DELTA, "new_bottlenecks": ["drift_velocity"]},
            "chain_delta": {"new_chains": [], "resolved_chains": [], "score_shift": 0.15},
        },
        "stability": stability if stability is not None else {
            "stability_score": 0.75, "trend": "destabilizing", "drivers": {},
        },
    }


def _blocks(drift, stability_score, motif_delta=None):
    """Minimal blocks for exercising the Overall Assessment classifier."""
    deltas = {
        "influence_delta": {}, "centrality_delta": {},
        "motif_delta": motif_delta or dict(_EMPTY_MOTIF_DELTA),
        "chain_delta": {"score_shift": 0.0},
    }
    return (
        {"narrative": "t", "drift": drift, "coherence_trend": 0.0, "trust_band": "HIGH"},
        {"narrative": "c", "chains": [], "motifs": {}, "deltas": deltas,
         "stability": {"stability_score": stability_score, "trend": "x", "drivers": {}}},
    )


def _assessment(text):
    return text.split("Overall Assessment:\n")[1].strip()


# ---------------------------------------------------------------------------
# Embedding + sections
# ---------------------------------------------------------------------------

def test_title_and_summary_sections_embed_both_narratives():
    text = generate_unified_narrative(
        _temporal(narrative="TEMPORAL-BODY"), _causal(narrative="CAUSAL-BODY"))
    assert "Unified Temporal" in text.splitlines()[0]
    assert "Temporal Summary:\nTEMPORAL-BODY" in text
    assert "Causal Summary:\nCAUSAL-BODY" in text


def test_integrated_interpretation_lines():
    text = generate_unified_narrative(_temporal(), _causal())
    assert "Integrated Interpretation:" in text
    assert "- Drift level: 0.20" in text
    assert "- Coherence trend: 0.30" in text
    assert "- Trust band: HIGH" in text
    assert "- Primary causal chain: Drift velocity: 0.20 → Causal Narrative" in text
    assert "- Structural motifs: loops: none; bottlenecks: drift_velocity; attractors: none" in text
    assert "- Key deltas: influence changes: 1, centrality changes: 0, motif events: 1, chain score shift: 0.15" in text
    assert "- Stability forecast: destabilizing (score 0.75)" in text


# ---------------------------------------------------------------------------
# Overall assessment classification
# ---------------------------------------------------------------------------

def test_assessment_stable():
    assert _assessment(generate_unified_narrative(*_blocks(0.2, 0.8))) == "Stable"


def test_assessment_destabilizing_by_drift():
    assert _assessment(generate_unified_narrative(*_blocks(0.8, 0.8))) == "Destabilizing"


def test_assessment_destabilizing_by_new_bottleneck():
    md = {**_EMPTY_MOTIF_DELTA, "new_bottlenecks": ["x"]}
    assert _assessment(generate_unified_narrative(*_blocks(0.1, 0.9, md))) == "Destabilizing"


def test_assessment_destabilizing_by_new_loop():
    md = {**_EMPTY_MOTIF_DELTA, "new_loops": [["a", "b"]]}
    assert _assessment(generate_unified_narrative(*_blocks(0.1, 0.9, md))) == "Destabilizing"


def test_assessment_destabilizing_by_low_stability():
    assert _assessment(generate_unified_narrative(*_blocks(0.1, 0.3))) == "Destabilizing"


def test_assessment_transitioning():
    md = {**_EMPTY_MOTIF_DELTA, "resolved_bottlenecks": ["x"]}  # motif event, not new
    assert _assessment(generate_unified_narrative(*_blocks(0.2, 0.6, md))) == "Transitioning"


def test_assessment_shifting_by_drift_band():
    assert _assessment(generate_unified_narrative(*_blocks(0.5, 0.6))) == "Shifting"


def test_assessment_shifting_is_gap_default():
    # High stability + low drift but a NEW attractor (not loop/bottleneck): not
    # destabilizing, not Stable (new motif present), not transitioning (score
    # > 0.7), not in a Shifting band → falls through to the Shifting default.
    md = {**_EMPTY_MOTIF_DELTA, "new_attractors": ["a"]}
    assert _assessment(generate_unified_narrative(*_blocks(0.1, 0.9, md))) == "Shifting"


# ---------------------------------------------------------------------------
# Formatting + sorting + determinism
# ---------------------------------------------------------------------------

def test_numbers_two_decimals_and_lists_sorted():
    causal = _causal(
        motifs={"feedback_loops": [], "bottlenecks": ["z", "a", "m"], "attractors": []},
        deltas={"influence_delta": {}, "centrality_delta": {},
                "motif_delta": dict(_EMPTY_MOTIF_DELTA),
                "chain_delta": {"score_shift": -0.3}},
        stability={"stability_score": 0.4, "trend": "transitioning", "drivers": {}},
    )
    text = generate_unified_narrative(_temporal(drift=0.5), causal)
    assert "- Drift level: 0.50" in text
    assert "- Structural motifs: loops: none; bottlenecks: a, m, z; attractors: none" in text  # sorted
    assert "chain score shift: -0.30" in text
    assert "(score 0.40)" in text


def test_deterministic():
    args = (_temporal(), _causal())
    assert generate_unified_narrative(*args) == generate_unified_narrative(*deepcopy(args))


# ---------------------------------------------------------------------------
# Fallbacks + serialization
# ---------------------------------------------------------------------------

def test_fallback_missing_motifs_deltas_no_prev_snapshot():
    # No previous snapshot: empty deltas, stability fallback (score 1.0 / steady),
    # and a causal block missing the motifs + deltas keys entirely.
    temporal = {"narrative": "", "drift": None, "coherence_trend": 0.0, "trust_band": None}
    causal = {"narrative": "", "chains": [],
              "stability": {"stability_score": 1.0, "trend": "steady", "drivers": {}}}
    text = generate_unified_narrative(temporal, causal)
    assert "Temporal Summary:\n(no temporal narrative)" in text
    assert "Causal Summary:\n(no causal narrative)" in text
    assert "- Drift level: 0.00" in text
    assert "- Trust band: —" in text
    assert "- Primary causal chain: (none)" in text
    assert "- Structural motifs: loops: none; bottlenecks: none; attractors: none" in text
    assert "- Key deltas: influence changes: 0, centrality changes: 0, motif events: 0, chain score shift: 0.00" in text
    assert "- Stability forecast: steady (score 1.00)" in text
    assert _assessment(text) == "Stable"               # drift 0, stability 1.0, no new motifs


def test_empty_inputs_do_not_crash():
    text = generate_unified_narrative({}, {})
    assert "(no temporal narrative)" in text
    assert "(no causal narrative)" in text
    assert "Overall Assessment:" in text


def test_returns_string_and_json_serializable():
    text = generate_unified_narrative(_temporal(), _causal())
    assert isinstance(text, str)
    json.dumps({"unified_narrative": text})


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


def test_endpoint_returns_unified_narrative(client):
    _seed(0.1, 0.7, 0.0)
    _seed(0.3, 0.5, 1.0)
    _seed(0.85, 0.15, 2.0)
    body = client.get("/operator/telemetry").json()

    assert "unified_narrative" in body
    unified = body["unified_narrative"]
    assert isinstance(unified, str)
    for header in ("Temporal Summary:", "Causal Summary:",
                   "Integrated Interpretation:", "Overall Assessment:"):
        assert header in unified
    # The Phase 8.9 causal narrative is embedded verbatim in the Causal Summary.
    assert "Primary Causal Chain:" in unified
    json.dumps(unified)

    # Exactly what the engine produces from the blocks the endpoint assembles.
    latest = body["latest"]
    temporal_block = {
        "narrative": body["narrative"],
        "drift": latest["drift"] if latest else None,
        "coherence_trend": body["analytics"]["coherence_trend"],
        "trust_band": latest["trust_band"] if latest else None,
    }
    causal_block = {
        "narrative": body["causal_narrative"],
        "chains": body["causal_chains"],
        "motifs": body["causal_motifs"],
        "deltas": body["causal_deltas"],
        "stability": body["causal_stability"],
    }
    assert unified == generate_unified_narrative(temporal_block, causal_block)


def test_endpoint_empty_history_assessment_stable(client):
    body = client.get("/operator/telemetry").json()
    unified = body["unified_narrative"]
    # No telemetry → drift 0, stability fallback 1.0, no motifs → Stable.
    assert unified.rstrip().endswith("Stable")
