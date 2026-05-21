---
name: clarity-temporal-event-normalizer
description: >
  Normalize, canonicalize, and align temporal expressions into structured,
  machine-usable event timestamps for downstream timeline reasoning. Use when
  asked to extract, normalize, canonicalize, or structure temporal data from
  freeform text into ISO 8601 form.
category: Timeline Construction
capabilities:
  - Extract temporal expressions from freeform text
  - Normalize dates and times to canonical ISO 8601 form
  - Handle ranges, vague expressions, and missing components per documented rules
  - Score per-event confidence reflecting normalization certainty
  - Produce deterministically ordered structured output (JSON array)
  - Emit machine-usable timestamps suitable for downstream timeline reasoning
limitations:
  - Does not infer dates from semantic context beyond what the text states or strongly implies
  - Does not resolve unanchored relative expressions (e.g., "recently", "next week") without an anchor date
  - Does not extract contradictions, causality, or evidence anchors (those are sibling skills)
  - Does not build chronological timelines from events — output is normalized atomic events only
input_shape: >
  Freeform text containing events, dates, times, ranges, or ambiguous temporal expressions.
output_shape: >
  JSON array of normalized event objects:
    - event_id (string, "evt-NNN")
    - canonical_timestamp (ISO 8601 or null)
    - temporal_expression (verbatim source text)
    - confidence (float 0.0-1.0)
dependencies: []
governance_version: 1.1.0
---

# Clarity Temporal Event Normalizer

## Purpose
Convert ambiguous or natural-language temporal expressions in freeform text
into canonical ISO 8601 timestamps. The output is a deterministic,
machine-usable structure — an array of normalized event objects — that
downstream timeline reasoning can consume directly.

Output is **atomic** (one object per temporal expression) and does **not**
assemble events into a timeline. Timeline assembly is the job of the
sibling Timeline Construction skill, `clarity-timeline-mapper`. This skill
produces the normalized substrate from which timelines are built.

## Category Justification
This skill operates on dates, times, ranges, and temporal expressions —
extracting them from text and normalizing them to canonical, machine-usable
form. Its primary output is a structured set of normalized atomic events
with per-event confidence.

This skill belongs to the **Timeline Construction** category because its
primary output is the building block of a timeline — normalized atomic
events with canonical timestamps. See `SKILL_TAXONOMY.md` § A for the
category definition.

This skill is the second in Timeline Construction. It is distinguished
from `clarity-timeline-mapper` (also Timeline Construction) by primary
output: that skill **builds chronologies** (ordered event lists with gap
and conflict identification across multiple events); this skill produces
**normalized atomic events** with canonical timestamps and per-event
confidence — the raw normalized substrate that timeline assembly can
consume.

## Boundary Statement

This skill **does not**:

- Build chronologies, infer event ordering across documents, or flag temporal contradictions; for that see `clarity-timeline-mapper`.
- Extract evidence anchors, contradictions, or argument structure; for those see Evidence Extraction and Legal Reasoning skills.
- Infer dates from semantic context not stated or strongly implied in the text.
- Resolve unanchored relative expressions ("recently", "soon", "next week") without an explicit or implied anchor date — these emit `null` timestamps with `confidence: 0.0`.

