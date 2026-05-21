"""
Tests for ELINS Unit 16 — drift severity classifier.

Layered coverage (≥ 60 tests, target 70+):
    A. _direction_per_pair helper
    B. _severity_for_max_swing helper + boundary thresholds
    C. classify_drift_severity core
    D. Pair presence / mismatched inputs
    E. Validation
    F. Wrapper — classify_drift_severity_for_run_ids
    G. Endpoint — POST /elins/regression/drift/severity
    H. Determinism + ordering
    I. Source-code purity / module surface
    J. End-to-end via persistence
"""
from __future__ import annotations

import inspect
import secrets
import time
from pathlib import Path

import pytest
from conftest import TestClient

import elins_persistence as ep
import elins_run_drift_severity as sev_mod


# ===========================================================================
# Fixtures — runs-dir isolation per test
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


# ===========================================================================
# Inline helpers for direction / magnitude shapes
# ===========================================================================
def _empty_direction() -> dict:
    return {
        "stable": [], "trending_up": [], "trending_down": [], "volatile": [],
        "summary": {"stable": 0, "trending_up": 0,
                    "trending_down": 0, "volatile": 0},
    }


def _direction_with(bucket: str, *pair_ids) -> dict:
    out = _empty_direction()
    out[bucket] = list(pair_ids)
    out["summary"][bucket] = len(pair_ids)
    return out


def _magnitude_for(pair_id: str,
                   sp_swing: int = 0, sp_range: int = 0,
                   ec_swing: int = 0, ec_range: int = 0) -> dict:
    return {pair_id: {
        "single_party": {
            "range": sp_range, "max_swing": sp_swing, "mean_step": float(sp_swing),
        },
        "economic_coercion": {
            "range": ec_range, "max_swing": ec_swing, "mean_step": float(ec_swing),
        },
    }}


def _entry(pair_id: str = "p::a", *, sp: int = 5, ec: int = 5) -> dict:
    return {
        "pair_id": pair_id,
        "single_party_score": sp,
        "economic_coercion_score": ec,
    }


# ===========================================================================
# A. _direction_per_pair helper
# ===========================================================================
class TestDirectionPerPair:
    def test_empty_input(self):
        assert sev_mod._direction_per_pair({}) == {}

    def test_each_bucket_inverted(self):
        d = {
            "stable":        ["a"],
            "trending_up":   ["b"],
            "trending_down": ["c"],
            "volatile":      ["d"],
        }
        out = sev_mod._direction_per_pair(d)
        assert out == {"a": "stable", "b": "trending_up",
                       "c": "trending_down", "d": "volatile"}

    def test_multiple_pairs_per_bucket(self):
        d = {"stable": ["a", "b"], "trending_up": ["c"]}
        out = sev_mod._direction_per_pair(d)
        assert out["a"] == "stable"
        assert out["b"] == "stable"
        assert out["c"] == "trending_up"

    def test_summary_key_ignored(self):
        """The 'summary' key in Unit 13 output isn't a bucket — should
        be ignored by the inverter."""
        d = _empty_direction()
        d["stable"] = ["x"]
        out = sev_mod._direction_per_pair(d)
        assert out == {"x": "stable"}

    def test_non_list_bucket_skipped(self):
        d = {"stable": "not a list", "trending_up": ["x"]}
        out = sev_mod._direction_per_pair(d)
        assert out == {"x": "trending_up"}

    def test_non_string_pair_id_skipped(self):
        d = {"stable": ["a", 42, None]}
        out = sev_mod._direction_per_pair(d)
        assert out == {"a": "stable"}


