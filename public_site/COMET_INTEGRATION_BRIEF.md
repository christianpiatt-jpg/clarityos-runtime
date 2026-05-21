# Comet Integration Brief — ClarityOS public_site

**Source:** `public_site/` (static package — 4 HTML pages, 1 CSS, 1 JS, 3 SVG placeholders, plus README)
**Target:** Hello Elementor (WordPress) on GoDaddy
**Mesh role:** Claude = implementation (delivered). Comet = integration + deployment (this brief). Static pages are immutable; Comet wraps the host, not the content.

---

## Part 1 — Integration brief

### Comet MUST

1. **Serve the 4 static HTML pages raw.** Hello Elementor's blank-canvas page template (or equivalent) is the correct container. The pages already contain `<html>` / `<head>` / `<body>` — they are complete documents.
2. **Map routes** to clean URLs:
   - `index.html` → `/`
   - `product.html` → `/product` (and `/product/`)
   - `about.html` → `/about` (and `/about/`)
   - `contact.html` → `/contact` (and `/contact/`)
3. **Place assets** so the relative hrefs resolve unchanged:
   - `assets/css/style.css` reachable at `./assets/css/style.css` from every HTML page.
   - `assets/js/main.js` reachable at `./assets/js/main.js`.
   - `assets/img/*.svg` reachable at `./assets/img/*.svg`.
4. **Force HTTPS** at the host level.
5. **Apply trailing-slash normalisation** consistent with the rest of the WordPress install (301 between `/product` and `/product/`).
6. **Wire the contact form** (`contact.html`):
   - Remove `data-static="true"` from the `<form>` element OR change it to `"false"`.
   - Wire `submit` to the chosen backend (WP form plugin, Cloud Function, Mailchimp — Comet picks).
   - Replace the `mailto:hello@example.com` fallback string in the `.form-fallback` paragraph with the real address.
   - Preserve `aria-live="polite"` on the `[data-role='contact-status']` node.
   - Preserve `novalidate` on the form so backend validation owns the truth.
7. **Replace the 3 SVG placeholders** with production artwork at the same filenames (`surface-phone.svg`, `surface-web.svg`, `surface-cloud.svg`). The HTML/CSS does not change.

### Comet MUST NOT

1. **Wrap the static pages** in another `<html>` / `<head>` / `<body>`. Hello Elementor must serve the static HTML as-is, not embed it inside the Elementor canvas.
2. **Inject WordPress shortcodes** anywhere inside the static HTML.
3. **Modify the CSS palette tokens** (`--color-bg`, `--color-text`, `--color-accent`, `--color-border`) or the 8-px spacing scale.
4. **Add a framework runtime** (jQuery, Alpine, React) or replace the vanilla `main.js`.
5. **Add external loads** — no Google Fonts, no analytics, no tag managers, no third-party JS, no cookie banners.
6. **Attach WooCommerce templates** to any of the 4 pages. WooCommerce surfaces live outside this set.
7. **Link the public site into the operator portal** (React cockpit). Cohort signup remains contact-form gated.
8. **Re-order page structure** (header / main / footer) or change semantic tags.

### Required routing

| Source file       | Production URL  | Notes                                            |
|-------------------|-----------------|--------------------------------------------------|
| `index.html`      | `/`             | Apex of the public marketing site.               |
| `product.html`    | `/product`      | TOC anchors (`#phone`, `#web`, ...) must resolve.|
| `about.html`      | `/about`        |                                                  |
| `contact.html`    | `/contact`      | Form binds here.                                 |
| `assets/css/style.css`   | `/assets/css/style.css` | Cache-bust on theme deploys only.      |
| `assets/js/main.js`      | `/assets/js/main.js`    | Loaded with `defer`.                   |
| `assets/img/*.svg`       | `/assets/img/*.svg`     | Filenames are stable.                  |

### Required rewrites / redirects

- HTTP → HTTPS 301 at the host level.
- Trailing-slash normalisation per the rest of the WordPress install.
- Legacy `/index.html` (if reached) → `/` 301.
- Anchor preservation (`/product#interpreter`) must work without rewrite interference.

### Contact form wiring

- Form lives in `contact.html`, marked `data-static="true"`.
- `main.js` prevents submit and surfaces a fallback email when `data-static="true"`.
- Comet flips the flag (or removes it), points `submit` at the chosen backend, and replaces the `hello@example.com` string in the `.form-fallback` line.
- Status messages render via the `[data-role='contact-status']` `<p>` (already `aria-live="polite"`). Reuse it; do not add a new status element.
- Field names are stable: `name`, `email`, `role`, `message`. Backend wiring should target these.

