# Cockpit

## Overview

The Cockpit is the operator workspace — a page that composes panels over the
ClarityOS subsystems. There are **two cockpit generations** in the web app:

- **`/cockpit`** — the v29-hardened cockpit (`routes/Cockpit.tsx`); panels under
  `components/cockpit/`.
- **`/cockpit-v2`** — the consolidated cockpit (`routes/CockpitV2.tsx`); panels
  under `components/cockpitV2/`, state in `state/cockpitStore.ts`.

Both are layout-and-wiring surfaces: they hold no reasoning logic and render
backend responses as-is.

## `/cockpit` — the v29-hardened cockpit

`routes/Cockpit.tsx` composes the panels under `components/cockpit/`. All state
lives in `hooks/*` — the route is layout and wiring only. It uses `useDeviceId`,
`useFlags`, `useContinuity`, and `useMesh`.

### Flag gating

The cockpit reads `/v29/flags`. While flags load it shows a dimmed shell rather
than blanking. Flags:

- `v28_surfaces` — gates the v28 surfaces (the ELINS quicklook, the continuity
  surface, the "Open ELINS" / "Feed" links).
- `onboarding_v1` — shows the onboarding wizard.
- `whats_new_v28` — shows the "What's new" panel.
- `membership_ui_enabled` — shows the Membership link.

### Panels

A header (title, a `Refresh` control, flag-gated links to `/dashboard`,
`/elins`, `/membership`), an `ElInsIndicator` panel, an optional
`ElinsQuicklook`, continuity/mesh error banners, then a two-column grid of
panels — each wrapped in an `ErrorBoundary` so one failing panel does not blank
the cockpit:

- `SessionList` — Markov session metadata.
- `RuntimePanel` — the deterministic envelope viewer.
- `VaultStatus` — vault status from the continuity snapshot.
- `EngineSelector` — selects the active engine.
- `SettingsPanel` — device settings.
- `ContinuitySurface` — the v28 continuity / mesh surface.
- `OnboardingWizard` — shown while `onboarding_v1` is set.
- `WhatsNewPanel` — shown while `whats_new_v28` is set.
- `RegressionFirstPanel` — the v80 Regression-First packet runner.

## `/cockpit-v2` — the consolidated cockpit

`routes/CockpitV2.tsx` is an additive, self-gated surface. It bypasses the app
`Layout` and `RequireAuth` and owns the viewport. When the operator is not
authenticated it renders its own `CockpitLoginPanel`; once authenticated it
renders a topbar plus a three-column CSS grid:

- **Left** — `SessionListPanel`, `EngineSelectorPanel`, `VaultStatusPanel`.
- **Center** — `ChatPanel`.
- **Right** — `EnvelopeViewerPanel`, `RuntimePanel`.

It is styled by `styles/cockpitV2.css` (`cv2-*` classes).

### State — `cockpitStore`

CockpitV2 uses `state/cockpitStore.ts` — a minimal external store backed by
React's `useSyncExternalStore` (no Redux, no Zustand, no new dependency). It is
imported only by `CockpitV2.tsx` and `components/cockpitV2/*`. All backend
access reuses `lib/api.ts` and `services/*`; the store adds no endpoints.

The store has **six slices**, each exposing `{ state, selectors, actions }`:

- `auth` — `status` (`anon` / `authing` / `authed` / `error`), `user`,
  `sessionId`; actions `login`, `logout`.
- `session` — the operator's session list (`fetchSessions`) and `selectedId`.
- `engine` — the selected `EngineId`.
- `vault` — the continuity snapshot (`fetchContinuitySnapshot`).
- `runtime` — the runtime envelope (`fetchRuntimeEnvelope`).
- `envelope` — the per-session envelope (`markovEnvelopeLatest`); stale
  responses are ignored.

`useCockpit(selector)` is the React binding. `bootstrapCockpit()` fires the
initial `session` and `vault` loads after authentication; the `runtime` slice
is loaded by `RuntimePanel` itself (on mount, then a 10-second poll).

## What the Cockpit is not

The following appear in earlier design material but exist in no code: a "State
Engine panel," a "Drift indicator," a "Layer pipeline" panel, an "Active
processes" panel, and a "Geometry alignment indicator." The real cockpit panels
are the ones listed above.
