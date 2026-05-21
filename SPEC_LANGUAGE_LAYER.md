# ClarityOS Language Layer — Specification

**Status:** Phase 3 design. Schemas + PSE implementation locked. Tests pin
the deterministic behavior contract.

**Date:** 2026-05-11
**Discipline:** *Expression-only layer.* Selects **how** ClarityOS speaks —
never **what** it decides.

---

## 1. Purpose

The Language Layer is a **non-architectural, expression-only** layer that
chooses the *shape* of ClarityOS's communication for a given turn.

It introduces four **drift primitives** for expression:

- **Motion** — talking about trajectory, velocity, friction.
- **Geometry** — talking about structure, alignment, shape.
- **Hydronics** — talking about pressure, flow, containment, relief.
- **Analogy** — bridging concepts, identity-safe reframing.

These are **not new base primitives**. They are **expression modes**
deterministically derived from the 10 base ClarityOS primitives
(`C, D, L, A, T, B, G, I, P, S`).

The Language Layer is governed by:
- the Constitutional Layer (`ConstitutionalConstraint`),
- the Azimuth Mechanic (Envelope → Transition → Reframing),
- the Orchestrator (Routing → Context → Workflows, C/D/G/I/S).

It adds **zero** architecture. It owns **only** the question:
> *Given everything the system already knows about C/D/G/I/S, what tone /
> structure / metaphor frame should this response take?*

---

## 2. Base References (already defined and authoritative)

| Surface | Module |
|---|---|
| 10 base primitives | `C, D, L, A, T, B, G, I, P, S` (cross-cutting) |
| Constitutional + Identity + Drift + Geometry + Propagation | `orchestrator_schemas.py` |
| Envelope state | `azimuth.py::EnvelopeState` |
| Transition + Reframing | `azimuth_transition.py`, `azimuth_reframing.py` |
| Orchestrator layers | `orchestrator_routing.py`, `orchestrator_context.py`, `orchestrator_workflows.py` |

The Language Layer **consumes** these. It does not modify them.

---

## 3. The Four Drift Primitives

Each expression primitive is a **derived view** of the base primitives —
no new state, no new architecture.

### 3.1 Motion (`D + T + B + P`)

| Attribute | Meaning |
|---|---|
| velocity   | Rate of change in the user's situation |
| direction  | Toward / away from a target |
| acceleration | Whether motion is speeding up or slowing |
| friction   | Resistance the user is encountering |
| trajectory | Forward arc projected from current state |
| stall      | When motion has paused or reversed |

**Use when:**
- user is moving toward/away from something
- there is clear drift over time
- we need to talk about "where this is going"

### 3.2 Geometry (`G + D + I`)

| Attribute | Meaning |
|---|---|
| curvature  | How the system bends under load |
| torsion    | Twisting between intent and outcome |
| shear      | Discontinuity between adjacent layers |
| symmetry   | Whether the system is balanced |
| alignment  | Whether parts are pointing the same way |

**Use when:**
- user is analyzing a system
- we need to talk about structure, shape, or alignment
- we are diagnosing misalignment or inversion

### 3.3 Hydronics (`L + D + B + P`)

| Attribute | Meaning |
|---|---|
| pressure       | Felt load |
| flow_rate      | Rate of throughput |
| blockage       | Where flow is interrupted |
| containment    | Where pressure is held |
| valve/release  | Where relief is possible |
| pressure_zones | How pressure distributes |

**Use when:**
- user is under emotional/relational load
- we need to talk about pressure and relief
- we are mapping burden across boundaries

### 3.4 Analogy (`P + S + I`)

| Attribute | Meaning |
|---|---|
| source_domain     | Where the metaphor comes from |
| target_domain     | What it's mapped to |
| clarity_gain      | How much the mapping clarifies |
| emotional_distance | Buffer the metaphor provides |

**Use when:**
- user needs conceptual bridging
- we are delivering correction pathways
- we need identity-safe reframing

---

## 4. Mapping to Base Primitives (locked)

```python
EXPRESSION_PRIMITIVE_DERIVATION = {
    ExpressionPrimitive.MOTION:    ("D", "T", "B", "P"),
    ExpressionPrimitive.GEOMETRY:  ("G", "D", "I"),
    ExpressionPrimitive.HYDRONICS: ("L", "D", "B", "P"),
    ExpressionPrimitive.ANALOGY:   ("P", "S", "I"),
}
```

**Invariant (test-enforced):** every expression primitive maps to a
non-empty subset of `{C, D, L, A, T, B, G, I, P, S}`. Any future addition
that introduces a non-base primitive fails the suite.

---

## 5. The Primitive Selection Engine (PSE)

### 5.1 Input — `LanguageContext`

```python
@dataclass(frozen=True)
class LanguageContext:
    envelope:          EnvelopeSnapshot           # pressure/valence/intensity/intention_class
    drift_state:       DriftState                 # from orchestrator
    geometry_profile:  GeometryProfile            # from orchestrator
    identity_profile:  IdentityProfile            # from orchestrator
    conversation_mode: ConversationMode           # OPERATOR/EXPLORATORY/EMOTIONAL/STRUCTURAL/DECISION
    propagation_state: Optional[PropagationState] = None
    last_primitive:    Optional[ExpressionPrimitive] = None  # whiplash hint
```

