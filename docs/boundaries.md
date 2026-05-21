# ClarityOS Runtime — Boundaries

> PASS-6 Phase C reference. This document is the canonical contract
> for the five runtime boundaries and their import edges. Any change
> that violates one of these rules must be reviewed at the
> architectural level — the CI suite assertions
> (`test_runtime_inv_*.py`, `test_module_load_guards.py`) gate the
> mechanical violations.

---

## Boundary inventory

| ID  | Module                   | Responsibility                                                                                                                  | Import policy                                                                                              |
| --- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| BD1 | `app.py`                 | Routes, auth, CORS, error envelope, rate limit, bcrypt. Injects the `#G` runner into the kernel.                                | Imports BD2 directly. **Never** imported by any other runtime module.                                       |
| BD2 | `intelligence_kernel.py` | ESO funnel, model funnel, audit funnel, S_ELINS QC, topic-label construction.                                                   | Eagerly imports BD3, BD4, BD5, `kernel_logging`, `perplexity_oracle`, `runtime_privacy`. **Never** imports BD1. |
| BD3 | `model_router.py`        | Provider selection, outbound HTTP, mock fallback, founder default (vault-backed).                                               | Eagerly imports `runtime_http_config`, `runtime_privacy`. **Lazy-imports** BD4 (`operator_state`) and BD2 (`intelligence_kernel`). Lazy-imports `local_model_runtime`. |
| BD4 | `operator_state.py`      | Per-user preferences, history, decay, continuity. Records every persistence write through BD5.                                  | Eagerly imports BD5 (`memory_vault`) + `runtime_privacy`. **Lazy-imports** BD3 (for `model_router.is_valid_model` validation only). |
| BD5 | `memory_vault.py`        | Per-user encrypted KV. PBKDF2 master key derivation, HMAC-CTR + HMAC-SHA256 MAC. Namespace allow-list.                          | Eagerly imports `runtime_privacy` only. **Zero** internal runtime imports — the deepest leaf.              |

The cross-cutting facade:

| Module               | Responsibility                                                                | Import policy                                                                          |
| -------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `runtime_privacy.py` | Pure-string redaction helpers (`user_ref`, `session_ref`, `prompt_preview`, `topic_trim`, `event_ref`). | **Zero** runtime imports, **zero** `import logging`. Pure stdlib only. (INV-X5) |

---

## Import-edge contract

```
 BD1  app.py
   │ eager
   ▼
 BD2  intelligence_kernel.py
   │ eager   ⇆  lazy back-edge ─────── model_router.call_regression_first
   ▼                                    (BD3 → BD2)
 BD3  model_router.py
   │ eager
   ▼
 (runtime_http_config + runtime_privacy)
   │
 BD3  ⇆  BD4  (symmetric lazy)
   │       │
   │       ▼
   │      BD4  operator_state.py
   │       │ eager
   │       ▼
 BD5  memory_vault.py
   │ eager
   ▼
 runtime_privacy.py  (cross-cutting, no boundary)
```

### Rules

1. **Eager imports flow downward.** Every eager top-level import in
   the runtime spine moves from a higher BD number to a lower one
   (BD1 → BD2 → BD3 → BD4 → BD5), with two documented exceptions
   below.

2. **No upward eager imports.** A lower-BD module must never import a
   higher-BD module at top level. The two existing back-edges (BD3 →
   BD4 and BD3 → BD2) are both **lazy** (inside-function `import`
   statements) so the module-load graph remains acyclic at import
   time.

3. **BD5 has zero internal imports.** `memory_vault.py` imports only
   stdlib plus `runtime_privacy`. This keeps the deepest leaf
   testable in isolation and immune to dependency-cycle bugs in the
   rest of the spine.

4. **`runtime_privacy` is pure.** It does not log, does not call any
   other runtime module, and lives outside the BD hierarchy. Every
   FIX-P5-scoped module imports it (INV-X1).

### Documented lazy back-edges

