"""
Tests for the FEA Integration Layer.

Two layers:
    1. Structural — enums / schemas / privacy contract / module-load
       guards / canonical directive values.
    2. Behavioral — integrate_alignment against concrete fixtures
       producing the expected halt level / trust delta / momentum
       flag / surface directives.

The engine is pure and deterministic, so behavioral tests assert
byte-equal returns. No mocking required — no I/O exists to mock.
"""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

import fea_integration_engine as engine
import fea_integration_schemas as schemas
import emotional_alignment_engine as fea_engine
import emotional_alignment_schemas as fea_schemas
import ambient_trust_engine as trust_engine
import ambient_trust_schemas as trust_schemas

from azimuth import (
    EnvelopeState,
    IntensityLevel,
    PressureLevel,
    Valence,
)
from language_schemas import ExpressionPrimitive
from orchestrator_schemas import (
    ActorKind,
    AuthorizationTier,
    DriftAxis,
    DriftState,
    GeometryProfile,
    IdentityProfile,
    PropagationState,
    SovereigntyLevel,
)


# ===========================================================================
# Upstream-state fixture builders
# ===========================================================================
_FIXED_TIME = datetime(2026, 5, 11, 12, 0, 0)


def _envelope(
    *,
    raw_text: str = "stub",
    pressure_level: PressureLevel = PressureLevel.LOW,
    valence: Valence = Valence.NEUTRAL,
    intensity: IntensityLevel = IntensityLevel.LOW,
    rough_intention: str = "stub-intention",
) -> EnvelopeState:
    return EnvelopeState(
        raw_text=raw_text,
        captured_at=_FIXED_TIME,
        emotional_intensity=intensity,
        valence=valence,
        pressure_level=pressure_level,
        rough_intention=rough_intention,
    )


def _propagation() -> PropagationState:
    drift = DriftState(
        axis=DriftAxis.INTENT, magnitude=0.1, direction="stable",
        baseline_anchor="stub", in_bounds=True, measured_at=_FIXED_TIME,
    )
    geom = GeometryProfile(
        depth=0, breadth=1, pressure_load=0.2,
        stability_score=0.9, captured_at=_FIXED_TIME,
    )
    ident = IdentityProfile(
        actor="test", actor_kind=ActorKind.USER,
        sovereignty_level=SovereigntyLevel.USER_OWNED,
        authorization_tier=AuthorizationTier.EXECUTE,
    )
    return PropagationState(
        from_step="x", to_step="y",
        active_constraints=(),
        drift_state=drift,
        geometry_profile=geom,
        identity_profile=ident,
        invariants_preserved=(),
    )


def _session(
    *,
    ability: int = 2,
    comprehension: int = 2,
    hard_stops: int = 0,
    ack: bool = True,
) -> trust_schemas.SessionContext:
    return trust_schemas.SessionContext(
        ability_level=ability,
        comprehension_level=comprehension,
        concept_exposures=(),
        hard_stop_count=hard_stops,
        last_action_acknowledged=ack,
    )


def _trust_state(ctx: trust_schemas.SessionContext) -> trust_schemas.TrustState:
    return trust_engine.assess_trust_state(ctx)


def _momentum(ctx: trust_schemas.SessionContext) -> trust_schemas.MomentumCheck:
    return trust_engine.verify_no_hard_stops(ctx)


def _understanding(
    ctx: trust_schemas.SessionContext,
) -> trust_schemas.UnderstandingCheck:
    return trust_engine.verify_comprehension_leads_action(ctx)


# ===========================================================================
# FEA-aligned-expression fixture builders
# ===========================================================================
def _aligned(
    *,
    safe_for_surface: bool = True,
    alignment_score: float = 0.9,
    steps: tuple = (),
    pressure_delta: int = 0,
    agency_delta: int = 0,
    primitive: ExpressionPrimitive = ExpressionPrimitive.GEOMETRY,
    internal_relator_preserved: bool = True,
) -> fea_schemas.AlignedExpression:
    """Construct an AlignedExpression directly (bypassing the FEA engine)
    so we can exercise every halt path including hand-built unsafe plans.
    """
    if not steps:
        steps = (fea_schemas.ReframeStep(
            reframe_type=fea_schemas.ReframeType.NONE,
            rationale="x",
        ),)
    plan = fea_schemas.ReframePlan(
        steps=steps,
        primitive=primitive,
        expected_pressure_delta=pressure_delta,
        expected_agency_delta=agency_delta,
    )
    return fea_schemas.AlignedExpression(
        plan=plan,
        alignment_score=alignment_score,
        internal_relator_preserved=internal_relator_preserved,
        safe_for_surface=safe_for_surface,
    )


