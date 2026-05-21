# Runtime Architecture

This is the canonical synthesis document for the ClarityOS runtime
layer — **5 real Python modules totalling 19,630 lines** that together
implement every HTTP-reachable behaviour in the system.

```
app.py                   15,278  HTTP / session / auth / billing webhook / mounted routers
intelligence_kernel.py    2,045  Kernel (ESO + model + ELINS + thread + audit funnels)
model_router.py             964  Model selection + provider dispatch + outbound HTTP
operator_state.py           592  Per-user preference + history + continuity
memory_vault.py             751  Per-user encrypted KV (4 backends)
```

The conceptual modules from earlier framings (`gateway.py`,
`continuity.py`, `vault.py`, `session_manager.py`,
`request_pipeline.py`) **do not exist as files** — their
responsibilities live inside `app.py` and `memory_vault.py`.

For per-module deep dives, see:

- [docs/runtime_app.md](runtime_app.md)
- [docs/intelligence_kernel.md](intelligence_kernel.md)
- [docs/model_router.md](model_router.md)
- [docs/operator_state.md](operator_state.md)
- [docs/memory_vault.md](memory_vault.md)

---

## 1. Canonical runtime call graph

The canonical call path for a single authenticated request, traced
from HTTP entry to vault persistence and back:

```
HTTP request (X-Session-ID header)
    │
    ▼
app.py — FastAPI route handler (e.g. /me/threads/{tid}/message)
    │
    ├─ require_session(x_session_id)         → sessions_store.get_session
    │     (raises 401 missing/invalid/expired)
    ├─ users_store.get_user(user)            (for cohort)
    ├─ feature flag check                    (v29_hardening.feature_enabled)
    ├─ rate limit                            (v29_hardening.enforce_rate_limit)
    │
    ▼
intelligence_kernel.run_thread_message(user, tid, content, project_id=...)
    │
    ├─ threads_vault.get_thread_meta(user, tid)    → memory_vault.vault_list
    │     (validates project_id; KeyError = bubble to 404)
    │
    ├─ threads_vault.append_message(...)           → memory_vault.vault_put
    │
    ├─ _resolve_project_routing(user, project_id)  → projects_vault.get_project
    │                                              → memory_vault.vault_list
    │
    ├─ _resolve_model(user, task="thread")
    │     │
    │     ├─ model_router.select_model(user, task=..., override=project_default)
    │     │     │
    │     │     ├─ is_valid_model(override)?       → SUPPORTED_MODELS lookup
    │     │     ├─ get_founder_default_model()     → _founder_default_model
    │     │     ├─ lazy import operator_state
    │     │     │  └─ operator_state.get_operator_state(user)
    │     │     │     └─ memory_vault.vault_list(user)
    │     │     └─ TASK_DEFAULTS["thread"]
    │     │
    │     ├─ operator_state.record_model_used(user, model_id)
    │     │     └─ memory_vault.vault_put(user, "operator_state.last_model_used", ...)
    │     │
    │     └─ (if local) operator_state.bump_local_model_usage(user)
    │           └─ memory_vault.vault_put(user, "operator_state.local_model_usage_count", ...)
    │
    ├─ _apply_project_routing(model_id, default, allowed)
    │     (reconciles router choice against project constraints)
    │
    ├─ threads_vault.get_thread(user, tid)        → memory_vault.vault_list
    │     (canonical transcript for prompt)
    │
    ├─ _format_thread_context(messages, latest=content)
    │     (last 8 messages, 6KB cap)
    │
    ├─ model_router.route_request(model_id, prompt, temperature, max_tokens)
    │     │
    │     ├─ parse_provider(model_id)
    │     ├─ _PROVIDER_HANDLERS[provider]         (e.g. _call_openai)
    │     │     │
    │     │     ├─ _provider_configured(provider)? — no → _mock_result
    │     │     ├─ build JSON body
    │     │     ├─ with _request_timeout(get_call_timeout(provider)):
    │     │     │  └─ _http_post_json(url, headers, body)
    │     │     │        └─ urllib.request → OpenAI API
    │     │     └─ extract text; on any exception → _mock_result
    │     │
    │     └─ return {ok, model_id, provider, text, mock, ts}
    │
    ├─ threads_vault.append_message(...)          → memory_vault.vault_put
    │     (assistant turn)
    │
    └─ kernel_logging.log_kernel_run(kind="thread", ok, duration_ms, meta={...})
    │
    ▼
app.py — wraps result in envelope, returns JSONResponse
    │
    └─ _envelope_http_exception_handler unwraps detail=envelope on any HTTPException
```

### Back-edges and cycle breaks

Two cycle-avoidance points are traversed on every call:

| Point | Site | Mechanism |
|---|---|---|
| `model_router.select_model` → `operator_state` | line 297 | **Lazy `import operator_state`** inside function body |
| `intelligence_kernel.run_thread_message` → `threads_vault` (not `app.py`) | — | Reads `threads_vault` directly; never back-imports `app.py` |

### `#G` runner injection path

