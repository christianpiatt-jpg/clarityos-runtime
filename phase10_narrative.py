# phase10_narrative.py
"""
Phase 10.3 — Unified Behavioral Narrative.

The behavioral analogue of Phase 7.3 (unified temporal narrative) and Phase
8.9 + 8.10 (unified causal / temporal-causal narrative), but for *actions*: a
deterministic, operator-facing explanation of what changed in behaviour, the
drivers behind it, and the patterns forming — assembled purely from the engines
already built (10.0 forecast, 10.1 deltas, 10.2 stability, 9.4 motifs).

    compute_behavioral_narrative(deltas, motifs, forecast, stability) -> dict

Output (mirrors the Phase-8 unified narrative shape)::

    {"summary": "...",                       # 2-3 deterministic sentences
     "habit_changes":   [{action_id, trend, delta}],         # sorted by |delta|
     "trigger_changes": [{chain, delta}],                    # sorted by |delta|
     "loop_changes":    [{loop, continuation_probability}],  # sorted desc
     "stability": {"score", "drivers"},      # the full 10.2 object, embedded
     "forecast_highlights": [{action_id, score, drivers}],   # top 3
     "raw": {"deltas", "motifs", "forecast"}}                # inputs, verbatim

Deterministic, factual generation — **no inference, no ML, no speculation, no
psychological language, no wall-clock, no randomness**. Imports nothing beyond
builtins — nothing from the CI-gated runtime spine, vault, or operator_state;
no operator_state writes, no new continuity buckets.

Join note: ``habit_changes`` pairs the 10.0 ``habit_trajectory`` (``action_id``
+ ``trend``) with the 10.1 ``frequency`` delta looked up by that ``action_id``.
The 10.1 frequency delta is keyed by action *label* while the 10.0 trajectory's
``action_id`` is a representative event id, so the caller (10.4) must key the
frequency deltas under the same identity as the trajectory — otherwise the trend
is preserved and the delta reads 0.0. Likewise ``trigger_changes`` reuses the
10.0 trigger *likelihoods* as the change signal (no temporal trigger-likelihood
delta is produced upstream — see the 10.2 note).

See ``phase10_spec.md`` ("Phase 10.3 — Unified Behavioral Narrative").
"""


def _count(n: int, noun: str) -> str:
    """``"1 habit change"`` / ``"0 habit changes"`` — deterministic pluralisation."""
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def compute_behavioral_narrative(deltas: dict, motifs: dict, forecast: dict, stability: dict) -> dict:
    """Assemble the unified behavioral narrative. Deterministic; output is
    JSON-serialisable. See the module docstring for the full shape and the
    join / trigger notes."""
    deltas = deltas or {}
    motifs = motifs or {}
    forecast = forecast or {}
    stability = stability or {}

    frequency = deltas.get("frequency") or {}

    # (2) Habit changes — trajectory (action_id + trend) joined to the 10.1
    #     frequency delta by action_id (0.0 when unmatched). Sorted by |delta|.
    habit_changes = []
    for entry in forecast.get("habit_trajectory") or []:
        action_id = entry.get("action_id")
        delta = float((frequency.get(action_id) or {}).get("delta", 0.0))
        habit_changes.append({
            "action_id": action_id,
            "trend": entry.get("trend", "stable"),
            "delta": delta,
        })
    habit_changes.sort(key=lambda e: (-abs(e["delta"]), str(e["action_id"])))

    # (3) Trigger changes — the 10.0 trigger likelihoods as the change signal.
    #     Sorted by |delta|.
    trigger_changes = []
    for entry in forecast.get("trigger_likelihood") or []:
        trigger_changes.append({
            "chain": list(entry.get("chain") or []),
            "delta": float(entry.get("likelihood", 0.0)),
        })
    trigger_changes.sort(key=lambda e: (-abs(e["delta"]), e["chain"]))

    # (4) Loop changes — loop continuation probabilities, descending.
    loop_changes = []
    for entry in forecast.get("loop_continuation") or []:
        loop_changes.append({
            "loop": list(entry.get("loop") or []),
            "continuation_probability": float(entry.get("continuation_probability", 0.0)),
        })
    loop_changes.sort(key=lambda e: (-e["continuation_probability"], e["loop"]))

    # (5) Stability — embed the full 10.2 object.
    stability_section = {
        "score": float(stability.get("score", 0.0)),
        "drivers": dict(stability.get("drivers") or {}),
    }

    # (6) Forecast highlights — top 3 next-action predictions (action_id / score
    #     / drivers; the 10.0 label is dropped per the highlight shape).
    forecast_highlights = []
    for entry in forecast.get("next_actions") or []:
        forecast_highlights.append({
            "action_id": entry.get("action_id"),
            "score": float(entry.get("score", 0.0)),
            "drivers": list(entry.get("drivers") or []),
        })
    forecast_highlights.sort(key=lambda e: (-e["score"], str(e["action_id"])))
    forecast_highlights = forecast_highlights[:3]

    # (1) Summary — 2-3 deterministic, factual sentences (no inference / psychology).
    score = stability_section["score"]
    if score > 0.7:
        stability_sentence = "Behavioral patterns are stable."
    elif score < 0.4:
        stability_sentence = "Behavioral patterns are shifting."
    else:
        stability_sentence = "Behavioral patterns show moderate change."
    counts_sentence = (
        f"Detected {_count(len(habit_changes), 'habit change')}, "
        f"{_count(len(trigger_changes), 'trigger change')}, and "
        f"{_count(len(loop_changes), 'loop')}."
    )
    sentences = [stability_sentence, counts_sentence]
    if forecast_highlights:
        top = forecast_highlights[0]
        sentences.append(
            f"Top predicted next action: {top['action_id']} (score {top['score']:.2f})."
        )
    summary = " ".join(sentences)

    return {
        "summary": summary,
        "habit_changes": habit_changes,
        "trigger_changes": trigger_changes,
        "loop_changes": loop_changes,
        "stability": stability_section,
        "forecast_highlights": forecast_highlights,
        "raw": {
            "deltas": deltas,
            "motifs": motifs,
            "forecast": forecast,
        },
    }
