# ClarityOS Surface + Distribution Layer — Implementation Plan

Backend additions + web cockpit composite + phone ELINS screen + daily 05:00-local
distribution scheduler. **Additive only**: existing routes, stores, envelope schema,
and Dewey taxonomy unchanged. No new primitives.

## Constraints honored

- **Local cognition**: full envelope evolution (v6→v27) stays on the existing `/markov/chat`
  path. The new surfaces only **read** envelope state.
- **Dewey-only metadata sharing**: mesh sync stores ONLY per-layer counts +
  `last_updated_ts` values. No vectors, no text, no event content.
- **No new primitives**: `#G ELINS` reuses `dewey_pipeline.embed_text_cached`,
  the existing universal-physics block, ELINS physics_block (when JSON ingested),
  and v17 PRC. It does NOT call `_evolve_envelope` so no per-user events are mutated.
- **O(1) reasoning**: every new endpoint reads/writes O(1) per-user blobs; the
  scheduler runs O(N queued reports) per wake, capped at 500 outstanding entries.

## Backend additions (in `app.py` and 2 new modules)

### New stores
- `elins_distribution_store.py` — queued reports + delivered feed
- `mesh_metadata_store.py` — per-user metadata mesh

### New endpoints (auth-gated via `X-Session-ID`)
| Route | Method | Purpose |
|---|---|---|
| `/elins/g/run` | POST | #G ELINS engine — scenario → structured analysis (no content storage) |
| `/elins/daily/queue` | POST | Queue today's report for delivery at next 05:00 local |
| `/elins/daily/feed` | GET | Paginated delivered-reports feed (web/phone consume) |
| `/mesh/sync` | POST | Push metadata-only blob (counts + last_updated_ts) |
| `/mesh/state` | GET | Pull aggregated mesh metadata for the user |
| `/continuity/snapshot` | GET | Cross-session continuity surface (metadata-only) |

### Daily delivery scheduler
- `threading.Thread(daemon=True)` started on first request
- Loops with 60s sleep; on each wake, scans queued reports where `scheduled_for_ts ≤ now`
- Marks delivered, appends to feed, optionally emails (env-var `CLARITYOS_SMTP_*`)
- Per-user `delivery_local_hour` defaults to 05:00; configurable via queue payload

## Data flow diagram

```
                      ┌────────────────────────────────────────┐
                      │            CLIENT SURFACES             │
                      │   ┌──────────┐         ┌──────────┐    │
                      │   │   WEB    │         │  PHONE   │    │
                      │   │ Cockpit  │         │  Screens │    │
                      │   └────┬─────┘         └────┬─────┘    │
                      └────────┼────────────────────┼──────────┘
                               │                    │
                               ▼                    ▼
                      ┌─────────────────────────────────────────┐
                      │          FASTAPI BACKEND (Cloud Run)    │
                      │                                         │
   /markov/chat ─────►│ _evolve_envelope()  (v6→v27 cascade)    │
                      │      │                                  │
                      │      ▼                                  │
                      │  envelopes_store  ◄──── reads ────────┐ │
                      │      │                                │ │
                      │      ├── physics_reasoning_context ───┤ │
                      │      ├── reasoning_cues/weights/...   │ │
                      │      ├── memory_context/cognitive_loop│ │
                      │      └── response_shape/templates/... │ │
                      │                                       │ │
                      │  ┌──────────────────────────────┐     │ │
                      │  │ NEW v28 SURFACE/DISTRIBUTION │     │ │
                      │  ├──────────────────────────────┤     │ │
   /elins/g/run ─────►│  │ #G engine: embed → dewey →   │     │ │
                      │  │ universal_physics → return.  │     │ │
                      │  │ Persists: dewey membership   │     │ │
                      │  │ ONLY (no scenario text).     │     │ │
                      │  ├──────────────────────────────┤     │ │
   /elins/daily/  ───►│  │ elins_distribution_store     │     │ │
   {queue,feed}       │  │   queued: list[report]       │     │ │
                      │  │   delivered: list[report]    │     │ │
                      │  │ scheduler thread @05:00local │     │ │
                      │  ├──────────────────────────────┤     │ │
   /mesh/{sync,state}►│  │ mesh_metadata_store          │     │ │
                      │  │   metadata-only blob/user    │     │ │
                      │  │   counts + last_updated_ts   │     │ │
                      │  ├──────────────────────────────┤     │ │
   /continuity/   ───►│  │ pulls from envelopes +       │ ◄───┘ │
   snapshot           │  │ markov_states (read-only)    │       │
                      │  └──────────────────────────────┘       │
                      └─────────────────────────────────────────┘
                               │
                               ▼ (optional)
                      ┌──────────────────┐
                      │  SMTP (env-var   │
                      │   gated)         │
                      └──────────────────┘
```

## Web component structure (additions only)

