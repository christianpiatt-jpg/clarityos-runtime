# ClarityOS Runtime — Locked Invariants

> PASS-6 Phase A reference. Each invariant below is backed by at least
> one explicit `test_runtime_inv_*.py` assertion plus one or more
> stability tests in the Phase D / Phase B runtime suites.
>
> The CI gate in `.github/workflows/ci.yml` blocks any change that
> regresses an invariant from this list.

The columns map to:
* **ID** — stable invariant identifier referenced from runtime source
  comments and test docstrings.
* **Modules** — the BD this invariant lives under.
* **Test(s)** — primary assertion location; secondary stability tests
  appear in the per-boundary `test_*_runtime.py` files.

---

## BD3 — `model_router.py`

| ID     | Invariant | Modules | Tests |
| ------ | --------- | ------- | ----- |
| INV-R1 | `select_model` precedence is `override > founder default > operator_state.preferred_model > TASK_DEFAULTS[task]`. `"auto"` is a sentinel that falls through. | BD3, BD4 (lazy) | `test_runtime_inv_router.py::TestINV_R1_SelectModelPrecedence` (parametrized 8-cell matrix); `test_v44_model_router.py::test_select_model_*` |
| INV-R2 | Founder default model is vault-backed under the synthetic user `__founder_global__` and key `founder_global.default_model`. The module-level slot is a write-through cache, not the source of truth. | BD3 ↔ BD5 | `test_runtime_inv_router.py::TestINV_R2_FounderDefaultVaultBacked`; `test_founder_default_vault_persistence.py` |
| INV-R3 | Provider HTTP timeout is per-context via `_PROVIDER_HTTP_TIMEOUT_VAR: ContextVar`. `_request_timeout(s)` scopes the override to the calling asyncio task or thread; LIFO restoration via `ContextVar.reset(token)`. | BD3 | `test_runtime_inv_router.py::TestINV_R3_ContextVarTimeout`; `test_fix_h6_provider_http_timeout_contextvar.py`; `test_model_router_runtime.py::TestD2*` |
| INV-R4 | `_mock_result` prompt preview uses `runtime_privacy.prompt_preview` (60-char cap, no ellipsis). Byte-stable for the same prompt. | BD3, runtime_privacy | `test_runtime_inv_router.py::TestINV_R4_MockResultUsesPromptPreview`; `test_fix_p5_runtime_privacy.py::TestModelRouterMockUsesPromptPreview` |
| INV-R5 | `resolve_model_alias` coerces friendly names case-insensitively to canonical `SUPPORTED_MODELS` ids; canonical ids are case-sensitive; unknown returns `None`. | BD3 | `test_runtime_inv_router.py::TestINV_R5_ResolveModelAlias` |
| INV-R6 | `_PROVIDER_HTTP_TIMEOUT` is readable as a module attribute via PEP 562 `__getattr__`; the read returns the current `ContextVar.get()`. | BD3 | `test_runtime_inv_router.py::TestINV_R6_LegacyAttributeShim` |

## BD2 — `intelligence_kernel.py`

