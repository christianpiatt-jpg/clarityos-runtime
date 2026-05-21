"""
Tests for v66 / Unit 71 — /runtime/providers/models endpoint and the
MODEL_REGISTRY structural rewrite.

Covers:
    A. Endpoint auth
    B. Response shape locked
    C. Registry / SUPPORTED_MODELS coherence
    D. Validation entry points still honour SUPPORTED_MODELS
"""
from __future__ import annotations

import time

import pytest
from fastapi import FastAPI

from conftest import TestClient

import model_router as mr
import runtime_http as rh_mod
import runtime_persistence as rp_mod
import runtime_providers
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
    sid = f"auth-models-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# ===========================================================================
# A. Auth
# ===========================================================================
class TestAuth:
    def test_unauthed_models_endpoint_returns_401(self, client):
        r = client.get("/runtime/providers/models")
        assert r.status_code == 401


# ===========================================================================
# B. Response shape
# ===========================================================================
class TestResponseShape:
    def test_top_level_keys_locked(self, client):
        r = client.get("/runtime/providers/models", headers=_auth())
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"registry", "supported"}

    def test_registry_has_five_provider_keys(self, client):
        body = client.get(
            "/runtime/providers/models", headers=_auth(),
        ).json()
        assert set(body["registry"].keys()) == {
            "openai", "anthropic", "google", "xai", "local",
        }

    def test_registry_values_are_string_lists(self, client):
        body = client.get(
            "/runtime/providers/models", headers=_auth(),
        ).json()
        for provider, models in body["registry"].items():
            assert isinstance(models, list), provider
            for model_id in models:
                assert isinstance(model_id, str), (provider, model_id)
                assert ":" in model_id, (provider, model_id)

    def test_supported_carries_auto_sentinel(self, client):
        body = client.get(
            "/runtime/providers/models", headers=_auth(),
        ).json()
        assert "auto" in body["supported"]

    def test_supported_includes_all_registry_models(self, client):
        body = client.get(
            "/runtime/providers/models", headers=_auth(),
        ).json()
        flat = {m for models in body["registry"].values() for m in models}
        for model_id in flat:
            assert model_id in body["supported"], model_id


# ===========================================================================
# C. Registry / SUPPORTED_MODELS coherence
# ===========================================================================
class TestRegistryCoherence:
    def test_model_registry_is_present(self):
        assert hasattr(mr, "MODEL_REGISTRY")
        assert isinstance(mr.MODEL_REGISTRY, dict)

    def test_supported_models_is_derived_from_registry(self):
        flat = [m for models in mr.MODEL_REGISTRY.values() for m in models]
        # SUPPORTED_MODELS should equal the flattened registry + "auto".
        assert tuple(flat) + ("auto",) == mr.SUPPORTED_MODELS

    def test_no_duplicate_models_across_providers(self):
        seen: set[str] = set()
        for provider, models in mr.MODEL_REGISTRY.items():
            for model_id in models:
                assert model_id not in seen, f"duplicate: {model_id}"
                seen.add(model_id)

    def test_supported_models_tuple_type_preserved(self):
        # Existing call sites do ``model_id in SUPPORTED_MODELS`` — that
        # works for both tuples and lists, but tuple is the lock-in.
        assert isinstance(mr.SUPPORTED_MODELS, tuple)

    def test_is_valid_model_still_works(self):
        assert mr.is_valid_model("anthropic:claude-3.7")
        assert mr.is_valid_model("auto")
        assert not mr.is_valid_model("not-a-real-model")
        assert not mr.is_valid_model(None)


# ===========================================================================
# D. runtime_providers validation against new registry
# ===========================================================================
class TestValidationStillWorks:
    def test_model_id_for_resolves_registry_entries(self):
        # The (provider, model) -> model_id helper exposed by
        # runtime_providers must continue to produce ids that pass
        # is_valid_model after the rewrite.
        mid = runtime_providers.model_id_for("anthropic", "claude-3.7")
        assert mr.is_valid_model(mid)

    def test_model_id_for_unknown_model_fails_is_valid_check(self):
        # ``model_id_for`` doesn't validate against the registry (it
        # only enforces the provider prefix); the second-stage
        # ``is_valid_model`` check is where the registry is consulted.
        # The combo of (model_id_for + is_valid_model) is the actual
        # allowlist gate in ``runtime_http.set_model_preferences``.
        mid = runtime_providers.model_id_for("anthropic", "not-real-9999")
        assert not mr.is_valid_model(mid)

    def test_model_id_for_rejects_unknown_provider(self):
        with pytest.raises(ValueError):
            runtime_providers.model_id_for("not-a-provider", "any")
