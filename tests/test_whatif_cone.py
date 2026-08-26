"""
What-if cone spikes — nudge table (B) and physics-as-mapper (A).

★★★ THE CONTRACT UNDER TEST: CONE-SHAPED OUTPUT ONLY.

Charge, direction, dispersion -- never the shard. There is no assertion here
that any module names an outcome, because no module may produce one. The
last test in this file enforces that structurally: it fails if either
module grows a field outside the declared axis vocabulary.

Everything here is a pure function over recorded readings. No model call, no
network, no I/O -- the physics readings below are verbatim shapes measured
against the live contract on 2026-08-26.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")

import pytest  # noqa: E402

import whatif_nudge as B  # noqa: E402
import whatif_physics_mapper as A  # noqa: E402


def _reading(parse_error=None, **primitives):
    return {
        "relational_primitives": dict(primitives),
        "_meta": {"parse_error": parse_error},
    }


# Measured live, gpt-5.4, 2026-08-26.
BASE = _reading(trust="fluctuating", alignment="misaligned",
                boundary="contested", agency="partial", distance="increasing")
WARM = _reading(trust="fluctuating", alignment="partially_aligned",
                boundary="soft", agency="partial", distance="decreasing")


# ---------------------------------------------------------------------------
# B — the nudge table
# ---------------------------------------------------------------------------
def test_table_covers_the_common_moves():
    assert len(B.NUDGES) >= 20


@pytest.mark.parametrize("phrase,expected", [
    ("comes in warm", "warmer"),
    ("goes quiet", "withdrawn"),
    ("stonewalls", "withdrawn"),
    ("apologises", "apologetic"),
    ("sets a boundary", "boundary_setting"),
    ("brushes it off", "dismissive"),
])
def test_aliases_resolve(phrase, expected):
    assert B.resolve_move(phrase) == expected


def test_unrecognised_move_returns_none_not_a_guess():
    """★ A confidently wrong direction is worse than an honest miss: the
    cone looks equally convincing either way. Unmatched text must fall
    through to the physics mapper, not be nudged somewhere plausible."""
    assert B.resolve_move("what if the tide comes in on Thursday") is None
    assert B.nudge_for("what if the tide comes in on Thursday") is None


def test_warmer_closes_distance_not_opens_it():
    """The sign convention that reads backwards at a glance."""
    n = B.nudge_for("warmer")
    assert n["distance"] == -1 and n["trust"] == +1


def test_direction_label_is_coarse():
    assert B.direction_label(B.nudge_for("warmer")) == "converging"
    assert B.direction_label(B.nudge_for("colder")) == "diverging"


# ---------------------------------------------------------------------------
# A — physics-as-mapper
# ---------------------------------------------------------------------------
def test_every_contract_value_classifies():
    """★ The first draft invented ladders instead of reading the enum in
    _EMOTIONAL_PHYSICS_PROMPT, so real values scored None and were read as
    NO MOVEMENT -- a flat cone out of a live signal. Every declared value
    must classify as level or regime, never 'unmapped'."""
    contract = {
        "trust": ["low", "medium", "high", "fluctuating"],
        "alignment": ["aligned", "partially_aligned", "misaligned"],
        "boundary": ["clear", "soft", "collapsed", "rigid", "contested"],
        "agency": ["full", "partial", "constrained", "outsourced"],
        "distance": ["close", "moderate", "distant", "increasing", "decreasing"],
    }
    for axis, values in contract.items():
        for v in values:
            kind, _ = A.classify(axis, v)
            assert kind in ("level", "regime"), f"{axis}={v!r} classified {kind}"


def test_unclear_is_not_a_midpoint():
    """The contract's honest null must never rank as a level -- treating it
    as one invents a direction out of a refusal to answer."""
    for axis in B.AXES:
        assert A.classify(axis, "unclear") == ("unclear", None)


def test_parse_failure_is_not_usable():
    assert not A.is_usable(_reading(parse_error="bad json", trust="high"))


def test_all_unclear_is_not_usable():
    assert not A.is_usable(_reading(**{a: "unclear" for a in B.AXES}))


def test_delta_reads_the_rate_axis():
    """distance increasing -> decreasing is the whole signal for a warm
    move. It must come out negative."""
    d = A.delta_between(BASE, WARM)
    assert d["distance"] == -1
    assert d["alignment"] == +1


def test_incomparable_axes_are_reported_not_scored():
    """★ trust is 'fluctuating' (a regime) on the base, so it cannot be
    differenced against a level. Scoring it 0 would read as 'no movement'
    and is exactly the failure this module was rebuilt to avoid."""
    comp = A.comparable_axes(BASE, WARM)
    assert comp["trust"] is False
    assert comp["distance"] is True
    assert A.delta_between(BASE, WARM)["trust"] == 0  # not scored, not claimed


def test_unmapped_terms_surfaces_ladder_holes():
    r = _reading(trust="sideways", alignment="aligned")
    assert A.unmapped_terms(r) == {"trust": "sideways"}
    assert A.unmapped_terms(BASE) == {}


def test_delta_for_refuses_an_unusable_base():
    def analyze(_):
        return _reading(**{a: "unclear" for a in B.AXES})
    assert A.delta_for("base", "alt", analyze) is None


# ---------------------------------------------------------------------------
# The contract itself
# ---------------------------------------------------------------------------
def test_output_is_cone_shaped_only():
    """★★★ No field may name an outcome. Both mappers emit exactly the five
    declared axes and nothing else -- if someone adds 'predicted_reply' or
    'likely_response', this fails."""
    n = B.nudge_for("warmer")
    assert set(n) == set(B.AXES)
    d = A.delta_between(BASE, WARM)
    assert set(d) == set(B.AXES)
    for v in list(n.values()) + list(d.values()):
        assert v in (-1, 0, 1), "axes carry direction only, never magnitude"
