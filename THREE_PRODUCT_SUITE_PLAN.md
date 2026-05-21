# Three-Product Intelligence Suite — Plan

**Status:** Phase 1 (repo prep). Module skeletons land in this commit;
no app.py wiring, no scheduler boot, no real data sources. Phase 2
follows when the four decisions are confirmed.

**Date:** 2026-05-11

---

## 1. Summary

ClarityOS will host three independent intelligence products with a
clear data-flow boundary (no circular dependencies):

```
   ┌─────────────────────────┐    ┌─────────────────────────┐
   │   EMAIL EP DASH         │    │   PERSONAL NEWS BASIN   │
   │   (email-only)          │    │   (news-only)           │
   │   cadence: on-demand    │    │   cadence: 2× / day     │
   └────────────┬────────────┘    └────────────┬────────────┘
                │                              │
                │   feeds                      │   feeds
                ▼                              ▼
              ┌──────────────────────────────────────┐
              │   DAILY PERSONAL ELINS               │
              │   (macro ↔ meso ↔ micro mix)         │
              │   cadence: 1× / day                  │
              │   consumes personal signals + the    │
              │   two products above + macro ELINS   │
              └──────────────────────────────────────┘
```

All three are orchestrated by a new `intelligence_scheduler.py`
which subsumes (does not replace) the existing `elins_scheduler.py`
cadence loop.

---

## 2. The Four Pinned Decisions

| # | Decision | Phase-1 commitment |
|---|---|---|
| 1 | **Email ingest source** | Manual paste / forward channel first. No IMAP, no Gmail API. Lowest risk; respects ClarityOS's no-skills, no-plugins boundary. IMAP/Gmail connector is a Phase 2+ option. |
| 2 | **News basin source** | Extend `perplexity_oracle.py` (v41) with a per-user source list (≤13). RSS connector deferred. Reuses existing ESO fetcher + sanitisation. |
| 3 | **Daily report destination** | Render inside `InsightsPanel` first (cheap; reuses v1 shell). A `/daily` route on desktop + web is a Phase 2 stretch. |
| 4 | **Scheduler** | New `intelligence_scheduler.py`. Coordinates the three products' cadences. **Existing `elins_scheduler` is preserved** — it becomes one of the cadences the new scheduler orchestrates (or stays standalone if the operator prefers; the new module accommodates both topologies). |

---

## 3. The Three Products

### 3.1 DAILY PERSONAL ELINS
- **Module:** `daily_personal_elins.py` (skeleton in this commit).
- **Mission:** Produce one daily intelligence report that fuses
  personal signals, email signals, news signals.
- **Inputs:**
  - macro ELINS run summary from `elins_project.get_macro_run(...)`
  - email dash snapshot from `email_ep_dash.get_snapshot(user_id)`
  - news basin synthesis from `personal_news_basin.get_synthesis(user_id, period)`
  - personal signals from `operator_state` + `intelligence_kernel`
- **Output envelope (3 sections):** MACRO / MESO / MICRO with bounded
  field counts per the operator-grade spec.
- **Cadence:** 1× / day. Composed lazily on first read each day; cache
  on success.
- **Dependencies:** `email_ep_dash`, `personal_news_basin`,
  `elins_project`, `operator_state`, `intelligence_kernel`.

### 3.2 EMAIL EP DASH
- **Module:** `email_ep_dash.py` (skeleton in this commit).
- **Mission:** Email-only intelligence dashboard. No news, no personal
  ELINS contamination — the spec is explicit on isolation.
- **Inputs:**
  - paste/forward channel: raw email blobs the user submits
    (sender / subject / body / timestamp)
  - thread context derived from sender + subject normalisation
  - per-email `intelligence_kernel.run_emotional_physics`
- **Output envelope (4 sections):** TRIAGE, ACTION EXTRACTION,
  PATTERN ANALYSIS, EP FILTER.
- **Cadence:** on-demand (user click) or continuous (background poll
  when inbox grows). Phase 1 surfaces on-demand only.
