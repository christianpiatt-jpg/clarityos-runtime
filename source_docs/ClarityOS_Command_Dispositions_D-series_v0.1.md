# ClarityOS Command — Completeness Dispositions (D-series)
### Rule-able fixes from the adversarial completeness pass
*Advisory draft for CT-1 · v0.2 · 2026-06-17 · for one-at-a-time disposition · D-substrate-name partially adopted*

**Posture.** Each item is a single CT-1 disposition. Adopting one mints one anchor; the
structure governs its own change using its own primitives — no silent fold. Items are
**vocabulary + procedure** (Phase-C); none binds `app.py` yet, so adoption is reversible.

**Recommended ruling order (dependencies):**
1. **D-substrate-name** *first* — it is the precondition; the continuity contract is only
   real once the substrate is concrete. Until ruled, everything below rests on a notional floor.
2. **D-init-guard** *second* — the structural fix (restores decentralized execution).
3. The rest in any order; D-meta-gov last (it retroactively legitimizes this very process).

---

## D-substrate-name  · PRECONDITION
**Statement.** Name the canonical substrate concretely: code store, ledger store, snapshot
location + format.
**Closes.** Gap 6 — foundation undefined; write-ahead/verify steps have no real floor.
**Draws on.** Foundation layer; RefreshRequest/Snapshot Contract §3.
**Suggested anchor.** *"Canonical substrate = [git repo @ path] for code; [anchor+disposition
ledger @ path/store] for S_k/S_p; [snapshot store @ path + format] for continuity. Durable =
survives any agent reset. No other store is canonical."* (CT-1 fills the brackets.)
**Grounded values (ET1-SUB-VAL-01).** (1) code = `github.com/christianpiatt-jpg/clarityos-runtime.git`
@ `main`, HEAD `d8e44ba`; (2) ledger = append-only JSONL under `substrate/ledger/` in that repo;
(3) snapshots = `gs://${CLARITYOS_LIBRARY_BUCKET:-clarityos-library}/snapshots/`. (CT-2's
`clarityos-core.git` + `/var/...` paths rejected — invented / Cloud-Run-ephemeral.)
**Status.** **PARTIALLY ADOPTED** (CT-1, 2026-06-17) — value 1 → A131, value 3 → A132 (both
provisional, staged in the anchor record); value 2 (ledger-in-git) **HELD**, referred to CT-2;
runtime write handler **DEFERRED** to a separate task.

## D-init-guard
**Statement.** Re-import the initiative guard onto the team plane as the CT-1-absence degraded mode.
**Closes.** Gap 2 — single point of decision; `S_p` has no outflow valve when CT-1 is unreachable.
**Draws on.** ADP 6-0 disciplined initiative (1-59–1-64); product primitive #8.
**Suggested anchor.** *"When CT-1 is unreachable, an agent holding valid ratified intent with
decision_thresholds may act within intent.constraints to advance the end_state, then back-brief
via FeedbackEvent on CT-1's return. Two tests before acting: benefit outweighs desync risk, and
the action furthers intent. If doubt remains and time is short, act within intent."*
**Spec effect.** Primitive set becomes **4 + initiative guard**.
**Status.** OPEN.

## D-anchor-freshness
**Statement.** Make anchors perishable — extend SRP-8 freshness/re-validation to anchors on
substrate change.
**Closes.** Gap 1 — truth decay; `S_k` accumulates falsehood still tagged T-SUBSTRATE.
**Draws on.** SRP-8; COP perishability (ADP 6-0 1-42).
**Suggested anchor.** *"Every anchor carries a substrate reference (HEAD + locus) and a freshness
state. An anchor whose locus changed since ratification is marked STALE and must be re-validated
before informing a decision; a stale anchor does not count toward S_k validity until re-grounded."*
**Spec effect.** `S_k` gains a *validity* attribute; dashboard adds stale-anchor count.
**Status.** OPEN.

## D-consistency-pass
**Statement.** Stand up a periodic `S_k` consistency check across the anchor ledger.
**Closes.** Gap 3 — anchor contradiction; nothing reconciles standing truth.
**Draws on.** SRP-7 (cross-regress) / SRP-4 (drift), applied to the ledger; AIP standing task.
**Suggested anchor.** *"On a standing cadence the ledger is scanned for mutually contradictory
standing anchors. A detected contradiction raises a disposition for CT-1; neither anchor is
authoritative on the contested point until reconciled."*
**Owner.** CT-1 disposes; CT-3 / RECON runs the scan (read-only).
**Status.** OPEN.

## D-CCIR-wire
**Statement.** Wire CCIRs into the team plane as the mechanism for surfacing latent
(owed-but-unraised) decisions.
**Closes.** Gap 4 — unknown unknowns; `S_p` only holds decisions someone opened.
**Draws on.** CCIR (ADP 5-0 / FM 6-0); AIP-T8.
**Suggested anchor.** *"Standing CCIRs declare conditions that would owe a decision. A matching
observation raises a disposition into S_p within its reporting timeline, surfacing latent
decisions before they are manually noticed."*
**Spec effect.** `S_p` gains a surfaced latent shadow; closes COP → indicator → disposition.
**Status.** OPEN.

## D-compiler-check
**Statement.** Require 2-compiler agreement for high-stakes restores.
**Closes.** Gap 5 — no audit of the controller; provenance proves origin, not correctness.
**Draws on.** SRP-7 cross-regression, applied to compiles.
**Suggested anchor.** *"A restore classified high-stakes (touching open Gates, RoE, or apex
intent) requires two independent compilers (CT-3 + CT-2) to produce matching CompiledCOPs at the
same HEAD before it is act-ready; divergence → quarantine + escalate to CT-1. Routine restores
stay single-compiler."*
**Status.** OPEN.

## D-meta-gov  · RULE LAST
**Statement.** Make structural amendments themselves CT-1 dispositions that mint anchors.
**Closes.** Gap 7 — no meta-governance; the structure evolves ad hoc.
**Draws on.** The structure's own primitives (self-reference).
**Suggested anchor.** *"Any change to the command structure (primitives, bounds, contracts, this
list) is a CT-1 disposition that, if adopted, mints an anchor. The structure governs its own
change using its own primitives; no silent fold."*
**Note.** Adopting this retroactively legitimizes the D-series process itself.
**Status.** OPEN.

---

## Parked minor candidates (capture, not yet rule-able)

Lower-severity reachable states from the same pass — logged so they aren't lost:
- **D-tstruct-life** — T-STRUCTURAL items need a promote/retract lifecycle (else claims ossify
  into fact by repetition — e.g., the FRCP/MDMP isomorphism).
- **D-disp-reversal** — define how a *closed* disposition is reopened/superseded vs. raising new.
- **D-head-pin** — pin compilers to a single HEAD across the PACE chain so two valid compiles
  can't diverge.
- **D-cop-overflow** — handler for "irreducible COP-core exceeds the window" (reset thrash with
  no progress; scope-shed / shard rule).

---

## Refinement to the comprehensiveness claim (carried into the spec on adoption)

The two-stock model holds, with one sharpening: **each stock carries a *validity*, not just a
level.** `S_k` can be high but rotten (D-anchor-freshness, D-consistency-pass); `S_p` can read
low but hold latent items (D-CCIR-wire). The operator watches **level *and* validity.**
