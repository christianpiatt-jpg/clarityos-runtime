"""
Tests for v65 / Unit 69 — provider health dashboard.

Stubs ``model_router._http_post_json`` to simulate provider responses
without real HTTP. Per Christian's spec: no real network calls in
tests.

Layered coverage:
    A. Unauthed → 401
    B. No env keys → only "mock" available; everything else "no api key"
    C. One env key → only that provider gets checked
    D. Stubbed success → available=true
    E. Stubbed failure → available=false + error string
    F. Response shape locked
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from conftest import TestClient

import model_router as mr
import runtime_http as rh_mod
import runtime_persistence as rp_mod
import sessions_store


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(rh_mod.providers_router)

    # Clean env so each test sets exactly the keys it cares about.
    # New (fork β.3) reachability-based providers added below so the
    # urllib path inside _check_provider_reachability bails out at the
    # "no api key configured" guard and never hits the real network.
    for k in (
        "CLARITYOS_ANTHROPIC_KEY",
        "CLARITYOS_OPENAI_KEY",
        "CLARITYOS_GEMINI_KEY",
        "CLARITYOS_XAI_KEY",
        "CLARITYOS_LOCAL_MODEL_PATH",
        # Reachability-checked providers (fork β.3):
        "CLARITYOS_PERPLEXITY_API_KEY",
        "CLARITYOS_MISTRAL_API_KEY",
        "CLARITYOS_DEEPSEEK_API_KEY",
    ):
        monkeypatch.delenv(k, raising=False)

    mr._reset_for_tests()
    rp_mod._reset_for_tests()
    yield TestClient(app)
    mr._reset_for_tests()
    rp_mod._reset_for_tests()


def _auth(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-ph-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# ===========================================================================
# A. Unauthed → 401
# ===========================================================================
class TestAuth:
    def test_unauthed_health_check_returns_401(self, client):
        r = client.get("/runtime/providers/health")
        assert r.status_code == 401


# ===========================================================================
# B. No env keys → only mock available
# ===========================================================================
class TestNoKeys:
    def test_no_keys_only_mock_available(self, client):
        r = client.get("/runtime/providers/health", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert body["mock"]["available"] is True
        assert body["mock"]["error"] is None
        # Inference-checked providers (existing).
        for provider in ("anthropic", "openai", "gemini"):
            assert body[provider]["available"] is False
            assert "no api key" in body[provider]["error"]
        # Reachability-checked providers (fork β.3).
        for provider in ("xai", "perplexity", "mistral", "deepseek"):
            assert body[provider]["available"] is False
            assert "no api key" in body[provider]["error"]


# ===========================================================================
# C. One env key → only that provider gets the HTTP check
# ===========================================================================
class TestSingleKey:
    def test_only_anthropic_key_triggers_anthropic_check(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")

        called = {"providers": []}
        def fake_http(url, *, headers, body):
            if "anthropic.com" in url:
                called["providers"].append("anthropic")
                return {"content": [{"type": "text", "text": "ok"}]}
            raise AssertionError(f"unexpected url {url}")
        monkeypatch.setattr(mr, "_http_post_json", fake_http)

        r = client.get("/runtime/providers/health", headers=_auth())
        body = r.json()
        assert body["anthropic"]["available"] is True
        assert body["openai"]["available"] is False
        assert body["gemini"]["available"] is False
        # Only the anthropic URL was hit.
        assert called["providers"] == ["anthropic"]


# ===========================================================================
# D. Stubbed success per provider
# ===========================================================================
class TestStubbedSuccess:
    def test_anthropic_success(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-a")
        monkeypatch.setattr(
            mr, "_http_post_json",
            lambda url, *, headers, body: {"content": [{"type": "text", "text": "ok"}]},
        )
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["anthropic"] == {"available": True, "error": None}

    def test_openai_success(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-o")
        monkeypatch.setattr(
            mr, "_http_post_json",
            lambda url, *, headers, body: {"choices": [{"message": {"content": "ok"}}]},
        )
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["openai"] == {"available": True, "error": None}

    def test_gemini_success(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-g")
        monkeypatch.setattr(
            mr, "_http_post_json",
            lambda url, *, headers, body: {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
        )
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["gemini"] == {"available": True, "error": None}


# ===========================================================================
# E. Stubbed failure per provider
# ===========================================================================
class TestStubbedFailure:
    def test_anthropic_failure_marks_unavailable_with_error(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")

        def boom(*_args, **_kwargs):
            raise ConnectionError("simulated 401 unauthorized")
        monkeypatch.setattr(mr, "_http_post_json", boom)

        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["anthropic"]["available"] is False
        assert "simulated 401 unauthorized" in r["anthropic"]["error"]

    def test_openai_failure_marks_unavailable_with_error(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        monkeypatch.setattr(
            mr, "_http_post_json",
            lambda *a, **kw: (_ for _ in ()).throw(TimeoutError("simulated timeout")),
        )
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["openai"]["available"] is False
        assert "simulated timeout" in r["openai"]["error"]

    def test_gemini_failure_marks_unavailable_with_error(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-test")
        monkeypatch.setattr(
            mr, "_http_post_json",
            lambda *a, **kw: (_ for _ in ()).throw(ValueError("simulated parse error")),
        )
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["gemini"]["available"] is False
        assert "simulated parse error" in r["gemini"]["error"]


# ===========================================================================
# F. Response shape locked
# ===========================================================================
class TestResponseShape:
    def test_keys_are_exactly_the_supported_providers(self, client):
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        # Fork β.3 — keys now include the 4 reachability-checked
        # providers alongside the 3 inference-checked ones plus mock.
        assert set(r.keys()) == {
            "anthropic", "openai", "gemini",          # inference-path
            "xai", "perplexity", "mistral", "deepseek",  # reachability
            "mock",                                    # always-available
        }

    def test_each_provider_carries_locked_inner_keys(self, client):
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        for provider, entry in r.items():
            assert set(entry.keys()) == {"available", "error"}, (
                f"{provider!r} entry keys: {set(entry.keys())}"
            )
            assert isinstance(entry["available"], bool)
            assert entry["error"] is None or isinstance(entry["error"], str)

    def test_mock_is_always_available(self, client):
        r = client.get("/runtime/providers/health", headers=_auth()).json()
        assert r["mock"] == {"available": True, "error": None}
