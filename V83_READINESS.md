# V83 — Entitlement projection

Status: ✅ Ready
Backend version: `4.22` → `4.23`
Build: `20260514190000` → `20260515120000`

---

## What this pass ships

### Founder-locked design call

The "Entitlement Engine" instruction proposed building a fresh
billing core (`sos_runtime/billing/membership_store.py` +
`users_store.py` + `state_machine.py`) plus an entitlement layer.
That was flagged and reconciled before any code:

* It would have **duplicated** `membership_store.py` + `users_store.py`
  + the billing state machine — modules that already exist and are
  tested across v30/v31/v42.
* It was **internally contradictory** — a fresh billing core (option
  a, "replace") *and* a "projection" (option b, "adapter").
* It put billing into **SOS_V1**, a service deliberately scoped to
  exclude it (`/engage /elins /continuity /state` only).

Founder picked **Option B — adapter/projection**. V83 builds exactly
that: a read-only projection over the existing stores, in the
ClarityOS main service. No new billing core. No new state machine.
No second source of truth.

### Backend

#### `entitlement_view.py` (new — repo root)

`compute_entitlement_view(user) -> dict` — a pure-ish, defensive
projection. Reads:

* `users_store` — `get_user`, `get_membership_view` (membership_tier,
  membership_status, billing_state, renewal_ts), plus the v74
  `membership_confirmed` / `membership_confirmed_ts` fields.
* `membership_store` — `is_member(user, FOUNDING_COHORT)` for the
  Founding 500 badge (authoritative cohort roster).
* `billing_config` — `get_billing_status()` for the Stripe mode label.

Returns a fully-shaped dict — **never None, never raises.** Unknown /
invalid users get `exists: False` with every feature flag `False`,
so callers render unconditionally.

##### Returned shape

```
{
  exists:                  bool,
  user:                    str,
  tier:                    str | None,          # membership_tier
  active:                  bool,                # derived (see below)
  billing_state:           str | None,          # v31 state machine
  cancel_at_period_end:    bool,                # honest False — no source yet
  current_period_end:      float | None,        # renewal_ts
  lifetime:                bool,                # honest False — no source yet
  founding_500_badge:      bool,                # cohort roster
  membership_confirmed:    bool,                # v74
  membership_confirmed_ts: float | None,        # v74
  features: {
    portal_access:      bool,   # = active
    founding_500_badge: bool,   # = founding (permanent)
    priority_support:   bool,   # = active AND founding
    downloads:          bool,   # = active
    community_access:   bool,   # = active
    billing_portal:     bool,   # = tier is not None
  },
  billing_mode:  str,                            # billing_config mode
  source:        "clarityos.entitlement_view.v83.1",
  computed_at:   float,
}
```

##### `active` derivation

The user is entitled when:

* `membership_status` is not `"cancelled"`, AND
* `billing_state` is `None` → access tracks `membership_status`,
* `billing_state` ∈ (`active`, `past_due`, `grace_period`) → access
  **retained** (past_due + grace are the v31 retry/grace window —
  access on purpose),
* `billing_state` ∈ (`cancelled`, `failed`) → access revoked.

Mirrors the normalisation `/me/billing` (v42) already uses.

##### Honest gaps

`cancel_at_period_end` and `lifetime` have **no field** in the
v30/v31 model — surfaced as deterministic `False`, not guessed. When
the v42 Stripe subscription webhook records a scheduled cancellation,
`cancel_at_period_end` gets a real source; until then it is honestly
`False`. Documented inline in `entitlement_view.py`.

#### Endpoints (`app.py`)

| Method | Path                               | Auth              | Behaviour |
|--------|------------------------------------|-------------------|-----------|
| GET    | `/me/entitlement`                  | `require_session` | Entitlement projection for the caller. |
| GET    | `/founder/entitlement/{user_id}`   | `_require_founder`| Projection for any user. 400 on malformed `user_id`; **200 with `exists: False`** for an unknown user (the projection never 404s). |

Both return the `compute_entitlement_view` dict directly — no
Pydantic model, same convention as the `/me/billing` precedent.
Endpoints are trivially thin: all logic is in the projection.

---

## Test summary

| Suite                               | Tests | Status |
|-------------------------------------|-------|--------|
| `tests/test_entitlement_view.py`    | 32    | ✅ new |

Adjacency sweep — **399 passed**, including the suites that own the
infrastructure the projection reads from (proves the source of truth
was not disturbed):

| Suite                               | Status |
|-------------------------------------|--------|
| `test_entitlement_view.py`          | ✅ (32, new) |
| `test_v30_membership.py`            | ✅     |
| `test_v31_billing.py`               | ✅     |
| `test_v42_billing_hardening.py`     | ✅     |
| `test_membership_confirm.py` (v74)  | ✅     |
| `test_v28_endpoints.py`             | ✅ (4.22 → 4.23) |
| `test_v51_projects.py`              | ✅ (4.22 → 4.23) |
| `test_v53_elins_v2.py`              | ✅ (4.22 → 4.23) |
| `test_v54_ingestion.py`             | ✅ (4.22 → 4.23) |
| `test_regression_first_endpoints.py`| ✅ (4.22 → 4.23) |
| `test_v80/81/82_*`                  | ✅ (4.22 → 4.23) |
| **Total**                           | **399 ✅** |

