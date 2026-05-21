# FEA Integration

## Purpose

`fea_integration` is the deterministic bridge between FEA's
`AlignedExpression` output and the surface/orchestrator layer. Given
an aligned expression plus a handful of Ambient Trust signals, it
produces a single `IntegratedAlignmentResult` carrying:

- a surface halt level (`NONE` / `SOFT` / `HARD`),
- a list of structural surface directives (pacing, disclosure,
  checkpoint, preview),
- a bounded trust-state delta,
- a momentum-preserved flag,
- an object-identity passthrough of the original `AlignedExpression`.

It is implemented in `fea_integration_engine.py` (256 lines) and
`fea_integration_schemas.py` (269 lines), anchored to the external
spec `SPEC_FEA_INTEGRATION.md`. The engine is pure Python — no I/O,
no LLM, no network, no randomness — and is structurally prevented
from carrying raw user text, identity, or session information through
any of its output types. FEA Integration is **advisory only**: the
surface decides what to do with the verdict, and the integration
layer never auto-sends, never mutates upstream state, and never
converts trust signals into safety overrides.

### Core invariant

> **FEA safety flags are authoritative. Ambient Trust is advisory.**
> The integration layer never converts trust signals into safety
> overrides, never auto-sends, and never mutates upstream state.

## Implementation location

- **Engine:** `fea_integration_engine.py` (256 lines).
- **Schemas:** `fea_integration_schemas.py` (269 lines).
- **External spec:** `SPEC_FEA_INTEGRATION.md` — the source-of-truth
  behavioral spec, kept at the repo root.
- **Imports** (eager only, no lazy):
  - Engine: schemas + `AlignedExpression`, `ReframeType` from
    `emotional_alignment_schemas` (ERA) +
    `MomentumCheck, SessionContext, TrustState, UnderstandingCheck`
    from `ambient_trust_schemas` + `EnvelopeState` from `azimuth` +
    `PropagationState` from `orchestrator_schemas`.
  - Schemas: stdlib `dataclasses` + `enum`, plus `AlignedExpression`
    from `emotional_alignment_schemas`.

That is the complete dependency surface.

## Data model

### Upstream types (reused, not owned)

FEA Integration reads seven types from sibling modules:

- **From `emotional_alignment_schemas` (ERA):** `AlignedExpression`,
  `ReframeType`. Documented in [docs/era.md](era.md).
- **From `ambient_trust_schemas`:** `SessionContext`, `TrustState`,
  `MomentumCheck`, `UnderstandingCheck`. Not yet Batch-canonicalized.
- **From `azimuth`:** `EnvelopeState`. Not yet Batch-canonicalized.
- **From `orchestrator_schemas`:** `PropagationState`. Not yet
  Batch-canonicalized.

### Enums (2)

```python
class SurfaceHaltLevel(str, Enum):
    NONE = "no_halt"      # surface may proceed
    SOFT = "soft_halt"    # borderline; surface should slow and reconsider
    HARD = "hard_halt"    # FEA flagged the plan unsafe; surface must not auto-apply

class SurfaceDirectiveType(str, Enum):
    PACE       = "pace"
    DISCLOSURE = "disclosure"
    CHECKPOINT = "checkpoint"
    PREVIEW    = "preview"
```

There is intentionally **no halting directive type** — halt is
encoded in `SurfaceHaltLevel`. Directives are structural pacing /
disclosure / checkpoint / preview hints only.

### Canonical directive values (locked table)

```python
CANONICAL_DIRECTIVE_VALUES = {
    SurfaceDirectiveType.PACE:       frozenset({"slow", "normal"}),
    SurfaceDirectiveType.DISCLOSURE: frozenset({"single_concept",
                                                "full_model_available"}),
    SurfaceDirectiveType.CHECKPOINT: frozenset({"offer_choice"}),
    SurfaceDirectiveType.PREVIEW:    frozenset({"preview_only"}),
}
```

7 canonical values across the 4 directive types. Every
`SurfaceDirective.value` must be a member of its type's frozenset;
the engine validates this at construction time via `_make_directive`,
which raises `ValueError` on any non-canonical value.

### Output dataclasses (2, all frozen)

```python
@dataclass(frozen=True)
class SurfaceDirective:
    directive_type: SurfaceDirectiveType
    value:          str           # must be in CANONICAL_DIRECTIVE_VALUES[directive_type]

@dataclass(frozen=True)
class IntegratedAlignmentResult:
    aligned_expression: AlignedExpression          # object-identity passthrough
    halt_level:         SurfaceHaltLevel
    trust_state_delta:  float                       # ∈ [0.0, 1.0], rounded to 4 places
    momentum_preserved: bool                        # passthrough of momentum.passes_invariant
    surface_directives: tuple                       # tuple[SurfaceDirective, ...]
```

