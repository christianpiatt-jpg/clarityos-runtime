"""
Tests for Phase 3 Unit 7 — evaluate_drift_risk.

Covers:
    A. Basic behavior — return type, non-risk fields unchanged, sorted/dedup
    B. Rule coverage — every documented rule fires (positive) and is
       quiet under negative cases
    C. Combined cases — multiple flags fire together
    D. Alignment-aware behavior (hard_halt, soft_halt)
    E. Determinism + no mutation
    F. Error handling
    G. Purity — no I/O, no LLM, no randomness, no network
    H. Module surface
"""
from __future__ import annotations

import inspect
from datetime import datetime

import pytest

import azimuth
import azimuth_transition as at
from azimuth import (
    AudienceType,
    ContextType,
    EnvelopeState,
    ExpressionCandidate,
    IntensityLevel,
    IntentionClass,
    PressureLevel,
    PressureSlope,
    UrgencyLevel,
    Valence,
)
from emotional_alignment_schemas import (
    AlignedExpression, ReframePlan, ReframeStep, ReframeType,
)
from fea_integration_schemas import (
    IntegratedAlignmentResult, SurfaceHaltLevel,
)
from language_schemas import ExpressionPrimitive


# ===========================================================================
# Fixture builders
# ===========================================================================
_FIXED_TIME = datetime(2026, 5, 11, 12, 0, 0)


def _env(
    *,
    raw_text: str = "neutral observation",
    pressure_level: PressureLevel = PressureLevel.LOW,
    intensity: IntensityLevel = IntensityLevel.MEDIUM,
    valence: Valence = Valence.NEUTRAL,
    rough_intention: str = "describe what happened today",
) -> EnvelopeState:
    return EnvelopeState(
        raw_text=raw_text,
        captured_at=_FIXED_TIME,
        emotional_intensity=intensity,
        valence=valence,
        pressure_level=pressure_level,
        rough_intention=rough_intention,
    )


def _candidate(
    env: EnvelopeState,
    *,
    audience: AudienceType = AudienceType.SELF,
    context: ContextType = ContextType.PERSONAL,
    urgency: UrgencyLevel = UrgencyLevel.LOW,
    intention_class: IntentionClass = IntentionClass.OTHER,
    aligned: IntegratedAlignmentResult = None,
) -> ExpressionCandidate:
    """Build an ExpressionCandidate directly (without invoking
    compute_aligned_expression) so tests can control whether aligned
    is set and what halt_level it carries."""
    return ExpressionCandidate(
        raw_text=env.raw_text,
        intention=env.rough_intention,
        intention_class=intention_class,
        pressure_level=env.pressure_level,
        pressure_slope=PressureSlope.FLAT,
        audience=audience,
        context=context,
        urgency=urgency,
        risk_flags=(),
        envelope_id=env.envelope_id,
        aligned=aligned,
    )


def _aligned_with_halt(level: SurfaceHaltLevel) -> IntegratedAlignmentResult:
    """Build a minimal IntegratedAlignmentResult with the given halt level."""
    plan = ReframePlan(
        steps=(ReframeStep(reframe_type=ReframeType.NONE, rationale="x"),),
        primitive=ExpressionPrimitive.GEOMETRY,
        expected_pressure_delta=0,
        expected_agency_delta=0,
    )
    aligned = AlignedExpression(
        plan=plan, alignment_score=0.5,
        internal_relator_preserved=True, safe_for_surface=True,
    )
    return IntegratedAlignmentResult(
        aligned_expression=aligned,
        halt_level=level,
        trust_state_delta=0.0,
        momentum_preserved=True,
        surface_directives=(),
    )


