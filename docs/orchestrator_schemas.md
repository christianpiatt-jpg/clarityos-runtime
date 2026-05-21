# Orchestrator Schemas

## Purpose

`orchestrator_schemas` is the **type root and structural contract** of
the Minimal Orchestrator. It owns one role today and frames three more:

- **The type root** (`orchestrator_schemas.py`) — the canonical enums,
  dataclasses, and module-load structural guards used by every
  orchestrator layer plus several intelligence-layer subsystems.
  `azimuth_transition`, `language_schemas`, `fea_integration_engine`,
  and `primitive_selection_engine` all import from here. With 7
  production importers, `orchestrator_schemas.py` is the second-most
  imported types module in the codebase (after `azimuth.py`).

- **The three engine layers** (`orchestrator_routing.py`,
  `orchestrator_context.py`, `orchestrator_workflows.py`) — all
  Phase‑1 skeletons. Public APIs are defined; bodies raise
  `NotImplementedError`. The detailed Phase‑2 algorithm sketches live
  in each module's docstrings. They are documented here for
  completeness and explicitly marked as not part of the runtime path.

### Core invariants (from module docstring + `SPEC_ORCHESTRATOR.md`)

1. **C/D/G/I/S contract:** the five letters of the minimal-orchestrator
   design map directly to five frozen dataclasses —
   `ConstitutionalConstraint` (C), `DriftState` (D), `GeometryProfile`
   (G), `IdentityProfile` (I), `PropagationState` (S).
   `PropagationState.__dataclass_fields__` MUST contain references to
   all five. Asserted at module load.
2. **Minimality contract:** no LLM libraries, no network libraries, no
   mutable global state, no functions that mutate input objects. All
   schemas are frozen dataclasses; all categorical types are enums.
3. **Defense in depth:** the structural guards run at module load
   (failing import on structurally broken edits) and are re-verified by
   the test suite.

## Status

| File | Status | Reason |
|---|---|---|
| `orchestrator_schemas.py` | **CURRENT** | 7 production importers; all enums/dataclasses/guards active at runtime |
| `orchestrator_routing.py` | **Phase‑1 skeleton — Phase‑2 deferred** | 3 stub functions, all raise `NotImplementedError`; zero production importers |
| `orchestrator_context.py` | **Phase‑1 skeleton — Phase‑2 deferred** | 3 stub functions, all raise `NotImplementedError`; zero production importers |
| `orchestrator_workflows.py` | **Phase‑1 skeleton — Phase‑2 deferred** | 3 stub functions, all raise `NotImplementedError`; zero production importers |

### Family note

The three engine layers were inventoried via Batch‑32/33/34 PASS‑1
and remain Phase‑1 skeletons. Every public function raises
`NotImplementedError`. `tests/test_orchestrator_schemas.py::TestSkeletonsRaise`
asserts they continue to do so.

Each module carries detailed Phase‑2 design specs in its docstrings:

- `orchestrator_routing` — C-first dispatcher: ABSOLUTE constraints
  filter the agent set before any capability match runs; identity
  tier filters before capability match; capability match scores
  remaining agents; geometry (pressure_load) tie-breaks.
- `orchestrator_context` — C/D/G/I/S aggregator: monotonic constraint
  flow (`attach_constraints` only ADDS, never weakens); per-axis drift
  metrics (INTENT primary in v1, TONE/SCOPE/IDENTITY/TIMELINE deferred);
  `assemble_context` sources constraints from `plan.overall_constraints`.
- `orchestrator_workflows` — runtime enforcement chokepoint: every
  step has BOTH a pre-check and a post-check; `halt_for_violation` is
  the only exit on violation; `requires_human_override` is True iff
  `violation.severity >= REQUIRED`; workflows never auto-resume past a
  halt.

**Production reality has routed through `azimuth_transition.py` rather
than the orchestrator engines** for the deterministic Azimuth → Cloud
pipeline. The orchestrator stubs remain the canonical design intent for
the Minimal Orchestrator pattern; no production module currently
imports any of the three engine layers.

