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
Phase 1 skeleton — schemas locked in ``orchestrator_schemas.py``.
Function bodies raise ``NotImplementedError`` pending real
implementation.

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

from typing import Callable, Optional

from orchestrator_schemas import (
    CheckpointToken,
    ContextEnvelope,
    ExecutionPlan,
    HaltState,
    PropagationState,
    Severity,
    Violation,
    WorkflowResult,
    WorkflowStatus,
)


# Type alias for the agent runner the workflow invokes per step.
# The orchestrator does not implement this — callers (gateway, tests)
# supply a runner that knows how to invoke the agent for one
# ExecutionStep given the current ContextEnvelope.
AgentRunner = Callable[..., dict]


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
    """
    raise NotImplementedError(
        "orchestrator_workflows.run_workflow — Phase 2 implementation",
    )


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
    raise NotImplementedError(
        "orchestrator_workflows.checkpoint — Phase 2 implementation",
    )


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
    raise NotImplementedError(
        "orchestrator_workflows.halt_for_violation — Phase 2 implementation",
    )