| ID     | Invariant | Modules | Tests |
| ------ | --------- | ------- | ----- |
| INV-K1 | `_macro_seq_lock` is pre-allocated at module import. Single `threading.Lock` instance for the process lifetime; `_reset_for_tests` preserves identity. | BD2 | `test_runtime_inv_kernel.py::TestINV_K1_MacroSeqLockPreallocated`; `test_b2_macro_seq_lock_preallocated.py`; `test_intelligence_kernel_runtime.py::TestD4*` |
| INV-K2 | Macro `run_id` format is `f"macro_{int(now*1000)}_{seq}"`. Under contention, seq values form a strictly increasing contiguous set. | BD2 | `test_runtime_inv_kernel.py::TestINV_K2_MacroRunIdFormat` (1000-id determinism burst); `test_intelligence_kernel_runtime.py::test_d4_run_id_format_under_concurrency` |
| INV-K3 | Every `run_*` path surfaces `model_id` in its result AND in `kernel_logging.log_kernel_run.meta`. | BD2 | `test_runtime_inv_kernel.py::TestINV_K3_ModelIdSurfaced` (run_c / run_G / run_ELINS / run_regional / run_macro); `test_v44_model_router.py::test_kernel_*` |
| INV-K4 | ESO oracle failures degrade gracefully. `_maybe_fetch_eso` returns `None` on exception; the run completes with `ok=True`. | BD2, perplexity_oracle | `test_runtime_inv_kernel.py::TestINV_K4_EsoFailureGracefulDegradation` |
| INV-K5 | Kernel run paths route model selection through `model_router.select_model` (or the local `_resolve_model` wrapper). No hardcoded canonical model ids in run-path code. | BD2 → BD3 | `test_runtime_inv_kernel.py::TestINV_K5_ModelSelectionRoutedThroughRouter` (source-grep) |

## BD4 — `operator_state.py`

| ID     | Invariant | Modules | Tests |
| ------ | --------- | ------- | ----- |
| INV-S1 | `_next_seq(prefix)` is strictly monotonic per prefix under `_SEQ_LOCK`. 50 concurrent callers see `{1..50}` exactly. Distinct prefixes have independent counters. | BD4 | `test_runtime_inv_state.py::TestINV_S1_NextSeqMonotonic`; `test_operator_state_runtime.py::TestD3*` |
| INV-S2 | `HISTORY_MAX = 200` enforced on live writes (via `_prune_history`) and on migration (via the FIX-P2 sort + slice in `migrate_operator_state_to_vault`). | BD4 → BD5 | `test_runtime_inv_state.py::TestINV_S2_HistoryMaxCap`; `test_fix_p2_migrate_strip_forbidden.py::TestHistoryMaxCap`; `test_operator_state_runtime.py::test_b2_history_max_holds_across_instance_boundary` |
| INV-S3 | `_strip_forbidden` removes exactly `{"text", "scenario_text", "input_text", "raw_text"}`. Returns an independent dict; idempotent on None/empty. | BD4 | `test_runtime_inv_state.py::TestINV_S3_StripForbidden`; `test_fix_p2_migrate_strip_forbidden.py::TestForbiddenStripping` |
| INV-S4 | `_trim_topic` delegates byte-for-byte to `runtime_privacy.topic_trim`. | BD4, runtime_privacy | `test_runtime_inv_state.py::TestINV_S4_TrimTopicDelegation`; `test_fix_p5_runtime_privacy.py::TestOperatorStateTopicTrimDelegates` |
| INV-S5 | `operator_state.py` imports `memory_vault` for persistence and nothing else. Source-grep gates any new persistence dep. | BD4 → BD5 | `test_runtime_inv_state.py::TestINV_S5_PersistenceDependency` |

## BD5 — `memory_vault.py`

