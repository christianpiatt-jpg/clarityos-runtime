"""
Tests for v46 — Memory Vault v1.0 (local secure storage + cross-surface continuity).

Covers:

memory_vault core:
  * vault_init / put / get / list / delete / clear round-trips
  * encryption round-trip via HMAC-CTR + HMAC-SHA256
  * decrypt fails with a different secret (key isolation)
  * namespace validation rejects unknown prefixes
  * mock backend deterministic; fs backend persists across reset
  * vault_status / vault_known_users / vault_count_for_user shape

operator_state migration:
  * legacy in-memory snapshot → migrate_operator_state_to_vault → state preserved
  * STATE_VERSION reflects v46
  * default state shape unchanged
  * record_elins_interaction / record_g_run write individual vault entries
  * HISTORY_MAX pruning still enforced

intelligence_kernel:
  * kernel_status carries the vault block
  * kernel_view_for_user exposes vault_keys / notes_count / embeddings_count

Endpoints:
  * /me/vault/status shape + per-user counts
  * /me/vault/notes — list / put / delete round-trip + bad keys 400
  * /me/vault/embeddings — list / put / delete + dim cap + delete
  * /founder/vault/users — founder gate + count
  * /founder/vault/{user_id}/keys — namespace grouping
  * /founder/vault/{user_id}/item/{key} — value retrieval + 404 on miss
  * /me capability advertises memory_vault
  * /health version 4.2
"""
from __future__ import annotations

import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(app_module, username, cohort="founder"):
    import bcrypt
    import sessions_store
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ---------------------------------------------------------------------------
# memory_vault — core API round-trips
# ---------------------------------------------------------------------------
def test_vault_put_get_round_trip(reset_stores):
    import memory_vault as mv
    mv.vault_init("alice")
    mv.vault_put("alice", "operator_state.preferred_model", "anthropic:claude-haiku-4-5-20251001")
    assert mv.vault_get("alice", "operator_state.preferred_model") == "anthropic:claude-haiku-4-5-20251001"


def test_vault_put_get_complex_value(reset_stores):
    import memory_vault as mv
    mv.vault_init("alice")
    payload = {"vector": [0.1, 0.2, 0.3], "tag": "x", "n": 7}
    mv.vault_put("alice", "embeddings.test", payload)
    got = mv.vault_get("alice", "embeddings.test")
    assert got == payload


def test_vault_get_missing_returns_default(reset_stores):
    import memory_vault as mv
    mv.vault_init("alice")
    assert mv.vault_get("alice", "notes.nope", default="DEFAULT") == "DEFAULT"


def test_vault_delete_idempotent(reset_stores):
    import memory_vault as mv
    mv.vault_init("alice")
    mv.vault_put("alice", "notes.x", "hello")
    mv.vault_delete("alice", "notes.x")
    mv.vault_delete("alice", "notes.x")  # second call no-op
    assert mv.vault_get("alice", "notes.x") is None


def test_vault_list_returns_decrypted(reset_stores):
    import memory_vault as mv
    mv.vault_init("alice")
    mv.vault_put("alice", "notes.a", "first")
    mv.vault_put("alice", "notes.b", "second")
    mv.vault_put("alice", "operator_state.preferred_model", "anthropic:claude-haiku-4-5-20251001")
    listing = mv.vault_list("alice")
    assert listing["notes.a"] == "first"
    assert listing["notes.b"] == "second"
    assert listing["operator_state.preferred_model"] == "anthropic:claude-haiku-4-5-20251001"


def test_vault_clear_drops_everything_for_user(reset_stores):
    import memory_vault as mv
    mv.vault_init("alice")
    mv.vault_put("alice", "notes.x", "x")
    mv.vault_put("bob", "notes.x", "y")
    mv.vault_clear("alice")
    assert mv.vault_list("alice") == {}
    # Bob untouched.
    assert mv.vault_get("bob", "notes.x") == "y"


def test_vault_init_validates_user(reset_stores):
    import memory_vault as mv
    with pytest.raises(ValueError):
        mv.vault_init("")


def test_vault_put_validates_namespace(reset_stores):
    import memory_vault as mv
    mv.vault_init("alice")
    with pytest.raises(ValueError):
        mv.vault_put("alice", "unknown_namespace.key", "x")


