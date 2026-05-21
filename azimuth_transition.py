"""
azimuth_transition.py — Transition Layer + Cloud Metadata Handoff
(Azimuth Mechanic, Track 1).

Detects when the user is moving from "just reflecting" to "I want to say
this," builds the ExpressionCandidate, evaluates drift-risk flags, and
produces the CloudMetadata that crosses the device → cloud boundary.

ROLE IN THE ARCHITECTURE
------------------------
The Transition Layer is the second-innermost privacy boundary. It can
read the full EnvelopeState (same device) and produce a richer
ExpressionCandidate that still stays local. The only thing this layer
emits across the device boundary is a CloudMetadata structure — which
by construction carries no raw text, no identifiers, no verbatim
phrases.

PHASE STATUS
------------
Phase 1 skeleton — schemas locked in ``azimuth.py``. Function bodies
raise ``NotImplementedError`` pending Phase 3 Unit 5 real implementation.

PUBLIC API
----------
    detect_externalization_intent(env, history=()) -> bool
    build_candidate(env, *, audience, context, …)  -> ExpressionCandidate
    evaluate_drift_risk(candidate)                 -> tuple[str, ...]
    build_cloud_metadata(candidate)                -> CloudMetadata

PRIVACY GUARANTEE
-----------------
``build_cloud_metadata`` is the ONLY function in the entire Azimuth
Mechanic that produces an upload-safe object. Its output (CloudMetadata)
is structurally guaranteed (see azimuth.py § structural privacy guards)
to omit raw_text, identifiers, names, and verbatim phrases.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from azimuth import (
    AudienceType,
    CloudMetadata,
    ContextType,
    EnvelopeState,
    ExpressionCandidate,
    IntensityLevel,
    IntentionClass,
    PressureLevel,
    PressureShape,
    PressureSlope,
    RISK_FLAGS_CANONICAL,
    UrgencyLevel,
    Valence,
)

# Phase 3 Unit 5 — live Azimuth → FEA → Integration path imports.
from emotional_alignment_engine import align_expression
from emotional_alignment_schemas import (
    EmotionalGeometry,
    EmotionalIntention,
    EmotionalSnapshot,
    MeaningNeed,
    RegulationGoal,
    RelationalPosture,
)
from ambient_trust_engine import (
    assess_trust_state,
    verify_comprehension_leads_action,
    verify_no_hard_stops,
)
from ambient_trust_schemas import SessionContext
from fea_integration_engine import integrate_alignment
from fea_integration_schemas import IntegratedAlignmentResult
from language_schemas import ExpressionPrimitive
from orchestrator_schemas import (
    ActorKind,
    AuthorizationTier,
    DriftAxis,
    DriftState,
    GeometryProfile,
    IdentityProfile,
    PropagationState,
    SovereigntyLevel,
)


# ---------------------------------------------------------------------------
# detect_externalization_intent
# ---------------------------------------------------------------------------
def detect_externalization_intent(
    env: EnvelopeState,
    recent_history: tuple = (),
) -> bool:
    """Return True if the user has signaled / is signaling externalization intent.

    Phase 3 Unit 9 implementation. The entry trigger for the entire
    Azimuth → Alignment → Risk → Cloud pipeline.

    Triggers (any is sufficient):

    Trigger 1 — Explicit user signal
        ``env.user_marked_externalize == True`` → True.

    Trigger 2 — Canonical externalization markers in raw_text
        Word-bounded, case-insensitive scan of ``env.raw_text`` for any
        of the locked phrases in ``_EXTERNALIZATION_MARKERS``. Matches
        require word boundaries on both sides — "should i send" matches
        "should I send the email" but not "should I sender" or
        "should I sending".

    Trigger 3 — Topic recurrence within 30 minutes
        ``recent_history`` contains 3+ envelopes that:
            * are within 30 minutes of ``env.captured_at`` (|delta| ≤ 1800 s), AND
            * have ``rough_intention`` with Jaccard similarity ≥ 0.5
              against ``env.rough_intention``.
        Tokenization: lowercase + split on non-alphanumerics, drop
        empty tokens. Jaccard = |intersection| / |union|. Both empty
        token sets → similarity 0.0.

    Args:
        env:             current envelope.
        recent_history:  iterable of prior EnvelopeStates (order
                         independent — the function does not assume
                         any sort order). May be empty.

    Returns:
        bool. ``True`` if any trigger fires; ``False`` otherwise.

    Raises:
        ValueError if ``env`` is not an EnvelopeState.
        ValueError if any element of ``recent_history`` is not an
            EnvelopeState.

    INVARIANTS:
        * Pure: no I/O, no LLM, no network, no randomness.
        * Deterministic: same inputs → same output.
        * Non-mutating: never touches ``env`` or ``recent_history``.
    """
    if not isinstance(env, EnvelopeState):
        raise ValueError(
            f"detect_externalization_intent expected EnvelopeState for "
            f"env, got {type(env).__name__}"
        )
    for i, e in enumerate(recent_history):
        if not isinstance(e, EnvelopeState):
            raise ValueError(
                f"detect_externalization_intent: recent_history[{i}] is "
                f"not an EnvelopeState (got {type(e).__name__})"
            )

    # Trigger 1 — explicit user flag.
    if env.user_marked_externalize:
        return True

    # Trigger 2 — canonical lexical markers (word-bounded).
    if _EXTERNALIZATION_MARKER_REGEX.search(env.raw_text):
        return True

    # Trigger 3 — topic recurrence within 30 minutes.
    if _topic_recurrence_fires(env, recent_history):
        return True

    return False


# ---------------------------------------------------------------------------
# Phase 3 Unit 9 helpers — locked tokens + lexical / time / Jaccard math
# ---------------------------------------------------------------------------

# Locked canonical externalization markers. Each phrase is matched with
# word boundaries on both sides so substring drift (e.g., "send" inside
# "sender") cannot trip the trigger.
_EXTERNALIZATION_MARKERS: tuple = (
    "i want to tell them",
    "should i send",
    "should i say",
    "do i send",
    "do i say",
    "is it okay to tell",
    "should i message",
    "should i text",
)

# Precompiled word-boundary regex covering all canonical markers. The
# leading and trailing \b stop substring drift in either direction.
_EXTERNALIZATION_MARKER_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(m) for m in _EXTERNALIZATION_MARKERS) + r")\b",
    re.IGNORECASE,
)

# Trigger-3 constants.
_TOPIC_RECURRENCE_WINDOW_SECONDS: int = 30 * 60   # 30 minutes
_TOPIC_RECURRENCE_THRESHOLD_COUNT: int = 3
_TOPIC_SIMILARITY_THRESHOLD: float = 0.5

# Tokenizer: lowercase, split on non-alphanumerics, drop empty tokens.
_TOKEN_SPLIT_RE = re.compile(r"[^a-zA-Z0-9]+")


def _tokenize_intention(intention: str) -> frozenset:
    """Pure. Lowercase + split on non-alphanumerics + drop empty tokens."""
    return frozenset(
        t for t in _TOKEN_SPLIT_RE.split(intention.lower()) if t
    )


def _jaccard_similarity(a: str, b: str) -> float:
    """Pure. Jaccard similarity between the token sets of two intention
    strings. Returns 0.0 when both token sets are empty (no information
    is no match)."""
    sa = _tokenize_intention(a)
    sb = _tokenize_intention(b)
    union = sa | sb
    if not union:
        return 0.0
    return len(sa & sb) / len(union)


def _within_recurrence_window(env: EnvelopeState, e: EnvelopeState) -> bool:
    """True iff ``e.captured_at`` is within the recurrence window of
    ``env.captured_at``. Uses absolute delta, so order doesn't matter."""
    delta = abs((env.captured_at - e.captured_at).total_seconds())
    return delta <= _TOPIC_RECURRENCE_WINDOW_SECONDS


