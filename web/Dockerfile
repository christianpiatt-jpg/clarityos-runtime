# ============================================================
#  ClarityOS Web Surface v0.2.0 — Cloud Run container (Track C)
#
#  Authoritative runtime: the TypeScript v0.2 surface under
#  ``web/src/surface/`` (NOT the Python ``web_surface.py`` stub,
#  which stays 503-gated in the existing ``clarity-engine``
#  service).
#
#  Build context: must be the repo root, NOT ``web/`` itself,
#  because COPY ``web/...`` paths reference the workspace.
#  Build from the repo root with:
#
#      docker build -f web/Dockerfile -t clarityos-web-v0-2:local .
#
#  Run locally:
#
#      docker run --rm -p 8080:8080 \
#          -e PORT=8080 -e ENVIRONMENT=local \
#          clarityos-web-v0-2:local
#
#  See DEPLOY.md for the full Cloud Run deploy recipe.
# ============================================================

FROM node:20-alpine

WORKDIR /app/web

# 1. Install runtime dependencies (incl. tsx).
#    ``--omit=dev`` skips test/dev tooling (vitest, jsdom,
#    @testing-library/*, ts-json-schema-generator).
COPY web/package.json web/package-lock.json /app/web/
RUN npm ci --omit=dev

# 2. Copy source + assets the runtime needs.
#    The TS surface uses ``import.meta.url`` for path resolution,
#    so the directory shape under /app/web must match the repo
#    layout: src/ + templates/ + assets/.
COPY web/src       /app/web/src
COPY web/templates /app/web/templates
COPY web/assets    /app/web/assets
COPY web/tsconfig.json /app/web/

# 3. Cloud Run binding contract.
ENV PORT=8080
ENV ENVIRONMENT=local
EXPOSE 8080

# 4. Run the TS entrypoint via tsx (no compile step — matches
#    the vitest runs-TS-directly convention).
CMD ["npx", "tsx", "src/server/main.ts"]
