"""#374 — absence is not an anomaly, not a sample, and not a forecast.

CT-1 ruled 2026-09-18: **an UNMAPPED record is neither a sample nor an
anomaly.** #355 stopped absence entering a computation as a value at three
sites; the same rule had to reach four more, all of them one layer out from
a site #355 had already corrected.

    SITE 1  ``el_ins.anomaly.detect_anomalies`` — every rule reads a
            POSITION (el/ins as coordinates, tsi as a level, the quadrant as
            a place). A 0/0 read has none, so all four rules were scoring the
            absence of a measurement. An UNMAPPED record now produces no
            anomalies, and an UNMAPPED *prior* counts as no prior.
    SITE 2  ``el_ins_store.compute_operator_summary`` — a fourth bucket
            ``unmapped``, out of the ratio and out of the TSI average.
    SITE 3  ``standard_elins._layer_6_forecast_5day`` — ``days[].phase``
            guards on ``no_signal`` like its sibling ``trend`` already did.

★★ WHAT THIS FILE IS FOR, GIVEN WHAT THE #355 BUILD COST. That build shipped
FIVE tautologies — assertions true by construction, each caught by a refuter
rather than by a test, on five different axes. So the rule here is: **every
test names the mutation that breaks it**, in its own docstring. If a test
cannot name one, it does not belong in this file.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import pytest  # noqa: E402

from ELINS import standard_elins as se  # noqa: E402
from el_ins import anomaly  # noqa: E402
from el_ins import el_ins_analyzer as A  # noqa: E402
from el_ins import el_ins_store as ST  # noqa: E402

UNMAPPED = A.RATIO_UNMAPPED


@pytest.fixture(autouse=True)
def _clean():
    ST._reset_for_tests()
    yield


def _result(cls, el, ins, mode="normal"):
    return {
        "analysis": {
            "el_score": el, "ins_score": ins,
            "ratio_classification": cls,
            "el_components": {}, "ins_components": {},
        },
        "reasoning_mode": mode,
        "regression_chain": {},
        "stability_notes": None,
    }


def _rec(cls, el, ins, *, tsi=None, mode="normal", ts=1000.0, tid="t374"):
    # tid=None is meaningful: an un-threaded record keeps the tsi it is given,
    # a threaded one has it re-stamped from the thread (el_ins_store.py:285).
    r = {
        "operator_id": "op_374", "thread_id": tid, "timestamp": ts,
        "source": "per_turn", "result": _result(cls, el, ins, mode),
    }
    if tsi is not None:
        r["tsi"] = tsi
    return r


# ==========================================================================
# SITE 1 — detect_anomalies
# ==========================================================================
def test_an_unmapped_record_fires_no_anomalies():
    """MUTATION THAT BREAKS THIS: delete the ``RATIO_UNMAPPED`` early
    return in ``detect_anomalies``.

    ★ THE MEASURED BEFORE-STATE, which is why this site exists: a thread of
    two stable balanced reads followed by one 0/0 turn fired THREE
    anomalies on that turn — ``low_ins`` (sev 3, ins 0.0 < 2.0),
    ``tsi_spike`` (sev 4, because #355 rightly excludes the frame from the
    TSI window so the record is stamped with the OTHER frames' 100), and
    ``quadrant_jump`` (sev 5, the quadrant "moving" from a place to
    nowhere). Pre-#355 the same frame scored into the window, TSI came out
    71, and nothing fired at all.
    """
    prior = _rec("balanced", 4.0, 3.0, tsi=70, ts=1000.0)
    unmapped = _rec(UNMAPPED, 0.0, 0.0, tsi=100, mode=A.MODE_UNMAPPED, ts=1001.0)
    assert anomaly.detect_anomalies(unmapped, prior_record=prior) == []
    # and with no prior at all, still nothing
    assert anomaly.detect_anomalies(unmapped) == []


def test_the_three_rules_that_fired_on_absence_each_still_fire_on_a_reading():
    """★ THE GUARD MUST NOT BE A BLANKET OFF-SWITCH.

    MUTATION THAT BREAKS THIS: make the early return unconditional, or key
    it on ``el == 0 and ins == 0`` instead of on the classification.

    Each of the three rules that used to fire on an UNMAPPED record is
    shown firing on a record that carries a real reading with the same
    numeric shape it would have had.
    """
    # low_ins: a REAL reading with low INS
    got = {a["type"] for a in anomaly.detect_anomalies(
        _rec("high_el", 9.0, 1.0, tsi=90))}
    assert "low_ins" in got and "high_el" in got and "tsi_spike" in got


def test_a_genuine_zero_zero_reading_that_predates_the_sentinel_is_still_scored():
    """#51 / #90 — NO RETROFIT.

    MUTATION THAT BREAKS THIS: key the guard on the SCORES (``el == 0 and
    ins == 0``) rather than on ``ratio_classification``.

    A record stored before #355 carries ``balanced`` for 0/0. Its meaning
    is fixed at write time and this leg does not reinterpret it: it is
    still scored exactly as it always was, ``low_ins`` and all.
    """
    old = _rec("balanced", 0.0, 0.0, tsi=50)
    got = {a["type"] for a in anomaly.detect_anomalies(old)}
    assert "low_ins" in got, "a pre-#355 record was silently re-read as absence"


def test_an_unmapped_prior_is_no_prior_so_no_quadrant_jump():
    """MUTATION THAT BREAKS THIS: drop the ``prior_record`` half of the
    guard and keep only the record half.

    ★ WHY IT IS ITS OWN RULE: a jump is a comparison of two positions. If
    the earlier one is UNMAPPED there is no "from", and reading it from
    0.0/0.0 places the prior in Q4 (stabilization) as though absence were
    a low-low reading — firing a spurious diagonal on the FIRST REAL READ
    after any quiet turn. With 0/0 common in ordinary conversation, that
    is the majority of real reads.

    ★★ THE PAIR IS CHOSEN SO THE RULE *WOULD* FIRE WITHOUT THE GUARD, and
    an earlier draft of this test was not. It used ``now = (1.0, 9.0)``,
    which is Q2; ``_quadrant(0.0, 0.0)`` is Q4, and Q4→Q2 is one axis
    change — distance 1, below ``_QUADRANT_JUMP_DISTANCE``. It could never
    fire with OR without the guard, so it passed either way. Q4→Q3 (EL
    high AND INS high) is the diagonal, distance 2, and is the only
    transition from an all-zero prior that reaches the threshold.
    """
    unmapped_prior = _rec(UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=1000.0)
    now = _rec("balanced", 9.0, 9.0, tsi=60, ts=1001.0)   # Q3
    # the fixture is only meaningful if the distance really does reach the
    # threshold — assert the geometry, not just the outcome
    assert anomaly._quadrant_distance(
        anomaly._quadrant(0.0, 0.0), anomaly._quadrant(9.0, 9.0)
    ) >= anomaly._QUADRANT_JUMP_DISTANCE
    got = {a["type"] for a in anomaly.detect_anomalies(
        now, prior_record=unmapped_prior)}
    assert "quadrant_jump" not in got, got


def test_a_real_prior_still_produces_a_quadrant_jump():
    """★ THE OTHER DIRECTION, or the test above passes on a dead rule.

    MUTATION THAT BREAKS THIS: make the prior guard unconditional.
    Q1 (EL high, INS low) → Q2 (EL low, INS high) is the diagonal.
    """
    prior = _rec("high_el", 9.0, 1.0, ts=1000.0)
    now = _rec("high_ins", 1.0, 9.0, ts=1001.0)
    got = {a["type"] for a in anomaly.detect_anomalies(now, prior_record=prior)}
    assert "quadrant_jump" in got, got


# ==========================================================================
# SITE 2 — compute_operator_summary
# ==========================================================================
def _store(*recs):
    for r in recs:
        ST.store_el_ins_record(r)


def test_the_distribution_gains_a_fourth_bucket_and_the_numbers_add_up():
    """MUTATION THAT BREAKS THIS: remove ``"unmapped": 0`` from ``counts``.

    ★ THE MEASURED BEFORE-STATE: three records, one UNMAPPED, read
    ``{high_el 0, high_ins 0, balanced 2}`` over ``sample_size 3`` — two
    counted against a sample of three, with nothing saying where the third
    went. With every recent record UNMAPPED it read all zeros over a
    non-zero sample.
    """
    _store(_rec("balanced", 4.0, 3.0, ts=1000.0),
           _rec("balanced", 4.1, 3.1, ts=1001.0),
           _rec(UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=1002.0))
    s = ST.compute_operator_summary("op_374")
    d = s["recent_classification_distribution"]
    assert d["unmapped"] == 1
    assert d["balanced"] == 2
    assert s["sample_size"] == 3
    assert s["mapped_sample_size"] == 2
    # ★ THE INVARIANT, stated as arithmetic rather than as three equalities:
    # every record is in exactly one bucket, and the three real classes are
    # a distribution over mapped_sample_size.
    assert sum(d.values()) == s["sample_size"]
    assert d["high_el"] + d["high_ins"] + d["balanced"] == s["mapped_sample_size"]


def test_sample_size_keeps_its_type_and_its_meaning():
    """MUTATION THAT BREAKS THIS: change ``sample_size`` to a dict or to
    the mapped count.

    Adding a key rather than changing one is the whole shape of this leg:
    turning an int into mapped/total is a wire ruling (cf. R-355-A).
    """
    _store(_rec("balanced", 4.0, 3.0, ts=1000.0),
           _rec(UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=1001.0))
    s = ST.compute_operator_summary("op_374")
    assert isinstance(s["sample_size"], int) and s["sample_size"] == 2
    assert isinstance(s["mapped_sample_size"], int)


def test_an_unmapped_record_is_excluded_from_the_tsi_average():
    """MUTATION THAT BREAKS THIS: remove the ``continue`` so an UNMAPPED
    record's stamped TSI joins ``tsis``.

    ★ #355 already excludes an undefined frame from the per-thread TSI
    window. If the operator mean re-admits it, the number #355 declined to
    compute comes straight back in through the average. The UNMAPPED
    record carries 100 (a threaded one inherits the other frames' value)
    while the real reads carry 40 and 60: including it moves the mean
    50 → 66.

    ★★ WHY ``thread_id=None``, AND IT IS NOT A CONVENIENCE.
    ``store_el_ins_record`` RE-STAMPS ``tsi`` from the thread whenever the
    record has a thread_id (el_ins_store.py:285-292), so a threaded
    fixture cannot express three different TSIs — all three come back 100
    and the assertion would pass whether or not the exclusion exists. That
    is precisely the un-failable shape this build has already shipped five
    times. An un-threaded record keeps the tsi it was given
    (el_ins_store.py:258-263), which is the only fixture that can tell the
    two behaviours apart.
    """
    _store(_rec("balanced", 4.0, 3.0, tsi=40, ts=1000.0, tid=None),
           _rec("balanced", 4.1, 3.1, tsi=60, ts=1001.0, tid=None),
           _rec(UNMAPPED, 0.0, 0.0, tsi=100, mode=A.MODE_UNMAPPED,
                ts=1002.0, tid=None))
    rows = ST.get_recent_el_ins("op_374", limit=20)
    # the fixture only means something if the TSIs really did survive
    assert sorted(r.get("tsi") for r in rows) == [40, 60, 100]
    s = ST.compute_operator_summary("op_374")
    assert s["avg_tsi"] == 50, s          # not 66
    assert s["mapped_sample_size"] == 2


def test_an_all_unmapped_operator_reports_zero_mapped_not_a_false_distribution():
    """MUTATION THAT BREAKS THIS: drop ``mapped_sample_size``.

    The defect in its purest form: all zeros across the three real classes
    over a non-zero sample, which reads as "no high_el, no high_ins, no
    balanced" — three findings — rather than "nothing was mapped".
    """
    _store(_rec(UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=1000.0),
           _rec(UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=1001.0))
    s = ST.compute_operator_summary("op_374")
    d = s["recent_classification_distribution"]
    assert (d["high_el"], d["high_ins"], d["balanced"]) == (0, 0, 0)
    assert d["unmapped"] == 2
    assert s["sample_size"] == 2
    assert s["mapped_sample_size"] == 0


# ==========================================================================
# SITE 3 — the forecast's phase
# ==========================================================================
NO_SIGNAL_TEXT = (
    "The Commission published the consultation document on Tuesday morning."
)
SIGNAL_TEXT = (
    "The urgent crisis creates real pressure and escalating conflict."
)


def test_a_no_signal_run_projects_undefined_not_balanced():
    """MUTATION THAT BREAKS THIS: remove the ``no_signal`` guard from
    ``days[].phase``.

    ★ ``trend`` has refused to name a shape it has no basis for since B-1
    §17.3 — "'flat' is a measured claim about a trajectory; absence of
    signal is not." Its sibling ``phase`` had no such guard, so a text
    scoring NOTHING still projected five days of "balanced", which reads
    to a member as a finding.
    """
    out = se.generate_ELINS(NO_SIGNAL_TEXT)
    assert out["ep_field_summary"]["no_signal"] is True
    days = out["forecast_5day"]["days"]
    assert len(days) == 5
    assert [d["phase"] for d in days] == ["undefined"] * 5
    assert "balanced" not in [d["phase"] for d in days]


def test_a_run_with_signal_still_projects_a_measured_phase():
    """★ THE OTHER DIRECTION, or the guard is a blanket off-switch.

    MUTATION THAT BREAKS THIS: make the phase unconditionally
    "undefined".
    """
    out = se.generate_ELINS(SIGNAL_TEXT)
    assert out["ep_field_summary"]["no_signal"] is False
    phases = {d["phase"] for d in out["forecast_5day"]["days"]}
    assert phases and "undefined" not in phases
    assert phases <= {"relief", "stress", "balanced"}


def test_balanced_is_still_reachable_as_a_measured_phase():
    """★ #374 MUST NOT DELETE THE WORD, ONLY STOP IT STANDING IN FOR
    ABSENCE. If "balanced" became unreachable, this leg would have removed
    a reading rather than named an absence — the exact error #355 site 2
    was careful to avoid for the EL/INS ratio.

    MUTATION THAT BREAKS THIS: guard on something broader than
    ``no_signal`` (e.g. ``net == 0``).
    """
    ep = {"net": 0.0, "no_signal": False}
    days = se._layer_6_forecast_5day(ep, {})["days"]
    assert [d["phase"] for d in days] == ["balanced"] * 5


def test_the_phase_and_trend_spellings_diverge_KNOWN_AND_RULED():
    """★ TWO SPELLINGS OF ABSENCE IN ONE DICT, CARRIED KNOWINGLY.

    ``phase`` says the string "undefined"; ``trend`` says ``None``. CT-1
    ruled 2026-09-18 to follow the order as written and leave ``trend``
    alone, because ``trend`` is a live field with readers and changing it
    is its own pass — #376, one spelling of absence across the dict.

    Pinned so the divergence is a decision on the record rather than a
    discrepancy someone finds later. MUTATION THAT BREAKS THIS: #376
    landing, which is exactly when this test should be revisited.
    """
    out = se.generate_ELINS(NO_SIGNAL_TEXT)["forecast_5day"]
    assert out["days"][0]["phase"] == "undefined"   # a string
    assert out["trend"] is None                     # not a string
    assert out["trend"] != "undefined"


def test_the_no_signal_guard_does_not_touch_projected_net():
    """The numbers are still the numbers; only the CLAIM about them is
    withheld.

    ★★ THE SEVENTH TAUTOLOGY, AND WHY THIS FIXTURE IS SHAPED THE WAY IT IS.
    An earlier draft ran the real pipeline on NO_SIGNAL_TEXT and asserted
    ``projected_net`` was present and ``ending_net == days[-1]``. But on
    the no-signal path ``net`` is 0.0 BY CONSTRUCTION (no primitives fired),
    and 0.0 decays to 0.0 -- so the mutation the docstring named, "zeroing
    projected_net", changed NOTHING and the test passed under it (measured
    by a refuter: 3 passed). Its second assertion compared two outputs of
    the function under test to each other.

    The layer is pure, so it can be fed a state production never produces
    -- ``no_signal`` True WITH a non-zero net -- which is the only fixture
    that makes zeroing observable. The expected series is computed
    INDEPENDENTLY here (12% mean-reversion, rounded to 4 at each step, from
    1.0), not read back from the function.

    MUTATION THAT BREAKS THIS: ``"projected_net": 0.0 if no_signal else
    cur``, or dropping the key on the no-signal path.
    """
    out = se._layer_6_forecast_5day({"net": 1.0, "no_signal": True}, {})
    days = out["days"]
    assert [d["phase"] for d in days] == ["undefined"] * 5      # the guard
    assert [d["projected_net"] for d in days] == [0.88, 0.7744, 0.6815, 0.5997, 0.5277]
    assert out["starting_net"] == 1.0
    assert out["ending_net"] == 0.5277
    assert out["trend"] is None                                  # untouched
