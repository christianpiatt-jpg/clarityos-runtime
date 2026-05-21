# SOS Cockpit — WordPress page template

Operator surface that renders inside a WordPress page. Sends operator
messages to `/wp-json/sos/v1/engage` (provided by the
`wp-sos-connector` plugin) and displays the reply + ELINS + state
panels.

This is part of **Pass 2** (`SOS_V2`) — the WP-facing half of the
SOS bundle. Pairs with `wp-sos-connector/` (plugin) and
`sos_runtime/` (Cloud Run service).

---

## Files

```
wp-cockpit/
├── cockpit-template.php          # WP page template ("Template Name: SOS Cockpit")
├── assets/
│   ├── cockpit.js                # vanilla JS (no framework)
│   └── cockpit.css               # palette + 8-px grid matching public_site/
└── README.md
```

## Installation

There are two clean ways to install. Comet picks one based on the
deployment scaffold; both are supported by the template.

### Option A — Drop into the active theme (recommended)

1. Copy `cockpit-template.php` into the active theme directory
   (e.g. `wp-content/themes/<active-theme>/cockpit-template.php`).
2. Copy `assets/cockpit.js` and `assets/cockpit.css` into the active
   theme under `assets/` (matching paths). The template uses
   theme-relative URLs by default.
3. WP Admin → Pages → Add New → in the **Template** dropdown,
   select **SOS Cockpit**.
4. Set the page slug to `/cockpit` (or whatever path Comet wired in
   the Comet integration brief).
5. Publish.

### Option B — Bundle into a child theme

Same as Option A but inside a child theme. Lets you redeploy the
parent theme without losing the template.

### Option C — Plugin-registered template (V3, optional)

The plugin (`wp-sos-connector`) could register this template via the
`theme_page_templates` filter so the file doesn't need to live in the
theme directory at all. **Not implemented in V2** — keeps the
template self-contained and theme-portable. Add in V3 if Comet
prefers the bundled-with-plugin install.

## What the template does

1. **Forces login** — `auth_redirect()` at the top redirects
   unauthenticated visitors to `wp-login.php`, returning to
   `/cockpit` after sign-in.
2. **Enqueues assets** — `cockpit.css` + `cockpit.js`.
3. **Localizes a bootstrap object** for the JS:
   ```js
   window.sosCockpit = {
     restRoot: "https://pro-mediations.com/wp-json/sos/v1",
     nonce:    "<wp_create_nonce('wp_rest')>",
     user:     { id: 42, display_name: "Alice" }
   };
   ```
4. **Renders the DOM scaffold**:
   - `#sos-cockpit` — root container
   - `#sos-banner` — error banner (hidden by default)
   - `#sos-log` — conversation log (operator + SOS bubbles)
   - `#sos-input`, `#sos-send` — form
   - `#sos-elins`, `#sos-state` — side panels

## JS behaviour

* **Send button** posts to `/wp-json/sos/v1/engage` with body
  `{ message }`. The plugin's REST endpoint fills in `user_id`,
  `session_id`, and merges the default context.
* **Cmd/Ctrl + Enter** also submits.
* **Success** — appends the operator + SOS bubbles, renders
  `data.elins` and `data.state` as JSON in the side panels, clears
  the input.
* **Error** — surfaces the upstream error message in the red banner
  (`#sos-banner`).
* **Auth nonce** — sent as `X-WP-Nonce` header. WP REST validates
  the nonce against the logged-in user's session.

## Styling

* Palette: `#FFFFFF` background, `#000000` text, `#0055FF` accent,
  `#E5E5E5` borders. Same locked palette as `public_site/`.
* 8-px spacing grid. System font stack.
* Mobile-first; the side-panels lay out next to the log at
  `min-width: 960px` and stack underneath below that.
* No animations, no gradients, no parallax, no external fonts.

## Customisation

* **Change accent colour** — edit the four `#0055ff` references in
  `cockpit.css`.
* **Change log height** — `.sos-log { max-height: 60vh; }`.
* **Replace the SOS-side bubble colour** — `.sos-bubble-sos .sos-bubble-body { color: ...; }`.
* **Hide a side panel** — wrap the relevant `<section class="sos-panel">`
  in `display: none` via theme CSS, or remove the markup directly.

## Smoke test

After Comet installs the plugin + template:

1. Open `/cockpit` while logged in.
2. Type any message; press **Send**.
3. Expect:
   - One operator bubble + one SOS bubble in the log.
   - `#sos-state` shows the JSON state envelope (`user_id`,
     `current_state`, `continuity`, `last_transition`, `updated_at`).
   - `#sos-elins` shows the empty `{}` (engage doesn't populate ELINS
     yet — `/elins` endpoint is the v34+ kernel-wire follow-up).
4. With the WP browser dev tools network panel, the POST should hit
   `/wp-json/sos/v1/engage` and return 200 with the upstream JSON.

## TODOs (V3)

* Richer cockpit UI — chain detail, multi-thread switcher, ELINS
  panel for the `/elins` endpoint output.
* Continuity timeline widget.
* Manual "Save state" button that calls `/state` write path with the
  operator-supplied next state.
* Founder console (admin-only view that reads `/founder/*` from the
  ClarityOS service — not this WP service).
