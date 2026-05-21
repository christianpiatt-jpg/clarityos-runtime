# Clarity Skills — Perplexity Format

This folder contains Perplexity-compatible skill files generated from
general-case patterns in the Clarity Library. Each skill packages a
single operator-grade analysis method into a reusable, uploadable file.

## Contents

| File | Purpose |
|---|---|
| `clarity-narrative-litigation.md` | Analyze legal motions, briefs, or agency filings using narrative-architecture |
| `clarity-narrative-spine-builder.md` | Extract the narrative spine of any document (actors, conflict, stakes, causal chain, institutional posture, frame, omissions) |
| `clarity-contradictions-extractor.md` | Extract and classify contradictions in any document |
| `clarity-evidence-anchor-extractor.md` | Extract and classify evidence anchors (facts, citations, exhibits, data, witness references) and map them to issues/claims |
| `clarity-timeline-mapper.md` | Build chronological timelines and surface temporal conflicts |
| `clarity-temporal-event-normalizer.md` | Normalize ambiguous temporal expressions to canonical ISO 8601 atomic events with per-event confidence (the substrate for timeline assembly) |
| `clarity-operator-brief-structurer.md` | Compress complex documents into operator-grade briefs (Situation / Assessment / Key Points / Recommended Actions) |
| `clarity-legal-argument-mapper.md` | Map the legal argument structure of a document (issues, standards, elements, evidence, burdens, dependencies, gaps) |
| `clarity-legal-precedent-extractor.md` | Extract case-law precedents referenced in legal text into structured precedent objects (case name, citation, holding, relevance, confidence) |
| `clarity-summarization-contrastive-brief.md` | Produce a contrastive brief over a multi-document record (sectioned summary + agreements / disagreements / gaps blocks) |
| `clarity-evidence-chain-normalizer.md` | Normalize the output of `clarity-evidence-anchor-extractor` into a stable evidence chain (canonicalized references, resolved cross-links, `chain-NNN` identifiers; **first dependency-bearing skill**) |
| `clarity-narrative-litigation.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-narrative-spine-builder.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-contradictions-extractor.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-evidence-anchor-extractor.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-timeline-mapper.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-temporal-event-normalizer.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-operator-brief-structurer.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-legal-argument-mapper.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-legal-precedent-extractor.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-summarization-contrastive-brief.zip` | Uploadable bundle (contains `SKILL.md`) |
| `clarity-evidence-chain-normalizer.zip` | Uploadable bundle (contains `SKILL.md`) |

Each `.zip` contains a single file at its root named `SKILL.md`, identical
in content to the matching `.md` file in this folder.

---

## How to Upload These Skills to Perplexity

1. Sign in to Perplexity in your browser.
2. Open the skills configuration area (Settings → Skills, or the equivalent
   surface in your Perplexity workspace).
3. Choose **Upload Skill** (or the equivalent "Add" / "Import" action).
4. Select the `.zip` file for the skill you want to install. Perplexity
   expects an archive containing a single `SKILL.md` at the archive root —
   that is exactly what these zips provide.
5. Confirm the parsed `name` and `description` match the YAML frontmatter
   in the file.
6. Save / activate the skill.

If your Perplexity surface offers a "create from text" or "paste markdown"
option instead of zip upload, you can paste the contents of the matching
`.md` file directly — the YAML frontmatter and body are already in the
expected shape.

---

## How to Create a New Skill (Same Pattern)

1. Pick a `name` that is **lowercase and hyphen-only** (e.g.
   `clarity-statute-mapper`). The name doubles as the filename and as the
   skill's identifier in Perplexity.

2. Create `clarity_skills/perplexity/<name>.md` with this skeleton:

   ```markdown
   ---
   name: <skill-name>
   description: >
     One or two sentences describing trigger phrases and the outputs the
     skill produces. Be explicit about WHEN the skill should fire — the
     description is what Perplexity matches against to decide whether to
     invoke the skill.
   ---

   # <Title Case Name>

   ## Purpose
   One paragraph: what the skill does and what it produces.

   ## Instructions

   ### 1. <First step>
   - <atomic action>
   - <atomic action>

   ### 2. <Second step>
   ...

   ## Example Input
   "<a representative user prompt>"

   ## Example Output
   <a concise illustration of the output shape>
   ```

