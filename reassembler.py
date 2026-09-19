"""
reassembler.py — #366 A8. The return-loop transformer: algebra → names → one
reading + one ask.

Names are restored ON-MACHINE from the seat map; no model saw them and the
pilot never sees an id. The output is the QC_Post shape: at most three
clauses, tone-neutral, each a three-token row

    <seat> – <verb> – performed | not performed | transferred | undefined

with the consolidation under it (robust k/N or contested, mass), the
relation being read named first (specimen 8b: two relations averaged under
one name is the defect), and ``undefined`` rendered when the row count
under a claim is 0 (specimen 8a). The reading's own ELINS check (the
verb-owner counts of the reading text) rides in ``meta`` and is acted on by
nothing.

THE ASK (#371) fires iff the asker holds a seat in the relation: A0 appears,
or a seat whose name is one of the author's declared classes. It is exactly
one row read back, no adjectives::

    (seat, verb, object) · conserved: <quantity> · direction: <seat→seat>
    · load: <numbers> · cell: <the unread cell between UP.expectation and
    UP.observation>

and it is recorded with the turn (on the seal) in id form, so the next
turn's UP can difference the answer against it. Ambient runs carry no ask.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from seat_ledger import SeatMap, SEAT_AUTHOR, SEAT_PRONOUN, SEAT_INSTRUMENT

UNDEFINED: str = "undefined"
MAX_CLAUSES: int = 3

_PERFORMED: dict = {
    "met": "performed",
    "violated": "not performed",
    "avoided": "not performed",
    "transferred": "transferred",
    UNDEFINED: UNDEFINED,
}
_CONSERVED: dict = {
    "obligation": "obligation",
    "expected": "expectation",
    "conditional": "condition",
    "counterfactual": "condition",
    "reported": "report",
    "event": "act",
}
_BEND_RANK: dict = {"violated": 4, "avoided": 3, "transferred": 2, "met": 1, UNDEFINED: 0}


def _name(sm: SeatMap, sid: Any) -> str:
    if sid is None or sid == UNDEFINED:
        return UNDEFINED
    if not isinstance(sid, str):
        return UNDEFINED
    if sid in sm.by_id:
        return sm.name_of(sid)
    return sid  # a lemma (lexical object) is already a word


def _obj_name(sm: SeatMap, t: dict) -> str:
    if t.get("ok") == "seat":
        return _name(sm, t.get("o"))
    if t.get("ok") in ("lex", "verb"):
        return str(t.get("o"))
    return UNDEFINED


def _row_mass(v: dict) -> float:
    m = v.get("mass")
    return float(m) if isinstance(m, (int, float)) else 0.0


def _other_seat(t: dict) -> Optional[str]:
    if t.get("ok") == "seat" and t.get("o") and t.get("o") != t.get("s"):
        return t.get("o")
    for x in (t.get("os") or []):
        if x and x != t.get("s"):
            return x
    return None


def _relation(sm: SeatMap, triples: list, values: dict, asker: set) -> str:
    """The seat pair the reading is about (specimen 8b: name it, never
    average two under one name): the first ranked row that holds TWO seats,
    asker rows first; a row with one seat names the other side undefined;
    0 rows → undefined."""
    ranked = _ranked(triples, values, asker)
    if not ranked:
        return UNDEFINED
    for idx, t, v in ranked:
        other = _other_seat(t)
        if t.get("s") and other:
            return "%s ↔ %s" % (_name(sm, t.get("s")), _name(sm, other))
    idx, t, v = ranked[0]
    return "%s ↔ %s" % (_name(sm, t.get("s")), UNDEFINED)


def _touches_asker(t: dict, asker: set) -> bool:
    seats = {t.get("s")} | ({t.get("o")} if t.get("ok") == "seat" else set()) | set(t.get("os") or []) | {t.get("link"), t.get("prov")}
    return bool(seats & asker) or bool(t.get("asker"))


def _ranked(triples: list, values: dict, asker: set) -> list:
    rows = []
    for idx, t in enumerate(triples):
        v = values.get(idx)
        if not isinstance(v, dict):
            continue
        if v.get("state") == UNDEFINED and not v.get("robust") and not v.get("candidates"):
            continue
        rows.append((idx, t, v))
    rows.sort(key=lambda r: (
        0 if _touches_asker(r[1], asker) else 1,
        0 if r[2].get("robust") else 1,
        -_BEND_RANK.get(r[2].get("state"), 0),
        -_row_mass(r[2]),
        r[0],
    ))
    return rows


def _split_text(v: dict) -> str:
    """R-366-F: the split carried INTO the reading -- which lane said what,
    state and direction, in lane order."""
    split = v.get("split") if isinstance(v.get("split"), dict) else {}
    parts = ["%s:%s/%s" % (lane, (c or {}).get("state", UNDEFINED), (c or {}).get("direction", UNDEFINED))
             for lane, c in split.items()]
    return " ".join(parts) if parts else "/".join(v.get("candidates") or [UNDEFINED])


def _clause_line(n: int, sm: SeatMap, t: dict, v: dict, n_lanes: int) -> str:
    seat = _name(sm, t.get("s"))
    state = v.get("state") if v.get("robust") else UNDEFINED
    perf = _PERFORMED.get(state, UNDEFINED)
    if t.get("neg") and perf == "performed":
        perf = "performed (negated row)"
    cons = ("robust %d/%d" % (v.get("lanes", n_lanes) if v.get("robust") else 0, n_lanes)) if v.get("robust") else \
        ("contested: %s" % _split_text(v))
    mass = v.get("mass")
    mass_s = ("mass %.2f" % mass) if isinstance(mass, (int, float)) else "mass undefined"
    obj = _obj_name(sm, t)
    return "%d. %s – %s – %s · object: %s · %s · %s · %s" % (n, seat, t.get("v"), perf, obj, t.get("mod"), cons, mass_s)


def build_ask(sm: SeatMap, triples: list, values: dict, asker: set, up: Optional[dict], turn: int) -> Optional[dict]:
    """The one ask, iff the asker holds a seat in the rows."""
    ranked = [r for r in _ranked(triples, values, asker) if _touches_asker(r[1], asker)]
    if not ranked:
        # the asker holds a seat but no row carried a value: the ask is the
        # first asker row, read back with undefined load
        for idx, t in enumerate(triples):
            if _touches_asker(t, asker):
                ranked = [(idx, t, {"state": UNDEFINED, "direction": UNDEFINED, "mass": UNDEFINED})]
                break
    if not ranked:
        return None
    idx, t, v = ranked[0]
    direction = v.get("direction") if v.get("direction") in ("s->o", "o->s") else UNDEFINED
    other = t.get("o") if t.get("ok") == "seat" else ((t.get("os") or [None])[0] if t.get("os") else None)
    if direction == "s->o":
        dir_ids = (t.get("s"), other)
    elif direction == "o->s":
        dir_ids = (other, t.get("s"))
    else:
        dir_ids = (t.get("s"), other)
    cell = _unread_cell(up)
    load = {"mass": v.get("mass") if isinstance(v.get("mass"), (int, float)) else UNDEFINED, "num": list(t.get("num") or [])}
    ask = {
        "row": idx, "s": t.get("s"), "v": t.get("v"), "o": t.get("o") if t.get("o") is not None else UNDEFINED, "ok": t.get("ok"),
        "conserved": _CONSERVED.get(t.get("mod"), "act"),
        "direction": [dir_ids[0] or UNDEFINED, dir_ids[1] or UNDEFINED],
        "load": load, "cell": cell, "turn": int(turn),
    }
    if not v.get("robust") and isinstance(v.get("split"), dict):
        # R-366-F: a contested row's split rides the ask (lane -> state/direction)
        ask["split"] = {lane: {"state": (c or {}).get("state", UNDEFINED), "direction": (c or {}).get("direction", UNDEFINED)}
                        for lane, c in v["split"].items()}
    return ask


def _unread_cell(up: Optional[dict]) -> dict:
    """The cell between the prior seal and this read. Status tokens carry
    no whitespace: the ask is stored on the seal under the prose guard."""
    if not isinstance(up, dict):
        return {"status": "no_prior_seal", "keys": []}
    per = ((up.get("score") or {}).get("per") or {})
    # only a CLAIMED key can be a cell between a measurement and a
    # measurement: the four physics bearings score_record always lists are
    # structurally unread on the thread path (physics does not run there)
    # and are not the missing middle of this turn
    claimed = set((up.get("expectation") or {}).keys())
    undefined = sorted(k for k, s in per.items() if s == "undefined" and k in claimed)
    missed = sorted(k for k, s in per.items() if s == "missed" and k in claimed)
    if undefined:
        return {"status": "unread", "keys": undefined}
    if missed:
        return {"status": "missed", "keys": missed}
    return {"status": "met", "keys": []}


def render_ask(sm: SeatMap, ask: Optional[dict]) -> Optional[str]:
    if not isinstance(ask, dict):
        return None
    s = _name(sm, ask.get("s"))
    o = _name(sm, ask.get("o")) if ask.get("ok") == "seat" else (ask.get("o") if ask.get("ok") in ("lex", "verb") else UNDEFINED)
    d = ask.get("direction") or [UNDEFINED, UNDEFINED]
    load = ask.get("load") or {}
    mass = load.get("mass")
    nums = load.get("num") or []
    load_s = ("mass %.2f" % mass) if isinstance(mass, (int, float)) else "mass undefined"
    if nums:
        load_s += " · " + " · ".join(str(n) for n in nums)
    cell = ask.get("cell") or {}
    keys = cell.get("keys") or []
    cell_s = str(cell.get("status", UNDEFINED)).replace("_", " ") + ((": " + ", ".join(keys)) if keys else "")
    split = ask.get("split") if isinstance(ask.get("split"), dict) else None
    split_s = (" · split: " + " ".join("%s:%s/%s" % (lane, c.get("state"), c.get("direction")) for lane, c in split.items())) if split else ""
    return "ask: (%s, %s, %s) · conserved: %s · direction: %s→%s · load: %s · cell: %s%s — ?" % (
        s, ask.get("v"), o, ask.get("conserved"), _name(sm, d[0]), _name(sm, d[1]), load_s, cell_s, split_s,
    )


def _shape_line(shape: Optional[dict]) -> Optional[str]:
    """The v24 response_shape (direction · phase · risk · sections), when the
    envelope cascade produced one this turn. Enum words only; omitted when
    absent -- never a default printed as a reading."""
    if not isinstance(shape, dict) or not shape:
        return None
    parts = []
    for k in ("direction", "phase", "risk"):
        v = shape.get(k)
        if isinstance(v, str) and v:
            parts.append("%s %s" % (k, v))
    secs = shape.get("sections")
    if isinstance(secs, list) and secs:
        parts.append("sections " + "/".join(str(s) for s in secs[:3]))
    return ("field: " + " · ".join(parts)) if parts else None


def reassemble(*, triples: list, values: dict, seatmap: SeatMap, asker_seats: set, up: Optional[dict],
               n_lanes: int, turn: int, undefined_rows: Optional[list] = None, contested_n: int = 0,
               provisioned: bool = True, shape: Optional[dict] = None, halt: Optional[dict] = None) -> dict:
    """Algebra → the reading. Returns ``{text, clauses, relation, ask,
    ask_text, rows, rows_read, robust, contested, undefined, meta}``.

    ``halt`` (a dict ``{step, constraint, description}``) renders the halt's
    rationale to the pilot and nothing else: the workflow stopped, nothing
    was sent, and it is never auto-resumed."""
    asker = set(asker_seats or set())
    n_rows = len(triples)
    if isinstance(halt, dict):
        text = "halt: %s — the workflow stopped at %s on %s; nothing was sent to a model and the turn is not resumed" % (
            halt.get("description") or UNDEFINED, halt.get("step") or UNDEFINED, halt.get("constraint") or UNDEFINED)
        return {"text": text, "clauses": [], "relation": UNDEFINED, "ask": None, "ask_text": None,
                "rows": n_rows, "rows_read": 0, "robust": 0, "contested": 0, "undefined": n_rows,
                "asker_holds_seat": False, "halted": True, "meta": {"elins_check": _elins_check(text)}}
    ranked = _ranked(triples, values, asker)
    if not provisioned:
        # a mock's rows are not a reading: nothing under the head, no ask
        ranked = []
    robust_n = sum(1 for _, _, v in ranked if v.get("robust"))
    contested_n = sum(1 for _, _, v in ranked if not v.get("robust"))
    undefined_n = n_rows - len(ranked)
    relation = _relation(seatmap, triples, values, asker) if provisioned else UNDEFINED
    asker_holds = any(_touches_asker(t, asker) for t in triples)
    lines: list = []
    if not provisioned:
        head = "sovereign seat not provisioned — no local model answered; %d rows carried no reading" % n_rows
    elif n_rows == 0:
        head = "reading: undefined — 0 rows (the turn carried no clause the parser could attribute)"
    elif not ranked:
        head = "reading: undefined — 0 of %d rows carried a value (%d lanes returned no reading)" % (n_rows, n_lanes)
    else:
        head = "reading · relation: %s · rows %d · robust %d · contested %d · undefined %d" % (
            relation, n_rows, robust_n, contested_n, undefined_n)
    lines.append(head)
    sl = _shape_line(shape)
    if sl and provisioned:
        lines.append(sl)
    clauses = []
    for n, (idx, t, v) in enumerate(ranked[:MAX_CLAUSES], start=1):
        line = _clause_line(n, seatmap, t, v, n_lanes)
        clauses.append({"row": idx, "text": line})
        lines.append(line)
    # ONE gate for the ask: build_ask returns None when no row touches the
    # asker's seats (a second, outer gate on asker_holds was redundant and
    # made neither observable by a single mutation -- the harness, 2026-09-19)
    ask = build_ask(seatmap, triples, values, asker, up, turn) if provisioned else None
    ask_text = render_ask(seatmap, ask)
    if ask_text:
        lines.append(ask_text)
    text = "\n".join(lines)
    return {
        "text": text,
        "clauses": clauses,
        "relation": relation,
        "ask": ask,
        "ask_text": ask_text,
        "rows": n_rows,
        "rows_read": len(ranked),
        "robust": robust_n,
        "contested": contested_n,
        "undefined": undefined_n,
        "asker_holds_seat": bool(asker_holds),
        "halted": False,
        "meta": {"elins_check": _elins_check(text), "shape": bool(sl)},
    }


def _elins_check(text: str) -> dict:
    """The reading's own counts (verb-owner set), acted on by nothing."""
    try:
        import primitives_extract
        prim = primitives_extract.extract_primitives(text or "")
        return {k: len(prim.get(k) or []) for k in ("P1", "P2", "P3", "P4", "Ts", "Te", "M")}
    except Exception as e:  # noqa: BLE001
        return {"status": "ABSENT", "reason": type(e).__name__}
