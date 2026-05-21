"""
orchestrator_schemas.py — Minimal Orchestrator shared schemas + invariants.

The single source of truth for the data types used by:
    * orchestrator_routing.py    (Layer 1: routing + plan)
    * orchestrator_context.py    (Layer 2: context + constraints + drift)
    * orchestrator_workflows.py  (Layer 3: run + checkpoint + halt)

C/D/G/I/S CONTRACT
------------------
The five letters of the minimal-orchestrator design map directly to
five frozen dataclasses:

    C — ConstitutionalConstraint   (hard runtime constraints)
    D — DriftState                 (runtime drift measurement)
    G — GeometryProfile            (structural shape of system state)
    I — IdentityProfile            (who is acting, with what authz)
    S — PropagationState           (state that flows between steps)

The structural invariant: ``PropagationState.__dataclass_fields__``
MUST contain references to all five letters. Without all five, state
cannot propagate. This is checked at module load via
``assert_propagation_contract()`` and asserted by the test suite.

MINIMALITY CONTRACT
-------------------
This module never:
    * imports LLM libraries
    * imports network libraries (no http, no urllib at top level)
    * defines mutable global state
    * defines functions that mutate input objects

All schemas are frozen dataclasses. All categorical types are enums.

See SPEC_ORCHESTRATOR.md for the full specification.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ===========================================================================
# Categorical types — canonical, locked
# ===========================================================================
class Severity(str, Enum):
    """How strictly a ConstitutionalConstraint must be enforced."""
    ADVISORY = "advisory"   # log but proceed
    REQUIRED = "required"   # must satisfy unless explicit human override
    ABSOLUTE = "absolute"   # never bypassable


class EnforcementMode(str, Enum):
    """What the workflow does when a constraint trips."""
    ALLOW_WITH_WARNING     = "allow_with_warning"
    HALT                   = "halt"
    REQUIRE_HUMAN_OVERRIDE = "require_human_override"


class DriftAxis(str, Enum):
    """Which dimension drift is measured along."""
    INTENT   = "intent"
    TONE     = "tone"
    SCOPE    = "scope"
    IDENTITY = "identity"
    TIMELINE = "timeline"


class ActorKind(str, Enum):
    """Categorical type of the acting party."""
    USER   = "user"
    AGENT  = "agent"
    SYSTEM = "system"


class SovereigntyLevel(str, Enum):
    """Whose authority underlies this action."""
    USER_OWNED = "user_owned"   # user is in direct control
    DELEGATED  = "delegated"    # acting on user's prior authorization
    AGENT_ONLY = "agent_only"   # system-initiated, no user authority


class AuthorizationTier(str, Enum):
    """Capability tier ordered by privilege."""
    READ    = "read"      # observe only
    OBSERVE = "observe"   # observe + record
    PROPOSE = "propose"   # propose actions for human review
    EXECUTE = "execute"   # execute (requires explicit user authz)


class WorkflowStatus(str, Enum):
    """Terminal + transitional workflow states."""
    PENDING              = "pending"
    RUNNING              = "running"
    COMPLETED            = "completed"
    HALTED               = "halted"
    PENDING_HUMAN_REVIEW = "pending_human_review"


# ===========================================================================
# Constants
# ===========================================================================
# Default drift bound. DriftState.in_bounds is True iff magnitude < this.
DEFAULT_DRIFT_THRESHOLD: float = 0.5

# Canonical names of invariants tracked through PropagationState.
INVARIANTS_CANONICAL: tuple = (
    "constitutional_constraints_intact",
    "drift_within_bounds",
    "geometry_within_stability_budget",
    "identity_unchanged_or_delegated",
    "no_constraint_dropped",
)


# ===========================================================================
# Local-only id generator
# ===========================================================================
def _new_local_id() -> str:
    """Generate a local-only id. NEVER uploaded. Used for in-process
    cross-references (workflow_id, propagation_id, snapshot_id)."""
    return secrets.token_urlsafe(12)


# ===========================================================================
# C — ConstitutionalConstraint
# ===========================================================================
@dataclass(frozen=True)
class ConstitutionalConstraint:
    """A hard runtime rule the orchestrator enforces.

    A constraint is fully specified by its rule_id; the orchestrator does
    not interpret the statement text — that's for the surface to display
    to humans. The orchestrator routes off rule_id + severity +
    enforcement.
    """
    rule_id:     str
    statement:   str
    severity:    Severity
    enforcement: EnforcementMode
    scope:       tuple = ()         # tuple of route/workflow names
    rationale:   str   = ""


# ===========================================================================
# D — DriftState
# ===========================================================================
@dataclass(frozen=True)
class DriftState:
    """Current drift measurement on a single axis.

    The orchestrator measures drift; the user (or a higher layer)
    decides what to DO about drift. ``in_bounds`` is the structural
    signal — when False, ABSOLUTE constraint "drift_within_bounds"
    is violated.
    """
    axis:            DriftAxis
    magnitude:       float           # [0, 1]
    direction:       str             # human-readable
    baseline_anchor: str             # what we're measuring against
    in_bounds:       bool
    measured_at:     datetime


# ===========================================================================
# G — GeometryProfile
# ===========================================================================
@dataclass(frozen=True)
class GeometryProfile:
    """Structural shape of the system state at a moment.

    Used by routing to tie-break (prefer lower pressure_load) and by
    workflows to detect structural instability (stability_score drop).
    """
    depth:           int             # workflow nesting depth
    breadth:         int             # active concurrent steps
    pressure_load:   float           # [0, 1]
    stability_score: float           # [0, 1], higher is more stable
    captured_at:     datetime


# ===========================================================================
# I — IdentityProfile
# ===========================================================================
@dataclass(frozen=True)
class IdentityProfile:
    """Who is acting, with what authority.

    PRIVACY: session_id is local-only and NEVER uploaded.
    """
    actor:              str
    actor_kind:         ActorKind
    sovereignty_level:  SovereigntyLevel
    authorization_tier: AuthorizationTier
    delegated_from:     Optional[str] = None
    session_id:         str           = ""


# ===========================================================================
# S — PropagationState
# ===========================================================================
@dataclass(frozen=True)
class PropagationState:
    """State that flows between workflow steps.

    STRUCTURAL INVARIANT (test-enforced):
        __dataclass_fields__ MUST contain
            active_constraints   (C)
            drift_state          (D)
            geometry_profile     (G)
            identity_profile     (I)
            invariants_preserved (S — list of invariant names verified)
        Removing any one of these fails the test suite and the
        ``assert_propagation_contract`` runtime guard.
    """
    from_step:            str
    to_step:              str
    active_constraints:   tuple                    # C — tuple of ConstitutionalConstraint
    drift_state:          DriftState               # D
    geometry_profile:     GeometryProfile          # G
    identity_profile:     IdentityProfile          # I
    invariants_preserved: tuple                    # S — tuple of invariant names
    propagation_id:       str = field(default_factory=_new_local_id)


# ===========================================================================
# Supporting types — routing
# ===========================================================================
@dataclass(frozen=True)
class RoutingRequest:
    """Incoming request to the orchestrator."""
    request_id:   str
    request_type: str
    payload:      dict
    identity:     IdentityProfile
    arrived_at:   datetime


@dataclass(frozen=True)
class RoutingDecision:
    """Output of route_request — which agent + which constraints."""
    request_id:           str
    selected_agent:       str
    rationale:            str
    constraints_attached: tuple                      # tuple[ConstitutionalConstraint]
    decided_at:           datetime


@dataclass(frozen=True)
class AgentBinding:
    """An entry in the agent registry."""
    agent_id:         str
    capabilities:     tuple                          # tuple[str]
    authorized_tiers: tuple                          # tuple[AuthorizationTier]


@dataclass(frozen=True)
class ExecutionStep:
    """One step in an execution plan."""
    step_id:     str
    action:      str
    inputs:      dict
    constraints: tuple                               # step-local constraint subset


@dataclass(frozen=True)
class ExecutionPlan:
    """The step sequence the chosen agent will perform."""
    plan_id:             str
    steps:               tuple                       # tuple[ExecutionStep]
    overall_constraints: tuple                       # tuple[ConstitutionalConstraint]
    created_at:          datetime


# ===========================================================================
# Supporting types — context
# ===========================================================================
@dataclass(frozen=True)
class ContextEnvelope:
    """The envelope passed to workflow execution.

    STRUCTURAL INVARIANT (test-enforced):
        Carries (constraints, identity, drift, geometry).
        Missing any of these is a structural error.
    """
    request:     RoutingRequest
    plan:        ExecutionPlan
    constraints: tuple                               # C
    identity:    IdentityProfile                     # I
    drift:       DriftState                          # D
    geometry:    GeometryProfile                     # G


# ===========================================================================
# Supporting types — workflows
# ===========================================================================
@dataclass(frozen=True)
class Violation:
    """A constraint violation detected at a step boundary."""
    constraint_id:    str
    severity:         Severity
    detected_at_step: str
    description:      str
    detected_at:      datetime


@dataclass(frozen=True)
class CheckpointToken:
    """Resumable snapshot at a step boundary.

    The orchestrator does NOT persist tokens — calling surfaces decide
    whether to store them for resume.
    """
    workflow_id: str
    step_id:     str
    propagation: PropagationState
    snapshot_id: str = field(default_factory=_new_local_id)


@dataclass(frozen=True)
class HaltState:
    """What halt_for_violation produces.

    INVARIANT: requires_human_override is True whenever
    violation.severity >= REQUIRED.
    """
    workflow_id:             str
    halted_at_step:          str
    violation:               Violation
    propagation_at_halt:     PropagationState
    requires_human_override: bool
    halted_at:               datetime


@dataclass(frozen=True)
class WorkflowResult:
    """Terminal product of run_workflow.

    INVARIANT: final_propagation satisfies the PropagationState
    structural contract.
    """
    workflow_id:       str
    status:            WorkflowStatus
    final_propagation: PropagationState
    checkpoints:       tuple                         # tuple[CheckpointToken]
    halt_state:        Optional[HaltState] = None
    completed_at:      Optional[datetime]  = None


# ===========================================================================
# Module-level structural guards
# ===========================================================================
# Required fields on PropagationState — the C/D/G/I/S contract.
_REQUIRED_PROPAGATION_FIELDS: frozenset = frozenset({
    "active_constraints",
    "drift_state",
    "geometry_profile",
    "identity_profile",
    "invariants_preserved",
})

# Required fields on ContextEnvelope — C/D/G/I (S is implicit at run time).
_REQUIRED_CONTEXT_FIELDS: frozenset = frozenset({
    "constraints",
    "identity",
    "drift",
    "geometry",
})


def assert_propagation_contract() -> None:
    """Runtime guard — raises AssertionError if PropagationState has
    dropped one of the canonical C/D/G/I/S fields. Tests call this; it
    is also safe to call at module-load time in development.
    """
    fields_set = set(PropagationState.__dataclass_fields__.keys())
    missing = _REQUIRED_PROPAGATION_FIELDS - fields_set
    assert not missing, (
        f"PropagationState C/D/G/I/S contract violated — missing fields: {missing}"
    )


def assert_context_contract() -> None:
    """Runtime guard — raises AssertionError if ContextEnvelope has
    dropped one of (constraints, identity, drift, geometry).
    """
    fields_set = set(ContextEnvelope.__dataclass_fields__.keys())
    missing = _REQUIRED_CONTEXT_FIELDS - fields_set
    assert not missing, (
        f"ContextEnvelope C/D/G/I contract violated — missing fields: {missing}"
    )


def assert_minimal_orchestrator_contract() -> None:
    """Composite guard. Runs all structural contracts. Tests call this
    as a final structural check."""
    assert_propagation_contract()
    assert_context_contract()


# Run the guards at module load time so a structurally broken edit
# fails import (defense in depth — tests still re-verify).
assert_minimal_orchestrator_contract()
