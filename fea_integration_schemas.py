"""
fea_integration_schemas.py — FEA Integration Layer shared schemas.

Single source of truth for:
    * fea_integration_engine.py (the integrate_alignment function)

CORE INVARIANT
--------------
    FEA safety flags are authoritative.
    Ambient Trust is advisory.
    The integration layer never converts trust signals into safety
    overrides, never auto-sends, and never mutates upstream state.

REUSED UPSTREAM TYPES (read-only)
---------------------------------
    AlignedExpression    ← emotional_alignment_schemas
    SessionContext       ← ambient_trust_schemas
    TrustState           ← ambient_trust_schemas
    MomentumCheck        ← ambient_trust_schemas
    UnderstandingCheck   ← ambient_trust_schemas
    EnvelopeState        ← azimuth
    PropagationState     ← orchestrator_schemas

NEW TYPES (this module)
-----------------------
    SurfaceHaltLevel          — enum: NONE / SOFT / HARD
    SurfaceDirectiveType      — enum: PACE / DISCLOSURE / CHECKPOINT / PREVIEW
    SurfaceDirective          — frozen dataclass
    IntegratedAlignmentResult — frozen dataclass

PRIVACY INVARIANTS (also enforced by tests/test_fea_integration.py):
    1. None of the integration output types contain `text`, `raw`,
       `user`, `id`, `name`, `email`, `session`, `identity`,
       `envelope_id`, `author`, `actor`, `content`, `body`, `message`
       fields.
    2. SurfaceDirective.value MUST be a member of CANONICAL_DIRECTIVE_VALUES
       for its directive type.
    3. All schemas are frozen dataclasses.
    4. No I/O references inside any schema.
    5. Module-load runtime guards run at import.

See SPEC_FEA_INTEGRATION.md for the full specification.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# Upstream type — referenced in IntegratedAlignmentResult.aligned_expression.
# This import is read-only; we never mutate AlignedExpression.
from emotional_alignment_schemas import AlignedExpression


# ===========================================================================
# Enums
# ===========================================================================
class SurfaceHaltLevel(str, Enum):
    """Halt level the surface should observe.

    NONE — no halt; surface may proceed.
    SOFT — borderline; surface should slow and reconsider.
    HARD — FEA flagged the plan unsafe; surface must not auto-apply.
    """
    NONE = "no_halt"
    SOFT = "soft_halt"
    HARD = "hard_halt"


class SurfaceDirectiveType(str, Enum):
    """The canonical directive categories the surface can be told to apply.

    There is intentionally NO halting directive type — halt is encoded
    in `SurfaceHaltLevel`. Directives are structural pacing / disclosure
    / checkpoint / preview hints.
    """
    PACE       = "pace"
    DISCLOSURE = "disclosure"
    CHECKPOINT = "checkpoint"
    PREVIEW    = "preview"


# ===========================================================================
# Canonical directive value table — locked
# ===========================================================================
# SurfaceDirective.value MUST be a member of the canonical set for its
# directive type. Adding/removing a value is a deliberate spec change.
CANONICAL_DIRECTIVE_VALUES: dict = {
    SurfaceDirectiveType.PACE:       frozenset({"slow", "normal"}),
    SurfaceDirectiveType.DISCLOSURE: frozenset({"single_concept",
                                                "full_model_available"}),
    SurfaceDirectiveType.CHECKPOINT: frozenset({"offer_choice"}),
    SurfaceDirectiveType.PREVIEW:    frozenset({"preview_only"}),
}


# ===========================================================================
# Schemas — frozen dataclasses
# ===========================================================================
@dataclass(frozen=True)
class SurfaceDirective:
    """A single structural pacing / disclosure / checkpoint / preview hint.

    PRIVACY: `value` is restricted to the canonical set in
    CANONICAL_DIRECTIVE_VALUES so this type can NEVER carry free text.
    The engine validates `value` membership at construction time.
    """
    directive_type: SurfaceDirectiveType
    value:          str


@dataclass(frozen=True)
class IntegratedAlignmentResult:
    """Single advisory verdict the surface and orchestrator consume.

    PRIVACY CONTRACT (structurally enforced):
        Fields are exactly: aligned_expression, halt_level,
        trust_state_delta, momentum_preserved, surface_directives.
        No forbidden identity / text fields.

    `aligned_expression` is the *same object* as the input
    `AlignedExpression` (object-identity passthrough). The integration
    layer never mutates AlignedExpression.
    """
    aligned_expression: AlignedExpression
    halt_level:         SurfaceHaltLevel
    trust_state_delta:  float
    momentum_preserved: bool
    surface_directives: tuple


# ===========================================================================
# Module-level privacy + structural guards
# ===========================================================================
_FORBIDDEN_FIELDS: frozenset = frozenset({
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
    "content",
    "body",
    "message",
})


_CANONICAL_FIELDS = {
    "SurfaceDirective":          frozenset({"directive_type", "value"}),
    "IntegratedAlignmentResult": frozenset({
        "aligned_expression", "halt_level",
        "trust_state_delta", "momentum_preserved",
        "surface_directives",
    }),
}


_CANONICAL_HALT_LEVELS: frozenset = frozenset({
    SurfaceHaltLevel.NONE,
    SurfaceHaltLevel.SOFT,
    SurfaceHaltLevel.HARD,
})


_CANONICAL_DIRECTIVE_TYPES: frozenset = frozenset({
    SurfaceDirectiveType.PACE,
    SurfaceDirectiveType.DISCLOSURE,
    SurfaceDirectiveType.CHECKPOINT,
    SurfaceDirectiveType.PREVIEW,
})


def assert_fea_integration_privacy_contract() -> None:
    """Runtime guard — raises if any integration type has gained a
    forbidden field. Called by the test suite and at module load.
    """
    for cls in (SurfaceDirective, IntegratedAlignmentResult):
        actual = set(cls.__dataclass_fields__.keys())
        leaked = actual & _FORBIDDEN_FIELDS
        assert not leaked, (
            f"{cls.__name__} privacy contract violated — "
            f"forbidden fields: {leaked}"
        )


def assert_fea_integration_field_sets_canonical() -> None:
    """Runtime guard — raises if any integration type's field set drifts
    from the canonical set."""
    for cls_name, expected_fields in _CANONICAL_FIELDS.items():
        cls = globals()[cls_name]
        actual = set(cls.__dataclass_fields__.keys())
        assert actual == expected_fields, (
            f"{cls_name} field set drift — expected {expected_fields}, "
            f"got {actual}"
        )


def assert_surface_halt_levels_canonical() -> None:
    """Runtime guard — raises if SurfaceHaltLevel has gained or lost
    members."""
    actual = set(SurfaceHaltLevel)
    assert actual == _CANONICAL_HALT_LEVELS, (
        f"SurfaceHaltLevel set drift — expected {_CANONICAL_HALT_LEVELS}, "
        f"got {actual}"
    )


def assert_surface_directive_types_canonical() -> None:
    """Runtime guard — raises if SurfaceDirectiveType has gained or lost
    members."""
    actual = set(SurfaceDirectiveType)
    assert actual == _CANONICAL_DIRECTIVE_TYPES, (
        f"SurfaceDirectiveType set drift — expected {_CANONICAL_DIRECTIVE_TYPES}, "
        f"got {actual}"
    )


def assert_canonical_directive_values() -> None:
    """Runtime guard — raises if CANONICAL_DIRECTIVE_VALUES has drifted.
    Adding/removing a value is a deliberate spec change.
    """
    expected = {
        SurfaceDirectiveType.PACE:       frozenset({"slow", "normal"}),
        SurfaceDirectiveType.DISCLOSURE: frozenset({"single_concept",
                                                    "full_model_available"}),
        SurfaceDirectiveType.CHECKPOINT: frozenset({"offer_choice"}),
        SurfaceDirectiveType.PREVIEW:    frozenset({"preview_only"}),
    }
    assert CANONICAL_DIRECTIVE_VALUES == expected, (
        f"CANONICAL_DIRECTIVE_VALUES drift — expected {expected}, "
        f"got {CANONICAL_DIRECTIVE_VALUES}"
    )
    # Every directive type must have a non-empty canonical set.
    for dtype in SurfaceDirectiveType:
        assert dtype in CANONICAL_DIRECTIVE_VALUES, (
            f"directive type {dtype} missing from CANONICAL_DIRECTIVE_VALUES"
        )
        assert len(CANONICAL_DIRECTIVE_VALUES[dtype]) > 0, (
            f"directive type {dtype} has empty canonical value set"
        )


def is_canonical_directive_value(
    directive_type: SurfaceDirectiveType,
    value: str,
) -> bool:
    """Return True iff `value` is a member of the canonical set for
    `directive_type`.

    Helper for callers building SurfaceDirective tuples — the engine
    also validates values when it constructs them.
    """
    return value in CANONICAL_DIRECTIVE_VALUES.get(directive_type, frozenset())


# Run guards at module load — broken edits fail import.
assert_fea_integration_privacy_contract()
assert_fea_integration_field_sets_canonical()
assert_surface_halt_levels_canonical()
assert_surface_directive_types_canonical()
assert_canonical_directive_values()
