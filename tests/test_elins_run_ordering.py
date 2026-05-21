"""
Tests for ELINS Unit 23 — time-aware drift ordering.

Layered coverage (>= 60 tests, target ~70):
    A. Core ordering — sort_run_ids_by_timestamp
    B. Validation
    C. Integration with drift / magnitude / severity / series wrappers
    D. Integration with summary_multi (output stays alphabetical by rid)
    E. Composite endpoint — uses timestamp order, filtering still works
    F. Source-code purity / module surface
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
import elins_run_ordering as ord_mod
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


def _write_legacy_file(runs_dir: Path, run_id: str, payload) -> None:
    """Unit 25: insert a legacy-shaped envelope (``metadata=None``)
    directly into the SQLite DB."""
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


class _StubDT:
    """Stand-in for ``datetime.datetime`` whose ``now()`` returns a
    canned ISO timestamp on each call. Used to inject distinct
    timestamps across saves so the ordering helper has unambiguous
    chronology to sort on (Windows clock resolution can otherwise tie
    every back-to-back save)."""
    def __init__(self, iso_values):
        self._iter = iter(iso_values)

    def now(self, tz=None):
        v = next(self._iter)

        class _T:
            def __init__(self, iso): self._iso = iso
            def isoformat(self): return self._iso
        return _T(v)


@pytest.fixture
def fixed_clock(monkeypatch):
    """Returns a callable: pass an iterable of ISO timestamps; the next
    N calls to ``ep.save_comparison_result`` will pull from that list.

    Unit 25: the actual ``datetime.now()`` site lives in
    ``elins_persistence_sqlite`` now that storage is SQLite-backed, so
    we monkeypatch that module's binding (the façade just re-exports)."""
    import elins_persistence_sqlite as _ep_sql
    def _install(values):
        monkeypatch.setattr(_ep_sql, "datetime", _StubDT(list(values)))
    return _install


# ===========================================================================
# A. Core ordering
# ===========================================================================
class TestCoreOrderingBasic:
    def test_returns_list(self):
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        out = ord_mod.sort_run_ids_by_timestamp(["a", "b"])
        assert isinstance(out, list)

    def test_empty_list_returns_empty(self):
        assert ord_mod.sort_run_ids_by_timestamp([]) == []

    def test_single_id_returns_unchanged(self):
        ep.save_comparison_result("solo", [_entry("p1")])
        assert ord_mod.sort_run_ids_by_timestamp(["solo"]) == ["solo"]

    def test_basic_timestamp_sort(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:01+00:00",  # zeta saved second-earliest
            "2026-05-12T10:00:00+00:00",  # alpha earliest
            "2026-05-12T10:00:02+00:00",  # mid latest
        ])
        ep.save_comparison_result("zeta",  [_entry("p1")])
        ep.save_comparison_result("alpha", [_entry("p1")])
        ep.save_comparison_result("mid",   [_entry("p1")])

        out = ord_mod.sort_run_ids_by_timestamp(["zeta", "alpha", "mid"])
        assert out == ["alpha", "zeta", "mid"]

    def test_reverse_input_sorts_to_canonical(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # a
            "2026-05-12T10:00:01+00:00",  # b
            "2026-05-12T10:00:02+00:00",  # c
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("c", [_entry("p1")])

        # Caller passes reverse-chronological → sorter rotates to ascending.
        assert ord_mod.sort_run_ids_by_timestamp(
            ["c", "b", "a"]) == ["a", "b", "c"]

    def test_already_sorted_input_unchanged(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
            "2026-05-12T10:00:02+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("c", [_entry("p1")])
        assert ord_mod.sort_run_ids_by_timestamp(
            ["a", "b", "c"]) == ["a", "b", "c"]

    def test_input_list_not_mutated(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])

        original = ["b", "a"]
        before = list(original)
        ord_mod.sort_run_ids_by_timestamp(original)
        assert original == before

    def test_repeated_calls_byte_equal(self):
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        first  = ord_mod.sort_run_ids_by_timestamp(["b", "a"])
        second = ord_mod.sort_run_ids_by_timestamp(["b", "a"])
        assert first == second

    def test_distinct_timestamps_strict_order(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T11:00:00+00:00",
            "2026-05-12T12:00:00+00:00",
            "2026-05-12T13:00:00+00:00",
        ])
        for rid in ("d", "c", "b", "a"):
            ep.save_comparison_result(rid, [_entry("p1")])
        out = ord_mod.sort_run_ids_by_timestamp(["a", "b", "c", "d"])
        assert out == ["d", "c", "b", "a"]


