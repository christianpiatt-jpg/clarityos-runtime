"""
Tests for v45 — Local model runtime + on-device inference pipeline.

Covers:
* local_model_runtime
  - load_local_model: no path → mock; bad path → mock with last_error;
    valid path (simulated) → real handle; cache reuse (warm-start).
  - run_local_inference: deterministic mock text; clamps temperature /
    max_tokens; dispatch to a fake llama_cpp via monkeypatch; degrades
    on inference failure.
  - unload_local_model: drops cache, releases native handle.
  - get_runtime_status: shape + memory_footprint computation.

* model_router integration
  - _call_local routes to runtime when path set; falls back to mock
    when path missing.
  - get_model_status['local'] includes the path field.
  - get_router_status includes a local_runtime block.
  - _reset_for_tests wipes the local handle cache (no leak across tests).

* operator_state
  - default state has local_model_usage_count=0; bump_local_model_usage
    increments idempotently and clamps negatives.
  - kernel routes to local model → counter increments.

* kernel
  - kernel_status includes a local_model block with the runtime fields.
  - kernel_view_for_user surfaces local_model_usage_count.

* Endpoints
  - GET /me/local_model returns runtime + per-user usage.
  - GET /founder/models/local returns runtime + env_path; founder gate.
"""
from __future__ import annotations

import os
import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures (mirroring v44)
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


# ---------------------------------------------------------------------------
# local_model_runtime — load_local_model
# ---------------------------------------------------------------------------
def test_load_local_model_unset_returns_mock(reset_stores, monkeypatch):
    monkeypatch.delenv("CLARITYOS_LOCAL_MODEL_PATH", raising=False)
    import local_model_runtime as lmr
    handle = lmr.load_local_model()
    assert handle.mock is True
    assert handle.backend == "mock"
    assert handle.path == ""


def test_load_local_model_bad_path_falls_to_mock(reset_stores, monkeypatch, tmp_path):
    bogus = str(tmp_path / "no_model_here.gguf")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", bogus)
    import local_model_runtime as lmr
    handle = lmr.load_local_model()
    assert handle.mock is True
    assert handle.backend == "mock"
    # Bad path is recorded as last_error so the UI can surface it.
    assert handle.last_error and "not found" in handle.last_error


def test_load_local_model_warm_start_cache(reset_stores, monkeypatch, tmp_path):
    """Second load with the same path returns the same handle object."""
    bogus = str(tmp_path / "weights.gguf")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", bogus)
    import local_model_runtime as lmr
    a = lmr.load_local_model()
    b = lmr.load_local_model()
    assert a is b


def test_load_local_model_real_path_simulated(
    reset_stores, monkeypatch, tmp_path,
):
    """Simulate a real GGUF load by monkeypatching _load_llama_cpp."""
    fake_path = tmp_path / "real.gguf"
    fake_path.write_bytes(b"fake-gguf-bytes")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(fake_path))

    import local_model_runtime as lmr

    class FakeLlama:
        def __init__(self): pass
        def __call__(self, prompt, **kw):
            return {"choices": [{"text": f"REAL:{prompt[:10]}"}]}

    monkeypatch.setattr(lmr, "_load_llama_cpp", lambda path: FakeLlama())

    handle = lmr.load_local_model()
    assert handle.mock is False
    assert handle.backend == "llama_cpp"
    assert handle.bytes_estimate > 0
    assert handle._native is not None


def test_load_local_model_missing_backend_degrades(
    reset_stores, monkeypatch, tmp_path,
):
    """When the path is real but the backend isn't installed the handle
    degrades to mock with a last_error explanation."""
    fake_path = tmp_path / "weights.gguf"
    fake_path.write_bytes(b"x")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(fake_path))

    import local_model_runtime as lmr

    def raise_import(_path):
        raise ImportError("llama_cpp not installed")
    monkeypatch.setattr(lmr, "_load_llama_cpp", raise_import)

    handle = lmr.load_local_model()
    assert handle.mock is True
    assert handle.backend == "mock"
    assert "llama_cpp" in (handle.last_error or "")


# ---------------------------------------------------------------------------
# local_model_runtime — run_local_inference
# ---------------------------------------------------------------------------
def test_run_local_inference_mock_is_deterministic(reset_stores, monkeypatch):
    monkeypatch.delenv("CLARITYOS_LOCAL_MODEL_PATH", raising=False)
    import local_model_runtime as lmr
    h = lmr.load_local_model()
    a = lmr.run_local_inference(h, "test prompt 1")
    b = lmr.run_local_inference(h, "test prompt 1")
    assert a["text"] == b["text"]
    assert a["mock"] is True
    assert a["text"].startswith("[local-mock")
    # Different prompt → different text (hash-prefixed).
    c = lmr.run_local_inference(h, "different prompt")
    assert c["text"] != a["text"]


