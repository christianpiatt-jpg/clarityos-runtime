"""
language_schemas.py — ClarityOS Language Layer schemas.

The single source of truth for the data types used by:
    * primitive_selection_engine.py (the PSE)

The Language Layer is an EXPRESSION-ONLY layer. It selects HOW
ClarityOS speaks (tone / structure / length / metaphor frame), never
WHAT it decides. It introduces FOUR drift primitives — Motion,
Geometry, Hydronics, Analogy — each of which is a DERIVED view of the
10 base ClarityOS primitives (C, D, L, A, T, B, G, I, P, S).

BASE-PRIMITIVE DERIVATION (locked, test-enforced):

    Motion    ← D + T + B + P
    Geometry  ← G + D + I
    Hydronics ← L + D + B + P
    Analogy   ← P + S + I

No new base primitives are introduced. No architecture is changed.

INVARIANTS (also enforced by tests/test_language_layer.py):

    1. Every expression primitive maps to a non-empty subset of the
       10 base primitives.
    2. All schemas are frozen dataclasses.
    3. No I/O references inside any schema.
    4. The EnvelopeSnapshot type carries ONLY the four documented
       fields from Azimuth's EnvelopeState — never raw_text or
       envelope_id.

See SPEC_LANGUAGE_LAYER.md for the full specification.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

# Upstream types. We import only the read-only shapes we need.
from azimuth import (
    IntensityLevel,
    IntentionClass,
    PressureLevel,
    Valence,
)
from orchestrator_schemas import (
    DriftState,
    GeometryProfile,
    IdentityProfile,
    PropagationState,
)


# ===========================================================================
# Conversation mode — input dimension
# ===========================================================================
class ConversationMode(str, Enum):
    """The cognitive register of the current turn."""
    OPERATOR    = "operator"      # analytical / professional / executable
    EXPLORATORY = "exploratory"   # thinking aloud, mapping a space
    EMOTIONAL   = "emotional"     # under load, needs witness + relief
    STRUCTURAL  = "structural"    # diagnosing a system
    DECISION    = "decision"      # forward commitment


# ===========================================================================
# Expression primitives — the four drift primitives
# ===========================================================================
class ExpressionPrimitive(str, Enum):
    """The four expression modes. Each is a DERIVED view of the 10 base
    primitives. See EXPRESSION_PRIMITIVE_DERIVATION below."""
    MOTION    = "motion"
    GEOMETRY  = "geometry"
    HYDRONICS = "hydronics"
    ANALOGY   = "analogy"


# Locked mapping: expression primitive → tuple of base primitives.
# This is the structural contract that prevents the Language Layer
# from introducing a new base primitive. Tests assert each tuple is
# a non-empty subset of BASE_PRIMITIVES.
BASE_PRIMITIVES: tuple = ("C", "D", "L", "A", "T", "B", "G", "I", "P", "S")

EXPRESSION_PRIMITIVE_DERIVATION: dict = {
    ExpressionPrimitive.MOTION:    ("D", "T", "B", "P"),
    ExpressionPrimitive.GEOMETRY:  ("G", "D", "I"),
    ExpressionPrimitive.HYDRONICS: ("L", "D", "B", "P"),
    ExpressionPrimitive.ANALOGY:   ("P", "S", "I"),
}


# ===========================================================================
# Tone / structure / length — output dimensions
# ===========================================================================
class ToneProfile(str, Enum):
    """Tonal register the response should adopt."""
    STABLE    = "stable"      # quiet, grounded, non-escalating
    DIRECT    = "direct"      # clear, decisive, structural
    SOFTENED  = "softened"    # gentler edges, holding language
    EXPANSIVE = "expansive"   # thinking-aloud, branching


class StructureProfile(str, Enum):
    """Structural shape of the response."""
    HIGHLY_STRUCTURED = "highly_structured"  # numbered lists, tables, headings
    MODERATE          = "moderate"           # mix of prose + minimal structure
    MINIMAL           = "minimal"            # flowing prose


class LengthProfile(str, Enum):
    """Target length of the response."""
    SHORT  = "short"     # ≤ ~3 sentences
    MEDIUM = "medium"    # ~1–3 paragraphs
    LONG   = "long"      # 4+ paragraphs


# ===========================================================================
# EnvelopeSnapshot — minimal Azimuth-envelope view for the Language Layer
# ===========================================================================
@dataclass(frozen=True)
class EnvelopeSnapshot:
    """A narrowed view of azimuth.EnvelopeState carrying ONLY the four
    fields the Language Layer is permitted to read.

    PRIVACY: This type intentionally has NO raw_text and NO envelope_id.
    The Language Layer never sees the user's intimate content. It only
    reads the structural metadata derived by the Envelope + Transition
    layers.

    Construct via:
        snapshot = EnvelopeSnapshot(
            pressure_level=env.pressure_level,
            valence=env.valence,
            intensity=env.emotional_intensity,
            intention_class=transition_candidate.intention_class,
        )
    """
    pressure_level:  PressureLevel
    valence:         Valence
    intensity:       IntensityLevel
    intention_class: IntentionClass


# ===========================================================================
# LanguageContext — PSE input
# ===========================================================================
@dataclass(frozen=True)
class LanguageContext:
    """Pure input for the Primitive Selection Engine.

    INVARIANT: No I/O. No mutable references. Caller assembles this
    fully before calling select_expression_plan().
    """
    envelope:           EnvelopeSnapshot
    drift_state:        DriftState
    geometry_profile:   GeometryProfile
    identity_profile:   IdentityProfile
    conversation_mode:  ConversationMode
    # Optional fields with defaults — must come last in dataclass order.
    propagation_state:  Optional[PropagationState] = None
    last_primitive:     Optional[ExpressionPrimitive] = None


# ===========================================================================
# ExpressionPlan — PSE output
# ===========================================================================
@dataclass(frozen=True)
class ExpressionPlan:
    """The PSE's decision for one conversational turn.

    The plan is a PROPOSAL. Downstream (Azimuth reframer, surface
    rendering) consumes it; the user never sees raw plans — they see
    the resulting text shaped according to the plan.
    """
    primitive: ExpressionPrimitive
    tone:      ToneProfile
    structure: StructureProfile
    length:    LengthProfile
    rationale: str = ""


# ===========================================================================
# Module-level structural guards
# ===========================================================================
_BASE_PRIMITIVE_SET: frozenset = frozenset(BASE_PRIMITIVES)


def assert_derivation_contract() -> None:
    """Runtime guard — verify every expression primitive maps to a
    non-empty subset of the 10 base primitives.

    Called by the test suite and at module load (defense in depth).
    """
    for primitive, derived in EXPRESSION_PRIMITIVE_DERIVATION.items():
        assert isinstance(derived, tuple) and len(derived) > 0, (
            f"{primitive.value} has empty/invalid derivation"
        )
        non_base = set(derived) - _BASE_PRIMITIVE_SET
        assert not non_base, (
            f"{primitive.value} derivation references non-base primitives: {non_base}"
        )
    # All four expression primitives must be represented.
    missing = set(ExpressionPrimitive) - set(EXPRESSION_PRIMITIVE_DERIVATION)
    assert not missing, (
        f"EXPRESSION_PRIMITIVE_DERIVATION missing entries for: {missing}"
    )


# Run guard at module load — a structurally broken edit fails import.
assert_derivation_contract()
