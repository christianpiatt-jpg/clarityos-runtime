# V42 Readiness — Stripe live mode + billing hardening

Status: ✅ Ready
Backend version: `3.8`
Billing config version: `billing_config.v42.1`
Build: `20260507400000`

---

## What v42 ships

A consolidated Stripe configuration + observability layer:

- New env vars (`CLARITYOS_STRIPE_MODE`, `CLARITYOS_STRIPE_SECRET_KEY`,
  `CLARITYOS_STRIPE_WEBHOOK_SECRET`) take precedence over the legacy
  `STRIPE_*` names so going-live is a single env-var swap.
- `billing_config.get_billing_status()` is the single source of truth
  for "is billing on, and in which mode?".
- The Stripe webhook now verifies the signature, rejects test/live
  mode mismatches, dedupes by event id, and drives subscription
  lifecycle state via `users_store.set_billing_state` (active /
  past_due / cancelled).
- `record_billing_event` keeps a sanitised ring of recent webhooks for
  the founder console; raw card / customer / email fields are stripped
  before they ever land in the log.
- `POST /founder/billing/status` surfaces mode + key presence + recent
  events; `GET /me/billing` exposes the user's normalised billing
  state without any Stripe ids.
- Web + phone surfaces show the active mode, recent events, and a
  visible warning when billing is disabled.

---

## Files added / changed

### New
- `billing_config.py` — env-var resolution + idempotent event seen-set +
  recent-events ring + sanitised `record_billing_event`.
- `web/src/components/founder/billing/FounderBillingPanel.tsx`
- `web/src/components/membership/MeBillingBadge.tsx`
- `tests/test_v42_billing_hardening.py` — 32 tests.
- `V42_READINESS.md` (this file).

### Modified
- `billing.py` — `is_configured`, `is_webhook_configured`, `_stripe`,
  `verify_webhook` route through `billing_config` (preferred env names
  + legacy fallback); empty signature header → `None` (rejection),
  not exception.
- `billing_intents.create_payment_intent` — refuses cleanly with
  `BillingError("billing_disabled", …)` when no key is set; attaches
  `environment` + `cohort` + `receipt_email` metadata to live
  PaymentIntents.
- `app.py`:
  - Imports `billing_config`.
  - `/billing/webhook` rewritten: missing signature in stripe mode →
    400; mode mismatch → 400; duplicate event id → 200 +
    `duplicate=True`; subscription / checkout events drive
    `users_store.set_billing_state`; every event is recorded on
    `billing_config`.
  - `_handle_subscription_event` covers
    `checkout.session.completed`, `invoice.payment_succeeded`,
    `invoice.payment_failed`, `customer.subscription.updated`,
    `customer.subscription.deleted`.
  - New `_billing_payload_meta` helper extracts a small whitelist of
    fields from the Stripe object.
  - `/founder/billing/status` — Stripe mode + recent events + webhook
    health (founder-gated).
  - `/me/billing` — normalised user billing snapshot (auth, no raw
    Stripe ids).
  - Backend version `3.8`; root listing extended.
- `web/src/lib/api.ts` — `V42BillingStatus`, `V42BillingEvent`,
  `V42FounderBillingStatus`, `V42MeBilling` + helpers.
- `web/src/components/founder/FounderDashboard.tsx` — embeds
  `FounderBillingPanel` as full-width row.
- `web/src/routes/Account.tsx` — adds a `BILLING` panel with
  `MeBillingBadge`.
- `phone/lib/api.ts` — `V42MeBilling` + `meBilling()` helper.
- `phone/app/billing.tsx` — header gets a TEST/LIVE/DISABLED pill;
  shows a "Billing temporarily unavailable" banner when disabled.
- `tests/conftest.py` — reset hook calls
  `billing_config._reset_for_tests`.
- `tests/test_v28_endpoints.py` — health version `3.8`.
- `BUILD_VERSION` — `20260507400000`.

---

## Env-var resolution

```
CLARITYOS_STRIPE_MODE          ∈ {"test", "live"}     — explicit override
CLARITYOS_STRIPE_SECRET_KEY    sk_test_... | sk_live_... (preferred)
CLARITYOS_STRIPE_WEBHOOK_SECRET whsec_...               (preferred)

# Legacy fallbacks (still honoured):
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET

# Unchanged from earlier:
CLARITYOS_BILLING_MODE         ∈ {"mock", "stripe"}    (runtime gate)
STRIPE_PRICE_ONETIME, STRIPE_PRICE_RECURRING            (legacy invite flow)
```

Mode resolution precedence:
1. `CLARITYOS_STRIPE_MODE` if set to a valid value.
2. Inspect secret key: `sk_live_*` → `live`, `sk_test_*` → `test`.
3. Otherwise `disabled` (no key present).

