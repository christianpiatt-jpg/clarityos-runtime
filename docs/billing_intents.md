# Billing Intents

## Purpose

`billing_intents` is the **PaymentIntent flow + multi-store
side-effect engine** for ClarityOS billing. It owns three concerns:

1. **PaymentIntent lifecycle** — create / confirm / fail / webhook
   dispatch, with mock and real Stripe modes sharing one record
   shape and one webhook-driven flow.
2. **Side-effect application** — coordinated writes across
   `users_store`, `membership_store`, and the user document fields
   for the 4 canonical `VALID_KINDS` (`membership_activation`,
   `membership_renewal`, `g_credit_single`, `g_credit_pack`).
3. **Renewal policy** — the 4 timing constants
   (`RENEWAL_PERIOD_DAYS`, `RENEWAL_RETRY_HOURS`,
   `MAX_RENEWAL_RETRIES`, `GRACE_PERIOD_HOURS`) and the
   `calculate_next_renewal_ts` helper, consumed by `billing_renewal`.

It is the **first canonicalized module that explicitly coordinates
writes across multiple stores**. Per `membership_store`'s PASS-3D
contract — "atomic coordination across stores is caller-side" —
`billing_intents` IS that caller. The multi-store writes are NOT
wrapped in transactions; reconciliation of partial-failure states
is operator-side.

It is the detail companion to `docs/billing.md`, which is the
broader subsystem doc covering this module + `billing.py` +
`billing_config.py` + `billing_renewal.py`.

## Implementation location

- **File:** `billing_intents.py` (483 lines, single file).
- **No package directory**, no `__init__.py`, no `__all__`.
- **No explicit version anchor** — `v31` is referenced inline in
  module docstring (line 2) and comments.
- **No external spec** — this document plus `docs/billing.md` are
  the authoritative contract.
- **Imports** (top level, stdlib + 3 subsystems):
  - stdlib: `logging`, `os`, `secrets`, `time`, `typing.Optional`
  - `membership_store` (CURRENT — Batch-25)
  - `users_store` (CURRENT — Batch-22)
  - `v29_hardening` (not yet canonicalized; used for structured
    `log_event` calls)
- **Lazy imports** (stripe-mode-only): `billing_config` (line 163)
  and `stripe` SDK (line 173). Memory-mode deployments do not need
  either installed.
- **Notable absence:** `billing_intents` does NOT import
  `billing.py`. Stripe webhook signature verification is delegated
  to `billing.verify_webhook` (per docstring line 46-47), which is
  called from `app.py`'s webhook route before the parsed event
  reaches `handle_payment_webhook`.

## Modes & flags

### Two orthogonal mode flags

`billing_intents` and `billing_config` use **two different env
vars** for two different concerns:

| Env var | Module | Purpose | Values |
|---|---|---|---|
| `CLARITYOS_BILLING_MODE` | `billing_intents._mode()` | Runtime path selection | `"mock"` (default) / `"stripe"` |
| `CLARITYOS_STRIPE_MODE` | `billing_config.get_stripe_mode()` | Stripe environment | `"test"` / `"live"` / `"disabled"` |

The two compose:
- `CLARITYOS_BILLING_MODE=mock` → mock intent flow regardless of
  Stripe keys
- `CLARITYOS_BILLING_MODE=stripe` → real Stripe flow, and
  `billing_config.get_stripe_mode()` further determines test vs
  live based on key prefix

The intent record carries BOTH:
- `mode` field (line 154): `_mode()` value (`"mock"` / `"stripe"`)
- `environment` field (line 179 / 206): `billing_config.get_stripe_mode()`
  value in stripe mode, `"mock"` in mock mode

### Mock auto-confirm flag

`CLARITYOS_MOCK_AUTO_CONFIRM` (default `"1"`) — when truthy in mock
mode, `create_payment_intent` immediately calls
`confirm_payment_intent` synchronously so legacy callers (v30
tests) get synchronous balance updates. Set to `"0"` to test the
real async confirm flow.

### Mode matrix

