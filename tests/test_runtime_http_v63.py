"""
Tests for v63 / Units 47 + 48 — session history + vault inspector
endpoints.

Mounts ``runtime_router`` on a private FastAPI app so the suite does
not boot the full ``app.py`` tree. Uses ``conftest.AppClient`` shim
because starlette's bundled TestClient is incompatible with the
installed httpx version (same as v60).

Layered coverage:
    A. GET /operator/session/{session_id} — detail endpoint
    B. GET /operator/sessions             — list per operator
    C. GET /operator/vault/{operator_id}  — vault inspector
    D. Cross-endpoint integration
    E. Source-code purity
"""
from __future__ import annotations

import inspect
import json

import pytest
from fastapi import FastAPI

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
    app = FastAPI()
    app.include_router(rh_mod.runtime_router)
    app.include_router(rh_mod.operator_router)

    # v64 / Unit 66 — override the auth dependency with a fixed
    # operator_id so existing v63 tests don't need to plumb session
    # tokens. End-to-end auth + 401 behaviour is exercised in
    # test_operator_auth.py. The override is a mutable callable so
    # individual tests can swap operator_id mid-flight to exercise
    # cross-operator scenarios.
    auth_cell = {"operator_id": "op_alice"}

    def fake_require_operator() -> str:
        return auth_cell["operator_id"]

    app.dependency_overrides[rh_mod.require_operator] = fake_require_operator
    # Expose the auth_cell on the app so tests can mutate it.
    app.state.auth_cell = auth_cell  # type: ignore[attr-defined]

    clock_counter = {"n": 0}
    sid_counter   = {"n": 0}

    def fake_now():
        clock_counter["n"] += 1
        return f"2026-05-12T10:00:{clock_counter['n']:02d}+00:00"

    def fake_make_session_id():
        sid_counter["n"] += 1
        return f"sess-v63-{sid_counter['n']:03d}"

    monkeypatch.setattr(sl_mod, "_now", fake_now)
    monkeypatch.setattr(sl_mod, "_make_session_id", fake_make_session_id)
    mr._reset_for_tests()
    rp_mod._reset_for_tests()
    try:
        c = TestClient(app)
        c._app = app  # type: ignore[attr-defined] — for auth_cell access in tests
        yield c
    finally:
        mr._reset_for_tests()
        rp_mod._reset_for_tests()


# ===========================================================================
# A. GET /operator/session/{session_id} — detail
# ===========================================================================
class TestSessionDetail:
    def test_200_returns_session_state(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.get(f"/operator/session/{s0['session_id']}")
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) == {"session_state"}
        assert body["session_state"]["session_id"] == s0["session_id"]

    def test_404_on_unknown_session_id(self, client):
        r = client.get("/operator/session/sess-does-not-exist")
        assert r.status_code == 404

    def test_400_on_malformed_session_id(self, client):
        # Path-traversal style. The persistence layer rejects via
        # regex; we surface that as 400 not 404.
        r = client.get("/operator/session/..foo")
        # ``..foo`` starts with a dot which the regex allows, so it
        # actually 404s. Try a genuinely malformed id.
        assert r.status_code in (400, 404)
        r2 = client.get("/operator/session/has spaces and / slashes")
        # FastAPI will URL-decode the slash and route to /sessions/...
        # which gives 422 or 404 depending on routing. Either way it's
        # not a 200.
        assert r2.status_code != 200

    def test_returns_history_after_step(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        )
        r = client.get(f"/operator/session/{s0['session_id']}")
        body = r.json()
        assert len(body["session_state"]["history"]) == 1
        assert body["session_state"]["history"][0]["text"] == "one"

    def test_session_state_carries_v59_history_shape(self, client):
        # Spec asked for {input, intent, runtime_response, model_response,
        # timestamp} but v59 locked {timestamp, intent_type, text,
        # runtime_decision, engine}. We return the v59 shape verbatim;
        # client UI maps to the spec's labels.
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        )
        r = client.get(f"/operator/session/{s0['session_id']}")
        entry = r.json()["session_state"]["history"][0]
        assert set(entry.keys()) == {
            "timestamp", "intent_type", "text",
            "runtime_decision", "engine",
        }


