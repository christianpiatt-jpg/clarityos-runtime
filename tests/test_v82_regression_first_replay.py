"""
Tests for V82 — packet history + replay.

Coverage:
    A. /packet persists original packet under regression_packets.{cid}
    B. /packet first-packet-wins (not overwritten by subsequent calls
       for the same chain_id — only possible via /replay though)
    C. Failed /packet does NOT persist a packet
    D. /replay creates a new chain with a new chain_id
    E. /replay requires an existing stored packet (404)
    F. /replay respects per-user partitioning
    G. /replay emits regression_chain_started + regression_chain_layer_updated
    H. /replay does not alter the original chain
    I. /replay seeded layer matches /packet seed policy
    J. /replay auth-gated (401)
    K. /replay-of-replay also persists the packet for the new chain
    L. Routes + manifest + /health 4.22
"""
from __future__ import annotations

import secrets
import time

import pytest


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    from conftest import TestClient
    return TestClient(app_module.app)


def _make_user(username, cohort="founder"):
    import bcrypt
    import sessions_store
    import users_store
    pwd_hash = bcrypt.hashpw(b"x", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    if cohort:
        users_store.update_user(username, {"cohort": cohort})
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(
        sid, username, expires_at=time.time() + 3600,
    )
    return username, sid


def _auth(sid):
    return {"X-Session-ID": sid}


def _canonical_packet(
    *,
    regression_required: bool = True,
    layers: int = 2,
    operator_intent: str = "Identify root cause of rendering failure.",
) -> dict:
    skeleton = []
    for i in range(layers):
        skeleton.append({
            "layer": i + 1,
            "name": f"Layer{i+1}_name",
            "question": f"Layer{i+1}_question",
            "location": f"Layer{i+1}_location",
            "goal": f"Layer{i+1}_goal",
        })
    return {
        "EL": 2, "INS": 3, "ratio": "0.67",
        "el_signals": ["something is wrong"],
        "ins_signals": ["page", "scaffold"],
        "classification": "structure-dominant",
        "operator_intent": operator_intent,
        "regression_required": regression_required,
        "regression_chain": skeleton if regression_required else [],
        "recommended_system_action": "Pause and request operator verification.",
    }


# ===========================================================================
# A/B/C. Packet persistence under /packet
# ===========================================================================
class TestPacketPersistence:
    def test_packet_persists_original_under_namespace(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()}, headers=_auth(sid),
        )
        chain_id = r.json()["chain_id"]
        # Stored under regression_packets.{chain_id} for that user.
        stored = memory_vault.vault_get(
            user, f"regression_packets.{chain_id}",
        )
        assert stored is not None
        assert stored["classification"] == "structure-dominant"
        assert stored["operator_intent"] == "Identify root cause of rendering failure."

    def test_packet_namespace_in_allowed_namespaces(self):
        import memory_vault
        assert "regression_packets" in memory_vault.ALLOWED_NAMESPACES

    def test_failed_packet_persists_nothing(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        bad_packet = _canonical_packet()
        del bad_packet["classification"]
        client.post(
            "/me/regression_first/packet",
            json={"packet": bad_packet}, headers=_auth(sid),
        )
        keys = memory_vault.vault_keys_for_user(user)
        assert not any(k.startswith("regression_packets.") for k in keys)

    def test_two_chains_persist_two_packets(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        r1 = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(operator_intent="first")},
            headers=_auth(sid),
        )
        r2 = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(operator_intent="second")},
            headers=_auth(sid),
        )
        c1 = r1.json()["chain_id"]
        c2 = r2.json()["chain_id"]
        p1 = memory_vault.vault_get(user, f"regression_packets.{c1}")
        p2 = memory_vault.vault_get(user, f"regression_packets.{c2}")
        assert p1["operator_intent"] == "first"
        assert p2["operator_intent"] == "second"