def test_vault_put_validates_namespace_only_key(reset_stores):
    """Bare namespace (e.g. ``notes.``) is invalid."""
    import memory_vault as mv
    mv.vault_init("alice")
    with pytest.raises(ValueError):
        mv.vault_put("alice", "notes.", "x")


def test_vault_put_validates_path_separators(reset_stores):
    import memory_vault as mv
    mv.vault_init("alice")
    with pytest.raises(ValueError):
        mv.vault_put("alice", "notes.bad/key", "x")


def test_vault_namespace_of_extracts_prefix(reset_stores):
    import memory_vault as mv
    assert mv.namespace_of("notes.team_brief") == "notes"
    assert mv.namespace_of("elins.123_456") == "elins"
    assert mv.namespace_of("") == ""
    assert mv.namespace_of("noseparator") == "noseparator"


# ---------------------------------------------------------------------------
# memory_vault — encryption + key isolation
# ---------------------------------------------------------------------------
def test_vault_encryption_round_trip(reset_stores):
    """Confirm the ciphertext on disk is not the plaintext, and that
    decrypt(encrypt(x)) == x."""
    import memory_vault as mv
    mv.vault_init("alice")
    mv.vault_put("alice", "notes.secret", "hello world")

    # Peek at the raw stored envelope (mock backend exposes _MEM_STORE).
    raw = mv._MEM_STORE["alice"]["notes.secret"]["v"]
    assert "hello world" not in raw   # ciphertext doesn't leak plaintext
    assert mv.vault_get("alice", "notes.secret") == "hello world"


def test_vault_decrypt_fails_with_different_secret(reset_stores, monkeypatch):
    """If the secret rotates, the previously-stored value is no longer
    decryptable. Demonstrates per-user key isolation."""
    import memory_vault as mv
    monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "secret-A")
    mv._reset_for_tests()
    mv.vault_init("alice")
    mv.vault_put("alice", "notes.secret", "stored under A")

    # Rotate the secret + clear key cache (re-derive will produce a different key).
    monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "secret-B")
    mv._KEY_CACHE.clear()

    with pytest.raises(ValueError):
        mv.vault_get("alice", "notes.secret")


def test_secret_required_no_default(monkeypatch):
    """v83 — memory_vault has no built-in default secret. _secret() raises
    RuntimeError when CLARITYOS_VAULT_SECRET is missing, empty, or blank so a
    misconfigured deployment fails loudly instead of silently encrypting
    every user's data under a guessable key."""
    import memory_vault as mv

    monkeypatch.delenv("CLARITYOS_VAULT_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        mv._secret()

    monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "")
    with pytest.raises(RuntimeError):
        mv._secret()

    monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "   ")
    with pytest.raises(RuntimeError):
        mv._secret()

    # A real value resolves cleanly and is whitespace-trimmed.
    monkeypatch.setenv("CLARITYOS_VAULT_SECRET", "  a-real-secret  ")
    assert mv._secret() == b"a-real-secret"


def test_vault_per_user_key_isolation(reset_stores):
    """Two users writing the same vault key end up with different
    ciphertext envelopes (because the per-user key differs)."""
    import memory_vault as mv
    mv.vault_init("alice")
    mv.vault_init("bob")
    mv.vault_put("alice", "notes.secret", "hello")
    mv.vault_put("bob", "notes.secret", "hello")
    a_raw = mv._MEM_STORE["alice"]["notes.secret"]["v"]
    b_raw = mv._MEM_STORE["bob"]["notes.secret"]["v"]
    assert a_raw != b_raw
    # Both decrypt back to the same plaintext under their own user_id.
    assert mv.vault_get("alice", "notes.secret") == "hello"
    assert mv.vault_get("bob", "notes.secret") == "hello"


def test_vault_status_default_shape(reset_stores):
    import memory_vault as mv
    s = mv.vault_status()
    assert s["enabled"] is True
    assert s["backend"] == "mock"
    assert s["encrypted"] is True
    assert s["scheme"].startswith("hmac-ctr")
    assert "operator_state" in s["namespaces"]
    assert "notes" in s["namespaces"]
    assert s["users"] == 0
    assert s["keys"] == 0


def test_vault_known_users_lists_users_with_entries(reset_stores):
    import memory_vault as mv
    mv.vault_put("alice", "notes.a", "x")
    mv.vault_put("bob", "notes.b", "x")
    users = mv.vault_known_users()
    assert "alice" in users
    assert "bob" in users


