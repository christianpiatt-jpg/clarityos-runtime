# UP M1/M2/M3 — Local-Libraries Corpus Report (v2.0 contract)

**Corpus ID:** `local_libraries_v1_2`
**Contract version:** v2.0.0 (LOCKED 2026-05-08)
**Runner:** [`_scratch/run_up_m123_library_alt_v2_0.py`](../../../_scratch/run_up_m123_library_alt_v2_0.py)
**Headline verdict:** **`UP_not_supported`** · **`v2_0_quorum = not_met`**
**Date evaluated:** 2026-05-08
**Result side-cars:**
[`up_m123_summary_local_libraries_v2_0.csv`](../../../_scratch/up_m123_summary_local_libraries_v2_0.csv) ·
[`*_v2_0_tokens.json`](../../../_scratch/up_m123_summary_local_libraries_v2_0_v2_0_tokens.json) ·
[`up_m123_v2_0_quorum_check_local_libraries.json`](../../../_scratch/up_m123_v2_0_quorum_check_local_libraries.json)

This report is the v2.0 evaluation companion to
[UP_M123_LOCAL_LIBRARIES_V1_4_REPORT.md](UP_M123_LOCAL_LIBRARIES_V1_4_REPORT.md).
The v1.4 evaluation passed v1.1 §6 quorum literally with 4 `modulation_robust`
cells, while documenting 6 robustness caveats. v2.0 codifies those caveats
into 6 binding gates (§3.A–§3.F). This report shows what v2.0 yields when
applied to the same corpus, same input rows, same M1/M3/perm fits — only
the post-classification gating differs.

The pre-v2.0 v1.4 artifacts are **preserved as written** per v2.0 §6.
This is a side-car evaluation, not a re-tokenization of v1.4.

---

## §1. Verdict at a glance

| field | value |
|---|---|
| `meets_v2_0_criterion` | **False** |
| `n_quorum_eligible` cells | **1** |
| Surviving cell | `delta_total_weight × alt_library_narrative` |
| Gate A (primary DV participation) | **FAIL** — surviving cell is on a secondary DV |
| Criterion (a) (same DV across ≥2 alts, sign-consistent) | **FAIL** — only 1 alt qualifies |
| Criterion (b) (≥2 distinct DVs same alt) | **FAIL** — only 1 DV qualifies |
| Gates that demoted v1.4 robust cells | **C** (low-prevalence), **E** (Pattern-5), **F** (numeric independence) |

v1.4 result on the same corpus: `meets_v1_1_criterion = True` with 4 robust
cells. v2.0 demotes 3 of those 4 via specific gates and the survivor lands
on a secondary DV — Gate A then closes the corpus-level claim.

---

## §2. v2.0 thresholds applied

Computed from N = 33 input rows (`E_over_r`-filtered):

| threshold | formula | value here |
|---|---|---:|
| `MIN_PREVALENCE` | `max(8, ⌈0.10·N⌉)` | 8 |
| `SAFE_PREVALENCE` | `max(15, ⌈0.20·N⌉)` | 15 |
| `ALPHA_SAFE` (perm_p threshold for prevalence ≥ SAFE) | constant | 0.05 |
| `ALPHA_LOW_PREV` (perm_p threshold for MIN ≤ prev < SAFE) | constant | 0.01 |
| `PATTERN_5_SHRINKAGE` (M3/M1 magnitude ratio trigger) | constant | 0.5 |
| `PATTERN_5_SE_BLOWUP` (M3 SE / M1 SE trigger) | constant | 5.0 |
| `NUMERIC_INDEP_CORR` (\|corr(alt, E/r)\| ceiling) | constant | 0.20 |

Library-alt prevalence vs thresholds:

| alt | n_pos | tier | required perm_p | \|corr(alt, E/r)\| | passes §3.F |
|---|---:|---|---:|---:|---|
| `alt_library_elins` | 13 | low_prev | 0.01 | 0.343 | ❌ |
| `alt_library_lawbridg` | 4 | **below MIN** | n/a (excluded) | 0.480 | ❌ |
| `alt_library_narrative` | 16 | safe | 0.05 | 0.022 | ✅ |

Region alts are uniformly degenerate (zero positives — all rows have
`region_label = Unknown`); they neither produce inferential cells nor
contribute to quorum. Gated alts remain diagnostic-only per v1.0 §1.

---

## §3. Per-cell v1.4 → v2.0 transition table

The four cells that were v1.1 `modulation_robust` under v1.4:

| DV | alt | β̂_int | v1.4 perm_p_int | v1.4 token | v2.0 token | demoting gate | reason |
|---|---|---:|---:|---|---|---|---|
| `delta_total_weight` | `alt_library_elins` | −262.1 | 0.0420 | `modulation_robust` | **`canonical_misspecified`** | §3.E (Pattern-5) | M1 β̂_E = −227.75, M3 β̂_E = −3.06 → \|M3\|/\|M1\| ≈ 0.013 ≪ 0.5 |
| `delta_total_weight` | `alt_library_lawbridg` | +261.2 | 0.0365 | `modulation_robust` | **`structurally_independent_numerically_correlated`** | §3.F (numeric independence) | \|corr(alt, E/r)\| = 0.480 ≥ 0.20; also fails §3.C (n_pos = 4 < 8) |
| `delta_total_weight` | `alt_library_narrative` | +247.3 | 0.0365 | `modulation_robust` | **`modulation_robust`** ✓ | — | All gates pass; only quorum-eligible cell |
| `delta_inv_weight` | `alt_library_lawbridg` | −0.31 | 0.0410 | `modulation_robust` | **`structurally_independent_numerically_correlated`** | §3.F (numeric independence) | \|corr\| = 0.480 ≥ 0.20; also fails §3.C |

