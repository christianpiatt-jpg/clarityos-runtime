# V76 — ProblemSolver.REGRESSION_FIRST (Endpoints + Kernel Realignment)

Status: ✅ Ready
Backend version: `4.18` (bumped from `4.17`)
Build: `20260514120000` (bumped from `20260514100000`)

---

## What this pass ships

### Founder-locked design call

V76 ships in **Direction A** — the V75 kernel was realigned to the
canonical V76 chain model (founder spec dated this pass). The
intermediate "stateful 6-layer scaffold + state machine + root-cause
summary" envelope from V75 was dropped in favour of a leaner
operator-finding log. Reason: V75's pre-populated scaffold pulled too
much state into the kernel; the canonical V76 spec keeps the kernel
thin and lets the operator drive layer creation. See conversation
transcript for the trade analysis; cleanest single-step migration.

### Scope

* Kernel realignment from V75 shape → V76 shape (this pass).
* Thin HTTP layer over the realigned kernel: six routes, all
  `require_session`.
* Per-user ownership index on the app side (V77 moves to memory_vault
  per-user partitioning).

### Backend kernel (rewritten)

`problem_solver/regression_first.py` — V76 public surface:

| Symbol                                          | Behaviour                                                       |
|-------------------------------------------------|-----------------------------------------------------------------|
| `start_chain(title, *, notes=None)`             | Open a chain. Layers + tags empty; `closed_at = None`. Validates title (1..200) + notes (≤8 KiB). |
| `record_finding(chain_id, layer_index, status, notes=None)` | Append/overwrite a finding for one layer. Auto-grows layer list; re-sorts ascending by `layer_index`. Status ∈ {ok, issue, blocked, unknown}. Layer notes ≤4 KiB. |
| `close_chain(chain_id, *, notes=None)`          | Set `closed_at = now`. Optionally overwrite top-level `notes`. Irreversible. |
| `tag_chain(chain_id, tags)`                     | Merge `tags` into chain's dict. Existing keys overwritten by supplied values; absent keys preserved. Validates types + caps (key ≤64, value ≤256, ≤32 tags/chain). Atomic on failure. |
| `get_chain(chain_id)` / `list_chains()`         | Read / list (newest-first by `created_at` then strictly-monotonic insertion seq). |
| `analyze_packet(raw, *, title=None, build_chain=True)` | Parse a unified packet emitted under the canonical bundle prompt; optionally opens an empty chain with `title = operator_intent`. The packet's `regression_chain` skeleton is informational only — kernel does NOT pre-populate layers. Operator drives via `/step`. |

#### Stored chain envelope (V76)

```
RegressionChain
  chain_id     str  (canonical UUID4, 36 chars with dashes)
  created_at   int  (ms epoch)
  closed_at    int | None  (ms epoch when /close runs)
  title        str  (1..200 after strip)
  notes        str | None  (≤8 KiB after strip; whitespace-only → None)
  layers       list[RegressionLayer]
    layer_index  int  (0-based, operator-supplied)
    status       "ok" | "issue" | "blocked" | "unknown"
    notes        str | None  (≤4 KiB after strip)
    updated_at   int  (ms epoch — stamped on every write)
  tags         dict[str, str]  (≤32 entries; key 1..64, value ≤256)
```

#### Removed from V75 (dropped intentionally)

* Pre-populated 6-layer canonical scaffold (`_DEFAULT_LAYERS`)
* 3-state state machine (`awaiting_verification` →
  `ready_for_root_cause` → `root_cause_identified`)
* `summarize_root_cause` + `RegressionSummary` (failed_layers +
  conclusion + surgical_fix)
* `_make_chain_id` returning `rgf_{ts_ms}_{counter:06d}` — replaced
  with `uuid.uuid4()`
* `provider_mode` / `PROVIDER_MODES` (kernel no longer offers a
  deterministic chain-builder)
