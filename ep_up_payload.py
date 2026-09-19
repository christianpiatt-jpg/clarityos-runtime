"""
ep_up_payload.py — #366 A4. Compose: the ONLY thing a model ever receives.

    EP   this turn: the attributed triples (ids and lemmas), the hydronic
         reading, D / T / N from the verb-owner set
    UP   this turn against the prior turn's frame: the sealed expectation,
         this turn's flattened observation, and score_record's tally
         (matched · missed · undefined). Absent on turn 0 -- "no prior seal",
         never an empty dict pretending to be one.

No key may hold a string that appears in the seat map. ``name_leak`` is
the A4 refuter as a function; ``compose`` runs it on its own output and
MASKS any leaking lexical value with the sentinel ``"masked"`` (a different
KIND than a word, D5) before anything is returned, so a payload that leaves
this module is clean by construction and the test proves the loop, not the
promise.

The direction bit (R-366-B): ``direction`` ∈ query·action·plan·diagnostic
and ``picked`` (True when the member chose it, False when the composer's
pre-set ``query`` rode through) travel on the payload and on the turn
record. No interim derivation exists.

The reading-order refuter: ``EP.triples`` is emitted in (sentence_idx,
verb_idx) order and ``in_reading_order`` says whether a chain is.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable, Optional

import turn_record

PAYLOAD_VERSION: str = "ep-up.v1"
DIRECTIONS: tuple = ("query", "action", "plan", "diagnostic")
MASKED: str = "masked"
UNDEFINED: str = "undefined"
HYDRONIC_UNDEFINED_REASON: str = "PressureModel.compute is not in the tree; D/T/N carried raw, direction not derived"

#: the keys of a triple that may carry LEXICAL strings (masked on a leak)
_LEXICAL_KEYS: tuple = ("o", "v")


def validate_direction(direction: Any, picked: Any) -> tuple:
    d = direction if isinstance(direction, str) and direction in DIRECTIONS else None
    if d is None:
        raise ValueError("direction must be one of %s" % (DIRECTIONS,))
    return d, bool(picked)


def compose_up(prior_record: Optional[dict], read: Optional[dict]) -> Optional[dict]:
    """UP: the prior seal against this turn's read. None on turn 0."""
    if not isinstance(prior_record, dict) or not isinstance(read, dict):
        return None
    exp = prior_record.get("expectation")
    if not isinstance(exp, dict):
        return None
    expectation = {k: v for k, v in exp.items() if k not in turn_record.META_KEYS}
    observation = turn_record.flatten_scalars(read)
    scored = turn_record.score_record({"expectation": exp, "observation": read})
    return {
        "prior_turn": prior_record.get("turn_index"),
        "expectation": expectation,
        "observation": observation,
        "score": {"matched": scored.get("matched", 0), "missed": scored.get("missed", 0),
                  "undefined": scored.get("undefined", 0), "per": scored.get("per_bearing") or {}},
    }


def triples_for_wire(triples: list) -> list:
    """The wire shape of A2's triples: ids, lemmas, enums, numbers. Nothing
    else rides."""
    out = []
    for t in triples:
        out.append({
            "i": t.get("i"), "k": t.get("k"),
            "s": t.get("s") if t.get("s") else UNDEFINED,
            "v": t.get("v"),
            "o": t.get("o") if t.get("o") is not None else UNDEFINED,
            "ok": t.get("ok"),
            "neg": bool(t.get("neg")), "mod": t.get("mod"), "con": list(t.get("con") or []), "t": t.get("t"),
            "prov": t.get("prov"), "link": t.get("link"), "os": list(t.get("os") or []),
            # the load: amount-shaped numbers only; an identifier-shaped one
            # is dropped here as well as at the parser (two doors, one rule);
            # a SEATED object carries none -- its numbers are part of its
            # name ("Rule 56" is ref_1, not ref_1 plus 56; refuter, 2026-09-19)
            "num": [] if t.get("ok") == "seat" else [str(n) for n in (t.get("num") or []) if not _identifier_number(str(n))],
        })
    return out


def in_reading_order(wire_triples: Iterable[dict]) -> bool:
    last = (-1, -1)
    for t in wire_triples:
        k = (int(t.get("i", -1)), int(t.get("k", -1)))
        if k < last:
            return False
        last = k
    return True


def compose(*, direction: str, picked: bool, turn: int, triples: list, verb_owner_set: Optional[dict],
            up: Optional[dict], ask_prev: Optional[dict], seatmap_names: set, proper_tokens: set) -> dict:
    """Build the payload, then mask until the refuter returns []."""
    d, p = validate_direction(direction, picked)
    vos = verb_owner_set if isinstance(verb_owner_set, dict) else {}
    ep = {
        "triples": triples_for_wire(triples),
        "hydronic": {"direction": UNDEFINED, "reason": HYDRONIC_UNDEFINED_REASON,
                     "counts": _hydronic_counts(vos)},
        "D": vos.get("D") if isinstance(vos.get("D"), int) else UNDEFINED,
        "T": vos.get("T") if isinstance(vos.get("T"), (int, float)) else UNDEFINED,
        "N": vos.get("N") if isinstance(vos.get("N"), (int, float)) else UNDEFINED,
        "masked": 0,
    }
    payload = {
        "v": PAYLOAD_VERSION,
        "direction": d,
        "picked": p,
        "turn": int(turn),
        "EP": ep,
        "UP": up if isinstance(up, dict) else None,
        "up_reason": None if isinstance(up, dict) else "no prior seal",
        "ask_prev": ask_prev if isinstance(ask_prev, dict) else None,
    }
    masked = _mask(payload, seatmap_names, proper_tokens)
    payload["EP"]["masked"] = masked
    leak = name_leak(payload, seatmap_names, proper_tokens)
    if leak:
        # cannot happen after _mask; if it does, the payload must NOT leave
        raise RuntimeError("A4 refuter tripped after masking: %s" % sorted(leak)[:5])
    return payload


