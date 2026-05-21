# ClarityOS Runtime — Deployment Runbook

> PASS-6 Phase C reference. This document covers env-var configuration,
> first-run bootstrap, and the Cloud Run deployment shape. The
> `.github/workflows/deploy.yml` scaffold operationalises every step
> below once PASS-7 activates the real build + push + deploy stages.

---

## Environment variables

Every runtime knob is read from an `os.environ.get(...)` call in the
spine modules. The table below enumerates every variable the runtime
spine references, grouped by purpose. Use `.env.example` at the repo
root as a copy-friendly template for local development.

### Required in production

| Variable                              | Module(s)         | Effect                                                                                                                                                                                       |
| ------------------------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CLARITYOS_VAULT_SECRET`              | `memory_vault.py` | Master PBKDF2 input. Missing / empty / whitespace causes `_secret()` to raise `RuntimeError` at the first vault op (**INV-V8**). Mounted from Secret Manager in production.                  |
| `CLARITYOS_ADMIN_USER`                | `app.py`          | Bootstrap admin username. Defaults to `"admin"` if unset.                                                                                                                                    |
| `CLARITYOS_ADMIN_PASSWORD`            | `app.py`          | Bootstrap admin password. Required at startup when `CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED=1`.                                                                                                |
| `CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED` | `app.py`        | Set to `"1"` in production to refuse boot if the admin password is unset. Set to `"0"` only in dev.                                                                                          |
| `CLARITYOS_BACKEND`                   | many              | `"memory"` (tests / local) vs `"firestore"` (production). Drives the default storage backend for users / sessions / library / etc.                                                            |
| `CLARITYOS_VAULT_BACKEND`             | `memory_vault.py` | Vault-specific override. Production: `"firestore"`. Falls through to `CLARITYOS_BACKEND` semantics otherwise.                                                                                |

### Backend tuning (optional)

| Variable                  | Effect                                                                                          |
| ------------------------- | ----------------------------------------------------------------------------------------------- |
| `CLARITYOS_VAULT_DIR`     | `fs` backend root (default `~/.clarityos/vault`).                                               |
| `CLARITYOS_VAULT_DB`      | `sqlite` backend path (default `~/.clarityos/vault.sqlite3`).                                   |
| `CLARITYOS_VAULT_PBKDF2`  | PBKDF2 iteration override. Default is `DEFAULT_PBKDF2_ITERATIONS = 100_000`.                    |

### Plaintext mode (DEV ONLY)

| Variable                       | Effect                                                                                                                                                                                                          |
| ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CLARITYOS_VAULT_PLAINTEXT`    | **Only** the literal string `"true"` (case-insensitive, whitespace-trimmed) enables plaintext mode. Legacy values `"1"` / `"yes"` no longer enable (PASS-4 FIX-P3). Triggers a one-shot WARNING per process. |

**Never set this in production.** The CI gate (`test_deployment_runtime.py::TestB1PlaintextEnvVarMatrix`) covers the documented value matrix.

### Auth / session / rate limiting

| Variable                                 | Effect                                                                  |
| ---------------------------------------- | ----------------------------------------------------------------------- |
| `CLARITYOS_SESSION_TTL`                  | Session lifetime in seconds (default 86400).                            |
| `CLARITYOS_INVITE_ONLY`                  | `"1"` blocks `/register` outside the invite flow.                       |
| `CLARITYOS_INVITE_BASE_URL`              | Base URL for invite emails (production only).                           |
| `CLARITYOS_INVITE_TTL_DAYS`              | Invite expiry (default 30).                                             |
| `CLARITYOS_RATE_LIMIT_ENFORCE`           | `"0"` disables rate-limit enforcement (tests + local dev).              |
| `CLARITYOS_RATE_LIMIT_CAPACITY`          | Per-route capacity override.                                            |
| `CLARITYOS_RATE_LIMIT_WINDOW_S`          | Per-route window override (seconds).                                    |
| `CLARITYOS_CORS_ORIGINS`                 | Comma-separated allowed origins for CORS. Empty = no CORS.              |
| `CLARITYOS_LIBRARY_BUCKET`               | GCS bucket for `/library/*` uploads (production).                       |
| `CLARITYOS_LIBRARY_PREFIX`               | GCS object-key prefix inside the bucket.                                |

