# Emotional Reality Alignment (ERA) — Specification

**Status:** Phase 3 design. Schemas + engine implementation locked. Tests pin
the deterministic behavior contract.

**Date:** 2026-05-11
**Core invariant:** *E = internal_relator.* Expression must match internal
relational meaning so the user's emotional choices produce the experience
they intend, not anchor-hijacked experience.

---

## 1. Purpose

The ERA module takes an emotional **snapshot + geometry + intention**
plus the **expression primitive** chosen by the Language Layer, and
produces:

1. A `ReframePlan` — an ordered set of `ReframeStep`s with expected
   pressure / agency deltas.
2. An `AlignedExpression` — the plan plus an alignment score and two
   safety flags (`internal_relator_preserved`, `safe_for_surface`).

The module enforces five behavioral commitments:

- **Preserves lived meaning** — the user's actual relational truth.
- **Reduces distortion** — shame, globalizing, helplessness.
- **Increases precision and agency.**
- **Never escalates pressure** under HIGH/CRITICAL load.
- **Never attacks identity.**

ERA is **advisory only**. The final expression still passes through the
Sovereignty Gate (downstream of ERA).

---

## 2. Privacy Model

```
                  ╔════════════════════════════════════╗
                  ║  Downstream surface                ║
                  ║  (consumes AlignedExpression)      ║
                  ╚═══════════════╤════════════════════╝
                                  │  ReframePlan + flags
                                  │  (NO text, NO identity)
                                  ▼
                  ┌─────────────────────────────────────┐
                  │  EMOTIONAL ALIGNMENT ENGINE         │
                  │  align_expression(...)              │
                  │  → pure · deterministic             │
                  └───────────────┬─────────────────────┘
                                  │  EmotionalSnapshot +
                                  │  EmotionalGeometry +
                                  │  EmotionalIntention +
                                  │  ExpressionPrimitive
                                  ▼
                  ┌─────────────────────────────────────┐
                  │  Caller (Azimuth Transition,        │
                  │   Orchestrator workflow, etc.)      │
                  └─────────────────────────────────────┘
```

**Boundary rules:**

1. ERA inputs (`EmotionalSnapshot`, `EmotionalGeometry`,
   `EmotionalIntention`) carry only **structural metadata** — no raw
   text, no identity.
2. ERA outputs (`ReframeStep`, `ReframePlan`, `AlignedExpression`) are
   **structurally guaranteed** (test-enforced) to omit `text`, `raw`,
   `user`, `id`, `name`, `email`, `session`.
3. The engine is pure: no I/O, no LLM, no network, no randomness.

---

## 3. Inputs (reused + minimal)

### 3.1 Reused upstream types

```python
PressureLevel       ← azimuth         # LOW / MEDIUM / HIGH / CRITICAL
IntensityLevel      ← azimuth         # LOW / MEDIUM / HIGH / EXTREME
Valence             ← azimuth         # POSITIVE / NEGATIVE / MIXED / NEUTRAL / UNKNOWN
ConversationMode    ← language_schemas # for context (not consumed here)
ExpressionPrimitive ← language_schemas # MOTION / GEOMETRY / HYDRONICS / ANALOGY
```

### 3.2 Minimal new types

The spec assumes `EmotionalSnapshot` and `EmotionalGeometry` exist
"from prior units." They do not, so the ERA module defines minimal
versions sufficient for the rule set in § 5. They are kept in
`emotional_alignment_schemas.py` and may be promoted to a separate
"Emotional Geometry" module later without breaking imports.