def test_run_local_inference_clamps_inputs(reset_stores, monkeypatch):
    monkeypatch.delenv("CLARITYOS_LOCAL_MODEL_PATH", raising=False)
    import local_model_runtime as lmr
    h = lmr.load_local_model()
    # Out-of-range temperature + max_tokens → no exception, mock returns OK.
    out = lmr.run_local_inference(h, "x", temperature=99.0, max_tokens=-5)
    assert out["ok"] is True


def test_run_local_inference_real_path_simulated(
    reset_stores, monkeypatch, tmp_path,
):
    fake_path = tmp_path / "real.gguf"
    fake_path.write_bytes(b"x")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(fake_path))
    import local_model_runtime as lmr

    class FakeLlama:
        def __call__(self, prompt, **kw):
            return {"choices": [{"text": f"REAL:{prompt}"}]}

    monkeypatch.setattr(lmr, "_load_llama_cpp", lambda path: FakeLlama())
    h = lmr.load_local_model()
    out = lmr.run_local_inference(h, "hi")
    assert out["mock"] is False
    assert out["text"] == "REAL:hi"
    assert out["backend"] == "llama_cpp"
    # inference_count bumps each call.
    lmr.run_local_inference(h, "again")
    assert h.inference_count == 2


def test_run_local_inference_failure_degrades_to_mock(
    reset_stores, monkeypatch, tmp_path,
):
    fake_path = tmp_path / "real.gguf"
    fake_path.write_bytes(b"x")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(fake_path))
    import local_model_runtime as lmr

    class FlakyLlama:
        def __call__(self, prompt, **kw):
            raise RuntimeError("inference exploded")

    monkeypatch.setattr(lmr, "_load_llama_cpp", lambda path: FlakyLlama())
    h = lmr.load_local_model()
    out = lmr.run_local_inference(h, "hi")
    assert out["ok"] is True
    assert out["mock"] is True
    assert "exploded" in out.get("fallback_error", "")


def test_run_local_inference_rejects_bad_handle(reset_stores):
    import local_model_runtime as lmr
    with pytest.raises(TypeError):
        lmr.run_local_inference("not-a-handle", "hi")


# ---------------------------------------------------------------------------
# unload_local_model
# ---------------------------------------------------------------------------
def test_unload_local_model_drops_cache(reset_stores, monkeypatch, tmp_path):
    fake_path = tmp_path / "weights.gguf"
    fake_path.write_bytes(b"x")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(fake_path))

    import local_model_runtime as lmr

    class FakeLlama:
        def __call__(self, prompt, **kw):
            return {"choices": [{"text": "x"}]}

    monkeypatch.setattr(lmr, "_load_llama_cpp", lambda path: FakeLlama())
    h = lmr.load_local_model()
    assert lmr.unload_local_model(h) is True
    assert lmr.get_cached_handle() is None
    # Second unload is a no-op.
    assert lmr.unload_local_model(h) is False


def test_unload_local_model_rejects_bad_arg(reset_stores):
    import local_model_runtime as lmr
    assert lmr.unload_local_model("nope") is False


# ---------------------------------------------------------------------------
# get_runtime_status — shape + memory footprint
# ---------------------------------------------------------------------------
def test_get_runtime_status_shape_unconfigured(reset_stores, monkeypatch):
    monkeypatch.delenv("CLARITYOS_LOCAL_MODEL_PATH", raising=False)
    import local_model_runtime as lmr
    s = lmr.get_runtime_status()
    assert s["configured"] is False
    assert s["loaded"] is False
    assert s["mock"] is True
    assert s["memory_footprint_mb"] == 0.0
    assert s["version"].startswith("local_model_runtime.v45")


def test_get_runtime_status_after_load(reset_stores, monkeypatch, tmp_path):
    weights = tmp_path / "weights.gguf"
    weights.write_bytes(b"x" * (2 * 1024 * 1024))   # 2 MB
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(weights))

    import local_model_runtime as lmr

    class FakeLlama:
        def __call__(self, prompt, **kw):
            return {"choices": [{"text": "x"}]}

    monkeypatch.setattr(lmr, "_load_llama_cpp", lambda path: FakeLlama())
    lmr.load_local_model()
    s = lmr.get_runtime_status()
    assert s["configured"] is True
    assert s["loaded"] is True
    assert s["backend"] == "llama_cpp"
    assert s["mock"] is False
    # 2MB file → 2.0 MB.
    assert s["memory_footprint_mb"] == pytest.approx(2.0, abs=0.05)


