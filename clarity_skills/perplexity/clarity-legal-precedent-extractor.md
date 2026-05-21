---
name: clarity-legal-precedent-extractor
description: >
  Extracts, normalizes, and structures legal precedents referenced in text —
  case names, citations, holdings, and relevance statements. Use when asked
  to extract, list, normalize, structure, or catalogue case-law citations
  and precedents in legal documents.
category: Legal Reasoning
capabilities:
  - Identify case-law references in legal text
  - Extract canonical citations and citation components (reporter, volume, page, year, court)
  - Summarize each precedent's holding in compressed form
  - Map each precedent's relevance to the surrounding argument or issue
  - Output structured precedent objects in deterministic order
limitations:
  - Does not perform legal interpretation or apply doctrines to facts
  - Does not validate jurisdictional hierarchy or court level
  - Does not assess binding vs. persuasive authority weight
  - Does not infer precedents not explicitly cited or strongly implied in the text
input_shape: >
  Freeform legal text containing case citations, references, or precedent discussions.
output_shape: >
  JSON array of precedent objects:
    - case_name (string)
    - citation (string or null)
    - holding (string)
    - relevance (string)
    - confidence (float 0.0-1.0)
dependencies: []
governance_version: 1.1.0
---

# Clarity Legal Precedent Extractor

## Purpose
Extract, normalize, and structure legal precedents referenced in text. The
output is a deterministic, machine-usable JSON array of precedent objects:
each carries the case name, the canonical citation (when present), a
compressed statement of the holding, an inline statement of the
precedent's relevance to the surrounding argument, and a confidence score
reflecting extraction certainty.

The skill is **deterministic and extractive** — it surfaces what the text
asserts about precedents, without performing legal interpretation,
validating court hierarchy, or weighing authority.

## Category Justification
This skill operates on legal authorities — case-law citations and
precedent discussions — and produces a structured analysis of how those
authorities are deployed in the source text. Its primary output is a
typed list of precedent objects with case name, citation, holding,
relevance, and confidence.

This skill belongs to the **Legal Reasoning** category because its
primary output is a structured doctrinal extraction (precedents and
their roles) rather than narrative framing or general evidence anchors.
See `SKILL_TAXONOMY.md` § A.

This skill is the second in Legal Reasoning. It is distinguished from
`clarity-legal-argument-mapper` (also Legal Reasoning) by primary
output: that skill maps the **whole argument architecture** (issues,
standards, elements, sub-elements, evidence, burdens, dependencies);
this skill produces a **focused precedent catalogue** — a structured
extraction of the case-law authorities the text invokes, with each
precedent's holding and relevance compressed into a single object. The
two are complementary: argument-mapper places precedents inside the
argument structure; precedent-extractor surfaces the precedents
themselves, atomized.

## Boundary Statement

This skill **does not**:

- Perform legal interpretation, apply doctrines to facts, or analyze burden frameworks; for that see `clarity-legal-argument-mapper` and other Legal Reasoning skills.
- Validate jurisdictional hierarchy, court level, or whether a precedent is binding in the forum where it is invoked. The skill records what the text says, not what is doctrinally correct.
- Assess binding vs. persuasive authority weight. Out of scope; would require external doctrinal knowledge beyond the input text.
- Extract evidence anchors, contradictions, or argument structure broadly; those are sibling skills (`clarity-evidence-anchor-extractor`, `clarity-contradictions-extractor`, `clarity-legal-argument-mapper`).
- Infer precedents not explicitly cited or strongly implied in the text. If the text does not name a case, the skill does not invent one.

