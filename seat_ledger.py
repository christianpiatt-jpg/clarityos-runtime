"""
seat_ledger.py — #366 A2. Attribution is a ledger, not a map.

WHAT THIS IS
------------
The second station of the out-loop transformer. Parsed clause rows
(``clause_parser.Clause``) come in; attributed triples with SEAT IDS come
out, and the seats' two verb slots are kept per relationship.

SEATS
-----
    A0        the author (first person: I · me · my · we · our)
    INST      the instrument -- its verdicts are a seat (WALK §4: anything
              that exerts holds a seat, intent not required)
    PRO       an unresolved third-person pronoun (it · they · this): no
              coreference is done, so the referent is not guessed
    S_n       a party read from a role noun or a PERSON entity (complainant,
              agency, administrative judge, the Director)
    org_n     an organisation / place entity (EEOC, the Commission)
    ref_n     a reference: a citation, a LAW / WORK entity, a case name.
              Never a party, never first person (R-374-A closes here)
    N_n       a nominalization standing as the agent of its own row (the
              sharing · the use · the reliance). The row's agent IS the
              nominalization; the seat it belongs to rides in ``link`` and is
              never substituted for it (specimen 7, rows 2 · 12 · 16 · 20).

Ids are assigned on FIRST APPEARANCE within a relationship (thread) and
persist across turns in the vault. The id↔name map lives ON-MACHINE ONLY:
``relationships.seatmap.{thread_id}``. It is read by the reassembler (A8)
and by nothing that serializes toward a model.

Every agent holds a seat. An object holds a seat when it is an entity, a
reference, first person, a pronoun, or a key that is an AGENT somewhere in
the same turn or the relationship's history (two passes over the turn's
rows, so the first mention is seated by the second). Every other object is
LEXICAL: its head lemma, a common noun, never a name.

TWO VERB SLOTS, NEVER MERGED
----------------------------
    verb_self[seat]   the seat's own clauses          (seat is ``s``)
    verb_field[seat]  verbs applied TO the seat        (seat is ``o`` or
                      inside the object, or a dative), by other seats and by
                      instruments
Both keyed by verb-object signature ``(verb_lemma, other_seat_or_lemma)`` so
the same word under two objects is two rows (WALK §1: *allow*).

DIRECTIONAL PRESSURE (the GO: "name A2's pressure sign on the row")
    sign(verb_field - verb_self) over the seat's demand/resist rows,
    basis = ``count_difference``. Named on every ledger row; the hydronic
    basis is NOT used here (PressureModel.compute is not in the tree).

THE LEDGER ROW
    (seat, owes, seat, verb, state, since_turn) with
    state ∈ {met, transferred, avoided, violated, undefined}, written only
    from demand/resist frames: an ``obligation`` row, a negated ``expected``
    row, a contrast marker on an ``event`` row. The STATE comes from the
    lanes' consolidated read (A7): robust → that state; contested or no
    reading → ``undefined`` (D5). Stored under
    ``relationships.ledger.{thread_id}``.

AUTHOR CLASSES
    The seat classes the author holds (WALK §1: "complainant" is the pilot's
    own seat class). Learned from the author's own copular clauses (``I am a
    complainant`` → attr ``complainant``) and declarable through
    ``declare_author_class``. A row whose seat name is one of them counts as
    the asker's seat (A8's ask fires iff the asker holds a seat).
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any, Iterable, Optional

import memory_vault
from clause_parser import Clause, SEAT_ENT_LABELS, REF_ENT_LABELS, is_unresolved_pronoun

logger = logging.getLogger("clarityos.seat_ledger")

LEDGER_VERSION: str = "seat.ledger.v1"
NAMESPACE: str = "relationships"
_LEDGER_PREFIX: str = "relationships.ledger."
_SEATMAP_PREFIX: str = "relationships.seatmap."

SEAT_AUTHOR: str = "A0"
SEAT_INSTRUMENT: str = "INST"
SEAT_PRONOUN: str = "PRO"
LEDGER_STATES: tuple = ("met", "transferred", "avoided", "violated", "undefined")
PRESSURE_BASIS: str = "count_difference"
UNDEFINED: str = "undefined"

_KIND_PREFIX: dict = {"seat": "S_", "org": "org_", "ref": "ref_", "nominal": "N_"}
_LOCK = threading.RLock()


def _norm_key(key: str) -> str:
    return re.sub(r"\s+", " ", (key or "").strip().lower())


# ===========================================================================
# The seat map -- on-machine only
# ===========================================================================
class SeatMap:
    """id ↔ name for one relationship. ``names()`` is the A4 refuter's set."""

    def __init__(self, data: Optional[dict] = None) -> None:
        self.by_id: dict = {}
        self.by_key: dict = {}
        self.counters: dict = {"seat": 0, "org": 0, "ref": 0, "nominal": 0}
        self.by_id[SEAT_AUTHOR] = {"name": "I", "kind": "author", "mentions": []}
        self.by_id[SEAT_INSTRUMENT] = {"name": "the instrument", "kind": "instrument", "mentions": []}
        self.by_id[SEAT_PRONOUN] = {"name": "(unresolved pronoun)", "kind": "pronoun", "mentions": []}
        if isinstance(data, dict):
            for sid, ent in (data.get("by_id") or {}).items():
                if isinstance(ent, dict) and isinstance(ent.get("name"), str):
                    # ``proper`` rides the round trip: a PERSON seat marked on
                    # turn N keeps its token-level A4 protection on turn N+1
                    # (the first reload dropped it -- refuter, 2026-09-19)
                    self.by_id[sid] = {"name": ent["name"], "kind": str(ent.get("kind") or "seat"),
                                       "mentions": list(ent.get("mentions") or []),
                                       "proper": bool(ent.get("proper"))}
            for k, sid in (data.get("by_key") or {}).items():
                self.by_key[str(k)] = str(sid)
            for k, v in (data.get("counters") or {}).items():
                if k in self.counters:
                    self.counters[k] = int(v)

    # -- assignment --------------------------------------------------------
    def seat_for(self, key: str, kind: str, mention: Optional[str] = None) -> str:
        """The id for ``key`` (assigned on first appearance)."""
        nk = _norm_key(key)
        if not nk or nk == UNDEFINED:
            raise ValueError("a seat needs a key")
        sid = self.by_key.get(nk)
        if sid is None:
            if kind not in _KIND_PREFIX:
                raise ValueError("unknown seat kind %r" % kind)
            self.counters[kind] += 1
            sid = "%s%d" % (_KIND_PREFIX[kind], self.counters[kind])
            self.by_id[sid] = {"name": key.strip(), "kind": kind, "mentions": [], "proper": False}
            self.by_key[nk] = sid
        ent = self.by_id[sid]
        if mention and mention not in ent["mentions"] and len(ent["mentions"]) < 12:
            ent["mentions"].append(mention)
        return sid

    def lookup(self, key: str) -> Optional[str]:
        return self.by_key.get(_norm_key(key))

    def name_of(self, sid: str) -> str:
        ent = self.by_id.get(sid)
        return ent["name"] if ent else UNDEFINED

    def kind_of(self, sid: str) -> str:
        ent = self.by_id.get(sid)
        return ent["kind"] if ent else UNDEFINED

    def names(self) -> set:
        """Every name and mention the map holds, lowercased. Ids and the
        three fixed seats' labels are NOT names."""
        out: set = set()
        for sid, ent in self.by_id.items():
            if ent["kind"] in ("author", "instrument", "pronoun"):
                continue
            out.add(_norm_key(ent["name"]))
            for m in ent["mentions"]:
                out.add(_norm_key(m))
        return {n for n in out if n}

    def proper_tokens(self) -> set:
        """Tokens of entity / reference names (the fixture's list: EEOC ·
        Commission · West · Rule · CFR · …), for the token-level refuter."""
        out: set = set()
        for sid, ent in self.by_id.items():
            if ent["kind"] not in ("org", "ref", "seat"):
                continue
            if ent["kind"] == "seat" and not ent.get("proper"):
                continue
            for tok in re.split(r"[^A-Za-z0-9§.]+", ent["name"]):
                t = tok.strip(".").lower()
                if len(t) >= 2 and t not in _STOP:
                    out.add(t)
            for m in ent["mentions"]:
                for tok in re.split(r"[^A-Za-z0-9§.]+", m):
                    t = tok.strip(".").lower()
                    if len(t) >= 2 and t not in _STOP:
                        out.add(t)
        return out

    def mark_proper(self, sid: str) -> None:
        if sid in self.by_id:
            self.by_id[sid]["proper"] = True

    def to_dict(self) -> dict:
        return {"v": LEDGER_VERSION, "by_id": self.by_id, "by_key": self.by_key, "counters": self.counters}


