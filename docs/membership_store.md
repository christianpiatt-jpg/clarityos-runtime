# Membership Store

## Purpose

`membership_store` is the **cohort + transaction + PaymentIntent
persistence layer** for ClarityOS membership. It holds three
independent persistence layers:

1. **Cohort state** — single-document blob per cohort name (e.g.,
   `founding_500`) carrying active member list, waitlist, and
   active count.
2. **Per-user transaction log** — append-only history of
   activations, cancellations, and #G credit purchases / consumes,
   capped at 1000 entries per user.
3. **PaymentIntent records** — v31 PaymentIntent persistence,
   keyed globally by `intent_id`.

It does **not** manage per-user membership fields (tier, status,
price, started/cancelled timestamps, g_credits, g_credit_history) —
those live in `users_store`. The split is deliberate: this module
owns the cohort-level and transaction-level state; `users_store`
owns the per-user document.

It is a **single-file, stateful infra module** structurally
analogous to `users_store` and `billing_config` — same backend
dispatch pattern, same lazy Firestore client, same module-level
mutable state. It is the detail companion to `docs/membership.md`,
which is the broader subsystem doc covering this module +
`membership_billing.py` + `entitlement_view.py` + `invites_store.py`
together.

## Implementation location

- **File:** `membership_store.py` (332 lines, single file).
- **No package directory**, no `__init__.py`, no `__all__`.
- **No external spec** — this document plus `docs/membership.md`
  are the authoritative contract.
- **No explicit version anchor** — the v31 PaymentIntent additions
  are commented inline (e.g., line 50, line 67, line 251) but no
  module-level `STORE_VERSION` constant.
- **Imports** (stdlib only at top level): `logging`, `os`, `time`,
  `typing.Optional`. The `google.cloud.firestore` import is lazy
  (inside `_get_firestore`), so memory-mode deployments do not
  require the package to be installed.
- **No upstream subsystem dependencies.** Deep leaf alongside
  `users_store`, `billing_config`, the schema files.

## Persistence model

### Backend selection

`CLARITYOS_BACKEND` environment variable, read **per-call** by
`_backend()` (line 61-62). Same pattern as `users_store`:

- `memory` (default) — three module-level dicts
- `firestore` — three Firestore collections, lazy client

### Three persistence layers

| Layer | Memory state | Firestore collection | Key |
|---|---|---|---|
| Cohorts | `_MEMORY_COHORTS: dict[str, dict]` (line 65) | `membership_cohorts` (line 48) | cohort name (e.g., `"founding_500"`) |
| Transactions | `_MEMORY_TX: dict[str, list]` (line 66) | `membership_transactions` (line 49) | username |
| Intents | `_MEMORY_INTENTS: dict[str, dict]` (line 67) | `membership_payment_intents` (line 50) | `intent_id` (global, not per-user) |

### Architectural asymmetry across layers

- **Cohort and transaction layers** use 4 helper primitives
  (`_load_cohort`, `_save_cohort`, `_load_tx`, `_save_tx`) that
  dispatch on `_backend()`. The public functions in these layers
  compose through the helpers without re-branching.
- **Intent layer** has no helpers — each of the 4 public intent
  functions (`record_intent`, `get_intent`, `update_intent`,
  `list_intents_for_user`) branches on `_backend()` directly.

The asymmetry is defensible: cohort/transaction operations share a
read-then-modify-then-write pattern that benefits from helpers;
intent operations are more varied (set, get, merge-update,
filtered query) and don't share a clean pattern.

### Lazy Firestore client

- `_firestore_client = None` at module load (line 68)
- `_get_firestore()` (lines 71-83) initializes on first use; caches
  thereafter
- ImportError if `google-cloud-firestore` is not installed →
  RuntimeError with actionable message
- Logged at init: `"membership_store firestore client initialised"`
  (line 82) — the ONLY logger call in the module

### State scope and reset

- All three memory dicts plus `_firestore_client` are
  module-level state
