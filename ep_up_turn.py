"""
ep_up_turn.py — #366: one member turn through the machine, in order.

    parse (A1) → attribute (A2) → compose EP/UP (A4) → route · plan ·
    context · run_workflow with the lane runner (A5) → parse the lane
    returns · intersect (A7) → reassemble (A8) → fold the ledger (A2) → the
    reading the pilot sees.

Two entry shapes, one machine:

    thread    ``compose_turn`` (reads only -- the route reserves on its
              ``reserve_text``) then ``run_turn`` (the writes). The
              relationship's seat map and ledger persist in the vault; UP
              rides from the prior seal; three lanes (time · ambient ·
              role), one vendor call each.
    session   ``shape_session_step`` / ``finish_session_step``: an
              ephemeral seat map, no UP (no seal exists on /session), one
              lane (role), one vendor call -- exactly the call the step made
              before, with algebra in the prompt instead of the text.

Nothing in this module logs member text or a name. The seat map never
leaves the process except to the member's own vault.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

import clause_parser
import directive_engine
import ep_up_payload
import lane_intersect
import orchestrator_context
import orchestrator_routing
import orchestrator_schemas as S
import orchestrator_workflows
import reassembler
import seat_ledger
import turn_record

logger = logging.getLogger("clarityos.ep_up_turn")

#: app.py binds this to ``_verb_owner_set`` at import (the kernel cannot
#: import app). Unbound → D from the primitive counts, T/N UNMAPPED.
VERB_OWNER_SET_FN: Optional[Callable[[str], dict]] = None

THREAD_LANES: tuple = lane_intersect.LANES
SESSION_LANES: tuple = ("role",)
REQUEST_TYPE_THREAD: str = "thread_message"
REQUEST_TYPE_SESSION: str = "session_step"
MACHINE_VERSION: str = "ep-up.turn.v1"

#: The constraint the plan carries: a name in a lane prompt is an ABSOLUTE
#: violation and the ONLY way a lane is not sent. It is attached at PLAN
#: level (build_execution_plan hints), not passed to route_request -- whose
#: own body halts on the mere presence of an ABSOLUTE+HALT constraint it
#: cannot check (board #50). The runner checks it; the workflow halts on it.
A4_CONSTRAINT = S.ConstitutionalConstraint(
    rule_id="A4.no_names",
    statement="no seat-map name reaches a model",
    severity=S.Severity.ABSOLUTE,
    enforcement=S.EnforcementMode.HALT,
    scope=(REQUEST_TYPE_THREAD, REQUEST_TYPE_SESSION),
    rationale="#366 (CT-1): the message arrives configured to verb-object, attributed identity, before any LLM",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def strip_directives(text: str) -> str:
    """The same strip the kernel applies (A28): a leading directive run is
    consumed, never parsed as clauses."""
    if not isinstance(text, str):
        return ""
    ds = directive_engine.parse_directives(text)
    return ds.text.strip() if ds.active else text.strip()


def verb_owner_set(text: str, read: Optional[dict] = None) -> Optional[dict]:
    """D / T / N (+ counts) for EP. Through app's ``_verb_owner_set`` when
    bound; otherwise D from the primitive counts and T / N UNMAPPED. The
    hydronic counts come from this turn's read when the producer carries
    none."""
    vos: Optional[dict] = None
    fn = VERB_OWNER_SET_FN
    if callable(fn):
        try:
            out = fn(text)
            vos = dict(out) if isinstance(out, dict) else None
        except Exception as e:  # noqa: BLE001 -- never the turn's cost
            logger.warning("verb_owner_set hook FAILED err=%s", type(e).__name__)
    if vos is None:
        try:
            import primitives_extract
            counts = primitives_extract.build_metadata(primitives_extract.extract_primitives(text or ""))["counts"]
            vos = {"D": int(sum(int(v) for v in counts.values() if isinstance(v, int))), "counts": dict(counts),
                   "T": "UNMAPPED", "N": "UNMAPPED"}
        except Exception as e:  # noqa: BLE001
            logger.warning("verb_owner_set fallback FAILED err=%s", type(e).__name__)
            vos = None
    if isinstance(vos, dict) and isinstance(read, dict):
        counts = vos.get("counts") if isinstance(vos.get("counts"), dict) else {}
        if not isinstance(counts.get("hydronic"), dict):
            hyd = (read.get("primitives") or {}).get("hydronic") if isinstance(read.get("primitives"), dict) else None
            if isinstance(hyd, dict):
                counts = dict(counts)
                counts["hydronic"] = dict(hyd)
                vos["counts"] = counts
    return vos


# ===========================================================================
# COMPOSE -- reads only
# ===========================================================================
def compose_turn(*, text: str, direction: str, picked: bool, user_id: Optional[str] = None,
                 thread_id: Optional[str] = None, read: Optional[dict] = None,
                 prior_record: Optional[dict] = None, turn_index: int = 0,
                 lanes: tuple = THREAD_LANES, seatmap: Optional[seat_ledger.SeatMap] = None,
                 author_classes: Optional[set] = None) -> dict:
    """parse → learn classes → attribute → UP → payload → lane prompts.
    No write: the seat map is loaded (or fresh) and extended in memory; the
    caller persists it through ``run_turn``."""
    d, p = ep_up_payload.validate_direction(direction, picked)
    clean = strip_directives(text)
    rows = clause_parser.parse_clauses(clean)
    learned = seat_ledger.learn_author_classes(rows)
    ledger: Optional[dict] = None
    if seatmap is None:
        if user_id and thread_id:
            ledger, seatmap = seat_ledger.load(user_id, thread_id)
        else:
            seatmap = seat_ledger.SeatMap()
    classes = set(author_classes or ()) | set((ledger or {}).get("author_classes") or []) | set(learned)
    triples = seat_ledger.attribute(rows, seatmap, author_classes=classes)
    if read is None:
        read = turn_record.build_geometry_observation(clean)
    up = ep_up_payload.compose_up(prior_record, read)
    ask_prev = prior_record.get("ask") if isinstance(prior_record, dict) and isinstance(prior_record.get("ask"), dict) else None
    vos = verb_owner_set(clean, read)
    payload = ep_up_payload.compose(
        direction=d, picked=p, turn=int(turn_index), triples=triples, verb_owner_set=vos,
        up=up, ask_prev=ask_prev, seatmap_names=seatmap.names(), proper_tokens=seatmap.proper_tokens(),
    )
    serialized = ep_up_payload.serialize(payload)
    prompts = {lane: lane_intersect.lane_prompt(lane, d, serialized) for lane in lanes}
    return {
        "v": MACHINE_VERSION,
        "text_chars": len(clean),
        "rows": rows,
        "triples": triples,
        "seatmap": seatmap,
        "ledger": ledger,
        "classes": classes,
        "learned": set(learned),
        "read": read,
        "up": up,
        "payload": payload,
        "serialized": serialized,
        "prompts": prompts,
        "reserve_text": "".join(prompts[l] for l in lanes),
        "lanes": tuple(lanes),
        "direction": d,
        "picked": p,
        "turn": int(turn_index),
    }


# ===========================================================================
# A5 -- route · plan · context · run the lanes
# ===========================================================================
def run_lanes(*, composed: dict, model_id: str, route_request_fn: Callable, request_id: str,
              actor: str, history_directions: tuple = (), request_type: str = REQUEST_TYPE_THREAD) -> dict:
    """The sequencer, kept: route_request's decision is bound to a real
    agent (the resolved model), planned one step per lane, and run through
    ``run_workflow`` with a runner that sends ONE lane prompt per step and
    keeps the vendor's dict verbatim (``_meta``/``stop_reason`` untouched;
    ``lane`` and ``contract_id`` added beside them)."""
    now = _now()
    identity = S.IdentityProfile(
        actor=actor or "", actor_kind=S.ActorKind.USER,
        sovereignty_level=S.SovereigntyLevel.USER_OWNED,
        authorization_tier=S.AuthorizationTier.EXECUTE,
    )
    req = S.RoutingRequest(request_id=request_id, request_type=request_type,
                           payload=composed["payload"], identity=identity, arrived_at=now)
    agents = (S.AgentBinding(
        agent_id=model_id, capabilities=(request_type,),
        authorized_tiers=(S.AuthorizationTier.EXECUTE, S.AuthorizationTier.PROPOSE,
                          S.AuthorizationTier.OBSERVE, S.AuthorizationTier.READ),
    ),)
    decision = orchestrator_routing.route_request(req, agents, ())
    plan = orchestrator_routing.build_execution_plan(decision, {
        "lanes": composed["lanes"], "model_id": model_id, "direction": composed["direction"],
        "contract_ids": lane_intersect.LANE_CONTRACT_IDS, "constraints": (A4_CONSTRAINT,),
    })
    drift = orchestrator_context.load_drift_state(actor or "anonymous", tuple(history_directions), composed["direction"])
    # G -- READ from the default factory (azimuth_transition._default_
    # propagation_state), the same object #133's plan reads, with breadth =
    # this plan's steps. Geometry is not measured on this path: the value is
    # the factory's and the comment says so because the code calls it.
    import azimuth_transition as _az
    _g = _az._default_propagation_state().geometry_profile
    geometry = S.GeometryProfile(depth=_g.depth, breadth=len(plan.steps), pressure_load=_g.pressure_load,
                                 stability_score=_g.stability_score, captured_at=now)
    context = orchestrator_context.assemble_context(req, plan, identity, drift, geometry)

    names = composed["seatmap"].names()
    proper = composed["seatmap"].proper_tokens()
    n_rows = len(composed["triples"])
    responses: list = []
    parsed: dict = {}

    def runner(step, ctx):
        lane = (step.inputs or {}).get("lane")
        prompt = composed["prompts"].get(lane)
        if not isinstance(prompt, str):
            return {orchestrator_workflows.VIOLATION_KEY: S.Violation(
                constraint_id="plan.lane_unknown", severity=S.Severity.REQUIRED,
                detected_at_step=step.step_id, description="no prompt for lane %r" % (lane,), detected_at=_now())}
        leak = ep_up_payload.name_leak(composed["payload"], names, proper)
        if leak:
            return {orchestrator_workflows.VIOLATION_KEY: S.Violation(
                constraint_id=A4_CONSTRAINT.rule_id, severity=S.Severity.ABSOLUTE,
                detected_at_step=step.step_id,
                description="%d seat-map token(s) in the payload; the lane was not sent" % len(leak),
                detected_at=_now())}
        try:
            resp = route_request_fn(step.inputs["model_id"], prompt)
        except Exception as e:  # noqa: BLE001 -- a failed lane is a degraded lane, named
            resp = {"ok": False, "model_id": step.inputs["model_id"], "provider": "none", "text": "",
                    "mock": True, "ts": time.time(), "stop_reason": None, "usage": None,
                    "fallback_error": type(e).__name__}
        resp = dict(resp) if isinstance(resp, dict) else {"ok": False, "text": str(resp or ""), "mock": True}
        resp["lane"] = lane
        resp["contract_id"] = step.inputs.get("contract_id")
        responses.append(resp)
        parsed[lane] = lane_intersect.parse_lane_return(resp.get("text"), n_rows)
        return resp

    result = orchestrator_workflows.run_workflow(plan, context, runner)
    halt = None
    if result.halt_state is not None:
        hs = result.halt_state
        halt = {"step": hs.halted_at_step, "constraint": hs.violation.constraint_id,
                "description": hs.violation.description, "requires_human_override": bool(hs.requires_human_override)}
    logger.info(
        "orchestrator route acted_on=True request_type=%s agent=%s halted_on_route=%s steps=%d status=%s "
        "drift=%.3f lanes_sent=%d",
        request_type, decision.selected_agent, decision.selected_agent == orchestrator_routing.HALT_AGENT,
        len(plan.steps), result.status.value, drift.magnitude, len(responses),
    )
    return {"decision": decision, "plan": plan, "context": context, "result": result,
            "lane_responses": responses, "parsed": parsed, "halt": halt, "drift": drift}


# ===========================================================================
# A7 + A8
# ===========================================================================
def consolidate(composed: dict, lanes_out: dict) -> tuple:
    n = len(composed["triples"])
    parsed = lanes_out.get("parsed") or {}
    if parsed:
        inter = lane_intersect.lane_intersect(parsed, n)
    else:
        inter = {"v": "intersect.v1", "n_lanes": 0, "lanes": [], "robust": {}, "contested": {},
                 "undefined_rows": list(range(n)), "lane_reasons": {}}
    values = lane_intersect.row_values(inter)
    return inter, values


def _prior_directions(user_id: Optional[str], thread_id: Optional[str]) -> tuple:
    if not user_id or not thread_id:
        return ()
    try:
        recs = turn_record.list_turn_records(user_id, thread_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("prior directions read FAILED err=%s", type(e).__name__)
        return ()
    return tuple(r.get("direction") for r in recs if isinstance(r, dict) and isinstance(r.get("direction"), str))


def run_turn(*, user_id: str, thread_id: str, text: str, direction: str, picked: bool, model_id: str,
             route_request_fn: Callable, read: Optional[dict] = None, prior_record: Optional[dict] = None,
             turn_index: int = 0, composed: Optional[dict] = None, response_shape: Optional[dict] = None) -> dict:
    """The thread path. Returns everything the kernel needs to persist the
    reply and annotate the seal; the ledger is written here."""
    if composed is None:
        composed = compose_turn(text=text, direction=direction, picked=picked, user_id=user_id, thread_id=thread_id,
                                read=read, prior_record=prior_record, turn_index=turn_index)
    history = _prior_directions(user_id, thread_id)
    lanes_out = run_lanes(composed=composed, model_id=model_id, route_request_fn=route_request_fn,
                          request_id=thread_id, actor=user_id, history_directions=history)
    responses = lanes_out["lane_responses"]
    mock_all = bool(responses) and all(bool(r.get("mock")) for r in responses)
    # the sovereign seat's state is READ off the lanes: no lane sent (a halt)
    # reads None -- unread, never "provisioned" (D5; refuter, 2026-09-19)
    provisioned = None if not responses else (not (composed["direction"] == "diagnostic" and mock_all))
    inter, values = consolidate(composed, lanes_out)
    asker = seat_ledger.asker_seat_ids(composed["seatmap"], composed["classes"])
    reading = reassembler.reassemble(
        triples=composed["triples"], values=values, seatmap=composed["seatmap"], asker_seats=asker,
        up=composed["up"], n_lanes=inter["n_lanes"], turn=composed["turn"], provisioned=(provisioned is not False),
        shape=response_shape, halt=lanes_out["halt"],
    )
    ledger_written = None
    if user_id and thread_id:
        try:
            ledger_written = seat_ledger.apply_turn(user_id, thread_id, composed["triples"], values, composed["turn"],
                                                    composed["seatmap"], learned_classes=composed["learned"])
        except Exception as e:  # noqa: BLE001 -- a ledger write must never cost the reply; never silent
            logger.warning("seat_ledger write FAILED err=%s", type(e).__name__)
    return {
        "composed": composed,
        "payload": composed["payload"],
        "serialized": composed["serialized"],
        "lanes": lanes_out,
        "lane_responses": responses,
        "halt": lanes_out["halt"],
        "intersection": inter,
        "values": values,
        "reading": reading,
        "asker_seats": asker,
        "provisioned": provisioned,
        "mock": mock_all if responses else None,
        "fallback_error": next((r.get("fallback_error") for r in responses if isinstance(r.get("fallback_error"), str) and r.get("fallback_error")), None),
        "ledger": ledger_written,
        "meta": reading_meta(composed, inter, reading, lanes_out, provisioned),
    }


def reading_meta(composed: dict, inter: dict, reading: dict, lanes_out: dict, provisioned: bool) -> dict:
    """What rides the MEMBER's wire beside the reading: counts, enums and
    the relation's name restored on-machine. Never a lane's text; never a
    prompt. (This dict goes to the member who owns the seats, not to a
    model.)"""
    return {
        "v": MACHINE_VERSION,
        "direction": composed["direction"],
        "picked": composed["picked"],
        "turn": composed["turn"],
        "rows": reading.get("rows"),
        "rows_read": reading.get("rows_read"),
        "robust": reading.get("robust"),
        "contested": reading.get("contested"),
        "undefined": reading.get("undefined"),
        "lanes": list(inter.get("lanes") or []),
        "lane_reasons": dict(inter.get("lane_reasons") or {}),
        "halted": bool(reading.get("halted")),
        "ask": bool(reading.get("ask_text")),
        "asker_holds_seat": bool(reading.get("asker_holds_seat")),
        "relation": reading.get("relation"),
        "provisioned": provisioned,               # True · False · None (no lane sent)
        "payload_chars": len(composed["serialized"]),
        "masked": int((composed["payload"].get("EP") or {}).get("masked") or 0),
        "up": composed["up"] is not None,
        "elins_check": (reading.get("meta") or {}).get("elins_check"),
    }


def seal_fields(turn: dict) -> dict:
    """direction · picked · ask, in the shape ``turn_record.annotate_seal``
    stores (None omits).

    The ask's ``o`` and ``v`` are taken from the WIRE triple (the masked
    form the lanes received), not from the reassembler's row: a word the
    mask replaced on this turn must not reach the seal and ride back as
    ``ask_prev`` on the next (refuter, 2026-09-19)."""
    composed = turn["composed"]
    ask = (turn.get("reading") or {}).get("ask")
    if isinstance(ask, dict):
        ask = dict(ask)
        wire = ((composed.get("payload") or {}).get("EP") or {}).get("triples") or []
        row = ask.get("row")
        if isinstance(row, int) and 0 <= row < len(wire):
            ask["o"] = wire[row].get("o", ask.get("o"))
            ask["v"] = wire[row].get("v", ask.get("v"))
    return {"direction": composed["direction"], "picked": composed["picked"], "ask": ask if isinstance(ask, dict) else None}


# ===========================================================================
# /session -- one lane, ephemeral seats, no UP
# ===========================================================================
def shape_session_step(text: str, intent_type: str) -> dict:
    """The /session shaper: the same compose, with the direction bit the
    selector already carries (picked -- /session has had the four-way
    selector since v57), an ephemeral seat map, no seal to difference
    against, one lane."""
    d = intent_type if intent_type in ep_up_payload.DIRECTIONS else "query"
    return compose_turn(text=text, direction=d, picked=(intent_type in ep_up_payload.DIRECTIONS),
                        lanes=SESSION_LANES, seatmap=seat_ledger.SeatMap())


def finish_session_step(composed: dict, response: dict, *, provisioned: bool = True) -> dict:
    """The step's vendor reply → the reading. One lane; n_lanes = 1."""
    n = len(composed["triples"])
    lane = composed["lanes"][0]
    parsed = {lane: lane_intersect.parse_lane_return((response or {}).get("text"), n)}
    inter = lane_intersect.lane_intersect(parsed, n)
    values = lane_intersect.row_values(inter)
    asker = seat_ledger.asker_seat_ids(composed["seatmap"], composed["classes"])
    reading = reassembler.reassemble(
        triples=composed["triples"], values=values, seatmap=composed["seatmap"], asker_seats=asker,
        up=None, n_lanes=1, turn=0, provisioned=provisioned,
    )
    return {"reading": reading, "intersection": inter, "values": values,
            "meta": reading_meta(composed, inter, reading, {"halt": None}, provisioned)}
