"""
Tests for ELINS Unit 26 — filter + sort + paginate for
``GET /elins/regression/runs``.

Layered coverage (>= 60 tests, target ~70):
    A. Core helper — query_runs (in-process)
    B. Sort + order
    C. Pagination
    D. Validation
    E. Endpoint — GET /elins/regression/runs with query params
    F. Backward compatibility — Unit 20 shape preserved when no params
    G. Integration with composite / ordering / metadata
"""
from __future__ import annotations

import secrets
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


class _StubDT:
    """Hand out canned ISO timestamps for each save call."""
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
    """Inject canned ISO strings for the next N ``save_*`` calls.

    Patches the implementation module's ``datetime`` binding (Unit 25
    pattern); the parse helper for since/until uses ``_dt_module`` so
    it stays immune to this injection."""
    def _install(values):
        monkeypatch.setattr(ep_sql, "datetime", _StubDT(list(values)))
    return _install


def _seed_three_distinct(fixed_clock):
    """Save three runs at distinct timestamps with three distinct
    sources, used by many filter/sort tests."""
    fixed_clock([
        "2024-01-01T10:00:00+00:00",
        "2024-06-01T10:00:00+00:00",
        "2024-12-01T10:00:00+00:00",
    ])
    ep.save_comparison_result("alpha",   [], source="single")
    ep.save_comparison_result("bravo",   [], source="batch")
    ep.save_comparison_result(
        "charlie", [],
        source="directory", evidence_dir="/x/y",
    )


