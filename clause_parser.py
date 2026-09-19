"""
clause_parser.py — #366 A1. The out-loop transformer's first station.

WHAT THIS IS
------------
A deterministic, on-machine clause parser. Member text goes in; attributed
verb–object rows come out, BEFORE any LLM sees anything. No vendor, no
network at inference. The library is spaCy (MIT) with the small English
model ``en_core_web_sm`` (MIT); both are exact-pinned (spaCy in
requirements.txt, the model wheel by URL in the Dockerfile).

Per clause the row is the amended A1 tuple, exactly::

    (agent_span, verb_lemma, object_span, negation, modality,
     contrast_span, tense, sentence_idx)

    modality ∈ {event, counterfactual, conditional, obligation, expected,
                reported}
    tense    ∈ {past, present, future, undefined}

plus the fields the ledger (A2) needs to seat the spans without re-parsing:
dependency labels, name keys, entity labels, first-person and
nominalization flags, the reporter's key on a reported clause, and the
numbers found in the object span (the load, never a name).

THE DERIVATION RULE, READ OFF THE TREES (not off the answer key)
----------------------------------------------------------------
    agent    the ``nsubj`` / ``csubj`` dependent of the clause verb; for a
             passive (``nsubjpass``) the agent is the ``agent``→``pobj``
             phrase when present, else ``undefined``, and the grammatical
             subject moves to the object slot. A verb with no subject of its
             own inherits its controller's subject through ``xcomp`` /
             ``conj`` / ``acomp`` (want → go; could adopt, reject, modify;
             will be able to impose).
    object   ``dobj``/``obj`` → a ``prep``→``pobj`` phrase → ``attr``/
             ``acomp`` (copula) → an ``xcomp`` verb lemma → ``undefined``.
    negation any ``neg`` dependent of the verb or of one of its auxiliaries,
             or a determiner *no* on the object. Never inferred from tone.
    modality R-366-E (CT-1 2026-09-19): ``would`` → counterfactual, and →
             conditional when an *if*-mark governs the clause or the clause
             it governs · ``could / might / may`` → conditional (``can``
             joins them: a possibility modal, named in the return as an
             extension, not a ruling) · ``should / must / need to / have
             to`` → obligation · ``will / expected to / likely`` → expected.
             A clause governed by a speech verb (say · find · observe · …)
             carries the reporter's key in ``prov``; when no modal marker is
             present it reads ``reported``. ``event`` ONLY when none of the
             above is present.
    contrast the expectation markers, carried verbatim and never dropped
             (specimen #380): the packet's eight (unlikely · suddenly ·
             reluctantly · only · still · though · but · even) plus the
             specimens' (however · rather than · than · compared with · if ·
             whether · yet · although · despite · instead · contrary).
             Each marker is assigned to the clause whose verb is its nearest
             clausal ancestor; a marker no clause claims rides the root row.
    tense    the finite verb's ``Tense`` morph; a non-finite verb takes its
             tensed auxiliary's; ``will``/``shall`` → future; else
             ``undefined`` (never guessed).

THE ENUMERATOR (R-374-A closes here -- in the tree, gated; not in the domain lexicon)
------------------------------------------------------------------------------------
``en_core_web_sm`` reads "Article I was informed …" with *I* as
``nsubjpass`` (measured 2026-09-19 — the tree does NOT do the work alone).
So first person is claimed only when the pronoun is (a) not inside a named
entity, (b) not inside a citation span (``Article I`` · ``Title I`` ·
``29 CFR 1614.109`` · ``Rule 56`` · ``527 U.S. at 219``), and (c) not a
capital *I* immediately preceded by an ENUMERATOR HEAD: a capitalized noun
with no determiner of its own whose lemma is in ``_ENUMERATOR_CARRIERS``
(Article · Count · Table · Title · Schedule · Part · Exhibit · Section …).
Condition (c) IS a lexicon -- a short one of enumerator nouns, named as such
-- with a structural gate that keeps "At this stage I want" and "For the
most part I agreed" as the author. A pronoun that fails any one of the
three is a reference, never the author's seat.

WHAT IS NOT DONE HERE
---------------------
No coreference (*it* / *they* stay unresolved pronouns and the ledger says
so), no seat ids (A2), no serialization to any model (A4). Nothing in this
module reads a store or logs member text.
"""
from __future__ import annotations

import os
import re
import threading
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable, Optional

PARSER_VERSION: str = "clause.parser.v1 spacy-3.8.14 en_core_web_sm-3.8.0"
MODEL_NAME: str = "en_core_web_sm"

MODALITIES: tuple = ("event", "counterfactual", "conditional", "obligation", "expected", "reported")
TENSES: tuple = ("past", "present", "future", "undefined")
UNDEFINED: str = "undefined"

