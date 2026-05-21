# Emotional Reality Alignment (ERA)

## Purpose

ERA is the deterministic emotional-reframing engine that takes a
structural snapshot of a user's emotional state and produces an
advisory reframe plan plus an aligned expression. It is implemented in
`emotional_alignment_engine.py` (374 lines) and
`emotional_alignment_schemas.py` (277 lines), anchored to the external
spec `SPEC_EMOTIONAL_REALITY_ALIGNMENT.md`. The engine is pure Python —
no I/O, no LLM, no network, no randomness — and is structurally
prevented from carrying raw user text, identity, or session
information through any of its output types. ERA is **advisory only**:
the surface decides what to do with the plan, and the final expression
still passes through the downstream Sovereignty Gate.

## Implementation location

- **Engine:** `emotional_alignment_engine.py` (374 lines).
- **Schemas:** `emotional_alignment_schemas.py` (277 lines).
- **External spec:** `SPEC_EMOTIONAL_REALITY_ALIGNMENT.md` — the
  source-of-truth behavioral spec, kept at the repo root.
- **Imports** (eager only, no lazy):
  - Engine: schemas + `azimuth.PressureLevel` +
    `language_schemas.ExpressionPrimitive`
  - Schemas: stdlib `dataclasses` + `enum`, plus
    `azimuth.{IntensityLevel, PressureLevel, Valence}` and
    `language_schemas.ExpressionPrimitive`

That is the complete dependency surface.

## Data model

### Upstream types (reused, not owned)

ERA reads four types from sibling modules:

- `PressureLevel`, `IntensityLevel`, `Valence` — from `azimuth`;
  ordinal enums representing the pressure, intensity, and valence
  axes that ERA consumes as already-quantised structural state.
- `ExpressionPrimitive` — from `language_schemas`; the structured
  expression mode the Language Layer has chosen. ERA forwards it
  into the plan but never inspects its content.

Neither `azimuth` nor `language_schemas` has a Batch 10 canonical
doc; both are candidates for future sub-batches. ERA treats these
types as opaque inputs.

### Input dataclasses (3, all frozen)

```python
EmotionalSnapshot{
    pressure_level: PressureLevel,
    intensity:      IntensityLevel,
    valence:        Valence,
    temporal_linked: bool,   # linked to a repeating pattern
    anchor_present:  bool,   # specific memory/pattern anchor active
}

EmotionalGeometry{
    curvature, torsion, shear, boundary: bool,
    stance_self, stance_other, stance_world: float ∈ [0, 1],
    pressure_gradient:                       float ∈ [0, 1],
}

EmotionalIntention{
    target_state:       str,
    regulatory_goal:    RegulationGoal,
    relational_posture: RelationalPosture,
    meaning_need:       MeaningNeed,
}
```

All carry only structural metadata — no raw text, no identity.

### Output dataclasses (3, all frozen)

```python
ReframeStep{
    reframe_type: ReframeType,
    rationale:    str,   # canonical engine-generated, never user text
}

ReframePlan{
    steps:                   tuple[ReframeStep, ...],
    primitive:               ExpressionPrimitive,
    expected_pressure_delta: int ∈ {-1, 0, +1},
    expected_agency_delta:   int ∈ {-1, 0, +1},
}

AlignedExpression{
    plan:                       ReframePlan,
    alignment_score:            float ∈ [0, 1],
    internal_relator_preserved: bool,
    safe_for_surface:           bool,
}
```

**Privacy contract (structurally guaranteed, test-asserted):** none of
the three output types may contain `text`, `raw`, `raw_text`, `user`,
`user_id`, `id`, `name`, `names`, `email`, `session`, `session_id`,
`identity`, `envelope_id`, `author`, or `actor` fields. The forbidden
set is `_FORBIDDEN_ERA_FIELDS` and is enforced by
`assert_era_privacy_contract()` at module load.

### Enums (4)

| Enum | Values |
|---|---|
| `RegulationGoal` | `CONTAIN`, `EXPRESS`, `TRANSFORM` |
| `RelationalPosture` | `CONNECT`, `SEPARATE`, `DEFEND`, `SUBMIT` |
| `MeaningNeed` | `CLARIFY`, `VALIDATE`, `REFRAME`, `NONE` |
| `ReframeType` | `LABEL`, `TEMPORAL`, `ROLE`, `SCALE`, `AGENCY`, `MEANING`, `NONE` |

All are `(str, Enum)` — values are stable strings.

### Module constants

- `_STANCE_HIGH_THRESHOLD = 0.7` — stance values at or above this
  threshold count as "high"; locked, test-asserted.
- `_HIGH_PRESSURE = frozenset({PressureLevel.HIGH, PressureLevel.CRITICAL})`
- `_RATIONALE` — dict of seven canonical per-reframe-type rationale
  strings; tests assert no other rationale ever appears in output.
