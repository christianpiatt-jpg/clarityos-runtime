# UP M1/M2/M3 — Contract v2.0.0

**STATUS:** LOCKED. This contract governs all future runs that cite
`contract_version: "v2.0.0"`. Pre-v2.0 artifacts are preserved per §6
and are NOT silently re-evaluated.

**Type:** Major contract revision. Tightens the corpus-level quorum
mechanic in v1.1.0 §6 in response to the empirical edge case
documented in
[UP_M123_LOCAL_LIBRARIES_V1_4_REPORT.md](UP_M123_LOCAL_LIBRARIES_V1_4_REPORT.md),
in which v1.1 §6 passed literally on a corpus that failed every
robustness check a serious reader would impose.

**Inherits:** v1.0.0 §1–9 (kept verbatim) + v1.1.0 §6–9 (tightened).
**Supersedes:** v1.1.0 corpus-level acceptance language only. Per-cell
classifier and token taxonomy in v1.1.0 §7 are preserved (and
extended in §4 below).
**Backward compatibility:** prospective. Pre-v2.0 runs are not
re-tokenized or re-evaluated under v2.0 by automated tools (per v1.1.0
§8 carries forward).

**Date drafted:** 2026-05-08
**Date locked:** 2026-05-08
**Motivating artifact:** `local_libraries_v1_2` × `library_alternators_v1_4`

---

## §1. Why v2.0

The v1.4 run on the local-libraries corpus produced four
`modulation_robust` cells and triggered `meets_v1_1_criterion = true`,
yet *every* of the following independently undermines that pass:

| caveat | what it shows |
|---|---|
| C1 — primary DV not supported | `delta_pct_total_weak` failed M1 perm gate (0.362) under all active alts. Modulation claim has no UP foundation under it. |
| C2 — sign inconsistency | `delta_total_weight` β̂_int values were −262 / +261 / +247 across the three library alts. A single mechanism cannot produce both signs. |
| C3 — low-prevalence partition | `alt_library_lawbridg` has 4 positive rows; M3 SE under such prevalence is unreliable. 2 of 4 robust cells came from this partition. |
| C4 — perm_p clusters at α | All 4 robust cells had perm_p_M3_int between 0.0365 and 0.0420. None safely below e.g. 0.01. |
| C5 — Pattern-5 dynamics masked | `delta_total_weight × elins`: 74× shrinkage of β̂_E from M1 to M3. Pattern 5 conditions fired alongside Pattern 3; classifier rule order returned Pattern 3, and v1.1 token taxonomy collapsed both into modulation_robust. |
| C6 — alt fails numeric independence | Empirical \|corr(alt_library_lawbridg, E/r)\| = 0.52. v1.4 admitted this on structural grounds; v1.1 numeric threshold (\|corr\| < 0.20) was bypassed. The cell is functionally a gated-alt phenomenon under a structural label. |

v2.0 codifies six tightenings (§§3.A–3.F) so future corpus claims
require the structural integrity these caveats reveal is missing here.

---

## §2. Definitions (additive to v1.0/v1.1)

- **Primary DV** — `delta_pct_total_weak`, per v1.0 contract.
- **Robust cell** — a `(DV, alternator)` cell with v1.1 §7 token
  `modulation_robust`. Unchanged from v1.1.
- **Quorum-eligible cell** (NEW) — a robust cell that additionally
  satisfies all eligibility filters in §3.C through §3.F. Only
  quorum-eligible cells contribute to the corpus-level claim.
- **Active alternator set** — alts where the alt column has nonzero
  variance on the corpus. Region/library/domain alts that are
  all-zero (e.g., `alt_region_MEA` on the Outlook corpus) are
  excluded from the active set.
- **MIN_PREVALENCE** — minimum positive count for an alt to be
  quorum-eligible. Default: `max(8, ceil(0.10 * N))`.
- **SAFE_PREVALENCE** — threshold above which the standard perm_p
  threshold applies. Default: `max(15, ceil(0.20 * N))`.
- **Pattern-5 indicator** (NEW) — a cell where any of the following
  hold:
  - `|β̂_E(M3)| < 0.5 · |β̂_E(M1)|` AND both are sign-defined
  - `sign(β̂_E(M3)) ≠ sign(β̂_E(M1))` AND both are sign-defined
  - M3 standard error on β̂_E is more than 5× the M1 SE on β̂_E

---

## §3. Tightenings to v1.1 §6 corpus quorum