Of the 4 v1.4 robust cells: **1 survives**, 1 reclassified to
`canonical_misspecified`, 2 reclassified to
`structurally_independent_numerically_correlated`. Cells flagged by §3.F
also independently fail §3.C — the lawbridg partition is structurally
fragile on multiple axes.

Cells that were v1.4 Pattern 3/5 but **not** v1.1-robust also re-tokenize
under v2.0 (they were already non-robust; v2.0 changes the label, not the
quorum status). Notable: `delta_inv_weight × alt_library_narrative` had
v1.4 perm_p_int = 0.051 (just above v1.1 α = 0.05); under v2.0 it lands
at `modulation_suggestive` — close but no quorum credit.

---

## §4. The surviving cell — `delta_total_weight × alt_library_narrative`

| field | value |
|---|---:|
| pattern_id | 3 (UP with regime-dependent magnitude) |
| n_pos (narrative) | 16 (≥ SAFE_PREVALENCE = 15) |
| applied perm_p threshold | 0.05 (safe tier) |
| perm_p_M3_int | 0.0365 |
| \|corr(alt, E/r)\| | 0.022 (well below 0.20) |
| Pattern-5 indicator | False (M1 β̂_E = −227.75, M3 β̂_E = −251.39 → ratio 1.10, no shrinkage) |
| β̂_int | +247.3 |
| §3.A (primary DV) | **FAIL** — DV is `delta_total_weight`, primary is `delta_pct_total_weak` |

This cell passes every cell-level gate (C, D, E, F) cleanly. It would
close criterion (a) if a second sign-consistent alt-cell existed for
`delta_total_weight`, or criterion (b) if a second DV-cell existed for
`alt_library_narrative`. Neither does. And §3.A blocks the corpus
claim regardless: a global modulation claim must touch the primary
DV.

---

## §5. Why each quorum gate fails

**Gate A — primary DV participation:** the surviving cell sits on
`delta_total_weight`. The primary DV `delta_pct_total_weak` has zero
quorum-eligible cells (its v1.4 perm_p_M1_E was 0.362, and its M3 cells
under library alts produced patterns 4 / 9 / 9, no Pattern 3/5 with
perm < α). v2.0 §3.A is binding — modulation of a curvature law one
cannot detect in M1 is not a meaningful corpus claim.

**Criterion (a) — same DV across ≥2 alts, sign-consistent:** the
surviving DV (`delta_total_weight`) has 1 quorum-eligible cell
(`alt_library_narrative`). Need 2 alts. Fails.

> Note on §3.B sign consistency, even though (a) already fails on count:
> if all three v1.4 robust cells on `delta_total_weight` had passed §3.C–F,
> §3.B would still have rejected criterion (a) — β̂_int values were
> {−262, +261, +247}, which violates sign consistency (one negative, two
> positive). The v1.4 report flagged this as caveat C2; v2.0 §3.B turns
> that observation into a binding rejection.

**Criterion (b) — same alt across ≥2 distinct DVs:** the surviving alt
(`alt_library_narrative`) has 1 quorum-eligible DV
(`delta_total_weight`). Need 2 DVs. Fails.

---

## §6. Side-by-side: v1.4 vs v2.0

| field | v1.4 (v1.1 contract) | v2.0 (v2.0 contract) |
|---|---|---|
| input rows | 33 | 33 (unchanged) |
| alt grid | 11 (8 v1.0/1.1 + 3 v1.4 library) | 11 (unchanged) |
| robust cells | **4** | 1 (only narrative × delta_total_weight retains `modulation_robust`) |
| primary-DV robust | 0 | 0 |
| meets quorum | ✅ literal | ❌ |
| robustness caveats raised | 6 (C1–C6) | gates C1/C3/C5/C6 now binding; C2/C4 binding via §3.B/§3.D |
| classifier ordering | Pattern 3 fires before Pattern 5 | **Pattern 5 fires before Pattern 3** (§3.E) |
| token taxonomy size | 8 (v1.1 §7) | 10 (v2.0 §4 — adds `canonical_misspecified` and `structurally_independent_numerically_correlated`) |

The empirical content of the runs is identical (same fits, same
permutations, same RNG seed). v2.0 closes the corpus claim that v1.4
literally satisfied — exactly the design intent.

---

## §7. Files

| file | role |
|---|---|
| `_scratch/regions_named_with_scale_DVs_local_libraries_combined.csv` | input — 33 rows |
| `_scratch/run_up_m123_library_alt_v2_0.py` | v2.0 sibling runner |
| `_scratch/up_m123_summary_local_libraries_v2_0.csv` | per-cell results — 55 rows + 6 gate flags + v2.0 token |
| `_scratch/up_m123_summary_local_libraries_v2_0_v2_0_tokens.json` | canonical token side-car |
| `_scratch/up_m123_v2_0_quorum_check_local_libraries.json` | quorum side-car (Gate A/B/criteria) |
| `analysis/physics/alternator/UP_M123_CONTRACT_v2.0.0.md` | governing contract (locked) |
| `analysis/physics/alternator/UP_M123_LOCAL_LIBRARIES_V1_4_REPORT.md` | predecessor report (preserved) |
| `_scratch/up_m123_local_libraries_v1_4_result.json` | v1.4 result (preserved) |
| `analysis/physics/alternator/UP_M123_CORPUS_INDEX.json` | corpus index — entries `local_libraries_v1_2_result_v1_4` and `local_libraries_v1_2_result_v2_0` |
