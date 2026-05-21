"""
Tests for Phase 3 Unit 5 — Azimuth → FEA Mapping + Integration.

Covers the new live path added to azimuth_transition.py:

    compute_aligned_expression(env: EnvelopeState) -> IntegratedAlignmentResult
    _map_envelope_to_fea_inputs(env) -> (snapshot, geometry, intention)

Test layers:
    A. Type validation
    B. Snapshot field mapping (direct + lexical)
    C. Geometry field mapping (lexical)
    D. Intention field mapping (lexical)
    E. Existing Azimuth stubs preserved
    F. Engine integration (compute_aligned_expression returns valid
       IntegratedAlignmentResult)
    G. Determinism + no mutation
    H. Worked-example end-to-end paths
    I. Source-code purity (no LLM, no I/O, no randomness, no network)
    J. Constants lock + module surface
"""
from __future__ import annotations

import inspect
from datetime import datetime

import pytest

import azimuth_transition as at
from azimuth import (
    EnvelopeState,
    IntensityLevel,
    PressureLevel,
    Valence,
)
from emotional_alignment_schemas import (
    AlignedExpression,
    EmotionalGeometry,
    EmotionalIntention,
    EmotionalSnapshot,
    MeaningNeed,
    RegulationGoal,
    RelationalPosture,
)
from fea_integration_schemas import (
    IntegratedAlignmentResult,
    SurfaceHaltLevel,
)
from language_schemas import ExpressionPrimitive


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


# ===========================================================================
# A. Type validation
# ===========================================================================
class TestTypeValidation:
    def test_compute_rejects_none(self):
        with pytest.raises(ValueError):
            at.compute_aligned_expression(None)  # type: ignore[arg-type]

    def test_compute_rejects_string(self):
        with pytest.raises(ValueError):
            at.compute_aligned_expression("not an envelope")  # type: ignore[arg-type]

    def test_compute_rejects_dict(self):
        with pytest.raises(ValueError):
            at.compute_aligned_expression({"raw_text": "x"})  # type: ignore[arg-type]

    def test_map_rejects_none(self):
        with pytest.raises(ValueError):
            at._map_envelope_to_fea_inputs(None)  # type: ignore[arg-type]

    def test_map_rejects_wrong_type(self):
        with pytest.raises(ValueError):
            at._map_envelope_to_fea_inputs(42)  # type: ignore[arg-type]


# ===========================================================================
# B. Snapshot field mapping
# ===========================================================================
class TestSnapshotMapping:
    @pytest.mark.parametrize("level", list(PressureLevel))
    def test_pressure_level_passthrough(self, level):
        snap, _, _ = at._map_envelope_to_fea_inputs(_env(pressure_level=level))
        assert snap.pressure_level == level

    @pytest.mark.parametrize("intensity", list(IntensityLevel))
    def test_intensity_passthrough(self, intensity):
        snap, _, _ = at._map_envelope_to_fea_inputs(_env(intensity=intensity))
        assert snap.intensity == intensity

    @pytest.mark.parametrize("valence", list(Valence))
    def test_valence_passthrough(self, valence):
        snap, _, _ = at._map_envelope_to_fea_inputs(_env(valence=valence))
        assert snap.valence == valence

    @pytest.mark.parametrize("text,expected", [
        ("I always feel this way", True),
        ("This keeps happening", True),
        ("Every time it's the same", True),
        ("Here we go again", True),
        ("ALWAYS so frustrating", True),         # case-insensitive
        ("a one-time thing", False),
        ("nothing repeating here", False),
    ])
    def test_temporal_linked_lexical(self, text, expected):
        snap, _, _ = at._map_envelope_to_fea_inputs(_env(raw_text=text))
        assert snap.temporal_linked is expected

    @pytest.mark.parametrize("text,expected", [
        ("Remember when we talked about this", True),
        ("Last time it went badly", True),
        ("Ever since the call", True),
        ("Since the meeting", True),
        ("Just thinking aloud", False),
    ])
    def test_anchor_present_lexical(self, text, expected):
        snap, _, _ = at._map_envelope_to_fea_inputs(_env(raw_text=text))
        assert snap.anchor_present is expected

    def test_snapshot_type(self):
        snap, _, _ = at._map_envelope_to_fea_inputs(_env())
        assert isinstance(snap, EmotionalSnapshot)


