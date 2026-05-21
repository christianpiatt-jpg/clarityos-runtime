"""
Tests for Phase 3 Unit 6 — build_candidate (real implementation).

Covers:
    A. Schema change — ExpressionCandidate.aligned field
    B. Basic behavior — return type + field population
    C. Intention-class derivation — all 7 cases (6 markers + OTHER)
    D. Explicit intention_class override
    E. Integration with Unit-5 alignment loop
    F. Parity with manual pipeline
    G. Determinism + no mutation
    H. Error handling
    I. Purity (no I/O, no LLM, no randomness, no network)
    J. Existing stubs preserved
"""
from __future__ import annotations

import inspect
from datetime import datetime
from unittest.mock import patch

import pytest

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
from fea_integration_schemas import (
    IntegratedAlignmentResult,
    SurfaceHaltLevel,
)


# ===========================================================================
# Fixture builder
# ===========================================================================
_FIXED_TIME = datetime(2026, 5, 11, 12, 0, 0)


def _env(
    *,
    raw_text: str = "neutral observation",
    pressure_level: PressureLevel = PressureLevel.LOW,
    intensity: IntensityLevel = IntensityLevel.LOW,
    valence: Valence = Valence.NEUTRAL,
    rough_intention: str = "describe what happened",
) -> EnvelopeState:
    return EnvelopeState(
        raw_text=raw_text,
        captured_at=_FIXED_TIME,
        emotional_intensity=intensity,
        valence=valence,
        pressure_level=pressure_level,
        rough_intention=rough_intention,
    )


def _build(env: EnvelopeState, **kwargs) -> ExpressionCandidate:
    """Default the required keyword args; let tests override."""
    kwargs.setdefault("audience", AudienceType.SELF)
    kwargs.setdefault("context", ContextType.PERSONAL)
    return at.build_candidate(env, **kwargs)


# ===========================================================================
# A. Schema change — ExpressionCandidate.aligned field exists + defaults
# ===========================================================================
class TestSchemaChange:
    def test_aligned_field_exists(self):
        assert "aligned" in ExpressionCandidate.__dataclass_fields__

    def test_aligned_defaults_to_none_on_direct_construction(self):
        c = ExpressionCandidate(
            raw_text="x", intention="x",
            intention_class=IntentionClass.OTHER,
            pressure_level=PressureLevel.LOW,
            pressure_slope=PressureSlope.FLAT,
            audience=AudienceType.SELF,
            context=ContextType.PERSONAL,
            urgency=UrgencyLevel.LOW,
        )
        assert c.aligned is None

    def test_aligned_canonical_field_set(self):
        """The full canonical field set is locked here."""
        expected = {
            "raw_text", "intention", "intention_class",
            "pressure_level", "pressure_slope",
            "audience", "context", "urgency",
            "risk_flags", "envelope_id", "candidate_id",
            "aligned",
        }
        assert set(ExpressionCandidate.__dataclass_fields__.keys()) == expected


# ===========================================================================
# B. Basic behavior — return type + field population
# ===========================================================================
class TestBasicBehavior:
    def test_returns_expression_candidate(self):
        c = _build(_env())
        assert isinstance(c, ExpressionCandidate)

    def test_raw_text_passthrough(self):
        c = _build(_env(raw_text="hello world"))
        assert c.raw_text == "hello world"

    def test_intention_passthrough_from_rough_intention(self):
        c = _build(_env(rough_intention="vent about my day"))
        assert c.intention == "vent about my day"

    def test_pressure_level_passthrough(self):
        c = _build(_env(pressure_level=PressureLevel.HIGH))
        assert c.pressure_level == PressureLevel.HIGH

    def test_audience_from_arg(self):
        c = _build(_env(), audience=AudienceType.ONE_TO_ONE)
        assert c.audience == AudienceType.ONE_TO_ONE

    def test_context_from_arg(self):
        c = _build(_env(), context=ContextType.PROFESSIONAL)
        assert c.context == ContextType.PROFESSIONAL

    def test_pressure_slope_from_arg(self):
        c = _build(_env(), pressure_slope=PressureSlope.RISING)
        assert c.pressure_slope == PressureSlope.RISING

    def test_pressure_slope_default_is_flat(self):
        c = _build(_env())
        assert c.pressure_slope == PressureSlope.FLAT

    def test_urgency_from_arg(self):
        c = _build(_env(), urgency=UrgencyLevel.HIGH)
        assert c.urgency == UrgencyLevel.HIGH

    def test_urgency_default_is_low(self):
        c = _build(_env())
        assert c.urgency == UrgencyLevel.LOW

    def test_risk_flags_empty(self):
        """evaluate_drift_risk is still a stub; build_candidate emits ()."""
        c = _build(_env())
        assert c.risk_flags == ()

    def test_envelope_id_back_reference(self):
        env = _env()
        c = _build(env)
        assert c.envelope_id == env.envelope_id

    def test_candidate_id_auto_generated(self):
        c = _build(_env())
        assert c.candidate_id  # non-empty
        c2 = _build(_env())
        assert c.candidate_id != c2.candidate_id  # unique per call


