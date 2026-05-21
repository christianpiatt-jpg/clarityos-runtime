# Membership

## Purpose

Membership is the Founding 500 cohort layer: cohort management and the cap,
activation, the in-cohort waitlist, #G credits, entitlement projection, and
invite-based onboarding.

## Implementation location

Repo-root modules: `membership_store.py`, `membership_billing.py`,
`entitlement_view.py`, `invites_store.py`. The HTTP endpoints are in `app.py`.

For the full per-module contract on cohorts, transactions, and PaymentIntent
persistence, see [docs/membership_store.md](membership_store.md).

## Tiers

There is **one** membership tier: `FOUNDING_COHORT` = `founding_500`, with
`FOUNDING_CAP` = 500 members, a locked price `FOUNDING_PRICE_LOCKED` of $50.00,
and a full price `FOUNDING_FULL_PRICE` of $150.00. Cancelling forfeits the
locked price — reactivation pays the full price.

## Data model

- **Cohort document** (`membership_store`): a single document
  `{active_count, members[], waitlist[]}`. One document keeps the cap check to a
  single read; `active_count` always equals `len(members)`.
- **Per-user transactions** (`membership_store`): capped at `MAX_TX_PER_USER`
  (1000), with a strictly monotonic `ts`. Monotonicity is enforced via a
  Windows-resolution-safe adjustment (`last_ts + 1e-6`) so ordering remains
  deterministic even when `time.time()` returns identical values on
  back-to-back calls.
- **Membership fields on the user record** (`users_store`): `membership_tier`,
  `membership_price`, `membership_status`, `membership_started_ts`,
  `membership_cancelled_ts`, and `membership_confirmed` / `membership_confirmed_ts`.
- **#G credits on the user record**: `g_credits` (balance) and
  `g_credit_history`.

## APIs / entrypoints

- `POST /membership/activate` — PaymentIntent-driven. Returns `pending` plus an
  `intent_id` / `client_secret`; the cohort slot is consumed only when the
  payment webhook succeeds. Idempotent when the user is already active. The
  v31 PaymentIntent record in `membership_store` includes `client_secret` by
  design (stored server-side so the server can resume the confirmation flow
  without re-fetching from Stripe). HTTP surfaces that expose intent records
  must filter this field from client responses — see
  [docs/membership_store.md](membership_store.md) for the per-module contract.
- `POST /membership/confirm` — a separate, no-charge flow (v74) that binds
  terms-of-service consent for operators who paid through the WordPress Stripe
  Checkout funnel.
- `POST /membership/g/buy_single` ($1.00, +1 credit) and
  `POST /membership/g/buy_pack_20` ($20.00, +20 credits); `GET /membership/g/history`.
- `GET /me/entitlement` and `GET /founder/entitlement/{user_id}`.
- Invites: `POST /invite/{token}/redeem` (free `founder_exception` invites);
  `POST /invite/{token}/checkout` then `/invite/{token}/finalize` (paid
  `terrace_1` invites).

## #G credits

The #G credit balance lives on the user record. `consume_g_credit` enforces a
non-negative balance, and credits gate `/elins/g/run` (the #G scenario engine).

Note: the non-negative-balance invariant is enforced in `users_store`
(`consume_g_credit`), not in `membership_store`. `membership_store` records
transactions with `credits_delta` but does not maintain the running balance.
See [docs/users_store.md](users_store.md) for the authoritative contract.

## In-cohort waitlist

When the cohort is full and the caller is not a returning cancelled member,
`/membership/activate` adds the user to the cohort document's `waitlist` (with a
1-indexed `waitlist_position`). This is distinct from `waitlist_store.py` — the
public, pre-signup funnel (`docs/waitlist.md`).

## Entitlement view

`entitlement_view.compute_entitlement_view` is a read-only **projection**, not a
second source of truth. It never raises (an unknown user returns
`exists: false`). It computes `active` (true for `active` / `past_due` /
`grace_period`; revoked for `cancelled` / `failed`), `founding_500_badge`,
`membership_confirmed`, and a `features` block (`portal_access`,
`founding_500_badge`, `priority_support`, `downloads`, `community_access`,
`billing_portal`).

## Invite flow

`invites_store.py` stores invite documents — `{invite_id, cohort, price,
billing_required, inviter, status, created_at, expires_at, used_by, used_at}`,
with `cohort` one of `founder_exception` (free) or `terrace_1` (paid). Free
invites are redeemed directly; paid invites run through a Stripe hosted Checkout
and a `finalize` step that verifies payment before the account is created.

## Integration points

- **Billing** — activation, renewal, and #G purchases all run through the
  PaymentIntent flow (`docs/billing.md`); a cohort slot is consumed only on a
  successful payment webhook.
- **Auth** — membership and credit fields live on the user record.
- **ELINS** — #G credits gate `/elins/g/run`.

## Invariants

- `active_count` always equals `len(members)`.
- A cohort slot is consumed only on real payment success — never at intent
  creation.
- `add_member` raises `cohort_full` / `already_member`; `remove_member` and
  `add_to_waitlist` are idempotent.
- The #G credit balance never goes negative (enforced by
  `users_store.consume_g_credit`, not `membership_store`).
- `membership_store` performs **no PII sanitization** on transaction or
  intent metadata, unlike `billing_config` (which uses `_sanitise_meta` to
  filter a 7-key forbidden set). Callers must not place email, phone, card
  data, or other sensitive fields into transaction or intent `metadata`. See
  [docs/membership_store.md](membership_store.md) for the full caller-side
  contract.

## Non-goals

There is only one tier — no monthly/annual variants beyond the legacy invite
plans. `entitlement_view` is a projection only and carries no
`cancel_at_period_end` or `lifetime` source field. `dewey_memberships_store.py`,
despite the name, is **not** part of this subsystem — it is a DEWEY-neighborhood
concept (documented with DEWEY).

## Fiction removed

None — this subsystem had no prior canon file. The Founding 500 tier, the #G
credit system, and the membership states named in the Batch 10c instruction as
possibly fictional are all real and are documented above.
