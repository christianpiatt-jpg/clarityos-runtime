# Governance Changelog

This file records the lifecycle of the governance layer itself —
distinct from the per-skill version history maintained in
`MANIFEST.json` and the per-skill content under
`clarity_skills/perplexity/`.

The governance layer follows the same semver scheme defined in
`VERSIONING.md`: patch for non-semantic edits, minor for additive
non-breaking changes, major for breaking changes.

---

## Governance v1.0.0 — Initial Release

Released: 2026-05-07

Established the governance layer with four canonical documents and a
manifest-level governance block.

- Added `VERSIONING.md` — patch / minor / major bump rules, manifest
  update rules, release discipline.
- Added `INTEGRITY_CHECKS.md` — hash verification, structural checks,
  contamination checks, pre-commit verification suite.
- Added `governance` top-level block to `MANIFEST.json` referencing the
  four canonical files. Bumped `manifest_version` 1.0.0 → 1.1.0
  (additive schema change).
- Added "Skill Library Governance" section to `README.md`.

State at end of v1.0.0:

- 3 skills (`clarity-narrative-litigation`,
  `clarity-contradictions-extractor`, `clarity-timeline-mapper`),
  each at skill-version 1.0.0.
- 4 canonical governance files, each at file-version 1.0.0.
- Manifest schema 1.1.0.
- Integrity suite passes (3 × OK).

---

## Governance v1.1.0 — Enforcement Layer

Released: 2026-05-07

Operationalized the governance layer — added enforcement, baseline,
drift detection, and self-test capability. Governance is now **active**
rather than merely documented.

- Added **Governance Gate** to `CREATE_NEW_SKILL_INSTRUCTIONS.md` —
  six mandatory checks every skill must clear before commit (version
  bump, manifest entry, integrity, contamination, drift, self-test).
  Bumped that file's version 1.0.0 → 1.1.0 (additive section).
- Added **Baseline Snapshot** (`BASELINE_STATE.json`) — frozen
  known-good state of every file in the library, including all skill
  hashes (`hash_md`, `hash_zip`), governance file hashes/versions,
  anchor file hashes (`MANIFEST.json`, `README.md`), `manifest_version`,
  `schema_version`, `governance_layer_version`, and `BUILD_VERSION` at
  the moment of release. Provides a restore point and the reference
  for drift detection.
- Added **Drift Detector** (`DRIFT_DETECTOR.ps1`) — compares current
  folder state to `BASELINE_STATE.json` and reports `DRIFT: NONE` or
  an itemized list of divergences. Catches: hash changes (skill,
  governance, anchor), missing files, unexpected new files,
  manifest_version drift, BUILD_VERSION drift.
- Added **Governance Self-Test** (`GOVERNANCE_SELF_TEST.ps1`) —
  verifies governance layer internal consistency: canonical files
  exist, are referenced in manifest, schema versioning is well-formed,
  integrity tooling can hash them, baseline tracks them with semver
  versions.
- Added **Operationalization** section to `README.md` — when to run
  what, gate procedure, script invocation guidance, baseline
  regeneration, phase summary.
- Added this changelog (`GOVERNANCE_CHANGELOG.md`) to give governance
  itself a documented lifecycle.

State at end of v1.1.0:

- 3 skills, each at skill-version 1.0.0 (unchanged).
- 8 governance / enforcement files:
  - `VERSIONING.md` (file v1.0.0)
  - `INTEGRITY_CHECKS.md` (file v1.0.0)
  - `SKILL_TEMPLATE.md` (file v1.0.0)
  - `CREATE_NEW_SKILL_INSTRUCTIONS.md` (file v1.1.0)
  - `BASELINE_STATE.json` (file v1.0.0)
  - `DRIFT_DETECTOR.ps1` (file v1.0.0)
  - `GOVERNANCE_SELF_TEST.ps1` (file v1.0.0)
  - `GOVERNANCE_CHANGELOG.md` (file v1.0.0 — this file)
- Manifest schema 1.1.0 (unchanged — no manifest schema changes in
  this release).
- Integrity suite passes (3 × OK).
- Drift Detector returns `DRIFT: NONE` against the v1.1.0 baseline.
- Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Phase 4 complete. Library has transitioned from
"documented" to "governed".

---

## Governance v1.2.0 — Expansion Enablement

Released: 2026-05-07

Established the scaffolding required for safe library expansion. New
skills can now be admitted to the library only under schema v1.2.0,
the taxonomy, and governance v1.1.0. Existing skills were migrated to
schema v1.2.0 in the same release (frontmatter additions only, no
behavioral changes; each existing skill bumped 1.0.0 → 1.0.1, patch).

- Added `SKILL_TAXONOMY.md` — fixed top-level category vocabulary
  (Narrative Analysis, Evidence Extraction, Timeline Construction,
  Legal Reasoning, Summarization). Includes rules for adding,
  merging, and deprecating categories, plus an authoritative mapping
  of existing skills to categories. Initial `taxonomy_version: 1.0.0`.
- Added `taxonomy_file: "SKILL_TAXONOMY.md"` reference to
  `MANIFEST.json` `governance` block.
- Bumped `MANIFEST.json` schema: `manifest_version` 1.1.0 → 1.2.0,
  added peer `schema_version: 1.2.0` field. Added five required
  per-skill fields: `category`, `capabilities`, `limitations`,
  `governance_version`, `baseline_hash`.
- Migrated the 3 existing skill manifest entries to schema v1.2.0:
  - `clarity-narrative-litigation` → category **Narrative Analysis**,
    governance_version `1.0.0`, baseline_hash recorded (= original
    pre-migration md_sha256, frozen forever).
  - `clarity-contradictions-extractor` → category **Evidence
    Extraction**, governance_version `1.0.0`, baseline_hash recorded.
  - `clarity-timeline-mapper` → category **Timeline Construction**,
    governance_version `1.0.0`, baseline_hash recorded.
  Each existing skill bumped 1.0.0 → 1.0.1 (patch — frontmatter
  additions, non-semantic). Zips regenerated. New `md_sha256` and
  `zip_sha256` recorded; `baseline_hash` preserves the pre-migration
  fingerprint.
- Updated `SKILL_TEMPLATE.md` 1.0.0 → 1.2.0 with new frontmatter
  fields (`category`, `capabilities`, `limitations`,
  `governance_version`), new body sections (Category Justification,
  Boundary Statement, Governance Compliance Checklist), and updated
  template notes. `baseline_hash` deliberately omitted from
  frontmatter to avoid self-reference (the hash of a file that
  contains its own hash is undefined); canonical value lives only in
  the manifest entry.
- Updated `CREATE_NEW_SKILL_INSTRUCTIONS.md` 1.1.0 → 1.2.0 with a new
  "Expansion Mode (Schema 1.2.0)" section covering: updated
  placeholder table, updated manifest entry shape, the
  `baseline_hash` filling protocol, updated pre-commit verification,
  and updated validation checklist. The Governance Gate from v1.1.0
  is preserved unchanged.
- Updated `DRIFT_DETECTOR.ps1` 1.0.0 → 1.2.0:
  - validates `SKILL_TAXONOMY.md` presence and hash via baseline
  - validates `schema_version` matches baseline
  - validates `governance.taxonomy_file` is `"SKILL_TAXONOMY.md"`
  - validates per-skill `version`, `md_sha256`, `zip_sha256`,
    `category`, `governance_version`, `baseline_hash` fields in
    `MANIFEST.json` against baseline
  - all v1.0.0 detections preserved
