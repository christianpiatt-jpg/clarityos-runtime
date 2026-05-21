# Azimuth

## Purpose

`azimuth` is the **type root and transition layer** of the Azimuth
Mechanic. It owns two roles:

- **The type root** (`azimuth.py`) — the canonical enums, dataclasses,
  and risk-flag set used by every intelligence-layer subsystem. ERA,
  FEA Integration, ambient_trust, language_schemas, feedback_schemas,
  ingestion_engine, and primitive_selection_engine all import from
  here. With 10 production importers, `azimuth.py` is the most-imported
  types module in the codebase.

- **The transition engine** (`azimuth_transition.py`) — the
  deterministic mapping from an on-device `EnvelopeState` through
  ERA → ambient_trust → FEA Integration into an
  `IntegratedAlignmentResult`, plus drift-risk evaluation and the
  device→cloud privacy-boundary crossing (`CloudMetadata`).

The two files together form the second-innermost privacy boundary
in the Azimuth Mechanic: they can read the full `EnvelopeState` on
device, derive a privacy-safe `CloudMetadata` for upload, and emit a
structural advisory verdict (`IntegratedAlignmentResult`) for
downstream surfaces.

### Core invariants (from `SPEC_AZIMUTH_MECHANIC.md`)

1. **Privacy boundary:** `EnvelopeState.raw_text` and
   `ExpressionCandidate.raw_text` MUST NEVER serialize to network,
   file, or non-local storage. Only `CloudMetadata` may cross the
   device → cloud boundary.
2. **User sovereignty:** the user can always stay in envelope, always
   reject reframings, and the system never sends on the user's
   behalf.
3. **Intent preservation:** reframings must preserve intention class
   and meet `preserved_intent_score >= 0.7` to be accepted.

## Status

| File | Status | Reason |
|---|---|---|
| `azimuth.py` | **CURRENT** | 10 production importers; all enums/dataclasses/constants active in runtime |
| `azimuth_transition.py` | **vNEXT — tested, production-dormant** | All 5 public functions are fully implemented (Phase 3 Units 5-9) and fully tested across 6 test files, but **no production module imports them**. The integration pipeline is forward-wired and verified, awaiting runtime wiring. |

The two files in this doc are both canonicalized. The dormancy of
`azimuth_transition.py` is a runtime status, not a code-quality
status — every function carries a real Phase 3 Unit implementation,
every privacy invariant holds, every test passes. PASS-4 documents
the implementation contract; future runtime wiring will not change
it.

### Family note

Two related files were excluded from Batch-20a's scope and are now
documented via Batch-30 PASS-1: `azimuth_envelope.py` (133 lines, 3
stubs) and `azimuth_reframing.py` (236 lines, 4 stubs plus the
`IntentSpec` dataclass). Both remain **Phase-1 skeletons** — every
public function raises `NotImplementedError`, and
`tests/test_azimuth_schemas.py::TestSkeletonsRaise` asserts that they
continue to do so.

Their docstrings carry detailed Phase-3 design specs that have not
been implemented:

- `azimuth_envelope` — 4-axis heuristic plan for capturing intensity
  / valence / pressure / intention from raw text, plus
  `evaluate_envelope` idempotency and `mark_externalize` flag-flip
  semantics.
- `azimuth_reframing` — `IntentSpec` extraction targets (dates,
  deadlines, dollar amounts, proper nouns, decision verbs), a 9-row
  tone-modulation rule table (`risk_flag × audience/context →
  action`), scoring rubric for `preserved_intent_score` and
  `drift_risk_after`, and the `run_azimuth_check`
  ACCEPT/TWEAK/REJECT UX contract.

**Production reality has routed around both modules.**
`azimuth_transition.py` implements `build_candidate`,
`evaluate_drift_risk`, and `build_cloud_metadata` directly — covering
the operational territory these stubs were originally scoped to own.
Zero production modules import either stub; the only importer is the
stub-raise test.

`azimuth_reframing.IntentSpec` is the **only frozen dataclass in the
azimuth family defined outside `azimuth.py`**. If/when reframing is
implemented, the schema would likely migrate into `azimuth.py` to
preserve the "single source of truth for data types" pattern the
type root establishes.

Open implementation questions:

- Are the Phase-3 stubs still on the roadmap, or has the architecture
  moved on?
