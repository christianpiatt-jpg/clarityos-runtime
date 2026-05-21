# Runtime Execution Layer

## Purpose

The Runtime Execution Layer is the operator-session execution stack — the
chain that accepts an operator turn, classifies its intent, evaluates ELINS,
computes the next runtime decision, routes any model call via the provider
bridge, persists the session and vault state, and returns the next operator
view. It is a pure-functional core (runtime kernel + dispatcher + session
runner) wrapped in a stateless HTTP surface and a persistence layer. It is
**not** the Intelligence Kernel, not an autonomous loop, not continuity
reentry — those are separate subsystems.

## Implementation location

Eight repo-root modules form the cluster, in execution order:

- `runtime_http.py` (Unit 41) — the FastAPI router; two stateless operator
  endpoints. Imports only `session_loop`, `runtime_persistence`, and
  `runtime_providers` (test-enforced).
- `session_loop.py` (Units 40 + 43) — the session façade. `start_session` /
  `step_session` with persistence integration (v61) and the v64 lost-update
  fix. The only bounded-non-determinism source.
- `operator_session_runner.py` (Unit 39) — one-step orchestrator that composes
  the dispatcher + `model_router.route_model_request` into a single result.
- `runtime_dispatcher.py` (Unit 36) — sits above the kernel. Rule-based intent
  → engine routing (`diagnostic` → `local`, `plan` → `claude`, `query` →
  `copilot`, `action` → `gemini`, fallback `copilot`), calls
  `run_runtime_step`, and maps the runtime decision to UI severity (`allow` →
  `info`, `warn` → `warning`, `block` → `critical`). Pure deterministic.
- `runtime_kernel.py` (Unit 35) — the pure-functional step kernel. Validates
  inputs, runs the ELINS session integrator, applies the runtime actions,
  merges vault state, and returns a locked-shape result.
- `runtime_persistence.py` (Unit 42) — vault and session persistence;
  in-memory by default with opt-in JSON-file backing.
- `runtime_providers.py` (Unit 65) — operator-vocabulary bridge over
  `model_router` (`get_available_providers`, `call_model`).
- `runtime_http_config.py` (Unit 71) — leaf timeout / retry config consumed
  by `model_router` and `runtime_http`; no back-imports (test-enforced).

The model dispatch itself lives in `model_router.route_model_request` (Unit
38, see `docs/model_router.md`) — the runtime layer calls but does not own
it.

## Data model

- **`operator_intent`** — `{session_id, operator_id, timestamp, intent_type
  (one of `query` / `action` / `plan` / `diagnostic`), payload}`. `payload`
  must include `elins_inputs` (Unit 27 / Unit 29 outputs) and may include a
  `runtime_mode` override and a `preferred_model_id` (v64 / Unit 65).
- **`session_context`** — `{session_id, operator_id, timestamp, runtime_mode
  (one of `normal` / `strict` / `diagnostic`)}`.
- **`vault_state`** — opaque dict the kernel reads and merges. The kernel
  replaces the `elins` sub-state with the new ELINS `vault_update` and
  preserves every other sub-state untouched.
- **Kernel result** — locked shape `{session_id, operator_id, timestamp,
  runtime_decision (`allow` | `warn` | `block`), runtime_events[],
  elins_block, vault_update, operator_view{headline, details}}`.
- **Dispatcher result** — locked shape `{session_id, operator_id, timestamp,
  model_route{engine, reason}, runtime (full kernel output), ui_response
  {headline, body, severity, tags}}`.
- **Runner result** — locked shape `{session_id, operator_id, timestamp,
  runtime (dispatcher result), model (`route_model_request` result),
  vault_update}`. `vault_update` is lifted from the nested kernel output for
  ergonomic persistence callers.
- **`session_state`** (the `session_loop` façade) — `{session_id, operator_id,
  vault_state, history[{timestamp, intent_type, text, runtime_decision,
  engine}, …]}`.
- **Persistence keys** — vault by `operator_id`, session by `session_id`;
  both validated against the strict regex `^[A-Za-z0-9._-]{1,128}$`
  (anti-path-traversal) and JSON-validated at save.
- **Bounded non-determinism** — session IDs come from `_make_session_id`
  (`uuid4`) and timestamps from `_now` (UTC `datetime.now`). Both are
  module-level helpers in `session_loop`, patchable for deterministic tests.

## APIs / entrypoints

- HTTP (in `runtime_http.py`):
  - `POST /operator/session/start` — body `{operator_id}` → `{session_state}`.
  - `POST /operator/session/step` — body `{session_state, text, intent_type
    (default "query")}` → `{session_state, step_result}`.
  - The v63 GET endpoints (`/operator/session/{session_id}`,
    `/operator/sessions`, `/operator/vault/{operator_id}`) are gated by
    `require_operator`, which resolves the operator from `X-Session-ID` (401
    on missing or invalid). Errors otherwise: 422 for Pydantic body
    validation, 400 for downstream `ValueError`s.
- **Façade** (`session_loop`) — `start_session(operator_id)` → `session_state`;
  `step_session(session_state, text, *, intent_type="query")` →
  `{session_state, step_result}`. Returns a new `session_state`; callers
  rebind, never mutate.
- **Orchestrator** (`operator_session_runner`) —
  `run_operator_session_step(operator_intent, vault_state)` composes the
  dispatcher + the model router.
- **Dispatcher** (`runtime_dispatcher`) —
  `dispatch_operator_intent(operator_intent, vault_state)`.
- **Kernel** (`runtime_kernel`) — `run_runtime_step(operator_intent,
  session_context, vault_state)`.
- **Persistence** (`runtime_persistence`) — `load_vault(operator_id)`,
  `save_vault(operator_id, vault_state)`, `load_session(session_id)`,
  `save_session(session_state)`, `reload_backend()`.
