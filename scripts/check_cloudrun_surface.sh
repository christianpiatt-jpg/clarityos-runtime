#!/usr/bin/env bash
# Card 10 — Cloud Run surface compile-only gate.
#
# Imports ``web_surface_entry`` and exercises the factory in both the
# disabled and enabled states. Useful as a fast CI smoke test before
# the heavier pytest gates run. Fails non-zero on:
#
#   * import error from web_surface_entry or any of its transitive
#     deps (web_surface, web_surface_models, web_surface_schema_loader),
#   * factory returning None,
#   * the surface accidentally activating on the default env (the
#     ``disabled by default`` invariant).
#
# Suggested CI wiring (later):
#
#   - name: Cloud Run surface compile check
#     run: bash scripts/check_cloudrun_surface.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

python - <<'PYEOF'
"""Compile-only gate for the v0.2.0 Cloud Run surface entrypoint."""
import os
import sys

# Ensure the default env is clean before the disabled-mode check.
os.environ.pop("WEB_SURFACE_V0_2_ENABLED", None)

import web_surface_entry

# --- 1. Disabled-by-default invariant -------------------------------------
app_off = web_surface_entry.create_web_surface_app()
assert app_off is not None, "factory returned None when disabled"
web_surface_routes = [
    getattr(r, "path", "")
    for r in app_off.routes
    if getattr(r, "path", "").startswith("/web-surface/v0.2")
]
assert web_surface_routes == [], (
    f"disabled app unexpectedly carries web-surface routes: "
    f"{web_surface_routes!r}"
)
print("[ok] disabled state: 0 web-surface routes mounted")

# --- 2. Enabled invariant -------------------------------------------------
os.environ["WEB_SURFACE_V0_2_ENABLED"] = "true"
# Re-import to pick up the env change (factory reads env at call time,
# but the inner web_surface module caches via importlib state).
import importlib
import web_surface
importlib.reload(web_surface)
importlib.reload(web_surface_entry)
app_on = web_surface_entry.create_web_surface_app()
assert app_on is not None, "factory returned None when enabled"
web_surface_routes = [
    getattr(r, "path", "")
    for r in app_on.routes
    if getattr(r, "path", "").startswith("/web-surface/v0.2")
]
assert len(web_surface_routes) > 0, (
    "enabled app should expose at least one web-surface route"
)
print(f"[ok] enabled state: {len(web_surface_routes)} web-surface routes mounted")

print("[ok] Cloud Run surface compile-only gate passed")
PYEOF
