"""
vault_get must cost ONE Firestore read, not N.

★ THE DEFECT. ``vault_get`` called ``_load_user``, and the Firestore
implementation of that STREAMS THE WHOLE ``entries`` collection. So one
logical get cost N reads, where N is the member's total key count -- and it
got worse the more they used the product. Measured 2026-08-27 on the live
project: 14,670 reads on one account holding 37 keys (~37x amplification),
65% of the daily free quota on a single member.

★★ POINT-GETS DO NOT APPEAR IN QUERY INSIGHTS, which is why this ran for
months unseen: the most expensive operation in the database is absent from
the page built to show database cost. The external check after deploy is the
Firestore usage console -- 22,625 daily reads is the recorded before-number.

The tests below pin the two things most likely to break, on BOTH backends.
"""
import os

os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import pytest  # noqa: E402

import memory_vault as mv  # noqa: E402


# --------------------------------------------------------------------------
# A stub that models the Firestore semantics that actually matter here.
# No emulator is running in this environment; this exercises _fire_get_one's
# real code path, including the .exists branch, without one.
# --------------------------------------------------------------------------
class _Snap:
    def __init__(self, data):
        self._data = data
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class _DocRef:
    def __init__(self, store, key):
        self._store, self._key = store, key
        store.setdefault("_reads", [])

    def get(self):
        self._store["_reads"].append(self._key)
        return _Snap(self._store["docs"].get(self._key))


class _Coll:
    def __init__(self, store):
        self._store = store

    def document(self, key):
        return _DocRef(self._store, key)

    def stream(self):
        self._store.setdefault("_streams", []).append(True)
        return [_Snap(d) for d in self._store["docs"].values()]


class _UserDoc:
    def __init__(self, store):
        self._store = store

    def collection(self, _name):
        return _Coll(self._store)


@pytest.fixture
def fire(monkeypatch):
    """Force the firestore branch and hand it the stub."""
    store = {"docs": {}, "_reads": [], "_streams": []}
    monkeypatch.setattr(mv, "_backend", lambda: "firestore")
    monkeypatch.setattr(mv, "_fire_user_doc", lambda uid: _UserDoc(store))
    return store


def _put(store, key, value_envelope, ts=1.0):
    store["docs"][key] = {"key": key, "v": value_envelope, "ts": ts}


# --------------------------------------------------------------------------
# GATE 2 — the negative control. The most likely way to break this.
# --------------------------------------------------------------------------
def test_missing_key_returns_none_not_a_snapshot(fire):
    """``entries.get(key)`` on a dict returns None. ``document(key).get()``
    returns a snapshot whose ``.exists`` is False -- and that object is
    TRUTHY. Returning it unchecked turns 'key not written yet' into an
    integrity error on a member's first read."""
    assert mv._fire_get_one("u", "elins.never_written") is None


def test_missing_key_yields_the_default_through_vault_get(fire):
    assert mv.vault_get("u", "elins.absent") is None
    assert mv.vault_get("u", "elins.absent", default="D") == "D"


def test_present_key_returns_the_load_user_shape(fire):
    """★ _decrypt_value reads rec["v"]. A different shape breaks decryption
    silently rather than loudly, so the shape is pinned explicitly."""
    _put(fire, "elins.k", b"envelope-bytes", ts=12.5)
    rec = mv._fire_get_one("u", "elins.k")
    assert rec == {"v": b"envelope-bytes", "ts": 12.5}
    assert set(rec) == {"v", "ts"}


def test_entry_without_a_v_field_is_treated_as_absent(fire):
    """Mirrors _fire_load_user's own defensive `if "v" not in d: continue`."""
    fire["docs"]["elins.broken"] = {"key": "elins.broken", "ts": 1.0}
    assert mv._fire_get_one("u", "elins.broken") is None


# --------------------------------------------------------------------------
# The point of the change: one read, and no collection stream.
# --------------------------------------------------------------------------
def test_vault_get_issues_exactly_one_read_and_never_streams(fire):
    for i in range(37):                      # the measured account's key count
        _put(fire, f"elins.k{i}", b"x")
    fire["_reads"].clear()
    mv._fire_get_one("u", "elins.k9")
    assert fire["_reads"] == ["elins.k9"], "more than one document was read"
    assert fire["_streams"] == [], "the entries collection was streamed"


def test_vault_get_does_not_stream_on_the_firestore_backend(fire, monkeypatch):
    """The regression guard proper: if vault_get ever routes back through
    _load_user on firestore, the amplification silently returns."""
    called = []
    monkeypatch.setattr(mv, "_load_user", lambda uid: called.append(uid) or {})
    mv.vault_get("u", "elins.anything", default=None)
    assert called == [], "vault_get called _load_user on the firestore backend"


# --------------------------------------------------------------------------
# GATE 3 — backend parity. The same behaviour on mock.
# --------------------------------------------------------------------------
@pytest.fixture
def mock_backend(monkeypatch):
    monkeypatch.setenv("CLARITYOS_VAULT_BACKEND", "mock")
    mv.vault_clear("u_parity")
    return "mock"


def test_mock_backend_round_trip_is_unchanged(mock_backend):
    """Compared against the pre-change capture: identical values, identical
    None, identical default."""
    mv.vault_init("u_parity")
    values = {"elins.a": {"n": 1, "s": "x"}, "elins.b": [1, 2, 3],
              "operator_state.c": "plain"}
    for k, v in values.items():
        mv.vault_put("u_parity", k, v)
    for k, v in values.items():
        assert mv.vault_get("u_parity", k) == v
    assert mv.vault_get("u_parity", "elins.nope") is None
    assert mv.vault_get("u_parity", "elins.nope", default="D") == "D"


def test_mock_backend_still_uses_load_user(mock_backend, monkeypatch):
    """mock/sqlite/fs load a whole file or row regardless -- there is no
    amplification to remove there, and adding a second path would be code
    for nothing."""
    seen = []
    real = mv._load_user
    monkeypatch.setattr(mv, "_load_user", lambda uid: seen.append(uid) or real(uid))
    mv.vault_get("u_parity", "elins.a")
    assert seen == ["u_parity"]


# --------------------------------------------------------------------------
# Emulator-gated, following tests/test_d1_entitlement_credit.py:129.
# Skips without FIRESTORE_EMULATOR_HOST; runs the real client when present.
# --------------------------------------------------------------------------
@pytest.mark.skipif(
    not os.environ.get("FIRESTORE_EMULATOR_HOST"),
    reason="Firestore emulator required: set FIRESTORE_EMULATOR_HOST=host:port",
)
def test_live_firestore_round_trip_and_missing_key(monkeypatch):
    monkeypatch.setenv("CLARITYOS_VAULT_BACKEND", "firestore")
    uid = "vault_one_read_probe"
    mv.vault_clear(uid)
    mv.vault_init(uid)
    mv.vault_put(uid, "elins.a", {"n": 1})
    assert mv.vault_get(uid, "elins.a") == {"n": 1}
    assert mv.vault_get(uid, "elins.absent", default="D") == "D"
    mv.vault_clear(uid)