def _step(rt: fea_schemas.ReframeType) -> fea_schemas.ReframeStep:
    return fea_schemas.ReframeStep(reframe_type=rt, rationale="x")


# ===========================================================================
# Top-level call helper
# ===========================================================================
def _integrate(
    aligned: fea_schemas.AlignedExpression,
    *,
    ctx: trust_schemas.SessionContext = None,
) -> schemas.IntegratedAlignmentResult:
    if ctx is None:
        ctx = _session()
    return engine.integrate_alignment(
        aligned=aligned,
        session=ctx,
        trust=_trust_state(ctx),
        envelope=_envelope(),
        propagation=_propagation(),
        momentum=_momentum(ctx),
        understanding=_understanding(ctx),
    )


# ===========================================================================
# A. Enums
# ===========================================================================
class TestEnums:
    def test_surface_halt_level_values(self):
        assert {v.value for v in schemas.SurfaceHaltLevel} == {
            "no_halt", "soft_halt", "hard_halt",
        }

    def test_surface_directive_type_values(self):
        assert {v.value for v in schemas.SurfaceDirectiveType} == {
            "pace", "disclosure", "checkpoint", "preview",
        }

    def test_no_directive_type_halt_member(self):
        """Invariant: halt is encoded in SurfaceHaltLevel, NEVER in
        SurfaceDirectiveType. Structurally enforced."""
        for v in schemas.SurfaceDirectiveType:
            assert "halt" not in v.value.lower()
            assert "block" not in v.value.lower()
            assert "stop" not in v.value.lower()


# ===========================================================================
# B. Schemas — frozen + instantiable
# ===========================================================================
class TestSurfaceDirective:
    def test_instantiable(self):
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.PACE, value="slow",
        )
        assert d.value == "slow"

    def test_frozen(self):
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.PACE, value="slow",
        )
        with pytest.raises(FrozenInstanceError):
            d.value = "normal"  # type: ignore[misc]


class TestIntegratedAlignmentResult:
    def test_instantiable(self):
        aligned = _aligned()
        r = schemas.IntegratedAlignmentResult(
            aligned_expression=aligned,
            halt_level=schemas.SurfaceHaltLevel.NONE,
            trust_state_delta=0.1,
            momentum_preserved=True,
            surface_directives=(),
        )
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE

    def test_frozen(self):
        aligned = _aligned()
        r = schemas.IntegratedAlignmentResult(
            aligned_expression=aligned,
            halt_level=schemas.SurfaceHaltLevel.NONE,
            trust_state_delta=0.1,
            momentum_preserved=True,
            surface_directives=(),
        )
        with pytest.raises(FrozenInstanceError):
            r.trust_state_delta = 0.5  # type: ignore[misc]


# ===========================================================================
# C. Privacy contract — no forbidden fields
# ===========================================================================
class TestPrivacyContract:
    @pytest.mark.parametrize("cls_name", [
        "SurfaceDirective", "IntegratedAlignmentResult",
    ])
    @pytest.mark.parametrize("forbidden", [
        "text", "raw", "raw_text",
        "user", "user_id", "id",
        "name", "names", "email",
        "session", "session_id", "identity",
        "envelope_id", "author", "actor",
        "content", "body", "message",
    ])
    def test_no_forbidden_field(self, cls_name, forbidden):
        cls = getattr(schemas, cls_name)
        assert forbidden not in cls.__dataclass_fields__, (
            f"{cls_name}.{forbidden} would leak identity/text — forbidden"
        )

    def test_surface_directive_canonical_fields(self):
        assert set(schemas.SurfaceDirective.__dataclass_fields__.keys()) == {
            "directive_type", "value",
        }

    def test_integrated_result_canonical_fields(self):
        assert set(schemas.IntegratedAlignmentResult.__dataclass_fields__.keys()) == {
            "aligned_expression", "halt_level",
            "trust_state_delta", "momentum_preserved",
            "surface_directives",
        }


# ===========================================================================
# D. Module-load runtime guards
# ===========================================================================
class TestRuntimeGuards:
    def test_privacy_guard_passes(self):
        schemas.assert_fea_integration_privacy_contract()

    def test_field_set_guard_passes(self):
        schemas.assert_fea_integration_field_sets_canonical()

    def test_halt_levels_canonical(self):
        schemas.assert_surface_halt_levels_canonical()

    def test_directive_types_canonical(self):
        schemas.assert_surface_directive_types_canonical()

    def test_canonical_directive_values(self):
        schemas.assert_canonical_directive_values()


