# V79 — Wire regression_first into intelligence_kernel and model_router

Status: ✅ Ready
Backend version: `4.19` → `4.20`
Build: `20260514140000` → `20260514150000`

> Backend plumbing only. **No HTTP changes** — the
> `/me/regression_first/packet` endpoint and UI surfaces land in V80.
> Existing V76 routes (`/start`, `/step`, `/get`, `/list`, `/close`,
> `/tag`) are untouched.

---

## What this pass ships

### Scope

Make `regression_first` a first-class task in the intelligence
kernel and model router. The task already had an HTTP surface (V76),
persistence (V77), and timeline emission (V78) — V79 adds the
discoverability + telemetry layer so the rest of the kernel can call
into the pipeline the same way it calls `run_thread_message`,
`summarize_thread`, `run_emotional_physics`, etc.

### model_router

* New `TASK_DEFAULTS["regression_first"] = "anthropic:claude-3.7"`.
  Same default as `G` / `ELINS` / `thread` / `emotional_physics` —
  the bundle prompt (`skills_export/regression_first/system_prompt.md`)
  is written for Claude 3.7.
* New `call_regression_first(packet, *, user=None, model_id=None, store=None) -> dict`.
  Thin facade that resolves `model_id` via the standard
  `select_model` precedence (explicit override → founder default →
  user `preferred_model` → `TASK_DEFAULTS`) and dispatches to
  `intelligence_kernel.run_regression_first`.
* `select_model` automatically picks up `regression_first` via the
  same plumbing used for every other task — no special-casing.

### intelligence_kernel

* New `run_regression_first(packet, *, user_id=None, model_id=None, store=None) -> dict`.
* Behaviour:
  * Resolves `model_id` via `_resolve_model(user_id, task="regression_first", override=model_id)`
    so `operator_state.last_model_used` stays in sync with every
    other run.
  * Calls `problem_solver.analyze_packet(packet, store=store)`.
  * Emits a structured `kernel_logging.log_kernel_run` line with
    `kind="run_regression_first"` and `meta = {model_id, chain_id,
    regression_required, classification}`.
  * Returns `{packet, chain, model_id, ok}`.
* Graceful degrade: malformed packets return `ok=False` with `packet`
  and `chain` both `None`. Same posture as `run_emotional_physics`.
  Never raises.
* Does **not** drive an LLM call itself — packets are already emitted
  upstream under the canonical bundle prompt. The model_id is
  resolved purely for telemetry and downstream V80 inference
  routing.

### Storage

Storage is fully pluggable via `store=`. The kernel defaults to
`problem_solver.DEFAULT_STORE` (in-memory) when no store is
supplied. The V80 endpoint will pass
`VaultBackedRegressionChainStore(user_id)` through; V79 doesn't add
any new endpoint, so vault wiring stays untouched.

---

## Endpoints

| Method | Path                                          | Status                          |
|--------|-----------------------------------------------|---------------------------------|
| —      | (none added)                                  | V80 will add `/packet`          |

`TestNoHttpChange` locks this — V79 does not register
`/me/regression_first/packet` and the existing V76 routes are still
present.

---

## Test summary

| Suite                                             | Tests | Status |
|---------------------------------------------------|-------|--------|
| `tests/test_v79_regression_first_task.py`         | 22    | ✅ new |
| `tests/test_v40_intelligence_kernel.py`           | ~30   | ✅     |
| `tests/test_v44_model_router.py`                  | ~30   | ✅     |
| `tests/test_problem_solver.py`                    | 84    | ✅     |
| `tests/test_regression_first_endpoints.py`        | 27    | ✅     |
| `tests/test_regression_first_vault_timeline.py`   | 29    | ✅     |
| `tests/test_el_ins_analyzer.py`                   | 33    | ✅     |
| `tests/test_el_ins_timeline.py`                   | ~30   | ✅     |
| `tests/test_v28_endpoints.py`                     | ~70   | ✅ (4.19 → 4.20) |
| `tests/test_v51_projects.py`                      | 40    | ✅ (4.19 → 4.20) |
| `tests/test_v53_elins_v2.py`                      | —     | ✅ (4.19 → 4.20) |
| `tests/test_v54_ingestion.py`                     | —     | ✅ (4.19 → 4.20) |
| `tests/test_membership_confirm.py`                | 6     | ✅     |
| **Full sweep**                                    | **486** | **✅** |

