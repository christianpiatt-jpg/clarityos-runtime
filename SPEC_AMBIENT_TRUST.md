# Ambient Trust — Specification

**Status:** Phase 1. Schemas + engine implementation locked. Tests pin the
deterministic behavior contract. This module exists so that later integration
layers (FEA integration, surface pacing, orchestrator post-step hooks) have a
real, type-aligned trust surface to consume.

**Date:** 2026-05-11
**Core invariant:** *Trust is structural, not motivational.* The user's sense
of being met is a function of two measurable things — whether comprehension
keeps up with ability, and whether momentum survives the system's actions —
and the system never converts a trust gap into a hard stop.

---

## 1. Purpose

Ambient Trust takes a `SessionContext` (ability, comprehension, exposure
counts, hard-stop counter, last-action acknowledgement) and produces:

1. A `TrustState` — current trust posture as four fields:
   `understanding_gap`, `momentum_intact`, `trust_score`, `repair_needed`.
2. An `UnderstandingCheck` — point-in-time verification of the invariant
   `comprehension_level >= ability_level - 1`.
3. A `MomentumCheck` — point-in-time verification that the system has not
   introduced a hard stop.
4. A `RepairDirective` — when `repair_needed` is True, a structural,
   non-blocking repair signal the surface can read.

The module enforces five behavioral commitments:

- **Trust gaps never stop momentum.** Repairs are gentle, never halts.
- **Comprehension leads action.** Ability cannot run more than one rank
  ahead of comprehension.
- **Concept exposure is a counter, never a gate.** The OS may count, but
  must not block on counts.
- **No raw text. No identity. Ever.**
- **Advisory only.** Ambient Trust returns data; the surface decides what
  to render.

Ambient Trust is **the canonical "interaction context" surface** for any
downstream integration layer that needs to reason about whether the user
is currently with the system. FEA Integration, Orchestrator post-step
hooks, and any future pacing module all read from this surface.

---

## 2. Privacy Model

```
                  ╔════════════════════════════════════╗
                  ║  Downstream integration layer       ║
                  ║  (consumes TrustState + checks)     ║
                  ╚═══════════════╤════════════════════╝
                                  │  TrustState + checks
                                  │  (NO text, NO identity)
                                  ▼
                  ┌─────────────────────────────────────┐
                  │  AMBIENT TRUST ENGINE               │
                  │  assess_trust_state(...)            │
                  │  verify_no_hard_stops(...)          │
                  │  verify_comprehension_leads_action  │
                  │  gentle_repair(...)                 │
                  │  → pure · deterministic             │
                  └───────────────┬─────────────────────┘
                                  │  SessionContext
                                  ▼
                  ┌─────────────────────────────────────┐
                  │  Caller (FEA Integration,           │
                  │  Orchestrator workflow, etc.)       │
                  └─────────────────────────────────────┘
```

**Boundary rules:**

1. `SessionContext` carries **only structural counters and ranks** — no
   raw text, no identity, no session ids, no concept text. Concept
   identifiers are restricted to a locked canonical set.
2. `TrustState`, `UnderstandingCheck`, `MomentumCheck`, and
   `RepairDirective` are **structurally guaranteed** (test-enforced) to
   omit `text`, `raw`, `user`, `id`, `name`, `email`, `session`,
   `identity`, `envelope_id`, `author`, `actor`, `content`, `body`,
   `message`.
3. The engine is pure: no I/O, no LLM, no network, no randomness.
4. `RepairDirective.rationale` is a **canonical, engine-generated string** —
   the engine never propagates user text.

---

## 3. Inputs

### 3.1 Locked constants

```python
MAX_LEVEL                       = 3      # ability/comprehension ∈ [0, 3]
GAP_TOLERANCE                   = 1      # comprehension >= ability - 1
SCORE_PENALTY_PER_GAP_LEVEL     = 0.2
SCORE_PENALTY_PER_HARD_STOP     = 0.1
SCORE_PENALTY_UNACKNOWLEDGED    = 0.2
HARD_STOP_PENALTY_CAP_LEVELS    = 2      # cap stops-penalty contribution
```

These constants are test-asserted; changing one is a deliberate spec change.

### 3.2 Canonical concept identifiers

`ConceptExposure.concept_id` must be a member of a locked canonical set.
This prevents free-text from entering the trust surface via the exposure
counter:

```python
CANONICAL_CONCEPT_IDS = (
    "envelope", "pressure", "geometry", "intention",
    "expression", "alignment", "halt_state",
    "trust", "momentum", "agency",
)
```

Adding a concept is a spec change; tests assert the set is locked.

### 3.3 New types

