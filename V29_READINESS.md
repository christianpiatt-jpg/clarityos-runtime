# ClarityOS v29 — Hardening + Launch Readiness Report

**Build:** `20260506100000`
**Backend version:** `2.5`
**Status:** Ready for Cohort 1 rollout (Founders + Terrace 1).

This pass added validation/rate-limit/feature-flag scaffolding to the v28
surfaces, hardened the cockpit + ELINS UIs (web + phone), seeded an
onboarding wizard + demo-data path, and locked in security + performance
invariants under tests.

All 64 tests pass under in-memory backends.

---

## 1. Backend hardening — file-by-file

### `v29_hardening.py` (new)
Reusable hardening primitives. No FastAPI imports at module-load time.
* `ValidationError` + `raise_validation` — translate into the project's
  `error_response` envelope (400 default, configurable status).
* `require_str / require_int / require_dict / require_bool / require_one_of` —
  type checks, length limits, range checks, required-field enforcement.
* `validate_mesh_payload` — composite validator for `/mesh/sync` (16 KB
  serialized cap + 64-key cap + non-empty device_id ≤ 128 chars).
* `check_rate_limit / enforce_rate_limit` — in-memory token bucket per
  `(user, route)`. Logs only by default; flip
  `CLARITYOS_RATE_LIMIT_ENFORCE=1` to 429.
* `log_event / TimedBlock / redact_user` — structured single-line logs.
  User-ids are truncated; dicts/lists are coerced to `<key>_count=N`.
* `feature_enabled / set_flag / list_flags` — registry with default,
  per-user, and per-cohort overrides. User overrides win over cohort,
  cohort wins over default.
* `DEMO_VAULT_ITEMS / DEMO_TIMELINE_EVENTS` — seeds for empty accounts.

