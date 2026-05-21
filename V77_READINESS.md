# V77 — Regression-First vault persistence

Status: ✅ Ready
Backend version: `4.19` (bumped from `4.18`; bundled with V78)
Build: `20260514140000` (bumped from `20260514120000`)

> V77 + V78 ship as **one** implementation pass per founder call.
> See [V78_READINESS.md](V78_READINESS.md) for the timeline-emission
> half of the same pass.

---

## What this pass ships

### Scope

Move regression-chain storage from the in-process `_V76_OWNERS` side
index into `memory_vault`'s native per-user partitioning. No HTTP
contract change — every request/response shape stays identical to
V76. The kernel keeps its user-agnostic signature; per-user scoping
is injected at the endpoint boundary through a pluggable storage
adapter.

### Storage abstraction

New file `problem_solver/chain_store.py`. Three public symbols:

| Symbol                                | Role                                                                |
|---------------------------------------|---------------------------------------------------------------------|
| `RegressionChainStoreProtocol`        | Runtime-checkable Protocol: `get`, `save`, `delete`, `list_all`.    |
| `InMemoryRegressionChainStore`        | Default. Process-local dict with a strictly-monotonic insertion seq so same-ms `start_chain` calls sort deterministically newest-first. Used by kernel-only tests + standalone callers. |
| `VaultBackedRegressionChainStore(user_id)` | Per-user wrapper around `memory_vault`. Stores each chain under `regression_chains.{chain_id}`. List sorts by `(created_at, chain_id) DESC`. |
| `DEFAULT_STORE`                       | Module-level `InMemoryRegressionChainStore` instance. Used when kernel callers pass `store=None`. |
| `VAULT_NAMESPACE = "regression_chains"` | Canonical namespace constant. Registered in `memory_vault.ALLOWED_NAMESPACES`. |

### Kernel refactor

Every public kernel function gains an optional `store=` kwarg, typed
as `RegressionChainStoreProtocol`. When omitted, the kernel uses
`DEFAULT_STORE`.

```python
start_chain(title, *, notes=None, store=None) -> RegressionChain
record_finding(chain_id, layer_index, status, notes=None, *, store=None) -> RegressionChain
close_chain(chain_id, *, notes=None, store=None) -> RegressionChain
tag_chain(chain_id, tags, *, store=None) -> RegressionChain
get_chain(chain_id, *, store=None) -> RegressionChain
list_chains(*, store=None) -> list[RegressionChain]
analyze_packet(raw, *, title=None, build_chain=True, store=None) -> CognitivePacket | None
```

Endpoint handlers construct a fresh
`VaultBackedRegressionChainStore(session["user"])` per request and
pass it through. The kernel never sees `user_id` directly — that
stays an endpoint concern.

### `memory_vault.ALLOWED_NAMESPACES`

Added `"regression_chains"`. Each chain lives at key
`regression_chains.{chain_id}` (UUID4 with dashes) and the value is
the full `RegressionChain` dict from V76.

### `app.py` changes

* Removed `_V76_OWNERS` side index + `_v76_reset_owners_for_tests`.
* New helper `_v76_store_for(user)` constructs the per-request
  vault-backed store.
* Every V76 endpoint (`/start`, `/step`, `/get`, `/list`, `/close`,
  `/tag`) now passes `store=_v76_store_for(user)` through to the
  kernel.
* Cross-user 404 path now provided by the vault itself — there's
  literally no way for user B to construct a store for user A's
  partition (the underlying `memory_vault.vault_get` is per-user).

### Test posture (V77 share)

| Suite                                            | Tests | Status |
|--------------------------------------------------|-------|--------|
| `tests/test_regression_first_vault_timeline.py` (V77 share — `TestVaultPersistence`, `TestPerUserPartitioning`, `TestPersistenceAcrossCalls`, `TestVaultBackedStoreUnit`) | 19    | ✅     |
| `tests/test_problem_solver.py` (unchanged — kernel uses `DEFAULT_STORE`) | 84    | ✅     |
| `tests/test_regression_first_endpoints.py` (V76 endpoint tests — still green against the vault-backed store) | 27    | ✅     |

### Files touched

```
memory_vault.py                                            (+ "regression_chains" to ALLOWED_NAMESPACES)

problem_solver/chain_store.py                              (new)
problem_solver/regression_first.py                         (kernel takes optional store=; no more module-level _CHAINS)
problem_solver/__init__.py                                 (re-exports the store layer)

app.py                                                     (- _V76_OWNERS / _v76_reset_owners_for_tests / _v76_load_chain_owned
                                                            + _v76_store_for; all v76 handlers pass store=
                                                            /health 4.18 → 4.19)

tests/conftest.py                                          (- _v76_reset_owners_for_tests hook
                                                            + ensures el_ins._reset_all_for_tests runs for V78 timeline)

tests/test_regression_first_vault_timeline.py              (new — 29 tests across V77 + V78 shares)
tests/test_regression_first_endpoints.py                   (/health version 4.18 → 4.19)
tests/test_v28_endpoints.py                                (version 4.18 → 4.19)
tests/test_v51_projects.py                                 (version 4.18 → 4.19)
tests/test_v53_elins_v2.py                                 (version 4.18 → 4.19)
tests/test_v54_ingestion.py                                (version 4.18 → 4.19)

BUILD_VERSION                                              20260514120000 → 20260514140000
V77_READINESS.md                                          (new)
V78_READINESS.md                                          (new — see for timeline half)
```

---

## Architecture invariants verified

* **No HTTP contract change.** Every request/response shape stays
  identical to V76. `/me/regression_first/*` endpoint tests pass
  unchanged (apart from the `/health` version bump).
* **No in-process owner state.** The `_V76_OWNERS` side index is
  gone. `TestPersistenceAcrossCalls` exercises a chain across
  multiple requests with no shared module state.
* **Per-user partitioning is native.** Cross-user 404 is now
  enforced by `memory_vault.vault_get` itself — not by an explicit
  ownership check. Locked by `TestPerUserPartitioning` (5 tests).
* **Kernel stays user-agnostic.** Every `problem_solver` public
  function is still callable without a `user_id`. Tests that use
  the `DEFAULT_STORE` (in-memory) prove this.
* **Storage adapter is the only seam.** Endpoints inject a vault
  store; kernel tests inject nothing (use default). Replacing the
  vault store with e.g. a Firestore-backed store later requires a
  single-line change in `_v76_store_for`.

---

## Migration notes

No external consumers exist for V76 chains yet (no web/phone/desktop
surfaces shipped). Existing V76 endpoint tests continue to pass
against the new vault-backed store with zero modification. V77 is
purely an internal refactor of the persistence layer.

If you've been calling the kernel directly from a notebook or REPL
during V76 development:

* `start_chain(...)` etc. still work the same — they write to the
  module-level `DEFAULT_STORE`.
* To write to a real vault from a notebook, pass `store=VaultBackedRegressionChainStore("your_user_id")`
  explicitly.

---

## What's still pending

* **V79 — `intelligence_kernel.run_regression_first(user, problem)`**
  + `model_router.TASK_DEFAULTS["regression_first"]` → claude-3.7
  + kernel logging + the `/me/regression_first/packet` (raw text →
  EL/INS + auto-trigger) endpoint that was deferred from V76.
* **V80 — surfaces.** Web cockpit panel + phone screen + desktop
  consumer of the V76 endpoints. With V77 in place, the surfaces
  can rely on chains surviving across sessions.