- Nine documented invariants (3 envelope + 6 reframing) have zero
  behavioral test coverage; implementation work needs those tests.
- `mark_externalize` is functionally a one-line
  `dataclasses.replace(env, user_marked_externalize=True)` — the
  lowest-effort stub to retire if reframing/envelope work resumes.

## Implementation location

- **Type root:** `azimuth.py` (317 lines).
- **Transition engine:** `azimuth_transition.py` (1,145 lines).
- **External spec:** `SPEC_AZIMUTH_MECHANIC.md` (repo root).
- **Imports:**
  - `azimuth.py`: stdlib only (`secrets`, `dataclasses`, `datetime`,
    `enum`, `typing`). Deepest leaf alongside `ambient_trust_schemas`
    in the intelligence-layer dependency graph.
  - `azimuth_transition.py`: imports from **7 subsystems** — `azimuth`,
    `emotional_alignment_engine`, `emotional_alignment_schemas`,
    `ambient_trust_engine`, `ambient_trust_schemas`,
    `fea_integration_engine`, `fea_integration_schemas`,
    `language_schemas`, `orchestrator_schemas`. Highest fan-in of any
    module in the intelligence layer.

## Data model (`azimuth.py`)

### Enums (10) — categorical types

All `(str, Enum)`, all locked.

| Enum | Values |
|---|---|
| `Valence` | `POSITIVE`, `NEGATIVE`, `MIXED`, `NEUTRAL`, `UNKNOWN` |
| `IntensityLevel` | `LOW`, `MEDIUM`, `HIGH`, `EXTREME` |
| `PressureLevel` | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| `PressureSlope` | `RISING`, `FLAT`, `FALLING` |
| `PressureShape` | `ASCENDING`, `DESCENDING`, `PLATEAU`, `SPIKE` |
| `AudienceType` | `SELF`, `ONE_TO_ONE`, `SMALL_GROUP`, `PUBLIC` |
| `ContextType` | `PERSONAL`, `PROFESSIONAL`, `HIGH_STAKES`, `LOW_STAKES` |
| `UrgencyLevel` | `LOW`, `MEDIUM`, `HIGH` |
| `IntentionClass` | `VENT`, `REQUEST`, `APOLOGIZE`, `BOUNDARY`, `OBSERVATION`, `GRATITUDE`, `OTHER` |
| `UserResponse` | `ACCEPT`, `TWEAK`, `REJECT` |

### Frozen dataclasses (6)

```python
@dataclass(frozen=True)
class EnvelopeState:
    raw_text:                str
    captured_at:             datetime
    emotional_intensity:     IntensityLevel
    valence:                 Valence
    pressure_level:          PressureLevel
    rough_intention:         str
    user_marked_externalize: bool = False
    envelope_id:             str  = field(default_factory=_new_local_id)

@dataclass(frozen=True)
class ExpressionCandidate:
    raw_text:        str
    intention:       str
    intention_class: IntentionClass
    pressure_level:  PressureLevel
    pressure_slope:  PressureSlope
    audience:        AudienceType
    context:         ContextType
    urgency:         UrgencyLevel
    risk_flags:      tuple = ()
    envelope_id:     str   = ""
    candidate_id:    str   = field(default_factory=_new_local_id)
    aligned:         Optional[IntegratedAlignmentResult] = None

@dataclass(frozen=True)
class CloudMetadata:
    pressure_shape:  PressureShape
    pressure_slope:  PressureSlope
    pressure_level:  PressureLevel
    audience_type:   AudienceType
    context_type:    ContextType
    urgency_level:   UrgencyLevel
    intention_class: IntentionClass
    risk_flags:      tuple = ()
    schema_version:  str   = "azimuth.v1"

@dataclass(frozen=True)
class CloudAdvisory:
    basin_pressure:      PressureLevel
    macro_field_weather: str
    audience_stake:      str
    advisories:          tuple = ()
    schema_version:      str   = "azimuth.v1"

@dataclass(frozen=True)
class ReframedExpression:
    original_intention:     str
    reframed_text:          str
    preserved_intent_score: float
    drift_risk_after:       float
    diff_notes:             tuple = ()
    candidate_id:           str   = ""

@dataclass(frozen=True)
class AzimuthCheckPrompt:
    landing_prediction: str
    reframed_options:   tuple
    user_question:      str = "Does this still feel like what you mean?"
```

