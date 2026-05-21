---
name: {{skill-name}}
description: >
  {{skill-description}}
category: {{category}}
capabilities:
  - {{capability-1}}
  - {{capability-2}}
  - {{capability-3}}
limitations:
  - {{limitation-1}}
  - {{limitation-2}}
input_shape: >
  {{input-shape-description}}
output_shape: >
  {{output-shape-description}}
dependencies: []
governance_version: 1.1.0
---

# {{Skill Title}}

## Purpose
{{purpose}}

## Category Justification
{{category-justification}}

This skill belongs to the **{{category}}** category because its
primary output is {{primary-output}}. See `SKILL_TAXONOMY.md` § A for
the category definition.

## Boundary Statement

This skill **does not**:

- {{boundary-item-1}}
- {{boundary-item-2}}
- {{boundary-item-3}}

For methods that fall outside the boundary above, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md` to find
the right category.

## Instructions

{{instructions}}

## Example Input
{{examples}}

## Example Output
{{examples}}

## Governance Compliance Checklist

Before this skill is committed:

- [ ] `category` matches a row in `SKILL_TAXONOMY.md` § A.
- [ ] `capabilities` and `limitations` lists are non-empty.
- [ ] `input_shape` is a non-empty string describing what the skill consumes (schema 1.3.0 — required).
- [ ] `output_shape` is a non-empty string describing what the skill produces (schema 1.3.0 — required).
- [ ] `dependencies` is a list (may be empty `[]`) of skill names this skill depends on (schema 1.3.0 — required).
- [ ] `governance_version` matches the current governance layer
      version (`1.1.0` as of this template).
- [ ] `name` is lowercase, hyphens only, and matches the filename.
- [ ] `description` contains explicit trigger phrases.
- [ ] No PII; no Layer 2 case material.
- [ ] File under 10 MB.
- [ ] `SKILL.md` at the root of the upload zip; byte-identical to
      this `.md`.
- [ ] Manifest entry under schema 1.3.0 includes `category`,
      `capabilities`, `limitations`, `input_shape`, `output_shape`,
      `dependencies`, `governance_version`, and `baseline_hash`
      (the SHA256 of this `.md` at first commit).
- [ ] Drift Detector returns `DRIFT: NONE` after baseline regeneration.
- [ ] Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

<!--
TEMPLATE NOTES (delete this comment block before saving the final skill):

  Template version: v1.3.0 (schema 1.3.0)

  Placeholders to replace:
    {{skill-name}}             lowercase, hyphens only — e.g. clarity-statute-mapper
    {{skill-description}}      1–3 sentences. Lead with WHEN to fire (trigger phrases),
                               then WHAT the skill produces. This is the matcher field.
    {{category}}               EXACT verbatim string from SKILL_TAXONOMY.md A:
                                 Narrative Analysis | Evidence Extraction |
                                 Timeline Construction | Legal Reasoning |
                                 Summarization
                               Mutually exclusive — pick exactly one based on PRIMARY OUTPUT.
    {{capability-N}}           One short sentence each. What the skill produces or does well.
                               Three to six items typical.
    {{limitation-N}}           One short sentence each. What the skill explicitly does NOT do.
                               Two to four items typical.
    {{input-shape-description}} REQUIRED (schema 1.3.0). Short prose describing the SHAPE
                               of input the skill expects. One or two lines. Examples:
                               "Freeform legal text containing case citations."
                               "Multi-document record (filings, exhibits, transcripts)."
    {{output-shape-description}} REQUIRED (schema 1.3.0). Short prose describing the SHAPE
                               of output the skill produces. One or two lines. Examples:
                               "JSON array of normalized event objects: ..."
                               "Markdown brief in fixed four-section structure."
    dependencies: []           REQUIRED (schema 1.3.0). YAML list. Empty `[]` if the skill
                               has no upstream skill dependencies. Otherwise list skill
                               names by exact `name` field — e.g.
                                 dependencies:
                                   - clarity-evidence-anchor-extractor
                                   - clarity-temporal-event-normalizer
    {{Skill Title}}            Title Case display name — e.g. "Clarity Statute Mapper"
    {{purpose}}                One paragraph describing the method and its output shape.
    {{category-justification}} 1-2 sentences. Why this skill is in {{category}} and not
                               in any neighbouring category. Reference the primary output.
    {{primary-output}}         Short noun phrase — what the skill produces (e.g.
                               "a normalized chronology with temporal-inconsistency flags").
    {{boundary-item-N}}        First-person prose restating limitations for readers.
    {{instructions}}           Numbered, atomic steps under ### headings. Each step
                               executable in isolation.
    {{examples}}               Replace BOTH occurrences (Example Input + Example Output).

  Schema 1.3.0 (this template):
    The three previously-additive fields — input_shape, output_shape, dependencies —
    are now REQUIRED in every skill's frontmatter. The governance self-test FAILS
    if any of these three is missing or empty (input_shape / output_shape) or
    not a list (dependencies). Validation rules:
      - input_shape: non-empty string
      - output_shape: non-empty string
      - dependencies: list (may be empty); items must be `name` strings of
                      skills that exist in MANIFEST.json

  Note on baseline_hash:
    baseline_hash is the SHA256 of THIS .md at first commit. Recorded ONLY in the
    MANIFEST.json entry (not in this frontmatter) to avoid the self-reference
    problem. Compute after finalizing the .md and paste into both md_sha256 and
    baseline_hash in the manifest entry. They start equal; thereafter md_sha256
    tracks current state and baseline_hash stays frozen.

  Constraints:
    - General-case Layer 1 only. No PII, no case-specific facts.
    - Total file size under 10 MB. Plain UTF-8.
    - Save as {{skill-name}}.md in /clarity_skills/perplexity/.
    - Bundle into {{skill-name}}.zip with SKILL.md at the archive root.

  See CREATE_NEW_SKILL_INSTRUCTIONS.md for the full procedure including the
  schema 1.3.0 enforcement notes and the Governance Gate.
-->
