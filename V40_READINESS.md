# V40 Readiness — Intelligence Kernel v1.0

Status: ✅ Ready
Backend version: `3.6`
Kernel version: `kernel.v1.0`
Build: `20260507200000`

---

## What v40 ships

A single coherent kernel that unifies #c, #G, ELINS, ESO, scheduler,
and operator state. Endpoints in `app.py` and the macro scheduler now
route through `intelligence_kernel.*`; ESO resolution, operator_state
recording, S_ELINS QC, and ELINS persistence happen in one module.
Endpoint contracts are unchanged — only internal wiring shifted.

The kernel exposes a status snapshot at
`/founder/intelligence/kernel/status` and a per-user view block on
`/me` so clients can see the effective ESO mode + inferred preferences
in one round-trip.

---

## Files added / changed

### New
- `intelligence_kernel.py` — `run_c`, `run_G`, `run_ELINS`,
  `run_regional_ELINS`, `run_macro_ELINS`,
  `_resolve_external_signal_mode`, `_maybe_fetch_eso`,
  `_apply_signal_mode_override`, `_run_s_elins_qc`,
  `kernel_status`, `kernel_view_for_user`, `_reset_for_tests`.
- `tests/test_v40_intelligence_kernel.py` — 41 tests.
- `V40_READINESS.md` (this file).

### Modified
- `app.py`:
  - Imports `intelligence_kernel`.
  - `/c/run` routes via `kernel.run_c` (preserves `domain_hint`
    fast-path that bypasses the kernel since it isn't on the public
    surface yet).
  - `/elins/g/run` wraps `_run_g_elins` with `kernel.run_G`; the inline
    operator_state recording was removed.
  - `/elins/preview` calls `kernel.run_ELINS(persist=False, kind="preview")`.
  - `/elins/global` calls `kernel.run_ELINS(persist=True, kind="global")`.
  - `/elins/regional/run` calls `kernel.run_regional_ELINS`.
  - New `GET /founder/intelligence/kernel/status` (founder).
  - `/me` now returns an `intelligence_kernel` block + a new
    `intelligence_kernel` capability id.
  - Backend version `3.6`; root listing extended.
- `elins_scheduler.py` — `_run_macro_elins_once` is now a thin cadence
  gate that delegates to `intelligence_kernel.run_macro_ELINS`. The
  full pass body lives in the kernel.
- `tests/conftest.py` — reset hook calls
  `intelligence_kernel._reset_for_tests`.
- `tests/test_v28_endpoints.py` — health version `3.6`.
- `BUILD_VERSION` — `20260507200000`.

### Deliberately unchanged
- `comment_generator.py`, `perplexity_oracle.py`,
  `ELINS/standard_elins.py`, `ELINS/regional_elins.py`,
  `ELINS/elins_project.py`, `operator_state.py`,
  `elins_entity_graph.py`, `elins_dashboard.py`. v40 is a wiring +
  centralisation pass, not a behaviour rewrite.

---

## Public API

```python
KERNEL_VERSION = "kernel.v1.0"

run_c(user, input, *, mode="default", external_signal_mode=None) -> dict
run_G(user, input, *, runner, mode="default", external_signal_mode=None) -> dict
run_ELINS(user, text, *,
          region=None, external_signal_mode=None,
          domain_hint=None, kind=None, topic_hint=None,
          persist=True, update_indexes=True) -> dict
run_regional_ELINS(user, region_code, *,
                   topic_hint=None,
                   external_signal_mode=None,
                   persist=True) -> dict
run_macro_ELINS(system_user, *,
                now_ts=None, external_signal_mode=None) -> dict

kernel_status() -> dict
kernel_view_for_user(user_id) -> dict
```

### Centralised helpers

- `_resolve_external_signal_mode(user, override)` — precedence:
  explicit override → `users_store.get_user(user).external_signal_mode`
  → `operator_state.get_operator_state(user).external_signal_mode` →
  `"cloud_only"`.
- `_maybe_fetch_eso(mode, *, region_code=None, user=None)` — delegates
  to `perplexity_oracle.fetch_basin_signals` only when mode is
  `cloud_perplexity`; returns `None` for `cloud_only` or unknown
  region.
- `_apply_signal_mode_override(user, override)` — mirrors a per-call
  override onto operator_state + users_store so the regional ESO
  resolver picks it up immediately.
- `_run_s_elins_qc(elins_obj)` — runs S_ELINS, attaches result to
  `elins_obj["qc"]`; logs + returns None on failure (caller continues
  with persistence).

---

## API surface

