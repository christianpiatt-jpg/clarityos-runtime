# RC v0.3.13 — Changelog

`feature/v0.3.13-engine-cohort-operator` — Operator-Intelligence Engine surfacing,
auth, and the cross-surface Operator Console.

## Added
- **Operator telemetry HTTP surface** — mounts `phase7_endpoint.py`
  (`GET /operator/telemetry`, `POST /operator/action`), exposing the committed
  Phase 7–9 engine (drift/coherence/trust telemetry, causal chains, action
  integration) to all clients.
- **Phase 10 & 11 surfacing** — `/operator/telemetry` now emits
  `behavioral_forecast` (10.4 envelope: forecast + stability + narrative) and
  `recommendation_narrative` (11.1), wiring the 9.3 influence stream → 10.1
  deltas → 10.2 stability → 10.3 narrative → 11.0 recommendations → 11.1 narrative.
  Closes the only engine-side surfacing gap.
- **Magic-link authentication** — `auth_magiclink.py` + `POST /auth/enter` /
  `GET /auth/verify`: CSPRNG one-time tokens (hash-at-rest, 5–15 min TTL,
  single-use, one live link/user), enumeration-safe, allowlist-only redirects,
  HttpOnly session cookie. Entry form is the external WordPress shell (no client
  login surface by design).
- **Operator Console (web · desktop · phone)** — 3 console shells + 48
  `operator*.ts` analysis modules per surface (Meta/Structural/Governance/…),
  with **49 web specs**, **49 desktop scaffolds**, **48 phone scaffolds**.
- **Peripheral engine modules** — `harmonizer.py` + `orientation_contracts.py`
  (cross-domain merge), `compass_elins_bridge.py` (ELINS↔Compass translation),
  all pure/additive/tested. Plus version-controlled `tests/test_phase6.py`.

## Fixed
- **Billing `grace_period` surface** — two stale tests still asserted the
  pre-`88cd5b4` `grace_period → past_due` mapping; updated to the distinct
  `grace_period` surface (matches the shipped code + the v42 amber-pill UI).

## Changed
- `tests/conftest.py` — `TESTING=1` (Phase 7 in-memory telemetry backend) +
  magic-link token store reset in `reset_stores`.

## Verification
- Backend: **9028 passed / 0 failed**. Console: web **650**, desktop **265**,
  phone **243** — all 0 failed. Total **10186 / 0**.
- Zero regressions (baseline failure set was 47 pre-existing reds: 45 unmounted
  Phase 7–11 endpoints + 2 stale billing tests; all resolved).

## Deferred (non-blocking)
- Phone in-package vitest runner (devDep + config); the phone scaffolds are green.
