# Model Router (`model_router.py`)

## 1. Purpose and role

`model_router.py` (v44 introduced; v45/v57/v64/v66/v79 layered;
`ROUTER_VERSION = "model_router.v57.1"`) is the **single point of
model-id resolution and provider dispatch** in the ClarityOS runtime
layer. Every kernel `run_*` reaches the router via two calls:

```python
model_id = model_router.select_model(user, task=...)
result   = model_router.route_request(model_id, prompt)
```

The router is **deterministic with respect to its inputs + the small
amount of stored state it consults** (`operator_state.preferred_model`,
the founder-set global default, and warm-start caches). Provider calls
are guarded by env keys; without keys the matching provider returns a
deterministic mock payload so the surrounding system can exercise
routing logic offline.

Five layers of behavior in one module:

| Layer | Owns |
|---|---|
| **Catalogue** | `MODEL_REGISTRY`, `SUPPORTED_MODELS`, `TASK_DEFAULTS`, `_PROVIDER_ENV_KEYS`, `_MODEL_ALIASES` |
| **Resolution** | `select_model` 4-step precedence + `resolve_model_alias` + `parse_provider` |
| **Dispatch** | `route_request` + 5 provider handlers + `_http_post_json` chokepoint |
| **Status** | `get_model_status`, `get_router_status`, `get_local_runtime_status` for the founder console |
| **Integration** | `route_model_request` (v57 dispatcher bridge), `call_regression_first` (v79 task helper) |

### Core invariants

1. **Deterministic precedence.** `select_model` always evaluates in
   the documented 4-step order.
2. **`AUTO` is a sentinel.** Trapped before dispatch.
3. **All provider handlers degrade to mock on missing config.**
4. **All provider handlers degrade to mock on any exception.**
5. **`route_request` never raises for real-network reasons** — only
   for input validation.
6. **Mock results truncate the prompt to 60 chars.**
7. **Dispatcher prompts never carry raw operator payload.**
8. **Hard-pinned engines bypass user preference.**
9. **Local handle cache invalidates on path change.**
10. **No retries** — every failure is one log line + one mock result.

### Status

| File | Status | Reason |
|---|---|---|
| `model_router.py` | **CURRENT** | 964 lines · 12 public functions · 35 importers (10 production + 24 tests + 1 doc) |

### Implementation location

- **Source:** `model_router.py` (964 lines).
- **Imports:** stdlib only eager (`logging`, `os`, `time`,
  `contextlib`, `typing`) + `runtime_http_config` (eager) + 3 lazy
  imports for cycle breaks (`operator_state`, `local_model_runtime`,
  `intelligence_kernel`).
- **No third-party HTTP library, no LLM SDK.** All provider HTTP uses
  stdlib `urllib.request`.

---

## 2. Public API surface

12 public functions plus 1 test helper.

| Function | Line | Purpose |
|---|---|---|
| `is_valid_model(model_id)` | 153 | None-safe membership check against `SUPPORTED_MODELS` |
| `resolve_model_alias(name)` | 187 | Friendly-name → canonical model_id (case-insensitive aliases) |
| `parse_provider(model_id)` | 207 | Map a model_id to its provider tag; raises on unknown id |
| `get_founder_default_model()` | 235 | Read process-global founder override |
| `set_founder_default_model(model_id)` | 239 | Set/clear founder override; validates against `SUPPORTED_MODELS` |
| `select_model(user, *, task, override=None)` | 269 | 4-step precedence → resolved `model_id` |
| `route_request(model_id, prompt, *, temperature=0.2, max_tokens=4096)` | 313 | Send a prompt to the chosen provider; returns normalised dict |
| `get_model_status()` | 682 | Per-provider configuration snapshot (founder console) |
| `get_router_status()` | 698 | Full router snapshot (defaults, providers, local runtime, version) |
| `get_local_runtime_status()` | 648 | Proxy to `local_model_runtime.get_runtime_status` with defensive fallback |
| `route_model_request(operator_intent, model_route)` | 804 | v57 dispatcher bridge — engine → model_id → response |
| `call_regression_first(packet, *, user=None, model_id=None, store=None)` | 918 | v79 task helper; lazy-delegates to `intelligence_kernel.run_regression_first` |
| `_reset_for_tests()` | 954 | Test helper — wipes founder default + local handle cache + resets local_model_runtime |

