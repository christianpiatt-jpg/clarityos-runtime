"""
Tests for ELINS Unit 5 — multi-regression comparison harness +
dashboard wrapper + FastAPI endpoint.

Layered coverage (≥ 60 tests):
    A. Schema (RegressionComparisonResult)
    B. Band-rank helpers (_band_for, _band_delta)
    C. compare_regressions — score_delta, band_delta, pass-through
    D. compare_regressions — determinism + no mutation
    E. compare_regressions_dashboard — dict shape + delta labels
    F. Endpoint — valid, malformed, auth, empty timelines, parity
    G. Source-code purity
    H. Isolation — no basin inference imports
    I. Independence — does not import dashboard wrapper module
    J. End-to-end + existing endpoints unaffected
"""
from __future__ import annotations

import inspect
import secrets
import time
from dataclasses import FrozenInstanceError

import pytest
from conftest import TestClient

import elins_regression_compare as cmp_mod
import elins_timeline_dashboard as etd
from elins_regression_compare import (
    RegressionComparisonResult,
    compare_regressions,
)
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
# Fixture builders
# ===========================================================================
def _sp_tp(
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


def _ec_tp(
    *,
    t: str = "t0",
    economic_pressure: float = 0.5,
    material_insecurity: float = 0.5,
    state_coercion: float = 0.5,
    compliance_signal: float = 0.5,
    resistance_capacity: float = 0.5,
    support_buffer: float = 0.5,
    trigger_event=None,
) -> TimePointEconomic:
    return TimePointEconomic(
        t=t,
        economic_pressure=economic_pressure,
        material_insecurity=material_insecurity,
        state_coercion=state_coercion,
        compliance_signal=compliance_signal,
        resistance_capacity=resistance_capacity,
        support_buffer=support_buffer,
        trigger_event=trigger_event,
    )


def _sp_empty() -> Timeline:
    return Timeline(timeline_id="sp_empty", points=())


def _ec_empty() -> TimelineEconomic:
    return TimelineEconomic(timeline_id="ec_empty", points=())


def _sp_flat(n: int = 3) -> Timeline:
    return Timeline(
        timeline_id="sp_flat",
        points=tuple(_sp_tp(t=f"t{i}") for i in range(n)),
    )


def _ec_flat(n: int = 3) -> TimelineEconomic:
    return TimelineEconomic(
        timeline_id="ec_flat",
        points=tuple(_ec_tp(t=f"t{i}") for i in range(n)),
    )


def _sp_rising() -> Timeline:
    return Timeline(
        timeline_id="sp_rising",
        points=(
            _sp_tp(t="t0", regime_competition=0.8, autocratization=0.2,
                   repression_index=0.2, digital_repression=0.1,
                   perceived_threat=0.2, fear_signal=0.2,
                   dissent_capacity=0.8, normative_constraint=0.8,
                   support_buffer=0.7),
            _sp_tp(t="t1", regime_competition=0.4, autocratization=0.6,
                   repression_index=0.6, digital_repression=0.5,
                   perceived_threat=0.6, fear_signal=0.6,
                   dissent_capacity=0.4, normative_constraint=0.4,
                   support_buffer=0.5),
            _sp_tp(t="t2", regime_competition=0.2, autocratization=0.8,
                   repression_index=0.9, digital_repression=0.7,
                   perceived_threat=0.8, fear_signal=0.8,
                   dissent_capacity=0.2, normative_constraint=0.2,
                   support_buffer=0.4),
        ),
    )


def _ec_rising() -> TimelineEconomic:
    return TimelineEconomic(
        timeline_id="ec_rising",
        points=(
            _ec_tp(t="t0", economic_pressure=0.2, material_insecurity=0.2,
                   state_coercion=0.2, compliance_signal=0.2,
                   resistance_capacity=0.7, support_buffer=0.7),
            _ec_tp(t="t1", economic_pressure=0.5, material_insecurity=0.5,
                   state_coercion=0.5, compliance_signal=0.4,
                   resistance_capacity=0.5, support_buffer=0.5,
                   trigger_event="layoffs"),
            _ec_tp(t="t2", economic_pressure=0.8, material_insecurity=0.8,
                   state_coercion=0.7, compliance_signal=0.6,
                   resistance_capacity=0.3, support_buffer=0.3),
        ),
    )


def _payload_pair(sp: Timeline, ec: TimelineEconomic) -> dict:
    return {
        "single_party_timeline": {
            "timeline_id": sp.timeline_id,
            "points": [
                {
                    "t": p.t,
                    "regime_competition":   p.regime_competition,
                    "autocratization":      p.autocratization,
                    "repression_index":     p.repression_index,
                    "digital_repression":   p.digital_repression,
                    "perceived_threat":     p.perceived_threat,
                    "fear_signal":          p.fear_signal,
                    "dissent_capacity":     p.dissent_capacity,
                    "normative_constraint": p.normative_constraint,
                    "support_buffer":       p.support_buffer,
                    "trigger_event":        p.trigger_event,
                }
                for p in sp.points
            ],
        },
        "economic_timeline": {
            "timeline_id": ec.timeline_id,
            "points": [
                {
                    "t": p.t,
                    "economic_pressure":   p.economic_pressure,
                    "material_insecurity": p.material_insecurity,
                    "state_coercion":      p.state_coercion,
                    "compliance_signal":   p.compliance_signal,
                    "resistance_capacity": p.resistance_capacity,
                    "support_buffer":      p.support_buffer,
                    "trigger_event":       p.trigger_event,
                }
                for p in ec.points
            ],
        },
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
# A. RegressionComparisonResult schema
# ===========================================================================
class TestSchema:
    def test_instantiable(self):
        r = RegressionComparisonResult(
            single_party_score=0,
            economic_coercion_score=0,
            score_delta=0,
            single_party_band="Fails core logic",
            economic_coercion_band="Fails core logic",
            band_delta="same",
            assertions_failed_single_party=(),
            assertions_failed_economic=(),
            scenario_results_single_party={},
            scenario_results_economic={},
        )
        assert r.score_delta == 0

    def test_frozen(self):
        r = RegressionComparisonResult(
            single_party_score=0, economic_coercion_score=0,
            score_delta=0,
            single_party_band="Fails core logic",
            economic_coercion_band="Fails core logic",
            band_delta="same",
            assertions_failed_single_party=(),
            assertions_failed_economic=(),
            scenario_results_single_party={},
            scenario_results_economic={},
        )
        with pytest.raises(FrozenInstanceError):
            r.score_delta = 5  # type: ignore[misc]


# ===========================================================================
# B. Band helpers
# ===========================================================================
class TestBandHelpers:
    @pytest.mark.parametrize("score,expected", [
        (10, "Strong"), (9, "Strong"),
        (8, "Acceptable"), (7, "Acceptable"),
        (6, "Weak"), (5, "Weak"),
        (4, "Fails core logic"), (0, "Fails core logic"),
    ])
    def test_band_for_score(self, score, expected):
        assert cmp_mod._band_for(score) == expected

    def test_band_delta_same(self):
        assert cmp_mod._band_delta("Strong", "Strong") == "same"

    def test_band_delta_up(self):
        assert cmp_mod._band_delta("Acceptable", "Strong") == "up"

    def test_band_delta_down(self):
        assert cmp_mod._band_delta("Strong", "Acceptable") == "down"

    def test_band_delta_up_two_steps(self):
        assert cmp_mod._band_delta("Weak", "Strong") == "up"

    def test_band_delta_down_three_steps(self):
        assert cmp_mod._band_delta("Strong", "Fails core logic") == "down"

    def test_band_rank_ordering(self):
        ranks = [
            cmp_mod._BAND_RANK["Fails core logic"],
            cmp_mod._BAND_RANK["Weak"],
            cmp_mod._BAND_RANK["Acceptable"],
            cmp_mod._BAND_RANK["Strong"],
        ]
        assert ranks == sorted(ranks)
        assert len(set(ranks)) == 4


# ===========================================================================
# C. compare_regressions core behavior
# ===========================================================================
class TestCompareRegressionsCore:
    def test_returns_result_instance(self):
        r = compare_regressions(_sp_empty(), _ec_empty())
        assert isinstance(r, RegressionComparisonResult)

    def test_empty_pair_score_zero(self):
        r = compare_regressions(_sp_empty(), _ec_empty())
        assert r.single_party_score == 0
        assert r.economic_coercion_score == 0
        assert r.score_delta == 0

    def test_empty_pair_band_same(self):
        r = compare_regressions(_sp_empty(), _ec_empty())
        assert r.single_party_band == "Fails core logic"
        assert r.economic_coercion_band == "Fails core logic"
        assert r.band_delta == "same"

    def test_empty_pair_no_assertion_failures(self):
        r = compare_regressions(_sp_empty(), _ec_empty())
        assert r.assertions_failed_single_party == ()
        assert r.assertions_failed_economic == ()

    def test_empty_pair_scenarios_present(self):
        r = compare_regressions(_sp_empty(), _ec_empty())
        # All scenarios vacuously pass on N=0.
        assert all(r.scenario_results_single_party.values())
        assert all(r.scenario_results_economic.values())

    def test_score_delta_economic_minus_single_party(self):
        r = compare_regressions(_sp_rising(), _ec_rising())
        expected = (run_economic_coercion_regression(_ec_rising()).score
                    - run_single_party_fear_regression(_sp_rising()).score)
        assert r.score_delta == expected

    def test_pass_through_single_party_assertions(self):
        sp = _sp_rising()
        r = compare_regressions(sp, _ec_rising())
        expected = run_single_party_fear_regression(sp).assertions_failed
        assert r.assertions_failed_single_party == expected

    def test_pass_through_economic_assertions(self):
        ec = _ec_rising()
        r = compare_regressions(_sp_rising(), ec)
        expected = run_economic_coercion_regression(ec).assertions_failed
        assert r.assertions_failed_economic == expected

    def test_pass_through_single_party_scenarios(self):
        sp = _sp_rising()
        r = compare_regressions(sp, _ec_rising())
        expected = run_single_party_fear_regression(sp).scenario_results
        assert r.scenario_results_single_party == expected

    def test_pass_through_economic_scenarios(self):
        ec = _ec_rising()
        r = compare_regressions(_sp_rising(), ec)
        expected = run_economic_coercion_regression(ec).scenario_results
        assert r.scenario_results_economic == expected

    def test_band_up_when_economic_higher(self):
        # Rising economic timeline scores 10 (Strong); empty SP scores 0
        # (Fails core logic).
        r = compare_regressions(_sp_empty(), _ec_rising())
        assert r.band_delta == "up"

    def test_band_down_when_single_party_higher(self):
        # Rising SP scores 9 (Strong); empty EC scores 0 (Fails core logic).
        r = compare_regressions(_sp_rising(), _ec_empty())
        assert r.band_delta == "down"

    def test_band_same_both_strong(self):
        # Both rising timelines reach Strong band (>= 9).
        r = compare_regressions(_sp_rising(), _ec_rising())
        assert r.band_delta == "same"

    def test_no_derived_series_in_result(self):
        """Result intentionally omits derived series (too large)."""
        r = compare_regressions(_sp_rising(), _ec_rising())
        assert not hasattr(r, "derived_series")
        assert not hasattr(r, "derived_series_single_party")

    def test_propagates_value_error_on_bad_sp_input(self):
        with pytest.raises(ValueError):
            compare_regressions("not a timeline", _ec_empty())  # type: ignore[arg-type]

    def test_propagates_value_error_on_bad_ec_input(self):
        with pytest.raises(ValueError):
            compare_regressions(_sp_empty(), "not a timeline")  # type: ignore[arg-type]


# ===========================================================================
# D. Determinism + no mutation
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeated_calls(self):
        sp = _sp_rising()
        ec = _ec_rising()
        r1 = compare_regressions(sp, ec)
        r2 = compare_regressions(sp, ec)
        assert r1 == r2

    def test_sp_timeline_not_mutated(self):
        sp = _sp_rising()
        before = tuple((p.t, p.fear_signal, p.regime_competition) for p in sp.points)
        compare_regressions(sp, _ec_rising())
        after = tuple((p.t, p.fear_signal, p.regime_competition) for p in sp.points)
        assert before == after

    def test_ec_timeline_not_mutated(self):
        ec = _ec_rising()
        before = tuple((p.t, p.economic_pressure, p.compliance_signal) for p in ec.points)
        compare_regressions(_sp_rising(), ec)
        after = tuple((p.t, p.economic_pressure, p.compliance_signal) for p in ec.points)
        assert before == after

    def test_different_length_timelines_accepted(self):
        """Module does not align timelines — different lengths are OK."""
        sp = _sp_rising()  # 3 points
        ec = _ec_flat(n=5)  # 5 points
        r = compare_regressions(sp, ec)
        assert isinstance(r, RegressionComparisonResult)


# ===========================================================================
# E. compare_regressions_dashboard — wrapper
# ===========================================================================
class TestDashboardWrapper:
    def test_returns_dict(self):
        out = etd.compare_regressions_dashboard(_sp_rising(), _ec_rising())
        assert isinstance(out, dict)

    def test_required_keys_present(self):
        out = etd.compare_regressions_dashboard(_sp_rising(), _ec_rising())
        for key in (
            "single_party_score", "economic_coercion_score",
            "score_delta", "score_delta_label",
            "single_party_band", "economic_coercion_band",
            "band_delta", "band_delta_label",
            "assertions_failed_single_party",
            "assertions_failed_economic",
            "scenario_results_single_party",
            "scenario_results_economic",
        ):
            assert key in out, f"missing key: {key}"

    def test_score_delta_label_economic_higher(self):
        out = etd.compare_regressions_dashboard(_sp_empty(), _ec_rising())
        # ec score >= 9, sp = 0 → score_delta >= 9
        assert out["score_delta"] >= 9
        assert "economic coercion" in out["score_delta_label"]
        assert "+" in out["score_delta_label"]

    def test_score_delta_label_single_party_higher(self):
        out = etd.compare_regressions_dashboard(_sp_rising(), _ec_empty())
        assert out["score_delta"] <= -7
        assert "single party fear" in out["score_delta_label"]

    def test_score_delta_label_tied(self):
        out = etd.compare_regressions_dashboard(_sp_empty(), _ec_empty())
        assert out["score_delta"] == 0
        assert out["score_delta_label"] == "tied"

    def test_band_delta_label_up(self):
        out = etd.compare_regressions_dashboard(_sp_empty(), _ec_rising())
        assert out["band_delta"] == "up"
        assert "economic coercion" in out["band_delta_label"]
        assert "higher" in out["band_delta_label"]

    def test_band_delta_label_down(self):
        out = etd.compare_regressions_dashboard(_sp_rising(), _ec_empty())
        assert out["band_delta"] == "down"
        assert "single party fear" in out["band_delta_label"]

    def test_band_delta_label_same(self):
        out = etd.compare_regressions_dashboard(_sp_empty(), _ec_empty())
        assert out["band_delta"] == "same"
        assert "tied at" in out["band_delta_label"]

    def test_assertions_serialised_as_lists(self):
        out = etd.compare_regressions_dashboard(_sp_rising(), _ec_rising())
        assert isinstance(out["assertions_failed_single_party"], list)
        assert isinstance(out["assertions_failed_economic"], list)

    def test_no_mutation_of_inputs(self):
        sp = _sp_rising()
        ec = _ec_rising()
        before_sp = tuple((p.t, p.fear_signal) for p in sp.points)
        before_ec = tuple((p.t, p.compliance_signal) for p in ec.points)
        etd.compare_regressions_dashboard(sp, ec)
        after_sp = tuple((p.t, p.fear_signal) for p in sp.points)
        after_ec = tuple((p.t, p.compliance_signal) for p in ec.points)
        assert before_sp == after_sp
        assert before_ec == after_ec


# ===========================================================================
# F. Endpoint behavior
# ===========================================================================
class TestEndpoint:
    def test_valid_payload_200(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare",
            json=_payload_pair(_sp_rising(), _ec_rising()),
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_required_keys(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare",
            json=_payload_pair(_sp_rising(), _ec_rising()),
            headers=_auth(sid),
        )
        body = resp.json()
        for key in (
            "single_party_score", "economic_coercion_score",
            "score_delta", "score_delta_label",
            "single_party_band", "economic_coercion_band",
            "band_delta", "band_delta_label",
        ):
            assert key in body

    def test_unauth_returns_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/compare",
            json=_payload_pair(_sp_rising(), _ec_rising()),
        )
        assert resp.status_code == 401

    def test_missing_sp_timeline_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        del payload["single_party_timeline"]
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_missing_ec_timeline_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        del payload["economic_timeline"]
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_timeline_not_object_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        payload["single_party_timeline"] = "not an object"
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_ec_timeline_not_object_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        payload["economic_timeline"] = []
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_missing_required_field_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        del payload["single_party_timeline"]["points"][0]["fear_signal"]
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_ec_missing_required_field_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        del payload["economic_timeline"]["points"][0]["compliance_signal"]
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_non_string_t_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        payload["single_party_timeline"]["points"][0]["t"] = 42
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_bool_for_numeric_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        payload["single_party_timeline"]["points"][0]["fear_signal"] = True
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_ec_bool_for_numeric_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        payload["economic_timeline"]["points"][0]["compliance_signal"] = True
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_empty_points_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_empty(), _ec_rising())
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_ec_empty_points_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_empty())
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_both_empty_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_empty(), _ec_empty())
        resp = client.post(
            "/elins/regression/compare",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["score_delta"] == 0
        assert body["band_delta"] == "same"
        assert body["score_delta_label"] == "tied"

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        sp = _sp_rising()
        ec = _ec_rising()
        direct = etd.compare_regressions_dashboard(sp, ec)
        resp = client.post(
            "/elins/regression/compare",
            json=_payload_pair(sp, ec),
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _payload_pair(_sp_rising(), _ec_rising())
        r1 = client.post("/elins/regression/compare",
                         json=payload, headers=_auth(sid))
        r2 = client.post("/elins/regression/compare",
                         json=payload, headers=_auth(sid))
        assert r1.json() == r2.json()


# ===========================================================================
# G. Source-code purity
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(cmp_mod)

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
# H. Isolation — does not import basin inference modules
# ===========================================================================
class TestIsolation:
    def test_no_dashboard_module_import(self):
        """The compare module is independent of the dashboard wrapper.
        (Dashboard imports compare, not the other way around.)"""
        src = inspect.getsource(cmp_mod)
        for pattern in (
            "import elins_timeline_dashboard",
            "from elins_timeline_dashboard",
        ):
            assert pattern not in src

    def test_no_basin_inference_imports(self):
        src = inspect.getsource(cmp_mod)
        for pattern in (
            "import elins_dashboard",
            "from elins_dashboard",
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
        ):
            assert pattern not in src


# ===========================================================================
# I. End-to-end + existing endpoints unaffected
# ===========================================================================
class TestExistingEndpointsUnaffected:
    def test_health_still_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_single_party_endpoint_still_works(self, client, app_module):
        sid = _make_user_session(app_module)
        sp_payload = _payload_pair(_sp_flat(), _ec_flat())["single_party_timeline"]
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=sp_payload, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_economic_endpoint_still_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ec_payload = _payload_pair(_sp_flat(), _ec_flat())["economic_timeline"]
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=ec_payload, headers=_auth(sid),
        )
        assert resp.status_code == 200


class TestEndToEnd:
    def test_full_chain_rising_pair(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare",
            json=_payload_pair(_sp_rising(), _ec_rising()),
            headers=_auth(sid),
        )
        body = resp.json()
        # Both rising timelines reach Strong band.
        assert body["single_party_band"] == "Strong"
        assert body["economic_coercion_band"] == "Strong"
        assert body["band_delta"] == "same"
        # Underlying assertion-failure surfaces are passed through.
        assert isinstance(body["assertions_failed_single_party"], list)
        assert isinstance(body["assertions_failed_economic"], list)

    def test_compare_module_band_constants_match_dashboard(self):
        """The band labels in compare module + dashboard wrapper must
        be identical strings (otherwise a label drift would break the
        downstream rank lookup)."""
        assert cmp_mod._BAND_STRONG == etd._BAND_STRONG
        assert cmp_mod._BAND_ACCEPTABLE == etd._BAND_ACCEPTABLE
        assert cmp_mod._BAND_WEAK == etd._BAND_WEAK
        assert cmp_mod._BAND_FAILS == etd._BAND_FAILS
