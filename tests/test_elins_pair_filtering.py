"""
Tests for ELINS Unit 21 — pair filtering + pagination for per-pair endpoints.

Layered coverage (>= 70 tests, target ~80):
    A. Core filtering — apply_pair_filters on {pair_id: ...} dicts
    B. Pagination — limit / offset / combined
    C. Validation — bad inputs through validate_pair_filters
    D. Drift bucket variant — apply_pair_filters_to_drift
    E. Diff variant — apply_pair_filters_to_diff
    F. Endpoint integration — query params wired into 5 endpoints
    G. Mixed analytics — magnitude + severity + series filter identically
    H. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_pair_filtering as pf
import elins_persistence as ep


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


def _entry(pair_id, *, sp=5, ec=5,
           sp_band="Acceptable", ec_band="Acceptable") -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp,
        "economic_coercion_score": ec,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _store_pairs(rid_a: str, rid_b: str, pair_ids):
    """Save two runs each with the given pair_ids (sp moves +3 between
    them so drift is consistently 'trending_up' for every pair)."""
    ep.save_comparison_result(
        rid_a, [_entry(p, sp=5, ec=5) for p in pair_ids],
    )
    ep.save_comparison_result(
        rid_b, [_entry(p, sp=8, ec=5) for p in pair_ids],
    )


# ===========================================================================
# A. Core filtering — apply_pair_filters on {pair_id: ...} dicts
# ===========================================================================
class TestCoreFilteringPrefix:
    def _data(self):
        return {f"p{i}": {"v": i} for i in range(5)}

    def test_no_filter_returns_all_keys_alphabetical(self):
        out = pf.apply_pair_filters(self._data(), None, None, None)
        assert list(out.keys()) == ["p0", "p1", "p2", "p3", "p4"]

    def test_empty_string_prefix_treated_as_no_filter(self):
        out = pf.apply_pair_filters(self._data(), "", None, None)
        assert list(out.keys()) == ["p0", "p1", "p2", "p3", "p4"]

    def test_prefix_matches_subset(self):
        data = {"alpha": 1, "alpine": 2, "beta": 3, "ant": 4}
        out = pf.apply_pair_filters(data, "alp", None, None)
        assert list(out.keys()) == ["alpha", "alpine"]

    def test_prefix_matches_none(self):
        data = {"alpha": 1, "beta": 2}
        out = pf.apply_pair_filters(data, "z", None, None)
        assert out == {}

    def test_prefix_matches_all(self):
        data = {"x_a": 1, "x_b": 2, "x_c": 3}
        out = pf.apply_pair_filters(data, "x_", None, None)
        assert list(out.keys()) == ["x_a", "x_b", "x_c"]

    def test_prefix_is_case_sensitive(self):
        data = {"Alpha": 1, "alpha": 2}
        out = pf.apply_pair_filters(data, "alp", None, None)
        assert list(out.keys()) == ["alpha"]

    def test_prefix_full_pair_id_match(self):
        data = {"foo": 1, "foobar": 2}
        out = pf.apply_pair_filters(data, "foo", None, None)
        assert list(out.keys()) == ["foo", "foobar"]

    def test_prefix_single_char(self):
        data = {"a": 1, "b": 2, "ax": 3}
        out = pf.apply_pair_filters(data, "a", None, None)
        assert list(out.keys()) == ["a", "ax"]

    def test_values_unchanged_when_filtering(self):
        data = {"a": {"deep": [1, 2]}, "b": {"deep": [3, 4]}}
        out = pf.apply_pair_filters(data, "a", None, None)
        assert out["a"] == {"deep": [1, 2]}

    def test_input_data_not_mutated(self):
        data = {"a": 1, "b": 2}
        before = dict(data)
        pf.apply_pair_filters(data, "a", None, None)
        assert data == before


class TestCoreFilteringDeterminism:
    def test_sorted_output_for_unsorted_input(self):
        data = {"zeta": 1, "alpha": 2, "mid": 3}
        out = pf.apply_pair_filters(data, None, None, None)
        assert list(out.keys()) == ["alpha", "mid", "zeta"]

    def test_repeated_calls_byte_equal(self):
        data = {f"p{i}": i for i in range(8)}
        a = pf.apply_pair_filters(data, "p", 3, 1)
        b = pf.apply_pair_filters(data, "p", 3, 1)
        assert a == b


class TestCoreFilteringEdgeCases:
    def test_empty_dict_returns_empty(self):
        assert pf.apply_pair_filters({}, None, None, None) == {}

    def test_empty_dict_with_prefix(self):
        assert pf.apply_pair_filters({}, "x", None, None) == {}

    def test_single_entry_dict(self):
        assert pf.apply_pair_filters({"a": 1}, None, None, None) == {"a": 1}

    def test_non_string_keys_are_dropped(self):
        # Python allows non-string dict keys; the spec contract is
        # pair_id (string), so non-string keys are defensively dropped.
        data = {"a": 1, 42: "weird", "b": 2}
        out = pf.apply_pair_filters(data, None, None, None)
        assert set(out.keys()) == {"a", "b"}


# ===========================================================================
# B. Pagination — limit / offset / combined
# ===========================================================================
class TestPagination:
    def _data(self):
        return {f"p{i:02d}": i for i in range(10)}

    def test_limit_only(self):
        out = pf.apply_pair_filters(self._data(), None, 3, None)
        assert list(out.keys()) == ["p00", "p01", "p02"]

    def test_offset_only(self):
        out = pf.apply_pair_filters(self._data(), None, None, 5)
        assert list(out.keys()) == ["p05", "p06", "p07", "p08", "p09"]

    def test_limit_and_offset_combined(self):
        out = pf.apply_pair_filters(self._data(), None, 3, 2)
        assert list(out.keys()) == ["p02", "p03", "p04"]

    def test_offset_zero_explicit(self):
        out = pf.apply_pair_filters(self._data(), None, 4, 0)
        assert list(out.keys()) == ["p00", "p01", "p02", "p03"]

    def test_offset_beyond_length_returns_empty(self):
        out = pf.apply_pair_filters(self._data(), None, None, 999)
        assert out == {}

    def test_limit_greater_than_available(self):
        out = pf.apply_pair_filters(self._data(), None, 50, None)
        assert list(out.keys()) == [f"p{i:02d}" for i in range(10)]

    def test_limit_one_returns_first(self):
        out = pf.apply_pair_filters(self._data(), None, 1, None)
        assert list(out.keys()) == ["p00"]

    def test_offset_at_length_returns_empty(self):
        out = pf.apply_pair_filters(self._data(), None, None, 10)
        assert out == {}

    def test_prefix_then_limit_offset_combined(self):
        data = {"a1": 1, "a2": 2, "a3": 3, "b1": 4}
        out = pf.apply_pair_filters(data, "a", 2, 1)
        assert list(out.keys()) == ["a2", "a3"]

    def test_prefix_filters_before_pagination(self):
        """Pagination is applied to the FILTERED set, not the full set."""
        data = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "b3": 5}
        # 'b' prefix narrows to 3 keys; offset=1 limit=1 → ["b2"]
        out = pf.apply_pair_filters(data, "b", 1, 1)
        assert list(out.keys()) == ["b2"]


# ===========================================================================
# C. Validation — bad inputs through validate_pair_filters
# ===========================================================================
class TestValidation:
    def test_non_string_prefix_raises(self):
        with pytest.raises(ValueError, match="pair_id_prefix"):
            pf.validate_pair_filters(42, None, None)

    def test_list_prefix_raises(self):
        with pytest.raises(ValueError, match="pair_id_prefix"):
            pf.validate_pair_filters(["a"], None, None)

    def test_zero_limit_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            pf.validate_pair_filters(None, 0, None)

    def test_negative_limit_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            pf.validate_pair_filters(None, -3, None)

    def test_string_limit_raises(self):
        with pytest.raises(ValueError, match="limit must be"):
            pf.validate_pair_filters(None, "5", None)

    def test_bool_limit_raises(self):
        # Python bool is technically int — reject it explicitly.
        with pytest.raises(ValueError, match="limit must be"):
            pf.validate_pair_filters(None, True, None)

    def test_negative_offset_raises(self):
        with pytest.raises(ValueError, match=">= 0"):
            pf.validate_pair_filters(None, None, -1)

    def test_string_offset_raises(self):
        with pytest.raises(ValueError, match="offset must be"):
            pf.validate_pair_filters(None, None, "0")

    def test_bool_offset_raises(self):
        with pytest.raises(ValueError, match="offset must be"):
            pf.validate_pair_filters(None, None, False)

    def test_apply_filters_non_dict_raises(self):
        with pytest.raises(ValueError, match="expected a dict"):
            pf.apply_pair_filters([], None, None, None)  # type: ignore[arg-type]

    def test_normalised_offset_default_zero(self):
        _, _, off = pf.validate_pair_filters(None, None, None)
        assert off == 0

    def test_normalised_prefix_none_becomes_empty(self):
        prefix, _, _ = pf.validate_pair_filters(None, None, None)
        assert prefix == ""


# ===========================================================================
# D. Drift bucket variant — apply_pair_filters_to_drift
# ===========================================================================
class TestDriftBucketFilter:
    def _drift(self):
        return {
            "stable":         ["p1", "p2", "p3"],
            "trending_up":    ["q1", "q2"],
            "trending_down":  [],
            "volatile":       ["p4"],
            "summary":        {"stable": 3, "trending_up": 2,
                               "trending_down": 0, "volatile": 1},
        }

    def test_no_filter_preserves_all(self):
        out = pf.apply_pair_filters_to_drift(self._drift(), None, None, None)
        assert sorted(out["stable"])      == ["p1", "p2", "p3"]
        assert sorted(out["trending_up"]) == ["q1", "q2"]
        assert sorted(out["volatile"])    == ["p4"]

    def test_prefix_p_keeps_only_p_pairs(self):
        out = pf.apply_pair_filters_to_drift(self._drift(), "p", None, None)
        assert sorted(out["stable"])      == ["p1", "p2", "p3"]
        assert out["trending_up"]         == []
        assert sorted(out["volatile"])    == ["p4"]

    def test_summary_recomputed_from_filtered_buckets(self):
        out = pf.apply_pair_filters_to_drift(self._drift(), "p", None, None)
        assert out["summary"]["stable"]        == 3
        assert out["summary"]["trending_up"]   == 0
        assert out["summary"]["trending_down"] == 0
        assert out["summary"]["volatile"]      == 1

    def test_limit_two_across_union(self):
        # Union = ["p1","p2","p3","p4","q1","q2"] → sorted → first 2 = ["p1","p2"]
        out = pf.apply_pair_filters_to_drift(self._drift(), None, 2, None)
        all_returned = (out["stable"] + out["trending_up"]
                        + out["trending_down"] + out["volatile"])
        assert sorted(all_returned) == ["p1", "p2"]

    def test_offset_after_p_prefix(self):
        # Filtered to ["p1","p2","p3","p4"] → offset 2 → ["p3","p4"]
        out = pf.apply_pair_filters_to_drift(self._drift(), "p", None, 2)
        all_returned = (out["stable"] + out["trending_up"]
                        + out["trending_down"] + out["volatile"])
        assert sorted(all_returned) == ["p3", "p4"]

    def test_drift_buckets_stay_alphabetical_within_each(self):
        drift = {
            "stable":         ["zeta", "alpha", "mid"],
            "trending_up":    [],
            "trending_down":  [],
            "volatile":       [],
            "summary":        {"stable": 3, "trending_up": 0,
                               "trending_down": 0, "volatile": 0},
        }
        out = pf.apply_pair_filters_to_drift(drift, None, None, None)
        assert out["stable"] == ["alpha", "mid", "zeta"]

    def test_drift_filter_non_dict_raises(self):
        with pytest.raises(ValueError, match="expected a dict"):
            pf.apply_pair_filters_to_drift([], None, None, None)  # type: ignore[arg-type]

    def test_drift_filter_prefix_excludes_all(self):
        out = pf.apply_pair_filters_to_drift(self._drift(), "z", None, None)
        for key in ("stable", "trending_up", "trending_down", "volatile"):
            assert out[key] == []
        assert out["summary"] == {"stable": 0, "trending_up": 0,
                                  "trending_down": 0, "volatile": 0}


# ===========================================================================
# E. Diff variant — apply_pair_filters_to_diff
# ===========================================================================
class TestDiffFilter:
    def _diff(self):
        return {
            "added":     ["a1", "a2"],
            "removed":   ["r1"],
            "changed":   [{"pair_id": "c1", "x": 1},
                          {"pair_id": "c2", "x": 2}],
            "unchanged": ["u1", "u2", "u3"],
            "summary":   {"added": 2, "removed": 1, "changed": 2,
                          "unchanged": 3},
        }

    def test_no_filter_preserves_lists_alphabetically(self):
        out = pf.apply_pair_filters_to_diff(self._diff(), None, None, None)
        assert out["added"]   == ["a1", "a2"]
        assert out["removed"] == ["r1"]
        assert [e["pair_id"] for e in out["changed"]] == ["c1", "c2"]
        assert out["unchanged"] == ["u1", "u2", "u3"]

    def test_prefix_a_keeps_only_added(self):
        out = pf.apply_pair_filters_to_diff(self._diff(), "a", None, None)
        assert out["added"]     == ["a1", "a2"]
        assert out["removed"]   == []
        assert out["changed"]   == []
        assert out["unchanged"] == []

    def test_prefix_c_keeps_only_changed(self):
        out = pf.apply_pair_filters_to_diff(self._diff(), "c", None, None)
        assert out["added"]   == []
        assert out["removed"] == []
        assert [e["pair_id"] for e in out["changed"]] == ["c1", "c2"]
        assert out["unchanged"] == []

    def test_summary_recomputed_after_prefix(self):
        out = pf.apply_pair_filters_to_diff(self._diff(), "u", None, None)
        assert out["summary"] == {
            "added": 0, "removed": 0, "changed": 0, "unchanged": 3,
        }

    def test_limit_two_across_diff_union(self):
        # Union = ["a1","a2","c1","c2","r1","u1","u2","u3"] sorted →
        # first 2 = ["a1","a2"] → both in 'added'
        out = pf.apply_pair_filters_to_diff(self._diff(), None, 2, None)
        assert sorted(out["added"]) == ["a1", "a2"]
        assert out["removed"] == []
        assert out["changed"] == []
        assert out["unchanged"] == []

    def test_offset_skips_into_changed(self):
        # Sorted union: a1,a2,c1,c2,r1,u1,u2,u3. offset=2 limit=2 → c1,c2
        out = pf.apply_pair_filters_to_diff(self._diff(), None, 2, 2)
        assert [e["pair_id"] for e in out["changed"]] == ["c1", "c2"]
        assert out["added"] == []

    def test_changed_entries_keep_their_payload(self):
        out = pf.apply_pair_filters_to_diff(self._diff(), "c", None, None)
        for entry in out["changed"]:
            assert "x" in entry  # full entry preserved, not just pair_id

    def test_diff_filter_non_dict_raises(self):
        with pytest.raises(ValueError, match="expected a dict"):
            pf.apply_pair_filters_to_diff([], None, None, None)  # type: ignore[arg-type]

    def test_changed_sorted_by_pair_id(self):
        diff = {
            "added": [], "removed": [], "unchanged": [],
            "changed": [{"pair_id": "z"}, {"pair_id": "a"},
                        {"pair_id": "m"}],
            "summary": {"added": 0, "removed": 0, "changed": 3,
                        "unchanged": 0},
        }
        out = pf.apply_pair_filters_to_diff(diff, None, None, None)
        assert [e["pair_id"] for e in out["changed"]] == ["a", "m", "z"]


# ===========================================================================
# F. Endpoint integration — query params wired into all 5 endpoints
# ===========================================================================
class TestEndpointMagnitude:
    _PATH = "/elins/regression/drift/magnitude"
    _IDS  = ["em_a", "em_b"]

    def _setup(self):
        _store_pairs(*self._IDS, ["alpha", "alpine", "beta", "gamma"])

    def test_no_filter_returns_all_pairs(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH, json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert set(body.keys()) == {"alpha", "alpine", "beta", "gamma"}

    def test_prefix_filters_pairs(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert set(body.keys()) == {"alpha", "alpine"}

    def test_limit_truncates(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?limit=2",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert list(body.keys()) == ["alpha", "alpine"]

    def test_offset_skips(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?offset=2",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert list(body.keys()) == ["beta", "gamma"]

    def test_combined(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?pair_id_prefix=al&limit=1&offset=1",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert list(body.keys()) == ["alpine"]

    def test_invalid_limit_zero_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        resp = client.post(
            self._PATH + "?limit=0",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_invalid_offset_negative_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        resp = client.post(
            self._PATH + "?offset=-1",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_unauth_still_401(self, client, app_module):
        resp = client.post(
            self._PATH + "?limit=2", json={"run_ids": self._IDS},
        )
        assert resp.status_code == 401

    def test_filter_does_not_alter_values(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        full = client.post(
            self._PATH, json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        filtered = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        for pid in filtered:
            assert filtered[pid] == full[pid]


class TestEndpointSeverity:
    _PATH = "/elins/regression/drift/severity"
    _IDS  = ["es_a", "es_b"]

    def _setup(self):
        _store_pairs(*self._IDS, ["alpha", "beta", "gamma"])

    def test_prefix_filters(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?pair_id_prefix=a",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert list(body.keys()) == ["alpha"]

    def test_limit_offset(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?limit=1&offset=1",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert list(body.keys()) == ["beta"]

    def test_invalid_limit_400(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        resp = client.post(
            self._PATH + "?limit=-5",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        )
        assert resp.status_code == 400


class TestEndpointSeries:
    _PATH = "/elins/regression/drift/series"
    _IDS  = ["esr_a", "esr_b"]

    def _setup(self):
        _store_pairs(*self._IDS, ["alpha", "beta", "gamma"])

    def test_prefix_filters(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?pair_id_prefix=g",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert list(body.keys()) == ["gamma"]

    def test_limit(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?limit=2",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert list(body.keys()) == ["alpha", "beta"]

    def test_invalid_offset_400(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        resp = client.post(
            self._PATH + "?offset=-1",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_filter_preserves_series_values(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        full = client.post(
            self._PATH, json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        filt = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert filt["alpha"] == full["alpha"]


class TestEndpointDrift:
    _PATH = "/elins/regression/drift"
    _IDS  = ["ed_a", "ed_b"]

    def _setup(self):
        _store_pairs(*self._IDS, ["alpha", "alpine", "beta", "gamma"])

    def test_no_filter_returns_all(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH, json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert body["trending_up"] == [
            "alpha", "alpine", "beta", "gamma",
        ]
        assert body["summary"]["trending_up"] == 4

    def test_prefix_filters_buckets(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert body["trending_up"] == ["alpha", "alpine"]
        assert body["summary"]["trending_up"] == 2

    def test_summary_reflects_filtered_buckets(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?pair_id_prefix=z",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert body["summary"] == {
            "stable": 0, "trending_up": 0,
            "trending_down": 0, "volatile": 0,
        }

    def test_limit_truncates_union(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?limit=2",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        # First 2 alphabetical: alpha, alpine
        assert body["trending_up"] == ["alpha", "alpine"]

    def test_invalid_limit_400(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        resp = client.post(
            self._PATH + "?limit=0",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        )
        assert resp.status_code == 400


class TestEndpointDiff:
    _PATH = "/elins/regression/diff"

    def _setup(self):
        # r1 has alpha, beta, gamma; r2 has alpine, beta, delta
        ep.save_comparison_result(
            "edif_a", [_entry("alpha"), _entry("beta"), _entry("gamma")],
        )
        ep.save_comparison_result(
            "edif_b", [_entry("alpine"), _entry("beta"), _entry("delta")],
        )

    def test_no_filter_full_diff(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.get(
            self._PATH + "?run_a=edif_a&run_b=edif_b", headers=_auth(sid),
        ).json()
        assert sorted(body["added"])     == ["alpine", "delta"]
        assert sorted(body["removed"])   == ["alpha", "gamma"]
        assert body["unchanged"]         == ["beta"]

    def test_prefix_alpine_keeps_only_alpine(self, client, app_module):
        """Use a prefix that uniquely matches one pair on each side."""
        sid = _make_user_session(app_module)
        self._setup()
        body = client.get(
            self._PATH + "?run_a=edif_a&run_b=edif_b&pair_id_prefix=alpi",
            headers=_auth(sid),
        ).json()
        assert body["added"]     == ["alpine"]
        assert body["removed"]   == []
        assert body["changed"]   == []
        assert body["unchanged"] == []

    def test_prefix_alp_keeps_both_alpha_and_alpine(self, client, app_module):
        """Both 'alpha' (removed) and 'alpine' (added) start with 'alp'."""
        sid = _make_user_session(app_module)
        self._setup()
        body = client.get(
            self._PATH + "?run_a=edif_a&run_b=edif_b&pair_id_prefix=alp",
            headers=_auth(sid),
        ).json()
        assert body["added"]   == ["alpine"]
        assert body["removed"] == ["alpha"]

    def test_summary_recomputed(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.get(
            self._PATH + "?run_a=edif_a&run_b=edif_b&pair_id_prefix=alp",
            headers=_auth(sid),
        ).json()
        # alpha is in 'removed', alpine is in 'added' — both prefix-match.
        assert body["summary"]["added"]     == 1
        assert body["summary"]["removed"]   == 1
        assert body["summary"]["changed"]   == 0
        assert body["summary"]["unchanged"] == 0

    def test_limit_offset(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        # Sorted union: alpha, alpine, beta, delta, gamma. offset=1 limit=2
        # → alpine, beta. alpine is in 'added', beta in 'unchanged'.
        body = client.get(
            self._PATH + "?run_a=edif_a&run_b=edif_b&limit=2&offset=1",
            headers=_auth(sid),
        ).json()
        assert body["added"]     == ["alpine"]
        assert body["unchanged"] == ["beta"]

    def test_invalid_offset_400(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        resp = client.get(
            self._PATH + "?run_a=edif_a&run_b=edif_b&offset=-3",
            headers=_auth(sid),
        )
        assert resp.status_code == 400


# ===========================================================================
# G. Mixed analytics — magnitude + severity + series filter identically
# ===========================================================================
class TestCrossAnalyticsFilterParity:
    """Filtering with the same prefix/limit/offset across the three
    pair_id-keyed endpoints must yield identical key sets."""
    _IDS = ["x_a", "x_b"]

    def _setup(self):
        _store_pairs(
            *self._IDS,
            ["alpha", "alpine", "beta", "gamma", "zeta"],
        )

    def _keys(self, client, sid, path, qs=""):
        return set(client.post(
            path + qs, json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json().keys())

    def test_prefix_alp_yields_same_pairs_for_three_endpoints(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        self._setup()
        m = self._keys(client, sid, "/elins/regression/drift/magnitude",
                       "?pair_id_prefix=alp")
        s = self._keys(client, sid, "/elins/regression/drift/severity",
                       "?pair_id_prefix=alp")
        sr = self._keys(client, sid, "/elins/regression/drift/series",
                        "?pair_id_prefix=alp")
        assert m == s == sr == {"alpha", "alpine"}

    def test_limit_offset_yields_same_pairs(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        m = self._keys(client, sid, "/elins/regression/drift/magnitude",
                       "?limit=2&offset=1")
        s = self._keys(client, sid, "/elins/regression/drift/severity",
                       "?limit=2&offset=1")
        sr = self._keys(client, sid, "/elins/regression/drift/series",
                        "?limit=2&offset=1")
        assert m == s == sr

    def test_drift_filtered_pair_set_matches_pair_keyed_endpoints(
        self, client, app_module,
    ):
        """The 'allowed' pair set should be the same regardless of which
        per-pair endpoint is hit."""
        sid = _make_user_session(app_module)
        self._setup()
        # Magnitude (pair_id-keyed)
        mag = client.post(
            "/elins/regression/drift/magnitude?limit=3",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        # Drift (bucket-keyed)
        drift = client.post(
            "/elins/regression/drift?limit=3",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        drift_pairs = set(
            drift["stable"] + drift["trending_up"]
            + drift["trending_down"] + drift["volatile"]
        )
        assert set(mag.keys()) == drift_pairs

    def test_summary_endpoints_unaffected_by_filter_params(
        self, client, app_module,
    ):
        """Unit 14 / Unit 18 endpoints don't accept Unit 21 query params;
        any unrecognised query string must be silently ignored."""
        sid = _make_user_session(app_module)
        self._setup()
        # Single-run summary: GET /elins/regression/run/{rid}/summary
        body_no_qs = client.get(
            "/elins/regression/run/x_a/summary", headers=_auth(sid),
        ).json()
        body_with_qs = client.get(
            "/elins/regression/run/x_a/summary?pair_id_prefix=alp&limit=2",
            headers=_auth(sid),
        ).json()
        assert body_no_qs == body_with_qs

    def test_summary_multi_unaffected_by_filter_query_params(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        self._setup()
        body_no_qs = client.post(
            "/elins/regression/runs/summary",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        body_with_qs = client.post(
            "/elins/regression/runs/summary?pair_id_prefix=alp&limit=1",
            json={"run_ids": self._IDS}, headers=_auth(sid),
        ).json()
        assert body_no_qs == body_with_qs


# ===========================================================================
# H. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_validate_pair_filters_callable(self):
        assert callable(pf.validate_pair_filters)

    def test_select_pair_ids_callable(self):
        assert callable(pf.select_pair_ids)

    def test_apply_pair_filters_callable(self):
        assert callable(pf.apply_pair_filters)

    def test_apply_pair_filters_to_drift_callable(self):
        assert callable(pf.apply_pair_filters_to_drift)

    def test_apply_pair_filters_to_diff_callable(self):
        assert callable(pf.apply_pair_filters_to_diff)

    def test_drift_bucket_keys_locked(self):
        assert pf._DRIFT_BUCKET_KEYS == (
            "stable", "trending_up", "trending_down", "volatile",
        )

    def test_diff_pair_list_keys_locked(self):
        assert pf._DIFF_PAIR_LIST_KEYS == ("added", "removed", "unchanged")
        assert pf._DIFF_CHANGED_KEY == "changed"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(pf)

    def _code_only(self) -> str:
        """Source with all triple-quoted docstring blocks stripped, so
        purity assertions don't trip over prose like 'No logging.' in
        the module docstring."""
        import re as _re
        src = self._src()
        # Strip triple-quoted blocks (both ''' and """).
        src = _re.sub(r'"""[\s\S]*?"""', "", src)
        src = _re.sub(r"'''[\s\S]*?'''", "", src)
        return src

    def test_no_io(self):
        src = self._code_only()
        for forbidden in ("open(", "Path(", "os.environ",
                          "json.load", "json.dump"):
            assert forbidden not in src

    def test_no_logging(self):
        src = self._code_only()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_network(self):
        src = self._code_only()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket",
                          "from urllib", "from http", "from requests"):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._code_only()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src

    def test_no_llm_imports(self):
        src = self._code_only()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_persistence_or_analytics_imports(self):
        """Filter module is purely about reshaping output dicts —
        must not import persistence or analytic modules."""
        src = self._code_only()
        for forbidden in (
            "elins_persistence", "elins_run_diff", "elins_run_drift",
            "elins_run_drift_magnitude", "elins_run_drift_severity",
            "elins_run_drift_series", "elins_run_summary",
        ):
            assert forbidden not in src
