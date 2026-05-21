# V67 — Units 70 + 71 (Auth UX coherence + Provider robustness)

Status: ✅ Ready
Backend version: `4.10` (bumped from 4.9)
Build: `20260513020000`

---

## What this pass ships

Two independent units land in this pass.

### Unit 70 — Phone + auth UX coherence

Backend already auth-gates `/operator/session/*` since Units 68/69. The
remaining client-side gaps are closed here:

* **Phone — six `operator_*.tsx` screens cleaned**
  * `operator_session.tsx` — `operator_id` KV row removed; bootstrap
    no longer falls back to `"op_anon"`; "Authed as ..." badge added
    under the subtitle.
  * `operator_session_history.tsx` — operator TextInput stripped (it
    was inert since v64/Unit 66 — server ignores client-supplied id);
    operator_id KV row in the detail view removed; "Authed as ..."
    badge added.
  * `operator_vault.tsx` — operator TextInput stripped (same reason);
    "Authed as ..." badge added.
  * `operator_profile.tsx`, `operator_timeline.tsx`,
    `operator_model_preferences.tsx` — wrapped in `AuthGate` so
    unauthed visits surface the same CTA instead of the previous
    "(not signed in)" placeholder + likely 401 banner.

* **New `phone/components/AuthGate.tsx`** — single component used by
  all six screens. Reads `getUser()` from `lib/api`; renders an
  inline "Sign in required" card with a `SIGN IN` button that pushes
  `/login` when unauthed; otherwise renders children unchanged.

* **Web — `RequireAuth.tsx` rewritten**
  * Pre-Unit-70: silent `<Navigate to="/login">` redirect.
  * Post-Unit-70: inline CTA panel ("Sign in required" + body +
    `SIGN IN` Link with the same `from` state attached so the
    Login route still redirects back).
  * Applies uniformly to every authenticated route in `App.tsx`
    (~20 routes). No per-route opt-in needed.

* **Desktop** — no changes. The desktop `App.tsx` already handles
  unauthed state by rendering the full `SignIn` form at the app
  level. The pre-existing UX matches the plan's intent (user sees
  the sign-in surface; doesn't get silently dropped).

* **Tests** — `web/src/components/__tests__/RequireAuth.test.tsx`
  (5 tests):
  * Unauth → inline CTA rendered, outlet not rendered.
  * Unauth → CTA Link targets `/login` with "SIGN IN" text.
  * Unauth → no auto-redirect (the pre-Unit-70 behaviour is gone).
  * Authed → protected outlet rendered, CTA not rendered.
  * CTA copy mentions "sign in to start or resume sessions".

### Unit 71 — Provider robustness + model registry

* **New leaf module `runtime_http_config.py`** — two timeout maps +
  one retry map, plus getters. Behaviour identical to pre-Unit-71
  (call=30s, health=3s, retries=0 across all five providers) but
  now addressable. Both `model_router` and `runtime_http` import
  from it; it imports neither back (verified by test).

* **`model_router.py`** —
  * `_PROVIDER_HTTP_TIMEOUT` now initialised from
    `runtime_http_config.DEFAULT_CALL_TIMEOUT`.
  * New `_request_timeout(seconds)` context manager temporarily
    mutates the global and restores it (LIFO-safe; exception-safe).
    Cleaner than the pre-Unit-71 ad-hoc try/finally monkey-patch in
    the health check.
  * Each of `_call_openai`, `_call_anthropic`, `_call_gemini` now
    wraps its `_http_post_json` call with
    `_request_timeout(runtime_http_config.get_call_timeout(provider))`
    so the per-provider value is read at call time.
  * `_http_post_json` signature **unchanged** — preserves every
    test mock in the suite.

* **`runtime_http.py`** —
  * `_PROVIDER_HEALTH_TIMEOUT = 3.0` constant removed.
  * `_check_provider_health` now wraps the per-provider probe with
    `_mr._request_timeout(runtime_http_config.get_health_timeout(provider))`,
    so the value is config-driven and explicit.

* **New `MODEL_REGISTRY` dict in `model_router.py`** — provider →
  tuple of model_id strings. `SUPPORTED_MODELS` becomes a derived
  flat tuple (registry contents + `"auto"` sentinel). Every existing
  consumer (`is_valid_model`, `set_operator_model_preference_in_vault`,
  the `runtime_providers.model_id_for` validation chain) continues to
  work — registry change is structural, not semantic.

* **New endpoint `GET /runtime/providers/models`** —
  * Auth-gated (same pattern as `/runtime/providers/health`).
  * Returns `{"registry": {<provider>: [<model_id>, ...], ...},
                "supported": [<model_id>, ..., "auto"]}`.

* **Web — `getProviderModels()` helper** in `web/src/lib/api.ts`.
  Mirrors `getProviderHealth()` exactly. Types
  (`ProviderModelsResponse`) exported for future UI consumption.

* **Tests**:
  * `tests/test_runtime_http_config.py` (28 tests) — config shape,
    getter coverage, `model_router` global wiring, `_request_timeout`
    correctness (nested + exception-safe), health-check timeout
    threading, leaf-module invariant.
  * `tests/test_provider_models_endpoint.py` (14 tests) — endpoint
    auth, response shape, registry coherence, validation entry
    points still honour `SUPPORTED_MODELS`.

---

## Test summary

| Suite              | Tests added | Net |
|--------------------|-------------|-----|
| Backend new        | 42          | new |
| Web new            | 5           | new |

Pre-Unit-71 backend total + 42 = current count. Pre-Unit-71 web 72 + 5
= 77. All passing.

---

## What did NOT change

* Backend auth contract on `/operator/session/*` — already locked at
  Unit 68. No new authz/IDOR work in this pass.
* `_http_post_json` signature — preserved so every test mock in the
  suite (esp. the 12 tests in `test_provider_health.py`) still works
  without modification.
* `SUPPORTED_MODELS` as the validation gate — only its source
  changed (now derived from `MODEL_REGISTRY` instead of literal).
  All `model_id in SUPPORTED_MODELS` checks still hit the same set.
* Existing endpoint contracts under `/operator/*`, `/me/*`,
  `/runtime/providers/*` — fully back-compatible.

---

## Files touched

```
phone/components/AuthGate.tsx                              (new)
phone/app/operator_session.tsx
phone/app/operator_session_history.tsx
phone/app/operator_vault.tsx
phone/app/operator_profile.tsx
phone/app/operator_timeline.tsx
phone/app/operator_model_preferences.tsx

web/src/components/RequireAuth.tsx
web/src/components/__tests__/RequireAuth.test.tsx          (new)
web/src/lib/api.ts

runtime_http_config.py                                     (new)
model_router.py
runtime_http.py

tests/test_runtime_http_config.py                          (new)
tests/test_provider_models_endpoint.py                     (new)

V67_READINESS.md                                           (new)
BUILD_VERSION
```
