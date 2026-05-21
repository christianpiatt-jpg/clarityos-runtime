"""
Tests for ELINS Unit 19 — run metadata wrapper (timestamps + source tags).

Layered coverage (≥ 60 tests, target 70+):
    A. Persistence — envelope shape, save/load round-trip, legacy compat
    B. Wrapper behavior — analytics modules see the new envelope
    C. Endpoint — GET /elins/regression/run/{run_id}/metadata
    D. Integration — analyze_and_store source/evidence_dir inference
    E. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import json
import re
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_run_diff as diff_mod
import elins_run_drift as drift_mod
import elins_run_drift_magnitude as mag_mod
import elins_run_drift_series as series_mod
import elins_run_drift_severity as sev_mod
import elins_run_summary as summary_mod
import elins_run_summary_multi as multi_mod
import elins_timeline_dashboard as etd


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


def _entry(pair_id="p1", *, sp=5, ec=5,
           sp_band="Acceptable", ec_band="Acceptable") -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp,
        "economic_coercion_score": ec,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _write_legacy_file(runs_dir: Path, run_id: str, payload) -> None:
    """Unit 25: insert a legacy-shaped envelope (``metadata=None``)
    directly into the SQLite DB, simulating a stored run created
    before Unit 19. Bypasses the public API because the test scenario
    is "this run already exists with no metadata"."""
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
# A. Persistence — envelope shape, round-trip, legacy compat
# ===========================================================================
class TestPersistenceEnvelopeShape:
    def test_save_then_load_returns_envelope(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert isinstance(loaded, dict)
        assert set(loaded.keys()) == {"metadata", "result"}

    def test_load_metadata_is_dict(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert isinstance(loaded["metadata"], dict)

    def test_metadata_has_four_locked_keys(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert set(loaded["metadata"].keys()) == {
            "created_at", "source", "evidence_dir", "engine_version",
        }

    def test_default_source_is_single(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert loaded["metadata"]["source"] == "single"

    def test_default_evidence_dir_is_none(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert loaded["metadata"]["evidence_dir"] is None

    def test_engine_version_locked(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert loaded["metadata"]["engine_version"] == "elins-19"

    def test_engine_version_constant_locked(self):
        assert ep._ENGINE_VERSION == "elins-19"

    def test_allowed_sources_locked(self):
        assert ep._ALLOWED_SOURCES == ("single", "batch", "directory")

    def test_created_at_is_string(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        assert isinstance(loaded["metadata"]["created_at"], str)

    def test_created_at_iso8601_prefix(self):
        ep.save_comparison_result("r", [_entry("p1")])
        loaded = ep.load_comparison_result("r")
        # ISO 8601 begins with YYYY-MM-DDTHH:MM:SS — assert that prefix.
        ts = loaded["metadata"]["created_at"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)

    def test_result_field_preserves_payload(self):
        payload = [_entry("p1", sp=5), _entry("p2", sp=8)]
        ep.save_comparison_result("r", payload)
        loaded = ep.load_comparison_result("r")
        assert loaded["result"] == payload

    def test_save_with_explicit_single_source(self):
        ep.save_comparison_result("r", [_entry("p1")], source="single")
        assert ep.load_comparison_result("r")["metadata"]["source"] == "single"

    def test_save_with_batch_source(self):
        ep.save_comparison_result(
            "r", [_entry("p1"), _entry("p2")], source="batch",
        )
        assert ep.load_comparison_result("r")["metadata"]["source"] == "batch"

    def test_save_with_directory_source_and_evidence_dir(self):
        ep.save_comparison_result(
            "r", [_entry("p1")],
            source="directory", evidence_dir="/path/to/evidence",
        )
        meta = ep.load_comparison_result("r")["metadata"]
        assert meta["source"] == "directory"
        assert meta["evidence_dir"] == "/path/to/evidence"

    def test_save_rejects_invalid_source(self):
        with pytest.raises(ValueError, match="source must be"):
            ep.save_comparison_result("r", [_entry("p1")], source="hacker")

    def test_save_rejects_none_source(self):
        with pytest.raises(ValueError, match="source must be"):
            ep.save_comparison_result("r", [_entry("p1")], source=None)  # type: ignore[arg-type]

    def test_save_rejects_int_source(self):
        with pytest.raises(ValueError, match="source must be"):
            ep.save_comparison_result("r", [_entry("p1")], source=1)  # type: ignore[arg-type]

    def test_save_accepts_evidence_dir_none_explicitly(self):
        ep.save_comparison_result(
            "r", [_entry("p1")], source="single", evidence_dir=None,
        )
        assert ep.load_comparison_result("r")["metadata"]["evidence_dir"] is None

    def test_save_accepts_evidence_dir_empty_string(self):
        # Empty string is a valid string — persistence layer doesn't
        # validate dir contents, only stores what it's told.
        ep.save_comparison_result(
            "r", [_entry("p1")], source="directory", evidence_dir="",
        )
        assert ep.load_comparison_result("r")["metadata"]["evidence_dir"] == ""

    def test_round_trip_preserves_complex_payload(self):
        payload = [
            _entry("a", sp=3, ec=7, sp_band="Strong", ec_band="Weak"),
            _entry("b", sp=8, ec=2, sp_band="Acceptable",
                   ec_band="Fails core logic"),
        ]
        ep.save_comparison_result("r", payload, source="batch")
        loaded = ep.load_comparison_result("r")
        assert loaded["result"] == payload
        assert loaded["metadata"]["source"] == "batch"

    def test_overwrite_refreshes_created_at(self, monkeypatch):
        """Overwriting an existing run_id picks up a fresh created_at.

        Unit 25: the ``datetime.now()`` call site lives in
        ``elins_persistence_sqlite`` (where ``_build_metadata`` is
        defined); the façade just re-exports. We monkeypatch the
        implementation module so the injection actually reaches the
        save path."""
        import elins_persistence_sqlite as _ep_sql
        seq = iter([
            _FakeDt("2026-05-12T10:00:00+00:00"),
            _FakeDt("2026-05-12T10:00:01+00:00"),
        ])

        class _FakeDateTime:
            @staticmethod
            def now(tz=None):
                return next(seq)

        monkeypatch.setattr(_ep_sql, "datetime", _FakeDateTime)
        ep.save_comparison_result("r", [_entry("p1")])
        ts_a = ep.load_comparison_result("r")["metadata"]["created_at"]
        ep.save_comparison_result("r", [_entry("p1")])
        ts_b = ep.load_comparison_result("r")["metadata"]["created_at"]
        assert ts_a != ts_b
        assert ts_a == "2026-05-12T10:00:00+00:00"
        assert ts_b == "2026-05-12T10:00:01+00:00"

    def test_save_rejects_malformed_run_id(self):
        with pytest.raises(ValueError):
            ep.save_comparison_result("bad/id", [_entry("p1")])

    def test_load_rejects_malformed_run_id(self):
        with pytest.raises(ValueError):
            ep.load_comparison_result("bad/id")

    def test_load_missing_run_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            ep.load_comparison_result("ghost")


class _FakeDt:
    """Tiny helper for deterministic created_at injection."""
    def __init__(self, iso: str):
        self._iso = iso

    def isoformat(self) -> str:
        return self._iso


class TestLegacyCompatibility:
    def test_legacy_list_file_load_normalised(self, _runs_dir_isolation):
        _write_legacy_file(_runs_dir_isolation, "leg",
                           [_entry("p1", sp=5)])
        loaded = ep.load_comparison_result("leg")
        assert isinstance(loaded, dict)
        assert set(loaded.keys()) == {"metadata", "result"}

    def test_legacy_list_file_metadata_is_none(self, _runs_dir_isolation):
        _write_legacy_file(_runs_dir_isolation, "leg",
                           [_entry("p1", sp=5)])
        loaded = ep.load_comparison_result("leg")
        assert loaded["metadata"] is None

    def test_legacy_list_file_result_preserves_payload(
        self, _runs_dir_isolation,
    ):
        payload = [_entry("p1", sp=5), _entry("p2", sp=8)]
        _write_legacy_file(_runs_dir_isolation, "leg", payload)
        loaded = ep.load_comparison_result("leg")
        assert loaded["result"] == payload

    def test_legacy_dict_file_falls_back_to_envelope(
        self, _runs_dir_isolation,
    ):
        """A stray dict file (e.g. legacy free-form payload) without
        envelope keys must still be returned via the envelope shape."""
        _runs_dir_isolation.mkdir(parents=True, exist_ok=True)
        (_runs_dir_isolation / "weird.json").write_text(
            json.dumps({"foo": "bar"}), encoding="utf-8",
        )
        loaded = ep.load_comparison_result("weird")
        assert loaded["metadata"] is None
        assert loaded["result"] == {"foo": "bar"}

    def test_new_format_envelope_returned_as_is(self, _runs_dir_isolation):
        # Drop a fully-formed envelope manually and confirm it round-trips.
        _runs_dir_isolation.mkdir(parents=True, exist_ok=True)
        envelope = {
            "metadata": {
                "created_at":     "2026-01-01T00:00:00+00:00",
                "source":         "batch",
                "evidence_dir":   "/x/y",
                "engine_version": "elins-19",
            },
            "result": [_entry("p1")],
        }
        (_runs_dir_isolation / "preformed.json").write_text(
            json.dumps(envelope), encoding="utf-8",
        )
        loaded = ep.load_comparison_result("preformed")
        assert loaded == envelope


# ===========================================================================
# B. Wrapper behavior — analytics modules see the new envelope
# ===========================================================================
class TestWrapperBehavior:
    """Each analytics wrapper must operate on the inner ``result``
    payload, regardless of whether the run is new-format or legacy."""

    def test_summary_wrapper_with_new_format(self):
        ep.save_comparison_result("r", [_entry("p1"), _entry("p2")])
        out = summary_mod.summary_table_for_run_id("r")
        assert out["total_pairs"] == 2

    def test_summary_wrapper_with_legacy_format(self, _runs_dir_isolation):
        _write_legacy_file(_runs_dir_isolation, "leg",
                           [_entry("p1"), _entry("p2"), _entry("p3")])
        out = summary_mod.summary_table_for_run_id("leg")
        assert out["total_pairs"] == 3

    def test_summary_multi_wrapper_with_mixed_formats(
        self, _runs_dir_isolation,
    ):
        ep.save_comparison_result("new", [_entry("p1")])
        _write_legacy_file(_runs_dir_isolation, "old",
                           [_entry("p1"), _entry("p2")])
        out = multi_mod.summary_across_run_ids(["new", "old"])
        assert out["runs"]["new"]["total_pairs"] == 1
        assert out["runs"]["old"]["total_pairs"] == 2

    def test_diff_wrapper_with_new_format(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8, ec=5)])
        out = diff_mod.diff_runs("a", "b")
        # Diff returns a dict — just verify it ran without error.
        assert isinstance(out, dict)

    def test_diff_wrapper_with_legacy_format(self, _runs_dir_isolation):
        _write_legacy_file(_runs_dir_isolation, "old_a",
                           [_entry("p1", sp=5, ec=5)])
        _write_legacy_file(_runs_dir_isolation, "old_b",
                           [_entry("p1", sp=8, ec=5)])
        out = diff_mod.diff_runs("old_a", "old_b")
        assert isinstance(out, dict)

    def test_drift_wrapper_with_new_format(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8, ec=5)])
        out = drift_mod.detect_drift_for_run_ids(["a", "b"])
        assert isinstance(out, dict)

    def test_drift_magnitude_wrapper_with_new_format(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8, ec=5)])
        out = mag_mod.drift_magnitude_for_run_ids(["a", "b"])
        assert isinstance(out, dict)

    def test_drift_severity_wrapper_with_new_format(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8, ec=5)])
        out = sev_mod.classify_drift_severity_for_run_ids(["a", "b"])
        assert isinstance(out, dict)

    def test_drift_series_wrapper_with_new_format(self):
        ep.save_comparison_result("a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("b", [_entry("p1", sp=8, ec=5)])
        out = series_mod.drift_series_for_run_ids(["a", "b"])
        assert "p1" in out
        assert out["p1"]["single_party_scores"] == [5, 8]

    def test_drift_series_wrapper_with_legacy_format(
        self, _runs_dir_isolation,
    ):
        _write_legacy_file(_runs_dir_isolation, "ol_a",
                           [_entry("p1", sp=5, ec=5)])
        _write_legacy_file(_runs_dir_isolation, "ol_b",
                           [_entry("p1", sp=8, ec=5)])
        out = series_mod.drift_series_for_run_ids(["ol_a", "ol_b"])
        assert "p1" in out
        assert out["p1"]["single_party_scores"] == [5, 8]

    def test_summary_metadata_does_not_leak_into_summary(self):
        """Metadata keys must not appear in the summary output."""
        ep.save_comparison_result("r", [_entry("p1")])
        out = summary_mod.summary_table_for_run_id("r")
        for forbidden in ("metadata", "created_at", "source",
                          "evidence_dir", "engine_version"):
            assert forbidden not in out

    def test_wrapper_metadata_does_not_alter_drift_classification(
        self, _runs_dir_isolation,
    ):
        """The drift classification on a legacy run should equal the
        same drift on a new-format run with identical payload."""
        # Legacy
        _write_legacy_file(_runs_dir_isolation, "leg_a",
                           [_entry("p1", sp=5, ec=5)])
        _write_legacy_file(_runs_dir_isolation, "leg_b",
                           [_entry("p1", sp=8, ec=5)])
        legacy_out = drift_mod.detect_drift_for_run_ids(["leg_a", "leg_b"])
        # New format (different ids to avoid collision)
        ep.save_comparison_result("new_a", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("new_b", [_entry("p1", sp=8, ec=5)])
        new_out = drift_mod.detect_drift_for_run_ids(["new_a", "new_b"])
        assert legacy_out == new_out


# ===========================================================================
# C. Endpoint — GET /elins/regression/run/{run_id}/metadata
# ===========================================================================
class TestMetadataEndpoint:
    _PATH_FMT = "/elins/regression/run/{rid}/metadata"

    def test_existing_run_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        resp = client.get(self._PATH_FMT.format(rid="r"), headers=_auth(sid))
        assert resp.status_code == 200

    def test_response_top_level_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        assert set(body.keys()) == {"run_id", "metadata"}

    def test_response_carries_run_id(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("my_run_19", [_entry("p1")])
        body = client.get(
            self._PATH_FMT.format(rid="my_run_19"), headers=_auth(sid),
        ).json()
        assert body["run_id"] == "my_run_19"

    def test_metadata_has_four_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        assert set(body["metadata"].keys()) == {
            "created_at", "source", "evidence_dir", "engine_version",
        }

    def test_metadata_engine_version_locked(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        assert body["metadata"]["engine_version"] == "elins-19"

    def test_metadata_default_source(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        assert body["metadata"]["source"] == "single"

    def test_metadata_default_evidence_dir_none(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        assert body["metadata"]["evidence_dir"] is None

    def test_metadata_explicit_source_batch(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")], source="batch")
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        assert body["metadata"]["source"] == "batch"

    def test_metadata_explicit_directory_with_evidence_dir(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result(
            "r", [_entry("p1")],
            source="directory", evidence_dir="/the/dir",
        )
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        assert body["metadata"]["source"] == "directory"
        assert body["metadata"]["evidence_dir"] == "/the/dir"

    def test_legacy_run_metadata_is_null(
        self, client, app_module, _runs_dir_isolation,
    ):
        sid = _make_user_session(app_module)
        _write_legacy_file(_runs_dir_isolation, "leg",
                           [_entry("p1")])
        body = client.get(
            self._PATH_FMT.format(rid="leg"), headers=_auth(sid),
        ).json()
        assert body["run_id"] == "leg"
        assert body["metadata"] is None

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            self._PATH_FMT.format(rid="ghost"), headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_unauth_returns_401(self, client, app_module):
        resp = client.get(self._PATH_FMT.format(rid="anything"))
        assert resp.status_code == 401

    def test_malformed_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.get(
            self._PATH_FMT.format(rid="bad$id"), headers=_auth(sid),
        )
        # FastAPI may catch some traversal patterns; either 400 or 404
        # is acceptable, never 200.
        assert resp.status_code in (400, 404)

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        r1 = client.get(self._PATH_FMT.format(rid="r"), headers=_auth(sid))
        r2 = client.get(self._PATH_FMT.format(rid="r"), headers=_auth(sid))
        assert r1.json() == r2.json()

    def test_metadata_endpoint_does_not_return_result(
        self, client, app_module,
    ):
        """The metadata endpoint must NOT include the run's payload."""
        sid = _make_user_session(app_module)
        ep.save_comparison_result(
            "r", [_entry("p1"), _entry("p2"), _entry("p3")],
        )
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        assert "result" not in body

    def test_get_run_endpoint_still_returns_list(self, client, app_module):
        """Sanity: the original GET /elins/regression/run/{id} endpoint
        must continue returning the bare ``result`` list (not the
        envelope), preserving its pre-Unit-19 contract."""
        sid = _make_user_session(app_module)
        ep.save_comparison_result(
            "r", [_entry("p1"), _entry("p2")],
        )
        body = client.get(
            "/elins/regression/run/r", headers=_auth(sid),
        ).json()
        assert isinstance(body, list)
        assert len(body) == 2

    def test_get_run_endpoint_does_not_leak_metadata(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(
            "/elins/regression/run/r", headers=_auth(sid),
        ).json()
        # body is a list, not a dict — no metadata key possible
        assert isinstance(body, list)

    def test_metadata_created_at_is_iso8601(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("r", [_entry("p1")])
        body = client.get(
            self._PATH_FMT.format(rid="r"), headers=_auth(sid),
        ).json()
        ts = body["metadata"]["created_at"]
        assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", ts)

    def test_metadata_endpoint_independent_of_run_payload(
        self, client, app_module,
    ):
        """A run with empty result and a run with N entries return the
        same metadata shape."""
        sid = _make_user_session(app_module)
        ep.save_comparison_result("empty", [])
        ep.save_comparison_result("full",  [_entry("p1"), _entry("p2")])
        empty_meta = client.get(
            self._PATH_FMT.format(rid="empty"), headers=_auth(sid),
        ).json()["metadata"]
        full_meta = client.get(
            self._PATH_FMT.format(rid="full"), headers=_auth(sid),
        ).json()["metadata"]
        assert set(empty_meta.keys()) == set(full_meta.keys())


# ===========================================================================
# D. Integration — analyze_and_store source/evidence_dir inference
# ===========================================================================
class TestAnalyzeAndStoreIntegration:
    def _sp_tl(self):
        from elins_regression_single_party import Timeline, TimePoint
        return Timeline(
            timeline_id="sp_x",
            points=(TimePoint(
                t="t0",
                regime_competition=0.5, autocratization=0.5,
                repression_index=0.5, digital_repression=0.5,
                perceived_threat=0.5, fear_signal=0.5,
                dissent_capacity=0.5, normative_constraint=0.5,
                support_buffer=0.5,
            ),),
        )

    def _ec_tl(self):
        from elins_regression_economic_coercion import (
            TimelineEconomic, TimePointEconomic,
        )
        return TimelineEconomic(
            timeline_id="ec_x",
            points=(TimePointEconomic(
                t="t0",
                economic_pressure=0.5, material_insecurity=0.5,
                state_coercion=0.5, compliance_signal=0.5,
                resistance_capacity=0.5, support_buffer=0.5,
            ),),
        )

    def test_single_pair_input_infers_single_source(self):
        out = etd.analyze_and_store([(self._sp_tl(), self._ec_tl())])
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["source"] == "single"

    def test_batch_input_infers_batch_source(self):
        pairs = [
            (self._sp_tl(), self._ec_tl()),
            (self._sp_tl(), self._ec_tl()),
        ]
        out = etd.analyze_and_store(pairs)
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["source"] == "batch"

    def test_empty_batch_input_infers_batch_source(self):
        out = etd.analyze_and_store([])
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["source"] == "batch"

    def test_directory_input_infers_directory_source(self, tmp_path):
        # Empty directory is fine — analyze_directory returns []. We
        # only need the source/evidence_dir tagging to fire.
        out = etd.analyze_and_store(str(tmp_path))
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["source"] == "directory"

    def test_directory_input_captures_evidence_dir(self, tmp_path):
        out = etd.analyze_and_store(str(tmp_path))
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["evidence_dir"] == str(tmp_path)

    def test_pairs_input_evidence_dir_is_none(self):
        out = etd.analyze_and_store([(self._sp_tl(), self._ec_tl())])
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["evidence_dir"] is None

    def test_explicit_source_overrides_inference(self):
        out = etd.analyze_and_store(
            [(self._sp_tl(), self._ec_tl())],
            source="batch",
        )
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["source"] == "batch"

    def test_explicit_evidence_dir_overrides_inference(self, tmp_path):
        out = etd.analyze_and_store(
            str(tmp_path), evidence_dir="/override/path",
        )
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["evidence_dir"] == "/override/path"

    def test_analyze_and_store_engine_version_locked(self):
        out = etd.analyze_and_store([(self._sp_tl(), self._ec_tl())])
        loaded = ep.load_comparison_result(out["run_id"])
        assert loaded["metadata"]["engine_version"] == "elins-19"

    def test_analyze_and_store_invalid_source_raises(self):
        with pytest.raises(ValueError, match="source must be"):
            etd.analyze_and_store(
                [(self._sp_tl(), self._ec_tl())],
                source="hacker",
            )

    def test_store_endpoint_records_single_source_for_one_pair(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        sp = {
            "timeline_id": "sp_a",
            "points": [
                {"t": "t0",
                 "regime_competition": 0.5, "autocratization": 0.5,
                 "repression_index": 0.5, "digital_repression": 0.5,
                 "perceived_threat": 0.5, "fear_signal": 0.5,
                 "dissent_capacity": 0.5, "normative_constraint": 0.5,
                 "support_buffer": 0.5},
            ],
        }
        ec = {
            "timeline_id": "ec_a",
            "points": [
                {"t": "t0",
                 "economic_pressure": 0.5, "material_insecurity": 0.5,
                 "state_coercion": 0.5, "compliance_signal": 0.5,
                 "resistance_capacity": 0.5, "support_buffer": 0.5},
            ],
        }
        store_resp = client.post(
            "/elins/regression/store",
            json={"run_id": "single_via_endpoint", "pairs": [
                {"single_party_timeline": sp, "economic_timeline": ec},
            ]},
            headers=_auth(sid),
        )
        assert store_resp.status_code == 200
        meta_body = client.get(
            "/elins/regression/run/single_via_endpoint/metadata",
            headers=_auth(sid),
        ).json()
        assert meta_body["metadata"]["source"] == "single"

    def test_store_endpoint_records_batch_source_for_multi_pair(
        self, client, app_module,
    ):
        sid = _make_user_session(app_module)
        sp = {
            "timeline_id": "sp_a",
            "points": [
                {"t": "t0",
                 "regime_competition": 0.5, "autocratization": 0.5,
                 "repression_index": 0.5, "digital_repression": 0.5,
                 "perceived_threat": 0.5, "fear_signal": 0.5,
                 "dissent_capacity": 0.5, "normative_constraint": 0.5,
                 "support_buffer": 0.5},
            ],
        }
        ec = {
            "timeline_id": "ec_a",
            "points": [
                {"t": "t0",
                 "economic_pressure": 0.5, "material_insecurity": 0.5,
                 "state_coercion": 0.5, "compliance_signal": 0.5,
                 "resistance_capacity": 0.5, "support_buffer": 0.5},
            ],
        }
        sp2 = dict(sp); sp2["timeline_id"] = "sp_b"
        ec2 = dict(ec); ec2["timeline_id"] = "ec_b"
        store_resp = client.post(
            "/elins/regression/store",
            json={"run_id": "batch_via_endpoint", "pairs": [
                {"single_party_timeline": sp,  "economic_timeline": ec},
                {"single_party_timeline": sp2, "economic_timeline": ec2},
            ]},
            headers=_auth(sid),
        )
        assert store_resp.status_code == 200
        meta_body = client.get(
            "/elins/regression/run/batch_via_endpoint/metadata",
            headers=_auth(sid),
        ).json()
        assert meta_body["metadata"]["source"] == "batch"

    def test_directory_endpoint_records_directory_source(
        self, client, app_module, tmp_path,
    ):
        sid = _make_user_session(app_module)
        store_resp = client.post(
            "/elins/regression/analyze_directory_and_store",
            json={"run_id": "dir_via_endpoint", "path": str(tmp_path)},
            headers=_auth(sid),
        )
        assert store_resp.status_code == 200
        meta_body = client.get(
            "/elins/regression/run/dir_via_endpoint/metadata",
            headers=_auth(sid),
        ).json()
        assert meta_body["metadata"]["source"] == "directory"
        assert meta_body["metadata"]["evidence_dir"] == str(tmp_path)


# ===========================================================================
# E. Source-code purity / module surface
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(ep)

    def test_metadata_constants_exposed(self):
        for name in (
            "_ENGINE_VERSION", "_ALLOWED_SOURCES",
            "_META_CREATED_AT_FIELD", "_META_SOURCE_FIELD",
            "_META_EVIDENCE_DIR_FIELD", "_META_ENGINE_VERSION_FIELD",
            "_ENVELOPE_METADATA_KEY", "_ENVELOPE_RESULT_KEY",
        ):
            assert hasattr(ep, name), f"missing module constant: {name}"

    def test_metadata_field_names_locked(self):
        assert ep._META_CREATED_AT_FIELD == "created_at"
        assert ep._META_SOURCE_FIELD == "source"
        assert ep._META_EVIDENCE_DIR_FIELD == "evidence_dir"
        assert ep._META_ENGINE_VERSION_FIELD == "engine_version"

    def test_envelope_keys_locked(self):
        assert ep._ENVELOPE_METADATA_KEY == "metadata"
        assert ep._ENVELOPE_RESULT_KEY == "result"

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

    def test_no_subprocess_or_eval(self):
        src = self._src()
        for forbidden in ("subprocess", "exec(", "eval("):
            assert forbidden not in src

    def test_validate_source_helper_callable(self):
        assert callable(ep._validate_source)

    def test_build_metadata_helper_callable(self):
        assert callable(ep._build_metadata)

    def test_build_metadata_returns_locked_keys(self):
        meta = ep._build_metadata("single", None)
        assert set(meta.keys()) == {
            "created_at", "source", "evidence_dir", "engine_version",
        }

    def test_build_metadata_engine_version(self):
        meta = ep._build_metadata("batch", "/x/y")
        assert meta["engine_version"] == "elins-19"

    def test_build_metadata_passes_through_source(self):
        meta = ep._build_metadata("directory", "/x")
        assert meta["source"] == "directory"

    def test_build_metadata_passes_through_evidence_dir(self):
        meta = ep._build_metadata("directory", "/some/dir")
        assert meta["evidence_dir"] == "/some/dir"

    def test_validate_source_accepts_each_locked_value(self):
        for s in ("single", "batch", "directory"):
            ep._validate_source(s)  # should not raise
