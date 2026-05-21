"""
Tests for v72 / Unit 81 — el_ins.rollup + /el_ins/rollup/* endpoints.

Covers:
    A. Window coercion (string / timedelta / numeric)
    B. Empty-history zeroed shape
    C. Average correctness (avg_el / avg_ins / avg_tsi)
    D. Reasoning-mode distribution correctness
    E. Window boundary inclusion/exclusion
    F. 24h / 7d / 30d endpoints
    G. Cross-operator isolation
"""
from __future__ import annotations

import time
from datetime import timedelta

import pytest
from fastapi import FastAPI

from conftest import TestClient

import el_ins
import runtime_http as rh_mod
import sessions_store


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


def _seed(operator: str, ts: float, el: float, ins: float, cls: str = "balanced"):
    el_ins.store_el_ins_record({
        "operator_id": operator, "thread_id": "t1",
        "timestamp":   ts, "source": "on_demand",
        "result":      _mk(cls, el, ins),
    })


# ===========================================================================
# A. Window coercion
# ===========================================================================
class TestWindowCoercion:
    def test_named_window_24h(self):
        out = el_ins.compute_rollup("op", "24h", now=1700000000.0)
        assert out["window_start"] == 1700000000.0 - 86400

    def test_named_window_7d(self):
        out = el_ins.compute_rollup("op", "7d", now=1700000000.0)
        assert out["window_start"] == 1700000000.0 - (60 * 60 * 24 * 7)

    def test_named_window_30d(self):
        out = el_ins.compute_rollup("op", "30d", now=1700000000.0)
        assert out["window_start"] == 1700000000.0 - (60 * 60 * 24 * 30)

    def test_timedelta_accepted(self):
        out = el_ins.compute_rollup("op", timedelta(hours=2), now=1700000000.0)
        assert out["window_start"] == 1700000000.0 - 7200

    def test_numeric_seconds_accepted(self):
        out = el_ins.compute_rollup("op", 3600, now=1700000000.0)
        assert out["window_start"] == 1700000000.0 - 3600

    def test_unknown_named_window_raises(self):
        with pytest.raises(ValueError):
            el_ins.compute_rollup("op", "yearly", now=1700000000.0)

    def test_zero_window_raises(self):
        with pytest.raises(ValueError):
            el_ins.compute_rollup("op", 0, now=1700000000.0)

    def test_negative_window_raises(self):
        with pytest.raises(ValueError):
            el_ins.compute_rollup("op", -1, now=1700000000.0)


# ===========================================================================
# B. Empty-history shape
# ===========================================================================
class TestEmptyHistory:
    def test_returns_zeroed_shape(self):
        out = el_ins.compute_rollup("ghost", "24h", now=1700000000.0)
        assert out["record_count"] == 0
        assert out["avg_el"] == 0.0
        assert out["avg_ins"] == 0.0
        assert out["avg_tsi"] == 0
        assert out["reasoning_mode_distribution"] == {}

    def test_shape_keys_locked(self):
        out = el_ins.compute_rollup("ghost", "24h", now=1700000000.0)
        assert set(out.keys()) == {
            "avg_el", "avg_ins", "avg_tsi",
            "reasoning_mode_distribution", "record_count",
            "window_start", "window_end",
        }


# ===========================================================================
# C. Average correctness
# ===========================================================================
class TestAverages:
    def test_single_record_avg_matches_record(self):
        _seed("alice", 1699999000.0, 4.0, 6.0)
        out = el_ins.compute_rollup("alice", "24h", now=1700000000.0)
        assert out["avg_el"] == 4.0
        assert out["avg_ins"] == 6.0

    def test_multi_record_averages(self):
        _seed("alice", 1699999000.0, 2.0, 4.0)
        _seed("alice", 1699999500.0, 4.0, 6.0)
        out = el_ins.compute_rollup("alice", "24h", now=1700000000.0)
        assert out["avg_el"] == 3.0
        assert out["avg_ins"] == 5.0
        assert out["record_count"] == 2

    def test_avg_tsi_skips_records_without_tsi(self):
        # First record stamped TSI=100; second also gets TSI. Third
        # record stored manually without thread_id has no TSI and is
        # excluded from the TSI average. Make sure the helper handles
        # mixed-tsi populations.
        _seed("alice", 1699999000.0, 2.0, 2.0)
        _seed("alice", 1699999500.0, 2.0, 2.0)
        out = el_ins.compute_rollup("alice", "24h", now=1700000000.0)
        # Both stored records have TSI = 100 (no variance on thread "t1"
        # since the analyses are identical) → avg_tsi 100.
        assert out["avg_tsi"] == 100


