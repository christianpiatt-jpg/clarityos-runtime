"""
Tests for Phase 3 Unit 9 — detect_externalization_intent.

Covers all three triggers, combined behavior, determinism, error
handling, and source-code purity.

    A. Trigger 1 — explicit user flag
    B. Trigger 2 — canonical externalization markers (with word-boundary)
    C. Trigger 3 — topic recurrence (Jaccard similarity + 30-min window)
    D. Combined triggers
    E. Determinism + purity
    F. Error handling
    G. Source-code purity
    H. Constants lock + module surface
    I. End-to-end pipeline (the full Azimuth chain is now callable)
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta

import pytest

import azimuth_transition as at
from azimuth import (
    EnvelopeState,
    IntensityLevel,
    PressureLevel,
    Valence,
)


# ===========================================================================
# Fixture builder
# ===========================================================================
_T0 = datetime(2026, 5, 11, 12, 0, 0)


def _env(
    *,
    raw_text: str = "neutral observation",
    rough_intention: str = "describe what happened",
    user_marked_externalize: bool = False,
    captured_at: datetime = _T0,
    pressure_level: PressureLevel = PressureLevel.LOW,
    intensity: IntensityLevel = IntensityLevel.LOW,
    valence: Valence = Valence.NEUTRAL,
) -> EnvelopeState:
    return EnvelopeState(
        raw_text=raw_text,
        captured_at=captured_at,
        emotional_intensity=intensity,
        valence=valence,
        pressure_level=pressure_level,
        rough_intention=rough_intention,
        user_marked_externalize=user_marked_externalize,
    )


# ===========================================================================
# A. Trigger 1 — explicit user signal
# ===========================================================================
class TestTrigger1ExplicitFlag:
    def test_fires_when_flag_true(self):
        env = _env(user_marked_externalize=True)
        assert at.detect_externalization_intent(env) is True

    def test_does_not_fire_when_flag_false(self):
        env = _env(user_marked_externalize=False)
        assert at.detect_externalization_intent(env) is False

    def test_does_not_fire_by_default(self):
        env = _env()
        assert at.detect_externalization_intent(env) is False

    def test_flag_overrides_no_other_triggers(self):
        """Flag alone is sufficient — no markers, no history needed."""
        env = _env(
            user_marked_externalize=True,
            raw_text="completely neutral",
            rough_intention="random thought",
        )
        assert at.detect_externalization_intent(env, recent_history=()) is True


# ===========================================================================
# B. Trigger 2 — canonical externalization markers
# ===========================================================================
class TestTrigger2Markers:
    @pytest.mark.parametrize("marker", [
        "i want to tell them",
        "should i send",
        "should i say",
        "do i send",
        "do i say",
        "is it okay to tell",
        "should i message",
        "should i text",
    ])
    def test_each_canonical_marker_fires(self, marker):
        """Each of the 8 canonical phrases triggers when present."""
        env = _env(raw_text=f"thinking — {marker} this thing")
        assert at.detect_externalization_intent(env) is True

    @pytest.mark.parametrize("marker", [
        "I want to tell them",         # mixed case
        "Should I send",
        "DO I SAY",
        "Is It Okay To Tell",
    ])
    def test_markers_case_insensitive(self, marker):
        env = _env(raw_text=f"reflecting on this... {marker} the news")
        assert at.detect_externalization_intent(env) is True

    @pytest.mark.parametrize("text", [
        "should I sender notify the group",   # "send" inside "sender"
        "should I sending the email",          # "send" inside "sending"
        "should I sends them tomorrow",        # "send" inside "sends"
        "I want to tell themselves apart",     # "them" inside "themselves"
        "do I sender know the answer",         # "send" inside "sender"
    ])
    def test_word_boundary_blocks_substring_drift(self, text):
        """Word boundaries on both sides prevent substring matches."""
        env = _env(raw_text=text)
        assert at.detect_externalization_intent(env) is False

    @pytest.mark.parametrize("text", [
        "I want to tell",                # truncated
        "should I",                       # truncated
        "send the email",                 # only the verb, no preceding context
        "tell them the news",             # missing "I want to"
        "do I",                            # truncated
    ])
    def test_partial_phrases_do_not_fire(self, text):
        env = _env(raw_text=text)
        assert at.detect_externalization_intent(env) is False

    def test_marker_at_start_of_text(self):
        env = _env(raw_text="should I send the report?")
        assert at.detect_externalization_intent(env) is True

    def test_marker_at_end_of_text(self):
        env = _env(raw_text="thinking out loud — should I send")
        assert at.detect_externalization_intent(env) is True

    def test_marker_in_middle_of_text(self):
        env = _env(
            raw_text="I'm processing this and wondering should I send the email later"
        )
        assert at.detect_externalization_intent(env) is True

    def test_neutral_text_does_not_fire(self):
        env = _env(raw_text="just journaling about my day")
        assert at.detect_externalization_intent(env) is False


# ===========================================================================
# C. Trigger 3 — topic recurrence within 30 minutes
# ===========================================================================
class TestTrigger3TopicRecurrence:
    def test_three_matching_envelopes_in_window_fires(self):
        env = _env(rough_intention="reach out about the contract")
        history = (
            _env(rough_intention="reach out about the contract",
                 captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="reach out about contract today",
                 captured_at=_T0 - timedelta(minutes=15)),
            _env(rough_intention="contract reach out plan",
                 captured_at=_T0 - timedelta(minutes=25)),
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_two_matching_envelopes_does_not_fire(self):
        env = _env(rough_intention="reach out about the contract")
        history = (
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=15)),
        )
        assert at.detect_externalization_intent(env, history) is False

    def test_exactly_three_at_threshold(self):
        """Exactly 3 matches → True (the threshold is ≥ 3)."""
        env = _env(rough_intention="reach out about the contract")
        history = tuple(
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5 * i))
            for i in range(1, 4)
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_four_matching_also_fires(self):
        env = _env(rough_intention="reach out about the contract")
        history = tuple(
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=2 * i))
            for i in range(1, 5)
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_low_jaccard_does_not_fire(self):
        """Below threshold (0.5) on every history element → no fire."""
        env = _env(rough_intention="reach out about the contract")
        # All history envelopes share at most 1 token ("reach") with env;
        # union grows so Jaccard stays below 0.5.
        history = (
            _env(rough_intention="reach the kitchen counter please",
                 captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="another totally different topic here",
                 captured_at=_T0 - timedelta(minutes=10)),
            _env(rough_intention="something else entirely now today",
                 captured_at=_T0 - timedelta(minutes=15)),
        )
        assert at.detect_externalization_intent(env, history) is False

    def test_jaccard_at_threshold_fires(self):
        """Jaccard exactly 0.5 → fires (the threshold is ≥ 0.5)."""
        # env tokens: {a, b}; history tokens: {a, b, c, d} → 2/4 = 0.5
        env = _env(rough_intention="alpha beta")
        history = tuple(
            _env(rough_intention="alpha beta gamma delta",
                 captured_at=_T0 - timedelta(minutes=5 * i))
            for i in range(1, 4)
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_jaccard_just_below_threshold_does_not_fire(self):
        """Jaccard 0.4 → does NOT fire."""
        # env tokens: {a, b}; history tokens: {a, b, c, d, e} → 2/5 = 0.4
        env = _env(rough_intention="alpha beta")
        history = tuple(
            _env(rough_intention="alpha beta gamma delta epsilon",
                 captured_at=_T0 - timedelta(minutes=5 * i))
            for i in range(1, 4)
        )
        assert at.detect_externalization_intent(env, history) is False

    def test_time_window_29_minutes_inside(self):
        """29-minute envelope: inside the 30-minute window → counts."""
        env = _env(rough_intention="reach out about contract")
        history = (
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=15)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=29)),
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_time_window_31_minutes_outside(self):
        """31-minute envelope: outside the 30-minute window → excluded."""
        env = _env(rough_intention="reach out about contract")
        history = (
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=15)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=31)),
        )
        # Only 2 envelopes within window — below the count threshold.
        assert at.detect_externalization_intent(env, history) is False

    def test_time_window_exactly_30_minutes_inside(self):
        """Exactly 30 minutes → inside window (|delta| ≤ 1800 s)."""
        env = _env(rough_intention="reach out about contract")
        history = (
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=10)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=30)),
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_future_envelopes_in_window_count_too(self):
        """The window is symmetric (|delta| ≤ 30 min) — future
        envelopes within window count too. Order-independent."""
        env = _env(rough_intention="reach out about contract")
        history = (
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 + timedelta(minutes=5)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 + timedelta(minutes=15)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 + timedelta(minutes=25)),
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_mixed_history_three_matching_in_window(self):
        """Only matching-AND-in-window envelopes count; unrelated and
        out-of-window ones are skipped."""
        env = _env(rough_intention="reach out about contract")
        history = (
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=10)),
            _env(rough_intention="random different thought",
                 captured_at=_T0 - timedelta(minutes=12)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=20)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=45)),  # outside
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_empty_history_does_not_fire_alone(self):
        env = _env(rough_intention="reach out about contract")
        assert at.detect_externalization_intent(env, recent_history=()) is False

    def test_history_ordering_does_not_matter(self):
        """The function does not assume any sort order."""
        env = _env(rough_intention="reach out about contract")
        h_forward = (
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=15)),
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=25)),
        )
        h_reversed = tuple(reversed(h_forward))
        assert (
            at.detect_externalization_intent(env, h_forward)
            == at.detect_externalization_intent(env, h_reversed)
            is True
        )

    def test_tokenizer_drops_punctuation(self):
        """Tokenizer splits on non-alphanumerics, so punctuation does
        not change Jaccard scoring."""
        env = _env(rough_intention="reach out, about contract!")
        history = tuple(
            _env(rough_intention="reach out about contract.",
                 captured_at=_T0 - timedelta(minutes=5 * i))
            for i in range(1, 4)
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_tokenizer_lowercases(self):
        """Tokenizer lowercases tokens — case differences don't lower
        Jaccard."""
        env = _env(rough_intention="REACH out about CONTRACT")
        history = tuple(
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5 * i))
            for i in range(1, 4)
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_empty_intentions_yield_zero_similarity(self):
        """Both intentions empty → similarity 0.0 (no information,
        no match)."""
        env = _env(rough_intention="")
        history = tuple(
            _env(rough_intention="",
                 captured_at=_T0 - timedelta(minutes=5 * i))
            for i in range(1, 4)
        )
        assert at.detect_externalization_intent(env, history) is False


# ===========================================================================
# D. Combined triggers
# ===========================================================================
class TestCombinedTriggers:
    def test_flag_plus_marker_fires(self):
        env = _env(
            user_marked_externalize=True,
            raw_text="should I send the email",
        )
        assert at.detect_externalization_intent(env) is True

    def test_flag_plus_recurrence_fires(self):
        env = _env(user_marked_externalize=True)
        # Even with no recurrence in history, flag wins.
        assert at.detect_externalization_intent(env, recent_history=()) is True

    def test_marker_plus_recurrence_fires(self):
        env = _env(raw_text="I want to tell them tomorrow")
        history = (
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5)),
        )
        assert at.detect_externalization_intent(env, history) is True

    def test_all_triggers_silent_returns_false(self):
        env = _env(
            user_marked_externalize=False,
            raw_text="just journaling",
            rough_intention="reflect",
        )
        history = (
            _env(rough_intention="cooking dinner tonight",
                 captured_at=_T0 - timedelta(minutes=10)),
        )
        assert at.detect_externalization_intent(env, history) is False


# ===========================================================================
# E. Determinism + purity
# ===========================================================================
class TestDeterminism:
    def test_same_inputs_same_output(self):
        env = _env(
            user_marked_externalize=True,
            raw_text="should I send",
        )
        assert (
            at.detect_externalization_intent(env)
            == at.detect_externalization_intent(env)
            == True
        )

    def test_env_not_mutated(self):
        env = _env(
            raw_text="should I send the email",
            rough_intention="reach out about contract",
        )
        before = (env.raw_text, env.rough_intention, env.captured_at,
                  env.user_marked_externalize, env.envelope_id)
        at.detect_externalization_intent(env)
        after = (env.raw_text, env.rough_intention, env.captured_at,
                 env.user_marked_externalize, env.envelope_id)
        assert before == after

    def test_history_not_mutated(self):
        env = _env(rough_intention="reach out")
        history = (
            _env(rough_intention="reach out", captured_at=_T0 - timedelta(minutes=5)),
            _env(rough_intention="reach out", captured_at=_T0 - timedelta(minutes=15)),
        )
        before_ids = tuple(e.envelope_id for e in history)
        before_intentions = tuple(e.rough_intention for e in history)
        at.detect_externalization_intent(env, history)
        after_ids = tuple(e.envelope_id for e in history)
        after_intentions = tuple(e.rough_intention for e in history)
        assert before_ids == after_ids
        assert before_intentions == after_intentions

    def test_repeated_calls_byte_equal(self):
        env = _env(rough_intention="reach out about contract")
        history = tuple(
            _env(rough_intention="reach out about contract",
                 captured_at=_T0 - timedelta(minutes=5 * i))
            for i in range(1, 4)
        )
        results = [
            at.detect_externalization_intent(env, history) for _ in range(5)
        ]
        assert all(r is True for r in results)


# ===========================================================================
# F. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_non_envelope_state_env_raises_value_error(self):
        with pytest.raises(ValueError):
            at.detect_externalization_intent("not an envelope")  # type: ignore[arg-type]

    def test_none_env_raises_value_error(self):
        with pytest.raises(ValueError):
            at.detect_externalization_intent(None)  # type: ignore[arg-type]

    def test_dict_env_raises_value_error(self):
        with pytest.raises(ValueError):
            at.detect_externalization_intent({"raw_text": "x"})  # type: ignore[arg-type]

    def test_bad_history_element_raises_value_error(self):
        env = _env()
        history = (_env(), "not an envelope", _env())  # mixed
        with pytest.raises(ValueError):
            at.detect_externalization_intent(env, history)  # type: ignore[arg-type]

    def test_history_with_none_element_raises_value_error(self):
        env = _env()
        history = (_env(), None)
        with pytest.raises(ValueError):
            at.detect_externalization_intent(env, history)  # type: ignore[arg-type]

    def test_empty_history_does_not_raise(self):
        env = _env()
        result = at.detect_externalization_intent(env, recent_history=())
        assert isinstance(result, bool)

    def test_default_empty_history_does_not_raise(self):
        env = _env()
        result = at.detect_externalization_intent(env)
        assert isinstance(result, bool)


# ===========================================================================
# G. Source-code purity
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(at.detect_externalization_intent)

    def test_no_llm_imports_in_function(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_in_function(self):
        src = self._src()
        for forbidden in ("urlopen(", "requests.", ".post(", ".put(",
                          "smtplib"):
            assert forbidden not in src

    def test_no_io_in_function(self):
        src = self._src()
        for forbidden in ("open(", "Path(", "json.load", "subprocess",
                          "exec(", "eval("):
            assert forbidden not in src

    def test_no_randomness_in_function(self):
        src = self._src()
        for forbidden in ("random.", "secrets."):
            assert forbidden not in src

    def test_no_logging_in_function(self):
        src = self._src()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src


# ===========================================================================
# H. Constants lock + module surface
# ===========================================================================
class TestConstantsAndSurface:
    def test_externalization_markers_locked(self):
        assert at._EXTERNALIZATION_MARKERS == (
            "i want to tell them",
            "should i send",
            "should i say",
            "do i send",
            "do i say",
            "is it okay to tell",
            "should i message",
            "should i text",
        )

    def test_recurrence_window_locked_at_30_minutes(self):
        assert at._TOPIC_RECURRENCE_WINDOW_SECONDS == 30 * 60

    def test_recurrence_threshold_count_locked_at_3(self):
        assert at._TOPIC_RECURRENCE_THRESHOLD_COUNT == 3

    def test_topic_similarity_threshold_locked_at_half(self):
        assert at._TOPIC_SIMILARITY_THRESHOLD == 0.5

    def test_helpers_callable(self):
        for name in (
            "_tokenize_intention", "_jaccard_similarity",
            "_within_recurrence_window", "_topic_recurrence_fires",
        ):
            assert hasattr(at, name)
            assert callable(getattr(at, name))


# ===========================================================================
# I. Helper-function unit tests
# ===========================================================================
class TestHelperFunctions:
    def test_tokenize_lowercases(self):
        assert at._tokenize_intention("Reach Out") == frozenset({"reach", "out"})

    def test_tokenize_drops_empty_tokens(self):
        assert at._tokenize_intention("a,,b ;; c") == frozenset({"a", "b", "c"})

    def test_tokenize_handles_empty_string(self):
        assert at._tokenize_intention("") == frozenset()

    def test_jaccard_identical(self):
        assert at._jaccard_similarity("a b c", "a b c") == 1.0

    def test_jaccard_disjoint(self):
        assert at._jaccard_similarity("a b", "c d") == 0.0

    def test_jaccard_partial(self):
        # {a,b} and {a,c} → intersect={a}, union={a,b,c} → 1/3
        assert abs(at._jaccard_similarity("a b", "a c") - (1/3)) < 1e-9

    def test_jaccard_both_empty(self):
        assert at._jaccard_similarity("", "") == 0.0

    def test_within_window_zero_delta(self):
        e1 = _env(captured_at=_T0)
        e2 = _env(captured_at=_T0)
        assert at._within_recurrence_window(e1, e2) is True

    def test_within_window_at_boundary(self):
        e1 = _env(captured_at=_T0)
        e2 = _env(captured_at=_T0 - timedelta(seconds=1800))
        assert at._within_recurrence_window(e1, e2) is True

    def test_outside_window_just_over(self):
        e1 = _env(captured_at=_T0)
        e2 = _env(captured_at=_T0 - timedelta(seconds=1801))
        assert at._within_recurrence_window(e1, e2) is False


# ===========================================================================
# J. End-to-end pipeline (Units 5 → 6 → 7 → 8 → 9 fully callable)
# ===========================================================================
class TestEndToEndPipeline:
    def test_signal_to_cloud_full_chain(self):
        """The Azimuth pipeline is now fully callable end-to-end:
        detect → build → evaluate → cloud."""
        from azimuth import (
            AudienceType, ContextType, PressureSlope, UrgencyLevel,
            CloudMetadata,
        )
        env = _env(
            raw_text="should I send the proposal to the team today",
            rough_intention="send the proposal",
            user_marked_externalize=False,
            pressure_level=PressureLevel.HIGH,
            intensity=IntensityLevel.HIGH,
            valence=Valence.NEGATIVE,
        )
        # Unit 9 — detect intent.
        signal = at.detect_externalization_intent(env)
        assert signal is True

        # Unit 6 — build candidate.
        c = at.build_candidate(
            env, audience=AudienceType.ONE_TO_ONE,
            context=ContextType.PROFESSIONAL,
            pressure_slope=PressureSlope.RISING,
            urgency=UrgencyLevel.MEDIUM,
        )

        # Unit 7 — evaluate risk.
        c = at.evaluate_drift_risk(env, candidate=c)

        # Unit 8 — build cloud metadata.
        meta = at.build_cloud_metadata(c)
        assert isinstance(meta, CloudMetadata)
        # Privacy boundary intact across the full chain.
        assert not hasattr(meta, "raw_text")
        assert not hasattr(meta, "envelope_id")
