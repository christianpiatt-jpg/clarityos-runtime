# V82 — Packet history + replay

Status: ✅ Ready (bundled with V81 — same `/health` bump + adjacency sweep)
Backend version: `4.21` → `4.22`
Build: `20260514170000` → `20260514190000`

> Ships as half of the **V81+V82 bundle** per founder-locked decision.
> See [V81_READINESS.md](V81_READINESS.md) for the archival half.

---

## What this pass ships

### Scope

Operators can replay a regression chain from its original packet.
The replay creates a **new** chain (new `chain_id`, fresh timeline
events, fresh seeded layer) — the original chain is untouched.

### Backend

#### Vault namespace ([memory_vault.py](memory_vault.py))

* `regression_packets` added to `ALLOWED_NAMESPACES`. Each entry
  lives under `regression_packets.{chain_id}` (the chain's id is the
  key). Value is the original packet dict.

#### `/packet` endpoint extension ([app.py](app.py))

* After a successful kernel run, the original packet is persisted
  via `_v82_persist_original_packet(user, chain_id, packet)`:
  * **First-packet-wins** — repeated writes are skipped (in V82 only
    `/replay` could trigger a second write for the same chain_id,
    and replay creates a new chain_id anyway).
  * **Defensive** — vault hiccups during persistence are logged and
    swallowed; they cannot roll back the chain mutation that just
    succeeded.
* Persistence happens AFTER the kernel succeeds but BEFORE the
  timeline emits, so a packet that fails to persist also doesn't
  emit a meaningless `chain_started` (the chain itself would still
  exist via the V77 vault store but the replay surface would be
  unreachable; this is the documented behaviour).

#### `/replay` endpoint ([app.py](app.py))

```
POST /me/regression_first/replay
  Auth: require_session
  Body: { chain_id: str }
  Response: V76RegressionChainModel  (the NEW chain)
```

Pipeline:

1. `_v82_load_original_packet(user, chain_id)` → 404 if no original
   packet is stored for the operator (chain was created via `/start`
   instead of `/packet`, chain_id is unknown, or vault read failed).
2. `intelligence_kernel.run_regression_first(packet=original, user_id=user, store=store)`
   — same V79 substrate as `/packet`.
3. If the kernel now degrades (extremely unlikely — the same packet
   succeeded once already), 422 `packet_rejected`. If it parses but
   `regression_required` flips somehow, 422 `regression_not_required`.
4. Persist the (same) original packet under the new chain_id so a
   replay-of-a-replay still finds an origin packet.
5. Emit `regression_chain_started`.
6. Same V80 seed policy — record the last skeleton entry as a
   finding with `status="unknown"` and notes synthesized from the
   entry's name/question/location/goal. Emit
   `regression_chain_layer_updated`.
7. Return the new chain.

### Surfaces

| Surface  | Location                                                         | Affordance                                                                            |
|----------|------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| Web      | [RegressionFirstPanel.tsx](web/src/components/cockpit/RegressionFirstPanel.tsx) | "Rerun regression" button on the result summary; swaps to the new chain; "replay" badge on title. |
| Phone    | [regression_first.tsx](phone/app/regression_first.tsx)           | "Rerun regression" secondary Pressable below the chain card; "(replay)" suffix on Chain header.   |
| Desktop  | [RegressionFirstShell.tsx](desktop/src/RegressionFirstShell.tsx) | "RERUN REGRESSION" secondary button on the chain panel; "REPLAY" badge on heading.                |

All three surfaces share `replayRegressionFirstChain(chain_id)` in
their respective `lib/api.ts` with identical signatures.

### Architecture invariants

* **First packet wins.** `_v82_persist_original_packet` reads
  existing entry first and skips if present. The kernel succeeds
  once, the packet locks. Locked by
  `TestReplay::test_replay_of_replay_persists_packet_for_new_chain`
  (replay creates a new chain_id, gets a fresh packet entry, but
  the original remains untouched).
* **Original chain untouched by replay.** Locked by
  `TestReplay::test_does_not_alter_original_chain`.
* **Per-user partitioning.** Cross-user replay returns 404. Locked
  by `TestReplay::test_respects_user_partitioning`.
* **404 on manual chains.** A chain created via `/start` (not
  `/packet`) has no stored packet → `/replay` returns 404. Locked
  by `TestReplay::test_404_for_chain_created_manually_no_packet`.
* **Continuity invariant.** Replay emits the same timeline event
  types as `/packet` — chain activity is uniform regardless of
  creation path. Locked by
  `TestReplay::test_emits_started_and_layer_updated_events`.
