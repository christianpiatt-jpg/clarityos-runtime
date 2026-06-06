# tests/test_phase9_ingest.py
#
# CARD 9.1 — action stream ingestion: raw → ActionEvent normalization +
# validation, append-only continuity storage, recent-window loading, and the
# POST /operator/action endpoint. No causal-graph integration yet (that's 9.2).
import pytest

import phase9_ingest
from phase9_actions import ActionEvent
from phase9_ingest import (
    get_action_continuity,
    ingest_action,
    load_recent_actions,
    store_action,
)
from phase7_endpoint import OPERATOR_ID  # noqa: F401  (kept for parity with the suite)


def _raw(id="act_1", label="Adjusted parameter X", timestamp=100.0, magnitude=0.7):
    return {"id": id, "label": label, "timestamp": timestamp, "magnitude": magnitude}


# ---------------------------------------------------------------------------
# ingest_action — valid normalization
# ---------------------------------------------------------------------------

def test_ingest_valid_action():
    event = ingest_action(_raw())
    assert isinstance(event, ActionEvent)
    assert event.id == "act_1"
    assert event.label == "Adjusted parameter X"
    assert event.timestamp == 100.0
    assert event.magnitude == 0.7


def test_ingest_magnitude_optional():
    event = ingest_action({"id": "a", "label": "Opened app", "timestamp": 5.0})
    assert event.magnitude is None


def test_ingest_int_timestamp_coerced_to_float():
    event = ingest_action(_raw(timestamp=1717000000))
    assert event.timestamp == pytest.approx(1717000000.0)
    assert isinstance(event.timestamp, float)


def test_ingest_deterministic():
    raw = _raw()
    assert ingest_action(raw) == ingest_action(dict(raw))


# ---------------------------------------------------------------------------
# ingest_action — validation
# ---------------------------------------------------------------------------

def test_reject_missing_id():
    with pytest.raises(ValueError):
        ingest_action({"label": "x", "timestamp": 1.0})


def test_reject_missing_label():
    with pytest.raises(ValueError):
        ingest_action({"id": "a", "timestamp": 1.0})


def test_reject_non_string_label():
    with pytest.raises(ValueError):
        ingest_action({"id": "a", "label": 123, "timestamp": 1.0})


def test_reject_missing_timestamp():
    with pytest.raises(ValueError):
        ingest_action({"id": "a", "label": "x"})


def test_reject_non_numeric_timestamp():
    with pytest.raises(ValueError):
        ingest_action({"id": "a", "label": "x", "timestamp": "soon"})


def test_reject_bool_timestamp():
    # bool is an int subclass — must be rejected as a non-numeric timestamp.
    with pytest.raises(ValueError):
        ingest_action({"id": "a", "label": "x", "timestamp": True})


def test_reject_negative_timestamp():
    with pytest.raises(ValueError):
        ingest_action(_raw(timestamp=-1.0))


def test_reject_magnitude_out_of_range_high():
    with pytest.raises(ValueError):
        ingest_action(_raw(magnitude=1.5))


def test_reject_magnitude_out_of_range_low():
    with pytest.raises(ValueError):
        ingest_action(_raw(magnitude=-1.5))


def test_magnitude_at_bounds_ok():
    assert ingest_action(_raw(magnitude=1.0)).magnitude == 1.0
    assert ingest_action(_raw(magnitude=-1.0)).magnitude == -1.0


# ---------------------------------------------------------------------------
# store_action + continuity (append-only, sorted by timestamp)
# ---------------------------------------------------------------------------

def test_store_appends_to_actions_key():
    continuity = {}
    store_action(ingest_action(_raw(id="a", timestamp=1.0)), continuity)
    assert "actions" in continuity
    assert len(continuity["actions"]) == 1
    assert continuity["actions"][0].id == "a"


def test_store_keeps_timestamp_sorted():
    continuity = {}
    for i, ts in enumerate([3.0, 1.0, 2.0]):
        store_action(ingest_action(_raw(id=f"a{i}", timestamp=ts)), continuity)
    assert [e.timestamp for e in continuity["actions"]] == [1.0, 2.0, 3.0]


def test_store_is_append_only():
    continuity = {}
    store_action(ingest_action(_raw(id="a", timestamp=1.0)), continuity)
    store_action(ingest_action(_raw(id="b", timestamp=2.0)), continuity)
    assert {e.id for e in continuity["actions"]} == {"a", "b"}   # nothing dropped


# ---------------------------------------------------------------------------
# load_recent_actions — window logic (caller supplies `now`, no wall-clock)
# ---------------------------------------------------------------------------

def test_load_recent_window():
    continuity = {}
    for ts in (10.0, 50.0, 90.0, 100.0):
        store_action(ingest_action(_raw(id=f"a{ts}", timestamp=ts)), continuity)
    # now=100, window=30 → cutoff 70 → only 90 and 100.
    recent = load_recent_actions(continuity, now=100.0, window=30.0)
    assert [e.timestamp for e in recent] == [90.0, 100.0]


def test_load_recent_includes_cutoff_boundary():
    continuity = {}
    store_action(ingest_action(_raw(id="edge", timestamp=70.0)), continuity)
    # cutoff = 100 - 30 = 70; timestamp >= cutoff is inclusive.
    assert len(load_recent_actions(continuity, now=100.0, window=30.0)) == 1


def test_load_recent_sorted_and_deterministic():
    continuity = {}
    for ts in (3.0, 1.0, 2.0):
        store_action(ingest_action(_raw(id=f"a{ts}", timestamp=ts)), continuity)
    recent = load_recent_actions(continuity, now=10.0, window=100.0)
    assert [e.timestamp for e in recent] == [1.0, 2.0, 3.0]


def test_load_recent_empty_continuity():
    assert load_recent_actions({}, now=10.0, window=5.0) == []


# ---------------------------------------------------------------------------
# Endpoint integration — POST /operator/action
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    import app
    from conftest import TestClient
    return TestClient(app.app)


@pytest.fixture(autouse=True)
def _reset_action_continuity():
    phase9_ingest._reset_for_tests()
    yield
    phase9_ingest._reset_for_tests()


def test_endpoint_post_action_ok_and_appends(client):
    resp = client.post("/operator/action", json=_raw(id="act_42", timestamp=100.0, magnitude=0.5))
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}

    # The action was appended to the process-wide continuity log.
    actions = get_action_continuity()["actions"]
    assert len(actions) == 1
    assert actions[0].id == "act_42"
    assert actions[0].magnitude == 0.5


def test_endpoint_post_multiple_sorted(client):
    client.post("/operator/action", json=_raw(id="a", timestamp=3.0))
    client.post("/operator/action", json=_raw(id="b", timestamp=1.0))
    client.post("/operator/action", json=_raw(id="c", timestamp=2.0))
    actions = get_action_continuity()["actions"]
    assert [e.timestamp for e in actions] == [1.0, 2.0, 3.0]


def test_endpoint_rejects_invalid_action(client):
    # Negative timestamp → 400, nothing stored.
    resp = client.post("/operator/action", json=_raw(timestamp=-5.0))
    assert resp.status_code == 400
    assert get_action_continuity()["actions"] == []


def test_endpoint_rejects_bad_magnitude(client):
    resp = client.post("/operator/action", json=_raw(magnitude=2.0))
    assert resp.status_code == 400
    assert get_action_continuity()["actions"] == []
