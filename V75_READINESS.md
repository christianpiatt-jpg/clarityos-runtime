# V75 — ProblemSolver.REGRESSION_FIRST (Backend Kernel + Skills_Export Bundle)

Status: ✅ Ready (backend kernel only — no endpoint wiring this pass)
Backend version: `4.17` (unchanged — no `/health` behavior shift)
Build: `20260514100000` (bumped from `20260513190000`)

---

## What this pass ships

### Scope (founder-confirmed)

* **Scope chosen:** *Backend kernel only* — `problem_solver/`
  kernel module + `skills_export/regression_first/` bundle + pytest
  suite. **No** endpoints, **no** `app.py` changes, **no**
  `intelligence_kernel` wiring, **no** UI surfaces. Endpoint/UI
  wiring arrives in its own follow-up unit.
* **Invocation envelope:** Both an *explicit* operator-driven path
  AND an *auto_trigger* path are supported through the kernel API
  via the `source` parameter, so when the wiring unit lands it can
  plug into either entry point without re-shaping the kernel.

### Architectural framing

The founder's V75 instruction packet was written in
manifest/protocol/interpreter-binding language. Per
[`ARCHITECTURE.md`](ARCHITECTURE.md) (locked 2026-05-07), ClarityOS
runtime cannot load skill manifests or branch on plugin presence.
The clean fit is the **EL/INS precedent** ([el_ins/](el_ins/) kernel
module + [skills_export/el_ins/](skills_export/el_ins/) bundle) — and
the founder's spec is literally an extension of EL/INS §4 "Trigger
regression to roots." That's the home V75 took.

### Backend

Net-new `problem_solver/` package, sibling to `el_ins/`:

```
problem_solver/
  __init__.py                 (re-exports + __all__)
  regression_first.py         (deterministic chain + LLM coercer + state machine + analyze_packet)
  auto_trigger.py             (pure cue detector + extract_problem + CUE_WORDS / CUE_PHRASES)
```

#### Public surface (kernel)

| Symbol                             | Role                                                                    |
|------------------------------------|-------------------------------------------------------------------------|
| `build_regression_chain(problem, …)` | Generate + persist a stateful chain. `provider_mode` ∈ {llm, deterministic, auto}, `source` ∈ {explicit, auto_trigger}. |
| `record_finding(chain_id, idx, status, notes)` | Operator finding for one layer. `status` ∈ {verified, failed}. Validates everything. |
| `summarize_root_cause(chain_id, *, surgical_fix=None)` | Gated — raises until every layer carries a finding. Requires `surgical_fix` when at least one layer failed. |
| `get_chain(chain_id)` / `list_chains()` | Read / list (newest-first). Raises `KeyError` on unknown id. |
| `analyze_packet(raw, *, problem=None, source="auto_trigger", build_chain=True)` | Parse the canonical unified packet emitted by Claude under the bundle prompt. Optionally builds + persists a stateful chain from the embedded `regression_chain` skeleton. |
| `should_auto_trigger(text, *, el_ins_result=None)` | Pure detector: cue word/phrase present AND (no EL/INS supplied OR EL/INS classified as `high_el`). |
| `extract_problem(text)`            | Normalises whitespace; future hook for richer extraction.               |

#### Constants

* `PROTOCOL_NAME = "ProblemSolver.REGRESSION_FIRST"`
* `PROVIDER_MODES = ("llm", "deterministic", "auto")`
* `SOURCES = ("explicit", "auto_trigger")`
* `LAYER_STATUSES = ("pending", "verified", "failed")`
* `CHAIN_STATES = ("awaiting_verification", "ready_for_root_cause", "root_cause_identified")`
* `CLASSIFICATIONS = ("emotion-dominant", "balanced", "structure-dominant")` — packet vocabulary
* `CUE_WORDS` — frozenset of 22 single-word problem cues
* `CUE_PHRASES` — 11 multi-word cue phrases ("doesn't work", "out of order", …)

#### Stored chain envelope

```
RegressionChain
  chain_id        rgf_{ts_ms}_{counter:06d}  (strictly monotonic)
  protocol        "ProblemSolver.REGRESSION_FIRST"
  problem         str
  source          "explicit" | "auto_trigger"
  created_ts      float
  layers          list[RegressionLayer]
    index    int  (1-based)
    name     str
    question str
    where    str           ← bundle's "location" mapped here on ingest
    goal     str
    status   "pending" | "verified" | "failed"
    notes    str | None
  state           "awaiting_verification" | "ready_for_root_cause" | "root_cause_identified"
  summary         RegressionSummary | None
    failed_layers list[int]
    conclusion    "root_cause_found" | "no_defect_in_chain"
    surgical_fix  str | None
```

