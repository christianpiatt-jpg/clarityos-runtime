# Orchestrator — Specification

**Status:** Phase 3 design. Schemas locked. Module skeletons land in this commit.
Real implementation deferred to a subsequent unit once the spec is reviewed.

**Date:** 2026-05-11
**Discipline:** *Minimal orchestrator* — only what's needed to enforce
**C/D/G/I/S** at runtime.

---

## 1. Purpose

The Orchestrator is the **runtime conscience** of ClarityOS.

Its single job: enforce the five invariants — **C** (Constitutional),
**D** (Drift), **G** (Geometry), **I** (Identity), **S** (Propagation) —
at every workflow step, on every routing decision, in every context
assembly.

It is **not** a planner. It is **not** an LLM caller. It is **not** a
domain executor. It is the thin layer that asks, at every boundary:

> "Is this allowed (C)? How far has it drifted (D)? What's the structural
> load (G)? Whose identity is acting (I)? What state propagates from
> here (S)?"

When any answer fails the constraint set, the orchestrator **halts and
surfaces** — never silently corrects, never auto-resumes, never decides
on the user's behalf.

---

## 2. The C/D/G/I/S Principle

**Minimal orchestrator** is defined by what it *doesn't* do.

Every line of code in this module must justify itself against:

> *"Is this needed to enforce C/D/G/I/S at runtime?"*

If the answer is no, it belongs in a domain module (Azimuth, ELINS,
news basin, daily ELINS), in an agent's own implementation, in a
storage module, or in a UI surface — **not** in the orchestrator.

The five letters bind concrete schemas:

| Letter | Concept       | Schema                     |
|:------:|:--------------|:---------------------------|
| C      | Constitutional | `ConstitutionalConstraint` |
| D      | Drift          | `DriftState`               |
| G      | Geometry       | `GeometryProfile`          |
| I      | Identity       | `IdentityProfile`          |
| S      | Propagation    | `PropagationState`         |

The `PropagationState` schema is the structural enforcement point: it
**must** carry references to all five letters. Without all five
present, state cannot propagate. This is checked at module load.

---

## 3. What the Orchestrator Does NOT Do

Negative space — explicit list of things the orchestrator must
never grow into:

1. **Does NOT call LLMs.** Period. Routing decides which agent gets the
   call; the agent calls.
2. **Does NOT execute domain logic.** No ELINS, no reframing, no news
   aggregation. Those live in their modules.
3. **Does NOT own long-term state.** It consumes external state
   (operator_state, ingestion bus, library archives) read-only.
4. **Does NOT own credentials.** Auth lives in the gateway layer.
5. **Does NOT store user data.** Identity is forwarded, not retained.
6. **Does NOT auto-correct drift.** It detects + halts; the user
   decides how to correct.
7. **Does NOT censor.** Same as Azimuth — may warn (constraint
   violation), never block content semantically.
8. **Does NOT auto-resume after a halt.** Every halt requires explicit
   human override.
9. **Does NOT mutate input requests.** Routing emits decisions, never
   in-place rewrites.
10. **Does NOT serve UI.** Surfaces consume orchestrator outputs; they
    do not embed inside it.

---

## 4. Three-Layer Architecture

```
                          ╔═══════════════════════════╗
                          ║   external request        ║
                          ║   (web / phone / cron)    ║
                          ╚════════╤══════════════════╝
                                   │
                          ┌────────┴───────────────────┐
                          │   LAYER 1 — ROUTING        │
                          │   route_request            │
                          │   select_agent             │
                          │   build_execution_plan     │
                          └────────┬───────────────────┘
                                   │  RoutingDecision + ExecutionPlan
                          ┌────────┴───────────────────┐
                          │   LAYER 2 — CONTEXT        │
                          │   assemble_context         │
                          │   attach_constraints       │
                          │   load_drift_state         │
                          └────────┬───────────────────┘
                                   │  ContextEnvelope (carries C/D/G/I/S)
                          ┌────────┴───────────────────┐
                          │   LAYER 3 — WORKFLOWS      │
                          │   run_workflow             │
                          │   checkpoint               │
                          │   halt_for_violation       │
                          └────────┬───────────────────┘
                                   │  WorkflowResult | HaltState
                                   ▼
                          ┌────────────────────────────┐
                          │   downstream agent /       │
                          │   surface / store          │
                          └────────────────────────────┘
```