```python
@dataclass(frozen=True)
class EmotionalSnapshot:
    pressure_level:  PressureLevel
    intensity:       IntensityLevel
    valence:         Valence
    temporal_linked: bool   # this state is linked to a repeating pattern
    anchor_present:  bool   # a specific memory/pattern anchor is active

@dataclass(frozen=True)
class EmotionalGeometry:
    curvature:         bool   # globalizing ("always", "never", "everything")
    torsion:           bool   # twisted between intent and outcome
    shear:             bool   # self-attack / identity collapse into behavior
    boundary:          bool   # boundary distortion (dominance / helplessness)
    stance_self:       float  # 0–1; high = self-attacking
    stance_other:      float  # 0–1; high = other-attacking
    stance_world:      float  # 0–1; high = world-hostile
    pressure_gradient: float  # 0–1; rate of change in pressure

@dataclass(frozen=True)
class EmotionalIntention:
    target_state:       str                 # short canonical label
    regulatory_goal:    RegulationGoal      # CONTAIN / EXPRESS / TRANSFORM
    relational_posture: RelationalPosture   # CONNECT / SEPARATE / DEFEND / SUBMIT
    meaning_need:       MeaningNeed         # CLARIFY / VALIDATE / REFRAME / NONE
```

---

## 4. Outputs

```python
class ReframeType(str, Enum):
    LABEL    = "label"     # global identity → behavior-bounded
    TEMPORAL = "temporal"  # repeat pattern → this instance
    ROLE     = "role"      # boundary distortion → role redefinition
    SCALE    = "scale"     # globalizing → specific scope
    AGENCY   = "agency"    # submit/helplessness → choice restored
    MEANING  = "meaning"   # torsion/shear → coherent meaning
    NONE     = "none"      # no reframe required

@dataclass(frozen=True)
class ReframeStep:
    reframe_type: ReframeType
    rationale:    str   # canonical, non-user-text

@dataclass(frozen=True)
class ReframePlan:
    steps:                   tuple[ReframeStep, ...]
    primitive:               ExpressionPrimitive
    expected_pressure_delta: int   # ∈ {-1, 0, +1}
    expected_agency_delta:   int   # ∈ {-1, 0, +1}

@dataclass(frozen=True)
class AlignedExpression:
    plan:                       ReframePlan
    alignment_score:            float   # [0.0, 1.0]
    internal_relator_preserved: bool
    safe_for_surface:           bool
```

---

## 5. Reframe Plan Construction (deterministic priority order)

The engine builds the plan as an **ordered set of reframe steps**.
Higher priority rules fire first. Multiple rules may fire — each
adds at most one step of its type.

### 5.1 HIGH/CRITICAL pressure path

Under `PressureLevel ∈ {HIGH, CRITICAL}`, the allowed reframe types
are **AGENCY and SCALE only**. All other types (LABEL, TEMPORAL,
ROLE, MEANING) are excluded by hard rule.

| Trigger | Adds |
|---|---|
| `geometry.curvature == True` | SCALE |
| `intention.relational_posture == SUBMIT` ∨ `geometry.stance_world ≥ 0.7` | AGENCY |
| no trigger fires | NONE |

### 5.2 LOW/MEDIUM pressure path

The full reframe palette is available; multiple steps may be added.

| Priority | Trigger | Adds |
|---:|---|---|
| 2 | `snapshot.temporal_linked == True` ∧ `snapshot.anchor_present == True` | TEMPORAL |
| 3 | `geometry.shear == True` ∨ `geometry.stance_self ≥ 0.7` | LABEL |
| 4a | `geometry.boundary == True` ∨ `geometry.stance_other ≥ 0.7` | ROLE |
| 4b | `intention.relational_posture == SUBMIT` | ROLE + AGENCY |
| 5 | `geometry.curvature == True` | SCALE |
| 6 | `geometry.torsion == True` ∨ `geometry.shear == True` | MEANING |
| – | no trigger fires | NONE |

**Stance threshold:** locked at `0.7`. Tests assert this constant.

### 5.3 Expected deltas

Computed from the set of reframe types present in `steps`:

| Step type present | Effect on `expected_pressure_delta` |
|---|---|
| SCALE | −1 |
| LABEL | −1 |
| else | 0 |

