"""
Tests for v51 — Project layer (projects_vault + ThreadMeta.project_id +
kernel routing + /me/projects endpoints).

Covers:

projects_vault:
* create_project happy path; bad shapes rejected; duplicate rejected
* list_projects empty / multi (newest-first)
* get_project happy + KeyError on missing
* update_project_summary set + clear
* add_thread_to_project idempotent + thread_count bump
* remove_thread_from_project
* list_project_threads in insertion order
* is_thread_in_project edge cases

threads_vault backward compat:
* default ThreadMeta.project_id is None
* create_thread(project_id="X") sets the field
* rename / append / get_thread_meta preserve project_id

model_router aliases:
* "claude" → anthropic:claude-3.7
* exact ids pass through
* unknown / empty returns None

kernel routing:
* run_thread_message with matching project_id uses default_model override
* run_thread_message with project_id mismatch → ValueError
* run_thread_message without project_id falls back to task default
* allowed_models filter falls back to first allowed when override invalid
* kernel_run log carries project_id

Endpoints:
* GET /me/projects empty
* POST /me/projects success + duplicate 400 + bad project_id 400
* GET /me/projects/{id} 404 on miss
* GET /me/threads?project_id=X filters correctly
* POST /me/threads with project_id sets membership + index
* POST /me/threads/{id}/message with project_id routes through default_model
* POST /me/threads/{id}/message with mismatched project_id → 400
* POST /me/threads with unknown project_id → 404
* GET /me/projects/{id}/threads matches list_project_threads
* /me capability advertises projects
* /health version 4.5
"""
from __future__ import annotations

import secrets
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


# ===========================================================================
# projects_vault — core round-trips
# ===========================================================================
def test_create_project_happy(reset_stores):
    import projects_vault as pv
    meta = pv.create_project("alice", {
        "project_id":     "VA_LITIGATION",
        "name":           "VA Litigation",
        "description":    "MSJ Opposition",
        "default_model":  "claude",
        "tags":           ["legal", "va"],
    })
    assert meta["project_id"] == "VA_LITIGATION"
    assert meta["name"] == "VA Litigation"
    assert meta["default_model"] == "claude"
    assert meta["tags"] == ["legal", "va"]
    assert meta["thread_count"] == 0
    assert isinstance(meta["created_at"], int) and meta["created_at"] > 0


def test_create_project_rejects_bad_id(reset_stores):
    import projects_vault as pv
    with pytest.raises(ValueError):
        pv.create_project("alice", {"project_id": "bad.id", "name": "x"})
    with pytest.raises(ValueError):
        pv.create_project("alice", {"project_id": "", "name": "x"})
    with pytest.raises(ValueError):
        pv.create_project("alice", {"project_id": "VALID", "name": ""})


def test_create_project_duplicate_rejected(reset_stores):
    import projects_vault as pv
    pv.create_project("alice", {"project_id": "VA_LITIGATION", "name": "VA"})
    with pytest.raises(ValueError):
        pv.create_project("alice", {"project_id": "VA_LITIGATION", "name": "VA again"})


def test_list_projects_empty(reset_stores):
    import projects_vault as pv
    assert pv.list_projects("alice") == []


def test_list_projects_newest_first(reset_stores):
    import projects_vault as pv
    pv.create_project("alice", {"project_id": "FIRST", "name": "First"})
    time.sleep(0.005)
    pv.create_project("alice", {"project_id": "SECOND", "name": "Second"})
    metas = pv.list_projects("alice")
    assert [m["project_id"] for m in metas] == ["SECOND", "FIRST"]


def test_get_project_missing_raises_key_error(reset_stores):
    import projects_vault as pv
    with pytest.raises(KeyError):
        pv.get_project("alice", "NOPE")


def test_update_project_summary_set_and_clear(reset_stores):
    import projects_vault as pv
    pv.create_project("alice", {"project_id": "P1", "name": "P1"})
    out = pv.update_project_summary("alice", "P1", "we drafted the brief", 12345)
    assert out["summary"] == "we drafted the brief"
    assert out["summary_ts_ms"] == 12345
    cleared = pv.update_project_summary("alice", "P1", None)
    assert cleared["summary"] is None
    assert cleared["summary_ts_ms"] is None


