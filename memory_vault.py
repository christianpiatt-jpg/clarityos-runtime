"""
v46 — Memory Vault v1.0: per-user encrypted local key/value storage.

The vault is the single persistence layer for operator-state-like data
that should stay close to the user but never end up in the unencrypted
parts of the broader datastore. v46 migrates ``operator_state`` onto
the vault, splits ELINS / #G interactions into individually-keyed
entries, and opens up two new namespaces (``notes.*`` + ``embeddings.*``)
for user content.

Storage backends:
    * ``mock``      — in-memory dict-of-dicts (default when CLARITYOS_BACKEND=memory)
    * ``fs``        — one JSON file per user under CLARITYOS_VAULT_DIR
    * ``sqlite``    — single SQLite DB at CLARITYOS_VAULT_DB
    * ``firestore`` — one Firestore document per entry; the production
                      backend, durable across Cloud Run cold starts and
                      redeploys (CLARITYOS_VAULT_BACKEND=firestore)

Encryption:
    Each value is encrypted at rest with a per-user key derived via
    PBKDF2(secret, b"clarityos:" + user_id, 100k iters) → 32 bytes. The
    encryption is HMAC-SHA256 in CTR mode (PRF stream cipher) with an
    encrypt-then-MAC HMAC-SHA256 over (nonce || ciphertext). The
    construction is fully stdlib so the runtime has no extra deps; if
    ``cryptography`` lands in the environment in the future we can swap
    for Fernet without changing the on-disk envelope name. The HMAC tag
    catches both tampering and wrong-key reads.

Public API:
    VAULT_VERSION
    ALLOWED_NAMESPACES                       # ("operator_state", "elins", ...)

    vault_init(user_id) -> None              # idempotent; ensures per-user storage
    vault_put(user_id, key, value) -> None
    vault_get(user_id, key, default=None) -> value
    vault_list(user_id) -> dict              # {key: value} for all entries
    vault_delete(user_id, key) -> None
    vault_clear(user_id) -> None

    vault_status() -> dict                    # global config snapshot for kernel_status
    vault_known_users() -> list[str]          # users that have at least one entry
    vault_keys_for_user(user_id) -> list[str]
    vault_count_for_user(user_id, namespace=None) -> int
    namespace_of(key) -> str

    _reset_for_tests() -> None                # wipes mock store
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
from typing import Any, Optional

import runtime_privacy

logger = logging.getLogger("clarityos.memory_vault")

VAULT_VERSION: str = "memory_vault.v46.1"

# Namespaces the vault accepts. The first segment of a key (everything
# before the first '.') must match one of these. Keeps unstructured
# keys from leaking in as folks evolve the schema.
ALLOWED_NAMESPACES: tuple = (
    "operator_state",
    "elins",
    "g_runs",
    "preferences",
    "local_model",
    "notes",
    "embeddings",
    # v47 — threaded interaction substrate. Sub-namespaces by convention:
    # ``threads.meta.{tid}``, ``threads.messages.{tid}.{ts_ms}_{seq}``,
    # ``threads.embeddings.{tid}.{...}`` (reserved, no logic yet).
    "threads",
    # v51 — project layer. Sub-namespaces by convention:
    # ``projects.{project_id}.meta``, ``projects.{project_id}.summary``,
    # ``projects.{project_id}.threads`` (denormalised list of thread_ids).
    "projects",
    # v77 — Regression-First chain persistence. Each chain is one
    # entry under ``regression_chains.{chain_id}``. The chain_id is a
    # canonical UUID4 (with dashes). Stored shape mirrors
    # ``problem_solver.RegressionChain`` exactly — no envelope/header,
    # the chain dict itself is the value.
    "regression_chains",
    # v82 — Original packet history. Each entry under
    # ``regression_packets.{chain_id}`` is the raw packet that
    # originated the chain. First packet wins (not overwritten on
    # repeated /packet calls for the same chain_id, which only
    # happens if someone manually triggers the replay endpoint —
    # see ``app.me_regression_first_packet`` for the
    # write-once enforcement).
    "regression_packets",
    # PASS-4 V2 — System-wide founder configuration that must
    # outlive a single process. The only key today is
    # ``founder_global.default_model`` (set via
    # /founder/models/override and consulted by model_router.
    # select_model). Stored under a synthetic user_id so the
    # existing per-user vault partitioning still applies; no per-user
    # data lives under this namespace.
    "founder_global",
)

# PBKDF2 iteration count. Tuned low enough that tests don't drag but
# high enough to be meaningful. Override via CLARITYOS_VAULT_PBKDF2.
DEFAULT_PBKDF2_ITERATIONS: int = 100_000


# ---------------------------------------------------------------------------
# Module state
# ---------------------------------------------------------------------------
_LOCK = threading.RLock()
_MEM_STORE: dict[str, dict[str, dict]] = {}    # user_id -> {key: {"v": ciphertext_b64, "ts": float}}
_SQLITE_CONN: Optional[sqlite3.Connection] = None
_SQLITE_PATH_CACHED: Optional[str] = None
_FIRE_CLIENT: Any = None                       # lazy google.cloud.firestore client (firestore backend)


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------
def _backend() -> str:
    """Resolve the storage backend.

    Precedence:
        1. ``CLARITYOS_VAULT_BACKEND`` if set + valid
        2. ``mock`` when ``CLARITYOS_BACKEND=memory`` (test default)
        3. ``fs`` otherwise
    """
    explicit = (os.environ.get("CLARITYOS_VAULT_BACKEND") or "").strip().lower()
    if explicit in ("mock", "fs", "sqlite", "firestore"):
        return explicit
    if (os.environ.get("CLARITYOS_BACKEND") or "memory").lower() == "memory":
        return "mock"
    return "fs"


def _vault_dir() -> str:
    """Directory for the ``fs`` backend. Defaults to ``~/.clarityos/vault``."""
    raw = (os.environ.get("CLARITYOS_VAULT_DIR") or "").strip()
    if raw:
        return raw
    return os.path.join(os.path.expanduser("~"), ".clarityos", "vault")


def _sqlite_path() -> str:
    raw = (os.environ.get("CLARITYOS_VAULT_DB") or "").strip()
    if raw:
        return raw
    return os.path.join(os.path.expanduser("~"), ".clarityos", "vault.sqlite3")


_PLAINTEXT_WARNING_EMITTED: bool = False


def _is_encrypted() -> bool:
    """Vault writes encrypt at rest unless explicitly disabled. The
    plaintext path exists for debugging only — tests still run with
    encryption ON to verify the round-trip works.

    PASS-4 FIX-P3 — The enablement check has been tightened to require
    the explicit string ``"true"`` (case-insensitive). The pre-fix
    check accepted any of ``"1" / "true" / "yes"``, which made
    accidental enablement easy (an env var set to a typo or
    placeholder could silently disable encryption). A one-time
    high-severity warning is logged the first time this function
    observes plaintext mode enabled in a given process.
    """
    global _PLAINTEXT_WARNING_EMITTED
    raw = (os.environ.get("CLARITYOS_VAULT_PLAINTEXT") or "").strip().lower()
    is_plaintext = (raw == "true")
    if is_plaintext and not _PLAINTEXT_WARNING_EMITTED:
        _PLAINTEXT_WARNING_EMITTED = True
        logger.warning(
            "memory_vault PLAINTEXT MODE ENABLED "
            "(CLARITYOS_VAULT_PLAINTEXT='true'): vault encryption is "
            "DISABLED. This mode is intended ONLY for local development "
            "and debugging — sensitive data at rest is NOT protected. "
            "Unset the variable or set it to 'false' in any non-dev "
            "environment.",
        )
    return not is_plaintext


def _pbkdf2_iters() -> int:
    raw = (os.environ.get("CLARITYOS_VAULT_PBKDF2") or "").strip()
    try:
        if raw:
            return max(1_000, int(raw))
    except ValueError:
        pass
    return DEFAULT_PBKDF2_ITERATIONS


def _secret() -> bytes:
    """Return the vault master secret from the environment.

    The secret is supplied via ``CLARITYOS_VAULT_SECRET`` — in production it
    is mounted from Google Secret Manager. There is deliberately no built-in
    default: a missing or empty secret is a hard error so a misconfigured
    deployment fails loudly instead of silently encrypting every user's data
    under a known, guessable key. The test harness sets the variable in
    ``tests/conftest.py``.
    """
    raw = (os.environ.get("CLARITYOS_VAULT_SECRET") or "").strip()
    if not raw:
        raise RuntimeError(
            "CLARITYOS_VAULT_SECRET is not set. The memory vault requires a "
            "master secret in the environment (mounted from Google Secret "
            "Manager in production). Refusing to fall back to a default key."
        )
    return raw.encode("utf-8")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _validate_user(user_id: Any) -> str:
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id must be a non-empty string")
    return user_id


def namespace_of(key: str) -> str:
    """Return the leading namespace segment of ``key``. Used by both
    the validator and the founder UI to bucket keys."""
    if not isinstance(key, str) or not key:
        return ""
    head, _sep, _rest = key.partition(".")
    return head


def _validate_key(key: Any) -> str:
    if not isinstance(key, str) or not key:
        raise ValueError("key must be a non-empty string")
    if "/" in key or "\x00" in key:
        raise ValueError("key may not contain '/' or null bytes")
    if len(key) > 256:
        raise ValueError("key length must be <= 256 chars")
    ns = namespace_of(key)
    if ns not in ALLOWED_NAMESPACES:
        raise ValueError(
            f"key namespace {ns!r} not in {list(ALLOWED_NAMESPACES)!r}",
        )
    # Disallow a namespace-only key like "elins." with nothing after it.
    if key == ns or key == ns + ".":
        raise ValueError(f"key must include a sub-key after the namespace ({ns!r})")
    return key


# ---------------------------------------------------------------------------
# Encryption helpers (HMAC-CTR + HMAC-SHA256 encrypt-then-MAC)
# ---------------------------------------------------------------------------
# Per-user key cache. Derivation runs PBKDF2 which is intentionally slow,
# so we cache derived keys. Wiped by ``_reset_for_tests``.
#
# PASS-4 FIX-H7 — Each cache entry is now ``(key_bytes, created_at)``
# and is treated as stale after ``_KEY_CACHE_TTL_SECONDS``. The
# encryption scheme and PBKDF2 parameters are unchanged; only the
# in-memory lifetime of a derived key is bounded, reducing the window
# during which a compromised process image would expose long-lived key
# material. ``_invalidate_key_cache_for_user`` provides explicit
# eviction for callers that know key material is about to change (e.g.
# master-secret rotation, user deletion).
_KEY_CACHE_TTL_SECONDS: float = 3600.0
_KEY_CACHE: dict[str, tuple[bytes, float]] = {}


def _derive_key(user_id: str) -> bytes:
    """Return the PBKDF2-derived key for ``user_id``, using the cache
    if present and not past its TTL. Otherwise re-derive (same PBKDF2
    parameters as the v46 baseline) and replace the cache entry.
    """
    cached = _KEY_CACHE.get(user_id)
    now = time.time()
    if cached is not None:
        key_bytes, created_at = cached
        if (now - created_at) < _KEY_CACHE_TTL_SECONDS:
            return key_bytes
        # Past TTL — fall through. The stale entry is overwritten
        # below; callers continue to receive a valid key.
    key = hashlib.pbkdf2_hmac(
        "sha256",
        _secret(),
        ("clarityos:" + user_id).encode("utf-8"),
        _pbkdf2_iters(),
        32,
    )
    _KEY_CACHE[user_id] = (key, now)
    return key


def _invalidate_key_cache_for_user(user_id: str) -> None:
    """PASS-4 FIX-H7 — Drop the cached PBKDF2-derived key for one user.

    Internal helper. Call sites that know a user's key material is
    about to change (master-secret rotation, user deletion, integrity
    failure on read) use this to force the next ``_derive_key`` to
    run the slow PBKDF2 path again. Idempotent — no-op when the user
    has no cached key.
    """
    if not isinstance(user_id, str) or not user_id:
        return
    with _LOCK:
        _KEY_CACHE.pop(user_id, None)


def _ctr_keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    """HMAC-SHA256(key, nonce || counter) PRF in CTR mode. Returns
    ``length`` bytes. Standard construction — a HMAC with a fixed key
    is a secure PRF, so concatenated outputs make a stream cipher."""
    out = bytearray()
    counter = 0
    while len(out) < length:
        block = hmac.new(
            key,
            nonce + counter.to_bytes(8, "big"),
            hashlib.sha256,
        ).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:length])


def _encrypt_value(user_id: str, plaintext: bytes) -> str:
    """Encrypt ``plaintext`` for ``user_id``. Returns a base64-encoded
    envelope: ``b64(scheme_byte || nonce(16) || ciphertext || mac(32))``.
    ``scheme_byte`` is 0x01 for HMAC-CTR (current default).

    When encryption is disabled the envelope is base64(0x00 || plaintext)
    so the on-disk format is still self-describing.
    """
    if not _is_encrypted():
        return base64.b64encode(b"\x00" + plaintext).decode("ascii")
    key = _derive_key(user_id)
    nonce = os.urandom(16)
    ks = _ctr_keystream(key, nonce, len(plaintext))
    ct = bytes(p ^ k for p, k in zip(plaintext, ks))
    mac = hmac.new(key, nonce + ct, hashlib.sha256).digest()
    return base64.b64encode(b"\x01" + nonce + ct + mac).decode("ascii")


def _decrypt_value(user_id: str, envelope_b64: str) -> bytes:
    raw = base64.b64decode(envelope_b64.encode("ascii"))
    if not raw:
        raise ValueError("empty vault envelope")
    scheme = raw[0]
    body = raw[1:]
    if scheme == 0x00:
        return body
    if scheme == 0x01:
        if len(body) < 16 + 32:
            raise ValueError("vault envelope truncated")
        nonce = body[:16]
        mac = body[-32:]
        ct = body[16:-32]
        key = _derive_key(user_id)
        expected = hmac.new(key, nonce + ct, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, mac):
            raise ValueError("vault MAC mismatch — wrong key or tampered data")
        ks = _ctr_keystream(key, nonce, len(ct))
        return bytes(c ^ k for c, k in zip(ct, ks))
    raise ValueError(f"unknown vault scheme 0x{scheme:02x}")


# ---------------------------------------------------------------------------
# Backend: mock (in-memory)
# ---------------------------------------------------------------------------
def _mem_load_user(user_id: str) -> dict[str, dict]:
    return _MEM_STORE.get(user_id) or {}


def _mem_save_user(user_id: str, entries: dict[str, dict]) -> None:
    if entries:
        _MEM_STORE[user_id] = entries
    else:
        _MEM_STORE.pop(user_id, None)


def _mem_known_users() -> list[str]:
    return sorted(_MEM_STORE.keys())


# ---------------------------------------------------------------------------
# Backend: fs (one JSON file per user)
# ---------------------------------------------------------------------------
def _fs_path_for(user_id: str) -> str:
    safe = user_id.replace("/", "_").replace("\\", "_")
    return os.path.join(_vault_dir(), safe + ".vault.json")


def _fs_ensure_dir() -> str:
    d = _vault_dir()
    os.makedirs(d, exist_ok=True)
    return d


def _fs_load_user(user_id: str) -> dict[str, dict]:
    path = _fs_path_for(user_id)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f) or {}
    except (OSError, json.JSONDecodeError) as e:  # pragma: no cover (defensive)
        logger.warning(
            "vault fs load failed user=%s err=%s",
            runtime_privacy.user_ref(user_id), e,
        )
        return {}
    return dict(doc.get("entries") or {})


def _fs_save_user(user_id: str, entries: dict[str, dict]) -> None:
    _fs_ensure_dir()
    path = _fs_path_for(user_id)
    if not entries:
        try:
            os.remove(path)
        except OSError:
            pass
        return
    doc = {
        "version": VAULT_VERSION,
        "user_id": user_id,
        "entries": entries,
        "saved_ts": time.time(),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    os.replace(tmp, path)


def _fs_known_users() -> list[str]:
    d = _vault_dir()
    if not os.path.isdir(d):
        return []
    out: list[str] = []
    for fn in os.listdir(d):
        if fn.endswith(".vault.json"):
            out.append(fn[:-len(".vault.json")])
    return sorted(out)


# ---------------------------------------------------------------------------
# Backend: sqlite (single DB)
# ---------------------------------------------------------------------------
def _sql_conn() -> sqlite3.Connection:
    global _SQLITE_CONN, _SQLITE_PATH_CACHED
    path = _sqlite_path()
    if _SQLITE_CONN is not None and _SQLITE_PATH_CACHED == path:
        return _SQLITE_CONN
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vault_entries (
            user_id TEXT NOT NULL,
            key     TEXT NOT NULL,
            value   TEXT NOT NULL,
            ts      REAL NOT NULL,
            PRIMARY KEY (user_id, key)
        )
        """,
    )
    conn.commit()
    _SQLITE_CONN = conn
    _SQLITE_PATH_CACHED = path
    return conn