* `source` / `SOURCES` on the chain envelope
* `_coerce_llm_output` + `_coerce_layer` (no chain stamping from
  skeleton)

#### Preserved from V75

* `skills_export/regression_first/` bundle (unchanged — same
  canonical system_prompt.md + schema.json + README.md)
* `analyze_packet` for the auto-trigger path (rewired to V76's
  empty-chain flow)
* `auto_trigger.py` (cue word/phrase detector, `extract_problem`)
* No-skills-import boundary — locked by
  `TestSkillsBundleAlignment::test_no_skills_export_python_import`

### HTTP endpoints (6, all `require_session`)

| Method | Path                                            | Purpose                                                   |
|--------|-------------------------------------------------|-----------------------------------------------------------|
| POST   | `/me/regression_first/start`                    | Open a new chain. Body: `{title, notes?}`.                |
| POST   | `/me/regression_first/step?chain_id={cid}`      | Record a finding. Body: `{layer_index, status, notes?}`.  |
| GET    | `/me/regression_first/{chain_id}`               | Fetch one chain. 404 if unknown or not owned by caller.   |
| GET    | `/me/regression_first`                          | List caller's chains, newest-first.                       |
| POST   | `/me/regression_first/{chain_id}/close`         | Close a chain. Body: `{notes?}`. Irreversible.            |
| POST   | `/me/regression_first/{chain_id}/tag`           | Merge tags. Body: `{tags: {k: v}}`. Tag deletion deferred to V78. |

#### Ownership model (V76 only)

V76 keeps an in-process side index `_V76_OWNERS: dict[chain_id, user]`
in `app.py`. Reads/mutates of a chain belonging to a different user
return **404** (existence not leaked). V77 replaces this with
memory_vault's native per-user partitioning and the side index
disappears. Cleared by the `reset_stores` test fixture via
`_v76_reset_owners_for_tests()`.

#### Pydantic models (new)

* `V76RegressionLayerModel(layer_index, status, notes?, updated_at)`
* `V76RegressionChainModel(chain_id, created_at, closed_at?, title, notes?, layers, tags)`
* `V76RegressionChainListResponse(chains)`
* `V76StartRequest(title, notes?)`
* `V76StepRequest(layer_index, status, notes?)`
* `V76CloseRequest(notes?)`
* `V76TagRequest(tags: dict[str, str])`

### Error contract

| Condition                                         | HTTP | Body                                                  |
|---------------------------------------------------|------|-------------------------------------------------------|
| Missing/invalid/expired session                   | 401  | `{detail: error_response("missing_session" / "invalid_session" / "expired_session")}` |
| Unknown chain id OR cross-user access             | 404  | `{detail: "chain not found"}`                         |
| Validation failure (status, layer_index, oversized fields, empty title, closed-chain mutation, bad tags) | 400  | `v29_hardening` validator envelope (`{detail: {error: "bad_input", message: ...}}`) |

### Activation phrase

Per founder spec: `"Activate Regression-First Mode for: <problem>"`
resolves to `POST /me/regression_first/start {"title": "<problem>"}`
and returns the new chain (empty `layers`, `closed_at: null`). The
operator then drives diagnostic layers via `/step`.

---

## Endpoints (running route inventory now at 81+)

| Method | Path                                          | Status |
|--------|-----------------------------------------------|--------|
| POST   | `/me/regression_first/start`                  | new    |
| POST   | `/me/regression_first/step`                   | new    |
| GET    | `/me/regression_first/{chain_id}`             | new    |
| GET    | `/me/regression_first`                        | new    |
| POST   | `/me/regression_first/{chain_id}/close`       | new    |
| POST   | `/me/regression_first/{chain_id}/tag`         | new    |

All 6 surfaced in the `GET /` routes manifest with v76 tags.

---

## Test summary

| Suite                                            | Tests | Net |
|--------------------------------------------------|-------|-----|
| `tests/test_problem_solver.py` (rewritten)       | 84    | replaces 81 V75 tests |
| `tests/test_regression_first_endpoints.py`       | 27    | new |
| **Net new in this pass**                         | **30**| 27 endpoint + 3 net delta on kernel |