- **Provider bridge** (`runtime_providers`) — `get_available_providers()`,
  `call_model(provider, model, prompt)`.
- **Config leaf** (`runtime_http_config`) — `get_call_timeout(provider)`,
  `get_health_timeout(provider)`, `get_retry_count(provider)`; all return
  defaults for an unknown provider.
- **Errors** — every layer raises `ValueError` on malformed input
  (`operator_intent`, `session_context`, `vault_state`, IDs); persistence
  additionally raises on non-JSON-serializable payloads. The kernel and
  dispatcher are deterministic — failures are validation failures, never
  network or model errors.

## Integration points

- **ELINS** — `runtime_kernel.run_runtime_step` calls
  `elins_session_integrator.run_elins_session` (Unit 33) and
  `apply_elins_runtime_actions` (Unit 34); these are distinct from the
  intelligence-kernel ELINS paths.
- **Model dispatch** — `operator_session_runner` calls
  `model_router.route_model_request` (Unit 38, in `docs/model_router.md`).
  `runtime_providers` is an alternate operator-vocab adapter over
  `model_router.route_request`. The runtime layer never talks to a provider
  directly.
- **Persistence** — `runtime_persistence` is the *only* runtime store; vault
  by `operator_id`, session by `session_id`. The other persistence layers
  (`operator_state`, `elins_project`, `threads_vault`, `kernel_logging`) are
  owned by the intelligence kernel and are out of scope.
- **Timeouts** — `runtime_http_config` is the single source of per-provider
  call and health timeouts; consumed by `model_router` and `runtime_http`.
- **Auth** — `runtime_http.require_operator` mirrors `app.py.require_session`
  but lives in `runtime_http` to avoid the circular import that would happen
  if `runtime_http` imported `app` (`app` already imports
  `runtime_http.runtime_router`).
- **Boundary with the Intelligence Kernel (10i)** — the two kernels do not
  call each other. The runtime kernel runs operator-session steps; the
  intelligence kernel runs intelligence operations (`run_c`, `run_G`,
  `run_ELINS`, threads, task modes). See *Non-goals*.

## Invariants

- **Pure deterministic core** — `runtime_kernel`, `runtime_dispatcher`, and
  `operator_session_runner` have no I/O, no network, and no model calls. The
  same inputs yield byte-equal output (modulo `route_request` timestamps).
- **Locked output shapes** — every layer documents and enforces a locked
  result shape (kernel result, dispatcher result, runner result).
- **Bounded non-determinism** — `session_loop` is the only non-deterministic
  layer; `uuid4` and `datetime.now` are confined to `_make_session_id` and
  `_now`, both patchable.
- **Stateless HTTP** — the `/operator/session/*` endpoints carry no
  per-request state; the client owns `session_state` and sends it back each
  step.
- **Strict import boundaries** — `runtime_http` imports only `session_loop` /
  `runtime_persistence` / `runtime_providers`; never the kernel or
  dispatcher. `runtime_http_config` has no back-imports. Both invariants are
  test-enforced.
- **Persistence safety** — strict ID regex (anti-path-traversal),
  `json.dumps`-validated at save, per-operator write lock (v62 / Unit 46),
  and the v64 / Unit 64 lost-update fix (`step_session` reloads vault +
  session from persistence on every step).
- **Immutability** — `step_session` returns a new `session_state`; callers
  rebind, never mutate. Inputs to the kernel / dispatcher / runner are never
  mutated.
- **Backend flexibility** — `runtime_persistence` is in-memory by default;
  `CLARITYOS_RUNTIME_STORE_DIR` opts into JSON-file backing; backend swap is
  supported via `reload_backend()`.
- **Provider bridge** — `runtime_providers` is a naming bridge over
  `model_router`; env-key gating, dispatch, and mock fallback remain in
  `model_router`.
- **No autonomous loop** — there is no background thread, daemon, or
  scheduler in this layer; every step is request-driven.

## Non-goals

- The Runtime Execution Layer is **not** the Intelligence Kernel
  (`intelligence_kernel.py`, 10i) — they are two different kernels running in
  separate stacks.
- It is not `operator_state` — that is a metadata store owned by the
  intelligence kernel and is the future 10k target.
- It is not `runtime_continuity.py` (Unit 37) — the dormant reentry module
  documented in `docs/continuity.md` (10g), built and tested but unwired.
- It is not `runtime_intelligence_wiring.py` (Phase 3 Unit 1) — a read-only
  intelligence-surfaces wiring layer that consumes Phase-2 producers; despite
  the `runtime_*` name, not part of this stack.
- It is not `operator_mode.py` (Phase 11) — a pure descriptive
  operator-posture derivation; despite the `operator_*` name, not part of
  this stack.
- It is not a scheduler, a router, or a forecasting engine — those are
  separate subsystems (`schedulers.md`, `model_router.md`).
- It has no autonomous behaviour and no "runtime AI"; every step is
  request-driven and model dispatch is delegated to `model_router`.

## Fiction removed

An "autonomous runtime loop", a "self-healing dispatcher", and an "execution
AI" / "runtime engine" do not exist — the runtime is a pure-functional
kernel / dispatcher / runner chain wrapped in a stateless HTTP surface plus a
persistence layer; the dispatcher is a rule-based deterministic stub.
"TermResolution" (retired in 10i) is not part of this layer either. The
cluster's candidate set also included two modules whose `runtime_*` /
`operator_*` filenames suggested membership but which are architecturally
separate — `runtime_intelligence_wiring.py` and `operator_mode.py` — both
excluded here and noted in *Non-goals*. `runtime_continuity.py` is a
near-namespace neighbour (Unit 37) but is the dormant reentry module
documented in 10g.
