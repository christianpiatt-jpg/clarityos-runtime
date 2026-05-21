"""
Tests for ELINS Unit 12 — run deletion + retention layer.

Layered coverage (≥ 35 tests):
    A. delete_run core
    B. DELETE /elins/regression/run/{run_id} endpoint
    C. delete_runs_older_than core
    D. POST /elins/regression/retention/delete_older_than endpoint
    E. Determinism + ordering
    F. Existing endpoints unaffected
"""
from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep


# ===========================================================================
# Fixtures — runs-dir isolation per test
# ===========================================================================
@pytest.fixture(autouse=True)
def _runs_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runs_dir = tmp_path / "elins_runs"
    monkeypatch.setenv(ep._RUNS_DIR_ENV_VAR, str(runs_dir))
    yield runs_dir


@pytest.fixture
def app_module(reset_stores):
    import app as app_module
    return app_module


@pytest.fixture
def client(app_module):
    return TestClient(app_module.app)


def _make_user_session(app_module, username="alice"):
    import bcrypt
    import sessions_store
    import users_store

    pwd_hash = bcrypt.hashpw(b"test-pass-123", bcrypt.gensalt())
    users_store.create_user(
        username=username, password_hash=pwd_hash, salt="",
        tier="free", created_at=time.time(),
    )
    sid = "sess_" + secrets.token_urlsafe(16)
    sessions_store.create_session(sid, username, expires_at=time.time() + 3600)
    return sid


def _auth(sid):
    return {"X-Session-ID": sid}


def _backdate(runs_dir: Path, run_id: str, days_old: float) -> None:
    """Unit 25: rewrite the stored run's ``metadata.created_at`` to be
    ``days_old`` days in the past. Replaces the pre-Unit-25 file-mtime
    trick now that storage is SQLite (no per-run JSON file to touch).

    The ``runs_dir`` argument is kept for signature compatibility but
    is no longer used — the SQLite backend resolves the active DB
    path via the same env var the autouse fixture sets up."""
    _ = runs_dir
    from datetime import datetime, timedelta, timezone
    new_dt = datetime.now(timezone.utc) - timedelta(days=days_old)
    ep._set_run_created_at(run_id, new_dt.isoformat())


# ===========================================================================
# A. delete_run core
# ===========================================================================
class TestDeleteRunCore:
    def test_deletes_existing_run(self):
        ep.save_comparison_result("to_delete", {"v": 1})
        assert "to_delete" in ep.list_runs()
        ep.delete_run("to_delete")
        assert "to_delete" not in ep.list_runs()

    def test_deletion_removes_row_from_db(self, _runs_dir_isolation):
        """Unit 25: storage is SQLite, so we verify the row is gone
        from the underlying table rather than a per-run JSON file."""
        import sqlite3
        ep.save_comparison_result("on_disk", {})
        db_path = _runs_dir_isolation / "elins_runs.db"
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT run_id FROM runs WHERE run_id = ?",
                ("on_disk",),
            ).fetchone()
            assert row is not None
        finally:
            conn.close()
        ep.delete_run("on_disk")
        conn = sqlite3.connect(str(db_path))
        try:
            row = conn.execute(
                "SELECT run_id FROM runs WHERE run_id = ?",
                ("on_disk",),
            ).fetchone()
            assert row is None
        finally:
            conn.close()

    def test_load_after_delete_raises_filenotfound(self):
        ep.save_comparison_result("doomed", {"v": 1})
        ep.delete_run("doomed")
        with pytest.raises(FileNotFoundError):
            ep.load_comparison_result("doomed")

    def test_second_delete_raises_filenotfound(self):
        ep.save_comparison_result("once", {"v": 1})
        ep.delete_run("once")
        with pytest.raises(FileNotFoundError):
            ep.delete_run("once")

    def test_delete_missing_run_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            ep.delete_run("never_existed")

    def test_deletion_does_not_affect_other_runs(self):
        ep.save_comparison_result("keep_a", {"v": "a"})
        ep.save_comparison_result("keep_b", {"v": "b"})
        ep.save_comparison_result("delete_me", {"v": "c"})
        ep.delete_run("delete_me")
        assert ep.list_runs() == ["keep_a", "keep_b"]
        # Unit 19: load returns {metadata, result} envelope.
        assert ep.load_comparison_result("keep_a")["result"] == {"v": "a"}
        assert ep.load_comparison_result("keep_b")["result"] == {"v": "b"}

    def test_deletion_reflected_in_list_runs(self):
        ep.save_comparison_result("a", {})
        ep.save_comparison_result("b", {})
        ep.save_comparison_result("c", {})
        assert ep.list_runs() == ["a", "b", "c"]
        ep.delete_run("b")
        assert ep.list_runs() == ["a", "c"]

    @pytest.mark.parametrize("bad_id", ["", " ", "a/b", "..", "../escape",
                                         "$dangerous", "a:b"])
    def test_delete_rejects_bad_run_ids(self, bad_id):
        with pytest.raises(ValueError):
            ep.delete_run(bad_id)

    def test_delete_non_string_raises(self):
        with pytest.raises(ValueError, match="must be a string"):
            ep.delete_run(42)  # type: ignore[arg-type]

    def test_delete_does_not_remove_runs_directory(self, _runs_dir_isolation):
        ep.save_comparison_result("only", {})
        ep.delete_run("only")
        # Directory should still exist even after the last file is gone.
        assert _runs_dir_isolation.is_dir()

    def test_delete_does_not_remove_unrelated_files(self, _runs_dir_isolation):
        ep.save_comparison_result("real", {})
        (_runs_dir_isolation / "README.txt").write_text("notes")
        ep.delete_run("real")
        assert (_runs_dir_isolation / "README.txt").exists()