# ===========================================================================
# C. Geometry field mapping
# ===========================================================================
class TestGeometryMapping:
    @pytest.mark.parametrize("text,expected", [
        ("This always happens", True),
        ("Nobody listens", True),
        ("Everyone is angry", True),
        ("Nothing works", True),
        ("Something specific occurred", False),
    ])
    def test_curvature_lexical(self, text, expected):
        _, geom, _ = at._map_envelope_to_fea_inputs(_env(raw_text=text))
        assert geom.curvature is expected

    def test_torsion_fires_when_conciliatory_intent_meets_attack(self):
        env = _env(
            rough_intention="apologize",
            raw_text="but you always make this worse",
        )
        _, geom, _ = at._map_envelope_to_fea_inputs(env)
        assert geom.torsion is True

    def test_torsion_does_not_fire_without_attack(self):
        env = _env(rough_intention="apologize", raw_text="I want to say sorry")
        _, geom, _ = at._map_envelope_to_fea_inputs(env)
        assert geom.torsion is False

    def test_torsion_does_not_fire_without_conciliatory_intent(self):
        env = _env(rough_intention="vent", raw_text="you always make this worse")
        _, geom, _ = at._map_envelope_to_fea_inputs(env)
        assert geom.torsion is False

    @pytest.mark.parametrize("text,expected", [
        ("I'm worthless", True),
        ("I'm a failure", True),
        ("It's my fault", True),
        ("just observing", False),
    ])
    def test_shear_lexical(self, text, expected):
        _, geom, _ = at._map_envelope_to_fea_inputs(_env(raw_text=text))
        assert geom.shear is expected

    @pytest.mark.parametrize("rough,expected", [
        ("set a limit",  True),
        ("draw a boundary", True),
        ("I won't do it again", True),
        ("describe what happened", False),
    ])
    def test_boundary_from_rough_intention(self, rough, expected):
        _, geom, _ = at._map_envelope_to_fea_inputs(_env(rough_intention=rough))
        assert geom.boundary is expected

    def test_stance_self_clipped_to_unit_interval(self):
        env = _env(raw_text="I'm worthless I'm broken my fault I ruined")
        _, geom, _ = at._map_envelope_to_fea_inputs(env)
        assert 0.0 <= geom.stance_self <= 1.0

    def test_stance_self_zero_when_no_self_attack(self):
        _, geom, _ = at._map_envelope_to_fea_inputs(_env(raw_text="hello"))
        assert geom.stance_self == 0.0

    def test_stance_other_zero_when_no_other_attack(self):
        _, geom, _ = at._map_envelope_to_fea_inputs(_env(raw_text="hello"))
        assert geom.stance_other == 0.0

    def test_stance_world_zero_when_no_world_hostile(self):
        _, geom, _ = at._map_envelope_to_fea_inputs(_env(raw_text="hello"))
        assert geom.stance_world == 0.0

    def test_stance_other_fires_on_accusatory(self):
        env = _env(raw_text="you always do this and it's your fault")
        _, geom, _ = at._map_envelope_to_fea_inputs(env)
        assert geom.stance_other > 0.0

    def test_stance_world_fires_on_world_hostile(self):
        env = _env(raw_text="nobody cares and everything is broken")
        _, geom, _ = at._map_envelope_to_fea_inputs(env)
        assert geom.stance_world > 0.0

    def test_pressure_gradient_is_zero(self):
        """Phase 3 Unit 5 has no history; pressure_gradient locked at 0.0."""
        _, geom, _ = at._map_envelope_to_fea_inputs(_env())
        assert geom.pressure_gradient == 0.0

    def test_geometry_type(self):
        _, geom, _ = at._map_envelope_to_fea_inputs(_env())
        assert isinstance(geom, EmotionalGeometry)


