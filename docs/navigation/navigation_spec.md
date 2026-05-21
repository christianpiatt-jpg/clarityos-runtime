# Navigation

## Overview

The web app has two navigation systems, plus a separate static-site nav.

## Cockpit shell — `components/Layout.tsx`

`Layout.tsx` is the main app shell: a top bar, a left rail, a main pane
(`<Outlet/>`), and a status bar.

- **Top bar** — the `ClarityOS` brand (links to `/`) and, on the right, the
  signed-in user with a `SIGN OUT` button, or a `SIGN IN` link.
- **Left rail** — `RailSection`s of `RailLink`s (`NavLink`s that take an
  `active` class on the current route). Sections: `OPERATOR` (Operator,
  Sessions, Continuity); `ENGINE` (Markov QC, System); `OPERATOR ENVELOPE`
  (Vault, Library, Timeline, Plans, Account); `CONVERSE` (Threads); `RUNTIME`
  (Session, History, Operator Vault, Model, Provider Health, Providers, and the
  EL/INS routes); `BRIDGES` (Iframe).
- **Status bar** — five `StatusCell`s, each with an `ok` / `warn` / `err` /
  `idle` tone: `SID` (session token prefix), `COHORT`, `MQC` (Markov QC score),
  `CONT` (pending continuity resume count), `API` (backend reachability).

## v1 surface nav — `components/v1/OperatorSidebar`

The v1 surface (`/threads`, `/personal-elins`) uses `OperatorSidebar` — a flat
`nav` of `NavItem`s: Home, Threads, Projects, Emotional Physics, Personal
ELINS, Library, Settings. The web client renders its thread list below the nav
items. An `activeNav` label highlights the current item.

## Unit 84 header

The Founding 500 Subscription Gate (`/founding500/confirm`) carries its own
`GlobalHeader` — a monospace logo and an uppercase status line.

## Static site nav

`public_site/index.html` has its own `site-nav` — a horizontal bar (Home,
Product, About, Contact) that collapses behind a `Menu` toggle on narrow
viewports.
