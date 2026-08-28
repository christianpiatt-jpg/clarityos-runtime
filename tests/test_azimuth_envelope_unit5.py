"""
Azimuth Envelope — Phase 3 Unit 5. The heuristics, and the invariants.

★★ THE INVARIANTS ARE TESTED, NOT ASSUMED. The module docstring declares
three (no network, no raw_text in logs, frozen returns) and a declaration
is not enforcement. Each has a test that would fail if the property broke.

★ raw_text is the innermost privacy boundary in the product. The test that
scans emitted log records is the one that matters most here: a future edit
adding a helpful `logger.info(f"capturing {raw_text}")` would pass every
other test in this file.
"""
import logging
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")

import pytest  # noqa: E402

import azimuth_envelope as ae  # noqa: E402
import azimuth_envelope_impl as impl  # noqa: E402
from azimuth import IntensityLevel, PressureLevel, Valence  # noqa: E402

CALM = "this is fine"
LOUD = "this is REALLY absolutely extremely bad!!!"
HEDGED = "kind of a bit maybe bad"


# --------------------------------------------------------------------------
# GATE 5 — the perturbation, in BOTH directions.
# --------------------------------------------------------------------------
def test_intensity_moves_up_with_amplifiers():
    calm = ae.capture_envelope(CALM).emotional_intensity
    loud = ae.capture_envelope(LOUD).emotional_intensity
    assert calm is IntensityLevel.LOW
    assert loud is IntensityLevel.EXTREME
    assert calm != loud


def test_intensity_score_moves_DOWN_with_hedges():
    """★ Direction IS the signal. Hedges must pull the score below neutral —
    the retired reading would have counted them as more signal, not less."""
    assert impl.intensity_score(HEDGED) < impl.intensity_score(CALM)
    assert impl.intensity_score(HEDGED) < 0


def test_the_enum_floors_below_low(recwarn):
    """★ REPORTED, NOT WORKED AROUND. IntensityLevel has no level below LOW,
    so a hedged score of -3 and a neutral score of 0 both band to LOW. The
    score moves; the enum cannot. Adding a level would change the locked
    schema, which this order forbids."""
    assert ae.capture_envelope(HEDGED).emotional_intensity is IntensityLevel.LOW
    assert ae.capture_envelope(CALM).emotional_intensity is IntensityLevel.LOW
    assert impl.intensity_score(HEDGED) != impl.intensity_score(CALM)


def test_every_named_intensity_channel_contributes():
    """The spec names five bump channels. All-caps, exclamation density and
    profanity are ones neither LangBridg nor the retired ruling carried."""
    base = impl.intensity_score("that is a problem")
    assert impl.intensity_score("that is a REALLY problem") > base   # amplifier
    assert impl.intensity_score("that is a PROBLEM NOW") > base      # all-caps
    assert impl.intensity_score("that is a problem!!") > base        # exclamation
    assert impl.intensity_score("that is a damn problem") > base     # profanity


# --------------------------------------------------------------------------
# The other three axes.
# --------------------------------------------------------------------------
def test_negation_inverts_valence():
    """The spec's own example: "not great" -> negative."""
    assert ae.capture_envelope("this is great").valence is Valence.POSITIVE
    assert ae.capture_envelope("this is not great").valence is Valence.NEGATIVE


def test_mixed_and_neutral_valence():
    assert ae.capture_envelope("I am happy but also worried").valence is Valence.MIXED
    assert ae.capture_envelope("the meeting is at three").valence is Valence.NEUTRAL


def test_pressure_rises_with_obligation_deadline_and_crisis():
    low = ae.capture_envelope("the meeting is at three").pressure_level
    high = ae.capture_envelope(
        "I have to finish this before Friday, it is urgent, we are at a "
        "breaking point and the deadline is today under real pressure"
    ).pressure_level
    assert low is PressureLevel.LOW
    assert high is PressureLevel.CRITICAL


def test_before_date_is_its_own_marker():
    assert impl.BEFORE_DATE_RE.search("get it done before Friday")
    assert not impl.BEFORE_DATE_RE.search("I stood before the committee")


