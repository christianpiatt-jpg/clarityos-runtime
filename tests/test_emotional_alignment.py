"""
Tests for the Emotional Reality Alignment (ERA) module.

Two layers:
    1. Structural — enums / schemas / privacy contract / module-load guards.
    2. Behavioral — build_reframe_plan / compute_alignment_score /
       align_expression against concrete fixtures producing the
       expected outputs.

The engine is pure and deterministic, so behavioral tests assert
byte-equal returns. No mocking required — no I/O exists to mock.
"""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError

import pytest

import emotional_alignment_engine as engine
import emotional_alignment_schemas as schemas

from azimuth import IntensityLevel, PressureLevel, Valence
from language_schemas import ExpressionPrimitive


# ===========================================================================
# Fixture builders — every test composes its own snapshot/geometry/intention
# ===========================================================================
def _snapshot(
    *,
    pressure_level: PressureLevel = PressureLevel.LOW,
    intensity: IntensityLevel = IntensityLevel.LOW,
    valence: Valence = Valence.NEUTRAL,
    temporal_linked: bool = False,
    anchor_present: bool = False,
) -> schemas.EmotionalSnapshot:
    return schemas.EmotionalSnapshot(
        pressure_level=pressure_level,
        intensity=intensity,
        valence=valence,
        temporal_linked=temporal_linked,
        anchor_present=anchor_present,
    )


def _geometry(
    *,
    curvature: bool = False,
    torsion: bool = False,
    shear: bool = False,
    boundary: bool = False,
    stance_self: float = 0.2,
    stance_other: float = 0.2,
    stance_world: float = 0.2,
    pressure_gradient: float = 0.2,
) -> schemas.EmotionalGeometry:
    return schemas.EmotionalGeometry(
        curvature=curvature,
        torsion=torsion,
        shear=shear,
        boundary=boundary,
        stance_self=stance_self,
        stance_other=stance_other,
        stance_world=stance_world,
        pressure_gradient=pressure_gradient,
    )


def _intention(
    *,
    target_state: str = "be heard",
    regulatory_goal: schemas.RegulationGoal = schemas.RegulationGoal.EXPRESS,
    relational_posture: schemas.RelationalPosture = schemas.RelationalPosture.CONNECT,
    meaning_need: schemas.MeaningNeed = schemas.MeaningNeed.NONE,
) -> schemas.EmotionalIntention:
    return schemas.EmotionalIntention(
        target_state=target_state,
        regulatory_goal=regulatory_goal,
        relational_posture=relational_posture,
        meaning_need=meaning_need,
    )


def _step_types(plan: schemas.ReframePlan) -> frozenset:
    return frozenset(s.reframe_type for s in plan.steps)


# ===========================================================================
# A. Enums
# ===========================================================================
class TestEnums:
    def test_reframe_type_values(self):
        assert {v.value for v in schemas.ReframeType} == {
            "label", "temporal", "role", "scale",
            "agency", "meaning", "none",
        }

    def test_regulation_goal_values(self):
        assert {v.value for v in schemas.RegulationGoal} == {
            "contain", "express", "transform",
        }

    def test_relational_posture_values(self):
        assert {v.value for v in schemas.RelationalPosture} == {
            "connect", "separate", "defend", "submit",
        }

    def test_meaning_need_values(self):
        assert {v.value for v in schemas.MeaningNeed} == {
            "clarify", "validate", "reframe", "none",
        }


# ===========================================================================
# B. Schemas — frozen + instantiable
# ===========================================================================
class TestEmotionalSnapshot:
    def test_instantiable(self):
        s = _snapshot()
        assert s.pressure_level == PressureLevel.LOW

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises(FrozenInstanceError):
            s.pressure_level = PressureLevel.HIGH  # type: ignore[misc]


class TestEmotionalGeometry:
    def test_instantiable(self):
        g = _geometry()
        assert g.curvature is False

    def test_frozen(self):
        g = _geometry()
        with pytest.raises(FrozenInstanceError):
            g.curvature = True  # type: ignore[misc]


class TestEmotionalIntention:
    def test_instantiable(self):
        i = _intention()
        assert i.regulatory_goal == schemas.RegulationGoal.EXPRESS

    def test_frozen(self):
        i = _intention()
        with pytest.raises(FrozenInstanceError):
            i.regulatory_goal = schemas.RegulationGoal.CONTAIN  # type: ignore[misc]


