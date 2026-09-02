"""
Emotional Physics PHASE 1 — the shadow layer.

★★★ THESE TESTS PIN THE PROHIBITIONS, NOT THE FEATURE.

The phase computes almost nothing on purpose. Its value is that two
absences — T and N — stay visible instead of being defaulted into a
plausible number. So the tests that matter here are the ones asserting what
does NOT happen.

★★ EmotionalState's own defaults are the hazard: `EmotionalState()` yields
N=5.0, E=0.5, m=3.0, T=0.5 — a complete, plausible, meaningless state.
Merely constructing it would manufacture the answer this phase withholds.
That is why the guard is "never constructed", not "constructed carefully".
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import re  # noqa: E402

import app as app_module  # noqa: E402

LOW = "The constraint caused friction. A bottleneck appeared. There was tension."
HIGH = (
    "The constraint caused friction and contradiction. A bottleneck and a deadlock "
    "appeared under structural tension. Competition and regulation from a competitor "
    "created external demand pressure. The goal and the objective and the incentive "
    "drove the motive. Trade-off, limitation and imbalance under strain and load."
)


# --------------------------------------------------------------------------
# THE SENTINEL — tested first, because a sentinel that never fires is
# indistinguishable from one that is not there.
# --------------------------------------------------------------------------
def test_only_E_remains_unmapped_and_it_is_never_defaulted():
    """E is the last of doctrine 8.4's four per-turn flows with no producer.

    * THIS TEST PREVIOUSLY PINNED T, on the reasoning that hedgeRatio "runs
    client-side, so the web path cannot supply it". That was true about WHERE
    IT RAN and false as a constraint on where it COULD run: langbridg.ts
    imports nothing and touches no browser API, so it ported to stdlib `re`.
    A LOCATION HAD BEEN READ AS A LIMITATION, twice, in this file's own
    prose. E is asserted here as UNMAPPED on the evidence that no producer
    has been identified -- NOT on the claim that none can exist."""
    p = app_module._emophysics_shadow("u", LOW)
    assert p["E"] == "UNMAPPED"
    assert p["computed"] is False


def test_the_reason_names_both_gaps_specifically():
    """A sentinel that says only 'unmapped' does not tell the next reader
    WHY, and the two gaps have different causes and different fixes."""
    reason = app_module._emophysics_shadow("u", LOW)["reason"]
    assert "arousal mapping unruled" in reason      # T -- built, not ruled
    assert "weighting unruled" in reason            # N -- built, not ruled
    assert "no producer identified" in reason       # E -- the real gap
    assert "not implemented" not in reason          # N IS implemented
    assert "no server-side producer" not in reason  # T IS implemented


def test_no_physics_number_is_ever_emitted():
    """★ The payload must carry no P, P_perc, alpha or collapse_probability
    under any name. A number here would be a confident value with correct
    units and no measurement behind it."""
    p = app_module._emophysics_shadow("u", HIGH)
    for forbidden in ("P", "P_perc", "alpha", "collapse_probability",
                      "pressure", "collapse"):
        assert forbidden not in p, f"shadow emitted {forbidden}"
    assert not re.search(r"\b(P|alpha)\b\s*[:=]\s*[\d.]", str(p))


def test_n_never_appears_as_five():
    """The specific failure this phase exists to prevent: N silently
    becoming EmotionalState's 5.0 default and logging a plausible
    pressure.

    * N is now a real measurement, so the guard is stronger than it was:
    CI is bounded in [0,1] BY CONSTRUCTION, so 5.0 is not merely absent,
    it is unreachable. The assertion is kept because the value it
    excludes is the one that would look most convincing."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert p["N"] != 5.0 and p["N"] != "5.0"
    assert isinstance(p["N"], float)
    assert 0.0 <= p["N"] <= 1.0


def test_the_engine_is_never_constructed(monkeypatch):
    """★★ Merely instantiating EmotionalState manufactures a full plausible
    state from dataclass defaults. Nothing in the shadow path may touch the
    engine at all."""
    import engine.emophysics as ep

    touched = []
    for name in ("EmotionalState", "PressureModel", "RelationalModel",
                 "ThresholdModel", "ConversionModel"):
        real = getattr(ep, name)

        def tripwire(*a, _n=name, **k):
            touched.append(_n)
            raise AssertionError(f"shadow constructed {_n}")

        monkeypatch.setattr(ep, name, tripwire)
        assert real is not None
    app_module._emophysics_shadow("u", HIGH)
    assert touched == [], f"engine touched: {touched}"