# ===========================================================================
# C. Intention-class derivation — all 7 cases (6 markers + OTHER)
# ===========================================================================
class TestIntentionClassDerivation:
    def test_vent_from_rough_intention(self):
        c = _build(_env(rough_intention="vent about my day"))
        assert c.intention_class == IntentionClass.VENT

    def test_apologize_from_rough_intention(self):
        c = _build(_env(rough_intention="apologize for last night"))
        assert c.intention_class == IntentionClass.APOLOGIZE

    def test_apologize_from_im_sorry_in_raw_text(self):
        c = _build(_env(
            rough_intention="reach out",
            raw_text="I'm sorry for what happened",
        ))
        assert c.intention_class == IntentionClass.APOLOGIZE

    def test_request_from_request_marker(self):
        c = _build(_env(rough_intention="make a request for time off"))
        assert c.intention_class == IntentionClass.REQUEST

    def test_request_from_need_marker(self):
        c = _build(_env(rough_intention="I need help with this"))
        assert c.intention_class == IntentionClass.REQUEST

    def test_request_from_ask_marker(self):
        c = _build(_env(rough_intention="ask about the project"))
        assert c.intention_class == IntentionClass.REQUEST

    def test_boundary_from_boundary_marker(self):
        c = _build(_env(rough_intention="set a boundary about email"))
        assert c.intention_class == IntentionClass.BOUNDARY

    def test_boundary_from_limit_marker(self):
        c = _build(_env(rough_intention="set a limit on hours"))
        assert c.intention_class == IntentionClass.BOUNDARY

    def test_boundary_from_no_word_boundary(self):
        """`no` matches as a whole word, not as substring."""
        c = _build(_env(rough_intention="just say no"))
        assert c.intention_class == IntentionClass.BOUNDARY

    def test_boundary_no_false_positive_on_noticed(self):
        """`noticed` contains `no` as substring but should NOT trip
        BOUNDARY — it should trip OBSERVATION instead."""
        c = _build(_env(rough_intention="I noticed something"))
        assert c.intention_class == IntentionClass.OBSERVATION

    def test_boundary_no_false_positive_on_notify(self):
        """`notify` contains `no` as substring but the `no` regex is
        word-bounded — should fall through to OTHER."""
        c = _build(_env(rough_intention="notify the team"))
        assert c.intention_class == IntentionClass.OTHER

    def test_observation_from_observe_marker(self):
        c = _build(_env(rough_intention="observe what happens"))
        assert c.intention_class == IntentionClass.OBSERVATION

    def test_observation_from_noticed_marker(self):
        c = _build(_env(rough_intention="I noticed a pattern"))
        assert c.intention_class == IntentionClass.OBSERVATION

    def test_gratitude_from_thanks_marker(self):
        c = _build(_env(rough_intention="say thanks for the help"))
        assert c.intention_class == IntentionClass.GRATITUDE

    def test_gratitude_from_appreciate_marker(self):
        c = _build(_env(rough_intention="appreciate the support"))
        assert c.intention_class == IntentionClass.GRATITUDE

    def test_other_when_no_marker_matches(self):
        c = _build(_env(rough_intention="describe what happened"))
        assert c.intention_class == IntentionClass.OTHER

    def test_priority_vent_beats_apologize(self):
        """VENT has highest priority; if both markers appear, VENT wins."""
        c = _build(_env(rough_intention="vent and apologize"))
        assert c.intention_class == IntentionClass.VENT

    def test_priority_apologize_beats_request(self):
        c = _build(_env(rough_intention="apologize and ask for help"))
        assert c.intention_class == IntentionClass.APOLOGIZE

    def test_priority_request_beats_boundary(self):
        c = _build(_env(rough_intention="ask about the boundary"))
        assert c.intention_class == IntentionClass.REQUEST

    def test_priority_boundary_beats_observation(self):
        c = _build(_env(rough_intention="set a boundary, I noticed"))
        assert c.intention_class == IntentionClass.BOUNDARY

    def test_priority_observation_beats_gratitude(self):
        c = _build(_env(rough_intention="I noticed and appreciate it"))
        assert c.intention_class == IntentionClass.OBSERVATION


