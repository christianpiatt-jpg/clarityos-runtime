# ClarityOS Runtime — Performance & Resilience Envelope

> PASS-7 reference. **Informational only — not gating.** This page
> documents the v0.1.0 runtime's behaviour under synthetic load and
> records observed envelope numbers. It does NOT establish a SLA.
>
> The CI gate (`runtime_spine` + `privacy_surface` +
> `determinism_surface`) gates correctness. PASS-7 sits next to it as
> an opt-in performance characterisation.

---

## What PASS-7 covers

PASS-7 is a small, runtime-code-free addition that adds two surfaces:

1. **`tests/test_load_envelope.py`** — a pytest suite tagged
   `@pytest.mark.load_envelope`. Three classes:

   * `TestL1SyntheticHttpLoad` — 50 concurrent flows of
     `login → /me → /elins/preview → /me` against the in-process
     FastAPI test client; asserts no 5xx, no invariant violations,
     no deadlocks within a 30-second per-flow timeout. A second
     test covers a mixed workload (half full-vertical, half
     `/me`-hammer).
   * `TestL2MacroConcurrency` — 50 concurrent macro invocations
     across distinct system_user labels; verifies run-id
     uniqueness, macro-seq monotonicity, and no cross-user
     contamination in either `operator_state` history (50 users ×
     10 writes each) or the vault (50 users × same key namespace).
   * `TestL3TimeoutUnderLoad` — 50-thread ContextVar timeout
     isolation; outlier-vs-siblings leakage check; slow-provider
     error redaction; default-restored post-burst.

2. **`scripts/run_load_probe.py`** — a stdlib-only standalone driver
   that fires real HTTP requests against a running dev server and
   prints latency + error metrics. Useful for ad-hoc smoke
   characterisation of a local deploy.

What PASS-7 deliberately does **not** do:

* Does not modify any runtime code. The CI gate's "zero runtime
  changes in stabilisation phases" rule continues to hold.
* Does not enforce performance thresholds. The L1–L3 tests assert
  correctness contracts (no 5xx, redaction holds, invariants hold)
  under load — they do not assert "p95 must be under X ms" because
  CI runner hardware varies too much for that to be load-bearing.
* Does not run in the default CI gate. The marker `load_envelope`
  is opt-in: `pytest -m load_envelope`.

---

## Running the load tests

```bash
# All PASS-7 envelope tests:
pytest -m load_envelope -q

# Individual classes:
pytest tests/test_load_envelope.py::TestL1SyntheticHttpLoad -q
pytest tests/test_load_envelope.py::TestL2MacroConcurrency -q
pytest tests/test_load_envelope.py::TestL3TimeoutUnderLoad -q

# With per-flow latency print (the L1 test prints a one-line
# envelope summary at end-of-test even without -s):
pytest tests/test_load_envelope.py::TestL1SyntheticHttpLoad::test_l1_fifty_concurrent_flows -q
```

The default CI gate (`runtime_spine or privacy_surface or determinism_surface`)
deliberately excludes `load_envelope`. Run it manually as part of a
PR's "extra coverage" pass or before cutting a release if you want a
load snapshot to attach to the release notes.

### Reading the L1 print-out

`test_l1_fifty_concurrent_flows` emits a single line like:

```
L1 envelope (N=50): burst 8.42s, p50 168ms, p95 312ms
```

These numbers are per-test-runner. Treat them as a relative
benchmark across runs on the same host, not an absolute SLA.

---

## Running the load probe against a dev instance

The standalone probe in `scripts/run_load_probe.py` is the right tool
for two cases:

1. Characterising the runtime against a non-test deployment shape
   (real ASGI server, not the in-process TestClient).
2. Smoke-checking a freshly-deployed dev instance before opening it
   up to traffic.

### Quick start

```bash
# 1. Boot the runtime locally (in a separate shell).
#    A dev env file is enough — see .env.example for the minimal
#    set; CLARITYOS_VAULT_SECRET is the only required value.
cp .env.example .env
$EDITOR .env   # set CLARITYOS_VAULT_SECRET to any non-empty value

python -m pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080

# 2. From another shell, drive the probe.
python scripts/run_load_probe.py

# Custom config:
python scripts/run_load_probe.py --concurrency 25 --flows 100
python scripts/run_load_probe.py --base-url http://localhost:8080 \
    --timeout 30 --concurrency 50 --flows 200

# Quiet mode (suppress per-flow lines; just print the summary):
python scripts/run_load_probe.py --concurrency 25 --flows 100 --quiet
```

### Probe output

The probe prints a structured summary at end-of-run. Example shape:

