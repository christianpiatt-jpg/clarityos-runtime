# ClarityOS RefreshRequest / Snapshot Contract
### Continuity mechanism for the team operating system — §8 companion to the Minimal Dynamic Spec
*Advisory draft for CT-1 · v0.2 · 2026-06-18 · bounds ratified · +geometry-validation rule (aligns Comms Contract v1.5 §8)*

**Posture (read first).** This is **vocabulary + procedure**, not an implemented schema. It
runs today under agent enforcement (CT-3 compiles, CT-2 alternate, CT-1 disposes). The field
names below are naming discipline; binding them into `app.py` is Phase D+. Nothing here
mutates the architecture (R-13). Bounds may be amended later — nothing is load-bearing in
code yet.

**Non-authority — the governing clause.** This contract is a *mechanical continuity
mechanism*, not a decision mechanism. No object, message, or step may mint an anchor, dispose
an item, alter RoE, or move S_k / S_p. If a step would require CT-1 authority, it is **out of
contract**. This clause overrides any other reading below.

---

## 1. Roles — who may do what (Authority bound)

| Act | Who | Note |
|-----|-----|------|
| **Emit** a RefreshRequest | any agent (CT-3, CT-2, worker) | non-authoritative — a request, not a command |
| **Satisfy** a RefreshRequest | CT-3 (primary), CT-2 (alternate) | = compile a CompiledCOP from substrate; read-only |
| **Mutate** substrate | CT-1 only, via Gate → Anchor | never inside this cycle |
| **Dispose** | CT-1 only | RefreshRequest / Snapshot / Rehydrate are not dispositions |

Compile is read-only and reentrant → concurrent RefreshRequests are safe to satisfy.
Emission carries a rate-limit ControlMeasure (anti-DoS on the compiler).

---

## 2. Objects (vocabulary)

Three objects. **Snapshot** and **CompiledCOP** share one **COP core**; they differ only in
direction of travel.

**RefreshRequest** — read-only restore request.
- `requester_id` · `reason` (wake | post-clear | drift-suspected | manual) · `timestamp`
- `last_known_anchor` (optional pointer, enables a delta compile)
- *no payload, no authority*

**Snapshot** — write-ahead **exit** artifact (agent → substrate), written before clear.
- COP core + optional: `work_in_flight` pointer (S_w) · `last_safe_gate` · `last_recon_source`
- write-ahead · verified · idempotent · non-authoritative

**CompiledCOP** — **restore** payload (substrate → agent); CT-3's projection.
- COP core, merged from the durable layer
- compiled-from-substrate · compact · freshness-checked · non-mutating

**COP core (required fields).**
- `active_anchors`: [ anchor_id + evidence_tag ]   ← pointers, never copies
- `open_dispositions`: S_p state (ids + status)
- `provenance`: compiler_id + signature / origin
- `hints`: schema_version · compiler_version · freshness_stamp

**Forbidden in any object (Content bound).**
transcript · intermediate reasoning · tool dumps · ephemeral chatter · agent-local memory ·
unratified findings · anything that inflates S_k or S_p · anything requiring CT-1 authority.

> The snapshot is a **projection**, not a second copy of the ledger. The ledger is canonical;
> the snapshot / CompiledCOP is a disposable view (Substrate bound). No part of this cycle may
> become a second substrate.

---

## 3. Lifecycle (Timing bound — atomic)

**Trigger.** `usage / window ≥ 0.90` **AND** a safepoint.

**Safepoint** = no open Gate · no half-processed disposition · no in-flight tool · no anchor
being minted · no RECON mid-parse. Defined over *locally observable* state + *substrate-
visible* open items **only** — never another node's private cognition (e.g. "CT-1 mid-decision"
blocks the reset only if it exists as an open disposition). If no safepoint exists, finish the
current action to reach one, then fire.

**Sequence — do not reorder:**
1. snapshot (COP core)
2. write to substrate
3. **verify** the write landed
4. clear context
5. rehydrate from CompiledCOP (compact, target ~0.2 fill)
6. reconcile freshness vs current HEAD (SRP-8)
7. resume

---

## 4. Failure semantics (cardinal rules)

> **Never clear before a verified snapshot. Never act after an unreconciled rehydrate.**

- **Pre-clear failure** (steps 1–3 fail): **abort** the reset. Continue on existing context.
  Raise initiative; alert CT-1. Do **not** clear.
- **Post-clear failure** (steps 5–6 fail): the agent is blank and un-grounded → **HALT**. Do
  **not** act. Fall to the restore PACE chain; escalate to CT-1.

**Restore PACE chain.** **P** CT-3 · **A** CT-2 (same compile) · **C** substrate directly
(git HEAD + latest snapshot + anchor ledger) · **E** CT-1 reconstructs. Source of truth is
always the substrate; agents are interchangeable compilers over it.

---

## 5. Validation on rehydrate (trust nothing unverified)

A CompiledCOP / Snapshot that fails **schema_version**, **compiler_version**, **freshness**,
or **provenance** check is **quarantined, not parsed** — treated as an un-sourced observation
(SRP-2 / R-9). A malformed or unverifiable restore never becomes the COP. On quarantine →
fall to the PACE chain (next compiler / substrate); escalate to CT-1 if exhausted.

**Geometry check (v0.2 — aligns Comms Contract v1.5 §8).** Validation checks **geometry, not
just schema.** A restore that preserves the *text* but **drops constraint geometry** — per-claim
provenance, substrate locus, or evidence tags — is quarantined exactly as a schema failure is.
Restoring text without its geometry rehydrates a hallucination-prone COP. Snapshots must
preserve geometry, not just schema.

---

## 6. Worked example (analytic mission set)

```
RefreshRequest:
  requester_id:      COW-1
  reason:            wake
  last_known_anchor: A130
  timestamp:         2026-06-17T15:36 EDT

CompiledCOP  (satisfied by CT-3):
  active_anchors:    [A68..A125, A126..A130] less A97, A100   (+ evidence_tags)
  open_dispositions: [D-recon-G-1: open, D-pending-1: in-flight, D-pending-4: held]
  provenance:        compiler=CT-3, signed
  hints:             schema v0.1 · compiler v0.1 · fresh @ HEAD d8e44ba
```

COW-1 rehydrates to standing in one read — no transcript, ~0.2 fill, reconciled to HEAD
before acting.

---

## 7. What this contract may never do (closing clause)

Mint an anchor · dispose an item · alter RoE · move S_k or S_p · imply or transfer authority ·
become a second substrate · act on an unverified restore.

Any of these = **out of contract**: the step halts and escalates to CT-1.
