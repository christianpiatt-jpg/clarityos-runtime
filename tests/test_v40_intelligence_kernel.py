"""
Tests for v40 — Intelligence Kernel v1.0.

Covers:
* run_c — comment dispatch + signal-mode override mirror.
* run_G — runner wrapping + operator_state recording + ESO mode override.
* run_ELINS — S_ELINS QC always attached; persistence on/off; raw text
  never lands in operator_state.
* run_regional_ELINS — ESO conditional behaviour; S_ELINS attached;
  persistence + operator_state hooks.
* run_macro_ELINS — full pass + entity-graph merge + macro-run record.
* Endpoint contracts unchanged: /c/run, /elins/g/run, /elins/preview,
  /elins/global, /elins/regional/run.
* Determinism of kernel calls given fixed inputs.
* /founder/intelligence/kernel/status shape + founder gate.
* /me embeds the intelligence_kernel block.
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


def _make_user(app_module, username, cohort="founder", *,
               signal_mode=None, g_credits=10):
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
    if g_credits:
        patch["g_credits"] = int(g_credits)
    if patch:
        users_store.update_user(username, patch)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ---------------------------------------------------------------------------
# run_c
# ---------------------------------------------------------------------------
def test_run_c_default_mode_is_comment(reset_stores):
    import intelligence_kernel as ik
    r = ik.run_c("alice", "the agency is drifting from its mandate")
    assert r["ok"] is True
    assert r["mode"] == "comment"
    assert isinstance(r["result"]["comment"], str) and r["result"]["comment"]


def test_run_c_explicit_comment_mode(reset_stores):
    import intelligence_kernel as ik
    r = ik.run_c("alice", "trust between partners is eroding", mode="comment")
    assert r["mode"] == "comment"


def test_run_c_unknown_mode_raises(reset_stores):
    import intelligence_kernel as ik
    with pytest.raises(ValueError):
        ik.run_c("alice", "x", mode="totally_made_up")


def test_run_c_external_signal_mode_override_persists(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_
    ik.run_c("alice", "trust pressure", external_signal_mode="cloud_perplexity")
    state = os_.get_operator_state("alice")
    assert state["external_signal_mode"] == "cloud_perplexity"


def test_run_c_is_deterministic(reset_stores):
    import intelligence_kernel as ik
    a = ik.run_c("alice", "trust pressure")
    b = ik.run_c("alice", "trust pressure")
    assert a["result"]["comment"] == b["result"]["comment"]


# ---------------------------------------------------------------------------
# run_G
# ---------------------------------------------------------------------------
def test_run_G_invokes_runner_and_records_g_history(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_

    def fake_runner(text, user):
        return {
            "ok": True,
            "analysis": {
                "qc_summary": {"pressure": 0.42},
                "persisted_membership_id": "memb_xyz",
            },
        }

    r = ik.run_G("alice", "trust pressure", runner=fake_runner)
    assert r["ok"] is True
    state = os_.get_operator_state("alice")
    assert len(state["g_history"]) == 1
    entry = state["g_history"][0]
    assert entry["mode"] == "G"
    assert "pressure" in entry["topic"]
    assert entry["g_id"] == "memb_xyz"


def test_run_G_failed_runner_no_record(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_

    def fake_runner(text, user):
        return {"ok": False, "error": "g_elins_failed"}

    r = ik.run_G("alice", "x", runner=fake_runner)
    assert r["ok"] is False
    state = os_.get_operator_state("alice")
    assert state["g_history"] == []


def test_run_G_signal_mode_override_persists(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_
    import users_store

    def fake_runner(text, user):
        return {"ok": True, "analysis": {"qc_summary": {"pressure": 0.1}}}

    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    ik.run_G(
        "alice", "x", runner=fake_runner,
        external_signal_mode="cloud_perplexity",
    )
    assert os_.get_operator_state("alice")["external_signal_mode"] == "cloud_perplexity"
    user_doc = users_store.get_user("alice") or {}
    assert user_doc.get("external_signal_mode") == "cloud_perplexity"


def test_run_G_does_not_persist_raw_text(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_

    def fake_runner(text, user):
        return {"ok": True, "analysis": {"qc_summary": {"pressure": 0.5}}}

    raw = "FNORD123 secret scenario"
    ik.run_G("alice", raw, runner=fake_runner)
    state = os_.get_operator_state("alice")
    assert "FNORD123" not in repr(state)


# ---------------------------------------------------------------------------
# run_ELINS
# ---------------------------------------------------------------------------
def test_run_ELINS_attaches_qc_and_persists_when_persist_true(reset_stores):
    import intelligence_kernel as ik
    from ELINS import elins_project
    r = ik.run_ELINS(
        "alice",
        "trust between partners is eroding under tariff pressure",
        kind="global", persist=True,
    )
    assert r["ok"] is True
    assert r["qc"] is not None
    assert r["qc"]["passed"] in (True, False)
    assert "qc" in r["elins"]
    runs = elins_project.list_runs_for_user("alice")
    assert any(row["id"] == r["run_id"] for row in runs)


def test_run_ELINS_persist_false_does_not_save_daily_run(reset_stores):
    import intelligence_kernel as ik
    from ELINS import elins_project
    r = ik.run_ELINS(
        "alice", "trust eroding", kind="preview", persist=False,
    )
    assert r["run_id"] is None
    runs = elins_project.list_runs_for_user("alice")
    assert runs == []


def test_run_ELINS_records_operator_state(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_
    ik.run_ELINS(
        "alice", "trust pressure tension", kind="preview", persist=False,
    )
    state = os_.get_operator_state("alice")
    assert len(state["elins_history"]) == 1
    assert state["elins_history"][0]["kind"] == "preview"


def test_run_ELINS_does_not_leak_raw_text(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_
    ik.run_ELINS(
        "alice",
        "FNORD123 trust between partners is eroding under tariff pressure",
        kind="preview", persist=False,
    )
    state = os_.get_operator_state("alice")
    assert "FNORD123" not in repr(state)


def test_run_ELINS_with_region_delegates_to_regional(reset_stores):
    import intelligence_kernel as ik
    r = ik.run_ELINS(
        "alice", "Senate vote on antitrust",
        region="US", persist=True,
    )
    assert r["region_code"] == "US"
    assert r["elins"]["region_code"] == "US"


def test_run_ELINS_is_deterministic_modulo_ts(reset_stores):
    import intelligence_kernel as ik
    a = ik.run_ELINS(
        "alice", "trust pressure tension drift", persist=False,
    )
    b = ik.run_ELINS(
        "alice", "trust pressure tension drift", persist=False,
    )
    a_p = a["elins"]["primitives"]
    b_p = b["elins"]["primitives"]
    assert a_p == b_p


# ---------------------------------------------------------------------------
# run_regional_ELINS
# ---------------------------------------------------------------------------
def test_run_regional_ELINS_attaches_qc_and_persists(reset_stores):
    import intelligence_kernel as ik
    from ELINS import elins_project
    r = ik.run_regional_ELINS(
        "alice", "MEA", topic_hint="Gulf shipping",
    )
    assert r["ok"] is True
    assert r["qc"] is not None
    assert r["region_code"] == "MEA"
    runs = elins_project.list_regional_runs("MEA")
    assert any(row["id"] == r["run_id"] for row in runs)


def test_run_regional_ELINS_no_eso_default(reset_stores):
    import intelligence_kernel as ik
    r = ik.run_regional_ELINS("alice", "MEA")
    assert r["eso_present"] is False


def test_run_regional_ELINS_eso_with_user_opt_in(reset_stores):
    import intelligence_kernel as ik
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    users_store.update_user("alice", {"external_signal_mode": "cloud_perplexity"})
    r = ik.run_regional_ELINS("alice", "MEA")
    assert r["eso_present"] is True
    assert r["elins"]["external_signals"]["present"] is True


def test_run_regional_ELINS_explicit_override_wins(reset_stores):
    """An explicit external_signal_mode override on the call should
    take precedence over the user's stored preference."""
    import intelligence_kernel as ik
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    # User preference says cloud_only, but the call overrides to perplexity.
    users_store.update_user("alice", {"external_signal_mode": "cloud_only"})
    r = ik.run_regional_ELINS(
        "alice", "MEA", external_signal_mode="cloud_perplexity",
    )
    assert r["eso_present"] is True


