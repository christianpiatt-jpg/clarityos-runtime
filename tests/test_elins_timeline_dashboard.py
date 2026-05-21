"""
Tests for ELINS Unit 2 — read-only Single-Party Fear regression
surface (wrapper module + FastAPI endpoint).

Layered coverage:
    A. Score-band logic (boundaries 0, 4, 5, 6, 7, 8, 9, 10)
    B. Wrapper passthrough — score, assertions, scenarios unchanged
    C. Wrapper purity — no mutation of timeline
    D. Endpoint behavior — 200 on valid payload, 400 on malformed, 401 on unauth
    E. Endpoint passthrough — timeline_id and rubric preserved
    F. Source-code purity — no I/O, no logging, no LLM, no network
    G. Isolation — wrapper does not import or modify elins_dashboard
    H. Determinism — same payload → byte-equal response
    I. Existing endpoints unaffected (smoke test of /health)
"""
from __future__ import annotations

import inspect
import secrets
import time

import pytest
from conftest import TestClient

import elins_timeline_dashboard as etd
from elins_regression_single_party import (
    SinglePartyFearRegressionResult,
    Timeline,
    TimePoint,
    run_single_party_fear_regression,
)


# ===========================================================================
# Fixture builders
# ===========================================================================
def _tp(
    *,
    t: str = "t0",
    regime_competition: float = 0.5,
    autocratization: float = 0.5,
    repression_index: float = 0.5,
    digital_repression: float = 0.5,
    perceived_threat: float = 0.5,
    fear_signal: float = 0.5,
    dissent_capacity: float = 0.5,
    normative_constraint: float = 0.5,
    support_buffer: float = 0.5,
    trigger_event=None,
) -> TimePoint:
    return TimePoint(
        t=t,
        regime_competition=regime_competition,
        autocratization=autocratization,
        repression_index=repression_index,
        digital_repression=digital_repression,
        perceived_threat=perceived_threat,
        fear_signal=fear_signal,
        dissent_capacity=dissent_capacity,
        normative_constraint=normative_constraint,
        support_buffer=support_buffer,
        trigger_event=trigger_event,
    )


def _rising_timeline() -> Timeline:
    return Timeline(
        timeline_id="rising_test",
        points=(
            _tp(t="t0", regime_competition=0.8, autocratization=0.2,
                repression_index=0.2, digital_repression=0.1,
                perceived_threat=0.2, fear_signal=0.2,
                dissent_capacity=0.8, normative_constraint=0.8,
                support_buffer=0.7),
            _tp(t="t1", regime_competition=0.6, autocratization=0.4,
                repression_index=0.4, digital_repression=0.3,
                perceived_threat=0.4, fear_signal=0.4,
                dissent_capacity=0.6, normative_constraint=0.6,
                support_buffer=0.6),
            _tp(t="t2", regime_competition=0.4, autocratization=0.6,
                repression_index=0.6, digital_repression=0.5,
                perceived_threat=0.6, fear_signal=0.6,
                dissent_capacity=0.4, normative_constraint=0.4,
                support_buffer=0.5, trigger_event="protests"),
            _tp(t="t3", regime_competition=0.2, autocratization=0.8,
                repression_index=0.9, digital_repression=0.7,
                perceived_threat=0.8, fear_signal=0.8,
                dissent_capacity=0.2, normative_constraint=0.2,
                support_buffer=0.4),
        ),
    )


def _flat_timeline() -> Timeline:
    return Timeline(
        timeline_id="flat_test",
        points=tuple(_tp(t=f"t{i}") for i in range(3)),
    )


def _payload_from_timeline(tl: Timeline) -> dict:
    return {
        "timeline_id": tl.timeline_id,
        "points": [
            {
                "t": p.t,
                "regime_competition": p.regime_competition,
                "autocratization": p.autocratization,
                "repression_index": p.repression_index,
                "digital_repression": p.digital_repression,
                "perceived_threat": p.perceived_threat,
                "fear_signal": p.fear_signal,
                "dissent_capacity": p.dissent_capacity,
                "normative_constraint": p.normative_constraint,
                "support_buffer": p.support_buffer,
                "trigger_event": p.trigger_event,
            }
            for p in tl.points
        ],
    }


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
# A. Score-band logic
# ===========================================================================
class TestScoreBand:
    def test_band_for_score_10(self):
        assert etd._score_band(10) == "Strong"

    def test_band_for_score_9(self):
        assert etd._score_band(9) == "Strong"

    def test_band_for_score_8(self):
        assert etd._score_band(8) == "Acceptable"

    def test_band_for_score_7(self):
        assert etd._score_band(7) == "Acceptable"

    def test_band_for_score_6(self):
        assert etd._score_band(6) == "Weak"

    def test_band_for_score_5(self):
        assert etd._score_band(5) == "Weak"

    def test_band_for_score_4(self):
        assert etd._score_band(4) == "Fails core logic"

    def test_band_for_score_0(self):
        assert etd._score_band(0) == "Fails core logic"

    def test_band_labels_locked(self):
        """Adding/renaming a label is a deliberate spec change."""
        assert etd._BAND_STRONG == "Strong"
        assert etd._BAND_ACCEPTABLE == "Acceptable"
        assert etd._BAND_WEAK == "Weak"
        assert etd._BAND_FAILS == "Fails core logic"


