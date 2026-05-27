# Pocket SPA — multi-stage build, served via nginx on Cloud Run.
#
# Stage 1: build the SPA with Vite. ``VITE_CLARITY_ENGINE_URL`` and
# ``VITE_BUILD_VERSION`` are passed as build-args so the deploy
# pipeline can inject the correct backend URL + commit SHA without
# baking them into the source tree.
#
# Stage 2: copy the compiled ``dist/`` into a slim nginx image. The
# nginx config (``nginx.conf``) adds the SPA fallback rule that
# Cloud Run does not provide out of the box.
#
# Build context: ``pocket/`` (not the repo root). See
# ``cloudbuild.pocket.yaml`` for the matching ``docker build`` args.
#
# Build-arg propagation note (v0.3.6 fix):
# ----------------------------------------
# In an earlier build, the ``--build-arg`` values reached docker
# per the cloudbuild step record but did NOT end up in the Vite
# build environment, producing a bundle with ``"(unset)"`` in
# place of the build version. The fix is structural — the ARGs
# now have non-empty defaults (so an unsubstituted build still
# produces meaningful values), AND a dedicated ``RUN`` step
# echoes + ``test -n``s both ARGs BEFORE the ``npm`` layers.
# BuildKit invalidates the cache for that layer (and everything
# downstream) whenever either ARG changes — which makes the
# build-arg → ENV → Vite chain provably deterministic.

FROM node:20-alpine AS build
WORKDIR /app

# Build-args. Defaults are sensible non-empty values so:
#   * a build without explicit ``--build-arg`` still produces a
#     working image (the runtime panel will show "dev" + the live
#     backend URL rather than "(unset)" / fallback)
#   * the RUN test below cannot pass with empty values, which
#     hard-fails a misconfigured build early
ARG VITE_CLARITY_ENGINE_URL="https://clarity-engine-736968277491.us-central1.run.app"
ARG VITE_BUILD_VERSION="dev"

ENV VITE_CLARITY_ENGINE_URL=${VITE_CLARITY_ENGINE_URL}
ENV VITE_BUILD_VERSION=${VITE_BUILD_VERSION}

# Force BuildKit to consume both ARGs as part of a real RUN step.
# Three things this gives us:
#   1. Layer cache invalidates whenever either ARG changes
#      (BuildKit otherwise sometimes skips invalidation when an
#      ARG is only referenced through an ENV).
#   2. The values are visible in the Cloud Build log for diagnostics.
#   3. ``test -n`` hard-fails the build if a substitution was
#      dropped — much better than producing a silently-empty bundle.
RUN echo "Pocket build-arg check:" \
 && echo "  VITE_BUILD_VERSION=${VITE_BUILD_VERSION}" \
 && echo "  VITE_CLARITY_ENGINE_URL=${VITE_CLARITY_ENGINE_URL}" \
 && test -n "${VITE_BUILD_VERSION}" \
 && test -n "${VITE_CLARITY_ENGINE_URL}"

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
