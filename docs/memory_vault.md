# Runtime — memory_vault.py

## Purpose

`memory_vault.py` (v46+, `VAULT_VERSION = "memory_vault.v46.1"`) is the
**per-user encrypted local key/value persistence layer**. The single
persistence layer for operator-state-like data that should stay close
to the user but never end up in unencrypted parts of the broader
datastore.

Four storage backends, one envelope format, one global lock. The
deepest leaf in the runtime dependency graph — **zero internal
imports** (stdlib + optional lazy `google.cloud.firestore`).

### Core invariants

1. **Master secret is mandatory** — `CLARITYOS_VAULT_SECRET` missing or empty → `RuntimeError`. No default key.
2. **Per-user key isolation** — PBKDF2 with salt `b"clarityos:" + user_id`.
3. **11-entry namespace allow-list** — keys outside the list are rejected.
4. **Vault key shape constraints** — no `/`, no null bytes, ≤ 256 chars, namespace prefix required.
5. **Encrypt-then-MAC** — HMAC-SHA256 over `nonce ‖ ciphertext` verified before decrypt.
6. **Atomic fs writes** — tempfile + `os.replace`.
7. **Single global RLock** — guards all read/write paths.
8. **Encryption ON by default** — opt-out via `CLARITYOS_VAULT_PLAINTEXT`.
9. **`vault_list` is tolerant, `vault_get` is strict** — intentional asymmetry.

## Status

| File | Status | Reason |
|---|---|---|
| `memory_vault.py` | **CURRENT** | 751 lines · 10 public functions · 20 importers (8 production + 12 tests) |

## Implementation location

- **Source:** `memory_vault.py` (751 lines).
- **Stdlib only:** `base64`, `hashlib`, `hmac`, `json`, `logging`, `os`, `sqlite3`, `threading`, `time`, `typing`.
- **Lazy optional:** `google.cloud.firestore` (only when `_backend() == "firestore"`).

## Backend dispatch

### `_backend() -> str` (line 118) — precedence

1. `CLARITYOS_VAULT_BACKEND` if set + valid (`mock` / `fs` / `sqlite` / `firestore`).
2. `mock` when `CLARITYOS_BACKEND=memory` (test default).
3. `fs` otherwise (production default for local deployments).

### Four backends

| Backend | Storage |
|---|---|
| `mock` | In-process dict (`_MEM_STORE: dict[user_id, dict[key, {v, ts}]]`) |
| `fs` | One JSON file per user under `_vault_dir()` (env `CLARITYOS_VAULT_DIR`, default `~/.clarityos/vault`) |
| `sqlite` | Single DB at `_sqlite_path()` (env `CLARITYOS_VAULT_DB`, default `~/.clarityos/vault.sqlite3`). Schema: `vault_entries(user_id TEXT, key TEXT, value TEXT, ts REAL, PRIMARY KEY (user_id, key))` |
| `firestore` | One document per entry under `memory_vault/{user_id}/entries/{vault_key}` + per-user marker doc. Batched commits under 450-op cap |

### Dispatch entrypoints (3)

| Function | Purpose |
|---|---|
| `_load_user(user_id) -> dict` | Routes to `_mem_load_user` / `_sql_load_user` / `_fire_load_user` / `_fs_load_user` |
| `_save_user(user_id, entries)` | Routes to the matching `_*_save_user` |
| `_known_users() -> list[str]` | Routes to the matching `_*_known_users` |

`_backend()` is **read on every dispatch call** — env-var changes
mid-process are picked up immediately (no caching).

### `fs` backend specifics

