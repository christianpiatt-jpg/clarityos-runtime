# UP M1/M2/M3 — Local-Libraries Corpus Report (v1.4 alternators)

**Corpus ID:** `local_libraries_v1_2`
**Alternator amendment:** `library_alternators_v1_4`
**Contract version:** v1.0.0 + v1.1.0 (no contract modified)
**Headline verdict:** **`v1_1_quorum_met_literally_but_failing_robustness_checks`**
**Date locked:** 2026-05-08
**Result file:** [`_scratch/up_m123_local_libraries_v1_4_result.json`](../../../_scratch/up_m123_local_libraries_v1_4_result.json)

This report is **additive**. No contract or earlier prereg/CSV/JSON is
modified. It is the canonical record of the first corpus to technically
pass the v1.1 §6 quorum, with full documentation of the robustness gaps
that motivate the v2.0 contract amendment.

---

## 1. Corpus description

| field | value |
|---|---|
| Source | ClarityOS local library subsystems (operator's OneDrive) |
| Subsystems | ELINS Library, Lawbridg References (PDF via v1.3), Narrative Architecture |
| Ingestion module | `_scratch/ingest_local_libraries.py` |
| PDF helper | `_scratch/pdf_to_text.py` (pdfminer.six) |
| Input rows (combined CSV) | 33 |
| After `E_over_r` NaN filter | 32 |
| Active regions | Unknown (33 rows; alt_region_* are degenerate) |
| Active libraries | elins (13), lawbridg (4), narrative (16) |
| DVs | 5 kernel DVs (primary: `delta_pct_total_weak`) |
| Alts evaluated | 8 + 3 = 11 (gated diagnostic + 6 region degenerate + **3 library inferential**) |
| Permutation reps | 2000 paired sign-flip (RNG seed 12345) |

## 2. Pre-flight checks

### 2a. Why region alts are degenerate here

100% of input rows have `region_label = "Unknown"` because no source
file in any of the three subsystems carried `region`/`basin`/`label`
metadata. Per v1.2 §2.3 the Unknown fallback fires; per v1.4 §1 this
is the motivating condition for library alternators.

### 2b. Library alts — prevalence and empirical independence

| alt | positive | negative | corr(alt, E/r) | passes \|corr\|<0.20? | low_prev? |
|---|---|---|---|---|---|
| `alt_library_elins` | 13 | 20 | **+0.318** | ❌ | no |
| `alt_library_lawbridg` | 4 | 29 | **−0.523** | ❌ | **yes** |
| `alt_library_narrative` | 16 | 17 | +0.033 | ✅ | no |

v1.4 §2.1 admits library alts on **structural** grounds (filesystem
location, not derived from E/r). Empirically two of three correlate
with E/r above the v1.0/v1.1 numeric threshold. **Lawbridg's
−0.52 correlation is stronger than the gated alts in the
extended-simulation calibration produced false positives at.**

### 2c. DV variance

| DV | variance | nonzero rows |
|---|---|---|
| `delta_pct_total_weak` (PRIMARY) | 2.80×10⁻³ | 21/33 |
| `delta_pct_total` | 4.98×10⁻⁴ | 32/33 |
| `delta_total_weight` | 1.81×10⁸ | 32/33 |
| `delta_mean_edge` | 2.31×10⁻¹ | 32/33 |
| `delta_inv_weight` | 3.13×10² | 32/33 |

All five DVs have variance; primary DV no longer mostly-zero.

---

## 3. Primary DV result — `delta_pct_total_weak`

Global M1 coefficient: **β̂_E = −3.25×10⁻⁴**, parametric p = 0.022,
**permutation p = 0.362**.

| alt | M3 perm_p_int | pattern | v1.1 token | v1.0 §7 AC#1? |
|---|---|---|---|---|
| `alt_library_elins` | 0.579 | 4 | `pattern_4` | ❌ |
| `alt_library_lawbridg` | 0.619 | 9 | `ambiguous` (low_prev) | ❌ |
| `alt_library_narrative` | 0.239 | 9 | `ambiguous` | ❌ |

> **Explicit:** `M1 perm_p = 0.362`, far above α = 0.05. Primary DV
> does not support UP under any active independent alt. **v1.0 §7 AC#1
> is NOT met.**

---

## 4. The four `modulation_robust` cells (v1.1 §6 literal pass)

| DV | alt | β̂_int | parametric p_int | **perm_p_int** | low_prev | \|corr(alt, E/r)\| |
|---|---|---|---|---|---|---|
| `delta_total_weight` | `alt_library_elins` | **−262.1** | 1.2×10⁻³⁰⁹ | 0.0420 | no | 0.32 |
| `delta_total_weight` | `alt_library_lawbridg` | **+261.2** | 5.7×10⁻¹⁰ | 0.0365 | **yes (n=4)** | **0.52** |
| `delta_total_weight` | `alt_library_narrative` | +247.3 | 1.1×10⁻¹⁰⁴ | 0.0365 | no | 0.03 |
| `delta_inv_weight` | `alt_library_lawbridg` | −0.31 | 2.3×10⁻¹⁰ | 0.0410 | **yes (n=4)** | **0.52** |

### Quorum (literal)

```
criterion_a_same_DV_two_alts:    True   (delta_total_weight × 3 library alts)
criterion_b_same_alt_two_DVs:    True   (alt_library_lawbridg × 2 DVs)
meets_v1_1_criterion:            True
robust_count:                    4
```

### Why "literal" needs heavy qualification

#### C1 — Primary DV not supported
M1 perm gate fails at p = 0.362; pattern is 4 / 9 / 9 across active
alts. v1.0 §7 AC#1 explicitly fails. Modulation evidence on secondary
DVs is reported, but the load-bearing UP claim is absent.

#### C2 — Sign inconsistency
β̂_int values for `delta_total_weight`: elins **−262**, lawbridg
**+261**, narrative **+247**. A genuine library-modulation of UP
curvature should produce coherent signs across the partition. Three
robust cells with elins flipped opposite to lawbridg+narrative is a
structural irregularity — the alt is functioning as a regime *flag*
(which-library-is-this), not a modulating factor in a unified
mechanism.

#### C3 — Low-prevalence partitions contribute 50% of robust cells
`alt_library_lawbridg` has only 4 positive rows. M3 SE under such
prevalence is unreliable. Two of four robust cells (delta_total_weight
× lawbridg, delta_inv_weight × lawbridg) involve this partition.

#### C4 — Permutation p clusters at α
All four robust cells have perm_p_M3_int in {0.0365, 0.0365, 0.0410,
0.0420}. None safely below e.g. 0.01. The synthetic calibration
showed parametric inference is conservative under permutation; here
the gap has narrowed but the cells sit right at the boundary.

#### C5 — Pattern-5 dynamics under-recognised
`delta_total_weight × elins`: M1 β̂_E = −227.75; M3 β̂_E = −3.06. That
is a **74× shrinkage** with no sign flip — Pattern 5 territory
("canonical-misspecified / regime-flipping"). My classifier returns
Pattern 3 because Pattern 3's check fires before Pattern 5's, but the
data structure matches Pattern 5. The v1.1 token taxonomy collapses
Pattern 3 and Pattern 5 (when perm-significant) into
`modulation_robust`, masking the misspecification flavour. Reading
this cell as "regime-modulated UP" overstates what the data supports.

#### C6 — Library alts are not numerically E/r-independent
Empirical correlations of {+0.32, −0.52, +0.03} mean the v1.4
admit-on-structural-grounds clause is doing real work. **Lawbridg's
|corr| = 0.52 is large enough that its modulation_robust contribution
is functionally the gated-alt phenomenon under a structural label.**
The synthetic suite previously demonstrated that gated alts produce
phantom modulation; that mechanism is at work here for two of the
four robust cells.

---

## 5. Verdict counts (active rows only — gated and library)

```
pattern_0                 5
ambiguous                 4
gated_only_artifact       4
modulation_robust         4
pattern_4                 3
canonical_up_supported    2
modulation_suggestive     2
additive_alt              1
```

The two `canonical_up_supported` cells are `delta_mean_edge ×
{lawbridg, narrative}` — small but real.

---

## 6. Acceptance summary

| criterion | result |
|---|---|
| v1.0 §7 AC#1 (UP detected on primary DV) | **❌ not met** (perm gate failure) |
| v1.1 §6 quorum (regime modulation, literal) | **✅ met** (4 robust cells) |
| v1.1 §6 quorum (regime modulation, robustness-checked) | **❌ would not meet** under any of C1–C6 |
| Robust cells on primary DV | 0 |
| Robust cells low-prevalence | 2/4 |
| Robust cells failing numeric independence | 1/4 (lawbridg, |corr|=0.52) |
| Robust cells with sign-coherent quorum | 0/4 (signs split −262 vs +261/+247) |

**One-line verdict:** v1.1 §6 met as written, but the pass is
dominated by a low-prevalence partition, a parametric-vs-permutation
boundary effect, and an alt that fails numeric independence. Not a
clean confirmation of regime-dependent UP.

---

## 7. Proposed v2.0 contract amendments (from this run)

The robustness gaps surfaced in §4 motivate six tightenings, captured
in [`UP_M123_CONTRACT_v2.0.0_DRAFT.md`](UP_M123_CONTRACT_v2.0.0_DRAFT.md):

| id | name | summary |
|---|---|---|
| A | primary_DV_participation_required | v1.1 §6 claim requires ≥1 robust cell on primary DV |
| B | sign_consistency_across_robust_cells | Criterion (a) cells must share β̂_int sign |
| C | low_prevalence_exclusion | n_pos < MIN_PREVALENCE cells cannot contribute |
| D | stricter_perm_p_threshold_for_low_prevalence | low-prev cells need perm_p < 0.01 |
| E | Pattern_5_exclusion_from_modulation_robust | huge-shrinkage cells tokenized as `canonical_misspecified` |
| F | numeric_independence_required_for_robust_contribution | structural admissibility ≠ quorum admissibility |

Per v1.1 §8 backward compatibility, these are **prospective**. This
v1.4 run's archived artifacts are preserved as written.

---

## 8. Files

| file | role |
|---|---|
| `_scratch/regions_named_with_scale_DVs_local_libraries_combined.csv` | input — 33 rows |
| `_scratch/up_m123_summary_local_libraries_v1_4.csv` | runner output — 55 rows |
| `_scratch/up_m123_summary_local_libraries_v1_4_v1_1_tokens.json` | canonical token side-car |
| `_scratch/up_m123_v1_1_quorum_check_local_libraries.json` | quorum side-car |
| `_scratch/up_m123_local_libraries_v1_4_result.json` | structured JSON of this report |
| `_scratch/library_alt_run.log` | full per-cell console log |
| `_scratch/run_up_m123_library_alt.py` | runner |
| `_scratch/ingest_local_libraries.py` | ingestion (frozen) |
| `_scratch/pdf_to_text.py` | PDF helper (frozen) |
| `analysis/physics/alternator/UP_M123_PREREG_v1_4_LIBRARY_ALTERNATORS.md` | prereg (frozen) |