### Privacy contract (structurally enforced)

None of the integration output types may contain `text`, `raw`,
`raw_text`, `user`, `user_id`, `id`, `name`, `names`, `email`,
`session`, `session_id`, `identity`, `envelope_id`, `author`,
`actor`, `content`, `body`, or `message` fields. The forbidden set
is `_FORBIDDEN_FIELDS` (18 entries) and is enforced by
`assert_fea_integration_privacy_contract()` at module load.

### Module constants

- `_SOFT_HALT_SCORE_THRESHOLD = 0.4` — soft halt fires when
  `aligned.alignment_score <` this threshold; locked, test-asserted.
- `_TRUST_DELTA_MOMENTUM_BONUS = 0.1` — added when
  `momentum.passes_invariant`.
- `_TRUST_DELTA_HALT_PENALTY = 0.1` — subtracted when
  `halt_level != NONE`.
- `_FORBIDDEN_FIELDS` — 18-element frozenset (see Privacy contract).
- `_CANONICAL_FIELDS` — dict mapping the 2 ERA output classes to
  their canonical field sets; field drift fails import.
- `_CANONICAL_HALT_LEVELS` — locked 3-element frozenset.
- `_CANONICAL_DIRECTIVE_TYPES` — locked 4-element frozenset.

### Module-load runtime guards (5)

All five live in `fea_integration_schemas.py` and run at import
(lines 265-269):

- `assert_fea_integration_privacy_contract()` — fails if any
  integration output class gained a forbidden field.
- `assert_fea_integration_field_sets_canonical()` — fails if any
  output class's field set drifted from the canonical set.
- `assert_surface_halt_levels_canonical()` — fails if
  `SurfaceHaltLevel` gained or lost members.
- `assert_surface_directive_types_canonical()` — fails if
  `SurfaceDirectiveType` gained or lost members.
- `assert_canonical_directive_values()` — fails if
  `CANONICAL_DIRECTIVE_VALUES` drifted; additionally verifies every
  directive type is present as a key with a non-empty value set.

Broken edits fail import — the privacy and shape contracts are
enforced structurally, not just by tests.

## APIs / entrypoints

### Public functions (2)

**`integrate_alignment(aligned, session, trust, envelope, propagation, momentum, understanding) -> IntegratedAlignmentResult`**

Pure function. Composes a halt level, trust delta, and surface
directives from FEA's aligned expression plus Ambient Trust signals.

**v1 scope note (load-bearing):** the signature accepts seven inputs
for forward compatibility, but v1 **only branches on three**:

- `aligned` — FEA's `AlignedExpression`
- `momentum` — Ambient Trust `MomentumCheck`
- `understanding` — Ambient Trust `UnderstandingCheck`

The four remaining inputs are **reserved for v2** and explicitly NOT
branched on in v1:

- `session` (`SessionContext`)
- `trust` (`TrustState`)
- `envelope` (`EnvelopeState`)
- `propagation` (`PropagationState`)

The reserved inputs are touched once each (`_ = session`, etc.) at
lines 236-239 to silence linter warnings. The source-code test asserts
that no field accesses occur on these inputs in v1.

**Algorithm:**

1. Compute `halt_level` via `_compute_halt_level(aligned)`.
2. Compute `trust_state_delta` via `_compute_trust_delta(momentum, halt_level)`.
3. Build `surface_directives` via
   `_build_surface_directives(aligned, momentum, understanding, halt_level)`.
4. Return `IntegratedAlignmentResult(...)` with `aligned_expression`
   as the **same object** as the input `aligned` (object-identity
   passthrough, not a copy), and `momentum_preserved` as a direct
   passthrough of `momentum.passes_invariant`.

**`is_canonical_directive_value(directive_type, value) -> bool`**

Helper for external callers that want to validate a directive value
without going through `_make_directive`. The engine itself does NOT
call this helper — engine-internal construction uses `_make_directive`'s
inline membership check against `CANONICAL_DIRECTIVE_VALUES`.

### Halt-level decision table (`_compute_halt_level`)

Exclusive 3-branch logic, takes only `aligned`:

| Condition | Halt level |
|---|---|
| `not aligned.safe_for_surface` | `HARD` |
| `aligned.alignment_score < 0.4` | `SOFT` |
| otherwise | `NONE` |

### Trust-delta formula (`_compute_trust_delta`)

Takes `(momentum, halt_level)`. Pure heuristic:

```
delta = 0.0
  + 0.1  if momentum.passes_invariant
  − 0.1  if halt_level != NONE
clamp to [0.0, 1.0]
round to 4 decimal places
```

### Surface directive rules (`_build_surface_directives`)

5 ordered rules, deduplicated by `(directive_type, value)` key.
Returns a `tuple` (frozen):

