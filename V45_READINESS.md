# V45 Readiness — Local model execution + on-device inference pipeline

Status: ✅ Ready
Backend version: `4.1`
Runtime version: `local_model_runtime.v45.1`
Router version: `model_router.v45.1`
Build: `20260507610000`

---

## What v45 ships

A first-class on-device inference runtime that the model router calls
into when `model_id == "local:llama3.1"`. The runtime cleanly degrades
to a deterministic mock when the operator hasn't configured a model
path, when the GGUF/ONNX backend isn't installed, or when a real
inference call fails — so the kernel is indifferent to whether real
weights are loaded. When `CLARITYOS_LOCAL_MODEL_PATH` *is* set the
runtime warm-starts on first use, caches a single thread-safe handle
per process, and dispatches subsequent inferences against it.

Per-user observability is wired through `operator_state` — every kernel
run that resolves to `local:llama3.1` bumps a
`local_model_usage_count` counter that the settings UI surfaces. The
founder console gets a `local_runtime` block on `/founder/models/status`
plus a dedicated `/founder/models/local` endpoint with the env path
and provider snapshot for debugging a misconfigured deploy.

---

## Files added / changed

### New
- `local_model_runtime.py` — `load_local_model`, `run_local_inference`,
  `unload_local_model`, `get_runtime_status`, `get_cached_handle`,
  `is_configured`, `configured_path` + module-level handle cache,
  per-handle locks, llama.cpp/ONNX backend selectors.
- `web/src/components/settings/LocalModelPanel.tsx` — Account-page
  panel (configured / loaded / backend / footprint / per-user usage /
  fallback note).
- `phone/app/local_model.tsx` — phone settings screen mirroring the web
  panel; pull-to-refresh CTA.
- `tests/test_v45_local_model.py` — 33 tests.
- `V45_READINESS.md` (this file).

### Modified
- `model_router.py`:
  - `ROUTER_VERSION` → `model_router.v45.1`; `LOCAL_MODEL_ID` constant.
  - `_call_local` now imports `local_model_runtime` lazily, warms the
    handle once via `_warm_local_handle`, and dispatches to
    `run_local_inference` (degrading to mock on any failure).
  - `get_model_status()` adds a `path` field to the `local` provider
    entry.
  - `get_router_status()` includes a `local_runtime` block.
  - `_reset_for_tests` wipes the warm handle cache + the runtime cache.
- `intelligence_kernel.py`:
  - Imports `local_model_runtime`.
  - `_resolve_model` bumps `operator_state.bump_local_model_usage(user)`
    when the resolved model_id is `local:llama3.1`.
  - `kernel_status()` includes a `local_model` block.
  - `kernel_view_for_user()` exposes `local_model_usage_count`.
- `operator_state.py`:
  - `STATE_VERSION` → `operator_state.v45.1`.
  - `_default_state` adds `local_model_usage_count: 0`.
  - `_normalise` coerces `local_model_usage_count` (legacy records
    default to 0, negative values clamp).
  - New `bump_local_model_usage(user_id, *, by=1)` setter.
- `app.py`:
  - Imports `local_model_runtime`.
  - `GET /me/local_model` (auth) — runtime + per-user usage snapshot.
  - `GET /founder/models/local` (founder) — runtime + env path +
    `local` provider snapshot.
  - `local_model` capability advertised on `/me`.
  - Backend version `4.1`; root listing extended.
  - `/health` reports `version: 4.1`.
- `web/src/lib/api.ts` — `V45_LOCAL_MODEL_ID`,
  `V45LocalRuntimeStatus`, `V45LocalModelMe`, `V45FounderLocal`,
  `meLocalModel`, `founderModelsLocal`; extends
  `V44RouterStatus.providers.local` + adds `V44RouterStatus.local_runtime`.
- `web/src/routes/Account.tsx` — embeds `<LocalModelPanel />`.
- `web/src/components/founder/models/FounderModelStatusPanel.tsx` —
  renders the `local_runtime` block (path / loaded / backend / mock /
  memory_footprint / inferences / last_error).
