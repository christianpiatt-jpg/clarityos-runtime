"""
#178 -- one vault load + decrypt per request.

WHAT THESE PIN. Outside a request nothing is cached (a put between two
lists is seen; the ContextVar is None). Inside a request the member's rows
load ONCE and each value decrypts ONCE however many reads follow; a write
in the same request is seen by the next read; the cache is torn down at
the response, so two requests never share a copy. The prefix read equals
the whole-vault read's slice; the kernel view's counts equal the counts
they replace; the operator state is byte-equal to its whole-vault reading;
/me and /me/operator_state answer the same bodies with the cache on and
off; vault_status is unchanged. The app's middleware opens and closes the
cache around every request.
"""
from __future__ import annotations

import json
import secrets
import time

import pytest

from conftest import TestClient, seed_controller

import intelligence_kernel as ik
import memory_vault as mv
import operator_state as os_mod
import sessions_store
import threads_vault
import users_store

import app as _app


@pytest.fixture(autouse=True)
def _isolate(reset_stores):
    mv._reset_for_tests()
    yield
    mv._reset_for_tests()


@pytest.fixture
def client():
    return TestClient(_app.app)


def _member(username="cache@example.com"):
    import bcrypt
    users_store.create_user(username=username, password_hash=bcrypt.hashpw(b"x", bcrypt.gensalt()),
                            salt="", tier="free", created_at=time.time())
    seed_controller(username)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, {"X-Session-ID": sid}


def _seed(user):
    mv.vault_put(user, "notes.a", {"t": "alpha"})
    mv.vault_put(user, "notes.b", {"t": "beta"})
    mv.vault_put(user, "embeddings.e1", [0.1, 0.2])
    mv.vault_put(user, "operator_state.preferred_model", "anthropic:claude-haiku-4-5-20251001")
    mv.vault_put(user, "elins.h.000001", {"ts": 1.0, "id": "x"})
    mv.vault_put(user, "g_runs.h.000001", {"ts": 2.0, "id": "y"})


class Counter:
    """Counts the loads and the decrypts the vault actually performs."""

    def __init__(self, monkeypatch):
        self.loads = 0
        self.decrypts = 0
        real_load, real_dec = mv._load_user, mv._decrypt_value

        def load(user_id):
            self.loads += 1
            return real_load(user_id)

        def dec(user_id, env):
            self.decrypts += 1
            return real_dec(user_id, env)

        monkeypatch.setattr(mv, "_load_user", load)
        monkeypatch.setattr(mv, "_decrypt_value", dec)


# --------------------------------------------------------------------------
# outside a request: no cache, ever
# --------------------------------------------------------------------------
def test_outside_a_request_nothing_is_cached(monkeypatch):
    user = "u_out"
    _seed(user)
    assert mv.request_cache_active() is False
    c = Counter(monkeypatch)
    a = mv.vault_list(user)
    mv.vault_put(user, "notes.a", {"t": "changed"})
    b = mv.vault_list(user)
    assert a["notes.a"] == {"t": "alpha"} and b["notes.a"] == {"t": "changed"}
    assert c.loads >= 3                      # list, the put's fresh load, list
    assert c.decrypts == 2 * 6               # every value, both times
    assert mv._REQ_CACHE.get() is None


# --------------------------------------------------------------------------
# inside a request: one load, one decrypt per value, writes seen, torn down
# --------------------------------------------------------------------------
def test_inside_a_request_one_load_and_one_decrypt_per_value(monkeypatch):
    user = "u_in"
    _seed(user)
    c = Counter(monkeypatch)
    token = mv.request_cache_open()
    try:
        assert mv.request_cache_active() is True
        first = mv.vault_list(user)
        assert c.loads == 1 and c.decrypts == 6
        second = mv.vault_list(user)
        keys = mv.vault_keys_for_user(user)
        n = mv.vault_count_for_user(user, "notes")
        one = mv.vault_get(user, "notes.a")
        mv.vault_init(user)
        assert c.loads == 1, "every read after the first reused the request's load"
        assert c.decrypts == 6, "no value decrypted twice"
        assert first == second and len(keys) == 6 and n == 2 and one == {"t": "alpha"}
    finally:
        mv.request_cache_close(token)
    assert mv._REQ_CACHE.get() is None


