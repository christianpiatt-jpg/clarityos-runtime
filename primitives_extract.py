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
        # #116 -- the caps travel WITH the counts. A count that equals its
        # cap is a floor, not a measurement ("30" on a long paste means
        # "at least 30"); the UI can only say so if it knows the cap, and
        # it must not hard-code numbers that live here.
        # hydronic carries NO cap on purpose: it counts distinct keyword
        # TYPES from four fixed tuples (8+8+6+7 = 29 in all), so the
        # per-list [:_CAP_HYDRO] slice never truncates and a hydronic count
        # is never a floor. Advertising 48 would be a cap that cannot occur.
        "caps": {
            "P1": _CAP_TERMS, "P2": _CAP_TERMS,
            "P3": _CAP_CLAUSES, "P4": _CAP_CLAUSES,
            "Ts": _CAP_TENSION, "Te": _CAP_TENSION, "M": _CAP_TENSION,
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


# ===========================================================================
# #135 -- seven grammar counters. The doctrine names seven ways a sentence
# smuggles judgment in as geometry; nothing measured them. These are
# regex + lexicon over what already ships (no parser -- spacy/nltk are
# absent from requirements.txt and stay absent). Counted per sentence via
# _sentences, summed. Pure functions; declared lexicons, each <= 30 entries.
#
# * "it seems / it appears" are ALSO hedges in app._HEDGES (app.py:6269-
# 6284, the T producer). Not duplicated here: G1 counts the STATIVE FRAME
# (a state asserted of a subject), T counts hedging per sentence -- two
# measures that happen to share surface tokens. app.py imports this module,
# so the twin cannot be imported from here either way.
# ===========================================================================
_G_KEYS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")

#: G1 -- stative verbs. The frame fires when the verb is followed by NO
#: determiner / noun-phrase start (K3's pattern): "feels unstable" fires,
#: "feels the load of 400 users" does not, "is 400 users" does not.
_G1_STATIVE = frozenset({
    "is", "are", "was", "were", "feel", "feels", "felt",
    "seem", "seems", "appear", "appears", "remain", "remains",
})
#: What a noun phrase starts with: determiners, quantifiers, object
#: pronouns, wh-words. A digit-initial token counts as one too (a measure).
_NP_START = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "my", "your", "his",
    "her", "its", "our", "their", "some", "any", "no", "every", "each",
    "all", "both", "it", "them", "him", "me", "us", "you",
    "what", "which", "who",
})
#: Adverbs allowed between the stative verb and an evaluative adjective
#: ("is just unacceptable") -- G5 looks through these.
_G_BRIDGE = frozenset({
    "very", "so", "just", "really", "quite", "simply", "totally", "clearly",
    "obviously", "completely", "utterly", "frankly", "honestly", "always",
    "never", "still", "now", "also",
})

#: G2 -- fused subjects: a PLURAL / collective agent making a decision in
#: one clause ("the team decided", "everyone wants").
_G2_PLURAL_AGENTS = (
    "we", "they", "everyone", "everybody", "people", "the team", "the group",
    "the board", "leadership", "management", "the family", "the company",
    "the community", "all of us", "both of us", "the committee",
    "the department", "the staff", "the crew", "the partners", "the members",
    "the founders", "the leaders", "the parents", "the kids", "the guys",
    "the others", "the rest of us", "the whole team", "the organization",
)
_G2_DECISION_VERBS = frozenset({
    "decided", "decides", "decide", "agreed", "agrees", "agree", "chose",
    "choose", "chooses", "wants", "want", "wanted", "refused", "refuse",
    "refuses", "insisted", "insist", "insists", "demanded", "demand",
    "demands", "expects", "expect", "expected", "believes", "believe",
    "believed", "thinks", "think", "thought",
})

#: G3 -- non-local agents: an ABSTRACTION acting ("the market demands",
#: "regulation requires"). Seeded from _TE_WORDS (external tensions).
_G3_ABSTRACT_AGENTS = (
    "the competition", "the competitor", "the market",
    "regulation", "the regulator", "the regulatory", "the external",
    "demand", "the customer", "the stakeholder", "the threat", "the deadline",
    "the supplier", "the sanction", "the rivalry", "the system", "the process",
    "the culture", "the institution", "the economy", "society",
    "the industry", "the algorithm", "the policy", "history", "the situation",
    "the world", "the numbers", "the data",
)
_G3_VERBS = frozenset({
    "demands", "demanded", "requires", "required", "forces", "forced",
    "dictates", "dictated", "decides", "decided", "punishes", "punished",
    "rewards", "rewarded", "wants", "wanted", "needs", "needed", "expects",
    "expected", "allows", "allowed", "refuses", "refused", "pushes",
    "pushed", "drives", "drove", "makes", "made",
})

#: G4 -- reflexive self-reference, the brief's pattern verbatim. NON-
#: reflexive coreference ("the team ... the team") needs a parser and is
#: out of scope: the flag G4_reflexive_only says so in the payload.
_G4_REFLEXIVE_RE = re.compile(r"\b\w+\s+\w*(itself|themselves|oneself)\b", re.IGNORECASE)