# ===========================================================================
# A. Basic behavior
# ===========================================================================
class TestBasicBehavior:
    def test_returns_expression_candidate(self):
        env = _env()
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert isinstance(result, ExpressionCandidate)

    def test_returns_new_object(self):
        env = _env()
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert result is not c

    def test_non_risk_fields_unchanged(self):
        env = _env()
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        for fname in ExpressionCandidate.__dataclass_fields__:
            if fname == "risk_flags":
                continue
            assert getattr(result, fname) == getattr(c, fname), (
                f"field {fname} changed unexpectedly"
            )

    def test_risk_flags_is_tuple(self):
        env = _env()
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert isinstance(result.risk_flags, tuple)

    def test_risk_flags_sorted(self):
        env = _env(
            raw_text="you always do this and everyone knows it",
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.HIGH,
        )
        c = _candidate(env, context=ContextType.PROFESSIONAL,
                       audience=AudienceType.ONE_TO_ONE)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert list(result.risk_flags) == sorted(result.risk_flags)

    def test_risk_flags_no_duplicates(self):
        env = _env(
            raw_text="you always you never everyone always",
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.HIGH,
        )
        c = _candidate(env, context=ContextType.PROFESSIONAL)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert len(result.risk_flags) == len(set(result.risk_flags))

    def test_no_flags_for_neutral_envelope(self):
        env = _env()  # all neutral defaults
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert result.risk_flags == ()

    def test_all_emitted_flags_are_canonical(self):
        env = _env(
            raw_text="you always do this everything is broken",
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.HIGH,
        )
        c = _candidate(
            env, context=ContextType.PROFESSIONAL,
            audience=AudienceType.ONE_TO_ONE,
            aligned=_aligned_with_halt(SurfaceHaltLevel.HARD),
        )
        result = at.evaluate_drift_risk(env, candidate=c)
        canonical = set(azimuth.RISK_FLAGS_CANONICAL)
        for f in result.risk_flags:
            assert f in canonical


# ===========================================================================
# B1. sharp_tone rule
# ===========================================================================
class TestSharpToneRule:
    def test_fires_on_high_intensity_one_to_one(self):
        env = _env(intensity=IntensityLevel.HIGH)
        c = _candidate(env, audience=AudienceType.ONE_TO_ONE)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "sharp_tone" in result.risk_flags

    def test_fires_on_extreme_intensity_group(self):
        env = _env(intensity=IntensityLevel.EXTREME)
        c = _candidate(env, audience=AudienceType.SMALL_GROUP)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "sharp_tone" in result.risk_flags

    def test_no_fire_when_audience_self(self):
        env = _env(intensity=IntensityLevel.EXTREME)
        c = _candidate(env, audience=AudienceType.SELF)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "sharp_tone" not in result.risk_flags

    def test_no_fire_when_medium_intensity(self):
        env = _env(intensity=IntensityLevel.MEDIUM)
        c = _candidate(env, audience=AudienceType.ONE_TO_ONE)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "sharp_tone" not in result.risk_flags


# ===========================================================================
# B2. high_pressure rule
# ===========================================================================
class TestHighPressureRule:
    def test_fires_on_high_pressure_professional(self):
        env = _env(pressure_level=PressureLevel.HIGH)
        c = _candidate(env, context=ContextType.PROFESSIONAL)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "high_pressure" in result.risk_flags

    def test_fires_on_critical_pressure_high_stakes(self):
        env = _env(pressure_level=PressureLevel.CRITICAL)
        c = _candidate(env, context=ContextType.HIGH_STAKES)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "high_pressure" in result.risk_flags

    def test_no_fire_on_medium_pressure(self):
        env = _env(pressure_level=PressureLevel.MEDIUM)
        c = _candidate(env, context=ContextType.PROFESSIONAL)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "high_pressure" not in result.risk_flags

    def test_no_fire_on_personal_context(self):
        env = _env(pressure_level=PressureLevel.HIGH)
        c = _candidate(env, context=ContextType.PERSONAL)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "high_pressure" not in result.risk_flags