# ===========================================================================
# B. _severity_for_max_swing helper + boundary tests
# ===========================================================================
class TestSeverityForMaxSwing:
    @pytest.mark.parametrize("swing,expected", [
        (0, "none"),
        (1, "weak"),
        (2, "weak"),
        (3, "moderate"),
        (4, "moderate"),
        (5, "strong"),
        (6, "strong"),
        (10, "strong"),
        (100, "strong"),
    ])
    def test_severity_map(self, swing, expected):
        assert sev_mod._severity_for_max_swing(swing) == expected

    def test_negative_swing_clamped_to_none(self):
        """Defensive: negative swings (out-of-contract) clamp to none."""
        assert sev_mod._severity_for_max_swing(-1) == "none"

    def test_boundary_2_to_3_transition(self):
        assert sev_mod._severity_for_max_swing(2) == "weak"
        assert sev_mod._severity_for_max_swing(3) == "moderate"

    def test_boundary_4_to_5_transition(self):
        assert sev_mod._severity_for_max_swing(4) == "moderate"
        assert sev_mod._severity_for_max_swing(5) == "strong"

    def test_severity_constants_locked(self):
        assert sev_mod._SEVERITY_NONE == "none"
        assert sev_mod._SEVERITY_WEAK == "weak"
        assert sev_mod._SEVERITY_MODERATE == "moderate"
        assert sev_mod._SEVERITY_STRONG == "strong"

    def test_threshold_constants_locked(self):
        assert sev_mod._WEAK_MAX_SWING == 2
        assert sev_mod._MODERATE_MAX_SWING == 4


# ===========================================================================
# C. classify_drift_severity core
# ===========================================================================
class TestCoreClassification:
    def test_stable_zero_magnitude(self):
        d = _direction_with("stable", "p1")
        m = _magnitude_for("p1", sp_swing=0, ec_swing=0)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "stable"
        assert out["p1"]["severity"] == "none"
        assert out["p1"]["direction"] == "stable"

    def test_stable_overrides_severity_even_if_swing_present(self):
        """Defensive: stable always means severity=none, regardless of
        any computed magnitude."""
        d = _direction_with("stable", "p1")
        m = _magnitude_for("p1", sp_swing=8, ec_swing=8)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "stable"
        assert out["p1"]["severity"] == "none"

    def test_trending_up_weak(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=2, ec_swing=0)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "trending_up_weak"
        assert out["p1"]["severity"] == "weak"

    def test_trending_up_moderate(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=4, ec_swing=2)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "trending_up_moderate"

    def test_trending_up_strong(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=6, ec_swing=2)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "trending_up_strong"

    def test_trending_down_weak(self):
        d = _direction_with("trending_down", "p1")
        m = _magnitude_for("p1", sp_swing=1, ec_swing=0)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "trending_down_weak"

    def test_trending_down_moderate(self):
        d = _direction_with("trending_down", "p1")
        m = _magnitude_for("p1", sp_swing=3, ec_swing=4)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "trending_down_moderate"

    def test_trending_down_strong(self):
        d = _direction_with("trending_down", "p1")
        m = _magnitude_for("p1", sp_swing=10, ec_swing=10)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "trending_down_strong"

    def test_volatile_strong(self):
        """Naming convention: 'volatile_strong' (not 'volatile_high_swing').
        Locked per work-set formula label = f'{direction}_{severity}'."""
        d = _direction_with("volatile", "p1")
        m = _magnitude_for("p1", sp_swing=8, ec_swing=2)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "volatile_strong"

    def test_volatile_weak(self):
        d = _direction_with("volatile", "p1")
        m = _magnitude_for("p1", sp_swing=1, ec_swing=2)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "volatile_weak"

    def test_volatile_moderate(self):
        d = _direction_with("volatile", "p1")
        m = _magnitude_for("p1", sp_swing=3, ec_swing=3)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "volatile_moderate"

    def test_max_swing_uses_larger_dimension(self):
        """Severity comes from max(sp_swing, ec_swing)."""
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=2, ec_swing=6)
        # max=6 → strong (ec dimension drives it)
        assert sev_mod.classify_drift_severity(d, m)["p1"]["label"] == "trending_up_strong"

    def test_max_swing_uses_sp_when_larger(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=5, ec_swing=1)
        # max=5 → strong
        assert sev_mod.classify_drift_severity(d, m)["p1"]["label"] == "trending_up_strong"

    def test_output_carries_per_dimension_max_swing(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=3, ec_swing=7, sp_range=4, ec_range=8)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["max_swing"] == {
            "single_party": 3, "economic_coercion": 7,
        }
        assert out["p1"]["range"] == {
            "single_party": 4, "economic_coercion": 8,
        }

    def test_output_keys_locked(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=2)
        out = sev_mod.classify_drift_severity(d, m)
        assert set(out["p1"].keys()) == {
            "label", "direction", "severity", "max_swing", "range",
        }

    def test_max_swing_subdict_keys_locked(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=2)
        out = sev_mod.classify_drift_severity(d, m)
        assert set(out["p1"]["max_swing"].keys()) == {
            "single_party", "economic_coercion",
        }

    def test_range_subdict_keys_locked(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=2)
        out = sev_mod.classify_drift_severity(d, m)
        assert set(out["p1"]["range"].keys()) == {
            "single_party", "economic_coercion",
        }

    def test_multiple_pairs(self):
        d = {
            "stable":        ["alpha"],
            "trending_up":   ["beta"],
            "trending_down": ["gamma"],
            "volatile":      ["delta"],
        }
        m = {
            "alpha": _magnitude_for("alpha", sp_swing=0)["alpha"],
            "beta":  _magnitude_for("beta",  sp_swing=2)["beta"],
            "gamma": _magnitude_for("gamma", sp_swing=4)["gamma"],
            "delta": _magnitude_for("delta", sp_swing=8)["delta"],
        }
        out = sev_mod.classify_drift_severity(d, m)
        assert out["alpha"]["label"] == "stable"
        assert out["beta"]["label"] == "trending_up_weak"
        assert out["gamma"]["label"] == "trending_down_moderate"
        assert out["delta"]["label"] == "volatile_strong"

    def test_max_swing_zero_with_trending_yields_none_suffix(self):
        """Edge case (mathematically impossible from real data): direction
        says trending_up but magnitude says 0 swing. Defensive: yields
        'trending_up_none' per the formula."""
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=0, ec_swing=0)
        out = sev_mod.classify_drift_severity(d, m)
        assert out["p1"]["label"] == "trending_up_none"
        assert out["p1"]["severity"] == "none"


