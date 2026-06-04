"""Orientation-domain contracts for the Harmonizer.

Pure data definitions — no I/O, no clock access, no external dependencies.
Every type carries a deterministic ``zero()`` constructor returning a valid
zero-value instance. ``zero()`` never reads the wall clock: zero-valued
timestamps use the fixed ``datetime.min`` sentinel so the factory stays
referentially transparent.

These dataclasses are the *only* contract types the harmonizer imports;
the harmonizer introduces no other package dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# Deterministic sentinel for zero-valued timestamps. A class constant, not a
# clock read — keeps every ``zero()`` factory pure and reproducible.
_ZERO_TS: datetime = datetime.min


@dataclass
class PressureField:
    """A scalar pressure reading with a source-confidence weight.

    ``sources`` is a list so a merged field can carry the provenance of every
    contributing reading; a single raw reading carries a one-element list.
    """

    value: float
    confidence: float
    sources: list[str] = field(default_factory=list)

    @classmethod
    def zero(cls) -> "PressureField":
        return cls(value=0.0, confidence=0.0, sources=[])


@dataclass
class StrainVector:
    """A directed strain magnitude attributed to a single dominant source."""

    magnitude: float
    direction: float
    source: str = ""

    @classmethod
    def zero(cls) -> "StrainVector":
        return cls(magnitude=0.0, direction=0.0, source="")


@dataclass
class IndividualState:
    """Point-in-time individual operator state. ``timestamp`` orders the
    last-known-state merge."""

    timestamp: datetime
    stability: float
    load: float

    @classmethod
    def zero(cls) -> "IndividualState":
        return cls(timestamp=_ZERO_TS, stability=0.0, load=0.0)


@dataclass
class OrgState:
    """Organisation-level state with a coherence weight used by the
    coherence-weighted merge. ``sources`` carries contributing provenance."""

    stability: float
    coherence: float
    sources: list[str] = field(default_factory=list)

    @classmethod
    def zero(cls) -> "OrgState":
        return cls(stability=0.0, coherence=0.0, sources=[])


@dataclass
class HydraulicState:
    """Point-in-time hydraulic state. ``timestamp`` orders the time-sorted
    (latest-wins) merge."""

    timestamp: datetime
    pressure: float
    flow: float
    resistance: float

    @classmethod
    def zero(cls) -> "HydraulicState":
        return cls(timestamp=_ZERO_TS, pressure=0.0, flow=0.0, resistance=0.0)


@dataclass
class MultiAgentState:
    """Directed adjacency graph: agent -> list of neighbour agent ids."""

    graph: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def zero(cls) -> "MultiAgentState":
        return cls(graph={})


@dataclass
class UnifiedSnapshot:
    """The harmonized cross-domain snapshot. ``timestamp`` is supplied by the
    caller (never read from the clock) so a snapshot is fully reproducible
    from its inputs."""

    timestamp: datetime
    pressure: PressureField
    strain: StrainVector
    individual: IndividualState
    org: OrgState
    hydraulic: HydraulicState
    multi: MultiAgentState
    metadata: dict[str, Any] = field(default_factory=dict)
