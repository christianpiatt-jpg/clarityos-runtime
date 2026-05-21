# UP Preregistered Analysis Plan — v1.1.0

This is the binding preregistration for any UP analysis run under this
module. Every analysis MUST follow this plan. Deviations require a
formal preregistration update **before** the analysis runs, not after
the data are seen.

This plan operates on top of:

- `PHYSICS_UP_SPEC_v1.1.0.md` — the regime-law specification.
- `PROOF_PIPELINE.md` (v1.2.0) — the staged pipeline (Stage 0 → 3).

---

## 1. Always fit M1 / M2 / M3

For every dataset, fit:

- **M1** (canonical UP): Δ ~ (E/r) + controls
- **M2** (additive alternator): Δ ~ (E/r) + A + controls
- **M3** (slope-switch / interaction): Δ ~ (E/r) + A + A·(E/r) + controls

All three are pre-registered. None are optional. **Reporting only M1 is
a preregistration violation.** Reporting only M3 (without M1 for
intuition) is also a violation; both must appear in the final report.

---

## 2. Alternator-first rule

Stage 0 alternator diagnostics MUST be run **and reported** BEFORE any
inferential statement on E/r. The four diagnostics are:

1. **Interaction test** (A × E/r)
2. **Threshold / change-point test**
3. **Mixture / HMM regime test**
4. **Residual multimodality test** on canonical M1 residuals

All four are pre-registered. **Skipping any of them is a preregistration
violation.** Adding additional diagnostics post-hoc is permitted only as
exploratory; they may not be reported as primary tests.

---

## 3. Primary inference from M3 (when alternator detected)

When alternator structure is detected at Stage 0:

- **M3 is the primary inferential model.**
- M3's E/r slope and A·(E/r) interaction are the primary inferential
  estimands.
- M1's slope is reported but **not used for primary inference**.
- If M1 and M3 disagree, the disagreement itself is reported, and **M3
  is trusted**.

When alternator structure is NOT detected at Stage 0:

- M1 may serve as the primary inferential model.
- M3 is still reported, as a robustness check that the no-alternator
  conclusion holds even when interaction terms are admitted.

---

## 4. Sample-size thresholds (preregistered cutoffs)

Per `PHYSICS_UP_SPEC_v1.1.0.md` § 5:

- **N ≈ 30** — exploratory only. **No inferential claims permitted.**
  P-values, confidence intervals treated as decision-grade, and
  hypothesis-test framing are NOT preregistered for N < 100. Any
  reporting must label findings "exploratory" and refrain from
  inferential language.
- **N ≥ 100** — canonical UP inferential regime. Inferential claims on
  M1 (when alternator absent) are preregistered.
- **N ≥ 200** — augmented UP (M3) stable detection regime. Inferential
  claims on M3's interaction term are preregistered.

If N falls below the threshold relevant to the model selected at Stage
1, the analysis is downgraded to exploratory and reported as such.

---

## 5. Power and FPR expectations (from simulation)

Each of the four Stage-0 diagnostics has a pre-simulated power profile
(under representative alternative regimes) and a pre-simulated false
positive rate (under the canonical-only null). Empirical results MUST
be reported alongside these reference profiles.

For each diagnostic, the report MUST include:

- The simulated **power at N=100** under a representative alternative.
- The simulated **power at N=200** under a representative alternative.
- The simulated **FPR** under the canonical-only null.
- The **observed test statistic** and the **simulated reference
  distribution** (or the analytic equivalent).

**Empirical results below simulated power thresholds are reported as
inconclusive, not as null findings.** This rule prevents underpowered
diagnostics from being mistaken for evidence of alternator absence.

---

## 6. Preregistered diagnostics — full list

The following are preregistered as **primary** Stage-0 tests (not
exploratory):

- Interaction test (A × E/r) — primary
- Threshold / change-point test — primary
- Mixture / HMM regime test — primary
- Residual multimodality test (on M1 residuals) — primary

Additional diagnostics may be run, but their results are **exploratory**
and must be labeled as such. Examples of exploratory diagnostics that
may be added (not preregistered): leverage analysis, bootstrap stability
of the threshold estimate, alternative HMM with different state counts,
permutation-based slope tests beyond the four primary diagnostics.

---

## 7. Reporting structure (preregistered)

Every UP report MUST contain, in this order:

1. Sample size N and per-regime sample sizes (if alternator observed).
2. Stage 0 results: the four primary diagnostics with their test
   statistics, simulated power/FPR references, and the alternator
   diagnosis label (absent / threshold-plausible / present-binary /
   present-latent).
3. Stage 1 model selection: which model is primary, by rule.
4. Stage 2 results: M1, M2, M3 coefficients with confidence intervals.
5. Stage 3 reporting: M1 for intuition; M3 (when primary) as the
   inferential claim; explicit treatment of any M1↔M3 disagreement.
6. Preregistration deviations: zero by default. Any deviation listed
   here as exploratory.

---

## Versioning

This preregistration is **v1.1.0**. Changes from v1.0.0:

- Added the alternator-first rule explicitly (§ 2).
- Added the canonical validity conditions (§ 3).
- Added the sample-size thresholds (§ 4: N≈30 / N≥100 / N≥200).
- Added the power/FPR-from-simulation reporting requirement (§ 5).
- Required the alternator diagnostics to be preregistered (not just
  encouraged) (§ 6).
- Specified the canonical reporting structure (§ 7).