| Edge         | Location                                                | Reason                                                                                                              |
| ------------ | ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| BD3 → BD4    | `model_router.select_model:297` — `import operator_state` | `select_model` needs `operator_state.get_operator_state` to read the user's `preferred_model`. Lazy because BD4 also imports BD3. |
| BD4 → BD3    | `operator_state.set_preferred_model:351` — `import model_router` | Validates a user-supplied model_id via `model_router.is_valid_model`. Lazy for the symmetric reason.                |
| BD3 → BD2    | `model_router.call_regression_first:942` — `import intelligence_kernel` | The v79 task helper delegates to `intelligence_kernel.run_regression_first`. Lazy because BD2 eagerly imports BD3. |

These three edges are the **only** sanctioned back-edges. New code
that needs an upward dependency must follow the same lazy-import
pattern, and the back-edge must be added to this table.

---

## What lives at each boundary

### BD1 — `app.py`

* All FastAPI route handlers.
* Auth (`/register`, `/login`, `/logout`), session middleware.
* CORS, error envelope (`error_response`), rate-limit dispatch via
  `v29_hardening`.
* `_session_ref` / `_user_ref` aliases over `runtime_privacy.session_ref`
  / `user_ref` (INV-H5).
* Billing route handlers (`/billing/intent`, `/billing/intent/confirm`,
  `/billing/history`, `/billing/webhook`, `/me/billing`,
  `/founder/billing/status`).
* Founder routes (`/founder/*`).
* Surface-specific endpoints (`/elins/*`, `/me`, `/me/*`,
  `/me/operator_state/*`, `/me/vault/*`, `/me/threads/*`, etc.).

### BD2 — `intelligence_kernel.py`

* `run_c` / `run_G` / `run_ELINS` / `run_regional_ELINS` /
  `run_macro_ELINS` / `run_thread_message` / `run_regression_first`.
* `_resolve_model` — single resolution funnel used by every run path.
* `_maybe_fetch_eso` — single ESO ingest funnel (sanitises via
  `perplexity_oracle.sanitize_eso`).
* `_run_s_elins_qc` — single S_ELINS QC funnel.
* `_macro_seq` / `_macro_seq_lock` / `_next_macro_seq` /
  `_make_macro_run_id` (INV-K1, INV-K2).
* `kernel_status` / `kernel_view_for_user` — aggregate snapshot.

### BD3 — `model_router.py`

* `MODEL_REGISTRY` / `SUPPORTED_MODELS` / `TASK_DEFAULTS` (immutable
  constants under PASS-6 — see INV-R5).
* `select_model` — precedence resolution (INV-R1).
* `route_request` + per-provider handlers (`_call_openai`,
  `_call_anthropic`, `_call_gemini`, `_call_xai`, `_call_local`).
* `_PROVIDER_HTTP_TIMEOUT_VAR: ContextVar` + `_request_timeout`
  context manager (INV-R3).
* `_FOUNDER_GLOBAL_USER_ID` / `_FOUNDER_DEFAULT_KEY` + the cache
  loaded flag (INV-R2).
* `resolve_model_alias` (INV-R5).
* `_mock_result` — deterministic mock payload built from
  `runtime_privacy.prompt_preview` (INV-R4).

### BD4 — `operator_state.py`

* `get_operator_state` / `update_operator_state` — read + merge.
* `set_preferred_model` / `record_model_used` /
  `bump_local_model_usage` / `set_external_signal_mode` —
  field-specific helpers.
* `record_elins_interaction` / `record_g_run` — append history
  entries; applies `_strip_forbidden` + `_prune_history` per write.
* `migrate_operator_state_to_vault` — legacy snapshot import; also
  applies `_strip_forbidden` + cap at `HISTORY_MAX` (INV-S2, INV-S3).
* `_next_seq` under `_SEQ_LOCK` — monotonic per-prefix counter
  (INV-S1).
* `_trim_topic` — thin delegate to `runtime_privacy.topic_trim`
  (INV-S4).
* `continuity_section` / `continuity_context` / `related_runs` — read
  helpers for the dashboard + ELINS inspector.

### BD5 — `memory_vault.py`

