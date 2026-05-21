# Billing

## Purpose

Billing is the Stripe-integrated economic layer: it drives membership
activation and renewal, #G credit purchases, the billing state machine, a daily
renewal scheduler, and Stripe webhook handling.

## Implementation location

Repo-root modules: `billing.py` (the Stripe SDK wrapper), `billing_config.py`
(Stripe mode and key resolution, event observability — v42), `billing_intents.py`
(the PaymentIntent flow — v31), `billing_renewal.py` (the daily renewal
scheduler — v31). The HTTP endpoints are in `app.py`; persistence is on the user
record and in `membership_store`.

For the full per-module contract on PaymentIntent creation, webhook handling,
and multi-store side-effect coordination, see
[docs/billing_intents.md](billing_intents.md).

## Data model

- **Billing state** lives on the user record (`users_store`): `billing_state`,
  `renewal_ts`, `renewal_retry_count`, `renewal_grace_until_ts`.
  `VALID_BILLING_STATES` = `active`, `past_due`, `grace_period`, `cancelled`,
  `failed`.
- **PaymentIntent records** live in a separate store — `membership_store`,
  collection `membership_payment_intents`, keyed by intent id. A `kind` is one
  of `membership_activation`, `membership_renewal`, `g_credit_single`,
  `g_credit_pack`.
- **`billing_config`** holds in-process (non-durable) ring buffers: recent
  events and the seen-event set.

## Stripe mode

`billing_config.get_stripe_mode()` resolves the mode by precedence:
`CLARITYOS_STRIPE_MODE` (`test` / `live`) → the secret-key prefix
(`sk_live_` / `sk_test_`) → `disabled` when no key is set. Keys come from
`CLARITYOS_STRIPE_SECRET_KEY` / `CLARITYOS_STRIPE_WEBHOOK_SECRET` (with legacy
`STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` as a fallback). A separate flag,
`CLARITYOS_BILLING_MODE` (`mock` by default, or `stripe`), selects the runtime
path; in mock mode `CLARITYOS_MOCK_AUTO_CONFIRM` (default on) fires the success
webhook synchronously. `get_billing_status()` reports `{mode, has_secret,
has_webhook_secret, live_mode, billing_enabled, version}` and never returns the
key itself.

The two flags are **orthogonal**: `CLARITYOS_BILLING_MODE` (mock / stripe) is
the runtime-path selector consumed by `billing_intents`; `CLARITYOS_STRIPE_MODE`
(test / live) is the Stripe-environment selector consumed by `billing_config`.
Intent records carry both — a `mode` field (mock / stripe) and an `environment`
field (test / live / mock). See [docs/billing_intents.md](billing_intents.md)
for the full mode matrix.

## APIs / entrypoints

- `create_payment_intent(user_id, amount, description, kind, metadata)` —
  validates the amount (≥ $0.50) and `kind`, then calls
  `stripe.PaymentIntent.create` (stripe mode) or synthesises a `pi_mock_…`
  intent (mock mode). The record is persisted via `membership_store`.
- `handle_payment_webhook(event)` — the idempotent dispatcher for
  `payment_intent.*` events.
- HTTP: `POST /billing/webhook`, `/billing/intent`, `/billing/intent/confirm`,
  `/billing/history`, `/founder/billing/status`, `/me/billing`. Legacy invite
  billing: `/invite/{token}/checkout`, `/invite/{token}/finalize`.

## State machine

- Activation success → `active`.
- Renewal success → `active` (the retry count resets).
- Renewal failure walks `active` → `past_due` (retries remain; `renewal_ts` set
  ~24 h out) → `grace_period` (retries exhausted; `renewal_grace_until_ts`
  ~24 h out) → `cancelled` (grace expired; terminal).
- `failed` is a rare initial-activation failure (also set on a cohort-cap race).
- `cancelled` and `failed` both revoke access.

## Renewal scheduler

`billing_renewal.py` runs a lazy daemon thread — one per process, started on the
first activation. Each tick (`RENEWAL_TICK_SECONDS`, 24 h) scans the users due
for renewal. A due user whose grace has expired is terminated (`cancelled` plus
cohort removal); otherwise a `membership_renewal` PaymentIntent is created at the
user's locked price. Policy constants: `RENEWAL_PERIOD_DAYS` 30,
`RENEWAL_RETRY_HOURS` 24, `MAX_RENEWAL_RETRIES` 3, `GRACE_PERIOD_HOURS` 24.

## Webhook

