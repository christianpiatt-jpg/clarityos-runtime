"""
What-if spike A — physics-as-mapper, and the check on the nudge table.

``/me/emotional_physics/analyze`` is ALREADY a text -> state function. So an
alternative described in free text can be turned into a directed
perturbation without any new model, any new adapter, and above all without
an embedder:

    base text            -> reading A
    base + alternative   -> reading B
    delta(A, B)          =  the directed perturbation

★ NO EMBEDDER. Nothing here produces or consumes a semantic vector. The
projection into state space is done by the physics layer, which already
emits the five ordinal relational primitives, and the delta is taken in
that ordinal space directly.

★★ THIS IS THE FALLBACK, NOT THE DEFAULT. It costs a model call per branch
(~$0.006 cached) and adds latency, where ``whatif_nudge`` is free and
instant. Its real job is to be the CHECK on the table: where the two
disagree is where the table is wrong or incomplete, and the disagreement
rate is what says how big the table needs to be.

★★★ CONE-SHAPED OUTPUT ONLY. Same contract as ``whatif_nudge`` -- axis
directions, charge, regime. No field here names an outcome, and none may
be added.

★ DEGRADE: a reading whose ``_meta.parse_error`` is non-null, or whose
primitives are entirely "unclear", is NOT a state. It is a refusal or a
failure, and either way differencing it produces a direction that looks
authoritative and means nothing. ``delta_for`` returns None in both cases
rather than a confident zero.
"""
from __future__ import annotations

from typing import Callable, Optional

from whatif_nudge import AXES

# ---------------------------------------------------------------------------
# Ordinal ladders for the five relational primitives.
#
# The physics contract emits these as words. To difference two readings the
# words need an order. Ladders run LOW -> HIGH in the same sign convention
# whatif_nudge documents (distance: higher = further apart).
#
# "unclear" is deliberately NOT on any ladder -- it is the contract's honest
# null, not a midpoint, and treating it as one would silently invent a
# direction out of a refusal to answer.
# ---------------------------------------------------------------------------
# ★★★ THE VOCABULARY IS A CLOSED ENUM, DECLARED IN THE PROMPT.
# intelligence_kernel.py, _EMOTIONAL_PHYSICS_PROMPT, LAYER 3:
#
#     trust:     low | medium | high | fluctuating | unclear
#     alignment: aligned | partially_aligned | misaligned | unclear
#     boundary:  clear | soft | collapsed | rigid | contested | unclear
#     agency:    full | partial | constrained | outsourced | unclear
#     distance:  close | moderate | distant | increasing | decreasing | unclear
#
# The first draft of this module INVENTED ladders ("eroding", "porous",
# "narrowing", "severed") instead of reading that block. Almost none of those
# words are in the contract, so real values scored None and were read as NO
# MOVEMENT -- the mapper reported a flat cone out of a live signal. Read the
# contract, do not guess the vocabulary.
#
# ★★ AND THREE OF THE FIVE AXES ARE NOT ORDINAL.
#
#   trust     mixes a LEVEL (low/medium/high) with a REGIME (fluctuating)
#   boundary  mixes integrity (clear/collapsed) with two OPPOSITE deviations
#             (soft, rigid) -- they are not two ends of one line
#   distance  mixes a LEVEL (close/moderate/distant) with a RATE
#             (increasing/decreasing)
#
# Only alignment and agency are cleanly ordinal. So "difference two readings"
# is undefined on the other three unless level and regime are separated --
# and a mapper that quietly ranks them anyway manufactures direction. Values
# of different KINDS are reported incomparable, not scored zero.
LEVELS: dict[str, tuple[str, ...]] = {
    "trust":     ("low", "medium", "high"),
    "alignment": ("misaligned", "partially_aligned", "aligned"),
    "boundary":  ("collapsed", "contested", "clear"),
    "agency":    ("outsourced", "constrained", "partial", "full"),
    "distance":  ("close", "moderate", "distant"),
}

# Non-ordinal values on the same axis. Present in the contract, meaningful,
# and NOT a point on the level ladder.
REGIMES: dict[str, tuple[str, ...]] = {
    "trust":    ("fluctuating",),
    "boundary": ("soft", "rigid"),
    "distance": ("decreasing", "increasing"),
}

# Directional reading for the rate-like regimes, used only where the contract
# makes the direction explicit. Everything else is regime-only.
_RATE_SIGN: dict[str, dict[str, int]] = {
    "distance": {"decreasing": -1, "increasing": +1},
}