# ===========================================================================
# D. Pair presence / mismatched inputs
# ===========================================================================
class TestPairPresence:
    def test_pair_only_in_direction_skipped(self):
        d = _direction_with("trending_up", "in_dir_only")
        m = {}  # no entries
        assert sev_mod.classify_drift_severity(d, m) == {}

    def test_pair_only_in_magnitude_skipped(self):
        d = _empty_direction()
        m = _magnitude_for("in_mag_only", sp_swing=5)
        assert sev_mod.classify_drift_severity(d, m) == {}

    def test_intersection_only(self):
        d = {
            "stable":        ["both1"],
            "trending_up":   ["dir_only"],
            "trending_down": [],
            "volatile":      ["both2"],
        }
        m = {
            "both1": _magnitude_for("both1", sp_swing=0)["both1"],
            "both2": _magnitude_for("both2", sp_swing=4)["both2"],
            "mag_only": _magnitude_for("mag_only", sp_swing=3)["mag_only"],
        }
        out = sev_mod.classify_drift_severity(d, m)
        assert set(out.keys()) == {"both1", "both2"}

    def test_magnitude_entry_missing_subdicts_skipped(self):
        """Defensive: if a magnitude entry lacks the expected
        single_party/economic_coercion shape, skip the pair."""
        d = _direction_with("trending_up", "p1")
        m = {"p1": {"missing_dims": True}}
        assert sev_mod.classify_drift_severity(d, m) == {}

    def test_magnitude_entry_with_string_sub_swing_skipped(self):
        """If max_swing isn't a clean int, skip defensively."""
        d = _direction_with("trending_up", "p1")
        m = {"p1": {
            "single_party":      {"range": 0, "max_swing": "bad", "mean_step": 0.0},
            "economic_coercion": {"range": 0, "max_swing": 0, "mean_step": 0.0},
        }}
        assert sev_mod.classify_drift_severity(d, m) == {}

    def test_magnitude_entry_with_bool_swing_skipped(self):
        """bool is subclass of int but rejected as numeric."""
        d = _direction_with("trending_up", "p1")
        m = {"p1": {
            "single_party":      {"range": 0, "max_swing": True, "mean_step": 0.0},
            "economic_coercion": {"range": 0, "max_swing": 0, "mean_step": 0.0},
        }}
        assert sev_mod.classify_drift_severity(d, m) == {}


