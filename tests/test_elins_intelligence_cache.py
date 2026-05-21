"""
Tests for ELINS2 Unit 11 — intelligence payload cache.

Layered coverage (>= 40 tests, target ~50):
    A. Hash stability + order-sensitivity
    B. store / get round-trip
    C. TTL expiry
    D. Invalidation
    E. Empty / small N cache
    F. Schema migration (intelligence_cache table exists)
    G. Unit 9 integration — cache hit short-circuits compute
    H. Validation
    I. Determinism
    J. Source-code purity / module surface
"""
from __future__ import annotations

import inspect
import sqlite3
import time
from pathlib import Path

import pytest

import elins_intelligence as intel_mod
import elins_intelligence_cache as cache_mod
import elins_persistence as ep
import elins_persistence_sqlite as ep_sql


# ===========================================================================
# Fixtures
# ===========================================================================
@pytest.fixture(autouse=True)
def _runs_dir_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    runs_dir = tmp_path / "elins_runs"
    monkeypatch.setenv(ep._RUNS_DIR_ENV_VAR, str(runs_dir))
    yield runs_dir


def _entry(pid="p1", *, sp=5, ec=5,
           sp_band="Acceptable", ec_band="Acceptable") -> dict:
    return {
        "pair_id": pid,
        "single_party_score": sp,
        "economic_coercion_score": ec,
        "single_party_band": sp_band,
        "economic_coercion_band": ec_band,
    }


def _seed_runs(prefix="s", n=3, sp=5, ec=5):
    rids: list = []
    for i in range(n):
        rid = f"{prefix}_{i:02d}"
        ep.save_comparison_result(rid, [_entry("p1", sp=sp, ec=ec),
                                          _entry("p2", sp=sp, ec=ec)])
        rids.append(rid)
    return rids


def _db_path(runs_dir: Path) -> Path:
    return runs_dir / ep._DB_FILENAME


# ===========================================================================
# A. Hash stability + order-sensitivity
# ===========================================================================
class TestRunSetHash:
    def test_same_list_same_hash(self):
        assert cache_mod._run_set_hash(["a", "b"]) == \
               cache_mod._run_set_hash(["a", "b"])

    def test_different_order_different_hash(self):
        assert cache_mod._run_set_hash(["a", "b"]) != \
               cache_mod._run_set_hash(["b", "a"])

    def test_empty_list_has_a_hash(self):
        h = cache_mod._run_set_hash([])
        assert isinstance(h, str)
        assert len(h) == 64  # SHA-256 hex digest length

    def test_hash_is_hex_string(self):
        h = cache_mod._run_set_hash(["x_01", "x_02"])
        assert all(c in "0123456789abcdef" for c in h)

    def test_single_element_differs_from_two(self):
        assert cache_mod._run_set_hash(["a"]) != \
               cache_mod._run_set_hash(["a", "a"])


# ===========================================================================
# B. store / get round-trip
# ===========================================================================
class TestStoreGet:
    def test_get_before_store_returns_none(self):
        _seed_runs(n=2)
        assert cache_mod.get_cached_intelligence(["s_00", "s_01"]) is None

    def test_store_then_get_round_trips(self, _runs_dir_isolation):
        _seed_runs(n=2)
        payload = {"foo": "bar", "nested": {"k": 1}}
        cache_mod.store_intelligence(
            ["s_00", "s_01"], payload, ttl_seconds=60,
        )
        out = cache_mod.get_cached_intelligence(["s_00", "s_01"])
        assert out == payload

    def test_store_replaces_existing(self):
        _seed_runs(n=2)
        cache_mod.store_intelligence(["s_00", "s_01"], {"v": 1}, 60)
        cache_mod.store_intelligence(["s_00", "s_01"], {"v": 2}, 60)
        assert cache_mod.get_cached_intelligence(
            ["s_00", "s_01"],
        ) == {"v": 2}

    def test_distinct_run_ids_have_distinct_entries(self):
        _seed_runs(prefix="a", n=2)
        _seed_runs(prefix="b", n=2)
        cache_mod.store_intelligence(["a_00", "a_01"], {"v": "A"}, 60)
        cache_mod.store_intelligence(["b_00", "b_01"], {"v": "B"}, 60)
        assert cache_mod.get_cached_intelligence(
            ["a_00", "a_01"],
        ) == {"v": "A"}
        assert cache_mod.get_cached_intelligence(
            ["b_00", "b_01"],
        ) == {"v": "B"}

    def test_different_order_cached_separately(self):
        _seed_runs(prefix="o", n=2)
        cache_mod.store_intelligence(["o_00", "o_01"], {"v": 1}, 60)
        cache_mod.store_intelligence(["o_01", "o_00"], {"v": 2}, 60)
        assert cache_mod.get_cached_intelligence(
            ["o_00", "o_01"],
        ) == {"v": 1}
        assert cache_mod.get_cached_intelligence(
            ["o_01", "o_00"],
        ) == {"v": 2}

    def test_payload_preserves_lists(self):
        _seed_runs(prefix="lst", n=1)
        payload = {"items": [1, 2, 3], "nested": [[1, 2], [3, 4]]}
        cache_mod.store_intelligence(["lst_00"], payload, 60)
        out = cache_mod.get_cached_intelligence(["lst_00"])
        assert out == payload

    def test_payload_preserves_floats(self):
        _seed_runs(prefix="fl", n=1)
        payload = {"a": 0.123456789, "b": 1e-10, "c": -3.14}
        cache_mod.store_intelligence(["fl_00"], payload, 60)
        out = cache_mod.get_cached_intelligence(["fl_00"])
        assert out == payload

    def test_empty_run_ids_cacheable(self):
        cache_mod.store_intelligence([], {"empty": True}, 60)
        assert cache_mod.get_cached_intelligence([]) == {"empty": True}


