# Feedback Ingestion System (FIS) — Specification

**Status:** Phase 3 design. Schemas + ingestion engine implementation locked.
Tests pin the deterministic behavior contract.

**Date:** 2026-05-11
**Discipline:** *Pattern-only storage.* Converts unstructured founder
feedback into constitutional structural patterns — never stores raw
text, never stores identity, never makes a model call.

---

## 1. Purpose

The Feedback Ingestion System (FIS) is the deterministic bridge from
**unstructured founder feedback** → **constitutional structural
patterns** that the rest of ClarityOS (Azimuth, Orchestrator, Language
Layer) can consume.

Its single rule: **the output carries no raw text and no identity.**
Whatever the founder typed is converted lexically + structurally into a
small, canonical `FeedbackPattern` envelope. The raw submission is
read **once**, transformed, and discarded by the caller.

The FIS is the same shape as the Language Layer:
pure deterministic function, no I/O, no LLM, behavioral tests pinning
exact outputs.

---

## 2. Privacy Model

```
                    ╔═══════════════════════════════╗
                    ║  ClarityOS update loop        ║
                    ║  (consumes FeedbackPattern)   ║
                    ╚═══════════╤═══════════════════╝
                                │  FeedbackPattern (no text, no identity)
                    ┌───────────┴───────────────────┐
                    │  INGESTION ENGINE             │
                    │  extract_pattern(submission)  │
                    │  → reads text ONCE, lexically │
                    │  → emits canonical pattern    │
                    └───────────┬───────────────────┘
                                │  FeedbackSubmission (transient)
                    ┌───────────┴───────────────────┐
                    │  founder feedback surface     │
                    │  (user types · sends once)    │
                    └───────────────────────────────┘
```

**Boundary rules:**

1. The caller passes a `FeedbackSubmission` (with `text`) to
   `extract_pattern(...)`.
2. The engine reads `text` **only** for lexical scans (drift markers,
   signal markers). The text never enters the return value.
3. The returned `FeedbackPattern` is **structurally guaranteed** (test-
   enforced) to omit `text`, `raw_text`, `user_id`, `actor`, `identity`,
   `envelope_id`, `name`, `names`.
4. The caller is responsible for discarding the submission after the
   call. The FIS does not persist anything.

---

## 3. Pipeline

```
                 FeedbackSubmission
                       │
                       ▼
        ┌──────────────────────────────┐
        │ 1. Classification            │
        │    pattern_type via rule     │
        │    chain (pressure → drift   │
        │    → mode → primitive)       │
        └──────────────┬───────────────┘
                       ▼
        ┌──────────────────────────────┐
        │ 2. Structural Extraction     │
        │    context = submission.mode │
        │    pressure_level forwarded  │
        │    primitive forwarded       │
        └──────────────┬───────────────┘
                       ▼
        ┌──────────────────────────────┐
        │ 3. Pattern Normalization     │
        │    signal via lexical scan   │
        │    (positive / negative /    │
        │    neutral; negative wins)   │
        └──────────────┬───────────────┘
                       ▼
        ┌──────────────────────────────┐
        │ 4. Constitutional Storage    │
        │    suggested_adjustment from │
        │    canonical mapping table   │
        └──────────────┬───────────────┘
                       ▼
        ┌──────────────────────────────┐
        │ 5. Update Loop Hooks         │
        │    FeedbackPattern emitted   │
        │    (downstream consumes it)  │
        └──────────────────────────────┘
```

---

## 4. Schemas (canonical)

The single source of truth is `feedback_schemas.py`.

### 4.1 Enums

```python
class SignalType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL  = "neutral"

class PatternType(str, Enum):
    TONE      = "tone"
    DRIFT     = "drift"
    PRESSURE  = "pressure"
    ALIGNMENT = "alignment"
    BOUNDARY  = "boundary"
    USE_CASE  = "use_case"
```

