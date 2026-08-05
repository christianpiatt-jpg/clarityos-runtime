# K3 Session Snapshot — 2026-07-31 ~14:52 EDT (restore point)
*Projection, not canonical. Compiler: Kimi K3 (witness lane, read-only/advisory).*
*Base: repo `C:\ClarityOS_Code` @ `868508c`, branch `campaign/metered-compute-gate-2026-07-23`.*
*Serving: `clarity-engine-00119-gas` (deploy-a2), code `2fd2ae9` + env-only changes.*
*Ledger reference: local `ops/ledger-floor` (D-error-26..29 CLOSED; D-error-30 free at time of draft).*

## Session arc (what happened, one line each)
1. Background doc drafted → v0.2 after three mermaid design records folded in
   (`ClarityOS_ClarityEngine_Background_SocialThermodynamics.md`; sources in `source_docs/`).
2. Felt-gap allowlist (`868508c`) verified at pin — 1 seam, exclusion intact, 7/7 gate table PASS, committed inert.
3. Mint-500 dispatch (MC-20260731-1056): K3 witness-lane read named `INVITE_HMAC_SECRET` missing
   as leading cause + orphan-write forensic signature. Converged with COW-1; ground truth confirmed both.
4. Deploy A executed: secret v1 (13 bytes — too short, second failure) → v2 (64 chars) →
   `00118-rub` → `00119-gas` (deploy-a2) → first mint (`mvEbXfQTqaMyc0G-Mn25mQ`) →
   first redeem (`piattjd2017@gmail.com`, founder_exception, `op_kWR-76Yg5IQ2LPO6`). **CLOSED-GREEN.**
5. D-error-30 case study drafted (Doctrine #97, case #30), PROPOSED, awaiting CT-1 routing
   to ET-1.W for ledger append (`ops/ledger/dispositions.jsonl`, signed commit).

## Open S_p (work in flight at snapshot)
| Item | State | Next act | Owner |
|---|---|---|---|
| **Deploy B — felt-gap enablement** | checklist delivered, NOT started | source deploy @ `868508c`, tagged 0%, env `CLARITYOS_FELT_GAP_READER_ENABLED=1` + `CLARITYOS_FELT_GAP_ALLOWLIST=piattjd2017@gmail.com`, smoke, traffic shift | pen (CT-1 gate) |
| ⚠ Deploy B precondition | LOAD-BEARING | serving image = `2fd2ae9`, allowlist code NOT in it; flipping the flag on current image analyzes EVERYONE except fixture | — |
| D-error-30 append | drafted, pending routing | ET-1.W writes under CT-1 authorship; re-verify next-free-id vs origin tip | ET-1.W |
| Traffic-split confirm | one read | `gcloud run services describe clarity-engine --format='value(status.traffic)'` → expect 100% `00119-gas` | pen |
| Orphan count | expect 2 (one per logged 500) | Firestore invites-collection read; KCnlrdozdsIY3Ts2ojoQlQ confirmed, second predicted | ET-1.W |
| `INVITE_BASE_URL` unset | side-catch logged in D-error-30 evidence | env-only revision setting `CLARITYOS_INVITE_BASE_URL=https://clarity.pro-mediations.com`; may ride a later deploy; possible one-line disposition | pen |
| Part-2 reorder (sign-before-write) | verified safe, optional | rides a future normal deploy; keep OUT of Deploy B | ET-1 |
| Secret v1 (13-byte dead letter) | inert | `gcloud secrets versions disable 1 --secret=invite-hmac-secret` (optional, after Deploy B) | pen |

## Hygiene register (captured, not scheduled)
- Duplicate Secret Manager pairs (`ANTHROPIC_API_KEY`/`Anthropic_Access`, `clarityos-admin-pw`/`clarityos-admin-password`, `STRIPE_WEBHOOK_SECRET`/`clarityos-stripe-webhook-secret`, `Gemini_Acess` [sic]) — naming drift cost one failed deploy today.
- Four legacy Cloud Run services idle (`clarityos-api-v0-2`, `clarityos-web-v0-2`, `clarityos-pocket-v0-3`, `sos-v1`).
- Four modified-unstaged files in working tree (`.gcloudignore`, `deploy.bat`, `deploy.sh`, `docs/deployment.md`) — diff-inspect `deploy.sh` before any source deploy.

## Standing constraints (carried forward)
- Fixture exclusion absolute (`soldierslawyer@gmail.com`, unconditional, wins over allowlist — proven 7/7 at pin).
- Piatt v. Collins freeze absolute.
- K3 lane: read-only/advisory; drafts and verifies, never writes substrate, never holds state acts.
- Pre-traffic gates: secret length (`wc -c`), tag-URL smoke, `COMMIT_SHA` verify — BEFORE any traffic act.
- Key permanence: `invite-hmac-secret` v2 is permanent; rotation invalidates all outstanding invites.

## Resume hooks (next session, in order)
1. Confirm traffic 100% on `00119-gas` (one describe read).
2. Deploy B pre-flight: working tree @ `868508c`, diff-inspect the 4 modified files, then source deploy tagged 0% (Part-2 reorder stays out).
3. Verify Deploy B env on tagged revision, smoke, gate the traffic shift.
4. Acceptance: arc_record for `piattjd2017@gmail.com` only; admin turn writes nothing; fixture excluded.
5. Route D-error-30 to ET-1.W; close orphan count; optional: disable secret v1, set `INVITE_BASE_URL`.

## Posture at snapshot
K3 idle, read-only. Deploy A green and closed. Deploy B checklist staged, awaiting pen's gate.
No mutations to canonical substrate by K3 this session. Working tree @ `868508c` untouched except
untracked additions: `source_docs/`, `snapshots/`, background doc (all K3 staging, non-canonical).
