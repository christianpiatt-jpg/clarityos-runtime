# Acceptance Harness — Run Sequence Diagram

Descriptive only. No execution paths in this file actually fire during
materialization. The sequences below trace what happens when the
operator invokes `scripts/run_acceptance.sh`.

---

## ASCII timeline (compact)

```
operator
  │
  │  bash scripts/run_acceptance.sh fast
  ▼
shell (run_acceptance.sh)
  │  generate run-id
  │  mkdir tests/acceptance/reports/<run-id>/
  │
  ▼
runner (tests/acceptance/runner.ts via npx ts-node)
  │  loadConfig(tests/acceptance/config.local.json)
  │  selectScenarios(mode)
  │
  ├─► scenario 01 (onboarding_per_surface)
  │     ├─► surfaces/web.ts       → Playwright Chromium
  │     ├─► surfaces/phone.ts     → Maestro CLI shell-out
  │     └─► surfaces/desktop.ts   → Playwright Electron
  │     ◄─ ScenarioResult { pass, duration_ms, messages }
  │
  ├─► scenario 02 (cross_surface_jump)              [full mode only]
  ├─► scenario 03 (two_operators_concurrent)        [full mode only]
  ├─► scenario 04 (artifact_presence)
  └─► scenario 05 (stability_window)                [full mode only]
  │
  │  write report.json + report.md to <run-dir>/
  │  exit 0|1|2
  ▼
shell (run_acceptance.sh)
  │  tee stdout.log + stderr.log into <run-dir>/
  │  print artifact paths
  │  print "next step: post_run_ingest.py <run-dir>"
  │  exit (propagated from runner)
  ▼
operator
  │
  │  python tests/acceptance/post_run_ingest.py --dry-run <run-dir>
  ▼
ingest (post_run_ingest.py, dry-run)
  │  read <run-dir>/report.json
  │  print compact record (no disk write)
  ▼
operator (confirms shape)
  │
  │  python tests/acceptance/post_run_ingest.py <run-dir>
  ▼
ingest (post_run_ingest.py, real)
  │  read <run-dir>/report.json
  │  append one line to tests/acceptance/reports/acceptance_runs.jsonl
  ▼
operator
  │
  │  curl /founder/acceptance/runs/recent?limit=10
  │  open /founder/acceptance/runs in browser
  ▼
backend (acceptance_dashboard.py)
  │  read acceptance_runs.jsonl (try/except on missing/malformed)
  │  return last N records
  ▼
web (FounderAcceptanceRuns.tsx)
  │  fetch /founder/acceptance/runs/recent?limit=10
  │  render table
  ▼
operator (sees the run)
```

---

## Mermaid sequence diagram (rendered by GitHub / VSCode preview)

```mermaid
sequenceDiagram
    autonumber
    actor Op as Operator
    participant Sh as scripts/run_acceptance.sh
    participant R as tests/acceptance/runner.ts
    participant W as surfaces/web.ts (Playwright)
    participant Ph as surfaces/phone.ts (Maestro)
    participant D as surfaces/desktop.ts (Playwright/Electron)
    participant FS as report.json + report.md
    participant I as post_run_ingest.py
    participant J as acceptance_runs.jsonl
    participant API as backend /founder/acceptance/*
    participant UI as Web Founder Dashboard

    Op->>Sh: bash run_acceptance.sh <mode>
    Sh->>Sh: generate run-id; mkdir reports/<run-id>/
    Sh->>R: npx ts-node runner.ts --mode --run-id

    R->>R: loadConfig(config.local.json)
    R->>R: selectScenarios(mode)

    loop each selected scenario
        R->>W: onboardWeb / verifyWebArtifacts
        W-->>R: ScenarioResult fragment
        R->>Ph: onboardPhone / verifyPhoneArtifacts
        Ph-->>R: ScenarioResult fragment
        R->>D: onboardDesktop / verifyDesktopArtifacts
        D-->>R: ScenarioResult fragment
    end

    R->>FS: write report.json
    R->>FS: write report.md
    R-->>Sh: exit code

    Sh->>FS: tee stdout.log, stderr.log
    Sh-->>Op: print artifacts and next-step hint

    Op->>I: post_run_ingest.py --dry-run <run-dir>
    I->>FS: read report.json
    I-->>Op: print preview (no disk write)

    Op->>I: post_run_ingest.py <run-dir>
    I->>FS: read report.json
    I->>J: append one record

    Op->>API: GET /founder/acceptance/runs/recent
    API->>J: read last N records
    API-->>Op: JSON

    Op->>UI: open /founder/acceptance/runs
    UI->>API: fetch /runs/recent
    API-->>UI: JSON
    UI-->>Op: render table
```

---

## Phase boundaries

The diagram crosses three trust phases:

1. **Materialization phase (Phases 1–4)** — Claude wrote files; nothing
   above this line executes during materialization.
2. **Operator-driven phase** — the operator manually triggers each step
   (`run_acceptance.sh`, `post_run_ingest.py`, dashboard hits). Each
   step is a deliberate, auditable invocation.
3. **CI phase (Phase 5, opt-in)** — the operator copies
   `tests/acceptance/ci/acceptance.yml` to `.github/workflows/`, removes
   the comment prefixes, and pushes. Subsequent runs follow the same
   sequence above but are triggered by GitHub Actions instead of a
   shell prompt.

The acceptance harness itself does not change between phases. Only the
trigger does.