def _sql_load_user(user_id: str) -> dict[str, dict]:
    cur = _sql_conn().execute(
        "SELECT key, value, ts FROM vault_entries WHERE user_id = ?",
        (user_id,),
    )
    out: dict[str, dict] = {}
    for k, v, ts in cur.fetchall():
        out[k] = {"v": v, "ts": float(ts)}
    return out


def _sql_save_user(user_id: str, entries: dict[str, dict]) -> None:
    conn = _sql_conn()
    with conn:
        conn.execute("DELETE FROM vault_entries WHERE user_id = ?", (user_id,))
        if entries:
            conn.executemany(
                "INSERT INTO vault_entries(user_id, key, value, ts) VALUES (?, ?, ?, ?)",
                [
                    (user_id, k, e["v"], float(e.get("ts") or 0.0))
                    for k, e in entries.items()
                ],
            )


def _sql_known_users() -> list[str]:
    cur = _sql_conn().execute("SELECT DISTINCT user_id FROM vault_entries")
    return sorted([r[0] for r in cur.fetchall()])


# ---------------------------------------------------------------------------
# Backend: firestore (one document per entry — durable on Cloud Run)
# ---------------------------------------------------------------------------
# Layout:
#     {coll}/{user_id}                      — per-user marker doc; its
#                                             presence is what
#                                             _fire_known_users() lists
#     {coll}/{user_id}/entries/{vault_key}  — one doc per entry,
#                                             fields {"key", "v", "ts"}
# A vault key is a safe Firestore document id: _validate_key forbids '/'
# and null bytes, caps length at 256, and requires an ALLOWED_NAMESPACES
# prefix (so a key can never be '.', '..', or match the reserved
# '__*__' pattern). Per-entry docs sidestep Firestore's 1 MiB
# per-document limit and keep an ordinary vault_put to a single write.
# Dedicated collection — distinct from vault_store.py's "vault" collection
# (the v1 notes/sessions storage), which shares this Firestore database.
_FIRE_COLLECTION = "memory_vault"
_FIRE_BATCH_LIMIT = 450  # Firestore caps a batch at 500 ops; leave headroom


