# Billing Config

## Purpose

`billing_config` is the **configuration and event-tracking layer**
for ClarityOS billing. It centralises Stripe mode/key resolution,
provides webhook idempotency tracking, maintains a recent-events
ring buffer for the founder console, and sanitises billing-event
metadata to keep PII out of the event log.

It is the v42 hardening of the v2 `STRIPE_*` env-var contract: the
new `CLARITYOS_STRIPE_*` names take precedence when both are set,
and the legacy names remain as backward-compatible fallbacks. The
module is consumed by `app.py`'s webhook handler, founder status
endpoint, and `/me/billing` route; by `founder_analytics` for mode
reporting; and by `entitlement_view` for billing-status projection.

It is a **single-file, stateful infra module** with no persistence
of its own. The seen-event set and recent-events ring buffer live
in-process and are cleared on restart.

It is the detail companion to the broader `docs/billing.md`
subsystem overview, which covers `billing.py`, `billing_intents.py`,
and `billing_renewal.py` alongside this module.

## Implementation location

- **File:** `billing_config.py` (238 lines, single file).
- **Version:** `STRIPE_VERSION = "billing_config.v42.1"` (line 46).
- **No package directory**, no `__init__.py`, no `__all__`.
- **No external spec** — this document plus `docs/billing.md` are
  the authoritative contract.
- **Imports** (stdlib only): `logging`, `os`, `time`,
  `collections.deque`, `typing.Any`, `typing.Optional`.
- **No upstream subsystem dependencies.** Deep leaf alongside
  `users_store`, `azimuth.py`, `orchestrator_schemas`,
  `ambient_trust_schemas`.

## Persistence model

`billing_config` has **no external persistence**. All state is:

- **In-memory** — Python set and deque
- **Process-local** — not shared across workers
- **Lost on restart** — no durability
- **Resettable** via `_reset_for_tests()` for the test suite

### Implications

- **Stripe webhook redelivery after a restart will re-process
  events.** The in-process `_seen_event_ids` set does not survive
  restart; idempotency falls through to the downstream handler's
  `side_effect_applied` flag (documented in `docs/billing.md`).
- **Recent-event history is ephemeral.** The `/founder/billing/status`
  endpoint surfaces only events from the current process lifetime.
- **Idempotency is best-effort, not durable.** At-least-once
  delivery semantics; exactly-once requires downstream handlers to
  be idempotent.

## Data model

`billing_config` defines **no dataclasses, no enums, no
TypedDicts**. Its "data model" consists of two in-memory state
items and two output dict shapes.

### Module state

**`_recent_events: deque[dict]`** (line 53)
- Fixed-size ring buffer via `deque(maxlen=_RECENT_EVENTS_MAX)`
  where `_RECENT_EVENTS_MAX = 50`
- Newest events appended to the **left** (`appendleft` at line 177)
- Oldest events automatically evicted when capacity exceeded

**`_seen_event_ids: set[str]`** (line 54)
- Cap: `_seen_event_max = 5000` (line 55)
- **Arbitrary-order eviction** via `set.pop()` when cap exceeded —
  NOT FIFO (see §Invariants for the corrected claim)

### Event record shape

Each entry in `_recent_events` has 6 fields (lines 169-176):

```python
{
    "ts":           float,           # time.time() at recording moment
    "event_type":   str,             # arg, str-coerced
    "user_id":      Optional[str],   # None if arg was falsy
    "event_id":     Optional[str],   # None if arg was falsy
    "mode":         str,             # arg, defaults to current get_stripe_mode()
    "payload_meta": dict,            # sanitised via _sanitise_meta
}
```

### `get_billing_status()` output shape

6 fields (lines 110-122):

```python
{
    "mode":               str,        # from get_stripe_mode()
    "has_secret":         bool,       # bool(get_secret_key())
    "has_webhook_secret": bool,       # bool(get_webhook_secret())
    "live_mode":          bool,       # mode == "live"
    "billing_enabled":    bool,       # mode in VALID_MODES
    "version":            str,        # STRIPE_VERSION
}
```

**Privacy guarantee:** the actual key is never returned — only
booleans and the mode label.

### Public constants (2)

- `STRIPE_VERSION: str = "billing_config.v42.1"` (line 46) —
  embedded in `get_billing_status()` output.
- `VALID_MODES: tuple = ("test", "live")` (line 47) — the canonical
  Stripe-mode tuple. Note: `"disabled"` is NOT in this tuple;
  `is_billing_enabled()` uses membership in `VALID_MODES` as its
  truth condition.

