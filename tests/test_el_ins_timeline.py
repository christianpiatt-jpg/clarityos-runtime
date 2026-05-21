"""
Tests for v73 / Unit 82 — el_ins.timeline + endpoints.

Covers:
    A. _validate shape locks
    B. store + list + list_since + get
    C. event builders (record / anomaly / rollup)
    D. Kernel integration (run_thread_message emits record + anomaly events)
    E. Rollup endpoint integration (emits rollup event for the requester)
    F. HTTP endpoints (auth, shape, cross-operator 404)
    G. Cross-operator isolation
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from conftest import TestClient

import el_ins
import intelligence_kernel as ik
import model_router as mr
import operator_state
import runtime_http as rh_mod
import sessions_store
import threads_vault


def _mk(cls: str, el: float, ins: float) -> dict:
    return {
        "analysis": {
            "el_components": [], "ins_components": [],
            "el_score": el, "ins_score": ins,
            "ratio_classification": cls,
        },
        "reasoning_mode": "normal",
        "regression_chain": {
            "projection": None, "drivers": [], "precedents": [],
            "principle_stack": [], "invariant": None,
        },
        "stability_notes": None,
    }


@pytest.fixture(autouse=True)
def _isolate():
    import memory_vault
    el_ins._reset_all_for_tests()
    memory_vault._reset_for_tests()
    yield
    el_ins._reset_all_for_tests()
    memory_vault._reset_for_tests()


# ===========================================================================
# A. Validation
# ===========================================================================
class TestValidation:
    def test_missing_operator_id_raises(self):
        with pytest.raises(ValueError):
            el_ins.store_event({
                "operator_id": "",
                "event_type": "record",
                "payload": {},
            })

    def test_unknown_event_type_raises(self):
        with pytest.raises(ValueError):
            el_ins.store_event({
                "operator_id": "alice",
                "event_type": "garbage",
                "payload": {},
            })

    def test_non_dict_payload_raises(self):
        with pytest.raises(ValueError):
            el_ins.store_event({
                "operator_id": "alice",
                "event_type": "record",
                "payload": "not-a-dict",  # type: ignore[arg-type]
            })

    def test_missing_timestamp_defaults_to_now(self):
        ev = el_ins.store_event({
            "operator_id": "alice",
            "event_type": "system",
            "payload": {},
        })
        # Stamped in milliseconds — within the last 2s of "now".
        now_ms = int(time.time() * 1000)
        assert abs(ev["timestamp_ms"] - now_ms) < 2000

    def test_supplied_id_preserved(self):
        ev = el_ins.store_event({
            "id": "fixed-id-001",
            "operator_id": "alice",
            "event_type": "system",
            "payload": {},
        })
        assert ev["id"] == "fixed-id-001"

    def test_id_defaults_to_uuid_hex(self):
        ev = el_ins.store_event({
            "operator_id": "alice",
            "event_type": "system",
            "payload": {},
        })
        assert len(ev["id"]) == 32   # uuid4 hex
        assert all(c in "0123456789abcdef" for c in ev["id"])

    def test_all_four_event_types_accepted(self):
        for t in ("record", "anomaly", "rollup", "system"):
            el_ins.store_event({
                "operator_id": "alice", "event_type": t, "payload": {},
            })
        assert len(el_ins.list_events("alice")) == 4


# ===========================================================================
# B. Store + retrieval
# ===========================================================================
class TestStoreRetrieval:
    def test_newest_first(self):
        for i in range(3):
            el_ins.store_event({
                "operator_id": "alice",
                "event_type": "system",
                "payload": {"i": i},
                "timestamp_ms": 1700000000000 + i,
            })
        rows = el_ins.list_events("alice")
        assert [r["timestamp_ms"] for r in rows] == [
            1700000000002, 1700000000001, 1700000000000,
        ]

    def test_limit_clamped_high(self):
        for i in range(5):
            el_ins.store_event({
                "operator_id": "alice", "event_type": "system",
                "payload": {}, "timestamp_ms": 1700000000000 + i,
            })
        rows = el_ins.list_events("alice", limit=99999)
        assert len(rows) == 5

    def test_limit_clamped_low(self):
        for i in range(5):
            el_ins.store_event({
                "operator_id": "alice", "event_type": "system",
                "payload": {}, "timestamp_ms": 1700000000000 + i,
            })
        rows = el_ins.list_events("alice", limit=0)
        assert len(rows) == 1  # clamped to >= 1

    def test_list_since(self):
        for i in range(5):
            el_ins.store_event({
                "operator_id": "alice", "event_type": "system",
                "payload": {}, "timestamp_ms": 1700000000000 + i,
            })
        rows = el_ins.list_events_since("alice", 1700000000002)
        assert len(rows) == 3   # i=2,3,4

    def test_get_by_id(self):
        ev = el_ins.store_event({
            "operator_id": "alice", "event_type": "system", "payload": {},
        })
        out = el_ins.get_event("alice", ev["id"])
        assert out is not None
        assert out["id"] == ev["id"]

    def test_get_unknown_returns_none(self):
        assert el_ins.get_event("alice", "nope") is None

    def test_validate_raises_on_empty_operator_for_list(self):
        with pytest.raises(ValueError):
            el_ins.list_events("")

    def test_list_unknown_operator_returns_empty(self):
        assert el_ins.list_events("ghost") == []


# ===========================================================================
# C. Event builders
# ===========================================================================
class TestBuilders:
    def test_record_event_shape(self):
        ev = el_ins.build_record_event(
            "alice", el=8.0, ins=1.0, tsi=90,
            reasoning_mode="grounding", thread_id="t1",
        )
        assert ev["event_type"] == "record"
        assert ev["operator_id"] == "alice"
        p = ev["payload"]
        assert p["el"] == 8.0
        assert p["ins"] == 1.0
        assert p["tsi"] == 90
        assert p["reasoning_mode"] == "grounding"
        assert p["thread_id"] == "t1"

    def test_anomaly_event_shape(self):
        ev = el_ins.build_anomaly_event(
            "alice", anomaly_id="a1", anomaly_type="high_el",
            severity=3, message="msg",
        )
        assert ev["event_type"] == "anomaly"
        p = ev["payload"]
        assert p["anomaly_id"] == "a1"
        assert p["type"] == "high_el"
        assert p["severity"] == 3
        assert p["message"] == "msg"

    def test_rollup_event_shape(self):
        ev = el_ins.build_rollup_event(
            "alice", window="24h", avg_el=3.0, avg_ins=4.0,
            avg_tsi=75, record_count=10,
        )
        assert ev["event_type"] == "rollup"
        p = ev["payload"]
        assert p["window"] == "24h"
        assert p["avg_el"] == 3.0
        assert p["avg_ins"] == 4.0
        assert p["avg_tsi"] == 75
        assert p["record_count"] == 10


# ===========================================================================
# D. Kernel integration
# ===========================================================================
class TestKernelIntegration:
    @pytest.fixture(autouse=True)
    def _stub_router(self, monkeypatch):
        monkeypatch.setattr(
            mr, "route_request",
            lambda model_id, prompt, **kw: {
                "ok": True, "text": "(mock reply)", "model_id": model_id,
                "provider": "mock", "mock": True, "ts": time.time(),
            },
        )
        yield

    def test_per_turn_off_no_timeline_events(self):
        tid = threads_vault.create_thread("alice", title="t")["thread_id"]
        ik.run_thread_message("alice", tid, "any text")
        assert el_ins.list_events("alice") == []

    def test_per_turn_on_emits_record_event(self):
        operator_state.set_el_ins_per_turn("alice", True)
        tid = threads_vault.create_thread("alice", title="t")["thread_id"]
        ik.run_thread_message("alice", tid, "neutral content")
        events = el_ins.list_events("alice")
        record_events = [e for e in events if e["event_type"] == "record"]
        assert len(record_events) == 1
        p = record_events[0]["payload"]
        assert "el" in p and "ins" in p and "reasoning_mode" in p

    def test_per_turn_on_high_el_emits_record_and_anomaly_events(self):
        operator_state.set_el_ins_per_turn("alice", True)
        tid = threads_vault.create_thread("alice", title="t")["thread_id"]
        ik.run_thread_message(
            "alice", tid,
            "catastrophic disaster doom panic obviously crisis terrible horrifying urgent",
        )
        events = el_ins.list_events("alice")
        types = {e["event_type"] for e in events}
        assert "record" in types
        assert "anomaly" in types


# ===========================================================================
# E. Rollup endpoint integration
# ===========================================================================
@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rh_mod.el_ins_router)
    app.include_router(rh_mod.timeline_router)
    el_ins._reset_all_for_tests()
    yield TestClient(app)
    el_ins._reset_all_for_tests()


def _auth(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-tl-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


class TestRollupEmitsTimelineEvent:
    def test_rollup_24h_emits_event(self, client):
        client.get("/el_ins/rollup/24h", headers=_auth())
        events = el_ins.list_events("op_alice")
        rollup_events = [e for e in events if e["event_type"] == "rollup"]
        assert len(rollup_events) == 1
        assert rollup_events[0]["payload"]["window"] == "24h"

    def test_rollup_7d_emits_event(self, client):
        client.get("/el_ins/rollup/7d", headers=_auth())
        events = el_ins.list_events("op_alice")
        assert any(e["payload"].get("window") == "7d" for e in events)

    def test_rollup_30d_emits_event(self, client):
        client.get("/el_ins/rollup/30d", headers=_auth())
        events = el_ins.list_events("op_alice")
        assert any(e["payload"].get("window") == "30d" for e in events)


# ===========================================================================
# F. HTTP endpoints
# ===========================================================================
class TestTimelineEndpoints:
    def test_list_unauthed_returns_401(self, client):
        assert client.get("/timeline").status_code == 401

    def test_since_unauthed_returns_401(self, client):
        assert client.get("/timeline/since/1700000000000").status_code == 401

    def test_get_unauthed_returns_401(self, client):
        assert client.get("/timeline/abc").status_code == 401

    def test_authed_list_empty_returns_empty_events(self, client):
        r = client.get("/timeline", headers=_auth())
        assert r.status_code == 200
        assert r.json() == {"operator_id": "op_alice", "events": []}

    def test_authed_list_returns_events(self, client):
        for _ in range(3):
            el_ins.store_event({
                "operator_id": "op_alice", "event_type": "system", "payload": {},
            })
        r = client.get("/timeline", headers=_auth())
        assert r.status_code == 200
        assert len(r.json()["events"]) == 3

    def test_limit_query_param(self, client):
        for _ in range(5):
            el_ins.store_event({
                "operator_id": "op_alice", "event_type": "system", "payload": {},
            })
        r = client.get("/timeline?limit=2", headers=_auth())
        assert len(r.json()["events"]) == 2

    def test_since_endpoint(self, client):
        for i in range(5):
            el_ins.store_event({
                "operator_id": "op_alice", "event_type": "system",
                "payload": {}, "timestamp_ms": 1700000000000 + i,
            })
        r = client.get("/timeline/since/1700000000003", headers=_auth())
        body = r.json()
        assert body["since_ms"] == 1700000000003
        assert len(body["events"]) == 2

    def test_get_by_id_authed(self, client):
        ev = el_ins.store_event({
            "operator_id": "op_alice", "event_type": "system", "payload": {},
        })
        r = client.get(f"/timeline/{ev['id']}", headers=_auth())
        assert r.status_code == 200
        assert r.json()["id"] == ev["id"]

    def test_get_unknown_returns_404(self, client):
        r = client.get("/timeline/nonexistent-id-12345", headers=_auth())
        assert r.status_code == 404


# ===========================================================================
# G. Cross-operator isolation
# ===========================================================================
class TestCrossOperatorIsolation:
    def test_alice_cannot_list_bobs_events(self, client):
        el_ins.store_event({
            "operator_id": "op_bob", "event_type": "system", "payload": {},
        })
        r = client.get("/timeline", headers=_auth("op_alice"))
        assert r.json()["events"] == []
        # Bob sees his own.
        r2 = client.get("/timeline", headers=_auth("op_bob"))
        assert len(r2.json()["events"]) == 1

    def test_alice_cannot_fetch_bobs_event_by_id(self, client):
        ev = el_ins.store_event({
            "operator_id": "op_bob", "event_type": "system", "payload": {},
        })
        r = client.get(f"/timeline/{ev['id']}", headers=_auth("op_alice"))
        # 404 not 403 — don't leak existence.
        assert r.status_code == 404
