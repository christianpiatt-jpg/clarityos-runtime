# ClarityOS Runtime

> PASS-6 Phase C — runtime section. This README focuses on the
> stabilised runtime spine; surface clients (web / phone / desktop)
> and the broader product layer have their own READMEs.

ClarityOS is an OS-shaped reasoning runtime. The runtime spine — five
modules, one cross-cutting privacy facade — is the locked architectural
contract that every higher-layer surface depends on.

---

## Runtime architecture (BD1–BD5)

The runtime is partitioned into five boundaries plus one cross-cutting
helper module. Each boundary owns a single responsibility, with import
edges flowing downward (BD1 → BD5).

```
                              BD1 — HTTP boundary
                          ┌──────────────────────┐
                          │      app.py          │
                          └──────────┬───────────┘
                                     │
                              BD2 — Kernel boundary
                          ┌──────────▼───────────┐
                          │ intelligence_kernel  │
                          └─────┬───────────┬────┘
                                │           │
            BD3 — Router        │           │   BD4 — State
        ┌─────────────────┐ ←───┘           └──→ ┌─────────────────────┐
        │  model_router   │ ←───  lazy  ───→     │  operator_state     │
        └────────┬────────┘                      └───────────┬─────────┘
                 │                                           │
                 └────────────────┬──────────────────────────┘
                                  │
                            BD5 — Vault boundary
                          ┌──────────────────────┐
                          │    memory_vault      │
                          └──────────────────────┘

        Cross-cutting facade (used by all five — no boundary):
                          ┌──────────────────────┐
                          │   runtime_privacy    │
                          └──────────────────────┘
```

| ID  | Module                    | Responsibility                                                                          |
| --- | ------------------------- | --------------------------------------------------------------------------------------- |
| BD1 | `app.py`                  | Routes, auth, CORS, error envelope, rate limit, bcrypt                                  |
| BD2 | `intelligence_kernel.py`  | ESO funnel, model funnel, audit funnel, S_ELINS QC, topic-label construction            |
| BD3 | `model_router.py`         | Provider selection, outbound HTTP, mock fallback, founder default (vault-backed)        |
| BD4 | `operator_state.py`       | Per-user preferences, history, decay, continuity — sole storage dep is BD5              |
| BD5 | `memory_vault.py`         | Per-user encrypted KV — PBKDF2 + HMAC-CTR + HMAC-SHA256 MAC; namespace allow-list       |
| —   | `runtime_privacy.py`      | Pure-string redaction helpers (`user_ref`, `session_ref`, `prompt_preview`, `topic_trim`, `event_ref`) |

See [`docs/boundaries.md`](docs/boundaries.md) for the import-edge
contract and the two documented lazy back-edges.

---

## Locked invariants

The PASS-4 hardening fixes and PASS-5 stabilization tests locked a set
of architectural invariants in [`docs/invariants.md`](docs/invariants.md).
Every invariant is backed by at least one explicit test in
`tests/test_runtime_inv_*.py` and one stability test in the Phase D /
Phase B runtime suites.

Summary by boundary (full text + test references in
[`docs/invariants.md`](docs/invariants.md)):

- **BD3 (router)** — selection precedence is `override > founder > preferred_model > task default`; founder default is vault-backed; HTTP timeout is per-context via `contextvars.ContextVar`; mock-result preview uses `runtime_privacy.prompt_preview`.
- **BD2 (kernel)** — `_macro_seq_lock` is pre-allocated; macro `run_id` format is `macro_<ts_ms>_<seq>` with strictly monotonic seq; every `run_*` surfaces `model_id`; ESO failures degrade gracefully.
- **BD4 (state)** — `_next_seq` is strictly monotonic per prefix; `HISTORY_MAX=200` enforced on live and migration paths; `_strip_forbidden` removes the four documented prompt-body keys.
- **BD5 (vault)** — `_KEY_CACHE` has a 3600s TTL; PBKDF2 derivation is deterministic; `CLARITYOS_VAULT_PLAINTEXT` enables only on explicit `"true"`; plaintext warning fires exactly once per process; namespace allow-list validates every key.
- **BD1 (http)** — no raw `user_id` or `session_id` in any FIX-P5-scoped logger; `/billing/intent/confirm` response is field-projected (no `client_secret`, no metadata); `/me/billing` maps `billing_state == "failed"` distinctly.

