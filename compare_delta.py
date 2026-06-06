"""
compare_delta.py — deterministic contrastive delta analysis for #compare (A25).

Pure, side-effect-free comparison of two targets found in the text — the
"difference engine." It produces:

    targets        — the two comparison subjects (explicit markers, else the
                     top-2 detected entities)
    similarities   — sentences carrying a similarity marker (both/same/shared…)
    differences    — contrast clauses bucketed to whichever single target they
                     mention ({A}-side vs {B}-side)
    attributes     — rows from explicit comparative sentences ("X is faster
                     than Y" -> attribute=faster, higher=X, lower=Y)

HONESTY NOTE: #compare is the WEAKEST deterministic directive. Real
attribute alignment + directional deltas need semantic understanding; with no
NLP dependency this is regex + keyword heuristics. It works when the text is
explicitly comparative (vs / between / "both" / "whereas" / "X is -er than Y")
and is sparse-to-empty otherwise. The "{A} > {B}" headings denote SIDE
attribution (which target a contrast clause is about), not a proven ordering,
except in the attribute table where "than" comparatives give a real direction.
This is the prime candidate for a model-backed pass (see A25 notes).

Determinism: scans are in text order; membership uses fixed sets; nothing is
ordered by set iteration.
"""
from __future__ import annotations

import re
from typing import Dict, List

_CAP = 15
_CLAUSE_MAXLEN = 200

_SIMILARITY = (
    "both", "similarly", "alike", "same", "shared", "in common", "as well as",
    "likewise", "equally", "share", "common",
)
_CONTRAST = (
    "whereas", "unlike", "while", "however", "but", "on the other hand",
    "in contrast", "differs", "different", "rather than", "instead", "than",
)
# Capitalised words that are not comparison targets (starters + compare words).
_TARGET_STOP = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "it", "they", "we",
    "you", "and", "or", "but", "both", "each", "either", "neither", "compared",
    "versus", "unlike", "while", "however", "although", "whereas", "in", "on",
    "at", "to", "for", "of", "by", "with", "from", "there", "here", "when",
    "where", "if", "then", "so", "as", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october",
    "november", "december",
})

_VS_RE = re.compile(
    r"\b([A-Za-z][\w.\-]*)\s+(?:vs\.?|versus)\s+(?:the |a |an )?([A-Za-z][\w.\-]*)",
    re.I,
)
_COMPARED_RE = re.compile(
    r"\b([A-Za-z][\w.\-]*)\s+compared\s+(?:to|with)\s+(?:the |a |an )?([A-Za-z][\w.\-]*)",
    re.I,
)
_BETWEEN_RE = re.compile(
    r"\bbetween\s+(?:the |a |an )?([A-Za-z][\w.\-]*)\s+and\s+(?:the |a |an )?([A-Za-z][\w.\-]*)",
    re.I,
)
_ENTITY_RE = re.compile(r"\b([A-Z][A-Za-z0-9]*(?:\s+[A-Z][A-Za-z0-9]*)*)\b")
_COMP_RE = re.compile(
    r"\b([A-Za-z][\w.\-]*)\s+(?:is|are|was|were)\s+(more |less )?"
    r"([A-Za-z][\w\-]+?)\s+than\s+(?:the |a |an )?([A-Za-z][\w.\-]*)",
    re.I,
)
_CLAUSE_SPLIT_RE = re.compile(
    r"\b(?:whereas|but|while|however|unlike|in contrast|on the other hand|"
    r"rather than|instead)\b|[,;]",
    re.I,
)


def _sentences(text: str) -> List[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]


def _trim(s: str) -> str:
    s = s.strip().rstrip(".,;")
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


def _clean(tok: str) -> str:
    """Strip surrounding punctuation from a captured token (so a sentence-final
    'Java.' aligns with the 'Java' target)."""
    return tok.strip().strip(".,;:!?'\"").strip()


def _local_entities(text: str) -> List[str]:
    out = []
    for m in _ENTITY_RE.finditer(text):
        words = m.group(1).strip().split()
        # Drop leading starter words so "Both Apple" -> "Apple".
        while words and words[0].lower() in _TARGET_STOP:
            words = words[1:]
        if not words:
            continue
        phrase = " ".join(words)
        is_acronym = phrase.isupper() and len(phrase) >= 2
        if len(words) == 1 and not is_acronym and phrase.lower() in _TARGET_STOP:
            continue
        out.append(phrase)
    return _dedup(out)


