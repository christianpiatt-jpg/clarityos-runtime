# Azimuth Mechanic — Specification

**Status:** Phase 3 design. Schemas locked. Module skeletons land in this commit.
Real implementation deferred to Phase 3 Unit 5 (Envelope + Transition) and Unit 6
(Reframing + Azimuth Check).

**Date:** 2026-05-11
**Tracks delivered together:** Envelope + Transition (Track 1) · Expression Reframing (Track 2)

---

## 1. Purpose

The Azimuth Mechanic closes the gap between **internal intention** and **external
expression**. Humans regularly experience a divergence between *what they mean
and feel* and *what lands when they say it*. This gap — call it **azimuth drift** —
is the source of most relational friction, professional misfires, and "I shouldn't
have said that" regret.

The Azimuth Mechanic does not censor. It does not moralize. It translates and
aligns.

---

## 2. Privacy Model — Three Concentric Layers

```
                            ╔════════════════════════════╗
                            ║   CLOUD                    ║
                            ║   metadata only            ║
                            ║   no raw text, no ids      ║
                            ╚═══════╤════════════════════╝
                                    │  pressure shape / slope / risk flags
                                    │  audience type / context type
                                    │  intention class
                                    │  NEVER raw content
                            ┌───────┴────────────────────┐
                            │   TRANSITION               │
                            │   internal → external      │
                            │   (still on-device)        │
                            └───────┬────────────────────┘
                                    │  ExpressionCandidate (private)
                            ┌───────┴────────────────────┐
                            │   ENVELOPE                 │
                            │   raw, intimate            │
                            │   zero-judgment            │
                            └────────────────────────────┘
```

**Boundary rules**

1. **Envelope ←→ Transition** — same device, same trust boundary. Raw text
   crosses freely.
2. **Transition → Cloud** — ONLY structural metadata. No raw text. No user
   identifiers. No verbatim phrases.
3. **Cloud → Reframing** — returns macro-context advisories
   ("audience is professional, high-stakes," "basin pressure elevated") —
   never directives.

---

## 3. Three-Layer Architecture

### 3.1 Layer 1 — Envelope (intimate, zero-judgment)

- **Purpose:** Allow the user to express anything — hard, sensitive,
  "inappropriate," messy — without judgment.
- **Behavior:** Captures raw text → produces structured but private
  representation.
- **Privacy:** Lives entirely on device. Raw text never exits.

### 3.2 Layer 2 — Transition (internal → external shift)

- **Purpose:** Detect when the user is moving from *just reflecting* to
  *I want to say this*.
- **Behavior:**
  - Recognizes externalization signals (explicit user mark or heuristic).
  - Builds an **ExpressionCandidate** object (still local).
  - Identifies **drift-risk flags** (too sharp, too soft, too emotional,
    too vague).
  - Derives **CloudMetadata** — the only structure permitted to cross
    the device boundary.
- **Privacy:** Candidate stays local. Only sanitized metadata goes up.

### 3.3 Layer 3 — Reframing (drift correction + user confirmation)

- **Purpose:** Help the user move from raw intention → clean expression
  that lands.
- **Behavior:**
  - Preserves the core intention (verified via `preserved_intent_score`).
  - Identifies likely tone / word misfires.
  - Produces 1–3 candidate reframings, each scored.
  - Presents to user with: "Here's how this will likely land. Here's a
    version that keeps your intention but is less likely to misfire.
    Does this still feel like what you mean?"
- **Privacy:** All choices remain with the user. No auto-send.

---

## 4. Schemas (canonical)

The single source of truth is `azimuth.py`. Every schema is a frozen
dataclass; every category is an enum. The Cloud privacy boundary is
enforced **structurally**: `CloudMetadata` deliberately omits every
field that could carry identifying or verbatim content.

### 4.1 EnvelopeState

```python
@dataclass(frozen=True)
class EnvelopeState:
    raw_text:                str                  # NEVER leaves the device
    captured_at:             datetime
    emotional_intensity:     IntensityLevel       # low|medium|high|extreme
    valence:                 Valence              # positive|negative|mixed|neutral|unknown
    pressure_level:          PressureLevel        # low|medium|high|critical
    rough_intention:         str                  # short, freeform
    user_marked_externalize: bool = False
    envelope_id:             str = <local uuid>   # local-only id
```

### 4.2 ExpressionCandidate