### Module constants

| Name | Value | Purpose |
|---|---|---|
| `ROUTER_VERSION` | `"model_router.v57.1"` | Reported by `get_router_status` |
| `LOCAL_MODEL_ID` | `"local:llama3.1"` | The single on-device model id |
| `MODEL_REGISTRY` | `dict[provider → tuple[model_id, ...]]` (5 providers) | Per-provider registry (v66) |
| `SUPPORTED_MODELS` | Flat tuple from `MODEL_REGISTRY` + `("auto",)` | Validation set (6 model_ids + sentinel) |
| `AUTO` | `"auto"` | Routing sentinel — not a wire model |
| `PROVIDER_PREFIXES` | 5-tuple of `(prefix, name)` pairs | Maps model_id → provider tag |
| `TASK_DEFAULTS` | 11-entry dict — task → model_id | Final fallback in `select_model` |
| `_PROVIDER_ENV_KEYS` | dict — provider → env-var names | "Configured" check source |
| `_MODEL_ALIASES` | 19-entry dict — friendly name → canonical id | Lowercase alias resolution |
| `_founder_default_model` | `Optional[str]` (line 147) | Process-global founder override (in-process only) |
| `_LOCAL_HANDLE_CACHE` | `Optional[Any]` (line 620) | Cached local runtime handle |
| `_LOCAL_HANDLE_PATH` | `Optional[str]` (line 621) | Path the cache was loaded for |
| `_PROVIDER_HTTP_TIMEOUT` | `float` (line 395) | Mutable HTTP timeout (NOT thread-safe — documented) |

---

## 3. Provider-selection logic

### `MODEL_REGISTRY` (5 providers)

```python
MODEL_REGISTRY: dict[str, tuple[str, ...]] = {
    "openai":    ("openai:gpt-4o", "openai:gpt-4o-mini"),
    "anthropic": ("anthropic:claude-3.7",),
    "google":    ("google:gemini-2.0-flash",),
    "xai":       ("xai:groq-llama",),
    "local":     ("local:llama3.1",),
}
```

**6 model_ids + `"auto"` sentinel** in the derived flat
`SUPPORTED_MODELS`.

### `select_model(user, *, task, override=None) -> str` (line 269)

4-step precedence:

```
1. Explicit override (if a valid model_id and != "auto")
2. Founder global default (set via /founder/models/override, in-process)
3. operator_state.preferred_model (if set + valid + != "auto")
4. Task-based fallback: TASK_DEFAULTS[bucket]
```

Step 3 **lazy-imports `operator_state`** (line 297) to break the
`model_router ↔ operator_state` cycle. Step 4's bucket is
`_normalise_task(task)` — maps kernel run aliases (`"run_c"` →
`"c"`, etc.).

### Alias resolution — `resolve_model_alias(name) -> Optional[str]` (line 187)

19-entry alias dict. **Case-insensitive for aliases, case-sensitive
for canonical ids:**

```
claude / anthropic / claude-3.7      → anthropic:claude-3.7
openai / gpt / gpt-4 / gpt-4o        → openai:gpt-4o
gpt-4o-mini                          → openai:gpt-4o-mini
gemini / google / gemini-2.0-flash   → google:gemini-2.0-flash
xai / grok / groq / groq-llama       → xai:groq-llama
local / llama / llama3.1             → local:llama3.1
```

Returns `None` on unknown names — caller decides whether to ignore
or raise.

### Provider parsing — `parse_provider(model_id) -> str` (line 207)

Maps a model_id to its provider tag:

| Prefix | Provider tag |
|---|---|
| `openai:` | `openai` |
| `anthropic:` | `anthropic` |
| `google:` | `gemini` |
| `xai:` | `xai` |
| `local:` | `local` |

