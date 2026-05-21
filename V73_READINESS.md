# V73 — Units 82 + 83 (Operator timeline + Org-level timeline)

Status: ✅ Ready
Backend version: `4.16` (bumped from 4.15)
Build: `20260513080000`

---

## What this pass ships

### Unit 82 — Operator timeline

* **`el_ins/timeline.py`** — pure-Python event store. `TimelineEvent`
  TypedDict carries `{id (uuid4 hex), timestamp_ms (int), event_type,
  payload, operator_id}`. Event types locked to four:
  ``"record"`` / ``"anomaly"`` / ``"rollup"`` / ``"system"``.
  Newest-first per-operator, strict operator isolation, validation
  enforces enum + non-empty fields. Three event-builder helpers
  (`build_record_event`, `build_anomaly_event`, `build_rollup_event`)
  centralise payload shapes so producers stay consistent.

* **Kernel integration** in `run_thread_message`: after the v69
  per-turn EL/INS hook stores a record + v71 computes reasoning_mode
  + v72 detects anomalies, the kernel emits:
  * one `record` event with `{el, ins, tsi, reasoning_mode, thread_id}`
  * one `anomaly` event per anomaly with `{anomaly_id, type, severity, message}`

  Same fail-soft pattern — timeline failures are swallowed.

* **Rollup endpoint integration**: `_rollup_for()` in
  `runtime_http.py` emits a `rollup` event after computing the
  rollup, for the requesting operator only. Side effect on a GET
  endpoint, matching the spec ("audit-trail of when operators
  reviewed").

* **HTTP endpoints** (auth-gated, top-level `/timeline/*` per spec):
  * `GET /timeline?limit=N` — newest-first
  * `GET /timeline/since/{timestamp_ms}`
  * `GET /timeline/{event_id}` — 404 on cross-operator (no leak)
  * No POST surface — timeline is write-only from system events.

* **Web `/operator/timeline`** route — table + click-to-expand JSON
  modal. Cockpit `ElInsIndicator` gains a second dot (accent-cyan)
  when fresh timeline events exist (24h window). Layout RUNTIME rail
  gets "Timeline" link.

* **Desktop `OperatorTimelineShell`** — 1:1 mirror with modal.
  Sidebar `NAV_ITEMS` gains "Timeline".

* **Phone `timeline.tsx`** — tap-to-expand inline list (no modal per
  spec). Cockpit indicator card gets a "Timeline →" button.

### Unit 83 — Org-level timeline (aggregated)

* **`el_ins/org_timeline.py`** — `compute_org_timeline(window)` walks
  every operator's timeline and emits sanitised entries. Three
  canonical windows (24h / 7d / 30d).
  * Operator IDs **masked** to last 6 characters (`_OPERATOR_MASK_TAIL`).
  * Payloads **summarised** per-type via `_summarise_payload`:
    * `record`  → `{el, ins, tsi}`
    * `anomaly` → `{severity, rule}` (rule = type)
    * `rollup`  → `{window, avg_el, avg_ins}` (no avg_tsi)
    * `system`  → `{}`
  * Thread IDs, raw payloads, anomaly messages, anomaly_ids:
    **never surfaced**.

* **HTTP endpoints** (founder-cohort gated):
  * `GET /org/timeline/24h`
  * `GET /org/timeline/7d`
  * `GET /org/timeline/30d`

  Gated via new `require_founder` dependency in `runtime_http.py`
  — mirrors `app.py`'s `_require_founder` but lazy-imports
  `users_store` to avoid the circular import. Cohorts that pass:
  `"founder"`, `"founder_exception"`. Anyone else → 403.

* **Web `/org/el_ins/timeline`** route — three-tab switcher
  (24h/7d/30d) + sanitised table. Layout RUNTIME rail gets
  "Org Timeline" link. 403 from server (non-founder) surfaces inline
  rather than triggering RequireAuth.

* **Desktop `OrgTimelineShell`** — mirror with tab buttons.
  Sidebar gets "Org Timeline". 403 stays in the shell (doesn't bounce
  to SignIn) so non-founders see a clear error.

* **Phone `org_timeline.tsx`** — three collapsible text-only sections
  per spec.

---

## Endpoints (all auth-gated; org endpoints also founder-cohort gated)

| Method | Path                                  | Purpose                                  |
|--------|---------------------------------------|------------------------------------------|
| GET    | `/timeline?limit=N`                   | Operator's newest-first event log        |
| GET    | `/timeline/since/{timestamp_ms}`      | Events newer than timestamp_ms           |
| GET    | `/timeline/{event_id}`                | Single-event lookup (404 cross-operator) |
| GET    | `/org/timeline/24h`                   | Org aggregate over last 24h (founder)    |
| GET    | `/org/timeline/7d`                    | Org aggregate over last 7 days (founder) |
| GET    | `/org/timeline/30d`                   | Org aggregate over last 30 days (founder)|

---

## Test summary

| Suite                                             | Tests | Net |
|---------------------------------------------------|-------|-----|
| `tests/test_el_ins_timeline.py`                   | 35    | new |
| `tests/test_el_ins_org_timeline.py`               | 34    | new |
| `web/.../OperatorTimeline.test.tsx`               | 12    | new |
| `web/.../OrgTimeline.test.tsx`                    |  9    | new |
| `web/.../cockpit/ElInsIndicator.test.tsx`         |  2    | +2  |
| **Total new**                                     | **92**|     |

Full suites:
- Web: **173/173 passed** (150 prior + 23 net new).
- Backend: pending full-suite confirmation; focused EL/INS subset =
  **165/165 passed**.
- Desktop: tsc clean, vite build clean (323.82 KB JS, 87.85 KB gzip).

---

## Architecture invariants verified

* **No cross-operator leakage**: timeline endpoints scope by authed
  `operator_id` in every read path; org timeline masks operator IDs
  and summarises payloads (verified by `TestNoLeakage` —
  thread_ids and raw anomaly messages never appear in serialised
  responses).
* **Write-only from system events**: no POST endpoint exists for
  `/timeline/*`. Events land via the kernel hook and rollup endpoint
  side-effects only.
* **No raw payloads in org timeline**: `_summarise_payload`
  is the only path that produces org entries' `payload_summary`
  field. Verified by 4 contract tests + 3 leak-prevention tests.
* **Append-only**: no update/delete API. Future Firestore backend can
  enforce this at the store layer.
* **No analyzer / EL/INS record shape / kernel signature changes**:
  the integration is purely additive — `run_thread_message`
  emits new events but its return-dict keys are unchanged from v72
  (which already added `reasoning_mode` and `anomalies`).

---

## Files touched

```
el_ins/timeline.py                                            (new)
el_ins/org_timeline.py                                        (new)
el_ins/__init__.py                                            (+ re-exports)
runtime_http.py                                               (+ require_founder + 3 timeline + 3 org-timeline endpoints + 2 new routers; rollup endpoints emit timeline events)
intelligence_kernel.py                                        (run_thread_message emits record + anomaly timeline events)
app.py                                                        (+ include_router(timeline_router, org_timeline_router); /health → "4.16")
BUILD_VERSION                                                 (20260513070000 → 20260513080000)

web/src/lib/api.ts                                            (+ types + 4 helpers)
web/src/components/cockpit/ElInsIndicator.tsx                 (+ timeline accent dot)
web/src/routes/OperatorTimeline.tsx                           (new)
web/src/routes/OrgTimeline.tsx                                (new)
web/src/App.tsx                                               (+ 2 routes)
web/src/components/Layout.tsx                                 (+ 2 rail links)
web/src/routes/__tests__/OperatorTimeline.test.tsx            (new — 12 tests)
web/src/routes/__tests__/OrgTimeline.test.tsx                 (new —  9 tests)
web/src/components/cockpit/__tests__/ElInsIndicator.test.tsx  (+ 2 new dot tests)

desktop/src/lib/api.ts                                        (+ types + 2 helpers)
desktop/src/OperatorTimelineShell.tsx                         (new)
desktop/src/OrgTimelineShell.tsx                              (new)
desktop/src/App.tsx                                           (+ 2 views)
desktop/src/components/v1/OperatorSidebar/OperatorSidebar.tsx (+ 2 entries)

phone/lib/api.ts                                              (+ types + 2 helpers)
phone/components/ElInsIndicator.tsx                           (+ Timeline button)
phone/app/timeline.tsx                                        (new)
phone/app/org_timeline.tsx                                    (new)
phone/app/_layout.tsx                                         (+ 2 Stack.Screens)

tests/test_el_ins_timeline.py                                 (new — 35 tests)
tests/test_el_ins_org_timeline.py                             (new — 34 tests)
tests/test_v28_endpoints.py                                   (version 4.15 → 4.16)
tests/test_v51_projects.py                                    (version 4.15 → 4.16)
tests/test_v53_elins_v2.py                                    (version 4.15 → 4.16)
tests/test_v54_ingestion.py                                   (version 4.15 → 4.16)

V73_READINESS.md                                              (new)
```