# ===========================================================================
# E. Canonical directive value table
# ===========================================================================
class TestCanonicalDirectiveValues:
    def test_pace_set(self):
        assert schemas.CANONICAL_DIRECTIVE_VALUES[
            schemas.SurfaceDirectiveType.PACE
        ] == frozenset({"slow", "normal"})

    def test_disclosure_set(self):
        assert schemas.CANONICAL_DIRECTIVE_VALUES[
            schemas.SurfaceDirectiveType.DISCLOSURE
        ] == frozenset({"single_concept", "full_model_available"})

    def test_checkpoint_set(self):
        assert schemas.CANONICAL_DIRECTIVE_VALUES[
            schemas.SurfaceDirectiveType.CHECKPOINT
        ] == frozenset({"offer_choice"})

    def test_preview_set(self):
        assert schemas.CANONICAL_DIRECTIVE_VALUES[
            schemas.SurfaceDirectiveType.PREVIEW
        ] == frozenset({"preview_only"})

    def test_is_canonical_directive_value_helper(self):
        for dtype, values in schemas.CANONICAL_DIRECTIVE_VALUES.items():
            for v in values:
                assert schemas.is_canonical_directive_value(dtype, v) is True
        assert schemas.is_canonical_directive_value(
            schemas.SurfaceDirectiveType.PACE, "warp_speed",
        ) is False

    def test_engine_rejects_non_canonical_value(self):
        """Defense-in-depth: _make_directive raises if a non-canonical
        value sneaks in."""
        with pytest.raises(ValueError):
            engine._make_directive(
                schemas.SurfaceDirectiveType.PACE, "warp_speed",
            )


# ===========================================================================
# F. Halt-level derivation (SPEC § 5)
# ===========================================================================
class TestHaltLevel:
    def test_safe_high_score_yields_none(self):
        aligned = _aligned(safe_for_surface=True, alignment_score=0.9)
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE

    def test_safe_at_threshold_yields_none(self):
        """alignment_score == 0.4 → still NONE (strict `<` threshold)."""
        aligned = _aligned(safe_for_surface=True, alignment_score=0.4)
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE

    def test_safe_below_threshold_yields_soft(self):
        aligned = _aligned(safe_for_surface=True, alignment_score=0.39)
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.SOFT

    def test_unsafe_yields_hard(self):
        aligned = _aligned(safe_for_surface=False, alignment_score=0.9)
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.HARD

    def test_unsafe_overrides_low_score(self):
        """FEA safety flag is authoritative; HARD wins over SOFT."""
        aligned = _aligned(safe_for_surface=False, alignment_score=0.1)
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.HARD


