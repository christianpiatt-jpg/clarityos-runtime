"""
Tests for v69 / Unit 74 — el_ins.el_ins_store.

Covers:
    A. Validation (operator_id, thread_id, source, result)
    B. store + retrieve by thread
    C. recent retrieval with limit + ordering
    D. macro retrieval with since filter
    E. multi-operator isolation
    F. _reset_for_tests hook
"""
from __future__ import annotations

import time

import pytest

import el_ins
from el_ins.el_ins_store import (
    VALID_SOURCES,
    _reset_for_tests,
    get_macro_el_ins,
    get_recent_el_ins,
    get_thread_el_ins,
    store_el_ins_record,
)


def _mock_result(cls: str = "balanced") -> dict:
    return {
        "analysis": {
            "el_components": [], "ins_components": [],
            "el_score": 1.0, "ins_score": 1.0,
            "ratio_classification": cls,
        },
        "reasoning_mode": "normal",
        "regression_chain": {
            "projection": None, "drivers": [], "precedents": [],
            "principle_stack": [], "invariant": None,
        },
        "stability_notes": None,
    }


@pytest.fixture(autouse=True)
def _isolate_store():
    _reset_for_tests()
    yield
    _reset_for_tests()


# ===========================================================================
# A. Validation
# ===========================================================================
class TestValidation:
    def test_missing_operator_id_raises(self):
        with pytest.raises(ValueError):
            store_el_ins_record({
                "operator_id": "", "thread_id": "t1",
                "timestamp": time.time(), "source": "on_demand",
                "result": _mock_result(),
            })

    def test_non_dict_record_raises(self):
        with pytest.raises(ValueError):
            store_el_ins_record(None)  # type: ignore[arg-type]

    def test_bad_thread_id_raises(self):
        with pytest.raises(ValueError):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "",
                "timestamp": time.time(), "source": "on_demand",
                "result": _mock_result(),
            })

    def test_thread_id_can_be_none(self):
        store_el_ins_record({
            "operator_id": "alice", "thread_id": None,
            "timestamp": time.time(), "source": "on_demand",
            "result": _mock_result(),
        })
        # Just confirm no exception.
        assert get_recent_el_ins("alice")[0]["thread_id"] is None

    def test_bad_source_raises(self):
        with pytest.raises(ValueError):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": time.time(), "source": "banana",
                "result": _mock_result(),
            })

    def test_all_valid_sources_accepted(self):
        for src in VALID_SOURCES:
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": time.time(), "source": src,
                "result": _mock_result(),
            })
        rows = get_recent_el_ins("alice")
        assert len(rows) == len(VALID_SOURCES)

    def test_result_not_dict_raises(self):
        with pytest.raises(ValueError):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": time.time(), "source": "on_demand",
                "result": "not a dict",  # type: ignore[arg-type]
            })

    def test_missing_timestamp_defaults_to_now(self):
        t0 = time.time()
        store_el_ins_record({
            "operator_id": "alice", "thread_id": "t1",
            "source": "on_demand",
            "result": _mock_result(),
        })
        ts = get_recent_el_ins("alice")[0]["timestamp"]
        assert ts >= t0


# ===========================================================================
# B. Thread retrieval
# ===========================================================================
class TestThreadRetrieval:
    def test_thread_records_filtered_by_thread_id(self):
        store_el_ins_record({
            "operator_id": "alice", "thread_id": "t1",
            "timestamp": 1.0, "source": "on_demand",
            "result": _mock_result("high_el"),
        })
        store_el_ins_record({
            "operator_id": "alice", "thread_id": "t2",
            "timestamp": 2.0, "source": "on_demand",
            "result": _mock_result("high_ins"),
        })
        store_el_ins_record({
            "operator_id": "alice", "thread_id": "t1",
            "timestamp": 3.0, "source": "on_demand",
            "result": _mock_result("balanced"),
        })
        t1 = get_thread_el_ins("alice", "t1")
        t2 = get_thread_el_ins("alice", "t2")
        assert len(t1) == 2
        assert len(t2) == 1

    def test_thread_records_newest_first(self):
        for i, ts in enumerate([1.0, 2.0, 3.0]):
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": ts, "source": "on_demand",
                "result": _mock_result(),
            })
        rows = get_thread_el_ins("alice", "t1")
        assert rows[0]["timestamp"] == 3.0
        assert rows[-1]["timestamp"] == 1.0

    def test_unknown_thread_returns_empty(self):
        assert get_thread_el_ins("alice", "nope") == []

    def test_thread_retrieval_validates_args(self):
        with pytest.raises(ValueError):
            get_thread_el_ins("", "t1")
        with pytest.raises(ValueError):
            get_thread_el_ins("alice", "")


