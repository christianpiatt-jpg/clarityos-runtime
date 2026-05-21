"""
ingestion_engine.py — Deterministic Feedback Ingestion Engine.

Pure, deterministic, testable. No I/O. No randomness. No LLM. No
network.

Given a FeedbackSubmission, extract_pattern() returns a FeedbackPattern
classifying:
    * pattern_type        — TONE / DRIFT / PRESSURE / ALIGNMENT / BOUNDARY / USE_CASE
    * context             — the conversation mode the feedback came from
    * pressure_level      — forwarded from submission
    * signal              — POSITIVE / NEGATIVE / NEUTRAL (lexical scan)
    * primitive_involved  — forwarded from submission
    * suggested_adjustment — canonical string from the locked table

SELECTION DISCIPLINE (strict priority order):

    1. HARD OVERRIDE — pressure ∈ {HIGH, CRITICAL}     → PRESSURE
    2. HARD OVERRIDE — text contains drift markers     → DRIFT
    3. mode == OPERATOR                                → ALIGNMENT
    4. mode == DECISION                                → USE_CASE
    5. mode == EMOTIONAL                               → TONE
    6. mode == STRUCTURAL                              → ALIGNMENT
    7. mode == EXPLORATORY                             → USE_CASE
    8. primitive fallback (currently dead path; future-proof)
    9. default                                         → ALIGNMENT

Whiplash prevention (optional, via ExtractionContext):
    If last_pattern_type is set and the candidate would change, the
    engine STICKS with last_pattern_type when both mode AND pressure are
    unchanged. Hard overrides (rules 1 and 2) always bypass whiplash.

INVARIANTS (locked, test-enforced):
    * Pure function — no I/O, no randomness, no LLM.
    * Output FeedbackPattern carries NO raw text and NO identity.
    * Same FeedbackSubmission → byte-identical FeedbackPattern.
"""
from __future__ import annotations

from typing import Optional

from feedback_schemas import (
    ExtractionContext,
    FeedbackPattern,
    FeedbackSubmission,
    PatternType,
    SignalType,
)
from azimuth import PressureLevel
from language_schemas import ConversationMode, ExpressionPrimitive


# ---------------------------------------------------------------------------
# Locked lexical sets — drift / signal markers
# ---------------------------------------------------------------------------
_HIGH_PRESSURE: frozenset = frozenset({
    PressureLevel.HIGH, PressureLevel.CRITICAL,
})

# Drift markers — when present in the text, rule 2 fires.
_DRIFT_MARKERS: tuple = (
    "drift",
    "confus",       # confusion / confused / confusing
    "mismatch",
    "misalign",     # misalignment / misaligned
    "lost",
    "wandered",
    "off track",
)

# Positive sentiment markers (substring match).
_POSITIVE_MARKERS: tuple = (
    "helpful", "helped", "good", "worked", "clear", "effective",
    "great", "useful", "love", "appreciate", "thanks", "thank",
)

# Negative sentiment markers (substring match). Negative wins on ties.
_NEGATIVE_MARKERS: tuple = (
    "wrong", "bad", "missed", "harsh", "sharp", "broken",
    "frustrat",      # frustrate / frustrated / frustrating
    "didn't", "doesn't", "couldn't", "shouldn't",
    "fail", "poor",
)


# ---------------------------------------------------------------------------
# Locked mapping tables — mode-driven, primitive-driven, adjustment
# ---------------------------------------------------------------------------
_MODE_TO_PATTERN: dict = {
    ConversationMode.OPERATOR:    PatternType.ALIGNMENT,
    ConversationMode.DECISION:    PatternType.USE_CASE,
    ConversationMode.EMOTIONAL:   PatternType.TONE,
    ConversationMode.STRUCTURAL:  PatternType.ALIGNMENT,
    ConversationMode.EXPLORATORY: PatternType.USE_CASE,
}

# Primitive fallback — fires only when mode has no mapping. Currently
# every ConversationMode is mapped, so this path is dead in production
# but kept for future-proofing.
_PRIMITIVE_TO_PATTERN: dict = {
    ExpressionPrimitive.HYDRONICS: PatternType.PRESSURE,
    ExpressionPrimitive.GEOMETRY:  PatternType.ALIGNMENT,
    ExpressionPrimitive.MOTION:    PatternType.DRIFT,
    ExpressionPrimitive.ANALOGY:   PatternType.USE_CASE,
}

