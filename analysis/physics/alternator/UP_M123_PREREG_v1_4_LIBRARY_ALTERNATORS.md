# UP M1/M2/M3 — Pre-registration v1.4: Library Alternators

**Status:** preregistered (no inferential commitments). Names a class
of E/r-independent **domain-indicator** alternators (`alt_library_<X>`)
that the v1.0/v1.1 contracts already permit under § 2 ("region
indicator, domain indicator, or any graph-extrinsic categorical/binary
variable"). v1.4 makes the use of these alternators explicit and
documents which corpus they apply to.

**Contract version anchor:** v1.0.0 § 1–9 + v1.1.0 § 6–9 (this prereg
inherits both; no contract is modified).

**Registered:** 2026-05-08
**Prereg ID:** `library_alternators_v1_4`
**Applies to corpus:** `local_libraries_v1_2` (and any future corpus
where region metadata is absent and library/subsystem labels are the
natural partition).

---

## 0. Discipline Lock

The following must NOT be modified by any task operating under this
prereg:

```
analysis/physics/alternator/UP_M123_CONTRACT_v1.0.0.md
analysis/physics/alternator/UP_M123_CONTRACT_v1.1.0.md
analysis/physics/alternator/UP_M123_PREREG_v1_2_LOCAL_LIBRARIES.md
analysis/physics/alternator/UP_M123_PREREG_v1_3_LAWBRIDG_PDF_CONVERSION.md
_scratch/up_m123_summary_v52_2*.csv
_scratch/up_m123_summary_v52_2*.json
_scratch/run_up_m123_analysis.py
_scratch/run_up_m123_region_alt.py
_scratch/ingest_local_libraries.py
_scratch/pdf_to_text.py
analysis/physics/up_kernel_spec.md
analysis/schema/up_kernel_schema.json
ELINS/*.py
```

All work additive.

---

## 1. Motivation

The v1.2 ingestion of the local libraries (run 2026-05-08T02:19:30Z)
produced 33 metric rows in which **every row carries `region_label =
"Unknown"`** because no source file supplied region/basin/label JSON
metadata. As a result, the existing `alt_region_*` alternators are
all-zero on this corpus and contribute no inferential power.

The v1.0 contract permits "region indicator, domain indicator, or any
graph-extrinsic categorical/binary variable" as an E/r-independent
alternator. **Library subsystem identity is a domain indicator** — it
is graph-extrinsic, partitions the corpus exhaustively, and (by
construction) does not covary with `E_over_r` magnitude.

v1.4 names this alternator class explicitly and registers its use on
the `local_libraries_v1_2` corpus.

## 2. Alternator definitions

For each row in the combined local-library corpus, derive three binary
alternators from the existing `library` column:

```
alt_library_elins      = 1[library == "elins"]
alt_library_lawbridg   = 1[library == "lawbridg"]
alt_library_narrative  = 1[library == "narrative"]
```

These are mutually exclusive (each row is in exactly one library) and
together exhaustive across the corpus. Each is treated as a separate
contrast (one-vs-rest), matching the existing `alt_region_<X>` pattern.

### 2.1 Independence verification

Per v1.0.0 § 2 / v1.1.0 § 6 clarifications, an alternator is treated as
E/r-independent when its construction does not derive from
`E_over_r`. The library label is assigned at ingestion time from
filesystem location and is not a function of any computed metric.
**Independence is structural, not subject to the |Pearson r(A, E/r)| <
0.20 numeric threshold.** The threshold check is reported as
informational diagnostic but does not gate inclusion.

### 2.2 Prevalence on the registered corpus

Pre-flight prevalence on `local_libraries_v1_2` (33 rows total):

| alternator | positive rows | negative rows |
|---|---|---|
| `alt_library_elins` | 13 | 20 |
| `alt_library_lawbridg` | 4 | 29 |
| `alt_library_narrative` | 16 | 17 |

`alt_library_lawbridg` has only 4 positive cases. Per v1.0/v1.1
modeling guidance, M3 standard errors on this alt are expected to be
unstable; cells involving this alt are reported but are flagged as
**low-prevalence** in the result table.

## 3. Models, permutation, DVs

Inherit v1.0.0 § 3–4 unchanged:

- M1: `DV ~ E_over_r`
- M2: `DV ~ alt`
- M3: `DV ~ E_over_r + alt + E_over_r:alt`
- HC3 standard errors, α = 0.05
- 2000 paired sign-flip permutations per cell, RNG seed 12345

DVs: the same five — `delta_pct_total_weak` (primary),
`delta_pct_total`, `delta_total_weight`, `delta_mean_edge`,
`delta_inv_weight`.

## 4. Acceptance criteria

Inherit v1.0 § 7 / v1.1 § 6 unchanged. The only substitution is that
the **set of E/r-independent alternators** is `alt_library_*` plus any
`alt_region_*` cells that turn out to have variance on the corpus.
Since v1.2 has none of the latter, the active independent set is
`{alt_library_elins, alt_library_lawbridg, alt_library_narrative}`.

For v1.1 quorum (§ 6):

- **(a)** Same DV `modulation_robust` under ≥ 2 library alts; OR
- **(b)** ≥ 2 distinct DVs `modulation_robust` under the same library
  alt.

## 5. Output artifacts

```
_scratch/run_up_m123_library_alt.py
_scratch/up_m123_summary_local_libraries_v1_4.csv
_scratch/up_m123_summary_local_libraries_v1_4_v1_1_tokens.json
_scratch/up_m123_v1_1_quorum_check_local_libraries.json
```

## 6. Sanity checks

- [ ] Result CSV exists with all five DVs × all alts populated.
- [ ] `alt_library_lawbridg` rows are flagged as `low_prevalence: true`
      in the v1.1 token side-car.
- [ ] Quorum side-car records `meets_v1_1_criterion` boolean and the
      enumerated robust cells (which may be empty).
- [ ] No edits to any frozen artifact.

---

## Anchors

- v1.0 contract: [UP_M123_CONTRACT_v1.0.0.md](UP_M123_CONTRACT_v1.0.0.md)
- v1.1 contract: [UP_M123_CONTRACT_v1.1.0.md](UP_M123_CONTRACT_v1.1.0.md)
- v1.2 prereg: [UP_M123_PREREG_v1_2_LOCAL_LIBRARIES.md](UP_M123_PREREG_v1_2_LOCAL_LIBRARIES.md)
- v1.3 prereg: [UP_M123_PREREG_v1_3_LAWBRIDG_PDF_CONVERSION.md](UP_M123_PREREG_v1_3_LAWBRIDG_PDF_CONVERSION.md)
- Corpus index: [UP_M123_CORPUS_INDEX.json](UP_M123_CORPUS_INDEX.json)
