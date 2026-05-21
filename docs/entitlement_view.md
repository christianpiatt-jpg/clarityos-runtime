# Entitlement View

## Purpose

`entitlement_view` is a **read-only projection** over the existing
membership and billing state. Given a username, it computes a
normalised entitlement dict that callers (WordPress, the operator
portal, cockpit gating logic) consume to decide what the user can
access.

It introduces no billing core, no state machine, and no second
source of truth. The authoritative state lives upstream in:

- **`users_store`** — `membership_tier` / `membership_status` /
  `billing_state` / `renewal_ts` / `membership_confirmed`
- **`membership_store`** — Founding 500 cohort roster
- **`billing_config`** — Stripe mode

`compute_entitlement_view(user)` reads these, derives the
entitlement view, and returns it. This is the "adapter" half of the
V83 entitlement work: project from existing state, never fork it.

The module is **pure-ish and defensive**: every public + private
path is wrapped so a single upstream hiccup degrades to a
well-shaped dict with safe defaults rather than raising. The output
is deterministic given fixed upstream state, with one exception:
the `computed_at` field reflects wall-clock time.

## Implementation location

- **File:** `entitlement_view.py` (209 lines, single file).
- **Version anchor:** `SOURCE_TAG = "clarityos.entitlement_view.v83.1"`
  (line 40) — introduced v83.
- **No package directory**, no `__init__.py`, no `__all__`.
- **No external spec** — this document is the authoritative contract.
- **Imports** (top level): stdlib (`logging`, `time`,
  `typing.Any`) + 3 upstream subsystems (`users_store`,
  `membership_store`, `billing_config`).
- **No module-level mutable state.** No assertion functions. No
  TypedDict, no dataclass, no enum.
- **One module logger:** `clarityos.entitlement_view`.

## Data model

### Output shape — 15 top-level fields

Both `_empty_view` (unknown user) and `compute_entitlement_view`
(populated) return dicts with the **exact same** 15-field
structure, so callers never need presence checks:

```python
{
    "exists":                  bool,                # True for known users
    "user":                    str,                 # echo of input
    "tier":                    Optional[str],       # membership_tier or None
    "active":                  bool,                # derived (see §Invariants)
    "billing_state":           Optional[str],       # passthrough from users_store
    "cancel_at_period_end":    bool,                # always False — no v30/v31 source
    "current_period_end":      Optional[float],     # renewal_ts passthrough
    "lifetime":                bool,                # always False — no v30/v31 source
    "founding_500_badge":      bool,                # Founding 500 roster membership
    "membership_confirmed":    bool,                # v74 user-document field
    "membership_confirmed_ts": Optional[float],     # v74 user-document field
    "features": {
        "portal_access":      bool,                 # = active
        "founding_500_badge": bool,                 # = founding
        "priority_support":   bool,                 # = active AND founding
        "downloads":          bool,                 # = active
        "community_access":   bool,                 # = active
        "billing_portal":     bool,                 # = (tier is not None)  — see §6.2
    },
    "billing_mode":            str,                 # from billing_config; "unknown" on failure
    "source":                  str,                 # SOURCE_TAG, always present
    "computed_at":             float,               # time.time() — only non-deterministic field
}
```

### Empty-view shape (unknown user)

When the user is unknown, invalid, or upstream reads fail,
`_empty_view(user)` returns the same 15-field structure with:

- `exists`: `False`
- `tier`: `None`
- `active`: `False`
- `billing_state`: `None`
- `cancel_at_period_end`: `False`
- `current_period_end`: `None`
- `lifetime`: `False`
- `founding_500_badge`: `False`
- `membership_confirmed`: `False`
- `membership_confirmed_ts`: `None`
- All 6 `features` fields: `False`
- `billing_mode`: `_billing_mode()` is still invoked — populated
- `source`: `SOURCE_TAG` — always present
- `computed_at`: `time.time()` — always present

### Source tag contract

- `SOURCE_TAG = "clarityos.entitlement_view.v83.1"` (line 40)
- Included in **every** output dict (both empty and populated) as
  the `"source"` field.
- Clients can use it as a schema-version marker for gating.
- The `.1` suffix is the minor-version slot. **Any breaking change
  to the 15-field output shape MUST bump the suffix** (e.g.,
  `v83.2`). Additive non-breaking field additions can keep the
  current tag.

