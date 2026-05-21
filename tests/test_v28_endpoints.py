"""
Endpoint tests for v28 surface + distribution layer + v29 hardening hooks.

Strategy:
* Force CLARITYOS_BACKEND=memory and use FastAPI's TestClient.
* Stub the embedder (dewey_pipeline.embed_text_cached / embed_object) so tests
  don't hit Vertex AI.
* Build a Cohort 1 (founder) user via the same code path as register/_create_user
  and inject a session via sessions_store directly to keep auth setup tiny.
"""
from __future__ import annotations

import time

import pytest
from conftest import TestClient


@pytest.fixture
def stub_embedder(monkeypatch):
    """Replace the real embedder with a deterministic 8-dim vector so #G runs
    don't depend on Vertex AI. Returns None for empty text (mirrors prod
    behavior when the embedder fails)."""
    import dewey_pipeline

    def fake_embed(text):
        if not text or not str(text).strip():
            return None
        # Stable per-input — short hash mod 100 / 100.0 across 8 dims.
        h = abs(hash(str(text)))
        return [((h >> (i * 4)) & 0xFF) / 255.0 for i in range(8)]

    monkeypatch.setattr(dewey_pipeline, "embed_text_cached", fake_embed)
    monkeypatch.setattr(dewey_pipeline, "embed_text", lambda t: fake_embed(t) or [])
    monkeypatch.setattr(dewey_pipeline, "embed_object", lambda o: fake_embed(str(o)) or [0.0] * 8)
    yield