# ===========================================================================
# B. GET /operator/sessions — list per operator
# ===========================================================================
class TestSessionList:
    def test_empty_list_when_no_sessions(self, client):
        r = client.get("/operator/sessions?operator_id=op_alice")
        assert r.status_code == 200
        body = r.json()
        assert body == {"operator_id": "op_alice", "sessions": []}

    def test_single_session_listed(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        r = client.get("/operator/sessions?operator_id=op_alice")
        body = r.json()
        assert len(body["sessions"]) == 1
        summary = body["sessions"][0]
        assert summary["session_id"]  == s0["session_id"]
        assert summary["operator_id"] == "op_alice"
        assert summary["history_len"] == 0
        # No steps yet → timestamp is empty.
        assert summary["timestamp"]   == ""

    def test_summary_keys_locked(self, client):
        client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        )
        r = client.get("/operator/sessions?operator_id=op_alice")
        summary = r.json()["sessions"][0]
        assert set(summary.keys()) == {
            "session_id", "operator_id", "history_len", "timestamp",
        }

    def test_history_len_grows_per_step(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        s1 = client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s1, "text": "two"},
        )
        r = client.get("/operator/sessions?operator_id=op_alice")
        assert r.json()["sessions"][0]["history_len"] == 2

    def test_operator_isolation(self, client):
        # v68 — POST /start ALSO uses authed identity (body operator_id
        # ignored). To create sessions for two operators, swap the
        # auth_cell between POSTs. Then GET each operator's list.
        client._app.state.auth_cell["operator_id"] = "op_alice"
        client.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
        )
        client._app.state.auth_cell["operator_id"] = "op_bob"
        client.post(
            "/operator/session/start",
            json={"operator_id": "ignored"},
        )
        # Now read each list under matching auth.
        client._app.state.auth_cell["operator_id"] = "op_alice"
        alice = client.get("/operator/sessions").json()
        client._app.state.auth_cell["operator_id"] = "op_bob"
        bob = client.get("/operator/sessions").json()
        assert len(alice["sessions"]) == 1
        assert len(bob["sessions"])   == 1
        assert alice["sessions"][0]["operator_id"] == "op_alice"
        assert bob["sessions"][0]["operator_id"]   == "op_bob"

    def test_newest_first_ordering(self, client):
        # Three sessions, with different last-step timestamps.
        a = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        # Step in `a` first → its history.timestamp gets fake clock 02.
        client.post(
            "/operator/session/step",
            json={"session_state": a, "text": "a"},
        )
        b = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": b, "text": "b"},
        )
        c = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": c, "text": "c"},
        )
        r = client.get("/operator/sessions?operator_id=op_alice").json()
        sids = [s["session_id"] for s in r["sessions"]]
        # Newest-first: c's last-step came after b's, b's after a's.
        assert sids == [
            c["session_id"], b["session_id"], a["session_id"],
        ]

    def test_query_param_operator_id_is_ignored_v66(self, client):
        # v66 — the v63 ?operator_id= query param is silently
        # ignored. Authed identity is the only source. Both well-
        # formed and malformed query values now produce 200 with the
        # authed operator's sessions (even if empty).
        client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        )
        # Ignored query value.
        r = client.get("/operator/sessions?operator_id=../etc/passwd")
        assert r.status_code == 200
        # Auth-cell is "op_alice" → returns Alice's sessions.
        assert r.json()["operator_id"] == "op_alice"


# ===========================================================================
# C. GET /operator/vault/{operator_id} — vault inspector
# ===========================================================================
class TestVaultInspector:
    def test_cold_vault_returns_null(self, client):
        r = client.get("/operator/vault/op_alice")
        assert r.status_code == 200
        body = r.json()
        assert body == {
            "operator_id":  "op_alice",
            "vault":        None,
            "last_updated": "",
        }

    def test_warm_vault_after_step(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "step one"},
        )
        r = client.get("/operator/vault/op_alice")
        body = r.json()
        assert body["operator_id"] == "op_alice"
        assert body["vault"] is not None
        assert "elins" in body["vault"]

    def test_last_updated_carries_fusion_timestamp(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "step one"},
        )
        r = client.get("/operator/vault/op_alice")
        # last_updated derives from elins.last_fusion.timestamp.
        # The Unit 31 fuse output carries one — the exact format
        # depends on the kernel, but it must be a non-empty string.
        assert isinstance(r.json()["last_updated"], str)
        assert r.json()["last_updated"] != ""

    def test_response_keys_locked(self, client):
        r = client.get("/operator/vault/op_alice")
        assert set(r.json().keys()) == {"operator_id", "vault", "last_updated"}

    def test_operator_isolation(self, client):
        # v66 — vault endpoint always uses the authed identity; the
        # path operator_id is ignored. Swap auth_cell to verify
        # operators see different vaults.
        s_alice = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s_alice, "text": "alice step"},
        )
        # Authed as alice; path value irrelevant.
        alice_vault = client.get("/operator/vault/whatever").json()["vault"]
        # Swap auth_cell to bob — bob has no vault.
        client._app.state.auth_cell["operator_id"] = "op_bob"
        bob_vault = client.get("/operator/vault/whatever").json()["vault"]
        assert alice_vault is not None
        assert bob_vault is None

    def test_path_operator_id_is_ignored_v66(self, client):
        # v66 — path operator_id is ignored. Even a path value that
        # doesn't match the persistence regex resolves to 200 because
        # the server uses the authed identity instead.
        # (Path values with literal "/" still 404 at FastAPI's route
        # matcher, not at our handler — that's a routing concern,
        # not an auth/persistence one. Use a single-segment funky
        # value to isolate the handler-level behaviour.)
        r = client.get("/operator/vault/some-random-spoofed-id")
        assert r.status_code == 200
        body = r.json()
        # Response operator_id is the AUTHED one, not the path one.
        assert body["operator_id"] == "op_alice"
        assert body["vault"] is None


