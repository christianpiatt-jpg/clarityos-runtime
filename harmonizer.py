"""Harmonizer — deterministic cross-domain merge of orientation contracts.

Every function in this module is PURE and DETERMINISTIC:
  * no I/O, no logging, no network
  * no randomness
  * no wall-clock access (``build_snapshot`` takes the timestamp as an
    argument; nothing here calls ``datetime.now()`` / ``utcnow()``)
  * imports only the orientation contracts (Step-1 module) + stdlib typing

Merge rules (one per domain):
  * pressure       — confidence-weighted average
  * strain         — max-dominant (largest |magnitude| wins)
  * individual     — last-known (latest timestamp wins)
  * org            — coherence-weighted average
  * hydraulic      — time-sorted (latest timestamp wins)
  * multi-agent    — adjacency union (deterministically sorted)

Determinism note: dict/set iteration order is not part of any merge result —
``merge_multi_agent_states`` sorts both agents and their neighbour lists, so
identical inputs always yield byte-identical output regardless of insertion
order.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from orientation_contracts import (
    PressureField,
    StrainVector,
    IndividualState,
    OrgState,
    HydraulicState,
    MultiAgentState,
    UnifiedSnapshot,
)


# ------------------------------------------------------------
# PRESSURE FIELD MERGE — confidence-weighted average
# ------------------------------------------------------------

def merge_pressure_fields(fields: list[PressureField]) -> PressureField:
    if not fields:
        return PressureField.zero()

    total_weight = sum(f.confidence for f in fields)
    if total_weight == 0:
        return PressureField.zero()

    weighted_value = sum(f.value * f.confidence for f in fields) / total_weight
    sources = [s for f in fields for s in f.sources]

    return PressureField(
        value=weighted_value,
        confidence=min(1.0, total_weight / len(fields)),
        sources=sources,
    )


# ------------------------------------------------------------
# STRAIN VECTOR MERGE — max-dominant
# ------------------------------------------------------------

def merge_strain_vectors(vectors: list[StrainVector]) -> StrainVector:
    if not vectors:
        return StrainVector.zero()

    # Largest absolute magnitude wins; ties resolve to the first such vector
    # in input order, so the result is deterministic for a given input list.
    dominant = max(vectors, key=lambda v: abs(v.magnitude))

    return StrainVector(
        magnitude=dominant.magnitude,
        direction=dominant.direction,
        source=dominant.source,
    )


# ------------------------------------------------------------
# INDIVIDUAL STATE MERGE — last-known (latest timestamp)
# ------------------------------------------------------------

def merge_individual_states(states: list[IndividualState]) -> IndividualState:
    if not states:
        return IndividualState.zero()

    return max(states, key=lambda s: s.timestamp)


# ------------------------------------------------------------
# ORG STATE MERGE — coherence-weighted average
# ------------------------------------------------------------

def merge_org_states(states: list[OrgState]) -> OrgState:
    if not states:
        return OrgState.zero()

    total_weight = sum(s.coherence for s in states)
    if total_weight == 0:
        return OrgState.zero()

    weighted_stability = sum(s.stability * s.coherence for s in states) / total_weight
    sources = [src for s in states for src in s.sources]

    return OrgState(
        stability=weighted_stability,
        coherence=min(1.0, total_weight / len(states)),
        sources=sources,
    )


# ------------------------------------------------------------
# HYDRAULIC STATE MERGE — time-sorted (latest timestamp)
# ------------------------------------------------------------

def merge_hydraulic_states(states: list[HydraulicState]) -> HydraulicState:
    if not states:
        return HydraulicState.zero()

    return max(states, key=lambda s: s.timestamp)


# ------------------------------------------------------------
# MULTI-AGENT STATE MERGE — adjacency union (sorted, deterministic)
# ------------------------------------------------------------

def merge_multi_agent_states(states: list[MultiAgentState]) -> MultiAgentState:
    if not states:
        return MultiAgentState.zero()

    merged: dict[str, set[str]] = {}
    for s in states:
        for agent, neighbors in s.graph.items():
            merged.setdefault(agent, set()).update(neighbors)

    # Sort agents and neighbour lists so the output is independent of set /
    # dict iteration order — required for full determinism.
    graph = {agent: sorted(merged[agent]) for agent in sorted(merged)}

    return MultiAgentState(graph=graph)


# ------------------------------------------------------------
# SNAPSHOT BUILDER — deterministic merge of all domains
# ------------------------------------------------------------

def build_snapshot(
    inputs: dict[str, Any],
    timestamp: datetime,
) -> UnifiedSnapshot:
    """Harmonize all six domains into a single snapshot.

    ``inputs`` keys (each maps to a list; missing keys default to empty):
        "pressure":   list[PressureField]
        "strain":     list[StrainVector]
        "individual": list[IndividualState]
        "org":        list[OrgState]
        "hydraulic":  list[HydraulicState]
        "multi":      list[MultiAgentState]

    ``timestamp`` is used exactly as provided — this function never reads the
    wall clock. Same inputs + same timestamp -> identical output.
    """
    pressure = merge_pressure_fields(inputs.get("pressure", []))
    strain = merge_strain_vectors(inputs.get("strain", []))
    individual = merge_individual_states(inputs.get("individual", []))
    org = merge_org_states(inputs.get("org", []))
    hydraulic = merge_hydraulic_states(inputs.get("hydraulic", []))
    multi = merge_multi_agent_states(inputs.get("multi", []))

    return UnifiedSnapshot(
        timestamp=timestamp,
        pressure=pressure,
        strain=strain,
        individual=individual,
        org=org,
        hydraulic=hydraulic,
        multi=multi,
        metadata={
            "pressure_sources": pressure.sources,
            "org_sources": org.sources,
            "degraded": False,
        },
    )
