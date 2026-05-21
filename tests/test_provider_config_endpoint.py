"""
Tests for v68 / Unit 73 — GET /runtime/providers/config endpoint.

Covers:
    A. Auth gate
    B. Response shape locked
    C. Per-provider timeouts match runtime_http_config getters
    D. Defaults block matches module-level constants
    E. mock provider is intentionally absent (no HTTP path)
    F. Config edits propagate (registry override picks up immediately)
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from conftest import TestClient

import model_router as mr
import runtime_http as rh_mod
import runtime_http_config as rhc
import runtime_persistence as rp_mod
import sessions_store


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(rh_mod.providers_router)
    for k in (
        "CLARITYOS_ANTHROPIC_KEY",
        "CLARITYOS_OPENAI_KEY",
        "CLARITYOS_GEMINI_KEY",
        "CLARITYOS_XAI_KEY",
        "CLARITYOS_LOCAL_MODEL_PATH",
    ):
        monkeypatch.delenv(k, raising=False)
    mr._reset_for_tests()
    rp_mod._reset_for_tests()
    yield TestClient(app)
    mr._reset_for_tests()
    rp_mod._reset_for_tests()


def _auth(user: str = "op_alice") -> dict[str, str]:
    sid = f"auth-pcfg-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# ===========================================================================
# A. Auth gate
# ===========================================================================
class TestAuth:
    def test_unauthed_config_endpoint_returns_401(self, client):
        r = client.get("/runtime/providers/config")
        assert r.status_code == 401


# ===========================================================================
# B. Response shape
# ===========================================================================
class TestResponseShape:
    def test_top_level_keys_locked(self, client):
        r = client.get("/runtime/providers/config", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"timeouts", "retries", "defaults"}

    def test_timeouts_cover_known_providers(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert set(body["timeouts"].keys()) == {
            "anthropic", "openai", "gemini", "xai", "local",
        }

    def test_each_timeout_entry_has_call_and_health(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        for provider, entry in body["timeouts"].items():
            assert set(entry.keys()) == {"call", "health"}, provider
            assert isinstance(entry["call"], (int, float)), provider
            assert isinstance(entry["health"], (int, float)), provider

    def test_retries_cover_known_providers(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert set(body["retries"].keys()) == {
            "anthropic", "openai", "gemini", "xai", "local",
        }
        for provider, n in body["retries"].items():
            assert isinstance(n, int), provider

    def test_defaults_block_carries_three_locked_keys(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert set(body["defaults"].keys()) == {
            "call_timeout", "health_timeout", "retries",
        }


# ===========================================================================
# C. Per-provider values come from runtime_http_config
# ===========================================================================
class TestValuesFromConfig:
    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini", "xai", "local"])
    def test_call_timeout_matches_getter(self, client, provider):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert body["timeouts"][provider]["call"] == rhc.get_call_timeout(provider)

    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini", "xai", "local"])
    def test_health_timeout_matches_getter(self, client, provider):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert body["timeouts"][provider]["health"] == rhc.get_health_timeout(provider)

    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini", "xai", "local"])
    def test_retries_match_getter(self, client, provider):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert body["retries"][provider] == rhc.get_retry_count(provider)


# ===========================================================================
# D. Defaults block
# ===========================================================================
class TestDefaults:
    def test_default_call_timeout_matches_module_constant(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert body["defaults"]["call_timeout"] == rhc.DEFAULT_CALL_TIMEOUT

    def test_default_health_timeout_matches_module_constant(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert body["defaults"]["health_timeout"] == rhc.DEFAULT_HEALTH_TIMEOUT

    def test_default_retries_matches_module_constant(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert body["defaults"]["retries"] == rhc.DEFAULT_RETRIES


# ===========================================================================
# E. mock provider absence (it has no HTTP path)
# ===========================================================================
class TestMockAbsence:
    def test_mock_provider_not_in_timeouts(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert "mock" not in body["timeouts"]

    def test_mock_provider_not_in_retries(self, client):
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert "mock" not in body["retries"]


# ===========================================================================
# F. Registry edits propagate
# ===========================================================================
class TestPropagation:
    def test_changing_call_timeout_reflects_in_endpoint(self, client, monkeypatch):
        monkeypatch.setitem(rhc.PROVIDER_CALL_TIMEOUTS, "anthropic", 7.5)
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert body["timeouts"]["anthropic"]["call"] == 7.5

    def test_changing_retries_reflects_in_endpoint(self, client, monkeypatch):
        monkeypatch.setitem(rhc.PROVIDER_RETRIES, "openai", 3)
        body = client.get(
            "/runtime/providers/config", headers=_auth(),
        ).json()
        assert body["retries"]["openai"] == 3
