"""
orchestrator_routing.py — Layer 1: Routing (Minimal Orchestrator).

The first layer of the C/D/G/I/S orchestrator. Given an incoming
``RoutingRequest``, selects exactly one agent and builds an
``ExecutionPlan`` whose steps carry the constraints active for the
chosen path.

ROLE IN THE ARCHITECTURE
------------------------
Routing is the C-first dispatcher. ABSOLUTE-severity constraints
filter the agent set BEFORE any capability match runs. Identity tier
filters BEFORE capability match. Capability match scores remaining
agents; geometry (pressure_load) tie-breaks.

The routing layer never calls LLMs. Never executes domain logic.
Never owns long-term state. Pure routing decision.

PHASE STATUS
------------
Phase 1 skeleton — schemas locked in ``orchestrator_schemas.py``.
Function bodies raise ``NotImplementedError`` pending real
implementation.

PUBLIC API
----------
    route_request(req, available_agents, constraints)        -> RoutingDecision
    select_agent(request_type, identity, constraints, agents) -> AgentBinding
    build_execution_plan(decision, context_hints)            -> ExecutionPlan

INVARIANTS (locked, enforced by tests + design discipline)
----------------------------------------------------------
    * NEVER selects an agent that violates an ABSOLUTE constraint.
    * NEVER drops constraints between RoutingDecision and ExecutionPlan.
    * NEVER mutates the input RoutingRequest.
    * Output ExecutionPlan.overall_constraints ⊇ union of step constraints.
"""
from __future__ import annotations

from typing import Optional

from orchestrator_schemas import (
    AgentBinding,
    AuthorizationTier,
    ConstitutionalConstraint,
    ExecutionPlan,
    ExecutionStep,
    IdentityProfile,
    RoutingDecision,
    RoutingRequest,
    Severity,
)


# ---------------------------------------------------------------------------
# route_request
# ---------------------------------------------------------------------------
def route_request(
    req: RoutingRequest,
    available_agents: tuple,
    constraints: tuple,
) -> RoutingDecision:
    """Resolve an incoming request to a single selected agent.

    Args:
        req:              the incoming RoutingRequest (immutable).
        available_agents: tuple[AgentBinding] of registered agents.
        constraints:      tuple[ConstitutionalConstraint] active at this
                          moment (system-wide + request-specific).

    Returns:
        RoutingDecision carrying the selected agent + the constraint set
        that travels with the plan.

    Algorithm (Phase-2 implementation):
        1. Filter ``available_agents`` to those whose ``authorized_tiers``
           contain ``req.identity.authorization_tier``.
        2. Drop any agent that violates any ABSOLUTE-severity constraint.
        3. Score remaining agents by capability match against
           ``req.request_type``.
        4. Tie-break by lowest pressure_load (geometry-aware — caller
           passes geometry via context_hints in build_execution_plan).
        5. Emit RoutingDecision with rationale + attached constraints.

    INVARIANTS:
        * Never selects an agent that violates an ABSOLUTE constraint.
        * Never mutates ``req``.
        * If no agent qualifies → returns a halt-on-route decision
          (selected_agent="<halt>", rationale describes the gap).
    """
    raise NotImplementedError(
        "orchestrator_routing.route_request — Phase 2 implementation",
    )


# ---------------------------------------------------------------------------
# select_agent
# ---------------------------------------------------------------------------
def select_agent(
    request_type: str,
    identity: IdentityProfile,
    constraints: tuple,
    agents: tuple,
) -> Optional[AgentBinding]:
    """Agent-registry lookup.

    Returns the AgentBinding that best fits the (request_type, identity
    tier, constraint set) tuple, or None if no agent qualifies.

    Used internally by ``route_request``; exposed for tests + alternative
    routing strategies.

    INVARIANT: returned agent satisfies every ABSOLUTE constraint.
    """
    raise NotImplementedError(
        "orchestrator_routing.select_agent — Phase 2 implementation",
    )


# ---------------------------------------------------------------------------
# build_execution_plan
# ---------------------------------------------------------------------------
def build_execution_plan(
    decision: RoutingDecision,
    context_hints: Optional[dict] = None,
) -> ExecutionPlan:
    """Construct the step sequence for the chosen agent.

    Args:
        decision:      the RoutingDecision from ``route_request``.
        context_hints: optional dict of hints (e.g., prior drift,
                       geometry snapshot, user-supplied scope limits).

    Returns:
        ExecutionPlan with:
            * ``steps``               — tuple[ExecutionStep]
            * ``overall_constraints`` — union of step constraints +
                                        ``decision.constraints_attached``

    INVARIANT: ``plan.overall_constraints`` is a SUPERSET of every
    ``step.constraints``. No constraint is silently dropped between
    routing and plan.
    """
    raise NotImplementedError(
        "orchestrator_routing.build_execution_plan — Phase 2 implementation",
    )