# ---------------------------------------------------------------------------
# model_router integration
# ---------------------------------------------------------------------------
def test_model_router_local_no_path_returns_mock(reset_stores, monkeypatch):
    monkeypatch.delenv("CLARITYOS_LOCAL_MODEL_PATH", raising=False)
    import model_router as mr
    out = mr.route_request("local:llama3.1", "hello")
    assert out["mock"] is True
    assert out["model_id"] == "local:llama3.1"
    assert out["provider"] == "local"


def test_model_router_local_with_path_uses_runtime(
    reset_stores, monkeypatch, tmp_path,
):
    weights = tmp_path / "real.gguf"
    weights.write_bytes(b"x")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(weights))
    import local_model_runtime as lmr
    import model_router as mr

    class FakeLlama:
        def __call__(self, prompt, **kw):
            return {"choices": [{"text": f"R:{prompt}"}]}

    monkeypatch.setattr(lmr, "_load_llama_cpp", lambda path: FakeLlama())

    out = mr.route_request("local:llama3.1", "ping")
    assert out["mock"] is False
    assert out["text"] == "R:ping"
    assert out["backend"] == "llama_cpp"
    assert out["model_path"] == str(weights)


def test_model_router_get_model_status_includes_local_path(
    reset_stores, monkeypatch, tmp_path,
):
    weights = tmp_path / "weights.gguf"
    weights.write_bytes(b"x")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(weights))
    import model_router as mr
    status = mr.get_model_status()
    assert status["local"]["configured"] is True
    assert status["local"]["path"] == str(weights)


def test_model_router_get_router_status_includes_local_runtime(reset_stores, monkeypatch):
    monkeypatch.delenv("CLARITYOS_LOCAL_MODEL_PATH", raising=False)
    import model_router as mr
    s = mr.get_router_status()
    assert "local_runtime" in s
    assert s["local_runtime"]["configured"] is False
    assert s["local_runtime"]["mock"] is True


def test_model_router_warm_start_cache_reused(
    reset_stores, monkeypatch, tmp_path,
):
    weights = tmp_path / "warm.gguf"
    weights.write_bytes(b"x")
    monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", str(weights))
    import local_model_runtime as lmr
    import model_router as mr

    load_calls = {"n": 0}
    real_load = lmr.load_local_model

    def counting_load(path=None):
        load_calls["n"] += 1
        return real_load(path)

    monkeypatch.setattr(lmr, "load_local_model", counting_load)
    monkeypatch.setattr(lmr, "_load_llama_cpp",
                        lambda p: type("L", (), {"__call__": lambda *a, **k: {"choices": [{"text": "x"}]}})())

    mr.route_request("local:llama3.1", "p1")
    mr.route_request("local:llama3.1", "p2")
    mr.route_request("local:llama3.1", "p3")
    # First call warms the router-level handle; subsequent calls reuse it.
    assert load_calls["n"] == 1


# ---------------------------------------------------------------------------
# operator_state — local_model_usage_count
# ---------------------------------------------------------------------------
def test_operator_state_default_local_usage_zero(reset_stores):
    import operator_state as os_mod
    state = os_mod.get_operator_state("alice")
    assert state["local_model_usage_count"] == 0


def test_operator_state_bump_local_model_usage(reset_stores):
    import operator_state as os_mod
    state = os_mod.bump_local_model_usage("alice")
    assert state["local_model_usage_count"] == 1
    state = os_mod.bump_local_model_usage("alice", by=2)
    assert state["local_model_usage_count"] == 3
    # Negative values clamp to 0 → no decrement.
    state = os_mod.bump_local_model_usage("alice", by=-5)
    assert state["local_model_usage_count"] == 3


def test_operator_state_bump_no_user_is_noop(reset_stores):
    import operator_state as os_mod
    assert os_mod.bump_local_model_usage("") == {}