---

## API surface

### `GET /founder/billing/status` (founder)
```jsonc
{
  "ok": true,
  "stripe": {
    "mode":               "test",     // test | live | disabled
    "has_secret":         true,
    "has_webhook_secret": true,
    "live_mode":          false,
    "billing_enabled":    true,
    "version":            "billing_config.v42.1"
  },
  "live_mode":           false,
  "recent_events":       [...],       // up to 50, newest first, sanitised
  "last_event_ts":       1715080800.123,
  "runtime_billing_mode": "mock"      // CLARITYOS_BILLING_MODE
}
```

### `GET /me/billing` (auth)
```jsonc
{
  "ok": true,
  "status":          "active" | "past_due" | "canceled" | "none",
  "plan":            "founding" | null,
  "renewal_ts":      1715080800.0,    // POSIX seconds, null when none
  "mode":            "test",          // mirror of /founder/billing/status.stripe.mode
  "billing_enabled": true
}
```

`/me/billing` is metadata-only: no Stripe ids, no card details, no
customer ids. Tests assert that the response repr never contains
`cus_`, `sub_`, `in_`, `pi_`, or `client_secret`.

---

## Webhook hardening

| Behaviour | v41 | v42 |
| --- | --- | --- |
| Missing signature in stripe mode | 400 (only on later verify) | 400 with `error=missing_signature` upfront |
| Invalid signature | 400 | 400 with `error=bad_signature` |
| Mode mismatch (test event on live key) | not checked | 400 with `error=mode_mismatch` |
| Duplicate event id | re-processed | 200 + `duplicate=true` short-circuit |
| `checkout.session.completed` | logged | drives `set_billing_state(active, renewal=now+30d)` + tx |
| `invoice.payment_succeeded` | logged | drives `set_billing_state(active, renewal=period_end)` |
| `invoice.payment_failed` | logged | drives `set_billing_state(past_due)` |
| `customer.subscription.updated` (status=past_due) | logged | drives `set_billing_state(past_due)` |
| `customer.subscription.deleted` | logged | drives `set_billing_state(cancelled)` + `membership_status=cancelled` |
| Recent events | not surfaced | sanitised ring on `billing_config` |

PII fields (`card`, `payment_method`, `customer`, `client_secret`,
`raw`, `email`, `phone`) are stripped from `payload_meta` before any
event is recorded or logged.

---

## UI

### Web
- **Founder dashboard** gains a `Billing` section with TEST / LIVE /
  DISABLED mode pill, key presence indicators, last-webhook timestamp,
  and a 12-row recent-events list. Disabled mode shows an explicit
  warning that new checkout will be rejected.
- **Account page** adds a `BILLING` panel with `MeBillingBadge`
  (status pill + mode pill + renewal date + disabled banner when off).

### Phone
- `billing.tsx` header now shows the mode pill and a disabled banner.
- All existing surfaces (`useMembership`, transactions, payment
  intents) are unchanged.

---

## Tests

```
tests/test_v42_billing_hardening.py — 32 tests, all pass
Full suite — 500 passed, 0 failed
```

Coverage:
- `billing_config`: env precedence, mode resolution, status shape,
  `seen_event` idempotency, `record_billing_event` PII filter,
  newest-first ordering of `list_recent_events`.
- `billing_intents.create_payment_intent`: mock mode succeeds; stripe
  mode without keys raises `billing_disabled`; input validation
  rejects empty user / sub-min amount / unknown kind.
- Webhook: mock-mode synthetic events accepted; stripe-mode missing
  signature → 400; invalid signature → 400 (monkey-patched
  `billing.verify_webhook`); test-event-on-live-key mismatch → 400;
  duplicate event id → `duplicate=True`; subscription / checkout
  lifecycle each drive `users_store.set_billing_state`; recent-events
  ring is populated.
- `/founder/billing/status`: shape + founder gate + reflects mode
  flip + `disabled` when no keys.
- `/me/billing`: default `none`; `active` with renewal_ts;
  `past_due`; `canceled`; assertion that no Stripe ids leak.

---

## Notes / follow-ups

- The legacy invite/checkout flow (`/invite/{token}/checkout`)
  continues to use the v2 `billing.py` helpers; it picks up the new
  env-var resolution automatically since both modules share
  `billing_config.get_secret_key()`.
- `billing_config` keeps state in-process. For multi-instance
  deployments the seen-event set should be lifted into Firestore (the
  same pattern as `elins_project`); we ship in-process today because
  Stripe will retry until 2xx, and the cap of 5,000 ids covers a
  single instance's lifetime comfortably.
- Pre-v42 surfaces are unchanged. Older clients reading `/me` still
  see the same fields; the new `/me/billing` and `/founder/billing/status`
  endpoints are additive.
