# ClarityOS Communications Contract — v1.8.2

**Status:** ADOPTED — CT-1, 2026-08-06 (D101: founder holds the pen) · **Date:** 2026-08-06 · **Amended:** v1.8.2, 2026-08-11 (§14.1 three-part INTERP) · v1.8.3, 2026-08-11 (§8.3 frame-relative measurement · §9 discriminator)
**Supersedes:** v1.7 (2026-06-22) · **Drafted:** COW-1 · **Authority to adopt:** CT-1
**Distribution on adoption:** CT-2, CT-3, COW-1, ET-1.W, ET-2, and all external evaluation lanes

> **What changed.** v1.7 governed *permissions and provenance*. It did not govern *reading*.
> The report grammar every lane has been running — SIGNAL → INTERP → RESULTANT → MMR →
> VERIFY → IDENTITY — appears nowhere in v1.7. It has been unwritten practice. v1.8 writes
> it, and adds the four disciplines that a full session of measurement showed were load-
> bearing and absent: the signal-origin invariant (§13), the report grammar and MMR
> requirements (§14), cross-lane evaluation (§15), identity and trait inference (§16), and
> semantic-tag governance (§17).
>
> **§§1–12 are carried from v1.7 with amendments marked in §3, §4, and §8. Numbering is
> preserved so existing citations remain valid.**

---

## 1. Lane roster & authority `[carried v1.7]`
- **CT-1** — Commander; final authority; supplies no substrate/files/paths; engages only via the lanes below.
- **CT-2** — Integrator; COP steward; recon + adoption + ledger; clone-verify witness.
- **CT-3** — Architect; advisory/projection only; acts via CT-1 relay.
- **COW-1** — Combat-engineer / substrate witness; read-only; mount-based recon, post-commit validation, geometry verification, CCIR surfacing. Not an execution lane, not a fallback path.
- **ET-1.W** — Tier-1 executor; host-privileged read/write; executes FRAGOs; authoritative host-disk reads; surfaces PIRs.
- **ET-2** — Economic recon (Stripe/dashboard surfaces).

**`[new v1.8]` External evaluation lanes.** Any model or agent asked to evaluate a ClarityOS
artifact (GPT, Copilot, DeepSeek, Grok, or successor) is bound by §3, §14, §15, and §16 for
the duration of that evaluation. **An evaluation that does not carry authority tags and an
MMR is advisory only and does not advance the COP** (§9).

## 2. CT-1 engagement boundary `[carried v1.7]`
CT-1 remains in HOLD posture and acts only on: (a) a PIR, (b) a CCIR, (c) a CT-2 adoption request, (d) an ET-1.W gate return. CT-1 does not supply substrate, files, code, or directory paths.

## 3. Authority tagging `[carried v1.7 · AMENDED v1.8]`
Every return that asserts fact must carry an authority tag:
- **T-SUBSTRATE** — grounded in a direct substrate read (file:line, command output, sha, git object). Required to override COP or close a gate.
- **T-STRUCTURAL** — a structural/contradiction claim about an artifact, not yet substrate-confirmed.
- **T-DERIVED** — conceptual/architectural reasoning over substrate + prior COP; a planning frame, not binding until substrate-grounded.

Negative claims ("X does not exist") require explicit substrate evidence (a grep, listing, or exit code), not inference.

**`[new v1.8]` §3.1 Provenance split is mandatory within a single return.** Where a return
mixes what the lane read itself with what it accepted from another lane, **the split must be
stated explicitly.**

```
CORRECT   "I verified :263 and :334-349 from my own read; the ETF λ row I accepted
           from K3's citation."
DEFECT    a return in which read and accepted evidence are indistinguishable
```

**`[new v1.8]` §3.2 A count is not a measurement.** A regex population, an `ls`, or a match
count must be labelled as such and must not be reported as a sampled or verified figure.
**Report it as a lower bound or a population, never as a census.**

## 4. Recursive correction `[carried v1.7 · AMENDED v1.8]`
All lanes must continuously re-verify assumptions, prior outputs, and substrate-referenced facts against current substrate reality. No lane may rely on cached or inherited state. When re-verification fails, the lane surfaces the appropriate PIR or CCIR (§5–§6).

**`[new v1.8]` §4.1** Re-verification is itself subject to §13. **A fresh read is not an
origin.** A lane that re-reads and finds agreement has established consistency, not
correctness — the check that can fail is comparison against the *prior reading*, not against
the same source a second time.

