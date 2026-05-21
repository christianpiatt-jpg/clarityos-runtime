"""
Tests for ELINS Unit 18 — cross-run aggregate summary.

Layered coverage (≥ 60 tests, target 70+):
    A. Core delegation logic — summary_across_runs (delegates to Unit 14)
    B. Validation — input shapes, pair structure, types
    C. Wrapper — summary_across_run_ids (load + delegate)
    D. Endpoint — POST /elins/regression/runs/summary
    E. Determinism + ordering
    F. Source-code purity / module surface
    G. End-to-end via persistence
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
import elins_run_summary_multi as multi_mod


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


def _legacy_entry(*, sp: int = 5, ec: int = 5,
                  sp_band: str = "Acceptable",
                  ec_band: str = "Acceptable") -> dict:
    e = _entry(sp=sp, ec=ec, sp_band=sp_band, ec_band=ec_band)
    del e["pair_id"]
    return e


# ===========================================================================
# A. Core delegation logic — summary_across_runs
# ===========================================================================
class TestCoreSingleRun:
    def test_single_run_top_level_shape(self):
        out = multi_mod.summary_across_runs([("only", [_entry("p1")])])
        assert set(out.keys()) == {"runs"}

    def test_single_run_inner_keyed_by_run_id(self):
        out = multi_mod.summary_across_runs([("only", [_entry("p1")])])
        assert list(out["runs"].keys()) == ["only"]

    def test_single_run_total_pairs(self):
        out = multi_mod.summary_across_runs(
            [("r", [_entry("a"), _entry("b"), _entry("c")])]
        )
        assert out["runs"]["r"]["total_pairs"] == 3

    def test_single_run_band_keys(self):
        out = multi_mod.summary_across_runs([("r", [_entry("p1")])])
        sp_bands = out["runs"]["r"]["single_party_bands"]
        assert set(sp_bands.keys()) == {"Strong", "Acceptable", "Weak", "Fails"}

    def test_single_run_score_stat_keys(self):
        out = multi_mod.summary_across_runs([("r", [_entry("p1")])])
        sp_scores = out["runs"]["r"]["single_party_scores"]
        assert set(sp_scores.keys()) == {"min", "max", "mean"}

    def test_single_run_value_correctness(self):
        run = [
            _entry("a", sp=2, ec=4, sp_band="Strong",     ec_band="Acceptable"),
            _entry("b", sp=8, ec=6, sp_band="Acceptable", ec_band="Strong"),
        ]
        out = multi_mod.summary_across_runs([("r", run)])
        r = out["runs"]["r"]
        assert r["total_pairs"] == 2
        assert r["single_party_scores"] == {"min": 2, "max": 8, "mean": 5.0}
        assert r["economic_coercion_scores"] == {"min": 4, "max": 6, "mean": 5.0}
        assert r["single_party_bands"]["Strong"] == 1
        assert r["single_party_bands"]["Acceptable"] == 1


class TestCoreMultiRun:
    def test_two_runs_both_present(self):
        out = multi_mod.summary_across_runs([
            ("a", [_entry("p1", sp=5)]),
            ("b", [_entry("p1", sp=8)]),
        ])
        assert set(out["runs"].keys()) == {"a", "b"}

    def test_three_runs_all_present(self):
        out = multi_mod.summary_across_runs([
            ("a", [_entry("p1")]),
            ("b", [_entry("p2")]),
            ("c", [_entry("p3")]),
        ])
        assert set(out["runs"].keys()) == {"a", "b", "c"}

    def test_two_runs_total_pairs_independent(self):
        out = multi_mod.summary_across_runs([
            ("small", [_entry("p1")]),
            ("big",   [_entry(f"p{i}") for i in range(7)]),
        ])
        assert out["runs"]["small"]["total_pairs"] == 1
        assert out["runs"]["big"]["total_pairs"] == 7

    def test_runs_have_independent_band_counts(self):
        out = multi_mod.summary_across_runs([
            ("strong_run",
             [_entry("p1", sp_band="Strong"), _entry("p2", sp_band="Strong")]),
            ("weak_run",
             [_entry("p1", sp_band="Weak")]),
        ])
        assert out["runs"]["strong_run"]["single_party_bands"]["Strong"] == 2
        assert out["runs"]["strong_run"]["single_party_bands"]["Weak"] == 0
        assert out["runs"]["weak_run"]["single_party_bands"]["Weak"] == 1
        assert out["runs"]["weak_run"]["single_party_bands"]["Strong"] == 0

    def test_runs_have_independent_score_stats(self):
        out = multi_mod.summary_across_runs([
            ("low",  [_entry("p1", sp=1), _entry("p2", sp=2)]),
            ("high", [_entry("p1", sp=8), _entry("p2", sp=9)]),
        ])
        assert out["runs"]["low"]["single_party_scores"]["max"] == 2
        assert out["runs"]["high"]["single_party_scores"]["min"] == 8

    def test_five_runs(self):
        runs = [
            (f"r{i}", [_entry("p1", sp=i)]) for i in range(5)
        ]
        out = multi_mod.summary_across_runs(runs)
        assert len(out["runs"]) == 5
        for i in range(5):
            assert out["runs"][f"r{i}"]["single_party_scores"]["min"] == i


class TestCoreDelegation:
    """Output for each run must equal Unit 14's summary_table on the
    same payload, byte-for-byte."""

    def test_single_run_matches_summary_table(self):
        run = [_entry("p1", sp=5, ec=8)]
        direct = summary_mod.summary_table(run)
        out = multi_mod.summary_across_runs([("r", run)])
        assert out["runs"]["r"] == direct

    def test_each_run_matches_summary_table_independently(self):
        run_a = [_entry("p1", sp=2, ec=2), _entry("p2", sp=4, ec=4)]
        run_b = [_entry("p1", sp=9, ec=9)]
        out = multi_mod.summary_across_runs([("a", run_a), ("b", run_b)])
        assert out["runs"]["a"] == summary_mod.summary_table(run_a)
        assert out["runs"]["b"] == summary_mod.summary_table(run_b)

    def test_empty_run_payload_matches_summary_table(self):
        out = multi_mod.summary_across_runs([("empty", [])])
        assert out["runs"]["empty"] == summary_mod.summary_table([])

    def test_legacy_entries_match_summary_table(self):
        run = [_legacy_entry(sp=3, ec=7), _legacy_entry(sp=4, ec=6)]
        out = multi_mod.summary_across_runs([("legacy", run)])
        assert out["runs"]["legacy"] == summary_mod.summary_table(run)

    def test_mixed_band_payload_matches_summary_table(self):
        run = [
            _entry("a", sp_band="Strong", ec_band="Strong"),
            _entry("b", sp_band="Acceptable", ec_band="Weak"),
            _entry("c", sp_band="Fails core logic", ec_band="Fails core logic"),
        ]
        out = multi_mod.summary_across_runs([("mixed", run)])
        assert out["runs"]["mixed"] == summary_mod.summary_table(run)


class TestCoreEmptyAndShape:
    def test_empty_runs_input_returns_empty_dict(self):
        assert multi_mod.summary_across_runs([]) == {"runs": {}}

    def test_empty_runs_input_top_level_key_present(self):
        out = multi_mod.summary_across_runs([])
        assert "runs" in out

    def test_accepts_list_pairs(self):
        """Pairs may arrive as either tuples or lists (JSON-friendly)."""
        out = multi_mod.summary_across_runs([["r", [_entry("p1")]]])
        assert "r" in out["runs"]

    def test_accepts_tuple_pairs(self):
        out = multi_mod.summary_across_runs([("r", [_entry("p1")])])
        assert "r" in out["runs"]

    def test_run_with_empty_payload_yields_empty_counts(self):
        out = multi_mod.summary_across_runs([("e", [])])
        sp_bands = out["runs"]["e"]["single_party_bands"]
        assert all(v == 0 for v in sp_bands.values())
        assert out["runs"]["e"]["total_pairs"] == 0
        assert out["runs"]["e"]["single_party_scores"] == {
            "min": None, "max": None, "mean": None,
        }


# ===========================================================================
# B. Validation
# ===========================================================================
class TestValidationCore:
    def test_non_list_runs_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            multi_mod.summary_across_runs("nope")  # type: ignore[arg-type]

    def test_dict_runs_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            multi_mod.summary_across_runs({"r": []})  # type: ignore[arg-type]

    def test_none_runs_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            multi_mod.summary_across_runs(None)  # type: ignore[arg-type]

    def test_pair_not_tuple_or_list_raises(self):
        with pytest.raises(ValueError, match="must be a "):
            multi_mod.summary_across_runs(["bad"])  # type: ignore[list-item]

    def test_pair_with_one_element_raises(self):
        with pytest.raises(ValueError, match="must be a "):
            multi_mod.summary_across_runs([("only_id",)])  # type: ignore[list-item]

    def test_pair_with_three_elements_raises(self):
        with pytest.raises(ValueError, match="must be a "):
            multi_mod.summary_across_runs(
                [("a", [_entry("p1")], "extra")]  # type: ignore[list-item]
            )

    def test_pair_with_non_string_run_id_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            multi_mod.summary_across_runs([(123, [_entry("p1")])])  # type: ignore[list-item]

    def test_pair_with_empty_string_run_id_raises(self):
        with pytest.raises(ValueError, match="non-empty string"):
            multi_mod.summary_across_runs([("", [_entry("p1")])])

    def test_pair_with_non_list_payload_raises(self):
        with pytest.raises(ValueError, match="must be a list"):
            multi_mod.summary_across_runs(
                [("r", "not_a_list")]  # type: ignore[list-item]
            )

    def test_validation_failure_first_error_index_in_message(self):
        with pytest.raises(ValueError, match=r"runs\[1\]"):
            multi_mod.summary_across_runs([
                ("good", [_entry("p1")]),
                "bad",  # type: ignore[list-item]
            ])

    def test_validation_failure_no_partial_output(self):
        """If validation fails, no exception leaves a partial summary
        on the function side. Defensive."""
        with pytest.raises(ValueError):
            multi_mod.summary_across_runs([
                ("good", [_entry("p1")]),
                ("bad_payload", "nope"),  # type: ignore[list-item]
            ])

    def test_inner_summary_table_error_propagates(self):
        """If a payload entry isn't a dict, summary_table raises during
        normalisation — that error must propagate, not be swallowed."""
        with pytest.raises(ValueError):
            multi_mod.summary_across_runs([("r", ["not_a_dict"])])


# ===========================================================================
# C. Wrapper — summary_across_run_ids
# ===========================================================================
class TestWrapper:
    def test_loads_one_run_byte_equal_to_direct(self):
        ep.save_comparison_result("solo", [_entry("p1", sp=5, ec=8)])
        wrapped = multi_mod.summary_across_run_ids(["solo"])
        direct  = multi_mod.summary_across_runs(
            [("solo", [_entry("p1", sp=5, ec=8)])]
        )
        assert wrapped == direct

    def test_loads_two_runs_byte_equal_to_direct(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        wrapped = multi_mod.summary_across_run_ids(["a", "b"])
        direct  = multi_mod.summary_across_runs([
            ("a", [_entry("p1", sp=5)]),
            ("b", [_entry("p1", sp=8)]),
        ])
        assert wrapped == direct

    def test_loads_three_runs(self):
        for i, sp in enumerate((1, 5, 9)):
            ep.save_comparison_result(f"r_{i}", [_entry("p1", sp=sp)])
        out = multi_mod.summary_across_run_ids(["r_0", "r_1", "r_2"])
        assert set(out["runs"].keys()) == {"r_0", "r_1", "r_2"}

    def test_single_run_id_allowed(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        out = multi_mod.summary_across_run_ids(["solo"])
        assert "solo" in out["runs"]

    def test_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            multi_mod.summary_across_run_ids("nope")  # type: ignore[arg-type]

    def test_none_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            multi_mod.summary_across_run_ids(None)  # type: ignore[arg-type]

    def test_dict_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            multi_mod.summary_across_run_ids({"a": 1})  # type: ignore[arg-type]

    def test_empty_run_ids_raises(self):
        with pytest.raises(ValueError, match=">= 1"):
            multi_mod.summary_across_run_ids([])

    def test_malformed_run_id_raises(self):
        with pytest.raises(ValueError):
            multi_mod.summary_across_run_ids(["bad/id"])

    def test_malformed_run_id_at_position_one_raises(self):
        ep.save_comparison_result("good", [_entry("p1")])
        with pytest.raises(ValueError):
            multi_mod.summary_across_run_ids(["good", "bad$id"])

    def test_missing_run_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            multi_mod.summary_across_run_ids(["ghost"])

    def test_partial_missing_raises_filenotfound(self):
        ep.save_comparison_result("present", [_entry("p1")])
        with pytest.raises(FileNotFoundError):
            multi_mod.summary_across_run_ids(["present", "ghost"])

    def test_validates_all_ids_before_loading(self):
        ep.save_comparison_result("good", [_entry("p1")])
        with pytest.raises(ValueError):
            multi_mod.summary_across_run_ids(["good", "bad/id"])

    def test_legacy_runs_via_wrapper(self):
        ep.save_comparison_result("leg", [_legacy_entry(sp=5, ec=8)])
        out = multi_mod.summary_across_run_ids(["leg"])
        assert out["runs"]["leg"]["total_pairs"] == 1
        assert out["runs"]["leg"]["single_party_scores"]["min"] == 5

    def test_empty_run_via_wrapper_yields_empty_counts(self):
        ep.save_comparison_result("e", [])
        out = multi_mod.summary_across_run_ids(["e"])
        assert out["runs"]["e"]["total_pairs"] == 0

    def test_deterministic_repeated_calls(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8)])
        first  = multi_mod.summary_across_run_ids(["a", "b"])
        second = multi_mod.summary_across_run_ids(["a", "b"])
        assert first == second

    def test_input_order_does_not_affect_alphabetical_output(self):
        ep.save_comparison_result("alpha", [_entry("p1", sp=5)])
        ep.save_comparison_result("zeta",  [_entry("p1", sp=9)])
        forward = multi_mod.summary_across_run_ids(["alpha", "zeta"])
        reverse = multi_mod.summary_across_run_ids(["zeta", "alpha"])
        assert list(forward["runs"].keys()) == ["alpha", "zeta"]
        assert list(reverse["runs"].keys()) == ["alpha", "zeta"]


# ===========================================================================
# D. Endpoint — POST /elins/regression/runs/summary
# ===========================================================================
class TestEndpoint:
    _PATH = "/elins/regression/runs/summary"

    def _store_three(self):
        for i, sp in enumerate((3, 5, 9)):
            ep.save_comparison_result(f"ep_{i}", [_entry("p1", sp=sp)])

    def test_single_run_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        resp = client.post(
            self._PATH,
            json={"run_ids": ["solo"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_multi_run_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three()
        resp = client.post(
            self._PATH,
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_has_runs_top_level_key(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        body = client.post(
            self._PATH,
            json={"run_ids": ["solo"]}, headers=_auth(sid),
        ).json()
        assert "runs" in body

    def test_response_keys_exactly_runs(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        body = client.post(
            self._PATH,
            json={"run_ids": ["solo"]}, headers=_auth(sid),
        ).json()
        assert set(body.keys()) == {"runs"}

    def test_response_runs_keyed_by_run_id(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three()
        body = client.post(
            self._PATH,
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        ).json()
        assert set(body["runs"].keys()) == {"ep_0", "ep_1", "ep_2"}

    def test_response_runs_alphabetical(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("zeta",  [_entry("p1", sp=9)])
        ep.save_comparison_result("alpha", [_entry("p1", sp=5)])
        body = client.post(
            self._PATH,
            json={"run_ids": ["zeta", "alpha"]},
            headers=_auth(sid),
        ).json()
        assert list(body["runs"].keys()) == ["alpha", "zeta"]

    def test_per_run_inner_shape(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        body = client.post(
            self._PATH,
            json={"run_ids": ["solo"]}, headers=_auth(sid),
        ).json()
        per = body["runs"]["solo"]
        assert set(per.keys()) == {
            "total_pairs",
            "single_party_bands",
            "economic_coercion_bands",
            "single_party_scores",
            "economic_coercion_scores",
        }

    def test_per_run_band_keys_locked(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        body = client.post(
            self._PATH,
            json={"run_ids": ["solo"]}, headers=_auth(sid),
        ).json()
        sp_bands = body["runs"]["solo"]["single_party_bands"]
        assert set(sp_bands.keys()) == {"Strong", "Acceptable", "Weak", "Fails"}

    def test_per_run_score_stat_keys_locked(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [_entry("p1")])
        body = client.post(
            self._PATH,
            json={"run_ids": ["solo"]}, headers=_auth(sid),
        ).json()
        sp_scores = body["runs"]["solo"]["single_party_scores"]
        assert set(sp_scores.keys()) == {"min", "max", "mean"}

    def test_unauth_returns_401(self, client, app_module):
        resp = client.post(self._PATH, json={"run_ids": ["a"]})
        assert resp.status_code == 401

    def test_missing_body_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(self._PATH, json={}, headers=_auth(sid))
        assert resp.status_code == 400

    def test_run_ids_not_list_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH,
            json={"run_ids": "nope"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_empty_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH,
            json={"run_ids": []}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_run_id_returns_400_with_index(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH,
            json={"run_ids": ["good", "bad$id"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400
        msg = str(resp.json())
        assert "run_ids[1]" in msg

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("present", [_entry("p1")])
        resp = client.post(
            self._PATH,
            json={"run_ids": ["present", "ghost"]},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three()
        direct = multi_mod.summary_across_run_ids(
            ["ep_0", "ep_1", "ep_2"])
        resp = client.post(
            self._PATH,
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three()
        r1 = client.post(
            self._PATH,
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        r2 = client.post(
            self._PATH,
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        assert r1.json() == r2.json()

    def test_value_correctness_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("solo", [
            _entry("a", sp=2, sp_band="Weak"),
            _entry("b", sp=8, sp_band="Strong"),
        ])
        body = client.post(
            self._PATH,
            json={"run_ids": ["solo"]}, headers=_auth(sid),
        ).json()
        per = body["runs"]["solo"]
        assert per["total_pairs"] == 2
        assert per["single_party_scores"]["min"] == 2
        assert per["single_party_scores"]["max"] == 8
        assert per["single_party_bands"]["Strong"] == 1
        assert per["single_party_bands"]["Weak"] == 1

    def test_empty_run_payload_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("e", [])
        body = client.post(
            self._PATH,
            json={"run_ids": ["e"]}, headers=_auth(sid),
        ).json()
        per = body["runs"]["e"]
        assert per["total_pairs"] == 0
        assert per["single_party_scores"] == {
            "min": None, "max": None, "mean": None,
        }

    def test_endpoint_handles_legacy_entries(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("leg", [
            _legacy_entry(sp=5, ec=5),
            _legacy_entry(sp=7, ec=5),
        ])
        body = client.post(
            self._PATH,
            json={"run_ids": ["leg"]}, headers=_auth(sid),
        ).json()
        assert body["runs"]["leg"]["total_pairs"] == 2

    def test_body_must_be_dict(self, client, app_module):
        sid = _make_user_session(app_module)
        # Sending a JSON list as body — FastAPI's `body: dict` annotation
        # rejects it before our handler runs (422), or our handler will
        # if FastAPI accepts. Either status is non-200; we just check
        # the request didn't succeed.
        resp = client.post(
            self._PATH,
            json=["a", "b"], headers=_auth(sid),
        )
        assert resp.status_code != 200

    def test_run_ids_with_numeric_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            self._PATH,
            json={"run_ids": [123]}, headers=_auth(sid),
        )
        assert resp.status_code == 400


# ===========================================================================
# E. Determinism + ordering
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeated_calls(self):
        runs = [
            ("a", [_entry("p1", sp=5)]),
            ("b", [_entry("p1", sp=8)]),
        ]
        assert multi_mod.summary_across_runs(runs) == \
            multi_mod.summary_across_runs(runs)

    def test_alphabetical_run_id_ordering(self):
        out = multi_mod.summary_across_runs([
            ("zeta",  [_entry("p1")]),
            ("alpha", [_entry("p1")]),
            ("mid",   [_entry("p1")]),
        ])
        assert list(out["runs"].keys()) == ["alpha", "mid", "zeta"]

    def test_input_runs_not_mutated(self):
        runs = [("r", [_entry("p1", sp=5)])]
        before = repr(runs)
        multi_mod.summary_across_runs(runs)
        assert repr(runs) == before

    def test_alphabetical_with_underscores_and_digits(self):
        out = multi_mod.summary_across_runs([
            ("run_3", [_entry("p1")]),
            ("run_1", [_entry("p1")]),
            ("run_2", [_entry("p1")]),
        ])
        assert list(out["runs"].keys()) == ["run_1", "run_2", "run_3"]


# ===========================================================================
# F. Source-code purity / module surface
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(multi_mod)

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

    def test_summary_across_runs_pure_no_open(self):
        """summary_across_runs has no file I/O — only the wrapper does."""
        src = inspect.getsource(multi_mod.summary_across_runs)
        assert "open(" not in src
        assert "load_comparison_result" not in src

    def test_no_basin_inference_imports(self):
        src = self._src()
        for pattern in (
            "import elins_dashboard", "from elins_dashboard",
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
        ):
            assert pattern not in src

    def test_delegates_to_summary_table(self):
        """Source must import & call Unit 14's summary_table."""
        src = self._src()
        assert "from elins_run_summary import summary_table" in src
        assert "summary_table(" in src