def _topic_recurrence_fires(
    env: EnvelopeState,
    recent_history: tuple,
) -> bool:
    """Trigger 3 evaluator. Counts envelopes in ``recent_history`` that
    are both (a) within the time window and (b) topically similar
    (Jaccard ≥ threshold). Fires when count ≥ threshold."""
    matching = 0
    for e in recent_history:
        if not _within_recurrence_window(env, e):
            continue
        if _jaccard_similarity(env.rough_intention, e.rough_intention) \
                >= _TOPIC_SIMILARITY_THRESHOLD:
            matching += 1
            if matching >= _TOPIC_RECURRENCE_THRESHOLD_COUNT:
                return True
    return False


# ---------------------------------------------------------------------------
# build_candidate
# ---------------------------------------------------------------------------
def build_candidate(
    env: EnvelopeState,
    *,
    audience: AudienceType,
    context: ContextType,
    pressure_slope: PressureSlope = PressureSlope.FLAT,
    urgency:        UrgencyLevel  = UrgencyLevel.LOW,
    intention_class: Optional[IntentionClass] = None,
) -> ExpressionCandidate:
    """Build an ExpressionCandidate from an envelope and contextual hints.

    Phase 3 Unit 6 implementation. Delegates into the Unit-5 alignment
    loop (`compute_aligned_expression`) and embeds the resulting
    IntegratedAlignmentResult on the candidate's ``aligned`` field.

    The candidate stays LOCAL. Only the CloudMetadata derived via
    ``build_cloud_metadata`` may cross the device boundary.

    Args:
        env:              the source envelope (raw_text preserved).
        audience:         who the expression is aimed at.
        context:          context category.
        pressure_slope:   trajectory of pressure across recent history
                          (defaults FLAT — caller can pre-compute from
                          history if needed).
        urgency:          how time-critical the expression is.
        intention_class:  explicit override; if omitted, derived from
                          ``env.rough_intention`` + ``env.raw_text``
                          via ``_derive_intention_class``.

    Returns:
        ExpressionCandidate with:
            * raw_text / intention / pressure_level / envelope_id
              copied from env
            * intention_class derived (or honored if explicit)
            * audience / context / pressure_slope / urgency from args
            * risk_flags = () — evaluate_drift_risk is still a stub
            * candidate_id auto-generated
            * aligned = compute_aligned_expression(env)

    Raises:
        ValueError if `env` is not an EnvelopeState.

    Default intention_class derivation rule table (per priority order):
        "vent"                     → IntentionClass.VENT
        "apologize" / "i'm sorry"  → IntentionClass.APOLOGIZE
        "request" / "need" / "ask" → IntentionClass.REQUEST
        "boundary" / "limit" / "no" (word-bounded) → IntentionClass.BOUNDARY
        "observe" / "noticed"      → IntentionClass.OBSERVATION
        "thanks" / "appreciate"    → IntentionClass.GRATITUDE
        else                       → IntentionClass.OTHER
    """
    if not isinstance(env, EnvelopeState):
        raise ValueError(
            f"build_candidate expected EnvelopeState, "
            f"got {type(env).__name__}"
        )

    if intention_class is None:
        intention_class = _derive_intention_class(env)

    aligned_result = compute_aligned_expression(env)

    return ExpressionCandidate(
        raw_text=env.raw_text,
        intention=env.rough_intention,
        intention_class=intention_class,
        pressure_level=env.pressure_level,
        pressure_slope=pressure_slope,
        audience=audience,
        context=context,
        urgency=urgency,
        risk_flags=(),
        envelope_id=env.envelope_id,
        aligned=aligned_result,
    )


