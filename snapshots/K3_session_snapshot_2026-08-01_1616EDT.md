# K3 Session Snapshot — 2026-08-01 ~16:16 EDT (restore point)
*Projection, not canonical. Compiler: Kimi K3 (witness lane). Supersedes K3_session_snapshot_2026-07-31_1452EDT.md.*
*Serving: `clarity-engine-00122-sir` @ 100% (commit `ae221b6`, pushed) · rollback `00119-gas` armed @ 0%.*

## Closed
- **Deploy A (invite path)** — 7/31. Secret v2 (64 chars), first mint, first redeem (`piattjd2017@gmail.com`, founder_exception, `op_kWR-76Yg5IQ2LPO6`).
- **B-1** — 8/1. Live now: Module B fix (`857ece6`), felt-gap allowlist code (`868508c`, **flag OFF, inert**), `INVITE_BASE_URL=https://clarity.pro-mediations.com`, admin auth recovered (stored hash == mounted secret `clarityos-admin-password:3`, wire manually closed).
- **Provider check** — green: real `openai:gpt-5.4` turn through the full thread path. Engine works end-to-end.

## Open — B-2 (three steps, no unknowns)
1. Env deploy: `CLARITYOS_FELT_GAP_READER_ENABLED=1` + `CLARITYOS_FELT_GAP_ALLOWLIST=piattjd2017@gmail.com` — `--update-env-vars` (NEVER `--set-`), tagged, 0% traffic. Expect literals 15→17, secrets untouched; verify count on tag.
2. Privacy gate on the tag: first_user turn → `arc_record` written; **admin turn (silent control) → nothing**. Firestore read on `arc_records` settles both. Both required.
3. Cut traffic → first real `arc_records`.

## Register (standing facts)
- **Control account = admin.** Non-fixture, off-allowlist, proven capable. Invite `0sfPXLQR_p95RLCqTe5WyQ` in reserve.
- **`/provider-health` untrusted.** openai leg falsified by real turn; anthropic/gemini unverified. Fix-or-annotate candidate.
- **Threads path is session-only** (`app.py:12433`) — no entitlement/credits needed for B-2 turns. Engine routes (`/model/complete` etc.) remain metered; credit grant returns when the showing moves past Threads.
- **Test sweep baseline:** 13 known-red in `tests/test_v44_model_router.py` (pre-existing from `8ea13b5`, gate working vs stale tests). Any 14th failure = stop.
- **Login throttle:** 5 attempts / 900s (`app.py:1075`). Never guess credentials.
- **Admin secret carries a trailing newline (49 bytes).** Never hash raw secret bytes — strip first (8/1 trap, caught pre-login).
- **`_bootstrap_admin` latent wire** (`app.py:429-436`): env password never reconciles to stored hash on boot. Manually closed 8/1; disposition candidate (reconcile-on-boot vs refuse-and-log).
- **`tokens.py:30` merges absence+invalidity** in one error — forces env reads to discriminate. Design corollary logged.
- **NODE/WIRE doctrine** saved as durable method. Corrections folded: #11 was a false positive (rule catching its own author); #13/#10 merged NODE (`REDACTED` sent literally); #8 WIRE-supported (pages send email, envelope carries `op_…`).
- **Rule-1 violations this week: 3** (provider keys, Kimi's metered-endpoint inference, +1). The doctrine catches its own authors — working as designed.
- **Fixture exclusion absolute** — `soldierslawyer@gmail.com` unconditional, wins over allowlist (proven 7/7 at pin). Piatt v. Collins freeze absolute.

## Pending queue (not scheduled)
- D-error-30 (mint-500 saga) — drafted, awaiting CT-1 routing to ET-1.W ledger append.
- Orphan count confirm (expect 2) — Firestore read, ET-1.W.
- Disable invite secret v1 (13-byte dead letter).
- Admin secret twin (`clarityos-admin-pw`, May 16) — dead weight; delete after confirming nothing references it.
- Duplicate secret pairs + 4 legacy Cloud Run services — hygiene disposition.
- Invite reorder (sign-before-write) — verified safe; rides a future deploy.
- Stale v44 tests — update to provision entitlement; restores sweep as clean go/no-go.

## Resume hooks (next session)
1. Execute B-2 step 1 (env deploy, tagged 0%) → verify literal count 17 + secrets 25/25 on the tag.
2. Privacy gate: two turns (first_user, admin) → Firestore `arc_records` read → expect exactly 1 (first_user's).
3. Cut traffic. B-2 closed.
4. Route D-error-30.

## Posture
K3 idle, read-only. No canonical mutations by this lane. Untracked staging only: `source_docs/`, `snapshots/`, background doc.
Week state: inside + method advanced; engine proven live with a real model; B-2 three steps from first real arc_records.

**Late entry (16:41):** first live EP-panel return archived — `source_docs/EP_live_return_first_worked_example_2026-08-01.png` (admin thread, single-sample; independent-convergence read logged). Note: that thread is the *control* — B-2 acceptance turns come from first_user only.