# --- R-366-E -----------------------------------------------------------------
_MODAL_COUNTERFACTUAL: frozenset = frozenset({"would"})
# ``can`` is NOT in R-366-E's list; it is the present form of ``could`` and a
# possibility modal. Carried as conditional and NAMED in the Part B return
# (an extension the pilot can strike with one line).
_MODAL_CONDITIONAL: frozenset = frozenset({"could", "might", "may", "can"})
# ``shall`` is NOT in R-366-E's list either; it is the obligation modal of
# legal drafting ("the agency shall respond") and is carried as obligation,
# NAMED in the Part B return beside ``can``. (``ought`` never parses as an
# auxiliary in this model and is not listed: a dead entry is a false claim.)
_MODAL_OBLIGATION: frozenset = frozenset({"should", "must", "shall"})
_MODAL_EXPECTED: frozenset = frozenset({"will"})
_OBLIGATION_VERBS: frozenset = frozenset({"need", "have"})      # need to / have to + xcomp
_EXPECTED_LEMMAS: frozenset = frozenset({"expect"})               # expected to + xcomp
_EXPECTED_ADVERBS: frozenset = frozenset({"likely"})
#: the marks that make a clause conditional. ``whether`` is NOT one: it
#: introduces an interrogative complement, and it already rides as a contrast
#: marker (refuter, 2026-09-19).
_IF_MARKS: frozenset = frozenset({"if", "unless", "provided"})
_SPEECH_VERBS: frozenset = frozenset({
    "say", "find", "report", "observe", "add", "note", "state", "argue",
    "claim", "tell", "write", "announce", "conclude", "hold", "explain",
    "recognize", "recognise", "acknowledge", "suggest", "warn", "estimate",
})

# --- contrast markers ----------------------------------------------------------
#: the packet's eight, verbatim
CONTRAST_MARKERS_PACKET: tuple = (
    "unlikely", "suddenly", "reluctantly", "only", "still", "though", "but", "even",
)
#: the specimens' additions (#379 / #380 / FT rows)
CONTRAST_MARKERS_SPECIMEN: tuple = (
    "however", "rather than", "than", "compared with", "if", "whether", "yet",
    "although", "despite", "instead", "contrary", "nevertheless",
)
CONTRAST_MARKERS: tuple = CONTRAST_MARKERS_PACKET + CONTRAST_MARKERS_SPECIMEN
_MULTIWORD_MARKERS: tuple = tuple(m for m in CONTRAST_MARKERS if " " in m)
_SINGLE_MARKERS: frozenset = frozenset(m for m in CONTRAST_MARKERS if " " not in m)

# --- first person + the enumerator guard --------------------------------------
_FIRST_PERSON: frozenset = frozenset({
    "i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves",
})
_THIRD_PRONOUNS: frozenset = frozenset({
    "it", "its", "they", "them", "their", "theirs", "he", "him", "his", "she",
    "her", "hers", "you", "your", "yours", "this", "that", "these", "those",
    "who", "whom", "which", "what", "whatever", "one", "there", "here",
    "everyone", "everything", "something", "anything", "nothing", "someone",
    "anyone", "none", "both", "each", "all", "some", "many", "most", "several",
    "few", "other", "others", "another",
})
#: enumerator HEADS -- a short lexicon, named as one: the nouns a Roman "I"
#: enumerates (Article I · Count I · Table I). The structural gate that makes
#: it safe is in ``_is_enumerator_carrier``: the head must be capitalized and
#: carry no determiner of its own, so "At this stage I want" (lowercase,
#: determiner) keeps its first person and "Count I alleges" does not.
_ENUMERATOR_CARRIERS: frozenset = frozenset({
    "article", "title", "schedule", "part", "exhibit", "section", "chapter",
    "appendix", "annex", "phase", "class", "type", "volume", "book", "act",
    "rule", "form", "grade", "level", "tier", "stage", "step", "world war",
    "count", "table", "paragraph", "issue", "figure", "item", "claim", "clause",
    "subsection", "point", "question", "option", "page", "line", "note",
    "footnote", "division", "round", "game", "season", "episode", "scene",
    "unit", "module", "lesson", "sheet", "plate", "panel", "series", "group",
    "zone", "district", "ward", "grade", "mark", "model",
})
#: citation / enumerator spans, found on the raw sentence text. A token inside
#: one is a REFERENCE: never a seat of its own, never first person.
_CITATION_RES: tuple = (
    re.compile(r"\b\d+\s+C\.?F\.?R\.?\s+(?:Part\s+)?\d+(?:\.\d+)*(?:\([a-z0-9]+\))*", re.I),
    re.compile(r"\b\d+\s+U\.?S\.?C?\.?\s+(?:§+\s*)?(?:at\s+)?\d+[a-z]?(?:\([a-z0-9]+\))*", re.I),
    re.compile(r"\b\d+\s+F\.\s*(?:2d|3d|4th|Supp\.?)\s+\d+", re.I),
    re.compile(r"\bRules?\s+\d+(?:\([a-z0-9]+\))*(?:\s+of\s+the\s+[A-Z][\w\s]{0,40}?Procedure)?"),
    # an enumerator head + a Roman or Arabic numeral: "Article I" · "Count I"
    # · "Table 3" · "Section 1614.104" -- the same heads the first-person
    # gate reads, capitalized, so the two rules cannot drift apart
    re.compile(r"\b(?:" + "|".join(sorted(c.capitalize() for c in _ENUMERATOR_CARRIERS if " " not in c))
               + r")s?\s+(?:[IVXLC]+|\d+(?:\.\d+)*)(?:\([a-z0-9]+\))*\b"),
    re.compile(r"§+\s*\d+(?:\.\d+)*(?:\([a-z0-9]+\))*"),
    # case names: "West, supra" · "Smith v. Jones" · "In re Doe"
    re.compile(r"\b[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3},\s+supra\b"),
    re.compile(r"\b[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3}\s+v\.\s+[A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3}"),
    re.compile(r"\bIn\s+re\s+[A-Z][\w.'-]+"),
)
#: entity labels that name a party (a seat) vs. a reference
SEAT_ENT_LABELS: frozenset = frozenset({"PERSON", "ORG", "GPE", "NORP", "LOC", "FAC"})
REF_ENT_LABELS: frozenset = frozenset({"LAW", "WORK_OF_ART", "EVENT", "PRODUCT"})

