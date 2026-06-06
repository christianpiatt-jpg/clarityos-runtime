"""
operator_brief.py — deterministic operator-grade synthesis for #operator (A27).

Pure, side-effect-free synthesis of a decision-ready, narrative-free operator
brief. Drops filler, then routes each remaining sentence to exactly ONE bucket
by priority (moves > risks > constraints > implications > signals), so the
sections are clean and non-redundant:

    signals        — core assertions (the default bucket)
    implications   — "therefore / thus / this means / as a result …"
    risks          — "risk / threat / failure / fragile / volatile …"
    constraints    — "limit / budget / deadline / required / depends on …"
    moves          — recommendations ("should / must / prioritize …") or an
                     imperative opener ("Reduce …", "Ensure …")

HONESTY NOTE (same posture as the other semantic handlers): heuristic, not
synthesis — no NLP dependency, so routing is keyword/structure based. It strips
scaffolding and buckets by signal; it does not "understand."

Determinism: sentences processed in text order; boolean membership over fixed
tuples; no set-iteration in the output path.
"""
from __future__ import annotations

import re
from typing import Dict, List

_CAP = 25
_CLAUSE_MAXLEN = 240

_FILLER_STARTS = (
    "let me", "let's", "let us", "here is", "here's", "i hope", "to begin",
    "to start", "as an ai", "in this response", "welcome", "to summarize",
    "in summary",
)
_FILLER_CONTAINS = ("hope this helps", "let me know if", "feel free to")

_IMPLICATION = (
    "therefore", "thus", "hence", "consequently", "as a result", "this means",
    "which means", "implies", "imply", "leads to", "leading to", "results in",
)
_RISK = (
    "risk", "threat", "danger", "vulnerability", "vulnerable", "failure",
    "fail", "fails", "downside", "concern", "exposure", "liability", "hazard",
    "fragile", "volatile", "uncertain", "jeopardy", "breach", "outage",
)
_CONSTRAINT = (
    "constraint", "limit", "limited", "cannot", "can't", "required",
    "requirement", "depends on", "only if", "budget", "deadline", "regulation",
    "restricted", "bounded", "fixed", "at most", "no more than", "capacity",
    "quota",
)
_MOVE_MARKERS = (
    "should", "recommend", "recommended", "need to", "needs to", "must",
    "consider", "prioritize", "prioritise", "ensure", "implement", "avoid",
    "adopt", "mitigate", "focus on", "next step", "take action", "escalate",
)
_MOVE_VERBS = frozenset({
    "deploy", "reduce", "focus", "ensure", "avoid", "prioritize", "prioritise",
    "implement", "adopt", "mitigate", "increase", "decrease", "build", "cut",
    "raise", "lower", "monitor", "review", "escalate", "pause", "accelerate",
    "consolidate", "invest", "hire", "launch", "stop", "start", "shift",
    "allocate", "secure", "optimize", "optimise",
})

_BUCKETS = ("signals", "implications", "risks", "constraints", "moves")


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


def _has_any(s: str, markers) -> bool:
    ls = s.lower()
    return any(re.search(rf"\b{re.escape(m)}\b", ls) for m in markers)


def _is_filler(s: str) -> bool:
    ls = s.lower().strip()
    if len(s.split()) < 3:
        return True
    if any(ls.startswith(p) for p in _FILLER_STARTS):
        return True
    return any(p in ls for p in _FILLER_CONTAINS)


def _first_word(s: str) -> str:
    m = re.match(r"\s*([A-Za-z']+)", s)
    return m.group(1).lower() if m else ""


def _classify(s: str) -> str:
    # Priority: most actionable first; "signals" is the default bucket.
    if _has_any(s, _MOVE_MARKERS) or _first_word(s) in _MOVE_VERBS:
        return "moves"
    if _has_any(s, _RISK):
        return "risks"
    if _has_any(s, _CONSTRAINT):
        return "constraints"
    if _has_any(s, _IMPLICATION):
        return "implications"
    return "signals"


def synthesize_operator_brief(text: str) -> Dict:
    """Synthesise an operator brief from ``text``. Non-str/empty → empty brief."""
    brief: Dict[str, List[str]] = {k: [] for k in _BUCKETS}
    if not isinstance(text, str) or not text.strip():
        return brief
    for s in _sentences(text):
        if _is_filler(s):
            continue
        brief[_classify(s)].append(_trim(s))
    for k in _BUCKETS:
        brief[k] = _dedup(brief[k])[:_CAP]
    return brief


def build_metadata(b: Dict) -> Dict:
    return {
        "status": "operator_synthesized",
        "signals": len(b["signals"]),
        "implications": len(b["implications"]),
        "risks": len(b["risks"]),
        "constraints": len(b["constraints"]),   # A27: card listed 4 counts; the
        "moves": len(b["moves"]),               # brief has 5 sections, so all 5
    }                                           # are counted for consistency.


def _bullets(items: List[str]) -> List[str]:
    return [f"- {it}" for it in items] if items else ["- _(none detected)_"]


def format_operator_brief(b: Dict) -> str:
    """Render the canonical Markdown operator brief (stable section order)."""
    lines: List[str] = ["# Operator Brief", "", "## Core Signals"]
    lines += _bullets(b["signals"]); lines.append("")
    lines.append("## Implications"); lines += _bullets(b["implications"]); lines.append("")
    lines.append("## Risks"); lines += _bullets(b["risks"]); lines.append("")
    lines.append("## Constraints"); lines += _bullets(b["constraints"]); lines.append("")
    lines.append("## Recommended Moves"); lines += _bullets(b["moves"])
    return "\n".join(lines)
