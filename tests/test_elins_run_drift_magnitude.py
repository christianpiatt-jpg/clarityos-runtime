"""
Tests for ELINS Unit 15 — score-magnitude drift.

Layered coverage (≥ 60 tests, target 70+):
    A. Internal helpers — _all_numeric, _step_diffs, _dimension_metrics
    B. Per-pair magnitude rules — range / max_swing / mean_step
    C. Multi-pair / partial presence / legacy entries
    D. Validation
    E. Wrapper — drift_magnitude_for_run_ids
    F. Endpoint — POST /elins/regression/drift/magnitude
    G. Determinism + ordering
    H. Source-code purity / module surface
    I. End-to-end: store → store → magnitude
"""
from __future__ import annotations

import inspect
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_run_drift_magnitude as mag_mod


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
def _entry(pair_id: str = "p::a", *, sp: int = 5, ec: int = 7) -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp,
        "economic_coercion_score": ec,
    }


def _legacy_entry(*, sp: int = 5, ec: int = 7) -> dict:
    e = _entry(sp=sp, ec=ec)
    del e["pair_id"]
    return e


def _runs_with(pair_id: str, sp_series: list, ec_series: list) -> list:
    """Build N runs each containing one pair with the given series."""
    assert len(sp_series) == len(ec_series)
    return [
        [_entry(pair_id, sp=sp_series[i], ec=ec_series[i])]
        for i in range(len(sp_series))
    ]


# ===========================================================================
# A. Internal helpers
# ===========================================================================
class TestAllNumeric:
    def test_all_ints(self):
        assert mag_mod._all_numeric([1, 2, 3]) is True

    def test_all_floats(self):
        assert mag_mod._all_numeric([1.0, 2.0]) is True

    def test_mixed_int_and_float(self):
        assert mag_mod._all_numeric([1, 2.0, 3]) is True

    def test_contains_none(self):
        assert mag_mod._all_numeric([1, None, 3]) is False

    def test_contains_bool(self):
        assert mag_mod._all_numeric([1, True, 3]) is False

    def test_contains_string(self):
        assert mag_mod._all_numeric([1, "two", 3]) is False

    def test_empty(self):
        assert mag_mod._all_numeric([]) is True


class TestStepDiffs:
    def test_basic(self):
        assert mag_mod._step_diffs([5, 6, 7]) == [1, 1]

    def test_negative_steps(self):
        assert mag_mod._step_diffs([7, 5, 3]) == [2, 2]

    def test_oscillation(self):
        assert mag_mod._step_diffs([5, 9, 5]) == [4, 4]

    def test_two_elements(self):
        assert mag_mod._step_diffs([5, 8]) == [3]

    def test_constant(self):
        assert mag_mod._step_diffs([5, 5, 5]) == [0, 0]

    def test_empty(self):
        assert mag_mod._step_diffs([]) == []

    def test_single(self):
        assert mag_mod._step_diffs([5]) == []


class TestDimensionMetrics:
    def test_monotonic_up(self):
        m = mag_mod._dimension_metrics([5, 6, 7])
        assert m == {"range": 2, "max_swing": 1, "mean_step": 1.0}

    def test_monotonic_down(self):
        m = mag_mod._dimension_metrics([9, 7, 5])
        assert m == {"range": 4, "max_swing": 2, "mean_step": 2.0}

    def test_oscillation(self):
        m = mag_mod._dimension_metrics([5, 9, 5])
        assert m == {"range": 4, "max_swing": 4, "mean_step": 4.0}

    def test_constant(self):
        assert mag_mod._dimension_metrics([5, 5, 5]) == {
            "range": 0, "max_swing": 0, "mean_step": 0.0,
        }

    def test_two_elements(self):
        assert mag_mod._dimension_metrics([5, 8]) == {
            "range": 3, "max_swing": 3, "mean_step": 3.0,
        }