def test_add_thread_to_project_idempotent_and_bumps_count(reset_stores):
    import projects_vault as pv
    pv.create_project("alice", {"project_id": "P1", "name": "P1"})
    pv.add_thread_to_project("alice", "P1", "thr_1")
    pv.add_thread_to_project("alice", "P1", "thr_2")
    pv.add_thread_to_project("alice", "P1", "thr_1")  # dup
    assert pv.list_project_threads("alice", "P1") == ["thr_1", "thr_2"]
    assert pv.get_project("alice", "P1")["thread_count"] == 2


def test_remove_thread_from_project(reset_stores):
    import projects_vault as pv
    pv.create_project("alice", {"project_id": "P1", "name": "P1"})
    pv.add_thread_to_project("alice", "P1", "thr_1")
    pv.add_thread_to_project("alice", "P1", "thr_2")
    pv.remove_thread_from_project("alice", "P1", "thr_1")
    assert pv.list_project_threads("alice", "P1") == ["thr_2"]
    pv.remove_thread_from_project("alice", "P1", "thr_99")  # idempotent
    assert pv.get_project("alice", "P1")["thread_count"] == 1


def test_is_thread_in_project_edges(reset_stores):
    import projects_vault as pv
    pv.create_project("alice", {"project_id": "P1", "name": "P1"})
    pv.add_thread_to_project("alice", "P1", "thr_a")
    assert pv.is_thread_in_project("alice", "P1", "thr_a") is True
    assert pv.is_thread_in_project("alice", "P1", "thr_b") is False
    assert pv.is_thread_in_project("alice", "NOPE", "thr_a") is False


def test_delete_project_idempotent(reset_stores):
    import projects_vault as pv
    pv.create_project("alice", {"project_id": "P1", "name": "P1"})
    pv.delete_project("alice", "P1")
    pv.delete_project("alice", "P1")  # no raise
    assert pv.list_projects("alice") == []


# ===========================================================================
# threads_vault — project_id field
# ===========================================================================
def test_thread_meta_default_project_id_is_none(reset_stores):
    """Backward compat: existing v47/v50 callers don't pass project_id;
    threads start with project_id=None."""
    import threads_vault as tv
    meta = tv.create_thread("alice", "x")
    assert meta["project_id"] is None


