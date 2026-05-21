---
name: clarity-summarization-contrastive-brief
description: >
  Produces contrastive legal briefs that summarize the record while explicitly
  surfacing points of agreement, disagreement, and evidentiary gaps between
  parties. Use when asked to brief, summarize, contrast, compare, or surface
  disagreements across a multi-document or multi-party legal record.
category: Summarization
capabilities:
  - Generate structured summaries of multi-document legal records
  - Highlight agreements, disagreements, and unresolved issues between positions
  - Align summary sections to evidence anchors and timeline references when present
  - Produce operator-ready briefs with clear sectioning and labels
  - Distinguish what the parties share, what they dispute, and what neither has supported
limitations:
  - Does not invent facts; constrained to the provided record
  - Does not perform novel legal reasoning beyond structuring and contrast
  - Does not resolve factual disputes; only surfaces and organizes them
  - Quality depends on upstream node / edge extraction and orientation quality (e.g., evidence anchors, contradictions, precedents from sibling skills)
input_shape: >
  Multi-document legal record (pleadings, evidence summaries, testimony excerpts) plus, optionally, explicit party positions or issues lists.
output_shape: >
  JSON object with:
    - sections: array of {title, body}
    - agreements: array of {issue, supporting_nodes}
    - disagreements: array of {issue, conflicting_nodes}
    - gaps: array of {issue, missing_information_description}
dependencies: []
governance_version: 1.1.0
---

# Clarity Summarization Contrastive Brief

## Purpose
Produce a contrastive brief that compresses a multi-document or multi-party
legal record while preserving the **structure of disagreement**. Output is
operator-ready: a sectioned narrative summary plus three explicit blocks —
agreements, disagreements, and evidentiary gaps — keyed by issue. The brief
is decision-ready in two senses: it shows what the record establishes, and
it shows where the record is silent or in conflict.

The skill is **extractive and organizing** — it surfaces and structures
what the record contains, without imposing legal interpretation or
inventing material the record does not provide.

## Category Justification
This skill compresses a multi-document record into a decision-ready
structured summary. Its primary output is a single JSON object that
holds both the narrative summary and the contrastive analysis (agreements
/ disagreements / gaps).

This skill belongs to the **Summarization** category because its primary
output is a structured summary of the record — compressed, sectioned, and
preserving the structure of disagreement. See `SKILL_TAXONOMY.md` § A.

This skill is the second in Summarization. It is distinguished from
`clarity-operator-brief-structurer` (also Summarization) by primary
output: that skill produces a **single-perspective operator brief** in
the fixed Situation / Assessment / Key Points / Recommended Actions
structure (output: one stream of compressed analysis to a decision-maker);
this skill produces a **multi-position contrastive brief** that
explicitly surfaces where parties agree, disagree, and have gaps in the
record (output: structured object with agreements / disagreements / gaps
blocks). Use the operator brief when you need one decision-ready stream;
use the contrastive brief when you need to see where the record holds
together and where it splits.

## Boundary Statement

This skill **does not**:

- Invent facts. The brief is bounded by the provided record. Issues, parties, positions, and supporting material must come from the record (or upstream skill outputs that came from the record).
- Perform novel legal reasoning, apply doctrines to facts, or weigh authority. For doctrinal work see Legal Reasoning skills (`clarity-legal-argument-mapper`, `clarity-legal-precedent-extractor`).
- Resolve factual disputes. The contrastive blocks **surface and organize** disputes; they do not adjudicate them.
- Extract precedents, contradictions, evidence anchors, or timelines as primary outputs. Those are sibling skills; this brief consumes their outputs when available.
- Generate a Situation / Assessment / Key Points / Recommended Actions brief. For that single-perspective shape see `clarity-operator-brief-structurer`.