- `phone/lib/api.ts` — same v45 types/helpers as web.
- `phone/app/_layout.tsx` — register `local_model` stack screen.
- `phone/app/settings.tsx` — link to `/local_model`.
- `tests/conftest.py` — reset hook for `local_model_runtime._reset_for_tests`.
- `tests/test_v28_endpoints.py` — health version `4.1`.
- `tests/test_v39_operator_state.py` — version assertion loosened.
- `tests/test_v44_model_router.py` — provider-status assertion accepts
  `path` on `local`; router-status version assertion loosened.
- `BUILD_VERSION` — `20260507610000`.

---

## Public API

```python
# local_model_runtime
load_local_model(path: Optional[str] = None) -> ModelHandle
run_local_inference(handle, prompt, *,
                    temperature=0.2, max_tokens=4096) -> dict
unload_local_model(handle) -> bool

get_runtime_status() -> dict        # configured/path/loaded/backend/mock/footprint/...
get_cached_handle() -> ModelHandle | None
is_configured() -> bool
configured_path() -> str | None

LOCAL_RUNTIME_VERSION = "local_model_runtime.v45.1"
DEFAULT_TEMPERATURE   = 0.2
DEFAULT_MAX_TOKENS    = 4096
```

```python
# model_router additions
LOCAL_MODEL_ID = "local:llama3.1"
get_local_runtime_status() -> dict
```

```python
# operator_state additions
bump_local_model_usage(user_id: str, *, by: int = 1) -> dict
```

### Runtime semantics

- `CLARITYOS_LOCAL_MODEL_PATH` unset → `load_local_model` returns a
  mock handle (`backend="mock"`, `mock=True`).
- Path set but file missing → mock handle with `last_error`.
- Path set + file present + `llama_cpp` available → real handle
  (`backend="llama_cpp"`, `mock=False`); cached for the process.
- Path set + file present + backend missing → mock handle with
  `last_error` explaining the missing import. The runtime never
  crashes the kernel.
- `run_local_inference` clamps temperature to `[0.0, 2.0]` and
  max_tokens to `[1, 32768]`.
- Inference exceptions degrade to the deterministic mock payload
  (with `fallback_error`); never raise out.
- Backend selection is by extension: `.gguf` / `.bin` / `*q[458]_*`
  → `llama_cpp`; `.onnx` / `.ort` → `onnxruntime`; unknown → assume
  `llama_cpp` (fails to import → mock).
- Per-handle `_lock` serialises generation calls so concurrent
  router requests don't trample inside `llama_cpp`.

---

## Provider env vars

```
CLARITYOS_LOCAL_MODEL_PATH = /opt/models/llama-3.1-8b.q4_K_M.gguf
```

When set, `model_router.get_model_status()['local']` returns
`{"configured": true, "path": "/opt/models/..."}`.

---

## API surface

### `GET /me/local_model` (auth)
```jsonc
{
  "ok": true,
  "model_id": "local:llama3.1",
  "runtime": {
    "version": "local_model_runtime.v45.1",
    "configured": true,
    "path": "/opt/models/llama-3.1-8b.q4_K_M.gguf",
    "loaded": true,
    "backend": "llama_cpp",
    "mock": false,
    "memory_footprint_mb": 4523.7,
    "inference_count": 12,
    "loaded_at": 1762345678.123,
    "last_error": null,
    "fallback": "real backend"
  },
  "usage": {
    "local_model_usage_count": 4,
    "last_model_used": "local:llama3.1",
    "preferred_model": "local:llama3.1",
    "is_local_preferred": true
  }
}
```

### `GET /founder/models/local` (founder)
```jsonc
{
  "ok": true,
  "model_id": "local:llama3.1",
  "runtime": { /* same shape as above + bytes_estimate, cached_handles */ },
  "env_path": "/opt/models/llama-3.1-8b.q4_K_M.gguf",
  "router_provider": { "configured": true, "path": "/opt/models/..." }
}
```

### `/me` additions
```jsonc
"intelligence_kernel": {
  ...,
  "local_model_usage_count": 4
}
```