### 5.2 Output — `ExpressionPlan`

```python
@dataclass(frozen=True)
class ExpressionPlan:
    primitive: ExpressionPrimitive          # MOTION/GEOMETRY/HYDRONICS/ANALOGY
    tone:      ToneProfile                  # STABLE/DIRECT/SOFTENED/EXPANSIVE
    structure: StructureProfile             # HIGHLY_STRUCTURED/MODERATE/MINIMAL
    length:    LengthProfile                # SHORT/MEDIUM/LONG
    rationale: str = ""                     # human-readable selection trace
```

### 5.3 Core function

```python
def select_expression_plan(ctx: LanguageContext) -> ExpressionPlan:
    """Pure, deterministic. No I/O. No randomness. No model calls.
    Uses envelope, drift, geometry, identity, and mode to select
    Motion/Geometry/Hydronics/Analogy + tone/structure/length."""
```

---

## 6. Selection Rules (deterministic priority order)

### 6.1 Primitive selection

The PSE applies rules in **strict priority order**. Higher priority
rules override lower ones.

| Priority | Trigger | Primitive | Rationale |
|---:|---|---|---|
| 1 | `pressure ∈ {HIGH, CRITICAL}` | **HYDRONICS** | Pressure/relief language is required. Hard override. |
| 2 | `drift.in_bounds == False` | **ANALOGY** | Clarity bridge needed to re-anchor. Hard override. |
| 3 | `mode == STRUCTURAL` | **GEOMETRY** | Mapping system structure. |
| 4 | `mode == DECISION` | **MOTION** | Forward trajectory of decision. |
| 5 | `mode == OPERATOR` | **GEOMETRY** (default, identity-tie-break) | Operator-grade analytical work. |
| 6 | `mode == EXPLORATORY` | **ANALOGY** | Bridging concepts. |
| 7 | `mode == EMOTIONAL` | **HYDRONICS** | Pressure / relief register. |
| 8 | default | **GEOMETRY** | Safe analytical default. |

**Identity tie-break for OPERATOR mode:**
- `actor_kind == USER ∧ authorization_tier == EXECUTE` → GEOMETRY
- otherwise → MOTION

**Whiplash prevention:**
After applying rules 3–8, if `ctx.last_primitive` is set AND the candidate
differs AND there is **no meaningful geometry change** since the prior
propagation state, the PSE *sticks with* `last_primitive` — unless the
current mode *strictly requires* a different primitive (STRUCTURAL needs
GEOMETRY, DECISION needs MOTION).

**Meaningful geometry change** = `|pressure_load_now − pressure_load_prior| ≥ 0.2`
OR `|stability_score_now − stability_score_prior| ≥ 0.2`.

Rules 1 and 2 (hard overrides) **always bypass** whiplash prevention —
emotional/clarity safety wins over coherence.

### 6.2 Tone / structure / length

| Trigger | Tone | Structure | Length |
|---|---|---|---|
| `pressure ∈ {HIGH, CRITICAL}` (override) | **STABLE** | **HIGHLY_STRUCTURED** | **MEDIUM** |
| `mode == OPERATOR` | DIRECT | HIGHLY_STRUCTURED | MEDIUM |
| `mode == EXPLORATORY` | EXPANSIVE | MODERATE | LONG |
| `mode == EMOTIONAL` | SOFTENED | MODERATE | MEDIUM |
| `mode == DECISION` | DIRECT | HIGHLY_STRUCTURED | SHORT |
| `mode == STRUCTURAL` | DIRECT | HIGHLY_STRUCTURED | MEDIUM |
| default | STABLE | MODERATE | MEDIUM |

The pressure override applies **regardless of mode** — invariant #9
(no emotional escalation) requires STABLE tone whenever pressure is HIGH.

---

## 7. Invariants (locked, test-enforced)

| # | Invariant | Enforcement |
|---:|---|---|
| 1 | **No new base primitives.** Every expression primitive maps to a subset of the 10 base primitives. | `EXPRESSION_PRIMITIVE_DERIVATION` constant + test |
| 2 | **No architecture changes.** Language Layer adds 3 files + 1 test file, nothing else. | Repository-level convention |
| 3 | **No I/O.** No network, no disk, no LLM calls. | Source-code inspection in tests |
| 4 | **No auto-send.** PSE returns a plan; never calls any sender. | Function-contract test (return type only) |
| 5 | **Identity safety.** ANALOGY must never attack identity; must preserve sovereignty. | Downstream contract — documented; PSE provides identity-safe selection only |
| 6 | **Drift reduction.** Selected primitive must not increase drift vs. intention. | Drift-override rule guarantees ANALOGY when out of bounds |
| 7 | **Monotonic constraints.** Language Layer cannot weaken constitutional constraints. | Layer has no constraint-write path; structurally true |
| 8 | **Determinism.** Same `LanguageContext` → same `ExpressionPlan`. | Pure-function test (deep equality across calls) |
| 9 | **No emotional escalation.** HYDRONICS must not increase pressure. | HIGH pressure → STABLE tone (never DIRECT or EXPANSIVE) — test-asserted |
| 10 | **Propagation coherence.** Avoid primitive whiplash unless geometry/pressure meaningfully change. | `_detect_whiplash_risk` + test |

