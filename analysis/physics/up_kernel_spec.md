# UP^ Kernel Specification — v1.0.0

This document defines **UP^** (read: "UP-hat") — the **operator form** of
Universal Physics. UP^ is the kernel that consumes region-level graph
states and produces the dependent variables (DVs) on which UP regime
inference is performed.

This spec is **center-only**:

- It defines **what UP^ is**, not how it is computed, displayed, or
  reported.
- It contains **no code, no imports, no runtime references**.
- It is **additive** — it does not modify any existing file.

UP^ sits inside the same module as the alternator-form regime law
(`analysis/physics/alternator/PHYSICS_UP_SPEC_v1.1.0.md`) and the
preregistered analysis plan (`UP_PREREGISTERED_ANALYSIS.md`). Those
documents specify when UP holds and how it is tested. **This document
specifies the DVs UP holds about.**

---

## 1. The UP^ law (canonical statement)

> **UP^ characterizes how orientation and regime jointly modulate
> scale-sensitive curvature DVs in edge-weighted regional graphs.**

The **primary readout** of UP^ is `delta_pct_total_weak`. Other DVs are
preregistered companions used to triangulate the primary signal.

---

## 2. The UP^ operator

UP^ is a deterministic mapping:

```
UP^ : (G_pre, G_post, A) ──▶ DV-vector
```

**Input:**

- `G_pre = (V, E, w_pre)` — a region's edge-weighted graph at the
  pre-state, with vertex set V, edge set E, and edge-weight function
  `w_pre : E → ℝ_{≥0}`.
- `G_post = (V, E, w_post)` — the same vertex and edge sets at the
  post-state, with edge-weight function `w_post : E → ℝ_{≥0}`.
- `A` — orientation / regime label(s) attached to the region. The
  alternator form A (binary / thresholded / latent) is defined in
  `PHYSICS_UP_SPEC_v1.1.0.md` § 2 and is **not redefined here**.

**Assumption (center spec):** the vertex set V and edge set E are
identical between `G_pre` and `G_post`. Dynamic edge sets are out of
scope for the center definition; they will be reconciled in a later
ring against existing region-metric outputs.

**Output:** an ordered vector of DVs

```
UP^(G_pre, G_post, A) = (
    delta_total_weight,
    delta_mean_edge,
    delta_pct_total,
    delta_inv_weight,
    delta_pct_total_weak       (primary)
)
```

UP^ is purely a **DV producer**. It does not perform regression, regime
selection, or inference. Those steps are governed by the alternator
spec and the preregistered analysis plan.

---

## 3. Notation

| Symbol | Meaning |
|---|---|
| `W_pre`  | `Σ_{e ∈ E} w_pre(e)`  — total pre-state weight  |
| `W_post` | `Σ_{e ∈ E} w_post(e)` — total post-state weight |
| `|E|`    | edge count (assumed equal pre/post; see § 2)    |
| `ε`      | preregistered small positive floor used in any denominator that could otherwise vanish |
| `τ_weak` | preregistered weak-edge threshold defined as a **quantile of `w_pre`** (e.g., the q-th quantile for some preregistered `q ∈ (0, 0.5]`) |
| `E_weak` | `{ e ∈ E : w_pre(e) ≤ τ_weak }` — the weak-edge subset, fixed by the pre-state |
| `W^weak_pre`, `W^weak_post` | total weight on `E_weak` at pre and post |

`τ_weak` is preregistered at the **module level**, not per analysis run,
so that the weak-edge subset is a stable, scale-equivariant feature of
the pre-state.

---

## 4. The five DVs

For each DV: **definition**, **invariance** (transformations that leave
it unchanged), **sensitivity** (transformations it responds to), and
**role in UP^** (which aspect of curvature / stress / scale it
encodes).

### 4.1 `delta_total_weight`

- **Definition:** `delta_total_weight = W_post − W_pre`.
- **Invariance:** invariant to vertex relabelings that preserve E.
  Invariant to permutations of edge labels.
- **Sensitivity:** scales linearly with a uniform edge-weight rescale
  (`w → α·w` ⇒ DV → α·DV). Sensitive to the **absolute** magnitude of
  bulk weight change. Saturates with the size of the region.
- **Role in UP^:** the **bulk-energy** DV — total stress accumulated or
  released across all channels. Used as the unnormalized reference
  against which the normalized DVs are read.

### 4.2 `delta_mean_edge`

- **Definition:** `delta_mean_edge = (W_post − W_pre) / |E|`.
- **Invariance:** invariant to vertex relabelings preserving E. Scale-
  equivariant (scales linearly with uniform weight rescale).
- **Sensitivity:** isolates the **per-edge average** weight change;
  insensitive to graph density (because density is divided out).
- **Role in UP^:** **density-normalized stress flow** — the per-channel
  curvature DV. Useful when comparing regions whose edge counts differ
  but whose per-channel dynamics should be commensurable.