# ===========================================================================
# B. Per-pair magnitude rules
# ===========================================================================
class TestPerPairMagnitude:
    def test_simple_monotonic_sp_and_ec(self):
        runs = _runs_with("p1", [5, 6, 7], [3, 5, 6])
        out = mag_mod.drift_magnitude(runs)
        assert out["p1"]["single_party"] == {
            "range": 2, "max_swing": 1, "mean_step": 1.0,
        }
        assert out["p1"]["economic_coercion"] == {
            "range": 3, "max_swing": 2, "mean_step": 1.5,
        }

    def test_oscillation(self):
        runs = _runs_with("p1", [5, 9, 5], [5, 5, 5])
        out = mag_mod.drift_magnitude(runs)
        assert out["p1"]["single_party"]["max_swing"] == 4
        assert out["p1"]["economic_coercion"]["max_swing"] == 0

    def test_constant_sequence_zeros_everywhere(self):
        runs = _runs_with("p1", [7, 7, 7], [3, 3, 3])
        out = mag_mod.drift_magnitude(runs)
        assert out["p1"] == {
            "single_party":      {"range": 0, "max_swing": 0, "mean_step": 0.0},
            "economic_coercion": {"range": 0, "max_swing": 0, "mean_step": 0.0},
        }

    def test_range_max_minus_min(self):
        runs = _runs_with("p1", [3, 9, 5, 7], [5, 5, 5, 5])
        # min=3, max=9 → range=6
        assert mag_mod.drift_magnitude(runs)["p1"]["single_party"]["range"] == 6

    def test_max_swing_largest_step(self):
        runs = _runs_with("p1", [5, 6, 10, 8], [5, 5, 5, 5])
        # steps = |1|, |4|, |2| → max=4
        assert mag_mod.drift_magnitude(runs)["p1"]["single_party"]["max_swing"] == 4

    def test_mean_step_average_of_abs_diffs(self):
        runs = _runs_with("p1", [0, 5, 12, 20], [0, 0, 0, 0])
        # steps = 5, 7, 8 → mean 6.666... → 6.7
        assert mag_mod.drift_magnitude(runs)["p1"]["single_party"]["mean_step"] == 6.7

    def test_mean_step_rounded_to_one_decimal(self):
        runs = _runs_with("p1", [0, 1, 2], [0, 0, 0])
        # steps = 1, 1 → mean 1.0
        assert mag_mod.drift_magnitude(runs)["p1"]["single_party"]["mean_step"] == 1.0

    def test_two_run_minimum(self):
        runs = _runs_with("p1", [5, 8], [3, 7])
        out = mag_mod.drift_magnitude(runs)
        assert out["p1"]["single_party"] == {
            "range": 3, "max_swing": 3, "mean_step": 3.0,
        }
        assert out["p1"]["economic_coercion"] == {
            "range": 4, "max_swing": 4, "mean_step": 4.0,
        }

    def test_long_series(self):
        sp_series = list(range(10))   # 0..9, steps all 1
        ec_series = [5] * 10
        runs = [
            [_entry("p1", sp=sp_series[i], ec=ec_series[i])]
            for i in range(10)
        ]
        out = mag_mod.drift_magnitude(runs)
        assert out["p1"]["single_party"] == {
            "range": 9, "max_swing": 1, "mean_step": 1.0,
        }
        assert out["p1"]["economic_coercion"] == {
            "range": 0, "max_swing": 0, "mean_step": 0.0,
        }

    def test_range_non_negative_with_oscillation(self):
        runs = _runs_with("p1", [9, 5, 9, 5], [9, 5, 9, 5])
        out = mag_mod.drift_magnitude(runs)
        # Range is always max-min, never negative.
        assert out["p1"]["single_party"]["range"] >= 0
        assert out["p1"]["economic_coercion"]["range"] >= 0

    def test_sp_and_ec_independent(self):
        runs = _runs_with("p1", [1, 2, 3], [9, 5, 1])
        out = mag_mod.drift_magnitude(runs)
        # SP: monotone up, EC: monotone down — different metrics.
        assert out["p1"]["single_party"]["range"] == 2
        assert out["p1"]["economic_coercion"]["range"] == 8


