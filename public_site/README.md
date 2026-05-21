# ClarityOS public site

Static reference implementation of the ClarityOS public marketing
site. Produced as a single self-contained deliverable for Comet to
wrap into the deployment scaffold (WordPress theme, Cloud Run static
hosting, GoDaddy static upload — Comet picks).

## Directory tree

```
public_site/
├── about.html
├── contact.html
├── index.html
├── product.html
├── README.md                  (this file)
└── assets/
    ├── css/
    │   └── style.css
    ├── img/
    │   ├── surface-cloud.svg
    │   ├── surface-phone.svg
    │   └── surface-web.svg
    └── js/
        └── main.js
```

ZIP for handoff: `clarityos_public_site.zip` at the repo root.

## Architecture summary

* **Static.** No build tools, no frameworks, no bundlers, no external
  fonts, no analytics, no cookies. Open `index.html` in a browser and
  it works.
* **HTML.** Four pages — `index.html`, `about.html`, `product.html`,
  `contact.html`. Each is self-contained, semantic, and minimal.
* **CSS.** A single `assets/css/style.css` with the founder-locked
  palette (`#FFFFFF` / `#000000` / `#0055FF` / `#E5E5E5`),
  8-px spacing scale, system font stack, mobile-first responsive
  breakpoint at 720 px.
* **JS.** A single `assets/js/main.js`, vanilla, loaded with
  `defer`. Handles the mobile nav toggle and the static contact-form
  prevention. No framework dependency, no third-party library, no
  external import.
* **Images.** SVG placeholders for the three surfaces (`surface-phone.svg`,
  `surface-web.svg`, `surface-cloud.svg`). Comet replaces with real
  artwork at integration time.

## Page-by-page intent

| Page             | Role                                                                  |
|------------------|-----------------------------------------------------------------------|
| `index.html`     | Value statement, PHONE/WEB/CLOUD three-column, interpreter description, "Request Access" CTA. |
| `product.html`   | Eight-section deep dive: PHONE runtime, WEB cockpit, CLOUD execution layer, interpreter, model router, clarity pipeline, local vault, multi-surface continuity. Includes a TOC. |
| `about.html`     | Origin, six design principles (determinism, OS-holds-state, no-plugins, per-user partitioning, graceful degrade, one-contract-three-surfaces), four-layer system architecture, five invariants. |
| `contact.html`   | Non-functional form (name / email / role / message), static-submit handler that surfaces a fallback email, two-day reply expectation. |

## Design constraints (locked)

* No animations.
* No gradients.
* No parallax.
* No external libraries.
* No external dependencies.
* No build tools.
* No framework runtime.
* High contrast.
* Mobile-first.
* Deterministic 8-px spacing grid.
* System font stack only.
* `--color-bg: #FFFFFF; --color-text: #000000; --color-accent: #0055FF; --color-border: #E5E5E5;`

## Comet integration notes

Comet owns:

1. **Wrapping** — embed the site in the chosen deployment scaffold
   (WordPress page-template, static Cloud Run bucket, or GoDaddy
   static upload).
2. **Routing** — wire the four pages into the production URL space.
   The current `<a>` href attributes use relative paths (`index.html`,
   `about.html`, etc.) so they work both as a static drop-in and
   inside a path-rewriting environment.
3. **Form backend** — `contact.html` carries a non-functional form
   marked `data-static="true"`. The handler in `main.js` prevents
   submission and shows a fallback email. Comet replaces both:
   - Set `data-static="false"` (or remove it) on the form.
   - Wire submit to the chosen backend (Cloud Function, Stripe-friendly
     waitlist, Mailchimp, etc).
   - Replace `hello@example.com` in the fallback prose with the
     real address.
4. **Real imagery** — drop production artwork in `assets/img/` over
   the SVG placeholders. Filenames are stable (`surface-phone.svg`,
   `surface-web.svg`, `surface-cloud.svg`) so swap is a no-op edit.
5. **Cohort gating** — if Comet attaches a real signup flow, the
   "Request Access" CTA on `index.html` and the CTA band on
   `product.html` are the binding points. Their current target is
   `contact.html`.

## Accessibility checklist

* `<a class="skip">` first focusable element on each page.
* `aria-current="page"` on the active nav item.
* `<form novalidate>` so HTML5 validation doesn't fight Comet's
  backend validation.
* `aria-live="polite"` on the form status node for screen-reader
  parity.
* All decorative images have `alt=""`; functional artwork uses
  descriptive alt text.
* All interactive elements have visible focus styles
  (`outline: 2px solid var(--color-accent)`).

## Relationship to the rest of the ClarityOS repo

* This site is **standalone**. It does not import from `web/`,
  `phone/`, or `desktop/`. It does not call any ClarityOS API
  endpoint. It does not read or write the vault.
* It is **distinct from the V32 `web/src/routes/Home.tsx` legacy
  landing**. That route stays as a fallback inside the React cockpit
  per the V74 readiness doc. This static site is the
  external-facing surface Comet integrates.
* Versioning is **independent**. No `/health` bump, no
  `BUILD_VERSION` change. The site lives on its own cadence.