State machine:

```
awaiting_verification ──► ready_for_root_cause ──► root_cause_identified
        (any pending)          (all findings)         (summary locked)
```

`summarize_root_cause` is gated; further `record_finding` calls are
rejected once the chain is finalized.

### Skills_export bundle

```
skills_export/regression_first/
  system_prompt.md   (canonical Claude instruction set — EL/INS + RF integration)
  schema.json        (JSON Schema for the unified emitted packet)
  README.md          (bundle docs, intended consumers, two-shape boundary)
```

* `system_prompt.md` is the founder-provided canonical instruction
  set verbatim — defines the unified cognitive-signal pipeline. The
  kernel reads it as **plain text** (Path.read_text), not as a
  Python import — same `ARCHITECTURE.md` boundary discipline as
  v69 `el_ins`.
* `schema.json` describes what Claude **emits** (unified packet:
  EL/INS scoring + signals + classification + operator intent +
  `regression_required` + `regression_chain` skeleton +
  `recommended_system_action`). The schema deliberately does **not**
  describe the stored chain envelope — that's a kernel-internal
  shape.
* The kernel maps the emitted `location` field to its stored `where`
  field (`_coerce_layer` accepts both, preferring `location` when
  present, falling back to `where` for legacy direct callers).

### Two related shapes, one source of truth

| Shape           | Where it lives              | Who emits / owns it     | Has state? |
|-----------------|-----------------------------|-------------------------|------------|
| Emitted packet  | `skills_export/.../schema.json` | Claude (LLM)        | No         |
| Stored chain    | `problem_solver/regression_first.py` (TypedDicts) | Kernel | Yes (state machine + per-layer status/notes + summary) |

`analyze_packet` is the seam: it parses the emitted shape, validates
it, and (when `regression_required` is true) wraps the chain
skeleton into a stateful chain via `_coerce_llm_output`.

### Architecture invariants verified

* **No skills_export import.** Both `problem_solver/regression_first.py`
  and `problem_solver/__init__.py` are grepped clean of
  `from skills_export` / `import skills_export`. Locked by
  `TestSkillsBundleAlignment::test_no_skills_export_python_import`.
* **No app.py / kernel / router edits.** Net-new files only. No
  existing module touched. Confirmed by file-count diff below.
* **No `/health` version bump.** Endpoint version stays `4.17`. The
  four version-tracking tests (`test_v28_endpoints`,
  `test_v51_projects`, `test_v53_elins_v2`, `test_v54_ingestion`)
  pass unchanged.
* **Boundary discipline.** Bundle prompt loaded as plain text,
  cached on first read, swappable via `_reset_prompt_cache` for
  tests. Mirrors `el_ins/el_ins_analyzer._load_system_prompt`.
* **Deterministic ids.** `rgf_{ts_ms}_{counter:06d}` strictly
  monotonic across same-millisecond calls. `list_chains` sorts by
  id desc, not `created_ts`, so ties resolve correctly.

---

## Endpoints

None this pass. The endpoint surface lands in V76 (next).

Planned (V76):

| Method | Path                                       | Purpose                                            |
|--------|--------------------------------------------|----------------------------------------------------|
| POST   | `/me/regression_first/start`               | Start a chain (explicit). Body: `{problem, provider_mode?}`. |
| POST   | `/me/regression_first/{chain_id}/finding`  | Record a finding. Body: `{layer_index, status, notes}`. |
| POST   | `/me/regression_first/{chain_id}/summary`  | Finalize. Body: `{surgical_fix?}`.                 |
| GET    | `/me/regression_first/{chain_id}`          | Read one chain.                                    |
| GET    | `/me/regression_first`                     | List operator's chains, newest-first.              |
| POST   | `/me/regression_first/packet`              | Submit raw text; runs EL/INS-driven auto-trigger + chain build via `analyze_packet`. |

---

## Test summary

| Suite                                            | Tests | Net |
|--------------------------------------------------|-------|-----|
| `tests/test_problem_solver.py`                   | 81    | new |
| **Total new**                                    | **81**|     |

Adjacency sweep (regression check):

