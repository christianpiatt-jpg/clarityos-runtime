"""
elins_operator_regime.py — ELINS11 Unit 30.

Operator regime actions on top of Unit 29's regime-comparison engine.
Three helpers that turn a structural regime delta into action
(decision + tags) or distribution (structured regime report), plus a
caller-supplied override surface for manual operator decisions.

ROLE
----
Operator workflow surface for regime-to-regime structural decisions.
Pure composition over Unit 29. Tag mutations are dedupe-aware and
idempotent; override paths leave the underlying comparison intact.

DECISION RULES (locked, deterministic)
--------------------------------------
    risk_assessment == "high"   →  decision = "block"
    risk_assessment == "medium" →  decision = "warn"
    risk_assessment == "low"    →  decision = "allow"

TAG VOCABULARY (locked)
-----------------------
Regime tags (exactly one fires):
    "regime_same"
    "regime_improved"
    "regime_degraded"

Risk tags (exactly one fires):
    "risk_low"
    "risk_medium"
    "risk_high"

Volatility tags (exactly one fires):
    "volatility_increased"   — absolute delta >  +0.005
    "volatility_decreased"   — absolute delta <  -0.005
    "volatility_stable"      — otherwise

Breakpoint tags (exactly one fires):
    "breakpoints_increased"
    "breakpoints_decreased"
    "breakpoints_stable"

PUBLIC API
----------
    evaluate_regime_change(baseline, candidate)         -> dict
    generate_regime_report(baseline, candidate)         -> dict
    tag_regime_decisions(comparison, decisions)         -> dict
"""
from __future__ import annotations

from elins_regime_comparison import compare_regimes


# Locked tag vocabulary.
TAG_REGIME_SAME:           str = "regime_same"
TAG_REGIME_IMPROVED:       str = "regime_improved"
TAG_REGIME_DEGRADED:       str = "regime_degraded"

TAG_RISK_LOW:    str = "risk_low"
TAG_RISK_MEDIUM: str = "risk_medium"
TAG_RISK_HIGH:   str = "risk_high"

TAG_VOLATILITY_INCREASED: str = "volatility_increased"
TAG_VOLATILITY_DECREASED: str = "volatility_decreased"
TAG_VOLATILITY_STABLE:    str = "volatility_stable"

TAG_BREAKPOINTS_INCREASED: str = "breakpoints_increased"
TAG_BREAKPOINTS_DECREASED: str = "breakpoints_decreased"
TAG_BREAKPOINTS_STABLE:    str = "breakpoints_stable"

TAG_OVERRIDE_DECISION:   str = "override_decision"
TAG_OVERRIDE_ESCALATED:  str = "override_escalated"

# Locked volatility tag cutoff (mirrors Unit 29's low-risk threshold).
_VOLATILITY_TAG_EPSILON: float = 0.005

# Decision vocabulary.
_DECISION_ALLOW: str = "allow"
_DECISION_WARN:  str = "warn"
_DECISION_BLOCK: str = "block"
_VALID_DECISIONS: tuple = (_DECISION_ALLOW, _DECISION_WARN, _DECISION_BLOCK)

# Risk → decision map (locked).
_RISK_DECISION_MAP: dict = {
    "high":   _DECISION_BLOCK,
    "medium": _DECISION_WARN,
    "low":    _DECISION_ALLOW,
}

# Risk → risk tag.
_RISK_TAG_MAP: dict = {
    "high":   TAG_RISK_HIGH,
    "medium": TAG_RISK_MEDIUM,
    "low":    TAG_RISK_LOW,
}

# Regime delta → regime tag.
_REGIME_TAG_MAP: dict = {
    "same":     TAG_REGIME_SAME,
    "improved": TAG_REGIME_IMPROVED,
    "degraded": TAG_REGIME_DEGRADED,
}

# Required Unit 29 comparison keys (a sanity-check surface for callers
# that build their own comparison dicts before invoking the operator).
_REQUIRED_COMPARISON_KEYS: tuple = (
    "regime_delta",
    "volatility_delta",
    "breakpoint_delta",
    "risk_assessment",
)


def _validate_decision(decision, label: str) -> None:
    if not isinstance(decision, str) or decision not in _VALID_DECISIONS:
        raise ValueError(
            f"{label} must be one of {_VALID_DECISIONS}, got {decision!r}"
        )


