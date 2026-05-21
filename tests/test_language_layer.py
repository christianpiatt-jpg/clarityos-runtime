"""
Tests for the ClarityOS Language Layer.

Two layers of testing:
    1. Structural — schemas / enums / mapping / invariants.
    2. Behavioral — `select_expression_plan` with concrete contexts
       producing the expected `ExpressionPlan`.

The PSE is pure and deterministic, so behavioral tests assert
byte-equal returns. No mocking required — no I/O exists to mock.
"""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

import language_schemas as ls
import primitive_selection_engine as pse

from azimuth import IntensityLevel, IntentionClass, PressureLevel, Valence
from orchestrator_schemas import (
    ActorKind, AuthorizationTier, ConstitutionalConstraint,
    DriftAxis, DriftState, EnforcementMode, GeometryProfile,
    IdentityProfile, PropagationState, Severity, SovereigntyLevel,
)


# ===========================================================================
# Fixture builders
# ===========================================================================
def _envelope(
    pressure: PressureLevel = PressureLevel.LOW,
    valence:  Valence       = Valence.NEUTRAL,
    intensity: IntensityLevel = IntensityLevel.LOW,
    intention_class: IntentionClass = IntentionClass.OBSERVATION,
) -> ls.EnvelopeSnapshot:
    return ls.EnvelopeSnapshot(
        pressure_level=pressure,
        valence=valence,
        intensity=intensity,
        intention_class=intention_class,
    )


def _drift(in_bounds: bool = True, magnitude: float = 0.1) -> DriftState:
    return DriftState(
        axis=DriftAxis.INTENT,
        magnitude=magnitude,
        direction="stable",
        baseline_anchor="session_start",
        in_bounds=in_bounds,
        measured_at=datetime.now(timezone.utc),
    )


def _geometry(
    pressure_load: float = 0.2,
    stability_score: float = 0.85,
) -> GeometryProfile:
    return GeometryProfile(
        depth=1, breadth=1,
        pressure_load=pressure_load,
        stability_score=stability_score,
        captured_at=datetime.now(timezone.utc),
    )


def _identity(
    actor: str = "alice",
    actor_kind: ActorKind = ActorKind.USER,
    tier: AuthorizationTier = AuthorizationTier.EXECUTE,
) -> IdentityProfile:
    return IdentityProfile(
        actor=actor,
        actor_kind=actor_kind,
        sovereignty_level=SovereigntyLevel.USER_OWNED,
        authorization_tier=tier,
        session_id="sess_local",
    )


def _constraint() -> ConstitutionalConstraint:
    return ConstitutionalConstraint(
        rule_id="C1", statement="x", severity=Severity.ADVISORY,
        enforcement=EnforcementMode.ALLOW_WITH_WARNING,
    )


def _propagation(
    pressure_load: float = 0.2,
    stability_score: float = 0.85,
) -> PropagationState:
    return PropagationState(
        from_step="s0", to_step="s1",
        active_constraints=(_constraint(),),
        drift_state=_drift(),
        geometry_profile=_geometry(pressure_load, stability_score),
        identity_profile=_identity(),
        invariants_preserved=("drift_within_bounds",),
    )


def _context(
    *,
    pressure: PressureLevel = PressureLevel.LOW,
    drift_in_bounds: bool = True,
    geometry_pressure_load: float = 0.2,
    geometry_stability: float = 0.85,
    mode: ls.ConversationMode = ls.ConversationMode.OPERATOR,
    actor_kind: ActorKind = ActorKind.USER,
    tier: AuthorizationTier = AuthorizationTier.EXECUTE,
    propagation: "PropagationState | None" = None,
    last_primitive: "ls.ExpressionPrimitive | None" = None,
) -> ls.LanguageContext:
    return ls.LanguageContext(
        envelope=_envelope(pressure=pressure),
        drift_state=_drift(in_bounds=drift_in_bounds),
        geometry_profile=_geometry(geometry_pressure_load, geometry_stability),
        identity_profile=_identity(actor_kind=actor_kind, tier=tier),
        conversation_mode=mode,
        propagation_state=propagation,
        last_primitive=last_primitive,
    )