# ===========================================================================
# G. Surface directive generation (SPEC § 6)
# ===========================================================================
class TestSurfaceDirectives:
    def test_pressure_delta_positive_emits_pace_slow(self):
        aligned = _aligned(pressure_delta=1)
        r = _integrate(aligned)
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.PACE, value="slow",
        )
        assert d in r.surface_directives

    def test_agency_delta_positive_emits_checkpoint(self):
        aligned = _aligned(agency_delta=1)
        r = _integrate(aligned)
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.CHECKPOINT,
            value="offer_choice",
        )
        assert d in r.surface_directives

    def test_temporal_step_emits_single_concept(self):
        aligned = _aligned(steps=(_step(fea_schemas.ReframeType.TEMPORAL),))
        r = _integrate(aligned)
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.DISCLOSURE,
            value="single_concept",
        )
        assert d in r.surface_directives

    def test_meaning_step_emits_full_model(self):
        aligned = _aligned(steps=(_step(fea_schemas.ReframeType.MEANING),))
        r = _integrate(aligned)
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.DISCLOSURE,
            value="full_model_available",
        )
        assert d in r.surface_directives

    def test_hard_halt_emits_preview_only(self):
        aligned = _aligned(safe_for_surface=False)
        r = _integrate(aligned)
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.PREVIEW,
            value="preview_only",
        )
        assert d in r.surface_directives

    def test_understanding_fails_emits_pace_slow(self):
        """Ambient-Trust trigger: understanding fails ⇒ PACE/slow."""
        ctx = _session(ability=3, comprehension=1)  # gap=2, fails
        aligned = _aligned()  # no FEA-driven pacing
        r = _integrate(aligned, ctx=ctx)
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.PACE, value="slow",
        )
        assert d in r.surface_directives

    def test_momentum_fails_emits_checkpoint(self):
        """Ambient-Trust trigger: momentum fails ⇒ CHECKPOINT."""
        ctx = _session(hard_stops=1)
        aligned = _aligned()  # no FEA-driven agency_delta
        r = _integrate(aligned, ctx=ctx)
        d = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.CHECKPOINT,
            value="offer_choice",
        )
        assert d in r.surface_directives

    def test_combined_triggers_dedup(self):
        """FEA pressure_delta AND understanding-fail both fire PACE/slow.
        Result must contain it exactly once."""
        ctx = _session(ability=3, comprehension=1)
        aligned = _aligned(pressure_delta=1)
        r = _integrate(aligned, ctx=ctx)
        pace_slow = schemas.SurfaceDirective(
            directive_type=schemas.SurfaceDirectiveType.PACE, value="slow",
        )
        count = sum(1 for d in r.surface_directives if d == pace_slow)
        assert count == 1

    def test_canonical_priority_order(self):
        """When all triggers fire, directives appear in canonical order."""
        ctx = _session(ability=3, comprehension=1, hard_stops=1)
        aligned = _aligned(
            safe_for_surface=False,         # → HARD halt → PREVIEW
            alignment_score=0.9,
            steps=(
                _step(fea_schemas.ReframeType.TEMPORAL),
                _step(fea_schemas.ReframeType.MEANING),
            ),
            pressure_delta=1,
            agency_delta=1,
        )
        r = _integrate(aligned, ctx=ctx)
        types_in_order = [d.directive_type for d in r.surface_directives]
        # Expected canonical priority: PACE, CHECKPOINT, DISCLOSURE, DISCLOSURE, PREVIEW
        assert types_in_order == [
            schemas.SurfaceDirectiveType.PACE,
            schemas.SurfaceDirectiveType.CHECKPOINT,
            schemas.SurfaceDirectiveType.DISCLOSURE,
            schemas.SurfaceDirectiveType.DISCLOSURE,
            schemas.SurfaceDirectiveType.PREVIEW,
        ]

    def test_no_triggers_yields_empty(self):
        aligned = _aligned()  # NONE plan, zero deltas, safe, score 0.9
        r = _integrate(aligned)
        assert r.surface_directives == ()

    def test_directive_values_are_canonical(self):
        """Every emitted directive value belongs to the canonical set."""
        ctx = _session(ability=3, comprehension=1, hard_stops=1)
        aligned = _aligned(
            safe_for_surface=False, steps=(
                _step(fea_schemas.ReframeType.TEMPORAL),
                _step(fea_schemas.ReframeType.MEANING),
            ),
            pressure_delta=1, agency_delta=1,
        )
        r = _integrate(aligned, ctx=ctx)
        for d in r.surface_directives:
            assert schemas.is_canonical_directive_value(
                d.directive_type, d.value,
            ), f"non-canonical directive: {d}"


# ===========================================================================
# H. Trust-state delta (SPEC § 7)
# ===========================================================================
class TestTrustDelta:
    def test_momentum_preserved_no_halt_yields_point_one(self):
        ctx = _session(ability=2, comprehension=2)
        r = _integrate(_aligned(), ctx=ctx)
        assert r.trust_state_delta == 0.1

    def test_momentum_preserved_soft_halt_yields_zero(self):
        ctx = _session(ability=2, comprehension=2)
        aligned = _aligned(alignment_score=0.2)  # SOFT halt
        r = _integrate(aligned, ctx=ctx)
        # +0.1 momentum - 0.1 halt = 0.0
        assert r.trust_state_delta == 0.0

    def test_momentum_preserved_hard_halt_yields_zero(self):
        ctx = _session()
        aligned = _aligned(safe_for_surface=False)  # HARD halt
        r = _integrate(aligned, ctx=ctx)
        assert r.trust_state_delta == 0.0

    def test_momentum_broken_no_halt_yields_zero(self):
        ctx = _session(hard_stops=1)  # momentum.passes_invariant = False
        r = _integrate(_aligned(), ctx=ctx)
        # 0.0 momentum + 0 halt = 0.0
        assert r.trust_state_delta == 0.0

    def test_momentum_broken_hard_halt_yields_zero(self):
        ctx = _session(hard_stops=1)
        aligned = _aligned(safe_for_surface=False)
        r = _integrate(aligned, ctx=ctx)
        # 0.0 momentum - 0.1 halt = -0.1 → clamped 0.0
        assert r.trust_state_delta == 0.0

    def test_delta_clamped_to_unit_interval(self):
        """Every reachable combination yields delta ∈ [0.0, 1.0]."""
        for safe in (True, False):
            for score in (0.0, 0.39, 0.4, 0.5, 0.9, 1.0):
                for hard_stops in (0, 1, 2):
                    ctx = _session(hard_stops=hard_stops)
                    aligned = _aligned(
                        safe_for_surface=safe, alignment_score=score,
                    )
                    r = _integrate(aligned, ctx=ctx)
                    assert 0.0 <= r.trust_state_delta <= 1.0