# ===========================================================================
# C. TTL expiry
# ===========================================================================
class TestTTLExpiry:
    def test_within_ttl_returns_payload(self):
        _seed_runs(prefix="ttl", n=1)
        cache_mod.store_intelligence(["ttl_00"], {"v": 1}, ttl_seconds=60)
        assert cache_mod.get_cached_intelligence(["ttl_00"]) == {"v": 1}

    def test_expired_row_returns_none(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        _seed_runs(prefix="exp", n=1)
        cache_mod.store_intelligence(["exp_00"], {"v": 1}, ttl_seconds=1)
        # Advance the clock used by ``get_cached_intelligence``: shift
        # by 10s, well past the 1-second TTL.
        from datetime import datetime, timezone, timedelta
        real_now = datetime.now(timezone.utc)
        future = real_now + timedelta(seconds=10)

        class _StubDT:
            @staticmethod
            def now(tz=None):
                return future if tz else future.replace(tzinfo=None)

            fromisoformat = staticmethod(datetime.fromisoformat)

        monkeypatch.setattr(cache_mod, "datetime", _StubDT)
        assert cache_mod.get_cached_intelligence(["exp_00"]) is None

    def test_expired_row_deleted_from_table(
        self, _runs_dir_isolation, monkeypatch: pytest.MonkeyPatch,
    ):
        _seed_runs(prefix="del", n=1)
        cache_mod.store_intelligence(["del_00"], {"v": 1}, ttl_seconds=1)

        from datetime import datetime, timezone, timedelta
        real_now = datetime.now(timezone.utc)
        future = real_now + timedelta(seconds=10)

        class _StubDT:
            @staticmethod
            def now(tz=None):
                return future if tz else future.replace(tzinfo=None)

            fromisoformat = staticmethod(datetime.fromisoformat)

        monkeypatch.setattr(cache_mod, "datetime", _StubDT)
        cache_mod.get_cached_intelligence(["del_00"])

        # Verify the row is gone.
        db = _db_path(_runs_dir_isolation)
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT * FROM intelligence_cache WHERE run_set_hash = ?",
                (cache_mod._run_set_hash(["del_00"]),),
            ).fetchone()
        finally:
            conn.close()
        assert row is None

    def test_ttl_zero_rejected(self):
        with pytest.raises(ValueError, match=">= 1"):
            cache_mod.store_intelligence(["x"], {}, ttl_seconds=0)

    def test_ttl_negative_rejected(self):
        with pytest.raises(ValueError, match=">= 1"):
            cache_mod.store_intelligence(["x"], {}, ttl_seconds=-30)

    def test_ttl_bool_rejected(self):
        with pytest.raises(ValueError, match="positive int"):
            cache_mod.store_intelligence(["x"], {}, ttl_seconds=True)

    def test_ttl_float_rejected(self):
        with pytest.raises(ValueError, match="positive int"):
            cache_mod.store_intelligence(["x"], {}, ttl_seconds=60.5)

    def test_corrupt_timestamp_treated_as_expired(
        self, _runs_dir_isolation,
    ):
        """A row with a malformed ``created_at`` field is purged on
        read and reported as a miss."""
        _seed_runs(prefix="cor", n=1)
        cache_mod.store_intelligence(["cor_00"], {"v": 1}, 60)
        # Hand-edit the row to corrupt the timestamp.
        db = _db_path(_runs_dir_isolation)
        conn = sqlite3.connect(str(db))
        try:
            conn.execute(
                "UPDATE intelligence_cache "
                "SET created_at = 'not-an-iso-string' WHERE run_set_hash = ?",
                (cache_mod._run_set_hash(["cor_00"]),),
            )
            conn.commit()
        finally:
            conn.close()
        assert cache_mod.get_cached_intelligence(["cor_00"]) is None