# ===========================================================================
# C. Multi-pair / partial presence / legacy
# ===========================================================================
class TestMultiPairAndPresence:
    def test_three_pairs_each_independent(self):
        runs = [
            [_entry("a", sp=5, ec=5),
             _entry("b", sp=5, ec=5),
             _entry("c", sp=5, ec=5)],
            [_entry("a", sp=5, ec=5),
             _entry("b", sp=8, ec=5),
             _entry("c", sp=5, ec=9)],
        ]
        out = mag_mod.drift_magnitude(runs)
        assert out["a"]["single_party"]["range"] == 0
        assert out["b"]["single_party"]["range"] == 3
        assert out["c"]["economic_coercion"]["range"] == 4

    def test_partial_presence_pair_dropped(self):
        runs = [
            [_entry("always", sp=5, ec=5),
             _entry("sometimes", sp=5, ec=5)],
            [_entry("always", sp=5, ec=5)],   # sometimes missing
        ]
        out = mag_mod.drift_magnitude(runs)
        assert "always" in out
        assert "sometimes" not in out

    def test_pair_in_first_only_dropped(self):
        runs = [
            [_entry("first_only", sp=5, ec=5)],
            [],
        ]
        assert mag_mod.drift_magnitude(runs) == {}

    def test_legacy_entries_use_pos_ids(self):
        runs = [
            [_legacy_entry(sp=5, ec=5)],
            [_legacy_entry(sp=8, ec=5)],
        ]
        out = mag_mod.drift_magnitude(runs)
        # pos_0 in both → classified
        assert "pos_0" in out
        assert out["pos_0"]["single_party"]["range"] == 3

    def test_pair_with_none_sp_score_dropped(self):
        runs = [
            [_entry("p1", sp=None, ec=5)],  # type: ignore[arg-type]
            [_entry("p1", sp=5, ec=5)],
        ]
        out = mag_mod.drift_magnitude(runs)
        assert "p1" not in out

    def test_pair_with_none_ec_score_dropped(self):
        runs = [
            [_entry("p1", sp=5, ec=None)],  # type: ignore[arg-type]
            [_entry("p1", sp=5, ec=5)],
        ]
        out = mag_mod.drift_magnitude(runs)
        assert "p1" not in out

    def test_pair_with_bool_score_dropped(self):
        runs = [
            [_entry("p1", sp=True, ec=5)],   # type: ignore[arg-type]
            [_entry("p1", sp=5, ec=5)],
        ]
        out = mag_mod.drift_magnitude(runs)
        assert "p1" not in out

    def test_pair_missing_score_field_dropped(self):
        runs = [
            [{"pair_id": "p1", "economic_coercion_score": 5}],   # no SP score
            [{"pair_id": "p1", "single_party_score": 5,
              "economic_coercion_score": 5}],
        ]
        out = mag_mod.drift_magnitude(runs)
        assert "p1" not in out

    def test_one_pair_dropped_other_kept(self):
        """If one pair has bad scores it's skipped, others are still
        computed."""
        runs = [
            [_entry("good", sp=5, ec=5),
             _entry("bad",  sp=None, ec=5)],   # type: ignore[arg-type]
            [_entry("good", sp=8, ec=5),
             _entry("bad",  sp=5, ec=5)],
        ]
        out = mag_mod.drift_magnitude(runs)
        assert "good" in out
        assert "bad" not in out


# ===========================================================================
# D. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_runs_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            mag_mod.drift_magnitude("nope")  # type: ignore[arg-type]

    def test_zero_runs_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            mag_mod.drift_magnitude([])

    def test_one_run_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            mag_mod.drift_magnitude([[_entry("p1")]])

    def test_run_not_list_raises(self):
        with pytest.raises(ValueError):
            mag_mod.drift_magnitude([_entry("p1"), _entry("p2")])  # type: ignore[list-item]

    def test_entry_not_dict_raises(self):
        with pytest.raises(ValueError):
            mag_mod.drift_magnitude([["bad"], [_entry("p1")]])  # type: ignore[list-item]


