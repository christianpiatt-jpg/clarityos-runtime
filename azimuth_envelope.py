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
Phase 1 skeleton — schemas locked in ``azimuth.py``. Function bodies
raise ``NotImplementedError`` pending Phase 3 Unit 5 real implementation.

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

from typing import Optional

from azimuth import (
    EnvelopeState,
    IntensityLevel,
    PressureLevel,
    Valence,
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
    raise NotImplementedError(
        "azimuth_envelope.capture_envelope — Phase 3 Unit 5 implementation",
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
    raise NotImplementedError(
        "azimuth_envelope.evaluate_envelope — Phase 3 Unit 5 implementation",
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
    raise NotImplementedError(
        "azimuth_envelope.mark_externalize — Phase 3 Unit 5 implementation",
    )