_STOP: frozenset = frozenset({
    "the", "of", "and", "or", "a", "an", "in", "on", "at", "to", "for", "by",
    "with", "de", "la", "le", "v", "vs", "re", "supra", "us", "u.s", "part",
})


# ===========================================================================
# Attribution -- rows → triples with ids
# ===========================================================================
def _kind_for_agent(row: Clause) -> str:
    if row.agent_is_ref or (row.agent_ent in REF_ENT_LABELS):
        return "ref"
    if row.agent_ent in SEAT_ENT_LABELS:
        return "org" if row.agent_ent in ("ORG", "GPE", "NORP", "FAC", "LOC") else "seat"
    if row.agent_nominalization:
        return "nominal"
    return "seat"


def _kind_for_object(row: Clause) -> Optional[str]:
    if row.object_is_ref or (row.object_ent in REF_ENT_LABELS):
        return "ref"
    if row.object_ent in SEAT_ENT_LABELS:
        return "org" if row.object_ent in ("ORG", "GPE", "NORP", "FAC", "LOC") else "seat"
    if row.object_proper:
        # a proper noun the recogniser did not span ("the Piatt letter" ·
        # "Marisol") is a NAME: it is seated so its tokens enter the
        # refuter's set and the id rides, never the word (refuter, 2026-09-19)
        return "seat"
    return None