---

## 8. Worked Examples

### 8.1 High-pressure operator turn

| Input | Value |
|---|---|
| pressure | HIGH |
| mode | OPERATOR |
| drift.in_bounds | True |

**Selection trace:**
- Rule 1 hits → HYDRONICS (pressure override).
- Tone override → STABLE (no emotional escalation).
- Structure → HIGHLY_STRUCTURED, Length → MEDIUM.

**Result:** `ExpressionPlan(HYDRONICS, STABLE, HIGHLY_STRUCTURED, MEDIUM)`.

### 8.2 System analysis

| Input | Value |
|---|---|
| pressure | LOW |
| mode | STRUCTURAL |
| drift.in_bounds | True |

- Rules 1 + 2 don't trigger.
- Rule 3 → GEOMETRY.
- Mode tone → DIRECT, HIGHLY_STRUCTURED, MEDIUM.

**Result:** `ExpressionPlan(GEOMETRY, DIRECT, HIGHLY_STRUCTURED, MEDIUM)`.

### 8.3 User confusion — concept bridging

| Input | Value |
|---|---|
| pressure | MEDIUM |
| mode | EXPLORATORY |
| drift.in_bounds | **False** |

- Rule 1 doesn't trigger.
- Rule 2 hits → ANALOGY (drift override).
- Mode tone → EXPANSIVE, MODERATE, LONG.

**Result:** `ExpressionPlan(ANALOGY, EXPANSIVE, MODERATE, LONG)`.

### 8.4 Decision moment

| Input | Value |
|---|---|
| pressure | MEDIUM |
| mode | DECISION |
| drift.in_bounds | True |

- Rules 1 + 2 don't trigger.
- Rule 4 → MOTION.
- Mode tone → DIRECT, HIGHLY_STRUCTURED, SHORT.

**Result:** `ExpressionPlan(MOTION, DIRECT, HIGHLY_STRUCTURED, SHORT)`.

### 8.5 Whiplash prevention across turns

Turn N-1: PSE chose MOTION (`mode=OPERATOR`, with `actor_kind=AGENT`, so MOTION won).
Turn N: same context shape, geometry essentially unchanged. Operator-grade identity now in play (e.g., user took over).

- Naive selection: rule 5 → GEOMETRY (operator-grade tie-break).
- Whiplash check: `last_primitive=MOTION`, no meaningful geometry change.
- Mode strict requirement check: OPERATOR mode does NOT strictly require GEOMETRY.
- → **Stick with MOTION** (coherence preserved).

**Result:** `ExpressionPlan(MOTION, DIRECT, HIGHLY_STRUCTURED, MEDIUM)`.

### 8.6 Whiplash bypass on hard override

Turn N-1: MOTION. Turn N: pressure spikes to HIGH.

- Rule 1 hits → HYDRONICS.
- Hard override bypasses whiplash check.
- Tone forced to STABLE.

**Result:** `ExpressionPlan(HYDRONICS, STABLE, HIGHLY_STRUCTURED, MEDIUM)`.

---

## 9. Module Inventory

```
SPEC_LANGUAGE_LAYER.md             ── this file
language_schemas.py                ── enums, EnvelopeSnapshot, LanguageContext, ExpressionPlan
primitive_selection_engine.py      ── deterministic select_expression_plan + helpers
tests/test_language_layer.py       ── structural + behavioral tests
```

---

## 10. Phase Plan

| Phase | Scope | Status |
|---|---|---|
| **This commit** | SPEC + schemas + deterministic PSE + tests | **Shipping** |
| Next | Wire into Azimuth reframing (PSE chooses tone/length, reframer fills text) | Pending |
| Next+1 | Wire into Orchestrator workflows (PSE called during context assembly) | Pending |
| Next+2 | Surface integration (web/phone display PSE's tone/structure decision) | Pending |

---

## 11. Test Discipline

Every selection rule in § 6 has a dedicated behavioral test:
- Pressure overrides
- Drift overrides
- Mode-driven defaults
- Identity tie-break
- Whiplash prevention
- Whiplash bypass (hard overrides + mode-strict requirements)
- Tone/structure/length per mode
- Pressure-driven tone override

Plus the structural invariants:
- All 4 expression primitives map to subsets of the 10 base primitives
- Determinism (same context → same plan, byte-equal)
- No I/O imports (source inspection)
- No randomness imports (source inspection)
- No LLM imports (source inspection)
- Schemas frozen
- Module surface exports the documented API
