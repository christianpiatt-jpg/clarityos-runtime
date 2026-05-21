"""
Tests for v38 — ELINS interactive dashboard.

Covers:
* elins_dashboard.get_dashboard_snapshot — empty state, after global only,
  after macro pass (full coverage), determinism.
* elins_dashboard.get_dashboard_for_date — pinned-day behaviour.
* /elins/dashboard endpoint shape + auth gate.
* /elins/dashboard/{date} endpoint validation + 200 path.
* /founder/elins/dashboard/overview shape + founder gate.
* Capabilities advertise the new id.
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
# Pure function — get_dashboard_snapshot
# ---------------------------------------------------------------------------
def test_snapshot_empty_state(reset_stores):
    import elins_dashboard
    snap = elins_dashboard.get_dashboard_snapshot("alice")
    assert snap["version"].startswith("elins_dashboard.v")
    assert snap["date"]
    assert snap["global"]["available"] is False
    for region in ("US", "EU", "MEA", "APAC", "Markets", "Tech"):
        assert region in snap["regional"]
        assert snap["regional"][region]["available"] is False
    assert snap["macro"]["last_run_id"] is None
    assert snap["entity_graph"]["available"] is False
    assert snap["entity_graph"]["entity_count"] == 0


def test_snapshot_after_global_only(reset_stores):
    """Saving a global daily run should populate the global section
    even when no regional or macro pass has happened."""
    from ELINS import standard_elins, elins_project
    import elins_dashboard
    obj = standard_elins.generate_ELINS(
        "global pressure on institutions and trust between partners erodes",
        user="alice",
    )
    elins_project.save_daily_run("alice", obj)
    snap = elins_dashboard.get_dashboard_snapshot("alice")
    assert snap["global"]["available"] is True
    assert snap["global"]["ep_mean"] >= 0.0
    assert isinstance(snap["global"]["domains"], dict)
    # No regional yet
    for region in ("US", "EU", "MEA", "APAC", "Markets", "Tech"):
        assert snap["regional"][region]["available"] is False


def test_snapshot_falls_back_to_system_user_when_caller_has_no_runs(reset_stores):
    """When the caller has never persisted a run but the scheduler has,
    the snapshot should surface the system user's run instead of empty."""
    import elins_scheduler
    import elins_dashboard
    elins_scheduler._run_macro_elins_once(force=True)
    snap = elins_dashboard.get_dashboard_snapshot("brand_new_user")
    assert snap["global"]["available"] is True
    assert snap["global"]["user"] == "scheduler"


def test_snapshot_after_macro_pass_full_coverage(reset_stores):
    """Macro pass should populate every section (global + regional +
    macro + entity_graph) when ESO is enabled."""
    import elins_scheduler, elins_scheduler_config
    import elins_dashboard
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    snap = elins_dashboard.get_dashboard_snapshot("alice")
    assert snap["global"]["available"] is True
    for region in ("US", "EU", "MEA", "APAC", "Markets", "Tech"):
        assert snap["regional"][region]["available"] is True
    assert snap["macro"]["last_run_id"] is not None
    assert snap["macro"]["regions_count"] == 6
    assert snap["macro"]["external_signal_mode"] == "cloud_perplexity"
    assert snap["entity_graph"]["available"] is True
    assert snap["entity_graph"]["entity_count"] > 0
    assert len(snap["entity_graph"]["top_entities"]) > 0


def test_snapshot_top_primitives_sorted_desc(reset_stores):
    from ELINS import standard_elins, elins_project
    import elins_dashboard
    obj = standard_elins.generate_ELINS(
        "trust pressure tension drift contradiction alignment", user="alice",
    )
    elins_project.save_daily_run("alice", obj)
    snap = elins_dashboard.get_dashboard_snapshot("alice")
    tops = snap["global"]["top_primitives"]
    intensities = [p["intensity"] for p in tops]
    assert intensities == sorted(intensities, reverse=True)


def test_snapshot_forecast_length_matches_engine(reset_stores):
    from ELINS import standard_elins, elins_project
    import elins_dashboard
    obj = standard_elins.generate_ELINS(
        "the institution is drifting under enormous pressure and contradiction.",
        user="alice",
    )
    elins_project.save_daily_run("alice", obj)
    snap = elins_dashboard.get_dashboard_snapshot("alice")
    # Forecast engine emits days+1 entries; default days=5 → 6.
    assert len(snap["global"]["forecast"]) == 6


def test_snapshot_is_deterministic_given_fixed_state(reset_stores):
    import elins_scheduler, elins_scheduler_config
    import elins_dashboard
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    a = elins_dashboard.get_dashboard_snapshot("alice")
    b = elins_dashboard.get_dashboard_snapshot("alice")
    # ts differs by call time; everything else should be identical.
    a.pop("ts", None); b.pop("ts", None)
    a.pop("date", None); b.pop("date", None)
    assert a == b


# ---------------------------------------------------------------------------
# Pure function — get_dashboard_for_date
# ---------------------------------------------------------------------------
def test_for_date_validates(reset_stores):
    import elins_dashboard
    with pytest.raises(ValueError):
        elins_dashboard.get_dashboard_for_date("alice", "")
    with pytest.raises(ValueError):
        elins_dashboard.get_dashboard_for_date("alice", "2026/05/06")
    with pytest.raises(ValueError):
        elins_dashboard.get_dashboard_for_date("alice", "5/6/26")