```python
@dataclass(frozen=True)
class ExpressionCandidate:
    raw_text:        str                  # still local; not uploaded
    intention:       str                  # preserved from envelope
    intention_class: IntentionClass       # vent|request|apologize|boundary|observation|gratitude|other
    pressure_level:  PressureLevel
    pressure_slope:  PressureSlope        # rising|flat|falling
    audience:        AudienceType         # self|one_to_one|small_group|public
    context:         ContextType          # personal|professional|high_stakes|low_stakes
    urgency:         UrgencyLevel         # low|medium|high
    risk_flags:      tuple[str, ...] = () # canonical names (see § 4.5)
    envelope_id:     str = ""             # local back-reference
    candidate_id:    str = <local uuid>   # local-only id
```

### 4.3 CloudMetadata — the only structure permitted to leave the device

```python
@dataclass(frozen=True)
class CloudMetadata:
    """PRIVACY GUARANTEE: NO raw_text, NO user_id, NO names,
    NO verbatim phrases, NO local ids. Only categorical metadata."""
    pressure_shape:  PressureShape        # ascending|descending|plateau|spike
    pressure_slope:  PressureSlope
    pressure_level:  PressureLevel
    audience_type:   AudienceType
    context_type:    ContextType
    urgency_level:   UrgencyLevel
    intention_class: IntentionClass
    risk_flags:      tuple[str, ...] = ()
    schema_version:  str = "azimuth.v1"
```

**Critical structural property:** `CloudMetadata.__dataclass_fields__` MUST
NOT include any of: `raw_text`, `user_id`, `envelope_id`, `candidate_id`,
`intention` (free-text), `rough_intention`. The test suite asserts this.

### 4.4 CloudAdvisory — returned by cloud

```python
@dataclass(frozen=True)
class CloudAdvisory:
    """Macro-context advisories. Never directives, never instructions."""
    basin_pressure:      PressureLevel
    macro_field_weather: str             # stable|mixed|turbulent|unknown
    audience_stake:      str             # low|medium|high
    advisories:          tuple[str, ...] = ()
    schema_version:      str = "azimuth.v1"
```

### 4.5 ReframedExpression

```python
@dataclass(frozen=True)
class ReframedExpression:
    original_intention:     str        # verbatim from envelope's rough_intention
    reframed_text:          str        # the candidate
    preserved_intent_score: float      # [0, 1] — higher is better
    drift_risk_after:       float      # [0, 1] — LOWER is better
    diff_notes:             tuple[str, ...] = ()   # human-readable diffs
    candidate_id:           str = ""
```

### 4.6 Canonical risk-flag set

```python
RISK_FLAGS_CANONICAL = (
    "sharp_tone",            # high intensity + non-self audience
    "soft_tone",             # too softened relative to stakes
    "high_pressure",         # high pressure + low context buffer
    "vague_target",          # vague intention + group audience
    "name_calling",          # accusatory language
    "all_or_nothing",        # absolutist either/or framing
    "urgency_inflation",     # urgency markers exceed actual urgency
    "passive_aggressive",    # indirect aggression markers
    "absolutist_language",   # "never", "always", "everyone"
    "ambiguous_request",     # ask not actionable
)
```

---

## 5. Layer Behaviors

### 5.1 Envelope

**`capture_envelope(raw_text, **hints) → EnvelopeState`**

- Computes `emotional_intensity` lexically (amplifier / softener markers).
- Computes `valence` lexically (positive / negative markers).
- Computes `pressure_level` from urgency / criticality markers.
- Extracts `rough_intention` heuristically (imperative verbs → "request";
  first-person past → "vent"; etc.).
- Generates local `envelope_id` (UUID-class).
- **Invariant:** no network call, no logging beyond local debug.

**`evaluate_envelope(env) → EnvelopeState`**

- Idempotent re-evaluation when heuristics update.
- Returns a NEW frozen object with the same `raw_text` + `envelope_id`
  but recomputed structural metadata.

**`mark_externalize(env) → EnvelopeState`**

- Flips `user_marked_externalize=True`. Returns a new frozen object.

### 5.2 Transition

**`detect_externalization_intent(env, recent_history=()) → bool`**

