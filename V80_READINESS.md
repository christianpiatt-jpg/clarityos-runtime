# V80 — Regression-First packet endpoint + 3 surfaces

Status: ✅ Ready
Backend version: `4.20` → `4.21`
Build: `20260514150000` → `20260514170000`

---

## What this pass ships

### Founder-locked decisions

1. **`/packet` emits timeline events.** A regression chain is a
   regression chain regardless of creation path; packet-driven chains
   must show up in the operator's timeline alongside manual ones, or
   the operator ends up with two histories for the same state.
   (Continuity invariant.)
2. **"Start + one step" semantics.** `/packet` opens a chain (emits
   `regression_chain_started`) and seeds the **last** entry of the
   packet's `regression_chain` skeleton as a finding with
   `status="unknown"` (emits one `regression_chain_layer_updated`).
   Remaining skeleton entries are operator-driven via `/step`.
3. **Split V79 + V80.** V79 was kernel-only plumbing; V80 is the
   endpoint + 3 surfaces. UI work across web/phone/desktop is large
   enough to warrant its own pass.

### Scope

* **Backend** — new `POST /me/regression_first/packet` endpoint.
* **Web** — `RegressionFirstPanel` mounted in the operator cockpit.
* **Phone** — `regression_first.tsx` screen + settings tile.
* **Desktop** — `RegressionFirstShell` + App.tsx view router.
* No new model_router or kernel changes — V79's wiring is reused
  end-to-end.

### Backend

`POST /me/regression_first/packet` (`app.py`):

* **Auth**: `require_session` (401 anonymous, same as every
  `/me/*` endpoint).
* **Body**: `V80PacketRequest { packet: dict[str, Any] }`.
* **Pipeline**:
  1. `_v76_store_for(user)` → vault-backed store (V77).
  2. `intelligence_kernel.run_regression_first(packet, user_id, store)`
     (V79) — resolves model_id via `TASK_DEFAULTS["regression_first"]`,
     parses + persists empty chain, emits structured kernel_run log.
  3. If `ok=False` → **422** `packet_rejected`.
  4. If `chain` is None (`regression_required=False`) → **422**
     `regression_not_required`.
  5. Emit `regression_chain_started` (V78 builder).
  6. If packet's skeleton has ≥ 1 entry, call
     `problem_solver.record_finding(chain_id, len(skeleton)-1,
     "unknown", _v80_synthesize_layer_notes(last_entry), store=store)`.
  7. Emit `regression_chain_layer_updated` for the seeded layer.
* **Response**: `V76RegressionChainModel` (same shape as
  `/me/regression_first/get`).

#### Notes synthesis

`_v80_synthesize_layer_notes(entry)` joins the skeleton entry's
`name | question | (look here: location) | (goal: goal)` so the
operator who later inspects the layer has the full diagnostic
context from the originating packet without having to re-read it.

#### Indexing

The seeded layer's `layer_index` is **the array position** of the
last entry in the skeleton, not the skeleton entry's 1-based `layer`
field. Stored chain layers are 0-based per V76 spec; packet skeleton
entries are 1-based per the bundle schema. The endpoint converts.

### Web cockpit

* New file: [web/src/components/cockpit/RegressionFirstPanel.tsx](web/src/components/cockpit/RegressionFirstPanel.tsx)
  * Pre-filled JSON editor with the canonical example packet.
  * "Run Regression First" button.
  * Result summary: title · chain_id · open/closed · layer/tag counts ·
    seeded layer index + status.
  * Error states: `invalid_json`, `packet_rejected`,
    `regression_not_required`, plus generic API errors.
* New API helper [web/src/lib/api.ts](web/src/lib/api.ts):
  `postRegressionFirstPacket(packet) -> RegressionFirstChain` +
  `RegressionFirstChain` / `RegressionFirstLayer` types.
* Wired into [web/src/routes/Cockpit.tsx](web/src/routes/Cockpit.tsx)
  as a new `<Panel title="Regression First (v80) — packet runner">`.
  Already lives under `<RequireAuth>` (no extra gating needed).

### Phone

* New screen: [phone/app/regression_first.tsx](phone/app/regression_first.tsx)
  * Same pre-filled JSON example.
  * Multiline `TextInput` + "Run Regression First" button.
  * Same result summary as the web panel (title, chain_id, state,
    seeded layer).
* New API helper [phone/lib/api.ts](phone/lib/api.ts):
  `postRegressionFirstPacket(packet) -> RegressionFirstChain` (1:1
  with web).
* Registered in [phone/app/_layout.tsx](phone/app/_layout.tsx) as a
  `Stack.Screen`.
* Discoverable from [phone/app/settings.tsx](phone/app/settings.tsx)
  — new "Regression First" card below the Threads card.