### Privacy boundary

Three dataclasses are **device-local** (may contain `raw_text`,
identifiers, free-text intention): `EnvelopeState`,
`ExpressionCandidate`, `ReframedExpression`.

Three dataclasses are **upload-safe** (canonical categorical
metadata only, no free text): `CloudMetadata`, `CloudAdvisory`,
`AzimuthCheckPrompt`.

`CloudMetadata` is the only structure that crosses the device →
cloud boundary. Its field set is locked.

### Canonical risk flags (12)

`RISK_FLAGS_CANONICAL` is a 12-element tuple of canonical lowercase
flag names:

```
sharp_tone, soft_tone, high_pressure, vague_target,
name_calling, all_or_nothing, urgency_inflation,
passive_aggressive, absolutist_language, ambiguous_request,
hard_halt, soft_halt
```

The last two (`hard_halt`, `soft_halt`) are Phase 3 Unit 7
additions that mirror FEA Integration's `SurfaceHaltLevel`. They
fire only when `candidate.aligned` is populated.

### Cloud privacy contract

`_FORBIDDEN_CLOUD_FIELDS` is a 10-element frozenset of field names
that MUST NOT appear in `CloudMetadata`: `raw_text`, `user_id`,
`envelope_id`, `candidate_id`, `intention`, `rough_intention`,
`name`, `names`, `identity`, `identifier`.

