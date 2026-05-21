# Runtime — app.py

## Purpose

`app.py` is the **HTTP runtime surface** of ClarityOS Cloud — a single
FastAPI application that exposes every user-facing, founder-facing,
public, and admin endpoint in the system. It is the only file in the
repository that constructs the `FastAPI` app instance, mounts auxiliary
routers, defines route handlers, and connects upstream subsystem
modules (kernel, model_router, billing, ELINS, vault) to HTTP routes.

The runtime concepts that some architectures place in separate files —
**gateway**, **session manager**, **continuity layer**, **request
pipeline**, **error envelope handler**, **rate limiter** — all live
**inside `app.py`** as subsystems, not as separate modules.

### Core invariants (from module + PASS‑3A)

1. **Every authenticated route depends on `require_session`** (FastAPI
   `Depends(require_session)` in route signatures).
2. **Session tokens never appear in full in logs** — `_session_ref`
   truncates to 8 chars.
3. **Passwords are bcrypt-hashed before persistence**; the bootstrap
   admin password is printed via `print(...)` (not `logger.*`).
4. **Single error envelope** — `error_response(error, message)` is the
   only error-envelope constructor; the global exception handler
   enforces it.
5. **CORS allowlist is strict** — no `*`; default is
   `pro-mediations.com` + `www.pro-mediations.com`.
6. **Webhook idempotency on `event_id`** — duplicate Stripe events
   short-circuit to `{ok: true, duplicate: true}`.
7. **Renewal scheduler lazy-boots at most once per process** on first
   `/membership/activate`.
8. **Rate limiting** — IP key for public endpoints; user key for
   authenticated endpoints.

## Status

| File | Status | Reason |
|---|---|---|
| `app.py` | **CURRENT** | 15,278 lines · 186 routes · 70+ Pydantic models · 390 top-level definitions · FastAPI app at `version="2.4"` |

## Implementation location

- **Source:** `app.py` (15,278 lines).
- **FastAPI app instance:** line 146 (`app = FastAPI(title="ClarityOS Cloud", version="2.4")`).
- **CORS middleware:** lines 303–309.
- **Global exception handler:** lines 463–471.
- **Session helper:** line 477 (`require_session`).
- **Cohort gates:** lines 804 (`_require_admin`), 813 (`_require_founder`).
- **Bootstrap admin:** line 355 (`_bootstrap_admin`).
- **Optional mounted routers:** lines 152–252 (8 from `acceptance_dashboard`, 6 from `runtime_http`).
- **Importers (production):** 1 — `runtime_http.py`. **Tests:** 62 files.

### Imports

- **Stdlib:** `json`, `logging`, `os`, `secrets`, `sys`, `time`, `datetime`, `typing`.
- **Third-party:** `bcrypt`, `fastapi`, `pydantic`. Lazy-optional: `google.cloud.storage`.
- **Internal store modules (16):** `users_store`, `sessions_store`, `invites_store`, `vault_store`, `library_store`, `timeline_store`, `usage_store`, `dewey_neighborhoods_store`, `dewey_memberships_store`, `markov_states_store`, `envelopes_store`, `trajectories_store`, `elins_distribution_store`, `mesh_metadata_store`, `membership_store`, `waitlist_store`, `dm_store`.
- **Internal subsystems (16):** `billing`, `billing_intents`, `billing_renewal`, `billing_config`, `membership_billing`, `v29_hardening`, `comment_generator`, `perplexity_oracle`, `elins_scheduler`, `elins_scheduler_config`, `elins_entity_graph`, `elins_dashboard`, `operator_state`, `intelligence_kernel`, `founder_analytics`, `model_router`, `local_model_runtime`, `memory_vault`, `threads_vault`, `projects_vault`, `problem_solver`, `entitlement_view`, `dewey_worker`, `dewey_pipeline`, `tokens` (as `invite_tokens`).
- **ELINS subpackage (6):** `ELINS.standard_elins`, `elins_project`, `forecast_engine`, `regional_elins`, `ingestion_bus`, `el_ins.timeline`.

**No imports of:** any `azimuth*`, `orchestrator_*`, `language_*`,
`feedback_*`, or any intelligence-layer engine. The intelligence-layer
canon is **not reached** from `app.py` directly.

## HTTP surface

### Route count and families

**186 routes** via `@app.<method>` decorators. Distinct route prefixes
(distilled from the full enumeration):