```
========================================================================
 ClarityOS load probe — summary
========================================================================
 target            : http://localhost:8080
 concurrency       : 20
 total flows       : 50
 per-call timeout  : 30.0s
 burst wall-clock  : 8.42s
------------------------------------------------------------------------
 ok                : 50/50  (100.0%)
 failed            : 0
------------------------------------------------------------------------
 latency (all flows, end-to-end)
   p50             : 168 ms
   p95             : 312 ms
   p99             : 348 ms
 latency (ok flows only)
   p50             : 168 ms
   p95             : 312 ms
------------------------------------------------------------------------
 per-step p95 (ok flows)
   register        : 18 ms
   login           : 30 ms
   me_1            : 22 ms
   preview         : 175 ms
   me_2            : 24 ms
------------------------------------------------------------------------
 HTTP status histogram (across every request issued)
   200             : 250
========================================================================
```

Exit code is 0 when every flow succeeded, 1 otherwise — so the script
is usable as a smoke-check step in a deploy pipeline.

### Probe contract — what it does, what it doesn't

The probe is a real client. It:

* Registers an ephemeral user per flow (unique username, throwaway
  password). The dev runtime accumulates these in `users_store` —
  fine on a dev box, do **not** run against production.
* Logs in, hits `/me`, drives one ELINS preview, hits `/me` again.
* Uses stdlib `urllib.request` for HTTP — no external Python deps
  required beyond what the runtime already needs.

The probe does NOT:

* Touch `/billing/*` endpoints. Billing has its own tests
  (`test_v31_billing.py`, `test_v42_billing_hardening.py`,
  `test_fix_p1_billing_surface_hardening.py`) and a load probe
  against Stripe would be irresponsible.
* Use real provider keys. The dev server's BD3 router falls back
  to the deterministic mock (the v44 contract) when no provider
  env keys are set.
* Drive concurrent macro runs. That's covered by
  `test_l2_macro_runs_unique_across_concurrent_users` against the
  in-process kernel.

---

## Observed envelope table

This table is a **template**, not a SLA. Record observed values on
your hardware to track relative trends. Each row is one PASS-7 run on
a documented machine; numbers are wall-clock from the L1 test print
+ the load-probe summary.

| Date       | Hardware                          | Suite            | N flows | Concurrency | p50 (ms) | p95 (ms) | p99 (ms) | Errors | Notes                            |
| ---------- | --------------------------------- | ---------------- | ------- | ----------- | -------- | -------- | -------- | ------ | -------------------------------- |
| _baseline_ | _local dev box (your machine)_    | L1 test          | 50      | 50          | _record_ | _record_ | n/a      | 0      | first PASS-7 baseline            |
| _baseline_ | _local dev box (your machine)_    | scripts probe    | 50      | 20          | _record_ | _record_ | _record_ | 0      | dev instance, mock providers     |
|            |                                   |                  |         |             |          |          |          |        |                                  |
|            |                                   |                  |         |             |          |          |          |        |                                  |

Suggested cadence: record one row per release tag, one row per
infrastructure change (Python version bump, dependency major-version
bump, backend swap memory ↔ Firestore).

---

## Interpretation guide

The load envelope is correctness-focused. A run is **green** when:

* Every flow returns 2xx (no 5xx surfaces under contention).
* `last_model_used` populates on every user's second `/me` (proves
  the kernel completed cleanly).
* No raw `user_id` / `session_id` appears in any FIX-P5 logger
  during the burst.
* No duplicate macro `run_id`s, no broken format, no cross-user
  contamination.
* `_PROVIDER_HTTP_TIMEOUT_VAR` isolation holds — outlier overrides
  do not leak into sibling threads.

A run is **yellow** (informational) when:

* Latency p95 jumps significantly from the baseline row above on
  the same hardware. PASS-7 does not block on this; it just
  surfaces the regression.
* The mock-provider fallback fires unexpectedly during the slow-
  provider error test. Expected behaviour, but the count matters
  for the redaction-under-load assertion.

A run is **red** (test failure) when:

* Any of the L1–L3 correctness assertions fails.

When L1–L3 stay green but latency drifts, the next step is to
update the baseline row, attach the new numbers to the release notes,
and move on.

---

## How PASS-7 relates to the rest

| Pass    | Theme                          | Locked by                                                                       |
| ------- | ------------------------------ | ------------------------------------------------------------------------------- |
| PASS-4  | Hardening fixes                | `tests/test_fix_*.py`                                                           |
| PASS-5  | Stabilization + concurrency    | `tests/test_*_runtime.py`                                                       |
| PASS-6  | CI gates + invariants + docs   | `tests/test_runtime_inv_*.py` + `pytest.ini` markers + `.github/workflows/*.yml` |
| PASS-7  | Optional load + stress envelope | `tests/test_load_envelope.py` + `scripts/run_load_probe.py` + this doc          |

PASS-7 explicitly does NOT establish a new gate. The runtime is
release-ready (v0.1.0) without PASS-7 running green; PASS-7 is the
characterisation layer that informs operator decisions about
deployment shape (instance count, max-concurrency, request timeout
budgets) without rewriting any contract the CI gate already enforces.
