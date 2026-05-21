"""
azimuth_reframing.py — Expression Reframing + User Azimuth Check
(Azimuth Mechanic, Track 2).

Given an ExpressionCandidate (local) and an optional CloudAdvisory (from
the cloud, macro-context only), produces 1–3 reframed candidate
expressions that preserve the user's intention while reducing drift
risk. Presents them to the user via an AzimuthCheckPrompt.

ROLE IN THE ARCHITECTURE
------------------------
The Reframing Layer is the final on-device transformation before the
user makes a sending decision. It NEVER auto-sends. It NEVER decides
on behalf of the user. Its only job is to surface "here's how this
will likely land" + "here's a version that preserves intention with
less drift" + "does this still feel like what you mean?"

PHASE STATUS
------------
Phase 1 skeleton — schemas locked in ``azimuth.py``. Function bodies
raise ``NotImplementedError`` pending Phase 3 Unit 6 real implementation.

PUBLIC API
----------
    preserve_intent(candidate, advisory=None)          -> IntentSpec
    reframe_candidate(candidate, intent_spec, …)       -> list[ReframedExpression]
    score_reframing(reframing, candidate)              -> tuple[float, float]
    run_azimuth_check(candidate, reframings)           -> AzimuthCheckPrompt

INTENT INVARIANTS (enforced)
----------------------------
    * preserve_intent must extract a non-empty must_preserve set when
      the candidate carries any non-trivial intention.
    * Every reframing returned by reframe_candidate must have every
      must_preserve token present (case-insensitive substring match).
    * Reframings with preserved_intent_score < 0.7 are rejected.

USER-SOVEREIGNTY INVARIANTS
---------------------------
    * run_azimuth_check NEVER sends, posts, or transmits.
    * The user's choices (ACCEPT / TWEAK / REJECT) are honored verbatim.
    * REJECT always returns the user to the envelope; no state pressure
      to externalize.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from azimuth import (
    AzimuthCheckPrompt,
    CloudAdvisory,
    ExpressionCandidate,
    IntentionClass,
    ReframedExpression,
    UserResponse,  # noqa: F401  — re-exported for surface convenience
)


# ---------------------------------------------------------------------------
# IntentSpec — the must-preserve extraction
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class IntentSpec:
    """Minimal preserved-intent extraction.

    Used by the reframer to guarantee tone modulation doesn't drift the
    underlying intent. Every must_preserve token MUST appear in every
    reframing (case-insensitive substring match).
    """
    intention_class: IntentionClass
    target_action:   str            # what the user is trying to accomplish
    target_state:    str            # what they want to leave the listener with
    must_preserve:   tuple = ()     # key concepts / words / facts that MUST appear


# ---------------------------------------------------------------------------
# preserve_intent
# ---------------------------------------------------------------------------
def preserve_intent(
    candidate: ExpressionCandidate,
    advisory: Optional[CloudAdvisory] = None,
) -> IntentSpec:
    """Extract the must-preserve elements of the user's intent.

    Args:
        candidate: the ExpressionCandidate (local, raw_text accessible).
        advisory:  optional CloudAdvisory carrying macro context.

    Returns:
        IntentSpec.

    Implementation guidance (Phase 3 Unit 6):
        * intention_class comes directly from candidate.intention_class.
        * target_action is derived from imperative verbs in raw_text
          OR the first non-trivial noun phrase after "I want to" /
          "I need to" / "I'd like to".
        * target_state is derived from the candidate's intention_class:
              VENT     → "be heard"
              REQUEST  → "the listener acts on the request"
              APOLOGIZE→ "the listener feels seen + repair offered"
              BOUNDARY → "the listener accepts the limit"
              etc.
        * must_preserve extracts factual / proper-noun / numeric tokens
          that the reframing MUST keep:
              - dates, deadlines, dollar amounts
              - explicit names of artifacts (project names, doc names)
              - decision verbs the user used ("decide", "cancel", "ship")

    INVARIANT: must_preserve is non-empty whenever raw_text contains
    any of: digits, deadline markers, proper nouns, decision verbs.
    """
    raise NotImplementedError(
        "azimuth_reframing.preserve_intent — Phase 3 Unit 6",
    )


# ---------------------------------------------------------------------------
# reframe_candidate
# ---------------------------------------------------------------------------
def reframe_candidate(
    candidate: ExpressionCandidate,
    intent_spec: IntentSpec,
    advisory: Optional[CloudAdvisory] = None,
    *,
    max_candidates: int = 3,
) -> list:
    """Produce 1..max_candidates ReframedExpression options.

    Each option:
        * Preserves intent_spec.target_action and .target_state.
        * Includes every must_preserve token (case-insensitive substring).
        * Reduces drift_risk_after vs. the original candidate.
        * Adapts tone / intensity to audience + context + cloud advisory.

    Tone-modulation rule table (Phase 3 Unit 6):

        | risk_flag present       | audience / context combinator       | action                                              |
        |-------------------------|-------------------------------------|-----------------------------------------------------|
        | "sharp_tone"            | ONE_TO_ONE                          | soften amplifiers; keep stakes language verbatim    |
        | "high_pressure"         | PROFESSIONAL                        | de-escalate urgency markers; demands → asks          |
        | "name_calling"          | any                                 | accusation → observation ("I observed …")           |
        | "absolutist_language"   | any                                 | "never" / "always" → "this week" / "this time"      |
        | "vague_target"          | SMALL_GROUP                         | force one concrete target action                    |
        | "urgency_inflation"     | any                                 | strip ≥2 of the inflated markers                    |
        | "soft_tone"             | HIGH_STAKES                         | re-introduce stakes language                        |
        | "passive_aggressive"    | any                                 | rewrite as direct request                            |
        | "ambiguous_request"     | any                                 | add explicit action verb + when                     |

    Filtering: any candidate failing the intent invariant (missing
    must_preserve tokens) or with preserved_intent_score < 0.7 is
    dropped. If no candidates remain, returns a list with the original
    candidate's text wrapped as a "no change" ReframedExpression — the
    user always has at least one option.

    Returns: list[ReframedExpression], sorted by preserved_intent_score
    descending, then drift_risk_after ascending.
    """
    raise NotImplementedError(
        "azimuth_reframing.reframe_candidate — Phase 3 Unit 6",
    )


# ---------------------------------------------------------------------------
# score_reframing
# ---------------------------------------------------------------------------
def score_reframing(
    reframing: ReframedExpression,
    candidate: ExpressionCandidate,
) -> tuple:
    """Compute (preserved_intent_score, drift_risk_after) for a reframing.

    Args:
        reframing:  the candidate reframing.
        candidate:  the original ExpressionCandidate it was derived from.

    Returns:
        tuple (preserved_intent_score, drift_risk_after), both in [0, 1].

    Scoring rubric (Phase 3 Unit 6):
        * preserved_intent_score:
              1.0 baseline
            − 0.15 per missing must_preserve token
            − 0.10 per missing intention-verb-class match
            − 0.10 if target_state semantic match is missing
            Floor 0.0.

        * drift_risk_after:
              0.0 baseline
            + 0.15 per residual risk_flag re-detected on the reframed text
            + 0.10 if length grew by > 2x the original
            Ceiling 1.0.

    INVARIANT: the returned tuple is order-stable across runs given
    identical inputs (no randomness, no time-dependence).
    """
    raise NotImplementedError(
        "azimuth_reframing.score_reframing — Phase 3 Unit 6",
    )


# ---------------------------------------------------------------------------
# run_azimuth_check
# ---------------------------------------------------------------------------
def run_azimuth_check(
    candidate: ExpressionCandidate,
    reframings: list,
) -> AzimuthCheckPrompt:
    """Build the user-facing Azimuth Check prompt.

    The returned ``AzimuthCheckPrompt`` carries:
        * landing_prediction — short narrative of how the ORIGINAL
          candidate would likely land (e.g., "this will likely read as
          a blanket attack on the team; the deadline concern will be
          lost").
        * reframed_options — tuple of ReframedExpression, ordered by
          score (best first).
        * user_question — always ends with the canonical
          "Does this still feel like what you mean?" line.

    The user can then respond with:
        * ACCEPT  → the surface returns the chosen ReframedExpression.
                    The USER decides whether to send / say it.
        * TWEAK   → the user edits manually; surface loops back through
                    ``reframe_candidate`` with the edited candidate.
        * REJECT  → surface returns the user to the envelope; no
                    externalization occurs.

    INVARIANTS:
        * No network call.
        * No mutation of ``candidate`` or ``reframings``.
        * No auto-send. Ever.
    """
    raise NotImplementedError(
        "azimuth_reframing.run_azimuth_check — Phase 3 Unit 6",
    )
