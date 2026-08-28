"""
azimuth_envelope_impl.py — Phase 3 Unit 5 heuristics for the Envelope Layer.

Imported by ``azimuth_envelope`` — the public API, the schemas and the
invariants stay there. This module holds only the lexicons and the four
per-axis scorers, so the heuristic tables sit in one reviewable place.

★ THE SPEC IS THE DOCSTRING OF ``azimuth_envelope.capture_envelope``. It is
implemented as written, not redesigned. A heuristic that looks wrong is
reported, not replaced.

★★ INTENSITY: amplifiers BUMP, hedges REDUCE. Direction IS the signal.
This supersedes a retired working ruling of 2026-08-28 ("hedges and
intensifiers both count; direction is noise, frequency is signal"). Under
the governing spec, summing both into one unsigned integer destroys exactly
the quantity being measured — which is why ``phone/lib/langbridg.ts:193-199``
(41 regexes summed to one int) is a defect in that surface's local
approximation. Different surface; not touched here.

INVARIANTS — no network, no logging of raw_text, pure functions only.
"""
from __future__ import annotations

import re
import unicodedata

# ===========================================================================
# Lexicons — module-level tuples, never sets, so iteration order is fixed and
# a capture is byte-identical across processes.
# ===========================================================================
AMPLIFIERS = (
    "really", "so", "absolutely", "extremely", "completely", "utterly",
    "totally", "incredibly", "insanely",
)
HEDGES = (
    "kind of", "a bit", "maybe", "sort of", "somewhat", "slightly",
    "perhaps", "possibly", "a little", "i guess", "i suppose",
)

# ★ AUTHORED, NOT FOUND. The spec names "profanity" and "crisis vocabulary";
# no list for either exists anywhere in the repo. These two tuples are
# genuine authoring and are the part of this module most likely to need
# CT-1's eye. Deliberately SHORT and unambiguous — a long list invites false
# positives, and a false EXTREME is worse than a missed one because it is
# the top of the scale.
PROFANITY = (
    "fuck", "fucking", "shit", "bullshit", "damn", "bastard", "bitch",
    "crap", "asshole",
)
CRISIS = (
    "crisis", "emergency", "urgent", "catastrophe", "disaster",
    "breaking point", "falling apart", "out of control", "last chance",
    "can't cope", "cannot cope",
)

POSITIVE = (
    "good", "great", "glad", "happy", "grateful", "proud", "relieved",
    "excited", "calm", "hopeful", "better", "love", "thanks", "thank you",
)
NEGATIVE = (
    "bad", "awful", "terrible", "angry", "sad", "hurt", "afraid", "anxious",
    "worried", "tired", "frustrated", "hate", "worse", "wrong", "upset",
)

# ★ Negation inversion is in the spec ("not great" -> negative). Window is
# three tokens: "not very good" inverts, but a "not" a clause away does not
# reach across and flip an unrelated word.
NEGATORS = (
    "not", "no", "never", "isnt", "wasnt", "arent", "dont", "didnt",
    "cant", "wont", "cannot", "nothing", "hardly", "barely",
)
NEGATION_WINDOW = 3

OBLIGATION = (
    "have to", "has to", "had to", "must", "need to", "needs to",
    "required to", "no choice", "supposed to",
)
DEADLINE = (
    "deadline", "due", "by tomorrow", "by monday", "by friday",
    "end of day", "eod", "asap", "immediately", "right away",
    "today", "tonight", "this week", "overdue",
)
# Reuses the vocabulary primitives_extract already carries for this exact
# axis (its _PRESSURE tuple) rather than authoring a parallel list that
# could drift from it.
PRESSURE_MARKERS = (
    "pressure", "strain", "load", "stress", "chokepoint", "hotspot",
    "overload",
)

APOLOGIZE = (
    "i'm sorry", "im sorry", "i am sorry", "i apologize", "i apologise",
    "my apologies", "sorry about",
)
REQUEST = (
    "i need", "can you", "could you", "would you", "please", "i'd like",
    "i want you to", "will you",
)
IMPERATIVE_VERBS = (
    "stop", "start", "tell", "give", "send", "call", "come", "go", "let",
    "help", "make", "take", "look", "listen", "answer", "explain", "fix",
    "check", "keep", "leave",
)

# rough_intention is a plain ``str`` in the locked schema, not an enum, so
# these are the literal strings the spec's docstring names.
INTENTION_APOLOGIZE = "apologize"
INTENTION_REQUEST = "request"
INTENTION_VENT = "vent"
INTENTION_REFLECT = "reflect"

