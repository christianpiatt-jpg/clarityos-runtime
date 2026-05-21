# UP Proof Pipeline — v1.2.0

A staged proof pipeline for Universal Physics analysis. Every UP claim
must walk this pipeline. The alternator-first rule from
`PHYSICS_UP_SPEC_v1.1.0.md` § 3 is enforced **structurally**: Stage 0
runs before everything else, and its result determines which inferential
model is valid downstream.

---

## Stage 0 — Alternator Diagnostics

**Run before any inference on E/r.** No exceptions.

Four diagnostics:

1. **Interaction test (A × E/r)**
   Test whether the slope of Δcurvature on E/r differs across regimes
   (or with A as a moderator). A significant interaction is direct
   evidence of regime-dependent slope structure.

2. **Threshold / change-point test**
   Test whether the relationship has a discontinuity at some E/r
   threshold θ. A significant change-point indicates that A is
   thresholded on E/r — the regime depends on E/r itself.

3. **Mixture / HMM regime test**
   Fit a latent-state model (Gaussian mixture or hidden Markov model)
   and test for multi-regime structure against the single-regime null.
   A significant test indicates latent regime structure even when no
   observed alternator is available.

4. **Residual multimodality test**
   Examine the residuals from canonical UP (M1). Multiple modes in the
   residual distribution are a sign of unmodeled regime structure that
   M1 cannot capture.

**Output:** alternator diagnosis label —
`absent` / `threshold-plausible` / `present-binary` / `present-latent`.

---

## Stage 1 — Model Selection Rule

| Stage 0 result | Selected model |
|---|---|
| Alternator absent (independence holds) | **Canonical UP (M1)** — valid for inference |
| Alternator threshold-plausible | **Augmented UP only** (M3) |
| Alternator present (binary or latent) | **Augmented UP only** (M3) |

The selection rule is **binding**. If Stage 0 detects any alternator
structure, canonical UP is descriptive only — its inferential output
must NOT be reported as the primary result. Only the model selected at
Stage 1 may serve as the primary inferential result.

---

## Stage 2 — Inference

Three models are always fit. Stage 1 determines which is **primary**;
the others are diagnostic / robustness.

### M1 — Canonical UP

```
Δcurvature ~ (E/r) + controls
```

The single-slope global model. Valid for inference only when the
alternator is absent.

### M2 — Additive alternator

```
Δcurvature ~ (E/r) + A + controls
```

Regime intercept shift but a shared slope. Diagnostic; rarely the
primary model.

### M3 — Slope-switch / interaction

```
Δcurvature ~ (E/r) + A + A·(E/r) + controls
```

Regime-specific slopes. The primary model whenever any alternator
structure is detected at Stage 0.

**All three models are always fit and reported.** What changes across
analyses is which is *primary* per Stage 1.

---

## Stage 3 — Reporting

Three reporting rules:

1. **Always report canonical (M1)** — for intuition and comparison
   with prior literature that assumed a single regime.

2. **When alternator detected, report M3 as the primary inferential
   result.** M3's E/r slope and A·(E/r) interaction are the
   inferential claims.

3. **When M1 and M3 disagree, trust M3.** M1's apparent relationship
   reflects regime mixing — a population-weighted average of two
   regime-specific relationships, which is neither. M3 isolates the
   within-regime relationship plus the regime difference.

A report that presents only M1 when Stage 0 detected alternator
structure is a Stage 3 violation. The pipeline rejects it. Reviewers
should reject any UP analysis that bypasses Stage 0 or substitutes M1
for M3 in the presence of detected alternator structure.

---

## Pipeline-flow summary

```
Stage 0 (diagnostics)
  ├─ alternator absent?  → Stage 1 selects M1 (canonical) as primary
  ├─ threshold-plausible? → Stage 1 selects M3 (augmented) as primary
  ├─ present-binary?      → Stage 1 selects M3 as primary
  └─ present-latent?      → Stage 1 selects M3 as primary

Stage 2: fit M1, M2, M3 (always all three)

Stage 3 reporting:
  - Always: report M1 for intuition
  - If primary = M3: report M3 as the inferential result
  - If M1 and M3 disagree: trust M3
```

---

## Versioning

This pipeline is **v1.2.0**. Changes from v1.1.0:

- Stage 0 expanded to include the four named alternator diagnostics
  (interaction / threshold / HMM / residual multimodality).
- Stage 1 model-selection rule made explicit and binding.
- Stage 2 always fits all three models (M1 / M2 / M3).
- Stage 3 reporting rule formalized: always report canonical,
  primary-on-augmented-when-detected, trust M3 over M1 on disagreement.