```
/admin                       /billing                 /billing/intent
/c                           /cmt                     /continuity
/dewey/*                     /elins/*                 /elins/daily
/elins/dashboard             /elins/entities/*        /elins/forecast
/elins/g                     /elins/ingest            /elins/regional
/elins/regression/*          /elins/v2                /envelope
/founder/*                   /founder/analytics       /founder/billing
/founder/dm                  /founder/elins/*         /founder/entitlement
/founder/intelligence/kernel /founder/membership      /founder/models
/founder/operator/{user_id}  /founder/vault/*         /founder/waitlist
/ingest                      /ingest/feeds            /invite/{token}
/library                     /markov                  /me/*
/membership                  /mesh                    /metadata
/public                      /runtime                 /timeline
/trajectory                  /v29                     /vault
/waitlist
```

### Mounted external routers (optional)

| Source | Routers mounted | Source line |
|---|---|---|
| `acceptance_dashboard` | `acceptance_router`, `analytics_router`, `telemetry_router`, `identity_router`, `console_router`, `surfaces_router`, `operator_router`, `launch_router` | 152–199 |
| `runtime_http` | `runtime_router`, `operator_router`, `providers_router`, `el_ins_router`, `timeline_router`, `org_timeline_router` | 207–252 |

Every mount is wrapped in `try/except ImportError` — a missing
optional module never blocks boot.

### Pydantic request models

**70+** classes inheriting from `BaseModel` (versioned `V28` …
`V83`). Versioned prefixes track the feature batch that introduced
each model. Pydantic body validation is automatic for every `POST`
route declared with a typed body parameter.

## Session handling subsystem

### `require_session` — the auth gate

```python
def require_session(x_session_id: Optional[str] = Header(default=None)) -> dict:
```

**Pipeline:**
1. Header missing → `HTTPException(401, "missing_session")`.
2. `sessions_store.get_session(x_session_id)` returns `None` → 401 `"invalid_session"`.
3. Session `expires_at < time.time()` → `sessions_store.delete_session(x_session_id)` + 401 `"expired_session"`.
4. `users_store.get_user(session["user"])` → populate cohort (defensive `try/except` for backend hiccups).
5. Return `{session_id, user, cohort}` dict to downstream `Depends`.

**Session TTL** is `SESSION_TTL_SECONDS` (env `CLARITYOS_SESSION_TTL`,
default 86400).

### Cohort gates (cascading dependencies)

| Gate | Line | Check |
|---|---|---|
| `_require_admin(session=Depends(require_session))` | 804 | `session["user"] == ADMIN_USER` |
| `_require_founder(session=Depends(require_session))` | 813 | `session["cohort"] in FOUNDER_LIKE_COHORTS` |

Cohort flows from `users_store` through `require_session` into the
cohort gates; it does NOT propagate into the kernel, model_router,
or operator_state.

### Session log redaction

```python
def _session_ref(session_id: str) -> str:
    if not session_id:
        return "<none>"
    return session_id[:8] + "..."
```

Used in every log line that references a session — the full token
never appears in stdout. This is the **runtime layer's primary
session-privacy invariant.**

### Session creation paths

- `/login` (line 689) — credentials match → `_create_session_for(username)`.
- `/register` (line 715) — new user → `_create_session_for`.
- `/invite/{token}/redeem` (1003), `/invite/{token}/finalize` (1087) — invite-driven flows.

`_create_session_for` (line 857) → `sessions_store.create_session(...)` → new session row with `expires_at = time.time() + SESSION_TTL_SECONDS`.

## Continuity subsystem (where it actually lives)

There is **no** `continuity.py` module. The "continuity layer" concept
is split across two files:

| Component | Location |
|---|---|
| `continuity_section(user_id, last_topics_n=3)` | `operator_state.py:485` |
| `continuity_context(user_id)` | `operator_state.py:508` |
| `related_runs(user_id, *, region=None, topic=None, limit=5)` | `operator_state.py:458` |
| `/continuity/snapshot` HTTP route | `app.py:8253` |
| Preference decay (the data layer underneath continuity) | `operator_state._decay_and_bump:145` |

The route handler in `app.py:8253` is a thin wrapper that calls
`operator_state.continuity_context` and returns the result inside the
standard envelope.

## Error envelope

### `error_response` — the only constructor