Each layer has a single role and consumes the output of the previous.

---

## 5. Schemas (canonical)

The single source of truth is `orchestrator_schemas.py`. Every schema
is a frozen dataclass; every category is an enum.

### 5.1 Categorical types

```python
class Severity(str, Enum):
    ADVISORY = "advisory"   # log but proceed
    REQUIRED = "required"   # must satisfy unless human override
    ABSOLUTE = "absolute"   # never bypassable

class EnforcementMode(str, Enum):
    ALLOW_WITH_WARNING     = "allow_with_warning"
    HALT                   = "halt"
    REQUIRE_HUMAN_OVERRIDE = "require_human_override"

class DriftAxis(str, Enum):
    INTENT   = "intent"
    TONE     = "tone"
    SCOPE    = "scope"
    IDENTITY = "identity"
    TIMELINE = "timeline"

class ActorKind(str, Enum):
    USER   = "user"
    AGENT  = "agent"
    SYSTEM = "system"

class SovereigntyLevel(str, Enum):
    USER_OWNED = "user_owned"
    DELEGATED  = "delegated"
    AGENT_ONLY = "agent_only"

class AuthorizationTier(str, Enum):
    READ    = "read"      # observe only
    OBSERVE = "observe"   # observe + record
    PROPOSE = "propose"   # propose actions for human review
    EXECUTE = "execute"   # execute (requires explicit user authz)

class WorkflowStatus(str, Enum):
    PENDING            = "pending"
    RUNNING            = "running"
    COMPLETED          = "completed"
    HALTED             = "halted"
    PENDING_HUMAN_REVIEW = "pending_human_review"
```

### 5.2 The five core C/D/G/I/S schemas

```python
# C — Constitutional
@dataclass(frozen=True)
class ConstitutionalConstraint:
    rule_id:     str
    statement:   str                # human-readable rule
    severity:    Severity
    enforcement: EnforcementMode
    scope:       tuple[str, ...]    # routes/workflows it applies to
    rationale:   str

# D — Drift
@dataclass(frozen=True)
class DriftState:
    axis:            DriftAxis
    magnitude:       float          # [0, 1]
    direction:       str            # human-readable
    baseline_anchor: str            # what we measure against
    in_bounds:       bool
    measured_at:     datetime

# G — Geometry
@dataclass(frozen=True)
class GeometryProfile:
    depth:           int            # workflow nesting depth
    breadth:         int            # active concurrent steps
    pressure_load:   float          # [0, 1]
    stability_score: float          # [0, 1], higher = more stable
    captured_at:     datetime

# I — Identity
@dataclass(frozen=True)
class IdentityProfile:
    actor:              str         # who is acting
    actor_kind:         ActorKind
    sovereignty_level:  SovereigntyLevel
    authorization_tier: AuthorizationTier
    delegated_from:     Optional[str] = None
    session_id:         str = ""    # local; never uploaded

# S — Propagation
@dataclass(frozen=True)
class PropagationState:
    """STRUCTURAL INVARIANT: must reference C/D/G/I/S.
    Without all five present, this state isn't fit to propagate."""
    from_step:           str
    to_step:             str
    active_constraints:  tuple[ConstitutionalConstraint, ...]   # C
    drift_state:         DriftState                             # D
    geometry_profile:    GeometryProfile                        # G
    identity_profile:    IdentityProfile                        # I
    invariants_preserved: tuple[str, ...]                       # S
    propagation_id:      str
```

**Structural property:** `PropagationState.__dataclass_fields__` MUST
contain `active_constraints`, `drift_state`, `geometry_profile`,
`identity_profile`, `invariants_preserved`. The test suite asserts
this. Any future PR that removes one of these fails the suite.

### 5.3 Supporting types (routing / context / workflows)

