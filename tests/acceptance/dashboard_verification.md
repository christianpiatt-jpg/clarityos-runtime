# Founder Dashboard — Verification Procedure

Step-by-step procedure for confirming that the four founder acceptance
endpoints respond with correctly-shaped data, and that the two web
sub-views render that data correctly.

This is descriptive only. The operator runs every command.

---

## Endpoints under verification

All endpoints are mounted by `acceptance_dashboard.py` under
`/founder/acceptance/*`:

| endpoint | source data | written by |
|---|---|---|
| `GET /founder/acceptance/incidents?since_hours=N` | `incident_store.py` (JSONL) | manual `POST /incidents` calls |
| `GET /founder/acceptance/runs` | `tests/acceptance/reports/run-*/report.json` | `runner.ts` |
| `GET /founder/acceptance/runs/recent?limit=N` | `tests/acceptance/reports/acceptance_runs.jsonl` | `post_run_ingest.py` |
| `GET /founder/acceptance/stability` | same JSONL | same |
| `GET /founder/acceptance/onboarding_timings/<user_id>` | `memory_vault.py` | onboarding FSM `_ts_ms` markers |

Verification covers the two Phase 3C-added endpoints (`/runs/recent`
and `/stability`) and the two Phase 3C-added web routes that consume
them. The other endpoints are left to `tests/acceptance/runbook.md` §
incident triage.

---

## Step 1 — Hit `/runs/recent` directly

Backend must be running at `http://localhost:8000`.

```
curl -fsS "http://localhost:8000/founder/acceptance/runs/recent?limit=10" \
  | python -m json.tool
```

