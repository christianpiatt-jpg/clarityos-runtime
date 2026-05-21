"""
fea_integration_engine.py — Deterministic FEA Integration Layer.

Pure, deterministic, testable. No I/O. No randomness. No LLM. No
network.

Given an AlignedExpression (from FEA) plus Ambient Trust outputs
(MomentumCheck, UnderstandingCheck) and the reserved-for-future
SessionContext / TrustState / EnvelopeState / PropagationState inputs,
produces an IntegratedAlignmentResult that:

    * passes AlignedExpression through unmodified (object identity),
    * encodes halt level for the surface,
    * encodes a trust score delta in [0.0, 1.0],
    * passes through the momentum-preserved flag,
    * emits structural surface directives (pacing, disclosure,
      checkpoint, preview).

CORE INVARIANT
--------------
    FEA safety flags are authoritative.
    Ambient Trust is advisory.
    The integration layer never converts trust signals into safety
    overrides, never auto-sends, and never mutates upstream state.

V1 SCOPE NOTE
-------------
    The signature accepts seven inputs for forward compatibility, but
    v1 only branches on:
        * aligned        (FEA output)
        * momentum       (Ambient Trust)
        * understanding  (Ambient Trust)
    The four reserved inputs (session, trust, envelope, propagation)
    are accepted, intentionally NOT branched on, and asserted as
    untouched by the source-code tests.

PUBLIC API
----------
    integrate_alignment(
        aligned, session, trust, envelope, propagation,
        momentum, understanding,
    ) -> IntegratedAlignmentResult

See SPEC_FEA_INTEGRATION.md for the full specification.
"""
from __future__ import annotations

# Upstream type imports — read-only.
from emotional_alignment_schemas import AlignedExpression, ReframeType
from ambient_trust_schemas import (
    MomentumCheck,
    SessionContext,
    TrustState,
    UnderstandingCheck,
)
from azimuth import EnvelopeState
from orchestrator_schemas import PropagationState

# Own types.
from fea_integration_schemas import (
    CANONICAL_DIRECTIVE_VALUES,
    IntegratedAlignmentResult,
    SurfaceDirective,
    SurfaceDirectiveType,
    SurfaceHaltLevel,
)


# ---------------------------------------------------------------------------
# Locked thresholds + deltas — change here affects deterministic behavior
# ---------------------------------------------------------------------------

# Below this alignment score, the surface is asked to soft-halt.
_SOFT_HALT_SCORE_THRESHOLD: float = 0.4

# Trust delta contributions per SPEC § 7.
_TRUST_DELTA_MOMENTUM_BONUS: float = 0.1
_TRUST_DELTA_HALT_PENALTY:   float = 0.1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_directive(
    directive_type: SurfaceDirectiveType,
    value: str,
) -> SurfaceDirective:
    """Construct a SurfaceDirective, validating `value` against the
    locked canonical set.

    Raises ValueError if `value` is not canonical. The engine itself
    only ever emits canonical values, so this is defense in depth — any
    drift in the rule table is caught here at construction time.
    """
    if value not in CANONICAL_DIRECTIVE_VALUES.get(directive_type, frozenset()):
        raise ValueError(
            f"non-canonical directive value: {directive_type}={value!r}"
        )
    return SurfaceDirective(directive_type=directive_type, value=value)


def _compute_halt_level(aligned: AlignedExpression) -> SurfaceHaltLevel:
    """SPEC § 5 — deterministic, exclusive.

        safe_for_surface == False        → HARD
        alignment_score < threshold      → SOFT
        otherwise                         → NONE
    """
    if not aligned.safe_for_surface:
        return SurfaceHaltLevel.HARD
    if aligned.alignment_score < _SOFT_HALT_SCORE_THRESHOLD:
        return SurfaceHaltLevel.SOFT
    return SurfaceHaltLevel.NONE


def _compute_trust_delta(
    momentum: MomentumCheck,
    halt_level: SurfaceHaltLevel,
) -> float:
    """SPEC § 7 — pure heuristic, clamped to [0.0, 1.0].

        baseline 0.0
        + 0.1 if momentum.passes_invariant
        − 0.1 if halt_level != NONE
        clamp to [0.0, 1.0]; round to 4 places.
    """
    delta = 0.0
    if momentum.passes_invariant:
        delta += _TRUST_DELTA_MOMENTUM_BONUS
    if halt_level != SurfaceHaltLevel.NONE:
        delta -= _TRUST_DELTA_HALT_PENALTY
    if delta < 0.0:
        return 0.0
    if delta > 1.0:
        return 1.0
    return round(delta, 4)