# ===========================================================================
# I. Momentum passthrough
# ===========================================================================
class TestMomentumPassthrough:
    def test_momentum_preserved_when_no_hard_stops(self):
        ctx = _session(hard_stops=0)
        r = _integrate(_aligned(), ctx=ctx)
        assert r.momentum_preserved is True

    def test_momentum_broken_when_hard_stop(self):
        ctx = _session(hard_stops=1)
        r = _integrate(_aligned(), ctx=ctx)
        assert r.momentum_preserved is False

    def test_momentum_passthrough_matches_ambient_trust_check(self):
        ctx = _session(hard_stops=2)
        expected = trust_engine.verify_no_hard_stops(ctx).passes_invariant
        r = _integrate(_aligned(), ctx=ctx)
        assert r.momentum_preserved == expected


# ===========================================================================
# J. AlignedExpression passthrough (invariant 4 — object identity)
# ===========================================================================
class TestAlignedExpressionPassthrough:
    def test_passthrough_object_identity(self):
        aligned = _aligned()
        r = _integrate(aligned)
        assert r.aligned_expression is aligned

    def test_passthrough_byte_equal(self):
        aligned = _aligned()
        r = _integrate(aligned)
        assert r.aligned_expression == aligned

    def test_passthrough_preserved_under_hard_halt(self):
        """Even when FEA flags unsafe, the AlignedExpression is unmodified."""
        aligned = _aligned(safe_for_surface=False, alignment_score=0.1)
        r = _integrate(aligned)
        assert r.aligned_expression is aligned


# ===========================================================================
# K. Worked examples (SPEC § 9)
# ===========================================================================
class TestWorkedExamples:
    def test_91_high_pressure_collapse(self):
        """SCALE + AGENCY, deltas (-1, +1), safe, high score."""
        aligned = _aligned(
            safe_for_surface=True, alignment_score=0.9,
            steps=(
                _step(fea_schemas.ReframeType.SCALE),
                _step(fea_schemas.ReframeType.AGENCY),
            ),
            pressure_delta=-1, agency_delta=1,
        )
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE
        assert r.trust_state_delta == 0.1
        assert r.momentum_preserved is True
        types = [d.directive_type for d in r.surface_directives]
        # agency_delta>0 fires CHECKPOINT; no others fire
        assert types == [schemas.SurfaceDirectiveType.CHECKPOINT]

    def test_92_authority_shame_full_plan(self):
        """Full FEA palette: TEMPORAL + LABEL + ROLE + AGENCY + MEANING."""
        aligned = _aligned(
            safe_for_surface=True, alignment_score=0.9,
            steps=(
                _step(fea_schemas.ReframeType.TEMPORAL),
                _step(fea_schemas.ReframeType.LABEL),
                _step(fea_schemas.ReframeType.ROLE),
                _step(fea_schemas.ReframeType.AGENCY),
                _step(fea_schemas.ReframeType.MEANING),
            ),
            pressure_delta=-1, agency_delta=1,
        )
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE
        assert r.trust_state_delta == 0.1
        values = {(d.directive_type, d.value) for d in r.surface_directives}
        assert (schemas.SurfaceDirectiveType.CHECKPOINT, "offer_choice") in values
        assert (schemas.SurfaceDirectiveType.DISCLOSURE, "single_concept") in values
        assert (schemas.SurfaceDirectiveType.DISCLOSURE, "full_model_available") in values

    def test_93_low_pressure_reflection(self):
        """LOW pressure, MEANING only, baseline score."""
        aligned = _aligned(
            safe_for_surface=True, alignment_score=0.5,
            steps=(_step(fea_schemas.ReframeType.MEANING),),
        )
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE
        assert r.trust_state_delta == 0.1
        values = {(d.directive_type, d.value) for d in r.surface_directives}
        assert values == {
            (schemas.SurfaceDirectiveType.DISCLOSURE, "full_model_available"),
        }

    def test_94_no_reframe_needed(self):
        """NONE plan, zero deltas."""
        aligned = _aligned()
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE
        assert r.trust_state_delta == 0.1
        assert r.surface_directives == ()
        assert r.momentum_preserved is True

    def test_95_unsafe_plan_hard_halt(self):
        """FEA hard-stop: safe_for_surface=False; HARD halt dominates."""
        aligned = _aligned(
            safe_for_surface=False, alignment_score=0.7,
            steps=(_step(fea_schemas.ReframeType.MEANING),),
            pressure_delta=1, agency_delta=0,
        )
        r = _integrate(aligned)
        assert r.halt_level == schemas.SurfaceHaltLevel.HARD
        assert r.trust_state_delta == 0.0  # +0.1 - 0.1 = 0.0
        values = {(d.directive_type, d.value) for d in r.surface_directives}
        assert values == {
            (schemas.SurfaceDirectiveType.PACE, "slow"),
            (schemas.SurfaceDirectiveType.DISCLOSURE, "full_model_available"),
            (schemas.SurfaceDirectiveType.PREVIEW, "preview_only"),
        }

    def test_96_edge_understanding_drives_pacing(self):
        """FEA clean but Ambient-Trust understanding fails → PACE/slow."""
        ctx = _session(ability=3, comprehension=1)
        aligned = _aligned()  # FEA clean, no plan
        r = _integrate(aligned, ctx=ctx)
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE  # FEA wins
        assert r.trust_state_delta == 0.1
        values = {(d.directive_type, d.value) for d in r.surface_directives}
        assert values == {
            (schemas.SurfaceDirectiveType.PACE, "slow"),
        }


