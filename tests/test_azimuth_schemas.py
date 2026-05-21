"""
Structural tests for the Azimuth Mechanic schema module (Phase 3 design).

These verify the dataclass shapes, enum values, and skeleton invariants
WITHOUT depending on any implementation. The privacy contract is
enforced STRUCTURALLY here — any future PR that adds a free-text field
to CloudMetadata fails this suite.

Behavior tests (lexical heuristics, reframing rules, etc.) land when
Phase 3 Unit 5 + Unit 6 ship the real implementations.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from datetime import datetime, timezone

import pytest

import azimuth
import azimuth_envelope
import azimuth_reframing
import azimuth_transition


# ===========================================================================
# Enums — canonical values locked
# ===========================================================================
class TestEnums:
    def test_valence_values(self):
        assert {v.value for v in azimuth.Valence} == {
            "positive", "negative", "mixed", "neutral", "unknown",
        }

    def test_intensity_levels(self):
        assert {v.value for v in azimuth.IntensityLevel} == {
            "low", "medium", "high", "extreme",
        }

    def test_pressure_levels(self):
        assert {v.value for v in azimuth.PressureLevel} == {
            "low", "medium", "high", "critical",
        }

    def test_pressure_slopes(self):
        assert {v.value for v in azimuth.PressureSlope} == {
            "rising", "flat", "falling",
        }

    def test_pressure_shapes(self):
        assert {v.value for v in azimuth.PressureShape} == {
            "ascending", "descending", "plateau", "spike",
        }

    def test_audience_types(self):
        assert {v.value for v in azimuth.AudienceType} == {
            "self", "one_to_one", "small_group", "public",
        }

    def test_context_types(self):
        assert {v.value for v in azimuth.ContextType} == {
            "personal", "professional", "high_stakes", "low_stakes",
        }

    def test_urgency_levels(self):
        assert {v.value for v in azimuth.UrgencyLevel} == {
            "low", "medium", "high",
        }

    def test_intention_classes(self):
        assert {v.value for v in azimuth.IntentionClass} == {
            "vent", "request", "apologize", "boundary",
            "observation", "gratitude", "other",
        }

    def test_user_response_values(self):
        assert {v.value for v in azimuth.UserResponse} == {
            "accept", "tweak", "reject",
        }


# ===========================================================================
# Risk-flag canonical set
# ===========================================================================
class TestRiskFlagsCanonical:
    def test_all_documented_flags_present(self):
        expected = {
            "sharp_tone", "soft_tone", "high_pressure", "vague_target",
            "name_calling", "all_or_nothing", "urgency_inflation",
            "passive_aggressive", "absolutist_language", "ambiguous_request",
            # Phase 3 Unit 7 — alignment-aware additions.
            "hard_halt", "soft_halt",
        }
        assert expected.issubset(set(azimuth.RISK_FLAGS_CANONICAL))

    def test_is_tuple(self):
        assert isinstance(azimuth.RISK_FLAGS_CANONICAL, tuple)

    def test_all_entries_are_str(self):
        for f in azimuth.RISK_FLAGS_CANONICAL:
            assert isinstance(f, str) and f

    def test_phase_3_unit_7_alignment_flags_present(self):
        """Phase 3 Unit 7 added two alignment-aware canonical flags
        driven by IntegratedAlignmentResult.halt_level."""
        assert "hard_halt" in azimuth.RISK_FLAGS_CANONICAL
        assert "soft_halt" in azimuth.RISK_FLAGS_CANONICAL

    def test_canonical_flag_count_locked(self):
        """Twelve canonical flags as of Unit 7: ten documented +
        hard_halt + soft_halt. Any addition is a deliberate spec
        change."""
        assert len(azimuth.RISK_FLAGS_CANONICAL) == 12


# ===========================================================================
# EnvelopeState — schema + frozen invariant
# ===========================================================================
def _make_envelope() -> azimuth.EnvelopeState:
    return azimuth.EnvelopeState(
        raw_text="test reflection",
        captured_at=datetime.now(timezone.utc),
        emotional_intensity=azimuth.IntensityLevel.MEDIUM,
        valence=azimuth.Valence.NEUTRAL,
        pressure_level=azimuth.PressureLevel.LOW,
        rough_intention="reflect",
    )


class TestEnvelopeState:
    def test_instantiable(self):
        env = _make_envelope()
        assert env.raw_text == "test reflection"
        assert env.user_marked_externalize is False
        assert env.envelope_id  # auto-generated

    def test_frozen(self):
        env = _make_envelope()
        with pytest.raises(FrozenInstanceError):
            env.raw_text = "modified"  # type: ignore[misc]

    def test_envelope_id_unique_per_instance(self):
        e1, e2 = _make_envelope(), _make_envelope()
        assert e1.envelope_id != e2.envelope_id

    def test_envelope_id_default_factory_present(self):
        env_field = {f.name: f for f in fields(azimuth.EnvelopeState)}["envelope_id"]
        # Default factory must exist so each instance gets its own id.
        assert env_field.default_factory is not None  # type: ignore[truthy-bool]


# ===========================================================================
# ExpressionCandidate — schema + frozen invariant
# ===========================================================================
def _make_candidate() -> azimuth.ExpressionCandidate:
    return azimuth.ExpressionCandidate(
        raw_text="I want to raise this",
        intention="boundary about workload",
        intention_class=azimuth.IntentionClass.BOUNDARY,
        pressure_level=azimuth.PressureLevel.HIGH,
        pressure_slope=azimuth.PressureSlope.RISING,
        audience=azimuth.AudienceType.ONE_TO_ONE,
        context=azimuth.ContextType.PROFESSIONAL,
        urgency=azimuth.UrgencyLevel.MEDIUM,
    )


class TestExpressionCandidate:
    def test_instantiable(self):
        c = _make_candidate()
        assert c.raw_text == "I want to raise this"
        assert c.candidate_id  # auto-generated
        assert c.risk_flags == ()  # default empty

    def test_frozen(self):
        c = _make_candidate()
        with pytest.raises(FrozenInstanceError):
            c.raw_text = "x"  # type: ignore[misc]

    def test_carries_envelope_back_reference(self):
        c = azimuth.ExpressionCandidate(
            raw_text="x", intention="x",
            intention_class=azimuth.IntentionClass.OTHER,
            pressure_level=azimuth.PressureLevel.LOW,
            pressure_slope=azimuth.PressureSlope.FLAT,
            audience=azimuth.AudienceType.SELF,
            context=azimuth.ContextType.PERSONAL,
            urgency=azimuth.UrgencyLevel.LOW,
            envelope_id="env_test_id",
        )
        assert c.envelope_id == "env_test_id"

    def test_canonical_field_set_includes_aligned(self):
        """Phase 3 Unit 6 added an Optional[IntegratedAlignmentResult]
        ``aligned`` field to ExpressionCandidate. The full canonical
        field set is locked here; any change is a deliberate spec
        change that must be reflected in this test."""
        expected = {
            "raw_text", "intention", "intention_class",
            "pressure_level", "pressure_slope",
            "audience", "context", "urgency",
            "risk_flags", "envelope_id", "candidate_id",
            "aligned",
        }
        assert set(azimuth.ExpressionCandidate.__dataclass_fields__.keys()) == expected

    def test_aligned_defaults_to_none(self):
        """``aligned`` is optional — backward compatible."""
        c = _make_candidate()
        assert c.aligned is None

    def test_aligned_can_carry_integrated_alignment_result(self):
        """``aligned`` accepts a real IntegratedAlignmentResult instance."""
        from emotional_alignment_schemas import (
            AlignedExpression, ReframePlan, ReframeStep, ReframeType,
        )
        from fea_integration_schemas import (
            IntegratedAlignmentResult, SurfaceHaltLevel,
        )
        from language_schemas import ExpressionPrimitive

        plan = ReframePlan(
            steps=(ReframeStep(
                reframe_type=ReframeType.NONE, rationale="x"),),
            primitive=ExpressionPrimitive.GEOMETRY,
            expected_pressure_delta=0,
            expected_agency_delta=0,
        )
        aligned = AlignedExpression(
            plan=plan, alignment_score=0.5,
            internal_relator_preserved=True, safe_for_surface=True,
        )
        result = IntegratedAlignmentResult(
            aligned_expression=aligned,
            halt_level=SurfaceHaltLevel.NONE,
            trust_state_delta=0.1,
            momentum_preserved=True,
            surface_directives=(),
        )
        c = azimuth.ExpressionCandidate(
            raw_text="x", intention="x",
            intention_class=azimuth.IntentionClass.OTHER,
            pressure_level=azimuth.PressureLevel.LOW,
            pressure_slope=azimuth.PressureSlope.FLAT,
            audience=azimuth.AudienceType.SELF,
            context=azimuth.ContextType.PERSONAL,
            urgency=azimuth.UrgencyLevel.LOW,
            aligned=result,
        )
        assert c.aligned is result
        assert c.aligned.halt_level == SurfaceHaltLevel.NONE


# ===========================================================================
# CloudMetadata — PRIVACY CONTRACT (structural)
# ===========================================================================
class TestCloudMetadataPrivacyContract:
    """These tests fail any PR that breaks the privacy boundary."""

    def test_no_raw_text_field(self):
        assert "raw_text" not in azimuth.CloudMetadata.__dataclass_fields__

    def test_no_user_id_field(self):
        assert "user_id" not in azimuth.CloudMetadata.__dataclass_fields__

    def test_no_envelope_id_field(self):
        assert "envelope_id" not in azimuth.CloudMetadata.__dataclass_fields__

    def test_no_candidate_id_field(self):
        assert "candidate_id" not in azimuth.CloudMetadata.__dataclass_fields__

    def test_no_free_text_intention_field(self):
        """The free-text ``intention`` from ExpressionCandidate must NOT
        appear in CloudMetadata. Only the categorical
        ``intention_class`` is permitted."""
        assert "intention" not in azimuth.CloudMetadata.__dataclass_fields__

    def test_no_rough_intention_field(self):
        assert "rough_intention" not in azimuth.CloudMetadata.__dataclass_fields__

    def test_no_name_or_identifier_fields(self):
        for forbidden in ("name", "names", "identity", "identifier"):
            assert forbidden not in azimuth.CloudMetadata.__dataclass_fields__

    def test_only_canonical_categorical_fields(self):
        """The full set of permitted CloudMetadata fields, locked."""
        expected = {
            "pressure_shape",
            "pressure_slope",
            "pressure_level",
            "audience_type",
            "context_type",
            "urgency_level",
            "intention_class",
            "risk_flags",
            "schema_version",
        }
        assert set(azimuth.CloudMetadata.__dataclass_fields__.keys()) == expected

    def test_runtime_privacy_guard(self):
        """The module-level guard helper executes without raising."""
        azimuth.assert_cloud_privacy_contract()  # must not raise

    def test_forbidden_set_includes_all_dangerous_keys(self):
        for forbidden in (
            "raw_text", "user_id", "envelope_id", "candidate_id",
            "intention", "rough_intention",
        ):
            assert forbidden in azimuth._FORBIDDEN_CLOUD_FIELDS

    def test_instantiable(self):
        m = azimuth.CloudMetadata(
            pressure_shape=azimuth.PressureShape.SPIKE,
            pressure_slope=azimuth.PressureSlope.RISING,
            pressure_level=azimuth.PressureLevel.HIGH,
            audience_type=azimuth.AudienceType.ONE_TO_ONE,
            context_type=azimuth.ContextType.PROFESSIONAL,
            urgency_level=azimuth.UrgencyLevel.HIGH,
            intention_class=azimuth.IntentionClass.REQUEST,
        )
        assert m.schema_version == "azimuth.v1"
        assert m.risk_flags == ()

    def test_frozen(self):
        m = azimuth.CloudMetadata(
            pressure_shape=azimuth.PressureShape.PLATEAU,
            pressure_slope=azimuth.PressureSlope.FLAT,
            pressure_level=azimuth.PressureLevel.LOW,
            audience_type=azimuth.AudienceType.SELF,
            context_type=azimuth.ContextType.PERSONAL,
            urgency_level=azimuth.UrgencyLevel.LOW,
            intention_class=azimuth.IntentionClass.OBSERVATION,
        )
        with pytest.raises(FrozenInstanceError):
            m.schema_version = "x"  # type: ignore[misc]


# ===========================================================================
# CloudAdvisory
# ===========================================================================
class TestCloudAdvisory:
    def test_instantiable(self):
        a = azimuth.CloudAdvisory(
            basin_pressure=azimuth.PressureLevel.HIGH,
            macro_field_weather="turbulent",
            audience_stake="high",
            advisories=("audience_in_high_stakes_basin",),
        )
        assert a.basin_pressure == azimuth.PressureLevel.HIGH
        assert a.schema_version == "azimuth.v1"

    def test_no_raw_or_id_fields(self):
        forbidden = {"raw_text", "user_id", "envelope_id", "candidate_id"}
        actual = set(azimuth.CloudAdvisory.__dataclass_fields__.keys())
        assert forbidden.isdisjoint(actual)


# ===========================================================================
# ReframedExpression
# ===========================================================================
class TestReframedExpression:
    def test_instantiable(self):
        r = azimuth.ReframedExpression(
            original_intention="vent + raise stakes",
            reframed_text="The deadline change is unworkable.",
            preserved_intent_score=0.88,
            drift_risk_after=0.14,
        )
        assert r.preserved_intent_score == 0.88
        assert r.drift_risk_after == 0.14
        assert r.diff_notes == ()

    def test_frozen(self):
        r = azimuth.ReframedExpression(
            original_intention="x", reframed_text="y",
            preserved_intent_score=1.0, drift_risk_after=0.0,
        )
        with pytest.raises(FrozenInstanceError):
            r.reframed_text = "z"  # type: ignore[misc]


# ===========================================================================
# AzimuthCheckPrompt
# ===========================================================================
class TestAzimuthCheckPrompt:
    def test_instantiable(self):
        prompt = azimuth.AzimuthCheckPrompt(
            landing_prediction="this will read as an attack",
            reframed_options=(),
        )
        assert prompt.user_question == "Does this still feel like what you mean?"

    def test_canonical_user_question(self):
        """The user question is the canonical closing of every Azimuth Check."""
        prompt = azimuth.AzimuthCheckPrompt(
            landing_prediction="",
            reframed_options=(),
        )
        assert "what you mean" in prompt.user_question


# ===========================================================================
# Skeleton invariants — every function raises NotImplementedError until
# Phase 3 Unit 5 / Unit 6 lands real behaviour
# ===========================================================================
class TestSkeletonsRaise:
    def test_envelope_capture_skeleton(self):
        with pytest.raises(NotImplementedError):
            azimuth_envelope.capture_envelope("x")

    def test_envelope_evaluate_skeleton(self):
        env = _make_envelope()
        with pytest.raises(NotImplementedError):
            azimuth_envelope.evaluate_envelope(env)

    def test_envelope_mark_externalize_skeleton(self):
        env = _make_envelope()
        with pytest.raises(NotImplementedError):
            azimuth_envelope.mark_externalize(env)

    def test_transition_detect_implemented(self):
        """Phase 3 Unit 9: detect_externalization_intent is now
        implemented. It returns a bool — True when any of the three
        triggers fires (explicit flag, lexical markers, or topic
        recurrence)."""
        env = _make_envelope()
        result = azimuth_transition.detect_externalization_intent(env)
        assert isinstance(result, bool)

    def test_transition_build_candidate_implemented(self):
        """Phase 3 Unit 6: build_candidate is now implemented (no longer
        a NotImplementedError stub). It returns a real ExpressionCandidate
        carrying the IntegratedAlignmentResult on its ``aligned`` field."""
        env = _make_envelope()
        result = azimuth_transition.build_candidate(
            env,
            audience=azimuth.AudienceType.ONE_TO_ONE,
            context=azimuth.ContextType.PROFESSIONAL,
        )
        assert isinstance(result, azimuth.ExpressionCandidate)
        assert result.aligned is not None

    def test_transition_evaluate_drift_risk_implemented(self):
        """Phase 3 Unit 7: evaluate_drift_risk is now implemented with
        the upgraded signature ``(env, *, candidate) -> ExpressionCandidate``."""
        env = _make_envelope()
        candidate = _make_candidate()
        result = azimuth_transition.evaluate_drift_risk(
            env, candidate=candidate,
        )
        assert isinstance(result, azimuth.ExpressionCandidate)
        assert isinstance(result.risk_flags, tuple)

    def test_transition_build_cloud_metadata_implemented(self):
        """Phase 3 Unit 8: build_cloud_metadata is now implemented. It
        derives pressure_shape and returns a fully-populated CloudMetadata
        with no raw text or local identifiers."""
        candidate = _make_candidate()
        meta = azimuth_transition.build_cloud_metadata(candidate)
        assert isinstance(meta, azimuth.CloudMetadata)
        assert not hasattr(meta, "raw_text")
        assert not hasattr(meta, "envelope_id")

    def test_reframing_preserve_intent_skeleton(self):
        candidate = _make_candidate()
        with pytest.raises(NotImplementedError):
            azimuth_reframing.preserve_intent(candidate)

    def test_reframing_reframe_candidate_skeleton(self):
        candidate = _make_candidate()
        spec = azimuth_reframing.IntentSpec(
            intention_class=azimuth.IntentionClass.VENT,
            target_action="x", target_state="y",
        )
        with pytest.raises(NotImplementedError):
            azimuth_reframing.reframe_candidate(candidate, spec)

    def test_reframing_score_reframing_skeleton(self):
        candidate = _make_candidate()
        reframing = azimuth.ReframedExpression(
            original_intention="x", reframed_text="y",
            preserved_intent_score=1.0, drift_risk_after=0.0,
        )
        with pytest.raises(NotImplementedError):
            azimuth_reframing.score_reframing(reframing, candidate)

    def test_reframing_run_azimuth_check_skeleton(self):
        candidate = _make_candidate()
        with pytest.raises(NotImplementedError):
            azimuth_reframing.run_azimuth_check(candidate, [])


# ===========================================================================
# Module surface — every documented symbol importable
# ===========================================================================
class TestModuleSurface:
    def test_azimuth_exports(self):
        for name in (
            # Enums
            "Valence", "IntensityLevel", "PressureLevel", "PressureSlope",
            "PressureShape", "AudienceType", "ContextType", "UrgencyLevel",
            "IntentionClass", "UserResponse",
            # Schemas
            "EnvelopeState", "ExpressionCandidate", "CloudMetadata",
            "CloudAdvisory", "ReframedExpression", "AzimuthCheckPrompt",
            # Constants + helpers
            "RISK_FLAGS_CANONICAL",
            "assert_cloud_privacy_contract",
        ):
            assert hasattr(azimuth, name), f"missing in azimuth: {name}"

    def test_envelope_module_exports(self):
        for name in ("capture_envelope", "evaluate_envelope", "mark_externalize"):
            assert hasattr(azimuth_envelope, name), f"missing: {name}"

    def test_transition_module_exports(self):
        for name in (
            "detect_externalization_intent",
            "build_candidate",
            "evaluate_drift_risk",
            "build_cloud_metadata",
        ):
            assert hasattr(azimuth_transition, name), f"missing: {name}"

    def test_reframing_module_exports(self):
        for name in (
            "preserve_intent",
            "reframe_candidate",
            "score_reframing",
            "run_azimuth_check",
            "IntentSpec",
        ):
            assert hasattr(azimuth_reframing, name), f"missing: {name}"


# ===========================================================================
# Cross-module type compatibility
# ===========================================================================
class TestCrossModuleTypes:
    def test_envelope_state_round_trips(self):
        """EnvelopeState created here is the same type the layer
        modules expect."""
        env = _make_envelope()
        # No raise — just confirms the import paths agree.
        assert isinstance(env, azimuth.EnvelopeState)

    def test_intent_spec_consumes_intention_class(self):
        spec = azimuth_reframing.IntentSpec(
            intention_class=azimuth.IntentionClass.REQUEST,
            target_action="ship the doc",
            target_state="reviewer signs off",
            must_preserve=("doc", "Friday"),
        )
        assert spec.intention_class == azimuth.IntentionClass.REQUEST