The only test file exercising these modules is
`tests/test_orchestrator_schemas.py`, which asserts: (1) the public
surface is importable, (2) the bodies raise `NotImplementedError`, (3)
the source contains no forbidden imports (LLM / network libraries),
and (4) cross-class structural carry-through —
`PropagationState → CheckpointToken → HaltState → WorkflowResult` —
can be constructed by hand even though no engine produces it yet.

## Implementation location

- **Type root:** `orchestrator_schemas.py` (406 lines).
- **Layer 1 stub (Routing):** `orchestrator_routing.py` (146 lines).
- **Layer 2 stub (Context):** `orchestrator_context.py` (170 lines).
- **Layer 3 stub (Workflows):** `orchestrator_workflows.py` (190 lines).
- **External spec:** `SPEC_ORCHESTRATOR.md` (repo root).
- **Test suite:** `tests/test_orchestrator_schemas.py` (670 lines,
  18 test classes).
- **Imports:**
  - `orchestrator_schemas.py`: stdlib only (`secrets`, `dataclasses`,
    `datetime`, `enum`, `typing`). Deepest leaf in the orchestrator
    dependency graph.
  - All three engine stubs: stdlib `typing` + `orchestrator_schemas`
    only. Zero other dependencies.

## Data model (`orchestrator_schemas.py`)

### Enums (7) — categorical types

All `(str, Enum)`, all locked, all test-pinned.

| Enum | Values |
|---|---|
| `Severity` | `ADVISORY`, `REQUIRED`, `ABSOLUTE` |
| `EnforcementMode` | `ALLOW_WITH_WARNING`, `HALT`, `REQUIRE_HUMAN_OVERRIDE` |
| `DriftAxis` | `INTENT`, `TONE`, `SCOPE`, `IDENTITY`, `TIMELINE` |
| `ActorKind` | `USER`, `AGENT`, `SYSTEM` |
| `SovereigntyLevel` | `USER_OWNED`, `DELEGATED`, `AGENT_ONLY` |
| `AuthorizationTier` | `READ`, `OBSERVE`, `PROPOSE`, `EXECUTE` |
| `WorkflowStatus` | `PENDING`, `RUNNING`, `COMPLETED`, `HALTED`, `PENDING_HUMAN_REVIEW` |

`AuthorizationTier` is documented as "ordered by privilege" but is a
plain `(str, Enum)` — there is no `__lt__` overload. Ordering is a
consumer responsibility.

### Constants

| Constant | Value | Purpose |
|---|---|---|
| `DEFAULT_DRIFT_THRESHOLD` | `0.5` (float) | `DriftState.in_bounds` is True iff `magnitude < this` |
| `INVARIANTS_CANONICAL` | 5-tuple of strings | Names of invariants tracked through `PropagationState.invariants_preserved`: `constitutional_constraints_intact`, `drift_within_bounds`, `geometry_within_stability_budget`, `identity_unchanged_or_delegated`, `no_constraint_dropped` |

### C/D/G/I/S core dataclasses (5)

```python
@dataclass(frozen=True)
class ConstitutionalConstraint:
    rule_id:     str
    statement:   str
    severity:    Severity
    enforcement: EnforcementMode
    scope:       tuple = ()         # tuple of route/workflow names
    rationale:   str   = ""

@dataclass(frozen=True)
class DriftState:
    axis:            DriftAxis
    magnitude:       float           # [0, 1]
    direction:       str             # human-readable
    baseline_anchor: str
    in_bounds:       bool
    measured_at:     datetime

@dataclass(frozen=True)
class GeometryProfile:
    depth:           int             # workflow nesting depth
    breadth:         int             # active concurrent steps
    pressure_load:   float           # [0, 1]
    stability_score: float           # [0, 1], higher is more stable
    captured_at:     datetime

@dataclass(frozen=True)
class IdentityProfile:
    actor:              str
    actor_kind:         ActorKind
    sovereignty_level:  SovereigntyLevel
    authorization_tier: AuthorizationTier
    delegated_from:     Optional[str] = None
    session_id:         str           = ""    # local-only; NEVER uploaded

@dataclass(frozen=True)
class PropagationState:
    from_step:            str
    to_step:              str
    active_constraints:   tuple                    # C
    drift_state:          DriftState               # D
    geometry_profile:     GeometryProfile          # G
    identity_profile:     IdentityProfile          # I
    invariants_preserved: tuple                    # S — tuple of invariant names
    propagation_id:       str = field(default_factory=_new_local_id)
```