Returns `"auto"` for the sentinel (honest log lines). Raises
`ValueError` on any unknown id.

### Validation

- `is_valid_model(model_id)` (line 153) — None-safe membership check.
- `set_founder_default_model(model_id)` validates against
  `SUPPORTED_MODELS` (raises on unknown). **Does not canonicalise
  aliases** — callers wanting alias support must call
  `resolve_model_alias` first.

### Hard-pinned engines (v57 dispatcher bridge)

```python
_ENGINE_HARD_PIN: dict[str, str] = {
    "local": LOCAL_MODEL_ID,
}

_ENGINE_TO_TASK: dict[str, str] = {
    "claude":  "G",       # plan / reasoning
    "copilot": "c",       # query / fast lexical
    "gemini":  "ELINS",   # action / deterministic pipeline
    "grok":    "c",       # alias for fast lane
}

_VALID_ENGINES: tuple = sorted(set(_ENGINE_HARD_PIN) | set(_ENGINE_TO_TASK))
```

**Hard-pinned engines bypass user preference** — `_ENGINE_HARD_PIN`
is consulted before `_ENGINE_TO_TASK` in `_resolve_model_id_for_engine`
(line 796–800).

---

## 4. Outbound HTTP funnel — `_http_post_json`

### Single chokepoint

```python
def _http_post_json(url: str, *, headers: dict, body: dict) -> dict:
    """Single-shot JSON POST over stdlib urllib."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    for k, v in headers.items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=_PROVIDER_HTTP_TIMEOUT) as resp:
        raw = resp.read()
    decoded = json.loads(raw.decode("utf-8"))
    if not isinstance(decoded, dict):
        raise ValueError("provider returned non-object JSON")
    return decoded
```

Located at line 419. **The only outbound HTTP path in the runtime
layer.** Test mocks monkey-patch at this single site rather than
per-provider. Stdlib only — no `requests`, `httpx`, `aiohttp`, or any
LLM SDK.

### `_PROVIDER_HTTP_TIMEOUT` and `_request_timeout`

```python
_PROVIDER_HTTP_TIMEOUT: float = runtime_http_config.DEFAULT_CALL_TIMEOUT
```

Mutable via the `_request_timeout(seconds)` context manager (line
398). **Documented as NOT thread-safe** (line 407) — mutates a
module-level global. Safe in the current single-threaded runtime;
would race in multi-worker uvicorn.

Each real call wraps the handler body in
`_request_timeout(runtime_http_config.get_call_timeout(provider))`
to apply a per-provider timeout.

### Provider endpoints

| Provider | Endpoint | Auth |
|---|---|---|
| OpenAI | `POST https://api.openai.com/v1/chat/completions` | `Authorization: Bearer <CLARITYOS_OPENAI_KEY>` |
| Anthropic | `POST https://api.anthropic.com/v1/messages` | `x-api-key: <CLARITYOS_ANTHROPIC_KEY>` + `anthropic-version: 2023-06-01` |
| Gemini | `POST .../models/{model}:generateContent?key=<CLARITYOS_GEMINI_KEY>` | Query-string key |
| xAI | (mock-only — no wire endpoint) | — |
| Local | In-process via `local_model_runtime.run_local_inference` | Path = `CLARITYOS_LOCAL_MODEL_PATH` |

### Provider handlers (5)

All share `(model_id, prompt, *, temperature, max_tokens) -> dict`.
Every handler:

1. `_provider_configured(provider)` first → if False, return `_mock_result(...)`.
2. Build provider-specific JSON body.
3. With `_request_timeout(...)`: `_http_post_json(url, headers, body)`.
4. Extract text per provider's response shape (raises `ValueError` on shape mismatch).
5. On any exception → `logger.warning + _mock_result(model_id, provider, prompt, started, error=str(e))`.