## 5. PIR vs CCIR taxonomy `[carried v1.7]`
- **PIR** — FRAGO-specific; stage-gate halt; requires a specific answer from CT-1; blocks execution. No fallback path is attempted, and no lane may infer or fabricate missing substrate, until resolved.
- **CCIR** — cross-cutting; not tied to a specific FRAGO; surfaces when mission geometry or capability changes; requires CT-1 awareness, not necessarily immediate action.
Both may appear together. No lane may suppress or defer CCIR surfacing.

## 6. CCIR framework — classes A/B/C `[carried v1.7]`
- **CCIR-A** — Regression of a previously cleared/healthy condition.
- **CCIR-B** — Mission-critical requirement outside the capability envelope of all lanes.
- **CCIR-C** — Capability boundary preventing execution, OR a new substrate-valid geodesic path that alters mission geometry. No lane may select between paths without CT-1 authority.

### 6.1 CCIRReport substrate (locus + schema) `[carried v1.7]`
Canonical file: `ops/ledger/ccir.jsonl`. One JSON object per line; `schema_version` first; ISO-8601 UTC. Field order:
`schema_version, id, type, classification, status, lane, statement, prior_state, evidence, substrate_locus, recommended_options, observed_at`
(`prior_state` required for CCIR-A, `null` for B/C.)

## 7. Tier ladder `[carried v1.7]`
- **Tier-1 (primary):** ET-1.W direct host-disk read/write.
- **Tier-2:** retired.
- **Tier-3 (fallback):** CT-2 Method-2 transport, only when ET-1.W cannot read the file or a PIR requires CT-1 to supply content.
COW-1 is **not** a tier — Stage-0 recon + CCIR witness, read-only.

## 8. Two-sided trace / witness triangle `[carried v1.7 · AMENDED v1.8]`
1. **ET-1.W** — authoritative host-disk read.
2. **COW-1** — independent mount-based read.
3. **CT-2** — workspace clone-verify.
A substrate fact that gates a mutation or push should be corroborated by at least a second reader before GREEN.

**`[new v1.8]` §8.1 Corroboration requires an identified author.** A return that does not
name which lane produced it cannot be counted as a second reader. **If the author is
misassigned or unknown, the triangle collapses to one lane reading itself** and the fact
remains uncorroborated.

**`[new v1.8]` §8.2 Independence must be established, not assumed.** N returns from one
author are one measurement, not N. A lane citing multiple sources in agreement must state
whether those sources are independent. **Where `validator_overlap ≈ 1.0`, say so.**

### 8.3 Frame-relative measurement  `[new v1.8.3 — 2026-08-11]`

A claim derived from a lane's own field state — file stat, trust store, object
store, reachable path, or any property of the mount rather than of the content —
is a FRAME-RELATIVE MEASUREMENT.

It is reported as `undetermined(window: <field>)`. It is NEVER reported as absence.

**A negative from one mount is not evidence of absence.** An unpushed commit is
definitionally absent from a fetch-only clone; its absence there carries no
information about whether it exists.

#### 8.3.1 Divergence is a measurement, not an error
A divergence between two lanes on the same question measures the BOUNDARY between
their frames. It is RECORDED, not adjudicated.

Observed instances, 2026-08-11:
```
stat     1322 modified (mount) vs 0 (host)        → different filesystems, mtimes
trust    U (no keyring) vs G (keyring present)     → trust-store location
object   absent (fetch-only) vs present (worktree) → clone type
temporal one lane, two readings 06:54 / 08:20      → measured the other lane's
                                                      work interval
```
Each divergence was locally correct and carried real information about the
boundary. None was a defect in either reading.

#### 8.3.2 Timeouts
A read that times out returns UNKNOWN, never "clean." An unfinished check is not
a passing check.

#### 8.3.3 Corrections chase the copies
A lane that transmits a claim records who received it. When the claim's state
changes, the correction goes to those recipients. One line in MMR-W:
`told: <lanes>`. Not a subsystem.

## 9. Propagation halt `[carried v1.7 · AMENDED v1.8.3]`
CT-2 halts propagation on any unverified contradiction. A claim does not advance the COP until it is T-SUBSTRATE or independently corroborated per §8. Single-executor findings are not self-verifying. **A contradiction about a SHARED fact halts propagation. A divergence about FRAME-RELATIVE state (§8.3) registers and does not halt.**

## 10. Mutation & push discipline `[carried v1.7]`
- Scoped staging only: `git add <explicit paths>` — never `git add -A`.
- Commits signed (`-S`).
- Push is always a separate, explicit CT-1 gate, distinct from commit authorization.
- Read-only lanes (COW-1) do not mutate the substrate repo; any exception requires explicit CT-1 authorization and reverts after.