# ===========================================================================
# E. Validation
# ===========================================================================
class TestValidation:
    def test_non_dict_direction_raises(self):
        with pytest.raises(ValueError, match="dict for direction"):
            sev_mod.classify_drift_severity("nope", {})  # type: ignore[arg-type]

    def test_non_dict_magnitude_raises(self):
        with pytest.raises(ValueError, match="dict for magnitude"):
            sev_mod.classify_drift_severity({}, "nope")  # type: ignore[arg-type]

    def test_none_direction_raises(self):
        with pytest.raises(ValueError):
            sev_mod.classify_drift_severity(None, {})  # type: ignore[arg-type]

    def test_none_magnitude_raises(self):
        with pytest.raises(ValueError):
            sev_mod.classify_drift_severity({}, None)  # type: ignore[arg-type]

    def test_empty_dicts_returns_empty(self):
        out = sev_mod.classify_drift_severity({}, {})
        assert out == {}


# ===========================================================================
# F. Wrapper — classify_drift_severity_for_run_ids
# ===========================================================================
class TestWrapper:
    def test_loads_and_classifies_byte_equal_to_manual_chain(self):
        """Wrapper should equal: detect_drift + drift_magnitude +
        classify_drift_severity called manually on the same loaded runs."""
        from elins_run_drift import detect_drift
        from elins_run_drift_magnitude import drift_magnitude

        ep.save_comparison_result("c1", [_entry("p1", sp=5, ec=5)])
        ep.save_comparison_result("c2", [_entry("p1", sp=8, ec=5)])

        wrapped = sev_mod.classify_drift_severity_for_run_ids(["c1", "c2"])

        runs = [
            [_entry("p1", sp=5, ec=5)],
            [_entry("p1", sp=8, ec=5)],
        ]
        d = detect_drift(runs)
        m = drift_magnitude(runs)
        manual = sev_mod.classify_drift_severity(d, m)

        assert wrapped == manual

    def test_wrapper_three_runs(self):
        for i, sp in enumerate((5, 6, 10)):
            ep.save_comparison_result(
                f"sev_{i}",
                [_entry("p1", sp=sp, ec=5)],
            )
        out = sev_mod.classify_drift_severity_for_run_ids(
            ["sev_0", "sev_1", "sev_2"])
        # SP series: 5, 6, 10 → swings 1, 4 → max_swing=4 → moderate
        # EC series: 5, 5, 5 → max_swing=0
        # Direction: SP strictly increasing → trending_up
        assert out["p1"]["label"] == "trending_up_moderate"

    def test_wrapper_stable_pair(self):
        for i in range(3):
            ep.save_comparison_result(
                f"st_{i}", [_entry("p1", sp=5, ec=5)],
            )
        out = sev_mod.classify_drift_severity_for_run_ids(
            ["st_0", "st_1", "st_2"])
        assert out["p1"]["label"] == "stable"
        assert out["p1"]["severity"] == "none"

    def test_wrapper_volatile_pair(self):
        for i, sp in enumerate((5, 9, 5)):
            ep.save_comparison_result(
                f"vol_{i}", [_entry("p1", sp=sp, ec=5)],
            )
        out = sev_mod.classify_drift_severity_for_run_ids(
            ["vol_0", "vol_1", "vol_2"])
        # SP: 5,9,5 → max_swing=4. Direction: oscillation → volatile.
        assert out["p1"]["label"] == "volatile_moderate"

    def test_non_list_run_ids_raises(self):
        with pytest.raises(ValueError, match="expected a list"):
            sev_mod.classify_drift_severity_for_run_ids("nope")  # type: ignore[arg-type]

    def test_zero_run_ids_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            sev_mod.classify_drift_severity_for_run_ids([])

    def test_single_run_id_raises(self):
        with pytest.raises(ValueError, match=">= 2 runs"):
            sev_mod.classify_drift_severity_for_run_ids(["only"])

    def test_malformed_run_id_raises_value_error(self):
        with pytest.raises(ValueError):
            sev_mod.classify_drift_severity_for_run_ids(["bad/id", "x"])

    def test_missing_run_raises_filenotfound(self):
        ep.save_comparison_result("present", [_entry("p1")])
        with pytest.raises(FileNotFoundError):
            sev_mod.classify_drift_severity_for_run_ids(["present", "ghost"])

    def test_validates_all_ids_before_loading(self):
        ep.save_comparison_result("good", [_entry("p1")])
        with pytest.raises(ValueError):
            sev_mod.classify_drift_severity_for_run_ids(["good", "bad/id"])

    def test_chronological_order_drives_direction(self):
        """Unit 23 invariant: the wrapper reorders run_ids by
        ``metadata.created_at`` regardless of caller order. Run ids
        are chosen so alphabetical tiebreak matches save order —
        important on Windows where back-to-back saves can share a
        timestamp."""
        ep.save_comparison_result("r1", [_entry("p1", sp=2, ec=5)])
        ep.save_comparison_result("r2", [_entry("p1", sp=9, ec=5)])
        forward = sev_mod.classify_drift_severity_for_run_ids(["r1", "r2"])
        reverse = sev_mod.classify_drift_severity_for_run_ids(["r2", "r1"])
        assert forward["p1"]["direction"] == "trending_up"
        assert reverse == forward

    def test_empty_runs_via_wrapper_returns_empty(self):
        ep.save_comparison_result("e1", [])
        ep.save_comparison_result("e2", [])
        assert sev_mod.classify_drift_severity_for_run_ids(["e1", "e2"]) == {}

    def test_wrapper_with_three_pairs(self):
        ep.save_comparison_result("wr1", [
            _entry("a", sp=5, ec=5), _entry("b", sp=5, ec=5),
        ])
        ep.save_comparison_result("wr2", [
            _entry("a", sp=5, ec=5), _entry("b", sp=8, ec=5),
        ])
        out = sev_mod.classify_drift_severity_for_run_ids(["wr1", "wr2"])
        assert out["a"]["label"] == "stable"
        assert out["b"]["label"] == "trending_up_moderate"  # swing=3

    def test_wrapper_drops_partial_presence_pair(self):
        ep.save_comparison_result("pp1", [
            _entry("always", sp=5, ec=5), _entry("sometimes", sp=5, ec=5),
        ])
        ep.save_comparison_result("pp2", [
            _entry("always", sp=8, ec=5),
        ])
        out = sev_mod.classify_drift_severity_for_run_ids(["pp1", "pp2"])
        assert "always" in out
        assert "sometimes" not in out


