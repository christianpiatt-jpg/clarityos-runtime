"""
azimuth.py — Azimuth Mechanic shared schemas, enums, and invariants.

The single source of truth for the data types used by:
    * azimuth_envelope.py   (Track 1: Envelope layer)
    * azimuth_transition.py (Track 1: Transition + Cloud metadata)
    * azimuth_reframing.py  (Track 2: Expression Reframing + Azimuth Check)

PRIVACY INVARIANTS (also enforced by tests/test_azimuth_schemas.py):

    1. EnvelopeState.raw_text and ExpressionCandidate.raw_text MUST NEVER
       serialize to network, file, or non-local storage.

    2. Only CloudMetadata may cross the device → cloud boundary.

    3. CloudMetadata.__dataclass_fields__ MUST NOT contain:
           raw_text, user_id, envelope_id, candidate_id,
           intention, rough_intention
       (See § 7.1 of SPEC_AZIMUTH_MECHANIC.md.)

USER-SOVEREIGNTY INVARIANTS:

    4. The user can always stay in envelope.
    5. The user can always reject all reframings.
    6. The system never sends on the user's behalf.

INTENT INVARIANTS:

    7. The Reframing layer must preserve intention class.
    8. Accepted reframings must have preserved_intent_score >= 0.7.

See SPEC_AZIMUTH_MECHANIC.md for the full specification.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

# Forward reference only — `from __future__ import annotations` makes the
# `Optional[IntegratedAlignmentResult]` annotation on ExpressionCandidate a
# string at runtime, so no circular import is triggered.
if TYPE_CHECKING:
    from fea_integration_schemas import IntegratedAlignmentResult


# ===========================================================================
# Categorical types — canonical, locked
# ===========================================================================
class Valence(str, Enum):
    """Rough direction of emotional charge inside the envelope."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    MIXED    = "mixed"
    NEUTRAL  = "neutral"
    UNKNOWN  = "unknown"


class IntensityLevel(str, Enum):
    """Magnitude of emotional charge."""
    LOW     = "low"
    MEDIUM  = "medium"
    HIGH    = "high"
    EXTREME = "extreme"


class PressureLevel(str, Enum):
    """Felt pressure / stakes."""
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class PressureSlope(str, Enum):
    """Trajectory of pressure across recent envelopes."""
    RISING  = "rising"
    FLAT    = "flat"
    FALLING = "falling"


class PressureShape(str, Enum):
    """Macro shape of the pressure curve over a window."""
    ASCENDING  = "ascending"
    DESCENDING = "descending"
    PLATEAU    = "plateau"
    SPIKE      = "spike"


class AudienceType(str, Enum):
    """Who the expression is aimed at."""
    SELF        = "self"
    ONE_TO_ONE  = "one_to_one"
    SMALL_GROUP = "small_group"
    PUBLIC      = "public"


class ContextType(str, Enum):
    """Context the expression lives in."""
    PERSONAL     = "personal"
    PROFESSIONAL = "professional"
    HIGH_STAKES  = "high_stakes"
    LOW_STAKES   = "low_stakes"


class UrgencyLevel(str, Enum):
    """How time-critical the expression is."""
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class IntentionClass(str, Enum):
    """Canonical bucket for intention. Drives reframing rules."""
    VENT        = "vent"
    REQUEST     = "request"
    APOLOGIZE   = "apologize"
    BOUNDARY    = "boundary"
    OBSERVATION = "observation"
    GRATITUDE   = "gratitude"
    OTHER       = "other"


class UserResponse(str, Enum):
    """User's reply to the Azimuth Check prompt."""
    ACCEPT = "accept"
    TWEAK  = "tweak"
    REJECT = "reject"


# ===========================================================================
# Canonical risk-flag set
# ===========================================================================
# Drift-risk flags use these canonical names. They are SHORT, STABLE
# strings — never raw text. Downstream consumers check by membership
# (`"sharp_tone" in candidate.risk_flags`).
RISK_FLAGS_CANONICAL: tuple = (
    "sharp_tone",            # high intensity + non-self audience
    "soft_tone",             # too softened relative to stakes
    "high_pressure",         # high pressure + low context buffer
    "vague_target",          # vague intention + group audience
    "name_calling",          # accusatory language
    "all_or_nothing",        # absolutist either/or framing
    "urgency_inflation",     # urgency markers exceed actual urgency
    "passive_aggressive",    # indirect aggression markers
    "absolutist_language",   # "never", "always", "everyone"
    "ambiguous_request",     # ask not actionable
    # Phase 3 Unit 7 — alignment-aware flags driven by
    # IntegratedAlignmentResult.halt_level. They are first-class
    # canonical risk flags: lowercase, structural, no free text.
    "hard_halt",             # FEA Integration: SurfaceHaltLevel.HARD
    "soft_halt",             # FEA Integration: SurfaceHaltLevel.SOFT
)


# ===========================================================================
# Local-only id generator
# ===========================================================================
def _new_local_id() -> str:
    """Generate a local-only id. NEVER uploaded — used for in-process
    cross-reference between EnvelopeState ↔ ExpressionCandidate ↔
    ReframedExpression. The cloud privacy contract drops every *_id field
    before any upload."""
    return secrets.token_urlsafe(12)