# ===========================================================================
# D. Intention field mapping
# ===========================================================================
class TestIntentionMapping:
    def test_target_state_from_rough_intention(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            rough_intention="say what I really mean",
        ))
        assert intent.target_state == "say what I really mean"

    def test_target_state_stripped(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            rough_intention="   express clearly   ",
        ))
        assert intent.target_state == "express clearly"

    def test_target_state_truncated_at_max_len(self):
        long = "x" * 200
        _, _, intent = at._map_envelope_to_fea_inputs(_env(rough_intention=long))
        assert len(intent.target_state) == at._TARGET_STATE_MAX_LEN

    def test_regulatory_goal_contain(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            rough_intention="contain my anger"))
        assert intent.regulatory_goal == RegulationGoal.CONTAIN

    def test_regulatory_goal_transform(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            rough_intention="transform this pattern"))
        assert intent.regulatory_goal == RegulationGoal.TRANSFORM

    def test_regulatory_goal_express_default(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            rough_intention="describe what happened"))
        assert intent.regulatory_goal == RegulationGoal.EXPRESS

    def test_relational_posture_submit(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            raw_text="i shouldn't bring it up"))
        assert intent.relational_posture == RelationalPosture.SUBMIT

    def test_relational_posture_defend(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            raw_text="you always do this"))
        assert intent.relational_posture == RelationalPosture.DEFEND

    def test_relational_posture_separate(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            raw_text="I need space to think"))
        assert intent.relational_posture == RelationalPosture.SEPARATE

    def test_relational_posture_connect_default(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            raw_text="just describing"))
        assert intent.relational_posture == RelationalPosture.CONNECT

    def test_meaning_need_clarify(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            raw_text="i don't understand what happened"))
        assert intent.meaning_need == MeaningNeed.CLARIFY

    def test_meaning_need_validate(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            raw_text="am i right to feel this way"))
        assert intent.meaning_need == MeaningNeed.VALIDATE

    def test_meaning_need_reframe(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            raw_text="I want to look at this differently"))
        assert intent.meaning_need == MeaningNeed.REFRAME

    def test_meaning_need_none_default(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env(
            raw_text="just describing"))
        assert intent.meaning_need == MeaningNeed.NONE

    def test_intention_type(self):
        _, _, intent = at._map_envelope_to_fea_inputs(_env())
        assert isinstance(intent, EmotionalIntention)


# ===========================================================================
# E. Existing Azimuth stubs preserved (no API mutation)
# ===========================================================================
class TestExistingStubsPreserved:
    def test_detect_externalization_intent_now_implemented_phase_3_unit_9(self):
        """Phase 3 Unit 9 implemented detect_externalization_intent."""
        result = at.detect_externalization_intent(_env())
        assert isinstance(result, bool)

    def test_build_candidate_now_implemented_phase_3_unit_6(self):
        """Phase 3 Unit 6 implemented build_candidate. It is no longer
        a stub — it returns a real ExpressionCandidate with the
        IntegratedAlignmentResult on its ``aligned`` field."""
        from azimuth import AudienceType, ContextType, ExpressionCandidate
        result = at.build_candidate(
            _env(),
            audience=AudienceType.SELF,
            context=ContextType.PERSONAL,
        )
        assert isinstance(result, ExpressionCandidate)
        assert result.aligned is not None

    def test_evaluate_drift_risk_now_implemented_phase_3_unit_7(self):
        """Phase 3 Unit 7 implemented evaluate_drift_risk. It is no
        longer a stub — it takes ``(env, *, candidate)`` and returns a
        new ExpressionCandidate with risk_flags populated."""
        from azimuth import AudienceType, ContextType, ExpressionCandidate
        env = _env()
        c = at.build_candidate(
            env, audience=AudienceType.SELF, context=ContextType.PERSONAL,
        )
        result = at.evaluate_drift_risk(env, candidate=c)
        assert isinstance(result, ExpressionCandidate)

    def test_build_cloud_metadata_now_implemented_phase_3_unit_8(self):
        """Phase 3 Unit 8 implemented build_cloud_metadata. It is no
        longer a stub."""
        from azimuth import AudienceType, ContextType, CloudMetadata
        env = _env()
        c = at.build_candidate(
            env, audience=AudienceType.SELF, context=ContextType.PERSONAL,
        )
        meta = at.build_cloud_metadata(c)
        assert isinstance(meta, CloudMetadata)


# ===========================================================================
# F. Engine integration (compute_aligned_expression)
# ===========================================================================
class TestComputeAlignedExpression:
    def test_returns_integrated_alignment_result(self):
        r = at.compute_aligned_expression(_env())
        assert isinstance(r, IntegratedAlignmentResult)

    def test_aligned_expression_is_real(self):
        r = at.compute_aligned_expression(_env())
        assert isinstance(r.aligned_expression, AlignedExpression)

    def test_aligned_expression_uses_default_primitive(self):
        r = at.compute_aligned_expression(_env())
        assert r.aligned_expression.plan.primitive == ExpressionPrimitive.GEOMETRY

    def test_alignment_score_in_unit_interval(self):
        r = at.compute_aligned_expression(_env())
        assert 0.0 <= r.aligned_expression.alignment_score <= 1.0

    def test_trust_delta_in_unit_interval(self):
        r = at.compute_aligned_expression(_env())
        assert 0.0 <= r.trust_state_delta <= 1.0

    def test_momentum_preserved_true_with_default_session(self):
        """Default SessionContext has no hard stops → momentum intact."""
        r = at.compute_aligned_expression(_env())
        assert r.momentum_preserved is True

    def test_halt_level_is_a_canonical_value(self):
        r = at.compute_aligned_expression(_env())
        assert r.halt_level in set(SurfaceHaltLevel)

    def test_clean_envelope_yields_no_halt(self):
        """Neutral envelope → FEA returns NONE plan + score 0.5 → no halt."""
        r = at.compute_aligned_expression(_env())
        assert r.halt_level == SurfaceHaltLevel.NONE


