---
name: clarity-evidence-anchor-extractor
description: >
  Identify, extract, and classify evidence anchors from any document. Evidence
  anchors include factual assertions, citations, exhibits, record references,
  data points, and witness statements — any text that functions as evidentiary
  support. Use when asked to extract, list, classify, anchor, table, or map
  the evidence in a document.
category: Evidence Extraction
capabilities:
  - Identify factual assertions and evidentiary statements
  - Extract citations, exhibits, and record references
  - Classify evidence anchors by type (fact, citation, exhibit, data, witness)
  - Map evidence anchors to issues or claims when present
  - Produce a structured evidence-anchor table for downstream analysis
limitations:
  - Does not perform legal reasoning, doctrinal analysis, or burden mapping
  - Does not extract or classify contradictions
  - Does not build timelines or normalize dates
  - Does not generate briefs or arguments
input_shape: >
  Document containing factual assertions, citations, exhibits, data points, or witness statements (filings, reports, transcripts, agency decisions, multi-source sets).
output_shape: >
  Structured evidence-anchor table with columns: # | Type | Content | Location | Source | Mapped to | Quality. Plus appended sections listing orphan anchors and unsupported claims.
dependencies: []
governance_version: 1.1.0
---

# Clarity Evidence Anchor Extractor

## Purpose
Identify and classify the evidence anchors in any document — the discrete
text fragments that function as evidentiary support. Output is a structured
evidence-anchor table with typed entries (fact / citation / exhibit / data /
witness), source locations, and — where the document presents discrete
issues or claims — the mapping from anchor to issue. The table is
scaffolding that downstream skills (legal reasoning, narrative analysis,
summarization) can use to verify support, identify gaps, and audit the
record.

## Category Justification
This skill pulls discrete, classifiable items from a document — factual
assertions, citations, exhibits, data points, witness references — and
produces a typed list with provenance.

This skill belongs to the **Evidence Extraction** category because its
primary output is a typed list of evidence items extracted from a document
with provenance and classification. See `SKILL_TAXONOMY.md` § A for the
category definition.

This skill is the second skill in Evidence Extraction. It is distinguished
from `clarity-contradictions-extractor` (also Evidence Extraction) by
primary output: that skill finds **contradictions** — places where claims
conflict with other claims — and produces a typed list of conflicts. This
skill finds **anchors** — places where claims are supported — and produces
a typed list of supports. The two are complementary: anchors describe what
the document asserts and where; contradictions describe where those
assertions break against each other.

## Boundary Statement

This skill **does not**:

- Perform legal reasoning, doctrinal analysis, or burden mapping; for that see Legal Reasoning skills (e.g., `clarity-legal-argument-mapper`).
- Extract or classify contradictions; for that see the sibling Evidence Extraction skill `clarity-contradictions-extractor`.
- Build timelines or normalize dates; for that see Timeline Construction skills (e.g., `clarity-timeline-mapper`).
- Generate briefs or arguments; output is a structural extraction only, never a synthesized argument.

For methods that fall outside the boundary above, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md` to find
the right category.

## Instructions

### 1. Read the Source in Full
- Read the document end to end.
- Identify the document type and its evidentiary expectations (filing, report, transcript, agency decision, news article, multi-source set).
- Note the document's section structure for use as anchor location references.

### 2. Identify Evidence Anchor Candidates
- Scan for any text that asserts a fact or provides support for an assertion.
- Common surface forms include: "the record shows…", "Exhibit A…", "Smith v. Jones, 123 F.3d 456…", "33% of respondents…", "[witness] testified that…", "Decl. of [name] ¶ 7…", "[Statute] § 102(b)…".
- Capture both pinpoint anchors (specific section / paragraph / page) and general anchors (broad reference to a record).

### 3. Classify by Anchor Type
Use the five canonical anchor types:

- **fact** — declarative factual assertion offered as primary support, with no further citation.
- **citation** — reference to legal authority: case law, statute, regulation, doctrinal source.
- **exhibit** — reference to a labeled exhibit, attachment, declaration, or filed document.
- **data** — numerical or quantitative claim (statistic, measurement, dollar figure, percentage, count).
- **witness** — testimonial reference: deposition, declaration content, sworn statement.

If a single text fragment functions as more than one type, classify by its primary role and note the secondary type in the table.

### 4. Capture Anchor Metadata
For each anchor, record:

- **Anchor #** — a sequential identifier for cross-reference.
- **Type** — from step 3.
- **Content** — verbatim quote (short) or paraphrased compression (longer).
- **Location** — section, paragraph, page in the document.
- **Cited source** — case name, statute, exhibit label, deponent name, dataset name. Empty if `fact` type with no citation.
- **Strength signal** — does the anchor stand on its own, or does it depend on another anchor? Note dependency.

### 5. Map Anchors to Issues or Claims
- If the document presents discrete issues, claims, or arguments, identify which anchor supports which issue/claim.
- An anchor may map to multiple issues, one issue, or none.
- Flag **orphan anchors** (anchors that don't connect to any stated claim) and **unsupported claims** (claims with no anchor).

### 6. Identify Anchor Quality Signals
For each anchor, note:

- **Specific** vs. **vague** — "Exhibit B page 12, line 7" vs. "the record".
- **Direct** vs. **secondhand** — first-hand declaration vs. summary of someone else's declaration.
- **First-party** vs. **third-party** — who's making the underlying claim.

These signals do not constitute legal weight; they are descriptive of the anchor's textual form.

### 7. Produce the Evidence Anchor Table
- Output a structured table with columns: **# | Type | Content | Location | Source | Mapped to | Quality**.
- Order anchors in document-encounter order (not by type).
- Append two flagged sections after the table:
  - **Orphan anchors** — anchors with no mapped claim.
  - **Unsupported claims** — claims with no mapped anchor.

### 8. Quality Check
- Verify every anchor traces to the source.
- Confirm classifications are internally consistent (the same fragment shape gets the same type).
- Confirm no embedded PII or case-specific tokens leaked from the source.

## Example Input
"Extract the evidence anchors from this motion for summary judgment."

## Example Output

| # | Type | Content | Location | Source | Mapped to | Quality |
|---|---|---|---|---|---|---|
| 1 | citation | Standard for summary judgment | p. 4 ¶ 1 | *Anderson v. Liberty Lobby* (1986) | Issue 1 | specific, direct |
| 2 | exhibit | Personnel file | p. 5 ¶ 3 | Exhibit A | Issue 1 element 2 | specific, first-party |
| 3 | witness | Statement re. policy | p. 6 ¶ 2 | Decl. of [Witness] ¶ 7 | Issue 1 element 2 | direct |
| 4 | data | 12% turnover rate | p. 7 ¶ 1 | (no citation) | (orphan) | vague |
| 5 | fact | Plaintiff was hired in 2019 | p. 3 ¶ 4 | (no citation) | Background | direct, undisputed |

**Orphan anchors:** #4 (turnover data; no claim references it).  
**Unsupported claims:** Issue 1 element 3 has no anchor in the record.

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