def _validate_comparison(comparison) -> None:
    if not isinstance(comparison, dict):
        raise ValueError(
            f"comparison must be a dict (Unit 29 output), "
            f"got {type(comparison).__name__}"
        )
    for key in _REQUIRED_COMPARISON_KEYS:
        if key not in comparison:
            raise ValueError(
                f"comparison missing required Unit 29 key {key!r}"
            )


def _volatility_tag(abs_delta: float) -> str:
    if abs_delta > _VOLATILITY_TAG_EPSILON:
        return TAG_VOLATILITY_INCREASED
    if abs_delta < -_VOLATILITY_TAG_EPSILON:
        return TAG_VOLATILITY_DECREASED
    return TAG_VOLATILITY_STABLE


def _breakpoint_tag(delta: int) -> str:
    if delta > 0:
        return TAG_BREAKPOINTS_INCREASED
    if delta < 0:
        return TAG_BREAKPOINTS_DECREASED
    return TAG_BREAKPOINTS_STABLE


def _tags_for_comparison(comparison: dict) -> list:
    """Build the locked-vocabulary tag list from a Unit 29 comparison.
    Alpha-sorted for deterministic operator rendering."""
    tags: list = [
        _REGIME_TAG_MAP.get(comparison["regime_delta"], TAG_REGIME_SAME),
        _RISK_TAG_MAP.get(comparison["risk_assessment"], TAG_RISK_MEDIUM),
        _volatility_tag(float(comparison["volatility_delta"]["absolute"])),
        _breakpoint_tag(int(comparison["breakpoint_delta"]["delta"])),
    ]
    return sorted(tags)


def evaluate_regime_change(baseline, candidate) -> dict:
    """Evaluate Unit 29 and emit decision + tags + full comparison.

    Args:
        baseline:  Unit 27 output for the reference period.
        candidate: Unit 27 output for the period under comparison.

    Returns:
        ``{
            "decision":   "allow | warn | block",
            "tags":       list[str],   # alpha-sorted
            "comparison": <full Unit 29 output>,
        }``.

    Raises:
        ValueError on a malformed payload (forwarded from Unit 29).
    """
    comparison = compare_regimes(baseline, candidate)
    decision = _RISK_DECISION_MAP.get(
        comparison["risk_assessment"], _DECISION_WARN,
    )
    tags = _tags_for_comparison(comparison)
    return {
        "decision":   decision,
        "tags":       tags,
        "comparison": comparison,
    }


def _empty_regime_report() -> dict:
    """Locked-shape placeholder — used when callers pass empty Unit 27
    payloads at both sides. Same key set as a populated report."""
    return {
        "headline":         "No structural data supplied for regime comparison.",
        "decision":         _DECISION_WARN,
        "risk_assessment":  "medium",
        "regime_delta":     "same",
        "volatility_delta": {"absolute": 0.0, "relative": 0.0},
        "breakpoint_delta": {
            "baseline_count": 0, "candidate_count": 0, "delta": 0,
        },
        "event_summary": {
            "new_events": [], "resolved_events": [], "persistent_events": [],
        },
        "baseline":   {},
        "candidate":  {},
        "comparison": {},
    }


def _headline_for_regime(decision: str,
                         comparison: dict) -> str:
    """Compose the spec-format headline:
        ``"BLOCK: Regime degraded to UNSTABLE (high risk; volatility +0.024;
        breakpoints +3)."``
    """
    regime_delta = comparison["regime_delta"]
    risk = comparison["risk_assessment"]
    vol_abs = float(comparison["volatility_delta"]["absolute"])
    bp_delta = int(comparison["breakpoint_delta"]["delta"])
    candidate_regime = comparison.get("candidate", {}).get("regime_class", "")
    return (
        f"{decision.upper()}: Regime {regime_delta} "
        f"to {candidate_regime.upper()} "
        f"({risk} risk; "
        f"volatility {vol_abs:+.3f}; "
        f"breakpoints {bp_delta:+d})."
    )