```python
@dataclass(frozen=True)
class RoutingRequest:
    request_id:   str
    request_type: str
    payload:      dict
    identity:     IdentityProfile
    arrived_at:   datetime

@dataclass(frozen=True)
class RoutingDecision:
    request_id:           str
    selected_agent:       str
    rationale:            str
    constraints_attached: tuple[ConstitutionalConstraint, ...]
    decided_at:           datetime

@dataclass(frozen=True)
class AgentBinding:
    agent_id:         str
    capabilities:     tuple[str, ...]
    authorized_tiers: tuple[AuthorizationTier, ...]

@dataclass(frozen=True)
class ExecutionStep:
    step_id:     str
    action:      str
    inputs:      dict
    constraints: tuple[ConstitutionalConstraint, ...]

@dataclass(frozen=True)
class ExecutionPlan:
    plan_id:             str
    steps:               tuple[ExecutionStep, ...]
    overall_constraints: tuple[ConstitutionalConstraint, ...]
    created_at:          datetime

@dataclass(frozen=True)
class ContextEnvelope:
    request:     RoutingRequest
    plan:        ExecutionPlan
    constraints: tuple[ConstitutionalConstraint, ...]
    identity:    IdentityProfile
    drift:       DriftState
    geometry:    GeometryProfile

@dataclass(frozen=True)
class Violation:
    constraint_id:    str
    severity:         Severity
    detected_at_step: str
    description:      str
    detected_at:      datetime

@dataclass(frozen=True)
class CheckpointToken:
    workflow_id: str
    step_id:     str
    propagation: PropagationState
    snapshot_id: str

@dataclass(frozen=True)
class HaltState:
    workflow_id:             str
    halted_at_step:          str
    violation:               Violation
    propagation_at_halt:     PropagationState
    requires_human_override: bool
    halted_at:               datetime

@dataclass(frozen=True)
class WorkflowResult:
    workflow_id:       str
    status:            WorkflowStatus
    final_propagation: PropagationState
    checkpoints:       tuple[CheckpointToken, ...]
    halt_state:        Optional[HaltState]
    completed_at:      Optional[datetime]
```

---

## 6. Layer Behaviors

### 6.1 Layer 1 — Routing (`orchestrator_routing.py`)

**`route_request(req, available_agents, constraints) → RoutingDecision`**

Resolves an incoming `RoutingRequest` to a single selected agent.

Algorithm (skeleton):
1. Filter `available_agents` to those whose `authorized_tiers`
   contain `req.identity.authorization_tier`.
2. Apply ABSOLUTE-severity constraints — any agent that violates
   one is dropped.
3. Score remaining agents by capability match against `req.request_type`.
4. Tie-break by lowest `pressure_load` (geometry-aware).
5. Emit `RoutingDecision` with rationale + the attached constraint set.

INVARIANT: never returns an agent that violates an `ABSOLUTE` constraint.

**`select_agent(request_type, identity, constraints) → AgentBinding`**

The agent-registry lookup. Returns the binding that best fits the
type + identity tier + constraint set. Used by `route_request`.

**`build_execution_plan(route, context_hints) → ExecutionPlan`**

Constructs the step sequence the chosen agent will perform. Each
`ExecutionStep` carries the constraints active for that step (a
subset of `RoutingDecision.constraints_attached`, plus any
step-specific constraints).

INVARIANT: `plan.overall_constraints` is the union of step-level
constraints — no constraint can be silently dropped between routing
and plan.

### 6.2 Layer 2 — Context (`orchestrator_context.py`)

**`assemble_context(req, plan, identity, drift, geometry) → ContextEnvelope`**

Gathers the C/D/G/I/S inputs into one envelope. The envelope is the
*only* thing passed to workflow execution.

INVARIANT: `ContextEnvelope` carries all of (constraints, identity,
drift, geometry). Missing any of them is a structural error.

**`attach_constraints(context, additional_constraints) → ContextEnvelope`**

Returns a new envelope (frozen) with the union of existing +
additional constraints. Used when a step locally adds constraints
(e.g., a sensitive operation tightens limits).

INVARIANT: never *removes* constraints, only adds. Constraints flow
monotonically; weakening requires explicit human override.

**`load_drift_state(actor, history, baseline) → DriftState`**

Computes the current drift state for an actor against a baseline,
given a history of recent actions. Pure function; deterministic.

INVARIANT: `DriftState.in_bounds` is `True` iff `magnitude <
DRIFT_THRESHOLD` (default 0.5).

### 6.3 Layer 3 — Workflows (`orchestrator_workflows.py`)

**`run_workflow(plan, context, agent_runner) → WorkflowResult`**

Executes the plan step by step, invoking `agent_runner` per step.

At **every step boundary**:

1. **Pre-step check**:
   - All `ABSOLUTE` constraints satisfied?
   - Identity unchanged from prior step (or properly delegated)?
   - Drift in bounds?
   - Geometry within stability budget?
   If any fails → `halt_for_violation`.