### Public constants
- `SOURCE_TAG: str` (line 40)

### Private constants
- `_ACCESS_BILLING_STATES = ("active", "past_due", "grace_period")` (45)
- `_REVOKED_BILLING_STATES = ("cancelled", "failed")` (48)

These two tuples are the billing-state partition. See §Invariants
for the partition contract.

## APIs / entrypoints

### Public function (1)

**`compute_entitlement_view(user: str) -> dict`** (line 113)

Computes the entitlement projection for the given username.

- Returns a fully-shaped 15-field dict — **never `None`, never
  raises.**
- Unknown / invalid users get `exists: False` with every feature
  flag `False`.
- All upstream exception paths are caught and logged at WARNING
  level; the function degrades to `_empty_view` or partial
  population rather than propagating.

### Private helpers (3)

- `_is_founding_member(user) -> bool` (line 54) — wraps
  `membership_store.is_member(user, membership_store.FOUNDING_COHORT)`
  with try/except → `False` on any exception.
- `_billing_mode() -> str` (line 69) — wraps
  `billing_config.get_billing_status()["mode"]` with try/except →
  `"unknown"` on any exception.
- `_empty_view(user) -> dict` (line 81) — returns the 15-field
  empty shape with safe defaults.

### HTTP routes (2)

| Method | Path | Handler | Auth | Body |
|---|---|---|---|---|
| GET | `/me/entitlement` | `me_entitlement` (app.py:12357) | `require_session` | `compute_entitlement_view(session["user"])` verbatim |
| GET | `/founder/entitlement/{user_id}` | (app.py:12365) | founder-gated | `compute_entitlement_view(user_id)` verbatim |

Both routes are **GET-only, thin pass-throughs**. No transformation,
no wrapping, no shape modification in `app.py`. The
`compute_entitlement_view` output IS the HTTP response body.

## Integration points

### Upstream — 3 subsystems

#### `users_store` (CURRENT, canonicalized Batch-22)

| Call | Line | Purpose |
|---|---|---|
| `users_store.get_user(user)` | 144 | Existence check + direct field reads (`membership_confirmed`, `membership_confirmed_ts`) |
| `users_store.get_membership_view(user)` | 153 | 10-field projection; 4 fields consumed (`tier`, `status`, `billing_state`, `renewal_ts`) |

**Six user-document fields consumed:**

- Via `get_user(user)` (direct):
  - `membership_confirmed` (bool, default `False`)
  - `membership_confirmed_ts` (float or None)
- Via `get_membership_view(user).get(...)`:
  - `tier` ← originally `users_store.membership_tier`
  - `status` ← originally `users_store.membership_status`
  - `billing_state` ← originally `users_store.billing_state`
  - `renewal_ts` ← originally `users_store.renewal_ts`

**Cross-doc note:** `membership_confirmed` and
`membership_confirmed_ts` are v74 additions to the user document
that are written by external callers but **not yet enumerated** in
`docs/users_store.md`'s field set. Adding them to the users_store
doc's "External-caller fields" subsection is a small follow-up to
maintain cross-doc consistency.

#### `membership_store` (not yet canonicalized)

| Symbol | Use |
|---|---|
| `membership_store.is_member(user, cohort)` | Roster membership check |
| `membership_store.FOUNDING_COHORT` | Constant identifying the Founding 500 cohort |

Both consumed only by `_is_founding_member`. Failure mode:
exception → `False` + WARNING log.

#### `billing_config` (not yet canonicalized)

| Symbol | Use |
|---|---|
| `billing_config.get_billing_status()` | Returns dict; `["mode"]` is extracted |

Note: this is **distinct from `billing_config.get_stripe_mode()`**
used by `founder_analytics` (Batch-15). Two different surfaces of
`billing_config`. Failure mode: exception → `"unknown"` + WARNING
log.

### Production importers (1)

- `app.py:112` — `import entitlement_view  # v83 — entitlement
  projection over v30/v31/v42 stores`

That is the only production importer. The module is consumed
exclusively through the 2 HTTP routes.

### Tests
- `tests/test_entitlement_view.py` — only test file. Same tight
  scope as `founder_analytics` (Batch-15).