# ===========================================================================
# G. Determinism + no mutation
# ===========================================================================
class TestDeterminism:
    def test_map_byte_equal(self):
        env = _env(raw_text="I always feel like nobody cares",
                   rough_intention="vent")
        r1 = at._map_envelope_to_fea_inputs(env)
        r2 = at._map_envelope_to_fea_inputs(env)
        assert r1 == r2

    def test_compute_byte_equal(self):
        env = _env(raw_text="I always feel like nobody cares",
                   rough_intention="vent")
        r1 = at.compute_aligned_expression(env)
        r2 = at.compute_aligned_expression(env)
        assert r1 == r2

    def test_envelope_not_mutated_by_map(self):
        env = _env(raw_text="I always feel this way")
        before = (env.raw_text, env.captured_at, env.emotional_intensity,
                  env.valence, env.pressure_level, env.rough_intention,
                  env.user_marked_externalize, env.envelope_id)
        at._map_envelope_to_fea_inputs(env)
        after = (env.raw_text, env.captured_at, env.emotional_intensity,
                 env.valence, env.pressure_level, env.rough_intention,
                 env.user_marked_externalize, env.envelope_id)
        assert before == after

    def test_envelope_not_mutated_by_compute(self):
        env = _env(raw_text="I always feel this way")
        before = (env.raw_text, env.rough_intention, env.envelope_id)
        at.compute_aligned_expression(env)
        after = (env.raw_text, env.rough_intention, env.envelope_id)
        assert before == after


# ===========================================================================
# H. Worked-example end-to-end paths
# ===========================================================================
class TestWorkedExamples:
    def test_91_globalizing_curvature(self):
        """Curvature in raw_text (`always`/`nobody`) should fire SCALE
        in FEA, which reduces pressure (pressure_delta=-1), so no
        PACE/slow surface directive."""
        env = _env(
            raw_text="I always feel like nobody cares",
            pressure_level=PressureLevel.MEDIUM,
            intensity=IntensityLevel.HIGH,
            valence=Valence.NEGATIVE,
            rough_intention="vent",
        )
        r = at.compute_aligned_expression(env)
        # FEA's SCALE reduces pressure → no PACE/slow trigger.
        from fea_integration_schemas import (
            SurfaceDirective, SurfaceDirectiveType,
        )
        pace_slow = SurfaceDirective(
            directive_type=SurfaceDirectiveType.PACE, value="slow",
        )
        assert pace_slow not in r.surface_directives

    def test_92_high_pressure_submit_posture(self):
        """HIGH pressure + SUBMIT posture: FEA emits AGENCY (under HIGH
        path: only AGENCY/SCALE allowed). agency_delta>0 fires
        CHECKPOINT/offer_choice in integration.

        We use a SUBMIT marker (`"i shouldn't"`) rather than world-
        hostile tokens because the world-hostile threshold in FEA is
        `stance_world >= 0.7`, which requires count >= 2.1 → 3+ matching
        phrases. SUBMIT-posture is a simpler, single-marker path.
        """
        env = _env(
            raw_text="I shouldn't say this but nobody listens anyway",
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.HIGH,
            valence=Valence.NEGATIVE,
            rough_intention="vent",
        )
        r = at.compute_aligned_expression(env)
        from fea_integration_schemas import (
            SurfaceDirective, SurfaceDirectiveType,
        )
        checkpoint = SurfaceDirective(
            directive_type=SurfaceDirectiveType.CHECKPOINT,
            value="offer_choice",
        )
        assert checkpoint in r.surface_directives

    def test_93_neutral_envelope(self):
        """Neutral envelope, no markers anywhere → NONE plan, no
        directives, halt=NONE."""
        env = _env()  # all defaults: low pressure, neutral
        r = at.compute_aligned_expression(env)
        assert r.halt_level == SurfaceHaltLevel.NONE
        assert r.surface_directives == ()

    def test_94_temporal_anchor_emits_disclosure(self):
        """temporal_linked + anchor_present fires TEMPORAL in FEA at
        LOW/MEDIUM pressure → DISCLOSURE/single_concept in integration.

        Note: temporal marker is `"keeps"` (with the s); plain "keep"
        does not match. Anchor marker is `"remember when"`.
        """
        env = _env(
            raw_text="This keeps happening — remember when it started",
            pressure_level=PressureLevel.MEDIUM,
            rough_intention="vent",
        )
        r = at.compute_aligned_expression(env)
        from fea_integration_schemas import (
            SurfaceDirective, SurfaceDirectiveType,
        )
        single = SurfaceDirective(
            directive_type=SurfaceDirectiveType.DISCLOSURE,
            value="single_concept",
        )
        assert single in r.surface_directives


