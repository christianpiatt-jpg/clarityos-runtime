"""
reduce_signal.py — deterministic signal compression for #reduce (A26).

Pure, side-effect-free reduction: drop filler/scaffolding, separate core
claims from supporting evidence, and emit a minimal essence form. Produces:

    core_claims   — non-filler, non-evidence assertions
    evidence      — sentences carrying an evidence signal (numbers, citations,
                    examples, study/data/report …)
    minimal       — the core claims with leading discourse connectives stripped

HONESTY NOTE (same posture as the other semantic handlers): this is a
deterministic HEURISTIC, not summarisation. The runtime has no NLP dependency,
so "core claim vs evidence vs filler" is keyword/structure-based — lossy and
approximate. It compresses by removing scaffolding, not by understanding.

Connective stripping requires a trailing COMMA ("However, X" -> "X") so that
content like "First responders" is never mangled.

Determinism: sentences are processed in text order; marker checks are boolean
membership over fixed tuples (no set-iteration in the output path).
"""
from __future__ import annotations

import re
from typing import Dict, List

_CAP = 25
_CLAUSE_MAXLEN = 240

_FILLER_STARTS = (
    "let me", "let's", "let us", "here is", "here's", "i hope", "i will explain",
    "to begin", "to start", "as an ai", "in this response", "welcome",
    "first, some", "before we", "in this section",
)
_FILLER_CONTAINS = (
    "hope this helps", "let me know if", "feel free to", "as we all know",
    "without further ado",
)
_EVIDENCE_MARKERS = (
    "according to", "study", "studies", "data", "survey", "report", "reports",
    "statistics", "for example", "for instance", "e.g.", "such as", "research",
    "percent", "measured", "sample", "evidence", "cited", "source",
)
_CONNECTIVES = (
    "however", "therefore", "moreover", "furthermore", "additionally",
    "in addition", "thus", "hence", "consequently", "nonetheless",
    "nevertheless", "in conclusion", "in summary", "to summarize", "that said",
    "basically", "essentially", "of course", "clearly", "obviously", "overall",
    "first", "second", "third", "finally", "next", "then", "so", "also",
    "besides", "indeed",
)

_CONN_RE = re.compile(
    r"^\s*(?:%s)\s*,\s+" % "|".join(re.escape(w) for w in _CONNECTIVES),
    re.I,
)


def _sentences(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]


def _trim(s: str) -> str:
    s = s.strip()
    return s if len(s) <= _CLAUSE_MAXLEN else s[:_CLAUSE_MAXLEN].rstrip() + "…"


def _dedup(seq: List[str]) -> List[str]:
    seen, out = set(), []
    for x in seq:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _is_filler(s: str) -> bool:
    ls = s.lower().strip()
    if len(s.split()) < 3:
        return True
    if any(ls.startswith(p) for p in _FILLER_STARTS):
        return True
    return any(p in ls for p in _FILLER_CONTAINS)


def _is_evidence(s: str) -> bool:
    if re.search(r"\d", s):          # numbers / dates / percentages
        return True
    ls = s.lower()
    return any(m in ls for m in _EVIDENCE_MARKERS)


def _strip_connectives(s: str) -> str:
    prev = None
    while prev != s:
        prev = s
        s = _CONN_RE.sub("", s, count=1)
    return s.strip() or prev


def reduce_text(text: str) -> Dict:
    """Reduce ``text`` to claims / evidence / minimal essence. Non-str/empty
    → empty reduction."""
    if not isinstance(text, str) or not text.strip():
        return {"core_claims": [], "evidence": [], "minimal": []}
    claims: List[str] = []
    evidence: List[str] = []
    for s in _sentences(text):
        if _is_filler(s):
            continue
        if _is_evidence(s):
            evidence.append(_trim(s))
        else:
            claims.append(_trim(s))
    claims = _dedup(claims)[:_CAP]
    evidence = _dedup(evidence)[:_CAP]
    minimal = [_strip_connectives(c) for c in claims]
    return {"core_claims": claims, "evidence": evidence, "minimal": minimal}


def build_metadata(r: Dict, original_text: str) -> Dict:
    minimal_text = " ".join(r["minimal"])
    reduced_len = max(1, len(minimal_text))
    original_len = max(1, len(original_text or ""))
    return {
        "status": "reduced",
        "core_claims": len(r["core_claims"]),
        "evidence": len(r["evidence"]),
        "compression_ratio": round(original_len / reduced_len, 3),
    }


def _bullets(items: List[str]) -> List[str]:
    return [f"- {it}" for it in items] if items else ["- _(none detected)_"]


def format_reduction(r: Dict) -> str:
    """Render the canonical Markdown reduction (stable section order)."""
    lines: List[str] = ["# Reduction", "", "## Core Claims"]
    lines += _bullets(r["core_claims"]); lines.append("")
    lines.append("## Supporting Evidence"); lines += _bullets(r["evidence"]); lines.append("")
    lines.append("## Minimal Form"); lines += _bullets(r["minimal"])
    return "\n".join(lines)