---

## Repo layout

```
.
├── app.py
├── intelligence_kernel.py
├── model_router.py
├── operator_state.py
├── memory_vault.py
├── runtime_privacy.py
├── runtime_http_config.py
├── kernel_logging.py
├── ELINS/                      # ELINS sub-pipeline (used by BD2)
├── requirements.txt
├── pytest.ini                  # PASS-6 Phase A — CI gate markers
├── .env.example                # local-dev env-var template
├── tests/
│   ├── conftest.py             # marker auto-assignment + reset fixtures
│   ├── test_runtime_inv_*.py   # PASS-6 Phase A — invariant tests
│   ├── test_*_runtime.py       # PASS-5 Phase D + PASS-6 Phase B
│   ├── test_module_load_guards.py
│   ├── test_deployment_runtime.py
│   └── test_fix_*.py           # PASS-4 fix-locked regression tests
├── docs/
│   ├── runtime_architecture.md # full BD1–BD5 architecture
│   ├── boundaries.md           # per-boundary contract
│   ├── invariants.md           # locked invariants reference
│   └── deployment.md           # env vars + deploy + first-run runbook
├── .github/workflows/
│   ├── ci.yml                  # PASS-6 Phase C — CI gate
│   └── deploy.yml              # PASS-6 Phase C — deploy scaffold
└── scripts/
    └── run_ci_gates.sh         # local CI-gate driver
```

> **Note on canonical packaging.** A future refactor may move the
> runtime spine modules under a `clarityos/` package directory (with
> a single `__init__.py`). The current root-level layout is the
> production-deployed structure; `docs/runtime_architecture.md`
> documents both views. Tests, CI gates, and `pytest.ini` are agnostic
> to which layout is on disk.

---

## Running the runtime

### Local development

```bash
# 1. Copy the env-var template and fill in values.
cp .env.example .env
# At minimum, set CLARITYOS_VAULT_SECRET. Everything else can stay default.

# 2. Install deps (Python 3.12).
python -m pip install -r requirements.txt

# 3. Boot the FastAPI app.
uvicorn app:app --host 0.0.0.0 --port 8080
```

Health checks:

```bash
curl http://localhost:8080/healthz
curl http://localhost:8080/runtime/providers/health  # founder-only
```

### Running tests

```bash
# Full suite (all tests in the repo).
pytest tests/

# CI gate union — the same selection ci.yml runs on every PR.
pytest -m "runtime_spine or privacy_surface or determinism_surface"

# Individual suites:
pytest -m runtime_spine        # cross-module spine tests
pytest -m privacy_surface      # logging / billing redaction tests
pytest -m determinism_surface  # selection / sequencing tests

# Or use the helper:
bash scripts/run_ci_gates.sh
```

Test markers are applied automatically by the
`pytest_collection_modifyitems` hook in `tests/conftest.py` — no
per-function decorators required.

### Preparing for deployment

See [`docs/deployment.md`](docs/deployment.md) for the full runbook.
Headline steps:

1. Configure GCP project, Workload Identity Federation, and Secret
   Manager entries for every required env var in `.env.example`.
2. Wire `CLARITYOS_VAULT_SECRET`, `CLARITYOS_STRIPE_SECRET_KEY`,
   `CLARITYOS_STRIPE_WEBHOOK_SECRET` as Secret Manager mounts in the
   Cloud Run service.
3. Set `CLARITYOS_BACKEND=firestore` and
   `CLARITYOS_VAULT_BACKEND=firestore` for production.