3. Validate the file before zipping:
   - YAML frontmatter parses (no tab characters; use spaces).
   - No personally-identifying information.
   - No case-specific facts (see boundary note below).
   - Total file size under 10 MB.
   - Plain UTF-8, LF or CRLF line endings.

4. Build the upload bundle. From PowerShell, run from this folder:

   ```powershell
   $name = "<skill-name>"
   $tmp  = Join-Path $env:TEMP ("skill_" + [guid]::NewGuid())
   New-Item -ItemType Directory -Path $tmp -Force | Out-Null
   Copy-Item "$name.md" (Join-Path $tmp "SKILL.md")
   Compress-Archive -Path (Join-Path $tmp "SKILL.md") `
                    -DestinationPath "$name.zip" -Force
   Remove-Item $tmp -Recurse -Force
   ```

   The result is `clarity_skills/perplexity/<name>.zip` with a single
   `SKILL.md` at its root.

5. Commit both `<name>.md` and `<name>.zip` in the same change so they
   stay in sync.

---

## Boundary Contract (Important)

These skills live in **Layer 1 — General Case**. They encode reasoning
*methods*, not case material. They must NOT contain:

- Personally-identifying information of any individual
- Names, dates, or reference numbers tied to a specific particular case
  (e.g. VA_LITIGATION, MSJ_OPPOSITION)
- Quoted excerpts from filings, emails, or agency records
- Anything that would make the skill useful only inside one engagement

If a skill needs case-specific context to do its job, that context belongs
in the particular-case workspace (Layer 2), supplied as the *input* to the
skill. The skill itself stays general.

A useful audit step before committing a new skill: grep the file for
forbidden tokens (names of involved parties, agency case numbers, dates of
specific contested events). If any appear, generalize them or remove them.

---

## How to Extend the Skill Library Over Time

A few patterns that keep the library coherent as it grows:

1. **One skill per discrete method.** Resist the urge to merge. A skill
   that tries to do contradictions *and* timelines *and* identity threads
   in one pass is harder to trigger reliably than three focused skills
   that compose.

2. **Spend the description on triggers.** The body teaches the method,
   but the `description` decides whether the skill fires at all. Use it
   to enumerate the phrases and tasks that should activate the skill.

3. **Numbered, atomic instructions.** Each step should be executable in
   isolation. Avoid prose paragraphs inside the Instructions section —
   they invite the model to summarize rather than execute.

4. **Generic examples.** The Example Input / Example Output blocks should
   show the *shape* of the interaction, never real case material. If your
   examples can only be understood with insider context, they're too
   specific.

5. **Version material revisions.** When you change a skill in a way that
   alters its behavior, bump a `version:` field in the frontmatter (e.g.
   `version: 2`). Keep prior versions under
   `clarity_skills/perplexity/archive/<name>.v1.md` if they're still
   useful as references.

6. **Re-zip after every edit.** The `.md` and `.zip` must stay in sync,
   because Perplexity uploads consume the zip. The PowerShell snippet
   above works for any skill name.

7. **Audit before commit.** A 30-second grep for PII / case tokens is
   cheaper than a leak. Treat the skill folder like a public artifact,
   because uploaded skills effectively are.

---

## Provenance

These skills were derived from general-case structural patterns in
`Clarity_OS_Operating_System/Clarity_Library/` — specifically the
Narrative Architecture, Contradictions, Timelines, Institutional
Topology, and Identity Threads bodies. They consume nothing from the
ClarityOS runtime and the runtime consumes nothing from them; see
`ARCHITECTURE.md` and `skills_export/` for the broader skills boundary
policy.

---

## Skill Generation Pipeline

The folder is structured as a repeatable, deterministic pipeline. Three
artifacts work together to keep new skills consistent with existing ones:

| File | Role |
|---|---|
| `SKILL_TEMPLATE.md` | The blank form. Contains placeholder tokens for every field a skill needs and a notes block explaining each placeholder. |
| `CREATE_NEW_SKILL_INSTRUCTIONS.md` | The procedure. Step-by-step instructions, the canonical PowerShell zip snippet, and the validation checklist. |
| `MANIFEST.json` | The registry. Every skill currently in the folder, with filenames, descriptions, versions, and SHA256 hashes for both the `.md` and the `.zip`. |

### How to use `SKILL_TEMPLATE.md`

`SKILL_TEMPLATE.md` is the source of truth for skill shape. It carries
placeholder tokens — `{{skill-name}}`, `{{skill-description}}`,
`{{Skill Title}}`, `{{purpose}}`, `{{instructions}}`, `{{examples}}` —
plus a trailing comment block that documents what each token expects.

Never edit `SKILL_TEMPLATE.md` to author a new skill. Duplicate it first:

```powershell
Copy-Item SKILL_TEMPLATE.md "<skill-name>.md"
```

Then open the copy and replace every placeholder. Delete the template
notes comment before saving. The result is a clean skill file that
mirrors the structure of every other skill in the folder.

If the template itself ever needs to evolve (e.g. you want to add a new
section every skill should carry), edit it directly — but treat that as
a pipeline-level change, not a skill-authoring step, and update existing
skills to match the new shape if you want them consistent.

### How to follow `CREATE_NEW_SKILL_INSTRUCTIONS.md`

`CREATE_NEW_SKILL_INSTRUCTIONS.md` is the runbook. Open it whenever you
add a skill and walk through the six steps — duplicate the template,
fill the placeholders, save, zip, place in the folder, and update
`MANIFEST.json`. Don't skip the validation checklist at the end; it is
designed to catch the failure modes that break Perplexity uploads or
contaminate Layer 1.

The instruction file gives two PowerShell variants for producing the
zip (Option A renames the source file in place; Option B uses a temp
directory). Either works. Both produce a zip with exactly one entry,
`SKILL.md` at the archive root, byte-identical to `<skill-name>.md`.

### How to update `MANIFEST.json`

Every change to the skills folder must be reflected in `MANIFEST.json`.
The manifest is the single registry the rest of the system relies on to
know what exists.

When you add a skill:

1. Append a new entry to the `skills` array in alphabetical order or
   logical grouping — match the shape of the existing entries.
2. Recompute both hashes:
   ```powershell
   (Get-FileHash -Algorithm SHA256 "<skill-name>.md").Hash.ToLower()
   (Get-FileHash -Algorithm SHA256 "<skill-name>.zip").Hash.ToLower()
   ```
   Paste them into `md_sha256` and `zip_sha256`.
3. Record `md_bytes` and `zip_bytes` from `(Get-Item <file>).Length`.
4. Set the new skill's `version` to `"1.0.0"`.
5. Bump the manifest's top-level `generated_at` to today's date.

When you revise an existing skill in a way that changes its behavior:

1. Bump that skill's `version` (e.g. `1.0.0` → `1.1.0`).
2. Recompute the two hashes and update them.
3. Bump `generated_at`.

When you remove a skill:

1. Delete its `.md` and `.zip` from the folder.
2. Remove its entry from the `skills` array.
3. Bump `generated_at`.

Verification one-liner — confirm a zip's `SKILL.md` matches the source
`.md`:

```powershell
# Extract SKILL.md from <skill-name>.zip and compare its hash to md_sha256.
$tmp = Join-Path $env:TEMP ("verify_" + [guid]::NewGuid())
Expand-Archive -LiteralPath "<skill-name>.zip" -DestinationPath $tmp
(Get-FileHash -Algorithm SHA256 (Join-Path $tmp "SKILL.md")).Hash.ToLower()
Remove-Item $tmp -Recurse -Force
```

### Keeping the skill library consistent over time

Three habits keep the folder coherent as it grows:

1. **Single source of truth per skill.** The `.md` is canonical; the
   `.zip` is a derived artifact. Never edit a zip directly. If the zip
   drifts from the `.md`, regenerate the zip — don't reconcile by
   editing both.
2. **Hashes in `MANIFEST.json` are the integrity contract.** If they
   stop matching the files, something is out of sync. The verification
   one-liner above is a 5-second check.
3. **Re-run the validation checklist on every change.** The checklist
   in `CREATE_NEW_SKILL_INSTRUCTIONS.md` is short and cheap. It catches
   the failure modes that take an hour to debug if they ship.

### How to avoid contaminating the personal envelope

Skills are Layer 1. The personal envelope (`VA_LITIGATION`,
`MSJ_OPPOSITION`, DOJ filings, evidence, named parties, contested dates,
agency case numbers) is Layer 2. The two layers are kept apart by the
contract laid out in `ARCHITECTURE.md`.

Concrete rules for this folder:

- Skill files describe **methods**. They never describe **cases**.
- An example in a skill file is a *shape*, not a real prompt. If your
  example only makes sense to someone with insider context on a specific
  matter, it is too specific — generalize it.
- Run a quick grep on every new skill before committing:
  ```powershell
  Select-String -Pattern "(VA|MSJ|DOJ|EEOC|MSPB|<your-name-here>)" `
                -LiteralPath "<skill-name>.md"
  ```
  Generic mentions of agencies as **categories** (e.g. "agency
  decisions") are fine; specific case material is not. Use judgment.
- If a method only works for one case, it is not a skill — it is a
  Layer 2 artifact and belongs in the particular-case workspace, not
  here.
- The `MANIFEST.json` `notes.boundary` field documents this rule
  inside the manifest itself. Treat it as binding.

If a skill ever ends up in this folder that violates the boundary,
remove it immediately, rotate any places it was uploaded (Perplexity
account skills), and update the manifest.

---

## Skill Library Governance

Two governance documents sit alongside the pipeline:

| File | Role |
|---|---|
| `VERSIONING.md` | Defines patch / minor / major bump rules, manifest update rules, and release discipline. Read before changing any skill version. |
| `INTEGRITY_CHECKS.md` | Defines the verification procedure: hash comparison against `MANIFEST.json`, structural checks (YAML / name format / size / zip layout), and contamination checks (PII, personal-envelope, case-specific material). |

Together with `SKILL_TEMPLATE.md`, `CREATE_NEW_SKILL_INSTRUCTIONS.md`,
and `MANIFEST.json`, they form the governance layer of the library.
The manifest's top-level `governance` block records the canonical
filenames of these documents so consumers can locate them
programmatically.

### How versioning works

Each skill carries a semver-style `MAJOR.MINOR.PATCH` version in its
`MANIFEST.json` entry. Skills start at `1.0.0`. Bumps follow the rules
in `VERSIONING.md`:

- **Patch** for non-semantic edits (typos, formatting, rewording
  without changing behavior, re-zipping after a tooling change).
- **Minor** for additive changes (a new instruction step, a new
  example, an expanded `description` with more triggers).
- **Major** for breaking changes (rename, restructured instructions,
  a removed step, output-shape changes, narrower triggers).

The manifest's own `manifest_version` follows the same scheme — it
versions the **schema** of `MANIFEST.json` itself, not the contents of
any particular skill. Adding the `governance` block bumped the schema
from `1.0.0` to `1.1.0` (additive ⇒ minor).

### How integrity checks work

`MANIFEST.json` records two SHA256 hashes per skill: one over the
source `.md`, one over the upload zip. `INTEGRITY_CHECKS.md` provides
the PowerShell snippets to recompute and compare them. The expected
output for a healthy library is one `OK` line per skill:

```
OK    clarity-narrative-litigation v1.0.0  md=True  zip=True
OK    clarity-contradictions-extractor v1.0.0  md=True  zip=True
OK    clarity-timeline-mapper v1.0.0  md=True  zip=True
```

Any `FAIL` line means the on-disk file diverges from the manifest. Do
not commit until every line is `OK`.

`INTEGRITY_CHECKS.md` also defines structural checks (YAML parses,
`name` is lowercase-hyphens-only, file under 10 MB, zip contains a
single `SKILL.md` at the root) and contamination checks (PII scan,
personal-envelope token grep, case-specificity heuristic). All three
sets — hash, structural, contamination — are bundled into the
**Pre-Commit Verification Suite** at the bottom of that document.

### How to update `MANIFEST.json`

The full procedure lives in `VERSIONING.md` § B. In short, every
change to a skill must:

1. Recompute `md_sha256` and `zip_sha256`.
2. Update `md_bytes` and `zip_bytes`.
3. Bump the per-skill `version` per the rules above.
4. Bump the top-level `generated_at` to today's date.

If the manifest's structure itself changes (new field, renamed field,
removed field), also bump `manifest_version`: additive ⇒ minor;
breaking ⇒ major.

