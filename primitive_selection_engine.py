"""
primitive_selection_engine.py — Deterministic Primitive Selection Engine.

Pure, deterministic, testable. No I/O. No randomness. No LLM calls.

Given a LanguageContext, select_expression_plan() returns an
ExpressionPlan choosing:
    * the expression primitive (Motion / Geometry / Hydronics / Analogy)
    * the tone (Stable / Direct / Softened / Expansive)
    * the structure (Highly-structured / Moderate / Minimal)
    * the length (Short / Medium / Long)

SELECTION DISCIPLINE (priority order — higher priority wins):

    1. HARD OVERRIDE — pressure ∈ {HIGH, CRITICAL}     → HYDRONICS + STABLE tone
    2. HARD OVERRIDE — drift.in_bounds == False        → ANALOGY (clarity bridge)
    3. mode == STRUCTURAL                              → GEOMETRY
    4. mode == DECISION                                → MOTION
    5. mode == OPERATOR                                → GEOMETRY (identity tie-break)
    6. mode == EXPLORATORY                             → ANALOGY
    7. mode == EMOTIONAL                               → HYDRONICS
    8. default                                         → GEOMETRY

Whiplash prevention: if last_primitive is set and the candidate differs
without a meaningful geometry change, stick with last_primitive UNLESS
the current mode strictly requires a different primitive. Hard
overrides (rules 1 and 2) always bypass whiplash prevention.

INVARIANTS (locked, test-enforced):
    * Pure function — no I/O, no randomness, no LLM calls.
    * Same LanguageContext → byte-identical ExpressionPlan.
    * HIGH/CRITICAL pressure → STABLE tone (no emotional escalation).
    * Drift out of bounds → ANALOGY (drift reduction).
"""
from __future__ import annotations

from language_schemas import (
    ConversationMode,
    ExpressionPlan,
    ExpressionPrimitive,
    LanguageContext,
    LengthProfile,
    StructureProfile,
    ToneProfile,
)
from azimuth import PressureLevel
from orchestrator_schemas import ActorKind, AuthorizationTier


# ---------------------------------------------------------------------------
# Tuning constants — locked thresholds for determinism
# ---------------------------------------------------------------------------

# Pressure levels that trigger the HYDRONICS hard-override.
_HIGH_PRESSURE: frozenset = frozenset({
    PressureLevel.HIGH, PressureLevel.CRITICAL,
})

# Thresholds for "meaningful geometry change" in whiplash detection.
# Locked for deterministic test behavior.
_PRESSURE_LOAD_DELTA:   float = 0.2
_STABILITY_SCORE_DELTA: float = 0.2


# ---------------------------------------------------------------------------
# Primitive selection
# ---------------------------------------------------------------------------
def _hard_override_primitive(ctx: LanguageContext) -> ExpressionPrimitive | None:
    """Return a primitive from a hard-override rule, or None if none apply.

    Rules 1 and 2 — these bypass whiplash prevention.
    """
    # Rule 1: HIGH/CRITICAL pressure → HYDRONICS.
    if ctx.envelope.pressure_level in _HIGH_PRESSURE:
        return ExpressionPrimitive.HYDRONICS
    # Rule 2: drift out of bounds → ANALOGY.
    if not ctx.drift_state.in_bounds:
        return ExpressionPrimitive.ANALOGY
    return None


def _operator_mode_primitive(ctx: LanguageContext) -> ExpressionPrimitive:
    """Tie-break GEOMETRY vs MOTION in OPERATOR mode using identity."""
    identity = ctx.identity_profile
    # Operator-grade default per spec § 6.1: USER with EXECUTE tier → GEOMETRY.
    if (
        identity.actor_kind == ActorKind.USER
        and identity.authorization_tier == AuthorizationTier.EXECUTE
    ):
        return ExpressionPrimitive.GEOMETRY
    return ExpressionPrimitive.MOTION


def _mode_driven_primitive(ctx: LanguageContext) -> ExpressionPrimitive:
    """Rules 3–8 — primitive from conversation mode (no overrides)."""
    mode = ctx.conversation_mode
    if mode == ConversationMode.STRUCTURAL:
        return ExpressionPrimitive.GEOMETRY
    if mode == ConversationMode.DECISION:
        return ExpressionPrimitive.MOTION
    if mode == ConversationMode.OPERATOR:
        return _operator_mode_primitive(ctx)
    if mode == ConversationMode.EXPLORATORY:
        return ExpressionPrimitive.ANALOGY
    if mode == ConversationMode.EMOTIONAL:
        return ExpressionPrimitive.HYDRONICS
    # default
    return ExpressionPrimitive.GEOMETRY


def _meaningful_geometry_change(ctx: LanguageContext) -> bool:
    """True if geometry has materially changed vs the prior propagation.

    "Materially" means pressure_load OR stability_score moved by at
    least the configured deltas. Pure comparison.
    """
    if ctx.propagation_state is None:
        # No prior — switching is always allowed (no whiplash to detect).
        return True
    prior = ctx.propagation_state.geometry_profile
    curr  = ctx.geometry_profile
    return (
        abs(curr.pressure_load - prior.pressure_load) >= _PRESSURE_LOAD_DELTA
        or abs(curr.stability_score - prior.stability_score) >= _STABILITY_SCORE_DELTA
    )


def _mode_strictly_requires(
    mode: ConversationMode,
    primitive: ExpressionPrimitive,
) -> bool:
    """True iff the mode strictly requires this primitive.

    Mode-strict requirements override whiplash continuity:
        * STRUCTURAL strictly requires GEOMETRY
        * DECISION   strictly requires MOTION
    """
    if mode == ConversationMode.STRUCTURAL and primitive == ExpressionPrimitive.GEOMETRY:
        return True
    if mode == ConversationMode.DECISION and primitive == ExpressionPrimitive.MOTION:
        return True
    return False