# ---------------------------------------------------------------------------
# evaluate_drift_risk — Phase 3 Unit 7 implementation
# ---------------------------------------------------------------------------
# Locked lexical token sets for the documented rule table.

_NAME_CALLING_TOKENS: tuple = ("you always", "you never")
_ABSOLUTIST_TEXT_TOKENS: tuple = (
    "all", "none", "everyone", "no one", "nobody", "always",
    "never", "everything", "nothing",
)
_PASSIVE_AGGRESSIVE_TOKENS: tuple = ("fine", "whatever")
_URGENCY_MARKERS: tuple = (
    "now", "asap", "urgent", "immediately", "right now",
    "today", "deadline",
)
# Small action-verb dictionary for "no action verb" detection in
# REQUEST envelopes. Substring matches accept inflections (e.g.,
# "send"/"sending"/"sends").
_ACTION_VERBS: tuple = (
    "do", "send", "make", "give", "tell", "ask", "help", "fix",
    "schedule", "create", "build", "review", "consider",
    "set up", "set-up", "set", "share", "approve", "confirm",
    "decide", "answer", "respond", "reply", "follow up",
    "remove", "add", "update", "submit", "ship", "deliver",
    "write", "draft", "call", "email", "meet",
)

# Pressure / context / audience / intensity sets used by the rules.
_HIGH_PRESSURE_LEVELS = frozenset({PressureLevel.HIGH, PressureLevel.CRITICAL})

# Word-boundary regex for short tokens that would false-positive on
# substring (e.g., "all" inside "tall"/"call"/"shall"). Built once at
# import time so we don't pay the cost per call.
_ABSOLUTIST_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _ABSOLUTIST_TEXT_TOKENS) + r")\b",
    re.IGNORECASE,
)
_PASSIVE_AGGRESSIVE_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _PASSIVE_AGGRESSIVE_TOKENS) + r")\b",
    re.IGNORECASE,
)
_URGENCY_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _URGENCY_MARKERS) + r")\b",
    re.IGNORECASE,
)


def _count_word_boundary(text: str, regex) -> int:
    """Count whole-word matches via a precompiled regex."""
    return len(regex.findall(text))


def _has_action_verb(text: str) -> bool:
    """Substring scan for any action verb in raw_text (case-insensitive)."""
    lowered = text.lower()
    for verb in _ACTION_VERBS:
        if verb in lowered:
            return True
    return False


def _intention_word_count(intention: str) -> int:
    """Count whitespace-delimited words in a rough_intention string."""
    return len(intention.split())


