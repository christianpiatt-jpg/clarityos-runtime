"""
Tests for v64 / Unit 67 — operator model preferences API.

Two endpoints, both auth-gated:
    GET  /operator/model_preferences  → resolved (provider, model)
    POST /operator/model_preferences  → set vault preference

Layered coverage:
    A. Unauthed → 401
    B. GET returns default when no vault preference
    C. POST updates vault → GET reflects change
    D. POST validation — invalid provider / unsupported model
    E. POST is per-operator (Alice's update doesn't change Bob's)
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
import session_loop as sl_mod
import sessions_store


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(rh_mod.runtime_router)
    app.include_router(rh_mod.operator_router)

    sid_counter = {"n": 0}
    def fake_make_session_id():
        sid_counter["n"] += 1
        return f"sess-pref-{sid_counter['n']:03d}"
    monkeypatch.setattr(sl_mod, "_make_session_id", fake_make_session_id)

    mr._reset_for_tests()
    rp_mod._reset_for_tests()
    yield TestClient(app)
    mr._reset_for_tests()
    rp_mod._reset_for_tests()


def _auth(user: str) -> dict[str, str]:
    sid = f"auth-pref-{user}"
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)
    return {"X-Session-ID": sid}


# ===========================================================================
# A. Unauthed → 401
# ===========================================================================
class TestAuth:
    def test_get_requires_auth(self, client):
        r = client.get("/operator/model_preferences")
        assert r.status_code == 401

    def test_post_requires_auth(self, client):
        r = client.post(
            "/operator/model_preferences",
            json={"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
        )
        assert r.status_code == 401


# ===========================================================================
# B. GET returns default when no vault preference
# ===========================================================================
class TestGetDefault:
    def test_no_vault_returns_chain_default(self, client):
        # No env keys → fallback to ("anthropic", "claude-haiku-4-5-20251001").
        r = client.get("/operator/model_preferences", headers=_auth("op_alice"))
        assert r.status_code == 200
        body = r.json()
        assert body["operator_id"] == "op_alice"
        assert body["provider"]    == "anthropic"
        assert body["model"]       == "claude-haiku-4-5-20251001"
        assert body["source"]      == "default"

    def test_no_vault_with_openai_key_returns_openai(self, client, monkeypatch):
        monkeypatch.setenv("CLARITYOS_OPENAI_KEY", "sk-test")
        r = client.get("/operator/model_preferences", headers=_auth("op_alice"))
        body = r.json()
        # With openai available and no anthropic key, default chain
        # picks openai (PROVIDERS_ORDER lists anthropic first but only
        # configured providers count).
        assert body["provider"] == "openai"
        assert body["source"]   == "default"


# ===========================================================================
# C. POST updates vault → GET reflects change
# ===========================================================================
class TestPostUpdate:
    def test_post_returns_updated_preference(self, client):
        r = client.post(
            "/operator/model_preferences",
            json={"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
            headers=_auth("op_alice"),
        )
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "operator_id": "op_alice",
            "provider":    "anthropic",
            "model":       "claude-haiku-4-5-20251001",
            "source":      "vault",
        }

    def test_subsequent_get_reflects_post(self, client):
        # Initial GET → default.
        before = client.get(
            "/operator/model_preferences", headers=_auth("op_alice"),
        ).json()
        assert before["source"] == "default"

        # POST.
        client.post(
            "/operator/model_preferences",
            json={"provider": "openai", "model": "gpt-5.4"},
            headers=_auth("op_alice"),
        )

        # GET again → vault preference now wins.
        after = client.get(
            "/operator/model_preferences", headers=_auth("op_alice"),
        ).json()
        assert after["source"]   == "vault"
        assert after["provider"] == "openai"
        assert after["model"]    == "gpt-5.4"

    def test_post_persists_to_vault(self, client):
        client.post(
            "/operator/model_preferences",
            json={"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
            headers=_auth("op_alice"),
        )
        vault = rp_mod.load_vault("op_alice")
        assert vault["runtime"]["model_preferences"] == {
            "provider": "anthropic", "model": "claude-haiku-4-5-20251001",
        }

    def test_post_overwrites_prior_preference(self, client):
        client.post(
            "/operator/model_preferences",
            json={"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
            headers=_auth("op_alice"),
        )
        client.post(
            "/operator/model_preferences",
            json={"provider": "gemini", "model": "gemini-2.5-flash"},
            headers=_auth("op_alice"),
        )
        vault = rp_mod.load_vault("op_alice")
        assert vault["runtime"]["model_preferences"]["provider"] == "gemini"


# ===========================================================================
# D. POST validation
# ===========================================================================
class TestPostValidation:
    def test_unknown_provider_returns_400(self, client):
        r = client.post(
            "/operator/model_preferences",
            json={"provider": "perplexity", "model": "sonar-pro"},
            headers=_auth("op_alice"),
        )
        assert r.status_code == 400

    def test_unsupported_model_returns_400(self, client):
        # Valid provider, but model doesn't exist in SUPPORTED_MODELS.
        r = client.post(
            "/operator/model_preferences",
            json={"provider": "anthropic", "model": "claude-99-omega"},
            headers=_auth("op_alice"),
        )
        assert r.status_code == 400

    def test_missing_model_returns_422(self, client):
        # Pydantic body validation — missing required field.
        r = client.post(
            "/operator/model_preferences",
            json={"provider": "anthropic"},
            headers=_auth("op_alice"),
        )
        assert r.status_code == 422

    def test_missing_provider_returns_422(self, client):
        r = client.post(
            "/operator/model_preferences",
            json={"model": "claude-haiku-4-5-20251001"},
            headers=_auth("op_alice"),
        )
        assert r.status_code == 422


# ===========================================================================
# E. Per-operator scoping
# ===========================================================================
class TestPerOperatorScoping:
    def test_alice_pref_does_not_affect_bob(self, client):
        # Alice sets preference.
        client.post(
            "/operator/model_preferences",
            json={"provider": "openai", "model": "gpt-5.4"},
            headers=_auth("op_alice"),
        )
        # Bob's GET still returns default chain.
        bob = client.get(
            "/operator/model_preferences", headers=_auth("op_bob"),
        ).json()
        assert bob["source"]   == "default"
        # And the underlying vault store didn't write to op_bob.
        assert rp_mod.load_vault("op_bob") is None

    def test_two_operators_independent_preferences(self, client):
        client.post(
            "/operator/model_preferences",
            json={"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
            headers=_auth("op_alice"),
        )
        client.post(
            "/operator/model_preferences",
            json={"provider": "openai", "model": "gpt-5.4"},
            headers=_auth("op_bob"),
        )
        alice = client.get(
            "/operator/model_preferences", headers=_auth("op_alice"),
        ).json()
        bob = client.get(
            "/operator/model_preferences", headers=_auth("op_bob"),
        ).json()
        assert alice["provider"] == "anthropic"
        assert bob["provider"]   == "openai"
