# Acceptance Harness — Operator Run Instructions

End-to-end procedure for running the harness against a real backend.
Companion to `README.md` (one-time setup), `runbook.md` (operations
reference), and `execution_plan.md` (lifecycle description). This file
is the live procedure the operator follows.

> **No execution by Claude.** Every command in this file is run by the
> operator in their own environment. Materialization wrote no shell
> output to disk and started no servers.

---

## 1. Prerequisites — confirm before invoking

Run each of these checks in your shell. They are inspections, not
installs.

| check | command | expected |
|---|---|---|
| Node ≥ 20 | `node --version` | `v20.x` or later |
| Python ≥ 3.11 | `python --version` | `Python 3.11.x` or later |
| Maestro on PATH (full mode only) | `maestro --version` | a version string |
| Playwright installed | `npx playwright --version` | a version string |
| Chromium browser binary | `npx playwright install --dry-run chromium` | reports installed |
| Acceptance config present | `cat tests/acceptance/config.local.json` | `<fill-…>` placeholders replaced with real values |
| Two test operators seeded | `python scripts/seed_acceptance_operators.py` | prints two operator IDs (idempotent — safe to re-run) |

If any check fails, see `README.md` for the install steps. **Do not
proceed until every prerequisite passes.**

---

## 2. Start the backend (operator runs; Claude does NOT)

The harness assumes the backend is reachable at the URL set in
`tests/acceptance/config.local.json::backend_base_url`. Default:
`http://localhost:8000`.

Document only — the operator runs this in a dedicated terminal:

```
# in one terminal, kept open for the duration of the run:
python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

Confirm the backend is up before invoking the harness:

```
curl -fsS http://localhost:8000/health
```

A non-200 response means the backend is not ready; do not start the
harness yet.

---

## 3. Optional — start the web dev server (for the web Playwright driver)

The web surface scenarios (01, 02, 03, 04) drive a running web app via
Playwright. In a second terminal:

```
cd web
npm run dev
```

Default port is `5173`. The harness reads `surfaces.web.baseUrl` from
the config; align both.

---

## 4. Run the harness

Pick a mode:

```
# Fast mode — scenarios 01 + 04, ~5–10 min wall.
bash scripts/run_acceptance.sh fast

# Full mode — scenarios 01–05, ~20–40 min wall.
bash scripts/run_acceptance.sh full
```

The shell script generates `run-<UTC>-<hex>`, creates
`tests/acceptance/reports/<run-id>/`, invokes
`npx ts-node tests/acceptance/runner.ts`, and tees stdout + stderr into
the run dir alongside the runner-produced `report.json` and `report.md`.

Exit codes:

| code | meaning |
|---|---|
| 0  | every selected scenario passed |
| 1  | one or more scenarios failed |
| 2  | fatal runner error |
| 64 | usage error |

---

## 5. Expected directory layout after a run

```
tests/acceptance/reports/run-20260508T142133Z-7a3c/
├── report.json     # canonical machine-readable output
├── report.md       # canonical human-readable summary
├── stdout.log      # shell capture (tee'd from runner stdout)
└── stderr.log      # shell capture (tee'd from runner stderr)
```

The runner always writes `report.json` first; `report.md` is written
last on a successful exit. If the runner is killed mid-run, you'll see
a partial `report.json` (whatever scenarios completed) and no
`report.md`.

---

## 6. How to read `report.json`

The structure conforms to `tests/acceptance/output_schema.json`. Top
fields:

- `run_id` — stable id for this run.
- `mode` — `"fast"` or `"full"`.
- `started_at`, `finished_at` — ISO 8601 UTC.
- `pass` — top-level binary; `true` iff every scenario passed.
- `scenarios[<id>]` — per-scenario result with `pass`, `duration_ms`,
  optional `details` (JSON-encoded), `messages` (string array).
- `config` — echoed `AcceptanceConfig` (vault secrets are replaced with
  placeholder text per the config schema).

Open the file in any JSON viewer. The minimum viable check is the
top-level `pass` field. If false, scan `scenarios` for the entries
where `pass` is false and read their `messages`.

A realistic example with mixed results lives at
`tests/acceptance/expected_outputs/realistic_run/report.json`.

---

## 7. How to read `report.md`

Same content as `report.json`, formatted for human reading. Each
scenario gets an `## ID — PASS|FAIL (Nms)` heading followed by:

- Optional encoded `details` line.
- Bulleted `messages` list — read top-to-bottom; this is the per-step
  narrative.

A realistic example lives at
`tests/acceptance/expected_outputs/realistic_run/report.md`.

---

## 8. Verify ingestion

After a successful run, append the run's metrics to the longitudinal
JSONL:

```
# preview what would be written, no disk I/O:
python tests/acceptance/post_run_ingest.py --dry-run \
  tests/acceptance/reports/run-20260508T142133Z-7a3c

# perform the append:
python tests/acceptance/post_run_ingest.py \
  tests/acceptance/reports/run-20260508T142133Z-7a3c
```

Confirm the JSONL was extended:

```
tail -n 1 tests/acceptance/reports/acceptance_runs.jsonl
```

The last line should be a single-record JSON with the just-finished
`run_id`. See `tests/acceptance/expected_outputs/ingest_preview.jsonl`
for the exact shape.

A more detailed validation procedure lives in
`tests/acceptance/ingest_validation.md`.

---

## 9. View the Founder dashboard

With the backend still running, hit the dashboard endpoints:

| endpoint | what it shows |
|---|---|
| `GET /founder/acceptance/runs` | every run (full report) under `tests/acceptance/reports/` |
| `GET /founder/acceptance/runs/recent?limit=10` | last 10 ingested rows from `acceptance_runs.jsonl` |
| `GET /founder/acceptance/stability` | aggregated stability metrics across ingested runs |
| `GET /founder/acceptance/incidents?since_hours=72` | open + recent P0/P1 incidents |
| `GET /founder/acceptance/onboarding_timings/<user_id>` | per-panel timestamps for one operator |

Web routes (founder cohort only):

- `/founder/acceptance` — surveillance summary
- `/founder/acceptance/runs` — recent-runs table
- `/founder/acceptance/stability` — aggregate stability view

Both web sub-views accept `?verify=1` to render a verification-mode
banner (Phase 4E) that confirms the page is reading fresh data. See
`tests/acceptance/dashboard_verification.md` for the full
verification procedure.

---

## 10. What to do on failure

See `tests/acceptance/failure_modes.md` for the realistic failure-mode
map (P0 / P1 / P2 with symptoms, likely causes, and operator actions).
Triage steps in short:

1. Confirm exit code from the shell script.
2. Open `report.md`, locate the failing scenario heading.
3. Read the `messages` array under that heading top-to-bottom.
4. Cross-reference the failure pattern in `failure_modes.md` to map
   to a severity (P0/P1/P2) and an action.
5. If P0 or P1, post an incident to
   `/founder/acceptance/incidents` (see `runbook.md` §When to open).
6. Do not re-run blindly — fix or document, then re-run with a fresh
   `run-id` (the shell script generates one automatically).

---

## 11. Anti-execution boundary

This document describes commands the operator runs. It does not run
them. Materialization (Phases 1–4) wrote no logs to
`tests/acceptance/reports/`, started no servers, and did not invoke
`scripts/run_acceptance.sh`.