# ===========================================================================
# G. Endpoint
# ===========================================================================
class TestEndpoint:
    def _store_three_runs(self):
        for i, sp in enumerate((5, 7, 10)):
            ep.save_comparison_result(
                f"ep_{i}", [_entry("p1", sp=sp, ec=5)],
            )

    def test_valid_returns_200(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("a", [_entry("p1")])
        ep.save_comparison_result("b", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["a", "b"]}, headers=_auth(sid),
        )
        assert resp.status_code == 200

    def test_response_shape_per_pair(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert "p1" in body
        assert set(body["p1"].keys()) == {
            "label", "direction", "severity", "max_swing", "range",
        }

    def test_severity_label_correct_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        # SP: 5,7,10 → swings 2,3 → max_swing=3 → moderate
        # Direction: strictly inc → trending_up
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["p1"]["label"] == "trending_up_moderate"

    def test_unauth_returns_401(self, client, app_module):
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["a", "b"]},
        )
        assert resp.status_code == 401

    def test_missing_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/severity",
            json={}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_run_ids_not_list_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": "nope"}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_zero_run_ids_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": []}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_one_run_id_returns_400(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("only", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["only"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400

    def test_malformed_run_id_returns_400_with_index(self, client, app_module):
        sid = _make_user_session(app_module)
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["good", "bad$id"]}, headers=_auth(sid),
        )
        assert resp.status_code == 400
        msg = str(resp.json())
        assert "run_ids[1]" in msg

    def test_missing_run_returns_404(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("present", [_entry("p1")])
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["present", "ghost"]},
            headers=_auth(sid),
        )
        assert resp.status_code == 404

    def test_response_matches_direct_wrapper(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        direct = sev_mod.classify_drift_severity_for_run_ids(
            ["ep_0", "ep_1", "ep_2"])
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        assert resp.json() == direct

    def test_byte_equal_repeated_responses(self, client, app_module):
        sid = _make_user_session(app_module)
        self._store_three_runs()
        r1 = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        r2 = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["ep_0", "ep_1", "ep_2"]},
            headers=_auth(sid),
        )
        assert r1.json() == r2.json()

    def test_empty_runs_returns_empty_dict(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("e1", [])
        ep.save_comparison_result("e2", [])
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["e1", "e2"]},
            headers=_auth(sid),
        )
        assert resp.json() == {}

    def test_stable_pair_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        for rid in ("st_a", "st_b"):
            ep.save_comparison_result(rid, [_entry("p1", sp=5, ec=5)])
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["st_a", "st_b"]},
            headers=_auth(sid),
        )
        body = resp.json()
        assert body["p1"]["label"] == "stable"
        assert body["p1"]["severity"] == "none"

    def test_volatile_pair_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        for i, sp in enumerate((5, 10, 5)):
            ep.save_comparison_result(
                f"vol_{i}", [_entry("p1", sp=sp, ec=5)],
            )
        resp = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["vol_0", "vol_1", "vol_2"]},
            headers=_auth(sid),
        )
        # SP: 5,10,5 → max_swing=5 → strong; oscillation → volatile
        assert resp.json()["p1"]["label"] == "volatile_strong"

    def test_two_pair_response_via_endpoint(self, client, app_module):
        sid = _make_user_session(app_module)
        ep.save_comparison_result("twoP_1", [
            _entry("a", sp=5, ec=5), _entry("b", sp=5, ec=5),
        ])
        ep.save_comparison_result("twoP_2", [
            _entry("a", sp=8, ec=5), _entry("b", sp=5, ec=9),
        ])
        body = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["twoP_1", "twoP_2"]},
            headers=_auth(sid),
        ).json()
        assert "a" in body and "b" in body
        # Both have swing=3 or 4 → moderate
        assert body["a"]["severity"] == "moderate"
        assert body["b"]["severity"] == "moderate"


