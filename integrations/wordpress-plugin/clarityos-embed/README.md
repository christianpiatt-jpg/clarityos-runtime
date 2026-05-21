# clarityos-embed

WordPress plugin that mounts the ClarityOS operator surface inside a
WordPress site. **External to ClarityOS runtime** — this plugin lives
outside `/web`, `/phone`, `/desktop`, and the FastAPI backend, and
consumes the same React build that the cockpit ships in standalone
mode. Architecture rule (no plugins inside ClarityOS runtime) is
preserved: this is a host-side adapter, not a runtime extension.

## What it gives you

- **Shortcode** `[clarityos]` — drop the cockpit into any page or post
  while keeping the theme's header / footer / sidebar.
- **Page template** `ClarityOS Embed` — full-bleed canvas with the
  theme chrome stripped out; the cockpit owns the whole viewport.
- **Settings page** at `Settings → ClarityOS Embed` — point the embed
  at your backend (Cloud Run URL etc.). Injected at runtime as
  `window.CLARITYOS_API_BASE` before `app.js` evaluates.

## Build + install

```bash
# 1. Build the React bundle in embed mode (predictable filenames,
#    single JS chunk, single CSS file, HashRouter-aware mount).
cd web
npm install            # if you haven't already
npm run build:embed
# → web/dist-embed/app.js
# → web/dist-embed/app.css

# 2. Copy the artefacts into this plugin's assets/ directory.
cp dist-embed/app.js  ../integrations/wordpress-plugin/clarityos-embed/assets/
cp dist-embed/app.css ../integrations/wordpress-plugin/clarityos-embed/assets/

# 3. Zip the plugin directory and upload it via Plugins → Add New →
#    Upload Plugin, OR copy the whole clarityos-embed/ folder into
#    your WordPress install at wp-content/plugins/clarityos-embed/.
cd ../integrations/wordpress-plugin
zip -r clarityos-embed.zip clarityos-embed/
```

After activation:

1. Go to **Settings → ClarityOS Embed** and paste your backend URL
   (e.g. `https://clarity-engine-xxxxx.run.app`). Save.
2. Create a Page (e.g. titled "ClarityOS"). Under **Page Attributes →
   Template** pick `ClarityOS Embed`. Publish.
3. Visit `/clarityos/` on your site — the operator UI loads.

To use the shortcode flavour instead: leave the page on its default
template and drop `[clarityos]` into the content. The mount div sits
inside the theme's normal page layout.

## How routing works in embed mode

`main.tsx` detects `#clarityos-root` (versus `#root` in standalone)
and switches React Router to `HashRouter`. That means:

- Internal routes look like `https://your-site.com/clarityos/#/threads`.
- WordPress doesn't have to know any ClarityOS route paths — the host
  URL is always just `/clarityos/` (or wherever you put the embed
  page).
- Switching themes, changing the page slug, or moving the embed to a
  different URL does not break internal navigation.

## Updating the build

The plugin uses each asset's file mtime as its cache-bust query
string, so re-copying a fresh `app.js` / `app.css` is enough — no need
to bump the plugin version. If you change PHP, bump `Version:` in
`clarityos-embed.php`.

## Security notes

- The plugin enqueues only static assets from inside its own
  directory. Nothing is fetched cross-origin at the PHP layer.
- The backend URL is sanitised with `esc_url_raw()` before being
  emitted, so a hostile admin can't inject `javascript:` through the
  settings form.
- `Content-Security-Policy` is the host site's responsibility. If your
  WordPress install sends a strict CSP, you'll need to allow the
  Cloud Run backend in `connect-src` and Google Fonts in `font-src`
  / `style-src`.
- The bundled React app is a build artefact of `/web` — same code
  audited by the regular ClarityOS test suite (`npm test` in `/web/`).
  No additional JS is shipped by this plugin.

## File layout

```
clarityos-embed/
  clarityos-embed.php       — plugin entry: shortcode, template hook,
                              settings page, asset enqueue
  templates/
    embed-page.php          — blank canvas; emits only the mount div
                              between wp_head() and wp_footer()
  assets/
    .gitkeep                — placeholder; built app.js + app.css land
                              here after npm run build:embed
  README.md                 — this file
```
