"""
web_surface.py - v0.2.0 Web Surface handler skeleton.

This module is the entrypoint for the ClarityOS v0.2.0 Web Surface.
It is intentionally a no-op stub at this commit: the router below is
included into the main FastAPI app in `app.py`, but every route returns
a 501 Not Implemented until the v0.2.0 surface is fleshed out.

The surface is mounted under the reserved prefix `/web-surface/v0.2`,
and is additionally guarded by the environment flag
`WEB_SURFACE_V0_2_ENABLED`. When the flag is anything other than the
string "true" (case-insensitive), the surface is wired in but every
request short-circuits to a 503 disabled response. This keeps the
surface inert in production until it is explicitly turned on.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse


WEB_SURFACE_PREFIX = "/web-surface/v0.2"
WEB_SURFACE_FLAG_ENV = "WEB_SURFACE_V0_2_ENABLED"

router = APIRouter(prefix=WEB_SURFACE_PREFIX, tags=["web-surface-v0.2"])


def is_web_surface_enabled() -> bool:
    """Return True iff the v0.2.0 Web Surface is explicitly enabled."""
    return os.environ.get(WEB_SURFACE_FLAG_ENV, "").strip().lower() == "true"


def _disabled_response() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "error": "web_surface_disabled",
            "detail": (
                "Web Surface v0.2.0 is not enabled in this environment. "
                f"Set {WEB_SURFACE_FLAG_ENV}=true to enable."
            ),
        },
    )


def _not_implemented_response(path: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={
            "error": "web_surface_not_implemented",
            "detail": "Web Surface v0.2.0 not implemented yet",
            "path": path,
            "version": "v0.2.0",
        },
    )


async def handle_web_surface(request: Request) -> JSONResponse:
    """Single dispatch entrypoint for the v0.2.0 Web Surface.

    Exposed as a module-level function so it can be unit-tested in
    isolation without spinning up the full FastAPI app.
    """
    if not is_web_surface_enabled():
        return _disabled_response()
    return _not_implemented_response(request.url.path)


@router.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    include_in_schema=False,
)
async def web_surface_catchall(full_path: str, request: Request) -> JSONResponse:
    return await handle_web_surface(request)


@router.get("", include_in_schema=False)
async def web_surface_root(request: Request) -> JSONResponse:
    return await handle_web_surface(request)


def describe() -> Dict[str, Any]:
    """Return a small metadata blob describing the surface state."""
    return {
        "surface": "web",
        "version": "v0.2.0",
        "prefix": WEB_SURFACE_PREFIX,
        "enabled": is_web_surface_enabled(),
        "flag_env": WEB_SURFACE_FLAG_ENV,
    }
