# Deploy Checklist — v0.3.13 (TASK 19)

Assumes the backend + console commits are landed (via `commit_backend.sh` +
`commit_console.sh`). **Excludes all Stripe / billing-mode / webhook changes**
(see `BILLING_C1_STRIPE_PLAN.md` — separate track).

## 0. Preconditions
- [ ] On the landing branch; backend + console commits present (`git log`).
- [ ] No Stripe env touched this release: `CLARITYOS_STRIPE_MODE`,
      `CLARITYOS_STRIPE_SECRET_KEY`, `CLARITYOS_STRIPE_WEBHOOK_SECRET`,
      `CLARITYOS_BILLING_MODE` **unchanged**. No `/billing/webhook` code change.

## 1. Backend tests
- [ ] `CLARITYOS_BACKEND=memory python -m pytest tests/ -q` → **9028 / 0**.

## 2. Console tests
- [ ] `npm --prefix web run test` → **650 / 0**.
- [ ] `npm --prefix desktop run test` → **265 / 0**.
- [ ] Phone: `PHONE_MODE=C1` → in-package `npm --prefix phone run test` (48);
      or `C2` → `(cd phone && ../web/node_modules/.bin/vitest run lib/__tests__ --environment node)` (243).

## 3. Version + tag
- [ ] `git apply landing_v0.3.13/build_version.patch` (BUILD_VERSION → 20260527222355; backend → 4.24).
- [ ] Commit release chore (see `TAG_PLAN_v0.3.13.md`).
- [ ] `git tag -a v0.3.13 -m "…"` (annotation in `TAG_PLAN_v0.3.13.md`).
- [ ] `git push && git push --tags` (after review/approval).

## 4. Deploy API service (Cloud Run)
- [ ] Confirm `.gcloudignore` + `BUILD_VERSION` bumped (cache-bust).
- [ ] Deploy per `project_clarityos_layout` (no env-var changes this release).
- [ ] Post-deploy smoke:
  - [ ] `GET /health` → `version: "4.24"`, build `20260527222355`.
  - [ ] `GET /operator/telemetry` → 200 with `behavioral_forecast` +
        `recommendation_narrative` keys present (neutral when no actions).
  - [ ] `POST /auth/enter` (form, valid email) → `{"status":"ok"}`; malformed → 400.
  - [ ] `GET /auth/verify?token=bad` → 400 generic "link no longer valid" page.
- [ ] Set production magic-link env if not already: `CLARITYOS_AUTH_BASE_URL`,
      `CLARITYOS_EMAIL_MODE=smtp` + `CLARITYOS_SMTP_*` (auth-only; not billing).

## 5. Deploy console bundle(s)
- [ ] Web: build + deploy the static site (Operator Console route live).
- [ ] Desktop: package via electron-builder (existing pipeline) if shipping a build.
- [ ] Phone: ship code + scaffolds; phone runner per chosen `PHONE_MODE`.

## 6. Post-deploy verification
- [ ] Operator Console (web) renders telemetry incl. Behavioral Forecast +
      Recommendations tiles (collapse when empty).
- [ ] No new errors in logs (auth tokens/emails never logged in `smtp` mode).
- [ ] Tag pushed; RC docs archived with the release.

## Rollback
- [ ] Revert the release commit + redeploy prior `BUILD_VERSION`; `/operator/*`
      and `/auth/*` are additive, so rollback is non-destructive (no schema/billing change).

## Explicitly NOT in this release
- ❌ Stripe live-mode cutover, key/secret changes, webhook hardening.
- ❌ `CLARITYOS_BILLING_MODE` flips. The only billing change is the **test-only**
  `grace_period` expectation fix (code behavior unchanged since 88cd5b4).
