"""
Tests for ELINS Unit 20 — enhanced run listing (IDs + metadata).

Layered coverage (≥ 60 tests, target 70+):
    A. Core listing — list_runs_with_metadata()
    B. Endpoint — GET /elins/regression/runs (Unit 20 shape)
    C. Integration — analyze_and_store path → listing reflects source/dir
    D. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import re
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_timeline_dashboard as etd


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


def _entry(pair_id="p1", *, sp=5, ec=5,
           sp_band="Acceptable", ec_band="Acceptable") -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp,
        "economic_coercion_score": ec,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _write_legacy_file(runs_dir: Path, run_id: str, payload) -> None:
    """Unit 25: insert a legacy-shaped envelope (``metadata=None``)
    directly into the SQLite DB."""
    import sqlite3
    import elins_persistence_sqlite as ep_sql
    db_path = runs_dir / ep_sql._DB_FILENAME
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ep_sql._ensure_init(str(db_path))
    envelope = {
        ep_sql._ENVELOPE_METADATA_KEY: None,
        ep_sql._ENVELOPE_RESULT_KEY:   payload,
    }
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, envelope_json) VALUES (?, ?)",
            (run_id, json.dumps(envelope, sort_keys=True, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


_LOCKED_KEYS: set = {
    "run_id", "created_at", "source", "evidence_dir", "engine_version",
    "notes", "tags", "archived",  # Unit 27/28 additions
}


# ===========================================================================
# A. Core listing — list_runs_with_metadata()
# ===========================================================================
class TestCoreListingShape:
    def test_returns_list(self):
        ep.save_comparison_result("r", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert isinstance(out, list)

    def test_empty_dir_returns_empty_list(self):
        assert ep.list_runs_with_metadata() == []

    def test_each_entry_is_dict(self):
        ep.save_comparison_result("r", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert all(isinstance(row, dict) for row in out)

    def test_each_entry_has_locked_keys(self):
        ep.save_comparison_result("r", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        for row in out:
            assert set(row.keys()) == _LOCKED_KEYS

    def test_run_id_field_matches_save_id(self):
        ep.save_comparison_result("specific_id", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert out[0]["run_id"] == "specific_id"

    def test_single_run_listed_once(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert len(out) == 1


class TestCoreListingOrdering:
    def test_alphabetical_ordering_simple(self):
        for rid in ("zeta", "alpha", "mid"):
            ep.save_comparison_result(rid, [])
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["alpha", "mid", "zeta"]

    def test_alphabetical_with_underscores_and_digits(self):
        for rid in ("run_3", "run_1", "run_2"):
            ep.save_comparison_result(rid, [])
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["run_1", "run_2", "run_3"]

    def test_alphabetical_with_hyphens(self):
        for rid in ("a-c", "a-b", "a-a"):
            ep.save_comparison_result(rid, [])
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["a-a", "a-b", "a-c"]

    def test_save_order_does_not_affect_listing(self):
        # Save in reverse-alpha; verify alphabetical output.
        for rid in ("z", "y", "x", "w", "v"):
            ep.save_comparison_result(rid, [])
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["v", "w", "x", "y", "z"]

    def test_deterministic_repeated_calls(self):
        for rid in ("a", "b", "c"):
            ep.save_comparison_result(rid, [])
        first  = ep.list_runs_with_metadata()
        second = ep.list_runs_with_metadata()
        assert first == second


class TestCoreListingMetadataValues:
    def test_default_source_is_single(self):
        ep.save_comparison_result("r", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert out[0]["source"] == "single"

    def test_explicit_batch_source(self):
        ep.save_comparison_result("r", [_entry("p1")], source="batch")
        out = ep.list_runs_with_metadata()
        assert out[0]["source"] == "batch"

    def test_explicit_directory_source_with_evidence_dir(self):
        ep.save_comparison_result(
            "r", [_entry("p1")],
            source="directory", evidence_dir="/some/dir",
        )
        out = ep.list_runs_with_metadata()
        assert out[0]["source"] == "directory"
        assert out[0]["evidence_dir"] == "/some/dir"

    def test_default_evidence_dir_is_none(self):
        ep.save_comparison_result("r", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert out[0]["evidence_dir"] is None

    def test_engine_version_locked(self):
        ep.save_comparison_result("r", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert out[0]["engine_version"] == "elins-19"

    def test_created_at_iso8601_prefix(self):
        ep.save_comparison_result("r", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        ts = out[0]["created_at"]
        assert isinstance(ts, str)
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)

    def test_source_in_allowed_set(self):
        for src in ("single", "batch", "directory"):
            ep.save_comparison_result(f"r_{src}", [_entry("p1")], source=src)
        out = ep.list_runs_with_metadata()
        for row in out:
            assert row["source"] in ep._ALLOWED_SOURCES

    def test_evidence_dir_passes_through(self):
        ep.save_comparison_result(
            "r", [_entry("p1")],
            source="directory", evidence_dir="/some/very/specific/path",
        )
        out = ep.list_runs_with_metadata()
        assert out[0]["evidence_dir"] == "/some/very/specific/path"

    def test_three_runs_each_have_independent_metadata(self):
        ep.save_comparison_result("a", [_entry("p1")], source="single")
        ep.save_comparison_result("b", [_entry("p1")], source="batch")
        ep.save_comparison_result(
            "c", [_entry("p1")],
            source="directory", evidence_dir="/c-dir",
        )
        out = ep.list_runs_with_metadata()
        by_id = {r["run_id"]: r for r in out}
        assert by_id["a"]["source"] == "single"
        assert by_id["b"]["source"] == "batch"
        assert by_id["c"]["source"] == "directory"
        assert by_id["c"]["evidence_dir"] == "/c-dir"


class TestCoreListingLegacyRuns:
    def test_legacy_run_yields_all_none_metadata_fields(
        self, _runs_dir_isolation,
    ):
        _write_legacy_file(_runs_dir_isolation, "leg", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        leg = out[0]
        assert leg["run_id"] == "leg"
        assert leg["created_at"] is None
        assert leg["source"] is None
        assert leg["evidence_dir"] is None
        assert leg["engine_version"] is None

    def test_legacy_run_still_has_all_locked_keys(
        self, _runs_dir_isolation,
    ):
        _write_legacy_file(_runs_dir_isolation, "leg", [])
        out = ep.list_runs_with_metadata()
        assert set(out[0].keys()) == _LOCKED_KEYS

    def test_mixed_legacy_and_new_runs(self, _runs_dir_isolation):
        _write_legacy_file(_runs_dir_isolation, "old", [_entry("p1")])
        ep.save_comparison_result("new", [_entry("p1")], source="batch")
        out = ep.list_runs_with_metadata()
        by_id = {r["run_id"]: r for r in out}
        assert by_id["old"]["source"] is None
        assert by_id["new"]["source"] == "batch"

    def test_alphabetical_ordering_includes_legacy(self, _runs_dir_isolation):
        _write_legacy_file(_runs_dir_isolation, "m_old", [_entry("p1")])
        ep.save_comparison_result("a_new", [_entry("p1")])
        ep.save_comparison_result("z_new", [_entry("p1")])
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["a_new", "m_old", "z_new"]

    def test_dict_legacy_with_no_envelope_keys(self, _runs_dir_isolation):
        """A legacy dict file without envelope keys (e.g. an old test
        artifact) must still appear in the listing with null metadata."""
        _runs_dir_isolation.mkdir(parents=True, exist_ok=True)
        (_runs_dir_isolation / "weird.json").write_text(
            json.dumps({"foo": "bar"}), encoding="utf-8",
        )
        out = ep.list_runs_with_metadata()
        assert any(r["run_id"] == "weird" for r in out)
        weird = next(r for r in out if r["run_id"] == "weird")
        assert weird["source"] is None
        assert weird["created_at"] is None


class TestCoreListingFilesystemRules:
    def test_listing_skips_non_json_files(self, _runs_dir_isolation):
        ep.save_comparison_result("real_run", [])
        (_runs_dir_isolation / "README.txt").write_text("notes")
        (_runs_dir_isolation / "scratch.tmp").write_text("junk")
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["real_run"]

    def test_listing_skips_subdirs(self, _runs_dir_isolation):
        ep.save_comparison_result("real_run", [])
        (_runs_dir_isolation / "subdir").mkdir()
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["real_run"]

    def test_listing_skips_invalid_stem_filenames(self, _runs_dir_isolation):
        ep.save_comparison_result("ok_run", [])
        (_runs_dir_isolation / "bad name.json").write_text("{}")
        out = ep.list_runs_with_metadata()
        assert [r["run_id"] for r in out] == ["ok_run"]

    def test_missing_runs_directory_returns_empty(self):
        # Fixture creates the parent tmp_path but the runs_dir under it
        # is never auto-created until a save happens.
        assert ep.list_runs_with_metadata() == []

    def test_zero_runs_after_delete(self):
        ep.save_comparison_result("r", [_entry("p1")])
        ep.delete_run("r")
        assert ep.list_runs_with_metadata() == []


# ===========================================================================
# B. Endpoint — GET /elins/regression/runs (Unit 20 shape)
# ===========================================================================
class TestEndpointShape:
    _PATH = "/elins/regression/runs"

    def test_empty_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(self._PATH, headers=_auth(sid))
        assert resp.status_code == 200

    def test_empty_returns_bare_empty_list(self, client, app_module):
        sid = _make_user_session(app_module)
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert body == []

    def test_response_is_bare_list_not_dict_wrapped(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert isinstance(body, list)

    def test_each_entry_has_locked_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        for row in body:
            assert set(row.keys()) == _LOCKED_KEYS

    def test_unauth_returns_401(self, client, app_module):
        resp = client.get(self._PATH)
        assert resp.status_code == 401


class TestEndpointMultipleRuns:
    _PATH = "/elins/regression/runs"

    def test_three_runs_alphabetical(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("zeta", "alpha", "mid"):
            ep.save_comparison_result(rid, [_entry("p1")])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert [r["run_id"] for r in body] == ["alpha", "mid", "zeta"]

    def test_count_matches_saved_runs(self, client, app_module):
        sid = _make_user_session(app_module)
        for i in range(7):
            ep.save_comparison_result(f"r_{i}", [_entry("p1")])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert len(body) == 7

    def test_metadata_per_run_independent(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1")], source="single")
        ep.save_comparison_result("b", [_entry("p1")], source="batch")
        ep.save_comparison_result(
            "c", [_entry("p1")],
            source="directory", evidence_dir="/c",
        )
        body = client.get(self._PATH, headers=_auth(sid)).json()
        by_id = {r["run_id"]: r for r in body}
        assert by_id["a"]["source"] == "single"
        assert by_id["b"]["source"] == "batch"
        assert by_id["c"]["source"] == "directory"
        assert by_id["c"]["evidence_dir"] == "/c"

    def test_deterministic_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("a", "b", "c"):
            ep.save_comparison_result(rid, [_entry("p1")])
        r1 = client.get(self._PATH, headers=_auth(sid)).json()
        r2 = client.get(self._PATH, headers=_auth(sid)).json()
        assert r1 == r2


class TestEndpointLegacyAndMixed:
    _PATH = "/elins/regression/runs"

    def test_legacy_run_returns_null_metadata_fields(
        self, client, app_module, _runs_dir_isolation,
    ):
        sid = _make_user_session(app_module)
        _write_legacy_file(_runs_dir_isolation, "leg", [_entry("p1")])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        leg = next(r for r in body if r["run_id"] == "leg")
        assert leg["created_at"] is None
        assert leg["source"] is None
        assert leg["evidence_dir"] is None
        assert leg["engine_version"] is None

    def test_legacy_run_still_has_locked_keys(
        self, client, app_module, _runs_dir_isolation,
    ):
        sid = _make_user_session(app_module)
        _write_legacy_file(_runs_dir_isolation, "leg", [])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert set(body[0].keys()) == _LOCKED_KEYS

    def test_mixed_legacy_and_new_alphabetical(
        self, client, app_module, _runs_dir_isolation,
    ):
        sid = _make_user_session(app_module)
        _write_legacy_file(_runs_dir_isolation, "m_old", [_entry("p1")])
        ep.save_comparison_result("a_new", [_entry("p1")], source="batch")
        ep.save_comparison_result(
            "z_new", [_entry("p1")],
            source="directory", evidence_dir="/x",
        )
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert [r["run_id"] for r in body] == ["a_new", "m_old", "z_new"]
        by_id = {r["run_id"]: r for r in body}
        assert by_id["a_new"]["source"] == "batch"
        assert by_id["m_old"]["source"] is None
        assert by_id["z_new"]["evidence_dir"] == "/x"


class TestEndpointValueCorrectness:
    _PATH = "/elins/regression/runs"

    def test_response_matches_direct_listing(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("a", "b", "c"):
            ep.save_comparison_result(rid, [_entry("p1")])
        endpoint = client.get(self._PATH, headers=_auth(sid)).json()
        direct = ep.list_runs_with_metadata()
        assert endpoint == direct

    def test_engine_version_on_every_new_run(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("r1", "r2", "r3"):
            ep.save_comparison_result(rid, [_entry("p1")])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert all(r["engine_version"] == "elins-19" for r in body)

    def test_created_at_iso8601_on_every_new_run(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("a", "b"):
            ep.save_comparison_result(rid, [_entry("p1")])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        for row in body:
            assert re.match(
                r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",
                row["created_at"],
            )

    def test_endpoint_reflects_overwrite(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")], source="single")
        ep.save_comparison_result("r", [_entry("p1")], source="batch")
        body = client.get(self._PATH, headers=_auth(sid)).json()
        # Overwrite keeps a single row; metadata reflects latest save.
        assert len(body) == 1
        assert body[0]["source"] == "batch"

    def test_endpoint_reflects_delete(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.delete_run("a")
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert [r["run_id"] for r in body] == ["b"]


# ===========================================================================
# C. Integration — analyze_and_store path → listing reflects source/dir
# ===========================================================================
class TestIntegration:
    _PATH = "/elins/regression/runs"

    def _sp_pair_payload(self):
        sp = {
            "timeline_id": "sp_a",
            "points": [
                {"t": "t0",
                 "regime_competition": 0.5, "autocratization": 0.5,
                 "repression_index": 0.5, "digital_repression": 0.5,
                 "perceived_threat": 0.5, "fear_signal": 0.5,
                 "dissent_capacity": 0.5, "normative_constraint": 0.5,
                 "support_buffer": 0.5},
            ],
        }
        ec = {
            "timeline_id": "ec_a",
            "points": [
                {"t": "t0",
                 "economic_pressure": 0.5, "material_insecurity": 0.5,
                 "state_coercion": 0.5, "compliance_signal": 0.5,
                 "resistance_capacity": 0.5, "support_buffer": 0.5},
            ],
        }
        return sp, ec

    def _pair2(self, sp, ec):
        sp2 = dict(sp); sp2["timeline_id"] = "sp_b"
        ec2 = dict(ec); ec2["timeline_id"] = "ec_b"
        return sp2, ec2

    def test_after_directory_scan_listing_shows_directory(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "from_dir", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.get(self._PATH, headers=_auth(sid)).json()
        row = next(r for r in body if r["run_id"] == "from_dir")
        assert row["source"] == "directory"
        assert row["evidence_dir"] == str(tmp_path)

    def test_after_single_pair_listing_shows_single(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        sp, ec = self._sp_pair_payload()
        client.post(
            "/elins/regression/store",
            json={"run_id": "from_single", "pairs": [
                {"single_party_timeline": sp, "economic_timeline": ec},
            ]},
            headers=_auth(sid),
        )
        body = client.get(self._PATH, headers=_auth(sid)).json()
        row = next(r for r in body if r["run_id"] == "from_single")
        assert row["source"] == "single"

    def test_after_batch_listing_shows_batch(self, client, app_module):
        sid = _make_user_session(app_module)
        sp, ec = self._sp_pair_payload()
        sp2, ec2 = self._pair2(sp, ec)
        client.post(
            "/elins/regression/store",
            json={"run_id": "from_batch", "pairs": [
                {"single_party_timeline": sp,  "economic_timeline": ec},
                {"single_party_timeline": sp2, "economic_timeline": ec2},
            ]},
            headers=_auth(sid),
        )
        body = client.get(self._PATH, headers=_auth(sid)).json()
        row = next(r for r in body if r["run_id"] == "from_batch")
        assert row["source"] == "batch"

    def test_evidence_dir_preserved_via_endpoint_chain(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "edpath", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.get(self._PATH, headers=_auth(sid)).json()
        row = next(r for r in body if r["run_id"] == "edpath")
        assert row["evidence_dir"] == str(tmp_path)

    def test_engine_version_consistent_across_sources(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        sp, ec = self._sp_pair_payload()
        client.post(
            "/elins/regression/store",
            json={"run_id": "ev_single", "pairs": [
                {"single_party_timeline": sp, "economic_timeline": ec},
            ]},
            headers=_auth(sid),
        )
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "ev_dir", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.get(self._PATH, headers=_auth(sid)).json()
        for row in body:
            assert row["engine_version"] == "elins-19"

    def test_listing_stable_across_repeated_calls(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        sp, ec = self._sp_pair_payload()
        client.post(
            "/elins/regression/store",
            json={"run_id": "stable_a", "pairs": [
                {"single_party_timeline": sp, "economic_timeline": ec},
            ]},
            headers=_auth(sid),
        )
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "stable_b", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        a = client.get(self._PATH, headers=_auth(sid)).json()
        b = client.get(self._PATH, headers=_auth(sid)).json()
        assert a == b

    def test_three_distinct_sources_visible_together(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        sp, ec = self._sp_pair_payload()
        sp2, ec2 = self._pair2(sp, ec)
        # single
        client.post(
            "/elins/regression/store",
            json={"run_id": "i_single", "pairs": [
                {"single_party_timeline": sp, "economic_timeline": ec},
            ]},
            headers=_auth(sid),
        )
        # batch
        client.post(
            "/elins/regression/store",
            json={"run_id": "i_batch", "pairs": [
                {"single_party_timeline": sp,  "economic_timeline": ec},
                {"single_party_timeline": sp2, "economic_timeline": ec2},
            ]},
            headers=_auth(sid),
        )
        # directory
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "i_dir", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.get(self._PATH, headers=_auth(sid)).json()
        sources = {r["run_id"]: r["source"] for r in body}
        assert sources == {
            "i_single": "single",
            "i_batch":  "batch",
            "i_dir":    "directory",
        }


# ===========================================================================
# D. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_function_callable(self):
        assert callable(ep.list_runs_with_metadata)

    def test_listing_fields_constant_locked(self):
        # Unit 27/28: listing now includes notes / tags / archived
        # alongside the original Unit 20 metadata fields.
        assert ep._LISTING_FIELDS == (
            "run_id", "created_at", "source", "evidence_dir",
            "engine_version", "notes", "tags", "archived",
        )

    def test_function_returns_list_type(self):
        assert isinstance(ep.list_runs_with_metadata(), list)


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(ep.list_runs_with_metadata)

    def test_no_logging_in_listing(self):
        src = self._src()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_network_in_listing(self):
        src = self._src()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket"):
            assert forbidden not in src

    def test_no_randomness_in_listing(self):
        src = self._src()
        for forbidden in ("random.", "secrets.", "uuid."):
            assert forbidden not in src

    def test_no_llm_in_listing(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_listing_queries_sqlite_runs_table(self):
        """Unit 25: storage is now SQLite; the listing function executes
        a single ``SELECT ... FROM runs ORDER BY run_id`` rather than
        delegating to ``list_runs()`` + per-row ``load_comparison_result``.
        This test locks the new architecture: the source must contain
        the ``runs`` table reference and an ORDER BY clause."""
        src = self._src()
        assert "FROM runs" in src
        assert "ORDER BY run_id" in src