def evaluate_drift_risk(
    env: EnvelopeState,
    *,
    candidate: ExpressionCandidate,
) -> ExpressionCandidate:
    """Identify drift-risk flags and return a new ExpressionCandidate with
    ``risk_flags`` populated. Pure, deterministic, side-effect-free.

    Phase 3 Unit 7 implementation. The signature is updated from the
    Phase-1 stub (``candidate -> tuple``) to ``(env, *, candidate) ->
    ExpressionCandidate``: three of the documented rules need fields
    that live only on the EnvelopeState (``emotional_intensity``,
    ``valence``), and the work-set's caller pattern is
    ``candidate = evaluate_drift_risk(env, candidate=candidate)``.

    All flags come from ``RISK_FLAGS_CANONICAL`` in azimuth.py. The
    output ``risk_flags`` tuple is **sorted** so the same rule set
    always produces byte-equal output regardless of evaluation order.

    Rule table:

        | Condition                                                    | Flag                                   |
        |--------------------------------------------------------------|----------------------------------------|
        | intensity ∈ {HIGH, EXTREME} ∧ audience ≠ SELF                | "sharp_tone"                           |
        | pressure ∈ {HIGH, CRITICAL} ∧ context ∈ {PRO, HIGH_STAKES}   | "high_pressure"                        |
        | rough_intention empty/one-word ∧ audience ∈ {GROUP, PUBLIC}  | "vague_target"                         |
        | raw_text contains "you always" / "you never"                 | "name_calling" + "absolutist_language" |
        | urgency markers ≥ 3 but candidate.urgency < HIGH             | "urgency_inflation"                    |
        | intention_class = REQUEST ∧ no action verb in raw_text       | "ambiguous_request"                    |
        | context = HIGH_STAKES ∧ intensity = LOW                      | "soft_tone"                            |
        | raw_text contains "fine" / "whatever" + negative valence     | "passive_aggressive"                   |
        | raw_text contains absolutist tokens                          | "absolutist_language"                  |
        |   (all/none/everyone/no one/nobody/always/never/             |                                        |
        |    everything/nothing — word-boundary matched)               |                                        |
        | candidate.aligned.halt_level == SurfaceHaltLevel.HARD        | "hard_halt"  (Phase 3 Unit 7)          |
        | candidate.aligned.halt_level == SurfaceHaltLevel.SOFT        | "soft_halt"  (Phase 3 Unit 7)          |

    Alignment-aware rules fire only when ``candidate.aligned`` is set.
    If ``candidate.aligned is None`` (no alignment data available), the
    two halt-derived flags are skipped silently.

    Args:
        env:       EnvelopeState. Source of ``emotional_intensity`` and
                   ``valence``, plus ``raw_text`` / ``rough_intention``
                   (read from env, not from candidate, to keep the
                   evaluation tied to the actual envelope state).
        candidate: ExpressionCandidate. Source of audience / context /
                   intention_class / urgency / pressure_level /
                   aligned.

    Returns:
        A new ExpressionCandidate identical to ``candidate`` except
        ``risk_flags`` is the sorted, deduplicated tuple of canonical
        flag names triggered by the rule table.

    Raises:
        ValueError if ``env`` is not an EnvelopeState.
        ValueError if ``candidate`` is not an ExpressionCandidate.
    """
    if not isinstance(env, EnvelopeState):
        raise ValueError(
            f"evaluate_drift_risk expected EnvelopeState for env, "
            f"got {type(env).__name__}"
        )
    if not isinstance(candidate, ExpressionCandidate):
        raise ValueError(
            f"evaluate_drift_risk expected ExpressionCandidate for "
            f"candidate, got {type(candidate).__name__}"
        )

    flags: set = set()

    # Rule 1: sharp_tone — intensity ∈ {HIGH, EXTREME} ∧ audience ≠ SELF
    high_intensity = env.emotional_intensity in (
        IntensityLevel.HIGH, IntensityLevel.EXTREME,
    )
    if high_intensity and candidate.audience != AudienceType.SELF:
        flags.add("sharp_tone")

    # Rule 2: high_pressure — pressure ∈ {HIGH, CRITICAL} ∧ context ∈ {PRO, HIGH_STAKES}
    if (env.pressure_level in _HIGH_PRESSURE_LEVELS
            and candidate.context in (
                ContextType.PROFESSIONAL, ContextType.HIGH_STAKES,
            )):
        flags.add("high_pressure")

    # Rule 3: vague_target — rough_intention empty/one-word ∧ audience ∈ {GROUP, PUBLIC}
    if (_intention_word_count(env.rough_intention) <= 1
            and candidate.audience in (
                AudienceType.SMALL_GROUP, AudienceType.PUBLIC,
            )):
        flags.add("vague_target")

    # Rule 4: name_calling + absolutist_language — "you always" / "you never"
    lowered_raw = env.raw_text.lower()
    if any(token in lowered_raw for token in _NAME_CALLING_TOKENS):
        flags.add("name_calling")
        flags.add("absolutist_language")

    # Rule 5: urgency_inflation — ≥ 3 urgency markers but candidate.urgency < HIGH
    if (_count_word_boundary(env.raw_text, _URGENCY_REGEX) >= 3
            and candidate.urgency != UrgencyLevel.HIGH):
        flags.add("urgency_inflation")

    # Rule 6: ambiguous_request — REQUEST class ∧ no action verb in raw_text
    if (candidate.intention_class == IntentionClass.REQUEST
            and not _has_action_verb(env.raw_text)):
        flags.add("ambiguous_request")

    # Rule 7: soft_tone — context = HIGH_STAKES ∧ intensity = LOW
    if (candidate.context == ContextType.HIGH_STAKES
            and env.emotional_intensity == IntensityLevel.LOW):
        flags.add("soft_tone")

    # Rule 8: passive_aggressive — "fine"/"whatever" + negative valence
    has_pa_token = bool(_PASSIVE_AGGRESSIVE_REGEX.search(env.raw_text))
    if has_pa_token and env.valence == Valence.NEGATIVE:
        flags.add("passive_aggressive")

    # Rule 9: absolutist_language — absolutist tokens (word-boundary matched).
    # This rule fires regardless of the name_calling combination above
    # so absolutist_language is set whenever ANY absolutist token is
    # present; deduplication is handled by the set.
    if _ABSOLUTIST_REGEX.search(env.raw_text):
        flags.add("absolutist_language")
        # all_or_nothing fires from the same condition (the docstring's
        # original rule 9 listed "all_or_nothing" for this trigger).
        flags.add("all_or_nothing")

    # Rule 10 / 11: alignment-aware flags (Phase 3 Unit 7).
    if candidate.aligned is not None:
        halt_level = candidate.aligned.halt_level
        # Import locally to avoid a top-level circular reference. We
        # already import from fea_integration_schemas at module load,
        # so this is just a name binding inside the function.
        from fea_integration_schemas import SurfaceHaltLevel
        if halt_level == SurfaceHaltLevel.HARD:
            flags.add("hard_halt")
        elif halt_level == SurfaceHaltLevel.SOFT:
            flags.add("soft_halt")

    sorted_flags = tuple(sorted(flags))

    # dataclasses.replace yields a new instance — never mutates input.
    from dataclasses import replace as _replace
    return _replace(candidate, risk_flags=sorted_flags)