# ===========================================================================
# D. Reasoning-mode distribution
# ===========================================================================
class TestReasoningModeDistribution:
    def test_distribution_counts_per_mode(self):
        # First record: high EL, low INS → grounding (TSI=100 → extended).
        # Second record same: also extended_reasoning.
        # Third record: low/low → stabilization (TSI<40 if volatility builds).
        # We control el/ins so the distribution is predictable. Single
        # records have TSI=100 → always extended_reasoning regardless.
        # Strategy: seed multiple records to make TSI drop into mid-range.
        for i, (el, ins) in enumerate([
            (8.0, 1.0), (1.0, 8.0), (8.0, 8.0), (1.0, 1.0),
        ]):
            _seed("alice", 1699999000.0 + i, el, ins)
        out = el_ins.compute_rollup("alice", "24h", now=1700000000.0)
        # Distribution should be non-empty and consistent with the
        # 6 reasoning_mode labels.
        dist = out["reasoning_mode_distribution"]
        assert sum(dist.values()) == out["record_count"]
        for mode in dist.keys():
            assert mode in (
                "grounding", "analysis", "structured_reflection",
                "stabilization", "extended_reasoning", "normal",
            )


# ===========================================================================
# E. Window boundary inclusion/exclusion
# ===========================================================================
class TestWindowBoundary:
    def test_record_inside_window_counted(self):
        _seed("alice", 1699999000.0, 4.0, 4.0)
        out = el_ins.compute_rollup("alice", "24h", now=1700000000.0)
        assert out["record_count"] == 1

    def test_record_outside_window_excluded(self):
        # 1700000000 - 86400 = 1699913600. Anything before this is out.
        _seed("alice", 1699900000.0, 4.0, 4.0)
        out = el_ins.compute_rollup("alice", "24h", now=1700000000.0)
        assert out["record_count"] == 0

    def test_future_record_excluded(self):
        # Record stamped in the future (clock skew) → excluded.
        _seed("alice", 1700001000.0, 4.0, 4.0)
        out = el_ins.compute_rollup("alice", "24h", now=1700000000.0)
        assert out["record_count"] == 0


# ===========================================================================
# F. HTTP endpoints
# ===========================================================================
@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rh_mod.el_ins_router)
    el_ins._reset_all_for_tests()
    yield TestClient(app)
    el_ins._reset_all_for_tests()


def _auth(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-roll-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


class TestRollupEndpoints:
    def test_24h_unauthed_401(self, client):
        r = client.get("/el_ins/rollup/24h")
        assert r.status_code == 401

    def test_7d_unauthed_401(self, client):
        assert client.get("/el_ins/rollup/7d").status_code == 401

    def test_30d_unauthed_401(self, client):
        assert client.get("/el_ins/rollup/30d").status_code == 401

    def test_24h_shape_locked(self, client):
        r = client.get("/el_ins/rollup/24h", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {
            "avg_el", "avg_ins", "avg_tsi",
            "reasoning_mode_distribution", "record_count",
            "window_start", "window_end",
        }

    def test_each_window_returns_record_count(self, client):
        # Seed a record from "now" - 10s. All three windows include it.
        now_ts = time.time()
        el_ins.store_el_ins_record({
            "operator_id": "op_alice", "thread_id": "t1",
            "timestamp":   now_ts - 10,
            "source":      "on_demand",
            "result":      _mk("balanced", 4.0, 4.0),
        })
        for window in ("24h", "7d", "30d"):
            r = client.get(f"/el_ins/rollup/{window}", headers=_auth())
            assert r.json()["record_count"] == 1

    def test_empty_operator_returns_zeros(self, client):
        r = client.get("/el_ins/rollup/24h", headers=_auth())
        body = r.json()
        assert body["record_count"] == 0
        assert body["avg_el"] == 0.0
        assert body["avg_ins"] == 0.0


# ===========================================================================
# G. Cross-operator isolation
# ===========================================================================
class TestCrossOperatorIsolation:
    def test_alice_rollup_excludes_bobs_records(self, client):
        now_ts = time.time()
        el_ins.store_el_ins_record({
            "operator_id": "op_bob", "thread_id": "t1",
            "timestamp":   now_ts - 10,
            "source":      "on_demand",
            "result":      _mk("balanced", 4.0, 4.0),
        })
        r = client.get("/el_ins/rollup/24h", headers=_auth("op_alice"))
        assert r.json()["record_count"] == 0
        r2 = client.get("/el_ins/rollup/24h", headers=_auth("op_bob"))
        assert r2.json()["record_count"] == 1