# ===========================================================================
# D-I. /replay endpoint
# ===========================================================================
class TestReplay:
    def test_creates_new_chain_with_new_id(self, client):
        _, sid = _make_user("alice")
        original_id = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()}, headers=_auth(sid),
        ).json()["chain_id"]
        r = client.post(
            "/me/regression_first/replay",
            json={"chain_id": original_id}, headers=_auth(sid),
        )
        assert r.status_code == 200
        new_chain = r.json()
        assert new_chain["chain_id"] != original_id

    def test_404_when_no_stored_packet(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/replay",
            json={"chain_id": "ghost"}, headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_404_for_chain_created_manually_no_packet(self, client):
        """A chain created via /start (not /packet) has no stored
        packet → replay 404s. Continuity invariant: /replay is the
        packet-driven path; manual chains have no original to replay."""
        _, sid = _make_user("alice")
        manual_id = client.post(
            "/me/regression_first/start",
            json={"title": "manual"}, headers=_auth(sid),
        ).json()["chain_id"]
        r = client.post(
            "/me/regression_first/replay",
            json={"chain_id": manual_id}, headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_respects_user_partitioning(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        alice_id = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()}, headers=_auth(alice_sid),
        ).json()["chain_id"]
        # Bob cannot replay Alice's chain.
        r = client.post(
            "/me/regression_first/replay",
            json={"chain_id": alice_id}, headers=_auth(bob_sid),
        )
        assert r.status_code == 404

    def test_emits_started_and_layer_updated_events(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        original_id = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(layers=2)},
            headers=_auth(sid),
        ).json()["chain_id"]
        # Baseline: /packet emitted exactly one of each.
        baseline = timeline.list_events(user)
        baseline_starts = sum(
            1 for e in baseline
            if e["event_type"] == "regression_chain_started"
        )
        baseline_layers = sum(
            1 for e in baseline
            if e["event_type"] == "regression_chain_layer_updated"
        )
        client.post(
            "/me/regression_first/replay",
            json={"chain_id": original_id}, headers=_auth(sid),
        )
        after = timeline.list_events(user)
        after_starts = sum(
            1 for e in after
            if e["event_type"] == "regression_chain_started"
        )
        after_layers = sum(
            1 for e in after
            if e["event_type"] == "regression_chain_layer_updated"
        )
        assert after_starts == baseline_starts + 1
        assert after_layers == baseline_layers + 1

    def test_does_not_alter_original_chain(self, client):
        _, sid = _make_user("alice")
        original_id = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(layers=2)},
            headers=_auth(sid),
        ).json()["chain_id"]
        original_before = client.get(
            f"/me/regression_first/{original_id}", headers=_auth(sid),
        ).json()
        client.post(
            "/me/regression_first/replay",
            json={"chain_id": original_id}, headers=_auth(sid),
        )
        original_after = client.get(
            f"/me/regression_first/{original_id}", headers=_auth(sid),
        ).json()
        # Original chain envelope unchanged after replay.
        assert original_before == original_after

    def test_seeded_layer_matches_packet_seed_policy(self, client):
        _, sid = _make_user("alice")
        original_id = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(layers=3)},
            headers=_auth(sid),
        ).json()["chain_id"]
        new_chain = client.post(
            "/me/regression_first/replay",
            json={"chain_id": original_id}, headers=_auth(sid),
        ).json()
        # Same V80 seed policy: last skeleton layer seeded with status="unknown".
        assert len(new_chain["layers"]) == 1
        assert new_chain["layers"][0]["layer_index"] == 2
        assert new_chain["layers"][0]["status"] == "unknown"
        # And the notes still capture the last skeleton entry.
        assert "Layer3_name" in new_chain["layers"][0]["notes"]

    def test_new_chain_has_fresh_envelope(self, client):
        _, sid = _make_user("alice")
        original_id = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()}, headers=_auth(sid),
        ).json()["chain_id"]
        new_chain = client.post(
            "/me/regression_first/replay",
            json={"chain_id": original_id}, headers=_auth(sid),
        ).json()
        # New chain is open + not archived (clean slate).
        assert new_chain["closed_at"] is None
        assert new_chain["archived"] is False
        assert new_chain["tags"] == {}

    def test_requires_session(self, client):
        r = client.post(
            "/me/regression_first/replay",
            json={"chain_id": "any"},
        )
        assert r.status_code == 401

    def test_replay_of_replay_persists_packet_for_new_chain(self, client):
        """A replay-of-a-replay still finds the original packet under
        the new chain's id. Locks the recursive replay path."""
        import memory_vault
        user, sid = _make_user("alice")
        original_id = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()}, headers=_auth(sid),
        ).json()["chain_id"]
        replayed_id = client.post(
            "/me/regression_first/replay",
            json={"chain_id": original_id}, headers=_auth(sid),
        ).json()["chain_id"]
        # The new chain's packet entry exists.
        stored = memory_vault.vault_get(
            user, f"regression_packets.{replayed_id}",
        )
        assert stored is not None
        # And a second replay (of the replay) succeeds → 200.
        r3 = client.post(
            "/me/regression_first/replay",
            json={"chain_id": replayed_id}, headers=_auth(sid),
        )
        assert r3.status_code == 200


# ===========================================================================
# L. Routes + manifest + version
# ===========================================================================
class TestRoutesAndManifest:
    def test_replay_route_registered(self, client):
        import app
        routes = {getattr(r, "path", None) for r in app.app.routes}
        assert "/me/regression_first/replay" in routes

    def test_root_manifest_lists_replay(self, client):
        r = client.get("/")
        endpoints = r.json()["endpoints"]
        assert "POST /me/regression_first/replay" in endpoints

    def test_health_version_locked(self, client):
        r = client.get("/health")
        assert r.json()["version"] == __import__("_version").__version__
