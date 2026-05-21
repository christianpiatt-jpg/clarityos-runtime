"""
ClarityOS Kernel Entrypoint — get_os()

Provides a singleton OS object that:
- wraps the EngineOrchestrator
- exposes shared subsystems used by engines and the console:
  library, narrative, analytics, elins, mesh, memory, global_arc, hydronic_maps

Design goals:
- Try to import real subsystem implementations by conventional package names.
- If missing, provide minimal stubs so the runtime remains functional and testable.
- Keep the API small and consistent so engines call through a single kernel interface.

Usage:
    from clarity_engine.kernel import get_os
    os = get_os()
    os.library.query("...")        # if implemented
    os.narrative.run("...")        # if implemented
    os.analytics.analyze("...")    # if implemented
    os.elins.run("...")            # if implemented
    os.orchestrator.list_engines()
"""

from typing import Any, Dict

# Orchestrator import (package-qualified)
try:
    from OS_Modules.Engine_Orchestrator.orchestrator import EngineOrchestrator
except Exception as e:
    raise ImportError(
        "Failed to import EngineOrchestrator from OS_Modules.Engine_Orchestrator.orchestrator: "
        f"{e}"
    )

def _import_module(name: str):
    try:
        module = __import__(name, fromlist=["*"])
        return module
    except Exception:
        return None

class _LibraryStub:
    def __init__(self):
        self._index = {}

    def query(self, q: str) -> Dict[str, Any]:
        return {"query": q, "results": [], "note": "library stub"}

    def add(self, key: str, obj: Any):
        self._index[key] = obj
        return True

class _NarrativeStub:
    def run(self, text: str) -> Dict[str, Any]:
        summary = text[:240] + ("…" if len(text) > 240 else "")
        return {"summary": summary, "structure": [], "note": "narrative stub"}

class _AnalyticsStub:
    def analyze(self, text: str) -> Dict[str, Any]:
        tokens = text.split()
        return {"tokens": len(tokens), "length": len(text), "note": "analytics stub"}

class _ELINSStub:
    def run(self, text: str) -> Dict[str, Any]:
        return {"elins": [], "source": text, "note": "elins stub"}

class _MeshStub:
    def query(self, q: str) -> Dict[str, Any]:
        return {"query": q, "nodes": [], "note": "mesh stub"}

class _MemoryStub:
    def get(self, key: str) -> Any:
        return None

    def put(self, key: str, value: Any) -> bool:
        return True

class _GlobalArcStub:
    def consult(self, text: str) -> Dict[str, Any]:
        return {"arc": [], "note": "global arc stub"}

class _HydronicMapsStub:
    def lookup(self, q: str) -> Dict[str, Any]:
        return {"map": {}, "note": "hydronic maps stub"}

_library_mod = _import_module("clarity_library")
_narrative_mod = _import_module("narrative_arch")
_analytics_mod = _import_module("analytics")
_elins_mod = _import_module("elins")
_mesh_mod = _import_module("va_mesh")
_memory_mod = _import_module("structural_memory")
_global_arc_mod = _import_module("global_arc")
_hydronic_mod = _import_module("hydronic_maps")

def _instantiate_subsystem(mod, attr_candidates, stub_cls):
    if not mod:
        return stub_cls()
    for attr in attr_candidates:
        obj = getattr(mod, attr, None)
        if obj:
            try:
                if callable(obj):
                    instance = obj() if not isinstance(obj, type) else obj()
                else:
                    instance = obj
                return instance
            except Exception:
                continue
    return stub_cls()

_library = _instantiate_subsystem(_library_mod, ["Library", "get_library", "create_library"], _LibraryStub)
_narrative = _instantiate_subsystem(_narrative_mod, ["Narrative", "get_narrative", "NarrativeEngine"], _NarrativeStub)
_analytics = _instantiate_subsystem(_analytics_mod, ["Analytics", "get_analytics", "Analyzer"], _AnalyticsStub)
_elins = _instantiate_subsystem(_elins_mod, ["ELINS", "get_elins", "ElinsEngine"], _ELINSStub)
_mesh = _instantiate_subsystem(_mesh_mod, ["Mesh", "get_mesh", "VAMesh"], _MeshStub)
_memory = _instantiate_subsystem(_memory_mod, ["Memory", "get_memory", "StructuralMemory"], _MemoryStub)
_global_arc = _instantiate_subsystem(_global_arc_mod, ["GlobalArc", "get_global_arc"], _GlobalArcStub)
_hydronic = _instantiate_subsystem(_hydronic_mod, ["HydronicMaps", "get_hydronic_maps"], _HydronicMapsStub)

class ClarityOS:
    def __init__(self):
        self.orchestrator = EngineOrchestrator()
        self.library = _library
        self.narrative = _narrative
        self.analytics = _analytics
        self.elins = _elins
        self.mesh = _mesh
        self.memory = _memory
        self.global_arc = _global_arc
        self.hydronic_maps = _hydronic
        self._diagnostics = {"status": "ok", "notes": []}

    def run_narrative(self, text: str) -> Dict[str, Any]:
        return self.narrative.run(text)

    def analyze(self, text: str) -> Dict[str, Any]:
        return self.analytics.analyze(text)

    def run_elins(self, text: str) -> Dict[str, Any]:
        return self.elins.run(text)

    def query_library(self, q: str) -> Dict[str, Any]:
        return self.library.query(q)

    def health(self) -> Dict[str, Any]:
        def _is_stub(obj, stub_cls):
            return isinstance(obj, stub_cls)

        return {
            "orchestrator": type(self.orchestrator).__name__,
            "library_real": not _is_stub(self.library, _LibraryStub),
            "narrative_real": not _is_stub(self.narrative, _NarrativeStub),
            "analytics_real": not _is_stub(self.analytics, _AnalyticsStub),
            "elins_real": not _is_stub(self.elins, _ELINSStub),
            "mesh_real": not _is_stub(self.mesh, _MeshStub),
            "memory_real": not _is_stub(self.memory, _MemoryStub),
            "global_arc_real": not _is_stub(self.global_arc, _GlobalArcStub),
            "hydronic_maps_real": not _is_stub(self.hydronic_maps, _HydronicMapsStub),
            "notes": self._diagnostics,
        }

_os_instance: ClarityOS = None

def get_os() -> ClarityOS:
    global _os_instance
    if _os_instance is None:
        _os_instance = ClarityOS()
    return _os_instance

def get_orchestrator() -> EngineOrchestrator:
    return get_os().orchestrator
