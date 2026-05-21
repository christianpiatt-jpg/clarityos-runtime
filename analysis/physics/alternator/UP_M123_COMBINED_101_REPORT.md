# UP^ M1/M2/M3 — Combined Corpus (Outlook + ELINS Library) Report

_Generated: 2026-05-08 02:21Z_

This report is a **side-car analysis** under the v1.1 amendment (`UP_M123_CONTRACT_v1.1.0.md`). The v1.0 governing preregistration (`UP_M123_CONTRACT_v1.0.0.md`) is **not** modified by this run; neither are the per-corpus summary CSVs/JSONs from prior corpora.

## 1. Corpus description

- **id**: `combined_101_v1_2`
- **rows**: 101 (Outlook: 88 + ELINS Library: 13)
- **date span**: 2026-03-23 → 2026-05-07
- **region distribution**: {'Markets': 30, 'US': 30, 'EU': 28, 'Unknown': 13}
- **contract version**: v1.1.0
- **input**: `_scratch/regions_named_with_scale_DVs_combined.csv`

## 2. Ingestion summary

**Outlook leg** (`_scratch/ingest_outlook_graph.py`)
- Source: Microsoft Graph mail folder, configured sender domains (FT, WSJ, Economist, WaPo, NYT)
- Rows produced: 88
- CSV: `_scratch/regions_named_with_scale_DVs_outlook.csv` (frozen by prior run)

**ELINS Library leg** (`_scratch/ingest_elins_library.py`)
- Source: `C:\Users\chris\ClarityOS_Library\Clarity_Library\02_Subsystems\ELINS_Library`
- File types: .json / .md / .txt (recursive)
- Rows produced: 13
- CSV: `_scratch/regions_named_with_scale_DVs_elins_library.csv`
- Region resolution: JSON field (region/basin/label) → canonical REGION_CODES, else `Unknown`. The 121 .txt/.md files in the library produced 0 canonical region matches and were routed through the `Markets` ELINS profile with their cluster label overridden to `Unknown` for graph induction.

**Combiner** (`_scratch/combine_regions_metrics_outlook_elins.py`)
- Concat row-wise → 101 rows total. `source` column distinguishes provenance.

## 3. Pre-flight checks

- `regions_named_with_scale_DVs_combined.csv` rows: 101 ✓
- `up_m123_summary_combined_region_alt_full.csv` rows: 40 (expected 5 DVs × 8 alts = 40)
- All five DVs present: ['delta_inv_weight', 'delta_mean_edge', 'delta_pct_total', 'delta_pct_total_weak', 'delta_total_weight']
- All eight alternators present: ['alt_binary_thresh', 'alt_cont_sigmoid', 'alt_region_APAC', 'alt_region_EU', 'alt_region_MEA', 'alt_region_Markets', 'alt_region_Tech', 'alt_region_US']
- Frozen artefacts unchanged: confirmed via separate sanity step.

## 4. Primary-DV summary (`delta_pct_total_weak`)

| alt | kind | pattern | M1 p_E | M3 p_int | perm p_int | verdict (legacy) |
|---|---|---:|---:|---:|---:|---|
| `alt_binary_thresh` | gated | 3 | 0.0393 | 0.0045 | 0.2655 | `non_interpretable_gated_alt` |
| `alt_cont_sigmoid` | gated | 3 | 0.0393 | 0.0043 | 0.2585 | `non_interpretable_gated_alt` |
| `alt_region_US` | region | 9 | 0.0393 | 0.0738 | 0.4210 | `ambiguous` |
| `alt_region_EU` | region | 9 | 0.0393 | 0.9105 | 0.9725 | `ambiguous` |
| `alt_region_MEA` | region | 1 | 0.0393 | — | 1.0000 | `single_slope_UP` |
| `alt_region_APAC` | region | 1 | 0.0393 | — | 1.0000 | `single_slope_UP` |
| `alt_region_Markets` | region | 9 | 0.0393 | 0.5516 | 0.8625 | `ambiguous` |
| `alt_region_Tech` | region | 1 | 0.0393 | — | 1.0000 | `single_slope_UP` |

## 5. Full alternator-grid pattern summary

| DV | `alt_binary_thresh` | `alt_cont_sigmoid` | `alt_region_APAC` | `alt_region_EU` | `alt_region_MEA` | `alt_region_Markets` | `alt_region_Tech` | `alt_region_US` |
|---|---|---|---|---|---|---|---|---|
| `delta_inv_weight` | 3 | 3 | 1 | 3 | 1 | 3 | 1 | 3 |
| `delta_mean_edge` | 3 | 3 | 1 | 9 | 1 | 5 | 1 | 3 |
| `delta_pct_total` | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 |
| `delta_pct_total_weak` | 3 | 3 | 1 | 9 | 1 | 9 | 1 | 9 |
| `delta_total_weight` | 3 | 3 | 1 | 3 | 1 | 3 | 1 | 3 |

Legend: 0=null, 1=canonical UP, 2=additive, 3=regime-dependent magnitude, 4=gated additive, 5=regime-flipping, 6=hidden modulation, 9=ambiguous.

## 6. Verdict / token histograms

**Legacy free-text verdicts** (from `verdict_perm_aware` in CSV):

- `ambiguous` — 4
- `hidden_modulation` — 1
- `modulation_unsupported_perm` — 8
- `no_signal` — 7
- `non_interpretable_gated_alt` — 8
- `single_slope_UP` — 12

