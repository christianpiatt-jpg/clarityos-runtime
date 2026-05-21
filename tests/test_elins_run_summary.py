"""
Tests for ELINS Unit 14 — single-run summary tables.

Layered coverage (≥ 60 tests, target ~70):
    A. Empty-run shape
    B. total_pairs counting
    C. Band counting per dimension (Strong/Acceptable/Weak/Fails)
    D. Score min/max/mean per dimension
    E. Mean rounding to 1 decimal
    F. Defensive handling (unknown bands, missing scores, legacy entries)
    G. Determinism + purity
    H. Wrapper (summary_table_for_run_id)
    I. Endpoint (GET /elins/regression/run/{run_id}/summary)
    J. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_run_summary as summary_mod


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
    sp_score: int = 7,
    ec_score: int = 7,
    sp_band: str = "Acceptable",
    ec_band: str = "Acceptable",
) -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp_score,
        "economic_coercion_score": ec_score,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _legacy_entry(**kwargs) -> dict:
    """Entry without pair_id — Unit 11 normalisation synthesises pos_<i>."""
    e = _entry(**kwargs)
    del e["pair_id"]
    return e


# ===========================================================================
# A. Empty-run shape
# ===========================================================================
class TestEmptyRun:
    def test_empty_run_returns_dict(self):
        out = summary_mod.summary_table([])
        assert isinstance(out, dict)

    def test_empty_run_total_pairs_zero(self):
        assert summary_mod.summary_table([])["total_pairs"] == 0

    def test_empty_run_all_band_counts_zero(self):
        out = summary_mod.summary_table([])
        for dim in ("single_party_bands", "economic_coercion_bands"):
            for band in ("Strong", "Acceptable", "Weak", "Fails"):
                assert out[dim][band] == 0

    def test_empty_run_score_stats_all_none(self):
        out = summary_mod.summary_table([])
        for dim in ("single_party_scores", "economic_coercion_scores"):
            assert out[dim] == {"min": None, "max": None, "mean": None}

    def test_empty_run_top_level_keys(self):
        out = summary_mod.summary_table([])
        assert set(out.keys()) == {
            "total_pairs",
            "single_party_bands", "economic_coercion_bands",
            "single_party_scores", "economic_coercion_scores",
        }


# ===========================================================================
# B. total_pairs counting
# ===========================================================================
class TestTotalPairs:
    def test_one_pair(self):
        assert summary_mod.summary_table([_entry("p1")])["total_pairs"] == 1

    def test_three_pairs(self):
        run = [_entry(f"p{i}") for i in range(3)]
        assert summary_mod.summary_table(run)["total_pairs"] == 3

    def test_ten_pairs(self):
        run = [_entry(f"p{i}") for i in range(10)]
        assert summary_mod.summary_table(run)["total_pairs"] == 10


# ===========================================================================
# C. Band counting per dimension
# ===========================================================================
class TestBandCounting:
    def test_all_strong_sp(self):
        run = [_entry(f"p{i}", sp_band="Strong") for i in range(5)]
        out = summary_mod.summary_table(run)
        assert out["single_party_bands"] == {
            "Strong": 5, "Acceptable": 0, "Weak": 0, "Fails": 0,
        }

    def test_all_acceptable_ec(self):
        run = [_entry(f"p{i}", ec_band="Acceptable") for i in range(4)]
        out = summary_mod.summary_table(run)
        assert out["economic_coercion_bands"]["Acceptable"] == 4

    def test_all_weak_sp(self):
        run = [_entry(f"p{i}", sp_band="Weak") for i in range(3)]
        assert summary_mod.summary_table(run)["single_party_bands"]["Weak"] == 3

    def test_fails_core_logic_maps_to_fails_key(self):
        """The full label 'Fails core logic' counts under the short
        'Fails' output key (work-set spec)."""
        run = [_entry("p1", sp_band="Fails core logic", ec_band="Fails core logic")]
        out = summary_mod.summary_table(run)
        assert out["single_party_bands"]["Fails"] == 1
        assert out["economic_coercion_bands"]["Fails"] == 1

    def test_mixed_bands_sp(self):
        run = [
            _entry("p1", sp_band="Strong"),
            _entry("p2", sp_band="Strong"),
            _entry("p3", sp_band="Acceptable"),
            _entry("p4", sp_band="Weak"),
            _entry("p5", sp_band="Fails core logic"),
        ]
        out = summary_mod.summary_table(run)
        assert out["single_party_bands"] == {
            "Strong": 2, "Acceptable": 1, "Weak": 1, "Fails": 1,
        }

    def test_mixed_bands_ec(self):
        run = [
            _entry("p1", ec_band="Strong"),
            _entry("p2", ec_band="Acceptable"),
            _entry("p3", ec_band="Acceptable"),
            _entry("p4", ec_band="Weak"),
            _entry("p5", ec_band="Fails core logic"),
            _entry("p6", ec_band="Fails core logic"),
        ]
        out = summary_mod.summary_table(run)
        assert out["economic_coercion_bands"] == {
            "Strong": 1, "Acceptable": 2, "Weak": 1, "Fails": 2,
        }

    def test_sp_and_ec_bands_independent(self):
        """SP and EC bands count independently — same pair can be in
        different bands across dimensions."""
        run = [_entry("p1", sp_band="Strong", ec_band="Fails core logic")]
        out = summary_mod.summary_table(run)
        assert out["single_party_bands"]["Strong"] == 1
        assert out["economic_coercion_bands"]["Fails"] == 1
        assert out["single_party_bands"]["Fails"] == 0
        assert out["economic_coercion_bands"]["Strong"] == 0

    def test_band_counts_sum_to_total_pairs_canonical(self):
        """When every pair has a canonical band, per-dimension band
        counts sum to total_pairs."""
        run = [
            _entry("p1", sp_band="Strong"),
            _entry("p2", sp_band="Acceptable"),
            _entry("p3", sp_band="Weak"),
            _entry("p4", sp_band="Fails core logic"),
        ]
        out = summary_mod.summary_table(run)
        assert sum(out["single_party_bands"].values()) == out["total_pairs"]

    def test_unknown_band_silently_skipped(self):
        """Bands outside the canonical 4-key set are dropped from
        per-band counts but still counted in total_pairs."""
        run = [
            _entry("p1", sp_band="Strong"),
            _entry("p2", sp_band="MysteryBand"),  # unknown
        ]
        out = summary_mod.summary_table(run)
        assert out["total_pairs"] == 2
        assert out["single_party_bands"]["Strong"] == 1
        # Unknown band → not counted anywhere.
        assert sum(out["single_party_bands"].values()) == 1

    def test_non_string_band_silently_skipped(self):
        """A non-string band value is defensively skipped."""
        run = [_entry("p1", sp_band=42)]  # type: ignore[arg-type]
        out = summary_mod.summary_table(run)
        assert sum(out["single_party_bands"].values()) == 0


# ===========================================================================
# D. Score min/max/mean per dimension
# ===========================================================================
class TestScoreStats:
    def test_single_pair_min_max_equal(self):
        run = [_entry("p1", sp_score=7, ec_score=5)]
        out = summary_mod.summary_table(run)
        assert out["single_party_scores"]["min"] == 7
        assert out["single_party_scores"]["max"] == 7
        assert out["economic_coercion_scores"]["min"] == 5
        assert out["economic_coercion_scores"]["max"] == 5

    def test_score_min(self):
        run = [
            _entry("p1", sp_score=8),
            _entry("p2", sp_score=3),
            _entry("p3", sp_score=10),
        ]
        out = summary_mod.summary_table(run)
        assert out["single_party_scores"]["min"] == 3

    def test_score_max(self):
        run = [
            _entry("p1", sp_score=5),
            _entry("p2", sp_score=2),
            _entry("p3", sp_score=9),
        ]
        out = summary_mod.summary_table(run)
        assert out["single_party_scores"]["max"] == 9

    def test_score_mean_simple(self):
        run = [
            _entry("p1", sp_score=4),
            _entry("p2", sp_score=6),
        ]
        # mean = 5
        assert summary_mod.summary_table(run)["single_party_scores"]["mean"] == 5.0

    def test_score_mean_with_negative(self):
        """Min/max work over negative ints too (defensive)."""
        run = [
            _entry("p1", sp_score=-3),
            _entry("p2", sp_score=5),
        ]
        out = summary_mod.summary_table(run)
        assert out["single_party_scores"]["min"] == -3
        assert out["single_party_scores"]["max"] == 5

    def test_sp_and_ec_score_independent(self):
        run = [
            _entry("p1", sp_score=10, ec_score=0),
            _entry("p2", sp_score=0,  ec_score=10),
        ]
        out = summary_mod.summary_table(run)
        assert out["single_party_scores"]["min"] == 0
        assert out["single_party_scores"]["max"] == 10
        assert out["economic_coercion_scores"]["min"] == 0
        assert out["economic_coercion_scores"]["max"] == 10

    def test_missing_score_field_skipped_from_stats(self):
        """An entry missing the score field doesn't crash mean — it's
        skipped defensively."""
        run = [
            {"pair_id": "p1", "single_party_band": "Strong",
             "economic_coercion_band": "Strong",
             "single_party_score": 5, "economic_coercion_score": 5},
            {"pair_id": "p2", "single_party_band": "Strong",
             "economic_coercion_band": "Strong"},  # missing scores
        ]
        out = summary_mod.summary_table(run)
        # Stats reflect only the 1 entry with scores.
        assert out["single_party_scores"]["min"] == 5
        assert out["single_party_scores"]["max"] == 5

    def test_all_scores_missing_returns_none(self):
        run = [
            {"pair_id": "p1", "single_party_band": "Strong",
             "economic_coercion_band": "Strong"},
        ]
        out = summary_mod.summary_table(run)
        assert out["single_party_scores"] == {"min": None, "max": None, "mean": None}

    def test_bool_score_skipped(self):
        """bool is subclass of int; defensively skipped from numeric stats."""
        run = [
            _entry("p1", sp_score=True),  # type: ignore[arg-type]
            _entry("p2", sp_score=5),
        ]
        out = summary_mod.summary_table(run)
        assert out["single_party_scores"]["min"] == 5
        assert out["single_party_scores"]["max"] == 5


class TestMeanRounding:
    def test_mean_rounded_to_one_decimal(self):
        # Scores 5, 7, 8 → mean 6.6666... → rounded to 6.7
        run = [
            _entry("p1", sp_score=5),
            _entry("p2", sp_score=7),
            _entry("p3", sp_score=8),
        ]
        assert summary_mod.summary_table(run)["single_party_scores"]["mean"] == 6.7

    def test_mean_exactly_half(self):
        # Scores 7, 8 → mean = 7.5 (exact)
        run = [
            _entry("p1", sp_score=7),
            _entry("p2", sp_score=8),
        ]
        assert summary_mod.summary_table(run)["single_party_scores"]["mean"] == 7.5

    def test_mean_integer_value_returned_as_float(self):
        # Scores 5, 5 → mean = 5.0
        run = [_entry("p1", sp_score=5), _entry("p2", sp_score=5)]
        assert summary_mod.summary_table(run)["single_party_scores"]["mean"] == 5.0

    def test_mean_three_thirds(self):
        # 1 + 2 + 3 = 6 / 3 = 2.0
        run = [_entry(f"p{i}", sp_score=v) for i, v in enumerate((1, 2, 3))]
        assert summary_mod.summary_table(run)["single_party_scores"]["mean"] == 2.0

    def test_mean_rounding_to_one_decimal_locked_constant(self):
        """The rounding precision is locked at 1 decimal place."""
        assert summary_mod._MEAN_ROUND_DIGITS == 1


# ===========================================================================
# F. Defensive / legacy handling
# ===========================================================================
class TestDefensiveHandling:
    def test_legacy_entries_summarised(self):
        """Entries without pair_id (legacy shape from pre-Unit-11
        stored runs) still summarise correctly."""
        run = [_legacy_entry(sp_score=5), _legacy_entry(sp_score=7)]
        out = summary_mod.summary_table(run)
        assert out["total_pairs"] == 2
        assert out["single_party_scores"]["min"] == 5
        assert out["single_party_scores"]["max"] == 7

    def test_mixed_legacy_and_canonical_entries(self):
        run = [
            _entry("p1", sp_band="Strong"),
            _legacy_entry(sp_band="Weak"),
        ]
        out = summary_mod.summary_table(run)
        assert out["total_pairs"] == 2
        assert out["single_party_bands"]["Strong"] == 1
        assert out["single_party_bands"]["Weak"] == 1


class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError):
            summary_mod.summary_table("nope")  # type: ignore[arg-type]

    def test_entry_not_dict_raises(self):
        # Propagated from Unit 11 normalisation.
        with pytest.raises(ValueError):
            summary_mod.summary_table(["bad"])  # type: ignore[list-item]

    def test_none_input_raises(self):
        with pytest.raises(ValueError):
            summary_mod.summary_table(None)  # type: ignore[arg-type]


# ===========================================================================
# G. Determinism + purity
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeated_calls(self):
        run = [
            _entry("p1", sp_score=9, ec_score=7),
            _entry("p2", sp_score=5, ec_score=3),
        ]
        a = summary_mod.summary_table(run)
        b = summary_mod.summary_table(run)
        assert a == b

    def test_input_run_not_mutated(self):
        run = [_entry("p1"), _entry("p2")]
        before = repr(run)
        summary_mod.summary_table(run)
        assert repr(run) == before

    def test_different_orders_same_result(self):
        """List order doesn't affect summary (band counts are
        commutative; min/max/mean too)."""
        a = summary_mod.summary_table([
            _entry("p1", sp_score=5),
            _entry("p2", sp_score=7),
            _entry("p3", sp_score=3),
        ])
        b = summary_mod.summary_table([
            _entry("p3", sp_score=3),
            _entry("p1", sp_score=5),
            _entry("p2", sp_score=7),
        ])
        assert a == b


# ===========================================================================
# H. Wrapper — summary_table_for_run_id
# ===========================================================================
class TestWrapper:
    def test_loads_and_summarises_byte_equal_to_direct(self):
        payload = [
            _entry("p1", sp_score=9, sp_band="Strong"),
            _entry("p2", sp_score=5, sp_band="Weak"),
        ]
        ep.save_comparison_result("wrap_test", payload)
        out = summary_mod.summary_table_for_run_id("wrap_test")
        direct = summary_mod.summary_table(payload)
        assert out == direct

    def test_missing_run_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            summary_mod.summary_table_for_run_id("never_stored")

    def test_malformed_run_id_raises_value_error(self):
        with pytest.raises(ValueError):
            summary_mod.summary_table_for_run_id("bad/id")

    def test_empty_run_id_raises_value_error(self):
        with pytest.raises(ValueError):
            summary_mod.summary_table_for_run_id("")

    def test_non_string_run_id_raises_value_error(self):
        with pytest.raises(ValueError):
            summary_mod.summary_table_for_run_id(42)  # type: ignore[arg-type]

    def test_empty_run_via_wrapper(self):
        ep.save_comparison_result("empty_wrap", [])
        out = summary_mod.summary_table_for_run_id("empty_wrap")
        assert out["total_pairs"] == 0

    def test_wrapper_uses_unit_11_normalisation(self):
        """Legacy-shape entries (no pair_id) still summarise correctly
        via the wrapper (Unit 11 _normalise_run is the bridge)."""
        payload = [_legacy_entry(sp_score=5), _legacy_entry(sp_score=7)]
        ep.save_comparison_result("legacy_wrap", payload)
        out = summary_mod.summary_table_for_run_id("legacy_wrap")
        assert out["total_pairs"] == 2

    def test_wrapper_three_pair_run(self):
        payload = [
            _entry("p1", sp_score=9, sp_band="Strong"),
            _entry("p2", sp_score=8, sp_band="Acceptable"),
            _entry("p3", sp_score=7, sp_band="Acceptable"),
        ]
        ep.save_comparison_result("three", payload)
        out = summary_mod.summary_table_for_run_id("three")
        assert out["total_pairs"] == 3
        assert out["single_party_bands"]["Acceptable"] == 2
        assert out["single_party_bands"]["Strong"] == 1


# ===========================================================================
# I. Endpoint
# ===========================================================================
class TestEndpoint:
    def test_valid_run_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("api_run", [_entry("p1")])
        resp = client.get(
            "/elins/regression/run/api_run/summary",
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_has_required_top_level_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("shape_run", [_entry("p1")])
        resp = client.get(
            "/elins/regression/run/shape_run/summary",
            headers=_auth(sid),
        )
        body = resp.json()
        assert set(body.keys()) == {
            "total_pairs",
            "single_party_bands", "economic_coercion_bands",
            "single_party_scores", "economic_coercion_scores",
        }

    def test_band_dict_has_four_canonical_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("band_keys", [_entry("p1")])
        resp = client.get(
            "/elins/regression/run/band_keys/summary",
            headers=_auth(sid),
        )
        body = resp.json()
        for dim in ("single_party_bands", "economic_coercion_bands"):
            assert set(body[dim].keys()) == {"Strong", "Acceptable", "Weak", "Fails"}

    def test_score_dict_has_min_max_mean(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("score_keys", [_entry("p1")])
        resp = client.get(
            "/elins/regression/run/score_keys/summary",
            headers=_auth(sid),
        )
        body = resp.json()
        for dim in ("single_party_scores", "economic_coercion_scores"):
            assert set(body[dim].keys()) == {"min", "max", "mean"}

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            "/elins/regression/run/never_stored/summary",
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_malformed_run_id_returns_400_or_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            "/elins/regression/run/bad$id/summary",
            headers=_auth(sid),
        )
        # Either 400 (our validator) or 404 (FastAPI path constraint).
        assert resp.status_code in (400, 404)

    def test_unauth_returns_401(self, client, app_module):
        ep.save_comparison_result("anon", [_entry("p1")])
        resp = client.get("/elins/regression/run/anon/summary")
        assert resp.status_code == 401

    def test_response_matches_direct_wrapper_call(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = [
            _entry("p1", sp_score=9, sp_band="Strong"),
            _entry("p2", sp_score=5, sp_band="Weak"),
            _entry("p3", sp_score=3, sp_band="Fails core logic"),
        ]
        ep.save_comparison_result("match_test", payload)
        direct = summary_mod.summary_table_for_run_id("match_test")
        resp = client.get(
            "/elins/regression/run/match_test/summary",
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_empty_run_summary_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("empty", [])
        resp = client.get(
            "/elins/regression/run/empty/summary",
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["total_pairs"] == 0
        assert body["single_party_scores"]["mean"] is None

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("rep", [_entry("p1"), _entry("p2")])
        r1 = client.get("/elins/regression/run/rep/summary", headers=_auth(sid))
        r2 = client.get("/elins/regression/run/rep/summary", headers=_auth(sid))
        assert r1.json() == r2.json()

    def test_does_not_collide_with_get_run_endpoint(self, client, app_module):
        """The Unit 10 GET /elins/regression/run/{id} should still work
        alongside the new GET /elins/regression/run/{id}/summary."""
        sid = _make_user_session(app_module)
        ep.save_comparison_result("coexist", [_entry("p1", sp_score=9)])

        get_run = client.get(
            "/elins/regression/run/coexist", headers=_auth(sid),
        )
        assert get_run.status_code == 200
        # The original payload, not the summary.
        assert isinstance(get_run.json(), list)

        get_summary = client.get(
            "/elins/regression/run/coexist/summary", headers=_auth(sid),
        )
        assert get_summary.status_code == 200
        # Summary dict, not the payload.
        body = get_summary.json()
        assert "total_pairs" in body
        assert body["total_pairs"] == 1

    def test_full_band_counts_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = [
            _entry("p1", sp_band="Strong",           ec_band="Acceptable"),
            _entry("p2", sp_band="Strong",           ec_band="Weak"),
            _entry("p3", sp_band="Acceptable",       ec_band="Fails core logic"),
            _entry("p4", sp_band="Weak",             ec_band="Strong"),
            _entry("p5", sp_band="Fails core logic", ec_band="Strong"),
        ]
        ep.save_comparison_result("full_bands", payload)
        body = client.get(
            "/elins/regression/run/full_bands/summary", headers=_auth(sid),
        ).json()
        assert body["single_party_bands"] == {
            "Strong": 2, "Acceptable": 1, "Weak": 1, "Fails": 1,
        }
        assert body["economic_coercion_bands"] == {
            "Strong": 2, "Acceptable": 1, "Weak": 1, "Fails": 1,
        }

    def test_total_pairs_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = [_entry(f"p{i}") for i in range(7)]
        ep.save_comparison_result("seven", payload)
        body = client.get(
            "/elins/regression/run/seven/summary", headers=_auth(sid),
        ).json()
        assert body["total_pairs"] == 7

    def test_score_stats_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = [
            _entry("p1", sp_score=4, ec_score=8),
            _entry("p2", sp_score=8, ec_score=4),
        ]
        ep.save_comparison_result("scored", payload)
        body = client.get(
            "/elins/regression/run/scored/summary", headers=_auth(sid),
        ).json()
        assert body["single_party_scores"] == {"min": 4, "max": 8, "mean": 6.0}
        assert body["economic_coercion_scores"] == {"min": 4, "max": 8, "mean": 6.0}


# ===========================================================================
# J. Source-code purity / module surface
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(summary_mod)

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

    def test_summary_table_pure_no_open(self):
        """summary_table has no file I/O — only summary_table_for_run_id
        does (via the persistence layer)."""
        src = inspect.getsource(summary_mod.summary_table)
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
    def test_summary_table_callable(self):
        assert callable(summary_mod.summary_table)

    def test_summary_table_for_run_id_callable(self):
        assert callable(summary_mod.summary_table_for_run_id)

    def test_band_key_map_locked(self):
        assert summary_mod._BAND_KEY_MAP == {
            "Strong":           "Strong",
            "Acceptable":       "Acceptable",
            "Weak":             "Weak",
            "Fails core logic": "Fails",
        }

    def test_band_output_keys_locked(self):
        assert summary_mod._BAND_OUTPUT_KEYS == (
            "Strong", "Acceptable", "Weak", "Fails",
        )

    def test_score_field_constants_locked(self):
        assert summary_mod._SP_SCORE_FIELD == "single_party_score"
        assert summary_mod._EC_SCORE_FIELD == "economic_coercion_score"

    def test_band_field_constants_locked(self):
        assert summary_mod._SP_BAND_FIELD == "single_party_band"
        assert summary_mod._EC_BAND_FIELD == "economic_coercion_band"


# ===========================================================================
# K. End-to-end: store via endpoint, fetch summary via endpoint
# ===========================================================================
class TestEndToEnd:
    def test_full_pipeline_store_then_summary(self, client, app_module):
        sid = _make_user_session(app_module)

        # Build a two-pair payload via /store.
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
        store_resp = client.post(
            "/elins/regression/store",
            json={"run_id": "e2e",
                  "pairs": [{"single_party_timeline": sp_payload,
                             "economic_timeline":     ec_payload}]},
            headers=_auth(sid),
        )
        assert store_resp.status_code == 200

        # Fetch the summary.
        sum_resp = client.get(
            "/elins/regression/run/e2e/summary",
            headers=_auth(sid),
        )
        assert sum_resp.status_code == 200
        body = sum_resp.json()
        assert body["total_pairs"] == 1
        # Score stats are present and populated.
        assert body["single_party_scores"]["min"] is not None
        assert body["single_party_scores"]["mean"] is not None
