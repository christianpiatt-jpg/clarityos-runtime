"""
lane_intersect.py — #366 A7. Consolidation: intersection, not the harmonizer.

Lanes read the SAME rows (they are shared by construction: every lane
receives the identical EP/UP payload) along one axis each:

    time      sequence -- done · pending · undone, by tense and modality
    ambient   the field -- what the row does to the pressure around the seats
    role      obligation -- who owes what to whom on the row

Each lane emits, per row, three values::

    state      ∈ {met, transferred, avoided, violated, undefined}
    direction  ∈ {"s->o", "o->s", "undefined"}
    mass       a number in [0, 1], or "undefined"

R-366-F (CT-1 2026-09-19): ``lane_intersect`` consolidates the lanes'
emitted values per row. Robust = UNANIMOUS on state and direction; anything
less = contested, and the split (which lane said what) is carried to A8. A
row every lane left undefined is neither: it is an undefined row (D5), and
the count of those is reported.

A lane's reply is parsed strictly: the first JSON object in the text, with
``rows`` as a list of ``{i, state, direction, mass}``. Anything unparseable,
or a value outside the vocabulary, reads ``undefined`` for that cell -- a
no-basis lane is a different kind than a disagreeing one, and the reason is
kept beside the rows.

The contract sections (§15 time · §16 ambient · §17 role of
COMMUNICATIONS_CONTRACT v1.8.x) do not exist yet in the Library; the ids
below name where they will sit, and the frames below ARE the contract text
this build ships. The frame is the instrument's instruction to a lane --
keys, enums and ids only; no member text, no name.
"""
from __future__ import annotations

import json
import re
from typing import Any, Optional

LANES: tuple = ("time", "ambient", "role")
LANE_CONTRACT_IDS: dict = {
    "time":    "COMMUNICATIONS_CONTRACT.v1.8.x.s15.time",
    "ambient": "COMMUNICATIONS_CONTRACT.v1.8.x.s16.ambient",
    "role":    "COMMUNICATIONS_CONTRACT.v1.8.x.s17.role",
}
ROW_STATES: tuple = ("met", "transferred", "avoided", "violated", "undefined")
ROW_DIRECTIONS: tuple = ("s->o", "o->s", "undefined")
UNDEFINED: str = "undefined"
LANE_RETURN_VERSION: str = "lane.v1"

_AXIS_TEXT: dict = {
    "time": (
        "axis=time. Read each row as a point in a sequence. state: met when the row's act is "
        "completed (past or present tense, no negation, mod event/reported); transferred when the act "
        "moved to another seat; avoided when a negated or counterfactual row withholds the act; violated "
        "when an obligation or expected row is negated; undefined when tense and modality do not settle it."
    ),
    "ambient": (
        "axis=ambient. Read each row for what it does to the field between its seats. state: met when the "
        "row lowers pressure on o; transferred when it moves pressure to a third seat (os); avoided when it "
        "withholds a response the field expected; violated when it raises pressure on a seat under an "
        "obligation; undefined when the field is not bent by the row."
    ),
    "role": (
        "axis=role. Read each row as an obligation between seats. state: met when s performed what the "
        "role owes o; transferred when the obligation was handed to another seat; avoided when s did not "
        "act on an obligation without refusing it; violated when s acted against it; undefined when no "
        "obligation is on the row."
    ),
}


def lane_frame(lane: str, direction: str) -> str:
    """The first lines of a lane prompt. No member text, no names."""
    if lane not in LANES:
        raise ValueError("unknown lane %r" % lane)
    return (
        "[ClarityOS ep-up.v1] lane=%s direction=%s contract=%s\n"
        "Input: one JSON object. EP.triples[i] is a row: s (seat id) v (verb lemma) o (seat id, lemma, or undefined) "
        "ok (seat|lex|verb|undefined) neg mod con t prov link os num. Seat ids are opaque; never guess a name. "
        "UP compares the prior turn's sealed expectation with this turn's observation; null means no prior seal.\n"
        "%s\n"
        "direction: s->o when the row's pressure runs from s to o, o->s when it runs back, undefined otherwise. "
        "mass: the share of this turn's load the row carries, 0 to 1, or \"undefined\".\n"
        "Output: ONLY a JSON object {\"v\":\"lane.v1\",\"lane\":\"%s\",\"rows\":[{\"i\":<row index>,\"state\":<state>,"
        "\"direction\":<direction>,\"mass\":<number or \"undefined\">}, ...]} with one entry per row index 0..n-1. No prose."
        % (lane, direction, LANE_CONTRACT_IDS[lane], _AXIS_TEXT[lane], lane)
    )


def lane_prompt(lane: str, direction: str, serialized_payload: str) -> str:
    return lane_frame(lane, direction) + "\n\n" + serialized_payload


# ===========================================================================
# Parsing a lane's reply
# ===========================================================================
def _first_rows_object(text: str):
    """The FIRST complete JSON object in ``text`` that carries ``rows`` --
    decoded from each '{' in turn, so a postscript with a brace after the
    object, or a brace in a preamble, does not void the lane (a greedy
    regex spanned first-'{' to last-'}' and did; refuter, 2026-09-19).
    Returns (obj, None) or (None, reason)."""
    dec = json.JSONDecoder()
    start = text.find("{")
    if start < 0:
        return None, "no JSON object in reply"
    last_err = None
    tries = 0
    while start >= 0 and tries < 20:
        tries += 1
        try:
            obj, _end = dec.raw_decode(text[start:])
            if isinstance(obj, dict) and "rows" in obj:
                return obj, None
            if isinstance(obj, dict):
                last_err = "rows missing"
            else:
                last_err = "JSON value is not an object"
        except Exception as e:  # noqa: BLE001 -- the reason is the finding
            last_err = "JSON parse failed: %s" % type(e).__name__
        start = text.find("{", start + 1)
    return None, last_err or "no JSON object in reply"