# ===========================================================================
# A. Structural — enums
# ===========================================================================
class TestEnums:
    def test_conversation_mode_values(self):
        assert {v.value for v in ls.ConversationMode} == {
            "operator", "exploratory", "emotional", "structural", "decision",
        }

    def test_expression_primitive_values(self):
        assert {v.value for v in ls.ExpressionPrimitive} == {
            "motion", "geometry", "hydronics", "analogy",
        }

    def test_tone_profile_values(self):
        assert {v.value for v in ls.ToneProfile} == {
            "stable", "direct", "softened", "expansive",
        }

    def test_structure_profile_values(self):
        assert {v.value for v in ls.StructureProfile} == {
            "highly_structured", "moderate", "minimal",
        }

    def test_length_profile_values(self):
        assert {v.value for v in ls.LengthProfile} == {
            "short", "medium", "long",
        }


# ===========================================================================
# B. Base-primitive derivation contract
# ===========================================================================
class TestBasePrimitiveDerivation:
    def test_base_primitives_set_is_ten_letters(self):
        assert set(ls.BASE_PRIMITIVES) == set("CDLATBGIPS")
        assert len(ls.BASE_PRIMITIVES) == 10

    def test_motion_derivation(self):
        assert ls.EXPRESSION_PRIMITIVE_DERIVATION[
            ls.ExpressionPrimitive.MOTION
        ] == ("D", "T", "B", "P")

    def test_geometry_derivation(self):
        assert ls.EXPRESSION_PRIMITIVE_DERIVATION[
            ls.ExpressionPrimitive.GEOMETRY
        ] == ("G", "D", "I")

    def test_hydronics_derivation(self):
        assert ls.EXPRESSION_PRIMITIVE_DERIVATION[
            ls.ExpressionPrimitive.HYDRONICS
        ] == ("L", "D", "B", "P")

    def test_analogy_derivation(self):
        assert ls.EXPRESSION_PRIMITIVE_DERIVATION[
            ls.ExpressionPrimitive.ANALOGY
        ] == ("P", "S", "I")

    def test_every_primitive_has_derivation(self):
        for primitive in ls.ExpressionPrimitive:
            assert primitive in ls.EXPRESSION_PRIMITIVE_DERIVATION

    def test_every_derivation_is_subset_of_base(self):
        base = set(ls.BASE_PRIMITIVES)
        for primitive, derived in ls.EXPRESSION_PRIMITIVE_DERIVATION.items():
            non_base = set(derived) - base
            assert not non_base, f"{primitive.value} has non-base: {non_base}"

    def test_every_derivation_is_non_empty(self):
        for primitive, derived in ls.EXPRESSION_PRIMITIVE_DERIVATION.items():
            assert len(derived) > 0

    def test_runtime_guard_passes(self):
        ls.assert_derivation_contract()  # must not raise


# ===========================================================================
# C. EnvelopeSnapshot — privacy boundary
# ===========================================================================
class TestEnvelopeSnapshot:
    def test_instantiable(self):
        env = _envelope()
        assert env.pressure_level == PressureLevel.LOW

    def test_frozen(self):
        env = _envelope()
        with pytest.raises(FrozenInstanceError):
            env.pressure_level = PressureLevel.HIGH  # type: ignore[misc]

    def test_no_raw_text_field(self):
        """EnvelopeSnapshot must NOT carry raw_text (privacy)."""
        assert "raw_text" not in ls.EnvelopeSnapshot.__dataclass_fields__

    def test_no_envelope_id_field(self):
        assert "envelope_id" not in ls.EnvelopeSnapshot.__dataclass_fields__

    def test_only_four_documented_fields(self):
        expected = {"pressure_level", "valence", "intensity", "intention_class"}
        assert set(ls.EnvelopeSnapshot.__dataclass_fields__.keys()) == expected


