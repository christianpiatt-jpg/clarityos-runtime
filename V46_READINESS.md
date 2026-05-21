# V46 Readiness — Memory Vault v1.0 + Cross-Surface Continuity

Status: ✅ Ready
Backend version: `4.2`
Vault version: `memory_vault.v46.1`
Operator state: `operator_state.v46.1`
Build: `20260507620000`

---

## What v46 ships

A first-class encrypted local key/value store that becomes the single
persistence layer for everything operator-shaped: operator state,
ELINS history, #G history, model preferences, local-model usage,
plus two new namespaces — **notes** + **embeddings** — that user
surfaces can write into directly.

The vault encrypts every value at rest using a per-user key derived
via PBKDF2 from a process-wide secret + the user_id. The encryption
construction is HMAC-SHA256 in CTR mode (PRF stream cipher) with an
encrypt-then-MAC HMAC-SHA256 over (nonce || ciphertext) — pure stdlib,
so no extra deps. A different secret produces a different key, so
on-disk data is unreadable across rotation events. Three storage
backends are available: **mock** (in-memory, default for tests), **fs**
(one JSON file per user), **sqlite** (single DB).

`operator_state.py` becomes a thin wrapper over `memory_vault`:

* The `operator_state.*` namespace holds scalar/dict fields.
* Each ELINS interaction is its own vault entry under `elins.{ts_ms}_{seq}`.
* Each #G run is its own vault entry under `g_runs.{ts_ms}_{seq}`.
* The history cap (`HISTORY_MAX = 200`) is enforced via `_prune_history`
  on every write.
* `migrate_operator_state_to_vault(user_id, legacy_state)` flips a
  v45-style snapshot into the v46 schema for one-shot upgrades.

The intelligence kernel surfaces the vault on both the founder side
(`kernel_status.vault`) and the user side (`kernel_view_for_user.vault_keys`
+ `notes_count` + `embeddings_count`). The settings UI on web + phone
exposes notes / embeddings management; the founder console gets a
`Vault Inspector` panel that walks every user, lists their keys grouped
by namespace, and reads decrypted item values on demand.

---

## Files added / changed

### New
- `memory_vault.py` — encrypted KV store with mock/fs/sqlite backends,
  HMAC-CTR + HMAC-SHA256 envelope, namespace validation, status +
  founder-inspector helpers.
- `web/src/components/settings/MemoryVaultPanel.tsx` — Account-page
  panel: status header + notes editor + embeddings list.
- `web/src/components/founder/vault/FounderVaultInspector.tsx` —
  3-column inspector (users → keys-by-namespace → item value).
- `phone/app/memory_vault.tsx` — notes editor + counts header.
- `phone/app/memory_vault_embeddings.tsx` — embeddings list/delete.
- `tests/test_v46_memory_vault.py` — 45 tests.
- `V46_READINESS.md` (this file).

### Modified
- `operator_state.py` — full rewrite onto `memory_vault`.
  - `STATE_VERSION` → `operator_state.v46.1`.
  - All `operator_state.*` fields persist as individual vault keys.
  - `record_elins_interaction` / `record_g_run` write `elins.*` /
    `g_runs.*` entries one-per-call (with monotonic seq counter).
  - `_prune_history` enforces `HISTORY_MAX` after each write.
  - New `migrate_operator_state_to_vault(user_id, legacy_state)`.
  - Removed legacy `_MEM_STATE` / `_save` / `_load` / `_normalise`.
- `intelligence_kernel.py`:
  - Imports `memory_vault`.
  - `kernel_status()` adds a `vault` block (enabled / backend /
    encrypted / keys / users / namespaces / version).
  - `kernel_view_for_user()` adds `vault_keys`, `notes_count`,
    `embeddings_count`.
- `app.py`:
  - Imports `memory_vault`.
  - 9 new endpoints:
    - `GET /me/vault/status` — caller-scoped global + user counts
    - `GET /me/vault/notes` — list notes
    - `POST /me/vault/notes` — create/replace note (key + text)
    - `POST /me/vault/notes/delete` — delete note
    - `GET /me/vault/embeddings` — list (key + dim only)
    - `POST /me/vault/embeddings` — store vector
    - `POST /me/vault/embeddings/delete` — delete vector
    - `GET /founder/vault/users` — list users with vault rows
    - `GET /founder/vault/{user_id}/keys` — keys grouped by namespace
    - `GET /founder/vault/{user_id}/item/{key}` — decrypted value
  - `memory_vault` capability advertised on `/me`.
  - Backend version `4.2`; root listing extended.
  - `/health` reports `version: 4.2`.
- `web/src/lib/api.ts` — V46 types + helpers.
- `web/src/routes/Account.tsx` — embeds `<MemoryVaultPanel />`.
- `web/src/components/founder/FounderDashboard.tsx` — embeds
  `<FounderVaultInspector />`.
