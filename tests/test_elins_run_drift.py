"""
Tests for ELINS Unit 13 — multi-run drift detection.

Layered coverage (≥ 60 tests, target 70+):
    A. Strict-monotonicity helpers
    B. Single-pair classification (the four-way label rule)
    C. detect_drift core — multi-run, multi-pair
    D. Pair presence / partial presence
    E. Validation & error handling
    F. detect_drift_for_run_ids wrapper
    G. POST /elins/regression/drift endpoint
    H. Determinism + ordering
    I. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_run_drift as drift_mod


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
        "score_delta": ec - sp,
        "single_party_band": "Strong",
        "economic_coercion_band": "Strong",
        "band_delta": "same",
    }


def _legacy_entry(*, sp: int = 5, ec: int = 7) -> dict:
    """Entry without pair_id (synthesises pos_<i>)."""
    e = _entry(sp=sp, ec=ec)
    del e["pair_id"]
    return e


def _three_runs_with(pair_id: str, sp_series: list, ec_series: list) -> list:
    """Build a list of 3 runs each containing a single pair_id with the
    given SP and EC scores per run."""
    assert len(sp_series) == len(ec_series)
    return [
        [_entry(pair_id, sp=sp_series[i], ec=ec_series[i])]
        for i in range(len(sp_series))
    ]


# ===========================================================================
# A. Strict-monotonicity helpers
# ===========================================================================
class TestStrictMonotonicityHelpers:
    @pytest.mark.parametrize("seq", [
        [1, 2, 3], [0, 1, 2, 3, 4], [-3, -2, -1], [1, 2],
    ])
    def test_strictly_increasing_true(self, seq):
        assert drift_mod._strictly_increasing(seq) is True

    @pytest.mark.parametrize("seq", [
        [1, 1, 2],          # equal-adjacent
        [3, 2, 1],          # decreasing
        [1, 3, 2],          # not monotone
        [5, 5, 5],          # all equal
    ])
    def test_strictly_increasing_false(self, seq):
        assert drift_mod._strictly_increasing(seq) is False

    @pytest.mark.parametrize("seq", [
        [3, 2, 1], [4, 3, 2, 1, 0], [-1, -2, -3], [9, 8],
    ])
    def test_strictly_decreasing_true(self, seq):
        assert drift_mod._strictly_decreasing(seq) is True

    @pytest.mark.parametrize("seq", [
        [3, 3, 2], [1, 2, 3], [2, 1, 3], [5, 5, 5],
    ])
    def test_strictly_decreasing_false(self, seq):
        assert drift_mod._strictly_decreasing(seq) is False

    @pytest.mark.parametrize("seq", [
        [5, 5, 5], [0, 0], ["a", "a", "a"],
    ])
    def test_all_identical_true(self, seq):
        assert drift_mod._all_identical(seq) is True

    @pytest.mark.parametrize("seq", [
        [5, 6, 5], [1, 2], [0, 1, 0],
    ])
    def test_all_identical_false(self, seq):
        assert drift_mod._all_identical(seq) is False

    def test_empty_seq_helpers(self):
        # Both monotonicity checks return True for empty sequences
        # (vacuously). all_identical also True for empty.
        assert drift_mod._strictly_increasing([]) is True
        assert drift_mod._strictly_decreasing([]) is True
        assert drift_mod._all_identical([]) is True


# ===========================================================================
# B. Single-pair classification (_classify_pair)
# ===========================================================================
class TestPairClassification:
    def test_stable_both_constant(self):
        assert drift_mod._classify_pair([5, 5, 5], [7, 7, 7]) == "stable"

    def test_trending_up_sp_increases_ec_flat(self):
        assert drift_mod._classify_pair([5, 6, 7], [5, 5, 5]) == "trending_up"

    def test_trending_up_ec_increases_sp_flat(self):
        assert drift_mod._classify_pair([5, 5, 5], [3, 4, 5]) == "trending_up"

    def test_trending_up_both_increase(self):
        assert drift_mod._classify_pair([1, 2, 3], [4, 5, 6]) == "trending_up"

    def test_trending_down_sp_decreases_ec_flat(self):
        assert drift_mod._classify_pair([5, 4, 3], [5, 5, 5]) == "trending_down"

    def test_trending_down_ec_decreases_sp_flat(self):
        assert drift_mod._classify_pair([5, 5, 5], [9, 8, 7]) == "trending_down"

    def test_trending_down_both_decrease(self):
        assert drift_mod._classify_pair([5, 4, 3], [9, 8, 7]) == "trending_down"

    def test_volatile_sp_up_ec_down(self):
        assert drift_mod._classify_pair([1, 2, 3], [9, 8, 7]) == "volatile"

    def test_volatile_sp_down_ec_up(self):
        assert drift_mod._classify_pair([9, 8, 7], [1, 2, 3]) == "volatile"

    def test_volatile_oscillation(self):
        assert drift_mod._classify_pair([5, 7, 5], [5, 5, 5]) == "volatile"

    def test_volatile_flat_then_up(self):
        # SP: [5,5,6] not strictly increasing (equal-adjacent at start)
        # EC: [5,5,5] flat. Not all flat, not strictly inc anywhere.
        assert drift_mod._classify_pair([5, 5, 6], [5, 5, 5]) == "volatile"

    def test_volatile_partial_monotonic(self):
        # SP: [5,6,6] not strictly inc (equal at end)
        # EC: [5,5,5] flat. Volatile.
        assert drift_mod._classify_pair([5, 6, 6], [5, 5, 5]) == "volatile"

    def test_volatile_when_sp_score_is_none(self):
        assert drift_mod._classify_pair([5, None, 7], [5, 5, 5]) == "volatile"

    def test_volatile_when_ec_score_is_none(self):
        assert drift_mod._classify_pair([5, 5, 5], [None, 5, 5]) == "volatile"

    def test_two_run_series_strict_inc(self):
        assert drift_mod._classify_pair([5, 6], [5, 5]) == "trending_up"

    def test_two_run_series_strict_dec(self):
        assert drift_mod._classify_pair([6, 5], [5, 5]) == "trending_down"

    def test_two_run_series_stable(self):
        assert drift_mod._classify_pair([5, 5], [5, 5]) == "stable"

    def test_long_series_stable(self):
        n = 10
        assert drift_mod._classify_pair([5] * n, [7] * n) == "stable"

    def test_long_series_strict_increasing(self):
        assert drift_mod._classify_pair(list(range(10)), [5] * 10) == "trending_up"


# ===========================================================================
# C. detect_drift core — multi-run, multi-pair
# ===========================================================================
class TestDetectDriftCore:
    def test_returns_dict_with_required_keys(self):
        runs = _three_runs_with("p::a", [5, 5, 5], [7, 7, 7])
        r = drift_mod.detect_drift(runs)
        for key in ("stable", "trending_up", "trending_down",
                    "volatile", "summary"):
            assert key in r
        for sk in ("stable", "trending_up", "trending_down", "volatile"):
            assert sk in r["summary"]

    def test_classifies_stable_pair(self):
        runs = _three_runs_with("p::a", [5, 5, 5], [7, 7, 7])
        r = drift_mod.detect_drift(runs)
        assert r["stable"] == ["p::a"]

    def test_classifies_trending_up(self):
        runs = _three_runs_with("p::a", [5, 6, 7], [5, 5, 5])
        r = drift_mod.detect_drift(runs)
        assert r["trending_up"] == ["p::a"]

    def test_classifies_trending_down(self):
        runs = _three_runs_with("p::a", [9, 8, 7], [9, 8, 7])
        r = drift_mod.detect_drift(runs)
        assert r["trending_down"] == ["p::a"]

    def test_classifies_volatile(self):
        runs = _three_runs_with("p::a", [5, 7, 5], [5, 5, 5])
        r = drift_mod.detect_drift(runs)
        assert r["volatile"] == ["p::a"]

    def test_multi_pair_each_in_its_own_bucket(self):
        runs = [
            [_entry("stable", sp=5, ec=7),
             _entry("up",     sp=5, ec=5),
             _entry("down",   sp=9, ec=9),
             _entry("vol",    sp=5, ec=9)],
            [_entry("stable", sp=5, ec=7),
             _entry("up",     sp=6, ec=5),
             _entry("down",   sp=7, ec=7),
             _entry("vol",    sp=6, ec=7)],
            [_entry("stable", sp=5, ec=7),
             _entry("up",     sp=7, ec=5),
             _entry("down",   sp=5, ec=5),
             _entry("vol",    sp=7, ec=5)],
        ]
        r = drift_mod.detect_drift(runs)
        assert r["stable"]        == ["stable"]
        assert r["trending_up"]   == ["up"]
        assert r["trending_down"] == ["down"]
        assert r["volatile"]      == ["vol"]

    def test_summary_counts(self):
        runs = [
            [_entry("a", sp=5, ec=7),
             _entry("b", sp=5, ec=5),
             _entry("c", sp=5, ec=9)],
            [_entry("a", sp=5, ec=7),
             _entry("b", sp=6, ec=6),
             _entry("c", sp=5, ec=9)],
        ]
        r = drift_mod.detect_drift(runs)
        assert r["summary"] == {
            "stable":        2,   # a and c
            "trending_up":   1,   # b (sp=5,6 strict inc; ec also up)
            "trending_down": 0,
            "volatile":      0,
        }

    def test_two_run_input_minimum(self):
        runs = [
            [_entry("p::a", sp=5, ec=5)],
            [_entry("p::a", sp=5, ec=5)],
        ]
        r = drift_mod.detect_drift(runs)
        assert r["stable"] == ["p::a"]

    def test_long_series_classification(self):
        sp_series = list(range(10))
        ec_series = [5] * 10
        runs = [
            [_entry("p::a", sp=sp_series[i], ec=ec_series[i])]
            for i in range(10)
        ]
        r = drift_mod.detect_drift(runs)
        assert r["trending_up"] == ["p::a"]


# ===========================================================================
# D. Partial presence — pairs missing from some runs
# ===========================================================================
class TestPartialPresence:
    def test_pair_in_first_only_dropped(self):
        runs = [
            [_entry("p::only_first", sp=5, ec=5)],
            [],
            [],
        ]
        r = drift_mod.detect_drift(runs)
        assert r["summary"]["stable"] == 0
        assert r["summary"]["volatile"] == 0
        assert r["stable"] == [] and r["volatile"] == []

    def test_pair_in_all_classified_pair_in_some_dropped(self):
        runs = [
            [_entry("always", sp=5, ec=5),
             _entry("sometimes", sp=5, ec=5)],
            [_entry("always", sp=5, ec=5)],   # sometimes missing
            [_entry("always", sp=5, ec=5),
             _entry("sometimes", sp=5, ec=5)],
        ]
        r = drift_mod.detect_drift(runs)
        # Only "always" classified.
        assert r["stable"] == ["always"]
        assert "sometimes" not in r["stable"]
        assert "sometimes" not in r["volatile"]

    def test_legacy_entries_use_pos_ids(self):
        """Entries without pair_id share pos_<i> across runs if the
        position matches."""
        runs = [
            [_legacy_entry(sp=5, ec=5)],
            [_legacy_entry(sp=5, ec=5)],
        ]
        r = drift_mod.detect_drift(runs)
        # pos_0 in both runs → classified as stable.
        assert r["stable"] == ["pos_0"]


# ===========================================================================
# E. detect_drift validation
# ===========================================================================
class TestDetectDriftValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            drift_mod.detect_drift("nope")  # type: ignore[arg-type]

    def test_zero_runs_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            drift_mod.detect_drift([])

    def test_single_run_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            drift_mod.detect_drift([[_entry()]])

    def test_run_not_list_raises(self):
        # Propagated from _normalise_run.
        with pytest.raises(ValueError):
            drift_mod.detect_drift([_entry(), _entry()])  # type: ignore[list-item]

    def test_entry_not_dict_raises(self):
        with pytest.raises(ValueError):
            drift_mod.detect_drift([["bad"], [_entry()]])  # type: ignore[list-item]


# ===========================================================================
# F. detect_drift_for_run_ids wrapper
# ===========================================================================
class TestDetectDriftForRunIdsWrapper:
    def test_loads_and_classifies_byte_equal_to_direct(self):
        ep.save_comparison_result("d_a", [_entry("p::x", sp=5, ec=5)])
        ep.save_comparison_result("d_b", [_entry("p::x", sp=6, ec=5)])
        ep.save_comparison_result("d_c", [_entry("p::x", sp=7, ec=5)])
        out = drift_mod.detect_drift_for_run_ids(["d_a", "d_b", "d_c"])
        direct = drift_mod.detect_drift([
            [_entry("p::x", sp=5, ec=5)],
            [_entry("p::x", sp=6, ec=5)],
            [_entry("p::x", sp=7, ec=5)],
        ])
        assert out == direct

    def test_non_list_run_ids_raises_value_error(self):
        with pytest.raises(ValueError, match="expected a list"):
            drift_mod.detect_drift_for_run_ids("nope")  # type: ignore[arg-type]

    def test_fewer_than_two_run_ids_raises_value_error(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            drift_mod.detect_drift_for_run_ids([])
        with pytest.raises(ValueError, match=">= 2 runs"):
            drift_mod.detect_drift_for_run_ids(["only_one"])

    def test_malformed_run_id_raises_value_error(self):
        with pytest.raises(ValueError):
            drift_mod.detect_drift_for_run_ids(["bad/id", "anything"])

    def test_missing_run_raises_filenotfound(self):
        ep.save_comparison_result("present", [_entry()])
        with pytest.raises(FileNotFoundError):
            drift_mod.detect_drift_for_run_ids(["present", "missing"])

    def test_validates_all_ids_before_loading(self):
        """A malformed id late in the list should fail BEFORE we
        load any earlier runs (defense against partial work)."""
        ep.save_comparison_result("good", [_entry()])
        with pytest.raises(ValueError):
            drift_mod.detect_drift_for_run_ids(["good", "bad/id"])

    def test_chronological_order_drives_trajectory(self):
        """Unit 23 invariant: the wrapper reorders run_ids by
        ``metadata.created_at`` regardless of caller order. Both
        forward and reverse caller orders therefore yield the same
        trajectory direction (the true chronological one).

        Run ids are chosen so alphabetical tiebreak matches save
        order — important on Windows where datetime.now() resolution
        is coarse enough that back-to-back saves can share a
        timestamp."""
        ep.save_comparison_result("r1", [_entry("p::a", sp=5, ec=5)])
        ep.save_comparison_result("r2", [_entry("p::a", sp=6, ec=5)])
        ep.save_comparison_result("r3", [_entry("p::a", sp=7, ec=5)])

        forward = drift_mod.detect_drift_for_run_ids(["r1", "r2", "r3"])
        reverse = drift_mod.detect_drift_for_run_ids(["r3", "r2", "r1"])
        # Save order = timestamp order = alphabetical tiebreak, so both
        # must classify "trending_up" regardless of caller order.
        assert forward["trending_up"] == ["p::a"]
        assert reverse == forward

    def test_via_wrapper_with_three_pairs(self):
        ep.save_comparison_result("r1", [
            _entry("stable", sp=5, ec=5),
            _entry("up",     sp=5, ec=5),
            _entry("vol",    sp=5, ec=9),
        ])
        ep.save_comparison_result("r2", [
            _entry("stable", sp=5, ec=5),
            _entry("up",     sp=6, ec=6),
            _entry("vol",    sp=6, ec=7),
        ])
        ep.save_comparison_result("r3", [
            _entry("stable", sp=5, ec=5),
            _entry("up",     sp=7, ec=7),
            _entry("vol",    sp=7, ec=5),
        ])
        out = drift_mod.detect_drift_for_run_ids(["r1", "r2", "r3"])
        assert out["stable"]        == ["stable"]
        assert out["trending_up"]   == ["up"]
        assert out["volatile"]      == ["vol"]


# ===========================================================================
# G. POST /elins/regression/drift endpoint
# ===========================================================================
class TestDriftEndpoint:
    def _store_3_classifying_runs(self):
        """Helper: stores three runs that produce one pair in each of
        the four buckets (except trending_down, which we add)."""
        ep.save_comparison_result("e1", [
            _entry("stable", sp=5, ec=5),
            _entry("up",     sp=5, ec=5),
            _entry("down",   sp=9, ec=9),
            _entry("vol",    sp=5, ec=9),
        ])
        ep.save_comparison_result("e2", [
            _entry("stable", sp=5, ec=5),
            _entry("up",     sp=6, ec=6),
            _entry("down",   sp=7, ec=7),
            _entry("vol",    sp=6, ec=7),
        ])
        ep.save_comparison_result("e3", [
            _entry("stable", sp=5, ec=5),
            _entry("up",     sp=7, ec=7),
            _entry("down",   sp=5, ec=5),
            _entry("vol",    sp=7, ec=5),
        ])

    def test_valid_payload_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry()])
        ep.save_comparison_result("b", [_entry()])
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["a", "b"]},
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_shape(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_3_classifying_runs()
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["e1", "e2", "e3"]},
            headers=_auth(sid),
        )
        body = resp.json()
        for key in ("stable", "trending_up", "trending_down",
                    "volatile", "summary"):
            assert key in body
        for sk in ("stable", "trending_up", "trending_down", "volatile"):
            assert sk in body["summary"]

    def test_three_run_classification_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_3_classifying_runs()
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["e1", "e2", "e3"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["stable"]        == ["stable"]
        assert body["trending_up"]   == ["up"]
        assert body["trending_down"] == ["down"]
        assert body["volatile"]      == ["vol"]
        assert body["summary"] == {
            "stable": 1, "trending_up": 1, "trending_down": 1, "volatile": 1,
        }

    def test_unauth_returns_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["a", "b"]},
        )
        assert resp.status_code == 401

    def test_missing_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift",
            json={}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_run_ids_not_list_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": "nope"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_zero_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": []}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_one_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("only", [_entry()])
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["only"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["good", "bad$id"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("present", [_entry()])
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["present", "ghost"]},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_3_classifying_runs()
        direct = drift_mod.detect_drift_for_run_ids(["e1", "e2", "e3"])
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["e1", "e2", "e3"]},
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry()])
        ep.save_comparison_result("b", [_entry()])
        r1 = client.post("/elins/regression/drift",
                         json={"run_ids": ["a", "b"]}, headers=_auth(sid))
        r2 = client.post("/elins/regression/drift",
                         json={"run_ids": ["a", "b"]}, headers=_auth(sid))
        assert r1.json() == r2.json()

    def test_two_run_minimum_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p::a", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p::a", sp=6, ec=5)])
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        body = resp.json()
        assert body["trending_up"] == ["p::a"]

    def test_error_message_includes_index_for_bad_run_id(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["good", "bad$id"]},
            headers=_auth(sid),
        )
        msg = str(resp.json())
        assert "run_ids[1]" in msg


# ===========================================================================
# H. Determinism + ordering
# ===========================================================================
class TestDeterminism:
    def test_repeated_calls_byte_equal(self):
        runs = [
            [_entry("a", sp=5, ec=5), _entry("b", sp=5, ec=5)],
            [_entry("a", sp=5, ec=5), _entry("b", sp=6, ec=5)],
        ]
        r1 = drift_mod.detect_drift(runs)
        r2 = drift_mod.detect_drift(runs)
        assert r1 == r2

    def test_lists_alphabetical_within_each_bucket(self):
        runs = [
            [_entry("zeta",  sp=5, ec=5),
             _entry("alpha", sp=5, ec=5),
             _entry("mid",   sp=5, ec=5)],
            [_entry("zeta",  sp=5, ec=5),
             _entry("alpha", sp=5, ec=5),
             _entry("mid",   sp=5, ec=5)],
        ]
        r = drift_mod.detect_drift(runs)
        assert r["stable"] == ["alpha", "mid", "zeta"]

    def test_input_runs_not_mutated(self):
        runs = [
            [_entry("p::a", sp=5, ec=5)],
            [_entry("p::a", sp=6, ec=5)],
        ]
        before = repr(runs)
        drift_mod.detect_drift(runs)
        assert repr(runs) == before


# ===========================================================================
# I. Source-code purity / module surface
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(drift_mod)

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

    def test_detect_drift_pure_no_open(self):
        """detect_drift has no file I/O — only detect_drift_for_run_ids
        does (via the persistence layer)."""
        src = inspect.getsource(drift_mod.detect_drift)
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
    def test_detect_drift_callable(self):
        assert callable(drift_mod.detect_drift)

    def test_detect_drift_for_run_ids_callable(self):
        assert callable(drift_mod.detect_drift_for_run_ids)

    def test_classification_labels_locked(self):
        assert drift_mod._LABEL_STABLE == "stable"
        assert drift_mod._LABEL_UP == "trending_up"
        assert drift_mod._LABEL_DOWN == "trending_down"
        assert drift_mod._LABEL_VOLATILE == "volatile"

    def test_score_field_constants_locked(self):
        assert drift_mod._SP_FIELD == "single_party_score"
        assert drift_mod._EC_FIELD == "economic_coercion_score"


# ===========================================================================
# J. End-to-end: store via endpoint, drift via endpoint
# ===========================================================================
class TestEndToEnd:
    def test_full_pipeline_three_runs(self, client, app_module):
        sid = _make_user_session(app_module)

        # Build three single-pair payloads via the /store endpoint to
        # exercise the full pair_id chain (Unit 5/8 → 10 → 13).
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

        for rid in ("morning", "noon", "evening"):
            r = client.post("/elins/regression/store",
                            json={"run_id": rid, **store_body},
                            headers=_auth(sid))
            assert r.status_code == 200

        # Identical payloads → drift should be stable.
        d = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["morning", "noon", "evening"]},
            headers=_auth(sid),
        )
        assert d.status_code == 200
        body = d.json()
        assert body["stable"] == ["case01_sp::case01_ec"]
        assert body["trending_up"] == []
        assert body["trending_down"] == []
        assert body["volatile"] == []
