# tests/test_phase7_storage.py
import json
from copy import deepcopy

import pytest

from phase6_contracts import (
    SuperCoherenceState,
    SuperEssenceState,
    SuperIdentityState,
    SuperIntegrationState,
    SuperPatternState,
    SuperstructureState,
)
import phase7_storage
from phase7_storage import (
    DEFAULT_ROOT,
    JsonlTelemetryStore,
    MemoryTelemetryStore,
    TelemetryRecord,
    _make_default_store,
    record_from_dict,
    record_from_json,
    record_to_dict,
    record_to_json,
)


def _state(
    value: float,
    *,
    dominant: str = "p",
    invariant: str = "i",
    operator: str = "o",
) -> SuperstructureState:
    """A SuperstructureState whose every numeric field equals ``value``."""
    return SuperstructureState(
        pattern=SuperPatternState(dominant, value, value, value, f"{dominant}:{value:.2f}"),
        integration=SuperIntegrationState(value, value, f"int:{value:.2f}"),
        coherence=SuperCoherenceState(value, value, value, f"coh:{value:.2f}"),
        essence=SuperEssenceState(value, invariant, value),
        identity=SuperIdentityState(operator, value, value, value),
    )


def _record(
    ts: float,
    value: float = 0.5,
    *,
    drift=None,
    coherence=0.5,
    band="HIGH",
    **labels,
) -> TelemetryRecord:
    return TelemetryRecord(
        timestamp=ts,
        superstructure=_state(value, **labels),
        drift=drift,
        coherence_health=coherence,
        trust_band=band,
    )


@pytest.fixture(autouse=True)
def _reset_module_store():
    """Keep the process-wide module facade clean between tests."""
    phase7_storage.reset()
    yield
    phase7_storage.reset()


# ---------------------------------------------------------------------------
# JSONL backend — append behaviour + directory creation
# ---------------------------------------------------------------------------

def test_jsonl_append_creates_dir_and_file(tmp_path):
    root = tmp_path / "telemetry"
    store = JsonlTelemetryStore(root)
    assert not root.exists()  # construction alone creates nothing
    store.append_record("op", _record(1.0))
    assert root.is_dir()
    assert (root / "op.jsonl").is_file()


