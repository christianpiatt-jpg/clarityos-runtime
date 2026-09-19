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
    DEFAULT_DRIFT_THRESHOLD,
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

    #366 A5 (R-366-D): implemented for the thread route. Type-checked, not
    reinterpreted: the envelope carries exactly what arrived.
    """
    if not isinstance(req, RoutingRequest):
        raise ValueError("req must be a RoutingRequest")
    if not isinstance(plan, ExecutionPlan):
        raise ValueError("plan must be an ExecutionPlan")
    if not isinstance(identity, IdentityProfile):
        raise ValueError("identity must be an IdentityProfile")
    if not isinstance(drift, DriftState):
        raise ValueError("drift must be a DriftState")
    if not isinstance(geometry, GeometryProfile):
        raise ValueError("geometry must be a GeometryProfile")
    env = ContextEnvelope(
        request=req,
        plan=plan,
        constraints=tuple(plan.overall_constraints or ()),
        identity=identity,
        drift=drift,
        geometry=geometry,
    )
    from orchestrator_schemas import assert_context_contract
    assert_context_contract()
    return env


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

    #366 A5 (R-366-D): the INTENT axis is implemented for the thread route.
    ``history`` is the tuple of the relationship's prior DIRECTION bits
    (query · action · plan · diagnostic), oldest first; ``baseline_anchor``
    is this turn's direction. magnitude = the share of the last
    ``DRIFT_WINDOW`` prior bits that differ from it -- a pure count, no
    clock, no store.

    ★ CARRIED, NOT GATED. ``in_bounds`` is True on this axis whatever the
    magnitude: the direction bit is the member's own authorization (R-366-B),
    so a member who picks ``action`` after three ``query`` turns has not
    drifted from anything the orchestrator may hold them to -- the first
    draft halted that turn with zero lanes sent (refuter, 2026-09-19). The
    measure rides ``magnitude`` / ``direction`` for a later reader; the
    workflow's D check reads ``in_bounds``. Every other axis keeps raising:
    the route does not exercise it, and a 0.0 it never measured would be a
    value where the honest answer is "unread" (D5).
    """
    if axis != DriftAxis.INTENT:
        raise NotImplementedError(
            "orchestrator_context.load_drift_state — axis %s is not exercised by the thread route (#366 R-366-D)" % axis,
        )
    if not isinstance(actor, str) or not actor:
        raise ValueError("actor must be a non-empty string")
    if not isinstance(baseline_anchor, str) or not baseline_anchor:
        raise ValueError("baseline_anchor must be a non-empty string")
    bits = tuple(h for h in (history or ()) if isinstance(h, str) and h)
    window = bits[-DRIFT_WINDOW:]
    if not window:
        magnitude = 0.0
        direction = "no prior turn"
    else:
        differing = sum(1 for b in window if b != baseline_anchor)
        magnitude = round(differing / float(len(window)), 4)
        direction = ("stable" if differing == 0 else ("shifting %d/%d" % (differing, len(window)))) + " (member-authorized; not gated)"
    from datetime import datetime, timezone
    return DriftState(
        axis=DriftAxis.INTENT,
        magnitude=magnitude,
        direction=direction,
        baseline_anchor=baseline_anchor,
        in_bounds=True,
        measured_at=datetime.now(timezone.utc),
    )


#: how many prior direction bits the INTENT drift reads (a bootstrap
#: number, like the record's 3 and 7 -- named, not physics)
DRIFT_WINDOW: int = 8