### No coupling to
- `intelligence_kernel` (no import either way)
- `model_router` / LLM SDKs
- `memory_vault`
- `operator_state`
- File I/O, network I/O (beyond what `users_store` does internally)
- HTTP routes inside the module itself — exposure is via `app.py`'s
  2 routes only

## Invariants

### Billing-state partition contract

The two private tuples partition the 5 canonical billing states
from `users_store.VALID_BILLING_STATES` into "access granted" vs
"access revoked":

| Set | Members | Effect on `active` |
|---|---|---|
| `_ACCESS_BILLING_STATES` | `active`, `past_due`, `grace_period` | `active = True` (unless `membership_status == "cancelled"`) |
| `_REVOKED_BILLING_STATES` | `cancelled`, `failed` | `active = False` |

**Mutual exclusivity:** the two tuples have empty intersection.

**Collective exhaustiveness:** the union equals
`users_store.VALID_BILLING_STATES` today.

**Coordination requirement:** any addition to
`users_store.VALID_BILLING_STATES` MUST be paired with an explicit
addition to either `_ACCESS_BILLING_STATES` or
`_REVOKED_BILLING_STATES`. Failure to do so causes the new state to
fall through to the `else` branch in `compute_entitlement_view`
(lines 174-175), which **fails closed**: `active = False`.

This is intentional — failing closed on unknown states is safer
than silently granting access. But it means the partitioning is a
**third source of truth** for billing-state semantics, alongside
`users_store.VALID_BILLING_STATES` and the hardcoded 3-element
subset in `users_store.list_users_due_for_renewal`. See
`docs/users_store.md`'s billing invariants.

### Access derivation (`active` field)

Priority-ordered decision chain (lines 166-175), first match wins:

| # | Condition | `active` |
|---|---|---|
| 1 | `membership_status == "cancelled"` | `False` |
| 2 | `billing_state ∈ _REVOKED_BILLING_STATES` | `False` |
| 3 | `billing_state ∈ _ACCESS_BILLING_STATES` | `True` |
| 4 | `billing_state is None` | `membership_status == "active"` |
| 5 | (any other value — fail-closed) | `False` |

Branch 1 overrides everything: a cancelled membership is inactive
regardless of billing state. Branch 4 handles the "no billing state
yet" case (e.g., free-tier users) by tracking `membership_status`.
Branch 5 is the unknown-state safety net.

### Empty-view contract

`_empty_view(user)` is returned via 4 convergent paths:

1. `user` is not a `str` → `_empty_view("")` (empty-string echo)
2. `user.strip()` is empty → `_empty_view(user)` (whitespace
   echoed back as-is)
3. `users_store.get_user(user)` raises → warning log, falls
   through to `_empty_view(user)`
4. `users_store.get_user(user)` returns `None`/falsy →
   `_empty_view(user)`

The empty view is **fully-shaped** (15 top-level fields, 6-field
`features` sub-dict, plus `billing_mode`, `source`, `computed_at`),
so callers always receive a renderable result.

### Never-raises contract

`compute_entitlement_view` and all three private helpers wrap
their upstream calls in `try/except Exception`. The module
guarantees:

- **Never returns `None`.**
- **Never raises.**
- Every exception path logs at WARNING level and degrades to a safe
  default (`False`, `"unknown"`, empty view, or omitted field).

### Determinism

For fixed upstream state, `compute_entitlement_view(user)` produces
**byte-equal output except for the `computed_at` field**, which
always reflects current wall-clock time (`time.time()`).

This pattern matches `founder_analytics`'s `ts` field and is the
expected shape for a "snapshot view at this moment."

### Feature derivation rules

Five of the six `features` fields gate on `active`:

- `portal_access` ← `active`
- `downloads` ← `active`
- `community_access` ← `active`
- `priority_support` ← `active AND founding`
- `founding_500_badge` ← `founding`

The sixth diverges deliberately:

- **`billing_portal` ← `tier is not None`** (NOT `active`)

A cancelled user with a non-None `tier` retains `billing_portal =
True`. This is intentional — a cancelled user needs portal access
to view their billing history, manage payment methods, or
reactivate. PASS-4 pins this as a load-bearing divergence, not a
bug.