# --- nominalizations -----------------------------------------------------------
_NOMINAL_SUFFIXES: tuple = ("ing", "tion", "sion", "ment", "ance", "ence", "ure", "al", "ery")
#: organisations and roles that END like nominalizations but ARE parties
_ROLE_NOUNS: frozenset = frozenset({
    "commission", "administration", "organization", "organisation", "corporation",
    "association", "institution", "government", "department", "foundation",
    "coalition", "delegation", "nation", "population", "union", "council",
    "tribunal", "official", "principal", "general", "professional", "individual",
    "criminal", "national", "judge", "counsel", "agency", "office", "director",
    "management", "parliament",
})
_DEVERBAL_LIST: frozenset = frozenset({
    "use", "reliance", "answer", "failure", "dismissal", "decision", "referral",
    "request", "review", "finding", "delay", "investigation", "appeal", "discovery",
    "denial", "refusal", "withdrawal", "release", "response", "practice", "process",
    "hearing", "referral", "approval", "petition", "complaint", "mismatch",
})

_NP_CHILD_DEPS: frozenset = frozenset({"det", "amod", "compound", "poss", "case", "nummod", "quantmod", "nmod", "npadvmod"})
_SUBJECT_DEPS: frozenset = frozenset({"nsubj", "csubj", "expl"})
_PASSIVE_SUBJECT_DEPS: frozenset = frozenset({"nsubjpass", "csubjpass"})
_CLAUSE_DEPS: frozenset = frozenset({"ROOT", "ccomp", "advcl", "conj", "relcl", "xcomp", "acl", "pcomp", "parataxis", "csubj"})


# ===========================================================================
# The row
# ===========================================================================
@dataclass
class Clause:
    """One attributed clause. ``tuple8`` is the A1 contract; the rest is what
    the ledger needs to seat the row without a second parse."""
    agent_span: str
    verb_lemma: str
    object_span: str
    negation: bool
    modality: str
    contrast_span: list
    tense: str
    sentence_idx: int
    # -- the ledger's fields --
    verb_idx: int                       # token index, for the reading order
    clause_dep: str                     # ROOT / ccomp / advcl / xcomp / conj / ...
    agent_dep: str                      # nsubj / agent / inherited / undefined
    agent_key: str                      # name key (lemma + compounds, or the entity text)
    agent_ent: str                      # entity label of the agent head, "" when none
    agent_first_person: bool
    agent_pronoun: bool                 # an UNRESOLVED third-person pronoun
    agent_nominalization: bool
    agent_link_key: Optional[str]       # the seat a nominalization belongs to, when the tree names one
    agent_link_first_person: bool
    agent_is_ref: bool                  # inside a citation / LAW entity
    object_dep: str                     # dobj / pobj / attr / acomp / xcomp / passive_subject / undefined
    object_key: str
    object_ent: str
    object_first_person: bool
    object_pronoun: bool
    object_is_ref: bool
    agent_proper: bool = False          # a proper noun in the agent phrase (PROPN or entity) -- a NAME
    object_proper: bool = False         # a proper noun in the object phrase -- a NAME the recogniser may not have spanned
    inner_keys: list = field(default_factory=list)   # (key, dep, first_person, ent) nominals inside the object / dative
    numbers: list = field(default_factory=list)      # NUM tokens in the object span -- the load
    prov_key: Optional[str] = None                   # the reporter's key on a reported clause
    prov_first_person: bool = False
    passive: bool = False

    @property
    def tuple8(self) -> tuple:
        return (self.agent_span, self.verb_lemma, self.object_span, self.negation,
                self.modality, list(self.contrast_span), self.tense, self.sentence_idx)

    def to_dict(self) -> dict:
        return asdict(self)


# ===========================================================================
# The model, loaded once
# ===========================================================================
_NLP = None
_NLP_LOCK = threading.Lock()
_LOAD_SECONDS: Optional[float] = None


def _nlp():
    """Load ``en_core_web_sm`` once per process. Lazy so tests that never
    parse pay nothing; ``warm()`` loads it eagerly at boot in production so
    the cold-start number (R-366-C) is the whole truth."""
    global _NLP, _LOAD_SECONDS
    if _NLP is not None:
        return _NLP
    with _NLP_LOCK:
        if _NLP is None:
            import time
            import spacy  # exact-pinned; no vendor, no network
            t0 = time.perf_counter()
            _NLP = spacy.load(MODEL_NAME, disable=("ner",) if _ner_disabled() else ())
            _LOAD_SECONDS = time.perf_counter() - t0
    return _NLP


def _ner_disabled() -> bool:
    # The entity recogniser is part of the enumerator guard and the seat
    # labels; it stays ON unless a test asks otherwise.
    return os.environ.get("CLARITYOS_CLAUSE_PARSER_NO_NER") == "1"


def warm() -> dict:
    """Load the model now. Returns ``{loaded, load_seconds, version}``."""
    _nlp()
    return {"loaded": True, "load_seconds": _LOAD_SECONDS, "version": PARSER_VERSION}


