# super_integration.py
from typing import Dict

from phase6_contracts import SuperIntegrationState, SuperPatternState
from super_pattern import _score_keywords


def compute_super_integration(
    sp: SuperPatternState,
    meta: Dict[str, str],
) -> SuperIntegrationState:
    all_text = " ".join(meta.values()).lower()

    integration_strength = _score_keywords(
        all_text,
        positives=["integrated", "integration", "unified", "joined"],
        negatives=["disjoint", "siloed", "separate"],
    )

    cross_layer_alignment = _score_keywords(
        all_text,
        positives=["aligned", "alignment", "coherent", "consistent"],
        negatives=["misaligned", "inconsistent", "conflicting"],
    )

    # bias integration_strength upward if pattern_strength is high
    integration_strength = max(
        0.0,
        min(1.0, (integration_strength + sp.pattern_strength) / 2.0),
    )

    integration_identity = f"int-{integration_strength:.2f}-align-{cross_layer_alignment:.2f}"

    return SuperIntegrationState(
        integration_strength=integration_strength,
        cross_layer_alignment=cross_layer_alignment,
        integration_identity=integration_identity,
    )
