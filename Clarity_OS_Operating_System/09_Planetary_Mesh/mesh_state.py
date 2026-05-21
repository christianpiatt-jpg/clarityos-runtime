# 09_Planetary_Mesh/mesh_state.py

from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class MeshState:
    """Planetary Mesh state vector."""
    global_state_vector: Dict[str, Any] = field(default_factory=dict)
    cross_basin_pressure_map: Dict[str, float] = field(default_factory=dict)
    hydronic_fronts: List[Dict[str, Any]] = field(default_factory=list)
    planetary_curvature: float = 0.0
    systemic_risk_score: float = 0.0
    anomalies: List[Dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "global_state_vector": self.global_state_vector,
            "cross_basin_pressure_map": self.cross_basin_pressure_map,
            "hydronic_fronts": self.hydronic_fronts,
            "planetary_curvature": self.planetary_curvature,
            "systemic_risk_score": self.systemic_risk_score,
            "anomalies": self.anomalies,
        }
