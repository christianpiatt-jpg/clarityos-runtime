"""
Tests for ELINS Unit 25 — SQLite-backed persistence layer.

Layered coverage (>= 80 tests, target ~90):
    A. Core CRUD — save / load / delete / overwrite
    B. Listing — list_runs / list_runs_with_metadata
    C. Migration — legacy JSON files imported on first access
    D. WAL + concurrency
    E. Schema + module surface
    F. Performance sanity
    G. Integration — analytics still work through the new backend
"""
from __future__ import annotations

import inspect
import json
import os
import secrets
import sqlite3
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_persistence_sqlite as ep_sql


# ===========================================================================
# Fixtures
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


def _entry(pair_id="p1", *, sp=5, ec=5,
           sp_band="Acceptable", ec_band="Acceptable") -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp,
        "economic_coercion_score": ec,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _db_path(runs_dir: Path) -> Path:
    return runs_dir / ep._DB_FILENAME


def _drop_json(runs_dir: Path, run_id: str, payload) -> Path:
    """Drop a raw JSON file for the migration tests. The persistence
    layer is NOT touched — we want to simulate a pre-Unit-25 deployment
    where the DB file does not yet exist."""
    runs_dir.mkdir(parents=True, exist_ok=True)
    target = runs_dir / f"{run_id}.json"
    target.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return target