### Supporting dataclasses — routing (5)

```python
@dataclass(frozen=True)
class RoutingRequest:
    request_id:   str
    request_type: str
    payload:      dict              # mutable — caller discipline
    identity:     IdentityProfile
    arrived_at:   datetime

@dataclass(frozen=True)
class RoutingDecision:
    request_id:           str
    selected_agent:       str
    rationale:            str
    constraints_attached: tuple
    decided_at:           datetime

@dataclass(frozen=True)
class AgentBinding:
    agent_id:         str
    capabilities:     tuple
    authorized_tiers: tuple

@dataclass(frozen=True)
class ExecutionStep:
    step_id:     str
    action:      str
    inputs:      dict               # mutable — caller discipline
    constraints: tuple

@dataclass(frozen=True)
class ExecutionPlan:
    plan_id:             str
    steps:               tuple
    overall_constraints: tuple
    created_at:          datetime
```

### Supporting dataclass — context (1)

```python
@dataclass(frozen=True)
class ContextEnvelope:
    request:     RoutingRequest
    plan:        ExecutionPlan
    constraints: tuple              # C
    identity:    IdentityProfile    # I
    drift:       DriftState         # D
    geometry:    GeometryProfile    # G
```

`ContextEnvelope` carries **C/D/G/I but not S explicitly** — the
`PropagationState` is constructed dynamically during workflow
execution rather than embedded in the envelope. The
`_REQUIRED_CONTEXT_FIELDS` guard is 4 entries, not 5.

### Supporting dataclasses — workflows (4)

```python
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
    snapshot_id: str = field(default_factory=_new_local_id)

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
    checkpoints:       tuple
    halt_state:        Optional[HaltState] = None
    completed_at:      Optional[datetime]  = None
```

### Privacy / sovereignty contract

The orchestrator's analogue of azimuth's privacy boundary is
**authority + structure separation**, not data redaction:

- `IdentityProfile.session_id` is documented local-only and never
  uploaded (line 192 of `orchestrator_schemas.py`).
- `SovereigntyLevel` enum tracks who has authority at each step
  (`USER_OWNED` / `DELEGATED` / `AGENT_ONLY`).
- `AuthorizationTier` enum tracks the privilege level
  (`READ` < `OBSERVE` < `PROPOSE` < `EXECUTE` by docstring convention).
- **No `_FORBIDDEN_*_FIELDS` set** — orchestrator types are not designed
  for a wire boundary in the same way `azimuth.CloudMetadata` is.

### Module-load guards (3)

All three guards live in `orchestrator_schemas.py` and the composite
runs at import (line 406):

- `assert_propagation_contract()` — fails if `PropagationState` has
  dropped any of the canonical C/D/G/I/S fields
  (`_REQUIRED_PROPAGATION_FIELDS` — 5 entries).
- `assert_context_contract()` — fails if `ContextEnvelope` has dropped
  any of (`constraints`, `identity`, `drift`, `geometry`)
  (`_REQUIRED_CONTEXT_FIELDS` — 4 entries; S is implicit at runtime).
- `assert_minimal_orchestrator_contract()` — composite that runs all
  structural contracts. Invoked at module load.