def _fire_client() -> Any:
    """Lazy-init the Firestore client. The import is deferred so the
    mock/fs/sqlite backends keep working without google-cloud-firestore
    installed (mirrors users_store._get_firestore)."""
    global _FIRE_CLIENT
    if _FIRE_CLIENT is not None:
        return _FIRE_CLIENT
    try:
        from google.cloud import firestore  # type: ignore
    except ImportError as e:  # pragma: no cover - deploy-env dependent
        raise RuntimeError(
            "CLARITYOS_VAULT_BACKEND=firestore but google-cloud-firestore "
            "is not installed."
        ) from e
    _FIRE_CLIENT = firestore.Client()
    logger.info("memory_vault firestore client initialised")
    return _FIRE_CLIENT


def _fire_doc_id(user_id: str) -> str:
    """Sanitise a user_id for use as a Firestore document id (mirrors
    the fs backend's path sanitisation)."""
    return user_id.replace("/", "_").replace("\\", "_")


def _fire_user_doc(user_id: str):
    return _fire_client().collection(_FIRE_COLLECTION).document(_fire_doc_id(user_id))


def _fire_load_user(user_id: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for snap in _fire_user_doc(user_id).collection("entries").stream():
        d = snap.to_dict() or {}
        if "v" not in d:  # pragma: no cover - defensive
            continue
        key = str(d.get("key") or snap.id)
        out[key] = {"v": d["v"], "ts": float(d.get("ts") or 0.0)}
    return out


def _fire_commit(client: Any, ops: list) -> None:
    """Apply (op, ref[, data]) tuples in batches under the 500-op cap."""
    for i in range(0, len(ops), _FIRE_BATCH_LIMIT):
        batch = client.batch()
        for op in ops[i:i + _FIRE_BATCH_LIMIT]:
            if op[0] == "set":
                batch.set(op[1], op[2])
            else:
                batch.delete(op[1])
        batch.commit()


def _fire_save_user(user_id: str, entries: dict[str, dict]) -> None:
    """Replace the stored entry set for ``user_id``. Diffs against the
    current Firestore state so an ordinary vault_put commits a single
    document write instead of rewriting the whole user."""
    client = _fire_client()
    user_doc = _fire_user_doc(user_id)
    entries_coll = user_doc.collection("entries")
    current = _fire_load_user(user_id)
    ops: list = []

    if not entries:
        # vault_clear — drop every entry doc and the marker doc.
        ops.extend(("delete", entries_coll.document(k)) for k in current)
        ops.append(("delete", user_doc))
        _fire_commit(client, ops)
        return

    for key, rec in entries.items():
        if current.get(key) != rec:
            ops.append((
                "set", entries_coll.document(key),
                {"key": key, "v": rec["v"], "ts": float(rec.get("ts") or 0.0)},
            ))
    for key in current:
        if key not in entries:
            ops.append(("delete", entries_coll.document(key)))
    # Refresh the marker doc so _fire_known_users() always sees this user.
    ops.append((
        "set", user_doc,
        {"user_id": user_id, "version": VAULT_VERSION, "saved_ts": time.time()},
    ))
    _fire_commit(client, ops)


def _fire_known_users() -> list[str]:
    coll = _fire_client().collection(_FIRE_COLLECTION)
    return sorted(snap.id for snap in coll.stream())


# ---------------------------------------------------------------------------
# Generic backend dispatch
# ---------------------------------------------------------------------------
def _load_user(user_id: str) -> dict[str, dict]:
    b = _backend()
    if b == "mock":
        return _mem_load_user(user_id)
    if b == "sqlite":
        return _sql_load_user(user_id)
    if b == "firestore":
        return _fire_load_user(user_id)
    return _fs_load_user(user_id)


def _save_user(user_id: str, entries: dict[str, dict]) -> None:
    b = _backend()
    if b == "mock":
        _mem_save_user(user_id, entries)
    elif b == "sqlite":
        _sql_save_user(user_id, entries)
    elif b == "firestore":
        _fire_save_user(user_id, entries)
    else:
        _fs_save_user(user_id, entries)


def _known_users() -> list[str]:
    b = _backend()
    if b == "mock":
        return _mem_known_users()
    if b == "sqlite":
        return _sql_known_users()
    if b == "firestore":
        return _fire_known_users()
    return _fs_known_users()


# ---------------------------------------------------------------------------
# Public — vault_init / put / get / list / delete / clear
# ---------------------------------------------------------------------------
def vault_init(user_id: str) -> None:
    """Idempotent. Creates per-user storage scaffolding (file/row) so
    callers can rely on the user existing before walking keys."""
    user_id = _validate_user(user_id)
    with _LOCK:
        existing = _load_user(user_id)
        if not existing:
            # Touch with an empty dict so fs/sqlite materialise the
            # storage row. Mock backend stays empty (no entry created).
            if _backend() == "fs":
                _fs_ensure_dir()
            elif _backend() == "sqlite":
                _sql_conn()
        # Trigger key derivation eagerly so the cache is warm. Helps
        # the very first vault_put be fast under fs/sqlite backends.
        _derive_key(user_id)


def vault_put(user_id: str, key: str, value: Any) -> None:
    """Store ``value`` (any JSON-serialisable type) under ``key`` for
    ``user_id``. Encrypts at rest by default. Overwrites any existing
    value for that key.
    """
    user_id = _validate_user(user_id)
    key = _validate_key(key)
    try:
        plaintext = json.dumps(value, separators=(",", ":"), default=str).encode("utf-8")
    except (TypeError, ValueError) as e:
        raise ValueError(f"value not JSON-serialisable: {e}") from e
    envelope = _encrypt_value(user_id, plaintext)
    with _LOCK:
        entries = dict(_load_user(user_id))
        entries[key] = {"v": envelope, "ts": time.time()}
        _save_user(user_id, entries)


def vault_get(user_id: str, key: str, default: Any = None) -> Any:
    """Decrypt + deserialize the value at ``key``. Returns ``default``
    when the key isn't present. Raises only on integrity failure
    (corrupted envelope / wrong key)."""
    user_id = _validate_user(user_id)
    key = _validate_key(key)
    with _LOCK:
        entries = _load_user(user_id)
    rec = entries.get(key)
    if rec is None:
        return default
    try:
        plaintext = _decrypt_value(user_id, rec["v"])
        return json.loads(plaintext.decode("utf-8"))
    except (ValueError, json.JSONDecodeError, KeyError) as e:
        logger.warning(
            "vault_get decrypt failed user=%s key=%s err=%s",
            runtime_privacy.user_ref(user_id), key, e,
        )
        raise


def vault_list(user_id: str) -> dict[str, Any]:
    """Return every entry for ``user_id`` as ``{key: decrypted_value}``.
    Entries that fail to decrypt are skipped (logged) so a single
    corrupted record doesn't poison reads."""
    user_id = _validate_user(user_id)
    with _LOCK:
        entries = _load_user(user_id)
    out: dict[str, Any] = {}
    for k, rec in entries.items():
        try:
            plaintext = _decrypt_value(user_id, rec["v"])
            out[k] = json.loads(plaintext.decode("utf-8"))
        except Exception as e:  # pragma: no cover (defensive)
            logger.warning(
                "vault_list decrypt failed user=%s key=%s err=%s",
                runtime_privacy.user_ref(user_id), k, e,
            )
    return out


def vault_delete(user_id: str, key: str) -> None:
    """Remove ``key`` for ``user_id``. No-op when the key doesn't exist."""
    user_id = _validate_user(user_id)
    key = _validate_key(key)
    with _LOCK:
        entries = dict(_load_user(user_id))
        if key in entries:
            entries.pop(key, None)
            _save_user(user_id, entries)


def vault_clear(user_id: str) -> None:
    """Drop every entry for ``user_id``. Convenient for migrations and
    test cleanup. Does not remove the per-user salt — re-using the
    same user_id reuses the same key."""
    user_id = _validate_user(user_id)
    with _LOCK:
        _save_user(user_id, {})


# ---------------------------------------------------------------------------
# Public — read-side helpers (kernel + founder console + UI)
# ---------------------------------------------------------------------------
def vault_keys_for_user(user_id: str) -> list[str]:
    user_id = _validate_user(user_id)
    with _LOCK:
        return sorted(_load_user(user_id).keys())


def vault_count_for_user(user_id: str, namespace: Optional[str] = None) -> int:
    """Cheap key count. ``namespace`` filters by the leading segment;
    ``None`` returns the total."""
    user_id = _validate_user(user_id)
    with _LOCK:
        keys = _load_user(user_id).keys()
    if namespace:
        prefix = namespace + "."
        return sum(1 for k in keys if k.startswith(prefix))
    return len(list(keys))


def vault_known_users() -> list[str]:
    """List every user_id that has at least one vault row. Used by the
    founder vault inspector."""
    return _known_users()


def vault_status() -> dict:
    """Global vault snapshot. Surfaced via ``kernel_status``."""
    backend = _backend()
    users = vault_known_users()
    total = 0
    for u in users:
        try:
            total += vault_count_for_user(u)
        except Exception:  # pragma: no cover (defensive)
            continue
    return {
        "version":     VAULT_VERSION,
        "enabled":     True,
        "backend":     backend,
        "encrypted":   _is_encrypted(),
        "namespaces":  list(ALLOWED_NAMESPACES),
        "users":       len(users),
        "keys":        total,
        "scheme":      "hmac-ctr+sha256-mac" if _is_encrypted() else "plain",
        "pbkdf2_iter": _pbkdf2_iters(),
        "fs_dir":      _vault_dir() if backend == "fs" else None,
        "sqlite_path": _sqlite_path() if backend == "sqlite" else None,
    }


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
def _reset_for_tests() -> None:
    """Wipe in-memory state. fs/sqlite backends are not reset here —
    tests that exercise those backends should use ``tmp_path`` and set
    ``CLARITYOS_VAULT_DIR`` / ``CLARITYOS_VAULT_DB`` accordingly."""
    global _MEM_STORE, _SQLITE_CONN, _SQLITE_PATH_CACHED, _FIRE_CLIENT
    global _PLAINTEXT_WARNING_EMITTED
    with _LOCK:
        _MEM_STORE = {}
        _KEY_CACHE.clear()
        if _SQLITE_CONN is not None:
            try:
                _SQLITE_CONN.close()
            except Exception:  # pragma: no cover
                pass
        _SQLITE_CONN = None
        _SQLITE_PATH_CACHED = None
        _FIRE_CLIENT = None
        # PASS-4 FIX-P3 — clear the one-shot plaintext-warning flag so
        # each test that toggles CLARITYOS_VAULT_PLAINTEXT can observe
        # the warning emission contract from a clean baseline.
        _PLAINTEXT_WARNING_EMITTED = False


# ---------------------------------------------------------------------------
# Readiness probe (v0.3.11 — Card 16)
# ---------------------------------------------------------------------------
def is_ready(user_id: str | None = None) -> bool:
    """Cheap, non-throwing readiness check for the memory vault.

    Returns ``True`` when the vault subsystem is configured well enough
    to derive a per-user key (i.e. ``CLARITYOS_VAULT_SECRET`` is set
    and the PBKDF2 derivation succeeds). Returns ``False`` otherwise —
    never raises.

    Callers (notably ``/me`` in app.py) use this to surface a
    ``vault_ready`` boolean to the client instead of letting a
    ``RuntimeError`` bubble all the way up to a FastAPI 500.

    If ``user_id`` is provided, the full key derivation is exercised
    (which validates both the master secret AND the user-id shape).
    If ``user_id`` is None, only the master-secret presence is
    checked (cheaper; useful for global readiness probes).
    """
    try:
        if user_id is None:
            _secret()
        else:
            _derive_key(user_id)
        return True
    except Exception:
        return False