| Handler | Line | Notes |
|---|---|---|
| `_call_openai` | 442 | Reads `choices[0].message.content` |
| `_call_anthropic` | 478 | Concatenates `content[*].text` for `type=="text"` blocks |
| `_call_gemini` | 519 | Concatenates `candidates[0].content.parts[*].text` |
| `_call_xai` | 557 | **Mock-only** — documented at lines 558–560 (v65 spec scoped out) |
| `_call_local` | 566 | Delegates to `local_model_runtime.run_local_inference` via warm-start cache |

### `route_request(model_id, prompt, *, temperature=0.2, max_tokens=4096) -> dict` (line 313)

```python
{
    "ok": True,
    "model_id": str,
    "provider": str,
    "text": str,
    "mock": bool,
    "ts": float,
}
```

Pipeline:

1. Validate `model_id` (raises `ValueError` on unknown id).
2. Trap `AUTO` sentinel — rewrite to `TASK_DEFAULTS["ELINS"]` (line 332).
3. `parse_provider(model_id)` → provider tag.
4. Lookup `_PROVIDER_HANDLERS[provider]` → handler callable.
5. If handler is `None` → `_mock_result(...)`.
6. Try handler. On any exception, log + `_mock_result(model_id,
   provider, prompt, started, error=str(e))`.

**`route_request` never raises for real-network reasons.** Only input
validation can raise.

### `_mock_result(model_id, provider, prompt, started, *, error=None) -> dict` (line 352)

```python
preview = (prompt or "")[:60]
out = {
    "ok": True,
    "model_id": model_id,
    "provider": provider,
    "text": f"[mock {model_id}] {preview}".rstrip(),
    "mock": True,
    "ts": started,
}
if error:
    out["error"] = error
return out
```

**Deterministic given prompt** — same prompt → byte-identical `text`
field. The `ts` field is wall-clock; only `text` is deterministic.

Documented intent (lines 360–362): *"We don't echo the full prompt to
keep logs free of operator content; instead we surface a hash-lite
preview that callers can correlate with."*

---

## 5. Task defaults and request shaping

### `TASK_DEFAULTS` (11 entries)

| Task | Default model_id |
|---|---|
| `c` | `openai:gpt-4o-mini` |
| `G` | `openai:gpt-4o` |
| `ELINS` | `openai:gpt-4o` |
| `regional` | `anthropic:claude-3.7` |
| `forecast` | `anthropic:claude-3.7` |
| `macro` | `anthropic:claude-3.7` |
| `entity` | `anthropic:claude-3.7` |
| `thread` | `openai:gpt-4o` |
| `thread_summary` | `anthropic:claude-3.7` |
| `emotional_physics` | `anthropic:claude-3.7` |
| `regression_first` | `openai:gpt-4o` |

**Note (per source lines 99–102):** OpenAI keys are wired live; the
Anthropic tasks mock-fall back until an Anthropic key is added.

### Request shaping per provider

Each provider handler shapes its body slightly differently:

| Provider | Body shape |
|---|---|
| OpenAI | `{model, messages: [{role: "user", content: prompt}], temperature, max_tokens}` |
| Anthropic | `{model, max_tokens, messages: [{role: "user", content: prompt}], temperature}` |
| Gemini | `{contents: [{parts: [{text: prompt}]}], generationConfig: {temperature, maxOutputTokens}}` |
| xAI | (no wire shape — mock-only) |
| Local | Forwarded to `local_model_runtime.run_local_inference(handle, prompt, temperature, max_tokens)` |

### Dispatcher bridge prompt shaping (v57)

`_shape_prompt_from_intent(operator_intent) -> str` (line 755) produces
a deterministic, length-capped prompt for the dispatcher bridge:

```
[ClarityOS operator step] intent={intent_type} session={session_id[:8]}
operator={operator_id[:8]} runtime_mode={runtime_mode}
override={override_decision} elins_inputs_keys={n_keys}
```

**No raw operator payload passthrough.** Truncated IDs (`[:8]`),
structured summary only. Documented at lines 757–763.

### v79 task helper — `call_regression_first`