# ---------------------------------------------------------------------------
# build_cloud_metadata — the privacy-boundary crossing point
# ---------------------------------------------------------------------------
def build_cloud_metadata(candidate: ExpressionCandidate) -> CloudMetadata:
    """Derive the structural fingerprint that crosses device → cloud.

    Phase 3 Unit 8 implementation. Pure, deterministic, side-effect-free.
    The returned CloudMetadata is the only Azimuth Mechanic artifact
    that may cross the device → cloud boundary.

    PRIVACY GUARANTEE (structurally enforced — see azimuth.py):
        The returned CloudMetadata carries:
            * pressure_shape, pressure_slope, pressure_level
            * audience_type, context_type, urgency_level
            * intention_class
            * risk_flags (canonical names only)
            * schema_version
        And NOTHING else. In particular: NO raw_text, NO envelope_id,
        NO candidate_id, NO intention (free-text), NO names.

    Rule table (locked):
        pressure_shape derivation from (pressure_level, pressure_slope):
              SPIKE      ← (HIGH/CRITICAL, RISING)
              ASCENDING  ← (any, RISING) and not SPIKE
              DESCENDING ← (any, FALLING)
              PLATEAU    ← (any, FLAT)
        risk_flags passes through unchanged (already canonical lowercase
            names from RISK_FLAGS_CANONICAL).
        schema_version uses the CloudMetadata default ("azimuth.v1").

    Args:
        candidate: ExpressionCandidate built by build_candidate and
                   (optionally) risk-flagged by evaluate_drift_risk.

    Returns:
        CloudMetadata with exactly the nine documented fields.

    Raises:
        ValueError if candidate is not an ExpressionCandidate.
        ValueError if any of candidate's enum fields are not from the
            canonical set (defensive sanity check before upload — a
            string-typed override would otherwise leak into the cloud
            payload).
    """
    if not isinstance(candidate, ExpressionCandidate):
        raise ValueError(
            f"build_cloud_metadata expected ExpressionCandidate, "
            f"got {type(candidate).__name__}"
        )

    # Defensive canonical-enum sanity checks. ExpressionCandidate's type
    # hints don't enforce membership at runtime — a caller could pass a
    # string. Reject before the value crosses the cloud boundary.
    if not isinstance(candidate.pressure_level, PressureLevel):
        raise ValueError(
            f"non-canonical pressure_level: {candidate.pressure_level!r}"
        )
    if not isinstance(candidate.pressure_slope, PressureSlope):
        raise ValueError(
            f"non-canonical pressure_slope: {candidate.pressure_slope!r}"
        )
    if not isinstance(candidate.audience, AudienceType):
        raise ValueError(
            f"non-canonical audience: {candidate.audience!r}"
        )
    if not isinstance(candidate.context, ContextType):
        raise ValueError(
            f"non-canonical context: {candidate.context!r}"
        )
    if not isinstance(candidate.urgency, UrgencyLevel):
        raise ValueError(
            f"non-canonical urgency: {candidate.urgency!r}"
        )
    if not isinstance(candidate.intention_class, IntentionClass):
        raise ValueError(
            f"non-canonical intention_class: {candidate.intention_class!r}"
        )

    pressure_shape = _derive_pressure_shape(
        candidate.pressure_level, candidate.pressure_slope,
    )

    # risk_flags passthrough — already lowercase canonical names from
    # RISK_FLAGS_CANONICAL (asserted by evaluate_drift_risk's tests).
    return CloudMetadata(
        pressure_shape=pressure_shape,
        pressure_slope=candidate.pressure_slope,
        pressure_level=candidate.pressure_level,
        audience_type=candidate.audience,
        context_type=candidate.context,
        urgency_level=candidate.urgency,
        intention_class=candidate.intention_class,
        risk_flags=tuple(candidate.risk_flags),
        # schema_version uses the default declared on CloudMetadata.
    )


def _derive_pressure_shape(
    level: PressureLevel,
    slope: PressureSlope,
) -> PressureShape:
    """Pure function. Derive PressureShape from (level, slope) per the
    locked rule table in build_cloud_metadata's docstring.

    Order matters: SPIKE check first (overrides ASCENDING for HIGH/
    CRITICAL + RISING).

        SPIKE      ← (HIGH/CRITICAL, RISING)
        ASCENDING  ← (any, RISING) and not SPIKE
        DESCENDING ← (any, FALLING)
        PLATEAU    ← (any, FLAT)
    """
    if slope == PressureSlope.RISING:
        if level in (PressureLevel.HIGH, PressureLevel.CRITICAL):
            return PressureShape.SPIKE
        return PressureShape.ASCENDING
    if slope == PressureSlope.FALLING:
        return PressureShape.DESCENDING
    # PressureSlope.FLAT — the only remaining canonical value.
    return PressureShape.PLATEAU


# ===========================================================================
# Phase 3 Unit 5 — Azimuth → FEA → Integration live path
# ===========================================================================
#
# Implements the deterministic mapping from EnvelopeState into the three FEA
# input types (EmotionalSnapshot, EmotionalGeometry, EmotionalIntention) and
# wires the resulting AlignedExpression through fea_integration_engine.
# integrate_alignment, producing an IntegratedAlignmentResult.
#
# All logic in this section is:
#     * pure (no I/O, no LLM, no randomness, no network),
#     * deterministic (same inputs → byte-equal output),
#     * structural (no raw user text propagated into output fields).
#
# The existing four public stubs above (detect_externalization_intent,
# build_candidate, evaluate_drift_risk, build_cloud_metadata) are not
# touched — their contracts are unchanged.
# ===========================================================================


# Locked lexical token sets — change here affects deterministic behavior.

_TEMPORAL_RECURRENCE_MARKERS: tuple = (
    "always", "every time", "keeps", "again",
)

_MEMORY_ANCHOR_MARKERS: tuple = (
    "remember when", "last time", "since", "ever since",
)

_ABSOLUTIST_TOKENS: tuple = (
    "always", "never", "everyone", "nobody",
    "everything", "nothing",
)

_ACCUSATORY_MARKERS: tuple = (
    "you always", "you never", "your fault", "you ruined",
)

_CONCILIATORY_INTENT_MARKERS: tuple = (
    "apologize", "sorry", "make peace", "calm",
)

_SELF_ATTACK_TOKENS: tuple = (
    "i'm stupid", "i'm worthless", "i'm a failure", "i'm broken",
    "my fault", "i ruined", "i always mess", "i can't do anything",
)