### Desktop

* New shell: [desktop/src/RegressionFirstShell.tsx](desktop/src/RegressionFirstShell.tsx)
  * Same packet editor + run button + result summary, styled with
    the Somatic palette tokens (`--os-accent`, `--os-boundary`).
  * Auth-gated via `DesktopAuthGate`; `handleAuthError` clears the
    session and bounces back to sign-in on 401/403.
* New API helper [desktop/src/lib/api.ts](desktop/src/lib/api.ts):
  same `postRegressionFirstPacket` + types.
* Wired into [desktop/src/App.tsx](desktop/src/App.tsx) as a new
  `"regression-first"` view, navigable via `onNavigate("Regression First")`.
* `npx tsc --noEmit` clean.

---

## Endpoints

| Method | Path                                          | Status |
|--------|-----------------------------------------------|--------|
| POST   | `/me/regression_first/packet`                 | new (v80) |

All 6 v76 routes + the new v80 route now listed in `GET /` manifest.

### Error contract (V80)

| Condition                                          | HTTP | Body                                                |
|----------------------------------------------------|------|-----------------------------------------------------|
| Missing/invalid session                            | 401  | `{detail: error_response("missing_session" / "invalid_session")}` |
| Pydantic body validation (non-dict `packet`)       | 422  | FastAPI default validation error                    |
| Kernel `ok=False` (malformed packet)               | 422  | `{detail: error_response("packet_rejected", ...)}`  |
| `regression_required=False` (no chain to create)   | 422  | `{detail: error_response("regression_not_required", ...)}` |

---

## Test summary

| Suite                                              | Tests | Status |
|----------------------------------------------------|-------|--------|
| `tests/test_v80_regression_first_packet.py`        | 22    | ✅ new |
| `web .../RegressionFirstPanel.test.tsx`            | 9     | ✅ new |
| `tests/test_v79_regression_first_task.py`          | 22    | ✅ (TestNoHttpChange→TestHttpSurface refactor) |
| `tests/test_problem_solver.py`                     | 84    | ✅     |
| `tests/test_regression_first_endpoints.py`         | 27    | ✅ (version 4.20→4.21) |
| `tests/test_regression_first_vault_timeline.py`    | 29    | ✅     |
| `tests/test_v40_intelligence_kernel.py`            | ~30   | ✅     |
| `tests/test_v44_model_router.py`                   | ~30   | ✅     |
| `tests/test_el_ins_analyzer.py`                    | 33    | ✅     |
| `tests/test_el_ins_timeline.py`                    | ~30   | ✅     |
| `tests/test_v28_endpoints.py`                      | ~70   | ✅ (4.20→4.21) |
| `tests/test_v47_threads.py`                        | ~80   | ✅     |
| `tests/test_v51_projects.py`                       | 40    | ✅ (4.20→4.21) |
| `tests/test_v53_elins_v2.py`                       | —     | ✅ (4.20→4.21) |
| `tests/test_v54_ingestion.py`                      | —     | ✅ (4.20→4.21) |
| `tests/test_membership_confirm.py`                 | 6     | ✅     |
| **Backend full sweep**                             | **542** | **✅** |
| **Web full suite**                                 | **192** | **✅** |
| **Desktop**                                        | tsc clean | **✅** |

### V80 backend test classes