# ===========================================================================
# E. Wrapper — drift_magnitude_for_run_ids
# ===========================================================================
class TestWrapper:
    def test_loads_and_computes_byte_equal_to_direct(self):
        ep.save_comparison_result("m1", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("m2", [_entry("p1", sp=8, ec=5)])
        out = mag_mod.drift_magnitude_for_run_ids(["m1", "m2"])
        direct = mag_mod.drift_magnitude([
            [_entry("p1", sp=5, ec=5)],
            [_entry("p1", sp=8, ec=5)],
        ])
        assert out == direct

    def test_three_runs_via_wrapper(self):
        for i, sp in enumerate((5, 6, 7)):
            ep.save_comparison_result(
                f"chrono_{i}",
                [_entry("p1", sp=sp, ec=5)],
            )
        out = mag_mod.drift_magnitude_for_run_ids(
            ["chrono_0", "chrono_1", "chrono_2"])
        assert out["p1"]["single_party"] == {
            "range": 2, "max_swing": 1, "mean_step": 1.0,
        }

    def test_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            mag_mod.drift_magnitude_for_run_ids("nope")  # type: ignore[arg-type]

    def test_zero_run_ids_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            mag_mod.drift_magnitude_for_run_ids([])

    def test_single_run_id_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            mag_mod.drift_magnitude_for_run_ids(["only"])

    def test_malformed_run_id_raises_value_error(self):
        with pytest.raises(ValueError):
            mag_mod.drift_magnitude_for_run_ids(["bad/id", "anything"])

    def test_missing_run_raises_filenotfound(self):
        ep.save_comparison_result("present", [_entry("p1")])
        with pytest.raises(FileNotFoundError):
            mag_mod.drift_magnitude_for_run_ids(["present", "missing"])

    def test_validates_all_ids_before_loading(self):
        ep.save_comparison_result("good", [_entry("p1")])
        with pytest.raises(ValueError):
            mag_mod.drift_magnitude_for_run_ids(["good", "bad/id"])

    def test_chronological_order_drives_metrics(self):
        ep.save_comparison_result("low",  [_entry("p1", sp=2, ec=5)])
        ep.save_comparison_result("high", [_entry("p1", sp=9, ec=5)])
        # forward: range=7, max_swing=7
        forward = mag_mod.drift_magnitude_for_run_ids(["low", "high"])
        reverse = mag_mod.drift_magnitude_for_run_ids(["high", "low"])
        # range and max_swing don't depend on order; both use absolute
        # differences. So forward and reverse should be identical here.
        assert forward == reverse

    def test_wrapper_with_three_pairs_via_persistence(self):
        ep.save_comparison_result("r1", [
            _entry("a", sp=5, ec=5), _entry("b", sp=5, ec=5),
        ])
        ep.save_comparison_result("r2", [
            _entry("a", sp=5, ec=5), _entry("b", sp=8, ec=5),
        ])
        ep.save_comparison_result("r3", [
            _entry("a", sp=5, ec=5), _entry("b", sp=10, ec=5),
        ])
        out = mag_mod.drift_magnitude_for_run_ids(["r1", "r2", "r3"])
        assert out["a"]["single_party"]["range"] == 0
        assert out["b"]["single_party"]["range"] == 5
        assert out["b"]["single_party"]["max_swing"] == 3
        assert out["b"]["single_party"]["mean_step"] == 2.5

    def test_legacy_runs_via_wrapper(self):
        ep.save_comparison_result("leg1", [_legacy_entry(sp=5, ec=5)])
        ep.save_comparison_result("leg2", [_legacy_entry(sp=9, ec=5)])
        out = mag_mod.drift_magnitude_for_run_ids(["leg1", "leg2"])
        assert "pos_0" in out
        assert out["pos_0"]["single_party"]["range"] == 4

    def test_empty_runs_via_wrapper_returns_empty(self):
        ep.save_comparison_result("e1", [])
        ep.save_comparison_result("e2", [])
        assert mag_mod.drift_magnitude_for_run_ids(["e1", "e2"]) == {}


# ===========================================================================
# F. Endpoint — POST /elins/regression/drift/magnitude
# ===========================================================================
class TestEndpoint:
    def _store_three_runs_with_one_pair(self):
        for i, sp in enumerate((5, 7, 10)):
            ep.save_comparison_result(
                f"mag_{i}", [_entry("p1", sp=sp, ec=5)],
            )

    def test_valid_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_has_pair_id_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs_with_one_pair()
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["mag_0", "mag_1", "mag_2"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert "p1" in body
        assert set(body["p1"].keys()) == {"single_party", "economic_coercion"}
        for dim in ("single_party", "economic_coercion"):
            assert set(body["p1"][dim].keys()) == {"range", "max_swing", "mean_step"}

    def test_metric_values_correct_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs_with_one_pair()
        # SP: 5, 7, 10 → range=5, swings=2,3 → max=3, mean=2.5
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["mag_0", "mag_1", "mag_2"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["p1"]["single_party"] == {
            "range": 5, "max_swing": 3, "mean_step": 2.5,
        }

    def test_unauth_returns_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["a", "b"]},
        )
        assert resp.status_code == 401

    def test_missing_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_run_ids_not_list_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": "nope"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_zero_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": []}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_one_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("only", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["only"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_run_id_returns_400_with_index(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["good", "bad$id"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400
        msg = str(resp.json())
        assert "run_ids[1]" in msg

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("present", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["present", "ghost"]},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs_with_one_pair()
        direct = mag_mod.drift_magnitude_for_run_ids(
            ["mag_0", "mag_1", "mag_2"])
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["mag_0", "mag_1", "mag_2"]},
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs_with_one_pair()
        r1 = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["mag_0", "mag_1", "mag_2"]},
            headers=_auth(sid),
        )
        r2 = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["mag_0", "mag_1", "mag_2"]},
            headers=_auth(sid),
        )
        assert r1.json() == r2.json()

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
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["p1", "p2"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert "always" in body
        assert "sometimes" not in body

    def test_empty_runs_returns_empty_dict(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("e1", [])
        ep.save_comparison_result("e2", [])
        resp = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["e1", "e2"]},
            headers=_auth(sid),
        )
        assert resp.json() == {}

    def test_two_pair_response(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("twoPair_1", [
            _entry("a", sp=5, ec=5),
            _entry("b", sp=5, ec=5),
        ])
        ep.save_comparison_result("twoPair_2", [
            _entry("a", sp=8, ec=5),
            _entry("b", sp=5, ec=9),
        ])
        body = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["twoPair_1", "twoPair_2"]},
            headers=_auth(sid),
        ).json()
        assert body["a"]["single_party"]["range"] == 3
        assert body["b"]["economic_coercion"]["range"] == 4


