# 09_Planetary_Mesh/mesh_router.py

from typing import Dict, Any, Optional
from .mesh_core import PlanetaryMesh
from .mesh_diagnostics import MeshDiagnostics


class MeshRouter:
    """
    Routing layer for the Planetary Mesh.
    - binds Markoff
    - exposes global diagnostics
    - handles cross-basin routing
    """

    def __init__(self, mesh: PlanetaryMesh, markoff_engine: Optional[object] = None):
        self.mesh = mesh
        self.diagnostics = MeshDiagnostics(mesh.state)
        self.markoff_engine = markoff_engine

    def bind_markoff(self, engine: object) -> None:
        self.markoff_engine = engine

    def activate_mesh(self) -> None:
        self.mesh.activate()
        self.mesh.update_from_hydronic()
        self.mesh.write_to_memory()

    def mesh_status(self) -> Dict[str, Any]:
        return {
            "MeshActive": self.mesh.is_active(),
            "BasinsRegistered": list(self.mesh.basins.keys()),
        }

    def global_diag(self) -> Dict[str, Any]:
        return self.diagnostics.global_diagnostics()