# ===========================================================================
# A. Core CRUD
# ===========================================================================
class TestCoreSaveLoad:
    def test_save_then_load_envelope_shape(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert set(loaded.keys()) == {"metadata", "result"}

    def test_save_preserves_result_payload(self):
        payload = [_entry("p1", sp=5), _entry("p2", sp=8)]
        ep.save_comparison_result("r", payload)
        loaded = ep.load_comparison_result("r")
        assert loaded["result"] == payload

    def test_save_default_source(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert loaded["metadata"]["source"] == "single"

    def test_save_explicit_batch_source(self):
        ep.save_comparison_result("r", [_entry("p1")], source="batch")
        loaded = ep.load_comparison_result("r")
        assert loaded["metadata"]["source"] == "batch"

    def test_save_directory_with_evidence_dir(self):
        ep.save_comparison_result(
            "r", [_entry("p1")],
            source="directory", evidence_dir="/x/y",
        )
        meta = ep.load_comparison_result("r")["metadata"]
        assert meta["source"] == "directory"
        assert meta["evidence_dir"] == "/x/y"

    def test_metadata_engine_version(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert loaded["metadata"]["engine_version"] == "elins-19"

    def test_metadata_created_at_iso8601(self):
        import re as _re
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        ts = loaded["metadata"]["created_at"]
        assert _re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)

    def test_save_rejects_invalid_source(self):
        with pytest.raises(ValueError, match="source must be"):
            ep.save_comparison_result("r", [], source="hacker")

    def test_save_rejects_malformed_run_id(self):
        with pytest.raises(ValueError):
            ep.save_comparison_result("bad/id", [])

    def test_load_rejects_malformed_run_id(self):
        with pytest.raises(ValueError):
            ep.load_comparison_result("bad/id")

    def test_load_missing_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            ep.load_comparison_result("ghost")

    def test_save_creates_db_file(self, _runs_dir_isolation):
        assert not _db_path(_runs_dir_isolation).exists()
        ep.save_comparison_result("r", [_entry("p1")])
        assert _db_path(_runs_dir_isolation).exists()

    def test_repeated_load_byte_equal(self):
        ep.save_comparison_result("r", [_entry("p1")])
        a = ep.load_comparison_result("r")
        b = ep.load_comparison_result("r")
        assert a == b

    def test_save_complex_nested_payload(self):
        payload = [
            _entry("a", sp=3, ec=7, sp_band="Strong", ec_band="Weak"),
            _entry("b", sp=8, ec=2, sp_band="Acceptable",
                   ec_band="Fails core logic"),
        ]
        ep.save_comparison_result("r", payload, source="batch")
        loaded = ep.load_comparison_result("r")
        assert loaded["result"] == payload


class TestOverwrite:
    def test_overwrite_replaces_result(self):
        ep.save_comparison_result("r", [_entry("p1", sp=5)])
        ep.save_comparison_result("r", [_entry("p1", sp=9)])
        loaded = ep.load_comparison_result("r")
        assert loaded["result"] == [_entry("p1", sp=9)]

    def test_overwrite_keeps_single_row(self, _runs_dir_isolation):
        ep.save_comparison_result("r", [])
        ep.save_comparison_result("r", [])
        conn = sqlite3.connect(str(_db_path(_runs_dir_isolation)))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM runs WHERE run_id = ?", ("r",),
            ).fetchone()[0]
        finally:
            conn.close()
        assert count == 1

    def test_overwrite_can_change_source(self):
        ep.save_comparison_result("r", [], source="single")
        ep.save_comparison_result("r", [], source="batch")
        assert ep.load_comparison_result("r")["metadata"]["source"] == "batch"


class TestDelete:
    def test_delete_removes_row(self):
        ep.save_comparison_result("r", [])
        ep.delete_comparison_result("r")
        with pytest.raises(FileNotFoundError):
            ep.load_comparison_result("r")

    def test_delete_run_alias_works(self):
        ep.save_comparison_result("r", [])
        ep.delete_run("r")
        with pytest.raises(FileNotFoundError):
            ep.load_comparison_result("r")

    def test_delete_missing_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            ep.delete_comparison_result("ghost")

    def test_delete_idempotent(self):
        ep.save_comparison_result("once", [])
        ep.delete_comparison_result("once")
        with pytest.raises(FileNotFoundError):
            ep.delete_comparison_result("once")

    def test_delete_rejects_malformed_id(self):
        with pytest.raises(ValueError):
            ep.delete_comparison_result("bad$id")

    def test_delete_one_does_not_affect_others(self):
        ep.save_comparison_result("keep", [_entry("p1", sp=5)])
        ep.save_comparison_result("drop", [_entry("p1", sp=9)])
        ep.delete_comparison_result("drop")
        assert ep.load_comparison_result("keep")["result"] == [
            _entry("p1", sp=5),
        ]


class TestRetention:
    def test_zero_days_is_noop(self):
        ep.save_comparison_result("kept", [])
        assert ep.delete_runs_older_than(0) == []
        assert "kept" in ep.list_runs()

    def test_old_run_deleted(self):
        ep.save_comparison_result("old", [])
        from datetime import datetime, timedelta, timezone
        ep._set_run_created_at(
            "old",
            (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(),
        )
        deleted = ep.delete_runs_older_than(30)
        assert deleted == ["old"]
        assert "old" not in ep.list_runs()

    def test_fresh_run_kept(self):
        ep.save_comparison_result("fresh", [])
        deleted = ep.delete_runs_older_than(30)
        assert deleted == []
        assert "fresh" in ep.list_runs()

    def test_legacy_run_not_deleted_by_age(
        self, _runs_dir_isolation,
    ):
        """A legacy envelope (metadata=None) has no created_at, so it
        must never be swept by age-based retention."""
        ep_sql._ensure_init(str(_db_path(_runs_dir_isolation)))
        conn = sqlite3.connect(str(_db_path(_runs_dir_isolation)))
        try:
            conn.execute(
                "INSERT INTO runs (run_id, envelope_json) VALUES (?, ?)",
                ("legacy", json.dumps(
                    {"metadata": None, "result": []},
                    sort_keys=True, ensure_ascii=False,
                )),
            )
            conn.commit()
        finally:
            conn.close()
        deleted = ep.delete_runs_older_than(30)
        assert deleted == []
        assert "legacy" in ep.list_runs()

    def test_returns_alphabetical_order(self):
        from datetime import datetime, timedelta, timezone
        for rid in ("zeta", "alpha", "mid"):
            ep.save_comparison_result(rid, [])
            ep._set_run_created_at(
                rid,
                (datetime.now(timezone.utc) - timedelta(days=100)).isoformat(),
            )
        assert ep.delete_runs_older_than(30) == ["alpha", "mid", "zeta"]


# ===========================================================================
# B. Listing
# ===========================================================================
class TestListing:
    def test_empty_returns_empty_list(self):
        assert ep.list_runs() == []

    def test_listing_alphabetical(self):
        for rid in ("zeta", "alpha", "mid"):
            ep.save_comparison_result(rid, [])
        assert ep.list_runs() == ["alpha", "mid", "zeta"]

    def test_with_metadata_returns_dicts(self):
        ep.save_comparison_result("r", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert isinstance(out, list)
        assert all(isinstance(row, dict) for row in out)

    def test_with_metadata_locked_keys(self):
        ep.save_comparison_result("r", [_entry("p1")])
        row = ep.list_runs_with_metadata()[0]
        assert set(row.keys()) == {
            "run_id", "created_at", "source",
            "evidence_dir", "engine_version",
            # Unit 27/28 — operator-utility fields always present.
            "notes", "tags", "archived",
        }

    def test_with_metadata_alphabetical(self):
        for rid in ("zeta", "alpha", "mid"):
            ep.save_comparison_result(rid, [])
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["alpha", "mid", "zeta"]

    def test_with_metadata_carries_source(self):
        ep.save_comparison_result("r", [], source="batch")
        row = ep.list_runs_with_metadata()[0]
        assert row["source"] == "batch"

    def test_with_metadata_carries_evidence_dir(self):
        ep.save_comparison_result(
            "r", [], source="directory", evidence_dir="/x",
        )
        row = ep.list_runs_with_metadata()[0]
        assert row["evidence_dir"] == "/x"

    def test_with_metadata_engine_version_locked(self):
        ep.save_comparison_result("r", [])
        assert ep.list_runs_with_metadata()[0]["engine_version"] == "elins-19"

    def test_legacy_metadata_all_none(self, _runs_dir_isolation):
        ep_sql._ensure_init(str(_db_path(_runs_dir_isolation)))
        conn = sqlite3.connect(str(_db_path(_runs_dir_isolation)))
        try:
            conn.execute(
                "INSERT INTO runs (run_id, envelope_json) VALUES (?, ?)",
                ("leg", json.dumps(
                    {"metadata": None, "result": [_entry("p1")]},
                    sort_keys=True, ensure_ascii=False,
                )),
            )
            conn.commit()
        finally:
            conn.close()
        row = ep.list_runs_with_metadata()[0]
        assert row["run_id"] == "leg"
        assert row["created_at"] is None
        assert row["source"] is None
        assert row["evidence_dir"] is None
        assert row["engine_version"] is None


# ===========================================================================
# C. Migration — legacy JSON files imported on first access
# ===========================================================================
class TestMigration:
    def test_db_missing_triggers_migration(self, _runs_dir_isolation):
        """A fresh tmp_path has no DB; dropping legacy JSONs there and
        then calling any persistence function imports them."""
        _drop_json(_runs_dir_isolation, "leg1", [_entry("p1", sp=5)])
        _drop_json(_runs_dir_isolation, "leg2", [_entry("p1", sp=8)])
        # First persistence call triggers init + migration.
        assert sorted(ep.list_runs()) == ["leg1", "leg2"]

    def test_migrated_legacy_list_has_null_metadata(
        self, _runs_dir_isolation,
    ):
        _drop_json(_runs_dir_isolation, "leg", [_entry("p1")])
        loaded = ep.load_comparison_result("leg")
        assert loaded["metadata"] is None
        assert loaded["result"] == [_entry("p1")]

    def test_migrated_envelope_file_returned_as_is(
        self, _runs_dir_isolation,
    ):
        envelope = {
            "metadata": {
                "created_at":     "2026-01-01T00:00:00+00:00",
                "source":         "directory",
                "evidence_dir":   "/x",
                "engine_version": "elins-19",
            },
            "result": [_entry("p1", sp=5)],
        }
        _drop_json(_runs_dir_isolation, "envel", envelope)
        loaded = ep.load_comparison_result("envel")
        assert loaded == envelope

    def test_migrated_free_form_dict_wrapped_as_legacy(
        self, _runs_dir_isolation,
    ):
        """A pre-Unit-19 free-form dict file (no envelope keys) gets
        wrapped at migration time so callers always see the envelope
        shape."""
        _drop_json(_runs_dir_isolation, "weird", {"foo": "bar"})
        loaded = ep.load_comparison_result("weird")
        assert loaded["metadata"] is None
        assert loaded["result"] == {"foo": "bar"}

    def test_migration_skips_non_json_files(self, _runs_dir_isolation):
        _runs_dir_isolation.mkdir(parents=True, exist_ok=True)
        (_runs_dir_isolation / "README.txt").write_text("notes")
        (_runs_dir_isolation / "scratch.tmp").write_text("junk")
        _drop_json(_runs_dir_isolation, "ok", [_entry("p1")])
        assert ep.list_runs() == ["ok"]

    def test_migration_skips_invalid_stem_filenames(
        self, _runs_dir_isolation,
    ):
        _runs_dir_isolation.mkdir(parents=True, exist_ok=True)
        (_runs_dir_isolation / "bad name with spaces.json").write_text("{}")
        _drop_json(_runs_dir_isolation, "ok_run", [_entry("p1")])
        assert ep.list_runs() == ["ok_run"]

    def test_migration_handles_corrupt_json(self, _runs_dir_isolation):
        """A corrupt JSON file shouldn't abort migration of the others."""
        _runs_dir_isolation.mkdir(parents=True, exist_ok=True)
        (_runs_dir_isolation / "corrupt.json").write_text("{not json")
        _drop_json(_runs_dir_isolation, "ok", [_entry("p1")])
        assert ep.list_runs() == ["ok"]

    def test_migration_idempotent_no_second_run(
        self, _runs_dir_isolation,
    ):
        """If the DB already exists, subsequent calls don't re-scan the
        JSON directory — locked by checking that a new JSON dropped
        AFTER the first init is NOT picked up."""
        _drop_json(_runs_dir_isolation, "first", [_entry("p1")])
        # First access: migration runs, picks up 'first'.
        assert ep.list_runs() == ["first"]
        # Drop another JSON AFTER init.
        _drop_json(_runs_dir_isolation, "second", [_entry("p1")])
        # No re-migration; 'second' is NOT present.
        assert ep.list_runs() == ["first"]

    def test_migration_leaves_json_files_intact(self, _runs_dir_isolation):
        target = _drop_json(_runs_dir_isolation, "leg", [_entry("p1")])
        ep.list_runs()  # triggers migration
        assert target.exists()
        # The file content is unchanged.
        re_read = json.loads(target.read_text(encoding="utf-8"))
        assert re_read == [_entry("p1")]

    def test_db_exists_no_migration(self, _runs_dir_isolation):
        """If the DB exists when we look at it, the JSON dir is not
        scanned — protects against re-importing the same data twice."""
        # Force-create a DB without any JSONs.
        ep.save_comparison_result("seed", [_entry("p1")])
        # Now drop a JSON into the dir; should NOT be picked up.
        _drop_json(_runs_dir_isolation, "after_init", [_entry("p1")])
        # Reset the init cache so next call re-checks the file, but the
        # file already exists so migration must not run.
        ep_sql._reset_init_cache_for_tests()
        assert sorted(ep.list_runs()) == ["seed"]


class TestSchema:
    def test_runs_table_exists_after_save(self, _runs_dir_isolation):
        ep.save_comparison_result("r", [])
        conn = sqlite3.connect(str(_db_path(_runs_dir_isolation)))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='runs'"
            ).fetchone()
        finally:
            conn.close()
        assert row is not None

    def test_runs_table_columns(self, _runs_dir_isolation):
        """Unit 27/28: the runs table now has three additional columns
        for operator-utility flags (notes / tags / archived)."""
        ep.save_comparison_result("r", [])
        conn = sqlite3.connect(str(_db_path(_runs_dir_isolation)))
        try:
            cols = conn.execute("PRAGMA table_info(runs)").fetchall()
        finally:
            conn.close()
        names = {c[1] for c in cols}
        assert names == {
            "run_id", "envelope_json",
            "notes", "tags", "archived",
        }

    def test_run_id_primary_key(self, _runs_dir_isolation):
        ep.save_comparison_result("r", [])
        conn = sqlite3.connect(str(_db_path(_runs_dir_isolation)))
        try:
            cols = conn.execute("PRAGMA table_info(runs)").fetchall()
        finally:
            conn.close()
        # PRAGMA table_info returns (cid, name, type, notnull, dflt, pk).
        pk_cols = [c for c in cols if c[5] == 1]
        assert len(pk_cols) == 1
        assert pk_cols[0][1] == "run_id"


# ===========================================================================
# D. WAL + Concurrency
# ===========================================================================
class TestWAL:
    def test_journal_mode_is_wal(self, _runs_dir_isolation):
        ep.save_comparison_result("r", [])
        conn = sqlite3.connect(str(_db_path(_runs_dir_isolation)))
        try:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        finally:
            conn.close()
        assert mode.lower() == "wal"

    def test_two_sequential_saves_no_lock_error(self):
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        assert sorted(ep.list_runs()) == ["a", "b"]

    def test_save_load_save_load_interleaved(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        assert ep.load_comparison_result("a")["result"][0]["single_party_score"] == 5
        ep.save_comparison_result("a", [_entry("p1", sp=8)])
        assert ep.load_comparison_result("a")["result"][0]["single_party_score"] == 8

    def test_two_loads_in_sequence_no_lock_error(self):
        ep.save_comparison_result("r", [_entry("p1")])
        a = ep.load_comparison_result("r")
        b = ep.load_comparison_result("r")
        assert a == b

    def test_concurrent_saves_from_threads(self):
        """Lock-free WAL means writes from multiple threads serialise
        without surfacing SQLITE_BUSY to the caller."""
        import threading
        errors: list = []

        def _w(idx):
            try:
                ep.save_comparison_result(f"t_{idx}", [_entry(f"p{idx}")])
            except Exception as e:  # noqa: BLE001
                errors.append((idx, e))

        threads = [
            threading.Thread(target=_w, args=(i,)) for i in range(8)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        assert sorted(ep.list_runs()) == [f"t_{i}" for i in range(8)]


# ===========================================================================
# E. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_facade_exports_all_public(self):
        for name in (
            "save_comparison_result", "load_comparison_result",
            "delete_comparison_result", "delete_run",
            "delete_runs_older_than",
            "list_runs", "list_runs_with_metadata",
        ):
            assert hasattr(ep, name), f"facade missing: {name}"
            assert callable(getattr(ep, name))

    def test_facade_exports_constants(self):
        for name in (
            "_DEFAULT_RUNS_DIR", "_RUNS_DIR_ENV_VAR", "_DB_PATH_ENV_VAR",
            "_DB_FILENAME", "_RUN_ID_RE", "_ENGINE_VERSION",
            "_ALLOWED_SOURCES", "_LISTING_FIELDS",
        ):
            assert hasattr(ep, name), f"facade missing constant: {name}"

    def test_facade_validate_helpers_callable(self):
        assert callable(ep._validate_run_id)
        assert callable(ep._validate_source)
        assert callable(ep._build_metadata)

    def test_facade_and_sqlite_share_engine_version(self):
        assert ep._ENGINE_VERSION == ep_sql._ENGINE_VERSION == "elins-19"

    def test_db_filename_is_locked(self):
        assert ep._DB_FILENAME == "elins_runs.db"

    def test_facade_module_doc_present(self):
        assert isinstance(ep.__doc__, str)
        assert "Unit 25" in ep.__doc__


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(ep_sql)

    def _code_only(self) -> str:
        import re as _re
        src = self._src()
        src = _re.sub(r'"""[\s\S]*?"""', "", src)
        src = _re.sub(r"'''[\s\S]*?'''", "", src)
        return src

    def test_no_logging(self):
        src = self._code_only()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_network(self):
        src = self._code_only()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket"):
            assert forbidden not in src

    def test_no_llm_imports(self):
        src = self._code_only()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._code_only()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src


# ===========================================================================
# F. Performance sanity (loose ceilings — guards against pathological regression)
# ===========================================================================
class TestPerformanceSanity:
    def test_save_under_50ms_small_payload(self):
        payload = [_entry("p1")]
        t0 = time.perf_counter()
        ep.save_comparison_result("perf_save", payload)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.05, f"save took {elapsed:.4f}s"

    def test_load_under_50ms_small_payload(self):
        ep.save_comparison_result("perf_load", [_entry("p1")])
        t0 = time.perf_counter()
        ep.load_comparison_result("perf_load")
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.05, f"load took {elapsed:.4f}s"

    def test_listing_under_100ms_with_50_runs(self):
        for i in range(50):
            ep.save_comparison_result(f"r_{i:03d}", [_entry("p1")])
        t0 = time.perf_counter()
        out = ep.list_runs()
        elapsed = time.perf_counter() - t0
        assert len(out) == 50
        assert elapsed < 0.1, f"list_runs took {elapsed:.4f}s"

    def test_listing_with_metadata_under_200ms_with_50_runs(self):
        for i in range(50):
            ep.save_comparison_result(f"m_{i:03d}", [_entry("p1")])
        t0 = time.perf_counter()
        out = ep.list_runs_with_metadata()
        elapsed = time.perf_counter() - t0
        assert len(out) == 50
        assert elapsed < 0.2, f"list_runs_with_metadata took {elapsed:.4f}s"


# ===========================================================================
# G. Integration — analytics still work through the new backend
# ===========================================================================
class TestAnalyticsIntegration:
    def test_diff_works_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        resp = client.get(
            "/elins/regression/diff?run_a=a&run_b=b", headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_drift_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_composite_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        resp = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {
            "run_ids", "metadata", "summary",
            "direction", "magnitude", "severity", "series",
        }

    def test_summary_endpoint_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        resp = client.get(
            "/elins/regression/run/r/summary", headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_metadata_endpoint_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")], source="batch")
        body = client.get(
            "/elins/regression/run/r/metadata", headers=_auth(sid),
        ).json()
        assert body["metadata"]["source"] == "batch"

    def test_listing_endpoint_works(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("a", "b", "c"):
            ep.save_comparison_result(rid, [])
        body = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["a", "b", "c"]

    def test_filtering_still_works_on_drift_series(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [
            _entry("alpha", sp=5), _entry("beta", sp=5),
        ])
        ep.save_comparison_result("b", [
            _entry("alpha", sp=8), _entry("beta", sp=5),
        ])
        body = client.post(
            "/elins/regression/drift/series?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert list(body.keys()) == ["alpha"]

    def test_directory_evidence_dir_metadata_preserved(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "dir_run", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.get(
            "/elins/regression/run/dir_run/metadata", headers=_auth(sid),
        ).json()
        assert body["metadata"]["source"] == "directory"
        assert body["metadata"]["evidence_dir"] == os.path.realpath(
            str(tmp_path),
        )

    def test_ordering_still_works_via_composite(
        self, client, app_module,
    ):
        """Unit 23 timestamp ordering still functions on SQLite-stored
        runs — caller order is ignored and the response reflects
        timestamp ordering (alphabetical tiebreak when timestamps are
        coarse-clock equal)."""
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r1", [_entry("p1", sp=2)])
        ep.save_comparison_result("r2", [_entry("p1", sp=9)])
        forward = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["r1", "r2"]}, headers=_auth(sid),
        ).json()
        reverse = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["r2", "r1"]}, headers=_auth(sid),
        ).json()
        assert forward == reverse

    def test_evidence_dir_allowlist_still_enforced(
        self, client, app_module, tmp_path,
    ):
        import elins_evidence_allowlist as al
        # Override autouse fixture: empty allowlist.
        original = al.ALLOWED_EVIDENCE_DIRS
        al.ALLOWED_EVIDENCE_DIRS = ()
        try:
            sid = _make_user_session(app_module)
            resp = client.post(
                "/elins/regression/analyze_directory_and_store",
                json={"run_id": "bad_dir", "path": str(tmp_path)},
                headers=_auth(sid),
            )
            assert resp.status_code == 400
        finally:
            al.ALLOWED_EVIDENCE_DIRS = original

    def test_runs_summary_endpoint_works(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("a", "b"):
            ep.save_comparison_result(rid, [_entry("p1")])
        resp = client.post(
            "/elins/regression/runs/summary",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body["runs"].keys()) == {"a", "b"}

    def test_drift_magnitude_endpoint_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert "p1" in resp.json()

    def test_drift_severity_endpoint_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1", sp=2)])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["p1"]["direction"] == "trending_up"

    def test_retention_endpoint_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("fresh", [_entry("p1")])
        resp = client.post(
            "/elins/regression/retention/delete_older_than",
            json={"days": 30}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == []
