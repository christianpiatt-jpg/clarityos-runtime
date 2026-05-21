# ClarityOS v30 — Membership Layer (Founding Cohort) Readiness Report

**Build:** `20260506200000`
**Backend version:** `2.6`
**Status:** Ready for Founding Cohort enrollment.

This pass implements the Founding 500 membership tier, a #G credit
system that gates `/elins/g/run`, mock billing hooks, and the full
web + phone UI surface for joining/managing membership and credits.

All 95 tests pass under in-memory backends (31 new v30 tests).

---

## 1. Membership model — backend

### `membership_store.py` (new)
Per-cohort state + per-user transaction history. Two collections:

* `membership_cohorts/{name}` — `{active_count, members[], waitlist[]}`.
  Single-doc reads make cap checks O(1).
* `membership_transactions/{user}` — append-only list bounded at
  `MAX_TX_PER_USER = 1000`.

Constants:
```python
FOUNDING_COHORT = "founding_500"
FOUNDING_CAP = 500
FOUNDING_PRICE_LOCKED = 50.00
FOUNDING_FULL_PRICE = 150.00
```

Public API:
* `get_cohort_state(name)` → `{cohort, active_count, cap, remaining, waitlist_count, is_full}`
* `is_cohort_full(name)`
* `add_member(user, name)` — raises `ValueError("cohort_full")` /
  `ValueError("already_member")` for caller to translate to HTTP code.
* `remove_member(user, name)` — idempotent.
* `is_member(user, name)`
* `add_to_waitlist(user, name)` — idempotent; appends `{username, ts}`.
* `waitlist_position(user, name)` → 1-indexed or `None`.
* `record_transaction(user, *, type, amount, credits_delta, metadata)`
* `list_transactions(user, *, limit)` — newest first.

NEVER stores prompts, scenario text, or conversation content. Schema is
fixed: only billing metadata (description, billing_id, source).

### `users_store.py` — extensions
New helpers; existing user document silently grows new fields (firestore
takes them transparently, memory dicts too):

* `get_g_credit_balance(user)` → int
* `add_g_credits(user, amount, *, history_entry)` → new balance
* `consume_g_credit(user, *, history_entry)` → new balance; raises
  `ValueError("no_credits")` when balance is 0.
* `set_membership(user, *, tier, price, status, started_ts, cancelled_ts)`
* `get_membership_view(user)` — read-only summary for clients.

User-doc fields added:
```
membership_tier         str   "founding_500" | None
membership_price        float locked at activation; immutable while active
membership_started_ts   float
membership_status       str   "active" | "cancelled" | None
membership_cancelled_ts float when status flipped to cancelled
g_credits               int   never < 0 (consume_g_credit enforces)
g_credit_history        list  tail of last USER_DOC_HISTORY_TAIL=50 events
```

### `membership_billing.py` (new)
Mock-friendly billing abstraction.

```python
charge(user_id, amount, description) -> {ok, billing_id, amount,
                                          description, ts, mode}
record_transaction(user_id, *, amount, type, metadata, credits_delta)
```

`CLARITYOS_BILLING_MODE` controls behavior:
* `"mock"` (default) — generates `mock_<token>` billing ids; never moves
  money. Used for v30 launch.
* `"stripe"` — placeholder; raises `NotImplementedError` (PaymentIntent
  plumbing lands in v31). The existing `billing.py` Stripe wrapper still
  runs the invite/checkout flow.

Validates: `user_id` non-empty, `amount` non-negative number,
`description` non-empty. Raises `BillingError(code, message)` on bad
input — caller maps to 402.

### `app.py` — endpoints
Six new routes, all flag-gated, rate-limit-stubbed, structured-logged:

| Endpoint | Validation | Flag-gated | Rate-limited | Logs |
|---|---|---|---|---|
| `GET  /membership/state` | – | `membership_ui_enabled` | yes | `membership_state` |
| `POST /membership/activate` | `accept_terms` required, cohort cap, price lock | `founder_tier_enabled` | yes | `membership_activate` / `_waitlist` / `_idempotent` / `_failed` / `_race` |
| `POST /membership/cancel` | must be active | `membership_ui_enabled` | yes | `membership_cancel` |
| `POST /membership/g/buy_single` | – | `g_credits_enabled` | yes | `g_buy_single` |
| `POST /membership/g/buy_pack_20` | – | `g_credits_enabled` | yes | `g_buy_pack_20` |
| `GET  /membership/g/history` | `limit` 1–500 | `membership_ui_enabled` | yes | – |