| `_mode()` | `_mock_auto_confirm()` | `create_payment_intent` behavior |
|---|---|---|
| `"mock"` (default) | True (default) | Mock intent created → synchronously confirmed via webhook → returns `status: "succeeded"` |
| `"mock"` | False | Mock intent created with `status: "requires_payment_method"`; caller must invoke `confirm_payment_intent` to drive the side effects |
| `"stripe"` | (ignored) | Real `stripe.PaymentIntent.create`; client confirms via Stripe.js; webhook arrives async from Stripe |

### Stripe mode prerequisites

Two prerequisites checked early in stripe-mode path (lines 157-175):
1. **Secret key present** — from `billing_config.get_secret_key()`
   OR legacy `STRIPE_SECRET_KEY` env. Missing key →
   `BillingError("billing_disabled")`.
2. **Stripe SDK installed** — lazy `import stripe`. ImportError →
   `BillingError("stripe_not_installed")`.

Both errors are clean BillingErrors with actionable messages, not
low-level exceptions.

## Data model

`billing_intents` defines **no dataclasses, no enums, no TypedDicts**.
The 13-field intent record is a plain dict managed via
`membership_store.record_intent` + `membership_store.update_intent`.

### Intent record (13 fields)

```python
{
    "intent_id":           str,                  # REQUIRED — mock or Stripe-issued
    "user":                str,                  # username
    "kind":                str,                  # ∈ VALID_KINDS
    "amount":              float,                # USD
    "description":         str,
    "metadata":            dict,                 # caller-controlled + auto-injected user_id/kind
    "status":              str,                  # "requires_payment_method" | "processing" | "succeeded" | "failed" | "canceled"
    "side_effect_applied": bool,                 # idempotency guard for _apply_*
    "created_ts":          float,                # time.time() at create
    "mode":                str,                  # "mock" | "stripe" — runtime path
    "intent_id":           str,                  # (set after Stripe create or mock generation)
    "client_secret":       Optional[str],        # ⚠ stored intentionally; HTTP layer must filter from list responses
    "environment":         str,                  # "test" | "live" | "mock"
    # Set on confirmation (only one of these for terminal states):
    "confirmed_ts":        Optional[float],      # webhook payment_intent.succeeded
    "failed_ts":           Optional[float],      # webhook payment_intent.payment_failed
    "failure_code":        Optional[str],        # from Stripe last_payment_error.code or "unknown"
}
```

**`client_secret` is intentionally stored** — per v31 design and
flagged in Batch-25 PASS-4 for `membership_store`. The single
create/confirm path returns it to the client (which needs it for
Stripe.js confirm); HTTP surfaces that LIST intents must filter it
from responses. See §Invariants → Security for details.

### Public constants (5)

| Constant | Value | Purpose |
|---|---|---|
| `VALID_KINDS` | 4-tuple: `("membership_activation", "membership_renewal", "g_credit_single", "g_credit_pack")` | Kind validation in `_validate_inputs`; also exposed for `app.py:9275` via `v29_hardening.require_one_of` |
| `RENEWAL_PERIOD_DAYS` | `30` | Days between successful renewals |
| `RENEWAL_RETRY_HOURS` | `24` | Gap between renewal retries |
| `MAX_RENEWAL_RETRIES` | `3` | Retry count before grace period |
| `GRACE_PERIOD_HOURS` | `24` | Grace period duration before cancellation |

The 4 renewal constants drive `billing_renewal.py`'s daily
scheduler. They live here (not in billing_renewal) because
`calculate_next_renewal_ts` uses `RENEWAL_PERIOD_DAYS` and the
constants are co-located with the calculator.

## APIs / entrypoints

### Public functions (5)

#### `create_payment_intent(user_id, amount, description, kind, metadata=None) -> dict` (line 130)

**Signature: positional args, NOT keyword-only.** Validates,
constructs the record, dispatches to mock or Stripe path,
persists via `membership_store.record_intent`, logs via
`v29_hardening.log_event("billing_intent_created", ...)`, and
optionally auto-confirms in mock mode.

**Validation** (`_validate_inputs`, lines 109-124):

| Check | Raises |
|---|---|
| `user_id` non-empty string | `BillingError("bad_user")` |
| `amount` float-coercible | `BillingError("bad_amount")` |
| `amount >= 0.50` (Stripe min) | `BillingError("bad_amount")` |
| `description` non-empty string | `BillingError("bad_description")` |
| `kind ∈ VALID_KINDS` | `BillingError("bad_kind")` |

