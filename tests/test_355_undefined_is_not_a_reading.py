"""#355 — undefined is not a reading. Three sites, one rule.

★ THE RULE, ALREADY RATIFIED. v1.8.3 §14.7 removed ``dominant`` for
"deriving a categorical claim from a strict inequality where only a
magnitude exists" (``ELINS/standard_elins.py:305-309``). #355 applies the
same rule at the three places absence was still entering a computation as
a value:

    SITE 1  ``turn_record.score_record`` — a bearing the expectation
            CLAIMED but the observation never took is ``undefined``, not
            ``missed``. A cross-writer omission was deflating trust.
    SITE 2  ``el_ins_analyzer._classify_ratio`` — 0/0 is ``UNMAPPED``,
            not ``balanced``; and an UNMAPPED frame is EXCLUDED from the
            TSI arithmetic rather than scored as a position.
    SITE 3  ``standard_elins`` — the domain lexicon matches on word
            boundaries, and a top score below the floor names NO domain.

★★ THE REFUTER IS THE POINT, twice over, and both refuters caught a real
defect in this build rather than confirming it:

  1. ``test_3b_per_token_pass`` MEASURES every one of the 78 domain
     tokens against the INFLECTED FORM IT EXISTS TO CATCH — "the laws",
     "the markets", "a constitutional question" — never against the token
     echoed back inside its own probe. The first 3b pass written for this
     order did the latter, asked a question that could not return "no",
     and passed a rule that silently killed 45 of the 78 tokens.
  2. ``test_the_reachable_classification_distribution`` pins how often
     0/0 is actually reached, because a sentinel that fires on nothing is
     decoration and a sentinel that fires on everything is a rename.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import re  # noqa: E402
from collections import Counter  # noqa: E402

import pytest  # noqa: E402

import turn_record as tr  # noqa: E402
from ELINS import standard_elins as se  # noqa: E402
from el_ins import el_ins_analyzer as A  # noqa: E402
from el_ins import el_ins_store as ST  # noqa: E402


# ==========================================================================
# SITE 1 — R15. A claimed bearing the observation never took.
# ==========================================================================
def test_r15_a_claimed_key_absent_from_the_observation_is_undefined():
    """The whole of R15, in one record.

    ``s_state`` is CLAIMED by the expectation and ABSENT from the
    observation, because the writer that sealed it and the writer that
    observed the next turn are not the same writer (#330). Before this
    branch that scored ``missed`` — a wrong answer counted against a
    question the observer never asked.
    """
    rec = {
        "expectation": {"boundary": "held", "s_state": "S3"},
        "observation": {"boundary": "held"},   # no s_state: never computed
    }
    out = tr.score_record(rec)
    assert out["per_bearing"]["s_state"] == "undefined"
    assert out["matched"] == 1              # boundary held, as claimed
    assert out["missed"] == 0               # ★ nothing is counted against
    assert out["undefined"] >= 1


def test_r15_does_not_swallow_a_real_disagreement():
    """The branch is keyed on ABSENCE, not on disagreement. A bearing that
    is present and different is still ``missed`` — that is the whole point
    of the score and #355 must not soften it."""
    rec = {
        "expectation": {"boundary": "held", "s_state": "S3"},
        "observation": {"boundary": "held", "s_state": "S1"},
    }
    out = tr.score_record(rec)
    assert out["per_bearing"]["s_state"] == "missed"
    assert out["missed"] == 1


def test_flatten_scalars_never_emits_a_none_leaf():
    """★ THE FACT THE NEXT TEST DEPENDS ON, MEASURED RATHER THAN ASSUMED.

    "The observation says not-present" is expressed by the key being
    ABSENT — never by the key being present with value ``None``. If that
    ever changes, the guard in ``score_record`` is guarding the wrong
    shape and the test below is testing a case that no longer matters.
    """
    obs = tr.build_geometry_observation(
        "The filing is urgent and the deadline creates real pressure."
    )
    flat = tr.flatten_scalars(obs)
    assert flat, "the observation must emit scalar leaves"
    assert [k for k, v in flat.items() if v is None] == []


def test_r15_absence_expecting_absence_is_still_a_match():
    """★★ CT-1's STANDING RULE, IN THE ONLY SHAPE THE SYSTEM PRODUCES.

    ``score_record``'s own docstring: "absence expecting absence is a
    trust INCREASE (both sides say 'not present', which is a hit)." Since
    ``flatten_scalars`` never emits a ``None`` leaf (proved above), that
    rule is ALWAYS expressed as: the expectation holds the key with value
    ``None``, and the observation does not hold the key at all.

    ★ THIS IS THE CASE R15 ALMOST DELETED. Without the
    ``exp.get(b) is not None`` guard, the new branch intercepts this
    first and scores it ``undefined`` — turning every one of CT-1's
    trust increases into a non-event. An earlier draft of this test used
    ``observation={"boundary": None}``, a shape no observer produces, and
    so passed while the rule was broken.
    """
    rec = {
        "expectation": {"boundary": None},
        "observation": {"primitives": {"P1": 1}},   # boundary ABSENT
    }
    out = tr.score_record(rec)
    assert out["per_bearing"]["boundary"] == "matched"
    assert out["matched"] == 1
    assert out["per_bearing"]["boundary"] != "undefined"


def test_r15_fires_only_on_a_positive_claim_with_nothing_to_check_it():
    """The branch's exact domain, stated as a table. A None expectation is
    not a claim; a valued expectation is."""
    absent_obs = {"primitives": {"P1": 1}}
    # a POSITIVE claim, never computed -> undefined
    assert tr.score_record(
        {"expectation": {"s_state": "S3"}, "observation": absent_obs}
    )["per_bearing"]["s_state"] == "undefined"
    # a NULL claim, never computed -> matched (absence expecting absence)
    assert tr.score_record(
        {"expectation": {"s_state": None}, "observation": absent_obs}
    )["per_bearing"]["s_state"] == "matched"


def test_r15_is_a_no_op_on_a_pre_330_record_and_the_test_proves_it():
    """★ PROVED, NOT ASSERTED.

    The claim in the source comment is that the new branch was structurally
    unreachable before ``s_state`` existed, because the base observation
    emits an INVARIANT key set. So: build the observation the pre-#330
    callers built, seal an expectation over every scalar leaf of it, and
    show that not one key is absent. If ``build_geometry_observation`` ever
    becomes conditional, this fails and the no-op claim is retired with it.
    """
    TEXTS = [
        "The filing is urgent and the deadline creates real pressure.",
        "ok",
        "We disagree about the schedule but not about the facts, and the "
        "tension has been building for weeks.",
        "Nothing much happened today.",
    ]
    key_sets = [
        frozenset(tr.flatten_scalars(tr.build_geometry_observation(t)))
        for t in TEXTS
    ]
    # ★ THE INVARIANCE CLAIM, MEASURED ACROSS DIFFERENT TEXTS -- not a set
    # compared against itself. If build_geometry_observation ever emits a
    # key conditionally, these diverge and the no-op claim is retired.
    assert len(set(key_sets)) == 1, (
        "the base observation is NOT key-invariant across texts; the R15 "
        f"no-op claim no longer holds. Differences: "
        f"{[sorted(s ^ key_sets[0]) for s in key_sets if s != key_sets[0]]}"
    )

    # Now the no-op itself: seal an expectation claiming every leaf of ONE
    # observation and score it against a DIFFERENT turn's observation --
    # the cross-writer situation R15 exists for. Because the key set is
    # invariant, nothing is ever absent, so the branch cannot fire.
    a = tr.build_geometry_observation(TEXTS[0])
    b_obs = tr.build_geometry_observation(TEXTS[2])
    out = tr.score_record(
        {"expectation": dict(tr.flatten_scalars(a)), "observation": b_obs}
    )
    flat_a = tr.flatten_scalars(a)
    claimed_undefined = [
        k for k, v in out["per_bearing"].items()
        if v == "undefined" and k in flat_a
    ]
    assert claimed_undefined == [], (
        "the R15 branch fired on a pre-#330 record shape: "
        f"{claimed_undefined}"
    )


# ==========================================================================
# SITE 2a — 0/0 is not the middle band.
# ==========================================================================
def test_zero_over_zero_does_not_classify_balanced():
    """The order's own wording: "a 0/0 read that does not classify
    balanced". Both scores zero is the ABSENCE of a reading, and it must
    not wear the label a real near-parity reading wears."""
    assert A._classify_ratio(0.0, 0.0) == A.RATIO_UNMAPPED
    assert A._classify_ratio(0.0, 0.0) != "balanced"


def test_the_unmapped_mode_is_not_normal():
    """``normal`` is a PRESCRIPTION — proceed as usual. An unmapped read
    has no basis to prescribe anything, so it must not fall through."""
    assert A._mode_for(A.RATIO_UNMAPPED) == A.MODE_UNMAPPED
    assert A._mode_for(A.RATIO_UNMAPPED) != "normal"
    # the other three are untouched
    assert A._mode_for("high_el") == "stabilize"
    assert A._mode_for("high_ins") == "expand"
    assert A._mode_for("balanced") == "normal"


def test_a_real_near_parity_read_is_still_balanced():
    """★ THE SEPARATION IS THE POINT. If 0/0 and a genuine near-parity
    read both land on ``UNMAPPED``, #355 has destroyed a reading instead
    of naming an absence."""
    assert A._classify_ratio(0.39, 0.32) == "balanced"
    assert A._classify_ratio(5.0, 0.0) == "high_el"
    assert A._classify_ratio(0.0, 5.0) == "high_ins"


def test_empty_input_is_unmapped_end_to_end():
    r = A.analyze_text("", provider_mode="deterministic")
    assert r["analysis"]["ratio_classification"] == A.RATIO_UNMAPPED
    assert r["reasoning_mode"] == A.MODE_UNMAPPED


def test_the_llm_validator_admits_the_new_pair_and_still_rejects_junk():
    """The coercer gates on an allowlist. A model that legitimately returns
    the new state must not be thrown away — and a model that returns
    nonsense must still be."""
    good = {
        "analysis": {"ratio_classification": A.RATIO_UNMAPPED},
        "reasoning_mode": A.MODE_UNMAPPED,
    }
    assert A._coerce_llm_output(good) is not None
    bad = {
        "analysis": {"ratio_classification": "vibes"},
        "reasoning_mode": "normal",
    }
    assert A._coerce_llm_output(bad) is None


def test_the_reachable_classification_distribution():
    """★ THE REFUTER. A sentinel that fires on nothing is decoration; one
    that fires on everything is a rename. This MEASURES which it is over
    ordinary turns, and pins the answer so a lexicon change that moves it
    fails loudly.

    Measured 2026-09-18: 0/0 is the COMMON case for conversational text
    (the EL/INS term sets are exact-token and small), so ``UNMAPPED`` is
    reached often. ``balanced`` survives only for genuine near-parity.
    """
    ORDINARY = [
        "Can you help me draft a response to this?",
        "The document was filed on Tuesday.",
        "I went to the store and then came home.",
        "Thanks, that makes sense.",
    ]
    INSTITUTIONAL = [
        "The court issued a ruling on the statute and the contract provision.",
        "The judgment cited precedent, the amendment, and the settlement terms.",
    ]
    EMOTIVE = [
        "This is an absolutely catastrophic disaster and a complete emergency.",
    ]
    PARITY = [
        "The urgent filing is critical and the court deadline is an emergency.",
    ]

    def cls(t):
        return A.analyze_text(t, provider_mode="deterministic")[
            "analysis"]["ratio_classification"]

    seen = Counter(cls(t) for t in ORDINARY + INSTITUTIONAL + EMOTIVE + PARITY)

    # All four states are reachable. None of them is dead code.
    assert set(seen) == {A.RATIO_UNMAPPED, "high_ins", "high_el", "balanced"}, seen
    # Ordinary conversational turns are the ones that flip.
    assert all(cls(t) == A.RATIO_UNMAPPED for t in ORDINARY)
    # A reading, once there is one, is never UNMAPPED.
    for t in INSTITUTIONAL + EMOTIVE + PARITY:
        assert cls(t) != A.RATIO_UNMAPPED, t


# ==========================================================================
# SITE 2b — an undefined frame is excluded from the TSI arithmetic.
# ==========================================================================
def _row(cls, el, ins, mode="normal", ts=0.0):
    return {
        "operator_id": "op_355",
        "thread_id": "t355",
        "timestamp": ts,
        "source": "per_turn",
        "result": {
            "analysis": {
                "el_score": el, "ins_score": ins,
                "ratio_classification": cls,
            },
            "reasoning_mode": mode,
        },
    }


def test_three_reads_one_undefined_tsi_is_taken_over_the_two_defined():
    """The order's own wording: "a three-read thread with one undefined
    frame, TSI over the two defined".

    ★ PROVED BY EQUALITY, not by eyeballing a number: the three-row thread
    with one undefined frame must score IDENTICALLY to the two-row thread
    that contains only the defined frames. That is what "over the two
    defined" means, and it is the only formulation a later tuning of
    ``_compute_tsi`` cannot quietly invalidate.
    """
    defined_a = _row("high_ins", 0.0, 5.06, mode="expand", ts=3.0)
    undefined = _row(A.RATIO_UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=2.0)
    defined_b = _row("high_ins", 0.0, 4.80, mode="expand", ts=1.0)

    # newest-first, as the store hands them over
    three = ST._stability_from_rows("t355", [defined_a, undefined, defined_b], 10)
    two = ST._stability_from_rows("t355", [defined_a, defined_b], 10)

    assert three["tsi"] == two["tsi"]
    assert three["stability"] == two["stability"]
    # ``window`` reports frames that CARRIED A READING, never the sample size.
    assert three["window"] == 2
    assert three["undefined_frames"] == 1
    # and the untouched thread reports no exclusions at all
    assert two["undefined_frames"] == 0


def test_an_undefined_frame_cannot_manufacture_a_flip():
    """The measured defect: a 0/0 read between two like reads was scored as
    a position, so the classification 'changed' twice and the thread read
    as oscillating. Excluded, the two real reads agree."""
    same = [
        _row("high_ins", 0.0, 5.0, mode="expand", ts=float(i))
        for i in (5.0, 3.0, 1.0)
    ]
    with_gap = [same[0],
                _row(A.RATIO_UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=4.0),
                same[1],
                _row(A.RATIO_UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=2.0),
                same[2]]
    clean = ST._stability_from_rows("t355", same, 10)
    gapped = ST._stability_from_rows("t355", with_gap, 10)
    assert gapped["tsi"] == clean["tsi"]
    assert gapped["stability"] == clean["stability"]
    assert gapped["undefined_frames"] == 2


def test_an_all_undefined_window_reports_zero_frames_carried_a_reading():
    """★ NAMED, NOT FIXED. The shape is the one the no-rows branch has
    always returned, because every reader already handles it and #355 is
    not a wire ruling. ``window == 0`` is the honest part. That
    ``stability``/``tsi`` still read "stable"/100 over an empty series is
    the same D5 defect one level up, and it is carried as R-355-A rather
    than silently changed here."""
    rows = [_row(A.RATIO_UNMAPPED, 0.0, 0.0, mode=A.MODE_UNMAPPED, ts=float(i))
            for i in (3.0, 2.0, 1.0)]
    out = ST._stability_from_rows("t355", rows, 10)
    assert out["window"] == 0
    assert out["undefined_frames"] == 3
    # pinned so R-355-A's resolution has to come through this test
    assert out["stability"] == "stable" and out["tsi"] == 100


def test_a_pre_v70_row_with_no_classification_key_is_not_retrofitted():
    """#51 / #90. A stored row that predates the key keeps reading the way
    it always read (it defaults to ``balanced`` downstream). Rewriting how
    a stored record reads is a retrofit and this build does not do one."""
    old = {
        "operator_id": "op_355", "thread_id": "t355", "timestamp": 1.0,
        "source": "per_turn",
        "result": {"analysis": {"el_score": 1.0, "ins_score": 1.0}},
    }
    out = ST._stability_from_rows("t355", [old], 10)
    assert out["undefined_frames"] == 0      # not swept into the new state
    assert out["window"] == 1


# ==========================================================================
# SITE 3 — the domain matcher and the floor.
# ==========================================================================
#: One probe per domain token: THE INFLECTED FORM THE TOKEN EXISTS TO
#: CATCH. Never the token echoed back inside its own probe — that is the
#: tautology the first 3b pass shipped, and it is what let a rule through
#: that killed 45 of 78 tokens.
_TOKEN_PROBES: dict = {
    "law": "the laws of the state", "court": "two courts ruled",
    "judge": "the judges agreed", "ruling": "recent rulings",
    "constitut": "a constitutional question",
    "statute": "several statutes apply", "legal": "legally binding",
    "litigat": "ongoing litigation", "supreme court": "the supreme court held",
    "judic": "judicial review", "institution": "public institutions",
    "agency": "federal agencies", "regulat": "new regulations",
    "ministr": "the ministry said", "bureau": "the bureaus",
    "oversight": "oversight board", "compliance": "compliance costs",
    "governance": "governance rules", "watchdog": "watchdogs warned",
    "econom": "the economy slowed", "market": "the markets fell",
    "inflat": "inflation rose", "supply": "supplies ran short",
    "demand": "demands grew", "tariff": "new tariffs",
    "trade": "trades settled", "currenc": "the currency fell",
    "fiscal": "fiscal policy", "monetary": "monetary policy",
    "deficit": "the deficits widened", "growth": "growth stalled",
    "recession": "two recessions", "china": "china said",
    "russia": "russia said", "us-": "us-china talks", "u.s.": "the u.s. said",
    "nato": "nato members", "border": "the borders closed",
    "alliance": "two alliances", "diploma": "diplomatic talks",
    "sanction": "new sanctions", "treaty": "two treaties",
    "war": "the wars ended", "public": "the publics view",
    "voter": "the voters chose", "protest": "the protests grew",
    "movement": "two movements", "communit": "the community spoke",
    "popular": "popular support", "social": "social media",
    "media coverage": "media coverage rose", "sentiment": "sentiments shifted",
    "i ": "i went", "my ": "my case", "feel": "she feels",
    "myself": "myself alone", "we ": "we went", "our ": "our case",
    "she ": "she went", "he ": "he went", "they ": "they went",
    "personal": "personally involved", "ai ": "ai systems",
    "model": "the models ran", "algorithm": "the algorithms",
    "platform": "two platforms", "infrastructure": "infrastructure spend",
    "software": "software updates", "chip": "the chips shipped",
    "data center": "a data center", "climate": "climate policy",
    "carbon": "carbon price", "emission": "carbon emissions",
    "ecolog": "ecological damage", "environment": "environmental review",
    "drought": "two droughts", "biodivers": "biodiversity loss",
    "energy supply": "energy supply risk",
}

_ALL_TOKENS = [(d, t) for d, ts in se._DOMAIN_LEXICON.items() for t in ts]


def test_every_domain_token_has_an_honest_probe():
    """The probe table must cover the lexicon exactly. If a token is added
    without a probe, 3b below would silently stop testing it."""
    missing = [t for _d, t in _ALL_TOKENS if t not in _TOKEN_PROBES]
    assert missing == [], f"tokens with no inflected probe: {missing}"
    assert len(_ALL_TOKENS) == 78


def test_3b_per_token_pass():
    """★ THE 3b PASS, run as a test rather than as a one-off script.

    For every one of the 78 tokens: if it scored under the PRE-#355
    substring rule against the form it exists to catch, it must still
    score under the boundary rule. Zero may be lost.

    Measured 2026-09-18: 75 of 78 tokens match under BOTH rules; 0 lost;
    0 spuriously gained. The three that match under NEITHER — ``agency``
    → "agencies", ``supply`` → "supplies", ``treaty`` → "treaties" — are
    y→ies plurals the substring rule missed too. That is a pre-existing
    limitation of the LEXICON, not a #355 regression, and it is named here
    rather than quietly fixed.
    """
    lost, gained, both = [], [], 0
    for dom, tok in _ALL_TOKENS:
        probe = _TOKEN_PROBES[tok]
        old = probe.count(tok)                                  # pre-#355
        new = len(se._compile_domain_token(tok).findall(probe))  # now
        if old > 0 and new == 0:
            lost.append((dom, tok, probe))
        if old == 0 and new > 0:
            gained.append((dom, tok, probe))
        if old > 0 and new > 0:
            both += 1

    assert lost == [], (
        "tokens that scored before and cannot score now — the order says "
        f"HOLD: {lost}"
    )
    assert gained == [], f"tokens that spuriously gained: {gained}"
    assert both == 75
    # the three y->ies plurals, named explicitly so a lexicon fix updates this
    neither = sorted(
        tok for _d, tok in _ALL_TOKENS
        if _TOKEN_PROBES[tok].count(tok) == 0
    )
    assert neither == ["agency", "supply", "treaty"]


def test_no_domain_loses_the_ability_to_score():
    """★ THIS TEST IS WEAK BY CONSTRUCTION AND SAYS SO.

    It passes under every candidate rule ever tried here, including the two
    that were wrong, because each domain has nine-ish tokens and only one
    needs to fire. It certifies "not totally dead", nothing more. The real
    per-token coverage is ``test_3b_per_token_pass`` (right edge),
    ``test_a_root_token_matches_inside_a_prefixed_word`` (left edge) and
    ``test_a_pronoun_token_does_not_fire_where_no_pronoun_is``
    (over-firing). Kept because "a domain went completely dark" is still
    worth catching; NOT counted as coverage.
    """
    for dom, tokens in se._DOMAIN_LEXICON.items():
        text = " ".join(_TOKEN_PROBES[t] for t in tokens)
        hits = sum(1 for t in tokens
                   if se._compile_domain_token(t).search(text))
        assert hits > 0, f"domain {dom} can no longer score at all"
        # and state the per-domain margin, so a rule that guts a domain down
        # to its last surviving token fails here instead of passing quietly.
        assert hits >= len(tokens) - 3, (
            f"domain {dom} scores on only {hits} of {len(tokens)} tokens"
        )


def test_the_per_token_cap_survives_the_new_domain_branch():
    """★ THE CAP WAS RE-IMPLEMENTED IN THE NEW BRANCH AND HAD NO TEST.

    ``_count_matches``'s domain path is new code in #355, and it carries
    its own ``min(5, hits)``. Deleting that ``min`` passed the whole file.
    A document saying "market" forty times would then score economic 40.0,
    swamping every other domain and making the floor meaningless on any
    text longer than a few paragraphs. A docstring asserting an invariant
    is not a test — which is this build's own stated failure mode.
    """
    forty = "the market " * 40
    assert forty.count("market") == 40
    scores = se._count_matches(forty, se._DOMAIN_LEXICON)
    assert scores["economic"] == 5.0, scores
    # the cap is PER TOKEN, not per domain: two capped tokens sum to 10
    two = ("the market " * 40) + ("tariff " * 40)
    assert se._count_matches(two, se._DOMAIN_LEXICON)["economic"] == 10.0


#: The eight tokens whose trailing SPACE is load-bearing — it is the whole
#: difference between a pronoun and a prefix.
_SPACE_TOKENS = ("i ", "my ", "we ", "our ", "she ", "he ", "they ", "ai ")


def test_the_lexicon_still_carries_its_eight_space_tokens():
    """If a token loses its space in the lexicon, the rule below silently
    starts treating it as a prefix. Pin the input, not just the output."""
    present = [t for _d, t in _ALL_TOKENS if t.endswith(" ")]
    assert sorted(present) == sorted(_SPACE_TOKENS)


#: Root tokens with the PREFIXED word each exists to catch. The left edge
#: is the axis two earlier drafts of this file could not test at all,
#: because every probe in ``_TOKEN_PROBES`` puts its token at a word start.
_ROOT_PREFIXED = {
    "regulat":   "deregulation of the agency",
    "constitut": "ruled unconstitutional",
    "econom":    "macroeconomic conditions",
    "ministr":   "the administration said",
    "legal":     "an illegal act",
    "agency":    "the interagency panel",
    "carbon":    "hydrocarbons burned",
    "judic":     "prejudicial error",
    "inflat":    "disinflation continues",
    "currenc":   "cryptocurrency markets",
}


def test_the_token_class_is_read_off_the_lexicon():
    """★ THE TEST THAT CAUGHT THIS BUILD'S SECOND AND THIRD DEFECTS.

    Two earlier drafts asserted a single blanket rule, each mirroring the
    implementation of the moment, so neither could fail:
      - one asserted ``re.escape(tok.strip())``, mirroring a ``.strip()``
        that turned the pronouns into open prefixes;
      - one asserted a leading ``\\b`` on every token, which deletes every
        root-inside-a-word match.

    The rule is READ OFF the lexicon: a trailing space marks a whole word
    and gets ``\\b``; everything else is a root and is matched anywhere.
    """
    for _dom, tok in _ALL_TOKENS:
        pat = se._compile_domain_token(tok).pattern
        if tok.endswith(" "):
            assert pat == r"\b" + re.escape(tok), tok
        else:
            assert pat == re.escape(tok), tok
            assert not pat.startswith(r"\b"), (
                f"{tok!r} is a ROOT and must not carry a leading boundary"
            )
    # nothing is ever stripped
    for tok in _SPACE_TOKENS:
        assert se._compile_domain_token(tok).pattern != r"\b" + re.escape(tok.strip())


def test_a_root_token_matches_inside_a_prefixed_word():
    """★ THE LEFT EDGE. A blanket leading boundary scores 0 of 10 here and
    blanks domain history on text whose domain is unambiguous."""
    for tok, probe in _ROOT_PREFIXED.items():
        hits = se._compile_domain_token(tok).findall(probe)
        assert hits, f"root {tok!r} no longer matches inside {probe!r}"
    # and end to end, the two texts a blanket boundary silently emptied
    assert _top("Deregulation of the agency was challenged as "
                "unconstitutional.") == "institutional"
    assert _top("Macroeconomic conditions and socioeconomic pressure "
                "dominated.") == "economic"


def test_every_root_token_has_a_left_edge_probe_or_is_named():
    """Roots without a prefixed probe are LISTED, so the gap is visible
    rather than silent. A probe table that silently covers 10 of 70 is the
    same defect as a probe built from its own token."""
    roots = {t for _d, t in _ALL_TOKENS if not t.endswith(" ")}
    covered = set(_ROOT_PREFIXED)
    assert covered <= roots
    assert len(covered) == 10, (
        f"left-edge coverage is {len(covered)} of {len(roots)} roots; "
        "extend _ROOT_PREFIXED rather than narrowing this assertion"
    )


#: Prose containing NOT ONE of the eight pronouns, but full of the words
#: that a mis-compiled pronoun token eats: it / is / in / issue / important
#: / informed (the ``.strip()`` cases), and hearing / held / her / health /
#: here (the ``he``-initial cases).
_NO_PRONOUN_CARRIER = (
    "the courts have applied the statutes. it is important that the "
    "rulings issue in writing, and the judges were informed. the hearing "
    "was held here and her health improved."
)


def test_a_pronoun_token_does_not_fire_where_no_pronoun_is():
    """★ THE OVER-FIRING CHECK, COUNTED.

    An earlier draft asserted ``all(h == tok for h in hits)``. The compiled
    pattern is a LITERAL with no groups, so every element ``findall`` can
    return is byte-identical to the token: that assertion was true by
    construction on every possible input and measured nothing. It was the
    FOURTH tautology in this build, on the fourth axis.

    This counts instead, against prose that contains none of the eight
    pronouns. Under the ``.strip()`` rule ``i `` scored 6 here; it must
    score 0.
    """
    for tok in _SPACE_TOKENS:
        n = len(se._compile_domain_token(tok).findall(_NO_PRONOUN_CARRIER))
        assert n == 0, f"{tok!r} fired {n}x on prose with no pronoun in it"
    scores = se._count_matches(_NO_PRONOUN_CARRIER, se._DOMAIN_LEXICON)
    assert scores["personal"] == 0.0, scores
    assert _top(_NO_PRONOUN_CARRIER) == "legal"


def test_a_pronoun_token_does_fire_where_the_pronoun_is():
    """The other direction, or the test above passes on a dead token."""
    SENTENCES = {
        "i ": "i went", "my ": "my case", "we ": "we went",
        "our ": "our case", "she ": "she went", "he ": "he went",
        "they ": "they went", "ai ": "ai systems",
    }
    for tok, s in SENTENCES.items():
        assert len(se._compile_domain_token(tok).findall(s)) == 1, tok


def test_the_enumerator_I_still_reads_personal_KNOWN_DEFECT():
    """★★ SITE 3 IS NOT CLOSED, AND THIS PINS EXACTLY HOW FAR IT GOT.

    #355 3a was opened because purely legal text was classified PERSONAL.
    It fixed the mechanism it named — ``'he '`` inside ``'the '`` — but a
    SECOND mechanism produces the same wrong reading and survives: the
    token ``'i '`` matches the standalone enumerator "I". Lowercased,
    "Article I", "Title I", "Schedule I", "Exhibit I", "Part I",
    "Section I", "Appendix I", "Chapter I", "Volume I", "Phase I",
    "Class I", "Type I" are each a word-standalone ``i`` followed by a
    space, and a leading ``\\b`` cannot discriminate — unlike ``'he '``
    inside ``'the '``, the enumerator IS a whole word.

    ★ THIS IS THE REGISTER THE DEPLOYMENT ACTUALLY READS. Statutes and
    contracts are made of numbered Articles, Titles and Schedules.

    ★ NOT A REGRESSION — the pre-#355 substring rule read these personal
    too, at higher magnitude (6.0 vs 4.0 on the first carrier). #355
    reduces the score and does not change the verdict. And
    ``DOMAIN_MIN_SIGNAL`` is no protection: every carrier below scores
    >= 2.0 and is therefore NAMED, not withheld.

    ★ PINNED AS CURRENT TRUTH, NOT AS DESIRED TRUTH. The fix is a lexicon
    edit (narrow ``'i '``, or add a preceding-word stop-list the way
    ``_is_negated`` does for the primitive lexicon), and CT-1 has scoped
    the domain lexicon beyond site 3 OUT. When that ruling comes, this
    test FAILS LOUDLY, which is the point — carried as R-374-A.
    """
    CARRIERS = [
        ("The courts have applied the statutes. It is important that "
         "Schedule I and Title I issue in writing. Article I was informed "
         "by Part I of Exhibit I.", 4.0),
        ("Article I confers the power; Title I applies; Schedule I is "
         "annexed.", 3.0),
        ("Part I of the agreement, Exhibit I, and Section I are attached.", 2.0),
        ("Phase I closed. Class I shares and Type I errors were reviewed "
         "in Appendix I.", 3.0),
        ("Chapter I and Chapter II of Volume I were served on counsel.", 2.0),
        ("The claim under Title I and Schedule I was denied by the agency.", 2.0),
    ]
    for text, want_personal in CARRIERS:
        scores = se._count_matches(text.lower(), se._DOMAIN_LEXICON)
        assert scores["personal"] == want_personal, (text, scores)
        assert scores["personal"] >= se.DOMAIN_MIN_SIGNAL      # the floor does not save it
        assert _top(text) == "personal", (text, scores)        # ← fails when R-374-A lands

    # ★ the multi-character numerals are NOT implicated: in "ii " the first
    # i is followed by i and the second has no boundary before it. That is
    # why carrier 5 scores 2.0 and not 3.0.
    assert se._compile_domain_token("i ").findall("chapter ii of volume i ") == ["i "]


def test_he_no_longer_matches_inside_the_nor_inside_he_initial_words():
    """The defect the site was opened for, stated as numbers — including
    the he-initial words an earlier probe happened not to contain."""
    THIRD_PERSON = (
        "the court reviewed the filing and the statute that the parties "
        "cited; the hearing was held here and her health improved"
    )
    assert THIRD_PERSON.count("he ") == 5          # the pre-#355 reading
    assert se._compile_domain_token("he ").findall(THIRD_PERSON) == []
    # a real pronoun still scores
    assert len(se._compile_domain_token("he ").findall("he said he would call")) == 2
    # and "i " does not eat "it/is/in"
    assert se._compile_domain_token("i ").findall("it is in issue") == []
    assert se._compile_domain_token("i ").findall("i went") == ["i "]


# --- the three regressions the order named, plus the one that refutes the
# --- rule this build originally shipped ------------------------------------
def _top(text):
    top, _scores = se._domain_top(
        se._count_matches(text.lower(), se._DOMAIN_LEXICON)
    )
    return top


def test_regression_legal_third_person_reads_legal():
    assert _top(
        "The court issued the ruling. The statute governs the matter. "
        "The judge signed it."
    ) == "legal"


def test_regression_bureaucratic_reads_none():
    assert _top(
        "The Commission published the consultation document on Tuesday morning."
    ) is None


def test_regression_genuinely_personal_reads_personal():
    assert _top(
        "I feel uncertain about my own position and we have not agreed."
    ) == "personal"


def test_regression_an_inflected_legal_brief_still_reads_legal():
    """★ THE REFUTER THAT CAUGHT THIS BUILD.

    Real legal prose is plural and inflected: "the courts", "the statutes",
    "the rulings", "constitutional", "litigation", "the judges". Under the
    trailing-``\\b`` rule #355 originally shipped, this text scored ``{}``
    — every legal token dead — and named NO domain. It is the case that
    distinguishes "closed the ``'he '`` hole" from "emptied the lexicon".
    """
    BRIEF = (
        "The courts have applied the statutes consistently. The rulings cite "
        "the constitutional text, and the litigation continues before the "
        "judges."
    )
    scores = se._count_matches(BRIEF.lower(), se._DOMAIN_LEXICON)
    assert scores["legal"] >= 2.0
    assert _top(BRIEF) == "legal"


def test_regression_plural_economic_prose_still_reads_economic():
    assert _top(
        "The markets fell as the tariffs took hold and the deficits widened."
    ) == "economic"


# --- 3c, the floor ---------------------------------------------------------
def test_the_floor_withholds_the_name_on_a_single_mention():
    """``DOMAIN_MIN_SIGNAL`` is a live path, not decoration: one token is
    an OCCURRENCE, two is a signal. Both of these score exactly 1.0 and
    must therefore name nothing."""
    for text in (
        "The report was long, and only one line mentioned climate.",
        "The novel ends just before the war.",
    ):
        scores = se._count_matches(text.lower(), se._DOMAIN_LEXICON)
        nz = {k: v for k, v in scores.items() if v > 0.0}
        assert nz, "probe no longer scores at all; the floor is untested"
        assert max(nz.values()) < se.DOMAIN_MIN_SIGNAL
        assert _top(text) is None


def test_the_floor_withholds_the_name_but_never_the_reading():
    """★ The floor hides the CLAIM, not the MEASUREMENT. A reader must
    still be able to see what scored."""
    text = "The novel ends just before the war."
    top, scores = se._domain_top(
        se._count_matches(text.lower(), se._DOMAIN_LEXICON)
    )
    assert top is None
    assert scores.get("geopolitical") == 1.0


def test_the_floor_reaches_every_path_that_crowns_a_domain():
    """★ 3c IS NOT INSTALLED IF IT IS INSTALLED IN ONE PLACE OF THREE.

    ``_apply_domain_overlay`` and ``_merge_eso`` both used to re-implement
    the crown inline. Measured before the fix, on a text scoring 1.0 (below
    the floor): the global read returned ``top=None`` and ALL SIX regional
    overlays returned ``top="geopolitical"`` — while stamping
    ``matcher_version`` v2, claiming the calibration they had bypassed.
    """
    import copy

    from ELINS import regional_elins as re_

    BELOW = se.generate_ELINS("The novel ends just before the war.")
    assert BELOW["domain_mapping"]["top"] is None          # the floor refused
    assert BELOW["domain_mapping"]["scores"]["geopolitical"] == 1.0

    for region in re_.REGION_PROFILES:
        dm = re_._apply_domain_overlay(
            copy.deepcopy(BELOW), region)["domain_mapping"]
        assert dm["top"] is None, f"{region} crowned below the floor: {dm}"
        assert dm["effective_top"] is None, region

    # ★ AND THE PATH PRODUCTION ACTUALLY TAKES, which the block above does
    # NOT reach: run_regional_elins always supplies profile
    # ["default_domain_hint"] (regional_elins.py:416), so dm["hint"] is never
    # None live and `if not dm.get("hint")` never fires. The reachable
    # divergence is therefore `top` going null while `effective_top` falls
    # back to the hint -- which is the hint doing its job, not the floor
    # being bypassed. An earlier draft asserted only the hint-less shape and
    # so could not fail on anything production produces.
    for region, profile in re_.REGION_PROFILES.items():
        dm = re_.run_regional_elins(region, "u1")["domain_mapping"]
        assert dm["hint"] == profile["default_domain_hint"], region
        if dm["top"] is None:
            assert dm["effective_top"] == dm["hint"], (
                f"{region}: top is None but effective_top is not the hint"
            )
        else:
            assert dm["scores"][dm["top"]] >= se.DOMAIN_MIN_SIGNAL, (
                f"{region} crowned {dm['top']} below the floor: {dm['scores']}"
            )

    # and a reading that DOES clear the floor is still crowned everywhere
    ABOVE = se.generate_ELINS(
        "The courts have applied the statutes. The rulings cite the "
        "constitutional text and the litigation continues."
    )
    assert ABOVE["domain_mapping"]["top"] == "legal"
    for region in re_.REGION_PROFILES:
        dm = re_._apply_domain_overlay(
            copy.deepcopy(ABOVE), region)["domain_mapping"]
        assert dm["top"] == "legal", region


def test_the_regional_overlay_feeds_the_floor_a_different_unit_KNOWN():
    """★ R-374-B, PINNED AS CURRENT TRUTH.

    The floor is calibrated in whole-token hit counts. The regional
    overlay multiplies (``round((raw + 0.1) * mult, 4)``), so it hands
    ``_domain_top`` weighted magnitudes instead — and #355 is what routed
    it there. Measured: five of six regions now report ``top: None`` where
    all six crowned before. The surface is unchanged because the hint
    stands in for ``effective_top``; it is ``top`` that went null.

    Pinned so the number and the unit are ruled together, not discovered
    later from a blank column.
    """
    from ELINS import regional_elins as re_

    nulls = [r for r in re_.REGION_PROFILES
             if re_.run_regional_elins(r, "u1")["domain_mapping"]["top"] is None]
    assert len(nulls) == 5, nulls          # ← fails when R-374-B is ruled
    for r in nulls:
        dm = re_.run_regional_elins(r, "u1")["domain_mapping"]
        assert dm["effective_top"] is not None      # the hint still reads
        assert max(dm["scores"].values()) < se.DOMAIN_MIN_SIGNAL


def test_a_hint_still_carries_when_nothing_clears_the_floor():
    """``effective_top`` has always been able to be None, and a caller hint
    is still allowed to stand in when the text names nothing."""
    out = se._layer_2_domains("The novel ends just before the war.", "legal")
    assert out["top"] is None
    assert out["effective_top"] == "legal"


# ==========================================================================
# VERSION STAMPS — forward only, never a backfill.
# ==========================================================================
def test_the_domain_layer_stamps_its_matcher_version():
    with_hint = se._layer_2_domains("The court issued a ruling.", "legal")
    without = se._layer_2_domains("The court issued a ruling.", None)
    assert with_hint["matcher_version"] == se.DOMAIN_MATCHER_VERSION
    assert without["matcher_version"] == se.DOMAIN_MATCHER_VERSION
    # ★ The stamp must DESCRIBE the rule. It is "classed", not
    # "wordboundary": a blanket word boundary is exactly what this is not.
    assert se.DOMAIN_MATCHER_VERSION == "domain.matcher.v2-classed"


def test_every_new_el_ins_record_carries_the_classifier_version():
    rec = ST._validate({
        "operator_id": "op_355", "thread_id": "t355",
        "timestamp": 1.0, "source": "per_turn",
        "result": A.analyze_text("hello", provider_mode="deterministic"),
    })
    assert rec["classifier_version"] == A.CLASSIFIER_VERSION
    assert A.CLASSIFIER_VERSION == "el_ins.classifier.v2-unmapped"


def test_an_older_record_without_a_stamp_is_left_alone():
    """#51 / #90 — the ABSENCE of a stamp is itself the reading
    ("classified under the pre-#355 rule"). Nothing backfills it."""
    old = {
        "operator_id": "op_355", "thread_id": "t355", "timestamp": 1.0,
        "source": "per_turn",
        "result": {"analysis": {"el_score": 0.0, "ins_score": 0.0,
                                "ratio_classification": "balanced"}},
    }
    out = ST._stability_from_rows("t355", [old], 10)
    assert "classifier_version" not in old
    assert out["window"] == 1          # still scored, exactly as before


def test_the_sentinel_is_declared_once():
    """One token, one spelling. A second constant is how two calibrations
    end up in one series."""
    assert ST.el_ins_analyzer.RATIO_UNMAPPED is A.RATIO_UNMAPPED
    assert A.RATIO_UNMAPPED == A.MODE_UNMAPPED == "UNMAPPED"