Activate semantics:
1. If `membership_status == "active"` → idempotent return.
2. If user is **not** a returning cancelled member AND cohort cap is
   reached → add to waitlist, return 200 with `waitlisted: true`. No
   charge.
3. Otherwise charge `next_price`, then call `add_member`, then write
   `membership_tier/price/status/started_ts` on the user doc, then
   record the transaction.

Cancel:
* Only valid when status is `active`. Sets status to `cancelled`,
  records `cancelled_ts`, removes from cohort, records a transaction
  with `metadata.price_lock_forfeit = true`.

Reactivation:
* When status is `cancelled`, `_founding_price_for(user)` returns
  `FOUNDING_FULL_PRICE` ($150) instead of the locked $50. The new lock
  is written at activation time (so future cancel→reactivate cycles
  keep paying full price).

### `app.py` — `/elins/g/run` integration
When `g_credits_enabled` is on, every #G run consumes one credit:

1. Pre-run balance check; 402 with `error: "no_credits"` if zero.
2. Run #G as before.
3. **After success**, `consume_g_credit` decrements + appends to
   `g_credit_history` and `record_transaction("g_consume")`.
4. Failed runs do **not** consume credits (validation/embed/etc.
   errors short-circuit before deduction).

The response now includes `g_credits_remaining: int` when the gate is
on.

### `app.py` — `/me`, `/health`, `/`
* `/me` adds the three v30 feature gates (`founder_tier_enabled`,
  `g_credits_enabled`, `membership_ui_enabled`) and a `membership` view
  block so the cockpit can render the badge in one round-trip.
* `/health` and `/` bumped to version `2.6`.
* `/` catalog includes the six membership endpoints.

### Startup flag bootstrap
After v29 cohort defaults, v30 adds:
```python
v29_hardening._DEFAULT_FLAGS.setdefault("founder_tier_enabled", False)
v29_hardening._DEFAULT_FLAGS.setdefault("g_credits_enabled", False)
v29_hardening._DEFAULT_FLAGS.setdefault("membership_ui_enabled", False)
for _coh in (COHORT_FOUNDER, COHORT_FOUNDER_EXCEPTION):
    set_flag("founder_tier_enabled", True, cohort=_coh)
    set_flag("g_credits_enabled", True, cohort=_coh)
    set_flag("membership_ui_enabled", True, cohort=_coh)
set_flag("g_credits_enabled", True, cohort=COHORT_TERRACE_1)
set_flag("membership_ui_enabled", True, cohort=COHORT_TERRACE_1)
```

Founders get the founding-tier offer; Terrace 1 sees the credit UI but
can't activate the founding tier server-side.

---

## 2. #G credit system — confirmed semantics

* Single-run purchase: `$1.00` → `credits_delta: +1`, `g_buy_single`
  transaction recorded.
* 20-pack purchase: `$20.00` → `credits_delta: +20`, `g_buy_pack_20`
  transaction recorded.
* Per-run consumption: 1 credit deducted on successful #G run.
* Negative-balance guard: `consume_g_credit` raises `ValueError`; route
  surfaces 402.
* Remaining balance returned in: `/membership/state`,
  `/membership/g/buy_single`, `/membership/g/buy_pack_20`,
  `/elins/g/run` (when gate is on).

Backend helpers (matches the spec verbatim):
```python
users_store.add_g_credits(user_id, amount, history_entry=...)
users_store.consume_g_credit(user_id, history_entry=...)
users_store.get_g_credit_balance(user_id)
```

---

## 3. Test suite

`tests/test_v30_membership.py` (new) — 31 tests. Coverage:

* `users_store` — balance default 0, increments persist history,
  consume blocks at 0, decrements stop at 0.