This pattern is stronger than `azimuth.py`'s privacy guard, which is
test-invoked only. Structurally broken edits to orchestrator schemas
fail import, not just `pytest`.

### Schema-layer drift surfaces

`orchestrator_schemas.py` is a declarative schema module; it defers
most validation to the caller and to the test suite. The following are
intentional design choices, not bugs — but each is a place where caller
discipline carries load that the module itself does not enforce.

**No `__post_init__` / no runtime type enforcement.** Wrong enum types,
NaN floats for `magnitude` / `pressure_load` / `stability_score`, etc.
all construct silently. Type annotations are advisory.

**`INVARIANTS_CANONICAL` is a string tuple, not an enum.** Producer-side
typos (e.g. `"drift_within_bound"` missing the `s`) silently fail
downstream membership checks. Same fragility pattern as
`RISK_FLAGS_CANONICAL` in azimuth.

**`AuthorizationTier` "ordered by privilege" is documentation-only.**
No `__lt__` overload, no integer mapping. A consumer wanting
"is at least `EXECUTE`" must build the comparison table itself.

**`WorkflowStatus` mixes terminal and transitional states** without
a structural marker. `COMPLETED` / `HALTED` are terminal;
`PENDING` / `RUNNING` / `PENDING_HUMAN_REVIEW` are not. Consumers
wanting "is this run done?" enumerate the terminal set themselves.

**`HaltState.requires_human_override` invariant** (Severity ≥ REQUIRED
→ True) is docstring-only, not enforced. `assert_propagation_contract`
doesn't reach this — the workflows engine must respect it.

**`RoutingRequest.payload` and `ExecutionStep.inputs` are `dict`.**
The only mutable-typed fields anywhere in the module. `frozen=True`
prevents reassignment of the field; it doesn't prevent in-place
mutation of the dict. Consumer discipline.

**No `schema_version` field anywhere.** Orchestrator types are not
wire-exposed (unlike `azimuth.CloudMetadata` which versions explicitly),
so the absence is consistent — but if these types ever become a wire
contract, versioning would have to be added.

## APIs / entrypoints

### Part A: `orchestrator_schemas.py` — CURRENT

**`assert_propagation_contract() -> None`** (line 374)

Runtime guard. Raises `AssertionError` if `PropagationState` has dropped
any C/D/G/I/S field. Invoked by the composite at module load + by tests.

**`assert_context_contract() -> None`** (line 386)

Runtime guard. Raises `AssertionError` if `ContextEnvelope` has dropped
any C/D/G/I field. Invoked by the composite at module load + by tests.

**`assert_minimal_orchestrator_contract() -> None`** (line 397)

Composite guard. Runs both of the above. **Invoked at module load**
(line 406) — a structurally broken edit fails import.

**`_new_local_id() -> str`** (line 122)

Generates `secrets.token_urlsafe(12)`. Used for `propagation_id` and
`snapshot_id`. Local-only — never serialized.

### Part B: `orchestrator_routing.py` — Phase‑1 skeleton

All 3 functions raise `NotImplementedError(... — Phase 2 implementation)`.

**`route_request(req, available_agents, constraints) -> RoutingDecision`** (line 58)

Phase‑2 algorithm (from docstring lines 75–84):

1. Filter `available_agents` by `req.identity.authorization_tier` ∈
   `agent.authorized_tiers`.
2. Drop any agent that violates any ABSOLUTE-severity constraint.
3. Score remaining agents by capability match against `req.request_type`.
4. Tie-break by lowest `pressure_load` (geometry-aware — caller passes
   geometry via `context_hints` in `build_execution_plan`).
5. Emit `RoutingDecision` with rationale + attached constraints. If no
   agent qualifies → halt-on-route decision (`selected_agent="<halt>"`,
   rationale describes the gap).

**`select_agent(request_type, identity, constraints, agents) -> Optional[AgentBinding]`** (line 99)

