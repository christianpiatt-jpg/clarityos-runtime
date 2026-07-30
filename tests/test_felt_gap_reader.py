"""
Unit tests for felt_gap_reader.py · Component A Phase-1

Offline synthetic pairs · deterministic · zero LLM.
Under Standing Truth: passes verify shape · not correctness on live turns.
"""

from felt_gap_reader import (
    classify_correction_type,
    felt_gap_from_correction_type,
    confidence_from_correction_type,
    build_arc_record,
)


def test_no_next_reply_returns_unknown():
    assert classify_correction_type("", False) == "unknown"
    assert classify_correction_type("some text", False) == "unknown"
    assert classify_correction_type(None, True) == "unknown"


def test_empty_and_whitespace_return_unknown():
    assert classify_correction_type("", True) == "unknown"
    assert classify_correction_type("   ", True) == "unknown"
    assert classify_correction_type("!!!", True) == "unknown"


def test_substring_bug_fixed():
    # These previously misfired via substring; must now return unknown or intended label
    assert classify_correction_type("now I get it", True) == "unknown"
    assert classify_correction_type("I'll book that", True) == "unknown"
    assert classify_correction_type("however that goes", True) == "unknown"
    # butter is great → "great" is in ACCEPT · word_set contains "great" · returns accept
    assert classify_correction_type("butter is great", True) == "accept"


def test_correct_tokens_word_level():
    assert classify_correction_type("no, that's wrong", True) == "correct"
    assert classify_correction_type("actually, that's not right", True) == "correct"
    assert classify_correction_type("let me clarify what I meant", True) == "correct"
    assert classify_correction_type("no.", True) == "correct"
    assert classify_correction_type("NO WAY", True) == "correct"


def test_back_and_forth_tokens_word_level():
    assert classify_correction_type("why did you say that?", True) == "back_and_forth"
    assert classify_correction_type("can you explain?", True) == "back_and_forth"
    assert classify_correction_type("how does that work", True) == "back_and_forth"
    assert classify_correction_type("but why", True) == "back_and_forth"


def test_accept_tokens_word_level():
    assert classify_correction_type("thanks, that helps", True) == "accept"
    assert classify_correction_type("perfect", True) == "accept"
    assert classify_correction_type("thanks!", True) == "accept"
    assert classify_correction_type("makes sense", True) == "accept"


def test_correct_precedence_over_back_and_forth():
    assert classify_correction_type("no, why did you say that", True) == "correct"
    assert classify_correction_type("actually, can you explain", True) == "correct"
    assert classify_correction_type("wrong. thanks anyway", True) == "correct"


def test_unicode_and_non_english_return_unknown():
    assert classify_correction_type("你好", True) == "unknown"


def test_non_string_input_returns_unknown():
    assert classify_correction_type(12345, True) == "unknown"
    assert classify_correction_type(None, True) == "unknown"


def test_felt_gap_mapping():
    assert felt_gap_from_correction_type("accept") == "aligned"
    assert felt_gap_from_correction_type("correct") == "misaligned"
    assert felt_gap_from_correction_type("back_and_forth") == "unresolved"
    assert felt_gap_from_correction_type("unknown") == "unmeasured"


def test_confidence_mapping():
    assert confidence_from_correction_type("accept") == "held"
    assert confidence_from_correction_type("correct") == "dropped"
    assert confidence_from_correction_type("back_and_forth") == "provisional"
    assert confidence_from_correction_type("unknown") == "null"


def test_arc_record_shape():
    record = build_arc_record(
        user_id="test_user",
        thread_id="test_thread",
        assistant_seq=42,
        user_prompt_text="What is the capital of France?",
        assistant_reply_text="The capital of France is Paris.",
        user_next_reply_text="Thanks!",
        user_next_reply_present=True,
    )
    assert record["e_t_user_prompt"] == "What is the capital of France?"
    assert record["y_t_assistant_reply"] == "The capital of France is Paris."
    assert record["correction_type"] == "accept"
    assert record["felt_gap"] == "aligned"
    assert record["confidence"] == "held"
    assert record["delta_m"] is None
    assert record["arc"] is None
    assert record["reader_version"] == "v0.1_phase1_first_cut"


def test_arc_record_trailing_pending():
    record = build_arc_record(
        user_id="test_user",
        thread_id="test_thread",
        assistant_seq=43,
        user_prompt_text="Question",
        assistant_reply_text="Answer",
        user_next_reply_text="",
        user_next_reply_present=False,
    )
    assert record["correction_type"] == "unknown"
    assert record["felt_gap"] == "unmeasured"
    assert record["confidence"] == "null"
    assert record["user_next_reply_present"] is False