### Billing (Stripe)

| Variable                          | Effect                                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------------------------- |
| `CLARITYOS_BILLING_MODE`          | `"mock"` (default) / `"stripe"` / `"stripe_test"`. Resolved via `billing_config.get_billing_status`. |
| `CLARITYOS_MOCK_AUTO_CONFIRM`     | `"1"` (default) auto-confirms mock intents; `"0"` drives the async webhook flow.                  |
| `CLARITYOS_STRIPE_MODE`           | Explicit Stripe mode override.                                                                    |
| `CLARITYOS_STRIPE_SECRET_KEY`     | Live / test secret key. Mount from Secret Manager.                                                |
| `CLARITYOS_STRIPE_WEBHOOK_SECRET` | Webhook signing secret. Mount from Secret Manager.                                                |
| `CLARITYOS_RENEWAL_TICK_SECONDS`  | Renewal scheduler tick (default 86400).                                                           |

### Model-provider keys (BD3 router)

| Variable                       | Effect                                                                                                            |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| `CLARITYOS_OPENAI_KEY`         | Wires `_call_openai` to the real OpenAI API. Without it, the mock fallback applies.                                |
| `CLARITYOS_ANTHROPIC_KEY`      | Wires `_call_anthropic` to the real Anthropic API.                                                                |
| `CLARITYOS_GEMINI_KEY`         | Wires `_call_gemini` to the real Gemini API.                                                                      |
| `CLARITYOS_XAI_KEY`            | Wires `_call_xai` to the real xAI / Groq API (currently mock-only by design).                                     |
| `CLARITYOS_LOCAL_MODEL_PATH`   | Path to a local GGUF / ONNX model file; enables `local:llama3.1` via `local_model_runtime`.                       |

### Schedulers + ops

| Variable                              | Effect                                                                                  |
| ------------------------------------- | --------------------------------------------------------------------------------------- |
| `CLARITYOS_DISABLE_MACRO_SCHEDULER`   | `"1"` blocks the macro-ELINS scheduler daemon from booting at app import. CI uses this. |
| `CLARITYOS_LOG_LEVEL`                 | Standard `logging` level name (defaults to `INFO` in production).                       |
| `CLARITYOS_ELINS_JSON_PATH`           | Bootstrap ELINS state JSON path (optional).                                             |
| `CLARITYOS_EVIDENCE_DIR`              | Evidence-allow-listed directory roots (operator evidence ingestion).                    |
| `CLARITYOS_SMTP_HOST`                 | SMTP host for operator report emails (production).                                      |
| `CLARITYOS_SMTP_TO_OVERRIDE`          | Force every email to a fixed recipient (staging).                                       |

---

## First-run bootstrap

The runtime expects to be the only process initialising the storage
backend. On the very first deploy:

1. Provision the Firestore database (Cloud Run + GCP project setup is
   out of scope for this doc; see your platform runbook).
2. Mount `CLARITYOS_VAULT_SECRET` from Secret Manager into the Cloud
   Run service. Generate a strong random value (≥ 32 bytes,
   `secrets.token_urlsafe(32)`). Never reuse across environments.
3. Set `CLARITYOS_ADMIN_PASSWORD` (Secret Manager) and
   `CLARITYOS_ADMIN_USER` (env var). The first boot creates the admin
   user automatically when the user table is empty.
4. Boot the service. The startup log line `startup config backend=…
   admin_user=… admin_pwd_source=…` confirms the bootstrap. The
   admin user appears under the redacted `_user_ref` form (e.g.
   `"admin..."`) — never as the raw value.
5. Visit `/login` with the admin credentials, then bootstrap the
   founder cohort via `/founder/cohort/...` (covered in the product
   runbook, out of scope here).