def _build_surface_directives(
    aligned: AlignedExpression,
    momentum: MomentumCheck,
    understanding: UnderstandingCheck,
    halt_level: SurfaceHaltLevel,
) -> tuple:
    """SPEC § 6 — additive directive generation in canonical priority
    order, deduplicated by (directive_type, value) pair.

    Order:
        1. PACE/slow         — pressure_delta > 0 OR understanding fails
        2. CHECKPOINT/offer  — agency_delta > 0  OR momentum   fails
        3. DISCLOSURE/single — TEMPORAL ∈ steps
        4. DISCLOSURE/full   — MEANING  ∈ steps
        5. PREVIEW/preview   — halt_level == HARD
    """
    step_types = frozenset(s.reframe_type for s in aligned.plan.steps)

    directives: list = []
    seen: set = set()

    def _add(directive_type: SurfaceDirectiveType, value: str) -> None:
        key = (directive_type, value)
        if key in seen:
            return
        seen.add(key)
        directives.append(_make_directive(directive_type, value))

    # Order 1 — PACE/slow.
    if (aligned.plan.expected_pressure_delta > 0
            or not understanding.passes_invariant):
        _add(SurfaceDirectiveType.PACE, "slow")

    # Order 2 — CHECKPOINT/offer_choice.
    if (aligned.plan.expected_agency_delta > 0
            or not momentum.passes_invariant):
        _add(SurfaceDirectiveType.CHECKPOINT, "offer_choice")

    # Order 3 — DISCLOSURE/single_concept (TEMPORAL).
    if ReframeType.TEMPORAL in step_types:
        _add(SurfaceDirectiveType.DISCLOSURE, "single_concept")

    # Order 4 — DISCLOSURE/full_model_available (MEANING).
    if ReframeType.MEANING in step_types:
        _add(SurfaceDirectiveType.DISCLOSURE, "full_model_available")

    # Order 5 — PREVIEW/preview_only (HARD halt only).
    if halt_level == SurfaceHaltLevel.HARD:
        _add(SurfaceDirectiveType.PREVIEW, "preview_only")

    return tuple(directives)


# ---------------------------------------------------------------------------
# Public API — integrate_alignment
# ---------------------------------------------------------------------------
def integrate_alignment(
    aligned: AlignedExpression,
    session: SessionContext,
    trust: TrustState,
    envelope: EnvelopeState,
    propagation: PropagationState,
    momentum: MomentumCheck,
    understanding: UnderstandingCheck,
) -> IntegratedAlignmentResult:
    """Pure function. Produce an IntegratedAlignmentResult from FEA +
    Ambient Trust + reserved-for-future state inputs.

    Args:
        aligned:       FEA's AlignedExpression (carries plan +
                       alignment_score + safety flags).
        session:       Ambient Trust SessionContext (reserved for v2 —
                       NOT branched on in v1).
        trust:         Ambient Trust TrustState (reserved — NOT
                       branched on in v1).
        envelope:      Azimuth EnvelopeState (reserved — NOT branched
                       on in v1).
        propagation:   Orchestrator PropagationState (reserved — NOT
                       branched on in v1).
        momentum:      Pre-computed Ambient Trust MomentumCheck.
        understanding: Pre-computed Ambient Trust UnderstandingCheck.

    Returns:
        IntegratedAlignmentResult with:
            * aligned_expression — object-identity passthrough of `aligned`
            * halt_level         — SurfaceHaltLevel per SPEC § 5
            * trust_state_delta  — float ∈ [0.0, 1.0] per SPEC § 7
            * momentum_preserved — bool (passthrough of
                                   momentum.passes_invariant)
            * surface_directives — tuple[SurfaceDirective, ...] per SPEC § 6

    Pure: same inputs → byte-equal output. No I/O, no randomness, no
    LLM, no network. Inputs are never mutated.
    """
    # Touch the reserved inputs once so static analyzers don't flag them
    # as unused — the source-code test asserts no FIELD accesses occur,
    # not that the parameters are unreferenced.
    _ = session
    _ = trust
    _ = envelope
    _ = propagation

    halt_level = _compute_halt_level(aligned)
    delta = _compute_trust_delta(momentum, halt_level)
    directives = _build_surface_directives(
        aligned=aligned,
        momentum=momentum,
        understanding=understanding,
        halt_level=halt_level,
    )

    return IntegratedAlignmentResult(
        aligned_expression=aligned,                    # object-identity passthrough
        halt_level=halt_level,
        trust_state_delta=delta,
        momentum_preserved=momentum.passes_invariant,  # bool passthrough
        surface_directives=directives,
    )
