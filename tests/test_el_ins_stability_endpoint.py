"""
Tests for v70 / Unit 76 + 77 — /el_ins/thread/{tid}/stability and
/el_ins/operator/summary HTTP endpoints.

Covers:
    A. Auth gate on both endpoints
    B. /thread/{tid}/stability response shape + behaviour
    C. /operator/summary response shape + behaviour
    D. Cross-operator isolation
    E. Query-parameter handling (window, sample_size)
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from conftest import TestClient

import el_ins
import runtime_http as rh_mod
import sessions_store


def _mk(cls: str, el: float, ins: float, mode: str = "normal") -> dict:
    if mode == "normal" and cls != "balanced":
        mode = "stabilize" if cls == "high_el" else "expand"
    return {
        "analysis": {
            "el_components": [], "ins_components": [],
            "el_score": el, "ins_score": ins,
            "ratio_classification": cls,
        },
        "reasoning_mode": mode,
        "regression_chain": {
            "projection": None, "drivers": [], "precedents": [],
            "principle_stack": [], "invariant": None,
        },
        "stability_notes": None,
    }


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rh_mod.el_ins_router)
    el_ins._reset_for_tests()
    yield TestClient(app)
    el_ins._reset_for_tests()


def _auth(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-elins-stab-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def _seed_thread(operator: str, thread_id: str, n: int = 6, mode: str = "rising_el"):
    for i in range(n):
        if mode == "rising_el":
            el = 4.0 + i
            ins = 1.0
            cls = "high_el"
        elif mode == "balanced":
            el = 2.0
            ins = 2.0
            cls = "balanced"
        else:
            el = 1.0
            ins = 4.0 + i
            cls = "high_ins"
        el_ins.store_el_ins_record({
            "operator_id": operator, "thread_id": thread_id,
            "timestamp":   float(1000 + i),
            "source":      "on_demand",
            "result":      _mk(cls, el, ins),
        })


# ===========================================================================
# A. Auth gate
# ===========================================================================
class TestAuth:
    def test_unauthed_stability_returns_401(self, client):
        r = client.get("/el_ins/thread/t1/stability")
        assert r.status_code == 401

    def test_unauthed_summary_returns_401(self, client):
        r = client.get("/el_ins/operator/summary")
        assert r.status_code == 401


# ===========================================================================
# B. /thread/{tid}/stability
# ===========================================================================
class TestStabilityEndpoint:
    def test_shape_locked(self, client):
        _seed_thread("op_alice", "t1", n=4, mode="balanced")
        r = client.get("/el_ins/thread/t1/stability", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"thread_id", "stability", "tsi", "window"}

    def test_stable_thread_returns_stable(self, client):
        _seed_thread("op_alice", "t1", n=6, mode="balanced")
        body = client.get(
            "/el_ins/thread/t1/stability", headers=_auth(),
        ).json()
        assert body["stability"] == "stable"

    def test_drifting_el_thread(self, client):
        _seed_thread("op_alice", "t1", n=6, mode="rising_el")
        body = client.get(
            "/el_ins/thread/t1/stability", headers=_auth(),
        ).json()
        assert body["stability"] == "drifting_el"

    def test_drifting_ins_thread(self, client):
        _seed_thread("op_alice", "t1", n=6, mode="rising_ins")
        body = client.get(
            "/el_ins/thread/t1/stability", headers=_auth(),
        ).json()
        assert body["stability"] == "drifting_ins"

    def test_empty_thread_returns_stable_defaults(self, client):
        body = client.get(
            "/el_ins/thread/ghost/stability", headers=_auth(),
        ).json()
        assert body["stability"] == "stable"
        assert body["tsi"] == 100
        assert body["window"] == 0

    def test_window_query_param_honoured(self, client):
        for i in range(20):
            el_ins.store_el_ins_record({
                "operator_id": "op_alice", "thread_id": "t1",
                "timestamp": float(1000 + i),
                "source": "on_demand",
                "result": _mk("balanced", 2.0, 2.0),
            })
        body = client.get(
            "/el_ins/thread/t1/stability?window=5", headers=_auth(),
        ).json()
        assert body["window"] == 5

    def test_tsi_in_range(self, client):
        _seed_thread("op_alice", "t1", n=10)
        body = client.get(
            "/el_ins/thread/t1/stability", headers=_auth(),
        ).json()
        assert 0 <= body["tsi"] <= 100


# ===========================================================================
# C. /operator/summary
# ===========================================================================
class TestOperatorSummaryEndpoint:
    def test_shape_locked(self, client):
        _seed_thread("op_alice", "t1", n=4)
        r = client.get("/el_ins/operator/summary", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {
            "recent_classification_distribution",
            "avg_tsi",
            "trend",
            "sample_size",
        }
        assert set(body["recent_classification_distribution"].keys()) == {
            "high_el", "high_ins", "balanced",
        }

    def test_distribution_counts_correct(self, client):
        # 3 high_el, 2 balanced.
        for i in range(3):
            el_ins.store_el_ins_record({
                "operator_id": "op_alice", "thread_id": "t1",
                "timestamp": float(1000 + i),
                "source": "on_demand",
                "result": _mk("high_el", 8.0, 1.0),
            })
        for i in range(2):
            el_ins.store_el_ins_record({
                "operator_id": "op_alice", "thread_id": "t1",
                "timestamp": float(2000 + i),
                "source": "on_demand",
                "result": _mk("balanced", 2.0, 2.0),
            })
        body = client.get(
            "/el_ins/operator/summary", headers=_auth(),
        ).json()
        d = body["recent_classification_distribution"]
        assert d["high_el"] == 3
        assert d["balanced"] == 2
        assert d["high_ins"] == 0
        assert body["sample_size"] == 5

    def test_avg_tsi_in_range(self, client):
        _seed_thread("op_alice", "t1", n=6)
        body = client.get(
            "/el_ins/operator/summary", headers=_auth(),
        ).json()
        assert 0 <= body["avg_tsi"] <= 100

    def test_no_records_returns_zero_summary(self, client):
        body = client.get(
            "/el_ins/operator/summary", headers=_auth(),
        ).json()
        assert body["sample_size"] == 0
        assert body["avg_tsi"] == 0
        assert body["trend"] == "stable"
        d = body["recent_classification_distribution"]
        assert d == {"high_el": 0, "high_ins": 0, "balanced": 0}

    def test_sample_size_query_param_honoured(self, client):
        for i in range(30):
            el_ins.store_el_ins_record({
                "operator_id": "op_alice", "thread_id": "t1",
                "timestamp": float(1000 + i),
                "source": "on_demand",
                "result": _mk("balanced", 2.0, 2.0),
            })
        body = client.get(
            "/el_ins/operator/summary?sample_size=10", headers=_auth(),
        ).json()
        assert body["sample_size"] == 10


# ===========================================================================
# D. Cross-operator isolation
# ===========================================================================
class TestCrossOperatorIsolation:
    def test_alice_cannot_see_bobs_stability(self, client):
        _seed_thread("op_bob", "t1", n=6, mode="rising_el")
        # Alice queries her own thread t1 — no records, returns stable.
        alice = client.get(
            "/el_ins/thread/t1/stability", headers=_auth("op_alice"),
        ).json()
        assert alice["window"] == 0
        # Bob's thread is drifting.
        bob = client.get(
            "/el_ins/thread/t1/stability", headers=_auth("op_bob"),
        ).json()
        assert bob["stability"] == "drifting_el"

    def test_alice_cannot_see_bobs_summary(self, client):
        _seed_thread("op_bob", "t1", n=6, mode="rising_el")
        alice = client.get(
            "/el_ins/operator/summary", headers=_auth("op_alice"),
        ).json()
        assert alice["sample_size"] == 0
        bob = client.get(
            "/el_ins/operator/summary", headers=_auth("op_bob"),
        ).json()
        assert bob["sample_size"] == 6