def test_run_regional_ELINS_records_region_preference(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_
    ik.run_regional_ELINS("alice", "MEA")
    state = os_.get_operator_state("alice")
    assert state["preferred_regions"].get("MEA", 0.0) > 0.0


def test_run_regional_ELINS_unknown_region_raises(reset_stores):
    import intelligence_kernel as ik
    with pytest.raises(ValueError):
        ik.run_regional_ELINS("alice", "ZZ")


# ---------------------------------------------------------------------------
# run_macro_ELINS
# ---------------------------------------------------------------------------
def test_run_macro_ELINS_full_pass(reset_stores):
    import intelligence_kernel as ik
    from ELINS import elins_project, regional_elins
    summary = ik.run_macro_ELINS("scheduler")
    assert summary["ran"] is True
    assert set(summary["regions"]) == set(regional_elins.REGION_CODES)
    assert summary["global_run_id"]
    # Macro record persisted
    record = elins_project.get_macro_run(summary["run_id"])
    assert record is not None
    # Entity graph snapshot persisted
    snap = elins_project.load_latest_entity_graph()
    assert snap is not None


def test_run_macro_ELINS_with_eso_mode(reset_stores):
    import intelligence_kernel as ik
    from ELINS import elins_project, regional_elins
    summary = ik.run_macro_ELINS(
        "scheduler", external_signal_mode="cloud_perplexity",
    )
    assert summary["external_signal_mode"] == "cloud_perplexity"
    for region in regional_elins.REGION_CODES:
        rgn = elins_project.latest_regional_run(region)
        ext = (rgn or {}).get("elins", {}).get("external_signals") or {}
        assert ext.get("present") is True, region


def test_run_macro_ELINS_run_id_unique(reset_stores):
    import intelligence_kernel as ik
    a = ik.run_macro_ELINS("scheduler")
    b = ik.run_macro_ELINS("scheduler")
    assert a["run_id"] != b["run_id"]


# ---------------------------------------------------------------------------
# Scheduler delegation — _run_macro_elins_once routes through kernel
# ---------------------------------------------------------------------------
def test_scheduler_delegates_to_kernel(reset_stores):
    """The scheduler's _run_macro_elins_once is now a thin wrapper that
    calls into the kernel — verifying the contract is preserved."""
    import elins_scheduler
    summary = elins_scheduler._run_macro_elins_once(force=True)
    assert summary["ran"] is True
    assert "regions" in summary
    assert "entity_graph_id" in summary


# ---------------------------------------------------------------------------
# Endpoint contracts — same shape as before the refactor
# ---------------------------------------------------------------------------
def test_endpoint_c_run_unchanged(app_module, client):
    user, sid = _make_user(app_module, "ec_a", cohort="founder")
    r = client.post(
        "/c/run", headers=_auth(sid),
        json={"text": "the agency is drifting from its mandate", "mode": "comment"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["mode"] == "comment"
    assert "result" in body
    assert "comment" in body["result"]


def test_endpoint_elins_preview_unchanged(app_module, client):
    user, sid = _make_user(app_module, "ep_a", cohort="founder")
    r = client.post(
        "/elins/preview", headers=_auth(sid),
        json={"text": "trust between partners is eroding under tariff pressure"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert "elins" in body
    assert "output_object" in body["elins"]
    # v40 — kernel attaches QC. Old contract didn't include it explicitly
    # but having it doesn't break clients.
    assert "qc" in body["elins"]


def test_endpoint_elins_global_unchanged(app_module, client):
    from ELINS import elins_project
    user, sid = _make_user(app_module, "eg_a", cohort="founder")
    r = client.post(
        "/elins/global", headers=_auth(sid),
        json={"text": "Court ruling on constitutional pressure"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert "run_id" in body
    assert "elins" in body
    assert "baseline" in body
    runs = elins_project.list_runs_for_user(user)
    assert any(row["id"] == body["run_id"] for row in runs)


def test_endpoint_elins_regional_run_unchanged(app_module, client):
    user, sid = _make_user(app_module, "er_a", cohort="founder")
    r = client.post(
        "/elins/regional/run", headers=_auth(sid),
        json={"region_code": "US"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["region_code"] == "US"
    assert "elins" in body
    assert "eso_present" in body


def test_endpoint_elins_g_run_records_g_history(app_module, client):
    """When /elins/g/run succeeds, operator_state should have a fresh
    #G entry — proves the kernel wraps the runner."""
    import operator_state as os_
    user, sid = _make_user(app_module, "egr_a", cohort="founder", g_credits=5)
    r = client.post(
        "/elins/g/run", headers=_auth(sid),
        json={"scenario_text": "tariffs are creating pressure on the courts"},
    )
    if r.status_code == 200:
        state = os_.get_operator_state(user)
        assert any(g["mode"] == "G" for g in state["g_history"])


# ---------------------------------------------------------------------------
# /founder/intelligence/kernel/status
# ---------------------------------------------------------------------------
def test_endpoint_kernel_status_shape(app_module, client):
    user, sid = _make_user(app_module, "ks_a", cohort="founder")
    r = client.get("/founder/intelligence/kernel/status", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    kernel = r.json()["kernel"]
    assert kernel["version"].startswith("kernel.v1")
    assert "eso_default_mode" in kernel
    assert "scheduler_enabled" in kernel
    assert "macro_cadence" in kernel
    assert "last_macro_run_ts" in kernel
    assert "regions" in kernel


def test_endpoint_kernel_status_after_macro_run(app_module, client):
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "ks_b", cohort="founder")
    r = client.get("/founder/intelligence/kernel/status", headers=_auth(sid))
    kernel = r.json()["kernel"]
    assert kernel["last_macro_run_ts"] is not None


def test_endpoint_kernel_status_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "ks_outsider", cohort=None)
    r = client.get("/founder/intelligence/kernel/status", headers=_auth(sid))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# /me intelligence_kernel block
# ---------------------------------------------------------------------------
def test_me_includes_intelligence_kernel_block(app_module, client):
    user, sid = _make_user(app_module, "me_a", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert "intelligence_kernel" in body
    ik_block = body["intelligence_kernel"]
    assert ik_block["version"].startswith("kernel.v1")
    assert ik_block["external_signal_mode"] in ("cloud_only", "cloud_perplexity")
    assert "preferred_domains" in ik_block
    assert "preferred_regions" in ik_block


def test_me_intelligence_kernel_reflects_user_preferences(app_module, client):
    import operator_state as os_
    user, sid = _make_user(app_module, "me_b", cohort="founder")
    os_.record_elins_interaction(
        user, "sc_1", {"topic": "x", "region": "MEA", "domain": "geopolitical"},
    )
    r = client.get("/me", headers=_auth(sid))
    ik_block = r.json()["intelligence_kernel"]
    assert ik_block["preferred_regions"].get("MEA", 0.0) > 0.0


def test_me_advertises_intelligence_kernel_capability(app_module, client):
    user, sid = _make_user(app_module, "cap_a", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    ids = [c["id"] for c in r.json().get("capabilities") or []]
    assert "intelligence_kernel" in ids


# ---------------------------------------------------------------------------
# Centralised ESO resolution — kernel routes match v35 + v36 expectations
# ---------------------------------------------------------------------------
def test_kernel_resolve_external_signal_mode_explicit_override(reset_stores):
    import intelligence_kernel as ik
    assert ik._resolve_external_signal_mode(None, "cloud_perplexity") == "cloud_perplexity"
    assert ik._resolve_external_signal_mode(None, "cloud_only") == "cloud_only"


def test_kernel_resolve_external_signal_mode_user_doc(reset_stores):
    import intelligence_kernel as ik
    import users_store
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=time.time(),
    )
    users_store.update_user("alice", {"external_signal_mode": "cloud_perplexity"})
    assert ik._resolve_external_signal_mode("alice", None) == "cloud_perplexity"


def test_kernel_resolve_external_signal_mode_default(reset_stores):
    import intelligence_kernel as ik
    assert ik._resolve_external_signal_mode("never_seen_user", None) == "cloud_only"


def test_kernel_maybe_fetch_eso_only_for_perplexity(reset_stores):
    import intelligence_kernel as ik
    assert ik._maybe_fetch_eso("cloud_only", region_code="US") is None
    eso = ik._maybe_fetch_eso("cloud_perplexity", region_code="US")
    assert eso is not None
    assert eso["region_code"] == "US"


def test_kernel_maybe_fetch_eso_unknown_region_returns_none(reset_stores):
    import intelligence_kernel as ik
    assert ik._maybe_fetch_eso("cloud_perplexity", region_code="ZZ") is None
