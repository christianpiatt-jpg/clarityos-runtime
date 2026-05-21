# Hero

## Overview

ClarityOS has two implemented hero surfaces in this repository, and the current
marketing hero is on neither — it lives in WordPress.

- **`web/src/routes/Home.tsx`** — the legacy React public landing page (v32). It
  is explicitly marked LEGACY: superseded by the WordPress marketing surface
  per v74 / Unit 84, and retained as a fallback. New public-surface work goes to
  the WordPress theme.
- **`public_site/index.html`** — a separate static marketing site with its own
  hero section.

There is no geometric hero — no Nucleus, Pentagon, or Polyhedron, and no
animations.

## `Home.tsx` hero

The `Hero` component is a `panel` section: an `<h1>` reading `ClarityOS`, a lede
paragraph ("A cognitive operating system. Clarity about the forces shaping
outcomes — not summaries, not advice. Local-first. Trust-centered. Yours."), and
a live cohort line that reads `N of 500 Founding seats remaining` or announces
the cohort is full. The cohort figure comes from `/public/cohort_status`. The
page's other sections are Founding Cohort, Capabilities, Timeline, Trust &
privacy, and a Call to Action whose copy flips between "Join the Founding
Cohort" and "Join the Waitlist" on cohort fill.

## `public_site` hero

`public_site/index.html` carries a `section hero` block — an `<h1>` headline, a
lede paragraph, and a `hero-cta` with a "Request Access" button and a "See how
it works" link. It is styled by `public_site/assets/css/style.css`.
