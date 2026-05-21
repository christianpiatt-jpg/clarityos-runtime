---
name: clarity-legal-argument-mapper
description: >
  Analyze legal documents (motions, briefs, agency decisions, opinions) and extract
  their legal argument structure: issues, standards of review, elements, sub-elements,
  burdens, evidence citations, and logical dependencies. Use when asked to map,
  dissect, decompose, or structurally analyze the legal logic of a document.
category: Legal Reasoning
capabilities:
  - Identify legal issues and classify them as questions of law, fact, or mixed
  - Extract standards of review and flag standard-mismatch errors
  - Map arguments to legal-test elements and sub-elements
  - Identify missing elements, unsupported assertions, and unmapped evidence
  - Identify burden-shifting errors and improperly invoked frameworks
  - Produce a structured legal argument map keyed by issue and element
limitations:
  - Does not perform narrative analysis (framing, identity threads, institutional behavior)
  - Does not extract or classify contradictions
  - Does not build timelines or normalize dates
  - Does not generate full briefs or rewrite legal documents
input_shape: >
  Legal document (motion, brief, opinion, agency decision) presenting one or more legal issues, standards of review, and supporting evidence or authority.
output_shape: >
  Structured argument map keyed by issue → element → sub-element → evidence/authority → burden → status, with an explicit Identified Gaps section listing missing elements, unsupported assertions, unmapped evidence, standard-mismatch errors, and burden-shifting errors.
dependencies: []
governance_version: 1.1.0
---

# Clarity Legal Argument Mapper

## Purpose
Analyze legal documents — motions, briefs, agency decisions, opinions — and
produce a structured map of their legal argument architecture. Output exposes
issues, standards of review, elements (with sub-elements), evidence and
authority citations, burdens of persuasion and production, and the logical
dependencies that hold the argument together — or reveal where it breaks.

## Category Justification
This skill operates on legal standards, doctrines, and procedural rules:
extracting their structure from a document, mapping arguments to legal-test
elements, identifying gaps in support, and flagging burden-shifting errors.

This skill belongs to the **Legal Reasoning** category because its primary
output is a structured map of the legal argument architecture (issues,
standards, elements, evidence citations, burdens, dependencies). See
`SKILL_TAXONOMY.md` § A for the category definition.

## Boundary Statement

This skill **does not**:

- Perform narrative analysis — framing, identity threads, institutional behavior; for that see Narrative Analysis skills (e.g., `clarity-narrative-litigation`).
- Extract or classify contradictions; for that see Evidence Extraction skills (e.g., `clarity-contradictions-extractor`).
- Build timelines or normalize dates; for that see Timeline Construction skills (e.g., `clarity-timeline-mapper`).
- Generate full briefs or rewrite legal documents; the output is a structural analysis, not a finished work product.

For methods that fall outside the boundary above, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md` to find
the right category.

## Instructions

### 1. Identify the Document Type and Posture
- Determine the document type: motion, brief, opinion, agency decision, statutory application, etc.
- Identify the forum (court, agency, tribunal) and the procedural posture.
- Note the relief sought, or — if an opinion or decision — the holding.

### 2. Extract the Issues
- List every distinct legal issue the document presents or decides.
- For each, classify as a question of law, question of fact, or mixed question.
- Number issues for cross-reference in later steps.

### 3. Extract Standards of Review
- For each issue, identify the applicable standard of review (de novo, abuse of discretion, substantial evidence, clear error, plausibility, etc.).
- Note any contested standards or unusual frameworks invoked.
- Flag standard-mismatch errors — issue type and asserted standard do not fit (e.g., asserting de novo for a discretionary call).

### 4. Map Arguments to Elements
- For each issue, identify the controlling legal test (statutory or doctrinal).
- Decompose the test into elements and, where helpful, sub-elements.
- Map each argument or assertion in the document to the specific element or sub-element it addresses.

### 5. Identify Evidence and Authority Citations
- For each element / sub-element, list the citations offered in support.
- Distinguish three citation types: record evidence (declarations, exhibits, deposition transcripts), legal authority (cases, statutes, regulations), and policy or doctrinal sources.
- Flag elements that have no evidentiary or authoritative support.

### 6. Map Burdens
- For each element, identify the burden of production and the burden of persuasion.
- Note any burden-shifting frameworks invoked (e.g., McDonnell Douglas, prima-facie-and-rebuttal patterns, Mt. Healthy mixed-motive).
- Flag burden-shifting errors: arguments treating a burden as shifted when the predicate was not satisfied, or arguments treating a non-shifting burden as shifted.

### 7. Identify Logical Dependencies
- For each argument, identify the other arguments or premises it depends on.
- Distinguish conjunctive structures (all required) from disjunctive structures (any one suffices).
- Identify cascading dependencies — where the failure of one element collapses an entire chain.

### 8. Identify Gaps
- **Missing elements** — legal tests with at least one element not addressed.
- **Unsupported assertions** — claims with no evidentiary or doctrinal citation.
- **Unmapped evidence** — cited material that doesn't connect to any element.
- **Standard-mismatch errors** carried over from step 3.
- **Burden-shifting errors** carried over from step 6.

### 9. Produce the Argument Map
- Output a structured outline keyed by **issue → element → sub-element → evidence/authority → burden → status**.
- Status values: supported, unsupported, contested, missing.
- Note logical dependencies between issues and within each issue's element chain.
- Append a final "Identified gaps" section that consolidates all gap-flagged items from step 8.

## Example Input
"Map the legal argument structure of this motion to dismiss for failure to
state a claim."

## Example Output

**Document type:** Motion to Dismiss (Rule 12(b)(6))  
**Forum / posture:** [Court / agency, procedural posture]  
**Relief sought:** Dismissal of [count(s)]

**Issue 1: [Issue statement]**  *(question of law)*
- **Standard of review:** [e.g., Twombly / Iqbal "plausibility"]
- **Test:** [Element 1] AND [Element 2] AND [Element 3]
  - **Element 1: [name]**
    - Sub-element 1a: [argument] — cites [authority/evidence] — *supported*
    - Sub-element 1b: [argument] — *unsupported* — gap
  - **Element 2: [name]**
    - [argument] — cites [authority] — *contested*
  - **Element 3: [name]** — *not addressed* — gap
- **Burden:** Moving party bears burden on motion; no shift available at 12(b)(6).
- **Dependencies:** Test is conjunctive — Element 3's absence defeats the issue.

**Issue 2: [Issue statement]**
- ...

**Identified gaps**
1. Element 3 of Issue 1 is not addressed.
2. Sub-element 1b lacks an authority or evidentiary citation.
3. [etc.]

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
