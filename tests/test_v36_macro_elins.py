"""
Tests for v36 — Macro-ELINS automation + scheduled global/regional runs.

Covers:
* elins_scheduler._run_macro_elins_once — runs global + all regions,
  persists everything, records the macro-run summary.
* Scheduler config gating: enabled flag, cadence, external_signal_mode.
* elins_project.record_macro_run / list_macro_runs / get_macro_run /
  get_macro_run_with_constituents.
* Founder endpoints: status, config, run_now, runs list, run detail.
* Determinism (region set + global scenario + record fields).
"""
from __future__ import annotations

import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(app_module, username, cohort="founder"):
    import secrets
    import users_store, sessions_store, bcrypt
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


# ---------------------------------------------------------------------------
# elins_scheduler._run_macro_elins_once
# ---------------------------------------------------------------------------
def test_run_macro_elins_once_runs_global_and_all_regions(reset_stores):
    import elins_scheduler
    from ELINS import elins_project, regional_elins
    summary = elins_scheduler._run_macro_elins_once(force=True)
    assert summary["ran"] is True
    assert set(summary["regions"]) == set(regional_elins.REGION_CODES)
    assert summary["global_run_id"]
    # Global persisted
    runs = elins_project.list_runs_for_user(summary["macro_record"]["global_run_ref"]["run_id"].split("_", 1)[0])
    # The global save uses user= system_user, so look it up
    sys_user = "scheduler"
    global_runs = elins_project.list_runs_for_user(sys_user)
    assert any(r["id"] == summary["global_run_id"] for r in global_runs)
    # Regional persisted
    for region in regional_elins.REGION_CODES:
        rgn_runs = elins_project.list_regional_runs(region)
        assert len(rgn_runs) >= 1
    # Macro-run record persisted
    record = elins_project.get_macro_run(summary["run_id"])
    assert record is not None
    assert record["regions"] == summary["regions"]


def test_run_macro_elins_once_respects_signal_mode(reset_stores):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    summary = elins_scheduler._run_macro_elins_once(force=True)
    assert summary["external_signal_mode"] == "cloud_perplexity"
    # Each regional run should have ESO present.
    from ELINS import elins_project, regional_elins
    for region in regional_elins.REGION_CODES:
        rgn = elins_project.latest_regional_run(region)
        assert rgn is not None
        ext = rgn["elins"].get("external_signals") or {}
        assert ext.get("present") is True, f"region={region}"


def test_run_macro_elins_once_default_mode_no_eso(reset_stores):
    import elins_scheduler
    # Default config has external_signal_mode = cloud_only
    summary = elins_scheduler._run_macro_elins_once(force=True)
    assert summary["external_signal_mode"] == "cloud_only"
    from ELINS import elins_project, regional_elins
    for region in regional_elins.REGION_CODES:
        rgn = elins_project.latest_regional_run(region)
        ext = rgn["elins"].get("external_signals") or {}
        assert ext.get("present") is False


def test_run_macro_elins_once_updates_last_run_ts(reset_stores):
    import elins_scheduler, elins_scheduler_config
    before = elins_scheduler_config.get_config().get("last_run_ts") or 0.0
    elins_scheduler._run_macro_elins_once(force=True)
    after = elins_scheduler_config.get_config().get("last_run_ts") or 0.0
    assert after > before


# ---------------------------------------------------------------------------
# Cadence gating
# ---------------------------------------------------------------------------
def test_scheduler_off_cadence_never_due(reset_stores):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"enabled": True, "cadence": "off"})
    cfg = elins_scheduler_config.get_config()
    assert elins_scheduler._is_due(cfg, time.time()) is False


def test_scheduler_disabled_never_due(reset_stores):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"enabled": False, "cadence": "daily"})
    cfg = elins_scheduler_config.get_config()
    assert elins_scheduler._is_due(cfg, time.time()) is False


def test_scheduler_due_when_first_run(reset_stores):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config(
        {"enabled": True, "cadence": "3x_week", "last_run_ts": 0.0},
    )
    cfg = elins_scheduler_config.get_config()
    assert elins_scheduler._is_due(cfg, time.time()) is True


def test_scheduler_not_due_within_interval(reset_stores):
    import elins_scheduler, elins_scheduler_config
    now = time.time()
    elins_scheduler_config.set_config({
        "enabled": True, "cadence": "daily", "last_run_ts": now - 100.0,
    })
    cfg = elins_scheduler_config.get_config()
    assert elins_scheduler._is_due(cfg, now) is False


