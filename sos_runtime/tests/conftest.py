"""
SOS Runtime — pytest fixtures.

Sets the test environment BEFORE the FastAPI app loads:
    * SOS_BACKEND=memory       — in-process firestore stub
    * SOS_LLM_MODE=fake        — deterministic echo, no Anthropic call
    * SOS_AUTH_MODE=insecure   — bypass JWT verification

Adds the repo root to sys.path so ``sos_runtime`` imports work when
pytest is invoked from the repo root (matches the existing ClarityOS
``tests/conftest.py`` convention).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# 1. Pin test env BEFORE importing any sos_runtime module. The env
#    vars are read at module-load time by firestore_store / llm /
#    auth, so this has to land first.
os.environ.setdefault("SOS_BACKEND",   "memory")
os.environ.setdefault("SOS_LLM_MODE",  "fake")
os.environ.setdefault("SOS_AUTH_MODE", "insecure")

# 2. Repo-root on sys.path so ``import sos_runtime`` resolves.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest


@pytest.fixture(autouse=True)
def _fresh_store() -> None:
    """Reset the in-memory backend between tests so events / sessions /
    states never leak across cases."""
    from sos_runtime import firestore_store
    firestore_store.reset_for_tests()
    yield
    firestore_store.reset_for_tests()


class _AppClient:
    """Tiny sync client compatible with httpx >=0.28 when the bundled
    starlette TestClient is from a version that still passes ``app=``
    to httpx. Mirrors the workaround in the repo-root conftest so the
    SOS tests don't fight the same starlette/httpx version pin."""

    __test__ = False

    def __init__(self, app) -> None:
        import httpx
        self._httpx = httpx
        self._transport = httpx.ASGITransport(app=app)

    def _run(self, coro):
        import asyncio
        return asyncio.run(coro)

    async def _do(self, method, url, *, json=None, headers=None):
        async with self._httpx.AsyncClient(
            transport=self._transport, base_url="http://testserver",
        ) as ac:
            if method == "GET":
                return await ac.get(url, headers=headers)
            if method == "POST":
                return await ac.post(url, json=json, headers=headers)
            if method == "OPTIONS":
                return await ac.options(url, headers=headers)
            raise ValueError(f"unsupported method {method}")

    def get(self, url, headers=None):
        return self._run(self._do("GET", url, headers=headers))

    def post(self, url, json=None, headers=None):
        return self._run(self._do("POST", url, json=json, headers=headers))

    def options(self, url, headers=None):
        return self._run(self._do("OPTIONS", url, headers=headers))


@pytest.fixture
def client():
    """Sync httpx-ASGI client bound to the SOS Runtime app."""
    from sos_runtime.main import app
    return _AppClient(app)