# ===========================================================================
# B3. vague_target rule
# ===========================================================================
class TestVagueTargetRule:
    def test_fires_on_empty_intention_group(self):
        env = _env(rough_intention="")
        c = _candidate(env, audience=AudienceType.SMALL_GROUP)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "vague_target" in result.risk_flags

    def test_fires_on_one_word_intention_public(self):
        env = _env(rough_intention="vent")
        c = _candidate(env, audience=AudienceType.PUBLIC)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "vague_target" in result.risk_flags

    def test_no_fire_on_multi_word_intention(self):
        env = _env(rough_intention="describe what happened")
        c = _candidate(env, audience=AudienceType.PUBLIC)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "vague_target" not in result.risk_flags

    def test_no_fire_on_one_word_intention_self_audience(self):
        env = _env(rough_intention="vent")
        c = _candidate(env, audience=AudienceType.SELF)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "vague_target" not in result.risk_flags


# ===========================================================================
# B4. name_calling + absolutist_language (joint rule)
# ===========================================================================
class TestNameCallingRule:
    def test_fires_on_you_always(self):
        env = _env(raw_text="you always do this")
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "name_calling" in result.risk_flags
        assert "absolutist_language" in result.risk_flags

    def test_fires_on_you_never(self):
        env = _env(raw_text="you never listen")
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "name_calling" in result.risk_flags
        assert "absolutist_language" in result.risk_flags

    def test_no_fire_on_neutral_text(self):
        env = _env(raw_text="I have a concern")
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "name_calling" not in result.risk_flags


# ===========================================================================
# B5. urgency_inflation rule
# ===========================================================================
class TestUrgencyInflationRule:
    def test_fires_on_three_urgency_markers_with_low_urgency(self):
        env = _env(raw_text="now urgent now urgent now urgent please")
        c = _candidate(env, urgency=UrgencyLevel.LOW)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "urgency_inflation" in result.risk_flags

    def test_no_fire_with_high_urgency_declared(self):
        env = _env(raw_text="now urgent now urgent now urgent")
        c = _candidate(env, urgency=UrgencyLevel.HIGH)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "urgency_inflation" not in result.risk_flags

    def test_no_fire_below_threshold(self):
        env = _env(raw_text="urgent please")  # only 1 marker
        c = _candidate(env, urgency=UrgencyLevel.LOW)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "urgency_inflation" not in result.risk_flags


# ===========================================================================
# B6. ambiguous_request rule
# ===========================================================================
class TestAmbiguousRequestRule:
    def test_fires_on_request_without_action_verb(self):
        # No action verb in raw_text — REQUEST class → ambiguous_request.
        env = _env(raw_text="I have a thought about this matter")
        c = _candidate(env, intention_class=IntentionClass.REQUEST)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "ambiguous_request" in result.risk_flags

    def test_no_fire_with_action_verb(self):
        env = _env(raw_text="can you send me the report")
        c = _candidate(env, intention_class=IntentionClass.REQUEST)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "ambiguous_request" not in result.risk_flags

    def test_no_fire_for_non_request_class(self):
        env = _env(raw_text="just thinking")
        c = _candidate(env, intention_class=IntentionClass.OBSERVATION)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "ambiguous_request" not in result.risk_flags


# ===========================================================================
# B7. soft_tone rule
# ===========================================================================
class TestSoftToneRule:
    def test_fires_on_low_intensity_high_stakes(self):
        env = _env(intensity=IntensityLevel.LOW)
        c = _candidate(env, context=ContextType.HIGH_STAKES)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "soft_tone" in result.risk_flags

    def test_no_fire_on_personal_context(self):
        env = _env(intensity=IntensityLevel.LOW)
        c = _candidate(env, context=ContextType.PERSONAL)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "soft_tone" not in result.risk_flags

    def test_no_fire_on_high_intensity_high_stakes(self):
        env = _env(intensity=IntensityLevel.HIGH)
        c = _candidate(env, context=ContextType.HIGH_STAKES)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "soft_tone" not in result.risk_flags


