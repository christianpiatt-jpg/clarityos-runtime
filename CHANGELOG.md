# Changelog

All notable changes to the ClarityOS runtime are recorded here. The
format loosely follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For the canonical mapping of every fix to its locked invariant and
test, see [`docs/invariants.md`](docs/invariants.md).

---

## [v0.1.0] — First stabilised runtime

This is the first release of the ClarityOS runtime spine as a
versioned artifact. It locks the BD1–BD5 boundary contract, the
PASS-4 hardening fixes, the PASS-5 stabilization suite, and the
PASS-6 CI gates + invariant tests + release engineering. The full
union of the three CI gates passes 516 tests in 65 seconds.

### Architecture (PASS-1 → PASS-3 — pre-stabilisation history)

* Five-boundary runtime spine, with eager imports flowing strictly
  downward (BD1 → BD5) and only three documented lazy back-edges:

  | BD  | Module                    | Responsibility                                                                 |
  | --- | ------------------------- | ------------------------------------------------------------------------------ |
  | BD1 | `app.py`                  | HTTP routes, auth, CORS, error envelope, rate limit                            |
  | BD2 | `intelligence_kernel.py`  | ESO funnel, model funnel, audit funnel, S_ELINS QC                             |
  | BD3 | `model_router.py`         | Provider selection, outbound HTTP, mock fallback, vault-backed founder default |
  | BD4 | `operator_state.py`       | Per-user preferences, history, decay; sole storage dep is BD5                  |
  | BD5 | `memory_vault.py`         | Per-user encrypted KV (PBKDF2 + HMAC-CTR + HMAC-SHA256 MAC)                    |

* Cross-cutting facade `runtime_privacy.py` (pure-string redaction
  helpers — no imports, no side effects).
* Pre-existing feature surface across v40 (kernel), v44 (router), v46
  (vault), v39 (state), v31/v42 (billing), v47/v51 (threads +
  projects), and the v34–v38 ELINS pipeline.

### PASS-4 — Hardening fixes (now locked)

Every PASS-4 fix is backed by a regression test in `tests/test_fix_*.py`
plus an invariant test in `tests/test_runtime_inv_*.py`.

| Fix     | Module(s)                            | Summary                                                                                                                                                          |
| ------- | ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **V2**  | `model_router.py`, `memory_vault.py` | Founder default model is vault-backed under `__founder_global__` / `founder_global.default_model`; module-level slot is a write-through cache only.              |
| **H6**  | `model_router.py`                    | Provider HTTP timeout moved into `_PROVIDER_HTTP_TIMEOUT_VAR: ContextVar`; `_request_timeout` scopes the override to the calling asyncio task / thread. PEP 562 `__getattr__` preserves the legacy read API. |
| **H7**  | `memory_vault.py`                    | `_KEY_CACHE` entries become `(key_bytes, created_at)` 2-tuples with `_KEY_CACHE_TTL_SECONDS = 3600.0`; `_invalidate_key_cache_for_user` added.                   |
| **B2**  | `intelligence_kernel.py`             | `_macro_seq_lock` pre-allocated at module import — closes the lazy-init TOCTOU window.                                                                          |
| **P1**  | `app.py`                             | `/billing/intent/confirm` response projected to a safe field allow-list (no `client_secret`, no raw provider `metadata`); `/me/billing` adds the `failed → "failed"` mapping. |
| **P2**  | `operator_state.py`                  | `migrate_operator_state_to_vault` now runs every legacy history entry through `_strip_forbidden` and caps at `HISTORY_MAX = 200` (newest kept).                  |
| **P3**  | `memory_vault.py`                    | `CLARITYOS_VAULT_PLAINTEXT` enablement tightened to the literal `"true"` (case-insensitive, whitespace-trimmed); legacy `"1"` / `"yes"` no longer enable. One high-severity warning per process via `_PLAINTEXT_WARNING_EMITTED`. |
| **P5**  | new `runtime_privacy.py` + 5 modules | Centralised log-redaction helpers (`user_ref`, `session_ref`, `prompt_preview`, `topic_trim`, `event_ref`). 27 logger call sites refactored across the spine.   |
| **C1**  | `memory_vault.py`                    | `_secret()` raises `RuntimeError` on missing / empty / whitespace `CLARITYOS_VAULT_SECRET` — no default-key fallback in any environment.                         |

