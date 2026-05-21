# Emotional Physics

## Purpose

`emotional_physics` is a kernel-resident, LLM-mediated structural
analysis task introduced in v52. Given user-supplied text, it returns
a strict 4-field structured JSON object describing the situation's
field curvature, edge pressure, relational primitives, and external
expression.

It is **not** sentiment analysis, **not** ERA, and **not** a general
emotional reasoning engine. It is a single deterministic reasoning
mode implemented inside `intelligence_kernel.py` and exposed through
one authenticated HTTP route.

The subsystem guarantees:

- exactly one LLM call per invocation
- strict 4-key output schema
- graceful degrade on malformed model output (never 5xx)
- no persistence, no state mutation, no vault writes
- stable output shape for downstream consumers

## Implementation location

- **Host file:** `intelligence_kernel.py`
- **Block span:** lines 1320–1594 (contiguous v52 block)
- **No standalone module file.** The reasoning mode lives in the
  kernel as an ordinary Python function (per `ARCHITECTURE.md`:
  OS-level reasoning modes go in the kernel, not as skill manifests).
- **Version anchor:** introduced v52.
- **Non-runtime bundle:** `skills_export/emotional_physics/` contains
  specification material (manifest, prompt drafts, schemas, examples).
  ClarityOS **never imports from `/skills_export/`** — the inline
  prompt at line 1352 is the runtime source of truth.

### Public symbols (3)

- `EMOTIONAL_PHYSICS_TASK: str` (line 1332) — task key for
  `model_router.TASK_DEFAULTS`; value `"emotional_physics"`.
- `EMOTIONAL_PHYSICS_INPUT_CHAR_CAP: int` (line 1346) — silent
  truncation cap on user input; value `6_000`.
- `run_emotional_physics(user_id: str, text: str) -> dict` (line
  1494) — the kernel entry point.

### Private symbols (6)

- `_EMOTIONAL_PHYSICS_KEYS: tuple` (line 1337) — 4-tuple of required
  output keys: `("field_curvature", "edge_pressure",
  "relational_primitives", "external_expression")`.
- `_EMOTIONAL_PHYSICS_PROMPT: str` (line 1352) — inline LLM system
  prompt embedding the full 4-layer JSON schema. The runtime source
  of truth.
- `_FENCE_RE: re.Pattern` (line 1431) — markdown-fence regex.
- `_BRACE_RE: re.Pattern` (line 1434) — first-brace-block regex.
- `_extract_json(text) -> (Optional[dict], Optional[str])` (line
  1437) — 3-strategy fence-tolerant JSON parser; never raises.
- `_emotional_physics_skeleton() -> dict` (line 1487) — empty 4-key
  skeleton `{k: {} for k in _EMOTIONAL_PHYSICS_KEYS}` for degrade.

## Data model

### Input

```python
{"text": str}    # required, non-empty after strip
```

- `text` is silently truncated to `EMOTIONAL_PHYSICS_INPUT_CHAR_CAP`
  (6000) characters before prompt construction.
- Empty, whitespace-only, or non-string input is rejected at the HTTP
  layer with status 400; the kernel function raises `ValueError` for
  the same conditions when called directly.

### Output

`run_emotional_physics` always returns a dict with this shape:

```python
{
    "field_curvature":        dict,    # {} when missing/invalid
    "edge_pressure":          dict,
    "relational_primitives":  dict,
    "external_expression":    dict,
    "_meta": {
        "model_id":    str,             # resolved model
        "ts_ms":       int,             # epoch milliseconds
        "parse_error": str | None,      # None on success, str on degrade
    },
}
```

### Degrade behavior

Two distinct degrade paths, both returning HTTP 200:

1. **Full parse failure** — model output is not valid JSON, or is
   JSON but not a dict (e.g. a top-level array). All four top-level
   keys are present with value `{}`; `_meta.parse_error` is a
   non-empty string. Pinned by
   `test_run_emotional_physics_graceful_degrade_on_garbage`.
2. **Partial response** — parse succeeds but one or more required
   keys are missing or not dicts. Present keys are populated with
   their dict values; missing keys remain as `{}` from the skeleton;
   `_meta.parse_error` lists the missing keys (e.g.
   `"missing or invalid keys: relational_primitives,external_expression"`).
   Pinned by `test_run_emotional_physics_partial_response_flags_missing`.

The contract is load-bearing: parse failures **never** produce 5xx.

## APIs / entrypoints

### Kernel function

`run_emotional_physics(user_id: str, text: str) -> dict` —
intelligence_kernel.py:1494.

Behaviour:

1. Validate text (raise `ValueError` on empty/whitespace/non-string).
2. Truncate to `EMOTIONAL_PHYSICS_INPUT_CHAR_CAP` silently.
3. Resolve model via `_resolve_model(user_id, task=EMOTIONAL_PHYSICS_TASK)`.
4. Build prompt: `_EMOTIONAL_PHYSICS_PROMPT + "\nSITUATION:\n" + cleaned`.
5. Dispatch via `model_router.route_request(model_id, prompt)`.
6. Parse with `_extract_json`; fill skeleton on failure, populate
   present keys on partial success.
7. Emit one `kernel_logging.log_kernel_run` entry.
8. Return the 4-key body + `_meta` dict.

### HTTP route

`POST /me/emotional_physics/analyze` — app.py:12073.

- **Auth:** `Depends(require_session)` — session required.
- **Request model:** `V52EmotionalPhysicsRequest { text: str }`.
- **Status codes:**
  - `200` — success or graceful degrade
  - `400` — empty/whitespace/non-string text OR kernel `ValueError`
  - `401` — unauthenticated
  - **never `5xx`** for parse failures