---

## Production deployment shape (Cloud Run)

The intended shape — to be activated by PASS-7 via
`.github/workflows/deploy.yml`:

```
┌──────────────────────────────────────────────────────────────────┐
│ Cloud Run service: clarityos-runtime                             │
│   image:     <registry>/<project>/clarityos-runtime:vX.Y.Z       │
│   region:    <region>                                            │
│   min-instances: 1   (cold-start avoidance)                      │
│   max-instances: N                                               │
│   env_vars:                                                      │
│     CLARITYOS_BACKEND=firestore                                  │
│     CLARITYOS_VAULT_BACKEND=firestore                            │
│     CLARITYOS_BILLING_MODE=stripe                                │
│     CLARITYOS_LOG_LEVEL=INFO                                     │
│     CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED=1                      │
│     CLARITYOS_RATE_LIMIT_ENFORCE=1                               │
│   secrets:                                                       │
│     CLARITYOS_VAULT_SECRET           ← Secret Manager            │
│     CLARITYOS_ADMIN_PASSWORD         ← Secret Manager            │
│     CLARITYOS_STRIPE_SECRET_KEY      ← Secret Manager            │
│     CLARITYOS_STRIPE_WEBHOOK_SECRET  ← Secret Manager            │
│     CLARITYOS_OPENAI_KEY             ← Secret Manager            │
│     CLARITYOS_ANTHROPIC_KEY          ← Secret Manager            │
└──────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────────┐
│ Firestore (project default DB)                                    │
│   memory_vault collection — per-entry documents under            │
│     memory_vault/{user_id}/entries/{vault_key}                   │
│   users / sessions / library / timeline / membership_store /     │
│   ... (existing per-store collections)                           │
└──────────────────────────────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────────────┐
│ Secret Manager                                                   │
│   projects/<project>/secrets/clarityos-vault-secret              │
│   projects/<project>/secrets/clarityos-admin-password            │
│   projects/<project>/secrets/clarityos-stripe-secret             │
│   projects/<project>/secrets/clarityos-stripe-webhook-secret     │
│   projects/<project>/secrets/clarityos-openai-key (optional)     │
│   projects/<project>/secrets/clarityos-anthropic-key (optional)  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Multi-instance behaviour

Cloud Run scales the runtime horizontally. Every instance shares the
same Firestore database; module-level state is per-instance. The
PASS-5 + PASS-6 stabilisation tests prove the following hold across
instance boundaries (see [`docs/invariants.md`](invariants.md)):

* **Founder default** — vault-backed; instance A's `set_founder_default_model`
  call is visible to instance B on first read after cold start
  (INV-R2, `test_model_router_runtime.py::TestD1*`).
* **Operator state** — every per-user field flows through the vault;
  instance B's `get_operator_state` returns the same shape instance A
  wrote (`test_operator_state_runtime.py::TestB2OperatorStateMultiInstance`).
* **Encryption** — PBKDF2 derivation is deterministic; the key cache
  per instance re-derives identical bytes from the master secret +
  user_id (INV-V2, `test_memory_vault_runtime.py::TestB5VaultUnderDeployment`).
* **Macro run_ids** — the wall-clock ms component combined with the
  per-instance monotonic seq makes cross-instance collisions
  vanishingly unlikely under realistic load
  (`test_intelligence_kernel_runtime.py::TestD4*`).
* **HTTP timeout overrides** — `ContextVar`-scoped, per-asyncio-task;
  no cross-thread / cross-instance contamination (INV-R3).

---

## Pre-deploy checklist

Before cutting a release tag and triggering `deploy.yml`:

1. CI gate green on `main`:
   ```
   pytest -m "runtime_spine or privacy_surface or determinism_surface"
   ```
   Expected: **all green** (see PASS-6 Phase B summary for current
   suite sizes).

2. `BUILD_VERSION` bumped at the repo root.

3. `.env.example` updated if any new env var was introduced.

4. `docs/invariants.md` updated if any invariant changed (which means
   `test_runtime_inv_*.py` was also updated — the CI gate enforces
   this).

5. `docs/boundaries.md` updated if any import edge moved.

6. Cut the tag (`vX.Y.Z`); push it. The `deploy.yml` workflow runs
   under the dry-run scaffold until PASS-7 activates the real
   deployment steps.

---

## Local development

Use `.env.example` as a starting point:

```bash
cp .env.example .env
# Set at minimum:
#   CLARITYOS_VAULT_SECRET=<any non-empty value for dev>
# Everything else can stay at the defaults.

