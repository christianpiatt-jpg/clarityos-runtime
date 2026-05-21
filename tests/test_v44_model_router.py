"""
Tests for v44 — Multi-model router + kernel-level model selection.

Covers:
* model_router.select_model — override > founder default > preferred_model
  > task default precedence; "auto" sentinel falls through.
* model_router.route_request — provider dispatch + mock fallback +
  unknown model rejection.
* get_model_status / get_router_status — env-driven configured flags.
* operator_state.set_preferred_model + record_model_used round-trip.
* Kernel integration:
  - run_c / run_G / run_ELINS / run_regional_ELINS / run_macro_ELINS
    surface ``model_id`` in their result.
  - kernel_logging records ``model_id`` in the meta.
  - kernel_view_for_user includes ``preferred_model`` + ``last_model_used``.
  - kernel_status includes the ``models`` block.
* Endpoints:
  - POST /me/operator_state/model — happy path + bad model 400.
  - GET /founder/models/status — founder gate + shape.
  - POST /founder/models/override — founder gate + clear-by-null.
"""
from __future__ import annotations

import json
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
# select_model precedence + determinism
# ---------------------------------------------------------------------------
def test_select_model_explicit_override(reset_stores):
    import model_router as mr
    assert mr.select_model(None, task="ELINS",
                           override="openai:gpt-4o") == "openai:gpt-4o"


def test_select_model_override_auto_falls_through(reset_stores):
    """``auto`` is a sentinel — it should NOT be returned as the
    selected model id; the router should fall through to the next
    precedence step."""
    import model_router as mr
    chosen = mr.select_model(None, task="c", override="auto")
    assert chosen == mr.TASK_DEFAULTS["c"]
    assert chosen != "auto"


def test_select_model_override_unknown_raises(reset_stores):
    import model_router as mr
    with pytest.raises(ValueError):
        mr.select_model(None, task="ELINS", override="not_a_model")


def test_select_model_founder_default_overrides_user_pref(reset_stores):
    import model_router as mr
    import operator_state
    operator_state.set_preferred_model("alice", "openai:gpt-4o")
    mr.set_founder_default_model("anthropic:claude-3.7")
    try:
        # No explicit override → founder default wins over user pref.
        assert mr.select_model("alice", task="c") == "anthropic:claude-3.7"
    finally:
        mr.set_founder_default_model(None)


def test_select_model_user_pref_used_when_no_override_and_no_founder_default(reset_stores):
    import model_router as mr
    import operator_state
    operator_state.set_preferred_model("alice", "google:gemini-2.0-flash")
    assert mr.select_model("alice", task="c") == "google:gemini-2.0-flash"


def test_select_model_falls_to_task_default(reset_stores):
    import model_router as mr
    # No user pref, no founder default.
    assert mr.select_model(None, task="c") == mr.TASK_DEFAULTS["c"]
    assert mr.select_model(None, task="ELINS") == mr.TASK_DEFAULTS["ELINS"]
    assert mr.select_model(None, task="macro") == mr.TASK_DEFAULTS["macro"]


def test_select_model_run_kind_aliases(reset_stores):
    """``run_c``, ``run_G`` etc. are accepted as task labels (mirrors
    kernel_logging.kind values)."""
    import model_router as mr
    assert mr.select_model(None, task="run_c") == mr.TASK_DEFAULTS["c"]
    assert mr.select_model(None, task="run_macro_ELINS") == mr.TASK_DEFAULTS["macro"]


def test_select_model_is_deterministic(reset_stores):
    import model_router as mr
    import operator_state
    operator_state.set_preferred_model("alice", "anthropic:claude-3.7")
    a = mr.select_model("alice", task="c")
    b = mr.select_model("alice", task="c")
    assert a == b == "anthropic:claude-3.7"