### Private constants

- `_RECENT_EVENTS_MAX = 50` (line 51) — ring buffer cap
- `_seen_event_max = 5000` (line 55) — seen-set cap
- `_SAFE_META_MAX_STR = 200` (line 195) — string truncation cap
- `_FORBIDDEN_META_KEYS: frozenset` (line 196-199) — 7 entries; see
  §Invariants for full enumeration

## APIs / entrypoints

### Configuration & mode resolution (6 functions)

| Function | Line | Returns |
|---|---|---|
| `get_secret_key()` | 61 | `Optional[str]` — `CLARITYOS_STRIPE_SECRET_KEY` then `STRIPE_SECRET_KEY` |
| `get_webhook_secret()` | 70 | `Optional[str]` — `CLARITYOS_STRIPE_WEBHOOK_SECRET` then `STRIPE_WEBHOOK_SECRET` |
| `get_stripe_mode()` | 78 | `str` — `"test"` / `"live"` / `"disabled"` (4-path resolution; see §Invariants) |
| `is_billing_enabled()` | 101 | `bool` — `True` iff `get_stripe_mode() ∈ VALID_MODES` |
| `is_live_mode()` | 106 | `bool` — `get_stripe_mode() == "live"` |
| `get_billing_status()` | 110 | `dict` — 6-field status snapshot (see §Data model) |

### Idempotency (2 functions)

| Function | Line | Returns | Purpose |
|---|---|---|---|
| `seen_event(event_id)` | 128 | `bool` | `True` iff `event_id` is in `_seen_event_ids` |
| `mark_event_seen(event_id)` | 135 | `None` | Add `event_id` to set; arbitrary-order eviction on cap overflow |

Both functions return early (no-op) for falsy `event_id` (None, empty string).

### Event logging (3 functions)

| Function | Line | Returns |
|---|---|---|
| `record_billing_event(event_type, *, user_id=None, payload_meta=None, event_id=None, mode=None)` | 155 | `dict` — the recorded entry |
| `list_recent_events(*, limit=50)` | 181 | `list[dict]` — newest-first, capped at `min(limit, 50)`, returns dict copies |
| `last_event_ts()` | 186 | `Optional[float]` — timestamp of newest event, or `None` if buffer is empty |

`record_billing_event` signature: `event_type` is positional;
everything else is **keyword-only**. `payload_meta` is sanitised
via `_sanitise_meta` before storage; `mode` defaults to the current
`get_stripe_mode()` if not supplied.

### Sanitization (private, but externally consumed)

| Symbol | Line | Notes |
|---|---|---|
| `_sanitise_meta(meta) -> dict` | 202 | **Private but accessed by `app.py:1297`** — see §Invariants |
| `_coerce_meta_value(v) -> Any` | 217 | Internal recursive helper |
| `_FORBIDDEN_META_KEYS: frozenset` | 196 | 7-entry forbidden set; see §Invariants |
| `_SAFE_META_MAX_STR: int = 200` | 195 | String truncation cap |

### Test helper

| Symbol | Line | Notes |
|---|---|---|
| `_reset_for_tests()` | 236 | Clears both state items; called by `tests/conftest.py` |

## Integration points

### Production importers (3)

| Importer | Surface consumed |
|---|---|
| `app.py:104` | Major consumer — webhook idempotency (`seen_event`, `mark_event_seen`, `record_billing_event`), mode resolution (`get_stripe_mode`, `VALID_MODES`), founder status (`get_billing_status`, `list_recent_events`, `last_event_ts`), `/me/billing` (`get_billing_status`), and direct `_sanitise_meta` call from webhook PII filter |
| `founder_analytics.py:26` | `get_stripe_mode()` only — for the `mode` field in `get_founder_analytics_summary` |
| `entitlement_view.py:34` | `get_billing_status()` only — extracts `["mode"]` for the entitlement projection's `billing_mode` field |

### HTTP coupling (no routes inside billing_config)

`billing_config` defines no HTTP routes. It is consumed by routes
defined in `app.py`:

- **Stripe webhook handler** (`POST /billing/webhook`, app.py:1174+) —
  the full idempotency + recording pipeline
- **`GET /founder/billing/status`** (app.py:10434) — surfaces
  `get_billing_status()`, `list_recent_events(50)`, `last_event_ts()`
- **`GET /me/billing`** (app.py:12329) — surfaces
  `get_billing_status()`

