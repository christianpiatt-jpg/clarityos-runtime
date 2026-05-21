# V81 — Tag deletion + chain archival

Status: ✅ Ready (bundled with V82 — same `/health` bump + adjacency sweep)
Backend version: `4.21` → `4.22`
Build: `20260514170000` → `20260514190000`

> Ships as half of the **V81+V82 bundle** per founder-locked decision.
> See [V82_READINESS.md](V82_READINESS.md) for the packet-replay half.

---

## What this pass ships

### Founder-locked semantics

**Archive = pure visibility flag.** Archived chains stay fully mutable —
`/step`, `/tag`, `/delete_tag`, `/close` all continue to work. The
default `GET /me/regression_first` list filters archived chains out;
pass `?include_archived=true` to include them. Archive is orthogonal
to close (a chain can be open+archived, closed+archived, etc.).
Archive is idempotent (calling on already-archived → no-op return).

This is **Model 1** from the V81 design discussion. Model 2
(archive-as-soft-close) was explicitly rejected: continuity invariant
requires that operators can continue work on a chain they've hidden
from the default list view.

### Backend

#### Kernel ([problem_solver/regression_first.py](problem_solver/regression_first.py))

* `RegressionChain` TypedDict gains `archived: bool` field.
  `start_chain` initialises it to `False`.
* `delete_tag(chain_id, key, *, store=None) -> RegressionChain` —
  drops one tag key. No-op when the key isn't present. Validates
  key is a non-empty string. Raises `ValueError` on closed chains
  (closed-chain mutation lockout from V77 still applies). Raises
  `KeyError` on unknown chain.
* `archive_chain(chain_id, *, store=None) -> RegressionChain` —
  sets `archived=True`. Idempotent. Does NOT touch `closed_at`.
  Raises `KeyError` on unknown chain.

#### Backward-compat ([problem_solver/chain_store.py](problem_solver/chain_store.py))

* `_coerce_chain_defaults(chain)` helper: defaults `archived=False`
  when reading a pre-V81 chain from the vault. Wired into
  `VaultBackedRegressionChainStore.get` and `.list_all`. Pre-V81
  chains keep working without a migration sweep.

#### Timeline ([el_ins/timeline.py](el_ins/timeline.py))

