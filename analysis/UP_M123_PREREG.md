# UP M1/M2/M3 Detection Protocol — Pre-registration v1.0

**Status:** locked. Future real-data applications of the Universal Physics
curvature-law protocol must follow this contract exactly. Diagnostic
deviations are permitted in reported diagnostics but do not contribute to
UP claims.

**Date locked:** 2026-05-07
**Calibration corpus:** 30-day × 6-region synthetic ELINS dataset, N = 180 rows
**Reference scripts:**
- DV layer: [ELINS/region_metrics.py](../ELINS/region_metrics.py) v52.2
- Inference: [_scratch/run_up_m123_region_alt.py](../_scratch/run_up_m123_region_alt.py)
- Simulation calibration: [_scratch/extended_simulation.py](../_scratch/extended_simulation.py)

---

## 1. Dependent variables (5 only)

| DV | role | description |
|---|---|---|
| `delta_pct_total_weak` | **PRIMARY** | percent-change in weak-triangle total weight (pre→post orientation) |
| `delta_pct_total` | secondary | percent-change in all-triangle total weight |
| `delta_total_weight` | secondary | absolute change in all-triangle total weight |
| `delta_mean_edge` | secondary | absolute change in mean edge weight |
| `delta_inv_weight` | secondary | absolute change in inverse-weight triangle sum |

The legacy `delta` (triangle homogeneity / coefficient of variation) is **EXCLUDED** from UP detection. CV is scale-invariant under multiplicative orientation, so it does not move under uniform interventions and yields no signal. It may be reported only for explicit scale-invariance diagnostics.

## 2. Alternators

- **Required:** at least one E/r-INDEPENDENT alternator. Acceptable forms: region indicator (`alt_region_<X>`), domain indicator, or any graph-extrinsic categorical/binary variable. Independence verification: |corr(alt, E_over_r)| < 0.20 must hold on the test corpus.
- **Disallowed in canonical inference:** E/r-gated alternators (e.g. `1[E/r > median]`, `sigmoid(k·(E/r − θ))`). These may appear in diagnostic output but **gated-alt Pattern 3/5 results are non-interpretable** and cannot support modulation claims.

## 3. Models — simplified spec, no controls

| model | formula |
|---|---|
| M1 (canonical) | `DV ~ E_over_r` |
| M2 (additive) | `DV ~ alt` |
| M3 (interaction) | `DV ~ E_over_r + alt + E_over_r:alt` |

- Standard errors: **HC3** (heteroskedasticity-robust)
- Significance: **α = 0.05**

## 4. Permutation (paired sign-flip)

Under H₀ of zero treatment effect, the DV's sign is exchangeable per row:

- `nperm = 2000`
- Random seed: `12345` (numpy `default_rng`)
- Per rep: refit M1 and M3 on sign-flipped DV
- `perm_p_M1_E = P(|β_E_perm| ≥ |β_E_obs|)`
- `perm_p_M3_int = P(|β_int_perm| ≥ |β_int_obs|)`

## 5. Pattern classification (unchanged from v52.2)

| ID | pattern | meaning |
|---|---|---|
| 0 | no signal | no significant E/r, alt, or interaction |
| 1 | single-slope UP | M1 and M3 both find E/r; no alternator role |
| 2 | additive alt | UP holds + parallel additive alternator |
| 3 | UP with regime-dependent magnitude | E/r slope varies with alt |
| 4 | gated additive (canonical phantom) | M1 sees E/r but the alt is the real driver |
| 5 | regime-flipping slopes (M1 misspecified) | alt flips sign of E/r effect |
| 6 | hidden modulation | M1 misses, M3 catches via interaction |
| 9 | ambiguous | mixed signals |

## 6. Inference rule — `verdict_perm_aware`

```
if alt_kind == "gated" and pattern in {3, 5}:
    → "non_interpretable_gated_alt"     # diagnostic only
elif pattern in {3, 5}:
    if perm_p_M3_int < α:               → "modulation_robust"
    else:                                → "modulation_unsupported_perm"
elif pattern == 1:                       → "single_slope_UP"
elif pattern == 2:                       → "additive_alt"
elif pattern == 0:                       → "no_signal"
elif pattern == 4:                       → "gated_phantom"
elif pattern == 6:                       → "hidden_modulation"
else:                                    → "ambiguous"
```

## 7. Acceptance criteria for "UP detected" on a corpus

A corpus is said to **support the Universal Physics curvature law** iff all three hold:

1. The **primary DV** (`delta_pct_total_weak`) is classified Pattern 1 or 2 under at least one E/r-independent alternator.
2. M1 β̂_E for the primary DV satisfies **both** parametric p < α **and** `perm_p_M1_E < α`.
3. No `verdict_perm_aware == "modulation_robust"` claim relies on a gated alt; gated-alt Pattern 3/5 is never supportive.

A corpus is said to **support regime-dependent UP modulation** iff:

1. At least one DV under an E/r-independent alternator yields `verdict_perm_aware == "modulation_robust"`.

Otherwise: the simpler model (single-slope UP, additive alt, or no signal) prevails.

## 8. Calibration evidence — simulation suite v52

Under the worst-case canonical misspecification (`slope_diff` thresholded `N=200`), parametric p for the interaction term is slightly **conservative** vs paired-permutation: empirical FPR ≈ 2.3% at nominal α = 5%. The permutation-backed inference rule is therefore safe — does not over-reject — and using it as the gating criterion for modulation claims is sound. Source: [_scratch/extended_permutation.json](../_scratch/extended_permutation.json).

## 9. Versioning & traceability

| component | version | location |
|---|---|---|
| Pre-reg spec | v1.0 | this file |
| DV layer | v52.2 | `ELINS/region_metrics.py` |
| Inference script | v52.2 | `_scratch/run_up_m123_region_alt.py` |
| Simulation calibration | v52.1 | `_scratch/extended_simulation.py` |
| Pattern classifier | v52.2 | `classify()` in inference script |

Any modification to DV definitions, model specs, permutation parameters, or the inference rule requires a new pre-reg version (v1.1, v2.0, …) and a re-run of the calibration suite.