# ===========================================================================
# D. Invalidation
# ===========================================================================
class TestInvalidation:
    def test_invalidate_removes_entry(self):
        _seed_runs(prefix="inv", n=1)
        cache_mod.store_intelligence(["inv_00"], {"v": 1}, 60)
        cache_mod.invalidate_intelligence(["inv_00"])
        assert cache_mod.get_cached_intelligence(["inv_00"]) is None

    def test_invalidate_missing_entry_no_error(self):
        # No row → invalidate is a no-op.
        cache_mod.invalidate_intelligence(["never_stored"])

    def test_invalidate_one_does_not_affect_others(self):
        _seed_runs(prefix="ix", n=2)
        cache_mod.store_intelligence(["ix_00"], {"v": "a"}, 60)
        cache_mod.store_intelligence(["ix_01"], {"v": "b"}, 60)
        cache_mod.invalidate_intelligence(["ix_00"])
        assert cache_mod.get_cached_intelligence(["ix_00"]) is None
        assert cache_mod.get_cached_intelligence(["ix_01"]) == {"v": "b"}

    def test_invalidate_idempotent(self):
        cache_mod.invalidate_intelligence(["x_y"])
        cache_mod.invalidate_intelligence(["x_y"])  # Second call: still no-op


# ===========================================================================
# E. Empty / small N cache
# ===========================================================================
class TestEmptyAndSmallN:
    def test_empty_list_misses_initially(self):
        assert cache_mod.get_cached_intelligence([]) is None

    def test_single_run_round_trip(self):
        _seed_runs(prefix="sg", n=1)
        cache_mod.store_intelligence(["sg_00"], {"v": "x"}, 60)
        assert cache_mod.get_cached_intelligence(["sg_00"]) == {"v": "x"}


# ===========================================================================
# F. Schema migration (intelligence_cache table exists)
# ===========================================================================
class TestSchemaMigration:
    def test_intelligence_cache_table_exists(self, _runs_dir_isolation):
        _seed_runs(prefix="sch", n=1)
        # Triggers _ensure_init which creates the table.
        db = _db_path(_runs_dir_isolation)
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='intelligence_cache'",
            ).fetchone()
        finally:
            conn.close()
        assert row is not None

    def test_intelligence_cache_columns_locked(self, _runs_dir_isolation):
        _seed_runs(prefix="col", n=1)
        db = _db_path(_runs_dir_isolation)
        conn = sqlite3.connect(str(db))
        try:
            cols = {
                row[1] for row in conn.execute(
                    "PRAGMA table_info(intelligence_cache)",
                )
            }
        finally:
            conn.close()
        assert cols == {
            "run_set_hash", "run_ids", "payload",
            "created_at", "ttl_seconds",
        }

    def test_intelligence_cache_hash_is_pk(self, _runs_dir_isolation):
        _seed_runs(prefix="pk", n=1)
        db = _db_path(_runs_dir_isolation)
        conn = sqlite3.connect(str(db))
        try:
            pk_cols = [
                row[1] for row in conn.execute(
                    "PRAGMA table_info(intelligence_cache)",
                )
                if row[5] >= 1  # pk-position column
            ]
        finally:
            conn.close()
        assert pk_cols == ["run_set_hash"]