| # | Trigger | Emits |
|---|---|---|
| 1 | `aligned.plan.expected_pressure_delta > 0` OR not `understanding.passes_invariant` | `PACE / slow` |
| 2 | `aligned.plan.expected_agency_delta > 0` OR not `momentum.passes_invariant` | `CHECKPOINT / offer_choice` |
| 3 | `ReframeType.TEMPORAL` in `aligned.plan.steps` | `DISCLOSURE / single_concept` |
| 4 | `ReframeType.MEANING` in `aligned.plan.steps` | `DISCLOSURE / full_model_available` |
| 5 | `halt_level == HARD` | `PREVIEW / preview_only` |

Order matters: directives are appended in this sequence. The dedupe
set means the same `(type, value)` pair cannot appear twice in the
output, but distinct values under the same type (e.g. both
`DISCLOSURE / single_concept` AND `DISCLOSURE / full_model_available`)
are allowed.

### HTTP entrypoints

**None.** FEA Integration is library-internal. The user-facing
surface is whatever `azimuth_transition` exposes downstream.

## Integration points

### Upstream

- **`emotional_alignment_schemas`** (ERA) — supplies
  `AlignedExpression` (the primary input) and `ReframeType` (used by
  the directive builder to inspect `aligned.plan.steps`). Canonical
  doc: [docs/era.md](era.md).
- **`ambient_trust_schemas`** — supplies `MomentumCheck` and
  `UnderstandingCheck` (used in v1) plus `SessionContext` and
  `TrustState` (reserved for v2).
- **`azimuth`** — supplies `EnvelopeState` (reserved for v2).
- **`orchestrator_schemas`** — supplies `PropagationState` (reserved
  for v2).

`ambient_trust_schemas`, `azimuth`, and `orchestrator_schemas` do
not yet have Batch canonical docs; they are candidates for future
sub-batches.

### Downstream consumers

- **`azimuth_transition.py`** — the **only** production importer.
  `compute_aligned_expression()` (around line 1091) maps
  `EnvelopeState` → ERA inputs, calls `align_expression()`, then
  calls `integrate_alignment(...)` with the seven inputs and returns
  the `IntegratedAlignmentResult`. See [docs/era.md](era.md) for the
  upstream half of this pipeline.
- **`azimuth.ExpressionCandidate.aligned`** — the
  `IntegratedAlignmentResult` returned by
  `compute_aligned_expression` is stored on the candidate's
  `aligned` field by `azimuth_transition.build_candidate` (Phase 3
  Unit 6). The field is typed
  `Optional[IntegratedAlignmentResult]` with a forward reference:
  the real import lives behind a `TYPE_CHECKING` gate in
  `azimuth.py` to break the azimuth ↔ fea_integration import cycle.
  At runtime the annotation is a string; consumers that need an
  `isinstance` check must import `IntegratedAlignmentResult` from
  `fea_integration_schemas` themselves. Pre-Unit-6 candidates with
  `aligned=None` remain valid — the default preserves backward
  compatibility. See [docs/azimuth.md](azimuth.md) for the consumer
  side.

### Tests

- **`tests/test_fea_integration.py`** — primary; imports both engine
  and schemas. Pins the halt-level logic, trust-delta formula,
  directive rules, privacy contract, canonical-set guards,
  object-identity passthrough, and module-load guard behavior.
- **`tests/test_azimuth_fea_integration.py`** — coupled; exercises
  the full `compute_aligned_expression` → `integrate_alignment` path
  through `azimuth_transition`.
- **`tests/test_evaluate_drift_risk.py`** — coupled; imports
  `fea_integration_schemas` for type references.
- **`tests/test_build_candidate.py`** — coupled; imports
  `fea_integration_schemas` for type references.
- **`tests/test_azimuth_schemas.py`** — tangential; mentions FEA
  but does not import it.

### External specification

`SPEC_FEA_INTEGRATION.md` (root of the repo) is the behavioral
source-of-truth. SPEC section references in this doc (e.g. SPEC § 5,
§ 6, § 7) map to that file: § 5 is the halt-level decision table,
§ 6 is the directive rules table, § 7 is the trust-delta formula.

## Invariants

FEA Integration enforces these invariants:

- **Pure function.** `integrate_alignment` is deterministic and
  side-effect free. Same inputs → byte-equal output. No I/O, no
  randomness, no LLM, no network.
- **Inputs never mutated.** All input dataclasses are frozen
  upstream (ERA, Ambient Trust); the integration layer additionally
  treats them as read-only.
- **Object-identity passthrough.** `IntegratedAlignmentResult.aligned_expression`
  is the same object as the input `aligned` — not a copy, not a
  reconstruction.
