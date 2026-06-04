# RC v0.3.13 — Manifest

**Base:** HEAD `2651c78` · branch `feature/v0.3.13-engine-cohort-operator`
**Backend version target:** bump on land (see integration notes).
**Total verified:** 10186 tests passed / 0 failed (9028 backend + 650 web + 265 desktop + 243 phone).

## Patch artifacts
| # | Patch | Files | Verified |
|---|---|---|---|
| 1 | `phase7_mount.patch` | 2 | 483 phase tests green |
| 2 | `billing_fix.patch` | 2 | both grace_period tests green |
| 3 | `auth_magiclink_landing.patch` *(repo root)* | 4 | 42/42; 0 regressions |
| 4 | `peripheral_harmonizer.patch` | 3 | within 33 |
| 5 | `peripheral_compass_bridge.patch` | 2 | within 33 |
| 6 | `peripheral_phase6_test.patch` | 1 | within 33 |
| 7 | `phase10_11_surface.patch` | 2 | 5 new + endpoint suite |
| 8 | `console_web_landing.patch` | 98 | web vitest 650/0 |
| 9 | `console_desktop_landing.patch` | 100 | desktop vitest 265/0 |
| 10 | `console_phone_landing.patch` | 97 | phone vitest 243/0 |

Scaffold-only (subsets of 9/10): `console_tests_desktop.patch` (49),
`console_tests_phone.patch` (48).

## Document artifacts (`landing_v0.3.13/`)
- Plans: `LANDING_PLAN_v0.3.13.md`, `CONSOLE_LANDING_PLAN.md`
- Reports: `INTEGRATED_SUITE_REPORT.md`, `PATCHSET_NORMALIZATION_REPORT.md`,
  `MERGE_READY_BUNDLE_REPORT.md`, `CONSOLE_LANDING_REPORT.md`,
  `FINAL_GREEN_TREE_REPORT.md`
- RC: `RC_v0.3.13_MANIFEST.md` (this), `RC_v0.3.13_CHANGELOG.md`,
  `RC_v0.3.13_INTEGRATION_NOTES.md`
- Applier: `apply_bundle.sh` (backend 7-patch bundle)

## What lands (file inventory)
- **Backend:** `auth_magiclink.py`, `harmonizer.py`, `orientation_contracts.py`,
  `compass_elins_bridge.py` (+ tests); `phase7_endpoint.py` (Phase 10/11 emit);
  app.py (mount + auth routes), conftest (TESTING=1 + auth reset); 2 billing-test
  fixes; `tests/test_phase6.py`, `tests/test_phase10_11_endpoint.py`.
- **Console:** 3 shells (web/desktop/phone) + 144 `operator*.ts` libs + 49 web
  specs + 49 desktop scaffolds + 48 phone scaffolds + desktop setupTests/shell spec.

## Known-deferred (flagged, not blocking backend RC)
- Phone in-package vitest runner (devDep + config) — option C1; scaffolds green.
- `operator-api.test.ts` on phone (API-factory test; needs phone harness).