# ===========================================================================
# D. LanguageContext + ExpressionPlan
# ===========================================================================
class TestLanguageContext:
    def test_instantiable(self):
        ctx = _context()
        assert ctx.conversation_mode == ls.ConversationMode.OPERATOR

    def test_frozen(self):
        ctx = _context()
        with pytest.raises(FrozenInstanceError):
            ctx.conversation_mode = ls.ConversationMode.EMOTIONAL  # type: ignore[misc]

    def test_optional_fields_default_none(self):
        ctx = _context()
        assert ctx.propagation_state is None
        assert ctx.last_primitive is None


class TestExpressionPlan:
    def test_instantiable(self):
        plan = ls.ExpressionPlan(
            primitive=ls.ExpressionPrimitive.GEOMETRY,
            tone=ls.ToneProfile.DIRECT,
            structure=ls.StructureProfile.HIGHLY_STRUCTURED,
            length=ls.LengthProfile.MEDIUM,
        )
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY
        assert plan.rationale == ""  # default

    def test_frozen(self):
        plan = ls.ExpressionPlan(
            primitive=ls.ExpressionPrimitive.GEOMETRY,
            tone=ls.ToneProfile.DIRECT,
            structure=ls.StructureProfile.HIGHLY_STRUCTURED,
            length=ls.LengthProfile.MEDIUM,
        )
        with pytest.raises(FrozenInstanceError):
            plan.primitive = ls.ExpressionPrimitive.MOTION  # type: ignore[misc]


