import threading
import time


class ClarityScheduler:
    """
    v3 Scheduler
    ------------
    Runs the orchestrator heartbeat every `interval_hours`.
    """

    def __init__(self, orchestrator, interval_hours=1.0):
        self.orchestrator = orchestrator
        self.interval_hours = interval_hours
        self.interval = interval_hours * 3600  # convert hours → seconds
        self.running = False
        self.thread = None

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.running:
            try:
                self.orchestrator.heartbeat()
            except Exception as e:
                print(f"[Scheduler] Heartbeat error: {e}")
            time.sleep(self.interval)

    def stop(self):
        self.running = False

    def status(self):
        return {
            "interval_hours": self.interval_hours,
            "engines": list(self.orchestrator.registry.keys()),
            "running": self.running,
        }