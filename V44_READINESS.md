# V44 Readiness — Multi-model router + kernel-level model selection

Status: ✅ Ready
Backend version: `4.0`
Router version: `model_router.v44.1`
Build: `20260507600000`

---

## What v44 ships

A central model-routing surface that every kernel `run_*` consults
before executing. The router resolves a `model_id` from a precedence
chain (explicit override → founder default → user `preferred_model` →
task default), guards real provider calls behind env keys, and emits
a deterministic mock payload when keys are absent so the rest of the
system can run offline. Each kernel run records the selected
`model_id` in its result + structured log line + the user's
`operator_state.last_model_used`.

Founders can set a global default model that overrides per-user
preferences; users can pick their own preferred model from the
settings surfaces (web + phone). The router catalogue is fixed at
six entries (five named providers + the `auto` sentinel) and lives
beside the existing kernel logging / billing config layers.

---

## Files added / changed

### New
- `model_router.py` — `select_model`, `route_request`, `parse_provider`,
  `get_model_status`, `get_router_status`, `get_founder_default_model`,
  `set_founder_default_model`, mock provider handlers.
- `web/src/components/settings/ModelPreferences.tsx`
- `web/src/components/founder/models/FounderModelStatusPanel.tsx`
- `phone/app/model_preferences.tsx`
- `tests/test_v44_model_router.py` — 39 tests.
- `V44_READINESS.md` (this file).

### Modified
- `operator_state.py`:
  - `_default_state` adds `preferred_model: None`, `last_model_used: None`.
  - `_normalise` accepts string values for both fields.
  - `update_operator_state` accepts `preferred_model` / `last_model_used`
    in patches.
  - New `set_preferred_model(user_id, model_id)` (validates against
    `model_router.SUPPORTED_MODELS`) + `record_model_used(user_id, model_id)`.
- `intelligence_kernel.py`:
  - Imports `model_router`.
  - New `_resolve_model(user, *, task, override)` helper that calls
    `model_router.select_model` and persists onto
    `operator_state.last_model_used`.
  - All five `run_*` paths resolve `model_id`, attach it to their
    result + their `kernel_logging.log_kernel_run` meta dict.
  - `kernel_status()` includes a `models` block (router status).
  - `kernel_view_for_user()` surfaces `preferred_model` +
    `last_model_used`.
- `app.py`:
  - Imports `model_router`.
  - New `POST /me/operator_state/model` (auth, validates).
  - New `GET /founder/models/status` (founder).
  - New `POST /founder/models/override` (founder, accepts null to clear).
  - `model_router` capability advertised on `/me`.
  - Backend version `4.0`; root listing extended.
- `web/src/lib/api.ts` — `V44ModelId`, `V44_MODEL_IDS`, `V44RouterStatus`,
  `meOperatorStateModel`, `founderModelsStatus`, `founderModelsOverride`.
- `web/src/components/founder/FounderDashboard.tsx` — embeds
  `FounderModelStatusPanel`.
- `web/src/routes/Account.tsx` — embeds `ModelPreferences`.
- `phone/lib/api.ts` — same v44 types/helpers as web.
- `phone/app/_layout.tsx` — register `model_preferences` stack screen.
- `phone/app/settings.tsx` — link to `model_preferences`.
- `tests/conftest.py` — reset hook for `model_router._reset_for_tests`.
- `tests/test_v28_endpoints.py` — health version `4.0`.
- `BUILD_VERSION` — `20260507600000`.

---

## Public API

```python
SUPPORTED_MODELS = (
    "openai:gpt-4.2",
    "anthropic:claude-3.7",
    "google:gemini-2.0",
    "xai:groq-llama",
    "local:llama3.1",
    "auto",
)

select_model(user, *, task, override=None)            -> model_id
route_request(model_id, prompt, *, temperature=0.2,
              max_tokens=4096)                        -> dict
parse_provider(model_id)                              -> "openai"|...|"auto"

get_model_status()                                    -> dict
get_router_status()                                   -> dict
get_founder_default_model() / set_founder_default_model(model_id)
```

### Routing rules (deterministic)

1. Explicit `override` (must be valid + not `"auto"`).
2. Founder global default (set via `/founder/models/override`).
3. `operator_state.preferred_model` (must be valid + not `"auto"`).
4. Task fallback (`TASK_DEFAULTS[task]`):
   - `c` → `xai:groq-llama` (fast)
   - `G` / `ELINS` / `regional` / `forecast` / `macro` / `entity`
     → `anthropic:claude-3.7` (deterministic reasoning)

`auto` is a sentinel — it never reaches `route_request` as the
selected id; the router falls through. Tests assert this.

---

## Provider env vars

```
CLARITYOS_OPENAI_KEY        — openai:*
CLARITYOS_ANTHROPIC_KEY     — anthropic:*
CLARITYOS_GEMINI_KEY        — google:*
CLARITYOS_XAI_KEY           — xai:*
CLARITYOS_LOCAL_MODEL_PATH  — local:*
```

