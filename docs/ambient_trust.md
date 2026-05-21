# Ambient Trust

## Purpose

`ambient_trust` is the deterministic Ambient Trust engine. Given a
`SessionContext` (caller-supplied snapshot of ability,
comprehension, concept exposures, hard-stop count, and last-action
ack), it produces:

- a **trust score** in `[0.0, 1.0]`,
- point-in-time `UnderstandingCheck` and `MomentumCheck` verdicts,
- a non-halting `RepairDirective` when repair is needed.

It models whether the system is moving at a safe pace, with
sufficient comprehension, and without repeated hard stops. The
canonical framing is **structural, not motivational**: the user's
sense of being met is treated as a function of (a) comprehension
keeping up with ability, and (b) momentum surviving the system's
actions. The system never converts a trust gap into a hard stop.

It is implemented in `ambient_trust_engine.py` (280 lines) and
`ambient_trust_schemas.py` (315 lines), anchored to the external
spec `SPEC_AMBIENT_TRUST.md`. The engine is pure Python — no I/O,
no LLM, no network, no randomness, no state — and is structurally
prevented from carrying raw user text, identity, or session
information through any of its output types. Ambient Trust is
**advisory only**: it returns data; never sends, applies, halts,
or mutates upstream state.

### Core invariant

> **Trust is structural, not motivational.**
> The system never converts a trust gap into a hard stop.

## Implementation location

- **Engine:** `ambient_trust_engine.py` (280 lines).
- **Schemas:** `ambient_trust_schemas.py` (315 lines).
- **External spec:** `SPEC_AMBIENT_TRUST.md` — the source-of-truth
  behavioral spec, kept at the repo root.
- **Imports** (eager only, no lazy):
  - Engine: schemas + `from ambient_trust_schemas import ...`
    (constants, enum, dataclasses) — one internal cross-import.
  - Schemas: stdlib `dataclasses` (`dataclass`, `field`) + `enum`
    (`Enum`). **No upstream subsystem dependencies.**
- **Position in dependency graph:** deepest leaf of the
  intelligence layer. Nothing in the intelligence layer is upstream
  of ambient_trust; it depends only on stdlib.
- **Canonical doc:** this file.

## Data model

### Upstream types
None. Ambient Trust is a leaf — all types are owned by this
subsystem.

### Enum (1)

```python
class RepairKind(str, Enum):
    NONE         = "none"           # no repair required
    RE_ANCHOR    = "re_anchor"      # re-state the working context (after a hard stop)
    SLOW_PACE    = "slow_pace"      # pace is too fast for current comprehension
    OFFER_CHOICE = "offer_choice"   # agency lost; restore choice
    NARROW_SCOPE = "narrow_scope"   # zoom into a smaller piece
```

**Invariant 10 (from schemas):** there is intentionally NO halting
or blocking member. `gentle_repair` never emits a halt-like
directive.

### Input dataclass (1, frozen)

```python
@dataclass(frozen=True)
class SessionContext:
    ability_level:            int
    comprehension_level:      int
    concept_exposures:        tuple    # tuple[ConceptExposure, ...]
    hard_stop_count:          int  = 0
    last_action_acknowledged: bool = True
```

The canonical "interaction context" type that downstream
integration layers (FEA Integration, surface pacing, Orchestrator
post-step hooks) consume. Keep it minimal and structural — adding
fields is a deliberate spec change.

**Level range:** `ability_level` and `comprehension_level` are
**expected** to be in `[0, MAX_LEVEL]`. This is a **caller-side
contract** — the engine does NOT enforce it (see §Invariants:
caller obligations).

### Output dataclasses (4, all frozen)

```python
@dataclass(frozen=True)
class ConceptExposure:
    concept_id: str                       # must be in CANONICAL_CONCEPT_IDS
    count:      int                       # never branched on in v1

@dataclass(frozen=True)
class TrustState:
    understanding_gap: int                # max(0, ability_level - comprehension_level)
    momentum_intact:   bool               # True iff hard_stop_count == 0
    trust_score:       float              # ∈ [0.0, 1.0], rounded to 4 decimals
    repair_needed:     bool

@dataclass(frozen=True)
class UnderstandingCheck:
    ability_level:       int
    comprehension_level: int
    gap:                 int
    passes_invariant:    bool             # True iff gap <= GAP_TOLERANCE

@dataclass(frozen=True)
class MomentumCheck:
    hard_stop_count:          int
    last_action_acknowledged: bool        # passed through, NOT branched on
    hard_stop_detected:       bool        # True iff hard_stop_count > 0
    passes_invariant:         bool        # True iff hard_stop_count == 0

@dataclass(frozen=True)
class RepairDirective:
    kind:      RepairKind
    rationale: str                        # canonical string from _RATIONALE; never user text
```