# --------------------------------------------------------------------------
# D — the one thing this phase does measure.
# --------------------------------------------------------------------------
def test_d_moves_with_the_members_text():
    """★ THE GATE. If D does not move, the extractor is not on the path and
    everything after this phase is built on nothing."""
    low = app_module._emophysics_shadow("u", LOW)["D"]
    high = app_module._emophysics_shadow("u", HIGH)["D"]
    assert low > 0, "no signal at all from tension-bearing text"
    assert high > low, f"D did not move ({low} -> {high})"


def test_the_full_distribution_is_captured():
    """The 8-way counts vector is CI's `p` in Phase 2. This phase starts
    accumulating the input the next phase consumes, so the whole vector is
    logged, not just the sum."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert set(p["counts"]) == {"P1", "P2", "P3", "P4", "Ts", "Te", "M", "hydronic"}
    assert p["D"] == sum(p["counts"].values())


def test_d_is_tagged_a_candidate():
    """D = sum(counts) is unruled. The tag is what makes a later change one
    line instead of an archaeology exercise."""
    assert app_module._emophysics_shadow("u", LOW)["D_status"] == "CANDIDATE"


def test_empty_and_non_string_input_do_not_raise():
    for bad in ("", "   ", None, 42, []):
        p = app_module._emophysics_shadow("u", bad)  # type: ignore[arg-type]
        assert p["D"] == 0 and p["computed"] is False


# --------------------------------------------------------------------------
# N — the compression index. CI = 1 - H/H_max over the fixed eight.
# --------------------------------------------------------------------------
# ★★★ WHAT THESE PIN. Not the arithmetic — that is four lines out of a
# spec. They pin the ZERO EDGE, because that is where this metric would
# have been quietly wrong. engine/emophysics/relational.py:142 answers the
# same shape of failure with `return 1.0`, which reads as PERFECT
# REGISTRATION at precisely the point the instrument has no measurement.
# The sentinel is asserted BY TYPE so no future refactor can round it into
# a number without a test going red.
def _counts(**kw):
    """The eight fixed keys, zero unless named. Mirrors
    primitives_extract.build_metadata, which never returns fewer."""
    base = {"P1": 0, "P2": 0, "P3": 0, "P4": 0,
            "Ts": 0, "Te": 0, "M": 0, "hydronic": 0}
    base.update(kw)
    return base


def test_ci_moves_when_the_distribution_moves():
    """★ THE GATE. If CI does not move with the counts, the field is
    decorative and the order failed."""
    concentrated = app_module._compression_index(_counts(P1=10, P2=1))
    spread = app_module._compression_index(
        _counts(P1=3, P2=3, P3=3, P4=3, Ts=3, Te=3, M=3, hydronic=3))
    assert isinstance(concentrated, float) and isinstance(spread, float)
    assert concentrated > spread, f"CI did not move ({spread} -> {concentrated})"


def test_a_single_category_turn_is_maximally_compressed():
    """All the weight in one category is zero entropy, so CI is exactly 1.
    ★ That is the CORRECT reading — over-compressed, brittle — and not an
    artifact of the zero categories, which each contribute 0 to H."""
    assert app_module._compression_index(_counts(Ts=7)) == 1.0


def test_a_perfectly_flat_spread_is_minimally_compressed():
    """Eight equal categories is maximum entropy: H == H_max, so CI is
    exactly 0. Entropy-friendly, resilient."""
    flat = _counts(P1=2, P2=2, P3=2, P4=2, Ts=2, Te=2, M=2, hydronic=2)
    assert app_module._compression_index(flat) == 0.0


def test_no_extraction_returns_a_different_kind_not_a_number():
    """★★★★★ D5, and the whole reason this order was written. An extraction
    that found nothing leaves p_i UNDEFINED. Asserted BY TYPE: a float here
    — any float — would be a confident reading with no measurement behind
    it, which is exactly relational.py:142's `return 1.0`."""
    out = app_module._compression_index(_counts())
    assert not isinstance(out, float)
    assert isinstance(out, str)
    assert out == "UNMAPPED"


def test_a_different_taxonomy_size_returns_the_sentinel():
    """n is the taxonomy size and it is CONSTANT. A denominator that varied
    would make two turns' CI values different measurements, and the series
    they are plotted in meaningless."""
    assert app_module._compression_index({"P1": 3, "P2": 1}) == "UNMAPPED"
    assert app_module._compression_index({}) == "UNMAPPED"


def test_the_empty_turn_carries_the_sentinel_through_the_payload():
    """End to end: the shadow payload, not just the function."""
    p = app_module._emophysics_shadow("u", "")
    assert p["N"] == "UNMAPPED"
    assert p["N_status"] == "UNMAPPED"
    assert not isinstance(p["N"], float)
    assert "p_i undefined" in p["reason"]


