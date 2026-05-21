# Language Layer

## Purpose

`language_layer` is the **type root and primitive selection layer** of
the ClarityOS Language Layer. It owns two roles:

- **The type root** (`language_schemas.py`) — the canonical enums,
  dataclasses, and derivation contract used by every Language Layer
  consumer. 7 production importers (primitive_selection_engine,
  azimuth_transition, feedback_schemas, emotional_alignment_schemas,
  emotional_alignment_engine, ingestion_engine, plus the alias in
  feedback_schemas) consume the types defined here.

- **The selection engine** (`primitive_selection_engine.py`) — the
  deterministic, pure-function chooser that, given a `LanguageContext`,
  emits an `ExpressionPlan` selecting the **primitive** (Motion /
  Geometry / Hydronics / Analogy), **tone** (Stable / Direct /
  Softened / Expansive), **structure** (Highly-structured / Moderate /
  Minimal), and **length** (Short / Medium / Long) of one
  conversational turn.

The Language Layer is **expression-only**. It selects HOW ClarityOS
speaks (tone / structure / length / metaphor frame), never WHAT it
decides. The four expression primitives are DERIVED views of the 10
base ClarityOS primitives — no new base primitives are introduced.

### Core invariants (from module docstrings + `SPEC_LANGUAGE_LAYER.md`)

1. **Derivation contract:** every `ExpressionPrimitive` maps to a
   non-empty subset of the 10 base primitives
   (`C, D, L, A, T, B, G, I, P, S`). Asserted at module load via
   `assert_derivation_contract()` + test-enforced.
2. **All schemas are frozen dataclasses.** Inputs to the engine are
   never mutated; outputs are constructed fresh.
3. **No I/O references inside any schema.** Pure data declarations.
4. **`EnvelopeSnapshot` is privacy-narrowed.** Carries ONLY the four
   documented structural fields from `azimuth.EnvelopeState` — never
   `raw_text` or `envelope_id`.
5. **Engine purity:** `select_expression_plan` is deterministic — no
   I/O, no randomness, no LLM calls. Same `LanguageContext` →
   byte-identical `ExpressionPlan`.

## Status

| File | Status | Reason |
|---|---|---|
| `language_schemas.py` | **CURRENT** | 7 production importers; module-load derivation guard active at runtime |
| `primitive_selection_engine.py` | **vNEXT — tested, production-dormant** | One public function fully implemented (8 private helpers + 3 locked constants), 39 behavioral test invocations in `tests/test_language_layer.py`, but **no production module imports it**. The selection engine is forward-wired and verified, awaiting runtime wiring. |

The two files are both canonicalized. The dormancy of
`primitive_selection_engine.py` is a runtime status, not a code-quality
status — every helper carries deterministic logic, every locked
constant is test-pinned, every priority rule is behaviorally covered.
This doc documents the implementation contract; future runtime wiring
will not change it.

The Language Layer's dormancy pattern matches `azimuth_transition.py`
(per [docs/azimuth.md](azimuth.md)) — implemented + tested + zero
production importers. The Phase‑2 work that wires this engine into the
runtime path is the natural follow-on once the surrounding subsystems
(orchestrator engines, sovereignty gate) reach implementation.

## Implementation location

- **Type root:** `language_schemas.py` (211 lines).
- **Selection engine:** `primitive_selection_engine.py` (311 lines).
- **External spec:** `SPEC_LANGUAGE_LAYER.md` (repo root).
- **Test file:** `tests/test_language_layer.py` — 39 behavioral
  invocations of `select_expression_plan` plus schema-shape tests.
- **Imports:**
  - `language_schemas.py`: stdlib (`dataclass`, `Enum`, `Optional`)
    + 4 types from `azimuth` (`IntensityLevel`, `IntentionClass`,
    `PressureLevel`, `Valence`) + 4 types from `orchestrator_schemas`
    (`DriftState`, `GeometryProfile`, `IdentityProfile`,
    `PropagationState`). Deepest depth-3 leaf in the schema graph
    (after azimuth and orchestrator_schemas).
  - `primitive_selection_engine.py`: stdlib (`from __future__`) + 7
    types from `language_schemas` + `PressureLevel` from `azimuth`
    + `ActorKind`, `AuthorizationTier` from `orchestrator_schemas`.
    Pure schema-consumer; no engine imports, no I/O.

