"""
What-if spike B — the ordinal nudge table.

★★★ THE CONTRACT: CONE-SHAPED OUTPUT ONLY.

This module returns charge, direction and dispersion. It NEVER returns a
shard. There is no field here that names what anyone will say or do, and
none may be added. The system already refuses that elsewhere --
``external_expression`` returns posture and guidance, never "say this and
they'll agree" -- and this module keeps to the same line. The cone IS the
answer, not an error bar around a missing one.

★★ WHAT THIS SOLVES

``dewey_pipeline.generate_alternative_branches`` perturbs the start vector
with a RANDOM Gaussian direction (``rng.gauss``). That gives a cone whose
width is meaningful and whose *direction* is noise. To ask "what if Suzie
comes in warm" the perturbation has to be DIRECTED, and the description of
the alternative arrives as free text.

★ AN EMBEDDER DOES NOT SOLVE THIS, and none is used here. An embedder
returns a vector in a semantic space of the wrong shape and offers no
projection into the ordinal state space below. The projection is the whole
problem. This module does it by table lookup: free, deterministic, zero
latency, zero marginal cost.

THE AXES are the five relational primitives the physics layer already
emits, so this module and ``whatif_physics_mapper`` speak the same
language and can be compared directly.

SIGN CONVENTIONS -- stated because they are otherwise guessable both ways:

    trust      +1 = more trust            -1 = less
    alignment  +1 = more aligned          -1 = more misaligned
    boundary   +1 = more intact/respected -1 = more contested/breached
    agency     +1 = more agency (subject) -1 = less
    distance   +1 = MORE distance         -1 = closer

``distance`` is the one that reads backwards at a glance: "warmer" lowers
it. It is kept as distance rather than flipped to closeness because that is
the word the physics contract already uses.
"""
from __future__ import annotations

from typing import Optional

AXES: tuple[str, ...] = ("trust", "alignment", "boundary", "agency", "distance")


def _m(trust=0, alignment=0, boundary=0, agency=0, distance=0) -> dict[str, int]:
    return {"trust": trust, "alignment": alignment, "boundary": boundary,
            "agency": agency, "distance": distance}


# ---------------------------------------------------------------------------
# The table. ~20 moves, which the order's estimate says covers most of it.
#
# Each entry is a DIRECTION, not a magnitude. Magnitude belongs to the cone's
# dispersion, not to the nudge -- claiming to know how MUCH warmer someone
# will be is exactly the shard this contract forbids.
# ---------------------------------------------------------------------------
NUDGES: dict[str, dict[str, int]] = {
    # -- toward contact -----------------------------------------------------
    "warmer":          _m(trust=+1, alignment=+1, boundary=+1, distance=-1),
    "conciliatory":    _m(trust=+1, alignment=+1, distance=-1),
    "apologetic":      _m(trust=+1, alignment=+1, agency=-1, distance=-1),
    "vulnerable":      _m(trust=+1, boundary=-1, agency=-1, distance=-1),
    "supportive":      _m(trust=+1, alignment=+1, agency=+1, distance=-1),
    "appreciative":    _m(trust=+1, alignment=+1, distance=-1),
    "curious":         _m(trust=+1, alignment=+1, agency=+1, distance=-1),

    # -- away from contact --------------------------------------------------
    "colder":          _m(trust=-1, alignment=-1, distance=+1),
    "withdrawn":       _m(trust=-1, agency=-1, distance=+1),
    "evasive":         _m(trust=-1, alignment=-1, boundary=-1, distance=+1),
    "indifferent":     _m(trust=-1, alignment=-1, agency=-1, distance=+1),
    "formal":          _m(boundary=+1, distance=+1),

    # -- pressure -----------------------------------------------------------
    "defensive":       _m(trust=-1, boundary=+1, agency=+1, distance=+1),
    "dismissive":      _m(trust=-1, alignment=-1, boundary=-1, agency=+1, distance=+1),
    "confrontational": _m(trust=-1, alignment=-1, boundary=-1, agency=+1, distance=+1),
    "hostile":         _m(trust=-1, alignment=-1, boundary=-1, agency=+1, distance=+1),
    "controlling":     _m(trust=-1, boundary=-1, agency=+1, distance=+1),
    "pleading":        _m(trust=0, alignment=+1, boundary=-1, agency=-1, distance=-1),

    # -- structural ---------------------------------------------------------
    "boundary_setting": _m(boundary=+1, agency=+1, distance=+1),
    "direct":           _m(trust=+1, boundary=+1, agency=+1),
}

# Surface phrasings that map onto a canonical move. Kept small and literal
# on purpose -- this is a lookup table, not a language model, and it should
# fail to match rather than guess.
_ALIASES: dict[str, str] = {
    "comes in warm": "warmer", "warm": "warmer", "friendly": "warmer",
    "kind": "warmer", "softer": "warmer",
    "cold": "colder", "chilly": "colder", "distant": "colder",
    "apologises": "apologetic", "apologizes": "apologetic", "sorry": "apologetic",
    "angry": "hostile", "furious": "hostile", "aggressive": "confrontational",
    "shuts down": "withdrawn", "goes quiet": "withdrawn", "silent": "withdrawn",
    "stonewalls": "withdrawn",
    "dodges": "evasive", "deflects": "evasive",
    "asks questions": "curious", "listens": "curious",
    "holds the line": "boundary_setting", "sets a boundary": "boundary_setting",
    "professional": "formal", "polite": "formal",
    "opens up": "vulnerable", "honest": "direct", "blunt": "direct",
    "backs me up": "supportive", "thanks me": "appreciative",
    "brushes it off": "dismissive", "belittles": "dismissive",
    "insists": "controlling", "demands": "controlling",
    "begs": "pleading",
}


def available_moves() -> tuple[str, ...]:
    return tuple(sorted(NUDGES))


def resolve_move(text: str) -> Optional[str]:
    """Map free text to a canonical move, or None.

    ★ Returns None rather than guessing. An unmatched alternative must fall
    through to the physics mapper (spike A), not be silently nudged in a
    direction nobody asked for -- a confidently wrong direction is worse
    than an honest miss, because the cone would look just as convincing.
    """
    if not text:
        return None
    t = " ".join(text.lower().split())
    if t in NUDGES:
        return t
    if t in _ALIASES:
        return _ALIASES[t]
    # Longest alias first, so "goes quiet" wins over a bare "quiet" substring.
    for phrase in sorted(_ALIASES, key=len, reverse=True):
        if phrase in t:
            return _ALIASES[phrase]
    for move in sorted(NUDGES, key=len, reverse=True):
        if move in t:
            return move
    return None


def nudge_for(text: str) -> Optional[dict[str, int]]:
    """Directed perturbation for an alternative described in free text.
    None when the move is unrecognised."""
    move = resolve_move(text)
    return dict(NUDGES[move]) if move else None


def charge(nudge: dict[str, int]) -> int:
    """How much of the state this move touches -- the cone's charge. Not a
    magnitude per axis; the count of axes moved."""
    return sum(1 for a in AXES if nudge.get(a, 0) != 0)


def direction_label(nudge: dict[str, int]) -> str:
    """Coarse regime for the cone. Deliberately three words wide: any finer
    and it starts describing an outcome."""
    toward = -nudge.get("distance", 0) + nudge.get("trust", 0)
    if toward > 0:
        return "converging"
    if toward < 0:
        return "diverging"
    return "lateral"
