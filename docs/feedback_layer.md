# Feedback Layer

## Purpose

`feedback_layer` is the **schema root and ingestion engine** of the
ClarityOS Feedback Ingestion System (FIS). It owns two roles:

- **The type root** (`feedback_schemas.py`) — the canonical enums,
  dataclasses, and structural privacy guards for founder feedback. The
  narrowest-scoped schema root in the codebase, serving exactly one
  consumer.

- **The ingestion engine** (`ingestion_engine.py`) — the deterministic,
  pure-function classifier that, given a `FeedbackSubmission`, emits a
  `FeedbackPattern` carrying canonical structural metadata (pattern
  type / context / pressure / signal / primitive / adjustment) — and
  **never** raw text or identity.

The FIS converts founder feedback into **constitutional structural
patterns**. The input boundary carries the user's text; the output is
structurally guaranteed to omit every field that could carry the
user's words or who they are.

### Core invariants (from module docstrings + `SPEC_FEEDBACK_INGESTION.md`)

1. **Privacy contract:** `FeedbackPattern.__dataclass_fields__` MUST
   NOT contain any of: `text`, `raw_text`, `user_id`, `actor`,
   `session_id`, `identity`, `envelope_id`, `name`, `names`, `user`,
   `author`. Asserted at module load via
   `assert_pattern_privacy_contract()` + test-enforced.
2. **Field-set lock:** `FeedbackPattern.__dataclass_fields__` MUST
   equal the canonical 6-field set exactly. Asserted at module load
   via `assert_pattern_field_set_canonical()` + test-enforced.
3. **All schemas are frozen dataclasses.** Inputs are never mutated;
   outputs are constructed fresh.
4. **No I/O references inside any schema.** Pure data declarations.
5. **Engine purity:** `extract_pattern` is deterministic — no I/O, no
   randomness, no LLM calls. Same `FeedbackSubmission` →
   byte-identical `FeedbackPattern`.
6. **Output carries no raw text and no identity** — enforced both
   structurally (the dataclass shape) and behaviorally (the engine
   reads `submission.text` ONCE for lexical scans then discards).

## Status

| File | Status | Reason |
|---|---|---|
| `feedback_schemas.py` | **CURRENT** | 1 production importer; two module-load privacy guards active at runtime |
| `ingestion_engine.py` | **vNEXT — tested, production-dormant** | One public function fully implemented (5 private helpers + 7 locked tables), 19 behavioral test classes in `tests/test_feedback_ingestion.py`, but **no production module imports it**. The engine is forward-wired and verified, awaiting runtime wiring. |

The two files are both canonicalized. The dormancy of
`ingestion_engine.py` is a runtime status, not a code-quality status —
every helper carries deterministic logic, every locked table is
test-pinned, every priority rule is behaviorally covered. The
ingestion subsystem is the most-isolated component in the
intelligence-layer codebase: feedback_schemas has the lowest fan-in of
any schema root, and ingestion_engine is fully orphaned (not reachable
through any production call chain, even transitively).

The Feedback Layer's dormancy pattern matches `primitive_selection_engine`
(per [docs/language_layer.md](language_layer.md)) — implemented + heavily
tested + zero production importers. The Phase‑2 work that wires this
engine into a runtime path (the founder feedback console / introspection
surface) is the natural follow-on.

## Implementation location

- **Type root:** `feedback_schemas.py` (180 lines).
- **Ingestion engine:** `ingestion_engine.py` (254 lines).
- **External spec:** `SPEC_FEEDBACK_INGESTION.md` (448 lines, repo
  root).
- **Test file:** `tests/test_feedback_ingestion.py` — 731 lines, 19
  test classes covering schema shape, privacy contract, mapping table
  coverage, rule-by-rule behavior, signal detection, end-to-end
  worked examples, determinism, whiplash prevention, and source-code
  invariants.
- **Imports:**
  - `feedback_schemas.py`: stdlib (`dataclass`, `datetime`, `Enum`,
    `Optional`) + 1 type from `azimuth` (`PressureLevel`) + 2 types
    from `language_schemas` (`ConversationMode`, `ExpressionPrimitive`).
    Reused-types policy explicit in module docstring.
  - `ingestion_engine.py`: stdlib (`Optional`) + 5 types from
    `feedback_schemas` (`ExtractionContext`, `FeedbackPattern`,
    `FeedbackSubmission`, `PatternType`, `SignalType`) + `PressureLevel`
    from `azimuth` + 2 types from `language_schemas`
    (`ConversationMode`, `ExpressionPrimitive`). Pure schema-consumer;
    no engine imports, no I/O.