### Test classes — V79 suite

| Class                       | Coverage                                                                                                  |
|-----------------------------|-----------------------------------------------------------------------------------------------------------|
| `TestTaskDefaults`          | `TASK_DEFAULTS["regression_first"]` registered; `select_model` precedence (default / explicit / founder / preferred). |
| `TestRunRegressionFirst`    | Happy path dispatches `analyze_packet`; injected store roundtrip; default in-memory store fallback; `last_model_used` recorded; explicit model override threaded through; graceful degrade on malformed packet + non-dict input; `regression_required=False` → no chain; `kernel_logging.log_kernel_run` emitted with correct meta. |
| `TestCallRegressionFirst`   | `call_regression_first` resolves model via TASK_DEFAULTS; explicit override; unknown override raises; user `preferred_model` wins; pass-through `store=`; router helper proxies to kernel (spy via monkeypatch). |
| `TestNoHttpChange`          | `/me/regression_first/packet` is NOT registered; all 6 V76 routes still present. |

---

## Files touched

```
model_router.py                                            (+ TASK_DEFAULTS["regression_first"]
                                                            + call_regression_first(packet, *, user, model_id, store))

intelligence_kernel.py                                     (+ import problem_solver
                                                            + run_regression_first(packet, *, user_id, model_id, store))

tests/test_v79_regression_first_task.py                   (new — 22 tests across 4 classes)
tests/test_v28_endpoints.py                                (version 4.19 → 4.20)
tests/test_v51_projects.py                                 (version 4.19 → 4.20)
tests/test_v53_elins_v2.py                                 (version 4.19 → 4.20)
tests/test_v54_ingestion.py                                (version 4.19 → 4.20)
tests/test_regression_first_endpoints.py                   (version 4.19 → 4.20)

app.py                                                     (/health 4.19 → 4.20)
BUILD_VERSION                                              20260514140000 → 20260514150000
V79_READINESS.md                                          (new)
```

---

## Architecture invariants verified

* **No HTTP surface change.** `TestNoHttpChange::test_no_new_regression_first_packet_route`
  asserts `/me/regression_first/packet` is NOT in `app.routes` and
  all 6 V76 routes still are.
* **Kernel-router parity.** Both `intelligence_kernel.run_regression_first`
  and `model_router.call_regression_first` resolve model_id via the
  same `select_model` plumbing and pass through `store=` identically.
* **Telemetry parity.** Every `run_regression_first` call emits a
  `kernel_logging.log_kernel_run` line with `kind="run_regression_first"`
  + `model_id` + `chain_id` + `regression_required` +
  `classification` — same shape as `run_thread_message` /
  `summarize_thread` / `run_emotional_physics`.
* **Storage stays pluggable.** Kernel never imports `memory_vault`
  to read chains; only the V77 endpoint helper does. V79 default
  store remains `problem_solver.DEFAULT_STORE` (in-memory).
* **Graceful degrade.** Malformed packets return
  `{packet: None, chain: None, model_id: <resolved>, ok: False}` —
  never raises. Locked by
  `TestRunRegressionFirst::test_graceful_degrade_on_*`.
* **No skills_export import.** The kernel calls
  `problem_solver.analyze_packet` which loads the bundle prompt as
  plain text. No new path bypasses this.

---

## What's still pending

* **V80 — packet endpoint + surfaces.** Adds
  `POST /me/regression_first/packet` (calls `call_regression_first`
  under the hood) plus web cockpit panel + phone screen + desktop
  consumer.
* **V81+ — onward.** Per V77/V78 readiness, no other regression_first
  units planned beyond V80.
