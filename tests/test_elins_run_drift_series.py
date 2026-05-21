"""
Tests for ELINS Unit 17 — per-pair drift sparkline data export.

Layered coverage (≥ 60 tests, target 70+):
    A. Internal helpers — _is_clean_numeric, _is_clean_band
    B. Core series logic — multi-run, multi-pair, length matching
    C. Skip rules — None / non-numeric / bool / missing band / etc.
    D. Pair presence — partial drops, legacy fallback
    E. Validation
    F. Wrapper — drift_series_for_run_ids
    G. Endpoint — POST /elins/regression/drift/series
    H. Determinism + ordering
    I. Source-code purity / module surface
    J. End-to-end via persistence
"""
from __future__ import annotations

import inspect
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_run_drift_series as series_mod


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


# ===========================================================================
# Payload helpers
# ===========================================================================
def _entry(
    pair_id: str = "p::a",
    *,
    sp: int = 5,
    ec: int = 5,
    sp_band: str = "Acceptable",
    ec_band: str = "Acceptable",
) -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp,
        "economic_coercion_score": ec,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _legacy_entry(*, sp: int = 5, ec: int = 5, sp_band: str = "Acceptable",
                  ec_band: str = "Acceptable") -> dict:
    e = _entry(sp=sp, ec=ec, sp_band=sp_band, ec_band=ec_band)
    del e["pair_id"]
    return e


def _runs_with(pair_id: str, sp_series: list, ec_series: list,
               sp_bands: list = None, ec_bands: list = None) -> list:
    """Build N runs each containing one pair with the given series."""
    n = len(sp_series)
    assert len(ec_series) == n
    sp_bands = sp_bands if sp_bands is not None else ["Acceptable"] * n
    ec_bands = ec_bands if ec_bands is not None else ["Acceptable"] * n
    return [
        [_entry(pair_id, sp=sp_series[i], ec=ec_series[i],
                sp_band=sp_bands[i], ec_band=ec_bands[i])]
        for i in range(n)
    ]


# ===========================================================================
# A. Internal helpers
# ===========================================================================
class TestCleanNumericHelper:
    @pytest.mark.parametrize("v", [0, 1, -5, 100, 0.0, 1.5, -3.7])
    def test_clean_numeric_true(self, v):
        assert series_mod._is_clean_numeric(v) is True

    @pytest.mark.parametrize("v", [None, True, False, "5", "", [], {}, object()])
    def test_clean_numeric_false(self, v):
        assert series_mod._is_clean_numeric(v) is False


class TestCleanBandHelper:
    @pytest.mark.parametrize("v", ["Strong", "Acceptable", "Weak",
                                    "Fails core logic", "x"])
    def test_clean_band_true(self, v):
        assert series_mod._is_clean_band(v) is True

    @pytest.mark.parametrize("v", [None, "", 0, 42, [], {}])
    def test_clean_band_false(self, v):
        assert series_mod._is_clean_band(v) is False


