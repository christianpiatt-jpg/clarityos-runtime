"""Schema loader for the v0.2.0 Web Surface JSON contract.

A single, side-effect-free helper that resolves + loads the canonical
schema artifact emitted by ``web/scripts/gen-contract-schema.mjs``.
Used by ``web_surface.py`` (the FastAPI handler) and by the
Python-side roundtrip tests in ``tests/test_web_surface_schema_roundtrip.py``.

Path resolution is anchored at the repo root via ``__file__``, so the
loader works identically whether the runtime is launched from the
repo root, from inside the ``tests/`` directory, or from a Cloud Run
container where the working directory may differ.

The loader is read-only and does no caching — call sites that need
the schema repeatedly can wrap this in their own ``functools.lru_cache``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# Anchor at the repo root so the path survives any caller's CWD.
_REPO_ROOT = Path(__file__).resolve().parent
SCHEMA_PATH: Path = (
    _REPO_ROOT
    / "web"
    / "src"
    / "contracts"
    / "webSurfaceV0_2.schema.json"
)


def load_web_surface_schema() -> dict[str, Any]:
    """Read + parse the v0.2.0 Web Surface JSON Schema.

    Returns the schema as a plain Python dict. Raises ``FileNotFoundError``
    if the artifact is missing (which usually means ``contracts:gen``
    has not been run on the TS side yet).
    """
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
