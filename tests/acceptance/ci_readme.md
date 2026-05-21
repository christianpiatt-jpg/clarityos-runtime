# Acceptance Harness — CI README

This document describes how the acceptance harness *would* run under CI
when the operator chooses to enable it. The harness is fully
materialized; CI is currently **inactive** by design.

## Why the workflow lives at `tests/acceptance/ci/acceptance.yml`

Materialization Constraint 3 prohibits creating new top-level
directories during write-only mode. The repo currently has no
`.github/` directory, so the CI workflow was placed at
`tests/acceptance/ci/acceptance.yml`. Every functional line in that
file is commented out, so even if CI accidentally picked it up, it
would parse as empty.

## To enable CI (operator-only step)

When the operator decides to wire CI:

1. Create the canonical workflow path:

   ```bash
   mkdir -p .github/workflows
   ```

2. Copy the materialized draft:

   ```bash
   cp tests/acceptance/ci/acceptance.yml .github/workflows/acceptance.yml
   ```

3. Open `.github/workflows/acceptance.yml` and uncomment the workflow
   body. Every functional line currently has a leading `#`. Removing
   those activates the workflow.

4. Review and adjust:
   - Trigger: `workflow_dispatch` is the safe default. Add `schedule:`
     and/or `pull_request:` only after a baseline manual run succeeds.
   - `runs-on`: defaults to `macos-latest` for desktop binary parity.
     Use `ubuntu-latest` if you only need web-mode fast runs (Linux
     cannot exercise the desktop scenarios).
   - `BACKEND_BASE_URL`: defaults to `http://localhost:8000`. Replace
     with a staging URL if running against a deployed backend.
   - `tests/acceptance/config.local.json`: write a CI-specific variant
     before the runner step. Either commit it under a different name
     (e.g., `config.ci.json`) and `cp` it into place at job start, or
     generate it inline from the seeded operator IDs.

5. Commit and push. CI runs on the next `workflow_dispatch` (or
   schedule / PR, whichever is enabled).

## What the workflow does

When active, the `acceptance` job follows the same lifecycle as a
local dry-run (`tests/acceptance/execution_plan.md` §Lifecycle) with
two differences:

- The runner is invoked via `bash scripts/run_acceptance.sh "${MODE}"`
  where `${MODE}` comes from `workflow_dispatch.inputs.mode`.
- Reports are uploaded as a GitHub Actions artifact named
  `acceptance-reports` with 30-day retention (configurable in the YAML).

## PR gating logic

The intended PR gating semantics are:

| harness exit | gate behaviour |
|---|---|
| 0 (all scenarios pass) | PR check ✅ |
| 1 (one or more failed) | PR check ❌; merge blocked |
| 2 (fatal runner error) | PR check ❌; merge blocked |
| 64 (usage error) | PR check ❌; merge blocked |

The draft YAML uses `continue-on-error: true` on the harness step so
that report artifacts upload even on failure, then a separate "Gate on
harness exit code" step exits non-zero if the harness failed. This
preserves diagnosability while still gating the PR.

## Artifact retention

The default workflow retains run artifacts for 30 days. To change:

- Bump `retention-days:` in the `actions/upload-artifact@v4` step.
- For long-term trend analysis, run `post_run_ingest.py` in CI (already
  wired in the draft) — that produces `acceptance_runs.jsonl` which is
  small enough to commit back to the repo via a follow-on PR if you
  want a permanent record.

## Secrets

The current draft requires **no secrets**. If you later add a real
backend URL or paid third-party integrations, register them as repo
secrets and reference them via `${{ secrets.NAME }}` — never paste
secrets into the YAML.

## When NOT to enable CI

CI is intentionally inactive while:

- The Maestro testIDs in the phone YAMLs are still placeholders
  (see `tests/acceptance/.maestro/onboarding_phone.yaml` ADJUSTMENT
  NOTES at file head).
- The desktop binary path is not yet pinned in
  `tests/acceptance/config.local.json`.
- The seed script `scripts/seed_acceptance_operators.py` has not been
  run in the target backend at least once.

Enabling CI before these are resolved produces consistent failures
that obscure real regressions.

## Anti-execution constraints

This README and the workflow YAML are documentation. Materialization
does not enable CI, install dependencies, or run any commands. Every
functional line in `acceptance.yml` is commented out; the migration
step (uncomment + copy) is operator-only.
