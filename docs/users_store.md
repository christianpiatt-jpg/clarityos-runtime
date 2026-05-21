# Users Store

## Purpose

`users_store` is the **identity persistence layer** for ClarityOS.
It owns the user document — a single dict per username covering
authentication credentials, membership, billing state, G-credits,
and onboarding state — and exposes a small CRUD surface backed by
either an in-process dict or Google Cloud Firestore.

It is one of the most-imported modules in the codebase: `app.py`
calls into it from 40+ sites across auth, billing, membership,
onboarding, and `/me`/`/founder` endpoints; `intelligence_kernel`,
`billing_renewal`, `billing_intents`, `founder_analytics`, and
`entitlement_view` all consume it as well.

The module is a **single-file CRUD layer**, structurally analogous
to `operator_state.py`. There is no schemas split, no engine/
schemas separation, no dataclasses, and no enums. The document
shape is a plain dict, documented in code and below — not encoded
as a TypedDict. Caller-side contracts replace structural
enforcement for everything except billing-state membership.

## Implementation location

- **File:** `users_store.py` (336 lines, single file).
- **No package directory**, no `__init__.py`, no `__all__`.
- **No external spec** — there is no `SPEC_USERS_STORE.md`. This
  document is the authoritative contract.
- **Imports** (top level): stdlib only — `logging`, `os`,
  `typing.Optional`. The `google.cloud.firestore` import is lazy
  (inside `_get_firestore`), so memory-mode deployments do not
  require the package to be installed.
- **No upstream subsystem dependencies.** Like `operator_state`,
  `users_store` is a deep leaf in the infra layer.
- **Module-level mutable state** (3 items):
  - `_MEMORY_USERS: dict[str, dict] = {}` — the in-process memory
    backend data (line 49).
  - `_firestore_client` — cached Firestore client, initialized
    lazily (line 55).
  - `logger` — module logger.

## Persistence model

### Backend selection

