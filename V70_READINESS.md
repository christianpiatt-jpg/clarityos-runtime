# V70 — Units 76 + 77 (EL/INS drift + operator dashboard)

Status: ✅ Ready
Backend version: `4.13` (bumped from 4.12)
Build: `20260513050000`

---

## What this pass ships

Two units that extend the v69 EL/INS module with a **temporal layer**
and an **operator-level macro view**, both purely deterministic (no
LLM, no skills-bundle changes, no per-turn-hook changes).

### Unit 76 — Drift detection + Thread Stability Index

* **`el_ins/el_ins_store.py`** — added:
  * `tsi: Optional[int]` field on `ElInsRecord` (stamped at store
    time for records with a `thread_id`; absent for thread-less
    on-demand analyses).
  * `compute_thread_stability(operator_id, thread_id, *, window=10)`
    returning `{thread_id, stability, tsi, window}`.
  * Private helpers: `_variance`, `_slope` (closed-form OLS),
    `_classify_drift`, `_compute_tsi`.
  * Tuning constants: `HIGH_EL_THRESHOLD`-style locked constants for
    drift fraction (0.34), slope threshold (0.25), TSI penalty
    weights, and the default window (10).
  * `store_el_ins_record` extended: after insertion, stamps `tsi` on
    the just-stored record so the historical record carries the
    thread's stability state *at the moment of that record*.

* **`runtime_http.py`** — new endpoint
  `GET /el_ins/thread/{thread_id}/stability?window=N` (auth-gated).
  Empty threads return `{stability: "stable", tsi: 100, window: 0}`.

* **Web — stability badge** in [OperatorElins.tsx](web/src/routes/OperatorElins.tsx).
  When a thread row is clicked, the drill-down panel now also calls
  `getElInsThreadStability(tid)` in parallel and surfaces a
  colour-coded badge (green=stable, yellow=oscillating, red=drifting).

* **Desktop — mirror badge** in [OperatorElinsShell.tsx](desktop/src/OperatorElinsShell.tsx).

### Unit 77 — Operator-level macro dashboard + trend

* **`el_ins/el_ins_store.py`** — added:
  * `compute_operator_summary(operator_id, *, sample_size=20)`
    returning the classification distribution, avg TSI, and a
    deterministic trend slope.
  * `_classify_trend(tsis)` — slope > 0.5 → improving, slope < -0.5
    → declining, else stable.

* **`runtime_http.py`** — new endpoint
  `GET /el_ins/operator/summary?sample_size=N` (auth-gated).

* **Web — new unified dashboard route** at
  `/operator/el_ins/dashboard` →
  [OperatorElinsDashboard.tsx](web/src/routes/OperatorElinsDashboard.tsx).
  Pulls summary + recent records in parallel. Renders:
  * Pie chart of classification distribution (pure SVG, no chart deps).
  * Line chart of TSI over time (pure SVG sparkline).
  * Trend label coloured by direction.
  * Last 20 records table with a TSI column.

* **Desktop — mirror shell** at
  [OperatorElinsDashboardShell.tsx](desktop/src/OperatorElinsDashboardShell.tsx).
  Wired into `App.tsx` view enum as `"el-ins-dashboard"` and into
  the `OperatorSidebar` NAV_ITEMS as `"EL/INS Dashboard"`.

* **Phone — dashboard surface**:
  * [phone/components/ElInsIndicator.tsx](phone/components/ElInsIndicator.tsx) gains a
    "View Dashboard →" button under the existing stability card.
  * New [phone/app/el_ins_dashboard.tsx](phone/app/el_ins_dashboard.tsx) — mobile-
    compact mirror with SUMMARY block, sparkline TSI chart (via
    `react-native-svg`), and the last 20 records list.
  * Registered as a `Stack.Screen` in `phone/app/_layout.tsx`.

* **Layout.tsx** RUNTIME rail now lists a third EL/INS link:
  **EL/INS Dashboard** at `/operator/el_ins/dashboard`.

---

## Endpoints

| Method | Path                                          | Purpose                              |
|--------|-----------------------------------------------|--------------------------------------|
| GET    | `/el_ins/thread/{thread_id}/stability?window=N` | Thread stability + TSI               |
| GET    | `/el_ins/operator/summary?sample_size=N`      | Operator distribution + avg TSI + trend |

Both auth-gated via `require_operator`. Same authz contract as the
rest of `/el_ins/*`.

---

## Test summary

| Suite                                            | Tests | Net |
|--------------------------------------------------|-------|-----|
| `test_el_ins_drift.py`                           | 36    | new |
| `test_el_ins_stability_endpoint.py`              | 16    | new |
| Web `OperatorElins.test.tsx` (new badge tests)   |  2    | +2  |
| Web `OperatorElinsDashboard.test.tsx`            | 11    | new |
| **Total new**                                    | **65** |    |

Full suites:
- Web: **120/120 passed** (107 prior + 13 net new).
- Backend: pending full-suite confirmation, focused EL/INS subset
  = **134/134 passed**.
- Desktop: tsc clean, vite build clean (296.81 KB JS, 83.56 KB gzip).

---

## What did NOT change

