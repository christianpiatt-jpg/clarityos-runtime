# Skill Taxonomy

This document defines the canonical category system that classifies
every skill in `clarity_skills/perplexity/`. Every skill — existing or
new — must declare exactly one `category` value, drawn from the table
in § A, in both its frontmatter and its `MANIFEST.json` entry.

The taxonomy serves four purposes:

1. **Prevents category drift** — a fixed vocabulary keeps the library
   from accumulating ad-hoc labels.
2. **Prevents overlapping scopes** — categories are mutually exclusive
   at the top level. A skill belongs in exactly one.
3. **Ensures discoverability** — both humans and automation can route
   to skills by category.
4. **Enables future automation** — category-based dispatch, indexing,
   and selection logic can be built on top of a stable taxonomy.

The current `taxonomy_version` is **1.0.0** (initial release).

---

## A. Top-Level Categories

| Category | Definition |
|---|---|
| **Narrative Analysis** | Methods that analyze the structure, framing, identity threads, and institutional behavior patterns of a document. Output: structural readings, framing maps, narrative leverage points. Examples: applying narrative-architecture analysis to legal motions, identifying institutional drift across an agency's communications. |
| **Evidence Extraction** | Methods that pull discrete, classifiable items from a document — contradictions, claims, assertions, citations, factual statements. Output: typed lists of extracted items with provenance and impact notes. Examples: extracting contradictions from an agency decision, listing every factual assertion in a brief. |
| **Timeline Construction** | Methods that build chronologies from a document or set of documents. Output: ordered event lists, normalized dates, gap and conflict identification. Examples: reconstructing a sequence of events from emails, identifying temporal inconsistencies across filings. |
| **Legal Reasoning** | Methods that operate on legal standards, doctrines, statutes, and procedural rules — applying them to facts, comparing arguments to authority, identifying standard-of-review issues. Output: legal analyses, authority gaps, doctrinal arguments. |
| **Summarization** | Methods that compress a document into a structured summary — preserving structure, claims, and disputes without losing fidelity. Output: structured summaries, key-points extracts, executive briefs. |

A skill belongs in exactly one of the categories above. If a method
seems to span multiple categories, classify it by its **primary
output** — what the skill produces — not by what inputs it touches.

### Examples (with reasoning)

- A skill that **applies narrative-architecture to a legal motion to
  produce a structural reading + opposition outline** → its primary
  output is a structural reading. Category: **Narrative Analysis**.
- A skill that **scans a document for contradictions and lists them
  with classifications** → primary output is a typed list of evidence
  items. Category: **Evidence Extraction**.
- A skill that **extracts dates from a document and builds a
  chronology** → primary output is an ordered event list. Category:
  **Timeline Construction**.

---

## B. Rules for Adding a New Category

A new category may be proposed when:

1. At least **two** existing or planned skills clearly fall outside
   every existing category, AND
2. The new category has a primary-output definition that does not
   overlap with any existing category, AND
3. The category name is durable — it should still make sense in five
   years and not be tied to a transient project.

To add a category:

1. Open a governance change (Phase-5+ release).
2. Append the new row to § A above with its definition.
3. Add an "Examples" entry illustrating the boundary.
4. Bump `taxonomy_version` per § E.
5. Run `GOVERNANCE_SELF_TEST.ps1`. The taxonomy must remain
   internally consistent.
6. Regenerate `BASELINE_STATE.json`.
7. Add an entry to `GOVERNANCE_CHANGELOG.md` describing the new
   category and its rationale.

Single-skill categories are not permitted. If only one skill needs
the new label, the skill belongs in an existing category.

---

## C. Rules for Merging Categories

Two categories may be merged when:

1. Their definitions overlap to the point that classification is
   ambiguous, AND
2. No existing skill straddles the boundary in a way that the merge
   would change its real classification.

To merge:

1. Pick the surviving name (the broader of the two, by convention).
2. Remove the deprecated row from § A.
3. Update every affected skill's `category` field in its frontmatter
   AND its manifest entry.
4. Bump every affected skill's `version` (patch — metadata-only edit).
5. Regenerate the affected zips and recompute hashes.
6. Bump `taxonomy_version` (major — breaking change).
7. Bump `manifest_version` (major — schema-breaking change because
   stored category strings changed meaning).