def test_jsonl_is_append_only(tmp_path):
    store = JsonlTelemetryStore(tmp_path)
    for ts in (1.0, 2.0, 3.0):
        store.append_record("op", _record(ts))
    lines = (tmp_path / "op.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    for ln in lines:  # every line is independently valid JSON
        json.loads(ln)


def test_jsonl_ordering_is_chronological_by_append(tmp_path):
    store = JsonlTelemetryStore(tmp_path)
    for i in range(5):
        store.append_record("op", _record(float(i)))
    assert [r.timestamp for r in store.load_history("op")] == [0.0, 1.0, 2.0, 3.0, 4.0]


def test_jsonl_limit_slicing(tmp_path):
    store = JsonlTelemetryStore(tmp_path)
    for i in range(5):
        store.append_record("op", _record(float(i)))
    assert [r.timestamp for r in store.load_history("op", limit=3)] == [2.0, 3.0, 4.0]
    assert len(store.load_history("op", limit=None)) == 5
    assert store.load_history("op", limit=0) == []
    assert store.load_history("op", limit=-1) == []


def test_jsonl_unknown_operator_returns_empty(tmp_path):
    store = JsonlTelemetryStore(tmp_path)
    assert store.load_history("ghost") == []


def test_jsonl_cross_operator_isolation(tmp_path):
    store = JsonlTelemetryStore(tmp_path)
    store.append_record("a", _record(1.0, value=0.2))
    store.append_record("b", _record(1.0, value=0.9))
    store.append_record("a", _record(2.0, value=0.25))
    assert len(store.load_history("a")) == 2
    assert len(store.load_history("b")) == 1
    assert (tmp_path / "a.jsonl").is_file()
    assert (tmp_path / "b.jsonl").is_file()


def test_jsonl_no_mutation_of_prior_records(tmp_path):
    store = JsonlTelemetryStore(tmp_path)
    store.append_record("op", _record(1.0, value=0.9))
    first = store.load_history("op")
    assert len(first) == 1
    snapshot = record_to_json(first[0])

    store.append_record("op", _record(2.0, value=0.1))
    store.append_record("op", _record(3.0, value=0.5))

    # The earlier-returned list is unaffected by later appends.
    assert len(first) == 1
    assert record_to_json(first[0]) == snapshot
    # And the persisted first record is byte-for-byte intact at index 0.
    again = store.load_history("op")
    assert again[0].timestamp == 1.0
    assert record_to_json(again[0]) == snapshot


# ---------------------------------------------------------------------------
# Serialization — deterministic + clean JSON round-trip
# ---------------------------------------------------------------------------

def test_record_round_trips_through_json():
    r = _record(
        1.5, value=0.375, drift=0.7, coherence=0.642, band="MEDIUM",
        dominant="extraction", invariant="inv-x", operator="op-7",
    )
    assert record_from_json(record_to_json(r)) == r
    assert record_from_dict(record_to_dict(r)) == r


def test_record_round_trips_with_none_drift():
    r = _record(0.0, drift=None, band="HIGH")
    back = record_from_json(record_to_json(r))
    assert back == r
    assert back.drift is None


def test_serialization_is_deterministic():
    r = _record(2.0, value=0.5, drift=0.3, coherence=0.8, band="HIGH")
    assert record_to_json(r) == record_to_json(r)
    assert record_to_json(deepcopy(r)) == record_to_json(r)
    # sort_keys -> stable, human-inspectable ordering
    d = json.loads(record_to_json(r))
    assert list(d.keys()) == sorted(d.keys())


def test_jsonl_full_file_round_trips(tmp_path):
    store = JsonlTelemetryStore(tmp_path)
    originals = [
        _record(
            float(i), value=i / 10,
            drift=(None if i == 0 else 0.5), coherence=0.5 + i / 100,
            band="HIGH", dominant=f"d{i}", operator=f"op{i}",
        )
        for i in range(4)
    ]
    for r in originals:
        store.append_record("op", r)
    assert store.load_history("op") == originals


# ---------------------------------------------------------------------------
# Memory backend — mirrors JSONL semantics
# ---------------------------------------------------------------------------

def test_memory_backend_mirrors_jsonl_behaviour(tmp_path):
    mem = MemoryTelemetryStore()
    js = JsonlTelemetryStore(tmp_path)
    for i in range(4):
        r = _record(float(i), value=i / 10)
        mem.append_record("op", r)
        js.append_record("op", r)

    assert [r.timestamp for r in mem.load_history("op")] == \
           [r.timestamp for r in js.load_history("op")]
    assert [r.timestamp for r in mem.load_history("op", limit=2)] == \
           [r.timestamp for r in js.load_history("op", limit=2)]
    assert mem.load_history("op", limit=0) == js.load_history("op", limit=0) == []
    assert mem.load_history("ghost") == js.load_history("ghost") == []


def test_memory_backend_returns_fresh_lists():
    mem = MemoryTelemetryStore()
    mem.append_record("op", _record(1.0))
    first = mem.load_history("op")
    mem.append_record("op", _record(2.0))
    assert len(first) == 1  # a copy, not the internal list


def test_memory_reset_clears():
    mem = MemoryTelemetryStore()
    mem.append_record("op", _record(1.0))
    mem.reset()
    assert mem.load_history("op") == []


# ---------------------------------------------------------------------------
# Operator-id validation (shared by both backends)
# ---------------------------------------------------------------------------

def test_valid_operator_ids_accepted(tmp_path):
    store = JsonlTelemetryStore(tmp_path)
    for ok in ["op", "clarityos-operator", "op_1", "Op.2", "a-b_c.d"]:
        store.append_record(ok, _record(1.0))
        assert store.load_history(ok)


@pytest.mark.parametrize("bad", ["", "a/b", "..", ".", "x\\y", "a b", "a" * 129])
def test_invalid_operator_id_rejected_both_backends(tmp_path, bad):
    for store in (JsonlTelemetryStore(tmp_path), MemoryTelemetryStore()):
        with pytest.raises(ValueError):
            store.append_record(bad, _record(1.0))
        with pytest.raises(ValueError):
            store.load_history(bad)


# ---------------------------------------------------------------------------
# Backend selection + module-level facade
# ---------------------------------------------------------------------------

def test_backend_selection_by_testing_env(monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    assert isinstance(_make_default_store(), MemoryTelemetryStore)

    monkeypatch.delenv("TESTING", raising=False)
    store = _make_default_store()
    assert isinstance(store, JsonlTelemetryStore)
    assert store.root == DEFAULT_ROOT
    # Selecting the JSONL default must not create the directory.
    assert not store.root.exists()


def test_module_facade_uses_memory_under_testing():
    # conftest sets TESTING=1, so the module facade is the in-memory backend.
    phase7_storage.append_record("op", _record(1.0))
    assert [r.timestamp for r in phase7_storage.load_history("op")] == [1.0]
    phase7_storage.reset()
    assert phase7_storage.load_history("op") == []
