"""
Tests for the Feedback Ingestion System (FIS).

Two layers:
    1. Structural — enums / schemas / privacy contract / mapping tables.
    2. Behavioral — extract_pattern() against concrete submissions
       producing the expected FeedbackPattern.

The engine is pure and deterministic, so behavioral tests assert
byte-equal returns. No mocking required — no I/O exists to mock.
"""
from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

import feedback_schemas as fs
import ingestion_engine as engine

from azimuth import PressureLevel
from language_schemas import ConversationMode, ExpressionPrimitive


# ===========================================================================
# Fixture builders
# ===========================================================================
def _submission(
    *,
    text: str = "feedback content",
    mode: ConversationMode = ConversationMode.OPERATOR,
    pressure_level: PressureLevel = PressureLevel.LOW,
    primitive_used: ExpressionPrimitive = ExpressionPrimitive.GEOMETRY,
) -> fs.FeedbackSubmission:
    return fs.FeedbackSubmission(
        text=text,
        mode=mode,
        pressure_level=pressure_level,
        primitive_used=primitive_used,
        timestamp=datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc),
    )


# ===========================================================================
# A. Enums
# ===========================================================================
class TestEnums:
    def test_signal_type_values(self):
        assert {v.value for v in fs.SignalType} == {
            "positive", "negative", "neutral",
        }

    def test_pattern_type_values(self):
        assert {v.value for v in fs.PatternType} == {
            "tone", "drift", "pressure", "alignment", "boundary", "use_case",
        }

    def test_pattern_type_count(self):
        assert len(fs.PatternType) == 6

    def test_signal_type_count(self):
        assert len(fs.SignalType) == 3

    def test_primitive_type_aliased(self):
        """PrimitiveType is aliased to ExpressionPrimitive — same enum."""
        assert fs.PrimitiveType is ExpressionPrimitive


# ===========================================================================
# B. Schemas — frozen + instantiable
# ===========================================================================
class TestFeedbackSubmission:
    def test_instantiable(self):
        s = _submission()
        assert s.text == "feedback content"
        assert s.mode == ConversationMode.OPERATOR

    def test_frozen(self):
        s = _submission()
        with pytest.raises(FrozenInstanceError):
            s.text = "modified"  # type: ignore[misc]


class TestFeedbackPattern:
    def test_instantiable(self):
        p = fs.FeedbackPattern(
            pattern_type=fs.PatternType.TONE,
            context=ConversationMode.EMOTIONAL,
            pressure_level=PressureLevel.MEDIUM,
            signal=fs.SignalType.NEGATIVE,
            primitive_involved=ExpressionPrimitive.HYDRONICS,
            suggested_adjustment="Soften tone",
        )
        assert p.pattern_type == fs.PatternType.TONE

    def test_frozen(self):
        p = fs.FeedbackPattern(
            pattern_type=fs.PatternType.TONE,
            context=ConversationMode.EMOTIONAL,
            pressure_level=PressureLevel.MEDIUM,
            signal=fs.SignalType.NEUTRAL,
            primitive_involved=ExpressionPrimitive.HYDRONICS,
            suggested_adjustment="x",
        )
        with pytest.raises(FrozenInstanceError):
            p.pattern_type = fs.PatternType.DRIFT  # type: ignore[misc]


class TestExtractionContext:
    def test_instantiable_with_defaults(self):
        ctx = fs.ExtractionContext()
        assert ctx.last_pattern_type is None
        assert ctx.last_pressure is None
        assert ctx.last_mode is None

    def test_instantiable_with_values(self):
        ctx = fs.ExtractionContext(
            last_pattern_type=fs.PatternType.ALIGNMENT,
            last_pressure=PressureLevel.LOW,
            last_mode=ConversationMode.OPERATOR,
        )
        assert ctx.last_pattern_type == fs.PatternType.ALIGNMENT

    def test_frozen(self):
        ctx = fs.ExtractionContext()
        with pytest.raises(FrozenInstanceError):
            ctx.last_pattern_type = fs.PatternType.TONE  # type: ignore[misc]