# ===========================================================================
# B. DELETE endpoint
# ===========================================================================
class TestDeleteEndpoint:
    def test_existing_run_returns_200_with_deleted_id(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("api_del", {"v": 1})
        resp = client.post("/login", json={"username": "alice", "password": "test-pass-123"})
        # Use raw httpx via the client — we need DELETE.
        # Our AppClient only has get/post; extend via direct httpx.
        import httpx
        import asyncio

        async def _do_delete():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete(
                    "/elins/regression/run/api_del",
                    headers=_auth(sid),
                )

        r = asyncio.run(_do_delete())
        assert r.status_code == 200
        assert r.json() == {"deleted": "api_del"}

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        import httpx, asyncio

        async def _do():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete(
                    "/elins/regression/run/never_stored",
                    headers=_auth(sid),
                )

        r = asyncio.run(_do())
        assert r.status_code == 404

    def test_malformed_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        import httpx, asyncio

        async def _do():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete(
                    "/elins/regression/run/bad$id",
                    headers=_auth(sid),
                )

        r = asyncio.run(_do())
        # Either 400 (our validator) or 404 (FastAPI path constraint).
        assert r.status_code in (400, 404)

    def test_unauthenticated_returns_401(self, client, app_module):
        ep.save_comparison_result("any", {})
        import httpx, asyncio

        async def _do():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete("/elins/regression/run/any")

        r = asyncio.run(_do())
        assert r.status_code == 401

    def test_deletion_reflected_in_list_runs_endpoint(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", {})
        ep.save_comparison_result("b", {})
        ep.save_comparison_result("c", {})

        import httpx, asyncio

        async def _do_delete():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete(
                    "/elins/regression/run/b", headers=_auth(sid),
                )

        r = asyncio.run(_do_delete())
        assert r.status_code == 200

        # Now /runs should reflect the deletion.
        # Unit 20: bare list of metadata dicts; assert the run_ids only.
        runs_resp = client.get("/elins/regression/runs", headers=_auth(sid))
        assert [row["run_id"] for row in runs_resp.json()] == ["a", "c"]

    def test_deletion_reflected_in_get_run_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("ephemeral", {"v": 1})
        # Confirm fetch works before delete.
        get_before = client.get(
            "/elins/regression/run/ephemeral", headers=_auth(sid),
        )
        assert get_before.status_code == 200

        import httpx, asyncio

        async def _do_delete():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete(
                    "/elins/regression/run/ephemeral", headers=_auth(sid),
                )

        asyncio.run(_do_delete())
        get_after = client.get(
            "/elins/regression/run/ephemeral", headers=_auth(sid),
        )
        assert get_after.status_code == 404

    def test_delete_is_idempotent_404_on_second(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("once", {})
        import httpx, asyncio

        async def _del():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete(
                    "/elins/regression/run/once", headers=_auth(sid),
                )

        first = asyncio.run(_del())
        second = asyncio.run(_del())
        assert first.status_code == 200
        assert second.status_code == 404

    def test_response_format_locked(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("format_test", {})
        import httpx, asyncio

        async def _del():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete(
                    "/elins/regression/run/format_test", headers=_auth(sid),
                )

        r = asyncio.run(_del())
        body = r.json()
        assert set(body.keys()) == {"deleted"}
        assert body["deleted"] == "format_test"

    def test_delete_preserves_other_runs(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("keep1", {"v": 1})
        ep.save_comparison_result("delete_me", {"v": 2})
        ep.save_comparison_result("keep2", {"v": 3})

        import httpx, asyncio

        async def _del():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app_module.app),
                base_url="http://testserver",
            ) as ac:
                return await ac.delete(
                    "/elins/regression/run/delete_me", headers=_auth(sid),
                )

        asyncio.run(_del())
        r1 = client.get("/elins/regression/run/keep1", headers=_auth(sid))
        r2 = client.get("/elins/regression/run/keep2", headers=_auth(sid))
        assert r1.status_code == 200
        assert r2.status_code == 200


# ===========================================================================
# C. delete_runs_older_than core
# ===========================================================================
class TestRetentionCore:
    def test_zero_days_is_no_op(self):
        ep.save_comparison_result("kept", {})
        assert ep.delete_runs_older_than(0) == []
        assert "kept" in ep.list_runs()

    def test_threshold_deletes_old_runs(self, _runs_dir_isolation):
        ep.save_comparison_result("old", {"v": "old"})
        ep.save_comparison_result("new", {"v": "new"})
        _backdate(_runs_dir_isolation, "old", days_old=100)
        deleted = ep.delete_runs_older_than(30)
        assert deleted == ["old"]
        assert ep.list_runs() == ["new"]

    def test_threshold_just_below_age_keeps_run(self, _runs_dir_isolation):
        """A 30-day-old run survives a 31-day threshold."""
        ep.save_comparison_result("borderline", {})
        _backdate(_runs_dir_isolation, "borderline", days_old=30)
        deleted = ep.delete_runs_older_than(31)
        assert deleted == []
        assert "borderline" in ep.list_runs()

    def test_threshold_above_age_deletes_run(self, _runs_dir_isolation):
        ep.save_comparison_result("old_enough", {})
        _backdate(_runs_dir_isolation, "old_enough", days_old=60)
        deleted = ep.delete_runs_older_than(30)
        assert deleted == ["old_enough"]

    def test_large_threshold_with_old_files_deletes_all(self, _runs_dir_isolation):
        for stem in ("a", "b", "c"):
            ep.save_comparison_result(stem, {})
            _backdate(_runs_dir_isolation, stem, days_old=400)
        deleted = ep.delete_runs_older_than(365)
        assert deleted == ["a", "b", "c"]
        assert ep.list_runs() == []

    def test_returns_alphabetical_order(self, _runs_dir_isolation):
        for stem in ("zeta", "alpha", "mid"):
            ep.save_comparison_result(stem, {})
            _backdate(_runs_dir_isolation, stem, days_old=100)
        assert ep.delete_runs_older_than(30) == ["alpha", "mid", "zeta"]

    def test_negative_days_raises(self):
        with pytest.raises(ValueError, match="must be >= 0"):
            ep.delete_runs_older_than(-1)

    def test_non_int_days_raises(self):
        with pytest.raises(ValueError, match="non-negative int"):
            ep.delete_runs_older_than("30")  # type: ignore[arg-type]

    def test_float_days_raises(self):
        with pytest.raises(ValueError, match="non-negative int"):
            ep.delete_runs_older_than(7.5)  # type: ignore[arg-type]

    def test_bool_days_raises(self):
        """bool is a subclass of int but rejected here as a typing nuisance."""
        with pytest.raises(ValueError, match="non-negative int"):
            ep.delete_runs_older_than(True)  # type: ignore[arg-type]

    def test_none_days_raises(self):
        with pytest.raises(ValueError, match="non-negative int"):
            ep.delete_runs_older_than(None)  # type: ignore[arg-type]

    def test_no_runs_directory_returns_empty(self, _runs_dir_isolation):
        # Don't create any runs → directory doesn't exist.
        assert not _runs_dir_isolation.exists()
        assert ep.delete_runs_older_than(30) == []

    def test_empty_runs_directory_returns_empty(self, _runs_dir_isolation):
        ep.save_comparison_result("then_delete", {})
        ep.delete_run("then_delete")
        # Directory exists but empty.
        assert _runs_dir_isolation.is_dir()
        assert ep.delete_runs_older_than(30) == []

    def test_no_old_runs_returns_empty(self):
        for stem in ("a", "b", "c"):
            ep.save_comparison_result(stem, {})
        # All runs are fresh — none older than 30 days.
        assert ep.delete_runs_older_than(30) == []
        assert ep.list_runs() == ["a", "b", "c"]

    def test_mixed_old_and_new_only_deletes_old(self, _runs_dir_isolation):
        ep.save_comparison_result("fresh1", {})
        ep.save_comparison_result("fresh2", {})
        ep.save_comparison_result("old1", {})
        ep.save_comparison_result("old2", {})
        _backdate(_runs_dir_isolation, "old1", days_old=100)
        _backdate(_runs_dir_isolation, "old2", days_old=100)
        deleted = ep.delete_runs_older_than(30)
        assert deleted == ["old1", "old2"]
        assert ep.list_runs() == ["fresh1", "fresh2"]

    def test_skips_non_json_files(self, _runs_dir_isolation):
        ep.save_comparison_result("real_run", {})
        _backdate(_runs_dir_isolation, "real_run", days_old=100)
        # Drop a non-JSON file with an old mtime.
        bad = _runs_dir_isolation / "notes.txt"
        bad.write_text("hello")
        old_t = time.time() - 100 * 86400
        os.utime(bad, (old_t, old_t))
        ep.delete_runs_older_than(30)
        # Non-JSON file is untouched.
        assert bad.exists()


# ===========================================================================
# D. Retention endpoint
# ===========================================================================
class TestRetentionEndpoint:
    def test_valid_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 30},
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_shape(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 30},
            headers=_auth(sid),
        )
        body = resp.json()
        assert set(body.keys()) == {"deleted", "count"}
        assert isinstance(body["deleted"], list)
        assert isinstance(body["count"], int)

    def test_zero_days_no_op(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("preserved", {})
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 0},
            headers=_auth(sid),
        )
        assert resp.json() == {"deleted": [], "count": 0}
        assert "preserved" in ep.list_runs()

    def test_deletes_old_runs_via_endpoint(
        self, client, app_module, _runs_dir_isolation,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("fresh", {})
        ep.save_comparison_result("old1", {})
        ep.save_comparison_result("old2", {})
        _backdate(_runs_dir_isolation, "old1", days_old=100)
        _backdate(_runs_dir_isolation, "old2", days_old=100)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 30},
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["count"] == 2
        assert body["deleted"] == ["old1", "old2"]
        assert ep.list_runs() == ["fresh"]

    def test_missing_days_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_negative_days_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": -1}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_string_days_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": "30"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_float_days_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 7.5}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_bool_days_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": True}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_unauth_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 30},
        )
        assert resp.status_code == 401

    def test_deterministic_ordering(
        self, client, app_module, _runs_dir_isolation,
    ):
        sid = _make_user_session(app_module)
        for stem in ("zeta", "alpha", "mid", "beta"):
            ep.save_comparison_result(stem, {})
            _backdate(_runs_dir_isolation, stem, days_old=100)
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 30},
            headers=_auth(sid),
        )
        assert resp.json()["deleted"] == ["alpha", "beta", "mid", "zeta"]

    def test_no_old_runs_returns_zero_count(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("recent", {})
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 30},
            headers=_auth(sid),
        )
        assert resp.json() == {"deleted": [], "count": 0}