def test_a_write_in_the_same_request_is_seen_by_the_next_read(monkeypatch):
    user = "u_write"
    _seed(user)
    token = mv.request_cache_open()
    try:
        assert mv.vault_list(user)["notes.a"] == {"t": "alpha"}
        mv.vault_put(user, "notes.a", {"t": "changed"})
        assert mv.vault_list(user)["notes.a"] == {"t": "changed"}
        assert mv.vault_get(user, "notes.a") == {"t": "changed"}
        mv.vault_delete(user, "notes.b")
        assert "notes.b" not in mv.vault_keys_for_user(user)
        assert mv.vault_get(user, "notes.b") is None
        mv.vault_clear(user)
        assert mv.vault_list(user) == {} and mv.vault_keys_for_user(user) == []
    finally:
        mv.request_cache_close(token)


def test_two_requests_never_share_a_copy(monkeypatch):
    user = "u_two"
    _seed(user)
    t1 = mv.request_cache_open()
    a = mv.vault_list(user)
    mv.request_cache_close(t1)
    # a write from "elsewhere" (another request, another instance) between them
    mv._MEM_STORE[user]["notes.a"] = {"v": mv._encrypt_value(user, json.dumps({"t": "elsewhere"}).encode()), "ts": 1.0}
    t2 = mv.request_cache_open()
    b = mv.vault_list(user)
    mv.request_cache_close(t2)
    assert a["notes.a"] == {"t": "alpha"} and b["notes.a"] == {"t": "elsewhere"}


def test_on_firestore_a_single_get_never_populates_the_whole_vault_copy(monkeypatch):
    """The Firestore branch: a get with nothing loaded yet is ONE document
    read and leaves the request's whole-vault copy empty; a keys read then
    loads once, and the gets after it read from that copy (no more
    document reads)."""
    user = "u_fire"
    _seed(user)
    calls = {"get_one": 0}

    def fake_get_one(user_id, key):
        calls["get_one"] += 1
        return dict(mv._MEM_STORE.get(user_id, {}).get(key) or {}) or None

    monkeypatch.setattr(mv, "_backend", lambda: "firestore")
    monkeypatch.setattr(mv, "_fire_get_one", fake_get_one)
    monkeypatch.setattr(mv, "_load_user", lambda u: dict(mv._MEM_STORE.get(u, {})))
    c = Counter(monkeypatch)
    token = mv.request_cache_open()
    try:
        assert mv.vault_get(user, "notes.a") == {"t": "alpha"}
        assert calls["get_one"] == 1 and c.loads == 0
        assert mv._REQ_CACHE.get()[user]["entries"] is None      # not populated by a get
        mv.vault_keys_for_user(user)
        assert c.loads == 1
        assert mv.vault_get(user, "notes.b") == {"t": "beta"}
        assert calls["get_one"] == 1 and c.loads == 1            # served from the copy
    finally:
        mv.request_cache_close(token)


def test_a_repeated_single_document_read_never_returns_a_stale_plaintext(monkeypatch):
    """Firestore branch, nothing loaded: a row another instance rewrote
    between two gets in the same request decrypts AGAIN (the decrypt cache
    is keyed by the ciphertext, not the key alone)."""
    user = "u_stale"
    _seed(user)
    monkeypatch.setattr(mv, "_backend", lambda: "firestore")
    monkeypatch.setattr(mv, "_fire_get_one", lambda u, k: dict(mv._MEM_STORE.get(u, {}).get(k) or {}) or None)
    token = mv.request_cache_open()
    try:
        assert mv.vault_get(user, "notes.a") == {"t": "alpha"}
        mv._MEM_STORE[user]["notes.a"] = {"v": mv._encrypt_value(user, json.dumps({"t": "rewritten"}).encode()), "ts": 2.0}
        assert mv.vault_get(user, "notes.a") == {"t": "rewritten"}
    finally:
        mv.request_cache_close(token)


def test_a_cache_hit_returns_a_copy_a_caller_cannot_poison_the_next_read():
    user = "u_alias"
    _seed(user)
    token = mv.request_cache_open()
    try:
        a = mv.vault_get(user, "notes.a")
        a["t"] = "mutated in place"
        assert mv.vault_get(user, "notes.a") == {"t": "alpha"}
        assert mv.vault_list(user)["notes.a"] == {"t": "alpha"}
    finally:
        mv.request_cache_close(token)


# --------------------------------------------------------------------------
# the prefix read and the counts equal what they replace
# --------------------------------------------------------------------------
def test_prefix_read_equals_the_whole_vault_slice():
    user = "u_prefix"
    _seed(user)
    whole = mv.vault_list(user)
    for pfx in ("operator_state.", "notes.", "elins.", ("operator_state.", "elins.", "g_runs.")):
        got = mv.vault_list_prefix(user, pfx)
        p = (pfx,) if isinstance(pfx, str) else pfx
        assert got == {k: v for k, v in whole.items() if k.startswith(p)}
    assert mv.vault_list_prefix(user, "nothing.") == {}