# ===========================================================================
# C. Privacy contract — FeedbackPattern carries no text, no identity
# ===========================================================================
class TestPrivacyContract:
    def test_no_text_field(self):
        assert "text" not in fs.FeedbackPattern.__dataclass_fields__

    def test_no_raw_text_field(self):
        assert "raw_text" not in fs.FeedbackPattern.__dataclass_fields__

    def test_no_user_id_field(self):
        assert "user_id" not in fs.FeedbackPattern.__dataclass_fields__

    def test_no_actor_field(self):
        assert "actor" not in fs.FeedbackPattern.__dataclass_fields__

    def test_no_session_id_field(self):
        assert "session_id" not in fs.FeedbackPattern.__dataclass_fields__

    def test_no_identity_field(self):
        assert "identity" not in fs.FeedbackPattern.__dataclass_fields__

    def test_no_envelope_id_field(self):
        assert "envelope_id" not in fs.FeedbackPattern.__dataclass_fields__

    def test_no_name_or_names_fields(self):
        for forbidden in ("name", "names", "user", "author"):
            assert forbidden not in fs.FeedbackPattern.__dataclass_fields__

    def test_canonical_six_fields_exact(self):
        expected = {
            "pattern_type", "context", "pressure_level",
            "signal", "primitive_involved", "suggested_adjustment",
        }
        assert set(fs.FeedbackPattern.__dataclass_fields__.keys()) == expected

    def test_runtime_privacy_guard(self):
        fs.assert_pattern_privacy_contract()  # must not raise

    def test_runtime_field_set_guard(self):
        fs.assert_pattern_field_set_canonical()  # must not raise


# ===========================================================================
# D. Mapping tables — coverage
# ===========================================================================
class TestMappingTables:
    def test_adjustment_table_covers_all_pattern_types(self):
        for pattern_type in fs.PatternType:
            assert pattern_type in engine._ADJUSTMENT_TABLE, (
                f"missing adjustment for {pattern_type.value}"
            )
            assert engine._ADJUSTMENT_TABLE[pattern_type]  # non-empty

    def test_mode_to_pattern_covers_all_modes(self):
        for mode in ConversationMode:
            assert mode in engine._MODE_TO_PATTERN

    def test_primitive_to_pattern_covers_all_primitives(self):
        for primitive in ExpressionPrimitive:
            assert primitive in engine._PRIMITIVE_TO_PATTERN

    def test_mode_to_pattern_spec_values(self):
        assert engine._MODE_TO_PATTERN[ConversationMode.OPERATOR]    == fs.PatternType.ALIGNMENT
        assert engine._MODE_TO_PATTERN[ConversationMode.DECISION]    == fs.PatternType.USE_CASE
        assert engine._MODE_TO_PATTERN[ConversationMode.EMOTIONAL]   == fs.PatternType.TONE
        assert engine._MODE_TO_PATTERN[ConversationMode.STRUCTURAL]  == fs.PatternType.ALIGNMENT
        assert engine._MODE_TO_PATTERN[ConversationMode.EXPLORATORY] == fs.PatternType.USE_CASE

    def test_primitive_to_pattern_spec_values(self):
        assert engine._PRIMITIVE_TO_PATTERN[ExpressionPrimitive.HYDRONICS] == fs.PatternType.PRESSURE
        assert engine._PRIMITIVE_TO_PATTERN[ExpressionPrimitive.GEOMETRY]  == fs.PatternType.ALIGNMENT
        assert engine._PRIMITIVE_TO_PATTERN[ExpressionPrimitive.MOTION]    == fs.PatternType.DRIFT
        assert engine._PRIMITIVE_TO_PATTERN[ExpressionPrimitive.ANALOGY]   == fs.PatternType.USE_CASE


# ===========================================================================
# E. Pressure overrides (Rule 1)
# ===========================================================================
class TestPressureOverride:
    def test_high_pressure_forces_pressure_pattern(self):
        s = _submission(pressure_level=PressureLevel.HIGH,
                        mode=ConversationMode.OPERATOR)  # would be ALIGNMENT
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.PRESSURE

    def test_critical_pressure_forces_pressure_pattern(self):
        s = _submission(pressure_level=PressureLevel.CRITICAL,
                        mode=ConversationMode.DECISION)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.PRESSURE

    def test_high_pressure_overrides_drift_marker(self):
        """Rule 1 has higher priority than rule 2."""
        s = _submission(
            text="this was confusing",
            pressure_level=PressureLevel.HIGH,
            mode=ConversationMode.OPERATOR,
        )
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.PRESSURE

    def test_medium_pressure_does_not_override(self):
        s = _submission(pressure_level=PressureLevel.MEDIUM,
                        mode=ConversationMode.OPERATOR)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.ALIGNMENT  # mode wins

    def test_low_pressure_does_not_override(self):
        s = _submission(pressure_level=PressureLevel.LOW,
                        mode=ConversationMode.EMOTIONAL)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.TONE