### §3.A — Primary DV participation required

A corpus supports global regime-dependent UP modulation only if at
least one **quorum-eligible** cell has DV equal to the primary DV
(`delta_pct_total_weak`).

**Rationale:** the v1.4 case showed a quorum pass entirely on
secondary scale-sensitive DVs (`delta_total_weight`, `delta_inv_weight`),
while the primary DV failed M1's permutation gate at 0.362. Modulation
of a curvature law one cannot detect in M1 is not a meaningful claim.

### §3.B — Sign consistency across robust cells contributing to (a)

Criterion (a) (same DV under ≥ 2 independent alts) requires the
contributing cells' β̂_int signs to agree:

- All cells must have `sign(β̂_int) > 0`, OR
- All cells must have `sign(β̂_int) < 0`.

Mixed-sign quorum contributions are reported as **suggestive but
not conclusive** and do not satisfy criterion (a).

**Rationale:** in the v1.4 case, three robust cells on
`delta_total_weight` had β̂_int values of −262, +261, +247. A unified
physical mechanism cannot produce opposite-direction modulation under
disjoint partitions of the same corpus — those signs reflect
partition labelling, not law-level structure.

### §3.C — Low-prevalence exclusion

A robust cell is quorum-ineligible if the alt's positive-row count is
below MIN_PREVALENCE.

**Default MIN_PREVALENCE:** `max(8, ceil(0.10 · N))`. For N = 33 this
is 8. The v1.4 case's `alt_library_lawbridg` (4 rows) would be
excluded.

Operators may register a corpus-specific override in the prereg.

**Rationale:** OLS standard errors on a binary alt with very few
positive cases are unreliable; perm_p is consequently noisy. Excluding
sub-MIN_PREVALENCE cells removes the most fragile modulation claims.

### §3.D — Stricter perm_p threshold for prevalence between MIN and SAFE

For cells where the alt's positive-row count is in
`[MIN_PREVALENCE, SAFE_PREVALENCE)`, the v1.1 §7 threshold for
`modulation_robust` is tightened from `perm_p_M3_int < 0.05` to
`perm_p_M3_int < 0.01`.

Cells in `[SAFE_PREVALENCE, ∞)` retain the v1.1 standard threshold
(0.05).

**Rationale:** small-but-not-tiny partitions still inflate the
parametric vs. permutation gap; the calibration shows perm_p clusters
at the parametric threshold for these cases. A stricter empirical
threshold protects against α-boundary clustering.

### §3.E — Pattern-5 exclusion from `modulation_robust`

A cell that meets the §2 Pattern-5 indicator is tokenized as
**`canonical_misspecified`** (NEW token) regardless of its perm_p
value, and is excluded from `modulation_robust`.

The classifier ordering rule is amended: Pattern 5's check fires
**before** Pattern 3's. A cell only becomes `modulation_robust` when
it passes Pattern 3 *and* fails Pattern 5.

**Rationale:** the v1.4 case had `delta_total_weight × elins` with M3
β̂_E 74× smaller than M1 β̂_E — textbook canonical-misspecification.
The v1.1 token taxonomy collapsed Pattern 3 and Pattern 5 (when
perm-significant) into one bucket, masking the misspecification
flavour. v2.0 surfaces it.

### §3.F — Numeric independence required for quorum contribution

Even if an alternator is structurally independent of E/r (region,
library, domain), the cell's alt column must satisfy
`|Pearson r(alt, E/r)| < 0.20` on the analysed dataset to contribute
to quorum. Cells failing this check are tokenized as
**`structurally_independent_numerically_correlated`** (NEW token) and
reported as suggestive but not robust.

**Rationale:** the v1.4 case's `alt_library_lawbridg` had |corr| =
0.52 — larger than the gated alts on the synthetic corpus that
generated documented phantom modulation. Structural admissibility is
necessary but not sufficient; the empirical decorrelation must also
hold for quorum credit.

---

## §4. Updated v1.1 §7 token taxonomy

Two new tokens are added; existing tokens retain their conditions:

| Token | Condition |
|---|---|
| `canonical_up_supported` | `pattern_id == 1` |
| `additive_alt`           | `pattern_id == 2` |
| `modulation_robust`      | `pattern_id ∈ {3, 5}` AND `perm_p_M3_int < α'` AND alt is independent (structurally and numerically per §3.F) AND prevalence ≥ MIN_PREVALENCE AND **not** Pattern-5-indicator. α' = 0.01 if prevalence < SAFE_PREVALENCE else 0.05. |
| `modulation_suggestive`  | `pattern_id ∈ {3, 5}` AND alt independent AND fails the `modulation_robust` strictness checks but `perm_p_M3_int < 0.05` |
| **`canonical_misspecified`** (NEW) | Pattern-5 indicator fires (large M3 shrinkage / sign flip / SE blow-up) |
| **`structurally_independent_numerically_correlated`** (NEW) | structural admit + \|corr(alt, E/r)\| ≥ 0.20 |
| `gated_only_artifact`    | `pattern_id ∈ {3, 5}` AND alt is gated |
| `ambiguous`              | `pattern_id == 9` |
| `pattern_<id>` fallback  | patterns 0/4/6 |

Quorum operates only on `modulation_robust` cells.

---

## §5. Compliance checklist (extends v1.1 §9)

A run is v2.0-compliant iff:

- [ ] v1.0 §5 compliance items pass.
- [ ] v1.1 §9 compliance items pass (canonical-token taxonomy is
      emitted).
- [ ] Per-cell tokens use the v2.0 augmented taxonomy in §4.
- [ ] Quorum check explicitly evaluates §3.A–§3.F and reports each
      gate's pass/fail boolean.
- [ ] Any global modulation claim is supported by quorum-eligible
      cells per §2 (not merely v1.1 robust cells).
- [ ] Localized findings (single robust cell, or quorum failing
      §3.A–§3.F) are reported with named caveats.

---

## §6. Backward compatibility

This contract applies prospectively. Pre-v2.0 artifacts (CSVs, JSONs,
reports, prereg files) MUST NOT be silently re-tokenized or
re-evaluated. The `local_libraries_v1_2` archived artifact is
preserved as written under v1.1; if re-evaluated under v2.0 the result
must live in a side-car file (e.g.,
`*_v2_0_quorum_check.json`).

---

## §7. Anchors

- v1.0 contract: [UP_M123_CONTRACT_v1.0.0.md](UP_M123_CONTRACT_v1.0.0.md)
- v1.1 contract: [UP_M123_CONTRACT_v1.1.0.md](UP_M123_CONTRACT_v1.1.0.md)
- Local-libraries corpus report (motivating artifact): [UP_M123_LOCAL_LIBRARIES_V1_4_REPORT.md](UP_M123_LOCAL_LIBRARIES_V1_4_REPORT.md)
- v1.4 prereg: [UP_M123_PREREG_v1_4_LIBRARY_ALTERNATORS.md](UP_M123_PREREG_v1_4_LIBRARY_ALTERNATORS.md)
- Corpus index: [UP_M123_CORPUS_INDEX.json](UP_M123_CORPUS_INDEX.json)

---

## §8. Open questions (for operator decision before lock)

1. **MIN_PREVALENCE / SAFE_PREVALENCE defaults.** Proposed
   `max(8, 0.10·N)` and `max(15, 0.20·N)`. Operator may adjust before
   lock; downstream runners read these as constants.
2. **§3.D threshold value (0.01).** Could be 0.005 or 0.025. 0.01 is a
   middle path consistent with conventional secondary-correction
   practice.
3. **§3.E SE blow-up multiplier (5×).** Could be 3× or 10×. 5× is a
   defensible default for catching the v1.4 elins case.
4. **Structural-vs-numerical hierarchy.** §3.F currently requires
   *both*. Alternative: structural admits to suggestive,
   numerical-only admits to nothing. Current draft is stricter.
5. **Re-evaluation policy.** §6 forbids silent re-tokenization. Should
   v2.0 ship with a `tools/v2_0_reevaluator.py` side-car generator
   that operators can opt into? Out of scope for this contract; would
   be a follow-on.

---

## §9. Versioning

- v2.0.0 (LOCKED 2026-05-08) — this file
- DV definitions: unchanged from v52.2 / v1.0
- Token taxonomy: extends v1.1 §7 with two new tokens
  (`canonical_misspecified`, `structurally_independent_numerically_correlated`)
- Quorum logic: tightened from v1.1 §6 via §3.A–§3.F

Lock timestamp is recorded in
[UP_M123_CORPUS_INDEX.json](UP_M123_CORPUS_INDEX.json) under entry
`contract_v2_0_0_lock`. Future runs cite `contract_version:
"v2.0.0"`.