python -m pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080
```

The default config keeps everything in memory (`CLARITYOS_BACKEND=memory`),
billing in mock mode, scheduler off. The first `/login` request will
auto-create the admin user from `CLARITYOS_ADMIN_USER`.

To run the CI gate locally:

```bash
bash scripts/run_ci_gates.sh
```

Or individually:

```bash
pytest -m runtime_spine
pytest -m privacy_surface
pytest -m determinism_surface
```

---

## Activation plan for PASS-7

The `.github/workflows/deploy.yml` scaffold lists the exact steps that
PASS-7 will activate. Summary:

1. Provision GCP Workload Identity Federation provider.
2. Provision the deploy service account with `roles/run.admin`,
   `roles/iam.serviceAccountUser`, `roles/secretmanager.secretAccessor`.
3. Configure GitHub Actions secrets: `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`,
   `GCP_PROJECT_ID`, `GCP_REGION`.
4. Uncomment the `auth` + `build-push` + `deploy-cloudrun` steps in
   `deploy.yml`.
5. Add a `production` environment in repo settings with a required
   reviewer for production tags.
6. Tag-and-ship via `git tag v0.1.0 && git push --tags`.

---

## Minimal production env

The absolute minimum env-var set for a production Cloud Run deploy.
Everything else has a documented default. The PASS-6 Phase E test
suite (`tests/test_deployment_runtime.py::TestE1ContainerStartup`)
exercises a fresh-container boot against this exact configuration.

| Variable                                | Value (production)                              | Source                              |
| --------------------------------------- | ----------------------------------------------- | ----------------------------------- |
| `CLARITYOS_VAULT_SECRET`                | strong random ≥ 32 bytes                        | Secret Manager (mounted as env)     |
| `CLARITYOS_BACKEND`                     | `firestore`                                     | service config                      |
| `CLARITYOS_VAULT_BACKEND`               | `firestore`                                     | service config                      |
| `CLARITYOS_BILLING_MODE`                | `stripe`                                        | service config                      |
| `CLARITYOS_STRIPE_SECRET_KEY`           | live Stripe secret                              | Secret Manager                      |
| `CLARITYOS_STRIPE_WEBHOOK_SECRET`       | Stripe webhook signing secret                   | Secret Manager                      |
| `CLARITYOS_ADMIN_USER`                  | `admin` (or your chosen name)                   | service config                      |
| `CLARITYOS_ADMIN_PASSWORD`              | strong random ≥ 24 bytes                        | Secret Manager                      |
| `CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED` | `1`                                             | service config                      |
| `CLARITYOS_LOG_LEVEL`                   | `INFO`                                          | service config                      |
| `CLARITYOS_RATE_LIMIT_ENFORCE`          | `1`                                             | service config                      |
| `CLARITYOS_CORS_ORIGINS`                | comma-separated list of trusted web origins     | service config                      |

Example for a Cloud Run deployment (mirrors the commented block in
`.github/workflows/deploy.yml`):

```yaml
env_vars: |-
  CLARITYOS_BACKEND=firestore
  CLARITYOS_VAULT_BACKEND=firestore
  CLARITYOS_BILLING_MODE=stripe
  CLARITYOS_BOOTSTRAP_PASSWORD_REQUIRED=1
  CLARITYOS_LOG_LEVEL=INFO
  CLARITYOS_RATE_LIMIT_ENFORCE=1
  CLARITYOS_CORS_ORIGINS=https://app.example.com