def is_loaded() -> bool:
    return _NLP is not None


# ===========================================================================
# Helpers over the tree
# ===========================================================================
def _citation_spans(sent_text: str, offset: int) -> list:
    """Character spans (absolute) of citations / enumerators in one sentence."""
    out = []
    for rx in _CITATION_RES:
        for m in rx.finditer(sent_text):
            out.append((offset + m.start(), offset + m.end(), m.group(0)))
    return out


def _in_citation(tok, spans) -> Optional[str]:
    for a, b, txt in spans:
        if tok.idx >= a and tok.idx + len(tok.text) <= b:
            return txt
    return None


#: entity labels that NAME something. Numbers, money, dates, percentages,
#: quantities and ordinals are values (the load), never names: a MONEY span
#: read as a name would carry "7,514 dollars" as an identity.
_NAME_ENT_LABELS: frozenset = SEAT_ENT_LABELS | REF_ENT_LABELS | frozenset({"LANGUAGE"})


def _ent_of(tok):
    """The NAMED entity containing ``tok``, or None. A heading-shaped span
    the recogniser labels ORG ("Complaints Requiring Hearings Are Rare") is
    not an entity: a span with a finite verb or auxiliary inside it names
    nobody. A value-typed span (MONEY · DATE · CARDINAL · PERCENT · …) is
    not a name."""
    if tok.ent_iob_ == "O":
        return None
    for e in tok.doc.ents:
        if e.start <= tok.i < e.end:
            if e.label_ not in _NAME_ENT_LABELS:
                return None
            if any(t.pos_ in ("VERB", "AUX") and "Fin" in t.morph.get("VerbForm") for t in e):
                return None
            if len(e) > 5:
                return None
            return e
    return None


def _is_enumerator_carrier(prev) -> bool:
    """The noun before a capital *I* enumerates it when it is a capitalized
    enumerator head with no determiner of its own and is not a time word:
    "Count I alleges" · "Table I lists" · "Article I was" -- never "At this
    stage I want" or "For the most part I agreed" or "Yesterday I filed"."""
    if prev.pos_ not in ("NOUN", "PROPN"):
        return False
    if not prev.text[:1].isupper():
        return False
    if any(c.dep_ == "det" for c in prev.children):
        return False
    if prev.ent_type_ in ("DATE", "TIME", "CARDINAL", "ORDINAL"):
        return False
    return prev.lemma_.lower() in _ENUMERATOR_CARRIERS


def _is_first_person(tok, spans) -> bool:
    if tok.lower_ not in _FIRST_PERSON:
        return False
    if _ent_of(tok) is not None:                  # inside a NAMED entity (Article I = LAW)
        return False
    if _in_citation(tok, spans) is not None:      # inside a citation span
        return False
    if tok.text == "I" and tok.i > 0 and _is_enumerator_carrier(tok.doc[tok.i - 1]):
        return False                              # an enumerator head stands before it
    return True


def is_unresolved_pronoun(key: Any) -> bool:
    """A third-person pronoun key (it · they · he · this): a referent the
    parser does not resolve and the ledger must not seat as a party."""
    return isinstance(key, str) and key.strip().lower() in _THIRD_PRONOUNS


def _np_span(tok):
    """The compact noun phrase around ``tok``: determiners, modifiers,
    compounds, possessives. Not the whole subtree (a relative clause is a
    clause of its own)."""
    ent = _ent_of(tok)
    lo, hi = tok.i, tok.i
    if ent is not None:
        lo, hi = ent.start, ent.end - 1
    stack = [c for c in tok.children if c.dep_ in _NP_CHILD_DEPS]
    while stack:
        c = stack.pop()
        lo, hi = min(lo, c.i), max(hi, c.i)
        stack.extend(cc for cc in c.children if cc.dep_ in ("compound", "case", "amod", "nummod", "det"))
    return tok.doc[lo:hi + 1]


def _key(tok, spans) -> str:
    """The name key the ledger seats by: an entity's text, a citation's
    text, else the head lemma with its noun compounds."""
    cit = _in_citation(tok, spans)
    if cit is not None:
        return _norm(cit)
    ent = _ent_of(tok)
    if ent is not None:
        return _norm(ent.text)
    if tok.lower_ in _FIRST_PERSON:
        return "I"
    if tok.pos_ == "PRON":
        return tok.lower_
    # a proper noun keeps its surface form (VA, not va): the recogniser does
    # not tag every mention, and the ledger matches keys case-insensitively
    parts = [(c.text if c.pos_ == "PROPN" else c.lemma_.lower())
             for c in tok.lefts if c.dep_ == "compound" and c.pos_ in ("NOUN", "PROPN")]
    parts.append(tok.text if tok.pos_ == "PROPN" else tok.lemma_.lower())
    return " ".join(parts)