## Data model (`language_schemas.py`)

### Enums (5) — categorical types

All `(str, Enum)`, all locked, all test-pinned.

| Enum | Values |
|---|---|
| `ConversationMode` | `OPERATOR`, `EXPLORATORY`, `EMOTIONAL`, `STRUCTURAL`, `DECISION` (5) |
| `ExpressionPrimitive` | `MOTION`, `GEOMETRY`, `HYDRONICS`, `ANALOGY` (4) |
| `ToneProfile` | `STABLE`, `DIRECT`, `SOFTENED`, `EXPANSIVE` (4) |
| `StructureProfile` | `HIGHLY_STRUCTURED`, `MODERATE`, `MINIMAL` (3) |
| `LengthProfile` | `SHORT`, `MEDIUM`, `LONG` (3) |

`ConversationMode` is the input dimension; the other four are output
dimensions assembled into `ExpressionPlan`. The 5-mode input space ×
the 4-primitive × 4-tone × 3-structure × 3-length output space is
fully enumerated — no continuous parameters in the Language Layer.

### Constants

| Constant | Value | Purpose |
|---|---|---|
| `BASE_PRIMITIVES` | 10-tuple of strings: `("C", "D", "L", "A", "T", "B", "G", "I", "P", "S")` | The 10 base ClarityOS primitives (single-letter codes from a parallel base-primitive system) |
| `EXPRESSION_PRIMITIVE_DERIVATION` | dict mapping each `ExpressionPrimitive` to a tuple of base codes | The structural contract preventing the Language Layer from introducing a new base primitive |
| `_BASE_PRIMITIVE_SET` | `frozenset(BASE_PRIMITIVES)` | Derived for set-difference operations in the module-load guard |

The locked derivation table:

```
Motion    ← D + T + B + P
Geometry  ← G + D + I
Hydronics ← L + D + B + P
Analogy   ← P + S + I
```

### Frozen dataclasses (3)

#### `EnvelopeSnapshot` — privacy-narrowed projection

```python
@dataclass(frozen=True)
class EnvelopeSnapshot:
    pressure_level:  PressureLevel
    valence:         Valence
    intensity:       IntensityLevel
    intention_class: IntentionClass
```

**The azimuth → language privacy boundary.** Carries ONLY the four
structural fields the Language Layer is permitted to read from an
upstream `azimuth.EnvelopeState`. The type intentionally has **no
`raw_text`** and **no `envelope_id`** — the Language Layer never sees
the user's intimate content, only the structural metadata derived by
the Envelope + Transition layers.

Construction recipe (documented inline in the schema):

```python
snapshot = EnvelopeSnapshot(
    pressure_level=env.pressure_level,
    valence=env.valence,
    intensity=env.emotional_intensity,
    intention_class=transition_candidate.intention_class,
)
```

The two upstream sources are azimuth-side: `env.*` from
`EnvelopeState`, `intention_class` from
`ExpressionCandidate.intention_class` (produced by
`azimuth_transition.build_candidate`).

#### `LanguageContext` — PSE input

```python
@dataclass(frozen=True)
class LanguageContext:
    envelope:           EnvelopeSnapshot
    drift_state:        DriftState
    geometry_profile:   GeometryProfile
    identity_profile:   IdentityProfile
    conversation_mode:  ConversationMode
    propagation_state:  Optional[PropagationState] = None
    last_primitive:     Optional[ExpressionPrimitive] = None
```

5 required + 2 optional fields. The optional fields are the Language
Layer's bridge to runtime state:

- `propagation_state` — carries the orchestrator C/D/G/I/S envelope
  from upstream. When `None`, the engine treats the request as
  fresh-start (no prior geometry to compare against).
- `last_primitive` — the previous turn's primitive, used by the
  engine's whiplash prevention. When `None`, no whiplash check fires
  (the engine is free to choose).

#### `ExpressionPlan` — PSE output

```python
@dataclass(frozen=True)
class ExpressionPlan:
    primitive: ExpressionPrimitive
    tone:      ToneProfile
    structure: StructureProfile
    length:    LengthProfile
    rationale: str = ""
```