### WooCommerce boundary

- WooCommerce is **out of scope** for the 4 public pages.
- The site has **no cart, no checkout, no product pages, no WooCommerce shortcodes**.
- "Request Access" CTAs on `index.html` and `product.html` target `contact.html` — they MUST NOT be retargeted to a WooCommerce flow without an explicit founder call.
- If a paid funnel lands later, it lives on separate WordPress routes (e.g. `/founding500`) and does not modify these 4 pages.

### Domain / subdomain expectations

| Surface                    | Host                              | Notes                                                     |
|----------------------------|-----------------------------------|-----------------------------------------------------------|
| Public marketing site      | Apex (e.g. `clarityos.example`)   | This deliverable.                                         |
| Operator portal (React)    | Subdomain (e.g. `app.clarityos.example`) | DIFFERENT host. Session cookies do not cross.       |
| Phone (Expo native)        | n/a                               | Mobile bundle, not web-routed.                            |
| Desktop (Electron)         | n/a                               | Native bundle, not web-routed.                            |

DNS-level separation prevents accidental session leakage. The static site does not embed an `<iframe>` of, link directly to, or share cookies with the operator portal.

---

## Part 2 — Verification checklist

Deterministic pass/fail. Run after integration; every check must pass.

| #  | Check                                                                                                                          | Pass criterion                                                                                                |
|----|--------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| 1  | `GET https://<domain>/` returns 200                                                                                            | Status 200; response body contains `<title>ClarityOS — Operator-grade reasoning runtime</title>`.              |
| 2  | `GET /about`, `/product`, `/contact` each return 200                                                                           | All three return 200 with their respective `<title>` strings.                                                  |
| 3  | `GET /assets/css/style.css` returns 200                                                                                        | Status 200; `Content-Type` starts with `text/css`.                                                             |
| 4  | `GET /assets/js/main.js` returns 200                                                                                           | Status 200; `Content-Type` is `text/javascript` or `application/javascript`.                                   |
| 5  | `GET /assets/img/surface-phone.svg`, `surface-web.svg`, `surface-cloud.svg` each return 200                                    | Status 200; `Content-Type` is `image/svg+xml`.                                                                 |
| 6  | HTTP request redirects to HTTPS                                                                                                | `http://<domain>/` returns 301 with `Location:` starting `https://`.                                            |
| 7  | Trailing-slash normalisation is consistent                                                                                     | `/product` and `/product/` both reachable (one 301s to the other; both end-state pages serve identical bodies).|
| 8  | Anchor links inside `/product` resolve                                                                                         | `/product#interpreter` loads `/product` and scrolls to `#interpreter` (the section exists in the response body).|
| 9  | Mobile viewport (width < 720 px) shows the nav toggle                                                                          | The `.nav-toggle` button is visible; `.nav-list` is hidden until `aria-expanded="true"`.                       |
| 10 | Desktop viewport (width ≥ 720 px) shows the inline nav                                                                         | `.nav-list` is visible by default; `.nav-toggle` is hidden.                                                    |
| 11 | Contact form does not 500 on submit                                                                                            | Submitting the form returns 2xx or 3xx (Comet's backend) **or** silently runs the static handler with `data-static="true"`. No 4xx/5xx leaks to the user. |
| 12 | No third-party network requests on any page                                                                                    | Browser network panel on `/`, `/product`, `/about`, `/contact` shows requests **only** to the site's own origin. No Google Fonts, no analytics, no CDN libraries. |

### Two extra checks if Comet has cycles

| #  | Check                                                                                                                          | Pass criterion                                                                                                |
|----|--------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------|
| 13 | Palette tokens match the locked values                                                                                         | Computed style of `.brand-text` has `color: rgb(0, 0, 0)`; `.btn-primary` has `background-color: rgb(0, 85, 255)`. |
| 14 | No `<iframe>`, no operator-portal link, no shared cookie with the cockpit subdomain                                            | Inspect the rendered HTML for `<iframe>` (must be absent) and the document cookie store under the public host (must contain no `session_id`-style cookie shared with the portal). |

---

**End of brief.** No new code. No modifications to the static package. No new assets or templates produced by Claude in this pass.