### No coupling to
- `intelligence_kernel`, `model_router`, LLM SDKs — none imported
- `memory_vault`, `operator_state` — none imported
- File I/O, network — neither directly (Stripe SDK calls live in `billing.py`)

### Tests (2 files)

- `tests/test_v42_billing_hardening.py` — primary SUT covering all
  4 surface areas
- `tests/conftest.py` — shared fixture (calls `_reset_for_tests`)

### Environment variables

| Variable | Precedence | Purpose |
|---|---|---|
| `CLARITYOS_STRIPE_MODE` | 1st | Explicit mode override (`"test"` / `"live"`) |
| `CLARITYOS_STRIPE_SECRET_KEY` | 1st (key) | Stripe secret key (v42 canonical) |
| `STRIPE_SECRET_KEY` | 2nd (key fallback) | Legacy v2 name |
| `CLARITYOS_STRIPE_WEBHOOK_SECRET` | 1st (webhook) | Webhook signing secret |
| `STRIPE_WEBHOOK_SECRET` | 2nd (webhook fallback) | Legacy v2 name |

## Invariants

### Stripe mode resolution — 4-path contract

`get_stripe_mode()` resolves via the following precedence (lines
78-98). The module docstring at line 16 lists only 3 outcomes;
the actual surface has 4 paths:

| # | Condition | Returned mode |
|---|---|---|
| 1 | `CLARITYOS_STRIPE_MODE ∈ VALID_MODES` | the explicit value |
| 2 | key starts with `sk_live_` | `"live"` |
| 3 | key starts with `sk_test_` | `"test"` |
| 4 | key present but unrecognised prefix | `"test"` (implicit fallback — "safer default than live") |
| 5 | no key | `"disabled"` |

**Path 4 is the load-bearing implicit fallback** that the docstring
omits. Any future change to mode-resolution logic must preserve the
fail-to-test-not-live default; the founder console surfaces the
unrecognised-prefix case via `get_billing_status`'s `live_mode`
field.

### `get_stripe_mode()` and `get_billing_status()["mode"]` cannot drift

`get_billing_status` calls `get_stripe_mode` directly at line 114.
They share logic; they cannot diverge.

### Idempotency — at-least-once semantics

- `seen_event` is a **fast-path optimization**, not the only
  duplicate-prevention mechanism.
- If processing fails between `seen_event` check and
  `mark_event_seen`, the event id is NOT marked; Stripe retry will
  re-process the event.
- Exactly-once semantics depend on downstream handlers being
  idempotent (per the `side_effect_applied` flag pattern documented
  in `docs/billing.md`).
- **Seen-set eviction is arbitrary-order, NOT FIFO.** `set.pop()`
  removes an arbitrary element (lines 144-149). New ids continue
  to be tracked, but any single id may be evicted at any time once
  the cap is reached.

### Event ring buffer semantics

- Newest events at the **left** (`appendleft`).
- Oldest events evicted automatically by `deque(maxlen=50)`.
- `list_recent_events(limit)` clamps `limit` to `[1, 50]`, returns
  newest-first as **dict copies** (callers cannot mutate internal
  records).
- `last_event_ts()` returns the timestamp of `_recent_events[0]`
  (the newest), or `None` if buffer empty. The trailing `or None`
  at line 189 means a recorded `ts == 0.0` would be treated as
  "no event" — edge case, not exercised in normal operation.

### Privacy contract — 7 forbidden meta keys

`_FORBIDDEN_META_KEYS` (line 196-199):

```python
frozenset({
    "card",            # Stripe card object
    "payment_method",  # Stripe payment-method object
    "customer",        # Stripe customer id
    "client_secret",   # Stripe client secret
    "raw",             # generic raw-payload field
    "email",           # PII
    "phone",           # PII
})
```

### Sanitization rules (`_sanitise_meta` + `_coerce_meta_value`)

- **Non-dict input** to `_sanitise_meta` → returns `{}` (no error,
  no log)
- **Non-string keys** → silently dropped
- **Forbidden keys** → silently dropped (at both top level AND
  inside nested dicts — the recursive case re-applies the filter)
- **Strings** → truncated to `_SAFE_META_MAX_STR = 200` chars
- **`int` / `float` / `bool` / `None`** → passthrough unchanged
- **Lists / tuples** → recursed and capped at 20 elements
- **Dicts** → recursed, with forbidden-key filter at the nested level
- **Anything else** → stringified via `str(v)`, then truncated to
  200 chars

