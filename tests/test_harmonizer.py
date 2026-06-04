"""Tests for the orientation Harmonizer (root modules harmonizer +
orientation_contracts).

Covers each merge rule's semantics, determinism (same inputs -> identical
output across repeated calls), and the clock-free snapshot builder (a fixed
timestamp argument is used verbatim — no wall-clock access).
"""
from __future__ import annotations

from datetime import datetime

from orientation_contracts import (
    PressureField,
    StrainVector,
    IndividualState,
    OrgState,
    HydraulicState,
    MultiAgentState,
    UnifiedSnapshot,
)
from harmonizer import (
    merge_pressure_fields,
    merge_strain_vectors,
    merge_individual_states,
    merge_org_states,
    merge_hydraulic_states,
    merge_multi_agent_states,
    build_snapshot,
)

# A fixed timestamp — never the wall clock — so snapshot output is reproducible.
FIXED_TS = datetime(2026, 5, 29, 12, 0, 0)


# ------------------------------------------------------------
# PRESSURE — confidence-weighted average
# ------------------------------------------------------------

def test_merge_pressure_fields_weighted_average():
    fields = [
        PressureField(value=10.0, confidence=1.0, sources=["a"]),
        PressureField(value=20.0, confidence=3.0, sources=["b"]),
    ]
    out = merge_pressure_fields(fields)
    # (10*1 + 20*3) / (1+3) = 70/4 = 17.5
    assert out.value == 17.5
    assert out.confidence == 1.0  # min(1.0, total_weight/len) = min(1.0, 4/2)
    assert out.sources == ["a", "b"]
    # Deterministic: identical inputs -> identical output.
    assert merge_pressure_fields(fields) == out


def test_merge_pressure_fields_empty_and_zero_weight():
    assert merge_pressure_fields([]) == PressureField.zero()
    zeros = [PressureField(value=9.0, confidence=0.0, sources=["x"])]
    assert merge_pressure_fields(zeros) == PressureField.zero()


# ------------------------------------------------------------
# STRAIN — max-dominant (largest |magnitude|)
# ------------------------------------------------------------

def test_merge_strain_vectors_max_dominant():
    vectors = [
        StrainVector(magnitude=2.0, direction=0.1, source="x"),
        StrainVector(magnitude=-5.0, direction=0.9, source="y"),
        StrainVector(magnitude=3.0, direction=0.2, source="z"),
    ]
    out = merge_strain_vectors(vectors)
    # |-5.0| is the largest magnitude.
    assert out.magnitude == -5.0
    assert out.direction == 0.9
    assert out.source == "y"
    assert merge_strain_vectors(vectors) == out


def test_merge_strain_vectors_empty():
    assert merge_strain_vectors([]) == StrainVector.zero()


# ------------------------------------------------------------
# INDIVIDUAL — last-known (latest timestamp)
# ------------------------------------------------------------

def test_merge_individual_states_last_known():
    early = IndividualState(timestamp=datetime(2026, 1, 1), stability=0.2, load=0.9)
    mid = IndividualState(timestamp=datetime(2026, 3, 1), stability=0.5, load=0.5)
    late = IndividualState(timestamp=datetime(2026, 6, 1), stability=0.8, load=0.1)
    # Unsorted input — latest timestamp must win regardless of order.
    out = merge_individual_states([mid, late, early])
    assert out == late
    assert out.stability == 0.8


def test_merge_individual_states_empty():
    assert merge_individual_states([]) == IndividualState.zero()


# ------------------------------------------------------------
# ORG — coherence-weighted average
# ------------------------------------------------------------

def test_merge_org_states_coherence_weighted():
    states = [
        OrgState(stability=1.0, coherence=1.0, sources=["o1"]),
        OrgState(stability=0.0, coherence=1.0, sources=["o2"]),
    ]
    out = merge_org_states(states)
    # (1*1 + 0*1) / (1+1) = 0.5
    assert out.stability == 0.5
    assert out.coherence == 1.0  # min(1.0, 2/2)
    assert out.sources == ["o1", "o2"]
    assert merge_org_states(states) == out


def test_merge_org_states_empty_and_zero_coherence():
    assert merge_org_states([]) == OrgState.zero()
    zeros = [OrgState(stability=0.7, coherence=0.0, sources=["o"])]
    assert merge_org_states(zeros) == OrgState.zero()


# ------------------------------------------------------------
# HYDRAULIC — time-sorted (latest timestamp)
# ------------------------------------------------------------