def test_thread_meta_create_with_project_id(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", "x", project_id="VA_LITIGATION")
    assert meta["project_id"] == "VA_LITIGATION"


def test_thread_meta_rename_preserves_project_id(reset_stores):
    """Renaming must not drop project_id (load-bearing for the
    /me/threads?project_id filter)."""
    import threads_vault as tv
    meta = tv.create_thread("alice", "old", project_id="VA_LITIGATION")
    out = tv.rename_thread("alice", meta["thread_id"], "new")
    assert out["project_id"] == "VA_LITIGATION"


def test_thread_meta_append_preserves_project_id(reset_stores):
    import threads_vault as tv
    meta = tv.create_thread("alice", "x", project_id="VA_LITIGATION")
    after, _ = tv.append_message(
        "alice", meta["thread_id"],
        {"role": "user", "content": "hi"},
    )
    assert after["project_id"] == "VA_LITIGATION"


# ===========================================================================
# model_router — alias resolution
# ===========================================================================
def test_resolve_model_alias_known_aliases(reset_stores):
    import model_router as mr
    assert mr.resolve_model_alias("claude") == "anthropic:claude-3.7"
    assert mr.resolve_model_alias("CLAUDE") == "anthropic:claude-3.7"
    assert mr.resolve_model_alias("gpt") == "openai:gpt-4o"
    assert mr.resolve_model_alias("gemini") == "google:gemini-2.0-flash"
    assert mr.resolve_model_alias("local") == "local:llama3.1"


def test_resolve_model_alias_canonical_pass_through(reset_stores):
    import model_router as mr
    assert mr.resolve_model_alias("anthropic:claude-3.7") == "anthropic:claude-3.7"


def test_resolve_model_alias_unknown_returns_none(reset_stores):
    import model_router as mr
    assert mr.resolve_model_alias("not_a_model") is None
    assert mr.resolve_model_alias("") is None
    assert mr.resolve_model_alias(None) is None


# ===========================================================================
# Kernel routing — project_id override
# ===========================================================================
def test_kernel_uses_project_default_model(reset_stores):
    import intelligence_kernel as ik
    import projects_vault as pv
    import threads_vault as tv
    pv.create_project("alice", {
        "project_id": "VA_LITIGATION", "name": "VA",
        "default_model": "openai:gpt-4o",   # override the thread default
    })
    m = tv.create_thread("alice", "T", project_id="VA_LITIGATION")
    pv.add_thread_to_project("alice", "VA_LITIGATION", m["thread_id"])
    out = ik.run_thread_message(
        "alice", m["thread_id"], "draft it",
        project_id="VA_LITIGATION",
    )
    assert out["model_id"] == "openai:gpt-4o"


def test_kernel_resolves_alias_in_project_default_model(reset_stores):
    """``"claude"`` in the project meta resolves to anthropic:claude-3.7."""
    import intelligence_kernel as ik
    import projects_vault as pv
    import threads_vault as tv
    pv.create_project("alice", {
        "project_id": "VA_LITIGATION", "name": "VA",
        "default_model": "claude",
    })
    m = tv.create_thread("alice", "T", project_id="VA_LITIGATION")
    out = ik.run_thread_message(
        "alice", m["thread_id"], "x", project_id="VA_LITIGATION",
    )
    assert out["model_id"] == "anthropic:claude-3.7"


def test_kernel_project_id_mismatch_raises(reset_stores):
    import intelligence_kernel as ik
    import projects_vault as pv
    import threads_vault as tv
    pv.create_project("alice", {"project_id": "VA", "name": "VA"})
    pv.create_project("alice", {"project_id": "OTHER", "name": "Other"})
    m = tv.create_thread("alice", "T", project_id="VA")
    with pytest.raises(ValueError):
        ik.run_thread_message(
            "alice", m["thread_id"], "x", project_id="OTHER",
        )


def test_kernel_no_project_id_falls_back_to_task_default(reset_stores):
    import intelligence_kernel as ik
    import model_router as mr
    import threads_vault as tv
    m = tv.create_thread("alice", "T")   # no project
    out = ik.run_thread_message("alice", m["thread_id"], "x")
    assert out["model_id"] == mr.TASK_DEFAULTS["thread"]


def test_kernel_allowed_models_constrains_choice(reset_stores):
    """If project's allowed_models doesn't include the chosen model,
    routing falls back to the first allowed model."""
    import intelligence_kernel as ik
    import projects_vault as pv
    import threads_vault as tv
    pv.create_project("alice", {
        "project_id": "P1", "name": "P1",
        "default_model": None,
        "allowed_models": ["openai:gpt-4o"],   # task default isn't in here
    })
    m = tv.create_thread("alice", "T", project_id="P1")
    out = ik.run_thread_message("alice", m["thread_id"], "x", project_id="P1")
    assert out["model_id"] == "openai:gpt-4o"


def test_kernel_log_carries_project_id(reset_stores, caplog):
    import json
    import intelligence_kernel as ik
    import projects_vault as pv
    import threads_vault as tv
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    pv.create_project("alice", {"project_id": "VA", "name": "VA"})
    m = tv.create_thread("alice", "T", project_id="VA")
    ik.run_thread_message("alice", m["thread_id"], "x", project_id="VA")
    found = []
    for rec in caplog.records:
        if rec.message.startswith("kernel_run "):
            payload = json.loads(rec.message.split(" ", 1)[1])
            if payload.get("kind") == "run_thread_message":
                found.append(payload)
    assert any(p.get("meta", {}).get("project_id") == "VA" for p in found)


# ===========================================================================
# Endpoints
# ===========================================================================
def test_endpoint_list_projects_empty(app_module, client):
    user, sid = _make_user(app_module, "p_a", cohort="founder")
    r = client.get("/me/projects", headers=_auth(sid))
    assert r.status_code == 200
    assert r.json()["projects"] == []


def test_endpoint_create_project_round_trip(app_module, client):
    user, sid = _make_user(app_module, "p_b", cohort="founder")
    r = client.post(
        "/me/projects", headers=_auth(sid),
        json={
            "project_id":    "VA_LITIGATION",
            "name":          "VA Litigation",
            "description":   "MSJ Opposition",
            "default_model": "claude",
            "tags":          ["legal", "va"],
        },
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["project_id"] == "VA_LITIGATION"
    assert body["name"] == "VA Litigation"
    assert body["default_model"] == "claude"
    assert body["tags"] == ["legal", "va"]

    # Round-trip via list + get.
    listing = client.get("/me/projects", headers=_auth(sid)).json()
    assert len(listing["projects"]) == 1
    detail = client.get("/me/projects/VA_LITIGATION", headers=_auth(sid)).json()
    assert detail["project_id"] == "VA_LITIGATION"


def test_endpoint_create_project_duplicate_400(app_module, client):
    user, sid = _make_user(app_module, "p_c", cohort="founder")
    body = {"project_id": "VA", "name": "VA"}
    client.post("/me/projects", headers=_auth(sid), json=body)
    r2 = client.post("/me/projects", headers=_auth(sid), json=body)
    assert r2.status_code == 400


def test_endpoint_create_project_bad_id_400(app_module, client):
    user, sid = _make_user(app_module, "p_d", cohort="founder")
    r = client.post(
        "/me/projects", headers=_auth(sid),
        json={"project_id": "bad.id", "name": "x"},
    )
    assert r.status_code == 400


def test_endpoint_get_project_404_on_missing(app_module, client):
    user, sid = _make_user(app_module, "p_e", cohort="founder")
    r = client.get("/me/projects/NOPE", headers=_auth(sid))
    assert r.status_code == 404


def test_endpoint_threads_filter_by_project_id(app_module, client):
    """GET /me/threads?project_id=X returns only threads tagged with X."""
    user, sid = _make_user(app_module, "p_f", cohort="founder")
    client.post(
        "/me/projects", headers=_auth(sid),
        json={"project_id": "VA", "name": "VA"},
    )
    client.post(
        "/me/projects", headers=_auth(sid),
        json={"project_id": "OTHER", "name": "Other"},
    )
    # Create three threads: 2 in VA, 1 in OTHER, 1 unassigned.
    client.post("/me/threads", headers=_auth(sid),
                json={"title": "A", "project_id": "VA"})
    client.post("/me/threads", headers=_auth(sid),
                json={"title": "B", "project_id": "VA"})
    client.post("/me/threads", headers=_auth(sid),
                json={"title": "C", "project_id": "OTHER"})
    client.post("/me/threads", headers=_auth(sid), json={"title": "D"})

    # Filter VA → 2 threads
    r_va = client.get("/me/threads?project_id=VA", headers=_auth(sid))
    titles = sorted(t["title"] for t in r_va.json()["threads"])
    assert titles == ["A", "B"]

    # Filter OTHER → 1 thread
    r_other = client.get("/me/threads?project_id=OTHER", headers=_auth(sid))
    assert [t["title"] for t in r_other.json()["threads"]] == ["C"]

    # No filter → all 4 threads
    r_all = client.get("/me/threads", headers=_auth(sid))
    assert len(r_all.json()["threads"]) == 4


def test_endpoint_create_thread_with_project_id(app_module, client):
    user, sid = _make_user(app_module, "p_g", cohort="founder")
    client.post(
        "/me/projects", headers=_auth(sid),
        json={"project_id": "VA", "name": "VA"},
    )
    r = client.post(
        "/me/threads", headers=_auth(sid),
        json={"title": "MSJ", "project_id": "VA"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["project_id"] == "VA"
    # The project's threads index now contains the new thread.
    listing = client.get(
        "/me/projects/VA/threads", headers=_auth(sid),
    ).json()
    assert len(listing["threads"]) == 1
    assert listing["threads"][0]["thread_id"] == body["thread_id"]
    # Project meta thread_count bumped.
    proj = client.get("/me/projects/VA", headers=_auth(sid)).json()
    assert proj["thread_count"] == 1


def test_endpoint_create_thread_with_unknown_project_404(app_module, client):
    user, sid = _make_user(app_module, "p_h", cohort="founder")
    r = client.post(
        "/me/threads", headers=_auth(sid),
        json={"title": "x", "project_id": "NOPE"},
    )
    assert r.status_code == 404


def test_endpoint_post_message_with_project_id_routes_correctly(app_module, client):
    """A message posted with project_id=VA into a VA-tagged thread
    routes through the project's default_model."""
    user, sid = _make_user(app_module, "p_i", cohort="founder")
    client.post(
        "/me/projects", headers=_auth(sid),
        json={"project_id": "VA", "name": "VA", "default_model": "claude"},
    )
    cr = client.post(
        "/me/threads", headers=_auth(sid),
        json={"title": "T", "project_id": "VA"},
    )
    tid = cr.json()["thread_id"]
    r = client.post(
        f"/me/threads/{tid}/message", headers=_auth(sid),
        json={"content": "draft", "project_id": "VA"},
    )
    assert r.status_code == 200
    assert r.json()["model_id"] == "anthropic:claude-3.7"


def test_endpoint_post_message_project_id_mismatch_400(app_module, client):
    user, sid = _make_user(app_module, "p_j", cohort="founder")
    client.post("/me/projects", headers=_auth(sid),
                json={"project_id": "VA", "name": "VA"})
    client.post("/me/projects", headers=_auth(sid),
                json={"project_id": "OTHER", "name": "Other"})
    cr = client.post(
        "/me/threads", headers=_auth(sid),
        json={"title": "T", "project_id": "VA"},
    )
    tid = cr.json()["thread_id"]
    # Post message claiming a different project_id than the thread's stored one.
    r = client.post(
        f"/me/threads/{tid}/message", headers=_auth(sid),
        json={"content": "x", "project_id": "OTHER"},
    )
    assert r.status_code == 400


def test_endpoint_post_message_without_project_id_works(app_module, client):
    """Backward compat: existing v47/v50 callers don't pass project_id."""
    user, sid = _make_user(app_module, "p_k", cohort="founder")
    cr = client.post("/me/threads", headers=_auth(sid), json={"title": "T"})
    tid = cr.json()["thread_id"]
    r = client.post(
        f"/me/threads/{tid}/message", headers=_auth(sid),
        json={"content": "hello"},
    )
    assert r.status_code == 200
    assert r.json()["meta"]["project_id"] is None


def test_endpoint_project_threads_index_consistent(app_module, client):
    """GET /me/projects/{id}/threads returns the same set as
    GET /me/threads?project_id={id}."""
    user, sid = _make_user(app_module, "p_l", cohort="founder")
    client.post("/me/projects", headers=_auth(sid),
                json={"project_id": "VA", "name": "VA"})
    for title in ("A", "B", "C"):
        client.post("/me/threads", headers=_auth(sid),
                    json={"title": title, "project_id": "VA"})
    a = client.get("/me/projects/VA/threads", headers=_auth(sid)).json()
    b = client.get("/me/threads?project_id=VA", headers=_auth(sid)).json()
    a_ids = sorted(t["thread_id"] for t in a["threads"])
    b_ids = sorted(t["thread_id"] for t in b["threads"])
    assert a_ids == b_ids
    assert len(a_ids) == 3


def test_endpoint_me_capability_advertises_projects(app_module, client):
    user, sid = _make_user(app_module, "p_cap", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    ids = [c["id"] for c in r.json().get("capabilities") or []]
    assert "projects" in ids


def test_health_version_4_5(app_module, client):
    r = client.get("/health")
    # v52 → 4.6, v53 → 4.7, v54 → 4.8, v60 → 4.9, v67 → 4.10, v68 → 4.11,
    # v69 → 4.12, v70 → 4.13, v71 → 4.14, v72 → 4.15, v73 → 4.16,
    # v74 → 4.17. The v51 contract didn't pin the literal, so we track
    # the current minor head.
    assert r.json()["version"] == "4.23"


# ===========================================================================
# Migration is no-op
# ===========================================================================
def test_migration_is_no_op(app_module, client):
    """First request for a fresh user returns empty projects list +
    no auto-created entries."""
    user, sid = _make_user(app_module, "p_mig", cohort="founder")
    # Hit /me + /me/projects + /me/threads.
    client.get("/me", headers=_auth(sid))
    pr = client.get("/me/projects", headers=_auth(sid)).json()
    tr = client.get("/me/threads", headers=_auth(sid)).json()
    assert pr["projects"] == []
    assert tr["threads"] == []


def test_existing_threads_without_project_id_still_work(reset_stores):
    """Round-trip a v47/v50-shaped thread (no project_id field). It
    should load with project_id=None and continue to function."""
    import threads_vault as tv
    m = tv.create_thread("alice", "legacy")
    assert m["project_id"] is None
    # Append + get_thread + rename — none of these should choke on the
    # missing field.
    tv.append_message("alice", m["thread_id"], {"role": "user", "content": "x"})
    meta, msgs = tv.get_thread("alice", m["thread_id"])
    assert meta["project_id"] is None
    assert len(msgs) == 1
    renamed = tv.rename_thread("alice", m["thread_id"], "renamed")
    assert renamed["project_id"] is None