- `_FORBIDDEN_ERA_FIELDS` — 15-element frozenset (see Privacy contract
  above).
- `_CANONICAL_REFRAME_TYPES` — locked 7-element frozenset.
- `_CANONICAL_FIELDS` — dict mapping the three ERA output classes to
  their canonical field sets; field drift fails import.

### Module-load runtime guards (3)

All three live in `emotional_alignment_schemas.py` and run at import:

- `assert_era_privacy_contract()` — fails if any ERA output class
  gained a forbidden field.
- `assert_era_field_sets_canonical()` — fails if any output class's
  field set drifted from the canonical set.
- `assert_reframe_types_canonical()` — fails if `ReframeType` gained
  or lost members.

Broken edits fail import — the privacy and shape contracts are
enforced structurally, not just by tests.

## APIs / entrypoints

### Public functions (3)

**`build_reframe_plan(snapshot, geometry, intention, primitive) -> ReframePlan`**

Pure function. Constructs the reframe plan from the structural inputs.

Under HIGH/CRITICAL pressure — only `AGENCY` and `SCALE` reframes
permitted (minimum-intervention principle):

| Trigger | Adds |
|---|---|
| `geometry.curvature` | SCALE |
| `intention.relational_posture == SUBMIT` ∨ `geometry.stance_world ≥ 0.7` | AGENCY |
| no trigger | `[NONE]` |

Under LOW/MEDIUM pressure — full palette, rules fire in priority order:

| Rule | Trigger | Adds |
|---|---|---|
| 2 | `temporal_linked ∧ anchor_present` | TEMPORAL |
| 3 | `shear ∨ stance_self ≥ 0.7` | LABEL |
| 4a | `boundary ∨ stance_other ≥ 0.7` | ROLE |
| 4b | `relational_posture == SUBMIT` | ROLE + AGENCY |
| 5 | `curvature` | SCALE |
| 6 | `torsion ∨ shear` | MEANING |
| – | no trigger | `[NONE]` |

Expected deltas are then computed:

- `SCALE` ∨ `LABEL` in steps → `pressure_delta = -1`
- `AGENCY` ∨ `ROLE` in steps → `agency_delta = +1`
- Under HIGH/CRITICAL: `pressure_delta = min(pressure_delta, 0)` —
  hard cap; reframe cannot increase pressure under high load.

**`compute_alignment_score(snapshot, geometry, intention, plan) -> float`**

Pure function returning a deterministic heuristic score ∈ [0, 1]:

```
score = 0.5  (baseline)
  + 0.2  if AGENCY ∈ steps ∧ expected_agency_delta ≥ 0
  + 0.2  if SCALE  ∈ steps ∧ expected_pressure_delta ≤ 0
  + 0.1  if TEMPORAL ∈ steps ∧ snapshot.temporal_linked
  + 0.1  if LABEL  ∈ steps ∧ (shear ∨ stance_self ≥ 0.7)
clamped to [0, 1], rounded to 4 decimals
```

`intention` is accepted for v2 extensibility but not consumed.

**`align_expression(snapshot, geometry, intention, primitive) -> AlignedExpression`**

Pure function. Composes plan + score + safety flags:

- `internal_relator_preserved` — `True` iff no `MEANING` step under
  HIGH/CRITICAL pressure.
- `safe_for_surface` — `True` iff `expected_pressure_delta ≤ 0` AND
  no `MEANING` step under HIGH/CRITICAL pressure.

`safe_for_surface = False` is the signal for the surface to defer to
human review rather than auto-apply the reframe.

### HTTP entrypoints

**None.** ERA is library-internal. The user-facing surface is
whatever Azimuth Transition + FEA Integration expose downstream.

## Integration points

### Upstream

- **`azimuth`** (sibling module) — provides `PressureLevel`,
  `IntensityLevel`, `Valence` enums. Not Batch 10 documented;
  candidate for a future sub-batch.
- **`language_schemas`** (sibling module) — provides
  `ExpressionPrimitive`. Not Batch 10 documented; candidate for a
  future sub-batch.

### Downstream consumers

- **`azimuth_transition.py`** — the primary wiring point.
  `compute_aligned_expression()` (around line 1091) maps
  `EnvelopeState` → ERA inputs and calls `align_expression()`. The
  result flows into FEA Integration.
- **`fea_integration_engine.py`** — `integrate_alignment()` (around
  line 195) consumes `AlignedExpression`; uses `safe_for_surface` +
  `alignment_score` to compute a halt level and surface directives.
- **Tests:** `tests/test_emotional_alignment.py` (≈ 1,115 lines, 21
  test classes, ≈ 102 cases) + `tests/test_fea_integration.py` for
  downstream integration.

### External specification