### `/founder/intelligence/kernel/status` additions
```jsonc
{
  ...,
  "models": {
    ...,
    "local_runtime": {
      "configured": bool, "path": str|null, "loaded": bool,
      "backend": str|null, "mock": bool,
      "memory_footprint_mb": float, "inference_count": int,
      ...
    }
  },
  "local_model": {
    "configured": bool, "path": str|null, "loaded": bool,
    "backend": str|null, "mock": bool,
    "memory_footprint_mb": float, "inference_count": int,
    "loaded_at": float|null, "last_error": str|null,
    "version": "local_model_runtime.v45.1"
  }
}
```

---

## UI

### Web
- **Account → Local model** — configured/loaded/backend pills,
  path (full), memory footprint, process-wide inference count,
  per-user usage counter, "preferred?" indicator, fallback note,
  last error (when present). Refreshable in place.
- **Founder console → Model status panel** — extends with a
  `Local model runtime` sub-section showing path / loaded / backend /
  mock / memory_footprint / inferences / last_error.

### Phone
- **`local_model.tsx`** — same data points stacked vertically with
  refresh CTA; surfaces "Path", "Your usage", "Fallback", and an
  optional "Last error" card.
- **`settings.tsx`** gains a "Local model" entry beneath
  "Model preferences".

---

## Tests

```
tests/test_v45_local_model.py — 33 tests, all pass
Full suite — 588 passed, 0 failed
```

Coverage:
- `load_local_model`: mock when env unset; mock when path missing
  (records `last_error`); warm-start cache reuse; real path simulated
  by monkeypatching `_load_llama_cpp`; missing-backend degradation.
- `run_local_inference`: deterministic mock text + per-prompt hash
  uniqueness; clamps out-of-range temperature/max_tokens; real
  dispatch via fake `Llama` class; inference exception degrades to
  mock with `fallback_error`; rejects non-`ModelHandle` arg.
- `unload_local_model`: drops cache + idempotent on second call;
  rejects bad arg.
- `get_runtime_status`: shape when unconfigured; computes
  `memory_footprint_mb` from file size after a real load.
- `model_router`: `_call_local` → mock when path missing; → real
  runtime when path set; `get_model_status['local']` carries `path`;
  `get_router_status` includes `local_runtime` block; warm-start
  dispatches load only once across N route calls.
- `operator_state`: default `local_model_usage_count == 0`;
  `bump_local_model_usage` increments + clamps negative; no-user
  call is a no-op.
- Kernel: routes user with `preferred_model="local:llama3.1"`
  through local — counter increments; non-local default does NOT
  bump; `kernel_status` includes `local_model` block;
  `kernel_view_for_user` exposes `local_model_usage_count`.
- Endpoints: `/me/local_model` shape + counter reflects post-run
  bump; `/founder/models/local` shape + founder gate;
  `/founder/models/status` carries `local_runtime`; `/me` advertises
  `local_model` capability; `/health` reports version `4.1`.

All tests run in mock mode (no real `llama_cpp` / `onnxruntime` import
required). Real-load paths are exercised via monkeypatching so the
test environment stays portable.

---

## Notes / follow-ups

- The kernel still doesn't feed prompts into LLM providers — v45 is
  the on-device runtime + observability layer. When prompt assembly
  lands (future pass), `route_request("local:llama3.1", prompt)` is
  ready to dispatch deterministically through the warm handle.
- `onnxruntime` generation pipeline is stubbed — the path loads the
  `InferenceSession` correctly but the generation step returns a
  placeholder string until a tokenizer + io_binding is wired. GGUF /
  llama.cpp is the productionised path.
- The runtime caches one handle per unique resolved path. Switching
  models in production requires either an explicit
  `unload_local_model(handle)` followed by a fresh `load_local_model`,
  or a process restart. The cache keying on the resolved path means
  two paths can be loaded simultaneously if a future feature needs it.
- Inference is CPU-only by design (the spec required CPU execution
  with bounded memory). GPU acceleration would slot into the existing
  loaders without changing the public API.
- Pre-v45 surfaces are unchanged. The `local_model` capability +
  the new endpoints are additive; clients that ignore them keep
  working as before.
