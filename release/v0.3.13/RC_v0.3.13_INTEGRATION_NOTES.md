# RC v0.3.13 — Integration Notes

## Dependency graph
```
            ┌─ phase7_mount ──────────────┐
HEAD ───────┤                             ├─ console_web ──┐
            ├─ billing_fix                │  console_desktop ─┤─ deploy
            ├─ auth_magiclink             │  console_phone ─┘
            ├─ peripheral_{harmonizer,compass,phase6}
            └─ phase7_mount ─► phase10_11_surface   (surface REQUIRES mount)
```
- Backend patches (1–7) touch disjoint files except app.py/conftest (mount+auth,
  non-overlapping hunks). Independent in content; ordered for a green suite at
  each step.
- `phase10_11_surface` requires `phase7_mount` (endpoint must be mounted to test).
- Console patches (8–10) require the mount (the console reads `/operator/telemetry`),
  are mutually independent, and never cross surfaces.

## Patch order (reproducible)
```bash
git switch feature/v0.3.13-engine-cohort-operator   # or a clean branch off HEAD 2651c78
bash landing_v0.3.13/apply_bundle.sh                 # backend 1–7
git apply landing_v0.3.13/console_web_landing.patch      # 8
git apply landing_v0.3.13/console_desktop_landing.patch  # 9
git apply landing_v0.3.13/console_phone_landing.patch    # 10
```
All 10 verified to apply cleanly with plain `git apply` on a clean `HEAD`
worktree (TASK 11 + TASK 14).

## Verification steps
```bash
# backend (memory backend; ~14 min full)
CLARITYOS_BACKEND=memory python -m pytest tests/ -q          # 9028 passed / 0 failed
# console
npm --prefix web     run test    # vitest: 650 / 0
npm --prefix desktop run test    # vitest: 265 / 0
# phone (until a phone runner lands): web's binary rooted at phone
( cd phone && ../web/node_modules/.bin/vitest run lib/__tests__ --environment node )  # 243 / 0
```

## Operator notes / caveats
1. **Suite gate is the FULL pytest run**, not subset reasoning — that is how the
   2nd stale billing test (`test_fix_p1_billing_surface_hardening`) was caught
   after the 1st (`INV-H4`). Always run the full suite before declaring green.
2. **Phone runner is the one open item.** Option **C1**: add `vitest` to phone
   devDeps + a node-env `vitest.config`; then port `operator-api.test.ts` too
   (it needs a value-transform of phone's `api.ts`). Option **C2**: land phone
   untested per existing precedent. Pick explicitly.
3. **No client login surface** ships — magic-link entry is the external WordPress
   shell (`pro-mediations.com/enter/`). Set `CLARITYOS_AUTH_BASE_URL`,
   `CLARITYOS_EMAIL_MODE=smtp` (+ SMTP_* envs) for production; default `log` mode
   writes the link to logs (dev only).
4. **Deploy:** bump `BUILD_VERSION`, confirm `/health`, deploy to Cloud Run per
   `project_clarityos_layout`. Gate on the full green suite above.
5. **Baseline context:** a clean checkout of `HEAD` is itself **47 reds** (45
   unmounted Phase 7–11 endpoints + 2 stale billing). This RC turns it green; do
   not mistake those pre-existing reds for RC regressions.
6. **Scaffolds vs landing patches:** `console_tests_{desktop,phone}.patch` are
   subsets of the `console_{desktop,phone}_landing.patch` — apply the landing
   patches, not both (the scaffold patches are for isolated review only).

## Backend version
This RC is additive to the HTTP contract (new `/operator/*`, `/auth/*` routes;
new additive `behavioral_forecast` + `recommendation_narrative` keys on existing
telemetry). Bump `/health` minor accordingly at land time.

## Commit sequence (Phase 3 scripts)
**Backend — `landing_v0.3.13/commit_backend.sh`** (clean HEAD; landing inputs present):
1. Gate: apply all 7 backend patches → full pytest (require 0 failed) → `reset --hard`.
2. `feat: mount operator engine surface (phase7–9)`  — app.py, conftest.
3. `fix: billing grace_period mapping (C1)`            — 2 billing tests.
4. `feat: auth magic-link + peripheral modules + phase10/11 surface`
   — auth + 3 peripherals + phase7_endpoint + new tests.
Guards: no console files, no `landing_v0.3.13/` inputs, no uncommitted tracked changes.

**Console — `landing_v0.3.13/commit_console.sh`** (AFTER backend; `PHONE_MODE=C1|C2`):
1. `console_web_landing.patch`     → web vitest     → `feat: operator console web`.
2. `console_desktop_landing.patch` → desktop vitest → `feat: operator console desktop`.
3. `console_phone_landing.patch`   → phone gate     → phone commit (C1 in-package / C2 external).
Guards: every committed path is under `web/` | `desktop/` | `phone/` only.

**Release —** `git apply build_version.patch` → release chore commit → `git tag -a v0.3.13`.

Verified in throwaway worktrees: backend commit mechanics (3 commits, no leakage),
console commit mechanics (3 commits, surface-scoped, 0 backend leakage). vitest
gates 650/265/243 verified independently; backend full-suite gate = 9028/0.