4 required + 1 default-empty. `rationale` is the deterministic
explanation string built by the engine's `_build_rationale` helper —
a first-class output, not an afterthought. Consumers can inspect
*why* a primitive was chosen without re-running the algorithm.

### Privacy boundary

**`EnvelopeSnapshot` is the language layer's privacy contract.** The
docstring is explicit: *"This type intentionally has NO raw_text and
NO envelope_id. The Language Layer never sees the user's intimate
content."*

The enforcement model differs from azimuth's `CloudMetadata`:

| Type | Enforcement |
|---|---|
| `azimuth.CloudMetadata` | `_FORBIDDEN_CLOUD_FIELDS` blocklist + `assert_cloud_privacy_contract()` runtime guard + test-locked field set |
| `language_schemas.EnvelopeSnapshot` | Construction discipline only — caller must build the snapshot, never pass `EnvelopeState` directly. No `_FORBIDDEN_FIELDS` guard, no field-set lock test. |

If `raw_text: str` were added to `EnvelopeSnapshot`, only the
docstring would complain — no structural assertion fires. PASS‑3C
should consider whether to mirror the azimuth pattern.

### Module-load guard (1)

```python
def assert_derivation_contract() -> None:
    ...
```

Runs at module load (line 211 of `language_schemas.py`). Three checks:

1. Every value in `EXPRESSION_PRIMITIVE_DERIVATION` is a non-empty tuple.
2. Every element of every tuple is in `BASE_PRIMITIVES` (set-difference
   must be empty).
3. Every `ExpressionPrimitive` enum value has an entry in the
   derivation dict.

Defense in depth: a structurally broken edit (typo in a derivation
tuple, missing primitive, extra base code) fails import, not just
`pytest`. Same pattern as `orchestrator_schemas.assert_minimal_orchestrator_contract`.

### Schema-layer drift surfaces

`language_schemas.py` is a declarative schema module; it defers most
validation to the caller and to the test suite. The following are
intentional design choices, not bugs — but each is a place where caller
discipline carries load that the module itself does not enforce.

**No `__post_init__` / no runtime type enforcement.** Wrong enum types,
NaN floats on `DriftState.magnitude` or `GeometryProfile.pressure_load`
(inherited from the orchestrator schema layer) all construct silently.
Type annotations are advisory.

**Base primitives are string codes, not an enum.** A consumer
hard-coding `"X"` expecting it to be a base primitive would silently
fail any set-membership check. The derivation dict is guarded at
module load; consumer-side typos are not. Same fragility pattern as
`RISK_FLAGS_CANONICAL` (azimuth) and `INVARIANTS_CANONICAL`
(orchestrator_schemas).

**`EnvelopeSnapshot` has no field-set lock test.** Unlike
`CloudMetadata` — which has `test_only_canonical_categorical_fields`
asserting the exact 9-field set — `EnvelopeSnapshot` is structurally
unguarded. If a future PR adds `raw_text` to the snapshot, the test
suite won't fail.

**`Invariant 3 ("No I/O references inside any schema")` has no obvious
test mechanism.** Orchestrator_schemas verifies its minimality contract
via `TestMinimalOrchestratorInvariants` (source AST scan). The
equivalent for `language_schemas.py` may or may not exist — worth
verifying.

**`LanguageContext.propagation_state` and `.last_primitive` default
to `None`.** Both are optional; the engine handles both. Callers
constructing a `LanguageContext` by hand may forget one and the
engine will silently take the "no prior" branch. The optional-with-
default pattern is rare in this codebase — most schemas require all
fields.

**`ExpressionPlan.rationale` defaults to empty string.** A synthetic
plan constructed without the trace passes type-check; consumers that
rely on the rationale string for logging or debugging won't get one.

## APIs / entrypoints

### Part A: `language_schemas.py` — CURRENT

**`assert_derivation_contract() -> None`** (line 189)

Runtime guard. Raises `AssertionError` if `EXPRESSION_PRIMITIVE_DERIVATION`
drifts from the locked contract. **Invoked at module load** (line 211)
+ called by the test suite.

The schema module is otherwise pure-declarative: enum definitions,
dataclass definitions, constant declarations. No constructors beyond
the dataclass `__init__` synthesized by `@dataclass(frozen=True)`.

### Part B: `primitive_selection_engine.py` — vNEXT (production-dormant)