class TestReframeStep:
    def test_instantiable(self):
        s = schemas.ReframeStep(
            reframe_type=schemas.ReframeType.LABEL,
            rationale="x",
        )
        assert s.reframe_type == schemas.ReframeType.LABEL

    def test_frozen(self):
        s = schemas.ReframeStep(
            reframe_type=schemas.ReframeType.NONE, rationale="x",
        )
        with pytest.raises(FrozenInstanceError):
            s.rationale = "y"  # type: ignore[misc]


class TestReframePlan:
    def test_instantiable(self):
        p = schemas.ReframePlan(
            steps=(schemas.ReframeStep(
                reframe_type=schemas.ReframeType.NONE, rationale="x",
            ),),
            primitive=ExpressionPrimitive.GEOMETRY,
            expected_pressure_delta=0,
            expected_agency_delta=0,
        )
        assert p.primitive == ExpressionPrimitive.GEOMETRY

    def test_frozen(self):
        p = schemas.ReframePlan(
            steps=(), primitive=ExpressionPrimitive.GEOMETRY,
            expected_pressure_delta=0, expected_agency_delta=0,
        )
        with pytest.raises(FrozenInstanceError):
            p.expected_pressure_delta = 1  # type: ignore[misc]


class TestAlignedExpression:
    def test_instantiable(self):
        plan = schemas.ReframePlan(
            steps=(), primitive=ExpressionPrimitive.GEOMETRY,
            expected_pressure_delta=0, expected_agency_delta=0,
        )
        a = schemas.AlignedExpression(
            plan=plan, alignment_score=0.5,
            internal_relator_preserved=True, safe_for_surface=True,
        )
        assert a.alignment_score == 0.5

    def test_frozen(self):
        plan = schemas.ReframePlan(
            steps=(), primitive=ExpressionPrimitive.GEOMETRY,
            expected_pressure_delta=0, expected_agency_delta=0,
        )
        a = schemas.AlignedExpression(
            plan=plan, alignment_score=0.5,
            internal_relator_preserved=True, safe_for_surface=True,
        )
        with pytest.raises(FrozenInstanceError):
            a.alignment_score = 0.7  # type: ignore[misc]


# ===========================================================================
# C. Privacy contract — no forbidden fields in any ERA type
# ===========================================================================
class TestPrivacyContract:
    @pytest.mark.parametrize("cls_name", [
        "ReframeStep", "ReframePlan", "AlignedExpression",
    ])
    @pytest.mark.parametrize("forbidden", [
        "text", "raw", "raw_text",
        "user", "user_id", "id",
        "name", "names", "email",
        "session", "session_id", "identity",
        "envelope_id", "author", "actor",
    ])
    def test_no_forbidden_field(self, cls_name, forbidden):
        cls = getattr(schemas, cls_name)
        assert forbidden not in cls.__dataclass_fields__, (
            f"{cls_name}.{forbidden} would leak identity/text — forbidden"
        )

    def test_reframe_step_canonical_fields(self):
        assert set(schemas.ReframeStep.__dataclass_fields__.keys()) == {
            "reframe_type", "rationale",
        }

    def test_reframe_plan_canonical_fields(self):
        assert set(schemas.ReframePlan.__dataclass_fields__.keys()) == {
            "steps", "primitive",
            "expected_pressure_delta", "expected_agency_delta",
        }

    def test_aligned_expression_canonical_fields(self):
        assert set(schemas.AlignedExpression.__dataclass_fields__.keys()) == {
            "plan", "alignment_score",
            "internal_relator_preserved", "safe_for_surface",
        }

    def test_emotional_snapshot_no_text(self):
        for forbidden in ("text", "raw", "user_id", "identity"):
            assert forbidden not in schemas.EmotionalSnapshot.__dataclass_fields__

    def test_emotional_geometry_no_text(self):
        for forbidden in ("text", "raw", "user_id", "identity"):
            assert forbidden not in schemas.EmotionalGeometry.__dataclass_fields__

    def test_emotional_intention_no_user_text(self):
        # target_state IS user-facing intent, but it's a structured short
        # label — the test asserts no general identity / raw text fields.
        for forbidden in ("text", "raw", "user_id", "name", "email", "session_id"):
            assert forbidden not in schemas.EmotionalIntention.__dataclass_fields__


# ===========================================================================
# D. Module-load runtime guards
# ===========================================================================
class TestRuntimeGuards:
    def test_privacy_guard_passes(self):
        schemas.assert_era_privacy_contract()

    def test_field_set_guard_passes(self):
        schemas.assert_era_field_sets_canonical()

    def test_reframe_types_canonical(self):
        schemas.assert_reframe_types_canonical()


