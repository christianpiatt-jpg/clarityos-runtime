"""
#285 + #289 -- the EL/INS store gets a floor and one key.

#285  el_ins/el_ins_store.py had no persistence branch: _backend() was defined
      and never called, every write and read touched _MEM, and "stored": True
      was true of the process only -- a container replacement emptied it.
      Now the Firestore branch is real: one document per record under the
      operator's own subcollection, so no read needs a composite index
      (none exists for an operator_id-keyed collection in production).
#289  The per-turn hook stored under the ACCOUNT NAME while every read route
      reads by the minted op_ id -- a per-turn record and an on-demand record
      for the same human landed in different buckets. Now
      users_store.operator_id_for is THE mapping; the session resolver and the
      hook both route through it, and with no op_ id the hook stores nothing,
      loudly.

The Firestore double below is the shape tests/test_v46_memory_vault.py uses
(documents keyed by path tuple; the store OUTLIVES _reset_for_tests exactly
like real Firestore) plus the query surface this store's branch needs:
where(filter=FieldFilter) / order_by / limit / stream. Its set() refuses a
nested array, as Firestore does, so a storable payload is proven, not assumed.
"""
from __future__ import annotations

import copy
import secrets
import time

import pytest
from fastapi import FastAPI

from conftest import TestClient, provision_operator

import el_ins
import sessions_store
from el_ins import el_ins_store as st


# ===========================================================================
# the Firestore double
# ===========================================================================
def _cmp(left, op, right) -> bool:
    try:
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if left is None:
            return False
        if op == ">=":
            return left >= right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == "<":
            return left < right
    except TypeError:
        return False
    raise ValueError(f"unsupported op {op!r}")


def _reject_nested_arrays(x, path="doc"):
    if isinstance(x, list):
        for i, v in enumerate(x):
            if isinstance(v, list):
                raise ValueError(f"Invalid data. Nested arrays are not supported at {path}[{i}]")
            _reject_nested_arrays(v, f"{path}[{i}]")
    elif isinstance(x, dict):
        for k, v in x.items():
            _reject_nested_arrays(v, f"{path}.{k}")


class _FakeQuery:
    def __init__(self, fs, path, filters=(), order=None, limit=None):
        self._fs, self._path = fs, path
        self._filters, self._order, self._limit = tuple(filters), order, limit

    def where(self, field=None, op=None, value=None, *, filter=None):
        if filter is not None:                      # google.cloud.firestore_v1.FieldFilter
            field, op, value = filter.field_path, filter.op_string, filter.value
        return _FakeQuery(self._fs, self._path, self._filters + ((field, op, value),),
                          self._order, self._limit)

    def order_by(self, field, direction="ASCENDING"):
        return _FakeQuery(self._fs, self._path, self._filters, (field, str(direction)), self._limit)

    def limit(self, n):
        return _FakeQuery(self._fs, self._path, self._filters, self._order, int(n))

    def stream(self):
        plen = len(self._path)
        rows = [(p, d) for p, d in list(self._fs.store.items())
                if len(p) == plen + 1 and p[:plen] == self._path]
        for field, op, value in self._filters:
            rows = [(p, d) for p, d in rows if _cmp(d.get(field), op, value)]
        if self._order:
            field, direction = self._order
            rows.sort(key=lambda pd: pd[1].get(field), reverse=("DESC" in direction.upper()))
        if self._limit is not None:
            rows = rows[: self._limit]
        for p, d in rows:
            yield _FakeSnap(p, d)


class _FakeColl(_FakeQuery):
    def document(self, doc_id):
        return _FakeDoc(self._fs, self._path + (doc_id,))


class _FakeDoc:
    def __init__(self, fs, path):
        self._fs, self._path = fs, path

    def collection(self, name):
        return _FakeColl(self._fs, self._path + (name,))

    def get(self):
        return _FakeSnap(self._path, self._fs.store.get(self._path))

    def set(self, data):
        _reject_nested_arrays(data)
        self._fs.store[self._path] = copy.deepcopy(dict(data))

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
        return copy.deepcopy(self._data) if self._data is not None else None


class _FakeFs:
    def __init__(self):
        self.store: dict = {}

    def collection(self, name):
        return _FakeColl(self, (name,))

    def paths(self, prefix=()):
        return [p for p in self.store if p[: len(prefix)] == tuple(prefix)]


@pytest.fixture
def fire(monkeypatch):
    """This store's branch flipped to Firestore against a fresh double.
    Only el_ins_store's _backend is patched, so a kernel turn in the same
    test still runs its other stores in memory."""
    fake = _FakeFs()
    monkeypatch.setattr(st, "_get_firestore", lambda: fake)
    monkeypatch.setattr(st, "_backend", lambda: "firestore")
    st._reset_for_tests()
    yield fake
    st._reset_for_tests()


