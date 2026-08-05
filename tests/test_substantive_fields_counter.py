"""
Tests for the substantive-fields counter (v52 emotional_physics logging).

Covers:

intelligence_kernel:
  * SUBSTANTIVE_DENOMINATOR is derived (11 enums + 4 subset arrays), not
    a hardcoded 15
  * Two-direction floor confirmation:
      - boundary  "clear" -> counted      (nominal; first-listed is not a floor)
      - intensity "low"   -> not counted  (ordinal floor)
  * Three-case range: rich 15/15, thin 0/15, degraded skeleton 0/15
  * signal_clarity is excluded from the count and reported on its own
  * Counter never raises on malformed / partial bodies

Why the floor test exists
-------------------------
``_ORDINAL_FLOOR`` carries four entries against twelve enums. Read without
this test it looks incomplete, and the obvious "fix" is to add the other
eight. That would score every nominal first-listed member — ``boundary:
clear``, ``agency: full``, ``stability: stable`` — as a non-substantive
floor hit, systematically under-counting substance. Only ordinal enums
have a degenerate bottom; nominal members are each a positive claim. The
two-direction assertion below pins that in both directions so the rule
cannot be "completed" into a wrong one.
"""
from __future__ import annotations

import pytest

import intelligence_kernel

# Gate membership: the counter lives in intelligence_kernel.py, which
# pytest.ini names as a BD1-BD5 file requiring a green runtime_spine gate.
# The conftest hook only adds markers to files it knows, so declaring it
# here is what puts these tests in the gate.
pytestmark = pytest.mark.runtime_spine


def _rich() -> dict:
    """Every counted field carrying a substantive value."""
    return {
        "field_curvature": {
            "intensity": "high",
            "gradient_direction": "inward",
            "stability": "unstable",
            "dominant_forces": ["uncertainty", "time_pressure"],
        },
        "edge_pressure": {
            "signal_clarity": "mixed",
            "signal_intensity": "high",
            "coherence": "fragmented",
            "perceived_posture": ["defensive"],
            "risk_of_misread": "high",
        },
        "relational_primitives": {
            "trust": "medium",
            "alignment": "misaligned",
            "boundary": "contested",
            "agency": "partial",
            "distance": "increasing",
            "dominant_pattern": ["pressure_asymmetry"],
        },
        "external_expression": {"recommended_posture": ["slow_down"]},
    }


def _thin() -> dict:
    """Every counted field at ``unclear``, an ordinal floor, or empty."""
    return {
        "field_curvature": {
            "intensity": "low",
            "gradient_direction": "unclear",
            "stability": "unclear",
            "dominant_forces": [],
        },
        "edge_pressure": {
            "signal_clarity": "unclear",
            "signal_intensity": "low",
            "coherence": "unclear",
            "perceived_posture": [],
            "risk_of_misread": "low",
        },
        "relational_primitives": {
            "trust": "low",
            "alignment": "unclear",
            "boundary": "unclear",
            "agency": "unclear",
            "distance": "unclear",
            "dominant_pattern": [],
        },
        "external_expression": {"recommended_posture": []},
    }


# ---------------------------------------------------------------------------
# Denominator
# ---------------------------------------------------------------------------
def test_denominator_is_derived_not_hardcoded():
    assert intelligence_kernel.SUBSTANTIVE_DENOMINATOR == 15
    assert intelligence_kernel.SUBSTANTIVE_DENOMINATOR == (
        len(intelligence_kernel._SUBSTANTIVE_ENUMS)
        + len(intelligence_kernel._SUBSTANTIVE_ARRAYS)
    )
    # 12 contract enums less signal_clarity, which is reported separately.
    assert len(intelligence_kernel._SUBSTANTIVE_ENUMS) == 11
    assert len(intelligence_kernel._SUBSTANTIVE_ARRAYS) == 4


# ---------------------------------------------------------------------------
# Two-direction floor confirmation — the assertion that matters
# ---------------------------------------------------------------------------
def test_nominal_first_listed_member_is_counted():
    """``boundary: clear`` is first-listed but nominal, so it is a real
    reading and must count. Adding boundary to _ORDINAL_FLOOR would break
    this."""
    body = _rich()
    body["relational_primitives"]["boundary"] = "clear"
    assert intelligence_kernel._count_substantive_fields(body) == 15


def test_ordinal_floor_member_is_not_counted():
    """``intensity: low`` is the bottom of an ordinal scale — ambiguous
    between a real low reading and nothing to see — so it must not count."""
    body = _rich()
    body["field_curvature"]["intensity"] = "low"
    assert intelligence_kernel._count_substantive_fields(body) == 14


def test_only_ordinal_enums_carry_a_floor():
    assert set(intelligence_kernel._ORDINAL_FLOOR) == {
        "intensity", "signal_intensity", "risk_of_misread", "trust",
    }
    assert set(intelligence_kernel._ORDINAL_FLOOR.values()) == {"low"}


# ---------------------------------------------------------------------------
# Three-case range
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "name, body, expected",
    [
        ("rich", _rich(), 15),
        ("thin", _thin(), 0),
        ("degraded", intelligence_kernel._emotional_physics_skeleton(), 0),
    ],
)
def test_three_case_range(name, body, expected):
    assert intelligence_kernel._count_substantive_fields(body) == expected


def test_unclear_is_never_counted():
    body = _rich()
    for layer, field in intelligence_kernel._SUBSTANTIVE_ENUMS:
        body[layer][field] = "unclear"
    assert intelligence_kernel._count_substantive_fields(body) == 4  # arrays


# ---------------------------------------------------------------------------
# signal_clarity is reported, not counted
# ---------------------------------------------------------------------------
def test_signal_clarity_excluded_from_count():
    """Its ``unclear`` is semantic — it predates the null-member work and
    means the signal itself reads as unclear. Counting it as an abstention
    would misread a correct answer as a shrug."""
    assert ("edge_pressure", "signal_clarity") not in \
        intelligence_kernel._SUBSTANTIVE_ENUMS
    body = _rich()
    body["edge_pressure"]["signal_clarity"] = "unclear"
    assert intelligence_kernel._count_substantive_fields(body) == 15


@pytest.mark.parametrize(
    "raw, expected",
    [("mixed", "mixed"), ("  Clear ", "clear"), ("unclear", "unclear"),
     ("", "absent"), (None, "absent")],
)
def test_signal_clarity_value_reported(raw, expected):
    body = _rich()
    body["edge_pressure"]["signal_clarity"] = raw
    assert intelligence_kernel._signal_clarity_value(body) == expected


# ---------------------------------------------------------------------------
# Never raises
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "body", [None, {}, [], "text", {"field_curvature": None},
             {"field_curvature": {"intensity": 3}},
             {"relational_primitives": {"dominant_pattern": "not-a-list"}}],
)
def test_counter_never_raises(body):
    assert intelligence_kernel._count_substantive_fields(body) == 0
    assert intelligence_kernel._signal_clarity_value(body) == "absent"
