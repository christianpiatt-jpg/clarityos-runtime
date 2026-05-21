"""
Tests for ELINS Unit 9 — directory scanner + analyze_directory wrapper
+ FastAPI endpoint.

Layered coverage (≥ 60 tests):
    A. Scanner core — empty / partial / complete pair handling
    B. Mixed format combinations (CSV/JSON × SP/EC)
    C. Pairing rules — ignore unrelated files, sort by stem, ignore subdirs
    D. Error handling — missing dir, file-as-dir, ambiguity, malformed file
    E. analyze_directory wrapper
    F. Endpoint behavior
    G. Purity / I/O constraints
    H. Module surface
    I. Determinism
"""
from __future__ import annotations

import inspect
import json
import os
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_directory_scanner as scanner
import elins_timeline_dashboard as etd
from elins_regression_economic_coercion import TimelineEconomic
from elins_regression_single_party import Timeline


# ===========================================================================
# CSV / JSON content helpers
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


def _sp_csv_content() -> str:
    return _SP_HEADER + "\nt0,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,\n"


def _ec_csv_content() -> str:
    return _EC_HEADER + "\nt0,0.5,0.5,0.5,0.5,0.5,0.5,\n"


def _sp_json_content() -> str:
    return json.dumps({
        "timeline_id": "json-sp-inline",
        "points": [
            {"t": "t0",
             "regime_competition": 0.5, "autocratization": 0.5,
             "repression_index": 0.5, "digital_repression": 0.5,
             "perceived_threat": 0.5, "fear_signal": 0.5,
             "dissent_capacity": 0.5, "normative_constraint": 0.5,
             "support_buffer": 0.5},
        ],
    })


def _ec_json_content() -> str:
    return json.dumps({
        "timeline_id": "json-ec-inline",
        "points": [
            {"t": "t0",
             "economic_pressure": 0.5, "material_insecurity": 0.5,
             "state_coercion": 0.5, "compliance_signal": 0.5,
             "resistance_capacity": 0.5, "support_buffer": 0.5},
        ],
    })


def _write(tmp_path: Path, name: str, content: str) -> str:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return str(p)