# ===========================================================================
# E. Determinism + idempotence
# ===========================================================================
class TestDeterminism:
    def test_repeated_retention_calls_deterministic(self, _runs_dir_isolation):
        for stem in ("a", "b", "c"):
            ep.save_comparison_result(stem, {})
            _backdate(_runs_dir_isolation, stem, days_old=100)
        # First call deletes everything.
        first = ep.delete_runs_older_than(30)
        assert first == ["a", "b", "c"]
        # Second call has nothing left.
        second = ep.delete_runs_older_than(30)
        assert second == []

    def test_delete_run_idempotent_after_first(self):
        ep.save_comparison_result("once", {})
        ep.delete_run("once")
        # Subsequent attempts always raise the same error.
        for _ in range(3):
            with pytest.raises(FileNotFoundError):
                ep.delete_run("once")


# ===========================================================================
# F. Existing endpoints unaffected
# ===========================================================================
class TestExistingEndpointsUnaffected:
    def test_health_still_works(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_runs_listing_endpoint_still_works(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get("/elins/regression/runs", headers=_auth(sid))
        assert resp.status_code == 200

    def test_save_then_load_still_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("preserved", {"v": 1})
        resp = client.get("/elins/regression/run/preserved", headers=_auth(sid))
        assert resp.status_code == 200
        assert resp.json() == {"v": 1}
