"""
cite_mode.py — `#cite` source-required validator (interpreter-layer, pure).

Standalone deterministic core for the `#cite` directive (A17). Two public fns:

    parse_cite_directive(text)  -> (is_cite: bool, stripped_text: str)
    validate_cite_output(text)  -> ValidationResult

`#cite` is a grounding constraint: factual claims must carry a citation, and
opinions must declare a basis (metric / poll / ranking / dataset). This module
ONLY decides whether grounding is *present* and, if not, what re-query
instruction to issue. It performs NO model calls, NO retrieval, NO I/O, and is
wired into nothing — it's the primitive the eventual integration (A18) builds
on (kernel vs dispatcher vs a new layer — that's a separate decision).

Detection is heuristic (regex + keyword): a MISSING-grounding gate, not a
correctness check. It flags output that lacks a source/basis; it does not
verify the source is real or correct. False positives are acceptable per spec.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

CITE_DIRECTIVE = "#cite"
FACTUAL_REQUERY = "Provide authoritative source for each factual claim."
OPINION_REQUERY = "Provide the basis (metric, poll, ranking, dataset) for each opinion."


@dataclass
class ValidationResult:
    ok: bool
    needs_retry: bool
    retry_instruction: Optional[str]
    reasons: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Directive parsing
# ---------------------------------------------------------------------------
def parse_cite_directive(text: str) -> Tuple[bool, str]:
    """``(is_cite, stripped_text)``. Detects a leading ``#cite`` token
    (case-insensitive, word-bounded so ``#citecisely`` won't match), and strips
    it plus any following whitespace / ``:`` / ``-``. One-turn; no persistence.
    Non-#cite (or non-str) input returns ``(False, text)`` unchanged."""
    if not isinstance(text, str):
        return False, text
    stripped = text.lstrip()
    m = re.match(r"#cite\b", stripped, flags=re.IGNORECASE)
    if not m:
        return False, text
    return True, stripped[m.end():].lstrip(" \t:-")


# ---------------------------------------------------------------------------
# Heuristic detectors (internal)
# ---------------------------------------------------------------------------
_FACTUAL_SUPERLATIVES = (
    "highest", "lowest", "largest", "smallest", "biggest", "fastest", "slowest",
    "longest", "shortest", "tallest", "oldest", "newest", "first", "last",
    "most populous", "record",
)
_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
)
_OPINION_WORDS = (
    "best", "worst", "greatest", "finest", "favorite", "favourite", "overrated",
    "underrated", "most influential", "most beautiful", "most important",
    "arguably", "in my opinion", "i think", "i believe", "better than", "worse than",
)
_CITATION_PATTERNS = (
    r"\baccording to\b",
    r"\bsource\s*:",
    r"\bcit(?:ed|ation|ing)\b",
    r"\b\d+\s+u\.?\s?s\.?\s+\d+\b",            # 467 U.S. 837
    r"\b\d+\s+u\.?s\.?c\.?\b",                 # 42 USC
    r"\bv\.\s+\w+",                            # case "v. Name"
    r"\(\s*\d{4}\s*\)",                        # (1984)
    r"\b(?:report|poll|survey|index|database|dataset|census|study|journal|statistics?)\b",
    r"\b(?:cdc|who|fbi|imdb|nielsen|comscore|gallup|pew|noaa|nasa|oecd|imf|"
    r"reuters|bloomberg|rotten tomatoes|sight\s*&\s*sound|chevron)\b",
    r"\bet al\.?",
    r"\bdoi[:\s]",
    r"https?://",
)
_BASIS_PATTERNS = (
    r"\b(?:using|based on|according to|drawn from|measured by)\b",
    r"\b(?:rating|ratings|score|scores|poll|ranking|rankings|metric|metrics|"
    r"dataset|criteria|index|box office|attendance|sales|gross)\b",
)


def _has_any(text: str, patterns) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


def _has_keyword(text: str, words) -> bool:
    low = text.lower()
    return any(re.search(rf"\b{re.escape(w)}\b", low) for w in words)


def _detect_factual_claim(text: str) -> bool:
    """numbers / dates / rankings / superlatives / measurable assertions."""
    t = text or ""
    if re.search(r"\d", t):  # any digit -> numeric / dated / statistical claim
        return True
    return _has_keyword(t, _FACTUAL_SUPERLATIVES) or _has_keyword(t, _MONTHS)


def _detect_citation(text: str) -> bool:
    """authoritative source signals (publication / agency / statute / case / URL)."""
    return _has_any(text or "", _CITATION_PATTERNS)


def _detect_opinion(text: str) -> bool:
    """subjective / quality judgments ("best", "greatest", "most influential")."""
    return _has_keyword(text or "", _OPINION_WORDS)


def _detect_basis(text: str) -> bool:
    """declared basis for an opinion ("using X ratings", "based on Y poll")."""
    return _has_any(text or "", _BASIS_PATTERNS)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_cite_output(text: str) -> ValidationResult:
    """Validate model output under `#cite`. A factual claim without a citation,
    or an opinion without a basis, sets ``needs_retry`` + the matching
    instruction(s). Otherwise ``ok=True`` with no instruction."""
    t = text if isinstance(text, str) else ""
    reasons: List[str] = []
    instructions: List[str] = []

    if _detect_factual_claim(t) and not _detect_citation(t):
        reasons.append("factual_claim_without_citation")
        instructions.append(FACTUAL_REQUERY)
    if _detect_opinion(t) and not _detect_basis(t):
        reasons.append("opinion_without_basis")
        instructions.append(OPINION_REQUERY)

    needs_retry = bool(reasons)
    return ValidationResult(
        ok=not needs_retry,
        needs_retry=needs_retry,
        retry_instruction=(" ".join(instructions) if instructions else None),
        reasons=reasons,
    )
