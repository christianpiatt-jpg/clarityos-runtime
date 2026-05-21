# Intelligence Scheduler Layer Specification (Phase 2 — Unit 4)

**Module:** `intelligence_scheduler.py`
**Status:** Locked — shipped 2026-05-11. 36/36 module tests, 1087/1087 backend tests.
**Slot in architecture:** Integration & Consolidation Layer → "Intelligence Scheduling Layer."

---

## 1. Purpose and role in the architecture

The `intelligence_scheduler` module is the **cadence orchestrator** for the three
personal-intelligence producers:

- **News**: `personal_news_basin.run_news_basin(user_id)`
- **Email**: `email_ep_dash.run_email_ep_dash(raw, user_id)` (on-demand)
- **Daily ELINS**: `daily_personal_elins.run_daily_personal_elins(user_id, date=None)`

It exposes a **cron-friendly `tick()` contract** (no daemons, no background threads).
A cron job invoking:

```bash
python -m intelligence_scheduler
```

once per minute is sufficient to maintain all cadences for all registered users.

---

## 2. Public API surface

```python
run_daily_personal_elins_once(user_id, date=None)   # 1×/day per UTC day
run_news_basin_once(user_id)                        # 2×/day (configurable times)
run_email_ep_dash_once(raw, user_id)                # on-demand, external caller
run_scheduled_tasks(now=None)                       # alias for tick()
tick(now=None)                                      # main production entrypoint
register_user(user_id)                              # add user to scheduler state
unregister_user(user_id)                            # remove user and their state
get_state()                                         # read-only view of current state
```

**Key properties:**
- **Pure stdlib**: no external dependencies.
- **Deterministic**: same `now` + same state ⇒ same envelopes + same final state.
- **Side effects**: only via the three producer modules and the state file.

---

## 3. Cadence semantics

| Producer                 | Cadence model                       | Trigger condition (per user)                                              |
|--------------------------|-------------------------------------|---------------------------------------------------------------------------|
| **News basin**           | 2×/day (default `09:00,21:00` UTC)  | Any scheduled time for today has passed AND `last_news_basin` < that time |
| **Daily personal ELINS** | 1×/day per UTC day                  | `last_daily_elins` < `today_utc`                                          |
| **Email EP dash**        | On-demand; optional scheduled marker| On-demand always; scheduled marker at 13:00 UTC if `CLARITYOS_EMAIL_EP_SCHEDULED=1` |

**Order per tick** (per user): `news_basin` → `email_ep_dash` (scheduled marker only) → `daily_personal_elins`.

**No double-runs**: once a cadence fires for a given window, it will not re-fire until the next window.

---

## 4. State model and persistence

**State file path:**
- Default: `.clarityos_scheduler_state.json`
- Override: `CLARITYOS_SCHEDULER_STATE=/path/to/state.json`

**Canonical JSON structure:**

```json
{
  "users": {
    "alice": {
      "last_daily_elins":          "2026-05-11",
      "last_news_basin":           "2026-05-11T09:05:00+00:00",
      "next_news_basin":           "2026-05-11T21:00:00+00:00",
      "last_email_scheduled_tick": "2026-05-11T13:30:00+00:00"
    }
  }
}
```

**Persistence guarantees:**
- **Atomic writes**: write to a temp file in the same directory, then `os.replace` to the final path.
- **No temp-file leakage**: tests assert no `.tmp` / `mktemp` artifacts remain.
- **Corruption handling**:
  - Whole-file JSON failure ⇒ reset to `{"users": {}}`.
  - Per-user invalid entry ⇒ drop that user only; others preserved.

---

## 5. Tick algorithm

```text
tick(now=None):
  1. Normalize `now` to UTC (if None, use current time).
  2. Load scheduler state from disk (or empty if missing/corrupt).
  3. Compute today's UTC date and today's scheduled news times.
  4. Iterate users in sorted order (alphabetical) for determinism.
  5. For each user:
     a. If any news time has elapsed and not yet run → run_news_basin_once(user).
     b. If scheduled email mode enabled and 13:00 UTC elapsed and not yet marked → record scheduled tick.
     c. If last_daily_elins < today_utc → run_daily_personal_elins_once(user).
  6. Catch and log exceptions per task; do not abort the tick; still advance state.
  7. Update `next_news_basin` for dashboards.
  8. Save updated state atomically.
  9. Return list of all non-None envelopes produced this tick.
```

**Return value:**
- `List[dict]` of envelopes from the underlying producers.
- `None` results (e.g., empty-day envelopes) are filtered out.

---

## 6. Environment variables

| Variable                       | Meaning                                          | Default                            |
|--------------------------------|--------------------------------------------------|------------------------------------|
| `CLARITYOS_SCHEDULER_STATE`    | Path to scheduler state file                     | `.clarityos_scheduler_state.json`  |
| `CLARITYOS_NEWS_TIMES`         | Comma-separated `HH:MM` times (UTC) for news     | `"09:00,21:00"`                    |
| `CLARITYOS_EMAIL_EP_SCHEDULED` | `"1"` to enable scheduled email cadence marker   | unset (disabled)                   |

---

## 7. Failure modes and graceful degradation

| Failure scenario                    | Behavior                                                                 |
|-------------------------------------|--------------------------------------------------------------------------|
| State file missing                  | Treated as empty state; created on first write.                          |
| State file JSON-corrupt             | Reset to empty state; tick continues.                                    |
| Single user entry corrupt           | That user dropped; others unaffected.                                    |
| No users registered                 | `tick()` returns `[]`; no writes (other than state-file refresh).        |
| No cadences due at `now`            | `tick()` returns `[]`; state unchanged except `next_news_basin` refresh. |
| Underlying producer raises          | Exception caught; logged; state advances; other users/tasks still run.   |
| Producer returns `None` (empty-day) | Excluded from returned envelope list; cadence still marked as run.       |

---

## 8. Integration with Phase 2 units

- **Upstream**: `register_user(user_id)` is called by whatever user-onboarding or operator-config flow exists (Phase 3 wiring).
- **Downstream**:
  - `personal_news_basin` and `email_ep_dash` write envelopes to the ingestion bus and their respective archives.
  - `daily_personal_elins` consumes bus packets + macro/micro context and writes the fused daily envelope.
- **Contract**: `intelligence_scheduler` never inspects envelope contents; it only:
  - Decides **when** to call each producer.
  - Persists **when** each producer last ran per user.

---

## 9. Test coverage

`tests/test_intelligence_scheduler.py` — 36 tests across 8 classes:

| Class | # tests | Coverage |
|---|---|---|
| `TestDailyElinsCadence`     | 4 | once-per-day, no double-run, next-day rollover, state mark |
| `TestNewsBasinCadence`      | 6 | 09:00 fires, before-09:00 doesn't, 21:00 fires, no double, next pointer, custom times via env |
| `TestEmailDashCadence`      | 5 | on-demand always, scheduled gated by env, before-13:00 doesn't fire, scheduled mode doesn't invoke runner |
| `TestStatePersistence`      | 8 | file creation, no `.tmp` leftovers, round-trip, whole-file corruption, per-user corruption, missing-file empty, unregister, register validation |
| `TestTickOrdering`          | 2 | news < daily in call order |
| `TestTickReturnValues`      | 5 | list type, empty cases, None-skip, exception-skip-continue |
| `TestMultiUserScheduling`   | 3 | independent cadences, one-user-failure-doesn't-block, unregister isolates state |
| `TestDeterminism`           | 3 | same-input-same-output, sorted user iteration, alias entrypoint parity |