# ===========================================================================
# Schemas — frozen dataclasses, structural privacy enforcement
# ===========================================================================

@dataclass(frozen=True)
class EnvelopeState:
    """The intimate, on-device representation of raw user reflection.

    PRIVACY: raw_text and envelope_id NEVER cross the device boundary.
    """
    raw_text:                str
    captured_at:             datetime
    emotional_intensity:     IntensityLevel
    valence:                 Valence
    pressure_level:          PressureLevel
    rough_intention:         str
    user_marked_externalize: bool = False
    envelope_id:             str  = field(default_factory=_new_local_id)


@dataclass(frozen=True)
class ExpressionCandidate:
    """Built from an EnvelopeState when the user has signaled externalization.

    PRIVACY: raw_text + intention + envelope_id + candidate_id all stay LOCAL.
    Only the CloudMetadata derived via build_cloud_metadata() may be
    uploaded.

    Phase 3 Unit 6: ``aligned`` carries the IntegratedAlignmentResult from
    fea_integration_engine when build_candidate runs the Unit-5 alignment
    loop. Defaults to None for backward compatibility — every existing
    caller and test that constructs an ExpressionCandidate without the
    field continues to work unchanged.

    PRIVACY NOTE: ``aligned`` (like raw_text and intention) stays LOCAL.
    The CloudMetadata privacy contract is unchanged — it never carries
    aligned, raw_text, intention, or any other free-text field.
    """
    raw_text:        str
    intention:       str
    intention_class: IntentionClass
    pressure_level:  PressureLevel
    pressure_slope:  PressureSlope
    audience:        AudienceType
    context:         ContextType
    urgency:         UrgencyLevel
    risk_flags:      tuple = ()
    envelope_id:     str   = ""
    candidate_id:    str   = field(default_factory=_new_local_id)
    aligned:         Optional[IntegratedAlignmentResult] = None


@dataclass(frozen=True)
class CloudMetadata:
    """The structural fingerprint that crosses the device → cloud boundary.

    PRIVACY GUARANTEE — structurally enforced:
        * NO  raw_text
        * NO  user_id
        * NO  envelope_id / candidate_id
        * NO  intention (free-text) / rough_intention
        * NO  names / verbatim phrases / identifiers
    Only canonical categorical metadata.

    The test suite asserts that __dataclass_fields__ matches the canonical
    set below exactly — any future PR that adds a free-text field fails
    the suite.
    """
    pressure_shape:  PressureShape
    pressure_slope:  PressureSlope
    pressure_level:  PressureLevel
    audience_type:   AudienceType
    context_type:    ContextType
    urgency_level:   UrgencyLevel
    intention_class: IntentionClass
    risk_flags:      tuple = ()
    schema_version:  str   = "azimuth.v1"


@dataclass(frozen=True)
class CloudAdvisory:
    """Cloud's response to a CloudMetadata submission.

    Macro context only. NEVER directives, NEVER instructions, NEVER raw
    content. The reframing layer reads advisories as hints.
    """
    basin_pressure:      PressureLevel
    macro_field_weather: str             # stable | mixed | turbulent | unknown
    audience_stake:      str             # low | medium | high
    advisories:          tuple = ()      # tuple of canonical advisory strings
    schema_version:      str   = "azimuth.v1"


@dataclass(frozen=True)
class ReframedExpression:
    """A candidate reframing that preserves intent while reducing drift risk.

    Returned by the Reframing layer; never auto-sent. The user always
    decides whether to accept, tweak, or reject.
    """
    original_intention:     str
    reframed_text:          str
    preserved_intent_score: float          # [0, 1]; higher is better
    drift_risk_after:       float          # [0, 1]; LOWER is better
    diff_notes:             tuple = ()
    candidate_id:           str   = ""


@dataclass(frozen=True)
class AzimuthCheckPrompt:
    """The user-facing confirmation prompt assembled by the Reframing layer.

    Always ends with: "Does this still feel like what you mean?"
    """
    landing_prediction: str
    reframed_options:   tuple                                    # tuple[ReframedExpression]
    user_question:      str = "Does this still feel like what you mean?"


# ===========================================================================
# Module-level structural privacy guards
# ===========================================================================
# Each item is a field name that MUST NOT appear in CloudMetadata. The
# test suite iterates this set and asserts absence. Adding any of these
# to CloudMetadata would break the privacy contract.
_FORBIDDEN_CLOUD_FIELDS: frozenset = frozenset({
    "raw_text",
    "user_id",
    "envelope_id",
    "candidate_id",
    "intention",
    "rough_intention",
    "name",
    "names",
    "identity",
    "identifier",
})


def assert_cloud_privacy_contract() -> None:
    """Runtime guard — raises AssertionError if CloudMetadata has gained
    a forbidden field. Called by the test suite. Also safe to call at
    module-load time in development.
    """
    cloud_fields = set(CloudMetadata.__dataclass_fields__.keys())
    leaked = cloud_fields & _FORBIDDEN_CLOUD_FIELDS
    assert not leaked, (
        f"CloudMetadata privacy contract violated — forbidden fields present: {leaked}"
    )
