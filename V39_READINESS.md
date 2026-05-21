# V39 Readiness — Operator state memory + long-horizon ELINS continuity

Status: ✅ Ready
Backend version: `3.5`
Operator state version: `operator_state.v39.1`
Dashboard snapshot version: `elins_dashboard.v39.1`
Build: `20260507100000`

---

## What v39 ships

A per-user, metadata-only memory layer that the ELINS surfaces consult
to provide long-horizon continuity. Every successful ELINS run (preview
/ regional / global / #G) appends a tiny event to the user's operator
state — never the raw scenario text, only ids + topic-label +
region/domain tags + timestamps. The continuity slice surfaces on the
v38 dashboard, drives a "related past runs" hint on the ELINS inspector,
and a /founder/operator/{user_id} route lets founders inspect any
user's full timeline + inferred preferences.

Setting `external_signal_mode = "cloud_perplexity"` from
`POST /me/operator_state` mirrors onto `users_store` so the regional
ELINS pipeline picks up ESO automatically — no separate toggle.

---

## Files added / changed

### New
- `operator_state.py` — state CRUD + interaction recorder + preference
  decay + continuity helpers; metadata-only by construction.
- `tests/test_v39_operator_state.py` — 29 tests.
- `web/src/components/founder/operator/OperatorTimeline.tsx`
- `web/src/components/founder/operator/OperatorProfilePanel.tsx`
- `web/src/components/dashboard/ContinuityCard.tsx`
- `web/src/routes/OperatorProfile.tsx`
- `phone/app/operator_profile.tsx`
- `phone/app/operator_timeline.tsx`
- `V39_READINESS.md` (this file)

### Modified
- `app.py` — three new endpoints (`GET /me/operator_state`,
  `POST /me/operator_state`, `GET /founder/operator/{user_id}/state`);
  `/elins/preview`, `/elins/global`, `/elins/regional/run`,
  `/elins/g/run` now call `operator_state.record_*` with
  ANALYSIS-derived topic labels (no raw text). Backend version `3.5`,
  capability `operator_state`, root listing extended.
- `elins_dashboard.py` — `_build_snapshot` adds a `continuity`
  section; snapshot version bumped to `elins_dashboard.v39.1`.
- `web/src/lib/api.ts` — `V39OperatorState`, `V39ElinsHistoryEntry`,
  `V39GHistoryEntry`, `V39ContinuitySection`, plus
  `meOperatorState`/`meOperatorStateUpdate`/`founderOperatorState`;
  `V38DashboardSnapshot.continuity?` extended.
- `web/src/App.tsx` — register `/founder/operator/:user_id`.
- `web/src/components/founder/MemberDetailPanel.tsx` — link from the
  selected user to their operator profile.
- `web/src/components/founder/ELINSInspector.tsx` — pulls
  `meOperatorState` on mount and renders a "Related past runs" panel
  next to the synthesis.
- `web/src/components/dashboard/DashboardRoot.tsx` — embeds
  `ContinuityCard` as a full-width row.
- `phone/lib/api.ts` — same v39 types/helpers as web; snapshot
  shape extended with `continuity?`.
- `phone/app/_layout.tsx` — register `operator_profile` and
  `operator_timeline` stack screens.
- `phone/app/settings.tsx` — "My intelligence profile" entry above the
  Vault row.
- `tests/conftest.py` — reset hook for `operator_state`.
- `tests/test_v28_endpoints.py` — health version `3.5`.
- `tests/test_v38_elins_dashboard.py` — version-prefix assertion
  loosened to `elins_dashboard.v` so future bumps don't break it.
- `BUILD_VERSION` — `20260507100000`.

---

## API surface

### `GET /me/operator_state` (auth)
Returns the caller's own state. Initial-call materialises the default
record so subsequent calls always get the canonical shape.

### `POST /me/operator_state` (auth)
Body:
```json
{ "external_signal_mode": "cloud_perplexity" }
```
Validates against `("cloud_only", "cloud_perplexity")`. On change, the
new value is mirrored onto `users_store` so the regional ELINS resolver
picks up ESO without requiring a separate toggle.

### `GET /founder/operator/{user_id}/state` (founder-only)
Returns another user's state. 404 when `user_id` doesn't exist.

---

## State shape

```jsonc
{
  "user_id":              "alice",
  "created_ts":           1715080800.0,
  "last_active_ts":       1715080900.0,
  "elins_history": [
    {"ts": 1715080800.0, "elins_id": "sc_abc", "topic": "pressure · institutional",
     "region": "US", "kind": "regional"},
    ...
  ],
  "g_history": [
    {"ts": 1715080900.0, "g_id": "memb_xyz", "mode": "G",
     "topic": "#G · pressure 0.412"},
    ...
  ],
  "preferred_domains": {"economic": 1.71, "geopolitical": 0.62},
  "preferred_regions": {"US": 1.71, "MEA": 0.62},
  "external_signal_mode": "cloud_only",
  "version": "operator_state.v39.1"
}
```

Caps:
- `HISTORY_MAX = 200` per list.
- `TOPIC_MAX_LEN = 200` chars; long topics are truncated.
- Forbidden keys (`text`, `scenario_text`, `input_text`, `raw_text`)
  are stripped from any incoming `context` dict.
- Preference weights decay 0.9× on every record + bump by 1.0 for the
  fresh hit; entries below 0.001 are pruned.

---

## Continuity hooks

| Endpoint | Topic source (no raw text) |
| --- | --- |
| `/elins/preview` | `synthesis.top_primitive · effective_top` |
| `/elins/global` | `synthesis.top_primitive · effective_top` |
| `/elins/regional/run` | caller-supplied `topic_hint` (truncated to 80 chars) |
| `/elins/g/run` | `"#G · pressure <qc.pressure>"` |

Each call updates `last_active_ts` and bumps the matching
preference weight.

---

## UI

### Web
- `/dashboard` gains a full-width `ContinuityCard` showing last topics +
  preferred domains/regions + ESO badge + total counts.
- `ELINSInspector` pulls `meOperatorState()` on mount and renders a
  "Related past runs" list next to the synthesis output.
- New `/founder/operator/:user_id` route renders
  `OperatorProfilePanel` (lifetime stats + preferred domains/regions
  bars + signal mode + account meta) alongside `OperatorTimeline`
  (ELINS + #G two-column timeline).
- `MemberDetailPanel` adds an "Operator profile →" link next to the
  selected username.

### Phone
- Settings → "My intelligence profile" → `/operator_profile` shows the
  user's own profile (account, signal-mode toggle pills, preference
  bars, link to timeline).
- `/operator_timeline` is a single-column ELINS + #G feed.
- Stack screens registered in `_layout.tsx`.

---

## Tests

```
tests/test_v39_operator_state.py — 29 tests, all pass
Full suite — 386 passed, 0 failed
```

Coverage:
- Default state shape + `get_operator_state` validation +
  `update_operator_state` signal-mode validation + ignore-unknown.
- `record_elins_interaction` / `record_g_run` append; kind defaults;
  preference accumulation with decay; raw-text fields stripped; topic
  truncated; history capped at `HISTORY_MAX`.
- `related_runs` filter by region (exact) + topic (case-insensitive
  substring); `continuity_section` shape; `continuity_context`
  surfaces `last_region`.
- `/me/operator_state` GET + POST round-trip + bad-mode 400 +
  `users_store` mirror after toggle.
- `/founder/operator/{user_id}/state` happy path + 404 + founder gate.
- `/elins/preview`, `/elins/regional/run`, `/elins/g/run` integration
  — operator state is updated; raw scenario text never appears in
  the persisted record.
- Dashboard `continuity` section is present and reflects the user's
  history.
- Capability surface advertises `operator_state`.

---

## Privacy posture

- Topic strings are truncated at 200 chars and, for prompt-bearing
  endpoints, derived from analysis output rather than raw input.
- `record_*` strips `text`, `scenario_text`, `input_text`, `raw_text`
  from the incoming context dict.
- The full ELINS payload is never written to operator_state — only
  the scenario id, the topic label, region/domain tags, and the
  timestamp.
- Test `test_no_raw_text_persisted_via_endpoints` exercises the
  `/elins/preview` path with a recognisable token (`FNORD123`) and
  asserts it never appears anywhere in the resulting state.

---

## Notes / follow-ups

- Continuity-aware ELINS generation is wired at the metadata level
  (the dashboard surfaces "you've worked on US/Markets recently"). A
  future pass can pipe `operator_state.continuity_context(user)` into
  `regional_elins.run_regional_elins` to bias domain weights toward
  the user's preferred regions / domains; the call site already has
  access to it via the operator state read.
- The `users_store` mirror of `external_signal_mode` keeps the v35
  ESO resolver code path untouched. If the resolver moves to read
  `operator_state` directly, the mirror can be removed.
- Pre-v39 surfaces (v28–v38) are unchanged. New endpoints + the
  `continuity` field on the dashboard snapshot are additive.