- Updated `GOVERNANCE_SELF_TEST.ps1` 1.0.0 → 1.2.0:
  - confirms `taxonomy_file` referenced in manifest governance block
  - confirms taxonomy file tracked in `BASELINE_STATE.json`
  - confirms each skill in manifest has all schema 1.2.0 required fields
  - confirms each skill's `category` is a known taxonomy category
    (parsed from `SKILL_TAXONOMY.md` § A)
  - confirms each skill's `governance_version` is valid semver
  - confirms each skill's `baseline_hash` is a valid SHA256
    (64 lowercase hex chars)
  - confirms `manifest_version` matches `schema_version`
  - confirms `CREATE_NEW_SKILL_INSTRUCTIONS.md` references the
    taxonomy
  - confirms `SKILL_TEMPLATE.md` frontmatter includes the schema
    1.2.0 fields
  - all v1.0.0 checks preserved
- Updated `BASELINE_STATE.json` for schema v1.2.0:
  - added `SKILL_TAXONOMY.md` under `governance_files`
  - bumped `schema_version` 1.1.0 → 1.2.0
  - bumped `manifest_version` 1.1.0 → 1.2.0
  - bumped `governance_layer_version` to 1.2.0
  - bumped `CREATE_NEW_SKILL_INSTRUCTIONS.md` file version 1.1.0 → 1.2.0
  - bumped `SKILL_TEMPLATE.md` file version 1.0.0 → 1.2.0
  - bumped `DRIFT_DETECTOR.ps1` file version 1.0.0 → 1.2.0
  - bumped `GOVERNANCE_SELF_TEST.ps1` file version 1.0.0 → 1.2.0
  - new per-skill fields `category`, `governance_version`,
    `baseline_hash` recorded in the `skills` block
  - all hashes regenerated post-migration
- Added "Phase 5: Expansion (Governance v1.2.0)" section to
  `README.md` covering: what Expansion Mode means, how the taxonomy
  works, how schema v1.2.0 works, how new skills must be created, how
  governance ensures consistency, and how the v1.2.0 baseline
  protects the library.

State at end of v1.2.0:

- 3 skills, each at skill-version 1.0.1 (frontmatter migration), each
  classified under the taxonomy:
  - `clarity-narrative-litigation` → Narrative Analysis
  - `clarity-contradictions-extractor` → Evidence Extraction
  - `clarity-timeline-mapper` → Timeline Construction
- 9 governance / enforcement files:
  - `VERSIONING.md` (v1.0.0)
  - `INTEGRITY_CHECKS.md` (v1.0.0)
  - `SKILL_TEMPLATE.md` (v1.2.0)
  - `CREATE_NEW_SKILL_INSTRUCTIONS.md` (v1.2.0)
  - `SKILL_TAXONOMY.md` (v1.0.0) — NEW
  - `BASELINE_STATE.json` (v1.0.0)
  - `DRIFT_DETECTOR.ps1` (v1.2.0)
  - `GOVERNANCE_SELF_TEST.ps1` (v1.2.0)
  - `GOVERNANCE_CHANGELOG.md` (v1.0.0 — this file)
- Manifest schema 1.2.0 (from 1.1.0).
- Integrity suite passes (3 × OK).
- Drift Detector returns `DRIFT: NONE` against the v1.2.0 baseline.
- Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Phase 5 (Expansion Enablement) complete. Library is
structurally ready for new skills. **No new skill may be created
under schema 1.1.0.** All new skills must comply with the taxonomy,
schema v1.2.0, and governance v1.1.0.

---

## Governance v1.2.0 — First New Skill: clarity-operator-brief-structurer

Released: 2026-05-07

The first new skill admitted under the v1.2.0 expansion regime. No
governance file changes; this is a pure library-content release that
validates the v1.2.0 procedure end-to-end. Phase 6 (first new skill
under v1.2.0) is now complete.

- Added `clarity-operator-brief-structurer.md` (skill-version 1.0.0)
  under category **Summarization**. Produces operator-grade briefs in
  a fixed Situation / Assessment / Key Points / Recommended Actions
  structure. `governance_version: 1.1.0` (born under the current
  governance layer); `baseline_hash` recorded at first commit
  (= initial `md_sha256`, frozen forever per § B of `VERSIONING.md`).
- Added `clarity-operator-brief-structurer.zip` containing `SKILL.md`
  byte-identical to the source `.md`.
- Added a manifest entry under schema 1.2.0 with all required fields
  (`category`, `capabilities`, `limitations`, `governance_version`,
  `baseline_hash`). Bumped `MANIFEST.json` `generated_at` to today.
- Updated `README.md` Contents table with two new rows for the new
  skill `.md` and `.zip`.
- Regenerated `BASELINE_STATE.json` to track the new skill plus the
  new `MANIFEST.json` hash, the new `README.md` hash, and the new
  `GOVERNANCE_CHANGELOG.md` hash. Baseline now lists 4 skills.

State at end of v1.2.0 + first-skill release:

- 4 skills under the taxonomy:
  - `clarity-narrative-litigation` v1.0.1 → Narrative Analysis
  - `clarity-contradictions-extractor` v1.0.1 → Evidence Extraction
  - `clarity-timeline-mapper` v1.0.1 → Timeline Construction
  - `clarity-operator-brief-structurer` v1.0.0 → Summarization
- 9 governance / enforcement files (unchanged from v1.2.0).
- Manifest schema 1.2.0 (unchanged).
- Integrity suite passes (4 × OK).
- Drift Detector returns `DRIFT: NONE` against the updated v1.2.0
  baseline.
- Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Phase 6 (first new skill under v1.2.0) complete.
The v1.2.0 expansion procedure is end-to-end validated. The library
now spans 4 of 5 taxonomy categories; **Legal Reasoning** is the only
unpopulated category.

---

## Governance v1.2.0 — Second New Skill: clarity-legal-argument-mapper + Taxonomy § F Refresh

Released: 2026-05-07

The second new skill admitted under the v1.2.0 expansion regime;
populates the previously-empty **Legal Reasoning** category, completing
**5 / 5 taxonomy coverage**. The same release also closes the
documentary gap flagged at the end of v1.2.0 + first-skill: the
"authoritative" mapping in `SKILL_TAXONOMY.md` § F is brought back into
sync with `MANIFEST.json`.

- Added `clarity-legal-argument-mapper.md` (skill-version 1.0.0) under
  category **Legal Reasoning**. Produces structured legal argument
  maps: issues, standards of review, elements, sub-elements, evidence
  and authority citations, burdens, logical dependencies, and an
  explicit gaps list (missing elements, unsupported assertions,
  unmapped evidence, standard-mismatch and burden-shifting errors).
  `governance_version: 1.1.0`; `baseline_hash` recorded at first
  commit (= initial `md_sha256`, frozen).
- Added `clarity-legal-argument-mapper.zip` containing `SKILL.md`
  byte-identical to source.
- Added a manifest entry under schema 1.2.0 with all required fields.
- Updated `SKILL_TAXONOMY.md` 1.0.0 → 1.0.1 (patch — § F mapping
  refresh; no category changes). Added two rows to § F:
  - `clarity-operator-brief-structurer` → Summarization
    (closing the documentary gap from the prior release)
  - `clarity-legal-argument-mapper` → Legal Reasoning (this release)
  § F is once again the authoritative mapping it claims to be.
- Updated `README.md` Contents table with two new rows for the new
  skill `.md` and `.zip`.
- Regenerated `BASELINE_STATE.json`: 5 skills tracked; refreshed
  `SKILL_TAXONOMY.md` governance-file hash and version (1.0.0 → 1.0.1);
  refreshed anchor hashes for `MANIFEST.json` and `README.md`;
  refreshed `GOVERNANCE_CHANGELOG.md` hash for the appended entry.

State at end of release:

- 5 skills covering all 5 taxonomy categories — full coverage:
  - `clarity-narrative-litigation` v1.0.1 → Narrative Analysis
  - `clarity-contradictions-extractor` v1.0.1 → Evidence Extraction
  - `clarity-timeline-mapper` v1.0.1 → Timeline Construction
  - `clarity-operator-brief-structurer` v1.0.0 → Summarization
  - `clarity-legal-argument-mapper` v1.0.0 → Legal Reasoning
- 9 governance / enforcement files. `SKILL_TAXONOMY.md` bumped to
  1.0.1; all other governance files unchanged.
- Manifest schema 1.2.0 (unchanged).
- Integrity suite passes (5 × OK).
- Drift Detector returns `DRIFT: NONE` against the updated v1.2.0
  baseline.
- Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Phase 7 (first Legal Reasoning skill) complete.
The library spans **all 5 taxonomy categories** — full coverage. The
v1.2.0 expansion procedure has now been validated by two consecutive
new-skill releases.

---

## Governance v1.3.0 — Third New Skill: clarity-narrative-spine-builder (first second-skill-per-category)

Released: 2026-05-07

The third new skill admitted under the v1.2.0 schema. First
**second-skill-per-category** event in the library —
`clarity-narrative-spine-builder` is the second skill in **Narrative
Analysis**, joining `clarity-narrative-litigation`. The category now
demonstrates that multiple skills can coexist in one taxonomy bucket
without overlap, by distinguishing on primary output:
`clarity-narrative-litigation` produces a legal opposition outline;
`clarity-narrative-spine-builder` produces a general-purpose
narrative spine that any downstream skill (legal, evidentiary,
temporal, summarization) can build on.

`governance_layer_version` is bumped 1.2.0 → 1.3.0 as a **release
tag**. No governance procedures changed in this release —
`VERSIONING.md`, `INTEGRITY_CHECKS.md`, `SKILL_TEMPLATE.md`,
`CREATE_NEW_SKILL_INSTRUCTIONS.md`, `DRIFT_DETECTOR.ps1`, and
`GOVERNANCE_SELF_TEST.ps1` are all unchanged. The bump records that
this is the v1.3.0 release iteration; it does not signal a procedural
change. Manifest schema and per-skill schema remain at 1.2.0.

- Added `clarity-narrative-spine-builder.md` (skill-version 1.0.0)
  under category **Narrative Analysis**. Produces a compressed
  structural map (Actors / Conflict & Stakes / Causal Chain /
  Institutional Posture / Frame / Omissions / Distortions / Selective
  Framing). `governance_version: 1.1.0`; `baseline_hash` recorded at
  first commit (= initial `md_sha256`, frozen).
- Added `clarity-narrative-spine-builder.zip` containing `SKILL.md`
  byte-identical to source.
- Added a manifest entry under schema 1.2.0 with all required fields.
- Updated `SKILL_TAXONOMY.md` 1.0.1 → 1.0.2 (patch — § F mapping
  refresh; one new row for the new skill).
- Updated `README.md` Contents table with two new rows for the new
  skill `.md` and `.zip`.
- Regenerated `BASELINE_STATE.json`: `baseline_version` 1.3.0 → 1.4.0;
  `governance_layer_version` 1.2.0 → 1.3.0 (release tag);
  6 skills tracked; refreshed `SKILL_TAXONOMY.md` and
  `GOVERNANCE_CHANGELOG.md` governance-file hashes; refreshed anchor
  hashes for `MANIFEST.json` and `README.md`.

State at end of v1.3.0:

- 6 skills, 5 categories — first second-skill-per-category arrangement:
  - **Narrative Analysis** (2):
    - `clarity-narrative-litigation` v1.0.1
    - `clarity-narrative-spine-builder` v1.0.0  ← new
  - **Evidence Extraction** (1):
    - `clarity-contradictions-extractor` v1.0.1
  - **Timeline Construction** (1):
    - `clarity-timeline-mapper` v1.0.1
  - **Summarization** (1):
    - `clarity-operator-brief-structurer` v1.0.0
  - **Legal Reasoning** (1):
    - `clarity-legal-argument-mapper` v1.0.0
- 9 governance / enforcement files. `SKILL_TAXONOMY.md` bumped to
  1.0.2; all other governance files unchanged.
- Manifest schema 1.2.0 (unchanged — no schema change).
- Integrity suite passes (6 × OK).
- Drift Detector returns `DRIFT: NONE` against the v1.4.0 baseline.
- Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Phase 8 (second skill in Narrative Analysis)
complete. The library has graduated from "one skill per category" to
demonstrating coexistence within a category. The taxonomy boundary
discipline holds — both Narrative Analysis skills share the category
but distinguish cleanly on primary output: legal-opposition outline
vs. general-purpose narrative spine.

---

## Governance v1.4.0 — Fourth New Skill: clarity-evidence-anchor-extractor (second skill in Evidence Extraction)

Released: 2026-05-07

The fourth new skill admitted under the v1.2.0 schema. Second
**second-skill-per-category** event in the library —
`clarity-evidence-anchor-extractor` is the second skill in **Evidence
Extraction**, joining `clarity-contradictions-extractor`. The category
now demonstrates internal differentiation by primary output, mirroring
the Narrative Analysis precedent set in v1.3.0:
`clarity-contradictions-extractor` finds where claims **conflict**;
`clarity-evidence-anchor-extractor` finds where claims are **supported**.
Together they cover the two halves of evidentiary structural analysis —
breaks (contradictions) and supports (anchors).

`governance_layer_version` is bumped 1.3.0 → 1.4.0 as a **release tag**.
No governance procedures changed in this release —
`VERSIONING.md`, `INTEGRITY_CHECKS.md`, `SKILL_TEMPLATE.md`,
`CREATE_NEW_SKILL_INSTRUCTIONS.md`, `DRIFT_DETECTOR.ps1`, and
`GOVERNANCE_SELF_TEST.ps1` are all unchanged. The bump records that
this is the v1.4.0 release iteration; it does not signal a procedural
change. Manifest schema and per-skill schema remain at 1.2.0.

- Added `clarity-evidence-anchor-extractor.md` (skill-version 1.0.0)
  under category **Evidence Extraction**. Produces a structured
  evidence-anchor table with five typed columns (fact / citation /
  exhibit / data / witness), source locations, mapping to issues or
  claims, quality signals (specific/vague, direct/secondhand,
  first-party/third-party), plus orphan-anchor and unsupported-claim
  flags. `governance_version: 1.1.0`; `baseline_hash` recorded at
  first commit (= initial `md_sha256`, frozen).
- Added `clarity-evidence-anchor-extractor.zip` containing `SKILL.md`
  byte-identical to source.
- Added a manifest entry under schema 1.2.0 with all required fields.
- Updated `SKILL_TAXONOMY.md` 1.0.2 → 1.0.3 (patch — § F mapping
  refresh; one new row for the new skill).
- Updated `README.md` Contents table with two new rows for the new
  skill `.md` and `.zip`.
- Regenerated `BASELINE_STATE.json`: `baseline_version` 1.4.0 → 1.5.0;
  `governance_layer_version` 1.3.0 → 1.4.0 (release tag); 7 skills
  tracked; refreshed `SKILL_TAXONOMY.md` and `GOVERNANCE_CHANGELOG.md`
  governance-file hashes; refreshed anchor hashes for `MANIFEST.json`
  and `README.md`.

State at end of v1.4.0:

- 7 skills, 5 categories — two categories now have two skills each:
  - **Narrative Analysis** (2):
    - `clarity-narrative-litigation` v1.0.1
    - `clarity-narrative-spine-builder` v1.0.0
  - **Evidence Extraction** (2):
    - `clarity-contradictions-extractor` v1.0.1
    - `clarity-evidence-anchor-extractor` v1.0.0  ← new
  - **Timeline Construction** (1):
    - `clarity-timeline-mapper` v1.0.1
  - **Summarization** (1):
    - `clarity-operator-brief-structurer` v1.0.0
  - **Legal Reasoning** (1):
    - `clarity-legal-argument-mapper` v1.0.0
