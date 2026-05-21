# FEA Integration Layer — Specification

**Status:** Phase 1. Schemas + engine implementation locked. Tests pin
the deterministic behavior contract. This unit is **integration only**
— no new emotional physics, no new trust math, just structural wiring
from FEA + Ambient Trust + Azimuth + Orchestrator state into a single
advisory result the surface and orchestrator can read.

**Date:** 2026-05-11
**Core invariant:** *FEA safety flags are authoritative. Ambient Trust is
advisory. The integration layer never converts trust signals into safety
overrides, never auto-sends, and never mutates upstream state.*

---

## 1. Purpose

The FEA Integration Layer takes:

* an `AlignedExpression` from FEA (`emotional_alignment_engine.align_expression`)
* a pre-computed `SessionContext`, `TrustState`, `MomentumCheck`,
  `UnderstandingCheck` from Ambient Trust
* an `EnvelopeState` from Azimuth
* a `PropagationState` from Orchestrator

…and produces a single `IntegratedAlignmentResult` that encodes:

1. The original `AlignedExpression`, unmodified.
2. A `SurfaceHaltLevel` for the surface (`NONE` / `SOFT` / `HARD`).
3. A `trust_state_delta` — the recommended additive change to
   `TrustState.trust_score`, clamped to `[0.0, 1.0]`.
4. A `momentum_preserved` boolean — a passthrough of
   `MomentumCheck.passes_invariant`.
5. A tuple of `SurfaceDirective`s — structural pacing / disclosure /
   checkpoint / preview hints.

The result is advisory only. The final expression still passes through
the Sovereignty Gate (downstream of integration).

---

## 2. Inputs

```python
AlignedExpression    ← emotional_alignment_schemas
SessionContext       ← ambient_trust_schemas
TrustState           ← ambient_trust_schemas
MomentumCheck        ← ambient_trust_schemas
UnderstandingCheck   ← ambient_trust_schemas
EnvelopeState        ← azimuth
PropagationState     ← orchestrator_schemas
```

`session`, `trust`, `envelope`, and `propagation` are accepted in the
signature for forward compatibility but are **not branched on in v1**.
Only `aligned`, `momentum`, and `understanding` drive the v1 rules.
Source-code tests assert v1 does not read fields off the four reserved
inputs.

---

## 3. Outputs

```python
class SurfaceHaltLevel(str, Enum):
    NONE = "no_halt"
    SOFT = "soft_halt"
    HARD = "hard_halt"

class SurfaceDirectiveType(str, Enum):
    PACE       = "pace"
    DISCLOSURE = "disclosure"
    CHECKPOINT = "checkpoint"
    PREVIEW    = "preview"

@dataclass(frozen=True)
class SurfaceDirective:
    directive_type: SurfaceDirectiveType
    value:          str   # ∈ CANONICAL_DIRECTIVE_VALUES[directive_type]

@dataclass(frozen=True)
class IntegratedAlignmentResult:
    aligned_expression: AlignedExpression   # passthrough
    halt_level:         SurfaceHaltLevel
    trust_state_delta:  float               # ∈ [0.0, 1.0]
    momentum_preserved: bool
    surface_directives: tuple               # tuple[SurfaceDirective, ...]
```

### 3.1 Canonical directive values (locked)

`SurfaceDirective.value` must be a member of the canonical set for its
directive type. Adding a value is a deliberate spec change.

```python
CANONICAL_DIRECTIVE_VALUES = {
    SurfaceDirectiveType.PACE:       frozenset({"slow", "normal"}),
    SurfaceDirectiveType.DISCLOSURE: frozenset({"single_concept",
                                                "full_model_available"}),
    SurfaceDirectiveType.CHECKPOINT: frozenset({"offer_choice"}),
    SurfaceDirectiveType.PREVIEW:    frozenset({"preview_only"}),
}
```

---

## 4. Privacy Model

```
                  ╔════════════════════════════════════╗
                  ║  Surface + Orchestrator             ║
                  ║  (consume IntegratedAlignmentResult) ║
                  ╚═══════════════╤════════════════════╝
                                  │  halt + delta + directives
                                  │  (NO text, NO identity)
                                  ▼
                  ┌─────────────────────────────────────┐
                  │  FEA INTEGRATION ENGINE             │
                  │  integrate_alignment(...)           │
                  │  → pure · deterministic             │
                  └───────────────┬─────────────────────┘
                                  │  AlignedExpression +
                                  │  (Ambient Trust + Azimuth +
                                  │   Orchestrator state)
                                  ▼
                  ┌─────────────────────────────────────┐
                  │  Caller (Azimuth Transition,        │
                  │   Orchestrator workflow, etc.)      │
                  └─────────────────────────────────────┘
```

**Boundary rules:**

1. Integration outputs (`SurfaceDirective`, `IntegratedAlignmentResult`)
   are **structurally guaranteed** (test-enforced) to omit forbidden
   identity / text fields.