# ===========================================================================
# L. Determinism
# ===========================================================================
class TestDeterminism:
    def test_byte_equal(self):
        aligned = _aligned(
            safe_for_surface=True, alignment_score=0.6,
            steps=(_step(fea_schemas.ReframeType.TEMPORAL),),
            pressure_delta=-1, agency_delta=1,
        )
        r1 = _integrate(aligned)
        r2 = _integrate(aligned)
        assert r1 == r2

    def test_byte_equal_with_hard_halt(self):
        aligned = _aligned(safe_for_surface=False)
        r1 = _integrate(aligned)
        r2 = _integrate(aligned)
        assert r1 == r2

    def test_byte_equal_with_ambient_trust_triggers(self):
        ctx = _session(ability=3, comprehension=1, hard_stops=2)
        aligned = _aligned()
        r1 = _integrate(aligned, ctx=ctx)
        r2 = _integrate(aligned, ctx=ctx)
        assert r1 == r2


# ===========================================================================
# M. Privacy — marker injection through EnvelopeState and intention
# ===========================================================================
class TestPrivacyMarkerInjection:
    def test_marker_in_envelope_raw_text_does_not_leak(self):
        """Even though raw_text is a field of EnvelopeState, the
        integration result must not contain it anywhere."""
        marker = "ZxYxQwertUniqueMarker8888"
        env = _envelope(raw_text=marker, rough_intention="stub")
        ctx = _session()
        result = engine.integrate_alignment(
            aligned=_aligned(),
            session=ctx,
            trust=_trust_state(ctx),
            envelope=env,
            propagation=_propagation(),
            momentum=_momentum(ctx),
            understanding=_understanding(ctx),
        )

        def _search(obj, seen=None):
            if seen is None:
                seen = set()
            obj_id = id(obj)
            if obj_id in seen:
                return False
            seen.add(obj_id)
            if isinstance(obj, str):
                return marker in obj
            if hasattr(obj, "__dataclass_fields__"):
                return any(
                    _search(getattr(obj, f.name), seen)
                    for f in obj.__dataclass_fields__.values()
                )
            if isinstance(obj, (list, tuple, set, frozenset)):
                return any(_search(x, seen) for x in obj)
            if isinstance(obj, dict):
                return any(_search(v, seen) for v in obj.values())
            return False

        assert not _search(result), (
            "marker in EnvelopeState.raw_text leaked into result"
        )

    def test_marker_in_rough_intention_does_not_leak(self):
        marker = "ZxYxQwertUniqueMarker9999"
        env = _envelope(raw_text="stub", rough_intention=marker)
        ctx = _session()
        result = engine.integrate_alignment(
            aligned=_aligned(),
            session=ctx,
            trust=_trust_state(ctx),
            envelope=env,
            propagation=_propagation(),
            momentum=_momentum(ctx),
            understanding=_understanding(ctx),
        )

        def _search(obj, seen=None):
            if seen is None:
                seen = set()
            obj_id = id(obj)
            if obj_id in seen:
                return False
            seen.add(obj_id)
            if isinstance(obj, str):
                return marker in obj
            if hasattr(obj, "__dataclass_fields__"):
                return any(
                    _search(getattr(obj, f.name), seen)
                    for f in obj.__dataclass_fields__.values()
                )
            if isinstance(obj, (list, tuple, set, frozenset)):
                return any(_search(x, seen) for x in obj)
            if isinstance(obj, dict):
                return any(_search(v, seen) for v in obj.values())
            return False

        assert not _search(result), (
            "marker in EnvelopeState.rough_intention leaked into result"
        )


