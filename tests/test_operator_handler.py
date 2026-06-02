"""
A27 — OperatorHandler + operator_brief tests.

#operator replaces the model output with a deterministic, narrative-free,
decision-ready operator brief. Heuristic (no NLP): each non-filler sentence is
routed to exactly one bucket by priority (moves > risks > constraints >
implications > signals). Tests use an input that exercises every bucket.
"""
from __future__ import annotations

import pytest

import directive_engine as de
import operator_brief as ob


HANDLER = de.DIRECTIVE_HANDLERS["operator"]

OP = (
    "Let me summarize. "
    "The market is growing rapidly. "
    "Therefore, demand will outpace supply. "
    "There is a significant risk of stockouts. "
    "The budget is limited to $2M. "
    "We should prioritize inventory now. "
    "I hope this helps."
)


# ---------------------------------------------------------------------------
# pre() — no-op
# ---------------------------------------------------------------------------
def test_pre_is_noop():
    assert HANDLER.pre("leave #operator exactly") == "leave #operator exactly"


# ---------------------------------------------------------------------------
# bucket extraction
# ---------------------------------------------------------------------------
def test_extracts_signals():
    b = ob.synthesize_operator_brief(OP)
    assert any("market is growing" in s for s in b["signals"])


def test_extracts_implications():
    b = ob.synthesize_operator_brief(OP)
    assert any("outpace supply" in s for s in b["implications"])


def test_extracts_risks():
    b = ob.synthesize_operator_brief(OP)
    assert any("risk of stockouts" in s for s in b["risks"])


def test_extracts_constraints():
    b = ob.synthesize_operator_brief(OP)
    assert any("budget" in s for s in b["constraints"])


def test_extracts_moves():
    b = ob.synthesize_operator_brief(OP)
    assert any("prioritize inventory" in s for s in b["moves"])


def test_filler_is_dropped():
    b = ob.synthesize_operator_brief(OP)
    blob = " ".join(sum(b.values(), []))
    assert "Let me summarize" not in blob
    assert "hope this helps" not in blob


# ---------------------------------------------------------------------------
# priority routing (one bucket per sentence)
# ---------------------------------------------------------------------------
def test_move_priority_over_risk():
    # "must mitigate … risk" matches both move and risk -> moves wins.
    b = ob.synthesize_operator_brief("We must mitigate the security risk now.")
    assert b["moves"]
    assert not b["risks"]


def test_imperative_opener_is_a_move():
    b = ob.synthesize_operator_brief("Reduce exposure immediately at the perimeter.")
    assert b["moves"]


# ---------------------------------------------------------------------------
# canonical structure
# ---------------------------------------------------------------------------
def test_canonical_structure_and_order():
    md = ob.format_operator_brief(ob.synthesize_operator_brief(OP))
    assert md.startswith("# Operator Brief")
    headers = [
        "## Core Signals", "## Implications", "## Risks",
        "## Constraints", "## Recommended Moves",
    ]
    positions = [md.index(h) for h in headers]
    assert positions == sorted(positions)


def test_empty_input_yields_well_formed_doc():
    b = ob.synthesize_operator_brief("")
    md = ob.format_operator_brief(b)
    assert "# Operator Brief" in md
    assert "## Core Signals" in md
    meta = ob.build_metadata(b)
    assert meta["signals"] == 0
    assert meta["moves"] == 0


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------
def test_metadata_counts():
    b = ob.synthesize_operator_brief(OP)
    meta = ob.build_metadata(b)
    assert meta["status"] == "operator_synthesized"
    assert meta["signals"] == len(b["signals"])
    assert meta["implications"] == len(b["implications"])
    assert meta["risks"] == len(b["risks"])
    assert meta["constraints"] == len(b["constraints"])
    assert meta["moves"] == len(b["moves"])


# ---------------------------------------------------------------------------
# determinism + retry contract
# ---------------------------------------------------------------------------
def test_deterministic():
    assert ob.synthesize_operator_brief(OP) == ob.synthesize_operator_brief(OP)
    assert ob.format_operator_brief(ob.synthesize_operator_brief(OP)) == \
        ob.format_operator_brief(ob.synthesize_operator_brief(OP))


def test_handler_never_retries():
    r = HANDLER.evaluate("anything at all here")
    assert r.retry_needed is False
    assert r.retry_instruction is None
    assert r.status == "operator_synthesized"


# ---------------------------------------------------------------------------
# through the engine
# ---------------------------------------------------------------------------
def test_engine_applies_operator():
    ds = de.parse_directives("#operator brief me")
    out, meta = de.apply_post_enforcement(ds, OP)
    assert out.startswith("# Operator Brief")
    om = meta.to_dict()["operator"]
    assert om["status"] == "operator_synthesized"
    assert om["moves"] == 1
    assert meta.retry_needed is False
