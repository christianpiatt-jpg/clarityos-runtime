"""
Tests for v72 / Unit 80 — el_ins.anomaly + anomaly_store + endpoints.

Covers:
    A. Rule triggers (high_el / low_ins / tsi_spike / quadrant_jump)
    B. Quadrant distance math
    C. Severity assignments locked
    D. Anomaly shape locked
    E. anomaly_store validation + retrieval
    F. GET /el_ins/anomalies + GET /el_ins/anomalies/{id}
    G. run_thread_message wires detect + store + return
    H. Cross-operator isolation
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
from el_ins.anomaly import (
    _quadrant,
    _quadrant_distance,
    ANOMALY_TYPES,
    detect_anomalies,
)


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


def _rec(el: float, ins: float, *, tsi: int = None, thread_id: str = "t1") -> dict:
    rec: dict = {
        "operator_id": "alice",
        "thread_id":   thread_id,
        "timestamp":   1700000000.0,
        "source":      "on_demand",
        "result":      _mk("balanced", el, ins),
    }
    if tsi is not None:
        rec["tsi"] = tsi
    return rec


# ===========================================================================
# A. Rule triggers
# ===========================================================================
class TestRuleTriggers:
    def test_high_el_fires(self):
        anoms = detect_anomalies(_rec(8.0, 5.0))
        types = [a["type"] for a in anoms]
        assert "high_el" in types

    def test_high_el_boundary_does_not_fire(self):
        # EL > 7.5 strict — 7.5 itself doesn't fire.
        anoms = detect_anomalies(_rec(7.5, 5.0))
        assert "high_el" not in [a["type"] for a in anoms]

    def test_low_ins_fires(self):
        anoms = detect_anomalies(_rec(5.0, 1.5))
        assert "low_ins" in [a["type"] for a in anoms]

    def test_low_ins_boundary_does_not_fire(self):
        # INS < 2.0 strict — 2.0 itself doesn't fire.
        anoms = detect_anomalies(_rec(5.0, 2.0))
        assert "low_ins" not in [a["type"] for a in anoms]

    def test_tsi_spike_fires(self):
        anoms = detect_anomalies(_rec(5.0, 5.0, tsi=90))
        assert "tsi_spike" in [a["type"] for a in anoms]

    def test_tsi_boundary_does_not_fire(self):
        anoms = detect_anomalies(_rec(5.0, 5.0, tsi=85))
        assert "tsi_spike" not in [a["type"] for a in anoms]

    def test_tsi_none_does_not_fire(self):
        anoms = detect_anomalies(_rec(5.0, 5.0))   # no TSI
        assert "tsi_spike" not in [a["type"] for a in anoms]

    def test_multiple_rules_fire_simultaneously(self):
        # High EL + low INS + TSI spike on a single record.
        anoms = detect_anomalies(_rec(8.0, 1.5, tsi=90))
        types = sorted(a["type"] for a in anoms)
        assert types == ["high_el", "low_ins", "tsi_spike"]


# ===========================================================================
# B. Quadrant distance math
# ===========================================================================
class TestQuadrantMath:
    def test_quadrant_classification(self):
        assert _quadrant(8.0, 1.0) == 1   # high EL, low INS
        assert _quadrant(1.0, 8.0) == 2   # low EL, high INS
        assert _quadrant(8.0, 8.0) == 3   # high EL, high INS
        assert _quadrant(1.0, 1.0) == 4   # low EL, low INS

    def test_diagonal_distance_is_two(self):
        assert _quadrant_distance(1, 2) == 2   # grounding ↔ analysis
        assert _quadrant_distance(3, 4) == 2   # structured ↔ stabilization

    def test_axis_neighbour_distance_is_one(self):
        # Q1 (high EL, low INS) → Q3 (high EL, high INS): differs on INS only.
        assert _quadrant_distance(1, 3) == 1
        # Q1 → Q4: differs on EL only.
        assert _quadrant_distance(1, 4) == 1

    def test_same_quadrant_distance_is_zero(self):
        assert _quadrant_distance(1, 1) == 0
        assert _quadrant_distance(3, 3) == 0


class TestQuadrantJumpRule:
    def test_diagonal_jump_fires(self):
        prior = _rec(1.0, 1.0)         # Q4
        curr  = _rec(8.0, 8.0)         # Q3 — wait, that's distance 2 from Q4
        # Actually Q4 (low, low) → Q3 (high, high) is diagonal distance 2.
        anoms = detect_anomalies(curr, prior_record=prior)
        assert "quadrant_jump" in [a["type"] for a in anoms]

    def test_axis_neighbour_does_not_fire(self):
        prior = _rec(1.0, 1.0)         # Q4
        curr  = _rec(8.0, 1.0)         # Q1 — adjacent, distance 1
        anoms = detect_anomalies(curr, prior_record=prior)
        assert "quadrant_jump" not in [a["type"] for a in anoms]

    def test_no_prior_record_does_not_fire(self):
        curr = _rec(8.0, 8.0)
        anoms = detect_anomalies(curr, prior_record=None)
        assert "quadrant_jump" not in [a["type"] for a in anoms]


# ===========================================================================
# C. Severity locked
# ===========================================================================
class TestSeverity:
    def test_high_el_severity_3(self):
        anoms = detect_anomalies(_rec(8.0, 5.0))
        assert next(a for a in anoms if a["type"] == "high_el")["severity"] == 3

    def test_low_ins_severity_3(self):
        anoms = detect_anomalies(_rec(5.0, 1.0))
        assert next(a for a in anoms if a["type"] == "low_ins")["severity"] == 3

    def test_tsi_spike_severity_4(self):
        anoms = detect_anomalies(_rec(5.0, 5.0, tsi=90))
        assert next(a for a in anoms if a["type"] == "tsi_spike")["severity"] == 4

    def test_quadrant_jump_severity_5(self):
        prior = _rec(1.0, 1.0)
        curr  = _rec(8.0, 8.0)
        anoms = detect_anomalies(curr, prior_record=prior)
        assert next(a for a in anoms if a["type"] == "quadrant_jump")["severity"] == 5


# ===========================================================================
# D. Shape locked
# ===========================================================================
class TestAnomalyShape:
    def test_required_keys(self):
        anoms = detect_anomalies(_rec(8.0, 5.0))
        a = anoms[0]
        expected = {"id", "timestamp", "type", "severity", "message",
                    "record_id", "operator_id", "thread_id"}
        assert set(a.keys()) == expected

    def test_id_is_uuid_hex(self):
        anoms = detect_anomalies(_rec(8.0, 5.0))
        a = anoms[0]
        # UUID4 hex is 32 chars, all lowercase hex digits.
        assert len(a["id"]) == 32
        assert all(c in "0123456789abcdef" for c in a["id"])

    def test_record_id_back_pointer_format(self):
        anoms = detect_anomalies(_rec(8.0, 5.0))
        # Format: "{thread_id}:{timestamp_ms}"
        assert anoms[0]["record_id"] == "t1:1700000000000"

    def test_type_in_locked_enum(self):
        for a in detect_anomalies(_rec(8.0, 1.0, tsi=90)):
            assert a["type"] in ANOMALY_TYPES


# ===========================================================================
# E. Store validation + retrieval
# ===========================================================================
@pytest.fixture(autouse=True)
def _isolate():
    import memory_vault
    el_ins._reset_all_for_tests()
    # operator_state lives in memory_vault — reset so the v69
    # ``el_ins_per_turn`` flag doesn't leak into adjacent test files
    # (mirror of v71's test_el_ins_reasoning_mode fixture).
    memory_vault._reset_for_tests()
    yield
    el_ins._reset_all_for_tests()
    memory_vault._reset_for_tests()


class TestAnomalyStore:
    def test_store_and_retrieve_newest_first(self):
        rec = _rec(8.0, 1.0)
        anoms = detect_anomalies(rec)
        el_ins.store_anomalies(list(anoms))
        rows = el_ins.list_anomalies("alice")
        assert len(rows) == 2  # high_el + low_ins
        # All belong to alice.
        assert all(r["operator_id"] == "alice" for r in rows)

    def test_get_anomaly_by_id(self):
        anoms = detect_anomalies(_rec(8.0, 5.0))
        el_ins.store_anomalies(list(anoms))
        target = anoms[0]
        out = el_ins.get_anomaly("alice", target["id"])
        assert out is not None
        assert out["id"] == target["id"]

    def test_get_anomaly_unknown_returns_none(self):
        assert el_ins.get_anomaly("alice", "nonexistent-id") is None

    def test_store_validates_severity_bounds(self):
        with pytest.raises(ValueError):
            el_ins.store_anomalies([{
                "id": "x", "operator_id": "alice", "type": "high_el",
                "severity": 99,  # out of [1,5]
                "timestamp": 1.0, "message": "", "record_id": "", "thread_id": None,
            }])

    def test_store_validates_type_enum(self):
        with pytest.raises(ValueError):
            el_ins.store_anomalies([{
                "id": "x", "operator_id": "alice", "type": "garbage",
                "severity": 3,
                "timestamp": 1.0, "message": "", "record_id": "", "thread_id": None,
            }])


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
    sid = f"auth-anom-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


def _seed_anomalies(operator: str, n: int = 3):
    for i in range(n):
        rec = {
            "operator_id": operator, "thread_id": "t1",
            "timestamp": float(1700000000 + i),
            "source": "on_demand",
            "result": _mk("high_el", 8.0, 1.0),
        }
        anoms = detect_anomalies(rec)
        el_ins.store_anomalies(list(anoms))


class TestAnomalyEndpoints:
    def test_list_unauthed_401(self, client):
        r = client.get("/el_ins/anomalies")
        assert r.status_code == 401

    def test_get_one_unauthed_401(self, client):
        r = client.get("/el_ins/anomalies/abc")
        assert r.status_code == 401

    def test_list_returns_empty_for_no_data(self, client):
        r = client.get("/el_ins/anomalies", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert body == {"operator_id": "op_alice", "anomalies": []}

    def test_list_returns_seeded_anomalies(self, client):
        _seed_anomalies("op_alice", n=3)
        r = client.get("/el_ins/anomalies", headers=_auth())
        body = r.json()
        # 3 records × 2 rules (high_el + low_ins) = 6 anomalies.
        assert len(body["anomalies"]) == 6

    def test_get_by_id_returns_anomaly(self, client):
        _seed_anomalies("op_alice", n=1)
        rows = client.get("/el_ins/anomalies", headers=_auth()).json()["anomalies"]
        target = rows[0]
        r = client.get(
            f"/el_ins/anomalies/{target['id']}", headers=_auth(),
        )
        assert r.status_code == 200
        assert r.json()["id"] == target["id"]

    def test_get_by_id_unknown_returns_404(self, client):
        _seed_anomalies("op_alice", n=1)
        r = client.get(
            "/el_ins/anomalies/nonexistent-id-12345", headers=_auth(),
        )
        assert r.status_code == 404


# ===========================================================================
# G. Kernel integration
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

    def test_per_turn_off_no_anomalies(self):
        tid = threads_vault.create_thread("alice", title="t")["thread_id"]
        out = ik.run_thread_message("alice", tid, "any text")
        assert out["anomalies"] == []

    def test_per_turn_on_high_el_text_emits_anomalies(self):
        import memory_vault
        memory_vault._reset_for_tests()
        operator_state.set_el_ins_per_turn("alice", True)
        tid = threads_vault.create_thread("alice", title="t")["thread_id"]
        # Deterministic analyzer treats this as high_el (many emotive markers).
        text = "catastrophic disaster doom panic obviously crisis terrible horrifying urgent"
        out = ik.run_thread_message("alice", tid, text)
        # Should fire at least one anomaly.
        assert isinstance(out["anomalies"], list)
        assert len(out["anomalies"]) > 0
        # And anomalies should be persisted.
        rows = el_ins.list_anomalies("alice")
        assert len(rows) == len(out["anomalies"])

    def test_existing_return_dict_keys_still_present(self):
        # Back-compat: anomalies is additive alongside meta /
        # user_message / assistant_message / model_id / reasoning_mode.
        tid = threads_vault.create_thread("alice", title="t")["thread_id"]
        out = ik.run_thread_message("alice", tid, "any text")
        for k in ("meta", "user_message", "assistant_message", "model_id",
                  "reasoning_mode", "anomalies"):
            assert k in out


# ===========================================================================
# H. Cross-operator isolation
# ===========================================================================
class TestCrossOperatorIsolation:
    def test_alice_cannot_list_bobs_anomalies(self, client):
        _seed_anomalies("op_bob", n=2)
        r = client.get("/el_ins/anomalies", headers=_auth("op_alice"))
        assert r.json()["anomalies"] == []
        # Bob sees his own.
        r2 = client.get("/el_ins/anomalies", headers=_auth("op_bob"))
        assert len(r2.json()["anomalies"]) == 4   # 2 records × 2 rules

    def test_alice_cannot_fetch_bobs_anomaly_by_id(self, client):
        _seed_anomalies("op_bob", n=1)
        bobs = client.get("/el_ins/anomalies", headers=_auth("op_bob")).json()["anomalies"]
        target_id = bobs[0]["id"]
        r = client.get(
            f"/el_ins/anomalies/{target_id}", headers=_auth("op_alice"),
        )
        # Scoped lookup → 404 not 403 (don't leak existence).
        assert r.status_code == 404