def test_vault_count_for_user_filters_by_namespace(reset_stores):
    import memory_vault as mv
    mv.vault_put("alice", "notes.a", "x")
    mv.vault_put("alice", "notes.b", "x")
    mv.vault_put("alice", "embeddings.e1", [0.1, 0.2])
    mv.vault_put("alice", "operator_state.preferred_model", "anthropic:claude-haiku-4-5-20251001")
    assert mv.vault_count_for_user("alice") == 4
    assert mv.vault_count_for_user("alice", "notes") == 2
    assert mv.vault_count_for_user("alice", "embeddings") == 1
    assert mv.vault_count_for_user("alice", "g_runs") == 0


# ---------------------------------------------------------------------------
# memory_vault — fs backend round-trip
# ---------------------------------------------------------------------------
def test_vault_fs_backend_persists_across_reset(reset_stores, monkeypatch, tmp_path):
    """fs backend writes JSON to disk so the same data is readable
    after a process-level _reset_for_tests."""
    import memory_vault as mv
    monkeypatch.setenv("CLARITYOS_VAULT_BACKEND", "fs")
    monkeypatch.setenv("CLARITYOS_VAULT_DIR", str(tmp_path))

    mv.vault_init("alice")
    mv.vault_put("alice", "notes.persistent", "still here")
    # Drop in-memory caches; the next read must hit disk.
    mv._reset_for_tests()
    assert mv.vault_get("alice", "notes.persistent") == "still here"
    # Sanity — file actually exists.
    files = list(tmp_path.glob("*.vault.json"))
    assert files, "expected a per-user vault file on disk"


def test_vault_sqlite_backend_round_trip(reset_stores, monkeypatch, tmp_path):
    import memory_vault as mv
    db = tmp_path / "vault.sqlite3"
    monkeypatch.setenv("CLARITYOS_VAULT_BACKEND", "sqlite")
    monkeypatch.setenv("CLARITYOS_VAULT_DB", str(db))

    mv.vault_init("alice")
    mv.vault_put("alice", "notes.from_sqlite", "hello")
    mv.vault_put("alice", "operator_state.preferred_model", "anthropic:claude-haiku-4-5-20251001")
    listing = mv.vault_list("alice")
    assert listing["notes.from_sqlite"] == "hello"
    assert listing["operator_state.preferred_model"] == "anthropic:claude-haiku-4-5-20251001"


# ---------------------------------------------------------------------------
# memory_vault — firestore backend (fake client; durable round-trips)
# ---------------------------------------------------------------------------
class _FakeFirestore:
    """In-memory stand-in for google.cloud.firestore.Client — implements
    only the surface memory_vault's firestore backend uses. Documents are
    keyed by their full path tuple, so subcollections fall out naturally.
    The store outlives _reset_for_tests(), exactly like real Firestore."""

    def __init__(self) -> None:
        self.store: dict = {}

    def collection(self, name):
        return _FakeColl(self, (name,))

    def batch(self):
        return _FakeBatch()


class _FakeColl:
    def __init__(self, fs, path):
        self._fs, self._path = fs, path

    def document(self, doc_id):
        return _FakeDoc(self._fs, self._path + (doc_id,))

    def stream(self):
        plen = len(self._path)
        for path, data in list(self._fs.store.items()):
            if len(path) == plen + 1 and path[:plen] == self._path:
                yield _FakeSnap(path, data)


class _FakeDoc:
    def __init__(self, fs, path):
        self._fs, self._path = fs, path

    def collection(self, name):
        return _FakeColl(self._fs, self._path + (name,))

    def get(self):
        return _FakeSnap(self._path, self._fs.store.get(self._path))

    def set(self, data):
        self._fs.store[self._path] = dict(data)

    def delete(self):
        self._fs.store.pop(self._path, None)


class _FakeSnap:
    def __init__(self, path, data):
        self._path, self._data = path, data

    @property
    def id(self):
        return self._path[-1]

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _FakeBatch:
    def __init__(self):
        self._ops: list = []

    def set(self, ref, data):
        self._ops.append(("set", ref, dict(data)))

    def delete(self, ref):
        self._ops.append(("delete", ref))

    def commit(self):
        for op in self._ops:
            if op[0] == "set":
                op[1].set(op[2])
            else:
                op[1].delete()
        self._ops = []


