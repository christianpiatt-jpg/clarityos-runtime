# engine_orchestrator.py
# Unified orchestrator for local engines + HTTP engines (Markoff, Clarity)

import importlib
import pkgutil
import json
import os
import requests


# ------------------------------------------------------------
#  HTTP ENGINE ADAPTER
# ------------------------------------------------------------

class HTTPEngineAdapter:
    """
    Wraps an HTTP engine endpoint (e.g., Markoff or Clarity).
    Expects POST <url> with JSON: { "text": "...", "meta": {...} }
    """

    def __init__(self, name, url, timeout=5):
        self.name = name
        self.url = url
        self.timeout = timeout

    def handle(self, text):
        try:
            payload = {"text": text, "meta": {}}
            resp = requests.post(self.url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            return {
                "engine": self.name,
                "error": f"HTTP engine failure: {e}",
                "url": self.url
            }


# ------------------------------------------------------------
#  ENGINE ORCHESTRATOR
# ------------------------------------------------------------

class EngineOrchestrator:
    """
    Loads:
      - Local Python engines from 04_Operator/engines/
      - HTTP engines from clarity_services.json
    Provides:
      - list_engines()
      - dispatch(verb, payload)
    """

    def __init__(self):
        self.engines = {}

        # Load local Python engines
        self._load_local_engines()

        # Load HTTP engines from service discovery
        self._load_http_engines()

    # --------------------------------------------------------
    #  LOCAL ENGINE LOADING
    # --------------------------------------------------------

    def _load_local_engines(self):
        """
        Loads Python modules from engines/ and registers them.
        """
        try:
            import engines as engines_pkg
        except ImportError:
            return

        pkg_path = engines_pkg.__path__

        for finder, name, ispkg in pkgutil.iter_modules(pkg_path):
            module_full = f"engines.{name}"
            try:
                module = importlib.import_module(module_full)

                # Preferred: module.register(orchestrator)
                if hasattr(module, "register"):
                    module.register(self)

                # Fallback: module.Engine class
                elif hasattr(module, "Engine"):
                    self.engines[name] = module.Engine()

                # Last resort: store module reference
                else:
                    self.engines[name] = module

            except Exception:
                # Silent fail to avoid breaking boot
                pass

    # --------------------------------------------------------
    #  HTTP ENGINE LOADING
    # --------------------------------------------------------

    def _load_http_engines(self):
        """
        Reads clarity_services.json and registers HTTP engines.
        """
        os_root = os.path.dirname(os.path.dirname(__file__))
        config_path = os.path.join(os_root, "clarity_services.json")

        if not os.path.exists(config_path):
            return

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        engines = data.get("engines", [])
        for entry in engines:
            if entry.get("type") == "http":
                name = entry.get("name")
                url = entry.get("url")
                if name and url:
                    self.engines[name] = HTTPEngineAdapter(name, url)

    # --------------------------------------------------------
    #  PUBLIC API
    # --------------------------------------------------------

    def register_engine(self, name, obj):
        """Register a local engine or adapter."""
        self.engines[name] = obj

    def list_engines(self):
        """Return list of engine names."""
        return list(self.engines.keys())

    def dispatch(self, verb, payload):
        """
        Dispatch a verb to the appropriate engine.
        For now:
          - 'cloud' → example_engine (legacy)
          - 'markoff' → markoff engine
          - 'clarity' → clarity engine
        """
        # Legacy cloud verb
        if verb == "cloud":
            engine = self.engines.get("example_engine")
            if engine and hasattr(engine, "handle"):
                return engine.handle(payload)
            return {"error": "No cloud engine available"}

        # Direct engine calls
        if verb in self.engines:
            engine = self.engines[verb]
            if hasattr(engine, "handle"):
                return engine.handle(payload)
            return {"error": f"Engine '{verb}' has no handle() method"}

        return {"error": f"Unknown verb '{verb}'"}
