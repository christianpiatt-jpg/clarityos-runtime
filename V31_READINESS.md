# ClarityOS v31 — Billing Finalization + PaymentIntents Readiness Report

**Build:** `20260506300000`
**Backend version:** `2.7`
**Status:** Ready — mock-mode default, stripe-mode wired and gated on env.

This pass swaps the v30 inline-charge model for a real PaymentIntent
flow (create → client confirms → webhook lands the side effect),
adds the billing state machine + 24-hour renewal scheduler with the
3-retry / 72-hour grace policy, and ships the corresponding UI on
both web and phone.

All **122 tests pass** under in-memory backends + mock billing
(27 new v31 tests).

---

## 1. Stripe PaymentIntents (real billing)

### `billing_intents.py` (new)
The PaymentIntent lifecycle lives entirely in this module so the rest
of the app talks through three functions:

```python
create_payment_intent(user_id, amount, description, kind, metadata=None) -> dict
confirm_payment_intent(intent_id) -> dict      # mock-only test helper
handle_payment_webhook(event) -> dict          # idempotent dispatcher
```

Validates inputs (`bad_user`, `bad_amount` ≥ $0.50 / Stripe min,
`bad_description`, `bad_kind`). The `kind` must be one of
`{membership_activation, membership_renewal, g_credit_single, g_credit_pack}`.

Modes:
* **mock** (default) — synthesizes `pi_mock_*` ids and `pi_mock_*_secret_*`
  client secrets. Honours `CLARITYOS_MOCK_AUTO_CONFIRM=1` (default) so
  legacy callers (v30 tests, web/phone in dev) get inline confirmation.
* **stripe** — calls `stripe.PaymentIntent.create(...)` with the kind +
  metadata + description; returns the real `id` + `client_secret`. Server
  never confirms in stripe mode.

### Idempotent webhook handling
`handle_payment_webhook` looks up the intent by id and:
1. Bails if the recorded status is already in the terminal state for the
   incoming event (`succeeded` for `payment_intent.succeeded`, `failed`
   for `payment_intent.payment_failed`).
2. Otherwise updates the intent record and applies the side-effect
   exactly once (guarded by `side_effect_applied: bool`).

Side effects per kind:
* **g_credit_single** → +1 credit, `g_credit_single` transaction.
* **g_credit_pack** → +20 credits, `g_credit_pack` transaction.
* **membership_activation** → adds user to cohort, sets membership +
  `billing_state="active"` + `renewal_ts=now+30d`, transaction.
* **membership_renewal** → extends `renewal_ts +30d`, resets retry
  count, transaction.

### Failure paths
* `g_credit_*` → `failed_payment` transaction, no balance change.
* `membership_activation` → `failed_payment` transaction +
  `billing_state="failed"` (rare; user must reactivate).
* `membership_renewal` → walks the state machine (see §2).

### No content stored
Intent records hold: `user`, `kind`, `amount`, `description`,
`metadata`, `status`, `client_secret`, `mode`, `created_ts`,
`confirmed_ts`/`failed_ts`. **No prompts, scenario text, or
conversation content.** Logs are structured (event + redacted user +
intent id + amount + status); no caller-supplied text reaches them.

---

## 2. Billing state machine

States stored on the user document via
`users_store.set_billing_state`:
```
active        → paid up; renewal_ts is the next charge date
past_due      → last renewal failed; in retry window (≤ 3 attempts / 72 h)
grace_period  → retries exhausted; brief manual-recovery window
cancelled     → terminal (also sets membership_status = "cancelled")
failed        → activation never succeeded
```

Renewal-failure transitions (`billing_intents._apply_failed`):
```
active           --fail-->  past_due  (retry_count=1, retry_at=now+24h)
past_due         --fail-->  past_due  (retry_count++, retry_at=now+24h)
past_due (3rd)   --fail-->  grace_period (grace_until=now+24h)
grace_period     --t→t-->   grace_period until grace_until expires
grace_period     --expire-->cancelled (also membership_status=cancelled)
```