def test_scheduler_due_after_interval(reset_stores):
    import elins_scheduler, elins_scheduler_config
    now = time.time()
    elins_scheduler_config.set_config({
        "enabled": True, "cadence": "daily", "last_run_ts": now - (24 * 3600 + 60),
    })
    cfg = elins_scheduler_config.get_config()
    assert elins_scheduler._is_due(cfg, now) is True


def test_run_macro_elins_skips_when_not_due(reset_stores):
    import elins_scheduler, elins_scheduler_config
    now = time.time()
    elins_scheduler_config.set_config({
        "enabled": True, "cadence": "daily", "last_run_ts": now - 100.0,
    })
    summary = elins_scheduler._run_macro_elins_once(now_ts=now, force=False)
    assert summary["ran"] is False
    assert summary["reason"] == "not_due"


def test_run_macro_elins_runs_when_due(reset_stores):
    import elins_scheduler, elins_scheduler_config
    now = time.time()
    elins_scheduler_config.set_config({
        "enabled": True, "cadence": "daily", "last_run_ts": now - (24 * 3600 + 60),
    })
    summary = elins_scheduler._run_macro_elins_once(now_ts=now, force=False)
    assert summary["ran"] is True


# ---------------------------------------------------------------------------
# elins_project macro-run helpers
# ---------------------------------------------------------------------------
def test_record_and_get_macro_run(reset_stores):
    from ELINS import elins_project
    rec = elins_project.record_macro_run(
        ts=time.time(), run_id="macro_test_1",
        regions=["US", "EU"],
        global_run_ref={"run_id": "g1", "scenario_id": "sc_x"},
        notes="test", region_run_ids={"US": "US_2026-05-06"},
        external_signal_mode="cloud_only",
    )
    assert rec["run_id"] == "macro_test_1"
    assert elins_project.get_macro_run("macro_test_1") is not None
    rows = elins_project.list_macro_runs()
    assert any(r["run_id"] == "macro_test_1" for r in rows)


def test_list_macro_runs_newest_first(reset_stores):
    from ELINS import elins_project
    elins_project.record_macro_run(
        ts=1000.0, run_id="macro_a", regions=[], global_run_ref={},
    )
    elins_project.record_macro_run(
        ts=2000.0, run_id="macro_b", regions=[], global_run_ref={},
    )
    rows = elins_project.list_macro_runs()
    assert rows[0]["run_id"] == "macro_b"
    assert rows[1]["run_id"] == "macro_a"


def test_get_macro_run_unknown_returns_none(reset_stores):
    from ELINS import elins_project
    assert elins_project.get_macro_run("does-not-exist") is None


def test_get_macro_run_with_constituents(reset_stores):
    import elins_scheduler
    from ELINS import elins_project
    summary = elins_scheduler._run_macro_elins_once(force=True)
    detail = elins_project.get_macro_run_with_constituents(summary["run_id"])
    assert detail is not None
    assert "global_run" in detail
    assert "regional_runs" in detail
    # All regions resolved
    from ELINS import regional_elins
    for region in regional_elins.REGION_CODES:
        assert region in detail["regional_runs"]


