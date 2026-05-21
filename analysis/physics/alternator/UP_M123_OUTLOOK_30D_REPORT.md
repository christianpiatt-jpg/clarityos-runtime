# UP M1/M2/M3 — Outlook 30-day Newsletter Corpus Report

**Corpus ID:** `outlook_30d_v52_2`
**Contract version:** v1.0.0 (see `analysis/UP_M123_PREREG.md`)
**Headline verdict:** **`UP_not_supported_on_this_corpus_v1_0_prereg`**
**Date locked:** 2026-05-07
**Result file:** [`_scratch/up_m123_outlook_corpus_result.json`](../../../_scratch/up_m123_outlook_corpus_result.json)

This report is an **additive artifact**. It does not modify the contract, the synthetic corpus reports, or any prior summary CSV/JSON.

---

## 1. Corpus description

Real Outlook newsletter ingestion via Microsoft Graph (Path C build).

| field | value |
|---|---|
| Source | FT, WSJ, Economist, WaPo, NYT (newsletters) |
| Window | 2026-04-08 → 2026-05-07 (30 days) |
| Rows | 88 |
| Active regions | US, EU, Markets |
| Empty regions | MEA, APAC, Tech (no senders mapped to those regions) |
| Ingestion module | `_scratch/ingest_outlook_graph.py` |
| Input CSV | `_scratch/regions_named_with_scale_DVs_outlook.csv` |
| Result CSV | `_scratch/up_m123_summary_v52_2_region_alt_full.csv` |

Rows per region: Markets 30, US 30, EU 28.

---

## 2. Pre-flight checks

### 2a. Region presence

| region | rows | source emails (per spec) |
|---|---|---|
| US | 30 | WSJ, WaPo, NYT |
| EU | 28 | Economist |
| Markets | 30 | FT |
| MEA | 0 | (no senders mapped) |
| APAC | 0 | (no senders mapped) |
| Tech | 0 | (no senders mapped) |

### 2b. Independence vs prereg threshold `|corr(alt, E/r)| < 0.20`

| alt | corr(alt, E/r) | strict-prereg compliant? |
|---|---|---|
| `alt_region_US` | −0.36126 | ❌ borderline (over threshold) |
| `alt_region_EU` | +0.45468 | ❌ borderline (over threshold) |
| `alt_region_Markets` | −0.08551 | ✅ compliant |
| `alt_region_MEA` | n/a | degenerate (no data) |
| `alt_region_APAC` | n/a | degenerate (no data) |
| `alt_region_Tech` | n/a | degenerate (no data) |

US and EU are **structurally** region-derived but exceed the strict numeric independence threshold. Markets is the only fully prereg-compliant alternator on this corpus.

### 2c. DV variance (need > 0 for inference)

| DV | variance | nonzero rows |
|---|---|---|
| `delta_pct_total_weak` (PRIMARY) | 6.05×10⁻⁴ | 83/88 |
| `delta_pct_total` | 1.36×10⁻⁴ | 87/88 |
| `delta_total_weight` | 5.31×10⁸ | 87/88 |
| `delta_mean_edge` | 6.85×10⁻¹ | 88/88 |
| `delta_inv_weight` | 2.21×10² | 87/88 |

All five DVs have meaningful variance — primary DV no longer mostly-zero (vs synthetic build).

---

## 3. Primary DV result — `delta_pct_total_weak`

Global M1 (alt-independent) coefficient: **β̂_E = −2.06×10⁻⁴**, parametric p = 0.030, **perm_p = 0.528**.

| alt | compliance | M3 p_int (param) | **M3 perm_p_int** | pattern | verdict |
|---|---|---|---|---|---|
| `alt_region_Markets` | strict | 0.752402 | **0.9205** | 9 | **ambiguous** |
| `alt_region_US` | borderline | 0.091586 | **0.4400** | 9 | ambiguous |
| `alt_region_EU` | borderline | 0.198904 | **0.6455** | 1 | single_slope_UP |
| `alt_region_MEA` | degenerate | n/a | 1.000 | 1* | (degenerate) |
| `alt_region_APAC` | degenerate | n/a | 1.000 | 1* | (degenerate) |
| `alt_region_Tech` | degenerate | n/a | 1.000 | 1* | (degenerate) |

`*` Pattern 1 in the degenerate rows is an artifact of zero-variance alt columns; the regression collapses to M1 only.

### Acceptance #1 check (UP detected)

Per v1.0 contract: primary DV must show Pattern 1 across all *active* independent alts AND `M1 perm_p < 0.05`.

