"""
A21 — Unified Directive Engine foundation tests.

directive_engine.py is the pure interpreter layer all seven directives plug
into. A21 ships the engine + a real CiteHandler (delegating to cite_mode,
reproducing the A18 grounded/incomplete/retry contract) + six inert stub
handlers. It is wired into nothing yet — the kernel migration is A28. These
tests pin the engine's contract so A22–A27 can drop in handlers without
surprises, and so the eventual A28 migration has a behavioural spec to hit.
"""
from __future__ import annotations

import pytest

import cite_mode
import directive_engine as de


# ---------------------------------------------------------------------------
# parse_directives
# ---------------------------------------------------------------------------
def test_parses_each_known_directive():
    for name in de.DIRECTIVES:
        ds = de.parse_directives(f"#{name} do the thing")
        assert ds.active is True
        assert ds.directives == [name]
        assert ds.text == "do the thing"


def test_parse_strips_separators():
    ds = de.parse_directives("#cite: who said this?")
    assert ds.directives == ["cite"]
    assert ds.text == "who said this?"


def test_parse_is_case_insensitive_and_records_raw():
    ds = de.parse_directives("#CITE hello")
    assert ds.directives == ["cite"]
    assert ds.raw_prefixes == ["#CITE"]


def test_parse_word_bounded():
    ds = de.parse_directives("#citecisely worded")
    assert ds.active is False
    assert ds.directives == []
    assert ds.text == "#citecisely worded"


def test_parse_unknown_hashtoken_left_intact():
    ds = de.parse_directives("#hashtag content")
    assert ds.active is False
    assert ds.text == "#hashtag content"


def test_parse_stacks_multiple_directives_in_order():
    ds = de.parse_directives("#cite #structure analyse this")
    assert ds.directives == ["cite", "structure"]
    assert ds.raw_prefixes == ["#cite", "#structure"]
    assert ds.text == "analyse this"


def test_parse_stops_at_first_non_directive():
    ds = de.parse_directives("#cite hello #structure")
    # Only the leading run is consumed; mid-message #tokens stay in text.
    assert ds.directives == ["cite"]
    assert ds.text == "hello #structure"


def test_parse_dedupes_preserving_order():
    ds = de.parse_directives("#cite #cite go")
    assert ds.directives == ["cite"]
    assert ds.raw_prefixes == ["#cite", "#cite"]


def test_parse_bare_directive_empty_text():
    ds = de.parse_directives("#cite")
    assert ds.directives == ["cite"]
    assert ds.text == ""


def test_parse_no_directive():
    ds = de.parse_directives("just a normal message")
    assert ds.active is False
    assert ds.directives == []
    assert ds.text == "just a normal message"


def test_parse_non_string():
    ds = de.parse_directives(None)  # type: ignore[arg-type]
    assert ds.active is False
    assert ds.directives == []


# ---------------------------------------------------------------------------
# pre-enforcement
# ---------------------------------------------------------------------------
def test_pre_enforcement_is_identity_at_a21():
    ds = de.parse_directives("#structure #cite content here")
    assert de.apply_pre_enforcement(ds, ds.text) == "content here"


# ---------------------------------------------------------------------------
# post-enforcement: cite (reproduces A18)
# ---------------------------------------------------------------------------
GROUNDED = "According to the official report, the findings are summarized."
UNGROUNDED = "The structure is 330 meters tall."


def test_post_cite_grounded_first_pass_no_retry():
    ds = de.parse_directives("#cite who?")
    out, meta = de.apply_post_enforcement(ds, GROUNDED)
    assert out == GROUNDED
    assert meta.retry_needed is False
    assert meta.to_dict()["cite"] == {"status": "grounded", "retry_used": False}


def test_post_cite_needs_retry_first_pass():
    ds = de.parse_directives("#cite how tall?")
    _out, meta = de.apply_post_enforcement(ds, UNGROUNDED)
    assert meta.retry_needed is True
    assert meta.retry_instruction  # validator's re-query instruction
    assert meta.to_dict()["cite"]["status"] is None


def test_post_cite_incomplete_after_retry():
    ds = de.parse_directives("#cite how tall?")
    _out, meta = de.apply_post_enforcement(ds, UNGROUNDED, retry_used=True)
    assert meta.retry_needed is False  # cap reached
    assert meta.to_dict()["cite"] == {"status": "incomplete", "retry_used": True}


def test_post_cite_grounded_after_retry():
    ds = de.parse_directives("#cite how tall?")
    _out, meta = de.apply_post_enforcement(ds, GROUNDED, retry_used=True)
    assert meta.to_dict()["cite"] == {"status": "grounded", "retry_used": True}


# ---------------------------------------------------------------------------
# post-enforcement: stubs + inactive
# ---------------------------------------------------------------------------
def test_post_stub_directive_produces_no_metadata():
    # #reduce is still an inert stub at A25 (structure/primitives/regression/compare real).
    ds = de.parse_directives("#reduce do it")
    out, meta = de.apply_post_enforcement(ds, "anything at all")
    assert out == "anything at all"
    assert meta.to_dict() == {}
    assert meta.retry_needed is False


def test_post_no_active_directives():
    ds = de.parse_directives("plain message")
    out, meta = de.apply_post_enforcement(ds, "model output")
    assert out == "model output"
    assert meta.to_dict() == {}
    assert meta.retry_needed is False


def test_stacked_cite_plus_stub_only_cite_reports():
    # Pair cite with a still-stub directive (#reduce) so only cite reports.
    ds = de.parse_directives("#cite #reduce question")
    _out, meta = de.apply_post_enforcement(ds, GROUNDED)
    assert set(meta.to_dict()) == {"cite"}  # the stub contributes nothing


# ---------------------------------------------------------------------------
# registry + cite parity
# ---------------------------------------------------------------------------
def test_registry_covers_all_seven():
    assert set(de.DIRECTIVE_HANDLERS) == set(de.DIRECTIVES)


def test_cite_parity_with_cite_mode():
    samples = (GROUNDED, UNGROUNDED, "It is the best.", "1984 was the year.")
    for sample in samples:
        ds = de.parse_directives("#cite x")
        _out, meta = de.apply_post_enforcement(ds, sample, retry_used=True)
        expected = "grounded" if cite_mode.validate_cite_output(sample).ok else "incomplete"
        assert meta.to_dict()["cite"]["status"] == expected
