"""
A25 — CompareHandler + compare_delta tests.

#compare replaces the model output with a deterministic contrastive delta map.
It is the weakest semantic directive deterministically, so tests use inputs
with explicit comparison signals (vs / between / "both" / "whereas" /
"X is -er than Y") and lean on internal-consistency checks.
"""
from __future__ import annotations

import pytest

import directive_engine as de
import compare_delta as cd


HANDLER = de.DIRECTIVE_HANDLERS["compare"]


# ---------------------------------------------------------------------------
# pre() — no-op
# ---------------------------------------------------------------------------
def test_pre_is_noop():
    assert HANDLER.pre("leave #compare exactly") == "leave #compare exactly"


# ---------------------------------------------------------------------------
# target detection
# ---------------------------------------------------------------------------
def test_targets_from_vs():
    assert cd.compare("Python vs Java are common.")["targets"] == ["Python", "Java"]


def test_targets_from_between():
    assert cd.compare("Choosing between cats and dogs is hard.")["targets"] == ["cats", "dogs"]


def test_targets_from_compared_to():
    assert cd.compare("Rust compared to Go is stricter.")["targets"] == ["Rust", "Go"]


def test_targets_fallback_to_entities_skips_starter_word():
    # "Both" must not be picked as a target.
    assert cd.compare("Both Apple and Google compete fiercely.")["targets"] == ["Apple", "Google"]


# ---------------------------------------------------------------------------
# similarities
# ---------------------------------------------------------------------------
def test_similarities_detected():
    c = cd.compare("Both Python and Java are object-oriented.")
    assert len(c["similarities"]) == 1


# ---------------------------------------------------------------------------
# differences (side-bucketed)
# ---------------------------------------------------------------------------
def test_differences_bucketed_by_target():
    c = cd.compare("Python is concise, whereas Java is verbose.")
    diffs = c["differences"]
    assert diffs["Python"]      # A-side clause
    assert diffs["Java"]        # B-side clause


def test_no_differences_below_two_targets():
    c = cd.compare("Hello there world.")
    assert c["differences"] == {}


# ---------------------------------------------------------------------------
# attribute table (directional comparative)
# ---------------------------------------------------------------------------
def test_attribute_row_from_comparative():
    c = cd.compare("Python is faster than Java.")
    rows = c["attributes"]
    assert len(rows) == 1
    r = rows[0]
    assert r["name"] == "faster"
    assert r["higher"] == "Python"
    assert r["lower"] == "Java"


def test_attribute_direction_flips_on_less():
    c = cd.compare("Java is less concise than Python.")
    r = c["attributes"][0]
    assert r["higher"] == "Python"   # "less concise" -> Python is higher
    assert r["lower"] == "Java"


# ---------------------------------------------------------------------------
# canonical structure + table rendering
# ---------------------------------------------------------------------------
def test_canonical_structure_and_order():
    md = cd.format_comparison(cd.compare("Python is faster than Java; both are popular."))
    assert md.startswith("# Comparison")
    headers = ["## Targets", "## Similarities", "## Differences", "## Attribute Table"]
    positions = [md.index(h) for h in headers]
    assert positions == sorted(positions)


def test_attribute_table_renders_row_with_delta():
    md = cd.format_comparison(cd.compare("Python is faster than Java."))
    assert "| Attribute | Python | Java | Delta |" in md
    assert "| faster | higher | lower | Python > Java |" in md


def test_empty_input_yields_well_formed_doc():
    md = cd.format_comparison(cd.compare(""))
    assert "# Comparison" in md
    assert "_(need ≥2 targets)_" in md
    assert cd.build_metadata(cd.compare(""))["difference_count"] == 0


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------
def test_metadata_matches_comparison():
    c = cd.compare("Python is concise, whereas Java is verbose. Both are popular.")
    meta = cd.build_metadata(c)
    assert meta["status"] == "compared"
    assert meta["targets"] == c["targets"]
    assert meta["similarity_count"] == len(c["similarities"])
    assert meta["difference_count"] == sum(len(v) for v in c["differences"].values())


# ---------------------------------------------------------------------------
# determinism + retry contract
# ---------------------------------------------------------------------------
def test_deterministic():
    t = "Python is faster than Java; both are popular but Java is verbose."
    assert cd.compare(t) == cd.compare(t)
    assert cd.format_comparison(cd.compare(t)) == cd.format_comparison(cd.compare(t))


def test_handler_never_retries():
    r = HANDLER.evaluate("anything")
    assert r.retry_needed is False
    assert r.retry_instruction is None
    assert r.status == "compared"


# ---------------------------------------------------------------------------
# through the engine
# ---------------------------------------------------------------------------
def test_engine_applies_compare():
    ds = de.parse_directives("#compare these")
    out, meta = de.apply_post_enforcement(ds, "Python is faster than Java.")
    assert out.startswith("# Comparison")
    cm = meta.to_dict()["compare"]
    assert cm["status"] == "compared"
    assert cm["targets"] == ["Python", "Java"]
    assert meta.retry_needed is False