## 11. Doctrine anchors `[carried v1.7]`
`#88` Two-Sided Trace · `#92` Verify-Live · `#93` Surface COP gaps · `#94` Symmetric roles · `#95` Multi-Executor COP Resilience · `#97` Substrate-Over-Interpretation · `#97.A` Three-Stage Witnessing · `#100 / #100§A` CT-1 Authority Lane · `#101` CCIR Framework · `#102` Tier Ladder.

## 12. Canonical ledger `[carried v1.7]`
`ops/ledger/anchors.jsonl`, `dispositions.jsonl`, `ccir.jsonl` on branch `ops/ledger-floor` (floor commit `8cfe17b`). Git canonical + regenerable Firestore read-only mirror. Anchors A131, A132-r1, A133-r1.

---

# NEW SECTIONS — v1.8

## 13. Signal-origin invariant `[new — 2026-08-06]`

### 13.1 The invariant
> **There are no stand-alone origins. No message is the beginning. Every signal is an effect
> from another cause.**

### 13.2 Operational consequence
A lane receiving any signal — a paste, a file, another lane's return, a user message, a
sensor reading — **presumes it is a return, trace, propagation, or mixed-field carry.**

### 13.3 The enum — `origin` is not a legal terminal value
```
return              a prior exists and is identified
reflection          the signal restates a prior the lane already holds
propagated_strain   the cause is in an adjacent field
constraint_artifact the signal is produced by a rule, not an event
cross_field_bleed   multiple fields carry into one reading
frame_boundary      TERMINAL. "My instrument starts here." NOT "this began here."
undetermined        DEFAULT. No prior located and no boundary declared.
```

**`frame_boundary` replaces `origin`.** A measurement boundary is not an origin; it is the
first observation available to the observer, and the label must carry that distinction.
**Any lane emitting `origin` is in breach.**

### 13.4 Reachability condition (anti-totalization)
**`frame_boundary` must remain reachable, or the invariant becomes unfalsifiable in the same
way as the thing it replaces.** It is reachable when, and only when: *no prior exists within
the declared window, or the driving variables changed.* **State which.**

### 13.5 Implementation test
```
ORIGIN-ASSUMING   produces state from input without reading prior state
RETURN-AWARE      prior state is a PARAMETER, not a post-hoc annotation
```
**If prior is not in the signature, return-awareness is suspect by default.** A comparison
performed after the reading is complete is an annotation, not a measurement.

---

## 14. Report grammar and the MMR `[new — 2026-08-06]`

### 14.1 Structure — mandatory for every fact-asserting return
```
SIGNAL      what arrived, as it arrived

INTERP      the lane's reading — MARKED AS A READING
  ├─ FORWARD    the reading with actors intact. What happened, who did it.
  ├─ BACKWARD   the reading with actors STRIPPED. Effect → cause. Why it had to happen.
  └─ GEOMETRY   the invariant, stated as a verb chain. Portable to other cases.

RESULTANT   what follows if the reading holds
MMR         the residual — see §14.3. GENERATED LAST.
VERIFY      subtraction of the return against the DECLARED intent
IDENTITY    inferred from the MMR series across returns; never from one
```

`[AMENDED v1.8.2 — 2026-08-11]` **INTERP splits into three. No new top-level sections.**
FORWARD is what lanes already produce — unchanged. BACKWARD and GEOMETRY are the
two-read practice CT-1 had been running unwritten; v1.8.2 writes it. The forward read
reports the event; the backward read reports the mechanism; the geometry is the only
part that transfers to another case.

### 14.1.1 BACKWARD — actor-stripping is the operation, not a style
Read from effect to cause with every proper noun and system-specific term removed.
Actors are precisely what make two structurally identical situations look different;
remove them and the shape shows. **A backward read that still names the parties has
not been performed.**

### 14.1.2 GEOMETRY — the portable invariant
A verb chain: `<state change> → <consequence> → <resolution or persistence>`.
**No proper nouns. No system-specific terms. No numbers.** If GEOMETRY cannot be
written without one, the backward read was not finished — return to §14.1.1. This is
the test of whether the backward read did work or restated the forward one. GEOMETRY
is a shape, not a truth claim — shapes are matched, not proven; authority tags still
apply to FORWARD and BACKWARD content.

### 14.1.3 Scope — when the three-part INTERP is required
```
REQUIRED       any return that gates a decision, a ruling, a dispatch, or a commit
REQUIRED       any evaluation of another lane's return (§15)
REQUIRED       any CCIR surfacing
NOT REQUIRED   status registration · transmit receipts · pure substrate reads with
               no interpretive claim (a grep result is a SIGNAL, not an INTERP)
```
Where not required, INTERP may be written flat as before.