- **Dependencies:** `intelligence_kernel.run_emotional_physics`,
  `memory_vault` (per-user storage).

### 3.3 PERSONAL NEWS BASIN EP
- **Module:** `personal_news_basin.py` (skeleton in this commit).
- **Mission:** Collect, classify, curate news from the user's chosen
  sources (≤13) and build a personal news intelligence archive.
- **Inputs:**
  - user-configured source list (≤13 sources, per spec cap)
  - perplexity_oracle fetcher (existing ESO infrastructure)
  - per-headline EP classifier (intelligence_kernel)
- **Output envelope (3 components):** COLLECTION, CURATION, SYNTHESIS.
- **Cadence:** 2× / day. Synthesis cadences: weekly + monthly rollup.
- **Dependencies:** `perplexity_oracle`, `intelligence_kernel`,
  `elins_entity_graph`, `memory_vault`.

---

## 4. The Intelligence Scheduler

- **Module:** `intelligence_scheduler.py` (skeleton in this commit).
- **Cadence policy:**
  - `daily_personal_elins`: 1× / day at user's local time (default 05:00)
  - `personal_news_basin`: 2× / day (default 06:00 + 18:00)
  - `email_ep_dash`: on-demand (manual trigger via API)
- **Env-var gate:** `CLARITYOS_DISABLE_INTELLIGENCE_SCHEDULER=1` to skip boot.
- **Relationship to `elins_scheduler`:** Phase 1 leaves `elins_scheduler`
  untouched. Phase 2 can either (a) leave both running independently or
  (b) have `intelligence_scheduler` orchestrate the macro cadence by
  importing the existing `_run_macro_elins_once` helper. The skeleton
  documents both topologies and picks (a) as the default until the
  operator confirms.
- **Public API:**
  - `start()` / `stop()`
  - `get_status() -> dict` (for a future `/founder/intelligence/scheduler/status` endpoint)
  - `_run_daily_personal_elins_once(user_id)`,
    `_run_news_basin_once(user_id)` test hooks
  - `set_cadence(product, cadence)` config setter

---

## 5. What's Prepared in This Commit

```
THREE_PRODUCT_SUITE_PLAN.md      ← this file
intelligence_scheduler.py        ← cadence orchestrator (skeleton)
daily_personal_elins.py          ← report composer (skeleton)
email_ep_dash.py                 ← email-only intelligence (skeleton)
personal_news_basin.py           ← news basin curator (skeleton)
```

All four `.py` modules:
- Have full docstring + I/O contract
- Use only stdlib + type hints (no business-logic imports yet)
- Stub public functions with `NotImplementedError` and a clear TODO
- Are **not** imported by `app.py` — no live routes yet
- Are **not** registered with any scheduler boot path

---

## 6. What's NOT Done (Phase 2)

- Wire the four modules into `app.py` with public + founder endpoints
- Implement real fetch/synthesise/compose logic in each module
- Implement `intelligence_scheduler.start()` cadence loop
- Wire the daily report into `InsightsPanel` (desktop + web)
- Add operator config UI (cadence, source list, paste channel)
- Add tests:
  - `tests/test_intelligence_scheduler.py`
  - `tests/test_daily_personal_elins.py`
  - `tests/test_email_ep_dash.py`
  - `tests/test_personal_news_basin.py`

---

## 7. Sequencing for Phase 2

Suggested order (smallest reviewable units first):

1. `personal_news_basin.py` real impl + tests (lowest risk; reuses
   perplexity_oracle which is already wired)
2. `email_ep_dash.py` real impl + tests (manual paste channel only)
3. `daily_personal_elins.py` real impl + tests (depends on 1 + 2)
4. `intelligence_scheduler.py` real impl + tests (depends on 1–3)
5. `app.py` route registration: one route block per product
6. Surface wiring: desktop InsightsPanel new tab, then web mirror
7. Operator UI for cadence + source-list config

Each unit ships as its own slice with build + tests passing before
the next begins.
