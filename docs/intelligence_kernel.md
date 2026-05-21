# Intelligence Kernel (`intelligence_kernel.py`)

## 1. Purpose and role

`intelligence_kernel.py` (v40, `KERNEL_VERSION = "kernel.v1.0"`) is the
**single coherent entry point** that unifies every non-HTTP reasoning
surface in ClarityOS into one module. Endpoints in `app.py` and the
macro scheduler in `elins_scheduler` route through this kernel; ESO
resolution, operator-state recording, S_ELINS QC, ELINS persistence,
audit logging, and model dispatch all happen here in one place.

The kernel sits **directly below the HTTP layer** and **above** every
other runtime concern: model routing, vault storage, operator-state,
ELINS pipeline, threads/projects, perplexity oracle, and the macro
scheduler. It owns no HTTP routes of its own — `app.py` is the only
HTTP entrypoint — and it owns no provider SDK or vault backend of its
own.

### Core invariants

1. **Single ESO funnel** — all ESO resolution goes through
   `_resolve_external_signal_mode` + `_maybe_fetch_eso`.
2. **Single model funnel** — all model resolution goes through
   `_resolve_model` → `model_router.select_model`.
3. **Single audit funnel** — every `run_*` calls
   `kernel_logging.log_kernel_run` in its `finally` block.
4. **S_ELINS QC always attached when ELINS succeeds.**
5. **Topic labels are analysis-derived, never raw text.**
6. **Mode override is persistent** — written to both `operator_state`
   and `users_store`.
7. **Macro_seq is strictly monotonic** — lock-guarded counter.
8. **`select_reasoning_mode` is a pure function.**
9. **The kernel never bubbles oracle/persistence/telemetry failures** —
   graceful degradation everywhere.

### Status

| File | Status | Reason |
|---|---|---|
| `intelligence_kernel.py` | **CURRENT** | 2,045 lines · 16 public entrypoints · 24 importers (5 production + 19 tests) |

### Implementation location

- **Source:** `intelligence_kernel.py` (2,045 lines).
- **Imports:** stdlib (`json`, `logging`, `re`, `time`, `datetime`,
  `typing`, `threading` lazy at line 2027) + ELINS subpackage (6
  modules) + 15 internal subsystems. No HTTP libraries, no LLM SDKs.

---

## 2. Public API surface (all `run_*` functions)

16 public entrypoints. Each is **deterministic with respect to the
persistence-layer state at call time**, modulo provider response
variance and wall-clock timestamps.

| Function | Line | Purpose |
|---|---|---|
| `run_c(user, input, *, mode="default", external_signal_mode=None)` | 251 | `#c` (comment) — routes to `comment_generator` |
| `run_G(user, input, *, runner, mode="default", external_signal_mode=None)` | 298 | `#G` (analysis) — `runner` is injected from `app.py` |
| `run_ELINS(user, text, *, region, external_signal_mode, domain_hint, kind, topic_hint, persist, update_indexes)` | 365 | Canonical ELINS run (v1 pipeline) |
| `run_regional_ELINS(user, region_code, *, topic_hint, external_signal_mode, persist)` | 482 | Regional ELINS (US/EU/MEA/APAC/Markets/Tech) |
| `run_macro_ELINS(system_user, *, now_ts, external_signal_mode)` | 579 | Macro pass: 1 global + 6 regional + macro_run record + entity-graph merge |
| `run_thread_message(user_id, thread_id, content, *, project_id=None)` | 801 | Thread turn — append user + assistant messages |
| `select_reasoning_mode(el, ins, tsi=None)` | 1071 | Pure mapping `(EL, INS, TSI) → mode label` |
| `summarize_thread(user_id, thread_id)` | 1159 | Generate or refresh a thread summary (v50) |
| `run_regression_first(...)` | 1256 | ProblemSolver REGRESSION_FIRST kernel task (v79) |
| `run_emotional_physics(user_id, text)` | 1494 | Structural-not-sentimental analysis (v52) |
| `run_elins_v2(...)` | 1600 | ELINS v2 — Path-C view (v53) |
| `run_manual_ingestion(...)` | 1695 | Manual document / feed entry (v54) |
| `run_feed_ingestion(...)` | 1766 | RSS / Atom feed ingestion (v54) |
| `run_ingestion_cycle(user_id)` | 1875 | Full ingestion cycle |
| `kernel_status()` | 1908 | Founder-facing static snapshot (no per-user fields) |
| `kernel_view_for_user(user_id)` | 1966 | Per-user `/me` embed (metadata only) |