# Canonical short strings — never user text. Test-asserted: every
# PatternType has an entry.
_ADJUSTMENT_TABLE: dict = {
    PatternType.PRESSURE:  "Reduce intensity; favor STABLE tone + HIGHLY_STRUCTURED structure",
    PatternType.DRIFT:     "Increase clarity bridging; consider ANALOGY primitive",
    PatternType.TONE:      "Soften tone; check audience and pressure context",
    PatternType.ALIGNMENT: "Re-anchor to structural baseline; favor GEOMETRY primitive",
    PatternType.BOUNDARY:  "Reinforce sovereignty boundaries; defer to user authority",
    PatternType.USE_CASE:  "Surface as exemplar pattern; consider for documentation",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _contains_drift_markers(text: str) -> bool:
    """True if text contains any canonical drift marker. Case-insensitive."""
    if not isinstance(text, str) or not text:
        return False
    lower = text.lower()
    return any(marker in lower for marker in _DRIFT_MARKERS)


def _detect_signal(text: str) -> SignalType:
    """Lexical signal classification. Negative wins on tie.

    Deterministic: given the same text, always returns the same SignalType.
    """
    if not isinstance(text, str) or not text:
        return SignalType.NEUTRAL
    lower = text.lower()
    has_negative = any(marker in lower for marker in _NEGATIVE_MARKERS)
    has_positive = any(marker in lower for marker in _POSITIVE_MARKERS)
    # Negative wins on tie (safer default).
    if has_negative:
        return SignalType.NEGATIVE
    if has_positive:
        return SignalType.POSITIVE
    return SignalType.NEUTRAL


def _hard_override(submission: FeedbackSubmission) -> Optional[PatternType]:
    """Return the override pattern, or None if no override applies.

    Rule 1: pressure ∈ {HIGH, CRITICAL} → PRESSURE.
    Rule 2: text contains drift markers → DRIFT.
    Rule 1 wins over rule 2 by priority order.
    """
    if submission.pressure_level in _HIGH_PRESSURE:
        return PatternType.PRESSURE
    if _contains_drift_markers(submission.text):
        return PatternType.DRIFT
    return None


def _select_pattern_type(submission: FeedbackSubmission) -> PatternType:
    """Run the full priority chain without whiplash check."""
    # Rules 1 + 2 (hard overrides).
    override = _hard_override(submission)
    if override is not None:
        return override

    # Rules 3-7 (mode-driven).
    if submission.mode in _MODE_TO_PATTERN:
        return _MODE_TO_PATTERN[submission.mode]

    # Rule 8 (primitive-driven fallback — currently dead path).
    if submission.primitive_used in _PRIMITIVE_TO_PATTERN:
        return _PRIMITIVE_TO_PATTERN[submission.primitive_used]

    # Rule 9 (safe default).
    return PatternType.ALIGNMENT


def _check_whiplash(
    candidate: PatternType,
    submission: FeedbackSubmission,
    ctx: Optional[ExtractionContext],
) -> PatternType:
    """If continuity is preferred (no meaningful Δ in mode/pressure),
    return the last pattern type. Hard overrides bypass this — caller
    handles that ordering.
    """
    if ctx is None or ctx.last_pattern_type is None:
        return candidate
    if candidate == ctx.last_pattern_type:
        return candidate
    mode_unchanged = ctx.last_mode == submission.mode
    pressure_unchanged = ctx.last_pressure == submission.pressure_level
    if mode_unchanged and pressure_unchanged:
        return ctx.last_pattern_type
    return candidate


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def extract_pattern(
    submission: FeedbackSubmission,
    ctx: Optional[ExtractionContext] = None,
) -> FeedbackPattern:
    """Pure deterministic feedback → pattern extraction.

    Reads `submission.text` ONCE (lexical scans for drift markers + signal
    markers) and discards. The returned FeedbackPattern carries NO raw
    text and NO identity — only canonical structural metadata.

    Args:
        submission: the founder feedback submission (frozen dataclass).
        ctx:        optional ExtractionContext for whiplash prevention.

    Returns:
        FeedbackPattern — pattern type, context, pressure, signal,
        primitive, and a canonical short adjustment string.

    INVARIANTS:
        * Pure function (no I/O, no randomness, no LLM).
        * Deterministic: same input → byte-equal output.
        * Output omits text, identity, and any user-supplied content.
    """
    # 1. Compute hard override (if any).
    override = _hard_override(submission)

    # 2. Pattern type:
    #    - If override fires, use it (bypasses whiplash).
    #    - Else compute candidate from mode/primitive chain, then apply
    #      whiplash check.
    if override is not None:
        pattern_type = override
    else:
        candidate = _select_pattern_type(submission)
        pattern_type = _check_whiplash(candidate, submission, ctx)

    # 3. Signal detection.
    signal = _detect_signal(submission.text)

    # 4. Adjustment — canonical short string, never user text.
    suggested_adjustment = _ADJUSTMENT_TABLE.get(pattern_type, "")

    # 5. Emit. No text. No identity.
    return FeedbackPattern(
        pattern_type=pattern_type,
        context=submission.mode,
        pressure_level=submission.pressure_level,
        signal=signal,
        primitive_involved=submission.primitive_used,
        suggested_adjustment=suggested_adjustment,
    )
