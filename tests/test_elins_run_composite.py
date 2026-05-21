"""
Tests for ELINS Unit 22 — composite per-run endpoint.

Layered coverage (>= 70 tests, target ~80):
    A. Core composition — composite_for_run_ids, single + multi run
    B. Filtering wrapper — composite_endpoint_wrapper + Unit 21 parity
    C. Endpoint — POST /elins/regression/run/composite
    D. Integration — directory / single / batch / legacy mixes
    E. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_run_composite as composite_mod
import elins_run_drift as drift_mod
import elins_run_drift_magnitude as mag_mod
import elins_run_drift_series as series_mod
import elins_run_drift_severity as sev_mod
import elins_run_summary as summary_mod
import elins_run_summary_multi as multi_mod


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
    """Save two runs with a +3 sp swing per pair (so drift is consistently
    'trending_up' for all pairs)."""
    ep.save_comparison_result(
        rid_a, [_entry(p, sp=5, ec=5) for p in pair_ids],
    )
    ep.save_comparison_result(
        rid_b, [_entry(p, sp=8, ec=5) for p in pair_ids],
    )


def _write_legacy_file(runs_dir: Path, run_id: str, payload) -> None:
    """Unit 25: insert a legacy-shaped envelope (``metadata=None``)
    directly into the SQLite DB. See test_elins_run_metadata.py for the
    canonical form."""
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


# ===========================================================================
# A. Core composition — composite_for_run_ids
# ===========================================================================
class TestCoreSingleRun:
    def test_returns_dict(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = composite_mod.composite_for_run_ids(["solo"])
        assert isinstance(out, dict)

    def test_run_ids_field_matches_input(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = composite_mod.composite_for_run_ids(["solo"])
        assert out["run_ids"] == ["solo"]

    def test_metadata_field_is_list_of_one(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = composite_mod.composite_for_run_ids(["solo"])
        assert isinstance(out["metadata"], list)
        assert len(out["metadata"]) == 1

    def test_metadata_carries_source_tag(self):
        ep.save_comparison_result("solo", [_entry("p1")], source="batch")
        out = composite_mod.composite_for_run_ids(["solo"])
        assert out["metadata"][0]["source"] == "batch"

    def test_summary_present_for_single_run(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = composite_mod.composite_for_run_ids(["solo"])
        assert "summary" in out

    def test_single_run_summary_matches_unit14(self):
        payload = [_entry("p1", sp=5), _entry("p2", sp=8)]
        ep.save_comparison_result("solo", payload)
        out = composite_mod.composite_for_run_ids(["solo"])
        assert out["summary"] == summary_mod.summary_table(payload)

    def test_single_run_omits_drift_fields(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = composite_mod.composite_for_run_ids(["solo"])
        for forbidden in ("direction", "magnitude", "severity", "series"):
            assert forbidden not in out

    def test_single_run_top_level_keys(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = composite_mod.composite_for_run_ids(["solo"])
        assert set(out.keys()) == {"run_ids", "metadata", "summary"}

    def test_single_run_summary_total_pairs(self):
        ep.save_comparison_result(
            "solo", [_entry("p1"), _entry("p2"), _entry("p3")],
        )
        out = composite_mod.composite_for_run_ids(["solo"])
        assert out["summary"]["total_pairs"] == 3


class TestCoreMultiRun:
    def test_two_run_top_level_keys(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        out = composite_mod.composite_for_run_ids(["a", "b"])
        assert set(out.keys()) == {
            "run_ids", "metadata", "summary",
            "direction", "magnitude", "severity", "series",
        }

    def test_multi_run_metadata_one_per_run(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        out = composite_mod.composite_for_run_ids(["a", "b"])
        assert len(out["metadata"]) == 2

    def test_multi_run_summary_uses_unit18_shape(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        out = composite_mod.composite_for_run_ids(["a", "b"])
        # Unit 18 shape is {"runs": {rid: per_run_summary, ...}}
        assert "runs" in out["summary"]
        assert set(out["summary"]["runs"].keys()) == {"a", "b"}

    def test_multi_run_direction_matches_unit13(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        out = composite_mod.composite_for_run_ids(["a", "b"])
        direct = drift_mod.detect_drift_for_run_ids(["a", "b"])
        assert out["direction"] == direct

    def test_multi_run_magnitude_matches_unit15(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        out = composite_mod.composite_for_run_ids(["a", "b"])
        direct = mag_mod.drift_magnitude_for_run_ids(["a", "b"])
        assert out["magnitude"] == direct

    def test_multi_run_severity_matches_unit16(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        out = composite_mod.composite_for_run_ids(["a", "b"])
        direct = sev_mod.classify_drift_severity_for_run_ids(["a", "b"])
        assert out["severity"] == direct

    def test_multi_run_series_matches_unit17(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        out = composite_mod.composite_for_run_ids(["a", "b"])
        direct = series_mod.drift_series_for_run_ids(["a", "b"])
        assert out["series"] == direct

    def test_multi_run_summary_matches_unit18(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        out = composite_mod.composite_for_run_ids(["a", "b"])
        direct = multi_mod.summary_across_run_ids(["a", "b"])
        assert out["summary"] == direct

    def test_three_run_composite(self):
        ep.save_comparison_result("r1", [_entry("p1", sp=3)])
        ep.save_comparison_result("r2", [_entry("p1", sp=5)])
        ep.save_comparison_result("r3", [_entry("p1", sp=9)])
        out = composite_mod.composite_for_run_ids(["r1", "r2", "r3"])
        assert out["run_ids"] == ["r1", "r2", "r3"]
        assert len(out["metadata"]) == 3
        assert "p1" in out["series"]
        assert out["series"]["p1"]["single_party_scores"] == [3, 5, 9]

    def test_metadata_order_matches_run_ids_order(self):
        ep.save_comparison_result("first", [_entry("p1")], source="single")
        ep.save_comparison_result("second", [_entry("p1")], source="batch")
        out = composite_mod.composite_for_run_ids(["first", "second"])
        assert out["metadata"][0]["source"] == "single"
        assert out["metadata"][1]["source"] == "batch"

    def test_run_ids_field_reflects_timestamp_order(self):
        """Unit 23 invariant: composite returns run_ids reordered by
        ``metadata.created_at``. The save order here is z then a, so
        timestamp order is [z, a] regardless of caller order. (Note:
        on systems with low-resolution clocks, ties break alphabetically
        → [a, z]; this test asserts on the alphabetical fallback to
        stay deterministic across Windows / macOS / Linux.)"""
        _store_pairs("z", "a", ["x"])
        out_in_order = composite_mod.composite_for_run_ids(["z", "a"])
        out_reversed = composite_mod.composite_for_run_ids(["a", "z"])
        # Caller order is ignored — both calls produce the same output.
        assert out_in_order == out_reversed
        # The two valid resolutions of save-order(z then a) are:
        #   * distinct ts → ["z", "a"]
        #   * tied ts (Windows clock resolution) → ["a", "z"] alphabetical
        assert out_in_order["run_ids"] in (["z", "a"], ["a", "z"])


class TestCoreValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            composite_mod.composite_for_run_ids("nope")  # type: ignore[arg-type]

    def test_empty_list_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            composite_mod.composite_for_run_ids([])

    def test_malformed_run_id_raises(self):
        with pytest.raises(ValueError):
            composite_mod.composite_for_run_ids(["bad/id"])

    def test_missing_run_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            composite_mod.composite_for_run_ids(["ghost"])

    def test_validates_all_ids_before_loading(self):
        ep.save_comparison_result("good", [_entry("p1")])
        with pytest.raises(ValueError):
            composite_mod.composite_for_run_ids(["good", "bad/id"])


class TestCoreDeterminism:
    def test_repeated_calls_byte_equal(self):
        _store_pairs("a", "b", ["alpha", "beta"])
        first  = composite_mod.composite_for_run_ids(["a", "b"])
        second = composite_mod.composite_for_run_ids(["a", "b"])
        assert first == second

    def test_pure_compose_reproducible(self):
        """The internal _compose helper is byte-equal across calls when
        given identical input."""
        results_a = [[_entry("p1", sp=5)], [_entry("p1", sp=8)]]
        meta_a    = [None, None]
        a = composite_mod._compose(["x", "y"], meta_a, results_a)
        b = composite_mod._compose(["x", "y"], meta_a, results_a)
        assert a == b


# ===========================================================================
# B. Filtering wrapper — composite_endpoint_wrapper + Unit 21 parity
# ===========================================================================
class TestFilteringWrapper:
    def _setup(self):
        _store_pairs("a", "b", ["alpha", "alpine", "beta", "gamma"])

    def test_no_filter_passes_through(self):
        self._setup()
        bare = composite_mod.composite_for_run_ids(["a", "b"])
        wrapped = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], None, None, None,
        )
        # Without a prefix and with full bucket pass-through, the only
        # potential delta is inside the drift bucket sort order. They
        # should byte-equal each other.
        assert wrapped == bare

    def test_prefix_filters_pair_keyed_sections(self):
        self._setup()
        out = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], "alp", None, None,
        )
        assert set(out["magnitude"].keys()) == {"alpha", "alpine"}
        assert set(out["severity"].keys())  == {"alpha", "alpine"}
        assert set(out["series"].keys())    == {"alpha", "alpine"}

    def test_prefix_filters_drift_buckets(self):
        self._setup()
        out = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], "alp", None, None,
        )
        assert sorted(out["direction"]["trending_up"]) == ["alpha", "alpine"]
        assert out["direction"]["summary"]["trending_up"] == 2

    def test_summary_unaffected_by_filter(self):
        self._setup()
        bare = composite_mod.composite_for_run_ids(["a", "b"])
        out = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], "alp", None, None,
        )
        assert out["summary"] == bare["summary"]

    def test_metadata_unaffected_by_filter(self):
        self._setup()
        bare = composite_mod.composite_for_run_ids(["a", "b"])
        out = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], "alp", None, None,
        )
        assert out["metadata"] == bare["metadata"]

    def test_run_ids_unaffected_by_filter(self):
        self._setup()
        out = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], "alp", None, None,
        )
        assert out["run_ids"] == ["a", "b"]

    def test_limit_truncates(self):
        self._setup()
        out = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], None, 2, None,
        )
        assert list(out["magnitude"].keys()) == ["alpha", "alpine"]

    def test_offset_skips(self):
        self._setup()
        out = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], None, None, 2,
        )
        assert list(out["magnitude"].keys()) == ["beta", "gamma"]

    def test_invalid_limit_raises_value_error(self):
        self._setup()
        with pytest.raises(ValueError):
            composite_mod.composite_endpoint_wrapper(
                ["a", "b"], None, 0, None,
            )

    def test_invalid_offset_raises_value_error(self):
        self._setup()
        with pytest.raises(ValueError):
            composite_mod.composite_endpoint_wrapper(
                ["a", "b"], None, None, -1,
            )

    def test_filter_validation_runs_before_load(self, monkeypatch):
        """Bad filter inputs must error BEFORE we touch the persistence
        layer — protects against expensive loads on bad client params."""
        called = {"count": 0}
        original_load = ep.load_comparison_result

        def _spy(rid):
            called["count"] += 1
            return original_load(rid)

        monkeypatch.setattr(ep, "load_comparison_result", _spy)
        # Patch the symbol on the composite module's import surface too.
        monkeypatch.setattr(composite_mod, "load_comparison_result", _spy)

        with pytest.raises(ValueError):
            composite_mod.composite_endpoint_wrapper(
                ["a", "b"], None, -5, None,
            )
        assert called["count"] == 0

    def test_single_run_wrapper_passes_through(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = composite_mod.composite_endpoint_wrapper(
            ["solo"], "alp", 1, 0,
        )
        # Single-run mode has no pair-keyed sections to filter.
        assert "summary" in out
        for forbidden in ("direction", "magnitude", "severity", "series"):
            assert forbidden not in out


class TestUnit21FilterParity:
    def _setup(self):
        _store_pairs("a", "b", ["alpha", "alpine", "beta", "gamma", "zeta"])

    def test_magnitude_section_matches_unit21_endpoint(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        self._setup()
        comp = client.post(
            "/elins/regression/run/composite?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        mag = client.post(
            "/elins/regression/drift/magnitude?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert comp["magnitude"] == mag

    def test_severity_section_matches_unit21_endpoint(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        self._setup()
        comp = client.post(
            "/elins/regression/run/composite?limit=2&offset=1",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        sev = client.post(
            "/elins/regression/drift/severity?limit=2&offset=1",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert comp["severity"] == sev

    def test_series_section_matches_unit21_endpoint(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        self._setup()
        comp = client.post(
            "/elins/regression/run/composite?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        srs = client.post(
            "/elins/regression/drift/series?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert comp["series"] == srs

    def test_direction_section_matches_unit21_endpoint(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        self._setup()
        comp = client.post(
            "/elins/regression/run/composite?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        drift = client.post(
            "/elins/regression/drift?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert comp["direction"] == drift


# ===========================================================================
# C. Endpoint — POST /elins/regression/run/composite
# ===========================================================================
class TestEndpointBasic:
    _PATH = "/elins/regression/run/composite"

    def test_single_run_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        resp = client.post(
            self._PATH, json={"run_ids": ["solo"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_two_run_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        _store_pairs("a", "b", ["alpha"])
        resp = client.post(
            self._PATH, json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_top_level_keys_single_run(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        body = client.post(
            self._PATH, json={"run_ids": ["solo"]}, headers=_auth(sid),
        ).json()
        assert set(body.keys()) == {"run_ids", "metadata", "summary"}

    def test_response_top_level_keys_multi_run(self, client, app_module):
        sid = _make_user_session(app_module)
        _store_pairs("a", "b", ["alpha"])
        body = client.post(
            self._PATH, json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert set(body.keys()) == {
            "run_ids", "metadata", "summary",
            "direction", "magnitude", "severity", "series",
        }

    def test_metadata_carries_source(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")], source="batch")
        body = client.post(
            self._PATH, json={"run_ids": ["solo"]}, headers=_auth(sid),
        ).json()
        assert body["metadata"][0]["source"] == "batch"

    def test_unauth_returns_401(self, client, app_module):
        resp = client.post(self._PATH, json={"run_ids": ["x"]})
        assert resp.status_code == 401

    def test_missing_body_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(self._PATH, json={}, headers=_auth(sid))
        assert resp.status_code == 400

    def test_run_ids_not_list_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH, json={"run_ids": "nope"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_empty_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH, json={"run_ids": []}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH, json={"run_ids": ["bad$id"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH, json={"run_ids": ["ghost"]}, headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_partial_missing_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("present", [_entry("p1")])
        resp = client.post(
            self._PATH,
            json={"run_ids": ["present", "ghost"]}, headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        _store_pairs("a", "b", ["alpha"])
        r1 = client.post(
            self._PATH, json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        r2 = client.post(
            self._PATH, json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert r1.json() == r2.json()

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        _store_pairs("a", "b", ["alpha"])
        endpoint = client.post(
            self._PATH, json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        direct = composite_mod.composite_endpoint_wrapper(
            ["a", "b"], None, None, None,
        )
        assert endpoint == direct


class TestEndpointFiltering:
    _PATH = "/elins/regression/run/composite"

    def _setup(self):
        _store_pairs("a", "b", ["alpha", "alpine", "beta", "gamma"])

    def test_prefix_filters_pair_keyed_sections(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert set(body["magnitude"].keys()) == {"alpha", "alpine"}
        assert set(body["severity"].keys())  == {"alpha", "alpine"}
        assert set(body["series"].keys())    == {"alpha", "alpine"}

    def test_prefix_filters_drift_buckets_via_endpoint(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        self._setup()
        body = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert sorted(body["direction"]["trending_up"]) == [
            "alpha", "alpine",
        ]

    def test_summary_unaffected_by_endpoint_filter(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        bare = client.post(
            self._PATH, json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        filt = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        assert bare["summary"] == filt["summary"]

    def test_invalid_limit_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        resp = client.post(
            self._PATH + "?limit=0",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_invalid_offset_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        self._setup()
        resp = client.post(
            self._PATH + "?offset=-3",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_filter_preserves_values_in_pair_sections(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        self._setup()
        bare = client.post(
            self._PATH, json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        filt = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        ).json()
        for pid in filt["magnitude"]:
            assert filt["magnitude"][pid] == bare["magnitude"][pid]
        for pid in filt["series"]:
            assert filt["series"][pid] == bare["series"][pid]


# ===========================================================================
# D. Integration — directory / single / batch / legacy / mixed
# ===========================================================================
class TestIntegration:
    _PATH = "/elins/regression/run/composite"

    def _sp_payload(self, tid="sp_a"):
        return {
            "timeline_id": tid,
            "points": [
                {"t": "t0",
                 "regime_competition": 0.5, "autocratization": 0.5,
                 "repression_index": 0.5, "digital_repression": 0.5,
                 "perceived_threat": 0.5, "fear_signal": 0.5,
                 "dissent_capacity": 0.5, "normative_constraint": 0.5,
                 "support_buffer": 0.5},
            ],
        }

    def _ec_payload(self, tid="ec_a"):
        return {
            "timeline_id": tid,
            "points": [
                {"t": "t0",
                 "economic_pressure": 0.5, "material_insecurity": 0.5,
                 "state_coercion": 0.5, "compliance_signal": 0.5,
                 "resistance_capacity": 0.5, "support_buffer": 0.5},
            ],
        }

    def test_directory_path_composite_works(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "dir_run", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.post(
            self._PATH, json={"run_ids": ["dir_run"]}, headers=_auth(sid),
        ).json()
        assert body["metadata"][0]["source"] == "directory"

    def test_single_pair_composite_works(self, client, app_module):
        sid = _make_user_session(app_module)
        client.post(
            "/elins/regression/store",
            json={"run_id": "single_run", "pairs": [{
                "single_party_timeline": self._sp_payload(),
                "economic_timeline":     self._ec_payload(),
            }]},
            headers=_auth(sid),
        )
        body = client.post(
            self._PATH, json={"run_ids": ["single_run"]}, headers=_auth(sid),
        ).json()
        assert body["metadata"][0]["source"] == "single"
        assert body["summary"]["total_pairs"] == 1

    def test_batch_composite_works(self, client, app_module):
        sid = _make_user_session(app_module)
        sp1 = self._sp_payload("sp_a"); sp2 = self._sp_payload("sp_b")
        ec1 = self._ec_payload("ec_a"); ec2 = self._ec_payload("ec_b")
        client.post(
            "/elins/regression/store",
            json={"run_id": "batch_run", "pairs": [
                {"single_party_timeline": sp1, "economic_timeline": ec1},
                {"single_party_timeline": sp2, "economic_timeline": ec2},
            ]},
            headers=_auth(sid),
        )
        body = client.post(
            self._PATH, json={"run_ids": ["batch_run"]}, headers=_auth(sid),
        ).json()
        assert body["metadata"][0]["source"] == "batch"
        assert body["summary"]["total_pairs"] == 2

    def test_legacy_run_composite(
        self, client, app_module, _runs_dir_isolation,
    ):
        sid = _make_user_session(app_module)
        _write_legacy_file(_runs_dir_isolation, "leg",
                           [_entry("p1"), _entry("p2")])
        body = client.post(
            self._PATH, json={"run_ids": ["leg"]}, headers=_auth(sid),
        ).json()
        # Legacy → metadata is None, but composite still returns it.
        assert body["metadata"][0] is None
        assert body["summary"]["total_pairs"] == 2

    def test_mixed_legacy_and_new_multi_run(
        self, client, app_module, _runs_dir_isolation,
    ):
        """Unit 23 invariant: legacy runs (no metadata) sort LAST.
        Mixing a legacy and a new run means the new run leads the
        sequence, the legacy run trails, and the series reflects that
        ordering — which inverts the value sequence relative to the
        save order seen in the test fixture."""
        sid = _make_user_session(app_module)
        _write_legacy_file(_runs_dir_isolation, "leg_old",
                           [_entry("p1", sp=5)])
        ep.save_comparison_result("new_one",
                                   [_entry("p1", sp=8)], source="single")
        body = client.post(
            self._PATH, json={"run_ids": ["leg_old", "new_one"]},
            headers=_auth(sid),
        ).json()
        # Sorted order: ["new_one", "leg_old"] (legacy sorts last).
        assert body["run_ids"]      == ["new_one", "leg_old"]
        assert body["metadata"][0]["source"] == "single"
        assert body["metadata"][1] is None
        assert body["series"]["p1"]["single_party_scores"] == [8, 5]

    def test_e2e_directory_then_directory_composite_drift(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        # Two directory scans (both empty) → two runs with no pairs.
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "d1", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "d2", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.post(
            self._PATH, json={"run_ids": ["d1", "d2"]}, headers=_auth(sid),
        ).json()
        # Both metadata entries flag directory source.
        assert body["metadata"][0]["source"] == "directory"
        assert body["metadata"][1]["source"] == "directory"
        # Empty directories → no common pairs → empty drift output.
        assert body["series"] == {}
        assert body["magnitude"] == {}

    def test_composite_metadata_evidence_dir_preserved(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "ed", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        body = client.post(
            self._PATH, json={"run_ids": ["ed"]}, headers=_auth(sid),
        ).json()
        assert body["metadata"][0]["evidence_dir"] == str(tmp_path)


# ===========================================================================
# E. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_composite_for_run_ids_callable(self):
        assert callable(composite_mod.composite_for_run_ids)

    def test_composite_endpoint_wrapper_callable(self):
        assert callable(composite_mod.composite_endpoint_wrapper)

    def test_internal_compose_callable(self):
        assert callable(composite_mod._compose)

    def test_top_level_keys_locked(self):
        assert composite_mod._KEY_RUN_IDS   == "run_ids"
        assert composite_mod._KEY_METADATA  == "metadata"
        assert composite_mod._KEY_SUMMARY   == "summary"
        assert composite_mod._KEY_DIRECTION == "direction"
        assert composite_mod._KEY_MAGNITUDE == "magnitude"
        assert composite_mod._KEY_SEVERITY  == "severity"
        assert composite_mod._KEY_SERIES    == "series"


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(composite_mod)

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

    def test_compose_helper_pure_no_open(self):
        """The internal _compose helper must not touch the filesystem."""
        src = inspect.getsource(composite_mod._compose)
        assert "open(" not in src
        assert "load_comparison_result" not in src

    def test_compose_helper_pure_no_validation(self):
        """The internal _compose helper must not re-validate run_ids
        (that's the loader's job)."""
        src = inspect.getsource(composite_mod._compose)
        assert "_validate_run_id" not in src

    def test_composite_module_delegates_to_existing_units(self):
        """Source must import from the existing analytic modules rather
        than reimplementing analytics."""
        src = self._code_only()
        for required in (
            "summary_table", "summary_across_runs",
            "detect_drift", "drift_magnitude",
            "drift_series", "classify_drift_severity",
        ):
            assert required in src