### Canonical concept-id tuple

```python
CANONICAL_CONCEPT_IDS: tuple = (
    "envelope", "pressure", "geometry", "intention", "expression",
    "alignment", "halt_state", "trust", "momentum", "agency",
)
```

10 canonical concept ids. **Wire-format contract: tuple order AND
content are canonical.** `assert_canonical_concept_ids` checks
both, not just set membership (stricter than ERA's or FEA's peer
asserts).

### Public scoring constants (6)

- `MAX_LEVEL = 3` — expected upper bound for level fields.
  **Caller-side contract; not engine-enforced.**
- `GAP_TOLERANCE = 1` — max gap between ability and comprehension
  before understanding invariant fails.
- `SCORE_PENALTY_PER_GAP_LEVEL = 0.2`
- `SCORE_PENALTY_PER_HARD_STOP = 0.1`
- `SCORE_PENALTY_UNACKNOWLEDGED = 0.2`
- `HARD_STOP_PENALTY_CAP_LEVELS = 2` — hard-stop count capped at
  this value for scoring purposes; the 3rd+ hard stop adds no
  additional penalty.

### Privacy contract (structurally enforced)

None of the six Ambient Trust dataclasses may contain `text`,
`raw`, `raw_text`, `user`, `user_id`, `id`, `name`, `names`,
`email`, `session`, `session_id`, `identity`, `envelope_id`,
`author`, `actor`, `content`, `body`, or `message` fields. The
forbidden set is `_FORBIDDEN_FIELDS` (18 entries, identical to FEA
Integration's set) and is enforced by
`assert_ambient_trust_privacy_contract()` at module load.

### Module-load runtime guards (4)

All four live in `ambient_trust_schemas.py` and run at import
(lines 312-315):

- `assert_ambient_trust_privacy_contract()` — fails if any of the
  6 dataclasses gained a forbidden field.
- `assert_ambient_trust_field_sets_canonical()` — fails if any
  dataclass's field set drifted from `_CANONICAL_FIELDS`.
- `assert_repair_kinds_canonical()` — fails if `RepairKind` gained
  or lost members.
- `assert_canonical_concept_ids()` — fails if the
  `CANONICAL_CONCEPT_IDS` tuple drifted in **order or content**.

Broken edits fail import — same architectural pattern as ERA and
FEA Integration.

### `_CANONICAL_CONCEPT_ID_SET` is defined in both files
The frozenset `frozenset(CANONICAL_CONCEPT_IDS)` is computed
independently at `schemas.py:244` (for the runtime guard) and at
`engine.py:68` (for fast membership tests during validation). Both
derive from the same source-of-truth tuple — benign duplication, not
a name collision.

## APIs / entrypoints

### Public functions (4)

**`assess_trust_state(ctx: SessionContext) -> TrustState`** (engine.py:153)

The primary entry point. Computes the full trust posture for a
session context.

Behavior:

1. Validates all `ConceptExposure.concept_id` values against
   `CANONICAL_CONCEPT_IDS` (raises `ValueError` on any non-canonical id).
2. Computes `gap = max(0, ability_level - comprehension_level)`.
3. Computes `momentum_intact = (hard_stop_count == 0)`.
4. Computes `trust_score` via the scoring formula (see Invariants
   §Scoring policy).
5. Computes `repair_needed` (True iff any trigger fires).
6. Returns a fresh `TrustState`.

**Gating invariant:** `assess_trust_state` is the **only** public
function that validates concept IDs. Callers that bypass it must
guarantee canonical concept IDs themselves.

**`verify_no_hard_stops(ctx: SessionContext) -> MomentumCheck`** (engine.py:194)

Pure function. Returns a `MomentumCheck` with:

- `hard_stop_count` and `last_action_acknowledged` (passthrough)
- `hard_stop_detected = (ctx.hard_stop_count > 0)`
- `passes_invariant = (ctx.hard_stop_count == 0)`

`last_action_acknowledged` is included in the output but **not
branched on**. The `passes_invariant` decision depends purely on
hard stops.

**`verify_comprehension_leads_action(ctx: SessionContext) -> UnderstandingCheck`** (engine.py:215)

Pure function. Returns an `UnderstandingCheck` with:

- `ability_level`, `comprehension_level` (passthrough)
- `gap = max(0, ability_level - comprehension_level)`
- `passes_invariant = (gap <= GAP_TOLERANCE)`

With `GAP_TOLERANCE = 1`, ability may run at most one rank ahead
of comprehension before the invariant fails.

**`gentle_repair(trust: TrustState, ctx: SessionContext) -> RepairDirective`** (engine.py:239)

Pure function. Selects a single non-halting `RepairDirective`.

Short-circuit: if `not trust.repair_needed` → returns
`RepairDirective(kind=NONE, rationale=_RATIONALE[NONE])`.

Otherwise, priority cascade (first match wins):

| # | Condition | `kind` |
|---|---|---|
| 1 | `ctx.hard_stop_count > 0` | `RE_ANCHOR` |
| 2 | `trust.understanding_gap > GAP_TOLERANCE` | `SLOW_PACE` |
| 3 | `not ctx.last_action_acknowledged` | `OFFER_CHOICE` |
| 4 | `trust.understanding_gap == GAP_TOLERANCE` | `NARROW_SCOPE` |
| 5 | defensive fallthrough | `NONE` |

The defensive fallthrough is **explicitly documented as unreachable**
under the SPEC § 6.2 contract; the test suite asserts unreachability.

**Call-pattern invariant:** `gentle_repair` reads from **both**
`trust` (for the short-circuit and `understanding_gap`) and `ctx`
(for `hard_stop_count` and `last_action_acknowledged`). Callers
must pass the **same `SessionContext` that produced `trust` via
`assess_trust_state`**. Inconsistent `(trust, ctx)` pairs can
produce surprising repairs.

### Helper

**`is_canonical_concept_id(concept_id: str) -> bool`** (schemas.py:302)

External-caller helper. Returns True iff `concept_id ∈
CANONICAL_CONCEPT_IDS`. The engine itself does NOT call this helper
— `_validate_concept_exposures` uses the inline check against
`_CANONICAL_CONCEPT_ID_SET`. The helper exists for external code
constructing `ConceptExposure` tuples.

### HTTP entrypoints

**None.** Ambient Trust is library-internal. The user-facing
surface is whatever `azimuth_transition` exposes downstream.

## Integration points

### Upstream
None. Ambient Trust has no upstream subsystem dependencies.

### Downstream consumers (2)

- **`fea_integration_engine.py`** (line 50) — imports
  `MomentumCheck`, `SessionContext`, `TrustState`,
  `UnderstandingCheck` from schemas. In FEA v1:
  - `MomentumCheck.passes_invariant` and
    `UnderstandingCheck.passes_invariant` are **actively consumed**
    (drive `PACE/slow` and `CHECKPOINT/offer_choice` directives).
  - `SessionContext` and `TrustState` are **reserved inputs in v1,
    NOT branched on**. See [docs/fea_integration.md](fea_integration.md).
- **`azimuth_transition.py`** (lines 69-74) — imports engine
  functions and `SessionContext` from schemas. Documented in
  Batch-20 (`docs/azimuth_transition.md`).

### External specification

`SPEC_AMBIENT_TRUST.md` (root of the repo) is the behavioral
source-of-truth. SPEC § 5 is the scoring formula, § 6.2 is the
repair-trigger contract, and § 7 is the repair priority cascade.

### Tests

- **`tests/test_ambient_trust.py`** — primary; imports both engine
  and schemas as `engine` / `schemas`. Pins the scoring formula,
  understanding/momentum checks, repair cascade, privacy contract,
  canonical-set guards, and module-load guard behavior.
- **`tests/test_fea_integration.py`** — coupled; imports both as
  `trust_engine` / `trust_schemas` for FEA integration fixtures.
- **`tests/test_azimuth_fea_integration.py`** — coupled; exercises
  ambient_trust in the full azimuth → FEA path.

## Invariants

### Purity and determinism

- **Pure functions.** All 4 public engine functions are
  deterministic and side-effect free. Same inputs → byte-equal
  outputs. No I/O, no randomness, no LLM, no network.
- **Inputs never mutated.** All input dataclasses are frozen;
  the engine additionally treats them as read-only.
- **Fresh outputs.** Every call returns a new dataclass instance.
  No object-identity passthrough pattern (unlike FEA Integration's
  `aligned_expression`).

### Scoring policy (`_compute_trust_score`)

Pure function. Signature: `(gap, hard_stop_count, last_action_acknowledged) -> float`.

```
score = 1.0
score -= SCORE_PENALTY_PER_GAP_LEVEL (0.2) * gap
if not last_action_acknowledged:
    score -= SCORE_PENALTY_UNACKNOWLEDGED (0.2)
capped_stops = min(hard_stop_count, HARD_STOP_PENALTY_CAP_LEVELS (2))
score -= SCORE_PENALTY_PER_HARD_STOP (0.1) * capped_stops
clamp to [0.0, 1.0]
return round(score, 4)
```

Properties:

- **Additive penalties.** Gap, unacknowledged, and hard-stop
  contributions independently subtract from the 1.0 baseline.
- **Hard-stop cap.** Only the first 2 hard stops affect score.
  Additional hard stops contribute zero penalty.
- **Monotonicity.** More gap → lower score; unacknowledged → lower;
  more hard stops (up to 2) → lower.
- **Determinism.** Rounded to 4 decimal places for byte-stable
  output.
- **Bounded.** Always in `[0.0, 1.0]`; explicit clamp before round.

### Understanding invariants

- `gap = max(0, ability_level - comprehension_level)`
- `UnderstandingCheck.passes_invariant = (gap <= GAP_TOLERANCE)`
- With `GAP_TOLERANCE = 1`, ability may be at most one rank ahead
  of comprehension before the invariant fails.
- Used by FEA Integration to drive the `PACE/slow` directive.

### Momentum invariants

- `momentum_intact = (hard_stop_count == 0)`
- `MomentumCheck.passes_invariant = (hard_stop_count == 0)`
- `MomentumCheck.hard_stop_detected = (hard_stop_count > 0)`
- `passes_invariant` and `hard_stop_detected` are logical
  opposites by construction.
- `MomentumCheck.last_action_acknowledged` is passthrough metadata
  — the field is included in the output but does NOT affect
  `passes_invariant`.
- Used by FEA Integration to drive the `CHECKPOINT/offer_choice`
  directive.

### Repair invariants

- `TrustState.repair_needed = _repair_needed(gap, hard_stop_count, last_action_acknowledged)`
- `_repair_needed` returns True iff any of:
  - `hard_stop_count > 0`
  - `not last_action_acknowledged`
  - `gap >= GAP_TOLERANCE`
- `gentle_repair` ALWAYS returns one of the 5 `RepairKind` values,
  never a halting/blocking directive (invariant 10).
- `RepairDirective.rationale` is ALWAYS a canonical string from
  `_RATIONALE` (engine.py:53-64). Never user text.
- The defensive fallthrough at engine.py:273-278 is documented as
  unreachable under SPEC § 6.2; tests assert this.
- `gentle_repair` is deterministic given `(trust, ctx)`.

### Concept-validation gating

- `_validate_concept_exposures` is called ONLY at the top of
  `assess_trust_state` (engine.py:168).
- `verify_no_hard_stops`, `verify_comprehension_leads_action`, and
  `gentle_repair` do NOT independently validate concept IDs.
- If a caller invokes these three functions directly with a
  `SessionContext` containing non-canonical concept IDs, the
  invalid IDs flow through silently. Callers must either route
  through `assess_trust_state` first OR construct `ConceptExposure`
  tuples using only canonical IDs (the `is_canonical_concept_id`
  helper exists for this).

### Schema and privacy invariants

- **Privacy.** 18 forbidden field names; enforced at module load
  across all 6 dataclasses by `assert_ambient_trust_privacy_contract`.
- **Field-set lock.** Each dataclass's field set is fixed and
  enforced at module load by `assert_ambient_trust_field_sets_canonical`.
- **Repair-kind lock.** `RepairKind` member set is locked and
  enforced at module load by `assert_repair_kinds_canonical`.
- **Concept-id tuple lock.** `CANONICAL_CONCEPT_IDS` order AND
  content are locked (stricter than peer assertions in ERA/FEA)
  and enforced at module load by `assert_canonical_concept_ids`.

### Caller-side obligations

These are NOT engine-enforced but are documented contracts:

- **Level range.** Maintain `ability_level` and
  `comprehension_level` in `[0, MAX_LEVEL]` (= `[0, 3]`). The
  engine does not validate this; values outside the range will
  produce arithmetically valid but semantically meaningless scores.
- **Canonical concept IDs.** Use only members of
  `CANONICAL_CONCEPT_IDS` when constructing `ConceptExposure`. Only
  `assess_trust_state` validates; other functions trust the caller.
- **Consistent (trust, ctx) pairs.** Always call `gentle_repair`
  with the same `SessionContext` that produced the `TrustState` via
  `assess_trust_state`. Mismatched pairs are a foot-gun.

## Non-goals

`ambient_trust` is **not**:

- a model invocation surface — no `model_router` import, no
  provider SDKs, no LLM call anywhere in the subsystem;
- a state store — fully stateless; nothing is persisted by
  Ambient Trust;
- a vault consumer — does not import `memory_vault`;
- an operator_state writer or reader — no `operator_state` import;
- a kernel reasoning mode — no `intelligence_kernel` import;
- an HTTP service — no `/me/ambient/*` or similar endpoint; the
  layer is library-internal, invoked only by `fea_integration` and
  `azimuth_transition`;
- a halting surface — `RepairKind` intentionally has no halting
  member; the integration layer (FEA Integration) and the surface
  decide whether to act on advisory signals;
- an autonomous repair system — every call is request-driven; no
  scheduler, no background work, no auto-apply;
- a learning surface — Ambient Trust never observes outcomes; the
  scoring policy and repair cascade are locked in code and the
  SPEC;
- a multi-turn or multi-session aggregator — every call is
  point-in-time, evaluated against a single `SessionContext`;
- a privacy escape hatch — the schemas structurally exclude
  identity and raw-text fields, and the guards fail import on
  drift.

## Fiction removed

The following constructs are explicitly not present in
`ambient_trust_engine.py` or `ambient_trust_schemas.py` and must
not be inferred:

- **No engine-side enforcement of `MAX_LEVEL`.** The constant is
  declared in schemas (line 44) but never imported by the engine.
  Levels outside `[0, MAX_LEVEL]` are accepted silently and produce
  arithmetically valid but semantically undefined results. This is
  a caller-side contract.
- **No concept-ID validation outside `assess_trust_state`.** The
  three other public engine functions (`verify_no_hard_stops`,
  `verify_comprehension_leads_action`, `gentle_repair`) do NOT
  re-validate. Non-canonical concept IDs flow through silently if
  the caller bypasses `assess_trust_state`.
- **No halting `RepairKind` member.** All 5 repair kinds are
  non-blocking (invariant 10). The integration layer never receives
  a "stop" or "halt" directive from `gentle_repair`.
- **No mutation of `SessionContext` or `TrustState`.** Both are
  frozen dataclasses; the engine never reconstructs or modifies
  them.
- **No identity passthrough.** Unlike FEA Integration's
  `aligned_expression`, ambient_trust outputs are fresh dataclass
  instances every call. `TrustState`, `UnderstandingCheck`,
  `MomentumCheck`, and `RepairDirective` are all newly constructed.
- **No model invocation, no vault access, no kernel coupling, no
  HTTP route, no file I/O, no network, no logging.**
- **No autonomous repair.** Callers must explicitly invoke
  `gentle_repair`; the engine never proactively emits a repair
  directive.
- **No state caching.** Every `assess_trust_state` call recomputes
  from scratch.
- **No multi-pass or iterative scoring.** Single deterministic
  evaluation per call.
- **No async, no scheduler, no background work.** Pure synchronous
  function calls.
- **No multi-session correlation.** Every call evaluates a single
  `SessionContext`; the engine has no notion of session history
  beyond what the caller encodes in `hard_stop_count` and
  `concept_exposures.count`.

Only the behaviour, fields, integrations, and invariants described
in this document are present in the code; the verified surface is
locked by the tests in `tests/test_ambient_trust.py` and the four
module-load assertion functions.
