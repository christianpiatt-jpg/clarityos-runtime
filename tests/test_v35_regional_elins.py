"""
Tests for v35 — Regional ELINS Modules + ESO-aware regional fields.

Covers:
* perplexity_oracle.fetch_basin_signals — ESO shape per region
* regional_elins.run_regional_elins — full pipeline run for each region
* ESO-conditional behaviour (cloud_perplexity vs default off)
* elins_project regional persistence (save / load / latest / list)
* Endpoints: /elins/regional/run, /elins/regional/list,
  /founder/elins/regional/batch + auth + validation
* Determinism (same input → same output)
* UI API shape — region_code, external_signals, regional_delta, etc.
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


def _make_user(app_module, username, cohort="founder", *, signal_mode=None):
    import secrets
    import users_store, sessions_store, bcrypt
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    patch = {}
    if cohort:
        patch["cohort"] = cohort
    if signal_mode is not None:
        patch["external_signal_mode"] = signal_mode
    if patch:
        users_store.update_user(username, patch)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ---------------------------------------------------------------------------
# perplexity_oracle
# ---------------------------------------------------------------------------
def test_oracle_fetch_returns_eso_per_region(reset_stores):
    import perplexity_oracle as po
    for region in po.SUPPORTED_REGIONS:
        eso = po.fetch_basin_signals(region)
        assert isinstance(eso, dict)
        assert eso["region_code"] == region
        assert isinstance(eso["signals"], list) and len(eso["signals"]) > 0
        for sig in eso["signals"]:
            assert "key" in sig and "intensity" in sig
        assert isinstance(eso["anchors"], list)
        assert isinstance(eso["domain_bias"], dict)
        assert eso["mock"] is True
        assert eso["version"].startswith("perplexity_oracle.v")


def test_oracle_unknown_region_raises(reset_stores):
    import perplexity_oracle as po
    with pytest.raises(ValueError):
        po.fetch_basin_signals("ZZ")


def test_oracle_off_mode_returns_none(reset_stores):
    import perplexity_oracle as po
    assert po.fetch_basin_signals("US", mode="off") is None


def test_is_eso_enabled_only_for_cloud_perplexity(reset_stores):
    import perplexity_oracle as po
    assert po.is_eso_enabled({"external_signal_mode": "cloud_perplexity"}) is True
    assert po.is_eso_enabled({"external_signal_mode": "off"}) is False
    assert po.is_eso_enabled({}) is False
    assert po.is_eso_enabled(None) is False


def test_oracle_is_deterministic(reset_stores):
    import perplexity_oracle as po
    a = po.fetch_basin_signals("MEA")
    b = po.fetch_basin_signals("MEA")
    assert a == b


# ---------------------------------------------------------------------------
# regional_elins.run_regional_elins
# ---------------------------------------------------------------------------
def test_run_regional_elins_for_each_region(reset_stores):
    from ELINS import regional_elins
    for region in regional_elins.REGION_CODES:
        out = regional_elins.run_regional_elins(region, user="alice")
        assert out["region_code"] == region
        assert "primitives" in out and "intensities" in out["primitives"]
        assert "ep_field_summary" in out
        assert "forecast_engine" in out
        assert out["forecast_engine"]["region_code"] == region
        # external_signals always present (even if empty)
        assert "external_signals" in out
        assert out["external_signals"]["present"] is False  # no ESO supplied


def test_run_regional_elins_with_eso_marks_external(reset_stores):
    from ELINS import regional_elins
    import perplexity_oracle as po
    eso = po.fetch_basin_signals("MEA")
    out = regional_elins.run_regional_elins("MEA", user="alice", eso=eso)
    assert out["external_signals"]["present"] is True
    assert out["external_signals"]["region_code"] == "MEA"
    assert len(out["external_signals"]["anchors"]) > 0
    # Synthesis surface mirrors anchors
    assert out["synthesis"]["external_present"] is True
    assert out["synthesis"]["external_anchors"] == eso["anchors"]


def test_run_regional_elins_without_eso_synthesis_clean(reset_stores):
    from ELINS import regional_elins
    out = regional_elins.run_regional_elins("US", user="alice", eso=None)
    assert out["external_signals"]["present"] is False
    assert out["synthesis"]["external_present"] is False
    assert out["synthesis"]["external_anchors"] == []


def test_run_regional_elins_topic_hint_appears_in_input(reset_stores):
    from ELINS import regional_elins
    out = regional_elins.run_regional_elins(
        "US", user="alice", topic_hint="Senate vote on antitrust",
    )
    text = (out.get("input_phase") or {}).get("text") or ""
    assert "Senate" in text


def test_run_regional_elins_eso_boosts_primitive(reset_stores):
    from ELINS import regional_elins
    import perplexity_oracle as po
    base = regional_elins.run_regional_elins("MEA", user="alice")
    eso = po.fetch_basin_signals("MEA")
    boosted = regional_elins.run_regional_elins("MEA", user="alice", eso=eso)
    base_pressure = base["primitives"]["intensities"]["pressure"]
    boost_pressure = boosted["primitives"]["intensities"]["pressure"]
    assert boost_pressure >= base_pressure  # ESO never lowers contribution


def test_run_regional_elins_unknown_region_raises(reset_stores):
    from ELINS import regional_elins
    with pytest.raises(ValueError):
        regional_elins.run_regional_elins("ZZ", user="alice")


def test_run_regional_elins_is_deterministic(reset_stores):
    from ELINS import regional_elins
    import perplexity_oracle as po
    eso = po.fetch_basin_signals("APAC")
    a = regional_elins.run_regional_elins("APAC", user="alice", topic_hint="t", eso=eso)
    b = regional_elins.run_regional_elins("APAC", user="alice", topic_hint="t", eso=eso)
    # ts fields differ by microseconds — drop them.
    a["input_phase"].pop("ts", None); b["input_phase"].pop("ts", None)
    a["output_object"].pop("ts", None); b["output_object"].pop("ts", None)
    a.pop("regional_run_ts", None); b.pop("regional_run_ts", None)
    assert a["primitives"] == b["primitives"]
    assert a["forecast_engine"] == b["forecast_engine"]
    assert a["synthesis"] == b["synthesis"]


def test_run_regional_elins_attaches_delta_when_previous_supplied(reset_stores):
    from ELINS import regional_elins
    prev = regional_elins.run_regional_elins("Markets", user="alice")
    cur = regional_elins.run_regional_elins(
        "Markets", user="alice", topic_hint="curve repricing", previous_run=prev,
    )
    delta = cur["regional_delta"]
    assert delta is not None
    assert "deltas" in delta
    assert delta["previous_scenario_id"] == prev["output_object"]["scenario_id"]


# ---------------------------------------------------------------------------
# elins_project regional persistence
# ---------------------------------------------------------------------------
def test_save_and_load_regional_run(reset_stores):
    from ELINS import regional_elins, elins_project
    out = regional_elins.run_regional_elins("EU", user="alice")
    run_id = elins_project.save_regional_run("EU", "2026-05-06", out)
    loaded = elins_project.load_regional_run("EU", "2026-05-06")
    assert loaded is not None
    assert loaded["id"] == run_id
    assert loaded["region_code"] == "EU"
    assert loaded["elins"]["region_code"] == "EU"


def test_save_regional_run_idempotent_on_same_day(reset_stores):
    from ELINS import regional_elins, elins_project
    a = regional_elins.run_regional_elins("EU", user="alice")
    b = regional_elins.run_regional_elins("EU", user="alice", topic_hint="b")
    id1 = elins_project.save_regional_run("EU", "2026-05-06", a)
    id2 = elins_project.save_regional_run("EU", "2026-05-06", b)
    assert id1 == id2
    runs = elins_project.list_regional_runs("EU")
    assert len(runs) == 1


def test_latest_regional_run_returns_most_recent(reset_stores):
    from ELINS import regional_elins, elins_project
    a = regional_elins.run_regional_elins("Tech", user="alice", topic_hint="day1")
    b = regional_elins.run_regional_elins("Tech", user="alice", topic_hint="day2")
    elins_project.save_regional_run("Tech", "2026-05-04", a)
    elins_project.save_regional_run("Tech", "2026-05-06", b)
    latest = elins_project.latest_regional_run("Tech")
    assert latest is not None
    assert latest["day"] == "2026-05-06"


def test_list_regional_runs_returns_all_for_region(reset_stores):
    from ELINS import regional_elins, elins_project
    for d in ("2026-05-04", "2026-05-05", "2026-05-06"):
        elins_project.save_regional_run(
            "APAC", d,
            regional_elins.run_regional_elins("APAC", user="alice", topic_hint=d),
        )
    rows = elins_project.list_regional_runs("APAC")
    assert len(rows) == 3
    days = [r["day"] for r in rows]
    assert days == sorted(days, reverse=True)


def test_save_regional_run_rejects_unknown_region(reset_stores):
    from ELINS import regional_elins, elins_project
    out = regional_elins.run_regional_elins("US", user="alice")
    with pytest.raises(ValueError):
        elins_project.save_regional_run("ZZ", None, out)


# ---------------------------------------------------------------------------
# /elins/regional/run endpoint
# ---------------------------------------------------------------------------
def test_endpoint_regional_run_returns_block(app_module, client):
    user, sid = _make_user(app_module, "rr_a", cohort="founder")
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "US", "topic_hint": "Senate hearing"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["region_code"] == "US"
    assert body["elins"]["region_code"] == "US"
    assert "forecast_engine" in body["elins"]
    # Default mode is no ESO.
    assert body["eso_present"] is False
    assert body["elins"]["external_signals"]["present"] is False


def test_endpoint_regional_run_persists(app_module, client):
    from ELINS import elins_project
    user, sid = _make_user(app_module, "rr_p", cohort="founder")
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "EU"},
    )
    assert r.status_code == 200
    run_id = r.json()["run_id"]
    runs = elins_project.list_regional_runs("EU")
    assert any(row["id"] == run_id for row in runs)


def test_endpoint_regional_run_attaches_eso_when_user_opted_in(app_module, client):
    user, sid = _make_user(
        app_module, "rr_eso", cohort="founder",
        signal_mode="cloud_perplexity",
    )
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "MEA"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["eso_present"] is True
    assert body["elins"]["external_signals"]["present"] is True
    assert len(body["elins"]["external_signals"]["anchors"]) > 0


def test_endpoint_regional_run_no_eso_when_signal_mode_off(app_module, client):
    user, sid = _make_user(
        app_module, "rr_noeso", cohort="founder",
        signal_mode="off",
    )
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "MEA"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["eso_present"] is False


def test_endpoint_regional_run_rejects_unknown_region(app_module, client):
    user, sid = _make_user(app_module, "rr_bad", cohort="founder")
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "ZZ"},
    )
    assert r.status_code == 400


def test_endpoint_regional_run_blocked_when_v28_off(app_module, client):
    user, sid = _make_user(app_module, "rr_lurker", cohort=None)
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "US"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# /elins/regional/list endpoint
# ---------------------------------------------------------------------------
def test_endpoint_regional_list_returns_all_regions(app_module, client):
    user, sid = _make_user(app_module, "rl_a", cohort="founder")
    r = client.get("/elins/regional/list", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["regions"] == ["US", "EU", "MEA", "APAC", "Markets", "Tech"]
    assert len(body["items"]) == 6
    for item in body["items"]:
        assert "region_code" in item
        # latest is None until first run
        assert "latest" in item


def test_endpoint_regional_list_reflects_runs(app_module, client):
    user, sid = _make_user(app_module, "rl_b", cohort="founder")
    client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "Tech"},
    )
    r = client.get("/elins/regional/list", headers=_auth(sid))
    assert r.status_code == 200
    items = {it["region_code"]: it for it in r.json()["items"]}
    assert items["Tech"]["latest"] is not None
    assert items["US"]["latest"] is None


# ---------------------------------------------------------------------------
# /founder/elins/regional/batch endpoint
# ---------------------------------------------------------------------------
def test_endpoint_regional_batch_runs_multiple(app_module, client):
    from ELINS import elins_project
    user, sid = _make_user(app_module, "rb_a", cohort="founder")
    r = client.post(
        "/founder/elins/regional/batch", headers=_auth(sid),
        json={"regions": ["US", "EU", "Markets"]},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert set(body["results"].keys()) == {"US", "EU", "Markets"}
    assert set(body["run_ids"].keys()) == {"US", "EU", "Markets"}
    for region in ("US", "EU", "Markets"):
        assert body["results"][region]["region_code"] == region
        runs = elins_project.list_regional_runs(region)
        assert any(row["id"] == body["run_ids"][region] for row in runs)


def test_endpoint_regional_batch_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "rb_outsider", cohort=None)
    r = client.post(
        "/founder/elins/regional/batch", headers=_auth(sid),
        json={"regions": ["US"]},
    )
    assert r.status_code == 403


def test_endpoint_regional_batch_rejects_empty(app_module, client):
    user, sid = _make_user(app_module, "rb_empty", cohort="founder")
    r = client.post(
        "/founder/elins/regional/batch", headers=_auth(sid),
        json={"regions": []},
    )
    assert r.status_code == 400


def test_endpoint_regional_batch_rejects_unknown(app_module, client):
    user, sid = _make_user(app_module, "rb_bad", cohort="founder")
    r = client.post(
        "/founder/elins/regional/batch", headers=_auth(sid),
        json={"regions": ["US", "ZZ"]},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# UI API shape — locks the keys the web + phone components rely on.
# ---------------------------------------------------------------------------
def test_ui_api_shape_for_regional_run(app_module, client):
    user, sid = _make_user(
        app_module, "ui_a", cohort="founder", signal_mode="cloud_perplexity",
    )
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "MEA"},
    )
    assert r.status_code == 200
    body = r.json()
    assert {"ok", "run_id", "region_code", "elins", "eso_present"} <= set(body.keys())
    elins = body["elins"]
    assert {"region_code", "topic_hint", "external_signals", "regional_delta",
            "primitives", "ep_field_summary", "forecast_engine",
            "synthesis", "output_object"} <= set(elins.keys())
    ext = elins["external_signals"]
    assert {"present", "region_code", "anchors", "signals"} <= set(ext.keys())
    syn = elins["synthesis"]
    assert {"region_code", "external_anchors", "external_present",
            "top_primitive", "domain", "signal", "trend"} <= set(syn.keys())


def test_regional_run_v35_version_string(reset_stores):
    from ELINS import regional_elins
    out = regional_elins.run_regional_elins("US", user="alice")
    assert out["output_object"]["version"].startswith("elins.regional.v35")
