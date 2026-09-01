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

import logging
from datetime import datetime, timezone
from typing import Optional

from orchestrator_schemas import (
    AgentBinding,
    AuthorizationTier,
    ConstitutionalConstraint,
    ExecutionPlan,
    EnforcementMode,
    ExecutionStep,
    IdentityProfile,
    RoutingDecision,
    RoutingRequest,
    Severity,
)

logger = logging.getLogger("clarityos.orchestrator.routing")

#: Sentinel for a decision that selected nothing. The docstring's own
#: contract: "If no agent qualifies -> returns a halt-on-route decision
#: (selected_agent='<halt>')". D5 -- a halt is a DIFFERENT KIND than a
#: selection, and a reader tells them apart without parsing prose.
HALT_AGENT: str = "<halt>"

#: What the schema cannot express, stated once rather than faked at each
#: use. AgentBinding carries agent_id / capabilities / authorized_tiers and
#: NO link to a constraint, so "this agent violates rule X" is not derivable
#: here. Mirrors the shadow-seam sentinel at app.py:6132 (_emophysics_shadow).
UNMAPPED: str = "unmapped"


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
    now = datetime.now(timezone.utc)

    # 0. In-scope constraints. Empty scope = system-wide; otherwise it
    #    applies when it names this request_type. EVERY in-scope constraint
    #    is attached, satisfying the locked invariant "NEVER drops
    #    constraints between decision and plan".
    in_scope = tuple(
        c for c in (constraints or ())
        if not getattr(c, "scope", ()) or req.request_type in getattr(c, "scope", ())
    )

    # 1. ABSOLUTE gate, resolved CONSERVATIVELY and for a stated reason.
    #
    #    The locked invariant is "NEVER selects an agent that violates an
    #    ABSOLUTE constraint". AgentBinding carries no constraint linkage
    #    (agent_id / capabilities / authorized_tiers only), so violation is
    #    NOT derivable from the schema -- and the schemas are locked and in
    #    production use by five modules, so this does not amend them.
    #
    #    Unable to prove non-violation, the invariant is satisfied the only
    #    honest way available: halt. Selecting anyway would assert a check
    #    that never ran.
    blocking = tuple(
        c for c in in_scope
        if getattr(c, "severity", None) == Severity.ABSOLUTE
        and getattr(c, "enforcement", None) == EnforcementMode.HALT
    )
    if blocking:
        return RoutingDecision(
            request_id=req.request_id,
            selected_agent=HALT_AGENT,
            rationale=(
                "absolute_halt_constraint rules=%d agent_violation_check=%s "
                "(AgentBinding carries no constraint linkage)"
                % (len(blocking), UNMAPPED)
            ),
            constraints_attached=in_scope,
            decided_at=now,
        )

    # 2. Tier filter -- an agent qualifies only if authorized for the
    #    caller's tier.
    tier = getattr(req.identity, "authorization_tier", None)
    eligible = tuple(
        a for a in (available_agents or ())
        if tier in (getattr(a, "authorized_tiers", ()) or ())
    )

    # 3. Capability match against request_type. Exact membership -- a fuzzy
    #    match would invent a ranking the registry does not carry.
    matched = tuple(a for a in eligible if req.request_type in (a.capabilities or ()))

    if not matched:
        return RoutingDecision(
            request_id=req.request_id,
            selected_agent=HALT_AGENT,
            rationale=(
                "no_agent_qualifies registered=%d tier_eligible=%d "
                "capability_matched=0 request_type=%s"
                % (len(available_agents or ()), len(eligible), req.request_type)
            ),
            constraints_attached=in_scope,
            decided_at=now,
        )

    # 4. Tie-break. The docstring names pressure_load, which arrives via
    #    context_hints in build_execution_plan and is NOT in this signature.
    #    Sorting by agent_id keeps the choice DETERMINISTIC and says so,
    #    rather than reading a geometry this function was never given.
    selected = sorted(matched, key=lambda a: a.agent_id)[0]
    return RoutingDecision(
        request_id=req.request_id,
        selected_agent=selected.agent_id,
        rationale=(
            "capability_match request_type=%s tier_eligible=%d matched=%d "
            "tiebreak=agent_id_lexicographic"
            % (req.request_type, len(eligible), len(matched))
        ),
        constraints_attached=in_scope,
        decided_at=now,
    )


# ---------------------------------------------------------------------------
# Shadow handoff log — §14.1 three-part shape
# ---------------------------------------------------------------------------
def log_shadow_handoff(
    req: RoutingRequest,
    decision: RoutingDecision,
    available_agents: tuple,
) -> dict:
    """Emit the routing handoff in the §14.1 three-part shape. Returns the
    payload for tests. NEVER raises to the caller.

    ★ SHADOW. This records a decision that NOTHING ACTS ON. No call path
    changes, no response differs. The point is to create the mounting
    point -- a server-side handoff is the only place an E/r ratio can be
    mounted, and today a browser tab calls two engines in sequence with no
    coordinator between them.

    Shape from AMENDMENT_14.1_forward_backward_geometry_v1:
        SIGNAL    what arrived, as it arrived
        INTERP    the reading, MARKED AS A READING
          FORWARD   actors intact -- what happened, who did it
          BACKWARD  actors STRIPPED -- effect to cause
          GEOMETRY  the invariant as a verb chain, portable

    §14.1's hard rule: GEOMETRY carries no proper noun and no
    system-specific term. If it cannot be written that way the backward
    read was not finished.

    Counts and enums only. The member's text never reaches this log --
    only its length, mirroring _emophysics_shadow (app.py:6132).
    """
    halted = decision.selected_agent == HALT_AGENT
    payload = {
        "signal": {
            "request_type":  req.request_type,
            "tier":          getattr(getattr(req, "identity", None),
                                     "authorization_tier", None),
            "payload_keys":  len(req.payload or {}),
            "agents_registered": len(available_agents or ()),
            "constraints_in_scope": len(decision.constraints_attached or ()),
        },
        "interp": {
            "reading": True,          # D4 -- a solved r, never an observation
            "forward":  ("the router received a request and selected no agent"
                         if halted else
                         "the router received a request and selected an agent"),
            "backward": ("no registry entry answered the capability, so the route "
                         "resolved to a halt" if halted else
                         "a registry entry answered the capability, so the route "
                         "resolved to that entry"),
            "geometry": ("demand arrives -> no supply answers -> the route halts "
                         "-> the caller proceeds unrouted" if halted else
                         "demand arrives -> supply answers -> the route binds "
                         "-> the caller proceeds routed"),
        },
        "decision": {
            "selected_agent": decision.selected_agent,
            "halted":         halted,
            "rationale":      decision.rationale,
        },
        "acted_on": False,            # SHADOW. Nothing routes on this.
        "computed": True,
    }
    try:
        logger.info("orchestrator_routing_shadow payload=%s", payload)
    except Exception:  # pragma: no cover - a log must never break a turn
        pass
    return payload


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
