# Schedulers

## Purpose

ClarityOS runs several independent schedulers — there is **no** single unified
scheduler. Each is a self-contained cadence engine that periodically runs one
family of background work. This document covers the three infrastructure
schedulers: the macro-ELINS scheduler, the personal-intelligence cadence
orchestrator, and the membership-renewal scheduler.

## Implementation location

Repo-root modules:

- `elins_scheduler.py` (v36) — the macro-ELINS scheduler. Its cadence
  configuration lives in `elins_scheduler_config.py`.
- `intelligence_scheduler.py` (Phase 2, Unit 4) — the personal-intelligence
  cadence orchestrator.
- `billing_renewal.py` (v31) — the membership-renewal scheduler. Only its
  scheduling mechanics are covered here; its billing-state behaviour is
  documented in `docs/billing.md`.

## Data model

- **elins_scheduler** — module-level singleton state: a `_scheduler_started`
  flag, one daemon `threading.Thread`, a `_stop_event`, and a
  strictly-monotonic `_run_id_counter`. `SCHEDULER_TICK_SECONDS` defaults to
  300 s (overridable via `CLARITYOS_MACRO_TICK_SECONDS`). Cadence config
  (`elins_scheduler_config`): `enabled` (bool), `cadence`
  (`off` / `daily` / `3x_week` / `weekly`), `external_signal_mode`
  (`cloud_only` / `cloud_perplexity`), `system_user`, `last_run_ts`.
- **intelligence_scheduler** — no in-memory singleton. State is a JSON file at
  `CLARITYOS_SCHEDULER_STATE` (default `.clarityos_scheduler_state.json`)
  holding `{users: {user_id: {last_daily_elins, last_news_basin,
  last_email_scheduled_tick, next_news_basin}}}`, written atomically
  (tempfile + `os.replace`).
- **billing_renewal** — a `_scheduler_started` flag guarding one daemon
  thread. `RENEWAL_TICK_SECONDS` defaults to 24 h (overridable via
  `CLARITYOS_RENEWAL_TICK_SECONDS`). The per-user renewal fields it scans live
  on the user record — see `docs/billing.md`.

## APIs / entrypoints

- **elins_scheduler** — `start_elins_scheduler()` / `stop_elins_scheduler()`
  (both idempotent), `is_running()`, and `_run_macro_elins_once(now_ts=None,
  *, force=True)`, which runs one macro pass (`force` bypasses the cadence
  gate; used by tests and `/founder/elins/macro/run_now`). The background loop
  calls `_run_macro_elins_once(force=False)` each tick. Config is read and
  written through `elins_scheduler_config.get_config()` / `set_config()`.
- **intelligence_scheduler** — `tick(now=None)` (aliased `run_scheduled_tasks`)
  evaluates every registered user's cadence and runs the due tasks;
  `register_user` / `unregister_user` / `get_state` manage tracking; the
  single-task runners are `run_daily_personal_elins_once`,
  `run_news_basin_once`, and `run_email_ep_dash_once`. `python -m
  intelligence_scheduler` runs one tick from the CLI.
- **billing_renewal** — `_ensure_renewal_scheduler_started()` lazily boots the
  daemon (idempotent; there is no stop entrypoint — the daemon runs for the
  process lifetime). `renew_membership(user_id, *, now_ts=None)` drives one
  user; `_renewal_one_pass(now_ts=None)` scans and drives every due user once,
  returning `{due, intents, terminated, no_op}` counts.

## Integration points

- **elins_scheduler** → `intelligence_kernel.run_macro_ELINS` — the scheduler
  delegates the entire macro pass to the kernel, passing through the
  `external_signal_mode` from its config; the kernel performs any ESO fetch.
  Cadence is read from `elins_scheduler_config`.
- **intelligence_scheduler** → `daily_personal_elins`, `personal_news_basin`,
  and `email_ep_dash` — the three producers it coordinates. It emits no
  intelligence itself.
- **billing_renewal** → `billing_intents`, `membership_store`, `users_store`,
  and `v29_hardening` (structured logging). The renewal lifecycle it drives is
  documented in `docs/billing.md`.