### `app.py` — v28 endpoint hardening
Each v28 route now:
1. Validates input via `v29_hardening.require_*`.
2. Gates on `feature_enabled("v28_surfaces", user, cohort)` (where
   applicable; `/sessions`, `/runtime/envelope`, `/engines` are not gated
   so the cockpit's basic shell still loads).
3. Calls `enforce_rate_limit(user, route)` (logging-only by default).
4. Emits a `log_event(...)` line on completion with timing and result
   counts (no user content).

| Endpoint | Validation | Flag-gated | Rate-limited | Logs |
|---|---|---|---|---|
| `POST /elins/g/run` | scenario_text length | yes | yes | `elins_g_run` |
| `POST /elins/daily/queue` | scenario + hour/minute + bools | yes | yes | `elins_daily_queue` |
| `GET  /elins/daily/feed` | `limit` 1–500 | yes | yes | `elins_daily_feed` |
| `POST /mesh/sync` | composite mesh validator | yes | yes | `mesh_sync` |
| `GET  /mesh/state` | – | yes | yes | `mesh_state` |
| `GET  /continuity/snapshot` | – | yes | yes | `continuity_snapshot` |
| `GET  /sessions` | `limit` 1–500 | – | yes | `sessions_list` |
| `GET  /runtime/envelope` | – | – | yes | `runtime_envelope` |
| `GET  /engines` | – | – | yes | – |

### `app.py` — `require_session`
Now also surfaces the user's `cohort` (from `users_store`) so feature
flags can be evaluated without a second store hit. Falls back to `None`
if the lookup fails — flag check then misses cohort but user override
still applies.

### `app.py` — startup
After `_bootstrap_admin()`, the launch cohort defaults are applied:
```python
for _coh in (COHORT_FOUNDER, COHORT_FOUNDER_EXCEPTION, COHORT_TERRACE_1):
    v29_hardening.set_flag("v28_surfaces", True, cohort=_coh)
    v29_hardening.set_flag("onboarding_v1", True, cohort=_coh)
    v29_hardening.set_flag("whats_new_v28", True, cohort=_coh)
```
Idempotent on every boot. Default-off for any cohort outside that set.

### `app.py` — new endpoints
* `GET  /v29/flags` — current user's flag map (admin sees raw defaults too).
* `GET  /v29/onboarding/state` — first-run progress.
* `POST /v29/onboarding/complete` — atomically mark a step done.
* `POST /v29/onboarding/seed` — idempotent demo-data seeder for empty
  accounts (writes to vault + timeline via existing storage layer).
* `GET  /v29/whats_new` — static "what's new in v28" panel content.

### `app.py` — `/me` extension
`/me` now returns `features` (the gated flag map) and `onboarding`
(the user's checklist progress) so the cockpit can render once without
chained fetches.

### `app.py` — version bump
`/health` and `/` now report `version: 2.5`. The endpoint catalog in `/`
was extended with the four `/v29/*` entries.

---

## 2. Test suite expansion

`tests/` (new). 64 tests, all green. Pure-Python (`pytest`); the test
runner spins the FastAPI app via a sync wrapper around
`httpx.AsyncClient(transport=httpx.ASGITransport(...))` so we don't
depend on `starlette.testclient` (which is incompatible with the locally
installed httpx 0.28).

| File | Coverage |
|---|---|
| `tests/conftest.py` | sys.path, env, store-reset fixtures, `AppClient` sync wrapper, `flags_clean` fixture |
| `tests/test_v29_hardening.py` | 27 tests — validators, mesh payload, rate limiter, flags, structured logging redaction |
| `tests/test_v28_endpoints.py` | 33 tests — `/elins/g/run`, `/elins/daily/queue` + scheduler delivery, `/mesh/sync` (oversize + LRU), `/continuity/snapshot` shape, `/runtime/envelope` 21-layer + vector strip, `/sessions`, `/engines`, `/v29/onboarding/*`, `/v29/onboarding/seed` idempotency, 401 contract on every gated route |
| `tests/test_v28_security.py` | 4 tests — invariants pinned: scenario text never persists post-delivery, raw float vectors never reach `/runtime/envelope`, Dewey origin_vector never returned, `log_event` never embeds caller payload values |

Run: `python -m pytest tests/ -q`

---

## 3. Web hardening (`web/src/...`)

### `lib/api.ts`
Added `V29Flag`, `V29FlagsResponse`, `V29OnboardingState`, `V29WhatsNew`
types and the four `/v29/*` helpers.

### `hooks/useFlags.ts` (new)
Module-level cache + in-flight de-dup so multiple components share a
single `/v29/flags` fetch. Defaults to all-false on failure (conservative
rollout).

### `routes/Cockpit.tsx`
* Mounts `<OnboardingWizard />` when `onboarding_v1` is on AND
  `/v29/onboarding/state.done` is false.
* Mounts `<WhatsNewPanel />` when `whats_new_v28` is on.
* Hides the ELINS link + Continuity surface when `v28_surfaces` is off.
* Wraps every panel in a `class ErrorBoundary` so a single panel crash
  doesn't blank the cockpit. Each banner has a manual Retry button.
* Adds `flagsLoading / snapshotLoading / meshLoading` indicators in the
  header so slow networks show progress instead of frozen UI.

### `routes/Elins.tsx`
* Hard-blocks (with a friendly empty state) when `v28_surfaces` is off.
* Validates scenario length client-side against `SCENARIO_MAX_LEN` so
  the user sees a clear message before the round-trip.
* Defensive `AnalysisRender` — every accessor guards against missing
  fields (e.g. partial backend response when no Dewey neighborhoods).
* Refresh button shows "Refreshing…" while the feed reload is in flight;
  feed errors render with a Retry button.
* Live char counter on the textarea.

### `components/cockpit/OnboardingWizard.tsx` (new)
Three-step checklist (vault check, Dewey sync, continuity snapshot) +
optional demo-data seeder. Posts to `/v29/onboarding/complete` per step.
Hidden once `done`.

### `components/cockpit/WhatsNewPanel.tsx` (new)
Reads `/v29/whats_new` and renders the static entries (v28 + v29). Each
entry is an expandable `<details>` block with bullet highlights.

`tsc --noEmit` — clean (exit=0).

---

## 4. Phone hardening (`phone/...`)

### `lib/api.ts`
Added `V29Flag`, `V29FlagsResponse`, and the three `/v29/*` helpers used
by the phone (`v29Flags`, `v29OnboardingState`, `v29OnboardingComplete`).

### `lib/hooks/useFlags.ts` (new)
Same intent as the web version, plus an AsyncStorage cache (key
`clarityos.v29_flags`) so launching offline still surfaces the last-known
flag map. Cache hydrates synchronously before the network fetch.

### `app/elins.tsx`
* Hard-blocks (friendly empty state) when `v28_surfaces` is off.
* `RefreshControl` for pull-to-refresh on the daily feed.
* AsyncStorage cache (`clarityos.elins_feed_cache`) — last-known feed is
  loaded on mount before the network fetch, so offline launches show
  something instead of "No delivered reports yet."
* Live char counter on the scenario textarea.
* Defensive `AnalysisRender` mirroring the web version.
* Error banners include an explicit Retry / Dismiss action.
* Typography, spacing, and button styles unchanged from v28 (the design
  system tokens are the same).

`tsc --noEmit` — no new errors introduced (the two pre-existing
`ingest.tsx` / `invite/[token].tsx` errors are unrelated to v29).

---

## 5. Onboarding + launch readiness

### Feature flags
* `v28_surfaces` — gates `/elins/*`, `/mesh/*`, `/continuity/snapshot`.
  Default off; on for Founders + Founder-Exception + Terrace 1.
* `onboarding_v1` — first-run wizard. Default-on for the launch cohort.
* `whats_new_v28` — cockpit panel. Default-on for the launch cohort.
* `demo_data` — seeds for empty accounts. Default off (opt-in via the
  wizard).
* `rate_limit_logging` — emits `log_event` on overflow (default on).

### Onboarding flow
Three checkpoints, each one a vault/Dewey/snapshot probe. Stored as
`onboarding[step] = ts` on the user document; `done: ts` set when the
last step lands. Idempotent re-clicks just bump the timestamp.

### Demo data
`POST /v29/onboarding/seed` writes two welcome notes (`vault.write`) and
one timeline event (`system.welcome`). Skipped if the vault already has
items — never duplicates seeds.

### "What's new in v28"
`GET /v29/whats_new` returns the static entry list (v28 + v29). Read by
the cockpit's `WhatsNewPanel` and gated by `whats_new_v28`. Edit
`app.py:v29_whats_new` to add v30+ entries.

### First-run experience
On signup the user lands on the cockpit with:
1. The onboarding wizard at the top (until done).
2. The "What's new" panel beside it.
3. All deterministic panels rendering empty-but-stable (vault, sessions,
   continuity surface).
4. Optional demo data via the wizard.

If anything 5xx's during initial fetch, each panel shows its own error
banner with Retry — the cockpit shell still renders.

---

## 6. Security pass — confirmed

| Invariant | How we know |
|---|---|
| Scenario text never persists post-delivery | `elins_distribution_store.deliver()` pops the queued record and stores only `scenario_id` (sha256 prefix). Locked by `test_delivered_record_has_scenario_id_not_text`. |
| Envelope vectors never leak to surfaces | `/runtime/envelope` strips `envelope_vector`, `envelope_centroid`, `events[*].vector`, `episodes[*].episode_vector`, `narratives[*].{node_vector,compressed_vector}`, `story_arcs[*].{arc_vector,arc_vector_compressed}`, `identity.identity_vector`, `trajectory.trajectory_vector`, `elins.mean_center_vector`, `elins_briefs[*].object_vector`. Test `test_runtime_envelope_strips_all_vectors` recursively walks the response and fails on any list-of-floats. |
| Dewey metadata never includes origin vectors | `/metadata/dewey` returns only `{neighborhood_id, name, curvature, has_origin_vector}`. Test `test_dewey_metadata_endpoint_never_returns_origin_vector` pins this. |
| Logs contain no user content | `v29_hardening.log_event` coerces dict/list/set/tuple values to `<key>_count=N`; primitives are pass-through but the v28 endpoints only pass redacted ids + numeric counts + route names. Test `test_log_event_does_not_embed_user_content`. User identifiers are truncated via `redact_user` to a 12-char prefix. |

---

## 7. Performance pass — confirmed

| Operation | Complexity | Note |
|---|---|---|
| Envelope rendering (`EnvelopeRenderer`) | O(layers) — 21 fixed | Layers expanded lazily via `<details>`; nested objects rendered with bounded slice (25 items, 6 inline values). |
| Mesh sync (`mesh_metadata_store.upsert_device`) | O(D log D), D ≤ 8 | LRU sort capped at the 8-device limit. |
| Daily scheduler (`_scheduler_one_pass`) | O(N due users × K queued per user) | Memory backend scans `_MEMORY` once; Firestore version uses a stream with `scheduled_for_ts <= now` filter (acceptable for v1; index recommended at scale). |
| Phone ELINS feed | Stable keys (`report_id`), `useMemo` on character counter; `AnalysisRender` reads only what it renders | Pull-to-refresh wired via `RefreshControl`. |

---

## 8. Files touched

**New**
* `v29_hardening.py`
* `tests/conftest.py`
* `tests/test_v29_hardening.py`
* `tests/test_v28_endpoints.py`
* `tests/test_v28_security.py`
* `web/src/hooks/useFlags.ts`
* `web/src/components/cockpit/OnboardingWizard.tsx`
* `web/src/components/cockpit/WhatsNewPanel.tsx`
* `phone/lib/hooks/useFlags.ts`
* `V29_READINESS.md` (this file)

**Modified**
* `app.py` — import + v28 hardening + `require_session` cohort + startup
  flag bootstrap + `/me` features/onboarding + new `/v29/*` endpoints +
  version bump.
* `web/src/lib/api.ts` — v29 helpers + types.
* `web/src/routes/Cockpit.tsx` — flag gating, onboarding mount,
  what's-new mount, error boundaries, retry banners.
* `web/src/routes/Elins.tsx` — flag gating, defensive renders, retry
  banners, char counter.
* `phone/lib/api.ts` — v29 helpers + types.
* `phone/app/elins.tsx` — flag gating, offline cache, pull-to-refresh,
  defensive renders.
* `BUILD_VERSION` — bumped to `20260506100000`.

---

## 9. Rollback path

If v29 needs to be reverted in production:
1. Set env var `CLARITYOS_RATE_LIMIT_ENFORCE=0` (already the default — no
   action if untouched).
2. Toggle off cohort flags via the in-process `set_flag(..., value=False,
   cohort="founder")` call from a maintenance shell, OR redeploy with
   the cohort-defaults loop commented out in `app.py`.
3. Surfaces collapse to friendly "not enabled" empty states; backend
   data is unchanged.

No persisted v28 state was touched by v29. Rollback is purely flag flips.

---

## 10. Known gaps / next-pass candidates (not in scope for v29)

* Rate-limit persistence — currently in-memory only; OK at one Cloud Run
  instance, less great at horizontal scale.
* Feature-flag persistence — overrides re-bootstrap on every process
  start. Move to Firestore in v30 if we need durable per-user opts.
* The `phone/app/ingest.tsx` and `phone/app/invite/[token].tsx`
  pre-existing TS errors are unrelated; out of scope for v29.
* Mesh LRU ties on identical `last_seen_ts` are decided by Python's
  stable sort (insertion order). Not a security or correctness issue at
  human-input rates, but a finer-grained tiebreaker could be worth
  adding before high-throughput sync.
