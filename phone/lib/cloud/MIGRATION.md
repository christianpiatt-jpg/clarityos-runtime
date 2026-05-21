# Architecture D — migration spec

The phone app currently runs end-to-end **local-first**: model router (stub),
Langbridg, Clarity transform, Vault, and Continuity all execute in
`phone/lib/`. This document defines the four cloud cutovers and the
contract each one must satisfy.

**No backend code has been written yet.** Each section below is the
contract for what the backend service needs to expose. Flip the matching
flag in `lib/cloud/config.ts` after the route ships.

The current backend (`C:\ClarityOS_Code\app.py`) is **stable
infrastructure** per prior direction. None of these routes exist on it
today; adding them requires explicit user go-ahead per route.

---

## 1. Cloud Clarity Engine

**Goal:** move `transform(clarityObject)` out of the device.

**Why first:** `transform()` is a pure function. No auth, no state, no
secrets. Lowest-risk cutover.

**Frontend integration point:** `phone/app/copy.tsx`. When
`isCloudEnabled('clarityEngine')` is true, instead of running
`transform(clarity)` locally, POST the ClarityObject to the route
below and render the response.

**Backend contract:**
```
POST /clarity/transform
Headers: X-Session-ID: <token>
Body:    ClarityObject (see phone/lib/langbridg.ts)
Returns: ClarityRender (see phone/lib/clarity.ts)
```

The server reuses the same `transform()` logic (port to Python or run
Node — engineer's choice). Pure function; no DB.

**Cutover steps:**
1. Add the route to `app.py`.
2. Port `transform()` to Python (≈50 lines).
3. Set `CLOUD_FEATURES.clarityEngine = true`.
4. Verify against the local result for a fixed input — they should be
   identical character-for-character.

---

## 2. Cloud Model Proxy

**Goal:** move API-key-bearing model calls server-side.

**Why second:** unblocks real model integration without shipping keys
to phones. `modelRouter.ts` already has the right shape — stub mode
calls `sendToX(text)`, real mode would call the proxy.

**Frontend integration point:** `phone/lib/modelRouter.ts`. When
`isCloudEnabled('modelProxy')` is true, every `sendToX` becomes a POST
to `/model/route` with `{ model, text }`.

**Backend contract:**
```
POST /model/route
Headers: X-Session-ID: <token>
Body:    { model: ModelId, text: string }
Returns: RouterResult (see phone/lib/modelRouter.ts)
```

Backend holds:
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`,
  `XAI_API_KEY`, `MICROSOFT_GRAPH_*` in Cloud Run env vars (or Secret
  Manager).
- Per-user rate limiting keyed off `X-Session-ID`.
- Cost accounting (decisions about which tier gets which models).

**Cutover steps:**
1. Add the route + provider switch in `app.py`.
2. Move keys to Secret Manager.
3. Set `CLOUD_FEATURES.modelProxy = true`.
4. The phone bundle ships zero keys.

---

## 3. Cloud Vault Sync

**Goal:** mirror local vault items to a per-user server store so a user
sees the same vault on phone + web.

**Why third:** introduces persistent per-user state. Needs auth + GCS
or Firestore + a sync protocol.

**Frontend integration point:** `phone/lib/vault.ts`. When
`isCloudEnabled('vaultSync')` is true, `saveNote/saveSession` push
after writing locally (write-through), and `listNotes/listSessions`
periodically pull deltas (last-write-wins or vector-clock).

**Backend contract:**
```
POST /vault/push
Headers: X-Session-ID: <token>
Body:    VaultNote | VaultSession (full object)
Returns: { ok: true, id, serverTime }

GET  /vault/pull?since=<iso>
Headers: X-Session-ID: <token>
Returns: { items: (VaultNote | VaultSession)[], serverTime }
```

Storage:
- Firestore collection `vault/{user}/items/{id}` works out of the box.
- Or GCS bucket `clarityos-vault/{user}/{id}.json`.

**Open questions** (resolve before shipping):
- Conflict resolution: last-write-wins or merge?
- Delete semantics: tombstones or soft-delete?
- Encryption: server-side only, or client-side AES-GCM with the key
  never crossing the wire? (The web Plans page already advertises the
  latter.)

**Cutover steps:**
1. Resolve open questions above.
2. Add routes + Firestore collection in `app.py`.
3. Set `CLOUD_FEATURES.vaultSync = true`.
4. First sync after enabling pushes the entire local vault — be sure
   the local index has stable IDs (it does — see `newId()` in vault.ts).

---

## 4. Cloud Continuity

**Goal:** detect interrupted sessions and resume options across devices.

**Why fourth:** depends on (3) — continuity surfaces vault items + last
threads, which only make sense if those are server-side.

**Frontend integration point:** `phone/lib/continuity.ts`. When
`isCloudEnabled('continuity')` is true, `getResumeOptions()` queries
the server in addition to local storage and merges results.

**Backend contract:**
```
POST /continuity/mark
Headers: X-Session-ID: <token>
Body:    { threadId: string, deviceId: string }

GET  /continuity/options
Headers: X-Session-ID: <token>
Returns: ResumeOption[]  (see phone/lib/continuity.ts)
```

Storage:
- Firestore document `continuity/{user}` with shape:
  ```
  { interrupted: { threadId, deviceId, at }?, lastThread: { ... }? }
  ```

**Cutover steps:**
1. Ship vault sync (3) first.
2. Add routes + Firestore doc in `app.py`.
3. Set `CLOUD_FEATURES.continuity = true`.
4. Boot check in `_layout.tsx` already calls `getResumeOptions()`; no
   chat or screen changes needed.

---

## Rollback

Every flag is independent. Setting it to `false` returns the matching
subsystem to local-only behavior with no data loss (local-first writes
are always the source of truth; cloud is a mirror). Leave all flags
`false` to ship today as a fully-local app.

---

## Status (this commit)

| Layer | Frontend ready | Backend ready | Flag |
|---|---|---|---|
| Clarity Engine | yes | **no** | `clarityEngine: false` |
| Model Proxy | yes | **no** | `modelProxy: false` |
| Vault Sync | yes | **no** | `vaultSync: false` |
| Continuity | yes | **no** | `continuity: false` |

The frontend is "ready" in the sense that the integration points exist
and the data shapes are nailed down. Backend work is gated on explicit
go-ahead per route, since adding routes contradicts the prior "backend
is stable infrastructure" directive.