class TestCoreOrderingTies:
    def test_ties_broken_alphabetically(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # all three identical
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:00+00:00",
        ])
        ep.save_comparison_result("zeta",  [_entry("p1")])
        ep.save_comparison_result("apple", [_entry("p1")])
        ep.save_comparison_result("mid",   [_entry("p1")])

        out = ord_mod.sort_run_ids_by_timestamp(["zeta", "apple", "mid"])
        assert out == ["apple", "mid", "zeta"]

    def test_partial_ties(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # a   (early)
            "2026-05-12T10:00:00+00:00",  # b   (early, same as a)
            "2026-05-12T10:00:01+00:00",  # c   (later)
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("c", [_entry("p1")])

        out = ord_mod.sort_run_ids_by_timestamp(["c", "a", "b"])
        # Within the tied early bucket, alphabetical → a, b. Then c.
        assert out == ["a", "b", "c"]

    def test_all_identical_timestamps_pure_alphabetical(self, fixed_clock):
        fixed_clock(["2026-05-12T10:00:00+00:00"] * 4)
        for rid in ("d", "c", "b", "a"):
            ep.save_comparison_result(rid, [_entry("p1")])
        out = ord_mod.sort_run_ids_by_timestamp(["d", "c", "b", "a"])
        assert out == ["a", "b", "c", "d"]


class TestCoreOrderingLegacy:
    def test_legacy_run_sorts_last(self, _runs_dir_isolation):
        ep.save_comparison_result("new", [_entry("p1")])
        _write_legacy_file(_runs_dir_isolation, "old", [_entry("p1")])
        out = ord_mod.sort_run_ids_by_timestamp(["old", "new"])
        assert out == ["new", "old"]

    def test_two_legacy_runs_alphabetical(self, _runs_dir_isolation):
        _write_legacy_file(_runs_dir_isolation, "z_old", [_entry("p1")])
        _write_legacy_file(_runs_dir_isolation, "a_old", [_entry("p1")])
        out = ord_mod.sort_run_ids_by_timestamp(["z_old", "a_old"])
        assert out == ["a_old", "z_old"]

    def test_all_legacy_runs(self, _runs_dir_isolation):
        for rid in ("c", "a", "b"):
            _write_legacy_file(_runs_dir_isolation, rid, [_entry("p1")])
        out = ord_mod.sort_run_ids_by_timestamp(["c", "a", "b"])
        assert out == ["a", "b", "c"]

    def test_mixed_legacy_and_new(
        self, _runs_dir_isolation, fixed_clock,
    ):
        fixed_clock([
            "2026-05-12T10:00:01+00:00",
            "2026-05-12T10:00:00+00:00",
        ])
        _write_legacy_file(_runs_dir_isolation, "leg", [_entry("p1")])
        ep.save_comparison_result("new_b", [_entry("p1")])
        ep.save_comparison_result("new_a", [_entry("p1")])

        out = ord_mod.sort_run_ids_by_timestamp(["leg", "new_b", "new_a"])
        # new_a (10:00:00) → new_b (10:00:01) → leg (legacy last)
        assert out == ["new_a", "new_b", "leg"]


# ===========================================================================
# B. Validation
# ===========================================================================
class TestValidation:
    def test_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            ord_mod.sort_run_ids_by_timestamp("nope")  # type: ignore[arg-type]

    def test_dict_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            ord_mod.sort_run_ids_by_timestamp({"a": 1})  # type: ignore[arg-type]

    def test_none_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            ord_mod.sort_run_ids_by_timestamp(None)  # type: ignore[arg-type]

    def test_malformed_id_raises_before_load(self):
        # Even with one valid id stored, a malformed id in the list
        # raises BEFORE any load happens.
        ep.save_comparison_result("good", [_entry("p1")])
        with pytest.raises(ValueError):
            ord_mod.sort_run_ids_by_timestamp(["good", "bad/id"])

    def test_missing_run_raises_filenotfound(self):
        with pytest.raises(FileNotFoundError):
            ord_mod.sort_run_ids_by_timestamp(["ghost"])

    def test_validates_all_ids_before_loading(self, monkeypatch):
        ep.save_comparison_result("good", [_entry("p1")])
        called = {"count": 0}
        original = ep.load_comparison_result

        def _spy(rid):
            called["count"] += 1
            return original(rid)

        monkeypatch.setattr(ord_mod, "load_comparison_result", _spy)
        with pytest.raises(ValueError):
            ord_mod.sort_run_ids_by_timestamp(["good", "bad$id"])
        assert called["count"] == 0


# ===========================================================================
# C. Integration with multi-run analytic wrappers
# ===========================================================================
class TestDriftWrapperOrdering:
    def test_drift_uses_timestamp_order(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # b_early
            "2026-05-12T10:00:01+00:00",  # a_late
        ])
        ep.save_comparison_result("b_early", [_entry("p1", sp=2)])
        ep.save_comparison_result("a_late",  [_entry("p1", sp=9)])
        # Caller order is alphabetical; chronological order is reverse.
        out = drift_mod.detect_drift_for_run_ids(["a_late", "b_early"])
        # b_early (sp=2) → a_late (sp=9) is trending_up.
        assert out["trending_up"] == ["p1"]

    def test_drift_caller_order_ignored(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
            "2026-05-12T10:00:02+00:00",
        ])
        ep.save_comparison_result("first",  [_entry("p1", sp=2)])
        ep.save_comparison_result("second", [_entry("p1", sp=5)])
        ep.save_comparison_result("third",  [_entry("p1", sp=9)])
        a = drift_mod.detect_drift_for_run_ids(
            ["first", "second", "third"])
        b = drift_mod.detect_drift_for_run_ids(
            ["third", "first", "second"])
        c = drift_mod.detect_drift_for_run_ids(
            ["second", "third", "first"])
        assert a == b == c