* `vault_init` / `vault_put` / `vault_get` / `vault_list` /
  `vault_delete` / `vault_clear` — public KV surface.
* `vault_keys_for_user` / `vault_count_for_user` / `vault_known_users`
  / `vault_status` — read-side helpers for kernel / founder console.
* `ALLOWED_NAMESPACES` (INV-V6) + `_validate_key` —  the namespace
  allow-list gate.
* `_encrypt_value` / `_decrypt_value` / `_ctr_keystream` — the
  HMAC-CTR + HMAC-SHA256 envelope (INV-V7).
* `_derive_key` + `_KEY_CACHE` + `_KEY_CACHE_TTL_SECONDS` +
  `_invalidate_key_cache_for_user` (INV-V1, INV-V2, INV-V3).
* `_is_encrypted` + `_PLAINTEXT_WARNING_EMITTED` — the FIX-P3 one-shot
  warning surface (INV-V4, INV-V5).
* `_secret` — startup contract: missing / empty / whitespace raises
  `RuntimeError` (INV-V8).
* Four backends: `mock`, `fs`, `sqlite`, `firestore`.

### `runtime_privacy.py`

* Five pure helpers: `session_ref`, `user_ref`, `prompt_preview`,
  `topic_trim`, `event_ref`.
* Five module-level constants: `SESSION_REF_LEN=8`, `USER_REF_LEN=8`,
  `MOCK_PROMPT_PREVIEW_LEN=60`, `TOPIC_MAX_LEN=200`,
  `EVENT_ID_SHORT_LEN=24`.

---

## Mutable module-level state (per process)

The runtime is single-process per Cloud Run instance. The module-level
state below is intentionally per-process — its lifecycle is bounded by
import, `_reset_for_tests`, or explicit invalidation:

| Module          | Symbol                         | Reset hook                          | Multi-instance contract                                                                                              |
| --------------- | ------------------------------ | ----------------------------------- | -------------------------------------------------------------------------------------------------------------------- |
| model_router    | `_founder_default_model`       | `_reset_for_tests`                  | Write-through cache; source of truth is `memory_vault.vault_get(__founder_global__, founder_global.default_model)`. |
| model_router    | `_founder_default_loaded`      | `_reset_for_tests`                  | Lazy-load flag; flips to True on first read.                                                                          |
| model_router    | `_LOCAL_HANDLE_CACHE`          | `_reset_for_tests`                  | Process-local. New instance re-loads via `local_model_runtime.load_local_model`.                                     |
| model_router    | `_PROVIDER_HTTP_TIMEOUT_VAR`   | none (ContextVar with default)      | Per-context isolation. Default is `runtime_http_config.DEFAULT_CALL_TIMEOUT`.                                        |
| intelligence_kernel | `_macro_seq` / `_macro_seq_lock` | `_reset_for_tests` (counter only) | Lock pre-allocated; counter is process-local; macro_run_id ties to wall-clock + counter so cross-instance collisions need same-ms + same-seq. |
| operator_state  | `_HISTORY_SEQ`                 | `_reset_memory_for_tests`           | Process-local counter for unique vault keys. Vault data itself is shared.                                            |
| memory_vault    | `_KEY_CACHE`                   | `_reset_for_tests`                  | Process-local PBKDF2 cache. TTL = 3600s. Source of truth is the master secret + user_id.                             |
| memory_vault    | `_PLAINTEXT_WARNING_EMITTED`   | `_reset_for_tests`                  | One-shot flag per process. Re-arms on `_reset_for_tests` so the test harness can verify the contract per case.       |
| memory_vault    | `_MEM_STORE`                   | `_reset_for_tests`                  | Mock-backend persistence. In production, the persistent store is fs / sqlite / Firestore — those survive instance restarts. |

All of the above are documented as "per-process" in
[`docs/runtime_architecture.md`](runtime_architecture.md). The
multi-instance B2 tests in `test_model_router_runtime.py`,
`test_operator_state_runtime.py`, `test_memory_vault_runtime.py`, and
`test_app_runtime_e2e.py` lock the per-instance behavior under
simulated cold starts.
