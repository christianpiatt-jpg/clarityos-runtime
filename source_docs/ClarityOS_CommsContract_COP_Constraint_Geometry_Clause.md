# Communications Contract — COP Constraint-Geometry Clause
### Folding hallucination-resistance into continuous-COP discipline
*COW advisory draft for CT-1 · v0.3 · 2026-08-03 · to fold into the Communications Contract (v1.4+) · +primitive-geometry layer · +missing-middle close · **+v0.4 answer discipline 2026-08-04 (K3-folded, below)***

**Principle.** A *continuous* COP is a continuously *constrained* COP. Hallucination is not a
property of content — it is a **geometry**: the COP drifting into an *under-constrained region*
where fluent claims are no longer anchored to truth. The Communications Contract's job is to
keep the COP in a **high-constraint region** at all times, and — critically — to keep it there
**across agent refreshes**, since a flattened restore is the easiest way to lose the geometry
and hallucinate on wake.

This is the unifying lens under **R-1 (COP poisoning / hallucinated observations)**: R-1 is
what happens when the constraint geometry collapses.

## The four constraints the COP must hold

| Under-constraint (how hallucination enters) | Constraint the contract adds back | Enforced by |
|---|---|---|
| Too much **generation freedom** | bound action to ratified intent + decision_thresholds | RoE (CT-2); `constraints` field; initiative guard (D-init-guard) |
| Too little **evidence locality** | every observation carries source + provenance; un-sourced quarantined | SRP-2 / R-1; `COPObservation.provenance`; evidence tag |
| Too **coarse a verification boundary** | verify per-claim, not per-message; corroborate ≥2 independent sources | SRP-7; D-compiler-check |
| Too weak a **structural lock** | every claim binds to a specific substrate **locus** (repo + commit + locus), reverse-traceable | A131; FRAGO reverse-trace; D-anchor-freshness |
| Too weak **validation hardness** | validate against external structure (locus + symbolic check), not the model's priors/fluency; abstain when unsupported | reverse-trace; evidence tag; SRP-1 (abstain-over-fabricate); D-compiler-check |

The mapping shows the geometry is already ~90% enforced by existing primitives. Folding it in
*names the principle* and closes the two granularity gaps below.

## Two disciplines this surfaces (D-candidates)

- **D-claim-locality** — a COP element binds to a *specific locus* (`file:line` / commit), not
  merely "a source." A claim that cannot name where it is grounded does not enter the COP.
  Sharpens A131 from repo+commit down to locus; ties to D-anchor-freshness staleness.
- **D-claim-verification-boundary** — provenance and corroboration attach at the **claim**
  level inside the message envelope, not at the message level — so unsupported content cannot
  ride alongside supported content in one envelope. Message-structure rule; schema deferred.

## The missing-middle close (standard move on closing a return)

**Rule.** Every return closes with a **missing-middle reflection**. Before a return is
complete, its author registers the gap between the **verified near end** (claims bound to
a substrate locus, [Corr]-tagged) and the **far end the return actually asserted**. The
reflection has three moves, in order:

1. **Name the verified near end** — what this return established at locus (`file:line`,
   commit, runtime read), with the tag level per claim.
2. **Name every extension past it** — each hop where the return traveled beyond the
   verified, stated as an extension, at the confidence it earned. An extension carried
   silently under the near end's confidence is over-extension: it launders the unverified
   through the verified.
3. **Mark what has no traceable effect** — levers, claims, and connections asserted but
   not traced to an actual wiring change or substrate effect. Registered as NODE (asserted
   connection) against WIRE (verified connection), per instance, without argument about
   which should win.