### `_sanitise_meta` is intentionally accessed externally

`app.py:1297` calls `billing_config._sanitise_meta` directly — a
**private function (underscore prefix) accessed across module
boundaries**. This is documented in `docs/billing.md` as part of
the webhook PII filter and is intentional, not a leak. PASS-4
notes it explicitly so future readers understand the
underscore-prefix is not a forbidden-access marker here.

### Logging — declared but unused

`logger = logging.getLogger("clarityos.billing_config")` (line 44)
is declared, but **no `logger.*` calls anywhere in the module
body**. Same pattern as `elins_dashboard.py`. PASS-4 candidate for
either cleanup or intentional documentation.

### Caller-side contracts

The following are caller obligations, not enforced by the module:

1. **Do not rely on FIFO semantics for `seen_event` eviction.**
   The set uses arbitrary-order eviction; any specific id may be
   dropped without notice once the cap is reached.
2. **Do not assume the recent-events ring is persistent.** It is
   cleared on every process restart; downstream consumers should
   not depend on full event history being available.
3. **Do not store sensitive PII in `payload_meta`.** Sanitization
   will drop forbidden keys and truncate long strings, but defence
   in depth is the caller's responsibility — pre-filter before
   calling `record_billing_event`.
4. **Do not expect `last_event_ts()` to reflect event payload
   timestamps.** It returns the **recording time** (`time.time()`
   at `record_billing_event` invocation), not the timestamp inside
   the Stripe event payload.

## Non-goals

`billing_config` is **not**:

- a Stripe API caller — that lives in `billing.py`;
- a webhook signature validator — `stripe.Webhook.construct_event`
  is called from `app.py`'s webhook handler;
- a billing engine — renewal logic is in `billing_renewal.py`,
  PaymentIntent flow is in `billing_intents.py`;
- a persistent event log — the recent-events ring is in-process
  only; durable transaction records live in `membership_store`;
- a billing-state machine — that lives on the user record via
  `users_store.set_billing_state`;
- an exactly-once delivery guarantor — the at-least-once
  semantics require downstream idempotency;
- a kernel reasoning mode — no `intelligence_kernel` coupling;
- an HTTP service — no routes defined inside this module;
- a configuration store — env-var reads only, no overrides
  persisted;
- a secrets manager — keys are read from env vars; `get_billing_status`
  never returns the actual keys, only presence booleans.

## Fiction removed

The following constructs are explicitly not present in
`billing_config.py` and must not be inferred:

- **No FIFO eviction.** The seen-event set uses `set.pop()` which
  removes an arbitrary element. `docs/billing.md`'s "FIFO" claim
  (line 98) was wrong and is corrected by this PASS-4 alongside
  the targeted edit to that file.
- **No 3-mode resolution.** The module docstring lists `"test" |
  "live" | "disabled"` but the actual surface has 4 paths
  (including the implicit-test-fallback for unrecognised key
  prefixes). PASS-4 pins the full 4-path table.
- **No 4-element PII filter.** `_FORBIDDEN_META_KEYS` has 7
  entries, not the 4 listed in `docs/billing.md:99`. PASS-4
  corrects that doc with the full 7-key enumeration.
- **No durable idempotency.** The seen-event set is in-process
  only. Stripe redelivery after restart will re-process events;
  exactly-once relies on downstream handlers.
- **No Stripe API calls.** This module is configuration + event
  tracking only. Stripe SDK calls live in `billing.py` (subscription
  events) and `billing_intents.py` (PaymentIntent flow).
- **No HTTP routes.** The 3 billing routes live in `app.py`.
- **No persistence layer.** Both `_recent_events` and
  `_seen_event_ids` are in-process Python collections, cleared on
  restart.
- **No LLM, kernel, vault, or operator_state coupling.** Pure infra
  module.
- **No file I/O, no network I/O** at this layer.
- **No used logger.** The logger is declared but never invoked.
- **No exception-raising path** in `_sanitise_meta` for malformed
  input — non-dict inputs return `{}` silently.
- **No return of actual keys** from `get_billing_status` — only
  booleans and the mode label.
- **No mode-disagreement** between `get_stripe_mode()` and
  `get_billing_status()["mode"]` — they share logic.

Only the behaviour, fields, and integrations described in this
document are present in the code. The verified surface is locked
by `tests/test_v42_billing_hardening.py` and the 3 production
importers documented in §Integration points.