- The skills bundle (`/skills_export/el_ins/`).
- The LLM analyzer code (`el_ins/el_ins_analyzer.py`).
- The per-turn hook in `intelligence_kernel.run_thread_message`.
- The `operator_state.el_ins_per_turn` flag semantics.
- Existing endpoints `POST /el_ins/analyze`, `GET /el_ins/recent`,
  `GET /el_ins/thread/{tid}`, `GET /el_ins/macro`.
- Existing `ElInsRecord` validation rules — `tsi` is **additive**
  optional. Records stored before this pass have no `tsi`; the
  dashboard handles missing TSI gracefully (filter from sparkline,
  show "—" in tables).

---

## Files touched

```
el_ins/el_ins_store.py
el_ins/__init__.py
runtime_http.py
app.py                              (/health + / version → "4.13")
BUILD_VERSION                       (20260513040000 → 20260513050000)

web/src/lib/api.ts                  (+ 2 helpers + 4 types)
web/src/routes/OperatorElins.tsx    (+ stability badge wiring)
web/src/routes/OperatorElinsDashboard.tsx                    (new)
web/src/App.tsx                     (+ /operator/el_ins/dashboard route)
web/src/components/Layout.tsx       (+ EL/INS Dashboard rail link)
web/src/routes/__tests__/OperatorElins.test.tsx              (+ 2 badge tests)
web/src/routes/__tests__/OperatorElinsDashboard.test.tsx     (new)

desktop/src/lib/api.ts              (+ 2 helpers + 4 types)
desktop/src/OperatorElinsShell.tsx  (+ stability badge wiring)
desktop/src/OperatorElinsDashboardShell.tsx                  (new)
desktop/src/App.tsx                 (+ "el-ins-dashboard" view)
desktop/src/components/v1/OperatorSidebar/OperatorSidebar.tsx (+ "EL/INS Dashboard")

phone/lib/api.ts                    (+ 2 helpers + 4 types)
phone/components/ElInsIndicator.tsx (+ "View Dashboard →" button)
phone/app/el_ins_dashboard.tsx                                (new)
phone/app/_layout.tsx               (+ Stack.Screen "el_ins_dashboard")

tests/test_el_ins_drift.py                                   (new — 36)
tests/test_el_ins_stability_endpoint.py                      (new — 16)
tests/test_v28_endpoints.py         (version bump 4.12 → 4.13)
tests/test_v51_projects.py          (version bump 4.12 → 4.13)
tests/test_v53_elins_v2.py          (version bump 4.12 → 4.13)
tests/test_v54_ingestion.py         (version bump 4.12 → 4.13)

V70_READINESS.md                                             (new)
```

---

## Spec checkbox audit

Mapping back to Christian's instruction sets:

### Unit 76

| Spec section | Status |
|--------------|--------|
| §1 Drift detection (stable / drifting_el / drifting_ins / oscillating) | ✅ `_classify_drift` |
| §2 Thread Stability Index 0-100 from variance + classification changes + mode changes | ✅ `_compute_tsi` with 4 capped penalties |
| §2 Deterministic formula (no LLM) | ✅ pure Python |
| §2 Stored alongside each EL/INS record | ✅ `tsi` field stamped at store time |
| §3 `GET /el_ins/thread/{tid}/stability` endpoint, locked shape | ✅ |
| §4 Store extension + `compute_thread_stability` helper | ✅ |
| §5 Web stability badge on per-thread view | ✅ |
| §5 Desktop stability badge | ✅ |
| §5 Color-coded green/yellow/red | ✅ |
| §6 Drift detection tests | ✅ 7 tests (`TestClassifyDrift`) |
| §6 TSI formula tests | ✅ 5 tests (`TestComputeTSI`) |
| §6 Endpoint tests | ✅ 7 tests (`TestStabilityEndpoint`) |
| §6 Web component tests | ✅ 2 new badge tests |
| Constraint: no LLM | ✅ |
| Constraint: no analyzer changes | ✅ |
| Constraint: no skills bundle changes | ✅ |
| Constraint: no per-turn hook changes | ✅ |

### Unit 77

| Spec section | Status |
|--------------|--------|
| §1 `GET /el_ins/operator/summary` endpoint, locked shape | ✅ |
| §2 Trend computation (improving / declining / stable) via deterministic slope | ✅ `_classify_trend` |
| §3 Web `/operator/el_ins/dashboard` with pie + line + trend + last 20 records | ✅ |
| §3 Desktop equivalent shell | ✅ |
| §4 Phone "View Dashboard" button + mobile summary | ✅ |
| §5 Endpoint tests | ✅ 9 tests (`TestOperatorSummaryEndpoint`) |
| §5 Trend calculation tests | ✅ 6 tests (`TestClassifyTrend`) |
| §5 Web component tests | ✅ 11 tests (`OperatorElinsDashboard.test.tsx`) |
| §5 Desktop shell tests | ⚠️  No tests — desktop has no test harness (v51/v68 precedent). tsc + vite build verified clean. |
| Constraint: no LLM | ✅ |
| Constraint: deterministic math only | ✅ |
| Constraint: Unit 76 untouched | ✅ |
| Constraint: analyzer untouched | ✅ |
| Constraint: skills bundle untouched | ✅ |
| Constraint: per-turn hook untouched | ✅ |
| Constraint: existing surfaces only add dashboard link | ✅ Layout.tsx rail + phone indicator card got a button; existing surfaces otherwise unchanged. |