- `phone/lib/api.ts` — V46 types + helpers.
- `phone/app/_layout.tsx` — register `memory_vault` +
  `memory_vault_embeddings` stack screens.
- `phone/app/settings.tsx` — link to `/memory_vault`.
- `tests/conftest.py` — reset hook for `memory_vault._reset_for_tests`.
- `tests/test_v28_endpoints.py` — health version `4.2`.
- `tests/test_v45_local_model.py` — version assertion loosened to `4.*`.
- `tests/test_v43_ux_and_analytics.py` — fixture writes via
  `memory_vault.vault_put` / `migrate_operator_state_to_vault`
  (old `operator_state._save` private API is gone).
- `BUILD_VERSION` — `20260507620000`.

---

## Public API

```python
# memory_vault
VAULT_VERSION = "memory_vault.v46.1"
ALLOWED_NAMESPACES = (
    "operator_state", "elins", "g_runs", "preferences",
    "local_model", "notes", "embeddings",
)

vault_init(user_id) -> None
vault_put(user_id, key, value) -> None
vault_get(user_id, key, default=None) -> Any
vault_list(user_id) -> dict[str, Any]
vault_delete(user_id, key) -> None
vault_clear(user_id) -> None

vault_status() -> dict
vault_known_users() -> list[str]
vault_keys_for_user(user_id) -> list[str]
vault_count_for_user(user_id, namespace=None) -> int
namespace_of(key) -> str
```

```python
# operator_state additions
STATE_VERSION = "operator_state.v46.1"
migrate_operator_state_to_vault(user_id, legacy_state) -> dict
```

### Storage rules

- Default backend: **mock** (in-memory) when `CLARITYOS_BACKEND=memory`
  (test default); otherwise **fs**. Override via
  `CLARITYOS_VAULT_BACKEND ∈ {mock, fs, sqlite}`.
- fs path: `CLARITYOS_VAULT_DIR` (defaults to `~/.clarityos/vault`).
- sqlite path: `CLARITYOS_VAULT_DB` (defaults to `~/.clarityos/vault.sqlite3`).
- Encryption: always on. Set `CLARITYOS_VAULT_PLAINTEXT=1` only for
  debugging — the on-disk envelope still tags itself.
- Per-user key derivation: PBKDF2-SHA256(secret, "clarityos:" + user_id,
  iterations) → 32-byte key. Iterations defaults to 100k; override via
  `CLARITYOS_VAULT_PBKDF2`.
- Per-write nonce: 16 random bytes from `os.urandom`.
- Authentication: HMAC-SHA256(key, nonce || ciphertext) → 32-byte tag.
  Decrypt fails (raises `ValueError`) if the tag doesn't match.

### Namespace contract

The first segment of a key (everything before the first `.`) must be
in `ALLOWED_NAMESPACES`. Bare namespace keys (`"notes."`, `"elins"`)
are rejected. `/`, `\\`, and null bytes are rejected. Keys are capped
at 256 chars.

---

## API surface

### `GET /me/vault/status` (auth)
```jsonc
{
  "ok": true,
  "global": {
    "version": "memory_vault.v46.1",
    "enabled": true, "backend": "mock", "encrypted": true,
    "scheme": "hmac-ctr+sha256-mac", "pbkdf2_iter": 100000,
    "namespaces": ["operator_state", "elins", "g_runs", ...],
    "users": 3, "keys": 47
  },
  "user": {
    "user_id": "alice",
    "vault_keys": 12,
    "notes_count": 2, "embeddings_count": 1,
    "operator_state_count": 5, "elins_count": 3, "g_runs_count": 1
  }
}
```

### `GET /me/vault/notes` (auth)
```jsonc
{ "ok": true, "notes": [{"key": "team_brief", "text": "..."}], "count": 1 }
```

### `POST /me/vault/notes` (auth)
```jsonc
{ "key": "team_brief", "text": "weekly notes" }
```
- Sub-key may not contain `.`, `/`, `\\`, or null bytes.
- Sub-key length ≤ 128.
- Text length ≤ 64 KB.

### `POST /me/vault/notes/delete` (auth)
```jsonc
{ "key": "team_brief" }
```

### `GET /me/vault/embeddings` (auth)
Returns `[{key, dim}]` — the vector itself is not echoed.

### `POST /me/vault/embeddings` (auth)
```jsonc
{ "key": "scen_42", "vector": [0.1, 0.2, ...] }
```
- Vector dim ≤ 4096.

### `POST /me/vault/embeddings/delete` (auth)
```jsonc
{ "key": "scen_42" }
```

### `GET /founder/vault/users` (founder)
```jsonc
{ "ok": true, "users": [{"user_id": "alice", "keys": 12}, ...], "count": 3 }
```

### `GET /founder/vault/{user_id}/keys` (founder)
```jsonc
{
  "ok": true, "user_id": "alice", "count": 12,
  "keys": ["elins.123_001", "notes.team_brief", ...],
  "by_namespace": {
    "elins": {"count": 3, "keys": [...]},
    "notes": {"count": 2, "keys": [...]}
  }
}
```

