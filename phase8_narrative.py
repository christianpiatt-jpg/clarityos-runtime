# phase8_narrative.py
"""
Phase 8.9 — Unified Causal Narrative (the Phase-8 narrative layer).

The causal counterpart to the Phase-7 narrative (7.9), but structural and
multi-layered: it weaves the strongest causal chain, the structural motifs, the
influence highlights, the temporal deltas, and the stability forecast into one
deterministic, text-only operator-grade explanation.

    generate_causal_narrative(curr, deltas, stability) -> str

``curr`` is the current causal state (``{influence, centrality, motifs,
chains}``); ``deltas`` is the 8.6 output; ``stability`` is the 8.7 output. The
output is a fixed-section template — no generative prose, no inference beyond the
template, every list sorted, every number formatted to two decimals.

Pure / deterministic: no I/O, wall-clock, randomness, or side effects. Imports
only the stdlib — nothing from the CI-gated runtime spine, vault, or
operator_state.

See ``phase8_spec.md`` ("Phase 8.9 — Unified Causal Narrative").
"""

# Order + display labels for the stability-driver count summary.
_DRIVER_SUMMARY = (
    ("rising_influence", "rising influence"),
    ("falling_influence", "falling influence"),
    ("new_bottlenecks", "new bottlenecks"),
    ("resolved_bottlenecks", "resolved bottlenecks"),
    ("new_loops", "new loops"),
    ("resolved_loops", "resolved loops"),
    ("chain_strengthening", "chain strengthening"),
    ("chain_weakening", "chain weakening"),
)


def _fmt(value) -> str:
    """A numeric value formatted to two decimals (``0.00`` when unparseable)."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _join_ids(ids) -> str:
    """Sorted, comma-joined node ids, or ``"none"`` when empty."""
    rendered = sorted(str(i) for i in (ids or []))
    return ", ".join(rendered) if rendered else "none"


def _join_sequences(sequences) -> str:
    """Sorted node-id sequences rendered ``"a → b; c → d"``, or ``"none"`` when
    empty. Used for feedback loops and chain signatures (lists of node ids)."""
    rendered = sorted(" → ".join(str(n) for n in seq) for seq in (sequences or []))
    return "; ".join(rendered) if rendered else "none"


def generate_causal_narrative(curr: dict, deltas: dict, stability: dict) -> str:
    """Synthesize the deterministic Phase-8 causal narrative.

    Sections: Primary Causal Chain (strongest chain's node labels + score),
    Structural Motifs (loops / bottlenecks / attractors), Influence Highlights
    (rising / falling), Causal Changes Since Last Snapshot (new / resolved
    motifs + chain score shift), and Stability Forecast (score / trend / driver
    counts). Missing inputs degrade to ``"none"`` / ``(no causal chain
    detected)`` / a ``steady`` 0.00 forecast.
    """
    curr = curr or {}
    deltas = deltas or {}
    stability = stability or {}

    # --- Primary causal chain (8.4 sorts chains by score desc → strongest first).
    chains = curr.get("chains") or []
    if chains:
        primary = chains[0]
        labels = [
            str(node.get("label", node.get("id", "")))
            for node in (primary.get("nodes") or [])
        ]
        chain_line = " → ".join(labels) if labels else "(no nodes)"
        chain_score = _fmt(primary.get("score", 0.0))
    else:
        chain_line = "(no causal chain detected)"
        chain_score = "0.00"

    # --- Structural motifs (current state).
    motifs = curr.get("motifs") or {}
    loops = _join_sequences(motifs.get("feedback_loops"))
    bottlenecks = _join_ids(motifs.get("bottlenecks"))
    attractors = _join_ids(motifs.get("attractors"))

    # --- Influence highlights (the 8.7 rising / falling drivers).
    drivers = stability.get("drivers") or {}
    rising = _join_ids(drivers.get("rising_influence"))
    falling = _join_ids(drivers.get("falling_influence"))

    # --- Causal changes since the previous snapshot (8.6 deltas).
    motif_delta = deltas.get("motif_delta") or {}
    new_motifs = (
        f"loops: {_join_sequences(motif_delta.get('new_loops'))}; "
        f"bottlenecks: {_join_ids(motif_delta.get('new_bottlenecks'))}; "
        f"attractors: {_join_ids(motif_delta.get('new_attractors'))}"
    )
    resolved_motifs = (
        f"loops: {_join_sequences(motif_delta.get('resolved_loops'))}; "
        f"bottlenecks: {_join_ids(motif_delta.get('resolved_bottlenecks'))}; "
        f"attractors: {_join_ids(motif_delta.get('resolved_attractors'))}"
    )
    chain_delta = deltas.get("chain_delta") or {}
    score_shift = _fmt(chain_delta.get("score_shift", 0.0))

    # --- Stability forecast (8.7).
    stability_score = _fmt(stability.get("stability_score", 0.0))
    trend = str(stability.get("trend", "steady"))
    driver_summary = ", ".join(
        f"{label} ({len(drivers.get(key) or [])})" for key, label in _DRIVER_SUMMARY
    )

    return "\n".join([
        "Primary Causal Chain:",
        f"- {chain_line}",
        f"- Chain score: {chain_score}",
        "",
        "Structural Motifs:",
        f"- Feedback loops: {loops}",
        f"- Bottlenecks: {bottlenecks}",
        f"- Attractors: {attractors}",
        "",
        "Influence Highlights:",
        f"- Rising: {rising}",
        f"- Falling: {falling}",
        "",
        "Causal Changes Since Last Snapshot:",
        f"- New motifs: {new_motifs}",
        f"- Resolved motifs: {resolved_motifs}",
        f"- Chain score shift: {score_shift}",
        "",
        "Stability Forecast:",
        f"- Score: {stability_score}",
        f"- Trend: {trend}",
        f"- Drivers: {driver_summary}",
    ])
