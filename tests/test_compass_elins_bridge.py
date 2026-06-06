"""Unit tests for compass_elins_bridge — the pure ELINS<->Compass translator.

Self-contained: no fixtures, no I/O. The repo-root conftest already puts the
project root on sys.path, so the bare ``import compass_elins_bridge`` resolves.
"""
from __future__ import annotations

import pytest

from compass_elins_bridge import (
    CompassELINSBridge,
    CompassState,
    OperatorVector,
    LEVERAGE_SATURATION,
    VULNERABILITY_SATURATION,
    scale,
    derive_unknowns,
)


def _sample_elins_state() -> dict:
    return {
        "global_tension": 0.8,
        "drift_windows": [
            {"start": 0, "end": 10, "magnitude": 0.3},
            {"start": 10, "end": 20, "magnitude": 0.6},
        ],
        "narrative_opacity": 0.25,
        "operator_alignment_score": 0.7,
        "sector_multipliers": ["tech", "markets", "energy"],
        "operator_exposures": ["litigation", "regulatory"],
    }


def test_ingest_elins_state_mapping():
    bridge = CompassELINSBridge()
    state = bridge.ingest_elins_state(_sample_elins_state())

    assert isinstance(state, CompassState)
    # pressure    <- global_tension
    assert state.pressure == pytest.approx(0.8)
    # timing      <- strongest drift magnitude (max of 0.3, 0.6)
    assert state.timing == pytest.approx(0.6)
    # visibility  <- 1 - narrative_opacity (1 - 0.25)
    assert state.visibility == pytest.approx(0.75)
    # position    <- operator_alignment_score
    assert state.position == pytest.approx(0.7)
    # leverage    <- 3 sector multipliers / saturation
    assert state.leverage == pytest.approx(3 / LEVERAGE_SATURATION)
    # vulnerability <- 2 operator exposures / saturation
    assert state.vulnerability == pytest.approx(2 / VULNERABILITY_SATURATION)


def test_ingest_clamps_and_handles_missing_fields():
    # Bonus coverage: out-of-range input clamps, missing fields go neutral,
    # and every axis still lands inside [0.0, 1.0].
    bridge = CompassELINSBridge()
    state = bridge.ingest_elins_state({"global_tension": 5.0})

    assert state.pressure == 1.0       # 5.0 clamped to the ceiling
    assert state.timing == 0.0         # no drift windows
    assert state.visibility == 1.0     # opacity defaults to 0 -> fully visible
    assert state.position == 0.0
    assert state.leverage == 0.0
    assert state.vulnerability == 0.0
    for axis in vars(state).values():
        assert 0.0 <= axis <= 1.0


def test_export_operator_state():
    bridge = CompassELINSBridge()
    cs = CompassState(
        pressure=0.5, timing=0.4, visibility=0.7,
        position=0.6, leverage=0.3, vulnerability=0.2,
    )
    analysis = {"net_score": 1.23, "risk_level": "elevated"}
    vector = bridge.export_operator_state(cs, analysis)

    assert isinstance(vector, OperatorVector)
    # verdict comes from the analysis
    assert vector.operator_net == pytest.approx(1.23)
    assert vector.operator_risk == "elevated"
    # field-relevant axes pass through unchanged
    assert vector.pressure == pytest.approx(0.5)
    assert vector.visibility == pytest.approx(0.7)
    assert vector.leverage == pytest.approx(0.3)
    assert vector.vulnerability == pytest.approx(0.2)
    # timing/position are Compass-internal and not part of the operator vector
    assert not hasattr(vector, "timing")
    assert not hasattr(vector, "position")


def test_compute_operator_coupling_bounds():
    bridge = CompassELINSBridge()

    # Far above the ceiling -> clamps to 2.0
    high = CompassState(
        pressure=0.0, timing=0.0, visibility=10.0,
        position=0.0, leverage=10.0, vulnerability=0.0,
    )
    assert bridge.compute_operator_coupling(high) == 2.0

    # Far below the floor -> clamps to 0.1
    low = CompassState(
        pressure=100.0, timing=0.0, visibility=0.0,
        position=0.0, leverage=0.0, vulnerability=100.0,
    )
    assert bridge.compute_operator_coupling(low) == 0.1

    # In-range -> exact formula, no clamping:
    # (0.5 + 0.5) / (0.5 + 0.5 + 1) = 1.0 / 2.0 = 0.5
    mid = CompassState(
        pressure=0.5, timing=0.0, visibility=0.5,
        position=0.0, leverage=0.5, vulnerability=0.5,
    )
    assert bridge.compute_operator_coupling(mid) == pytest.approx(0.5)

    # The result is always inside the documented envelope.
    for cs in (high, low, mid):
        coupling = bridge.compute_operator_coupling(cs)
        assert 0.1 <= coupling <= 2.0


def test_determinism_same_input_same_output():
    bridge = CompassELINSBridge()
    elins_state = _sample_elins_state()
    analysis = {"net_score": 0.9, "risk_level": "moderate"}

    s1 = bridge.ingest_elins_state(elins_state)
    s2 = bridge.ingest_elins_state(elins_state)
    assert s1 == s2  # dataclass structural equality

    assert bridge.compute_operator_coupling(s1) == bridge.compute_operator_coupling(s2)
    assert bridge.export_operator_state(s1, analysis) == bridge.export_operator_state(s2, analysis)

    # The pure helpers are deterministic too.
    assert scale(0.42) == scale(0.42)
    assert derive_unknowns(0.3) == derive_unknowns(0.3)
