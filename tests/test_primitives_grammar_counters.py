"""
#135 -- seven grammar counters in primitives_extract.

WHAT THESE PIN. One positive and one negative fixture per counter, the K3
control pair for G1 (the one pattern that was tested both directions
before this landed), and the empty string -> all zeros. These are
heuristics over lexicons; the fixtures are unambiguous on purpose, exactly
as test_primitives_handler.py treats the P-series detectors.
"""
from __future__ import annotations

import primitives_extract as pe

G_KEYS = ("G1", "G2", "G3", "G4", "G5", "G6", "G7")


def _g(text):
    return pe.grammar_counts(text)


# --------------------------------------------------------------------------
# the shape
# --------------------------------------------------------------------------
def test_empty_and_non_string_input_are_all_zeros_with_zero_sentences():
    for bad in ("", "   ", None, 42, []):
        out = _g(bad)
        assert all(out[k] == 0 for k in G_KEYS), bad
        assert out["sentences"] == 0
        assert out["G4_reflexive_only"] is True


def test_the_lexicons_stay_small():
    """The brief caps every declared lexicon at 30 entries: priors on record,
    not a vocabulary that grows until it matches everything."""
    for name in ("_G1_STATIVE", "_NP_START", "_G_BRIDGE", "_G2_PLURAL_AGENTS",
                 "_G2_DECISION_VERBS", "_G3_ABSTRACT_AGENTS", "_G3_VERBS",
                 "_G5_EVALUATIVE", "_G6_OVERLOADED"):
        assert len(getattr(pe, name)) <= 30, name


# --------------------------------------------------------------------------
# G1 -- stative frame. THE K3 CONTROL PAIR.
# --------------------------------------------------------------------------
def test_g1_fires_on_the_k3_control_and_not_on_its_twin():
    assert _g("The system feels unstable.")["G1"] == 1
    assert _g("The system feels the load of 400 users.")["G1"] == 0


def test_g1_a_measure_after_the_verb_is_not_a_state():
    assert _g("The load is 400 users.")["G1"] == 0
    assert _g("The team is exhausted.")["G1"] == 1


# --------------------------------------------------------------------------
# G2 -- fused subject
# --------------------------------------------------------------------------
def test_g2_plural_agent_with_a_decision_verb():
    assert _g("The team decided to ship on Friday.")["G2"] == 1
    assert _g("Maria decided to ship on Friday.")["G2"] == 0


# --------------------------------------------------------------------------
# G3 -- non-local agent
# --------------------------------------------------------------------------
def test_g3_an_abstraction_acting():
    assert _g("The market demands a response.")["G3"] == 1
    assert _g("Ana demands a response.")["G3"] == 0


# --------------------------------------------------------------------------
# G4 -- reflexive self-reference (reflexive only; coreference needs a parser)
# --------------------------------------------------------------------------
def test_g4_reflexive_pronoun():
    assert _g("The team blames itself for the delay.")["G4"] == 1
    assert _g("The team blames the vendor for the delay.")["G4"] == 0


# --------------------------------------------------------------------------
# G5 -- objectless evaluation, a subset of G1
# --------------------------------------------------------------------------
def test_g5_evaluative_complement():
    hit = _g("That is unacceptable.")
    assert hit["G5"] == 1 and hit["G1"] == 1
    miss = _g("The plan is ready.")
    assert miss["G5"] == 0 and miss["G1"] == 1


def test_g5_looks_through_one_bridge_adverb():
    assert _g("This is just ridiculous.")["G5"] == 1


# --------------------------------------------------------------------------
# G6 -- overloaded nouns
# --------------------------------------------------------------------------
def test_g6_lexicon_count():
    assert _g("The culture needs accountability.")["G6"] == 2
    assert _g("The pipeline needs a fix.")["G6"] == 0


# --------------------------------------------------------------------------
# G7 -- operator intent
# --------------------------------------------------------------------------
def test_g7_first_person_intent_about_how_it_lands():
    assert _g("I want this to land well.")["G7"] == 1
    assert _g("I want a sandwich.")["G7"] == 0


# --------------------------------------------------------------------------
# sums per sentence
# --------------------------------------------------------------------------
def test_counts_sum_across_sentences():
    out = _g("That is unacceptable. The system feels unstable.")
    assert out["sentences"] == 2
    assert out["G1"] == 2 and out["G5"] == 1


# --------------------------------------------------------------------------
# the refuter pass -- precision over recall
# --------------------------------------------------------------------------
def test_g3_counts_one_agent_phrase_once():
    assert _g("The competition demands more.")["G3"] == 1


def test_g7_is_about_how_something_lands_not_first_person_doing_the_verb():
    assert _g("I need to read the report.")["G7"] == 0
    assert _g("We should show up.")["G7"] == 0
    assert _g("I want it to read as calm.")["G7"] == 1
    assert _g("I expect the note to land softly.")["G7"] == 1


def test_g1_needs_a_complement():
    assert _g("It is.")["G1"] == 0
    assert _g("The system feels unstable.")["G1"] == 1