def generate_regime_report(baseline, candidate) -> dict:
    """Bundle Units 27 + 29 + 30 into an operator-facing report.

    Args:
        baseline:  Unit 27 output for the reference period.
        candidate: Unit 27 output for the period under comparison.

    Returns:
        Locked-shape dict::

            {
              "headline":         str,
              "decision":         "allow | warn | block",
              "risk_assessment":  "low | medium | high",
              "regime_delta":     "same | improved | degraded",
              "volatility_delta": {"absolute", "relative"},
              "breakpoint_delta": {"baseline_count", "candidate_count", "delta"},
              "event_summary":    {"new_events", "resolved_events", "persistent_events"},
              "baseline":         <Unit 27 output>,
              "candidate":        <Unit 27 output>,
              "comparison":       <Unit 29 output>,
            }

    Raises:
        ValueError on a malformed payload (forwarded from Unit 29).
    """
    evaluation = evaluate_regime_change(baseline, candidate)
    comparison = evaluation["comparison"]
    headline = _headline_for_regime(evaluation["decision"], comparison)
    return {
        "headline":         headline,
        "decision":         evaluation["decision"],
        "risk_assessment":  comparison["risk_assessment"],
        "regime_delta":     comparison["regime_delta"],
        "volatility_delta": comparison["volatility_delta"],
        "breakpoint_delta": comparison["breakpoint_delta"],
        "event_summary":    comparison["event_summary"],
        "baseline":         comparison["baseline"],
        "candidate":        comparison["candidate"],
        "comparison":       comparison,
    }


def tag_regime_decisions(comparison, decisions) -> dict:
    """Apply caller-supplied overrides + tags to a Unit 29 comparison.

    Supported override keys (all optional):

        "override_decision": str   — replace the risk-based decision
                                     with an explicit "allow / warn /
                                     block". Adds the ``override_decision``
                                     tag so audit logs can trace
                                     manual overrides.
        "escalate":          bool  — when True, append the
                                     ``override_escalated`` tag.
        "audit_note":        str   — kept in the response's
                                     ``overrides`` echo for audit
                                     trails; does not generate a tag.

    Args:
        comparison: full Unit 29 ``compare_regimes`` output (or any
            dict matching its locked contract).
        decisions: dict of override / audit / escalation directives.
            Empty dict is allowed and is a no-op apart from the
            base risk-derived tags.

    Returns:
        ``{
            "applied":   True,
            "tags":      list[str],   # alpha-sorted, deduped
            "overrides": dict,        # echo of the validated overrides
        }``.

    Raises:
        ValueError on a malformed comparison or decisions dict.
    """
    _validate_comparison(comparison)
    if not isinstance(decisions, dict):
        raise ValueError(
            f"tag_regime_decisions expected decisions to be a dict, "
            f"got {type(decisions).__name__}"
        )

    base_tags = set(_tags_for_comparison(comparison))
    overrides: dict = {}

    # override_decision: validates against the locked vocabulary and
    # augments the tag set with both the matching risk-tier tag and
    # the audit-trail "override_decision" marker.
    if "override_decision" in decisions:
        ov = decisions["override_decision"]
        _validate_decision(ov, "decisions['override_decision']")
        overrides["override_decision"] = ov
        base_tags.add(TAG_OVERRIDE_DECISION)
        # Also reflect the operator's intended tier in the tag set so
        # downstream callers see both the original risk tag AND the
        # chosen tier.
        decision_tier_tag = {
            _DECISION_ALLOW: TAG_RISK_LOW,
            _DECISION_WARN:  TAG_RISK_MEDIUM,
            _DECISION_BLOCK: TAG_RISK_HIGH,
        }[ov]
        base_tags.add(decision_tier_tag)

    if "escalate" in decisions:
        esc = decisions["escalate"]
        if not isinstance(esc, bool):
            raise ValueError(
                f"decisions['escalate'] must be a bool, "
                f"got {type(esc).__name__}"
            )
        overrides["escalate"] = esc
        if esc:
            base_tags.add(TAG_OVERRIDE_ESCALATED)

    if "audit_note" in decisions:
        note = decisions["audit_note"]
        if not isinstance(note, str):
            raise ValueError(
                f"decisions['audit_note'] must be a string, "
                f"got {type(note).__name__}"
            )
        overrides["audit_note"] = note

    return {
        "applied":   True,
        "tags":      sorted(base_tags),
        "overrides": overrides,
    }