* `membership_store` — default cohort state, idempotent add/remove,
  cap-full raises `cohort_full`, waitlist position, transaction cap.
* `/membership/state` — happy path + 403 when flag off.
* `/membership/activate` — terms required, happy path, idempotent on
  re-call, waitlist when cap is full (verified active_count never
  exceeds cap).
* `/membership/cancel` — sets cancelled status, surfaces full price,
  rejects when not active. Reactivation pays full $150.
* `/membership/g/buy_*` — increments balance, returns purchase block,
  blocked when `g_credits_enabled` is off.
* `/membership/g/history` — newest first.
* `/elins/g/run` — 402 when no credits, consumes one credit on
  success, does NOT consume on validation failure.
* Auth contract — every membership endpoint returns 401 unauthenticated.

Run: `python -m pytest tests/ -q` — 95 passed.

The existing v28 happy path test was updated to buy a pack first
(founder accounts now require credits).

---

## 4. UI — Web

New files under `web/src/`:
* `lib/api.ts` — extended with v30 types + six helpers
  (`membershipState`, `membershipActivate`, `membershipCancel`,
  `gBuySingle`, `gBuyPack20`, `gHistory`). Flag union extended with the
  three v30 names.
* `hooks/useMembership.ts` — fetches `/membership/state`, exposes
  activate / cancel / buySingle / buyPack20 with optimistic balance
  updates.
* `routes/MembershipPage.tsx` — composed page; route registered at
  `/membership` in `App.tsx`.
* `components/membership/MembershipStatusCard.tsx` — tier label, locked
  price, next price, cohort fill, waitlist position, status badge
  (ACTIVE / CANCELLED / NOT JOINED).
* `components/membership/GCreditsPanel.tsx` — balance, two buy buttons,
  recent activity table (uses `history_tail` from /membership/state).
* `components/membership/PurchaseCreditsModal.tsx` — confirm dialog
  with Esc-to-close, error-surface + retry.
* `components/cockpit/OnboardingWizard.tsx` — extended with
  `<PostOnboardingMembershipOffer />`, rendered when
  `/v29/onboarding/state.done === true`.

`Cockpit.tsx` header now includes a `Membership →` link when the
`membership_ui_enabled` flag is on.

UI rules respected:
* Loading + error states explicit.
* Existing design system (button styles, card borders, spacing).
* Existing hooks/services pattern (`useFlags`, `useMembership`).
* Never infers or summarizes content — every value renders verbatim
  from the backend response.
* Defensive accessors guard against missing fields.

`tsc --noEmit` — clean (exit=0).

---

## 5. UI — Phone

New files under `phone/`:
* `lib/api.ts` — v30 types + helpers.
* `lib/hooks/useMembership.ts` — mirrors web hook.
* `app/membership.tsx` — Founding cohort screen. Status card,
  activate/cancel, link to `/g_credits`.
* `app/g_credits.tsx` — balance + buy buttons + native `Modal`-based
  purchase confirmation + recent activity list.
* `app/settings.tsx` — `MembershipBadge` component inline in the
  Account card. Tap opens `/membership`.

Native phone idioms:
* `Switch` for the "I understand the price-lock terms" toggle.
* `Modal` for the purchase confirmation.
* `ScrollView` + design tokens (`colors`, `radius`, `space`) from
  `lib/theme.ts`.

`tsc --noEmit` — no new errors. The two pre-existing errors
(`ingest.tsx` ProviderId, `invite/[token].tsx` discriminant) are
unrelated to v30.

---

## 6. Onboarding integration

`OnboardingWizard.tsx` now branches on `state.done`:

* If false → render the three-step checklist (vault, Dewey, snapshot).
* If true → render `<PostOnboardingMembershipOffer />`.

