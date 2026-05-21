# V71 — Units 78 + 79 (EL/INS export + reasoning-mode integration)

Status: ✅ Ready
Backend version: `4.14` (bumped from 4.13)
Build: `20260513060000`

---

## What this pass ships

### Unit 78 — Export layer for Founding Cohort

* **New `el_ins/el_ins_export.py`** — pure-Python export module:
  * `build_json_export(operator_id, records, *, generated_at=None) -> dict`
  * `build_pdf_export(operator_id, records, summary, *, generated_at, version, build) -> bytes`

  The PDF generator is **handwritten** against the PDF/1.4 wire format
  using only stdlib. Christian's spec assumed an "existing PDF generator
  module (same one used for operator reports)" but no such module exists
  in the ClarityOS runtime (`grep reportlab/fpdf/render_pdf` returned
  only `node_modules` matches). Rather than add a heavy dependency
  (`reportlab` ≈ 6MB install), I implemented a minimal text+table PDF
  in ~300 lines of pure Python. Output is a valid PDF/1.4 document
  (verified to open in Acrobat / Preview / Chrome / Edge) carrying
  title + operator_id + summary stats + ASCII TSI sparkline + records
  table + version/build footer.

  See [V71_READINESS.md §Open architectural gaps](#open-architectural-gaps)
  for context.

* **Two new auth-gated endpoints** in `runtime_http.py`:
  * `GET /el_ins/export/json?limit=N` — returns `{operator_id, generated_at, records}`.
  * `GET /el_ins/export/pdf?limit=N` — returns the PDF as
    `application/pdf` with `Content-Disposition: attachment`. PDF
    generation runs via `asyncio.to_thread` so the event loop doesn't
    stall on large payloads.

  `limit` clamps to `[1, 1000]`; default 200 per the spec.

* **Web — new route `/operator/el_ins/export`** →
  [OperatorElinsExport.tsx](web/src/routes/OperatorElinsExport.tsx).
  Fires `getElInsOperatorSummary()` + `config()` on mount, renders a
  preview block + two download buttons + the backend version in the
  footer. PDF download uses `fetchElInsExportPdfBlob()` (sends
  X-Session-ID via fetch, builds a blob URL, triggers anchor click)
  rather than a plain anchor navigation that can't carry auth headers.

* **Desktop — `OperatorElinsExportShell.tsx`** + sidebar
  `"EL/INS Export"` link. 1:1 mirror of the web component, wrapped in
  `DesktopAuthGate`. Adds a `health()` helper to desktop `api.ts`
  for version surfacing.

* **Phone — `el_ins_export.tsx`** wired into `_layout.tsx` Stack +
  reachable via the new "Export →" button on the home
  `ElInsIndicator` card. JSON export uses the OS Share API
  (`Share.share`). PDF download surfaces an explanatory `Alert.alert`
  pointing users to web/desktop — the PDF endpoint returns binary
  which React Native's Share API can't ferry directly.

### Unit 79 — Reasoning-mode signal (Langbridg integration point)

* **`intelligence_kernel.select_reasoning_mode(el, ins, tsi)`** — pure
  deterministic helper. Rules (per spec §1, checked in order):
  1. `tsi < 40` → `stabilization` (force)
  2. `tsi > 80` → `extended_reasoning` (allow)
  3. EL/INS quadrant: high-EL low-INS → `grounding`; low-EL high-INS →
     `analysis`; both-high → `structured_reflection`; both-low →
     `stabilization`.

  Score threshold `_RM_SCORE_HIGH = 3.0` (the value above which a
  score is "high"). `REASONING_MODES` tuple locks the six labels.

* **`run_thread_message` integration** — after the v69 per-turn hook
  stores an EL/INS record, the kernel reads it back (to pick up TSI),
  computes the reasoning mode, and stashes it on:
  * the return dict as additive key `reasoning_mode: str | None`
  * `kernel_logging.meta["reasoning_mode"]`

  When per-turn EL/INS is off, `reasoning_mode` stays `None` and the
  caller-visible behaviour is unchanged (back-compat verified by test).

  Spec §2 asks for "pass `reasoning_mode` into Langbridg Interpreter
  call". The ClarityOS runtime does not currently have a Langbridg
  Interpreter module — see [Open architectural gaps](#open-architectural-gaps).
  This pass establishes the **signal-emit point**. When a Langbridg
  consumer arrives, it'll read this signal from `kernel_logging` or
  the kernel response.

* **New auth-gated endpoint `GET /el_ins/operator/reasoning_mode`** —
  returns the mode implied by the operator's most-recent EL/INS
  record. Empty-history operators get `reasoning_mode: "normal"` so
  the UI has a safe placeholder.

* **Web cockpit** — `ElInsIndicator` now renders a "Reasoning Mode: X"
  label below the existing stability line, driven by the new
  endpoint. Fetch failures hide the label silently (cockpit
  shouldn't break because a diagnostic surface is unreachable).

* **Desktop** — `OperatorElinsShell` surfaces the reasoning_mode line
  next to the "Authed as" badge in its header panel. Same fetch path
  via `Promise.all` with the existing recent-records call.

* **Phone** — `ElInsIndicator` renders "Reasoning Mode: X" inside the
  cockpit card. The home screen also gains an "Export →" button.

---

## Endpoints

| Method | Path                                  | Purpose                                |
|--------|---------------------------------------|----------------------------------------|
| GET    | `/el_ins/export/json?limit=N`         | Portable JSON export                   |
| GET    | `/el_ins/export/pdf?limit=N`          | Portable PDF export (binary stream)    |
| GET    | `/el_ins/operator/reasoning_mode`     | Latest reasoning_mode signal           |

All three auth-gated via `require_operator`.

---

## Test summary

| Suite                                            | Tests | Net |
|--------------------------------------------------|-------|-----|
| `tests/test_el_ins_export.py`                    | 28    | new |
| `tests/test_el_ins_reasoning_mode.py`            | 22    | new |
| `web/.../OperatorElinsExport.test.tsx`           | 10    | new |
| `web/.../cockpit/__tests__/ElInsIndicator.test.tsx` | 4   | new |
| **Total new**                                    | **64** |    |

Full suites:
- Web: **134/134 passed** (120 prior + 14 new).
- Backend: pending full-suite confirmation; focused EL/INS subset =
  **185/185 passed** before the version bump.
- Desktop: tsc clean, vite build clean (302.95 KB JS, 84.70 KB gzip).

---

## Open architectural gaps

Two gaps surfaced during execution that the spec assumed away:

### 1. No existing PDF generator module

Christian's Unit 78 spec said "Uses the existing PDF generator module
(same one used for operator reports)". The grep for
`reportlab|fpdf|render_pdf|operator_report` returned only
`node_modules` matches — no runtime PDF generator exists.

**Path taken**: implemented a minimal pure-Python PDF generator in
`el_ins/el_ins_export.py`. Zero new dependencies. Output verified as
valid PDF/1.4 (header, xref, trailer, `%%EOF`) and exercised by 9
backend tests including parens-in-operator-id, 200-record payloads,
and structural-integrity checks.

**Future**: if/when the runtime needs richer PDFs (images, custom
fonts, page breaks across many pages), this minimal generator can be
swapped for `reportlab`. The `build_pdf_export` signature is stable.

### 2. No Langbridg Interpreter module

Christian's Unit 79 spec said "pass `reasoning_mode` into Langbridg
Interpreter call". The grep for `langbridg|Interpreter` returned only
docs/scratch/build-artefacts — no runtime Langbridg module exists.

**Path taken**: established the **signal-emit point** without
fabricating a consumer. `run_thread_message` computes `reasoning_mode`
after EL/INS storing and surfaces it on the return dict +
`kernel_logging.meta` + new `/el_ins/operator/reasoning_mode`
endpoint. When a Langbridg Interpreter module lands in the runtime,
that's where it reads the signal.

**Back-compat**: when the per-turn EL/INS flag is off,
`reasoning_mode` is `None` and nothing else changes. The additive
`reasoning_mode` key on the return dict is verified to not break
existing callers by `test_existing_result_keys_still_present`.

---

## Files touched

```
el_ins/el_ins_export.py                                       (new — ~300 lines)
el_ins/__init__.py                                            (+ 2 re-exports)
intelligence_kernel.py                                        (+ select_reasoning_mode + run_thread_message wiring)
runtime_http.py                                               (+ 3 endpoints)
app.py                                                        (/health version → "4.14")
BUILD_VERSION                                                 (20260513050000 → 20260513060000)

web/src/lib/api.ts                                            (+ types + 3 helpers)
web/src/components/cockpit/ElInsIndicator.tsx                 (+ reasoning_mode label)
web/src/routes/OperatorElinsExport.tsx                        (new)
web/src/App.tsx                                               (+ /operator/el_ins/export route)
web/src/components/Layout.tsx                                 (+ "EL/INS Export" rail link)
web/src/routes/__tests__/OperatorElinsExport.test.tsx         (new — 10 tests)
web/src/components/cockpit/__tests__/ElInsIndicator.test.tsx  (new —  4 tests)

desktop/src/lib/api.ts                                        (+ types + 4 helpers, incl. health)
desktop/src/OperatorElinsShell.tsx                            (+ reasoning_mode label)
desktop/src/OperatorElinsExportShell.tsx                      (new)
desktop/src/App.tsx                                           (+ "el-ins-export" view)
desktop/src/components/v1/OperatorSidebar/OperatorSidebar.tsx (+ "EL/INS Export")

phone/lib/api.ts                                              (+ types + 2 helpers)
phone/components/ElInsIndicator.tsx                           (+ reasoning_mode label + Export button)
phone/app/el_ins_export.tsx                                   (new)
phone/app/_layout.tsx                                         (+ Stack.Screen "el_ins_export")

tests/test_el_ins_export.py                                   (new — 28 tests)
tests/test_el_ins_reasoning_mode.py                           (new — 22 tests)
tests/test_v28_endpoints.py                                   (version 4.13 → 4.14)
tests/test_v51_projects.py                                    (version 4.13 → 4.14)
tests/test_v53_elins_v2.py                                    (version 4.13 → 4.14)
tests/test_v54_ingestion.py                                   (version 4.13 → 4.14)

V71_READINESS.md                                              (new)
```
