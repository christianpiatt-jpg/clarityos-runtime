"""
problem_solver/auto_trigger.py — V75 / ProblemSolver.REGRESSION_FIRST.

Pure detection helper that decides whether an incoming
operator message should auto-start a regression chain. This module
performs **no side effects**: it returns a boolean (and an optional
extracted problem statement). The caller decides whether to actually
open a chain via ``regression_first.start_chain`` (or to process the
text upstream into a packet that ``regression_first.analyze_packet``
can parse).

The contract:

    should_auto_trigger(text, *, el_ins_result=None) -> bool
    extract_problem(text) -> str

When ``el_ins_result`` is supplied, the detector is stricter — it
only fires when EL/INS classifies the text as ``high_el``. Without an
EL/INS result, a cue-word match alone is sufficient (the OS may want
a chain even when the operator is calm-but-clear about a problem).

CUE words are a tight, lowercase frozenset. Adding obscure words
inflates false positives. Keep it tight.
"""
from __future__ import annotations

import re
from typing import Optional


# Problem-cue tokens. Tight, lowercased, intentionally non-poetic.
# Hyphenated forms are split during tokenisation (matches el_ins'
# tokeniser), so include single-word forms only here.
CUE_WORDS: frozenset[str] = frozenset({
    "broken",
    "bug",
    "buggy",
    "crash",
    "crashed",
    "crashing",
    "error",
    "errors",
    "failed",
    "failing",
    "failure",
    "fails",
    "glitch",
    "hang",
    "hung",
    "incorrect",
    "issue",
    "misbehaving",
    "problem",
    "regression",
    "stuck",
    "wrong",
})


# Multi-word cue phrases. Matched verbatim, case-insensitive, on the
# raw text (not the token stream).
CUE_PHRASES: tuple[str, ...] = (
    "doesn't work",
    "does not work",
    "didn't work",
    "did not work",
    "not working",
    "isn't working",
    "is not working",
    "won't work",
    "will not work",
    "out of order",
    "not responding",
)


# Tokeniser identical to el_ins'. Lowercase, hyphen+apostrophe kept
# inside tokens.
_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z\-']*")


def _tokenise(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


def should_auto_trigger(
    text: str,
    *,
    el_ins_result: Optional[dict] = None,
) -> bool:
    """Return ``True`` iff ``text`` looks like a problem report.

    When ``el_ins_result`` is supplied, both conditions must hold:
        - cue word/phrase present, AND
        - el_ins_result['analysis']['ratio_classification'] == 'high_el'

    When ``el_ins_result`` is None, a cue-word/phrase match alone is
    sufficient.
    """
    text = (text or "").strip()
    if not text:
        return False

    cue_present = _has_cue(text)
    if not cue_present:
        return False

    if el_ins_result is None:
        return True

    analysis = (el_ins_result or {}).get("analysis") or {}
    classification = analysis.get("ratio_classification")
    return classification == "high_el"


def _has_cue(text: str) -> bool:
    """Pure cue-presence test. Public for tests + integration code."""
    lower = text.lower()
    for phrase in CUE_PHRASES:
        if phrase in lower:
            return True
    tokens = _tokenise(text)
    for tok in tokens:
        if tok in CUE_WORDS:
            return True
    return False


def extract_problem(text: str) -> str:
    """Return a normalised problem statement for downstream callers
    (e.g. ``regression_first.start_chain``). Strips and collapses
    whitespace. Always returns a string — empty/whitespace-only
    input yields ``""`` (never ``None``).
    """
    text = (text or "").strip()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)