```python
def call_regression_first(packet, *, user=None, model_id=None, store=None) -> dict:
    resolved = select_model(user, task="regression_first", override=model_id)
    import intelligence_kernel    # lazy — break cycle
    return intelligence_kernel.run_regression_first(
        packet, user_id=user, model_id=resolved, store=store,
    )
```

Resolves `model_id` via the standard precedence + lazy-delegates to
the kernel. The lazy import (line 942) breaks the `model_router ↔
intelligence_kernel` cycle.

---

## 6. Local-model routing

### `_call_local` (line 566)

When `CLARITYOS_LOCAL_MODEL_PATH` is unset (or `local_model_runtime`
is unavailable for any reason), falls back to the deterministic router
mock. The runtime itself also degrades to its own deterministic mock
when the path is set but the file/backend isn't actually there —
**both paths converge on a `mock=True` payload**.

Pipeline:

1. `_provider_configured("local")` (reads `CLARITYOS_LOCAL_MODEL_PATH`)
   — if False, return `_mock_result(model_id, "local", prompt,
   started)`.
2. **Lazy import** `local_model_runtime` (line 583) — keeps the router
   test surface decoupled when local is unused.
3. `_warm_local_handle(local_model_runtime)` — returns cached handle
   or loads it.
4. If handle is `None` → mock.
5. `local_model_runtime.run_local_inference(handle, prompt,
   temperature, max_tokens)`.
6. Normalise into the router contract:
   `{ok, model_id, provider, text, mock, ts, backend, duration_ms,
   tokens_estimated, model_path, fallback_error?}`.

### Warm-start cache

```python
_LOCAL_HANDLE_CACHE: Optional[Any] = None
_LOCAL_HANDLE_PATH: Optional[str] = None
```

Cached for the process lifetime. `_warm_local_handle(runtime_module)`:

1. Read `runtime_module.configured_path()`.
2. Path unset → drop cache, return `None`.
3. Cache hit + path match → return cached handle.
4. Cache miss → `runtime_module.load_local_model(path)`; cache +
   return; on failure return `None`.

**Invariant:** the cache invalidates on path change. Protects against
env-var changes mid-process.

### `get_local_runtime_status() -> dict` (line 648)

Proxy to `local_model_runtime.get_runtime_status()` with defensive
fallback when the runtime module isn't importable. Returns a stable
shape regardless of runtime availability:

```python
{
    "configured": bool,
    "path": Optional[str],
    "loaded": bool,
    "backend": Optional[str],
    "mock": bool,
    "memory_footprint_mb": float,
    "inference_count": int,
    "loaded_at": Optional[...],
    "last_error": Optional[str],
}
```

---

## 7. ESO interactions (kernel → router)

The router has **no direct ESO interaction**. ESO is a kernel-side
concept; the router only sees its downstream effect — the model_id
the kernel passes after ESO mode resolution.

### Indirect dependency chain

```
kernel._resolve_external_signal_mode(user, override)
        ↓
operator_state.set_external_signal_mode(user, mode)     [if override]
        ↓
kernel._resolve_model(user, task=...)
        ↓
model_router.select_model(user, task=...)
        ↓
        ├─ Step 3 lazy-imports operator_state
        └─ Reads operator_state.preferred_model
```

The router **never reads `operator_state.external_signal_mode`** and
**never calls `perplexity_oracle`**. ESO mode affects which model
gets selected only indirectly via the user's preferred_model field —
and even that is independent of ESO mode (preferred_model is set by
the user, not by ESO).

### What the router does see

- `model_router.LOCAL_MODEL_ID` is **exported for kernel use** — the
  kernel checks `model_id == LOCAL_MODEL_ID` to decide whether to
  bump `operator_state.local_model_usage_count`.
- `TASK_DEFAULTS` is **read by the kernel's fallback path** when
  `model_router.select_model` raises (defensive `try/except` at
  `intelligence_kernel._resolve_model:199`).

There is no other state shared between the router and the ESO
subsystem.

---

