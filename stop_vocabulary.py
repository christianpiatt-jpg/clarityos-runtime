"""#196 (CT-1 2026-09-09) -- ONE stop vocabulary, backend-side.

Every vendor names the end of a generation differently. Before this module
each surface applied the same wrong rule -- "anything that is not
``end_turn`` is a cut" -- so a perfectly normal OpenAI ``stop`` and a
perfectly normal Gemini ``STOP`` both rendered "stopped early" on a reply
the model had finished saying.

The table below is the one place that knows what a raw vendor token means.
It answers with exactly three words:

    normal    the model finished on its own
    cut       the model was stopped before it finished
    unknown   a token this table has never seen

``unknown`` is NOT a cut and NOT a completion. A caller renders nothing for
it and this module logs the raw token ONCE, so an unrecognised vendor word
shows up in the log as a thing to add here rather than as a wrong mark on a
member's screen. Absence (a mock reply, an older wire, a provider that sends
no signal) is a different KIND again: ``classify_stop`` answers ``None``,
nothing is logged, and nothing renders.

The RAW vendor string is never replaced. It stays on ``_meta.stop_reason``
so the surface can name the instrument (R5.3); this module only says which
of the three kinds it is, on ``_meta.stop_class``.

Matching is case-insensitive after a strip, which is what makes the table
one vocabulary rather than six: Gemini's ``STOP`` and OpenAI's ``stop`` are
the same word, and Gemini's ``MAX_TOKENS`` and Anthropic's ``max_tokens``
are the same word. Nothing else is inferred -- an unlisted token is
``unknown``, never a guess.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

logger = logging.getLogger("clarityos.stop_vocabulary")

NORMAL = "normal"
CUT = "cut"
UNKNOWN = "unknown"

#: The table. Keys are the folded form (strip + lowercase) of the raw vendor
#: token; the comment on each line names the vendor(s) that emit it. Adding a
#: vendor means adding a line here and nowhere else.
STOP_VOCABULARY: dict[str, str] = {
    # ---- the model finished on its own -------------------------------
    "end_turn":       NORMAL,   # Anthropic
    "stop":           NORMAL,   # OpenAI, Ollama (done_reason), most OpenAI-compatible
    "stop_sequence":  NORMAL,   # Anthropic (a configured stop sequence matched)
    "eos":            NORMAL,   # local runtimes (llama.cpp and friends)
    # Gemini's "STOP" folds onto "stop"; it is the same word.

    # ---- the model was cut off ---------------------------------------
    "max_tokens":     CUT,      # Anthropic; Gemini's "MAX_TOKENS" folds onto this
    "length":         CUT,      # OpenAI (finish_reason)
    "content_filter": CUT,      # OpenAI
    "safety":         CUT,      # Gemini's "SAFETY"
}

# ---------------------------------------------------------------------------
# THE BOUNDARY OF THIS TABLE, NAMED (ET-1 -> CT-1, #196).
#
# The table above is CT-1's, word for word, and his rule for anything else is
# UNKNOWN -- so these are NOT added here. But they are real tokens that real
# adapters in this repo can return, and under the rule each now renders
# nothing where the old (wrong) rule rendered "stopped early: <word>". Two of
# them are genuinely cuts, which is the direction that loses information:
#
#   refusal                        Anthropic -- the model declined to
#                                  continue. A CUT in everything but name;
#                                  model_router's own comment names it
#                                  ("end_turn / max_tokens / refusal / ..."),
#                                  and the phone's pre-#196 test used it as
#                                  the example of a mark.
#   RECITATION                     Gemini -- output suppressed. A cut.
#   BLOCKLIST                      Gemini -- blocked. A cut.
#   PROHIBITED_CONTENT             Gemini -- blocked. A cut.
#   MALFORMED_FUNCTION_CALL        Gemini -- a cut.
#   OTHER                          Gemini -- unspecified. Unclassifiable.
#   FINISH_REASON_UNSPECIFIED      Gemini -- unspecified. Unclassifiable.
#   model_context_window_exceeded  OpenAI -- a cut.
#   tool_calls / function_call     OpenAI -- normal structured stops.
#   tool_use / pause_turn          Anthropic -- normal structured stops; no
#                                  tool path reaches this route today.
#   load                           local runtimes -- a cut.
#
# Rendering nothing is the SAFE direction (it never claims a finished reply
# was cut) and every one of them is logged once by classify_stop, so they
# surface as words to rule on rather than as wrong marks on a member's
# screen. A one-line addition each, once CT-1 rules.
# ---------------------------------------------------------------------------

#: Raw tokens already reported, so the log carries one line per unseen word
#: rather than one per turn. Process-local and intentionally unbounded in
#: theory, bounded in practice by the number of distinct vendor tokens.
_SEEN_UNKNOWN: set[str] = set()
_SEEN_LOCK = threading.Lock()


def fold(raw: str) -> str:
    """The lookup key for a raw vendor token."""
    return raw.strip().lower()


def classify_stop(raw: object) -> Optional[str]:
    """Return ``"normal"``, ``"cut"``, ``"unknown"`` -- or ``None``.

    ``None`` means there was no stop signal at all (a mock reply, a provider
    that sends none, an older wire). That is a different kind from
    ``"unknown"``, which means a signal arrived and this table does not know
    the word. Only ``"unknown"`` is logged, and only the first time each
    distinct token is seen.

    Never raises: a caller is on a member's turn.
    """
    if not isinstance(raw, str):
        return None
    key = fold(raw)
    if not key:
        return None
    kind = STOP_VOCABULARY.get(key)
    if kind is not None:
        return kind
    with _SEEN_LOCK:
        first = key not in _SEEN_UNKNOWN
        if first:
            _SEEN_UNKNOWN.add(key)
    if first:
        # The raw token only -- it is a vendor enum, never member text.
        logger.warning("stop_vocabulary unknown token=%r -- add it to STOP_VOCABULARY", raw)
    return UNKNOWN


def is_cut(raw: object) -> bool:
    """True only when the table says the reply was cut off."""
    return classify_stop(raw) == CUT


def _reset_seen_for_tests() -> None:
    """Test hook: forget which unknown tokens have been logged."""
    with _SEEN_LOCK:
        _SEEN_UNKNOWN.clear()