BEFORE_DATE_RE = re.compile(
    r"\bbefore\s+(?:the\s+)?"
    r"(?:\d|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|tomorrow|noon|midnight|next\s+week|the\s+end)",
    re.IGNORECASE,
)
FIRST_PERSON_PAST_RE = re.compile(
    r"\bI\s+(?:\w+ed|was|were|had|did|felt|went|said|thought|knew|saw|got)\b"
)
# Two or more consecutive all-caps words, or one of 3+ letters. "I" and "A"
# never qualify; an acronym like "EOD" does, which is acceptable — it is a
# shouted token either way.
CAPS_RUN_RE = re.compile(r"\b[A-Z]{3,}(?:\s+[A-Z]{2,})*\b")
SENTENCE_SPLIT_RE = re.compile(r"[.!?]+|\n+")
TOKEN_RE = re.compile(r"[a-z']+")


def normalize(text: str) -> str:
    """NFKC + lower-case, for lexicon matching. Never logged, never stored."""
    return unicodedata.normalize("NFKC", text).lower()


def count_terms(low: str, terms) -> int:
    """Total occurrences of every term. Word-bounded so "so" does not match
    inside "also" — a boundary bug here would silently flatten the axis."""
    total = 0
    for term in terms:
        total += len(re.findall(r"\b" + re.escape(term) + r"\b", low))
    return total


def exclamation_density(text: str) -> float:
    """Exclamation marks per sentence. Named by the spec as its own channel."""
    sentences = [s for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    if not sentences:
        return 0.0
    return text.count("!") / float(len(sentences))


def caps_runs(text: str) -> int:
    """All-caps phrases. Its own channel per the spec, and one neither
    LangBridg nor the retired ruling carried."""
    return len(CAPS_RUN_RE.findall(text))


# ===========================================================================
# Per-axis scorers. Each returns an integer score; the enum banding lives in
# azimuth_envelope so the thresholds and the lexicons are reviewable apart.
# ===========================================================================
def intensity_score(text: str) -> int:
    """Amplifiers, all-caps, exclamation density and profanity BUMP.
    Hedges REDUCE. The signed sum is the score — direction is the signal."""
    low = normalize(text)
    bump = (
        count_terms(low, AMPLIFIERS)
        + count_terms(low, PROFANITY) * 2      # profanity is a strong bump
        + caps_runs(text)
        + int(exclamation_density(text) >= 1.0)
        + int(exclamation_density(text) >= 2.0)   # second step for ">= 2/sentence"
    )
    reduce_ = count_terms(low, HEDGES)
    return bump - reduce_


def valence_score(text: str) -> tuple[int, int]:
    """(positive, negative) hit counts, with negation inversion inside a
    3-token window: "not great" scores negative, not positive."""
    low = normalize(text).replace("'", "")
    tokens = TOKEN_RE.findall(low)
    pos = neg = 0
    pos_set = {t.replace("'", "") for t in POSITIVE if " " not in t}
    neg_set = {t.replace("'", "") for t in NEGATIVE if " " not in t}
    for i, tok in enumerate(tokens):
        if tok not in pos_set and tok not in neg_set:
            continue
        window = tokens[max(0, i - NEGATION_WINDOW):i]
        negated = any(w in NEGATORS for w in window)
        if tok in pos_set:
            neg += 1 if negated else 0
            pos += 0 if negated else 1
        else:
            pos += 1 if negated else 0
            neg += 0 if negated else 1
    # multi-word entries are matched as phrases, never negated
    for phrase in (t for t in POSITIVE if " " in t):
        pos += low.count(phrase)
    for phrase in (t for t in NEGATIVE if " " in t):
        neg += low.count(phrase)
    return pos, neg


def pressure_score(text: str) -> int:
    """Obligation, deadline markers, "before <date>", and crisis vocabulary."""
    low = normalize(text)
    return (
        count_terms(low, OBLIGATION)
        + count_terms(low, DEADLINE)
        + count_terms(low, PRESSURE_MARKERS)
        + len(BEFORE_DATE_RE.findall(text))
        + count_terms(low, CRISIS) * 2          # crisis weighs double
    )


def intention_of(text: str) -> str:
    """Rough intention, in the spec's own precedence: an apology outranks a
    request, which outranks imperative-led instruction, which outranks a
    first-person-past vent. Everything else reflects."""
    low = normalize(text)
    if count_terms(low, APOLOGIZE) or any(p in low for p in APOLOGIZE):
        return INTENTION_APOLOGIZE
    if any(p in low for p in REQUEST):
        return INTENTION_REQUEST
    sentences = [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]
    imperative = 0
    for s in sentences:
        first = TOKEN_RE.findall(normalize(s))
        if first and first[0] in IMPERATIVE_VERBS:
            imperative += 1
    past = len(FIRST_PERSON_PAST_RE.findall(text))
    if imperative and imperative >= past:
        return INTENTION_REQUEST
    if past:
        return INTENTION_VENT
    return INTENTION_REFLECT
