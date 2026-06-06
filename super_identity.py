# super_identity.py
from typing import Dict

from phase6_contracts import (
    SuperCoherenceState,
    SuperEssenceState,
    SuperIdentityState,
    SuperIntegrationState,
    SuperPatternState,
)


def compute_super_identity(
    sp: SuperPatternState,
    si: SuperIntegrationState,
    sc: SuperCoherenceState,
    se: SuperEssenceState,
    meta: Dict[str, str],
) -> SuperIdentityState:
    # aggregate metrics
    identity_strength = max(
        0.0,
        min(
            1.0,
            (
                sp.pattern_strength
                + si.integration_strength
                + sc.coherence_level
                + se.essence_signal
            )
            / 4.0,
        ),
    )

    identity_stability = max(
        0.0,
        min(1.0, (sp.pattern_stability + sc.drift_resistance) / 2.0),
    )

    identity_projection = max(
        0.0,
        min(
            1.0,
            (
                identity_strength
                + identity_stability
                + sc.load_resilience
                + se.essence_clarity
            )
            / 4.0,
        ),
    )

    base_name = meta.get("operatorIdentity", "clarityos-operator").lower()
    operator_identity = f"{base_name}:s{identity_strength:.2f}-c{sc.coherence_level:.2f}"

    return SuperIdentityState(
        operator_identity=operator_identity,
        identity_strength=identity_strength,
        identity_stability=identity_stability,
        identity_projection=identity_projection,
    )