8. Run the full Governance Gate.
9. Regenerate `BASELINE_STATE.json`.
10. Record the merge in `GOVERNANCE_CHANGELOG.md`.

---

## D. Rules for Deprecating Categories

A category may be deprecated when no skill is classified under it AND
no reasonable future skill is expected to fall under it.

A deprecated category is removed from § A in the next taxonomy major
bump. It is NOT silently retained — § A is the authoritative list.
Past skills referencing a deprecated category must have been
re-classified before the deprecation lands. Deprecation does not
strand existing skills.

---

## E. Versioning the Taxonomy

This document carries an implicit `taxonomy_version` recorded in
`BASELINE_STATE.json` under `governance_files["SKILL_TAXONOMY.md"]`.
The bump rules:

- **Patch** — typo / formatting / clarification of existing
  definitions without changing what falls in or out of the category.
- **Minor** — additive: a new category added that doesn't reclassify
  any existing skill.
- **Major** — breaking: a category is renamed, merged, removed, or
  its definition narrows in a way that reclassifies existing skills.

---

## F. Mapping of Existing Skills → Categories

| Skill | Category | Primary Output |
|---|---|---|
| `clarity-narrative-litigation` | Narrative Analysis | Structural reading of a legal/institutional document with leverage points and an opposition outline. |
| `clarity-narrative-spine-builder` | Narrative Analysis | General-purpose narrative spine: actors, conflict, stakes, causal chain, institutional posture, frame, and omissions/distortions/selective framing. |
| `clarity-contradictions-extractor` | Evidence Extraction | Numbered, typed list of contradictions in a document, with conflict-type classification and impact notes. |
| `clarity-evidence-anchor-extractor` | Evidence Extraction | Structured evidence-anchor table — facts, citations, exhibits, data points, and witness references — typed and mapped to issues/claims when present, with orphan/unsupported flags. |
| `clarity-evidence-chain-normalizer` | Evidence Extraction | Normalized evidence chain over the output of `clarity-evidence-anchor-extractor` — anchor references canonicalized, cross-links resolved, anchors grouped into stable `chain-NNN` identifiers with orphan-anchor flags. **First dependency-bearing skill in the library** (depends on the anchor extractor). |
| `clarity-timeline-mapper` | Timeline Construction | Normalized chronology with temporal-inconsistency flags. |
| `clarity-temporal-event-normalizer` | Timeline Construction | JSON array of normalized atomic events — verbatim temporal expressions canonicalized to ISO 8601 timestamps with per-event confidence scores. The substrate for timeline assembly. |
| `clarity-operator-brief-structurer` | Summarization | Operator-grade brief in fixed Situation / Assessment / Key Points / Recommended Actions structure. |
| `clarity-summarization-contrastive-brief` | Summarization | Contrastive brief — single JSON object with `sections` (sectioned summary) plus explicit `agreements`, `disagreements`, and `gaps` blocks keyed by issue. Multi-position view of a record. |

> **Schema 1.3.0 enforcement note (taxonomy v1.0.7):** As of schema 1.3.0,
> every skill listed above must carry `input_shape`, `output_shape`, and
> `dependencies` in its frontmatter and manifest entry. The governance
> self-test enforces this. Any skill missing these fields is a
> governance violation and will fail the self-test.
| `clarity-legal-argument-mapper` | Legal Reasoning | Structured map of legal argument architecture: issues, standards of review, elements, sub-elements, evidence citations, burdens, logical dependencies, and identified gaps. |
| `clarity-legal-precedent-extractor` | Legal Reasoning | JSON array of precedent objects — case name, citation, holding, relevance, and confidence — extracted in source-encounter order. The atomized precedent catalogue that argument-mapping can hang from. |

This mapping is authoritative. If a skill's category is updated, both
this table AND the skill's frontmatter AND its manifest entry must
change in the same release.

---

## G. Boundary

The taxonomy is a **Layer 1** artifact. Categories describe
**methods**. They never describe **cases**. A category like
"VA-Litigation Drafting" would violate the boundary — it would tie a
general-purpose category to a particular-case engagement. If you find
yourself wanting to add such a category, the underlying need belongs
in the personal envelope (Layer 2), not in the skill library.