**Reused from existing modules** (no new copies):
- `PressureLevel` ← `azimuth`
- `ConversationMode` ← `language_schemas`
- `ExpressionPrimitive` (aliased as `PrimitiveType` for spec parity) ← `language_schemas`

### 4.2 Dataclasses

```python
@dataclass(frozen=True)
class FeedbackSubmission:
    text:           str
    mode:           ConversationMode
    pressure_level: PressureLevel
    primitive_used: ExpressionPrimitive
    timestamp:      datetime

@dataclass(frozen=True)
class FeedbackPattern:
    """STRUCTURAL PRIVACY GUARANTEE — test-enforced:
        NO text, NO raw_text, NO user_id, NO identity, NO envelope_id."""
    pattern_type:         PatternType
    context:              ConversationMode
    pressure_level:       PressureLevel
    signal:               SignalType
    primitive_involved:   ExpressionPrimitive
    suggested_adjustment: str

@dataclass(frozen=True)
class ExtractionContext:
    """Optional whiplash-prevention hint. None → straight rule chain."""
    last_pattern_type: Optional[PatternType] = None
    last_pressure:     Optional[PressureLevel] = None
    last_mode:         Optional[ConversationMode] = None
```

---

## 5. Extraction Rules (deterministic priority order)

The PSE for feedback runs rules in **strict priority**. Higher priority
wins.

| Priority | Trigger | Pattern | Notes |
|---:|---|---|---|
| 1 | `submission.pressure_level ∈ {HIGH, CRITICAL}` | **PRESSURE** | Hard override — bypasses whiplash. |
| 2 | `text` contains any drift marker | **DRIFT** | Hard override — bypasses whiplash. |
| 3 | `submission.mode == OPERATOR` | ALIGNMENT | Mode-driven default. |
| 4 | `submission.mode == DECISION` | USE_CASE | Mode-driven default. |
| 5 | `submission.mode == EMOTIONAL` | TONE | Mode-driven default. |
| 6 | `submission.mode == STRUCTURAL` | ALIGNMENT | Mode-driven default. |
| 7 | `submission.mode == EXPLORATORY` | USE_CASE | Mode-driven default. |
| 8 | Primitive fallback (if mode unmapped) | per `_PRIMITIVE_TO_PATTERN` | Currently dead path; future-proof. |
| 9 | default | ALIGNMENT | Safe fallback. |

**Drift markers (locked):**
```python
("drift", "confus", "mismatch", "misalign", "lost", "wandered", "off track")
```

**Primitive → Pattern mapping (rule 8 fallback):**
```python
{
    HYDRONICS: PRESSURE,
    GEOMETRY:  ALIGNMENT,
    MOTION:    DRIFT,
    ANALOGY:   USE_CASE,
}
```

**Whiplash prevention:**
If `ExtractionContext` is supplied with `last_pattern_type`, and the
candidate differs, AND `mode == last_mode` AND `pressure_level ==
last_pressure`, the engine **preserves** `last_pattern_type`.

Hard overrides (rules 1 and 2) **always bypass** whiplash prevention.

---

## 6. Signal Detection

Lexical scan of `submission.text`. Negative wins on tie (safer default).

```python
_POSITIVE_MARKERS = (
    "helpful", "helped", "good", "worked", "clear", "effective",
    "great", "useful", "love", "appreciate", "thanks", "thank",
)

_NEGATIVE_MARKERS = (
    "wrong", "bad", "missed", "harsh", "sharp", "broken",
    "frustrat", "didn't", "doesn't", "couldn't", "shouldn't",
    "fail", "poor",
)
```

Rules:
- If text contains any negative marker → `SignalType.NEGATIVE`.
- Else if text contains any positive marker → `SignalType.POSITIVE`.
- Else → `SignalType.NEUTRAL`.

---

## 7. Suggested Adjustment Table (locked)

