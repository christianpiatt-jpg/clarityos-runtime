"""
Tests for ELINS Unit 8 — batch comparison harness + wrapper + endpoint.

Layered coverage (≥ 60 tests):
    A. compare_regressions_batch core
    B. compare_regressions_batch_dashboard wrapper
    C. Endpoint behavior — valid / 400 / auth / empty
    D. Per-pair index in error messages
    E. Determinism + no input mutation
    F. Source-code purity
    G. Existing endpoints unaffected
"""
from __future__ import annotations

import inspect
import secrets
import time

import pytest
from conftest import TestClient

import elins_regression_compare as cmp_mod
import elins_timeline_dashboard as etd
from elins_regression_compare import (
    RegressionComparisonResult,
    compare_regressions,
    compare_regressions_batch,
)
from elins_regression_economic_coercion import (
    TimelineEconomic,
    TimePointEconomic,
)
from elins_regression_single_party import (
    Timeline,
    TimePoint,
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


def _sp_flat(tid: str = "sp_flat") -> Timeline:
    return Timeline(
        timeline_id=tid,
        points=tuple(_sp_tp(t=f"t{i}") for i in range(2)),
    )


def _ec_flat(tid: str = "ec_flat") -> TimelineEconomic:
    return TimelineEconomic(
        timeline_id=tid,
        points=tuple(_ec_tp(t=f"t{i}") for i in range(2)),
    )


def _sp_rising(tid: str = "sp_rising") -> Timeline:
    return Timeline(
        timeline_id=tid,
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


def _ec_rising(tid: str = "ec_rising") -> TimelineEconomic:
    return TimelineEconomic(
        timeline_id=tid,
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


def _batch_payload(*pairs) -> dict:
    return {"pairs": [_payload_pair(sp, ec) for (sp, ec) in pairs]}


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
# A. compare_regressions_batch core
# ===========================================================================
class TestBatchCore:
    def test_empty_list_returns_empty_list(self):
        assert compare_regressions_batch([]) == []

    def test_single_pair_returns_one_element(self):
        result = compare_regressions_batch([(_sp_rising(), _ec_rising())])
        assert len(result) == 1

    def test_single_pair_matches_compare_regressions(self):
        sp = _sp_rising()
        ec = _ec_rising()
        single = compare_regressions(sp, ec)
        batch = compare_regressions_batch([(sp, ec)])[0]
        assert batch == single

    def test_multiple_pairs_preserve_order(self):
        pairs = [
            (_sp_rising("a"), _ec_rising("a")),
            (_sp_empty(), _ec_empty()),
            (_sp_flat("c"), _ec_flat("c")),
        ]
        result = compare_regressions_batch(pairs)
        assert len(result) == 3
        assert result[0].single_party_score >= 9   # rising → strong
        assert result[1].single_party_score == 0   # empty → 0
        # Order check via timeline-id passthrough is implicit in the
        # underlying validators; here we just rely on the score pattern.

    def test_each_element_matches_direct_compare(self):
        pairs = [
            (_sp_rising("a"), _ec_rising("a")),
            (_sp_flat("b"), _ec_flat("b")),
            (_sp_empty(), _ec_empty()),
        ]
        batch = compare_regressions_batch(pairs)
        for (sp, ec), b in zip(pairs, batch):
            assert b == compare_regressions(sp, ec)

    def test_returns_list_of_result_dataclasses(self):
        result = compare_regressions_batch([(_sp_empty(), _ec_empty())])
        assert all(isinstance(r, RegressionComparisonResult) for r in result)

    def test_non_list_raises_value_error(self):
        with pytest.raises(ValueError, match="expected a list"):
            compare_regressions_batch("not a list")  # type: ignore[arg-type]

    def test_pair_not_2_element_raises(self):
        with pytest.raises(ValueError, match="2-element tuple"):
            compare_regressions_batch([(_sp_empty(),)])  # type: ignore[list-item]

    def test_pair_with_three_elements_raises(self):
        with pytest.raises(ValueError, match="2-element tuple"):
            compare_regressions_batch([(_sp_empty(), _ec_empty(), "extra")])  # type: ignore[list-item]

    def test_pair_not_tuple_or_list_raises(self):
        with pytest.raises(ValueError, match="2-element tuple"):
            compare_regressions_batch(["not a pair"])  # type: ignore[list-item]

    def test_pair_with_wrong_inner_type_propagates(self):
        with pytest.raises(ValueError):
            compare_regressions_batch([("not a timeline", _ec_empty())])  # type: ignore[list-item]

    def test_lists_inside_pairs_accepted(self):
        """Pair entries can be lists, not just tuples."""
        result = compare_regressions_batch([[_sp_empty(), _ec_empty()]])
        assert len(result) == 1

    def test_five_pairs_preserve_order_via_score_pattern(self):
        """Order is preserved across a 5-element batch."""
        pairs = [
            (_sp_rising("a"), _ec_empty()),    # delta = -9 (sp wins)
            (_sp_empty(),     _ec_rising("b")),  # delta = +10 (ec wins)
            (_sp_rising("c"), _ec_rising("c")),  # delta near 0 (both Strong)
            (_sp_empty(),     _ec_empty()),    # delta = 0
            (_sp_flat("e"),   _ec_flat("e")),  # delta near 0
        ]
        result = compare_regressions_batch(pairs)
        assert len(result) == 5
        assert result[0].score_delta < 0
        assert result[1].score_delta > 0
        assert result[3].score_delta == 0

    def test_assertions_failed_per_pair_independent(self):
        """Each pair's assertion-failure list reflects its own data, not
        the previous or next pair."""
        pairs = [
            (_sp_rising("with_failures"), _ec_rising("with_failures")),
            (_sp_empty(),                 _ec_empty()),
        ]
        batch = compare_regressions_batch(pairs)
        # Empty timelines have no assertion failures (vacuous pass).
        assert batch[1].assertions_failed_single_party == ()
        assert batch[1].assertions_failed_economic == ()


class TestBatchModuleSurface:
    def test_batch_function_callable(self):
        assert callable(compare_regressions_batch)

    def test_batch_dashboard_callable(self):
        assert callable(etd.compare_regressions_batch_dashboard)


# ===========================================================================
# B. compare_regressions_batch_dashboard wrapper
# ===========================================================================
class TestBatchDashboard:
    def test_empty_returns_empty_list(self):
        assert etd.compare_regressions_batch_dashboard([]) == []

    def test_single_pair_returns_one_dict(self):
        out = etd.compare_regressions_batch_dashboard(
            [(_sp_rising(), _ec_rising())])
        assert len(out) == 1
        assert isinstance(out[0], dict)

    def test_single_pair_dict_matches_single_dashboard(self):
        sp = _sp_rising()
        ec = _ec_rising()
        single = etd.compare_regressions_dashboard(sp, ec)
        batch_first = etd.compare_regressions_batch_dashboard([(sp, ec)])[0]
        assert batch_first == single

    def test_required_keys_per_element(self):
        out = etd.compare_regressions_batch_dashboard(
            [(_sp_rising(), _ec_rising())])
        for entry in out:
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
                assert key in entry

    def test_three_pairs_three_dicts(self):
        pairs = [
            (_sp_rising("a"), _ec_rising("a")),
            (_sp_empty(),     _ec_empty()),
            (_sp_flat("c"),   _ec_flat("c")),
        ]
        out = etd.compare_regressions_batch_dashboard(pairs)
        assert len(out) == 3

    def test_score_delta_label_economic_higher(self):
        # ec rising scores 10, sp empty scores 0 → +10
        out = etd.compare_regressions_batch_dashboard(
            [(_sp_empty(), _ec_rising())])
        assert "economic coercion" in out[0]["score_delta_label"]
        assert out[0]["score_delta"] >= 9

    def test_score_delta_label_single_party_higher(self):
        out = etd.compare_regressions_batch_dashboard(
            [(_sp_rising(), _ec_empty())])
        assert "single party fear" in out[0]["score_delta_label"]

    def test_score_delta_label_tied(self):
        out = etd.compare_regressions_batch_dashboard(
            [(_sp_empty(), _ec_empty())])
        assert out[0]["score_delta_label"] == "tied"

    def test_band_delta_label_up(self):
        out = etd.compare_regressions_batch_dashboard(
            [(_sp_empty(), _ec_rising())])
        assert out[0]["band_delta"] == "up"
        assert "higher" in out[0]["band_delta_label"]

    def test_band_delta_label_same(self):
        out = etd.compare_regressions_batch_dashboard(
            [(_sp_empty(), _ec_empty())])
        assert out[0]["band_delta"] == "same"
        assert "tied at" in out[0]["band_delta_label"]

    def test_assertions_serialised_as_lists(self):
        out = etd.compare_regressions_batch_dashboard(
            [(_sp_rising(), _ec_rising())])
        assert isinstance(out[0]["assertions_failed_single_party"], list)
        assert isinstance(out[0]["assertions_failed_economic"], list)


# ===========================================================================
# C. Endpoint behavior
# ===========================================================================
class TestEndpoint:
    def test_valid_payload_200(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload((_sp_rising(), _ec_rising())),
            headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_is_list(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload((_sp_rising(), _ec_rising())),
            headers=_auth(sid),
        )
        assert isinstance(resp.json(), list)

    def test_empty_pairs_returns_200_empty_list(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json={"pairs": []},
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_three_pairs_three_elements(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload(
                (_sp_rising("a"), _ec_rising("a")),
                (_sp_empty(),     _ec_empty()),
                (_sp_flat("c"),   _ec_flat("c")),
            ),
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 3

    def test_unauth_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload((_sp_rising(), _ec_rising())),
        )
        assert resp.status_code == 401

    def test_missing_pairs_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json={},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_pairs_not_list_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json={"pairs": "not a list"},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_pair_not_object_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json={"pairs": ["not an object"]},
            headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_missing_sp_timeline_in_pair_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        del payload["pairs"][0]["single_party_timeline"]
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_missing_ec_timeline_in_pair_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        del payload["pairs"][0]["economic_timeline"]
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_missing_required_field_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        del payload["pairs"][0]["single_party_timeline"]["points"][0]["fear_signal"]
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_ec_non_numeric_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        payload["pairs"][0]["economic_timeline"]["points"][0]["compliance_signal"] = "high"
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_bool_for_numeric_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        payload["pairs"][0]["single_party_timeline"]["points"][0]["fear_signal"] = True
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_non_string_t_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        payload["pairs"][0]["single_party_timeline"]["points"][0]["t"] = 99
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_sp_empty_timeline_id_400(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        payload["pairs"][0]["single_party_timeline"]["timeline_id"] = ""
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_empty_points_in_sp_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload((_sp_empty(), _ec_rising())),
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["single_party_score"] == 0
        assert body[0]["single_party_band"] == "Fails core logic"

    def test_empty_points_in_ec_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload((_sp_rising(), _ec_empty())),
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["economic_coercion_score"] == 0
        assert body[0]["economic_coercion_band"] == "Fails core logic"

    def test_both_empty_points_accepted(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload((_sp_empty(), _ec_empty())),
            headers=_auth(sid),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["score_delta"] == 0
        assert body[0]["band_delta"] == "same"

    def test_response_matches_direct_dashboard(self, client, app_module):
        sid = _make_user_session(app_module)
        pairs = [
            (_sp_rising("a"), _ec_rising("a")),
            (_sp_empty(),     _ec_empty()),
        ]
        direct = etd.compare_regressions_batch_dashboard(pairs)
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload(*pairs),
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        r1 = client.post("/elins/regression/compare_batch",
                         json=payload, headers=_auth(sid))
        r2 = client.post("/elins/regression/compare_batch",
                         json=payload, headers=_auth(sid))
        assert r1.json() == r2.json()


# ===========================================================================
# D. Per-pair index in error messages
# ===========================================================================
class TestErrorMessageIndices:
    def test_error_includes_pair_index(self, client, app_module):
        """When validation fails on the second pair, the error message
        includes pairs[1] so callers can debug."""
        sid = _make_user_session(app_module)
        payload = _batch_payload(
            (_sp_rising("a"), _ec_rising("a")),
            (_sp_rising("b"), _ec_rising("b")),
        )
        # Break the second pair's first sp point.
        payload["pairs"][1]["single_party_timeline"]["points"][0]["fear_signal"] = "bad"
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400
        body = resp.json()
        # Detail is dict-shaped per error_response helper.
        msg = str(body)
        assert "pairs[1]" in msg
        assert "single_party_timeline" in msg

    def test_error_includes_point_index(self, client, app_module):
        sid = _make_user_session(app_module)
        payload = _batch_payload((_sp_rising(), _ec_rising()))
        # Break the third sp point.
        payload["pairs"][0]["single_party_timeline"]["points"][2]["repression_index"] = None
        resp = client.post(
            "/elins/regression/compare_batch",
            json=payload, headers=_auth(sid),
        )
        assert resp.status_code == 400
        msg = str(resp.json())
        assert "points[2]" in msg


# ===========================================================================
# E. Determinism + no input mutation
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeated_batch_calls(self):
        pairs = [
            (_sp_rising("a"), _ec_rising("a")),
            (_sp_flat("b"),   _ec_flat("b")),
        ]
        r1 = compare_regressions_batch(pairs)
        r2 = compare_regressions_batch(pairs)
        assert r1 == r2

    def test_dashboard_byte_equal_repeated(self):
        pairs = [
            (_sp_rising("a"), _ec_rising("a")),
            (_sp_flat("b"),   _ec_flat("b")),
        ]
        r1 = etd.compare_regressions_batch_dashboard(pairs)
        r2 = etd.compare_regressions_batch_dashboard(pairs)
        assert r1 == r2

    def test_input_pairs_not_mutated(self):
        sp = _sp_rising()
        ec = _ec_rising()
        pairs = [(sp, ec)]
        before_sp = tuple((p.t, p.fear_signal) for p in sp.points)
        before_ec = tuple((p.t, p.compliance_signal) for p in ec.points)
        before_pairs_len = len(pairs)
        compare_regressions_batch(pairs)
        after_sp = tuple((p.t, p.fear_signal) for p in sp.points)
        after_ec = tuple((p.t, p.compliance_signal) for p in ec.points)
        assert before_sp == after_sp
        assert before_ec == after_ec
        assert len(pairs) == before_pairs_len


# ===========================================================================
# F. Source-code purity
# ===========================================================================
class TestPurity:
    def _src(self) -> str:
        return inspect.getsource(cmp_mod.compare_regressions_batch)

    def test_no_llm_imports(self):
        src = self._src()
        for forbidden in ("openai", "anthropic", "intelligence_kernel",
                          "perplexity_oracle", "model_router"):
            assert forbidden not in src

    def test_no_network(self):
        src = self._src()
        for forbidden in ("urlopen(", "requests.", ".post(", ".put(", "smtplib"):
            assert forbidden not in src

    def test_no_io(self):
        src = self._src()
        for forbidden in ("open(", "Path(", "json.load", "subprocess",
                          "exec(", "eval("):
            assert forbidden not in src

    def test_no_logging(self):
        src = self._src()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._src()
        for forbidden in ("random.", "secrets."):
            assert forbidden not in src

    def test_dashboard_wrapper_no_basin_imports(self):
        """The dashboard wrapper module must not import basin inference."""
        src = inspect.getsource(etd)
        for pattern in (
            "import elins_dashboard", "from elins_dashboard",
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
        ):
            assert pattern not in src


# ===========================================================================
# G. Existing endpoints unaffected
# ===========================================================================
class TestExistingEndpointsUnaffected:
    def test_health_still_works(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_single_party_endpoint_still_works(self, client, app_module):
        sid = _make_user_session(app_module)
        sp_payload = _batch_payload((_sp_flat(), _ec_flat()))["pairs"][0]["single_party_timeline"]
        resp = client.post(
            "/elins/regression/single_party_fear",
            json=sp_payload, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_economic_endpoint_still_works(self, client, app_module):
        sid = _make_user_session(app_module)
        ec_payload = _batch_payload((_sp_flat(), _ec_flat()))["pairs"][0]["economic_timeline"]
        resp = client.post(
            "/elins/regression/economic_coercion",
            json=ec_payload, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_single_pair_compare_endpoint_still_works(self, client, app_module):
        sid = _make_user_session(app_module)
        single_payload = _batch_payload((_sp_flat(), _ec_flat()))["pairs"][0]
        resp = client.post(
            "/elins/regression/compare",
            json=single_payload, headers=_auth(sid),
        )
        assert resp.status_code == 200


# ===========================================================================
# H. End-to-end smoke
# ===========================================================================
class TestEndToEnd:
    def test_full_chain_three_pair_batch(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/compare_batch",
            json=_batch_payload(
                (_sp_rising("rising"), _ec_rising("rising")),
                (_sp_empty(),          _ec_empty()),
                (_sp_flat("flat"),     _ec_flat("flat")),
            ),
            headers=_auth(sid),
        )
        body = resp.json()
        assert len(body) == 3
        # First pair: both Strong (rising timelines).
        assert body[0]["single_party_band"] == "Strong"
        assert body[0]["economic_coercion_band"] == "Strong"
        # Second pair: both Fails core logic (empty timelines).
        assert body[1]["single_party_band"] == "Fails core logic"
        assert body[1]["economic_coercion_band"] == "Fails core logic"
        assert body[1]["band_delta"] == "same"
        # Third pair: scenario-results dicts present per element.
        for entry in body:
            assert isinstance(entry["scenario_results_single_party"], dict)
            assert isinstance(entry["scenario_results_economic"], dict)
