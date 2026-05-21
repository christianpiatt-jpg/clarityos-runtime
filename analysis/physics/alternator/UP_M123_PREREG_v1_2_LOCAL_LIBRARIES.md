# UP M1/M2/M3 — Pre-registration v1.2: ClarityOS Local Library Corpus

**Status:** preregistered (no inferential commitments). Locks corpus
boundaries, ingestion rules, metric set, alternator grid, tokenization
plan, quorum evaluation, and artifact paths.

**Contract version anchor:** v1.0.0 § 1–9 + v1.1.0 § 6–9 (this prereg
inherits both; no contract is modified).

**Registered:** 2026-05-07
**Corpus ID:** `local_libraries_v1_2`

---

## 1. Corpus Name

**ClarityOS Local Library Corpus (v1.2)**

## 2. Corpus Definition

Three local library subsystems on the operator's OneDrive-synced
filesystem:

```
C:\Users\chris\ClarityOS_Library\Clarity_Library\02_Subsystems\ELINS_Library
C:\Users\chris\ClarityOS_Library\Clarity_Library\02_Subsystems\Lawbridg References
C:\Users\chris\ClarityOS_Library\Clarity_Library\02_Subsystems\Narrative_Architecture
```

**Pre-registration-time presence check (informational, not constraining):**

| subsystem root | exists? | text-file count (.json/.md/.txt, depth ≤ 3) |
|---|---|---|
| `ELINS_Library` | ✓ | 121 |
| `Lawbridg References` | ✓ | 0 |
| `Narrative_Architecture` | ✓ | 112 |

`Lawbridg References` shows zero text-file matches at depth ≤ 3 at
prereg time — either the content is in excluded binary formats or sits
at deeper paths. Ingestion will report counts; if Lawbridg yields zero
ingestible files at run time, that subsystem produces an empty per-library
CSV and is excluded from quorum evaluation. This is documented now to
avoid the appearance of post-hoc adjustment.

### 2.1 Included file types

- `.json`
- `.md`
- `.txt`

### 2.2 Excluded file types

- Binary formats: `.png`, `.jpg`, `.pdf`, `.docx`, `.xlsx`, `.pptx`
- Any file > 5 MB
- Any file lacking extractable text

### 2.3 Metadata extraction

For each file:

| field | source |
|---|---|
| `date` | JSON metadata (`date`, `timestamp`, etc.) → else file mtime |
| `region_label` | JSON `region`/`basin`/`label` → else `"Unknown"` |
| `library` | `"elins"` \| `"lawbridg"` \| `"narrative"` |
| `source` | `"local_library"` |
| `path_relative` | path relative to its subsystem root |

## 3. Metric Computation

Use the existing ELINS metric code (unchanged — frozen per § 8). All
metrics produced through `region_metrics_row` and `build_envelope_weighted_graph`.

| metric | role |
|---|---|
| `delta_pct_total_weak` | DV (PRIMARY) |
| `delta_pct_total` | DV |
| `delta_total_weight` | DV |
| `delta_mean_edge` | DV |
| `delta_inv_weight` | DV |
| `E` | input |
| `r` | input |
| `E_over_r` | derived |
| `orientation_score` | covariate / context |
| `node_count` | covariate / context |
| `body_length` | descriptive |

No new metrics are introduced.

## 4. Output Artifacts

### 4.1 Per-library metric CSVs

- `_scratch/regions_named_with_scale_DVs_elins_library.csv`
- `_scratch/regions_named_with_scale_DVs_lawbridg.csv`
- `_scratch/regions_named_with_scale_DVs_narrative.csv`

### 4.2 Combined local-library CSV

- `_scratch/regions_named_with_scale_DVs_local_libraries_combined.csv`

### 4.3 Combined all-sources CSV (optional)

- `_scratch/regions_named_with_scale_DVs_all_sources_combined.csv`

Concatenates: Outlook + ELINS Library + Lawbridg + Narrative
Architecture. Used only if cross-corpus pooling is the chosen analysis
unit; otherwise per-library and per-corpus CSVs are the inferential
inputs.

## 5. Alternator Analysis Plan

### 5.1 Alternators

Same eight as the Outlook v1.0 run:

- `alt_binary_thresh` (gated, diagnostic only)
- `alt_cont_sigmoid` (gated, diagnostic only)
- `alt_region_US`
- `alt_region_EU`
- `alt_region_MEA`
- `alt_region_APAC`
- `alt_region_Markets`
- `alt_region_Tech`

### 5.2 Models

- M1 (slope test): `DV ~ E_over_r`
- M3 (interaction test): `DV ~ E_over_r + alt + E_over_r:alt`
- 2000 paired sign-flip permutations per (DV × alt) cell
- Random seed: `12345`
- Standard errors: HC3
- Significance: α = 0.05

### 5.3 DVs

The same five DVs as in § 3.

## 6. Tokenization Plan

### 6.1 Legacy free-text tokens

The runner's existing free-text verdict labels remain untouched in the
primary CSV output (preserves backward compatibility per v1.1 § 8).

### 6.2 Canonical v1.1 tokens

A side-car canonical-token file will be produced per corpus:

```
_scratch/up_m123_summary_<corpus>_v1_1_tokens.json
```

The mapping follows v1.1.0 § 7:

| pattern_id | additional condition | canonical token |
|---|---|---|
| 1 | — | `canonical_up_supported` |
| 2 | — | `additive_alt` |
| 3 or 5 | `perm_p_M3_int < α` AND alt is independent | `modulation_robust` |
| 3 or 5 | `perm_p_M3_int ≥ α` AND alt is independent | `modulation_suggestive` |
| 3 or 5 | alt is gated | `gated_only_artifact` |
| 9 | — | `ambiguous` |
| 0 / 4 / 6 | — | `pattern_<id>` (fallback, exploratory only) |

Side-car files do not modify any pre-existing artifact (per v1.1 § 8).

## 7. v1.1 Quorum Evaluation

A side-car JSON will be produced per corpus:

```
_scratch/up_m123_v1_1_quorum_check_<corpus>.json
```

Per v1.1.0 § 6, the corpus supports global regime-dependent UP
modulation iff at least one of:

- **(a)** Same DV qualifies as `modulation_robust` under ≥ 2
  E/r-independent region alternators; OR
- **(b)** ≥ 2 distinct DVs qualify as `modulation_robust` under the
  same E/r-independent alternator.

If neither holds → `meets_v1_1_criterion = false`. Localized cells
(single robust cell satisfying neither (a) nor (b)) are reported with
an explicit "does not meet § 6" annotation.

## 8. Frozen Artifacts

The following must NOT be modified by any task that operates under this
prereg:

```
analysis/physics/alternator/UP_M123_CONTRACT_v1.0.0.md
analysis/physics/alternator/UP_M123_CONTRACT_v1.1.0.md
_scratch/up_m123_summary_v52_2*.csv
_scratch/up_m123_summary_v52_2*.json
_scratch/run_up_m123_analysis.py
_scratch/run_up_m123_region_alt.py
analysis/physics/up_kernel_spec.md
analysis/schema/up_kernel_schema.json
ELINS/*.py
```

All new work is additive.

## 9. Expected Outcomes

This prereg makes **no inferential commitments**. It only defines:

- corpus boundaries
- ingestion rules
- metric computation
- alternator analysis grid
- tokenization
- quorum evaluation
- artifact outputs

A run governed by this prereg produces results; the v1.0 / v1.1
contracts decide whether those results support UP, regime-dependent
modulation, both, or neither. No claim is pre-committed.

## 10. Registration

This prereg is registered at:

- This file: `analysis/physics/alternator/UP_M123_PREREG_v1_2_LOCAL_LIBRARIES.md`
- Index entry in: `analysis/physics/alternator/UP_M123_CORPUS_INDEX.json`

with:

- `id`: `local_libraries_v1_2`
- `status`: `preregistered`
- `paths`: the three subsystem roots in § 2
- `contract_version`: `v1.1.0`

---

## Anchors

- v1.0 contract: [UP_M123_CONTRACT_v1.0.0.md](UP_M123_CONTRACT_v1.0.0.md)
- v1.1 contract: [UP_M123_CONTRACT_v1.1.0.md](UP_M123_CONTRACT_v1.1.0.md)
- Outlook 30d report (prior corpus): [UP_M123_OUTLOOK_30D_REPORT.md](UP_M123_OUTLOOK_30D_REPORT.md)
- Corpus index: [UP_M123_CORPUS_INDEX.json](UP_M123_CORPUS_INDEX.json)