| Pattern | Suggested Adjustment |
|---|---|
| PRESSURE  | Reduce intensity; favor STABLE tone + HIGHLY_STRUCTURED structure |
| DRIFT     | Increase clarity bridging; consider ANALOGY primitive |
| TONE      | Soften tone; check audience and pressure context |
| ALIGNMENT | Re-anchor to structural baseline; favor GEOMETRY primitive |
| BOUNDARY  | Reinforce sovereignty boundaries; defer to user authority |
| USE_CASE  | Surface as exemplar pattern; consider for documentation |

These are **canonical short strings** — never raw text from the user.
The test suite asserts every `PatternType` has an entry.

---

## 8. Invariants (locked, test-enforced)

| # | Invariant | Enforcement |
|---:|---|---|
| 1 | **No raw text stored** in `FeedbackPattern`. | Structural — `text` not in `__dataclass_fields__`; test-asserted. |
| 2 | **No identity stored** in `FeedbackPattern`. | `user_id`, `actor`, `identity`, `envelope_id`, `name`, `names` all absent; test-asserted. |
| 3 | **Deterministic extraction.** | Pure function; behavioral tests assert byte-equal returns. |
| 4 | **No I/O.** | Source-code inspection in tests (no `open()`, no `Path`, etc.). |
| 5 | **No LLM.** | Source inspection (no openai / anthropic / intelligence_kernel / model_router imports). |
| 6 | **No network.** | Source inspection (no urllib / http / requests / socket). |
| 7 | **No randomness.** | Source inspection (no random / secrets imports). |
| 8 | **No auto-send.** | Function returns a value; no side effects, no callbacks invoked. |
| 9 | **Constitutional safety.** | Every output pattern maps to a canonical `suggested_adjustment` from the locked table. |
| 10 | **Pattern-only storage.** | `FeedbackPattern.__dataclass_fields__` is exactly the canonical 6 fields. |

---

## 9. Worked Examples

### 9.1 "Tone too sharp under pressure"

| Input | Value |
|---|---|
| text             | `"Tone too sharp under pressure"` |
| mode             | `EMOTIONAL` |
| pressure_level   | `MEDIUM` |
| primitive_used   | `HYDRONICS` |

**Trace:**
- Rule 1: pressure=MEDIUM → no override.
- Rule 2: no drift markers.
- Rule 5: mode=EMOTIONAL → **TONE**.
- Signal: "sharp" matches negative → **NEGATIVE**.

**Output:**
```python
FeedbackPattern(
    pattern_type=TONE,
    context=EMOTIONAL,
    pressure_level=MEDIUM,
    signal=NEGATIVE,
    primitive_involved=HYDRONICS,
    suggested_adjustment="Soften tone; check audience and pressure context",
)
```

### 9.2 "Wanted more structure in decision mode"

| Input | Value |
|---|---|
| text             | `"Wanted more structure in decision mode"` |
| mode             | `DECISION` |
| pressure_level   | `LOW` |
| primitive_used   | `MOTION` |

**Trace:**
- Rules 1 + 2: no override.
- Rule 4: mode=DECISION → **USE_CASE**.
- Signal: no markers match → **NEUTRAL**.

**Output:**
```python
FeedbackPattern(
    pattern_type=USE_CASE,
    context=DECISION,
    pressure_level=LOW,
    signal=NEUTRAL,
    primitive_involved=MOTION,
    suggested_adjustment="Surface as exemplar pattern; consider for documentation",
)
```

### 9.3 "Analogy helped reduce drift"

| Input | Value |
|---|---|
| text             | `"Analogy helped reduce drift"` |
| mode             | `EXPLORATORY` |
| pressure_level   | `LOW` |
| primitive_used   | `ANALOGY` |

**Trace:**
- Rule 1: no.
- Rule 2: "drift" is a drift marker → **DRIFT** (override).
- Signal: "helped" → **POSITIVE**.

**Output:**
```python
FeedbackPattern(
    pattern_type=DRIFT,
    context=EXPLORATORY,
    pressure_level=LOW,
    signal=POSITIVE,
    primitive_involved=ANALOGY,
    suggested_adjustment="Increase clarity bridging; consider ANALOGY primitive",
)
```