def _use_firestore(monkeypatch):
    """Point memory_vault at a fresh fake Firestore. Returns (mv, fake)."""
    import memory_vault as mv
    fake = _FakeFirestore()
    monkeypatch.setenv("CLARITYOS_VAULT_BACKEND", "firestore")
    monkeypatch.setattr(mv, "_fire_client", lambda: fake)
    return mv, fake


def test_vault_firestore_persists_across_reset(reset_stores, monkeypatch):
    """The durability guarantee: data written under the firestore backend
    survives a process-level _reset_for_tests — the fake store stands in
    for Firestore, which outlives any Cloud Run container."""
    mv, _fake = _use_firestore(monkeypatch)
    mv.vault_init("alice")
    mv.vault_put("alice", "notes.persistent", "still here")
    mv._reset_for_tests()  # drop in-process caches; firestore is external
    assert mv.vault_get("alice", "notes.persistent") == "still here"
    assert mv.vault_status()["backend"] == "firestore"


def test_vault_firestore_round_trip(reset_stores, monkeypatch):
    mv, _fake = _use_firestore(monkeypatch)
    mv.vault_init("alice")
    mv.vault_put("alice", "notes.a", "first")
    mv.vault_put("alice", "notes.b", "second")
    mv.vault_put("alice", "operator_state.preferred_model", "anthropic:claude-haiku-4-5-20251001")
    assert mv.vault_list("alice") == {
        "notes.a": "first",
        "notes.b": "second",
        "operator_state.preferred_model": "anthropic:claude-haiku-4-5-20251001",
    }
    mv.vault_delete("alice", "notes.a")
    assert mv.vault_get("alice", "notes.a") is None
    assert mv.vault_keys_for_user("alice") == [
        "notes.b", "operator_state.preferred_model",
    ]


def test_vault_firestore_overwrite_keeps_single_entry(reset_stores, monkeypatch):
    """Re-putting a key overwrites in place — exercises the save-diff."""
    mv, _fake = _use_firestore(monkeypatch)
    mv.vault_put("alice", "notes.x", "v1")
    mv.vault_put("alice", "notes.x", "v2")
    assert mv.vault_get("alice", "notes.x") == "v2"
    assert mv.vault_keys_for_user("alice") == ["notes.x"]


def test_vault_firestore_clear_and_known_users(reset_stores, monkeypatch):
    mv, _fake = _use_firestore(monkeypatch)
    mv.vault_put("alice", "notes.x", "a")
    mv.vault_put("bob", "notes.y", "b")
    assert sorted(mv.vault_known_users()) == ["alice", "bob"]
    mv.vault_clear("alice")
    assert mv.vault_list("alice") == {}
    assert mv.vault_known_users() == ["bob"]      # alice's marker doc dropped
    assert mv.vault_get("bob", "notes.y") == "b"  # bob untouched


# ---------------------------------------------------------------------------
# operator_state — vault-backed shape + migration
# ---------------------------------------------------------------------------
def test_operator_state_default_shape_unchanged(reset_stores):
    import operator_state as os_
    state = os_.get_operator_state("alice")
    assert state["user_id"] == "alice"
    assert state["external_signal_mode"] == "cloud_only"
    assert state["elins_history"] == []
    assert state["g_history"] == []
    assert state["preferred_model"] is None
    assert state["last_model_used"] is None
    assert state["local_model_usage_count"] == 0
    assert state["version"] == "operator_state.v46.1"


def test_operator_state_record_elins_writes_individual_vault_entry(reset_stores):
    """Each record_elins_interaction → one vault key under ``elins.*``."""
    import memory_vault as mv
    import operator_state as os_
    os_.record_elins_interaction(
        "alice", "sc_1",
        {"topic": "fed rate", "region": "US", "domain": "economic"},
    )
    keys = mv.vault_keys_for_user("alice")
    elins_keys = [k for k in keys if k.startswith("elins.")]
    assert len(elins_keys) == 1
    entry = mv.vault_get("alice", elins_keys[0])
    assert entry["elins_id"] == "sc_1"
    assert entry["topic"] == "fed rate"
    assert entry["region"] == "US"
    assert entry["kind"] == "regional"


def test_operator_state_record_g_run_writes_individual_vault_entry(reset_stores):
    import memory_vault as mv
    import operator_state as os_
    os_.record_g_run("alice", "g_1", {"mode": "G", "topic": "comment"})
    keys = mv.vault_keys_for_user("alice")
    g_keys = [k for k in keys if k.startswith("g_runs.")]
    assert len(g_keys) == 1
    entry = mv.vault_get("alice", g_keys[0])
    assert entry["g_id"] == "g_1"
    assert entry["mode"] == "G"