### Module constants

| Name | Value | Purpose |
|---|---|---|
| `KERNEL_VERSION` | `"kernel.v1.0"` | Surfaced in `kernel_status` |
| `VALID_SIGNAL_MODES` | re-export from `operator_state` | ESO mode allow-list |
| `_RM_SCORE_HIGH` | `3.0` | EL/INS quadrant threshold |
| `_TSI_FORCE_STABILIZATION` | `40` | TSI gate (forced stabilization) |
| `_TSI_ALLOW_EXTENDED` | `80` | TSI gate (extended reasoning) |
| `SUMMARY_CONTEXT_MESSAGES` | `20` | Last-N cap for thread summary input |
| `SUMMARY_CONTEXT_CHAR_BUDGET` | `8_000` | Hard char ceiling for summary prompt |

---

## 3. ESO resolution boundary

The external signal oracle (ESO) provides macro-context signals from
Perplexity. The kernel funnels all ESO interaction through three
helpers.

### `_resolve_external_signal_mode(user, override) -> str` (line 71)

4-step precedence:

1. **Explicit override** — if `isinstance(override, str)` and in
   `VALID_SIGNAL_MODES = ("cloud_only", "cloud_perplexity")`.
2. **`users_store.get_user(user).external_signal_mode`** — the mirror
   layer (read first because regional ESO resolvers read here).
3. **`operator_state.get_operator_state(user).external_signal_mode`** —
   the canonical kernel-side source.
4. **Fallback `"cloud_only"`.**

### `_apply_signal_mode_override(user, override) -> None` (line 157)

Writes the override to **both** `operator_state.set_external_signal_mode`
**and** `users_store.update_user`. Documented dual source of truth —
see PASS‑3B B2. Required so the regional ESO resolver (which reads
`users_store` first) picks up the override immediately.

### `_maybe_fetch_eso(mode, *, region_code, user) -> Optional[dict]` (line 100)

| Condition | Behaviour |
|---|---|
| `mode != "cloud_perplexity"` | Return `None` (no oracle call) |
| `not region_code` | Return `None` |
| `perplexity_oracle.fetch_basin_signals` raises `ValueError` | Return `None` (unknown region) |
| Any other oracle failure | `_record_error(str(e))` + `logger.warning` + return `None` |
| Success | `perplexity_oracle.sanitize_eso(eso)` → tag `source ∈ {"mock", "perplexity"}` → return |

**Sanitisation contract:** strips HTML, drops body-style fields,
truncates strings to 2000 chars. Applied **before** any downstream
consumer sees the ESO.

### `_eso_source(mode, eso) -> str` (line 145)

Resolves the public `eso_source` tag for log lines: `"none"` /
`"mock"` / `"perplexity"`. Returned in every `log_kernel_run` call.

---

## 4. Model-selection funnel

### `_resolve_model(user, *, task, override=None) -> str` (line 180)

Thin wrapper around `model_router.select_model` that **records the
chosen model_id onto `operator_state.last_model_used`**. Pipeline:

1. `model_router.select_model(user, task=task, override=override)` →
   `model_id`.
2. On router failure → fallback to
   `model_router.TASK_DEFAULTS["ELINS"]` (defensive `try/except`).
3. If `user`: `operator_state.record_model_used(user, model_id)`.
4. If `model_id == model_router.LOCAL_MODEL_ID`:
   `operator_state.bump_local_model_usage(user)`.
5. Return `model_id`.

**Cross-module invariant (selected ≡ recorded):** the model_id
returned to the caller is always the model_id persisted onto
`operator_state`. No code path returns a model_id that wasn't
recorded.

Task buckets used by the kernel: `"c"`, `"G"`, `"ELINS"`, `"regional"`,
`"macro"`, `"entity"`, `"thread"`, `"thread_summary"`,
`"emotional_physics"`, `"regression_first"`. Each maps to a default
model_id in `model_router.TASK_DEFAULTS`.

---

## 5. ELINS pipeline (v1 + v2)

### v1 — Canonical ELINS via `run_ELINS` (line 365)

`run_ELINS(user, text, *, region, external_signal_mode, domain_hint,
kind, topic_hint, persist, update_indexes) -> dict`.