| Class                          | Coverage                                                                |
|--------------------------------|-------------------------------------------------------------------------|
| `TestHappyPath`                | Persists chain in vault under `regression_chains.{cid}`; response matches `V76RegressionChainModel`. |
| `TestSeededLayer`              | Last skeleton entry seeded with `status="unknown"`; `layer_index` is the array position (not the skeleton's 1-based `layer` field); 1-layer skeleton still seeds at index 0. |
| `TestTimelineEmission`         | Both `regression_chain_started` AND `regression_chain_layer_updated` emitted exactly once; layer event payload targets the last skeleton index. |
| `TestPerUserPartitioning`      | Cross-user 404 (Bob can't read Alice's chain or see it in his list); cross-user timeline isolation (Bob's timeline empty of regression events). |
| `TestPacketRejected`           | Missing required field / invalid scores / wrong classification vocabulary / non-dict packet → 422 `packet_rejected`; rejected packets emit ZERO timeline events. |
| `TestRegressionNotRequired`    | `regression_required=False` → 422 `regression_not_required`; no chain in vault; no timeline events. |
| `TestAuthGating`               | Anonymous + invalid session both 401. |
| `TestRouteAndManifest`         | Route registered in `app.routes`; all v76 routes still present; route entry in `GET /` manifest; `/health` version locked at 4.21. |

### V80 web test class

| Class                          | Coverage                                                                |
|--------------------------------|-------------------------------------------------------------------------|
| `RegressionFirstPanel`         | Renders editor + run button; pre-filled example contains canonical fields; click posts parsed JSON to `postRegressionFirstPacket`; renders chain summary + ok marker on success; renders error code/message on `ApiError`; rejects non-JSON and bare-string body without hitting the API; renders fallback when chain has no layers. |

---

## Files touched

```
app.py                                                     (+ V80PacketRequest
                                                            + _v80_synthesize_layer_notes
                                                            + POST /me/regression_first/packet handler
                                                            + manifest entry
                                                            + Any import
                                                            /health 4.20 → 4.21)

tests/test_v80_regression_first_packet.py                  (new — 22 tests across 8 classes)
tests/test_v79_regression_first_task.py                    (TestNoHttpChange → TestHttpSurface, narrowed to "v76 routes present")
tests/test_v28_endpoints.py                                (version 4.20 → 4.21)
tests/test_v51_projects.py                                 (version 4.20 → 4.21)
tests/test_v53_elins_v2.py                                 (version 4.20 → 4.21)
tests/test_v54_ingestion.py                                (version 4.20 → 4.21)
tests/test_regression_first_endpoints.py                   (version 4.20 → 4.21)

web/src/lib/api.ts                                         (+ postRegressionFirstPacket
                                                            + RegressionFirstChain / RegressionFirstLayer types)
web/src/components/cockpit/RegressionFirstPanel.tsx        (new)
web/src/routes/Cockpit.tsx                                 (+ import + new Panel)
web/src/components/cockpit/__tests__/RegressionFirstPanel.test.tsx  (new — 9 tests)

phone/lib/api.ts                                           (+ postRegressionFirstPacket + types)
phone/app/regression_first.tsx                             (new screen)
phone/app/_layout.tsx                                      (+ Stack.Screen registration)
phone/app/settings.tsx                                     (+ "Regression First" card)

desktop/src/lib/api.ts                                     (+ postRegressionFirstPacket + types)
desktop/src/RegressionFirstShell.tsx                       (new)
desktop/src/App.tsx                                        (+ import, View union, handleNavigate label, view router branch)

BUILD_VERSION                                              20260514150000 → 20260514170000
V80_READINESS.md                                          (new)
```

---

## Architecture invariants verified

* **`/packet` emits timeline events.** Both `regression_chain_started`
  AND `regression_chain_layer_updated` emit on every successful
  packet ingest. Continuity invariant: packet-driven chains coexist
  with manual `/start` + `/step` chains in the same timeline.
* **Per-user partitioning** is native — same `_v76_store_for(user)`
  helper used by every other v76 endpoint; cross-user reads return
  404 (existence not leaked).
* **Vault round-trip.** Every successful `/packet` call writes the
  chain to `regression_chains.{chain_id}` for the caller's user.
  Direct vault reads in tests confirm the chain is present + correct.
* **Defensive timeline emission.** Failures are swallowed and logged;
  chain mutation already committed to the vault.
* **422 paths emit NO events.** `packet_rejected` and
  `regression_not_required` both bail out before any timeline call.
  Locked by `TestPacketRejected::test_rejected_packet_emits_no_timeline_events`
  + `TestRegressionNotRequired::test_no_timeline_events_when_not_required`.
* **Layer indexing convention.** Stored chain layers stay 0-based
  per V76 spec; skeleton entries' 1-based `layer` field is ignored.
  Locked by `TestSeededLayer::test_single_layer_skeleton_seeded_at_index_zero`.
* **No new model_router or kernel changes.** V79 substrate is reused
  end-to-end. V80 is endpoint + surfaces only.
* **Surface parity.** Web/phone/desktop all expose
  `postRegressionFirstPacket(packet) -> RegressionFirstChain` with
  identical TypeScript types. Same example packet pre-filled across
  all three surfaces. Same result summary fields.

---

## What's still pending

Nothing in the V76–V80 regression-first arc. The full pipeline is:

* **V75** — kernel + skills_export bundle
* **V76** — 6 manual endpoints
* **V77** — vault persistence
* **V78** — timeline emission
* **V79** — intelligence_kernel + model_router wiring
* **V80** — `/packet` endpoint + 3 surfaces ← (this pass)

The protocol is now fully shipped across the backend, three client
surfaces, the timeline, and the vault. Operators can:

1. Manually create + walk chains via the v76 endpoints.
2. Drop a single packet and get a one-shot persisted chain via
   v80 `/packet`.
3. See every chain mutation in their operator timeline.
4. Cross-reference chains with EL/INS analysis (the same packet
   carries both).

Any future regression_first work is now feature-add territory —
e.g. tag deletion (deferred from V77), packet-history replay, or
LLM-driven inference of new packets from raw operator text. None
of those are in flight.