def learn_author_classes(rows: Iterable[Clause]) -> set:
    """``I am a complainant`` → {"complainant"}. Only the author's own copular
    clauses with a common-noun complement; never inferred from a verb."""
    out: set = set()
    for r in rows:
        if r.agent_first_person and r.verb_lemma == "be" and r.object_dep == "attr" \
                and not r.negation \
                and r.object_key not in (UNDEFINED, "") and not r.object_is_ref and not r.object_ent \
                and not r.object_pronoun and not r.object_first_person:
            # "I am not a lawyer" declares nothing (refuter, 2026-09-19)
            out.add(_norm_key(r.object_key))
    return out


def attribute(rows: list, seatmap: SeatMap, *, author_classes: Optional[set] = None) -> list:
    """Clause rows → triples with seat ids. Two passes: agents first (every
    agent holds a seat), then objects (a key that is an agent anywhere is
    seated everywhere). Returns a list of dicts in the rows' order::

        {"i": sentence_idx, "k": verb_idx, "s": seat_id, "v": lemma,
         "o": seat_id | lemma | None, "ok": "seat"|"lex"|"verb"|"undefined",
         "neg": bool, "mod": modality, "con": [markers], "t": tense,
         "prov": seat_id|None, "link": seat_id|None, "os": [seat ids inside the object],
         "num": [numbers], "asker": bool}
    """
    classes = {_norm_key(c) for c in (author_classes or set())}
    # pass 1 -- agents
    agent_ids: list = []
    for r in rows:
        sid = None
        if r.agent_key in (UNDEFINED, ""):
            sid = None
        elif r.agent_first_person:
            sid = SEAT_AUTHOR
        elif r.agent_pronoun:
            sid = SEAT_PRONOUN
        else:
            kind = _kind_for_agent(r)
            sid = seatmap.seat_for(r.agent_key, kind, mention=r.agent_span if r.agent_span != UNDEFINED else None)
            if kind in ("org", "ref") or r.agent_ent or r.agent_proper:
                seatmap.mark_proper(sid)
        agent_ids.append(sid)
    # pass 2 -- objects, links, provenance
    out: list = []
    for r, sid in zip(rows, agent_ids):
        o, ok = None, UNDEFINED
        if r.object_key not in (UNDEFINED, ""):
            if r.object_dep in ("xcomp", "ccomp"):
                o, ok = r.object_key, "verb"
            elif r.object_first_person:
                o, ok = SEAT_AUTHOR, "seat"
            elif r.object_pronoun:
                o, ok = SEAT_PRONOUN, "seat"
            else:
                kind = _kind_for_object(r)
                if kind is not None:
                    o = seatmap.seat_for(r.object_key, kind, mention=r.object_span)
                    seatmap.mark_proper(o)
                    ok = "seat"
                else:
                    known = seatmap.lookup(r.object_key)
                    if known is not None:
                        o, ok = known, "seat"
                    else:
                        o, ok = r.object_key, "lex"
        os_ids: list = []
        for ik in r.inner_keys:
            k = ik.get("key") or ""
            if ik.get("first_person"):
                os_ids.append(SEAT_AUTHOR)
            elif ik.get("is_ref") or ik.get("ent") in REF_ENT_LABELS:
                rid = seatmap.seat_for(k, "ref", mention=k)
                seatmap.mark_proper(rid)
                os_ids.append(rid)
            elif ik.get("ent") in SEAT_ENT_LABELS:
                oid = seatmap.seat_for(k, "org" if ik["ent"] in ("ORG", "GPE", "NORP", "FAC", "LOC") else "seat", mention=k)
                seatmap.mark_proper(oid)
                os_ids.append(oid)
            elif ik.get("proper") and k and k != UNDEFINED:
                # a proper noun inside the object phrase or a possessive
                # ("the agency's Vega memo") holds a seat too: named, so its
                # tokens are in the refuter's set
                pid = seatmap.seat_for(k, "seat", mention=k)
                seatmap.mark_proper(pid)
                os_ids.append(pid)
            else:
                known = seatmap.lookup(k)
                if known is not None:
                    os_ids.append(known)
        link = None
        if r.agent_nominalization and r.agent_link_key:
            if r.agent_link_first_person:
                link = SEAT_AUTHOR
            else:
                link = seatmap.lookup(r.agent_link_key)
                if link is None:
                    link = seatmap.seat_for(r.agent_link_key, "seat", mention=r.agent_link_key)
        prov = None
        if r.prov_key:
            if r.prov_first_person:
                prov = SEAT_AUTHOR
            elif is_unresolved_pronoun(r.prov_key):
                prov = SEAT_PRONOUN          # "he said" -- the same referent is PRO on its own row
            else:
                prov = seatmap.lookup(r.prov_key) or seatmap.seat_for(r.prov_key, "seat", mention=r.prov_key)
        seats_here = {x for x in ([sid, o if ok == "seat" else None, link, prov] + os_ids) if x}
        asker = SEAT_AUTHOR in seats_here or any(
            _norm_key(seatmap.name_of(x)) in classes for x in seats_here if x not in (SEAT_AUTHOR, SEAT_INSTRUMENT, SEAT_PRONOUN)
        )
        out.append({
            "i": r.sentence_idx, "k": r.verb_idx,
            "s": sid, "v": r.verb_lemma, "o": o, "ok": ok,
            "neg": bool(r.negation), "mod": r.modality, "con": list(r.contrast_span), "t": r.tense,
            "prov": prov, "link": link, "os": os_ids, "num": list(r.numbers),
            "asker": bool(asker),
        })
    return out