def _hydronic_counts(vos: dict) -> dict:
    counts = vos.get("counts") if isinstance(vos.get("counts"), dict) else {}
    hyd = counts.get("hydronic") if isinstance(counts.get("hydronic"), dict) else {}
    return {k: int(v) for k, v in hyd.items() if isinstance(v, int)}


# ===========================================================================
# The A4 refuter
# ===========================================================================
def _tokens(s: str) -> list:
    return [t for t in re.split(r"[^a-z0-9§.]+", s.lower()) if t]


def _lexical_slots(payload: Any) -> list:
    """(container, key, kind) for every slot that can carry a MEMBER-DERIVED
    string: a triple's ``o`` (lexical / verb) and its contrast markers
    (kind ``word``), its ``v`` (kind ``verb``), and the prior ask's ``o`` /
    ``v``. Keys, ids and enums are the instrument's own vocabulary and are
    not in the set -- a seat that happens to be named "state" or "model"
    must not make the payload's own field names read as a leak.

    A verb lemma is checked against PROPER names only: a clause-subject
    seat named *allow* or *grant* is a process the parser seated, and the
    verb *allow* in another row is a verb, not that seat. An object word
    is checked against every name -- a lexical object equal to a seat's
    name is that seat, and it must ride as the id or not at all."""
    out: list = []
    if not isinstance(payload, dict):
        return out
    for t in ((payload.get("EP") or {}).get("triples") or []):
        if not isinstance(t, dict):
            continue
        if t.get("ok") in ("lex", "verb"):
            out.append((t, "o", "word"))
        out.append((t, "v", "verb"))
        con = t.get("con")
        if isinstance(con, list):
            for i in range(len(con)):
                out.append((con, i, "word"))
        num = t.get("num")
        if isinstance(num, list):
            for i in range(len(num)):
                out.append((num, i, "word"))     # a number that is a reference's token is a name
    ap = payload.get("ask_prev")
    if isinstance(ap, dict):
        if ap.get("ok") in ("lex", "verb"):
            out.append((ap, "o", "word"))
        out.append((ap, "v", "verb"))
    return out


def _slot_leaks(val: str, kind: str, names: set, proper: set) -> bool:
    if kind == "verb":
        return _leaks(val, set(), proper)
    if kind == "word" and _identifier_number(val):
        return True
    return _leaks(val, names, proper)


def name_leak(payload: Any, seatmap_names: set, proper_tokens: set) -> set:
    """The A4 refuter: the seat-map names / proper tokens that appear in a
    member-derived slot of the payload. Empty set = clean. Whole names are
    matched as word sequences; entity and reference tokens (EEOC ·
    Commission · West · Rule · CFR · 1614.109) are matched one by one."""
    leak: set = set()
    names = {n.strip().lower() for n in seatmap_names if isinstance(n, str) and n.strip() and n.strip().lower() != "i"}
    for container, key, kind in _lexical_slots(payload):
        val = container[key]
        if not isinstance(val, str) or val in (UNDEFINED, MASKED):
            continue
        if _slot_leaks(val, kind, names, proper_tokens):
            leak.add(val.lower())
    return leak


def _leaks(value: str, names: set, proper: set) -> bool:
    # the seal spells a compound with underscores (turn_record._seal_token);
    # a name is a name in either spelling
    v = value.lower().replace("_", " ")
    if v in names:
        return True
    for tok in _tokens(v):
        if tok in proper:
            return True
    for n in names:
        if " " in n and n in v:
            return True
    return False


def _identifier_number(value: str) -> bool:
    """A numeric word that identifies rather than measures (a docket, an
    SSN, a phone): more than six digits, or digit groups joined by
    hyphens/dots. Mirrors clause_parser.is_identifier_number for the slots
    the parser did not size."""
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return False
    if len(digits) > 6:
        return True
    return bool(re.match(r"^\d+([-./]\d+)+$", value.strip())) and len(digits) >= 5


def _mask(payload: dict, names: set, proper: set) -> int:
    """Replace any member-derived string that leaks with ``masked``. Only
    the lexical slots can carry words; ids and enums cannot leak."""
    masked = 0
    nm = {n.strip().lower() for n in names if isinstance(n, str) and n.strip() and n.strip().lower() != "i"}
    for container, key, kind in _lexical_slots(payload):
        val = container[key]
        if isinstance(val, str) and val not in (UNDEFINED, MASKED) and _slot_leaks(val, kind, nm, proper):
            container[key] = MASKED
            masked += 1
    return masked


def serialize(payload: dict) -> str:
    """The exact bytes a lane prompt carries. Deterministic."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
