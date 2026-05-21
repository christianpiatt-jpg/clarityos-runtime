---
name: clarity-operator-brief-structurer
description: >
  Convert complex documents, transcripts, filings, or multi-source inputs into
  operator-grade briefs with a fixed four-part structure (Situation, Assessment,
  Key Points, Recommended Actions). Use when asked to summarize, brief, structure,
  or compress a document into a decision-ready format.
category: Summarization
capabilities:
  - Extract the core situation from complex input
  - Identify key facts ranked by decision impact
  - Identify operator-relevant signals and uncertainties
  - Produce a structured brief in the fixed Situation / Assessment / Key Points / Recommended Actions format
  - Maintain clarity and compression — output is always shorter than the source
limitations:
  - Does not perform legal analysis or apply legal standards to facts
  - Does not extract or classify contradictions
  - Does not build timelines or normalize dates
  - Does not rewrite source documents verbatim or beyond fair-use length
input_shape: >
  Complex document, transcript, filing, or multi-source input that the operator needs in compressed decision-ready form.
output_shape: >
  Operator-grade brief in fixed four-part structure: Situation, Assessment, Key Points, Recommended Actions.
dependencies: []
governance_version: 1.1.0
---

# Clarity Operator Brief Structurer

## Purpose
Convert complex documents, transcripts, filings, or multi-source inputs into
operator-grade briefs with a fixed four-part structure (Situation → Assessment
→ Key Points → Recommended Actions). Output is decision-ready, compressed, and
faithful to the source.

## Category Justification
This skill produces a structured summary that compresses a document into a
decision-ready format while preserving the source's claims and structure.

This skill belongs to the **Summarization** category because its primary
output is a four-section operator brief that compresses a document into
decision-ready form. See `SKILL_TAXONOMY.md` § A for the category definition.

## Boundary Statement

This skill **does not**:

- Perform legal analysis or apply legal standards to facts; for legal reasoning, see Legal Reasoning skills.
- Extract or classify contradictions; for that, see Evidence Extraction skills (e.g., `clarity-contradictions-extractor`).
- Build timelines or normalize dates; for that, see Timeline Construction skills (e.g., `clarity-timeline-mapper`).
- Reproduce source text verbatim or beyond fair-use length; output is always compressed and original.

For methods that fall outside the boundary above, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md` to find
the right category.

## Instructions

### 1. Ingest the Source Material
- Read the document, transcript, or set of inputs in full.
- Identify the document type (filing, report, transcript, multi-source set).
- Identify the operator's likely decision context, explicit or implied.

### 2. Extract the Situation
- Capture the core fact pattern in 2–4 sentences.
- Identify the actors, the timeline anchor, and the trigger that makes this a situation now.
- Strip background detail that does not bear on the current decision.

### 3. Form the Assessment
- State the operator-relevant interpretation of the situation.
- Identify the structural shape (escalating, stalled, resolving, forking).
- Note critical uncertainties and what would resolve them.

### 4. Identify Key Points
- List 3–7 facts the operator must hold in mind.
- Each point one sentence; rank by decision impact.
- Distinguish hard facts from inferences; flag inferences explicitly.

### 5. Recommend Actions
- Propose 2–5 actions, ordered by urgency or dependency.
- Each recommendation should connect to a Key Point or address an uncertainty.
- Note dependencies and prerequisites between actions.

### 6. Compose the Brief
- Output four labelled sections: **Situation**, **Assessment**, **Key Points**, **Recommended Actions**.
- Total length proportional to source complexity but always shorter than the source.
- Operator-grade language: declarative, compressed, no hedging filler.

### 7. Quality Check
- Verify every claim in the brief traces back to the source.
- Confirm the four sections are non-redundant (no claim appears in two sections).
- Confirm no embedded PII or case-specific tokens leaked from the source.

## Example Input
"Summarize this 40-page agency report into an operator brief I can read before
the 9 AM meeting."

## Example Output

**Situation**  
[2–4 sentence fact pattern with actors, timeline anchor, and current trigger]

**Assessment**  
[Operator-relevant interpretation, structural shape, critical uncertainties]

**Key Points**
1. [Decision-impact-ranked fact]
2. [Decision-impact-ranked fact]
3. [Decision-impact-ranked fact]

**Recommended Actions**
1. [Urgency-ordered action with prerequisite note if any]
2. [Urgency-ordered action with prerequisite note if any]

## Governance Compliance Checklist

Before this skill is committed:

- [ ] `category` matches a row in `SKILL_TAXONOMY.md` § A.
- [ ] `capabilities` and `limitations` lists are non-empty.
- [ ] `governance_version` matches the current governance layer
      version (`1.1.0` as of this template).
- [ ] `name` is lowercase, hyphens only, and matches the filename.
- [ ] `description` contains explicit trigger phrases.
- [ ] No PII; no Layer 2 case material.
- [ ] File under 10 MB.
- [ ] `SKILL.md` at the root of the upload zip; byte-identical to
      this `.md`.
- [ ] Manifest entry under schema 1.2.0 includes `category`,
      `capabilities`, `limitations`, `governance_version`, and
      `baseline_hash` (the SHA256 of this `.md` at first commit).
- [ ] Drift Detector returns `DRIFT: NONE` after baseline regeneration.
- [ ] Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.