If `region` is given, delegates to `run_regional_ELINS`. Otherwise the
pipeline runs:

1. `_apply_signal_mode_override(user, external_signal_mode)`.
2. `_resolve_external_signal_mode(user, external_signal_mode)` →
   `resolved_mode`.
3. `_resolve_model(user, task="ELINS")` → `model_id`.
4. `standard_elins.generate_ELINS(text, domain_hint, user)` →
   `elins_obj`.
5. `_run_s_elins_qc(elins_obj)` → attach `elins_obj["qc"]`. **Key is
   always set** — either to the QC dict or to `None`. Never absent.
6. If `persist=True`: `elins_project.save_daily_run(user, elins_obj)`
   → `run_id`.
7. If `update_indexes=True`:
   `elins_project.update_global_primitive_index`,
   `update_domain_history`, `update_ep_baseline` → `baseline`.
8. `operator_state.record_elins_interaction(user, record_id,
   context={topic, region, kind, domain})` — **topic is
   analysis-derived** (`synthesis.top_primitive · domain`).
9. `kernel_logging.log_kernel_run(kind="run_ELINS", ...)` in
   `finally`.

Returns `{ok, elins, run_id, qc, baseline, model_id}`.

### S_ELINS QC

`_run_s_elins_qc(elins_obj) -> Optional[dict]` (line 216) calls
`standard_elins.generate_S_ELINS(elins_obj)`. Logs + returns `None` on
failure (caller continues with persistence regardless). Designed so
that the `qc` key is **never missing** from a successful ELINS
output — only `None` when QC itself failed.

### Regional ELINS via `run_regional_ELINS` (line 482)

Region-aware run for 6 basins: `US`, `EU`, `MEA`, `APAC`, `Markets`,
`Tech`. Same pre/post structure as `run_ELINS`, but:

- Uses `regional_elins.run_regional_elins(...)` instead of
  `standard_elins.generate_ELINS`.
- Reads `_maybe_fetch_eso(mode, region_code=region_code, user=user)`
  for region-specific oracle data.
- Persists via `elins_project` regional save path (idempotent same-day
  per v35 memory).

### v2 — Path-C view via `run_elins_v2` (line 1600)

ELINS v2 / Path-C is an **alternative ELINS construction path** that
uses `ELINS.elins_v2_view` as a view adapter. Introduced in v53. The
kernel exposes it as a separate entrypoint (`run_elins_v2`) rather
than a flag on `run_ELINS`, preserving the v1 pipeline contract
unchanged.

Path-C consumes the same `(user, text, ...)` shape but routes the
construction through `elins_v2_view` instead of `standard_elins`.
S_ELINS QC and persistence semantics are preserved.

---

## 6. Thread/project routing

### `run_thread_message(user_id, thread_id, content, *, project_id=None) -> dict` (line 801)

Append a user message, route through the model router, append the
assistant reply. Pipeline:

1. Validate `content` is a non-empty string (raises `ValueError`).
2. If `project_id` supplied:
   `threads_vault.get_thread_meta(user_id, thread_id)` (cheap
   pre-flight). Raises `KeyError` (→ 404 in `app.py`) on missing
   thread; raises `ValueError` if `project_id` mismatches the thread's
   stored project_id.
3. `threads_vault.append_message(user_id, thread_id, user_msg)` —
   user turn persisted.
4. `_resolve_project_routing(user_id, project_id)` →
   `(project_default, project_allowed)` from `projects_vault`.
5. `_resolve_model(user_id, task="thread", override=project_default)` →
   `model_id`.
6. `_apply_project_routing(model_id, project_default,
   project_allowed)` — reconciles router choice against project
   constraints.
7. If `project_default` was supplied and the final `model_id` differs,
   re-record via `operator_state.record_model_used` for telemetry
   parity.
8. `threads_vault.get_thread(user_id, thread_id)` → canonical
   transcript.
9. `_format_thread_context(messages, latest=content)` — last 8
   messages, 6 KB cap.
10. `model_router.route_request(model_id, prompt)` → assistant reply.
11. `threads_vault.append_message(user_id, thread_id, assistant_msg)`.
12. `kernel_logging.log_kernel_run(kind="thread", ...)`.

Returns `{meta, user_message, assistant_message, model_id}`.

### `_apply_project_routing(model_id, project_default, project_allowed) -> str` (line 782)

Reconciler matrix:

| Condition | Returned model_id |
|---|---|
| `project_default` is in `project_allowed` | `project_default` |
| Router choice is in `project_allowed` | router choice |
| Neither | `project_allowed[0]` |
| `project_allowed` is empty / None | router choice (pass-through) |

### `summarize_thread(user_id, thread_id) -> dict` (line 1159)

Generate or refresh a thread summary. Pipeline:

1. Pull transcript via `threads_vault.get_thread`.
2. `_format_summary_prompt(messages)` (line 1136) — SYSTEM-prefixed
   compact transcript prompt; last 20 messages, 8 KB cap.
3. `_resolve_model(user_id, task="thread_summary")`.
4. `model_router.route_request(model_id, prompt)`.
5. `threads_vault.update_thread_summary(...)` persists summary +
   `summary_ts_ms`.

Documented at line 1124–1133 in source.

---

## 7. Regression-first pipeline

### `run_regression_first(...)` (line 1256)

ProblemSolver REGRESSION_FIRST kernel task (v79). The kernel function
does not itself drive a model call directly — packets are emitted
upstream under the bundle's `system_prompt.md`, and this function
parses them through the canonical pipeline.

**Persistence layer:** chains and packets are stored via
`memory_vault` namespaces `regression_chains.*` (v77) and
`regression_packets.*` (v82). Each chain is one entry under
`regression_chains.{chain_id}`; the original packet that originated
the chain is stored under `regression_packets.{chain_id}`. First
packet wins (not overwritten on repeated `/packet` calls).

**Cross-module bridge:** `model_router.call_regression_first(packet,
*, user, model_id, store)` (model_router line 918) is the v79 task
helper that:

1. Resolves `model_id` via the standard precedence
   (`select_model(user, task="regression_first", override=model_id)`).
2. Lazy-imports `intelligence_kernel` (line 942 — explicit cycle
   break).
3. Delegates to `intelligence_kernel.run_regression_first(packet,
   user_id=user, model_id=resolved, store=store)`.

`TASK_DEFAULTS["regression_first"]` resolves to `openai:gpt-4o` per
`model_router` PASS‑1.

The `problem_solver` module owns the packet parser
(`analyze_packet`), the RegressionChain dataclass, and the chain
store; `chain_store.py` is built on `memory_vault`.

---

## 8. Emotional physics

### `run_emotional_physics(user_id, text) -> dict` (line 1494)

Structural-not-sentimental analysis (v52). Multi-layered JSON contract.
The kernel routes through `model_router` (task `"emotional_physics"`,
default `anthropic:claude-3.7`) and parses the model's JSON output.

### Supporting helpers