_OTHER_ATTACK_TOKENS: tuple = (
    "you always", "you never", "your fault", "you ruined",
    "you don't care", "you made me",
)

_WORLD_HOSTILE_TOKENS: tuple = (
    "nobody cares", "no one cares", "everyone's against",
    "the world", "everything is broken", "everything's broken",
)

_BOUNDARY_INTENT_TOKENS: tuple = (
    "limit", "boundary", "won't", "no more", "stop", "enough",
)

_CONTAIN_INTENT_TOKENS: tuple = ("contain", "hold", "keep in", "swallow")
_EXPRESS_INTENT_TOKENS: tuple = ("say", "tell", "express", "let out", "speak")
_TRANSFORM_INTENT_TOKENS: tuple = ("change", "transform", "shift", "process")

_SUBMIT_TEXT_MARKERS: tuple = (
    "i shouldn't", "i have to", "i can't say no", "i give up",
    "i'm sorry", "i deserve",
)
_SEPARATE_TEXT_MARKERS: tuple = (
    "i need space", "step back", "distance", "get away",
)
_DEFEND_TEXT_MARKERS: tuple = (
    "your fault", "you started", "you always", "you don't",
)

_CLARIFY_MEANING_MARKERS: tuple = (
    "what does it mean", "i don't understand", "why is",
)
_VALIDATE_MEANING_MARKERS: tuple = (
    "am i right", "is it okay", "validate", "am i wrong", "tell me i",
)
_REFRAME_MEANING_MARKERS: tuple = (
    "reframe", "different way", "look at this differently",
    "another perspective",
)

# Float-stance scaling: count / DENOM, clipped to [0.0, 1.0].
_STANCE_DENOM: float = 3.0

# Locked default for v1. Future versions may derive primitive per-envelope.
_DEFAULT_PRIMITIVE: ExpressionPrimitive = ExpressionPrimitive.GEOMETRY

# Locked target_state max length (canonicalised rough_intention).
_TARGET_STATE_MAX_LEN: int = 80


# ---------------------------------------------------------------------------
# Lexical helpers — pure, deterministic
# ---------------------------------------------------------------------------
def _has_any_marker(text: str, markers: tuple) -> bool:
    """Case-insensitive substring match against any marker."""
    lowered = text.lower()
    for m in markers:
        if m in lowered:
            return True
    return False


def _count_markers(text: str, markers: tuple) -> int:
    """Case-insensitive count of total occurrences across all markers."""
    lowered = text.lower()
    total = 0
    for m in markers:
        if m:
            total += lowered.count(m)
    return total


def _stance_ratio(count: int) -> float:
    """Convert a token count into a stance float in [0.0, 1.0]."""
    if count <= 0:
        return 0.0
    ratio = count / _STANCE_DENOM
    if ratio >= 1.0:
        return 1.0
    return round(ratio, 4)


# ---------------------------------------------------------------------------
# Snapshot mapping
# ---------------------------------------------------------------------------
def _map_envelope_to_snapshot(env: EnvelopeState) -> EmotionalSnapshot:
    """Deterministic. Maps EnvelopeState fields + lexical scans of raw_text
    into an EmotionalSnapshot.

    Direct passthroughs:
        pressure_level ← env.pressure_level
        intensity      ← env.emotional_intensity
        valence        ← env.valence

    Lexical derivations:
        temporal_linked ← raw_text contains any of
                          {"always", "every time", "keeps", "again"}
        anchor_present  ← raw_text contains any of
                          {"remember when", "last time", "since",
                           "ever since"}
    """
    return EmotionalSnapshot(
        pressure_level=env.pressure_level,
        intensity=env.emotional_intensity,
        valence=env.valence,
        temporal_linked=_has_any_marker(env.raw_text, _TEMPORAL_RECURRENCE_MARKERS),
        anchor_present=_has_any_marker(env.raw_text, _MEMORY_ANCHOR_MARKERS),
    )


# ---------------------------------------------------------------------------
# Geometry mapping
# ---------------------------------------------------------------------------
def _map_envelope_to_geometry(env: EnvelopeState) -> EmotionalGeometry:
    """Deterministic lexical analysis of EnvelopeState → EmotionalGeometry.

    Rules:
        curvature         ← raw_text has any absolutist token
        torsion           ← rough_intention has any conciliatory marker
                            AND raw_text has any accusatory marker
        shear             ← raw_text has any self-attack token
        boundary          ← rough_intention has any boundary-intent token
        stance_self       ← clipped count of self-attack tokens / 3
        stance_other      ← clipped count of other-attack tokens / 3
        stance_world      ← clipped count of world-hostile tokens / 3
        pressure_gradient ← 0.0 (no history available in v1)
    """
    conciliatory = _has_any_marker(env.rough_intention, _CONCILIATORY_INTENT_MARKERS)
    accusatory   = _has_any_marker(env.raw_text, _ACCUSATORY_MARKERS)

    return EmotionalGeometry(
        curvature=_has_any_marker(env.raw_text, _ABSOLUTIST_TOKENS),
        torsion=(conciliatory and accusatory),
        shear=_has_any_marker(env.raw_text, _SELF_ATTACK_TOKENS),
        boundary=_has_any_marker(env.rough_intention, _BOUNDARY_INTENT_TOKENS),
        stance_self=_stance_ratio(
            _count_markers(env.raw_text, _SELF_ATTACK_TOKENS)
        ),
        stance_other=_stance_ratio(
            _count_markers(env.raw_text, _OTHER_ATTACK_TOKENS)
        ),
        stance_world=_stance_ratio(
            _count_markers(env.raw_text, _WORLD_HOSTILE_TOKENS)
        ),
        pressure_gradient=0.0,
    )