# ===========================================================================
# D. Explicit intention_class override
# ===========================================================================
class TestIntentionClassOverride:
    def test_explicit_overrides_derivation(self):
        c = _build(
            _env(rough_intention="vent about my day"),
            intention_class=IntentionClass.GRATITUDE,
        )
        assert c.intention_class == IntentionClass.GRATITUDE

    def test_explicit_other_overrides_strong_marker(self):
        """Even with a clear VENT marker, explicit OTHER is honored."""
        c = _build(
            _env(rough_intention="vent vent vent"),
            intention_class=IntentionClass.OTHER,
        )
        assert c.intention_class == IntentionClass.OTHER

    @pytest.mark.parametrize("ic", list(IntentionClass))
    def test_each_intention_class_can_be_set_explicitly(self, ic):
        c = _build(_env(), intention_class=ic)
        assert c.intention_class == ic


# ===========================================================================
# E. Integration with Unit-5 alignment loop
# ===========================================================================
class TestAlignmentLoopIntegration:
    def test_aligned_field_populated(self):
        c = _build(_env())
        assert c.aligned is not None

    def test_aligned_is_integrated_alignment_result(self):
        c = _build(_env())
        assert isinstance(c.aligned, IntegratedAlignmentResult)

    def test_aligned_has_halt_level(self):
        c = _build(_env())
        assert c.aligned.halt_level in set(SurfaceHaltLevel)

    def test_compute_aligned_expression_called_exactly_once(self):
        """build_candidate must call compute_aligned_expression once
        per invocation."""
        with patch.object(
            at, "compute_aligned_expression",
            wraps=at.compute_aligned_expression,
        ) as spy:
            _build(_env())
            assert spy.call_count == 1

    def test_compute_aligned_expression_receives_env(self):
        env = _env()
        with patch.object(
            at, "compute_aligned_expression",
            wraps=at.compute_aligned_expression,
        ) as spy:
            _build(env)
            spy.assert_called_once_with(env)


# ===========================================================================
# F. Parity with manual pipeline
# ===========================================================================
class TestParityWithManualPipeline:
    def test_parity_with_manual_compute_then_construct(self):
        """build_candidate(env) must equal a manual call chain that
        computes alignment separately and constructs the candidate."""
        env = _env(
            raw_text="I always feel like nobody cares",
            rough_intention="vent about my day",
        )

        manual_aligned = at.compute_aligned_expression(env)
        manual_class = at._derive_intention_class(env)

        # Reset random candidate_id by patching the factory.
        with patch("azimuth._new_local_id", return_value="fixed_id"):
            manual = ExpressionCandidate(
                raw_text=env.raw_text,
                intention=env.rough_intention,
                intention_class=manual_class,
                pressure_level=env.pressure_level,
                pressure_slope=PressureSlope.FLAT,
                audience=AudienceType.SELF,
                context=ContextType.PERSONAL,
                urgency=UrgencyLevel.LOW,
                risk_flags=(),
                envelope_id=env.envelope_id,
                aligned=manual_aligned,
            )
            live = at.build_candidate(
                env, audience=AudienceType.SELF,
                context=ContextType.PERSONAL,
            )

        # All fields except candidate_id match (candidate_id auto-generates).
        assert live.raw_text == manual.raw_text
        assert live.intention == manual.intention
        assert live.intention_class == manual.intention_class
        assert live.pressure_level == manual.pressure_level
        assert live.pressure_slope == manual.pressure_slope
        assert live.audience == manual.audience
        assert live.context == manual.context
        assert live.urgency == manual.urgency
        assert live.risk_flags == manual.risk_flags
        assert live.envelope_id == manual.envelope_id
        assert live.aligned == manual.aligned


# ===========================================================================
# G. Determinism + no mutation
# ===========================================================================
class TestDeterminism:
    def test_same_env_same_args_yields_field_equal_candidate(self):
        """Same inputs → same candidate (modulo auto-generated candidate_id)."""
        env = _env(rough_intention="vent")
        c1 = _build(env)
        c2 = _build(env)
        # Compare every field except candidate_id (auto-generated).
        for fname in ExpressionCandidate.__dataclass_fields__:
            if fname == "candidate_id":
                continue
            assert getattr(c1, fname) == getattr(c2, fname)

    def test_aligned_byte_equal_across_calls(self):
        env = _env(rough_intention="vent about it")
        c1 = _build(env)
        c2 = _build(env)
        assert c1.aligned == c2.aligned

    def test_envelope_not_mutated(self):
        env = _env(raw_text="I always feel this way", rough_intention="vent")
        before = (env.raw_text, env.captured_at, env.emotional_intensity,
                  env.valence, env.pressure_level, env.rough_intention,
                  env.user_marked_externalize, env.envelope_id)
        _build(env)
        after = (env.raw_text, env.captured_at, env.emotional_intensity,
                 env.valence, env.pressure_level, env.rough_intention,
                 env.user_marked_externalize, env.envelope_id)
        assert before == after


