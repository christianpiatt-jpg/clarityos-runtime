# LANDING PLAN — v0.3.13-engine-cohort-operator (TASK 8)

**Base:** HEAD `2651c78` · branch `feature/v0.3.13-engine-cohort-operator`
**Method:** every patch isolated + applied/verified on throwaway clean-HEAD
worktrees; `CLARITYOS_BACKEND=memory`. Main tree never modified.
**Artifacts:** all under `landing_v0.3.13/` (apply from repo root).

---

## Dependency-ordered sequence

```
1 mount ──► 2 billing ──► 3 auth ──► 4 peripherals ──► 5 phase10/11 surface ──► 6 console (web→desktop→phone) ──► 7 deploy
```
Steps 1–5 are backend and mutually independent in content (distinct
files/hunks) but are ordered so the suite is green after each. Step 6 depends
on step 1 (the console consumes `/operator/telemetry`). Step 7 is last.

| # | Step | Patch / action | Touches | Size | Verified |
|---|---|---|---|---|---|
| 1 | Mount Phase 7–9 surface | `phase7_mount.patch` | app.py +conftest (2 hunks) | S | ✅ 483 phase tests green on HEAD+mount |
| 2 | Fix stale billing tests | `billing_fix.patch` | 2 test files | XS | ✅ both grace_period tests green |
| 3 | Land auth magic-link | `auth_magiclink_landing.patch` | 4 files (+940) | S | ✅ 42/42; 0 auth regressions (proven) |
| 4 | Land peripheral modules | `peripheral_harmonizer.patch`, `peripheral_compass_bridge.patch`, `peripheral_phase6_test.patch` | 6 new files | M | ✅ 33 tests green on clean HEAD |
| 5 | Surface Phase 10 & 11 | `phase10_11_surface.patch` | phase7_endpoint.py +1 test | M | ✅ 5 new + endpoint suite green |
| 6 | Land Operator Console | see `CONSOLE_LANDING_PLAN.md` | web→desktop→phone | L | ⏳ web tested; desktop/phone need ports |
| 7 | Deploy | `BUILD_VERSION` bump + Cloud Run | — | XS | — |

**Integrated full suite (steps 1–5 stacked):** _running — will confirm 0 failed
/ ~8990 passed._ Fast subset across every touched area: **125 passed**.

---

## Per-step detail (reproducible)

### Step 1 — Mount Phase 7–9 surface  `phase7_mount.patch`
Mounts the committed unified router (`phase7_endpoint.py`: `GET /operator/telemetry`
+ `POST /operator/action`) + the `TESTING=1` harness flag. **This alone converts
45 of the 47 baseline reds to green.**
```
git apply landing_v0.3.13/phase7_mount.patch
python -m pytest tests/test_phase7*.py tests/test_phase8*.py tests/test_phase9*.py \
                 tests/test_phase10*.py tests/test_phase11*.py -q     # -> 483 passed
```

### Step 2 — Fix stale billing tests  `billing_fix.patch`
Two tests asserted the pre-`88cd5b4` mapping `grace_period → past_due`; `88cd5b4`
made grace_period distinct (and added a passing test) but missed these two:
`test_runtime_inv_http.py::…INV_H4…[grace_period-past_due]` and
`test_fix_p1_billing_surface_hardening.py::…test_existing_grace_period_maps_to_past_due`.
Patch updates both expectations to `grace_period` (+ renames the second).
```
git apply landing_v0.3.13/billing_fix.patch
python -m pytest tests/test_runtime_inv_http.py tests/test_fix_p1_billing_surface_hardening.py -q
```

### Step 3 — Land auth magic-link  `auth_magiclink_landing.patch`
4 files (+940/−3): `auth_magiclink.py`, `tests/test_auth_magiclink.py`, app.py
auth hunks, conftest auth hunks. No client login surface (WordPress shell, by
design). Proven zero-regression (failure set identical with/without auth).
```
git apply landing_v0.3.13/auth_magiclink_landing.patch
python -m pytest tests/test_auth_magiclink.py -q                     # -> 42 passed
```

### Step 4 — Land peripheral modules  (3 patches)
All pure, additive, **not wired into app.py**, fully tested:
`harmonizer.py`+`orientation_contracts.py` (+15 tests), `compass_elins_bridge.py`
(+5), `tests/test_phase6.py` (+10 — adds VC coverage for already-committed
phase6 source). Land order is free; suggested as listed.
```
git apply landing_v0.3.13/peripheral_harmonizer.patch
git apply landing_v0.3.13/peripheral_compass_bridge.patch
git apply landing_v0.3.13/peripheral_phase6_test.patch
python -m pytest tests/test_harmonizer.py tests/test_compass_elins_bridge.py tests/test_phase6.py -q  # -> 33 passed
```

### Step 5 — Surface Phase 10 & 11  `phase10_11_surface.patch`
Closes the only true engine-side gap: `/operator/telemetry` now emits
`behavioral_forecast` (10.4 envelope {forecast, stability, narrative}) and
`recommendation_narrative` (11.1). Wires the 9.3 influence stream → 10.1 deltas →
10.2 stability → 10.3 narrative → 11.0 recs → 11.1 narrative. Requires step 1.
```
git apply landing_v0.3.13/phase7_mount.patch        # if not already applied
git apply landing_v0.3.13/phase10_11_surface.patch
python -m pytest tests/test_phase10_11_endpoint.py -q               # -> 5 passed
```

### Step 6 — Land Operator Console — see `CONSOLE_LANDING_PLAN.md`
web (tested) → desktop (port 49 lib specs; harness exists) → phone (harness
decision: C1 stand-up vs C2 untested-precedent). **Largest remaining effort.**

### Step 7 — Deploy
Bump `BUILD_VERSION`, confirm `/health` version, deploy to Cloud Run per
`project_clarityos_layout`. Gate on a full green suite.

---

## Risks / decisions
| # | Item | Action |
|---|---|---|
| R1 | desktop/phone console untested (96 modules) | port web specs (Phase 6B); phone harness decision required |
| R2 | phone has no test runner | choose C1 (stand up) or C2 (land untested per precedent) — **do not silently pick** |
| R3 | one ~10k-line WIP blob | these isolated patches are the de-mixing; land as discrete commits |

## Artifact manifest (`landing_v0.3.13/`)
`phase7_mount.patch` · `billing_fix.patch` · `phase10_11_surface.patch` ·
`peripheral_harmonizer.patch` · `peripheral_compass_bridge.patch` ·
`peripheral_phase6_test.patch` · `CONSOLE_LANDING_PLAN.md` · this file.
(`auth_magiclink_landing.patch` lives at repo root.)