```python
@dataclass(frozen=True)
class ConceptExposure:
    concept_id: str   # ∈ CANONICAL_CONCEPT_IDS
    count:      int   # >= 0

@dataclass(frozen=True)
class SessionContext:
    """The canonical 'interaction context' type. Downstream
    integration layers (FEA Integration, etc.) consume this.

    Carries ONLY structural metadata — no text, no identity.
    """
    ability_level:            int                       # ∈ [0, MAX_LEVEL]
    comprehension_level:      int                       # ∈ [0, MAX_LEVEL]
    concept_exposures:        tuple                     # tuple[ConceptExposure, ...]
    hard_stop_count:          int = 0                   # >= 0
    last_action_acknowledged: bool = True
```

---

## 4. Outputs

```python
class RepairKind(str, Enum):
    NONE          = "none"          # no repair required
    RE_ANCHOR     = "re_anchor"     # re-state working context
    SLOW_PACE     = "slow_pace"     # pace too fast for comprehension
    OFFER_CHOICE  = "offer_choice"  # agency lost; restore choice
    NARROW_SCOPE  = "narrow_scope"  # zoom into a smaller piece

@dataclass(frozen=True)
class TrustState:
    understanding_gap:  int           # max(0, ability - comprehension)
    momentum_intact:    bool
    trust_score:        float         # ∈ [0.0, 1.0]
    repair_needed:      bool

@dataclass(frozen=True)
class UnderstandingCheck:
    ability_level:       int
    comprehension_level: int
    gap:                 int          # max(0, ability - comprehension)
    passes_invariant:    bool         # comprehension >= ability - GAP_TOLERANCE

@dataclass(frozen=True)
class MomentumCheck:
    hard_stop_count:          int
    last_action_acknowledged: bool
    hard_stop_detected:       bool    # hard_stop_count > 0
    passes_invariant:         bool    # hard_stop_count == 0

@dataclass(frozen=True)
class RepairDirective:
    kind:      RepairKind
    rationale: str                    # canonical, engine-generated
```

---

## 5. Trust Score (deterministic heuristic)

```text
score = 1.0  (baseline — full trust)

  - SCORE_PENALTY_PER_GAP_LEVEL * understanding_gap
  - SCORE_PENALTY_UNACKNOWLEDGED                       (if !last_action_acknowledged)
  - SCORE_PENALTY_PER_HARD_STOP * min(hard_stop_count, HARD_STOP_PENALTY_CAP_LEVELS)

clip to [0.0, 1.0]
```

`trust_score` is a pure function of `SessionContext`.

---

## 6. `momentum_intact` and `repair_needed`

### 6.1 `momentum_intact`

`True` iff `hard_stop_count == 0`. Trust gaps DO NOT break momentum — only
actual hard stops do. This is invariant 1.

### 6.2 `repair_needed`

`True` iff any of:

- `understanding_gap >= GAP_TOLERANCE` (gap at the edge gets a preventive
  nudge; gap over the edge gets the heavier `SLOW_PACE` directive)
- `last_action_acknowledged is False`
- `hard_stop_count > 0`

`False` otherwise.

---

## 7. Repair Selection (deterministic priority order)

`gentle_repair(trust, ctx)` selects exactly one `RepairKind`. Priority,
highest first:

| Priority | Trigger | Emits |
|---:|---|---|
| 1 | `hard_stop_count > 0` | `RE_ANCHOR` |
| 2 | `understanding_gap > GAP_TOLERANCE` | `SLOW_PACE` |
| 3 | `last_action_acknowledged == False` | `OFFER_CHOICE` |
| 4 | `understanding_gap == GAP_TOLERANCE` | `NARROW_SCOPE` |
| 5 | none of the above | `NONE` |

`RepairDirective.rationale` is taken from a locked rationale table; the
engine never propagates user text or session details into the rationale.

---

## 8. Invariants (locked, test-enforced)

| # | Invariant | Enforcement |
|---:|---|---|
| 1 | Trust gaps never stop momentum. | `momentum_intact` is a function of `hard_stop_count` only. Test-asserted. |
| 2 | Comprehension leads action: `comprehension_level >= ability_level - 1`. | `verify_comprehension_leads_action` checks this; downstream surfaces should respect it. Test-asserted. |
| 3 | Concept exposure counters never gate behavior in this module. | The engine reads `concept_exposures` but does not branch on counts. Source-code asserted. |
| 4 | No raw user text in any Ambient Trust type. | Structural — forbidden fields not in any `__dataclass_fields__`. Test-asserted. |
| 5 | No identity fields. | Structural — test-asserted across all output types and `SessionContext`. |
| 6 | Deterministic. Same inputs → same outputs. | Behavioral tests assert byte-equal returns. |
| 7 | No I/O, no LLM, no network, no randomness. | Source-code inspection in tests. |
| 8 | `RepairDirective.rationale` is canonical (never user text). | Engine emits from a locked rationale table; test-asserted via marker injection. |
| 9 | `trust_score ∈ [0.0, 1.0]` for all reachable inputs. | Clamping; test-asserted across parameterized inputs. |
| 10 | `gentle_repair` never emits a `HALT`-like directive. | `RepairKind` has no halting member; structurally true. |
| 11 | Concept ids are restricted to `CANONICAL_CONCEPT_IDS`. | Runtime guard at module load; test-asserted. |
| 12 | Ambient Trust is advisory. The surface decides what to render. | Module returns data; never calls send / never blocks. Source-inspection asserted. |