# ===========================================================================
# B8. passive_aggressive rule
# ===========================================================================
class TestPassiveAggressiveRule:
    def test_fires_on_fine_with_negative_valence(self):
        env = _env(raw_text="fine, whatever you want",
                   valence=Valence.NEGATIVE)
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "passive_aggressive" in result.risk_flags

    def test_fires_on_whatever_with_negative_valence(self):
        env = _env(raw_text="whatever, I'll deal with it",
                   valence=Valence.NEGATIVE)
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "passive_aggressive" in result.risk_flags

    def test_no_fire_without_negative_valence(self):
        env = _env(raw_text="that's fine with me",
                   valence=Valence.NEUTRAL)
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "passive_aggressive" not in result.risk_flags

    def test_no_fire_without_marker(self):
        env = _env(raw_text="I disagree with this approach",
                   valence=Valence.NEGATIVE)
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "passive_aggressive" not in result.risk_flags


# ===========================================================================
# B9. absolutist_language + all_or_nothing rules
# ===========================================================================
class TestAbsolutistLanguageRule:
    def test_fires_on_always(self):
        env = _env(raw_text="this always happens")
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "absolutist_language" in result.risk_flags
        assert "all_or_nothing" in result.risk_flags

    def test_fires_on_never(self):
        env = _env(raw_text="nothing ever works")
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "absolutist_language" in result.risk_flags

    def test_fires_on_everyone(self):
        env = _env(raw_text="everyone is upset")
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "absolutist_language" in result.risk_flags
        assert "all_or_nothing" in result.risk_flags

    def test_word_boundary_no_false_positive_on_call(self):
        """`all` is word-bounded — `call` should NOT trigger."""
        env = _env(raw_text="I have a call to make")
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "absolutist_language" not in result.risk_flags

    def test_no_fire_on_neutral_text(self):
        env = _env(raw_text="a specific concern about scheduling")
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "absolutist_language" not in result.risk_flags