Retry cadence + grace window are module-level constants on
`billing_intents` for easy test tuning:
```python
RENEWAL_PERIOD_DAYS = 30
RENEWAL_RETRY_HOURS = 24
MAX_RENEWAL_RETRIES = 3
GRACE_PERIOD_HOURS = 24
```

---

## 3. Membership renewal scheduler

### `billing_renewal.py` (new)
Public API:
```python
calculate_next_renewal_ts(ts) -> float         # ts + 30 days
renew_membership(user_id, *, now_ts=None) -> dict
_renewal_one_pass(now_ts=None) -> dict         # tests drive this directly
_ensure_renewal_scheduler_started()            # lazy daemon thread
```

Behavior:
* Scans `users_store.list_users_due_for_renewal(now)` (memory backend
  iterates the dict; firestore uses a `where(renewal_ts <= now)` query).
* For each due user:
  * If `billing_state == "grace_period"` and grace window passed →
    `_terminate_membership` (cohort removal + `cancelled` flip + tx
    record).
  * Otherwise → `billing_intents.create_payment_intent(..., kind="membership_renewal")`.
* Returns `{due, intents, terminated, no_op}` counts so callers
  (and tests) can assert behavior.

Lazy boot:
* The daemon thread is started on the first `/membership/activate`
  call (or any explicit call site). One thread per Cloud Run instance,
  ticks every `RENEWAL_TICK_SECONDS` (default 24 h, env-overridable).

---

## 4. Billing history + transactions

`membership_store.record_transaction` (already in v30) is kept; v31
adds the new transaction types it produces:

```
membership_activation   → on successful activation
membership_renewal      → on successful renewal
g_credit_single         → on +1 credit purchase
g_credit_pack           → on +20 credit purchase
g_consume               → on each #G run (no payment)
membership_cancel       → on cancel (manual or grace-expire)
failed_payment          → on any failed intent
refund                  → placeholder for future use
```

`membership_store.list_transactions(user, limit)` returns newest-first.

### `membership_store` extensions (v31)
* `record_intent(record)` — persist a new intent (or replace).
* `get_intent(intent_id)` — read a single intent record.
* `update_intent(intent_id, updates)` — merge updates into existing.
* `list_intents_for_user(user, limit)` — newest-first.

In-memory + firestore backends both supported.

---

## 5. New endpoints

| Endpoint | Validation | Flag-gated | Logs |
|---|---|---|---|
| `POST /billing/intent` | amount ≥ $0.50, description non-empty, kind ∈ `VALID_KINDS` | `membership_ui_enabled` | inline + structured |
| `POST /billing/intent/confirm` | non-empty intent_id, must belong to caller | – | structured |
| `POST /billing/webhook` | mock-mode: JSON body must be a dict; stripe-mode: `Stripe-Signature` header verified via `billing.verify_webhook` | – | `billing_webhook_received` |
| `GET  /billing/history` | `limit` 1–500 | `membership_ui_enabled` | – |

All routes return the project's `error_response` envelope on failure.

---

## 6. Updated membership endpoints

### `/membership/activate`
Now creates a PaymentIntent (instead of inline-charging). Returns:
```json
{
  "ok": true,
  "pending": true | false,
  "intent": {"intent_id", "client_secret", "status", "amount", "kind", "mode"},
  "state": <full membership view>,
  "already_active"? : true,
  "waitlisted"? : true
}
```
* `pending: false` only when in mock auto-confirm mode (the side-effect
  has already landed by the time the response returns).
* `pending: true` is the production path — client confirms via
  Stripe.js (or `/billing/intent/confirm` in mock mode) and the
  webhook applies the side-effect.

### `/membership/cancel`
Now also flips `billing_state` to `cancelled` alongside the legacy
`membership_status="cancelled"`. Cohort row removed, transaction
recorded.

### `/membership/state`
New `billing` block:
```json
{
  "billing": {
    "state": "active|past_due|grace_period|cancelled|failed|null",
    "renewal_ts": <epoch>,
    "renewal_retry_count": 0..3,
    "renewal_grace_until_ts": <epoch>,
    "next_amount": 50.0
  }
}
```

### `/membership/g/buy_single` and `/membership/g/buy_pack_20`
Both now use PaymentIntents:
```json
{
  "ok": true,
  "pending": true | false,
  "balance": <int>,
  "intent": {...},
  "purchase": {"units", "amount", "intent_id", "mode"}
}
```