class TestMagnitudeWrapperOrdering:
    def test_magnitude_caller_order_ignored(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("first",  [_entry("p1", sp=2)])
        ep.save_comparison_result("second", [_entry("p1", sp=9)])
        a = mag_mod.drift_magnitude_for_run_ids(["first", "second"])
        b = mag_mod.drift_magnitude_for_run_ids(["second", "first"])
        assert a == b

    def test_magnitude_max_swing_uses_chronology(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
            "2026-05-12T10:00:02+00:00",
        ])
        ep.save_comparison_result("t1", [_entry("p1", sp=5)])
        ep.save_comparison_result("t2", [_entry("p1", sp=9)])
        ep.save_comparison_result("t3", [_entry("p1", sp=1)])
        out = mag_mod.drift_magnitude_for_run_ids(["t3", "t1", "t2"])
        # Chronological: 5 → 9 → 1; max_swing single_party = 8 (9→1)
        assert out["p1"]["single_party"]["max_swing"] == 8


class TestSeverityWrapperOrdering:
    def test_severity_caller_order_ignored(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("first",  [_entry("p1", sp=2)])
        ep.save_comparison_result("second", [_entry("p1", sp=9)])
        a = sev_mod.classify_drift_severity_for_run_ids(["first", "second"])
        b = sev_mod.classify_drift_severity_for_run_ids(["second", "first"])
        assert a == b

    def test_severity_direction_uses_chronology(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # b_late_alpha = early
            "2026-05-12T10:00:01+00:00",  # a_late = late
        ])
        ep.save_comparison_result("b_late_alpha", [_entry("p1", sp=2)])
        ep.save_comparison_result("a_late",       [_entry("p1", sp=9)])
        out = sev_mod.classify_drift_severity_for_run_ids(
            ["a_late", "b_late_alpha"])
        # b_late_alpha is chronologically first (sp=2) → a_late (sp=9)
        # → trending_up.
        assert out["p1"]["direction"] == "trending_up"


