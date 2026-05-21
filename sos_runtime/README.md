# SOS Runtime — `SOS_V1`

Operator-facing reasoning service. Sits behind the WordPress SOS
Connector plugin, talks to Claude, persists to Firestore. Standalone
Cloud Run service; **independent** of the V47–V82 ClarityOS
infrastructure (different host, different versioning cadence, no
shared imports).

This is **Pass 1** of the bundled `SOS_V1 + SOS_V2` work. SOS_V2
(WordPress connector plugin + cockpit page stub) lands as the next
pass.

---

## Architecture

```
WordPress ──Bearer JWT──►  Cloud Run (SOS Runtime, this service)
                              │
                              ├──►  Anthropic Claude  (SOS_ANTHROPIC_API_KEY)
                              │
                              └──►  Firestore         (sessions / events / states)
```

All five endpoints are session-scoped per `user_id`. WordPress is the
operator trust boundary; this service trusts the `user_id` in the
request body and uses Cloud Run IAM to gate ingress at the platform
layer.

## Endpoint surface

| Method | Path          | Auth | Persistence side-effects                                                                 |
|--------|---------------|------|------------------------------------------------------------------------------------------|
| GET    | `/health`     | none | none                                                                                     |
| GET    | `/status`     | iam  | none                                                                                     |
| POST   | `/engage`     | iam  | upsert `sessions/{sid}` · append `events` (engage + model_response) · touch `states/{uid}.continuity.last_engage_ts_ms` |
| POST   | `/elins`      | iam  | upsert `sessions/{sid}` · append `events` (elins). v1 stub — see §"What's deferred"      |
| POST   | `/continuity` | iam  | upsert `sessions/{sid}` · append `events` (continuity) · merge into `states/{uid}.continuity` |
| POST   | `/state`      | iam  | upsert `sessions/{sid}` · `current_state` write transitions; reads append nothing        |

## Firestore schema

Three collections, all int-ms timestamps:

```
sessions/{session_id}
  id, user_id, created_at, updated_at, metadata

events/{auto_id}
  id, session_id, user_id,
  type    ∈ engage | elins | continuity | state,
  payload, model_response?, created_at

states/{user_id}
  id, current_state, last_transition, continuity, updated_at
```

Security: `firestore.rules` blocks ALL client-SDK access. Only the
Cloud Run service account (admin SDK) reaches the data.

## Environment

| Var                          | Required? | Purpose                                                            |
|------------------------------|-----------|--------------------------------------------------------------------|
| `SOS_BACKEND`                | no        | `memory` flips Firestore + LLM + auth all to test-mode in one shot |
| `SOS_FIRESTORE_BACKEND`      | no        | `firestore` (default) \| `memory`                                  |
| `SOS_LLM_MODE`               | no        | `real` (default if key set) \| `fake`                              |
| `SOS_AUTH_MODE`              | no        | `iam` (default) \| `insecure` — **never set `insecure` in prod**   |
| `SOS_ANTHROPIC_API_KEY`      | prod      | Anthropic API key. Wired via Secret Manager in `cloudbuild.yaml`.  |
| `SOS_ANTHROPIC_MODEL`        | no        | Model id. Default: `claude-3-7-sonnet-latest`.                     |
| `SOS_AUDIENCE`               | prod      | Expected `aud` claim — the Cloud Run service URL.                  |
| `SOS_CORS_ORIGINS`           | no        | Comma-separated allow-list. Default: `https://pro-mediations.com,https://www.pro-mediations.com` |
| `PORT`                       | runtime   | Set by Cloud Run automatically. Defaults to 8080.                  |

## Local development

```bash
# From the repo root.
cd sos_runtime
pip install -r requirements.txt
SOS_BACKEND=memory uvicorn sos_runtime.main:app --reload
# In another terminal:
curl http://localhost:8000/health
```

`SOS_BACKEND=memory` flips three things at once: Firestore goes
in-process, the LLM dispatcher returns deterministic echoes, and JWT
verification is bypassed. Useful for browser-side dev against the
cockpit JS.

## Tests

```bash
# From the repo root:
python -m pytest sos_runtime/tests/ -v
```