- `_fs_path_for(user_id)` sanitises `user_id` (replaces `/`, `\`).
- `_fs_save_user` is **atomic** — writes to `path + ".tmp"`, then `os.replace`.
- Empty entries → file is removed.

### `sqlite` backend specifics

- `_SQLITE_CONN` cached process-globally with `check_same_thread=False`.
- `_SQLITE_PATH_CACHED` invalidates the cached connection if env var changes mid-process.
- `_sql_save_user` does `DELETE WHERE user_id` then `executemany INSERT` (transactional via `with conn:`).

### `firestore` backend specifics

- Layout: `{coll}/{user_id}/entries/{vault_key}` + per-user marker doc.
- Per-entry docs sidestep Firestore's 1 MiB per-doc limit.
- `_fire_save_user` **diffs** against current state — an ordinary `vault_put` commits a single document write.
- `_FIRE_BATCH_LIMIT = 450` (under SDK's 500-op cap).
- Dedicated collection name `memory_vault` (distinct from `vault_store.py`'s legacy `"vault"` collection).

## Encryption scheme

### Envelope format

```
b64( scheme(1) ‖ nonce(16) ‖ ciphertext(N) ‖ mac(32) )

scheme 0x00 → plaintext  (only when CLARITYOS_VAULT_PLAINTEXT is set)
scheme 0x01 → HMAC-CTR + HMAC-SHA256 encrypt-then-MAC
```

### `_encrypt_value(user_id, plaintext) -> str` (line 263)

```python
key = _derive_key(user_id)
nonce = os.urandom(16)
ks = _ctr_keystream(key, nonce, len(plaintext))
ct = bytes(p ^ k for p, k in zip(plaintext, ks))
mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()
return base64.b64encode(b"\x01" + nonce + ct + mac).decode("ascii")
```

**Non-deterministic by design** — fresh nonce per call. Same plaintext
+ same user → **different ciphertext every call** (semantic security
under CPA).

### `_decrypt_value(user_id, envelope_b64) -> bytes` (line 281)

```python
raw = base64.b64decode(envelope_b64)
scheme = raw[0]
if scheme == 0x01:
    nonce = body[:16]
    mac = body[-32:]
    ct = body[16:-32]
    key = _derive_key(user_id)
    expected = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, mac):
        raise ValueError("vault MAC mismatch — wrong key or tampered data")
    ks = _ctr_keystream(key, nonce, len(ct))
    return bytes(c ^ k for c, k in zip(ct, ks))
```

**Deterministic** — same envelope + same user key → same plaintext.
`hmac.compare_digest` resists timing attacks.

### CTR-mode keystream

```python
def _ctr_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """HMAC-SHA256(key, nonce || counter) PRF in CTR mode."""
```

A HMAC with a fixed key is a secure PRF, so concatenated outputs make a
stream cipher. Stdlib-only construction. Documented intent (line 25–27):
*"if `cryptography` lands in the environment in the future we can swap
for Fernet without changing the on-disk envelope name."*

### `_is_encrypted()` (line 149)

Returns True unless `CLARITYOS_VAULT_PLAINTEXT in {"1", "true", "yes"}`.

**Privacy gap (PASS‑3B P5):** opt-out exists. Documented "for debugging
only — tests still run with encryption ON to verify the round-trip
works."

## Key derivation

### `_derive_key(user_id) -> bytes` (line 231)

```python
key = hashlib.pbkdf2_hmac(
    "sha256",
    _secret(),
    ("clarityos:" + user_id).encode("utf-8"),
    _pbkdf2_iters(),     # default 100_000
    32,
)
```

**Per-user key isolation.** Two users with the same master secret get
two completely independent 32-byte keys. Cross-user decryption fails
the MAC check.

### `_KEY_CACHE: dict[str, bytes]` (line 228)

Derivation is **cached for the process lifetime.** PBKDF2 is
intentionally slow (~100k iterations); caching the result avoids
paying the cost on every read/write.

**Wiped only by `_reset_for_tests`.** A memory dump would reveal all
currently-cached per-user keys.

### `_secret() -> bytes` (line 167)

Reads `CLARITYOS_VAULT_SECRET`. **Mandatory** — raises `RuntimeError`
if missing or empty.

```python
raw = (os.environ.get("CLARITYOS_VAULT_SECRET") or "").strip()
if not raw:
    raise RuntimeError(
        "CLARITYOS_VAULT_SECRET is not set. The memory vault requires a "
        "master secret in the environment (mounted from Google Secret "
        "Manager in production). Refusing to fall back to a default key."
    )
