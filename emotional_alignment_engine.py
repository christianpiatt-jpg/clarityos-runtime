"""
emotional_alignment_engine.py — Deterministic Emotional Reality Alignment.

Pure, deterministic, testable. No I/O. No randomness. No LLM. No
network.

Given EmotionalSnapshot + EmotionalGeometry + EmotionalIntention +
ExpressionPrimitive, produces a ReframePlan and AlignedExpression
that preserve internal relational meaning while reducing distortion
(shame, globalizing, helplessness).

CORE INVARIANT
--------------
    E = internal_relator
    Expression must match internal relational meaning so the user's
    emotional choices produce the experience they intend, not
    anchor-hijacked experience.

SELECTION DISCIPLINE
--------------------
Under HIGH/CRITICAL pressure: only AGENCY and SCALE reframes allowed
(minimum-intervention principle). Under LOW/MEDIUM pressure: full
reframe palette.

Reframes never increase pressure. Reframes never attack identity.
Reframes never weaken constitutional constraints.

PUBLIC API
----------
    build_reframe_plan(snapshot, geometry, intention, primitive) -> ReframePlan
    compute_alignment_score(snapshot, geometry, intention, plan) -> float
    align_expression(snapshot, geometry, intention, primitive)   -> AlignedExpression

See SPEC_EMOTIONAL_REALITY_ALIGNMENT.md for the full specification.
"""
from __future__ import annotations

from emotional_alignment_schemas import (
    AlignedExpression,
    EmotionalGeometry,
    EmotionalIntention,
    EmotionalSnapshot,
    ReframePlan,
    ReframeStep,
    ReframeType,
    RelationalPosture,
)
from azimuth import PressureLevel
from language_schemas import ExpressionPrimitive


# ---------------------------------------------------------------------------
# Locked thresholds — change here affects deterministic behavior
# ---------------------------------------------------------------------------

# Stance values at or above this threshold count as "high" for rule firing.
_STANCE_HIGH_THRESHOLD: float = 0.7

# Pressure levels that trigger the minimum-intervention path.
_HIGH_PRESSURE: frozenset = frozenset({
    PressureLevel.HIGH, PressureLevel.CRITICAL,
})


# ---------------------------------------------------------------------------
# Canonical rationale strings — never user text
# ---------------------------------------------------------------------------
# Each ReframeStep carries a short, engine-generated rationale. These
# strings are the canonical set; tests assert no other rationale ever
# appears in the output.
_RATIONALE: dict = {
    ReframeType.LABEL:
        "label: separate identity from behavior (shear / self-attack present)",
    ReframeType.TEMPORAL:
        "temporal: distinguish this instance from the repeat pattern",
    ReframeType.ROLE:
        "role: boundary distortion — redefine relational role",
    ReframeType.SCALE:
        "scale: localize globalizing language to specific scope",
    ReframeType.AGENCY:
        "agency: restore choice (submit posture or world-hostile stance)",
    ReframeType.MEANING:
        "meaning: address torsion / shear in low-pressure window",
    ReframeType.NONE:
        "no reframe required",
}


# ---------------------------------------------------------------------------
# Helper predicates
# ---------------------------------------------------------------------------
def _is_high_pressure(snapshot: EmotionalSnapshot) -> bool:
    return snapshot.pressure_level in _HIGH_PRESSURE


def _shear_or_self_attack(geometry: EmotionalGeometry) -> bool:
    return geometry.shear or geometry.stance_self >= _STANCE_HIGH_THRESHOLD


def _boundary_or_other_attack(geometry: EmotionalGeometry) -> bool:
    return geometry.boundary or geometry.stance_other >= _STANCE_HIGH_THRESHOLD


def _world_hostile(geometry: EmotionalGeometry) -> bool:
    return geometry.stance_world >= _STANCE_HIGH_THRESHOLD


def _is_submit(intention: EmotionalIntention) -> bool:
    return intention.relational_posture == RelationalPosture.SUBMIT


# ---------------------------------------------------------------------------
# Step builder
# ---------------------------------------------------------------------------
def _step(reframe_type: ReframeType) -> ReframeStep:
    """Build a ReframeStep with the canonical rationale for the type."""
    return ReframeStep(
        reframe_type=reframe_type,
        rationale=_RATIONALE[reframe_type],
    )


