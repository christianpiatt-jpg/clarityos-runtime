# phase8_unified_narrative.py
"""
Phase 8.10 — Unified Temporal-Causal Narrative (Phase-7 + Phase-8 integration).

The synthesis layer: Phase 7 explained *what happened over time* (drift,
coherence, trust, the temporal narrative); Phase 8 explained *why, structurally*
(graph, motifs, chains, deltas, stability, the causal narrative). 8.10 fuses both
into one deterministic, operator-grade explanation — the operator's one-stop read
of the system's state.

    generate_unified_narrative(temporal, causal) -> str

``temporal`` and ``causal`` are structured *blocks* (dicts) bundling each phase's
narrative + the values the Integrated Interpretation needs:

    temporal = {"narrative": str,            # Phase 7.9 narrative
                "drift": float | None,        # latest record drift level
                "coherence_trend": float,     # Phase 7.3 analytics
                "trust_band": str | None}     # latest record trust band
    causal   = {"narrative": str,            # Phase 8.9 causal narrative
                "chains": [...],              # Phase 8.4 chains (strongest first)
                "motifs": {...},              # Phase 8.3 motifs
                "deltas": {...},              # Phase 8.6 deltas
                "stability": {...}}           # Phase 8.7 stability forecast

No generative prose, no inference beyond the template, no randomness, no
wall-clock; all lists sorted, all numbers formatted to two decimals; missing
pieces degrade to labelled placeholders.

Pure / deterministic: no I/O, side effects, or imports beyond the stdlib —
nothing from the CI-gated runtime spine, vault, or operator_state.

See ``phase8_spec.md`` ("Phase 8.10 — Unified Temporal-Causal Narrative").
"""

TITLE = "Unified Temporal–Causal Narrative"

_MOTIF_FAMILIES = (
    "new_loops", "resolved_loops", "new_bottlenecks",
    "resolved_bottlenecks", "new_attractors", "resolved_attractors",
)


def _fmt(value) -> str:
    """Two-decimal format; ``None`` / unparseable → ``0.00``."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _join_ids(ids) -> str:
    rendered = sorted(str(i) for i in (ids or []))
    return ", ".join(rendered) if rendered else "none"


def _join_sequences(sequences) -> str:
    rendered = sorted(" → ".join(str(n) for n in seq) for seq in (sequences or []))
    return "; ".join(rendered) if rendered else "none"


def _primary_chain(chains) -> str:
    """Node labels of the strongest chain (8.4 sorts chains by score desc), or a
    placeholder when there are none."""
    chains = chains or []
    if not chains:
        return "(none)"
    labels = [str(n.get("label", n.get("id", ""))) for n in (chains[0].get("nodes") or [])]
    return " → ".join(labels) if labels else "(none)"


def _motif_summary(motifs) -> str:
    motifs = motifs or {}
    return (
        f"loops: {_join_sequences(motifs.get('feedback_loops'))}; "
        f"bottlenecks: {_join_ids(motifs.get('bottlenecks'))}; "
        f"attractors: {_join_ids(motifs.get('attractors'))}"
    )


def _delta_summary(deltas) -> str:
    deltas = deltas or {}
    influence_changes = sum(1 for v in (deltas.get("influence_delta") or {}).values() if v != 0.0)
    centrality_changes = sum(1 for v in (deltas.get("centrality_delta") or {}).values() if v != 0.0)
    motif_delta = deltas.get("motif_delta") or {}
    motif_events = sum(len(motif_delta.get(k) or []) for k in _MOTIF_FAMILIES)
    score_shift = _fmt((deltas.get("chain_delta") or {}).get("score_shift", 0.0))
    return (
        f"influence changes: {influence_changes}, centrality changes: {centrality_changes}, "
        f"motif events: {motif_events}, chain score shift: {score_shift}"
    )


def _overall_assessment(drift: float, stability_score: float, motif_delta: dict) -> str:
    """Deterministic system-state classification.

    Precedence (most severe / most specific first, since the card's rules
    overlap): Destabilizing → Stable → Transitioning → Shifting (default).
    """
    motif_delta = motif_delta or {}
    new_loops = motif_delta.get("new_loops") or []
    new_bottlenecks = motif_delta.get("new_bottlenecks") or []
    new_attractors = motif_delta.get("new_attractors") or []
    motif_events = sum(len(motif_delta.get(k) or []) for k in _MOTIF_FAMILIES)
    no_new_motifs = not (new_loops or new_bottlenecks or new_attractors)

    if drift > 0.6 or len(new_loops) > 0 or len(new_bottlenecks) > 0 or stability_score < 0.4:
        return "Destabilizing"
    if drift < 0.3 and stability_score > 0.7 and no_new_motifs:
        return "Stable"
    if motif_events > 0 and 0.4 <= stability_score <= 0.7:
        return "Transitioning"
    # 0.3 ≤ drift ≤ 0.6 OR 0.4 ≤ stability_score ≤ 0.7, and everything else.
    return "Shifting"


def generate_unified_narrative(temporal: dict, causal: dict) -> str:
    """Fuse the Phase-7 temporal block and the Phase-8 causal block into one
    deterministic narrative (Temporal Summary + Causal Summary + Integrated
    Interpretation + Overall Assessment). Output is JSON-serialisable (a string).
    """
    temporal = temporal or {}
    causal = causal or {}

    temporal_text = (temporal.get("narrative") or "").strip() or "(no temporal narrative)"
    causal_text = (causal.get("narrative") or "").strip() or "(no causal narrative)"

    drift_raw = temporal.get("drift")
    drift_value = float(drift_raw) if isinstance(drift_raw, (int, float)) else 0.0
    stability = causal.get("stability") or {}
    stability_score_raw = stability.get("stability_score", 0.0)
    stability_score = float(stability_score_raw) if isinstance(stability_score_raw, (int, float)) else 0.0
    deltas = causal.get("deltas") or {}

    interpretation = [
        f"- Drift level: {_fmt(drift_raw)}",
        f"- Coherence trend: {_fmt(temporal.get('coherence_trend', 0.0))}",
        f"- Trust band: {temporal.get('trust_band') or '—'}",
        f"- Primary causal chain: {_primary_chain(causal.get('chains'))}",
        f"- Structural motifs: {_motif_summary(causal.get('motifs'))}",
        f"- Key deltas: {_delta_summary(deltas)}",
        f"- Stability forecast: {stability.get('trend', 'steady')} (score {_fmt(stability_score_raw)})",
    ]
    assessment = _overall_assessment(drift_value, stability_score, deltas.get("motif_delta"))

    return "\n".join([
        TITLE,
        "",
        "Temporal Summary:",
        temporal_text,
        "",
        "Causal Summary:",
        causal_text,
        "",
        "Integrated Interpretation:",
        *interpretation,
        "",
        "Overall Assessment:",
        assessment,
    ])