| Step type present | Effect on `expected_agency_delta` |
|---|---|
| AGENCY | +1 |
| ROLE | +1 |
| else | 0 |

**Hard cap under HIGH/CRITICAL:** `expected_pressure_delta = min(delta, 0)`.
The reframe **must not** increase pressure when load is already HIGH.

---

## 6. Alignment Score (deterministic heuristic)

```text
score = 0.5  (baseline)

  + 0.2  if AGENCY  ∈ steps  ∧ expected_agency_delta   ≥ 0
  + 0.2  if SCALE   ∈ steps  ∧ expected_pressure_delta ≤ 0
  + 0.1  if TEMPORAL ∈ steps ∧ snapshot.temporal_linked = True
  + 0.1  if LABEL   ∈ steps  ∧ (geometry.shear ∨ geometry.stance_self ≥ 0.7)

clip to [0.0, 1.0]
```

The score is a **pure function** of `(snapshot, geometry, intention,
plan)`. `intention` is accepted in the signature for future
extensibility but not consumed in the v1 heuristic.

---

## 7. Safety Flags

### 7.1 `internal_relator_preserved`

`True` iff no step contradicts the snapshot:

- Specifically: NO `MEANING` step is present when
  `pressure_level ∈ {HIGH, CRITICAL}`.

(Other contradictions can be added in future versions; the v1 rule
is the spec-listed one.)

### 7.2 `safe_for_surface`

`True` iff:
- `expected_pressure_delta ≤ 0`, AND
- no `MEANING` step under HIGH/CRITICAL pressure.

`False` otherwise — the surface should NOT auto-apply the reframe and
should defer to human review.

---

## 8. Invariants (locked, test-enforced)

| # | Invariant | Enforcement |
|---:|---|---|
| 1 | No raw user text stored in any ERA type. | Structural — `text`/`raw` not in any `__dataclass_fields__`; test-asserted. |
| 2 | No identity fields (`user_id`, `name`, `email`, `session_id`). | Structural — test-asserted across `ReframeStep`, `ReframePlan`, `AlignedExpression`, and the three base types. |
| 3 | Deterministic. Same inputs → same outputs (deep equality). | Behavioral tests assert byte-equal returns across calls. |
| 4 | No I/O, no LLM, no network, no randomness. | Source-code inspection in tests. |
| 5 | Reframing must not increase pressure under HIGH/CRITICAL. | `_compute_deltas` clamps via `min(delta, 0)`; test-asserted. |
| 6 | Reframing must not increase shame / self-attack. | Achieved by only fire-and-add (never amplify); test-asserted via no-MEANING-under-HIGH rule. |
| 7 | Reframing must not weaken constitutional constraints. | ERA emits advisory; doesn't touch constraints. Structurally true. |
| 8 | At least one of {precision, agency, temporal differentiation} increases. | When any rule fires, at least one of SCALE/AGENCY/TEMPORAL/LABEL/ROLE/MEANING is added; each maps to one of the three improvement axes. |
| 9 | `alignment_score` is a pure function of `(snapshot, geometry, intention, plan)`. | `compute_alignment_score` has no I/O; test-asserted via determinism. |
| 10 | ERA is advisory only — final expression still passes through Sovereignty Gate. | Module returns data; never calls send. Source-inspection asserted. |

---

## 9. Worked Examples

### 9.1 Authority shame (MEDIUM pressure, temporal anchor, shame, boundary)

```
pressure        = MEDIUM
temporal_linked = True
anchor_present  = True
shear           = True
boundary        = True
stance_self     = 0.8
relational_posture = SUBMIT
```

**Plan:** `TEMPORAL` (rule 2) + `LABEL` (rule 3) + `ROLE` + `AGENCY`
(rule 4b) + `SCALE`? no (no curvature) + `MEANING` (rule 6, shear in
low/medium).

