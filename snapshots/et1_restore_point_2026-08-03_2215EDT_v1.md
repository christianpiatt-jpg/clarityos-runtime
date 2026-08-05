# ET-1.W restore point — 2026-08-03 22:15 EDT

Set on pen's instruction ("set restore point here"). Read-only capture plus one local
annotated git tag. No commit, no push, no deploy, no traffic act, no Firestore write.

Pin label: `restore/2026-08-03-2215edt-motion11-prefire`
Captured: 2026-08-03 22:15:43 EDT / 2026-08-04T02:15:43Z

---

## 1. Git

| field | value |
|---|---|
| local HEAD | `ae221b68ddc9c0eb176de97e46b0a03f6ae9d41f` |
| branch | `campaign/metered-compute-gate-2026-07-23` |
| remote branch head | `ae221b6` — converged 0/0 with local |
| `origin/main` | `75b0f701a2acd72cac4376d67ade48775b904ad8` (behind; campaign branch is the working line) |
| tracked modifications | **NONE** — working tree == `ae221b6` for all tracked content |
| untracked entries | 17 (inventory in §5) |
| restore tag | `restore/2026-08-03-2215edt-motion11-prefire` (annotated, **local only — not pushed**) |

Recent line: `ae221b6` <- `868508c` <- `857ece6` <- `2fd2ae9` <- `ee3297f`

## 2. Cloud Run — service `clarity-engine`, project `founding-os`, region `us-central1`

| tag | revision | traffic | image digest | COMMIT_SHA |
|---|---|---|---|---|
| `feltgap` | `clarity-engine-00092-h9r` | 0% | `sha256:87a23ace…f3a` | `2fd2ae9` |
| `deploy-a2` | `clarity-engine-00119-gas` | 0% | `sha256:87a23ace…f3a` | `2fd2ae9` |
| **`b1-verify`** | **`clarity-engine-00122-sir`** | **100% (SERVING)** | `sha256:f3c17173…efb` | `ae221b6` |
| `b2-verify` | `clarity-engine-00124-yib` | 0% | `sha256:f3c17173…efb` | `ae221b6` |

`latestReadyRevisionName` = `clarity-engine-00124-yib`
Service URL: `https://clarity-engine-y3chr4su7a-uc.a.run.app`

Build provenance for the serving image: Cloud Build `54b4bbe7-ba0b-4685-b9bc-85b8d515fd7c`,
2026-08-01T14:08:41Z, SUCCESS, `--source` zip -> `cloud-run-source-deploy`.

`00122-sir` and `00124-yib` share one image digest; `00124-yib` differs by env only
(`CLARITYOS_FELT_GAP_READER_ENABLED=1`, `CLARITYOS_FELT_GAP_ALLOWLIST=piattjd2017@gmail.com`).

Secret binding to preserve across any redeploy: `INVITE_HMAC_SECRET -> invite-hmac-secret:2`
(present on all four revisions above). `CLARITYOS_INVITE_BASE_URL=https://clarity.pro-mediations.com`
present on `00122-sir` and `00124-yib` only.

**Traffic restore command (if traffic is later moved and must come back to this pin):**

    gcloud run services update-traffic clarity-engine --project founding-os \
      --region us-central1 --to-revisions clarity-engine-00122-sir=100

## 3. Firestore (project `founding-os`, `(default)` database)

Root collections: `_audit`, `contact_requests`, `events`, `g_debits`, `invites`,
`magic_link_tokens`, `membership_cohorts`, `membership_transactions`, `memory_vault`,
`mesh_metadata`, `sessions`, `states`, `users`, `waitlist`

| collection | count at pin | notes |
|---|---|---|
| `users` | 15 | incl. `admin`, `piattjd2017@gmail.com` (first_user / allowlisted), `christian.piatt@outlook.com`, fixture `soldierslawyer@gmail.com` |
| `invites` | 2 | `mvEbXfQTqaMyc0G-Mn25mQ` = used; `0sfPXLQR_p95RLCqTe5WyQ` = **unused, RESERVE** |
| `states` | 1 | `xcFNjcNeD5BScTwVKpAy` |

