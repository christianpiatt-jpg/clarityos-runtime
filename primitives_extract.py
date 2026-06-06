"""
primitives_extract.py — deterministic primitive extraction for #primitives (A23).

Pure, side-effect-free decomposition of text into the P-series primitives:

    P1 Entities · P2 Actions · P3 Relations · P4 States
    Tensions: Ts (structural) · Te (external) · M (motive)
    Hydronic: flows · blockages · gradients · pressure points

HONESTY NOTE: this is a deterministic HEURISTIC scaffold, not semantic NLP.
The codebase carries no NLP dependency (cite_mode + structure_format are both
pure regex/keyword heuristics, and the runtime forbids extra deps), so
"primitive extraction" here is regex + curated keyword sets + capitalisation
cues. It is precision-leaning and lossy — false positives/negatives are
expected, exactly as cite_mode's detectors are "a gate, not a correctness
check." A semantically faithful decomposition would need a model-backed pass
(see A23 notes); that is intentionally out of scope for this deterministic
handler.

Determinism: every produced list is ordered by appearance in the text, or by
a FIXED keyword-tuple order — never by set iteration (string-set order is not
stable across processes).
"""
from __future__ import annotations

import re
from typing import Dict, List

# Per-category output caps (bound the size of the decomposition).
_CAP_TERMS = 30
_CAP_CLAUSES = 20
_CAP_TENSION = 12
_CAP_HYDRO = 12
_CLAUSE_MAXLEN = 200

# Single capitalised words that are almost never entities (sentence starters,
# pronouns, days/months). Multi-word Capitalised runs + ACRONYMS bypass this.
_ENTITY_STOP = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "it", "we", "you",
    "they", "he", "she", "i", "and", "but", "or", "if", "then", "so", "as",
    "in", "on", "at", "to", "for", "of", "by", "with", "from", "there",
    "here", "when", "where", "while", "however", "therefore", "thus", "also",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
})

# Curated action-verb lexicon (base forms). Augmented by -ing/-ed morphology.
_ACTION_VERBS = frozenset({
    "build", "create", "make", "run", "use", "move", "flow", "cause", "drive",
    "require", "enable", "prevent", "block", "deploy", "design", "plan",
    "manage", "control", "send", "receive", "process", "analyse", "analyze",
    "compute", "measure", "increase", "decrease", "reduce", "expand", "shift",
    "produce", "deliver", "support", "connect", "integrate", "remove", "add",
    "update", "transform", "extract", "detect", "route", "validate", "trigger",
    "start", "stop", "open", "close", "grow", "fail", "succeed", "launch",
})
# -ing/-ed words that are not actions (avoid obvious false positives).
_VERBISH_STOP = frozenset({
    "during", "nothing", "something", "anything", "everything", "morning",
    "evening", "ceiling", "feeling", "meeting", "setting", "wedding",
    "embedded", "needed", "indeed", "speed", "seed", "feed", "deed",
    "hundred", "sacred", "naked", "wicked", "limited", "related",
})

_RELATION_MARKERS = (
    "because", "therefore", "thus", "hence", "due to", "leads to",
    "leading to", "results in", "result in", "caused by", "causes", "caused",
    "depends on", "depend on", "requires", "required", "constrains",
    "enables", "prevents", "so that", "in order to", "as a result",
    "if ", "then ",
)
_STATE_WORDS = frozenset({
    "active", "inactive", "blocked", "unblocked", "pending", "complete",
    "completed", "incomplete", "stable", "unstable", "open", "closed",
    "ready", "failing", "failed", "running", "idle", "available",
    "unavailable", "degraded", "healthy", "broken", "operational",
    "offline", "online", "locked", "frozen",
})

_TS_WORDS = frozenset({  # structural tensions
    "constraint", "constraints", "contradiction", "tension", "tensions",
    "conflict", "trade-off", "tradeoff", "limitation", "bottleneck",
    "friction", "imbalance", "rigidity", "deadlock", "structural",
})
_TE_WORDS = frozenset({  # external tensions
    "competition", "competitor", "market", "regulation", "regulatory",
    "external", "demand", "customer", "stakeholder", "threat", "deadline",
    "supplier", "sanction", "rivalry",
})
_M_WORDS = frozenset({  # motive forces
    "goal", "goals", "objective", "objectives", "motivation", "motive",
    "incentive", "purpose", "aim", "intent", "mission", "ambition",
    "aspiration", "driver",
})

# Hydronic keyword tuples — FIXED order for deterministic output.
_FLOWS = ("flow", "stream", "current", "throughput", "pipeline", "channel",
          "circulation", "conduit")
_BLOCKAGES = ("blockage", "barrier", "bottleneck", "obstruction", "congestion",
              "clog", "dam", "block")
_GRADIENTS = ("gradient", "slope", "differential", "incline", "decline",
              "ramp")
_PRESSURE = ("pressure", "strain", "load", "stress", "chokepoint", "hotspot",
             "overload")

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_ENTITY_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*)\b")


def _empty() -> Dict:
    return {
        "P1": [], "P2": [], "P3": [], "P4": [],
        "Ts": [], "Te": [], "M": [],
        "hydronic": {"flows": [], "blockages": [], "gradients": [],
                     "pressure_points": []},
    }


