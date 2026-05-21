# Founder Analytics

## Purpose

`founder_analytics` is a pure read-side aggregator that joins four
upstream stores — `users_store`, `operator_state`, `billing_config`,
and `ELINS.elins_project` — into a single metadata-only summary for
the founder console. It performs no reasoning, no persistence, no
mutation, and no model invocation. The module exists to provide a
stable, low-latency snapshot of platform-wide activity in a single
HTTP round-trip.

## Implementation location

- **File:** `founder_analytics.py` (single file, ~136 lines).
- **Version:** `SUMMARY_VERSION = "founder_analytics.v43.1"`.
- **Public exports:**
  - `get_founder_analytics_summary(now_ts=None) -> dict`
  - `SUMMARY_VERSION`
- **Private constants:** `_DAY_S`, `_WEEK_S`, `_MONTH_S` (window math).
- **No classes, no private helpers, no module state, no caching.**
- **Imports:**
  - stdlib: `logging`, `time`, `typing.Optional`
  - `billing_config`, `operator_state`, `users_store`,
    `ELINS.elins_project`

That is the complete dependency surface.

## Data model

`get_founder_analytics_summary(now_ts=None)` returns a JSON-safe
dict:

```python
{
    "users": {
        "total":      int,
        "active_7d":  int,
        "active_30d": int,
    },
    "billing": {
        "active_subscriptions": int,
        "past_due":             int,
        "canceled":             int,
        "mode":                 str,
    },
    "intelligence": {
        "elins_runs_7d":     int,
        "g_runs_7d":         int,
        "macro_runs_7d":     int,
        "eso_usage_rate_7d": float,    # rounded to 4 decimals
    },
    "ts":      float,    # now_ts or time.time()
    "version": str,      # SUMMARY_VERSION
}
```

### Field semantics

**Users:**

- `total` — number of usernames in `users_store`
- `active_7d` / `active_30d` — users with `last_active_ts` within
  the rolling window

**Billing:**

- `active_subscriptions` — `billing_state == "active"`
- `past_due` — `billing_state in {"past_due", "grace_period"}`
- `canceled` — `billing_state == "cancelled"` OR
  `membership_status == "cancelled"`
- `mode` — `billing_config.get_stripe_mode()`

**Intelligence:**

- `elins_runs_7d` — count of `operator_state.elins_history` entries
  with `ts >= cutoff_7d`
- `g_runs_7d` — count of `operator_state.g_history` entries with
  `ts >= cutoff_7d`
- `macro_runs_7d` — count of `elins_project.list_macro_runs(limit=200)`
  with `ts >= cutoff_7d`
- `eso_usage_rate_7d` — fraction of `macro_runs_7d` with
  `external_signal_mode == "cloud_perplexity"`; `0.0` when
  `macro_runs_7d == 0`

**Top-level:**

- `ts` — the cutoff anchor for the 7d / 30d windows
- `version` — module version string; always present

## APIs / entrypoints

### Public function

`get_founder_analytics_summary(now_ts: Optional[float] = None) -> dict`

- Resolves `now = now_ts or time.time()`, computes
  `cutoff_7d = now - 7*86400` and `cutoff_30d = now - 30*86400`.
- Walks all usernames returned by `users_store.list_all_usernames()`.
- For each user: reads `operator_state.get_operator_state(username)`
  and `users_store.get_user(username)` defensively.
- Reads `elins_project.list_macro_runs(limit=200)` and
  `billing_config.get_stripe_mode()`.
- Returns the metadata summary dict.

### HTTP route

`GET /founder/analytics/summary` — handler
`founder_analytics_summary` in `app.py`; founder-gated via
`_require_founder`. Returns `{"ok": True, "summary": <dict>}`.

## Integration points

### Upstream stores (read-only, 4)

- **`users_store`** — `list_all_usernames()` + `get_user(username)`
- **`operator_state`** — `get_operator_state(username)`
- **`billing_config`** — `get_stripe_mode()`
- **`ELINS.elins_project`** — `list_macro_runs(limit=200)`

### Importers (1)

- `app.py` — the founder console route handler.

### Kernel

**None.** `intelligence_kernel.py` does not import this module.

### Tests

- **`tests/test_v43_ux_and_analytics.py`** — 16 tests total, ~12
  directly exercising `founder_analytics`:
  - `test_summary_*` (9) — window math, billing bucketing, ELINS / G
    / macro counts, `eso_usage_rate_7d` rounding and zero-division
    case, determinism, shape / version field
  - `test_endpoint_analytics_*` (3) — HTTP shape, founder gate,
    runtime-state reflection

## Invariants

1. **Pure read-only.** No writes to any store. No `.put()`,
   `.save()`, or `.update_*` calls anywhere in the module.
2. **Deterministic.** Same store state + same `now_ts` → byte-equal
   output.
3. **Defensive reads.** Every upstream call is wrapped in
   `try/except Exception`; failures degrade to `{}` or `[]` without
   breaking the summary shape.
4. **Metadata-only output.** Counts and one string (`billing.mode`).
   No usernames, no per-user details, no PII.
5. **No caching.** Every call walks the full user list fresh.
6. **No I/O.** No network, no file system, no provider calls;
   everything goes through upstream store APIs.
7. **No kernel coupling.** Does not import `intelligence_kernel`,
   `model_router`, or `memory_vault`.
8. **Stable shape.** All fields always present; `version` always
   emitted so the founder console can render-vs-skip on schema
   change.
9. **Zero-division safe.** `eso_usage_rate_7d = 0.0` when
   `macro_runs_7d == 0`.
10. **Rounding policy.** Only `eso_usage_rate_7d` is rounded
    (4 decimals); all other values are unrounded integers.

## Non-goals

`founder_analytics` is **not**:

- a model invocation surface — no provider dispatch, no LLM, no
  `model_router` import;
- an operator_state writer — strictly read-only;
- a vault consumer — does not import `memory_vault`;
- a background task — no scheduler, no async, no thread;
- a paginated endpoint — single round-trip, all-at-once aggregation;
- a per-user analytics surface — only aggregate counts;
- a cross-user correlation engine — iteration is uniform across all
  usernames;
- a caching layer — recomputed on every call.

## Fiction removed

Because this subsystem had no prior canonical doc, no drift existed
when this document was first written. The following constructs are
explicitly not present in `founder_analytics.py` and must not be
inferred:

- **No caching layer** — no `_CACHE`, no TTL, no invalidation.
- **No per-user output** — only aggregates; the iteration variable
  `username` is never surfaced.
- **No kernel coupling** — `intelligence_kernel` is never imported.
- **No streaming endpoint** — one synchronous call returns the
  complete summary.
- **No write surface** — cannot be used to mutate any upstream
  store.
- **No retry / backoff / circuit-breaker logic** — defensive
  `try/except Exception` is the only protection.
- **No alternate output formats** — JSON-safe dict only; no CSV,
  no Prometheus, no time-series.
- **No historical retention** — every call is "as of now"; there is
  no past-snapshot store.

Only the behaviour, fields, and integrations described in this
document are present in the code; the verified surface is pinned by
~12 tests in `tests/test_v43_ux_and_analytics.py`.