## 8. operator_state interactions

### Read path (lazy)

`select_model` step 3 (line 295–303):

```python
if user:
    try:
        import operator_state
        state = operator_state.get_operator_state(user) or {}
        pref = state.get("preferred_model")
        if isinstance(pref, str) and pref and pref != AUTO and is_valid_model(pref):
            return pref
    except Exception:  # pragma: no cover (defensive)
        pass
```

**Lazy import** breaks the `model_router ↔ operator_state` cycle. The
silent `except Exception: pass` is the documented defensive path
(PASS‑3C N5) — `operator_state` failures fall through to step 4
(task default) without logging.

### Write path

**The router never writes operator_state.** All writes happen in
`intelligence_kernel._resolve_model`:

| Action | Trigger |
|---|---|
| `operator_state.record_model_used(user, model_id)` | Always after `select_model` returns |
| `operator_state.bump_local_model_usage(user)` | When `model_id == LOCAL_MODEL_ID` |

This is the **selected ≡ recorded invariant** (cross-module X4 from
PASS‑3A): the model_id returned to the caller is always the model_id
persisted onto operator_state.

### Validation symmetry

`operator_state.set_preferred_model` (line 351 of `operator_state.py`)
lazy-imports `model_router.is_valid_model` to validate user-supplied
model_ids. The cycle is broken on both sides — neither module
imports the other at top level.

### Founder default (operator_state-free)

`_founder_default_model` is **a process-global, not persisted to
operator_state or memory_vault**:

```python
_founder_default_model: Optional[str] = None
```

Set via `set_founder_default_model(model_id)`; cleared via
`_reset_for_tests` or explicit `None`/`""`. `logger.info` line on
every set (not on every read). **Cross-user leak by design** — a
founder setting the default affects ALL users of that Cloud Run
instance (PASS‑3A I26 / PASS‑3B B5).

---

## 9. Privacy boundaries

### G‑R1 — No raw payload in dispatcher-shaped prompts

`_shape_prompt_from_intent` (line 755) builds a structured summary
with `session_id[:8]`, `operator_id[:8]`, runtime_mode,
override_decision, and `elins_inputs_keys=N`. **Never the raw
payload.** Documented as *"deterministic, length-capped, no raw
payload text passthrough."*

### G‑R2 — Mock result truncation

`_mock_result` (line 352) echoes only the first 60 chars of the
prompt as `[mock {model_id}] {preview}`. Documented intent (lines
360–362): *"to keep logs free of operator content."*

### G‑R3 — No API keys in module-level state

HTTP headers are constructed at call time from `os.environ.get(...)`
(e.g. `_call_openai:446`). Keys never enter module-level state — no
global caches them, no log line includes them.

### G‑R4 — No prompt/response text in failure logs

```python
logger.warning("openai call failed → mock; err=%s", e)
```

The exception message only (`err=str(e)`) — never the prompt or
response body. Provider response failures preserve the original error
string in the mock fallback's `error` field, but `_mock_result`
doesn't echo it into the returned `text` field.

### G‑R5 — Founder default state is metadata-only

`get_founder_default_model()` returns a model_id string. No
operator content, no session info, no user context.

### G‑R6 — `get_router_status` is metadata-only

Returns provider configured state, version string, supported models,
local runtime metadata, task defaults. **No prompts, no responses, no
keys, no user-identifying data.**

### G‑R7 — `get_model_status` is metadata-only

Per-provider `{configured: bool}` map + `local.path` (path string
only, not credentials). Surfaced to the founder console.

### Documented gaps

- **`_request_timeout` is documented NOT thread-safe** (line 407). In
  multi-worker uvicorn this would race; safe today because the runtime
  is single-threaded. PASS‑3C B1.
- **Provider response shape assumptions** (PASS‑3C B10) — each
  `_call_*` reads specific JSON paths and raises `ValueError` on
  mismatch, but a structurally valid but semantically empty response
  passes through.

---

## 10. Determinism boundaries

### Pure / deterministic

