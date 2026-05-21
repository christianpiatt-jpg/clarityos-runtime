"""
Tests for Unit 41 — HTTP runtime surface.

Mounts ``runtime_router`` on a private FastAPI app so the suite does
not boot the full ``app.py`` tree. This proves the module is
side-effect free at import.

Layered coverage (target ~35 tests):
    A. /start endpoint — shape + status
    B. /start validation
    C. /step endpoint — shape + status
    D. /step validation
    E. Round-trip: start → step → step (vault + history continuity)
    F. Engine + decision propagation per intent_type
    G. Body validation (Pydantic 422 paths)
    H. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json

import pytest
from fastapi import FastAPI

# conftest.AppClient wraps httpx.ASGITransport because the bundled
# starlette TestClient is incompatible with the installed httpx
# version. Every other endpoint test in this repo uses the same shim.
from conftest import TestClient

import model_router as mr
import runtime_http as rh_mod
import runtime_persistence as rp_mod
import session_loop as sl_mod


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture
def client(monkeypatch):
    """Private FastAPI app with only the runtime router mounted —
    proves runtime_http imports cleanly without booting app.py.
    Pins the session_id factory + clock so tests are deterministic.
    Resets runtime_persistence between tests so v43 vault/session
    persistence does not leak across cases."""
    app = FastAPI()
    app.include_router(rh_mod.runtime_router)

    # v65 / Unit 68 — override require_operator with a fixed
    # operator_id so existing v60-v64 tests don't have to plumb auth
    # tokens. End-to-end auth + 401 behaviour is exercised in
    # test_operator_session_auth.py.
    app.dependency_overrides[rh_mod.require_operator] = lambda: "op_alice"

    counter = {"n": 0}

    def fake_now():
        counter["n"] += 1
        return f"2026-05-12T10:00:{counter['n']:02d}+00:00"

    def fake_make_session_id():
        return f"sess-http-{counter['n']:03d}"

    monkeypatch.setattr(sl_mod, "_now", fake_now)
    monkeypatch.setattr(sl_mod, "_make_session_id", fake_make_session_id)
    mr._reset_for_tests()
    rp_mod._reset_for_tests()
    try:
        yield TestClient(app)
    finally:
        mr._reset_for_tests()
        rp_mod._reset_for_tests()


# ===========================================================================
# A. /start — shape + status
# ===========================================================================
class TestStartShape:
    def test_200_status(self, client):
        r = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        )
        assert r.status_code == 200

    def test_response_envelope_keys(self, client):
        r = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        )
        assert set(r.json().keys()) == {"session_state"}

    def test_session_state_locked_keys(self, client):
        r = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        )
        state = r.json()["session_state"]
        assert set(state.keys()) == {
            "session_id", "operator_id", "vault_state", "history",
        }

    def test_authed_operator_id_in_response_v68(self, client):
        # v68 — body operator_id is server-ignored. The returned
        # session_state.operator_id is the AUTHED identity. Fixture
        # override returns "op_alice" regardless of what the body
        # claims; verify that.
        r = client.post(
            "/operator/session/start",
            json={"operator_id": "op_zed"},  # spoof attempt ignored
        )
        assert r.json()["session_state"]["operator_id"] == "op_alice"

    def test_vault_state_starts_empty(self, client):
        r = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        )
        assert r.json()["session_state"]["vault_state"] == {}

    def test_history_starts_empty(self, client):
        r = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        )
        assert r.json()["session_state"]["history"] == []


# ===========================================================================
# B. /start validation
# ===========================================================================
class TestStartValidation:
    def test_missing_operator_id_returns_422(self, client):
        r = client.post("/operator/session/start", json={})
        assert r.status_code == 422

    def test_non_string_operator_id_returns_422(self, client):
        r = client.post(
            "/operator/session/start",
            json={"operator_id": 42},
        )
        assert r.status_code == 422

    def test_empty_operator_id_no_longer_400_v68(self, client):
        # v68 — body operator_id is server-ignored. The empty-string
        # rejection from Unit 40 used to fire because body.operator_id
        # was passed straight through; under v68 the authed identity
        # is used instead, so an empty body operator_id is harmless.
        r = client.post(
            "/operator/session/start",
            json={"operator_id": ""},
        )
        assert r.status_code == 200
        assert r.json()["session_state"]["operator_id"] == "op_alice"


# ===========================================================================
# C. /step — shape + status
# ===========================================================================
class TestStepShape:
    def test_200_status(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={"session_state": s, "text": "do it"},
        )
        assert r.status_code == 200

    def test_response_envelope_keys(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={"session_state": s, "text": "do it"},
        )
        assert set(r.json().keys()) == {"session_state", "step_result"}

    def test_step_result_is_unit39_shape(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={"session_state": s, "text": "do it"},
        )
        assert set(r.json()["step_result"].keys()) == {
            "session_id", "operator_id", "timestamp",
            "runtime", "model", "vault_update",
        }

    def test_session_state_returned_has_appended_history(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={"session_state": s, "text": "do it"},
        )
        assert len(r.json()["session_state"]["history"]) == 1

    def test_default_intent_type_is_query(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={"session_state": s, "text": "do it"},
        )
        assert (
            r.json()["session_state"]["history"][0]["intent_type"]
            == "query"
        )


# ===========================================================================
# D. /step validation
# ===========================================================================
class TestStepValidation:
    def test_missing_session_state_returns_422(self, client):
        r = client.post(
            "/operator/session/step",
            json={"text": "do it"},
        )
        assert r.status_code == 422

    def test_missing_text_returns_422(self, client):
        r = client.post(
            "/operator/session/step",
            json={"session_state": {}, "text_typo": "do it"},
        )
        assert r.status_code == 422

    def test_unknown_intent_type_returns_400(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={
                "session_state": s,
                "text": "do it",
                "intent_type": "hallucinate",
            },
        )
        assert r.status_code == 400
        assert "intent_type" in r.json()["detail"]

    def test_malformed_session_state_returns_400(self, client):
        r = client.post(
            "/operator/session/step",
            json={
                "session_state": {"operator_id": "x"},   # missing required keys
                "text": "do it",
            },
        )
        assert r.status_code == 400

    def test_non_dict_session_state_returns_422(self, client):
        # Pydantic rejects non-dict at the body layer (422), before
        # session_loop ever sees it.
        r = client.post(
            "/operator/session/step",
            json={"session_state": [1, 2, 3], "text": "do it"},
        )
        assert r.status_code == 422


# ===========================================================================
# E. Round-trip: start → step → step (continuity)
# ===========================================================================
class TestRoundTrip:
    def test_two_steps_grow_fusion_history(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r1 = client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        ).json()
        r2 = client.post(
            "/operator/session/step",
            json={"session_state": r1["session_state"], "text": "two"},
        ).json()
        h1 = r1["session_state"]["vault_state"]["elins"]["fusion_history"]
        h2 = r2["session_state"]["vault_state"]["elins"]["fusion_history"]
        assert len(h1) == 1
        assert len(h2) == 2

    def test_history_carries_step_texts_in_order(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r1 = client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        ).json()
        r2 = client.post(
            "/operator/session/step",
            json={"session_state": r1["session_state"], "text": "two"},
        ).json()
        r3 = client.post(
            "/operator/session/step",
            json={"session_state": r2["session_state"], "text": "three"},
        ).json()
        texts = [e["text"] for e in r3["session_state"]["history"]]
        assert texts == ["one", "two", "three"]

    def test_session_id_preserved_across_steps(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r1 = client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        ).json()
        r2 = client.post(
            "/operator/session/step",
            json={"session_state": r1["session_state"], "text": "two"},
        ).json()
        assert r2["session_state"]["session_id"] == s0["session_id"]


# ===========================================================================
# F. Engine + decision propagation per intent_type
# ===========================================================================
class TestEnginePropagation:
    @pytest.mark.parametrize("intent_type,engine", [
        ("query",      "copilot"),
        ("plan",       "claude"),
        ("action",     "gemini"),
        ("diagnostic", "local"),
    ])
    def test_intent_routes_to_engine(self, client, intent_type, engine):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={
                "session_state": s,
                "text": "do it",
                "intent_type": intent_type,
            },
        ).json()
        assert r["session_state"]["history"][0]["engine"] == engine

    def test_runtime_decision_in_history(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={"session_state": s, "text": "do it"},
        ).json()
        decision = r["session_state"]["history"][0]["runtime_decision"]
        assert decision in {"allow", "warn", "block"}

    def test_model_response_present(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={"session_state": s, "text": "do it"},
        ).json()
        assert "text" in r["step_result"]["model"]["response"]


# ===========================================================================
# G. JSON round-trip / payload safety
# ===========================================================================
class TestPayloadSafety:
    def test_start_response_is_json(self, client):
        r = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        )
        assert r.headers["content-type"].startswith("application/json")
        json.loads(r.content)  # no-raise

    def test_step_response_is_json(self, client):
        s = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.post(
            "/operator/session/step",
            json={"session_state": s, "text": "do it"},
        )
        assert r.headers["content-type"].startswith("application/json")
        json.loads(r.content)  # no-raise


# ===========================================================================
# H. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_runtime_router_exported(self):
        assert hasattr(rh_mod, "runtime_router")
        # APIRouter, not the full FastAPI app.
        from fastapi import APIRouter
        assert isinstance(rh_mod.runtime_router, APIRouter)

    def test_router_prefix(self):
        assert rh_mod.runtime_router.prefix == "/operator/session"

    def test_imports_only_session_loop_persistence_and_fastapi(self):
        # v61 / Unit 43 added runtime_persistence so /start can honour
        # ``resume=true`` by looking up a stored session. Otherwise
        # the import lock is unchanged: no direct knowledge of layers
        # below Unit 40.
        src = inspect.getsource(rh_mod)
        assert "import session_loop" in src
        assert "import runtime_persistence" in src
        assert "from fastapi" in src
        for forbidden in (
            "from runtime_kernel",
            "from runtime_dispatcher",
            "from model_router",
            "from elins_",
            "from operator_session_runner",  # Unit 39 leaks through Unit 40
        ):
            assert forbidden not in src

    def test_no_persistence_or_network_imports(self):
        src = inspect.getsource(rh_mod)
        for forbidden in (
            "import sqlite3", "import pickle",
            "import requests", "import httpx",
            "open(", "subprocess",
        ):
            assert forbidden not in src

    def test_no_app_construction_at_import(self):
        # Importing the module must not have side effects beyond
        # registering the router. Re-importing should be a no-op.
        import importlib
        importlib.reload(rh_mod)
        from fastapi import APIRouter
        assert isinstance(rh_mod.runtime_router, APIRouter)
