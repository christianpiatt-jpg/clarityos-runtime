"""
ambient_trust_schemas.py — Ambient Trust shared schemas + invariants.

Single source of truth for:
    * ambient_trust_engine.py (assess_trust_state / verify_no_hard_stops /
      verify_comprehension_leads_action / gentle_repair)

CORE INVARIANT
--------------
    Trust is structural, not motivational.

    The user's sense of being met is a function of:
        (a) comprehension keeping up with ability, and
        (b) momentum surviving the system's actions.
    The system never converts a trust gap into a hard stop.

CROSS-CUTTING TYPE
------------------
    SessionContext is the canonical "interaction context" type that
    downstream integration layers (FEA Integration, surface pacing,
    Orchestrator post-step hooks) consume. Keep it minimal and
    structural — adding fields here is a deliberate spec change.

PRIVACY INVARIANTS (also enforced by tests/test_ambient_trust.py):
    1. None of the Ambient Trust types contain `text`, `raw`, `user`,
       `id`, `name`, `email`, `session`, `identity`, `envelope_id`,
       `author`, `actor`, `content`, `body`, `message` fields.
    2. ConceptExposure.concept_id is restricted to CANONICAL_CONCEPT_IDS.
    3. All schemas are frozen dataclasses.
    4. No I/O references inside any schema.
    5. Module-load runtime guards run at import.

See SPEC_AMBIENT_TRUST.md for the full specification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ===========================================================================
# Locked constants — change here affects deterministic behavior
# ===========================================================================
MAX_LEVEL: int = 3
GAP_TOLERANCE: int = 1
SCORE_PENALTY_PER_GAP_LEVEL: float = 0.2
SCORE_PENALTY_PER_HARD_STOP: float = 0.1
SCORE_PENALTY_UNACKNOWLEDGED: float = 0.2
HARD_STOP_PENALTY_CAP_LEVELS: int = 2


# ===========================================================================
# Canonical concept identifier set
# ===========================================================================
# ConceptExposure.concept_id MUST be a member of this tuple. The runtime
# guard at module load asserts the set has not drifted. Adding a concept
# is a deliberate spec change.
CANONICAL_CONCEPT_IDS: tuple = (
    "envelope",
    "pressure",
    "geometry",
    "intention",
    "expression",
    "alignment",
    "halt_state",
    "trust",
    "momentum",
    "agency",
)


# ===========================================================================
# Enum — RepairKind
# ===========================================================================
class RepairKind(str, Enum):
    """The canonical repair directives Ambient Trust can emit.

    Each maps to a single non-blocking corrective move:

        NONE          — no repair required
        RE_ANCHOR     — re-state the working context (used after a hard stop)
        SLOW_PACE     — pace is too fast for current comprehension
        OFFER_CHOICE  — agency lost; restore choice
        NARROW_SCOPE  — zoom into a smaller piece

    There is intentionally NO halting / blocking member. Invariant 10:
    gentle_repair never emits a halt-like directive.
    """
    NONE         = "none"
    RE_ANCHOR    = "re_anchor"
    SLOW_PACE    = "slow_pace"
    OFFER_CHOICE = "offer_choice"
    NARROW_SCOPE = "narrow_scope"


# ===========================================================================
# Inputs
# ===========================================================================
@dataclass(frozen=True)
class ConceptExposure:
    """A counter for how many times the user has been exposed to a
    canonical concept.

    PRIVACY: concept_id is restricted to CANONICAL_CONCEPT_IDS so this
    type can NEVER carry free text. The runtime guard
    `assert_canonical_concept_ids` enforces the set.
    """
    concept_id: str
    count:      int


@dataclass(frozen=True)
class SessionContext:
    """The canonical 'interaction context' type for Ambient Trust and
    downstream integration layers.

    PRIVACY CONTRACT (structurally enforced):
        Fields are exactly: ability_level, comprehension_level,
        concept_exposures, hard_stop_count, last_action_acknowledged.
        No `text`, `raw`, `user`, `id`, `name`, `email`, `session`,
        `identity`, `envelope_id`, `author`, `actor`, `content`,
        `body`, `message` fields.
    """
    ability_level:            int
    comprehension_level:      int
    concept_exposures:        tuple                            # tuple[ConceptExposure, ...]
    hard_stop_count:          int  = 0
    last_action_acknowledged: bool = True


# ===========================================================================
# Outputs
# ===========================================================================
@dataclass(frozen=True)
class TrustState:
    """Current trust posture — pure function of SessionContext.

    PRIVACY CONTRACT (structurally enforced):
        Fields are exactly: understanding_gap, momentum_intact,
        trust_score, repair_needed. No forbidden fields.
    """
    understanding_gap: int     # max(0, ability_level - comprehension_level)
    momentum_intact:   bool    # True iff hard_stop_count == 0
    trust_score:       float   # ∈ [0.0, 1.0]
    repair_needed:     bool


@dataclass(frozen=True)
class UnderstandingCheck:
    """Point-in-time verification of comprehension vs ability.

    Invariant 2: comprehension_level >= ability_level - GAP_TOLERANCE.
    """
    ability_level:       int
    comprehension_level: int
    gap:                 int
    passes_invariant:    bool


@dataclass(frozen=True)
class MomentumCheck:
    """Point-in-time verification that the system has not introduced a
    hard stop.

    Invariant 1: trust gaps never stop momentum — only actual hard stops
    do. `passes_invariant` is True iff `hard_stop_count == 0`.
    """
    hard_stop_count:          int
    last_action_acknowledged: bool
    hard_stop_detected:       bool
    passes_invariant:         bool


@dataclass(frozen=True)
class RepairDirective:
    """A single, non-blocking corrective signal the surface can read.

    PRIVACY: `rationale` is canonical, engine-generated — NEVER user
    text. Tests assert this by injecting unique markers into upstream
    fields and verifying they don't appear in any output field.
    """
    kind:      RepairKind
    rationale: str


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


# Each Ambient Trust type's canonical field set. Drift = test failure.
_CANONICAL_FIELDS = {
    "ConceptExposure":     frozenset({"concept_id", "count"}),
    "SessionContext":      frozenset({
        "ability_level", "comprehension_level", "concept_exposures",
        "hard_stop_count", "last_action_acknowledged",
    }),
    "TrustState":          frozenset({
        "understanding_gap", "momentum_intact",
        "trust_score", "repair_needed",
    }),
    "UnderstandingCheck":  frozenset({
        "ability_level", "comprehension_level",
        "gap", "passes_invariant",
    }),
    "MomentumCheck":       frozenset({
        "hard_stop_count", "last_action_acknowledged",
        "hard_stop_detected", "passes_invariant",
    }),
    "RepairDirective":     frozenset({"kind", "rationale"}),
}


# Canonical RepairKind set — locked.
_CANONICAL_REPAIR_KINDS: frozenset = frozenset({
    RepairKind.NONE,
    RepairKind.RE_ANCHOR,
    RepairKind.SLOW_PACE,
    RepairKind.OFFER_CHOICE,
    RepairKind.NARROW_SCOPE,
})


_CANONICAL_CONCEPT_ID_SET: frozenset = frozenset(CANONICAL_CONCEPT_IDS)


def assert_ambient_trust_privacy_contract() -> None:
    """Runtime guard — raises if any Ambient Trust type has gained a
    forbidden field. Called by the test suite and at module load.
    """
    for cls in (
        ConceptExposure,
        SessionContext,
        TrustState,
        UnderstandingCheck,
        MomentumCheck,
        RepairDirective,
    ):
        actual = set(cls.__dataclass_fields__.keys())
        leaked = actual & _FORBIDDEN_FIELDS
        assert not leaked, (
            f"{cls.__name__} privacy contract violated — forbidden fields: {leaked}"
        )


def assert_ambient_trust_field_sets_canonical() -> None:
    """Runtime guard — raises if any Ambient Trust type's field set
    drifts from the canonical set."""
    for cls_name, expected_fields in _CANONICAL_FIELDS.items():
        cls = globals()[cls_name]
        actual = set(cls.__dataclass_fields__.keys())
        assert actual == expected_fields, (
            f"{cls_name} field set drift — expected {expected_fields}, "
            f"got {actual}"
        )


def assert_repair_kinds_canonical() -> None:
    """Runtime guard — raises if RepairKind has gained or lost members."""
    actual = set(RepairKind)
    assert actual == _CANONICAL_REPAIR_KINDS, (
        f"RepairKind set drift — expected {_CANONICAL_REPAIR_KINDS}, "
        f"got {actual}"
    )


def assert_canonical_concept_ids() -> None:
    """Runtime guard — raises if the canonical concept-id set has drifted.
    Adding/removing a concept id is a spec change."""
    # Tuple identity is the wire-format contract — preserve order + content.
    expected = (
        "envelope", "pressure", "geometry", "intention",
        "expression", "alignment", "halt_state",
        "trust", "momentum", "agency",
    )
    assert CANONICAL_CONCEPT_IDS == expected, (
        f"CANONICAL_CONCEPT_IDS drift — expected {expected}, "
        f"got {CANONICAL_CONCEPT_IDS}"
    )


def is_canonical_concept_id(concept_id: str) -> bool:
    """Return True iff `concept_id` is a member of CANONICAL_CONCEPT_IDS.

    Helper for callers building ConceptExposure tuples — the engine
    also validates exposures at the top of assess_trust_state.
    """
    return concept_id in _CANONICAL_CONCEPT_ID_SET


# Run guards at module load — broken edits fail import.
assert_ambient_trust_privacy_contract()
assert_ambient_trust_field_sets_canonical()
assert_repair_kinds_canonical()
assert_canonical_concept_ids()