The entire public surface is one function:

#### `select_expression_plan(ctx: LanguageContext) -> ExpressionPlan` (line 269)

Pure, deterministic selection of the response shape for one turn.

**Algorithm (priority order, higher priority wins):**

1. **Hard override 1:** `ctx.envelope.pressure_level ∈ {HIGH, CRITICAL}`
   → `HYDRONICS` primitive + `STABLE` tone + `HIGHLY_STRUCTURED` +
   `MEDIUM`. Bypasses whiplash check.
2. **Hard override 2:** `ctx.drift_state.in_bounds == False`
   → `ANALOGY` primitive (drift reduction). Bypasses whiplash check.
3. **Mode-driven** (no hard override):
   - `STRUCTURAL`  → `GEOMETRY`
   - `DECISION`    → `MOTION`
   - `OPERATOR`    → `GEOMETRY` if (USER + EXECUTE), else `MOTION`
   - `EXPLORATORY` → `ANALOGY`
   - `EMOTIONAL`   → `HYDRONICS`
   - default       → `GEOMETRY`
4. **Whiplash prevention:** if `ctx.last_primitive` is set and the
   mode-driven candidate differs without a meaningful geometry change,
   stick with `last_primitive` UNLESS the current mode strictly
   requires a different primitive (`STRUCTURAL` strictly requires
   `GEOMETRY`; `DECISION` strictly requires `MOTION`). Hard overrides
   (rules 1 and 2) always bypass whiplash.
5. Compute `(tone, structure, length)` from pressure + mode via
   `_select_tone_structure_length`.
6. Build deterministic `rationale` string via `_build_rationale`.

**Returns:** `ExpressionPlan` — deterministic given the input.

#### Private helpers (8)

| Helper | Purpose |
|---|---|
| `_hard_override_primitive(ctx)` | Rules 1 + 2; returns `Optional[ExpressionPrimitive]` |
| `_operator_mode_primitive(ctx)` | OPERATOR tie-break: USER + EXECUTE → GEOMETRY, else MOTION (per spec § 6.1) |
| `_mode_driven_primitive(ctx)` | Rules 3–8; pure 5-mode dispatch + default |
| `_meaningful_geometry_change(ctx)` | True iff `pressure_load` OR `stability_score` moved ≥ delta vs `propagation_state.geometry_profile` (no prior → True) |
| `_mode_strictly_requires(mode, primitive)` | True iff `(STRUCTURAL, GEOMETRY)` or `(DECISION, MOTION)` — these escape whiplash prevention |
| `_select_primitive(ctx)` | Full chain: override → mode candidate → whiplash check |
| `_select_tone_structure_length(ctx)` | Pressure override (STABLE/HIGHLY_STRUCTURED/MEDIUM) → 5-mode table → safe default |
| `_build_rationale(ctx, primitive, tone, structure, length)` | Deterministic `" · "`-joined trace; pressure/drift/continuity/mode branch by inspection order |

Every helper is pure. Every helper is byte-deterministic given inputs.

#### Locked tuning constants (3)

| Constant | Value | Purpose |
|---|---|---|
| `_HIGH_PRESSURE` | `frozenset({PressureLevel.HIGH, PressureLevel.CRITICAL})` | Trigger HYDRONICS hard-override + STABLE tone (invariants 3, 5) |
| `_PRESSURE_LOAD_DELTA` | `0.2` (float) | Whiplash detection threshold for pressure change |
| `_STABILITY_SCORE_DELTA` | `0.2` (float) | Whiplash detection threshold for stability change |

All three documented as "locked for deterministic test behavior."
Changing any of these changes engine output and breaks behavioral
tests.

#### Tone / structure / length decision table

```
pressure ∈ {HIGH, CRITICAL}     → (STABLE,    HIGHLY_STRUCTURED, MEDIUM)
mode = OPERATOR                 → (DIRECT,    HIGHLY_STRUCTURED, MEDIUM)
mode = EXPLORATORY              → (EXPANSIVE, MODERATE,          LONG)
mode = EMOTIONAL                → (SOFTENED,  MODERATE,          MEDIUM)
mode = DECISION                 → (DIRECT,    HIGHLY_STRUCTURED, SHORT)
mode = STRUCTURAL               → (DIRECT,    HIGHLY_STRUCTURED, MEDIUM)
default                         → (STABLE,    MODERATE,          MEDIUM)
```