2. The engine is pure: no I/O, no LLM, no network, no randomness.
3. The engine **does not modify any input** — `aligned_expression` is
   the same object as the input `aligned`.
4. `SurfaceDirective.value` is a canonical string drawn from the locked
   `CANONICAL_DIRECTIVE_VALUES` table — never user text.

---

## 5. Halt-Level Rules (deterministic, exclusive)

```text
if  aligned.safe_for_surface == False  →  HARD
elif aligned.alignment_score < 0.4     →  SOFT
else                                    →  NONE
```

**FEA wins.** Ambient Trust signals never escalate or override these
halt-level rules. Trust gaps surface elsewhere (via directives and the
trust delta), never as halts.

---

## 6. Surface Directive Generation (deterministic, additive)

A directive is added when its trigger fires. Directives are deduplicated
by `(directive_type, value)` pair and emitted in canonical priority
order:

| Order | Trigger | Directive |
|---:|---|---|
| 1 | `aligned.plan.expected_pressure_delta > 0`  OR  `not understanding.passes_invariant` | `(PACE, "slow")` |
| 2 | `aligned.plan.expected_agency_delta > 0`    OR  `not momentum.passes_invariant`     | `(CHECKPOINT, "offer_choice")` |
| 3 | `TEMPORAL ∈ aligned.plan.steps` | `(DISCLOSURE, "single_concept")` |
| 4 | `MEANING  ∈ aligned.plan.steps` | `(DISCLOSURE, "full_model_available")` |
| 5 | `halt_level == HARD` | `(PREVIEW, "preview_only")` |

The combined FEA-internal / Ambient-Trust-external triggers in rows 1 + 2
guarantee that whether pacing or checkpoint is needed because of FEA's
plan or because of Ambient Trust's understanding/momentum, the same
canonical directive is emitted (and dedup'd to one instance).

---

## 7. Trust-State Delta (deterministic)

```text
delta = 0.0  (baseline)

  + 0.1   if momentum.passes_invariant == True
  − 0.1   if halt_level != NONE

clip to [0.0, 1.0]
```

The delta is the recommended *additive* change to
`TrustState.trust_score`. Per invariant 3, the delta is clamped to
`[0.0, 1.0]`: this layer can only *suggest building trust*, never burn
it down via the integration channel. Trust decreases happen through
Ambient Trust's own mechanisms (hard-stop counter, unacknowledged
flag, etc.) — not through this integration delta.

Effective values:

| momentum_preserved | halt_level | delta |
|:--:|:--:|:--:|
| True  | NONE | 0.1 |
| True  | SOFT | 0.0 |
| True  | HARD | 0.0 |
| False | NONE | 0.0 |
| False | SOFT | 0.0 |
| False | HARD | 0.0 |

---

## 8. Invariants (locked, test-enforced)

| # | Invariant | Enforcement |
|---:|---|---|
| 1 | FEA safety flag is authoritative: `safe_for_surface == False` ⇒ `halt_level == HARD`. | Engine rule §5; test-asserted. |
| 2 | Low alignment escalates to at least SOFT: `alignment_score < 0.4` ⇒ `halt_level ∈ {SOFT, HARD}`. | Engine rule §5; test-asserted. |
| 3 | `trust_state_delta ∈ [0.0, 1.0]`. | Clamp in §7; test-asserted across parameterised inputs. |
| 4 | `aligned_expression` is passed through unmodified (object identity). | Engine never mutates inputs; test-asserted. |
| 5 | No raw user text in any integration output. | Structural — forbidden fields not in any `__dataclass_fields__`. Test-asserted. |
| 6 | No identity fields in any integration output. | Structural; test-asserted. |
| 7 | Ambient Trust never overrides FEA safety: there is no rule path where Ambient Trust converts a `NONE`/`SOFT` halt into a less-severe state. | Engine rule §5 reads only FEA fields; source-code asserted. |
| 8 | Integration is advisory only — no auto-send patterns, no halt enforcement. | Module returns data; source-inspection asserted. |
| 9 | `SurfaceDirective.value` is a member of `CANONICAL_DIRECTIVE_VALUES`. | Runtime guard at module load + validation at engine boundary. |
| 10 | Deterministic. Same inputs → byte-equal outputs. | Behavioral tests assert byte-equal returns. |
| 11 | No I/O, no LLM, no network, no randomness. | Source-code inspection in tests. |
| 12 | `session`, `trust`, `envelope`, `propagation` are read-only in v1 (reserved for future versions). | Source-code asserted; no field-access of those four inputs. |

---

## 9. Worked Examples

### 9.1 High-pressure collapse (HIGH pressure + curvature + SUBMIT)

```
aligned.safe_for_surface         = True
aligned.alignment_score          = 0.9
aligned.plan.steps               = [SCALE, AGENCY]
aligned.plan.expected_pressure_delta = -1
aligned.plan.expected_agency_delta   = +1
momentum.passes_invariant        = True
understanding.passes_invariant   = True
```