```
web/src/
├── lib/api.ts          (add: gElinsRun, elinsQueue, elinsFeed, meshSync,
│                            meshState, continuitySnapshot)
└── routes/
    ├── Cockpit.tsx     (NEW — composite: SessionList + RuntimePanel +
    │                    VaultStatus + EngineSelector + Settings +
    │                    ContinuitySurface, fed by existing API)
    └── Elins.tsx       (NEW — #G runner + daily feed)
```

`Cockpit.tsx` reads the LATEST envelope via `/markov/envelope/latest` and renders:
- the v17 `physics_reasoning_context`
- v18 `reasoning_cues` / v19 `reasoning_weights`
- v20 `memory_context` / v22 `cognitive_loop` / v23 `reasoning_scaffold`
- v24 `response_shape` / v25 `response_templates` / v27 `connective_ops`
- v14 `coherence` flags

All blocks are deterministic dicts — UI just walks the JSON. **No summarization,
no embeddings, no inference at the surface layer.**

## Phone screen structure (additions only)

```
phone/
├── lib/api.ts          (add: same helpers as web)
└── app/
    └── elins.tsx       (NEW — #G runner + daily feed)
```

The existing Orb (`components/Orb.tsx`), session list (`app/session/`), vault
(`app/vault.tsx`), engine selector (`components/EngineToggle.tsx`), and
continuity layer (`app/continuity.tsx`) already exist. The new ELINS screen
is the only addition needed for this layer.

## Mesh sync logic

```
client (web or phone) ─POST /mesh/sync──► server
   body: {
     device_id: str,                    # opaque device handle
     metadata: {
       envelope_layers: { v17_present, v18_present, ... },
       last_updated_ts: { v17, v18, ... },
       counts: { episodes, narratives, story_arcs, events },
       session_ids: list[str],          # session ids only, no content
       continuity_ts: float
     }
   }

server merges into mesh_metadata_store[user][device_id] = metadata
GET /mesh/state returns aggregate { device_id → metadata } for the user.
```

Per-user mesh blob is bounded: ≤ 16 KB per device, ≤ 8 devices retained
(LRU eviction by `last_seen_ts`).

## ELINS distribution logic

```
1. Client POST /elins/daily/queue { scenario_text, deliver_email?, deliver_feed? }
   → server computes `scheduled_for_ts` = next 05:00 local for the user
   → returns { ok, report_id, scheduled_for_ts }

2. Scheduler thread (60s tick):
   for report in queued where scheduled_for_ts ≤ now:
       analysis = _run_g_elins(report.scenario_text, user)
       elins_distribution_store.deliver(report_id, analysis)
       if deliver_email and SMTP configured: send_email(analysis)
       feed[user].append({delivered_at, scenario_id, analysis})

3. GET /elins/daily/feed → returns delivered reports for user (limit + cursor).
```

## #G ELINS engine logic

```
POST /elins/g/run { scenario_text }
   ↓
   v_scenario = embed_text_cached(scenario_text)
   neighborhoods = top_neighborhoods_with_curvature(v_scenario, user_nbs, k=5)
   noise = compute_noise_component(v_scenario, v_scenario, v_scenario, neighborhoods)
   universal = _build_universal_physics_block()
   physics_block = (envelope.elins.physics_block if present else {})
   ↓
   return {
     ok: true,
     analysis: {
       neighborhoods: [{nb_id, sim, curvature}],
       universal_physics: universal,
       elins_physics: physics_block,
       qc_summary: { drift, pressure },
       last_updated_ts: now
     }
   }

   PERSIST: only dewey_memberships_store entries (membership is metadata, not content)
   NEVER: scenario_text, vectors of scenario, output text
```

## Local vault + Dewey-only sharing guarantees

| What | Where | Shared? |
|---|---|---|
| Vault items (text/binary content) | `vault_store` (per-user Firestore doc) | NEVER |
| Library user items | `library_store` (per-user) | NEVER |
| Envelope events (text snapshots) | `envelopes_store.events` (per-user) | NEVER |
| Envelope layer aggregates (counts, ts) | `envelopes_store` | Mesh-summarized: counts + ts only |
| DEWEY neighborhoods (membership) | `dewey_memberships_store` | Already metadata; mesh shareable |
| Dewey neighborhood vectors | `dewey_neighborhoods_store` | Stays local (mesh stores IDs only) |

## Files added / changed in this pass

```
NEW   elins_distribution_store.py
NEW   mesh_metadata_store.py
EDIT  app.py                              (+ 6 routes, + scheduler thread, + helpers)
EDIT  web/src/lib/api.ts                  (+ 6 helpers)
NEW   web/src/routes/Cockpit.tsx
NEW   web/src/routes/Elins.tsx
EDIT  web/src/App.tsx                     (+ 2 route entries)
EDIT  phone/lib/api.ts                    (+ 6 helpers)
NEW   phone/app/elins.tsx
NEW   SURFACE_DISTRIBUTION_PLAN.md        (this file)
```

## Out of scope for this pass

- SMTP integration (placeholder hook; env-var-gated, no-op when unset)
- Push notifications to mobile (feed is poll-based for now)
- Cross-device push of mesh changes (clients pull `/mesh/state`)
- React UI polish beyond functional rendering of envelope dicts