* **Failed `/packet` persists nothing.** A rejected packet leaves
  no entry under `regression_packets`. Locked by
  `TestPacketPersistence::test_failed_packet_persists_nothing`.
* **Seed policy parity.** Replay's seeded layer matches the V80 seed
  policy exactly (last skeleton entry, `status="unknown"`, notes
  synthesized identically). Locked by
  `TestReplay::test_seeded_layer_matches_packet_seed_policy`.

---

## Test summary (V82 share)

| Suite                                              | Tests | Status |
|----------------------------------------------------|-------|--------|
| `tests/test_v82_regression_first_replay.py`        | 17    | ✅ new |
| `web .../RegressionFirstPanel.test.tsx` (V82 share)| 5     | ✅ new (14 total in file) |

Full adjacency sweep (combined V81+V82): **594 backend + 197 web + desktop tsc clean.**

### V82 backend test classes

| Class                          | Coverage                                                                                |
|--------------------------------|-----------------------------------------------------------------------------------------|
| `TestPacketPersistence`        | `/packet` persists original under `regression_packets.{cid}`; `regression_packets` is in `ALLOWED_NAMESPACES`; failed packets persist nothing; two distinct packets persist independently. |
| `TestReplay`                   | Creates new chain with new id; 404 on missing stored packet; 404 for manual `/start` chains (no original); cross-user 404; emits both `started` + `layer_updated` events; doesn't alter original chain; seeded layer matches V80 policy; new chain has fresh envelope (closed_at=None, archived=False, empty tags); requires session; replay-of-replay still persists packet for new chain. |
| `TestRoutesAndManifest`        | `/replay` registered; in manifest; `/health` 4.22. |

### V82 web test cases (in RegressionFirstPanel.test.tsx)

| Test                                                  | Locks                                                          |
|-------------------------------------------------------|----------------------------------------------------------------|
| `rerun button appears after successful packet run`    | Button is hidden until a packet has succeeded                  |
| `rerun calls /replay with the current chain_id`       | API call shape (one arg, chain_id of the currently-shown chain) |
| `rerun success swaps the summary to the new chain + tags replay` | UI swaps to the new chain + replay badge appears        |
| `rerun error surfaces via the error banner`           | ApiError surfaces in the existing error banner                 |
| `rerun is absent before any successful run`           | Lock — no button in idle state                                 |

---

## Files touched (V82 share)

```
memory_vault.py                                (+ "regression_packets" to ALLOWED_NAMESPACES)

app.py                                         (+ V82ReplayRequest
                                                + _V82_PACKET_NS / _v82_packet_key helpers
                                                + _v82_persist_original_packet
                                                + _v82_load_original_packet
                                                + /me/regression_first/packet calls persist helper
                                                + POST /me/regression_first/replay handler
                                                + manifest entry)

tests/test_v82_regression_first_replay.py      (new — 17 tests across 3 classes)

web/src/lib/api.ts                             (+ replayRegressionFirstChain)
web/src/components/cockpit/RegressionFirstPanel.tsx  (+ onRerun callback + Rerun button + replay badge + source tracking)
web/src/components/cockpit/__tests__/RegressionFirstPanel.test.tsx  (+ 5 Rerun tests + replayRegressionFirstChain mock + archived field on fixture)

phone/lib/api.ts                               (+ replayRegressionFirstChain)
phone/app/regression_first.tsx                 (+ rerun callback + secondary Pressable + (replay) header suffix + ctaSecondary styles)

desktop/src/lib/api.ts                         (+ replayRegressionFirstChain)
desktop/src/RegressionFirstShell.tsx           (+ onRerun callback + RERUN REGRESSION button + REPLAY badge + btnSecondary / btnSecondaryDisabled / replayBadgeStyle)

V82_READINESS.md                               (new)
BUILD_VERSION                                  20260514170000 → 20260514190000   (shared with V81)
```

---

## What's still pending

The regression_first protocol is now complete across V75–V82. Future
work is feature-add territory:

* **Unarchive surface** — currently archival is irreversible (the
  flag flips True only; no `unarchive` endpoint). The flag itself
  is reversible at the kernel level (it's just `chain["archived"] = False`)
  but no surface exposes it.
* **Per-chain detail page** — both surfaces currently show a single
  active chain summary; a dedicated chain detail / chain list view
  could surface tags, layer history, full notes editing, and
  replay-from-the-list affordances.
* **Packet history inspector** — `regression_packets.{chain_id}`
  entries are not exposed via any GET endpoint. A founder console
  could surface them.

None of these are blockers.