* New event type `regression_chain_archived` added to
  `TimelineEventType` Literal and `TIMELINE_EVENT_TYPES` tuple
  (additive only — v78's started/layer_updated/closed unchanged).
* New builder `build_regression_chain_archived_event(operator_id, *, chain_id, archived_at_ms)`
  — payload indexes back into the chain via `chain_id` and stamps
  the operator-visible timestamp at which archival happened (the
  kernel itself doesn't track this; the timeline is authoritative
  for the transition moment).

#### Endpoints ([app.py](app.py))

| Method | Path                                          | Behaviour                                                           |
|--------|-----------------------------------------------|---------------------------------------------------------------------|
| POST   | `/me/regression_first/delete_tag`             | Body `{chain_id, key}`. No-op on missing key. **No timeline event** (tags are metadata, not state). |
| POST   | `/me/regression_first/archive`                | Body `{chain_id}`. Idempotent. Emits `regression_chain_archived`.   |
| GET    | `/me/regression_first?include_archived=true`  | New query param, default `false`. Pure list filter — archived chains stay reachable via `/me/regression_first/{chain_id}` and all mutators. |

* `V76RegressionChainModel` gains `archived: bool = False`. Surfaces
  it on every response that already returns the chain.
* `_chain_to_model` reads `chain.get("archived", False)` for
  backward-compat (defensive — store coercion already fills it in).

### Architecture invariants

* **Archive is pure visibility.** Locked by
  `TestArchivedChainMutability` (4 tests): `step`/`tag`/`delete_tag`/
  `close` all work on archived chains.
* **Archive ≠ close.** Locked by
  `TestArchiveChainKernel::test_does_not_close_chain`.
* **Idempotent.** Locked by
  `TestArchiveChainKernel::test_idempotent_returns_same_chain` and
  endpoint-side `TestArchiveEndpoint::test_idempotent_200_ok`.
* **Per-user partitioning.** Cross-user calls on either endpoint
  return 404. Locked by `TestDeleteTagEndpoint::test_cross_user_returns_404`
  and `TestArchiveEndpoint::test_cross_user_returns_404`.
* **No timeline event for `/delete_tag`.** Locked by
  `TestDeleteTagEndpoint::test_emits_no_timeline_events`.
* **Archived chain stays directly fetchable.** `GET /me/regression_first/{cid}`
  ignores the archive flag. Locked by
  `TestListArchivedFilter::test_archived_chain_still_fetchable_directly`.
* **Backward-compat.** Pre-V81 chains read from the vault default
  `archived=False` via `_coerce_chain_defaults`.

---

## Test summary (V81 share)

| Suite                                                | Tests | Status |
|------------------------------------------------------|-------|--------|
| `tests/test_v81_regression_first_archive.py`         | 35    | ✅ new |
| `tests/test_problem_solver.py` (envelope key update) | 84    | ✅     |

Full adjacency sweep (combined V81+V82): **594 backend + 197 web + desktop tsc clean.**

### V81 test classes

| Class                          | Coverage                                                                                |
|--------------------------------|-----------------------------------------------------------------------------------------|
| `TestDeleteTagKernel`          | Removes existing key; no-op for missing key; persists via store; unknown chain → KeyError; non-string key + empty key → ValueError; closed chain rejects delete_tag. |
| `TestArchiveChainKernel`       | Sets `archived=True`; idempotent (same chain id, same flag); unknown chain → KeyError; does not close chain; default `archived=False` on new chains. |
| `TestArchivedChainMutability`  | Archived chains still accept `record_finding`, `tag_chain`, `delete_tag`, `close_chain` (locks Model 1 semantics). |
| `TestDeleteTagEndpoint`        | Updates tags; no-op on missing key; unknown chain 404; cross-user 404; **emits no timeline events**; requires session. |
| `TestArchiveEndpoint`          | Sets flag; emits `regression_chain_archived` event with `archived_at_ms`; idempotent 200 OK; unknown chain 404; cross-user 404; requires session. |
| `TestListArchivedFilter`       | Excludes archived by default; includes when `?include_archived=true`; archived chain still fetchable directly via `/me/regression_first/{cid}`. |
| `TestRoutesAndManifest`        | Both new routes registered; both in `GET /` manifest; `/health` 4.22; chain envelope exposes `archived` field. |

---

## Files touched (V81 share)

```
problem_solver/regression_first.py             (+ RegressionChain.archived field
                                                + start_chain sets archived=False
                                                + delete_tag(chain_id, key, *, store)
                                                + archive_chain(chain_id, *, store))
problem_solver/chain_store.py                  (+ _coerce_chain_defaults helper
                                                + applied in VaultBackedStore.get / .list_all)
problem_solver/__init__.py                     (+ re-exports delete_tag + archive_chain)

el_ins/timeline.py                             (+ regression_chain_archived event type
                                                + build_regression_chain_archived_event)
el_ins/__init__.py                             (re-exports new builder)

app.py                                         (+ V81DeleteTagRequest / V81ArchiveRequest
                                                + V76RegressionChainModel.archived field
                                                + _chain_to_model maps archived
                                                + POST /me/regression_first/delete_tag
                                                + POST /me/regression_first/archive
                                                + /me/regression_first list include_archived query
                                                + 2 manifest entries
                                                /health 4.21 → 4.22)

tests/test_v81_regression_first_archive.py     (new — 35 tests across 7 classes)
tests/test_problem_solver.py                   (envelope assertion includes archived key)

V81_READINESS.md                               (new)
```

---

## What's still pending

Nothing in the archival arc. V82 (bundled with this pass) is the
next deliverable.