### `GET /founder/vault/{user_id}/item/{key:path}` (founder)
Returns decrypted value or `{"ok": false, "error": "not_found"}`.

### `/me` additions
```jsonc
"intelligence_kernel": {
  ...,
  "vault_keys":       12,
  "notes_count":      2,
  "embeddings_count": 1
}
"capabilities": [..., {"id": "memory_vault", "label": "Memory Vault", "route": "/me/vault/status"}]
```

### `/founder/intelligence/kernel/status` additions
```jsonc
{
  "vault": {
    "enabled": true, "backend": "mock", "encrypted": true,
    "keys": 47, "users": 3,
    "namespaces": [...],
    "version": "memory_vault.v46.1"
  }
}
```

---

## UI

### Web
- **Account → Memory Vault** — status panel (counts), inline note
  editor (key + textarea + save), notes list with edit/delete actions,
  embeddings list with dim + delete.
- **Founder console → Vault Inspector** — 3-column layout: users
  (with key counts) → keys grouped by namespace → item view (JSON pretty
  print, decrypted server-side).

### Phone
- **`memory_vault.tsx`** — counts card + compose card + notes list.
  "Embeddings →" link in the notes header navigates to the
  embeddings screen.
- **`memory_vault_embeddings.tsx`** — list view with dim + delete.
- **`settings.tsx`** gets a "Memory Vault" entry.

---

## Tests

```
tests/test_v46_memory_vault.py — 45 tests, all pass
Full suite — 633 passed, 0 failed
```

Coverage:
- vault_init / put / get / list / delete / clear round-trips +
  defaults + idempotent delete.
- Namespace validation: unknown prefix rejected, bare namespace key
  rejected, path separators rejected; `namespace_of()` extraction.
- Encryption: ciphertext doesn't contain plaintext; round-trip works;
  rotated secret breaks decrypt (key isolation); same plaintext for
  two users produces different ciphertext envelopes.
- vault_status default shape; vault_known_users lists users with
  entries; vault_count_for_user filters by namespace.
- fs backend persists across `_reset_for_tests`; sqlite backend
  round-trip.
- operator_state default shape unchanged; ELINS / #G runs persist as
  individual vault entries; HISTORY_MAX still capped at 200; raw-text
  rejection works; preferred_model + local_model_usage_count + record_model_used
  all work via the vault; migration helper round-trips a legacy snapshot.
- kernel_status carries `vault` block; kernel_view_for_user exposes
  `vault_keys` / `notes_count` / `embeddings_count`.
- Endpoints: /me/vault/status shape; notes round-trip + bad-key 400;
  embeddings round-trip + dim cap; founder/vault/users founder gate;
  founder/vault/{user}/keys namespace grouping; founder/vault/{user}/item
  decrypted value + 404 path; capability advertised; /health version 4.2.
- Continuity: `run_ELINS` writes a vault `elins.*` entry;
  `run_G` writes a `g_runs.*` entry.

All tests run with the mock backend + real encryption (no plaintext
mode in CI). fs + sqlite paths use `tmp_path` so tests stay isolated.

---

## Notes / follow-ups

- The vault uses HMAC-CTR + HMAC-SHA256 because `cryptography` isn't
  in `requirements.txt`. Adding `cryptography` would let us swap to
  Fernet without changing the on-disk envelope name (the scheme byte
  is reserved for future versions: `0x00` = plain, `0x01` = HMAC-CTR,
  future: `0x02` = Fernet).
- `CLARITYOS_VAULT_SECRET` MUST be set in every environment — `_secret()`
  raises `RuntimeError` if it is missing or empty. There is no built-in
  default key. Production mounts a 32-byte random secret from Google
  Secret Manager (secret name `CLARITYOS_VAULT_SECRET`); the pytest suite
  pins a fixed throwaway value in `tests/conftest.py`. Rotating the secret
  without a migration plan breaks decryption for every existing user — the
  vault data must be cleared (or re-encrypted) whenever the key changes.
- The fs backend writes one JSON file per user; on a Cloud Run
  deployment the filesystem is ephemeral, so production should use
  the sqlite backend with a persistent volume, or graduate to a
  Firestore-backed implementation (the abstraction is ready — add a
  `_firestore_load_user` / `_firestore_save_user` pair next to the
  sqlite ones).
- The ELINS / #G history is now an individual-entry append, so
  HISTORY_MAX prunes via `vault_delete` rather than slicing a list.
  This keeps writes O(1) but reads still walk every vault entry —
  fine at the current scale, swap to a per-user index entry if /me
  starts taking measurable time.
- Per-user encryption keys are derived once and cached for the
  process lifetime; `_reset_for_tests` clears the cache between tests.
- Pre-v46 surfaces are unchanged. Older clients that ignore the new
  `vault_keys` / `notes_count` / `embeddings_count` fields on /me
  continue to work.
