# UP^ M1/M2/M3 Alternator-Independence Contract — v1.0.0

This document is a **binding methodological contract** for any future
M1/M2/M3 inferential run on UP^ kernel DVs. It codifies four rules:

1. E/r-gated alternators are banned from canonical inferential claims.
2. Every inferential run must include at least one E/r-independent
   alternator.
3. Paired sign-flip permutation is mandatory for `beta_E (M1)` and
   `beta_int (M3)`.
4. Pattern 3 and Pattern 5 classifications are **inferential only when
   the permutation null also rejects H0**; analytic-only classifications
   are reported as suggestive.

This contract is a **companion** to:

- `analysis/physics/up_kernel_spec.md` — UP^ kernel spec (DV definitions).
- `analysis/physics/alternator/PHYSICS_UP_SPEC_v1.1.0.md` — UP regime-law spec.
- `analysis/physics/alternator/UP_PREREGISTERED_ANALYSIS.md` — analysis plan.
- `analysis/physics/alternator/PROOF_PIPELINE.md` — staged pipeline.

It **does not modify** any of those documents. It tightens the rules
applied to runs governed by them.

---

## 0. Why this contract exists

The first M1/M2/M3 pass on the v52.2 ELINS corpus (180 named regions x 6
groups x 30 days) used **E/r-gated** alternators by construction:

- `alt_binary_thresh = 1[E/r > median(E/r)]`
- `alt_cont_sigmoid  = sigmoid(5 * (E/r - median(E/r)))`

A follow-up run (`_scratch/run_up_m123_analysis_region_alt.py`) repeated
the same M1/M2/M3 fits and the same paired sign-flip permutation, but
substituted **E/r-independent** region-based alternators
(`alt_region_US = 1[region_label == 'US']`,
`alt_region_Markets = 1[region_label == 'Markets']`).

The two runs disagree systematically:

- The **primary DV** (`delta_pct_total_weak`) shifted from Pattern 9
  ("ambiguous") under gated alternators to Pattern 1 ("single-slope
  canonical UP, M1 ≈ M3, no alternator action") under both region
  alternators, with the M1 E/r slope highly significant under the
  permutation null.
- For **every DV**, in the E/r-independent run, no M3 interaction
  coefficient survived the paired sign-flip permutation
  (`perm_p_M3_int ∈ [0.57, 0.96]`), even when the analytic classifier
  still returned Pattern 3.
- Analytic Pattern 3 / Pattern 5 results from the gated run mostly
  collapsed (to Pattern 1 / 2 / 4) under E/r-independent alternators.

The conclusion of that exploratory pass — that gated alternators
inflate the apparent regime-by-E/r interaction — is what this contract
makes binding for any future inferential run.

The empirical run does not authorize the contract by itself
(preregistrations are method-only); it provides the motivation. The
contract below is method-only and applies prospectively.

---

## 1. Ban on E/r-gated alternators in inferential claims

For any **inferential** M1/M2/M3 claim about a UP^ kernel DV, the
alternator A used in the inferential models MUST NOT be a function of
E/r.

Specifically PROHIBITED as the inferential alternator:

- Threshold form: `A = 1[E/r > θ]` for any θ derived from E/r.
- Continuous form: `A = sigmoid(c * (E/r − θ))` or any monotone function
  of E/r.
- Quantile form: `A = 1[E/r > q-th quantile(E/r)]`.
- Any A whose value depends mathematically on E/r in the analysis
  sample.

E/r-gated alternators MAY appear in a run **only as exploratory
diagnostics**, must be clearly labelled as such, and must be reported
**alongside** (not in place of) at least one E/r-independent
inferential alternator. They MUST NOT be substituted for the
inferential alt or treated as a headline result.

---

## 2. Required E/r-independent alternator(s)

Each inferential M1/M2/M3 run MUST include at least one E/r-independent
alternator A. Acceptable constructions:

| Form | Definition | A ⫫ (E/r) argument |
|---|---|---|
| **Categorical / region** | `A = 1[label ∈ G]` for some preregistered partition G of the labels. | By construction: A is a function of an external label, not of E/r. |
| **Pre-period covariate** | A determined entirely from data observed before the analysis window. | Temporal precedence: A is fixed before E/r at the analysis window is observed. |
| **External signal** | A determined by a covariate that is not derivable from the analysis window's E/r values. | Independence argued from data-generating process; correlation must still be reported. |

Acceptability of any specific A construction MUST be justified in the
preregistration with an explicit argument for `A ⫫ (E/r)`. When A is
categorical, the argument is satisfied by construction. When A is
continuous, A's correlation with E/r MUST be reported, and the run must
preregister an upper bound on `|Pearson r(A, E/r)|` (default: 0.10) for
A to qualify as E/r-independent. A construction that fails its bound
ex post is downgraded to exploratory.

---

## 3. Paired sign-flip permutation

Every inferential M1/M2/M3 run MUST include a paired sign-flip
permutation that produces, for each (DV, alt) pair, both:

- **`perm_p_M1_E`** — `P(|β_E,perm| ≥ |β_E,obs|)` under row-wise sign
  flip of the DV, refitting M1.
- **`perm_p_M3_int`** — `P(|β_int,perm| ≥ |β_int,obs|)` under the same
  sign-flip, refitting M3.

Required parameters:

- Minimum **2000** permutation reps (PERM_REPS).
- RNG seed disclosed in the preregistration.
- Sign-flip applied row-wise to the DV; alt and covariates left intact
  (paired permutation; not full label exchange).
- Refits use the same model formulas and the same covariance estimator
  (default: HC3) as the observed fits.

The reference implementation is the `paired_permutation` function in
`_scratch/run_up_m123_analysis.py` (v52.2). Any other implementation
MUST match its semantics; deviations require a documented amendment to
this contract.

When the DV variance is zero in the analysis sample, permutation is
skipped and the row is reported as exploratory only — Pattern 3 / 5
cannot be claimed inferentially in that case.

---

## 4. Pattern 3 / 5 inferential discipline

The pattern classifier (codes 0/1/2/3/4/5/6/9, defined in
`run_up_m123_analysis.py::classify`) is computed from analytic
p-values and HC3 standard errors. Pattern 3 ("regime-dependent
magnitude — alternator modulates E/r slope") and Pattern 5
("regime-flipping slopes — canonical E/r is misspecified; trust M3")
are the two interaction-driven classifications.

For an **inferential** claim that a DV exhibits regime-dependent UP
under an alternator A:

- The analytic classifier MUST return Pattern 3 or Pattern 5 on the
  observed fit, AND
- The corresponding paired sign-flip permutation MUST yield
  `perm_p_M3_int < α` (default α = 0.05; α MUST be preregistered).

Pattern 3 / 5 with `perm_p_M3_int ≥ α` is reported as
**suggestive, not inferential**. Such a result MUST be labelled
"ANALYTIC-ONLY — perm_p_M3_int = X.XXX cannot reject H0" in any
reporting and MUST NOT support an inferential statement about
regime-dependent UP.

This rule applies symmetrically to inferential claims based on M1's
`beta_E`: Pattern 1 ("single-slope UP") is inferential only when both
the analytic `p_E` and the permutation `perm_p_M1_E` clear α.

---

## 5. Reporting structure

Every M1/M2/M3 report governed by this contract MUST contain, in this
order:

1. **Sample size** N and per-alt-regime sample sizes.
2. **Alternators used**, with each labelled as inferential
   (E/r-independent) or exploratory (E/r-gated). A's correlation with
   E/r MUST be reported for any continuous A. Categorical A's partition
   MUST be specified.
3. **Per (DV, alt) pair**:
   - M1, M2, M3 coefficients with HC3 standard errors.
   - Analytic p-values for `β_E` (M1 and M3) and `β_int` (M3).
   - Paired sign-flip permutation p-values: `perm_p_M1_E`,
     `perm_p_M3_int`, with `perm_reps`.
   - Pattern id and analytic interpretation.
   - **Perm-aware verdict** per § 4.
4. **Comparison block** when both inferential and exploratory alts are
   present, showing how patterns and permutation p-values shift between
   them. This block is the basis for any claim that a gated-alt result
   was a confound.
5. **Inferential summary**: enumerate every DV/alt cell that meets § 4
   inferential bar; everything else is reported as suggestive only.

---

## Compliance checklist

A run is contract-compliant iff all of the following are true:

- [ ] At least one alternator A in the run satisfies `A ⫫ (E/r)` per § 2.
- [ ] Every (DV, alt) cell in the inferential block is fit on an
      E/r-independent A.
- [ ] Paired sign-flip permutation per § 3 was run for every cell, with
      ≥ 2000 reps and a disclosed RNG seed.
- [ ] Every Pattern 3 / 5 inferential claim is paired with a
      permutation-supported `perm_p_M3_int < α`.
- [ ] Every reported result without permutation support is labelled
      "suggestive" or "ANALYTIC-ONLY".
- [ ] If E/r-gated alts also appear, they are labelled exploratory and
      reported alongside, not in place of, the inferential alt.

A run that fails any item above is **not** an inferential run under
this contract; its findings are exploratory regardless of analytic
significance.

---

## Versioning

This contract is **v1.0.0**.

Future amendments require:

- explicit version bump (v1.x.0 for additive rules; v2.0.0 for any
  loosening),
- a new file at `analysis/physics/alternator/UP_M123_CONTRACT_vX.Y.Z.md`,
- an "Amendment" block in the new file referencing this one and stating
  what changed and why.

This file is not modified after publication. v1.0.0 stands as written.
