# Skill Library Versioning

This document defines how skill versions are assigned and incremented.
Read it before changing any file in `clarity_skills/perplexity/`.

---

## A. Versioning Rules

Every skill carries a `version` field in its `MANIFEST.json` entry.
Skill versions follow a semver-style three-number scheme:
`MAJOR.MINOR.PATCH`.

### Initial version

Each new skill **starts at `"1.0.0"`** when first added to the library.

### Patch increment (`x.y.PATCH`)

Bump the patch number for changes that do not alter the skill's
behavior:

- Typo fixes
- Formatting fixes (whitespace, list markers, heading levels)
- Non-semantic edits — clarifying wording without changing what the
  skill does or what it produces
- Comment / note adjustments inside the skill body
- Re-zipping after a tooling change that produces a different
  `zip_sha256` but identical `.md` content

Example: `1.0.0 → 1.0.1`.

### Minor increment (`x.MINOR.0`)

Bump the minor number for additive, non-breaking changes:

- A new instruction step
- A new example (input or output)
- An expanded `description` field with additional trigger phrases
- A new optional section in the body
- Strengthened guidance that remains backward-compatible with prior
  invocations

Reset patch to `0` when minor bumps. Example: `1.0.4 → 1.1.0`.

### Major increment (`MAJOR.0.0`)

Bump the major number for breaking changes:

- Renaming the skill (the `name` field changes)
- Restructuring instructions in a way that alters the output shape
- Removing a previously-documented step, section, or example
- Changing trigger phrases such that previously-firing prompts no
  longer match
- Any change a downstream Perplexity workspace would need to be aware
  of before re-uploading

Reset minor and patch to `0`. Example: `1.4.7 → 2.0.0`.

If a skill is renamed, the major bump applies **to the new file**; the
old file is removed from the folder and from `MANIFEST.json` in the
same change.

---

## B. Manifest Update Rules

`MANIFEST.json` is the single registry the rest of the system relies on
to know what exists. It must stay in sync with the folder.

`MANIFEST.json` **must** be updated whenever:

- A new skill is added to `clarity_skills/perplexity/`
- A skill is modified (any change to its `.md` content)
- A skill is removed from the folder
- A skill's `version` bumps for any reason
- The pipeline tooling changes how zips are produced (so `zip_sha256`
  changes)

Concretely, every update must:

1. Recompute `md_sha256` from the `.md` file.
2. Recompute `zip_sha256` from the `.zip` file.
3. Update `md_bytes` and `zip_bytes` to reflect the current sizes.
4. Set the per-skill `version` to its new value.
5. Bump the top-level `generated_at` to today's date (`YYYY-MM-DD`).

The hashes in `MANIFEST.json` are the **integrity contract** for the
library. If they do not match the on-disk files, the library is
considered out of sync and must be repaired before any new skill is
added.

---

## C. Release Discipline

Every skill update — whether new, revised, or removed — is a small
release. Each release **must** include all of the following, in this
order:

1. **Edit** the `.md` file (or add a new one).
2. **Bump the version** in `MANIFEST.json` per the rules above.
3. **Regenerate the zip bundle** so `SKILL.md` inside is byte-identical
   to the new `.md`. See `CREATE_NEW_SKILL_INSTRUCTIONS.md` for the
   PowerShell snippet.
4. **Update the manifest entry** with new `md_sha256`, `zip_sha256`,
   `md_bytes`, `zip_bytes`, and `version`.
5. **Bump `generated_at`** at the top of the manifest.
6. **Verify** the hashes by re-running `Get-FileHash` against the
   actual files and confirming they match the values you just wrote
   into the manifest. See `INTEGRITY_CHECKS.md` for the verification
   procedure.

If any of these steps is skipped, the release is incomplete. A release
with mismatched hashes is treated the same as a missing release: it
must be reverted or completed before any further work in this folder.

---

## Quick Reference

| Change kind | Example | Bump |
|---|---|---|
| Fix a typo | `acency` → `agency` | patch |
| Reword without changing meaning | "Read the entire text." → "Read the document in full." | patch |
| Re-zip after tooling change | `.md` unchanged, `.zip` regenerated | patch |
| Add an instruction step | New "### 6. Verify" section | minor |
| Add an example | Second Example Input/Output pair | minor |
| Expand triggers in `description` | Add "Use when reviewing…" | minor |
| Rename the skill | `clarity-foo` → `clarity-bar` | major |
| Remove a documented step | Drop "### 3. …" entirely | major |
| Restructure output shape | Switch from numbered list to table | major |
| Tighten triggers (some prompts no longer match) | Remove "Analyze…" from `description` | major |

---

## Versioning the Manifest Itself

`MANIFEST.json` carries its own top-level `manifest_version` field.
That field versions the **schema** of the manifest — not the contents
of any individual skill.

Bump `manifest_version` when the manifest's structure changes:

- **Patch** — descriptive notes, comment-style fields added.
- **Minor** — a new optional top-level field added (additive,
  backward-compatible). Existing readers can ignore the new field.
- **Major** — an existing field renamed, removed, or repurposed.
  Existing readers will break.

The first manifest in this library was `1.0.0`. Adding the
`governance` top-level block was a `1.1.0` change.
