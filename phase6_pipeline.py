# phase6_pipeline.py
from typing import Dict

from phase6_contracts import SuperstructureState
from super_pattern import compute_super_pattern
from super_integration import compute_super_integration
from super_coherence import compute_super_coherence
from super_essence import compute_super_essence
from super_identity import compute_super_identity


def run_superstructure(meta: Dict[str, str]) -> SuperstructureState:
    sp = compute_super_pattern(meta)
    si = compute_super_integration(sp, meta)
    sc = compute_super_coherence(sp, si, meta)
    se = compute_super_essence(sp, si, sc, meta)
    sid = compute_super_identity(sp, si, sc, se, meta)
    return SuperstructureState(
        pattern=sp,
        integration=si,
        coherence=sc,
        essence=se,
        identity=sid,
    )