**Returns:** the 13-field record dict.

#### `confirm_payment_intent(intent_id) -> dict` (line 228)

**Mock-mode only.** Synthesizes a `payment_intent.succeeded`
webhook event for the given intent and routes it through
`handle_payment_webhook`. Idempotent — returns existing record
unchanged if already `status == "succeeded"`.

In stripe mode, raises `BillingError("stripe_mode")` — real
confirmation happens client-side via Stripe.js.

#### `fail_payment_intent(intent_id, *, code="card_declined") -> dict` (line 246)

**Mock-mode only.** Mirror of `confirm_payment_intent` for the
failure path. Synthesizes `payment_intent.payment_failed` with
the given `code`. Idempotent. Refuses in stripe mode.

#### `handle_payment_webhook(event: dict) -> dict` (line 259)

**Does NOT raise — returns `{ok: False, error: ...}` envelopes**
on errors. Different error contract from the other 4 public
functions because Stripe webhook delivery requires non-raising
semantics.

Handles two event types:
- `payment_intent.succeeded` → status="succeeded", confirmed_ts,
  conditionally `_apply_succeeded` (if not `side_effect_applied`)
- `payment_intent.payment_failed` → status="failed", failed_ts,
  failure_code, conditionally `_apply_failed`

Other event types (`canceled`, `processing`, `requires_action`,
etc.) are logged as `"billing_webhook_other"` and the intent is
returned unchanged.

Logs 3 structured events: `"billing_intent_succeeded"`,
`"billing_intent_failed"`, `"billing_webhook_other"`, plus
`"billing_webhook_unknown_intent"` for missing intents.

#### `calculate_next_renewal_ts(ts: float) -> float` (line 480)

```python
return float(ts) + RENEWAL_PERIOD_DAYS * 86400.0
```

Pure function. No None handling — `float(None)` raises TypeError;
caller responsibility. Consumed by `_apply_succeeded` for
activation/renewal paths and by `app.py:12672` for founder-driven
activation.

### `BillingError` (line 78)

```python
class BillingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
```

**First canonicalized module to define its own exception class.**
Two attributes: machine-readable `code` and human-readable
`message`. `app.py` catches `BillingError` at 4 HTTP route handlers
(lines 8964, 9152, 9284, 9326) and translates to HTTP responses.

### Error code enumeration (11 sites)

| Code | Site | Trigger |
|---|---|---|
| `bad_user` | `_validate_inputs:110` | user_id not non-empty string |
| `bad_amount` | `_validate_inputs:113-119` | amount not numeric OR < $0.50 |
| `bad_description` | `_validate_inputs:120-121` | description not non-empty string |
| `bad_kind` | `_validate_inputs:122-123` | kind ∉ VALID_KINDS |
| `billing_disabled` | `create_payment_intent:167-171` | stripe mode + no secret key |
| `stripe_not_installed` | `create_payment_intent:173-175` | stripe mode + SDK missing |
| `stripe_create_failed` | `create_payment_intent:197-198` | `stripe.PaymentIntent.create` rejected |
| `not_found` | `confirm_payment_intent:233-234` | intent_id absent from membership_store |
| `not_found` | `fail_payment_intent:249-250` | intent_id absent |
| `stripe_mode` | `confirm_payment_intent:237-241` | server-side confirm refused |
| `stripe_mode` | `fail_payment_intent:253-254` | server-side fail refused |

### Side-effect engine — `_apply_succeeded` (lines 357-432)

Dispatches on `kind`. Multi-store writes are NOT wrapped in
try/except (except for the cap-race `ValueError` catch around
`add_member`).

**`g_credit_single`** (2 stores, 2 writes):
1. `users_store.add_g_credits(user, 1, history_entry={...})`
2. `membership_store.record_transaction(type="g_credit_single", credits_delta=1)`

**`g_credit_pack`** (2 stores, 2 writes):
1. `users_store.add_g_credits(user, 20, history_entry={...})`
2. `membership_store.record_transaction(type="g_credit_pack", credits_delta=20)`

