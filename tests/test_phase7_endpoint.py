# tests/test_phase7_endpoint.py
#
# CARD 7.2A — read-only /operator/telemetry endpoint. Verifies the route
# surfaces the durable Phase 7 telemetry (Card 7.1) without auth, without
# mutating the store, and round-tripping record_to_dict cleanly.
#
# Runs under TESTING=1 (tests/conftest.py), so phase7_storage uses its
# in-memory backend — no JSONL files are written.
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
import phase7_telemetry
from phase7_endpoint import OPERATOR_ID


@pytest.fixture
def client():
    import app
    from conftest import TestClient
    return TestClient(app.app)


@pytest.fixture(autouse=True)
def _reset_phase7():
    """Clean telemetry store around each test (module-level facade)."""
    phase7_storage.reset()
    yield
    phase7_storage.reset()


def _state(
    value: float,
    *,
    dominant: str = "p",
    invariant: str = "i",
    operator: str = "o",
) -> SuperstructureState:
    return SuperstructureState(
        pattern=SuperPatternState(dominant, value, value, value, f"{dominant}:{value:.2f}"),
        integration=SuperIntegrationState(value, value, f"int:{value:.2f}"),
        coherence=SuperCoherenceState(value, value, value, f"coh:{value:.2f}"),
        essence=SuperEssenceState(value, invariant, value),
        identity=SuperIdentityState(operator, value, value, value),
    )


def test_telemetry_empty_history(client):
    resp = client.get("/operator/telemetry")
    assert resp.status_code == 200
    body = resp.json()
    assert body["history"] == []
    assert body["latest"] is None


def test_telemetry_returns_history_and_latest(client):
    phase7_telemetry.record_snapshot(OPERATOR_ID, _state(0.8), 1.0)
    phase7_telemetry.record_snapshot(OPERATOR_ID, _state(0.4, dominant="shift"), 2.0)

    resp = client.get("/operator/telemetry")
    assert resp.status_code == 200
    body = resp.json()

    assert isinstance(body["history"], list)
    assert len(body["history"]) == 2
    # Chronological order (oldest first) is preserved.
    assert [r["timestamp"] for r in body["history"]] == [1.0, 2.0]
    # latest matches the last appended record.
    assert body["latest"] == body["history"][-1]
    assert body["latest"]["timestamp"] == 2.0
    # Full record shape round-trips.
    latest = body["latest"]
    assert set(latest.keys()) == {
        "timestamp", "superstructure", "drift", "coherence_health", "trust_band",
    }
    assert latest["trust_band"] in {"LOW", "MEDIUM", "HIGH"}
    # First record has no prior -> drift None; second has a measured drift.
    assert body["history"][0]["drift"] is None
    assert isinstance(body["history"][1]["drift"], float)
    # Nested SuperstructureState survives serialization.
    assert latest["superstructure"]["identity"]["operator_identity"]


def test_telemetry_payload_matches_record_to_dict(client):
    phase7_telemetry.record_snapshot(OPERATOR_ID, _state(0.5), 1.0)
    stored = phase7_telemetry.get_history(OPERATOR_ID)
    expected_latest = phase7_storage.record_to_dict(stored[-1])

    body = client.get("/operator/telemetry").json()
    assert body["latest"] == expected_latest
    assert body["history"] == [expected_latest]


def test_telemetry_is_read_only(client):
    phase7_telemetry.record_snapshot(OPERATOR_ID, _state(0.7), 1.0)
    before = phase7_telemetry.get_history(OPERATOR_ID)
    # Repeated reads must not mutate or grow the store.
    client.get("/operator/telemetry")
    client.get("/operator/telemetry")
    after = phase7_telemetry.get_history(OPERATOR_ID)
    assert len(before) == len(after) == 1


def test_telemetry_no_auth_required(client):
    # No session header supplied; the endpoint must still return 200.
    resp = client.get("/operator/telemetry")
    assert resp.status_code == 200
