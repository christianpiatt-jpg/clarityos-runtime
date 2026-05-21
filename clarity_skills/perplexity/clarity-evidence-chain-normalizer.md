---
name: clarity-evidence-chain-normalizer
description: >
  Normalize evidence anchors into a stable evidence chain. Accepts a list of
  evidence anchors produced by `clarity-evidence-anchor-extractor`, canonicalizes
  anchor references, resolves cross-links between anchors, and emits a structured
  evidence chain. Use when asked to chain, link, normalize, resolve, sequence,
  or canonicalize the evidence after extraction.
category: Evidence Extraction
capabilities:
  - Accept evidence-anchor objects produced by clarity-evidence-anchor-extractor
  - Normalize anchor references to canonical form (case names, citation components, exhibit labels, deponent names, dataset names)
  - Identify cross-links between anchors (one anchor referencing another)
  - Resolve the cross-link graph into a connected chain structure with stable chain identifiers
  - Produce structured evidence-chain output with orphan-anchor flags and normalization notes
limitations:
  - Does not extract anchors from raw text (that is the upstream skill clarity-evidence-anchor-extractor)
  - Does not extract or classify contradictions (sibling skill clarity-contradictions-extractor)
  - Does not weigh authority or assess legal significance of any anchor
  - Does not infer cross-links not stated or strongly implied in the source anchors
input_shape: >
  list of evidence anchors extracted from upstream skill
output_shape: >
  normalized evidence chain with resolved anchors and cross-links
dependencies:
  - clarity-evidence-anchor-extractor
governance_version: 1.1.0
---

# Clarity Evidence Chain Normalizer

## Purpose
Take the output of `clarity-evidence-anchor-extractor` and turn it into a
**stable evidence chain**: a structure where every anchor reference is
canonicalized, cross-references between anchors are resolved into explicit
links, and connected anchors are grouped into chain identifiers that
downstream skills can address.

This is the first dependency-bearing skill in the library. It does not
extract from raw text; it consumes the structured anchor table the
extractor emits, and elevates it into a chain.

## Category Justification
This skill operates on evidence items: it receives a typed list of
extracted anchors and produces a typed list of normalized, cross-linked
anchors organized into chains. Its primary output is a structured
evidence-chain artifact — still squarely in the "extract and structure
evidence items" lane.

This skill belongs to the **Evidence Extraction** category because its
primary output is a structured evidence artifact (chain of normalized
anchors with cross-links). See `SKILL_TAXONOMY.md` § A.

This skill is the third in Evidence Extraction. It is distinguished from
its siblings by primary output:

- `clarity-contradictions-extractor` finds where claims **conflict** with
  other claims (typed contradictions list).
- `clarity-evidence-anchor-extractor` finds where claims are **supported**
  (typed anchor table).
- `clarity-evidence-chain-normalizer` (this skill) takes the supports and
  **chains** them — canonicalizing references and resolving cross-links —
  into a stable structure that downstream legal/argument analysis can
  address by chain identifier.

The three skills form a natural pipeline: anchors → contradictions / chains.

## Boundary Statement

This skill **does not**:

- Extract anchors from raw text. That is `clarity-evidence-anchor-extractor`'s job. This skill consumes the extractor's output as its input.
- Extract or classify contradictions. For that see `clarity-contradictions-extractor`.
- Build chronological timelines or normalize dates. For that see Timeline Construction skills.
- Weigh authority or assess legal significance of any anchor. The chain is structural; doctrinal weight is a Legal Reasoning concern.
- Infer cross-links that are not stated or strongly implied in the source anchors. If anchor A doesn't reference anchor B in the text, this skill does not invent a link.

For methods that fall outside this boundary, see other skills in
`clarity_skills/perplexity/` or consult `SKILL_TAXONOMY.md`.

## Method

The method has three passes over the input anchor list:

1. **Ingest and validate** — receive the evidence-anchor objects produced
   by `clarity-evidence-anchor-extractor`. Verify each anchor has the
   required fields (`# / Type / Content / Location / Source / Mapped to /
   Quality`). Reject malformed entries with a normalization note.

2. **Normalize references** — canonicalize each anchor's references:
   - Case names: `Plaintiff v. Defendant` short form, no italics, no party titles.
   - Citations: parse into reporter / volume / page / year / court when possible.
   - Exhibit labels: `Exhibit <Letter or Number>` canonical form.
   - Deponents and witnesses: full surname; resolve "Mr./Ms." titles.
   - Dataset / record references: standardize to source + locator form.
   Record any normalization decision in the `normalization_notes` output.