# ===========================================================================
# B. Core series logic
# ===========================================================================
class TestCoreSeriesLogic:
    def test_two_run_yields_length_two_series(self):
        runs = _runs_with("p1", [5, 8], [3, 7])
        out = series_mod.drift_series(runs)
        for series_key in out["p1"].values():
            assert len(series_key) == 2

    def test_three_run_yields_length_three_series(self):
        runs = _runs_with("p1", [5, 6, 7], [3, 5, 6])
        out = series_mod.drift_series(runs)
        for series_key in out["p1"].values():
            assert len(series_key) == 3

    def test_ten_run_yields_length_ten_series(self):
        sp_series = list(range(10))
        ec_series = [5] * 10
        runs = [
            [_entry("p1", sp=sp_series[i], ec=ec_series[i])]
            for i in range(10)
        ]
        out = series_mod.drift_series(runs)
        assert len(out["p1"]["single_party_scores"]) == 10
        assert len(out["p1"]["single_party_bands"]) == 10

    def test_score_series_correct_values(self):
        runs = _runs_with("p1", [5, 6, 7], [3, 5, 6])
        out = series_mod.drift_series(runs)
        assert out["p1"]["single_party_scores"] == [5, 6, 7]
        assert out["p1"]["economic_coercion_scores"] == [3, 5, 6]

    def test_band_series_correct_values(self):
        runs = _runs_with(
            "p1", [5, 5, 5], [5, 5, 5],
            sp_bands=["Strong", "Acceptable", "Weak"],
            ec_bands=["Acceptable", "Acceptable", "Strong"],
        )
        out = series_mod.drift_series(runs)
        assert out["p1"]["single_party_bands"] == ["Strong", "Acceptable", "Weak"]
        assert out["p1"]["economic_coercion_bands"] == ["Acceptable", "Acceptable", "Strong"]

    def test_full_band_label_fails_core_logic_preserved(self):
        runs = _runs_with(
            "p1", [5, 5], [5, 5],
            sp_bands=["Fails core logic", "Acceptable"],
            ec_bands=["Strong", "Strong"],
        )
        out = series_mod.drift_series(runs)
        assert out["p1"]["single_party_bands"] == [
            "Fails core logic", "Acceptable",
        ]

    def test_each_pair_has_four_series(self):
        runs = _runs_with("p1", [5, 5], [5, 5])
        out = series_mod.drift_series(runs)
        assert set(out["p1"].keys()) == {
            "single_party_scores",
            "economic_coercion_scores",
            "single_party_bands",
            "economic_coercion_bands",
        }

    def test_series_lengths_all_match_runs_length(self):
        runs = _runs_with("p1", [1, 2, 3, 4, 5], [5, 5, 5, 5, 5])
        out = series_mod.drift_series(runs)
        for series_key in out["p1"].values():
            assert len(series_key) == 5

    def test_multi_pair_each_independent(self):
        runs = [
            [_entry("a", sp=1, ec=2), _entry("b", sp=10, ec=20)],
            [_entry("a", sp=3, ec=4), _entry("b", sp=30, ec=40)],
        ]
        out = series_mod.drift_series(runs)
        assert out["a"]["single_party_scores"] == [1, 3]
        assert out["a"]["economic_coercion_scores"] == [2, 4]
        assert out["b"]["single_party_scores"] == [10, 30]
        assert out["b"]["economic_coercion_scores"] == [20, 40]

    def test_constant_series_returned_as_is(self):
        runs = _runs_with("p1", [5, 5, 5], [3, 3, 3])
        out = series_mod.drift_series(runs)
        assert out["p1"]["single_party_scores"] == [5, 5, 5]
        assert out["p1"]["economic_coercion_scores"] == [3, 3, 3]

    def test_oscillation_preserved_in_order(self):
        runs = _runs_with("p1", [5, 9, 5, 9], [5, 5, 5, 5])
        out = series_mod.drift_series(runs)
        assert out["p1"]["single_party_scores"] == [5, 9, 5, 9]

    def test_sp_and_ec_bands_independent(self):
        runs = _runs_with(
            "p1", [5, 5], [5, 5],
            sp_bands=["Strong", "Strong"],
            ec_bands=["Weak", "Fails core logic"],
        )
        out = series_mod.drift_series(runs)
        assert out["p1"]["single_party_bands"] == ["Strong", "Strong"]
        assert out["p1"]["economic_coercion_bands"] == ["Weak", "Fails core logic"]

    def test_returned_lists_independent_from_internal_state(self):
        """Returned series should be plain lists (not references to
        internal mutable state)."""
        runs = _runs_with("p1", [5, 6], [5, 5])
        out = series_mod.drift_series(runs)
        # Mutate the returned list — shouldn't affect anything.
        out["p1"]["single_party_scores"].append(999)
        # Re-call: should produce the original 2-element series.
        out2 = series_mod.drift_series(runs)
        assert out2["p1"]["single_party_scores"] == [5, 6]

    def test_chronological_ordering_preserved(self):
        """Series order matches run order — no sorting of values."""
        runs = _runs_with("p1", [9, 1, 5], [9, 1, 5])
        out = series_mod.drift_series(runs)
        assert out["p1"]["single_party_scores"] == [9, 1, 5]


