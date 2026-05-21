"""
feedback_schemas.py — Feedback Ingestion System (FIS) schemas.

Single source of truth for:
    * ingestion_engine.py  (the deterministic extract_pattern function)

The FIS converts founder feedback into **constitutional structural
patterns** — never storing raw text and never storing identity. The
output `FeedbackPattern` is structurally guaranteed (test-enforced) to
omit every field that could carry the user's words or who they are.

REUSED TYPES (no new copies — same primitives across ClarityOS):

    PressureLevel       ← azimuth
    ConversationMode    ← language_schemas
    ExpressionPrimitive ← language_schemas (aliased as PrimitiveType)

PRIVACY INVARIANTS (also enforced by tests/test_feedback_ingestion.py):

    1. FeedbackPattern.__dataclass_fields__ MUST NOT contain:
           text, raw_text, user_id, actor, session_id, identity,
           envelope_id, name, names
    2. All schemas are frozen dataclasses.
    3. No I/O references inside any schema.

See SPEC_FEEDBACK_INGESTION.md for the full specification.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

# Reused types — single source of truth lives in upstream modules.
from azimuth import PressureLevel
from language_schemas import ConversationMode, ExpressionPrimitive

# Alias for naming parity with the FIS spec.
# The PrimitiveType type IS ExpressionPrimitive; we expose both names.
PrimitiveType = ExpressionPrimitive


# ===========================================================================
# Enums — canonical FIS values
# ===========================================================================
class SignalType(str, Enum):
    """Lexical sentiment classification of the submission text."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL  = "neutral"


class PatternType(str, Enum):
    """Canonical pattern categories the engine emits."""
    TONE      = "tone"
    DRIFT     = "drift"
    PRESSURE  = "pressure"
    ALIGNMENT = "alignment"
    BOUNDARY  = "boundary"
    USE_CASE  = "use_case"


# ===========================================================================
# Input — FeedbackSubmission
# ===========================================================================
@dataclass(frozen=True)
class FeedbackSubmission:
    """The transient input to extract_pattern.

    NOTE: this dataclass carries the user's text BY DESIGN — it is the
    input boundary. The text is read ONCE by the engine, transformed
    lexically, and discarded. The engine NEVER returns text in its
    output (see FeedbackPattern privacy contract).

    Caller responsibility: do not persist this object. Pass it through
    extract_pattern() and discard.
    """
    text:           str
    mode:           ConversationMode
    pressure_level: PressureLevel
    primitive_used: ExpressionPrimitive
    timestamp:      datetime


# ===========================================================================
# Output — FeedbackPattern (pattern-only storage)
# ===========================================================================
@dataclass(frozen=True)
class FeedbackPattern:
    """The canonical, identity-free, text-free pattern the engine emits.

    PRIVACY CONTRACT (structurally enforced, test-asserted):
        __dataclass_fields__ contains EXACTLY these six fields:
            pattern_type, context, pressure_level, signal,
            primitive_involved, suggested_adjustment.
        Any future PR adding text / user_id / identity / envelope_id /
        name fails the test suite at import time.
    """
    pattern_type:         PatternType
    context:              ConversationMode
    pressure_level:       PressureLevel
    signal:               SignalType
    primitive_involved:   ExpressionPrimitive
    suggested_adjustment: str


# ===========================================================================
# ExtractionContext — optional whiplash-prevention hint
# ===========================================================================
@dataclass(frozen=True)
class ExtractionContext:
    """Optional hint passed to extract_pattern to prevent whiplash.

    If None (the default), the engine applies the straight rule chain.
    If provided with last_pattern_type, the engine preserves continuity
    when mode + pressure are unchanged (per SPEC § 5 whiplash rules).
    """
    last_pattern_type: Optional[PatternType]      = None
    last_pressure:     Optional[PressureLevel]    = None
    last_mode:         Optional[ConversationMode] = None


# ===========================================================================
# Module-level structural privacy guards
# ===========================================================================
# Field names that MUST NOT appear in FeedbackPattern. The privacy
# contract is enforced both at module load and by the test suite.
_FORBIDDEN_PATTERN_FIELDS: frozenset = frozenset({
    "text",
    "raw_text",
    "user_id",
    "actor",
    "session_id",
    "identity",
    "envelope_id",
    "name",
    "names",
    "user",
    "author",
})


def assert_pattern_privacy_contract() -> None:
    """Runtime guard — raises AssertionError if FeedbackPattern has
    grown a forbidden field. Called by the test suite and at module
    load (defense in depth).
    """
    actual = set(FeedbackPattern.__dataclass_fields__.keys())
    leaked = actual & _FORBIDDEN_PATTERN_FIELDS
    assert not leaked, (
        f"FeedbackPattern privacy contract violated — forbidden fields: {leaked}"
    )


# The full canonical FeedbackPattern field set, locked.
_CANONICAL_PATTERN_FIELDS: frozenset = frozenset({
    "pattern_type",
    "context",
    "pressure_level",
    "signal",
    "primitive_involved",
    "suggested_adjustment",
})


def assert_pattern_field_set_canonical() -> None:
    """Runtime guard — raises if FeedbackPattern has more or fewer than
    the canonical 6 fields. Catches accidental field additions even when
    they don't match the forbidden list."""
    actual = set(FeedbackPattern.__dataclass_fields__.keys())
    assert actual == _CANONICAL_PATTERN_FIELDS, (
        f"FeedbackPattern field set drift — expected {_CANONICAL_PATTERN_FIELDS}, "
        f"got {actual}"
    )


# Run guards at module load — broken edits fail import.
assert_pattern_privacy_contract()
assert_pattern_field_set_canonical()