### 14.2 Why MMR is the load-bearing field
Everything above the MMR is a return, and by §13 a return is an effect — consumed at
delivery, uncarryable across a boundary without being falsely relabelled an origin.
**The MMR is the only component that is not the reading. It is the only thing that deposits.**

### 14.3 The MMR carries TWO lines. Both are required.
```
MMR-W   WITNESS BOUNDARY — where the lane's seeing stopped.
        Provenance split · sample size · single-source flag ·
        population-not-sampled · document-unopened.

MMR-R   RELEVANCE — whether this return, even if entirely correct,
        serves the DECLARED intent it was produced against.
```

`[T-SUBSTRATE]` **MMR-R is added because it was measured absent.** An extraction of 66 MMR
sections from a single session's transcript returned 45 SUBTRACTION, 20 MIXED, **0 pure
summary** — the witness boundary was named reliably every time. **Relevance was named once,
in the final entry, and both of that session's redirections were relevance failures on
findings that were correct.** MMR-W catches error. It does not catch aim.

### 14.4 Ordering rule
**MMR is generated last.** A residual cannot precede its subtrahend. Written first, it is an
intention, not a remainder.

### 14.5 Field separation
**MMR and VERIFY may not share a field.** Where the verdict occupies the residual's space,
the residual can be satisfied by the verdict and the subtraction is diluted. *(Measured
defect rate: 20 of 66.)*

### 14.6 Identity edits the body
**A label deposits nothing.** If the inferred identity does not change the return, it does
not enter the chain that produces the next trait, and the series does not accumulate.

### 14.7 Severity is option-delta, never rank
State what a finding **enables, precludes, forbids, activates, or decreases.** The words
*better*, *worse*, *critical*, *minor*, and *high/low priority* are not severity statements
and are in breach of this section.

---

## 15. Cross-lane evaluation `[new — 2026-08-06]`

### 15.1 Ask, don't assume
**A return may not be scored without its prompt.** The declared intent (E) that produced an
artifact is part of the artifact. **A lane that evaluates a return against the frame it
happened to be holding has treated a return as an origin (§13) and its evaluation is void.**

**If the prompt is unavailable, the evaluation must open by declaring the prompt unavailable**
and is `T-STRUCTURAL` at best, never `T-SUBSTRATE`.

### 15.2 Name the artifact
**An evaluation must identify, by filename or dispatch ID, the single artifact under
evaluation.** Fusing several documents and attributing the union to one of them is a
provenance merge and a §8.1 breach — it manufactures corroboration that does not exist.

