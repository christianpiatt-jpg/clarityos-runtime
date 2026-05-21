# Ingestion Validation

Step-by-step procedure for validating that
`tests/acceptance/post_run_ingest.py` reads a run report and appends
the correct compact record to
`tests/acceptance/reports/acceptance_runs.jsonl`.

This document is descriptive — every command is run by the operator,
not by Claude.

---

## Goal

Confirm the ingestion pipeline is wired correctly **before** trusting
the dashboard's `Recent runs` and `Stability metrics` views. After
this validation passes, the dashboard data is as trustworthy as the
runner's own `report.json`.

---

## Prerequisite

You must have completed at least one harness run, producing a directory
shaped like:

```
tests/acceptance/reports/run-<UTC>-<hex>/
├── report.json
├── report.md
├── stdout.log
└── stderr.log
```

If you have not run the harness yet, follow
`tests/acceptance/operator_run_instructions.md` §4 first.

For this validation alone, you can also point the script at a curated
example without running anything live:

```
tests/acceptance/expected_outputs/realistic_run/
├── report.json
└── report.md
```

The realistic example produces an identical-shaped record to a real
run; only the field values differ.

---

## Step 1 — Inspect the report

```
cat tests/acceptance/reports/run-<UTC>-<hex>/report.json | head -20
```

Confirm the file is well-formed JSON with a top-level `run_id`, `mode`,
`pass`, `started_at`, `finished_at`, and `scenarios` keys. If any of
those is missing, ingestion will store nulls — fix the runner output
first.

---

## Step 2 — Dry-run ingest (no disk write)

The Phase 4D additive `--dry-run` flag prints what *would* be appended
without touching disk:

```
python tests/acceptance/post_run_ingest.py --dry-run \
  tests/acceptance/reports/run-<UTC>-<hex>
```

You should see output like:

```
[ingest] DRY RUN — no write performed
[ingest] would append to: tests/acceptance/reports/acceptance_runs.jsonl
{"run_id":"run-<UTC>-<hex>","mode":"full","pass":true, ...}
```

Compare the printed JSON line against
`tests/acceptance/expected_outputs/ingest_preview.jsonl` for the
canonical shape. The keys should match exactly:

- `run_id` (string)
- `mode` (`"fast" | "full"`)
- `pass` (boolean)
- `started_at`, `finished_at` (ISO 8601 strings)
- `scenarios` (object: scenario id → `{pass, duration_ms}`)
- `stability` (object or null — populated only when scenario 05 ran)

If a key is missing or has the wrong type, **stop here**. Either the
runner produced an unexpected shape (treat as P1 against the runner)
or `post_run_ingest.py` was edited incorrectly (revert the edit).

Exit code from the dry-run:

| code | meaning |
|---|---|
| 0  | record built and printed; nothing written |
| 2  | report.json missing or unreadable |
| 64 | usage error (bad args) |

---

## Step 3 — Confirm the destination is empty (or known) before real ingest

```
ls -la tests/acceptance/reports/acceptance_runs.jsonl 2>/dev/null \
  || echo "no JSONL yet"
```

If the file exists, check the last line so you can compare against the
post-ingest tail:

```
tail -n 1 tests/acceptance/reports/acceptance_runs.jsonl
```

---

## Step 4 — Real ingest (one run, one append)

```
python tests/acceptance/post_run_ingest.py \
  tests/acceptance/reports/run-<UTC>-<hex>
```

Expected output:

```
[ingest] appended record for run-<UTC>-<hex> → tests/acceptance/reports/acceptance_runs.jsonl
```

Exit code 0 = appended. Any other exit means the file was not modified.

---

## Step 5 — Confirm the append landed

```
tail -n 1 tests/acceptance/reports/acceptance_runs.jsonl
```

The output should be the same JSON line you saw in Step 2's dry-run.

Spot-check by parsing it:

```
tail -n 1 tests/acceptance/reports/acceptance_runs.jsonl \
  | python -c "import json,sys; r=json.loads(sys.stdin.read()); print(r['run_id'], r['pass'])"
```

Expected:

```
run-<UTC>-<hex> True
```

---

## Step 6 — Verify ingest is idempotent under the operator's discipline

`post_run_ingest.py` does NOT auto-deduplicate. Each invocation appends
one row, even for the same `run_dir`. This is intentional — the
operator is responsible for invoking it exactly once per run. To
confirm:

```
# Count records for a given run id (should be 1 after one ingest):
grep -c "\"run_id\":\"run-<UTC>-<hex>\"" \
  tests/acceptance/reports/acceptance_runs.jsonl
```

If the count is greater than 1, you ran `post_run_ingest.py` multiple
times against the same run dir. The dashboard will show duplicates.
Either dedupe by hand (edit the JSONL) or accept the duplicates and
note in your op log.

---

## Step 7 — Verify dashboard reflects the new data

Backend must be running at `http://localhost:8000`:

```
curl -fsS "http://localhost:8000/founder/acceptance/runs/recent?limit=1" \
  | python -m json.tool
```

The first run record should include the `run_id` you just ingested.
Specifically:

- `runs[0].run_id` matches your run.
- `runs[0].pass` matches the run's top-level pass.
- `runs[0].scenarios` has one entry per executed scenario with
  `pass` and `duration_ms`.

If the run does not appear in the API response:

- Confirm the JSONL path resolution. The endpoint reads the path set
  in `CLARITYOS_ACCEPTANCE_REPORTS` (default `tests/acceptance/reports`)
  and looks for `acceptance_runs.jsonl` inside.
- Restart the backend if you moved the JSONL file location.

For the aggregate stability view:

```
curl -fsS http://localhost:8000/founder/acceptance/stability \
  | python -m json.tool
```

If your run included scenario 05, the response should reflect the
incremented `runs_with_stability` count.

---

## Step 8 — Verify in the web UI

Open the founder web dashboard:

- `/founder/acceptance/runs?verify=1` — recent runs in a table.
  The `?verify=1` flag activates the Phase 4E verification banner so
  you know you're looking at the verification view rather than a
  cached page.
- `/founder/acceptance/stability?verify=1` — aggregate stability.

The verification banner is a small visual cue; data is the same as
without `?verify=1`. See
`tests/acceptance/dashboard_verification.md` for the full procedure.

---

## What "valid ingestion" means

Ingestion is valid when:

1. `post_run_ingest.py --dry-run <run_dir>` prints a record matching
   `expected_outputs/ingest_preview.jsonl` shape.
2. The real (non-dry-run) invocation appends exactly one line per
   invocation.
3. `GET /founder/acceptance/runs/recent?limit=1` returns the same
   `run_id` that was just ingested.
4. `GET /founder/acceptance/stability` increments
   `runs_with_stability` by 1 if scenario 05 ran.

If all four hold, the pipeline is wired correctly and the dashboard is
trustworthy.

---

## Anti-execution boundary

Materialization wrote no JSONL records, hit no dashboard endpoints,
started no backend. Every command in this file is invoked by the
operator manually.