For methods that fall outside this boundary, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md`.

## Method

The method has three passes over the record:

1. **Decomposition** — read the record, identify the parties and their
   stated positions, and enumerate the discrete issues the record places
   in dispute or in agreement. Each issue becomes a row that the brief
   will resolve into one of three buckets: agreement, disagreement, or
   gap.

2. **Per-issue resolution** — for each issue, identify:
   - **Supporting nodes** when both parties (or all positions) endorse
     the same factual or legal proposition. Nodes are record items —
     evidence anchors, paragraphs of pleadings, testimony excerpts,
     precedent citations — that any sibling extractor would have surfaced
     from the same record.
   - **Conflicting nodes** when parties endorse incompatible propositions
     on the same issue. The brief records both (or all) sides.
   - **Missing information** when the record contains the issue but no
     party has supplied factual or doctrinal support — these become gap
     entries.

3. **Composition** — assemble:
   - A `sections` array of narrative summary blocks (typically:
     Background, Procedural Posture, Disputed Facts, Disputed Legal
     Issues, Common Ground, Open Questions). Sections compress the
     record; they do not duplicate the contrastive blocks below.
   - An `agreements` array, one entry per shared issue, listing the
     supporting nodes from the record.
   - A `disagreements` array, one entry per disputed issue, listing the
     conflicting nodes from each side.
   - A `gaps` array, one entry per under-supported issue, with a short
     description of what the record is missing.

Output is a single JSON object — see the Output Contract below.

## Instructions

### 1. Read the Record in Full
- Read every document in the record end to end.
- Note the document type for each (pleading, declaration, exhibit, transcript, decision).
- Identify the procedural posture and the forum.

### 2. Identify Parties and Positions
- List the parties (plaintiff, defendant, intervenor, agency, etc.).
- For each, note the position(s) they advance — explicit (stated) and implicit (inferable from filings).
- If the record names amici or third parties whose positions matter, include them as positions.

### 3. Enumerate Issues
- List every discrete issue the record places in dispute or in clear agreement.
- Number each issue for cross-reference in later sections.
- For each issue, note whether it appears central or peripheral to the relief sought.

### 4. Resolve Each Issue into a Bucket
For each numbered issue, determine which bucket applies:

- **Agreement** — all positions endorse the same proposition. Capture the supporting nodes (record items) that establish the agreement.
- **Disagreement** — positions diverge. Capture the conflicting nodes from each side.
- **Gap** — the issue is in the record but no position has provided support, or the support is materially incomplete. Describe what is missing.

An issue may appear in two buckets (e.g., parties agree on Element 1 but disagree on Element 2 of the same legal test). In that case, split it into sub-issues.

### 5. Compose the Sections Array
- Decide which narrative sections the brief needs (typically: Background, Procedural Posture, Disputed Facts, Common Ground, Disputed Legal Issues, Open Questions).
- For each section, write a compressed summary that draws from the record and from upstream skill outputs (anchors, contradictions, precedents) when those are provided as input.
- Section bodies are operator-grade: declarative, compressed, no hedging filler.

### 6. Emit the Contrastive Blocks
- Build the `agreements` array, one entry per agreement-bucket issue.
- Build the `disagreements` array, one entry per disagreement-bucket issue.
- Build the `gaps` array, one entry per gap-bucket issue.
- For agreements and disagreements, include `supporting_nodes` / `conflicting_nodes` arrays — short references to record items (e.g., "Decl. of A ¶ 7", "Pl. Br. § II.A", "Anderson v. Liberty Lobby, 477 U.S. 242").

### 7. Quality Check
- Verify every claim in `sections` traces back to a record item or upstream skill output.
- Verify every `supporting_nodes` / `conflicting_nodes` reference is grounded in the record.
- Confirm no PII or Layer 2 case-specific tokens leaked from the source into framing language.
- Confirm the JSON parses and matches the Output Contract.

## Output Contract

The output is a **single JSON object** with exactly four top-level keys:
`sections`, `agreements`, `disagreements`, `gaps`. No extra keys.

```json
{
  "sections": [
    { "title": "Background", "body": "..." },
    { "title": "Procedural Posture", "body": "..." }
  ],
  "agreements": [
    {
      "issue": "Plaintiff was hired in 2019",
      "supporting_nodes": ["Compl. ¶ 12", "Ans. ¶ 12", "Decl. of A ¶ 3"]
    }
  ],
  "disagreements": [
    {
      "issue": "Reason for termination",
      "conflicting_nodes": [
        "Pl.: Decl. of A ¶ 14 (alleges retaliation)",
        "Def.: Decl. of B ¶ 8 (cites performance)"
      ]
    }
  ],
  "gaps": [
    {
      "issue": "Causation between protected activity and termination",
      "missing_information_description": "Neither side cites contemporaneous correspondence between the alleged protected activity and the termination decision."
    }
  ]
}
```

Field rules:

- `sections` — array of objects with exactly two string fields: `title` and `body`. Required, may be empty if the brief is purely contrastive (rare).
- `agreements` — array of objects with `issue` (string) and `supporting_nodes` (array of strings). May be empty.
- `disagreements` — array of objects with `issue` (string) and `conflicting_nodes` (array of strings). Each conflicting node should identify the position it represents (e.g., "Pl.:", "Def.:") and the record reference. May be empty.
- `gaps` — array of objects with `issue` (string) and `missing_information_description` (string). May be empty.

The output MUST be a single JSON object — not an array, not multiple
objects. Downstream consumers parse this contract directly.

## Example Input
"Summarize the record in this case [hypothetical multi-party employment
matter]: complaint, answer, two declarations, three exhibits. Surface
agreements, disagreements, and evidentiary gaps between the parties."

## Example Output
```json
{
  "sections": [
    {
      "title": "Background",
      "body": "Plaintiff alleges termination in retaliation for protected activity in 2023. Defendant asserts performance-based termination."
    },
    {
      "title": "Procedural Posture",
      "body": "Cross-motions for summary judgment pending; discovery closed."
    },
    {
      "title": "Disputed Facts",
      "body": "Reason for termination is the central factual dispute. Both sides agree on hiring date, position, and termination date."
    },
    {
      "title": "Common Ground",
      "body": "Plaintiff was hired in 2019 to a named position; was terminated in 2023; engaged in some workplace activity that defendant acknowledges."
    },
    {
      "title": "Open Questions",
      "body": "Causation between protected activity and termination is unresolved on the current record."
    }
  ],
  "agreements": [
    {
      "issue": "Plaintiff was hired in 2019",
      "supporting_nodes": ["Compl. ¶ 12", "Ans. ¶ 12", "Decl. of A ¶ 3"]
    },
    {
      "issue": "Plaintiff was terminated in 2023",
      "supporting_nodes": ["Compl. ¶ 18", "Ans. ¶ 18"]
    }
  ],
  "disagreements": [
    {
      "issue": "Reason for termination",
      "conflicting_nodes": [
        "Pl.: Decl. of A ¶ 14 (alleges retaliation)",
        "Def.: Decl. of B ¶ 8 (cites performance)"
      ]
    },
    {
      "issue": "Whether plaintiff's activity qualified as protected",
      "conflicting_nodes": [
        "Pl.: Pl. Br. § II.A (statutory interpretation)",
        "Def.: Def. Br. § III.B (narrower reading)"
      ]
    }
  ],
  "gaps": [
    {
      "issue": "Causation between protected activity and termination",
      "missing_information_description": "Neither side cites contemporaneous correspondence between the alleged protected activity and the termination decision."
    }
  ]
}
```

## Governance Compliance Checklist

Before this skill is committed:

- [ ] `category` matches a row in `SKILL_TAXONOMY.md` § A.
- [ ] `capabilities` and `limitations` lists are non-empty.
- [ ] `governance_version` matches the current governance layer version recorded for skills (`1.1.0`).
- [ ] `name` is lowercase, hyphens only, and matches the filename.
- [ ] `description` contains explicit trigger phrases.
- [ ] No PII; no Layer 2 case material.
- [ ] File under 10 MB.
- [ ] `SKILL.md` at the root of the upload zip; byte-identical to this `.md`.
- [ ] Manifest entry under schema 1.2.0 includes all required fields plus additive `input_shape`, `output_shape`, `dependencies`.
- [ ] `baseline_hash` (in manifest entry only) is set to the SHA256 of this `.md` at first commit and frozen thereafter.
- [ ] Drift Detector returns `DRIFT: NONE` after baseline regeneration.
- [ ] Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.
