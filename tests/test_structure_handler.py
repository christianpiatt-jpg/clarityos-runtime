"""
A22 — StructureHandler + structure_format tests.

#structure is a post-generation, deterministic, MEANING-PRESERVING shape pass:
no prompt change, no retry, no semantics, no correctness check. These tests
cover the pure formatter (structure_format.format_output), the handler's
DirectiveResult contract, and the handler running through the engine.

Note on scope: the A22 card listed two auto-heading conversions
("Heading:" -> "# Heading" and no-space "##Heading" -> "## Heading"). Both
reclassify literal text as headings (a "Status:" label, a "#climate" hashtag)
and so ALTER MEANING — which #structure must not do. They are intentionally
NOT implemented; the tests below pin that safe behaviour.
"""
from __future__ import annotations

import pytest

import directive_engine as de
import structure_format as sf


HANDLER = de.DIRECTIVE_HANDLERS["structure"]


# ---------------------------------------------------------------------------
# pre() — no-op
# ---------------------------------------------------------------------------
def test_pre_is_noop():
    assert HANDLER.pre("  leave me #structure exactly  ") == "  leave me #structure exactly  "


# ---------------------------------------------------------------------------
# whitespace normalisation
# ---------------------------------------------------------------------------
def test_strips_trailing_whitespace_per_line():
    assert sf.format_output("alpha   \nbeta\t\n") == "alpha\nbeta"


def test_collapses_multiple_blank_lines():
    assert sf.format_output("a\n\n\n\nb") == "a\n\nb"


def test_trims_leading_and_trailing_blank_lines():
    assert sf.format_output("\n\n  \nhello\n\n\n") == "hello"


# ---------------------------------------------------------------------------
# headings — existing headings normalised; non-headings left alone
# ---------------------------------------------------------------------------
def test_collapses_spaces_in_existing_heading():
    assert sf.format_output("##    Title") == "## Title"


def test_existing_heading_single_space_unchanged():
    assert sf.format_output("## Title") == "## Title"


def test_no_space_hash_is_not_promoted_to_heading():
    # Meaning-preserving: "##text" / "#climate" stay literal text.
    assert sf.format_output("##Heading") == "##Heading"
    assert sf.format_output("#climate change") == "#climate change"


def test_label_colon_is_not_promoted_to_heading():
    assert sf.format_output("Status: done") == "Status: done"


# ---------------------------------------------------------------------------
# lists
# ---------------------------------------------------------------------------
def test_star_bullet_becomes_dash():
    assert sf.format_output("* item") == "- item"


def test_plus_bullet_becomes_dash():
    assert sf.format_output("+ item") == "- item"


def test_indented_bullet_preserves_indent():
    assert sf.format_output("  * nested") == "  - nested"


def test_dash_bullet_unchanged():
    assert sf.format_output("- item") == "- item"


def test_ordered_list_unchanged():
    assert sf.format_output("1. item") == "1. item"


def test_emphasis_not_treated_as_bullet():
    assert sf.format_output("*emphasis* in text") == "*emphasis* in text"


def test_thematic_break_preserved():
    assert sf.format_output("* * *") == "* * *"


# ---------------------------------------------------------------------------
# fenced code blocks — preserved verbatim
# ---------------------------------------------------------------------------
def test_code_fence_contents_preserved_verbatim():
    src = "```\n* not a bullet\n\n\nx = 1   \n```"
    # Inside the fence: bullet not converted, blank lines kept, trailing
    # spaces on the code line kept; only the fence lines are touched.
    assert sf.format_output(src) == "```\n* not a bullet\n\n\nx = 1   \n```"


def test_formatting_resumes_after_fence():
    src = "```\n* code\n```\n* real bullet"
    assert sf.format_output(src) == "```\n* code\n```\n- real bullet"


# ---------------------------------------------------------------------------
# idempotency + determinism
# ---------------------------------------------------------------------------
def test_idempotent():
    messy = "##  H\n\n\n* a\n+ b   \n\n\n"
    once = sf.format_output(messy)
    assert sf.format_output(once) == once


def test_already_clean_is_unchanged():
    clean = "# Title\n\n- a\n- b"
    assert sf.format_output(clean) == clean


# ---------------------------------------------------------------------------
# handler DirectiveResult contract
# ---------------------------------------------------------------------------
def test_handler_reports_changed_true():
    r = HANDLER.evaluate("* item   ")
    assert r.status == "formatted"
    assert r.output == "- item"
    assert r.meta == {"status": "formatted", "changed": True}


def test_handler_reports_changed_false_on_clean_input():
    r = HANDLER.evaluate("- item")
    assert r.meta == {"status": "formatted", "changed": False}
    assert r.output == "- item"


def test_handler_never_retries():
    r = HANDLER.evaluate("anything")
    assert r.retry_needed is False
    assert r.retry_instruction is None


# ---------------------------------------------------------------------------
# through the engine
# ---------------------------------------------------------------------------
def test_engine_applies_structure_formatting():
    ds = de.parse_directives("#structure please format")
    out, meta = de.apply_post_enforcement(ds, "* a\n\n\n* b   ")
    assert out == "- a\n\n- b"
    assert meta.to_dict()["structure"] == {"status": "formatted", "changed": True}
    assert meta.retry_needed is False


def test_engine_structure_changed_false_passthrough():
    ds = de.parse_directives("#structure x")
    out, meta = de.apply_post_enforcement(ds, "already clean")
    assert out == "already clean"
    assert meta.to_dict()["structure"]["changed"] is False
