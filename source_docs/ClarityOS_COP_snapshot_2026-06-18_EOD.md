# ClarityOS COP Snapshot — 2026-06-18 EOD (COW-1)
*Projection, not canonical. Canonical = committed ledger `ops/ledger-floor @ ece5b3b`.*
*Compiler: COW-1 · base `main @ d8e44ba` (A131) · freshness: 2026-06-18 EOD*

## Substrate (verified this session, T-SUBSTRATE)
- **Code base:** `main = d8e44ba` (A131 canonical). `origin/main = 196683c` (6 billing commits stale; converge later).
- **Ledger floor:** `ops/ledger-floor = ece5b3b` — **PUSHED** (`origin/ops/ledger-floor = ece5b3b`, 0/0 divergence). Live `ls-remote` was network-blocked; confidence high via remote-tracking==local-tip. ET-1.W can confirm with `git ls-remote origin ops/ledger-floor`.
- **Chain:** `d8e44ba → 8cfe17b (floor A131–A133-r1) → b4a1f09 (D-error-24b + D-comms-contract-v1-5) → e2cdf89 (D-error-28) → ece5b3b (D-error-29)`.
- **Anchors (canonical):** A131 code, A132-r1 `ops/snapshots/`, A133-r1 `ops/ledger/` (Option C: git canonical + Firestore mirror). Write authority: ET-1.W primary / ET-1.C alt, CT-1 authoring identity.
- **Dispositions:** 15 in `ops/ledger/dispositions.jsonl`; latest D-error-28, D-error-29 CLOSED.

## Decisions ratified this session
- **Billing model:** $50/mo membership = access; compute credit packs = metered ($0.01/call, 1 credit/call). Credit ledger already exists (`users_store` g_credits / consume / add). Membership = access; credits = compute.
- **D1 patch design:** `require_active_entitlement` (membership → 403) + `metered_compute` yield-dependency (atomic credit debit → 402, idempotency-key header, refund-on-failure). 6 compute routes + 7 Tier-2 writes (entitlement-only).
- **Decisions CLOSED:** D1 idem-key header (YES) · D2 fresh-key-after-refund (YES) · D3 no streaming → `/markov/chat` in the 6 (substrate-anchored, ET-1.W grep) · D4 firestore prod (substrate-anchored at revision `00076-deq` + boot assertion).
- **Comms Contract v1.5** ratified (c: accept + defer cleanups). Constraint-Geometry clause folded (§§3.4,4.3,4.4,7.2,7.3).

## In-flight (open S_p)
| FRAGO | Owner | Status |
|-------|-------|--------|
| `ET1-FLOOR-COMMIT-01 + push` | ET-1.W | **CLOSED-GREEN** (verified pushed @ ece5b3b) |
| `COW1-D1-ARTIFACT-01-v2` | COW-1 | **BUNDLE DELIVERED + byte-verified** → `ClarityOS_command_staging/d1_patch/bundle/` |
| `ET1-D1-PATCH-VALIDATE-01` | ET-1.W | Stage 0 PASS; **Stages 1–3 HALTED** pending bundle transfer + base confirm |
| `CLEANUP-TRIO-01` | CT-3 | inflight — Snapshot Contract v0.2, §4.4/§8 text, Doctrines #98/#99 |
| D-error-25 (COW stale-COP) | CT-1 | proposed α; not yet in ledger (gap at 25 real) |
| D-init-guard | — | next D-series structural item, after D1 |

## D1 bundle — byte-identity (verified round-trip)
Location: `ClarityOS_command_staging/d1_patch/bundle/` — `.patch`, `app.py.final`, `users_store.py.final`, `MANIFEST.sha256`, `test_d1_entitlement_credit.py`, `BUNDLE.md`.
```
PRE  app.py dfb1cb73…6197b8   users_store.py 5937226e…d79c620
POST app.py 100d5ba1…1143a8   users_store.py 467f1e18…ca24d02
patch 2d9770dd…571840
```

## Open adversarial items (test-coverage, not substrate)
1. **422 + yield-dependency:** does `metered_compute` leave a charge when body validation fails? (Test 5 is the proof surface.)
2. **Concurrency:** two-parallel-calls Firestore-emulator test before go-live. CT-1 to dispose pre-commit vs pre-go-live gate.

## Resume hooks (next session)
1. CT-1 → ET-1.W one-liner: **base = `main @ d8e44ba`** (NOT origin 196683c; NOT `ops/ledger-floor`); fork `feat/d1-entitlement-credit-debit`.
2. **Transfer the 6 bundle files** to ET-1.W's read surface (CT-2 recommends a `d1_bundle_transfer` mirror, symmetric with the ledger-floor review copy).
3. ET-1.W: **PRE-hash gate → `git apply` → POST-hash gate → `import app` → pytest (+ emulator concurrency) → scoped signed commit → STOP** at 3-way push gate.
4. Dispose the two adversarial-test gates (422, concurrency).
5. Then: CLEANUP-TRIO-01, then D-init-guard (next D-series).

## Posture at pause
COW-1 read-only/advisory, idle. Floor pushed. D1 bundle delivered + byte-verified, awaiting transfer+apply. No mutations to canonical substrate by COW-1 this session. `main` untouched; `ops/ledger-floor` at `ece5b3b` (pushed).