**Deltas:** pressure −1 (LABEL), agency +1 (AGENCY).
**Score:** 0.5 + 0.2 (AGENCY) + 0.1 (TEMPORAL+temporal_linked) + 0.1 (LABEL+shear) = **0.9**.
**Flags:** preserved=True, safe=True.

### 9.2 Repeated failure / globalizing (MEDIUM, curvature, temporal)

```
pressure        = MEDIUM
temporal_linked = True
anchor_present  = True
curvature       = True
```

**Plan:** `TEMPORAL` + `SCALE`. Deltas: pressure −1, agency 0.
**Score:** 0.5 + 0.2 (SCALE) + 0.1 (TEMPORAL) = **0.8**.

### 9.3 Anger hiding fear (HIGH, boundary + stance_other high)

```
pressure          = HIGH
boundary          = True
stance_other      = 0.9
stance_world      = 0.7
relational_posture = DEFEND
```

**Plan:** under HIGH, only AGENCY/SCALE permitted. `AGENCY` fires
(stance_world ≥ 0.7). SCALE doesn't fire (no curvature).

**Result:** `[AGENCY]`. Deltas: pressure 0, agency +1.
**Flags:** preserved=True (no MEANING), safe=True.

### 9.4 Collapse (CRITICAL, curvature + shame + SUBMIT)

```
pressure        = CRITICAL
curvature       = True
shear           = True
stance_self     = 0.9
relational_posture = SUBMIT
```

**Plan:** `SCALE` (curvature) + `AGENCY` (SUBMIT). Under CRITICAL,
LABEL/TEMPORAL/ROLE/MEANING all excluded even though shear is present.

**Result:** `[SCALE, AGENCY]`. Deltas: pressure −1, agency +1.
**Flags:** preserved=True (no MEANING), safe=True.

### 9.5 Low-pressure reflection (LOW, torsion only)

```
pressure   = LOW
torsion    = True
shear      = False
relational_posture = CONNECT
```

**Plan:** `MEANING` only (rule 6 fires; nothing else applies).
**Deltas:** pressure 0, agency 0.
**Score:** 0.5 (no bonuses match).
**Flags:** preserved=True, safe=True.

### 9.6 No-reframe needed (LOW pressure, nothing distorted)

```
pressure = LOW
[all geometry flags False, all stance values low]
```

**Plan:** `[NONE]`. Deltas 0/0. Score 0.5. Flags True/True.

---

## 10. Module Inventory

```
SPEC_EMOTIONAL_REALITY_ALIGNMENT.md   ── this file
emotional_alignment_schemas.py        ── base + ERA types + 3 runtime guards
emotional_alignment_engine.py         ── deterministic build_reframe_plan /
                                          compute_alignment_score / align_expression
tests/test_emotional_alignment.py     ── structural + behavioral tests
```

---

## 11. Phase Plan

| Phase | Scope | Status |
|---|---|---|
| **This commit** | SPEC + schemas + deterministic engine + tests | **Shipping** |
| Next | Wire ERA into Azimuth `reframe_candidate` as the alignment scorer | Pending |
| Next+1 | Wire into Orchestrator post-step hook (HaltState if safe_for_surface=False) | Pending |
| Next+2 | Promote base types to a dedicated `emotional_geometry_schemas.py` if reused beyond ERA | Pending |

---

## 12. Test Discipline

Every rule in § 5 + § 6 + § 7 has a dedicated behavioral test. Plus:

- Structural: enums + frozen + privacy field set + module-load guards.
- Worked examples 9.1–9.6 are each a discrete behavioral test.
- Invariants 1–10 are each individually verified (some via source-code
  inspection, some via behavioral assertion).
- Delta range: `expected_pressure_delta` and `expected_agency_delta`
  asserted to lie in `{-1, 0, +1}` for every reachable plan.
- Determinism: same inputs → byte-equal `ReframePlan` and
  `AlignedExpression` across multiple calls.