def test_operator_state_history_capped(reset_stores):
    """HISTORY_MAX still enforced via _prune_history."""
    import memory_vault as mv
    import operator_state as os_
    for i in range(220):
        os_.record_elins_interaction(
            "alice", f"sc_{i}", {"topic": "t", "region": "US"},
        )
    state = os_.get_operator_state("alice")
    assert len(state["elins_history"]) == 200
    # Vault should also have been pruned (oldest entries removed).
    elins_keys = [k for k in mv.vault_keys_for_user("alice") if k.startswith("elins.")]
    assert len(elins_keys) == 200


def test_operator_state_set_preferred_model_writes_vault(reset_stores):
    import memory_vault as mv
    import operator_state as os_
    os_.set_preferred_model("alice", "anthropic:claude-haiku-4-5-20251001")
    assert mv.vault_get("alice", "operator_state.preferred_model") == "anthropic:claude-haiku-4-5-20251001"
    assert os_.get_operator_state("alice")["preferred_model"] == "anthropic:claude-haiku-4-5-20251001"


def test_operator_state_set_preferred_model_clear(reset_stores):
    import memory_vault as mv
    import operator_state as os_
    os_.set_preferred_model("alice", "anthropic:claude-haiku-4-5-20251001")
    os_.set_preferred_model("alice", None)
    assert mv.vault_get("alice", "operator_state.preferred_model") is None


def test_operator_state_record_model_used(reset_stores):
    """v44 record_model_used continues to work via the vault."""
    import operator_state as os_
    os_.record_model_used("alice", "openai:gpt-5.4")
    assert os_.get_operator_state("alice")["last_model_used"] == "openai:gpt-5.4"


def test_operator_state_bump_local_model_usage(reset_stores):
    """v45 bump_local_model_usage now persists via the vault."""
    import operator_state as os_
    os_.bump_local_model_usage("alice")
    os_.bump_local_model_usage("alice", by=2)
    assert os_.get_operator_state("alice")["local_model_usage_count"] == 3


def test_operator_state_strips_raw_text_fields(reset_stores):
    """Raw-text rejection still works post-vault refactor."""
    import operator_state as os_
    os_.record_elins_interaction(
        "alice", "sc_1",
        {"topic": "t", "region": "US",
         "text": "DO NOT KEEP", "scenario_text": "ALSO NOT", "raw_text": "NO"},
    )
    state = os_.get_operator_state("alice")
    entry = state["elins_history"][0]
    for forbidden in ("text", "scenario_text", "raw_text"):
        assert forbidden not in entry


def test_operator_state_migration_round_trip(reset_stores):
    """A legacy-shaped dict migrates into the vault and reads back as
    a v46 state."""
    import operator_state as os_
    legacy = {
        "external_signal_mode": "cloud_perplexity",
        "preferred_domains": {"economic": 1.5, "geopolitical": 0.8},
        "preferred_regions": {"US": 2.0, "MEA": 0.5},
        "preferred_model": "openai:gpt-5.4",
        "last_model_used": "anthropic:claude-haiku-4-5-20251001",
        "local_model_usage_count": 7,
        "created_ts": 1_000_000.0,
        "last_active_ts": 1_001_000.0,
        "elins_history": [
            {"ts": 1_000_100.0, "elins_id": "sc_a", "topic": "t",
             "region": "US", "kind": "regional"},
            {"ts": 1_000_200.0, "elins_id": "sc_b", "topic": "u",
             "region": "EU", "kind": "regional"},
        ],
        "g_history": [
            {"ts": 1_000_300.0, "g_id": "g_a", "mode": "G", "topic": "x"},
        ],
    }
    state = os_.migrate_operator_state_to_vault("alice", legacy)
    assert state["external_signal_mode"] == "cloud_perplexity"
    assert state["preferred_model"] == "openai:gpt-5.4"
    assert state["last_model_used"] == "anthropic:claude-haiku-4-5-20251001"
    assert state["local_model_usage_count"] == 7
    assert len(state["elins_history"]) == 2
    assert len(state["g_history"]) == 1
    # Vault has the correct number of entries (8 = 2 elins + 1 g + 5 OS fields, plus created/last_active).
    import memory_vault as mv
    keys = mv.vault_keys_for_user("alice")
    elins_keys = [k for k in keys if k.startswith("elins.")]
    assert len(elins_keys) == 2


