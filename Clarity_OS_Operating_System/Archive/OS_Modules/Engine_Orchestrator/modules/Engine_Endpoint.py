import os

class EngineEndpoint:
    def __init__(self):
        self.module_path = os.path.join(os.getcwd(), "Engine_Endpoint")

    def run(self, payload):
        return {
            "module": "Engine_Endpoint",
            "status": "ok",
            "payload": payload,
            "module_path": self.module_path,
        }

    def diagnose(self):
        return {
            "module": self.__class__.__name__,
            "module_path": self.module_path,
            "path_exists": os.path.exists(self.module_path),
            "metadata_present": os.path.exists(os.path.join(self.module_path, "metadata.txt")),
            "state_present": os.path.exists(os.path.join(self.module_path, "state.json")),
            "status": "ready",
        }