The kernel needs the heavyweight `#G` analyser (which lives in
`app.py`'s `_run_g_elins`), but **cannot import `app.py`** without
creating a cycle. Solution: callable injection.

```
HTTP request → app.py route handler
    │
    └─ intelligence_kernel.run_G(user, input, runner=app._run_g_elins, ...)
            │
            └─ runner(input, user)            ← the actual #G analyser
                    │
                    └─ (heavyweight #G analysis inside app.py)
```

**Zero import coupling.** The kernel never sees `app.py`'s module
object — only the callable. Documented at `intelligence_kernel:27` as
the deliberate cycle break.

### The reverse direction is never traversed

- `memory_vault` never imports anything internal.
- `operator_state` only lazy-imports `model_router.is_valid_model`.
- `model_router` only lazy-imports `intelligence_kernel.run_regression_first`.
- `intelligence_kernel` never imports `app.py`.

The runtime forms a **near-DAG with two lazy back-edges**.

---

## 2. Boundary topology

Five real boundaries, mapped to real files, plus three cross-cutting
boundaries (logging, concurrency, privacy gates).

```
═══════════════════════════════════════════════════════════════════════════
                          Layer 5 — HTTP / Session / Auth
                          (app.py, 15,278 lines)
                          BD1 — HTTP boundary
═══════════════════════════════════════════════════════════════════════════
                                    │
                                    │  (injects #G runner)
                                    ▼
═══════════════════════════════════════════════════════════════════════════
                          Layer 4 — Intelligence Kernel
                          (intelligence_kernel.py, 2,045 lines)
                          BD2 — Kernel boundary
═══════════════════════════════════════════════════════════════════════════
                     │              │              │
                     ▼              ▼              ▼
            ┌──────────────────┐ ┌──────────────────────┐
            │ Layer 3a Routing │ │ Layer 3b State       │
            │ (model_router,   │ │ (operator_state,     │
            │  964 lines)      │ │  592 lines)          │
            │ BD3 — router     │ │ BD4 — operator-state │
            └──────────────────┘ └──────────────────────┘
                     │              │
                     │  (lazy)      │
                     ◄─────────────►│
                                    │
                                    ▼
═══════════════════════════════════════════════════════════════════════════
                          Layer 2 — Persistence
                          (memory_vault.py, 751 lines)
                          BD5 — vault boundary
═══════════════════════════════════════════════════════════════════════════
                                    │
                                    ▼ (firestore backend only)
                              Google Firestore
                              memory_vault/{user}/entries/{key}
```

### Boundary discipline

| Boundary | File | Owns | Cross-boundary discipline |
|---|---|---|---|
| **BD1 (HTTP)** | `app.py` | Routes, auth, CORS, error envelope, rate limit, bcrypt | Injects `#G` runner into kernel; never imported by other runtime modules |
| **BD2 (Kernel)** | `intelligence_kernel.py` | ESO funnel, model funnel, audit funnel, S_ELINS QC, topic-label construction | Never imports `app.py`; analysis-derived topic labels only |
| **BD3 (Router)** | `model_router.py` | Provider selection, outbound HTTP, mock fallback, founder default | Lazy reads from operator_state; lazy delegates to kernel (v79) |
| **BD4 (State)** | `operator_state.py` | Per-user preferences, history, decay, continuity | Lazy validates via model_router.is_valid_model; sole storage dep is vault |
| **BD5 (Vault)** | `memory_vault.py` | Per-user encrypted KV, 4 backends, namespace allow-list, master secret | Zero internal imports — the deepest leaf |

### Logging boundary (cross-cutting)

All 5 modules use stdlib `logging` with the namespace pattern `clarityos.*`:

| Module | Logger name | Active? |
|---|---|---|
| `app.py` | `clarityos` | ✅ writes at info/warning |
| `intelligence_kernel.py` | `clarityos.intelligence_kernel` | ✅ via `kernel_logging.log_kernel_run` |
| `model_router.py` | `clarityos.model_router` | ✅ warnings on provider failures |
| `operator_state.py` | `clarityos.operator_state` | ⚠️ defined but never used |
| `memory_vault.py` | `clarityos.memory_vault` | ✅ warnings on decrypt failures |

Discipline rules:

- Session tokens truncated via `_session_ref` (8 chars).
- Passwords never logged (bootstrap uses `print()`, not `logger.*`).
- API keys never enter module state.
- Provider responses logged only on failure as `err=str(e)`.
- Full `user_id`, vault keys, model_ids ARE logged in plain text (PASS‑3D gap G‑P4).

### Concurrency boundary

| Lock | Module | Type | Allocation |
|---|---|---|---|
| `_LOCK` | memory_vault | `threading.RLock()` (re-entrant) | Always at module load |
| `_SEQ_LOCK` | operator_state | `threading.Lock()` | Always at module load |
| `_macro_seq_lock` | intelligence_kernel | `Optional[threading.Lock]` | **Lazy** (first call) |

**Explicit thread-unsafety:** `model_router._PROVIDER_HTTP_TIMEOUT`
mutation via `_request_timeout` context manager is documented as
**not thread-safe** (line 407). Safe in single-threaded uvicorn; would
race in multi-worker.

### Privacy gates (8 — see §5 for full enumeration)

| Gate | Location | Mechanism |
|---|---|---|
| G1 — HTTP entry | `app.py:117–309, 463, 477` | bcrypt + session-redact + CORS + rate-limit + envelope |
| G2 — Kernel → state | `intelligence_kernel.run_*` | Analysis-derived topic labels only |
| G3 — Kernel → ESO | `intelligence_kernel:100–142` | Mode gate + sanitize_eso + graceful degrade |
| G4 — State → vault | `operator_state:133, 107` | `_strip_forbidden` + `_trim_topic` |
| G5 — Kernel → router | `intelligence_kernel:717, model_router:755` | Length-capped prompts + truncated IDs |
| G6 — Router → providers | `model_router:352, 419` | 60-char preview + no API key logging |
| G7 — Vault encryption | `memory_vault:231, 263` | PBKDF2 per-user + HMAC-CTR + HMAC-SHA256 |
| G8 — Logging discipline | all 5 modules | Selective redaction |

---

## 3. Cycle analysis

The runtime carries **two direct import cycles within the 5 modules**,
both broken by lazy imports. Plus three additional cycles touching
modules outside the 5-module scope.

### Direct cycles (within 5 modules)

| Cycle | Edge 1 | Edge 2 | Break |
|---|---|---|---|
| **BD3 ↔ BD4** (`model_router ↔ operator_state`) | `model_router.select_model:297` — `import operator_state` (lazy) | `operator_state.set_preferred_model:351` — `import model_router` (lazy) | **Symmetric lazy import** |
| **BD3 ↔ BD2** (`model_router ↔ intelligence_kernel`) | `intelligence_kernel:54` — `import model_router` (eager top-level) | `model_router.call_regression_first:942` — `import intelligence_kernel` (lazy) | **Asymmetric** — kernel eager, router lazy |

### Direct cycles (outside the 5 modules)

| Cycle | Break |
|---|---|
| `model_router ↔ local_model_runtime` | 3 lazy import sites in router (`_call_local:583`, `get_local_runtime_status:654`, `_reset_for_tests:961`) |
| `app.py ↔ acceptance_dashboard` | `try/except ImportError` at every mount site (`app.py:152–199`) |
| `app.py ↔ runtime_http` | `try/except ImportError` at every mount site (`app.py:207–252`) |

### Callable-injection edge

**The exception to the lazy-import pattern.** `intelligence_kernel ↔ app.py`
is broken by callable injection rather than lazy imports:

- `app.py` calls `intelligence_kernel.run_G(user, input, runner=_run_g_elins, ...)`.
- The kernel never imports `app.py` — it receives the runner as a parameter.
- Documented at `intelligence_kernel:27` as the cleanest cycle break in the codebase.

### Why no other cycles exist

| Pair | Why no cycle |
|---|---|
| `app.py` ↔ any other | `app.py` imports the other 4 eagerly; none of them imports `app.py` |
| `intelligence_kernel` ↔ `operator_state` | Kernel imports state eagerly; state never imports kernel |
| `intelligence_kernel` ↔ `memory_vault` | Kernel imports vault eagerly; vault has **zero internal imports** |
| `model_router` ↔ `memory_vault` | Router never imports vault; vault never imports router |
| `operator_state` ↔ `memory_vault` | State imports vault eagerly; vault never imports state |
| `app.py` ↔ `memory_vault` | App imports vault eagerly; vault never imports anything |

**`memory_vault` is the unambiguous bottom of the graph.** `app.py` is
the unambiguous top. The middle three (`intelligence_kernel`,
`model_router`, `operator_state`) form a partial DAG with two lazy
back-edges.

---

## 4. Cross-module invariants

46 cross-module invariants from PASS‑3A, organized by the flow they
enforce.

### Session handling chain

| # | Invariant |
|---|---|
| X1 | The session-token-to-user mapping is opaque outside `app.py` + `sessions_store`. Kernel, router, state, vault all operate on `user_id` strings only |
| X2 | Cohort flows from session into `_require_founder`/`_require_admin` only — never propagates into kernel/router/state |
| X3 | Session expiry is silently destructive (deleted server-side before 401) |

### Model selection chain

| # | Invariant |
|---|---|
| X4 | **Selected ≡ recorded.** `intelligence_kernel._resolve_model` writes `last_model_used` to operator_state after every `model_router.select_model` call |
| X5 | Local model id triggers `bump_local_model_usage` at the same call site |
| X6 | `select_model` step 3 reads operator_state via lazy import |
| X7 | `set_preferred_model` validates via lazy `model_router.is_valid_model` import (symmetric cycle break) |
| X8 | Step 4 of `select_model` (`TASK_DEFAULTS` fallback) is module-local — no cross-module read |

### ESO mode chain

| # | Invariant |
|---|---|
| X9 | Mode override is written to BOTH `operator_state.set_external_signal_mode` AND `users_store.update_user` (dual source of truth) |
| X10 | Mode resolution has 4-step fallback: explicit override → users_store → operator_state → `"cloud_only"` |
| X11 | Mode != `cloud_perplexity` is a hard gate at the kernel boundary; perplexity_oracle is never called |
| X12 | `perplexity_oracle.sanitize_eso` happens at the kernel boundary before downstream handoff |
| X13 | Failed oracle calls log via `perplexity_oracle._record_error` + return `None` |

### ELINS persistence chain

| # | Invariant |
|---|---|
| X14 | Pipeline order is fixed: `generate_ELINS → _run_s_elins_qc → save_daily_run → update_indexes → record_elins_interaction → log_kernel_run` |
| X15 | `S_ELINS QC` is attached as `elins_obj["qc"]` before persistence (even when QC fails → `qc=None`) |
| X16 | Persistence + index updates are independently fault-tolerant (two separate try/except blocks) |

### Thread/project routing chain

| # | Invariant |
|---|---|
| X17 | Thread `project_id` is validated against stored thread meta BEFORE any work (cheap pre-flight) |
| X18 | `_apply_project_routing` reconciles router choice against project allow-list |
| X19 | `last_model_used` is re-recorded if allowed_models forced a different choice |

### Vault storage chain

| # | Invariant |
|---|---|
| X20 | All operator_state reads/writes flow through memory_vault |
| X21 | All threads_vault / projects_vault reads/writes flow through memory_vault |
| X22 | Namespace ownership is implicit (operator_state owns `operator_state.*`, `elins.*`, `g_runs.*`; threads_vault owns `threads.*`; projects_vault owns `projects.*`; chain_store owns `regression_chains.*`, `regression_packets.*`) |
| X23 | Vault is the only encryption boundary — upstream layers write plaintext dicts |

### Single-funnel invariants (cross-module)

| # | Funnel | Site |
|---|---|---|
| X24 | ESO resolution | `intelligence_kernel._resolve_external_signal_mode` |
| X25 | Model selection | `intelligence_kernel._resolve_model` → `model_router.select_model` |
| X26 | Audit logging | `kernel_logging.log_kernel_run` (every kernel `run_*`) |
| X27 | HTTP outbound | `model_router._http_post_json` |
| X28 | Error envelope | `app.py.error_response` + global handler |
| X29 | Vault backend dispatch | `memory_vault._load_user` / `_save_user` |
| X30 | Per-user encryption | `memory_vault._derive_key` |
| X31 | Mock provider response | `model_router._mock_result` |

### Privacy invariants (cross-module)

| # | Invariant |
|---|---|
| X32 | Raw user text never crosses kernel → operator_state (analysis-derived topic labels enforce) |
| X33 | Raw user text never enters model_router log lines (`_mock_result` truncation + `_shape_prompt_from_intent` field-only construction) |
| X34 | API keys never enter module-level state (read from `os.environ` at call time, used to construct HTTP headers) |
| X35 | Vault master secret is only read inside `memory_vault` (two read sites: `_secret()` line 167 and `_derive_key()` line 237) |

### Determinism invariants (cross-module)

| # | Invariant |
|---|---|
| X36 | `select_model(user, task)` deterministic given inputs + (operator_state, founder_default) state |
| X37 | Kernel `run_*` deterministic w.r.t. persistence state at call time (documented `intelligence_kernel:26`) |
| X38 | Vault decryption deterministic |
| X39 | Vault encryption non-deterministic by design (fresh nonce per call — semantic security under CPA) |
| X40 | `select_reasoning_mode` is pure |
| X41 | Mock provider responses deterministic given prompt |

### Failure-handling invariants

| # | Invariant |
|---|---|
| X42 | Kernel never bubbles oracle/persistence/telemetry failures |
| X43 | Router never raises from `route_request` for real-network reasons |
| X44 | Operator_state never wraps vault errors — failures propagate |
| X45 | Vault `vault_list` tolerates per-key decrypt failures; `vault_get` raises (intentional asymmetry) |
| X46 | Test reset hooks must be invoked in dependency order via `tests/conftest.py` |

---

## 5. Privacy & determinism contract

### 8 privacy gates (G1–G8)

| Gate | Location | Mechanism |
|---|---|---|
| **G1 — HTTP entry** | `app.py` | bcrypt + session-redact + CORS + rate-limit + envelope |
| **G2 — Kernel → operator_state** | `intelligence_kernel.run_*` | Analysis-derived topic labels only |
| **G3 — Kernel → ESO** | `intelligence_kernel:100–142` | Mode gate + sanitize_eso + graceful degrade |
| **G4 — operator_state → vault** | `operator_state:133, 107` | `_strip_forbidden` (4 fields) + `_trim_topic` (200 chars) |
| **G5 — Kernel → router** | `intelligence_kernel:717, model_router:755` | Length-capped prompts + truncated IDs |
| **G6 — Router → providers** | `model_router:352, 419` | 60-char preview + no API key logging |
| **G7 — Vault encryption** | `memory_vault:231, 263` | PBKDF2 per-user + HMAC-CTR + HMAC-SHA256 + scheme byte |
| **G8 — Logging discipline** | all 5 modules | Selective redaction |

### 25 explicit privacy guarantees (EG1–EG25)

EG1 bcrypt one-way passwords · EG2 session token truncated to 8 chars
in logs · EG3 vault master secret mandatory (no default) · EG4
per-user PBKDF2 key isolation · EG5 vault namespace allow-list (11
entries) · EG6 `_strip_forbidden` removes 4 raw-text fields · EG7
topic truncation at 200 chars · EG8 mock prompt truncation at 60
chars · EG9 dispatcher prompts use `[:8]` truncated IDs · EG10 thread
context capped (8 messages / 6 KB; summary: 20 messages / 8 KB) · EG11
CORS allowlist strict (no `*`) · EG12 API keys never in module state ·
EG13 encryption ON by default · EG14 HTTP-error envelope universal ·
EG15 webhook event idempotency · EG16 Stripe-mode signature mandatory ·
EG17 encrypt-then-MAC · EG18 `hmac.compare_digest` for MAC · EG19
atomic fs writes · EG20 single-RLock vault access · EG21 history caps
prevent unbounded growth · EG22 vault key shape enforced · EG23 ESO
mode gate · EG24 ESO output sanitisation · EG25 failed oracle calls
degrade silently.

### 9 implicit privacy guarantees (IG1–IG9)

IG1 no raw text in operator_state writes (kernel-side convention) ·
IG2 no PII in `g_id` / `elins_id` strings · IG3 no PII in
`/billing/intent` metadata (caller contract) · IG4 provider response
shapes are not validated semantically · IG5 `runner` callable returns
`{"ok": bool, ...}` · IG6 vault values are JSON-serialisable · IG7 no
raw payload in dispatcher-shaped prompts · IG8 engine-generated
rationale strings are non-PII · IG9 test reset hooks wipe sensitive
caches.

### 11 privacy gaps (G‑P1 to G‑P11)

| ID | Gap | Severity |
|---|---|---|
| G‑P1 | `_strip_forbidden` enumerated blocklist (4 fields) | High |
| G‑P2 | Migration preserves un-stripped legacy entries | High |
| G‑P3 | Forbidden-field guard inconsistency across schema roots | Medium |
| G‑P4 | Selective log redaction — full user_id / vault keys / model_ids logged | High |
| G‑P5 | Encryption opt-out exists (`CLARITYOS_VAULT_PLAINTEXT`) | High |
| G‑P6 | **Bootstrap admin password captured by Cloud Logging** despite `print()` not `logger.*` | **CRITICAL** |
| G‑P7 | No per-user key rotation primitive | High |
| G‑P8 | `/billing/intent/confirm` returns full intent record | Low |
| G‑P9 | Transaction metadata returned raw on history endpoints | Medium |
| G‑P10 | `_KEY_CACHE` retains all per-user keys until process restart | Medium |
| G‑P11 | Per-call env var reads (no caching) | Low |

### 18 non-deterministic surfaces

| Category | Surfaces |
|---|---|
| **Intentional non-determinism** | Vault envelope ciphertext (fresh nonce per call), `secrets.token_urlsafe` (operator IDs, session IDs, bootstrap password), `_macro_seq` (process-global) |
| **Wall-clock-derived** | `created_ts`, `last_active_ts`, `_make_history_key.ts`, `_make_macro_run_id`, `_mock_result.ts`, `duration_ms`, webhook event ts |
| **Real provider responses** | OpenAI/Anthropic/Gemini text (temperature variance), HTTP transport latency |
| **Environment-driven** | `_backend()`, `_provider_configured`, `_is_encrypted`, `_secret`, `_pbkdf2_iters` (all read on every call) |
| **Process-global mutable** | `_founder_default_model`, `_LOCAL_HANDLE_CACHE`, `_PROVIDER_HTTP_TIMEOUT` |

### 16 process-global leak surfaces

| Module | Globals |
|---|---|
| app.py | `_gcs_client`, `app` |
| intelligence_kernel | `_macro_seq`, `_macro_seq_lock` |
| model_router | `_founder_default_model`, `_LOCAL_HANDLE_CACHE`, `_LOCAL_HANDLE_PATH`, `_PROVIDER_HTTP_TIMEOUT` |
| operator_state | `_SEQ_LOCK`, `_HISTORY_SEQ` |
| memory_vault | `_LOCK`, `_MEM_STORE`, `_SQLITE_CONN`, `_SQLITE_PATH_CACHED`, `_FIRE_CLIENT`, `_KEY_CACHE` |

### 10 cross-module privacy/determinism interactions

X1 selected ≡ recorded · X2 ESO mode dual-source-of-truth · X3
analysis-derived topic flows kernel → state · X4 vault encryption is
downstream of all content filters · X5 founder default overrides
per-user preference · X6 mock determinism preserves text not metadata ·
X7 lazy imports preserve module-load determinism · X8 `_KEY_CACHE`
couples encryption non-determinism to process lifetime · X9
operator_state strip is the only "data filter" before vault · X10
audit funnel logs duration but not content.

---

## 6. Boundary violations and near-violations

### Direct violations (V1–V3)

| ID | Violation | File |
|---|---|---|
| **V1** | ESO mode mirror across `operator_state` AND `users_store` (single-source-of-truth violation) | `intelligence_kernel:167–174` |
| **V2** | Founder default in `model_router` process-global, not vault (persistence boundary violation) | `model_router:147` |
| **V3** | `_gcs_client` in `app.py` module-global (client encapsulation boundary) | `app.py:509` |

### Near-violations (N1–N5)

| ID | Near-violation | File |
|---|---|---|
| **N1** | `operator_state` lazy-imports `model_router` (layering inversion — state reaches into routing for validation) | `operator_state:351` |
| **N2** | Kernel reads `users_store` for ESO mirror | `intelligence_kernel:86–89` |
| **N3** | `app.py` reads `users_store` for cohort | `app.py:499–502` |
| **N4** | Kernel logging `meta` may contain leakable fields (caller-discipline) | `intelligence_kernel` (every `run_*`) |
| **N5** | Lazy-imported modules can fail silently (`except Exception: pass`) | `model_router:302` |

### Escalated boundary issues (B1–B10)

| ID | Issue | Severity |
|---|---|---|
| **B1** | `_request_timeout` thread-safety (will race in multi-worker uvicorn) | High |
| **B2** | `_macro_seq_lock` TOCTOU on first call (lazy lock) | Low |
| **B3** | `_LOCAL_HANDLE_CACHE` cross-user | Documented design |
| **B4** | `_KEY_CACHE` process lifetime | Medium |
| **B5** | Founder default cross-user | Documented design |
| **B6** | **Bootstrap password captured by Cloud Logging** | **CRITICAL** |
| **B7** | No per-user key rotation | High |
| **B8** | `_strip_forbidden` enumerated blocklist | High |
| **B9** | Encryption opt-out exists | High |
| **B10** | Provider response shape assumptions | Medium |

---

## 7. Cycle-avoidance and boot-resilience patterns

Five distinct patterns are in use across the runtime:

### Pattern P1 — Callable injection

| Usage | Location |
|---|---|
| `#G` runner | `intelligence_kernel.run_G(user, input, *, runner, ...)` — runner passed as parameter |

**Properties:** Zero import coupling. Most rigorous. The kernel never
knows where the callable lives.

### Pattern P2 — Lazy import inside function body

| Usage | Location |
|---|---|
| `select_model` step 3 reads operator_state | `model_router:297` |
| `set_preferred_model` validates via model_router | `operator_state:351` |
| `_call_local` reaches into local_model_runtime | `model_router:583` |
| `get_local_runtime_status` reaches into local_model_runtime | `model_router:654` |
| `_reset_for_tests` resets local_model_runtime | `model_router:961` |
| `call_regression_first` reaches into intelligence_kernel | `model_router:942` |

**Properties:** Pays the import cost on first call. Clean for sparse
cross-references. Tested by all 5 modules under conftest reset.

### Pattern P3 — `try/except ImportError` at mount site

| Usage | Location |
|---|---|
| `acceptance_dashboard` routers (8 mounts) | `app.py:152–199` |
| `runtime_http` routers (6 mounts) | `app.py:207–252` |

**Properties:** Most tolerant — boot succeeds even when the imported
module is absent. Used for optional surfaces, not for cycle breaks
per se.

### Pattern P4 — Structural absence (no pattern at all)

For invariants like "no `weaken_constraints` function exists" — the
cycle is avoided by **the function not existing**. Hard-by-absence:

- `no weaken_constraints` (operator_state)
- `no unhash_password` (app.py)
- `no rotate_key` primitive (memory_vault — PASS‑4 FIX‑H5 proposes adding)
- `no resume_from_checkpoint` (orchestrator_workflows — outside the 5 modules)

### Pattern P5 — Configuration-driven dispatch

| Usage | Location |
|---|---|
| Backend dispatch (mock/fs/sqlite/firestore) | `memory_vault._backend()` reads env on every call; `_load_user`/`_save_user` route via `if/elif` |
| Provider dispatch (openai/anthropic/gemini/xai/local) | `model_router._PROVIDER_HANDLERS` dict lookup |

**Properties:** Not a cycle break per se, but keeps the import graph
flat — the dispatcher imports all options at module load (or lazily),
then routes by string key at call time.

### Global-state guards (test reset hooks)

| Module | Reset hook |
|---|---|
| `memory_vault` | `_reset_for_tests` — wipes `_MEM_STORE`, `_KEY_CACHE`, closes `_SQLITE_CONN`, drops `_FIRE_CLIENT` |
| `operator_state` | `_reset_memory_for_tests` — wipes `_HISTORY_SEQ` counter (vault reset is separate) |
| `model_router` | `_reset_for_tests` — wipes founder default + local handle cache + delegates to `local_model_runtime._reset_for_tests` |
| `intelligence_kernel` | `_reset_for_tests` — wipes `_macro_seq` + `_macro_seq_lock` |
| `app.py` | no hook — relies on upstream stores being reset |

`tests/conftest.py` invokes these in dependency order.

---

## 8. Canonical diagrams (text-only)

### Call graph (compact)

```
HTTP request (X-Session-ID)
    │
    ▼
[BD1] app.py
  ├─ require_session → sessions_store
  ├─ feature flag / rate limit (v29_hardening)
  │
  ▼
[BD2] intelligence_kernel
  ├─ _resolve_external_signal_mode → operator_state + users_store
  ├─ _maybe_fetch_eso (gated) → perplexity_oracle + sanitize_eso
  ├─ _resolve_model → model_router.select_model
  │     ↑                ↓
  │     │                ├─ lazy → operator_state.get_operator_state → memory_vault
  │     │                └─ TASK_DEFAULTS fallback
  │     │
  │     └─ operator_state.record_model_used → memory_vault
  ├─ threads_vault / projects_vault / ELINS pipeline → memory_vault
  ├─ model_router.route_request
  │     │
  │     └─ _http_post_json → urllib → OpenAI / Anthropic / Gemini
  ├─ operator_state.record_* → memory_vault
  └─ kernel_logging.log_kernel_run
    │
    ▼
[BD1] app.py wraps in error envelope → JSONResponse
```

### Boundary topology

```
                ┌──────────────────────────────────────┐
                │   BD1 HTTP    (app.py)              │
                └──────────────────────────────────────┘
                              │
                              │ injects #G runner ↓ (callable)
                              ▼
                ┌──────────────────────────────────────┐
                │   BD2 Kernel  (intelligence_kernel)  │
                └──────────────────────────────────────┘
                       │              │
            ┌──────────┘              └───────────┐
            ▼                                      ▼
   ┌──────────────────┐                  ┌──────────────────┐
   │  BD3 Router      │ ◄──(lazy)──►     │  BD4 State       │
   │  (model_router)  │                  │  (operator_state)│
   └──────────────────┘                  └──────────────────┘
            │                                      │
            └──────────────┬───────────────────────┘
                           ▼
                ┌──────────────────────────────────────┐
                │   BD5 Vault   (memory_vault)         │
                │   ┌──────┬─────┬────────┬──────────┐ │
                │   │ mock │ fs  │ sqlite │firestore │ │
                │   └──────┴─────┴────────┴──────────┘ │
                └──────────────────────────────────────┘
```

### State-flow diagram

```
USER REQUEST           ROUTING DECISION         PERSISTENCE
                                                
[X-Session-ID] ─► require_session            ┌─ operator_state.* (vault)
                  │                          │    ├─ external_signal_mode
                  ▼                          │    ├─ preferred_model
              {user, cohort} ──┐             │    ├─ last_model_used
                                │             │    ├─ local_model_usage_count
                                ▼             │    ├─ el_ins_per_turn
            intelligence_kernel              │    └─ created_ts / last_active_ts
                  │                          │
                  ├─ ESO mode resolution ◄───┤
                  │                          │
                  ├─ select_model ◄──────────┤
                  │   (reads preferred_model)│
                  │                          │
                  ├─ record_model_used  ────►┤
                  │                          │
                  ├─ run_ELINS pipeline ────►├─ elins.* (vault)
                  │                          │    └─ {ts, elins_id, topic, region, kind}
                  │                          │       (capped HISTORY_MAX=200)
                  │                          │
                  ├─ run_G  ────────────────►├─ g_runs.* (vault)
                  │                          │    └─ {ts, g_id, mode, topic}
                  │                          │
                  ├─ thread_message ────────►├─ threads.* (vault, via threads_vault)
                  │                          │    ├─ threads.meta.{tid}
                  │                          │    └─ threads.messages.{tid}.{ts}_{seq}
                  │                          │
                  └─ kernel_logging        ┌─ projects.* (vault, via projects_vault)
                                          ┌─ regression_chains.* (vault)
                                          └─ regression_packets.* (vault)
```

### Privacy / determinism boundary map

```
                            FORBIDDEN
                          ─────────────
              raw user text │ session  │  passwords  │  API keys
                            │  tokens  │             │
                            ─────────────
                                      │
                                      │ filtered by 8 gates:
                                      ▼
   [G1] HTTP entry      bcrypt + session redact + CORS + rate-limit + envelope
   [G2] kernel→state    analysis-derived topic labels only
   [G3] kernel→ESO      mode gate + sanitize_eso + graceful degrade
   [G4] state→vault     _strip_forbidden + _trim_topic
   [G5] kernel→router   length-capped prompts + truncated IDs
   [G6] router→provider 60-char preview + no API key logging
   [G7] vault encrypt   PBKDF2 per-user + HMAC-CTR + HMAC-SHA256
   [G8] logging         selective redaction (session_id[:8], no keys, no plaintext)

                            ALLOWED THROUGH
                          ─────────────────
              user_id (full)  │  model_ids   │  vault keys
                              │              │  (in logs)
                              │              │  truncated event_ids
                          ─────────────────
                                      │
                                      ▼
                                 STORAGE / OBSERVABILITY
```

---

## 9. Known guarantees and gaps

### Hard boundaries (cannot be violated — structural enforcement)

- Every authenticated route uses `Depends(require_session)`.
- Vault master secret mandatory (`RuntimeError` if missing).
- Per-user key isolation via PBKDF2 (cryptographic guarantee).
- Namespace allow-list (11 entries) enforced at every vault put/get/delete.
- Encrypt-then-MAC; MAC verified before decrypt.
- `vault_list` tolerant; `vault_get` strict (intentional asymmetry).
- Provider handlers degrade to mock on missing config or any exception.
- `route_request` never raises for real-network reasons.
- History caps (200 per namespace per user) enforced after every record_*.
- `_strip_forbidden` removes 4 named fields before persistence.
- Mock prompt truncation at 60 chars.
- Single error envelope universal across all HTTPExceptions.
- CORS allowlist strict (no `*`).
- Webhook idempotency via `billing_config.seen_event`.
- Stripe-mode signature verification mandatory.

### Soft boundaries (caller-discipline)

- No PII in `/billing/intent` metadata (caller contract).
- Topic labels analysis-derived (kernel-side convention).
- `g_id` / `elins_id` strings non-PII (caller responsibility).
- `runner` callable shape (kernel reads `result.get("ok")` / `get("analysis")`).
- Provider response shape (handler raises `ValueError` on field mismatch but doesn't validate semantically).
- Vault values JSON-serialisable (caller responsibility).
- `update_operator_state` unknown keys silently dropped.

### Hard-by-absence invariants

| Invariant | Why it holds |
|---|---|
| No `weaken_constraints` function | Doesn't exist in any runtime module |
| No `unhash_password` function | bcrypt is one-way; no inverse path exists |
| No `key_rotation` primitive | `vault_clear` doesn't invalidate per-user salt |
| No `resume_from_checkpoint` in workflows | `orchestrator_workflows.py` is a Phase-1 stub |

### Unresolved privacy/determinism issues

| Issue | Severity | Where to fix |
|---|---|---|
| **G‑P6 — Bootstrap admin password captured by Cloud Logging** | **CRITICAL** | `app.py:_bootstrap_admin:355–390` |
| G‑P1 — `_strip_forbidden` enumerated blocklist | High | `operator_state:140` — pattern-match (PASS‑4 FIX‑H1) |
| G‑P2 — Migration preserves un-stripped legacy | High | `operator_state:526–580` — opt-in scrub (PASS‑4 FIX‑H2) |
| G‑P4 — Selective log redaction (full user_id logged) | High | All 5 modules — `_user_ref` helper (PASS‑4 FIX‑H3) |
| G‑P5 — Encryption opt-out exists | High | `memory_vault:149–154` — warning + production lockout (PASS‑4 FIX‑H4) |
| G‑P7 — No per-user key rotation | High | `memory_vault` — new `rotate_user_key` (PASS‑4 FIX‑H5) |
| B1 — `_request_timeout` not thread-safe | High | `model_router:395–416` — `contextvars` (PASS‑4 FIX‑H6) |
| G‑P10 — `_KEY_CACHE` persistence | Medium | `memory_vault:228, 231–243` — TTL + invalidation (PASS‑4 FIX‑H7) |
| V1 — ESO dual source of truth | Medium | `intelligence_kernel:167–174` — single source (PASS‑4 FIX‑M4) |
| B10 — Provider response shape brittleness | Medium | `model_router:442–516` — semantic validation (PASS‑4 FIX‑M3) |

---

## Total runtime metrics

| Metric | Value |
|---|---|
| Total lines of code | 19,630 (5 modules) |
| Public functions | 186 routes + 16 kernel fns + 12 router fns + 12 state fns + 10 vault fns |
| Process-global mutable state | 16 globals |
| Locks | 3 explicit (1 thread-unsafe documented) |
| Direct cycles within 5 modules | 2 (both lazy-broken) |
| Runtime call cycles | 1 (via callable injection — `#G` runner) |
| Privacy gates | 8 |
| Privacy guarantees (explicit) | 25 |
| Privacy guarantees (implicit) | 9 |
| Privacy gaps | 11 |
| Single-funnel chokepoints | 8 |
| Cross-module invariants | 46 |
| Total invariants (PASS‑3A) | 154 (61 explicit + 39 implicit + 46 cross-module + 8 hard-by-absence) |
| Test coverage commitments (PASS‑5) | 231 tests across 19 test files |

---

## Non-goals

The runtime layer is **not**:

- a kernel for the intelligence layer (canonicalized azimuth /
  orchestrator / language / feedback engines are production-dormant).
- an LLM SDK consumer — pure stdlib `urllib.request` for all provider HTTP.
- a per-user isolator at the application level — isolation is
  cryptographic, not access-control.
- thread-safe in `_PROVIDER_HTTP_TIMEOUT` mutation (documented).
- multi-instance synchronised — founder default, macro counter, local
  handle cache all diverge between Cloud Run instances.
- a retry framework — failures degrade silently or propagate
  validation/lookup errors.
- a deterministic system in production response text — real provider
  calls introduce variance.

---

## Fiction removed

- **No `gateway.py`, `continuity.py`, `vault.py`, `session_manager.py`,
  or `request_pipeline.py`.** These are not real modules. Their
  concepts live inside `app.py` (gateway, session, error envelope,
  rate limit, mounted routers) and `memory_vault.py` (vault).
- **No intelligence-layer engine reachable from the runtime.**
  `azimuth_*`, `orchestrator_*`, `language_*`, `feedback_*`,
  `primitive_selection_engine`, `emotional_alignment_engine`,
  `fea_integration_engine`, `ingestion_engine` are all
  production-dormant.
- **No multi-key transactional writes** at the vault level — each
  `vault_put` is independent.
- **No key rotation primitive** — `vault_clear` doesn't invalidate the
  per-user salt.
- **No retry across providers** — `route_request` returns mock on any
  failure; no alternate provider attempt.

Only the modules, boundaries, funnels, gates, and invariants
described in this document are present in the runtime layer. The
verified surface is locked by **80+ test files** under `tests/` and
the PASS‑5 test plan adds **231 invariant-pinning tests** to harden
every documented guarantee.