def _select_primitive(ctx: LanguageContext) -> ExpressionPrimitive:
    """Run the full priority chain: hard overrides → mode → whiplash check."""
    # 1+2: hard overrides bypass everything else.
    override = _hard_override_primitive(ctx)
    if override is not None:
        return override

    # 3-8: mode-driven candidate.
    candidate = _mode_driven_primitive(ctx)

    # Whiplash prevention.
    if (
        ctx.last_primitive is not None
        and candidate != ctx.last_primitive
        and not _meaningful_geometry_change(ctx)
        and not _mode_strictly_requires(ctx.conversation_mode, candidate)
    ):
        return ctx.last_primitive

    return candidate


# ---------------------------------------------------------------------------
# Tone / structure / length selection
# ---------------------------------------------------------------------------
def _select_tone_structure_length(
    ctx: LanguageContext,
) -> tuple:
    """Return (tone, structure, length) tuple based on pressure + mode."""
    # Pressure override — invariant #9: no emotional escalation.
    # HIGH/CRITICAL pressure forces STABLE tone regardless of mode.
    if ctx.envelope.pressure_level in _HIGH_PRESSURE:
        return (
            ToneProfile.STABLE,
            StructureProfile.HIGHLY_STRUCTURED,
            LengthProfile.MEDIUM,
        )

    mode = ctx.conversation_mode
    if mode == ConversationMode.OPERATOR:
        return (
            ToneProfile.DIRECT,
            StructureProfile.HIGHLY_STRUCTURED,
            LengthProfile.MEDIUM,
        )
    if mode == ConversationMode.EXPLORATORY:
        return (
            ToneProfile.EXPANSIVE,
            StructureProfile.MODERATE,
            LengthProfile.LONG,
        )
    if mode == ConversationMode.EMOTIONAL:
        return (
            ToneProfile.SOFTENED,
            StructureProfile.MODERATE,
            LengthProfile.MEDIUM,
        )
    if mode == ConversationMode.DECISION:
        return (
            ToneProfile.DIRECT,
            StructureProfile.HIGHLY_STRUCTURED,
            LengthProfile.SHORT,
        )
    if mode == ConversationMode.STRUCTURAL:
        return (
            ToneProfile.DIRECT,
            StructureProfile.HIGHLY_STRUCTURED,
            LengthProfile.MEDIUM,
        )

    # Safe default.
    return (
        ToneProfile.STABLE,
        StructureProfile.MODERATE,
        LengthProfile.MEDIUM,
    )


# ---------------------------------------------------------------------------
# Rationale builder — human-readable selection trace
# ---------------------------------------------------------------------------
def _build_rationale(
    ctx: LanguageContext,
    primitive: ExpressionPrimitive,
    tone: ToneProfile,
    structure: StructureProfile,
    length: LengthProfile,
) -> str:
    """Construct a short human-readable rationale string. Deterministic."""
    pressure = ctx.envelope.pressure_level
    mode = ctx.conversation_mode
    drift_ok = ctx.drift_state.in_bounds

    parts: list = []

    # Why this primitive?
    if pressure in _HIGH_PRESSURE:
        parts.append(f"pressure={pressure.value} → HYDRONICS override")
    elif not drift_ok:
        parts.append("drift out of bounds → ANALOGY override")
    elif (
        ctx.last_primitive is not None
        and primitive == ctx.last_primitive
        and not _meaningful_geometry_change(ctx)
    ):
        parts.append(
            f"continuity preserved (last={ctx.last_primitive.value}, "
            f"no meaningful geometry change)"
        )
    else:
        parts.append(f"mode={mode.value} → {primitive.value}")

    # Why this tone?
    if pressure in _HIGH_PRESSURE:
        parts.append("tone=STABLE (no emotional escalation)")
    else:
        parts.append(f"tone={tone.value} (mode default)")

    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def select_expression_plan(ctx: LanguageContext) -> ExpressionPlan:
    """Pure, deterministic selection of the response shape for one turn.

    Algorithm (priority order):

        1. If pressure ∈ {HIGH, CRITICAL}: HYDRONICS + STABLE tone
           (hard override; bypasses whiplash check).
        2. If drift out of bounds: ANALOGY (hard override).
        3. Else mode-driven:
              STRUCTURAL  → GEOMETRY
              DECISION    → MOTION
              OPERATOR    → GEOMETRY (operator-grade) / MOTION (otherwise)
              EXPLORATORY → ANALOGY
              EMOTIONAL   → HYDRONICS
        4. Whiplash prevention: if last_primitive set and no meaningful
           geometry change, stick with last_primitive unless mode strictly
           requires a different one (STRUCTURAL needs GEOMETRY, DECISION
           needs MOTION).
        5. Compute (tone, structure, length) from pressure + mode.
        6. Build deterministic rationale string.

    Args:
        ctx: LanguageContext with all fields populated.

    Returns:
        ExpressionPlan — deterministic given the input.

    INVARIANTS:
        * Pure (no I/O, no randomness).
        * Determinism: select_expression_plan(ctx) == select_expression_plan(ctx).
        * Pressure ∈ {HIGH, CRITICAL} ⇒ tone = STABLE.
        * Drift out of bounds ⇒ primitive = ANALOGY.
    """
    primitive = _select_primitive(ctx)
    tone, structure, length = _select_tone_structure_length(ctx)
    rationale = _build_rationale(ctx, primitive, tone, structure, length)
    return ExpressionPlan(
        primitive=primitive,
        tone=tone,
        structure=structure,
        length=length,
        rationale=rationale,
    )