# ===========================================================================
# The ledger -- two verb slots, pressure sign, rows
# ===========================================================================
def _sig(v: str, other: Any) -> str:
    return "%s|%s" % (v, other if other is not None else UNDEFINED)


def is_demand_or_resist(t: dict) -> bool:
    """The frames that write the ledger: an obligation, a negated
    expectation, a contrast marker on an event."""
    if t.get("mod") == "obligation":
        return True
    if t.get("mod") == "expected" and t.get("neg"):
        return True
    if t.get("mod") == "event" and t.get("con"):
        return True
    return False


def fold_slots(ledger: dict, triples: list) -> dict:
    """Accumulate verb_self / verb_field per seat from this turn's triples.
    ``ledger["seats"][sid] = {"verb_self": {sig: n}, "verb_field": {sig: n}}``.
    Never merged: a seat's own verb and a verb applied to it are two dicts."""
    seats = ledger.setdefault("seats", {})

    def slot(sid, which):
        s = seats.setdefault(sid, {"verb_self": {}, "verb_field": {}})
        return s[which]

    for t in triples:
        s, v, o, ok = t.get("s"), t.get("v"), t.get("o"), t.get("ok")
        if s:
            d = slot(s, "verb_self")
            k = _sig(v, o)
            d[k] = d.get(k, 0) + 1
        targets = list(t.get("os") or [])
        if ok == "seat" and o:
            targets.append(o)
        for tgt in targets:
            if tgt == s:
                continue
            d = slot(tgt, "verb_field")
            k = _sig(v, s)
            d[k] = d.get(k, 0) + 1
    return ledger


def pressure_sign(ledger: dict, sid: str) -> dict:
    """sign(verb_field − verb_self), basis count_difference, for one seat."""
    s = (ledger.get("seats") or {}).get(sid) or {}
    field_n = sum((s.get("verb_field") or {}).values())
    self_n = sum((s.get("verb_self") or {}).values())
    diff = field_n - self_n
    return {"sign": (1 if diff > 0 else -1 if diff < 0 else 0), "field": field_n, "self": self_n, "basis": PRESSURE_BASIS}