def test_merge_hydraulic_states_time_sorted():
    a = HydraulicState(timestamp=datetime(2026, 1, 1), pressure=1.0, flow=1.0, resistance=1.0)
    b = HydraulicState(timestamp=datetime(2026, 9, 9), pressure=2.0, flow=2.0, resistance=2.0)
    out = merge_hydraulic_states([a, b])
    assert out == b
    assert merge_hydraulic_states([b, a]) == b  # order-independent


def test_merge_hydraulic_states_empty():
    assert merge_hydraulic_states([]) == HydraulicState.zero()


# ------------------------------------------------------------
# MULTI-AGENT — adjacency union (sorted, deterministic)
# ------------------------------------------------------------

def test_merge_multi_agent_states_adjacency_union():
    states = [
        MultiAgentState(graph={"a": ["b", "c"]}),
        MultiAgentState(graph={"a": ["c", "d"], "b": ["a"]}),
    ]
    out = merge_multi_agent_states(states)
    assert out.graph == {"a": ["b", "c", "d"], "b": ["a"]}


def test_merge_multi_agent_states_is_order_independent():
    s1 = MultiAgentState(graph={"a": ["c", "b"]})
    s2 = MultiAgentState(graph={"a": ["b"], "z": ["y", "x"]})
    forward = merge_multi_agent_states([s1, s2])
    reverse = merge_multi_agent_states([s2, s1])
    # Sorted union -> identical output regardless of input / neighbour order.
    assert forward == reverse
    assert forward.graph == {"a": ["b", "c"], "z": ["x", "y"]}


def test_merge_multi_agent_states_empty():
    assert merge_multi_agent_states([]) == MultiAgentState.zero()


# ------------------------------------------------------------
# SNAPSHOT BUILDER — deterministic, clock-free
# ------------------------------------------------------------

def _sample_inputs() -> dict:
    return {
        "pressure": [
            PressureField(value=10.0, confidence=1.0, sources=["p1"]),
            PressureField(value=20.0, confidence=3.0, sources=["p2"]),
        ],
        "strain": [StrainVector(magnitude=4.0, direction=0.3, source="s1")],
        "individual": [
            IndividualState(timestamp=datetime(2026, 2, 2), stability=0.6, load=0.4),
        ],
        "org": [OrgState(stability=0.9, coherence=2.0, sources=["o1"])],
        "hydraulic": [
            HydraulicState(timestamp=datetime(2026, 4, 4), pressure=1.5, flow=0.5, resistance=0.2),
        ],
        "multi": [MultiAgentState(graph={"a": ["b"]})],
    }


def test_build_snapshot_uses_provided_timestamp():
    snap = build_snapshot(_sample_inputs(), FIXED_TS)
    # The builder must use the argument verbatim — never the wall clock.
    assert snap.timestamp == FIXED_TS


def test_build_snapshot_is_deterministic():
    inputs = _sample_inputs()
    first = build_snapshot(inputs, FIXED_TS)
    second = build_snapshot(_sample_inputs(), FIXED_TS)
    # Same inputs + same timestamp -> identical output. (If the builder read
    # the clock, repeated calls would diverge on `timestamp`.)
    assert first == second


def test_build_snapshot_field_types_and_metadata():
    snap = build_snapshot(_sample_inputs(), FIXED_TS)
    assert isinstance(snap, UnifiedSnapshot)
    assert isinstance(snap.pressure, PressureField)
    assert isinstance(snap.strain, StrainVector)
    assert isinstance(snap.individual, IndividualState)
    assert isinstance(snap.org, OrgState)
    assert isinstance(snap.hydraulic, HydraulicState)
    assert isinstance(snap.multi, MultiAgentState)
    # Merged values flow through.
    assert snap.pressure.value == 17.5
    assert snap.metadata["pressure_sources"] == ["p1", "p2"]
    assert snap.metadata["org_sources"] == ["o1"]
    assert snap.metadata["degraded"] is False


def test_build_snapshot_empty_inputs_yield_zero_values():
    snap = build_snapshot({}, FIXED_TS)
    assert snap.timestamp == FIXED_TS
    assert snap.pressure == PressureField.zero()
    assert snap.strain == StrainVector.zero()
    assert snap.individual == IndividualState.zero()
    assert snap.org == OrgState.zero()
    assert snap.hydraulic == HydraulicState.zero()
    assert snap.multi == MultiAgentState.zero()
    assert snap.metadata["degraded"] is False