# ---------------------------------------------------------------------------
# route_request — provider dispatch + mock fallback
# ---------------------------------------------------------------------------
def test_route_request_default_mock(reset_stores):
    import model_router as mr
    r = mr.route_request("anthropic:claude-3.7", "hello world")
    assert r["ok"] is True
    assert r["mock"] is True
    assert r["model_id"] == "anthropic:claude-3.7"
    assert r["provider"] == "anthropic"


def test_route_request_calls_correct_provider(reset_stores, monkeypatch):
    import model_router as mr
    called = {"name": None}

    def fake_handler(model_id, prompt, *, temperature, max_tokens):
        called["name"] = mr.parse_provider(model_id)
        return {
            "ok": True, "model_id": model_id, "provider": called["name"],
            "text": "[fake]", "mock": False, "ts": 0.0,
        }

    monkeypatch.setitem(mr._PROVIDER_HANDLERS, "openai", fake_handler)
    r = mr.route_request("openai:gpt-4o", "ping")
    assert called["name"] == "openai"
    assert r["mock"] is False


def test_route_request_unknown_model_raises(reset_stores):
    import model_router as mr
    with pytest.raises(ValueError):
        mr.route_request("not:a-model", "x")


def test_route_request_auto_resolves_safely(reset_stores):
    """``auto`` must resolve to a real provider when route_request is
    called with it directly (defence-in-depth — callers should have
    already resolved via select_model)."""
    import model_router as mr
    r = mr.route_request("auto", "hello")
    assert r["mock"] is True
    assert r["provider"] != "auto"


def test_route_request_mock_is_deterministic(reset_stores):
    import model_router as mr
    a = mr.route_request("anthropic:claude-3.7", "exact prompt")
    b = mr.route_request("anthropic:claude-3.7", "exact prompt")
    # ts differs — strip it.
    a.pop("ts", None); b.pop("ts", None)
    assert a == b


# ---------------------------------------------------------------------------
# get_model_status / get_router_status
# ---------------------------------------------------------------------------
def test_provider_status_default_all_unconfigured(reset_stores, monkeypatch):
    for env in ("CLARITYOS_OPENAI_KEY", "CLARITYOS_ANTHROPIC_KEY",
                "CLARITYOS_GEMINI_KEY", "CLARITYOS_XAI_KEY",
                "CLARITYOS_LOCAL_MODEL_PATH"):
        monkeypatch.delenv(env, raising=False)
    import model_router as mr
    status = mr.get_model_status()
    for provider in ("openai", "anthropic", "gemini", "xai"):
        assert status[provider] == {"configured": False}
    # v45 — local provider carries an extra `path` field for the UI;
    # `configured` is still False when the env var is unset.
    assert status["local"]["configured"] is False
    assert status["local"]["path"] is None


def test_provider_status_reflects_env_keys(reset_stores, monkeypatch):
    monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "test-key")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", "/tmp/llama")
    import model_router as mr
    status = mr.get_model_status()
    assert status["anthropic"]["configured"] is True
    assert status["local"]["configured"] is True
    assert status["openai"]["configured"] is False


def test_router_status_includes_supported_models(reset_stores):
    import model_router as mr
    status = mr.get_router_status()
    # v45 bumped the router version. Either v44 or v45+ is fine — the
    # selector contract didn't change.
    assert status["version"].startswith("model_router.v")
    assert "auto" in status["supported_models"]
    assert "anthropic:claude-3.7" in status["supported_models"]
    assert isinstance(status["task_defaults"], dict)


# ---------------------------------------------------------------------------
# operator_state — preferred_model + last_model_used
# ---------------------------------------------------------------------------
def test_operator_state_default_model_fields(reset_stores):
    import operator_state
    state = operator_state.get_operator_state("alice")
    assert state["preferred_model"] is None
    assert state["last_model_used"] is None


def test_operator_state_set_preferred_model_validates(reset_stores):
    import operator_state
    with pytest.raises(ValueError):
        operator_state.set_preferred_model("alice", "not_a_model")


