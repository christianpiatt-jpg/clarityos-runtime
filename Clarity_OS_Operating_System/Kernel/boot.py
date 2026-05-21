from OS_Modules.manifold.Manifold import GlobalManifold
from OS_Modules.Interfaces.Manifold_Binding import ManifoldBinding


class ClarityOS:
    """
    v3 ClarityOS Kernel Boot
    ------------------------
    Wires:
      - GlobalManifold
      - ManifoldBinding
      - EngineOrchestrator
      - ClarityScheduler
    """

    def __init__(self):
        self.manifold = None
        self.binding = None
        self.orchestrator = None
        self.scheduler = None

    def boot(self):
        # Create manifold
        self.manifold = GlobalManifold()

        # Bind manifold → orchestrator + scheduler
        self.binding = ManifoldBinding(self.manifold)

        # Expose orchestrator and scheduler from binding
        self.orchestrator = self.binding.orchestrator
        self.scheduler = self.binding.scheduler

        # Start scheduler heartbeat
        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()

        return {
            "status": "ClarityOS Online",
            "engines": list(self.orchestrator.registry.keys()),
            "manifold": self.manifold.status(),
            "scheduler_interval_hours": self.scheduler.interval_hours,
        }