#: G5 -- objectless evaluation: a G1 frame whose complement is an
#: evaluative adjective ("that is unacceptable"). G5 is a subset of G1 by
#: construction.
_G5_EVALUATIVE = frozenset({
    "unacceptable", "wrong", "inappropriate", "unfair", "absurd", "fine",
    "ridiculous", "unreasonable", "impossible", "pointless",
    "unprofessional", "disrespectful", "toxic", "hopeless", "terrible",
    "awful", "bad", "good", "great", "perfect", "excellent", "insane",
    "crazy", "stupid", "lazy", "selfish", "rude", "outrageous", "pathetic",
    "unbelievable",
})

#: G6 -- overloaded nouns: words that carry a verdict as if they were a
#: thing. Pure lexicon count (singular or plural).
_G6_OVERLOADED = frozenset({
    "leadership", "culture", "accountability", "trauma", "trust",
    "alignment", "legitimacy", "identity", "values", "respect",
    "boundaries", "safety", "integrity", "authenticity", "empowerment",
    "transparency", "ownership", "engagement", "wellness", "narrative",
    "energy", "vibe", "toxicity", "gaslighting", "closure", "growth",
    "mindset", "resilience", "loyalty", "entitlement",
})

#: G7 -- operator intent: first person want/need/expect x how SOMETHING
#: should read/show/land/say/look ("I want this to land well"). The
#: frame is precision-leaning on purpose: an OBJECT and "to" must sit
#: between the modal and the verb, so "I need to read the report" and
#: "we should show up" (first person doing the verb) do not count.
_G7_INTENT_RE = re.compile(
    r"\b(?:I|we)\s+(?:want|wanted|need|needed|should|expect|expected)\s+"
    r"(?:this|it|that|them|these|those|(?:the|my|our|this|that)\s+\w+)\s+to\s+"
    r"(?:read|show|land|say|look)\b",
    re.IGNORECASE,
)

_G_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-]*")


def _g_tokens(sentence: str) -> List[str]:
    return [t.lower() for t in _G_TOKEN_RE.findall(sentence)]


def _g_is_np_start(tok: str) -> bool:
    return tok in _NP_START or tok[:1].isdigit()


def _g_is_verb(tok: str) -> bool:
    """G3's verb test: the G3 list, or an action verb in base / -s / -ed /
    -ing form. Lossy, like every detector in this module."""
    if tok in _G3_VERBS or tok in _ACTION_VERBS:
        return True
    for suffix in ("ing", "ed", "es", "s"):
        if tok.endswith(suffix) and len(tok) > len(suffix) + 2:
            base = tok[: -len(suffix)]
            if base in _ACTION_VERBS or base + "e" in _ACTION_VERBS:
                return True
    return False


def _g1_g5(sentence: str) -> tuple:
    toks = _g_tokens(sentence)
    g1 = g5 = 0
    for i, tok in enumerate(toks):
        if tok not in _G1_STATIVE:
            continue
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if nxt is None:
            continue                       # "It is." -- no complement, no state asserted
        if _g_is_np_start(nxt):
            continue                       # "feels the load" -- a measure, not a state
        g1 += 1
        # G5 looks through one bridge adverb: "is just unacceptable".
        window = [t for t in toks[i + 1:i + 3] if t not in _G_BRIDGE][:1]
        if window and window[0] in _G5_EVALUATIVE:
            g5 += 1
    return g1, g5


def _g2(sentence: str) -> int:
    low = " " + " ".join(_g_tokens(sentence)) + " "
    if not any(" %s " % agent in low for agent in _G2_PLURAL_AGENTS):
        return 0
    return 1 if any(" %s " % v in low for v in _G2_DECISION_VERBS) else 0


def _g3(sentence: str) -> int:
    toks = _g_tokens(sentence)
    joined = " " + " ".join(toks) + " "
    hits = 0
    for agent in _G3_ABSTRACT_AGENTS:
        needle = " %s " % agent
        start = 0
        while True:
            at = joined.find(needle, start)
            if at < 0:
                break
            # the token index right after the agent phrase
            after = joined[:at + len(needle)].split()
            idx = len(after)
            follow = [t for t in toks[idx:idx + 2] if t not in _G_BRIDGE][:1]
            if follow and _g_is_verb(follow[0]):
                hits += 1
            start = at + 1
    return hits


def _g6(sentence: str) -> int:
    n = 0
    for tok in _g_tokens(sentence):
        if tok in _G6_OVERLOADED or (tok.endswith("s") and tok[:-1] in _G6_OVERLOADED):
            n += 1
    return n


def grammar_counts(text) -> Dict:
    """The seven grammar counters over ``text``, summed per sentence.

    Returns ``{G1..G7: int, G4_reflexive_only: True, sentences: int}``.
    Non-string or empty input returns all zeros with ``sentences`` 0 --
    a TRUE COUNT (no sentence, nothing counted), not a sentinel.
    """
    out = {k: 0 for k in _G_KEYS}
    out["G4_reflexive_only"] = True
    out["sentences"] = 0
    if not isinstance(text, str) or not text.strip():
        return out
    sents = _sentences(text)
    out["sentences"] = len(sents)
    for sent in sents:
        g1, g5 = _g1_g5(sent)
        out["G1"] += g1
        out["G5"] += g5
        out["G2"] += _g2(sent)
        out["G3"] += _g3(sent)
        out["G4"] += len(_G4_REFLEXIVE_RE.findall(sent))
        out["G6"] += _g6(sent)
        out["G7"] += len(_G7_INTENT_RE.findall(sent))
    return out
