# 09_Planetary_Mesh/mesh_diagnostics.py

from typing import Dict, Any
from .mesh_state import MeshState


class MeshDiagnostics:
    """Planetary-level diagnostics for the mesh."""

    def __init__(self, state: MeshState):
        self.state = state

    def global_diagnostics(self) -> Dict[str, Any]:
        # This is what Markoff will call
        return self.state.snapshot()

    def systemic_risk(self) -> float:
        return self.state.systemic_risk_score
