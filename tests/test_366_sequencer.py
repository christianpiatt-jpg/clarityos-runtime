"""
#366 A5 + A7 -- the sequencer, kept and built: route_request's decision is
bound to a real agent, planned one step per lane, run through run_workflow
with the lane runner; a halt is the ONLY violation exit and it never
resumes; the vendor's dict survives the runner byte-for-byte; the
unexercised branches still raise. Then the lanes' consolidation (R-366-F):
unanimous = robust, anything less = contested with the split carried.

Every test names the mutation that breaks it.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import lane_intersect as li
import orchestrator_context as C
import orchestrator_routing as R
import orchestrator_schemas as S
import orchestrator_workflows as W

NOW = datetime.now(timezone.utc)
MODEL = "openai:gpt-5.4"


def _identity(actor: str = "alice") -> S.IdentityProfile:
    return S.IdentityProfile(actor=actor, actor_kind=S.ActorKind.USER,
                             sovereignty_level=S.SovereigntyLevel.USER_OWNED,
                             authorization_tier=S.AuthorizationTier.EXECUTE)


def _decision(agent: str = MODEL, constraints: tuple = ()) -> S.RoutingDecision:
    return S.RoutingDecision(request_id="t1", selected_agent=agent, rationale="",
                             constraints_attached=constraints, decided_at=NOW)


def _constraint(rule_id: str = "A4.no_names", sev=S.Severity.ABSOLUTE) -> S.ConstitutionalConstraint:
    return S.ConstitutionalConstraint(rule_id=rule_id, statement="x", severity=sev,
                                      enforcement=S.EnforcementMode.HALT, scope=("thread_message",))


def _plan(lanes=("time", "ambient", "role"), constraints=()) -> S.ExecutionPlan:
    return R.build_execution_plan(_decision(constraints=constraints), {
        "lanes": lanes, "model_id": MODEL, "direction": "query",
        "contract_ids": li.LANE_CONTRACT_IDS, "constraints": (_constraint(),),
    })


def _request() -> S.RoutingRequest:
    return S.RoutingRequest(request_id="t1", request_type="thread_message", payload={"v": "ep-up.v1"},
                            identity=_identity(), arrived_at=NOW)


def _context(plan=None, drift=None, geometry=None) -> S.ContextEnvelope:
    plan = plan or _plan()
    drift = drift or C.load_drift_state("alice", (), "query")
    geometry = geometry or S.GeometryProfile(depth=0, breadth=len(plan.steps), pressure_load=0.0, stability_score=1.0, captured_at=NOW)
    return C.assemble_context(_request(), plan, _identity(), drift, geometry)


# ---------------------------------------------------------------------------
# the decision, kept
# ---------------------------------------------------------------------------
class TestTheDecisionIsKept:
    def test_a_registered_agent_binds_and_an_empty_registry_still_halts(self):
        """board #50's finding stands when nothing is bound; #366 binds the
        resolved model. Mutation: select the first agent regardless of
        capability -> a wrong-capability agent binds."""
        req = _request()
        agents = (S.AgentBinding(agent_id=MODEL, capabilities=("thread_message",),
                                 authorized_tiers=(S.AuthorizationTier.EXECUTE,)),)
        d = R.route_request(req, agents, ())
        assert d.selected_agent == MODEL
        assert R.route_request(req, (), ()).selected_agent == R.HALT_AGENT
        wrong = (S.AgentBinding(agent_id="x", capabilities=("elins_run",), authorized_tiers=(S.AuthorizationTier.EXECUTE,)),)
        assert R.route_request(req, wrong, ()).selected_agent == R.HALT_AGENT


# ---------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------
class TestThePlan:
    def test_one_step_per_lane_carrying_lane_model_direction_and_contract(self):
        """Three lanes -> three steps in lane order, each input naming its
        lane, the bound model, the direction bit and the contract id.
        Mutation: one step for all lanes -> len 1."""
        plan = _plan()
        assert [s.inputs["lane"] for s in plan.steps] == ["time", "ambient", "role"]
        assert all(s.inputs["model_id"] == MODEL and s.inputs["direction"] == "query" for s in plan.steps)
        assert plan.steps[2].inputs["contract_id"] == li.LANE_CONTRACT_IDS["role"]
        assert all(s.action == "lane_read" for s in plan.steps)

    def test_no_constraint_is_dropped_between_decision_and_plan(self):
        """overall ⊇ every step's constraints, and the plan-level A4 constraint
        rides on every step. Mutation: leave the hints' constraints off the
        steps -> the superset holds but A4 is missing from the step."""
        attached = (_constraint("privacy.no_address", S.Severity.REQUIRED),)
        plan = _plan(constraints=attached)
        overall = set(plan.overall_constraints)
        for s in plan.steps:
            assert set(s.constraints) <= overall
            assert any(c.rule_id == "A4.no_names" for c in s.constraints)
        assert any(c.rule_id == "privacy.no_address" for c in overall)

    def test_a_duplicate_rule_keeps_the_higher_severity(self):
        """The same rule_id at two severities -> one entry, the higher.
        Mutation: keep the first seen -> ADVISORY wins."""
        attached = (_constraint("A4.no_names", S.Severity.ADVISORY),)
        plan = _plan(constraints=attached)
        a4 = [c for c in plan.overall_constraints if c.rule_id == "A4.no_names"]
        assert len(a4) == 1 and a4[0].severity == S.Severity.ABSOLUTE

    def test_a_halt_decision_plans_zero_steps(self):
        """A halted route runs nothing; the attached constraints still ride.
        Mutation: plan the lanes anyway -> 3 steps for no agent."""
        plan = R.build_execution_plan(_decision(agent=R.HALT_AGENT, constraints=(_constraint("k"),)), {"lanes": ("role",), "model_id": MODEL})
        assert plan.steps == () and any(c.rule_id == "k" for c in plan.overall_constraints)

    def test_a_plan_without_lanes_is_refused(self):
        """Mutation: default to the three lanes -> no ValueError."""
        with pytest.raises(ValueError):
            R.build_execution_plan(_decision(), {"model_id": MODEL})


# ---------------------------------------------------------------------------
# the context
# ---------------------------------------------------------------------------
class TestTheContext:
    def test_assemble_carries_the_plans_constraints_and_type_checks(self):
        """constraints == plan.overall_constraints; a wrong type is a
        ValueError, not a silent envelope. Mutation: accept any object."""
        ctx = _context()
        assert tuple(ctx.constraints) == tuple(ctx.plan.overall_constraints)
        with pytest.raises(ValueError):
            C.assemble_context(_request(), "not a plan", _identity(), ctx.drift, ctx.geometry)  # type: ignore[arg-type]

    @pytest.mark.parametrize("history, anchor, magnitude", [
        ((), "query", 0.0),
        (("query", "query", "query"), "query", 0.0),
        (("action", "action", "query"), "query", 0.6667),
        (("plan",) * 9 + ("query",) * 0, "query", 1.0),
        (("action",) * 5 + ("query",) * 8, "query", 0.0),   # only the last 8 count
    ])
    def test_intent_drift_is_the_share_of_the_last_eight_prior_bits_that_differ(self, history, anchor, magnitude):
        """A pure count over DRIFT_WINDOW prior direction bits. Mutation:
        count the whole history -> the fifth case reads 5/13."""
        d = C.load_drift_state("alice", history, anchor)
        assert d.axis == S.DriftAxis.INTENT
        assert d.magnitude == pytest.approx(magnitude, abs=1e-4)
        assert d.baseline_anchor == anchor

    def test_a_changed_direction_is_measured_but_not_gated(self):
        """R-366-B: the bit is the member's own authorization, so a full
        shift (1.0) still reads in_bounds True and says so -- the first
        draft halted the member's turn on it. Mutation: gate on the
        threshold -> in_bounds False at 1.0."""
        d = C.load_drift_state("alice", ("query", "query", "query"), "action")
        assert d.magnitude == 1.0 and d.in_bounds is True
        assert d.direction == "shifting 3/3 (member-authorized; not gated)"

    def test_no_prior_turn_says_so(self):
        """direction names the absence, never 'stable' for a turn that had
        nothing to be stable against (D5)."""
        assert C.load_drift_state("alice", (), "query").direction == "no prior turn"

    def test_the_other_axes_keep_raising(self):
        """R-366-D: unexercised branches raise, pinned. Mutation: return 0.0
        for TONE -> no NotImplementedError."""
        with pytest.raises(NotImplementedError):
            C.load_drift_state("alice", (), "query", axis=S.DriftAxis.TONE)
        with pytest.raises(NotImplementedError):
            C.attach_constraints(_context(), ())
        with pytest.raises(NotImplementedError):
            R.select_agent("thread_message", _identity(), (), ())


# ---------------------------------------------------------------------------
# run_workflow
# ---------------------------------------------------------------------------
class TestRunWorkflow:
    def test_three_steps_run_three_checkpoints_and_complete(self):
        """One checkpoint per step, C/D/G/I/S intact on each, the same actor
        at the end. Mutation: skip checkpoint() -> 0 tokens."""
        plan, ctx = _plan(), _context()
        calls = []
        res = W.run_workflow(plan, ctx, lambda step, c: calls.append(step.step_id) or {"ok": True})
        assert res.status == S.WorkflowStatus.COMPLETED and res.completed_at is not None
        assert calls == [s.step_id for s in plan.steps]
        assert len(res.checkpoints) == 3
        for tok in res.checkpoints:
            assert set(S._REQUIRED_PROPAGATION_FIELDS) <= set(tok.propagation.__dataclass_fields__)
        assert res.final_propagation.identity_profile.actor == ctx.identity.actor
        assert res.final_propagation.from_step == plan.steps[-1].step_id and res.final_propagation.to_step == "<end>"
        assert res.halt_state is None

    def test_a_runner_violation_halts_and_never_resumes(self):
        """The violation on step 2 halts the run: one checkpoint, step 3 is
        never called, requires_human_override is True for REQUIRED.
        Mutation: continue past the violation -> calls == 3."""
        plan, ctx = _plan(), _context()
        calls = []

        def runner(step, c):
            calls.append(step.step_id)
            if step.inputs["lane"] == "ambient":
                return {W.VIOLATION_KEY: S.Violation(constraint_id="A4.no_names", severity=S.Severity.REQUIRED,
                                                     detected_at_step=step.step_id, description="a name", detected_at=NOW)}
            return {}

        res = W.run_workflow(plan, ctx, runner)
        assert res.status == S.WorkflowStatus.HALTED
        assert calls == [plan.steps[0].step_id, plan.steps[1].step_id]
        assert len(res.checkpoints) == 1
        assert res.halt_state.halted_at_step == plan.steps[1].step_id
        assert res.halt_state.requires_human_override is True
        assert res.completed_at is None

    def test_an_advisory_violation_halts_without_requiring_override(self):
        """halt_for_violation's invariant: override is required iff severity
        >= REQUIRED. Mutation: always True."""
        plan, ctx = _plan(("role",)), _context(_plan(("role",)))
        v = S.Violation(constraint_id="tone", severity=S.Severity.ADVISORY, detected_at_step="x", description="", detected_at=NOW)
        res = W.run_workflow(plan, ctx, lambda s, c: {W.VIOLATION_KEY: v})
        assert res.status == S.WorkflowStatus.HALTED and res.halt_state.requires_human_override is False

    def test_drift_out_of_bounds_halts_before_any_step_runs(self):
        """The PRE check: a DriftState that says out-of-bounds halts with no
        runner call, constraint drift_within_bounds. (The thread route's
        INTENT axis never says so -- see the context tests -- so the state is
        built by hand here.) Mutation: run the step first -> calls == 1."""
        drift = S.DriftState(axis=S.DriftAxis.INTENT, magnitude=0.9, direction="shifting", baseline_anchor="query",
                             in_bounds=False, measured_at=NOW)
        plan = _plan()
        ctx = _context(plan, drift=drift)
        calls = []
        res = W.run_workflow(plan, ctx, lambda s, c: calls.append(1) or {})
        assert res.status == S.WorkflowStatus.HALTED and calls == []
        assert res.halt_state.violation.constraint_id == "drift_within_bounds"

    def test_geometry_below_the_floor_halts(self):
        """Mutation: drop the floor check -> COMPLETED."""
        plan = _plan()
        geom = S.GeometryProfile(depth=0, breadth=3, pressure_load=0.9, stability_score=0.1, captured_at=NOW)
        res = W.run_workflow(plan, _context(plan, geometry=geom), lambda s, c: {})
        assert res.status == S.WorkflowStatus.HALTED
        assert res.halt_state.violation.constraint_id == "geometry_within_stability_budget"

    def test_an_empty_plan_completes_with_no_checkpoint(self):
        """A halted route's plan (zero steps) runs nothing and completes.
        Mutation: raise on an empty plan."""
        plan = R.build_execution_plan(_decision(agent=R.HALT_AGENT), {"lanes": ("role",), "model_id": MODEL})
        res = W.run_workflow(plan, _context(plan), lambda s, c: {})
        assert res.status == S.WorkflowStatus.COMPLETED and res.checkpoints == ()

    def test_plan_and_context_are_not_mutated(self):
        """Frozen in, frozen out: the field VALUES snapshotted before the run
        equal the fields after it (comparing an object with itself proves
        nothing -- the refuter's tautology). Mutation: object.__setattr__ the
        plan's steps to () inside run_workflow -> the snapshot differs."""
        plan, ctx = _plan(), _context()
        steps_before, overall_before = tuple(plan.steps), tuple(plan.overall_constraints)
        ctx_before = (tuple(ctx.constraints), ctx.identity.actor, ctx.drift.magnitude, ctx.geometry.stability_score, ctx.plan.plan_id)
        W.run_workflow(plan, ctx, lambda s, c: {})
        assert tuple(plan.steps) == steps_before and len(steps_before) == 3
        assert tuple(plan.overall_constraints) == overall_before
        assert (tuple(ctx.constraints), ctx.identity.actor, ctx.drift.magnitude, ctx.geometry.stability_score, ctx.plan.plan_id) == ctx_before

    def test_checkpoint_and_halt_refuse_a_state_without_propagation(self):
        """The old skeleton tests' inputs ({}), now a ValueError -- a
        different kind than NotImplementedError. Mutation: build a token
        from an empty state."""
        with pytest.raises(ValueError):
            W.checkpoint({})
        v = S.Violation(constraint_id="C1", severity=S.Severity.ABSOLUTE, detected_at_step="s1", description="x", detected_at=NOW)
        with pytest.raises(ValueError):
            W.halt_for_violation({}, v)
        with pytest.raises(ValueError):
            W.run_workflow(_plan(), _context(), "not callable")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# the lane runner (ep_up_turn.run_lanes) -- needs the parser
# ---------------------------------------------------------------------------
spacy = pytest.importorskip("spacy", reason="#366 A1: spaCy is the parser (requirements.txt)")

import ep_up_payload as ep  # noqa: E402
import ep_up_turn  # noqa: E402
import seat_ledger as sl  # noqa: E402

TEXT = "I filed complaints against the agency. The agency dismissed them without a hearing."


def _lane_json(lane: str, prompt: str) -> str:
    payload = json.loads(prompt.split("\n\n", 1)[1])
    rows = [{"i": i, "state": "met", "direction": "s->o", "mass": 0.5} for i, _ in enumerate(payload["EP"]["triples"])]
    return json.dumps({"v": "lane.v1", "lane": lane, "rows": rows})


class TestTheLaneRunner:
    def _composed(self):
        return ep_up_turn.compose_turn(text=TEXT, direction="query", picked=False, seatmap=sl.SeatMap())

    def test_each_lane_gets_the_frame_plus_the_serialized_payload_and_no_text(self):
        """prompt == lane_frame + blank line + the payload bytes; the member's
        sentence and the seated name never appear. Mutation: append the text
        after the payload -> 'dismissed them' in the prompt."""
        composed = self._composed()
        seen = []

        def fake(model_id, prompt):
            lane = prompt.split("lane=", 1)[1].split(" ", 1)[0]
            seen.append((model_id, lane, prompt))
            return {"ok": True, "model_id": model_id, "provider": "fake", "text": _lane_json(lane, prompt),
                    "mock": False, "ts": 0.0, "stop_reason": "end_turn", "usage": {"prompt_tokens": 1, "completion_tokens": 1},
                    "_meta": {"stop_reason": "end_turn", "adapter": "fake"}}

        out = ep_up_turn.run_lanes(composed=composed, model_id=MODEL, route_request_fn=fake, request_id="t1", actor="alice")
        assert [l for _, l, _ in seen] == ["time", "ambient", "role"]
        for model_id, lane, prompt in seen:
            assert model_id == MODEL
            assert prompt == li.lane_frame(lane, "query") + "\n\n" + composed["serialized"]
            assert TEXT not in prompt and "dismissed them" not in prompt
            assert "agency" not in prompt.lower()          # seated: the id rides, never the name
            assert "complaints" not in prompt               # the surface form; the lemma is algebra
        assert out["halt"] is None and out["result"].status == S.WorkflowStatus.COMPLETED

    def test_the_vendor_dict_survives_the_runner_byte_for_byte(self):
        """``_meta`` and ``stop_reason`` are the adapter's; the runner adds
        ``lane`` and ``contract_id`` BESIDE them. Mutation: rebuild the dict
        with the fields the runner knows -> _meta lost."""
        composed = self._composed()
        meta = {"stop_reason": "end_turn", "adapter": "fake"}

        def fake(model_id, prompt):
            lane = prompt.split("lane=", 1)[1].split(" ", 1)[0]
            return {"ok": True, "model_id": model_id, "provider": "fake", "text": _lane_json(lane, prompt),
                    "mock": False, "ts": 0.0, "stop_reason": "end_turn", "usage": None, "_meta": dict(meta)}

        out = ep_up_turn.run_lanes(composed=composed, model_id=MODEL, route_request_fn=fake, request_id="t1", actor="alice")
        for r in out["lane_responses"]:
            assert r["_meta"] == meta and r["stop_reason"] == "end_turn"
            assert r["lane"] in li.LANES and r["contract_id"] == li.LANE_CONTRACT_IDS[r["lane"]]
            assert "_meta" in r and "lane" not in r["_meta"]

    def test_a_name_in_the_payload_halts_before_any_lane_is_sent(self):
        """The A4 constraint as the workflow's violation: the runner finds the
        leak, returns the Violation, run_workflow halts on step 1, zero vendor
        calls. Mutation: send first and check after -> one call."""
        composed = self._composed()
        agency = composed["seatmap"].lookup("agency")
        assert agency is not None
        # poison: a lexical object carrying the seat's NAME
        composed["payload"]["EP"]["triples"][0]["o"] = "agency"
        composed["payload"]["EP"]["triples"][0]["ok"] = "lex"
        calls = []
        out = ep_up_turn.run_lanes(composed=composed, model_id=MODEL, route_request_fn=lambda m, p: calls.append(p) or {}, request_id="t1", actor="alice")
        assert calls == []
        assert out["halt"] is not None and out["halt"]["constraint"] == "A4.no_names"
        assert out["halt"]["requires_human_override"] is True
        assert out["lane_responses"] == []

    def test_a_lane_whose_call_raises_is_a_degraded_lane_not_a_halt(self):
        """The vendor raising is not a constitutional violation: the lane is
        recorded mock with the exception TYPE, the other lanes still run.
        Mutation: let the exception propagate -> no result."""
        composed = self._composed()

        def fake(model_id, prompt):
            if "lane=ambient" in prompt:
                raise TimeoutError("slow")
            lane = prompt.split("lane=", 1)[1].split(" ", 1)[0]
            return {"ok": True, "model_id": model_id, "provider": "fake", "text": _lane_json(lane, prompt), "mock": False, "ts": 0.0}

        out = ep_up_turn.run_lanes(composed=composed, model_id=MODEL, route_request_fn=fake, request_id="t1", actor="alice")
        assert out["halt"] is None and len(out["lane_responses"]) == 3
        amb = [r for r in out["lane_responses"] if r["lane"] == "ambient"][0]
        assert amb["mock"] is True and amb["fallback_error"] == "TimeoutError"
        assert out["parsed"]["ambient"]["ok"] is False


# ---------------------------------------------------------------------------
# A7 -- parse and intersect (R-366-F)
# ---------------------------------------------------------------------------
class TestLaneParse:
    def test_a_valid_reply_fills_every_row(self):
        """Mutation: read rows by position instead of ``i`` -> a reordered
        reply misfiles."""
        text = json.dumps({"v": "lane.v1", "lane": "role", "rows": [
            {"i": 1, "state": "met", "direction": "o->s", "mass": 0.25},
            {"i": 0, "state": "violated", "direction": "s->o", "mass": 1},
        ]})
        p = li.parse_lane_return(text, 2)
        assert p["ok"] is True and p["reason"] is None
        assert p["rows"][0] == {"state": "violated", "direction": "s->o", "mass": 1.0}
        assert p["rows"][1] == {"state": "met", "direction": "o->s", "mass": 0.25}

    def test_prose_and_bad_values_read_undefined_with_a_reason(self):
        """A prose reply is a no-basis lane; a value outside the vocabulary is
        an undefined cell; a mass outside [0,1] or a bool is undefined.
        Mutation: default a bad state to met."""
        p = li.parse_lane_return("Certainly! Here is my reading of the rows.", 2)
        assert p["ok"] is False and p["reason"] == "no JSON object in reply"
        assert all(c == {"state": "undefined", "direction": "undefined", "mass": "undefined"} for c in p["rows"].values())
        q = li.parse_lane_return(json.dumps({"rows": [{"i": 0, "state": "met-ish", "direction": "up", "mass": 1.7}, {"i": 1, "state": "met", "direction": "s->o", "mass": True}]}), 2)
        assert q["rows"][0] == {"state": "undefined", "direction": "undefined", "mass": "undefined"}
        assert q["rows"][1]["mass"] == "undefined" and q["rows"][1]["state"] == "met"
        r = li.parse_lane_return(json.dumps({"rows": [{"i": 0, "state": "met", "direction": "s->o", "mass": 0.3}]}), 3)
        assert r["ok"] is True and r["reason"] == "answered 1 of 3 rows"

    def test_a_repeated_index_is_one_answer_and_a_fractional_one_is_none(self):
        """rows [{i:0},{i:0}] for two rows answers ONE row and says so; i=1.7
        files under no row. Mutation: count entries instead of distinct rows
        -> 'answered 2 of 2'; truncate the float -> row 1 filled."""
        dup = json.dumps({"rows": [{"i": 0, "state": "met", "direction": "s->o", "mass": 0.5},
                                   {"i": 0, "state": "violated", "direction": "s->o", "mass": 0.5}]})
        p = li.parse_lane_return(dup, 2)
        assert p["reason"] == "answered 1 of 2 rows" and p["rows"][0]["state"] == "met"
        frac = json.dumps({"rows": [{"i": 1.7, "state": "met", "direction": "s->o", "mass": 0.5}]})
        q = li.parse_lane_return(frac, 2)
        assert q["ok"] is False and q["rows"][1]["state"] == "undefined"

    def test_a_brace_after_the_object_does_not_void_the_lane(self):
        """The FIRST complete rows object is decoded; a postscript or a
        preamble with a brace is not part of it. Mutation: span first-{ to
        last-} -> JSON parse failed."""
        text = '{"v":"lane.v1","lane":"role","rows":[{"i":0,"state":"met","direction":"s->o","mass":0.5}]}\nNote: {see above}'
        p = li.parse_lane_return(text, 1)
        assert p["ok"] is True and p["rows"][0]["state"] == "met"
        pre = 'Sure {thing}: {"v":"lane.v1","lane":"role","rows":[{"i":0,"state":"avoided","direction":"o->s","mass":0.2}]}'
        q = li.parse_lane_return(pre, 1)
        assert q["ok"] is True and q["rows"][0]["state"] == "avoided"

    def test_the_frames_name_the_axis_the_contract_and_the_schema(self):
        """Instrument text only: keys, enums, ids. Mutation: drop 'No prose'
        or the contract id."""
        for lane in li.LANES:
            f = li.lane_frame(lane, "action")
            assert f.startswith("[ClarityOS ep-up.v1] lane=%s direction=action contract=%s" % (lane, li.LANE_CONTRACT_IDS[lane]))
            assert "No prose" in f and "\"rows\"" in f
            for st in li.ROW_STATES:
                assert st in f
        with pytest.raises(ValueError):
            li.lane_frame("mood", "query")


def _ret(cells: dict) -> dict:
    return {"ok": True, "rows": cells, "reason": None}


def _cell(state="met", direction="s->o", mass=0.5) -> dict:
    return {"state": state, "direction": direction, "mass": mass}


UNDEF = {"state": "undefined", "direction": "undefined", "mass": "undefined"}


class TestIntersect:
    def test_unanimous_is_robust_with_the_mean_mass(self):
        """Three lanes, same state and direction -> robust, mass = mean.
        Mutation: take the first lane's mass -> 0.2 not 0.4."""
        rets = {"time": _ret({0: _cell(mass=0.2)}), "ambient": _ret({0: _cell(mass=0.4)}), "role": _ret({0: _cell(mass=0.6)})}
        out = li.lane_intersect(rets, 1)
        assert out["robust"] == {0: {"state": "met", "direction": "s->o", "mass": 0.4, "lanes": 3}}
        assert out["contested"] == {} and out["undefined_rows"] == []

    def test_one_dissent_is_contested_and_the_split_is_carried(self):
        """R-366-F: anything less than unanimous is contested; the split
        names each lane's value. Mutation: majority wins -> robust met."""
        rets = {"time": _ret({0: _cell("met")}), "ambient": _ret({0: _cell("met")}), "role": _ret({0: _cell("violated")})}
        out = li.lane_intersect(rets, 1)
        assert 0 in out["contested"] and out["robust"] == {}
        c = out["contested"][0]
        assert c["split"]["role"]["state"] == "violated" and c["split"]["time"]["state"] == "met"
        assert c["states"] == ["met", "violated"] and c["lanes"] == 3
        vals = li.row_values(out)
        assert vals[0]["state"] == "undefined" and vals[0]["robust"] is False and vals[0]["candidates"] == ["met", "violated"]

    def test_a_lane_that_did_not_answer_makes_the_row_contested_not_robust(self):
        """Two agree, one undefined: not unanimous across the lanes -> contested
        (the unanswered lane is information). Mutation: intersect over the
        answering lanes only -> robust."""
        rets = {"time": _ret({0: _cell()}), "ambient": _ret({0: _cell()}), "role": _ret({0: dict(UNDEF)})}
        out = li.lane_intersect(rets, 1)
        assert 0 in out["contested"] and out["contested"][0]["lanes"] == 2

    def test_every_lane_undefined_is_an_undefined_row(self):
        """Neither robust nor contested: no lane read it (D5)."""
        rets = {ln: _ret({0: dict(UNDEF)}) for ln in li.LANES}
        out = li.lane_intersect(rets, 1)
        assert out["undefined_rows"] == [0] and out["robust"] == {} and out["contested"] == {}
        assert li.row_values(out) == {}

    def test_direction_disagreement_alone_is_contested(self):
        """Same state, different direction -> contested. Mutation: intersect
        on state only."""
        rets = {"time": _ret({0: _cell(direction="s->o")}), "ambient": _ret({0: _cell(direction="o->s")}), "role": _ret({0: _cell(direction="s->o")})}
        out = li.lane_intersect(rets, 1)
        assert 0 in out["contested"] and out["contested"][0]["directions"] == ["o->s", "s->o"]