`assert_cloud_privacy_contract` (line 308) is the runtime guard.
**Unlike peer subsystems (ERA, FEA, ambient_trust), this guard is
NOT auto-run at module load** — it is invoked only by the test
suite. This is a deliberate design choice noted in the function
docstring ("Called by the test suite. Also safe to call at
module-load time in development."), but is worth flagging since it
diverges from the post-azimuth pattern.

### Schema-layer drift surfaces

`azimuth.py` is a declarative schema module; it deliberately defers
most validation to the caller and to the test suite. The following are
intentional design choices, not bugs — but each is a place where caller
discipline carries load that the module itself does not enforce.

**No runtime type enforcement.** No dataclass uses `__post_init__`;
type annotations are advisory. `EnvelopeState(pressure_level=Valence.NEGATIVE, ...)`
constructs without complaint (wrong-enum). Construction of an envelope
with semantically inconsistent fields (e.g. `valence=Valence.UNKNOWN`
paired with `emotional_intensity=IntensityLevel.EXTREME`) is also
unchecked. The test suite locks each enum's value set but not pairwise
field consistency.

**Two-layer privacy enforcement.** The wire-safety contract is
enforced by **two complementary mechanisms**, not one:

- `_FORBIDDEN_CLOUD_FIELDS` + `assert_cloud_privacy_contract()`
  catches field names matching the 10-entry identity/free-text
  blocklist documented above (`raw_text`, `user_id`, …, `identifier`).
- The test suite's `test_only_canonical_categorical_fields`
  (`tests/test_azimuth_schemas.py:284`) locks the exact 9-field
  `CloudMetadata` set. This catches any new field — including ones
  that would not appear in the blocklist (e.g. a hypothetical
  `summary_text`). The runtime guard is necessary; the field-set
  lock is sufficient.

**Serialization contract — caller-managed.** No `to_dict` / `from_dict`
helpers exist in `azimuth.py`; every consumer implements its own JSON
projection.

- `(str, Enum)` values serialize cleanly as their underlying string.
- `datetime` (`EnvelopeState.captured_at`) has no built-in JSON
  encoder — callers must convert via `.isoformat()` or a custom
  encoder.
- `tuple` fields (`risk_flags`, `diff_notes`, `advisories`) JSON-encode
  as arrays; round-trips return `list`, not `tuple`. Structural
  equality checks may diverge if a consumer assumes identity.

**`schema_version` is an unconstrained string.** `CloudMetadata` and
`CloudAdvisory` both default to `"azimuth.v1"`, but the field is a
free `str` — no enum, no negotiation, no downstream version check. A
bump to `"azimuth.v2"` would not break any consumer that does not
explicitly test for the value.

**Empty-string id defaults.** `ExpressionCandidate.envelope_id` and
`ReframedExpression.candidate_id` default to `""`, **not `None`**. A
caller writing `if c.envelope_id:` treats the default as falsy; a
caller writing `if c.envelope_id is not None:` treats it as set. The
empty string is a sentinel, not an absence — callers correlating
candidates back to envelopes must pick one convention and hold it.

**`RISK_FLAGS_CANONICAL` is a tuple, not an enum.** Membership checks
(`"sharp_tone" in candidate.risk_flags`) work by string identity. A
typo in a producer (`"sharptone"`) silently fails downstream rules.
Twelve entries are locked by the test suite, but the consumer side
has no compile-time check.

**`ExpressionCandidate.aligned` is a forward reference.** The
annotation `Optional[IntegratedAlignmentResult]` is a string at
runtime because of `from __future__ import annotations`. The real
import lives behind a `TYPE_CHECKING` gate in `azimuth.py` to break
the azimuth ↔ fea_integration import cycle. Static type-checkers
resolve it; `isinstance` checks at runtime require the consumer to
import `IntegratedAlignmentResult` from `fea_integration_schemas`
itself. See [docs/fea_integration.md](fea_integration.md) for the
producer side.

## APIs / entrypoints

### Part A: `azimuth.py` — CURRENT

**`assert_cloud_privacy_contract() -> None`** (line 308)

Runtime guard. Raises `AssertionError` if `CloudMetadata` has
gained any field in `_FORBIDDEN_CLOUD_FIELDS`. **Not auto-run at
module load.** Called by `tests/test_azimuth_schemas.py`.

### Part B: `azimuth_transition.py` — vNEXT (production-dormant)

All 5 functions are pure, deterministic, side-effect-free. None
are called by any production module; all are called only by tests.

#### `detect_externalization_intent(env, recent_history=()) -> bool` (line 93, Phase 3 Unit 9)

Three triggers (any sufficient):

1. **Explicit user flag:** `env.user_marked_externalize == True`.
2. **Canonical lexical markers:** word-bounded, case-insensitive
   scan of `env.raw_text` for any of 8 locked phrases (`"i want to
   tell them"`, `"should i send"`, `"should i say"`, etc.). Word
   boundaries on both sides prevent substring drift.
3. **Topic recurrence within 30 minutes:** `recent_history`
   contains 3+ envelopes that are (a) within
   `_TOPIC_RECURRENCE_WINDOW_SECONDS` (1800s) of `env.captured_at`,
   AND (b) have `rough_intention` with Jaccard similarity ≥ 0.5
   against `env.rough_intention`. Jaccard uses lowercase + split on
   non-alphanumerics; both-empty token sets return 0.0.

Raises `ValueError` on non-`EnvelopeState` `env` or any
non-`EnvelopeState` in `recent_history`.

#### `build_candidate(env, *, audience, context, …) -> ExpressionCandidate` (line 251, Phase 3 Unit 6)

Constructs an `ExpressionCandidate` from an envelope plus contextual
hints. Internally calls `compute_aligned_expression(env)` (line
312) to populate the `aligned` field. The candidate stays
**device-local**; only `build_cloud_metadata` produces an
upload-safe object.

Defaults `intention_class` via `_derive_intention_class` if not
supplied. Default `pressure_slope=FLAT`, `urgency=LOW`.

Priority cascade for `intention_class` derivation (first match
wins):
1. VENT → 2. APOLOGIZE → 3. REQUEST → 4. BOUNDARY (markers OR
word-bounded `"no"`) → 5. OBSERVATION → 6. GRATITUDE → 7. OTHER
(fallthrough)

#### `evaluate_drift_risk(env, *, candidate) -> ExpressionCandidate` (line 395, Phase 3 Unit 7)

Returns a new `ExpressionCandidate` (via `dataclasses.replace`) with
`risk_flags` populated. Output flags are **sorted** for
deterministic order. Pure, never mutates inputs.

11-rule table (some rules emit 2 flags):

| Rule | Condition | Flag(s) |
|---|---|---|
| 1 | `intensity ∈ {HIGH, EXTREME}` AND `audience ≠ SELF` | `sharp_tone` |
| 2 | `pressure ∈ {HIGH, CRITICAL}` AND `context ∈ {PROFESSIONAL, HIGH_STAKES}` | `high_pressure` |
| 3 | `rough_intention` word-count ≤ 1 AND `audience ∈ {SMALL_GROUP, PUBLIC}` | `vague_target` |
| 4 | `raw_text` contains `"you always"` or `"you never"` | `name_calling` + `absolutist_language` |
| 5 | ≥3 urgency markers AND `candidate.urgency ≠ HIGH` | `urgency_inflation` |
| 6 | `intention_class == REQUEST` AND no action verb in `raw_text` | `ambiguous_request` |
| 7 | `context == HIGH_STAKES` AND `intensity == LOW` | `soft_tone` |
| 8 | passive-aggressive token AND `valence == NEGATIVE` | `passive_aggressive` |
| 9 | absolutist token (word-bounded) in `raw_text` | `absolutist_language` + `all_or_nothing` |
| 10 | `candidate.aligned.halt_level == HARD` | `hard_halt` |
| 11 | `candidate.aligned.halt_level == SOFT` | `soft_halt` |

Rules 10-11 are skipped silently when `candidate.aligned is None`.

#### `build_cloud_metadata(candidate) -> CloudMetadata` (line 546, Phase 3 Unit 8)

The privacy-boundary crossing point. Derives `pressure_shape` from
`(pressure_level, pressure_slope)` and passes the remaining
categorical fields through. **Runs 6 defensive `isinstance` enum
checks** before constructing the output — a stronger guarantee than
any peer subsystem provides at output time. Any string-typed
override raises `ValueError` before crossing the cloud boundary.

`_derive_pressure_shape` decision table (SPIKE checked first):

| slope | level | shape |
|---|---|---|
| `RISING` | `HIGH` or `CRITICAL` | `SPIKE` |
| `RISING` | any other | `ASCENDING` |
| `FALLING` | any | `DESCENDING` |
| `FLAT` | any | `PLATEAU` |

#### `compute_aligned_expression(env) -> IntegratedAlignmentResult` (line 1091, Phase 3 Unit 5)

The integration pipeline. Five steps:

1. Validate `env` is an `EnvelopeState`.
2. Map envelope to `(EmotionalSnapshot, EmotionalGeometry,
   EmotionalIntention)` via `_map_envelope_to_fea_inputs`.
3. Call `align_expression(snapshot, geometry, intention,
   ExpressionPrimitive.GEOMETRY)` (ERA).
4. Build v1 Ambient Trust state via `_default_session_context`,
   `assess_trust_state`, `verify_no_hard_stops`,
   `verify_comprehension_leads_action`, and a placeholder
   `PropagationState` via `_default_propagation_state`.
5. Call `integrate_alignment(aligned, session, trust, env,
   propagation, momentum, understanding)` (FEA Integration).

Returns the `IntegratedAlignmentResult` verbatim.

**V1 placeholder semantics:** `session`, `trust`, `envelope`,
`propagation` are **reserved inputs in FEA v1** — accepted but not
branched on (verified in Batch-18 PASS-3D §1). The
`_default_session_context` returns a blank session
(ability=0, comprehension=0, no exposures, no hard stops, ack=True);
`_default_propagation_state` returns a structurally-valid
`PropagationState` using a `_FIXED_EPOCH = datetime(2026, 1, 1)`
for deterministic identifier timestamps. Only `momentum` and
`understanding` carry real semantic content in v1.

### Lexical analysis substrate

`azimuth_transition.py` contains **44 private constants** for
textual analysis: marker tuples (externalization, urgency,
absolutist, passive-aggressive, name-calling, temporal recurrence,
memory anchor, self-attack, other-attack, world-hostile,
boundary-intent, contain/express/transform intent, submit/separate/
defend, clarify/validate/reframe meaning, intention-class
derivation by category), precompiled word-boundary regexes
(absolutist, passive-aggressive, urgency, externalization,
boundary-no), threshold constants (recurrence window,
similarity threshold, stance denominator, target-state max length),
and the `_DEFAULT_PRIMITIVE = ExpressionPrimitive.GEOMETRY`
default.

The marker sets are the load-bearing substrate for the priority
cascades documented above. Every value is locked; adding a marker
is a deliberate spec change.

## Integration points

### `azimuth.py` — 10 production importers

| Importer | What it consumes |
|---|---|
| `azimuth_envelope.py` | enums + EnvelopeState |
| `azimuth_reframing.py` | enums + ReframedExpression types |
| `azimuth_transition.py` | full surface |
| `language_schemas.py` | `IntensityLevel`, `IntentionClass`, `PressureLevel`, `Valence` |
| `ingestion_engine.py` | `PressureLevel` |
| `feedback_schemas.py` | `PressureLevel` |
| `fea_integration_engine.py` | `EnvelopeState` (reserved-in-v1 input type) |
| `emotional_alignment_schemas.py` | `IntensityLevel`, `PressureLevel`, `Valence` |
| `emotional_alignment_engine.py` | `PressureLevel` |
| `primitive_selection_engine.py` | `PressureLevel` |

This makes `azimuth.py` the **most-imported types module in the
codebase**. Locking its enums and dataclasses stabilizes every
downstream subsystem.

### `azimuth_transition.py` — zero production importers

No production module imports any of the 5 public functions. The
entire surface is reachable only through tests:

- `tests/test_azimuth_schemas.py`
- `tests/test_azimuth_fea_integration.py`
- `tests/test_build_candidate.py`
- `tests/test_build_cloud_metadata.py`
- `tests/test_evaluate_drift_risk.py`
- `tests/test_detect_externalization_intent.py`

The 7 upstream subsystems are imported but only used inside
`azimuth_transition`'s own helpers and the integration pipeline.

### No coupling to
- `intelligence_kernel`, `model_router`, `memory_vault`,
  `operator_state` — none are imported by either file.
- No LLM SDKs, no `urllib`, no `requests`, no file I/O.
- No HTTP routes — neither file is referenced by `app.py`.

## Invariants

### Determinism

- **Both files are pure.** No I/O, no LLM, no network.
- **Determinism is content-based, not identity-based.** The one
  source of randomness — `_new_local_id` (azimuth.py:161) using
  `secrets.token_urlsafe(12)` — is applied to `envelope_id` and
  `candidate_id` defaults. Neither id propagates into any computed
  output: `_map_envelope_to_snapshot`, `_map_envelope_to_geometry`,
  `_map_envelope_to_intention`, `_derive_intention_class`,
  `evaluate_drift_risk`, and `build_cloud_metadata` never read
  `envelope_id` or `candidate_id`. Same envelope content → byte-equal
  output, regardless of randomly-assigned ids.

### Privacy

- **Three local-only dataclasses:** `EnvelopeState`,
  `ExpressionCandidate`, `ReframedExpression` may contain
  `raw_text`, identifiers, free-text intention.
- **Three upload-safe dataclasses:** `CloudMetadata`,
  `CloudAdvisory`, `AzimuthCheckPrompt` carry canonical categorical
  metadata only.
- **Cloud-boundary guard:** `_FORBIDDEN_CLOUD_FIELDS` (10 entries)
  is asserted by `assert_cloud_privacy_contract` against
  `CloudMetadata.__dataclass_fields__`. **Test-invoked only, not
  auto-run at module load.**
- **Defense-in-depth at the boundary:** `build_cloud_metadata` runs
  6 `isinstance` enum checks on `pressure_level`, `pressure_slope`,
  `audience`, `context`, `urgency`, `intention_class` before
  constructing the output. String overrides raise `ValueError`.

### Output stability

- `evaluate_drift_risk` returns flags as a sorted tuple
  (`tuple(sorted(flags))`) for deterministic byte-equal output.
- `_derive_pressure_shape` uses an exclusive 4-branch decision table
  with SPIKE checked first.
- `_compute_trust_score`-derived determinism in
  `compute_aligned_expression` is byte-stable per ambient_trust's
  `round(score, 4)` contract.
- `_FIXED_EPOCH = datetime(2026, 1, 1, 0, 0, 0)` ensures the v1
  `PropagationState` placeholder has deterministic identifier
  timestamps.

### Frozen everywhere

All 6 dataclasses in `azimuth.py` are `@dataclass(frozen=True)`.
Inputs to `azimuth_transition` functions are never mutated;
`evaluate_drift_risk` uses `dataclasses.replace` to construct new
candidates rather than mutating.

### Priority cascades

Multiple functions use first-match-wins lexical cascades with
locked priority order:

- `_derive_intention_class`: VENT → APOLOGIZE → REQUEST → BOUNDARY
  (markers OR word-bounded `"no"`) → OBSERVATION → GRATITUDE → OTHER
- `_derive_regulatory_goal`: CONTAIN → TRANSFORM → EXPRESS (default)
- `_derive_relational_posture`: SUBMIT → DEFEND → SEPARATE → CONNECT
  (default)
- `_derive_meaning_need`: CLARIFY → VALIDATE → REFRAME → NONE
  (default)

Each marker set is locked at module load.

### User sovereignty (encoded by absence)

- No function in either file sends, applies, commits, or auto-acts.
- `ReframedExpression` is returned to the caller; the user always
  decides whether to accept, tweak, or reject (per
  `UserResponse` enum).
- No function bypasses `CloudMetadata` to upload anything else.

## Non-goals

`azimuth` is **not**:

- a kernel reasoning mode — neither file imports
  `intelligence_kernel`;
- a model invocation surface — no `model_router` import, no
  provider SDKs;
- a vault consumer — no `memory_vault` import;
- an operator_state writer or reader — no `operator_state` import;
- an HTTP service — no routes in `app.py`;
- a state store — fully stateless;
- an autonomous send/apply system — every operation is
  request-driven; `UserResponse` is always required before action;
- a generic text classifier — the marker sets are narrow, locked,
  and tied to specific intention/posture/meaning categories;
- a multi-turn aggregator — every call evaluates a single envelope;
- a privacy escape hatch — `CloudMetadata` is the only upload-safe
  type, and its field set is structurally locked.

## Fiction removed

The following constructs are explicitly not present in `azimuth.py`
or `azimuth_transition.py` and must not be inferred:

- **No active production wiring for `azimuth_transition`.** All 5
  public functions exist, are tested, and would work correctly if
  called — but no production module currently invokes them. This is
  a runtime status, not a code-quality status. PASS-4 marks this as
  vNEXT.
- **Module docstring in `azimuth_transition.py:18-21` is stale.**
  Claims "Phase 1 skeleton — Function bodies raise
  `NotImplementedError` pending Phase 3 Unit 5 real implementation."
  Reality: every public function has a Phase 3 Unit 5-9
  implementation. Code-side cleanup candidate (one-line fix).
- **`assert_cloud_privacy_contract` does not auto-run at module
  load.** It is defined but invoked only by tests, unlike peer
  subsystems (ERA / FEA / ambient_trust) whose privacy guards run
  at import. This is a deliberate-but-different choice.
- **`_new_local_id` is random.** `EnvelopeState.envelope_id` and
  `ExpressionCandidate.candidate_id` are randomly assigned via
  `secrets.token_urlsafe(12)`. This randomness does NOT propagate
  into any computation — but several function docstrings claim
  "deterministic — same inputs → same output" without qualifying
  that determinism is content-based, not identity-based.
- **No mutation of `EnvelopeState` or `ExpressionCandidate`.**
  Both are frozen; `evaluate_drift_risk` uses
  `dataclasses.replace`.
- **No multiple LLM calls.** `compute_aligned_expression` invokes
  ERA's `align_expression` once and FEA's `integrate_alignment`
  once. Neither is an LLM call — both are pure deterministic Python
  inside their respective subsystems.
- **No file I/O at runtime.** No prompt loading, no schema loading,
  no `Path.read_text()` anywhere.
- **No retry logic.** A failed alignment or integration call would
  raise; there is no fallback path in `compute_aligned_expression`.
- **No persistence.** No vault writes, no operator_state writes, no
  side effects beyond returning the result.
- **`CloudMetadata` is the only upload-safe type.** Anything else
  crossing the device boundary is a privacy violation.
- **No autonomous reframing.** `ReframedExpression` is returned to
  the caller; the user's `UserResponse` is always required.
- **Two files in the azimuth family are NOT documented here:**
  `azimuth_envelope.py` and `azimuth_reframing.py`. They are
  deferred to Batch-20b. Inferring their behavior from this doc
  would be unsafe.

Only the behaviour, fields, integrations, and invariants described
in this document are present in the code; the verified surface is
locked by the tests in `tests/test_azimuth_schemas.py`,
`tests/test_azimuth_fea_integration.py`,
`tests/test_build_candidate.py`,
`tests/test_build_cloud_metadata.py`,
`tests/test_evaluate_drift_risk.py`, and
`tests/test_detect_externalization_intent.py`.