| ID     | Invariant | Modules | Tests |
| ------ | --------- | ------- | ----- |
| INV-V1 | `_KEY_CACHE` entries are `(key_bytes, created_at_timestamp)` tuples; cache lifetime is bounded by `_KEY_CACHE_TTL_SECONDS = 3600.0`. | BD5 | `test_runtime_inv_vault.py::TestINV_V1_KeyCacheShapeAndTTL`; `test_fix_h7_key_cache_ttl.py`; `test_memory_vault_runtime.py::TestD5*` |
| INV-V2 | `_derive_key` returns `PBKDF2-HMAC-SHA256(secret, "clarityos:" + user_id, _pbkdf2_iters(), 32)` — same bytes on every call regardless of cache state. | BD5 | `test_runtime_inv_vault.py::TestINV_V2_DeriveKeyDeterminism`; `test_memory_vault_runtime.py::TestD5KeyCacheTTLUnderConcurrency` |
| INV-V3 | `_invalidate_key_cache_for_user(user_id)` is idempotent, per-user, and safe to call concurrently with `_derive_key` under `_LOCK`. | BD5 | `test_runtime_inv_vault.py::TestINV_V3_InvalidationContract`; `test_memory_vault_runtime.py::test_d5_invalidation_during_concurrent_reads_is_safe` |
| INV-V4 | `CLARITYOS_VAULT_PLAINTEXT` enables plaintext mode only on the explicit string `"true"` (case-insensitive, whitespace-trimmed). Legacy spellings `"1"` / `"yes"` no longer enable. | BD5 | `test_runtime_inv_vault.py::TestINV_V4_PlaintextEnablement`; `test_fix_p3_plaintext_vault_guardrails.py`; `test_deployment_runtime.py::TestB1PlaintextEnvVarMatrix` |
| INV-V5 | Plaintext mode emits exactly one WARNING per process via the `_PLAINTEXT_WARNING_EMITTED` one-shot flag. Message names the env var, says encryption is disabled, pins to dev-only scope. | BD5 | `test_runtime_inv_vault.py::TestINV_V5_PlaintextOneShotWarning`; `test_fix_p3_plaintext_vault_guardrails.py::TestOneTimeWarning` |
| INV-V6 | `_validate_key` rejects keys whose leading namespace is not in `ALLOWED_NAMESPACES` (frozen 12-entry registry: `operator_state`, `elins`, `g_runs`, `preferences`, `local_model`, `notes`, `embeddings`, `threads`, `projects`, `regression_chains`, `regression_packets`, `founder_global`). | BD5 | `test_runtime_inv_vault.py::TestINV_V6_NamespaceAllowList`; `test_deployment_runtime.py::TestB1InvalidNamespaceAndKey` |
| INV-V7 | `vault_get` / `vault_put` round-trip is byte-stable for matching `(user_id, key, secret)`. Scheme byte `0x01` carries MAC; scheme `0x00` (plaintext) skips MAC. MAC mismatch raises. | BD5 | `test_runtime_inv_vault.py::TestINV_V7_RoundTripContract`; `test_memory_vault_runtime.py::test_b5_encrypted_round_trip_under_deployment_env` |
| INV-V8 | `_secret()` raises `RuntimeError` if `CLARITYOS_VAULT_SECRET` is unset, empty, or whitespace-only. No default-secret fallback in any environment. | BD5 | `test_runtime_inv_vault.py::TestINV_V8_SecretRequired`; `test_deployment_runtime.py::TestB1MissingVaultSecret` |

## BD1 — `app.py`

| ID     | Invariant | Modules | Tests |
| ------ | --------- | ------- | ----- |
| INV-H1 | No FIX-P5-scoped logger (`clarityos`, `clarityos.intelligence_kernel`, `clarityos.model_router`, `clarityos.operator_state`, `clarityos.memory_vault`) emits a record containing a raw `user_id` substring. | BD1, BD2, BD3, BD4, BD5 | `test_runtime_inv_http.py::TestINV_H1_NoRawUserIdInLoggers` (5-module source grep); `test_fix_p5_runtime_privacy.py::TestNoFullUserInLogs`; `test_app_runtime_e2e.py::TestD6*` |
| INV-H2 | Same as INV-H1 but for `session_id`. | BD1, BD2, BD3 | `test_runtime_inv_http.py::TestINV_H2_NoRawSessionIdInLoggers`; `test_app_runtime_e2e.py::TestB4LoggingSurfaceUnderDeployment` |
| INV-H3 | `POST /billing/intent/confirm` returns only the safe field projection: `intent_id`, `status`, `amount`, `kind`, `mode`, `description`, `created_ts`, `confirmed_ts`, `failed_ts`, `failure_code`. `client_secret` and raw provider `metadata` are never returned. | BD1, billing_intents | `test_runtime_inv_http.py::TestINV_H3_BillingConfirmFieldProjection`; `test_fix_p1_billing_surface_hardening.py::TestConfirmRedaction` |
| INV-H4 | `GET /me/billing` maps per the FIX-P1 table: `active → "active"`, `past_due → "past_due"`, `grace_period → "grace_period"`, `cancelled → "canceled"`, `failed → "failed"`, else → `"none"`. | BD1, users_store, billing_config | `test_runtime_inv_http.py::TestINV_H4_MeBillingFailedMapping` (parametrized × 5); `test_fix_p1_billing_surface_hardening.py::TestMeBillingStatusMapping` |
| INV-H5 | Local helpers `_session_ref` / `_user_ref` in `app.py` are byte-identical aliases for `runtime_privacy.session_ref` / `user_ref`. | BD1, runtime_privacy | `test_runtime_inv_http.py::TestINV_H5_LocalHelpersAreAliases` (parametrized × 6 inputs each) |

