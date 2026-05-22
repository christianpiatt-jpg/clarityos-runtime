"""
web_surface_entry.py — Cloud Run entrypoint for the v0.2.0 Web Surface.

This module is the standalone Cloud Run-side entrypoint for the v0.2.0
Web Surface. It is intentionally inert:

  * When ``WEB_SURFACE_V0_2_ENABLED`` is not the explicit string ``"true"``
    (case-insensitive), the returned app has **no routes** — requests
    to any path 404. This is the disabled-by-default contract: even if
    the container is deployed, traffic that hits the surface gets a
    clear "this endpoint does not exist" rather than a 503-style
    "exists but disabled" signal.

  * When the flag is enabled, the existing ``web_surface.router`` (with
    its ``/web-surface/v0.2`` prefix) is included. Every handler still
    returns the 501 ``ErrorEnvelope`` stub from Card 7 — no actual
    behaviour change. The router's own internal flag-guarding becomes
    a defence-in-depth no-op (it always agrees with this outer guard).

Deployment topology (PASS-7 will activate):

    uvicorn web_surface_entry:create_web_surface_app \
        --host 0.0.0.0 --port 8080 \
        --factory

The ``--factory`` flag is required because ``create_web_surface_app``
is a factory function, not a module-level app instance — this lets
us read ``WEB_SURFACE_V0_2_ENABLED`` at startup time per container.

Today nothing actually runs this. The entry module exists so the
Cloud Run topology is defined + import-checkable + test-covered before
the activation card lands.
"""

from __future__ import annotations

import os

from fastapi import FastAPI

import web_surface


WEB_SURFACE_FLAG_ENV = web_surface.WEB_SURFACE_FLAG_ENV


def _flag_enabled() -> bool:
    """Mirror the same flag-parse rule as ``web_surface.is_web_surface_enabled``
    so the outer guard agrees with the inner one. Tightened to require
    the literal ``"true"`` (case-insensitive, whitespace-trimmed) per
    the PASS-4 FIX-P3 precedent on ``CLARITYOS_VAULT_PLAINTEXT``."""
    return os.environ.get(WEB_SURFACE_FLAG_ENV, "").strip().lower() == "true"


def create_web_surface_app() -> FastAPI:
    """Factory for the Cloud Run-side Web Surface FastAPI app.

    Reads the enable flag at call time (not import time) so per-
    container env changes take effect without a code redeploy. When
    disabled the returned app has zero routes; when enabled it carries
    ``web_surface.router`` (and the router's existing 501 stubs).
    """
    app = FastAPI(
        title="ClarityOS Web Surface v0.2.0",
        version=web_surface.WEB_SURFACE_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    if _flag_enabled():
        # Router carries its own ``/web-surface/v0.2`` prefix; mounting
        # it into a fresh sub-app preserves that as the live path.
        app.include_router(web_surface.router)
    # else: app has no routes — any request 404s.

    return app