# ===========================================================================
# B. Wrapper passthrough
# ===========================================================================
class TestWrapperPassthrough:
    def test_returns_dict(self):
        out = etd.get_single_party_fear_regression(_rising_timeline())
        assert isinstance(out, dict)

    def test_required_keys_present(self):
        out = etd.get_single_party_fear_regression(_rising_timeline())
        for key in (
            "timeline_id", "score", "score_band",
            "structural_consistency_score", "timeline_sensitivity_score",
            "fear_mechanism_score", "threat_mechanism_score",
            "repression_coverage_score",
            "assertions_passed", "assertions_failed",
            "scenario_results",
        ):
            assert key in out, f"missing key: {key}"

    def test_timeline_id_preserved(self):
        out = etd.get_single_party_fear_regression(_rising_timeline())
        assert out["timeline_id"] == "rising_test"

    def test_score_matches_validator(self):
        tl = _rising_timeline()
        out = etd.get_single_party_fear_regression(tl)
        expected = run_single_party_fear_regression(tl).score
        assert out["score"] == expected

    def test_dimension_scores_match_validator(self):
        tl = _rising_timeline()
        out = etd.get_single_party_fear_regression(tl)
        v = run_single_party_fear_regression(tl)
        assert out["structural_consistency_score"] == v.structural_consistency_score
        assert out["timeline_sensitivity_score"] == v.timeline_sensitivity_score
        assert out["fear_mechanism_score"] == v.fear_mechanism_score
        assert out["threat_mechanism_score"] == v.threat_mechanism_score
        assert out["repression_coverage_score"] == v.repression_coverage_score

    def test_assertions_lists_match_validator(self):
        tl = _rising_timeline()
        out = etd.get_single_party_fear_regression(tl)
        v = run_single_party_fear_regression(tl)
        assert tuple(out["assertions_passed"]) == v.assertions_passed
        assert tuple(out["assertions_failed"]) == v.assertions_failed

    def test_scenario_results_match_validator(self):
        tl = _rising_timeline()
        out = etd.get_single_party_fear_regression(tl)
        v = run_single_party_fear_regression(tl)
        assert out["scenario_results"] == v.scenario_results

    def test_band_consistent_with_score(self):
        tl = _rising_timeline()
        out = etd.get_single_party_fear_regression(tl)
        assert out["score_band"] == etd._score_band(out["score"])

    def test_assertions_serialised_as_lists_not_tuples(self):
        out = etd.get_single_party_fear_regression(_rising_timeline())
        assert isinstance(out["assertions_passed"], list)
        assert isinstance(out["assertions_failed"], list)


# ===========================================================================
# C. Wrapper purity — no mutation, propagates ValueError
# ===========================================================================
class TestWrapperPurity:
    def test_timeline_not_mutated(self):
        tl = _rising_timeline()
        before = tuple((p.t, p.fear_signal, p.regime_competition)
                       for p in tl.points)
        etd.get_single_party_fear_regression(tl)
        after = tuple((p.t, p.fear_signal, p.regime_competition)
                      for p in tl.points)
        assert before == after

    def test_propagates_value_error_on_bad_input(self):
        with pytest.raises(ValueError):
            etd.get_single_party_fear_regression("not a timeline")  # type: ignore[arg-type]

    def test_pure_repeated_calls(self):
        tl = _rising_timeline()
        out1 = etd.get_single_party_fear_regression(tl)
        out2 = etd.get_single_party_fear_regression(tl)
        assert out1 == out2