## Cross-cutting — `runtime_privacy.py`

| ID     | Invariant | Tests |
| ------ | --------- | ----- |
| INV-X1 | All five FIX-P5-scoped modules import `runtime_privacy` at module load. | `test_fix_p5_runtime_privacy.py::TestModulesImportRuntimePrivacy` (parametrized × 5) |
| INV-X2 | `session_ref` / `user_ref` return `"<none>"` for `None` / empty / non-string; otherwise `value[:N] + "..."`. | `test_fix_p5_runtime_privacy.py::TestSessionRef`, `TestUserRef` |
| INV-X3 | `prompt_preview` caps at `MOCK_PROMPT_PREVIEW_LEN = 60` and never appends an ellipsis (preserves v44 mock byte contract). | `test_fix_p5_runtime_privacy.py::TestPromptPreview` |
| INV-X4 | `event_ref` caps at `EVENT_ID_SHORT_LEN = 24` and appends `"..."` only when truncation occurred. | `test_fix_p5_runtime_privacy.py::TestEventRef` |
| INV-X5 | `runtime_privacy` is pure-string — no `import logging`, no `logger.*` calls, no side effects. | `test_fix_p5_runtime_privacy.py::TestPurity` |

---

## Fix → Invariant → Test crosswalk

| PASS-4 fix | Invariants strengthened | Primary regression tests |
| ---------- | ----------------------- | ------------------------ |
| **V2** — vault-backed founder default | INV-R2 | `test_founder_default_vault_persistence.py`; `test_model_router_runtime.py::TestD1*`; `test_app_runtime_e2e.py::TestB6*` |
| **FIX-H6** — HTTP timeout ContextVar | INV-R3, INV-R6 | `test_fix_h6_provider_http_timeout_contextvar.py`; `test_model_router_runtime.py::TestD2*` |
| **B2** — `_macro_seq_lock` pre-allocation | INV-K1, INV-K2 | `test_b2_macro_seq_lock_preallocated.py`; `test_intelligence_kernel_runtime.py::TestD4*` |
| **FIX-H7** — key cache TTL + invalidation | INV-V1, INV-V2, INV-V3 | `test_fix_h7_key_cache_ttl.py`; `test_memory_vault_runtime.py::TestD5*` |
| **FIX-P1** — billing surface | INV-H3, INV-H4 | `test_fix_p1_billing_surface_hardening.py`; `test_runtime_inv_http.py::TestINV_H3*`, `TestINV_H4*` |
| **FIX-P2** — migration scrub + cap | INV-S2, INV-S3 | `test_fix_p2_migrate_strip_forbidden.py`; `test_operator_state_runtime.py::TestB2*` |
| **FIX-P3** — plaintext guardrail | INV-V4, INV-V5 | `test_fix_p3_plaintext_vault_guardrails.py`; `test_deployment_runtime.py::TestB1PlaintextEnvVarMatrix` |
| **FIX-P5** — runtime_privacy | INV-H1, INV-H2, INV-H5, INV-X1–X5 | `test_fix_p5_runtime_privacy.py`; `test_runtime_inv_http.py`; `test_app_runtime_e2e.py::TestD6*`, `TestB4*` |
