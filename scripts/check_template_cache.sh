#!/usr/bin/env bash
# Card A5 — template-cache + render-pipeline drift gate.
#
# Runs the vitest pipeline suite, which exercises:
#   * templateCache.loadCachedTemplate (cache-miss + cache-hit paths)
#   * clearTemplateCache + re-cache cycles
#   * executeRenderPipeline (HTML registered + HTML fallback + JSON)
#   * renderWebSurface alias delegating to the pipeline
#
# Fails non-zero on:
#   * template file missing (loadTemplate throws inside the cache)
#   * pipeline output drift (any test assertion fails)
#   * render-pipeline / template-cache module import failure
#
# Suggested CI wiring (later):
#
#   - name: Render pipeline + template cache drift gate
#     run: bash scripts/check_template_cache.sh
#
# The TS-side renderer uses ESM + import.meta.url for path
# resolution, so a plain ``node -e require(...)`` from the card's
# example won't work in this repo (no dist/ build step). vitest is
# the right invocation primitive for this drift check.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}/web"

npx vitest run src/surface/__tests__/renderPipeline.test.ts
echo "[ok] render pipeline + template cache drift gate passed"
