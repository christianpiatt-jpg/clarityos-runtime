# Acceptance Harness — Execution Plan (Dry-Run)

This document describes the dry-run lifecycle for the acceptance harness.
It is **descriptive only**. It contains no commands that execute the
harness, and no enabling of CI. Operator triggers execution manually
per `runbook.md`.

---

## Lifecycle (single run)

```
[1] Operator invokes scripts/run_acceptance.sh fast | full
[2] Shell script generates run-id: run-<UTC YYYYmmddTHHMMSSZ>-<4-hex>
[3] Shell script creates tests/acceptance/reports/<run-id>/
[4] Shell script invokes:
       npx ts-node tests/acceptance/runner.ts --mode=<mode> --run-id=<run-id>
[5] Runner loads tests/acceptance/config.local.json via loadConfig()
       - regenerates per-run vault_secret values (node:crypto::randomBytes)
[6] Runner selects scenarios via selectScenarios(mode)
       - fast → [01, 04]
       - full → [01, 02, 03, 04, 05]
[7] Runner executes each scenario sequentially:
       - persists report.json to <run-id>/ after every scenario
       - on throw, records the error in messages and continues
[8] After last scenario, runner writes report.md (human-readable summary)
[9] Shell script captures stdout.log + stderr.log alongside report.{json,md}
[10] Shell script prints next-step hint:
       python tests/acceptance/post_run_ingest.py <run-dir>
[11] Operator runs post_run_ingest.py
       - reads report.json
       - appends one record to tests/acceptance/reports/acceptance_runs.jsonl
[12] Founder dashboard at /founder/acceptance reads the runs + the
     incident store and renders pass/fail surface.
```

The dry-run differs from a real run in zero respects on the runner
side — it is the same code path. The "dry-run" qualifier here means
the harness is materialized, runnable, but not yet invoked by Claude.

---

## Expected directory layout (after one run)

```
tests/acceptance/
├── reports/
│   ├── acceptance_runs.jsonl           # appended by post_run_ingest.py
│   └── run-20260508T142133Z-7a3c/      # one dir per run
│       ├── report.json                 # canonical machine-readable output
│       ├── report.md                   # canonical human-readable summary
│       ├── stdout.log                  # shell capture (tee'd)
│       └── stderr.log                  # shell capture (tee'd)
└── expected_outputs/                    # examples; never overwritten by runs
    ├── sample_report.json
    └── sample_report.md
```

The runner is idempotent per `run-id`: re-invoking the runner with the
same `--run-id` overwrites the existing report files. The shell script
generates fresh ids on each invocation, so this is a no-op in normal
operation.

---

## Expected stdout shape

The runner prints one line per scenario start, plus the runner's own
header lines and the final pivot. A fast-mode pass run looks like:

```
[run_acceptance] mode=fast
[run_acceptance] run_id=run-20260508T142133Z-7a3c
[run_acceptance] output_dir=/abs/path/tests/acceptance/reports/run-20260508T142133Z-7a3c
[run_acceptance] runner=tests/acceptance/runner.ts
[runner] starting 01_onboarding_per_surface
[runner] starting 04_artifact_presence

[run_acceptance] runner exit code: 0
[run_acceptance] artifacts:
  /abs/.../report.json
  /abs/.../report.md
  /abs/.../stdout.log
  /abs/.../stderr.log

[run_acceptance] next step:
  python tests/acceptance/post_run_ingest.py /abs/.../run-20260508T142133Z-7a3c
```

A failing run will have the same structure but with a non-zero exit
code, and the offending scenario(s) will appear with `pass: false` in
`report.json` and as `FAIL` headings in `report.md`.

## Expected stderr shape

Stderr is rarely written by the runner itself. Most output appears on
stdout. Stderr typically only contains:

- Playwright timeout / launch errors (when a browser fails to start).
- Maestro spawn errors (when the `maestro` binary is not on PATH).
- `ts-node` compilation errors (if a scenario file has a syntax error).

A clean dry-run produces an empty `stderr.log` and a populated
`stdout.log`.

---

## Failure-mode map (P0 / P1 / P2)

| pattern in messages | severity | action |
|---|---|---|
| `vault isolation breach (...)` | **P0** | open P0 incident; freeze deploys; investigate cross-operator data leak |
| `web/desktop/phone bootstrap (...) failed: ...` | **P1** | open P1 incident; surface broken; investigate per-surface error |
| `desktop missing thread <id>` / `phone missing ELINS <key>` | **P1** | open P1 incident; cross-surface continuity failure |
| `<surface> onboarding for <handle> took <ms>ms (limit <limit>ms)` | **P1** | open P1 incident if reproducible; threshold breach |
| `monotonicity violated: iteration N ELINS count C2 < ...` | **P1** | open P1 incident; suspected state leakage |
| `timing variance: max ... > 2× mean (...)` | **P2** | log P2; investigate progressive slowdown but does not block launch |
| `iteration N threw: ...` | **P1** | open P1 incident; read stderr.log for stacktrace |
| `unknown scenario: ...` | **P2** | configuration error; not a substrate failure |

P3 is reserved for cosmetic / logging-only issues that the runner does
not currently emit. The dashboard accepts P3 incidents only via direct
operator post.

The acceptance harness does **not** automatically open incidents. The
operator (or a future CI job) parses `report.json` and POSTs to
`/founder/acceptance/incidents` for triage.

---

## Cross-references (Phase 4 additions)

The descriptive failure-mode map above is intentionally compact. The
realistic catalogue with operator actions and non-action rules lives in
[`failure_modes.md`](failure_modes.md). Reach for it whenever a run
emits a non-PASS result and you need to triage.

Companion documents written in Phase 4:

- [`operator_run_instructions.md`](operator_run_instructions.md) —
  end-to-end operator procedure for running the harness.
- [`run_sequence_diagram.md`](run_sequence_diagram.md) — ASCII +
  Mermaid sequence diagrams of operator → shell → runner → scenarios →
  ingest → dashboard.
- [`failure_modes.md`](failure_modes.md) — realistic P0/P1/P2 catalogue
  with symptoms, likely causes, operator actions, non-action rules.
- [`ingest_validation.md`](ingest_validation.md) — step-by-step
  validation of the post-run ingest pipeline (including `--dry-run`).
- [`dashboard_verification.md`](dashboard_verification.md) — endpoint +
  web-route verification of the founder dashboard.
- [`expected_outputs/realistic_run/`](expected_outputs/realistic_run/) —
  curated example of a realistic run report (mixed timings, all-pass
  with notable variance).
- [`expected_outputs/ingest_preview.jsonl`](expected_outputs/ingest_preview.jsonl) —
  one-line example of what `post_run_ingest.py` appends.

## Anti-execution constraints

This document is descriptive. It deliberately does not include:

- Live `bash` or `node` or `python` invocations.
- Any command that would start the harness during materialization.
- Any link to a CI trigger.

The shell script `scripts/run_acceptance.sh` carries the only live
commands; it is invoked manually by the operator and never by Claude
during materialization.