2. **Run step** via `agent_runner(step, context)`.

3. **Post-step check**:
   - Did the step emit a `Violation`?
   - Did drift exceed bounds?
   If yes → `halt_for_violation`.

4. **Checkpoint** via `checkpoint(workflow_state)`.

5. **Build PropagationState** carrying C/D/G/I/S for the next step.

INVARIANTS:
- Never auto-resumes past a halt.
- Never mutates `plan` or `context`.
- Never skips a checkpoint.
- The workflow result's `final_propagation` carries the same
  identity that arrived in the request (or a properly delegated
  descendant).

**`checkpoint(workflow_state) → CheckpointToken`**

Captures a resumable state at a step boundary. The token is local;
the orchestrator does not persist long-term — a calling surface
(e.g., the gateway) is responsible for storing the token if a
resumable workflow is needed.

**`halt_for_violation(workflow_state, violation) → HaltState`**

Stops the workflow and produces a `HaltState`. The halt is
**always** surfaced for human review. The orchestrator never
self-resolves a violation.

INVARIANT: `HaltState.requires_human_override` is `True` whenever
`violation.severity >= REQUIRED`. For `ADVISORY` violations the
workflow may continue after logging.

---

## 7. Interaction Flow

```
EXTERNAL REQUEST
  │  RoutingRequest(request_type="elins_run", identity=…)
  ▼
ROUTING.route_request(req, agents, constraints)
  ─► RoutingDecision(selected_agent="elins_agent",
                     constraints_attached=(C1, C2, …))
  │
  ▼
ROUTING.build_execution_plan(decision, hints)
  ─► ExecutionPlan(steps=(s1, s2, s3),
                   overall_constraints=(C1, C2, …))
  │
  ▼
CONTEXT.load_drift_state(actor, history, baseline)
  ─► DriftState(axis=INTENT, magnitude=0.18, in_bounds=True)
  │
  ▼
CONTEXT.assemble_context(req, plan, identity, drift, geometry)
  ─► ContextEnvelope(constraints=(C1, C2, …),
                     identity=I, drift=D, geometry=G)
  │
  ▼
WORKFLOW.run_workflow(plan, context, agent_runner)
  │
  ├─ pre-check s1   → OK
  ├─ agent_runner(s1, ctx)
  ├─ post-check s1  → OK
  ├─ checkpoint     → token1 (carries PropagationState with C/D/G/I/S)
  │
  ├─ pre-check s2   → OK
  ├─ agent_runner(s2, ctx)
  ├─ post-check s2  → Violation(absolute, "exceeded scope")
  │                   ─► halt_for_violation
  ▼
HaltState(workflow_id="wf_42", halted_at_step="s2",
          violation=…, propagation_at_halt=…,
          requires_human_override=True)
  │
  ▼
WorkflowResult(status=HALTED, halt_state=HaltState(…),
               checkpoints=(token1,),
               final_propagation=propagation_at_halt)
  │
  ▼
[surface presents halt to user → user reviews + overrides or aborts]
```

---

## 8. Invariants (locked)

### 8.1 C/D/G/I/S structural invariants

1. `PropagationState.__dataclass_fields__` MUST contain `active_constraints`,
   `drift_state`, `geometry_profile`, `identity_profile`,
   `invariants_preserved`. Test-asserted at module load.
2. Every `ContextEnvelope` MUST carry (constraints, identity, drift, geometry).
3. Every `WorkflowResult` MUST carry a `final_propagation` that itself
   satisfies invariant 1.

### 8.2 Routing invariants

4. Routing NEVER selects an agent that violates an `ABSOLUTE` constraint.
5. Routing NEVER drops constraints between `RoutingDecision` and `ExecutionPlan`.
6. Routing produces a NEW `RoutingDecision` — never mutates the input request.

### 8.3 Context invariants

7. Constraints flow monotonically — `attach_constraints` only adds.
8. Constraint weakening requires explicit human override; no
   programmatic relaxation.
9. `load_drift_state` is pure (no I/O, no randomness, no time-dependent
   internal state beyond `now`).

### 8.4 Workflow invariants