def test_operator_state_reads_three_namespaces_and_equals_its_whole_vault_reading(monkeypatch):
    user = "u_state"
    _seed(user)
    # the reference: the state as the whole-vault read computes it
    os_mod.get_operator_state(user)          # first call writes created_ts
    ref_entries = mv.vault_list(user)
    c = Counter(monkeypatch)
    state = os_mod.get_operator_state(user)
    assert state["preferred_model"] == "anthropic:claude-haiku-4-5-20251001"
    assert [h["id"] for h in state["elins_history"]] == ["x"]
    assert [h["id"] for h in state["g_history"]] == ["y"]
    # decrypted only the three namespaces (4 keys of 7), never notes/embeddings
    assert c.decrypts == sum(1 for k in ref_entries if k.startswith(("operator_state.", "elins.", "g_runs.")))
    assert c.decrypts < len(ref_entries)


def test_kernel_view_counts_equal_the_counts_they_replace(monkeypatch):
    user = "u_view"
    _seed(user)
    threads_vault.create_thread(user, title="t")
    view = ik.kernel_view_for_user(user)
    assert view["vault_keys"] == mv.vault_count_for_user(user)
    assert view["notes_count"] == mv.vault_count_for_user(user, "notes") == 2
    assert view["embeddings_count"] == mv.vault_count_for_user(user, "embeddings") == 1
    assert view["thread_count"] == 1


# --------------------------------------------------------------------------
# the app: the middleware opens the cache; bodies equal cache on / off
# --------------------------------------------------------------------------
class CloseSpy:
    """Witnesses the middleware: the cache opened for the request and closed
    with the same token after it (the test thread's own context never holds
    the var, so `_REQ_CACHE.get() is None` here would prove nothing)."""

    def __init__(self, monkeypatch):
        self.opened = []
        self.closed = []
        real_open, real_close = mv.request_cache_open, mv.request_cache_close

        def opn():
            t = real_open()
            self.opened.append(t)
            return t

        def cls(token):
            self.closed.append(token)
            real_close(token)

        monkeypatch.setattr(mv, "request_cache_open", opn)
        monkeypatch.setattr(mv, "request_cache_close", cls)


def test_get_me_loads_the_vault_once_and_the_middleware_closes_the_cache(monkeypatch, client):
    user, h = _member()
    _seed(user)
    threads_vault.create_thread(user, title="t")
    os_mod.get_operator_state(user)          # created_ts written before the measured call
    c = Counter(monkeypatch)
    spy = CloseSpy(monkeypatch)
    r = client.get("/me", headers=h)
    assert r.status_code == 200, r.text
    assert c.loads == 1, f"GET /me loaded the vault {c.loads} times"
    assert len(spy.opened) == 1 and spy.closed == spy.opened   # opened once, closed with its token
    body = r.json()
    assert body["intelligence_kernel"]["notes_count"] == 2 and body["intelligence_kernel"]["thread_count"] == 1


def test_bodies_are_equal_with_the_cache_on_and_off(client):
    user, h = _member("bodies@example.com")
    _seed(user)
    threads_vault.create_thread(user, title="t")
    os_mod.get_operator_state(user)
    on_me = client.get("/me", headers=h).json()
    on_state = client.get("/me/operator_state", headers=h).json()
    # off: the same readers, no request context (the ContextVar is None here)
    off_view = ik.kernel_view_for_user(user)
    off_state = os_mod.get_operator_state(user)
    volatile = {"last_active_ts"}
    assert {k: v for k, v in on_state["state"].items() if k not in volatile} == \
           {k: v for k, v in off_state.items() if k not in volatile}
    assert on_me["intelligence_kernel"] == off_view


def test_two_requests_see_a_write_between_them(client):
    user, h = _member("between@example.com")
    _seed(user)
    a = client.get("/me", headers=h).json()["intelligence_kernel"]["notes_count"]
    mv.vault_put(user, "notes.c", {"t": "gamma"})
    b = client.get("/me", headers=h).json()["intelligence_kernel"]["notes_count"]
    assert (a, b) == (2, 3)


def test_vault_status_is_unchanged():
    st = mv.vault_status()
    assert "backend" in st and "encrypted" in st and "scheme" in st


def test_the_middleware_closes_the_cache_on_a_refused_request_too(client, monkeypatch):
    spy = CloseSpy(monkeypatch)
    r = client.get("/me/relationships/bad.id/arc", headers=_member("err@example.com")[1])
    assert r.status_code == 400
    assert len(spy.opened) == 1 and spy.closed == spy.opened
    # and on an unauthenticated 401
    r = client.get("/me")
    assert r.status_code == 401
    assert len(spy.opened) == 2 and spy.closed == spy.opened