### 9.4 "System felt frustrating under high pressure"

| Input | Value |
|---|---|
| text             | `"System felt frustrating under high pressure"` |
| mode             | `OPERATOR` |
| pressure_level   | `HIGH` |
| primitive_used   | `GEOMETRY` |

**Trace:**
- Rule 1: pressure=HIGH → **PRESSURE** (override).
- Signal: "frustrat" → **NEGATIVE**.

**Output:**
```python
FeedbackPattern(
    pattern_type=PRESSURE,
    context=OPERATOR,
    pressure_level=HIGH,
    signal=NEGATIVE,
    primitive_involved=GEOMETRY,
    suggested_adjustment="Reduce intensity; favor STABLE tone + HIGHLY_STRUCTURED structure",
)
```

### 9.5 "Clear and helpful — good alignment with my goal"

| Input | Value |
|---|---|
| text             | `"Clear and helpful — good alignment with my goal"` |
| mode             | `STRUCTURAL` |
| pressure_level   | `LOW` |
| primitive_used   | `GEOMETRY` |

**Trace:**
- Rules 1 + 2: no.
- Rule 6: mode=STRUCTURAL → **ALIGNMENT**.
- Signal: "clear" + "helpful" + "good" — all positive → **POSITIVE**.

**Output:**
```python
FeedbackPattern(
    pattern_type=ALIGNMENT,
    context=STRUCTURAL,
    pressure_level=LOW,
    signal=POSITIVE,
    primitive_involved=GEOMETRY,
    suggested_adjustment="Re-anchor to structural baseline; favor GEOMETRY primitive",
)
```

### 9.6 Whiplash prevention across turns

| Turn | mode | pressure | primitive | text | naive pattern | output |
|---|---|---|---|---|---|---|
| N-1 | OPERATOR | LOW | GEOMETRY | "Worked well" | ALIGNMENT (mode) | ALIGNMENT |
| N   | EMOTIONAL | LOW | HYDRONICS | "Felt off" | TONE (mode change) | TONE (mode changed → switch allowed) |
| N+1 | EMOTIONAL | LOW | HYDRONICS | "Better now" | TONE (mode unchanged, no Δ) | TONE (continuity) |

Whiplash is bypassed when mode or pressure changes; preserved when they
don't.

---

## 10. Module Inventory

```
SPEC_FEEDBACK_INGESTION.md         ── this file
feedback_schemas.py                ── enums, FeedbackSubmission, FeedbackPattern, ExtractionContext
ingestion_engine.py                ── deterministic extract_pattern + helpers
tests/test_feedback_ingestion.py   ── structural + behavioral tests
```

---

## 11. Phase Plan

| Phase | Scope | Status |
|---|---|---|
| **This commit** | SPEC + schemas + deterministic engine + tests | **Shipping** |
| Next | Wire FIS into Orchestrator workflow as a post-step hook | Pending |
| Next+1 | Surface integration (web/phone "send feedback" → extract_pattern → store pattern only) | Pending |
| Next+2 | Update loop — patterns inform constraint adjustments | Pending |

---

## 12. Test Discipline

Every selection rule in § 5 has a dedicated behavioral test:
- Pressure overrides (HIGH + CRITICAL)
- Drift overrides (all canonical markers)
- Mode-driven rules (all 5 modes)
- Primitive-driven mapping (table coverage)
- Signal detection (positive / negative / neutral / tie-breaking)
- Whiplash prevention (preserve when no Δ; bypass on overrides)
- Suggested adjustment table (every PatternType covered)

Plus structural invariants:
- `FeedbackPattern` has exactly 6 canonical fields — no `text`, no
  identity.
- Module-load runtime guard catches privacy violations at import.
- Source-code inspection enforces no LLM / network / I/O / randomness
  imports.
- Determinism: same submission → byte-equal pattern.
