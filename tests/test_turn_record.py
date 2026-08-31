"""
The per-turn record — the seat rule, the three-valued trust, and the first
assertion ever written against ``_build_s_strategy_layer``.

★ WHAT THESE PIN

The seat rule is the whole reason the record is two-phase. If the
expectation can be written after the return is seen, the residual is
fitted and the record is worse than nothing: it looks like evidence.
``test_seat_rule_*`` pin that the violation is REJECTED, not warned about.

D5 — a turn with no prior returns a DIFFERENT KIND OF THING, never 0.0.
Three statuses, and the tests pin all three, because collapsing "nothing
to compare" into "zero match" is the failure this record exists to avoid.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import pytest  # noqa: E402

import memory_vault  # noqa: E402
import turn_record as tr  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    memory_vault._reset_for_tests()
    tr._reset_seq_for_tests()
    yield


U = "u_turn"
T = "thread1"


# --------------------------------------------------------------------------
# The seat rule
# --------------------------------------------------------------------------
def test_seat_rule_seal_precedes_observe_on_the_happy_path():
    key = tr.seal_expectation(U, T, 0, {"boundary": "clear"})
    rec = tr.observe_return(U, key, {"boundary": "clear"})
    # Ordering is causal; the clock may report equal stamps inside one
    # ~15.6 ms tick. What must never happen is a LATER seal.
    assert rec["ts_sealed"] <= rec["ts_observed"]
    assert rec["observation"] == {"boundary": "clear"}


def test_seat_rule_rejects_a_record_sealed_after_the_return():
    """★ THE INVARIANT. A ts_sealed in the future means the expectation was
    written knowing the return. The write is refused, not flagged."""
    key = tr.seal_expectation(U, T, 0, {"boundary": "clear"})
    rec = memory_vault.vault_get(U, key)
    rec["ts_sealed"] = rec["ts_sealed"] + 10_000_000_000  # +10s in ns: seal "after" the return
    memory_vault.vault_put(U, key, rec)

    with pytest.raises(ValueError, match="SEAT RULE VIOLATED"):
        tr.observe_return(U, key, {"boundary": "clear"})

    # and the observation did not land
    assert memory_vault.vault_get(U, key)["observation"] is None


def test_a_sealed_expectation_takes_exactly_one_return():
    key = tr.seal_expectation(U, T, 0, {"boundary": "clear"})
    tr.observe_return(U, key, {"boundary": "clear"})
    with pytest.raises(ValueError, match="already observed"):
        tr.observe_return(U, key, {"boundary": "soft"})


# --------------------------------------------------------------------------
# E-prime — bearings, never verdicts
# --------------------------------------------------------------------------
def test_prose_is_refused_in_an_expectation():
    with pytest.raises(ValueError, match="whitespace"):
        tr.seal_expectation(U, T, 0, {"boundary": "he is being defensive"})


def test_prose_is_refused_in_an_observation():
    key = tr.seal_expectation(U, T, 0, {"boundary": "clear"})
    with pytest.raises(ValueError):
        tr.observe_return(U, key, {"notes": "a" * 80})


# --------------------------------------------------------------------------
# No truncation at write
# --------------------------------------------------------------------------
def test_the_writer_holds_no_window():
    """operator_state prunes to HISTORY_MAX=200 at write. This does not:
    a window baked in at write is a conclusion stored as an observable."""
    for i in range(250):
        k = tr.seal_expectation(U, T, i, {"boundary": "clear"})
        tr.observe_return(U, k, {"boundary": "clear"})
    assert len(tr.list_turn_records(U, T)) == 250
    # the window is the READER's parameter
    assert len(tr.list_turn_records(U, T, window=7)) == 7


# --------------------------------------------------------------------------
# D5 — three kinds of return
# --------------------------------------------------------------------------
def test_no_prior_yet_is_not_zero():
    """★ Turn 1 has nothing to have expected. Reporting 0.0 would state a
    reading the record does not hold."""
    out = tr.trust_signal(U, T)
    assert out["status"] == "no_prior_yet"
    assert "value" not in out


def test_undefined_when_no_claim_was_ever_made():
    """An expectation carrying only provenance claims nothing, so the rate
    has no denominator. Not 0.0 -- a different kind of thing."""
    k = tr.seal_expectation(U, T, 0, {"source": tr.SOURCE_PERSISTENCE})
    tr.observe_return(U, k, {"boundary": "clear"})
    out = tr.trust_signal(U, T)
    assert out["status"] == "undefined"
    assert "value" not in out


def test_an_unmet_claim_scores_as_a_miss_not_as_undefined():
    """★ A claim that did not land is a MISS. Only the absence of a claim
    is undefined. Collapsing the two would hide every wrong prediction."""
    k = tr.seal_expectation(U, T, 0, {"pressure_score": 3})
    rec = tr.observe_return(U, k, {"pressure_score": 5})
    s = tr.score_record(rec)
    assert s["per_bearing"]["pressure_score"] == "missed"
    assert s["missed"] == 1


def test_absence_expecting_absence_counts_as_a_match():
    """CT-1: absence expecting absence is a trust INCREASE. Absence with no
    expectation is UNDEFINED. Two different things."""
    k = tr.seal_expectation(U, T, 0, {"boundary": "clear", "agency": None})
    rec = tr.observe_return(U, k, {"boundary": "clear"})
    s = tr.score_record(rec)
    assert s["per_bearing"]["agency"] == "matched"      # None expected, None seen
    assert s["per_bearing"]["distance"] == "undefined"  # never claimed


# --------------------------------------------------------------------------
# ★ D1 — MOTION. The direction is the acceptance test.
# --------------------------------------------------------------------------
def test_turn_2_gives_a_value_but_no_direction():
    for i, (e, o) in enumerate([("clear", "clear")]):
        k = tr.seal_expectation(U, T, i, {"boundary": e})
        tr.observe_return(U, k, {"boundary": o})
    out = tr.trust_signal(U, T)
    assert out["status"] == "value"
    assert "direction" not in out, "a direction needs two points"


def test_turn_3_states_a_direction_turn_2_could_not():
    """★ THE PERTURBATION. One scored turn yields a value and no slope.
    A second yields a slope. The surface says something at turn 3 that it
    could not say at turn 2 -- an unmoved gauge would fail this."""
    k1 = tr.seal_expectation(U, T, 0, {"boundary": "clear"})
    tr.observe_return(U, k1, {"boundary": "clear"})          # 1/1
    at_turn_2 = tr.trust_signal(U, T)

    k2 = tr.seal_expectation(U, T, 1, {"boundary": "clear"})
    tr.observe_return(U, k2, {"boundary": "soft"})           # 0/1
    at_turn_3 = tr.trust_signal(U, T)

    assert "direction" not in at_turn_2
    assert at_turn_3["direction"] == "falling"
    assert at_turn_3["delta"] < 0
    assert at_turn_3["value"] < at_turn_2["value"]


def test_theta_floor_is_reported_never_enforced_at_write():
    for i in range(7):
        k = tr.seal_expectation(U, T, i, {"boundary": "clear"})
        tr.observe_return(U, k, {"boundary": "clear"})
    out = tr.trust_signal(U, T)
    assert out["theta_floor"] == 7
    assert out["theta_ready"] is True


# --------------------------------------------------------------------------
# ★ GATE 5 — the first assertion ever written on _build_s_strategy_layer
# --------------------------------------------------------------------------
def test_s_strategy_seven_field_gate_returns_empty_when_one_field_is_missing():
    """★ FIRST TEST ON THIS PATH. The builder has a seven-field required
    gate (app.py:4824-4828) and shipped with zero coverage.

    Absence returns {} -- a different kind of thing than a computed
    overlay, which is why the rail reads "0 keys" rather than a number."""
    import app as app_module

    full = {
        "hydronic_state": {
            "hci": 0.4, "flow_rate": 0.9, "compression_ratio": 0.1, "entropy": 0.3,
        },
        "contradiction_load": {"cx_value": 0.2, "p_mis": 0.1},
        "markoff_state": {"variance": 0.5},
    }
    built = app_module._build_s_strategy_layer(full, None)
    assert built, "all seven present should build a non-empty overlay"
    assert built["cohesion"] == pytest.approx(0.8)   # 1 - cx_value

    for block, field in (
        ("hydronic_state", "hci"), ("hydronic_state", "flow_rate"),
        ("hydronic_state", "compression_ratio"), ("hydronic_state", "entropy"),
        ("contradiction_load", "cx_value"), ("contradiction_load", "p_mis"),
        ("markoff_state", "variance"),
    ):
        partial = {k: dict(v) for k, v in full.items()}
        partial[block].pop(field)
        assert app_module._build_s_strategy_layer(partial, None) == {}, (
            "missing %s.%s must gate the whole overlay to {}" % (block, field)
        )


def test_s_strategy_basin_hop_is_the_only_term_that_reads_a_prior():
    """★ basin_hop compares supply NOW against supply PRIOR -- the only
    time term in the overlay, and the reason the per-turn record exists."""
    import app as app_module

    base = {
        "hydronic_state": {
            "hci": 0.4, "flow_rate": 0.9, "compression_ratio": 0.1, "entropy": 0.3,
        },
        "contradiction_load": {"cx_value": 0.2, "p_mis": 0.1},
        "markoff_state": {"variance": 0.5},
    }
    prior_low = {"hydronic_state": {"flow_rate": 0.1}}
    prior_high = {"hydronic_state": {"flow_rate": 0.89}}

    assert app_module._build_s_strategy_layer(base, prior_low)["basin_hop"] is True
    assert app_module._build_s_strategy_layer(base, prior_high)["basin_hop"] is False
