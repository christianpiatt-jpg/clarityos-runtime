"""
Tests for v64 / Unit 65 — runtime_providers adapter + vault-stored
model preference + per-operator selection.

No real HTTP — provider calls are stubbed by monkey-patching
``model_router._http_post_json`` (the single chokepoint introduced
in v65).

Layered coverage:
    A. Env-var matrix → get_available_providers
    B. Provider→model_id bridge (model_id_for)
    C. call_model — mock fallback when key absent
    D. call_model — stub real call when key present
    E. get_operator_model resolution chain
    F. Vault preference round-trip
    G. session_loop integrates preferred_model_id into operator_intent
    H. provider_error field surfaces in history on fallback
"""
from __future__ import annotations

import pytest

import model_router as mr
import runtime_persistence as rp_mod
import runtime_providers as rp
import session_loop as sl_mod


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _reset_all(monkeypatch):
    """Clean env + persistence + router state per test."""
    for key in (
        "CLARITYOS_ANTHROPIC_KEY",
        "CLARITYOS_OPENAI_KEY",
        "CLARITYOS_GEMINI_KEY",
        "CLARITYOS_XAI_KEY",
        "CLARITYOS_LOCAL_MODEL_PATH",
        "CLARITYOS_RUNTIME_STORE_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    rp_mod.reload_backend()
    rp_mod._reset_for_tests()
    mr._reset_for_tests()
    yield
    rp_mod._reset_for_tests()
    mr._reset_for_tests()


# ===========================================================================
# A. Env-var matrix → get_available_providers
# ===========================================================================
class TestAvailableProviders:
    def test_no_keys_empty_list(self):
        assert rp.get_available_providers() == []

    def test_anthropic_only(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")
        assert rp.get_available_providers() == ["anthropic"]

    def test_openai_only(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        assert rp.get_available_providers() == ["openai"]

    def test_anthropic_plus_openai_ordering(self, monkeypatch):
        # PROVIDERS_ORDER puts anthropic first, then openai.
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        avail = rp.get_available_providers()
        assert avail == ["anthropic", "openai"]

    def test_all_keys_present(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-a")
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-o")
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-g")
        monkeypatch.setenv("CLARITYOS_XAI_KEY", "sk-x")
        monkeypatch.setenv("CLARITYOS_LOCAL_MODEL_PATH", "/tmp/model.gguf")
        # We can't actually load the local model file, so file existence
        # doesn't matter here — _provider_configured just checks the env.
        avail = rp.get_available_providers()
        assert avail == ["anthropic", "openai", "gemini", "xai", "local"]


# ===========================================================================
# B. Provider→model_id bridge
# ===========================================================================
class TestModelIdBridge:
    def test_anthropic_maps_to_anthropic_prefix(self):
        assert rp.model_id_for("anthropic", "claude-haiku-4-5-20251001") == "anthropic:claude-haiku-4-5-20251001"

    def test_openai_maps_to_openai_prefix(self):
        assert rp.model_id_for("openai", "gpt-5.4") == "openai:gpt-5.4"

    def test_gemini_maps_to_google_prefix(self):
        # NB: operator-vocab "gemini" maps to model_router prefix "google:".
        assert rp.model_id_for("gemini", "gemini-2.5-flash") == "google:gemini-2.5-flash"

    def test_unknown_provider_rejected(self):
        with pytest.raises(ValueError, match="provider"):
            rp.model_id_for("perplexity", "sonar-pro")

    def test_empty_model_rejected(self):
        with pytest.raises(ValueError, match="model"):
            rp.model_id_for("anthropic", "")


# ===========================================================================
# C. call_model — mock fallback when key absent
# ===========================================================================
class TestCallModelMockFallback:
    def test_anthropic_without_key_returns_mock_text(self):
        text = rp.call_model("anthropic", "claude-haiku-4-5-20251001", "hello")
        # Mock text prefixes with "[mock anthropic:claude-haiku-4-5-20251001]".
        assert text.startswith("[mock anthropic:claude-haiku-4-5-20251001]")

    def test_unsupported_model_id_returns_synthetic_mock(self):
        # Model name that won't pass is_valid_model — bridge returns
        # a synthetic mock without touching model_router.
        text = rp.call_model("anthropic", "claude-99-omega", "hi")
        assert text.startswith("[mock anthropic:claude-99-omega]")


# ===========================================================================
# D. call_model — stub real call when key present
# ===========================================================================
class TestCallModelRealStub:
    def test_anthropic_real_path_via_stubbed_http(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")

        captured = {"url": None, "body": None, "headers": None}
        def fake_http(url, *, headers, body):
            captured["url"] = url
            captured["headers"] = headers
            captured["body"] = body
            return {"content": [{"type": "text", "text": "stub-anthropic-reply"}]}
        monkeypatch.setattr(mr, "_http_post_json", fake_http)

        text = rp.call_model("anthropic", "claude-haiku-4-5-20251001", "hello there")
        assert text == "stub-anthropic-reply"
        assert captured["url"] == "https://api.anthropic.com/v1/messages"
        assert captured["headers"]["x-api-key"] == "sk-test"
        assert captured["body"]["model"] == "claude-haiku-4-5-20251001"
        assert captured["body"]["messages"][0]["content"] == "hello there"

    def test_openai_real_path_via_stubbed_http(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")

        def fake_http(url, *, headers, body):
            return {"choices": [{"message": {"content": "stub-openai-reply"}}]}
        monkeypatch.setattr(mr, "_http_post_json", fake_http)

        text = rp.call_model("openai", "gpt-5.4", "hi")
        assert text == "stub-openai-reply"

    def test_gemini_real_path_via_stubbed_http(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_GEMINI_KEY", "sk-test")

        def fake_http(url, *, headers, body):
            return {"candidates": [{"content": {"parts": [{"text": "stub-gemini-reply"}]}}]}
        monkeypatch.setattr(mr, "_http_post_json", fake_http)

        text = rp.call_model("gemini", "gemini-2.5-flash", "hi")
        assert text == "stub-gemini-reply"

    def test_anthropic_http_failure_falls_back_to_mock(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")

        def boom(url, *, headers, body):
            raise ConnectionError("simulated network error")
        monkeypatch.setattr(mr, "_http_post_json", boom)

        text = rp.call_model("anthropic", "claude-haiku-4-5-20251001", "hi")
        assert text.startswith("[mock anthropic:claude-haiku-4-5-20251001]")


# ===========================================================================
# E. get_operator_model resolution chain
# ===========================================================================
class TestGetOperatorModel:
    def test_empty_vault_no_keys_falls_back_to_anthropic_default(self):
        provider, model = rp.get_operator_model({})
        assert (provider, model) == ("anthropic", "claude-haiku-4-5-20251001")

    def test_no_vault_pref_uses_first_available_provider(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        # No anthropic key — first available is openai.
        provider, model = rp.get_operator_model({})
        assert provider == "openai"
        assert model == "gpt-5.4"

    def test_vault_pref_wins_over_default(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        vault = {
            "runtime": {
                "model_preferences": {"provider": "gemini", "model": "gemini-2.5-flash"},
            },
        }
        provider, model = rp.get_operator_model(vault)
        assert (provider, model) == ("gemini", "gemini-2.5-flash")

    def test_malformed_vault_pref_falls_through(self, monkeypatch):
        # provider not in PROVIDERS_ORDER → ignore, fall through.
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        vault = {
            "runtime": {"model_preferences": {"provider": "perplexity", "model": "x"}},
        }
        provider, model = rp.get_operator_model(vault)
        assert provider == "openai"   # fallback chain kicked in

    def test_vault_pref_missing_model_falls_through(self):
        vault = {"runtime": {"model_preferences": {"provider": "anthropic"}}}
        provider, model = rp.get_operator_model(vault)
        # Falls through to no-key default.
        assert (provider, model) == ("anthropic", "claude-haiku-4-5-20251001")


# ===========================================================================
# F. Vault preference round-trip
# ===========================================================================
class TestVaultPreferenceRoundtrip:
    def test_set_returns_new_vault_with_preference(self):
        new = rp.set_operator_model_preference_in_vault(
            {}, "anthropic", "claude-haiku-4-5-20251001",
        )
        assert new["runtime"]["model_preferences"] == {
            "provider": "anthropic", "model": "claude-haiku-4-5-20251001",
        }

    def test_set_preserves_existing_keys(self):
        vault = {"elins": {"fusion_history": [{"step": 1}]}}
        new = rp.set_operator_model_preference_in_vault(
            vault, "openai", "gpt-5.4",
        )
        assert new["elins"] == {"fusion_history": [{"step": 1}]}
        assert new["runtime"]["model_preferences"]["provider"] == "openai"

    def test_set_does_not_mutate_input(self):
        vault = {"runtime": {"other_key": "preserved"}}
        new = rp.set_operator_model_preference_in_vault(
            vault, "anthropic", "claude-haiku-4-5-20251001",
        )
        # New runtime dict; input unchanged.
        assert "model_preferences" not in vault["runtime"]
        assert new["runtime"]["other_key"] == "preserved"

    def test_set_rejects_unknown_provider(self):
        with pytest.raises(ValueError, match="provider"):
            rp.set_operator_model_preference_in_vault({}, "perplexity", "x")


# ===========================================================================
# G. session_loop integration — preferred_model_id reaches Unit 38
# ===========================================================================
class TestSessionLoopIntegration:
    def test_vault_pref_used_in_step(self, monkeypatch):
        # Capture the model_id that route_request sees.
        captured = {"model_id": None}
        real_route = mr.route_request
        def spy_route(model_id, prompt, **kwargs):
            captured["model_id"] = model_id
            return real_route(model_id, prompt, **kwargs)
        monkeypatch.setattr(mr, "route_request", spy_route)

        state = sl_mod.start_session("op_alice")
        # Seed a vault preference for op_alice.
        prior_vault = rp_mod.load_vault("op_alice") or {}
        new_vault = rp.set_operator_model_preference_in_vault(
            prior_vault, "gemini", "gemini-2.5-flash",
        )
        rp_mod.save_vault("op_alice", new_vault)

        sl_mod.step_session(state, "do a thing")
        # Vault preference should override the engine-based default
        # (query intent → copilot engine → xai:groq-llama).
        assert captured["model_id"] == "google:gemini-2.5-flash"

    def test_no_vault_pref_uses_engine_default(self, monkeypatch):
        # Without a vault preference and without env keys, the
        # engine-based path picks copilot → xai:groq-llama for query
        # intents (per Unit 36's locked routing).
        captured = {"model_id": None}
        real_route = mr.route_request
        def spy_route(model_id, prompt, **kwargs):
            captured["model_id"] = model_id
            return real_route(model_id, prompt, **kwargs)
        monkeypatch.setattr(mr, "route_request", spy_route)

        state = sl_mod.start_session("op_alice")
        # Wipe vault to ensure no preference.
        rp_mod._VAULTS.clear()
        sl_mod.step_session(state, "do a thing")
        # With NO env keys, get_operator_model returns ("anthropic",
        # "claude-haiku-4-5-20251001") (final fallback). That gets injected and wins.
        # This proves the chain works end-to-end.
        assert captured["model_id"] == "anthropic:claude-haiku-4-5-20251001"


# ===========================================================================
# H. provider_error field surfaces in history on fallback
# ===========================================================================
class TestProviderErrorField:
    def test_real_http_failure_records_provider_error(self, monkeypatch):
        monkeypatch.setenv("CLARITYOS_ANTHROPIC_KEY", "sk-test")
        # Force the anthropic real-call path to fail.
        def boom(url, *, headers, body):
            raise ConnectionError("simulated network error")
        monkeypatch.setattr(mr, "_http_post_json", boom)

        state = sl_mod.start_session("op_alice")
        # Set anthropic preference so the step hits the failing path.
        prior_vault = rp_mod.load_vault("op_alice") or {}
        new_vault = rp.set_operator_model_preference_in_vault(
            prior_vault, "anthropic", "claude-haiku-4-5-20251001",
        )
        rp_mod.save_vault("op_alice", new_vault)

        out = sl_mod.step_session(state, "hi")
        entry = out["session_state"]["history"][0]
        assert "provider_error" in entry
        assert "simulated network error" in entry["provider_error"]

    def test_no_provider_error_when_step_succeeds(self):
        # No env keys → mock path → no fallback_error → no
        # provider_error key on the history entry.
        state = sl_mod.start_session("op_alice")
        out = sl_mod.step_session(state, "hi")
        entry = out["session_state"]["history"][0]
        assert "provider_error" not in entry
