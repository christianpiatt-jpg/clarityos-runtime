# Pocket — ClarityOS phone-sized web surface (v0.3.0)

Pocket is a **React + Vite SPA** served via nginx on Cloud Run. It is
a separate runtime from the Expo native `/phone/` app and the
TypeScript v0.2 web surface at `cockpit.pro-mediations.com`.

| Surface | Runtime | Source | Domain |
|---|---|---|---|
| Cockpit | Node v0.2 (TS server-render) | `web/` | `cockpit.pro-mediations.com` |
| Pocket  | React/Vite SPA + nginx        | `pocket/` | `pocket.clarityos.dev` (planned) |
| Phone   | Expo React Native             | `phone/` | mobile app stores |

No file in `pocket/` imports from `web/`, `phone/`, or any ClarityOS
Python module. This is by design.

## Local development

```bash
cd pocket
npm install
npm run dev
```

Vite serves at <http://localhost:5174> (5173 is taken by the cockpit
dev server). Set the backend URL via `pocket/.env.local`:

```
VITE_CLARITY_ENGINE_URL=https://clarity-engine-XXXXXX.us-central1.run.app
VITE_BUILD_VERSION=local-dev
```

If unset, `/runtime` renders "(not configured)" / "(unset)" instead
of firing requests at an undefined target.

## Production build (local)

```bash
cd pocket
npm install
VITE_CLARITY_ENGINE_URL=https://... VITE_BUILD_VERSION=$(date -u +%Y%m%d%H%M%S) npm run build
```

Output lands in `pocket/dist/`. The container build (next section)
does the same thing inside a `node:20-alpine` layer, then copies the
`dist/` into an `nginx:alpine` image with the SPA fallback rule.

## Deploy (Cloud Build → Cloud Run)

From the repo root:

```bash
PROJECT="founding-os"
REGION="us-central1"
TAG=$(date -u +%Y%m%d%H%M%S)
IMAGE="${REGION}-docker.pkg.dev/${PROJECT}/cloud-run-source-deploy/clarityos-pocket-v0-3:${TAG}"
API_URL="https://clarity-engine-736968277491.us-central1.run.app"

# 1. Build + push the image.
gcloud builds submit \
    --config pocket/cloudbuild.pocket.yaml \
    --ignore-file=pocket/.gcloudignore.pocket \
    --substitutions="_IMAGE=${IMAGE},_API_URL=${API_URL},_BUILD_VERSION=${TAG}" \
    .

# 2. Deploy to Cloud Run.
gcloud run deploy clarityos-pocket-v0-3 \
    --image "${IMAGE}" \
    --region "${REGION}" \
    --platform managed \
    --allow-unauthenticated \
    --port 8080 \
    --concurrency 80 \
    --cpu 1 \
    --memory 512Mi \
    --max-instances 3
```

Verify after deploy:

```bash
SERVICE_URL=$(gcloud run services describe clarityos-pocket-v0-3 \
    --region "${REGION}" --format='value(status.url)')

curl -i "${SERVICE_URL}/"
curl -i "${SERVICE_URL}/runtime"
# SPA fallback check — should return 200 + index.html, not 404:
curl -i "${SERVICE_URL}/this/path/does/not/exist"
```

## Prerequisites (NOT included in the v0.3.0 scaffold branch)

These need to be in place before Pocket can serve real traffic at
`pocket.clarityos.dev`. They are intentionally **out of scope** for
this branch — each gets its own card.

1. **Backend CORS update.** Add `https://pocket.clarityos.dev` (and
   your dev origin) to the `CORSMiddleware` allow-list in `app.py`.
   Without this, the SPA's `fetch` calls to the Python clarity-engine
   are browser-blocked.
2. **Domain ownership.** Register `clarityos.dev` (or pick a
   subdomain on a domain you already own) and verify it in Google
   Search Console so Cloud Run can mint a managed cert.
3. **DNS.** Create the domain mapping via
   `gcloud run domain-mappings create --service clarityos-pocket-v0-3
   --domain pocket.clarityos.dev`, then add the CNAME record it
   gives you to your DNS provider.

## Architectural rules

- No cross-runtime imports (`pocket/` is self-contained).
- No DOM-level embedding of the cockpit Node surface.
- `/runtime` is **Pocket-native** — it surfaces Pocket's own build
  version + the backend URL it was wired to. It is NOT an API
  mirror of the cockpit's `K_SERVICE` / `K_REVISION` panel.
- Backend talks happen ONLY via `pocket/src/api/client.ts`. Routes
  do not call `fetch` directly.

## Next milestone — v0.3.1

- Implement `clarify` screen (chat-style UI hitting backend)
- Implement `me` screen (operator profile)
- Implement `runs` screen (ELINS run list)
- Wire backend status indicator into the nav bar