3. **Cross-link and chain** — for each anchor, identify references to
   other anchors in the same input list:
   - Explicit references (e.g., "see also Anchor #3", "as cited in Exhibit B")
   - Citation-resolution links (e.g., short-form citations resolved to first-mention case)
   - Source-locality links (e.g., two anchors citing the same exhibit at different page references)
   Build the cross-link graph. Connected anchors form a **chain**, assigned
   a `chain_id`. Anchors with no cross-links become **orphan anchors**.

## Instructions

### 1. Receive Anchors
- Accept the JSON array output from `clarity-evidence-anchor-extractor`.
- Validate that every anchor has the seven required fields.
- If any anchor is malformed, emit a normalization note flagging it; do not silently drop.

### 2. Normalize Each Anchor
- For each anchor, apply the canonicalization rules from § Method step 2.
- Preserve the original `Anchor #` (now treated as `anchor_id` in the output) for traceability.
- Record a per-anchor normalization note when canonicalization changed the surface form.

### 3. Detect Cross-Links
- Scan each anchor's `Content` and `Source` for references that resolve to other anchors in the same list.
- Reference types to detect:
  - Short-form citation → first-mention case anchor
  - "See also Anchor #N" / "Compare Anchor #N" / "as cited in Exhibit X"
  - Two anchors citing the same exhibit / declaration / record
  - Witness statements citing other anchors' claims
- Record each link as a directed edge: `from_anchor_id`, `to_anchor_id`, `relation_type`.

### 4. Build Chains
- Treat the cross-link graph as undirected for chain assignment.
- Connected components become chains. Assign each chain a stable `chain_id` of the form `chain-NNN` (zero-padded 3-digit), in encounter order of the lowest `anchor_id` in each component.
- Anchors not in any cross-link relationship become orphan anchors.

### 5. Emit Output
Produce a single JSON object per the Output Contract below. Order:
- `chains` array sorted by `chain_id` ascending.
- Anchors within each chain sorted by `anchor_id` ascending.
- `orphan_anchors` sorted by `anchor_id` ascending.
- `normalization_notes` sorted by source `anchor_id` ascending.

### 6. Quality Check
- Verify every anchor in the input appears exactly once in the output (in a chain or in orphans, never both, never missing).
- Verify every cross-link's `from_anchor_id` and `to_anchor_id` reference anchors that exist in the chain.
- Verify chain identifiers are unique and follow the `chain-NNN` form.

## Output Contract

The output is a **single JSON object** with exactly three top-level keys:
`chains`, `orphan_anchors`, `normalization_notes`. No extra keys.

```json
{
  "chains": [
    {
      "chain_id": "chain-001",
      "anchors": [
        {
          "anchor_id": "1",
          "type": "citation",
          "content": "Standard for summary judgment",
          "location": "p. 4 ¶ 1",
          "source": "Anderson v. Liberty Lobby, 477 U.S. 242 (1986)",
          "mapped_to": "Issue 1",
          "quality": "specific, direct"
        },
        {
          "anchor_id": "5",
          "type": "citation",
          "content": "summary judgment standard short-form",
          "location": "p. 6 ¶ 2",
          "source": "Anderson at 247",
          "mapped_to": "Issue 1 element 2",
          "quality": "specific, direct"
        }
      ],
      "cross_links": [
        {
          "from_anchor_id": "5",
          "to_anchor_id": "1",
          "relation_type": "short_form_resolution"
        }
      ]
    }
  ],
  "orphan_anchors": [
    {
      "anchor_id": "4",
      "type": "data",
      "content": "12% turnover rate",
      "location": "p. 7 ¶ 1",
      "source": "(no citation)",
      "mapped_to": "(orphan)",
      "quality": "vague"
    }
  ],
  "normalization_notes": [
    {
      "anchor_id": "1",
      "note": "Case name normalized: Anderson v. Liberty Lobby, Inc. -> Anderson v. Liberty Lobby (party suffix stripped)."
    }
  ]
}
```

Field rules:

- `chains` — array of objects; each has `chain_id` (string `chain-NNN`), `anchors` (array of normalized anchor objects), `cross_links` (array of directed edges with `from_anchor_id`, `to_anchor_id`, `relation_type`).
- `orphan_anchors` — array of normalized anchor objects with no cross-links to any other anchor in the input.
- `normalization_notes` — array of objects with `anchor_id` and `note` (string explaining the normalization decision).
- Anchor objects preserve the seven fields from `clarity-evidence-anchor-extractor` output (`anchor_id`, `type`, `content`, `location`, `source`, `mapped_to`, `quality`), with values canonicalized per § Method step 2.