# ===========================================================================
# E. Behavioral — pressure overrides (Rule 1)
# ===========================================================================
class TestPressureOverrides:
    def test_high_pressure_forces_hydronics(self):
        ctx = _context(pressure=PressureLevel.HIGH,
                       mode=ls.ConversationMode.OPERATOR)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS

    def test_critical_pressure_forces_hydronics(self):
        ctx = _context(pressure=PressureLevel.CRITICAL,
                       mode=ls.ConversationMode.STRUCTURAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS

    def test_high_pressure_forces_stable_tone(self):
        """Invariant #9 — no emotional escalation."""
        ctx = _context(pressure=PressureLevel.HIGH,
                       mode=ls.ConversationMode.OPERATOR)
        plan = pse.select_expression_plan(ctx)
        assert plan.tone == ls.ToneProfile.STABLE

    def test_high_pressure_overrides_decision_mode(self):
        ctx = _context(pressure=PressureLevel.HIGH,
                       mode=ls.ConversationMode.DECISION)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS
        assert plan.tone == ls.ToneProfile.STABLE

    def test_medium_pressure_does_not_override(self):
        ctx = _context(pressure=PressureLevel.MEDIUM,
                       mode=ls.ConversationMode.STRUCTURAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY  # mode wins

    def test_low_pressure_does_not_override(self):
        ctx = _context(pressure=PressureLevel.LOW,
                       mode=ls.ConversationMode.EMOTIONAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS  # mode default


# ===========================================================================
# F. Behavioral — drift override (Rule 2)
# ===========================================================================
class TestDriftOverride:
    def test_out_of_bounds_forces_analogy(self):
        ctx = _context(drift_in_bounds=False,
                       mode=ls.ConversationMode.STRUCTURAL)  # would normally be GEOMETRY
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.ANALOGY

    def test_out_of_bounds_overrides_decision_mode(self):
        ctx = _context(drift_in_bounds=False,
                       mode=ls.ConversationMode.DECISION)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.ANALOGY

    def test_in_bounds_lets_mode_win(self):
        ctx = _context(drift_in_bounds=True,
                       mode=ls.ConversationMode.STRUCTURAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY

    def test_pressure_takes_priority_over_drift(self):
        """Rule 1 has higher priority than Rule 2."""
        ctx = _context(pressure=PressureLevel.HIGH,
                       drift_in_bounds=False,
                       mode=ls.ConversationMode.OPERATOR)
        plan = pse.select_expression_plan(ctx)
        # HYDRONICS wins (rule 1) over ANALOGY (rule 2).
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS


# ===========================================================================
# G. Behavioral — mode-driven selection (Rules 3-7)
# ===========================================================================
class TestModeDrivenSelection:
    def test_structural_mode_to_geometry(self):
        ctx = _context(mode=ls.ConversationMode.STRUCTURAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY

    def test_decision_mode_to_motion(self):
        ctx = _context(mode=ls.ConversationMode.DECISION)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.MOTION

    def test_operator_mode_with_execute_user_to_geometry(self):
        ctx = _context(
            mode=ls.ConversationMode.OPERATOR,
            actor_kind=ActorKind.USER,
            tier=AuthorizationTier.EXECUTE,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY

    def test_operator_mode_with_agent_to_motion(self):
        """Operator mode + non-EXECUTE identity → MOTION (tie-break)."""
        ctx = _context(
            mode=ls.ConversationMode.OPERATOR,
            actor_kind=ActorKind.AGENT,
            tier=AuthorizationTier.PROPOSE,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.MOTION

    def test_exploratory_mode_to_analogy(self):
        ctx = _context(mode=ls.ConversationMode.EXPLORATORY)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.ANALOGY

    def test_emotional_mode_to_hydronics(self):
        ctx = _context(mode=ls.ConversationMode.EMOTIONAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS


# ===========================================================================
# H. Behavioral — tone / structure / length
# ===========================================================================
class TestToneStructureLength:
    def test_high_pressure_tone_structure_length(self):
        ctx = _context(pressure=PressureLevel.HIGH,
                       mode=ls.ConversationMode.EMOTIONAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.tone      == ls.ToneProfile.STABLE
        assert plan.structure == ls.StructureProfile.HIGHLY_STRUCTURED
        assert plan.length    == ls.LengthProfile.MEDIUM

    def test_operator_tone_structure_length(self):
        ctx = _context(mode=ls.ConversationMode.OPERATOR)
        plan = pse.select_expression_plan(ctx)
        assert plan.tone      == ls.ToneProfile.DIRECT
        assert plan.structure == ls.StructureProfile.HIGHLY_STRUCTURED
        assert plan.length    == ls.LengthProfile.MEDIUM

    def test_exploratory_tone_structure_length(self):
        ctx = _context(mode=ls.ConversationMode.EXPLORATORY)
        plan = pse.select_expression_plan(ctx)
        assert plan.tone      == ls.ToneProfile.EXPANSIVE
        assert plan.structure == ls.StructureProfile.MODERATE
        assert plan.length    == ls.LengthProfile.LONG

    def test_emotional_tone_structure_length(self):
        ctx = _context(mode=ls.ConversationMode.EMOTIONAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.tone      == ls.ToneProfile.SOFTENED
        assert plan.structure == ls.StructureProfile.MODERATE
        assert plan.length    == ls.LengthProfile.MEDIUM

    def test_decision_tone_structure_length(self):
        ctx = _context(mode=ls.ConversationMode.DECISION)
        plan = pse.select_expression_plan(ctx)
        assert plan.tone      == ls.ToneProfile.DIRECT
        assert plan.structure == ls.StructureProfile.HIGHLY_STRUCTURED
        assert plan.length    == ls.LengthProfile.SHORT

    def test_structural_tone_structure_length(self):
        ctx = _context(mode=ls.ConversationMode.STRUCTURAL)
        plan = pse.select_expression_plan(ctx)
        assert plan.tone      == ls.ToneProfile.DIRECT
        assert plan.structure == ls.StructureProfile.HIGHLY_STRUCTURED
        assert plan.length    == ls.LengthProfile.MEDIUM


# ===========================================================================
# I. Behavioral — whiplash prevention
# ===========================================================================
class TestWhiplashPrevention:
    def test_no_whiplash_when_geometry_stable(self):
        """Last MOTION + agent-mode OPERATOR + stable geometry → stay MOTION
        (would naively flip to GEOMETRY since operator default for USER+EXECUTE
        is GEOMETRY, but identity here is AGENT so naive pick is MOTION anyway).
        Reframe: last GEOMETRY + agent-mode OPERATOR → stay GEOMETRY since
        no meaningful change."""
        # Set up: last_primitive=GEOMETRY, current naive selection would be
        # MOTION (because identity is AGENT in OPERATOR mode).
        prop = _propagation(pressure_load=0.2, stability_score=0.85)
        ctx = _context(
            mode=ls.ConversationMode.OPERATOR,
            actor_kind=ActorKind.AGENT,
            tier=AuthorizationTier.PROPOSE,
            geometry_pressure_load=0.2,
            geometry_stability=0.85,
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.GEOMETRY,  # last turn used GEOMETRY
        )
        plan = pse.select_expression_plan(ctx)
        # Naive selection for OPERATOR + AGENT = MOTION, but whiplash check
        # should keep GEOMETRY because geometry hasn't changed meaningfully.
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY

    def test_whiplash_bypassed_by_meaningful_pressure_change(self):
        """Geometry pressure_load shifted >= 0.2 → switch allowed."""
        prop = _propagation(pressure_load=0.2, stability_score=0.85)
        ctx = _context(
            mode=ls.ConversationMode.OPERATOR,
            actor_kind=ActorKind.AGENT,
            tier=AuthorizationTier.PROPOSE,
            geometry_pressure_load=0.5,  # 0.3 delta — meaningful
            geometry_stability=0.85,
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.GEOMETRY,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.MOTION

    def test_whiplash_bypassed_by_stability_change(self):
        prop = _propagation(pressure_load=0.2, stability_score=0.85)
        ctx = _context(
            mode=ls.ConversationMode.OPERATOR,
            actor_kind=ActorKind.AGENT,
            tier=AuthorizationTier.PROPOSE,
            geometry_pressure_load=0.2,
            geometry_stability=0.5,  # 0.35 delta — meaningful
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.GEOMETRY,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.MOTION

    def test_whiplash_check_skipped_with_no_propagation(self):
        ctx = _context(
            mode=ls.ConversationMode.OPERATOR,
            actor_kind=ActorKind.AGENT,
            tier=AuthorizationTier.PROPOSE,
            propagation=None,
            last_primitive=ls.ExpressionPrimitive.GEOMETRY,
        )
        plan = pse.select_expression_plan(ctx)
        # No propagation → switch is allowed.
        assert plan.primitive == ls.ExpressionPrimitive.MOTION

    def test_high_pressure_bypasses_whiplash(self):
        """Hard override (rule 1) wins regardless of whiplash."""
        prop = _propagation(pressure_load=0.2, stability_score=0.85)
        ctx = _context(
            pressure=PressureLevel.HIGH,
            mode=ls.ConversationMode.OPERATOR,
            geometry_pressure_load=0.2,
            geometry_stability=0.85,
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.GEOMETRY,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS

    def test_drift_override_bypasses_whiplash(self):
        prop = _propagation(pressure_load=0.2, stability_score=0.85)
        ctx = _context(
            drift_in_bounds=False,
            mode=ls.ConversationMode.OPERATOR,
            geometry_pressure_load=0.2,
            geometry_stability=0.85,
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.GEOMETRY,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.ANALOGY

    def test_structural_mode_strictly_requires_geometry(self):
        """Even with whiplash continuity, STRUCTURAL forces GEOMETRY."""
        prop = _propagation(pressure_load=0.2, stability_score=0.85)
        ctx = _context(
            mode=ls.ConversationMode.STRUCTURAL,
            geometry_pressure_load=0.2,
            geometry_stability=0.85,
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.MOTION,  # last used MOTION
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY

    def test_decision_mode_strictly_requires_motion(self):
        prop = _propagation(pressure_load=0.2, stability_score=0.85)
        ctx = _context(
            mode=ls.ConversationMode.DECISION,
            geometry_pressure_load=0.2,
            geometry_stability=0.85,
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.GEOMETRY,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.MOTION

    def test_same_primitive_continuity_is_not_whiplash(self):
        prop = _propagation()
        ctx = _context(
            mode=ls.ConversationMode.STRUCTURAL,
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.GEOMETRY,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY


# ===========================================================================
# J. Determinism (Invariant #8)
# ===========================================================================
class TestDeterminism:
    def test_same_context_same_plan(self):
        ctx = _context(
            mode=ls.ConversationMode.OPERATOR,
            pressure=PressureLevel.MEDIUM,
        )
        plan1 = pse.select_expression_plan(ctx)
        plan2 = pse.select_expression_plan(ctx)
        assert plan1 == plan2

    def test_multiple_calls_byte_equal(self):
        ctx = _context(mode=ls.ConversationMode.EMOTIONAL)
        plans = [pse.select_expression_plan(ctx) for _ in range(5)]
        assert all(p == plans[0] for p in plans)

    def test_different_modes_different_plans(self):
        ctx_op = _context(mode=ls.ConversationMode.OPERATOR)
        ctx_em = _context(mode=ls.ConversationMode.EMOTIONAL)
        assert pse.select_expression_plan(ctx_op) != pse.select_expression_plan(ctx_em)

    def test_rationale_is_deterministic(self):
        ctx = _context(mode=ls.ConversationMode.STRUCTURAL)
        r1 = pse.select_expression_plan(ctx).rationale
        r2 = pse.select_expression_plan(ctx).rationale
        assert r1 == r2
        assert r1  # non-empty


# ===========================================================================
# K. Invariant enforcement — source-code inspection
# ===========================================================================
class TestSourceCodeInvariants:
    def _src(self, mod) -> str:
        return inspect.getsource(mod)

    def test_no_llm_imports_in_pse(self):
        src = self._src(pse)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src, f"PSE must not import {forbidden}"

    def test_no_llm_imports_in_schemas(self):
        src = self._src(ls)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_imports_in_pse(self):
        src = self._src(pse)
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket"):
            assert forbidden not in src

    def test_no_randomness_imports_in_pse(self):
        src = self._src(pse)
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets"):
            assert forbidden not in src

    def test_no_io_imports_in_pse(self):
        """No file system access in the PSE."""
        src = self._src(pse)
        for forbidden in ("open(", "Path(", "pathlib", "os.path",
                          "with open"):
            assert forbidden not in src


# ===========================================================================
# L. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_schemas_exports(self):
        for name in (
            "ConversationMode", "ExpressionPrimitive",
            "ToneProfile", "StructureProfile", "LengthProfile",
            "EnvelopeSnapshot", "LanguageContext", "ExpressionPlan",
            "BASE_PRIMITIVES", "EXPRESSION_PRIMITIVE_DERIVATION",
            "assert_derivation_contract",
        ):
            assert hasattr(ls, name), f"missing in schemas: {name}"

    def test_pse_exports_select_expression_plan(self):
        assert hasattr(pse, "select_expression_plan")
        assert callable(pse.select_expression_plan)

    def test_select_expression_plan_returns_expression_plan(self):
        ctx = _context()
        plan = pse.select_expression_plan(ctx)
        assert isinstance(plan, ls.ExpressionPlan)


# ===========================================================================
# M. Worked examples from SPEC § 8
# ===========================================================================
class TestWorkedExamples:
    def test_example_81_high_pressure_operator(self):
        ctx = _context(
            pressure=PressureLevel.HIGH,
            mode=ls.ConversationMode.OPERATOR,
            drift_in_bounds=True,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS
        assert plan.tone == ls.ToneProfile.STABLE
        assert plan.structure == ls.StructureProfile.HIGHLY_STRUCTURED
        assert plan.length == ls.LengthProfile.MEDIUM

    def test_example_82_system_analysis(self):
        ctx = _context(
            pressure=PressureLevel.LOW,
            mode=ls.ConversationMode.STRUCTURAL,
            drift_in_bounds=True,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.GEOMETRY
        assert plan.tone == ls.ToneProfile.DIRECT
        assert plan.structure == ls.StructureProfile.HIGHLY_STRUCTURED
        assert plan.length == ls.LengthProfile.MEDIUM

    def test_example_83_user_confusion_concept_bridging(self):
        ctx = _context(
            pressure=PressureLevel.MEDIUM,
            mode=ls.ConversationMode.EXPLORATORY,
            drift_in_bounds=False,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.ANALOGY
        assert plan.tone == ls.ToneProfile.EXPANSIVE
        assert plan.structure == ls.StructureProfile.MODERATE
        assert plan.length == ls.LengthProfile.LONG

    def test_example_84_decision_moment(self):
        ctx = _context(
            pressure=PressureLevel.MEDIUM,
            mode=ls.ConversationMode.DECISION,
            drift_in_bounds=True,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.MOTION
        assert plan.tone == ls.ToneProfile.DIRECT
        assert plan.structure == ls.StructureProfile.HIGHLY_STRUCTURED
        assert plan.length == ls.LengthProfile.SHORT

    def test_example_86_whiplash_bypass_on_hard_override(self):
        prop = _propagation()
        ctx = _context(
            pressure=PressureLevel.HIGH,
            mode=ls.ConversationMode.OPERATOR,
            propagation=prop,
            last_primitive=ls.ExpressionPrimitive.MOTION,
        )
        plan = pse.select_expression_plan(ctx)
        assert plan.primitive == ls.ExpressionPrimitive.HYDRONICS
        assert plan.tone == ls.ToneProfile.STABLE


# ===========================================================================
# N. Invariant cross-checks (composite)
# ===========================================================================
class TestInvariantCrossChecks:
    def test_invariant_8_determinism(self):
        """Invariant 8: same context → byte-equal plan."""
        ctx = _context(mode=ls.ConversationMode.OPERATOR)
        assert pse.select_expression_plan(ctx) == pse.select_expression_plan(ctx)

    def test_invariant_9_no_emotional_escalation(self):
        """Invariant 9: HIGH/CRITICAL pressure ⇒ STABLE tone, regardless of mode."""
        for mode in ls.ConversationMode:
            for pressure in (PressureLevel.HIGH, PressureLevel.CRITICAL):
                ctx = _context(pressure=pressure, mode=mode)
                plan = pse.select_expression_plan(ctx)
                assert plan.tone == ls.ToneProfile.STABLE, (
                    f"pressure={pressure.value}, mode={mode.value} "
                    f"yielded tone={plan.tone.value}, expected STABLE"
                )

    def test_invariant_6_drift_reduction(self):
        """Invariant 6: drift out of bounds ⇒ ANALOGY (clarity bridge)."""
        for mode in ls.ConversationMode:
            # Skip the high-pressure pre-empt
            ctx = _context(
                pressure=PressureLevel.LOW,
                drift_in_bounds=False,
                mode=mode,
            )
            plan = pse.select_expression_plan(ctx)
            assert plan.primitive == ls.ExpressionPrimitive.ANALOGY, (
                f"mode={mode.value} did not produce ANALOGY on drift override"
            )

    def test_invariant_1_no_new_base_primitives(self):
        """Invariant 1: every expression primitive maps to a subset of
        the 10 base primitives."""
        base = set(ls.BASE_PRIMITIVES)
        for primitive, derivation in ls.EXPRESSION_PRIMITIVE_DERIVATION.items():
            assert set(derivation).issubset(base)

    def test_invariant_4_no_auto_send(self):
        """Invariant 4: PSE only returns a plan. No side effects, no calls.

        Structurally enforced: source contains no calls to any send /
        post / write / upload patterns.
        """
        src = inspect.getsource(pse)
        for forbidden in (".post(", ".put(", ".send(",
                          "urlopen(", "requests.", "smtplib"):
            assert forbidden not in src

    def test_invariant_3_no_io(self):
        """Invariant 3: no I/O anywhere in the PSE."""
        src = inspect.getsource(pse)
        for forbidden in ("open(", "json.dump", "json.load",
                          "fetch(", "subprocess", "exec("):
            assert forbidden not in src