def ledger_rows(triples: list, states: dict, turn: int, ledger: dict) -> list:
    """The ledger rows this turn writes: one per demand/resist triple.
    ``states`` maps the triple's position (index into ``triples``) → the
    consolidated row value from A7 (``{"state","direction","mass"}``) or
    None. A row with no consolidated state is ``undefined``."""
    rows: list = []
    for idx, t in enumerate(triples):
        if not is_demand_or_resist(t):
            continue
        val = states.get(idx) if isinstance(states, dict) else None
        state = UNDEFINED
        if isinstance(val, dict) and val.get("state") in LEDGER_STATES:
            state = val["state"]
        owes_to = t.get("o") if t.get("ok") == "seat" else (t.get("os") or [None])[0]
        rows.append({
            "seat": t.get("s"), "owes": True, "to": owes_to,
            "verb": t.get("v"), "object": t.get("o") if t.get("ok") in ("seat", "lex", "verb") else None,
            "state": state, "since_turn": int(turn), "frame": t.get("mod"),
            "pressure": pressure_sign(ledger, t.get("s")) if t.get("s") else {"sign": 0, "basis": PRESSURE_BASIS, "field": 0, "self": 0},
            "row": idx,
        })
    return rows


# ===========================================================================
# Persistence -- relationships.ledger.{tid} · relationships.seatmap.{tid}
# ===========================================================================
def _ledger_key(thread_id: str) -> str:
    return _LEDGER_PREFIX + thread_id


def _seatmap_key(thread_id: str) -> str:
    return _SEATMAP_PREFIX + thread_id


def load(user_id: str, thread_id: str) -> tuple:
    """(ledger dict, SeatMap) for a relationship; fresh when absent."""
    with _LOCK:
        led = memory_vault.vault_get(user_id, _ledger_key(thread_id))
        sm = memory_vault.vault_get(user_id, _seatmap_key(thread_id))
    ledger = dict(led) if isinstance(led, dict) else {"v": LEDGER_VERSION, "seats": {}, "rows": [], "author_classes": [], "turns": 0}
    ledger.setdefault("seats", {}); ledger.setdefault("rows", []); ledger.setdefault("author_classes", []); ledger.setdefault("turns", 0)
    return ledger, SeatMap(sm if isinstance(sm, dict) else None)


def save(user_id: str, thread_id: str, ledger: dict, seatmap: SeatMap) -> None:
    ledger = dict(ledger)
    ledger["v"] = LEDGER_VERSION
    ledger["updated_ts"] = time.time()
    with _LOCK:
        memory_vault.vault_put(user_id, _ledger_key(thread_id), ledger)
        memory_vault.vault_put(user_id, _seatmap_key(thread_id), seatmap.to_dict())


def declare_author_class(user_id: str, thread_id: str, cls: str) -> list:
    """Record a seat class the author holds (WALK §1). Returns the list."""
    c = _norm_key(cls)
    if not c or " " in c and len(c) > 40:
        raise ValueError("a seat class is one short noun phrase")
    ledger, sm = load(user_id, thread_id)
    classes = list(ledger.get("author_classes") or [])
    if c not in classes:
        classes.append(c)
    ledger["author_classes"] = classes
    save(user_id, thread_id, ledger, sm)
    return classes


def apply_turn(user_id: str, thread_id: str, triples: list, states: dict, turn: int,
               seatmap: SeatMap, learned_classes: Optional[set] = None) -> dict:
    """Fold one turn into the relationship's ledger and persist both halves.
    Returns the ledger rows this turn wrote."""
    ledger, _old = load(user_id, thread_id)
    classes = set(ledger.get("author_classes") or []) | {_norm_key(c) for c in (learned_classes or set())}
    ledger["author_classes"] = sorted(c for c in classes if c)
    fold_slots(ledger, triples)
    new_rows = ledger_rows(triples, states, turn, ledger)
    ledger["rows"] = list(ledger.get("rows") or []) + new_rows
    ledger["turns"] = int(ledger.get("turns") or 0) + 1
    save(user_id, thread_id, ledger, seatmap)
    return {"rows": new_rows, "seats": len(ledger["seats"]), "author_classes": ledger["author_classes"]}


def asker_seat_ids(seatmap: SeatMap, author_classes: Iterable[str]) -> set:
    """A0 plus every seat whose name is one of the author's classes."""
    classes = {_norm_key(c) for c in author_classes}
    out = {SEAT_AUTHOR}
    for sid, ent in seatmap.by_id.items():
        if ent["kind"] in ("seat",) and _norm_key(ent["name"]) in classes:
            out.add(sid)
        elif ent["kind"] == "seat" and any(_norm_key(m) in classes for m in ent.get("mentions") or []):
            out.add(sid)
    return out
