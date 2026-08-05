# COW-1 Wiremap — Map-to-Fix Punch List (code-side, read-only)
*FRAGO-D · COW-1 · 2026-06-18 · repo `clarityos-runtime`, working-tree reads*

**Scope:** in-repo code-side of the money path + enforcement points (Condition 2). Read-only.
Each node marked **✅ healthy / ⛔ defect / 🔑 needs-credential** (latter is out of code-side scope).
Evidence: **T-SUBSTRATE** = read at `file:line`; **T-STRUCTURAL** = inference.
**Hard stop (Condition 1):** this is a diagnostic map → fix list. It ends at the fix list. No
instrumentation engine / auto-reconcile / HQ console without a separate CT-1 gate.

---

## Headline — launch-blocker

### D1 ⛔ Entitlement is computed but never enforced on value-delivery routes (confirms D-recon-G-1)

- **Engine routes gate on `require_session` only — no entitlement check:**
  `/markov` `app.py:8364`, `/galileo` `8373`, `/library` `8382`, `/tizzy` `8391`,
  `/markov/chat` `8028`, `/engine/v1/run` `11539`. *(T-SUBSTRATE)*
- **`require_session`** (`app.py:553-579`) validates session existence/expiry and surfaces
  `cohort` — it reads **no** `billing_state` / `membership_status` / entitlement. *(T-SUBSTRATE)*
- **Engine handler bodies** (`app.py:8364-8398`) call the adapter directly; no internal gate. *(T-SUBSTRATE)*
- **`entitlement_view.compute_entitlement_view`** is computed but **consumed only by display
  endpoints** (`app.py:13433`, `13448`; the comment at `13419` even says "consume to gate
  access" — the intent was never wired to the engines). *(T-SUBSTRATE)*
- **Impact:** any valid session — free tier, expired, cancelled, or past_due — can invoke paid
  engine compute. Revenue is recorded but not enforced.
- **Systemic, not just engines:** authenticated user-data writes gate on session only too —
  `/library/write` `2263`, `/vault/write` `2119`, `/timeline/write` `2371`,
  `/markov/state/update` `2835`. The entitlement gate exists **nowhere** as a dependency. *(T-SUBSTRATE)*
- **Fix sketch:** add one dependency `require_active_entitlement` = `require_session` +
  `compute_entitlement_view(user).active` (raise 402/403 on inactive), and apply it to the
  engine + metered routes. One new dependency, ~a dozen decorator edits. Decide per-route
  whether a free-tier allowance applies.

---

## Provisioning side — healthy

- **P1 ✅ Webhook `/billing/webhook`** `app.py:1408` — v42-hardened (signature verify,
  seen-event dedup, mode/livemode match). *(loci T-SUBSTRATE; hardening corroborated by CT-2 deep-read + RECON-F)*
- **P2 ✅ Billing-state writes** — the four Stripe event handlers set `billing_state`
  active/past_due/cancelled via `users_store.set_billing_state` (`1665`, `1696`, `1728`,
  `1745`, `1764`). Provisioning records entitlement correctly. *(T-SUBSTRATE)*
- **P3 ✅ Join-key = email** (RECON-F) — webhook resolves buyer email → provisions passwordless
  shell. *(T-SUBSTRATE, prior)*

> The provisioning half *writes* state correctly. The defect is purely that enforcement never
> *reads* it on value routes. The plumbing is sound; the valve is missing.

---

## Needs-credential — out of code-side scope (ET-1.W + read-only keys)

- **🔑 Stripe live config** — checkout session mode, enabled webhook events, payload/metadata
  (checkout is at Stripe, confirmed by CT-1). → ET-1.W via **read-only** Stripe key.
- **🔑 WP runtime state** — actual role/membership records, duplicate-customer reality,
  `user_has_active_membership()` live behavior. → ET-1.W **read-scoped** WP.
- **🔑 Cloud Run env audit** — live env vars. → ET-1.W `gcloud` read.

---

## Ranked fix list (for launch)

1. **D1 (blocker) — enforce entitlement on engine + metered routes.** This is the revenue leak;
   it is the single most launch-relevant fix in the whole map.
2. *(pending credentialed pass)* duplicate-customer handling and stale-session / role hysteresis
   — confirm via the Stripe + WP recon, then rank against D1.

**Map-to-fix verdict:** the code-side money path is healthy on provisioning and broken on
enforcement. Closing D1 is the launch requirement; the rest is confirm-and-rank after the
credentialed half runs.