Pressure override is **invariant-driven**: HIGH/CRITICAL pressure
always forces `STABLE` tone (invariant 3 — "no emotional escalation").

## Integration points

### `language_schemas.py` — 7 production importers

| Importer | What it consumes |
|---|---|
| `primitive_selection_engine.py` | `ConversationMode, ExpressionPlan, ExpressionPrimitive, LanguageContext, LengthProfile, StructureProfile, ToneProfile` (7 types — full consumer) |
| `azimuth_transition.py` | `ExpressionPrimitive` (used as `_DEFAULT_PRIMITIVE = ExpressionPrimitive.GEOMETRY`) |
| `feedback_schemas.py` | `ConversationMode, ExpressionPrimitive` (aliased as `PrimitiveType = ExpressionPrimitive` for FIS naming parity) |
| `emotional_alignment_schemas.py` | `ExpressionPrimitive` |
| `emotional_alignment_engine.py` | `ExpressionPrimitive` |
| `ingestion_engine.py` | `ConversationMode, ExpressionPrimitive` |

This makes `language_schemas.py` tied with `orchestrator_schemas.py`
as the **second-most-imported types module in the codebase** (after
`azimuth.py` at 10 production importers).

### `primitive_selection_engine.py` — zero production importers

No production module imports `select_expression_plan`. The entire
surface is reachable only through `tests/test_language_layer.py`
(39 behavioral invocations).

The 7 upstream schema imports (10 types total from
language_schemas + azimuth + orchestrator_schemas) are eager — the
engine is fully resolved at import time, just not exercised by any
production path.

### Tests — `tests/test_language_layer.py`

No dedicated `tests/test_language_schemas.py` or
`tests/test_primitive_selection_engine.py`. All tests live in
`tests/test_language_layer.py`, treating the schema + engine pair as
one subsystem:

- 39 behavioral invocations of `select_expression_plan` with
  constructed `LanguageContext` fixtures and asserted `ExpressionPlan`
  outputs.
- Tests pin the priority order, the hard overrides, the whiplash
  prevention, the mode-driven dispatch, and the secondary-dimension
  selection.

Additional test files that import `language_schemas` types as fixtures:

- `tests/test_azimuth_schemas.py` (cross-module type tests)
- `tests/test_azimuth_fea_integration.py`
- `tests/test_evaluate_drift_risk.py`
- `tests/test_fea_integration.py`
- `tests/test_emotional_alignment.py`
- `tests/test_feedback_ingestion.py`

### No coupling to

- `intelligence_kernel`, `model_router`, `memory_vault`,
  `operator_state` — none are imported by either file.
- No LLM SDKs, no `urllib`, no `requests`, no file I/O.
- No HTTP routes — neither file is referenced by `app.py`.
- No scheduler, no background work, no persistence.

## Invariants

### Schema-level (`language_schemas.py`)

Module-load enforced:

- **Derivation contract.** `EXPRESSION_PRIMITIVE_DERIVATION` maps each
  of the 4 `ExpressionPrimitive` values to a non-empty subset of
  `BASE_PRIMITIVES`. Drift fails import.

Structural (test-asserted + frozen-dataclass enforced):

- **All schemas are frozen.** Every `@dataclass` decorator carries
  `frozen=True`. Inputs are never mutated.
- **No I/O references inside any schema.** Documentation-asserted;
  no obvious source-AST guard equivalent to orchestrator_schemas's
  `TestMinimalOrchestratorInvariants`.
- **`EnvelopeSnapshot` carries ONLY 4 fields.** Documentation-
  asserted; no field-set lock test (drift surface — see schema-layer
  drift surfaces above).

### Engine-level (`primitive_selection_engine.py`)

Module-locked + test-enforced:

- **Pure function.** `select_expression_plan` has no I/O, no
  randomness, no LLM calls.
- **Determinism.** Same `LanguageContext` → byte-identical
  `ExpressionPlan`. Identifier randomness in upstream types
  (`envelope_id`, `propagation_id`) does NOT propagate into the
  selection output — the engine never reads those id fields.