When a key is absent the matching provider returns a deterministic
mock payload (`{"text": "[mock <model_id>] <prompt[:60]>", "mock":
True, ...}`). This keeps the surrounding system runnable + tests
deterministic without network access.

---

## API surface

### `POST /me/operator_state/model` (auth)
```jsonc
{ "preferred_model": "anthropic:claude-3.7" }   // or null/"" to clear
```
Validates against `SUPPORTED_MODELS`. Returns the updated operator
state.

### `GET /founder/models/status` (founder)
```jsonc
{
  "ok": true,
  "router": {
    "version":               "model_router.v44.1",
    "supported_models":      [...],
    "task_defaults":         { "c": "xai:groq-llama", ... },
    "founder_default_model": "anthropic:claude-3.7" | null,
    "providers": {
      "openai":    { "configured": true|false },
      "anthropic": { "configured": true|false },
      "gemini":    { "configured": true|false },
      "xai":       { "configured": true|false },
      "local":     { "configured": true|false }
    }
  }
}
```

### `POST /founder/models/override` (founder)
```jsonc
{ "default_model": "anthropic:claude-3.7" }   // or null to clear
```
Sets a process-wide default. Cleared value falls back to per-user
preferences + task defaults. Validates against `SUPPORTED_MODELS`.

### `/me` additions
```jsonc
"intelligence_kernel": {
  ...,
  "preferred_model": "anthropic:claude-3.7",
  "last_model_used": "anthropic:claude-3.7"
}
```

---

## Kernel observability

Every `run_*` now emits its kernel log line with `meta.model_id`:

```jsonc
{
  "kind":        "run_ELINS",
  "user_id":     "alice",
  "duration_ms": 4.2,
  "ok":          true,
  "meta": {
    "kind":     "preview",
    "ep_mean":  0.12,
    "has_eso":  false,
    "persist":  false,
    "model_id": "anthropic:claude-3.7"
  },
  ...
}
```

The selected `model_id` is also persisted onto
`operator_state.last_model_used` after each run, so `/me` and the
phone settings surface can show "last model used" without a second
round-trip.

---

## UI

### Web
- **Account → Model preferences** — dropdown of supported models +
  current preference + last model used + per-provider configured pills.
  Writes via `POST /me/operator_state/model`.
- **Founder console → Model status panel** — provider READY/NO KEY
  pills, founder default override (with a clear-to-none option), and
  the current task-default mapping.

### Phone
- **`model_preferences.tsx`** — pill row of model ids, status card
  (current pref + last model used + founder default if active), and
  a provider-status list (when `/founder/models/status` succeeds; the
  page still works for non-founder users by hiding the providers
  card).
- **`settings.tsx`** gets a "Model preferences" entry beneath the
  intelligence-profile entry.

---

## Tests

```
tests/test_v44_model_router.py — 39 tests, all pass
Full suite — 555 passed, 0 failed
```

Coverage:
- Routing precedence: explicit override > founder default > user pref >
  task default. `auto` sentinel falls through.
- `route_request` happy path (mock fallback) + correct provider call
  via monkey-patched handler + unknown model rejection +
  `auto` defence-in-depth + mock determinism.
- Provider status reflects env keys; default state is
  all-unconfigured.
- `operator_state` model fields: defaults None; setter validates;
  cleared on null; `record_model_used` round-trip.
- Kernel integration: every `run_*` returns `model_id`; kernel log
  carries `meta.model_id`; `last_model_used` persisted;
  `kernel_view_for_user` exposes both fields; `kernel_status` includes
  the `models` block.
- Endpoint contracts: `POST /me/operator_state/model` happy +
  null-to-clear + bad-model 400; `GET /founder/models/status` shape +
  founder gate; `POST /founder/models/override` round-trip + clear-by-null
  + bad-model 400 + founder gate.
- `/me` exposes `preferred_model` + `last_model_used` after a kernel
  run; advertises `model_router` capability.

All tests run in mock mode (no real HTTP). The "live" path is
exercised via monkey-patching `_PROVIDER_HANDLERS` to verify dispatch.

---

## Notes / follow-ups

- The kernel doesn't yet feed prompts into the LLM providers — the
  ELINS / forecast / macro paths are deterministic Python
  pipelines. v44 is the routing + selection plumbing; future passes
  will add prompt assembly and feed `route_request(...)` outputs back
  into kernel decisions.
- Founder override is an in-process value. For multi-instance
  deployments it should move into a small Firestore key/value store
  alongside `elins_scheduler_config`. The endpoint shape will not
  change.
- Pre-v44 surfaces are unchanged. The `model_id` field on `run_*`
  results is purely additive; older clients that ignore it continue
  to work.