4. Cut a release tag (`vX.Y.Z`) — the `.github/workflows/deploy.yml`
   scaffold runs (currently a dry-run; PASS-7 activates the real
   build + push + deploy steps).

---

## Release tagging plan

| Tag        | Scope                                                                          |
| ---------- | ------------------------------------------------------------------------------ |
| **v0.1.0** | First stabilised runtime. PASS-4 hardening + PASS-5 stabilization + PASS-6 Phase A/B/C/D complete. CI gate green. Single-instance Cloud Run deployment supported. |
| **v0.2.0** | Web integration. `/web/` static site + cockpit + founder console wired to the stabilised runtime. No runtime spine changes. |
| **v1.0.0** | Multi-surface OS release. Phone (Expo) + Desktop (Electron) clients consume the same backend. Multi-instance Cloud Run with Firestore-backed vault. Founder cohort + billing live. |

Each tag is cut from `main` after the CI gate passes; `deploy.yml`
runs on the tag push and (once PASS-7 lands) drives the production
release.

---

## Cutting a release

The release engineering is documented in `CHANGELOG.md`,
`VERSION`, `docs/release_notes/`, and the `.github/workflows/release.yml`
workflow. To cut a new release:

### Step 1 — Update the version manifest

```bash
# Edit VERSION (no extra whitespace, no extra lines).
echo "v0.1.1" > VERSION

# Add a new section to CHANGELOG.md. The format is the same as the
# existing [v0.1.0] section. The release-integrity test
# (tests/test_release_integrity.py) will fail if CHANGELOG.md does
# not carry a heading for the exact value in VERSION.
$EDITOR CHANGELOG.md

# Create the release-notes source. The release workflow reads this
# file and uses it as the GitHub Release body.
$EDITOR docs/release_notes/v0.1.1.md
```

### Step 2 — Verify locally

```bash
# Re-run the CI gate against your working tree.
bash scripts/run_ci_gates.sh

# Run the release-integrity tests specifically — these confirm
# VERSION, CHANGELOG.md, the release workflow, and the release-notes
# source are all consistent.
pytest tests/test_release_integrity.py -q
```

### Step 3 — Tag + push

```bash
# Tag the commit. The tag value MUST match the contents of VERSION
# exactly — release.yml fails otherwise.
git tag v0.1.1
git push origin v0.1.1
```

### Step 4 — Observe the workflow

The `.github/workflows/release.yml` workflow then:

1. Checks out the tagged SHA.
2. Re-runs the full CI gate (`runtime_spine` + `privacy_surface` +
   `determinism_surface`). A release **MUST NOT** publish on a red
   gate.
3. Verifies `VERSION` matches the pushed tag.
4. Verifies `docs/release_notes/${TAG}.md` exists.
5. Builds a placeholder runtime tarball (`dist/clarityos-runtime-${TAG}.tar.gz`).
6. Uploads the tarball + JUnit report as workflow artifacts.
7. Publishes a GitHub Release with the release-notes file as the
   body and the tarball attached.

### How CI validates releases

| Check                                                      | Where                                       |
| ---------------------------------------------------------- | ------------------------------------------- |
| Three CI gates green at the tag SHA                        | `release.yml`, step `Verify CI gate ...`    |
| Tag literal matches `VERSION` file                         | `release.yml`, step `Verify VERSION matches`|
| `docs/release_notes/${TAG}.md` exists                      | `release.yml`, step `Verify release-notes`  |
| `VERSION` matches semver                                   | `tests/test_release_integrity.py`           |
| `CHANGELOG.md` carries a section for the current version   | `tests/test_release_integrity.py`           |
| `release.yml` references `VERSION` correctly               | `tests/test_release_integrity.py`           |
| All three CI gate markers resolve to a positive test count | `tests/test_release_integrity.py`           |

### Release artifacts

For v0.1.0 the release attaches a tarball
(`clarityos-runtime-v0.1.0.tar.gz`) containing the runtime spine,
tests, docs, and CI workflow files. PASS-7 will swap the tarball for
a real container image pushed to a registry; the release workflow
shape stays the same.