Agent-registry lookup; used internally by `route_request` and exposed
for tests + alternative routing strategies. Returns `None` if no agent
qualifies.

**`build_execution_plan(decision, context_hints=None) -> ExecutionPlan`** (line 123)

Constructs the step sequence. Invariant:
`plan.overall_constraints` is a SUPERSET of every `step.constraints`.
No constraint is silently dropped between routing and plan.

### Part C: `orchestrator_context.py` — Phase‑1 skeleton

All 3 functions raise `NotImplementedError(... — Phase 2 implementation)`.

**`assemble_context(req, plan, identity, drift, geometry) -> ContextEnvelope`** (line 60)

Gathers C/D/G/I/S inputs into one envelope. `ContextEnvelope.constraints`
is sourced from `plan.overall_constraints` — plan-level constraints are
authoritative at context-assembly time.

**`attach_constraints(context, additional_constraints) -> ContextEnvelope`** (line 95)

Returns a new frozen envelope with the union of existing + additional
constraints. **Monotonic** — only adds, never weakens. Deduplication
rule: constraints with identical `rule_id` are deduped; if the same
rule appears with different `severity`, the HIGHER severity wins
(defense-in-depth).

**`load_drift_state(actor, history, baseline_anchor, axis=DriftAxis.INTENT) -> DriftState`** (line 128)

Pure function. Per-axis Phase‑2 metrics:

| Axis | Metric |
|---|---|
| `INTENT` | Divergence between current request intent and baseline |
| `TONE` | Change in lexical tone markers |
| `SCOPE` | Expansion of touched-resource set vs baseline |
| `IDENTITY` | Change in actor / delegation chain |
| `TIMELINE` | Elapsed gap since `baseline_anchor` exceeds budget |

v1 primary axis is INTENT; the others may return `magnitude=0.0,
in_bounds=True` until later units add richer measurement.

### Part D: `orchestrator_workflows.py` — Phase‑1 skeleton

All 3 functions raise `NotImplementedError(... — Phase 2 implementation)`.
This layer introduces one type alias:

```python
AgentRunner = Callable[..., dict]
```

**`run_workflow(plan, context, agent_runner) -> WorkflowResult`** (line 76)

Phase‑2 algorithm:

1. Initialize workflow_state with `workflow_id`, `status=RUNNING`.
2. For each step in `plan.steps`:
   - **PRE-step check:** all ABSOLUTE constraints satisfied? identity
     unchanged or properly delegated? `drift.in_bounds` is True?
     `geometry.stability_score` above floor?
   - Run step via `agent_runner(step, context)`.
   - **POST-step check:** did the runner return a Violation indicator?
     did drift recompute exceed bounds?
   - On any failure → `halt_for_violation` → return HALTED result.
   - `checkpoint(workflow_state)` → `CheckpointToken`.
   - Build next `PropagationState` carrying C/D/G/I/S.
3. After all steps succeed, return COMPLETED result.

Returns one of `COMPLETED`, `HALTED`, `PENDING_HUMAN_REVIEW`.

**`checkpoint(workflow_state) -> CheckpointToken`** (line 133)

Captures a resumable snapshot at a step boundary. The orchestrator
does NOT persist the token — callers (gateway, cron, surface) decide
whether to store it for resume.

**`halt_for_violation(workflow_state, violation) -> HaltState`** (line 160)

Stops the workflow and produces a HaltState for human review.
**Invariant: `requires_human_override` is True whenever
`violation.severity >= REQUIRED`.** For ADVISORY violations the caller
MAY continue after logging; for REQUIRED and ABSOLUTE the halt is
binding until human override. The orchestrator does NOT self-resolve,
never retries, never skips.

## Integration points

### `orchestrator_schemas.py` — 7 production importers

