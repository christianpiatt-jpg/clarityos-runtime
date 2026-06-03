# tests/test_phase10_11_endpoint.py
#
# Phase 10/11 surfacing on GET /operator/telemetry. The endpoint now emits:
#   * behavioral_forecast        — the 10.4 envelope {forecast (10.0),
#                                   stability (10.2), narrative (10.3)}
#   * recommendation_narrative   — the 11.1 compute_recommendation_narrative
#                                   object (recommendations + drivers + context)
# Deterministic — no wall-clock; action timestamps are the only temporal input.
import json

import pytest

import phase9_ingest


def _raw(id, label, timestamp, magnitude=0.6):
    return {"id": id, "label": label, "timestamp": timestamp, "magnitude": magnitude}


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


# ---------------------------------------------------------------------------
# behavioral_forecast envelope (Phase 10.4)
# ---------------------------------------------------------------------------
def test_telemetry_emits_behavioral_forecast_envelope(client):
    resp = client.get("/operator/telemetry")
    assert resp.status_code == 200
    bf = resp.json()["behavioral_forecast"]
    assert set(bf) == {"forecast", "stability", "narrative"}
    assert set(bf["forecast"]) >= {
        "next_actions", "habit_trajectory", "trigger_likelihood", "loop_continuation",
    }
    assert "score" in bf["stability"]
    assert "summary" in bf["narrative"]


# ---------------------------------------------------------------------------
# recommendation_narrative object (Phase 11.2)
# ---------------------------------------------------------------------------
def test_telemetry_emits_recommendation_narrative(client):
    rn = client.get("/operator/telemetry").json()["recommendation_narrative"]
    for key in ("summary", "recommendations", "drivers", "stability_context"):
        assert key in rn, key
    assert isinstance(rn["recommendations"], list)
    assert isinstance(rn["summary"], str) and rn["summary"]


# ---------------------------------------------------------------------------
# Empty action stream -> neutral / empty (no fabricated forecast)
# ---------------------------------------------------------------------------
def test_empty_history_is_neutral(client):
    body = client.get("/operator/telemetry").json()
    bf = body["behavioral_forecast"]
    assert bf["forecast"]["next_actions"] == []
    assert bf["forecast"]["loop_continuation"] == []
    assert body["recommendation_narrative"]["recommendations"] == []


# ---------------------------------------------------------------------------
# Posted actions flow through 9.1 -> 10.0 forecast
# ---------------------------------------------------------------------------
def test_posted_actions_populate_forecast(client):
    for i, ts in enumerate((10.0, 20.0, 30.0, 40.0, 50.0)):
        assert client.post(
            "/operator/action", json=_raw(f"p{i}", "prune", ts, 0.7)
        ).status_code == 200
    bf = client.get("/operator/telemetry").json()["behavioral_forecast"]
    labels = [a["label"] for a in bf["forecast"]["next_actions"]]
    assert "prune" in labels


# ---------------------------------------------------------------------------
# Whole response stays JSON-serialisable (no engine object leaks)
# ---------------------------------------------------------------------------
def test_telemetry_response_is_json_serialisable(client):
    for i, ts in enumerate((1.0, 2.0, 3.0)):
        client.post("/operator/action", json=_raw(f"a{i}", "sync", ts, 0.5))
    body = client.get("/operator/telemetry").json()
    json.dumps(body)  # must not raise
    assert "behavioral_forecast" in body and "recommendation_narrative" in body
