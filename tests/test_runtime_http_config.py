"""
Tests for runtime_http_config (v66 / Unit 71).

Covers:
    A. Module shape — defaults, maps, getter signatures
    B. Per-provider getters — known, unknown, None
    C. Wiring — model_router._PROVIDER_HTTP_TIMEOUT picks up the
       config default at import time
    D. Wiring — model_router._request_timeout mutates and restores
       the global transactionally
    E. Health check timeout — _check_provider_health pulls from
       runtime_http_config.get_health_timeout
    F. No back-imports — runtime_http_config is a leaf module
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
# A. Module shape
# ===========================================================================
class TestShape:
    def test_default_call_timeout_is_30_seconds(self):
        assert rhc.DEFAULT_CALL_TIMEOUT == 30.0

    def test_default_health_timeout_is_3_seconds(self):
        assert rhc.DEFAULT_HEALTH_TIMEOUT == 3.0

    def test_default_retries_is_zero(self):
        assert rhc.DEFAULT_RETRIES == 0

    def test_call_timeouts_cover_all_providers(self):
        assert set(rhc.PROVIDER_CALL_TIMEOUTS.keys()) == {
            "anthropic", "openai", "gemini", "xai", "local",
        }

    def test_health_timeouts_cover_all_providers(self):
        assert set(rhc.PROVIDER_HEALTH_TIMEOUTS.keys()) == {
            "anthropic", "openai", "gemini", "xai", "local",
        }

    def test_retries_cover_all_providers(self):
        assert set(rhc.PROVIDER_RETRIES.keys()) == {
            "anthropic", "openai", "gemini", "xai", "local",
        }


# ===========================================================================
# B. Getters
# ===========================================================================
class TestGetters:
    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini", "xai", "local"])
    def test_call_timeout_matches_map(self, provider):
        assert rhc.get_call_timeout(provider) == rhc.PROVIDER_CALL_TIMEOUTS[provider]

    @pytest.mark.parametrize("provider", ["anthropic", "openai", "gemini", "xai", "local"])
    def test_health_timeout_matches_map(self, provider):
        assert rhc.get_health_timeout(provider) == rhc.PROVIDER_HEALTH_TIMEOUTS[provider]

    def test_unknown_provider_returns_default_call_timeout(self):
        assert rhc.get_call_timeout("nonexistent") == rhc.DEFAULT_CALL_TIMEOUT

    def test_unknown_provider_returns_default_health_timeout(self):
        assert rhc.get_health_timeout("nonexistent") == rhc.DEFAULT_HEALTH_TIMEOUT

    def test_none_provider_returns_default_call_timeout(self):
        assert rhc.get_call_timeout(None) == rhc.DEFAULT_CALL_TIMEOUT

    def test_none_provider_returns_default_health_timeout(self):
        assert rhc.get_health_timeout(None) == rhc.DEFAULT_HEALTH_TIMEOUT

    def test_retry_count_zero_by_default(self):
        for provider in ("anthropic", "openai", "gemini", "xai", "local"):
            assert rhc.get_retry_count(provider) == 0
        assert rhc.get_retry_count("unknown") == 0
        assert rhc.get_retry_count(None) == 0


# ===========================================================================
# C. model_router picks up the default at import
# ===========================================================================
class TestModelRouterDefault:
    def test_model_router_global_matches_config_default(self):
        # The pre-Unit-71 behaviour was a hardcoded 30.0; the post-
        # Unit-71 behaviour is that the same value comes from
        # runtime_http_config.DEFAULT_CALL_TIMEOUT.
        assert mr._PROVIDER_HTTP_TIMEOUT == rhc.DEFAULT_CALL_TIMEOUT


# ===========================================================================
# D. _request_timeout context manager
# ===========================================================================
class TestRequestTimeoutContextManager:
    def test_request_timeout_sets_global_inside_block(self):
        original = mr._PROVIDER_HTTP_TIMEOUT
        seen_inside = None
        with mr._request_timeout(7.5):
            seen_inside = mr._PROVIDER_HTTP_TIMEOUT
        assert seen_inside == 7.5
        # Restored after the block exits.
        assert mr._PROVIDER_HTTP_TIMEOUT == original

    def test_request_timeout_restores_after_exception(self):
        original = mr._PROVIDER_HTTP_TIMEOUT
        with pytest.raises(RuntimeError):
            with mr._request_timeout(1.5):
                raise RuntimeError("boom")
        assert mr._PROVIDER_HTTP_TIMEOUT == original

    def test_request_timeout_nested_blocks_restore_lifo(self):
        original = mr._PROVIDER_HTTP_TIMEOUT
        with mr._request_timeout(10.0):
            with mr._request_timeout(20.0):
                assert mr._PROVIDER_HTTP_TIMEOUT == 20.0
            assert mr._PROVIDER_HTTP_TIMEOUT == 10.0
        assert mr._PROVIDER_HTTP_TIMEOUT == original


# ===========================================================================
# E. Health-check pulls timeout from config
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
    sid = f"auth-cfg-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


class TestHealthCheckUsesConfig:
    def test_health_check_applies_config_health_timeout(self, client, monkeypatch):
        """During the health probe, _PROVIDER_HTTP_TIMEOUT must equal
        the value runtime_http_config.get_health_timeout returns. The
        fake _http_post_json snapshots the live value mid-call so we
        can assert against it."""
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")
        observed: dict[str, float] = {}

        def fake_http(url, *, headers, body):
            observed["timeout_during_call"] = mr._PROVIDER_HTTP_TIMEOUT
            return {"content": [{"type": "text", "text": "ok"}]}

        monkeypatch.setattr(mr, "_http_post_json", fake_http)
        # Push a distinctive health timeout so we can detect a hit.
        monkeypatch.setitem(rhc.PROVIDER_HEALTH_TIMEOUTS, "anthropic", 1.25)

        r = client.get("/runtime/providers/health", headers=_auth())
        assert r.status_code == 200
        assert observed["timeout_during_call"] == 1.25

    def test_health_check_restores_call_timeout_after_probe(self, client, monkeypatch):
        """The global timeout must return to the pre-probe value once
        the health check completes — i.e. the call path isn't
        permanently throttled to 3s."""
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")
        monkeypatch.setattr(
            mr, "_http_post_json",
            lambda url, *, headers, body: {"content": [{"type": "text", "text": "ok"}]},
        )
        prior = mr._PROVIDER_HTTP_TIMEOUT
        client.get("/runtime/providers/health", headers=_auth())
        assert mr._PROVIDER_HTTP_TIMEOUT == prior


# ===========================================================================
# F. No back-imports
# ===========================================================================
class TestLeafModule:
    def test_runtime_http_config_does_not_import_model_router(self):
        # If runtime_http_config imported model_router (which itself
        # imports runtime_http_config), Python would deadlock or
        # produce a partial module on cold import. Assert the leaf
        # nature by inspecting the module's globals.
        import sys
        cfg_globals = sys.modules["runtime_http_config"].__dict__
        # The module deliberately doesn't bind model_router / runtime_http
        # at the top level. Allow `runtime_http_config` to reference
        # standard library names only.
        assert "model_router" not in cfg_globals
        assert "runtime_http" not in cfg_globals