```python
def error_response(error: str, message: str) -> dict:
    return {"ok": False, "error": error, "message": message}
```

### Global exception handler

```python
@app.exception_handler(HTTPException)
async def _envelope_http_exception_handler(_request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "ok" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response("http_error", str(exc.detail)),
    )
```

**Behaviour:**
- `HTTPException(detail=envelope_dict)` → JSONResponse with the envelope as the body.
- `HTTPException(detail="bare string")` → wrapped via `error_response("http_error", str(detail))`.
- Every error response is guaranteed `{ok: false, error, message}` shape — the client never sees a raw FastAPI error.

### Status code conventions

| Status | Used for |
|---|---|
| 400 | bad payload / bad signature / `v29_hardening.raise_validation` defaults |
| 401 | `missing_session`, `invalid_session`, `expired_session` |
| 402 | `BillingError` on intent-creation paths |
| 403 | `_require_admin`, `_require_founder`, `feature_disabled` |
| 404 | `not_found` on intent / user lookups |
| 409 | `user_exists`, `subscription_inactive`, `cohort_full` |
| 422 | FastAPI/Pydantic body validation failures (automatic) |
| 429 | `v29_hardening.enforce_rate_limit` rejections |
| 500 | GCS init errors, defensive `pragma: no cover` branches |
| 503 | `billing_not_configured`, `webhook_not_configured` |

## Rate limiting

### Public endpoints — IP key

```python
v29_hardening.check_rate_limit(f"ip:{ip}", route_path, capacity=10, window_s=600.0)
```

Used by `/waitlist/join` (line 9420) — capacity 10 per 10 minutes per
IP. The IP key prevents per-account bypass.

`_client_ip(request)` (line 9402) extracts the first-hop IP from
`X-Forwarded-For` (Cloud Run forwards via this header), falling back
to the socket peer.

### Authenticated endpoints — user key

```python
v29_hardening.enforce_rate_limit(user, route_path)
```

Used by every founder/membership/billing/ELINS route. The capacity and
window are configured inside `v29_hardening`.

### Feature gates

`v29_hardening.feature_enabled(flag, user, cohort)` is called before
work begins on routes that depend on a feature flag (e.g.
`membership_ui_enabled`, `founder_tier_enabled`, `v28_surfaces`).
Disabled features → `HTTPException(403, "feature_disabled")`.

## Boundary interactions

### With the kernel (`intelligence_kernel`)

`app.py` calls into the kernel for:
- `intelligence_kernel.run_thread_message` (from `/me/threads/{tid}/message`).
- `intelligence_kernel.summarize_thread` (from `/me/threads/{tid}/summarize`).
- `intelligence_kernel.run_ELINS`, `run_regional_ELINS`, `run_macro_ELINS`, `run_emotional_physics`, `run_elins_v2`, `run_manual_ingestion`, `run_feed_ingestion`, `run_ingestion_cycle`, `run_regression_first` (from various `/elins/*` and `/me/*` routes).
- `intelligence_kernel.kernel_status` (from `/founder/intelligence/kernel/status`).
- `intelligence_kernel.kernel_view_for_user` (from `/me`).

**Callback path:** `app.py` defines `_run_g_elins` (the heavyweight #G
analyser) and passes it as the `runner` callable to
`intelligence_kernel.run_G` — **the only callable-injection cycle break
in the runtime layer.**

### With model_router

Direct calls from `app.py`:
- `/founder/models/status` → `model_router.get_router_status`.
- `/founder/models/override` → `model_router.set_founder_default_model`.

No direct `route_request` calls — that flows through the kernel.

### With operator_state

Direct calls from `app.py`:
- `/me/operator_state` → `operator_state.{get_,update_}operator_state`.
- `/me/operator_state/model` → `operator_state.set_preferred_model`.
- `/founder/operator/{user_id}/state` → `operator_state.get_operator_state`.
- `/continuity/snapshot` → `operator_state.continuity_context`.

### With memory_vault

Direct calls from `app.py`:
- `/me/vault/*` (notes, embeddings, status) → `memory_vault.*`.
- `/founder/vault/*` (users, keys, item) → `memory_vault.*`.

**Note:** The legacy `/vault/*` routes (write, update, delete, list)
go through `vault_store.py`, NOT `memory_vault.py`. They are
**separate storage systems** despite sharing the "vault" name.

### With billing subsystem