- **Response:** the kernel return dict, verbatim.

## Integration points

### Model router

- **Task default:** `TASK_DEFAULTS["emotional_physics"] =
  "anthropic:claude-3.7"` (model_router.py:123).
- Full precedence chain applies: explicit override → founder default
  → `operator_state.preferred_model` → task default. See
  [docs/model_router.md](model_router.md) for the resolution chain.

### Kernel helpers

- `_resolve_model(user_id, task)` (kernel:180) — handles model
  selection and operator_state telemetry (`record_model_used`,
  `bump_local_model_usage`). These writes happen **outside** the
  emotional_physics block.
- `_resolve_external_signal_mode(user_id, None)` (kernel:71) — used
  only to populate the `external_signal_mode` log field.

### State / persistence

- **No direct `operator_state.*` calls** inside the v52 block.
  Telemetry writes happen via `_resolve_model`.
- **No `memory_vault` access** anywhere.
- **No file I/O** anywhere. Inline prompt is the only prompt source.

### Logging

Exactly one `kernel_logging.log_kernel_run(...)` call per invocation,
with:

- `kind="emotional_physics"`
- `external_signal_mode` (derived from `_resolve_external_signal_mode`)
- `eso_source="none"` (hardcoded — emotional_physics never queries an
  external signal oracle)
- `duration_ms` (from `time.perf_counter()` delta)
- `meta` containing `model_id`, `input_len`, `raw_len`, `parse_error`
- `error=parse_error`

### Tests

`tests/test_v52_emotional_physics.py` — 421 lines, 21 tests, all
directly pinning the v52 block:

- `test_task_defaults_has_emotional_physics` (1) — task registration
- `test_extract_json_*` (7) — direct / fenced / bare-fence /
  prose-wrapped / malformed / empty / array-rejected
- `test_run_emotional_physics_*` (7) — happy path, fence tolerance,
  full-degrade, partial-response missing-keys, empty-text raises,
  input cap, kernel log emit
- `test_endpoint_analyze_*` (4) — HTTP happy, HTTP degrade, 400, 401
- `test_me_capabilities_lists_emotional_physics` (1)
- `test_health_version_4_x` (1)

## Invariants

1. **Char cap.** Input is truncated to
   `EMOTIONAL_PHYSICS_INPUT_CHAR_CAP` (6000) before prompt
   construction; truncation is silent — no warning, no error.
2. **Schema.** Output always contains the 4 keys in
   `_EMOTIONAL_PHYSICS_KEYS`; each value is a dict (`{}` when missing
   or invalid).
3. **Prompt.** The inline `_EMOTIONAL_PHYSICS_PROMPT` is the only
   runtime prompt; no `/skills_export/` reads.
4. **Parsing.** `_extract_json` never raises; strategies (in order)
   are direct `json.loads` → fence-stripped → first-brace-block;
   arrays and other non-dicts are rejected.
5. **Degrade.** Full failure → all 4 keys = `{}`; partial response →
   present keys populated, missing keys = `{}`; `_meta.parse_error`
   non-empty in both cases; HTTP status stays 200.
6. **Routing.** Exactly one `model_router.route_request` call per
   invocation; model id resolved via `_resolve_model`.
7. **Logging.** Exactly one structured log entry per invocation,
   carrying `kind`, `model_id`, `duration_ms`, `parse_error`.
8. **State.** No direct `operator_state` writes, no vault access,
   no file I/O within the v52 block.

## Non-goals

`emotional_physics` is **not**:

- the ERA subsystem (`emotional_alignment_engine.py`) — separate
  module, separate framing, pure deterministic (no LLM);
- a general emotional reasoning engine — strict 4-layer schema only;
- a state machine — single request → single response;
- a persistence layer — nothing is stored;
- a multi-turn system — each call is independent;
- a dashboard or aggregator — produces structural analysis, not
  metrics;
- a router or provider interface — delegates dispatch to
  `model_router`.

## Fiction removed

This subsystem had no prior canonical doc, so no drift existed when
this document was first written. The following constructs are
explicitly not present in the v52 block and must not be inferred:

- **The skills bundle is not the runtime prompt.** The bundle at
  `skills_export/emotional_physics/prompts/system_prompt.txt`
  carries a different 5-key schema (`summary`, `forces`,
  `constraints`, `trajectories`, `risk_zones`). The runtime ignores
  it entirely; the inline 4-key prompt at kernel:1352 is
  authoritative. The bundle remains in the repo as
  specification/template material; runtime behaviour follows the
  inline prompt.
- **The skeleton does not enforce per-layer shapes.** Each missing
  key defaults to `{}`, not to a per-layer mini-schema. The detailed
  per-layer structure is encoded only in the prompt; the kernel does
  not validate it.
- **The subsystem does not read or write `operator_state`
  directly.** Telemetry writes (`record_model_used`,
  `bump_local_model_usage`) happen via `_resolve_model`, outside the
  v52 block.
- **The subsystem never makes multiple LLM calls per invocation.**
  Exactly one `model_router.route_request` call, always.
- **The subsystem does not read any file at runtime.** No prompt
  loading, no schema loading, no `/skills_export/` reads.
- **The subsystem does not retry.** A provider error inside
  `route_request` is downgraded to a deterministic mock by the
  router; the resulting (possibly mock) text is parsed normally.
- **The subsystem does not persist results.** No vault writes, no
  store calls. The output is returned to the caller and forgotten.

Only the behaviour, fields, and integrations described in this
document are present in the code; the verified surface is pinned by
21 tests in `tests/test_v52_emotional_physics.py`.