def _build_steps_high_pressure(
    snapshot: EmotionalSnapshot,
    geometry: EmotionalGeometry,
    intention: EmotionalIntention,
) -> list:
    """Under HIGH/CRITICAL: only AGENCY and SCALE allowed."""
    steps: list = []
    if geometry.curvature:
        steps.append(_step(ReframeType.SCALE))
    if _is_submit(intention) or _world_hostile(geometry):
        steps.append(_step(ReframeType.AGENCY))
    return steps


def _build_steps_low_medium_pressure(
    snapshot: EmotionalSnapshot,
    geometry: EmotionalGeometry,
    intention: EmotionalIntention,
) -> list:
    """Under LOW/MEDIUM: full palette available. Steps added in priority order."""
    steps: list = []

    # Rule 2 — temporal anchor
    if snapshot.temporal_linked and snapshot.anchor_present:
        steps.append(_step(ReframeType.TEMPORAL))

    # Rule 3 — shear / self-attack
    if _shear_or_self_attack(geometry):
        steps.append(_step(ReframeType.LABEL))

    # Rule 4 — boundary distortion (with SUBMIT producing both ROLE + AGENCY)
    boundary_distortion = _boundary_or_other_attack(geometry)
    submit_posture = _is_submit(intention)
    if boundary_distortion or submit_posture:
        steps.append(_step(ReframeType.ROLE))
        if submit_posture:
            steps.append(_step(ReframeType.AGENCY))

    # Rule 5 — globalizing
    if geometry.curvature:
        steps.append(_step(ReframeType.SCALE))

    # Rule 6 — torsion / shear → MEANING (only at low/medium pressure)
    if geometry.torsion or geometry.shear:
        steps.append(_step(ReframeType.MEANING))

    return steps


def _compute_deltas(
    step_types: frozenset,
    pressure_level: PressureLevel,
) -> tuple:
    """Compute (expected_pressure_delta, expected_agency_delta).

    Per SPEC § 5.3:
        SCALE or LABEL  →  pressure_delta = -1
        AGENCY or ROLE  →  agency_delta = +1
        else            →  0

    Under HIGH/CRITICAL, pressure_delta is clamped to ≤ 0 (invariant 5).
    """
    pressure_delta = 0
    if ReframeType.SCALE in step_types or ReframeType.LABEL in step_types:
        pressure_delta = -1

    agency_delta = 0
    if ReframeType.AGENCY in step_types or ReframeType.ROLE in step_types:
        agency_delta = 1

    # Hard cap under HIGH/CRITICAL — never increase pressure.
    if pressure_level in _HIGH_PRESSURE:
        pressure_delta = min(pressure_delta, 0)

    return pressure_delta, agency_delta


# ---------------------------------------------------------------------------
# Public API — build_reframe_plan
# ---------------------------------------------------------------------------
def build_reframe_plan(
    snapshot: EmotionalSnapshot,
    geometry: EmotionalGeometry,
    intention: EmotionalIntention,
    primitive: ExpressionPrimitive,
) -> ReframePlan:
    """Construct a ReframePlan from the structural inputs.

    Pure function. No I/O, no randomness, no LLM.

    Args:
        snapshot:  EmotionalSnapshot — pressure / intensity / valence /
                   temporal links.
        geometry:  EmotionalGeometry — curvature / torsion / shear /
                   boundary / stance vectors.
        intention: EmotionalIntention — what the user is trying to do.
        primitive: ExpressionPrimitive — the Language Layer's chosen
                   expression mode (forwarded into the plan).

    Returns:
        ReframePlan with steps + primitive + expected deltas.

    Algorithm:
        * HIGH/CRITICAL pressure path: only AGENCY and SCALE permitted.
        * LOW/MEDIUM pressure path: full palette per SPEC § 5.2.
        * Empty result → [NONE] step.
        * Deltas computed from step-type set per SPEC § 5.3.
    """
    if _is_high_pressure(snapshot):
        steps = _build_steps_high_pressure(snapshot, geometry, intention)
    else:
        steps = _build_steps_low_medium_pressure(snapshot, geometry, intention)

    if not steps:
        steps = [_step(ReframeType.NONE)]

    step_types = frozenset(s.reframe_type for s in steps)
    pressure_delta, agency_delta = _compute_deltas(
        step_types, snapshot.pressure_level,
    )

    return ReframePlan(
        steps=tuple(steps),
        primitive=primitive,
        expected_pressure_delta=pressure_delta,
        expected_agency_delta=agency_delta,
    )