- **HIGH/CRITICAL pressure ⇒ STABLE tone.** Asserted by the pressure
  override branch at line 176.
- **Drift out of bounds ⇒ ANALOGY.** Asserted by hard override rule 2
  at line 77.
- **Hard overrides bypass whiplash prevention.** Structural — rules 1
  and 2 return before whiplash logic runs.
- **`STRUCTURAL` strictly requires `GEOMETRY`; `DECISION` strictly
  requires `MOTION`.** Asserted by `_mode_strictly_requires` (line 128).
- **Rationale is deterministic.** Same inputs → same `" · "`-joined
  trace.

## Non-goals

`language_layer` is **not**:

- a kernel reasoning mode — neither file imports `intelligence_kernel`;
- a model invocation surface — no `model_router` import, no provider
  SDKs;
- a vault consumer — no `memory_vault` import;
- an `operator_state` writer or reader — no `operator_state` import;
- an HTTP service — no routes in `app.py`;
- a state store — fully stateless;
- a text generator — the engine selects the SHAPE of the response
  (primitive / tone / structure / length); the actual text rendering
  is downstream;
- a sender — `select_expression_plan` returns an `ExpressionPlan`;
  the surface decides what to do with it. The user always decides
  whether to send the rendered text;
- a learning / training / personalisation surface — the rule set is
  locked in code and in `SPEC_LANGUAGE_LAYER.md`; the engine never
  observes outcomes;
- an ML model — pure deterministic Python, rule-based, no weights;
- a multi-turn aggregator — every call evaluates a single
  `LanguageContext`. The `last_primitive` field carries continuity but
  the engine remains single-turn;
- a privacy escape hatch — `EnvelopeSnapshot` is the only Language
  Layer view of the user's reflection, and it carries no raw text by
  design.

## Fiction removed

The following constructs are explicitly not present in
`language_schemas.py` or `primitive_selection_engine.py` and must not
be inferred:

- **No active production wiring for `primitive_selection_engine`.**
  `select_expression_plan` is fully implemented + tested but no
  production module currently invokes it. This is a runtime status,
  not a code-quality status — same vNEXT framing as
  `azimuth_transition.py`.
- **No `__post_init__` validation on any dataclass.** Wrong enum
  types, NaN floats, semantically inconsistent field combinations all
  construct silently.
- **No `_FORBIDDEN_*_FIELDS` set for `EnvelopeSnapshot`.** Privacy is
  enforced by construction discipline only, not by structural
  assertion. If/when the snapshot becomes a wire contract, a
  forbidden-fields guard would be required (none exists today).
- **No field-set lock test for `EnvelopeSnapshot`.** The canonical
  4-field set is documentation-locked, not test-locked.
- **No schema_version field on any Language Layer type.** Consistent
  with the fact that none of these types cross an external boundary
  (the user-facing surface receives the rendered text, not the
  `ExpressionPlan`).
- **No engine imports for `primitive_selection_engine`.** The engine
  consumes only schema types from 3 schema roots (language_schemas,
  azimuth, orchestrator_schemas). No `model_router`, no
  `emotional_alignment_engine`, no `ingestion_engine` cross-call.
- **No mutation of `LanguageContext` or `ExpressionPlan`.** Both are
  frozen; the engine constructs a new `ExpressionPlan` per call.
- **No file I/O at runtime.** No prompt loading, no rule loading from
  files — every constant is defined inline in the source.
- **No randomness.** `_new_local_id` is not used by either Language
  Layer module; no `secrets.token_urlsafe` call anywhere. Determinism
  is content-based, period.
- **No multiple algorithms.** The engine runs ONE priority chain.
  There is no "model selection" or "strategy" parameter.
- **No autonomous turn loop.** `select_expression_plan` is invoked
  per turn by the caller. The engine has no scheduler, no background
  work, no auto-resume.
- **No coupling to `azimuth_transition.evaluate_drift_risk` flag
  vocabulary.** The Language Layer reads `drift_state.in_bounds`
  (boolean) — it does not inspect `risk_flags`. The two engines are
  parallel consumers of orchestrator/azimuth types, not chained.

Only the behaviour, fields, integrations, and invariants described in
this document are present in the code; the verified surface is locked
by the tests in `tests/test_language_layer.py` (39 behavioral
invocations + schema-shape tests).
