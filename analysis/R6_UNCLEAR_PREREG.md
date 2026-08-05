# R6 — Eight-enum `| unclear` · Pre-registration v1.0

**Status:** LOCKED PRE-EDIT. Written before any mutation to
`intelligence_kernel.py`. The prediction below is fixed and may not be
revised after the post-edit probe returns.

**Date locked:** 2026-08-04
**Pin at lock (pre-edit):** `ae221b68ddc9`
**Target:** `_EMOTIONAL_PHYSICS_PROMPT`, [intelligence_kernel.py:1554](../intelligence_kernel.py#L1554)
**Change:** append `| unclear` to the eight enum strings that carry no null
member. Eight single-token appends inside one string literal. No new types,
no orchestrator, no schema.

---

## 1. Substrate state at lock

Twelve enums in the contract. Four already carry a null member; eight do not.
The two sets are **disjoint** — this corrects the 06:28 enforcement inventory
line "4 of 8 forced enums carry `unclear`", which implied 4 ⊂ 8. A forced
enum carrying `unclear` is a contradiction in terms.

| Already compliant (4) | Members |
|---|---|
| `field_curvature.gradient_direction` | inward \| outward \| mixed \| **unclear** |
| `edge_pressure.signal_clarity` | clear \| mixed \| **unclear** |
| `relational_primitives.trust` | low \| medium \| high \| fluctuating \| **unclear** |
| `relational_primitives.alignment` | aligned \| partially_aligned \| misaligned \| **unclear** |

| Edit target (8) | Line | Members at lock |
|---|---|---|
| `field_curvature.intensity` | 1565 | low \| medium \| high |
| `field_curvature.stability` | 1567 | stable \| unstable \| oscillating |
| `edge_pressure.signal_intensity` | 1579 | low \| medium \| high |
| `edge_pressure.coherence` | 1580 | coherent \| fragmented \| contradictory |
| `edge_pressure.risk_of_misread` | 1585 | low \| medium \| high |
| `relational_primitives.boundary` | 1593 | clear \| soft \| collapsed \| rigid \| contested |
| `relational_primitives.agency` | 1594 | full \| partial \| constrained \| outsourced |
| `relational_primitives.distance` | 1595 | close \| moderate \| distant \| increasing \| decreasing |

## 2. Prior — why the expected effect is low

The four compliant enums are a natural control group: on them the null was
**already available** and the model **declined it** on a genuinely uncertain
input (the repo question).

| Field | Null available | Returned | Used null |
|---|---|---|---|
| `trust` | yes | `medium` | no |
| `alignment` | yes | `misaligned` | no |
| `signal_clarity` | yes | `mixed` | no |
| `gradient_direction` | yes | `inward` | no |

**4 of 4 declined the offered exit.** Corroborating: the prompt already
carries an explicit `do not force-fit` guard on the list fields, and that
guard was also ignored.

The mechanism under test is therefore *not* "the schema forbids abstention."
It is "the model does not abstain when permitted."

## 3. Prediction — LOCKED

> **UNCHANGED.** The post-edit probe will still return non-null values on
> `intensity` and `stability`. Specifically: `intensity: high`,
> `stability: unstable`, as before.

Registered by pen; ET-1.W concurs on the substrate grounds in §2.

## 4. Probe

Re-run the **eleven-word wiring-map request**, verbatim and unmodified, at
the post-edit pin. Single run, no reroll, no prompt tuning.

- Pre-edit return of record: `intensity: high`, `stability: unstable`
- Probe text is operator-held. Paste verbatim below before running so the
  lock is complete:

```
PROBE (verbatim, fill before running):
```

## 5. Decision rule

| Outcome | Reading | Disposition |
|---|---|---|
| Returns `unclear` on `intensity` and/or `stability` | The enum was the binding constraint | **R6 works.** Cheapest fix on the board; promote it. |
| Still returns `high` / `unstable` | Forced choice was not the mechanism | **R6 closed as cosmetic.** Invention originates outside schema control; the search moves off the contract surface. |

Partial result (one field flips, one does not) is reported as-is and does
**not** license a rerun to break the tie.

## 6. What this edit does not fix — stated at lock, not after

- `intensity`, `signal_intensity`, `risk_of_misread` are magnitude fields.
  `unclear` supplies an abstention path but **no `baseline_ref`**. The
  untethered-magnitude gap survives the edit.
- `intensity`, `stability` are `subject=person` → cold-illegal. `unclear`
  mitigates the forced-choice half only; the **return-loop gate is still
  absent**.
- Validation at the enforcement point remains key-presence only
  (`intelligence_kernel.py:1757-1766`). Adding a member to the contract text
  does not add a check; nothing rejects an out-of-enum value either way.

None of the above is in R6 scope. Recorded so a green probe is not mistaken
for closure.

## 7. Verification surface

Deliberately minimal. Eight string appends warrant a count, not an
attestation format:

```bash
python analysis/prompt_interrogator.py --json
```

Expect **12 of 12** enums carrying a null member and **zero** FORCED-CHOICE
edges. That is the whole check.
