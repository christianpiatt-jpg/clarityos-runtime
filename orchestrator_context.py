"""
orchestrator_context.py — Layer 2: Context (Minimal Orchestrator).

Assembles the C/D/G/I/S context envelope that travels with every
workflow step. The envelope is the only thing the workflow layer
sees — context assembly is the chokepoint where C/D/G/I/S come
together.

ROLE IN THE ARCHITECTURE
------------------------
Context is the C/D/G/I/S aggregator. It pulls constraints (already
attached by routing), identity (from the request), drift (computed
from history), and geometry (snapshotted at assembly time) into one
frozen envelope.

The context layer never calls LLMs. Never executes domain logic.
``load_drift_state`` is the only non-trivial computation here, and
it must be pure (no I/O, no network, no randomness).

PHASE STATUS
------------
Phase 1 skeleton — schemas locked in ``orchestrator_schemas.py``.
Function bodies raise ``NotImplementedError`` pending real
implementation.

PUBLIC API
----------
    assemble_context(req, plan, identity, drift, geometry)   -> ContextEnvelope
    attach_constraints(context, additional_constraints)      -> ContextEnvelope
    load_drift_state(actor, history, baseline_anchor, axis)  -> DriftState

INVARIANTS (locked, enforced by tests + design discipline)
----------------------------------------------------------
    * Constraints flow MONOTONICALLY — attach_constraints only ADDS.
    * Constraint weakening requires explicit human override; no
      programmatic relaxation in this layer.
    * load_drift_state is a pure function (deterministic given inputs).
    * Every returned ContextEnvelope satisfies the C/D/G/I structural
      contract (constraints + identity + drift + geometry all present).
"""
from __future__ import annotations

from typing import Optional

from orchestrator_schemas import (
    ContextEnvelope,
    ConstitutionalConstraint,
    DriftAxis,
    DriftState,
    ExecutionPlan,
    GeometryProfile,
    IdentityProfile,
    RoutingRequest,
)


# ---------------------------------------------------------------------------
# assemble_context
# ---------------------------------------------------------------------------
def assemble_context(
    req: RoutingRequest,
    plan: ExecutionPlan,
    identity: IdentityProfile,
    drift: DriftState,
    geometry: GeometryProfile,
) -> ContextEnvelope:
    """Gather the C/D/G/I/S inputs into one envelope.

    Args:
        req:      the routing request (immutable).
        plan:     the execution plan (immutable).
        identity: the identity profile attached at routing time.
        drift:    the drift state for this request (pre-computed via
                  ``load_drift_state``).
        geometry: the geometry snapshot at assembly time.

    Returns:
        ContextEnvelope carrying (constraints, identity, drift, geometry).

    INVARIANT: the returned envelope satisfies
    ``assert_context_contract`` — constraints + identity + drift +
    geometry are all present. Missing any one is a structural error.

    The ``constraints`` field is sourced from ``plan.overall_constraints``;
    plan-level constraints are authoritative at context-assembly time.
    """
    raise NotImplementedError(
        "orchestrator_context.assemble_context — Phase 2 implementation",
    )


# ---------------------------------------------------------------------------
# attach_constraints
# ---------------------------------------------------------------------------
def attach_constraints(
    context: ContextEnvelope,
    additional_constraints: tuple,
) -> ContextEnvelope:
    """Return a NEW envelope (frozen) with the union of existing +
    additional constraints.

    Used when a step locally adds constraints (e.g., a sensitive
    operation tightens limits beyond what was attached at routing time).

    Args:
        context:                the existing envelope.
        additional_constraints: tuple[ConstitutionalConstraint] to add.

    Returns:
        A new ContextEnvelope. The original is untouched.

    INVARIANT: constraint flow is MONOTONIC. This function only adds.
    To weaken constraints, an explicit human override path is required
    (out of scope for this layer).

    Deduplication: constraints with identical ``rule_id`` are deduped;
    if the same rule appears with different ``severity``, the HIGHER
    severity wins (defense-in-depth).
    """
    raise NotImplementedError(
        "orchestrator_context.attach_constraints — Phase 2 implementation",
    )


# ---------------------------------------------------------------------------
# load_drift_state
# ---------------------------------------------------------------------------
def load_drift_state(
    actor: str,
    history: tuple,
    baseline_anchor: str,
    axis: DriftAxis = DriftAxis.INTENT,
) -> DriftState:
    """Compute the current drift state for an actor against a baseline.

    Args:
        actor:           the actor whose drift is being measured.
        history:         tuple of prior action records (immutable).
        baseline_anchor: what the drift is measured against
                         (e.g., "session_start", "last_user_authz").
        axis:            which drift axis to measure (default INTENT).

    Returns:
        DriftState with:
            * ``magnitude`` in [0, 1]
            * ``in_bounds`` = (magnitude < DEFAULT_DRIFT_THRESHOLD)
            * ``measured_at`` = now (UTC)
            * ``direction`` = short human-readable summary

    INVARIANT: This function is PURE.
        * No I/O.
        * No network.
        * No randomness.
        * Deterministic given (actor, history, baseline_anchor, axis).

    Implementation guidance (Phase 2):
        * Different axes use different metrics:
            INTENT   — divergence between current request intent and
                       baseline (e.g., last user-authorized intent).
            TONE     — change in lexical tone markers.
            SCOPE    — expansion of touched-resource set vs baseline.
            IDENTITY — change in actor / delegation chain.
            TIMELINE — elapsed gap since baseline_anchor exceeds budget.
        * For Phase 2 v1, INTENT is the primary axis; others may
          return magnitude=0.0, in_bounds=True until later units add
          richer measurement.
    """
    raise NotImplementedError(
        "orchestrator_context.load_drift_state — Phase 2 implementation",
    )
