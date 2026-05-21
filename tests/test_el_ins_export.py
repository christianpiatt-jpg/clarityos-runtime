"""
Tests for v71 / Unit 78 — el_ins.el_ins_export module + endpoints.

Covers:
    A. build_json_export envelope shape + per-record projection
    B. build_pdf_export emits a valid PDF/1.4 byte stream
    C. PDF carries summary stats + footer (version, build)
    D. GET /el_ins/export/json endpoint auth + clamping
    E. GET /el_ins/export/pdf endpoint auth + content-type
    F. Cross-operator isolation on both endpoints
"""
from __future__ import annotations

import time

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


def _seed(operator: str, thread_id: str, n: int = 5):
    for i in range(n):
        el_ins.store_el_ins_record({
            "operator_id": operator, "thread_id": thread_id,
            "timestamp":   float(1700000000 + i),
            "source":      "on_demand",
            "result":      _mk("balanced", 2.0 + i * 0.5, 2.0),
        })


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rh_mod.el_ins_router)
    el_ins._reset_for_tests()
    yield TestClient(app)
    el_ins._reset_for_tests()


def _auth(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-elins-export-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# ===========================================================================
# A. JSON export module
# ===========================================================================
class TestJsonExportModule:
    def test_envelope_shape_locked(self):
        out = el_ins.build_json_export("alice", [], generated_at=1700000000.0)
        assert set(out.keys()) == {"operator_id", "generated_at", "records"}
        assert out["operator_id"] == "alice"
        assert out["generated_at"].startswith("2023-")  # 1700000000 → 2023
        assert out["records"] == []

    def test_record_projection(self):
        records = [{
            "operator_id": "alice", "thread_id": "t1",
            "timestamp": 1700000000.0, "source": "per_turn",
            "tsi": 75,
            "result": _mk("high_el", 7.5, 2.0),
        }]
        out = el_ins.build_json_export("alice", records, generated_at=1700000001.0)
        assert len(out["records"]) == 1
        r = out["records"][0]
        assert r["thread_id"] == "t1"
        assert r["el"] == 7.5
        assert r["ins"] == 2.0
        assert r["classification"] == "high_el"
        assert r["tsi"] == 75
        assert r["source"] == "per_turn"
        assert r["timestamp"].startswith("2023-")

    def test_record_without_tsi_emits_null(self):
        records = [{
            "operator_id": "alice", "thread_id": None,
            "timestamp": 1700000000.0, "source": "on_demand",
            "result": _mk("balanced", 2.0, 2.0),
        }]
        out = el_ins.build_json_export("alice", records)
        assert out["records"][0]["tsi"] is None

    def test_empty_operator_raises(self):
        with pytest.raises(ValueError):
            el_ins.build_json_export("", [])

    def test_non_list_records_raises(self):
        with pytest.raises(ValueError):
            el_ins.build_json_export("alice", "not-a-list")  # type: ignore[arg-type]


# ===========================================================================
# B. PDF export module
# ===========================================================================
class TestPdfExportModule:
    def test_returns_bytes(self):
        out = el_ins.build_pdf_export(
            "alice", [], {"sample_size": 0, "avg_tsi": 0, "trend": "stable",
                          "recent_classification_distribution": {"high_el": 0, "high_ins": 0, "balanced": 0}},
            version="4.14", build="20260513060000",
        )
        assert isinstance(out, bytes)
        assert len(out) > 100

    def test_pdf_header_signature(self):
        out = el_ins.build_pdf_export(
            "alice", [], {"sample_size": 0, "avg_tsi": 0, "trend": "stable",
                          "recent_classification_distribution": {"high_el": 0, "high_ins": 0, "balanced": 0}},
            version="x", build="y",
        )
        assert out.startswith(b"%PDF-1.4")

    def test_pdf_has_xref_and_eof(self):
        out = el_ins.build_pdf_export(
            "alice", [], {"sample_size": 0, "avg_tsi": 0, "trend": "stable",
                          "recent_classification_distribution": {"high_el": 0, "high_ins": 0, "balanced": 0}},
            version="x", build="y",
        )
        assert b"xref" in out
        assert b"trailer" in out
        assert out.rstrip().endswith(b"%%EOF")

    def test_pdf_contains_operator_id(self):
        out = el_ins.build_pdf_export(
            "op_christian", [], {"sample_size": 0, "avg_tsi": 0, "trend": "stable",
                                 "recent_classification_distribution": {"high_el": 0, "high_ins": 0, "balanced": 0}},
            version="x", build="y",
        )
        assert b"op_christian" in out

    def test_pdf_contains_version_and_build_in_footer(self):
        out = el_ins.build_pdf_export(
            "alice", [], {"sample_size": 0, "avg_tsi": 0, "trend": "stable",
                          "recent_classification_distribution": {"high_el": 0, "high_ins": 0, "balanced": 0}},
            version="4.14", build="20260513060000",
        )
        assert b"4.14" in out
        assert b"20260513060000" in out

    def test_pdf_renders_records(self):
        records = [{
            "operator_id": "alice", "thread_id": "thread-99",
            "timestamp": 1700000000.0, "source": "per_turn",
            "tsi": 75,
            "result": _mk("high_el", 7.5, 2.0),
        }]
        out = el_ins.build_pdf_export(
            "alice", records, {"sample_size": 1, "avg_tsi": 75, "trend": "stable",
                               "recent_classification_distribution": {"high_el": 1, "high_ins": 0, "balanced": 0}},
            version="x", build="y",
        )
        assert b"thread-99" in out
        assert b"high_el" in out

    def test_pdf_escapes_parens_in_operator_id(self):
        # PDF literals escape ( ) with backslash. Verify the generator
        # handles a weird operator id without producing a malformed
        # content stream.
        out = el_ins.build_pdf_export(
            "alice(test)", [], {"sample_size": 0, "avg_tsi": 0, "trend": "stable",
                                "recent_classification_distribution": {"high_el": 0, "high_ins": 0, "balanced": 0}},
            version="x", build="y",
        )
        # Escaped form in the content stream.
        assert b"alice\\(test\\)" in out
        # Still parseable — header + EOF intact.
        assert out.startswith(b"%PDF-1.4")
        assert out.rstrip().endswith(b"%%EOF")

    def test_pdf_handles_large_record_count(self):
        # Records that overflow a single page are silently truncated;
        # the document still has to be valid.
        records = []
        for i in range(200):
            records.append({
                "operator_id": "alice", "thread_id": f"t{i}",
                "timestamp": float(1700000000 + i), "source": "on_demand",
                "tsi": 50 + (i % 50),
                "result": _mk("balanced", 2.0, 2.0),
            })
        out = el_ins.build_pdf_export(
            "alice", records, {"sample_size": 200, "avg_tsi": 75, "trend": "stable",
                               "recent_classification_distribution": {"high_el": 0, "high_ins": 0, "balanced": 200}},
            version="x", build="y",
        )
        assert out.startswith(b"%PDF-1.4")
        assert out.rstrip().endswith(b"%%EOF")

    def test_empty_records_handled(self):
        out = el_ins.build_pdf_export(
            "alice", [], {"sample_size": 0, "avg_tsi": 0, "trend": "stable",
                          "recent_classification_distribution": {"high_el": 0, "high_ins": 0, "balanced": 0}},
            version="x", build="y",
        )
        # "(no TSI data)" — the parens get backslash-escaped in PDF
        # string literal syntax (PDF/1.4 §7.3.4.2).
        assert b"\\(no TSI data\\)" in out


# ===========================================================================
# C. JSON endpoint
# ===========================================================================
class TestJsonEndpoint:
    def test_unauthed_returns_401(self, client):
        r = client.get("/el_ins/export/json")
        assert r.status_code == 401

    def test_authed_returns_200_and_shape(self, client):
        _seed("op_alice", "t1", n=3)
        r = client.get("/el_ins/export/json", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"operator_id", "generated_at", "records"}
        assert body["operator_id"] == "op_alice"
        assert len(body["records"]) == 3

    def test_limit_query_param(self, client):
        _seed("op_alice", "t1", n=10)
        r = client.get("/el_ins/export/json?limit=3", headers=_auth())
        assert r.status_code == 200
        assert len(r.json()["records"]) == 3

    def test_limit_clamped_high(self, client):
        _seed("op_alice", "t1", n=5)
        r = client.get("/el_ins/export/json?limit=99999", headers=_auth())
        assert r.status_code == 200
        # Only 5 stored; limit clamped doesn't manufacture rows.
        assert len(r.json()["records"]) == 5

    def test_limit_clamped_low(self, client):
        _seed("op_alice", "t1", n=5)
        r = client.get("/el_ins/export/json?limit=0", headers=_auth())
        assert r.status_code == 200
        assert len(r.json()["records"]) == 1

    def test_empty_operator_returns_empty_records(self, client):
        r = client.get("/el_ins/export/json", headers=_auth())
        assert r.status_code == 200
        assert r.json()["records"] == []


# ===========================================================================
# D. PDF endpoint
# ===========================================================================
class TestPdfEndpoint:
    def test_unauthed_returns_401(self, client):
        r = client.get("/el_ins/export/pdf")
        assert r.status_code == 401

    def test_authed_returns_pdf_bytes(self, client):
        _seed("op_alice", "t1", n=3)
        r = client.get("/el_ins/export/pdf", headers=_auth())
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/pdf")
        assert r.content.startswith(b"%PDF-1.4")
        assert r.content.rstrip().endswith(b"%%EOF")

    def test_pdf_has_attachment_disposition(self, client):
        _seed("op_alice", "t1", n=1)
        r = client.get("/el_ins/export/pdf", headers=_auth())
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()
        assert "el_ins_export_op_alice.pdf" in cd

    def test_pdf_empty_history_still_renders(self, client):
        r = client.get("/el_ins/export/pdf", headers=_auth())
        assert r.status_code == 200
        assert r.content.startswith(b"%PDF-1.4")

    def test_limit_clamped_high(self, client):
        _seed("op_alice", "t1", n=5)
        r = client.get("/el_ins/export/pdf?limit=99999", headers=_auth())
        assert r.status_code == 200


# ===========================================================================
# E. Cross-operator isolation
# ===========================================================================
class TestCrossOperatorIsolation:
    def test_alice_json_export_excludes_bobs_records(self, client):
        _seed("op_bob", "t1", n=4)
        r = client.get("/el_ins/export/json", headers=_auth("op_alice"))
        assert r.status_code == 200
        assert r.json()["records"] == []
        assert r.json()["operator_id"] == "op_alice"

    def test_bob_can_export_his_own(self, client):
        _seed("op_bob", "t1", n=4)
        r = client.get("/el_ins/export/json", headers=_auth("op_bob"))
        assert r.status_code == 200
        assert len(r.json()["records"]) == 4