- Pattern 1 across active alts (US=9, EU=1, Markets=9): **❌ false**
- M1 `perm_p = 0.528` < α = 0.05: **❌ false**

> **Explicit statement:** the permutation gate fails (perm_p = 0.528). Primary DV does not support UP detection on this corpus.

---

## 4. Full Markets cell — five DVs at the strict-compliant alt

| DV | M1 β̂_E | M1 p_param | **M1 p_perm** | M3 p_int_param | **M3 p_int_perm** | pattern | verdict |
|---|---|---|---|---|---|---|---|
| `delta_pct_total_weak` | −2.06×10⁻⁴ | 0.030 | 0.528 | 0.752 | 0.921 | 9 | ambiguous |
| `delta_pct_total` | −3.79×10⁻⁵ | 0.446 | 0.921 | 0.485 | 0.957 | 0 | no_signal |
| `delta_total_weight` | −631.05 | **2.6×10⁻¹³²** | **0.000** | **1.5×10⁻¹⁶** | 0.302 | 3 | modulation_unsupported_perm |
| `delta_mean_edge` | −0.01256 | **5.5×10⁻¹¹** | 0.052 | **1.1×10⁻¹³** | 0.278 | 3 | modulation_unsupported_perm |
| `delta_inv_weight` | +0.40502 | **1.0×10⁻⁶⁵** | **0.000** | **5.3×10⁻¹⁰** | 0.519 | 3 | modulation_unsupported_perm |

> **Parametric vs permutation gap.** Three secondary DVs (`delta_total_weight`, `delta_mean_edge`, `delta_inv_weight`) report parametric M3 p_int as low as 10⁻¹⁶ for the interaction term — what would be reported as "decisive modulation" under classical inference. The paired sign-flip permutation gives 0.278–0.519 for the same coefficients. The prereg's perm gate correctly declines to call this modulation. This matches the synthetic calibration prediction (extended_permutation.json: empirical FPR ≈ 2.3% at nominal 5%) that the cumulative-graph design inflates parametric inference.

---

## 5. Verdict counts

Excluding degenerate (no-data) rows for MEA/APAC/Tech.

```
modulation_unsupported_perm    8
non_interpretable_gated_alt    6
no_signal                      4
additive_alt                   3
ambiguous                      2
single_slope_UP                1
hidden_modulation              1
modulation_robust              0
```

> **Explicit:** `modulation_robust = 0`. No DV × region-alt cell survived the perm gate. Acceptance #2 (regime modulation detected) is **not met**.

---

## 6. Interpretation

### 6a. What this falsifies and what it does not

| claim | status under v1.0 prereg on this corpus |
|---|---|
| UP curvature law present in 30-day FT/WSJ/Economist/WaPo corpus | **rejected** (perm gate fails on primary DV) |
| Regime-dependent magnitude in same corpus | **rejected** (no modulation_robust verdicts) |
| Universal Physics theory itself | **untouched** — one corpus, one operationalization, one window |
| The M1/M2/M3 protocol | **validated** as a confound + dependence detector — flags exactly what calibration said it should |

### 6b. Next-move options

1. **Accept the falsification.** Document v1.0's verdict on this corpus and pre-register a new corpus before re-testing.
2. **Expand the corpus.** Add MEA/APAC/Tech sender mappings (e.g., Bloomberg APAC, Al-Monitor) to bring 6 active regions and ~180 rows — closer to the synthetic baseline that detected UP.
3. **Address the cumulative-graph dependence.** Switch from cumulative-through-day-d graphs to per-day snapshot graphs so rows are independent. Closes the parametric-vs-permutation gap; may reveal whether real signal exists under independent observations.
4. **Re-examine the operationalization.** Inspect which ELINS lexical primitives newsletter prose actually activates — DVs and intervention may not capture UP in this register.

---

## 7. Files

| file | role |
|---|---|
| `_scratch/regions_named_with_scale_DVs_outlook.csv` | input — 88 ELINS-on-newsletter rows |
| `_scratch/up_m123_summary_v52_2_region_alt_full.csv` | output — full M1/M3 + permutation + verdict |
| `_scratch/up_m123_outlook_corpus_result.json` | structured JSON of this report |
| `_scratch/region_alt_outlook_run.log` | full per-cell console log |
| `_scratch/ingest_outlook_graph.py` | ingestion module (Path C, MS Graph) |
| `_scratch/run_up_m123_region_alt.py` | M1/M2/M3 + perm runner (auto-detects this CSV) |