# ===========================================================================
# D. Endpoint behavior
# ===========================================================================
class TestEndpointBehavior:
    def test_valid_payload_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=_payload_from_timeline(_rising_timeline()),
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_carries_required_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=_payload_from_timeline(_rising_timeline()),
            headers=_auth(sid),
        )
        body = resp.json()
        for key in (
            "timeline_id", "score", "score_band",
            "structural_consistency_score", "timeline_sensitivity_score",
            "fear_mechanism_score", "threat_mechanism_score",
            "repression_coverage_score",
            "assertions_passed", "assertions_failed",
            "scenario_results",
        ):
            assert key in body, f"missing key: {key}"

    def test_response_timeline_id_matches_request(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=_payload_from_timeline(_rising_timeline()),
            headers=_auth(sid),
        )
        assert resp.json()["timeline_id"] == "rising_test"

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        tl = _rising_timeline()
        direct = etd.get_single_party_fear_regression(tl)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=_payload_from_timeline(tl),
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_unauthenticated_returns_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=_payload_from_timeline(_rising_timeline()),
            # no X-Session-ID header
        )
        assert resp.status_code == 401

    def test_missing_timeline_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        del payload["timeline_id"]
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_empty_timeline_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        payload["timeline_id"] = ""
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_list_points_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json={"timeline_id": "x", "points": "oops"},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_missing_required_field_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        del payload["points"][0]["fear_signal"]
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_numeric_field_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        payload["points"][0]["fear_signal"] = "very high"
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_bool_for_numeric_field_returns_400(self, client, app_module):
        """bool subclasses int; we explicitly reject it as a numeric."""
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        payload["points"][0]["fear_signal"] = True
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_string_t_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        payload["points"][0]["t"] = 42
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_non_string_trigger_event_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        payload["points"][0]["trigger_event"] = 42
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_omitted_trigger_event_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        for p in payload["points"]:
            p.pop("trigger_event", None)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_empty_points_list_returns_200(self, client, app_module):
        """ELINS Unit 3: empty `points` is now valid. The validator
        returns a vacuous all-zero result; the endpoint passes it
        through with 200."""
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json={"timeline_id": "empty", "points": []},
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_empty_points_response_is_zero_score_fails_core_logic(self, client, app_module):
        """Empty timeline → score 0 → 'Fails core logic' band."""
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json={"timeline_id": "empty", "points": []},
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["timeline_id"] == "empty"
        assert body["score"] == 0
        assert body["score_band"] == "Fails core logic"
        # All five dimension scores are 0.
        assert body["structural_consistency_score"] == 0
        assert body["timeline_sensitivity_score"] == 0
        assert body["fear_mechanism_score"] == 0
        assert body["threat_mechanism_score"] == 0
        assert body["repression_coverage_score"] == 0
        # All assertions vacuously pass; no failures.
        assert body["assertions_failed"] == []
        assert len(body["assertions_passed"]) == 6
        # All scenarios vacuously pass.
        assert all(body["scenario_results"].values())

    def test_int_values_accepted_for_numeric_fields(self, client, app_module):
        """JSON ints (e.g., 0, 1) are valid floats."""
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        payload["points"][0]["fear_signal"] = 0
        payload["points"][0]["repression_index"] = 1
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 200


# ===========================================================================
# E. Determinism
# ===========================================================================
class TestEndpointDeterminism:
    def test_same_payload_byte_equal_response(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_from_timeline(_rising_timeline())
        r1 = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        r2 = client.post(
            "/elins/regression/single_party_fear",
            json=payload, headers=_auth(sid),
        )
        assert r1.json() == r2.json()


# ===========================================================================
# F. Source-code purity
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(etd)

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

    def test_no_io(self):
        src = self._src()
        for forbidden in ("open(", "Path(", "pathlib", "os.path",
                          "json.load", "json.dump", "subprocess",
                          "exec(", "eval("):
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


# ===========================================================================
# G. Isolation — wrapper does not import or modify elins_dashboard
# ===========================================================================
class TestIsolation:
    def test_wrapper_module_does_not_import_dashboard(self):
        """The new wrapper module's source must not import
        elins_dashboard. Path D — clean separation. (Docstring prose
        may mention it; only actual import statements are forbidden.)"""
        src = inspect.getsource(etd)
        for pattern in (
            "import elins_dashboard",
            "from elins_dashboard",
        ):
            assert pattern not in src, f"forbidden import: {pattern}"

    def test_wrapper_module_does_not_call_inference(self):
        """Should not import any ELINS basin inference modules."""
        src = inspect.getsource(etd)
        for forbidden in (
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
            "import elins_distribution_store",
            "from elins_distribution_store",
        ):
            assert forbidden not in src


# ===========================================================================
# H. Existing endpoints unaffected (smoke)
# ===========================================================================
class TestExistingEndpointsUnaffected:
    def test_health_still_works(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_root_still_works(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.json()["service"] == "ClarityOS Cloud"


# ===========================================================================
# I. End-to-end — wrapper composes Unit 1 result correctly
# ===========================================================================
class TestEndToEnd:
    def test_full_chain_rising_timeline(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=_payload_from_timeline(_rising_timeline()),
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["timeline_id"] == "rising_test"
        # Rising-concentration timeline scores at least Acceptable.
        assert body["score"] >= 7
        assert body["score_band"] in ("Acceptable", "Strong")
        # All 5 scenarios are reported.
        assert set(body["scenario_results"].keys()) == {
            "test_1_rising_concentration",
            "test_2_crackdown_event",
            "test_3_threat_spike_without_full_repression",
            "test_4_constraint_restoration",
            "test_5_digital_substitution",
        }
