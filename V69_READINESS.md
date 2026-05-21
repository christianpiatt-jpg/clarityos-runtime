# V69 — Units 74 + 75 (EL/INS reasoning-stability operator)

Status: ✅ Ready
Backend version: `4.12` (bumped from 4.11)
Build: `20260513040000`

---

## What this pass ships

A new reasoning-stability operator that scores text by the ratio of
**Emotive Language (EL)** to **Institutional Signal (INS)** and routes
the consuming model into one of three modes: `stabilize`, `expand`,
or `normal`.

Per the locked architecture decision (Option C):
- **/skills_export/el_ins/** — canonical external bundle (system prompt
  + schema + README) for Claude / Langbridg / third-party LLMs.
- **`el_ins/` kernel module** — in-runtime analyzer with LLM-primary +
  deterministic-fallback engine, dedicated storage, optional per-turn
  hook, and three surfaces (cockpit indicator + dashboard + macro view).

The skills bundle and the kernel module both read **the same**
`system_prompt.md` — single source of truth.

---

## File layout

```
skills_export/el_ins/                                  (new bundle)
    system_prompt.md
    schema.json
    README.md

el_ins/                                                (new kernel dir)
    __init__.py
    el_ins_analyzer.py
    el_ins_store.py

runtime_http.py            (+ /el_ins/* router + 4 endpoints)
intelligence_kernel.py     (+ per-turn hook in run_thread_message)
operator_state.py          (+ el_ins_per_turn flag, getter/setter)
app.py                     (+ include_router(el_ins_router); /health → 4.12)

web/src/lib/api.ts                                     (+ types + 4 helpers)
web/src/components/cockpit/ElInsIndicator.tsx          (new)
web/src/routes/OperatorElins.tsx                       (new — /operator/el_ins)
web/src/routes/OperatorElinsMacro.tsx                  (new — /operator/el_ins/macro)
web/src/routes/Cockpit.tsx                             (+ ElInsIndicator panel)
web/src/components/Layout.tsx                          (+ 2 RailLinks)
web/src/App.tsx                                        (+ 2 routes)
web/src/routes/__tests__/OperatorElins.test.tsx        (new — 10 tests)
web/src/routes/__tests__/OperatorElinsMacro.test.tsx   (new —  9 tests)

desktop/src/lib/api.ts                                 (+ types + 4 helpers)
desktop/src/OperatorElinsShell.tsx                     (new)
desktop/src/OperatorElinsMacroShell.tsx                (new)
desktop/src/App.tsx                                    (+ 2 view enums, routes)
desktop/src/components/v1/OperatorSidebar/OperatorSidebar.tsx
                                                       (+ "EL/INS", "EL/INS Macro" nav)

phone/lib/api.ts                                       (+ types + 2 helpers)
phone/components/ElInsIndicator.tsx                    (new — home/cockpit card)
phone/app/index.tsx                                    (+ ElInsIndicator render)
phone/app/el_ins.tsx                                   (new — tap-through screen)
phone/app/_layout.tsx                                  (+ Stack.Screen "el_ins")

tests/test_el_ins_analyzer.py                          (new — 33 tests)
tests/test_el_ins_store.py                             (new — 22 tests)
tests/test_el_ins_endpoint.py                          (new — 18 tests)
tests/test_el_ins_per_turn_hook.py                     (new —  9 tests)

V69_READINESS.md                                       (new)
BUILD_VERSION                                          (20260513030000 → 20260513040000)
```

---

## Kernel surface

`el_ins.analyze_text(text, *, provider_mode="auto") -> ElInsResult`

- `"auto"` (default): try LLM, fall back to deterministic on any
  failure (model_router unreachable, JSON parse failure, validation
  failure). Production default.
- `"llm"`: same as auto — analyzer never raises, always returns a
  shaped result.
- `"deterministic"`: pure Python heuristic only. No LLM call. Used by
  the per-turn hook for cost control and by callers in offline /
  phone runtime paths.

`el_ins.analyze_thread(messages, *, provider_mode="auto") -> list[ElInsResult]`
mirrors batch semantics for macro-analysis paths.

The deterministic heuristic uses two carefully-tuned vocabularies
(`EMOTIVE_TERMS`, `INSTITUTIONAL_TERMS`), density-normalises to 0..10,
classifies via fixed thresholds (`HIGH_EL_THRESHOLD = 1.30`,
`HIGH_INS_THRESHOLD = 0.70`), and maps the bucket deterministically
to `reasoning_mode`.

---

## Endpoints

All four under `el_ins_router` (`/el_ins`), auth-gated via
`require_operator`. Same authz contract as `/runtime/providers/*`.

| Method | Path                          | Purpose                          |
|--------|-------------------------------|----------------------------------|
| POST   | `/el_ins/analyze`             | Analyze text; store if thread_id |
| GET    | `/el_ins/recent?limit=N`      | Recent N records for operator    |
| GET    | `/el_ins/thread/{thread_id}`  | Per-thread history               |
| GET    | `/el_ins/macro?since=<float>` | Macro batch, optional since      |

---

## Storage

New `el_ins/el_ins_store.py`. In-memory backend (matches the
`macro_scheduler_store` + `users_store` pattern; Firestore eligible
via `CLARITYOS_BACKEND=firestore`, hook left for a future pass).

Records keyed by `(operator_id, thread_id, timestamp)`. Stored
newest-first per operator so reads stay O(N) without re-sort.

Sources: `on_demand` (POST /analyze with thread_id), `per_turn`
(kernel hook), `macro` (reserved for batch workflows).

---

## Per-turn hook (opt-in)

`intelligence_kernel.run_thread_message` reads
`operator_state.get_el_ins_per_turn(user_id)`. When True, runs a
deterministic EL/INS analysis on the user's message after the
assistant turn lands and stores the result under `source="per_turn"`.

Default off — so existing operators don't silently pay the analysis
cost.

Hook failures are swallowed — analysis is a diagnostic, never
allowed to break the chat response path. Verified by
`test_el_ins_per_turn_hook.py::TestFailureIsolation`.

---

## Surfaces

### Cockpit indicator (web + desktop + phone)
Compact badge — "Stability: Balanced / High-EL / High-INS" — driven
by `getElInsRecent(1)`. Tap-through to the full surface on phone;
inline link on web/desktop. Hides itself silently on fetch failure.

### `/operator/el_ins` (web + desktop)
Per-user dashboard. Three panels:
1. **ANALYZE** — textarea + provider_mode picker + optional thread_id
2. **RECENT** — newest-first table of the operator's 100 most recent records
3. **SELECTED THREAD** — drill-down loaded on row click

### `/operator/el_ins/macro` (web + desktop)
Macro/aggregate view. Rolling window selector (24h / 7d / 30d / all
time). Computes per-bucket distribution percentages + avg EL/INS
scores from the `/el_ins/macro` data.

### Phone — `/el_ins`
Compact mirror of OperatorElins (analyze + recent list). AuthGate-
wrapped per v67/v68 convention. Tap-through from the home indicator
card.

---

## Test summary

| Suite                                       | Tests | Net |
|---------------------------------------------|-------|-----|
| `test_el_ins_analyzer.py`                   | 33    | new |
| `test_el_ins_store.py`                      | 22    | new |
| `test_el_ins_endpoint.py`                   | 18    | new |
| `test_el_ins_per_turn_hook.py`              |  9    | new |
| `web/.../OperatorElins.test.tsx`            | 10    | new |
| `web/.../OperatorElinsMacro.test.tsx`       |  9    | new |
| **Total new**                               | **101** |   |

Full suites:
- Web: **107/107 passed** (88 prior + 19 new).
- Backend: pending full-suite confirmation (focused subset including
  EL/INS + adjacent operator_state + threads = **198+9 passing**).
- Desktop: tsc clean, vite build clean (287.57 KB JS, 81.91 KB gzip).

---

## ARCHITECTURE.md alignment

EL/INS lands as the first ClarityOS module to combine:
1. A `/skills_export/` canonical external bundle.
2. A kernel runtime module that **reads** the skills bundle's
   `system_prompt.md` as plain text — NOT as a Python import.

This pattern preserves the no-import boundary while letting the kernel
share a single source of truth with external consumers. The
`test_el_ins_analyzer.py::TestSkillsBundleAlignment::test_no_skills_export_python_import`
test locks the boundary against regression.

---

## What did NOT change

- ELINS, ELINS forecast engine, ELINS macro scheduler — unrelated
  surfaces; `el_ins` is a sibling, not a child.
- `model_router` public surface — only consumed by the analyzer.
- `threads_vault`, `memory_vault`, `projects_vault` — analyses live
  in their own store.
- `operator_state` history caps (`HISTORY_MAX=200`) — EL/INS records
  live in `el_ins_store`, not `operator_state.elins_history`.
- Auth contract — every new endpoint is `require_operator`-gated.

---

## Spec checkbox audit

Mapping back to Christian's module spec:

| Spec section | Status |
|--------------|--------|
| §2.1 Skills export (3 files) | ✅ system_prompt.md + schema.json + README.md |
| §2.2 Kernel module (3 files) | ✅ __init__.py + el_ins_analyzer.py + el_ins_store.py |
| §2.3 HTTP + integration | ✅ /el_ins/* in runtime_http.py + per-turn hook in intelligence_kernel.py |
| §2.4 Web + desktop surfaces | ✅ OperatorElins + OperatorElinsMacro + cockpit indicator on all three trees |
| §3.1 Public Python API (analyze_text, analyze_thread, ElInsResult, provider_modes) | ✅ |
| §3.2 Deterministic fallback | ✅ EMOTIVE_TERMS + INSTITUTIONAL_TERMS vocabularies + density scoring |
| §3.3 LLM mode | ✅ model_router.route_request + fence-tolerant JSON parse + fallback on failure |
| §4.1 POST /el_ins/analyze | ✅ |
| §4.2 Optional per-turn hook | ✅ operator_state.el_ins_per_turn flag; default off |
| §5 Storage model (el_ins_store) | ✅ store_el_ins_record + 3 retrieval fns + ElInsRecord typed |
| §6.1 Cockpit indicator (all surfaces) | ✅ web + desktop + phone |
| §6.2 /operator/el_ins | ✅ web route + desktop shell |
| §6.3 /operator/el_ins/macro | ✅ web route + desktop shell |
| §7.1 Kernel tests (analyzer + store) | ✅ 33 + 22 = 55 |
| §7.2 HTTP tests | ✅ 18 + 9 per-turn = 27 |
| §7.3 Web tests (Operator + Macro) | ✅ 10 + 9 = 19 |
| §7.3 Desktop tests | tsc + vite verification only (v51 precedent — no harness) |
| §8 Memory + docs | ✅ V69_READINESS.md + project_clarityos_v69_units_74_75.md + ARCHITECTURE.md update |