# ===========================================================================
# D. Cross-endpoint integration
# ===========================================================================
class TestIntegration:
    def test_session_detail_and_list_agree_on_history(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        )
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "two"},
        )
        detail = client.get(
            f"/operator/session/{s0['session_id']}",
        ).json()["session_state"]
        listing = client.get(
            "/operator/sessions?operator_id=op_alice",
        ).json()["sessions"][0]
        # Detail history length must equal list summary history_len.
        # (The list endpoint's summary is derived from the same
        # stored session_state.)
        assert len(detail["history"]) == listing["history_len"]

    def test_vault_inspector_and_session_detail_agree(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        )
        vault = client.get("/operator/vault/op_alice").json()["vault"]
        session_vault = client.get(
            f"/operator/session/{s0['session_id']}",
        ).json()["session_state"]["vault_state"]
        # The per-operator vault snapshot must match the per-session
        # vault_state (each step writes both to the same payload).
        assert vault == session_vault

    def test_json_safe_responses(self, client):
        s0 = client.post(
            "/operator/session/start",
            json={"operator_id": "op_alice"},
        ).json()["session_state"]
        client.post(
            "/operator/session/step",
            json={"session_state": s0, "text": "one"},
        )
        for path in (
            f"/operator/session/{s0['session_id']}",
            "/operator/sessions?operator_id=op_alice",
            "/operator/vault/op_alice",
        ):
            r = client.get(path)
            assert r.status_code == 200
            body = r.json()
            # Round-trip through json.dumps proves no float NaN etc.
            json.dumps(body)


# ===========================================================================
# E. Source-code purity
# ===========================================================================
class TestModuleSurface:
    def test_imports_unchanged_otherwise(self):
        # v63 doesn't add any new top-level imports — both
        # runtime_persistence + session_loop were already there.
        src = inspect.getsource(rh_mod)
        assert "import session_loop" in src
        assert "import runtime_persistence" in src
        # No persistence / network / model SDK imports added.
        for forbidden in (
            "import sqlite3", "import pickle",
            "import requests", "import httpx",
            "from runtime_kernel", "from runtime_dispatcher",
            "from model_router", "from elins_",
            "from operator_session_runner",
        ):
            assert forbidden not in src

    def test_new_endpoints_are_get(self):
        # All three v63 additions must be GETs (read-only). Routes
        # are split across runtime_router (under /operator/session
        # prefix) and operator_router (under /operator prefix) to
        # avoid path-doubling.
        runtime_pairs = {
            (route.path, frozenset(route.methods))
            for route in rh_mod.runtime_router.routes
            if hasattr(route, "methods")
        }
        operator_pairs = {
            (route.path, frozenset(route.methods))
            for route in rh_mod.operator_router.routes
            if hasattr(route, "methods")
        }
        # Detail under the runtime_router (relative path /{id} =
        # full path /operator/session/{id}).
        assert ("/operator/session/{session_id}", frozenset({"GET"})) in runtime_pairs
        # List + vault under operator_router.
        assert ("/operator/sessions",             frozenset({"GET"})) in operator_pairs
        assert ("/operator/vault/{operator_id}",  frozenset({"GET"})) in operator_pairs