# ---------------------------------------------------------------------------
# Intention mapping
# ---------------------------------------------------------------------------
def _canonicalise_target_state(rough_intention: str) -> str:
    """Strip + truncate rough_intention into a short canonical label."""
    stripped = rough_intention.strip()
    if len(stripped) <= _TARGET_STATE_MAX_LEN:
        return stripped
    return stripped[:_TARGET_STATE_MAX_LEN]


def _derive_regulatory_goal(env: EnvelopeState) -> RegulationGoal:
    """Lexical derivation. Falls through to EXPRESS by default.

    Order matters — first match wins:
        contain markers   → CONTAIN
        transform markers → TRANSFORM
        else              → EXPRESS (default; also covers "say"/"tell"/...)
    """
    ri = env.rough_intention.lower()
    for tok in _CONTAIN_INTENT_TOKENS:
        if tok in ri:
            return RegulationGoal.CONTAIN
    for tok in _TRANSFORM_INTENT_TOKENS:
        if tok in ri:
            return RegulationGoal.TRANSFORM
    return RegulationGoal.EXPRESS


def _derive_relational_posture(env: EnvelopeState) -> RelationalPosture:
    """Lexical derivation. Falls through to CONNECT by default.

    Order matters:
        submit markers   → SUBMIT
        defend markers   → DEFEND
        separate markers → SEPARATE
        else             → CONNECT
    """
    rt = env.raw_text.lower()
    if _has_any_marker(rt, _SUBMIT_TEXT_MARKERS):
        return RelationalPosture.SUBMIT
    if _has_any_marker(rt, _DEFEND_TEXT_MARKERS):
        return RelationalPosture.DEFEND
    if _has_any_marker(rt, _SEPARATE_TEXT_MARKERS):
        return RelationalPosture.SEPARATE
    return RelationalPosture.CONNECT


def _derive_meaning_need(env: EnvelopeState) -> MeaningNeed:
    """Lexical derivation. Falls through to NONE by default."""
    rt = env.raw_text.lower()
    if _has_any_marker(rt, _CLARIFY_MEANING_MARKERS):
        return MeaningNeed.CLARIFY
    if _has_any_marker(rt, _VALIDATE_MEANING_MARKERS):
        return MeaningNeed.VALIDATE
    if _has_any_marker(rt, _REFRAME_MEANING_MARKERS):
        return MeaningNeed.REFRAME
    return MeaningNeed.NONE


def _map_envelope_to_intention(env: EnvelopeState) -> EmotionalIntention:
    """Deterministic. Maps EnvelopeState → EmotionalIntention."""
    return EmotionalIntention(
        target_state=_canonicalise_target_state(env.rough_intention),
        regulatory_goal=_derive_regulatory_goal(env),
        relational_posture=_derive_relational_posture(env),
        meaning_need=_derive_meaning_need(env),
    )


# ---------------------------------------------------------------------------
# _map_envelope_to_fea_inputs — the three-tuple bundle
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Phase 3 Unit 6 — intention-class derivation for build_candidate
# ---------------------------------------------------------------------------
# Locked priority order — first match wins. Markers come from the existing
# build_candidate docstring rule table. "no" is matched as a whole word
# (regex \bno\b) to avoid false positives like "noticed" / "I know" /
# "notify".
_INTENTION_VENT_MARKERS:        tuple = ("vent",)
_INTENTION_APOLOGIZE_MARKERS:   tuple = ("apologize", "i'm sorry")
_INTENTION_REQUEST_MARKERS:     tuple = ("request", "need", "ask")
_INTENTION_BOUNDARY_PHRASES:    tuple = ("boundary", "limit")
_INTENTION_OBSERVATION_MARKERS: tuple = ("observe", "noticed")
_INTENTION_GRATITUDE_MARKERS:   tuple = ("thanks", "appreciate")

# Word-boundary regex for "no" — avoids false positives in tokens like
# "noticed", "notify", "I know", "nope".
_INTENTION_BOUNDARY_NO_RE = re.compile(r"\bno\b", re.IGNORECASE)


def _intention_text(env: EnvelopeState) -> str:
    """Concatenate rough_intention + raw_text (lowercased) for derivation."""
    return (env.rough_intention + " " + env.raw_text).lower()


def _derive_intention_class(env: EnvelopeState) -> IntentionClass:
    """Pure function. Derive IntentionClass from envelope text via the
    priority-ordered rule table documented on build_candidate.

    Priority (first match wins):
        1. VENT
        2. APOLOGIZE
        3. REQUEST
        4. BOUNDARY
        5. OBSERVATION
        6. GRATITUDE
        7. OTHER (fallthrough)
    """
    text = _intention_text(env)

    for m in _INTENTION_VENT_MARKERS:
        if m in text:
            return IntentionClass.VENT

    for m in _INTENTION_APOLOGIZE_MARKERS:
        if m in text:
            return IntentionClass.APOLOGIZE

    for m in _INTENTION_REQUEST_MARKERS:
        if m in text:
            return IntentionClass.REQUEST

    for m in _INTENTION_BOUNDARY_PHRASES:
        if m in text:
            return IntentionClass.BOUNDARY
    if _INTENTION_BOUNDARY_NO_RE.search(text):
        return IntentionClass.BOUNDARY

    for m in _INTENTION_OBSERVATION_MARKERS:
        if m in text:
            return IntentionClass.OBSERVATION

    for m in _INTENTION_GRATITUDE_MARKERS:
        if m in text:
            return IntentionClass.GRATITUDE

    return IntentionClass.OTHER