10. Every step has a pre-check AND a post-check.
11. Every checkpoint produces a `PropagationState` satisfying invariant 1.
12. `halt_for_violation` is the ONLY exit on violation — no silent skip.
13. `requires_human_override` is True for any halt where
    `violation.severity >= REQUIRED`.
14. Workflows NEVER auto-resume past a halt.
15. Workflows NEVER mutate `plan` or `context`.

### 8.5 Minimality invariants

16. The orchestrator NEVER calls LLMs.
17. The orchestrator NEVER executes domain logic (Azimuth / ELINS / etc.).
18. The orchestrator NEVER owns long-term state.
19. The orchestrator NEVER serves UI directly.

### 8.6 Identity invariants

20. `IdentityProfile.session_id` is local-only and never uploaded.
21. Identity propagates through every step; no anonymous execution path.

---

## 9. Module Inventory

```
orchestrator_schemas.py             ── C/D/G/I/S schemas + supporting types
orchestrator_routing.py             ── Layer 1 (route / select / plan) — skeleton
orchestrator_context.py             ── Layer 2 (assemble / attach / drift) — skeleton
orchestrator_workflows.py           ── Layer 3 (run / checkpoint / halt) — skeleton
tests/test_orchestrator_schemas.py  ── structural tests; C/D/G/I/S contract
```

---

## 10. Phase Plan

| Phase | Scope | Status |
|---|---|---|
| **This commit** | Spec + schemas + skeletons + structural tests | **Shipping now** |
| Next | Routing layer real impl + behavior tests | Deferred |
| Next+1 | Context layer real impl + behavior tests | Deferred |
| Next+2 | Workflows layer real impl + behavior tests | Deferred |
| Next+3 | Wiring: gateway integration + surface adoption | Deferred |

---

## 11. Test Discipline

The Phase-1 structural test suite (`tests/test_orchestrator_schemas.py`)
asserts the C/D/G/I/S contract directly on the dataclass field set:

- `PropagationState.__dataclass_fields__` contains the canonical
  C/D/G/I/S references.
- All five core schemas exist and are frozen.
- All function bodies raise `NotImplementedError` (skeleton invariant).
- No mutable global state anywhere in the orchestrator modules.

Any future PR that removes a C/D/G/I/S field from `PropagationState`,
or that adds mutable state, or that introduces an LLM call, fails the
suite — the minimal-orchestrator contract is enforced by code, not just
by convention.

---

## 12. Worked Examples

### 12.1 Successful workflow

```
Request: "Run ELINS v2 on text"
Identity: actor=alice, kind=USER, sovereignty=USER_OWNED, tier=EXECUTE
Constraints active:
    - C1 (ABSOLUTE): "No upload of raw text outside user-authorized boundaries"
    - C2 (REQUIRED): "Drift on INTENT must stay below 0.5"

Routing:    select elins_agent (capabilities include "elins_run", tier=EXECUTE OK)
Context:    drift.in_bounds=True, geometry.stability=0.82
Workflow:   3 steps, all pre/post checks pass, 3 checkpoints
Result:     WorkflowResult(status=COMPLETED, halt_state=None,
                            final_propagation=PropagationState(…))
```

### 12.2 Constitutional violation → halt

```
Request: "Auto-post draft to public channel"
Identity: actor=alice, kind=USER, sovereignty=USER_OWNED, tier=PROPOSE
Constraints active:
    - C1 (ABSOLUTE): "Public posting requires AUTH_TIER >= EXECUTE"

Routing:    flag — actor.tier=PROPOSE < required EXECUTE
            → RoutingDecision points to a halt-on-route
Workflow:   pre-check step 1 → violation detected
            → halt_for_violation(state, V1)
Result:     WorkflowResult(status=HALTED,
                            halt_state=HaltState(
                                violation=V1,
                                requires_human_override=True))
            [surface shows: "Posting needs your explicit execute authz"]
```

### 12.3 Drift over threshold → halt with advisory + required

```
Request: "Continue session"
Drift:   DriftState(axis=SCOPE, magnitude=0.68, in_bounds=False)
                ↑ exceeds default threshold 0.5

Workflow:   pre-check step 1 → drift.in_bounds=False, ABSOLUTE constraint
            "drift must stay below threshold" violated
            → halt_for_violation
Result:     status=HALTED,
            halt_state.violation.severity=REQUIRED,
            requires_human_override=True
            [surface: "Scope drift is large — review and confirm continuation"]
```
