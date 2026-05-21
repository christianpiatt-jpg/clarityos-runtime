# SOS Runtime Connector

WordPress plugin. Bridges the WP operator surface (`/cockpit`) to the
SOS_V1 Cloud Run service. Exposes `/wp-json/sos/v1/{engage,elins,continuity,state}`;
authenticates Cloud Run with a service-account-signed ID token.

This is **Pass 2** of the bundled `SOS_V1 + SOS_V2` work. Pass 1 (the
Cloud Run service itself) lives at `sos_runtime/` in this repo.

---

## Files

```
wp-sos-connector/
├── sos-connector.php                 # plugin bootstrap + autoloader
├── includes/
│   ├── class-sos-settings.php        # Settings → SOS Runtime page
│   ├── class-sos-client.php          # JWT signing + Cloud Run HTTP
│   └── class-sos-rest.php            # sos/v1 REST routes
├── assets/
│   └── admin.css                     # admin settings styling
└── README.md
```

## Installation

1. Zip the `wp-sos-connector/` directory.
2. WP Admin → Plugins → Add New → Upload Plugin → upload the zip.
3. Activate.
4. Visit **Settings → SOS Runtime**.

## Settings fields

Stored as a single nested option `sos_runtime_settings`.

| Field                  | Required | Value                                                       |
|------------------------|----------|-------------------------------------------------------------|
| Cloud Run URL          | yes      | Base URL of the SOS_V1 service (e.g. `https://os-runtime-xxxxxx.run.app`). HTTPS required. No trailing slash. |
| Service account JSON   | yes      | Full JSON for a GCP service account that holds `roles/run.invoker` on the Cloud Run service. Stored in `wp_options`. |
| Audience               | no       | Expected `aud` claim on the minted ID token. Defaults to the Cloud Run URL. Override only if the SOS_V1 service runs behind a load balancer with a different public URL. |

Any settings change invalidates the cached ID token (`sos_runtime_id_token`
transient).

## REST endpoints

Namespace: `sos/v1`.

| Path                   | Method | Forwards to (Cloud Run) | Body sent upstream                                                                  |
|------------------------|--------|--------------------------|-------------------------------------------------------------------------------------|
| `/wp-json/sos/v1/engage`     | POST   | `POST /engage`     | `{user_id, session_id, message, context}` (context merged from request + plugin)    |
| `/wp-json/sos/v1/elins`      | POST   | `POST /elins`      | `{user_id, session_id, signal}`                                                     |
| `/wp-json/sos/v1/continuity` | POST   | `POST /continuity` | `{user_id, session_id, markers}`                                                    |
| `/wp-json/sos/v1/state`      | POST   | `POST /state`      | `{user_id, session_id, current_state?}` (current_state omitted on reads)            |

### Auth chain

```
Browser  ──cookie + X-WP-Nonce──►  WordPress  ──Bearer ID-token──►  Cloud Run
```

1. **Operator → WordPress** — cookie auth + `X-WP-Nonce` header (the
   cockpit JS sends `wp_create_nonce('wp_rest')` issued at template
   render time). `permission_callback` enforces:
   - `is_user_logged_in()` (401 otherwise),
   - `current_user_can('read')` (403 otherwise),
   - membership stub (currently always `true` — V3 wires WC Memberships
     `wc_memberships_is_user_active_member(user, 'founding-500')`).
2. **WordPress → Cloud Run** — the plugin mints an OIDC **ID token**
   using the configured service account and sends it as
   `Authorization: Bearer <id_token>`. Cloud Run IAM gates ingress;
   SOS_V1's `auth.py` does a second `aud`-claim check via Google
   tokeninfo.

### Auth notes

* The Pass 2 spec mentioned `scope=cloud-platform` + "access token" —
  the actual Cloud Run IAM flow uses an **ID token** minted via
  `target_audience` (matches what SOS_V1 verifies). This plugin
  implements the correct ID-token flow; the JWT carries
  `target_audience = <audience>` and the JWT itself has
  `aud = https://oauth2.googleapis.com/token`.
* JWT signing is rolled with `openssl_sign(..., OPENSSL_ALGO_SHA256)` —
  no Composer dep, no vendored library, ~30 lines of code in
  `class-sos-client.php`.
* ID tokens are cached for 55 minutes (Google issues with 1 hour TTL;
  5-min buffer covers clock skew + in-flight calls).

## Membership gating (stub for V2)

`Rest::user_has_active_membership()` currently returns `true` for any
logged-in user. The V3 marker is in the function body:

```php
// TODO(V3): when wc_memberships is installed, replace with:
//   if ( function_exists( 'wc_memberships_is_user_active_member' ) ) {
//       return (bool) wc_memberships_is_user_active_member(
//           $user_id, self::MEMBERSHIP_PLAN_SLUG
//       );
//   }
```

The plan slug constant is `Rest::MEMBERSHIP_PLAN_SLUG = 'founding-500'`.

## Context payload

The plugin contributes a default context that ships with every
`/engage` call:

```json
{
  "site_url":        "https://pro-mediations.com",
  "wp_user_login":   "alice",
  "wp_display_name": "Alice",
  "wp_user_roles":   ["subscriber"],
  "plan_slug":       "founding-500"
}
```

Caller-supplied `context` fields (from the cockpit JS) override the
defaults via `array_replace`. We deliberately do **not** dump
`get_user_meta($user_id)` — that's plugin-extensible and frequently
includes sensitive third-party fields.

## Test connection

**Settings → SOS Runtime → Test /health** calls `GET /health` on the
configured Cloud Run service. Tests URL + IAM principal in one round
trip. Result renders inline (success / failure with the upstream
error message).

## Errors

WP → Cloud Run failures surface as HTTP 502 from the REST endpoint
with body:

```json
{
  "error":   "upstream_error",
  "code":    "sos_runtime_http_5xx",  // or sos_runtime_token_exchange_failed, etc.
  "message": "Cloud Run returned 503: ...",
  "detail":  { "status": 503, "body": ... }
}
```

The cockpit JS surfaces the `message` in the red banner.

## Security notes

* The service account JSON is stored **plaintext** in `wp_options`.
  Exclude the `wp_options` row `option_name = 'sos_runtime_settings'`
  from any DB dump that leaves the host.
* The plugin never emits the service account JSON in any HTTP
  response or error message — only the upstream HTTP status + a
  truncated body are surfaced.
* CORS is enforced **upstream** by SOS_V1 (`pro-mediations.com` +
  `www.pro-mediations.com` by default). The WP REST endpoints sit on
  the same origin as the cockpit JS, so CORS doesn't apply to the
  browser→WP hop.

## Versioning

Plugin lives outside the ClarityOS V## arc — same convention as
`sos_runtime/`. Bumps in lockstep with the SOS bundle:

* V2.0.0 (this pass) — initial connector + cockpit page template.
* V3 (planned) — replace membership stub with WC Memberships check;
  add the founder console + richer cockpit UI.

## Uninstall

`register_uninstall_hook` clears:

* The `sos_runtime_settings` option.
* The cached `sos_runtime_id_token` transient.

Deactivation leaves settings in place (standard WP convention).
