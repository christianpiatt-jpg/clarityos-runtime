"""
Tests for v43 — UX polish + founder analytics surfaces.

Covers:
* founder_analytics.get_founder_analytics_summary:
  - Empty state (no users, no runs, no macro passes).
  - Aggregates synthetic users + memberships + operator_state +
    macro runs deterministically.
  - ESO usage rate computed as
    (# macro runs with external_signal_mode == "cloud_perplexity")
    / (total macro runs in 7d window).
  - Active 7d / 30d windows respect operator_state.last_active_ts.
* /founder/analytics/summary:
  - Founder-only gate.
  - Shape matches the spec.
* /me capability list advertises ``founder_analytics``.
* Dashboard empty-state contract (no macro / no entity graph) is
  preserved — the snapshot endpoint returns the right `available`
  flags even when the underlying stores are empty.
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
               billing_state=None, last_active=None):
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
    if billing_state is not None:
        patch["billing_state"] = billing_state
    if patch:
        users_store.update_user(username, patch)
    if last_active is not None:
        import operator_state
        # Bypass the public API to set a controlled last_active_ts.
        state = operator_state.get_operator_state(username)
        state["last_active_ts"] = float(last_active)
        operator_state._save(username, state)
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


# ---------------------------------------------------------------------------
# get_founder_analytics_summary — pure module
# ---------------------------------------------------------------------------
def test_summary_empty_state(reset_stores):
    import founder_analytics
    summary = founder_analytics.get_founder_analytics_summary(now_ts=1_000_000.0)
    assert summary["users"] == {"total": 0, "active_7d": 0, "active_30d": 0}
    assert summary["billing"]["active_subscriptions"] == 0
    assert summary["billing"]["past_due"] == 0
    assert summary["billing"]["canceled"] == 0
    # Mode reflects current env, which is "disabled" in the default test env.
    assert summary["billing"]["mode"] in ("test", "live", "disabled")
    assert summary["intelligence"]["macro_runs_7d"] == 0
    assert summary["intelligence"]["eso_usage_rate_7d"] == 0.0


def test_summary_counts_users_total(reset_stores):
    import founder_analytics, users_store, time as _t
    for name in ("a", "b", "c"):
        users_store.create_user(
            username=name, password_hash=b"x", salt="",
            tier="free", created_at=_t.time(),
        )
    summary = founder_analytics.get_founder_analytics_summary()
    assert summary["users"]["total"] == 3


def test_summary_active_windows(reset_stores):
    import founder_analytics, users_store, operator_state, time as _t
    now = 1_000_000.0
    users_store.create_user(
        username="recent", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    users_store.create_user(
        username="month_ago", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    users_store.create_user(
        username="ancient", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    # v46 — operator_state lives in memory_vault. Write last_active_ts
    # directly so the analytics aggregator sees the fixture timestamp.
    import memory_vault
    operator_state.get_operator_state("recent")        # init
    memory_vault.vault_put("recent", "operator_state.last_active_ts", now - 3600)
    operator_state.get_operator_state("month_ago")
    memory_vault.vault_put("month_ago", "operator_state.last_active_ts", now - 20 * 86400)
    operator_state.get_operator_state("ancient")
    memory_vault.vault_put("ancient", "operator_state.last_active_ts", now - 60 * 86400)

    summary = founder_analytics.get_founder_analytics_summary(now_ts=now)
    assert summary["users"]["total"] == 3
    assert summary["users"]["active_7d"] == 1
    assert summary["users"]["active_30d"] == 2


def test_summary_billing_aggregation(reset_stores):
    import founder_analytics, users_store, time as _t
    users_store.create_user(
        username="active1", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    users_store.create_user(
        username="active2", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    users_store.create_user(
        username="late", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    users_store.create_user(
        username="canceled", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    users_store.update_user("active1", {"billing_state": "active"})
    users_store.update_user("active2", {"billing_state": "active"})
    users_store.update_user("late", {"billing_state": "past_due"})
    users_store.update_user("canceled", {"billing_state": "cancelled"})
    summary = founder_analytics.get_founder_analytics_summary()
    assert summary["billing"]["active_subscriptions"] == 2
    assert summary["billing"]["past_due"] == 1
    assert summary["billing"]["canceled"] == 1


def test_summary_intelligence_runs_in_7d_window(reset_stores):
    import founder_analytics, users_store, operator_state, time as _t
    now = 1_000_000.0
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    # v46 — populate history by hand-writing each entry into the vault
    # via the migration helper so we control timestamps for the window
    # assertions below.
    operator_state.migrate_operator_state_to_vault("alice", {
        "elins_history": [
            {"ts": now - 3600, "elins_id": "sc_1", "topic": "t",
             "region": "US", "kind": "regional"},
            {"ts": now - 2 * 86400, "elins_id": "sc_2", "topic": "t",
             "region": "EU", "kind": "regional"},
            {"ts": now - 14 * 86400, "elins_id": "sc_3", "topic": "old",
             "region": None, "kind": "preview"},
        ],
        "g_history": [
            {"ts": now - 3600, "g_id": "g_1", "mode": "G", "topic": "x"},
            {"ts": now - 30 * 86400, "g_id": "g_2", "mode": "G", "topic": "old"},
        ],
    })
    summary = founder_analytics.get_founder_analytics_summary(now_ts=now)
    assert summary["intelligence"]["elins_runs_7d"] == 2
    assert summary["intelligence"]["g_runs_7d"] == 1


def test_summary_eso_usage_rate(reset_stores):
    import founder_analytics
    from ELINS import elins_project
    now = 1_000_000.0
    # 4 macro runs in 7d: 3 with cloud_perplexity, 1 with cloud_only → 0.75
    elins_project.record_macro_run(
        ts=now - 3600, run_id="m_1", regions=["US"],
        global_run_ref={}, external_signal_mode="cloud_perplexity",
    )
    elins_project.record_macro_run(
        ts=now - 7200, run_id="m_2", regions=["EU"],
        global_run_ref={}, external_signal_mode="cloud_perplexity",
    )
    elins_project.record_macro_run(
        ts=now - 86400, run_id="m_3", regions=["MEA"],
        global_run_ref={}, external_signal_mode="cloud_perplexity",
    )
    elins_project.record_macro_run(
        ts=now - 2 * 86400, run_id="m_4", regions=["APAC"],
        global_run_ref={}, external_signal_mode="cloud_only",
    )
    # Older than 7d — must be excluded.
    elins_project.record_macro_run(
        ts=now - 14 * 86400, run_id="m_5", regions=["Tech"],
        global_run_ref={}, external_signal_mode="cloud_perplexity",
    )
    summary = founder_analytics.get_founder_analytics_summary(now_ts=now)
    assert summary["intelligence"]["macro_runs_7d"] == 4
    assert summary["intelligence"]["eso_usage_rate_7d"] == 0.75


def test_summary_eso_rate_zero_when_no_runs(reset_stores):
    import founder_analytics
    summary = founder_analytics.get_founder_analytics_summary()
    assert summary["intelligence"]["macro_runs_7d"] == 0
    assert summary["intelligence"]["eso_usage_rate_7d"] == 0.0


def test_summary_is_deterministic_for_fixed_state(reset_stores):
    import founder_analytics, users_store, time as _t
    users_store.create_user(
        username="alice", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    users_store.update_user("alice", {"billing_state": "active"})
    a = founder_analytics.get_founder_analytics_summary(now_ts=1_000_000.0)
    b = founder_analytics.get_founder_analytics_summary(now_ts=1_000_000.0)
    a.pop("ts", None); b.pop("ts", None)
    assert a == b


def test_summary_shape_matches_spec(reset_stores):
    import founder_analytics
    summary = founder_analytics.get_founder_analytics_summary()
    assert {"users", "billing", "intelligence", "ts", "version"} <= set(summary.keys())
    assert {"total", "active_7d", "active_30d"} <= set(summary["users"].keys())
    assert {"active_subscriptions", "past_due", "canceled", "mode"} <= set(summary["billing"].keys())
    assert {"elins_runs_7d", "g_runs_7d", "macro_runs_7d", "eso_usage_rate_7d"} <= set(summary["intelligence"].keys())


# ---------------------------------------------------------------------------
# /founder/analytics/summary
# ---------------------------------------------------------------------------
def test_endpoint_analytics_summary_shape(app_module, client):
    user, sid = _make_user(app_module, "fa_a", cohort="founder")
    r = client.get("/founder/analytics/summary", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert "summary" in body
    s = body["summary"]
    assert "users" in s and "billing" in s and "intelligence" in s
    assert s["users"]["total"] >= 1   # at least the requesting founder
    assert s["billing"]["mode"] in ("test", "live", "disabled")


def test_endpoint_analytics_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "fa_outsider", cohort=None)
    r = client.get("/founder/analytics/summary", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_analytics_reflects_runtime_state(app_module, client):
    """End-to-end: kick a macro pass with cloud_perplexity ESO, then
    verify the analytics endpoint reports macro_runs_7d >= 1 and
    eso_usage_rate_7d == 1.0."""
    import elins_scheduler, elins_scheduler_config
    elins_scheduler_config.set_config({"external_signal_mode": "cloud_perplexity"})
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "fa_b", cohort="founder")
    r = client.get("/founder/analytics/summary", headers=_auth(sid))
    body = r.json()
    intel = body["summary"]["intelligence"]
    assert intel["macro_runs_7d"] >= 1
    assert intel["eso_usage_rate_7d"] == 1.0


# ---------------------------------------------------------------------------
# /me capability advertises founder_analytics
# ---------------------------------------------------------------------------
def test_me_advertises_founder_analytics_capability(app_module, client):
    user, sid = _make_user(app_module, "cap_a", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    ids = [c["id"] for c in r.json().get("capabilities") or []]
    assert "founder_analytics" in ids


# ---------------------------------------------------------------------------
# Dashboard empty-state contract (UX polish)
# ---------------------------------------------------------------------------
def test_dashboard_empty_state_contract(app_module, client):
    """A fresh user with no runs sees:
       - global available=False (or fallback to scheduler — also fine)
       - regional all available=False
       - macro last_run_id=None
       - entity_graph available=False
    The web/phone dashboard skeletons + empty-state cards rely on
    these flags being set correctly."""
    user, sid = _make_user(app_module, "ds_a", cohort="founder")
    r = client.get("/elins/dashboard", headers=_auth(sid))
    assert r.status_code == 200
    snap = r.json()["snapshot"]
    assert snap["macro"]["last_run_id"] is None
    assert snap["entity_graph"]["available"] is False
    for region in ("US", "EU", "MEA", "APAC", "Markets", "Tech"):
        assert snap["regional"][region]["available"] is False


def test_dashboard_after_macro_pass_has_macro_section(app_module, client):
    """Run the macro pass once; macro + entity sections must populate."""
    import elins_scheduler
    elins_scheduler._run_macro_elins_once(force=True)
    user, sid = _make_user(app_module, "ds_b", cohort="founder")
    r = client.get("/elins/dashboard", headers=_auth(sid))
    snap = r.json()["snapshot"]
    assert snap["macro"]["last_run_id"] is not None
    # Entity graph may or may not have entries if ESO is off and the
    # global scaffold had no lexical hits — but the snapshot's
    # available flag should still be set correctly.
    assert "available" in snap["entity_graph"]


# ---------------------------------------------------------------------------
# users_store.list_all_usernames
# ---------------------------------------------------------------------------
def test_list_all_usernames_round_trip(reset_stores):
    import users_store, time as _t
    assert users_store.list_all_usernames() == []
    users_store.create_user(
        username="alpha", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    users_store.create_user(
        username="beta", password_hash=b"x", salt="",
        tier="free", created_at=_t.time(),
    )
    names = sorted(users_store.list_all_usernames())
    assert names == ["alpha", "beta"]
