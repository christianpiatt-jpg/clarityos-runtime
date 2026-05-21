---
name: clarity-narrative-spine-builder
description: >
  Extract the narrative spine from any document by identifying the core actors
  (protagonist, antagonist, institutional roles), the central conflict and stakes,
  the causal chain, the institutional posture, and the narrative frame. Use when
  asked to map, build, extract, or expose the underlying narrative structure of
  a document, set of documents, or transcript.
category: Narrative Analysis
capabilities:
  - Identify protagonist, antagonist, and institutional actors with their roles
  - Extract the core conflict and the stakes for each actor
  - Identify the narrative frame and any nested subframes
  - Identify omissions, distortions, and selective framing in the text
  - Produce a compressed narrative spine the operator can hold in working memory
  - Provide a structural map that downstream analysis can hang from
limitations:
  - Does not perform legal reasoning, doctrinal analysis, or burden mapping
  - Does not extract or classify contradictions
  - Does not build timelines or normalize dates
  - Does not generate full briefs or rewrite source documents
input_shape: >
  Document, set of documents, or transcript — any source from which actors, conflicts, and institutional posture can be read.
output_shape: >
  Compressed structural map with sections: Actors, Conflict & Stakes, Causal Chain, Institutional Posture, Frame, and Omissions / Distortions / Selective Framing.
dependencies: []
governance_version: 1.1.0
---

# Clarity Narrative Spine Builder

## Purpose
Extract the narrative spine from any document, set of documents, or
transcript. Output is a compressed structural map: who the actors are, what
the central conflict is, what is at stake, how the causal chain runs, what
institutional posture frames the narrative, and what the narrative is trying
to make the reader believe — or not notice. The spine is general-purpose
scaffolding that more specialized methods (legal reasoning, evidence
extraction, timeline construction, summarization) can build on.

## Category Justification
This skill operates on the structure, framing, identity threads, and
institutional behavior patterns of a document — extracting a structural
reading that exposes how the narrative is assembled and what it foregrounds
versus omits.

This skill belongs to the **Narrative Analysis** category because its
primary output is a structural reading — a narrative spine that maps actors,
conflict, stakes, frame, and omissions. See `SKILL_TAXONOMY.md` § A for the
category definition.

This skill is the second skill in Narrative Analysis. It is distinguished
from `clarity-narrative-litigation` (also Narrative Analysis) by primary
output: that skill applies narrative-architecture specifically to legal
documents and produces an opposition outline with leverage points; this
skill produces the general-purpose narrative spine first, which any
downstream method — including `clarity-narrative-litigation` — can build
from.

## Boundary Statement

This skill **does not**:

- Perform legal reasoning, doctrinal analysis, or element/burden mapping; for that see Legal Reasoning skills (e.g., `clarity-legal-argument-mapper`).
- Extract or classify contradictions; for that see Evidence Extraction skills (e.g., `clarity-contradictions-extractor`).
- Build timelines or normalize dates; for that see Timeline Construction skills (e.g., `clarity-timeline-mapper`).
- Generate full briefs or rewrite source documents; output is a compressed structural map only.

For methods that fall outside the boundary above, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md` to find
the right category.

## Instructions

### 1. Read the Source in Full
- Read the document, set of documents, or transcript end to end.
- Identify the document type (filing, report, transcript, news article, multi-source set).
- Identify the implied or explicit audience (court, regulator, public, internal stakeholder, individual operator).

### 2. Identify the Actors
- **Protagonist** — the actor the narrative centers on or asks the reader to side with.
- **Antagonist** — the actor positioned in opposition.
- **Institutional actors** — agencies, organizations, courts, or systems that act on or constrain the protagonist or antagonist.
- For each actor, note their stated role, their actual role in the events, and any gap between the two.

### 3. Extract the Core Conflict and Stakes
- State the central conflict in one or two sentences.
- For each actor, identify what they stand to gain or lose.
- Distinguish material stakes (money, position, liberty) from positional stakes (precedent, reputation, framing power).

### 4. Map the Causal Chain
- Identify the precipitating event(s).
- Trace the chain of actions, reactions, and decisions the document asserts.
- Note where the chain has gaps — steps the document skips, or steps it asserts without warrant.

### 5. Identify Institutional Posture
- For each institutional actor, identify their posture: enforcing, deferring, escalating, deflecting, internalizing, or disclaiming.
- Note discrepancies between an institution's stated posture and its actions in the document.

### 6. Extract the Narrative Frame and Subframes
- The **frame** is the lens the document asks the reader to use (e.g., "this is a procedural failure", "this is an integrity issue", "this is routine").
- Identify any **subframes** that nest inside the main frame (e.g., a procedural-failure frame containing a personality-conflict subframe).
- Name the frame in 3–7 words.

### 7. Identify Omissions, Distortions, and Selective Framing
- **Omissions** — facts a reasonable reader would expect that the document doesn't address.
- **Distortions** — facts the document includes but characterizes in ways the underlying material doesn't support.
- **Selective framing** — accurate facts presented in ways that systematically favor one actor's reading.
- For each, note where in the document the issue appears and what is missing or mischaracterized.

### 8. Produce the Narrative Spine
- Output a compressed structural map with sections: **Actors**, **Conflict & Stakes**, **Causal Chain**, **Institutional Posture**, **Frame**, **Omissions / Distortions / Selective Framing**.
- Total length proportional to source complexity but always shorter than the source.
- Use declarative, compressed language. The spine is scaffolding, not narrative prose.

### 9. Quality Check
- Verify every claim in the spine traces back to the source.
- Confirm the spine compresses without inventing.
- Confirm no embedded PII or case-specific tokens leaked from the source.

## Example Input
"Build the narrative spine of this internal agency report."

## Example Output

**Actors**
- Protagonist: [stated role / actual role / gap]
- Antagonist: [stated role / actual role / gap]
- Institutional: [agency / court / system, with each actor's role]

**Conflict & Stakes**
- Conflict: [1–2 sentence statement]
- Stakes: [per-actor material and positional stakes]

**Causal Chain**
1. [Precipitating event]
2. [Action / reaction]
3. [Decision]
4. [...]
- Gaps: [skipped or asserted-without-warrant steps]

**Institutional Posture**
- [Actor]: [posture] — [stated vs. acted]
- [Actor]: [posture] — [stated vs. acted]

**Frame**
- Main: [3–7 word name]
- Subframes: [any nested frames]

**Omissions / Distortions / Selective Framing**
- Omission: [what is missing] — [where the gap appears]
- Distortion: [what is mischaracterized] — [where in the text]
- Selective framing: [pattern] — [evidence in the text]

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
