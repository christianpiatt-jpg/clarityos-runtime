"""
Tests for V81 — tag deletion + chain archival.

Coverage:
    A. Kernel: delete_tag removes / no-ops / validates / rejects closed
    B. Kernel: archive_chain sets flag / idempotent / unknown raises /
       orthogonal to close
    C. Kernel: archived chains still accept step/tag/close/delete_tag
    D. Endpoint: /delete_tag updates tags, user-partitioned,
       no timeline event, 404 on unknown
    E. Endpoint: /archive sets flag, emits chain_archived event,
       user-partitioned, idempotent
    F. Endpoint: /list excludes archived by default, includes with
       ?include_archived=true
    G. Routes + manifest + /health 4.22
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


# ===========================================================================
# A. Kernel: delete_tag
# ===========================================================================
class TestDeleteTagKernel:
    def test_removes_existing_key(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        ps.tag_chain(c["chain_id"], {"area": "wp", "severity": "high"})
        out = ps.delete_tag(c["chain_id"], "severity")
        assert out["tags"] == {"area": "wp"}

    def test_noop_for_missing_key(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        ps.tag_chain(c["chain_id"], {"area": "wp"})
        out = ps.delete_tag(c["chain_id"], "severity")
        assert out["tags"] == {"area": "wp"}

    def test_persists_via_store(self, reset_stores):
        import problem_solver as ps
        store = ps.VaultBackedRegressionChainStore("alice")
        c = ps.start_chain("x", store=store)
        ps.tag_chain(c["chain_id"], {"area": "wp"}, store=store)
        ps.delete_tag(c["chain_id"], "area", store=store)
        # Reload from vault.
        reloaded = store.get(c["chain_id"])
        assert reloaded is not None
        assert reloaded["tags"] == {}

    def test_unknown_chain_raises_keyerror(self, reset_stores):
        import problem_solver as ps
        with pytest.raises(KeyError):
            ps.delete_tag("does-not-exist", "k")

    def test_non_string_key_rejected(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.delete_tag(c["chain_id"], 42)  # type: ignore[arg-type]

    def test_empty_key_rejected(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        with pytest.raises(ValueError):
            ps.delete_tag(c["chain_id"], "   ")

    def test_closed_chain_rejects_delete_tag(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        ps.tag_chain(c["chain_id"], {"area": "wp"})
        ps.close_chain(c["chain_id"])
        with pytest.raises(ValueError):
            ps.delete_tag(c["chain_id"], "area")


# ===========================================================================
# B. Kernel: archive_chain
# ===========================================================================
class TestArchiveChainKernel:
    def test_sets_archived_flag(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        assert c["archived"] is False
        out = ps.archive_chain(c["chain_id"])
        assert out["archived"] is True

    def test_idempotent_returns_same_chain(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        first = ps.archive_chain(c["chain_id"])
        second = ps.archive_chain(c["chain_id"])
        assert first["archived"] is True
        assert second["archived"] is True
        # Same chain id, same archived state.
        assert first["chain_id"] == second["chain_id"]

    def test_unknown_chain_raises_keyerror(self, reset_stores):
        import problem_solver as ps
        with pytest.raises(KeyError):
            ps.archive_chain("does-not-exist")

    def test_does_not_close_chain(self, reset_stores):
        """Archive and close are orthogonal — archiving doesn't
        touch ``closed_at``."""
        import problem_solver as ps
        c = ps.start_chain("x")
        assert c["closed_at"] is None
        out = ps.archive_chain(c["chain_id"])
        assert out["closed_at"] is None
        assert out["archived"] is True

    def test_existing_chains_default_archived_false(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        assert c["archived"] is False


# ===========================================================================
# C. Archived chains stay fully mutable
# ===========================================================================
class TestArchivedChainMutability:
    def test_archived_chain_accepts_step(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        ps.archive_chain(c["chain_id"])
        out = ps.record_finding(c["chain_id"], 0, "ok", "still works")
        assert out["archived"] is True
        assert out["layers"][0]["status"] == "ok"

    def test_archived_chain_accepts_tag(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        ps.archive_chain(c["chain_id"])
        out = ps.tag_chain(c["chain_id"], {"k": "v"})
        assert out["archived"] is True
        assert out["tags"] == {"k": "v"}

    def test_archived_chain_accepts_delete_tag(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        ps.tag_chain(c["chain_id"], {"k": "v"})
        ps.archive_chain(c["chain_id"])
        out = ps.delete_tag(c["chain_id"], "k")
        assert out["archived"] is True
        assert out["tags"] == {}

    def test_archived_chain_accepts_close(self, reset_stores):
        import problem_solver as ps
        c = ps.start_chain("x")
        ps.archive_chain(c["chain_id"])
        out = ps.close_chain(c["chain_id"])
        assert out["archived"] is True
        assert out["closed_at"] is not None


# ===========================================================================
# D. Endpoint: /delete_tag
# ===========================================================================
class TestDeleteTagEndpoint:
    def test_updates_tags(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"area": "wp", "severity": "high"}},
            headers=_auth(sid),
        )
        r = client.post(
            "/me/regression_first/delete_tag",
            json={"chain_id": chain_id, "key": "severity"},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json()["tags"] == {"area": "wp"}

    def test_noop_when_key_missing(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        r = client.post(
            "/me/regression_first/delete_tag",
            json={"chain_id": chain_id, "key": "ghost"},
            headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json()["tags"] == {}

    def test_unknown_chain_returns_404(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/delete_tag",
            json={"chain_id": "nope", "key": "k"},
            headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_cross_user_returns_404(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "alice"}, headers=_auth(alice_sid),
        ).json()["chain_id"]
        r = client.post(
            "/me/regression_first/delete_tag",
            json={"chain_id": chain_id, "key": "k"},
            headers=_auth(bob_sid),
        )
        assert r.status_code == 404

    def test_emits_no_timeline_events(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        # Baseline: /start emitted exactly one event.
        client.post(
            f"/me/regression_first/{chain_id}/tag",
            json={"tags": {"k": "v"}}, headers=_auth(sid),
        )
        baseline = len(timeline.list_events(user))
        client.post(
            "/me/regression_first/delete_tag",
            json={"chain_id": chain_id, "key": "k"},
            headers=_auth(sid),
        )
        assert len(timeline.list_events(user)) == baseline

    def test_requires_session(self, client):
        r = client.post(
            "/me/regression_first/delete_tag",
            json={"chain_id": "any", "key": "k"},
        )
        assert r.status_code == 401


# ===========================================================================
# E. Endpoint: /archive
# ===========================================================================
class TestArchiveEndpoint:
    def test_sets_archived_flag(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        r = client.post(
            "/me/regression_first/archive",
            json={"chain_id": chain_id}, headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json()["archived"] is True
        # closed_at unchanged.
        assert r.json()["closed_at"] is None

    def test_emits_chain_archived_event(self, client):
        from el_ins import timeline
        user, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            "/me/regression_first/archive",
            json={"chain_id": chain_id}, headers=_auth(sid),
        )
        events = timeline.list_events(user)
        kinds = [e["event_type"] for e in events]
        assert kinds.count("regression_chain_archived") == 1
        archived_event = next(
            e for e in events
            if e["event_type"] == "regression_chain_archived"
        )
        assert archived_event["payload"]["chain_id"] == chain_id
        assert isinstance(archived_event["payload"]["archived_at_ms"], int)

    def test_idempotent_200_ok(self, client):
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            "/me/regression_first/archive",
            json={"chain_id": chain_id}, headers=_auth(sid),
        )
        r = client.post(
            "/me/regression_first/archive",
            json={"chain_id": chain_id}, headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json()["archived"] is True

    def test_unknown_chain_returns_404(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/archive",
            json={"chain_id": "nope"}, headers=_auth(sid),
        )
        assert r.status_code == 404

    def test_cross_user_returns_404(self, client):
        _, alice_sid = _make_user("alice")
        _, bob_sid   = _make_user("bob")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "alice"}, headers=_auth(alice_sid),
        ).json()["chain_id"]
        r = client.post(
            "/me/regression_first/archive",
            json={"chain_id": chain_id}, headers=_auth(bob_sid),
        )
        assert r.status_code == 404

    def test_requires_session(self, client):
        r = client.post(
            "/me/regression_first/archive",
            json={"chain_id": "any"},
        )
        assert r.status_code == 401


# ===========================================================================
# F. Endpoint: /list include_archived
# ===========================================================================
class TestListArchivedFilter:
    def test_excludes_archived_by_default(self, client):
        _, sid = _make_user("alice")
        open_id = client.post(
            "/me/regression_first/start",
            json={"title": "open"}, headers=_auth(sid),
        ).json()["chain_id"]
        archived_id = client.post(
            "/me/regression_first/start",
            json={"title": "archived"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            "/me/regression_first/archive",
            json={"chain_id": archived_id}, headers=_auth(sid),
        )
        r = client.get("/me/regression_first", headers=_auth(sid))
        ids = [c["chain_id"] for c in r.json()["chains"]]
        assert open_id in ids
        assert archived_id not in ids

    def test_includes_archived_when_flag_set(self, client):
        _, sid = _make_user("alice")
        open_id = client.post(
            "/me/regression_first/start",
            json={"title": "open"}, headers=_auth(sid),
        ).json()["chain_id"]
        archived_id = client.post(
            "/me/regression_first/start",
            json={"title": "archived"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            "/me/regression_first/archive",
            json={"chain_id": archived_id}, headers=_auth(sid),
        )
        r = client.get(
            "/me/regression_first?include_archived=true",
            headers=_auth(sid),
        )
        ids = [c["chain_id"] for c in r.json()["chains"]]
        assert open_id in ids
        assert archived_id in ids

    def test_archived_chain_still_fetchable_directly(self, client):
        """Get-by-id ignores the archive flag — the chain is reachable
        regardless of list filter."""
        _, sid = _make_user("alice")
        chain_id = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        ).json()["chain_id"]
        client.post(
            "/me/regression_first/archive",
            json={"chain_id": chain_id}, headers=_auth(sid),
        )
        r = client.get(
            f"/me/regression_first/{chain_id}", headers=_auth(sid),
        )
        assert r.status_code == 200
        assert r.json()["archived"] is True


# ===========================================================================
# G. Routes + manifest + version
# ===========================================================================
class TestRoutesAndManifest:
    def test_routes_registered(self, client):
        import app
        routes = {getattr(r, "path", None) for r in app.app.routes}
        assert "/me/regression_first/delete_tag" in routes
        assert "/me/regression_first/archive" in routes

    def test_root_manifest_lists_v81_routes(self, client):
        r = client.get("/")
        endpoints = r.json()["endpoints"]
        assert "POST /me/regression_first/delete_tag" in endpoints
        assert "POST /me/regression_first/archive" in endpoints

    def test_health_version_locked(self, client):
        r = client.get("/health")
        assert r.json()["version"] == "4.23"

    def test_chain_envelope_includes_archived_field(self, client):
        _, sid = _make_user("alice")
        r = client.post(
            "/me/regression_first/start",
            json={"title": "x"}, headers=_auth(sid),
        )
        assert "archived" in r.json()
        assert r.json()["archived"] is False
