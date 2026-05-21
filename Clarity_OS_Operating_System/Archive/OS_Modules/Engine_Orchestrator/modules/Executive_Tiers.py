import os

class ExecutiveTiers:
    def __init__(self):
        # Semantic module folder
        self.module_path = os.path.join(os.getcwd(), "Executive_Tiers")

    def run(self, payload):
        """
        Execute the Executive_Tiers module with the given payload.
        """
        return {
            "module": "Executive_Tiers",
            "status": "ok",
            "payload": payload,
            "module_path": self.module_path,
        }

    def diagnose(self):
        """
        Return diagnostic information for this module.
        """
        return {
            "module": self.__class__.__name__,
            "module_path": self.module_path,
            "path_exists": os.path.exists(self.module_path),
            "metadata_present": os.path.exists(os.path.join(self.module_path, "metadata.txt")),
            "state_present": os.path.exists(os.path.join(self.module_path, "state.json")),
            "status": "ready",
        }