# ===========================================================================
# F. Drift overrides (Rule 2) — every documented marker
# ===========================================================================
class TestDriftOverride:
    @pytest.mark.parametrize("text", [
        "this caused drift in my workflow",
        "got confused halfway through",
        "felt like a mismatch with what I wanted",
        "noticed some misalignment with my intent",
        "lost the thread of the conversation",
        "the agent wandered off topic",
        "went off track from what I was asking",
    ])
    def test_drift_marker_in_text_forces_drift_pattern(self, text):
        s = _submission(text=text, mode=ConversationMode.OPERATOR,
                        pressure_level=PressureLevel.LOW)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.DRIFT

    def test_drift_marker_overrides_mode(self):
        s = _submission(text="this was confusing",
                        mode=ConversationMode.STRUCTURAL,  # would be ALIGNMENT
                        pressure_level=PressureLevel.LOW)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.DRIFT

    def test_no_drift_markers_lets_mode_win(self):
        s = _submission(text="this was great",
                        mode=ConversationMode.STRUCTURAL,
                        pressure_level=PressureLevel.LOW)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.ALIGNMENT


# ===========================================================================
# G. Mode-driven selection (Rules 3-7)
# ===========================================================================
class TestModeDrivenSelection:
    def test_operator_mode_to_alignment(self):
        s = _submission(mode=ConversationMode.OPERATOR)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.ALIGNMENT

    def test_decision_mode_to_use_case(self):
        s = _submission(mode=ConversationMode.DECISION)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.USE_CASE

    def test_emotional_mode_to_tone(self):
        s = _submission(mode=ConversationMode.EMOTIONAL)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.TONE

    def test_structural_mode_to_alignment(self):
        s = _submission(mode=ConversationMode.STRUCTURAL)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.ALIGNMENT

    def test_exploratory_mode_to_use_case(self):
        s = _submission(mode=ConversationMode.EXPLORATORY)
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.USE_CASE


# ===========================================================================
# H. Signal detection
# ===========================================================================
class TestSignalDetection:
    @pytest.mark.parametrize("text", [
        "this was helpful",
        "really good feedback",
        "worked perfectly",
        "very clear",
        "effective response",
        "great work",
        "useful pattern",
        "love it",
        "really appreciate that",
        "thanks for the help",
    ])
    def test_positive_markers_return_positive(self, text):
        s = _submission(text=text)
        p = engine.extract_pattern(s)
        assert p.signal == fs.SignalType.POSITIVE

    @pytest.mark.parametrize("text", [
        "this was wrong",
        "felt bad",
        "missed the point",
        "too harsh",
        "tone was sharp",
        "system felt broken",
        "really frustrating",
        "didn't land",
        "doesn't work for me",
        "couldn't follow",
        "fail to see why",
        "poor response",
    ])
    def test_negative_markers_return_negative(self, text):
        s = _submission(text=text)
        p = engine.extract_pattern(s)
        assert p.signal == fs.SignalType.NEGATIVE

    def test_no_markers_return_neutral(self):
        s = _submission(text="recorded a thought about the system")
        p = engine.extract_pattern(s)
        assert p.signal == fs.SignalType.NEUTRAL

    def test_tie_negative_wins(self):
        """Per spec: negative wins on tie (safer default)."""
        s = _submission(text="this was helpful but felt wrong")
        p = engine.extract_pattern(s)
        assert p.signal == fs.SignalType.NEGATIVE

    def test_empty_text_neutral(self):
        s = _submission(text="")
        p = engine.extract_pattern(s)
        assert p.signal == fs.SignalType.NEUTRAL

    def test_case_insensitive_signal(self):
        s = _submission(text="THIS WAS HELPFUL")
        p = engine.extract_pattern(s)
        assert p.signal == fs.SignalType.POSITIVE


