# Acceptance Harness — Failure-Mode Map

Realistic catalogue of what can go wrong during a real run, classified
by severity. Every entry has: **symptoms** (what the operator sees),
**likely cause**, **operator action**, and **non-action rules** (things
NOT to do).

Severity definitions follow the D3 default in `incident_store.py`:

- **P0** — data loss, vault corruption, security boundary failure,
  total surface outage.
- **P1** — visible write-path quota or auth error, artifact-presence
  failure on at least one surface for any operator, onboarding
  completion failure on a previously-passing surface.
- **P2** — UI selector drift, slow surfaces, individual flakiness that
  does not block launch acceptance.

The harness does NOT auto-classify or auto-incident. The operator
classifies and posts manually via
`POST /founder/acceptance/incidents`.

---

## P0 — block deploys

### P0.1 — Backend unreachable

**Symptoms**
- `report.md` shows every scenario `FAIL`.
- `messages` arrays contain `connect ECONNREFUSED 127.0.0.1:8000` or
  similar TCP-level errors.
- `report.json::pass` is `false`; every scenario duration is roughly
  the connect-timeout floor (~30s).

**Likely cause**
- Backend (uvicorn / app.py) was not started in a sidecar terminal.
- Port mismatch between `surfaces.web.baseUrl` and the running backend.
- Network or DNS misconfig if running against a remote backend.

**Operator action**
1. Confirm backend is up: `curl -fsS http://localhost:8000/health`.
2. Confirm `tests/acceptance/config.local.json::backend_base_url`
   matches the live URL.
3. Restart the backend, re-run the harness.
4. If reproducible, post a P0 incident citing the run id.

**Non-action rules**
- Do **not** edit `report.json` to mark scenarios as passing.
- Do **not** disable the failing scenarios in
  `tests/acceptance/scenarios/index.ts` to "get green".
- Do **not** ship until a clean run lands.

### P0.2 — Vault corruption / cross-operator data leak

**Symptoms**
- Scenario 03 fails with
  `vault isolation breach (threads|elins|projects): shared keys ...`.
- Two operators' artifact sets overlap.

**Likely cause**
- Backend isolation bug: vault read path is not properly scoping by
  operator id.
- `memory_vault.py` salt / key derivation bug.
- Session token leak between operator contexts in the test driver.

**Operator action**
1. **Stop all deploys immediately.**
2. Capture `report.json`, `stdout.log`, `stderr.log` for the failing
   run; they are the forensic artefact.
3. Post a P0 incident with full detail.
4. Investigate the backend layer that owns vault key derivation
   (`memory_vault.py`).
5. Add a regression test before fixing.

**Non-action rules**
- Do **not** rerun in hopes of green.
- Do **not** clear the incident from the dashboard before root-cause is
  confirmed.

### P0.3 — Maestro CLI crash / phone process unrecoverable

**Symptoms**
- Phone scenarios fail with `failed to spawn maestro` or
  `maestro test exited with signal: SIGSEGV` in `stderr.log`.
- The simulator process becomes unresponsive; restarting Maestro alone
  does not help.

**Likely cause**
- Simulator OS update incompatibility.
- Phone build out of sync with the testIDs the YAML expects.
- Resource exhaustion (RAM / disk) during a long full-mode run.

**Operator action**
1. Confirm Maestro version: `maestro --version`.
2. Restart the simulator and Maestro; re-run only the phone scenarios.
3. If the crash is reproducible, treat as P0 — phone surface is
   functionally unavailable.

**Non-action rules**
- Do **not** mark the run green by removing the phone driver from
  `tests/acceptance/surfaces/phone.ts`.
- Do **not** commit local Maestro version overrides without a
  recorded rationale.

---

## P1 — investigate and fix before launch

### P1.1 — Scenario assertion failure (artifact presence)

**Symptoms**
- Scenarios 02 or 04 fail with `<surface> missing ELINS <key>` or
  `<surface> missing thread <id>`.
- The artifact was created on web but does not appear on phone or
  desktop.

**Likely cause**
- Cross-surface continuity broken: hydration is reading stale state.
- Vault snapshot not yet propagated to all surfaces (race on
  `pull-on-focus` semantics).
- The Maestro evalScript is reading from the wrong testID and missing
  artifacts that ARE present.

**Operator action**
1. Manually open each surface as the test operator and visually
   confirm artifact presence.
2. If the artifact is visually present, fix the testID alignment in
   `.maestro/artifact_presence_phone.yaml` (P2 in disguise).
3. If the artifact is genuinely missing on a surface, file a P1.
4. Inspect hydration code path on the surface that's missing the
   artifact.

**Non-action rules**
- Do **not** add a `wait` or `sleep` to the scenario as a workaround.
- Do **not** delete the artifact and re-run.

### P1.2 — Onboarding timing violation

**Symptoms**
- `<surface> onboarding for <handle> took <ms>ms (limit <limit>ms)`.
- Specific surface consistently exceeds the 10-minute budget.

