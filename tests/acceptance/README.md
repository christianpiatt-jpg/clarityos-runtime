# Acceptance Harness

Operator-run validation harness for the ClarityOS surface integration.
Implements the polish-plan §8 binary acceptance criteria across web,
phone, and desktop.

## Layout

```
tests/acceptance/
├── runner.ts                  # entry point — orchestrates scenarios
├── config.ts                  # loads config.local.json
├── timer.ts                   # tiny timing helper
├── config.local.json          # per-environment config (gitignored)
├── scenarios/
│   ├── index.ts               # registry + fast/full mode selector
│   ├── 01_onboarding_per_surface.ts
│   ├── 02_cross_surface_jump.ts
│   ├── 03_two_operators_concurrent.ts   (placeholder)
│   ├── 04_artifact_presence.ts          (placeholder)
│   └── 05_stability_window.ts           (placeholder)
├── surfaces/
│   ├── web.ts                 # Playwright web driver
│   ├── desktop.ts             # Playwright Electron driver
│   └── phone.ts               # Maestro shell-out wrapper
├── .maestro/
│   ├── onboarding_phone.yaml
│   └── artifact_presence_phone.yaml
└── reports/                   # run outputs (gitignored)
```

## One-time setup (operator runs these — not Claude)

These commands install the dependencies the harness needs. **Claude does
not execute them.** Run them yourself on your environment.

```bash
# Playwright (web + electron driver)
npm install --save-dev @playwright/test ts-node typescript
npx playwright install chromium

# Maestro CLI (phone driver). macOS / Linux:
curl -Ls "https://get.maestro.mobile.dev" | bash
# then add ~/.maestro/bin to PATH

# Seed two test operators in users_store
python scripts/seed_acceptance_operators.py
# copy the printed IDs into config.local.json
```

## Configure

Open `tests/acceptance/config.local.json` and fill:

- `operators[].id` — the IDs printed by the seed script
- `surfaces.desktop.binaryPath` — absolute path to the built desktop binary
- `surfaces.web.baseUrl` — local web dev server URL (default
  `http://localhost:5173`)

Do not commit `config.local.json` — it contains environment-specific
operator identifiers.

## Run (operator runs — not Claude)

```bash
# Fast mode: scenarios 01 + 04 only.
npx ts-node tests/acceptance/runner.ts --mode=fast --run-id=local-001

# Full mode: all five scenarios.
npx ts-node tests/acceptance/runner.ts --mode=full --run-id=local-002

# Read the report:
cat tests/acceptance/reports/local-001/report.md
```

Exit codes:
- `0` — all scenarios pass
- `1` — one or more scenarios failed
- `2` — fatal runner error

## Acceptance dashboard

After the backend is running, the founder-only dashboard is at:

```
/founder/acceptance
```

It shows:
- the 72h stability window pass/fail
- open and resolved P0/P1 incidents
- run summaries from `tests/acceptance/reports/`

## P0/P1 severity definition (D3 default)

- **P0** — data loss · vault corruption · security boundary failure ·
  total surface outage.
- **P1** — visible write-path quota or auth error · artifact-presence
  failure on at least one surface for any operator · onboarding
  completion failure on a previously-passing surface.

## Notes

- The runner creates per-run vault secrets via `node:crypto::randomBytes`
  and never persists them. The placeholder `vault_secret` in
  `config.local.json` is overwritten in memory at load time.
- Maestro selectors and the appId in `.maestro/*.yaml` are placeholders;
  align them with the shipped phone UI text or testIDs before the first
  real run.
- Scenarios 03, 04, 05 are placeholders that return `pass: true` until
  implemented. The runner reports them as `(placeholder)` in the
  Markdown summary.