`SPEC_EMOTIONAL_REALITY_ALIGNMENT.md` (root of the repo) is the
behavioral source-of-truth. All SPEC section references in this doc
(e.g. SPEC § 5.2) map to that file. The SPEC's "Phase Plan" table is
partially outdated: items 1 and 2 of the "Pending" list ("Wire into
Azimuth", "Wire into Orchestrator post-step hook") are now done; item
3 (promote base types to `emotional_geometry_schemas.py`) remains
pending.

## Invariants

ERA enforces ten invariants from SPEC § 8 plus the structural guards
from `schemas.py`:

- **No raw user text** in any ERA input or output type; structural,
  test-asserted.
- **No identity fields** (`user_id`, `name`, `email`, `session_id`,
  etc.) — see `_FORBIDDEN_ERA_FIELDS` for the full 15-element list.
- **Deterministic.** Same inputs → byte-equal outputs; tests assert
  via repeat calls.
- **No I/O, no LLM, no network, no randomness.** Verified by
  source-code inspection tests.
- **Reframing never increases pressure under HIGH/CRITICAL.**
  `_compute_deltas` clamps via `min(delta, 0)`.
- **Reframing never attacks identity.** Achieved by fire-and-add-only
  rules; no rule produces self-attacking output.
- **Reframing never weakens constitutional constraints.** ERA emits
  advisory data; never sends or applies anything.
- **At least one of {precision, agency, temporal differentiation}
  increases** when any rule fires.
- **`alignment_score` is a pure function** of `(snapshot, geometry,
  intention, plan)`.
- **ERA is advisory only.** The module returns data; never calls a
  send/apply/commit primitive. Final decisions pass through the
  downstream Sovereignty Gate.
- **Schemas locked.** Field-set drift in any ERA output class fails
  module load.
- **Reframe type set locked.** Gaining or losing a `ReframeType`
  member fails module load.

## Non-goals

ERA is **not**:

- the Sovereignty Gate — ERA is advisory; the gate is a separate
  downstream subsystem that decides what to actually do;
- a text engine — ERA never receives or produces user text; inputs
  are structural snapshots, outputs are typed plans with canonical
  rationale strings;
- an HTTP service — there is no `/me/era/*` or similar endpoint;
  ERA is library-internal, invoked only by other Python modules;
- a state store — ERA is stateless; nothing is persisted by ERA,
  by design;
- an autonomous reframer — every call is request-driven; no
  scheduler, no background work, no auto-apply;
- a learning / training / personalisation surface — ERA never
  observes outcomes; the rule set is locked in code and the SPEC;
- an LLM caller or model client — pure deterministic Python;
- a generic emotion classifier — ERA consumes already-classified
  structural inputs from upstream;
- a privacy escape hatch — the schemas structurally exclude identity
  and raw-text fields, and the guards fail import on drift;
- a replacement for the v52 `emotional_physics` kernel reasoning
  mode — that lives inside `intelligence_kernel.py`, uses an LLM,
  and operates on raw user text; ERA and `emotional_physics` share
  a namespace word but are different systems.

## Fiction removed

The following constructs are explicitly not present in
`emotional_alignment_engine.py` or `emotional_alignment_schemas.py`
and must not be inferred:

- **Fabricated architecture:** "ERA engine AI", an autonomous
  reframer, a "reframing ML model", a learning loop, cross-user
  reframe sharing or training, a multi-step LLM reasoning chain, a
  background reframe scheduler, a batch reframe processor.
- **Fabricated APIs:** `apply_reframe()`, `commit_plan()`,
  `send_reframe()` — ERA never sends or applies; only returns
  advisory data. `async_reframe()` or streaming variants —
  synchronous, single-call only. `from_text(raw_user_text)` — there
  is no text input. Multi-plan / batch generation, plan diff, plan
  merge — none exist.
- **Fabricated security framings:** "ERA stores user emotional
  history" — stateless. "ERA logs to a moderation pipeline" — no
  logging. "ERA does identity / PII handling" — structurally
  precluded.
- **Fabricated integrations:** direct HTTP endpoint — none. Direct
  Operator State writes — ERA doesn't touch Operator State. Direct
  Memory Vault writes — ERA doesn't persist. Direct Intelligence
  Kernel coupling — the kernel doesn't call ERA; Azimuth Transition
  does. "ERA emits canonical user-facing text" — `rationale` is
  engine-generated canonical strings, never user text.
- **Fabricated naming bridges:** ERA is not the v52
  `emotional_physics` kernel reasoning mode despite the namespace
  overlap on "emotional"; the two are different systems with
  different inputs (structural vs. raw text), different determinism
  (pure vs. LLM-mediated), and different invariants.

Only the behaviour, fields, integrations, and invariants described
in this document are present in the code; SPEC §§ 1-8 and worked
examples 9.1-9.6 are the authoritative behavioral source.
