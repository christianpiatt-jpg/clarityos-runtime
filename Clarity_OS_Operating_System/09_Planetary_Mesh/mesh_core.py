# 09_Planetary_Mesh/mesh_core.py

from typing import Dict, Any
from .mesh_state import MeshState


class PlanetaryMesh:
    """
    Core Planetary Mesh engine.
    Responsible for:
    - node/basin registry
    - global flow mapping
    - hydronic overlays
    - structural memory hooks
    """

    def __init__(self, memory_layer=None, hydronic_layer=None):
        self.state = MeshState()
        self.memory_layer = memory_layer
        self.hydronic_layer = hydronic_layer
        self.basins: Dict[str, Dict[str, Any]] = {}
        self.active = False

    def register_basin(self, basin_id: str, meta: Dict[str, Any]) -> None:
        self.basins[basin_id] = meta

    def activate(self) -> None:
        self.active = True

    def is_active(self) -> bool:
        return self.active

    def update_from_hydronic(self) -> None:
        if not self.hydronic_layer:
            return
        # placeholder: pull hydronic data into mesh state
        hydronic_snapshot = self.hydronic_layer.snapshot()
        self.state.cross_basin_pressure_map = hydronic_snapshot.get(
            "pressure_map", {}
        )
        self.state.hydronic_fronts = hydronic_snapshot.get("fronts", [])

    def write_to_memory(self) -> None:
        if not self.memory_layer:
            return
        self.memory_layer.store_mesh_snapshot(self.state.snapshot())