def test_for_date_pins_to_specific_day(reset_stores):
    """Saving a run on a specific day and asking for that day should
    resolve. Other days should be empty."""
    from ELINS import standard_elins, elins_project, regional_elins
    import elins_dashboard
    obj = standard_elins.generate_ELINS("pressure", user="alice")
    elins_project.save_daily_run("alice", obj, day="2026-05-06")
    rgn = regional_elins.run_regional_elins("US", user="alice")
    elins_project.save_regional_run("US", "2026-05-06", rgn)
    snap = elins_dashboard.get_dashboard_for_date("alice", "2026-05-06")
    assert snap["date"] == "2026-05-06"
    assert snap["global"]["available"] is True
    assert snap["regional"]["US"]["available"] is True
    snap_other = elins_dashboard.get_dashboard_for_date("alice", "2025-01-01")
    assert snap_other["regional"]["US"]["available"] is False


# ---------------------------------------------------------------------------
# Endpoint — /elins/dashboard
# ---------------------------------------------------------------------------
def test_endpoint_dashboard_default_user(app_module, client):
    user, sid = _make_user(app_module, "ed_a", cohort="founder")
    r = client.get("/elins/dashboard", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    snap = body["snapshot"]
    assert {"ts", "date", "global", "regional", "macro", "entity_graph", "version"} <= set(snap.keys())
    for region in ("US", "EU", "MEA", "APAC", "Markets", "Tech"):
        assert region in snap["regional"]


def test_endpoint_dashboard_after_macro_pass(app_module, client):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "ed_b", cohort="founder")
    r = client.get("/elins/dashboard", headers=_auth(sid))
    assert r.status_code == 200
    snap = r.json()["snapshot"]
    assert snap["entity_graph"]["available"] is True
    assert snap["macro"]["last_run_id"] is not None


def test_endpoint_dashboard_blocked_when_v28_off(app_module, client):
    user, sid = _make_user(app_module, "ed_lurker", cohort=None)
    r = client.get("/elins/dashboard", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_dashboard_for_date_happy_path(app_module, client):
    user, sid = _make_user(app_module, "ed_c", cohort="founder")
    r = client.get("/elins/dashboard/2026-05-06", headers=_auth(sid))
    assert r.status_code == 200
    snap = r.json()["snapshot"]
    assert snap["date"] == "2026-05-06"


def test_endpoint_dashboard_for_date_validation(app_module, client):
    user, sid = _make_user(app_module, "ed_d", cohort="founder")
    r = client.get("/elins/dashboard/not-a-date", headers=_auth(sid))
    assert r.status_code == 400


def test_endpoint_dashboard_for_date_blocked_when_v28_off(app_module, client):
    user, sid = _make_user(app_module, "ed_lurker2", cohort=None)
    r = client.get("/elins/dashboard/2026-05-06", headers=_auth(sid))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Endpoint — /founder/elins/dashboard/overview
# ---------------------------------------------------------------------------
def test_endpoint_overview_returns_counts(app_module, client):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "fo_a", cohort="founder")
    r = client.get("/founder/elins/dashboard/overview", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    overview = r.json()["overview"]
    assert overview["macro_runs_count"] >= 1
    assert overview["entity_graph_snapshots"] >= 1
    assert isinstance(overview["regional_coverage"], dict)
    for region in ("US", "EU", "MEA", "APAC", "Markets", "Tech"):
        assert region in overview["regional_coverage"]
        assert overview["regional_coverage"][region]["runs"] >= 1
    assert overview["scheduler_config"]["external_signal_mode"] == "cloud_perplexity"


def test_endpoint_overview_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "fo_outsider", cohort=None)
    r = client.get("/founder/elins/dashboard/overview", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_overview_empty_state(app_module, client):
    user, sid = _make_user(app_module, "fo_empty", cohort="founder")
    r = client.get("/founder/elins/dashboard/overview", headers=_auth(sid))
    assert r.status_code == 200
    overview = r.json()["overview"]
    assert overview["macro_runs_count"] == 0
    assert overview["entity_graph_snapshots"] == 0
    assert overview["latest_date"] is None


# ---------------------------------------------------------------------------
# Capabilities advertise the new id
# ---------------------------------------------------------------------------
def test_me_advertises_dashboard_capability(app_module, client):
    user, sid = _make_user(app_module, "cap_a", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    assert r.status_code == 200
    ids = [c["id"] for c in r.json().get("capabilities") or []]
    assert "elins_dashboard" in ids


# ---------------------------------------------------------------------------
# UI shape lockdown
# ---------------------------------------------------------------------------
def test_ui_shape_for_dashboard_response(app_module, client):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "ui_d", cohort="founder")
    r = client.get("/elins/dashboard", headers=_auth(sid))
    snap = r.json()["snapshot"]
    g = snap["global"]
    assert {"scenario_id", "ep_mean", "domains", "top_primitives",
            "forecast", "has_eso", "available"} <= set(g.keys())
    e = snap["entity_graph"]
    assert {"entity_count", "edge_count", "updated_ts",
            "top_entities", "available"} <= set(e.keys())
    if e["top_entities"]:
        ent = e["top_entities"][0]
        assert {"name", "degree", "ep_mean", "top_domains"} <= set(ent.keys())
    m = snap["macro"]
    assert {"last_run_id", "last_run_ts", "ep_mean",
            "regions_count", "external_signal_mode"} <= set(m.keys())
