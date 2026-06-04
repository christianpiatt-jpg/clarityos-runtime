# Console Landing Report (TASK 13)

Three surface-scoped patches bundling the Operator Console WIP + tests.

## Patches
| Patch | Files | Lines | Scope check | Content |
|---|---|---|---|---|
| `console_web_landing.patch` | 98 | 32045 | **100% `web/`, 0 foreign** | OperatorConsole.tsx + OperatorConsole.test.tsx + 48 libs + 48 specs |
| `console_desktop_landing.patch` | 100 | 29311 | **100% `desktop/`, 0 foreign** | OperatorConsoleShell.tsx + 48 libs + 49 scaffolds + setupTests.ts + shell spec |
| `console_phone_landing.patch` | 97 | 28445 | **100% `phone/`, 0 foreign** | operator_console.tsx + 48 libs + 48 scaffolds |

Test scaffold patches (subset, also standalone): `console_tests_desktop.patch` (49),
`console_tests_phone.patch` (48).

## Quality scan (added lines)
- `console.log`/`console.debug`: **0**
- commented-out `import`: **0**
- `TODO`/`FIXME`/`XXX`: **0**
- cross-surface contamination: **0** (every path begins with its own surface dir)

## Empirical verification (vitest)
| Surface | Result | Notes |
|---|---|---|
| web | **650 passed / 0 failed** (91 files) | full web suite |
| desktop | **265 passed / 0 failed** (50 files) | 49 scaffolds + OperatorConsoleShell spec |
| phone | **243 passed / 0 failed** (48 files) | pure operator-lib scaffolds, via web's vitest binary rooted at phone (node env) |

## Notes / decisions
- **`operator-api.test.ts` excluded from phone.** It is an API-*factory* test
  (imports values from `../api`), not an operator-console string-builder. The 48
  pure-lib tests import only *types* from `../api` (elided by esbuild) and pass.
  The factory test forces a value-transform of phone's surface-distinct `api.ts`,
  which trips esbuild in the cross-binary run; it needs phone's own harness.
  Desktop keeps all 49 (desktop `api.ts` ≡ web).
- **Phone harness:** phone has `node_modules` but **no vitest**. Landing phone
  tests for real (option C1) needs `vitest` as a phone devDep + a minimal
  `vitest.config` (node env). The scaffolds themselves are verified; only the
  in-package runner is outstanding. Option C2 (land untested, per phone
  precedent) remains valid.
- **Desktop harness** already present in WIP (`desktop/vite.config.ts` test block
  + `setupTests.ts`); no harness drift introduced.

## Phone landing modes — C1 vs C2 (`commit_console.sh`)
The phone commit step is `PHONE_MODE`-controlled; both land **identical phone code**
(operator_console.tsx + 48 libs + 48 scaffolds) and differ only in the runner.

| | C2 (default — precedent) | C1 (full parity) |
|---|---|---|
| Runner | none in-package; verify via web's vitest binary rooted at phone (node env) → **243/0** | `npm --prefix phone install -D vitest` + `phone/vitest.config.ts` (node env) → in-package **48/0** |
| Commit | `chore: operator console phone scaffolds (C2: verified externally)` | `feat: operator console phone (C1: in-package vitest runner)` |
| `operator-api.test.ts` | excluded (API-factory; needs value-transform of phone api.ts) | port it next (desktop already proves it passes) |
| Cost | no phone dep churn | adds a devDep + lockfile churn; needs network for install |

Recommendation: **C2** for the v0.3.13 cut (matches the existing phone precedent,
zero dependency risk); schedule **C1** as a fast follow to give phone real CI.
