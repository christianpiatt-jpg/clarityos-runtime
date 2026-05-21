"""
Tests for V77 (vault persistence) + V78 (timeline integration) on
the V76 ``/me/regression_first/*`` endpoint surface.

V77 coverage:
    A. Chain persists in memory_vault under regression_chains.{cid}
    B. Vault partitions chains per-user (cross-user → 404, no leak)
    C. Chains survive across endpoint calls (no in-process owner index)
    D. VaultBackedRegressionChainStore unit-level round-trip
    E. InMemoryRegressionChainStore vs VaultBackedRegressionChainStore
       isolation (kernel default vs endpoint-injected)

V78 coverage:
    F. /start emits regression_chain_started (and only that)
    G. /step emits regression_chain_layer_updated (1:1 per step)
    H. /close emits regression_chain_closed
    I. /tag emits NO event (tags are metadata, not state changes)
    J. /get + /list emit NO events
    K. Cross-user no-leak: alice events not visible to bob's timeline
    L. Adjacency: regression events coexist with existing
       record/anomaly/rollup events without overlap.
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


# ===========================================================================
# V77 — A. Chain persists in memory_vault
# ===========================================================================
class TestVaultPersistence:
    def test_start_writes_to_vault(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/start",
            json={"title": "vault check"},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        chain_id = r.json()["chain_id"]
        # Direct vault read confirms the chain is persisted.
        stored = memory_vault.vault_get(
            user, f"regression_chains.{chain_id}",
        )
        assert stored is not None
        assert stored["chain_id"] == chain_id
        assert stored["title"] == "vault check"

    def test_step_writes_back_to_vault(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        )
        chain_id = r.json()["chain_id"]
        client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "issue", "notes": "n"},
            headers=_auth(sid),
        )
        stored = memory_vault.vault_get(
            user, f"regression_chains.{chain_id}",
        )
        assert len(stored["layers"]) == 1
        assert stored["layers"][0]["status"] == "issue"

    def test_close_writes_back_to_vault(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        )
        chain_id = r.json()["chain_id"]
        client.post(
            f"/me/regression_first/{chain_id}/close",
            json={"notes": "wrap"}, headers=_auth(sid),
        )
        stored = memory_vault.vault_get(
            user, f"regression_chains.{chain_id}",
        )
        assert stored["closed_at"] is not None
        assert stored["notes"] == "wrap"

    def test_tag_writes_back_to_vault(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        )
        chain_id = r.json()["chain_id"]
        client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"area": "ops"}}, headers=_auth(sid),
        )
        stored = memory_vault.vault_get(
            user, f"regression_chains.{chain_id}",
        )
        assert stored["tags"] == {"area": "ops"}

    def test_chain_id_key_namespace(self, client):
        import memory_vault
        user, sid = _make_user("alice")
        client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        )
        keys = memory_vault.vault_keys_for_user(user)
        assert any(k.startswith("regression_chains.") for k in keys)
        # And no other user has any entries yet.
        assert memory_vault.vault_keys_for_user("bob") == []


# ===========================================================================
# V77 — B. Per-user partitioning (cross-user → 404)
# ===========================================================================
class TestPerUserPartitioning:
    def test_cross_user_get_returns_404(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "alice"}, headers=_auth(alice_sid),
        ).json()["chain_id"]
        # Bob can't see alice's chain.
        r = client.get(
            f"/me/regression_first/{chain_id}", headers=_auth(bob_sid),
        )
        assert r.status_code == 404

    def test_cross_user_step_returns_404(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "alice"}, headers=_auth(alice_sid),
        ).json()["chain_id"]
        r = client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "ok"},
            headers=_auth(bob_sid),
        )
        assert r.status_code == 404

    def test_cross_user_close_returns_404(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "alice"}, headers=_auth(alice_sid),
        ).json()["chain_id"]
        r = client.post(
            f"/me/regression_first/{chain_id}/close",
            json={}, headers=_auth(bob_sid),
        )
        assert r.status_code == 404

    def test_cross_user_tag_returns_404(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "alice"}, headers=_auth(alice_sid),
        ).json()["chain_id"]
        r = client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"k": "v"}}, headers=_auth(bob_sid),
        )
        assert r.status_code == 404

    def test_bob_list_excludes_alice_chains(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        client.post(
            "/me/regression_first/start",
            json={"title": "alice 1"}, headers=_auth(alice_sid),
        )
        client.post(
            "/me/regression_first/start",
            json={"title": "alice 2"}, headers=_auth(alice_sid),
        )
        r = client.get("/me/regression_first", headers=_auth(bob_sid))
        assert r.status_code == 200
        assert r.json()["chains"] == []

    def test_alice_list_includes_only_alice_chains(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        a1 = client.post(
            "/me/regression_first/start",
            json={"title": "alice 1"}, headers=_auth(alice_sid),
        ).json()["chain_id"]
        client.post(
            "/me/regression_first/start",
            json={"title": "bob 1"}, headers=_auth(bob_sid),
        )
        r = client.get("/me/regression_first", headers=_auth(alice_sid))
        ids = [c["chain_id"] for c in r.json()["chains"]]
        assert a1 in ids
        assert len(ids) == 1


# ===========================================================================
# V77 — C. Persistence across endpoint calls (no in-process state)
# ===========================================================================
class TestPersistenceAcrossCalls:
    def test_chain_survives_multiple_separate_requests(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "spans calls"}, headers=_auth(sid),
        ).json()["chain_id"]
        # Each of these is a separate HTTP round-trip; if there were
        # in-process state we'd be relying on the test client reusing
        # the same process. The vault is the source of truth.
        client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "ok"},
            headers=_auth(sid),
        )
        client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 1, "status": "issue"},
            headers=_auth(sid),
        )
        client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"area": "x"}},
            headers=_auth(sid),
        )
        r = client.get(
            f"/me/regression_first/{chain_id}", headers=_auth(sid),
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body["layers"]) == 2
        assert body["tags"] == {"area": "x"}

    def test_kernel_default_store_does_not_leak_into_endpoints(
        self, client,
    ):
        """The kernel's in-memory DEFAULT_STORE must NOT be the
        same store endpoints write to. Endpoints use vault-backed."""
        import problem_solver
        # Create a chain via the kernel default store (no user).
        kernel_chain = problem_solver.start_chain("kernel-only")
        # Endpoint list should not include it.
        _, sid = _make_user("alice")
        r = client.get("/me/regression_first", headers=_auth(sid))
        ids = [c["chain_id"] for c in r.json()["chains"]]
        assert kernel_chain["chain_id"] not in ids


# ===========================================================================
# V77 — D. VaultBackedRegressionChainStore round-trip
# ===========================================================================
class TestVaultBackedStoreUnit:
    def test_save_and_get_roundtrip(self, reset_stores):
        import problem_solver
        store = problem_solver.VaultBackedRegressionChainStore("alice")
        chain = problem_solver.start_chain("vault unit", store=store)
        fetched = store.get(chain["chain_id"])
        assert fetched is not None
        assert fetched["chain_id"] == chain["chain_id"]
        assert fetched["title"] == "vault unit"

    def test_get_unknown_returns_none(self, reset_stores):
        import problem_solver
        store = problem_solver.VaultBackedRegressionChainStore("alice")
        assert store.get("nonexistent-id") is None

    def test_list_all_scoped_to_user(self, reset_stores):
        import problem_solver
        alice_store = problem_solver.VaultBackedRegressionChainStore("alice")
        bob_store   = problem_solver.VaultBackedRegressionChainStore("bob")
        problem_solver.start_chain("alice a", store=alice_store)
        problem_solver.start_chain("alice b", store=alice_store)
        problem_solver.start_chain("bob a",   store=bob_store)
        alice_list = alice_store.list_all()
        bob_list   = bob_store.list_all()
        assert len(alice_list) == 2
        assert len(bob_list)   == 1
        assert {c["title"] for c in alice_list} == {"alice a", "alice b"}
        assert bob_list[0]["title"] == "bob a"

    def test_delete_removes_from_vault(self, reset_stores):
        import problem_solver
        store = problem_solver.VaultBackedRegressionChainStore("alice")
        chain = problem_solver.start_chain("doomed", store=store)
        store.delete(chain["chain_id"])
        assert store.get(chain["chain_id"]) is None

    def test_constructor_rejects_invalid_user(self):
        import problem_solver
        for bad in ("", None, 42):
            with pytest.raises(ValueError):
                problem_solver.VaultBackedRegressionChainStore(bad)  # type: ignore[arg-type]


# ===========================================================================
# V78 — F/G/H. Timeline event emission per endpoint
# ===========================================================================
class TestTimelineEmission:
    def test_start_emits_chain_started(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/start",
            json={"title": "deploy hang"}, headers=_auth(sid),
        )
        chain_id = r.json()["chain_id"]
        events = timeline.list_events(user)
        starts = [
            e for e in events
            if e["event_type"] == "regression_chain_started"
        ]
        assert len(starts) == 1
        ev = starts[0]
        assert ev["payload"]["chain_id"] == chain_id
        assert ev["payload"]["title"] == "deploy hang"
        assert isinstance(ev["payload"]["created_at_ms"], int)
        assert isinstance(ev["timestamp_ms"], int)

    def test_step_emits_layer_updated(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "issue", "notes": "n"},
            headers=_auth(sid),
        )
        events = timeline.list_events(user)
        layer_events = [
            e for e in events
            if e["event_type"] == "regression_chain_layer_updated"
        ]
        assert len(layer_events) == 1
        ev = layer_events[0]
        assert ev["payload"]["chain_id"] == chain_id
        assert ev["payload"]["layer_index"] == 0
        assert ev["payload"]["status"] == "issue"
        assert isinstance(ev["payload"]["updated_at_ms"], int)

    def test_step_overwrite_emits_second_event(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "unknown"},
            headers=_auth(sid),
        )
        client.post(
            f"/me/regression_first/step?chain_id={chain_id}",
            json={"layer_index": 0, "status": "issue"},
            headers=_auth(sid),
        )
        layer_events = [
            e for e in timeline.list_events(user)
            if e["event_type"] == "regression_chain_layer_updated"
        ]
        assert len(layer_events) == 2

    def test_close_emits_chain_closed(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            f"/me/regression_first/{chain_id}/close",
            json={}, headers=_auth(sid),
        )
        closes = [
            e for e in timeline.list_events(user)
            if e["event_type"] == "regression_chain_closed"
        ]
        assert len(closes) == 1
        ev = closes[0]
        assert ev["payload"]["chain_id"] == chain_id
        assert isinstance(ev["payload"]["closed_at_ms"], int)


# ===========================================================================
# V78 — I/J. Tag + read endpoints emit no events
# ===========================================================================
class TestNoSpuriousEmission:
    def test_tag_emits_no_event(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"area": "x"}}, headers=_auth(sid),
        )
        events = timeline.list_events(user)
        # Only the started event from /start.
        assert {e["event_type"] for e in events} == {
            "regression_chain_started",
        }

    def test_get_emits_no_event(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        baseline = len(timeline.list_events(user))
        client.get(
            f"/me/regression_first/{chain_id}", headers=_auth(sid),
        )
        client.get(
            f"/me/regression_first/{chain_id}", headers=_auth(sid),
        )
        assert len(timeline.list_events(user)) == baseline

    def test_list_emits_no_event(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        )
        baseline = len(timeline.list_events(user))
        client.get("/me/regression_first", headers=_auth(sid))
        client.get("/me/regression_first", headers=_auth(sid))
        assert len(timeline.list_events(user)) == baseline


# ===========================================================================
# V78 — K. Cross-user no-leak
# ===========================================================================
class TestCrossUserTimelineNoLeak:
    def test_alice_events_invisible_to_bob(self, client):
        from el_ins import timeline
        alice, alice_sid = _make_user("alice")
        bob,   bob_sid   = _make_user("bob")
        client.post(
            "/me/regression_first/start",
            json={"title": "alice chain"}, headers=_auth(alice_sid),
        )
        # Alice has 1 started event.
        assert any(
            e["event_type"] == "regression_chain_started"
            for e in timeline.list_events(alice)
        )
        # Bob has 0 regression events.
        assert not any(
            str(e["event_type"]).startswith("regression_chain_")
            for e in timeline.list_events(bob)
        )


# ===========================================================================
# V78 — L. Adjacency with existing event types
# ===========================================================================
class TestEventTypeAdjacency:
    def test_existing_types_preserved(self):
        from el_ins.timeline import TIMELINE_EVENT_TYPES
        # Original v73 types still present (additive boundary).
        for kind in ("record", "anomaly", "rollup", "system"):
            assert kind in TIMELINE_EVENT_TYPES

    def test_three_new_types_registered(self):
        from el_ins.timeline import TIMELINE_EVENT_TYPES
        for kind in (
            "regression_chain_started",
            "regression_chain_layer_updated",
            "regression_chain_closed",
        ):
            assert kind in TIMELINE_EVENT_TYPES

    def test_builders_round_trip_via_store_event(self):
        """Builders produce events that pass validation in
        ``store_event``. Locks the payload shape against drift."""
        from el_ins import timeline
        timeline._reset_for_tests()
        ts = int(time.time() * 1000)
        for event in (
            timeline.build_regression_chain_started_event(
                "alice", chain_id="c1",
                title="t", created_at_ms=ts,
            ),
            timeline.build_regression_chain_layer_updated_event(
                "alice", chain_id="c1",
                layer_index=2, status="issue", updated_at_ms=ts,
            ),
            timeline.build_regression_chain_closed_event(
                "alice", chain_id="c1", closed_at_ms=ts,
            ),
        ):
            stored = timeline.store_event(event)
            assert stored["operator_id"] == "alice"
            assert stored["payload"]["chain_id"] == "c1"
            assert isinstance(stored["id"], str) and stored["id"]
            assert isinstance(stored["timestamp_ms"], int)
