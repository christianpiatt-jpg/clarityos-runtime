# Creating a New Perplexity Skill

This document is the canonical, repeatable procedure for adding a new
skill to `clarity_skills/perplexity/`. Follow it end-to-end every time.

---

## Step-by-Step

### 1. Duplicate `SKILL_TEMPLATE.md`

From this folder:

```powershell
Copy-Item SKILL_TEMPLATE.md "{{skill-name}}.md"
```

Replace `{{skill-name}}` with the actual lowercase, hyphen-only name of
the skill you are creating (e.g. `clarity-statute-mapper`).

### 2. Replace placeholders with actual content

Open `{{skill-name}}.md` and replace every placeholder:

| Placeholder | What to put there |
|---|---|
| `{{skill-name}}` | The same lowercase, hyphen-only name used in the filename |
| `{{skill-description}}` | 1–3 sentences. Lead with WHEN the skill should fire (trigger phrases), then WHAT it produces. This is the matcher field — Perplexity uses it to decide whether to invoke the skill. |
| `{{Skill Title}}` | Title Case display name (e.g. "Clarity Statute Mapper") |
| `{{purpose}}` | One paragraph describing the method and output shape |
| `{{instructions}}` | Numbered, atomic steps under `###` headings — each step executable in isolation |
| `{{examples}}` (Example Input) | A representative user prompt in quotes |
| `{{examples}}` (Example Output) | A concise illustration of the output |

Delete the trailing `<!-- TEMPLATE NOTES ... -->` comment block from the
template before saving.

### 3. Save as `{{skill-name}}.md`

The file must live at:

```
clarity_skills/perplexity/{{skill-name}}.md
```

Both the filename and the `name:` field in the YAML frontmatter must match
exactly.

### 4. Create a zip with `SKILL.md` at the root

Perplexity expects a zip whose only entry is `SKILL.md` at the archive
root — not `{{skill-name}}.md`. Use this PowerShell snippet from inside
`clarity_skills/perplexity/`:

```powershell
Compress-Archive -Path SKILL.md -DestinationPath {{skill-name}}.zip -Force
```

That command requires a file literally named `SKILL.md` in the current
directory. Two clean ways to produce that:

**Option A — quick (rename in place, then restore):**

```powershell
$name = "{{skill-name}}"
Copy-Item "$name.md" SKILL.md
Compress-Archive -Path SKILL.md -DestinationPath "$name.zip" -Force
Remove-Item SKILL.md
```

**Option B — temp directory (no transient file in the skills folder):**

```powershell
$name = "{{skill-name}}"
$tmp  = Join-Path $env:TEMP ("skill_" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
Copy-Item "$name.md" (Join-Path $tmp "SKILL.md")
Compress-Archive -Path (Join-Path $tmp "SKILL.md") `
                 -DestinationPath "$name.zip" -Force