def _coerce_cell(raw: Any) -> dict:
    state = raw.get("state") if isinstance(raw, dict) else None
    direction = raw.get("direction") if isinstance(raw, dict) else None
    mass = raw.get("mass") if isinstance(raw, dict) else None
    if state not in ROW_STATES:
        state = UNDEFINED
    if direction not in ROW_DIRECTIONS:
        direction = UNDEFINED
    if isinstance(mass, bool) or not isinstance(mass, (int, float)) or not (0.0 <= float(mass) <= 1.0):
        mass = UNDEFINED
    else:
        mass = round(float(mass), 4)
    return {"state": state, "direction": direction, "mass": mass}


def parse_lane_return(text: Any, n_rows: int) -> dict:
    """``{"ok": bool, "rows": {i: cell}, "reason": str|None}``. Every row
    index 0..n_rows-1 is present; a row the lane did not answer is
    undefined with reason ``missing``."""
    rows = {i: {"state": UNDEFINED, "direction": UNDEFINED, "mass": UNDEFINED} for i in range(int(n_rows))}
    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "rows": rows, "reason": "empty reply"}
    obj, reason = _first_rows_object(text)
    if obj is None:
        return {"ok": False, "rows": rows, "reason": reason}
    raw_rows = obj.get("rows")
    if not isinstance(raw_rows, list):
        return {"ok": False, "rows": rows, "reason": "rows missing"}
    filled: set = set()
    for r in raw_rows:
        if not isinstance(r, dict):
            continue
        i_raw = r.get("i")
        if isinstance(i_raw, bool):
            continue
        if isinstance(i_raw, float):
            if not i_raw.is_integer():
                continue                          # 1.7 files under no row
            i_raw = int(i_raw)
        if isinstance(i_raw, str) and i_raw.strip().isdigit():
            i_raw = int(i_raw.strip())
        if not isinstance(i_raw, int):
            continue
        if i_raw in rows and i_raw not in filled:
            rows[i_raw] = _coerce_cell(r)          # the first answer for a row stands; a repeat is not a second row
            filled.add(i_raw)
    answered = len(filled)
    return {"ok": answered > 0, "rows": rows, "reason": None if answered == len(rows) else ("answered %d of %d rows" % (answered, len(rows)))}


# ===========================================================================
# The intersection
# ===========================================================================
def lane_intersect(returns: dict, n_rows: int) -> dict:
    """``returns`` = {lane: parse_lane_return(...)}. Per row: unanimous on
    (state, direction) across the lanes that ANSWERED it → robust, mass =
    mean of the numeric masses (undefined when none is numeric); otherwise
    contested with the split; every lane undefined → an undefined row."""
    lanes = [ln for ln in LANES if ln in returns] + [ln for ln in returns if ln not in LANES]
    robust: dict = {}
    contested: dict = {}
    undefined_rows: list = []
    for i in range(int(n_rows)):
        cells = {ln: (returns[ln].get("rows") or {}).get(i) for ln in lanes}
        cells = {ln: c for ln, c in cells.items() if isinstance(c, dict)}
        answered = {ln: c for ln, c in cells.items() if c.get("state") != UNDEFINED or c.get("direction") != UNDEFINED}
        if not answered:
            undefined_rows.append(i)
            continue
        states = {c["state"] for c in answered.values()}
        dirs = {c["direction"] for c in answered.values()}
        masses = [c["mass"] for c in answered.values() if isinstance(c.get("mass"), (int, float))]
        mass = round(sum(masses) / len(masses), 4) if masses else UNDEFINED
        if len(states) == 1 and len(dirs) == 1 and len(answered) == len(cells) and len(cells) == len(lanes):
            robust[i] = {"state": next(iter(states)), "direction": next(iter(dirs)), "mass": mass, "lanes": len(answered)}
        else:
            contested[i] = {"split": {ln: dict(c) for ln, c in cells.items()}, "mass": mass,
                            "states": sorted(states), "directions": sorted(dirs), "lanes": len(answered)}
    return {
        "v": "intersect.v1",
        "n_lanes": len(lanes),
        "lanes": lanes,
        "robust": robust,
        "contested": contested,
        "undefined_rows": undefined_rows,
        "lane_reasons": {ln: returns[ln].get("reason") for ln in lanes},
    }


def row_values(intersection: dict) -> dict:
    """{row index: {"state","direction","mass","robust": bool}} for the
    ledger and the reassembler; contested rows carry their split's majority
    ONLY as ``candidates``, never as a state -- their state is undefined."""
    out: dict = {}
    for i, v in (intersection.get("robust") or {}).items():
        out[int(i)] = {"state": v["state"], "direction": v["direction"], "mass": v["mass"], "robust": True}
    for i, v in (intersection.get("contested") or {}).items():
        out[int(i)] = {"state": UNDEFINED, "direction": UNDEFINED, "mass": v.get("mass", UNDEFINED), "robust": False,
                       "candidates": v.get("states"), "split": v.get("split")}
    return out
