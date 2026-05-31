# phase11_recommendations.py
"""
Phase 11.0 — Action Recommendation Engine.

A deterministic, structural recommendation layer over the Phase 9/10 engines: it
identifies behavioral *leverage points* and surfaces them as recommended
operator actions. It does NOT advise, interpret, or guess — every recommendation
is grounded in a structural signal (a delta, a motif, a forecast value), scored
by a fixed rule, and sorted deterministically.

    compute_action_recommendations(deltas, motifs, stability, forecast) -> list[dict]

Each recommendation::

    {"action_id": <str>,
     "label": <str>,
     "reason": "habit_weakening" | "trigger_volatility" | "loop_break"
             | "bottleneck_relief" | "attractor_alignment" | "forecast_alignment",
     "score": <float in [0, 1]>}

The six recommendation types (each score clamped to ``[0, 1]``):
  1. habit_weakening    — a label whose 10.1 frequency delta is negative (its
                          frequency dropped); ``score = |frequency delta|``.
  2. trigger_volatility — a 10.0 trigger chain, scored by its likelihood
                          (``score = |likelihood|`` — the volatility signal; no
                          temporal trigger-likelihood delta exists upstream, see 10.2).
  3. loop_break         — a 10.0 loop, scored by how breakable it is
                          (``score = 1 - continuation_probability``).
  4. bottleneck_relief  — a 9.4 action bottleneck; ``score = normalized list
                          rank`` (9.4 sorts bottlenecks by centrality desc, so the
                          position encodes inbound-influence strength).
  5. attractor_alignment— a 9.4 action attractor; ``score = normalized list rank``
                          (9.4 sorts attractors by influence desc → attractor strength).
  6. forecast_alignment — a 10.0 next-action prediction; ``score = forecast score``.
                          Keyed by *label* so it dedupes with habit recs.

Final list: drop zero-score candidates, sort by descending score (ties by
action_id then reason), dedupe by ``action_id`` keeping the highest-scoring
reason, cap at 10.

``stability`` is accepted for signature parity with the Phase-10 API (and future
instability-weighting); the six types above derive from deltas + motifs +
forecast only.

Pure / deterministic: no I/O, wall-clock, randomness, ML, inference, or
psychological language. Imports nothing beyond builtins — nothing from the
CI-gated runtime spine, vault, or operator_state; no operator_state writes, no
new continuity buckets.

See ``phase11_spec.md`` ("Phase 11.0 — Action Recommendation Engine").
"""

TOP_K = 10


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def compute_action_recommendations(deltas: dict, motifs: dict, stability: dict, forecast: dict) -> list:
    """Deterministic structural action recommendations. See the module docstring
    for the six types, scoring rules, and ordering. Output is JSON-serialisable."""
    deltas = deltas or {}
    motifs = motifs or {}
    forecast = forecast or {}
    # `stability` is reserved (signature parity / future instability-weighting).

    candidates = []

    # (1) habit_weakening — a label whose frequency dropped (10.1 frequency delta < 0).
    frequency = deltas.get("frequency") or {}
    for label in sorted(frequency):
        delta = float((frequency.get(label) or {}).get("delta", 0.0))
        if delta < 0.0:
            candidates.append({
                "action_id": label,
                "label": label,
                "reason": "habit_weakening",
                "score": _clamp(abs(delta), 0.0, 1.0),
            })

    # (2) trigger_volatility — a volatile 10.0 trigger chain (scored by likelihood).
    for entry in forecast.get("trigger_likelihood") or []:
        chain = list(entry.get("chain") or [])
        key = " → ".join(str(node) for node in chain)
        candidates.append({
            "action_id": key,
            "label": key,
            "reason": "trigger_volatility",
            "score": _clamp(abs(float(entry.get("likelihood", 0.0))), 0.0, 1.0),
        })

    # (3) loop_break — a 10.0 loop, scored by how breakable it is.
    for entry in forecast.get("loop_continuation") or []:
        loop = list(entry.get("loop") or [])
        key = " → ".join(str(node) for node in loop)
        candidates.append({
            "action_id": key,
            "label": key,
            "reason": "loop_break",
            "score": _clamp(1.0 - float(entry.get("continuation_probability", 0.0)), 0.0, 1.0),
        })

    # (4) bottleneck_relief — 9.4 bottlenecks, scored by normalized list rank
    #     (the 9.4 list is sorted by centrality desc, so position encodes the
    #     inbound-influence strength).
    bottlenecks = list(motifs.get("action_bottlenecks") or [])
    for i, node_id in enumerate(bottlenecks):
        candidates.append({
            "action_id": node_id,
            "label": node_id,
            "reason": "bottleneck_relief",
            "score": _clamp((len(bottlenecks) - i) / len(bottlenecks), 0.0, 1.0),
        })

    # (5) attractor_alignment — 9.4 attractors, normalized list rank (sorted by
    #     influence desc → attractor strength).
    attractors = list(motifs.get("action_attractors") or [])
    for i, node_id in enumerate(attractors):
        candidates.append({
            "action_id": node_id,
            "label": node_id,
            "reason": "attractor_alignment",
            "score": _clamp((len(attractors) - i) / len(attractors), 0.0, 1.0),
        })

    # (6) forecast_alignment — highly-predicted 10.0 next actions, keyed by label
    #     so they dedupe with habit recs on the same action.
    for entry in forecast.get("next_actions") or []:
        label = entry.get("label")
        if label is None:
            continue
        candidates.append({
            "action_id": label,
            "label": label,
            "reason": "forecast_alignment",
            "score": _clamp(float(entry.get("score", 0.0)), 0.0, 1.0),
        })

    # Drop zero-leverage candidates, sort deterministically (score desc, then
    # action_id, then reason), dedupe by action_id keeping the highest-scoring
    # reason, cap at TOP_K.
    candidates = [c for c in candidates if c["score"] > 0.0]
    candidates.sort(key=lambda c: (-c["score"], str(c["action_id"]), c["reason"]))

    seen = set()
    recommendations = []
    for candidate in candidates:
        if candidate["action_id"] in seen:
            continue
        seen.add(candidate["action_id"])
        recommendations.append(candidate)

    return recommendations[:TOP_K]