def test_operator_state_set_preferred_model_accepts_clear(reset_stores):
    import operator_state
    operator_state.set_preferred_model("alice", "anthropic:claude-3.7")
    state = operator_state.set_preferred_model("alice", None)
    assert state["preferred_model"] is None


def test_operator_state_record_model_used(reset_stores):
    import operator_state
    operator_state.record_model_used("alice", "openai:gpt-4o")
    assert operator_state.get_operator_state("alice")["last_model_used"] == "openai:gpt-4o"


# ---------------------------------------------------------------------------
# Kernel integration — model_id surfaces on every run_*
# ---------------------------------------------------------------------------
def test_kernel_run_c_surfaces_model_id(reset_stores):
    import intelligence_kernel as ik
    r = ik.run_c("alice", "the agency is drifting from its mandate")
    assert r["ok"] is True
    assert r["model_id"]


def test_kernel_run_G_surfaces_model_id(reset_stores):
    import intelligence_kernel as ik

    def fake_runner(text, user):
        return {"ok": True, "analysis": {"qc_summary": {"pressure": 0.4}}}

    r = ik.run_G("alice", "x", runner=fake_runner)
    assert r["ok"] is True
    assert r["model_id"] == ik.model_router.TASK_DEFAULTS["G"]


def test_kernel_run_ELINS_surfaces_model_id(reset_stores):
    import intelligence_kernel as ik
    r = ik.run_ELINS(
        "alice", "trust between partners is eroding",
        kind="preview", persist=False,
    )
    assert "model_id" in r
    assert r["model_id"] == ik.model_router.TASK_DEFAULTS["ELINS"]


def test_kernel_run_regional_ELINS_surfaces_model_id(reset_stores):
    import intelligence_kernel as ik
    r = ik.run_regional_ELINS("alice", "US")
    assert "model_id" in r
    assert r["model_id"] == ik.model_router.TASK_DEFAULTS["regional"]


def test_kernel_run_macro_ELINS_surfaces_model_id(reset_stores):
    import intelligence_kernel as ik
    summary = ik.run_macro_ELINS("scheduler")
    assert summary["model_id"] == ik.model_router.TASK_DEFAULTS["macro"]


def test_kernel_logging_includes_model_id(reset_stores, caplog):
    import intelligence_kernel as ik
    caplog.set_level("INFO", logger="clarityos.kernel.runs")
    ik.run_c("alice", "the agency is drifting from its mandate")
    # Find the run_c log line + parse JSON payload.
    found_model_ids = []
    for rec in caplog.records:
        msg = rec.message
        if msg.startswith("kernel_run "):
            payload = json.loads(msg.split(" ", 1)[1])
            if (payload.get("meta") or {}).get("model_id"):
                found_model_ids.append(payload["meta"]["model_id"])
    assert any(found_model_ids), "no model_id present in any kernel_run log"


def test_kernel_run_records_last_model_used(reset_stores):
    """After run_*, operator_state.last_model_used reflects the
    selected model."""
    import intelligence_kernel as ik
    import operator_state
    ik.run_ELINS("alice", "trust eroding", kind="preview", persist=False)
    state = operator_state.get_operator_state("alice")
    assert state["last_model_used"] == ik.model_router.TASK_DEFAULTS["ELINS"]


def test_kernel_view_for_user_includes_model_fields(reset_stores):
    import intelligence_kernel as ik
    import operator_state
    operator_state.set_preferred_model("alice", "openai:gpt-4o")
    operator_state.record_model_used("alice", "anthropic:claude-3.7")
    view = ik.kernel_view_for_user("alice")
    assert view["preferred_model"] == "openai:gpt-4o"
    assert view["last_model_used"] == "anthropic:claude-3.7"