### 4.3 `delta_pct_total`

- **Definition:** `delta_pct_total = (W_post − W_pre) / max(W_pre, ε)`.
- **Invariance:** **scale-invariant** — uniform rescale of all weights
  by α leaves this DV unchanged. Invariant to vertex relabelings
  preserving E.
- **Sensitivity:** responds to **relative** growth or contraction of
  total weight; dimensionless; well-behaved across regions of very
  different absolute sizes.
- **Role in UP^:** **scale-free curvature ratio** — the dimensionless
  bulk DV. The most directly cross-regional companion to the bulk DV in
  § 4.1.

### 4.4 `delta_inv_weight`

- **Definition:**
  `delta_inv_weight = Σ_{e ∈ E} 1/max(w_post(e), ε) − Σ_{e ∈ E} 1/max(w_pre(e), ε)`.
- **Invariance:** invariant to vertex relabelings preserving E.
- **Sensitivity:** **NOT** scale-invariant — under uniform rescale `w →
  α·w` the DV scales as `α^{-1}`. Strongly weighted toward **small**
  edges (because `1/w` blows up as `w → 0`), so it amplifies dynamics
  on weak channels.
- **Role in UP^:** **weak-channel stress detector** — captures fragility
  and near-zero-edge dynamics that the bulk DVs (§ 4.1, § 4.3) miss.

### 4.5 `delta_pct_total_weak` — **PRIMARY**

- **Definition:**
  `delta_pct_total_weak = (W^weak_post − W^weak_pre) / max(W^weak_pre, ε)`,
  where `E_weak` is fixed by the **pre-state** quantile threshold
  `τ_weak` (see § 3).
- **Invariance:** **scale-invariant** when `τ_weak` is a quantile of
  `w_pre` (uniform rescale leaves both `E_weak` and the ratio
  unchanged). Invariant to vertex relabelings preserving E.
- **Sensitivity:** combines the dimensionless property of `delta_pct_total`
  with the weak-channel selectivity of `delta_inv_weight`. Maximally
  responsive to **redistribution of stress within weak channels** — the
  regime in which alternator-driven dynamics are expected to be most
  visible.
- **Role in UP^:** **the canonical UP^ readout.** The DV whose
  regime-conditional behavior the alternator A is expected to govern
  most cleanly, and the DV against which M1 / M3 inference (per the
  preregistered plan) is primarily reported.

---

## 5. Primary DV designation

`delta_pct_total_weak` is the **primary** DV.

Rationale (recorded for the preregistration trail):

1. It is **scale-invariant**, so estimates and effect sizes are
   comparable across regions of different absolute size.
2. It is **weak-channel selective**, so it concentrates statistical
   power where alternator-driven regime structure is most expected to
   manifest.
3. It is **dimensionless**, which makes its coefficients in M1 / M3
   directly interpretable as fractional response to E/r.
4. It is **stable under uniform measurement rescaling** of the
   underlying graph, so calibration-driven shifts in `w` do not
   contaminate the DV.

The other four DVs are **preregistered companions**, not alternative
primaries. Reporting only the companions, or substituting one of them
for `delta_pct_total_weak` as the headline result, is a preregistration
violation under `UP_PREREGISTERED_ANALYSIS.md` § 3.

---

## 6. Relation to the alternator regime law

UP^ and the alternator law are **complementary**:

- **UP^** (this spec) produces the DVs.
- **The alternator law** (`PHYSICS_UP_SPEC_v1.1.0.md`) determines the
  regime structure under which those DVs are interpreted.
- **The preregistered plan** (`UP_PREREGISTERED_ANALYSIS.md`) governs
  how M1 / M2 / M3 are fit on each DV and how the alternator-first rule
  is enforced.

A UP^ output vector by itself is **not** an inferential claim. It
becomes inferential only after Stage 0 alternator diagnostics and Stage
1 model selection (per `UP_PREREGISTERED_ANALYSIS.md`).

---

## 7. Companion artifacts

- `analysis/schema/up_kernel_schema.json` — JSON schema for a single
  UP^ output record (one row per `(region, DV)` pair) including
  M1 / M3 coefficients, p-values, permutation p-values, and the
  pattern-code interpretation. The DV registry inside the schema
  records which DV is **primary**.
- `analysis/physics/alternator/PHYSICS_UP_SPEC_v1.1.0.md` — the
  regime-law spec (alternator form). **Not modified by this document.**
- `analysis/physics/alternator/UP_PREREGISTERED_ANALYSIS.md` — the
  preregistered M1 / M2 / M3 plan. **Not modified by this document.**

---

## Versioning

This spec is **v1.0.0** — the first center-form definition of UP^.

This is a center artifact. Subsequent rings will:

- connect existing region-metric outputs into the DV vector defined
  here,
- wire the JSON schema into the analysis schema layer,
- define how `pattern_code` is assigned per row,

— each as its own additive ring, leaving this document and the
alternator-form spec untouched.