### Source tag contract

`SOURCE_TAG` is the schema-version marker. Clients depend on its
presence in every output. **Breaking changes to the 15-field
output shape MUST bump the suffix** (`v83.1` → `v83.2`). Additive
non-breaking field additions can keep the current tag.

### Honesty for unsourced fields

Two fields have no source in the current v30/v31 model and are
**always `False`**, with comments (lines 187-189 + docstring lines
132-137) explicitly stating they are "surfaced honestly as False —
not guessed":

- `cancel_at_period_end` — will gain a real source when the v42
  Stripe subscription webhook starts recording scheduled
  cancellations.
- `lifetime` — no current notion of lifetime membership in the
  v30/v31 model.

Until those sources land, the values are deterministic `False`,
not fabricated. Future PRs adding real data should preserve this
honesty discipline.

### Foot-gun for whitespace usernames

If `user` is a whitespace-only string (e.g., `"   "`), the
**original (unstripped) value** is echoed back in the `user` field
of `_empty_view`. The `exists: False` flag still applies. Callers
relying on the `user` field to be a normalised identifier should
strip it themselves.

## Non-goals

`entitlement_view` is **not**:

- a billing engine — no Stripe coupling, no charge logic, no
  webhook handling; that lives in `billing_intents` /
  `billing_renewal` / `billing_config`;
- a membership engine — `set_membership` lives in `users_store`,
  not here; this module only reads;
- a state machine — there are no transitions, no scheduling, no
  retry logic; one read pass per call;
- a credit ledger — `g_credits` are not part of the entitlement
  view (the cockpit reads them via separate `/me/membership` or
  `/me/credits` paths);
- a permissions engine — features are a fixed 6-field dict gated
  on `active` (and `tier`); there is no role system, no scope
  language, no policy DSL;
- a cache — every call re-reads from upstream stores; no
  in-process caching;
- a mutation surface — both HTTP routes are GET-only;
- an HTTP handler — routes live in `app.py`; this module is a
  library;
- a kernel reasoning mode — no `intelligence_kernel` coupling;
- a privacy or identity guard — relies on `users_store` and
  upstream auth for identity; emits no privacy-sensitive fields
  beyond what `users_store` already exposes.

## Fiction removed

The following constructs are explicitly not present in
`entitlement_view.py` and must not be inferred:

- **No fork of billing or membership state.** All state lives
  upstream. The module reads and projects; it never writes.
- **No state machine transitions.** No transitions, no scheduling,
  no retry. Single call = single read pass.
- **No raise paths.** Every public + private path is defensive;
  upstream exceptions degrade to safe defaults with WARNING logs.
- **No partial-shape returns.** The 15-field output shape is
  identical between empty and populated views; callers never need
  presence checks.
- **No automatic billing-state inference.** Unknown billing states
  fail closed (`active = False`) — they are NEVER silently
  promoted to access.
- **No fabricated data for `cancel_at_period_end` / `lifetime`.**
  These have no v30/v31 source and are deterministically `False`,
  not guessed.
- **No caching, no precomputation, no background refresh.** Every
  call re-reads from upstream stores fresh.
- **No `billing_portal` gating on `active`.** The `billing_portal`
  feature derives from `tier is not None`, not `active` — a
  cancelled user with a tier still has billing_portal access. This
  is intentional.
- **No bulk or multi-user view.** `compute_entitlement_view` takes
  exactly one `user` and returns one dict; there is no batch
  surface, no list view, no scan.
- **No write surface anywhere.** Both HTTP routes are GET-only.
- **No `SOURCE_TAG` bump on additive change.** The minor-version
  suffix bumps only on breaking changes to the 15-field shape.
- **No double-call to `_billing_mode()` in a single
  `compute_entitlement_view` invocation.** The function is invoked
  exactly once per public call (line 206) or once in `_empty_view`
  (line 104), never both.
- **No deterministic `computed_at`.** This single field always
  reflects current wall-clock time. The rest of the output is
  deterministic given fixed upstream state.

Only the behaviour, fields, and integrations described in this
document are present in the code. The verified surface is exercised
by `tests/test_entitlement_view.py` and the 2 HTTP routes in
`app.py`.
