# super_essence.py
from typing import Dict

from phase6_contracts import SuperCoherenceState, SuperEssenceState, SuperIntegrationState, SuperPatternState
from super_pattern import _score_keywords


def compute_super_essence(
    sp: SuperPatternState,
    si: SuperIntegrationState,
    sc: SuperCoherenceState,
    meta: Dict[str, str],
) -> SuperEssenceState:
    essence_text = meta.get("operatorMetaEssence", "") + " " + " ".join(meta.values())
    essence_text = essence_text.lower()

    essence_signal = _score_keywords(
        essence_text,
        positives=["core", "essence", "invariant", "identity", "irreducible"],
        negatives=["unclear", "vague", "ambiguous"],
    )

    essence_clarity = _score_keywords(
        essence_text,
        positives=["clear", "clarity", "sharp", "defined"],
        negatives=["blurry", "fuzzy", "unclear"],
    )

    # incorporate upstream stability/coherence
    essence_signal = max(
        0.0,
        min(
            1.0,
            (essence_signal + sp.pattern_stability + si.integration_strength + sc.coherence_level)
            / 4.0,
        ),
    )

    invariant_identity = f"stable-{sp.pattern_stability:.2f}-coh-{sc.coherence_level:.2f}"

    return SuperEssenceState(
        essence_signal=essence_signal,
        invariant_identity=invariant_identity,
        essence_clarity=essence_clarity,
    )