**Reserve invite `0sfPXLQR_p95RLCqTe5WyQ`** — minted 2026-08-01T19:58:04Z on the fixed
revision, expires **2026-08-08T19:58:04Z**, cohort `founder_exception`, price 0,
`billing_required: false`, inviter `admin`. Held per `K3_handoff_2026-08-03.md:50`.
This is the only unused invite and it is **not** an orphan. Deleting it is the open
cancel-recommendation against Dispatch 1B.

**Not captured here:** Firestore contents are live and mutable. This restore point records
counts and identifiers only — it is not a data backup. A `memory_vault` write (e.g. the
B-2 privacy gate) will not be undone by anything in this file.

## 4. Test baseline

    python -m pytest -m "runtime_spine or privacy_surface or determinism_surface" -q

Result at this pin: **13 failed, 667 passed, 8447 deselected** (211s).

All 13 reds in `tests/test_v44_model_router.py`, all `assert 403 == 200` (metered_compute
entitlement gate), pre-existing since `8ea13b5`. Documented baseline: `K3_handoff_2026-08-03.md:47`
— **any 14th red = stop.**

## 5. Untracked inventory at pin (NOT covered by the git tag)

```
ClarityOS_ClarityEngine_Background_SocialThermodynamics.md
SPEC_READER_GROUNDING_v0.1_DRAFT.md
analysis/trace_state_distribution_reconciliation_2026-08-03.md
bucket-before-phase4.txt
command_structure/
drafts/
et1_prod_env_reads_return_2026-07-08_1220EDT_v1.md
et1_public_base_url_reconciliation_return_2026-07-08_1526EDT_v1.md
lb_snapshot_20260604_154124/
phase5a_engine_before.yaml
phase5a_rollback_revision.txt
preflight-4b-prestate-2026-06-07T1121-EDT.yaml
preflight-4b-users-admin-predelete-20260607T153829Z.json
review_packets/
snapshots/
source_docs/
specs/D1_CT2_REVIEW.md
```

Includes `SPEC_READER_GROUNDING_v0.1_DRAFT.md` (content is v0.2) and the whole `snapshots/`,
`drafts/`, `command_structure/`, `review_packets/`, `source_docs/` trees.

## 6. What this restore point does and does not cover

Covered — exactly restorable:
- Tracked source at `ae221b6` via `git checkout restore/2026-08-03-2215edt-motion11-prefire`
- Cloud Run traffic split (command in §2); all four revisions exist and are `Ready`

Not covered:
- **Untracked files** (§5) — a git tag does not protect these. `git clean` or a hard reset
  with `-x` would destroy them. If durable protection is wanted, they need a commit or an
  out-of-tree copy; say the word.
- **Firestore data** — counts recorded, contents not backed up
- **Secret Manager versions** — bindings recorded, secret material not captured
- Anything on the two `.claude/worktrees/` copies

## 7. Open state carried into this pin

Pen holds (unchanged):
- Motion 11 v2 Feeds 1-3 dispatch — **composed, NOT fired**; three §A prerequisites open
- Dispatch 1B (invite deletion) — cancel recommended, unactioned
- Dispatch 2 — rewrite-or-close, unactioned (both dispatches were 07-31-substrate)
- B-2 privacy gate — `00124-yib` armed @ 0%, two-turn rule, `arc_records.` prefix under
  `memory_vault/{user_id}/entries/`; expect 1 key first_user, 0 admin
- Motions 8/9/10 (Recons 1-3) — shape-registered, no go taken
- Traffic-flip authorization — separate from any deploy

ET-1.W witness catches open against the Motion 11 v2 dispatch (C-1 through C-6), of which
**C-1** (mock default specified as `False`; codebase is 3x`True` vs 1x`False`, and `False`
renders absence as presence) and **C-3** (`test_reason_enum_closed` unsatisfiable — `Literal`/
`TypedDict` are static-only) are spec defects that change what Phase 1 ships.

Fixture `soldierslawyer@gmail.com` untouched. Piatt v. Collins freeze 2026-07-15 -> 2026-09-30
in place.