The offer card:
* Hidden when `membership_ui_enabled` is false.
* Hidden when `founder_tier_enabled` is false.
* Hidden when `membership.status === "active"`.
* Hidden when the user dismissed it (`localStorage`-backed).
* Adapts copy when the cohort is full ("Join the waitlist").
* Two CTAs: navigate to `/membership` (Activate / Join waitlist), or
  Dismiss (limited mode — no #G runs because the credit gate is on).

If the user declines, the cockpit still works for non-#G features. The
`/elins/g/run` 402 surfaces a "Buy more from /membership" message that
the Elins screen already renders via the existing error banner.

---

## 7. Cohort enforcement — confirmed

| Rule | Enforced where |
|---|---|
| founding_500 cap full → new users go to waitlist | `app.py:membership_activate` checks `is_cohort_full()` before charging; calls `add_to_waitlist`, returns `waitlisted: true`. |
| Cancellation forfeits price lock | `app.py:_founding_price_for` returns `FOUNDING_FULL_PRICE` ($150) when status is cancelled. |
| Reactivation pays full price | Same; on activate the new locked price is written via `set_membership(price=150.0)`. |
| User cannot exceed cap by re-trying | `add_member` raises `ValueError("cohort_full")`; route returns 409. Test: `test_activate_when_cap_full_returns_waitlist`. |

---

## 8. Files touched

**New**
* `membership_store.py`
* `membership_billing.py`
* `tests/test_v30_membership.py`
* `web/src/hooks/useMembership.ts`
* `web/src/components/membership/MembershipStatusCard.tsx`
* `web/src/components/membership/GCreditsPanel.tsx`
* `web/src/components/membership/PurchaseCreditsModal.tsx`
* `web/src/routes/MembershipPage.tsx`
* `phone/lib/hooks/useMembership.ts`
* `phone/app/membership.tsx`
* `phone/app/g_credits.tsx`
* `V30_READINESS.md` (this file)

**Modified**
* `app.py` — v30 imports, flag bootstrap, `/me` extension, six
  membership endpoints, `/elins/g/run` credit gate, version bump,
  what's-new entry, root catalog.
* `users_store.py` — five new public helpers + USER_DOC_HISTORY_TAIL.
* `tests/conftest.py` — `membership_store` reset hook + v30 cohort
  default flags.
* `tests/test_v28_endpoints.py` — version assertion bump (2.5 → 2.6),
  v28 #G happy path now buys credits first.
* `web/src/lib/api.ts` — V29Flag union extended; v30 helpers + types.
* `web/src/App.tsx` — `/membership` route.
* `web/src/routes/Cockpit.tsx` — Membership link in header.
* `web/src/components/cockpit/OnboardingWizard.tsx` — post-onboarding
  membership offer.
* `phone/lib/api.ts` — V29Flag union extended; v30 helpers + types.
* `phone/app/settings.tsx` — MembershipBadge inline in Account card.
* `BUILD_VERSION` — bumped to `20260506200000`.

---

## 9. Rollback path

v30 is purely additive. To revert:
1. Set `CLARITYOS_BILLING_MODE=mock` (already default; only matters for
   future stripe rollouts).
2. Toggle off cohort flags via maintenance shell:
   ```python
   v29_hardening.set_flag("founder_tier_enabled", False, cohort="founder")
   v29_hardening.set_flag("g_credits_enabled", False, cohort="founder")
   ```
   Or comment out the loop in `app.py` startup and redeploy.
3. UI surfaces collapse to friendly disabled states; backend data is
   untouched. No persisted state mutation needed.

The v30 user-doc fields stay in place; if v31 wants to retire them we
can null them via a one-shot migration.

---

## 10. Known gaps / next-pass candidates

* Real Stripe one-tap charges — `membership_billing.charge()` raises
  `NotImplementedError` in stripe mode. v31 should add Stripe Customer +
  PaymentMethod plumbing so the founding-tier activation can actually
  move money.
* The waitlist endpoint is implicit (no `/membership/waitlist/*` route);
  position is surfaced via `/membership/state.waitlist_position`. If
  product wants a dedicated waitlist surface, add it in v31.
* The `confirm()` dialog used for cancel on web is a native browser
  prompt — we could replace it with a custom modal if design wants
  consistency.
* Per-user transaction history is bounded at 1000 events;
  `MAX_TX_PER_USER` should be configurable when high-volume cohorts
  ship.
* The v29 rate limiter is in-memory; per-route caps for the membership
  routes inherit the v29 default (60/min). Worth tuning once we have
  observed launch traffic.
