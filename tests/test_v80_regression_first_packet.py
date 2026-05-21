"""
Tests for V80 — POST /me/regression_first/packet.

Coverage:
    A. Happy path: packet creates persisted chain (returns V76 model)
    B. Chain is seeded with last skeleton layer as 'unknown' finding
    C. Both timeline events emitted (started + layer_updated)
    D. Per-user partitioning (cross-user 404 + bob's list empty)
    E. Kernel ok=False → 422 packet_rejected
    F. regression_required=False → 422 regression_not_required
    G. Auth gating (401 anonymous)
    H. Route registered in manifest
    I. /health version locked at 4.23
    J. /packet emits no events when chain not created (422 paths)
    K. Existing v76/v77/v78 routes still present
"""
from __future__ import annotations

import secrets
import time

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
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
        "recommended_system_action": (
            "Pause and request operator verification."
            if regression_required else "Proceed normally."
        ),
    }


# ===========================================================================
# A. Happy path
# ===========================================================================
class TestHappyPath:
    def test_packet_creates_persisted_chain(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()},
            headers=_auth(sid),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Wire shape matches V76RegressionChainModel.
        assert set(body.keys()) >= {
            "chain_id", "created_at", "closed_at",
            "title", "notes", "layers", "tags",
        }
        # Title comes from packet.operator_intent.
        assert body["title"] == "Identify root cause of rendering failure."
        # Chain was persisted to the user's vault partition.
        stored = memory_vault.vault_get(
            user, f"regression_chains.{body['chain_id']}",
        )
        assert stored is not None
        assert stored["chain_id"] == body["chain_id"]

    def test_packet_response_is_v76_chain_model(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()},
            headers=_auth(sid),
        )
        body = r.json()
        # closed_at remains null at packet creation time.
        assert body["closed_at"] is None
        # tags default to empty dict (operator can add via /tag later).
        assert body["tags"] == {}


# ===========================================================================
# B. Chain seeded with last skeleton layer
# ===========================================================================
class TestSeededLayer:
    def test_last_skeleton_layer_seeded_as_unknown(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(layers=3)},
            headers=_auth(sid),
        )
        body = r.json()
        # Exactly ONE layer seeded — the LAST one in the skeleton.
        assert len(body["layers"]) == 1
        seeded = body["layers"][0]
        # Layer_index = position in skeleton array (0-based) → last
        # entry is index 2 for a 3-layer skeleton.
        assert seeded["layer_index"] == 2
        # Status is 'unknown' (operator hasn't actually verified
        # anything; the layer is just present + populated).
        assert seeded["status"] == "unknown"
        # Notes synthesised from last skeleton entry.
        assert "Layer3_name" in seeded["notes"]
        assert "Layer3_question" in seeded["notes"]
        assert "Layer3_location" in seeded["notes"]
        assert "Layer3_goal" in seeded["notes"]

    def test_single_layer_skeleton_seeded_at_index_zero(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(layers=1)},
            headers=_auth(sid),
        )
        body = r.json()
        assert len(body["layers"]) == 1
        assert body["layers"][0]["layer_index"] == 0
        assert body["layers"][0]["status"] == "unknown"


# ===========================================================================
# C. Timeline emission
# ===========================================================================
class TestTimelineEmission:
    def test_packet_emits_started_and_layer_updated(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(layers=2)},
            headers=_auth(sid),
        )
        events = timeline.list_events(user)
        kinds = [e["event_type"] for e in events]
        # Exactly one of each — start + the seeded layer.
        assert kinds.count("regression_chain_started") == 1
        assert kinds.count("regression_chain_layer_updated") == 1
        # No close or anomaly emitted.
        assert "regression_chain_closed" not in kinds

    def test_layer_event_targets_last_skeleton_index(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(layers=4)},
            headers=_auth(sid),
        )
        events = timeline.list_events(user)
        layer_event = next(
            e for e in events
            if e["event_type"] == "regression_chain_layer_updated"
        )
        assert layer_event["payload"]["layer_index"] == 3
        assert layer_event["payload"]["status"] == "unknown"


