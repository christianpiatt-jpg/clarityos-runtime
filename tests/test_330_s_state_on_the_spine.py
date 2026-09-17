"""
#330 leg 1 — the attractor's own conclusion on the spine.

★ WHAT THESE PIN

``record_turn`` already sealed a text-derived expectation and observed the
previous one. What it never sealed was what the INSTRUMENT concluded — only
what the extractor counted off the text. ``s_state_label`` existed in
turn_record with ZERO callers and a docstring that promised a parameter
``build_geometry_observation`` did not have. This leg closes that, and the
last test in this file is the reason the leg is held rather than shipped.

★★ THE REFUTER IS THE POINT (``test_the_reachable_label_distribution``).
A seal that always says the same thing always matches, and a seal that
always matches is the #110/#111 pattern: a default counted as a reading.
So the distribution is MEASURED here, over synthetic vectors AND over the
producer that actually feeds this route, and the current truth is pinned so
that fixing the lexicon FAILS this file loudly instead of silently changing
what the record means.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

from collections import Counter  # noqa: E402

import pytest  # noqa: E402

import memory_vault  # noqa: E402
import turn_record as tr  # noqa: E402
from ELINS import elins_v2_view, standard_elins  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    memory_vault._reset_for_tests()
    tr._reset_seq_for_tests()
    yield


U = "u_330"
T = "thread_330"

TEXT = "The filing is urgent and the deadline creates real pressure."
PRESSURE = {"pressure": 0.5}          # gap 0.1396 -> seals S3
ALIGNED = {"trust": 1.0, "alignment": 1.0}   # gap 0.2377 -> seals S1
LEVEL = {}                            # gap 0.0000 -> seals NOTHING (the gate declines)


# --------------------------------------------------------------------------
# 1. Every existing caller is untouched
# --------------------------------------------------------------------------
def test_existing_callers_get_a_byte_identical_observation():
    """``intensities`` defaults to None, and None is not a reading.

    This is the whole backward-compatibility contract of the leg: the
    physics route passes nothing, and its record must be exactly what it
    was before the parameter existed.
    """
    without = tr.build_geometry_observation(TEXT)
    explicit_none = tr.build_geometry_observation(TEXT, intensities=None)
    assert without == explicit_none
    assert "s_state" not in without

    # The key is ABSENT, not null -- so the next turn scores it as
    # "undefined" (no claim was made) rather than a claim of nothing.
    exp = tr.persistence_expectation(without)
    assert "s_state" not in exp


def test_the_label_rides_only_when_intensities_arrive(monkeypatch):
    with_vec = tr.build_geometry_observation(TEXT, intensities=PRESSURE)
    assert with_vec["s_state"] == "S3"

    # ★ ASSERT THE TOKEN ONLY WHERE IT CAN MOVE. The first draft of this
    # test asserted CONF_MULTI_READING on the ordinary path and was a FALSE
    # PASS: pressure_score returns an int for every text (0 is not None),
    # so `readings` is already 2 before the label is considered, and the
    # ladder buckets 2 and 3 to the same token -- the assertion survived
    # deleting the `readings += 1` it claimed to prove. Force the pressure
    # reading to decline, and the promotion is then caused BY the label.
    import azimuth_envelope_impl

    def _declines(_t):
        raise RuntimeError("pressure_score declined")

    monkeypatch.setattr(azimuth_envelope_impl, "pressure_score", _declines)

    without = tr.build_geometry_observation(TEXT)
    assert without["pressure_score"] is None
    assert without[tr._COP_KEY]["confidence"] == tr.CONF_SINGLE_READING

    with_label = tr.build_geometry_observation(TEXT, intensities=PRESSURE)
    assert with_label["s_state"] == "S3"
    assert with_label[tr._COP_KEY]["confidence"] == tr.CONF_MULTI_READING, (
        "the label did not count as an independent reading"
    )
    # ★ OPEN, and named rather than settled here: whether the label SHOULD
    # count as independent at all. On the live producer it is derived from
    # the same pressure signal the record already carries, so the third
    # "reading" may be one reading counted twice. CT-1's to rule.


# --------------------------------------------------------------------------
# 2. Seal, then observe -- matched and missed are BOTH reachable
# --------------------------------------------------------------------------
def test_seal_then_observe_reaches_matched_and_missed():
    # turn 0 -- seals S3, has no prior to observe
    first = tr.record_turn(U, T, TEXT, intensities=PRESSURE)
    assert first["observed_prior"] is False
    assert "prior_s_state" not in first          # D5: absent, not null

    # turn 1 -- observes turn 0 and reaches the same state
    second = tr.record_turn(U, T, TEXT, intensities=PRESSURE)
    assert second["observed_prior"] is True
    assert second["prior_s_state"] == "S3"
    assert second["s_state_match"] is True

    # turn 2 -- observes turn 1 and reaches a DIFFERENT determinate state
    third = tr.record_turn(U, T, "A quiet note about the schedule.", intensities=ALIGNED)
    assert third["prior_s_state"] == "S3"
    assert third["s_state_match"] is False


def test_what_is_sealed_is_scored_without_touching_BEARINGS():
    """Coordinate 3 of the order: ``claimed`` picks up anything sealed.

    ★ BEARINGS is NOT widened. Widening it would re-score every record
    already stored (#90, no retrofit); ``score_record`` reads the
    expectation's own keys, so a new sealed key is scored for free.
    """
    tr.record_turn(U, T, TEXT, intensities=PRESSURE)
    tr.record_turn(U, T, TEXT, intensities=PRESSURE)

    rows = tr.list_turn_records(U, T)
    scored = tr.score_record(rows[0])
    assert scored["status"] == "scored"
    assert scored["per_bearing"]["s_state"] == "matched"
    # ★ and it is scored WITHOUT being a named bearing -- the whole point
    # of reading `claimed` off the expectation instead of a constant.
    assert "s_state" not in tr.BEARINGS

    tr.record_turn(U, T, "A quiet note about the schedule.", intensities=ALIGNED)
    assert tr.score_record(tr.list_turn_records(U, T)[1])["per_bearing"]["s_state"] == "missed"


# --------------------------------------------------------------------------
# 3. A label that declines seals NOTHING
# --------------------------------------------------------------------------
def test_a_declining_label_omits_the_key_and_never_seals_a_null(monkeypatch):
    monkeypatch.setattr(tr, "s_state_label", lambda _i: None)
    obs = tr.build_geometry_observation(TEXT, intensities=PRESSURE)
    assert "s_state" not in obs
    assert "s_state" not in tr.persistence_expectation(obs)

    out = tr.record_turn(U, T, TEXT, intensities=PRESSURE)
    rec = tr.list_turn_records(U, T)[0]
    assert "s_state" not in rec["expectation"]
    assert "prior_s_state" not in out


def test_a_non_dict_intensities_is_not_a_reading():
    for junk in ("S3", 3, [0.5], None):
        obs = tr.build_geometry_observation(TEXT, intensities=junk)
        assert "s_state" not in obs


# --------------------------------------------------------------------------
# 4. ★★ THE REFUTER -- measured, reported, and pinned as it actually is
# --------------------------------------------------------------------------
#: Eight intensity vectors spanning the scored space (tension is excluded
#: from §2 scoring by design, so it is here as a control).
_VECTORS = [
    ("all zero (an empty text)",                 {}),
    ("pressure only",                            {"pressure": 0.5}),
    ("pressure + drift + contradiction",         {"pressure": 0.9, "drift": 0.8, "contradiction": 0.8}),
    ("trust high + alignment high, no pressure", {"trust": 0.9, "alignment": 0.9}),
    ("trust high + alignment high + pressure",   {"trust": 0.9, "alignment": 0.9, "pressure": 0.7}),
    ("alignment only (an EU region bump)",       {"alignment": 0.05}),
    ("everything at 1.0",                        {"pressure": 1.0, "trust": 1.0, "drift": 1.0,
                                                  "contradiction": 1.0, "alignment": 1.0, "tension": 1.0}),
    ("tension only (not scored, by design)",     {"tension": 0.9}),
]

#: Eight real texts, run through the producer that actually feeds
#: /elins/v2/run. These are the labels a MEMBER can cause.
_TEXTS = [
    ("a calm agreement",        "We agreed the terms and both parties signed the amended schedule."),
    ("explicit trust language", "I trust her completely; we are fully aligned and confident in each other."),
    ("explicit distrust",       "There is no trust here at all and we are completely misaligned."),
    ("deadline pressure",       "The filing is urgent and the deadline creates real pressure on the team."),
    ("crisis and collapse",     "The crisis escalated and the whole arrangement is about to collapse."),
    ("drift and contradiction", "His account is inconsistent and the position keeps sliding away from terms."),
    ("pure tension",            "There is open conflict and a standoff between the two departments."),
    ("bureaucratic neutral",    "The Commission published the consultation document on Tuesday morning."),
]


def test_the_function_discriminates_over_the_scored_space():
    """The LABEL itself is not degenerate -- given a separated field it moves,
    and given a LEVEL one it declines instead of naming a winner."""
    labels = [tr.s_state_label(v) for _n, v in _VECTORS]
    print()
    print("#330 synthetic distribution (gated by the writers' rule):",
          dict(Counter(str(x) for x in labels)))
    for (name, v), lab in zip(_VECTORS, labels):
        dist, arg = elins_v2_view.compute_state_distribution(v)
        gap = elins_v2_view.attractor_verdict(dist, arg)["gap"]
        print("    %-44s gap %.4f  %s" % (name, gap, lab))
    named = {x for x in labels if x is not None}
    assert len(named) > 1, (
        "s_state_label named ONE state on every vector it accepted: the seal "
        "would always match and would mean nothing (#110/#111)."
    )
    # and it DECLINES on a level field rather than crowning the argmax
    assert None in labels


def test_an_indeterminate_field_seals_absent_not_a_name():
    """★ THE WRITERS' RULE, pinned on the write path (#284).

    ``attractor_verdict`` exists precisely so that "a record that names a
    state names the one the surface would show". Sealing the raw argmax
    would let the card print "prior seal: S1 - matched" directly beneath
    "indeterminate — no attractor leads" on the same card -- the
    contradiction CT-1 measured on the 2026-08-27 walk, re-opened on a new
    WRITE path. A level field seals ABSENT (D5), never a name.
    """
    dist, arg = elins_v2_view.compute_state_distribution(LEVEL)
    verdict = elins_v2_view.attractor_verdict(dist, arg)
    assert verdict["determinate"] is False        # the surface names none
    assert arg == "S1"                            # ...but the raw argmax does
    assert tr.s_state_label(LEVEL) is None        # and the SEAL follows the surface

    obs = tr.build_geometry_observation(TEXT, intensities=LEVEL)
    assert "s_state" not in obs
    assert "s_state" not in tr.persistence_expectation(obs)


def test_the_seal_and_the_surface_can_never_drift_apart():
    """Whatever is sealed is exactly what ``attractor_verdict`` would show."""
    for _name, v in _VECTORS:
        dist, arg = elins_v2_view.compute_state_distribution(v)
        verdict = elins_v2_view.attractor_verdict(dist, arg)
        expected = verdict["state"] if verdict["determinate"] else None
        assert tr.s_state_label(v) == expected


def test_the_reachable_label_distribution():
    """★★ WHAT A MEMBER CAN ACTUALLY CAUSE, measured not assumed.

    D3 in ``s_state_label``'s docstring says trust enters S1/S2 as a
    MULTIPLIER, so a zero annihilates both. The substrate is narrower
    still: the ``trust`` and ``alignment`` LEXICONS ARE EMPTY, so those two
    intensities can never leave 0.0 on this path, the four scores rarely
    separate, and the writers' rule DECLINES on seven of eight real texts.

    THIS TEST PINS THAT AS IT IS. It is a drift guard, not an endorsement:
    when #307(b) restores a non-zero trust term this test FAILS, and the
    failure is the signal to re-read the distribution and lift #330's hold.
    """
    lex = standard_elins._PRIMITIVE_LEXICON
    assert lex.get("trust") == [], (
        "the trust lexicon is no longer empty -- re-measure the reachable "
        "distribution and revisit #330's hold at 0%"
    )
    assert lex.get("alignment") == [], (
        "the alignment lexicon is no longer empty -- re-measure and revisit"
    )

    labels = []
    print()
    print("#330 REACHABLE distribution (live producer, real text, gated):")
    for name, text in _TEXTS:
        vec = standard_elins._layer_1_primitives(text)["intensities"]
        dist, arg = elins_v2_view.compute_state_distribution(vec)
        verdict = elins_v2_view.attractor_verdict(dist, arg)
        lab = tr.s_state_label(vec)
        labels.append(lab)
        nz = {k: v for k, v in vec.items() if v}
        print("    %-24s %-38s argmax %s gap %.4f -> %s"
              % (name, str(nz), arg, verdict["gap"], lab))
    dist_counts = dict(Counter(str(x) for x in labels))
    print("    ->", dist_counts)

    # The measured truth at this commit: the field separates on ONE of the
    # eight, and that one is the crisis/collapse text (gap 0.0876 > 0.05).
    named = [x for x in labels if x is not None]
    assert len(named) == 1 and named[0] == "S3", (
        "the reachable seal set changed (%s) -- #330's refuter finding is "
        "stale, re-measure before trusting the seal" % dist_counts
    )
    # ...and the seven that seal nothing are exactly the ones the CARD would
    # call indeterminate, so the record and the surface agree turn for turn.
    for _name, text in _TEXTS:
        vec = standard_elins._layer_1_primitives(text)["intensities"]
        d, a = elins_v2_view.compute_state_distribution(vec)
        v = elins_v2_view.attractor_verdict(d, a)
        assert tr.s_state_label(vec) == (v["state"] if v["determinate"] else None)


def test_no_region_profile_can_move_the_label():
    """The record is written BEFORE the envelope, so it seals the
    PRE-REGIONAL vector. This pins that the bump cannot change the label:
    no profile bumps ``trust``, and with tr == 0 both S1 and S2 stay
    annihilated whatever ``alignment`` does.
    """
    from ELINS import regional_elins

    for code, profile in regional_elins.REGION_PROFILES.items():
        assert "trust" not in profile["entity_bumps"], (
            "region %s now bumps trust: the pre-regional vector sealed by "
            "_run_intensities can diverge from the envelope's own attractor" % code
        )

    base = {"pressure": 0.4, "tension": 0.2}
    for code, profile in regional_elins.REGION_PROFILES.items():
        bumped = dict(base)
        for k, b in profile["entity_bumps"].items():
            bumped[k] = round(min(1.0, bumped.get(k, 0.0) + b), 4)
        assert tr.s_state_label(bumped) == tr.s_state_label(base), code
