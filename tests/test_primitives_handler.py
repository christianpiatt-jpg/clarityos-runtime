"""
A23 — PrimitivesHandler + primitives_extract tests.

#primitives is the first SEMANTIC handler: it replaces the model output with a
deterministic P-series decomposition. Extraction is a heuristic scaffold (no
NLP dependency in the runtime), so these tests use unambiguous inputs and lean
on internal-consistency checks (counts == list lengths) rather than asserting
fuzzy totals.
"""
from __future__ import annotations

import pytest

import directive_engine as de
import primitives_extract as pe


HANDLER = de.DIRECTIVE_HANDLERS["primitives"]


# ---------------------------------------------------------------------------
# pre() — no-op
# ---------------------------------------------------------------------------
def test_pre_is_noop():
    assert HANDLER.pre("leave #primitives exactly") == "leave #primitives exactly"


# ---------------------------------------------------------------------------
# P1–P4 extraction
# ---------------------------------------------------------------------------
def test_extracts_entities():
    prim = pe.extract_primitives("NASA partnered with John Smith in Berlin.")
    assert "NASA" in prim["P1"]
    assert "John Smith" in prim["P1"]
    assert "Berlin" in prim["P1"]


def test_common_word_not_an_entity():
    # A sentence-initial common word must not be treated as an entity.
    prim = pe.extract_primitives("The system runs well.")
    assert "The" not in prim["P1"]


def test_extracts_actions():
    prim = pe.extract_primitives("The team is creating systems and they deployed updates.")
    assert "creating" in prim["P2"]
    assert "deployed" in prim["P2"]


def test_extracts_relations():
    prim = pe.extract_primitives("It failed because the database crashed.")
    assert len(prim["P3"]) == 1


def test_extracts_states():
    prim = pe.extract_primitives("The server is blocked while the queue is stable.")
    assert len(prim["P4"]) == 1


# ---------------------------------------------------------------------------
# tensions
# ---------------------------------------------------------------------------
def test_extracts_structural_tension():
    prim = pe.extract_primitives("There is a structural constraint in the design.")
    assert len(prim["Ts"]) == 1


def test_extracts_external_tension():
    prim = pe.extract_primitives("Market competition creates demand.")
    assert len(prim["Te"]) == 1


def test_extracts_motive_force():
    prim = pe.extract_primitives("Our goal is to expand the mission.")
    assert len(prim["M"]) == 1


# ---------------------------------------------------------------------------
# hydronic
# ---------------------------------------------------------------------------
def test_extracts_hydronic_primitives():
    prim = pe.extract_primitives(
        "Data flows hit a bottleneck and pressure built along the gradient.",
    )
    h = prim["hydronic"]
    assert h["flows"]            # "flows" -> flow
    assert h["blockages"]        # "bottleneck"
    assert h["pressure_points"]  # "pressure"
    assert h["gradients"]        # "gradient"


# ---------------------------------------------------------------------------
# canonical structure
# ---------------------------------------------------------------------------
def test_canonical_structure_and_order():
    prim = pe.extract_primitives("NASA flows because of a constraint; the goal is stable.")
    md = pe.format_primitives(prim)
    assert md.startswith("# Primitives")
    headers = [
        "## P1 — Entities", "## P2 — Actions", "## P3 — Relations",
        "## P4 — States", "## Tensions", "## Hydronic",
    ]
    positions = [md.index(h) for h in headers]  # raises if any missing
    assert positions == sorted(positions)       # sections in canonical order
    # Tensions + Hydronic sub-labels present.
    for label in ("- Ts:", "- Te:", "- M:", "- Flows:", "- Blockages:",
                  "- Gradients:", "- Pressure Points:"):
        assert label in md


def test_empty_input_yields_well_formed_empty_doc():
    prim = pe.extract_primitives("")
    md = pe.format_primitives(prim)
    assert "# Primitives" in md
    assert "## P1 — Entities" in md
    assert "_(none detected)_" in md  # empty P1–P4 sections
    assert pe.build_metadata(prim)["counts"]["P1"] == 0


# ---------------------------------------------------------------------------
# metadata counts
# ---------------------------------------------------------------------------
def test_metadata_counts_match_list_lengths():
    prim = pe.extract_primitives(
        "NASA deployed a pipeline because of a constraint; the system is stable. "
        "The goal is growth despite market competition and a bottleneck.",
    )
    meta = pe.build_metadata(prim)
    assert meta["status"] == "extracted"
    c = meta["counts"]
    for key in ("P1", "P2", "P3", "P4", "Ts", "Te", "M"):
        assert c[key] == len(prim[key])
    h = prim["hydronic"]
    assert c["hydronic"] == (
        len(h["flows"]) + len(h["blockages"])
        + len(h["gradients"]) + len(h["pressure_points"])
    )


# ---------------------------------------------------------------------------
# determinism + retry contract
# ---------------------------------------------------------------------------
def test_deterministic():
    text = "NASA flows hit a bottleneck because of a constraint; the goal is stable."
    assert pe.extract_primitives(text) == pe.extract_primitives(text)
    assert pe.format_primitives(pe.extract_primitives(text)) == \
        pe.format_primitives(pe.extract_primitives(text))


def test_handler_never_retries():
    r = HANDLER.evaluate("anything at all")
    assert r.retry_needed is False
    assert r.retry_instruction is None
    assert r.status == "extracted"


# ---------------------------------------------------------------------------
# through the engine
# ---------------------------------------------------------------------------
def test_engine_applies_primitives():
    ds = de.parse_directives("#primitives break this down")
    out, meta = de.apply_post_enforcement(
        ds, "NASA deployed a pipeline because demand grew.",
    )
    assert out.startswith("# Primitives")
    pm = meta.to_dict()["primitives"]
    assert pm["status"] == "extracted"
    assert "counts" in pm
    assert meta.retry_needed is False
