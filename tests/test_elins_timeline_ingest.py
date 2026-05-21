"""
Tests for ELINS Unit 6 — CSV/JSON timeline ingestors.

Layered coverage (≥ 60 tests):
    A. SP CSV loader — happy path, header validation, row validation,
       trigger handling, N=0
    B. EC CSV loader — same coverage for the economic schema
    C. SP JSON loader — happy path, payload validation, point validation
    D. EC JSON loader — same coverage for the economic schema
    E. Integration sanity — ingested timelines are valid validator inputs
    F. Purity / I/O constraints — only CSV loaders touch open()
    G. Module surface — 4 functions exported, locked field tuples
    H. Determinism — same inputs → byte-equal outputs
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

import elins_timeline_ingest as ingest
from elins_regression_economic_coercion import (
    TimelineEconomic,
    TimePointEconomic,
    run_economic_coercion_regression,
)
from elins_regression_single_party import (
    Timeline,
    TimePoint,
    run_single_party_fear_regression,
)


# ===========================================================================
# CSV fixture helpers
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


def _write(tmp_path: Path, name: str, content: str) -> str:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return str(path)


def _sp_csv_two_rows(tmp_path: Path, name: str = "case-01.csv") -> str:
    return _write(
        tmp_path, name,
        _SP_HEADER + "\n"
        "t0,0.8,0.2,0.2,0.1,0.2,0.2,0.8,0.8,0.7,\n"
        "t1,0.4,0.6,0.6,0.5,0.6,0.6,0.4,0.4,0.5,protests\n",
    )


def _ec_csv_two_rows(tmp_path: Path, name: str = "ec-01.csv") -> str:
    return _write(
        tmp_path, name,
        _EC_HEADER + "\n"
        "t0,0.2,0.2,0.2,0.2,0.7,0.7,\n"
        "t1,0.7,0.7,0.6,0.5,0.3,0.3,layoffs\n",
    )


def _sp_csv_header_only(tmp_path: Path) -> str:
    return _write(tmp_path, "empty.csv", _SP_HEADER + "\n")


def _ec_csv_header_only(tmp_path: Path) -> str:
    return _write(tmp_path, "empty-ec.csv", _EC_HEADER + "\n")


# ===========================================================================
# JSON fixture helpers
# ===========================================================================
def _sp_json_one_point() -> dict:
    return {
        "timeline_id": "json-sp",
        "points": [
            {
                "t": "t0",
                "regime_competition": 0.8, "autocratization": 0.2,
                "repression_index": 0.2, "digital_repression": 0.1,
                "perceived_threat": 0.2, "fear_signal": 0.2,
                "dissent_capacity": 0.8, "normative_constraint": 0.8,
                "support_buffer": 0.7,
            },
        ],
    }


def _ec_json_one_point() -> dict:
    return {
        "timeline_id": "json-ec",
        "points": [
            {
                "t": "t0",
                "economic_pressure": 0.5, "material_insecurity": 0.5,
                "state_coercion": 0.5, "compliance_signal": 0.5,
                "resistance_capacity": 0.5, "support_buffer": 0.5,
            },
        ],
    }


# ===========================================================================
# A. SP CSV loader
# ===========================================================================
class TestSPCsvLoader:
    def test_happy_path_returns_timeline(self, tmp_path):
        tl = ingest.load_timeline_from_csv(_sp_csv_two_rows(tmp_path))
        assert isinstance(tl, Timeline)

    def test_timeline_id_from_filename_stem(self, tmp_path):
        tl = ingest.load_timeline_from_csv(
            _sp_csv_two_rows(tmp_path, name="case-42.csv"))
        assert tl.timeline_id == "case-42"

    def test_two_rows_parsed(self, tmp_path):
        tl = ingest.load_timeline_from_csv(_sp_csv_two_rows(tmp_path))
        assert len(tl.points) == 2

    def test_first_point_fields(self, tmp_path):
        tl = ingest.load_timeline_from_csv(_sp_csv_two_rows(tmp_path))
        p = tl.points[0]
        assert p.t == "t0"
        assert p.regime_competition == 0.8
        assert p.autocratization == 0.2

    def test_empty_trigger_event_becomes_none(self, tmp_path):
        tl = ingest.load_timeline_from_csv(_sp_csv_two_rows(tmp_path))
        assert tl.points[0].trigger_event is None

    def test_non_empty_trigger_event_preserved(self, tmp_path):
        tl = ingest.load_timeline_from_csv(_sp_csv_two_rows(tmp_path))
        assert tl.points[1].trigger_event == "protests"

    def test_header_only_yields_empty_points(self, tmp_path):
        tl = ingest.load_timeline_from_csv(_sp_csv_header_only(tmp_path))
        assert tl.points == ()

    def test_missing_header_field_raises(self, tmp_path):
        bad = _SP_HEADER.replace(",fear_signal", "")  # drop fear_signal
        path = _write(tmp_path, "bad.csv", bad + "\n")
        with pytest.raises(ValueError, match="missing required fields"):
            ingest.load_timeline_from_csv(path)

    def test_extra_header_field_rejected(self, tmp_path):
        bad = _SP_HEADER + ",extra_metadata"
        path = _write(tmp_path, "extra.csv",
                      bad + "\n"
                      "t0,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,,foo\n")
        with pytest.raises(ValueError, match="unexpected fields"):
            ingest.load_timeline_from_csv(path)

    def test_non_numeric_value_raises(self, tmp_path):
        path = _write(
            tmp_path, "nonnum.csv",
            _SP_HEADER + "\n"
            "t0,not_a_number,0.2,0.2,0.1,0.2,0.2,0.8,0.8,0.7,\n",
        )
        with pytest.raises(ValueError, match="not a number"):
            ingest.load_timeline_from_csv(path)

    def test_empty_numeric_cell_raises(self, tmp_path):
        path = _write(
            tmp_path, "empty_cell.csv",
            _SP_HEADER + "\n"
            "t0,,0.2,0.2,0.1,0.2,0.2,0.8,0.8,0.7,\n",
        )
        with pytest.raises(ValueError, match="is empty"):
            ingest.load_timeline_from_csv(path)

    def test_empty_t_cell_raises(self, tmp_path):
        path = _write(
            tmp_path, "empty_t.csv",
            _SP_HEADER + "\n"
            ",0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,0.5,\n",
        )
        with pytest.raises(ValueError, match="field 't' is empty"):
            ingest.load_timeline_from_csv(path)

    def test_nonexistent_file_raises_oserror(self, tmp_path):
        with pytest.raises((OSError, FileNotFoundError)):
            ingest.load_timeline_from_csv(str(tmp_path / "missing.csv"))

    def test_missing_header_row_raises(self, tmp_path):
        path = _write(tmp_path, "nohdr.csv", "")
        with pytest.raises(ValueError, match="missing a header row"):
            ingest.load_timeline_from_csv(path)


# ===========================================================================
# B. EC CSV loader
# ===========================================================================
class TestECCsvLoader:
    def test_happy_path_returns_timeline_economic(self, tmp_path):
        tl = ingest.load_economic_timeline_from_csv(_ec_csv_two_rows(tmp_path))
        assert isinstance(tl, TimelineEconomic)

    def test_timeline_id_from_filename(self, tmp_path):
        tl = ingest.load_economic_timeline_from_csv(
            _ec_csv_two_rows(tmp_path, name="ec-99.csv"))
        assert tl.timeline_id == "ec-99"

    def test_first_point_fields(self, tmp_path):
        tl = ingest.load_economic_timeline_from_csv(_ec_csv_two_rows(tmp_path))
        p = tl.points[0]
        assert p.t == "t0"
        assert p.economic_pressure == 0.2

    def test_trigger_event_preserved(self, tmp_path):
        tl = ingest.load_economic_timeline_from_csv(_ec_csv_two_rows(tmp_path))
        assert tl.points[1].trigger_event == "layoffs"

    def test_header_only_yields_empty(self, tmp_path):
        tl = ingest.load_economic_timeline_from_csv(_ec_csv_header_only(tmp_path))
        assert tl.points == ()

    def test_missing_required_field_raises(self, tmp_path):
        bad = _EC_HEADER.replace(",compliance_signal", "")
        path = _write(tmp_path, "bad-ec.csv", bad + "\n")
        with pytest.raises(ValueError, match="missing required fields"):
            ingest.load_economic_timeline_from_csv(path)

    def test_extra_header_rejected(self, tmp_path):
        bad = _EC_HEADER + ",extra_col"
        path = _write(tmp_path, "extra-ec.csv",
                      bad + "\n"
                      "t0,0.5,0.5,0.5,0.5,0.5,0.5,,foo\n")
        with pytest.raises(ValueError, match="unexpected fields"):
            ingest.load_economic_timeline_from_csv(path)

    def test_non_numeric_value_raises(self, tmp_path):
        path = _write(
            tmp_path, "nonnum-ec.csv",
            _EC_HEADER + "\n"
            "t0,not_a_num,0.5,0.5,0.5,0.5,0.5,\n",
        )
        with pytest.raises(ValueError, match="not a number"):
            ingest.load_economic_timeline_from_csv(path)

    def test_empty_numeric_cell_raises(self, tmp_path):
        path = _write(
            tmp_path, "empty-cell-ec.csv",
            _EC_HEADER + "\n"
            "t0,,0.5,0.5,0.5,0.5,0.5,\n",
        )
        with pytest.raises(ValueError, match="is empty"):
            ingest.load_economic_timeline_from_csv(path)

    def test_filename_with_complex_path(self, tmp_path):
        sub = tmp_path / "sub" / "dir"
        sub.mkdir(parents=True)
        path = _write(sub, "deep-ec-case.csv",
                      _EC_HEADER + "\n"
                      "t0,0.5,0.5,0.5,0.5,0.5,0.5,\n")
        tl = ingest.load_economic_timeline_from_csv(path)
        assert tl.timeline_id == "deep-ec-case"


# ===========================================================================
# C. SP JSON loader
# ===========================================================================
class TestSPJsonLoader:
    def test_happy_path_returns_timeline(self):
        tl = ingest.load_timeline_from_json(_sp_json_one_point())
        assert isinstance(tl, Timeline)
        assert tl.timeline_id == "json-sp"
        assert len(tl.points) == 1

    def test_empty_points_returns_empty_timeline(self):
        tl = ingest.load_timeline_from_json(
            {"timeline_id": "empty", "points": []})
        assert tl.points == ()

    def test_trigger_event_omitted_defaults_none(self):
        tl = ingest.load_timeline_from_json(_sp_json_one_point())
        assert tl.points[0].trigger_event is None

    def test_trigger_event_string_preserved(self):
        obj = _sp_json_one_point()
        obj["points"][0]["trigger_event"] = "purge"
        tl = ingest.load_timeline_from_json(obj)
        assert tl.points[0].trigger_event == "purge"

    def test_trigger_event_null_becomes_none(self):
        obj = _sp_json_one_point()
        obj["points"][0]["trigger_event"] = None
        tl = ingest.load_timeline_from_json(obj)
        assert tl.points[0].trigger_event is None

    def test_missing_timeline_id_raises(self):
        obj = _sp_json_one_point()
        del obj["timeline_id"]
        with pytest.raises(ValueError, match="timeline_id"):
            ingest.load_timeline_from_json(obj)

    def test_empty_timeline_id_raises(self):
        obj = _sp_json_one_point()
        obj["timeline_id"] = ""
        with pytest.raises(ValueError, match="timeline_id"):
            ingest.load_timeline_from_json(obj)

    def test_non_string_timeline_id_raises(self):
        obj = _sp_json_one_point()
        obj["timeline_id"] = 42
        with pytest.raises(ValueError, match="timeline_id"):
            ingest.load_timeline_from_json(obj)

    def test_non_dict_input_raises(self):
        with pytest.raises(ValueError, match="expected dict"):
            ingest.load_timeline_from_json("not a dict")  # type: ignore[arg-type]

    def test_missing_points_raises(self):
        with pytest.raises(ValueError, match="points must be a list"):
            ingest.load_timeline_from_json({"timeline_id": "x"})

    def test_points_not_list_raises(self):
        with pytest.raises(ValueError, match="points must be a list"):
            ingest.load_timeline_from_json(
                {"timeline_id": "x", "points": "oops"})

    def test_point_not_object_raises(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            ingest.load_timeline_from_json(
                {"timeline_id": "x", "points": ["bad"]})

    def test_missing_required_field_raises(self):
        obj = _sp_json_one_point()
        del obj["points"][0]["fear_signal"]
        with pytest.raises(ValueError, match="missing required field"):
            ingest.load_timeline_from_json(obj)

    def test_non_numeric_field_raises(self):
        obj = _sp_json_one_point()
        obj["points"][0]["fear_signal"] = "high"
        with pytest.raises(ValueError, match="must be a number"):
            ingest.load_timeline_from_json(obj)

    def test_bool_for_numeric_raises(self):
        obj = _sp_json_one_point()
        obj["points"][0]["fear_signal"] = True
        with pytest.raises(ValueError, match="must be a number"):
            ingest.load_timeline_from_json(obj)

    def test_int_accepted_for_numeric(self):
        obj = _sp_json_one_point()
        obj["points"][0]["fear_signal"] = 0
        obj["points"][0]["repression_index"] = 1
        tl = ingest.load_timeline_from_json(obj)
        assert tl.points[0].fear_signal == 0.0
        assert tl.points[0].repression_index == 1.0

    def test_non_string_t_raises(self):
        obj = _sp_json_one_point()
        obj["points"][0]["t"] = 42
        with pytest.raises(ValueError, match="must be a non-empty string"):
            ingest.load_timeline_from_json(obj)

    def test_empty_t_raises(self):
        obj = _sp_json_one_point()
        obj["points"][0]["t"] = ""
        with pytest.raises(ValueError, match="must be a non-empty string"):
            ingest.load_timeline_from_json(obj)

    def test_non_string_trigger_raises(self):
        obj = _sp_json_one_point()
        obj["points"][0]["trigger_event"] = 42
        with pytest.raises(ValueError, match="trigger_event must be a string"):
            ingest.load_timeline_from_json(obj)


# ===========================================================================
# D. EC JSON loader
# ===========================================================================
class TestECJsonLoader:
    def test_happy_path_returns_timeline_economic(self):
        tl = ingest.load_economic_timeline_from_json(_ec_json_one_point())
        assert isinstance(tl, TimelineEconomic)
        assert tl.timeline_id == "json-ec"

    def test_empty_points_returns_empty(self):
        tl = ingest.load_economic_timeline_from_json(
            {"timeline_id": "e", "points": []})
        assert tl.points == ()

    def test_missing_required_field_raises(self):
        obj = _ec_json_one_point()
        del obj["points"][0]["compliance_signal"]
        with pytest.raises(ValueError, match="missing required field"):
            ingest.load_economic_timeline_from_json(obj)

    def test_non_numeric_field_raises(self):
        obj = _ec_json_one_point()
        obj["points"][0]["compliance_signal"] = "high"
        with pytest.raises(ValueError, match="must be a number"):
            ingest.load_economic_timeline_from_json(obj)

    def test_bool_for_numeric_raises(self):
        obj = _ec_json_one_point()
        obj["points"][0]["compliance_signal"] = False
        with pytest.raises(ValueError, match="must be a number"):
            ingest.load_economic_timeline_from_json(obj)

    def test_missing_timeline_id_raises(self):
        with pytest.raises(ValueError, match="timeline_id"):
            ingest.load_economic_timeline_from_json({"points": []})

    def test_non_dict_raises(self):
        with pytest.raises(ValueError, match="expected dict"):
            ingest.load_economic_timeline_from_json([])  # type: ignore[arg-type]

    def test_points_not_list_raises(self):
        with pytest.raises(ValueError, match="points must be a list"):
            ingest.load_economic_timeline_from_json(
                {"timeline_id": "x", "points": 42})

    def test_trigger_omitted_defaults_none(self):
        tl = ingest.load_economic_timeline_from_json(_ec_json_one_point())
        assert tl.points[0].trigger_event is None

    def test_trigger_string_preserved(self):
        obj = _ec_json_one_point()
        obj["points"][0]["trigger_event"] = "sanctions"
        tl = ingest.load_economic_timeline_from_json(obj)
        assert tl.points[0].trigger_event == "sanctions"


# ===========================================================================
# E. Integration sanity — ingested timelines feed validators
# ===========================================================================
class TestIntegrationSanity:
    def test_sp_csv_to_validator(self, tmp_path):
        tl = ingest.load_timeline_from_csv(_sp_csv_two_rows(tmp_path))
        r = run_single_party_fear_regression(tl)
        assert 0 <= r.score <= 10

    def test_sp_json_to_validator(self):
        tl = ingest.load_timeline_from_json(_sp_json_one_point())
        r = run_single_party_fear_regression(tl)
        assert 0 <= r.score <= 10

    def test_ec_csv_to_validator(self, tmp_path):
        tl = ingest.load_economic_timeline_from_csv(_ec_csv_two_rows(tmp_path))
        r = run_economic_coercion_regression(tl)
        assert 0 <= r.score <= 10

    def test_ec_json_to_validator(self):
        tl = ingest.load_economic_timeline_from_json(_ec_json_one_point())
        r = run_economic_coercion_regression(tl)
        assert 0 <= r.score <= 10

    def test_sp_n0_csv_yields_score_zero(self, tmp_path):
        tl = ingest.load_timeline_from_csv(_sp_csv_header_only(tmp_path))
        assert run_single_party_fear_regression(tl).score == 0

    def test_ec_n0_json_yields_score_zero(self):
        tl = ingest.load_economic_timeline_from_json(
            {"timeline_id": "e", "points": []})
        assert run_economic_coercion_regression(tl).score == 0


# ===========================================================================
# F. Purity / I/O constraints
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(ingest)

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

    def test_csv_loaders_use_open(self):
        """The two CSV loader functions should each call open()."""
        sp_src = inspect.getsource(ingest.load_timeline_from_csv)
        ec_src = inspect.getsource(ingest.load_economic_timeline_from_csv)
        assert "open(" in sp_src
        assert "open(" in ec_src

    def test_json_loaders_do_not_use_open(self):
        """The JSON loaders MUST NOT touch the filesystem."""
        sp_json_src = inspect.getsource(ingest.load_timeline_from_json)
        ec_json_src = inspect.getsource(ingest.load_economic_timeline_from_json)
        assert "open(" not in sp_json_src
        assert "open(" not in ec_json_src

    def test_no_subprocess_or_eval(self):
        src = self._src()
        for forbidden in ("subprocess", "exec(", "eval("):
            assert forbidden not in src


# ===========================================================================
# G. Module surface — public API + locked field tuples
# ===========================================================================
class TestModuleSurface:
    def test_four_public_loaders_exist_and_callable(self):
        for name in (
            "load_timeline_from_csv",
            "load_timeline_from_json",
            "load_economic_timeline_from_csv",
            "load_economic_timeline_from_json",
        ):
            assert hasattr(ingest, name)
            assert callable(getattr(ingest, name))

    def test_sp_numeric_fields_locked(self):
        assert ingest._SP_NUMERIC_FIELDS == (
            "regime_competition", "autocratization", "repression_index",
            "digital_repression", "perceived_threat", "fear_signal",
            "dissent_capacity", "normative_constraint", "support_buffer",
        )

    def test_ec_numeric_fields_locked(self):
        assert ingest._EC_NUMERIC_FIELDS == (
            "economic_pressure", "material_insecurity", "state_coercion",
            "compliance_signal", "resistance_capacity", "support_buffer",
        )

    def test_sp_csv_header_set_includes_t_and_trigger(self):
        assert "t" in ingest._SP_CSV_HEADER
        assert "trigger_event" in ingest._SP_CSV_HEADER

    def test_ec_csv_header_set_includes_t_and_trigger(self):
        assert "t" in ingest._EC_CSV_HEADER
        assert "trigger_event" in ingest._EC_CSV_HEADER


# ===========================================================================
# H. Determinism — same inputs → equal outputs
# ===========================================================================
class TestDeterminism:
    def test_sp_json_byte_equal(self):
        obj = _sp_json_one_point()
        t1 = ingest.load_timeline_from_json(obj)
        t2 = ingest.load_timeline_from_json(obj)
        assert t1 == t2

    def test_ec_json_byte_equal(self):
        obj = _ec_json_one_point()
        t1 = ingest.load_economic_timeline_from_json(obj)
        t2 = ingest.load_economic_timeline_from_json(obj)
        assert t1 == t2

    def test_sp_csv_byte_equal(self, tmp_path):
        path = _sp_csv_two_rows(tmp_path)
        t1 = ingest.load_timeline_from_csv(path)
        t2 = ingest.load_timeline_from_csv(path)
        assert t1 == t2

    def test_ec_csv_byte_equal(self, tmp_path):
        path = _ec_csv_two_rows(tmp_path)
        t1 = ingest.load_economic_timeline_from_csv(path)
        t2 = ingest.load_economic_timeline_from_csv(path)
        assert t1 == t2

    def test_input_dict_not_mutated(self):
        obj = _sp_json_one_point()
        before = repr(obj)
        ingest.load_timeline_from_json(obj)
        after = repr(obj)
        assert before == after