# ===========================================================================
# C. Skip rules
# ===========================================================================
class TestSkipRules:
    def test_none_sp_score_drops_pair(self):
        runs = [
            [_entry("p1", sp=None)],   # type: ignore[arg-type]
            [_entry("p1", sp=5)],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_none_ec_score_drops_pair(self):
        runs = [
            [_entry("p1", ec=None)],   # type: ignore[arg-type]
            [_entry("p1", ec=5)],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_bool_sp_score_drops_pair(self):
        runs = [
            [_entry("p1", sp=True)],   # type: ignore[arg-type]
            [_entry("p1", sp=5)],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_string_sp_score_drops_pair(self):
        runs = [
            [_entry("p1", sp="five")],   # type: ignore[arg-type]
            [_entry("p1", sp=5)],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_missing_score_field_drops_pair(self):
        runs = [
            [{"pair_id": "p1",
              "single_party_band": "Strong", "economic_coercion_band": "Strong"}],
            [_entry("p1", sp=5)],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_missing_sp_band_drops_pair(self):
        runs = [
            [{"pair_id": "p1", "single_party_score": 5,
              "economic_coercion_score": 5,
              "economic_coercion_band": "Strong"}],   # missing SP band
            [_entry("p1")],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_missing_ec_band_drops_pair(self):
        runs = [
            [{"pair_id": "p1", "single_party_score": 5,
              "economic_coercion_score": 5,
              "single_party_band": "Strong"}],   # missing EC band
            [_entry("p1")],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_empty_string_band_drops_pair(self):
        runs = [
            [_entry("p1", sp_band="")],
            [_entry("p1")],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_non_string_band_drops_pair(self):
        runs = [
            [_entry("p1", sp_band=42)],   # type: ignore[arg-type]
            [_entry("p1")],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_one_bad_pair_others_kept(self):
        runs = [
            [_entry("good", sp=5, ec=5),
             _entry("bad",  sp=None, ec=5)],   # type: ignore[arg-type]
            [_entry("good", sp=8, ec=5),
             _entry("bad",  sp=5, ec=5)],
        ]
        out = series_mod.drift_series(runs)
        assert "good" in out
        assert "bad" not in out


# ===========================================================================
# D. Pair presence — partial drops, legacy fallback
# ===========================================================================
class TestPairPresence:
    def test_partial_presence_dropped(self):
        runs = [
            [_entry("always", sp=5, ec=5),
             _entry("sometimes", sp=5, ec=5)],
            [_entry("always", sp=8, ec=5)],
        ]
        out = series_mod.drift_series(runs)
        assert "always" in out
        assert "sometimes" not in out

    def test_pair_in_first_only_dropped(self):
        runs = [
            [_entry("first_only", sp=5, ec=5)],
            [],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_pair_in_last_only_dropped(self):
        runs = [
            [],
            [_entry("last_only", sp=5, ec=5)],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_pair_in_middle_only_dropped(self):
        runs = [
            [],
            [_entry("middle", sp=5, ec=5)],
            [],
        ]
        assert series_mod.drift_series(runs) == {}

    def test_legacy_entries_use_pos_ids(self):
        """Entries without pair_id share pos_<i> across runs at same pos."""
        runs = [
            [_legacy_entry(sp=5, ec=5)],
            [_legacy_entry(sp=8, ec=5)],
        ]
        out = series_mod.drift_series(runs)
        assert "pos_0" in out
        assert out["pos_0"]["single_party_scores"] == [5, 8]


# ===========================================================================
# E. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_runs_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            series_mod.drift_series("nope")  # type: ignore[arg-type]

    def test_zero_runs_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            series_mod.drift_series([])

    def test_one_run_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            series_mod.drift_series([[_entry("p1")]])

    def test_run_not_list_raises(self):
        with pytest.raises(ValueError):
            series_mod.drift_series([_entry("p1"), _entry("p2")])  # type: ignore[list-item]

    def test_entry_not_dict_raises(self):
        with pytest.raises(ValueError):
            series_mod.drift_series([["bad"], [_entry("p1")]])  # type: ignore[list-item]


# ===========================================================================
# F. Wrapper — drift_series_for_run_ids
# ===========================================================================
class TestWrapper:
    def test_loads_and_computes_byte_equal_to_direct(self):
        ep.save_comparison_result("s_a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("s_b", [_entry("p1", sp=8, ec=5)])
        out = series_mod.drift_series_for_run_ids(["s_a", "s_b"])
        direct = series_mod.drift_series([
            [_entry("p1", sp=5, ec=5)],
            [_entry("p1", sp=8, ec=5)],
        ])
        assert out == direct

    def test_three_run_via_wrapper(self):
        for i, sp in enumerate((5, 6, 9)):
            ep.save_comparison_result(
                f"chrono_{i}", [_entry("p1", sp=sp, ec=5)],
            )
        out = series_mod.drift_series_for_run_ids(
            ["chrono_0", "chrono_1", "chrono_2"])
        assert out["p1"]["single_party_scores"] == [5, 6, 9]

    def test_chronological_order_drives_series(self):
        """Unit 23 invariant: the wrapper reorders run_ids by
        ``metadata.created_at`` regardless of caller order. Run ids
        are chosen so alphabetical tiebreak matches save order —
        important on Windows where back-to-back saves can share a
        timestamp."""
        ep.save_comparison_result("r1", [_entry("p1", sp=2, ec=5)])
        ep.save_comparison_result("r2", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("r3", [_entry("p1", sp=9, ec=5)])
        forward = series_mod.drift_series_for_run_ids(["r1", "r2", "r3"])
        reverse = series_mod.drift_series_for_run_ids(["r3", "r2", "r1"])
        assert forward["p1"]["single_party_scores"] == [2, 5, 9]
        assert reverse == forward

    def test_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            series_mod.drift_series_for_run_ids("nope")  # type: ignore[arg-type]

    def test_zero_run_ids_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            series_mod.drift_series_for_run_ids([])

    def test_single_run_id_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            series_mod.drift_series_for_run_ids(["only"])

    def test_malformed_run_id_raises_value_error(self):
        with pytest.raises(ValueError):
            series_mod.drift_series_for_run_ids(["bad/id", "anything"])

    def test_missing_run_raises_filenotfound(self):
        ep.save_comparison_result("present", [_entry("p1")])
        with pytest.raises(FileNotFoundError):
            series_mod.drift_series_for_run_ids(["present", "missing"])

    def test_validates_all_ids_before_loading(self):
        ep.save_comparison_result("good", [_entry("p1")])
        with pytest.raises(ValueError):
            series_mod.drift_series_for_run_ids(["good", "bad/id"])

    def test_legacy_runs_via_wrapper(self):
        ep.save_comparison_result("leg1", [_legacy_entry(sp=5, ec=5)])
        ep.save_comparison_result("leg2", [_legacy_entry(sp=9, ec=5)])
        out = series_mod.drift_series_for_run_ids(["leg1", "leg2"])
        assert "pos_0" in out
        assert out["pos_0"]["single_party_scores"] == [5, 9]

    def test_empty_runs_via_wrapper_returns_empty(self):
        ep.save_comparison_result("e1", [])
        ep.save_comparison_result("e2", [])
        assert series_mod.drift_series_for_run_ids(["e1", "e2"]) == {}

    def test_wrapper_with_two_pairs(self):
        ep.save_comparison_result("w1", [
            _entry("a", sp=5, ec=5),
            _entry("b", sp=10, ec=10),
        ])
        ep.save_comparison_result("w2", [
            _entry("a", sp=8, ec=5),
            _entry("b", sp=10, ec=10),
        ])
        out = series_mod.drift_series_for_run_ids(["w1", "w2"])
        assert out["a"]["single_party_scores"] == [5, 8]
        assert out["b"]["single_party_scores"] == [10, 10]

    def test_wrapper_drops_partial_presence_pair(self):
        ep.save_comparison_result("pp1", [
            _entry("always", sp=5, ec=5),
            _entry("sometimes", sp=5, ec=5),
        ])
        ep.save_comparison_result("pp2", [
            _entry("always", sp=8, ec=5),
        ])
        out = series_mod.drift_series_for_run_ids(["pp1", "pp2"])
        assert "always" in out
        assert "sometimes" not in out

    def test_wrapper_drops_pair_with_missing_band(self):
        ep.save_comparison_result("mb1", [
            {"pair_id": "p1", "single_party_score": 5,
             "economic_coercion_score": 5,
             "economic_coercion_band": "Strong"},
        ])
        ep.save_comparison_result("mb2", [_entry("p1")])
        assert series_mod.drift_series_for_run_ids(["mb1", "mb2"]) == {}


# ===========================================================================
# G. Endpoint — POST /elins/regression/drift/series
# ===========================================================================
class TestEndpoint:
    def _store_three_runs(self):
        for i, sp in enumerate((5, 7, 10)):
            ep.save_comparison_result(
                f"ep_{i}", [_entry("p1", sp=sp, ec=5)],
            )

    def test_valid_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_has_pair_id_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert "p1" in body

    def test_per_pair_has_four_series_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert set(body["p1"].keys()) == {
            "single_party_scores", "economic_coercion_scores",
            "single_party_bands", "economic_coercion_bands",
        }

    def test_series_values_match_input_order(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        body = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        ).json()
        assert body["p1"]["single_party_scores"] == [5, 7, 10]

    def test_unauth_returns_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["a", "b"]},
        )
        assert resp.status_code == 401

    def test_missing_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/series",
            json={}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_run_ids_not_list_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": "nope"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_zero_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": []}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_one_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("only", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["only"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_run_id_returns_400_with_index(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["good", "bad$id"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400
        msg = str(resp.json())
        assert "run_ids[1]" in msg

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("present", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["present", "ghost"]},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        direct = series_mod.drift_series_for_run_ids(
            ["ep_0", "ep_1", "ep_2"])
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        r1 = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        r2 = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        assert r1.json() == r2.json()

    def test_empty_runs_returns_empty_dict(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("e1", [])
        ep.save_comparison_result("e2", [])
        resp = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["e1", "e2"]},
            headers=_auth(sid),
        )
        assert resp.json() == {}

    def test_partial_presence_pair_absent_from_response(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("p1", [
            _entry("always", sp=5, ec=5),
            _entry("sometimes", sp=5, ec=5),
        ])
        ep.save_comparison_result("p2", [
            _entry("always", sp=5, ec=5),
        ])
        body = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["p1", "p2"]},
            headers=_auth(sid),
        ).json()
        assert "always" in body
        assert "sometimes" not in body

    def test_two_pair_response(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("twoP_1", [
            _entry("a", sp=5, ec=5),
            _entry("b", sp=10, ec=10),
        ])
        ep.save_comparison_result("twoP_2", [
            _entry("a", sp=8, ec=5),
            _entry("b", sp=10, ec=10),
        ])
        body = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["twoP_1", "twoP_2"]},
            headers=_auth(sid),
        ).json()
        assert body["a"]["single_party_scores"] == [5, 8]
        assert body["b"]["single_party_scores"] == [10, 10]

    def test_band_series_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("bd1", [
            _entry("p1", sp_band="Strong", ec_band="Acceptable"),
        ])
        ep.save_comparison_result("bd2", [
            _entry("p1", sp_band="Acceptable", ec_band="Fails core logic"),
        ])
        body = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["bd1", "bd2"]},
            headers=_auth(sid),
        ).json()
        assert body["p1"]["single_party_bands"] == ["Strong", "Acceptable"]
        assert body["p1"]["economic_coercion_bands"] == [
            "Acceptable", "Fails core logic",
        ]


# ===========================================================================
# H. Determinism + ordering
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeated_calls(self):
        runs = _runs_with("p1", [5, 6, 7], [3, 5, 6])
        assert series_mod.drift_series(runs) == series_mod.drift_series(runs)

    def test_alphabetical_pair_id_ordering(self):
        runs = [
            [_entry("zeta",  sp=5, ec=5),
             _entry("alpha", sp=5, ec=5),
             _entry("mid",   sp=5, ec=5)],
            [_entry("zeta",  sp=8, ec=5),
             _entry("alpha", sp=8, ec=5),
             _entry("mid",   sp=8, ec=5)],
        ]
        out = series_mod.drift_series(runs)
        assert list(out.keys()) == ["alpha", "mid", "zeta"]

    def test_input_runs_not_mutated(self):
        runs = _runs_with("p1", [5, 6], [5, 5])
        before = repr(runs)
        series_mod.drift_series(runs)
        assert repr(runs) == before


# ===========================================================================
# I. Source-code purity / module surface
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(series_mod)

    def test_no_llm_imports(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network_imports(self):
        src = self._src()
        for forbidden in ("import urllib", "import http",
                          "import requests", "import socket",
                          "from urllib", "from http", "from requests"):
            assert forbidden not in src

    def test_no_logging(self):
        src = self._src()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._src()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src

    def test_no_subprocess_or_eval(self):
        src = self._src()
        for forbidden in ("subprocess", "exec(", "eval("):
            assert forbidden not in src

    def test_drift_series_pure_no_open(self):
        """drift_series has no file I/O — only the wrapper does."""
        src = inspect.getsource(series_mod.drift_series)
        assert "open(" not in src

    def test_no_basin_inference_imports(self):
        src = self._src()
        for pattern in (
            "import elins_dashboard", "from elins_dashboard",
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
        ):
            assert pattern not in src


class TestModuleSurface:
    def test_drift_series_callable(self):
        assert callable(series_mod.drift_series)

    def test_drift_series_for_run_ids_callable(self):
        assert callable(series_mod.drift_series_for_run_ids)

    def test_field_constants_locked(self):
        assert series_mod._SP_SCORE_FIELD == "single_party_score"
        assert series_mod._EC_SCORE_FIELD == "economic_coercion_score"
        assert series_mod._SP_BAND_FIELD == "single_party_band"
        assert series_mod._EC_BAND_FIELD == "economic_coercion_band"


# ===========================================================================
# J. End-to-end via persistence
# ===========================================================================
class TestEndToEnd:
    def test_store_then_series(self, client, app_module):
        sid = _make_user_session(app_module)

        sp_payload = {
            "timeline_id": "case01_sp",
            "points": [
                {"t": "t0",
                 "regime_competition": 0.5, "autocratization": 0.5,
                 "repression_index": 0.5, "digital_repression": 0.5,
                 "perceived_threat": 0.5, "fear_signal": 0.5,
                 "dissent_capacity": 0.5, "normative_constraint": 0.5,
                 "support_buffer": 0.5},
            ],
        }
        ec_payload = {
            "timeline_id": "case01_ec",
            "points": [
                {"t": "t0",
                 "economic_pressure": 0.5, "material_insecurity": 0.5,
                 "state_coercion": 0.5, "compliance_signal": 0.5,
                 "resistance_capacity": 0.5, "support_buffer": 0.5},
            ],
        }
        store_body = {"pairs": [{
            "single_party_timeline": sp_payload,
            "economic_timeline":     ec_payload,
        }]}

        for rid in ("morning", "evening"):
            r = client.post("/elins/regression/store",
                            json={"run_id": rid, **store_body},
                            headers=_auth(sid))
            assert r.status_code == 200

        # Series shape: same payload twice → both series have length 2.
        s = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["morning", "evening"]},
            headers=_auth(sid),
        )
        assert s.status_code == 200
        body = s.json()
        pid = "case01_sp::case01_ec"
        assert pid in body
        for series_key in body[pid].values():
            assert len(series_key) == 2