# ===========================================================================
# G. Unit 9 integration — cache hit short-circuits compute
# ===========================================================================
class TestUnit9Integration:
    def test_repeat_call_returns_equal_payload(self):
        rids = _seed_runs(prefix="r9", n=3)
        a = intel_mod.intelligence_for_run_ids(rids)
        b = intel_mod.intelligence_for_run_ids(rids)
        assert a == b

    def test_cache_populated_after_first_call(self, _runs_dir_isolation):
        rids = _seed_runs(prefix="pop", n=3)
        intel_mod.intelligence_for_run_ids(rids)
        cached = cache_mod.get_cached_intelligence(rids)
        assert cached is not None
        assert cached["run_ids"] == rids

    def test_second_call_does_not_recompute(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        """Wrap each sub-section builder in a spy. After the first
        call the cache is hot, so the second call must hit zero
        builders — proving Unit 9 short-circuits to cache."""
        rids = _seed_runs(prefix="spy", n=3)
        # Prime the cache.
        intel_mod.intelligence_for_run_ids(rids)
        # Now install a sentinel — any subsequent compute call would
        # crash the test.
        call_count = {"n": 0}
        real_builder = intel_mod._build_similarity_section

        def spy(*args, **kwargs):
            call_count["n"] += 1
            return real_builder(*args, **kwargs)

        monkeypatch.setattr(
            intel_mod, "_build_similarity_section", spy,
        )
        out = intel_mod.intelligence_for_run_ids(rids)
        assert call_count["n"] == 0
        assert out["run_ids"] == rids

    def test_cache_invalidation_forces_recompute(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        rids = _seed_runs(prefix="ic", n=3)
        intel_mod.intelligence_for_run_ids(rids)
        cache_mod.invalidate_intelligence(rids)

        call_count = {"n": 0}
        real_builder = intel_mod._build_similarity_section

        def spy(*args, **kwargs):
            call_count["n"] += 1
            return real_builder(*args, **kwargs)

        monkeypatch.setattr(
            intel_mod, "_build_similarity_section", spy,
        )
        intel_mod.intelligence_for_run_ids(rids)
        assert call_count["n"] == 1

    def test_cache_disabled_bypasses_lookup(
        self, monkeypatch: pytest.MonkeyPatch,
    ):
        rids = _seed_runs(prefix="off", n=3)
        intel_mod.intelligence_for_run_ids(rids)  # populates cache

        monkeypatch.setattr(intel_mod, "_CACHE_ENABLED", False)
        call_count = {"n": 0}
        real_builder = intel_mod._build_similarity_section

        def spy(*args, **kwargs):
            call_count["n"] += 1
            return real_builder(*args, **kwargs)

        monkeypatch.setattr(
            intel_mod, "_build_similarity_section", spy,
        )
        intel_mod.intelligence_for_run_ids(rids)
        assert call_count["n"] == 1  # cache lookup skipped


# ===========================================================================
# H. Validation
# ===========================================================================
class TestValidation:
    def test_get_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            cache_mod.get_cached_intelligence("not-a-list")

    def test_store_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            cache_mod.store_intelligence("not-a-list", {}, 60)

    def test_invalidate_non_list_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            cache_mod.invalidate_intelligence("not-a-list")

    def test_store_non_dict_payload_raises(self):
        with pytest.raises(ValueError, match="payload"):
            cache_mod.store_intelligence(["x"], "not-a-dict", 60)

    def test_store_malformed_run_id_raises(self):
        with pytest.raises(ValueError):
            cache_mod.store_intelligence(["bad/id"], {}, 60)

    def test_get_malformed_run_id_raises(self):
        with pytest.raises(ValueError):
            cache_mod.get_cached_intelligence(["bad/id"])


# ===========================================================================
# I. Determinism
# ===========================================================================
class TestDeterminism:
    def test_hash_deterministic(self):
        rids = ["a_01", "a_02", "a_03"]
        assert cache_mod._run_set_hash(rids) == \
               cache_mod._run_set_hash(rids)

    def test_repeat_store_get_byte_equal(self):
        _seed_runs(prefix="bd", n=1)
        payload = {"a": 1, "b": [1, 2, 3]}
        cache_mod.store_intelligence(["bd_00"], payload, 60)
        a = cache_mod.get_cached_intelligence(["bd_00"])
        b = cache_mod.get_cached_intelligence(["bd_00"])
        assert a == b


# ===========================================================================
# J. Source-code purity / module surface
# ===========================================================================
class TestModuleSurface:
    def test_public_functions_callable(self):
        for fn in (
            cache_mod.get_cached_intelligence,
            cache_mod.store_intelligence,
            cache_mod.invalidate_intelligence,
        ):
            assert callable(fn)

    def test_default_ttl_locked(self):
        assert cache_mod.DEFAULT_TTL_SECONDS == 300


class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(cache_mod)

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
