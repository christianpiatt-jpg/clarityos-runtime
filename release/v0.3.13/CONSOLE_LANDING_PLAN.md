# Operator Console — Landing Plan (TASK 7)

Branch `feature/v0.3.13-engine-cohort-operator`. Read-only audit; nothing
committed. Evidence: `git ls-files`/`diff` + Explore inventory.

## 1. Inventory (uncommitted)

| Surface | Console shell | added lines | `operator*.ts` libs | lib tests |
|---|---|---|---|---|
| web | `web/src/routes/OperatorConsole.tsx` | +2322 | 48 | **49** (vitest) |
| desktop | `desktop/src/OperatorConsoleShell.tsx` | +2049 | 48 | **0** |
| phone | `phone/app/operator_console.tsx` | +1880 | 48 | **0** |

144 untracked `operator*.ts` lib files total (48 × 3). **Perfect basename
parity** — the same 48 module basenames exist on every surface, grouped:
Meta\* (~14), Structural\* (~15), Governance\* (~8), Synthesis/Coherence/
Resilience/Immunity/Stability (~5), State/Diff (3), Signature (3), Timeline/
Diagnostics (2), Summaries (1).

## 2. Test-coverage gap

- **web** — 49 vitest specs in `web/src/lib/__tests__/operator*.test.ts`; runner
  configured (`vite.config.ts` test block). **Covered.**
- **desktop** — 0 lib specs, but the **harness already exists**
  (`desktop/vite.config.ts` test block + `desktop/src/setupTests.ts` +
  `desktop/src/__tests__/OperatorConsoleShell.test.tsx`). **Ready to receive ports.**
- **phone** — 0 specs, **no harness** (no test runner configured). Matches the
  repo precedent ("phone has no harness").

## 3. Portability finding (decisive for scaffolding)

The lib modules are **code-identical across surfaces** — a `diff` of
`web/…/operatorSummaries.ts` vs the desktop/phone copies shows **only comment
lines differ** (each non-web copy carries a "Desktop/Phone mirror of web/…"
header and condensed inline comments); every `export`d function and body is the
same. Verified: exports match 1:1 on all three surfaces.

**Consequence:** a web lib spec ports to desktop with **no test-body change**.
The specs use only relative imports (`../api` types + `../<module>`), which
resolve identically under `desktop/src/lib/__tests__/` (desktop has its own
`src/lib/api.ts` with the same `EngineV1*` types). The port is therefore:

```
cp web/src/lib/__tests__/operatorSummaries.test.ts \
   desktop/src/lib/__tests__/operatorSummaries.test.ts
# …repeat for all 49; no edits to the test bodies.
```

(Phone, lacking a runner, needs a harness stood up first — see Phase C.)

## 4. Landing sequence (deterministic, dependency-ordered)

**Phase A — web console (lowest risk; already tested).**
1. Land `web/src/routes/OperatorConsole.tsx` + 48 `web/src/lib/operator*.ts` +
   49 `web/src/lib/__tests__/operator*.test.ts`.
2. Gate: `npm --prefix web run test` green + `tsc` clean.

**Phase B — desktop console (port-then-land).**
1. **Generate scaffolds:** copy all 49 `web/src/lib/__tests__/operator*.test.ts`
   → `desktop/src/lib/__tests__/` (mechanical; bodies unchanged).
2. Gate: `npm --prefix desktop run test` green + `tsc` clean. Fix only import/
   type drift surfaced by the compiler (expected to be near-zero given §3).
3. Land `desktop/src/OperatorConsoleShell.tsx` + 48 desktop libs + the 49 ports.

**Phase C — phone console (harness decision required).**
- **C1 (parity, recommended):** stand up a phone vitest/jest-expo runner +
  setup file, port the 49 specs, gate green, then land
  `phone/app/operator_console.tsx` + 48 phone libs + specs.
- **C2 (precedent):** land phone untested (as the existing phone surfaces are).
  Risk is bounded — the lib code is identical to the web/desktop logic verified
  in A/B — but there is no phone regression net. **Flag, don't silently pick.**

## 5. Required test scaffolds — status

- **Mechanism:** verified (§3) — direct copy, no body edits, harness exists for
  desktop.
- **Generation + verification of the 49 desktop ports** is itself Phase B.1–B.2
  above; it needs desktop `node_modules` + a vitest run, so it is an executable
  landing step, not a static artifact. I can generate all 49 and run desktop
  vitest on request.

## 6. Effort / risk

| Item | Size | Note |
|---|---|---|
| Phase A (web) | **M** | tested; review 48 libs + shell, run vitest |
| Phase B (desktop) | **M** | 49 mechanical ports + 1 vitest run + shell review |
| Phase C (phone) | **M–L** | L if standing up a harness (C1); M if untested (C2) |
| R1 risk | High→Med | desktop coverage closes after Phase B; phone is the residual |