# ===========================================================================
# D. Per-user partitioning
# ===========================================================================
class TestPerUserPartitioning:
    def test_alice_packet_invisible_to_bob_list(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()},
            headers=_auth(alice_sid),
        )
        alice_chain_id = r.json()["chain_id"]
        # Bob's list is empty.
        rb = client.get("/me/regression_first", headers=_auth(bob_sid))
        assert rb.status_code == 200
        assert rb.json()["chains"] == []
        # Bob cannot read alice's chain.
        r404 = client.get(
            f"/me/regression_first/{alice_chain_id}",
            headers=_auth(bob_sid),
        )
        assert r404.status_code == 404

    def test_alice_packet_visible_to_alice_list(self, client):
        _, alice_sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()},
            headers=_auth(alice_sid),
        )
        chain_id = r.json()["chain_id"]
        rl = client.get(
            "/me/regression_first", headers=_auth(alice_sid),
        )
        ids = [c["chain_id"] for c in rl.json()["chains"]]
        assert chain_id in ids

    def test_bob_timeline_does_not_see_alice_events(self, client):
        from el_ins import timeline
        alice, alice_sid = _make_user("alice")
        bob,   bob_sid   = _make_user("bob")
        client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()},
            headers=_auth(alice_sid),
        )
        # Alice has events.
        assert any(
            str(e["event_type"]).startswith("regression_chain_")
            for e in timeline.list_events(alice)
        )
        # Bob has none.
        assert not any(
            str(e["event_type"]).startswith("regression_chain_")
            for e in timeline.list_events(bob)
        )


# ===========================================================================
# E. Kernel ok=False → 422 packet_rejected
# ===========================================================================
class TestPacketRejected:
    def test_missing_required_field_returns_422(self, client):
        _, sid = _make_user("alice")
        packet = _canonical_packet()
        del packet["classification"]
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": packet},
            headers=_auth(sid),
        )
        assert r.status_code == 422
        body = r.json()
        # error_response shape: {detail: {error, message}}
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict):
            assert detail.get("error") == "packet_rejected"
        else:
            # Fallback in case error_response wraps differently
            assert "packet_rejected" in str(body)

    def test_invalid_scores_returns_422(self, client):
        _, sid = _make_user("alice")
        packet = _canonical_packet()
        packet["EL"] = 99
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": packet},
            headers=_auth(sid),
        )
        assert r.status_code == 422

    def test_invalid_classification_returns_422(self, client):
        _, sid = _make_user("alice")
        packet = _canonical_packet()
        packet["classification"] = "high_el"   # wrong vocabulary
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": packet},
            headers=_auth(sid),
        )
        assert r.status_code == 422

    def test_non_dict_packet_returns_422(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": "not-a-dict"},  # type: ignore[dict-item]
            headers=_auth(sid),
        )
        # Pydantic may reject before our 422 (would be 400/422 either
        # way); just confirm it doesn't reach a 200.
        assert r.status_code in (400, 422)

    def test_rejected_packet_emits_no_timeline_events(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        packet = _canonical_packet()
        del packet["classification"]
        client.post(
            "/me/regression_first/packet",
            json={"packet": packet},
            headers=_auth(sid),
        )
        kinds = [e["event_type"] for e in timeline.list_events(user)]
        assert "regression_chain_started" not in kinds
        assert "regression_chain_layer_updated" not in kinds


# ===========================================================================
# F. regression_required=False → 422 regression_not_required
# ===========================================================================
class TestRegressionNotRequired:
    def test_returns_422_when_no_regression_needed(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(regression_required=False)},
            headers=_auth(sid),
        )
        assert r.status_code == 422
        body = r.json()
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict):
            assert detail.get("error") == "regression_not_required"

    def test_no_chain_persisted_when_not_required(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(regression_required=False)},
            headers=_auth(sid),
        )
        keys = memory_vault.vault_keys_for_user(user)
        assert not any(k.startswith("regression_chains.") for k in keys)

    def test_no_timeline_events_when_not_required(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet(regression_required=False)},
            headers=_auth(sid),
        )
        kinds = [e["event_type"] for e in timeline.list_events(user)]
        assert "regression_chain_started" not in kinds


# ===========================================================================
# G. Auth gating
# ===========================================================================
class TestAuthGating:
    def test_anonymous_returns_401(self, client):
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()},
        )
        assert r.status_code == 401

    def test_invalid_session_returns_401(self, client):
        r = client.post(
            "/me/regression_first/packet",
            json={"packet": _canonical_packet()},
            headers={"X-Session-ID": "not-a-real-session"},
        )
        assert r.status_code == 401


# ===========================================================================
# H. Route + manifest + version
# ===========================================================================
class TestRouteAndManifest:
    def test_route_registered(self, client):
        import app
        routes = {getattr(r, "path", None) for r in app.app.routes}
        assert "/me/regression_first/packet" in routes
        # All v76 routes still present.
        for path in (
            "/me/regression_first/start",
            "/me/regression_first/step",
            "/me/regression_first/{chain_id}",
            "/me/regression_first",
            "/me/regression_first/{chain_id}/close",
            "/me/regression_first/{chain_id}/tag",
        ):
            assert path in routes, f"v76 route missing: {path!r}"

    def test_root_manifest_lists_v80_packet(self, client):
        r = client.get("/")
        assert r.status_code == 200
        endpoints = r.json()["endpoints"]
        assert "POST /me/regression_first/packet" in endpoints

    def test_health_version_locked(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["version"] == "4.23"
