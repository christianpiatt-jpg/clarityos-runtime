# ET-1 RESTORE POINT · 2026-08-24 17:55 EDT / 21:55Z

**Lane:** ET-1.W · **Branch:** `campaign/metered-compute-gate-2026-07-23`
**Tip at capture:** `fe2fcea` · 10 commits ahead of origin, pushed this session
**Safety branch:** `pre-redact-backup-2026-08-24` → `526a8b1` (pre-rewrite history, local only)

---

## 1 · HISTORY REWRITE — read this first

`e2e0d91` carried a **plaintext `INVITE_HMAC_SECRET`** at line 37 of
`snapshots/east4-service-2026-08-22.yaml`. The repo is **public**. The commit was
rewritten before any push.

```
e2e0d91  →  d74bc98   (redacted, amended)
9c39db5  →  f30524a   (rebased)
526a8b1  →  fe2fcea   (rebased)
```

Verified across all 10 commits in the push range: **0 occurrences** of the literal.
The value remains live in Secret Manager under `project-afdae2c0-0f5c-454d-a4d`;
only the repo copy was redacted. Original history preserved locally at
`pre-redact-backup-2026-08-24`.

**How it got in:** the pre-commit scan tested `sk_live|sk_test|whsec_|BEGIN PRIVATE`.
A bare 32-char HMAC key matches none of them. **A denylist of known prefixes cannot
see a key you didn't anticipate.** Any future config export needs the inverse test —
flag every `value:` under `env:` and justify each one.

---

## 2 · SHIPPED THIS SESSION

| Commit | What |
|---|---|
| `d74bc98` | east4 service pre-image, redacted |
| `f30524a` | OperatorWelcome module + Layout A1–A4 fixes |
| `fe2fcea` | `Cockpit.tsx` class rename — grid collision |

Earlier in range: the door (`Home.tsx`), the recovered provider patch,
`.gcloudignore`, v87 fail-closed 409.

**Deployed:** `index-UHmUTqGL.js` / `index-CEaHEqfl.css` to
`gs://clarityos-web-founding-os`, CDN invalidated, verified `Age: 0`.
**The collision fix `fe2fcea` is NOT deployed** — committed only.

---

## 3 · THE GRID COLLISION — measured, not inferred

`routes/Cockpit.tsx:62` applied `className="cockpit"` a second time inside
Layout's `<main>`. Measured in the live DOM, same nesting, both classes:

```
.cockpit       grid · cols 220px 1060px · container 1280px in a 1060px pane
               child 1: 220px   <- OperatorWelcome landed here
               child 2: 1060px
               child 3: 220px

.cockpit-page  block · cols none · container 1020px
               children: 1020px each
```

Two symptoms, one class: first child crushed to rail width, and `width:100vw`
overflowing the pane by 220px. **Exactly two files carried the class** — the
third-file UNK is closed. No CSS added for `.cockpit-page`; styling is a
separate loop.

---

## 4 · OPEN — needs a ruling

1. **Deploy `fe2fcea`** — the collision fix is committed and not shipped.
2. **`/enter/` still 404s.** A2 blocked across five envelopes on one thing:
   `list_connected_browsers` → `[]`. No wp-admin session has ever reached this lane.
3. **R-4 / R-5** — the Stripe webhook registration and what
   `price_1TYDrfGgUU05AeM681Ybd7hU` actually costs. Both gate promotion of a
   live-mode buy path. `BILLING_MODE=stripe`, `STRIPE_MODE=live`, measured.
4. **Wire 1** — `runtime_persistence` Firestore backend. Diff described, not written.
5. **Source maps + 4 unreferenced bundle generations** public in the SPA bucket.
6. **`_audit/provider_connectors.patch`** still public; `0c3726d`'s message says
   it was removed. Record and object disagree.

---

## 5 · CARRY — findings worth more than the tasks

**One instrument-shape failure, four instances, one week.** A gate that cannot
touch what it tests: `services list` couldn't measure request count · a `*_store.py`
glob couldn't see `memory_vault` · a prefix denylist couldn't see an HMAC key ·
`?cb=` bypassed the rule, not the cache. Different lanes, same shape.

**The intake path carries structure and drops content.**
`model_router.py:1083 _shape_prompt_from_intent` emits six metadata fields by
explicit contract — *"no raw payload text passthrough"* — and the sixth is a key
*count*. The operator's text never reaches the model. Same root explains the
identical runtime summaries and the engine mislabel.

**`extended_reasoning` is TSI-gated, not score-gated.**
`intelligence_kernel.py:1305`: `tsi > 80 → extended_reasoning` regardless of
EL/INS. One record per thread → TSI 100 → that label for the first analysis of
anything. The scores displayed beside it were never consulted.

**Wire 1's named source files are archived and empty of mechanism.**
`Engine/state/session_state.py` is a 32-line dataclass with no persistence;
`Engine/utils/working_memory_bridge.py` is 8 lines whose store is `print()`.
Neither ships. The port has no source — `vault_store.py` is the template.

**east4 retired.** Service deleted 14:27Z, export banked. Project, Firestore,
4 buckets, 5 secrets, 3 other services all intact and still billing.
Production vault secret **differs** from east4's — anything written under east4
was already unreadable, and amounted to one May probe doc.
