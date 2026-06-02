"""
A26 — ReduceHandler + reduce_signal tests.

#reduce replaces the model output with a deterministic reduction: filler
dropped, core claims vs supporting evidence separated, minimal essence emitted.
Heuristic (no NLP), so tests use inputs with clear filler / claim / evidence
shape and lean on internal-consistency checks.
"""
from __future__ import annotations

import pytest

import directive_engine as de
import reduce_signal as rs


HANDLER = de.DIRECTIVE_HANDLERS["reduce"]

RICH = (
    "Let me explain. "
    "The system is fundamentally unstable. "
    "According to the 2023 report, failures rose 40 percent. "
    "However, the core issue is architectural. "
    "I hope this helps."
)


# ---------------------------------------------------------------------------
# pre() — no-op
# ---------------------------------------------------------------------------
def test_pre_is_noop():
    assert HANDLER.pre("leave #reduce exactly") == "leave #reduce exactly"


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------
def test_extracts_core_claims():
    r = rs.reduce_text(RICH)
    assert len(r["core_claims"]) == 2
    assert "The system is fundamentally unstable." in r["core_claims"]


def test_extracts_evidence():
    r = rs.reduce_text(RICH)
    assert len(r["evidence"]) == 1
    assert "2023 report" in r["evidence"][0]


def test_filler_is_dropped():
    r = rs.reduce_text(RICH)
    blob = " ".join(r["core_claims"] + r["evidence"] + r["minimal"])
    assert "Let me explain" not in blob
    assert "hope this helps" not in blob


# ---------------------------------------------------------------------------
# minimal form
# ---------------------------------------------------------------------------
def test_minimal_strips_leading_connective():
    r = rs.reduce_text(RICH)
    # "However, the core issue …" -> "the core issue …" in minimal,
    # while the un-stripped form remains in core_claims.
    assert "the core issue is architectural." in r["minimal"]
    assert "However, the core issue is architectural." in r["core_claims"]


def test_connective_strip_requires_comma():
    # "First responders" must NOT be stripped (no comma after "First").
    r = rs.reduce_text("First responders arrived quickly at the scene.")
    assert r["minimal"][0].startswith("First responders")


def test_minimal_shorter_than_original():
    r = rs.reduce_text(RICH)
    minimal_text = " ".join(r["minimal"])
    assert len(minimal_text) < len(RICH)


# ---------------------------------------------------------------------------
# canonical structure
# ---------------------------------------------------------------------------
def test_canonical_structure_and_order():
    md = rs.format_reduction(rs.reduce_text(RICH))
    assert md.startswith("# Reduction")
    headers = ["## Core Claims", "## Supporting Evidence", "## Minimal Form"]
    positions = [md.index(h) for h in headers]
    assert positions == sorted(positions)


def test_empty_input_yields_well_formed_doc():
    r = rs.reduce_text("")
    md = rs.format_reduction(r)
    assert "# Reduction" in md
    assert "## Core Claims" in md
    meta = rs.build_metadata(r, "")
    assert meta["core_claims"] == 0
    assert meta["evidence"] == 0


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------
def test_metadata_counts_and_ratio():
    r = rs.reduce_text(RICH)
    meta = rs.build_metadata(r, RICH)
    assert meta["status"] == "reduced"
    assert meta["core_claims"] == len(r["core_claims"])
    assert meta["evidence"] == len(r["evidence"])
    # Compression: original longer than the minimal essence -> ratio > 1.
    assert meta["compression_ratio"] > 1.0


# ---------------------------------------------------------------------------
# determinism + retry contract
# ---------------------------------------------------------------------------
def test_deterministic():
    assert rs.reduce_text(RICH) == rs.reduce_text(RICH)
    assert rs.format_reduction(rs.reduce_text(RICH)) == rs.format_reduction(rs.reduce_text(RICH))


def test_handler_never_retries():
    res = HANDLER.evaluate("anything at all here")
    assert res.retry_needed is False
    assert res.retry_instruction is None
    assert res.status == "reduced"


# ---------------------------------------------------------------------------
# through the engine
# ---------------------------------------------------------------------------
def test_engine_applies_reduce():
    ds = de.parse_directives("#reduce this")
    out, meta = de.apply_post_enforcement(ds, RICH)
    assert out.startswith("# Reduction")
    rm = meta.to_dict()["reduce"]
    assert rm["status"] == "reduced"
    assert rm["core_claims"] == 2
    assert "compression_ratio" in rm
    assert meta.retry_needed is False