| Property | Status |
|---|---|
| `select_model(user, task)` given inputs + (operator_state, founder_default) state | Deterministic |
| `resolve_model_alias(name)` | Pure dict lookup |
| `parse_provider(model_id)` | Pure |
| `is_valid_model(model_id)` | Pure membership check |
| `_normalise_task(task)` | Pure dict lookup + fallback |
| `_shape_prompt_from_intent(operator_intent)` | Pure (length-capped) |
| `_mock_result.text` | Deterministic given prompt + model_id |
| `_resolve_model_id_for_engine(engine, user)` | Deterministic given engine + (operator_state, founder_default) state |
| `get_router_status()` / `get_model_status()` | Deterministic given env + cached state |

### Non-deterministic

| Property | Source |
|---|---|
| Real OpenAI / Anthropic / Gemini text | Temperature 0.2 reduces but does not eliminate model variance |
| `_mock_result.ts` field | Wall-clock (`time.time()` at handler entry) |
| HTTP transport latency | Network conditions |
| Local model output (when real) | Model variance |
| `_LOCAL_HANDLE_CACHE` warmth | Process-state dependent — first call pays load cost |

### Retry behavior: **none**

The router has no retry logic. Every failure is one log line + one
mock result. **No exponential backoff, no circuit breaker, no
provider failover.** The router trusts the caller (kernel) to handle
the `mock=True` signal as appropriate.

Caller-facing failure modes:

| Failure | Response shape |
|---|---|
| Unknown `model_id` | Raises `ValueError` (validation) |
| Provider unconfigured | `_mock_result(...)` |
| Provider returns malformed JSON | `_mock_result(..., error="...")` |
| Provider raises HTTP error | `_mock_result(..., error="...")` |
| Provider returns empty text | `ValueError` raised internally, caught, → `_mock_result(..., error="...")` |
| Provider returns valid response | `{ok: True, mock: False, text, ts, ...}` |

The caller sees `mock=False` for real responses, `mock=True` otherwise.

---

## 11. Cross-module interactions

### Imports (production)

```
runtime_http_config       # eager — single internal dep
contextlib                # stdlib (contextmanager)
logging, os, time, typing # stdlib
```

### Lazy imports (cycle breaks — 5 sites)

| Lazy import | Location | Cycle broken |
|---|---|---|
| `operator_state` | `select_model:297` | router ↔ operator_state |
| `local_model_runtime` | `_call_local:583` | router ↔ runtime |
| `local_model_runtime` | `get_local_runtime_status:654` | router ↔ runtime |
| `local_model_runtime` | `_reset_for_tests:961` | router ↔ runtime |
| `intelligence_kernel` | `call_regression_first:942` | router ↔ kernel |

### Importers (35 total — 10 production + 24 tests + 1 doc)

- **Production:** `app.py`, `intelligence_kernel.py`, `operator_state.py`, `runtime_http.py`, `runtime_providers.py`, `el_ins/el_ins_analyzer.py`, `operator_session_runner.py`, plus indirect production reach via `acceptance_dashboard.py` and `daily_personal_elins.py`.
- **Tests:** every batch-specific test from v44 onward + el_ins tests + runtime tests + dispatcher tests.
- **Docs:** `docs/operator_state.md` (string match, not a code import).

### Three known cycles, all broken

| Cycle | Direction | Break mechanism |
|---|---|---|
| `model_router ↔ operator_state` | router lazy → state; state lazy → router | Symmetric lazy import |
| `model_router ↔ local_model_runtime` | router lazy → runtime; runtime has no back-import | Asymmetric — runtime is leaf |
| `model_router ↔ intelligence_kernel` | kernel eager → router; router lazy → kernel | Asymmetric — kernel eager, router lazy |

### No coupling

- **No LLM SDK** (`anthropic`, `openai`, `google.generativeai`).
- **No third-party HTTP library** (`requests`, `httpx`, `aiohttp`).
- **No vault import** — never reads or writes `memory_vault`.
- **No HTTP route definitions** — never imported by FastAPI route
  decorators; the route layer in `app.py` calls into the router as a
  function.