`POST /billing/webhook`: mock mode accepts unsigned JSON; stripe mode requires a
`Stripe-Signature` header verified via `stripe.Webhook.construct_event` (a
missing webhook secret → 503, a bad signature → 400), and rejects a test/live
mode mismatch (400). A duplicate event id short-circuits to
`{ok: true, duplicate: true}`. `payment_intent.*` events go to
`handle_payment_webhook`; `checkout.session.completed`,
`invoice.payment_succeeded`, and `customer.subscription.updated` / `.deleted` go
to the subscription handler, which maps Stripe status onto `billing_state`.

## HTTP invariants

**Client-secret exposure**

- Returned only on intent-creation and intent-confirmation endpoints:
  `/billing/intent`, `/membership/activate`, `/membership/g/buy_single`,
  `/membership/g/buy_pack_20`, and mock-only `/billing/intent/confirm`.
- Always returned only to the authenticated owner of the intent.
- Never returned in history or read endpoints (`/billing/history`,
  `/membership/state`, `/membership/g/history`, `/me/billing`,
  `/founder/billing/status`).
- Webhook-event storage strips `client_secret` at write time.

**Metadata discipline**

- System-generated metadata is always non-PII (`intent_id`, `kind`,
  `cohort`, `units`, `reason`, `manual`, `founder`, `automated`, etc.).
- Transaction history endpoints (`/billing/history`,
  `/membership/g/history`) return raw transaction metadata.
- Callers must not put PII into metadata when creating intents, because
  transaction metadata is surfaced as-is.

**Diagnostic vs simplified UX views**

- `/membership/state` is the diagnostic view: exposes the full 5-state
  `billing_state` vocabulary (`active`, `past_due`, `grace_period`,
  `cancelled`, `failed`) and renewal internals (`renewal_retry_count`,
  `renewal_grace_until_ts`).
- `/me/billing` is the simplified UX view: collapses backend states into
  `{none, active, past_due, canceled}`.

**Founder-activation renewal boot gap**

- The renewal scheduler is lazily started by `/membership/activate` only.
- Founder-only activations (`/founder/membership/activate`) do not start
  the scheduler.
- A deployment with only founder activations will set `renewal_ts` but
  will not auto-renew until a user hits `/membership/activate`.

## Integration points

- **Auth / users** — billing state and the renewal fields live on the user
  record.
- **Membership** — a successful `membership_activation` consumes a cohort slot;
  a `membership_renewal` keeps it; #G credit intents top up the credit balance.
- **Stripe** — the only external dependency; fully bypassed in mock mode.

## Invariants

- Side effects are idempotent: a `side_effect_applied` flag plus a
  terminal-state check means credits and slots are never double-applied on a
  Stripe redelivery. The flag is set in a separate `update_intent` call AFTER
  `_apply_*` returns; if `_apply_*` partially completes and raises, the
  terminal-state check on redelivery silences retry — partial state requires
  operator-side reconciliation. See
  [docs/billing_intents.md](billing_intents.md) for the full multi-store
  failure-mode table.
- The webhook handler (`handle_payment_webhook`) **never raises** — it returns
  `{ok: False, error: ...}` envelopes on errors so the HTTP layer can always
  return 200 to Stripe and let Stripe's own redelivery retry. All other public
  functions in `billing_intents` raise `BillingError(code, message)` on
  validation or Stripe failure.
- Multi-store coordination is **best-effort** — `billing_intents._apply_*`
  writes across `users_store` + `membership_store` without transaction
  wrapping. The worst-case failure mode is cohort-slot leak via a
  `set_membership` failure after `add_member` succeeded; see
  [docs/billing_intents.md](billing_intents.md) §Invariants.
- The seen-event set is bounded (5000) with arbitrary-order
  eviction; new event ids are always tracked, but any single id may
  be evicted once the cap is reached. (See
  [docs/billing_config.md](billing_config.md) for the
  `_seen_event_ids` semantics.)
- PII and sensitive fields are stripped from logged metadata. The
  full forbidden-key set is: `card`, `payment_method`, `customer`,
  `client_secret`, `raw`, `email`, `phone`. (See
  `_FORBIDDEN_META_KEYS` in `billing_config.py` and
  [docs/billing_config.md](billing_config.md) for the canonical
  list.)
- No billing module persists scenario or prompt text.

## Non-goals

Billing hosts no UI, does not manage Stripe Products or prices itself (it
consumes intents), and stores no card data. The legacy
`membership_billing.charge` path is an unimplemented placeholder superseded by
the PaymentIntent flow.

## Fiction removed

None — this subsystem had no prior canon file. The "billing tiers," "credit
system," and "status levels" the Batch 10c instruction listed as possibly
fictional are all real and are documented above.