`halt_level` = `NONE` (score >= 0.4, safe).
`trust_state_delta` = `0.1` (momentum preserved + no halt).
`momentum_preserved` = `True`.
Directives: `[(CHECKPOINT, "offer_choice")]` (agency_delta > 0).

### 9.2 Authority shame (MEDIUM, full FEA plan)

```
aligned.safe_for_surface         = True
aligned.alignment_score          = 0.9
aligned.plan.steps               = [TEMPORAL, LABEL, ROLE, AGENCY, MEANING]
aligned.plan.expected_pressure_delta = -1
aligned.plan.expected_agency_delta   = +1
momentum.passes_invariant        = True
understanding.passes_invariant   = True
```

`halt_level` = `NONE`.
`trust_state_delta` = `0.1`.
Directives:
`[(CHECKPOINT, "offer_choice"), (DISCLOSURE, "single_concept"),
  (DISCLOSURE, "full_model_available")]`.

### 9.3 Low-pressure reflection (LOW, MEANING only)

```
aligned.safe_for_surface         = True
aligned.alignment_score          = 0.5
aligned.plan.steps               = [MEANING]
aligned.plan.expected_pressure_delta = 0
aligned.plan.expected_agency_delta   = 0
momentum.passes_invariant        = True
understanding.passes_invariant   = True
```

`halt_level` = `NONE` (score = 0.5).
`trust_state_delta` = `0.1`.
Directives: `[(DISCLOSURE, "full_model_available")]`.

### 9.4 No-reframe needed (LOW, NONE plan)

```
aligned.safe_for_surface         = True
aligned.alignment_score          = 0.5
aligned.plan.steps               = [NONE]
aligned.plan.expected_pressure_delta = 0
aligned.plan.expected_agency_delta   = 0
momentum.passes_invariant        = True
understanding.passes_invariant   = True
```

`halt_level` = `NONE`. `trust_state_delta` = `0.1`. Directives: `[]`.

### 9.5 Unsafe plan (FEA hard-stop)

```
aligned.safe_for_surface         = False
aligned.alignment_score          = 0.7
aligned.plan.steps               = [MEANING]    (manually injected under HIGH)
aligned.plan.expected_pressure_delta = +1
aligned.plan.expected_agency_delta   = 0
momentum.passes_invariant        = True
understanding.passes_invariant   = True
```

`halt_level` = `HARD` (FEA safety flag is authoritative — score is
ignored because safe_for_surface=False fires first).
`trust_state_delta` = `0.0` (momentum + halt cancel).
Directives: `[(PACE, "slow"), (DISCLOSURE, "full_model_available"),
              (PREVIEW, "preview_only")]`.

### 9.6 Edge: understanding-gap drives pacing

```
aligned.safe_for_surface         = True
aligned.alignment_score          = 0.9
aligned.plan.steps               = [NONE]
aligned.plan.expected_pressure_delta = 0
aligned.plan.expected_agency_delta   = 0
momentum.passes_invariant        = True
understanding.passes_invariant   = False    (Ambient Trust says comprehension lagging)
```

`halt_level` = `NONE` (FEA is clean).
`trust_state_delta` = `0.1`.
Directives: `[(PACE, "slow")]` — driven by Ambient Trust, even though
FEA has no pressure_delta. This is the integration adding a structural
nudge.

---

## 10. Module Inventory

```
SPEC_FEA_INTEGRATION.md          ── this file
fea_integration_schemas.py       ── enums + types + 4 runtime guards
fea_integration_engine.py        ── integrate_alignment + canonical
                                      value validation
tests/test_fea_integration.py    ── structural + behavioral tests
```

---

## 11. Phase Plan

| Phase | Scope | Status |
|---|---|---|
| **This commit** | SPEC + schemas + deterministic engine + tests | **Shipping** |
| Next | Wire `integrate_alignment` into Azimuth Transition (consume after FEA) | Pending |
| Next+1 | Wire into Orchestrator post-step hook — `halt_level == HARD` → orchestrator `HaltState` (the dataclass) | Pending |
| Next+2 | Expand v1 to actually read `session`/`trust`/`envelope`/`propagation` | Pending |

---

## 12. Test Discipline

Every rule in § 5 + § 6 + § 7 has a dedicated behavioral test. Plus:

- Structural: enums + frozen + privacy field set + module-load guards.
- Worked examples 9.1–9.6 are each a discrete behavioral test.
- Invariants 1–12 are each individually verified (some via source-code
  inspection, some via behavioral assertion).
- Delta range: `trust_state_delta ∈ [0.0, 1.0]` asserted across
  parameterised inputs.
- Determinism: same inputs → byte-equal outputs across multiple calls.
- Privacy: marker injection into `EnvelopeState.raw_text` and
  `intention` must not leak into `IntegratedAlignmentResult`.
- Passthrough: `aligned_expression` field is *object-identity-equal* to
  the input `aligned`.
- Forward-compat: source-code asserts v1 does not branch on
  `session`, `trust`, `envelope`, or `propagation`.