- 9 governance / enforcement files. `SKILL_TAXONOMY.md` bumped to
  1.0.3; all other governance files unchanged.
- Manifest schema 1.2.0 (unchanged — no schema change).
- Integrity suite passes (7 × OK).
- Drift Detector returns `DRIFT: NONE` against the v1.5.0 baseline.
- Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Phase 9 (second skill in Evidence Extraction)
complete. Two of the five taxonomy categories now contain coexisting
skills, each pair distinguished by primary output. The pattern
established in v1.3.0 (in-category coexistence by output-type
distinction) generalizes cleanly: contradictions (breaks) vs. anchors
(supports), opposition outline (legal lens) vs. narrative spine
(general lens). Three categories — Timeline Construction,
Summarization, Legal Reasoning — still hold a single skill each.

---

## Governance v2.0.0 — Agent Kernel Initialization

Released: 2026-05-08

**Maximum Vision Path Step 1.** Major release. Introduced a second
authored layer alongside skills: the **Agent Kernel**. Where a skill
is a single method (uploaded to Perplexity as a `.md` + `.zip`
bundle), an **agent** is a compositional role — a persona that
receives operator intent, selects skills from the library, composes
them in the right order, and produces an operator-grade output.

This is the first **major** governance bump (1.x.x → 2.0.0). The
trigger is a new top-level concept (agents) and a new top-level block
in `MANIFEST.json`. Existing skills continue to work without
modification; the skills array shape is unchanged. But manifest
readers now have to know about the agents block to be complete, which
makes the schema change major.

### New artifacts

- Added `AGENT_SPEC_TEMPLATE.md` (file v1.0.0). Initial agent
  template. Frontmatter declares the nine required schema 2.0.0 agent
  fields: `category`, `capabilities`, `limitations`, `skills_used`,
  `behavioral_profile`, `activation_triggers`, `output_shape`,
  `governance_version`, `agent_kernel_version`. Body has the standard
  Purpose / Category Justification / Boundary / Operating Procedure
  / Example sections plus three agent-specific sections: **Identity**,
  **Skills Composition**, **Behavioral Model**.
- Added `AGENT_TAXONOMY.md` (file v1.0.0). Five canonical agent
  categories: **Operator**, **Analyst**, **Reviewer**, **Composer**,
  **Custodian**. Same structural pattern as `SKILL_TAXONOMY.md` —
  rules for adding, merging, and deprecating categories; agent-to-
  category mapping; relationship to skills (agents compose skills,
  not vice versa); Layer 1 boundary statement.
- Added `clarity-operator-agent.md` (agent-version 1.0.0) under
  category **Operator**. The first agent admitted under the kernel.
  Composes all seven skills currently in the library and is the
  default entry point for direct operator interaction.
  `governance_version: 2.0.0`, `agent_kernel_version: 1.0.0`,
  `baseline_hash` recorded at first commit.

### Manifest schema changes (1.2.0 → 2.0.0)

- Bumped `manifest_version` 1.2.0 → 2.0.0 (major — new top-level
  block).
- Bumped `schema_version` 1.2.0 → 2.0.0 (matches manifest_version).
- Added `governance.agent_template_file: "AGENT_SPEC_TEMPLATE.md"`.
- Added `governance.agent_taxonomy_file: "AGENT_TAXONOMY.md"`.
- Added new top-level `agents` array, parallel to `skills`. Each
  agent entry carries: `name`, `version`, `filename`, `description`,
  `md_sha256`, `md_bytes`, `category`, `capabilities`, `limitations`,
  `skills_used`, `behavioral_profile`, `activation_triggers`,
  `output_shape`, `governance_version`, `agent_kernel_version`,
  `baseline_hash`. (No `zip_filename` / `zip_sha256` / `zip_bytes`
  — agents are spec files only.)

### Script updates

- Updated `DRIFT_DETECTOR.ps1` 1.2.0 → 2.0.0 — agent-aware:
  - Iterates `baseline.agents` (new top-level block) and validates
    per-agent `.md` hashes.
  - Validates per-agent manifest fields (`version`, `md_sha256`,
    `category`, `governance_version`, `agent_kernel_version`,
    `baseline_hash`) against baseline.
  - Validates `governance.agent_template_file` and
    `governance.agent_taxonomy_file` references.
  - Adds agent `.md` files to the expected-files list.
- Updated `GOVERNANCE_SELF_TEST.ps1` 1.2.0 → 2.0.0 — agent-aware:
  - Canonical files now 7 (added `AGENT_SPEC_TEMPLATE.md`,
    `AGENT_TAXONOMY.md`).
  - Validates `governance.agent_template_file` and
    `governance.agent_taxonomy_file` in manifest.
  - New per-agent checks: schema 2.0.0 fields present; category in
    `AGENT_TAXONOMY` (parsed live); `governance_version` and
    `agent_kernel_version` are semver; `baseline_hash` is valid
    SHA256; `skills_used` cross-references skills in `m.skills`.
  - Validates `AGENT_SPEC_TEMPLATE.md` frontmatter contains the
    schema 2.0.0 agent fields.

### Other updates

- Added "ClarityOS Agent Kernel (Governance v2.0.0)" section to
  `README.md`.
- Regenerated `BASELINE_STATE.json` for v2.0.0:
  - `baseline_version` 1.5.0 → 2.0.0.
  - `manifest_version` 1.2.0 → 2.0.0.
  - `schema_version` 1.2.0 → 2.0.0.
  - `governance_layer_version` 1.4.0 → 2.0.0.
  - Added new top-level `agent_kernel_version: 1.0.0`.
  - Added `clarity-operator-agent` to a new `agents` block (parallel
    to `skills`).
  - Added `AGENT_SPEC_TEMPLATE.md` and `AGENT_TAXONOMY.md` to
    `governance_files` (each at v1.0.0).
  - Bumped `DRIFT_DETECTOR.ps1` and `GOVERNANCE_SELF_TEST.ps1`
    versions in `governance_files` to 2.0.0.
  - Refreshed `MANIFEST.json` and `README.md` anchor hashes.
  - Refreshed `GOVERNANCE_CHANGELOG.md` governance-file hash.

State at end of v2.0.0:

- 7 skills (unchanged) under 5 taxonomy categories.
- 1 agent under 1 of 5 agent taxonomy categories:
  - **Operator** (1):
    - `clarity-operator-agent` v1.0.0
- 11 governance / enforcement / kernel files:
  - `VERSIONING.md` (v1.0.0)
  - `INTEGRITY_CHECKS.md` (v1.0.0)
  - `SKILL_TEMPLATE.md` (v1.2.0)
  - `CREATE_NEW_SKILL_INSTRUCTIONS.md` (v1.2.0)
  - `SKILL_TAXONOMY.md` (v1.0.3)
  - `AGENT_SPEC_TEMPLATE.md` (v1.0.0) — NEW
  - `AGENT_TAXONOMY.md` (v1.0.0) — NEW
  - `BASELINE_STATE.json` (v2.0.0)
  - `DRIFT_DETECTOR.ps1` (v2.0.0)
  - `GOVERNANCE_SELF_TEST.ps1` (v2.0.0)
  - `GOVERNANCE_CHANGELOG.md` (v1.0.0 — this file)
