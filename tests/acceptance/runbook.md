# Acceptance Harness — Operator Runbook

Operations companion to `tests/acceptance/README.md`. The README covers
one-time setup; this runbook covers the live-run lifecycle and how to
interpret the artefacts.

---

## How to run

After completing `README.md` setup (Playwright + Maestro installed,
`config.local.json` filled, two test operators seeded):

```bash
# Fast mode — scenarios 01 + 04 (about 5–10 minutes wall time).
bash scripts/run_acceptance.sh fast

# Full mode — all five scenarios (about 20–40 minutes wall time
# depending on hardware and surface response).
bash scripts/run_acceptance.sh full
```

The shell script generates a deterministic `run_id`, creates
`tests/acceptance/reports/<run_id>/`, and tees both stdout and stderr
into that directory while the runner produces `report.json` and
`report.md` in the same place.

Exit codes (propagated from the runner):

| code | meaning |
|---|---|
| 0  | every selected scenario passed |
| 1  | one or more scenarios failed |
| 2  | fatal runner error (e.g., config not loadable) |
| 64 | usage error (bad mode argument to the shell script) |

---

## Run lifecycle

A typical run progresses through these phases:

1. **Run-id generation.** `run-<UTC timestamp>-<4-hex>`. The id is
   stable for the duration of the run and is the directory name under
   `tests/acceptance/reports/`.
2. **Config load.** `tests/acceptance/runner.ts` calls `loadConfig()`
   from `config.local.json`. Per-run vault secrets are regenerated via
   `node:crypto::randomBytes` — placeholders in the config file are
   overwritten in memory.
3. **Scenario selection.** Fast mode selects scenarios with `fast: true`
   in `tests/acceptance/scenarios/index.ts` (currently 01, 04). Full
   mode selects all five.
4. **Sequential execution.** Each scenario runs end-to-end before the
   next starts. The runner persists `report.json` after every scenario
   so a crash mid-run still leaves a partial report.
5. **Report finalization.** When the last scenario completes, the
   runner writes `report.md` (human-readable summary) alongside the
   final `report.json`. Both have the same `pass` field.
6. **Post-run ingest (optional).** Operator runs
   `python tests/acceptance/post_run_ingest.py <run_dir>` to append a
   compact metrics record to `tests/acceptance/reports/acceptance_runs.jsonl`
   for trend tracking.

---

## Expected outputs

### `report.json` (machine-readable)

Conforms to `tests/acceptance/output_schema.json` (JSON Schema).
Top-level shape:

```jsonc
{
  "run_id": "run-20260508T142133Z-7a3c",
  "mode": "fast" | "full",
  "started_at": "2026-05-08T14:21:33.214Z",
  "finished_at": "2026-05-08T14:27:18.881Z",
  "config": { /* echoed AcceptanceConfig */ },
  "scenarios": {
    "01_onboarding_per_surface": {
      "id": "01_onboarding_per_surface",
      "name": "Onboarding per surface",
      "pass": true,
      "duration_ms": 187234,
      "messages": ["web onboarding for op_a: 31420ms ok", ...]
    },
    /* ... */
  },
  "pass": true
}
```

### `report.md` (human-readable)

A flat Markdown summary. Top of file states `mode`, `started`,
`finished`, and the binary `result: PASS|FAIL`. Each scenario then
gets a heading with its pass/fail and a bulleted message list.

### `stdout.log` / `stderr.log`

Verbatim shell capture from the runner process. Useful when a scenario
returned an error message that referenced a downstream tool (Playwright,
Maestro). The runner itself rarely writes to stderr; failures mostly
appear in `stdout.log`.

---

## How to interpret a result

### Scenario-level pass/fail

A scenario passes iff its `pass` field is `true` in `report.json`. The
`messages` array carries the per-step narrative — read it linearly.

| `messages` shape | interpretation |
|---|---|
| `"<surface> onboarding for <handle>: <ms>ms ok"` | green path |
| `"<surface> onboarding for <handle> took <ms>ms (limit <limit>ms)"` | timing budget exceeded — possible polish-plan §8 violation |
| `"<surface> onboarding failed for <handle>: <error>"` | hard failure mid-flow — open as P1 incident |
| `"vault isolation breach (<kind>): shared keys <ids>"` | hard failure — open as **P0 incident** (security boundary) |
| `"missing ELINS <key>"` / `"missing thread <id>"` | artifact-presence failure — P1 incident |
| `"timing variance: max ... > 2× mean"` | progressive slowdown — likely state leak; P1 incident |

### Run-level pass/fail

The run passes iff every selected scenario passes. Scenario 03 failures
should be treated as P0 by default (cross-operator data leakage is a
spec-defined security boundary). All other failures default to P1
unless they involve data loss or vault corruption.

---

## When to open a P0 / P1 incident

The harness does NOT auto-create incidents. The operator (or the run
orchestrator) calls the dashboard endpoint after triaging:

```bash
curl -X POST http://localhost:8000/founder/acceptance/incidents \
  -H "Content-Type: application/json" \
  -d '{
        "severity": "P0",
        "surface": "web",
        "title": "vault isolation breach: op_a saw op_b ELINS key",
        "os": "macos",
        "operator_id": "op_a@clarityos.test",
        "detail": "see tests/acceptance/reports/<run_id>/report.md §03"
      }'
```

The incident immediately appears at `/founder/acceptance` in the web
dashboard. See `tests/acceptance/README.md` for the full P0 / P1
taxonomy (D3 default).

---

## When to re-run

| condition | action |
|---|---|
| All scenarios pass | proceed with whatever the run was gating (polish week, launch step, etc.) |
| Single scenario failed with a transient timeout | re-run with same `run_id` is not supported; generate a new run with `bash scripts/run_acceptance.sh fast` |
| Cross-operator isolation breach (scenario 03) | **stop. open P0 incident. fix before continuing.** |
| Stability scenario failed on monotonicity | check for state leakage in the FSM or vault; re-run after fix |
| 72-hour stability window check (separate from scenario 05) | this is a passive incident-store query, not a re-run; see dashboard |

---

## Files this runbook references

| path | purpose |
|---|---|
| `scripts/run_acceptance.sh` | shell entry point; generates run-id and tees output |
| `tests/acceptance/runner.ts` | TypeScript runner; orchestrates scenarios |
| `tests/acceptance/scenarios/*.ts` | individual scenarios |
| `tests/acceptance/surfaces/*.ts` | per-surface drivers (Playwright + Maestro) |
| `tests/acceptance/.maestro/*.yaml` | Maestro flows for phone |
| `tests/acceptance/config.local.json` | per-environment config (gitignored) |
| `tests/acceptance/output_schema.json` | JSON Schema for `report.json` |
| `tests/acceptance/post_run_ingest.py` | metrics rollup into JSONL |
| `tests/acceptance/reports/<run_id>/` | per-run artefacts |
| `tests/acceptance/reports/acceptance_runs.jsonl` | longitudinal metrics roll-up |
| `tests/acceptance/README.md` | one-time setup |
