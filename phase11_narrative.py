# phase11_narrative.py
"""
Phase 11.1 — Recommendation Narrative.

The explanation layer for the 11.0 recommendation engine — the recommendation
analogue of Phase 7.3 / 8.9-8.10 (causal) / 10.3 (behavioral) narratives. Where
11.0 says *what to do*, 11.1 says *why these actions*: a deterministic,
operator-facing account of why each recommendation was generated, the structural
drivers behind them, and the stability context.

    compute_recommendation_narrative(recommendations, deltas, motifs, stability) -> dict

Output::

    {"summary": "...",                                  # 2-3 deterministic sentences
     "recommendations": [{action_id, label, reason, score, explanation}],
     "drivers": {"habit", "triggers", "loops",
                 "bottlenecks", "attractors", "forecast_alignment"},  # [{action_id, metric, reason}]
     "stability_context": {"score", "drivers"},         # the full 10.2 object
     "raw": {"recommendations", "deltas", "motifs"}}     # inputs, verbatim

The explanations and driver buckets are derived from the ``recommendations``
list (the 11.0 output) — the drivers section is simply the recommendations
partitioned by reason. ``deltas`` / ``motifs`` feed only the ``raw`` transparency
section; ``stability`` feeds the summary + the embedded context.

Deterministic, factual generation — **no inference, no ML, no speculation, no
psychological language, no wall-clock, no randomness**. Imports nothing beyond
builtins — nothing from the CI-gated runtime spine, vault, or operator_state;
no operator_state writes, no new continuity buckets.

See ``phase11_spec.md`` ("Phase 11.1 — Recommendation Narrative").
"""

# Deterministic explanation templates, keyed by the 11.0 recommendation reason.
_EXPLANATIONS = {
    "habit_weakening": "This action is recommended because its habit strength is decreasing.",
    "trigger_volatility": "This action is recommended due to volatility in its associated trigger chain.",
    "loop_break": "This action is recommended to interrupt a weakening or unstable loop.",
    "bottleneck_relief": "This action is recommended because it is a bottleneck with high inbound influence.",
    "attractor_alignment": "This action aligns with a strong behavioral attractor.",
    "forecast_alignment": "This action is predicted as likely in the near future.",
}

# Drivers-section bucket → the 11.0 recommendation reason it collects.
_DRIVER_BUCKETS = (
    ("habit", "habit_weakening"),
    ("triggers", "trigger_volatility"),
    ("loops", "loop_break"),
    ("bottlenecks", "bottleneck_relief"),
    ("attractors", "attractor_alignment"),
    ("forecast_alignment", "forecast_alignment"),
)


def _count(n: int, noun: str) -> str:
    """``"1 recommendation"`` / ``"0 recommendations"`` — deterministic pluralisation."""
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def compute_recommendation_narrative(recommendations, deltas: dict, motifs: dict, stability: dict) -> dict:
    """Assemble the recommendation narrative. Deterministic; output is
    JSON-serialisable. See the module docstring for the full shape."""
    recommendations = list(recommendations or [])
    deltas = deltas or {}
    motifs = motifs or {}
    stability = stability or {}

    # (2) Recommendation explanations — each 11.0 rec + a deterministic template
    #     (order preserved from 11.0: descending score).
    explained = []
    for rec in recommendations:
        reason = rec.get("reason", "")
        explained.append({
            "action_id": rec.get("action_id"),
            "label": rec.get("label"),
            "reason": reason,
            "score": float(rec.get("score", 0.0)),
            "explanation": _EXPLANATIONS.get(reason, ""),
        })

    # (3) Drivers — the recommendations partitioned by reason (the 11.0 score-desc
    #     order is preserved within each bucket). Each entry: {action_id, metric,
    #     reason}, where metric is the 11.0 leverage score.
    drivers = {}
    for bucket, reason in _DRIVER_BUCKETS:
        drivers[bucket] = [
            {"action_id": rec.get("action_id"), "metric": float(rec.get("score", 0.0)), "reason": reason}
            for rec in recommendations
            if rec.get("reason") == reason
        ]

    # (4) Stability context — embed the full 10.2 object.
    stability_context = {
        "score": float(stability.get("score", 0.0)),
        "drivers": dict(stability.get("drivers") or {}),
    }

    # (1) Summary — 2-3 deterministic, factual sentences (no inference / psychology).
    score = stability_context["score"]
    if score > 0.7:
        stability_sentence = "Behavioral system is stable; recommendations focus on optimization."
    elif score < 0.4:
        stability_sentence = "Behavioral system shows instability; recommendations target stabilization."
    else:
        stability_sentence = (
            "Behavioral system shows moderate variability; recommendations address key leverage points."
        )
    reason_count = len({rec.get("reason") for rec in recommendations})
    counts_sentence = (
        f"Generated {_count(len(recommendations), 'recommendation')} "
        f"across {_count(reason_count, 'reason type')}."
    )
    sentences = [stability_sentence, counts_sentence]
    if explained:
        top = explained[0]
        sentences.append(
            f"Top recommendation: {top['label']} — {top['reason']} (score {top['score']:.2f})."
        )
    summary = " ".join(sentences)

    return {
        "summary": summary,
        "recommendations": explained,
        "drivers": drivers,
        "stability_context": stability_context,
        "raw": {
            "recommendations": recommendations,
            "deltas": deltas,
            "motifs": motifs,
        },
    }