# ===========================================================================
# E. HIGH/CRITICAL pressure path — only AGENCY/SCALE allowed
# ===========================================================================
class TestHighPressurePath:
    def test_high_pressure_no_meaning_even_with_torsion(self):
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        g = _geometry(torsion=True, shear=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        types = _step_types(plan)
        assert schemas.ReframeType.MEANING not in types

    def test_critical_pressure_no_label_even_with_shear(self):
        s = _snapshot(pressure_level=PressureLevel.CRITICAL)
        g = _geometry(shear=True, stance_self=0.9)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        types = _step_types(plan)
        assert schemas.ReframeType.LABEL not in types

    def test_high_pressure_no_temporal_even_with_anchor(self):
        s = _snapshot(
            pressure_level=PressureLevel.HIGH,
            temporal_linked=True, anchor_present=True,
        )
        g = _geometry()
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        types = _step_types(plan)
        assert schemas.ReframeType.TEMPORAL not in types

    def test_high_pressure_no_role_even_with_boundary(self):
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        g = _geometry(boundary=True, stance_other=0.9)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        types = _step_types(plan)
        assert schemas.ReframeType.ROLE not in types

    def test_high_pressure_scale_fires_when_curvature(self):
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        g = _geometry(curvature=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert schemas.ReframeType.SCALE in _step_types(plan)

    def test_high_pressure_agency_fires_when_submit(self):
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        g = _geometry()
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert schemas.ReframeType.AGENCY in _step_types(plan)

    def test_high_pressure_agency_fires_when_world_hostile(self):
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        g = _geometry(stance_world=0.8)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert schemas.ReframeType.AGENCY in _step_types(plan)

    def test_critical_with_nothing_to_correct_is_none(self):
        s = _snapshot(pressure_level=PressureLevel.CRITICAL)
        g = _geometry()  # all flags False, low stance
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert _step_types(plan) == {schemas.ReframeType.NONE}

    def test_high_pressure_delta_never_positive(self):
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        g = _geometry(curvature=True, stance_world=0.9)
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert plan.expected_pressure_delta <= 0


# ===========================================================================
# F. Temporal anchor (Rule 2)
# ===========================================================================
class TestTemporalRule:
    def test_temporal_linked_and_anchor_fires_temporal(self):
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry()
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.MOTION)
        assert schemas.ReframeType.TEMPORAL in _step_types(plan)

    def test_temporal_linked_without_anchor_does_not_fire(self):
        s = _snapshot(temporal_linked=True, anchor_present=False)
        g = _geometry()
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.MOTION)
        assert schemas.ReframeType.TEMPORAL not in _step_types(plan)

    def test_anchor_without_temporal_link_does_not_fire(self):
        s = _snapshot(temporal_linked=False, anchor_present=True)
        g = _geometry()
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.MOTION)
        assert schemas.ReframeType.TEMPORAL not in _step_types(plan)


