"""
A24 — RegressionHandler + regression_trace tests.

#regression replaces the model output with a deterministic backward causal
trace (the backward half of Double Regression). Extraction is a heuristic
scaffold (no NLP dependency), so tests use unambiguous inputs and lean on
internal-consistency checks (metadata counts == list lengths).
"""
from __future__ import annotations

import pytest

import directive_engine as de
import regression_trace as rt


HANDLER = de.DIRECTIVE_HANDLERS["regression"]

FIRE = "The fire started. Then the alarm rang. Finally people evacuated."


# ---------------------------------------------------------------------------
# pre() — no-op
# ---------------------------------------------------------------------------
def test_pre_is_noop():
    assert HANDLER.pre("leave #regression exactly") == "leave #regression exactly"


# ---------------------------------------------------------------------------
# events + ordering
# ---------------------------------------------------------------------------
def test_extracts_events():
    r = rt.regress(FIRE)
    assert len(r["events"]) == 3


def test_chain_is_backward():
    md = rt.format_regression(rt.regress(FIRE))
    # Backward chain: the outcome (evacuated) precedes the origin (fire started).
    assert md.index("evacuated") < md.index("fire started")
    assert "1. " in md   # numbered chain


# ---------------------------------------------------------------------------
# causal links / turning points
# ---------------------------------------------------------------------------
def test_turning_points_detected():
    r = rt.regress("The disk filled, therefore the service crashed.")
    assert len(r["turning_points"]) >= 1


def test_pivot_markers_are_turning_points():
    r = rt.regress(FIRE)            # "Then …", "Finally …"
    assert len(r["turning_points"]) >= 2


# ---------------------------------------------------------------------------
# primitive emergence
# ---------------------------------------------------------------------------
def test_emergence_marked_by_origin_word():
    r = rt.regress("The outage originated from a config error. Then services failed.")
    assert r["emergence_kind"] == "marked"
    assert "originated" in r["emergence"]


def test_emergence_defaults_to_earliest():
    r = rt.regress("Services stalled badly. Users complained loudly.")
    assert r["emergence_kind"] == "earliest"
    assert r["emergence"] == "Services stalled badly."


# ---------------------------------------------------------------------------
# structural drivers
# ---------------------------------------------------------------------------
def test_structural_drivers_detected():
    r = rt.regress("A budget constraint and market pressure shaped the outcome.")
    assert len(r["drivers"]) >= 1


# ---------------------------------------------------------------------------
# canonical structure
# ---------------------------------------------------------------------------
def test_canonical_structure_and_order():
    md = rt.format_regression(rt.regress(FIRE))
    assert md.startswith("# Regression Analysis")
    headers = [
        "## Causal Chain (Backward)", "## Turning Points",
        "## Structural Drivers", "## Primitive Emergence",
    ]
    positions = [md.index(h) for h in headers]   # raises if missing
    assert positions == sorted(positions)


def test_empty_input_yields_well_formed_doc():
    r = rt.regress("")
    md = rt.format_regression(r)
    assert "# Regression Analysis" in md
    assert "## Causal Chain (Backward)" in md
    meta = rt.build_metadata(r)
    assert meta["length"] == 0
    assert meta["emergence"] == "none"


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------
def test_metadata_matches_trace():
    r = rt.regress(FIRE)
    meta = rt.build_metadata(r)
    assert meta["status"] == "regressed"
    assert meta["length"] == len(r["events"])
    assert meta["turning_points"] == len(r["turning_points"])
    assert meta["emergence"] == r["emergence_kind"]


def test_metadata_emergence_is_content_free_label():
    # The label is a kind, never the root-cause text (telemetry hygiene).
    r = rt.regress("The outage originated from a config error.")
    assert rt.build_metadata(r)["emergence"] in ("marked", "earliest", "none")


# ---------------------------------------------------------------------------
# determinism + retry contract
# ---------------------------------------------------------------------------
def test_deterministic():
    assert rt.regress(FIRE) == rt.regress(FIRE)
    assert rt.format_regression(rt.regress(FIRE)) == rt.format_regression(rt.regress(FIRE))


def test_handler_never_retries():
    res = HANDLER.evaluate("anything")
    assert res.retry_needed is False
    assert res.retry_instruction is None
    assert res.status == "regressed"


# ---------------------------------------------------------------------------
# through the engine
# ---------------------------------------------------------------------------
def test_engine_applies_regression():
    ds = de.parse_directives("#regression trace this")
    out, meta = de.apply_post_enforcement(ds, FIRE)
    assert out.startswith("# Regression Analysis")
    rm = meta.to_dict()["regression"]
    assert rm["status"] == "regressed"
    assert rm["length"] == 3
    assert meta.retry_needed is False
