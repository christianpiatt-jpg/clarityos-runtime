"""
Tests for ELINS Unit 10 — persistence layer + analyze_and_store wrapper
+ 4 FastAPI endpoints.

Layered coverage (≥ 60 tests):
    A. Persistence core — save / load / list / overwrite / validation
    B. analyze_and_store wrapper — directory + pairs paths
    C. Endpoint: POST /elins/regression/store
    D. Endpoint: POST /elins/regression/analyze_directory_and_store
    E. Endpoint: GET /elins/regression/runs
    F. Endpoint: GET /elins/regression/run/{run_id}
    G. Purity / isolation
    H. Determinism
    I. Module surface
"""
from __future__ import annotations

import inspect
import json
import os
import re
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_timeline_dashboard as etd
from elins_regression_economic_coercion import (
    TimelineEconomic, TimePointEconomic,
)
from elins_regression_single_party import Timeline, TimePoint


# ===========================================================================
# Fixtures — runs-dir isolation per test
# ===========================================================================
@pytest.fixture(autouse=True)
def _runs_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point CLARITYOS_ELINS_RUNS_DIR at a fresh tmp dir for every test
    so persistence state never leaks between tests."""
    runs_dir = tmp_path / "elins_runs"
    monkeypatch.setenv(ep._RUNS_DIR_ENV_VAR, str(runs_dir))
    yield runs_dir


# ===========================================================================
# Timeline helpers (mirror Unit 5 fixtures)
# ===========================================================================
def _sp_tp(*, t="t0", **overrides) -> TimePoint:
    base = dict(
        t=t, regime_competition=0.5, autocratization=0.5,
        repression_index=0.5, digital_repression=0.5,
        perceived_threat=0.5, fear_signal=0.5,
        dissent_capacity=0.5, normative_constraint=0.5,
        support_buffer=0.5, trigger_event=None,
    )
    base.update(overrides)
    return TimePoint(**base)


def _ec_tp(*, t="t0", **overrides) -> TimePointEconomic:
    base = dict(
        t=t, economic_pressure=0.5, material_insecurity=0.5,
        state_coercion=0.5, compliance_signal=0.5,
        resistance_capacity=0.5, support_buffer=0.5, trigger_event=None,
    )
    base.update(overrides)
    return TimePointEconomic(**base)


def _sp_tl(tid="sp_test") -> Timeline:
    return Timeline(timeline_id=tid, points=(_sp_tp(),))


def _ec_tl(tid="ec_test") -> TimelineEconomic:
    return TimelineEconomic(timeline_id=tid, points=(_ec_tp(),))


# ===========================================================================
# CSV/JSON helpers for analyze_directory_and_store endpoint tests
# ===========================================================================
_SP_HEADER = (
    "t,regime_competition,autocratization,repression_index,"
    "digital_repression,perceived_threat,fear_signal,dissent_capacity,"
    "normative_constraint,support_buffer,trigger_event"
)
_EC_HEADER = (
    "t,economic_pressure,material_insecurity,state_coercion,"
    "compliance_signal,resistance_capacity,support_buffer,trigger_event"
)


def _make_pair_files(tmp_path: Path, stem: str) -> None:
    (tmp_path / f"{stem}_sp.csv").write_text(
        _SP_HEADER + "\nt0,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,\n",
        encoding="utf-8",
    )
    (tmp_path / f"{stem}_ec.csv").write_text(
        _EC_HEADER + "\nt0,0.5,0.5,0.5,0.5,0.5,0.5,\n",
        encoding="utf-8",
    )


def _payload_pair(sp: Timeline, ec: TimelineEconomic) -> dict:
    return {
        "single_party_timeline": {
            "timeline_id": sp.timeline_id,
            "points": [
                {
                    "t": p.t,
                    "regime_competition":   p.regime_competition,
                    "autocratization":      p.autocratization,
                    "repression_index":     p.repression_index,
                    "digital_repression":   p.digital_repression,
                    "perceived_threat":     p.perceived_threat,
                    "fear_signal":          p.fear_signal,
                    "dissent_capacity":     p.dissent_capacity,
                    "normative_constraint": p.normative_constraint,
                    "support_buffer":       p.support_buffer,
                    "trigger_event":        p.trigger_event,
                }
                for p in sp.points
            ],
        },
        "economic_timeline": {
            "timeline_id": ec.timeline_id,
            "points": [
                {
                    "t": p.t,
                    "economic_pressure":   p.economic_pressure,
                    "material_insecurity": p.material_insecurity,
                    "state_coercion":      p.state_coercion,
                    "compliance_signal":   p.compliance_signal,
                    "resistance_capacity": p.resistance_capacity,
                    "support_buffer":      p.support_buffer,
                    "trigger_event":       p.trigger_event,
                }
                for p in ec.points
            ],
        },
    }


# ===========================================================================
# Endpoint fixtures
# ===========================================================================
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
# A. Persistence core
# ===========================================================================
class TestPersistenceCore:
    def test_save_then_load_byte_equal_dict(self):
        payload = {"score": 9, "band": "Strong"}
        ep.save_comparison_result("run_1", payload)
        # Unit 19: load returns {metadata, result} envelope.
        assert ep.load_comparison_result("run_1")["result"] == payload

    def test_save_then_load_byte_equal_list(self):
        payload = [{"score": 7}, {"score": 5}, {"score": 9}]
        ep.save_comparison_result("run_2", payload)
        assert ep.load_comparison_result("run_2")["result"] == payload

    def test_save_then_load_nested(self):
        payload = {"runs": [{"id": "a", "scores": [1, 2, 3]}]}
        ep.save_comparison_result("nested", payload)
        assert ep.load_comparison_result("nested")["result"] == payload

    def test_load_missing_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError, match="run_id not found"):
            ep.load_comparison_result("does_not_exist")

    def test_list_runs_empty(self):
        assert ep.list_runs() == []

    def test_list_runs_after_three_saves(self):
        ep.save_comparison_result("zeta", {})
        ep.save_comparison_result("alpha", {})
        ep.save_comparison_result("mid", {})
        assert ep.list_runs() == ["alpha", "mid", "zeta"]

    def test_list_runs_alphabetical(self):
        for r in ("c", "a", "b", "d"):
            ep.save_comparison_result(r, {})
        assert ep.list_runs() == ["a", "b", "c", "d"]

    def test_list_runs_ignores_non_json_files(self, _runs_dir_isolation):
        ep.save_comparison_result("real_run", {})
        # Drop an unrelated file in the runs dir.
        (_runs_dir_isolation / "README.txt").write_text("notes")
        (_runs_dir_isolation / "scratch.tmp").write_text("junk")
        assert ep.list_runs() == ["real_run"]

    def test_list_runs_ignores_subdirs(self, _runs_dir_isolation):
        ep.save_comparison_result("real_run", {})
        (_runs_dir_isolation / "subdir").mkdir()
        assert ep.list_runs() == ["real_run"]

    def test_list_runs_skips_invalid_stem_filenames(self, _runs_dir_isolation):
        ep.save_comparison_result("ok_run", {})
        # Manual file with disallowed characters in the stem.
        (_runs_dir_isolation / "bad name with spaces.json").write_text("{}")
        assert ep.list_runs() == ["ok_run"]

    def test_save_creates_runs_directory(self, _runs_dir_isolation):
        assert not _runs_dir_isolation.exists()
        ep.save_comparison_result("first", {})
        assert _runs_dir_isolation.is_dir()

    def test_overwrite_replaces_existing(self):
        ep.save_comparison_result("doubled", {"v": 1})
        ep.save_comparison_result("doubled", {"v": 2})
        # Unit 19: load returns {metadata, result} envelope.
        assert ep.load_comparison_result("doubled")["result"] == {"v": 2}

    def test_overwrite_keeps_only_one_entry_in_list_runs(self):
        ep.save_comparison_result("once", {"v": 1})
        ep.save_comparison_result("once", {"v": 2})
        assert ep.list_runs() == ["once"]


class TestRunIdValidation:
    @pytest.mark.parametrize("bad_id", ["", " ", "with space", "a/b",
                                         "a\\b", "..", "../escape",
                                         "a.b", "$dangerous", "a:b"])
    def test_save_rejects_bad_run_ids(self, bad_id):
        with pytest.raises(ValueError):
            ep.save_comparison_result(bad_id, {})

    @pytest.mark.parametrize("bad_id", ["", " ", "a/b", "..", "$x"])
    def test_load_rejects_bad_run_ids(self, bad_id):
        with pytest.raises(ValueError):
            ep.load_comparison_result(bad_id)

    def test_save_rejects_non_string(self):
        with pytest.raises(ValueError, match="must be a string"):
            ep.save_comparison_result(42, {})  # type: ignore[arg-type]

    def test_load_rejects_non_string(self):
        with pytest.raises(ValueError, match="must be a string"):
            ep.load_comparison_result(None)  # type: ignore[arg-type]

    @pytest.mark.parametrize("good_id", [
        "run_1", "RUN-2", "abc123", "case01_sp",
        "a-b-c", "A_B_C-1-2", "x",
    ])
    def test_save_accepts_valid_run_ids(self, good_id):
        ep.save_comparison_result(good_id, {})
        assert good_id in ep.list_runs()


class TestSerialisationFormat:
    def test_envelope_json_is_sorted_keys(self, _runs_dir_isolation):
        """Unit 25: the stored envelope_json column is sorted-keys for
        byte-equal determinism. Replaces the pre-Unit-25 file-read
        check now that storage is SQLite."""
        import sqlite3
        ep.save_comparison_result("ordered",
                                   {"z": 1, "a": 2, "m": 3})
        conn = sqlite3.connect(str(_runs_dir_isolation / "elins_runs.db"))
        try:
            row = conn.execute(
                "SELECT envelope_json FROM runs WHERE run_id = ?",
                ("ordered",),
            ).fetchone()
        finally:
            conn.close()
        raw = row[0]
        # Within the "result" sub-dict, sorted-keys means 'a' < 'm' < 'z'.
        assert raw.index('"a"') < raw.index('"m"') < raw.index('"z"')

    def test_repeated_save_result_byte_equal(self, _runs_dir_isolation):
        """Unit 19: the metadata.created_at timestamp may shift between
        back-to-back saves, but the inner ``result`` portion must remain
        byte-equal for the same input payload (sorted-keys + 2-space
        determinism)."""
        payload = {"score": 9, "band": "Strong", "extras": [1, 2, 3]}
        ep.save_comparison_result("first", payload)
        env_a = ep.load_comparison_result("first")
        ep.save_comparison_result("first", payload)
        env_b = ep.load_comparison_result("first")
        assert env_a["result"] == env_b["result"]


# ===========================================================================
# B. analyze_and_store wrapper
# ===========================================================================
class TestWrapper:
    def test_pairs_input_returns_run_id_and_result(self):
        out = etd.analyze_and_store([(_sp_tl(), _ec_tl())])
        assert "run_id" in out
        assert "result" in out
        assert isinstance(out["result"], list)
        assert len(out["result"]) == 1

    def test_pairs_input_stores_result(self):
        out = etd.analyze_and_store([(_sp_tl(), _ec_tl())])
        # Unit 19: load returns {metadata, result} envelope.
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["result"] == out["result"]

    def test_pairs_input_matches_direct_batch_dashboard(self):
        pairs = [(_sp_tl(), _ec_tl())]
        out = etd.analyze_and_store(pairs)
        direct = etd.compare_regressions_batch_dashboard(pairs)
        assert out["result"] == direct

    def test_directory_input_returns_run_id_and_result(self, tmp_path):
        _make_pair_files(tmp_path, "case01")
        out = etd.analyze_and_store(str(tmp_path))
        assert "run_id" in out
        assert len(out["result"]) == 1

    def test_directory_input_matches_direct_analyze(self, tmp_path):
        _make_pair_files(tmp_path, "case01")
        out = etd.analyze_and_store(str(tmp_path))
        direct = etd.analyze_directory(str(tmp_path))
        assert out["result"] == direct

    def test_explicit_run_id_used_as_is(self):
        out = etd.analyze_and_store([(_sp_tl(), _ec_tl())], run_id="my_run_42")
        assert out["run_id"] == "my_run_42"
        # Unit 19: load returns {metadata, result} envelope.
        assert ep.load_comparison_result("my_run_42")["result"] == out["result"]

    def test_auto_generated_run_id_uuid_like(self):
        out = etd.analyze_and_store([(_sp_tl(), _ec_tl())])
        # Format: "run_" + 32 hex chars.
        assert re.match(r"^run_[0-9a-f]{32}$", out["run_id"])

    def test_two_calls_get_distinct_auto_ids(self):
        a = etd.analyze_and_store([(_sp_tl(), _ec_tl())])
        b = etd.analyze_and_store([(_sp_tl(), _ec_tl())])
        assert a["run_id"] != b["run_id"]

    def test_empty_pairs_input_stores_empty_result(self):
        out = etd.analyze_and_store([])
        assert out["result"] == []
        # Unit 19: load returns {metadata, result} envelope.
        assert ep.load_comparison_result(out["run_id"])["result"] == []

    def test_empty_directory_stores_empty_result(self, tmp_path):
        out = etd.analyze_and_store(str(tmp_path))
        assert out["result"] == []

    def test_invalid_input_type_raises(self):
        with pytest.raises(ValueError, match="expected directory path"):
            etd.analyze_and_store(42)  # type: ignore[arg-type]

    def test_invalid_run_id_propagates_value_error(self):
        with pytest.raises(ValueError):
            etd.analyze_and_store([(_sp_tl(), _ec_tl())], run_id="bad/id")


# ===========================================================================
# C. Endpoint: POST /elins/regression/store
# ===========================================================================
class TestStoreEndpoint:
    def test_valid_pairs_returns_200_with_run_id(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/store",
            json={"pairs": [_payload_pair(_sp_tl(), _ec_tl())]},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "run_id" in body
        assert "result" in body
        assert len(body["result"]) == 1

    def test_explicit_run_id_used(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/store",
            json={"run_id": "explicit_id_99",
                  "pairs": [_payload_pair(_sp_tl(), _ec_tl())]},
            headers=_auth(sid),
        )
        assert resp.json()["run_id"] == "explicit_id_99"

    def test_auto_run_id_when_not_provided(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/store",
            json={"pairs": [_payload_pair(_sp_tl(), _ec_tl())]},
            headers=_auth(sid),
        )
        rid = resp.json()["run_id"]
        assert re.match(r"^run_[0-9a-f]{32}$", rid)

    def test_unauth_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/store",
            json={"pairs": []},
        )
        assert resp.status_code == 401

    def test_missing_pairs_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/store",
            json={}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_pairs_not_list_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/store",
            json={"pairs": "nope"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_bad_run_id_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/store",
            json={"run_id": "../escape", "pairs": []},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_empty_run_id_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/store",
            json={"run_id": "", "pairs": []},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_empty_pairs_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/store",
            json={"pairs": []},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json()["result"] == []

    def test_malformed_pair_400(self, client, app_module):
        sid = _make_user_session(app_module)
        bad = _payload_pair(_sp_tl(), _ec_tl())
        del bad["single_party_timeline"]["points"][0]["fear_signal"]
        resp = client.post(
            "/elins/regression/store",
            json={"pairs": [bad]},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_store_then_fetch_round_trip(self, client, app_module):
        sid = _make_user_session(app_module)
        store_resp = client.post(
            "/elins/regression/store",
            json={"run_id": "round_trip",
                  "pairs": [_payload_pair(_sp_tl(), _ec_tl())]},
            headers=_auth(sid),
        )
        assert store_resp.status_code == 200
        get_resp = client.get(
            "/elins/regression/run/round_trip",
            headers=_auth(sid),
        )
        assert get_resp.status_code == 200
        assert get_resp.json() == store_resp.json()["result"]


# ===========================================================================
# D. Endpoint: POST /elins/regression/analyze_directory_and_store
# ===========================================================================
class TestAnalyzeDirectoryAndStoreEndpoint:
    def test_valid_dir_200(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        _make_pair_files(evidence_dir, "case01")
        resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"path": str(evidence_dir)},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "run_id" in body
        assert len(body["result"]) == 1

    def test_explicit_run_id(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        _make_pair_files(evidence_dir, "case01")
        resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"path": str(evidence_dir), "run_id": "dir_run_42"},
            headers=_auth(sid),
        )
        assert resp.json()["run_id"] == "dir_run_42"

    def test_missing_dir_404(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"path": str(tmp_path / "nope")},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_path_is_a_file_404(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        f = tmp_path / "f.txt"
        f.write_text("hello")
        resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"path": str(f)},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_missing_path_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_bad_run_id_400(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"path": str(evidence_dir), "run_id": "bad/id"},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_file_in_dir_400(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        # Bad CSV.
        (evidence_dir / "case01_sp.csv").write_text(
            _SP_HEADER + "\nt0,nope,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,\n",
            encoding="utf-8",
        )
        (evidence_dir / "case01_ec.csv").write_text(
            _EC_HEADER + "\nt0,0.5,0.5,0.5,0.5,0.5,0.5,\n",
            encoding="utf-8",
        )
        resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"path": str(evidence_dir)},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_unauth_401(self, client, app_module, tmp_path):
        resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"path": str(tmp_path)},
        )
        assert resp.status_code == 401

    def test_round_trip_directory(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        evidence_dir = tmp_path / "evidence"
        evidence_dir.mkdir()
        _make_pair_files(evidence_dir, "case01")
        store_resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"path": str(evidence_dir), "run_id": "dir_round_trip"},
            headers=_auth(sid),
        )
        assert store_resp.status_code == 200
        get_resp = client.get(
            "/elins/regression/run/dir_round_trip",
            headers=_auth(sid),
        )
        assert get_resp.json() == store_resp.json()["result"]


# ===========================================================================
# E. Endpoint: GET /elins/regression/runs
# ===========================================================================
class TestListRunsEndpoint:
    def test_empty_returns_empty_list(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get("/elins/regression/runs", headers=_auth(sid))
        assert resp.status_code == 200
        # Unit 20: bare list of metadata dicts; empty when no runs exist.
        assert resp.json() == []

    def test_lists_after_three_stores(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("c", "a", "b"):
            client.post(
                "/elins/regression/store",
                json={"run_id": rid, "pairs": []},
                headers=_auth(sid),
            )
        # Unit 20: list contains metadata dicts (one per run, alphabetical
        # by run_id). The locked field set is asserted by the dedicated
        # Unit 20 listing test module — here we only check the run_ids.
        resp = client.get("/elins/regression/runs", headers=_auth(sid))
        body = resp.json()
        assert [row["run_id"] for row in body] == ["a", "b", "c"]

    def test_unauth_401(self, client, app_module):
        resp = client.get("/elins/regression/runs")
        assert resp.status_code == 401


# ===========================================================================
# F. Endpoint: GET /elins/regression/run/{run_id}
# ===========================================================================
class TestGetRunEndpoint:
    def test_existing_run_returns_200_with_result(self, client, app_module):
        sid = _make_user_session(app_module)
        client.post(
            "/elins/regression/store",
            json={"run_id": "exists",
                  "pairs": [_payload_pair(_sp_tl(), _ec_tl())]},
            headers=_auth(sid),
        )
        resp = client.get("/elins/regression/run/exists", headers=_auth(sid))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) == 1

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            "/elins/regression/run/never_stored",
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_bad_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        # FastAPI path matching may catch some traversal attempts
        # before our code; either 400 or 404 is acceptable here, but
        # under no circumstances should it 200 with arbitrary content.
        resp = client.get(
            "/elins/regression/run/bad$id",
            headers=_auth(sid),
        )
        assert resp.status_code in (400, 404)

    def test_unauth_401(self, client, app_module):
        resp = client.get("/elins/regression/run/anything")
        assert resp.status_code == 401

    def test_returns_stored_payload_byte_equal(self, client, app_module):
        sid = _make_user_session(app_module)
        store_resp = client.post(
            "/elins/regression/store",
            json={"run_id": "byte_eq",
                  "pairs": [_payload_pair(_sp_tl(), _ec_tl())]},
            headers=_auth(sid),
        )
        get_resp = client.get(
            "/elins/regression/run/byte_eq",
            headers=_auth(sid),
        )
        assert get_resp.json() == store_resp.json()["result"]


# ===========================================================================
# G. Purity / isolation
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(ep)

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
        """Persistence module itself must not use random/secrets;
        UUID generation lives in the dashboard wrapper."""
        src = self._src()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid.", "import uuid"):
            assert forbidden not in src

    def test_no_subprocess_or_eval(self):
        src = self._src()
        for forbidden in ("subprocess", "exec(", "eval("):
            assert forbidden not in src

    def test_no_basin_inference_imports(self):
        src = self._src()
        for pattern in (
            "import elins_dashboard", "from elins_dashboard",
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
        ):
            assert pattern not in src


# ===========================================================================
# H. Determinism
# ===========================================================================
class TestDeterminism:
    def test_load_repeated_byte_equal(self):
        ep.save_comparison_result("det1", {"a": 1, "b": [2, 3]})
        a = ep.load_comparison_result("det1")
        b = ep.load_comparison_result("det1")
        assert a == b

    def test_save_load_loop_byte_equal(self):
        payload = {"runs": [{"id": "x", "score": 9}]}
        ep.save_comparison_result("det2", payload)
        loaded = ep.load_comparison_result("det2")
        # Unit 19: load returns {metadata, result} envelope.
        assert loaded["result"] == payload

    def test_list_runs_repeated_byte_equal(self):
        for r in ("a", "b", "c"):
            ep.save_comparison_result(r, {})
        assert ep.list_runs() == ep.list_runs()


# ===========================================================================
# I. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_three_persistence_functions_exported(self):
        for name in ("save_comparison_result",
                     "load_comparison_result", "list_runs"):
            assert hasattr(ep, name)
            assert callable(getattr(ep, name))

    def test_wrapper_exported(self):
        assert hasattr(etd, "analyze_and_store")
        assert callable(etd.analyze_and_store)

    def test_run_id_regex_locked(self):
        rx = ep._RUN_ID_RE
        assert rx.match("run_1") and rx.match("ABC-99") and rx.match("x")
        assert rx.match("") is None
        assert rx.match("a/b") is None
        assert rx.match("..") is None
        assert rx.match("a b") is None

    def test_default_runs_dir_constant(self):
        assert ep._DEFAULT_RUNS_DIR == "./elins_runs"

    def test_runs_dir_env_var_constant(self):
        assert ep._RUNS_DIR_ENV_VAR == "CLARITYOS_ELINS_RUNS_DIR"