# ===========================================================================
# N. Source-code invariants
# ===========================================================================
class TestSourceCodeInvariants:
    def _src(self, mod) -> str:
        return inspect.getsource(mod)

    def test_no_llm_imports_in_engine(self):
        src = self._src(engine)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src, f"engine must not import {forbidden}"

    def test_no_llm_imports_in_schemas(self):
        src = self._src(schemas)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_imports_in_engine(self):
        src = self._src(engine)
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket",
                          "from urllib", "from http", "from requests"):
            assert forbidden not in src

    def test_no_randomness_imports_in_engine(self):
        src = self._src(engine)
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets"):
            assert forbidden not in src

    def test_no_io_in_engine(self):
        src = self._src(engine)
        for forbidden in ("open(", "Path(", "pathlib", "os.path",
                          "json.load", "json.dump", "subprocess",
                          "exec(", "eval("):
            assert forbidden not in src

    def test_no_send_patterns_in_engine(self):
        """Invariant 8: integration is advisory only — no send patterns."""
        src = self._src(engine)
        for forbidden in (".post(", ".put(", ".send(", "urlopen(",
                          "requests.", "smtplib"):
            assert forbidden not in src

    def test_v1_does_not_branch_on_reserved_inputs(self):
        """Invariant 12: v1 doesn't access fields off the four reserved
        inputs (session, trust, envelope, propagation).

        We scan engine source for any attribute access of the form
        `session.<x>`, `trust.<x>`, `envelope.<x>`, `propagation.<x>`.
        The `_ = name` lines are bare references, not field access.
        """
        src = self._src(engine)
        for reserved in ("session.", "trust.", "envelope.", "propagation."):
            assert reserved not in src, (
                f"engine v1 must not branch on reserved input fields: "
                f"found {reserved!r}"
            )


# ===========================================================================
# O. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_schemas_exports(self):
        for name in (
            "SurfaceHaltLevel", "SurfaceDirectiveType",
            "SurfaceDirective", "IntegratedAlignmentResult",
            "CANONICAL_DIRECTIVE_VALUES",
            "assert_fea_integration_privacy_contract",
            "assert_fea_integration_field_sets_canonical",
            "assert_surface_halt_levels_canonical",
            "assert_surface_directive_types_canonical",
            "assert_canonical_directive_values",
            "is_canonical_directive_value",
        ):
            assert hasattr(schemas, name), f"missing in schemas: {name}"

    def test_engine_exports(self):
        for name in ("integrate_alignment",):
            assert hasattr(engine, name)
            assert callable(getattr(engine, name))