---

## 7. Tests

`tests/test_v31_billing.py` (new) — 27 tests. Coverage:

* PaymentIntent input validation (5 cases).
* Auto-confirm-on / auto-confirm-off behavior.
* Confirm lands credits idempotently.
* Failed intent transitions (`active → past_due → grace_period`).
* `calculate_next_renewal_ts` is exact at +30 days.
* Renewal scheduler:
  * Picks up due users and creates intents.
  * Terminates members past the grace window.
  * Skips not-due users.
* `/membership/activate`:
  * Returns `pending: True` in manual-confirm mode.
  * Webhook landing flips status to `active` + sets `renewal_ts`.
  * Failed webhook records `failed_payment`, `billing_state=failed`.
  * Duplicate webhook events are no-ops (cohort active_count unchanged).
* `/billing/intent` + `/billing/intent/confirm`:
  * Happy path.
  * Unknown kind → 400.
  * Cross-user confirm → 403.
* `/billing/history` returns combined transactions + intents.
* `/membership/g/buy_*` async-path:
  * Pending until webhook fires.
  * Failed payment leaves balance at 0 + records `failed_payment` tx.
* `/membership/cancel` flips `billing_state`.
* Webhook receiver:
  * Auth contract for /billing endpoints.
  * Non-dict body → 400.
  * Unknown intent → 200 (Stripe stops retrying).

`tests/conftest.py` updates:
* `CLARITYOS_BILLING_MODE=mock` and `CLARITYOS_MOCK_AUTO_CONFIRM=1`
  set as test defaults.
* `manual_confirm` fixture — flips auto-confirm off so a test can drive
  the async webhook flow.
* `membership_store` reset hook (clears intents map).

`tests/test_v30_membership.py` and `tests/test_v28_endpoints.py`
updated for the new contract:
* Activate response no longer has `body["billing"]`; checks `body["intent"]`.
* Health version bumped to `2.7`.
* Transaction type for credit purchases is now `g_credit_single` /
  `g_credit_pack` (was `g_buy_single` / `g_buy_pack_20`).

Total: 122 tests passing.

---

## 8. Web UI — billing

New components under `web/src/components/membership/`:
* **`PaymentModal.tsx`** — generic intent confirmation dialog. Renders
  amount + kind + mode + intent_id. In mock mode shows an info banner
  explaining the synthetic-webhook path; in stripe mode shows a
  placeholder for Stripe Elements (`client_secret` displayed for
  diagnostics only).
* **`RenewalStatusCard.tsx`** — billing-state badge + next renewal
  date + retry count + grace deadline + "Update payment method"
  placeholder button (disabled — flagged as future work).
* **`BillingHistoryPanel.tsx`** — two tables: transactions (with
  human-readable type labels) and payment intents (with status badge).
  Has its own refresh + error handling.

Updated:
* **`MembershipPage.tsx`** — composes `RenewalStatusCard` between
  status + credits panels; mounts `BillingHistoryPanel` at the bottom;
  surfaces `PaymentModal` whenever an action returns
  `pending: true`. Tracks busy state across activation, cancellation,
  credit purchases, and intent confirmation.
* **`useMembership.ts`** — `activate` now returns the full
  `ActivateResult` (so the page can branch on `pending` + `intent`).
  Added `confirmIntent(intent_id)` that calls
  `/billing/intent/confirm` and refreshes state.
* **`lib/api.ts`** — added `V31BillingState`, `PaymentIntentView`,
  `BillingHistoryIntent`, `ActivateResult`, `PurchaseResult` (now
  with `pending` + `intent`), and the three v31 helpers.

`tsc --noEmit` exit 0.

---

## 9. Phone UI — billing

New screens under `phone/app/`:
* **`billing.tsx`** — full billing view: state badge + renewal
  metadata + transactions list + intents list. Pull-aware refresh +
  error states.

Updated:
* **`membership.tsx`** — adds the **"Billing"** card with renewal
  status badge + next-renewal-ts, links to `/billing`. Now shows the
  PaymentConfirmModal whenever activation returns a pending intent;
  same flow as web.