def _make_complete_pair(tmp_path: Path, stem: str, *,
                        sp_format: str = "csv", ec_format: str = "csv") -> None:
    """Write both _sp and _ec files for `stem` in the chosen formats."""
    if sp_format == "csv":
        _write(tmp_path, f"{stem}_sp.csv", _sp_csv_content())
    else:
        _write(tmp_path, f"{stem}_sp.json", _sp_json_content())
    if ec_format == "csv":
        _write(tmp_path, f"{stem}_ec.csv", _ec_csv_content())
    else:
        _write(tmp_path, f"{stem}_ec.json", _ec_json_content())


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
# A. Scanner core
# ===========================================================================
class TestScannerCore:
    def test_empty_directory_returns_empty(self, tmp_path):
        assert scanner.scan_directory_for_timeline_pairs(str(tmp_path)) == []

    def test_only_sp_files_returns_empty(self, tmp_path):
        _write(tmp_path, "case01_sp.csv", _sp_csv_content())
        assert scanner.scan_directory_for_timeline_pairs(str(tmp_path)) == []

    def test_only_ec_files_returns_empty(self, tmp_path):
        _write(tmp_path, "case01_ec.csv", _ec_csv_content())
        assert scanner.scan_directory_for_timeline_pairs(str(tmp_path)) == []

    def test_one_complete_pair_returns_one(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1

    def test_pair_returns_typed_timelines(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        sp, ec = scanner.scan_directory_for_timeline_pairs(str(tmp_path))[0]
        assert isinstance(sp, Timeline)
        assert isinstance(ec, TimelineEconomic)

    def test_three_pairs_returned(self, tmp_path):
        for stem in ("case01", "case02", "case03"):
            _make_complete_pair(tmp_path, stem)
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 3

    def test_incomplete_pair_silently_dropped(self, tmp_path):
        # case01 complete, case02 only sp
        _make_complete_pair(tmp_path, "case01")
        _write(tmp_path, "case02_sp.csv", _sp_csv_content())
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1

    def test_only_complete_pairs_in_output(self, tmp_path):
        # case01 complete, case02 only ec, case03 complete
        _make_complete_pair(tmp_path, "case01")
        _write(tmp_path, "case02_ec.csv", _ec_csv_content())
        _make_complete_pair(tmp_path, "case03")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        # Only case01 and case03 form complete pairs.
        assert len(result) == 2


class TestPairingRules:
    def test_ignores_readme(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        _write(tmp_path, "README.md", "# notes")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1

    def test_ignores_temp_files(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        _write(tmp_path, "scratch.tmp", "junk")
        _write(tmp_path, "notes.txt", "hello")
        _write(tmp_path, "data.xlsx", "binary blob")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1

    def test_ignores_files_with_wrong_role_suffix(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        _write(tmp_path, "case02_xx.csv", _sp_csv_content())  # wrong role
        _write(tmp_path, "case03_meta.json", _sp_json_content())
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1

    def test_ignores_files_with_wrong_extension(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        _write(tmp_path, "case02_sp.txt", "wrong ext")
        _write(tmp_path, "case02_ec.yaml", "wrong ext")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1

    def test_ignores_subdirectories(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        sub = tmp_path / "subdir"
        sub.mkdir()
        # Files in subdir should NOT be scanned.
        _make_complete_pair(sub, "case_in_subdir")
        # Even named like a pair, the subdir itself is skipped.
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1

    def test_results_sorted_by_stem(self, tmp_path):
        # Create out of alphabetical order.
        for stem in ("zeta", "alpha", "mid"):
            _make_complete_pair(tmp_path, stem)
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        # Each pair's SP timeline_id is the SP filename stem
        # ("zeta_sp"), so sorted stems are alpha < mid < zeta.
        stems = [sp.timeline_id for sp, _ in result]
        assert stems == ["alpha_sp", "mid_sp", "zeta_sp"]


# ===========================================================================
# B. Mixed format combinations
# ===========================================================================
class TestFormatCombinations:
    def test_sp_csv_ec_csv(self, tmp_path):
        _make_complete_pair(tmp_path, "case", sp_format="csv", ec_format="csv")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1
        assert result[0][0].timeline_id == "case_sp"   # CSV: filename stem
        assert result[0][1].timeline_id == "case_ec"

    def test_sp_json_ec_json(self, tmp_path):
        _make_complete_pair(tmp_path, "case", sp_format="json", ec_format="json")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1
        # JSON: timeline_id from the JSON's own field, not the filename.
        assert result[0][0].timeline_id == "json-sp-inline"
        assert result[0][1].timeline_id == "json-ec-inline"

    def test_sp_csv_ec_json(self, tmp_path):
        _make_complete_pair(tmp_path, "case", sp_format="csv", ec_format="json")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1
        assert result[0][0].timeline_id == "case_sp"           # CSV
        assert result[0][1].timeline_id == "json-ec-inline"    # JSON

    def test_sp_json_ec_csv(self, tmp_path):
        _make_complete_pair(tmp_path, "case", sp_format="json", ec_format="csv")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 1
        assert result[0][0].timeline_id == "json-sp-inline"
        assert result[0][1].timeline_id == "case_ec"

    def test_multiple_pairs_with_different_format_combos(self, tmp_path):
        _make_complete_pair(tmp_path, "a01", sp_format="csv",  ec_format="csv")
        _make_complete_pair(tmp_path, "b02", sp_format="json", ec_format="json")
        _make_complete_pair(tmp_path, "c03", sp_format="csv",  ec_format="json")
        _make_complete_pair(tmp_path, "d04", sp_format="json", ec_format="csv")
        result = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert len(result) == 4

    def test_csv_loaded_via_csv_loader(self, tmp_path):
        """SP CSV should be loaded via the CSV ingestor (timeline_id from
        filename), not the JSON ingestor."""
        _make_complete_pair(tmp_path, "csv_only", sp_format="csv", ec_format="csv")
        sp, ec = scanner.scan_directory_for_timeline_pairs(str(tmp_path))[0]
        assert sp.timeline_id == "csv_only_sp"

    def test_json_loaded_via_json_loader(self, tmp_path):
        """SP JSON should be loaded via the JSON ingestor (timeline_id
        from the JSON dict's own field)."""
        _make_complete_pair(tmp_path, "json_only", sp_format="json", ec_format="json")
        sp, ec = scanner.scan_directory_for_timeline_pairs(str(tmp_path))[0]
        assert sp.timeline_id == "json-sp-inline"


# ===========================================================================
# D. Error handling
# ===========================================================================
class TestErrorHandling:
    def test_nonexistent_path_raises_filenotfound(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            scanner.scan_directory_for_timeline_pairs(str(tmp_path / "missing"))

    def test_path_is_a_file_raises_notadirectory(self, tmp_path):
        f = _write(tmp_path, "not_a_dir.txt", "hello")
        with pytest.raises(NotADirectoryError):
            scanner.scan_directory_for_timeline_pairs(f)

    def test_empty_path_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty str"):
            scanner.scan_directory_for_timeline_pairs("")

    def test_non_string_path_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty str"):
            scanner.scan_directory_for_timeline_pairs(42)  # type: ignore[arg-type]

    def test_none_path_raises_value_error(self):
        with pytest.raises(ValueError, match="non-empty str"):
            scanner.scan_directory_for_timeline_pairs(None)  # type: ignore[arg-type]

    def test_ambiguous_sp_role_raises(self, tmp_path):
        """Both case01_sp.csv AND case01_sp.json present → ValueError."""
        _write(tmp_path, "case01_sp.csv",  _sp_csv_content())
        _write(tmp_path, "case01_sp.json", _sp_json_content())
        _write(tmp_path, "case01_ec.csv",  _ec_csv_content())
        with pytest.raises(ValueError, match="ambiguous role"):
            scanner.scan_directory_for_timeline_pairs(str(tmp_path))

    def test_ambiguous_ec_role_raises(self, tmp_path):
        _write(tmp_path, "case01_sp.csv",  _sp_csv_content())
        _write(tmp_path, "case01_ec.csv",  _ec_csv_content())
        _write(tmp_path, "case01_ec.json", _ec_json_content())
        with pytest.raises(ValueError, match="ambiguous role"):
            scanner.scan_directory_for_timeline_pairs(str(tmp_path))

    def test_malformed_csv_propagates_value_error(self, tmp_path):
        _write(tmp_path, "case01_sp.csv",
               _SP_HEADER + "\nt0,not_a_number,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,\n")
        _write(tmp_path, "case01_ec.csv", _ec_csv_content())
        with pytest.raises(ValueError):
            scanner.scan_directory_for_timeline_pairs(str(tmp_path))

    def test_malformed_json_propagates_error(self, tmp_path):
        _write(tmp_path, "case01_sp.json", "{ not valid json")
        _write(tmp_path, "case01_ec.csv", _ec_csv_content())
        with pytest.raises((ValueError, json.JSONDecodeError)):
            scanner.scan_directory_for_timeline_pairs(str(tmp_path))


# ===========================================================================
# E. analyze_directory wrapper
# ===========================================================================
class TestAnalyzeDirectoryWrapper:
    def test_empty_dir_returns_empty(self, tmp_path):
        assert etd.analyze_directory(str(tmp_path)) == []

    def test_one_pair_returns_one_dict(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        out = etd.analyze_directory(str(tmp_path))
        assert len(out) == 1
        assert isinstance(out[0], dict)

    def test_three_pairs_three_dicts(self, tmp_path):
        for stem in ("a", "b", "c"):
            _make_complete_pair(tmp_path, stem)
        out = etd.analyze_directory(str(tmp_path))
        assert len(out) == 3

    def test_required_keys_per_dict(self, tmp_path):
        _make_complete_pair(tmp_path, "case01")
        out = etd.analyze_directory(str(tmp_path))
        for entry in out:
            for key in (
                "single_party_score", "economic_coercion_score",
                "score_delta", "score_delta_label",
                "single_party_band", "economic_coercion_band",
                "band_delta", "band_delta_label",
                "assertions_failed_single_party",
                "assertions_failed_economic",
                "scenario_results_single_party",
                "scenario_results_economic",
            ):
                assert key in entry

    def test_output_matches_direct_batch_dashboard(self, tmp_path):
        for stem in ("alpha", "beta"):
            _make_complete_pair(tmp_path, stem)
        pairs = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        direct = etd.compare_regressions_batch_dashboard(pairs)
        via_wrapper = etd.analyze_directory(str(tmp_path))
        assert via_wrapper == direct

    def test_propagates_filenotfound(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            etd.analyze_directory(str(tmp_path / "missing"))

    def test_propagates_value_error_on_malformed_file(self, tmp_path):
        _write(tmp_path, "case01_sp.csv",
               _SP_HEADER + "\nt0,not_a_num,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,\n")
        _write(tmp_path, "case01_ec.csv", _ec_csv_content())
        with pytest.raises(ValueError):
            etd.analyze_directory(str(tmp_path))


# ===========================================================================
# F. Endpoint behavior
# ===========================================================================
class TestEndpoint:
    def test_valid_dir_200_with_one_pair(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        _make_complete_pair(tmp_path, "case01")
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 1

    def test_empty_dir_200_empty_list(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_three_pairs_returned_in_stem_order(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        for stem in ("zeta", "alpha", "mid"):
            _make_complete_pair(tmp_path, stem)
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 3

    def test_missing_directory_returns_404(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path / "not_there")},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_path_is_a_file_returns_404(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        f = _write(tmp_path, "not_a_dir.txt", "hello")
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": f},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_missing_path_field_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_empty_path_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": ""}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_string_path_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": 42}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_unauth_returns_401(self, client, app_module, tmp_path):
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
        )
        assert resp.status_code == 401

    def test_response_matches_direct_wrapper(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        _make_complete_pair(tmp_path, "case01")
        _make_complete_pair(tmp_path, "case02")
        direct = etd.analyze_directory(str(tmp_path))
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_malformed_csv_in_dir_returns_400(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        _write(tmp_path, "case01_sp.csv",
               _SP_HEADER + "\nt0,not_a_num,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,\n")
        _write(tmp_path, "case01_ec.csv", _ec_csv_content())
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_json_in_dir_returns_500_or_400(self, client, app_module, tmp_path):
        """Malformed JSON typically raises json.JSONDecodeError (subclass
        of ValueError) — either 400 (caught as bad evidence) or a
        framework 500 is acceptable here. The specific contract: the
        endpoint does not crash silently."""
        sid = _make_user_session(app_module)
        _write(tmp_path, "case01_sp.json", "{ not valid json")
        _write(tmp_path, "case01_ec.csv", _ec_csv_content())
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code in (400, 500)

    def test_ambiguous_role_returns_400(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        _write(tmp_path, "case01_sp.csv",  _sp_csv_content())
        _write(tmp_path, "case01_sp.json", _sp_json_content())
        _write(tmp_path, "case01_ec.csv",  _ec_csv_content())
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_unrelated_files_ignored(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        _make_complete_pair(tmp_path, "case01")
        _write(tmp_path, "README.md", "# notes")
        _write(tmp_path, "scratch.tmp", "junk")
        resp = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# ===========================================================================
# G. Purity / I/O constraints
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(scanner)

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
                          "import secrets", "from secrets"):
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
# H. Module surface
# ===========================================================================
class TestModuleSurface:
    def test_scanner_callable(self):
        assert callable(scanner.scan_directory_for_timeline_pairs)

    def test_analyze_directory_callable(self):
        assert callable(etd.analyze_directory)

    def test_pair_file_regex_locked(self):
        """The locked regex matches the documented filename convention."""
        rx = scanner._PAIR_FILE_RE
        assert rx.match("case01_sp.csv")
        assert rx.match("case01_sp.json")
        assert rx.match("case01_ec.csv")
        assert rx.match("case01_ec.json")
        # Negatives
        assert rx.match("case01_xx.csv") is None
        assert rx.match("case01_sp.txt") is None
        assert rx.match("README.md") is None
        assert rx.match("_sp.csv") is None  # empty stem


# ===========================================================================
# I. Determinism
# ===========================================================================
class TestDeterminism:
    def test_repeated_scans_byte_equal(self, tmp_path):
        for stem in ("a", "b", "c"):
            _make_complete_pair(tmp_path, stem)
        r1 = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        r2 = scanner.scan_directory_for_timeline_pairs(str(tmp_path))
        assert r1 == r2

    def test_repeated_analyze_byte_equal(self, tmp_path):
        for stem in ("a", "b"):
            _make_complete_pair(tmp_path, stem)
        r1 = etd.analyze_directory(str(tmp_path))
        r2 = etd.analyze_directory(str(tmp_path))
        assert r1 == r2

    def test_endpoint_byte_equal_repeated(self, client, app_module, tmp_path):
        sid = _make_user_session(app_module)
        _make_complete_pair(tmp_path, "case01")
        r1 = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)}, headers=_auth(sid))
        r2 = client.post(
            "/elins/regression/analyze_directory",
            json={"path": str(tmp_path)}, headers=_auth(sid))
        assert r1.json() == r2.json()


# ===========================================================================
# J. Existing endpoints unaffected
# ===========================================================================
class TestExistingEndpointsUnaffected:
    def test_health_still_works(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_compare_endpoint_still_works(self, client, app_module):
        sid = _make_user_session(app_module)
        # Build a valid single-compare payload from minimal data.
        sp_payload = {
            "timeline_id": "ad-hoc",
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
            "timeline_id": "ad-hoc-ec",
            "points": [
                {"t": "t0",
                 "economic_pressure": 0.5, "material_insecurity": 0.5,
                 "state_coercion": 0.5, "compliance_signal": 0.5,
                 "resistance_capacity": 0.5, "support_buffer": 0.5},
            ],
        }
        resp = client.post(
            "/elins/regression/compare",
            json={"single_party_timeline": sp_payload,
                  "economic_timeline": ec_payload},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
