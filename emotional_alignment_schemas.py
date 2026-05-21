"""
emotional_alignment_schemas.py — Emotional Reality Alignment (ERA) schemas.

Single source of truth for:
    * emotional_alignment_engine.py (the deterministic align_expression
      function + its build_reframe_plan / compute_alignment_score helpers)

CORE INVARIANT
--------------
    E = internal_relator
    Expression must match internal relational meaning so the user's
    emotional choices produce the experience they intend.

REUSED UPSTREAM TYPES
---------------------
    PressureLevel, IntensityLevel, Valence ← azimuth
    ExpressionPrimitive                     ← language_schemas

NEW BASE TYPES (minimal, per SPEC § 3.2)
----------------------------------------
    EmotionalSnapshot     — structural snapshot of emotional state
    EmotionalGeometry     — structural shape (curvature, torsion, shear, …)
    EmotionalIntention    — what the user is trying to do emotionally

ERA-SPECIFIC OUTPUT TYPES
-------------------------
    ReframeStep, ReframePlan, AlignedExpression
    + ReframeType, RegulationGoal, RelationalPosture, MeaningNeed enums

PRIVACY INVARIANTS (also enforced by tests/test_emotional_alignment.py):
    1. None of the ERA output types contain `text`, `raw`, `user`,
       `id`, `name`, `email`, `session` fields.
    2. All schemas are frozen dataclasses.
    3. No I/O references inside any schema.
    4. Module-load runtime guards run at import.

See SPEC_EMOTIONAL_REALITY_ALIGNMENT.md for the full specification.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Reused types — single source of truth lives in upstream modules.
from azimuth import IntensityLevel, PressureLevel, Valence
from language_schemas import ExpressionPrimitive


# ===========================================================================
# Enums for EmotionalIntention
# ===========================================================================
class RegulationGoal(str, Enum):
    """What the user is trying to do with their emotional state."""
    CONTAIN   = "contain"
    EXPRESS   = "express"
    TRANSFORM = "transform"


class RelationalPosture(str, Enum):
    """How the user is positioned relative to the other party / world."""
    CONNECT  = "connect"
    SEPARATE = "separate"
    DEFEND   = "defend"
    SUBMIT   = "submit"


class MeaningNeed(str, Enum):
    """What kind of meaning-work is needed (if any)."""
    CLARIFY  = "clarify"
    VALIDATE = "validate"
    REFRAME  = "reframe"
    NONE     = "none"


# ===========================================================================
# Enum for ReframeStep
# ===========================================================================
class ReframeType(str, Enum):
    """The canonical reframe categories ERA can emit.

    Each maps to a single concrete corrective move:

        LABEL    — global identity attack → behavior-bounded
        TEMPORAL — repeat pattern collapse → this-instance differentiation
        ROLE     — boundary distortion → role redefinition
        SCALE    — globalizing language → specific scope
        AGENCY   — submit / helplessness → choice restored
        MEANING  — torsion/shear at low pressure → coherent meaning
        NONE     — no reframe required
    """
    LABEL    = "label"
    TEMPORAL = "temporal"
    ROLE     = "role"
    SCALE    = "scale"
    AGENCY   = "agency"
    MEANING  = "meaning"
    NONE     = "none"


# ===========================================================================
# Minimal base types (per SPEC § 3.2)
# ===========================================================================
@dataclass(frozen=True)
class EmotionalSnapshot:
    """Minimal structural snapshot of the user's emotional state.

    Carries only structural metadata — NO raw text, NO identity.
    """
    pressure_level:  PressureLevel
    intensity:       IntensityLevel
    valence:         Valence
    temporal_linked: bool           # linked to a repeating pattern
    anchor_present:  bool           # specific memory/pattern anchor active


@dataclass(frozen=True)
class EmotionalGeometry:
    """Structural shape of the user's emotional state.

    Captures distortion patterns:
        curvature   — globalizing ("always", "never", "everything")
        torsion     — twisted between intent and outcome
        shear       — self-attack / identity collapse into behavior
        boundary    — boundary distortion (dominance / helplessness)
        stance_*    — vector of who is being blamed / hostile-to
        pressure_gradient — rate of change in pressure
    """
    curvature:         bool
    torsion:           bool
    shear:             bool
    boundary:          bool
    stance_self:       float   # [0, 1]; high = self-attacking
    stance_other:      float   # [0, 1]; high = other-attacking
    stance_world:      float   # [0, 1]; high = world-hostile
    pressure_gradient: float   # [0, 1]; rate of pressure change


@dataclass(frozen=True)
class EmotionalIntention:
    """What the user is trying to do emotionally.

    Minimal version per SPEC § 3.2.
    """
    target_state:       str
    regulatory_goal:    RegulationGoal
    relational_posture: RelationalPosture
    meaning_need:       MeaningNeed


# ===========================================================================
# ERA output types
# ===========================================================================
@dataclass(frozen=True)
class ReframeStep:
    """A single corrective move in a reframe plan.

    PRIVACY: `rationale` is a canonical, engine-generated string —
    NEVER user text. Tests assert this by injecting unique markers
    into upstream fields and verifying they don't appear in any
    output field.
    """
    reframe_type: ReframeType
    rationale:    str


@dataclass(frozen=True)
class ReframePlan:
    """Ordered set of reframe steps with predicted deltas.

    PRIVACY CONTRACT (structurally enforced):
        Fields are exactly: steps, primitive, expected_pressure_delta,
        expected_agency_delta. No `text`, `raw`, `user`, `id`, `name`,
        `email`, `session` fields.
    """
    steps:                   tuple                 # tuple[ReframeStep, ...]
    primitive:               ExpressionPrimitive
    expected_pressure_delta: int                    # ∈ {-1, 0, +1}
    expected_agency_delta:   int                    # ∈ {-1, 0, +1}


@dataclass(frozen=True)
class AlignedExpression:
    """The final ERA output — the plan, plus a score and two safety flags.

    PRIVACY CONTRACT (structurally enforced):
        No `text`, `raw`, `user`, `id`, `name`, `email`, `session`
        fields. Only the four documented fields below.
    """
    plan:                       ReframePlan
    alignment_score:            float      # ∈ [0.0, 1.0]
    internal_relator_preserved: bool
    safe_for_surface:           bool


# ===========================================================================
# Module-level privacy guards
# ===========================================================================
_FORBIDDEN_ERA_FIELDS: frozenset = frozenset({
    "text",
    "raw",
    "raw_text",
    "user",
    "user_id",
    "id",
    "name",
    "names",
    "email",
    "session",
    "session_id",
    "identity",
    "envelope_id",
    "author",
    "actor",
})

# Canonical ReframeType set — locked.
_CANONICAL_REFRAME_TYPES: frozenset = frozenset({
    ReframeType.LABEL,
    ReframeType.TEMPORAL,
    ReframeType.ROLE,
    ReframeType.SCALE,
    ReframeType.AGENCY,
    ReframeType.MEANING,
    ReframeType.NONE,
})

# Each ERA output type's canonical field set.
_CANONICAL_FIELDS = {
    "ReframeStep":       frozenset({"reframe_type", "rationale"}),
    "ReframePlan":       frozenset({
        "steps", "primitive",
        "expected_pressure_delta", "expected_agency_delta",
    }),
    "AlignedExpression": frozenset({
        "plan", "alignment_score",
        "internal_relator_preserved", "safe_for_surface",
    }),
}


def assert_era_privacy_contract() -> None:
    """Runtime guard — raises if any ERA output type has gained a
    forbidden field. Called by the test suite and at module load.
    """
    for cls in (ReframeStep, ReframePlan, AlignedExpression):
        actual = set(cls.__dataclass_fields__.keys())
        leaked = actual & _FORBIDDEN_ERA_FIELDS
        assert not leaked, (
            f"{cls.__name__} privacy contract violated — forbidden fields: {leaked}"
        )


def assert_era_field_sets_canonical() -> None:
    """Runtime guard — raises if any ERA output type's field set drifts
    from the canonical set."""
    for cls_name, expected_fields in _CANONICAL_FIELDS.items():
        cls = globals()[cls_name]
        actual = set(cls.__dataclass_fields__.keys())
        assert actual == expected_fields, (
            f"{cls_name} field set drift — expected {expected_fields}, "
            f"got {actual}"
        )


def assert_reframe_types_canonical() -> None:
    """Runtime guard — raises if ReframeType has gained or lost members."""
    actual = set(ReframeType)
    assert actual == _CANONICAL_REFRAME_TYPES, (
        f"ReframeType set drift — expected {_CANONICAL_REFRAME_TYPES}, got {actual}"
    )


# Run guards at module load — broken edits fail import.
assert_era_privacy_contract()
assert_era_field_sets_canonical()
assert_reframe_types_canonical()
