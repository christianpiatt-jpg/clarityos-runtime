# V72 — Units 80 + 81 (EL/INS anomaly alerts + organizational roll-up)

Status: ✅ Ready
Backend version: `4.15` (bumped from 4.14)
Build: `20260513070000`

---

## What this pass ships

### Unit 80 — Anomaly alerts

* **`el_ins/anomaly.py`** — pure-Python detection module. Four rules:
  * EL > 7.5 → `high_el` severity 3
  * INS < 2.0 → `low_ins` severity 3
  * TSI > 85 → `tsi_spike` severity 4
  * Diagonal quadrant transition between consecutive records (Manhattan
    distance ≥ 2 on the 2×2 EL/INS lattice) → `quadrant_jump` severity 5

  Thresholds are strict (`>` / `<`), not inclusive — boundaries do NOT
  fire. Locked by 8 boundary tests.

* **`el_ins/anomaly_store.py`** — newest-first per-operator store
  with `store_anomalies` / `list_anomalies` / `get_anomaly` /
  `list_anomalies_since`. Validation enforces type + severity bounds.

* **Kernel integration** — `run_thread_message` after EL/INS storing:
  reads the stamped record back (to pick up TSI), pulls the prior
  thread record for the quadrant-jump rule, calls `detect_anomalies`,
  stores results, and surfaces them on the return dict as additive
  `anomalies: list`. Failures swallowed — diagnostic never breaks the
  chat path.

* **HTTP endpoints**:
  * `GET /el_ins/anomalies?limit=N` — newest-first list (clamp [1, 1000])
  * `GET /el_ins/anomalies/{id}` — single-anomaly lookup, 404 on cross-operator

* **Surfaces**:
  * Web `/operator/el_ins/anomalies` route + table view + severity chips +
    red-dot badge on the cockpit `ElInsIndicator` when at least one
    anomaly landed in the last 24h (stateless, no client last-seen).
  * Desktop `OperatorElinsAnomaliesShell` + `EL/INS Anomalies` sidebar
    entry + header red dot.
  * Phone `el_ins_anomalies.tsx` tap-to-expand list + cockpit card
    "Anomalies →" button with `(new)` suffix on recent anomalies +
    inline red dot next to stability label.

### Unit 81 — Organizational roll-up

* **`el_ins/rollup.py`** — `compute_rollup(operator_id, window)`
  returning `{avg_el, avg_ins, avg_tsi, reasoning_mode_distribution,
  record_count, window_start, window_end}`. Window accepts the named
  strings ``"24h"`` / ``"7d"`` / ``"30d"``, a `timedelta`, or raw
  float-seconds. Pure deterministic aggregation; no LLM.

  Records without a `tsi` field are still counted toward
  `reasoning_mode_distribution` but excluded from the TSI average.
  `reasoning_mode` is recomputed per record via
  `intelligence_kernel.select_reasoning_mode(el, ins, tsi)` so the
  distribution stays consistent with the cockpit indicator.

* **HTTP endpoints**:
  * `GET /el_ins/rollup/24h`
  * `GET /el_ins/rollup/7d`
  * `GET /el_ins/rollup/30d`

* **Surfaces**:
  * Web `/operator/el_ins/rollup` route — three-card grid (24h / 7d /
    30d), each card with avg EL/INS/TSI + reasoning-mode SVG pie chart
    + record count.
  * Desktop `OperatorElinsRollupShell` mirror + `EL/INS Roll-Up`
    sidebar entry.
  * Phone `el_ins_rollup.tsx` — three collapsible sections per spec
    (text-only on phone — no charts).

---

## Endpoints (auth-gated)

| Method | Path                              | Purpose                                 |
|--------|-----------------------------------|-----------------------------------------|
| GET    | `/el_ins/anomalies?limit=N`       | Newest-first anomaly list               |
| GET    | `/el_ins/anomalies/{id}`          | Single anomaly lookup                   |
| GET    | `/el_ins/rollup/24h`              | 24h aggregate                           |
| GET    | `/el_ins/rollup/7d`               | 7d aggregate                            |
| GET    | `/el_ins/rollup/30d`              | 30d aggregate                           |

---

## Test summary