Adjacency sweep:

| Suite                                       | Tests | Status |
|---------------------------------------------|-------|--------|
| `tests/test_problem_solver.py`              | 84    | ✅     |
| `tests/test_regression_first_endpoints.py`  | 27    | ✅     |
| `tests/test_el_ins_analyzer.py`             | 33    | ✅     |
| `tests/test_el_ins_store.py`                | 22    | ✅     |
| `tests/test_v28_endpoints.py`               | ~70   | ✅ (version 4.17 → 4.18) |
| `tests/test_v47_threads.py`                 | ~80   | ✅     |
| `tests/test_v51_projects.py`                | 40    | ✅ (version 4.17 → 4.18) |
| `tests/test_v53_elins_v2.py`                | ~    | ✅ (version 4.17 → 4.18) |
| `tests/test_v54_ingestion.py`               | ~    | ✅ (version 4.17 → 4.18) |
| `tests/test_membership_confirm.py`          | 6     | ✅     |
| **Sweep total**                             | **376** | **✅** |

### Test classes — kernel (test_problem_solver.py)

| Class                          | Coverage                                                    |
|--------------------------------|-------------------------------------------------------------|
| `TestStartChain`               | Envelope keys, UUID id format, ms timestamps, optional notes, validation (empty/oversized title, oversized notes, non-string notes), unique ids, persistence. |
| `TestRecordFinding`            | Auto-append on first sight, overwrite on subsequent post, ascending re-sort by layer_index, all 4 statuses valid, optional notes, whitespace normalisation, invalid status / negative index / non-int index rejected, unknown chain raises KeyError, closed-chain rejection, oversized notes rejected. |
| `TestCloseChain`               | Sets closed_at, optional notes overwrites top-level, whitespace notes → None, oversized notes rejected, double-close → ValueError("already closed"), unknown chain → KeyError. |
| `TestTagChain`                 | Merge into empty + into existing, overwrite vs preserve, empty dict noop, validation (non-dict/key/value type, empty/oversized key, oversized value, >32 tags/chain), atomic-on-failure, closed-chain rejection, unknown chain → KeyError. |
| `TestStore`                    | KeyError on get unknown, empty list, newest-first ordering (ms ties broken by insertion seq), closed chains still listed, reset hook, constant vocabularies, UUID round-trip. |
| `TestExtractPacketDict`        | Passthrough dict, fence strip, invalid → None. |
| `TestAnalyzePacket`            | Happy path persists empty chain (skeleton informational only), regression_required=false → no chain, build_chain=False → no persistence, title defaults to operator_intent, oversized intent gets truncated, invalid scores/classification/missing fields all return None, fenced JSON, signal coercion to strings, regression_chain must be list. |
| `TestAutoTrigger`              | Cue word + phrase triggers, EL/INS gating (`high_el` required when provided), empty input, `extract_problem` whitespace normalisation, cue word constants lowercased. |
| `TestSkillsBundleAlignment`    | Prompt + schema + README exist, schema is valid JSON, no python import of skills_export (locked), schema describes packet (not stored chain), packet uses `location` while stored chain uses `layer_index`. |
| `TestCanonicalExample`         | Pulls the second ```json``` block from `system_prompt.md` and parses it via `analyze_packet` — locks the documented example against the kernel. |

### Test classes — endpoints (test_regression_first_endpoints.py)