# ===========================================================================
# H. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_non_envelope_state_raises_value_error(self):
        with pytest.raises(ValueError):
            at.build_candidate(
                "not an envelope",  # type: ignore[arg-type]
                audience=AudienceType.SELF,
                context=ContextType.PERSONAL,
            )

    def test_none_env_raises_value_error(self):
        with pytest.raises(ValueError):
            at.build_candidate(
                None,  # type: ignore[arg-type]
                audience=AudienceType.SELF,
                context=ContextType.PERSONAL,
            )

    def test_dict_env_raises_value_error(self):
        with pytest.raises(ValueError):
            at.build_candidate(
                {"raw_text": "x"},  # type: ignore[arg-type]
                audience=AudienceType.SELF,
                context=ContextType.PERSONAL,
            )

    def test_missing_audience_raises_type_error(self):
        with pytest.raises(TypeError):
            at.build_candidate(_env(), context=ContextType.PERSONAL)  # type: ignore[call-arg]

    def test_missing_context_raises_type_error(self):
        with pytest.raises(TypeError):
            at.build_candidate(_env(), audience=AudienceType.SELF)  # type: ignore[call-arg]

    def test_positional_keyword_args_rejected(self):
        """audience / context are keyword-only — positional calls fail."""
        with pytest.raises(TypeError):
            at.build_candidate(  # type: ignore[misc]
                _env(), AudienceType.SELF, ContextType.PERSONAL,
            )


# ===========================================================================
# I. Purity (no I/O, no LLM, no randomness, no network)
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(at)

    def test_no_llm_imports(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            for line in src.splitlines():
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"'):
                    continue
                assert forbidden not in stripped, (
                    f"unexpected reference to {forbidden} in: {line}"
                )

    def test_no_network_imports(self):
        src = self._src()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket",
                          "from urllib", "from http", "from requests"):
            assert forbidden not in src

    def test_no_io(self):
        src = self._src()
        for forbidden in ("open(", "Path(", "pathlib", "os.path",
                          "json.load", "json.dump", "subprocess",
                          "exec(", "eval("):
            assert forbidden not in src

    def test_no_send_patterns(self):
        src = self._src()
        for forbidden in (".post(", ".put(", ".send(", "urlopen(",
                          "requests.", "smtplib"):
            assert forbidden not in src


# ===========================================================================
# J. Existing stubs preserved (no API mutation in this unit)
# ===========================================================================
class TestExistingStubsPreserved:
    def test_detect_externalization_intent_now_implemented_phase_3_unit_9(self):
        """Phase 3 Unit 9 implemented detect_externalization_intent."""
        result = at.detect_externalization_intent(_env())
        assert isinstance(result, bool)

    def test_evaluate_drift_risk_now_implemented_phase_3_unit_7(self):
        """Phase 3 Unit 7 implemented evaluate_drift_risk with the
        upgraded signature ``(env, *, candidate) -> ExpressionCandidate``.
        It is no longer a stub."""
        env = _env()
        c = _build(env)
        result = at.evaluate_drift_risk(env, candidate=c)
        assert isinstance(result, ExpressionCandidate)

    def test_build_cloud_metadata_now_implemented_phase_3_unit_8(self):
        """Phase 3 Unit 8 implemented build_cloud_metadata. It is no
        longer a stub."""
        from azimuth import CloudMetadata
        env = _env()
        c = _build(env)
        meta = at.build_cloud_metadata(c)
        assert isinstance(meta, CloudMetadata)

    def test_build_candidate_no_longer_stub(self):
        """Phase 3 Unit 6: build_candidate is now implemented."""
        c = _build(_env())
        assert isinstance(c, ExpressionCandidate)


# ===========================================================================
# K. Module surface — derive helper exists
# ===========================================================================
class TestModuleSurface:
    def test_derive_intention_class_exists(self):
        assert hasattr(at, "_derive_intention_class")
        assert callable(at._derive_intention_class)

    def test_intention_marker_tuples_locked(self):
        for name in (
            "_INTENTION_VENT_MARKERS", "_INTENTION_APOLOGIZE_MARKERS",
            "_INTENTION_REQUEST_MARKERS", "_INTENTION_BOUNDARY_PHRASES",
            "_INTENTION_OBSERVATION_MARKERS", "_INTENTION_GRATITUDE_MARKERS",
        ):
            tokens = getattr(at, name)
            assert isinstance(tokens, tuple)
            assert len(tokens) > 0

    def test_boundary_no_regex_word_bounded(self):
        """`no` regex must use \\b boundaries."""
        import re
        pattern = at._INTENTION_BOUNDARY_NO_RE.pattern
        assert r"\bno\b" in pattern
        # Sanity: the regex flags should include IGNORECASE
        assert at._INTENTION_BOUNDARY_NO_RE.flags & re.IGNORECASE