# ---------------------------------------------------------------------------
# Endpoints — /founder/elins/scheduler/{status,config}
# ---------------------------------------------------------------------------
def test_endpoint_scheduler_status_default(app_module, client):
    user, sid = _make_user(app_module, "sched_a", cohort="founder")
    r = client.get("/founder/elins/scheduler/status", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["config"]["cadence"] in ("off", "daily", "3x_week", "weekly")
    assert "running" in body
    assert isinstance(body["valid_cadences"], list)


def test_endpoint_scheduler_status_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "sched_outsider", cohort=None)
    r = client.get("/founder/elins/scheduler/status", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_scheduler_config_persists_changes(app_module, client):
    user, sid = _make_user(app_module, "sched_b", cohort="founder")
    r = client.post(
        "/founder/elins/scheduler/config", headers=_auth(sid),
        json={"cadence": "daily", "external_signal_mode": "cloud_perplexity"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["config"]["cadence"] == "daily"
    assert body["config"]["external_signal_mode"] == "cloud_perplexity"
    # Status round-trip
    r2 = client.get("/founder/elins/scheduler/status", headers=_auth(sid))
    assert r2.json()["config"]["cadence"] == "daily"


def test_endpoint_scheduler_config_rejects_bad_cadence(app_module, client):
    user, sid = _make_user(app_module, "sched_bad", cohort="founder")
    r = client.post(
        "/founder/elins/scheduler/config", headers=_auth(sid),
        json={"cadence": "hourly"},
    )
    assert r.status_code == 400


def test_endpoint_scheduler_config_rejects_bad_signal_mode(app_module, client):
    user, sid = _make_user(app_module, "sched_bad2", cohort="founder")
    r = client.post(
        "/founder/elins/scheduler/config", headers=_auth(sid),
        json={"external_signal_mode": "totally_made_up"},
    )
    assert r.status_code == 400


def test_endpoint_scheduler_config_enabled_starts_thread(app_module, client):
    import elins_scheduler
    user, sid = _make_user(app_module, "sched_on", cohort="founder")
    assert elins_scheduler.is_running() is False
    r = client.post(
        "/founder/elins/scheduler/config", headers=_auth(sid),
        json={"enabled": True, "cadence": "off"},  # off cadence keeps ticks no-op
    )
    assert r.status_code == 200
    assert r.json()["running"] is True
    # Disable round-trip
    r2 = client.post(
        "/founder/elins/scheduler/config", headers=_auth(sid),
        json={"enabled": False},
    )
    assert r2.json()["running"] is False
    elins_scheduler._reset_for_tests()


# ---------------------------------------------------------------------------
# Endpoint — /founder/elins/macro/run_now
# ---------------------------------------------------------------------------
def test_endpoint_run_now_executes_pass(app_module, client):
    user, sid = _make_user(app_module, "rn_a", cohort="founder")
    r = client.post("/founder/elins/macro/run_now", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    summary = r.json()["summary"]
    assert summary["ran"] is True
    assert len(summary["regions"]) == 6


def test_endpoint_run_now_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "rn_outsider", cohort=None)
    r = client.post("/founder/elins/macro/run_now", headers=_auth(sid))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Endpoints — /founder/elins/macro/runs + run/{run_id}
# ---------------------------------------------------------------------------
def test_endpoint_macro_runs_returns_list(app_module, client):
    user, sid = _make_user(app_module, "ml_a", cohort="founder")
    client.post("/founder/elins/macro/run_now", headers=_auth(sid))
    client.post("/founder/elins/macro/run_now", headers=_auth(sid))
    r = client.get("/founder/elins/macro/runs", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["count"] >= 2
    assert isinstance(body["runs"], list)


def test_endpoint_macro_run_detail_returns_constituents(app_module, client):
    user, sid = _make_user(app_module, "md_a", cohort="founder")
    summary = client.post("/founder/elins/macro/run_now", headers=_auth(sid)).json()["summary"]
    run_id = summary["run_id"]
    r = client.get(f"/founder/elins/macro/run/{run_id}", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    detail = r.json()["run"]
    assert detail["run_id"] == run_id
    assert "global_run" in detail
    assert "regional_runs" in detail
    assert len(detail["regional_runs"]) == 6


def test_endpoint_macro_run_detail_404_unknown(app_module, client):
    user, sid = _make_user(app_module, "md_b", cohort="founder")
    r = client.get("/founder/elins/macro/run/macro_does_not_exist", headers=_auth(sid))
    assert r.status_code == 404


def test_endpoint_macro_runs_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "ml_outsider", cohort=None)
    r = client.get("/founder/elins/macro/runs", headers=_auth(sid))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# UI shape
# ---------------------------------------------------------------------------
def test_ui_shape_for_run_now(app_module, client):
    user, sid = _make_user(app_module, "ui_a", cohort="founder")
    r = client.post("/founder/elins/macro/run_now", headers=_auth(sid))
    assert r.status_code == 200
    summary = r.json()["summary"]
    assert {"ran", "run_id", "ts", "regions", "global_run_id",
            "external_signal_mode", "cadence", "macro_record"} <= set(summary.keys())


def test_ui_shape_for_macro_run_detail(app_module, client):
    user, sid = _make_user(app_module, "ui_b", cohort="founder")
    summary = client.post("/founder/elins/macro/run_now", headers=_auth(sid)).json()["summary"]
    r = client.get(f"/founder/elins/macro/run/{summary['run_id']}", headers=_auth(sid))
    detail = r.json()["run"]
    assert {"run_id", "ts", "regions", "global_run_ref", "region_run_ids",
            "external_signal_mode", "notes",
            "global_run", "regional_runs"} <= set(detail.keys())


# ---------------------------------------------------------------------------
# Determinism — the regions set + ESO mode in the macro record are stable.
# ---------------------------------------------------------------------------
def test_macro_run_regions_set_is_stable(reset_stores):
    import elins_scheduler
    from ELINS import regional_elins
    a = elins_scheduler._run_macro_elins_once(force=True)
    b = elins_scheduler._run_macro_elins_once(force=True)
    assert a["regions"] == b["regions"] == list(regional_elins.REGION_CODES)
    assert a["external_signal_mode"] == b["external_signal_mode"]