| Importer | What it consumes |
|---|---|
| `orchestrator_routing.py` | 9 types (`AgentBinding, AuthorizationTier, ConstitutionalConstraint, ExecutionPlan, ExecutionStep, IdentityProfile, RoutingDecision, RoutingRequest, Severity`) |
| `orchestrator_workflows.py` | 9 types (`CheckpointToken, ContextEnvelope, ExecutionPlan, HaltState, PropagationState, Severity, Violation, WorkflowResult, WorkflowStatus`) |
| `orchestrator_context.py` | 8 types (`ContextEnvelope, ConstitutionalConstraint, DriftAxis, DriftState, ExecutionPlan, GeometryProfile, IdentityProfile, RoutingRequest`) |
| `azimuth_transition.py` | 8 types (`ActorKind, AuthorizationTier, DriftAxis, DriftState, GeometryProfile, IdentityProfile, PropagationState, SovereigntyLevel`) |
| `language_schemas.py` | 4 types (`DriftState, GeometryProfile, IdentityProfile, PropagationState`) |
| `fea_integration_engine.py` | 1 type (`PropagationState` — reserved-in-v1 envelope/propagation slot) |
| `primitive_selection_engine.py` | 2 types (`ActorKind, AuthorizationTier`) |

This makes `orchestrator_schemas.py` tied with `language_schemas.py`
as the **second-most-imported types module in the codebase** (after
`azimuth.py` at 10 production importers).

### The three engine layers — zero production importers

No production module imports any of `orchestrator_routing`,
`orchestrator_context`, or `orchestrator_workflows`. The entire
surface is reachable only through `tests/test_orchestrator_schemas.py`.
The 3-layer engine pipeline is **canonical design intent**, not
runtime path. See [docs/azimuth.md](azimuth.md) for the engine
(`azimuth_transition`) that handles the runtime deterministic pipeline.

### No coupling to

- `intelligence_kernel`, `model_router`, `memory_vault`,
  `operator_state` — none are imported by any orchestrator module.
- No LLM SDKs, no `urllib`, no `requests`, no file I/O.
- No HTTP routes — none of the orchestrator modules are referenced by
  `app.py`.

## Invariants

### Structural (module-load enforced)

- `PropagationState` carries all 5 C/D/G/I/S fields. Asserted by
  `assert_propagation_contract` at import.
- `ContextEnvelope` carries `(constraints, identity, drift, geometry)`.
  Asserted by `assert_context_contract` at import.
- Composite `assert_minimal_orchestrator_contract` runs at module
  load. Structurally broken edits fail import.

### Privacy / sovereignty (encoded by structure)

- `IdentityProfile.session_id` is local-only and never uploaded.
- `SovereigntyLevel` makes authority categorical: any code path that
  needs to know "who has the right to act" reads this enum.
- No free-text identifier or session field in any type that crosses an
  external boundary (which is moot because no orchestrator type
  currently crosses any external boundary at all).

### Frozen everywhere

All 15 dataclasses in `orchestrator_schemas.py` are
`@dataclass(frozen=True)`. The two mutable-typed fields
(`RoutingRequest.payload: dict` and `ExecutionStep.inputs: dict`) are
reassignment-locked but the dict values themselves are caller's
responsibility.

### Engine-layer invariants (documented, not yet enforceable)

These live in the engine module docstrings and become enforceable when
Phase‑2 implementations land:

- **Routing:** never selects an agent that violates an ABSOLUTE
  constraint; never drops constraints between `RoutingDecision` and
  `ExecutionPlan`; never mutates `req`;
  `plan.overall_constraints ⊇ ⋃ step.constraints`.
- **Context:** constraints flow MONOTONICALLY (`attach_constraints`
  only adds); no programmatic relaxation; `load_drift_state` is pure
  (deterministic given inputs); every returned `ContextEnvelope`
  satisfies the C/D/G/I structural contract.
- **Workflows:** every step has BOTH pre-check AND post-check; every
  checkpoint produces a `PropagationState` satisfying C/D/G/I/S;
  `halt_for_violation` is the ONLY exit on violation;
  `requires_human_override` is True for any violation with
  `severity >= REQUIRED`; workflows NEVER auto-resume past a halt;
  workflows NEVER mutate plan or context.