---

## Repository hygiene

PASS-6 Phase F locks the repo's upload shape. Three layers gate the
hygiene contract:

1. **`.gitignore`** — keeps build artifacts, caches, secrets, and
   editor scratch out of the tracked tree.
2. **`scripts/check_repo_clean.py`** — strict pre-upload gate.
   Walks the filesystem, asserts no stray files, no secret files,
   no missing scaffolding. Exit code 0/1, usable in a pre-commit
   hook or release pipeline.
3. **`scripts/verify_dependencies.py`** — walks every runtime + test
   import and asserts each external dep is declared in
   `requirements.txt` (production) or `requirements-dev.txt`
   (dev/tests). Also flags declared deps that nothing imports.
4. **`tests/test_repo_hygiene.py`** — pytest assertions tagged
   `runtime_spine`. Gates: no stray files (9 globs parametrized),
   required scaffolding present (27 files), dependency-freeze
   compliance (exact pins, no dev-only leaks), no `__init__.py`
   drift in `tests/` or `scripts/`, helper-script shebangs +
   parseability.

### Repo layout

```
.
├── VERSION                       # release version (vX.Y.Z)
├── CHANGELOG.md                  # PASS-1..PASS-6 history + v0.1.0 entry
├── README.md                     # this file
├── .gitignore                    # PASS-6 Phase F — ignore list
├── .env.example                  # CLARITYOS_* env template
├── pytest.ini                    # CI gate markers + load_envelope marker
├── requirements.txt              # production deps (exact pins)
├── requirements-dev.txt          # test deps (-r runtime + pytest/httpx)
│
├── app.py                        # BD1 — HTTP routes
├── intelligence_kernel.py        # BD2 — kernel + ESO + model funnel
├── model_router.py               # BD3 — provider selection + HTTP
├── operator_state.py             # BD4 — per-user state
├── memory_vault.py               # BD5 — encrypted KV
├── runtime_privacy.py            # cross-cutting redaction helpers
├── runtime_http_config.py        # call/health timeout config
├── kernel_logging.py             # audit-stream emitter
│
├── ELINS/                        # ELINS sub-pipeline (used by BD2)
├── billing_intents.py            # Stripe PaymentIntent helpers
├── billing_config.py             # Stripe mode resolution + event ring
├── users_store.py                # users table (mock + Firestore)
├── sessions_store.py             # sessions table (mock + Firestore)
├── ... (other adjacent runtime files)
│
├── .github/workflows/
│   ├── ci.yml                    # PR gate — three CI suites
│   ├── deploy.yml                # tag scaffold — gate then deploy
│   └── release.yml               # tag → GitHub Release + artifact
│
├── docs/
│   ├── runtime_architecture.md
│   ├── invariants.md
│   ├── boundaries.md
│   ├── deployment.md
│   ├── performance.md            # PASS-7 envelope notes
│   └── release_notes/
│       └── v0.1.0.md
│
├── scripts/
│   ├── run_ci_gates.sh           # local CI gate driver
│   ├── cut_release.sh            # local release-cutting helper
│   ├── run_load_probe.py         # PASS-7 load probe (real-HTTP)
│   ├── check_repo_clean.py       # PASS-6 Phase F pre-upload gate
│   └── verify_dependencies.py    # PASS-6 Phase F deps gate
│
└── tests/
    ├── conftest.py
    ├── test_runtime_inv_*.py     # PASS-6 Phase A invariant tests
    ├── test_*_runtime.py         # PASS-5 Phase D + Phase B
    ├── test_module_load_guards.py
    ├── test_deployment_runtime.py
    ├── test_release_integrity.py
    ├── test_repo_hygiene.py
    ├── test_load_envelope.py     # PASS-7 (opt-in marker)
    └── test_fix_*.py             # PASS-4 fix regression tests
```

### How to run tests