- Manifest schema 2.0.0 (from 1.2.0).
- Integrity suite passes (7 × OK skills, 1 × OK agent).
- Drift Detector returns `DRIFT: NONE` against the v2.0.0 baseline.
- Governance Self-Test returns `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Maximum Vision Path Step 1 complete. The library
now has two authored layers: the skill library (7 skills, 5 categories,
end-to-end-validated by 4 release iterations) and the agent kernel
(1 agent, 1 of 5 categories, scaffolding for compositional roles).
The agent kernel reuses every governance pattern established for
skills: taxonomy, schema, drift detection, integrity self-test,
baseline regeneration, changelog. Subsequent Maximum Vision Path
steps build on top of this kernel.

---

## Governance v2.0.0 — Post-Kernel Walk: Timeline Construction #2 + Operator Agent v1.0.1

Released: 2026-05-08

The walk-around-the-block release after the v2.0.0 agent kernel
initialization. **No governance procedure changes; no schema changes;
no script changes.** The release exercises the new agent-aware
governance end-to-end with one new skill and one Operator Agent edit.
`baseline_version`, `manifest_version`, `schema_version`, and
`governance_layer_version` all stay at `2.0.0`; `agent_kernel_version`
stays at `1.0.0`. This is a content release within the v2.0.0 cycle.

### New skill

- Added `clarity-temporal-event-normalizer.md` (skill-version 1.0.0)
  under category **Timeline Construction**. Second skill in Timeline
  Construction, joining `clarity-timeline-mapper`. Normalizes
  ambiguous temporal expressions to canonical ISO 8601 timestamps;
  emits a JSON array of normalized atomic events with per-event
  confidence. Distinguished from `clarity-timeline-mapper` by primary
  output: that skill **builds chronologies**; this skill produces the
  **normalized substrate** that timeline assembly consumes.
  `governance_version: 1.1.0`; `baseline_hash` recorded at first
  commit (= initial `md_sha256`, frozen forever per `VERSIONING.md`).
- Added `clarity-temporal-event-normalizer.zip` containing `SKILL.md`
  byte-identical to source.
- Manifest entry includes the 13 schema-1.2.0 required fields plus
  three additive optional fields: `input_shape`, `output_shape`,
  `dependencies`. The additive fields are **descriptive metadata only**
  in this release; formal schema 1.3.0 ratification (template
  prescription + self-test enforcement of the new fields) is deferred
  to a separate governance release.

### Operator Agent update

- Updated `clarity-operator-agent.md`: appended
  `clarity-temporal-event-normalizer` to `skills_used` (now 8 skills);
  body Skills Composition section adds a one-line description of the
  new skill's selection criteria. Manifest agent entry bumped
  1.0.0 → 1.0.1 (patch — additive `skills_used` entry, non-semantic
  edit otherwise) with refreshed `md_sha256` and `md_bytes`.
- **`baseline_hash` frozen** at the original v1.0.0 birth-state
  (`0cea5f13ce29b3ec40c77890c959c6d7e4bd0fb79062c2cd3b7a1a9edf7a9600`)
  per `VERSIONING.md` immutability rule. This is the first agent
  version bump in the library, and the first time the
  `md_sha256` ≠ `baseline_hash` invariant is exercised on the agent
  side. The drift detector's `baseline_hash`-immutability check
  validates the discipline.

### Other updates

- Updated `SKILL_TAXONOMY.md` 1.0.3 → 1.0.4 (patch — § F mapping
  refresh; one new row for the new skill).
- Updated `README.md` Contents table with two new rows for the new
  skill `.md` and `.zip`.
- Regenerated `BASELINE_STATE.json` twice as spec'd: once after the
  new skill (verifies skill-side path), once after the agent edit
  (verifies agent-side path). Both regenerations end at clean state.
  `baseline_version` stays at `2.0.0` per spec — this release is
  within the v2.0.0 baseline cycle, not a baseline-major change.

State at end of release:

- 8 skills, 5 categories — three categories now hold two skills:
  - **Narrative Analysis** (2):
    - `clarity-narrative-litigation` v1.0.1
    - `clarity-narrative-spine-builder` v1.0.0
  - **Evidence Extraction** (2):
    - `clarity-contradictions-extractor` v1.0.1
    - `clarity-evidence-anchor-extractor` v1.0.0
  - **Timeline Construction** (2):
    - `clarity-timeline-mapper` v1.0.1
    - `clarity-temporal-event-normalizer` v1.0.0  ← new
  - **Summarization** (1):
    - `clarity-operator-brief-structurer` v1.0.0
  - **Legal Reasoning** (1):
    - `clarity-legal-argument-mapper` v1.0.0
- 1 agent, 1 of 5 agent categories:
  - **Operator** (1):
    - `clarity-operator-agent` **v1.0.1** (now references 8 skills;
      `baseline_hash` frozen at v1.0.0 birth-state)
- Manifest schema 2.0.0. Governance layer 2.0.0. Agent kernel 1.0.0.
  All unchanged — additive content release only.
- 11 governance / enforcement / kernel files. `SKILL_TAXONOMY.md`
  bumped to 1.0.4; all others unchanged.
- Integrity suite passes (8 × OK skills, 1 × OK agent).
- Drift Detector: `DRIFT: NONE` against the regenerated v2.0.0 baseline.
- Governance Self-Test: `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Post-kernel walk-around-the-block validated
end-to-end. The agent kernel handled the new skill addition cleanly:
the agent schema's `skills_used` cross-reference accepted the new skill
name; the self-test's "agent skills_used entries reference existing
skills" check passed; the drift detector caught all changes mid-flight
and returned to clean after baseline regeneration. The
`baseline_hash`-immutability invariant survived its first test on the
agent side. The system is ready for further skill additions and the
next Maximum Vision Path step.

---

## Governance v2.0.0 — Second Walk: Legal Reasoning #2 + Operator Agent v1.0.2

Released: 2026-05-08

