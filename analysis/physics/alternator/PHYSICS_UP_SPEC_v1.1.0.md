# Universal Physics (UP) — Specification v1.1.0

This document specifies Universal Physics (UP) as a **regime law** rather
than a single global relationship, and formalizes the role of the
**alternator operator A** that selects regimes. It establishes the
alternator-first epistemic rule, defines the validity conditions for
canonical vs augmented UP, and sets sample-size thresholds for
inferential claims.

This spec is the foundational reference for the analysis tools and
preregistered analysis plan that live alongside it in
`analysis/physics/alternator/`.

---

## 1. UP as a Regime Law

UP describes the relationship between curvature change and the
energy-to-radius ratio (E/r) **within a fixed regime A**. The core
relation is:

> **Δcurvature ∝ (E/r)** — within regime A.

Regime A may take three forms:

- **Binary** — A is one of two discrete labels.
- **Thresholded** — A is a function of E/r, switching at some threshold.
- **Latent** — A is unobserved and must be inferred from data
  (e.g., via a hidden Markov model or finite mixture model).

**Canonical UP** is the special case where **A = +1** uniformly — a
single regime with no alternator action. In this special case the
relation collapses to the familiar global form. **Outside this special
case, UP holds piecewise across regimes** and the alternator A
determines which regime applies to any given observation.

---

## 2. The Alternator Operator A

A is the regime selector — the structural variable that determines which
regime any observation belongs to. Three canonical forms:

| Form | Definition | When it applies |
|---|---|---|
| **Binary** | A ∈ {+1, −1} | Two clear regimes; categorical observation. |
| **Thresholded** | A = 1[E/r > θ] for some threshold θ | The regime depends on E/r itself; mediator / moderator pattern. |
| **Latent** | A inferred from data via mixture or HMM | The regime is unobserved; recovered statistically. |

The alternator is the **essential** structural variable. Treating it as
absent when present is a specification error: it produces a single-slope
estimate that is a population-weighted average of two distinct
regime-specific relationships, which is neither of them.

---

## 3. Epistemic Rule (mandatory)

> **Alternator diagnostics MUST precede any inference on E/r.**

This is non-negotiable. Before any conclusion can be drawn about the
relationship between Δcurvature and E/r, the analyst MUST:

1. Test for alternator presence.
2. Determine alternator form (binary / thresholded / latent).
3. Confirm or reject alternator independence from E/r.

If the alternator is **thresholded** or **latent**, **canonical UP is
descriptive only** — not inferential. Stage 0 of the proof pipeline
exists to make this rule operational; it cannot be skipped, deferred,
or treated as a robustness check.

---

## 4. Validity Conditions

| Condition | Canonical UP | Augmented UP |
|---|---|---|
| A ⫫ (E/r) (alternator independent of E/r) | **Valid for inference** | Optional |
| A = f(E/r) (alternator depends on E/r) | NOT valid | **Required** |
| Regime structure detected (any form) | NOT valid | **Required** |

**Canonical UP is valid for inference if and only if the alternator is
independent of E/r.** If the alternator is dependent on E/r (or any
regime structure is detected), the augmented model — which includes A
and the A·(E/r) interaction term — is required. The augmented model is
the only model whose coefficients identify within-regime relationships
when regime structure is present.

---

## 5. Sample Size Rule

| N | Status |
|---|---|
| **N ≈ 30** | Exploratory only — no inferential claims permitted. |
| **N ≥ 100** | First inferential regime — canonical UP testable. |
| **N ≥ 200** | Stable detection of both E/r and A — augmented UP testable. |

Inferential claims (p-values, decision-grade confidence intervals)
require **N ≥ 100**. Augmented UP claims — those that rely on
estimating both the E/r main effect and the A or A·(E/r) effect — require
**N ≥ 200**. Below these thresholds, results are reported as exploratory.

---

## 6. What this spec does and does not do

**This spec does:**

- Define UP as a regime law.
- Identify the alternator A as the regime selector.
- Make alternator diagnostics mandatory before any E/r inference.
- Formalize when canonical UP suffices and when augmented UP is required.
- Set sample-size thresholds for exploratory vs. inferential claims.

**This spec does not:**

- Specify the empirical method for alternator detection (that is the
  pipeline's job — see `PROOF_PIPELINE.md`).
- Specify the preregistered analysis plan (see
  `UP_PREREGISTERED_ANALYSIS.md`).
- Specify the implementation of the diagnostic tools (see
  `diagnostic_up_alternator.py` and `templates_up_alternator.py`).

---

## Versioning

This spec is **v1.1.0**. Changes from v1.0.0:

- Added the regime-law framing (UP as conditional on A).
- Added the three alternator forms (binary, thresholded, latent).
- Made the alternator-first epistemic rule mandatory.
- Defined canonical vs augmented validity conditions.
- Specified sample-size thresholds (N≈30 exploratory / N≥100 / N≥200).