Expected JSON shape (matches the endpoint's response model):

```json
{
  "limit": 10,
  "count": <int 0..10>,
  "available_total": <int>,
  "runs": [
    {
      "run_id": "run-<UTC>-<hex>",
      "mode": "fast | full",
      "pass": true,
      "started_at": "<ISO>",
      "finished_at": "<ISO>",
      "scenarios": {
        "01_onboarding_per_surface": { "pass": true, "duration_ms": <int> }
      },
      "stability": { "monotonicity_pass": true, "..." } | null
    }
  ],
  "note": "no acceptance_runs.jsonl yet — run post_run_ingest.py at least once" | null
}
```

If `acceptance_runs.jsonl` does not exist, you will see:

```json
{
  "limit": 10,
  "count": 0,
  "available_total": 0,
  "runs": [],
  "note": "no acceptance_runs.jsonl yet — run post_run_ingest.py at least once"
}
```

This is correct (try/except on file absence per Phase 3C §C1).

---

## Step 2 — Hit `/stability` directly

```
curl -fsS http://localhost:8000/founder/acceptance/stability \
  | python -m json.tool
```

Expected JSON shape:

```json
{
  "runs_with_stability": <int>,
  "monotonicity_pass_count": <int>,
  "monotonicity_fail_count": <int>,
  "iteration_mean_ms_avg": <number | null>,
  "iteration_max_ms_max":  <integer | null>,
  "iteration_stddev_ms_avg": <number | null>,
  "note": "no stability data yet — scenario 05 must run + ingest at least once" | null
}
```

If no scenario 05 records have been ingested, all metric fields are
`null` and `note` is populated. This is correct (D1.5 file-absence
fallback behaviour).

---

## Step 3 — Verify in the web UI (recent runs)

Open in a browser (or any web client of your choice) with the founder
session active:

```
http://localhost:5173/founder/acceptance/runs?verify=1
```

The `?verify=1` query param activates the Phase 4E verification
banner. You should see:

- A small banner at the top that says **"Verification Mode — ?verify=1
  active"** (or similar).
- Below the banner, a table with columns: run id, mode, pass,
  finished, scenarios (pass / total), monotonicity, mean iter (ms).
- Each row corresponds to one record from `acceptance_runs.jsonl`,
  newest first.

Reload without `?verify=1`:

```
http://localhost:5173/founder/acceptance/runs
```

Same table, no banner. The data should be identical.

If the banner appears with `?verify=1` and disappears without it, the
verification mode toggle is wired correctly.

---

## Step 4 — Verify in the web UI (stability)

```
http://localhost:5173/founder/acceptance/stability?verify=1
```

You should see:

- The verification banner.
- An aggregate table: runs with stability data, monotonicity pass /
  fail count, iteration mean (avg), iteration max (max), iteration
  stddev (avg).
- An "Interpretation" section explaining what monotonicity and timing
  mean.

Reload without `?verify=1` — same table, no banner.

---

## Step 5 — Interpret the metrics

### Monotonicity

| field | meaning | what action it suggests |
|---|---|---|
| `monotonicity_pass_count` ↑ over time | scenario 05 keeps passing the artifact-count monotonicity check | system is stable; no action |
| `monotonicity_fail_count` ↑ even once | scenario 05 saw a count drop between iterations | open P1 — likely state leakage in vault or FSM |
| `monotonicity_pass_count == 0` and `monotonicity_fail_count == 0` | no scenario 05 records yet | run the harness in `full` mode to generate data |

### Iteration timing

| field | meaning |
|---|---|
| `iteration_mean_ms_avg` | average per-iteration duration of scenario 05, averaged across runs |
| `iteration_max_ms_max` | the worst single iteration anywhere across all runs |
| `iteration_stddev_ms_avg` | average within-run standard deviation |

Trends to watch:

- `iteration_mean_ms_avg` climbing >25% from baseline over consecutive
  runs → P2 incident, investigate progressive slowdown (see
  `failure_modes.md` §P2.2).
- `iteration_max_ms_max` ≥ 2× current `iteration_mean_ms_avg` → P1
  incident, scenario 05 will start failing its variance bound.
- `iteration_stddev_ms_avg` growing → run-to-run jitter increasing,
  possible environment-level cause.

### Recent runs

A healthy `runs/recent` view shows:

- All `pass` columns reading `PASS`.
- `scenarios (pass / total)` reading `5 / 5` in full-mode runs.
- `monotonicity` column reading `ok` for runs that included scenario
  05.
- `mean iter (ms)` columns roughly stable across consecutive runs.

A single run with a different shape is worth investigating; a sustained
deviation is worth filing a P1 or P2 depending on severity per
`failure_modes.md`.

---

## Step 6 — Confirm timing markers (optional, deeper inspection)

For a single operator's onboarding timing:

```
curl -fsS "http://localhost:8000/founder/acceptance/onboarding_timings/<user_id>" \
  | python -m json.tool
```

Expected (when timing markers have been recorded):

```json
{
  "user_id": "<user_id>",
  "surfaces": {
    "panel_1_ts_ms": <int>,
    "panel_2_ts_ms": <int>,
    "...": "..."
  },
  "note": null
}
```

When no markers exist:

```json
{
  "user_id": "<user_id>",
  "surfaces": {},
  "note": "no timing markers recorded for this user yet"
}
```

This endpoint reads from `memory_vault.py`'s on-disk store (the FSM
writes `_ts_ms` to operator_state). If the response is empty for a
user that completed onboarding, the FSM did not persist its markers
to the vault — open a P1 against the FSM.

---

## What "verified" means

The dashboard is verified when:

1. `/runs/recent` returns either populated `runs[]` or the documented
   empty-with-note shape.
2. `/stability` returns either populated metrics or the documented
   empty-with-note shape.
3. `/founder/acceptance/runs?verify=1` shows the banner; without
   `?verify=1` the banner is absent. Same for `/stability?verify=1`.
4. The two web tables read coherently with `tail -n 10` of
   `acceptance_runs.jsonl`.

If any of those four fail, file a P1 against the dashboard and
investigate the relevant endpoint or component.

---

## Anti-execution boundary

This file is operator-run. Materialization started no servers and hit
no endpoints.
