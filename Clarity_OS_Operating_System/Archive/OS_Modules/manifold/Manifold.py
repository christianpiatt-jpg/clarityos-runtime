class GlobalManifold:
    """
    v3 Global Manifold
    ------------------
    Minimal, stable, operator-grade manifold implementation.

    Responsibilities:
    - Hold drift / basins / pressure / temporal channels
    - Bind to the ManifoldBinding layer
    - Provide a `.process()` entry point for routing signals
    - Forward signals to the EngineOrchestrator via the binding
    """

    def __init__(self):
        self.drift = []
        self.basins = []
        self.pressure = []
        self.temporal = []
        self.binding = None  # Set by ManifoldBinding

    def bind(self, binding):
        """
        Called by ManifoldBinding to attach orchestrator + scheduler.
        """
        self.binding = binding

    def status(self):
        """
        Returns the current manifold state.
        """
        return {
            "drift": self.drift,
            "basins": self.basins,
            "pressure": self.pressure,
            "temporal": self.temporal,
        }

    def process(self, signal):
        """
        Main routing entry point.
        Accepts a signal dict:
            {
                "engine": "markoff",
                "input": "hello world"
            }

        Returns:
            {
                "engine": "markoff",
                "input": "...",
                "output": <engine output>
            }
        """

        if not self.binding:
            return {"error": "Manifold not bound to orchestrator"}

        engine = signal.get("engine")
        payload = signal.get("input")

        if not engine:
            return {"error": "No engine specified in signal"}

        try:
            orchestrator = self.binding.orchestrator
        except Exception:
            return {"error": "Binding missing orchestrator"}

        if orchestrator is None:
            return {"error": "Orchestrator not initialized"}

        # Orchestrator must have a .run(engine_name, payload) method
        try:
            result = orchestrator.run(engine, payload)
        except Exception as e:
            return {"error": f"Engine routing failed: {e}"}

        return {
            "engine": engine,
            "input": payload,
            "output": result,
        }