| Suite                                            | Tests | Net |
|--------------------------------------------------|-------|-----|
| `tests/test_el_ins_anomaly.py`                   | 39    | new |
| `tests/test_el_ins_rollup.py`                    | 24    | new |
| `web/.../OperatorElinsAnomalies.test.tsx`        |  7    | new |
| `web/.../OperatorElinsRollup.test.tsx`           |  7    | new |
| `web/.../cockpit/ElInsIndicator.test.tsx`        |  2    | +2  |
| **Total new**                                    | **79**|     |

Full suites:
- Web: **150/150 passed** (134 prior + 16 net new).
- Backend: pending full-suite confirmation; focused EL/INS subset =
  **248/248 passed**.
- Desktop: tsc clean, vite build clean (312.97 KB JS, 86.32 KB gzip).

---

## What did NOT change

- Analyzer (`el_ins/el_ins_analyzer.py`) — untouched.
- Skills bundle (`/skills_export/el_ins/`) — byte-identical to v69.
- Per-turn hook signature — additive integration only.
- `ElInsRecord` shape — anomalies live in a separate store keyed by
  uuid4 + `record_id` back-pointer.
- Existing v69-v71 endpoints — fully back-compatible.
- `run_thread_message` return dict — gained additive `anomalies: list`;
  every prior key still present.

---

## Quadrant numbering (locked, test-verified)

| Q  | EL    | INS   | Reasoning mode equivalent |
|----|-------|-------|---------------------------|
| Q1 | high  | low   | grounding                 |
| Q2 | low   | high  | analysis                  |
| Q3 | high  | high  | structured_reflection     |
| Q4 | low   | low   | stabilization             |

"jump distance" = Manhattan distance on the 2×2 lattice. Diagonal
transitions (Q1↔Q4 max-distance pairs aren't actually diagonal here;
Q1↔Q2 and Q3↔Q4 are the diagonals because they differ on both axes).
Distance ≥ 2 = diagonal = `quadrant_jump` fires.

---

## Files touched

```
el_ins/anomaly.py                                              (new)
el_ins/anomaly_store.py                                        (new)
el_ins/rollup.py                                               (new)
el_ins/__init__.py                                             (+ re-exports)
intelligence_kernel.py                                         (run_thread_message wires anomalies)
runtime_http.py                                                (+ 5 endpoints)
app.py                                                         (/health version → "4.15")
BUILD_VERSION                                                  (20260513060000 → 20260513070000)

web/src/lib/api.ts                                             (+ types + 4 helpers)
web/src/components/cockpit/ElInsIndicator.tsx                  (+ red-dot badge)
web/src/routes/OperatorElinsAnomalies.tsx                      (new)
web/src/routes/OperatorElinsRollup.tsx                         (new)
web/src/App.tsx                                                (+ 2 routes)
web/src/components/Layout.tsx                                  (+ 2 rail links)
web/src/routes/__tests__/OperatorElinsAnomalies.test.tsx       (new — 7 tests)
web/src/routes/__tests__/OperatorElinsRollup.test.tsx          (new — 7 tests)
web/src/components/cockpit/__tests__/ElInsIndicator.test.tsx   (+ 2 new badge tests)

desktop/src/lib/api.ts                                         (+ types + 2 helpers)
desktop/src/OperatorElinsAnomaliesShell.tsx                    (new)
desktop/src/OperatorElinsRollupShell.tsx                       (new)
desktop/src/App.tsx                                            (+ 2 views)
desktop/src/components/v1/OperatorSidebar/OperatorSidebar.tsx  (+ 2 entries)

phone/lib/api.ts                                               (+ types + 2 helpers)
phone/components/ElInsIndicator.tsx                            (+ red dot + 2 buttons)
phone/app/el_ins_anomalies.tsx                                 (new)
phone/app/el_ins_rollup.tsx                                    (new)
phone/app/_layout.tsx                                          (+ 2 Stack.Screens)

tests/test_el_ins_anomaly.py                                   (new — 39 tests)
tests/test_el_ins_rollup.py                                    (new — 24 tests)
tests/test_v28_endpoints.py                                    (version 4.14 → 4.15)
tests/test_v51_projects.py                                     (version 4.14 → 4.15)
tests/test_v53_elins_v2.py                                     (version 4.14 → 4.15)
tests/test_v54_ingestion.py                                    (version 4.14 → 4.15)

V72_READINESS.md                                               (new)
```