**Likely cause**
- Backend latency under load.
- Web server cold start.
- Maestro / Playwright spawn overhead on a constrained machine.

**Operator action**
1. Re-run on a less-loaded machine to discriminate harness vs target.
2. If reproducible across machines, file P1 — the surface is too slow
   for the spec's 10-minute floor.
3. Profile the slowest panel via the FSM `_ts_ms` markers exposed by
   `getTimings()`.

**Non-action rules**
- Do **not** raise `onboarding_max_minutes` in `config.local.json` to
  "fix" this. The threshold is a polish-plan §8 contract value.

### P1.3 — Onboarding completion failure on a previously-passing surface

**Symptoms**
- Scenario 01 passed last run; this run fails on the same surface for
  the same operator.
- `messages` contains a hard error like
  `Panel 5 textarea did not appear within 30000ms`.

**Likely cause**
- Surface UI changed; the harness selectors are no longer aligned.
- Onboarding FSM deterministic-state regression (e.g., FSM stuck on
  a previous run's state).

**Operator action**
1. Compare the failing run's `report.md` against the prior green run.
2. Identify which step regressed.
3. File P1, root-cause the regression before re-running.

**Non-action rules**
- Do **not** clear the FSM state or vault state between iterations to
  "force" a pass.

### P1.4 — Stability monotonicity violation

**Symptoms**
- Scenario 05 fails with
  `monotonicity violated: iteration N ELINS count C2 < iteration M count C1`.
- Artifact count decreased between iterations.

**Likely cause**
- State leakage: an iteration is somehow clearing prior artifacts.
- Vault TTL or eviction running too aggressively.
- Test driver itself is mutating state it should not.

**Operator action**
1. Read scenario 05 details for the per-iteration counts.
2. Inspect the vault directly to see whether the artifacts are present
   server-side after the offending iteration.
3. File P1 — even if surface remains usable, monotonicity loss
   suggests a substrate-layer bug.

**Non-action rules**
- Do **not** lower the `MAX_TO_MEAN_RATIO` constant in
  `05_stability_window.ts` to mask the issue.

---

## P2 — log and investigate; does not block launch

### P2.1 — UI selector drift

**Symptoms**
- Scenario fails on a specific selector — e.g.,
  `Panel 1 input[name="handle"] not visible`.
- Manual inspection confirms the panel renders correctly with a
  different attribute or copy.

**Likely cause**
- A polish PR renamed a button label or replaced an `input[name]` with
  a `data-testid`.
- The Maestro YAML expects a testID that the RN component doesn't have.

**Operator action**
1. Update the selector in the relevant
   `tests/acceptance/surfaces/*.ts` or `.maestro/*.yaml`.
2. Add a P2 incident note linking the harness PR + the originating
   polish PR for traceability.
3. Re-run; the harness should green.

**Non-action rules**
- Do **not** revert the polish PR.
- Do **not** treat selector drift as a P1 — the surface still works,
  the harness is just out of sync.

### P2.2 — Slow surfaces (within budget)

**Symptoms**
- Timing variance scenario 05 reports
  `timing variance ok: max=Xms mean=Yms ratio=1.5+`.
- Run still passes (ratio < 2.0) but the trend is upward run-over-run
  on the dashboard's stability metrics view.

**Likely cause**
- Progressive cold-cache effects.
- A backend endpoint is gradually accruing cost (e.g., scanning a
  growing JSONL, unbounded incident store).
- The harness operator is on a shared machine with intermittent load.

**Operator action**
1. Open `/founder/acceptance/stability` and watch the trend across the
   last ~10 runs.
2. If `iteration_mean_ms_avg` climbs >25% from baseline, file P2 and
   profile the slowest backend endpoint.

**Non-action rules**
- Do **not** open a P1 unless the ratio actually crosses 2.0.

### P2.3 — Individual scenario flakiness

**Symptoms**
- A single scenario fails ~10% of runs with no consistent error
  pattern.

**Likely cause**
- Genuine race in the surface (rarely the harness itself).
- Local environment variance (network, simulator start-up jitter).

**Operator action**
1. Re-run; if the next run is green, log a P2 with both run-ids and
   move on.
2. If the failure rate creeps up over 3+ consecutive runs, escalate to
   P1.

**Non-action rules**
- Do **not** add `if (process.env.CI) {}` retry logic to the scenarios.
  The harness is intentionally retry-free so flakiness surfaces
  honestly.

---

## What the harness does NOT do automatically

The acceptance harness deliberately avoids several "smart" behaviours
to keep the failure surface honest:

| not done | rationale |
|---|---|
| automatic incident posting | the operator classifies; the harness reports |
| retry on transient failure | retries hide flakiness; we want it visible |
| Slack / email notifications | no external dependencies; dashboard is the channel |
| auto-skipping previously-failing scenarios | a known-bad scenario is still a known-bad scenario |
| auto-bumping thresholds in `config.local.json` | thresholds are spec values; the harness honours them |

Any of those would be a separate Phase 5+ feature, opt-in only, with
its own incident discipline.