def _norm(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(the|a|an)\s+", "", s, flags=re.I)
    return s.rstrip(".,;:")


def _is_nominalization(tok) -> bool:
    """A process standing as an agent: a deverbal noun, a gerund subject
    ("Granting the request would be discretionary" -- the lemma is *grant*,
    the token ends in -ing), or a clause as subject (``csubj``)."""
    if tok.dep_ in ("csubj", "csubjpass") or tok.pos_ in ("VERB", "AUX"):
        return True
    if tok.pos_ != "NOUN":
        return False
    lem = tok.lemma_.lower()
    if lem in _ROLE_NOUNS:
        return False
    if lem in _DEVERBAL_LIST:
        return True
    if tok.lower_.endswith("ing") and len(tok.lower_) > 5:
        return True
    return lem.endswith(_NOMINAL_SUFFIXES) and len(lem) > 5


def _link_of_nominalization(tok, spans) -> Optional[Any]:
    """The seat a nominalization belongs to, when the tree names one:
    a possessive (the agency's sharing), a *by* agent, or a *from/of/among*
    phrase whose object is a party (an entity or a role noun)."""
    for c in tok.children:
        if c.dep_ == "poss" and c.pos_ in ("NOUN", "PROPN", "PRON"):
            return c
    for c in tok.children:
        if c.dep_ == "prep" and c.lemma_.lower() in ("by", "from", "of", "among", "between"):
            for p in c.children:
                if p.dep_ == "pobj" and (p.pos_ in ("PROPN", "PRON") or _ent_of(p) is not None
                                         or p.lemma_.lower() in _ROLE_NOUNS or _is_nominalization(p) is False and p.pos_ == "NOUN" and c.lemma_.lower() in ("by", "from", "among")):
                    return p
    return None


def _clause_heads(sent) -> list:
    """Every token that heads a clause: VERBs (not participial modifiers) and
    AUX copulas that head their own clause."""
    heads = []
    for t in sent:
        if t.pos_ == "VERB":
            if t.dep_ in ("amod", "compound", "nmod"):
                continue                          # "proposed rule", "approved agencies"
            if t.dep_ == "acl" and "Part" in t.morph.get("VerbForm") and not any(c.dep_ in _SUBJECT_DEPS | _PASSIVE_SUBJECT_DEPS | {"dobj", "obj"} for c in t.children):
                continue                          # a bare participle with nothing under it
            heads.append(t)
        elif t.pos_ == "AUX" and t.dep_ not in ("aux", "auxpass") and t.dep_ in _CLAUSE_DEPS:
            if any(c.dep_ in ("acomp", "attr", "prep", "advmod", "nsubj", "nsubjpass", "xcomp", "ccomp") for c in t.children) or t.dep_ == "ROOT":
                heads.append(t)
    return heads


def _own_subject(v):
    """The clause's own subject. An expletive (*there is*, *it makes sense*
    with ``expl``) names nobody and is not a subject here."""
    for c in v.children:
        if c.dep_ in ("nsubj", "csubj"):
            return c, c.dep_
    for c in v.children:
        if c.dep_ in _PASSIVE_SUBJECT_DEPS:
            return c, c.dep_
    return None, None


#: verbs whose OBJECT controls the following infinitive ("allow the agency to
#: develop", "pressure a complainant into withdrawing"). Anything else is
#: subject control ("want to go", "make sense to allow").
_OBJECT_CONTROL_VERBS: frozenset = frozenset({
    "allow", "permit", "enable", "force", "compel", "require", "cause", "lead",
    "pressure", "push", "ask", "tell", "order", "direct", "convince", "persuade",
    "help", "get", "leave", "let", "expect", "want", "encourage", "urge", "invite",
    "authorize", "authorise", "entitle", "oblige", "prevent", "stop", "keep",
})


def _parent(v):
    """The clause above ``v``, stepping over a preposition (pcomp → prep →
    its head) and an adjective complement (xcomp → acomp → its copula)."""
    h = v.head
    if h is v:
        return None
    if h.pos_ == "ADP":
        h = h.head
    return h


def _controller_subject(v, depth: int = 0):
    """Inherit a subject through xcomp / conj / acomp / pcomp / advcl-without-
    subject. Returns (token, dep, hops) or (None, None, hops)."""
    if depth > 6:
        return None, None, depth
    subj, dep = _own_subject(v)
    if subj is not None:
        return subj, dep, depth
    if v.dep_ in ("xcomp", "conj", "acomp", "pcomp", "advcl", "acl", "relcl") and v.head is not v:
        h = _parent(v)
        if h is None:
            return None, None, depth
        if v.dep_ == "relcl":
            return h, "relcl_head", depth + 1
        if v.dep_ == "acl":
            return h, "acl_head", depth + 1
        # object control ONLY under a verb that takes it: the nearest dobj of
        # the governing verb controls a pcomp/xcomp
        if v.dep_ in ("xcomp", "pcomp") and h.pos_ == "VERB" and h.lemma_.lower() in _OBJECT_CONTROL_VERBS:
            for c in h.children:
                if c.dep_ in ("dobj", "obj"):
                    return c, "object_control", depth + 1
        # an adjective complement's subject is the copula's subject
        if h.pos_ == "ADJ" and h.dep_ == "acomp":
            return _controller_subject(h, depth + 1)
        return _controller_subject(h, depth + 1)
    return None, None, depth


def _aux_chain(v) -> list:
    """The auxiliary lemmas that scope this verb, inherited through the
    control chain when the verb has none of its own AND no subject of its
    own: "could adopt, reject, or modify" shares the modal; "The agency must
    respond, and the judge granted the motion" does not -- the second clause
    is a finite clause with its own subject (refuter, 2026-09-19)."""
    own = [c.lemma_.lower() for c in v.children if c.dep_ in ("aux", "auxpass")]
    own = [a for a in own if a != "to"]
    if own:
        return own
    if _own_subject(v)[0] is not None:
        return []
    if v.dep_ in ("xcomp", "conj", "acomp", "pcomp", "ccomp_inherit") and v.head is not v:
        h = v.head
        if h.pos_ == "ADP":
            h = h.head
        return _aux_chain(h)
    return []


def _governors(v):
    """The verb and the clause heads above it, root first-out."""
    t = v
    seen = 0
    while seen < 12:
        yield t
        if t.dep_ == "ROOT" or t.head is t:
            break
        t = t.head
        seen += 1


def _has_if_mark(v) -> bool:
    for t in _governors(v):
        for c in t.children:
            if c.dep_ == "mark" and c.lemma_.lower() in _IF_MARKS:
                return True
            if c.dep_ == "advcl":
                for cc in c.children:
                    if cc.dep_ == "mark" and cc.lemma_.lower() in ("if", "unless"):
                        return True
    return False


def _negated(v, obj_tok, subj_tok=None) -> bool:
    """A ``neg`` dependent of the verb or of an auxiliary, never/not as an
    adverb, or a determiner *no* on the object OR the subject ("No agency
    responded" -- the same dependency on the other side of the verb;
    refuter, 2026-09-19)."""
    for c in v.children:
        if c.dep_ == "neg":
            return True
        if c.dep_ in ("aux", "auxpass"):
            if any(cc.dep_ == "neg" for cc in c.children):
                return True
        if c.dep_ == "advmod" and c.lemma_.lower() in ("never", "not"):
            return True
    for tok in (obj_tok, subj_tok):
        if tok is not None:
            for c in tok.children:
                if c.dep_ == "det" and c.lemma_.lower() == "no":
                    return True
    return False


def _tense(v, auxes_tokens) -> str:
    vf = v.morph.get("VerbForm")
    t = v.morph.get("Tense")
    if "Fin" in vf and t:
        return "past" if "Past" in t else "present"
    for a in auxes_tokens:
        if a.lemma_.lower() in ("will", "shall"):
            return "future"
        at = a.morph.get("Tense")
        if at:
            return "past" if "Past" in at else "present"
    if t and "Part" not in vf:
        return "past" if "Past" in t else "present"
    return UNDEFINED


def _aux_tokens(v) -> list:
    own = [c for c in v.children if c.dep_ in ("aux", "auxpass") and c.lemma_.lower() != "to"]
    if own:
        return own
    if _own_subject(v)[0] is not None:
        return []
    if v.dep_ in ("xcomp", "conj", "acomp", "pcomp") and v.head is not v:
        h = v.head
        if h.pos_ == "ADP":
            h = h.head
        return _aux_tokens(h)
    return []


def _speech_provenance(v):
    """The reporter's token when a speech verb governs this clause."""
    if v.dep_ == "ccomp" and v.head.lemma_.lower() in _SPEECH_VERBS:
        s, _ = _own_subject(v.head)
        return s if s is not None else v.head
    for c in v.children:
        if c.dep_ == "advcl" and c.lemma_.lower() in _SPEECH_VERBS and any(m.dep_ == "mark" and m.lemma_.lower() == "as" for m in c.children):
            s, _ = _own_subject(c)
            return s if s is not None else c
    for t in v.subtree:
        if t.lower_ == "according":
            for c in t.children:
                if c.dep_ == "prep":
                    for p in c.children:
                        if p.dep_ == "pobj":
                            return p
            for c in t.head.children if t.head is not t else ():
                if c.dep_ == "pobj":
                    return c
    return None


def _modality(v, auxes: list, obj_tok) -> str:
    lemmas = set(auxes)
    if lemmas & _MODAL_OBLIGATION:
        return "obligation"
    if v.lemma_.lower() in _OBLIGATION_VERBS and any(c.dep_ == "xcomp" and any(cc.lemma_.lower() == "to" for cc in c.children) for c in v.children):
        return "obligation"
    if v.dep_ == "xcomp" and v.head.lemma_.lower() in _OBLIGATION_VERBS and v.head.pos_ == "VERB":
        return "obligation"
    if lemmas & _MODAL_COUNTERFACTUAL:
        return "conditional" if _has_if_mark(v) else "counterfactual"
    if lemmas & _MODAL_CONDITIONAL:
        return "conditional"
    if _has_if_mark(v):
        return "conditional"
    if lemmas & _MODAL_EXPECTED:
        return "expected"
    if any(c.dep_ == "advmod" and c.lemma_.lower() in _EXPECTED_ADVERBS for c in v.children):
        return "expected"
    if v.dep_ == "xcomp" and v.head.lemma_.lower() in _EXPECTED_LEMMAS:
        return "expected"
    if v.lemma_.lower() in _EXPECTED_LEMMAS and any(c.dep_ == "xcomp" for c in v.children):
        return "expected"
    return "event"


def _object(v):
    """(token, dep) of the object slot, or (None, 'undefined')."""
    for c in v.children:
        if c.dep_ in ("dobj", "obj"):
            return c, c.dep_
    for c in v.children:
        if c.dep_ in ("attr", "acomp"):
            return c, c.dep_
    for c in v.children:
        if c.dep_ == "prep" and c.lemma_.lower() not in ("by",):
            for p in c.children:
                if p.dep_ in ("pobj", "pcomp"):
                    return p, "pobj:" + c.lemma_.lower()
    for c in v.children:
        if c.dep_ == "xcomp" and c.pos_ in ("VERB", "AUX"):
            return c, "xcomp"
    for c in v.children:
        if c.dep_ == "ccomp":
            return c, "ccomp"
    return None, UNDEFINED


def _marker_claims(sent, heads) -> dict:
    """Assign each contrast marker in the sentence to the clause whose verb is
    its nearest clausal ancestor. Multiword markers are matched on the text
    and assigned by their first token. Returns {verb_idx: [markers]}."""
    claims: dict = {h.i: [] for h in heads}
    head_ids = set(claims.keys())
    root = None
    for h in heads:
        if h.dep_ == "ROOT":
            root = h
    if root is None and heads:
        root = heads[0]

    def owner(tok):
        # a coordinating marker (``but`` · ``yet`` as cc) belongs to the
        # clause it introduces: the next conj sibling that heads a clause
        if tok.dep_ == "cc":
            for sib in tok.head.children:
                if sib.dep_ == "conj" and sib.i > tok.i and sib.i in head_ids:
                    return sib.i
        t = tok
        for _ in range(12):
            if t.i in head_ids:
                return t.i
            if t.head is t:
                break
            t = t.head
        return root.i if root is not None else None

    taken = set()
    text = sent.text
    for mw in _MULTIWORD_MARKERS:
        for m in re.finditer(r"\b" + re.escape(mw) + r"\b", text, flags=re.I):
            start = sent.start_char + m.start()
            first = None
            for t in sent:
                if t.idx == start:
                    first = t
                    break
            if first is None:
                continue
            o = owner(first)
            if o is None:
                continue
            claims[o].append(m.group(0).lower())
            for t in sent:
                if start <= t.idx < sent.start_char + m.end():
                    taken.add(t.i)
    for t in sent:
        if t.i in taken:
            continue
        if t.lower_ in _SINGLE_MARKERS:
            o = owner(t)
            if o is None:
                continue
            # ``if`` as a mark belongs to the clause it marks: the advcl head
            claims[o].append(t.lower_)
    return claims


#: a number is the LOAD only when it is amount-shaped. A digit run longer
#: than this, or grouped with hyphens (123-45-6789), identifies a person or a
#: file -- a docket, an SSN, a phone -- and is not carried (refuter, 2026-09-19).
_NUMBER_MAX_DIGITS: int = 6
_IDENTIFIER_NUMBER = re.compile(r"^\d+([-./]\d+)+$")


def is_identifier_number(text: str) -> bool:
    """True when a numeric token reads as an identifier rather than a load."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) > _NUMBER_MAX_DIGITS:
        return True
    if _IDENTIFIER_NUMBER.match((text or "").strip()) and len(digits) >= 5:
        return True
    return False


def _numbers(span) -> list:
    out = []
    for t in span:
        if (t.like_num or t.pos_ == "NUM") and not is_identifier_number(t.text):
            out.append(t.text)
    return out


def _has_proper(tok, ent) -> bool:
    """Any proper noun in the compact phrase around ``tok`` (or an entity)."""
    if ent is not None:
        return True
    try:
        return any(t.pos_ == "PROPN" for t in _np_span(tok))
    except Exception:  # pragma: no cover -- a span that cannot be built names nothing
        return tok.pos_ == "PROPN"


def _inner_keys(v, obj_tok, spans) -> list:
    out = []
    if obj_tok is not None:
        for t in obj_tok.subtree:
            if t is obj_tok:
                continue
            if t.dep_ in ("pobj", "poss", "conj", "appos", "dative") and t.pos_ in ("NOUN", "PROPN", "PRON"):
                ent = _ent_of(t)
                out.append({"key": _key(t, spans), "dep": t.dep_,
                            "first_person": _is_first_person(t, spans),
                            "ent": (ent.label_ if ent is not None else ""),
                            "is_ref": _in_citation(t, spans) is not None or ((ent.label_ in REF_ENT_LABELS) if ent is not None else False),
                            "proper": (not _is_first_person(t, spans)) and _has_proper(t, ent)})
    for c in v.children:
        if c.dep_ == "dative":
            ent = _ent_of(c)
            out.append({"key": _key(c, spans), "dep": "dative",
                        "first_person": _is_first_person(c, spans),
                        "ent": (ent.label_ if ent is not None else ""),
                        "is_ref": False,
                        "proper": (not _is_first_person(c, spans)) and _has_proper(c, ent)})
    return out


# ===========================================================================
# The parse
# ===========================================================================
def parse_clauses(text: str) -> list:
    """Text → attributed clause rows, in reading order (sentence, then verb
    position). Empty or non-string text → ``[]``."""
    if not isinstance(text, str) or not text.strip():
        return []
    nlp = _nlp()
    doc = nlp(text)
    rows: list = []
    for s_idx, sent in enumerate(doc.sents):
        spans = _citation_spans(sent.text, sent.start_char)
        heads = _clause_heads(sent)
        claims = _marker_claims(sent, heads)
        for v in heads:
            subj, subj_dep = _own_subject(v)
            passive = subj_dep in _PASSIVE_SUBJECT_DEPS if subj_dep else False
            agent_tok, agent_dep = None, UNDEFINED
            obj_tok, obj_dep = None, UNDEFINED
            if passive:
                obj_tok, obj_dep = subj, "passive_subject"
                for c in v.children:
                    if c.dep_ == "agent":
                        for p in c.children:
                            if p.dep_ == "pobj":
                                agent_tok, agent_dep = p, "agent"
            else:
                if subj is not None:
                    agent_tok, agent_dep = subj, subj_dep
                else:
                    ctrl, cdep, hops = _controller_subject(v)
                    # an inherited PASSIVE subject is the patient, not the
                    # agent: "was filed by the member and dismissed by the
                    # agency" -- the second verb's own by-phrase names its
                    # agent and the complaint stays in the object slot
                    # (refuter, 2026-09-19). Its own ``auxpass`` says the
                    # same ("was expected to be dismissed").
                    own_auxpass = any(c.dep_ == "auxpass" for c in v.children)
                    if ctrl is not None and (str(cdep) in _PASSIVE_SUBJECT_DEPS or own_auxpass):
                        passive = True
                        obj_tok, obj_dep = ctrl, "passive_subject"
                        for c in v.children:
                            if c.dep_ == "agent":
                                for p in c.children:
                                    if p.dep_ == "pobj":
                                        agent_tok, agent_dep = p, "agent"
                    elif ctrl is not None:
                        agent_tok, agent_dep = ctrl, "inherited:" + str(cdep)
                if not passive:
                    obj_tok, obj_dep = _object(v)
            auxes_l = _aux_chain(v)
            auxes_t = _aux_tokens(v)
            prov = _speech_provenance(v)
            modality = _modality(v, auxes_l, obj_tok)
            if modality == "event" and prov is not None:
                modality = "reported"
            contrast = list(claims.get(v.i, []))

            def _desc(tok):
                if tok is None:
                    return {"span": UNDEFINED, "key": UNDEFINED, "ent": "", "fp": False, "pron": False, "ref": False, "proper": False}
                if tok.pos_ in ("VERB", "AUX", "ADJ", "ADV") and tok.dep_ in ("xcomp", "acomp", "ccomp", "pcomp"):
                    return {"span": tok.lemma_.lower(), "key": tok.lemma_.lower(), "ent": "", "fp": False, "pron": False, "ref": False, "proper": False}
                ent = _ent_of(tok)
                cit = _in_citation(tok, spans)
                # an entity whose span holds a citation ("Section 1614.104--
                # Agency Processing" read as ORG) is a reference, not a party
                ent_has_cit = ent is not None and any(_in_citation(t, spans) is not None for t in ent)
                fp = _is_first_person(tok, spans)
                return {
                    "span": _np_span(tok).text if cit is None else cit,
                    "key": _key(tok, spans),
                    "ent": ent.label_ if ent is not None else "",
                    "fp": fp,
                    "pron": tok.pos_ in ("PRON", "DET", "ADV") and tok.lower_ in _THIRD_PRONOUNS,
                    "ref": cit is not None or ent_has_cit or (ent is not None and ent.label_ in REF_ENT_LABELS),
                    # a NAME the recogniser may not have spanned: any proper
                    # noun in the phrase ("the Piatt letter" · "Marisol")
                    "proper": (not fp) and _has_proper(tok, ent),
                }

            a = _desc(agent_tok)
            o = _desc(obj_tok)
            nominal = agent_tok is not None and not a["fp"] and not a["ref"] and a["ent"] == "" and not a["pron"] and not a["proper"] and _is_nominalization(agent_tok)
            link_key, link_fp = None, False
            if nominal:
                lk = _link_of_nominalization(agent_tok, spans)
                if lk is not None:
                    link_key = _key(lk, spans)
                    link_fp = _is_first_person(lk, spans)
            rows.append(Clause(
                agent_span=a["span"], verb_lemma=v.lemma_.lower(), object_span=o["span"],
                negation=_negated(v, obj_tok if obj_dep not in ("xcomp", "ccomp") else None,
                                  agent_tok if (agent_tok is not None and not passive) else None),
                modality=modality, contrast_span=contrast,
                tense=_tense(v, auxes_t), sentence_idx=s_idx,
                verb_idx=v.i, clause_dep=v.dep_,
                agent_dep=agent_dep, agent_key=a["key"], agent_ent=a["ent"],
                agent_first_person=a["fp"], agent_pronoun=a["pron"],
                agent_nominalization=nominal, agent_link_key=link_key, agent_link_first_person=link_fp,
                agent_is_ref=a["ref"],
                object_dep=obj_dep, object_key=o["key"], object_ent=o["ent"],
                object_first_person=o["fp"], object_pronoun=o["pron"], object_is_ref=o["ref"],
                agent_proper=bool(a["proper"]), object_proper=bool(o["proper"]),
                inner_keys=_inner_keys(v, obj_tok if obj_dep not in ("xcomp", "ccomp") else None, spans),
                numbers=_numbers(_np_span(obj_tok)) if (obj_tok is not None and obj_dep not in ("xcomp", "ccomp")) else [],
                prov_key=(_key(prov, spans) if prov is not None else None),
                prov_first_person=(_is_first_person(prov, spans) if prov is not None else False),
                passive=passive,
            ))
    rows.sort(key=lambda r: (r.sentence_idx, r.verb_idx))
    return rows


def rows_in_reading_order(rows: Iterable[Clause]) -> bool:
    """True iff ``rows`` is ordered by (sentence_idx, verb_idx). The
    reading-order refuter is this predicate over the emitted chain."""
    last = (-1, -1)
    for r in rows:
        k = (r.sentence_idx, r.verb_idx)
        if k < last:
            return False
        last = k
    return True