class TestSeriesWrapperOrdering:
    def test_series_caller_order_ignored(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
            "2026-05-12T10:00:02+00:00",
        ])
        ep.save_comparison_result("morning", [_entry("p1", sp=2)])
        ep.save_comparison_result("noon",    [_entry("p1", sp=5)])
        ep.save_comparison_result("evening", [_entry("p1", sp=9)])
        a = series_mod.drift_series_for_run_ids(
            ["morning", "noon", "evening"])
        b = series_mod.drift_series_for_run_ids(
            ["evening", "noon", "morning"])
        assert a == b
        assert a["p1"]["single_party_scores"] == [2, 5, 9]

    def test_series_byte_equal_to_manually_sorted(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("first",  [_entry("p1", sp=2)])
        ep.save_comparison_result("second", [_entry("p1", sp=9)])
        # Pre-sorted by hand vs. wrapper-sorted should match.
        sorted_call = series_mod.drift_series_for_run_ids(
            ["first", "second"])
        unsorted_call = series_mod.drift_series_for_run_ids(
            ["second", "first"])
        assert sorted_call == unsorted_call


# ===========================================================================
# D. Integration with summary_multi
# ===========================================================================
class TestSummaryMultiOrdering:
    def test_summary_caller_order_ignored(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("first",  [_entry("p1")])
        ep.save_comparison_result("second", [_entry("p1")])
        a = multi_mod.summary_across_run_ids(["first", "second"])
        b = multi_mod.summary_across_run_ids(["second", "first"])
        assert a == b

    def test_summary_output_keys_remain_alphabetical(self, fixed_clock):
        """Unit 18 sorts its OUTPUT 'runs' dict alphabetically by rid;
        Unit 23 only changes the internal load order, so the visible
        key order in the response is unaffected."""
        fixed_clock([
            "2026-05-12T10:00:01+00:00",  # zeta first chronologically...
            "2026-05-12T10:00:02+00:00",
        ])
        ep.save_comparison_result("zeta",  [_entry("p1")])
        ep.save_comparison_result("alpha", [_entry("p1")])
        out = multi_mod.summary_across_run_ids(["zeta", "alpha"])
        # ...but the response keys still come back alphabetical.
        assert list(out["runs"].keys()) == ["alpha", "zeta"]


# ===========================================================================
# E. Composite endpoint integration
# ===========================================================================
class TestCompositeOrdering:
    _PATH = "/elins/regression/run/composite"

    def test_composite_run_ids_field_reflects_timestamp_order(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # b_early
            "2026-05-12T10:00:01+00:00",  # a_late
        ])
        ep.save_comparison_result("b_early", [_entry("p1", sp=2)])
        ep.save_comparison_result("a_late",  [_entry("p1", sp=9)])
        body = client.post(
            self._PATH,
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert body["run_ids"] == ["b_early", "a_late"]

    def test_composite_metadata_aligned_with_sorted_run_ids(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # b_early
            "2026-05-12T10:00:01+00:00",  # a_late
        ])
        ep.save_comparison_result("b_early", [_entry("p1")], source="single")
        ep.save_comparison_result("a_late",  [_entry("p1")], source="batch")
        body = client.post(
            self._PATH,
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert body["metadata"][0]["source"] == "single"  # b_early
        assert body["metadata"][1]["source"] == "batch"   # a_late

    def test_composite_series_uses_chronology(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # b_early sp=2
            "2026-05-12T10:00:01+00:00",  # a_late sp=9
        ])
        ep.save_comparison_result("b_early", [_entry("p1", sp=2)])
        ep.save_comparison_result("a_late",  [_entry("p1", sp=9)])
        body = client.post(
            self._PATH,
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert body["series"]["p1"]["single_party_scores"] == [2, 9]

    def test_composite_filtering_still_applies_after_ordering(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("first",
                                   [_entry("alpha", sp=2),
                                    _entry("beta", sp=2)])
        ep.save_comparison_result("second",
                                   [_entry("alpha", sp=9),
                                    _entry("beta", sp=9)])
        body = client.post(
            self._PATH + "?pair_id_prefix=alp",
            json={"run_ids": ["second", "first"]}, headers=_auth(sid),
        ).json()
        # Filtering reduces to alpha; chronology gives series [2, 9].
        assert set(body["series"].keys()) == {"alpha"}
        assert body["series"]["alpha"]["single_party_scores"] == [2, 9]

    def test_composite_caller_order_ignored_byte_equal(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
            "2026-05-12T10:00:02+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1", sp=2)])
        ep.save_comparison_result("b", [_entry("p1", sp=5)])
        ep.save_comparison_result("c", [_entry("p1", sp=9)])
        forward = client.post(
            self._PATH,
            json={"run_ids": ["a", "b", "c"]}, headers=_auth(sid),
        ).json()
        shuffled = client.post(
            self._PATH,
            json={"run_ids": ["c", "a", "b"]}, headers=_auth(sid),
        ).json()
        assert forward == shuffled


# ===========================================================================
# F. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_sort_run_ids_by_timestamp_callable(self):
        assert callable(ord_mod.sort_run_ids_by_timestamp)

    def test_bucket_constants_locked(self):
        assert ord_mod._SORT_BUCKET_TIMESTAMPED == 0
        assert ord_mod._SORT_BUCKET_LEGACY == 1


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(ord_mod)

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
                          "import requests", "import socket"):
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

    def test_no_analytic_imports(self):
        """Ordering helper must not depend on the analytic modules
        themselves — that would create a circular import. It only
        depends on persistence."""
        src = self._code_only()
        for forbidden in (
            "elins_run_diff", "elins_run_drift",
            "elins_run_summary", "elins_run_composite",
        ):
            assert forbidden not in src