The second walk-around-the-block release after the v2.0.0 agent kernel
initialization. **No governance procedure changes; no schema changes;
no script changes.** Same release shape as the prior walk: one new
skill (Legal Reasoning #2, joining `clarity-legal-argument-mapper`)
and one Operator Agent edit (v1.0.1 → v1.0.2). Two baseline
regenerations as spec'd. `baseline_version`, `manifest_version`,
`schema_version`, `governance_layer_version`, and `agent_kernel_version`
all unchanged.

### New skill

- Added `clarity-legal-precedent-extractor.md` (skill-version 1.0.0)
  under category **Legal Reasoning**. Second skill in Legal Reasoning,
  joining `clarity-legal-argument-mapper`. Extracts, normalizes, and
  structures legal precedents referenced in text — case names,
  citations, holdings, and relevance statements — as a deterministic
  JSON array of precedent objects with per-precedent confidence.
  Distinguished from `clarity-legal-argument-mapper` by primary
  output: that skill maps the **whole argument architecture**; this
  skill produces a **focused precedent catalogue** (atomized
  precedents that an argument map can hang from).
  `governance_version: 1.1.0`; `baseline_hash` recorded at first
  commit (= initial `md_sha256`, frozen forever per `VERSIONING.md`).
- Added `clarity-legal-precedent-extractor.zip` containing `SKILL.md`
  byte-identical to source.
- Manifest entry includes the 13 schema-1.2.0 required fields plus
  three additive optional fields: `input_shape`, `output_shape`,
  `dependencies`. Same descriptive-metadata-only treatment as the
  Timeline Construction #2 release; formal schema 1.3.0 ratification
  remains deferred.

### Operator Agent update

- Updated `clarity-operator-agent.md`: appended
  `clarity-legal-precedent-extractor` to `skills_used` (now 9
  skills); body Skills Composition section adds a one-line
  description of the new skill's selection criteria. Manifest agent
  entry bumped 1.0.1 → 1.0.2 (patch — additive `skills_used`
  entry, non-semantic edit otherwise) with refreshed `md_sha256`
  and `md_bytes`.
- **`baseline_hash` frozen** at the original v1.0.0 birth-state
  (`0cea5f13ce29b3ec40c77890c959c6d7e4bd0fb79062c2cd3b7a1a9edf7a9600`)
  per `VERSIONING.md` immutability rule. Second consecutive agent
  bump that exercises the immutability invariant; the
  `md_sha256` ≠ `baseline_hash` divergence on the agent now spans
  two version increments.

### Other updates

- Updated `SKILL_TAXONOMY.md` 1.0.4 → 1.0.5 (patch — § F mapping
  refresh; one new row).
- Updated `README.md` Contents table (two new rows).
- Regenerated `BASELINE_STATE.json` twice as spec'd.
  `baseline_version` stays at `2.0.0` per release pattern.

State at end of release:

- 9 skills, 5 categories — four categories now hold two skills, one
  still singleton:
  - **Narrative Analysis** (2):
    - `clarity-narrative-litigation` v1.0.1
    - `clarity-narrative-spine-builder` v1.0.0
  - **Evidence Extraction** (2):
    - `clarity-contradictions-extractor` v1.0.1
    - `clarity-evidence-anchor-extractor` v1.0.0
  - **Timeline Construction** (2):
    - `clarity-timeline-mapper` v1.0.1
    - `clarity-temporal-event-normalizer` v1.0.0
  - **Legal Reasoning** (2):
    - `clarity-legal-argument-mapper` v1.0.0
    - `clarity-legal-precedent-extractor` v1.0.0  ← new
  - **Summarization** (1):
    - `clarity-operator-brief-structurer` v1.0.0
- 1 agent, 1 of 5 agent categories:
  - **Operator** (1):
    - `clarity-operator-agent` **v1.0.2** (now references 9 skills;
      `baseline_hash` frozen at v1.0.0 birth-state through two version
      bumps)
- Manifest schema 2.0.0. Governance layer 2.0.0. Agent kernel 1.0.0.
  All unchanged.
- `SKILL_TAXONOMY.md` bumped to 1.0.5; all other governance files
  unchanged.
- Integrity suite passes (9 × OK skills, 1 × OK agent).
- Drift Detector: `DRIFT: NONE` against the regenerated v2.0.0 baseline.
- Governance Self-Test: `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Second post-kernel walk validated end-to-end.
Summarization is now the only remaining singleton category. The
release pattern (one skill + one agent edit + two baseline regens) is
the established cadence; the agent absorbs new skills cleanly via
`skills_used` append; the `baseline_hash`-immutability invariant
holds across consecutive agent bumps. System ready for the next walk
or the next Maximum Vision Path step, whichever comes first.

---

## Governance v2.0.0 — Third Walk: Summarization #2 + Operator Agent v1.0.3 (full 5×2 coverage)

Released: 2026-05-08

The third walk-around-the-block release after the v2.0.0 agent kernel
initialization. Closes the singleton-category gap: **all five taxonomy
categories now hold two skills each (5×2 full coverage)**. **No
governance procedure changes; no schema changes; no script changes.**
Same release shape as the prior two walks. `baseline_version`,
`manifest_version`, `schema_version`, `governance_layer_version`, and
`agent_kernel_version` all unchanged.

### New skill

- Added `clarity-summarization-contrastive-brief.md` (skill-version
  1.0.0) under category **Summarization**. Second skill in
  Summarization, joining `clarity-operator-brief-structurer`.
  Produces a contrastive brief over a multi-document record:
  single JSON object with a `sections` array (sectioned narrative
  summary) plus explicit `agreements`, `disagreements`, and `gaps`
  blocks keyed by issue. Distinguished from
  `clarity-operator-brief-structurer` by primary output: that skill
  produces a **single-perspective brief** in the fixed Situation /
  Assessment / Key Points / Recommended Actions structure; this
  skill produces a **multi-position contrastive brief** that
  preserves the structure of disagreement.
  `governance_version: 1.1.0`; `baseline_hash` recorded at first
  commit (= initial `md_sha256`, frozen forever per `VERSIONING.md`).
- Added `clarity-summarization-contrastive-brief.zip` containing
  `SKILL.md` byte-identical to source.
- Manifest entry includes the 13 schema-1.2.0 required fields plus
  three additive optional fields (`input_shape`, `output_shape`,
  `dependencies`). Same descriptive-metadata-only treatment as the
  prior two walks; formal schema 1.3.0 ratification still deferred.

### Operator Agent update

- Updated `clarity-operator-agent.md`: appended
  `clarity-summarization-contrastive-brief` to `skills_used` (now
  10 skills); body Skills Composition section adds a one-line
  description of the new skill's selection criteria. Manifest agent
  entry bumped 1.0.2 → 1.0.3 (patch — additive `skills_used`
  entry, non-semantic edit otherwise) with refreshed `md_sha256`
  and `md_bytes`.
- **`baseline_hash` frozen** at the original v1.0.0 birth-state
  (`0cea5f13ce29b3ec40c77890c959c6d7e4bd0fb79062c2cd3b7a1a9edf7a9600`)
  per `VERSIONING.md` immutability rule. **Third consecutive agent
  bump** that exercises the immutability invariant; the
  `md_sha256` ≠ `baseline_hash` divergence on the agent now spans
  three version increments (1.0.0 → 1.0.1 → 1.0.2 → 1.0.3).

### Other updates

- Updated `SKILL_TAXONOMY.md` 1.0.5 → 1.0.6 (patch — § F mapping
  refresh; one new row).
- Updated `README.md` Contents table (two new rows).
- Regenerated `BASELINE_STATE.json` twice as spec'd.
  `baseline_version` stays at `2.0.0` per release pattern.

State at end of release:

- 10 skills, 5 categories — **full 5×2 coverage achieved**:
  - **Narrative Analysis** (2):
    - `clarity-narrative-litigation` v1.0.1
    - `clarity-narrative-spine-builder` v1.0.0
  - **Evidence Extraction** (2):
    - `clarity-contradictions-extractor` v1.0.1
    - `clarity-evidence-anchor-extractor` v1.0.0
  - **Timeline Construction** (2):
    - `clarity-timeline-mapper` v1.0.1
    - `clarity-temporal-event-normalizer` v1.0.0
  - **Legal Reasoning** (2):
    - `clarity-legal-argument-mapper` v1.0.0
    - `clarity-legal-precedent-extractor` v1.0.0
  - **Summarization** (2):
    - `clarity-operator-brief-structurer` v1.0.0
    - `clarity-summarization-contrastive-brief` v1.0.0  ← new
- 1 agent, 1 of 5 agent categories:
  - **Operator** (1):
    - `clarity-operator-agent` **v1.0.3** (now references 10 skills;
      `baseline_hash` frozen at v1.0.0 birth-state through three
      version bumps)
- Manifest schema 2.0.0. Governance layer 2.0.0. Agent kernel 1.0.0.
  All unchanged.
- `SKILL_TAXONOMY.md` bumped to 1.0.6; all other governance files
  unchanged.
- Integrity suite passes (10 × OK skills, 1 × OK agent).
- Drift Detector: `DRIFT: NONE` against the regenerated v2.0.0 baseline.
- Governance Self-Test: `GOVERNANCE SELF-TEST: OK`.

**Phase status:** Third post-kernel walk validated end-to-end. The
library has reached **full 5×2 coverage** under the v2.0.0 agent
kernel — every taxonomy category holds two skills distinguished by
primary output. The release pattern (one skill, one agent edit, two
baseline regens) is now established as the rhythm. The
`baseline_hash`-immutability invariant has held across three
consecutive agent bumps, with `md_sha256` diverging from
`baseline_hash` by an ever-larger content delta each release. Natural
next steps: (1) schema 1.3.0 ratification for the additive fields;
(2) a second agent (Analyst, Reviewer, Composer, or Custodian
category); (3) Maximum Vision Path beyond the kernel.

---

## Governance v2.0.0 — Schema 1.3.0 Ratification

Released: 2026-05-08

Library-wide schema upgrade. The three previously-additive fields —
`input_shape`, `output_shape`, `dependencies` — are now **mandatory**
on every skill and **enforced** by the governance self-test. Schema
1.3.0 ratifies what the last three walks treated as descriptive
metadata. This is not a content release; it is a schema discipline
release.

### Reconciliation note: schema_version vs manifest_version

The spec set `schema_version: 1.3.0` at top of `MANIFEST.json`. Prior
state had both `manifest_version` and `schema_version` at `2.0.0`
(set lockstep at the agent kernel introduction). The v2.0.0 self-test
enforced equality between them.

This release intentionally diverges them:

- `manifest_version` — tracks the **manifest's structural schema**
  (top-level blocks: governance, skills, agents, etc.). Stays at
  `2.0.0`. Bumps on structural manifest changes (e.g., the agent kernel
  jump from 1.2.0 to 2.0.0).
- `schema_version` — tracks the **per-skill content schema** (what
  fields each skill entry must have). Goes 2.0.0 → `1.3.0` per spec —
  resuming the per-skill schema line that ran 1.0.0 → 1.1.0 → 1.2.0
  before the agent kernel collapsed both fields to 2.0.0.
- The self-test's equality check is **softened** in v2.1.0 to require
  only that both are valid semver. Divergence is now an intentional
  signal, not a violation.

### Schema 1.3.0 — required fields per skill

```yaml
# skill .md frontmatter (and manifest entry):
input_shape: >
  <non-empty string describing the input shape the skill consumes>
output_shape: >
  <non-empty string describing the output shape the skill produces>
dependencies: []   # list, may be empty; items must be skill `name` strings
```

The governance self-test enforces:

- `input_shape` present and non-empty (string).
- `output_shape` present and non-empty (string).
- `dependencies` present (may be empty list); items must reference
  skills that exist in `MANIFEST.json`.

### Library-wide migration

Three skills already complied (Walks #1–3): `clarity-temporal-event-normalizer`,
`clarity-legal-precedent-extractor`, `clarity-summarization-contrastive-brief`.
**Seven skills required frontmatter migration** in this release:

| Skill | Version bump |
|---|---|
| `clarity-narrative-litigation` | 1.0.1 → 1.0.2 |
| `clarity-contradictions-extractor` | 1.0.1 → 1.0.2 |
| `clarity-timeline-mapper` | 1.0.1 → 1.0.2 |
| `clarity-operator-brief-structurer` | 1.0.0 → 1.0.1 |
| `clarity-legal-argument-mapper` | 1.0.0 → 1.0.1 |
| `clarity-narrative-spine-builder` | 1.0.0 → 1.0.1 |
| `clarity-evidence-anchor-extractor` | 1.0.0 → 1.0.1 |

Each migration: added the three required frontmatter fields with
descriptions reflecting each skill's actual input/output shape; no
other content changes. `.md` rehashed; `.zip` regenerated; manifest
entry updated with new `md_sha256`/`zip_sha256`/`md_bytes`/`zip_bytes`
+ the three new fields. **`baseline_hash` frozen** for all 7 skills
per `VERSIONING.md` immutability rule. For the 4 skills born under
schema 1.2.0 (`clarity-operator-brief-structurer`,
`clarity-legal-argument-mapper`, `clarity-narrative-spine-builder`,
`clarity-evidence-anchor-extractor`), this is their first
`md_sha256` ≠ `baseline_hash` divergence — the immutability invariant
exercised on these 4 for the first time.

### Governance file changes

- **`SKILL_TEMPLATE.md`** v1.2.0 → v1.3.0. Frontmatter now includes
  `input_shape`, `output_shape`, `dependencies` as required fields.
  Governance Compliance Checklist updated. Template notes describe
  validation rules.
- **`CREATE_NEW_SKILL_INSTRUCTIONS.md`** v1.2.0 → v1.3.0. Validation
  Checklist additions for the three new fields. New "Schema 1.3.0 —
  Enforcement Notes" section.
- **`INTEGRITY_CHECKS.md`** v1.0.0 → v1.1.0 (minor — additive checks).
  New § 6 "Schema 1.3.0 — required `input_shape`, `output_shape`,
  `dependencies`" with PowerShell verification snippet.
- **`GOVERNANCE_SELF_TEST.ps1`** v2.0.0 → v2.1.0. Three new schema
  1.3.0 enforcement checks (input_shape non-empty, output_shape
  non-empty, dependencies field-present-and-resolves). Equality check
  between `manifest_version` and `schema_version` softened to "both
  valid semver" with informational note when they diverge. Total
  checks: 23 (was 19).
- **`SKILL_TAXONOMY.md`** v1.0.6 → v1.0.7. Added enforcement note
  after § F.

### Other updates

- `MANIFEST.json` top-level: `schema_version` 2.0.0 → 1.3.0;
  `manifest_version` stays at 2.0.0. Each of the 7 migrated skill
  entries gets the three new fields appended after `baseline_hash`,
  plus refreshed hash/byte values and bumped `version`.
- `README.md`: added schema 1.3.0 enforcement bullet to the Governance
  consistency rules; noted the legitimate `manifest_version` vs
  `schema_version` divergence.
- `BASELINE_STATE.json` regenerated twice as spec'd.
  `baseline_version` stays at `2.0.0` per release pattern.

### Operator Agent update (Phase B)

- Updated `clarity-operator-agent.md`: small Behavioral Model addition
  noting that under schema 1.3.0+ the standardized
  `input_shape` / `output_shape` / `dependencies` fields are available
  for agent composition planning. Manifest agent entry bumped
  1.0.3 → 1.0.4 with refreshed `md_sha256` and `md_bytes`.
- **`baseline_hash` frozen** at original v1.0.0 birth-state
  (`0cea5f13...`). Fourth consecutive agent bump exercising the
  immutability invariant.

State at end of release:

- 10 skills, 5 categories — 5×2 coverage preserved. All 10 skills
  carry `input_shape` + `output_shape` + `dependencies` (3 already had
  them; 7 newly migrated). Skill versions:
  - **Narrative Analysis** (2): `clarity-narrative-litigation` v1.0.2; `clarity-narrative-spine-builder` v1.0.1.
  - **Evidence Extraction** (2): `clarity-contradictions-extractor` v1.0.2; `clarity-evidence-anchor-extractor` v1.0.1.
  - **Timeline Construction** (2): `clarity-timeline-mapper` v1.0.2; `clarity-temporal-event-normalizer` v1.0.0 (already compliant).
  - **Legal Reasoning** (2): `clarity-legal-argument-mapper` v1.0.1; `clarity-legal-precedent-extractor` v1.0.0 (already compliant).
  - **Summarization** (2): `clarity-operator-brief-structurer` v1.0.1; `clarity-summarization-contrastive-brief` v1.0.0 (already compliant).
- 1 agent: `clarity-operator-agent` **v1.0.4** (still references 10
  skills; `baseline_hash` frozen through 4 version bumps).
- Manifest: `manifest_version` 2.0.0 (unchanged); `schema_version`
  2.0.0 → **1.3.0**; `governance_layer_version` 2.0.0 (unchanged);
  `agent_kernel_version` 1.0.0 (unchanged).
- 11 governance / enforcement / kernel files. Bumped this release:
  `SKILL_TEMPLATE.md` 1.2.0 → 1.3.0; `CREATE_NEW_SKILL_INSTRUCTIONS.md`
  1.2.0 → 1.3.0; `INTEGRITY_CHECKS.md` 1.0.0 → 1.1.0;
  `GOVERNANCE_SELF_TEST.ps1` 2.0.0 → 2.1.0; `SKILL_TAXONOMY.md`
  1.0.6 → 1.0.7. Unchanged: `VERSIONING.md`, `AGENT_SPEC_TEMPLATE.md`,
  `AGENT_TAXONOMY.md`, `DRIFT_DETECTOR.ps1`, `GOVERNANCE_CHANGELOG.md`
  (file-version unchanged — content appended).
- Integrity suite passes (10 × OK skills, 1 × OK agent).
- Drift Detector: `DRIFT: NONE` against the regenerated v2.0.0 baseline.
- Governance Self-Test: `GOVERNANCE SELF-TEST: OK` (23/23 checks).

**Phase status:** Schema 1.3.0 ratified and enforced. The library's
per-skill schema is now back in lockstep with the per-skill content
discipline (input/output explicitly declared, dependencies tracked).
The dual-version convention (`manifest_version` for structure;
`schema_version` for per-skill content) is now formal. Natural next
steps: (1) bring `dependencies` to life — first skill that actually
declares an upstream dependency; (2) second agent under a different
agent taxonomy category; (3) drift-detector tracking of the new
fields against baseline (currently only self-test enforces presence).

---

## Governance v2.0.0 — First Dependency-Bearing Skill: clarity-evidence-chain-normalizer (Evidence Extraction #3)

Released: 2026-05-08

The first skill in the library to declare a real, non-empty
`dependencies` array — exercising schema 1.3.0's dependency-resolution
check end-to-end. Also the first **third skill in a category**
(Evidence Extraction now holds three; the two prior in-category
expansions stopped at two each). No governance procedure changes; no
schema changes; no script changes. Same release shape as the prior
walks: one new skill (Phase A) + Operator Agent edit (Phase B); two
baseline regenerations.

### New skill

- Added `clarity-evidence-chain-normalizer.md` (skill-version 1.0.0)
  under category **Evidence Extraction**. Third skill in Evidence
  Extraction, joining `clarity-contradictions-extractor` (finds
  conflicts) and `clarity-evidence-anchor-extractor` (finds supports).
  This skill consumes the anchor extractor's output and elevates it
  into a stable **evidence chain**: canonicalizes references,
  resolves cross-links, groups connected anchors into stable
  `chain-NNN` identifiers, and flags orphan anchors.
- **`dependencies: ["clarity-evidence-anchor-extractor"]`** — first
  non-empty dependencies array in the library. The schema 1.3.0
  self-test verifies that the named dependency exists in
  `MANIFEST.json`'s skills array and resolves cleanly. This release
  brings the dependency machinery to life rather than testing only
  empty-list cases.
- Added `clarity-evidence-chain-normalizer.zip` containing `SKILL.md`
  byte-identical to source.
- Manifest entry includes the 13 schema-1.2.0 required fields plus
  the three schema-1.3.0 fields. `dependencies: ["clarity-evidence-anchor-extractor"]`.
- `governance_version: 1.1.0`; `baseline_hash` recorded at first commit
  (= initial `md_sha256`, frozen).

### The Evidence Extraction pipeline

The category now demonstrates a **natural pipeline** rather than just
sibling differentiation:

```
raw text  ->  clarity-evidence-anchor-extractor  ->  anchor table
anchor table  ->  clarity-evidence-chain-normalizer  ->  evidence chain
raw text  ->  clarity-contradictions-extractor  ->  contradictions list
```

The chain normalizer does not extract from raw text; it consumes the
anchor extractor's output. This is the first explicit
upstream/downstream skill relationship in the library, formalized via
the new `dependencies` field.

### Operator Agent update

- Updated `clarity-operator-agent.md`: appended
  `clarity-evidence-chain-normalizer` to `skills_used` (now 11
  skills); body Skills Composition section adds a one-line
  description noting it consumes the anchor extractor's output.
  Manifest agent entry bumped 1.0.4 → 1.0.5 (patch — additive
  `skills_used` entry, non-semantic edit otherwise) with refreshed
  `md_sha256` and `md_bytes`.
- **`baseline_hash` frozen** at the original v1.0.0 birth-state
  (`0cea5f13ce29b3ec40c77890c959c6d7e4bd0fb79062c2cd3b7a1a9edf7a9600`)
  per `VERSIONING.md` immutability rule. **Fifth consecutive agent
  bump** spanning the same frozen birth-state hash.

### Other updates

- Updated `SKILL_TAXONOMY.md` 1.0.7 → 1.0.8 (patch — § F mapping
  refresh; one new row marking the first dependency-bearing skill).
- Updated `README.md` Contents table (two new rows).
- Regenerated `BASELINE_STATE.json` twice as spec'd.
  `baseline_version` stays at `2.0.0` per release pattern.

State at end of release:

- 11 skills, 5 categories — Evidence Extraction now has 3:
  - **Narrative Analysis** (2): `clarity-narrative-litigation` v1.0.2; `clarity-narrative-spine-builder` v1.0.1.
  - **Evidence Extraction** (3): `clarity-contradictions-extractor` v1.0.2; `clarity-evidence-anchor-extractor` v1.0.1; `clarity-evidence-chain-normalizer` v1.0.0 ← new.
  - **Timeline Construction** (2): `clarity-timeline-mapper` v1.0.2; `clarity-temporal-event-normalizer` v1.0.0.
  - **Legal Reasoning** (2): `clarity-legal-argument-mapper` v1.0.1; `clarity-legal-precedent-extractor` v1.0.0.
  - **Summarization** (2): `clarity-operator-brief-structurer` v1.0.1; `clarity-summarization-contrastive-brief` v1.0.0.
- 1 agent: `clarity-operator-agent` **v1.0.5** (now references 11
  skills; `baseline_hash` frozen through 5 version bumps).
- Manifest schema unchanged: `manifest_version: 2.0.0`,
  `schema_version: 1.3.0`, `governance_layer_version: 2.0.0`,
  `agent_kernel_version: 1.0.0`.
- 11 governance / enforcement / kernel files. `SKILL_TAXONOMY.md`
  bumped to 1.0.8; all others unchanged.
- Integrity suite passes (11 × OK skills, 1 × OK agent).
- Drift Detector: `DRIFT: NONE` against the regenerated v2.0.0 baseline.
- Governance Self-Test: `GOVERNANCE SELF-TEST: OK` (22 checks,
  including the dependency-resolution check now exercising a
  non-empty list).

**Phase status:** Schema 1.3.0's dependency machinery is now live. The
self-test's "all skills have dependencies field; all referenced
skills resolve" check has its first non-trivial pass — a real upstream
reference resolves correctly. The Evidence Extraction category
demonstrates a natural three-skill pipeline (raw text → anchors →
chain; raw text → contradictions). Library-side milestones reached:
first 3-skill category, first dependency edge, first pipeline
formalized in metadata.

---

## How to record a new governance release

When the governance layer changes — a new enforcement artifact, a
revised gate procedure, a schema change to `BASELINE_STATE.json`, etc.
— append a new section to this file in the same shape as above:

1. Heading: `## Governance vX.Y.Z — <Short Name>`
2. `Released: YYYY-MM-DD` line.
3. One-paragraph summary of the release intent.
4. Bulleted list of the concrete additions / changes.
5. `State at end of vX.Y.Z:` block listing the post-release inventory.

The bump rule is the same as for skills:

- Patch — non-semantic edits to governance files (typos, formatting,
  rewording without changing behavior).
- Minor — additive enforcement (a new check, a new artifact, an
  expanded gate) that does not break the existing procedure.
- Major — breaking changes to the governance procedure (renamed gate
  step, removed enforcement artifact, restructured baseline schema).

After recording the release, regenerate `BASELINE_STATE.json` so the
drift detector takes the new state as its reference point.