@pytest.fixture
def app_module(reset_stores, stub_embedder):
    """Reload-like access to the FastAPI app (already imported but stores are
    reset by the reset_stores fixture). Returns the module so tests can poke
    constants + helpers."""
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _make_user(app_module, username="alice", cohort="founder"):
    """Create a user with the given cohort and return a session dict that
    matches what require_session would yield. Bypasses the invite/billing
    flow — tests target post-signup state."""
    import users_store
    import sessions_store
    import bcrypt

    import secrets
    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
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
# Health + flags
# ---------------------------------------------------------------------------
def test_health_version(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # Tracks current minor head: v54 → 4.8, v60 → 4.9, v67 → 4.10,
    # v68 → 4.11, v69 → 4.12, v70 → 4.13, v71 → 4.14, v72 → 4.15,
    # v73 → 4.16, v74 → 4.17. The v28 contract never pinned the
    # literal; this assertion bumps with each app.py version.
    assert body["version"] == "4.23"


def test_v29_flags_returns_user_view(app_module, client):
    user, sid = _make_user(app_module, "flagsuser", cohort="founder")
    r = client.get("/v29/flags", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    # Founders get v28_surfaces enabled by startup bootstrap.
    assert body["flags"]["v28_surfaces"] is True


def test_v29_flags_default_off_for_unscoped_user(app_module, client):
    user, sid = _make_user(app_module, "lurker", cohort=None)
    r = client.get("/v29/flags", headers=_auth(sid))
    assert r.status_code == 200
    assert r.json()["flags"]["v28_surfaces"] is False


# ---------------------------------------------------------------------------
# /elins/g/run
# ---------------------------------------------------------------------------
def test_elins_g_run_happy_path(app_module, client):
    user, sid = _make_user(app_module, "ginny", cohort="founder")
    # v30 — founders have the g_credits gate on; buy a pack first so the
    # #G run has a credit to consume.
    client.post("/membership/g/buy_pack_20", headers=_auth(sid))
    r = client.post(
        "/elins/g/run",
        headers=_auth(sid),
        json={"scenario_text": "us-china trade tensions and energy supply"},
    )
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["ok"] is True
    a = body["analysis"]
    assert "neighborhoods" in a
    assert "qc_summary" in a
    assert "universal_physics" in a
    assert isinstance(a["last_updated_ts"], (int, float))
    # v30 — credit was consumed.
    assert body["g_credits_remaining"] == 19


def test_elins_g_run_empty_scenario_rejected(app_module, client):
    user, sid = _make_user(app_module, "gina", cohort="founder")
    r = client.post(
        "/elins/g/run", headers=_auth(sid), json={"scenario_text": "   "},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert body["error"] in {"empty_field", "missing_field"}


def test_elins_g_run_oversize_rejected(app_module, client):
    user, sid = _make_user(app_module, "gigi", cohort="founder")
    payload = {"scenario_text": "x" * (app_module.SCENARIO_MAX_LEN + 100)}
    r = client.post("/elins/g/run", headers=_auth(sid), json=payload)
    assert r.status_code == 400
    assert r.json()["error"] == "field_too_long"


def test_elins_g_run_blocked_when_flag_off(app_module, client):
    user, sid = _make_user(app_module, "guest", cohort=None)
    r = client.post(
        "/elins/g/run", headers=_auth(sid),
        json={"scenario_text": "anything"},
    )
    assert r.status_code == 403
    assert r.json()["error"] == "feature_disabled"


# ---------------------------------------------------------------------------
# /elins/daily — queue → scheduler → delivery cycle
# ---------------------------------------------------------------------------
def test_elins_daily_queue_then_scheduler_delivers(app_module, client):
    import elins_distribution_store

    user, sid = _make_user(app_module, "danny", cohort="founder")
    r = client.post(
        "/elins/daily/queue",
        headers=_auth(sid),
        json={"scenario_text": "a daily scenario"},
    )
    assert r.status_code == 200, r.json()
    queue_body = r.json()
    assert queue_body["ok"] is True
    rid = queue_body["report_id"]
    sched = queue_body["scheduled_for_ts"]
    assert sched > time.time()

    # Drive the scheduler past the scheduled time directly (no sleeping).
    summary = app_module._scheduler_one_pass(now_ts=sched + 1)
    assert summary["delivered"] == 1

    # Queue cleared, delivered list populated.
    feed_r = client.get("/elins/daily/feed", headers=_auth(sid))
    assert feed_r.status_code == 200
    feed = feed_r.json()
    assert feed["count"] == 1
    delivered = feed["delivered"][0]
    assert delivered["report_id"] == rid
    # Scenario id is a hash, never the original text.
    assert delivered["scenario_id"].startswith("sc_")
    assert "scenario_text" not in delivered


def test_elins_daily_queue_empty_rejected(app_module, client):
    user, sid = _make_user(app_module, "denny", cohort="founder")
    r = client.post(
        "/elins/daily/queue", headers=_auth(sid),
        json={"scenario_text": ""},
    )
    assert r.status_code == 400


def test_elins_daily_queue_bad_hour_rejected(app_module, client):
    user, sid = _make_user(app_module, "drake", cohort="founder")
    r = client.post(
        "/elins/daily/queue", headers=_auth(sid),
        json={"scenario_text": "x", "local_hour": 99},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "out_of_range"


# ---------------------------------------------------------------------------
# /mesh/sync — oversize + LRU
# ---------------------------------------------------------------------------
def test_mesh_sync_happy(app_module, client):
    user, sid = _make_user(app_module, "marvin", cohort="founder")
    r = client.post(
        "/mesh/sync", headers=_auth(sid),
        json={"device_id": "dev-1", "metadata": {"events_count": 7}},
    )
    assert r.status_code == 200, r.json()
    assert r.json()["device"]["last_seen_ts"] > 0


def test_mesh_sync_oversize_rejected(app_module, client):
    user, sid = _make_user(app_module, "morgan", cohort="founder")
    huge = {"x": "y" * (16 * 1024 + 1)}
    r = client.post(
        "/mesh/sync", headers=_auth(sid),
        json={"device_id": "dev-2", "metadata": huge},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "mesh_payload"


def test_mesh_sync_lru_at_eight(app_module, client):
    """Drive the store directly with explicit timestamps so the eviction
    assertion isn't sensitive to the host clock's resolution (Windows
    time.time() can repeat across rapid calls)."""
    import mesh_metadata_store
    user, _sid = _make_user(app_module, "milo", cohort="founder")
    for i in range(10):
        mesh_metadata_store.upsert_device(
            user, f"dev-{i}", {"i": i}, now_ts=1000.0 + i,
        )
    state = mesh_metadata_store.state_for(user)
    assert len(state["devices"]) == 8
    # Oldest two (dev-0, dev-1) should be evicted, dev-9 (newest) kept.
    assert "dev-0" not in state["devices"]
    assert "dev-1" not in state["devices"]
    assert "dev-9" in state["devices"]


def test_mesh_state_blocked_when_flag_off(app_module, client):
    user, sid = _make_user(app_module, "mira", cohort=None)
    r = client.get("/mesh/state", headers=_auth(sid))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# /continuity/snapshot — shape contract
# ---------------------------------------------------------------------------
def test_continuity_snapshot_shape(app_module, client):
    user, sid = _make_user(app_module, "carol", cohort="founder")
    r = client.get("/continuity/snapshot", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    snap = r.json()["snapshot"]
    # Required top-level keys
    for k in ("user", "now_ts", "counts", "last_updated_ts",
              "memory_context", "coherence_flags"):
        assert k in snap
    # Required count keys
    for k in ("events", "episodes", "narratives", "story_arcs", "elins_briefs"):
        assert k in snap["counts"]
        assert isinstance(snap["counts"][k], int)


# ---------------------------------------------------------------------------
# /sessions and /engines — minimal surface
# ---------------------------------------------------------------------------
def test_sessions_list_empty(app_module, client):
    user, sid = _make_user(app_module, "shilo", cohort="founder")
    r = client.get("/sessions", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert isinstance(body["sessions"], list)
    assert body["count"] == len(body["sessions"])


def test_sessions_list_bad_limit_rejected(app_module, client):
    user, sid = _make_user(app_module, "sam", cohort="founder")
    # FastAPI coerces ?limit=abc to 422 before our validator sees it; we test
    # the in-app validator using a negative int.
    r = client.get("/sessions?limit=-1", headers=_auth(sid))
    assert r.status_code == 400


def test_engines_returns_catalog(app_module, client):
    user, sid = _make_user(app_module, "ed", cohort="founder")
    r = client.get("/engines", headers=_auth(sid))
    assert r.status_code == 200
    engines = r.json()["engines"]
    assert {e["id"] for e in engines} == {"markov", "galileo", "library", "tizzy"}


# ---------------------------------------------------------------------------
# /runtime/envelope — receives all 21 layers + strips heavy vectors
# ---------------------------------------------------------------------------
def test_runtime_envelope_strips_vectors_and_renders_layers(app_module, client):
    import envelopes_store

    user, sid = _make_user(app_module, "ronan", cohort="founder")
    # Seed a fully-populated envelope so the renderer's 21 layers are present.
    big_vec = [0.1] * 768
    envelopes_store.set_envelope(user, {
        "updated_at": time.time(),
        "envelope_vector": big_vec,
        "envelope_centroid": big_vec,
        "events": [{"vector": big_vec, "summary": "evt"}],
        "episodes": {"e1": {"episode_vector": big_vec}},
        "narratives": {"n1": {"node_vector": big_vec, "compressed_vector": big_vec}},
        "story_arcs": {"a1": {"arc_vector": big_vec, "arc_vector_compressed": big_vec}},
        "identity": {"identity_vector": big_vec, "last_updated_ts": time.time()},
        "trajectory": {"trajectory_vector": big_vec, "phase": "arc1"},
        "elins": {"physics_block": {"k": 1}, "mean_center_vector": big_vec, "s_strategy_layer": {}},
        "universal_physics": {"constraints": []},
        "coherence": {"identity_ok": True, "trajectory_ok": True},
        "external_context": {},
        "physics_reasoning_context": {},
        "reasoning_cues": {},
        "reasoning_weights": {},
        "memory_context": {"last_updated_ts": time.time()},
        "external_knowledge": {},
        "cognitive_loop": {},
        "reasoning_scaffold": {},
        "response_shape": {},
        "response_templates": {},
        "sentence_operators": {},
        "connective_ops": {},
        "elins_briefs": [{"object_vector": big_vec, "scenario_id": "sc_test"}],
    })

    r = client.get("/runtime/envelope", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    env = r.json()["envelope"]

    # All 21 v6→v27 layers reach the surface.
    expected_layers = [
        "events", "episodes", "narratives", "story_arcs", "identity",
        "trajectory", "elins", "universal_physics", "coherence",
        "external_context", "physics_reasoning_context", "reasoning_cues",
        "reasoning_weights", "memory_context", "external_knowledge",
        "cognitive_loop", "reasoning_scaffold", "response_shape",
        "response_templates", "sentence_operators", "connective_ops",
    ]
    for layer in expected_layers:
        assert layer in env, f"missing layer {layer}"

    # Heavy vectors are stripped to descriptors.
    def is_descriptor(v):
        return isinstance(v, dict) and v.get("_vector") is True

    assert is_descriptor(env["envelope_vector"])
    assert env["envelope_vector"]["dim"] == 768
    assert is_descriptor(env["envelope_centroid"])
    assert is_descriptor(env["events"][0]["vector"])
    assert is_descriptor(env["identity"]["identity_vector"])
    assert is_descriptor(env["trajectory"]["trajectory_vector"])
    assert is_descriptor(env["elins"]["mean_center_vector"])
    assert is_descriptor(env["elins_briefs"][0]["object_vector"])


# ---------------------------------------------------------------------------
# /v29/onboarding flow
# ---------------------------------------------------------------------------
def test_onboarding_state_then_complete(app_module, client):
    user, sid = _make_user(app_module, "olive", cohort="founder")

    r = client.get("/v29/onboarding/state", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["next_step"] == "vault_check"
    assert body["done"] is False

    for step in ("vault_check", "dewey_sync", "continuity_snapshot"):
        r = client.post(
            "/v29/onboarding/complete", headers=_auth(sid),
            json={"step": step},
        )
        assert r.status_code == 200, r.json()

    final = client.get("/v29/onboarding/state", headers=_auth(sid)).json()
    assert final["done"] is True


def test_onboarding_complete_rejects_unknown_step(app_module, client):
    user, sid = _make_user(app_module, "owen", cohort="founder")
    r = client.post(
        "/v29/onboarding/complete", headers=_auth(sid),
        json={"step": "not_a_real_step"},
    )
    assert r.status_code == 400


def test_demo_seed_idempotent(app_module, client):
    import vault_store

    user, sid = _make_user(app_module, "dani", cohort="founder")
    r = client.post("/v29/onboarding/seed", headers=_auth(sid))
    assert r.status_code == 200
    summary = r.json()["summary"]
    assert summary["vault"] >= 1

    # Second call must be a no-op (already populated).
    r2 = client.post("/v29/onboarding/seed", headers=_auth(sid))
    assert r2.status_code == 200
    summary2 = r2.json()["summary"]
    assert summary2["skipped"] is True
    assert summary2["vault"] == 0


# ---------------------------------------------------------------------------
# Auth requirement — unauthenticated calls return 401 (consistent shape)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("path,method,body", [
    ("/sessions", "GET", None),
    ("/runtime/envelope", "GET", None),
    ("/engines", "GET", None),
    ("/continuity/snapshot", "GET", None),
    ("/mesh/state", "GET", None),
    ("/elins/daily/feed", "GET", None),
    ("/elins/daily/queue", "POST", {"scenario_text": "x"}),
    ("/elins/g/run", "POST", {"scenario_text": "x"}),
    ("/mesh/sync", "POST", {"device_id": "d", "metadata": {}}),
    ("/v29/onboarding/state", "GET", None),
    ("/v29/onboarding/complete", "POST", {"step": "vault_check"}),
])
def test_endpoints_require_session(app_module, client, path, method, body):
    if method == "GET":
        r = client.get(path)
    else:
        r = client.post(path, json=body)
    assert r.status_code == 401, f"{path} returned {r.status_code}"
    assert r.json()["error"] in {"missing_session", "invalid_session"}