**`membership_activation`** (2 stores, 4 writes):
1. **`membership_store.add_member(user)`** — try/except `ValueError`
2. `users_store.set_membership(tier=FOUNDING_COHORT, price=amount, status="active", started_ts=now)`
3. `users_store.set_billing_state(billing_state="active", renewal_ts=now+30d, renewal_retry_count=0)`
4. `membership_store.record_transaction(type="membership_activation")`

If `add_member` raises `ValueError` (cohort cap race): records
`failed_payment` transaction with `race: True` flag, sets
`billing_state="failed"`, returns early. The caller still marks
`side_effect_applied=True` because the failure-handling side effect
DID run.

**`membership_renewal`** (2 stores, 2 writes):
1. `users_store.set_billing_state(billing_state="active", renewal_ts=now+30d, renewal_retry_count=0)`
2. `membership_store.record_transaction(type="membership_renewal")`

Does NOT touch cohort (already in), does NOT update
`membership_status` (renewal doesn't change status).

### Side-effect engine — `_apply_failed` (lines 435-474)

**`g_credit_single` / `g_credit_pack`** (1 store, 1 write):
1. `membership_store.record_transaction(type="failed_payment", reason=code, kind=...)`

No user_store changes. No credits added.

**`membership_activation`** (2 stores, 2 writes):
1. `membership_store.record_transaction(type="failed_payment", ...)`
2. `users_store.set_billing_state(billing_state="failed")`

No cohort add (the user never got in).

**`membership_renewal`** — the renewal failure state machine:

```
retries = (user_doc.renewal_retry_count) + 1

record_transaction(type="failed_payment", retry=retries)

if retries < MAX_RENEWAL_RETRIES (3):
    set_billing_state(
        billing_state="past_due",
        renewal_ts=now + RENEWAL_RETRY_HOURS (24h),
        renewal_retry_count=retries,
    )
else:
    set_billing_state(
        billing_state="grace_period",
        renewal_retry_count=retries,
        renewal_grace_until_ts=now + GRACE_PERIOD_HOURS (24h),
    )
```

Walks: `active → past_due → past_due → grace_period`. The
`grace_period → cancelled` transition is handled by
`billing_renewal.py`'s scheduler, NOT here.

### Private surface (8 functions)

- `_mode()` (90) — `CLARITYOS_BILLING_MODE` env read
- `_mock_auto_confirm()` (94) — `CLARITYOS_MOCK_AUTO_CONFIRM` env read
- `_new_mock_intent_id()` (98) — `"pi_mock_" + token_urlsafe(12)`
- `_new_mock_client_secret(intent_id)` (102) — `"{id}_secret_" + token_urlsafe(8)`
- `_validate_inputs(user_id, amount, description, kind)` (109) — validation tuple
- `_build_synthetic_event(intent_id, event_type, *, failure_code=None)` (334) — mock webhook event construction
- `_apply_succeeded(user, kind, intent)` (357) — multi-store success side effects
- `_apply_failed(user, kind, intent)` (435) — failure side effects (including renewal state machine)

## Integration points

### Production importers (2)

| Importer | Surface consumed |
|---|---|
| `app.py:87` | 8+ call sites: `create_payment_intent` (3×), `confirm_payment_intent`, `handle_payment_webhook`, `calculate_next_renewal_ts`, `VALID_KINDS`, `BillingError` (catch in 4 routes) |
| `billing_renewal.py:37` | Renewal-policy constants (`RENEWAL_*`, `MAX_RENEWAL_RETRIES`, `GRACE_PERIOD_HOURS`), `calculate_next_renewal_ts`, likely `create_payment_intent` for renewal intent generation |

### HTTP coupling (no routes inside this module)

The module is consumed by `app.py`'s routes for:
- `POST /billing/webhook` — `handle_payment_webhook(event)` (app.py:1282)
- `POST /membership/activate` — `create_payment_intent(kind="membership_activation")` (app.py:8959)
- `POST /membership/g/buy_single` — `create_payment_intent(kind="g_credit_single")` (app.py:9147)
- `POST /membership/g/buy_pack_20` — `create_payment_intent(kind="g_credit_pack")` (likely)
- `POST /billing/intent` — generic intent creation with `VALID_KINDS` validation (app.py:9281)
- `POST /billing/intent/confirm` — `confirm_payment_intent(intent_id)` (app.py:9325)
- Founder activation flow uses `calculate_next_renewal_ts` (app.py:12672)

### Cross-store write coordination

`billing_intents` is the **first canonicalized module** that writes
to multiple stores in coordinated sequences. Per stores' own
PASS-3D contracts:

- `users_store` provides single-document atomicity per CRUD call
- `membership_store` provides single-document atomicity per
  CRUD call

This module composes those calls but provides NO multi-store
atomicity. See §Invariants for failure modes.

### User-document fields read but not in `users_store`'s documented set

`_apply_succeeded` and `create_payment_intent` read three fields
from the user document that are NOT in `users_store.md`'s
enumerated field set:

- `user_doc.get("cohort")` (line 182) — used for Stripe metadata
- `user_doc.get("email")` (line 185) — used as `receipt_email`
- `user_doc.get("renewal_retry_count")` (line 455) — IS in
  `users_store`'s billing-state field set ✓

**Cross-doc audit candidate:** `cohort` and `email` should be
added to `users_store.md`'s "External-caller fields" subsection
alongside `membership_confirmed` and `membership_confirmed_ts`
(flagged in Batch-23).

### Tests (2 files)

- `tests/test_v31_billing.py` — primary SUT (v31 introduction)
- `tests/test_v42_billing_hardening.py` — coupled (v42 hardening)

### No coupling to
- `intelligence_kernel`, `model_router`, LLM SDKs
- `memory_vault`, `operator_state`
- `entitlement_view`, `founder_analytics`
- HTTP routes inside this module (routes live in `app.py`)
- `billing.py` directly (Stripe signature verification delegated
  via the parsed event dict)

## Invariants

### Intent lifecycle state machine

Allowed transitions:
- `create` → `"requires_payment_method"` (mock) OR Stripe-issued
  status (real, typically `"requires_payment_method"`)
- `"requires_payment_method"` → `"succeeded"` via
  `payment_intent.succeeded` webhook
- `"requires_payment_method"` → `"failed"` via
  `payment_intent.payment_failed` webhook

**Invalid transitions do NOT raise** — `handle_payment_webhook`
silently allows last-event-wins semantics. A `succeeded` event
after a `failed` event would overwrite the failed status.
Benign for Stripe-driven flows (Stripe doesn't redeliver
inconsistent events) but possible via operator-triggered
`confirm_payment_intent` / `fail_payment_intent` sequences.

### Two-tier idempotency

1. **Terminal-state check** (lines 286-289): if event type matches
   current terminal state (`succeeded`/`failed`), return intent
   unchanged.
2. **`side_effect_applied` flag** (lines 295, 311): set in a
   separate `update_intent` call AFTER `_apply_*` returns. Guards
   side-effect application from being repeated.

### **`side_effect_applied` is set in a SEPARATE update after `_apply_*` returns**

Sequence (success path, lines 291-298):
1. Set `status="succeeded"` + `confirmed_ts` → first `update_intent`
2. If not `side_effect_applied`: call `_apply_succeeded(user, kind, intent)`
3. Set `side_effect_applied=True` → second `update_intent`

**Edge case:** if `_apply_succeeded` partially completes and
raises between the two updates, status is already "succeeded" in
storage but side effects only partially applied. On redelivery,
the terminal-state check (step 1's check) matches and returns
early — **side effects are NOT retried**. Partial state persists
and requires operator-side reconciliation.

This is **documented design**, not a bug. The two-update pattern
records the fact that side effects ran (for audit) — it is NOT a
guard against partial application.

### Multi-store atomicity is unguarded

No try/except wraps the multi-store writes in `_apply_*` (except
for the cap-race `ValueError` catch around `add_member`).

**Worst-case failure mode: cohort-slot leak via `set_membership` failure.**

If `_apply_succeeded` for `membership_activation`:
1. `membership_store.add_member(user)` succeeds → cohort slot consumed
2. `users_store.set_membership(...)` raises (Firestore error)
3. `_apply_succeeded` aborts; `side_effect_applied` never set
4. Webhook handler doesn't run the second `update_intent`; status
   stays "succeeded" from the first update

On Stripe redelivery:
- Terminal-state check (line 286-287) sees `status="succeeded"`
- Returns early without retrying side effects
- **Cohort slot remains consumed; user document missing membership
  fields**

### Failure modes by write site

| Failure at | Resulting state | Recovery |
|---|---|---|
| `add_member` raises non-ValueError | No cohort consumed; intent stays "succeeded but partially applied" | Redelivery silenced by terminal-state check |
| `add_member` raises `ValueError` (cap race) | Caught: `failed_payment` tx + `billing_state="failed"` recorded; early return | side_effect_applied set; intent finalized |
| `set_membership` fails after add | **Cohort slot leaked; user document inconsistent** | Operator-side reconciliation |
| `set_billing_state` fails after set_membership | Membership set but billing_state not | Operator-side |
| `record_transaction` fails (last write) | All user-facing state correct; transaction log missing one entry | Detectable via audit |

### Race protection: `add_member` cap-fill

Lines 391-402 wrap `add_member` in `try/except ValueError`. On
race (cohort filled between intent creation and webhook):
- Writes `failed_payment` transaction with `race: True` flag
- Sets `billing_state="failed"` on user
- Returns early

`side_effect_applied=True` is still set by the caller (line 297)
because the failure-handling side effect DID run.

### Renewal failure state machine

Per `_apply_failed` for `membership_renewal`:

```
Failure 1: active → past_due,    retry_count=1, renewal_ts = +24h
Failure 2: past_due → past_due,  retry_count=2, renewal_ts = +24h
Failure 3: past_due → grace_period, retry_count=3, renewal_grace_until_ts = +24h
```

The `grace_period → cancelled` transition lives in
`billing_renewal.py`, NOT here.

### Webhook handler does NOT raise

`handle_payment_webhook` is the ONE public function that does not
raise `BillingError`. Returns `{ok: False, error: ...}` envelopes
for `"bad_event"`, `"no_intent_id"`, `"intent_not_found"`. This is
deliberate — Stripe webhook delivery requires non-raising
semantics so the HTTP layer can always return 200 to Stripe
(failures handled out-of-band via logs + audit).

### `client_secret` storage is intentional

The intent record stores `client_secret` (Stripe-issued in real
mode; synthesized in mock). The record is returned by
`create_payment_intent` to enable client-side confirmation via
Stripe.js.

**HTTP exposure caveat:** endpoints that LIST intents
(`/me/billing/history`, `/membership/g/history`, etc.) MUST filter
`client_secret` from responses to clients. This module does NOT
filter — caller-side responsibility.

**PASS-4 follow-up (carries forward from Batch-25):** audit
`app.py`'s intent-listing handlers to verify `client_secret` is
stripped before serializing to HTTP responses.

### No metadata sanitization

Like `membership_store`, this module does NOT call
`billing_config._sanitise_meta` or any equivalent. Metadata passes
through `_validate_inputs` only for the 4 documented fields
(`user_id`, `amount`, `description`, `kind`); the `metadata` dict
is unconstrained.

Callers must NOT place PII in `metadata`. The dict goes to:
- `stripe.PaymentIntent.create(..., metadata=md, ...)` in stripe
  mode (line 192) — Stripe sees it
- `membership_store.record_intent(record)` (line 208) — stored
  verbatim
- `membership_store.record_transaction(..., metadata={...})`
  (multiple sites in `_apply_*`) — stored verbatim

### No Stripe customer caching

The module does NOT cache `customer_id` per user. Each
PaymentIntent is created fresh. Typical Stripe integrations cache
customer ids for receipts and recurring billing — this module
defers that responsibility to either the user document (if a
caller wants to add it) or to Stripe's own metadata-driven
identification.

### Caller-side contracts (documented but not enforced)

1. **Use canonical `kind` strings** — `_validate_inputs` enforces
   `VALID_KINDS` membership; downstream consumers rely on these
   specific strings.
2. **Do not put PII in `metadata`** — no sanitization layer here.
3. **HTTP layer must strip `client_secret`** from list-intent
   responses (the create/confirm path needs it; list paths must
   not echo it).
4. **Operator-side reconciliation** is required for multi-store
   partial-failure cases. The module logs every operation via
   `v29_hardening.log_event` for audit trail.
5. **Same `intent_id`** between create and confirm/fail — caller
   responsibility to thread it through.
6. **Stripe mode requires both env key AND SDK installed** — early
   `BillingError` if either is missing.
7. **HTTP surfaces** — See [docs/billing.md](billing.md) for the
   HTTP-layer invariants governing client-secret exposure, metadata
   discipline, and diagnostic vs simplified billing views.

## Non-goals

`billing_intents` is **not**:

- a Stripe SDK wrapper — that's `billing.py` (webhook signature
  verification, etc.);
- a webhook signing layer — signature verification is delegated to
  `billing.verify_webhook`; this module consumes the parsed event
  dict;
- a billing-state machine root — billing_state lives on the user
  record in `users_store`; this module only writes transitions for
  the renewal-failure path;
- a renewal scheduler — `billing_renewal.py` runs the daemon
  thread; this module owns only the renewal-policy constants and
  the `calculate_next_renewal_ts` helper;
- a metadata sanitizer — like `membership_store`, accepts arbitrary
  metadata dicts; PII discipline is caller-side;
- a Stripe customer cache — no `customer_id` field stored per user;
- a kind/status validator beyond what's documented — `VALID_KINDS`
  is the only enforced membership constraint; intent `status` and
  `kind` are stored as plain strings;
- an exactly-once delivery guarantor — at-least-once semantics with
  two-tier idempotency (terminal-state check + side_effect_applied);
- a transaction (DB) coordinator — single-document atomicity per
  store call; multi-store coordination is best-effort with
  documented failure modes;
- a #G credit ledger — credits live in `users_store`; this module
  only triggers `add_g_credits` calls on successful credit
  purchases;
- a kernel reasoning mode — no `intelligence_kernel` coupling;
- an HTTP service — routes live in `app.py`.

## Fiction removed

The following constructs are explicitly not present in
`billing_intents.py` and must not be inferred:

- **No multi-store transactions.** Multi-store writes are
  best-effort with documented partial-failure modes (cohort-slot
  leak being the worst case).
- **No retry on transient failures.** If `set_membership` raises
  due to a transient Firestore error, no retry happens at this
  layer.
- **No rollback / compensating writes.** If a downstream write
  fails after an upstream succeeded, the upstream is NOT undone.
  Operator-side reconciliation.
- **No exception wrapping** around the `_apply_*` writes. Only the
  cap-race `ValueError` around `add_member` is caught.
- **No invariant validation on store transitions.** A `succeeded`
  event after a `failed` event silently overwrites. Last event
  wins.
- **No durability of in-process intent state.** Records persist
  via `membership_store` — restart-safe. The mode flag and
  idempotency state are computed per-call from env + stored
  record, not cached.
- **No `_FORBIDDEN_META_KEYS`-style PII filter.** Caller-side
  discipline.
- **No Stripe customer caching.** Each PaymentIntent is created
  fresh.
- **No `client_secret` redaction.** The create path returns it
  intentionally; list paths in `app.py` must filter.
- **No webhook signature verification.** Delegated to
  `billing.verify_webhook` — called by `app.py`'s webhook route
  before the parsed event reaches `handle_payment_webhook`.
- **No retry on webhook delivery failure.** If
  `handle_payment_webhook` returns `{ok: False, ...}`, the HTTP
  layer surfaces a non-200 to Stripe, triggering Stripe's own
  redelivery — at-least-once on Stripe's side.
- **No multi-currency support.** All amounts are USD (line 191).
- **No partial refund handling.** The `_apply_failed` paths record
  failures but do not initiate refunds; refund flow is out of v31
  scope (per inline comment at line 395-396).
- **No subscription lifecycle.** PaymentIntents are one-shot per
  call; `membership_renewal` creates a new intent rather than
  using Stripe subscriptions.
- **No mode-flag validation** in `_mode()` — accepts any lowercase
  string from env. Only `"stripe"` triggers the real-Stripe branch;
  any other value (including `"mock"`, `"disabled"`, or typos like
  `"strpe"`) falls through to the mock branch.

Only the behaviour, fields, and integrations described in this
document are present in the code. The verified surface is locked
by `tests/test_v31_billing.py` and `tests/test_v42_billing_hardening.py`.