# ---------------------------------------------------------------------------
# Kernel integration
# ---------------------------------------------------------------------------
def test_kernel_increments_local_usage_when_local_chosen(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_mod
    os_mod.set_preferred_model("alice", "local:llama3.1")
    ik.run_ELINS("alice", "trust eroding", kind="preview", persist=False)
    state = os_mod.get_operator_state("alice")
    assert state["last_model_used"] == "local:llama3.1"
    assert state["local_model_usage_count"] == 1
    # Second run bumps again.
    ik.run_ELINS("alice", "more text", kind="preview", persist=False)
    assert os_mod.get_operator_state("alice")["local_model_usage_count"] == 2


def test_kernel_does_not_increment_for_non_local_model(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_mod
    # Default task default for ELINS is anthropic:claude-3.7 — not local.
    ik.run_ELINS("alice", "x", kind="preview", persist=False)
    assert os_mod.get_operator_state("alice")["local_model_usage_count"] == 0


def test_kernel_status_includes_local_model_block(reset_stores, monkeypatch):
    monkeypatch.delenv("CLARITYOS_LOCAL_MODEL_PATH", raising=False)
    import intelligence_kernel as ik
    s = ik.kernel_status()
    assert "local_model" in s
    lm = s["local_model"]
    assert lm["configured"] is False
    assert lm["loaded"] is False
    assert lm["mock"] is True
    assert "memory_footprint_mb" in lm
    assert "inference_count" in lm


def test_kernel_view_for_user_includes_local_usage(reset_stores):
    import intelligence_kernel as ik
    import operator_state as os_mod
    os_mod.bump_local_model_usage("alice")
    os_mod.bump_local_model_usage("alice")
    view = ik.kernel_view_for_user("alice")
    assert view["local_model_usage_count"] == 2


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def test_endpoint_me_local_model_shape(app_module, client):
    user, sid = _make_user(app_module, "lm_a", cohort="founder")
    r = client.get("/me/local_model", headers=_auth(sid))
    assert r.status_code == 200, r.json()
    body = r.json()
    assert body["model_id"] == "local:llama3.1"
    assert "runtime" in body
    assert "usage" in body
    assert "configured" in body["runtime"]
    assert "fallback" in body["runtime"]
    assert body["usage"]["local_model_usage_count"] == 0
    assert body["usage"]["is_local_preferred"] is False


def test_endpoint_me_local_model_reflects_usage(app_module, client):
    """After the kernel routes the user through the local model, the
    /me/local_model endpoint should show the bumped counter."""
    user, sid = _make_user(app_module, "lm_b", cohort="founder")
    # Set preference → kernel will pick local on the next ELINS run.
    client.post(
        "/me/operator_state/model", headers=_auth(sid),
        json={"preferred_model": "local:llama3.1"},
    )
    client.post(
        "/elins/preview", headers=_auth(sid),
        json={"text": "trust between partners eroding"},
    )
    r = client.get("/me/local_model", headers=_auth(sid))
    body = r.json()
    assert body["usage"]["local_model_usage_count"] == 1
    assert body["usage"]["is_local_preferred"] is True
    assert body["usage"]["last_model_used"] == "local:llama3.1"


def test_endpoint_founder_models_local_shape(app_module, client):
    user, sid = _make_user(app_module, "lm_f", cohort="founder")
    r = client.get("/founder/models/local", headers=_auth(sid))
    assert r.status_code == 200
    body = r.json()
    assert body["model_id"] == "local:llama3.1"
    assert "runtime" in body
    assert "env_path" in body
    assert "router_provider" in body
    # No path set in tests → env_path is None.
    assert body["env_path"] is None
    assert body["router_provider"]["configured"] is False


def test_endpoint_founder_models_local_requires_founder(app_module, client):
    user, sid = _make_user(app_module, "lm_outsider", cohort=None)
    r = client.get("/founder/models/local", headers=_auth(sid))
    assert r.status_code == 403


def test_endpoint_me_advertises_local_model_capability(app_module, client):
    user, sid = _make_user(app_module, "cap_lm", cohort="founder")
    r = client.get("/me", headers=_auth(sid))
    ids = [c["id"] for c in r.json().get("capabilities") or []]
    assert "local_model" in ids


def test_endpoint_founder_models_status_includes_local_runtime(app_module, client):
    """v44's /founder/models/status now carries the v45 local_runtime
    block via get_router_status."""
    user, sid = _make_user(app_module, "lm_router", cohort="founder")
    r = client.get("/founder/models/status", headers=_auth(sid))
    body = r.json()
    assert "local_runtime" in body["router"]
    assert body["router"]["local_runtime"]["configured"] is False


def test_health_version_bumped_to_4_1(app_module, client):
    """v45 set health version to 4.1; v46 bumps to 4.2. Either is OK
    here — the v45 contract didn't include the literal version string."""
    r = client.get("/health")
    assert r.json()["version"].startswith("4.")
