# ClarityOS — Cloud Run Deploy (Track C)

This document covers deployment of the **v0.2 TypeScript Web Surface** as
a new Cloud Run service. The existing **Python `clarity-engine` service**
is unchanged.

---

## Service inventory

| Service                 | Runtime                        | Source        | 503 gate                       | Status               |
|-------------------------|--------------------------------|---------------|--------------------------------|----------------------|
| `clarity-engine`        | Python 3.12 + FastAPI          | `app.py`      | `WEB_SURFACE_V0_2_ENABLED` env | Untouched, in prod   |
| `clarityos-web-v0-2`    | Node 20 + TypeScript (tsx)     | `web/`        | None (staging-only)            | Track C — staging    |

Track C deliberately does **not** consolidate runtimes. The Python service
keeps its 503 gate on `/web-surface/v0.2/*` exactly as today. The new
Node service serves the actual TS implementation built across A1–A18
and exposes it under a separate Cloud Run URL.

---

## Authority

- **Authoritative v0.2 runtime:** TypeScript in `web/src/surface/`,
  driven by `routeWebSurface(req)`.
- **Adapter boundary:** `web/src/server/` (HTTP ↔ surface translation).
  Pure functions; tests in `web/src/server/__tests__/`.
- **Bootstrap:** `web/src/server/main.ts` (runs via `tsx`).
- **Container:** `web/Dockerfile` (Node 20 alpine, no compile step).

---

## Local smoke test

From the repo root:

```bash
cd web
npm install            # one-time
npm run serve          # binds 0.0.0.0:8080 by default
```

Then in another shell:

```bash
curl -i http://127.0.0.1:8080/health
# HTTP/1.1 200 OK
# content-type: application/json
#
# {"status":"ok","surface":"v0.2.0"}

curl -i http://127.0.0.1:8080/ready
# (same payload)

curl -i http://127.0.0.1:8080/home
# 200 text/html; charset=utf-8 + the home view

curl -i http://127.0.0.1:8080/web-surface/v0.2/assets/style.css
# 200 text/css + the fingerprinted asset bytes
```

---

## Container build

Build context is **the repo root**, not `web/`:

```bash
docker build -f web/Dockerfile -t clarityos-web-v0-2:local .
docker run --rm -p 8080:8080 \
    -e PORT=8080 -e ENVIRONMENT=local \
    clarityos-web-v0-2:local
```

Smoke-check with the same `curl` commands above against
`http://127.0.0.1:8080`.

---

## Cloud Run deploy — staging only

> **The Python `clarity-engine` service stays untouched.**
> The 503 gate for the v0.2 surface in the Python app is **not**
> weakened or bypassed by this deploy. Runtime consolidation is
> a separate future track.

### One-time setup

```bash
# 1. Authenticate (interactive).
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID

# 2. Enable required APIs (idempotent).
gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com

# 3. Create the Artifact Registry repo (one-time per project).
gcloud artifacts repositories create clarityos-web \
    --repository-format=docker \
    --location=us-east4 \
    --description="ClarityOS v0.2 TypeScript Web Surface images"
```

### Build + push the image

```bash
# Run from the repo root so the Dockerfile's COPY paths resolve.
PROJECT="YOUR_GCP_PROJECT_ID"
REGION="us-east4"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/clarityos-web/clarityos-web-v0-2:$(date -u +%Y%m%d%H%M%S)"

gcloud builds submit \
    --tag "${IMAGE}" \
    --file web/Dockerfile \
    .
```

### Deploy to Cloud Run (staging)

```bash
gcloud run deploy clarityos-web-v0-2 \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --min-instances 0 \
    --max-instances 5 \
    --concurrency 80 \
    --cpu 1 \
    --memory 512Mi \
    --set-env-vars "ENVIRONMENT=staging" \
    --tag staging
```

### Verify the staging URL

```bash
SERVICE_URL=$(gcloud run services describe clarityos-web-v0-2 \
    --region "${REGION}" \
    --format='value(status.url)')

echo "Staging URL: ${SERVICE_URL}"

curl -i "${SERVICE_URL}/health"
curl -i "${SERVICE_URL}/ready"
curl -i "${SERVICE_URL}/home"
curl -i "${SERVICE_URL}/web-surface/v0.2/assets/style.css"
```

---

## Environment variables

| Var           | Default   | Notes                                                    |
|---------------|-----------|----------------------------------------------------------|
| `PORT`        | `8080`    | Cloud Run sets this automatically. Adapter respects it.  |
| `ENVIRONMENT` | `local`   | One of `local` / `staging` / `prod`. Used for logging only. |

Track C does **not** introduce environment-specific behavior beyond
log labelling. Adding behavioural switches is a future card.

---

## Production posture (intentionally not automated here)

Promotion to production is **manual and explicit**, not part of Track C:

1. Verify the staging service for at least one full hour of synthetic
   traffic (`/home`, asset paths, JSON endpoints, the demo form/upload/
   stream/sse paths).
2. Confirm the Python `clarity-engine` service is unchanged and its
   `/web-surface/v0.2/*` paths still return 503.
3. Coordinate any DNS / load-balancer changes separately.
4. Deploy with `--set-env-vars "ENVIRONMENT=prod"` and the same
   image SHA verified in staging.

> The Python 503 gate is **only** removed by a separate, explicit
> change — not in Track C.

---

## Rollback

Cloud Run keeps prior revisions automatically:

```bash
# List revisions
gcloud run revisions list \
    --service clarityos-web-v0-2 \
    --region "${REGION}"

# Pin all traffic back to a known-good revision
gcloud run services update-traffic clarityos-web-v0-2 \
    --region "${REGION}" \
    --to-revisions "REVISION_NAME=100"
```

---

## What this deploy does NOT do

- It does not modify `app.py`, `web_surface.py`, `web_surface_entry.py`,
  `Dockerfile` (root), or `deploy.sh`.
- It does not reimplement any v0.2 logic in Python.
- It does not create a Python↔Node bridge, RPC channel, or sidecar.
- It does not change the Python 503 gate.
- It does not change A1–A18 behavior.

Track C is strictly: **wrap the existing TypeScript surface in a thin
HTTP adapter and ship it as its own Cloud Run service.**