### `GET /founder/intelligence/kernel/status` (founder)
Returns:
```jsonc
{
  "ok": true,
  "kernel": {
    "version":           "kernel.v1.0",
    "eso_default_mode":  "cloud_only",
    "scheduler_enabled": false,
    "macro_cadence":     "3x_week",
    "last_macro_run_ts": null,
    "valid_signal_modes": ["cloud_only", "cloud_perplexity"],
    "regions": ["US","EU","MEA","APAC","Markets","Tech"]
  }
}
```

### `/me` — `intelligence_kernel` block
```jsonc
"intelligence_kernel": {
  "version":              "kernel.v1.0",
  "external_signal_mode": "cloud_only",
  "preferred_domains":    {},
  "preferred_regions":    {}
}
```

### Endpoint contracts preserved
- `/c/run` — same body / same return shape.
- `/elins/g/run` — same body / same return shape; operator_state side
  effect now lives in `kernel.run_G` instead of inline.
- `/elins/preview` — same body. Response now includes
  `elins.qc` (the S_ELINS QC dict) — purely additive.
- `/elins/global` — same body / same return shape.
- `/elins/regional/run` — same body / same return shape.

---

## Centralised behaviour

| Concern | Pre-v40 | Post-v40 |
| --- | --- | --- |
| ESO resolution | `app._resolve_eso_for` + `elins_scheduler._resolve_eso` | `intelligence_kernel._resolve_external_signal_mode` + `_maybe_fetch_eso` |
| Operator state ELINS recording | inline in 3 endpoints | inside `run_ELINS` / `run_regional_ELINS` |
| Operator state #G recording | inline in `/elins/g/run` | inside `run_G` |
| ESO mode override mirror | inline in `/me/operator_state` | inside `_apply_signal_mode_override` (kernel) |
| S_ELINS QC | only on `/elins/qc` | always attached to `elins_obj["qc"]` for kernel runs |
| Macro pass orchestration | `elins_scheduler._run_macro_elins_once` | `intelligence_kernel.run_macro_ELINS` (scheduler is now a cadence gate) |

---

## Tests

```
tests/test_v40_intelligence_kernel.py — 41 tests, all pass
Full suite — 427 passed, 0 failed
```

Coverage:
- `run_c` — comment dispatch, unknown-mode rejection, signal-mode
  override mirror, determinism.
- `run_G` — runner success records `g_history`; failure leaves it
  empty; signal-mode override mirrored onto users_store; raw text
  never stored.
- `run_ELINS` — S_ELINS attached + persistence on; persist=False
  makes daily-run a no-op; operator_state recorded; raw text never
  stored; region delegates to regional path; determinism.
- `run_regional_ELINS` — QC attached; default `eso_present=False`;
  user opt-in via users_store turns ESO on; explicit override beats
  user preference; region preference recorded; unknown region raises.
- `run_macro_ELINS` — full pass writes macro record + entity graph;
  ESO mode is honoured (every region has external_signals.present);
  consecutive passes have unique run ids.
- Scheduler delegation — `_run_macro_elins_once(force=True)` returns
  the kernel summary verbatim.
- Endpoint contracts — `/c/run`, `/elins/preview`, `/elins/global`,
  `/elins/regional/run`, `/elins/g/run` shapes preserved.
- `/founder/intelligence/kernel/status` — shape + after-macro-run
  reflects `last_macro_run_ts` + founder gate.
- `/me` — `intelligence_kernel` block present + reflects user
  preferences + `intelligence_kernel` capability advertised.
- ESO helpers — explicit override wins; user-doc fallback;
  default `cloud_only`; `_maybe_fetch_eso` only fetches for
  `cloud_perplexity` and returns None on unknown region.

---

## Notes / follow-ups

- The kernel is intentionally framework-light: a leaf module with no
  dependency on `app.py`. The #G runner is injected from the endpoint
  to keep imports acyclic.
- `/c/run` currently bypasses the kernel when `domain_hint` is
  supplied (the kernel `run_c` surface does not yet thread through
  `domain_hint`). The same operator_state mirroring still happens via
  the explicit signal-mode parameter when callers want it. A future
  pass can lift `domain_hint` into the kernel surface.
- `_resolve_external_signal_mode` checks users_store first to keep the
  v35 ESO resolver path matching exactly. When users_store and
  operator_state diverge, users_store wins. The
  `/me/operator_state` POST writes both, so they should not diverge in
  practice.
- Pre-v40 surfaces (v28–v39) are unchanged; only internal wiring
  shifted. The `/me` `intelligence_kernel` block + the
  `elins.qc` field on `/elins/preview` are additive.