- True if `env.user_marked_externalize` OR raw_text contains
  externalization markers ("I want to tell them", "how should I say
  this", "should I send", "draft a message") OR recent_history shows
  escalating engagement.

**`build_candidate(env, *, audience, context, pressure_slope, urgency, intention_class) → ExpressionCandidate`**

- Derives audience from explicit hint OR session context default.
- Derives context similarly.
- Computes `pressure_slope` from recent envelope history.
- Classifies `intention_class` from `env.rough_intention` (heuristic).
- Calls `evaluate_drift_risk(candidate)` to populate `risk_flags`.

**`evaluate_drift_risk(candidate) → tuple[str, ...]`**

Returns a subset of `RISK_FLAGS_CANONICAL` based on:

| Condition                                                      | Flag                 |
|----------------------------------------------------------------|----------------------|
| intensity ∈ {HIGH, EXTREME} ∧ audience ≠ SELF                  | `sharp_tone`         |
| pressure ∈ {HIGH, CRITICAL} ∧ context ∈ {PROFESSIONAL, HIGH_STAKES} | `high_pressure`      |
| rough_intention is empty or single-word ∧ audience ∈ {SMALL_GROUP, PUBLIC} | `vague_target` |
| raw_text contains accusation markers ("you always", "you never") | `name_calling` + `absolutist_language` |
| urgency_marker count ≥ 3 but candidate.urgency < HIGH          | `urgency_inflation`  |
| intention_class = REQUEST ∧ no action verb in raw_text         | `ambiguous_request`  |
| context = HIGH_STAKES ∧ intensity = LOW                        | `soft_tone`          |

**`build_cloud_metadata(candidate) → CloudMetadata`**

- Drops `raw_text` entirely.
- Drops `envelope_id`, `candidate_id`, `intention` (free-text).
- Maps pressure trajectory + level → `pressure_shape`.
- Forwards canonical risk flags.
- Returns the structurally-private metadata.

### 5.3 Reframing

**`preserve_intent(candidate, advisory) → IntentSpec`**

Extracts:
- `intention_class` (from candidate)
- `target_action` (the verb / goal the user is pursuing)
- `target_state` (the state they want the listener to leave with)
- `must_preserve` (key concepts that MUST appear in any reframing — the
  intent invariant guard).

**`reframe_candidate(candidate, intent_spec, advisory, *, max_candidates=3) → list[ReframedExpression]`**

Applies tone-modulation rules:

| Rule input                                                    | Modulation                                         |
|---------------------------------------------------------------|----------------------------------------------------|
| `sharp_tone` flag, audience=ONE_TO_ONE                        | Soften amplifiers; keep stakes language verbatim   |
| `high_pressure` + context=PROFESSIONAL                        | De-escalate urgency markers; convert demands → asks |
| `name_calling` + `absolutist_language`                        | Reframe accusation → observation ("I observed…")    |
| `vague_target` + audience=SMALL_GROUP                         | Force one concrete target action in the reframing  |
| `urgency_inflation`                                           | Strip ≥2 of the inflated markers                   |
| `soft_tone` + context=HIGH_STAKES                             | Re-introduce stakes language                       |

For each generated reframing:
- Verify every `must_preserve` token appears (case-insensitive substring).
- Compute `(preserved_intent_score, drift_risk_after)` via
  `score_reframing`.
- Reject any candidate with `preserved_intent_score < 0.7`.

**`score_reframing(reframing, candidate) → (float, float)`**

- `preserved_intent_score`: fraction of `must_preserve` tokens present,
  adjusted for verb-class agreement.
- `drift_risk_after`: 0 + 0.15 × (# residual risk_flags re-detected on
  the reframed text, capped at 1.0).

**`run_azimuth_check(candidate, reframings) → AzimuthCheckPrompt`**

Returns a prompt with:
- `landing_prediction` — short narrative of how the original would likely land.
- `reframed_options` — the 1–3 reframings sorted by
  `preserved_intent_score` desc, then `drift_risk_after` asc.
- `user_question` — "Does this still feel like what you mean?"

User responses:
- `ACCEPT` → returns the chosen `ReframedExpression`.
- `TWEAK` → user edits manually; loops back through `reframe_candidate`.
- `REJECT` → stays in envelope (no externalization).

---

## 6. Interaction Flow

```
USER
  │  "I'm so done with this. They never listen and the deadline is moving again."
  ▼
ENVELOPE.capture_envelope(raw_text)
  ─► EnvelopeState(
        raw_text="I'm so done…",
        emotional_intensity=HIGH,
        valence=NEGATIVE,
        pressure_level=HIGH,
        rough_intention="vent + raise stakes",
        user_marked_externalize=False)
  │
  │  [user reflects locally; may stop here]
  │
  │  [user signals: "I want to bring this up in standup tomorrow"]
  ▼
ENVELOPE.mark_externalize(env)
  ─► EnvelopeState(…, user_marked_externalize=True)
  │
  ▼
TRANSITION.detect_externalization_intent(env)  →  True
  │
  ▼
TRANSITION.build_candidate(env, audience=SMALL_GROUP, context=PROFESSIONAL)
  ─► ExpressionCandidate(
        raw_text="…", intention="vent + raise stakes",
        intention_class=BOUNDARY,
        pressure_level=HIGH, pressure_slope=RISING,
        audience=SMALL_GROUP, context=PROFESSIONAL,
        urgency=MEDIUM,
        risk_flags=("sharp_tone","absolutist_language","high_pressure"))
  │
  ▼
TRANSITION.build_cloud_metadata(candidate)
  ─► CloudMetadata(
        pressure_shape=SPIKE, pressure_slope=RISING, pressure_level=HIGH,
        audience_type=SMALL_GROUP, context_type=PROFESSIONAL,
        urgency_level=MEDIUM,
        intention_class=BOUNDARY,
        risk_flags=("sharp_tone","absolutist_language","high_pressure"))
  │  ◀─── DEVICE → CLOUD BOUNDARY ───▶
  ▼
CLOUD.advise(metadata)
  ─► CloudAdvisory(
        basin_pressure=HIGH,
        macro_field_weather="turbulent",
        audience_stake="high",
        advisories=("audience_in_high_stakes_basin",
                    "professional_context_amplifies_absolutist_language"))
  │  ◀─── CLOUD → DEVICE ───▶
  ▼
REFRAMING.preserve_intent(candidate, advisory)
  ─► IntentSpec(
        intention_class=BOUNDARY,
        target_action="surface that the deadline change is unworkable",
        target_state="get the team to acknowledge + decide",
        must_preserve=("deadline","unworkable","decision needed"))
  │
  ▼
REFRAMING.reframe_candidate(candidate, intent_spec, advisory)
  ─► [
       ReframedExpression(
         original_intention="vent + raise stakes",
         reframed_text="The shifting deadline is reaching unworkable.
                        I want us to decide today: do we cut scope,
                        move the date, or escalate?",
         preserved_intent_score=0.88,
         drift_risk_after=0.14,
         diff_notes=("removed 'never listen'",
                     "softened opener",
                     "explicit decision request added")),
       ReframedExpression(
         original_intention="vent + raise stakes",
         reframed_text="I need to flag: the deadline change is more
                        than I can absorb. Can we talk through options?",
         preserved_intent_score=0.81,
         drift_risk_after=0.20,
         diff_notes=("converted accusation → I-statement",
                     "explicit ask added")),
     ]
  │
  ▼
REFRAMING.run_azimuth_check(candidate, reframings)
  ─► AzimuthCheckPrompt(
        landing_prediction="As written, this will likely read as a
                            blanket attack on the team. The deadline
                            concern will be lost.",
        reframed_options=(…),
        user_question="Does this still feel like what you mean?")
  │
  ▼
USER  ─►  ACCEPT  /  TWEAK  /  REJECT
            │           │           │
            │           │           └─► back to envelope (no externalization)
            │           └─► manual edit, re-run reframe_candidate
            └─► surface returns chosen ReframedExpression
                (user decides whether to send/say it)
```

---

## 7. Invariants (locked, must not be violated)

### 7.1 Privacy invariants

1. `EnvelopeState.raw_text` MUST NEVER serialize to network, file, or
   non-local storage.
2. `ExpressionCandidate.raw_text` MUST NEVER cross the device boundary.
3. Only `CloudMetadata` may be sent to cloud — and it carries no
   raw text, no user identifier, no local id, no names.
4. `CloudMetadata.__dataclass_fields__` is **structurally** enforced
   to contain only categorical / canonical fields (test-validated).

### 7.2 Intent invariants

5. The Reframing layer MUST preserve the user's `rough_intention`
   intent class (vent / request / apologize / boundary / observation /
   gratitude / other).
6. Any reframing accepted MUST have
   `preserved_intent_score ≥ 0.7` (default threshold).
7. All `must_preserve` tokens in `IntentSpec` MUST appear in the
   reframed text (case-insensitive substring match).

### 7.3 User-sovereignty invariants

8. The user can always stay in envelope (never forced to externalize).
9. The user can always reject all reframings (returns to envelope).
10. The user can always override (manual edit; no auto-send).
11. The system NEVER sends a message on the user's behalf — only the
    user does.

### 7.4 No-censorship invariants

12. The system does NOT block, censor, or refuse content.
13. The system MAY warn (`risk_flags`, drift predictions) — never
    prevent.
14. The reframing layer MUST always produce at least 1 option if the
    candidate is well-formed; if it cannot, the user falls back to
    sending raw (their choice).

---

## 8. Example Transformations

### 8.1 High pressure → safer expression

| Layer | Content |
|---|---|
| Envelope | "This is a disaster. I'm going to lose my mind if they don't fix it by Monday." |
| CloudMetadata | `{pressure_shape: SPIKE, pressure_level: HIGH, audience_type: PROFESSIONAL, intention_class: REQUEST, risk_flags: ("sharp_tone", "urgency_inflation")}` |
| Reframed | "This needs to land by Monday — the cost of slipping is high. What's the path?" |
| Preserved intent | Urgency conveyed · accountability preserved · no name-calling · explicit ask added |

### 8.2 Sensitive content → clearer framing

| Layer | Content |
|---|---|
| Envelope | "She acts like my time doesn't matter and I'm sick of it." |
| CloudMetadata | `{pressure_shape: ASCENDING, audience_type: ONE_TO_ONE, intention_class: BOUNDARY, risk_flags: ("name_calling", "absolutist_language")}` |
| Reframed | "I want to talk about how we schedule. The pattern this week left me feeling deprioritized." |
| Preserved intent | Boundary still set · observation language replaces accusation · scheduled the conversation |

### 8.3 Inappropriate impulse → honest non-destructive wording

| Layer | Content |
|---|---|
| Envelope | "I just want to tell him to f*** off." |
| CloudMetadata | `{pressure_shape: SPIKE, audience_type: ONE_TO_ONE, intention_class: BOUNDARY, risk_flags: ("sharp_tone", "name_calling")}` |
| Reframed | "I don't want to engage with this right now. I'll come back when I can be useful." |
| Preserved intent | Refusal preserved · exit ramp provided · door not slammed |

### 8.4 Vague intention → concrete ask

| Layer | Content |
|---|---|
| Envelope | "Things at work are weird, idk." |
| CloudMetadata | `{pressure_shape: PLATEAU, audience_type: ONE_TO_ONE, intention_class: OTHER, risk_flags: ("vague_target",)}` |
| Reframed | "I'm not settled about how the project is going. Can we walk through where you and I see it differently?" |
| Preserved intent | Discomfort surfaced · target named (project) · action proposed |

---

## 9. Integration Points

| Surface | Integration |
|---|---|
| **Web Intelligence Panel** (Phase 3 Unit 2) | Adds an Azimuth Check section when user explicitly requests "how would this land?". Reads via in-process function call (same host). |
| **Phone Intelligence Panel** (Phase 3 Unit 3) | Same surface, mobile-optimized. |
| **Cloud Gateway** (Phase 3 Unit 4+) | Exposes `POST /azimuth/advise` endpoint that accepts `CloudMetadata` and returns `CloudAdvisory`. NEVER accepts raw text. |

The cloud endpoint is the only crossing point; everything else runs on-device.

---

## 10. Module Inventory

```
azimuth.py                          ── shared schemas + enums + canonical sets
azimuth_envelope.py                 ── Track 1: Envelope layer (skeleton)
azimuth_transition.py               ── Track 1: Transition + Cloud metadata (skeleton)
azimuth_reframing.py                ── Track 2: Reframing + Azimuth Check (skeleton)
tests/test_azimuth_schemas.py       ── structural tests (privacy contract enforced)
```

---

## 11. Phase Plan

| Phase | Scope | Status |
|---|---|---|
| **This commit** | Spec + schemas + skeletons + structural tests | **Shipping now** |
| Phase 3 Unit 5 | `azimuth_envelope.py` + `azimuth_transition.py` real impl + behavior tests | Deferred |
| Phase 3 Unit 6 | `azimuth_reframing.py` real impl + reframing test corpus | Deferred |
| Phase 3 Unit 7 | Cloud `/azimuth/advise` endpoint + Web/Phone panel wiring | Deferred |

---

## 12. Test Discipline

The Phase-1 structural test suite (`tests/test_azimuth_schemas.py`)
asserts the privacy contract **directly on the dataclass field set**:

- `CloudMetadata.__dataclass_fields__` contains exactly the canonical
  categorical fields and nothing else.
- `raw_text`, `user_id`, `envelope_id`, `candidate_id`, `intention`,
  `rough_intention` are **structurally absent** from `CloudMetadata`.
- Any future PR that adds a free-text field to `CloudMetadata` is
  rejected by the test suite — the privacy boundary is enforced by code,
  not just by convention.
