# UP^ M1/M2/M3 Alternator-Independence Contract — Amendment v1.1.0

**Amendment to v1.0.0 — Regime-Dependent Modulation Criterion (v1.1.0)**

This file is a v1.1 amendment to
[UP_M123_CONTRACT_v1.0.0.md](UP_M123_CONTRACT_v1.0.0.md).

**v1.0.0 remains the governing preregistration.** v1.1.0 adds a stricter
criterion for global regime-dependent UP modulation claims and pins the
canonical token taxonomy required for that criterion to be mechanically
evaluable. v1.0.0 is **not** modified by this amendment.

This amendment also does not modify:

- `analysis/physics/up_kernel_spec.md`
- `analysis/physics/alternator/PHYSICS_UP_SPEC_v1.1.0.md`
- `analysis/physics/alternator/UP_PREREGISTERED_ANALYSIS.md`
- `analysis/physics/alternator/PROOF_PIPELINE.md`

---

## § 6. Criterion for global regime-dependent modulation (new in v1.1)

§ 4 of v1.0.0 establishes the **per-cell** inferential bar: a
`(DV, alternator)` cell qualifies as `modulation_robust` only when the
analytic classifier returns Pattern 3 or Pattern 5 AND
`perm_p_M3_int < α`.

v1.1 tightens the **corpus-level** claim. A corpus supports global
regime-dependent UP modulation only if at least one of the following holds:

- **(a)** The same DV qualifies as `modulation_robust` under
  **two or more** E/r-independent region alternators; OR
- **(b)** **Two or more** distinct DVs qualify as `modulation_robust`
  under the same E/r-independent alternator.

A single isolated `(DV, alternator)` cell that meets `modulation_robust`
but satisfies **neither** (a) nor (b) is reported as a
**localized / exploratory** finding and **does NOT** count as evidence of
global regime-dependent modulation. Such cells MUST be flagged for
targeted follow-up and explicitly described in results.

### Clarifications

- **Independence of alternators**: defined by the alternator partitioning
  used in the analysis (e.g., US, EU, MEA, APAC, Markets, Tech). Two
  region alternators drawn from the same partition (`alt_region_X`,
  `alt_region_Y` for `X ≠ Y`) qualify as independent for the purposes of
  (a). Continuous-form alternators count as independent only when their
  `|Pearson r(A, E/r)|` is below the threshold preregistered in § 2 of
  v1.0.0.
- **Distinct DVs**: must be meaningfully different operationalizations
  (e.g., `delta_pct_total_weak` vs `delta_inv_weight`), NOT trivial
  rescalings of the same metric. Two DVs that differ only by a
  deterministic monotone transform of a third quantity do NOT count as
  distinct.
- **Localized findings**: documented as per-cell results with the exact
  token, the DV, the alternator, the analytic and permutation p-values,
  and an explicit "does not meet § 6" annotation.

---

## § 7. Canonical token taxonomy (new in v1.1)

To make § 6 mechanically evaluable, every per-cell verdict produced by a
run governed by this contract MUST be one of the following six canonical
tokens. Free-text verdicts are no longer permitted as the basis for
corpus-level decisions under v1.1.

| Token | Condition |
|---|---|
| `canonical_up_supported` | `pattern_id == 1` |
| `additive_alt`           | `pattern_id == 2` |
| `modulation_robust`      | `pattern_id ∈ {3, 5}` AND `perm_p_M3_int < α` AND alternator is E/r-independent |
| `modulation_suggestive`  | `pattern_id ∈ {3, 5}` AND `perm_p_M3_int ≥ α` AND alternator is E/r-independent |
| `gated_only_artifact`    | `pattern_id ∈ {3, 5}` AND alternator is E/r-gated |
| `ambiguous`              | `pattern_id == 9` |

Pattern IDs 0, 4, and 6 do not have a canonical token and are emitted as
`pattern_<id>` (e.g., `pattern_4`). Cells emitted under the `pattern_<id>`
fallback are exploratory only and do **NOT** contribute to the § 6 quorum
on either axis.

The corpus quorum check in § 6 operates **only** on cells where:

1. The alternator is E/r-independent (per § 2 of v1.0.0), AND
2. The token is `modulation_robust`.

Cells with token `modulation_suggestive`, `gated_only_artifact`, or any
`pattern_<id>` fallback do not contribute to the quorum count on either
axis.

---

## § 8. Backward compatibility

This amendment applies **prospectively**. Past runs (CSVs, JSONs, summary
tables written before v1.1.0) MUST NOT be silently re-tokenized or
reclassified by automated tools. They may be reprocessed manually under
v1.1 with explicit audit-trail labelling, but the original artefacts are
preserved as written.

A v1.1-compliant run produces tokens directly as part of its primary
output. A pre-v1.1 run that is re-evaluated under v1.1 must do so in a
side-car file (e.g., `*_v1_1_quorum_check.json`) leaving the original
output untouched.

---

## § 9. Compliance checklist (extends § 5 of v1.0.0)

A run is v1.1-compliant iff the v1.0.0 compliance checklist passes AND:

- [ ] Every per-cell verdict in inferential output is one of the six § 7
      canonical tokens, or a `pattern_<id>` fallback for unmapped
      patterns.
- [ ] The corpus-level quorum check is computed and reported alongside
      per-cell tokens, with both `robust_cells_by_alternator` and
      `robust_cells_by_dv` axes shown.
- [ ] Any global regime-dependent modulation claim is supported by
      `meets_v1_1_criterion == true`. Localized cells are explicitly
      marked.

---

## Anchors

- [analysis/physics/alternator/UP_M123_CONTRACT_v1.0.0.md](UP_M123_CONTRACT_v1.0.0.md)
  — governing preregistration; **not modified**.
- [analysis/physics/up_kernel_spec.md](../up_kernel_spec.md)
  — UP^ kernel spec.
- [_scratch/run_up_m123_analysis_region_alt.py](../../../_scratch/run_up_m123_analysis_region_alt.py)
  — first reference implementation that emits canonical tokens and runs
  the corpus quorum check.

---

## Versioning

This amendment is **v1.1.0**.

Future amendments require their own versioned files
(`UP_M123_CONTRACT_vX.Y.Z.md`) with an explicit `Amendment` block citing
this one and stating what changed and why. v1.0.0 remains the immutable
governing preregistration; this amendment file is itself immutable after
publication.