* **`useMembership.ts`** — mirrors web: `activate` returns
  `ActivateResult`, `confirmIntent` added.
* **`lib/api.ts`** — v31 types + `billingCreateIntent` /
  `billingConfirmIntent` / `billingHistory` helpers.

The `PaymentConfirmModal` is colocated in `membership.tsx` to keep the
diff small; the web app's `PaymentModal` is the canonical version.

`tsc --noEmit` — only the pre-existing
`ingest.tsx` ProviderId error remains (unrelated to v31).

---

## 10. Files touched

**New**
* `billing_intents.py`
* `billing_renewal.py`
* `tests/test_v31_billing.py`
* `web/src/components/membership/PaymentModal.tsx`
* `web/src/components/membership/RenewalStatusCard.tsx`
* `web/src/components/membership/BillingHistoryPanel.tsx`
* `phone/app/billing.tsx`
* `V31_READINESS.md` (this file)

**Modified**
* `app.py` — v31 imports, /billing/* endpoints, membership endpoints
  use intents, /me unchanged (already exposes membership view), version
  bump, what's-new entry, root catalog.
* `membership_store.py` — intent record/get/update/list helpers + new
  `_INTENT_COLL`.
* `users_store.py` — `set_billing_state`, `get_billing_state`,
  `list_users_due_for_renewal`, extended `get_membership_view`.
* `tests/conftest.py` — billing-mode env defaults, `manual_confirm`
  fixture, membership_store reset.
* `tests/test_v30_membership.py` — updated for new activate response
  shape + transaction type names.
* `tests/test_v28_endpoints.py` — bumped version assertion.
* `web/src/lib/api.ts` — v31 types + helpers; `MembershipStateView`
  extended with `billing` block.
* `web/src/hooks/useMembership.ts` — activate returns full result;
  `confirmIntent` added.
* `web/src/routes/MembershipPage.tsx` — wires the three new
  components + payment modal.
* `phone/lib/api.ts` — same as web for phone.
* `phone/lib/hooks/useMembership.ts` — mirrors web hook.
* `phone/app/membership.tsx` — billing card, payment modal,
  renewal badge.
* `BUILD_VERSION` — bumped to `20260506300000`.

---

## 11. Rollback path

v31 is purely additive on the database side; no migrations.

To revert:
1. Set `CLARITYOS_BILLING_MODE=mock` and `CLARITYOS_MOCK_AUTO_CONFIRM=1`
   (the launch defaults). All flows remain functional with mock
   billing, no money moves.
2. To disable the webhook + intent flow entirely, redeploy without the
   `billing_intents`/`billing_renewal` imports — the v30 inline-charge
   path can be restored from git.
3. Existing user docs gain extra fields (`billing_state`, `renewal_ts`,
   etc.) that are ignored by the v30 code — safe to leave in place.

---

## 12. Known gaps / next-pass candidates

* **Stripe stripe-mode integration testing** — the code path is wired
  but the test suite runs in mock mode only. Before enabling stripe
  in production, run a manual integration pass with a Stripe test key.
* **Update Payment Method** — the button is rendered but disabled. v32
  should wire Stripe Customer + PaymentMethod plumbing so users can
  swap cards from the UI when in past_due / grace_period.
* **Refund flow** — the `refund` transaction type is reserved but no
  endpoint exists. Add when ops needs to issue a manual refund.
* **Webhook retry storage** — if a Stripe webhook fails our handler we
  return non-200 and Stripe retries automatically. We don't currently
  buffer or de-duplicate at the network layer; the side-effect-applied
  flag handles dedup at the store layer.
* **Activation cap race** — there's still a small window where two
  users can both pass the `is_cohort_full` check, both create intents,
  and both confirm — net result: cohort active_count = cap+1. The
  webhook handler defends against this by recording `failed_payment`
  + `billing_state=failed` and not joining the second user, but the
  intent has already moved money. v32 should reserve a slot at intent
  creation and refund on failure.
* **Renewal scheduler observability** — currently logs only on passes
  with non-zero activity. Adding a heartbeat log would make outage
  detection easier.