### V83 test classes

| Class                          | Coverage |
|--------------------------------|----------|
| `TestProjectionShape`          | Unknown user → `exists: False` + fully shaped; empty/non-string user handled; source tag; existing user with no membership. |
| `TestActiveDerivation`         | `active` across every billing_state — active / past_due / grace_period retain access; cancelled / failed revoke; cancelled membership overrides; no-billing-machine tracks membership_status. |
| `TestFoundingBadge`            | Badge true for cohort member, false for non-cohort; **badge survives billing lapse** (permanent cohort fact, access is not). |
| `TestFeatures`                 | Active founding member features all on; inactive features off (but `billing_portal` stays on for reactivation); `priority_support` needs active AND founding. |
| `TestMembershipConfirmed`      | v74 `membership_confirmed` + `_ts` surface; default false. |
| `TestMeEntitlementEndpoint`    | 200 for authed; 401 anonymous; reflects the caller, not an arbitrary user. |
| `TestFounderEntitlementEndpoint`| Founder reads any user; non-founder 403; 401 anonymous; unknown user → 200 `exists: False`; slash-bearing user_id rejected. |
| `TestManifestAndVersion`       | Both routes in the `GET /` manifest; `/health` 4.23. |

---

## Files touched

```
entitlement_view.py                         (new — compute_entitlement_view projection)

app.py                                       (+ import entitlement_view
                                              + GET /me/entitlement
                                              + GET /founder/entitlement/{user_id}
                                              + 2 manifest entries
                                              /health 4.22 → 4.23)

tests/test_entitlement_view.py               (new — 32 tests across 8 classes)
tests/test_v28_endpoints.py                  (version 4.22 → 4.23)
tests/test_v51_projects.py                   (version 4.22 → 4.23)
tests/test_v53_elins_v2.py                   (version 4.22 → 4.23)
tests/test_v54_ingestion.py                  (version 4.22 → 4.23)
tests/test_regression_first_endpoints.py     (version 4.22 → 4.23)
tests/test_v80_regression_first_packet.py    (version 4.22 → 4.23)
tests/test_v81_regression_first_archive.py   (version 4.22 → 4.23)
tests/test_v82_regression_first_replay.py    (version 4.22 → 4.23)

BUILD_VERSION                                 20260514190000 → 20260515120000
V83_READINESS.md                             (new)
```

**Not touched:** `membership_store.py`, `users_store.py`,
`billing_config.py`, `billing_intents.py`, `billing_renewal.py`,
`membership_billing.py`. The projection is strictly read-side. The
billing/membership source of truth is unchanged — verified by the
v30/v31/v42 suites passing untouched.

---

## Architecture invariants verified

* **Single source of truth preserved.** `entitlement_view` reads
  v30/v31/v42/v74 state; it writes nothing. No second entitlement
  model. The v30/v31/v42 suites pass unmodified.
* **No billing core duplication.** No new `membership_store`, no new
  `users_store`, no new state machine. The proposed
  `sos_runtime/billing/` was not built.
* **SOS_V1 scope intact.** Billing stays out of `sos_runtime/`. The
  entitlement projection lives in the ClarityOS main service, where
  the billing data already is.
* **Never raises.** Every store read in `compute_entitlement_view`
  is defensively wrapped; the function always returns a fully-shaped
  dict. Locked by `TestProjectionShape`.
* **Honest fields.** `cancel_at_period_end` / `lifetime` are
  surfaced `False` with inline notes rather than guessed — no
  invented state.
* **`/me/billing` consistency.** The `active` derivation mirrors the
  v42 `/me/billing` normalisation, so the two endpoints never
  disagree about whether a user is paid up.

---

## What's still open (separate concerns, none in flight)

* **SOS_V1 `/health` verification** — the deployed Cloud Run service
  (`https://sos-v1-736968277491.us-east4.run.app`) has not yet been
  confirmed to serve a request. Unrelated to V83, but still the
  cleanest next ops step: `gcloud run services proxy` + `curl
  /health` in Cloud Shell.
* **`cancel_at_period_end` real source** — when the v42 Stripe
  `customer.subscription.updated` webhook records a scheduled
  cancellation, `entitlement_view` can read it instead of emitting
  `False`. One-line change at that point.
* **WordPress consumption** — the `wp-sos-connector` plugin (SOS_V2)
  can call `/me/entitlement` (or a ClarityOS-main-service equivalent)
  to gate portal access. That wiring is a WordPress-side unit.