def _map_envelope_to_fea_inputs(env: EnvelopeState) -> tuple:
    """Pure function. Map an EnvelopeState into the three FEA input types.

    Returns:
        (EmotionalSnapshot, EmotionalGeometry, EmotionalIntention)

    Raises:
        ValueError if `env` is not an EnvelopeState.
    """
    if not isinstance(env, EnvelopeState):
        raise ValueError(
            f"_map_envelope_to_fea_inputs expected EnvelopeState, "
            f"got {type(env).__name__}"
        )

    snapshot = _map_envelope_to_snapshot(env)
    geometry = _map_envelope_to_geometry(env)
    intention = _map_envelope_to_intention(env)
    return (snapshot, geometry, intention)


# ---------------------------------------------------------------------------
# Default Ambient Trust + Orchestrator state for the v1 integration call
# ---------------------------------------------------------------------------
# v1 of fea_integration_engine.integrate_alignment does not read fields off
# `session`, `trust`, `envelope`, or `propagation` (asserted by the source-
# code test in test_fea_integration). It DOES read `momentum.passes_invariant`
# and `understanding.passes_invariant`. The factories below build minimal
# real instances so the integration call is type-correct and momentum/
# understanding are well-defined (passing None for those would crash the
# engine).
#
# Future Phase 3 units will replace these factories with calls that derive
# real SessionContext / TrustState / PropagationState from the actual
# operator state and orchestrator workflow.
# ---------------------------------------------------------------------------
_FIXED_EPOCH: datetime = datetime(2026, 1, 1, 0, 0, 0)


def _default_session_context() -> SessionContext:
    """Build the v1 default SessionContext (no prior interaction state)."""
    return SessionContext(
        ability_level=0,
        comprehension_level=0,
        concept_exposures=(),
        hard_stop_count=0,
        last_action_acknowledged=True,
    )


def _default_propagation_state() -> PropagationState:
    """Build a structurally-valid PropagationState placeholder.

    v1 doesn't read any field off this object (asserted by FEA Integration's
    source-code test), but the type signature requires a real instance.
    Identifier fields use a fixed epoch timestamp so this factory is
    deterministic.
    """
    drift = DriftState(
        axis=DriftAxis.INTENT,
        magnitude=0.0,
        direction="stable",
        baseline_anchor="azimuth_v1",
        in_bounds=True,
        measured_at=_FIXED_EPOCH,
    )
    geom = GeometryProfile(
        depth=0, breadth=1, pressure_load=0.0,
        stability_score=1.0, captured_at=_FIXED_EPOCH,
    )
    ident = IdentityProfile(
        actor="azimuth", actor_kind=ActorKind.SYSTEM,
        sovereignty_level=SovereigntyLevel.USER_OWNED,
        authorization_tier=AuthorizationTier.OBSERVE,
    )
    return PropagationState(
        from_step="azimuth_transition",
        to_step="fea_integration",
        active_constraints=(),
        drift_state=drift,
        geometry_profile=geom,
        identity_profile=ident,
        invariants_preserved=(),
    )


# ---------------------------------------------------------------------------
# compute_aligned_expression — the live Azimuth → FEA → Integration path
# ---------------------------------------------------------------------------
def compute_aligned_expression(env: EnvelopeState) -> IntegratedAlignmentResult:
    """Live Phase 3 Unit 5 path: EnvelopeState → FEA → FEA Integration.

    Pipeline (deterministic, pure):
        1. Validate `env` is an EnvelopeState.
        2. Map envelope to (EmotionalSnapshot, EmotionalGeometry,
           EmotionalIntention) via _map_envelope_to_fea_inputs.
        3. Call align_expression(snapshot, geometry, intention, primitive)
           with primitive = ExpressionPrimitive.GEOMETRY (v1 default).
        4. Build minimal real Ambient Trust + Orchestrator state for v1
           (session, trust, propagation as structurally-valid placeholders;
           momentum and understanding via the real Ambient Trust engine).
        5. Call integrate_alignment(...) with the seven inputs and return
           its IntegratedAlignmentResult.

    Args:
        env: EnvelopeState. The caller's intimate, on-device envelope.

    Returns:
        IntegratedAlignmentResult — the structural advisory verdict
        downstream surfaces and orchestrator consume.

    Raises:
        ValueError if `env` is not an EnvelopeState.

    Invariants:
        * Pure: no I/O, no LLM, no network, no randomness.
        * `env` is never mutated.
        * Same envelope → byte-equal IntegratedAlignmentResult.
        * Existing Azimuth stubs are not invoked (they would raise).
    """
    if not isinstance(env, EnvelopeState):
        raise ValueError(
            f"compute_aligned_expression expected EnvelopeState, "
            f"got {type(env).__name__}"
        )

    snapshot, geometry, intention = _map_envelope_to_fea_inputs(env)
    aligned = align_expression(snapshot, geometry, intention, _DEFAULT_PRIMITIVE)

    session = _default_session_context()
    trust = assess_trust_state(session)
    propagation = _default_propagation_state()
    momentum = verify_no_hard_stops(session)
    understanding = verify_comprehension_leads_action(session)

    return integrate_alignment(
        aligned=aligned,
        session=session,
        trust=trust,
        envelope=env,
        propagation=propagation,
        momentum=momentum,
        understanding=understanding,
    )