def _analysis(cls="balanced", el=1.0, ins=1.0):
    return {
        "analysis": {"el_components": [], "ins_components": [],
                     "el_score": el, "ins_score": ins, "ratio_classification": cls},
        "reasoning_mode": "normal",
        "regression_chain": {"projection": None, "drivers": [], "precedents": [],
                             "principle_stack": [], "invariant": None},
        "stability_notes": None,
    }


def _rec(op, tid=None, ts=None, source="on_demand", **kw):
    return {"operator_id": op, "thread_id": tid, "timestamp": ts if ts is not None else time.time(),
            "source": source, "result": _analysis(**kw)}


# ===========================================================================
# #285 (a) -- write, replace the container, read back
# ===========================================================================
def test_a_write_restart_read_back_every_reader(fire):
    op = "op_" + secrets.token_urlsafe(6)
    t0 = time.time()
    st.store_el_ins_record(_rec(op, "t1", ts=t0 - 20, cls="high_el", el=4.0))
    st.store_el_ins_record(_rec(op, "t1", ts=t0 - 10, cls="balanced"))
    st.store_el_ins_record(_rec(op, None, ts=t0))                       # untagged (#284)
    assert st._MEM == {}                                                # nothing in the process

    st._MEM.clear(); st._reset_for_tests()                              # the container replacement

    recent = st.get_recent_el_ins(op)
    assert [r["thread_id"] for r in recent] == [None, "t1", "t1"]      # newest-first by timestamp
    assert st.get_recent_el_ins(op, limit=2)[0]["thread_id"] is None
    thread = st.get_thread_el_ins(op, "t1")
    assert len(thread) == 2 and thread[0]["result"]["analysis"]["ratio_classification"] == "balanced"
    assert len(st.get_macro_el_ins(op, since=t0 - 10)) == 2
    assert len(st.get_macro_el_ins(op)) == 3
    stab = st.compute_thread_stability(op, "t1")
    assert stab["window"] == 2 and 0 <= stab["tsi"] <= 100
    summ = st.compute_operator_summary(op)
    assert summ["sample_size"] == 3
    # #374 -- a fourth bucket. None of these three records is UNMAPPED, so
    # the count is 0 and the three real classes are unchanged: the reader
    # now sees that nothing was dropped, rather than having to assume it.
    assert summ["recent_classification_distribution"] == {
        "high_el": 1, "high_ins": 0, "balanced": 2, "unmapped": 0,
    }
    assert summ["mapped_sample_size"] == 3      # every record carried a reading
    # the layout: one document per record under the operator's subcollection
    paths = fire.paths(("el_ins_records", op, "records"))
    assert len(paths) == 3 and all(len(p) == 4 for p in paths)
    docs = [fire.store[p] for p in paths]
    assert all(isinstance(d.get("tsi"), int) for d in docs if d["thread_id"] == "t1")   # stamped before the write
    assert all("tsi" not in d for d in docs if d["thread_id"] is None)                # no thread, no TSI
    assert st.get_recent_el_ins("op_someone_else") == []


def test_a2_under_the_env_var_the_other_stores_read(monkeypatch):
    """The letter of the order: CLARITYOS_BACKEND=firestore, the store alone."""
    fake = _FakeFs()
    monkeypatch.setattr(st, "_get_firestore", lambda: fake)
    monkeypatch.setenv("CLARITYOS_BACKEND", "firestore")
    st._reset_for_tests()
    op = "op_envvar"
    st.store_el_ins_record(_rec(op, "t9"))
    st._MEM.clear()
    assert st._backend() == "firestore"
    assert len(st.get_recent_el_ins(op)) == 1 and fire_paths(fake, op) == 1
    st._reset_for_tests()


def fire_paths(fake, op):
    return len(fake.paths(("el_ins_records", op, "records")))


def test_a3_same_millisecond_writes_do_not_overwrite(fire):
    op = "op_burst"
    ts = time.time()
    for _ in range(3):
        st.store_el_ins_record(_rec(op, "t1", ts=ts))
    assert fire_paths(fire, op) == 3
    assert len(st.get_thread_el_ins(op, "t1")) == 3


def test_a4_the_real_analyzer_output_is_storable(fire):
    """The double's set() refuses nested arrays as Firestore does; a real
    analyzer result must pass through it."""
    op = "op_real"
    result = el_ins.analyze_text("catastrophic disaster doom; the statute and the testimony",
                                 provider_mode="deterministic")
    st.store_el_ins_record({"operator_id": op, "thread_id": "t1", "timestamp": time.time(),
                            "source": "on_demand", "result": dict(result)})
    assert fire_paths(fire, op) == 1