## Non-goals

`orchestrator_schemas` is **not**:

- a kernel reasoning mode — none of the modules import
  `intelligence_kernel`;
- a model invocation surface — no `model_router` import, no provider
  SDKs;
- a vault consumer — no `memory_vault` import;
- an `operator_state` writer or reader — no `operator_state` import;
- an HTTP service — no routes in `app.py`;
- a state store — fully stateless;
- a generic workflow framework — the C/D/G/I/S contract is narrow,
  locked, and tied to the Minimal Orchestrator design;
- a privacy escape hatch — orchestrator types are not designed to
  cross any external boundary; if/when they do, a versioning + forbidden-
  fields contract would be required (none exists today);
- a runtime path — Phase‑1 skeleton bodies raise
  `NotImplementedError`; the runtime pipeline runs through
  `azimuth_transition.py` instead.

## Fiction removed

The following constructs are explicitly not present in
`orchestrator_schemas.py` or its three engine stubs and must not be
inferred:

- **No active production wiring for any orchestrator engine.** All
  9 stub functions across routing / context / workflows raise
  `NotImplementedError`. The runtime pipeline runs through
  `azimuth_transition.py`; orchestrator engines are canonical design
  intent for a future Phase‑2.
- **No `__post_init__` validation on any dataclass.** Wrong enum
  types, NaN floats, semantically inconsistent field combinations all
  construct silently. The test suite locks enum value sets but not
  pairwise field consistency.
- **No `_FORBIDDEN_*_FIELDS` set.** Orchestrator types are not
  wire-exposed; the azimuth privacy-blocklist pattern does not apply
  here. If/when these types become a wire contract, a forbidden-
  fields contract would have to be added.
- **No `schema_version` field anywhere.** Same justification: types
  are not wire-exposed. The absence is consistent with the design.
- **No `AuthorizationTier` ordering enforcement.** The "ordered by
  privilege" docstring is documentation-only; no `__lt__` overload,
  no integer mapping. Comparison logic lives in consumers.
- **No `HaltState.requires_human_override` runtime check.** The
  invariant lives in the schema docstring (line 327), the workflows
  module docstring (line 44), and the `halt_for_violation` function
  docstring (line 180) — three-way documentation redundancy without
  structural enforcement until the workflows engine is implemented.
- **No `WorkflowState` dataclass.** `checkpoint` and
  `halt_for_violation` take a generic `dict` for `workflow_state`. If
  implementation lands, either a private dataclass appears in
  `orchestrator_workflows.py` (creating a second "schemas outside the
  schemas module" outlier — `AgentRunner` is the first), or the dict
  shape stays informal.
- **No `resume_from_checkpoint` function.** Workflows produce
  `CheckpointToken`s but never consume them. Resume logic lives
  outside the orchestrator by design — same one-way pattern as
  routing → context: each layer produces shapes the next consumes, no
  callback architecture.
- **No multi-orchestrator coordination.** There is no shared
  scheduler framework, no central task queue, no cross-instance
  coordination. The Minimal Orchestrator is single-process by design.
- **No engine module imports anything beyond schemas.** All three
  Phase‑1 stubs import only `typing` + `orchestrator_schemas`. No
  cross-engine import, no LLM SDK, no `urllib`, no logging, no
  `secrets`, no `datetime`.

Only the behaviour, fields, integrations, and invariants described in
this document are present in the code; the verified surface is locked
by the tests in `tests/test_orchestrator_schemas.py` (670 lines, 18
test classes including `TestPropagationStateCDGIS`,
`TestContextEnvelopeContract`, `TestRuntimeGuards`,
`TestSkeletonsRaise`, `TestModuleSurface`,
`TestMinimalOrchestratorInvariants`, and `TestCrossModuleTypes`).
