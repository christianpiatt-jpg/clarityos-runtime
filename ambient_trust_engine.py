"""
ambient_trust_engine.py — Deterministic Ambient Trust engine.

Pure, deterministic, testable. No I/O. No randomness. No LLM. No
network.

Given a SessionContext, produces a TrustState plus point-in-time
checks (UnderstandingCheck, MomentumCheck) and a non-blocking
RepairDirective when repair is needed.

CORE INVARIANT
--------------
    Trust is structural, not motivational.

    The user's sense of being met is a function of:
        (a) comprehension keeping up with ability, and
        (b) momentum surviving the system's actions.
    The system never converts a trust gap into a hard stop.

PUBLIC API
----------
    assess_trust_state(ctx)                       -> TrustState
    verify_no_hard_stops(ctx)                     -> MomentumCheck
    verify_comprehension_leads_action(ctx)        -> UnderstandingCheck
    gentle_repair(trust, ctx)                     -> RepairDirective

See SPEC_AMBIENT_TRUST.md for the full specification.
"""
from __future__ import annotations

from ambient_trust_schemas import (
    CANONICAL_CONCEPT_IDS,
    GAP_TOLERANCE,
    HARD_STOP_PENALTY_CAP_LEVELS,
    MomentumCheck,
    RepairDirective,
    RepairKind,
    SCORE_PENALTY_PER_GAP_LEVEL,
    SCORE_PENALTY_PER_HARD_STOP,
    SCORE_PENALTY_UNACKNOWLEDGED,
    SessionContext,
    TrustState,
    UnderstandingCheck,
)


# ---------------------------------------------------------------------------
# Canonical rationale strings — never user text
# ---------------------------------------------------------------------------
# Each RepairKind carries a short, engine-generated rationale. These
# strings are the canonical set; tests assert no other rationale ever
# appears in the output.
_RATIONALE: dict = {
    RepairKind.NONE:
        "no repair required",
    RepairKind.RE_ANCHOR:
        "re_anchor: hard stop present — re-state the working context",
    RepairKind.SLOW_PACE:
        "slow_pace: comprehension gap exceeds tolerance — slow pacing",
    RepairKind.OFFER_CHOICE:
        "offer_choice: last action unacknowledged — restore agency",
    RepairKind.NARROW_SCOPE:
        "narrow_scope: comprehension at tolerance edge — narrow scope",
}


# Locked canonical concept-id set, reused for fast membership tests.
_CANONICAL_CONCEPT_ID_SET: frozenset = frozenset(CANONICAL_CONCEPT_IDS)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _validate_concept_exposures(ctx: SessionContext) -> None:
    """Raise ValueError if any ConceptExposure.concept_id is outside the
    canonical set. Invariant 11.

    Note: this validation reads concept_id only — counts are never
    branched on (invariant 3).
    """
    for exposure in ctx.concept_exposures:
        if exposure.concept_id not in _CANONICAL_CONCEPT_ID_SET:
            raise ValueError(
                f"non-canonical concept_id: {exposure.concept_id!r}"
            )


def _understanding_gap(ctx: SessionContext) -> int:
    """max(0, ability_level - comprehension_level)."""
    gap = ctx.ability_level - ctx.comprehension_level
    return gap if gap > 0 else 0


def _momentum_intact(ctx: SessionContext) -> bool:
    """Trust gaps never stop momentum — only actual hard stops do."""
    return ctx.hard_stop_count == 0


def _compute_trust_score(
    gap: int,
    hard_stop_count: int,
    last_action_acknowledged: bool,
) -> float:
    """Pure heuristic, baseline 1.0 with penalty subtractions per SPEC § 5.

    score = 1.0
        - SCORE_PENALTY_PER_GAP_LEVEL * gap
        - SCORE_PENALTY_UNACKNOWLEDGED   (if not acknowledged)
        - SCORE_PENALTY_PER_HARD_STOP * min(hard_stop_count, cap)

    Clipped to [0.0, 1.0]; rounded to 4 places for byte-equal determinism.
    """
    score = 1.0
    score -= SCORE_PENALTY_PER_GAP_LEVEL * gap
    if not last_action_acknowledged:
        score -= SCORE_PENALTY_UNACKNOWLEDGED
    capped_stops = (
        hard_stop_count
        if hard_stop_count <= HARD_STOP_PENALTY_CAP_LEVELS
        else HARD_STOP_PENALTY_CAP_LEVELS
    )
    score -= SCORE_PENALTY_PER_HARD_STOP * capped_stops

    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return round(score, 4)


def _repair_needed(
    gap: int,
    hard_stop_count: int,
    last_action_acknowledged: bool,
) -> bool:
    """True iff any of the trigger conditions hold (SPEC § 6.2).

    `gap >= GAP_TOLERANCE` covers both the edge (preventive NARROW_SCOPE)
    and over-edge (heavier SLOW_PACE) cases.
    """
    if hard_stop_count > 0:
        return True
    if not last_action_acknowledged:
        return True
    if gap >= GAP_TOLERANCE:
        return True
    return False


