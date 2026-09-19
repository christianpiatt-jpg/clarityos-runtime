"""
orchestrator_workflows.py — Layer 3: Workflows (Minimal Orchestrator).

Executes an ExecutionPlan step by step, with pre/post C/D/G/I/S checks
at every step boundary. On any constraint violation, halts and
surfaces — never auto-resumes.

ROLE IN THE ARCHITECTURE
------------------------
The workflow layer is the runtime enforcement chokepoint. Every step
has TWO C/D/G/I/S checks:

    1. PRE-step:  constraints satisfied? identity unchanged? drift in
                  bounds? geometry within stability budget?
    2. POST-step: did the step emit a Violation? did drift exceed
                  bounds after running?

Either failure → ``halt_for_violation`` → ``HaltState`` → workflow
stops → human override required.

The workflow layer never calls LLMs directly. It calls an
``agent_runner`` callable supplied by the caller (typically the
gateway). The agent runner is the part that DOES call LLMs — but
that's the agent's job, not the orchestrator's.

PHASE STATUS
------------
Schemas locked in ``orchestrator_schemas.py``. #366 A5 (R-366-D, CT-1
2026-09-19): the bodies are implemented IN PLACE for exactly the path the
thread route exercises -- ``run_workflow`` · ``checkpoint`` ·
``halt_for_violation``. Nothing here calls a model: the ``agent_runner``
the kernel supplies does, and this layer inspects only its return shape
for a ``violation`` indicator.

PUBLIC API
----------
    run_workflow(plan, context, agent_runner)         -> WorkflowResult
    checkpoint(workflow_state)                        -> CheckpointToken
    halt_for_violation(workflow_state, violation)     -> HaltState

INVARIANTS (locked, enforced by tests + design discipline)
----------------------------------------------------------
    * Every step has BOTH pre-check AND post-check.
    * Every checkpoint produces a PropagationState satisfying the
      C/D/G/I/S contract.
    * halt_for_violation is the ONLY exit on violation.
    * requires_human_override is True for any violation with
      severity >= REQUIRED.
    * Workflows NEVER auto-resume past a halt.
    * Workflows NEVER mutate plan or context.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from orchestrator_schemas import (
    CheckpointToken,
    ContextEnvelope,
    ExecutionPlan,
    HaltState,
    INVARIANTS_CANONICAL,
    PropagationState,
    Severity,
    Violation,
    WorkflowResult,
    WorkflowStatus,
    _new_local_id,
)


# Type alias for the agent runner the workflow invokes per step.
# The orchestrator does not implement this — callers (gateway, tests)
# supply a runner that knows how to invoke the agent for one
# ExecutionStep given the current ContextEnvelope.
AgentRunner = Callable[..., dict]

#: The geometry floor the PRE-step check holds a step to. Below it the
#: structure is unstable and the step does not run. A ruling constant, not
#: a tuned one: the thread path arrives with stability 1.0 from the
#: default factory (azimuth_transition._default_propagation_state).
STABILITY_FLOOR: float = 0.2

#: The runner's violation indicator: a ``Violation`` under this key in the
#: returned dict halts the workflow. The ONLY way a step's output stops a
#: run -- the orchestrator does not read vendor text.
VIOLATION_KEY: str = "violation"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _initial_propagation(plan: ExecutionPlan, context: ContextEnvelope, first_step: str) -> PropagationState:
    return PropagationState(
        from_step="route",
        to_step=first_step,
        active_constraints=tuple(plan.overall_constraints or ()),
        drift_state=context.drift,
        geometry_profile=context.geometry,
        identity_profile=context.identity,
        invariants_preserved=tuple(INVARIANTS_CANONICAL),
    )


def _pre_check(step, context: ContextEnvelope, propagation: PropagationState) -> Optional[Violation]:
    """The PRE-step C/D/G/I check. Returns the first Violation, or None.

    C -- an ABSOLUTE constraint with enforcement HALT that the plan carries
         is not violated by the step's mere existence; violation is a
         runner-reported fact (POST). Nothing to decide here.
    D -- drift must be in bounds.
    G -- geometry stability must clear the floor.
    I -- the identity that arrived is the identity that runs.
    """
    if not context.drift.in_bounds:
        return Violation(constraint_id="drift_within_bounds", severity=Severity.REQUIRED,
                         detected_at_step=step.step_id,
                         description="drift %.3f on %s is out of bounds" % (context.drift.magnitude, context.drift.axis.value),
                         detected_at=_now())
    if context.geometry.stability_score < STABILITY_FLOOR:
        return Violation(constraint_id="geometry_within_stability_budget", severity=Severity.REQUIRED,
                         detected_at_step=step.step_id,
                         description="stability %.3f below floor %.2f" % (context.geometry.stability_score, STABILITY_FLOOR),
                         detected_at=_now())
    if propagation.identity_profile.actor != context.identity.actor:
        return Violation(constraint_id="identity_unchanged_or_delegated", severity=Severity.ABSOLUTE,
                         detected_at_step=step.step_id,
                         description="identity changed between steps", detected_at=_now())
    return None


def _post_check(step, output) -> Optional[Violation]:
    """The POST-step check: did the runner report a Violation?"""
    if isinstance(output, dict):
        v = output.get(VIOLATION_KEY)
        if isinstance(v, Violation):
            return v
        if v is not None:
            return Violation(constraint_id="runner_violation", severity=Severity.REQUIRED,
                             detected_at_step=step.step_id,
                             description="runner reported a violation of unknown shape (%s)" % type(v).__name__,
                             detected_at=_now())
    return None


# ---------------------------------------------------------------------------
# run_workflow
# ---------------------------------------------------------------------------
def run_workflow(
    plan: ExecutionPlan,
    context: ContextEnvelope,
    agent_runner: AgentRunner,
) -> WorkflowResult:
    """Execute the plan step by step with C/D/G/I/S checks at every boundary.

    Args:
        plan:         the ExecutionPlan from routing (immutable).
        context:      the ContextEnvelope from context assembly (immutable).
        agent_runner: callable invoked once per step:
                          agent_runner(step, context) -> dict
                      The callable is responsible for any LLM / domain
                      logic. The orchestrator inspects only its return
                      shape for Violation indicators.

    Returns:
        WorkflowResult with:
            * status            — COMPLETED, HALTED, or PENDING_HUMAN_REVIEW
            * final_propagation — last PropagationState built
            * checkpoints       — tuple of CheckpointToken (one per step)
            * halt_state        — set iff status == HALTED
            * completed_at      — set iff status == COMPLETED

    Algorithm (Phase 2 implementation):
        1. Initialize workflow_state with workflow_id, status=RUNNING.
        2. For each step in plan.steps:
           a. PRE-step check:
              - all ABSOLUTE constraints satisfied?
              - identity unchanged or properly delegated from prior step?
              - drift.in_bounds is True?
              - geometry.stability_score above floor?
              If any fails → halt_for_violation → return HALTED result.
           b. Run step via agent_runner(step, context).
           c. POST-step check:
              - did the runner return a Violation indicator?
              - did drift recompute exceed bounds?
              If any fails → halt_for_violation → return HALTED result.
           d. checkpoint(workflow_state) → CheckpointToken.
           e. Build next PropagationState carrying C/D/G/I/S.
        3. After all steps succeed, return COMPLETED result.

    INVARIANTS:
        * Never auto-resumes past a halt.
        * Never mutates ``plan`` or ``context``.
        * Never skips a checkpoint between steps.
        * Final propagation carries the SAME identity that arrived
          (or a properly delegated descendant).

    #366 A5: the runner's outputs are the RUNNER's business (the kernel's
    closure keeps them); this function returns the workflow record only --
    the propagation (S) carrying C/D/G/I, with the PRE check reading D, G
    and I (C is a runner-reported fact, checked POST; there is no separate
    check of S, which is the record itself). An empty plan (a halted route)
    completes with zero checkpoints.
    """
    if not callable(agent_runner):
        raise ValueError("agent_runner must be callable")
    steps = tuple(plan.steps or ())
    workflow_id = _new_local_id()
    first = steps[0].step_id if steps else "<none>"
    propagation = _initial_propagation(plan, context, first)
    state: dict = {
        "workflow_id": workflow_id,
        "status": WorkflowStatus.RUNNING,
        "step_id": first,
        "propagation": propagation,
        "checkpoints": [],
    }
    for idx, step in enumerate(steps):
        state["step_id"] = step.step_id
        pre = _pre_check(step, context, propagation)
        if pre is not None:
            halt = halt_for_violation(state, pre)
            return WorkflowResult(workflow_id=workflow_id, status=WorkflowStatus.HALTED,
                                  final_propagation=propagation, checkpoints=tuple(state["checkpoints"]),
                                  halt_state=halt, completed_at=None)
        output = agent_runner(step, context)
        post = _post_check(step, output)
        if post is not None:
            halt = halt_for_violation(state, post)
            return WorkflowResult(workflow_id=workflow_id, status=WorkflowStatus.HALTED,
                                  final_propagation=propagation, checkpoints=tuple(state["checkpoints"]),
                                  halt_state=halt, completed_at=None)
        token = checkpoint(state)
        state["checkpoints"].append(token)
        nxt = steps[idx + 1].step_id if idx + 1 < len(steps) else "<end>"
        propagation = PropagationState(
            from_step=step.step_id,
            to_step=nxt,
            active_constraints=propagation.active_constraints,
            drift_state=propagation.drift_state,
            geometry_profile=propagation.geometry_profile,
            identity_profile=propagation.identity_profile,
            invariants_preserved=propagation.invariants_preserved,
        )
        state["propagation"] = propagation
    state["status"] = WorkflowStatus.COMPLETED
    return WorkflowResult(workflow_id=workflow_id, status=WorkflowStatus.COMPLETED,
                          final_propagation=propagation, checkpoints=tuple(state["checkpoints"]),
                          halt_state=None, completed_at=_now())


# ---------------------------------------------------------------------------
# checkpoint
# ---------------------------------------------------------------------------
def checkpoint(workflow_state: dict) -> CheckpointToken:
    """Capture a resumable snapshot at a step boundary.

    Args:
        workflow_state: the orchestrator's internal state for the current
                        workflow (workflow_id, current step_id, the
                        PropagationState just built, plus internal
                        bookkeeping).

    Returns:
        CheckpointToken referencing the PropagationState (which itself
        carries C/D/G/I/S).

    INVARIANT: ``token.propagation`` is a PropagationState that
    satisfies the structural contract (C/D/G/I/S all present).

    The orchestrator does NOT persist the token. Callers (gateway,
    cron, surface) decide whether to store it for resume.
    """
    if not isinstance(workflow_state, dict):
        raise ValueError("workflow_state must be a dict")
    prop = workflow_state.get("propagation")
    if not isinstance(prop, PropagationState):
        raise ValueError("workflow_state carries no PropagationState")
    wid = workflow_state.get("workflow_id")
    sid = workflow_state.get("step_id")
    if not isinstance(wid, str) or not wid or not isinstance(sid, str) or not sid:
        raise ValueError("workflow_state needs workflow_id and step_id")
    return CheckpointToken(workflow_id=wid, step_id=sid, propagation=prop)


# ---------------------------------------------------------------------------
# halt_for_violation
# ---------------------------------------------------------------------------
def halt_for_violation(
    workflow_state: dict,
    violation: Violation,
) -> HaltState:
    """Stop the workflow and produce a HaltState for human review.

    Args:
        workflow_state: the orchestrator's internal state at the moment
                        of violation.
        violation:      the detected Violation.

    Returns:
        HaltState carrying:
            * workflow_id
            * halted_at_step
            * violation
            * propagation_at_halt (PropagationState — C/D/G/I/S intact)
            * requires_human_override
            * halted_at (now UTC)

    INVARIANT: ``requires_human_override`` is True whenever
    ``violation.severity >= REQUIRED``. For ADVISORY violations
    the caller MAY continue after logging; for REQUIRED and ABSOLUTE
    the halt is binding until human override.

    The orchestrator does NOT self-resolve. It never retries. It never
    skips. The user / surface decides what happens next.
    """
    if not isinstance(workflow_state, dict):
        raise ValueError("workflow_state must be a dict")
    if not isinstance(violation, Violation):
        raise ValueError("violation must be a Violation")
    prop = workflow_state.get("propagation")
    if not isinstance(prop, PropagationState):
        raise ValueError("workflow_state carries no PropagationState")
    workflow_state["status"] = WorkflowStatus.HALTED
    return HaltState(
        workflow_id=str(workflow_state.get("workflow_id") or ""),
        halted_at_step=str(workflow_state.get("step_id") or violation.detected_at_step),
        violation=violation,
        propagation_at_halt=prop,
        requires_human_override=violation.severity in (Severity.REQUIRED, Severity.ABSOLUTE),
        halted_at=_now(),
    )
