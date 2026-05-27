# Pocket SPA — multi-stage build, served via nginx on Cloud Run.
#
# Stage 1: build the SPA with Vite. ``VITE_CLARITY_ENGINE_URL`` and
# ``VITE_BUILD_VERSION`` are passed as build args so the deploy
# pipeline can inject the correct backend URL + tag without baking
# them into the source tree.
#
# Stage 2: copy the compiled ``dist/`` into a slim nginx image. The
# nginx config (``nginx.conf``) adds the SPA fallback rule that
# Cloud Run does not provide out of the box.
#
# Build context: ``pocket/`` (not the repo root). See
# ``cloudbuild.pocket.yaml`` for the matching ``docker build`` args.

FROM node:20-alpine AS build
WORKDIR /app

ARG VITE_CLARITY_ENGINE_URL=""
ARG VITE_BUILD_VERSION=""
ENV VITE_CLARITY_ENGINE_URL=$VITE_CLARITY_ENGINE_URL
ENV VITE_BUILD_VERSION=$VITE_BUILD_VERSION

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
