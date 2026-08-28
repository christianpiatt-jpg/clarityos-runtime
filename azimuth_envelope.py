"""
azimuth_envelope.py — Envelope Layer (Azimuth Mechanic, Track 1).

The intimate, zero-judgment layer that captures raw user reflection
without moralizing or optimizing. Raw content NEVER leaves this layer.

ROLE IN THE ARCHITECTURE
------------------------
The Envelope is the innermost privacy boundary. Whatever the user puts
in stays in. Other layers may derive structural metadata from the
EnvelopeState (intensity / valence / pressure / intention class) but
must never serialize or transmit ``raw_text``.

PHASE STATUS
------------
Phase 3 Unit 5 — IMPLEMENTED 2026-08-28. Schemas remain locked in
``azimuth.py``; this module fills the bodies the Phase 1 skeleton declared.
The heuristic list in ``capture_envelope``'s docstring is the specification
and was implemented as written, not redesigned. Lexicons and per-axis
scorers live in ``azimuth_envelope_impl`` so the tables stay reviewable
apart from the banding.

PUBLIC API
----------
    capture_envelope(raw_text, **hints)   -> EnvelopeState
    evaluate_envelope(env)                -> EnvelopeState
    mark_externalize(env)                 -> EnvelopeState

INVARIANTS (locked, enforced by tests + design discipline)
----------------------------------------------------------
    * No network call from any function in this module.
    * No logging of raw_text beyond local DEBUG.
    * Every returned EnvelopeState is a frozen dataclass — the layer
      cannot be tricked into mutating the user's intimate state.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Optional

import azimuth_envelope_impl as _impl
from azimuth import (
    EnvelopeState,
    IntensityLevel,
    PressureLevel,
    Valence,
)




# ===========================================================================
# Banding. Thresholds live here; lexicons live in azimuth_envelope_impl.
# ===========================================================================
# The scorers return signed integers. These tables turn a score into the
# LOCKED enum the schema demands. Kept beside each other so the whole
# score -> level story is one screen.
#
# ★★ A CEILING AND A FLOOR WORTH KNOWING, both properties of the locked
# schema rather than of the heuristic:
#   IntensityLevel has no level BELOW "low", so hedging can only pull a
#   score down TO low, never past it. "this is fine" (score 0) and "kind of
#   a bit maybe bad" (score -3) both band to LOW. The score moves; the enum
#   cannot. Reported, not worked around -- adding a level would change the
#   schema, which this order forbids.
_INTENSITY_BANDS = (
    (6, IntensityLevel.EXTREME),
    (3, IntensityLevel.HIGH),
    (1, IntensityLevel.MEDIUM),
)
_PRESSURE_BANDS = (
    (6, PressureLevel.CRITICAL),
    (3, PressureLevel.HIGH),
    (1, PressureLevel.MEDIUM),
)


def _band(score, bands, floor):
    for threshold, level in bands:
        if score >= threshold:
            return level
    return floor


def _valence_of(text: str) -> Valence:
    pos, neg = _impl.valence_score(text)
    if pos and neg:
        return Valence.MIXED
    if pos:
        return Valence.POSITIVE
    if neg:
        return Valence.NEGATIVE
    return Valence.NEUTRAL


def _derive(text: str):
    """All four axes, or an exception. Never a partial fill.

    ★★ NO DEFAULTS. A frozen dataclass returned with three fields guessed is
    the ``N = 5.0`` failure in a different hat -- a complete, plausible,
    meaningless state. If the input cannot be scored, this raises and the
    caller gets nothing rather than something wrong.
    """
    if not isinstance(text, str):
        raise TypeError(
            "capture_envelope: raw_text must be str, got %s" % type(text).__name__
        )
    if not text.strip():
        raise ValueError(
            "capture_envelope: raw_text is empty; refusing to derive an "
            "envelope from nothing (a defaulted state is worse than none)"
        )
    return (
        _band(_impl.intensity_score(text), _INTENSITY_BANDS, IntensityLevel.LOW),
        _valence_of(text),
        _band(_impl.pressure_score(text), _PRESSURE_BANDS, PressureLevel.LOW),
        _impl.intention_of(text),
    )


# ---------------------------------------------------------------------------
# capture_envelope
# ---------------------------------------------------------------------------
def capture_envelope(
    raw_text: str,
    *,
    explicit_intensity: Optional[IntensityLevel] = None,
    explicit_valence:   Optional[Valence] = None,
    explicit_pressure:  Optional[PressureLevel] = None,
    explicit_intention: Optional[str] = None,
) -> EnvelopeState:
    """Capture a raw reflection into envelope state.

    Args:
        raw_text:            the user's unfiltered reflection (any content).
        explicit_intensity:  optional user-supplied intensity override.
        explicit_valence:    optional user-supplied valence override.
        explicit_pressure:   optional user-supplied pressure override.
        explicit_intention:  optional user-supplied "rough intention" string.

    Returns:
        EnvelopeState with:
            * raw_text preserved verbatim (still on device)
            * captured_at = now (UTC)
            * emotional_intensity computed (lexical heuristic on amplifiers /
              softeners), or explicit override.
            * valence computed (lexical positive / negative markers), or
              explicit override.
            * pressure_level computed (urgency / criticality markers),
              or explicit override.
            * rough_intention inferred (imperative → "request",
              first-person past → "vent", "I'm sorry" → "apologize",
              etc.), or explicit override.
            * user_marked_externalize = False (default)
            * envelope_id = fresh local id

    Implementation guidance (Phase 3 Unit 5):
        * Intensity heuristics: "really", "so", "absolutely", "extremely",
          all-caps phrases, exclamation density, profanity → bump.
          Hedges ("kind of", "a bit", "maybe") → reduce.
        * Valence heuristics: pos lexicon vs neg lexicon, with negation
          inversion ("not great" → negative).
        * Pressure heuristics: deadline markers, "have to", "must",
          "before <date>", crisis vocabulary.
        * Rough intention heuristics: imperative verb count, first-person
          past tense ratio, presence of "I'm sorry" / "I apologize",
          "I need" / "can you" markers.

    INVARIANTS:
        * No network call.
        * No logging of raw_text beyond local DEBUG.
        * Return value is a frozen dataclass — caller cannot mutate it.
    """
    intensity, valence, pressure, intention = _derive(raw_text)
    # raw_text is preserved verbatim and NEVER logged or transmitted -- the
    # envelope is the innermost privacy boundary.
    return EnvelopeState(
        raw_text=raw_text,
        captured_at=datetime.now(timezone.utc),
        emotional_intensity=explicit_intensity or intensity,
        valence=explicit_valence or valence,
        pressure_level=explicit_pressure or pressure,
        rough_intention=explicit_intention or intention,
        user_marked_externalize=False,
    )


# ---------------------------------------------------------------------------
# evaluate_envelope
# ---------------------------------------------------------------------------
def evaluate_envelope(env: EnvelopeState) -> EnvelopeState:
    """Re-evaluate structural metadata on an existing envelope.

    Useful when the heuristics (or weights) update without changing the
    raw_text. Returns a NEW EnvelopeState with the same ``raw_text`` and
    ``envelope_id`` but recomputed ``emotional_intensity`` / ``valence``
    / ``pressure_level`` / ``rough_intention``.

    Idempotent on stable heuristics: ``evaluate_envelope(evaluate_envelope(e)) == evaluate_envelope(e)``.
    """
    intensity, valence, pressure, intention = _derive(env.raw_text)
    # replace() keeps raw_text, envelope_id, captured_at and the
    # externalize flag; only the derived metadata is recomputed. That is
    # what makes evaluate_envelope(evaluate_envelope(e)) == evaluate_envelope(e).
    return replace(
        env,
        emotional_intensity=intensity,
        valence=valence,
        pressure_level=pressure,
        rough_intention=intention,
    )


# ---------------------------------------------------------------------------
# mark_externalize
# ---------------------------------------------------------------------------
def mark_externalize(env: EnvelopeState) -> EnvelopeState:
    """Flip ``user_marked_externalize=True`` on the envelope.

    The user has explicitly signaled they want to consider expressing
    this. Returns a new frozen EnvelopeState; the original is untouched
    (caller can keep the pre-externalization snapshot for journal /
    reflection).
    """
    # A frozen copy: the caller keeps the pre-externalization snapshot.
    return replace(env, user_marked_externalize=True)