# ===========================================================================
# H. Determinism + ordering
# ===========================================================================
class TestDeterminism:
    def test_byte_equal_repeated_calls(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=3)
        assert sev_mod.classify_drift_severity(d, m) == \
               sev_mod.classify_drift_severity(d, m)

    def test_alphabetical_pair_ordering(self):
        d = {
            "stable":        ["zeta", "alpha", "mid"],
            "trending_up":   [],
            "trending_down": [],
            "volatile":      [],
        }
        m = {
            "alpha": _magnitude_for("alpha", sp_swing=0)["alpha"],
            "mid":   _magnitude_for("mid",   sp_swing=0)["mid"],
            "zeta":  _magnitude_for("zeta",  sp_swing=0)["zeta"],
        }
        out = sev_mod.classify_drift_severity(d, m)
        assert list(out.keys()) == ["alpha", "mid", "zeta"]

    def test_inputs_not_mutated(self):
        d = _direction_with("trending_up", "p1")
        m = _magnitude_for("p1", sp_swing=3)
        before_d = repr(d)
        before_m = repr(m)
        sev_mod.classify_drift_severity(d, m)
        assert repr(d) == before_d
        assert repr(m) == before_m


# ===========================================================================
# I. Source-code purity / module surface
# ===========================================================================
class TestSourceCodePurity:
    def _src(self) -> str:
        return inspect.getsource(sev_mod)

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

    def test_no_logging(self):
        src = self._src()
        for forbidden in ("logging.", "logger.", "print("):
            assert forbidden not in src

    def test_no_randomness(self):
        src = self._src()
        for forbidden in ("import random", "from random",
                          "import secrets", "from secrets",
                          "uuid."):
            assert forbidden not in src

    def test_no_subprocess_or_eval(self):
        src = self._src()
        for forbidden in ("subprocess", "exec(", "eval("):
            assert forbidden not in src

    def test_classify_drift_severity_pure_no_open(self):
        """classify_drift_severity has no file I/O — only the wrapper does."""
        src = inspect.getsource(sev_mod.classify_drift_severity)
        assert "open(" not in src

    def test_no_basin_inference_imports(self):
        src = self._src()
        for pattern in (
            "import elins_dashboard", "from elins_dashboard",
            "import elins_scheduler", "from elins_scheduler",
            "import elins_entity_graph", "from elins_entity_graph",
            "import dewey_pipeline", "from dewey_pipeline",
        ):
            assert pattern not in src


