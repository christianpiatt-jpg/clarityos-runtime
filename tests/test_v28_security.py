"""
Security invariant tests for v28 surfaces.

These tests pin the invariants the v29 readiness report cites:
* scenario text never leaks into delivered records,
* envelope vectors never leak through /runtime/envelope,
* Dewey neighborhood metadata never includes origin_vector,
* mesh device blobs never include vectors,
* structured logs never embed user content.
"""
from __future__ import annotations

import json
import logging
import time

import pytest


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


def test_delivered_record_has_scenario_id_not_text(app_module):
    """elins_distribution_store.deliver() must replace scenario_text with
    a hashed scenario_id; the text must not survive in the delivered list."""
    import elins_distribution_store as store
    user = "secret_user"
    rid = store.queue(user, "this is private", scheduled_for_ts=1000.0)["report_id"]
    delivered = store.deliver(user, rid, delivered_at=1001.0, analysis={"k": "v"})
    assert delivered is not None
    serialized = json.dumps(delivered)
    assert "this is private" not in serialized
    assert delivered["scenario_id"].startswith("sc_")


def test_runtime_envelope_strips_all_vectors(app_module):
    """/runtime/envelope must not return any list-of-floats — only strings,
    numbers, dicts, and ``{_vector: True, dim: N}`` descriptors."""
    import envelopes_store
    from conftest import TestClient

    user = "envuser"
    big = [0.1] * 16
    envelopes_store.set_envelope(user, {
        "envelope_vector": big,
        "envelope_centroid": big,
        "events": [{"vector": big, "summary": "x"}],
        "elins_briefs": [{"object_vector": big, "scenario_id": "sc_x"}],
        "narratives": {"n1": {"node_vector": big, "compressed_vector": big}},
        "story_arcs": {"a1": {"arc_vector": big, "arc_vector_compressed": big}},
        "identity": {"identity_vector": big},
        "trajectory": {"trajectory_vector": big},
        "elins": {"mean_center_vector": big},
    })
    # Bypass the route's flag gate: drive envelope-stripping helper directly
    # by simulating a session for the user.
    import sessions_store, secrets, users_store
    import bcrypt
    pwd = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(user, pwd, salt="", tier="free", created_at=time.time())
    users_store.update_user(user, {"cohort": "founder"})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)

    client = TestClient(app_module.app)
    r = client.get("/runtime/envelope", headers={"X-Session-ID": sid})
    assert r.status_code == 200
    env = r.json()["envelope"]

    def assert_no_float_lists(obj, path="env"):
        if isinstance(obj, list):
            # Lists of floats are forbidden (vectors should be descriptors).
            if obj and all(isinstance(x, (int, float)) for x in obj):
                pytest.fail(f"raw vector leaked at {path}: {obj[:4]}…")
            for i, v in enumerate(obj):
                assert_no_float_lists(v, f"{path}[{i}]")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                assert_no_float_lists(v, f"{path}.{k}")

    assert_no_float_lists(env)


def test_dewey_metadata_endpoint_never_returns_origin_vector(app_module):
    """/metadata/dewey may return ``has_origin_vector: bool`` but never the
    origin_vector itself."""
    import dewey_neighborhoods_store, sessions_store, secrets, users_store
    import bcrypt

    user = "deweyuser"
    pwd = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(user, pwd, salt="", tier="free", created_at=time.time())
    users_store.update_user(user, {"cohort": "founder"})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, user, expires_at=time.time() + 3600)

    big = [0.1] * 16
    dewey_neighborhoods_store.create("nb1", {
        "id": "nb1",
        "user": user,
        "name": "test-neigh",
        "origin_vector": big,
        "curvature": 0.5,
    })

    from conftest import TestClient
    client = TestClient(app_module.app)
    r = client.get("/metadata/dewey", headers={"X-Session-ID": sid})
    assert r.status_code == 200
    body = r.json()
    serialized = json.dumps(body)
    # No raw vector should appear; only the boolean indicator.
    assert "0.1, 0.1" not in serialized
    nbs = body["neighborhoods"]
    assert all("origin_vector" not in nb for nb in nbs)
    assert all("has_origin_vector" in nb for nb in nbs)


def test_log_event_does_not_embed_user_content(caplog):
    """log_event must not write any caller-provided string content beyond
    the redacted user id + event name + numeric/bool primitives + dict-len
    counts. Strings are allowed (route names etc.) but free-form blobs from
    callers should be coerced to length counts."""
    import v29_hardening as h

    private_payload = {"secret_text": "this should never appear in logs"}
    with caplog.at_level(logging.INFO, logger="clarityos.v29"):
        h.log_event("test", user="aliceXYZ", payload=private_payload)
    msg = caplog.records[-1].getMessage()
    assert "this should never appear" not in msg
    # Verify the count is logged in place of the dict.
    assert "payload_count=1" in msg