def _sentences(text: str) -> List[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _trim(s: str) -> str:
    s = s.strip()
    return s if len(s) <= _CLAUSE_MAXLEN else s[:_CLAUSE_MAXLEN].rstrip() + "…"


def _dedup(seq: List[str]) -> List[str]:
    seen = set()
    out = []
    for x in seq:
        k = x.lower()
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _entities(text: str) -> List[str]:
    out: List[str] = []
    for m in _ENTITY_RE.finditer(text):
        phrase = m.group(1).strip()
        words = phrase.split()
        is_acronym = phrase.isupper() and len(phrase) >= 2
        if len(words) == 1 and not is_acronym and phrase.lower() in _ENTITY_STOP:
            continue
        out.append(phrase)
    return _dedup(out)[:_CAP_TERMS]


def _actions(text: str) -> List[str]:
    out: List[str] = []
    for w in _WORD_RE.findall(text):
        lw = w.lower()
        if len(lw) < 3 or lw in _VERBISH_STOP:
            continue
        is_verb = (
            lw in _ACTION_VERBS
            or (lw.endswith("ing") and len(lw) > 4)
            or (lw.endswith("ed") and len(lw) > 4)
        )
        if is_verb:
            out.append(lw)
    return _dedup(out)[:_CAP_TERMS]


def _clauses_matching(text: str, *, markers=None, words=None) -> List[str]:
    out: List[str] = []
    for s in _sentences(text):
        ls = s.lower()
        hit = False
        if markers is not None:
            hit = any(mk in ls for mk in markers)
        if not hit and words is not None:
            hit = any(re.search(rf"\b{re.escape(w)}\b", ls) for w in words)
        if hit:
            out.append(_trim(s))
    return _dedup(out)


def _hydronic_terms(text: str, keywords) -> List[str]:
    low = text.lower()
    out: List[str] = []
    for kw in keywords:  # fixed tuple order → deterministic
        if re.search(rf"\b{re.escape(kw)}(?:s|es)?\b", low):
            out.append(kw)
    return out[:_CAP_HYDRO]


def extract_primitives(text: str) -> Dict:
    """Decompose ``text`` into the P-series primitive structure (see module
    docstring). Returns the canonical dict; non-str input → empty structure."""
    if not isinstance(text, str) or not text.strip():
        return _empty()
    return {
        "P1": _entities(text),
        "P2": _actions(text),
        "P3": _clauses_matching(text, markers=_RELATION_MARKERS)[:_CAP_CLAUSES],
        "P4": _clauses_matching(text, words=_STATE_WORDS)[:_CAP_CLAUSES],
        "Ts": _clauses_matching(text, words=_TS_WORDS)[:_CAP_TENSION],
        "Te": _clauses_matching(text, words=_TE_WORDS)[:_CAP_TENSION],
        "M": _clauses_matching(text, words=_M_WORDS)[:_CAP_TENSION],
        "hydronic": {
            "flows": _hydronic_terms(text, _FLOWS),
            "blockages": _hydronic_terms(text, _BLOCKAGES),
            "gradients": _hydronic_terms(text, _GRADIENTS),
            "pressure_points": _hydronic_terms(text, _PRESSURE),
        },
    }


def build_metadata(prim: Dict) -> Dict:
    h = prim["hydronic"]
    hydronic_count = (
        len(h["flows"]) + len(h["blockages"])
        + len(h["gradients"]) + len(h["pressure_points"])
    )
    return {
        "status": "extracted",
        "counts": {
            "P1": len(prim["P1"]), "P2": len(prim["P2"]),
            "P3": len(prim["P3"]), "P4": len(prim["P4"]),
            "Ts": len(prim["Ts"]), "Te": len(prim["Te"]), "M": len(prim["M"]),
            "hydronic": hydronic_count,
        },
    }


def _bullets(items: List[str]) -> List[str]:
    return [f"- {it}" for it in items] if items else ["- _(none detected)_"]


def _kv(label: str, items: List[str]) -> str:
    return f"- {label}: {'; '.join(items) if items else '_(none)_'}"


def format_primitives(prim: Dict) -> str:
    """Render the canonical Markdown decomposition (stable section order)."""
    h = prim["hydronic"]
    lines: List[str] = ["# Primitives", ""]
    lines.append("## P1 — Entities"); lines += _bullets(prim["P1"]); lines.append("")
    lines.append("## P2 — Actions"); lines += _bullets(prim["P2"]); lines.append("")
    lines.append("## P3 — Relations"); lines += _bullets(prim["P3"]); lines.append("")
    lines.append("## P4 — States"); lines += _bullets(prim["P4"]); lines.append("")
    lines.append("## Tensions")
    lines.append(_kv("Ts", prim["Ts"]))
    lines.append(_kv("Te", prim["Te"]))
    lines.append(_kv("M", prim["M"]))
    lines.append("")
    lines.append("## Hydronic")
    lines.append(_kv("Flows", h["flows"]))
    lines.append(_kv("Blockages", h["blockages"]))
    lines.append(_kv("Gradients", h["gradients"]))
    lines.append(_kv("Pressure Points", h["pressure_points"]))
    return "\n".join(lines)