### How to maintain consistency across the library

Three rules keep the library coherent as it grows:

1. **The `.md` is canonical; the `.zip` is derived.** Never edit a zip
   by hand. If the zip drifts from the `.md`, regenerate the zip — do
   not reconcile by editing both.
2. **`MANIFEST.json` hashes are the integrity contract.** When they
   stop matching the files, the library is broken until they match
   again. The library-wide verification snippet in
   `INTEGRITY_CHECKS.md` § A is a five-second check; run it before
   every commit.
3. **One change at a time.** Don't bundle a rename, a content
   revision, and a new skill into one update. Each becomes hard to
   review and harder to revert.

### How to avoid personal-envelope contamination

The previous section ("How to avoid contaminating the personal
envelope" under **Skill Generation Pipeline**) defines the rules in
detail. Governance adds two enforcement points on top of those rules:

1. **Contamination checks are part of the integrity suite.** Run the
   PII / personal-envelope grep from `INTEGRITY_CHECKS.md` § C on
   every new or revised skill. A hit must be removed or generalized
   before the manifest is updated.
2. **Major version bumps trigger a full re-audit.** Whenever a skill's
   major version changes (rename, restructure), re-run the full
   contamination suite — large edits are exactly when case-specific
   language tends to slip in.

If contamination is ever discovered post-commit, the response is the
same as in the previous section: remove the file immediately, rotate
any Perplexity workspace it was uploaded to, update the manifest, and
record the incident in your particular-case workspace (Layer 2) — not
here.

### How to run the verification steps before committing a new skill

Before committing any new or revised skill, walk this short sequence:

1. Run the **structural checks** from `INTEGRITY_CHECKS.md` § B
   against the new/changed `.md`.
2. Run the **contamination checks** from `INTEGRITY_CHECKS.md` § C.
3. Regenerate the `.zip` per `CREATE_NEW_SKILL_INSTRUCTIONS.md`.
4. Recompute both SHA256 hashes and update the manifest entry.
5. Bump the skill's `version` per `VERSIONING.md` and the top-level
   `generated_at`.
6. Run the **library-wide hash verification** from
   `INTEGRITY_CHECKS.md` § A. Confirm every skill returns `OK`.

The Pre-Commit Verification Suite in `INTEGRITY_CHECKS.md` runs steps
1–3 and the contamination scan as one PowerShell block — it is the
fastest way to walk the gate. Step 6 is the final library-wide pass
that confirms nothing else regressed.

Only after step 6 is clean is the skill ready to ship.

---

## Operationalization (Governance v1.1.0)

The governance layer is **active** as of v1.1.0. The four canonical
governance documents (`VERSIONING.md`, `INTEGRITY_CHECKS.md`,
`SKILL_TEMPLATE.md`, `CREATE_NEW_SKILL_INSTRUCTIONS.md`) are now backed
by four enforcement artifacts.

| File | Role |
|---|---|
| `BASELINE_STATE.json` | Frozen "known-good" snapshot of every file in the library at the moment v1.1.0 was declared operational. The reference point for drift detection. |
| `DRIFT_DETECTOR.ps1` | Compares the current state of the folder against `BASELINE_STATE.json` and reports `DRIFT: NONE` or an itemized list of mismatches (hash drift, missing files, unexpected new files, schema drift, BUILD_VERSION drift). |
| `GOVERNANCE_SELF_TEST.ps1` | Verifies the governance layer is internally consistent — all four canonical files exist, all are referenced in the manifest, schema version is well-formed, integrity tooling can hash them, baseline tracks them. Reports `GOVERNANCE SELF-TEST: OK` or itemized failures. |
| `GOVERNANCE_CHANGELOG.md` | Lifecycle history of the governance layer itself. v1.0.0 = initial release. v1.1.0 = enforcement layer. |

### When to run what

| Action | Run |
|---|---|
| Before committing any new or revised skill | Pre-Commit Verification Suite (`INTEGRITY_CHECKS.md`) **plus** Drift Detector **plus** Governance Self-Test (the six-check **Governance Gate**) |
| After committing a new or revised skill | Regenerate `BASELINE_STATE.json` and bump the relevant entry in `GOVERNANCE_CHANGELOG.md` if any governance file moved |
| Periodic library audit (weekly / before release) | `DRIFT_DETECTOR.ps1` and `GOVERNANCE_SELF_TEST.ps1` |
| After modifying any governance document itself | Bump the document's version in `BASELINE_STATE.json`, regenerate the baseline, run `GOVERNANCE_SELF_TEST.ps1`, append a changelog entry |

### The Governance Gate

`CREATE_NEW_SKILL_INSTRUCTIONS.md` now ends with a mandatory
**Governance Gate** section listing the six checks every skill must
clear before commit:

1. Version bump correct (per `VERSIONING.md`).
2. Manifest entry correct (per `MANIFEST.json` governance block).
3. Integrity suite passes (per `INTEGRITY_CHECKS.md` § A).
4. Contamination sweep clean (per `INTEGRITY_CHECKS.md` § C).
5. Drift Detector reports `DRIFT: NONE`.
6. Governance Self-Test reports `GOVERNANCE SELF-TEST: OK`.

The gate is the single choke point. A skill that does not clear all
six checks is not accepted, regardless of how clean each piece looks
individually.

### Running the scripts

The scripts are plain PowerShell. From a PowerShell prompt with the
working directory set anywhere:

```powershell
& "C:\ClarityOS_Code\clarity_skills\perplexity\DRIFT_DETECTOR.ps1"
& "C:\ClarityOS_Code\clarity_skills\perplexity\GOVERNANCE_SELF_TEST.ps1"
```

If your machine's `ExecutionPolicy` blocks unsigned scripts, invoke
them with the explicit interpreter:

```powershell
powershell -ExecutionPolicy Bypass -File `
  "C:\ClarityOS_Code\clarity_skills\perplexity\DRIFT_DETECTOR.ps1"
```

### Regenerating the baseline

Every authorized change to the library invalidates the prior baseline.
After committing the change, regenerate `BASELINE_STATE.json` so the
drift detector has a fresh reference point. The structure is fixed
(see the existing `BASELINE_STATE.json` in this folder); recompute
SHA256 for every tracked file, set per-file versions per
`VERSIONING.md`, bump `generated_at`, and write the JSON.

A future patch may ship a `REGENERATE_BASELINE.ps1` helper. For now,
regeneration is part of the manual release procedure.

### Phase summary

| Phase | Status |
|---|---|
| Phase 1 — Skill Template (`SKILL_TEMPLATE.md`) | done |
| Phase 2 — Skill Creation Pipeline (`CREATE_NEW_SKILL_INSTRUCTIONS.md`) | done |
| Phase 3 — Governance Layer (`VERSIONING.md`, `INTEGRITY_CHECKS.md`, manifest governance block, README governance section) | done |
| Phase 4 — Governance Enforcement (Gate, Baseline, Drift Detector, Self-Test, Changelog) | **done — v1.1.0 operational** |
| Phase 5 — Expansion Enablement (taxonomy, schema 1.2.0, baseline regen) | **done — v1.2.0 expansion enabled** |
| Phase 6 — First new skill under v1.2.0 | open |

---

## Phase 5: Expansion (Governance v1.2.0)

The governance layer is now operational, and the library is
structurally ready to expand. **No new skill may be created under
schema 1.1.0.** All new skills must comply with `SKILL_TAXONOMY.md`,
schema v1.2.0, and governance v1.1.0.

### What "Expansion Mode" means

Phase 5 is the regime under which new skills are admitted to the
library. The scaffolding is complete: a taxonomy fixes the category
vocabulary, a richer schema captures per-skill metadata, the template
and instructions guide authors through compliance, and the drift
detector + self-test enforce both at every commit.

### How the taxonomy works

`SKILL_TAXONOMY.md` defines a small, fixed set of top-level
categories. Every skill — existing or new — must declare exactly one
`category` value, drawn verbatim from § A of that file, in both its
frontmatter and its `MANIFEST.json` entry.

Categories are mutually exclusive at the top level. A skill is
classified by its **primary output**, not by what inputs it touches.
Adding, merging, or deprecating a category is itself a governance
change — see `SKILL_TAXONOMY.md` §§ B–E for the procedure and bump
rules.

The current taxonomy version is **1.0.0**. The categories are:
**Narrative Analysis**, **Evidence Extraction**, **Timeline
Construction**, **Legal Reasoning**, **Summarization**.

### How schema v1.2.0 works

Schema v1.2.0 extends each skill's `MANIFEST.json` entry with five
required fields:

| Field | Meaning |
|---|---|
| `category` | Verbatim string from `SKILL_TAXONOMY.md` § A. |
| `capabilities` | Non-empty list. What the skill produces or does well. |
| `limitations` | Non-empty list. What the skill explicitly does not do. |
| `governance_version` | The governance layer version under which the skill was first registered. Forensic record. |
| `baseline_hash` | The SHA256 of the skill's `.md` at first commit. Frozen forever. Distinct from `md_sha256` (current state). |

The same fields, except `baseline_hash`, also live in the skill's
frontmatter. `baseline_hash` is excluded from frontmatter to avoid
the self-reference problem (the hash of a file that contains its own
hash). The canonical value lives only in the manifest entry.

The manifest schema itself bumped `manifest_version` 1.1.0 → 1.2.0
and gained a peer `schema_version` field at the same value, plus
`taxonomy_file: "SKILL_TAXONOMY.md"` inside the `governance` block.

### How new skills must be created

Follow `CREATE_NEW_SKILL_INSTRUCTIONS.md` from start to finish — the
file now ends with both an **Expansion Mode (Schema 1.2.0)** section
and the **Governance Gate**. The short-form sequence:

1. Copy `SKILL_TEMPLATE.md` v1.2.0 to `<skill-name>.md`.
2. Pick exactly one `category` from `SKILL_TAXONOMY.md` § A.
3. Fill the new placeholders: `category`, `capabilities`,
   `limitations`, `category-justification`, `primary-output`,
   `boundary-item-N`, `governance_version: 1.1.0`.
4. Save and zip per the existing procedure.
5. Compute the `.md` SHA256; record it as both `md_sha256` AND
   `baseline_hash` in the new manifest entry. (They are equal at
   first commit; thereafter `md_sha256` tracks current state and
   `baseline_hash` stays frozen.)
6. Update `MANIFEST.json` with the full v1.2.0 entry.
7. Run the **Governance Gate** — all six checks must clear.
8. Regenerate `BASELINE_STATE.json` so the new skill is in the
   tracked set.
9. Re-run the Drift Detector and the Governance Self-Test against
   the new baseline — both must return `OK`.
10. Append a `GOVERNANCE_CHANGELOG.md` entry only if the change
    affected a governance file (a new skill alone does not require a
    changelog entry; a schema or template change does).

### How governance ensures consistency

- The **taxonomy** prevents category drift and overlap.
- The **schema** ensures every skill carries comparable metadata.
- The **template** ensures every skill is born compliant.
- The **instructions** + **Governance Gate** enforce the procedure.
- The **drift detector** catches any post-commit divergence from
  baseline.
- The **self-test** catches schema-level inconsistencies (missing
  fields, unknown categories, malformed `governance_version`,
  malformed `baseline_hash`, taxonomy/manifest reference mismatch).
- **As of schema 1.3.0**, the self-test enforces that every skill carries
  non-empty `input_shape` and `output_shape` strings plus a present
  `dependencies` field (list, may be empty); any item in `dependencies`
  must reference a skill that exists in `MANIFEST.json`. The schema
  fields `input_shape` / `output_shape` / `dependencies` were additive
  optional metadata in earlier walks; schema 1.3.0 ratifies them as
  mandatory. `manifest_version` (currently 2.0.0) and `schema_version`
  (currently 1.3.0) now legitimately diverge — manifest tracks
  structural schema changes; schema_version tracks per-skill content
  schema independently.

Together, these turn "compliance" into a property the library
mechanically defends, not a property authors have to remember.

### How baseline v1.2.0 protects the library

The v1.2.0 baseline tracks:

- All skill `.md` and `.zip` hashes, plus per-skill `version`,
  `category`, `governance_version`, and `baseline_hash`.
- All governance file hashes and per-file versions, including the
  newly-added `SKILL_TAXONOMY.md`.
- Anchor file hashes for `MANIFEST.json` and `README.md`.
- `manifest_version`, `schema_version`, `governance_layer_version`,
  and `BUILD_VERSION` at the moment v1.2.0 was declared.

Any post-commit edit to any tracked file produces a `DRIFT: DETECTED`
result until the baseline is regenerated. The baseline is the single
source of truth for "this is what the library is supposed to look
like right now." Tampering, accidental edits, and missed-version-bumps
all surface immediately.

---

## ClarityOS Agent Kernel (Governance v2.0.0)

Governance v2.0.0 introduces a second authored layer alongside skills:
the **Agent Kernel**. Where a skill is a single method, an **agent** is
a compositional **role** — a persona that receives operator intent,
selects skills from the skill library, composes them in the right
order, and produces an operator-grade output.

### What an agent is

An agent is described by a single `.md` file (no `.zip` — agents are
specs, not Perplexity-uploadable bundles). The agent file declares:

- `category` — verbatim from `AGENT_TAXONOMY.md` § A
- `capabilities` and `limitations` — same shape as skills
- `skills_used` — list of skill names the agent composes
- `behavioral_profile` — reactive / proactive / observer / executor
- `activation_triggers` — when the agent is invoked
- `output_shape` — what the agent produces overall
- `governance_version` — `2.0.0` (the agent kernel governance era)
- `agent_kernel_version` — `1.0.0` (the agent kernel itself)
- `baseline_hash` — recorded in the manifest entry, frozen at first commit

The agent body has the same shape as a skill body, plus three sections
specific to agents: **Identity** (who the agent acts on behalf of),
**Skills Composition** (which skills are invoked and why), and
**Operating Procedure** (the steps the agent walks when invoked).

### Agent taxonomy

`AGENT_TAXONOMY.md` defines five top-level categories: **Operator**,
**Analyst**, **Reviewer**, **Composer**, **Custodian**. The taxonomy
mirrors `SKILL_TAXONOMY.md` in structure but classifies by **primary
action** (what the agent does) rather than by primary output.

### Agent ↔ skill relationship

Agents compose skills. Skills do not compose agents.

Every entry in an agent's `skills_used` list must appear in
`MANIFEST.json` under the `skills` array. The governance self-test
validates this cross-reference: an agent referencing a non-existent
skill is a governance violation.

If an agent needs a method that no skill provides, the agent surfaces
the gap in its output rather than improvising. Agents do not invent
skills.

### Manifest changes at v2.0.0

The manifest schema bumped 1.2.0 → 2.0.0 and now includes:

- `governance.agent_template_file` — points to `AGENT_SPEC_TEMPLATE.md`
- `governance.agent_taxonomy_file` — points to `AGENT_TAXONOMY.md`
- New top-level `agents` array, parallel to the existing `skills` array

The skills array shape is unchanged. Existing skills continue to work
without modification. Adding the agents block is additive at the
top-level structure, but the schema bump is **major** because new
top-level blocks change what readers must know.

### Drift detector + self-test changes at v2.0.0

Both scripts bumped 1.2.0 → 2.0.0:

- **Drift detector** now iterates `baseline.agents` (a new top-level
  block parallel to `baseline.skills`), validates per-agent fields in
  the manifest against the baseline, and tracks agent `.md` files in
  the expected-files list. Agent files are NOT in `governance_files`
  — they have their own block.
- **Self-test** adds six new checks: agent schema 2.0.0 fields are
  present, agent categories are valid `AGENT_TAXONOMY` entries, agent
  `governance_version` and `agent_kernel_version` are semver, agent
  `baseline_hash` is valid SHA256, agent `skills_used` references
  existing skills, and `AGENT_SPEC_TEMPLATE.md` frontmatter contains
  the expected schema 2.0.0 agent fields.

### First agent

`clarity-operator-agent` (v1.0.0, **Operator**) is the first agent
admitted under the kernel. It composes all seven skills currently in
the library and is the default entry point for direct operator
interaction.

### Boundary

Agents are Layer 1 — general-case roles. They never describe Layer 2
cases. An agent like "VA-Litigation Operator" would violate the
boundary; particular-case engagements live in the personal envelope
(Layer 2), not in the agent kernel.