class TestModuleSurface:
    def test_classify_drift_severity_callable(self):
        assert callable(sev_mod.classify_drift_severity)

    def test_wrapper_callable(self):
        assert callable(sev_mod.classify_drift_severity_for_run_ids)

    def test_direction_buckets_locked(self):
        assert sev_mod._DIRECTION_BUCKETS == (
            "stable", "trending_up", "trending_down", "volatile",
        )


# ===========================================================================
# J. End-to-end via persistence
# ===========================================================================
class TestEndToEnd:
    def test_store_then_severity(self, client, app_module):
        sid = _make_user_session(app_module)

        sp_payload = {
            "timeline_id": "case01_sp",
            "points": [
                {"t": "t0",
                 "regime_competition": 0.5, "autocratization": 0.5,
                 "repression_index": 0.5, "digital_repression": 0.5,
                 "perceived_threat": 0.5, "fear_signal": 0.5,
                 "dissent_capacity": 0.5, "normative_constraint": 0.5,
                 "support_buffer": 0.5},
            ],
        }
        ec_payload = {
            "timeline_id": "case01_ec",
            "points": [
                {"t": "t0",
                 "economic_pressure": 0.5, "material_insecurity": 0.5,
                 "state_coercion": 0.5, "compliance_signal": 0.5,
                 "resistance_capacity": 0.5, "support_buffer": 0.5},
            ],
        }
        store_body = {"pairs": [{
            "single_party_timeline": sp_payload,
            "economic_timeline":     ec_payload,
        }]}

        for rid in ("morning", "evening"):
            r = client.post("/elins/regression/store",
                            json={"run_id": rid, **store_body},
                            headers=_auth(sid))
            assert r.status_code == 200

        # Identical inputs → stable / none.
        s = client.post(
            "/elins/regression/drift/severity",
            json={"run_ids": ["morning", "evening"]},
            headers=_auth(sid),
        )
        assert s.status_code == 200
        body = s.json()
        assert body["case01_sp::case01_ec"]["label"] == "stable"
        assert body["case01_sp::case01_ec"]["severity"] == "none"