# ---------------------------------------------------------------------------
# Public API — assess_trust_state
# ---------------------------------------------------------------------------
def assess_trust_state(ctx: SessionContext) -> TrustState:
    """Pure function. Compute the current TrustState from SessionContext.

    Args:
        ctx: SessionContext — ability / comprehension ranks, concept
             exposure counts, hard-stop counter, last-action ack.

    Returns:
        TrustState with understanding_gap, momentum_intact, trust_score,
        repair_needed.

    Raises:
        ValueError if any ConceptExposure.concept_id is outside the
        canonical set (invariant 11).
    """
    _validate_concept_exposures(ctx)

    gap = _understanding_gap(ctx)
    momentum = _momentum_intact(ctx)
    score = _compute_trust_score(
        gap=gap,
        hard_stop_count=ctx.hard_stop_count,
        last_action_acknowledged=ctx.last_action_acknowledged,
    )
    repair = _repair_needed(
        gap=gap,
        hard_stop_count=ctx.hard_stop_count,
        last_action_acknowledged=ctx.last_action_acknowledged,
    )

    return TrustState(
        understanding_gap=gap,
        momentum_intact=momentum,
        trust_score=score,
        repair_needed=repair,
    )


# ---------------------------------------------------------------------------
# Public API — verify_no_hard_stops
# ---------------------------------------------------------------------------
def verify_no_hard_stops(ctx: SessionContext) -> MomentumCheck:
    """Pure function. Verify that the system has not introduced a hard
    stop.

    Returns:
        MomentumCheck with hard_stop_count, last_action_acknowledged,
        hard_stop_detected (True iff count > 0), and passes_invariant
        (True iff count == 0).
    """
    detected = ctx.hard_stop_count > 0
    return MomentumCheck(
        hard_stop_count=ctx.hard_stop_count,
        last_action_acknowledged=ctx.last_action_acknowledged,
        hard_stop_detected=detected,
        passes_invariant=not detected,
    )


# ---------------------------------------------------------------------------
# Public API — verify_comprehension_leads_action
# ---------------------------------------------------------------------------
def verify_comprehension_leads_action(
    ctx: SessionContext,
) -> UnderstandingCheck:
    """Pure function. Verify comprehension keeps up with ability.

    Invariant 2: ``comprehension_level >= ability_level - GAP_TOLERANCE``.
    With GAP_TOLERANCE = 1, ability may run at most one rank ahead of
    comprehension.

    Returns:
        UnderstandingCheck with ranks, gap, and passes_invariant.
    """
    gap = _understanding_gap(ctx)
    return UnderstandingCheck(
        ability_level=ctx.ability_level,
        comprehension_level=ctx.comprehension_level,
        gap=gap,
        passes_invariant=gap <= GAP_TOLERANCE,
    )


# ---------------------------------------------------------------------------
# Public API — gentle_repair
# ---------------------------------------------------------------------------
def gentle_repair(
    trust: TrustState,
    ctx: SessionContext,
) -> RepairDirective:
    """Pure function. Select a single non-blocking RepairDirective.

    Priority order (SPEC § 7):
        1. hard_stop_count > 0         → RE_ANCHOR
        2. understanding_gap > GAP_TOLERANCE → SLOW_PACE
        3. last_action_acknowledged is False → OFFER_CHOICE
        4. understanding_gap == GAP_TOLERANCE → NARROW_SCOPE
        5. otherwise                          → NONE

    `trust.repair_needed` is False short-circuits to NONE. Reading the
    fast-path off `trust` keeps callers from re-running the full
    assessment.

    Returns:
        RepairDirective with kind + canonical rationale.
    """
    if not trust.repair_needed:
        return RepairDirective(
            kind=RepairKind.NONE,
            rationale=_RATIONALE[RepairKind.NONE],
        )

    if ctx.hard_stop_count > 0:
        kind = RepairKind.RE_ANCHOR
    elif trust.understanding_gap > GAP_TOLERANCE:
        kind = RepairKind.SLOW_PACE
    elif not ctx.last_action_acknowledged:
        kind = RepairKind.OFFER_CHOICE
    elif trust.understanding_gap == GAP_TOLERANCE:
        kind = RepairKind.NARROW_SCOPE
    else:
        # Defensive fall-through: trust.repair_needed claimed True but
        # no trigger fires. Treat as NONE rather than fabricating a
        # directive. This branch is unreachable under the SPEC § 6.2
        # contract; the test suite asserts the unreachability.
        kind = RepairKind.NONE

    return RepairDirective(kind=kind, rationale=_RATIONALE[kind])