secrets:  |-
  CLARITYOS_VAULT_SECRET=projects/${PROJECT_ID}/secrets/clarityos-vault-secret:latest
  CLARITYOS_ADMIN_PASSWORD=projects/${PROJECT_ID}/secrets/clarityos-admin-password:latest
  CLARITYOS_STRIPE_SECRET_KEY=projects/${PROJECT_ID}/secrets/clarityos-stripe-secret:latest
  CLARITYOS_STRIPE_WEBHOOK_SECRET=projects/${PROJECT_ID}/secrets/clarityos-stripe-webhook-secret:latest
```

**Never set `CLARITYOS_VAULT_PLAINTEXT` in production.** The runtime
invariant **INV-V4** requires the explicit string `"true"` to enable
plaintext mode — keeping the variable unset is the safe production
default. The deploy workflow's `env_vars:` block above intentionally
omits it.

---

## Local dev vs production — behaviour table

The runtime behaves identically across environments under the locked
invariants. The differences below are the documented operator-visible
deltas. Every cell is enforced by at least one test in
`tests/test_deployment_runtime.py` or `tests/test_runtime_inv_*.py`.

| Aspect                         | Local dev (`.env.example` defaults)         | Production (Cloud Run env)                            |
| ------------------------------ | ------------------------------------------- | ----------------------------------------------------- |
| `CLARITYOS_VAULT_PLAINTEXT`    | typically unset (encryption on)             | **must not be set** (encryption on; INV-V4 enforces) |
| `CLARITYOS_VAULT_SECRET`       | any non-empty value                         | mounted from Secret Manager, ≥ 32 random bytes        |
| `CLARITYOS_BACKEND`            | `memory` (or unset → defaults to memory)    | `firestore`                                           |
| `CLARITYOS_VAULT_BACKEND`      | `mock` (via `CLARITYOS_BACKEND=memory`)     | `firestore`                                           |
| `CLARITYOS_BILLING_MODE`       | `mock`                                      | `stripe`                                              |
| `CLARITYOS_MOCK_AUTO_CONFIRM`  | `1` (auto-confirm mock intents)             | not applicable (Stripe drives confirms)               |
| `CLARITYOS_DISABLE_MACRO_SCHEDULER` | `1` in CI; unset locally to exercise it | unset (scheduler runs)                                |
| `CLARITYOS_LOG_LEVEL`          | `INFO` or `DEBUG`                           | `INFO`                                                |
| Plaintext warning              | does NOT fire (unless `="true"` for testing)| does NOT fire (env var must be unset)                 |
| `clarityos.kernel.runs` stream | written to stdout (visible via `pytest -s`) | structured audit stream — ship to Cloud Logging       |
| Vault data lifetime            | process-local (lost on restart)             | durable (Firestore across instance restarts)          |
| Founder default propagation    | instant (shared `_MEM_STORE`)               | vault-backed; new instances re-read on cold start     |
| Stripe webhooks                | mock + auto-confirm                         | live Stripe signature verification                    |
| Email (operator reports)       | smtp host optional; suppressed if unset     | smtp host required for digest emails                  |
| CI gate enforcement            | run `bash scripts/run_ci_gates.sh`          | enforced on PR via `.github/workflows/ci.yml`         |
| Release artifact               | `dist/clarityos-runtime-<TAG>.tar.gz`       | container image in registry (post-PASS-7)             |

The five FIX-P5-scoped loggers behave identically in both
environments — no raw `user_id` / `session_id` / `client_secret` /
vault secret ever appears in their output. This is locked by
`test_runtime_inv_http.py::TestINV_H1_NoRawUserIdInLoggers` and
`tests/test_deployment_runtime.py::TestE3ObservabilitySurface`.

---

## How to use `deploy.yml`

The `.github/workflows/deploy.yml` workflow has two phases by design:

1. **Today (v0.1.0)** — Scaffold mode. The workflow triggers on `v*`
   tag pushes and on manual `workflow_dispatch`. It runs the
   ``ci-gate`` job (full CI gate against the tagged SHA) and then a
   ``deploy`` job that emits a dry-run notice. No image is built, no
   registry is touched, no deploy happens.

2. **After PASS-7** — Real deployment. The same workflow runs the
   same gate, then authenticates to GCP via Workload Identity
   Federation, builds + pushes a container image, and deploys to
   Cloud Run.

### Activation checklist (PASS-7)

The exact wiring lives under the `TODO(PASS-7)` block in
`.github/workflows/deploy.yml`. To activate:

1. **GCP setup**
   * Create the GCP project (or reuse an existing one).
   * Provision a Workload Identity Federation pool + provider that
     trusts this GitHub repository.
   * Create the deploy service account with these roles:
     - `roles/run.admin`
     - `roles/iam.serviceAccountUser`
     - `roles/artifactregistry.writer`
     - `roles/secretmanager.secretAccessor`
   * Create Secret Manager entries for every secret in the "Minimal
     production env" table above.

2. **Repo secrets** (Settings → Secrets and variables → Actions)
   * `GCP_WIF_PROVIDER` — full resource name of the WIF provider.
   * `GCP_DEPLOY_SA` — email of the deploy service account.
   * `GCP_PROJECT_ID` — the GCP project id.
   * `GCP_REGISTRY_HOST` — e.g. `us-central1-docker.pkg.dev`.

3. **Repo environment** (Settings → Environments)
   * Create a `production` environment with one or more required
     reviewers. Add `environment: production` to the `deploy` job in
     `deploy.yml`. Tag pushes will then pause for manual approval
     before deploying.

4. **Workflow edits**
   * Replace the `IMAGE_NAME` and `PROJECT_ID` placeholders at the top
     of `deploy.yml` (`REPLACE_IN_PASS_7`) with `${{ secrets.* }}`
     expressions.
   * Uncomment the four step blocks under the `TODO(PASS-7)` block
     (auth, buildx, build-push, deploy-cloudrun).

5. **Permissions bump**
   * Add `id-token: write` to the deploy job's `permissions:` block
     so the WIF auth step can mint the GCP token.

### What's placeholder vs real

| Element                                       | v0.1.0 state                                  | PASS-7 state                                       |
| --------------------------------------------- | --------------------------------------------- | -------------------------------------------------- |
| `on: push tags v*`                            | real                                          | real                                               |
| ci-gate job                                   | real (runs the same gate as ci.yml)           | real                                               |
| `env: IMAGE_NAME`                             | placeholder `REPLACE_IN_PASS_7`               | `${{ secrets.GCP_REGISTRY_HOST }}/.../runtime`     |
| `env: PROJECT_ID`                             | placeholder `REPLACE_IN_PASS_7`               | `${{ secrets.GCP_PROJECT_ID }}`                    |
| `env: CLOUD_RUN_SERVICE`                      | real (`clarityos-runtime`)                    | real                                               |
| `env: GCP_REGION`                             | real (`us-central1`)                          | real                                               |
| `Authenticate to GCP` step                    | commented (no auth)                           | uncommented, uses WIF                              |
| `Build + push runtime container` step         | commented (no build)                          | uncommented, uses `docker/build-push-action@v6`    |
| `Deploy to Cloud Run` step                    | commented (no deploy)                         | uncommented, uses `google-github-actions/deploy-cloudrun@v2` |
| Production reviewers gate                     | not configured                                | required-reviewer GitHub Environment               |

### Testing the scaffold locally

The deploy workflow's ci-gate job runs the exact same selector as
`.github/workflows/ci.yml` and `scripts/run_ci_gates.sh`. To preview
what it does:

```bash
bash scripts/run_ci_gates.sh union
```

The ``Emit release + target metadata`` step in the deploy job prints
the placeholder values to the workflow logs at scaffold time — useful
for confirming the env layout before activating PASS-7.