---

## 9. Worked Examples

### 9.1 In-rhythm session (no repair needed)

```
ability_level            = 2
comprehension_level      = 2
concept_exposures        = [(envelope, 3), (pressure, 2)]
hard_stop_count          = 0
last_action_acknowledged = True
```

`TrustState`: gap=0, momentum_intact=True, trust_score=1.0,
repair_needed=False.
`gentle_repair` → `RepairDirective(NONE, "no repair required")`.

### 9.2 Ability one rank ahead (still passes invariant; preventive nudge)

```
ability_level            = 2
comprehension_level      = 1
hard_stop_count          = 0
last_action_acknowledged = True
```

`UnderstandingCheck`: gap=1, passes_invariant=True (gap at tolerance is
still within bounds).
`TrustState`: gap=1, momentum_intact=True, trust_score=0.8 (1.0 − 0.2*1),
repair_needed=True (preventive — gap is at the edge).
`gentle_repair` → `NARROW_SCOPE`. The invariant still holds, so this is
a gentle preventive nudge to zoom in before the gap widens.

### 9.3 Ability two ranks ahead (invariant breaks; pace too fast)

```
ability_level            = 3
comprehension_level      = 1
hard_stop_count          = 0
last_action_acknowledged = True
```

`UnderstandingCheck`: gap=2, passes_invariant=False.
`TrustState`: gap=2, momentum_intact=True (no hard stop), trust_score=0.6,
repair_needed=True.
`gentle_repair` → `SLOW_PACE`.

### 9.4 User stopped acknowledging actions

```
ability_level            = 2
comprehension_level      = 2
hard_stop_count          = 0
last_action_acknowledged = False
```

`TrustState`: gap=0, momentum_intact=True, trust_score=0.8 (−0.2),
repair_needed=True.
`gentle_repair` → `OFFER_CHOICE`.

### 9.5 Hard stop introduced (worst case the module must survive)

```
ability_level            = 2
comprehension_level      = 2
hard_stop_count          = 1
last_action_acknowledged = True
```

`MomentumCheck`: hard_stop_count=1, hard_stop_detected=True,
passes_invariant=False.
`TrustState`: gap=0, momentum_intact=False, trust_score=0.9 (−0.1*1),
repair_needed=True.
`gentle_repair` → `RE_ANCHOR`.

### 9.6 Compound: ability ahead AND hard stop

```
ability_level            = 3
comprehension_level      = 1
hard_stop_count          = 2
last_action_acknowledged = False
```

`TrustState`: gap=2, momentum_intact=False, trust_score = max(0,
1.0 − 0.2*2 − 0.2 − 0.1*2) = 0.2, repair_needed=True.
`gentle_repair` → `RE_ANCHOR` (hard-stop has priority 1).

---

## 10. Module Inventory

```
SPEC_AMBIENT_TRUST.md           ── this file
ambient_trust_schemas.py        ── enums + types + 3 runtime guards
ambient_trust_engine.py         ── assess_trust_state /
                                    verify_no_hard_stops /
                                    verify_comprehension_leads_action /
                                    gentle_repair
tests/test_ambient_trust.py     ── structural + behavioral tests
```

---

## 11. Phase Plan

| Phase | Scope | Status |
|---|---|---|
| **This commit** | SPEC + schemas + deterministic engine + tests | **Shipping** |
| Next | FEA Integration Layer consumes `TrustState` + `SessionContext` | Pending |
| Next+1 | Wire `verify_comprehension_leads_action` into Orchestrator post-step | Pending |
| Next+2 | Persist exposure counters via `memory_vault` (separate module — Ambient Trust stays pure) | Pending |

---

## 12. Test Discipline

Every rule in § 5 + § 6 + § 7 has a dedicated behavioral test. Plus:

- Structural: enums + frozen + privacy field set + module-load guards.
- Worked examples 9.1–9.6 are each a discrete behavioral test.
- Invariants 1–12 are each individually verified (some via source-code
  inspection, some via behavioral assertion).
- Score range: `trust_score` ∈ `[0.0, 1.0]` asserted across parameterized
  inputs.
- Determinism: same inputs → byte-equal outputs across multiple calls.
- Privacy: marker injection into the only string field (`ConceptExposure.
  concept_id`) is rejected unless the id is in the canonical set.