# ---------------------------------------------------------------------------
# intelligence_kernel — vault block + per-user counts
# ---------------------------------------------------------------------------
def test_kernel_status_includes_vault_block(reset_stores):
    import intelligence_kernel as ik
    s = ik.kernel_status()
    assert "vault" in s
    v = s["vault"]
    assert v["enabled"] is True
    assert v["backend"] == "mock"
    assert v["encrypted"] is True
    assert "namespaces" in v


def test_kernel_view_for_user_includes_vault_counts(reset_stores):
    import intelligence_kernel as ik
    import memory_vault as mv
    mv.vault_put("alice", "notes.a", "x")
    mv.vault_put("alice", "notes.b", "y")
    mv.vault_put("alice", "embeddings.e1", [0.1])
    view = ik.kernel_view_for_user("alice")
    assert view["notes_count"] == 2
    assert view["embeddings_count"] == 1
    assert view["vault_keys"] >= 3


# ---------------------------------------------------------------------------
# Endpoints — /me/vault/status + notes + embeddings
# ---------------------------------------------------------------------------
def test_endpoint_me_vault_status_shape(app_module, client):
    user, sid = _make_user(app_module, "vault_a", cohort="founder")
    r = client.get("/me/vault/status", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert "global" in body
    assert "user" in body
    assert body["user"]["user_id"] == user
    assert body["global"]["backend"] == "mock"
    assert body["global"]["encrypted"] is True


def test_endpoint_notes_round_trip(app_module, client):
    user, sid = _make_user(app_module, "vault_b", cohort="founder")
    # Empty list initially.
    r = client.get("/me/vault/notes", headers=_auth(sid))
    assert r.status_code == 200
    assert r.json()["notes"] == []

    # Create a note.
    r2 = client.post(
        "/me/vault/notes", headers=_auth(sid),
        json={"key": "team_brief", "text": "weekly notes"},
    )
    assert r2.status_code == 200, r2.json()

    # List shows it.
    r3 = client.get("/me/vault/notes", headers=_auth(sid))
    notes = r3.json()["notes"]
    assert len(notes) == 1
    assert notes[0] == {"key": "team_brief", "text": "weekly notes"}

    # Update with same key replaces.
    client.post(
        "/me/vault/notes", headers=_auth(sid),
        json={"key": "team_brief", "text": "updated text"},
    )
    r4 = client.get("/me/vault/notes", headers=_auth(sid))
    assert r4.json()["notes"][0]["text"] == "updated text"

    # Delete.
    client.post(
        "/me/vault/notes/delete", headers=_auth(sid),
        json={"key": "team_brief"},
    )
    r5 = client.get("/me/vault/notes", headers=_auth(sid))
    assert r5.json()["notes"] == []


def test_endpoint_notes_rejects_dotted_key(app_module, client):
    """Sub-keys must not contain '.', '/', or '\\\\' — the namespace
    is added by the server."""
    user, sid = _make_user(app_module, "vault_c", cohort="founder")
    r = client.post(
        "/me/vault/notes", headers=_auth(sid),
        json={"key": "bad.key", "text": "x"},
    )
    assert r.status_code == 400


def test_endpoint_embeddings_round_trip(app_module, client):
    user, sid = _make_user(app_module, "vault_d", cohort="founder")
    r = client.post(
        "/me/vault/embeddings", headers=_auth(sid),
        json={"key": "e1", "vector": [0.1, 0.2, 0.3, 0.4]},
    )
    assert r.status_code == 200
    assert r.json()["dim"] == 4

    r2 = client.get("/me/vault/embeddings", headers=_auth(sid))
    embs = r2.json()["embeddings"]
    assert len(embs) == 1
    assert embs[0] == {"key": "e1", "dim": 4}

    client.post(
        "/me/vault/embeddings/delete", headers=_auth(sid),
        json={"key": "e1"},
    )
    assert client.get("/me/vault/embeddings", headers=_auth(sid)).json()["embeddings"] == []


def test_endpoint_embeddings_caps_dim(app_module, client):
    user, sid = _make_user(app_module, "vault_e", cohort="founder")
    huge = [0.0] * 8000
    r = client.post(
        "/me/vault/embeddings", headers=_auth(sid),
        json={"key": "huge", "vector": huge},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Endpoints — /founder/vault/*
# ---------------------------------------------------------------------------
def test_endpoint_founder_vault_users_lists_only_users_with_entries(
    app_module, client,
):
    import memory_vault as mv
    user, sid = _make_user(app_module, "fv_admin", cohort="founder")
    # Create vault entries for two users.
    mv.vault_put("user_a", "notes.x", "x")
    mv.vault_put("user_b", "operator_state.preferred_model", "anthropic:claude-haiku-4-5-20251001")
    r = client.get("/founder/vault/users", headers=_auth(sid))
    assert r.status_code == 200
    users = r.json()["users"]
    user_ids = {u["user_id"] for u in users}
    assert "user_a" in user_ids
    assert "user_b" in user_ids


def test_endpoint_founder_vault_users_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "fv_outsider", cohort=None)
    r = client.get("/founder/vault/users", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_founder_vault_keys_groups_by_namespace(app_module, client):
    import memory_vault as mv
    user, sid = _make_user(app_module, "fv_admin2", cohort="founder")
    mv.vault_put("target", "notes.a", "x")
    mv.vault_put("target", "notes.b", "x")
    mv.vault_put("target", "embeddings.e1", [0.1])
    mv.vault_put("target", "operator_state.preferred_model", "anthropic:claude-haiku-4-5-20251001")
    r = client.get("/founder/vault/target/keys", headers=_auth(sid))
    body = r.json()
    assert body["count"] == 4
    assert "notes" in body["by_namespace"]
    assert body["by_namespace"]["notes"]["count"] == 2
    assert body["by_namespace"]["embeddings"]["count"] == 1
    assert body["by_namespace"]["operator_state"]["count"] == 1


def test_endpoint_founder_vault_item_returns_decrypted_value(app_module, client):
    import memory_vault as mv
    user, sid = _make_user(app_module, "fv_admin3", cohort="founder")
    mv.vault_put("target", "notes.brief", "weekly notes")
    r = client.get(
        "/founder/vault/target/item/notes.brief", headers=_auth(sid),
    )
    body = r.json()
    assert body["ok"] is True
    assert body["value"] == "weekly notes"
    assert body["namespace"] == "notes"


def test_endpoint_founder_vault_item_404_on_missing(app_module, client):
    user, sid = _make_user(app_module, "fv_admin4", cohort="founder")
    r = client.get(
        "/founder/vault/no_user/item/notes.nope", headers=_auth(sid),
    )
    body = r.json()
    assert body["ok"] is False
    assert body["error"] == "not_found"


# ---------------------------------------------------------------------------
# /me capability + /health version
# ---------------------------------------------------------------------------
def test_endpoint_me_advertises_memory_vault_capability(app_module, client):
    user, sid = _make_user(app_module, "cap_v", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    ids = [c["id"] for c in r.json().get("capabilities") or []]
    assert "memory_vault" in ids


def test_health_version_bumped_to_4_2(app_module, client):
    """v46 set health version to 4.2; v47 bumps to 4.3. Either is OK
    here — the v46 contract didn't include the literal version string."""
    r = client.get("/health")
    assert r.json()["version"].startswith("4.")


# ---------------------------------------------------------------------------
# Continuity — kernel writes ELINS history into vault via operator_state
# ---------------------------------------------------------------------------
def test_kernel_run_elins_writes_vault_entry(reset_stores):
    """A kernel run should bump operator_state, which now persists into
    the vault under elins.*."""
    import intelligence_kernel as ik
    import memory_vault as mv
    ik.run_ELINS("alice", "trust between partners eroding",
                 kind="preview", persist=False)
    elins_keys = [k for k in mv.vault_keys_for_user("alice") if k.startswith("elins.")]
    assert len(elins_keys) >= 1


def test_kernel_run_g_writes_vault_entry(reset_stores):
    """run_G with a successful runner should write a g_runs.* entry."""
    import intelligence_kernel as ik
    import memory_vault as mv

    def fake_runner(text, user):
        return {"ok": True, "analysis": {"qc_summary": {"pressure": 0.42}}}

    ik.run_G("alice", "x", runner=fake_runner)
    g_keys = [k for k in mv.vault_keys_for_user("alice") if k.startswith("g_runs.")]
    assert len(g_keys) == 1
