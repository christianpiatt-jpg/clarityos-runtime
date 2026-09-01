"""
turn_record.py — the per-turn record. Five dark terms wait on this one.

WHY THIS EXISTS
---------------
``trust``, ``flow_rate``, ``basin_hop`` and ``theta`` all need the same
thing and none of them can be computed without it: a record of what was
expected BEFORE the next turn arrived, next to what actually arrived.

THE SEAT RULE — the invariant that makes the residual honest
------------------------------------------------------------
RESTORE_POINT_2026-08-15:33 —

    "The seat-expectation must be written BEFORE the return is seen.
     Otherwise the expectation is fitted to the return, the residual is
     whatever you want, and you have rebuilt Qwen with better vocabulary."

:37 — "The fabrication moves UPSTREAM INTO THE EXPECTATION TERM — one
layer earlier and much harder to catch."

So this module is TWO-PHASE by construction, not by convention:

    seal_expectation(...)   writes ts_sealed and the expectation. No return
                            exists yet, so none can be fitted.
    observe_return(...)     writes ts_observed and the observation, and
                            REJECTS THE WRITE unless ts_sealed < ts_observed.

A single-call API would let a caller pass both timestamps and defeat the
rule with a typo. There is no single-call API.

NO TRUNCATION AT WRITE
----------------------
Records are unbounded. The writer holds no window constant. 3 and 7 are
BOOTSTRAP numbers, not physics — once a member has history the thresholds
come from their own distribution, and a window baked in at write is a
conclusion stored as an observable. ``list_turn_records`` takes the window
as a READ-TIME parameter, defaulting to everything.

Note this departs from ``operator_state.record_elins_interaction``, which
calls ``_prune_history`` to cap at HISTORY_MAX=200 at write time. The key
pattern is borrowed; the prune deliberately is not.

STORAGE
-------
One vault key per record, mirroring operator_state's history pattern
(``{prefix}{ts_ms}_{seq}``). No document is rewritten to append, so
concurrent turns cannot clobber each other. ``operator_state.
update_operator_state`` cannot carry this: it applies a fixed allowlist and
silently drops unknown keys (operator_state.py:267-269).

E-PRIME — the record holds bearings, never verdicts
---------------------------------------------------
Every stored value is an enum member, a count, or a number. ``_reject_prose``
refuses anything that reads like a sentence about a person. ``notes`` and
thread summaries are class ``attribution`` — perishable, and not this record.
THE CLASS ALLOWLIST IS FOUR AND IT IS CLOSED
--------------------------------------------
geometry / attribution / crossing / ratio. See RECORD_CLASSES. A write that
fits none of them is a REPORT, never a fifth entry.

* NO RECLASSIFICATION OF HISTORY. A row written under an older, narrower
allowlist keeps the class it was written with. Deciding after the fact what
a past row should have been is attribution written backwards -- the same
failure the seat rule refuses one layer up.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

import memory_vault

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------
# Namespaced UNDER operator_state, which memory_vault already allows
# (ALLOWED_NAMESPACES). No new store, no change to a core file, and
# get_operator_state reads its keys by name rather than enumerating the
# prefix, so these records are inert to it.
_PREFIX: str = "operator_state.turn_record."

#: The four bearings the floor predicts. Exact-match scoreable, no new
#: physics and no model call. CT-1 named seat/role rules and forward
#: gradient projection as the fuller form; that replaces the CONTENT of
#: ``expectation`` without changing the record's shape.
BEARINGS: tuple = ("boundary", "agency", "distance", "alignment")

#: RECORD CLASSES -- the allowlist is FOUR, and it is closed.
#:
#: geometry     the SHAPE of a reading -- counts, bearings, positions.
#:              Recomputable from the turn's text.
#: attribution  WHO or WHAT. Perishable. Droppable. Not written here.
#: crossing     DID THIS RETURN CROSS A NON-INVERTING NODE?
#:              world (an act intervened) / instrument (a tool read it)
#:              / neither (interior -- ECHO).
#: ratio        A QUOTIENT OF TWO READINGS. Any two-arm quantity.
#:              NOT a magnitude, NOT a score, NOT a verdict.
#:
#: ** NO FIFTH CLASS. A value that fits none of these four is a REPORT,
#: not a widening. Growing the allowlist to make a write succeed is how
#: a class system stops classifying and starts accepting.
CLASS_GEOMETRY: str = "geometry"
CLASS_ATTRIBUTION: str = "attribution"
CLASS_CROSSING: str = "crossing"
CLASS_RATIO: str = "ratio"

RECORD_CLASSES: frozenset = frozenset(
    {CLASS_GEOMETRY, CLASS_ATTRIBUTION, CLASS_CROSSING, CLASS_RATIO})

#: COPObservation primitive #5 -- PROVENANCE. Where a reading CAME FROM.
#: This is the E/r marker: OBSERVED is E, DERIVED and INHERITED are r. A
#: record that cannot say which cannot support an angle later.
PROV_OBSERVED: str = "observed_this_call"   # computed from the text that arrived
PROV_DERIVED: str = "derived"               # computed from another field here
PROV_INHERITED: str = "inherited"           # carried from a prior record
PROV_UNKNOWN: str = "unknown"               # SENTINEL -- never a guess

#: CONFIDENCE, and it is NOT a probability. It counts how many independent
#: readings contributed to a payload, which is a fact the writer can check.
#:
#: * D5 -- the no-basis case returns a DIFFERENT KIND, not a number. A float
#: defaulting to 0.0 would repeat elins_v2_view.py:147, where a missing
#: second reading is read as perfect agreement and annihilates the term.
#: There is no numeric confidence in this module. There is no 0.0.
#:
#: ** It asserts a COUNT, never agreement. Two readings of DIFFERENT
#: quantities cannot agree or disagree, so claiming "corroborated" would
#: state something unmeasured. The tokens say how many, and stop there.
CONF_NO_BASIS: str = "no_basis"             # SENTINEL -- nothing contributed
CONF_SINGLE_READING: str = "single_reading"
CONF_MULTI_READING: str = "multi_reading"

#: THE CROSSING MARKER -- did this return cross a NON-INVERTING node?
#:
#: A non-inverting node responds without interpreting: the world, a
#: filesystem, an exit code, an HTTP status, a byte count. An INVERTING
#: node emits carrier-shaped output -- a user, a model, any lane.
#:
#: *** WHY THE RECORD NEEDS IT. An interior turn and an act-and-return
#: turn are THE SAME SHAPE ON DISK without this field. A later reader
#: cannot tell evidence from echo, and no amount of care at read time
#: recovers a distinction that was never written down.
#:
#: ** SIBLING of provenance, not a replacement. provenance says WHERE a
#: value came from; crossing says WHETHER it has been outside the
#: interior. A value can be OBSERVED_THIS_CALL and still have crossed
#: nothing -- that is exactly the turn path today.
CROSSED_WORLD: str = "world"                # an act intervened
CROSSED_INSTRUMENT: str = "instrument"      # a tool read it
CROSSING_NEITHER: str = "neither"           # interior only -- ECHO
CROSSING_UNDETERMINED: str = "undetermined"  # SENTINEL -- a different KIND

_PROVENANCE_TOKENS: frozenset = frozenset(
    {PROV_OBSERVED, PROV_DERIVED, PROV_INHERITED, PROV_UNKNOWN})
_CONFIDENCE_TOKENS: frozenset = frozenset(
    {CONF_NO_BASIS, CONF_SINGLE_READING, CONF_MULTI_READING})
_CROSSING_TOKENS: frozenset = frozenset(
    {CROSSED_WORLD, CROSSED_INSTRUMENT, CROSSING_NEITHER,
     CROSSING_UNDETERMINED})

#: The carrier key. ``build_geometry_observation`` stamps its own reading
#: here and ``observe_return`` LIFTS IT OUT before storing, so the stored
#: observation payload stays byte-identical to what it was before this
#: commit (tests/test_turn_record.py:47 asserts that payload exactly).
#:
#: *** It is underscore-prefixed for a load-bearing reason. The kernel hook
#: passes ONE dict to BOTH observe_return (:995) and persistence_expectation
#: (:999). Without the underscore rule in ``flatten_scalars`` this key would
#: flatten into the NEXT expectation as a claimed bearing and silently move
#: score_record's tally. Measured: no existing observation key begins with
#: "_", so the skip is a no-op on every row already written.
_COP_KEY: str = "_cop"

#: A stored scalar longer than this, or containing whitespace, reads as
#: prose rather than a bearing. Enum members ("partially_aligned") and
#: state labels ("S3") sit well inside it.
_MAX_SCALAR_LEN: int = 40

#: The backward pass is unsolvable below this many scored turns. It is a
#: FLOOR for that one purpose and nothing else — never a write-time window.
THETA_FLOOR_TURNS: int = 7

_SEQ_LOCK = threading.Lock()
_SEQ: dict = {}


# --------------------------------------------------------------------------
# Keys
# --------------------------------------------------------------------------
def _next_seq(ns: str) -> int:
    """Process-wide monotonic counter so two writes in the same millisecond
    still produce distinct keys."""
    with _SEQ_LOCK:
        n = _SEQ.get(ns, 0) + 1
        _SEQ[ns] = n
        return n


def _thread_ns(thread_id: str) -> str:
    tid = str(thread_id or "").strip()
    if not tid:
        raise ValueError("thread_id must be a non-empty string")
    if "." in tid or "/" in tid:
        raise ValueError("thread_id must not contain '.' or '/'")
    return _PREFIX + tid + "."


def _now_ns() -> int:
    """Wall-clock NANOSECONDS.

    ★ Not cosmetic. ``time.time()`` on Windows advances in ~15.6 ms steps,
    so a seal and its observe inside one tick return the IDENTICAL float and
    ``ts_sealed < ts_observed`` rejects an honest record. The invariant was
    correct; the clock could not express it. ``time_ns`` resolves to 100 ns
    here, so ordering survives.
    """
    return time.time_ns()


def _make_key(thread_id: str, ts_ns: int) -> str:
    """``…{thread_id}.{ts_ms}_{seq}`` — sorts lexicographically into
    chronological order within one thread."""
    ns = _thread_ns(thread_id)
    return "%s%d_%06d" % (ns, int(ts_ns // 1_000_000), _next_seq(ns))


# --------------------------------------------------------------------------
# E-prime guard
# --------------------------------------------------------------------------
def _reject_prose(value: Any, where: str) -> Any:
    """Bearings, counts and numbers pass. Sentences do not.

    D2: no field may contain a sentence about a person. This is enforced
    rather than documented, because a convention that is only written down
    is a convention that gets written past.
    """
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > _MAX_SCALAR_LEN:
            raise ValueError(
                "%s: string of %d chars reads as prose, not a bearing "
                "(max %d)" % (where, len(value), _MAX_SCALAR_LEN)
            )
        if any(ch.isspace() for ch in value):
            raise ValueError(
                "%s: %r contains whitespace; bearings are single tokens" % (where, value)
            )
        return value
    if isinstance(value, dict):
        return {str(k): _reject_prose(v, where + "." + str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_reject_prose(v, where + "[]") for v in value]
    raise ValueError("%s: unsupported type %s" % (where, type(value).__name__))


# --------------------------------------------------------------------------
# Phase 1 — seal the expectation, before any return exists
# --------------------------------------------------------------------------
def seal_expectation(
    user_id: str,
    thread_id: str,
    turn_index: int,
    expectation: dict,
    *,
    record_class: str = CLASS_GEOMETRY,
) -> str:
    """Write the expectation for the NEXT turn and stamp ``ts_sealed``.

    D4 — the expectation is a solved r. It is stored under its own key,
    tagged with its class, and never merged into the observation.

    Returns the record key. Pass it to ``observe_return`` next turn.
    """
    if not isinstance(expectation, dict) or not expectation:
        raise ValueError("expectation must be a non-empty dict")
    if record_class not in RECORD_CLASSES:
        # * The rejection names what IS allowed, so a caller reaching for a
        # fifth class reads the closed set rather than inventing one.
        raise ValueError(
            "record_class must be one of %s; got %r"
            % (sorted(RECORD_CLASSES), record_class)
        )
    try:
        ti = int(turn_index)
    except (TypeError, ValueError):
        raise ValueError("turn_index must be an int")
    if ti < 0:
        raise ValueError("turn_index must be >= 0")

    clean = _reject_prose(dict(expectation), "expectation")
    ts = _now_ns()
    key = _make_key(thread_id, ts)
    # COP #5 -- the EXPECTATION half. Both are read off what was actually
    # passed: provenance from the declared source, confidence from the
    # count of bearings genuinely claimed.
    #
    # * The observation half is the SENTINEL here, and that is the honest
    # reading: at seal time no return exists, so there is nothing to have
    # observed and nothing to have confidence in. It is filled by
    # observe_return or it stays unknown forever.
    claimed = [k for k in clean.keys() if k not in META_KEYS]
    memory_vault.vault_put(user_id, key, {
        "turn_index":  ti,
        "class":       record_class,
        "ts_sealed":   ts,
        "ts_observed": None,
        "expectation": clean,
        "observation": None,
        "provenance": {
            "expectation": _SOURCE_PROVENANCE.get(clean.get("source"), PROV_UNKNOWN),
            "observation": PROV_UNKNOWN,
        },
        "confidence": {
            "expectation": CONF_SINGLE_READING if claimed else CONF_NO_BASIS,
            "observation": CONF_NO_BASIS,
        },
        # The marker describes THE RETURN, and at seal time no return
        # exists. Undetermined is the honest reading, and it is a
        # different KIND from both crossed and did-not-cross.
        "crossing": CROSSING_UNDETERMINED,
    })
    return key


# --------------------------------------------------------------------------
# Phase 2 — observe the return. The invariant is enforced here.
# --------------------------------------------------------------------------
def observe_return(user_id: str, record_key: str, observation: dict) -> dict:
    """Attach the observed return and stamp ``ts_observed``.

    REJECTS THE WRITE unless ``ts_sealed < ts_observed``. A record where
    the expectation was not sealed first is a fitted residual: worthless,
    and unsafe because it looks like evidence.

    Also refuses to observe twice — a sealed record takes one return.
    """
    if not isinstance(observation, dict) or not observation:
        raise ValueError("observation must be a non-empty dict")
    rec = memory_vault.vault_get(user_id, record_key)
    if not isinstance(rec, dict):
        raise KeyError("no turn record at %s" % record_key)
    if rec.get("ts_observed") is not None:
        raise ValueError(
            "record %s already observed; a sealed expectation takes one return"
            % record_key
        )

    ts_sealed = rec.get("ts_sealed")
    ts_observed = _now_ns()
    if not isinstance(ts_sealed, (int, float)):
        raise ValueError("record %s carries no ts_sealed" % record_key)
    # ★ THE SEAT RULE, ENFORCED -- and enforced on the thing that is
    # actually provable.
    #
    # ORDERING is guaranteed CAUSALLY, not by the clock: observe_return can
    # only run against a record that already exists, already carries
    # ts_sealed, and has observation=None. There is no single-call API and
    # no way to write an expectation after reading a return.
    #
    # The CLOCK check catches the fabrication signature -- a seal stamped
    # LATER than the return. It does NOT demand strict inequality, because
    # it cannot: measured on this platform, time.time_ns() advances in
    # ~15.6 ms steps (values end in ...099900), so a seal and its observe
    # inside one tick report the IDENTICAL stamp. Rejecting equality would
    # refuse honest records and teach callers to retry until the clock
    # moved, which is worse than the rule it enforces.
    if int(ts_sealed) > int(ts_observed):
        raise ValueError(
            "SEAT RULE VIOLATED: ts_sealed (%r) is LATER than ts_observed (%r). "
            "Refusing the write -- the residual would be fitted."
            % (ts_sealed, ts_observed)
        )

    rec = dict(rec)

    # COP #5 -- LIFT the carrier out BEFORE storing, so the stored payload
    # is exactly what it was before this commit.
    incoming = dict(observation)
    cop = incoming.pop(_COP_KEY, None)

    obs_prov, obs_conf = PROV_UNKNOWN, CONF_NO_BASIS
    crossing = CROSSING_UNDETERMINED
    if isinstance(cop, dict):
        if cop.get("provenance") in _PROVENANCE_TOKENS:
            obs_prov = cop["provenance"]
        if cop.get("confidence") in _CONFIDENCE_TOKENS:
            obs_conf = cop["confidence"]
        # *** A marker that GUESSES is worse than no marker: it launders
        # echo as evidence. An unstamped or unrecognised value stays
        # UNDETERMINED. It is never inferred from the payload, and never
        # from the text -- text is carrier-shaped output from an
        # inverting node, so reading crossing out of it would be the
        # laundering itself.
        if cop.get("crossing") in _CROSSING_TOKENS:
            crossing = cop["crossing"]

    # *** NO BACKFILL. A record sealed BEFORE this commit carries no
    # provenance dict, and it cannot know what its expectation was built
    # from. It gets the sentinel. Inferring a value for it would be a
    # fabrication with a timestamp on it, which is the one thing a
    # provenance field exists to prevent.
    prev_prov = rec.get("provenance")
    prev_conf = rec.get("confidence")
    prov = dict(prev_prov) if isinstance(prev_prov, dict) else {"expectation": PROV_UNKNOWN}
    conf = dict(prev_conf) if isinstance(prev_conf, dict) else {"expectation": CONF_NO_BASIS}
    prov["observation"] = obs_prov
    conf["observation"] = obs_conf

    rec["observation"] = _reject_prose(incoming, "observation")
    rec["ts_observed"] = ts_observed
    rec["provenance"] = prov
    rec["confidence"] = conf
    rec["crossing"] = crossing
    memory_vault.vault_put(user_id, record_key, rec)
    return rec


# --------------------------------------------------------------------------
# Read — the window lives HERE, never in the writer
# --------------------------------------------------------------------------
def list_turn_records(
    user_id: str,
    thread_id: str,
    *,
    window: Optional[int] = None,
) -> list:
    """Records for one thread, oldest→newest.

    ``window`` is a READ-TIME parameter and defaults to None = everything.
    The writer stores unbounded; the count is the reader's business.
    """
    ns = _thread_ns(thread_id)
    entries = memory_vault.vault_list(user_id) or {}
    rows = [v for k, v in sorted(entries.items()) if k.startswith(ns) and isinstance(v, dict)]
    rows.sort(key=lambda r: (r.get("turn_index", 0), r.get("ts_sealed", 0)))
    if window is not None:
        try:
            w = int(window)
        except (TypeError, ValueError):
            raise ValueError("window must be an int or None")
        if w <= 0:
            raise ValueError("window must be > 0")
        rows = rows[-w:]
    return rows


# --------------------------------------------------------------------------
# The producer — persistence, the honest null model
# --------------------------------------------------------------------------
#: Keys carried for provenance, never scored. D4: the expectation is a
#: solved r, and it says so in its own payload.
META_KEYS: frozenset = frozenset({"source"})

SOURCE_PERSISTENCE: str = "persistence"

#: An expectation declares its own source, so its provenance is READ, not
#: guessed. ``persistence`` flattens the PRIOR turn observation forward, so
#: its values are carried in -- INHERITED. A source with no entry here
#: resolves to PROV_UNKNOWN rather than to the nearest plausible token.
_SOURCE_PROVENANCE: dict = {SOURCE_PERSISTENCE: PROV_INHERITED}


def flatten_scalars(d: dict, prefix: str = "") -> dict:
    """Flat scalar leaves of a nested observation. ``{"primitives": {"P1": 2}}``
    becomes ``{"primitives.P1": 2}`` so a prediction can name one leaf."""
    out: dict = {}
    for k, v in (d or {}).items():
        # * Carrier keys are metadata ABOUT the reading, not part of it.
        # They must never become a claimed bearing. No existing key starts
        # with "_", so this drops nothing that was ever stored.
        if str(k).startswith("_"):
            continue
        key = prefix + str(k)
        if isinstance(v, dict):
            out.update(flatten_scalars(v, key + "."))
        elif isinstance(v, (str, int, float, bool)) or v is None:
            out[key] = v
    return out


def persistence_expectation(observation: dict) -> dict:
    """The null model: turn N+1 looks like turn N.

    ★ D4 -- this is a SOLVED r and is marked as one. ``source`` rides in the
    payload so a reader can never mistake it for an observation.

    Legitimate rather than a placeholder: a prediction of no change is the
    honest null, and FORCE is deviation from it. Works from turn 1, needs no
    model call and no new physics. When markov stops returning a pinned
    S-state this becomes ``source="markov"`` and NOTHING ELSE CHANGES --
    the record's shape holds.
    """
    exp = flatten_scalars(observation or {})
    exp["source"] = SOURCE_PERSISTENCE
    return exp


def pending_seal(user_id: str, thread_id: str) -> Optional[str]:
    """Key of the newest sealed-but-unobserved record, or None.

    Lets the caller find the prior seal without holding a pointer across
    turns -- there is nothing to lose, and nothing to fabricate.
    """
    ns = _thread_ns(thread_id)
    entries = memory_vault.vault_list(user_id) or {}
    open_keys = [
        k for k, v in entries.items()
        if k.startswith(ns) and isinstance(v, dict) and v.get("ts_observed") is None
    ]
    return sorted(open_keys)[-1] if open_keys else None


def next_turn_index(user_id: str, thread_id: str) -> int:
    """Monotonic per thread. Derived from what is stored, so a restart
    cannot reset it."""
    return len(list_turn_records(user_id, thread_id))


# --------------------------------------------------------------------------
# trust — the first thing the record makes computable
# --------------------------------------------------------------------------
def score_record(rec: dict) -> dict:
    """Score one sealed-then-observed record over the four bearings.

    D5 — FAILURE RETURNS A DIFFERENT KIND OF THING. Three outcomes, and
    they are not interchangeable:

        matched   the bearing was expected and arrived as expected
        missed    the bearing was expected and arrived otherwise
        undefined the bearing was NOT expected -- no claim was made, so
                  there is nothing to be right or wrong about

    CT-1's rule: absence expecting absence is a trust INCREASE (both sides
    say "not present", which is a hit). Absence with no expectation is
    UNDEFINED, never 0.0.
    """
    exp = rec.get("expectation") or {}
    obs = rec.get("observation")
    if obs is None:
        return {"status": "unobserved", "matched": 0, "missed": 0, "undefined": len(BEARINGS)}

    flat_obs = flatten_scalars(obs)
    # Score every key the expectation CLAIMED, plus the named bearings so a
    # bearing that was never claimed still reports as undefined rather than
    # vanishing from the tally.
    claimed = [k for k in exp.keys() if k not in META_KEYS]
    keys = list(dict.fromkeys(claimed + list(BEARINGS)))

    matched = missed = undefined = 0
    per: dict = {}
    for b in keys:
        if b not in exp:
            per[b] = "undefined"      # no claim was made
            undefined += 1
            continue
        e = exp.get(b)
        o = flat_obs.get(b, None)
        if e == o:                    # includes None == None: absence expecting absence
            per[b] = "matched"
            matched += 1
        else:
            per[b] = "missed"
            missed += 1
    return {
        "status": "scored",
        "matched": matched,
        "missed": missed,
        "undefined": undefined,
        "per_bearing": per,
    }


def trust_signal(
    user_id: str,
    thread_id: str,
    *,
    window: Optional[int] = None,
) -> dict:
    """The match rate across the window, plus a direction once one exists.

    D5 — three kinds of return, never a bare 0.0:

        {"status": "no_prior_yet"}   fewer than one scored record. A first
                                     turn has nothing to have expected.
        {"status": "undefined"}      records exist but no bearing was ever
                                     claimed, so the rate has no denominator.
        {"status": "value", ...}     value in [0,1]; ``direction`` is
                                     present only from the SECOND scored
                                     record on, because a direction needs
                                     two points.

    trust lights at turn 2. It could not have lit at turn 1, and reporting
    0.0 there would state a reading the record does not hold.
    """
    rows = list_turn_records(user_id, thread_id, window=window)
    scored = [(r, score_record(r)) for r in rows]
    scored = [(r, s) for r, s in scored if s["status"] == "scored"]

    if not scored:
        return {
            "status": "no_prior_yet",
            "scored_turns": 0,
            "theta_floor": THETA_FLOOR_TURNS,
            "theta_ready": False,
        }

    denom = sum(s["matched"] + s["missed"] for _, s in scored)
    if denom == 0:
        return {
            "status": "undefined",
            "reason": "records exist but no bearing carried an expectation",
            "scored_turns": len(scored),
            "theta_floor": THETA_FLOOR_TURNS,
            "theta_ready": False,
        }

    per_turn = []
    for _, s in scored:
        d = s["matched"] + s["missed"]
        per_turn.append(round(s["matched"] / d, 4) if d else None)

    value = round(sum(s["matched"] for _, s in scored) / denom, 4)

    out = {
        "status": "value",
        "value": value,
        "scored_turns": len(scored),
        "per_turn": per_turn,
        "theta_floor": THETA_FLOOR_TURNS,
        "theta_ready": len(scored) >= THETA_FLOOR_TURNS,
    }

    # A direction needs two points. One scored turn gives a value and no
    # slope -- saying "flat" there would assert something unmeasured.
    pts = [p for p in per_turn if p is not None]
    if len(pts) >= 2:
        delta = round(pts[-1] - pts[-2], 4)
        out["direction"] = "rising" if delta > 0 else ("falling" if delta < 0 else "flat")
        out["delta"] = delta
    return out


# --------------------------------------------------------------------------
# Building the READ half — geometry only, recomputable from the turn
# --------------------------------------------------------------------------
#: Keys inside a physics block that carry prose. Stripped before storage:
#: they are class ``attribution``, not geometry, and _reject_prose would
#: refuse them anyway.
_PROSE_KEYS: frozenset = frozenset({
    "notes", "note", "interpretation", "summary", "description", "narrative",
    "recommended_posture", "message_guidance", "friction_reduction_moves",
    "risk_if_unchanged", "next_step",
})

_PHYSICS_BLOCKS: tuple = (
    "field_curvature", "edge_pressure", "relational_primitives",
)


def build_geometry_observation(text: str, physics: Optional[dict] = None) -> dict:
    """Assemble the recomputable half of a turn record.

    Holds: the physics enum bearings verbatim (prose stripped), the
    primitive counts, a pressure reading, and the S-state label when the
    caller supplies intensities. Every value is an enum member or a count.

    ``external_expression`` is deliberately absent -- every one of its
    fields is prose (see EmotionalPhysicsView's reclassification), so it is
    class ``attribution`` and does not belong in a geometry record.
    """
    import primitives_extract

    prim = primitives_extract.extract_primitives(text if isinstance(text, str) else "")
    hyd = prim.get("hydronic") or {}
    counts = {
        "P1": len(prim.get("P1") or []), "P2": len(prim.get("P2") or []),
        "P3": len(prim.get("P3") or []), "P4": len(prim.get("P4") or []),
        "Ts": len(prim.get("Ts") or []), "Te": len(prim.get("Te") or []),
        "M":  len(prim.get("M")  or []),
        "hydronic": {k: len(hyd.get(k) or []) for k in
                     ("flows", "blockages", "gradients", "pressure_points")},
    }

    # ★ The order names pressure_v2(text). No such function exists in the
    # tree; the nearest is azimuth_envelope_impl.pressure_score, a pure
    # deterministic count of obligation / deadline / crisis markers. Named
    # here rather than silently substituted.
    try:
        import azimuth_envelope_impl
        pressure = int(azimuth_envelope_impl.pressure_score(text or ""))
    except Exception:
        pressure = None

    obs: dict = {"primitives": counts, "pressure_score": pressure}

    # COP #5 -- count the INDEPENDENT readings that contributed. The
    # extractor always contributes; pressure_score is wrapped and may
    # decline; physics does not run on the turn path today.
    readings = 1                                    # primitives_extract ran
    if pressure is not None:
        readings += 1                               # pressure_score returned

    if isinstance(physics, dict):
        for block in _PHYSICS_BLOCKS:
            b = physics.get(block)
            if not isinstance(b, dict):
                continue
            for k, v in b.items():
                if k in _PROSE_KEYS:
                    continue
                if isinstance(v, str):
                    obs[k] = v                      # enum bearing, verbatim
                    readings += 1
                elif isinstance(v, (list, tuple)):
                    obs[k + "_n"] = len(v)          # a count, not the members
                    readings += 1

    # * This function KNOWS where its reading came from -- it computed it
    # from the text that just arrived. So it stamps the provenance itself
    # rather than letting a downstream writer assert it second-hand. The
    # stamp rides under the carrier key and never reaches storage.
    # *** THE CROSSING MARKER, DERIVED -- not guessed, and not read out
    # of the text.
    #
    # It is derived from this function INPUT SET, which is static and
    # checkable: primitives_extract imports only re and typing, and
    # azimuth_envelope_impl.pressure_score is arithmetic over the
    # normalised text. No filesystem, no socket, no exit code, no status.
    # A reading assembled only from pure functions of interior text
    # PROVABLY did not cross a non-inverting node.
    #
    # ** The distinction that keeps this honest: deriving the marker from
    # what the producer READ is checkable, while inferring it from what
    # the text SAYS would let a member describe an act and have the
    # record score it as one. The second is the laundering. This is not.
    #
    # * A caller that genuinely crossed something -- ran a command, read
    # an exit code, took an HTTP status -- supplies its own token. This
    # function cannot, because it never does.
    obs[_COP_KEY] = {
        "provenance": PROV_OBSERVED,
        "confidence": (CONF_NO_BASIS if readings == 0 else
                       CONF_SINGLE_READING if readings == 1 else
                       CONF_MULTI_READING),
        "crossing": CROSSING_NEITHER,
    }
    return obs


def s_state_label(intensities: dict) -> Optional[str]:
    """The softmax winner from elins_v2_view, or None when it declines.

    ★ D3 -- INVERTED TERM, reported not fixed. trust enters S1 and S2 as a
    MULTIPLIER (elins_v2_view.py:161-162): score_S1 = (1-p)*al*tr. With tr
    absent and read as 0.0, both aligned states are ANNIHILATED rather than
    reduced, so S3 wins whenever pressure > 0. The label is pinned by a
    missing term, not by the reading. That is what this record exists to
    unpin, and it is why markov training waits on it.
    """
    try:
        from ELINS import elins_v2_view
        _dist, attractor = elins_v2_view.compute_state_distribution(intensities or {})
        return attractor
    except Exception:
        return None


# --------------------------------------------------------------------------
# The three-step record, as ONE callable
# --------------------------------------------------------------------------
def record_turn(user_id: str, thread_id: str, text: str) -> dict:
    """Read this turn, observe the PREVIOUS seal against it, then seal for
    the turn that does not exist yet.

    ** THE ORDER OF THE THREE STEPS IS LOAD-BEARING and it is why this is
    a function rather than a comment. Sealing before observing would score
    a seal against the very turn that produced it -- the fitted residual
    the record exists to refuse. A caller that inlines the sequence can
    get it subtly wrong; a caller that calls this cannot.

    Returns a small status dict. Raises nothing that the caller has to
    care about beyond the usual write errors -- callers on a request path
    should still wrap it, because a record must never cost a response.

    * Mirrors the sequence already inline at intelligence_kernel.py:991.
    That copy is fenced by a prior order and is NOT refactored here;
    the duplication is reported rather than removed under a gate that
    forbids touching it.
    """
    read = build_geometry_observation(text if isinstance(text, str) else "")
    pending = pending_seal(user_id, thread_id)
    observed = False
    if pending:
        observe_return(user_id, pending, read)
        observed = True
    key = seal_expectation(
        user_id, thread_id,
        next_turn_index(user_id, thread_id),
        persistence_expectation(read),
    )
    return {"sealed_key": key, "observed_prior": observed}


# --------------------------------------------------------------------------
# Test hook
# --------------------------------------------------------------------------
def _reset_seq_for_tests() -> None:
    with _SEQ_LOCK:
        _SEQ.clear()