def test_kernel_status_includes_models_block(reset_stores):
    import intelligence_kernel as ik
    status = ik.kernel_status()
    assert "models" in status
    assert "providers" in status["models"]
    assert "supported_models" in status["models"]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def test_endpoint_set_preferred_model(app_module, client):
    user, sid = _make_user(app_module, "mp_a", cohort="founder")
    r = client.post(
        "/me/operator_state/model", headers=_auth(sid),
        json={"preferred_model": "anthropic:claude-3.7"},
    )
    assert r.status_code == 200, r.json()
    state = r.json()["state"]
    assert state["preferred_model"] == "anthropic:claude-3.7"


def test_endpoint_set_preferred_model_clear_with_null(app_module, client):
    user, sid = _make_user(app_module, "mp_b", cohort="founder")
    client.post(
        "/me/operator_state/model", headers=_auth(sid),
        json={"preferred_model": "anthropic:claude-3.7"},
    )
    r = client.post(
        "/me/operator_state/model", headers=_auth(sid),
        json={"preferred_model": None},
    )
    assert r.status_code == 200
    assert r.json()["state"]["preferred_model"] is None


def test_endpoint_set_preferred_model_rejects_unknown(app_module, client):
    user, sid = _make_user(app_module, "mp_c", cohort="founder")
    r = client.post(
        "/me/operator_state/model", headers=_auth(sid),
        json={"preferred_model": "not_a_model"},
    )
    assert r.status_code == 400


def test_endpoint_founder_models_status_shape(app_module, client):
    user, sid = _make_user(app_module, "fm_a", cohort="founder")
    r = client.get("/founder/models/status", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert "router" in body
    router = body["router"]
    assert "supported_models" in router
    assert "providers" in router
    assert "task_defaults" in router


def test_endpoint_founder_models_status_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "fm_outsider", cohort=None)
    r = client.get("/founder/models/status", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_founder_models_override_round_trip(app_module, client):
    user, sid = _make_user(app_module, "fmo_a", cohort="founder")
    r = client.post(
        "/founder/models/override", headers=_auth(sid),
        json={"default_model": "google:gemini-2.0-flash"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["default_model"] == "google:gemini-2.0-flash"
    assert body["router"]["founder_default_model"] == "google:gemini-2.0-flash"
    # Clear the override.
    r2 = client.post(
        "/founder/models/override", headers=_auth(sid),
        json={"default_model": None},
    )
    assert r2.json()["router"]["founder_default_model"] is None


def test_endpoint_founder_models_override_validates(app_module, client):
    user, sid = _make_user(app_module, "fmo_b", cohort="founder")
    r = client.post(
        "/founder/models/override", headers=_auth(sid),
        json={"default_model": "not_a_model"},
    )
    assert r.status_code == 400


def test_endpoint_founder_models_override_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "fmo_outsider", cohort=None)
    r = client.post(
        "/founder/models/override", headers=_auth(sid),
        json={"default_model": "anthropic:claude-3.7"},
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# /me — preferred_model + last_model_used surfaced via intelligence_kernel block
# ---------------------------------------------------------------------------
def test_me_includes_preferred_and_last_model(app_module, client):
    user, sid = _make_user(app_module, "me_a", cohort="founder")
    client.post(
        "/me/operator_state/model", headers=_auth(sid),
        json={"preferred_model": "anthropic:claude-3.7"},
    )
    # Trigger a kernel run so last_model_used populates.
    client.post(
        "/elins/preview", headers=_auth(sid),
        json={"text": "trust between partners eroding"},
    )
    r = client.get("/me", headers=_auth(sid))
    body = r.json()
    ik_block = body["intelligence_kernel"]
    assert ik_block["preferred_model"] == "anthropic:claude-3.7"
    # last_model_used should reflect the user's preference (which the
    # router selects for the ELINS task).
    assert ik_block["last_model_used"] == "anthropic:claude-3.7"


def test_me_advertises_model_router_capability(app_module, client):
    user, sid = _make_user(app_module, "cap_a", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    ids = [c["id"] for c in r.json().get("capabilities") or []]
    assert "model_router" in ids
