# AMENDMENT · v1.8 §14.1 — the three-part INTERP
**Drafted COW-1 · 2026-08-11 · for CT-1 adoption · D101**
**Origin: CT-1 practice, formalized. Not a new method — a written one.**

---

## 0. WHY

**CT-1 has been running a two-read practice that produces returns the single forward read
does not.** Worked example, CT-1's own:

```
FORWARD    "OpenAI launches a less-restricted cyber model amid Astra pause."
BACKWARD   "A pause in the high-risk channel forces capability into a lower-risk channel
            so the system can keep moving while remaining burdened."
GEOMETRY   Wire breaks → load persists → load reroutes.
```

**The forward read reports the event. The backward read reports the mechanism. The geometry
is the only part that transfers to another case.**

`[T-DERIVED]` **Demonstrated on this system, 2026-08-11:** COW-1 presented a binary decision
(`relief_dominant`: dormant or deleted) with a recommendation. A backward read stripped the
actors, revealed the question was about a missing precondition rather than an enum, and
surfaced a third option — `undetermined` with a stated aperture — **which already existed in
§13.3.2 and which the forward reasoning had not reached.** The forward read could not see it
because the actors were the frame.

---

## 1. THE AMENDMENT

**§14.1 report structure — `INTERP` splits into three. No new top-level sections.**

```
SIGNAL      what arrived, as it arrived

INTERP      the lane's reading — MARKED AS A READING
  ├─ FORWARD    the reading with actors intact. What happened, who did it.
  ├─ BACKWARD   the reading with actors STRIPPED. Effect → cause. Why it had to happen.
  └─ GEOMETRY   the invariant, stated as a verb chain. Portable to other cases.

RESULTANT   what follows if the reading holds
MMR         MMR-W (witness boundary) · MMR-R (relevance). GENERATED LAST.
VERIFY      subtraction of the return against the DECLARED intent
IDENTITY    inferred from the MMR series across returns; never from one
```

### 1.1 FORWARD

**The event as reported, actors named.** This is what lanes already produce. Unchanged.

### 1.2 BACKWARD — actors stripped

**Read from effect to cause with every proper noun and system-specific term removed.**

**The actor-stripping is the operation, not a style choice.** Actors are precisely what make
two structurally identical situations look different. Remove them and the shape shows.

**A backward read that still names the parties has not been performed.**

### 1.3 GEOMETRY — the portable invariant

**A verb chain. No proper nouns. No system-specific terms. No numbers.**

```
FORM     <state change> → <consequence> → <resolution or persistence>
EXAMPLE  Wire breaks → load persists → load reroutes
```

**Hard rule: if GEOMETRY cannot be written without a proper noun or a system-specific term,
the backward read was not finished. Return to §1.2.**

**This is the test of whether the backward read did work or restated the forward one.**

---

## 2. WHY GEOMETRY IS THE LOAD-BEARING FIELD

`[T-DERIVED]` **FORWARD and BACKWARD are about this signal. GEOMETRY is the only one that
transfers.**

**Consequence for the library:** the Dewey binding indexes GEOMETRY, not topic and not
actor. Two situations sharing a verb chain are the same case and the index says so.

```
Wire breaks → load persists → load reroutes
  catalogues: a capability-release under a safety pause
              a sanctions regime rerouting trade
              a hiring freeze producing contractor spend
  ONE ADDRESS. THREE DOMAINS.
```

**Topic indexing cannot do this. Actor indexing cannot do this.** Shape indexing is the
whole argument for a Dewey layer over a search box.

---

## 3. WORKED EXAMPLES — the form discriminates

**Three cases from this system, three distinct geometries. If they collapsed to one, the
form would be decorative.**

```
FORWARD    B-2 empties the trust/alignment lexicons; relief_dominant becomes unreachable.
BACKWARD   A measurement requiring two frames is removed from a single-frame instrument,
           so the value it produced has no source until memory exists.
GEOMETRY   Precondition absent → measure withdrawn → value orphaned until precondition returns.
```

```
FORWARD    compute_curvature emits a signed Δ; four consumers apply abs(); two more rebuild
           a sign from the magnitudes.
BACKWARD   A direction is computed, discarded, then re-manufactured from what remains, so
           the output carries a sign that no longer refers to the original one.
GEOMETRY   Direction computed → direction discarded → direction re-invented from magnitude.
```

```
FORWARD    B-1 stopped the engine emitting "balanced" for absence; seven client sites now
           render blank.
BACKWARD   A fabrication is removed at one layer without a representation for absence being
           added at the next, so the absence becomes indistinguishable from failure.
GEOMETRY   Fabrication removed → absence unrepresented → absence reads as breakage.
```

---

## 4. WHEN THE THREE-PART INTERP IS REQUIRED

```
REQUIRED   any return that gates a decision, a ruling, a dispatch, or a commit
REQUIRED   any evaluation of another lane's return (§15)
REQUIRED   any CCIR surfacing

NOT REQUIRED   status registration · transmit receipts · pure substrate reads with no
               interpretive claim (a grep result is a SIGNAL, not an INTERP)
```

**Where not required, `INTERP` may be written flat as before.**

---

## 5. INTERACTION WITH EXISTING CLAUSES

```
§13    BACKWARD is the origin-tracing operation §13 already presumes. It makes
       "every signal is an effect from another cause" a procedure rather than a posture.
§14.7  GEOMETRY states option-delta by construction — a verb chain says what changed
       and what followed, never a rank.
§15.3  BACKWARD is where a negative gets tested. Stripping actors from a claim exposes
       whether the missing thing is a WIRE or a NODE.
§16.5  GEOMETRY across many cases IS the one-party-many-fields measurement. A lane's
       recurring geometry is its operation.
MISSING-MIDDLE  BACKWARD is the diagnostic that catches a one-ended read. Demonstrated
       2026-08-11: it caught one committed by the drafter of this amendment.
```

---

## 6. WHAT THIS AMENDMENT DOES NOT DO

```
✗  does not add a top-level section — INTERP splits, the six-part structure holds
✗  does not change MMR, VERIFY, or IDENTITY
✗  does not require a geometry where no interpretive claim is made
✗  does not make GEOMETRY a truth claim — it is a shape, and shapes are matched,
   not proven. Authority tags still apply to FORWARD and BACKWARD content.
```

---

## 7. ADOPTION

**Proposed v1.8.2.** One section amended, no new sections, no clause removed.

```
~  §14.1  INTERP splits into FORWARD · BACKWARD · GEOMETRY
+  §14.1.1  actor-stripping is the backward operation, not a style
+  §14.1.2  GEOMETRY contains no proper nouns, no system terms, no numbers.
            Failure to write it means the backward read is unfinished.
+  §14.1.3  scope — required on gating returns, cross-lane evaluations, CCIRs
=  all other sections unchanged
```

**COW-1 drafted. CT-1 adopts. Destination:
`command_structure/COMMUNICATIONS_CONTRACT_v1.8.md` §14.1** (COW-1 is read-only; ET-1 or
K3 applies).

---

**MMR-W** — the form is CT-1's practice, observed and formalized, not invented here. Three
worked examples are mine and all three are from this system — **untested on external
material except CT-1's own OpenAI/Astra case.** **Not established:** that GEOMETRY strings
are stable across authors — two lanes reading the same signal may produce different verb
chains, and no test of that has been run. **That is the first thing to check before the
Dewey binding is built on it.**