`CLARITYOS_BACKEND` environment variable, read **per-call** by
`_backend()` (line 41-43, "Read backend mode each time so tests
can monkey-patch the env var"):

- `memory` (default) — in-process `_MEMORY_USERS` dict, wiped on
  restart.
- `firestore` — Google Cloud Firestore, persistent, network I/O.

### Memory backend

- Single module-level dict: `_MEMORY_USERS: dict[str, dict]`.
- Key is `username`; value is the user document.
- Cleared only by `_reset_memory_for_tests()` (line 335) — the test
  reset hook. Not used in production.
- O(1) lookup; O(n) iteration in `list_all_usernames` and
  `list_users_due_for_renewal`.

### Firestore backend

- Collection name: `_USERS_COLLECTION = "users"` (line 38).
- Lazy client: `_get_firestore()` (line 58-79) imports
  `google.cloud.firestore` on first use and caches a single
  `firestore.Client()` instance in `_firestore_client`.
- **Two well-formed error paths** at init:
  - `ImportError` → wrapped with an actionable message pointing to
    `requirements.txt` or `CLARITYOS_BACKEND=memory` fallback.
  - Client init exception → wrapped with Cloud Run / `gcloud auth
    application-default login` guidance.
- Every public CRUD primitive routes Firestore reads/writes through
  `_users_collection()` (line 82-83).
- Document id is the `username` string.

### Backend parity

All 6 backend-branching functions have full semantic parity between
memory and Firestore. The one defensive edge case worth noting:
`list_all_usernames` falls back to `doc.id` when the Firestore
document's `username` field is missing (line 305) — but
`create_user` always sets that field, so this fallback is defensive
code rather than a real divergence.

### Cost-shape differences

- `user_exists` is O(1) in memory but a full document read in
  Firestore — callers running tight loops should be aware.
- `list_users_due_for_renewal` is server-side filtered in Firestore
  via `FieldFilter("renewal_ts", "<=", now_ts)`; in memory it is a
  full O(n) scan.
- All other primitives are O(1) per call in both backends.

### Lazy import contract

The lazy Firestore import means **memory-mode deployments do not
require `google-cloud-firestore` to be installed**. This is
load-bearing for dev, test, and CI environments. Importing
`users_store` does not trigger the Firestore import; only the
first call that resolves to the Firestore backend does.

## Data model

The user document is a **dict, not a dataclass**. Its shape is
extensible by any caller through `update_user`, which accepts an
arbitrary dict and merges. The known field set, enumerated by
tracing every write site in the module and its callers:

### Core fields (5) — written by `create_user`
| Field | Type | Notes |
|---|---|---|
| `username` | `str` | Document id in Firestore; key in memory backend |
| `password_hash` | `bytes` | bcrypt hash; salt is embedded in the hash |
| `salt` | `str` | Reserved for non-bcrypt schemes; empty string for bcrypt |
| `tier` | `str` | E.g. `"free"`, `"paid"`; **not enum-enforced** |
| `created_at` | `float` | POSIX seconds |

### G-credit fields (2) — written by `add_g_credits` / `consume_g_credit`
| Field | Type | Notes |
|---|---|---|
| `g_credits` | `int` | Current balance; non-negative (enforced only by `consume_g_credit`'s raise) |
| `g_credit_history` | `list[dict]` | Tail of last `USER_DOC_HISTORY_TAIL` (50) entries; **full history lives in `membership_store`** |

### Membership fields (5) — written by `set_membership`
| Field | Type | Notes |
|---|---|---|
| `membership_tier` | `str \| None` | Per module comment: `"founding_500"` or `None`; **not enum-enforced** |
| `membership_price` | `float \| None` | Locked at activation; never increases (caller-side discipline) |
| `membership_status` | `str \| None` | Per module comment: `"active"`, `"cancelled"`, or `None`; **not enum-enforced** |
| `membership_started_ts` | `float` | POSIX seconds; written only when arg non-None |
| `membership_cancelled_ts` | `float` | POSIX seconds; written only when arg non-None |

### Billing fields (4) — written by `set_billing_state`
| Field | Type | Notes |
|---|---|---|
| `billing_state` | `str` | **Must be in `VALID_BILLING_STATES`** — the one enforced field |
| `renewal_ts` | `float` | Next charge timestamp |
| `renewal_retry_count` | `int` | Failed-renewal retry counter |
| `renewal_grace_until_ts` | `float` | Grace-window expiry timestamp |

### External-caller fields (3+) — written by `update_user` from `app.py`
| Field | Type | Source | Notes |
|---|---|---|---|
| `password_hash` | `bytes` | `app.py:976` | Password reset overwrites the core field |
| `onboarding` | `dict` | `app.py:8622` | Onboarding state snapshot |
| `cancel_at_ts` | `float` | `app.py:1387, 1396` | Pending-cancellation timestamp |

### Schema-extension contract
`update_user(username, data: dict)` accepts an **arbitrary dict**
and merges it into the document. The 19 fields enumerated above are
the known set; any caller can add new fields without coordination.
**There is no `_FORBIDDEN_FIELDS` set, no `_CANONICAL_FIELDS` lock,
and no module-load assertion.** The schema is open-ended by design.

### Public constants
- `USER_DOC_HISTORY_TAIL = 50` (line 163) — re-exported by
  `app.py:8881` as the single source of truth.
- `VALID_BILLING_STATES = ("active", "past_due", "grace_period",
  "cancelled", "failed")` (line 261) — 5-element tuple of canonical
  billing-state strings.

## APIs / entrypoints

The 13 public functions split cleanly into a **two-tier
architecture**:

### Tier 1 — Primitives (6 functions, direct backend branching)

These functions explicitly branch on `_backend()`:

| Function | Line | Purpose |
|---|---|---|
| `get_user(username) -> Optional[dict]` | 89 | Read user document |
| `create_user(username, password_hash, salt, tier, created_at)` | 97 | Insert user document (silently overwrites existing) |
| `user_exists(username) -> bool` | 125 | Existence check |
| `update_user(username, data: dict)` | 131 | Merge `data` into existing document; warns + no-ops on missing user |
| `list_all_usernames() -> list[str]` | 296 | All usernames |
| `list_users_due_for_renewal(now_ts) -> list[str]` | 312 | Renewal scheduler query |

### Tier 2 — Composites (7 functions, build on primitives)

These functions contain **no `_backend()` checks** — they inherit
backend dispatch automatically through the primitives:

| Function | Line | Built on | Behavior |
|---|---|---|---|
| `get_g_credit_balance(user) -> int` | 166 | `get_user` | Returns 0 for unknown users; defensive int coercion with try/except |
| `add_g_credits(user, amount, *, history_entry=None) -> int` | 175 | `get_user` + `update_user` | Increment + history append + tail cap; negative amounts allowed for refunds |
| `consume_g_credit(user, *, history_entry=None) -> int` | 193 | `get_user` + `update_user` | Decrement by 1; **raises `ValueError("no_credits")` on zero balance** |
| `set_membership(user, *, tier, price, status, started_ts, cancelled_ts)` | 209 | `update_user` | Atomic write of membership fields; None-skip for the two timestamps |
| `get_membership_view(user) -> dict` | 232 | `get_user` | Always returns a dict (never None) — 10 fields combining membership + credits + billing |
| `set_billing_state(user, *, billing_state, renewal_ts, renewal_retry_count, renewal_grace_until_ts)` | 264 | `update_user` | **Validates `billing_state ∈ VALID_BILLING_STATES`** (raises `ValueError`); None-skip pattern; empty-payload no-op |
| `get_billing_state(user) -> Optional[str]` | 291 | `get_user` | Simple read |

### Private surface (4 functions + 2 constants)

- `_backend()` (41) — env-var read, per-call
- `_get_firestore()` (58) — lazy client init
- `_users_collection()` (82) — collection getter
- `_reset_memory_for_tests()` (335) — test hook
- `_USERS_COLLECTION = "users"` (38)
- `_MEMORY_USERS: dict[str, dict] = {}` (49)

## Integration points

### Production importers (6 + 1 script)
| Importer | Line | Role |
|---|---|---|
| `app.py` | 66 | 40+ call sites — auth, billing, membership, /me endpoints, G-credits, onboarding |
| `intelligence_kernel.py` | 60 | Kernel-path user lookups during run_* tasks |
| `founder_analytics.py` | 28 | `list_all_usernames()` + `get_user()` |
| `billing_renewal.py` | 39 | Renewal scheduler — `list_users_due_for_renewal`, `set_billing_state` |
| `billing_intents.py` | 58 | PaymentIntent flow — `set_billing_state` + `update_user` |
| `entitlement_view.py` | 36 | Entitlement projection — `get_user` + `get_membership_view` |
| `scripts/seed_acceptance_operators.py` | 30 | Acceptance test seeding (not production) |

### HTTP coupling
**No HTTP routes inside `users_store`.** The module is consumed by
`app.py`'s routes — auth/registration, password reset, `/me/*`,
billing webhook (`/billing/webhook`), founder console, onboarding,
and the G-credit purchase/consume endpoints.

Selected `app.py` call patterns (verified in PASS-1):
- Auth: `create_user(331)`, `user_exists(125+ sites)`, `get_user`
- Password reset: `update_user(..., {"password_hash": ...})` (976)
- Onboarding: `update_user(..., {"onboarding": ...})` (8622)
- Membership: `set_membership` (9020), `get_membership_view` (1458)
- Billing: `set_billing_state` (1325, 1348, 1379, 1393, 1409, 9029)
- G-credits: `get_g_credit_balance` (8041), `consume_g_credit` (8078)
- Re-export: `USER_DOC_HISTORY_TAIL` (app.py:8881)

### Tests
60 test files reference `users_store`. The primary cluster
(auth/billing/membership/credits contract surface):

- `tests/test_v28_endpoints.py`, `tests/test_v28_security.py` — v28
  endpoint + auth/security
- `tests/test_v30_membership.py` — v30 Founding cohort membership
- `tests/test_v31_billing.py` — v31 billing finalization
- `tests/test_v42_billing_hardening.py` — v42 billing hardening
- `tests/test_membership_confirm.py` — membership confirm flow
- `tests/test_entitlement_view.py` — entitlement projection
- `tests/test_el_ins_org_timeline.py` — direct importer

The remaining ~53 files use `users_store` only as a fixture
dependency (e.g., calling `create_user` to set up a session
context). They do not test users_store behavior.

## Invariants

### Backend invariants

- **`_backend()` is read per-call**, not cached, so tests can
  monkey-patch the env var between calls.
- **Primitives dispatch; composites compose.** The 6 primitives are
  the only sites with explicit `if _backend() == "firestore"`
  branches. The 7 composites have zero backend awareness.
- **Memory + Firestore semantic parity** across all 6 branching
  primitives. Documents written through the memory backend and the
  Firestore backend are read back identically (with the one
  defensive `doc.id` fallback in `list_all_usernames`).
- **Lazy Firestore import** — memory-mode deployments do not require
  `google-cloud-firestore` installed.

### Document invariants

- **Document shape is open-ended.** No `_FORBIDDEN_FIELDS`, no
  `_CANONICAL_FIELDS`, no field-set assertions at module load.
  Any caller can extend via `update_user`.
- **`create_user` silently overwrites** existing documents. Caller
  must run `user_exists()` first.
- **`update_user` is a no-op (with warning log) on missing user.**
  Both backends check existence first.
- **`g_credits` is non-negative — but only enforced in
  `consume_g_credit`.** `add_g_credits` allows negative `amount`
  (for refunds); a malformed call could leave the field negative.
- **`g_credit_history` is a tail-of-50, applied per-call** in
  `add_g_credits` and `consume_g_credit`. Reactive truncation; not
  a structural cap. Full history lives in `membership_store`.

### Billing invariants

- **`set_billing_state` is the one validating function in the
  module.** It rejects any `billing_state ∉ VALID_BILLING_STATES`.
- **`update_user` is an enforcement bypass.** A caller routing
  around `set_billing_state` could write any string to the
  `billing_state` field. Caller-side discipline.
- **`list_users_due_for_renewal` uses a hardcoded subset** of
  billing states (`"active"`, `"past_due"`, `"grace_period"`) at
  lines 321 and 327 — NOT derived from `VALID_BILLING_STATES`.
  Adding a new in-renewal state requires updating both
  `VALID_BILLING_STATES` and the hardcoded tuples in
  `list_users_due_for_renewal`.

### Membership invariants

- **`get_membership_view` always returns a dict, never None.**
  Explicit contract for cockpit rendering: 10 fields combining
  membership + credits + billing.
- **`membership_tier` and `membership_status` are caller-side
  canonical strings**, not enum-enforced. Per module comment:
  - `membership_tier` ∈ `{"founding_500", None}`
  - `membership_status` ∈ `{"active", "cancelled", None}`
- **`membership_price` is locked at activation** by caller-side
  discipline. The module does not enforce monotonicity.

### State invariants

- **Three module-level mutable state items:** `_MEMORY_USERS`,
  `_firestore_client`, and the implicit per-document state.
- **`_reset_memory_for_tests` clears only `_MEMORY_USERS`.** The
  cached `_firestore_client` persists (correct — tests should not
  hit Firestore). Real Firestore data is never touched by this
  reset (correct — would be destructive).
- **Logging surface is minimal:** `logger.info` on user creation
  and Firestore client init; `logger.warning` on `update_user`
  no-ops. No `logger.error`, no `logger.exception`.

### Caller-side contracts (documented but not enforced)

These are obligations on the caller. The module does not enforce
them; misuse fails silently or produces malformed documents.

1. **Call `user_exists()` before `create_user()`** to avoid
   silently overwriting an existing user document — which would
   reset `g_credits`, `membership_*`, `billing_*`, and all other
   fields to creation defaults.
2. **Use canonical strings for `membership_tier` and
   `membership_status`** (per module comment values). The module
   does not validate.
3. **Do not write `billing_state` via `update_user`.** Route
   through `set_billing_state` to get `VALID_BILLING_STATES`
   validation.
4. **Keep `g_credits` non-negative.** `consume_g_credit` enforces
   this at decrement time, but `add_g_credits` does not — a
   negative `amount` larger than current balance would leave
   `g_credits` negative.

## Non-goals

`users_store` is **not**:

- a session store — sessions live elsewhere; this module manages
  durable user documents only;
- an auth surface — it stores `password_hash` and `salt` but does
  no hashing, no comparison, no JWT issuance; auth logic lives in
  `app.py` callers;
- a permissions or roles system — `tier` is a free-form string,
  not an enum, not a permissions ladder;
- a billing engine — it stores billing state but does not drive
  charges, renewals, or webhooks; that lives in `billing_intents`,
  `billing_renewal`, `billing_config`;
- a membership engine — `set_membership` writes fields; it does
  not validate transitions, enforce monotonic pricing, or coordinate
  with credits;
- a credit ledger — the `g_credit_history` field is a tail-of-50
  for UI rendering only; the full transaction log lives in
  `membership_store`;
- a schema enforcement layer — the document shape is open-ended;
  callers can extend via `update_user` without coordination;
- a transactional store — operations are individual reads and
  writes; there is no batch, no transaction, no atomic
  multi-document update;
- a cache — every read goes to the backend (memory dict or
  Firestore) every time; no in-process caching layer.

## Fiction removed

The following constructs are explicitly not present in
`users_store.py` and must not be inferred:

- **No dataclasses, no enums, no TypedDict.** The user document
  is a plain `dict`. The "schema" in the module docstring is a
  comment, not a type.
- **No module-load assertion functions.** Unlike ERA / FEA /
  ambient_trust / orchestrator_schemas, `users_store` has no
  `assert_*_canonical`, no field-set guards, no enum locks. The
  only validation is `VALID_BILLING_STATES` membership in
  `set_billing_state`.
- **No `_FORBIDDEN_FIELDS` privacy set.** The schema is
  open-ended; any caller can add any field via `update_user`.
- **No duplicate-check in `create_user`.** It overwrites existing
  documents silently. The docstring at lines 105-107 makes this
  explicit; caller-side `user_exists()` is the only protection.
- **No automatic retry on Firestore failures.** A network or auth
  exception propagates to the caller.
- **No transaction support.** There is no `with users_store.batch()`
  or `users_store.transaction(...)`; each public call is its own
  operation.
- **No caching layer.** Each `get_user` hits the backend every time.
- **No automatic backend fallback.** If `CLARITYOS_BACKEND=firestore`
  and the Firestore client fails to initialize, `_get_firestore`
  raises — it does not fall back to memory.
- **No history beyond the tail of 50.** `g_credit_history` on the
  user doc is a window; the full history lives in
  `membership_store`. Other history fields (if any are added) get
  no automatic cap.
- **No HTTP routes inside this module.** Routes live in `app.py`
  and consume `users_store` as a library.
- **No kernel coupling beyond user lookup.** `intelligence_kernel`
  imports `users_store` but the relationship is one-way: the
  kernel reads user documents; users_store knows nothing about the
  kernel.
- **No password verification.** `users_store` stores
  `password_hash` and `salt` but does not compare, hash, or verify
  passwords. That logic lives in `app.py`.

Only the behaviour, fields, and integrations described in this
document are present in the code. The verified surface is exercised
by the primary test cluster in §Integration points → Tests and by
the 40+ call sites in `app.py`.