### PASS-5 — Stabilization (concurrency, determinism, privacy)

`tests/test_*_runtime.py` adds 50- to 200-thread stress tests for every
concurrency-sensitive surface, plus a 20-client HTTP-level burst that
validates the full vertical (BD1 → BD5) under load:

* **D1** — Multi-instance founder-default consistency (process A
  writes → process B with fresh module globals reads the same value
  from the vault).
* **D2** — `_PROVIDER_HTTP_TIMEOUT_VAR` per-context isolation under
  50 concurrent threads, each in its own `_request_timeout` block.
* **D3** — `operator_state._next_seq` returns a contiguous unique set
  under 50-thread contention; distinct prefixes are independent.
* **D4** — 50 concurrent `run_macro_ELINS` invocations produce 50
  unique `macro_<ts_ms>_<seq>` ids.
* **D5** — `_derive_key` returns deterministic PBKDF2 bytes under 50-
  thread cache-TTL races; cache ends with a single coherent entry.
* **D6** — 20 concurrent HTTP clients each run login → /me → /elins/preview
  → /me with zero raw user/session leaks across the five FIX-P5
  loggers, zero 500s, and consistent `last_model_used` per user.

### PASS-6 — Operationalization

#### Phase A — CI gates + invariant tests

* `pytest.ini` defines three CI markers: `runtime_spine`,
  `privacy_surface`, `determinism_surface`.
* `tests/conftest.py::pytest_collection_modifyitems` auto-applies the
  markers based on file name — no per-function decorators.
* Five invariant test files in `tests/test_runtime_inv_*.py`:
  * BD1 (`test_runtime_inv_http.py`) — 22 tests: log-redaction grep
    across all 5 FIX-P5 modules; `/billing/intent/confirm` field
    projection; `/me/billing` 5-cell mapping; `_session_ref` /
    `_user_ref` byte-equivalence with `runtime_privacy`.
  * BD2 (`test_runtime_inv_kernel.py`) — 13 tests: macro-seq lock
    pre-allocation + identity stability; 1000-id determinism burst;
    `model_id` surfaces on all 5 `run_*`; ESO failure degrades
    gracefully; source-grep against hardcoded model ids.
  * BD3 (`test_runtime_inv_router.py`) — 21 tests: 8-cell selection
    precedence matrix; vault-backed founder default; ContextVar
    timeout default + nesting; mock byte-equivalence with
    `runtime_privacy.prompt_preview`; alias resolution rules.
  * BD4 (`test_runtime_inv_state.py`) — 13 tests: monotonic `_next_seq`;
    `HISTORY_MAX = 200` on live + migration; `_strip_forbidden` removes
    exactly 4 keys; `_trim_topic` delegation; source-grep guarding
    persistence dep to `memory_vault` only.
  * BD5 (`test_runtime_inv_vault.py`) — 24 tests: cache TTL shape;
    PBKDF2 determinism; invalidation contract; plaintext parser
    tightening (parametrized 6 legacy values + 4 explicit); one-shot
    warning; frozen `ALLOWED_NAMESPACES` registry; encrypt/decrypt
    round-trip + MAC tamper-rejection; `_secret()` raises on missing
    env.
* `tests/test_module_load_guards.py` — 12 tests asserting fresh-import
  state, founder-default reload from vault, plaintext does NOT
  silently activate after a reset.

#### Phase B — Deployment-mode validation