```

**No default fallback** — a misconfigured deployment fails loudly
instead of silently encrypting every user's data under a known key.

### `_pbkdf2_iters() -> int` (line 157)

Env `CLARITYOS_VAULT_PBKDF2`; floor 1000; default
`DEFAULT_PBKDF2_ITERATIONS = 100_000`. Tuned low enough for tests not
to drag, high enough to be meaningful.

## Namespace rules

### `ALLOWED_NAMESPACES` (11-entry tuple)

```python
ALLOWED_NAMESPACES: tuple = (
    "operator_state",
    "elins",
    "g_runs",
    "preferences",
    "local_model",
    "notes",
    "embeddings",
    "threads",                # v47 — threaded interaction substrate
    "projects",               # v51 — project layer
    "regression_chains",      # v77 — Regression-First chain persistence
    "regression_packets",     # v82 — original packet history
)
```

Each new namespace was added by a specific batch (v46 base set; v47
threads; v51 projects; v77 regression_chains; v82 regression_packets —
documented inline at lines 76–97).

### `namespace_of(key) -> str` (line 196)

Returns the leading segment of `key` (everything before the first
`.`). Used by both the validator and the founder UI to bucket keys.

### `_validate_key(key) -> str` (line 205)

Rejects any key:
- Non-string or empty.
- Containing `/` or null byte.
- Length > 256 chars.
- Namespace (leading segment) not in `ALLOWED_NAMESPACES`.
- Namespace-only (e.g. `"elins"` or `"elins."` with nothing after).

## Public API

| Function | Line | Purpose |
|---|---|---|
| `vault_init(user_id)` | 589 | Idempotent; ensures per-user storage scaffolding; pre-warms `_KEY_CACHE` |
| `vault_put(user_id, key, value)` | 607 | Store JSON-serialisable value; encrypts at rest |
| `vault_get(user_id, key, default=None)` | 625 | Decrypt + deserialise; raises on integrity failure |
| `vault_list(user_id) -> dict` | 644 | Return all entries as `{key: decrypted_value}`; **logs + skips per-key decrypt failures** |
| `vault_delete(user_id, key)` | 661 | No-op when key absent |
| `vault_clear(user_id)` | 672 | Drop every entry; does NOT remove per-user salt |
| `vault_keys_for_user(user_id) -> list[str]` | 684 | Sorted list of keys |
| `vault_count_for_user(user_id, namespace=None) -> int` | 690 | Cheap key count; optional namespace filter |
| `vault_known_users() -> list[str]` | 702 | Sorted list of user_ids with at least one row |
| `vault_status() -> dict` | 708 | Global config snapshot (version, backend, encrypted, namespaces, users, keys, scheme, pbkdf2_iter, fs_dir, sqlite_path) |
| `namespace_of(key) -> str` | 196 | Leading segment of a key |
| `_reset_for_tests()` | 736 | Wipes `_MEM_STORE`, `_KEY_CACHE`, closes `_SQLITE_CONN`, drops `_FIRE_CLIENT` |

### Module constants

| Name | Value |
|---|---|
| `VAULT_VERSION` | `"memory_vault.v46.1"` |
| `ALLOWED_NAMESPACES` | 11-entry tuple (above) |
| `DEFAULT_PBKDF2_ITERATIONS` | `100_000` |

## Module-level state

| Name | Type | Purpose |
|---|---|---|
| `_LOCK` | `threading.RLock` | Always-allocated at module load; guards every read/write path |
| `_MEM_STORE` | `dict[str, dict[str, dict]]` | mock backend storage |
| `_SQLITE_CONN` | `Optional[sqlite3.Connection]` | Cached sqlite handle |
| `_SQLITE_PATH_CACHED` | `Optional[str]` | Invalidates `_SQLITE_CONN` on env change |
| `_FIRE_CLIENT` | `Any` | Lazy firestore client |
| `_KEY_CACHE` | `dict[str, bytes]` | Per-user derived-key cache |

## State transitions

### Initialization (`vault_init`)

```
1. _validate_user(user_id)
2. With _LOCK:
   a. _load_user(user_id) → check existing entries
   b. If empty: ensure fs dir / sqlite conn exists (mock stays empty)
3. _derive_key(user_id) → pre-warm _KEY_CACHE (avoid PBKDF2 cost on first put)
```

### Put (`vault_put`)

```
1. _validate_user(user_id)
2. _validate_key(key)
3. json.dumps(value, default=str) → plaintext bytes  (raises on non-serialisable)
4. _encrypt_value(user_id, plaintext) → envelope_b64
5. With _LOCK:
   a. entries = _load_user(user_id)
   b. entries[key] = {"v": envelope, "ts": time.time()}
   c. _save_user(user_id, entries)
```

### Get (`vault_get`) — strict

```
1. Validate user_id + key
2. With _LOCK: entries = _load_user(user_id)
3. If key absent: return default
4. _decrypt_value → plaintext → json.loads
5. On integrity failure: logger.warning + RE-RAISE
```

### List (`vault_list`) — tolerant

```
1. Validate user_id
2. With _LOCK: entries = _load_user(user_id)
3. For each key:
   a. Try _decrypt_value + json.loads
   b. On exception: logger.warning + SKIP (do not raise)
4. Return {key: decrypted_value} dict (may exclude corrupted entries)
```

**Intentional asymmetry** — `vault_get` raises so callers can react;
`vault_list` skips so one bad record doesn't poison bulk reads.

### Clear

```
1. Validate user_id
2. With _LOCK: _save_user(user_id, {})
   → fs backend removes file
   → sqlite delete by user_id
   → firestore drops all entry docs + marker doc