# ===========================================================================
# I. Source-code purity
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(at)

    def test_no_llm_imports(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            # Allow the comment-mention of "no LLM calls" in docstrings,
            # but reject any actual import statement.
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

    def test_no_randomness_imports(self):
        src = self._src()
        for forbidden in ("import random", "from random",
                          "import secrets ", "from secrets"):
            # Note: azimuth.py uses `secrets` internally for envelope_id,
            # but we only check this transition module's source.
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
# J. Constants lock + module surface
# ===========================================================================
class TestConstantLocks:
    def test_default_primitive_locked(self):
        assert at._DEFAULT_PRIMITIVE == ExpressionPrimitive.GEOMETRY

    def test_target_state_max_len_locked(self):
        assert at._TARGET_STATE_MAX_LEN == 80

    def test_stance_denom_locked(self):
        assert at._STANCE_DENOM == 3.0


class TestModuleSurface:
    def test_compute_aligned_expression_exported(self):
        assert hasattr(at, "compute_aligned_expression")
        assert callable(at.compute_aligned_expression)

    def test_map_helper_exported(self):
        """Private but importable for tests."""
        assert hasattr(at, "_map_envelope_to_fea_inputs")
        assert callable(at._map_envelope_to_fea_inputs)

    def test_lexical_token_sets_present(self):
        """Sanity — every locked token set is a non-empty tuple."""
        for name in (
            "_TEMPORAL_RECURRENCE_MARKERS", "_MEMORY_ANCHOR_MARKERS",
            "_ABSOLUTIST_TOKENS", "_ACCUSATORY_MARKERS",
            "_CONCILIATORY_INTENT_MARKERS", "_SELF_ATTACK_TOKENS",
            "_OTHER_ATTACK_TOKENS", "_WORLD_HOSTILE_TOKENS",
            "_BOUNDARY_INTENT_TOKENS",
            "_CONTAIN_INTENT_TOKENS", "_EXPRESS_INTENT_TOKENS",
            "_TRANSFORM_INTENT_TOKENS",
            "_SUBMIT_TEXT_MARKERS", "_SEPARATE_TEXT_MARKERS",
            "_DEFEND_TEXT_MARKERS",
            "_CLARIFY_MEANING_MARKERS", "_VALIDATE_MEANING_MARKERS",
            "_REFRAME_MEANING_MARKERS",
        ):
            tokens = getattr(at, name)
            assert isinstance(tokens, tuple)
            assert len(tokens) > 0


# ===========================================================================
# K. Direct vs lazy invocation parity
# ===========================================================================
class TestParityWithDirectCalls:
    """compute_aligned_expression must produce the same
    IntegratedAlignmentResult as a manual call chain through the
    underlying FEA + Ambient Trust + Integration engines."""

    def test_parity_with_manual_pipeline(self):
        from emotional_alignment_engine import align_expression
        from ambient_trust_engine import (
            assess_trust_state, verify_no_hard_stops,
            verify_comprehension_leads_action,
        )
        from fea_integration_engine import integrate_alignment

        env = _env(
            raw_text="I always feel like nobody cares",
            pressure_level=PressureLevel.MEDIUM,
            intensity=IntensityLevel.HIGH,
            valence=Valence.NEGATIVE,
            rough_intention="vent",
        )

        snap, geom, intent = at._map_envelope_to_fea_inputs(env)
        aligned = align_expression(snap, geom, intent, at._DEFAULT_PRIMITIVE)
        session = at._default_session_context()
        trust = assess_trust_state(session)
        propagation = at._default_propagation_state()
        momentum = verify_no_hard_stops(session)
        understanding = verify_comprehension_leads_action(session)
        manual = integrate_alignment(
            aligned=aligned, session=session, trust=trust,
            envelope=env, propagation=propagation,
            momentum=momentum, understanding=understanding,
        )

        live = at.compute_aligned_expression(env)
        assert live == manual