36 tests cover:

* `/health` — public, payload shape, no-auth-required
* `/status` — authenticated introspection, caller principal shape
* `/engage` — happy path, response envelope, session + event persistence, model_response mutation, continuity touch
* `/elins` — deterministic stub, normalized shape, TODO marker, event append
* `/continuity` — marker merge into state, no current_state transition, event append
* `/state` — read vs write paths, last_transition behavior, event append only on writes
* Cross-endpoint persistence (engage → state read sees continuity)
* Per-user isolation
* Validation (empty / missing fields → 422)
* CORS preflight allowed for `pro-mediations.com`
* Backend isolation (in-memory store cleared between tests)

## Deployment (Comet's territory)

```bash
# Build + push + deploy in one shot.
gcloud builds submit --config cloudbuild.yaml \
  --substitutions=_REGION=us-central1,_SERVICE_NAME=os-runtime,_ANTHROPIC_KEY_SECRET=sos-anthropic-api-key
```

Key steps the `cloudbuild.yaml` performs:

1. Docker build with the service code.
2. Push to GCR (`gcr.io/$PROJECT_ID/os-runtime:$SHORT_SHA`).
3. `gcloud run deploy` with `--no-allow-unauthenticated` (Cloud Run
   IAM is the ingress gate).
4. `SOS_ANTHROPIC_API_KEY` mounted from Secret Manager (key
   `sos-anthropic-api-key` by default — flip via substitution).

After deploy, run the Firestore rules:

```bash
gcloud firestore deploy firestore.rules
```

And lock the WordPress connector's service-account principal as the
sole invoker:

```bash
gcloud run services add-iam-policy-binding os-runtime \
  --region=us-central1 \
  --member=serviceAccount:wp-sos-connector@$PROJECT.iam.gserviceaccount.com \
  --role=roles/run.invoker
```

## What's deferred to follow-up units

### `SOS_V2` (next pass)

* WordPress connector plugin (PHP) at `wp-sos-connector/`.
* Cockpit page template + JS at `wp-cockpit/`.
* Manual smoke per the Comet integration brief.

### Future (no current commitment)

* **`/elins` kernel wire** — currently a deterministic echo + TODO
  marker. Wiring to the V34+ ELINS kernel (`ELINS.standard_elins` /
  `regional_elins` / `forecast_engine` in the main repo) is its own
  follow-up unit. Cleanest path is HTTP — SOS calls back into the
  existing ClarityOS service rather than importing its Python.
* **Local JWK verification** — `auth.py` uses Google's tokeninfo
  endpoint, which adds a network hop per request. Swapping to
  cached JWKs via PyJWT cuts that latency. Operationally simpler to
  ship with tokeninfo first.
* **Firestore composite indexes** — the events queries
  (`list_events_for_session`, `list_events_for_user`) need composite
  indexes on (`session_id`, `created_at desc`) and (`user_id`,
  `created_at desc`). Create them after the first production query
  fails — Firestore emits the exact link in the error.

## Relationship to the rest of the repo

| Surface                            | Purpose                                                                              | This service touches it? |
|------------------------------------|--------------------------------------------------------------------------------------|---------------------------|
| `app.py` + V47–V82 endpoints       | ClarityOS internal service (X-Session-ID auth, encrypted local vault)                | No — different host       |
| `web/` React cockpit               | Operator portal for the ClarityOS service (V48+)                                     | No — different audience   |
| `public_site/`                     | Static marketing site (delivered with Comet integration brief)                       | No                        |
| `wp-sos-connector/` (V2, not yet)  | PHP plugin that talks to **this** service                                            | Yes — V2 lands next       |
| `wp-cockpit/` (V2, not yet)        | Cockpit page template + JS, served by WordPress                                      | Yes — V2 lands next       |

## Versioning

* SOS lives outside the ClarityOS `V##` arc. This pass: `SOS_V1.0.0`
  in `VERSION`.
* No `BUILD_VERSION` bump on the main service.
* No `/health` version change on `app.py`.
* SOS_V2 (WordPress side) bumps to `SOS_V2.0.0` when it lands.