For methods that fall outside this boundary, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md`.

## Method

The method has three conceptual passes over the source text:

1. **Detection** — locate every textual reference to a legal authority. Includes formal citations ("Anderson v. Liberty Lobby, 477 U.S. 242 (1986)"), short-form references ("Anderson at 247"), case-name-only references ("under Anderson"), and statutory or doctrinal references that function as precedent in the argument.
2. **Normalization** — for each reference, canonicalize the case name, parse the citation into components (reporter, volume, page, year, court when available), and record the holding the source asserts the case stands for.
3. **Relevance mapping** — for each precedent, capture in one sentence what role the precedent plays in the surrounding text (what proposition it is offered to support, distinguish, or rebut).

Each precedent is emitted as a single object with five fields. Output is
ordered deterministically: by first source-encounter position of each
distinct case.

## Instructions

### 1. Read the Source in Full
- Read the document end to end.
- Identify the document type (motion, brief, opinion, agency decision, secondary authority).
- Note any sections that signal heavy precedent density (Argument, Discussion, Analysis).

### 2. Detect Precedent References
- Mark every textual reference to a legal authority. Capture verbatim with source position.
- Detect both first mentions (with full citations) and short-form follow-ups; map short-forms back to first-mention case names.
- Include statutory and regulatory references when the text uses them as precedential authority.

### 3. Normalize Case Names
- Use the canonical form: `Plaintiff v. Defendant` for two-party cases, with italicization stripped.
- For en banc / consolidated / per curiam variants, retain the canonical short form unless the text relies on the variant.
- Resolve short-forms ("Anderson at 247") to the first-mention case name.

### 4. Extract and Parse Citations
- Capture the citation verbatim where given.
- For each citation, parse components when extractable: reporter, volume, page, year, court.
- If no citation accompanies a reference, set `citation` to `null` and reduce confidence accordingly.

### 5. Summarize the Holding
- Capture the proposition the source text asserts the case stands for, in 1–2 sentences.
- Use the source's framing — do not impose external interpretation.
- If the text references a case by name only (no holding stated), record `holding` as the most specific implied proposition from context, and reduce confidence.

### 6. Map Relevance
- In one sentence, state what role the precedent plays at the source position: support for X, distinguished from X, rebutted as inapplicable, cited for general principle, etc.
- Cite the source position (section / paragraph) where the precedent is invoked.

### 7. Score Confidence
- **0.9–1.0** — full citation + explicit holding statement + clear relevance role.
- **0.7–0.85** — full citation, holding inferred from immediate context.
- **0.5–0.65** — case name only, citation absent, holding partially stated.
- **0.3–0.45** — short-form reference whose first-mention is ambiguous.
- **0.0–0.25** — reference is mentioned but role and holding cannot be determined from text.

### 8. Order and Emit
- Order precedents by first source-encounter position (deterministic).
- If a precedent is invoked multiple times, emit ONE object per distinct case; mention the multiple invocations inside `relevance` if their roles differ.
- Emit as a single JSON array per the Output Contract below.

## Output Contract

The output is a **JSON array of precedent objects**. Every object MUST
have all five fields with the types and shapes below — no extra fields,
no missing fields.

```json
[
  {
    "case_name": "Anderson v. Liberty Lobby",
    "citation": "477 U.S. 242 (1986)",
    "holding": "Summary judgment is proper when no genuine dispute of material fact exists.",
    "relevance": "Cited at p. 4 ¶ 1 as the controlling standard for the moving party's burden.",
    "confidence": 1.0
  },
  {
    "case_name": "Smith v. Jones",
    "citation": null,
    "holding": "Plaintiffs must plead specific facts under heightened pleading standards.",
    "relevance": "Invoked at p. 7 ¶ 3 to argue the complaint is insufficient.",
    "confidence": 0.55
  }
]
```

Field rules:

- `case_name` — canonical short form (`Plaintiff v. Defendant`), no italicization, no party titles. Required.
- `citation` — full citation as it appears in the source, OR `null` if no citation is provided. String or `null`.
- `holding` — one or two sentences, the proposition the source asserts the case stands for. Required (use best inference + reduced confidence if not explicitly stated).
- `relevance` — one sentence, the role at the cited source position. Required.
- `confidence` — float in `[0.0, 1.0]`. Scored per § 7 of Instructions.

The output MUST be a single JSON array — not an object containing an
array, not a sequence of objects. Downstream consumers
(e.g., `clarity-legal-argument-mapper`) parse this contract directly to
populate the evidence column of the argument map.

## Example Input
"The summary judgment standard requires the moving party to show no
genuine dispute of material fact. *Anderson v. Liberty Lobby*, 477 U.S.
242, 247 (1986). Plaintiff's complaint, by contrast, fails to plead
specific facts as required under *Smith v. Jones* and is therefore
insufficient on its face."

## Example Output
```json
[
  {
    "case_name": "Anderson v. Liberty Lobby",
    "citation": "477 U.S. 242, 247 (1986)",
    "holding": "Summary judgment requires the moving party to show no genuine dispute of material fact.",
    "relevance": "Cited as the controlling standard for the moving party's summary judgment burden.",
    "confidence": 1.0
  },
  {
    "case_name": "Smith v. Jones",
    "citation": null,
    "holding": "Plaintiffs must plead specific facts under heightened pleading standards.",
    "relevance": "Invoked to argue the complaint fails to meet the pleading standard.",
    "confidence": 0.55
  }
]
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
