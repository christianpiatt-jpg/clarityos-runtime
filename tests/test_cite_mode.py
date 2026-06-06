"""A17 — tests for cite_mode (the pure `#cite` validator): parse + validate.

No fixtures, no I/O — the module is pure logic. Repo-root conftest puts the
project root on sys.path so the bare ``import cite_mode`` resolves.
"""
from __future__ import annotations

from cite_mode import parse_cite_directive, validate_cite_output


class TestParse:
    def test_detects_and_strips_prefix(self):
        is_cite, rest = parse_cite_directive("#cite What movie had the highest attendance")
        assert is_cite is True
        assert rest == "What movie had the highest attendance"

    def test_case_insensitive_and_leading_whitespace(self):
        assert parse_cite_directive("   #CITE foo") == (True, "foo")

    def test_strips_following_colon(self):
        assert parse_cite_directive("#cite: bar") == (True, "bar")

    def test_bare_directive(self):
        assert parse_cite_directive("#cite") == (True, "")

    def test_word_boundary_no_false_match(self):
        is_cite, rest = parse_cite_directive("#citecisely speaking")
        assert is_cite is False
        assert rest == "#citecisely speaking"

    def test_non_cite_unchanged(self):
        assert parse_cite_directive("what is the rule") == (False, "what is the rule")

    def test_non_string_returns_unchanged(self):
        assert parse_cite_directive(None) == (False, None)


class TestValidate:
    def test_factual_without_citation_retries(self):
        r = validate_cite_output("The film grossed 2.9 billion dollars.")
        assert r.ok is False and r.needs_retry is True
        assert "factual_claim_without_citation" in r.reasons
        assert "authoritative source" in r.retry_instruction

    def test_factual_with_citation_ok(self):
        r = validate_cite_output("According to the Comscore Report, attendance was highest in 2019.")
        assert r.ok is True and r.needs_retry is False
        assert r.retry_instruction is None

    def test_opinion_without_basis_retries(self):
        r = validate_cite_output("Blade Runner is the best sci-fi movie.")
        assert r.ok is False
        assert "opinion_without_basis" in r.reasons
        assert "basis" in r.retry_instruction

    def test_opinion_with_basis_ok(self):
        r = validate_cite_output("Based on IMDb ratings, Blade Runner is the best sci-fi movie.")
        assert r.ok is True

    def test_no_claims_ok(self):
        r = validate_cite_output("Hello, how can I help you today?")
        assert r.ok is True and r.reasons == []

    def test_both_missing_lists_both_reasons(self):
        r = validate_cite_output("It is the best film and grossed 100 million.")
        assert r.ok is False
        assert set(r.reasons) == {"factual_claim_without_citation", "opinion_without_basis"}
        assert "authoritative source" in r.retry_instruction
        assert "basis" in r.retry_instruction

    def test_empty_whitespace_none_ok(self):
        assert validate_cite_output("").ok is True
        assert validate_cite_output("   ").ok is True
        assert validate_cite_output(None).ok is True