The output MUST be a single JSON object — not an array, not multiple
objects.

## Example Input

(Output of `clarity-evidence-anchor-extractor` on a motion-to-dismiss):

```json
[
  { "anchor_id": "1", "type": "citation", "content": "Summary judgment standard", "location": "p. 4 ¶ 1", "source": "Anderson v. Liberty Lobby, 477 U.S. 242 (1986)", "mapped_to": "Issue 1", "quality": "specific, direct" },
  { "anchor_id": "2", "type": "exhibit", "content": "Personnel file", "location": "p. 5 ¶ 3", "source": "Exhibit A", "mapped_to": "Issue 1 element 2", "quality": "specific, first-party" },
  { "anchor_id": "3", "type": "witness", "content": "Statement re. policy", "location": "p. 6 ¶ 2", "source": "Decl. of A ¶ 7", "mapped_to": "Issue 1 element 2", "quality": "direct" },
  { "anchor_id": "4", "type": "data", "content": "12% turnover rate", "location": "p. 7 ¶ 1", "source": "(no citation)", "mapped_to": "(orphan)", "quality": "vague" },
  { "anchor_id": "5", "type": "citation", "content": "summary judgment standard short-form", "location": "p. 6 ¶ 2", "source": "Anderson at 247", "mapped_to": "Issue 1 element 2", "quality": "specific, direct" }
]
```

## Example Output

```json
{
  "chains": [
    {
      "chain_id": "chain-001",
      "anchors": [
        { "anchor_id": "1", "type": "citation", "content": "Summary judgment standard", "location": "p. 4 ¶ 1", "source": "Anderson v. Liberty Lobby, 477 U.S. 242 (1986)", "mapped_to": "Issue 1", "quality": "specific, direct" },
        { "anchor_id": "5", "type": "citation", "content": "summary judgment standard short-form", "location": "p. 6 ¶ 2", "source": "Anderson at 247", "mapped_to": "Issue 1 element 2", "quality": "specific, direct" }
      ],
      "cross_links": [
        { "from_anchor_id": "5", "to_anchor_id": "1", "relation_type": "short_form_resolution" }
      ]
    },
    {
      "chain_id": "chain-002",
      "anchors": [
        { "anchor_id": "2", "type": "exhibit", "content": "Personnel file", "location": "p. 5 ¶ 3", "source": "Exhibit A", "mapped_to": "Issue 1 element 2", "quality": "specific, first-party" },
        { "anchor_id": "3", "type": "witness", "content": "Statement re. policy", "location": "p. 6 ¶ 2", "source": "Decl. of A ¶ 7", "mapped_to": "Issue 1 element 2", "quality": "direct" }
      ],
      "cross_links": [
        { "from_anchor_id": "3", "to_anchor_id": "2", "relation_type": "shared_mapped_issue" }
      ]
    }
  ],
  "orphan_anchors": [
    { "anchor_id": "4", "type": "data", "content": "12% turnover rate", "location": "p. 7 ¶ 1", "source": "(no citation)", "mapped_to": "(orphan)", "quality": "vague" }
  ],
  "normalization_notes": []
}
```

## Governance Compliance Checklist

Before this skill is committed:

- [ ] `category` matches a row in `SKILL_TAXONOMY.md` § A.
- [ ] `capabilities` and `limitations` lists are non-empty.
- [ ] `input_shape` and `output_shape` are non-empty strings (schema 1.3.0).
- [ ] `dependencies` is a list; every item is the `name` of a skill that exists in `MANIFEST.json` (schema 1.3.0).
- [ ] `governance_version` matches the current governance layer version recorded for skills (`1.1.0`).
- [ ] `name` is lowercase, hyphens only, and matches the filename.
- [ ] `description` contains explicit trigger phrases.
- [ ] No PII; no Layer 2 case material.
- [ ] File under 10 MB.
- [ ] `SKILL.md` at the root of the upload zip; byte-identical to this `.md`.
- [ ] Manifest entry under schema 1.3.0 includes all required fields plus `input_shape`, `output_shape`, `dependencies`.
- [ ] `baseline_hash` (in manifest entry only) is set to the SHA256 of this `.md` at first commit and frozen thereafter.
- [ ] Drift Detector returns `DRIFT: NONE` after baseline regeneration.
- [ ] Governance Self-Test returns `GOVERNANCE SELF-TEST: OK` (including the schema 1.3.0 dependency-resolution check).