# ===========================================================================
# G. Additional core edge cases
# ===========================================================================
class TestCoreOrderingEdgeCases:
    def test_two_runs_distinct_timestamps_input_order_a_b(
        self, fixed_clock,
    ):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        assert ord_mod.sort_run_ids_by_timestamp(["a", "b"]) == ["a", "b"]

    def test_two_runs_distinct_timestamps_input_order_b_a(
        self, fixed_clock,
    ):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        assert ord_mod.sort_run_ids_by_timestamp(["b", "a"]) == ["a", "b"]

    def test_seven_runs_random_order(self, fixed_clock):
        # Save in alphabetical order with strictly-ascending timestamps
        # so that timestamp order == alphabetical for unambiguous testing.
        fixed_clock([
            f"2026-05-12T10:00:0{i}+00:00" for i in range(7)
        ])
        for rid in ("a", "b", "c", "d", "e", "f", "g"):
            ep.save_comparison_result(rid, [_entry("p1")])
        # Caller passes a deliberately scrambled order.
        scrambled = ["e", "a", "g", "c", "b", "f", "d"]
        assert ord_mod.sort_run_ids_by_timestamp(scrambled) == [
            "a", "b", "c", "d", "e", "f", "g",
        ]

    def test_iso_timestamps_with_microseconds(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00.000001+00:00",
            "2026-05-12T10:00:00.000002+00:00",
        ])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("a", [_entry("p1")])
        # b has earlier ts.
        assert ord_mod.sort_run_ids_by_timestamp(["a", "b"]) == ["b", "a"]

    def test_iso_timestamps_across_dates(self, fixed_clock):
        fixed_clock([
            "2026-05-13T00:00:00+00:00",  # one day later
            "2026-05-12T23:59:59+00:00",
        ])
        ep.save_comparison_result("late",  [_entry("p1")])
        ep.save_comparison_result("early", [_entry("p1")])
        assert ord_mod.sort_run_ids_by_timestamp(
            ["late", "early"]) == ["early", "late"]

    def test_overwritten_run_uses_latest_timestamp(self, fixed_clock):
        """Saving the same run_id twice updates created_at; ordering
        respects the LATEST save's timestamp."""
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # a (early)
            "2026-05-12T10:00:01+00:00",  # b (slightly later)
            "2026-05-12T10:00:05+00:00",  # a re-saved (now latest)
        ])
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        ep.save_comparison_result("a", [_entry("p1")])  # overwrite
        out = ord_mod.sort_run_ids_by_timestamp(["a", "b"])
        # a now has the latest ts → sorts last.
        assert out == ["b", "a"]

    def test_returns_strings_not_objects(self, fixed_clock):
        fixed_clock(["2026-05-12T10:00:00+00:00"])
        ep.save_comparison_result("solo", [_entry("p1")])
        out = ord_mod.sort_run_ids_by_timestamp(["solo"])
        assert all(isinstance(rid, str) for rid in out)

    def test_output_length_matches_input_length(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
            "2026-05-12T10:00:02+00:00",
        ])
        for rid in ("a", "b", "c"):
            ep.save_comparison_result(rid, [_entry("p1")])
        assert len(ord_mod.sort_run_ids_by_timestamp(["c", "a", "b"])) == 3