## Data model (`feedback_schemas.py`)

### Enums (2) — categorical types

All `(str, Enum)`, all locked, all test-pinned.

| Enum | Values |
|---|---|
| `SignalType` | `POSITIVE`, `NEGATIVE`, `NEUTRAL` (3) |
| `PatternType` | `TONE`, `DRIFT`, `PRESSURE`, `ALIGNMENT`, `BOUNDARY`, `USE_CASE` (6) |

Both new to this file. Unlike `language_schemas` (which redeclares its
full enum set), `feedback_schemas` keeps its surface narrow — only the
two enums truly local to the FIS subsystem are defined here.

### Reused-types policy

The module docstring (lines 12–16) explicitly names which types come
from upstream schema roots:

- `PressureLevel ← azimuth`
- `ConversationMode ← language_schemas`
- `ExpressionPrimitive ← language_schemas (aliased as PrimitiveType)`

This is the only schema root with an explicit reuse policy. The other
roots reuse types implicitly via imports; `feedback_schemas` documents
the reuse as architecture.

#### `PrimitiveType` alias

```python
PrimitiveType = ExpressionPrimitive
```

Line 41 — documented as "naming parity with the FIS spec." Same
re-export convention as `azimuth_reframing.UserResponse` (`noqa: F401`)
but at the schema layer rather than the engine layer. Consumers
writing to the FIS spec vocabulary can `from feedback_schemas import
PrimitiveType`; consumers writing to the language-layer vocabulary
use `ExpressionPrimitive`. Both names refer to the same type.

### Frozen dataclasses (3)

#### `FeedbackSubmission` — INPUT (carries text by design)

```python
@dataclass(frozen=True)
class FeedbackSubmission:
    text:           str
    mode:           ConversationMode
    pressure_level: PressureLevel
    primitive_used: ExpressionPrimitive
    timestamp:      datetime
```

The input boundary type. Documented at lines 71–77: *"this dataclass
carries the user's text BY DESIGN — it is the input boundary. The
text is read ONCE by the engine, transformed lexically, and discarded.
The engine NEVER returns text in its output."*

Caller responsibility: do not persist this object — pass through
`extract_pattern()` and discard.

#### `FeedbackPattern` — OUTPUT (privacy-locked, exactly 6 fields)

```python
@dataclass(frozen=True)
class FeedbackPattern:
    pattern_type:         PatternType
    context:              ConversationMode
    pressure_level:       PressureLevel
    signal:               SignalType
    primitive_involved:   ExpressionPrimitive
    suggested_adjustment: str
```

**Exactly 6 fields, structurally enforced.** No text fields. No
identity fields. No timestamps (the input timestamp is deliberately
not propagated). The only `str` field is `suggested_adjustment`, which
carries engine-generated canonical short strings from
`ingestion_engine._ADJUSTMENT_TABLE` — not user content.

#### `ExtractionContext` — optional whiplash hint

```python
@dataclass(frozen=True)
class ExtractionContext:
    last_pattern_type: Optional[PatternType]      = None
    last_pressure:     Optional[PressureLevel]    = None
    last_mode:         Optional[ConversationMode] = None
```

All three fields `Optional` with `None` defaults. Constructing
`ExtractionContext()` with no arguments yields an empty hint that the
engine treats as "no whiplash check."

### Privacy boundary — gold-standard enforcement

**Two complementary module-level guards**, both invoked at module load
(lines 179, 180):

#### Guard 1: `assert_pattern_privacy_contract()` (line 144)

Checks `FeedbackPattern.__dataclass_fields__` against
`_FORBIDDEN_PATTERN_FIELDS` — an 11-entry frozenset:

```python
_FORBIDDEN_PATTERN_FIELDS = frozenset({
    "text", "raw_text", "user_id", "actor", "session_id",
    "identity", "envelope_id", "name", "names", "user", "author",
})
```

If any forbidden field name appears in
`FeedbackPattern.__dataclass_fields__.keys()`, the guard raises
`AssertionError`. **Catches identity/free-text fields by name.**

#### Guard 2: `assert_pattern_field_set_canonical()` (line 167)

Checks `FeedbackPattern.__dataclass_fields__` against
`_CANONICAL_PATTERN_FIELDS` — the exact 6-field set:

```python
_CANONICAL_PATTERN_FIELDS = frozenset({
    "pattern_type", "context", "pressure_level",
    "signal", "primitive_involved", "suggested_adjustment",
})
```

If any field is added or removed (regardless of name), the guard
raises. **Catches drift by total field count.**

**The two guards implement the "necessary vs sufficient" pattern** that
[docs/azimuth.md](azimuth.md) describes for `CloudMetadata`: the
forbidden-field check is necessary (catches PII by name), the
field-set lock is sufficient (catches any new field, including ones
that don't match the blocklist). Both run at module load.

This is the **strongest privacy enforcement of any schema root in the
codebase**:

| Schema root | Forbidden-field guard | Field-set lock | Invocation |
|---|---|---|---|
| `azimuth.CloudMetadata` | Yes | Yes (test-only) | Test-only (deliberate per `docs/azimuth.md`) |
| `orchestrator_schemas` | N/A (no wire boundary) | N/A | Structural contract (C/D/G/I/S) |
| `language_schemas.EnvelopeSnapshot` | Yes (post Batch‑40) | Yes (post Batch‑40) | Module load (post Batch‑40) |
| `feedback_schemas.FeedbackPattern` | **Yes** | **Yes** | **Module load (both)** |

## Engine API (`ingestion_engine.py`)

### Module constants

#### Pressure trigger

| Constant | Value |
|---|---|
| `_HIGH_PRESSURE` | `frozenset({PressureLevel.HIGH, PressureLevel.CRITICAL})` |

Identical to the same-named constants in `primitive_selection_engine`
and `emotional_alignment_engine`. Three engines, three independent
declarations of the same set.

#### Lexical marker tuples (3)

| Tuple | Count | Examples |
|---|---|---|
| `_DRIFT_MARKERS` | 7 | `"drift", "confus", "mismatch", "misalign", "lost", "wandered", "off track"` |
| `_POSITIVE_MARKERS` | 12 | `"helpful", "good", "worked", "clear", "love", "thank", ...` |
| `_NEGATIVE_MARKERS` | 13 | `"wrong", "bad", "harsh", "frustrat", "didn't", "fail", ...` |

All substring matches, case-insensitive (text lowercased before scan).
`"confus"` matches `confusion/confused/confusing`; `"frustrat"` matches
`frustrate/frustrated/frustrating` — deliberate stem-style markers,
not exact word boundaries.

#### Mapping tables (3)

| Table | Domain → Codomain | Status |
|---|---|---|
| `_MODE_TO_PATTERN` | 5 `ConversationMode` values → `PatternType` | Complete (all 5 modes mapped) |
| `_PRIMITIVE_TO_PATTERN` | 4 `ExpressionPrimitive` values → `PatternType` | **Dead path** — every mode is mapped, so the primitive fallback never fires |
| `_ADJUSTMENT_TABLE` | 6 `PatternType` values → canonical short string | Complete (every `PatternType` mapped) |

`_PRIMITIVE_TO_PATTERN` is documented at lines 97–99 as *"currently dead
path but kept for future-proofing"* — same "reserved-but-not-branched-on"
pattern as `emotional_alignment_engine`'s `intention` parameter and
`fea_integration_engine`'s 4 reserved inputs.

### Public function

#### `extract_pattern(submission: FeedbackSubmission, ctx: Optional[ExtractionContext] = None) -> FeedbackPattern` (line 204)

Pure deterministic feedback → pattern extraction.

Reads `submission.text` ONCE (lexical scans for drift markers + signal
markers) and discards. The returned `FeedbackPattern` carries NO raw
text and NO identity — only canonical structural metadata.

**Algorithm (5 numbered steps, lines 227–253):**

1. Compute hard override (rules 1+2 via `_hard_override`).
2. Pattern type selection:
   - If override fires → use it (bypasses whiplash).
   - Else compute `candidate` via `_select_pattern_type`, then apply
     `_check_whiplash`.
3. Signal detection via `_detect_signal(submission.text)`.
4. Adjustment lookup: `_ADJUSTMENT_TABLE[pattern_type]`.
5. Emit `FeedbackPattern` with no text, no identity.

### Selection discipline — 9-rule priority order

```
1. HARD OVERRIDE — pressure ∈ {HIGH, CRITICAL}     → PRESSURE
2. HARD OVERRIDE — text contains drift markers     → DRIFT
3. mode == OPERATOR                                → ALIGNMENT
4. mode == DECISION                                → USE_CASE
5. mode == EMOTIONAL                               → TONE
6. mode == STRUCTURAL                              → ALIGNMENT
7. mode == EXPLORATORY                             → USE_CASE
8. primitive fallback (dead path; future-proof)
9. default                                         → ALIGNMENT
```

Rules 3–7 implemented as the `_MODE_TO_PATTERN` dict lookup. Rule 8 is
structurally unreachable today but the dispatch order is preserved
for v2.

### Hard overrides (`_hard_override`, line 148)

Two rules, priority order:

- **Rule 1:** `submission.pressure_level in _HIGH_PRESSURE` → `PRESSURE`.
- **Rule 2:** `_contains_drift_markers(submission.text)` → `DRIFT`.

Rule 1 wins over rule 2 by inspection order. Hard overrides bypass
whiplash prevention entirely.

### Whiplash prevention (`_check_whiplash`, line 181)

Preserves pattern continuity across consecutive submissions when
neither mode nor pressure has changed:

```
if ctx is None or ctx.last_pattern_type is None:
    return candidate                        # no continuity hint
if candidate == ctx.last_pattern_type:
    return candidate                        # already aligned
if mode_unchanged AND pressure_unchanged:
    return ctx.last_pattern_type            # stick — no real change to justify switch
return candidate                            # mode or pressure changed — accept switch
```

Hard overrides (rules 1+2) bypass this entirely — the dispatch in
`extract_pattern` (line 234–238) only calls `_check_whiplash` if
`_hard_override` returned `None`.

### Signal detection (`_detect_signal`, line 130)

Lexical sentiment classification. Negative wins on tie:

- Lowercase `submission.text`.
- If any negative marker appears → `SignalType.NEGATIVE`.
- Else if any positive marker appears → `SignalType.POSITIVE`.
- Else → `SignalType.NEUTRAL`.

Documented inline (line 140) as "Negative wins on tie (safer default)."
Same conservative-bias principle as `emotional_alignment_engine`'s
"no MEANING under HIGH/CRITICAL" and `primitive_selection_engine`'s
"STABLE tone under HIGH pressure."

### Adjustment table

`_ADJUSTMENT_TABLE` is the 6-entry canonical map from `PatternType` to
a short engine-generated adjustment string:

```
PRESSURE  → "Reduce intensity; favor STABLE tone + HIGHLY_STRUCTURED structure"
DRIFT     → "Increase clarity bridging; consider ANALOGY primitive"
TONE      → "Soften tone; check audience and pressure context"
ALIGNMENT → "Re-anchor to structural baseline; favor GEOMETRY primitive"
BOUNDARY  → "Reinforce sovereignty boundaries; defer to user authority"
USE_CASE  → "Surface as exemplar pattern; consider for documentation"
```

Documented at line 107: *"Canonical short strings — never user text.
Test-asserted: every PatternType has an entry."*

`suggested_adjustment` is the operator-facing output field. The string
IS user-visible (founder/admin console) but is engine-generated, not
user-supplied. The privacy contract permits engine-generated strings;
it forbids identity-bearing or text-bearing strings.

### Private helpers (5)

| Helper | Purpose |
|---|---|
| `_contains_drift_markers(text)` | Case-insensitive substring scan against `_DRIFT_MARKERS` (line 122) |
| `_detect_signal(text)` | POSITIVE/NEGATIVE/NEUTRAL classification; negative wins on tie (line 130) |
| `_hard_override(submission)` | Rules 1+2: returns `PRESSURE`, `DRIFT`, or `None` (line 148) |
| `_select_pattern_type(submission)` | Full priority chain without whiplash check (line 162) |
| `_check_whiplash(candidate, submission, ctx)` | Returns `ctx.last_pattern_type` when mode + pressure unchanged (line 181) |

Every helper is pure. Every helper is byte-deterministic given inputs.

## Integration points

### `feedback_schemas.py` — 1 production importer

| Importer | What it consumes |
|---|---|
| `ingestion_engine.py` | 5 types: `ExtractionContext, FeedbackPattern, FeedbackSubmission, PatternType, SignalType` |

**Lowest fan-in of any schema root.** Fan-in comparison:

| Schema root | Production importers |
|---|---|
| `azimuth.py` | 10 |
| `orchestrator_schemas.py` | 7 |
| `language_schemas.py` | 7 |
| `feedback_schemas.py` | **1** |

`feedback_schemas` serves exactly one engine. The FIS subsystem is the
cleanest-isolated component in the intelligence-layer codebase.

### `ingestion_engine.py` — zero production importers

No production module imports `extract_pattern`. The only references
are:

- `tests/test_feedback_ingestion.py` (the behavioral test suite).
- `SPEC_FEEDBACK_INGESTION.md` (the source-of-truth spec).
- `feedback_schemas.py` docstring lines 5, 69, 77, 113 (cross-references
  describing the engine as the documented consumer of feedback_schemas
  types) — **docstring-only**, not imports.

### Test suite — `tests/test_feedback_ingestion.py` (731 lines, 19 test classes)

| Category | Test classes |
|---|---|
| Type / shape | `TestEnums`, `TestFeedbackSubmission`, `TestFeedbackPattern`, `TestExtractionContext` |
| Privacy | `TestPrivacyContract`, `TestOutputDoesNotLeakUserText` |
| Mapping tables | `TestMappingTables` |
| Rule-by-rule | `TestPressureOverride`, `TestDriftOverride`, `TestModeDrivenSelection`, `TestSignalDetection` |
| Output structure | `TestSuggestedAdjustment`, `TestForwardedFields` |
| End-to-end | `TestWorkedExamples` |
| Properties | `TestDeterminism`, `TestWhiplashPrevention`, `TestSourceCodeInvariants`, `TestRulePriority` |
| Cross-cutting | `TestModuleSurface` |

The **two separate privacy test classes** (`TestPrivacyContract` line
135 + `TestOutputDoesNotLeakUserText` line 633) is unusual — most
engines have one. The duplication reflects that privacy is the single
most load-bearing invariant for this engine: feedback ingestion is
the operator-facing introspection surface, where text leakage would
be most consequential.

### External specification

`SPEC_FEEDBACK_INGESTION.md` (448 lines, repo root) is the
behavioral source-of-truth. SPEC section references in module
docstrings map to that file. The spec-to-implementation ratio is
unusual — 448 lines of spec against 180 lines of schema + 254 lines
of engine = 434 lines of code. The spec is genuinely detailed; every
rule, every marker, every adjustment string is specified externally.

## Invariants

### Schema-level (`feedback_schemas.py`)

Module-load enforced:

- **Privacy contract.** `FeedbackPattern.__dataclass_fields__` contains
  none of the 11 forbidden field names. Asserted by
  `assert_pattern_privacy_contract()` at import.
- **Field-set canonical.** `FeedbackPattern.__dataclass_fields__`
  equals the exact 6-field set. Asserted by
  `assert_pattern_field_set_canonical()` at import.

Structural (test-asserted + frozen-dataclass enforced):

- **All schemas are frozen.** Every `@dataclass` decorator carries
  `frozen=True`. Inputs are never mutated.
- **No I/O references inside any schema.** Documentation-asserted +
  source-code test.

### Engine-level (`ingestion_engine.py`)

Module-locked + test-enforced:

- **Pure function.** `extract_pattern` has no I/O, no randomness, no
  LLM calls.
- **Determinism.** Same `FeedbackSubmission` → byte-identical
  `FeedbackPattern`.
- **Output carries no raw text.** Test-enforced via
  `TestOutputDoesNotLeakUserText`. The engine reads `submission.text`
  once for lexical scans and discards.
- **Output carries no identity.** Structurally enforced via the
  `FeedbackPattern` schema (no identity fields exist on the output
  type).
- **Hard overrides always bypass whiplash.** Structural — rules 1+2
  return before `_check_whiplash` is called.
- **Negative wins on tie** in signal detection. Documented as "safer
  default" + test-pinned.
- **`suggested_adjustment` is canonical** — never user text. Every
  string comes from `_ADJUSTMENT_TABLE`; test-asserted that every
  `PatternType` has a non-empty entry.
- **Rule priority preserved.** `TestRulePriority` pins the 9-rule
  order; reordering breaks tests.

## Non-goals

`feedback_layer` is **not**:

- a kernel reasoning mode — neither file imports `intelligence_kernel`;
- a model invocation surface — no `model_router` import, no provider
  SDKs;
- a vault consumer — no `memory_vault` import;
- an `operator_state` writer or reader — no `operator_state` import;
- an HTTP service — no routes in `app.py`;
- a state store — fully stateless; nothing is persisted by the FIS;
- a text generator — the engine emits canonical short adjustment
  strings from a locked table, never user-derived prose;
- a feedback router — `extract_pattern` returns a `FeedbackPattern`;
  the surface decides what to do with it (display in founder console,
  surface for documentation, etc.);
- a learning / training / personalisation surface — the rule set is
  locked in code and in `SPEC_FEEDBACK_INGESTION.md`; the engine
  never observes outcomes;
- an ML model — pure deterministic Python, rule-based, no weights;
- a multi-turn aggregator — every call evaluates a single
  `FeedbackSubmission`. The `ExtractionContext.last_pattern_type` field
  carries continuity but the engine remains single-submission;
- a privacy escape hatch — `FeedbackPattern` is the only Feedback
  Layer output, and its field set is structurally locked + privacy-
  guarded at module load;
- a stateful classifier — the engine has no memory beyond the
  optional `ExtractionContext` hint; nothing is retained between
  calls.

## Fiction removed

The following constructs are explicitly not present in
`feedback_schemas.py` or `ingestion_engine.py` and must not be
inferred:

- **No active production wiring for `ingestion_engine`.**
  `extract_pattern` is fully implemented + tested but no production
  module currently invokes it. This is a runtime status, not a
  code-quality status — same vNEXT framing as
  `primitive_selection_engine` and `azimuth_transition`. The
  expected eventual consumer is the founder feedback console /
  introspection surface; no such consumer exists today.
- **No `__post_init__` validation on any dataclass.** Wrong enum
  types, semantically inconsistent field combinations all construct
  silently. The privacy and field-set guards check structural shape,
  not field values.
- **No engine imports for `ingestion_engine`.** The engine consumes
  only schema types from 3 schema roots (`feedback_schemas`, `azimuth`,
  `language_schemas`). No cross-engine call, no `model_router`, no
  `intelligence_kernel`.
- **No mutation of `FeedbackSubmission`, `FeedbackPattern`, or
  `ExtractionContext`.** All three are frozen; the engine constructs
  a new `FeedbackPattern` per call.
- **No file I/O at runtime.** No log loading, no rule loading from
  files — every constant is defined inline in the source.
- **No randomness.** No `secrets.token_urlsafe` call anywhere in the
  module. The FIS does not generate identifiers; submissions are
  content-identified by their fields, not by an ID.
- **No timestamp generation.** `FeedbackSubmission.timestamp` is
  caller-supplied. The engine does not call `datetime.now()` or
  `datetime.utcnow()`.
- **No `BOUNDARY` rule.** `PatternType.BOUNDARY` exists in the enum
  and has an `_ADJUSTMENT_TABLE` entry, but no rule in `extract_pattern`
  emits it. The pattern is documented in the spec but unreachable in
  the current implementation. Either a future rule will emit it, or
  it remains defensively-coded dead capacity.
- **No primitive-driven dispatch in production.**
  `_PRIMITIVE_TO_PATTERN` (rule 8) is structurally unreachable —
  every `ConversationMode` is mapped in `_MODE_TO_PATTERN`, so the
  primitive fallback never fires. Documented as "currently dead path
  but kept for future-proofing."
- **No multiple algorithms.** The engine runs ONE priority chain.
  There is no "model selection" or "strategy" parameter.
- **No autonomous feedback loop.** `extract_pattern` is invoked per
  submission by the caller. The engine has no scheduler, no
  background work, no auto-aggregation.
- **No identity field on any output type.** `FeedbackPattern` has
  exactly 6 fields, none of which is an identifier. The 11-entry
  `_FORBIDDEN_PATTERN_FIELDS` blocklist + 6-entry
  `_CANONICAL_PATTERN_FIELDS` lock together guarantee that no
  identity field can be added without failing import.
- **No coupling to `primitive_selection_engine` or
  `emotional_alignment_engine`.** All three engines share types from
  `azimuth` and `language_schemas` but do not import each other. The
  FIS sits parallel to the language layer and the ERA pipeline, not
  downstream of either.

Only the behaviour, fields, integrations, and invariants described
in this document are present in the code; the verified surface is
locked by the tests in `tests/test_feedback_ingestion.py` (731 lines,
19 test classes including `TestPrivacyContract`,
`TestOutputDoesNotLeakUserText`, `TestMappingTables`,
`TestRulePriority`, `TestSourceCodeInvariants`, `TestDeterminism`,
and `TestWhiplashPrevention`).