| Class                          | Coverage                                                    |
|--------------------------------|-------------------------------------------------------------|
| `TestHappyPath`                | Full lifecycle: start → step (twice + overwrite) → tag (twice + merge) → list → get → close (with notes); newest-first list ordering. |
| `TestSession`                  | All 6 routes return 401 with no header / invalid session; cross-user chain returns 404 (existence not leaked). |
| `TestUnknownChain`             | All 4 mutating routes (get/step/close/tag) return 404 on unknown chain id. |
| `TestValidation`               | Empty/oversized title 400; invalid status 400; negative layer_index 400; oversized tag value 400; empty tag key 400. |
| `TestClosedChainLockout`       | Step on closed 400, tag on closed 400, double-close 400. |
| `TestTagMergeOverHttp`         | Merge preserves unmentioned keys; empty `tags: {}` is a no-op. |
| `TestHealthAndManifest`        | `/health` version pinned at `4.18`; `/` routes manifest lists all 6 v76 routes. |

---

## Files touched

```
problem_solver/regression_first.py                        (rewritten — V76 shape)
problem_solver/__init__.py                                (re-exports updated)

tests/test_problem_solver.py                              (rewritten — 84 tests)
tests/test_regression_first_endpoints.py                  (new — 27 tests)
tests/conftest.py                                         (+ problem_solver + _v76 owner index reset)

tests/test_v28_endpoints.py                               (version 4.17 → 4.18)
tests/test_v51_projects.py                                (version 4.17 → 4.18)
tests/test_v53_elins_v2.py                                (version 4.17 → 4.18)
tests/test_v54_ingestion.py                               (version 4.17 → 4.18)

app.py                                                     (+ problem_solver import,
                                                            + 7 Pydantic models,
                                                            + 6 /me/regression_first/* handlers,
                                                            + _V76_OWNERS side index,
                                                            + 6 entries in routes manifest,
                                                            /health version 4.17 → 4.18)

BUILD_VERSION                                              20260514100000 → 20260514120000
V76_READINESS.md                                          (new)
```

skills_export bundle (`skills_export/regression_first/`) **unchanged**
in this pass — the canonical system_prompt.md + schema.json + README
shipped in V75 still match V76's analyze_packet contract.

---

## Architecture invariants verified

* **No-skills-import boundary still locked.** Both
  `problem_solver/regression_first.py` and `problem_solver/__init__.py`
  grep clean of `from skills_export` / `import skills_export`.
* **Bundle is the source of truth for the emitted shape.** Kernel
  reads `system_prompt.md` as plain text; never python-imports.
* **Per-user data is per-user.** Cross-user chain access returns
  404 (existence not leaked); test class `TestSession` locks this.
* **Closed chains are immutable.** `record_finding`, `tag_chain`,
  and a second `close_chain` all raise on closed chains.
* **Tag mutation is atomic.** A batch containing one invalid tag
  leaves the chain's existing tags intact (no partial commit).
* **Status enum is the new vocabulary.** `LAYER_STATUSES =
  ("ok", "issue", "blocked", "unknown")`. Old V75 vocabulary
  (`pending` / `verified` / `failed`) is removed.

---

## What's still pending (separate units)

* **V77 — vault persistence.** Move `_CHAINS` from process-local dict
  to `memory_vault` namespace `regression_chains` (per-user). The
  `_V76_OWNERS` side index disappears in this pass.
* **V78 — intelligence_kernel + auto-trigger wiring.**
  `intelligence_kernel.run_regression_first(user, problem)` +
  `model_router.TASK_DEFAULTS["regression_first"]` → claude-3.7 +
  kernel logging + the `/me/regression_first/packet` (raw text →
  EL/INS + auto-trigger) endpoint that was deferred from V76.
* **V79 — el_ins timeline integration.** New `TimelineEventType =
  "regression_chain"` so chain events surface in
  `el_ins.org_timeline`.
* **V80 — surfaces.** Web cockpit panel + phone screen + desktop
  consumer of the v76 endpoints.

---

## Migration notes for existing callers

V75 was *backend kernel only* — no endpoints, no app.py wiring, no
external consumers. Nothing in the codebase consumes V75's kernel
API today. The V76 rewrite therefore has **zero impact** on existing
callers; the 81 V75 tests were replaced with 84 V76 tests in one
pass.