def test_n_is_tagged_a_candidate_exactly_as_d_is():
    """The closed form is ruled; the WEIGHTING is not. Whether Ts/Te should
    outrank P1-P4 before the counts become a probability vector is the same
    open question D carries. The tag is what makes that change one line."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert p["N_status"] == "CANDIDATE"
    assert p["D_status"] == "CANDIDATE"


def test_the_returned_value_is_not_rounded():
    """Rounding is a display decision and belongs at the log boundary. A
    consumer must never inherit a truncation made for readability."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert p["N"] == app_module._compression_index(p["counts"])


# --------------------------------------------------------------------------
# T — the hedge ratio, ported from phone/lib/langbridg.ts
# --------------------------------------------------------------------------
# ★★★ WHAT THESE PIN: FIDELITY, not plausibility. A test asserting only that
# the Python agrees with itself proves nothing — it would pass just as well
# against a "better" lexicon, and the phone and the server would then be two
# instruments wearing one name.
#
# Every expected value below is DERIVED BY HAND from langbridg.ts and the
# derivation is written next to it. Comparison is at 2dp because the TS
# rounds; the Python stores full precision (see _hedge_ratio's docstring).
#
# ★★ TWO PORTED QUIRKS ARE PINNED DELIBERATELY. They are wrong, they are the
# original's behaviour, and pinning them is what stops a later "fix" from
# silently desynchronising the two surfaces:
#   1. The abbreviation guard replaces "U.S." with "U.S<DOT>", which STILL
#      contains a dot, so multi-dot abbreviations still split.
#   2. Each pattern scans independently and the counts SUM, so one phrase
#      can score twice.

# (label, text, expected sentences, expected hedges) — hand-derived from
# langbridg.ts:46-56 (splitSentences), :125-171 (HEDGES), :193-200 (count).
T_FIXTURES = [
    # 1 hedge at sentence start. "I think" matches /\bI think\b/gi. One
    #   sentence: "[^.!?\n]+[.!?]+" takes the whole string.
    ("hedge_at_start", "I think the plan works.", 1, 1),
    # 2 hedge mid-sentence. "probably" -> /\bprobably\b/gi.
    ("hedge_mid", "The plan is probably fine.", 1, 1),
    # 3 hedge at end. "I guess" -> /\bI guess\b/gi.
    ("hedge_at_end", "The plan works, I guess.", 1, 1),
    # 4 ★ PORTED QUIRK. Guard turns "Dr."->"Dr<DOT>", "Mr."->"Mr<DOT>", and
    #   "U.S."->"U.S<DOT>" — which still holds a dot, so the splitter breaks
    #   at "the U." | "S. yesterday.". TWO sentences, not one. No hedges.
    ("abbreviations", "Dr. Smith met Mr. Jones in the U.S. yesterday.", 2, 0),
    # 5 ★ Same quirk: "e.g."->"e.g<DOT>" leaves the first dot, so
    #   "Use a tool, e." | "g. a wrench." | "It works." = THREE sentences.
    ("abbrev_eg", "Use a tool, e.g. a wrench. It works.", 3, 0),
    # 6 two sentences, one hedge ("Maybe" -> /\bmaybe\b/gi, /i matters).
    ("two_sentences", "Maybe it works. It does not.", 2, 1),
    # 7 no hedges at all.
    ("no_hedges", "The system compiles and the tests pass.", 1, 0),
    # 8 ★ DOUBLE COUNT. "might be" AND "just" are separate patterns; each
    #   scans the whole text and the counts SUM. TWO, from one clause.
    ("double_count", "It might be just fine.", 1, 2),
    # 9 /\blike,\s*/gi — note the TRAILING \s* and NO closing \b. Matches
    #   "like, " including the space. One hedge. ("So," is not a hedge.)
    ("like_comma", "So, like, the thing broke.", 1, 1),
    # 10 optional group: /\bit seems(?: like)?\b/gi matches "It seems like";
    #    /\bcould be\b/gi matches separately. TWO.
    ("it_seems_like", "It seems like it could be wrong.", 1, 2),
    # 11 ★ UNICODE. JS \b (no /u) is ASCII-only, so a Cyrillic letter is a
    #    NON-word char and \b EXISTS before "just" -> it matches. Python's
    #    default \b is unicode-aware and would NOT match. re.ASCII restores
    #    the JS reading. This fixture is the proof of that flag choice.
    ("unicode_word_boundary", "\u0442just here.", 1, 1),
    # 12 CRLF. "[^.!?\n]" admits \r, so the split is on "." only and the
    #    stray \r is stripped by .trim(). "probably" -> 1 hedge.
    ("crlf", "First line.\r\nSecond line probably.", 2, 1),
    # 13 no terminator — second alternative "[^.!?\n]+\Z" takes the tail.
    #    "just" is a hedge.
    ("no_terminator", "just a fragment", 1, 1),
    # 14 a real sentence with no hedge and no terminator.
    ("plain_fragment", "the build is green", 1, 0),
]


