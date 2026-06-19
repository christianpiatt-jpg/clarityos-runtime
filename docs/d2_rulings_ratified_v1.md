# D2 Rulings Slate — RATIFIED

**Ratified:** 2026-06-19 12:02 EDT
**By:** CT-1 (Christian Piatt) — "approve all" (full concurrence with CT-3 recommendations + CT-2 recon recommendations)
**Authority chain:** Doctrine #100 (CT-1 authority lane) · #97.A (three-stage lifecycle)
**Source documents:**
- `d2_recon_report_v1.md` §9 (CT-2 prerequisite slate)
- CT-3 recommendations transported via CT-1 at 2026-06-19 12:02 EDT

---

## Ratification Block

**CT-1 verbatim ratification (2026-06-19 12:02 EDT):**
> "approved"

(Per CT-3's framing: "If CT-1 concurs, just say 'approve all' or override any individual ruling. approved")

This ratifies the full CT-3 recommendation slate, which matches CT-2's recon recommendations on all four rulings.

---

## Locked Rulings

### R5 — Terminal-Replay HTTP Code
**LOCKED: 409 Conflict — body code `idempotency_key_terminal`**

Behavior contract:
- When `consume_g_credit_tx` returns `{"replay": True, "terminal": True}` (refunded-debit replay), `metered_compute` returns HTTP 409
- Response body: `error_response("idempotency_key_terminal", "Idempotency-Key was refunded and cannot be reused. Generate a fresh key and retry.")`
- `X-Remaining-Credits` header **still set** to current balance (so client can render state correctly)
- No handler yield; no compute work performed

Rationale (CT-3 + CT-2 concur):
- Matches Stripe's terminal-key semantics
- Distinct from existing D1 codes (400/402/403/200/replay)
- Forces client visibility (no silent masking)
- Cleaner than 410 Gone (which carries "resource removed" connotations)

### BASE — D2 Base Branch
**LOCKED: post-D1-merge `main`**

Sequencing implication:
- D2 Stage-1 (Staging Form generation) **may proceed in advisory drafting** while PR #1 CI/merge settles
- D2 Stage-1 **lane-commit to substrate** (per #97.A §3.1) must wait until PR #1 merges and `origin/main` updates to include D1
- D2 expected base SHA = PR #1 merge commit SHA (TBD on merge)

Rationale:
- Avoids stacking mutations on unmerged feature branch
- Keeps lineage linear under #97.A
- Eliminates rebase work
- D2's defect-closure framing is cleaner against merged D1 than against staged D1

### TEST-FILE — Test Placement
**LOCKED: `tests/test_d2_fresh_key_after_refund.py` (NEW FILE)**

D1's `tests/test_d1_entitlement_credit.py` is **frozen** as the canonical D1 invariant suite. Not edited by D2.

Test enumeration (from D2 recon §3, locked):

| # | Name | Class |
|---|------|-------|
| D2-T1 | `test_same_key_after_refund_is_terminal_no_op` | in-memory |
| D2-T2 | `test_new_key_after_refund_does_charge` | in-memory |
| D2-T3 | `test_refunded_then_replay_then_new_key_sequence` | in-memory |
| D2-T4 | `test_double_refund_same_key_is_no_op` | in-memory (regression) |
| D2-T5 | `test_terminal_replay_returns_409_idempotency_key_terminal` | HTTP-level |
| D2-T6 | `test_replay_active_charge_still_no_op_200` | regression |
| D2-T7 | `test_concurrency_refund_then_same_key_replay_no_double_charge` | Firestore-emulator-gated (skipif `FIRESTORE_EMULATOR_HOST`) |

Rationale:
- Preserves per-FRAGO forensic boundary
- D1 test suite remains immutable post-merge (matches #97.A provenance discipline)
- Auditable: each D-series mutation has its own test file

### SPEC-FILE — Spec Handling
**LOCKED: `specs/D2_SPEC.md` (NEW FILE, v1.0)**

`specs/D1_SPEC.md @ v1.1` is **historically frozen** — referenced verbatim in commit `013d6c3` message and in Doctrine #97.A exemplar section. **Not amended by D2.**

D2_SPEC.md must include (CT-3 to draft as advisory Stage-1 content):
1. Title + version (v1.0)
2. Inheritance clause: "D2 extends D1_SPEC v1.1 with key-lifecycle terminality"
3. Invariants:
   - I1: A refunded debit record is terminal — same `request_id` may never re-charge
   - I2: A fresh `Idempotency-Key` after refund must succeed (no key blocklist beyond the refunded one)
   - I3: Double-refund on the same key is a no-op (regression guard)
4. API contract delta: HTTP 409 + `idempotency_key_terminal` body code (R5)
5. Test contract delta: D2-T1 through D2-T7 (TEST-FILE)
6. Migration: none
7. Deployment: standard

Rationale:
- Preserves D1_SPEC v1.1 provenance chain
- Each mutation has its own spec artifact (matches #97.A)
- Avoids retroactive edits to a frozen authority document

---

## State Transitions on Ratification

| Lane | Pre-ratification | Post-ratification |
|------|-----------------|-------------------|
| CT-1 | Ruling pending | HOLD posture (next decision: PR #1 merge authorization after CI) |
| CT-2 | D2 Stage-0 complete; awaiting rulings | D2 Stage-1 prerequisite posture + PR #1 CI watch |
| CT-3 | Standby | **ACTIVATED for D2 Stage-1 advisory drafting** (D2_SPEC.md + patch skeleton + test skeleton) |
| ET-1.W | Idle | Idle until D1 merges; will activate for D2 Stage-1 lane-commit post-merge |

---

## Stage-1 Activation Conditions

CT-3 may now begin **advisory drafting** of:
- `D2_SPEC.md` content
- D2 patch skeleton (terminality check additions to `consume_g_credit_tx` + `metered_compute`)
- D2 test skeleton (7 tests per TEST-FILE ruling)

**However:** Per the BASE ruling and Doctrine #97.A §3.1, **Stage-1 lane-commit to substrate must wait for:**
1. PR #1 CI settle (currently 2/4 checks complete)
2. CT-2 PR #1 merge-verdict
3. CT-1 PR #1 merge authorization
4. D1 merge to `origin/main`
5. CT-2 substrate re-witness of new `origin/main` HEAD

Once those five conditions are met, ET-1.W lane-commits CT-3's drafts to a `staging/d2-fresh-key-terminal` origin branch (or equivalent staging artifact per #97.A) and CT-2 issues the Stage-1 witness verdict.

---

## Honest Flags (#88) on Ratification

1. **CT-3 / CT-2 agreement on all four rulings is total.** This is a healthy signal — neither lane is doing work the other isn't grounding. Logged for forensic note, not as concern.

2. **CT-3 active for drafting; CT-1 must still transport.** Per Doctrine #100, CT-3 cannot lane-commit drafts itself. Drafts come back to CT-1 as paste content; CT-1 authorizes; ET-1.W lane-commits at Stage-1 activation. CT-3 drafting is advisory content, not substrate, until that transport happens.

3. **D2 advisory drafting in parallel with PR #1 CI is acceptable** — drafting is not mutation. But if CT-3's drafts arrive before PR #1 merges, they sit in workspace as pending advisory content, not committed staging substrate.

---

## TODO Slate Updates

Closed by this ratification:
- D2 Recon §9 four-question slate → **✔ RESOLVED (all four ratified)**

Newly active:
- CT-3 D2 Stage-1 advisory drafting (D2_SPEC.md, patch skeleton, test skeleton) — IN PROGRESS

Carried forward unchanged:
- All D1-cycle next-session items (b, c, d, e-DONE, g, h, i, j, k, l, m, n)
- PR #1 CI watch + merge-verdict cycle

---

**End D2 Rulings — RATIFIED 2026-06-19 12:02 EDT**