def test_a5_the_memory_branch_is_untouched_and_reset_stays_memory_only(fire):
    op = "op_mem"
    st.store_el_ins_record(_rec(op, "t1"))
    st._reset_for_tests()                                  # memory-only: the double keeps its doc
    assert fire_paths(fire, op) == 1


# ===========================================================================
# #285 (c) -- thread_id=None stores and reads
# ===========================================================================
def test_c_untagged_record_stores_and_reads_under_firestore(fire):
    op = "op_untagged"
    st.store_el_ins_record(_rec(op, None))
    st._MEM.clear()
    rows = st.get_recent_el_ins(op)
    assert len(rows) == 1 and rows[0]["thread_id"] is None and "tsi" not in rows[0]
    assert st.get_thread_el_ins(op, "t1") == []           # a thread read never sees it
    assert st.compute_operator_summary(op)["sample_size"] == 1
    doc = fire.store[fire.paths(("el_ins_records", op, "records"))[0]]
    assert doc["thread_id"] is None                        # null in the document, never ""


# ===========================================================================
# #289 -- one key
# ===========================================================================
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


def _stub_router(monkeypatch):
    import model_router as mr
    monkeypatch.setattr(
        mr, "route_request",
        lambda model_id, prompt, **kw: {"ok": True, "text": "(mock reply)", "model_id": model_id,
                                       "provider": "mock", "mock": True, "ts": time.time()},
    )


def _router_client():
    from runtime_http import el_ins_router
    app = FastAPI()
    app.include_router(el_ins_router)
    return TestClient(app)


def _session(user):
    sid = "sess_" + secrets.token_urlsafe(12)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def _one_key_flow(monkeypatch, user="writer@example.com", op="op_w1"):
    """A per-turn write (the kernel hook) and an on-demand write (the route)
    for the same human; returns the router client + session headers."""
    import intelligence_kernel as ik
    import operator_state
    import threads_vault
    provision_operator(user, op)
    _stub_router(monkeypatch)
    operator_state.set_el_ins_per_turn(user, True)
    tid = threads_vault.create_thread(user, title="lease")["thread_id"]
    ik.run_thread_message(user, tid, "catastrophic disaster doom")
    client = _router_client()
    h = _session(user)
    r = client.post("/el_ins/analyze", json={"text": "statute clause testimony",
                                             "provider_mode": "deterministic"}, headers=h)
    assert r.status_code == 200, r.text
    return client, h, tid


def test_b_per_turn_and_on_demand_land_in_the_same_bucket(reset_stores, monkeypatch):
    client, h, tid = _one_key_flow(monkeypatch)
    rows = st.get_recent_el_ins("op_w1")
    assert sorted(r["source"] for r in rows) == ["on_demand", "per_turn"]
    assert all(r["operator_id"] == "op_w1" for r in rows)
    assert st.get_recent_el_ins("writer@example.com") == []          # the address is a key of nothing
    assert "writer@example.com" not in st._MEM
    assert all("@" not in k for k in st._MEM)
    # the route reads the same bucket: RECENT shows the turn (what CT-1 never saw)
    api = client.get("/el_ins/recent", headers=h).json()["records"]
    assert sorted(r["source"] for r in api) == ["on_demand", "per_turn"]
    assert client.get(f"/el_ins/thread/{tid}", headers=h).json()["records"][0]["source"] == "per_turn"
    # the hook's sibling writes take the same key: the record event is readable by op_ id
    events = el_ins.list_events("op_w1")
    assert any(e["event_type"] == "record" and e["payload"]["thread_id"] == tid for e in events)
    assert el_ins.list_events("writer@example.com") == []


def test_b2_the_same_flow_under_firestore(reset_stores, monkeypatch, fire):
    client, h, tid = _one_key_flow(monkeypatch, user="writer2@example.com", op="op_w2")
    assert fire_paths(fire, "op_w2") == 2
    assert fire_paths(fire, "writer2@example.com") == 0
    assert all("@" not in p[1] for p in fire.paths(("el_ins_records",)))
    api = client.get("/el_ins/recent", headers=h).json()["records"]
    assert sorted(r["source"] for r in api) == ["on_demand", "per_turn"]
    stab = client.get(f"/el_ins/thread/{tid}/stability", headers=h).json()
    assert stab["window"] == 1 and stab["thread_id"] == tid