- **No intelligence-layer engine imports.**

---

## 12. Known guarantees and gaps

### Strong runtime guarantees

1. **Deterministic precedence** — `select_model` always evaluates
   4-step order; same inputs + state → same `model_id`.
2. **Unknown ids raise everywhere** — `is_valid_model` is None-safe;
   `select_model`, `set_founder_default_model`, `route_request`,
   `parse_provider` all reject unknown ids.
3. **`AUTO` is a sentinel** — trapped before dispatch.
4. **All providers degrade to mock** on missing config or any
   exception.
5. **`route_request` never raises for real-network reasons** — only
   input validation.
6. **Single HTTP outbound funnel** — `_http_post_json` is the only
   path to provider APIs.
7. **No LLM SDK** — pure stdlib `urllib.request`.
8. **No API keys in module state** — read at call time only.
9. **Mock prompt truncation** — 60-char preview.
10. **Hard-pin engines bypass user preference** — OS policy wins.
11. **Local handle cache invalidates on path change.**
12. **No retry logic** — single attempt + mock fallback.

### Known gaps

| Gap | Severity | PASS‑3 reference |
|---|---|---|
| **`_request_timeout` is NOT thread-safe** | High (when multi-worker uvicorn lands) | PASS‑3C B1 / PASS‑4 FIX‑H6 |
| **Founder default cross-user** — process-global affects all users | Documented design | PASS‑3A I26 / PASS‑3B B5 |
| **`_LOCAL_HANDLE_CACHE` cross-user** — shared model instance | Documented design | PASS‑3A I24 |
| **xAI handler mock-only** — in dispatch table but never wire-calls | Documented design | PASS‑3B C5 |
| **`set_founder_default_model` rejects aliases** — `"claude"` raises; canonical id required | Documented behaviour | PASS‑3A I17 |
| **`select_model` step 3 silent exception swallow** — `except Exception: pass` hides operator_state read failures | Low — defensive path | PASS‑3C N5 / PASS‑4 candidate |
| **Provider response shape brittleness** — semantic emptiness passes through if structure is valid | Medium | PASS‑3C B10 / PASS‑4 FIX‑M3 |
| **No retry / no provider failover** — single attempt + mock | Documented design |  |
| **Founder default not persisted across process restarts** — in-process only | Documented design | PASS‑3A I31 |

### Critical hardening targets (from PASS‑4)

| Fix | Target |
|---|---|
| **FIX‑H6** | `_PROVIDER_HTTP_TIMEOUT` → `contextvars.ContextVar` for thread-safety |
| **FIX‑M3** | Provider response shape validation — reject empty `text` |
| **FIX‑L5** | xAI handler honest mock-only branding — `logger.warning` at handler entry |
| **N1 mitigation** | Move `SUPPORTED_MODELS` + `is_valid_model` to a separate `model_constants.py` to dissolve the `operator_state ↔ model_router` lazy import |
| **V2 mitigation** | Persist founder default to `memory_vault` under namespace `founder_global.*` for multi-instance consistency |

None of these gaps are blocking. The router's core invariants — single
HTTP funnel, mock fallback on any failure, single model funnel through
`select_model` — are intact.

---

## Summary

`model_router.py` is the **single point of model selection and
provider dispatch** in the ClarityOS runtime. 964 lines, 12 public
functions, 1 outbound HTTP chokepoint (`_http_post_json`), 5 provider
handlers (4 real + 1 mock-only), 4-step precedence chain, deterministic
mock fallback on every failure mode.

The router owns **no operator state** (it reads but never writes),
**no vault data**, **no LLM SDK**, **no third-party HTTP library**.
Pure stdlib. Pure deterministic except where the real network meets
the real provider — and even then, failures degrade to deterministic
mock instead of bubbling errors.

The router is **production-current** (`ROUTER_VERSION =
"model_router.v57.1"`) and is the second-most-imported runtime module
after `memory_vault`.