Remove-Item $tmp -Recurse -Force
```

Both options produce a zip whose sole entry is `SKILL.md` at the root,
byte-identical to `{{skill-name}}.md`.

### 5. Place both files in `/clarity_skills/perplexity/`

The final state must include:

```
clarity_skills/perplexity/{{skill-name}}.md
clarity_skills/perplexity/{{skill-name}}.zip
```

### 6. Update `MANIFEST.json`

Add a new entry for the skill (see the existing entries for shape).
Recompute and record both `md_sha256` and `zip_sha256`. Bump the
manifest's `generated_at` date.

```powershell
# Compute the two hashes for the manifest entry:
(Get-FileHash -Algorithm SHA256 "{{skill-name}}.md").Hash.ToLower()
(Get-FileHash -Algorithm SHA256 "{{skill-name}}.zip").Hash.ToLower()
```

---

## Validation Checklist

Run through this before committing:

- [ ] YAML frontmatter is valid (parses; uses spaces not tabs; quotes balanced).
- [ ] `name` is **lowercase, hyphens only** — no underscores, no spaces, no caps.
- [ ] Filename matches `name` exactly (`{{skill-name}}.md`).
- [ ] `description` contains explicit **trigger phrases** ("Use when…", "Analyze…", "Extract…").
- [ ] File size is **under 10 MB** (skills here are typically a few KB).
- [ ] **No PII** — no names, addresses, emails, phone numbers, agency case
      numbers, dates of contested events, or anything tied to a real
      individual or matter.
- [ ] No quoted excerpts from filings, emails, or agency records.
- [ ] No case-specific facts. (See boundary note below.)
- [ ] Zip contains a single entry named **`SKILL.md`** at the archive root.
- [ ] `SKILL.md` inside the zip is byte-identical to `{{skill-name}}.md`.
- [ ] `MANIFEST.json` updated with the new entry and refreshed hashes.

---

## Boundary Note

**Skills belong to the general-case layer (Layer 1).**
They encode reasoning *methods*, not case material.

A skill must never carry:

- Personally-identifying information about any individual
- Case-specific facts (the VA_LITIGATION project, the MSJ_OPPOSITION
  thread, named parties, agency reference numbers, etc.)
- Quoted excerpts from particular filings or records
- Anything that would only make sense inside one engagement

If a skill needs case-specific context to do its job, that context is
supplied as the **input** to the skill at runtime. The particular case
lives in the personal envelope (Layer 2). The skill stays general,
reusable, and free of any data that should not leave Layer 1.

A useful audit step before zipping: grep the new file for likely PII or
case tokens (party names, agency numbers, contested dates) and remove or
generalize anything that surfaces.

---

## Expansion Mode (Schema 1.2.0)

Under schema 1.2.0 the requirements above are extended. New skills must
declare themselves under the canonical taxonomy and carry richer
metadata in the manifest. Walk through these additions before running
the Governance Gate.

### Updated Step 2 — placeholders to fill (Schema 1.2.0 additions)

The template (`SKILL_TEMPLATE.md` v1.2.0) carries new placeholders:

| Placeholder | What to put there |
|---|---|
| `{{category}}` | Exact verbatim string from `SKILL_TAXONOMY.md` § A. One of: **Narrative Analysis**, **Evidence Extraction**, **Timeline Construction**, **Legal Reasoning**, **Summarization**. Mutually exclusive — pick exactly one based on the skill's primary output. |
| `{{capability-N}}` | One short sentence each. What the skill produces or does well. Three to six items typical. |
| `{{limitation-N}}` | One short sentence each. What the skill explicitly does NOT do. Two to four items typical. |
| `{{category-justification}}` | 1-2 sentences. Why this skill belongs in `{{category}}` and not in a neighbouring category. Reference primary output. |
| `{{primary-output}}` | Short noun phrase describing the skill's output shape (e.g. "a normalized chronology with temporal-inconsistency flags"). |
| `{{boundary-item-N}}` | First-person prose restating the limitations for readers of the skill. |

`governance_version` in frontmatter is fixed at `1.1.0` for skills
created under the current governance layer. `baseline_hash` is **not**
in frontmatter (self-reference problem); it lives only in the manifest
entry — see below.

### Updated Step 6 — manifest entry (Schema 1.2.0)

Every skill's `MANIFEST.json` entry under schema 1.2.0 must include:

```json
{
  "name": "<skill-name>",
  "version": "1.0.0",
  "filename": "<skill-name>.md",
  "zip_filename": "<skill-name>.zip",
  "description": "...",
  "md_sha256": "<current SHA256>",
  "zip_sha256": "<current SHA256>",
  "md_bytes": 0,
  "zip_bytes": 0,
  "category": "<verbatim from SKILL_TAXONOMY.md A>",
  "capabilities": [ "...", "..." ],
  "limitations": [ "...", "..." ],
  "governance_version": "1.1.0",
  "baseline_hash": "<creation-time SHA256 of the .md>"
}
```

`category`, `capabilities`, `limitations` should mirror the values in
the skill's frontmatter. `governance_version` records the governance
layer version under which the skill was first registered.
`baseline_hash` is the immutable creation-time SHA256 of the .md —
frozen forever, distinct from `md_sha256` which tracks current state.

### Filling baseline_hash

`baseline_hash` is the SHA256 of the skill's `.md` AT THE MOMENT IT IS
FIRST COMMITTED to the library. It does not change when the skill is
revised. Procedure:

1. Finalize the `.md` content (replace all placeholders, delete the
   template notes block).
2. Compute the hash:
   ```powershell
   (Get-FileHash -LiteralPath "<skill-name>.md" -Algorithm SHA256).Hash.ToLower()
   ```
3. Paste the lowercase hex digest into the manifest entry's
   `baseline_hash` field.
4. The same value also goes into `md_sha256` at first commit (they
   are equal until the skill is first revised; thereafter `md_sha256`
   tracks current and `baseline_hash` stays frozen).

### Updated Step 7 — pre-commit verification under Expansion Mode

Before the Governance Gate proper, run:

1. `DRIFT_DETECTOR.ps1` — must report `DRIFT: NONE` against the
   *current* baseline. If it reports drift, an unauthorized change
   has happened elsewhere in the folder; resolve before adding a new
   skill.
2. After committing the new skill (writing the `.md`, the `.zip`, and
   the manifest entry), regenerate `BASELINE_STATE.json` so it
   includes the new skill entry, the new hashes, and the recorded
   `baseline_hash`.
3. Run `DRIFT_DETECTOR.ps1` again, against the new baseline — must
   report `DRIFT: NONE`.
4. Run `GOVERNANCE_SELF_TEST.ps1` — must report
   `GOVERNANCE SELF-TEST: OK`. The self-test will verify the new
   skill's category is a known taxonomy entry, that all schema 1.2.0
   fields are present, that `governance_version` is valid semver, and
   that `baseline_hash` is a valid SHA256.

### Updated Validation Checklist (Schema 1.2.0 + 1.3.0 additions)

In addition to the items in the prior checklist:

- [ ] `category` is a verbatim match to a row in `SKILL_TAXONOMY.md` § A.
- [ ] `capabilities` is a non-empty list; each item is one short sentence.
- [ ] `limitations` is a non-empty list; each item is one short sentence.
- [ ] `governance_version` is `"1.1.0"` (or the current governance layer version).
- [ ] `baseline_hash` is set in the manifest entry, equal to the SHA256 of the `.md` at first commit, recorded as 64 lowercase hex characters.
- [ ] **`input_shape` is a non-empty string** describing what the skill consumes (schema 1.3.0 — required).
- [ ] **`output_shape` is a non-empty string** describing what the skill produces (schema 1.3.0 — required).
- [ ] **`dependencies` is a list (may be empty `[]`)** of skill names this skill depends on (schema 1.3.0 — required).
- [ ] Frontmatter mirrors manifest for `category`, `capabilities`, `limitations`, `governance_version`, `input_shape`, `output_shape`, `dependencies`.
- [ ] `Category Justification` and `Boundary Statement` body sections are filled.
- [ ] `Governance Compliance Checklist` at the bottom of the `.md` is reasoned through.

### Schema 1.3.0 — Enforcement Notes

As of schema 1.3.0, **`input_shape`, `output_shape`, and `dependencies`
are mandatory** on every skill. They are no longer additive optional
metadata. The governance self-test enforces:

- `input_shape` present and non-empty (string).
- `output_shape` present and non-empty (string).
- `dependencies` present (may be empty list); items, if any, must be `name`
  strings of skills that exist in `MANIFEST.json`.

A skill missing or empty in any of these three fields FAILS the self-test
and cannot be admitted to the library. Existing skills that predate
schema 1.3.0 were migrated as part of the 1.3.0 ratification release;
all current skills carry these fields.

---

## Governance Gate

All four governance artifacts must be satisfied before a skill is
accepted into `clarity_skills/perplexity/`. This is the **single choke
point** for quality.

A skill is **not** committed unless **all six** of the following are
true:

### 1. Version bump is correct
See `VERSIONING.md` § A. New skills start at `1.0.0`. If you changed an
existing skill, the per-skill `version` in `MANIFEST.json` must be
bumped per the patch / minor / major rules.

### 2. Manifest entry is correct
See the `governance` block at the top of `MANIFEST.json` and
`VERSIONING.md` § B. The new or revised entry must include `name`,
`version`, `filename`, `zip_filename`, `description`, `md_sha256`,
`zip_sha256`, `md_bytes`, `zip_bytes`. The top-level `generated_at`
must be bumped to today's date (`YYYY-MM-DD`).

### 3. Integrity suite passes
See `INTEGRITY_CHECKS.md` § A. The library-wide hash check must return
one `OK` line per skill — every skill's `md_sha256` and `zip_sha256`
must match the on-disk files. Any `FAIL` line blocks the commit.

### 4. Contamination sweep is clean
See `INTEGRITY_CHECKS.md` § C. Run the PII regex scan, the
personal-envelope token grep, and the case-specificity heuristic. Hits
must be removed or generalized before the gate clears.

### 5. Drift Detector reports `DRIFT: NONE`
Run `DRIFT_DETECTOR.ps1`. Expected output:

```
DRIFT: NONE
```

If drift is detected, either revert the unauthorized change or, if the
change is intentional, regenerate `BASELINE_STATE.json` after the
release settles. Regenerating the baseline is part of the release
procedure for any authorized change.

### 6. Governance Self-Test reports `GOVERNANCE SELF-TEST: OK`
Run `GOVERNANCE_SELF_TEST.ps1`. Expected first line:

```
GOVERNANCE SELF-TEST: OK
```

This confirms the governance layer itself is internally consistent
before you build on top of it.

---

If any of the six checks above fails, **the skill is not committed**.
No exceptions. The gate exists precisely because the failure modes it
catches are easy to miss in review and expensive to clean up later.

### Quick-reference gate command (PowerShell)

Run from `clarity_skills/perplexity/`:

```powershell
$folder = "C:\ClarityOS_Code\clarity_skills\perplexity"
$name   = "<skill-name>"   # the skill being committed