# ===========================================================================
# P. Invariant cross-checks
# ===========================================================================
class TestInvariantCrossChecks:
    def test_invariant_1_fea_safety_authoritative(self):
        """safe_for_surface == False ⇒ halt_level == HARD, always."""
        for score in (0.0, 0.39, 0.4, 0.5, 0.9, 1.0):
            for hard_stops in (0, 1, 2):
                ctx = _session(hard_stops=hard_stops)
                aligned = _aligned(safe_for_surface=False,
                                   alignment_score=score)
                r = _integrate(aligned, ctx=ctx)
                assert r.halt_level == schemas.SurfaceHaltLevel.HARD

    def test_invariant_2_low_alignment_escalates(self):
        """alignment_score < 0.4 ⇒ halt_level ∈ {SOFT, HARD}."""
        for safe in (True, False):
            for score in (0.0, 0.1, 0.39):
                aligned = _aligned(safe_for_surface=safe,
                                   alignment_score=score)
                r = _integrate(aligned)
                assert r.halt_level in (
                    schemas.SurfaceHaltLevel.SOFT,
                    schemas.SurfaceHaltLevel.HARD,
                )

    def test_invariant_3_delta_in_unit_interval(self):
        for safe in (True, False):
            for score in (0.0, 0.4, 0.9):
                for stops in (0, 1, 5, 100):
                    ctx = _session(hard_stops=stops)
                    aligned = _aligned(safe_for_surface=safe,
                                       alignment_score=score)
                    r = _integrate(aligned, ctx=ctx)
                    assert 0.0 <= r.trust_state_delta <= 1.0

    def test_invariant_4_aligned_expression_passthrough(self):
        """For every reachable input, aligned_expression is the same
        object as the input."""
        for safe in (True, False):
            for score in (0.0, 0.5, 1.0):
                aligned = _aligned(safe_for_surface=safe,
                                   alignment_score=score)
                r = _integrate(aligned)
                assert r.aligned_expression is aligned

    def test_invariant_7_trust_never_overrides_fea(self):
        """No Ambient-Trust state can make a HARD halt LESS severe."""
        aligned = _aligned(safe_for_surface=False, alignment_score=0.9)
        for ability in range(4):
            for comprehension in range(4):
                for stops in (0, 1, 2):
                    for ack in (True, False):
                        ctx = _session(
                            ability=ability, comprehension=comprehension,
                            hard_stops=stops, ack=ack,
                        )
                        r = _integrate(aligned, ctx=ctx)
                        assert r.halt_level == schemas.SurfaceHaltLevel.HARD

    def test_invariant_9_all_directive_values_canonical(self):
        """Every directive emitted is in the canonical set."""
        ctx = _session(ability=3, comprehension=1, hard_stops=1)
        aligned = _aligned(
            safe_for_surface=False, steps=(
                _step(fea_schemas.ReframeType.TEMPORAL),
                _step(fea_schemas.ReframeType.MEANING),
            ),
            pressure_delta=1, agency_delta=1,
        )
        r = _integrate(aligned, ctx=ctx)
        for d in r.surface_directives:
            assert schemas.is_canonical_directive_value(
                d.directive_type, d.value,
            )

    def test_invariant_10_determinism(self):
        ctx = _session(ability=3, comprehension=1, hard_stops=1)
        aligned = _aligned(
            safe_for_surface=False, alignment_score=0.2,
            steps=(_step(fea_schemas.ReframeType.MEANING),),
            pressure_delta=1, agency_delta=1,
        )
        r1 = _integrate(aligned, ctx=ctx)
        r2 = _integrate(aligned, ctx=ctx)
        assert r1 == r2


# ===========================================================================
# Q. Constants lock
# ===========================================================================
class TestConstantLocks:
    def test_soft_halt_score_threshold(self):
        assert engine._SOFT_HALT_SCORE_THRESHOLD == 0.4

    def test_momentum_bonus(self):
        assert engine._TRUST_DELTA_MOMENTUM_BONUS == 0.1

    def test_halt_penalty(self):
        assert engine._TRUST_DELTA_HALT_PENALTY == 0.1


# ===========================================================================
# R. End-to-end with real FEA engine (smoke test of the wiring)
# ===========================================================================
class TestEndToEndWithRealFEA:
    """These tests build the AlignedExpression via the real FEA engine
    (not the test-only _aligned() helper) to confirm the integration
    layer plays nicely with actual FEA output shapes."""

    def test_real_fea_output_safe_path(self):
        """LOW pressure + curvature → SCALE → safe FEA output."""
        snapshot = fea_schemas.EmotionalSnapshot(
            pressure_level=PressureLevel.LOW,
            intensity=IntensityLevel.LOW,
            valence=Valence.NEUTRAL,
            temporal_linked=False, anchor_present=False,
        )
        geometry = fea_schemas.EmotionalGeometry(
            curvature=True, torsion=False, shear=False, boundary=False,
            stance_self=0.1, stance_other=0.1, stance_world=0.1,
            pressure_gradient=0.1,
        )
        intention = fea_schemas.EmotionalIntention(
            target_state="be heard",
            regulatory_goal=fea_schemas.RegulationGoal.EXPRESS,
            relational_posture=fea_schemas.RelationalPosture.CONNECT,
            meaning_need=fea_schemas.MeaningNeed.NONE,
        )
        aligned = fea_engine.align_expression(
            snapshot, geometry, intention, ExpressionPrimitive.GEOMETRY,
        )
        r = _integrate(aligned)
        assert r.aligned_expression is aligned
        assert r.halt_level == schemas.SurfaceHaltLevel.NONE
        # FEA emits SCALE → pressure_delta = -1 → no PACE/slow directive
        types = [d.directive_type for d in r.surface_directives]
        assert schemas.SurfaceDirectiveType.PACE not in types