def test_T_parity_with_the_typescript_on_every_fixture():
    """★ Sentence count and hedge count are each pinned, so a divergence
    reports WHICH half moved rather than only that the ratio changed."""
    for label, text, exp_sents, exp_hedges in T_FIXTURES:
        got_s = len(app_module._split_sentences(text))
        got_h = app_module._count_hedge_matches(text)
        assert got_s == exp_sents, f"{label}: sentences {got_s} != {exp_sents}"
        assert got_h == exp_hedges, f"{label}: hedges {got_h} != {exp_hedges}"


def test_T_ratio_matches_the_typescript_rounded_to_two_places():
    """The TS rounds inside the computation; we round only to compare, so
    the stored value keeps full precision and parity still holds."""
    for label, text, exp_sents, exp_hedges in T_FIXTURES:
        got = app_module._hedge_ratio(text)
        expected = round(exp_hedges / exp_sents, 2)   # what the TS returns
        assert isinstance(got, float), f"{label}: expected a ratio"
        assert round(got, 2) == expected, f"{label}: {round(got, 2)} != {expected}"


def test_T_stores_full_precision_not_the_rounded_value():
    """★ 1/3 is the case that separates the two. The TS would store 0.33."""
    got = app_module._hedge_ratio("Maybe. It works. It does not.")
    assert isinstance(got, float)
    assert got != round(got, 2), "the stored ratio was rounded at computation"


def test_T_moves_when_the_hedges_move():
    """★ THE GATE. If T does not move with the hedging, it is decorative."""
    none_ = app_module._hedge_ratio("The build is green and the tests pass.")
    many = app_module._hedge_ratio(
        "I think it might be basically just possibly fine.")
    assert none_ == 0.0
    assert isinstance(many, float) and many >= 5.0, many
    assert many > none_


def test_T_no_sentences_returns_a_different_kind_not_zero():
    """★★★★★★★ D5, and the THIRD time this exact shape has appeared:
        engine/emophysics/relational.py:142   `if P <= 0: return 1.0`
        the CI sum==0 case                    (fixed at birth, aca7146)
        langbridg.ts:351                      sentenceCount == 0 -> 0

    The TS returns 0, which reads as "no hedging at all" — a real and
    confident measurement asserted where none was taken. Asserted BY TYPE so
    no refactor can round it back into a number.

    ★ THE SERVER AND THE PHONE DISAGREE HERE, DELIBERATELY. The phone is
    wrong."""
    for empty in ("", "   ", "\n\n", None, 42, []):
        out = app_module._hedge_ratio(empty)
        assert not isinstance(out, float), f"{empty!r} produced a number"
        assert out == "UNMAPPED"


def test_the_payload_carries_T_and_tags_it_a_candidate():
    """The arithmetic is ported exactly; the hedge-ratio -> arousal MAPPING
    is asserted by a comment, not derived. Tagged like D and N."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert isinstance(p["T"], float)
    assert p["T_status"] == "CANDIDATE"


def test_the_payload_marks_E_absent_rather_than_omitting_it():
    """★★★ Doctrine 8.4 names four per-turn flows — E, D, T, N. E was the
    only one with no key at all, and an ABSENT field is quieter than an
    UNMAPPED one: a reader sees three flows and never asks about a fourth."""
    p = app_module._emophysics_shadow("u", HIGH)
    assert p["E"] == "UNMAPPED"
    assert p["E_status"] == "UNMAPPED"
    assert "no producer identified" in p["reason"]


def test_the_reason_no_longer_claims_T_has_no_producer():
    """That clause was the falsified one: it described where hedgeRatio RAN
    and was read as a constraint on where it COULD run."""
    reason = app_module._emophysics_shadow("u", LOW)["reason"]
    assert "no server-side producer" not in reason


def test_computed_is_still_false_with_three_flows_mapped():
    """D, N and T are measured; E is not. `computed` stays False until the
    state is whole — three of four is not a state."""
    assert app_module._emophysics_shadow("u", HIGH)["computed"] is False
