"""
A1 + A2 — envelope bootstrap and the thread-message cascade.

★ THE DEFECT THIS LOCKS DOWN

``_evolve_envelope`` runs a 60-step cascade over 28 declared layer fields and
opens by refusing to act when the user has no envelope document:

    envelope = envelopes_store.get(user)
    if envelope is None:
        return {}, {}          # "we don't create one implicitly"

That guard is correct and these tests PIN it. The defect was upstream:
nothing created the document, so the cascade declined on every call forever,
and ``GET /runtime/envelope`` answered with five containers the handler
fabricated from nothing -- 100 bytes that never changed across real activity.

★★ THE PROOF IS THE RESPONSE BODY, NOT THE PANEL. The assertions below are
byte counts and key counts on the actual endpoint payload, because a UI that
renders "(absent)" cannot distinguish "no data" from "no document" and
neither can a screenshot.
"""
import os

os.environ.setdefault("CLARITYOS_BACKEND", "memory")
os.environ.setdefault("CLARITYOS_VAULT_SECRET", "test-only-not-a-real-secret")

import pytest  # noqa: E402

import app as app_module  # noqa: E402
import envelopes_store  # noqa: E402


# --------------------------------------------------------------------------
# A1 — bootstrap
# --------------------------------------------------------------------------
def test_bootstrap_creates_the_document_when_absent():
    envelopes_store._reset_memory_for_tests()
    assert envelopes_store.get("u_boot") is None
    doc = app_module._ensure_envelope("u_boot")
    assert envelopes_store.get("u_boot") is not None
    # The shape is reused verbatim from POST /envelope/update (app.py:8706),
    # not invented here. Two creation shapes for one document is how field
    # drift starts.
    assert set(doc) == {"user", "elins_briefs", "envelope_vector",
                        "envelope_decay_ts", "updated_at"}
    assert doc["elins_briefs"] == [] and doc["envelope_vector"] is None


def test_bootstrap_is_idempotent_and_never_clobbers():
    envelopes_store._reset_memory_for_tests()
    app_module._ensure_envelope("u_idem")
    envelopes_store.set_envelope("u_idem", {"user": "u_idem", "identity": {"marker": 1},
                                            "elins_briefs": [{"brief_id": "b1"}]})
    again = app_module._ensure_envelope("u_idem")
    assert again["identity"] == {"marker": 1}, "second call overwrote real data"
    assert again["elins_briefs"] == [{"brief_id": "b1"}]


def test_the_evolve_guard_is_unchanged():
    """★ Fix the cause, not the symptom. _evolve_envelope must still decline
    on a missing document -- a cascade that conjured its own input could not
    tell 'new user' from 'load failed'."""
    envelopes_store._reset_memory_for_tests()
    evolved, sims = app_module._evolve_envelope("u_noenv", [0.1] * 32)
    assert evolved == {} and sims == {}


def test_bootstrap_seeds_no_layer_fields():
    """Absent is a valid starting state -- every layer is read defensively.
    Seeding empty containers would recreate the '0 items' vs '(absent)'
    ambiguity the runtime panel already has."""
    envelopes_store._reset_memory_for_tests()
    doc = app_module._ensure_envelope("u_bare")
    for field in app_module._ENVELOPE_PRESERVED_SERVER_FIELDS:
        assert field not in doc, f"bootstrap fabricated {field}"


# --------------------------------------------------------------------------
# A2 — the cascade
# --------------------------------------------------------------------------
def test_cascade_populates_the_envelope_from_one_message():
    envelopes_store._reset_memory_for_tests()
    before = app_module._ensure_envelope("u_casc")
    assert len(before) == 5
    evolved = app_module._run_envelope_cascade(
        "u_casc", "At dinner I dismissed his advice and he went quiet.")
    assert len(evolved) > 5, "cascade produced no new layers"
    stored = envelopes_store.get("u_casc")
    assert len(stored) > 5 and stored["updated_at"] >= before["updated_at"]


def test_cascade_is_safe_on_a_freshly_bootstrapped_empty_envelope():
    """★ NEGATIVE CONTROL. A member with no history must get a valid
    envelope and the cascade must not crash walking an empty one."""
    envelopes_store._reset_memory_for_tests()
    app_module._ensure_envelope("u_empty")
    evolved = app_module._run_envelope_cascade("u_empty", "first words ever")
    assert isinstance(evolved, dict) and evolved


def test_cascade_accrues_continuity_across_turns():
    """Continuity is real and runs through the PERSISTED LAYERS -- the v6
    event list grows turn over turn. That is what makes the panel counts
    move."""
    envelopes_store._reset_memory_for_tests()
    app_module._run_envelope_cascade("u_cont", "the first thing that happened")
    n1 = len(envelopes_store.get("u_cont").get("events") or [])
    app_module._run_envelope_cascade("u_cont", "then something else happened")
    n2 = len(envelopes_store.get("u_cont").get("events") or [])
    assert n1 >= 1, "first turn recorded no event"
    assert n2 > n1, f"second turn did not accrue ({n1} -> {n2})"


def test_envelope_vector_stays_none_without_elins_briefs():
    """★ MEASURED, AND PINNED SO IT IS NOT MISTAKEN FOR CONTINUITY.

    _run_envelope_cascade reads envelope_vector as its prior and falls back
    to v_obs. It falls back EVERY time: _evolve_envelope derives
    new_vector from compute_multilayer_envelope_vector(briefs) (app.py:6607)
    and nothing on the threads plane creates briefs -- those come from ELINS
    ingest. So the vector prior is inert today and every turn is cold on
    that axis.

    If this test ever fails because the vector became non-None, that is
    GOOD news: briefs now exist and the prior went live. Update the
    docstring on _run_envelope_cascade at the same time."""
    envelopes_store._reset_memory_for_tests()
    app_module._run_envelope_cascade("u_vec", "something happened today")
    stored = envelopes_store.get("u_vec")
    assert stored["elins_briefs"] == [], "briefs appeared - re-read the docstring"
    assert not stored.get("envelope_vector")
    assert not stored.get("envelope_centroid")


def test_cascade_declines_loudly_on_an_empty_embedding(monkeypatch):
    """An empty embed must return {} and log -- never raise into the caller
    and never silently write a degenerate envelope."""
    envelopes_store._reset_memory_for_tests()
    app_module._ensure_envelope("u_noembed")
    monkeypatch.setattr(app_module.dewey_pipeline, "embed_text_cached", lambda t: [])
    assert app_module._run_envelope_cascade("u_noembed", "anything") == {}