def test_intention_precedence():
    assert ae.capture_envelope("I'm sorry about that").rough_intention == "apologize"
    assert ae.capture_envelope("can you send it over").rough_intention == "request"
    assert ae.capture_envelope("Stop doing that.").rough_intention == "request"
    assert ae.capture_envelope("I felt awful and I went home").rough_intention == "vent"
    assert ae.capture_envelope("the sky is blue").rough_intention == "reflect"


# --------------------------------------------------------------------------
# GATE 3 — no partial fills.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["", "   ", "\n\t "])
def test_empty_input_RAISES_rather_than_defaulting(bad):
    """★ A frozen dataclass returned with guessed fields is the N=5.0 failure
    in a different hat. Refuse instead."""
    with pytest.raises(ValueError):
        ae.capture_envelope(bad)


@pytest.mark.parametrize("bad", [None, 42, [], {}])
def test_non_string_input_RAISES(bad):
    with pytest.raises(TypeError):
        ae.capture_envelope(bad)


# --------------------------------------------------------------------------
# GATE 4 — determinism and idempotence.
# --------------------------------------------------------------------------
def test_capture_is_deterministic_on_the_derived_axes():
    a = ae.capture_envelope(LOUD)
    b = ae.capture_envelope(LOUD)
    assert (a.emotional_intensity, a.valence, a.pressure_level, a.rough_intention) == \
           (b.emotional_intensity, b.valence, b.pressure_level, b.rough_intention)


def test_evaluate_is_idempotent():
    """The docstring states the requirement; this enforces it."""
    once = ae.evaluate_envelope(ae.capture_envelope(LOUD))
    twice = ae.evaluate_envelope(once)
    assert once == twice


def test_evaluate_preserves_identity_and_flag():
    e = ae.mark_externalize(ae.capture_envelope(LOUD))
    r = ae.evaluate_envelope(e)
    assert r.envelope_id == e.envelope_id
    assert r.raw_text == e.raw_text
    assert r.captured_at == e.captured_at
    assert r.user_marked_externalize is True


# --------------------------------------------------------------------------
# GATE 2 — the locked invariants.
# --------------------------------------------------------------------------
def test_returns_are_frozen():
    for env in (ae.capture_envelope(LOUD),
                ae.evaluate_envelope(ae.capture_envelope(LOUD)),
                ae.mark_externalize(ae.capture_envelope(LOUD))):
        with pytest.raises(Exception):
            env.raw_text = "mutated"


def test_mark_externalize_does_not_mutate_the_original():
    before = ae.capture_envelope(LOUD)
    after = ae.mark_externalize(before)
    assert before.user_marked_externalize is False
    assert after.user_marked_externalize is True
    assert before is not after


def test_no_network_import_reaches_this_module():
    """By import inspection: neither module may pull a network client."""
    import inspect
    for mod in (ae, impl):
        src = inspect.getsource(mod)
        for banned in ("requests", "urllib", "httpx", "socket", "aiohttp",
                       "google.cloud"):
            assert banned not in src, f"{mod.__name__} references {banned}"


def test_no_network_call_by_tripwire(monkeypatch):
    """By tripwire: even an indirect socket open fails the test."""
    import socket

    def boom(*a, **k):
        raise AssertionError("azimuth_envelope opened a socket")

    monkeypatch.setattr(socket.socket, "connect", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    ae.evaluate_envelope(ae.capture_envelope(LOUD))


def test_raw_text_NEVER_reaches_a_log_record_at_info_or_above(caplog):
    """★★ THE PRIVACY INVARIANT, BY GENERATION. The envelope is the innermost
    boundary; raw_text stays on device. A future `logger.info(raw_text)`
    would pass every other test in this file."""
    secret = "MYSECRETPHRASE the deadline is today and I have to go"
    with caplog.at_level(logging.INFO):
        env = ae.capture_envelope(secret)
        ae.evaluate_envelope(env)
        ae.mark_externalize(env)
    for rec in caplog.records:
        if rec.levelno >= logging.INFO:
            assert "MYSECRETPHRASE" not in rec.getMessage()
            assert "MYSECRETPHRASE" not in str(rec.args or "")