3. Per-user salt NOT removed — re-using user_id reuses the same key
```

## Privacy / leak-prevention mechanisms

### Cryptographic
- PBKDF2 per-user key isolation.
- HMAC-CTR + HMAC-SHA256 encrypt-then-MAC.
- `hmac.compare_digest` for MAC verification (timing-attack-resistant).
- Mandatory master secret (no default fallback).
- `os.urandom(16)` for fresh nonce per encrypt.

### Application-layer
- Namespace allow-list (11 entries).
- Key shape constraints (no `/`, no null bytes, ≤ 256 chars).
- JSON-serialisable values only.
- Atomic fs writes (tempfile + `os.replace`).
- `vault_list` tolerant vs `vault_get` strict asymmetry.

### State-leak mitigation
- `_LOCK` (RLock) serialises all read/write paths.
- `_KEY_CACHE` wiped by `_reset_for_tests`.
- No raw plaintext in any log line.
- `vault_status()` returns metadata only (counts, paths, scheme name).

### Known gaps (PASS‑3B)
- **No per-user key rotation primitive.** `vault_clear` doesn't invalidate the per-user salt; rotating one user's key requires rotating the master secret (which re-keys ALL users).
- **`_KEY_CACHE` persists across the process lifetime.** Wiped only by `_reset_for_tests` or process restart.
- **Encryption opt-out exists** via `CLARITYOS_VAULT_PLAINTEXT`. Documented "for debugging only."

## Invariants

### Configuration
1. Master secret is mandatory (no default).
2. Encryption ON by default.
3. `_backend()` is read on every dispatch (env changes picked up immediately).

### Cryptographic
4. PBKDF2 per-user key isolation via salt `b"clarityos:" + user_id`.
5. Encrypt-then-MAC; MAC verified before decrypt.
6. `hmac.compare_digest` for timing-attack resistance.
7. Encryption is non-deterministic (fresh nonce per call).
8. Decryption is deterministic.

### Storage
9. Namespace allow-list (11 entries) enforced at every `vault_put` / `vault_get` / `vault_delete`.
10. Vault key shape constraints enforced.
11. Atomic fs writes via tempfile + `os.replace`.
12. Firestore per-entry-doc + per-user-marker-doc layout.
13. Firestore batch limit 450 (under SDK's 500-op cap).

### Concurrency
14. Single `_LOCK` (RLock) guards all read/write paths.
15. Re-entrant lock allows nested calls within the same thread.

### API asymmetry
16. `vault_list` tolerates per-key decrypt failures (logs + skips).
17. `vault_get` raises on integrity failure.

## Integration points

### Imports (production)

**Zero internal imports.** Stdlib only + lazy `google.cloud.firestore`
(only when `_backend() == "firestore"`).

### Importers (20 total — 8 production + 12 tests)

- **Production:** `operator_state.py`, `intelligence_kernel.py`, `threads_vault.py`, `projects_vault.py`, `problem_solver/chain_store.py`, `app.py`, `acceptance_dashboard.py`, `runtime_intelligence_wiring.py` (transitive).
- **Tests:** `test_v46_memory_vault.py` (primary), `test_v43_ux_and_analytics.py`, `test_v47_threads.py`, `test_v80_regression_first_packet.py`, `test_v82_regression_first_replay.py`, `test_regression_first_vault_timeline.py`, `test_el_ins_*` (5 files), `tests/conftest.py`.
- **Docs:** `docs/operator_state.md` (string match, not a code import).

### Deepest leaf

`memory_vault` depends on **no other ClarityOS module**. Everything
upstream (operator_state, threads_vault, projects_vault, kernel) flows
through it without back-reference. Zero circular dependency risk.

## Non-goals

`memory_vault` is **not**:

- a database engine — uses sqlite/firestore as backends but doesn't expose SQL.
- a multi-tenant isolator at the application level — per-user isolation is cryptographic, not access-control.
- a key management service — no `rotate_key`, no key escrow, no audit log of key usage.
- a session store — sessions live in `sessions_store`.
- a backup system — `vault_clear` doesn't archive; deletion is destructive.
- a content sanitiser — encrypts whatever it's given. Content filtering is upstream (operator_state).
- a transactional store — multi-key atomic writes are not supported; each `vault_put` is an independent transaction at the backend level.

## Fiction removed

- **No default master secret** — `_secret()` raises `RuntimeError` on missing env var. No fallback.
- **No key rotation primitive** — `vault_clear` does NOT invalidate the per-user salt.
- **No external cryptography library** — pure stdlib (`hashlib`, `hmac`, `os.urandom`, `base64`). The `cryptography` package is documented as a future swap, not currently used.
- **No per-user file isolation in mock/sqlite backends** — they share a single process structure / DB, with per-user namespacing inside.
- **No deterministic encryption** — fresh nonce per call is required for semantic security.
- **No transactional multi-key writes** — each `vault_put` is independent.

Only the behaviour described in this document is present in the code;
the verified surface is locked by 12 test files.
