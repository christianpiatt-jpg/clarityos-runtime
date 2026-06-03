"""
compass_elins_bridge.py — bidirectional mapping between the ELINS field model
and the Compass operator model.

ELINS describes the *field* (global tension, drift, narrative opacity, operator
alignment, sector multipliers, operator exposures). The Compass describes the
*operator's posture* on six axes (pressure, timing, visibility, position,
leverage, vulnerability). This module is the deterministic, pure translation
layer between the two:

    ELINS field state              --ingest_elins_state-->   CompassState
    CompassState + Compass verdict --export_operator_state--> OperatorVector

Everything here is pure and deterministic: the same input always yields the
same output — no I/O, no clocks, no randomness. That keeps the bridge testable
and safe to call from any layer (kernel, operator console, scheduler).
"""
from __future__ import annotations

from dataclasses import dataclass

# Count at which a list-of-signals axis (sector multipliers / operator
# exposures) saturates to a full 1.0 on its Compass axis. Module-level and
# documented so the mapping is auditable and the tests can mirror it instead
# of hard-coding a magic number.
LEVERAGE_SATURATION: float = 5.0
VULNERABILITY_SATURATION: float = 5.0


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------
@dataclass
class CompassState:
    """The operator's posture on the six Compass axes.

    The ingest mapping guarantees every axis lands in [0.0, 1.0];
    hand-constructed states are not range-enforced (callers may build
    extreme states deliberately — see coupling clamping)."""

    pressure: float
    timing: float
    visibility: float
    position: float
    leverage: float
    vulnerability: float


@dataclass
class OperatorVector:
    """The operator state ELINS consumes back: the Compass net/risk verdict
    plus the four field-relevant axes ELINS re-ingests (timing and position
    are Compass-internal and deliberately not exported)."""

    operator_net: float
    operator_risk: str
    pressure: float
    visibility: float
    leverage: float
    vulnerability: float


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------
def scale(value: float) -> float:
    """Clamp an axis signal into the canonical [0.0, 1.0] range.

    Negative, non-finite (NaN), and non-numeric inputs saturate to 0.0;
    values above 1.0 saturate to 1.0. Pure and total — never raises."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v != v:  # NaN
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def derive_unknowns(opacity: float) -> float:
    """Fraction of the field that is opaque / unknown, in [0.0, 1.0].

    Narrative opacity maps directly to unknown mass: higher opacity means more
    of the field is hidden. Visibility is its complement (1 - unknowns)."""
    return scale(opacity)


def _clamp(value: float, lo: float, hi: float) -> float:
    """Clamp ``value`` into the inclusive [lo, hi] range."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


# ---------------------------------------------------------------------------
# Bridge
# ---------------------------------------------------------------------------
class CompassELINSBridge:
    """Deterministic, stateless translator between ELINS and the Compass."""

    def ingest_elins_state(self, elins_state: dict) -> CompassState:
        """
        Map ELINS field metrics -> Compass axes.

        Required ELINS fields:
          global_tension: float
          drift_windows: list[{start, end, magnitude}]
          narrative_opacity: float
          operator_alignment_score: float
          sector_multipliers: list[str]
          operator_exposures: list[str]

        Missing fields degrade to neutral (0.0 / empty) rather than raising, so
        a partial field state still produces a well-formed CompassState.
        """
        global_tension = elins_state.get("global_tension", 0.0)
        drift_windows = elins_state.get("drift_windows") or []
        narrative_opacity = elins_state.get("narrative_opacity", 0.0)
        operator_alignment_score = elins_state.get("operator_alignment_score", 0.0)
        sector_multipliers = elins_state.get("sector_multipliers") or []
        operator_exposures = elins_state.get("operator_exposures") or []

        # pressure   — global field tension bears directly on the operator.
        pressure = scale(global_tension)

        # timing     — the strongest drift window sets the clock; no drift
        #              windows means no time pressure.
        magnitudes = [
            scale(w.get("magnitude", 0.0))
            for w in drift_windows
            if isinstance(w, dict)
        ]
        timing = max(magnitudes) if magnitudes else 0.0

        # visibility — the complement of narrative opacity (unknown mass).
        visibility = scale(1.0 - derive_unknowns(narrative_opacity))

        # position   — how well the operator is aligned with the field.
        position = scale(operator_alignment_score)

        # leverage   — count of sector multipliers, saturating at the cap.
        leverage = scale(len(sector_multipliers) / LEVERAGE_SATURATION)

        # vulnerability — count of operator exposures, saturating at the cap.
        vulnerability = scale(len(operator_exposures) / VULNERABILITY_SATURATION)

        return CompassState(
            pressure=pressure,
            timing=timing,
            visibility=visibility,
            position=position,
            leverage=leverage,
            vulnerability=vulnerability,
        )

    def export_operator_state(
        self, compass_state: CompassState, analysis: dict
    ) -> OperatorVector:
        """
        Map Compass axes + Compass analysis -> operator vector for ELINS.

        ``analysis`` contains:
          net_score: float
          risk_level: str

        The four field-relevant axes pass through unchanged; the net/risk
        verdict comes from the Compass analysis. Missing analysis keys degrade
        to a neutral net (0.0) and an "unknown" risk label.
        """
        return OperatorVector(
            operator_net=float(analysis.get("net_score", 0.0)),
            operator_risk=str(analysis.get("risk_level", "unknown")),
            pressure=compass_state.pressure,
            visibility=compass_state.visibility,
            leverage=compass_state.leverage,
            vulnerability=compass_state.vulnerability,
        )

    def compute_operator_coupling(self, compass_state: CompassState) -> float:
        """
        coupling = (visibility + leverage) / (pressure + vulnerability + 1)
        Clamped to [0.1, 2.0].

        High when the operator can see and act (visibility + leverage) while the
        field isn't bearing down (low pressure + vulnerability); low otherwise.
        The +1 keeps the denominator well-conditioned even at zero load.
        """
        numerator = compass_state.visibility + compass_state.leverage
        denominator = compass_state.pressure + compass_state.vulnerability + 1.0
        return _clamp(numerator / denominator, 0.1, 2.0)