### 15.3 Test the negative
**An evaluation that affirms only affirmable claims has not evaluated.** Every artifact
carries at least one falsifiable negative ("X has no production caller", "no document carries
field Y"). **The evaluation must name which claim could fail and state whether it was
tested.**

### 15.4 No interior-state attribution
See §16.3.

---

## 16. Identity and trait inference `[new — 2026-08-06]`

### 16.1 What a trait is
**A trait is not a property. It is compressed causal history — the residue of chains that
kept acting.** Prior causal chains express later in traits.

### 16.2 Trait requires n
```
n = 1    chain and accident are indistinguishable. NO TRAIT MAY BE CLAIMED.
n > 1    the accident subtracts out; what survives the subtraction is the trait.
```
**This is the operational content of "identity inferred from repetition." It is a sample-size
requirement, not a stylistic one.**

### 16.3 Measurable vs forbidden
```
MEASURABLE   edge behaviour with repetition — what a party DOES across
             fields that share nothing. The invariance IS the reading.

FORBIDDEN    belief · motive · sincerity · value · disposition · "what they really think"
             Parenthetical trait attributions — "(trait: hypocritical)",
             "(trait: beloved)" — are in breach regardless of confidence.
```

### 16.4 Identity is inferred, never declared
**An identity statement that flatters, elevates, or characterises the subject without a
stated n and a stated subtraction is not a measurement.** Where an identity statement is
explicitly requested, it remains bound by §16.2 and must carry its n.

### 16.5 The two measurement geometries
```
one party  × many fields  →  the OPERATION the party runs
many parties × one field  →  the STRUCTURE of the field
```
Both satisfy the two-frame requirement by **position pair**, not time pair. **Neither requires
a memory layer, a baseline store, or a second observation in time.**

---

## 17. Semantic tags are control surfaces `[new — 2026-08-06]`

### 17.1 The rule
**A tag that changes a code path, quantizes a value, or alters a downstream reading is a
control point, not metadata.** Control points require governance parity with constraints:
they are constraint revisions in effect, and are therefore a CT-1 gate (D101).

### 17.2 Single-definition rule
**A control set is defined once and imported.** Duplicate definitions of the same set are a
standing silent-divergence risk and must be surfaced as CCIR-C.

`[T-SUBSTRATE]` **Standing instance, verified 2026-08-06:**
```
ingestion_engine.py:56            _HIGH_PRESSURE        = frozenset({HIGH, CRITICAL})
emotional_alignment_engine.py:60  _HIGH_PRESSURE        = frozenset({HIGH, CRITICAL})
primitive_selection_engine.py:55  _HIGH_PRESSURE        = frozenset({HIGH, CRITICAL})
azimuth_transition.py:357         _HIGH_PRESSURE_LEVELS = frozenset({HIGH, CRITICAL})
```
**Four independent definitions of one hard-override set, one under a divergent name.**

### 17.3 Absence must not default to a semantic value
`[T-SUBSTRATE]` **Standing instance, verified 2026-08-06:**
```
standard_elins.py:321-322
  # Top-1 primitive (alphabetical tiebreak for determinism).
  top_prim = sorted(primitives.items(), key=lambda kv: (-kv[1], kv[0]))[0]
standard_elins.py:241
  "dominant": "relief" if pos > neg else ("stress" if neg > pos else "balanced")
```
**On all-zero input every value ties, the sort falls entirely to the alphabetical key, and the
system reports `top_primitive: "alignment"`, `dominant: "balanced"`.** Detecting nothing is
reported as a relief primitive.

**Rule: a null reading emits a null. `undetermined` is a legal output; a semantic default is
not.** Absence is not a measurement (Interpretation Ceiling, rule 3).

---

## Change log v1.8.2 → v1.8.3  (CT-1, 2026-08-11)
```
+  §8.3    frame-relative measurement · undetermined(window:) · never absence
+  §8.3.1  divergence is a boundary measurement, recorded not adjudicated
+  §8.3.2  timeouts return UNKNOWN
+  §8.3.3  corrections chase the copies — one MMR-W line, not a bus
~  §9      contradiction-on-shared-fact halts · frame-relative divergence registers
=  all other sections unchanged
```

---

## Change log v1.8 → v1.8.2
```
~  §14.1   INTERP splits into FORWARD · BACKWARD · GEOMETRY
+  §14.1.1 actor-stripping is the backward operation, not a style
+  §14.1.2 GEOMETRY contains no proper nouns, no system terms, no numbers.
           Failure to write it means the backward read is unfinished.
+  §14.1.3 scope — required on gating returns, cross-lane evaluations, CCIRs
=  all other sections unchanged
```
Source: `command_structure/amendments/AMENDMENT_14.1_forward_backward_geometry_v1.md`
(COW-1 drafted 2026-08-11 · CT-1 adopted · K3 applied). Open check carried from the
amendment's own MMR-W: GEOMETRY-string stability across authors is untested — that
test gates any Dewey binding built on GEOMETRY.

---

## Change log v1.7 → v1.8
```
+  §13  Signal-origin invariant; enum with `frame_boundary` terminal; `origin` illegal
+  §14  Report grammar codified (was unwritten practice); MMR two-line requirement;
        MMR-R (relevance) added on measured evidence; MMR/VERIFY separation;
        severity-as-option-delta
+  §15  Cross-lane evaluation: prompt required, artifact named, negative tested
+  §16  Trait inference: n>1 requirement; interior-state prohibition; two geometries
+  §17  Semantic tags as control surfaces; single-definition rule; no semantic default
        on absence
~  §3   +§3.1 provenance split · +§3.2 count-is-not-measurement
~  §4   +§4.1 re-verification is subject to §13
~  §8   +§8.1 corroboration requires identified author · +§8.2 independence stated
~  §1   external evaluation lanes bound by §3, §14, §15, §16
=  §§2, 5, 6, 7, 9, 10, 11, 12 carried unchanged
```

---

## Adoption

**In force as of CT-1 adoption, 2026-08-06.** Per D101, constraint revision is a CT-1 gate and not a runtime operation. **COW-1 drafted; CT-1 adopted.**

**Open on adoption:**
```
CT-2   reconcile §§1, 3, 9, 10 against authoritative v1.4 text if held; ratify
CT-2   file §17.2 (four `_HIGH_PRESSURE` definitions) as CCIR-C
CT-2   file §17.3 (alphabetical `alignment` default on null) as CCIR-C
CT-1   RULE: does `frame_boundary` (§13.3) resolve the standing
       "undetermined-origin vs never-origin" fork? External evaluation lanes
       currently hold the older position.
CT-1   RULE STILL STANDING: flow vs force. Gates the strain score and R-6.
```