| Suite                              | Tests | Status |
|------------------------------------|-------|--------|
| `tests/test_problem_solver.py`     | 81    | ✅     |
| `tests/test_el_ins_analyzer.py`    | 33    | ✅     |
| `tests/test_el_ins_store.py`       | 22    | ✅     |
| `tests/test_v28_endpoints.py`      | 70+   | ✅     |
| `tests/test_v51_projects.py`       | 40    | ✅     |
| `tests/test_v53_elins_v2.py`       | —     | ✅     |
| `tests/test_v54_ingestion.py`      | —     | ✅     |
| `tests/test_membership_confirm.py` | 6     | ✅     |
| **Sweep total**                    | **312** | **✅** |

---

## Test classes (problem_solver suite)

| Class                          | Coverage                                                    |
|--------------------------------|-------------------------------------------------------------|
| `TestDefaultChain`             | Canonical six-layer deterministic chain; pending state; protocol id locked. |
| `TestSchemaShape`              | Top-level + layer keys; `rgf_{ts}_{counter}` id pattern; strictly-monotonic ids; source defaults. |
| `TestStateMachine`             | pending → ready transitions; overwrite semantics; `_compute_state` purity. |
| `TestSummarize`                | Gating on pending layers; verified-only conclusion; failed-layer conclusion; required surgical_fix; post-finalize lockout. |
| `TestValidation`               | Empty problem; invalid source / mode / status / notes; unknown chain / layer indices. |
| `TestStore`                    | `list_chains` newest-first by id; `_reset_for_tests` clears state; constant vocabularies. |
| `TestLlmMode`                  | LLM failure → deterministic fallback; invalid JSON → fallback; legacy `{layers:[…]}` direct shape; fenced JSON; malformed layers. |
| `TestAutoTrigger`              | Cue word + cue phrase triggers; EL/INS gating (`high_el` only); empty input; `extract_problem` whitespace normalisation. |
| `TestSkillsBundleAlignment`    | Prompt + schema + README exist; schema is parseable JSON; no python import of `skills_export`; schema describes packet not stored chain; schema layers use `location` not `where`. |
| `TestCanonicalPacket`          | `_extract_packet_dict` (passthrough / fence-strip / invalid); canonical packet parses; `regression_required=false` short-circuits; fenced JSON; legacy `where` still works; `_coerce_layer` `location`/`where` precedence. |
| `TestAnalyzePacket`            | Happy path persists + returns chain; `regression_required=false` → no chain; `build_chain=False` skips persistence; problem defaults to `operator_intent`; invalid scores / classification / missing fields all return None; fenced JSON; signal list coercion. |
| `TestCanonicalExample`         | Pulls the second ```json``` block from `system_prompt.md` and parses it via `analyze_packet` — locks the documented example against the kernel. |

---

## Files touched

```
problem_solver/                                           (new package)
  __init__.py                                              (new)
  regression_first.py                                      (new)
  auto_trigger.py                                          (new)

skills_export/regression_first/                            (new bundle)
  system_prompt.md                                         (new — founder's canonical instruction set verbatim)
  schema.json                                              (new)
  README.md                                                (new)

tests/test_problem_solver.py                               (new — 81 tests)

BUILD_VERSION                                              20260513190000 → 20260514100000
V75_READINESS.md                                           (new)
```

No edits to `app.py`, `intelligence_kernel.py`, `model_router.py`,
`memory_vault.py`, or any existing module. Net-new files only.

---

## What's still pending (separate units)

* **V76 — endpoints.** Six `/me/regression_first/*` routes + Pydantic
  models + `require_session` auth + 404/400/409 paths + pytest.
* **V77 — vault persistence.** Move `_CHAINS` from process-local
  dict to `memory_vault` namespace `regression_chains`.
* **V78 — intelligence_kernel wiring.** `intelligence_kernel.run_regression_first(user, problem)`
  + `model_router.TASK_DEFAULTS["regression_first"]` →
  `claude-3.7` + kernel logging.
* **V79 — el_ins timeline integration.** New `TimelineEventType =
  "regression_chain"` so chains show up in
  `el_ins.org_timeline`.
* **V80 — surfaces.** Web cockpit panel + phone screen + desktop
  consumer of the new endpoints.

---

## Activation phrase (per founder spec)

`"Activate Regression-First Mode for: <problem>"` — when V76 lands,
this resolves to `POST /me/regression_first/start
{"problem": "<problem>"}` and returns the canonical six-layer
deterministic chain. Until then, the kernel is callable via
`problem_solver.build_regression_chain(...)` from Python directly.