def classify(axis: str, value: object) -> tuple[str, Optional[object]]:
    """Return ``(kind, payload)`` for one contract value.

    kind is one of:
      "level"        payload = int position on LEVELS[axis]
      "regime"       payload = the regime word
      "unclear"      payload = None   -- the contract's honest null
      "unmapped"     payload = the raw word -- a hole, must stay visible
      "absent"       payload = None
    """
    if not isinstance(value, str) or not value.strip():
        return ("absent", None)
    v = value.strip().lower().replace(" ", "_")
    if v == "unclear":
        return ("unclear", None)
    levels = LEVELS.get(axis) or ()
    if v in levels:
        return ("level", levels.index(v))
    if v in (REGIMES.get(axis) or ()):
        return ("regime", v)
    return ("unmapped", value)


def primitives_of(reading: dict) -> dict[str, tuple[str, Optional[object]]]:
    rp = (reading or {}).get("relational_primitives") or {}
    return {a: classify(a, rp.get(a)) for a in AXES}


def is_usable(reading: dict) -> bool:
    """A reading is usable only if it parsed AND said something.

    ★ Both failure modes present as a 200 carrying "unclear" everywhere and
    are byte-identical apart from ``_meta.parse_error``. Measured
    2026-08-26: a bare perspective frame with no situation returns
    parse_error None -- an honest null, not a parse failure. Both are
    unusable here, but for different reasons, and only this field tells
    them apart.
    """
    meta = (reading or {}).get("_meta") or {}
    if meta.get("parse_error"):
        return False
    kinds = primitives_of(reading)
    return any(k in ("level", "regime") for k, _ in kinds.values())


def delta_for(
    base_text: str,
    alternative_text: str,
    analyze: Callable[[str], dict],
) -> Optional[dict[str, int]]:
    """Directed perturbation from two physics readings.

    ``analyze`` is injected so this module does no I/O of its own and stays
    testable against recorded readings. Returns axis -> {-1, 0, +1}, or None
    when either reading is unusable.
    """
    a = analyze(base_text)
    if not is_usable(a):
        return None
    b = analyze(f"{base_text}\n\n{alternative_text}")
    if not is_usable(b):
        return None
    return delta_between(a, b)


def unmapped_terms(reading: dict) -> dict[str, str]:
    """Axis -> the word the contract emitted that no ladder covers.

    ★ Coverage must be observable. A word this module cannot rank is a hole
    in the ladder, and it is indistinguishable at the delta from a genuine
    "nothing moved" unless it is reported separately. Callers should print
    this, not swallow it.
    """
    out: dict[str, str] = {}
    for axis, (kind, payload) in primitives_of(reading).items():
        if kind == "unmapped":
            out[axis] = str(payload)
    return out


def delta_between(reading_a: dict, reading_b: dict) -> dict[str, int]:
    """Sign of the ordinal movement per axis. Sign only, not magnitude:
    the physics words are ordinal, not metric, so the gap between
    'eroding' and 'fluctuating' is not a distance and must not be
    reported as one."""
    ra, rb = primitives_of(reading_a), primitives_of(reading_b)
    out: dict[str, int] = {}
    for axis in AXES:
        ka, pa = ra.get(axis, ("absent", None))
        kb, pb = rb.get(axis, ("absent", None))
        if ka == "level" and kb == "level":
            out[axis] = (pb > pa) - (pb < pa)
        elif kb == "regime" and axis in _RATE_SIGN:
            # A rate answers the direction question directly, whatever the
            # other side was: "decreasing" IS a converging move.
            out[axis] = _RATE_SIGN[axis].get(str(pb), 0)
        else:
            # Different kinds, unclear, or a hole. Refusing to score is the
            # point -- inventing a sign here is how a flat cone starts
            # looking authoritative.
            out[axis] = 0
    return out


def comparable_axes(reading_a: dict, reading_b: dict) -> dict[str, bool]:
    """Which axes the two readings can actually be differenced on. Callers
    should report the incomparable ones rather than counting them as
    agreement or disagreement."""
    ra, rb = primitives_of(reading_a), primitives_of(reading_b)
    out: dict[str, bool] = {}
    for axis in AXES:
        ka, _ = ra.get(axis, ("absent", None))
        kb, _ = rb.get(axis, ("absent", None))
        out[axis] = (ka == "level" and kb == "level") or (
            kb == "regime" and axis in _RATE_SIGN)
    return out