# ===========================================================================
# C. Combined cases — multiple flags fire together
# ===========================================================================
class TestCombinedFlags:
    def test_high_intensity_high_pressure_absolutist(self):
        env = _env(
            raw_text="you always do this and everyone knows it",
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.HIGH,
        )
        c = _candidate(
            env, audience=AudienceType.ONE_TO_ONE,
            context=ContextType.PROFESSIONAL,
        )
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "sharp_tone" in result.risk_flags
        assert "high_pressure" in result.risk_flags
        assert "name_calling" in result.risk_flags
        assert "absolutist_language" in result.risk_flags
        assert "all_or_nothing" in result.risk_flags

    def test_passive_aggressive_plus_absolutist(self):
        env = _env(
            raw_text="fine, nothing ever works around here",
            valence=Valence.NEGATIVE,
        )
        c = _candidate(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "passive_aggressive" in result.risk_flags
        assert "absolutist_language" in result.risk_flags


# ===========================================================================
# D. Alignment-aware behavior (hard_halt, soft_halt)
# ===========================================================================
class TestAlignmentAware:
    def test_hard_halt_fires_when_aligned_is_hard(self):
        env = _env()
        c = _candidate(env, aligned=_aligned_with_halt(SurfaceHaltLevel.HARD))
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "hard_halt" in result.risk_flags

    def test_soft_halt_fires_when_aligned_is_soft(self):
        env = _env()
        c = _candidate(env, aligned=_aligned_with_halt(SurfaceHaltLevel.SOFT))
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "soft_halt" in result.risk_flags

    def test_no_halt_flag_when_aligned_is_none_level(self):
        env = _env()
        c = _candidate(env, aligned=_aligned_with_halt(SurfaceHaltLevel.NONE))
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "hard_halt" not in result.risk_flags
        assert "soft_halt" not in result.risk_flags

    def test_no_halt_flag_when_aligned_field_is_none(self):
        env = _env()
        c = _candidate(env, aligned=None)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert "hard_halt" not in result.risk_flags
        assert "soft_halt" not in result.risk_flags

    def test_hard_halt_and_soft_halt_are_mutually_exclusive(self):
        """A single result can never carry both — halt_level is one enum
        member at a time."""
        env = _env()
        for level in (SurfaceHaltLevel.HARD, SurfaceHaltLevel.SOFT):
            c = _candidate(env, aligned=_aligned_with_halt(level))
            result = at.evaluate_drift_risk(env, candidate=c)
            both = ("hard_halt" in result.risk_flags
                    and "soft_halt" in result.risk_flags)
            assert not both

    def test_parity_manual_vs_compute_aligned(self):
        """Building the candidate via build_candidate (which runs the
        Unit-5 alignment loop) should yield the same risk_flags as
        building it manually with the same IntegratedAlignmentResult."""
        env = _env(
            raw_text="describe what happened today",
            rough_intention="describe what happened",
        )

        # Path 1 — full pipeline through build_candidate (sets aligned).
        live = at.build_candidate(
            env, audience=AudienceType.SELF, context=ContextType.PERSONAL,
        )
        live_evaluated = at.evaluate_drift_risk(env, candidate=live)

        # Path 2 — manual: compute aligned, build candidate by hand,
        # evaluate.
        manual_aligned = at.compute_aligned_expression(env)
        manual = _candidate(env, aligned=manual_aligned)
        manual_evaluated = at.evaluate_drift_risk(env, candidate=manual)

        assert live_evaluated.risk_flags == manual_evaluated.risk_flags


# ===========================================================================
# E. Determinism + no mutation
# ===========================================================================
class TestDeterminism:
    def test_same_inputs_same_flags(self):
        env = _env(
            raw_text="you always do this and everyone knows",
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.HIGH,
        )
        c = _candidate(env, context=ContextType.PROFESSIONAL,
                       audience=AudienceType.ONE_TO_ONE,
                       aligned=_aligned_with_halt(SurfaceHaltLevel.HARD))
        r1 = at.evaluate_drift_risk(env, candidate=c)
        r2 = at.evaluate_drift_risk(env, candidate=c)
        assert r1.risk_flags == r2.risk_flags

    def test_envelope_not_mutated(self):
        env = _env(raw_text="you always do this", intensity=IntensityLevel.HIGH)
        c = _candidate(env, audience=AudienceType.ONE_TO_ONE)
        before = (env.raw_text, env.captured_at, env.emotional_intensity,
                  env.valence, env.pressure_level, env.rough_intention,
                  env.envelope_id)
        at.evaluate_drift_risk(env, candidate=c)
        after = (env.raw_text, env.captured_at, env.emotional_intensity,
                 env.valence, env.pressure_level, env.rough_intention,
                 env.envelope_id)
        assert before == after

    def test_candidate_not_mutated(self):
        env = _env(raw_text="you always do this", intensity=IntensityLevel.HIGH)
        c = _candidate(env, audience=AudienceType.ONE_TO_ONE)
        original_risk_flags = c.risk_flags
        original_candidate_id = c.candidate_id
        at.evaluate_drift_risk(env, candidate=c)
        # Input candidate untouched — only a new instance carries flags.
        assert c.risk_flags == original_risk_flags
        assert c.candidate_id == original_candidate_id


# ===========================================================================
# F. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_non_envelope_state_raises_value_error(self):
        c = _candidate(_env())
        with pytest.raises(ValueError):
            at.evaluate_drift_risk("not an env", candidate=c)  # type: ignore[arg-type]

    def test_none_env_raises_value_error(self):
        c = _candidate(_env())
        with pytest.raises(ValueError):
            at.evaluate_drift_risk(None, candidate=c)  # type: ignore[arg-type]

    def test_non_candidate_raises_value_error(self):
        env = _env()
        with pytest.raises(ValueError):
            at.evaluate_drift_risk(env, candidate="not a candidate")  # type: ignore[arg-type]

    def test_none_candidate_raises_value_error(self):
        env = _env()
        with pytest.raises(ValueError):
            at.evaluate_drift_risk(env, candidate=None)  # type: ignore[arg-type]

    def test_missing_candidate_kwarg_raises_type_error(self):
        env = _env()
        with pytest.raises(TypeError):
            at.evaluate_drift_risk(env)  # type: ignore[call-arg]

    def test_positional_candidate_rejected(self):
        env = _env()
        c = _candidate(env)
        with pytest.raises(TypeError):
            at.evaluate_drift_risk(env, c)  # type: ignore[misc]


# ===========================================================================
# G. Purity — no I/O, no LLM, no randomness, no network
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(at.evaluate_drift_risk)

    def test_no_llm_imports_in_function(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_calls_in_function(self):
        src = self._src()
        for forbidden in ("urlopen(", "requests.", ".post(", ".put("):
            assert forbidden not in src

    def test_no_io_in_function(self):
        src = self._src()
        for forbidden in ("open(", "Path(", "json.load", "subprocess",
                          "exec(", "eval("):
            assert forbidden not in src

    def test_no_randomness_in_function(self):
        src = self._src()
        for forbidden in ("random.", "secrets.token"):
            assert forbidden not in src


# ===========================================================================
# H. Module surface + helpers
# ===========================================================================
class TestModuleSurface:
    def test_evaluate_drift_risk_callable(self):
        assert callable(at.evaluate_drift_risk)

    def test_marker_tuples_locked(self):
        for name in (
            "_NAME_CALLING_TOKENS", "_ABSOLUTIST_TEXT_TOKENS",
            "_PASSIVE_AGGRESSIVE_TOKENS", "_URGENCY_MARKERS",
            "_ACTION_VERBS",
        ):
            tokens = getattr(at, name)
            assert isinstance(tokens, tuple)
            assert len(tokens) > 0

    def test_high_pressure_levels_locked(self):
        assert PressureLevel.HIGH in at._HIGH_PRESSURE_LEVELS
        assert PressureLevel.CRITICAL in at._HIGH_PRESSURE_LEVELS
        assert PressureLevel.LOW not in at._HIGH_PRESSURE_LEVELS
        assert PressureLevel.MEDIUM not in at._HIGH_PRESSURE_LEVELS


# ===========================================================================
# I. Existing pipeline stubs preserved (only this unit's stub now implemented)
# ===========================================================================
class TestPipelineStubsPreserved:
    def test_detect_externalization_intent_now_implemented_phase_3_unit_9(self):
        """Phase 3 Unit 9 implemented detect_externalization_intent.
        It is no longer a stub — it returns a bool."""
        result = at.detect_externalization_intent(_env())
        assert isinstance(result, bool)

    def test_build_cloud_metadata_now_implemented_phase_3_unit_8(self):
        """Phase 3 Unit 8 implemented build_cloud_metadata. It is no
        longer a stub — given an ExpressionCandidate, it returns a
        CloudMetadata fingerprint."""
        from azimuth import CloudMetadata
        env = _env()
        c = at.build_candidate(
            env, audience=AudienceType.SELF, context=ContextType.PERSONAL,
        )
        meta = at.build_cloud_metadata(c)
        assert isinstance(meta, CloudMetadata)

    def test_build_candidate_implemented(self):
        c = at.build_candidate(
            _env(), audience=AudienceType.SELF, context=ContextType.PERSONAL,
        )
        assert isinstance(c, ExpressionCandidate)

    def test_evaluate_drift_risk_implemented(self):
        result = at.evaluate_drift_risk(_env(), candidate=_candidate(_env()))
        assert isinstance(result, ExpressionCandidate)
