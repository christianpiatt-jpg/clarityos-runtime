# ClarityOS Command — Provisional Anchor Record
*COW advisory staging · 2026-06-17 · PROVISIONAL until ledger stand-up*

> **⚠ SUPERSEDED 2026-06-18.** This staging record (A132=GCS / A133=`substrate/`) drifted from
> the committed ledger floor. Canonical truth is now `ops/ledger/` @ `8cfe17b` (A131, A132-r1,
> A133-r1 with `ops/` paths). See `ClarityOS_COP_rebaseline_2026-06-18.md`. Do not cite this
> file as current.

**Status: provisional.** No canonical ledger exists yet (ET1-SUB-VAL-01 confirmed absence;
`command_structure/` is untracked). These anchors are **adopted by CT-1 but staged here**
until the ledger is stood up. **Update 2026-06-18: D-substrate-name fully disposed** — Value 2
adopted (CT-2 corrected advisory, Option A + amendments) → A133. The ledger location is now
decided; A131/A132/A133 await transcription into `substrate/ledger/` once CT-1 authorizes the
write. One open sub-point remains: committer identity (see A133).

---

## Disposition: D-substrate-name — PARTIALLY ADOPTED (CT-1, 2026-06-17)

| Value | Subject | Outcome |
|-------|---------|---------|
| 1 | Code substrate | **ADOPTED** → A131 |
| 2 | Ledger store (git) | **ADOPTED** (CT-2 corrected advisory, Option A + amendments) → A133 |
| 3 | Snapshot store (GCS) | **ADOPTED** → A132 (location only; write path deferred) |
| — | Runtime write handler | **DEFERRED** to a separate task |

Corrected against ET1-SUB-VAL-01; CT-2's proposed `clarityos-core.git` and `/var/...` paths
rejected as ungrounded/ephemeral.

---

## A131 — Canonical code substrate  *(provisional)*

> The canonical code substrate is `github.com/christianpiatt-jpg/clarityos-runtime.git` @
> `main`. HEAD is authoritative; every T-SUBSTRATE anchor cites repo + commit hash.
> HEAD at ratification: `d8e44ba`.

- Evidence: **T-SUBSTRATE** — git remote verified (order ET1-SUB-VAL-01, finding A).
- Closes: D-substrate-name value 1.

## A132 — Canonical continuity snapshot store  *(provisional)*

> Continuity snapshots are canonical at
> `gs://${CLARITYOS_LIBRARY_BUCKET:-clarityos-library}/snapshots/snapshot-<timestamp>.json`
> (GCS, durable across Cloud Run resets). The runtime write path is deferred to a separate
> task; the location is canonical now.

- Evidence: location **T-SUBSTRATE** (`app.py:286` bucket config; Cloud Run ephemerality,
  ET1-SUB-VAL-01 finding B); store choice **T-STRUCTURAL** (recommendation, finding E).
- Closes: D-substrate-name value 3 (location). Operability pending deferred handler task.

---

## A133 — Canonical ledger store  *(provisional; CT-2 corrected advisory, 2026-06-18)*

> The anchor + disposition ledger is canonical at `clarityos-runtime.git/substrate/ledger/`
> as two append-only JSONL files: `anchors.jsonl` (S_k) and `dispositions.jsonl` (S_p). Git is
> authoritative; an optional Firestore mirror is read-only, regenerable, zero-authority.
> Commits are signed; single-writer cadence (one append per CT-1 disposition).

- Evidence: store choice **T-STRUCTURAL**, grounded in durability **T-SUBSTRATE** (ET1-SUB-VAL-01).
- Closes: D-substrate-name value 2.
- **OPEN sub-point — committer identity.** CT-2 proposed CT-3 commits via CT-1 relay. COW
  objects: this collides with the contract (CT-3 read-only) and undermines D-compiler-check
  (a compiler that also writes the ledger can close its own loop). **COW recommendation:**
  the write executes via **ET-1** (write-capable executor) under **CT-1 authorship**; CT-3
  stays read-only compiler; CT-2 alternate. Pending CT-1 ruling + `D-substrate-sign` (signing
  topology, UNTRACED).

---

## Keystone now closed

D-substrate-name is fully disposed across all three values (A131 code · A132 snapshots ·
A133 ledger). The substrate location is decided; the D-series now has a real floor to record
into — pending (a) CT-1's ruling on the committer sub-point and (b) authorization to stand up
`substrate/ledger/` (a canonical-substrate write).

---

## D-comms-contract-v1-5 — ACCEPTED (b), provisional (CT-1, 2026-06-18)

CT-1 ruled **(b)** — accept v1.5 with cleanup pass:
- **Flag 1 (§4.4) folded** — Reading-A lock: per-claim verification normative; schema-level
  enforcement deferred to Phase D+; mixed-class messages self-flag class boundaries inline.
- **Flag 3 (§8) folded** — Snapshot Contract bumped to **v0.2** (geometry-validation rule);
  v1.5 §8 supersedes Snapshot Contract v0.1 validation rule. Two docs now agree.
- **Flag 2 resolved** — D-claim-locality = **Doctrine #98**; D-claim-verification-boundary =
  **Doctrine #99** (ratified as contract clause + doctrine number).
- **Path correction** — records to `substrate/ledger/dispositions.jsonl` (per A133), **not**
  CT-2's drafted `ops/ledger/`.

Provisional disposition entry (transcribe to `substrate/ledger/dispositions.jsonl` on stand-up):

```json
{"schema_version":"1","id":"D-comms-contract-v1-5","status":"CLOSED","statement":"Communications Contract v1.5 ratified (b: cleanup pass) — folds Constraint-Geometry Clause into §§3.4,4.3,4.4,7.2,7.3; Flag-1 Reading-A lock + Flag-3 §8 supersession folded; Doctrines #98/#99 numbered. Supersedes v1.4. No schema/envelope change; new sections T-STRUCTURAL until grounded.","resolves":["comms-contract-v1-5"],"evidence":["COW-1 v0.2 advisory 2026-06-18","CT-3 merge 2026-06-18","CT-2 substrate review 2026-06-18"],"authority":"CT-1","ratified_at":"2026-06-18"}
```

Status: **provisional** — cannot durably record until `substrate/ledger/` exists (committer
ruling still pending).

## Transcription instruc