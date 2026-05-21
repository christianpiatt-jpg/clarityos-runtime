# V78 — Regression-First operator timeline integration

Status: ✅ Ready
Backend version: `4.19` (bundled with V77 — same pass, same bump)
Build: `20260514140000` (bundled with V77)

> V77 + V78 ship as **one** implementation pass per founder call.
> See [V77_READINESS.md](V77_READINESS.md) for the vault-persistence
> half of the same pass.

---

## What this pass ships

### Scope

Emit operator-timeline events for regression-chain activity, so
operators see chain lifecycle moments in their history alongside
existing thread/anomaly/rollup events. **Additive only** — no
existing event type is changed; three new types join the four V73
types in `el_ins/timeline.py`.

### Three new event types

`el_ins/timeline.py` registers three new strings on
`TIMELINE_EVENT_TYPES` and the corresponding `TimelineEventType`
Literal:

| Event type                          | Emitted by                                | Payload fields                                                 |
|-------------------------------------|-------------------------------------------|----------------------------------------------------------------|
| `regression_chain_started`          | `POST /me/regression_first/start`         | `chain_id` · `title` · `created_at_ms`                         |
| `regression_chain_layer_updated`    | `POST /me/regression_first/step`          | `chain_id` · `layer_index` · `status` · `updated_at_ms`        |
| `regression_chain_closed`           | `POST /me/regression_first/{cid}/close`   | `chain_id` · `closed_at_ms`                                    |

### Three new builders

`el_ins/timeline.py` exposes three pure builders. Same naming
convention as v73's `build_record_event` / `build_anomaly_event` /
`build_rollup_event`.

```python
build_regression_chain_started_event(operator_id, *, chain_id, title, created_at_ms)
build_regression_chain_layer_updated_event(operator_id, *, chain_id, layer_index, status, updated_at_ms)
build_regression_chain_closed_event(operator_id, *, chain_id, closed_at_ms)
```

Builders are pure; the endpoint stores the produced event via the
existing `timeline.store_event(...)`.

### Emission map

| Endpoint                                          | Emits                                                  |
|---------------------------------------------------|--------------------------------------------------------|
| `POST /me/regression_first/start`                 | `regression_chain_started` (1 event per call)          |
| `POST /me/regression_first/step`                  | `regression_chain_layer_updated` (1 event per call, including overwrites) |
| `POST /me/regression_first/{cid}/close`           | `regression_chain_closed` (1 event per call)           |
| `POST /me/regression_first/{cid}/tag`             | **none** — tags are mid-investigation metadata         |
| `GET  /me/regression_first/{cid}`                 | **none** — reads are not events                        |
| `GET  /me/regression_first`                       | **none** — reads are not events                        |

Locked by `TestNoSpuriousEmission` (3 tests).

### Emission is defensive

The endpoint helper `_v76_emit_timeline_event(event)` wraps
`store_event` in a `try/except` that logs and continues on failure.
A timeline storage hiccup will never roll back a successful chain
mutation — the chain itself is the source of truth, and the timeline
is a derived view. Same convention as `el_ins.run_thread_message`'s
emission hooks.

### Payload design notes

Payloads stay **minimal** — they index back into the chain via
`chain_id` rather than duplicating chain state. Consumers that want
the full chain dereference via `GET /me/regression_first/{chain_id}`.
This keeps timeline entries from drifting away from the vault-stored
chain (which is mutable while the chain is open).

### Test posture (V78 share)

| Suite                                                   | Tests | Status |
|---------------------------------------------------------|-------|--------|
| `tests/test_regression_first_vault_timeline.py` (V78 share — `TestTimelineEmission`, `TestNoSpuriousEmission`, `TestCrossUserTimelineNoLeak`, `TestEventTypeAdjacency`) | 10    | ✅     |
| `tests/test_el_ins_timeline.py` (existing v73 builders + storage still locked) | n/a   | ✅     |
| `tests/test_problem_solver.py` (kernel unchanged) | 84    | ✅     |
| `tests/test_regression_first_endpoints.py` (V76 contract preserved) | 27    | ✅     |

---

## Files touched (V78 share — bundled with V77 above)

```
el_ins/timeline.py                                         (+ 3 event types in TimelineEventType + TIMELINE_EVENT_TYPES
                                                            + 3 builders: build_regression_chain_started_event,
                                                              build_regression_chain_layer_updated_event,
                                                              build_regression_chain_closed_event)
el_ins/__init__.py                                         (re-exports the 3 new builders)

app.py                                                     (+ from el_ins import timeline as el_ins_timeline
                                                            + _v76_emit_timeline_event helper
                                                            + emission calls in /start, /step, /close handlers)

tests/test_regression_first_vault_timeline.py              (new — V78 share inside the combined V77+V78 file)
```

(See [V77_READINESS.md](V77_READINESS.md) for the full bundled file
diff including V77's persistence work.)

---

## Architecture invariants verified

* **Additive only — no existing event type changed.** v73's
  `record` / `anomaly` / `rollup` / `system` are unchanged. Locked
  by `TestEventTypeAdjacency::test_existing_types_preserved`.
* **Per-user partitioning.** Events emit with
  `operator_id = session["user"]`. The timeline module's
  per-operator bucket isolates cross-user reads natively. Locked
  by `TestCrossUserTimelineNoLeak`.
* **No spurious emission.** `/tag`, `/get`, `/list` emit no
  timeline events. Locked by `TestNoSpuriousEmission` (3 tests).
* **Defensive emission.** Emission failures are swallowed and
  logged; chain state already committed to vault. Same posture as
  `el_ins.run_thread_message`'s emission hook.
* **Minimal payloads, no state duplication.** Every payload
  references back to the chain via `chain_id`; the full chain
  lives in the vault, the timeline indexes it. Consumers fetching
  the chain always see current state, not a snapshot.
* **Builders produce schema-valid events.** Locked by
  `TestEventTypeAdjacency::test_builders_round_trip_via_store_event`
  which stores each builder's output via the existing
  `store_event` validator.

---

## What's still pending

Same as V77 — V79 (intelligence_kernel + auto-trigger wiring) and
V80 (surfaces) are the next units.