# ===========================================================================
# H. Endpoint-level ordering checks (each multi-run endpoint)
# ===========================================================================
class TestEndpointOrdering:
    def _setup_two_distinct(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",  # b_early sp=2
            "2026-05-12T10:00:01+00:00",  # a_late sp=9
        ])
        ep.save_comparison_result("b_early", [_entry("p1", sp=2)])
        ep.save_comparison_result("a_late",  [_entry("p1", sp=9)])

    def test_drift_endpoint_caller_order_ignored(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup_two_distinct(fixed_clock)
        forward = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["b_early", "a_late"]}, headers=_auth(sid),
        ).json()
        reverse = client.post(
            "/elins/regression/drift",
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert forward == reverse
        assert forward["trending_up"] == ["p1"]

    def test_magnitude_endpoint_caller_order_ignored(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup_two_distinct(fixed_clock)
        forward = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["b_early", "a_late"]}, headers=_auth(sid),
        ).json()
        reverse = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert forward == reverse

    def test_severity_endpoint_caller_order_ignored(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup_two_distinct(fixed_clock)
        forward = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["b_early", "a_late"]}, headers=_auth(sid),
        ).json()
        reverse = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert forward == reverse

    def test_series_endpoint_caller_order_ignored(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup_two_distinct(fixed_clock)
        forward = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["b_early", "a_late"]}, headers=_auth(sid),
        ).json()
        reverse = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert forward == reverse
        assert forward["p1"]["single_party_scores"] == [2, 9]

    def test_summary_multi_endpoint_caller_order_ignored(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup_two_distinct(fixed_clock)
        forward = client.post(
            "/elins/regression/runs/summary",
            json={"run_ids": ["b_early", "a_late"]}, headers=_auth(sid),
        ).json()
        reverse = client.post(
            "/elins/regression/runs/summary",
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert forward == reverse

    def test_composite_endpoint_caller_order_ignored(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup_two_distinct(fixed_clock)
        forward = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["b_early", "a_late"]}, headers=_auth(sid),
        ).json()
        reverse = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["a_late", "b_early"]}, headers=_auth(sid),
        ).json()
        assert forward == reverse