* `tests/test_deployment_runtime.py` — 35 tests: missing /
  empty / whitespace `CLARITYOS_VAULT_SECRET` blocks both `vault_init`
  and `vault_put`; explicit `"true"` enables plaintext + exactly one
  warning over 20 calls; 12 non-`"true"` legacy values do not enable;
  fresh-import globals match documented defaults; default startup
  emits zero spine warnings; plaintext-enabled startup emits exactly
  the one PLAINTEXT warning and nothing else.
* Extended `test_memory_vault_runtime.py` (B5 — 5 tests): TTL across
  simulated hours, no cross-instance contamination, namespace
  allow-list enforced on write AND read.
* Extended `test_model_router_runtime.py` (B2 — 5 tests): founder
  default + `select_model` precedence + alias resolution all stable
  across simulated instance boundaries; constants unchanged across
  resets.
* Extended `test_operator_state_runtime.py` (B2 — 4 tests): every
  persistent field byte-identical after restart; seq counter
  independence; `_strip_forbidden` still applies; `HISTORY_MAX` holds
  across the boundary.
* Extended `test_app_runtime_e2e.py` (B4 + B6 — 5 tests): mixed-
  workload logging-surface scan; no plaintext warning under default
  env; no billing secrets in any captured log; full lifecycle across
  simulated instance boundary preserves `last_model_used` and founder
  default; user-preference-driven selection survives the restart.

#### Phase C — Repo + CI scaffolding

* `.github/workflows/ci.yml` — Four-job CI gate (union + per-suite)
  with coverage upload and JUnit artifacts.
* `.github/workflows/deploy.yml` — Scaffold only; activation
  documented under `TODO(PASS-7)` block.
* `.env.example` — Complete `CLARITYOS_*` env-var template (37
  variables, grouped by purpose).
* `README.md` — Runtime architecture + invariants + how-to-run.
* `docs/invariants.md` — Full invariant reference + fix-to-test
  crosswalk.
* `docs/boundaries.md` — Per-boundary contract + import-edge diagram
  + the three lazy back-edges + mutable-module-state table.
* `docs/deployment.md` — Env vars + first-run + Cloud Run shape +
  multi-instance behaviour + PASS-7 activation plan.
* `scripts/run_ci_gates.sh` — Local CI-gate driver.

#### Phase D — Release finalization

* `VERSION` — `v0.1.0`.
* `CHANGELOG.md` — this file.
* `.github/workflows/release.yml` — tag-triggered (`v*`) workflow:
  full CI-gate run + release-notes generation + GitHub Release
  publish. Container build is placeholder.
* `docs/release_notes/v0.1.0.md` — release-note source consumed by
  the release workflow.
* `tests/test_release_integrity.py` — D6 release-integrity tests
  (semver `VERSION`, `CHANGELOG.md` carries an entry for the current
  version, `release.yml` references `VERSION` correctly, the three CI
  markers each resolve to a positive test count, full gate union is
  consistent).

### Test posture at v0.1.0

| Suite                 | Test count | Runtime  |
| --------------------- | ---------- | -------- |
| `runtime_spine`       | 516        | ~65s CI  |
| `privacy_surface`     | 218        | ~25s CI  |
| `determinism_surface` | 235        | ~30s CI  |
| Union (the CI gate)   | 516        | ~65s CI  |

Zero failures, zero unexpected skips, zero runtime code changes
introduced after Phase A. Every PASS-4 fix has at least one
regression test, one invariant test, and one stability test in the
runtime suite.

### Known limitations / not in scope for v0.1.0

* The `.github/workflows/deploy.yml` scaffold does NOT build a real
  container image or push to a registry. PASS-7 activates that.
* Real provider HTTP calls (OpenAI, Anthropic, Gemini) require env
  keys at runtime; without them the mock-fallback contract applies
  (this is by design — see BD3 in `docs/boundaries.md`).
* Firestore-backed integration tests are not run in CI (the mock
  backend is sufficient for the spine invariants; production deploys
  exercise Firestore directly).

[v0.1.0]: https://github.com/REPLACE_ME/clarityos/releases/tag/v0.1.0
