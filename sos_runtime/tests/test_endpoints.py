"""
SOS Runtime — endpoint tests.

Coverage:
    A. /health — public, returns service + version metadata
    B. /status — authenticated introspection
    C. /engage — chain: session upsert + event append + LLM call + state touch
    D. /elins — deterministic stub, event append, TODO marker present
    E. /continuity — markers merge into state.continuity
    F. /state — read vs write paths; last_transition behavior
    G. Cross-endpoint persistence (session shared across /engage + /state)
    H. Validation: missing / empty fields rejected
    I. CORS origins respected
    J. Backend isolation: in-memory store cleared between tests
"""
from __future__ import annotations

import pytest


# ===========================================================================
# A. /health
# ===========================================================================
class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_payload_shape(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"
        assert body["service"] == "os-runtime"
        assert isinstance(body["version"], str)
        assert body["version"].startswith("SOS_V")

    def test_health_does_not_require_auth(self, client):
        # No Authorization header. Insecure-mode bypass would pass it
        # anyway, but /health is intentionally public for liveness
        # probes — independent of auth mode.
        r = client.get("/health")
        assert r.status_code == 200


# ===========================================================================
# B. /status
# ===========================================================================
class TestStatus:
    def test_status_returns_200_in_insecure_mode(self, client):
        r = client.get("/status")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["service"] == "os-runtime"
        assert body["auth"]["mode"] == "insecure"
        assert body["llm"]["mode"] == "fake"

    def test_status_caller_email_is_insecure_marker(self, client):
        body = client.get("/status").json()
        assert body["caller"]["mode"] == "insecure"
        assert "@" in (body["caller"]["email"] or "")


# ===========================================================================
# C. /engage
# ===========================================================================
class TestEngage:
    def _body(self, **kwargs):
        defaults = {
            "user_id":    "alice",
            "session_id": "sess-1",
            "message":    "hello SOS",
            "context":    {"page": "cockpit"},
        }
        defaults.update(kwargs)
        return defaults

    def test_engage_returns_reply(self, client):
        r = client.post("/engage", json=self._body())
        assert r.status_code == 200
        body = r.json()
        assert "reply" in body
        assert body["reply"]   # non-empty echo
        assert isinstance(body["reply"], str)

    def test_engage_response_envelope_shape(self, client):
        body = client.post("/engage", json=self._body()).json()
        assert set(body.keys()) == {"reply", "elins", "state", "continuity"}
        assert isinstance(body["elins"], dict)
        assert isinstance(body["state"], dict)
        assert isinstance(body["continuity"], dict)

    def test_engage_state_user_id_matches_request(self, client):
        body = client.post("/engage", json=self._body()).json()
        assert body["state"]["user_id"] == "alice"

    def test_engage_continuity_includes_last_engage_ts(self, client):
        body = client.post("/engage", json=self._body()).json()
        assert "last_engage_ts_ms" in body["continuity"]
        assert isinstance(body["continuity"]["last_engage_ts_ms"], int)

    def test_engage_persists_session(self, client):
        client.post("/engage", json=self._body())
        from sos_runtime.firestore_store import get_store
        store = get_store()
        sess = store.get_session("sess-1")
        assert sess is not None
        assert sess["user_id"] == "alice"
        assert sess["metadata"]["last_endpoint"] == "engage"

    def test_engage_appends_event(self, client):
        client.post("/engage", json=self._body())
        from sos_runtime.firestore_store import get_store
        events = get_store().list_events_for_session("sess-1")
        assert len(events) >= 1
        types = [e["type"] for e in events]
        assert "engage" in types

    def test_engage_event_payload_carries_message(self, client):
        client.post("/engage", json=self._body(message="ping"))
        from sos_runtime.firestore_store import get_store
        events = get_store().list_events_for_session("sess-1")
        engage_events = [e for e in events if e["type"] == "engage"]
        assert any(e["payload"].get("message") == "ping" for e in engage_events)

    def test_engage_event_records_model_response(self, client):
        client.post("/engage", json=self._body())
        from sos_runtime.firestore_store import get_store
        events = get_store().list_events_for_session("sess-1")
        engage_events = [e for e in events if e["type"] == "engage"]
        # The first engage event gets the model response mutated in.
        assert any(
            e.get("model_response") and "reply" in (e["model_response"] or {})
            for e in engage_events
        )

    def test_engage_does_not_transition_state(self, client):
        body = client.post("/engage", json=self._body()).json()
        # /engage explicitly touches continuity but doesn't transition
        # current_state — last_transition stays None until /state
        # writes a new current_state.
        assert body["state"]["last_transition"] is None
        assert body["state"]["current_state"] is None


# ===========================================================================
# D. /elins
# ===========================================================================
class TestElins:
    def _body(self, **kwargs):
        defaults = {
            "user_id":    "alice",
            "session_id": "sess-elins",
            "signal":     {"weight": 0.7, "tag": "operator_input"},
        }
        defaults.update(kwargs)
        return defaults

    def test_elins_returns_ok_true(self, client):
        body = client.post("/elins", json=self._body()).json()
        assert body["ok"] is True

    def test_elins_returns_normalized_signal(self, client):
        body = client.post("/elins", json=self._body()).json()
        norm = body["normalized"]
        assert norm["user_id"] == "alice"
        assert norm["session_id"] == "sess-elins"
        assert norm["signal"] == {"weight": 0.7, "tag": "operator_input"}
        assert "received_at_ms" in norm
        assert isinstance(norm["received_at_ms"], int)

    def test_elins_todo_marker_present(self, client):
        body = client.post("/elins", json=self._body()).json()
        assert "todo" in body
        assert "V34" in body["todo"]   # kernel-wire hint

    def test_elins_appends_event(self, client):
        client.post("/elins", json=self._body())
        from sos_runtime.firestore_store import get_store
        events = get_store().list_events_for_session("sess-elins")
        assert any(e["type"] == "elins" for e in events)


# ===========================================================================
# E. /continuity
# ===========================================================================
class TestContinuity:
    def _body(self, **kwargs):
        defaults = {
            "user_id":    "alice",
            "session_id": "sess-cont",
            "markers":    {"timeline_anchor": "T+0", "phase": "orientation"},
        }
        defaults.update(kwargs)
        return defaults

    def test_continuity_returns_ack(self, client):
        body = client.post("/continuity", json=self._body()).json()
        assert body["ack"] is True

    def test_continuity_merges_markers_into_state(self, client):
        client.post("/continuity", json=self._body())
        from sos_runtime.firestore_store import get_store
        state = get_store().get_state("alice")
        assert state is not None
        assert state["continuity"]["timeline_anchor"] == "T+0"
        assert state["continuity"]["phase"] == "orientation"

    def test_continuity_does_not_transition_current_state(self, client):
        body = client.post("/continuity", json=self._body()).json()
        # Per spec: continuity writes into the continuity map, not
        # current_state. last_transition should stay None for the
        # operator's first continuity write.
        from sos_runtime.firestore_store import get_store
        state = get_store().get_state("alice")
        assert state["current_state"] is None
        assert state["last_transition"] is None

    def test_continuity_appends_event(self, client):
        client.post("/continuity", json=self._body())
        from sos_runtime.firestore_store import get_store
        events = get_store().list_events_for_user("alice")
        assert any(e["type"] == "continuity" for e in events)


# ===========================================================================
# F. /state — read vs write
# ===========================================================================
class TestState:
    def test_state_read_with_no_prior_writes_returns_null_envelope(self, client):
        body = client.post("/state", json={
            "user_id": "alice", "session_id": "sess-state",
        }).json()
        assert body["user_id"] == "alice"
        assert body["current_state"] is None
        assert body["continuity"] == {}
        assert body["last_transition"] is None

    def test_state_write_sets_current_state(self, client):
        body = client.post("/state", json={
            "user_id":       "alice",
            "session_id":    "sess-state",
            "current_state": "interpretation",
        }).json()
        assert body["current_state"] == "interpretation"
        assert isinstance(body["last_transition"], int)

    def test_state_write_appends_event(self, client):
        client.post("/state", json={
            "user_id":       "alice",
            "session_id":    "sess-state",
            "current_state": "orientation",
        })
        from sos_runtime.firestore_store import get_store
        events = get_store().list_events_for_user("alice")
        assert any(
            e["type"] == "state"
            and e["payload"].get("current_state") == "orientation"
            for e in events
        )

    def test_state_read_does_not_append_event(self, client):
        # Establish a prior write, then read; the read should NOT
        # add a second event.
        client.post("/state", json={
            "user_id":       "alice",
            "session_id":    "sess-state",
            "current_state": "orientation",
        })
        from sos_runtime.firestore_store import get_store
        n_before = len([
            e for e in get_store().list_events_for_user("alice")
            if e["type"] == "state"
        ])
        client.post("/state", json={
            "user_id": "alice", "session_id": "sess-state",
        })
        n_after = len([
            e for e in get_store().list_events_for_user("alice")
            if e["type"] == "state"
        ])
        assert n_after == n_before


# ===========================================================================
# G. Cross-endpoint persistence
# ===========================================================================
class TestCrossEndpoint:
    def test_engage_then_state_read_sees_continuity_from_engage(self, client):
        client.post("/engage", json={
            "user_id": "bob", "session_id": "sess-cross",
            "message": "hi", "context": {},
        })
        body = client.post("/state", json={
            "user_id": "bob", "session_id": "sess-cross",
        }).json()
        # /engage wrote last_engage_ts_ms into continuity; /state read
        # must see it.
        assert "last_engage_ts_ms" in body["continuity"]

    def test_two_users_isolated(self, client):
        client.post("/state", json={
            "user_id": "alice", "session_id": "s-a",
            "current_state": "orientation",
        })
        client.post("/state", json={
            "user_id": "bob", "session_id": "s-b",
            "current_state": "interpretation",
        })
        alice = client.post("/state", json={
            "user_id": "alice", "session_id": "s-a",
        }).json()
        bob = client.post("/state", json={
            "user_id": "bob", "session_id": "s-b",
        }).json()
        assert alice["current_state"] == "orientation"
        assert bob["current_state"]   == "interpretation"


# ===========================================================================
# H. Validation
# ===========================================================================
class TestValidation:
    def test_engage_missing_message_422(self, client):
        r = client.post("/engage", json={
            "user_id": "alice", "session_id": "s1",
        })
        assert r.status_code == 422

    def test_engage_empty_message_422(self, client):
        r = client.post("/engage", json={
            "user_id": "alice", "session_id": "s1", "message": "",
        })
        assert r.status_code == 422

    def test_engage_missing_user_id_422(self, client):
        r = client.post("/engage", json={
            "session_id": "s1", "message": "hi", "context": {},
        })
        assert r.status_code == 422

    def test_elins_accepts_empty_signal(self, client):
        # Empty signal is valid — operator may submit only the envelope.
        r = client.post("/elins", json={
            "user_id": "alice", "session_id": "s1",
        })
        assert r.status_code == 200

    def test_continuity_accepts_empty_markers(self, client):
        # Same convention: empty markers is valid.
        r = client.post("/continuity", json={
            "user_id": "alice", "session_id": "s1",
        })
        assert r.status_code == 200


# ===========================================================================
# I. CORS
# ===========================================================================
class TestCors:
    def test_options_preflight_allowed_for_pro_mediations(self, client):
        r = client.options(
            "/engage",
            headers={
                "Origin": "https://pro-mediations.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,authorization",
            },
        )
        # FastAPI's CORSMiddleware returns 200 for allowed preflight.
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") in (
            "https://pro-mediations.com", "*",
        )


# ===========================================================================
# J. Backend isolation
# ===========================================================================
class TestBackendIsolation:
    def test_store_is_cleared_between_tests_part_1(self, client):
        # Establish state in test 1.
        client.post("/engage", json={
            "user_id": "alice", "session_id": "iso-1",
            "message": "first", "context": {},
        })
        from sos_runtime.firestore_store import get_store
        assert get_store().get_session("iso-1") is not None

    def test_store_is_cleared_between_tests_part_2(self, client):
        # Same fixture name — but the autouse fixture in conftest.py
        # reset the store. Session iso-1 must be gone.
        from sos_runtime.firestore_store import get_store
        assert get_store().get_session("iso-1") is None