```bash
# Full test suite (everything in tests/, including non-CI tests).
pytest tests/

# CI gate union — the same selection ci.yml runs on every PR.
pytest -m "runtime_spine or privacy_surface or determinism_surface"

# Individual gates:
pytest -m runtime_spine
pytest -m privacy_surface
pytest -m determinism_surface

# PASS-7 load + stress envelope (opt-in, not in default gate):
pytest -m load_envelope

# Via the helper script:
bash scripts/run_ci_gates.sh           # all three CI gates
bash scripts/run_ci_gates.sh spine     # spine only
bash scripts/run_ci_gates.sh privacy
bash scripts/run_ci_gates.sh determinism
```

### How to run CI gates locally

The `scripts/run_ci_gates.sh` driver sets the same test-only env
defaults the GitHub Actions workflow uses (vault throwaway secret,
mock billing mode, log level WARNING) and runs the marker selection.
Mirrors `.github/workflows/ci.yml` exactly so a failure locally
predicts the CI result.

### How to cut releases

See [Cutting a release](#cutting-a-release) above for the full
four-step procedure (update VERSION, update CHANGELOG, run integrity
tests + CI gate, tag + push). The `scripts/cut_release.sh` helper
automates the validation; the tag push triggers
`.github/workflows/release.yml`.

### How to run the load probe

Boot the runtime locally (`uvicorn app:app --host 0.0.0.0 --port 8080`),
then drive the probe in another shell:

```bash
python scripts/run_load_probe.py
python scripts/run_load_probe.py --concurrency 25 --flows 100
python scripts/run_load_probe.py --base-url http://localhost:8080 \
    --timeout 30 --concurrency 50
```

See [`docs/performance.md`](docs/performance.md) for the output
shape, the recommended observed-envelope table, and the
interpretation guide.

### How to prepare for upload

Before pushing the repo (or before tagging a release):

```bash
# 1. Run the upload-readiness gates.
python scripts/check_repo_clean.py
python scripts/verify_dependencies.py

# 2. Run the CI gate locally to mirror what main-branch protection
#    will require.
bash scripts/run_ci_gates.sh

# 3. If anything fails, fix it. Common issues:
#    * sa.json (or other secret file) accidentally left in the tree
#      → delete it, then re-run check_repo_clean.py
#    * a dev dependency leaked into requirements.txt
#      → move it to requirements-dev.txt
#    * an import not declared in either requirements file
#      → add it to the appropriate file
#
# 4. Once both pre-upload scripts exit 0 AND the CI gate is green,
#    the repo is upload-ready. Initialize the git remote (if needed)
#    and push:
#       git init
#       git add .
#       git commit -m "ClarityOS Runtime v0.1.0"
#       git remote add origin git@github.com:<org>/<repo>.git
#       git push -u origin main
#
# 5. To cut the v0.1.0 release after the push:
#       bash scripts/cut_release.sh v0.1.0
#       git tag v0.1.0
#       git push origin v0.1.0
```

The post-push `.github/workflows/ci.yml` will run on the initial
push; configure branch protection on `main` to require all three CI
suites + the runtime-gate union as required checks before any
subsequent merge.

---

## PASS history (for archaeologists)

| Pass | Theme                          | Outcome                                                                       |
| ---- | ------------------------------ | ----------------------------------------------------------------------------- |
| 1–3  | Feature buildout               | v44 router, v46 vault, v40 kernel, v39 operator_state, etc.                   |
| 4    | Privacy + concurrency hardening | V2, B2, H6, H7, P1, P2, P3, P5 fixes — every one locked by an existing test.  |
| 5    | Stabilization                  | Phase D concurrency + multi-instance; PASS-5 → PASS-6 transition plan.        |
| 6    | Operationalization             | Phase A invariant tests, Phase B deployment-mode validation, Phase C CI+docs. |

Detailed fix → test → invariant mapping lives in
[`docs/invariants.md`](docs/invariants.md).