- **Drivers** — `elins_scheduler` and `billing_renewal` run their own daemon
  threads; `intelligence_scheduler` owns no thread and is driven by an
  external cron / job runner calling `tick()` on a timer.

## Invariants

- **Idempotency** — re-ticking inside a cadence window is a no-op for all
  three. `start_elins_scheduler` / `stop_elins_scheduler` and
  `_ensure_renewal_scheduler_started` are idempotent; `renew_membership`
  returns a `no_op` action for a user that is not due.
- **Determinism** — `intelligence_scheduler` is fully deterministic: the same
  `now` plus the same starting state yields the same envelopes and the same
  final state. `elins_scheduler`'s cadence gate is deterministic given the
  config and `last_run_ts`.
- **A failed tick does not kill the scheduler** — each daemon loop catches and
  logs exceptions and keeps running. `intelligence_scheduler` additionally
  advances per-user cadence markers even when a producer fails, so a
  persistently broken producer is not retried every tick.
- **One daemon per process** — `elins_scheduler` and `billing_renewal` each
  start at most one thread per process.
- **Monotonic run ids** — `elins_scheduler._make_run_id` uses a locked counter
  so two passes in the same millisecond still receive distinct ids.
- **Atomic state** — `intelligence_scheduler` writes its JSON state via
  tempfile + `os.replace`; whole-file corruption resets to empty state, and a
  malformed per-user entry resets only that user.

## Billing renewal scheduler

The renewal scheduler (`billing_renewal`) is a lightweight daemon thread that
performs due detection, renewal-intent creation, and grace-expiry termination.
All retry/backoff logic lives in `billing_intents`.

**Boot and lifecycle**

- Scheduler is lazily started by the `/membership/activate` route.
- Founder-only activations do not start the scheduler.
- At most one scheduler thread runs per process (`_scheduler_started` guard).
- Daemon thread: exits with the process; no stop/join API.

**Tick loop**

Each tick runs `_renewal_one_pass()` then `time.sleep(RENEWAL_TICK_SECONDS)`.

- Exceptions inside a pass are logged and the next tick continues.
- Idle passes (no intents, no terminations) produce no logs.

**Due detection**

- Uses `users_store.list_users_due_for_renewal()` as the sole source of truth.
- `renew_membership` re-validates state defensively to handle between-read
  drift.

**Termination path**

`_terminate_membership` performs four independent writes:

1. `users_store.set_membership(..., status="cancelled")`
2. `users_store.set_billing_state(..., billing_state="cancelled")`
3. `membership_store.remove_member(user)`
4. `membership_store.record_transaction("membership_cancel",
   metadata={"automated": True})`

No cross-document transaction is used. Partial-failure states are possible.
This inherits the best-effort multi-store semantics documented in
[docs/billing_intents.md](billing_intents.md).

**Integration**

- Renewal policy constants and the retry/grace state machine live in
  `billing_intents`.
- Scheduler only triggers when to attempt renewal or terminate; it does not
  implement policy.

## Non-goals

- There is no shared scheduler framework, no central task queue, and no
  cross-scheduler coordination — the three modules are independent.
- Schedulers emit no intelligence of their own; they decide *when* to invoke
  producers and persist cadence state, nothing more.
- No scheduler hosts UI; founder controls (such as
  `/founder/elins/scheduler/config`) live in the HTTP layer.
- `elins_scheduler` runs only the unattended global + regional macro pass; it
  does not run the per-user personal cadences — that is
  `intelligence_scheduler`.

## Fiction removed

Earlier layout drafts proposed dead-letter queues, event-driven scheduler
pipelines, backoff strategies, priority queues, and a single unified "core
scheduler loop." None of these exist. The schedulers are interval- and
cron-tick based, not event-driven: `elins_scheduler` and `billing_renewal`
wake on a fixed timer, and `intelligence_scheduler` has no loop at all — an
external caller invokes `tick()`. There is no task queue and no dead-letter
queue — a failed tick is caught, logged, and the loop simply continues. Those
drafts also implied scheduler-owned "log rotation", "cache invalidation", and
"entitlement refresh" jobs; no such schedules are registered.
