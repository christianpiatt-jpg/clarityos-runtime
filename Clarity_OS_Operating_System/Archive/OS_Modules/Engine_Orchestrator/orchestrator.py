from engine.markoff_core import MarkoffModel
from OS_Modules.Engine_Orchestrator.module_map import MODULE_NAME_MAP

from OS_Modules.Engine_Orchestrator.modules.Engine_Endpoint import EngineEndpoint
from OS_Modules.Engine_Orchestrator.modules.Executive_Tiers import ExecutiveTiers
from OS_Modules.Engine_Orchestrator.modules.Subscription_Flow import SubscriptionFlow
from OS_Modules.Engine_Orchestrator.modules.Login_Token import LoginToken
from OS_Modules.Engine_Orchestrator.modules.Pricing_Matrix import PricingMatrix
from OS_Modules.Engine_Orchestrator.modules.Institutional_Contracts import InstitutionalContracts
from OS_Modules.Engine_Orchestrator.modules.Multilingual import Multilingual


class EngineOrchestrator:
    """
    v3 Engine Orchestrator
    ----------------------
    - Holds engine registry
    - Runs engines on demand
    - Provides heartbeat for scheduler
    - Connects to manifold (set by ManifoldBinding)
    """

    def __init__(self):
        self.registry = {}
        self.manifold = None  # Set by ManifoldBinding

        # Register Markoff engine
        try:
            self.registry["markoff"] = MarkoffModel()
        except Exception as e:
            print(f"[Orchestrator] Failed to load Markoff engine: {e}")

        # Register v3 modules
        try:
            self.registry["Engine_Endpoint"] = EngineEndpoint()
            self.registry["Executive_Tiers"] = ExecutiveTiers()
            self.registry["Subscription_Flow"] = SubscriptionFlow()
            self.registry["Login_Token"] = LoginToken()
            self.registry["Pricing_Matrix"] = PricingMatrix()
            self.registry["Institutional_Contracts"] = InstitutionalContracts()
            self.registry["Multilingual"] = Multilingual()
        except Exception as e:
            print(f"[Orchestrator] Failed to load v3 modules: {e}")

    def run(self, engine_name, payload):
        """
        Execute an engine/module with the given payload.
        """
        key = MODULE_NAME_MAP.get(engine_name, engine_name)
        engine = self.registry.get(key)

        if not engine:
            return {"error": f"Engine '{engine_name}' not found"}

        try:
            return engine.run(payload)
        except Exception as e:
            return {"error": f"Engine execution failed: {e}"}

    def heartbeat(self):
        """
        Called by the scheduler every interval.
        """
        return True

    def diagnose_all(self):
        """
        Run diagnostics on every registered engine/module.
        """
        report = {}
        for name, engine in self.registry.items():
            if hasattr(engine, "diagnose"):
                try:
                    report[name] = engine.diagnose()
                except Exception as e:
                    report[name] = {"error": f"Diagnostic failure: {e}"}
            else:
                report[name] = {"error": "No diagnostic interface"}
        return report

    def diagnose_os(self):
        """
        Return OS-level diagnostic information.
        """
        return {
            "orchestrator": "online",
            "registered_engines": list(self.registry.keys()),
            "manifold_bound": self.manifold is not None,
            "scheduler_interval_hours": getattr(self, "scheduler_interval_hours", None),
            "manifold_state": {
                "drift": getattr(self.manifold, "drift", []),
                "basins": getattr(self.manifold, "basins", []),
                "pressure": getattr(self.manifold, "pressure", []),
                "temporal": getattr(self.manifold, "temporal", []),
            } if self.manifold else None,
        }

    def diagnose_markoff(self):
        """
        Return Markoff engine diagnostic information.
        """
        engine = self.registry.get("markoff")
        if not engine:
            return {"error": "Markoff engine not found"}

        try:
            return {
                "engine": "markoff",
                "transition_count": engine.transition_count,
                "vocabulary_size": len(engine.transitions),
                "ready": True,
            }
        except Exception as e:
            return {"error": f"Markoff diagnostic failure: {e}"}