- `/billing/webhook` (line 1164) — Stripe webhook receiver.
- `/billing/intent`, `/billing/intent/confirm`, `/billing/history` — direct calls to `billing_intents` + `membership_store`.
- `/membership/*` — full membership lifecycle (activate / cancel / confirm / g/buy_*).
- `/founder/membership/*` — manual founder controls.
- `/founder/billing/status` — `billing_config.get_billing_status`.

### With GCS

`load_library_object(path)` → `_get_gcs_client()` (lazy) → `gcs_storage.Client()` → GCS blob read. Used only by `/library/*` routes. **The only direct GCS access in the runtime layer.**

## Invariants

### Auth + session
1. Every authenticated route uses `Depends(require_session)`.
2. Cohort gates layer on top via `_require_admin` / `_require_founder`.
3. Session tokens never appear in full in logs.
4. Expired sessions are deleted server-side before the 401 is raised.
5. Passwords are bcrypt-hashed before persistence.
6. Bootstrap admin password is printed via `print(...)`, never via `logger.*`.

### Errors + envelopes
7. Single error envelope: `error_response` is the only constructor.
8. Global exception handler enforces the envelope on every `HTTPException`.

### CORS + rate-limiting
9. `allow_origins=CORS_ORIGINS` (no `*`).
10. `allow_methods=[GET, POST, OPTIONS]`, `allow_headers=[Content-Type, X-Session-ID, Authorization]`.
11. Public endpoints rate-limit by IP key.
12. Authenticated endpoints rate-limit by user key.

### Billing + scheduler
13. Renewal scheduler boots at most once per process (`/membership/activate` lazy-boots).
14. Webhook idempotency via `billing_config.seen_event`.
15. Stripe-mode signature verification is mandatory.

### Boot resilience
16. Optional routers (acceptance_dashboard, runtime_http) are mounted via `try/except ImportError`.
17. GCS client is lazy-init; missing google-cloud-storage doesn't block boot.

## Privacy contract (app.py-specific)

- **bcrypt one-way password hashing** at the single `_create_user` site.
- **Session token redaction** via `_session_ref` — 8-char prefix only.
- **Bootstrap admin password printed via `print()`** — NOT `logger.*`. **Note: Cloud Run captures stdout, so this print lands in Cloud Logging anyway.** Documented privacy gap (PASS‑3B B6).
- **CORS allowlist strict** — no wildcard.
- **No API keys, no passwords, no full session tokens** in any log line.
- **`user_id` IS logged in full** — caller responsibility to not encode PII in user IDs.

## Non-goals

`app.py` is **not**:

- a kernel — it never imports any intelligence-layer engine directly. All kernel runs route through `intelligence_kernel`.
- a model provider — no LLM SDK imports.
- a vault — `memory_vault` is the persistence layer.
- a state machine for billing — the state machine lives in `billing_intents` and `billing_renewal`.
- a stateless service — it holds `_gcs_client` and the `FastAPI` app instance as process globals.
- the only entry point in the codebase — but it IS the only HTTP entry point.
- a multi-tenant isolator — multiple users share the process. Per-user isolation lives in `memory_vault`'s PBKDF2 key derivation.

## Fiction removed

The following constructs are explicitly not present in `app.py`:

- **No `gateway.py` module.** All gateway concepts (CORS, routing, auth, error envelope) live inline in `app.py`.
- **No `session_manager.py` module.** Session creation/validation lives in `app.py`; storage lives in `sessions_store.py`.
- **No `continuity.py` module.** Continuity helpers live in `operator_state.py`; the HTTP route lives in `app.py`.
- **No `vault.py` module.** Persistence is `memory_vault.py` (per-user encrypted KV) and `vault_store.py` (legacy v1 notes/sessions/elins_raw storage — separate subsystem).
- **No `request_pipeline.py` module.** FastAPI's `Depends` chain + middleware IS the pipeline.
- **No direct LLM SDK import.** All provider calls funnel through `model_router._http_post_json`.
- **No direct intelligence-layer engine import** (`azimuth`, `orchestrator_*`, `language_*`, `feedback_*`, `primitive_selection_engine`, etc.). The intelligence layer is production-dormant; the runtime reaches it through the kernel, which itself bypasses these modules.

Only the behaviour, routes, helpers, and invariants described in this
document are present in the code. The verified surface is locked by
the **62 test files** under `tests/` that import `app`.