# ===========================================================================
# G. Shear / self-attack (Rule 3) — LABEL
# ===========================================================================
class TestLabelRule:
    def test_shear_flag_fires_label(self):
        s = _snapshot()
        g = _geometry(shear=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert schemas.ReframeType.LABEL in _step_types(plan)

    def test_high_stance_self_fires_label(self):
        s = _snapshot()
        g = _geometry(stance_self=0.8)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert schemas.ReframeType.LABEL in _step_types(plan)

    def test_low_stance_self_no_shear_no_label(self):
        s = _snapshot()
        g = _geometry(stance_self=0.3)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert schemas.ReframeType.LABEL not in _step_types(plan)


# ===========================================================================
# H. Boundary / SUBMIT (Rule 4) — ROLE [+AGENCY]
# ===========================================================================
class TestRoleAndAgencyRule:
    def test_boundary_flag_fires_role(self):
        s = _snapshot()
        g = _geometry(boundary=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        types = _step_types(plan)
        assert schemas.ReframeType.ROLE in types

    def test_high_stance_other_fires_role(self):
        s = _snapshot()
        g = _geometry(stance_other=0.85)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert schemas.ReframeType.ROLE in _step_types(plan)

    def test_submit_posture_fires_role_and_agency(self):
        s = _snapshot()
        g = _geometry()  # no boundary, low stance
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        types = _step_types(plan)
        assert schemas.ReframeType.ROLE in types
        assert schemas.ReframeType.AGENCY in types

    def test_boundary_without_submit_no_agency(self):
        s = _snapshot()
        g = _geometry(boundary=True)
        i = _intention(relational_posture=schemas.RelationalPosture.CONNECT)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        # ROLE fires from boundary; AGENCY does not fire (no SUBMIT)
        assert schemas.ReframeType.ROLE in _step_types(plan)
        assert schemas.ReframeType.AGENCY not in _step_types(plan)


# ===========================================================================
# I. Curvature (Rule 5) — SCALE
# ===========================================================================
class TestScaleRule:
    def test_curvature_fires_scale(self):
        s = _snapshot()
        g = _geometry(curvature=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert schemas.ReframeType.SCALE in _step_types(plan)

    def test_no_curvature_no_scale(self):
        s = _snapshot()
        g = _geometry(curvature=False)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert schemas.ReframeType.SCALE not in _step_types(plan)

    def test_scale_reduces_pressure_delta(self):
        s = _snapshot()
        g = _geometry(curvature=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert plan.expected_pressure_delta == -1


# ===========================================================================
# J. MEANING (Rule 6) — only at LOW/MEDIUM, requires torsion or shear
# ===========================================================================
class TestMeaningRule:
    def test_torsion_at_low_pressure_fires_meaning(self):
        s = _snapshot(pressure_level=PressureLevel.LOW)
        g = _geometry(torsion=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.ANALOGY)
        assert schemas.ReframeType.MEANING in _step_types(plan)

    def test_shear_at_medium_pressure_fires_meaning(self):
        s = _snapshot(pressure_level=PressureLevel.MEDIUM)
        g = _geometry(shear=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.ANALOGY)
        assert schemas.ReframeType.MEANING in _step_types(plan)

    def test_meaning_excluded_under_high_pressure(self):
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        g = _geometry(torsion=True, shear=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.ANALOGY)
        assert schemas.ReframeType.MEANING not in _step_types(plan)

    def test_no_torsion_no_shear_no_meaning(self):
        s = _snapshot(pressure_level=PressureLevel.LOW)
        g = _geometry()  # neither torsion nor shear
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.ANALOGY)
        assert schemas.ReframeType.MEANING not in _step_types(plan)


# ===========================================================================
# K. NONE case — no rule fires
# ===========================================================================
class TestNoneCase:
    def test_neutral_low_pressure_yields_none(self):
        s = _snapshot(pressure_level=PressureLevel.LOW)
        g = _geometry()  # all flags False, low stance
        i = _intention()  # CONNECT, no SUBMIT
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert _step_types(plan) == {schemas.ReframeType.NONE}

    def test_none_case_zero_deltas(self):
        s = _snapshot(pressure_level=PressureLevel.LOW)
        g = _geometry()
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert plan.expected_pressure_delta == 0
        assert plan.expected_agency_delta == 0


# ===========================================================================
# L. Delta range constraints
# ===========================================================================
class TestDeltaRanges:
    @pytest.mark.parametrize("pressure", list(PressureLevel))
    @pytest.mark.parametrize("curvature", [True, False])
    @pytest.mark.parametrize("posture", list(schemas.RelationalPosture))
    def test_pressure_delta_in_legal_range(self, pressure, curvature, posture):
        s = _snapshot(pressure_level=pressure)
        g = _geometry(curvature=curvature, shear=True, stance_self=0.8)
        i = _intention(relational_posture=posture)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert plan.expected_pressure_delta in (-1, 0, 1)
        # And specifically: never increase under HIGH/CRITICAL
        if pressure in (PressureLevel.HIGH, PressureLevel.CRITICAL):
            assert plan.expected_pressure_delta <= 0

    @pytest.mark.parametrize("pressure", list(PressureLevel))
    @pytest.mark.parametrize("posture", list(schemas.RelationalPosture))
    def test_agency_delta_in_legal_range(self, pressure, posture):
        s = _snapshot(pressure_level=pressure)
        g = _geometry()
        i = _intention(relational_posture=posture)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert plan.expected_agency_delta in (-1, 0, 1)


# ===========================================================================
# M. Alignment score
# ===========================================================================
class TestAlignmentScore:
    def test_baseline_score_with_none_plan(self):
        s = _snapshot()
        g = _geometry()
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        score = engine.compute_alignment_score(s, g, i, plan)
        assert score == 0.5

    def test_agency_bonus(self):
        # SUBMIT → AGENCY + ROLE → agency_delta = 1 → bonus +0.2
        s = _snapshot()
        g = _geometry()
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        score = engine.compute_alignment_score(s, g, i, plan)
        assert score >= 0.7  # 0.5 + 0.2 (AGENCY bonus)

    def test_scale_bonus(self):
        s = _snapshot()
        g = _geometry(curvature=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        score = engine.compute_alignment_score(s, g, i, plan)
        assert score >= 0.7  # 0.5 + 0.2 (SCALE bonus)

    def test_temporal_bonus(self):
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry()
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        score = engine.compute_alignment_score(s, g, i, plan)
        assert score >= 0.6  # 0.5 + 0.1 (TEMPORAL bonus)

    def test_label_bonus_with_shear(self):
        s = _snapshot()
        g = _geometry(shear=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        score = engine.compute_alignment_score(s, g, i, plan)
        assert score >= 0.6  # 0.5 + 0.1 (LABEL bonus)

    def test_score_in_unit_interval(self):
        for pressure in PressureLevel:
            s = _snapshot(pressure_level=pressure,
                          temporal_linked=True, anchor_present=True)
            g = _geometry(curvature=True, shear=True, boundary=True,
                          stance_self=0.9, stance_other=0.9, stance_world=0.9)
            i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
            plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
            score = engine.compute_alignment_score(s, g, i, plan)
            assert 0.0 <= score <= 1.0

    def test_score_capped_at_one(self):
        # Maximum possible bonuses: AGENCY + SCALE + TEMPORAL + LABEL = +0.6
        # → score = 1.1 capped to 1.0
        s = _snapshot(
            pressure_level=PressureLevel.LOW,
            temporal_linked=True, anchor_present=True,
        )
        g = _geometry(curvature=True, shear=True, stance_self=0.8)
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        score = engine.compute_alignment_score(s, g, i, plan)
        assert score == 1.0


# ===========================================================================
# N. Safety flags
# ===========================================================================
class TestSafetyFlags:
    def test_low_pressure_meaning_safe_for_surface(self):
        s = _snapshot(pressure_level=PressureLevel.LOW)
        g = _geometry(torsion=True)
        i = _intention()
        result = engine.align_expression(s, g, i, ExpressionPrimitive.ANALOGY)
        assert result.safe_for_surface is True
        assert result.internal_relator_preserved is True

    def test_high_pressure_with_only_agency_safe(self):
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        g = _geometry(stance_world=0.8)
        i = _intention()
        result = engine.align_expression(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert result.safe_for_surface is True
        assert result.internal_relator_preserved is True

    def test_critical_no_meaning_flags_preserved(self):
        s = _snapshot(pressure_level=PressureLevel.CRITICAL)
        g = _geometry(torsion=True, shear=True, curvature=True)
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        result = engine.align_expression(s, g, i, ExpressionPrimitive.HYDRONICS)
        # MEANING must NOT be in plan (excluded under CRITICAL)
        types = _step_types(result.plan)
        assert schemas.ReframeType.MEANING not in types
        assert result.internal_relator_preserved is True
        assert result.safe_for_surface is True

    def test_manually_constructed_meaning_under_high_pressure_unsafe(self):
        """If a plan is hand-built (bypassing build_reframe_plan) that
        includes MEANING under HIGH pressure, the safety flags surface
        that violation."""
        s = _snapshot(pressure_level=PressureLevel.HIGH)
        # Hand-build a plan that violates the contract
        bad_plan = schemas.ReframePlan(
            steps=(schemas.ReframeStep(
                reframe_type=schemas.ReframeType.MEANING,
                rationale="manually-injected violation",
            ),),
            primitive=ExpressionPrimitive.ANALOGY,
            expected_pressure_delta=0,
            expected_agency_delta=0,
        )
        # The private helper functions surface the violation:
        assert engine._internal_relator_preserved(s, bad_plan) is False
        assert engine._safe_for_surface(s, bad_plan) is False


# ===========================================================================
# O. align_expression composition
# ===========================================================================
class TestAlignExpressionComposition:
    def test_returns_aligned_expression(self):
        s = _snapshot()
        g = _geometry()
        i = _intention()
        result = engine.align_expression(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert isinstance(result, schemas.AlignedExpression)

    def test_plan_matches_build_reframe_plan(self):
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry(shear=True)
        i = _intention()
        result = engine.align_expression(s, g, i, ExpressionPrimitive.GEOMETRY)
        expected_plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert result.plan == expected_plan

    def test_score_matches_compute_alignment_score(self):
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry(shear=True)
        i = _intention()
        result = engine.align_expression(s, g, i, ExpressionPrimitive.GEOMETRY)
        expected_score = engine.compute_alignment_score(s, g, i, result.plan)
        assert result.alignment_score == expected_score


# ===========================================================================
# P. Worked examples (SPEC § 9)
# ===========================================================================
class TestWorkedExamples:
    def test_91_authority_shame(self):
        s = _snapshot(
            pressure_level=PressureLevel.MEDIUM,
            intensity=IntensityLevel.HIGH,
            valence=Valence.NEGATIVE,
            temporal_linked=True, anchor_present=True,
        )
        g = _geometry(
            shear=True, boundary=True,
            stance_self=0.8, stance_other=0.5,
        )
        i = _intention(
            target_state="be heard without shame",
            regulatory_goal=schemas.RegulationGoal.EXPRESS,
            relational_posture=schemas.RelationalPosture.SUBMIT,
            meaning_need=schemas.MeaningNeed.VALIDATE,
        )
        result = engine.align_expression(s, g, i, ExpressionPrimitive.HYDRONICS)
        types = _step_types(result.plan)

        assert schemas.ReframeType.TEMPORAL in types
        assert schemas.ReframeType.ROLE in types or schemas.ReframeType.AGENCY in types
        assert result.alignment_score > 0.5  # above baseline
        assert result.internal_relator_preserved is True
        assert result.safe_for_surface is True

    def test_92_repeated_failure_globalizing(self):
        s = _snapshot(
            pressure_level=PressureLevel.MEDIUM,
            temporal_linked=True, anchor_present=True,
        )
        g = _geometry(curvature=True)
        i = _intention(
            regulatory_goal=schemas.RegulationGoal.TRANSFORM,
            relational_posture=schemas.RelationalPosture.SEPARATE,
            meaning_need=schemas.MeaningNeed.REFRAME,
        )
        result = engine.align_expression(s, g, i, ExpressionPrimitive.MOTION)
        types = _step_types(result.plan)

        assert schemas.ReframeType.SCALE in types
        assert schemas.ReframeType.TEMPORAL in types
        assert result.plan.expected_pressure_delta <= 0

    def test_93_anger_hiding_fear(self):
        s = _snapshot(
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.EXTREME,
            valence=Valence.NEGATIVE,
        )
        g = _geometry(
            torsion=True, boundary=True,
            stance_self=0.3, stance_other=0.9, stance_world=0.7,
            pressure_gradient=0.8,
        )
        i = _intention(
            regulatory_goal=schemas.RegulationGoal.CONTAIN,
            relational_posture=schemas.RelationalPosture.DEFEND,
        )
        result = engine.align_expression(s, g, i, ExpressionPrimitive.HYDRONICS)
        types = _step_types(result.plan)

        # AGENCY fires (stance_world ≥ 0.7), but no MEANING under HIGH
        assert schemas.ReframeType.AGENCY in types
        assert schemas.ReframeType.MEANING not in types
        # ROLE excluded under HIGH pressure
        assert schemas.ReframeType.ROLE not in types

    def test_94_collapse_critical_pressure(self):
        s = _snapshot(
            pressure_level=PressureLevel.CRITICAL,
            intensity=IntensityLevel.EXTREME,
            valence=Valence.NEGATIVE,
            temporal_linked=True, anchor_present=True,
        )
        g = _geometry(
            curvature=True, torsion=True, shear=True,
            stance_self=0.9, stance_world=0.6,
            pressure_gradient=0.9,
        )
        i = _intention(
            regulatory_goal=schemas.RegulationGoal.CONTAIN,
            relational_posture=schemas.RelationalPosture.SUBMIT,
            meaning_need=schemas.MeaningNeed.NONE,
        )
        result = engine.align_expression(s, g, i, ExpressionPrimitive.HYDRONICS)
        types = _step_types(result.plan)

        # Under CRITICAL: only AGENCY and SCALE permitted
        assert schemas.ReframeType.SCALE in types  # curvature
        assert schemas.ReframeType.AGENCY in types  # SUBMIT
        assert schemas.ReframeType.LABEL not in types
        assert schemas.ReframeType.TEMPORAL not in types
        assert schemas.ReframeType.MEANING not in types
        assert schemas.ReframeType.ROLE not in types
        assert result.internal_relator_preserved is True
        assert result.safe_for_surface is True

    def test_95_low_pressure_reflection(self):
        s = _snapshot(
            pressure_level=PressureLevel.LOW,
            intensity=IntensityLevel.MEDIUM,
            valence=Valence.MIXED,
        )
        g = _geometry(torsion=True)
        i = _intention(
            regulatory_goal=schemas.RegulationGoal.TRANSFORM,
            meaning_need=schemas.MeaningNeed.CLARIFY,
        )
        result = engine.align_expression(s, g, i, ExpressionPrimitive.ANALOGY)
        types = _step_types(result.plan)

        # MEANING fires (LOW pressure + torsion)
        assert schemas.ReframeType.MEANING in types
        # Score baseline 0.5 (no AGENCY/SCALE/TEMPORAL/LABEL bonus)
        # Bonus only fires for those specific types; MEANING isn't in the
        # bonus list. So score should equal baseline.
        assert result.alignment_score == 0.5

    def test_96_no_reframe_needed(self):
        s = _snapshot(pressure_level=PressureLevel.LOW)
        g = _geometry()  # all defaults are non-firing
        i = _intention()
        result = engine.align_expression(s, g, i, ExpressionPrimitive.GEOMETRY)
        types = _step_types(result.plan)

        assert types == {schemas.ReframeType.NONE}
        assert result.alignment_score == 0.5
        assert result.internal_relator_preserved is True
        assert result.safe_for_surface is True


# ===========================================================================
# Q. Determinism
# ===========================================================================
class TestDeterminism:
    def test_build_reframe_plan_byte_equal(self):
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry(shear=True, curvature=True)
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        plan1 = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        plan2 = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert plan1 == plan2

    def test_compute_alignment_score_deterministic(self):
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry(shear=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        score1 = engine.compute_alignment_score(s, g, i, plan)
        score2 = engine.compute_alignment_score(s, g, i, plan)
        assert score1 == score2

    def test_align_expression_byte_equal(self):
        s = _snapshot(temporal_linked=True, anchor_present=True,
                      pressure_level=PressureLevel.MEDIUM)
        g = _geometry(shear=True, curvature=True, boundary=True,
                      stance_self=0.85)
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        r1 = engine.align_expression(s, g, i, ExpressionPrimitive.HYDRONICS)
        r2 = engine.align_expression(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert r1 == r2

    def test_no_text_or_identity_leakage(self):
        """A unique marker in `target_state` MUST NOT leak into any
        output field of the AlignedExpression."""
        marker = "ZxYxQwertUniqueMarker7777"
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry(shear=True)
        i = _intention(target_state=marker)
        result = engine.align_expression(s, g, i, ExpressionPrimitive.HYDRONICS)

        # Walk the output and verify the marker doesn't appear anywhere.
        def _search(obj):
            if isinstance(obj, str):
                return marker in obj
            if hasattr(obj, "__dataclass_fields__"):
                return any(
                    _search(getattr(obj, f.name))
                    for f in obj.__dataclass_fields__.values()
                )
            if isinstance(obj, (list, tuple)):
                return any(_search(x) for x in obj)
            return False

        assert not _search(result), (
            "target_state leaked into AlignedExpression"
        )


# ===========================================================================
# R. Source-code invariants
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
        """Invariant 10: ERA is advisory only — no send patterns."""
        src = self._src(engine)
        for forbidden in (".post(", ".put(", ".send(", "urlopen(",
                          "requests.", "smtplib"):
            assert forbidden not in src


# ===========================================================================
# S. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_schemas_exports(self):
        for name in (
            # Enums
            "RegulationGoal", "RelationalPosture", "MeaningNeed",
            "ReframeType",
            # Base types
            "EmotionalSnapshot", "EmotionalGeometry", "EmotionalIntention",
            # ERA output types
            "ReframeStep", "ReframePlan", "AlignedExpression",
            # Guards
            "assert_era_privacy_contract",
            "assert_era_field_sets_canonical",
            "assert_reframe_types_canonical",
        ):
            assert hasattr(schemas, name), f"missing in schemas: {name}"

    def test_engine_exports(self):
        for name in (
            "build_reframe_plan", "compute_alignment_score",
            "align_expression",
        ):
            assert hasattr(engine, name)
            assert callable(getattr(engine, name))


# ===========================================================================
# T. Cross-priority — HIGH/CRITICAL hard restriction never fires excluded types
# ===========================================================================
class TestHighPressureExclusion:
    @pytest.mark.parametrize("forbidden_type", [
        schemas.ReframeType.LABEL,
        schemas.ReframeType.TEMPORAL,
        schemas.ReframeType.ROLE,
        schemas.ReframeType.MEANING,
    ])
    def test_high_pressure_never_emits_excluded_type(self, forbidden_type):
        """For every trigger combination that would fire the excluded type
        under low pressure, HIGH pressure must NOT include it."""
        s = _snapshot(
            pressure_level=PressureLevel.HIGH,
            temporal_linked=True, anchor_present=True,
        )
        g = _geometry(
            curvature=True, torsion=True, shear=True, boundary=True,
            stance_self=0.9, stance_other=0.9, stance_world=0.9,
            pressure_gradient=0.9,
        )
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert forbidden_type not in _step_types(plan)

    @pytest.mark.parametrize("forbidden_type", [
        schemas.ReframeType.LABEL,
        schemas.ReframeType.TEMPORAL,
        schemas.ReframeType.ROLE,
        schemas.ReframeType.MEANING,
    ])
    def test_critical_pressure_never_emits_excluded_type(self, forbidden_type):
        s = _snapshot(
            pressure_level=PressureLevel.CRITICAL,
            temporal_linked=True, anchor_present=True,
        )
        g = _geometry(
            curvature=True, torsion=True, shear=True, boundary=True,
            stance_self=0.9, stance_other=0.9, stance_world=0.9,
        )
        i = _intention(relational_posture=schemas.RelationalPosture.SUBMIT)
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.HYDRONICS)
        assert forbidden_type not in _step_types(plan)


# ===========================================================================
# U. Invariant cross-checks
# ===========================================================================
class TestInvariantCrossChecks:
    def test_invariant_3_determinism(self):
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry(shear=True, curvature=True)
        i = _intention()
        r1 = engine.align_expression(s, g, i, ExpressionPrimitive.GEOMETRY)
        r2 = engine.align_expression(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert r1 == r2

    def test_invariant_5_no_pressure_increase_under_high(self):
        """For every realistic input combination, pressure_delta <= 0 under
        HIGH/CRITICAL."""
        for pressure in (PressureLevel.HIGH, PressureLevel.CRITICAL):
            for curv in (True, False):
                for posture in schemas.RelationalPosture:
                    s = _snapshot(pressure_level=pressure)
                    g = _geometry(curvature=curv, shear=True,
                                  stance_self=0.9)
                    i = _intention(relational_posture=posture)
                    plan = engine.build_reframe_plan(
                        s, g, i, ExpressionPrimitive.HYDRONICS,
                    )
                    assert plan.expected_pressure_delta <= 0

    def test_invariant_9_alignment_score_pure(self):
        """Same (snapshot, geometry, intention, plan) → same score."""
        s = _snapshot(temporal_linked=True, anchor_present=True)
        g = _geometry(shear=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        scores = [
            engine.compute_alignment_score(s, g, i, plan) for _ in range(5)
        ]
        assert all(x == scores[0] for x in scores)

    def test_invariant_8_at_least_one_improvement_axis(self):
        """When ANY rule fires, the plan must improve at least one axis
        (precision via SCALE/LABEL, agency via AGENCY/ROLE, or temporal
        differentiation via TEMPORAL)."""
        # Pick a fixture that fires some rule.
        s = _snapshot(pressure_level=PressureLevel.LOW,
                      temporal_linked=True, anchor_present=True)
        g = _geometry(curvature=True)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        improvement_types = {
            schemas.ReframeType.SCALE,   # precision (specificity)
            schemas.ReframeType.LABEL,   # precision (behavior-bounded)
            schemas.ReframeType.AGENCY,  # agency
            schemas.ReframeType.ROLE,    # agency (role redefinition)
            schemas.ReframeType.TEMPORAL,  # temporal differentiation
        }
        assert improvement_types & _step_types(plan), (
            "plan fired rules but no improvement axis present"
        )

    def test_score_always_in_unit_interval(self):
        """Invariant 9 implication: score ∈ [0, 1] for all reachable inputs."""
        for pressure in PressureLevel:
            for posture in schemas.RelationalPosture:
                s = _snapshot(
                    pressure_level=pressure,
                    temporal_linked=True, anchor_present=True,
                )
                g = _geometry(
                    curvature=True, torsion=True, shear=True, boundary=True,
                    stance_self=0.9, stance_other=0.9, stance_world=0.9,
                )
                i = _intention(relational_posture=posture)
                result = engine.align_expression(
                    s, g, i, ExpressionPrimitive.GEOMETRY,
                )
                assert 0.0 <= result.alignment_score <= 1.0


# ===========================================================================
# V. Stance threshold lock
# ===========================================================================
class TestStanceThreshold:
    def test_stance_threshold_value(self):
        """The threshold is locked at 0.7 per SPEC § 5.2."""
        assert engine._STANCE_HIGH_THRESHOLD == 0.7

    def test_at_threshold_fires(self):
        """stance_self exactly at threshold fires LABEL."""
        s = _snapshot()
        g = _geometry(stance_self=0.7)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert schemas.ReframeType.LABEL in _step_types(plan)

    def test_below_threshold_does_not_fire(self):
        s = _snapshot()
        g = _geometry(stance_self=0.69)
        i = _intention()
        plan = engine.build_reframe_plan(s, g, i, ExpressionPrimitive.GEOMETRY)
        assert schemas.ReframeType.LABEL not in _step_types(plan)
