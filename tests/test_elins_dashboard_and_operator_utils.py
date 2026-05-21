"""
Tests for ELINS Unit 27 + Unit 28 — dashboard composite + operator
utilities (notes / tags / rename / archive).

Layered coverage (>= 80 tests, target ~90):
    A. Dashboard single-run
    B. Dashboard multi-run
    C. Notes CRUD
    D. Tags CRUD
    E. Rename
    F. Archive / unarchive
    G. Listing with notes / tags / archived
    H. Backward compatibility (analytics + envelope unchanged)
"""
from __future__ import annotations

import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_persistence_sqlite as ep_sql
from elins_run_dashboard import dashboard_for_run_ids


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


class _StubDT:
    def __init__(self, iso_values):
        self._iter = iter(iso_values)

    def now(self, tz=None):
        v = next(self._iter)

        class _T:
            def __init__(self, iso): self._iso = iso
            def isoformat(self): return self._iso
        return _T(v)


@pytest.fixture
def fixed_clock(monkeypatch):
    def _install(values):
        monkeypatch.setattr(ep_sql, "datetime", _StubDT(list(values)))
    return _install


# ===========================================================================
# A. Dashboard single-run
# ===========================================================================
class TestDashboardSingleRun:
    def test_returns_dict(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = dashboard_for_run_ids(["solo"])
        assert isinstance(out, dict)

    def test_top_level_keys_locked(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = dashboard_for_run_ids(["solo"])
        assert set(out.keys()) == {
            "run_ids", "metadata", "summary",
            "drift", "notes", "tags", "archived",
        }

    def test_drift_section_has_four_sub_keys_all_empty(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = dashboard_for_run_ids(["solo"])
        assert set(out["drift"].keys()) == {
            "direction", "magnitude", "severity", "series",
        }
        for v in out["drift"].values():
            assert v == {}

    def test_single_run_metadata_aligned(self):
        ep.save_comparison_result("solo", [_entry("p1")], source="batch")
        out = dashboard_for_run_ids(["solo"])
        assert out["metadata"][0]["source"] == "batch"

    def test_single_run_summary_uses_unit14_shape(self):
        ep.save_comparison_result(
            "solo", [_entry("p1"), _entry("p2")],
        )
        out = dashboard_for_run_ids(["solo"])
        assert out["summary"]["total_pairs"] == 2

    def test_notes_array_one_entry(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        ep.set_notes("solo", "my note")
        out = dashboard_for_run_ids(["solo"])
        assert out["notes"] == ["my note"]

    def test_tags_array_one_entry(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        ep.set_tags("solo", ["alpha", "beta"])
        out = dashboard_for_run_ids(["solo"])
        assert out["tags"] == [["alpha", "beta"]]

    def test_archived_array_one_entry(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        ep.set_archived("solo", True)
        out = dashboard_for_run_ids(["solo"])
        assert out["archived"] == [True]

    def test_get_endpoint_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        resp = client.get(
            "/elins/regression/run/dashboard/solo",
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_get_endpoint_missing_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            "/elins/regression/run/dashboard/ghost",
            headers=_auth(sid),
        )
        assert resp.status_code == 404


# ===========================================================================
# B. Dashboard multi-run
# ===========================================================================
class TestDashboardMultiRun:
    def test_two_run_keys_present(self, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-02-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        out = dashboard_for_run_ids(["a", "b"])
        assert set(out.keys()) == {
            "run_ids", "metadata", "summary",
            "drift", "notes", "tags", "archived",
        }

    def test_multi_run_drift_populated(self, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-02-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        out = dashboard_for_run_ids(["a", "b"])
        assert out["drift"]["direction"]["trending_up"] == ["p1"]
        assert out["drift"]["magnitude"]["p1"]["single_party"]["max_swing"] == 4

    def test_multi_run_run_ids_timestamp_sorted(self, fixed_clock):
        fixed_clock([
            "2024-02-01T10:00:00+00:00",  # b is later
            "2024-01-01T10:00:00+00:00",  # a is earlier
        ])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        out = dashboard_for_run_ids(["b", "a"])
        assert out["run_ids"] == ["a", "b"]

    def test_multi_run_metadata_aligned_to_sorted(self, fixed_clock):
        fixed_clock([
            "2024-02-01T10:00:00+00:00",
            "2024-01-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("b", [_entry("p1")], source="batch")
        ep.save_comparison_result("a", [_entry("p1")], source="single")
        out = dashboard_for_run_ids(["b", "a"])
        # Sorted: [a, b] → metadata[0] is a's, metadata[1] is b's.
        assert out["metadata"][0]["source"] == "single"
        assert out["metadata"][1]["source"] == "batch"

    def test_multi_run_notes_aligned_to_sorted(self, fixed_clock):
        fixed_clock([
            "2024-02-01T10:00:00+00:00",
            "2024-01-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.set_notes("a", "earlier")
        ep.set_notes("b", "later")
        out = dashboard_for_run_ids(["b", "a"])
        # Sorted: [a, b]
        assert out["notes"] == ["earlier", "later"]

    def test_multi_run_summary_uses_unit18_shape(self, fixed_clock):
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-02-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        out = dashboard_for_run_ids(["a", "b"])
        assert "runs" in out["summary"]
        assert set(out["summary"]["runs"].keys()) == {"a", "b"}

    def test_post_endpoint_multi_run_returns_200(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-02-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        resp = client.post(
            "/elins/regression/run/dashboard",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_post_endpoint_empty_run_ids_returns_400(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/run/dashboard",
            json={"run_ids": []}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_post_endpoint_missing_run_returns_404(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("present", [_entry("p1")])
        resp = client.post(
            "/elins/regression/run/dashboard",
            json={"run_ids": ["present", "ghost"]}, headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_post_endpoint_unauth_returns_401(self, client):
        resp = client.post(
            "/elins/regression/run/dashboard",
            json={"run_ids": ["x"]},
        )
        assert resp.status_code == 401


# ===========================================================================
# C. Notes CRUD
# ===========================================================================
class TestNotesCRUD:
    def test_default_notes_is_none(self):
        ep.save_comparison_result("r", [])
        assert ep.get_notes("r") is None

    def test_set_notes_then_get(self):
        ep.save_comparison_result("r", [])
        ep.set_notes("r", "hello world")
        assert ep.get_notes("r") == "hello world"

    def test_clear_notes_with_none(self):
        ep.save_comparison_result("r", [])
        ep.set_notes("r", "first")
        ep.set_notes("r", None)
        assert ep.get_notes("r") is None

    def test_get_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            ep.get_notes("ghost")

    def test_set_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            ep.set_notes("ghost", "x")

    def test_set_notes_rejects_int(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match="notes must be"):
            ep.set_notes("r", 42)

    def test_notes_get_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        ep.set_notes("r", "from helper")
        body = client.get(
            "/elins/regression/run/r/notes", headers=_auth(sid),
        ).json()
        assert body == {"run_id": "r", "notes": "from helper"}

    def test_notes_set_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        resp = client.post(
            "/elins/regression/run/r/notes",
            json={"notes": "via endpoint"}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json() == {"run_id": "r", "notes": "via endpoint"}
        assert ep.get_notes("r") == "via endpoint"

    def test_notes_set_endpoint_clears_with_null(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        ep.set_notes("r", "first")
        resp = client.post(
            "/elins/regression/run/r/notes",
            json={"notes": None}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["notes"] is None

    def test_notes_set_endpoint_404_for_missing(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/run/ghost/notes",
            json={"notes": "x"}, headers=_auth(sid),
        )
        assert resp.status_code == 404


# ===========================================================================
# D. Tags CRUD
# ===========================================================================
class TestTagsCRUD:
    def test_default_tags_is_empty_list(self):
        ep.save_comparison_result("r", [])
        assert ep.get_tags("r") == []

    def test_set_tags_then_get(self):
        ep.save_comparison_result("r", [])
        ep.set_tags("r", ["alpha", "beta"])
        assert ep.get_tags("r") == ["alpha", "beta"]

    def test_clear_tags_with_empty_list(self):
        ep.save_comparison_result("r", [])
        ep.set_tags("r", ["x"])
        ep.set_tags("r", [])
        assert ep.get_tags("r") == []

    def test_get_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            ep.get_tags("ghost")

    def test_set_missing_run_raises(self):
        with pytest.raises(FileNotFoundError):
            ep.set_tags("ghost", ["x"])

    def test_set_tags_rejects_non_list(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match="tags must be a list"):
            ep.set_tags("r", "alpha")

    def test_set_tags_rejects_non_string_element(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match="tags\\[1\\]"):
            ep.set_tags("r", ["alpha", 42])

    def test_tags_get_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        ep.set_tags("r", ["a", "b"])
        body = client.get(
            "/elins/regression/run/r/tags", headers=_auth(sid),
        ).json()
        assert body == {"run_id": "r", "tags": ["a", "b"]}

    def test_tags_set_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        resp = client.post(
            "/elins/regression/run/r/tags",
            json={"tags": ["x", "y"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json() == {"run_id": "r", "tags": ["x", "y"]}

    def test_tags_set_endpoint_404_for_missing(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/run/ghost/tags",
            json={"tags": ["x"]}, headers=_auth(sid),
        )
        assert resp.status_code == 404


# ===========================================================================
# E. Rename
# ===========================================================================
class TestRename:
    def test_rename_moves_row(self):
        ep.save_comparison_result("old", [_entry("p1", sp=5)])
        ep.rename_run("old", "new")
        with pytest.raises(FileNotFoundError):
            ep.load_comparison_result("old")
        loaded = ep.load_comparison_result("new")
        assert loaded["result"] == [_entry("p1", sp=5)]

    def test_rename_preserves_metadata(self):
        ep.save_comparison_result(
            "old", [], source="directory", evidence_dir="/x",
        )
        ep.rename_run("old", "new")
        meta = ep.load_comparison_result("new")["metadata"]
        assert meta["source"] == "directory"
        assert meta["evidence_dir"] == "/x"

    def test_rename_preserves_notes(self):
        ep.save_comparison_result("old", [])
        ep.set_notes("old", "important")
        ep.rename_run("old", "new")
        assert ep.get_notes("new") == "important"

    def test_rename_preserves_tags(self):
        ep.save_comparison_result("old", [])
        ep.set_tags("old", ["t1", "t2"])
        ep.rename_run("old", "new")
        assert ep.get_tags("new") == ["t1", "t2"]

    def test_rename_preserves_archived(self):
        ep.save_comparison_result("old", [])
        ep.set_archived("old", True)
        ep.rename_run("old", "new")
        assert ep.get_archived("new") is True

    def test_rename_same_id_is_noop(self):
        ep.save_comparison_result("r", [_entry("p1")])
        ep.rename_run("r", "r")
        assert ep.load_comparison_result("r")["result"] == [_entry("p1")]

    def test_rename_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            ep.rename_run("ghost", "new")

    def test_rename_collision_raises(self):
        ep.save_comparison_result("a", [])
        ep.save_comparison_result("b", [])
        with pytest.raises(ValueError, match="already exists"):
            ep.rename_run("a", "b")

    def test_rename_endpoint_success(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("old", [])
        resp = client.post(
            "/elins/regression/run/old/rename",
            json={"new_run_id": "new"}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json() == {
            "old_run_id": "old", "new_run_id": "new",
        }

    def test_rename_endpoint_collision_returns_400(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [])
        ep.save_comparison_result("b", [])
        resp = client.post(
            "/elins/regression/run/a/rename",
            json={"new_run_id": "b"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_rename_endpoint_missing_returns_404(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/run/ghost/rename",
            json={"new_run_id": "new"}, headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_rename_endpoint_malformed_new_id_returns_400(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("old", [])
        resp = client.post(
            "/elins/regression/run/old/rename",
            json={"new_run_id": "bad$id"}, headers=_auth(sid),
        )
        assert resp.status_code == 400


# ===========================================================================
# F. Archive / unarchive
# ===========================================================================
class TestArchive:
    def test_default_not_archived(self):
        ep.save_comparison_result("r", [])
        assert ep.get_archived("r") is False

    def test_archive_sets_flag(self):
        ep.save_comparison_result("r", [])
        ep.set_archived("r", True)
        assert ep.get_archived("r") is True

    def test_unarchive_clears_flag(self):
        ep.save_comparison_result("r", [])
        ep.set_archived("r", True)
        ep.set_archived("r", False)
        assert ep.get_archived("r") is False

    def test_archived_excluded_from_default_listing(self):
        ep.save_comparison_result("kept", [])
        ep.save_comparison_result("dropped", [])
        ep.set_archived("dropped", True)
        out = ep.query_runs()
        assert [r["run_id"] for r in out] == ["kept"]

    def test_archived_included_with_flag(self):
        ep.save_comparison_result("a", [])
        ep.save_comparison_result("b", [])
        ep.set_archived("b", True)
        out = ep.query_runs(include_archived=True)
        assert sorted([r["run_id"] for r in out]) == ["a", "b"]

    def test_set_archived_rejects_non_bool(self):
        ep.save_comparison_result("r", [])
        with pytest.raises(ValueError, match="flag must be"):
            ep.set_archived("r", 1)

    def test_archive_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        resp = client.post(
            "/elins/regression/run/r/archive", headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json() == {"run_id": "r", "archived": True}

    def test_unarchive_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        ep.set_archived("r", True)
        resp = client.post(
            "/elins/regression/run/r/unarchive", headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json() == {"run_id": "r", "archived": False}

    def test_archive_endpoint_missing_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/run/ghost/archive", headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_unarchive_endpoint_missing_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/run/ghost/unarchive", headers=_auth(sid),
        )
        assert resp.status_code == 404


# ===========================================================================
# G. Listing with notes / tags / archived
# ===========================================================================
class TestListingExtensions:
    def test_listing_row_includes_notes(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        ep.set_notes("r", "hello")
        body = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        assert body[0]["notes"] == "hello"

    def test_listing_row_includes_tags(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        ep.set_tags("r", ["foo", "bar"])
        body = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        assert body[0]["tags"] == ["foo", "bar"]

    def test_listing_row_includes_archived(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        body = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        assert body[0]["archived"] is False

    def test_listing_hides_archived_by_default(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("active", [])
        ep.save_comparison_result("hidden", [])
        ep.set_archived("hidden", True)
        body = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["active"]

    def test_listing_include_archived_query_param(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("active", [])
        ep.save_comparison_result("hidden", [])
        ep.set_archived("hidden", True)
        body = client.get(
            "/elins/regression/runs?include_archived=true",
            headers=_auth(sid),
        ).json()
        assert sorted([r["run_id"] for r in body]) == ["active", "hidden"]

    def test_listing_include_archived_false_explicit(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("active", [])
        ep.save_comparison_result("hidden", [])
        ep.set_archived("hidden", True)
        body = client.get(
            "/elins/regression/runs?include_archived=false",
            headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["active"]

    def test_listing_filter_plus_archived(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [], source="single")
        ep.save_comparison_result("b", [], source="batch")
        ep.set_archived("b", True)
        # Filter by source=batch, default hides archived → empty.
        body = client.get(
            "/elins/regression/runs?source=batch", headers=_auth(sid),
        ).json()
        assert body == []
        # With include_archived → batch row reappears.
        body2 = client.get(
            "/elins/regression/runs?source=batch&include_archived=true",
            headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body2] == ["b"]

    def test_legacy_run_has_default_operator_fields(
        self, _runs_dir_isolation,
    ):
        import json, sqlite3
        ep_sql._ensure_init(str(_runs_dir_isolation / ep._DB_FILENAME))
        conn = sqlite3.connect(str(_runs_dir_isolation / ep._DB_FILENAME))
        try:
            conn.execute(
                "INSERT INTO runs (run_id, envelope_json) VALUES (?, ?)",
                ("leg", json.dumps(
                    {"metadata": None, "result": []},
                    sort_keys=True, ensure_ascii=False,
                )),
            )
            conn.commit()
        finally:
            conn.close()
        out = ep.list_runs_with_metadata()
        leg = next(r for r in out if r["run_id"] == "leg")
        assert leg["notes"] is None
        assert leg["tags"] == []
        assert leg["archived"] is False

    def test_listing_alphabetical_order_preserved(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        for rid in ("zeta", "alpha", "mid"):
            ep.save_comparison_result(rid, [])
        body = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["alpha", "mid", "zeta"]

    def test_listing_unaffected_by_notes_content(
        self, client, app_module,
    ):
        """Notes are descriptive only — they should not change which
        runs appear in the listing."""
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        before = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        ep.set_notes("r", "x" * 1000)
        after = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in before] == [r["run_id"] for r in after]


# ===========================================================================
# H. Backward compatibility (analytics + envelope unchanged)
# ===========================================================================
class TestBackwardCompat:
    def test_envelope_shape_unchanged_after_set_notes(self):
        """Operator utilities live in separate columns; the envelope
        JSON (analytics payload) is never touched."""
        ep.save_comparison_result("r", [_entry("p1", sp=5)])
        before = ep.load_comparison_result("r")
        ep.set_notes("r", "x")
        ep.set_tags("r", ["a", "b"])
        ep.set_archived("r", True)
        after = ep.load_comparison_result("r")
        assert before == after

    def test_diff_analytics_unaffected_by_archive(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        # Archive one — the diff endpoint must still return the same
        # delta. Operator utility flags are orthogonal to analytics.
        ep.set_archived("a", True)
        resp = client.get(
            "/elins/regression/diff?run_a=a&run_b=b", headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["changed"][0]["pair_id"] == "p1"

    def test_drift_unaffected_by_archive_flag(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-02-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=9)])
        ep.set_archived("a", True)
        ep.set_archived("b", True)
        # Drift wrappers don't filter by archived — analytic semantics
        # are unchanged.
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["trending_up"] == ["p1"]

    def test_composite_unaffected_by_operator_utilities(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-02-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        before = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        # Set notes/tags/archive on both runs.
        ep.set_notes("a", "x")
        ep.set_tags("a", ["q"])
        ep.set_archived("a", True)
        after = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert before == after

    def test_listing_endpoint_still_returns_bare_array(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [])
        body = client.get(
            "/elins/regression/runs", headers=_auth(sid),
        ).json()
        assert isinstance(body, list)

    def test_unit_22_composite_endpoint_unchanged_shape(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-02-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        body = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        # Composite's flat top-level shape unchanged — no nested
        # "drift" key (that's Unit 27 dashboard).
        assert set(body.keys()) == {
            "run_ids", "metadata", "summary",
            "direction", "magnitude", "severity", "series",
        }
        assert "drift" not in body
        assert "notes" not in body

    def test_dashboard_endpoint_does_not_alter_envelope(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1", sp=5)])
        before = ep.load_comparison_result("r")
        # Hit dashboard endpoint several times.
        for _ in range(3):
            client.get(
                "/elins/regression/run/dashboard/r",
                headers=_auth(sid),
            )
        after = ep.load_comparison_result("r")
        assert before == after

    def test_save_load_round_trip_unaffected(self):
        ep.save_comparison_result("r", [_entry("p1", sp=5)])
        ep.set_notes("r", "x")
        ep.set_tags("r", ["a"])
        loaded = ep.load_comparison_result("r")
        # The result list is exactly what was saved — notes/tags don't
        # leak into the envelope.
        assert loaded["result"] == [_entry("p1", sp=5)]

    def test_delete_run_clears_operator_utilities_too(self):
        """Deleting a run removes the row entirely — so subsequent
        notes/tags lookups raise FileNotFoundError."""
        ep.save_comparison_result("r", [])
        ep.set_notes("r", "x")
        ep.set_tags("r", ["a"])
        ep.delete_run("r")
        with pytest.raises(FileNotFoundError):
            ep.get_notes("r")
        with pytest.raises(FileNotFoundError):
            ep.get_tags("r")

    def test_existing_metadata_endpoint_still_works(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [], source="batch")
        resp = client.get(
            "/elins/regression/run/r/metadata", headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["source"] == "batch"


# ===========================================================================
# Module surface sanity
# ===========================================================================
class TestModuleSurface:
    def test_facade_exports_operator_utilities(self):
        for name in (
            "get_notes", "set_notes",
            "get_tags", "set_tags",
            "get_archived", "set_archived",
            "rename_run",
        ):
            assert hasattr(ep, name), f"facade missing: {name}"
            assert callable(getattr(ep, name))

    def test_dashboard_module_callable(self):
        assert callable(dashboard_for_run_ids)

    def test_dashboard_drift_subkeys_locked(self):
        from elins_run_dashboard import _DRIFT_SUBKEYS
        assert _DRIFT_SUBKEYS == (
            "direction", "magnitude", "severity", "series",
        )
