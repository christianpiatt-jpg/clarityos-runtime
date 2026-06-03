"""
Phase 5 — monitoring_alerts (modules 19 + 20) + GET /founder/alerts.

Pure compute-and-surface aggregators (no outbound delivery; matches the repo's
established alert pattern). Content-safe: counts/severities/types/levels only,
never anomaly message text or account ids. Module 18 (webhook failures) is
deferred behind billing WIP and surfaced as such.
"""
from __future__ import annotations

import secrets
import time

import pytest


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(username, cohort="founder"):
    import bcrypt
    import sessions_store
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


def _anom(op, idx, sev, atype, ts, msg="ROUTINE_MESSAGE"):
    return {
        "id": f"an_{op}_{idx}", "operator_id": op, "type": atype,
        "severity": sev, "timestamp": ts, "message": msg,
        "record_id": "r1", "thread_id": None,
    }


# ---------------------------------------------------------------------------
# module 19 — kernel_anomaly_alerts
# ---------------------------------------------------------------------------
def test_anomaly_aggregation_and_window(reset_stores):
    import monitoring_alerts as ma
    import users_store
    from el_ins import anomaly_store
    anomaly_store._reset_for_tests()
    now = 1_000_000.0
    users_store.create_user(username="op1", password_hash=b"x", salt="",
                            tier="free", created_at=now)
    anomaly_store.store_anomalies([
        _anom("op1", 1, 2, "high_el", now),
        _anom("op1", 2, 4, "tsi_spike", now),
        _anom("op1", 3, 5, "high_el", now),
        _anom("op1", 4, 3, "low_ins", now - 48 * 3600),   # outside 24h window
    ])
    out = ma.kernel_anomaly_alerts(now_ts=now, window_hours=24)
    assert out["total"] == 3                      # old one excluded
    assert out["high_severity"] == 2              # sev 4 + 5
    assert out["operators_affected"] == 1
    assert out["by_severity"] == {"1": 0, "2": 1, "3": 0, "4": 1, "5": 1}
    assert out["by_type"] == {"high_el": 2, "tsi_spike": 1}
    assert out["level"] == "red"                  # high_severity > 0


def test_anomaly_empty_is_green(reset_stores):
    import monitoring_alerts as ma
    from el_ins import anomaly_store
    anomaly_store._reset_for_tests()
    out = ma.kernel_anomaly_alerts(now_ts=1_000_000.0)
    assert out["total"] == 0
    assert out["level"] == "green"


def test_anomaly_alerts_leak_no_message_text(reset_stores):
    import json
    import monitoring_alerts as ma
    import users_store
    from el_ins import anomaly_store
    anomaly_store._reset_for_tests()
    now = 1_000_000.0
    users_store.create_user(username="op1", password_hash=b"x", salt="",
                            tier="free", created_at=now)
    anomaly_store.store_anomalies([
        _anom("op1", 1, 3, "high_el", now, msg="SECRET_ANOMALY_DETAIL"),
    ])
    out = ma.kernel_anomaly_alerts(now_ts=now)
    assert "SECRET_ANOMALY_DETAIL" not in json.dumps(out)


# ---------------------------------------------------------------------------
# module 20 — membership_churn_alerts
# ---------------------------------------------------------------------------
def test_churn_aggregation(reset_stores):
    import monitoring_alerts as ma
    import users_store
    now = 1_000_000.0

    def mk(name, **bill):
        users_store.create_user(username=name, password_hash=b"x", salt="",
                                tier="free", created_at=now)
        users_store.set_billing_state(name, **bill)

    mk("c1", billing_state="cancelled")
    mk("f1", billing_state="failed")
    mk("p1", billing_state="past_due")
    mk("g1", billing_state="grace_period", renewal_grace_until_ts=now + 2 * 86400)
    mk("a1", billing_state="active")

    out = ma.membership_churn_alerts(now_ts=now, window_days=7)
    assert out["cancelled"] == 1
    assert out["failed"] == 1
    assert out["past_due"] == 1
    assert out["grace_period"] == 1
    assert out["grace_expiring_soon"] == 1        # grace ends in 2d, within 7d
    assert out["at_risk_total"] == 4              # active excluded
    assert out["level"] == "red"                  # hard churn (cancelled+failed)


def test_churn_empty_is_green(reset_stores):
    import monitoring_alerts as ma
    out = ma.membership_churn_alerts(now_ts=1_000_000.0)
    assert out["at_risk_total"] == 0
    assert out["level"] == "green"


# ---------------------------------------------------------------------------
# combined summary + deferred module 18
# ---------------------------------------------------------------------------
def test_summary_shape_and_deferred_webhook(reset_stores):
    import monitoring_alerts as ma
    from el_ins import anomaly_store
    anomaly_store._reset_for_tests()
    s = ma.get_alerts_summary(now_ts=1_000_000.0)
    assert set(s) >= {"overall_level", "kernel_anomalies", "membership_churn",
                      "stripe_webhook_failures", "version"}
    assert s["overall_level"] in ("green", "amber", "red")
    assert s["stripe_webhook_failures"]["status"] == "deferred"


# ---------------------------------------------------------------------------
# endpoint — GET /founder/alerts
# ---------------------------------------------------------------------------
def test_founder_alerts_endpoint_ok(client):
    _u, sid = _make_user("founder1", cohort="founder")
    resp = client.get("/founder/alerts", headers=_auth(sid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "overall_level" in body["alerts"]
    assert body["alerts"]["stripe_webhook_failures"]["status"] == "deferred"


def test_founder_alerts_endpoint_requires_founder(client):
    _u, sid = _make_user("member1", cohort="member")
    resp = client.get("/founder/alerts", headers=_auth(sid))
    assert resp.status_code == 403
