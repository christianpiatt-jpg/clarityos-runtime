# V43 Readiness — UX polish + founder analytics surfaces

Status: ✅ Ready
Backend version: `3.9`
Analytics version: `founder_analytics.v43.1`
Build: `20260507500000`

---

## What v43 ships

A founder-only analytics aggregator that joins users / billing /
intelligence stores into a single read-only summary, plus a UX polish
pass on the cockpit + dashboard surfaces (web + phone). Loading
skeletons and empty states make the analyst feel immediate and legible
even when no macro pass has fired yet.

No backend contracts changed beyond the additive `/founder/analytics/summary`
endpoint + a small `users_store.list_all_usernames` helper.

---

## Files added / changed

### New
- `founder_analytics.py` — pure read-side aggregator;
  `get_founder_analytics_summary(now_ts=None)`.
- `web/src/components/founder/analytics/FounderAnalyticsSummary.tsx`
- `web/src/components/cockpit/ElinsQuicklook.tsx`
- `phone/app/founder_analytics.tsx`
- `tests/test_v43_ux_and_analytics.py` — 16 tests.
- `V43_READINESS.md` (this file).

### Modified
- `users_store.py` — new `list_all_usernames()` helper (memory +
  Firestore backends); used by `founder_analytics`.
- `app.py`:
  - Imports `founder_analytics`.
  - New `GET /founder/analytics/summary` (founder).
  - Capability `founder_analytics` added to `/me`.
  - Backend version `3.9`; root listing extended.
- `web/src/lib/api.ts` — `V43FounderAnalyticsSummary` +
  `founderAnalyticsSummary()` helper.
- `web/src/routes/Cockpit.tsx` — tightened CTA copy ("Open ELINS →"
  with title attribute), inlined `ElinsQuicklook` panel under the
  onboarding wizard.
- `web/src/components/founder/FounderDashboard.tsx` — embeds
  `FounderAnalyticsSummary` as full-width row.
- `web/src/components/dashboard/DashboardRoot.tsx` — replaces the
  spinner with a `DashboardSkeleton` (5 placeholder cards).
- `phone/lib/api.ts` — `V43FounderAnalyticsSummary` +
  `founderAnalyticsSummary()` helper.
- `phone/app/_layout.tsx` — register `founder_analytics` stack screen.
- `phone/app/founder.tsx` — `Analytics` shortcut after Dashboard.
- `phone/app/dashboard.tsx` — replaces spinner with a 4-card
  skeleton; `ActivityIndicator` import dropped (unused now).
- `tests/test_v28_endpoints.py` — health version `3.9`.
- `BUILD_VERSION` — `20260507500000`.

---

## API surface

### `GET /founder/analytics/summary` (founder)
```jsonc
{
  "ok": true,
  "summary": {
    "users":         { "total": 42, "active_7d": 18, "active_30d": 31 },
    "billing":       { "active_subscriptions": 12, "past_due": 1, "canceled": 3, "mode": "test" },
    "intelligence":  { "elins_runs_7d": 87, "g_runs_7d": 14, "macro_runs_7d": 9, "eso_usage_rate_7d": 0.78 },
    "ts":            1715080800.123,
    "version":       "founder_analytics.v43.1"
  }
}
```

Fields are deterministic given a fixed snapshot of the underlying
stores and a fixed `now_ts`. The function never mutates state.

---

## ESO usage rate

```
eso_usage_rate_7d = (# macro runs in last 7d with external_signal_mode == "cloud_perplexity")
                  / (# macro runs in last 7d)
```

Returns `0.0` when no runs exist in the window. Rounded to 4 decimals.

This approximation uses `elins_project.list_macro_runs` directly,
since `kernel_logging` records aren't persisted to a store. The macro
record carries the resolved `external_signal_mode` per pass, so this
is a proper count rather than an approximation when macro is the
primary ESO consumer.

---

## UX polish

### Web
- **Cockpit header CTA** simplified: `Open ELINS →` (with `title`
  tooltip) instead of two competing buttons. Feed access kept as a
  smaller `Feed` button.
- **`ElinsQuicklook`** card lives directly under the onboarding
  wizard (when `v28_surfaces` is on). Shows:
  - "last macro run <ts> · ep <mean>" line, OR an italicised empty
    state ("No macro runs yet — kick one off from the founder
    console or wait for the next scheduled tick.")
  - ESO mode pill (`ESO perplexity` / `ESO off`).
- **Dashboard `/dashboard`** swaps the spinner for a `DashboardSkeleton`
  with 5 placeholder cards (global, regional, macro, entity,
  continuity). Existing `available: false` empty states inside
  `GlobalPanel` / `RegionalGrid` / `MacroSummary` / `EntitySummary`
  already covered the no-data scenarios; v43 just makes the loading
  state honest.
- **Founder console** gains a full-width `Analytics` panel with
  three lightweight stat cards (Users / Billing / Intelligence). No
  charts; small bars for active rate and ESO usage rate.

### Phone
- **`dashboard.tsx`** replaces the `ActivityIndicator` with a
  4-card skeleton; pull-to-refresh continues to call
  `/elins/dashboard` (unchanged). Empty-state strings on macro /
  entity sections were already in place from v38; this pass just
  removes the spinner so loading + empty are visually distinguishable.
- **`founder_analytics.tsx`** is the founder-only screen reflecting
  the same metrics in a stacked-card layout. `Analytics` shortcut
  added to the founder hub, right after Dashboard.

---

## Tests

```
tests/test_v43_ux_and_analytics.py — 16 tests, all pass
Full suite — 516 passed, 0 failed
```

Coverage:
- `get_founder_analytics_summary`:
  - Empty state returns zeroes everywhere.
  - User total counts every entry in `list_all_usernames()`.
  - 7d / 30d active windows respect `operator_state.last_active_ts`.
  - Billing aggregation counts `active`, `past_due` (incl.
    `grace_period`), `cancelled`.
  - Intelligence run counts respect the 7d cutoff.
  - ESO usage rate computed correctly for 4-of-3 mock data; older
    runs excluded from the window.
  - Determinism for fixed `now_ts` + fixed store state.
  - Output shape matches the spec.
- `/founder/analytics/summary`:
  - Founder-only gate.
  - Shape matches spec; reflects runtime state after a macro pass.
- `/me` advertises `founder_analytics` capability.
- Dashboard empty-state contract: fresh users see
  `macro.last_run_id == None`, `entity_graph.available == False`,
  every region `available == False`.
- After a macro pass, `last_run_id` populates and the entity-graph
  block returns the right `available` flag.
- `users_store.list_all_usernames` round-trip on the memory backend.

---

## Notes / follow-ups

- The "active_7d / active_30d" counts use
  `operator_state.last_active_ts`, which is bumped on every
  `record_elins_interaction` / `record_g_run`. Users who only browse
  the cockpit without running ELINS / #G will not appear as active.
  When session-tracking lands, swap in a session-bucket join.
- `eso_usage_rate_7d` is currently macro-driven. When manual
  `/elins/regional/run` invocations start to dominate, lift the count
  into a kernel-log-derived metric (which the spec already allowed
  for as a future approximation path).
- Pre-v43 surfaces (v28–v42) are unchanged. The new endpoint,
  capability, skeleton screens, and analytics panel are additive.