# ===========================================================================
# I. Cross-endpoint chronology parity
# ===========================================================================
class TestCrossEndpointChronologyParity:
    """The same chronological assumption holds across every multi-run
    endpoint — they all see the same sorted run_id sequence."""

    def _setup(self, fixed_clock):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
            "2026-05-12T10:00:02+00:00",
        ])
        ep.save_comparison_result(
            "z_old",   [_entry("p1", sp=2)],          # earliest
        )
        ep.save_comparison_result(
            "a_mid",   [_entry("p1", sp=5)],
        )
        ep.save_comparison_result(
            "m_late",  [_entry("p1", sp=9)],
        )

    def test_drift_and_composite_agree_on_direction(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup(fixed_clock)
        scrambled = ["a_mid", "m_late", "z_old"]
        d = client.post(
            "/elins/regression/drift",
            json={"run_ids": scrambled}, headers=_auth(sid),
        ).json()
        c = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": scrambled}, headers=_auth(sid),
        ).json()
        assert d["trending_up"] == c["direction"]["trending_up"]

    def test_series_and_composite_agree_on_series(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup(fixed_clock)
        scrambled = ["m_late", "z_old", "a_mid"]
        s = client.post(
            "/elins/regression/drift/series",
            json={"run_ids": scrambled}, headers=_auth(sid),
        ).json()
        c = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": scrambled}, headers=_auth(sid),
        ).json()
        assert s == c["series"]
        assert s["p1"]["single_party_scores"] == [2, 5, 9]

    def test_magnitude_and_composite_agree(
        self, client, app_module, fixed_clock,
    ):
        sid = _make_user_session(app_module)
        self._setup(fixed_clock)
        m = client.post(
            "/elins/regression/drift/magnitude",
            json={"run_ids": ["m_late", "a_mid", "z_old"]},
            headers=_auth(sid),
        ).json()
        c = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["m_late", "a_mid", "z_old"]},
            headers=_auth(sid),
        ).json()
        assert m == c["magnitude"]


# ===========================================================================
# J. Legacy-aware integration
# ===========================================================================
class TestLegacyIntegration:
    def test_legacy_run_appears_last_in_series(
        self, fixed_clock, _runs_dir_isolation,
    ):
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("a_new", [_entry("p1", sp=5)])
        ep.save_comparison_result("b_new", [_entry("p1", sp=8)])
        _write_legacy_file(_runs_dir_isolation, "leg",
                           [_entry("p1", sp=99)])
        out = series_mod.drift_series_for_run_ids(
            ["leg", "a_new", "b_new"])
        # Sorted: [a_new, b_new, leg]; series reflects that.
        assert out["p1"]["single_party_scores"] == [5, 8, 99]

    def test_legacy_run_in_composite_metadata_aligned(
        self, client, app_module, fixed_clock, _runs_dir_isolation,
    ):
        sid = _make_user_session(app_module)
        fixed_clock([
            "2026-05-12T10:00:00+00:00",
            "2026-05-12T10:00:01+00:00",
        ])
        ep.save_comparison_result("aaa_new", [_entry("p1", sp=5)],
                                   source="single")
        ep.save_comparison_result("bbb_new", [_entry("p1", sp=8)],
                                   source="batch")
        _write_legacy_file(_runs_dir_isolation, "ccc_leg",
                           [_entry("p1", sp=99)])
        body = client.post(
            "/elins/regression/run/composite",
            json={"run_ids": ["ccc_leg", "bbb_new", "aaa_new"]},
            headers=_auth(sid),
        ).json()
        assert body["run_ids"] == ["aaa_new", "bbb_new", "ccc_leg"]
        assert body["metadata"][0]["source"] == "single"
        assert body["metadata"][1]["source"] == "batch"
        assert body["metadata"][2] is None