# ===========================================================================
# I. Suggested adjustment — canonical strings only
# ===========================================================================
class TestSuggestedAdjustment:
    def test_pressure_adjustment(self):
        s = _submission(pressure_level=PressureLevel.HIGH)
        p = engine.extract_pattern(s)
        assert p.suggested_adjustment == engine._ADJUSTMENT_TABLE[fs.PatternType.PRESSURE]

    def test_drift_adjustment(self):
        s = _submission(text="lost the thread")
        p = engine.extract_pattern(s)
        assert p.suggested_adjustment == engine._ADJUSTMENT_TABLE[fs.PatternType.DRIFT]

    def test_tone_adjustment(self):
        s = _submission(mode=ConversationMode.EMOTIONAL)
        p = engine.extract_pattern(s)
        assert p.suggested_adjustment == engine._ADJUSTMENT_TABLE[fs.PatternType.TONE]

    def test_alignment_adjustment(self):
        s = _submission(mode=ConversationMode.STRUCTURAL)
        p = engine.extract_pattern(s)
        assert p.suggested_adjustment == engine._ADJUSTMENT_TABLE[fs.PatternType.ALIGNMENT]

    def test_use_case_adjustment(self):
        s = _submission(mode=ConversationMode.DECISION)
        p = engine.extract_pattern(s)
        assert p.suggested_adjustment == engine._ADJUSTMENT_TABLE[fs.PatternType.USE_CASE]

    def test_adjustment_is_never_user_text(self):
        """No matter what text the user supplies, the adjustment must
        come from the canonical table — never echo user text."""
        s = _submission(text="please record this verbatim message")
        p = engine.extract_pattern(s)
        assert "verbatim message" not in p.suggested_adjustment


# ===========================================================================
# J. Worked examples from SPEC § 9
# ===========================================================================
class TestWorkedExamples:
    def test_example_91_tone_too_sharp(self):
        s = _submission(
            text="Tone too sharp under pressure",
            mode=ConversationMode.EMOTIONAL,
            pressure_level=PressureLevel.MEDIUM,
            primitive_used=ExpressionPrimitive.HYDRONICS,
        )
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.TONE
        assert p.signal       == fs.SignalType.NEGATIVE
        assert p.context      == ConversationMode.EMOTIONAL
        assert p.primitive_involved == ExpressionPrimitive.HYDRONICS

    def test_example_92_wanted_more_structure(self):
        s = _submission(
            text="Wanted more structure in decision mode",
            mode=ConversationMode.DECISION,
            pressure_level=PressureLevel.LOW,
            primitive_used=ExpressionPrimitive.MOTION,
        )
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.USE_CASE
        assert p.signal       == fs.SignalType.NEUTRAL

    def test_example_93_analogy_helped_reduce_drift(self):
        s = _submission(
            text="Analogy helped reduce drift",
            mode=ConversationMode.EXPLORATORY,
            pressure_level=PressureLevel.LOW,
            primitive_used=ExpressionPrimitive.ANALOGY,
        )
        p = engine.extract_pattern(s)
        # "drift" triggers rule 2 override before mode would map to USE_CASE
        assert p.pattern_type == fs.PatternType.DRIFT
        assert p.signal       == fs.SignalType.POSITIVE

    def test_example_94_frustrating_under_high_pressure(self):
        s = _submission(
            text="System felt frustrating under high pressure",
            mode=ConversationMode.OPERATOR,
            pressure_level=PressureLevel.HIGH,
            primitive_used=ExpressionPrimitive.GEOMETRY,
        )
        p = engine.extract_pattern(s)
        # Rule 1 fires (HIGH pressure)
        assert p.pattern_type == fs.PatternType.PRESSURE
        assert p.signal       == fs.SignalType.NEGATIVE  # "frustrat" → NEGATIVE

    def test_example_95_clear_and_helpful(self):
        s = _submission(
            text="Clear and helpful — good alignment with my goal",
            mode=ConversationMode.STRUCTURAL,
            pressure_level=PressureLevel.LOW,
            primitive_used=ExpressionPrimitive.GEOMETRY,
        )
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.ALIGNMENT
        assert p.signal       == fs.SignalType.POSITIVE