- `_reset_memory_for_tests()` (line 329-332) clears all three
  memory dicts; does NOT clear `_firestore_client` (intentional —
  tests shouldn't hit real Firestore)
- No persistence beyond the backend; nothing written to disk by
  this module itself

### Backend parity

Verified across all 3 collections:
- **Cohorts:** memory uses `dict(blob)` copies; Firestore uses
  `_cohort_doc(name).set(blob)`. Read normalizes Firestore data to
  the 3-field shape at lines 102-107.
- **Transactions:** memory uses `list(txs)` copies; Firestore wraps
  in `{"transactions": txs}` and unwraps on read (line 198).
- **Intents:** memory uses `dict(intent_record)` copies; Firestore
  uses direct document `set()`. Both backends use `dict(rec)` /
  `doc.to_dict()` on read so callers cannot mutate internal state.

Missing-record behavior is identical across both backends:
- `_load_cohort` returns `_empty_cohort()` for missing cohorts
- `_load_tx` returns `[]` for unknown users
- `get_intent` returns `None` for unknown ids
- `list_intents_for_user` returns `[]` for users with no intents

## Data model

`membership_store` defines **no dataclasses, no enums, no
TypedDicts**. Three data shapes are managed as plain dicts.

### Cohort blob (3 fields)

```python
{
    "active_count": int,                                    # invariant: == len(members)
    "members":      list[str],                              # active usernames
    "waitlist":     list[{"username": str, "ts": float}],   # FIFO append order
}
```

- **`active_count` is redundant** with `len(members)`. The
  redundancy is intentional per the module docstring (line 14):
  "Stored as a single document so the cap check is one read." Both
  `add_member` (line 148) and `remove_member` (line 161)
  synchronize the count on every write.
- **`members` is append-only with hole-preserving removal**: order
  is "insertion order with holes from removals." Not contiguous
  after cancellations.
- **`waitlist` is FIFO by append order**, NOT by `ts` sort. The
  1-indexed `waitlist_position` derives from list index, which IS
  chronological because append order matches time order.

### Transaction record (6 fields)

```python
{
    "user":          str,                  # username
    "type":          str,                  # str-coerced
    "amount":        float,                # USD, float-coerced
    "credits_delta": int,                  # +1, +20, -1, 0
    "metadata":      dict,                 # caller-controlled, NOT sanitized
    "ts":            float,                # strictly monotonic
}
```

**Strictly-monotonic `ts` enforcement** (lines 220-227):

```python
now = time.time()
if txs:
    last_ts = float(txs[-1].get("ts", 0.0) or 0.0)
    if now <= last_ts:
        now = last_ts + 1e-6
```

The Windows-resolution workaround: `time.time()` on Windows can
return identical floats for back-to-back calls. Without the
adjustment, "newest first" sorting ties to insertion order and the
contract becomes flaky. The `last_ts + 1e-6` bump guarantees
strict monotonicity within a single user's log.

### PaymentIntent record (13 fields)

```python
{
    "intent_id":           str,                          # REQUIRED — raises ValueError on missing
    "user":                str,
    "kind":                str,                          # see canonical kinds below
    "amount":              float,
    "description":         str,
    "metadata":            dict,                         # caller-controlled, NOT sanitized
    "status":              str,                          # see canonical statuses below
    "client_secret":       Optional[str],                # ⚠ INTENTIONALLY STORED — see §Invariants
    "mode":                str,                          # mock | stripe
    "created_ts":          float,
    "confirmed_ts":        Optional[float],
    "failed_ts":           Optional[float],
    "side_effect_applied": bool,                         # caller-managed idempotency guard
}
```

**`record_intent` validates ONE field only**: `intent_id` must be
truthy (lines 280-282; raises `ValueError("intent_id required")`).
The other 12 fields are not validated — the function accepts any
dict and stores whatever is passed.

### Canonical strings (documented but NOT enforced)

The module docstring (line 21-22) lists 5 canonical transaction
type values:

```
"membership_activate", "membership_cancel",
"g_buy_single", "g_buy_pack_20", "g_consume"
```

The PaymentIntent comment block (lines 260-265) lists canonical
kind and status values:

- `kind ∈ {"membership_activation", "membership_renewal",
  "g_credit_single", "g_credit_pack"}`
- `status ∈ {"requires_payment_method", "processing",
  "succeeded", "failed", "canceled"}`

**None of these are enforced.** `record_transaction` accepts any
string via `str(type)`; `record_intent` accepts any dict. Callers
are expected to use the canonical values; the module does not
validate.

### Public constants (5)

- `FOUNDING_COHORT: str = "founding_500"` (line 53) — consumed by
  `entitlement_view`, `app.py`, `users_store` field values
- `FOUNDING_CAP: int = 500` (line 54) — cohort capacity ceiling;
  enforced ONLY for `FOUNDING_COHORT`
- `FOUNDING_PRICE_LOCKED: float = 50.00` (line 55) — Founding
  cohort locked price
- `FOUNDING_FULL_PRICE: float = 150.00` (line 56) — post-cohort
  reactivation price (cancelling forfeits the locked price)
- `MAX_TX_PER_USER: int = 1000` (line 58) — transaction-log
  truncation cap per user

### Private constants

- `_COHORT_COLL = "membership_cohorts"` (48)
- `_TX_COLL = "membership_transactions"` (49)
- `_INTENT_COLL = "membership_payment_intents"` (50)

## APIs / entrypoints

### Cohort management (7 public functions)

| Function | Line | Returns | Notes |
|---|---|---|---|
| `get_cohort_state(name=FOUNDING_COHORT)` | 122 | `dict` — 6-field summary | Always returns a dict; `cap` and `remaining` are `None` for non-founding cohorts |
| `is_cohort_full(name=FOUNDING_COHORT)` | 135 | `bool` | Wraps `get_cohort_state()["is_full"]`; only `True` for FOUNDING_COHORT at cap |
| `add_member(user, name=FOUNDING_COHORT)` | 139 | `dict` — updated cohort state | Raises `ValueError("already_member")` or `ValueError("cohort_full")`; auto-removes from waitlist on promotion |
| `remove_member(user, name=FOUNDING_COHORT)` | 155 | `dict` — updated cohort state | **Idempotent** (early return if not member) |
| `is_member(user, name=FOUNDING_COHORT)` | 166 | `bool` | Consumed by `entitlement_view._is_founding_member` |
| `add_to_waitlist(user, name=FOUNDING_COHORT)` | 170 | `dict` — updated cohort state | **Idempotent** (early return if already on waitlist) |
| `waitlist_position(user, name=FOUNDING_COHORT)` | 181 | `Optional[int]` | 1-indexed; `None` if not on waitlist |

### Transaction log (2 public functions)

| Function | Signature | Returns |
|---|---|---|
| `record_transaction` (line 210) | `(user, *, type, amount, credits_delta, metadata=None) -> dict` | The stored record (6 fields) |
| `list_transactions` (line 243) | `(user, *, limit=100) -> list` | Newest-first; clamped to `max(1, int(limit))` |

`record_transaction` is positional-`user` plus **all keyword-only** args. Enforces strictly-monotonic `ts` and reactive truncation at `MAX_TX_PER_USER = 1000`.

### PaymentIntent persistence (4 public functions, v31)

| Function | Signature | Returns |
|---|---|---|
| `record_intent` (line 278) | `(intent_record: dict) -> dict` | The stored record; raises `ValueError` if `intent_id` missing |
| `get_intent` (line 290) | `(intent_id: str) -> Optional[dict]` | Returns dict copy or None |
| `update_intent` (line 300) | `(intent_id, updates: dict) -> Optional[dict]` | Merge semantics; returns merged record or None if not found |
| `list_intents_for_user` (line 313) | `(user, *, limit=50) -> list` | Newest-first by `created_ts`; uses **4× over-fetch + Python sort** in Firestore mode |

### Private surface

- `_backend()` (61) — env-var read, per-call
- `_get_firestore()` (71) — lazy client init
- `_cohort_doc(name)`, `_tx_doc(user)`, `_intent_doc(intent_id)` — Firestore document getters
- `_empty_cohort()` — empty cohort blob factory
- `_load_cohort`, `_save_cohort`, `_load_tx`, `_save_tx` — backend dispatch helpers
- `_reset_memory_for_tests()` — test hook clearing all three memory dicts

## Integration points

### Production importers (5)

| Importer | Surface consumed |
|---|---|
| `app.py:85` | 22+ call sites: cohort cap checks (`is_cohort_full`, `add_to_waitlist`, `waitlist_position`), member management (`add_member`, `remove_member`, `is_member`), cohort state surfaces (`get_cohort_state`), transaction logging (`record_transaction`), transaction listings (`list_transactions`), intent CRUD (`get_intent`, `list_intents_for_user`), price constants (`FOUNDING_PRICE_LOCKED`, `FOUNDING_FULL_PRICE`), cohort identifier (`FOUNDING_COHORT`) |
| `entitlement_view.py:35` | **2 symbols only**: `is_member(user, FOUNDING_COHORT)` and `FOUNDING_COHORT` constant. Documented in [docs/entitlement_view.md](entitlement_view.md). |
| `billing_intents.py:57` | PaymentIntent CRUD + transaction logging (full surface for the v31 flow) |
| `billing_renewal.py:38` | Transaction logging + membership checks (renewal lifecycle) |
| `membership_billing.py:46` | **Legacy** per `docs/billing.md` — unimplemented placeholder superseded by the PaymentIntent flow |

### Tests (6 files)

- `tests/test_v30_membership.py` — primary SUT (cohort logic introduction)
- `tests/test_v31_billing.py` — coupled (PaymentIntent persistence)
- `tests/test_v32_waitlist.py` — coupled (waitlist functions)
- `tests/test_membership_confirm.py` — coupled (confirmation flow)
- `tests/test_entitlement_view.py` — coupled (via `entitlement_view`'s `is_member` call)
- `tests/conftest.py` — shared fixture (likely `_reset_memory_for_tests` hook)

### HTTP routes (none inside this module)

`membership_store` defines no HTTP routes. It is consumed by
`app.py` for:
- `POST /membership/activate`, `POST /membership/confirm`,
  `POST /membership/g/buy_single`, `POST /membership/g/buy_pack_20`,
  `GET /membership/g/history`
- Cohort and transaction queries via various `/me/*` and
  `/founder/*` endpoints

See `docs/membership.md` for the full HTTP-route enumeration.

### Cross-store ownership boundary

`membership_store` owns: cohort state, per-user transactions,
PaymentIntent records.

`users_store` owns: per-user membership fields (`membership_tier`,
`membership_price`, `membership_status`, `membership_started_ts`,
`membership_cancelled_ts`, `g_credits`, `g_credit_history`,
`membership_confirmed`, `membership_confirmed_ts`).

`app.py` coordinates writes across both stores within a single
flow. Atomic coordination across stores is **caller-side**; this
module guarantees only single-document atomicity within its own
collections.

### No coupling to
- `intelligence_kernel`, `model_router`, LLM SDKs — none imported
- `memory_vault`, `operator_state` — none imported
- `billing_config` — none imported (despite shared concern with
  Stripe events; the two modules are intentionally independent)

## Invariants

### Cohort invariants

- **`active_count == len(members)`** — synchronized at both
  `add_member` and `remove_member` write sites.
- **`FOUNDING_CAP = 500` enforced ONLY for `FOUNDING_COHORT`**
  (line 145). Other cohort names bypass the cap check. If future
  cohorts need caps, the check at line 145 must be generalized.
- **Member uniqueness** enforced via `add_member` raising
  `ValueError("already_member")` (lines 143-144).
- **Member ordering** is insertion-order with holes from removals
  — NOT contiguous after cancellations.
- **Waitlist is FIFO by append order**, not by `ts` sort.
- **Promotion auto-removes from waitlist** — `add_member` filters
  the user out of the waitlist when adding them to the cohort
  (line 150).
- **Reactivation is a free path** — `add_member` checks only
  current members, not history. A removed user can be re-added if
  the cohort isn't full.

### Transaction invariants

- **Strictly monotonic `ts`** via Windows-resolution-safe
  adjustment (`now = last_ts + 1e-6` at line 227). Determinism
  guaranteed even when `time.time()` returns identical floats on
  back-to-back calls.
- **`MAX_TX_PER_USER = 1000` truncation** is **reactive** — applied
  on each write at line 237-238. Truncates to newest-1000; drops
  oldest.
- **Listing order: newest-first** by `ts` descending
  (`list_transactions` line 245).
- **Firestore writes are full-overwrite**, not merge — the entire
  list per user is stored as one document with a
  `"transactions"` array (line 205).
- **All record fields are coerced**: `type` via `str()`, `amount`
  via `float()`, `credits_delta` via `int()`, `metadata` via
  `dict(metadata or {})`. `ts` is set by the function (never from
  caller).
- **No metadata sanitization** — see §Privacy below.

### Intent invariants

- **`intent_id` is the only required field** (raises ValueError
  otherwise).
- **No other field validation** — `record_intent` accepts any dict.
- **Updates are merge** (`update_intent` uses `existing.update(updates)`
  at line 305).
- **`update_intent` returns `None` for unknown ids** (does not
  raise).
- **Idempotency relies on caller-side `side_effect_applied` flag**
  (per the comment block at line 272). The module does not enforce
  side-effect tracking — that's the caller's responsibility.
- **`list_intents_for_user` uses 4× over-fetch + Python sort** in
  Firestore mode (line 318: `.limit(int(limit) * 4)`). Efficient
  for moderate intent lists; the multiplier is a heuristic that
  could miss results for users with many intents distributed
  unevenly across the index.

### Critical security invariant — `client_secret` storage is intentional

The PaymentIntent record schema includes `client_secret` (line 267
comment + persistence at lines 284/286). This is **documented
design**, not a leak:

- The Stripe-issued `client_secret` is needed to resume
  client-side payment confirmation.
- Storing it server-side enables `/billing/intent/confirm` flows
  without re-fetching from Stripe.
- The secret is per-intent (not per-customer) and short-lived.

**HTTP exposure must filter `client_secret` from responses to
clients.** The module stores it; the HTTP layer is responsible for
not echoing it back. PASS-4 verification follow-up: confirm that
`/membership/g/history`, `/me/membership/transactions`, and other
intent-listing endpoints in `app.py` strip `client_secret` before
returning to clients.

### Atomicity

- **Single-document writes are atomic** in both backends (Firestore
  document-level set, memory dict assignment).
- **Read-modify-write cycles are NOT atomic.** `add_member`,
  `remove_member`, `add_to_waitlist`, `record_transaction`, and
  `update_intent` all have a load → mutate → save cycle that is
  race-vulnerable to concurrent writes.
- **`add_member` is self-defending** — it re-checks the cap inside
  the function (line 145), limiting the blast radius of
  `is_cohort_full()` + `add_member()` races to a `cohort_full`
  raise (rather than over-cap state). But two concurrent
  `add_member` calls hitting the cap simultaneously is still a
  race.
- **No multi-document transactions.** Each function touches one
  document.
- **No optimistic locking.**

### Caller-side contracts (documented but not enforced)

1. **Use canonical transaction `type` strings**:
   `membership_activate`, `membership_cancel`, `g_buy_single`,
   `g_buy_pack_20`, `g_consume`. The module accepts any string;
   downstream consumers expect these.
2. **Use canonical intent `kind` strings**: `membership_activation`,
   `membership_renewal`, `g_credit_single`, `g_credit_pack`.
3. **Use canonical intent `status` strings**:
   `requires_payment_method`, `processing`, `succeeded`, `failed`,
   `canceled`.
4. **Do not put PII in `metadata`.** The module performs no
   sanitization — caller-side discipline only.
5. **Coordinate with `users_store` for membership fields.** This
   module owns cohort/transaction/intent state; the per-user
   membership fields (tier, status, price, timestamps) live in
   `users_store`. Atomic coordination across both stores is the
   caller's responsibility.
6. **Use the `side_effect_applied` flag for intent idempotency.**
   The module persists the flag but does not enforce it; the
   caller's webhook handler must check + set.
7. **Do not assume read-modify-write is atomic.** Concurrent
   writers can race; design around eventual consistency.

### G-credit non-negativity is enforced ELSEWHERE

The invariant "G-credit balance never goes negative" lives in
`users_store.consume_g_credit`, NOT in this module. `membership_store`
records transactions with `credits_delta` (which can be positive or
negative) but does not maintain the running balance. See
[docs/users_store.md](users_store.md) for the authoritative
contract.

## Non-goals

`membership_store` is **not**:

- a per-user membership state holder — `users_store` owns
  `membership_tier`, `membership_status`, `membership_price`,
  timestamps, and `g_credits`;
- a billing-state machine — billing state lives on the user
  record, managed by `users_store.set_billing_state`;
- a Stripe API caller — that lives in `billing.py` and
  `billing_intents.py`;
- a webhook handler — webhooks are processed in `app.py`'s
  `/billing/webhook` route; this module just persists what the
  handler decides to record;
- a PII sanitizer — unlike `billing_config._sanitise_meta`, this
  module trusts callers; `metadata` is stored verbatim;
- a transaction-type validator — accepts any string for `type`,
  `kind`, `status`;
- a #G credit ledger — credit balance lives in `users_store`; this
  module records only transaction history;
- an entitlement engine — projection of cohort + billing state
  into a feature dict lives in `entitlement_view`;
- a multi-document transaction coordinator — single-document
  atomicity only;
- an HTTP service — no routes inside this module;
- a kernel reasoning mode — no `intelligence_kernel` coupling.

## Fiction removed

The following constructs are explicitly not present in
`membership_store.py` and must not be inferred:

- **No automatic cohort-cap generalization.** `FOUNDING_CAP` is
  applied only to `FOUNDING_COHORT` (line 145). Other cohort
  names have no cap. Adding a new capped cohort requires extending
  the check at line 145.
- **No multi-document atomicity.** Each function touches one
  document; concurrent writers can race.
- **No optimistic locking, no compare-and-swap.** The
  read-modify-write pattern is vulnerable to lost updates under
  concurrent writes.
- **No enforcement of transaction or intent type strings.** All
  five canonical transaction types, four intent kinds, and five
  intent statuses are documented in code comments but not
  validated.
- **No PII sanitization.** Architectural asymmetry with
  `billing_config._sanitise_meta` (which has a 7-key forbidden
  set). If a caller passes email, phone, card data, or other
  sensitive fields in `metadata`, this module stores them
  verbatim.
- **No `client_secret` redaction.** The intent record stores the
  Stripe client_secret by design (v31). HTTP surfaces must filter
  it before returning to clients; this module does not.
- **No G-credit balance management.** Transactions record
  `credits_delta` but the running balance lives in `users_store`.
  The non-negative invariant is enforced by
  `users_store.consume_g_credit`, not here.
- **No automatic deduplication of transactions.** Two identical
  `record_transaction` calls produce two records (with different
  `ts` values due to the monotonic adjustment).
- **No intent expiry.** Records persist until the document is
  manually deleted or the memory store is reset; no TTL.
- **No background tasks.** No scheduler, no async, no thread.
- **No HTTP routes.** Routes live in `app.py`.
- **No kernel, vault, model_router, or operator_state coupling.**
- **No used logger except for Firestore init.** Single `logger.info`
  call at line 82; no warning, error, or exception logging.
- **No reactivation history.** `add_member` checks only current
  members, not historical removals. A user can cycle between
  cohort and non-cohort indefinitely without the module tracking
  the cycle count.

Only the behaviour, fields, and integrations described in this
document are present in the code. The verified surface is locked
by `tests/test_v30_membership.py`, `tests/test_v31_billing.py`,
`tests/test_v32_waitlist.py`, `tests/test_membership_confirm.py`,
and `tests/test_entitlement_view.py`.