# 3. Library-wide integrity
$m = Get-Content -Raw -LiteralPath (Join-Path $folder "MANIFEST.json") | ConvertFrom-Json
foreach ($s in $m.skills) {
  $md  = (Get-FileHash -LiteralPath (Join-Path $folder $s.filename)     -Algorithm SHA256).Hash.ToLower()
  $zip = (Get-FileHash -LiteralPath (Join-Path $folder $s.zip_filename) -Algorithm SHA256).Hash.ToLower()
  $ok  = ($md -eq $s.md_sha256) -and ($zip -eq $s.zip_sha256)
  Write-Output "$($s.name) v$($s.version) : $(if ($ok) {'OK'} else {'FAIL'})"
}

# 4. Contamination sweep on the new / changed skill
Select-String -LiteralPath (Join-Path $folder "$name.md") `
  -Pattern '\b\d{3}-\d{2}-\d{4}\b|@[\w.-]+\.[\w.-]+|VA_LITIGATION|MSJ_OPPOSITION'

# 5. Drift detector
& (Join-Path $folder "DRIFT_DETECTOR.ps1")

# 6. Governance self-test
& (Join-Path $folder "GOVERNANCE_SELF_TEST.ps1")
```

Steps 1 and 2 are manual — review against `VERSIONING.md` and the
manifest. Steps 3–6 produce machine-readable output and are the binary
go / no-go.