For methods that fall outside the boundary above, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md`.

## Method

### 1. Extract Temporal Expressions
- Scan the text for any expression with temporal content: explicit dates ("March 14, 2021"), times ("14:32"), ranges ("between Q1 and Q3"), relative expressions ("two weeks later"), vague expressions ("around mid-2020"), and partial dates ("in 2019").
- Capture each expression verbatim along with its position in the source.

### 2. Normalize to ISO 8601
Apply these rules in order:

- **Full date**: `YYYY-MM-DD`. Example: "March 14, 2021" → `2021-03-14`.
- **Full date + time**: `YYYY-MM-DDTHH:MM:SS` (24h). Example: "March 14, 2021 at 2:32pm" → `2021-03-14T14:32:00`.
- **Full date + time + zone**: append zone designator. Example: "2pm EST on March 14, 2021" → `2021-03-14T14:00:00-05:00`.
- **Year only**: `YYYY`. Example: "in 2019" → `2019`.
- **Year-month only**: `YYYY-MM`. Example: "March 2021" → `2021-03`.
- **Quarter**: map to start month (note coarse precision in confidence). Example: "Q1 2021" → `2021-01`.
- **Range**: emit as **two** event objects with related `event_id`s sharing a prefix, marking start and end. The same `temporal_expression` appears in both objects.

### 3. Handle Ranges, Vague Expressions, and Missing Components
- **Ranges** ("between March and June 2021") → two events with start and end timestamps; confidence reflects bounded precision of each endpoint.
- **Vague** ("around mid-2020") → best-estimate timestamp (e.g., `2020-06`) with reduced confidence (≤0.5).
- **Missing components** ("the 14th") → `null` timestamp if no anchor is available; record verbatim expression. If anchor is available from prior context, use it and mark confidence accordingly.
- **Relative without anchor** ("recently", "later that week" with no week reference) → `null` timestamp, `confidence: 0.0`.

### 4. Confidence Scoring
- **1.0** — fully specified, unambiguous (full date + time + zone).
- **0.8–0.95** — fully specified date or date+time without explicit zone.
- **0.5–0.7** — coarse precision (year-only, quarter, month-only).
- **0.2–0.4** — vague or estimated (e.g., "around mid-2020", "early 2019").
- **0.0** — unanchored relative expression with `null` timestamp.

### 5. Deterministic Ordering
- Order the output array by `canonical_timestamp` ascending.
- `null` timestamps sort to the end.
- Tie-break (equal non-null timestamps OR all-null) by source-position: first occurrence in input first.

## Output Contract

The output is a **JSON array of event objects**. Every object MUST have all
four fields with the types and shapes below — no extra fields, no missing
fields.

```json
[
  {
    "event_id": "evt-001",
    "canonical_timestamp": "2021-03-14",
    "temporal_expression": "March 14, 2021",
    "confidence": 1.0
  },
  {
    "event_id": "evt-002",
    "canonical_timestamp": null,
    "temporal_expression": "recently",
    "confidence": 0.0
  }
]
```

Field rules:

- `event_id` — string of the form `"evt-NNN"` (zero-padded 3-digit), assigned in deterministic source-encounter order before sorting. After sorting, `event_id`s remain attached to their objects (so the array order may not match `event_id` order, by design).
- `canonical_timestamp` — ISO 8601 string or `null`. ISO 8601 may be year-only (`"2019"`), year-month (`"2021-03"`), full date (`"2021-03-14"`), date+time (`"2021-03-14T14:32:00"`), or date+time+zone (`"2021-03-14T14:32:00-05:00"`).
- `temporal_expression` — original verbatim text from the source, **not paraphrased**, **not truncated**.
- `confidence` — float in `[0.0, 1.0]`. Scored per § 4 of Method.

The output MUST be a single JSON array — not an object containing an array,
not a sequence of objects. Downstream consumers (e.g.,
`clarity-timeline-mapper`) parse this contract directly.

## Example Input
"Smith was hired in March 2021 and left around mid-2023. The hearing was
held on July 4 at 9 AM EDT, and a follow-up call happened recently."

## Example Output
```json
[
  {
    "event_id": "evt-001",
    "canonical_timestamp": "2021-03",
    "temporal_expression": "March 2021",
    "confidence": 0.6
  },
  {
    "event_id": "evt-002",
    "canonical_timestamp": "2023-06",
    "temporal_expression": "around mid-2023",
    "confidence": 0.4
  },
  {
    "event_id": "evt-003",
    "canonical_timestamp": null,
    "temporal_expression": "July 4 at 9 AM EDT",
    "confidence": 0.3
  },
  {
    "event_id": "evt-004",
    "canonical_timestamp": null,
    "temporal_expression": "recently",
    "confidence": 0.0
  }
]
```

`evt-003` carries `null` because the source supplies month/day/time/zone
but no year and no anchor; confidence is reduced to reflect partial
specificity. `evt-004` is unanchored and emits `null` with `confidence: 0.0`.

## Governance Compliance Checklist

Before this skill is committed:

- [ ] `category` matches a row in `SKILL_TAXONOMY.md` § A.
- [ ] `capabilities` and `limitations` lists are non-empty.
- [ ] `governance_version` matches the current governance layer
      version recorded for skills (`1.1.0` as of this template).
- [ ] `name` is lowercase, hyphens only, and matches the filename.
- [ ] `description` contains explicit trigger phrases.
- [ ] No PII; no Layer 2 case material.
- [ ] File under 10 MB.
- [ ] `SKILL.md` at the root of the upload zip; byte-identical to
      this `.md`.
- [ ] Manifest entry under schema 1.2.0 includes all required fields plus
      additive `input_shape`, `output_shape`, `dependencies`.
- [ ] `baseline_hash` (in manifest entry) is set to the SHA256 of this
      `.md` at first commit and frozen thereafter.
- [ ] Drift Detector returns `DRIFT: NONE` after baseline regeneration.
- [ ] Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.