# ===========================================================================
# G. Determinism + ordering
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeated_calls(self):
        runs = [
            [_entry("p1", sp=5, ec=5), _entry("p2", sp=5, ec=5)],
            [_entry("p1", sp=8, ec=5), _entry("p2", sp=5, ec=9)],
        ]
        a = mag_mod.drift_magnitude(runs)
        b = mag_mod.drift_magnitude(runs)
        assert a == b

    def test_alphabetical_pair_id_ordering(self):
        runs = [
            [_entry("zeta",  sp=5, ec=5),
             _entry("alpha", sp=5, ec=5),
             _entry("mid",   sp=5, ec=5)],
            [_entry("zeta",  sp=8, ec=5),
             _entry("alpha", sp=8, ec=5),
             _entry("mid",   sp=8, ec=5)],
        ]
        out = mag_mod.drift_magnitude(runs)
        assert list(out.keys()) == ["alpha", "mid", "zeta"]

    def test_input_runs_not_mutated(self):
        runs = [
            [_entry("p1", sp=5, ec=5)],
            [_entry("p1", sp=8, ec=5)],
        ]
        before = repr(runs)
        mag_mod.drift_magnitude(runs)
        assert repr(runs) == before

    def test_dimension_subdict_keys_locked(self):
        runs = _runs_with("p1", [5, 6], [5, 5])
        out = mag_mod.drift_magnitude(runs)
        for dim in ("single_party", "economic_coercion"):
            assert set(out["p1"][dim].keys()) == {
                "range", "max_swing", "mean_step",
            }


# ===========================================================================
# H. Source-code purity / module surface
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(mag_mod)

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

    def test_drift_magnitude_pure_no_open(self):
        """drift_magnitude has no file I/O — only the wrapper does."""
        src = inspect.getsource(mag_mod.drift_magnitude)
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
    def test_drift_magnitude_callable(self):
        assert callable(mag_mod.drift_magnitude)

    def test_drift_magnitude_for_run_ids_callable(self):
        assert callable(mag_mod.drift_magnitude_for_run_ids)

    def test_field_constants_locked(self):
        assert mag_mod._SP_FIELD == "single_party_score"
        assert mag_mod._EC_FIELD == "economic_coercion_score"

    def test_mean_step_round_digits_locked(self):
        assert mag_mod._MEAN_STEP_ROUND_DIGITS == 1


# ===========================================================================
# I. End-to-end: store via endpoint, magnitude via endpoint
# ===========================================================================
class TestEndToEnd:
    def test_store_then_magnitude(self, client, app_module):
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

        # Two stores under different ids — identical payload → zero
        # magnitude.
        for rid in ("morning", "evening"):
            r = client.post("/elins/regression/store",
                            json={"run_id": rid, **store_body},
                            headers=_auth(sid))
            assert r.status_code == 200

        m = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["morning", "evening"]},
            headers=_auth(sid),
        )
        assert m.status_code == 200
        body = m.json()
        # Identical inputs → zero range/swing/mean_step everywhere.
        assert body["case01_sp::case01_ec"]["single_party"] == {
            "range": 0, "max_swing": 0, "mean_step": 0.0,
        }
        assert body["case01_sp::case01_ec"]["economic_coercion"] == {
            "range": 0, "max_swing": 0, "mean_step": 0.0,
        }