def _targets(text: str) -> List[str]:
    for rx in (_VS_RE, _COMPARED_RE, _BETWEEN_RE):
        m = rx.search(text)
        if m:
            return _dedup([_clean(m.group(1)), _clean(m.group(2))])
    return _local_entities(text)[:2]


def _similarities(text: str) -> List[str]:
    return _dedup([_trim(s) for s in _sentences(text)
                   if _has_any(s, _SIMILARITY)])[:_CAP]


def _differences(text: str, targets: List[str]) -> Dict[str, List[str]]:
    if len(targets) < 2:
        return {}
    a, b = targets[0], targets[1]
    da: List[str] = []
    db: List[str] = []
    al, bl = a.lower(), b.lower()
    for s in _sentences(text):
        if not _has_any(s, _CONTRAST):
            continue
        for cl in (c.strip() for c in _CLAUSE_SPLIT_RE.split(s) if c.strip()):
            cll = cl.lower()
            ina = re.search(rf"\b{re.escape(al)}\b", cll) is not None
            inb = re.search(rf"\b{re.escape(bl)}\b", cll) is not None
            if ina and not inb:
                da.append(_trim(cl))
            elif inb and not ina:
                db.append(_trim(cl))
    return {a: _dedup(da)[:_CAP], b: _dedup(db)[:_CAP]}


def _attributes(text: str, targets: List[str]) -> List[Dict[str, str]]:
    if len(targets) < 2:
        return []
    tset = {t.lower() for t in targets}
    rows: List[Dict[str, str]] = []
    seen = set()
    for m in _COMP_RE.finditer(text):
        left, ml, attr, right = (
            _clean(m.group(1)), (m.group(2) or "").strip().lower(),
            m.group(3), _clean(m.group(4)),
        )
        if left.lower() not in tset or right.lower() not in tset:
            continue
        higher, lower = (right, left) if ml == "less" else (left, right)
        key = (attr.lower(), higher.lower(), lower.lower())
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": attr.lower(), "higher": higher, "lower": lower})
    return rows[:_CAP]


def compare(text: str) -> Dict:
    """Contrastive delta analysis of ``text``. Non-str/empty → empty result."""
    if not isinstance(text, str) or not text.strip():
        return {"targets": [], "similarities": [], "differences": {}, "attributes": []}
    targets = _targets(text)
    return {
        "targets": targets,
        "similarities": _similarities(text),
        "differences": _differences(text, targets),
        "attributes": _attributes(text, targets),
    }


def build_metadata(c: Dict) -> Dict:
    diff_count = sum(len(v) for v in c["differences"].values())
    return {
        "status": "compared",
        "targets": list(c["targets"]),
        "similarity_count": len(c["similarities"]),
        "difference_count": diff_count,
    }


def _bullets(items: List[str]) -> List[str]:
    return [f"- {it}" for it in items] if items else ["- _(none detected)_"]


def format_comparison(c: Dict) -> str:
    """Render the canonical Markdown comparison (stable section order)."""
    targets = c["targets"]
    lines: List[str] = ["# Comparison", "", "## Targets"]
    lines += _bullets(targets)
    lines.append("")
    lines.append("## Similarities")
    lines += _bullets(c["similarities"])
    lines.append("")
    lines.append("## Differences")
    if len(targets) >= 2:
        a, b = targets[0], targets[1]
        diffs = c["differences"]
        lines.append(f"### {a} > {b}")
        lines += _bullets(diffs.get(a, []))
        lines.append(f"### {b} > {a}")
        lines += _bullets(diffs.get(b, []))
    else:
        lines.append("_(need ≥2 targets)_")
    lines.append("")
    lines.append("## Attribute Table")
    a = targets[0] if len(targets) > 0 else "A"
    b = targets[1] if len(targets) > 1 else "B"
    lines.append(f"| Attribute | {a} | {b} | Delta |")
    lines.append("|---|---|---|---|")
    rows = c["attributes"]
    if not rows:
        lines.append("| _(none)_ |  |  |  |")
    else:
        for r in rows:
            acell = "higher" if r["higher"].lower() == a.lower() else (
                "lower" if r["lower"].lower() == a.lower() else "—")
            bcell = "higher" if r["higher"].lower() == b.lower() else (
                "lower" if r["lower"].lower() == b.lower() else "—")
            lines.append(f"| {r['name']} | {acell} | {bcell} | {r['higher']} > {r['lower']} |")
    return "\n".join(lines)