# ===========================================================================
# K. Determinism (Invariant #3)
# ===========================================================================
class TestDeterminism:
    def test_same_submission_byte_equal(self):
        s = _submission(text="great work")
        p1 = engine.extract_pattern(s)
        p2 = engine.extract_pattern(s)
        assert p1 == p2

    def test_multiple_calls_consistent(self):
        s = _submission(text="totally helpful")
        patterns = [engine.extract_pattern(s) for _ in range(5)]
        assert all(p == patterns[0] for p in patterns)

    def test_different_text_different_signal(self):
        s_pos = _submission(text="helpful and clear")
        s_neg = _submission(text="missed the mark badly")
        assert engine.extract_pattern(s_pos).signal != engine.extract_pattern(s_neg).signal

    def test_determinism_across_modes(self):
        for mode in ConversationMode:
            s = _submission(mode=mode)
            p1 = engine.extract_pattern(s)
            p2 = engine.extract_pattern(s)
            assert p1 == p2, f"non-deterministic for mode={mode.value}"


# ===========================================================================
# L. Whiplash prevention
# ===========================================================================
class TestWhiplashPrevention:
    def test_no_ctx_means_no_whiplash_check(self):
        s = _submission(mode=ConversationMode.EMOTIONAL)
        p = engine.extract_pattern(s, ctx=None)
        assert p.pattern_type == fs.PatternType.TONE  # straight mode mapping

    def test_continuity_preserved_when_no_change(self):
        """Last TONE + same mode + same pressure → stay TONE even though
        candidate would be ALIGNMENT."""
        s = _submission(
            mode=ConversationMode.STRUCTURAL,  # → ALIGNMENT naively
            pressure_level=PressureLevel.LOW,
        )
        ctx = fs.ExtractionContext(
            last_pattern_type=fs.PatternType.TONE,
            last_pressure=PressureLevel.LOW,
            last_mode=ConversationMode.STRUCTURAL,
        )
        p = engine.extract_pattern(s, ctx=ctx)
        assert p.pattern_type == fs.PatternType.TONE

    def test_mode_change_bypasses_whiplash(self):
        s = _submission(
            mode=ConversationMode.EMOTIONAL,
            pressure_level=PressureLevel.LOW,
        )
        ctx = fs.ExtractionContext(
            last_pattern_type=fs.PatternType.ALIGNMENT,
            last_pressure=PressureLevel.LOW,
            last_mode=ConversationMode.OPERATOR,  # changed
        )
        p = engine.extract_pattern(s, ctx=ctx)
        # Mode changed → switch is allowed → TONE (EMOTIONAL mode)
        assert p.pattern_type == fs.PatternType.TONE

    def test_pressure_change_bypasses_whiplash(self):
        s = _submission(
            mode=ConversationMode.STRUCTURAL,
            pressure_level=PressureLevel.MEDIUM,  # changed
        )
        ctx = fs.ExtractionContext(
            last_pattern_type=fs.PatternType.TONE,
            last_pressure=PressureLevel.LOW,  # was LOW
            last_mode=ConversationMode.STRUCTURAL,
        )
        p = engine.extract_pattern(s, ctx=ctx)
        # Pressure changed → switch is allowed → ALIGNMENT (STRUCTURAL mode)
        assert p.pattern_type == fs.PatternType.ALIGNMENT

    def test_hard_override_bypasses_whiplash(self):
        """HIGH pressure ALWAYS produces PRESSURE, regardless of last."""
        s = _submission(
            mode=ConversationMode.OPERATOR,
            pressure_level=PressureLevel.HIGH,
        )
        ctx = fs.ExtractionContext(
            last_pattern_type=fs.PatternType.TONE,
            last_pressure=PressureLevel.HIGH,
            last_mode=ConversationMode.OPERATOR,
        )
        p = engine.extract_pattern(s, ctx=ctx)
        assert p.pattern_type == fs.PatternType.PRESSURE

    def test_drift_override_bypasses_whiplash(self):
        s = _submission(
            text="got confused",
            mode=ConversationMode.OPERATOR,
            pressure_level=PressureLevel.LOW,
        )
        ctx = fs.ExtractionContext(
            last_pattern_type=fs.PatternType.TONE,
            last_pressure=PressureLevel.LOW,
            last_mode=ConversationMode.OPERATOR,
        )
        p = engine.extract_pattern(s, ctx=ctx)
        assert p.pattern_type == fs.PatternType.DRIFT