- **v1 scope.** `session`, `trust`, `envelope`, `propagation` are
  accepted in the signature but never branched on; source-code tests
  assert no field accesses on these inputs.
- **Halt-level decision is exclusive.** Exactly one of
  `{NONE, SOFT, HARD}` is returned, determined by the 3-branch table
  above. Halt depends ONLY on `aligned.safe_for_surface` and
  `aligned.alignment_score`.
- **Trust-delta is bounded.** Always in `[0.0, 1.0]`, rounded to 4
  decimal places. Depends ONLY on `momentum.passes_invariant` and
  `halt_level`.
- **Directive validity.** Every emitted `SurfaceDirective.value`
  must be a member of `CANONICAL_DIRECTIVE_VALUES` for its type;
  `_make_directive` raises `ValueError` on any non-canonical value.
- **Directive deduplication.** The output tuple cannot contain the
  same `(directive_type, value)` pair twice; the engine dedupes by
  key set as it appends.
- **Tuple return.** `surface_directives` is a `tuple`, not a `list`
  — immutable.
- **No raw user text** in any integration output type; structural,
  test-asserted, and 18-field forbidden-set enforced at module load.
- **No identity fields** in any integration output type — see
  `_FORBIDDEN_FIELDS` for the full set.
- **Schemas locked.** Field-set drift in any integration output
  class fails module load.
- **Halt and directive sets locked.** Gaining or losing a
  `SurfaceHaltLevel` or `SurfaceDirectiveType` member fails module
  load.
- **Canonical directive table locked.** Drift in
  `CANONICAL_DIRECTIVE_VALUES` fails module load; the guard
  additionally verifies every directive type has a non-empty value
  set.
- **FEA safety is authoritative.** The integration layer never
  promotes Ambient Trust signals into safety overrides; trust
  signals only contribute to the bounded `trust_state_delta` and to
  directive triggers, never to the halt-level decision.
- **Advisory only.** The module returns data; never calls a
  send/apply/commit primitive. Final decisions pass through the
  downstream Sovereignty Gate.

## Non-goals

FEA Integration is **not**:

- the Sovereignty Gate — FEA Integration is advisory; the gate is a
  separate downstream subsystem that decides what to actually do;
- a text engine — FEA Integration never receives or produces user
  text; inputs are structural advisory verdicts + trust check
  outcomes, outputs are typed halt levels + canonical-value
  directives;
- an HTTP service — there is no `/me/fea/*` or similar endpoint;
  the layer is library-internal, invoked only by `azimuth_transition`;
- a state store — FEA Integration is stateless; nothing is
  persisted by FEA Integration, by design;
- an autonomous decision system — every call is request-driven; no
  scheduler, no background work, no auto-apply;
- a learning / training / personalisation surface — FEA Integration
  never observes outcomes; the rule set is locked in code and the
  SPEC;
- an LLM caller or model client — pure deterministic Python;
- a privacy escape hatch — the schemas structurally exclude identity
  and raw-text fields, and the guards fail import on drift;
- a v2 implementation — the four reserved inputs are intentionally
  not consumed in v1.

## Fiction removed

The following constructs are explicitly not present in
`fea_integration_engine.py` or `fea_integration_schemas.py` and
must not be inferred:

- **No use of `session`, `trust`, `envelope`, or `propagation` in
  v1.** All four are reserved inputs touched once to silence
  linters; the source-code test asserts no field accesses.
- **No halting directive type.** Halt is encoded only in
  `SurfaceHaltLevel`; directives are structural pacing / disclosure
  / checkpoint / preview hints, never "halt" or "stop" hints.
- **No `rationale`, `metadata`, or free-text fields on
  `SurfaceDirective`.** The dataclass has exactly two fields:
  `directive_type` and `value`. `value` is restricted to the
  canonical set so the type cannot carry free text.
- **No mutation of `AlignedExpression`.** It passes through by
  object identity; never reconstructed, never copied, never
  modified.
- **No model invocation.** No `model_router` import; no provider
  SDK imports anywhere in the subsystem.
- **No vault, no operator_state, no kernel coupling.** None of
  these are imported.
- **No HTTP surface.** No `/fea` routes anywhere in `app.py`.
- **No async, no scheduler, no background work.** Pure synchronous
  function call.
- **No `is_canonical_directive_value` call from the engine.** The
  helper exists for external callers; the engine validates inline
  via `_make_directive`'s membership check against
  `CANONICAL_DIRECTIVE_VALUES`.
- **No autonomous safety override.** The integration layer never
  converts Ambient Trust signals into FEA safety decisions — FEA
  flags are authoritative; Ambient Trust is advisory.

Only the behaviour, fields, integrations, and invariants described
in this document are present in the code; the verified surface is
locked by the tests in `tests/test_fea_integration.py` and the
five module-load assertion functions.