# ===========================================================================
# C. Recent retrieval
# ===========================================================================
class TestRecentRetrieval:
    def test_recent_returns_newest_first(self):
        for ts in [1.0, 2.0, 3.0]:
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": ts, "source": "on_demand",
                "result": _mock_result(),
            })
        rows = get_recent_el_ins("alice")
        assert [r["timestamp"] for r in rows] == [3.0, 2.0, 1.0]

    def test_recent_respects_limit(self):
        for ts in [1.0, 2.0, 3.0, 4.0, 5.0]:
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": ts, "source": "on_demand",
                "result": _mock_result(),
            })
        rows = get_recent_el_ins("alice", limit=2)
        assert len(rows) == 2
        assert rows[0]["timestamp"] == 5.0

    def test_recent_limit_clamped_high(self):
        for ts in [1.0, 2.0, 3.0]:
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": ts, "source": "on_demand",
                "result": _mock_result(),
            })
        rows = get_recent_el_ins("alice", limit=10_000)
        assert len(rows) == 3

    def test_recent_limit_clamped_low(self):
        for ts in [1.0, 2.0]:
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": ts, "source": "on_demand",
                "result": _mock_result(),
            })
        rows = get_recent_el_ins("alice", limit=0)
        assert len(rows) == 1   # clamped to >= 1

    def test_recent_unknown_operator_returns_empty(self):
        assert get_recent_el_ins("ghost") == []


# ===========================================================================
# D. Macro retrieval
# ===========================================================================
class TestMacroRetrieval:
    def test_macro_filters_by_since(self):
        for ts in [10.0, 20.0, 30.0]:
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": ts, "source": "macro",
                "result": _mock_result(),
            })
        rows = get_macro_el_ins("alice", since=15.0)
        assert len(rows) == 2
        assert all(r["timestamp"] >= 15.0 for r in rows)

    def test_macro_since_none_returns_all(self):
        for ts in [10.0, 20.0]:
            store_el_ins_record({
                "operator_id": "alice", "thread_id": "t1",
                "timestamp": ts, "source": "macro",
                "result": _mock_result(),
            })
        rows = get_macro_el_ins("alice")
        assert len(rows) == 2

    def test_macro_bad_since_raises(self):
        with pytest.raises(ValueError):
            get_macro_el_ins("alice", since="banana")  # type: ignore[arg-type]


# ===========================================================================
# E. Multi-operator isolation
# ===========================================================================
class TestMultiOperator:
    def test_operators_have_isolated_histories(self):
        store_el_ins_record({
            "operator_id": "alice", "thread_id": "t1",
            "timestamp": 1.0, "source": "on_demand",
            "result": _mock_result("high_el"),
        })
        store_el_ins_record({
            "operator_id": "bob", "thread_id": "t1",
            "timestamp": 2.0, "source": "on_demand",
            "result": _mock_result("high_ins"),
        })
        a = get_recent_el_ins("alice")
        b = get_recent_el_ins("bob")
        assert len(a) == 1
        assert len(b) == 1
        assert a[0]["operator_id"] == "alice"
        assert b[0]["operator_id"] == "bob"


# ===========================================================================
# F. Reset hook
# ===========================================================================
class TestResetHook:
    def test_reset_clears_all_records(self):
        store_el_ins_record({
            "operator_id": "alice", "thread_id": "t1",
            "timestamp": 1.0, "source": "on_demand",
            "result": _mock_result(),
        })
        assert len(get_recent_el_ins("alice")) == 1
        _reset_for_tests()
        assert get_recent_el_ins("alice") == []
