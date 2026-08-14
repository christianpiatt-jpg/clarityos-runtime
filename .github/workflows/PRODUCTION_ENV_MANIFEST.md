# Production environment manifest — `clarity-engine`

**NAMES AND SECRET-MANAGER PATHS ONLY. NO VALUES.**
This file is generated from the live Cloud Run spec with values filtered
out in the pipeline; it must never be edited to carry one.

- Service: `clarity-engine` · region `us-central1` · project `founding-os`
- Entries: **43** — 25 secret-backed, 18 literal
- Measured: 2026-08-13

## Why this file exists

`.github/workflows/deploy.yml` declares **9** entries. The service runs
**43**. `deploy-cloudrun`'s `env_vars:`/`secrets:` inputs are
declarative, so activating that recipe as written deletes the difference.
Reconcile against this list before uncommenting anything there.

Production is deployed by `./deploy.sh` (`gcloud run deploy --source .`
with `--update-env-vars`, a merge), which is why these survive releases.

## Secret-backed

| name | Secret Manager path |
|---|---|
| `ANTHROPIC_API_KEY` | `projects/founding-os/secrets/ANTHROPIC_API_KEY:latest` |
| `CLARITYOS_ADMIN_PASSWORD` | `projects/founding-os/secrets/clarityos-admin-password:3` |
| `CLARITYOS_ANTHROPIC_KEY` | `projects/founding-os/secrets/ANTHROPIC_API_KEY:latest` |
| `CLARITYOS_DEEPSEEK_KEY` | `projects/founding-os/secrets/DEEPSEEK_API_KEY:latest` |
| `CLARITYOS_GEMINI_KEY` | `projects/founding-os/secrets/GEMINI_API_KEY:latest` |
| `CLARITYOS_MISTRAL_KEY` | `projects/founding-os/secrets/MISTRAL_API_KEY:latest` |
| `CLARITYOS_OPENAI_KEY` | `projects/founding-os/secrets/OPENAI_API_KEY:latest` |
| `CLARITYOS_OPERATOR_TOKEN` | `projects/founding-os/secrets/clarityos-operator-token:latest` |
| `CLARITYOS_PERPLEXITY_API_KEY` | `projects/founding-os/secrets/PERPLEXITY_API_KEY:latest` |
| `CLARITYOS_SMTP_PASSWORD` | `projects/founding-os/secrets/clarityos-smtp-token:3` |
| `CLARITYOS_SMTP_USER` | `projects/founding-os/secrets/clarityos-smtp-token:3` |
| `CLARITYOS_STRIPE_SECRET_KEY` | `projects/founding-os/secrets/clarityos-stripe-secret-key:5` |
| `CLARITYOS_STRIPE_WEBHOOK_SECRET` | `projects/founding-os/secrets/clarityos-stripe-webhook-secret:9` |
| `CLARITYOS_VAULT_SECRET` | `projects/founding-os/secrets/clarityos-vault-secret:latest` |
| `CLARITYOS_XAI_KEY` | `projects/founding-os/secrets/XAI_API_KEY:latest` |
| `DEEPSEEK_API_KEY` | `projects/founding-os/secrets/DEEPSEEK_API_KEY:latest` |
| `GEMINI_API_KEY` | `projects/founding-os/secrets/GEMINI_API_KEY:latest` |
| `INVITE_HMAC_SECRET` | `projects/founding-os/secrets/invite-hmac-secret:2` |
| `MISTRAL_API_KEY` | `projects/founding-os/secrets/MISTRAL_API_KEY:latest` |
| `OPENAI_API_KEY` | `projects/founding-os/secrets/OPENAI_API_KEY:latest` |
| `PERPLEXITY_API_KEY` | `projects/founding-os/secrets/PERPLEXITY_API_KEY:latest` |
| `POSTMARK_SERVER_TOKEN` | `projects/founding-os/secrets/clarityos-smtp-token:latest` |
| `STRIPE_SECRET_KEY` | `projects/founding-os/secrets/clarityos-stripe-secret-key:5` |
| `STRIPE_WEBHOOK_SECRET` | `projects/founding-os/secrets/clarityos-stripe-webhook-secret:9` |
| `XAI_API_KEY` | `projects/founding-os/secrets/XAI_API_KEY:latest` |

## Literal (set directly on the service)

Values are intentionally omitted. Read them from the live service when
needed; do not record them here.

| name |
|---|
| `BRANCH` |
| `BUILD_TAG` |
| `CLARITYOS_BACKEND` |
| `CLARITYOS_BILLING_MODE` |
| `CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED` |
| `CLARITYOS_EMAIL_MODE` |
| `CLARITYOS_FELT_GAP_ALLOWLIST` |
| `CLARITYOS_FELT_GAP_READER_ENABLED` |
| `CLARITYOS_INVITE_BASE_URL` |
| `CLARITYOS_PUBLIC_BASE_URL` |
| `CLARITYOS_ROTATION_MARKER` |
| `CLARITYOS_SMTP_FROM` |
| `CLARITYOS_SMTP_HOST` |
| `CLARITYOS_SMTP_PORT` |
| `CLARITYOS_STRIPE_MODE` |
| `CLARITYOS_STRIPE_PRICE_FOUNDING` |
| `CLARITYOS_VAULT_BACKEND` |
| `COMMIT_SHA` |
