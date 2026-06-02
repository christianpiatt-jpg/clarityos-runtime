# super_coherence.py
from typing import Dict

from phase6_contracts import SuperCoherenceState, SuperIntegrationState, SuperPatternState
from super_pattern import _score_keywords


def compute_super_coherence(
    sp: SuperPatternState,
    si: SuperIntegrationState,
    meta: Dict[str, str],
) -> SuperCoherenceState:
    all_text = " ".join(meta.values()).lower()

    coherence_level = _score_keywords(
        all_text,
        positives=["coherent", "coherence", "consistent", "aligned"],
        negatives=["incoherent", "inconsistent", "fragmented"],
    )

    drift_resistance = _score_keywords(
        all_text,
        positives=["stable", "stability", "anchored", "robust"],
        negatives=["drift", "drifting", "unstable"],
    )

    load_resilience = _score_keywords(
        all_text,
        positives=["resilient", "resilience", "under load", "high load"],
        negatives=["brittle", "fragile", "fails under load"],
    )

    # incorporate upstream signals
    coherence_level = max(
        0.0,
        min(1.0, (coherence_level + sp.pattern_coherence + si.integration_strength) / 3.0),
    )

    coherence_identity = (
        f"coh-{coherence_level:.2f}-drift-{drift_resistance:.2f}-load-{load_resilience:.2f}"
    )

    return SuperCoherenceState(
        coherence_level=coherence_level,
        drift_resistance=drift_resistance,
        load_resilience=load_resilience,
        coherence_identity=coherence_identity,
    )
