from OS_Modules.Engine_Orchestrator.orchestrator import EngineOrchestrator
from OS_Modules.Scheduler.scheduler import ClarityScheduler


class ManifoldBinding:
    """
    v3 Manifold Binding Layer
    -------------------------
    Connects:
      - GlobalManifold
      - EngineOrchestrator
      - ClarityScheduler

    Responsibilities:
      - Attach orchestrator to manifold
      - Attach scheduler to orchestrator
      - Provide orchestrator access to manifold
      - Provide manifold access to orchestrator
    """

    def __init__(self, manifold):
        self.manifold = manifold

        # Create orchestrator
        self.orchestrator = EngineOrchestrator()

        # Create scheduler
        self.scheduler = ClarityScheduler(self.orchestrator)

        # Bind manifold → binding
        self.manifold.bind(self)

        # Bind orchestrator → manifold
        self.orchestrator.manifold = self.manifold

    def status(self):
        return {
            "orchestrator": list(self.orchestrator.registry.keys()),
            "scheduler_running": self.scheduler.running,
        }