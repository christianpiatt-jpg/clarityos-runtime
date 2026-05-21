"""
Tests for v73 / Unit 83 — el_ins.org_timeline + /org/timeline/* endpoints.

Covers:
    A. Window coercion (string / timedelta / numeric)
    B. Operator masking (last 6 chars)
    C. Per-event-type summarisation contracts
    D. Newest-first chronological ordering across operators
    E. Window boundary inclusion/exclusion
    F. /org/timeline/{24h,7d,30d} endpoints — auth + founder gating
    G. No raw payload / thread_id leakage
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
import users_store
from el_ins.org_timeline import _mask_operator, _summarise_payload


@pytest.fixture(autouse=True)
def _isolate():
    import memory_vault
    el_ins._reset_all_for_tests()
    memory_vault._reset_for_tests()
    users_store._reset_memory_for_tests()
    yield
    el_ins._reset_all_for_tests()
    memory_vault._reset_for_tests()
    users_store._reset_memory_for_tests()


# ===========================================================================
# A. Window coercion
# ===========================================================================
class TestWindowCoercion:
    def test_named_windows_accepted(self):
        for w in ("24h", "7d", "30d"):
            el_ins.compute_org_timeline(w, now=1700000000.0)  # no raise

    def test_unknown_named_raises(self):
        with pytest.raises(ValueError):
            el_ins.compute_org_timeline("yearly", now=1700000000.0)

    def test_timedelta_accepted(self):
        out = el_ins.compute_org_timeline(timedelta(hours=2), now=1700000000.0)
        assert out == []  # no events stored

    def test_numeric_seconds_accepted(self):
        el_ins.compute_org_timeline(3600, now=1700000000.0)  # no raise

    def test_zero_window_raises(self):
        with pytest.raises(ValueError):
            el_ins.compute_org_timeline(0, now=1700000000.0)

    def test_negative_window_raises(self):
        with pytest.raises(ValueError):
            el_ins.compute_org_timeline(-1, now=1700000000.0)


# ===========================================================================
# B. Operator masking
# ===========================================================================
class TestOperatorMasking:
    def test_long_id_masked_to_last_6(self):
        assert _mask_operator("op_christian") == "istian"

    def test_short_id_unchanged(self):
        # 5-char id is <= 6 chars — returned as-is.
        assert _mask_operator("alice") == "alice"

    def test_exactly_six_chars_unchanged(self):
        assert _mask_operator("abcdef") == "abcdef"

    def test_seven_chars_masked(self):
        assert _mask_operator("abcdefg") == "bcdefg"

    def test_empty_returns_empty(self):
        assert _mask_operator("") == ""

    def test_none_returns_empty(self):
        assert _mask_operator(None) == ""  # type: ignore[arg-type]


# ===========================================================================
# C. Summarisation contracts
# ===========================================================================
class TestSummarisation:
    def test_record_summary_has_only_locked_keys(self):
        out = _summarise_payload("record", {
            "el": 8.0, "ins": 1.0, "tsi": 90,
            "reasoning_mode": "grounding",   # MUST be dropped
            "thread_id": "t1",                # MUST be dropped
        })
        assert set(out.keys()) == {"el", "ins", "tsi"}
        assert out["el"] == 8.0
        assert out["ins"] == 1.0
        assert out["tsi"] == 90

    def test_record_summary_with_no_tsi(self):
        out = _summarise_payload("record", {"el": 5.0, "ins": 5.0})
        assert out["tsi"] is None

    def test_anomaly_summary_has_only_locked_keys(self):
        out = _summarise_payload("anomaly", {
            "type": "high_el",
            "severity": 3,
            "message": "EL too high",   # MUST be dropped
            "anomaly_id": "abc",        # MUST be dropped
        })
        assert set(out.keys()) == {"severity", "rule"}
        assert out["severity"] == 3
        assert out["rule"] == "high_el"

    def test_rollup_summary_has_only_locked_keys(self):
        out = _summarise_payload("rollup", {
            "window": "24h",
            "avg_el": 3.5,
            "avg_ins": 4.5,
            "avg_tsi": 80,                # MUST be dropped
            "record_count": 20,           # MUST be dropped
        })
        assert set(out.keys()) == {"window", "avg_el", "avg_ins"}
        assert out["window"] == "24h"

    def test_system_summary_empty(self):
        out = _summarise_payload("system", {"raw": "anything"})
        assert out == {}

    def test_unknown_type_summary_empty(self):
        out = _summarise_payload("nonsense", {"raw": "x"})
        assert out == {}


# ===========================================================================
# D. Compute + ordering
# ===========================================================================
class TestComputeOrdering:
    def test_empty_returns_empty(self):
        assert el_ins.compute_org_timeline("24h", now=1700000000.0) == []

    def test_newest_first_across_operators(self):
        now_ts = 1700000000.0
        # Store events for two operators at different times.
        for op, ts in [("alice", 1699999000.0), ("op_christian", 1699999500.0), ("alice", 1699999800.0)]:
            el_ins.store_event({
                "operator_id":  op,
                "event_type":   "record",
                "payload":      {"el": 5.0, "ins": 5.0, "tsi": 80},
                "timestamp_ms": int(ts * 1000),
            })
        out = el_ins.compute_org_timeline("24h", now=now_ts)
        # 3 events, newest-first.
        assert [e["timestamp_ms"] for e in out] == [
            1699999800000, 1699999500000, 1699999000000,
        ]


# ===========================================================================
# E. Window boundary
# ===========================================================================
class TestWindowBoundary:
    def test_event_in_window_included(self):
        now_ts = 1700000000.0
        el_ins.store_event({
            "operator_id": "alice", "event_type": "record",
            "payload": {"el": 5.0, "ins": 5.0, "tsi": 80},
            "timestamp_ms": int((now_ts - 3600) * 1000),
        })
        assert len(el_ins.compute_org_timeline("24h", now=now_ts)) == 1

    def test_event_outside_window_excluded(self):
        now_ts = 1700000000.0
        # 25 hours ago — outside 24h window.
        el_ins.store_event({
            "operator_id": "alice", "event_type": "record",
            "payload": {"el": 5.0, "ins": 5.0, "tsi": 80},
            "timestamp_ms": int((now_ts - 25 * 3600) * 1000),
        })
        assert len(el_ins.compute_org_timeline("24h", now=now_ts)) == 0

    def test_future_event_excluded(self):
        now_ts = 1700000000.0
        el_ins.store_event({
            "operator_id": "alice", "event_type": "record",
            "payload": {"el": 5.0, "ins": 5.0, "tsi": 80},
            "timestamp_ms": int((now_ts + 100) * 1000),
        })
        assert len(el_ins.compute_org_timeline("24h", now=now_ts)) == 0


# ===========================================================================
# F. HTTP endpoints
# ===========================================================================
@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(rh_mod.org_timeline_router)
    el_ins._reset_all_for_tests()
    yield TestClient(app)
    el_ins._reset_all_for_tests()


def _auth(user: str = "founder_alice", *, cohort: str = "founder") -> dict[str, str]:
    # Seed a user doc so require_founder can read its cohort. The
    # users_store API uses (username, password_hash, salt, tier,
    # created_at); we don't care about auth-hash fidelity here so
    # placeholder strings + a current timestamp are fine.
    if not users_store.get_user(user):
        users_store.create_user(
            user, "x", "x", tier="standard", created_at=time.time(),
        )
    users_store.update_user(user, {"cohort": cohort})
    sid = f"auth-org-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


class TestOrgTimelineEndpoints:
    def test_24h_unauthed_returns_401(self, client):
        assert client.get("/org/timeline/24h").status_code == 401

    def test_7d_unauthed_returns_401(self, client):
        assert client.get("/org/timeline/7d").status_code == 401

    def test_30d_unauthed_returns_401(self, client):
        assert client.get("/org/timeline/30d").status_code == 401

    def test_non_founder_returns_403(self, client):
        # Authed but no founder cohort → 403.
        r = client.get(
            "/org/timeline/24h",
            headers=_auth("regular_user", cohort="terrace_1"),
        )
        assert r.status_code == 403

    def test_founder_returns_200(self, client):
        r = client.get(
            "/org/timeline/24h", headers=_auth(cohort="founder"),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["window"] == "24h"
        assert body["entries"] == []

    def test_founder_exception_also_allowed(self, client):
        r = client.get(
            "/org/timeline/24h",
            headers=_auth("fe_user", cohort="founder_exception"),
        )
        assert r.status_code == 200

    def test_7d_endpoint_window_label(self, client):
        r = client.get("/org/timeline/7d", headers=_auth())
        assert r.json()["window"] == "7d"

    def test_30d_endpoint_window_label(self, client):
        r = client.get("/org/timeline/30d", headers=_auth())
        assert r.json()["window"] == "30d"


# ===========================================================================
# G. No raw payload / thread_id leakage
# ===========================================================================
class TestNoLeakage:
    def test_thread_id_not_in_org_timeline(self, client):
        # Store a record event that contains thread_id internally.
        el_ins.store_event({
            "operator_id":  "op_alice",
            "event_type":   "record",
            "payload":      {"el": 8.0, "ins": 1.0, "tsi": 90,
                             "reasoning_mode": "grounding",
                             "thread_id": "SECRET-THREAD-123"},
            "timestamp_ms": int(time.time() * 1000),
        })
        r = client.get("/org/timeline/24h", headers=_auth())
        body = r.json()
        # Serialise the whole response and verify no leak.
        import json
        serialised = json.dumps(body)
        assert "SECRET-THREAD-123" not in serialised

    def test_anomaly_message_not_in_org_timeline(self, client):
        el_ins.store_event({
            "operator_id":  "op_alice",
            "event_type":   "anomaly",
            "payload":      {"type": "high_el", "severity": 3,
                             "message": "SECRET-MESSAGE-XYZ",
                             "anomaly_id": "abc"},
            "timestamp_ms": int(time.time() * 1000),
        })
        r = client.get("/org/timeline/24h", headers=_auth())
        import json
        serialised = json.dumps(r.json())
        assert "SECRET-MESSAGE-XYZ" not in serialised

    def test_full_operator_id_not_in_org_timeline(self, client):
        el_ins.store_event({
            "operator_id":  "op_christian_full_id",
            "event_type":   "record",
            "payload":      {"el": 5.0, "ins": 5.0, "tsi": 80},
            "timestamp_ms": int(time.time() * 1000),
        })
        r = client.get("/org/timeline/24h", headers=_auth())
        import json
        serialised = json.dumps(r.json())
        # The full id must not appear; only the masked tail.
        assert "op_christian_full_id" not in serialised
        # Last 6 chars = "ull_id"
        assert "ull_id" in serialised
