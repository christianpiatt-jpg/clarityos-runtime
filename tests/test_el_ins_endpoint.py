"""
Tests for v69 / Unit 74 — /el_ins/* HTTP endpoints.

Covers:
    A. Auth gate on all four endpoints
    B. POST /el_ins/analyze response shape + provider_mode validation
    C. thread_id present → record stored, absent → not stored
    D. GET /el_ins/recent returns operator-scoped records, newest-first
    E. GET /el_ins/thread/{thread_id} filters by thread
    F. GET /el_ins/macro applies since filter
    G. Cross-operator isolation
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from conftest import TestClient

import el_ins
import runtime_http as rh_mod
import sessions_store


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(rh_mod.el_ins_router)
    el_ins._reset_for_tests()
    yield TestClient(app)
    el_ins._reset_for_tests()


def _auth(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-elins-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# ===========================================================================
# A. Auth gate
# ===========================================================================
class TestAuth:
    def test_unauthed_analyze_returns_401(self, client):
        r = client.post("/el_ins/analyze", json={"text": "x"})
        assert r.status_code == 401

    def test_unauthed_recent_returns_401(self, client):
        r = client.get("/el_ins/recent")
        assert r.status_code == 401

    def test_unauthed_thread_returns_401(self, client):
        r = client.get("/el_ins/thread/t1")
        assert r.status_code == 401

    def test_unauthed_macro_returns_401(self, client):
        r = client.get("/el_ins/macro")
        assert r.status_code == 401


# ===========================================================================
# B. Analyze endpoint
# ===========================================================================
class TestAnalyzeEndpoint:
    def test_authed_analyze_returns_200_and_shape(self, client):
        r = client.post(
            "/el_ins/analyze",
            json={"text": "catastrophic disaster doom", "provider_mode": "deterministic"},
            headers=_auth(),
        )
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"result", "stored", "thread_id", "timestamp"}
        assert body["result"]["analysis"]["ratio_classification"] == "high_el"
        assert body["stored"] is False
        assert body["thread_id"] is None

    def test_invalid_provider_mode_returns_400(self, client):
        r = client.post(
            "/el_ins/analyze",
            json={"text": "x", "provider_mode": "banana"},
            headers=_auth(),
        )
        assert r.status_code == 400

    def test_missing_text_returns_422(self, client):
        # Pydantic body validation kicks in before our handler.
        r = client.post("/el_ins/analyze", json={}, headers=_auth())
        assert r.status_code == 422

    def test_default_provider_mode_is_auto(self, client):
        # No provider_mode in body → default auto. With no LLM configured
        # this should fall back to deterministic and still succeed.
        r = client.post(
            "/el_ins/analyze",
            json={"text": "statute clause testimony"},
            headers=_auth(),
        )
        assert r.status_code == 200


# ===========================================================================
# C. Storage on thread_id
# ===========================================================================
class TestStorage:
    def test_thread_id_present_stores_record(self, client):
        r = client.post(
            "/el_ins/analyze",
            json={
                "text": "catastrophic disaster",
                "provider_mode": "deterministic",
                "thread_id": "thread-001",
            },
            headers=_auth(),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["stored"] is True
        assert body["thread_id"] == "thread-001"

    def test_no_thread_id_no_store(self, client):
        r = client.post(
            "/el_ins/analyze",
            json={"text": "catastrophic", "provider_mode": "deterministic"},
            headers=_auth(),
        )
        assert r.json()["stored"] is False
        # Confirm store remains empty for this operator.
        r2 = client.get("/el_ins/recent", headers=_auth())
        assert r2.json()["records"] == []


# ===========================================================================
# D. Recent endpoint
# ===========================================================================
class TestRecentEndpoint:
    def _store_n(self, client, n: int, headers: dict):
        for i in range(n):
            client.post(
                "/el_ins/analyze",
                json={
                    "text": f"catastrophic {i}",
                    "provider_mode": "deterministic",
                    "thread_id": "t1",
                },
                headers=headers,
            )

    def test_recent_returns_authed_operator_records(self, client):
        h = _auth()
        self._store_n(client, 3, h)
        r = client.get("/el_ins/recent", headers=h)
        body = r.json()
        assert r.status_code == 200
        assert body["operator_id"] == "op_alice"
        assert len(body["records"]) == 3

    def test_recent_newest_first(self, client):
        h = _auth()
        self._store_n(client, 3, h)
        rows = client.get("/el_ins/recent", headers=h).json()["records"]
        # Timestamps decreasing.
        assert rows[0]["timestamp"] >= rows[1]["timestamp"] >= rows[2]["timestamp"]

    def test_recent_limit_query_param(self, client):
        h = _auth()
        self._store_n(client, 5, h)
        rows = client.get("/el_ins/recent?limit=2", headers=h).json()["records"]
        assert len(rows) == 2


# ===========================================================================
# E. Thread endpoint
# ===========================================================================
class TestThreadEndpoint:
    def test_thread_filters_by_thread_id(self, client):
        h = _auth()
        client.post(
            "/el_ins/analyze",
            json={"text": "catastrophic", "provider_mode": "deterministic",
                  "thread_id": "ta"},
            headers=h,
        )
        client.post(
            "/el_ins/analyze",
            json={"text": "statute", "provider_mode": "deterministic",
                  "thread_id": "tb"},
            headers=h,
        )
        ta = client.get("/el_ins/thread/ta", headers=h).json()
        tb = client.get("/el_ins/thread/tb", headers=h).json()
        assert len(ta["records"]) == 1
        assert len(tb["records"]) == 1
        assert ta["thread_id"] == "ta"
        assert tb["thread_id"] == "tb"

    def test_unknown_thread_returns_empty_records(self, client):
        h = _auth()
        r = client.get("/el_ins/thread/nope", headers=h)
        assert r.status_code == 200
        assert r.json()["records"] == []


# ===========================================================================
# F. Macro endpoint
# ===========================================================================
class TestMacroEndpoint:
    def test_macro_since_filter(self, client):
        h = _auth()
        client.post(
            "/el_ins/analyze",
            json={"text": "catastrophic", "provider_mode": "deterministic",
                  "thread_id": "t1"},
            headers=h,
        )
        # Record now() — anything since this point includes the record.
        cutoff = time.time() - 1.0
        r = client.get(f"/el_ins/macro?since={cutoff}", headers=h)
        assert r.status_code == 200
        assert len(r.json()["records"]) >= 1

    def test_macro_no_since_returns_all(self, client):
        h = _auth()
        for _ in range(2):
            client.post(
                "/el_ins/analyze",
                json={"text": "catastrophic", "provider_mode": "deterministic",
                      "thread_id": "t1"},
                headers=h,
            )
        r = client.get("/el_ins/macro", headers=h)
        assert len(r.json()["records"]) == 2


# ===========================================================================
# G. Cross-operator isolation
# ===========================================================================
class TestCrossOperatorIsolation:
    def test_alice_cannot_see_bobs_records(self, client):
        ha = _auth("op_alice")
        hb = _auth("op_bob")
        client.post(
            "/el_ins/analyze",
            json={"text": "catastrophic", "provider_mode": "deterministic",
                  "thread_id": "t1"},
            headers=hb,
        )
        # Alice queries — gets nothing.
        alice_rows = client.get("/el_ins/recent", headers=ha).json()["records"]
        assert alice_rows == []
        # Bob queries — gets his record.
        bob_rows = client.get("/el_ins/recent", headers=hb).json()["records"]
        assert len(bob_rows) == 1
        assert bob_rows[0]["operator_id"] == "op_bob"
