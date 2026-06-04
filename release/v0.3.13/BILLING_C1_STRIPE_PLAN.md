# Billing C1 — Stripe Integration Plan (SEPARATE TRACK · NOT v0.3.13)

> **Scope guard:** Nothing in this plan ships with v0.3.13. v0.3.13 contains a
> **test-only** `grace_period` expectation fix; no Stripe code, env, key, or
> webhook change. This document is forward-looking only.

## 0. Current reality (baseline)
- **Mode:** mock by default. `billing_config.py` resolves mode via
  `CLARITYOS_STRIPE_MODE` → key prefix (`sk_live`/`sk_test`) → disabled.
- **Flows present:** PaymentIntent create/confirm (v31), subscription
  orchestration + endpoints (C1 steps 1–3), `/billing/webhook` with
  signature + idempotency (`seen_event`) + `record_billing_event` (PII-filtered).
- **State machine:** active / past_due / **grace_period** (now surfaced
  distinctly) / cancelled / failed; 24h renewal scheduler (3-retry/72h/grace).
- **Known noise (Perplexity-class findings):**
  - Webhook `bad_signature` from **quote-wrapped secrets** (fixed in df94c97 —
    keep the strip-guard; add a startup assertion).
  - Env/secret drift between mock and live; secrets in env vs Secret Manager.
  - Webhook retries / duplicate events → idempotency must be airtight.

## 1. Staging-first Stripe integration
1. **Stripe test account + restricted keys** (`sk_test_…`, `whsec_…test`).
2. Stand up a **staging** Cloud Run revision with `CLARITYOS_STRIPE_MODE=test`.
3. Drive the existing PaymentIntent + subscription flows end-to-end against
   Stripe **test mode** (Stripe CLI `stripe listen` → staging `/billing/webhook`).
4. No production traffic until staging is green for a full renewal cycle
   (activate → renew → past_due → grace → recover/cancel).

## 2. Env + Secret Manager wiring
- Move `CLARITYOS_STRIPE_SECRET_KEY` + `CLARITYOS_STRIPE_WEBHOOK_SECRET` into
  **GCP Secret Manager**; inject as Cloud Run secrets (not plain env).
- **Startup assertion:** fail fast if mode=live but a secret is missing,
  empty, or quote-wrapped (extend the df94c97 strip-guard into a validator).
- One source of truth for mode: `billing_config.get_billing_status()`; log the
  resolved mode (not the secret) at boot.

## 3. Webhook hardening
- Verify signature with the raw body (already done); reject missing/bad → 400.
- **Idempotency:** persist `event.id` (`seen_event`) before side effects;
  duplicate → short-circuit `{duplicate: true}` (already present — add a TTL'd
  store + a metric).
- Handle the full set: `checkout.session.completed`,
  `invoice.payment_{succeeded,failed}`, `customer.subscription.{updated,deleted}`.
- Mode-mismatch guard (test event on live endpoint) → 400.
- Emit structured `billing_event` logs with PII filtered; alert on
  failure-rate spikes (reuse the module-18 Stripe-webhook-failure alert).

## 4. Test strategy
- **Unit:** mode resolution, signature validation (incl. quote-wrapped secret),
  idempotency dedupe, state transitions, grace/renewal scheduler.
- **Integration (staging):** Stripe CLI fixtures for each event type → assert
  `users_store.set_billing_state` transitions + `/me/billing` surface.
- **Negative:** replayed event, tampered signature, mode mismatch, missing secret.
- **Gate:** no live cutover until the staging suite + a full simulated renewal
  cycle are green; keep mock-mode default for local/CI.

## 5. Rollout sequence (future)
1. Secret Manager wiring + startup validator (staging).
2. Webhook hardening + idempotency store + metrics (staging).
3. Full test-mode renewal-cycle soak.
4. Limited live cohort (founding members) with `CLARITYOS_STRIPE_MODE=live`.
5. General availability.

## Explicit non-goals here
- Any change landing in v0.3.13.
- Flipping `CLARITYOS_BILLING_MODE` / `CLARITYOS_STRIPE_MODE` in any environment now.
- Touching `/billing/webhook` code as part of the operator/auth/console release.