**v1.1 canonical tokens** (from `up_m123_summary_combined_region_alt_full_v1_1_tokens.json`):

- `ambiguous` — 4
- `canonical_up_supported` — 12
- `gated_only_artifact` — 8
- `modulation_suggestive` — 8
- `pattern_0` — 7
- `pattern_6` — 1

> **Degeneracy note.** 12 of the `canonical_up_supported` tokens come from cells where the region alternator column has zero variance in the corpus (no rows in MEA/APAC/Tech). In those cells M3 trivially collapses to M1 — the alternator never moves — so the Pattern-1 classification is mechanical, not a real test of E/r-independence. Per v1.0 §2 these are downgraded to exploratory and excluded from the v1.0 verdict computed in §7.

Degenerate Pattern-1 cells:

- `delta_pct_total_weak × alt_region_MEA` (alt column all-zero)
- `delta_pct_total_weak × alt_region_APAC` (alt column all-zero)
- `delta_pct_total_weak × alt_region_Tech` (alt column all-zero)
- `delta_total_weight × alt_region_MEA` (alt column all-zero)
- `delta_total_weight × alt_region_APAC` (alt column all-zero)
- `delta_total_weight × alt_region_Tech` (alt column all-zero)
- `delta_mean_edge × alt_region_MEA` (alt column all-zero)
- `delta_mean_edge × alt_region_APAC` (alt column all-zero)
- `delta_mean_edge × alt_region_Tech` (alt column all-zero)
- `delta_inv_weight × alt_region_MEA` (alt column all-zero)
- `delta_inv_weight × alt_region_APAC` (alt column all-zero)
- `delta_inv_weight × alt_region_Tech` (alt column all-zero)

## 7. Corpus verdicts

**v1.0 verdict (governing preregistration, `UP_M123_CONTRACT_v1.0.0.md`):**

- `v1_0_verdict`: **UP_not_supported**
- inferential cells examined on primary DV (`delta_pct_total_weak`, region alt, non-degenerate): 3
- degenerate region alts excluded: `alt_region_MEA`, `alt_region_APAC`, `alt_region_Tech`
- cells meeting v1.0 §4 inferential bar (Pattern 1 ∧ analytic p_E < α ∧ perm_p_M1_E < α): 0

**v1.1 quorum (amendment, `UP_M123_CONTRACT_v1.1.0.md` § 6):**

- `meets_v1_1_criterion`: **False**
- `max_robust_cells_by_dv` (criterion (a)): 0 (≥2 satisfies (a))
- `max_robust_cells_by_alt` (criterion (b)): 0 (≥2 satisfies (b))
- robust cells: 0

## 8. Interpretation

The combined corpus **does NOT meet** the v1.1 § 6 corpus-level criterion for global regime-dependent UP modulation. Neither

- (a) ≥2 robust cells for the same DV across independent region alts, NOR
- (b) ≥2 robust cells for the same region alt across distinct DVs

is satisfied. Any individual `modulation_robust` cell — if present — is a **localized / exploratory** finding under v1.1 § 6 and is explicitly flagged for follow-up rather than counted as evidence of global regime-dependent modulation.

Cells in non-canonical pattern fallbacks (`pattern_0`, `pattern_4`, `pattern_6`) are exploratory only and do not contribute to the quorum on either axis. Cells under gated alternators (`alt_binary_thresh`, `alt_cont_sigmoid`) reach Pattern 3/5 by construction (the alternator is a function of E/r), so their Pattern-3/5 hits are tokenised as `gated_only_artifact` and are excluded from the quorum.

## 9. Next-corpus recommendations

- **Resolve `Unknown` region pollution.** The 13 ELINS-library rows all landed in the `Unknown` bucket because none of the .txt/.md library files carry a JSON `region`/`basin`/`label` field. Two additive options without modifying frozen artefacts:
  1. Add a deterministic filename-pattern resolver as a third fallback in `ingest_elins_library.py` (e.g., `PanNikkei`/`Asia` → `APAC`, `AfricaBasin` → `MEA`, `USUrbanCorridor` → `US`, `Markets_Corridor` → `Markets`).
  2. Emit JSON sidecars (`<file>.elins.json`) carrying explicit `region` tags for high-signal library files.
- **Expand canonical-region coverage.** The combined corpus has zero rows in `MEA`, `APAC`, `Tech`. Quorum criterion (a) is structurally hard to meet without ≥2 populated independent region alternators, so the next ingest pass should target sources that feed those buckets (Caixin/Nikkei/Aaj Tak for APAC, Al Jazeera / Africa Report for MEA, semiconductor / AI trade pubs for Tech).
- **Ingest the remaining preregistered libraries.** `UP_M123_PREREG_v1_2_LOCAL_LIBRARIES.md` declared three roots; only ELINS_Library was ingested in this pass. Next pass: `Lawbridg References` (0 files at prereg time — recheck) and `Narrative_Architecture` (112 files at prereg time).
- **Power.** N=101 with 4 occupied region buckets is small for stable Pattern 3/5 detection on per-region splits. Targeting N≈300 across ≥4 region buckets is a reasonable next milestone.

---

Side-car artefacts:

- `_scratch/up_m123_summary_combined_region_alt_full.csv` (40 rows)
- `_scratch/up_m123_summary_combined_region_alt_full_v1_1_tokens.json`
- `_scratch/up_m123_v1_1_quorum_check_combined.json`