**Failure this prevents.** The signature failure is the *verified-prefix carry*: a return
whose first half is locus-bound and whose second half rides the first half's credibility —
then gets quoted downstream as if all of it were verified. Worked instances at adoption:
COW-1's strip rule (files created vs. reality-touching acts; `acts ≥ files`); K3's
self-reported over-extension ("enum fields legal" → corrected to "enum vocabulary legal,
enum application unverifiable"); two dispatches written against stale substrate in one
session (Dispatch 1B's `unused = orphan` rule, falsified by a named reserve asset).

**Mechanics.** The reflection is a *reflection*, not a disclaimer: it does not weaken the
return, it prices it. A return with an explicit missing middle is *more* citable, because
the reader can quote the near end without inheriting the far end. The reflection is also
where a mid-execution method correction is registered (per P/D/A discipline: register the
correction; do not silently pivot) — the close is the natural home for it.

**Scope.** Standard move on *closing a return* — recon returns, witness returns, recon
P/D/A returns, and any return whose claims will be merged or quoted by another lane.
Strip before merge happens at the reader; the missing-middle close is what makes the
strip cheap.

## Validation hardness & abstention (the primitive-geometry layer)

Two deeper mechanisms from primitive geometry harden everything above:

- **Validate by structure, not by fluency.** A claim is true here not because an agent stated
  it well, but because it **reverse-traces to a substrate locus and survives a check.** The
  substrate + evidence tag *is* the solver. Low-dimensional, exact references (`file:line`,
  commit hash) are far easier to validate than high-dimensional prose — which is the real
  reason D-claim-locality binds a claim to a locus rather than a summary. Geometry is a *hard*
  constraint: the output must satisfy it, not merely sound like it does.
- **Abstain over fabricate.** When the substrate/COP lacks support, the agent **withholds and
  raises collection** rather than inventing — already SRP-1 (anti-gamble). The geometry frame
  makes abstention the *default* under low constraint, not an exception: low constraint +
  high stakes = a gamble, which the contract blocks.

These connect to the existing **geometric command manifold** (Distributed Command Primitives
§11 — Operator / Doctrine / Recon / Execution each in a distinct geometry), retained, per that
section, as a **modeling lens, not a literal claim.**

## Continuity tie-in (why this lives next to the COP)

On RefreshRequest / rehydrate, the COP must reload with its **constraint geometry intact** —
per-claim provenance, locus, and evidence tags preserved. A compact restore that keeps the
*text* but drops the *geometry* rehydrates a hallucination-prone COP. Therefore Snapshot /
CompiledCOP validation (SRP-2 / R-9) must check **geometry, not just schema**: a restore
missing provenance / locus / tags is **quarantined, not parsed**.

## Provenance of this clause (applying the discipline to itself)

The framing arrived with external citations [1]–[6] that are **unverified here**. Per the very
discipline this clause encodes, the *principle* is folded in; the *citations are not* propagated
as substrate. Empirical claims herein are **T-STRUCTURAL** until grounded. (Folding unverified
citations into an anti-hallucination clause would itself be a constraint-geometry violation.)

## Posture

Vocabulary + procedure (Phase-C). Reconcile against the actual Communications Contract
(`comms_contract_v1_4`, CT-2-held — not seen by COW). No schema change; the per-claim envelope
discipline is naming, deferred to Phase D+.

---

## v0.4 amendment · Answer discipline for stripped returns (2026-08-04)

*Source: pen + Claude chat realizations 2026-08-04 (contact/grip reframe, maneuver-grade
output shape, position-cost sort). Folded by K3; every substrate anchor below verified at
pin `ae221b6` before banking. This governs **LLM-stripped returns and restatements to the
user at the return half of the loop** — the system sent (r), the return has come back, and
what the user now reads must be composed under these rules.*

### The contact criterion (what an answer may restate)

**An output that cannot move is a sensor that is not attached.** Before any value is
restated to the user as a finding, it must pass the contact test: *two different inputs
produced different outputs at this locus.* A constant is not a wrong reading — it is a
disconnected one, and restating it as information is the verified-prefix carry in numeric
form.

Enumerated defect class (finite set, closed 2026-08-04): `engine_v1.py` carries **12
input-independent output literals** plus one disguised constant — `deviation_from_origin`
(`engine_v1.py:215-220`) computes to `0.10 · assumed_age_days` = **9.0 for every unclamped
input**, derivation-shaped, age-parameter echo. `harmonizer.py:183` hardcodes
`degraded: False` — the partial-failure flag of a six-family merge, disconnected.
`compute_state_distribution`'s uniform vertex (25/25/25/25) moves only on lexicon hit.
The census is open for extension; the class is named.

**Notation:** `[const]` — value is input-independent; do not restate as finding.
`[grip]` — contact verified by perturbation (the thing was changed and the hold
registered it; e.g., ET-1's clean-pin isolation of the 13 v44 CI failures 2026-08-04).
A grep you can't perturb is a grep you haven't gripped.

### Maneuver-grade answer shape (how a stripped claim is phrased)

Precision-regime output in a maneuver-regime problem is the inversion this contract
exists to block. **Every claim in a stripped return is: bounded, falsifiable, reversible —
and names the condition that decided it plus what would change it.** The verified model
(`# 🎯 Plain Language Explanation_Gohard.txt:348/:359`, second ladder :595/:603):

> `return False, "Monostable — catastrophe impossible"`
> `return True, "Catastrophe POSSIBLE (but not certain)"`

Forbidden forms: bare precision with no condition (`0.4753`), and bare softness with no
failure mode (`elevated`) — the second is worse: a claim that can't be wrong is a
commitment the user can't feel. `[mvg]` — claim carries its condition and reversal
condition. `[blocks: <move>]` — position-cost assertion, valid only with the blocked move
named; a position claim without its move is the vague-claim disease wearing strategy.

### Return-half restatement (pairing against what was sent)

The r-side exists: `elins_project_runs` (`ELINS/elins_project.py:47`) — the forecast
envelope, dated and horizon-bounded. When a return comes back, the restatement **pairs
against what was emitted**; it does not re-derive fresh and launder the pairing.

- `|r − E|` is reported with its cause ambiguity **declared, never resolved by
  magnitude**: same deviation, three geometries — model wrong / world moved /
  adversarial return. `[Δunsep]` — deviation reported, causes unseparated; separation
  requires repetition across counterparties (ORI.2), not a bigger number.
- **Zero dissonance is ambiguous by construction** — perfect model or no contact, and
  the number alone cannot say which (`reconstruction_error: 0.0` is that case written
  down: unconditional zero, numbness reporting as accuracy). A restatement of zero
  deviation must carry the contact tag or the ambiguity, never neither.
- **Some deviation is the signal.** The return half of the loop is where the system
  can feel the other move; a restatement that minimizes dissonance instead of reading
  it has thrown away the only thing the loop was for.

### Failure this prevents

The live instance is this session's corpus: `intensity: medium` on a nine-word
placeholder, `stability: unstable` with no legal way to say "nothing here,"
`soft collapse` with four decimals parked on the noise floor, and a six-of-seven
observation series where the numeric panel returned the same derived constants on
every input. Each was fluent, precise-looking, and attached to nothing. The user
cannot tell a constant from a reading — marking the difference is the system's job,
and this amendment is where the marking rules live.
