# phase7_explanation.py
"""
Phase 7.9 — Causal Narrative Synthesis (Phase 7 explanation layer).

Builds a deterministic, text-only narrative from the Phase 7 signals
(analytics + alerts + causal factors). This is NOT generative prose and NOT an
LLM call — it is a fixed template filled from the inputs, answering: what
changed, how fast, why it likely changed, and what to be aware of.

    generate_causal_narrative(analytics, alerts, causal_factors) -> str

Pure: no randomness, no I/O, no wall-clock, no side effects. No imports beyond
the stdlib — nothing from the CI-gated runtime spine.

See ``phase7_spec.md`` ("Phase 7.9 — Causal Narrative Synthesis").
"""

# The four deterministic interpretation paragraphs, keyed by trajectory.
INTERPRETATIONS = {
    "Diverging": (
        "Recent operator actions correlate with destabilizing identity "
        "movement. Continued monitoring recommended."
    ),
    "Wobbling": (
        "Identity movement shows mixed signals with moderate instability. "
        "Review contributing actions."
    ),
    "Recovering": (
        "Identity movement is stabilizing. Contributing actions appear to "
        "support recovery."
    ),
    "Stable": (
        "Identity movement is stable. No significant contributing actions "
        "detected."
    ),
}

# Unknown trajectories fall back to the conservative "Stable" reading.
_DEFAULT_TRAJECTORY = "Stable"


def _fmt(value) -> str:
    """Two-decimal fixed format, matching the console tiles."""
    return f"{float(value):.2f}"


def _is_none_factors(causal_factors) -> bool:
    """True when there are no real contributing actions (empty or the Phase
    7.7 ``[{"action": "none", ...}]`` sentinel)."""
    if not causal_factors:
        return True
    return len(causal_factors) == 1 and causal_factors[0].get("action") == "none"


def generate_causal_narrative(analytics, alerts, causal_factors) -> str:
    """Render the deterministic causal narrative.

    ``analytics`` is the Phase 7.3 block (drift_velocity / drift_acceleration /
    coherence_trend / stability_forecast / trajectory). ``alerts`` is the Phase
    7.6 list of strings. ``causal_factors`` is the Phase 7.7 list of
    ``{action, correlation, contribution}`` dicts.
    """
    trajectory = analytics.get("trajectory", _DEFAULT_TRAJECTORY)

    lines = [
        "Identity Movement Summary:",
        f"- Drift velocity: {_fmt(analytics.get('drift_velocity', 0.0))}",
        f"- Drift acceleration: {_fmt(analytics.get('drift_acceleration', 0.0))}",
        f"- Coherence trend: {_fmt(analytics.get('coherence_trend', 0.0))}",
        f"- Stability forecast: {_fmt(analytics.get('stability_forecast', 0.0))}",
        f"- Trajectory classification: {trajectory}",
        "",
        "Key Alerts:",
    ]
    if alerts:
        lines.extend(f"- {alert}" for alert in alerts)
    else:
        lines.append("- None")

    lines.append("")
    lines.append("Likely Contributing Actions:")
    if _is_none_factors(causal_factors):
        lines.append("- No significant contributing actions detected")
    else:
        for factor in causal_factors:
            lines.append(
                f"- {factor.get('action')} "
                f"(contribution: {_fmt(factor.get('contribution', 0.0))})"
            )

    lines.append("")
    lines.append("Overall Interpretation:")
    lines.append(INTERPRETATIONS.get(trajectory, INTERPRETATIONS[_DEFAULT_TRAJECTORY]))

    return "\n".join(lines)