# ===========================================================================
# M. Source-code invariants (Invariants 4, 5, 6, 7, 8)
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
        src = self._src(fs)
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_imports_in_engine(self):
        src = self._src(engine)
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket",
                          "from urllib", "from http"):
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
        """Invariant #8: no auto-send."""
        src = self._src(engine)
        for forbidden in (".post(", ".put(", ".send(",
                          "urlopen(", "requests.", "smtplib"):
            assert forbidden not in src


# ===========================================================================
# N. Output text invariant — no user text leaks
# ===========================================================================
class TestOutputDoesNotLeakUserText:
    def test_user_text_does_not_appear_in_pattern(self):
        unique_phrase = "ZyxQwertUniqueMarker9999"
        s = _submission(
            text=f"feedback containing {unique_phrase} in it",
            mode=ConversationMode.OPERATOR,
        )
        p = engine.extract_pattern(s)
        # The unique phrase MUST NOT appear in any field of the output.
        for field_name in p.__dataclass_fields__:
            value = getattr(p, field_name)
            assert unique_phrase not in str(value), (
                f"user text leaked into FeedbackPattern.{field_name}"
            )

    def test_long_user_text_doesnt_leak(self):
        long_text = "this is a long submission " * 100
        s = _submission(text=long_text, mode=ConversationMode.EMOTIONAL)
        p = engine.extract_pattern(s)
        for field_name in p.__dataclass_fields__:
            value = getattr(p, field_name)
            assert "this is a long submission" not in str(value)


# ===========================================================================
# O. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_schemas_exports(self):
        for name in (
            "SignalType", "PatternType", "PrimitiveType",
            "FeedbackSubmission", "FeedbackPattern", "ExtractionContext",
            "assert_pattern_privacy_contract",
            "assert_pattern_field_set_canonical",
        ):
            assert hasattr(fs, name), f"missing in feedback_schemas: {name}"

    def test_engine_exports_extract_pattern(self):
        assert hasattr(engine, "extract_pattern")
        assert callable(engine.extract_pattern)

    def test_extract_pattern_returns_feedback_pattern(self):
        s = _submission()
        result = engine.extract_pattern(s)
        assert isinstance(result, fs.FeedbackPattern)


# ===========================================================================
# P. Cross-priority — pressure beats drift, drift beats mode
# ===========================================================================
class TestRulePriority:
    def test_pressure_beats_drift_marker(self):
        s = _submission(
            text="this caused drift",
            pressure_level=PressureLevel.HIGH,
            mode=ConversationMode.OPERATOR,
        )
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.PRESSURE

    def test_drift_marker_beats_mode_mapping(self):
        s = _submission(
            text="this caused drift",
            pressure_level=PressureLevel.LOW,
            mode=ConversationMode.OPERATOR,  # would be ALIGNMENT
        )
        p = engine.extract_pattern(s)
        assert p.pattern_type == fs.PatternType.DRIFT

    def test_mode_beats_primitive_fallback(self):
        """All ConversationModes have a mapping, so mode always wins
        over primitive fallback."""
        s = _submission(
            mode=ConversationMode.OPERATOR,
            primitive_used=ExpressionPrimitive.MOTION,  # would map to DRIFT in fallback
        )
        p = engine.extract_pattern(s)
        # Mode wins → ALIGNMENT (not DRIFT)
        assert p.pattern_type == fs.PatternType.ALIGNMENT


# ===========================================================================
# Q. Context + primitive forwarding
# ===========================================================================
class TestForwardedFields:
    def test_context_is_forwarded_mode(self):
        s = _submission(mode=ConversationMode.EXPLORATORY)
        p = engine.extract_pattern(s)
        assert p.context == ConversationMode.EXPLORATORY

    def test_pressure_level_is_forwarded(self):
        s = _submission(pressure_level=PressureLevel.MEDIUM)
        p = engine.extract_pattern(s)
        assert p.pressure_level == PressureLevel.MEDIUM

    def test_primitive_involved_is_forwarded(self):
        s = _submission(primitive_used=ExpressionPrimitive.ANALOGY)
        p = engine.extract_pattern(s)
        assert p.primitive_involved == ExpressionPrimitive.ANALOGY