| Helper | Line | Purpose |
|---|---|---|
| `_emotional_physics_skeleton()` | 1487 | Deterministic skeleton dict — used as a fallback shape when the model output is unparseable |
| `_extract_json(text)` | 1437 | Best-effort JSON extraction from model output. Fence-tolerant (handles ```json blocks). Returns `(parsed_dict_or_None, error_or_None)` |

The function:

1. `_resolve_model(user_id, task="emotional_physics")`.
2. Builds a layered prompt against the v52 spec.
3. `model_router.route_request(model_id, prompt)`.
4. `_extract_json(response_text)` → structured dict or fallback.
5. If parsing fails: return `_emotional_physics_skeleton()` with
   `error` annotation; pipeline still succeeds (ok=True) per the
   "no graceful-degradation-bubbles" invariant.
6. `kernel_logging.log_kernel_run(kind="emotional_physics", ...)`.

Per v52 memory: *"multi-layered JSON contract; correctness +
coherence matter more than latency, so route to the deterministic-
reasoning default."* No vendor pinning beyond the task default —
users can override via `operator_state.preferred_model`.

---

## 9. Ingestion subsystem

### `run_manual_ingestion(...)` (line 1695)

Manual document / feed entry (v54). Caller supplies the text content
directly; ingestion bus writes the document into the user's ELINS
ingestion namespace.

### `run_feed_ingestion(...)` (line 1766)

RSS / Atom feed ingestion. Pulls latest entries from a configured
feed source via `ELINS.ingestion_bus`, normalises them, and writes
them into the ingestion namespace.

### `run_ingestion_cycle(user_id) -> dict` (line 1875)

Full ingestion cycle — typically driven from the macro scheduler or
a founder console action. Iterates registered feeds and runs
`run_feed_ingestion` for each.

**Persistence backbone:** `ELINS.ingestion_bus` (imported eager at
kernel module load) handles the actual ingestion writes. The bus is
backed by `memory_vault` like every other persistence path.

**Audit:** every ingestion run terminates with
`kernel_logging.log_kernel_run(kind="ingestion", ...)`.

---

## 10. Macro-ELINS pass

### `run_macro_ELINS(system_user, *, now_ts=None, external_signal_mode=None) -> dict` (line 579)

Daily orchestrator-driven pass that produces a global + 6 regional
ELINS plus a summary record. Called by `elins_scheduler`'s daemon
thread (lazy-booted; cadence defaults to 24h per v36 memory).

Pipeline:

1. `_apply_signal_mode_override(system_user, external_signal_mode)`.
2. `_resolve_external_signal_mode(system_user, external_signal_mode)`.
3. **Global ELINS:** `run_ELINS(system_user, _global_scenario_text(),
   persist=True, kind="macro_global", ...)`.
4. **Six regional ELINS:** for each of `US`, `EU`, `MEA`, `APAC`,
   `Markets`, `Tech` → `run_regional_ELINS(system_user, region_code,
   persist=True)`.
5. `elins_project.record_macro_run(now, run_id, summary)` — single
   macro-summary persistence call.
6. `elins_entity_graph.merge_run(...)` — auto-merges the entity graph
   after each macro pass (v37 boot).
7. `kernel_logging.log_kernel_run(kind="run_macro_ELINS", ...)`.

### Helpers

| Helper | Line | Purpose |
|---|---|---|
| `_global_scenario_text()` | 230 | Fixed scaffold text for the global pass — never persisted as user content; deterministic across runs |
| `_today_utc()` | 238 | ISO-formatted UTC date string |
| `_make_macro_run_id(now, seq=None)` | 242 | `f"macro_{ms}"` or `f"macro_{ms}_{seq}"` |
| `_next_macro_seq()` | 2033 | Strictly-monotonic counter; lazily allocated `threading.Lock` (line 2030) |

### Macro counter invariant

`_macro_seq` is a process-global incrementing int (line 2029),
lock-guarded via lazily allocated `_macro_seq_lock` (line 2030). Two
macro passes in the same millisecond receive distinct ids via the
`_{seq}` suffix. **Reset only by `_reset_for_tests`** — across process
restarts the counter starts over at 0.

---

## 11. Audit logging funnel

**Every `run_*` calls `kernel_logging.log_kernel_run` in its
`finally` block.** Universal contract:

```python
kernel_logging.log_kernel_run(
    kind="run_ELINS",
    user_id=user,
    external_signal_mode=resolved_mode,
    eso_source="none",
    duration_ms=(time.perf_counter() - started) * 1000.0,
    ok=ok,
    error=err,
    meta={...},
)
```

`kernel_logging.safe_meta` (per v41 memory) strips raw-text fields
from `meta` and truncates strings to 200 chars before logging.
Caller-discipline contract: `meta` is intentionally flexible to
capture per-call telemetry; the funnel adds defense-in-depth.

The audit funnel is the **single chokepoint** for kernel-level
observability. There is no per-run-type alternate log path. If the
funnel call is omitted in a future `run_*`, the kernel's audit
guarantee is broken.

### Selected reasoning mode (separate from audit)

`select_reasoning_mode(el, ins, tsi=None) -> str` (line 1071) is a
**pure function** that maps `(EL, INS, TSI)` to one of:

- `"stabilization"` (TSI < 40, or both EL/INS low)
- `"extended_reasoning"` (TSI > 80)
- `"grounding"` (EL ≥ 3, INS < 3)
- `"analysis"` (EL < 3, INS ≥ 3)
- `"structured_reflection"` (EL ≥ 3, INS ≥ 3)
- `"normal"` (unreachable in practice)

Constants: `_RM_SCORE_HIGH = 3.0`, `_TSI_FORCE_STABILIZATION = 40`,
`_TSI_ALLOW_EXTENDED = 80`. Documented at lines 1092–1094 as no I/O,
no module state, deterministic and reversible.

---

## 12. Determinism contract

| Property | Status |
|---|---|
| `run_*` deterministic w.r.t. persistence state at call time | ✅ Documented (line 26) |
| `select_reasoning_mode` is pure | ✅ Documented (line 1092–1094) |
| `_resolve_external_signal_mode` deterministic given inputs + (operator_state, users_store) state | ✅ |
| `_eso_source` is pure | ✅ |
| `_make_macro_run_id(now, seq)` is pure | ✅ |
| `_global_scenario_text()` is pure | ✅ |
| `_extract_json(text)` is pure (regex + JSON parse) | ✅ |
| Mock provider response `text` deterministic given prompt | ✅ Inherited from `model_router._mock_result` |
| Real provider response | ❌ Non-deterministic (temperature 0.2 reduces but does not eliminate model variance) |
| `_macro_seq` counter | ✅ Deterministic within a process; non-deterministic across processes |
| Wall-clock-embedded `ts` in persistence records | ❌ Non-deterministic (intentional — wall-clock is the audit signal) |
| `_make_macro_run_id` ms portion | ❌ Non-deterministic (wall-clock) |
| Macro pass scheduling | ❌ Non-deterministic across processes (per-process counter, per-process scheduler) |

---

## 13. Privacy boundaries

The kernel sits between three layers (HTTP, model providers, vault)
and is the **single point** where raw user input could leak into any
of those layers. Five privacy gates are enforced inside the kernel:

### G‑K1 — Analysis-derived topic labels (no raw input persisted)

Every `record_elins_interaction` call builds the `topic` field from
analysis output (`synthesis.top_primitive · domain`); every
`record_g_run` call builds it from `f"#G · pressure {round(p, 3)}"`.
**Raw user input (`text`, `input`, `content`) never enters
`operator_state`.**

### G‑K2 — ESO sanitisation at the kernel boundary

`_maybe_fetch_eso` calls `perplexity_oracle.sanitize_eso` on every
successful fetch (line 139). Downstream consumers (regional ELINS,
macro pass) never see an un-sanitised oracle response.

### G‑K3 — `kernel_logging.safe_meta` strips raw-text fields

The audit funnel's `meta` parameter is sanitised before logging.
Caller discipline + module-level scrubbing.

### G‑K4 — Length-capped prompts at the model boundary

`_format_thread_context` caps at last 8 messages / 6 KB.
`_format_summary_prompt` caps at last 20 messages / 8 KB. The kernel
never sends an unbounded prompt to `model_router`.

### G‑K5 — No raw input in `kernel_status` / `kernel_view_for_user`

Both functions return metadata-only views: counts, version strings,
last-activity timestamps, configured paths. Never raw input, never
session tokens, never API keys.

### Documented privacy gaps

- **`_strip_forbidden` blocklist enumeration** (in `operator_state`,
  not the kernel) — the kernel relies on this layer to scrub
  caller-side raw text. PASS‑3D gap G‑P1.
- **Migration path preserves un-stripped legacy entries** —
  `operator_state.migrate_operator_state_to_vault` deliberately
  doesn't scrub. PASS‑3D gap G‑P2.

---

## 14. Cross-module interactions

### Imports (production, eager)

```
ELINS.elins_project          ELINS.elins_v2_view (v53)
ELINS.forecast_engine        ELINS.ingestion_bus (v54)
ELINS.regional_elins         ELINS.standard_elins
comment_generator            elins_entity_graph
elins_scheduler_config       kernel_logging
local_model_runtime          memory_vault
model_router                 operator_state
perplexity_oracle            problem_solver
projects_vault               threads_vault
users_store
```

### Importers (24 total — 5 production + 19 tests)

- **Production:** `app.py`, `runtime_http.py`, `model_router.py` (lazy
  in `call_regression_first`), `elins_scheduler.py`,
  `personal_news_basin.py`, `el_ins/rollup.py`.
- **Tests:** every batch test from v40 onward + `el_ins/*` test files.

### No imports of

- `app.py` (uses callable injection for `#G`).
- Any intelligence-layer engine — `azimuth*`, `orchestrator_*`,
  `language_*`, `feedback_*`, `primitive_selection_engine`,
  `emotional_alignment_engine`, etc. **The intelligence layer is
  bypassed at the runtime.**
- Any LLM SDK (`anthropic`, `openai`, `google.generativeai`). All
  provider access goes through `model_router`.

### Cycle breaks

| Cycle | Break |
|---|---|
| `intelligence_kernel ↔ app.py` | `#G runner` is injected as a `Callable` parameter to `run_G` — zero import coupling |
| `intelligence_kernel ↔ model_router` | `model_router.call_regression_first` lazy-imports the kernel at line 942 |
| `intelligence_kernel ↔ operator_state` | Both eager — no cycle (state never imports kernel) |
| `intelligence_kernel ↔ memory_vault` | Both eager — no cycle (vault is the deepest leaf) |

---

## 15. Known guarantees and gaps

### Strong runtime guarantees

1. **Single ESO funnel** — every ESO interaction passes through two
   helpers, no bypass paths.
2. **Single model funnel** — `_resolve_model` is the only call site
   for `model_router.select_model` in production code.
3. **Single audit funnel** — every `run_*` has a `finally` block that
   calls `kernel_logging.log_kernel_run`.
4. **Topic labels are analysis-derived** — raw user input never
   reaches `operator_state` via the kernel.
5. **`select_reasoning_mode` is pure** — documented, test-asserted.
6. **`_macro_seq` is strictly monotonic per process** — lock-guarded
   counter; same-millisecond passes receive distinct ids.
7. **`#G runner` is injected, not imported** — exemplary cycle break.
8. **Graceful degradation everywhere** — oracle, persistence, and
   telemetry failures all degrade silently via `logger.warning`;
   only `ValueError` (validation) and `KeyError` (lookup) propagate
   to the HTTP layer.

### Known gaps

| Gap | Severity |
|---|---|
| **ESO mode dual source of truth** (operator_state + users_store mirror) — drift risk if one write succeeds and the other fails | Medium — PASS‑3B B2 |
| **`select_model` step 3 silently swallows `operator_state` failures** — `except Exception: pass` at line 302 hides backend issues | Medium — PASS‑3C N5 |
| **`kernel_logging.safe_meta` is downstream of caller discipline** — caller controls what enters `meta`; only post-construction scrub | Medium — PASS‑3D G‑K3 |
| **`_macro_seq_lock` has a brief TOCTOU window on first call** — lazily allocated lock | Low — PASS‑3C B2 |
| **Stale `azimuth_transition.py` module docstring** — claims "Phase 1 skeleton" but is Phase-3 implemented. Not in the kernel but in a module the kernel calls into | Low — PASS‑3B A3 |
| **Real provider response variance** — `run_*` is "deterministic w.r.t. persistence state" but real provider calls introduce non-determinism in the `text` field | Documented design |
| **Wall-clock-embedded `ts` in records** — same kernel inputs produce same content fields, but timestamps and ids differ across runs | Documented design |

### Critical gaps (escalated from PASS‑4)

| Gap | Severity | Where to fix |
|---|---|---|
| **`_strip_forbidden` 4-field enumerated blocklist** | High | `operator_state.py:140` — pattern-match suffix patterns (`*_text`, `*_body`, `*_content`, etc.) |
| **`migrate_operator_state_to_vault` preserves un-stripped legacy** | High | `operator_state.py:526–580` — add opt-in `scrub_legacy: bool = False` |
| **Per-user key rotation primitive missing** | High | `memory_vault.py` — new `rotate_user_key` function |
| **`_request_timeout` not thread-safe** | High | `model_router.py:395–416` — `contextvars.ContextVar` |

None of these gaps are inside `intelligence_kernel.py` itself — the
kernel relies on the upstream/downstream modules' guarantees. The
kernel's own invariants (ESO funnel, model funnel, audit funnel, topic
labels) are intact.

---

## Summary

`intelligence_kernel.py` is the **single coherent reasoning entry
point** for ClarityOS Cloud — 2,045 lines, 16 public `run_*` functions,
three single-funnel chokepoints (ESO / model / audit), and an
explicit no-back-import cycle break for `app.py`'s `#G` runner. It
owns no HTTP routes, no model provider SDKs, no vault backends — it
funnels through `app.py` (HTTP entry), `model_router` (provider
dispatch), `operator_state` (per-user state), and `memory_vault`
(persistence). Its determinism is real but bounded: pure helpers are
pure, but real provider calls and wall-clock timestamps introduce
variance by design.

The kernel is **production-current** (`KERNEL_VERSION = "kernel.v1.0"`)
and remains the deepest production-wired module in the runtime layer.
The intelligence-layer engines (`azimuth*`, `orchestrator_*`,
`language_*`, `feedback_*`) are **not** reached from the kernel —
they're production-dormant per their canon docs.