def test_289_operator_id_for_is_the_mapping():
    import users_store
    assert users_store.operator_id_for("nobody_" + secrets.token_hex(3)) is None
    u = "mapped_" + secrets.token_hex(3)
    provision_operator(u, "op_mapped")
    assert users_store.operator_id_for(u) == "op_mapped"
    users_store.update_user(u, {"operator_id": ""})
    assert users_store.operator_id_for(u) is None              # blank is absent
    users_store.update_user(u, {"operator_id": 42})
    assert users_store.operator_id_for(u) is None              # a non-string is absent


def test_289_the_session_resolver_routes_through_the_one_mapping(monkeypatch):
    import runtime_http as rh
    import users_store
    from fastapi import HTTPException
    u = "routed_" + secrets.token_hex(3)
    h = _session(u)                                            # conftest backfills op == user
    assert rh._resolve_authed_identity(h["X-Session-ID"]) == (u, u)
    monkeypatch.setattr(users_store, "operator_id_for", lambda username: "op_sentinel")
    assert rh._resolve_authed_identity(h["X-Session-ID"]) == (u, "op_sentinel")   # one function, not two lookups
    monkeypatch.setattr(users_store, "operator_id_for", lambda username: None)
    with pytest.raises(HTTPException) as ei:
        rh._resolve_authed_identity(h["X-Session-ID"])
    assert ei.value.status_code == 409                         # the resolver's refusal is unchanged


def test_289_without_an_op_id_the_hook_stores_nothing_and_says_so(reset_stores, monkeypatch, caplog):
    import intelligence_kernel as ik
    import logging
    import operator_state
    import threads_vault
    user = "unminted@example.com"                              # a doc without an operator_id
    import users_store
    users_store.create_user(user, password_hash=b"", salt="", tier="member", created_at=time.time())
    _stub_router(monkeypatch)
    operator_state.set_el_ins_per_turn(user, True)
    tid = threads_vault.create_thread(user, title="t")["thread_id"]
    caplog.set_level(logging.WARNING, logger="clarityos.intelligence_kernel")
    caplog.set_level(logging.WARNING)
    out = ik.run_thread_message(user, tid, "catastrophic")
    assert out["assistant_message"]["content"]                 # the turn is never the cost
    assert st.get_recent_el_ins(user) == [] and st._MEM == {}  # nothing stored under the address
    assert el_ins.list_events(user) == []
    lines = [r.getMessage() for r in caplog.records if "el_ins per-turn: no operator_id" in r.getMessage()]
    assert len(lines) == 1
    assert "user_ref=" in lines[0] and "unminted@example.com" not in lines[0]   # a hash, never the address
    assert "unminted@example.com" not in caplog.text


def test_289_the_flag_off_path_is_unchanged(reset_stores, monkeypatch):
    import intelligence_kernel as ik
    import threads_vault
    provision_operator("quiet@example.com", "op_q")
    _stub_router(monkeypatch)
    tid = threads_vault.create_thread("quiet@example.com", title="t")["thread_id"]
    ik.run_thread_message("quiet@example.com", tid, "catastrophic")
    assert st.get_recent_el_ins("op_q") == [] and st._MEM == {}


def test_285_a_floor_failure_is_loud_and_never_the_turns_cost(reset_stores, monkeypatch, caplog):
    """Under Firestore a write can fail for reasons outside the process. The
    hook stays fail-soft (the turn is answered) and becomes LOUD: one WARNING
    with the step and the exception TYPE -- never its message (a google error
    names the document path and the project), never the address."""
    import intelligence_kernel as ik
    import logging
    import operator_state
    import threads_vault
    user = "floor@example.com"
    provision_operator(user, "op_floor")
    _stub_router(monkeypatch)
    operator_state.set_el_ins_per_turn(user, True)
    tid = threads_vault.create_thread(user, title="t")["thread_id"]

    def _boom(record):
        raise RuntimeError("Could not initialise Firestore client: projects/founding-os/databases/(default)")
    monkeypatch.setattr(el_ins, "store_el_ins_record", _boom)      # the package name the kernel calls
    caplog.set_level(logging.WARNING)
    out = ik.run_thread_message(user, tid, "catastrophic")
    assert out["assistant_message"]["content"]                       # the turn is answered
    lines = [r.getMessage() for r in caplog.records
             if r.levelno >= logging.WARNING and "el_ins per-turn: store step failed" in r.getMessage()]
    assert len(lines) == 1
    assert "err=RuntimeError" in lines[0] and "user_ref=" in lines[0]
    assert "founding-os" not in caplog.text                          # the message never rides
    assert "floor@example.com" not in caplog.text                    # the address never rides
    assert st.get_recent_el_ins("op_floor") == []