# ---------------------------------------------------------------------------
# Public API — compute_alignment_score
# ---------------------------------------------------------------------------
def compute_alignment_score(
    snapshot: EmotionalSnapshot,
    geometry: EmotionalGeometry,
    intention: EmotionalIntention,
    plan: ReframePlan,
) -> float:
    """Deterministic heuristic — pure function of all four inputs.

    Per SPEC § 6:
        baseline 0.5
        +0.2  if AGENCY in steps and expected_agency_delta >= 0
        +0.2  if SCALE  in steps and expected_pressure_delta <= 0
        +0.1  if TEMPORAL in steps and snapshot.temporal_linked
        +0.1  if LABEL  in steps and (shear or stance_self >= 0.7)
        clip to [0.0, 1.0]

    `intention` is accepted for future extensibility; not consumed in
    the v1 heuristic.
    """
    _ = intention  # reserved for v2 scoring

    score = 0.5
    step_types = frozenset(s.reframe_type for s in plan.steps)

    if (ReframeType.AGENCY in step_types
            and plan.expected_agency_delta >= 0):
        score += 0.2

    if (ReframeType.SCALE in step_types
            and plan.expected_pressure_delta <= 0):
        score += 0.2

    if ReframeType.TEMPORAL in step_types and snapshot.temporal_linked:
        score += 0.1

    if (ReframeType.LABEL in step_types
            and (geometry.shear or geometry.stance_self >= _STANCE_HIGH_THRESHOLD)):
        score += 0.1

    # Clamp.
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return round(score, 4)


# ---------------------------------------------------------------------------
# Safety flag helpers
# ---------------------------------------------------------------------------
def _internal_relator_preserved(
    snapshot: EmotionalSnapshot,
    plan: ReframePlan,
) -> bool:
    """True if no step in the plan contradicts the snapshot.

    Per SPEC § 7.1: no MEANING step may appear under HIGH/CRITICAL.
    """
    if not _is_high_pressure(snapshot):
        return True
    step_types = {s.reframe_type for s in plan.steps}
    return ReframeType.MEANING not in step_types


def _safe_for_surface(
    snapshot: EmotionalSnapshot,
    plan: ReframePlan,
) -> bool:
    """True iff the plan is safe to apply at the surface.

    Per SPEC § 7.2:
        * expected_pressure_delta <= 0
        * no MEANING under HIGH/CRITICAL pressure
    """
    if plan.expected_pressure_delta > 0:
        return False
    if _is_high_pressure(snapshot):
        step_types = {s.reframe_type for s in plan.steps}
        if ReframeType.MEANING in step_types:
            return False
    return True


# ---------------------------------------------------------------------------
# Public API — align_expression
# ---------------------------------------------------------------------------
def align_expression(
    snapshot: EmotionalSnapshot,
    geometry: EmotionalGeometry,
    intention: EmotionalIntention,
    primitive: ExpressionPrimitive,
) -> AlignedExpression:
    """Compose plan + score + safety flags into a single AlignedExpression.

    Pure function — deterministic given the inputs. ERA is advisory:
    the AlignedExpression carries the plan and the safety verdict, but
    the surface decides what to DO with that information (the final
    decision still passes through the Sovereignty Gate downstream).

    Args:
        snapshot:  EmotionalSnapshot.
        geometry:  EmotionalGeometry.
        intention: EmotionalIntention.
        primitive: ExpressionPrimitive (from the Language Layer).

    Returns:
        AlignedExpression with plan, alignment_score in [0, 1],
        internal_relator_preserved bool, and safe_for_surface bool.
    """
    plan = build_reframe_plan(snapshot, geometry, intention, primitive)
    score = compute_alignment_score(snapshot, geometry, intention, plan)
    preserved = _internal_relator_preserved(snapshot, plan)
    safe = _safe_for_surface(snapshot, plan)
    return AlignedExpression(
        plan=plan,
        alignment_score=score,
        internal_relator_preserved=preserved,
        safe_for_surface=safe,
    )
