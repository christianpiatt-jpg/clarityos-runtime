# phase8_stability.py
"""
Phase 8.7 — Causal Stability Forecast (structural trend analysis).

Where 8.6 reports *what changed* in the causal structure, 8.7 reports what that
change *means*: is the causal system stabilizing, destabilizing, entering a
structural transition, or steady? It is the causal analogue of Phase-7's
stability forecast, but richer — it folds in motif churn and multi-chain
structure, not just drift.

    compute_causal_stability(deltas, curr) -> dict

``deltas`` is the Phase 8.6 ``compute_causal_deltas`` output; ``curr`` is the
current causal state (``{influence, centrality, motifs, chains}``). Output:

    {"stability_score": float,                 # [0, 1]
     "trend": "stabilizing" | "destabilizing" | "transitioning" | "steady",
     "drivers": {"rising_influence", "falling_influence",
                 "new_bottlenecks", "resolved_bottlenecks",
                 "new_loops", "resolved_loops",
                 "chain_strengthening", "chain_weakening"}}

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the stdlib — nothing from the CI-gated runtime spine, vault, or
operator_state.

See ``phase8_spec.md`` ("Phase 8.7 — Causal Stability Forecast").
"""

# Trend thresholds.
STABILIZING_MIN = 0.7        # stability_score must exceed this to "stabilize"
DESTABILIZING_MAX = 0.4      # below this, the system is "destabilizing"
QUIET_CHAIN_SHIFT = 0.1      # |score_shift| under this counts as a quiet chain set
MOTIF_EVENT_SCALE = 10.0     # motif_events normalized by this for the motif score

# Driver thresholds — a node / chain set moves a driver only past ±0.1.
DRIVER_RISE = 0.1
DRIVER_FALL = -0.1


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _avg_abs(values) -> float:
    """Mean absolute value of ``values`` (0.0 for an empty iterable)."""
    values = [abs(float(v)) for v in values]
    return sum(values) / len(values) if values else 0.0


def _chain_signatures(chains) -> list:
    """Sorted node-id sequences (lists) for a chain list — the same chain
    identity the 8.6 deltas use."""
    return sorted(
        [str(node.get("id")) for node in (chain.get("nodes") or [])]
        for chain in (chains or [])
    )


def compute_causal_stability(deltas: dict, curr: dict) -> dict:
    """Forecast the causal system's stability from the 8.6 deltas + current
    state. Deterministic; output is JSON-serialisable.

    Stability score (each component in ``[0, 1]``; final = their mean):
      * influence  = 1 - clamp(mean|influence_delta|, 0, 1)
      * centrality = 1 - clamp(mean|centrality_delta|, 0, 1)
      * motif      = 1 - clamp(motif_events / 10, 0, 1)
      * chain      = 1 - clamp(|chain score_shift|, 0, 1)

    Trend (first matching rule wins):
      * steady        — no movement at all (zero volatility / events / shift);
                        this is also the no-previous-snapshot fallback (→ 1.0).
      * destabilizing — score < 0.4, OR any new loop, OR any new bottleneck.
      * stabilizing   — score > 0.7 AND motif_events == 0 AND |shift| < 0.1.
      * transitioning — 0.4 ≤ score ≤ 0.7 AND motif_events > 0.
      * steady        — otherwise (covers the rule-gaps, e.g. a high score with
                        only resolved-motif / attractor churn).
    """
    deltas = deltas or {}
    curr = curr or {}
    influence_delta = deltas.get("influence_delta") or {}
    centrality_delta = deltas.get("centrality_delta") or {}
    motif_delta = deltas.get("motif_delta") or {}
    chain_delta = deltas.get("chain_delta") or {}

    # --- component scores ---------------------------------------------------
    influence_volatility = _avg_abs(influence_delta.values())
    centrality_volatility = _avg_abs(centrality_delta.values())
    influence_score = 1.0 - _clamp(influence_volatility, 0.0, 1.0)
    centrality_score = 1.0 - _clamp(centrality_volatility, 0.0, 1.0)

    new_loops = motif_delta.get("new_loops") or []
    resolved_loops = motif_delta.get("resolved_loops") or []
    new_bottlenecks = motif_delta.get("new_bottlenecks") or []
    resolved_bottlenecks = motif_delta.get("resolved_bottlenecks") or []
    new_attractors = motif_delta.get("new_attractors") or []
    resolved_attractors = motif_delta.get("resolved_attractors") or []
    motif_events = (
        len(new_loops) + len(resolved_loops)
        + len(new_bottlenecks) + len(resolved_bottlenecks)
        + len(new_attractors) + len(resolved_attractors)
    )
    motif_score = 1.0 - _clamp(motif_events / MOTIF_EVENT_SCALE, 0.0, 1.0)

    score_shift = float(chain_delta.get("score_shift", 0.0))
    chain_shift_abs = abs(score_shift)
    chain_score = 1.0 - _clamp(chain_shift_abs, 0.0, 1.0)

    stability_score = _clamp(
        (influence_score + centrality_score + motif_score + chain_score) / 4.0,
        0.0, 1.0,
    )

    # --- trend classification ----------------------------------------------
    no_movement = (
        influence_volatility == 0.0
        and centrality_volatility == 0.0
        and motif_events == 0
        and chain_shift_abs == 0.0
    )
    if no_movement:
        trend = "steady"
    elif (
        stability_score < DESTABILIZING_MAX
        or len(new_loops) > 0
        or len(new_bottlenecks) > 0
    ):
        trend = "destabilizing"
    elif (
        stability_score > STABILIZING_MIN
        and motif_events == 0
        and chain_shift_abs < QUIET_CHAIN_SHIFT
    ):
        trend = "stabilizing"
    elif DESTABILIZING_MAX <= stability_score <= STABILIZING_MIN and motif_events > 0:
        trend = "transitioning"
    else:
        trend = "steady"

    # --- drivers ------------------------------------------------------------
    curr_chain_sigs = _chain_signatures(curr.get("chains"))
    drivers = {
        "rising_influence": sorted(n for n, d in influence_delta.items() if d > DRIVER_RISE),
        "falling_influence": sorted(n for n, d in influence_delta.items() if d < DRIVER_FALL),
        "new_bottlenecks": sorted(new_bottlenecks),
        "resolved_bottlenecks": sorted(resolved_bottlenecks),
        "new_loops": sorted(list(loop) for loop in new_loops),
        "resolved_loops": sorted(list(loop) for loop in resolved_loops),
        # 8.6 exposes only the aggregate chain score_shift (no per-chain deltas),
        # so the current chain set is listed as strengthening / weakening when
        # that shift crosses the ±0.1 driver threshold.
        "chain_strengthening": curr_chain_sigs if score_shift > DRIVER_RISE else [],
        "chain_weakening": curr_chain_sigs if score_shift < DRIVER_FALL else [],
    }

    return {"stability_score": stability_score, "trend": trend, "drivers": drivers}