class TestModuleSurface:
    def test_summary_across_runs_callable(self):
        assert callable(multi_mod.summary_across_runs)

    def test_summary_across_run_ids_callable(self):
        assert callable(multi_mod.summary_across_run_ids)

    def test_module_docstring_present(self):
        assert isinstance(multi_mod.__doc__, str)
        assert len(multi_mod.__doc__) > 50


# ===========================================================================
# G. End-to-end via persistence
# ===========================================================================
class TestEndToEnd:
    def test_store_then_summary(self, client, app_module):
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

        s = client.post(
            "/elins/regression/runs/summary",
            json={"run_ids": ["morning", "evening"]},
            headers=_auth(sid),
        )
        assert s.status_code == 200
        body = s.json()
        assert set(body["runs"].keys()) == {"morning", "evening"}
        for rid in ("morning", "evening"):
            assert body["runs"][rid]["total_pairs"] == 1

    def test_store_then_summary_matches_unit14_per_run(
        self, client, app_module,
    ):
        """End-to-end: each run's summary in the multi response equals
        Unit 14's single-run summary endpoint output for that same run."""
        sid = _make_user_session(app_module)

        sp_payload = {
            "timeline_id": "case02_sp",
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
            "timeline_id": "case02_ec",
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

        client.post("/elins/regression/store",
                    json={"run_id": "u14_a", **store_body},
                    headers=_auth(sid))
        client.post("/elins/regression/store",
                    json={"run_id": "u14_b", **store_body},
                    headers=_auth(sid))

        single_a = client.get(
            "/elins/regression/run/u14_a/summary", headers=_auth(sid),
        ).json()
        single_b = client.get(
            "/elins/regression/run/u14_b/summary", headers=_auth(sid),
        ).json()
        multi = client.post(
            "/elins/regression/runs/summary",
            json={"run_ids": ["u14_a", "u14_b"]},
            headers=_auth(sid),
        ).json()

        assert multi["runs"]["u14_a"] == single_a
        assert multi["runs"]["u14_b"] == single_b
