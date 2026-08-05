# ClarityOS Command — COP Re-baseline (from committed substrate)
*COW-1 · 2026-06-18 · re-grounded from `ops/ledger-floor` @ `8cfe17b` · supersedes prior staging COP*

**Why this exists.** COW-1's prior staging COP drifted from the committed ledger floor and
produced two substrate-disconfirmed catches. This re-baselines COW's COP from the canonical
substrate (the committed ledger), not from local staging. Prior staging docs are superseded.

## Canonical substrate (verified @ `ops/ledger-floor` `8cfe17b`)
- **Branch:** `ops/ledger-floor` (local + origin). **Code:** clarityos-runtime @ `main`, HEAD `d8e44ba`.
- **Ledger:** `ops/ledger/anchors.jsonl` (3 lines) + `ops/ledger/dispositions.jsonl` (9 lines).
  `sha256(dispositions.jsonl)` = `4ce30ce0…36d5da` (matches CT-2).

### Anchors (canonical)
- **A131** — code substrate: clarityos-runtime @ `main`, pinned `d8e44ba`. *(T-SUBSTRATE)*
- **A132-r1** — snapshot store: **`ops/snapshots/`** (Option C: git canonical + Firestore read-only mirror). Supersedes A132. *(T-STRUCTURAL)*
- **A133-r1** — ledger: **`ops/ledger/`** (Option C). Supersedes A133. *(T-STRUCTURAL)*
- **Write authority** (per A132-r1/A133-r1): **ET-1.W primary / ET-1.C alternate, CT-1 authoring identity.** Scoped `git add -f ops/...` only; signing required. → This already settles the committer question.

### Dispositions committed (9)
`D-substrate-name`, `D-A132-plane`, `D-A133-plane` (CLOSED) · `D-error-22/23/23a/24` (CT-2 + COW error case studies, Doctrine #97) · `D-error-24b` (OPEN — signing scope) · `D-signing-config` (CLOSED — SSH ed25519, `%G?`=G).

## Pending appends (next signed commit on `ops/ledger-floor`)
1. **D-comms-contract-v1-5** — READY. CT-2 reissued Line 1, JSON-validated, no duplicate in ledger.
   Ruling reconciled: **(c)** is the ledger disposition; cleanups deferred to **CLEANUP-TRIO-01**.
2. **D-error-24b → CLOSED** — HELD pending ET-1.W `ET1-RESCOPE-01` return (literal config values).

## Reconciliation — "accept b and c"
- **(c)** = canonical ledger ruling: ratify v1.5 verbatim, defer cleanups.
- **(b)** = the *content* of CLEANUP-TRIO-01: COW's folded cleanups — Snapshot Contract **v0.2**
  (done), §4.4 Reading-A lock text, §8 supersession footnote, Doctrines **#98/#99**.
- No contradiction: (c) defers; (b) is what the deferral contains.

## COW self-error — proposed case study (for CT-1 disposition)
```json
{"schema_version":"1","id":"D-error-25","status":"PROPOSED","statement":"COW-1 issued two catches (path substrate/ vs ops/; ruling b vs c) compiled from a stale pre-r1 staging COP rather than the committed ledger floor 8cfe17b; cited superseded A133. Substrate-disconfirmed on verification and withdrawn. Root cause: compiled from local cache, not substrate - the failure the RefreshRequest/compiler discipline exists to prevent. Logged as Doctrine #97 case study #25.","resolves":["doctrine#97#case25"],"evidence":["git rev-parse 8cfe17b OK","sha256 ops/ledger/dispositions.jsonl=4ce30ce0...36d5da matches CT-2","A133-r1 supersedes A133 (ops/ not substrate/)"],"authority":"CT-1","ratified_at":"<pending>"}
```

## Superseded
`ClarityOS_Anchor_Record_provisional.md` (which carried A132=GCS / A133=`substrate/`) is
**SUPERSEDED** by the committed floor. Canonical truth = committed `ops/ledger/` @ `8cfe17b`.