# ===========================================================================
# A. Core helper — query_runs
# ===========================================================================
class TestQueryRunsBasic:
    def test_returns_list(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        assert isinstance(ep.query_runs(), list)

    def test_returns_flat_dicts_with_locked_keys(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs()
        for row in out:
            assert set(row.keys()) == {
                "run_id", "created_at", "source",
                "evidence_dir", "engine_version",
                # Unit 27/28 — operator-utility fields always present.
                "notes", "tags", "archived",
            }

    def test_default_sort_alphabetical(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs()
        assert [r["run_id"] for r in out] == ["alpha", "bravo", "charlie"]

    def test_no_params_matches_list_runs_with_metadata(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        assert ep.query_runs() == ep.list_runs_with_metadata()

    def test_empty_database_returns_empty(self):
        assert ep.query_runs() == []


class TestQueryRunsFilterBySource:
    def test_filter_source_single(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(source="single")
        assert [r["run_id"] for r in out] == ["alpha"]

    def test_filter_source_batch(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(source="batch")
        assert [r["run_id"] for r in out] == ["bravo"]

    def test_filter_source_directory(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(source="directory")
        assert [r["run_id"] for r in out] == ["charlie"]

    def test_filter_source_matches_none(self, fixed_clock):
        # Only single-source runs exist; filtering for directory yields
        # an empty list.
        fixed_clock(["2024-01-01T10:00:00+00:00"])
        ep.save_comparison_result("only_single", [], source="single")
        assert ep.query_runs(source="directory") == []

    def test_filter_source_excludes_legacy_runs(
        self, _runs_dir_isolation, fixed_clock,
    ):
        """Legacy runs (metadata=None) don't have a source field, so
        filtering by source excludes them."""
        # One new run.
        fixed_clock(["2024-01-01T10:00:00+00:00"])
        ep.save_comparison_result("new", [], source="batch")
        # One legacy run via direct DB insert.
        import sqlite3, json
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
        out = ep.query_runs(source="batch")
        assert [r["run_id"] for r in out] == ["new"]


class TestQueryRunsFilterByTime:
    def test_since_filter_keeps_later(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(since="2024-05-01T00:00:00")
        assert [r["run_id"] for r in out] == ["bravo", "charlie"]

    def test_since_inclusive_boundary(self, fixed_clock):
        """since is inclusive — a run whose ts equals since must be kept."""
        fixed_clock(["2024-06-01T10:00:00+00:00"])
        ep.save_comparison_result("boundary", [], source="single")
        out = ep.query_runs(since="2024-06-01T10:00:00")
        assert [r["run_id"] for r in out] == ["boundary"]

    def test_until_filter_keeps_earlier(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(until="2024-07-01T00:00:00")
        assert [r["run_id"] for r in out] == ["alpha", "bravo"]

    def test_until_exclusive_boundary(self, fixed_clock):
        """until is exclusive — a run whose ts equals until is dropped."""
        fixed_clock(["2024-06-01T10:00:00+00:00"])
        ep.save_comparison_result("boundary", [], source="single")
        out = ep.query_runs(until="2024-06-01T10:00:00")
        assert out == []

    def test_since_and_until_window(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(
            since="2024-05-01T00:00:00",
            until="2024-11-01T00:00:00",
        )
        assert [r["run_id"] for r in out] == ["bravo"]

    def test_time_filter_excludes_legacy(
        self, _runs_dir_isolation, fixed_clock,
    ):
        fixed_clock(["2024-01-01T10:00:00+00:00"])
        ep.save_comparison_result("new", [], source="batch")
        import sqlite3, json
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
        out = ep.query_runs(since="2020-01-01T00:00:00")
        assert [r["run_id"] for r in out] == ["new"]

    def test_naive_timestamp_interpreted_as_utc(self, fixed_clock):
        fixed_clock(["2024-06-01T10:00:00+00:00"])
        ep.save_comparison_result("ts1", [], source="single")
        # Naive since equals exact stored time → inclusive → kept.
        out = ep.query_runs(since="2024-06-01T10:00:00")
        assert [r["run_id"] for r in out] == ["ts1"]

    def test_tz_aware_input_works(self, fixed_clock):
        fixed_clock(["2024-06-01T10:00:00+00:00"])
        ep.save_comparison_result("ts1", [], source="single")
        out = ep.query_runs(since="2024-06-01T10:00:00+00:00")
        assert [r["run_id"] for r in out] == ["ts1"]


class TestQueryRunsCombinedFilters:
    def test_source_and_since(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(source="batch", since="2024-05-01T00:00:00")
        assert [r["run_id"] for r in out] == ["bravo"]

    def test_source_and_until(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(source="single", until="2024-07-01T00:00:00")
        assert [r["run_id"] for r in out] == ["alpha"]

    def test_source_and_window(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        # Window includes Bravo (batch), Charlie (directory). Filter to
        # batch only.
        out = ep.query_runs(
            source="batch",
            since="2024-05-01T00:00:00",
            until="2024-12-31T00:00:00",
        )
        assert [r["run_id"] for r in out] == ["bravo"]

    def test_filter_yielding_empty(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(
            source="single",
            since="2025-01-01T00:00:00",
        )
        assert out == []


# ===========================================================================
# B. Sort + order
# ===========================================================================
class TestQueryRunsSortRunId:
    def test_sort_run_id_asc(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(sort="run_id", order="asc")
        assert [r["run_id"] for r in out] == ["alpha", "bravo", "charlie"]

    def test_sort_run_id_desc(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(sort="run_id", order="desc")
        assert [r["run_id"] for r in out] == ["charlie", "bravo", "alpha"]

    def test_default_sort_is_run_id(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        # No sort param → run_id ASC.
        out = ep.query_runs()
        assert [r["run_id"] for r in out] == ["alpha", "bravo", "charlie"]


class TestQueryRunsSortCreatedAt:
    def test_sort_created_at_asc(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        # alpha=Jan, bravo=Jun, charlie=Dec → asc order matches.
        out = ep.query_runs(sort="created_at", order="asc")
        assert [r["run_id"] for r in out] == ["alpha", "bravo", "charlie"]

    def test_sort_created_at_desc(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        out = ep.query_runs(sort="created_at", order="desc")
        assert [r["run_id"] for r in out] == ["charlie", "bravo", "alpha"]

    def test_sort_created_at_with_legacy_legacy_goes_last(
        self, _runs_dir_isolation, fixed_clock,
    ):
        """Legacy runs (no timestamp) always go last regardless of
        order — they have no comparable signal."""
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-06-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("new_a", [], source="batch")
        ep.save_comparison_result("new_b", [], source="batch")
        import sqlite3, json
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

        asc = ep.query_runs(sort="created_at", order="asc")
        assert [r["run_id"] for r in asc] == ["new_a", "new_b", "leg"]

        desc = ep.query_runs(sort="created_at", order="desc")
        # In desc, timestamped runs come first reversed, then legacy.
        assert [r["run_id"] for r in desc] == ["new_b", "new_a", "leg"]

    def test_sort_created_at_ties_broken_by_run_id(self, fixed_clock):
        fixed_clock([
            "2024-06-01T10:00:00+00:00",
            "2024-06-01T10:00:00+00:00",
            "2024-06-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("zeta",  [], source="single")
        ep.save_comparison_result("apple", [], source="single")
        ep.save_comparison_result("mid",   [], source="single")
        out = ep.query_runs(sort="created_at", order="asc")
        assert [r["run_id"] for r in out] == ["apple", "mid", "zeta"]


class TestQueryRunsStability:
    def test_repeated_calls_byte_equal(self, fixed_clock):
        _seed_three_distinct(fixed_clock)
        a = ep.query_runs(source="batch")
        b = ep.query_runs(source="batch")
        assert a == b


# ===========================================================================
# C. Pagination
# ===========================================================================
class TestQueryRunsPagination:
    def _seed_seven(self, fixed_clock):
        fixed_clock([
            f"2024-06-{i:02d}T10:00:00+00:00" for i in range(1, 8)
        ])
        for rid in ("g", "f", "e", "d", "c", "b", "a"):
            ep.save_comparison_result(rid, [], source="single")

    def test_limit_only(self, fixed_clock):
        self._seed_seven(fixed_clock)
        out = ep.query_runs(limit=3)
        assert [r["run_id"] for r in out] == ["a", "b", "c"]

    def test_offset_only(self, fixed_clock):
        self._seed_seven(fixed_clock)
        out = ep.query_runs(offset=4)
        assert [r["run_id"] for r in out] == ["e", "f", "g"]

    def test_limit_and_offset(self, fixed_clock):
        self._seed_seven(fixed_clock)
        out = ep.query_runs(limit=2, offset=2)
        assert [r["run_id"] for r in out] == ["c", "d"]

    def test_offset_beyond_returns_empty(self, fixed_clock):
        self._seed_seven(fixed_clock)
        out = ep.query_runs(offset=99)
        assert out == []

    def test_limit_greater_than_available(self, fixed_clock):
        self._seed_seven(fixed_clock)
        out = ep.query_runs(limit=999)
        assert len(out) == 7

    def test_pagination_applied_after_filter(self, fixed_clock):
        """Limit/offset run AFTER source/since filtering."""
        fixed_clock([f"2024-06-{i:02d}T10:00:00+00:00" for i in range(1, 6)])
        ep.save_comparison_result("a", [], source="single")
        ep.save_comparison_result("b", [], source="batch")
        ep.save_comparison_result("c", [], source="single")
        ep.save_comparison_result("d", [], source="batch")
        ep.save_comparison_result("e", [], source="single")
        # Filter to single → [a, c, e]. Limit 2 → [a, c].
        out = ep.query_runs(source="single", limit=2)
        assert [r["run_id"] for r in out] == ["a", "c"]

    def test_pagination_applied_after_sort(self, fixed_clock):
        self._seed_seven(fixed_clock)
        out = ep.query_runs(order="desc", limit=2)
        assert [r["run_id"] for r in out] == ["g", "f"]


# ===========================================================================
# D. Validation
# ===========================================================================
class TestQueryRunsValidation:
    def test_invalid_source_raises(self):
        with pytest.raises(ValueError, match="source must be"):
            ep.query_runs(source="hacker")

    def test_invalid_since_raises(self):
        with pytest.raises(ValueError, match="since"):
            ep.query_runs(since="not-a-date")

    def test_invalid_until_raises(self):
        with pytest.raises(ValueError, match="until"):
            ep.query_runs(until="not-a-date")

    def test_invalid_sort_raises(self):
        with pytest.raises(ValueError, match="sort"):
            ep.query_runs(sort="unknown")

    def test_invalid_order_raises(self):
        with pytest.raises(ValueError, match="order"):
            ep.query_runs(order="sideways")

    def test_zero_limit_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            ep.query_runs(limit=0)

    def test_negative_offset_raises(self):
        with pytest.raises(ValueError, match=">= 0"):
            ep.query_runs(offset=-1)

    def test_bool_limit_raises(self):
        with pytest.raises(ValueError, match="limit"):
            ep.query_runs(limit=True)

    def test_string_offset_raises(self):
        with pytest.raises(ValueError, match="offset"):
            ep.query_runs(offset="0")


# ===========================================================================
# E. Endpoint — GET /elins/regression/runs with query params
# ===========================================================================
class TestEndpoint:
    _PATH = "/elins/regression/runs"

    def _seed(self, fixed_clock):
        _seed_three_distinct(fixed_clock)

    def test_endpoint_source_filter(self, client, app_module, fixed_clock):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(
            self._PATH + "?source=batch", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["bravo"]

    def test_endpoint_since_filter(self, client, app_module, fixed_clock):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(
            self._PATH + "?since=2024-05-01T00:00:00", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["bravo", "charlie"]

    def test_endpoint_until_filter(self, client, app_module, fixed_clock):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(
            self._PATH + "?until=2024-07-01T00:00:00", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["alpha", "bravo"]

    def test_endpoint_combined_filters(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(
            self._PATH + "?source=batch&since=2024-01-01T00:00:00",
            headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["bravo"]

    def test_endpoint_sort_run_id_desc(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(
            self._PATH + "?sort=run_id&order=desc", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["charlie", "bravo", "alpha"]

    def test_endpoint_sort_created_at_asc(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(
            self._PATH + "?sort=created_at&order=asc",
            headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["alpha", "bravo", "charlie"]

    def test_endpoint_sort_created_at_desc(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(
            self._PATH + "?sort=created_at&order=desc",
            headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["charlie", "bravo", "alpha"]

    def test_endpoint_limit_offset(self, client, app_module, fixed_clock):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(
            self._PATH + "?limit=1&offset=1", headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in body] == ["bravo"]

    def test_endpoint_invalid_source_returns_400(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        resp = client.get(
            self._PATH + "?source=hacker", headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_endpoint_invalid_since_returns_400(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        resp = client.get(
            self._PATH + "?since=not-a-date", headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_endpoint_invalid_sort_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            self._PATH + "?sort=garbage", headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_endpoint_invalid_order_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            self._PATH + "?order=sideways", headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_endpoint_invalid_limit_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            self._PATH + "?limit=0", headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_endpoint_invalid_offset_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            self._PATH + "?offset=-1", headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_endpoint_unauth_returns_401(self, client, app_module):
        resp = client.get(self._PATH + "?source=batch")
        assert resp.status_code == 401

    def test_endpoint_response_keys_locked(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._seed(fixed_clock)
        body = client.get(self._PATH, headers=_auth(sid)).json()
        for row in body:
            assert set(row.keys()) == {
                "run_id", "created_at", "source",
                "evidence_dir", "engine_version",
                # Unit 27/28 — operator-utility fields always present.
                "notes", "tags", "archived",
            }


# ===========================================================================
# F. Backward compatibility — Unit 20 shape preserved when no params
# ===========================================================================
class TestBackwardCompat:
    _PATH = "/elins/regression/runs"

    def test_no_params_returns_bare_list(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("c", "a", "b"):
            ep.save_comparison_result(rid, [])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert isinstance(body, list)
        assert [r["run_id"] for r in body] == ["a", "b", "c"]

    def test_no_params_keys_include_operator_utilities(
        self, client, app_module,
    ):
        """Unit 27/28: listing rows now also include notes / tags /
        archived. The Unit 20 backward-compat clause is preserved at
        the data level (the original 5 metadata fields keep their
        names and meanings); the row simply carries 3 extra
        operator-utility fields too."""
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert set(body[0].keys()) == {
            "run_id", "created_at", "source",
            "evidence_dir", "engine_version",
            "notes", "tags", "archived",
        }

    def test_no_params_matches_list_runs_with_metadata(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        for rid in ("a", "b", "c"):
            ep.save_comparison_result(rid, [])
        body = client.get(self._PATH, headers=_auth(sid)).json()
        assert body == ep.list_runs_with_metadata()


# ===========================================================================
# G. Integration — composite / ordering / metadata still work
# ===========================================================================
class TestIntegration:
    def test_filtered_list_run_ids_can_feed_composite(
        self, client, app_module, fixed_clock,
    ):
        """The filtered listing surface is meant to drive dashboards;
        a typical workflow is filter by source → take those run_ids →
        feed them to the composite endpoint. End-to-end works."""
        sid = _make_user_session(app_module)
        fixed_clock(["2024-01-01T10:00:00+00:00"])
        ep.save_comparison_result(
            "alpha",
            [{"pair_id": "p1", "single_party_score": 5,
              "economic_coercion_score": 5,
              "single_party_band": "Acceptable",
              "economic_coercion_band": "Acceptable"}],
            source="single",
        )
        listing = client.get(
            "/elins/regression/runs?source=single",
            headers=_auth(sid),
        ).json()
        assert [r["run_id"] for r in listing] == ["alpha"]
        composite = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": [r["run_id"] for r in listing]},
            headers=_auth(sid),
        ).json()
        assert composite["run_ids"] == ["alpha"]

    def test_metadata_preserved_through_filter(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        _seed_three_distinct(fixed_clock)
        body = client.get(
            "/elins/regression/runs?source=directory",
            headers=_auth(sid),
        ).json()
        assert body[0]["evidence_dir"] == "/x/y"
        assert body[0]["engine_version"] == "elins-19"

    def test_filter_parity_with_query_runs_helper(
        self, client, app_module, fixed_clock,
    ):
        """Endpoint must be a thin wrapper around ``query_runs`` —
        same args → same output."""
        sid = _make_user_session(app_module)
        _seed_three_distinct(fixed_clock)
        endpoint = client.get(
            "/elins/regression/runs?source=batch&sort=created_at"
            "&order=desc",
            headers=_auth(sid),
        ).json()
        direct = ep.query_runs(
            source="batch", sort="created_at", order="desc",
        )
        assert endpoint == direct

    def test_ordering_endpoint_unaffected_by_filter_changes(
        self, client, app_module, fixed_clock,
    ):
        """Unit 23 timestamp ordering on the multi-run analytics
        endpoints is independent of Unit 26's listing filter."""
        sid = _make_user_session(app_module)
        fixed_clock([
            "2024-01-01T10:00:00+00:00",
            "2024-06-01T10:00:00+00:00",
        ])
        ep.save_comparison_result("r1", [
            {"pair_id": "p1", "single_party_score": 5,
             "economic_coercion_score": 5,
             "single_party_band": "Acceptable",
             "economic_coercion_band": "Acceptable"},
        ])
        ep.save_comparison_result("r2", [
            {"pair_id": "p1", "single_party_score": 9,
             "economic_coercion_score": 5,
             "single_party_band": "Acceptable",
             "economic_coercion_band": "Acceptable"},
        ])
        composite = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["r2", "r1"]}, headers=_auth(sid),
        ).json()
        # Composite uses timestamp ordering regardless of caller input.
        assert composite["run_ids"] == ["r1", "r2"]
