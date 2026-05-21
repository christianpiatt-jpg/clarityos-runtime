# Geometry System

## Overview

The ClarityOS "geometry system" is its **design-token system** — the colours,
spacing, sizing, radii, typography, borders, and effects from which every UI
surface is composed. The term is the implementation's own: `web/src/v1-tokens.css`
declares itself the "single source of truth for v1 surface geometry." There is
no shape language and no geometric-primitive system; geometry here means the
token set.

## Token files

The web app carries two coexisting token files:

- `web/src/styles/tokens.css` — the `--os-*` tokens; the "operator cockpit"
  palette and the single source of truth for the SPA.
- `web/src/v1-tokens.css` — the `--color-*` / `--space-*` / `--font-*` /
  `--radius-*` tokens; the source of truth for the v1 surface. v1 components
  reference only these.

The two sets coexist: v1-surface components use the `v1-tokens.css` set; the
rest of the SPA uses the `--os-*` set.

## `tokens.css` — operator cockpit tokens

**Surface:** `--os-void` `#000000` · `--os-deep` `#0a0a0a` · `--os-surface`
`#111111` · `--os-elevated` `#1a1a1a`

**Boundaries and accents:** `--os-boundary` `#E02020` (red — frame, danger,
discard) · `--os-focus` `#00F0FF` (cyan — active, focus, primary action) ·
`--os-focus-deep` `#2563eb` · `--os-focus-violet` `#8b5cf6`

**Text:** `--os-text-primary` `#FFFFFF` · `--os-text-secondary` `#A0A0A0` ·
`--os-text-tertiary` `#585858`

**Lines and washes:** `--os-line` `rgba(255,255,255,0.06)` · `--os-line-strong`
`rgba(255,255,255,0.16)` · `--os-surface-wash` `rgba(0,0,0,0.4)` ·
`--os-nav-wash` `rgba(0,0,0,0.7)`

**Status:** `--os-ok` `#4ade80` · `--os-warn` `#fbbf24` · `--os-err`
(= `--os-boundary`)

**Typography:** `--font-sans` — Inter · `--font-mono` — JetBrains Mono

**Sizing:** `--frame` `20px` · `--gap` `12px` · `--gap-lg` `20px` · `--pad`
`12px` · `--rail-w` `220px` · `--status-h` `36px` · `--topbar-h` `56px` ·
`--radius-0` `0` · `--radius-sm` `4px` · `--radius-md` `8px`

**Effects:** `--shadow-card` `0 4px 24px rgba(0,0,0,0.5)` · `--focus-ring`
`0 0 0 2px rgba(0,240,255,0.45)`

## `v1-tokens.css` — v1 surface tokens

**Spacing:** `--space-outer` `24px` · `--space-inner` `16px` · `--space-gap`
`12px`

**Layout widths:** `--sidebar-width` `240px` · `--insights-width` `320px`

**Borders:** `--border-1` `1px solid rgba(255,255,255,0.15)` · `--border-cyan`
`2px solid #00F0FF` · `--border-red` `2px solid #E02020`

**Radii:** `--radius-none` `0px` · `--radius-small` `4px`

**Colors:** `--color-bg-void` `#000000` · `--color-bg-surface` `#0A0A0A` ·
`--color-bg-surface-alt` `#111111` · `--color-text-primary` `#FFFFFF` ·
`--color-text-secondary` `#888888` · `--color-accent-cyan` `#00F0FF` ·
`--color-accent-red` `#E02020`

**Typography:** `--font-sans` · `--font-mono` · `--font-size-base` `14px` ·
`--font-size-small` `12px` · `--line-height-chat` `1.5` · `--line-height-data`
`1.2`

**Gridlines:** `--gridline-cyan` `rgba(0,240,255,0.15)`

## Shared design language

Both token sets express one design language:

- Black void background; layered dark surfaces.
- Cyan (`#00F0FF`) for focus, activity, and primary action.
- Red (`#E02020`) for boundary, danger, and discard.
- White primary text; muted greys for secondary text.
- Sans (Inter / system-ui) for prose; monospace (JetBrains Mono) for data.
- Small radii (`0` / `4px` / `8px`); thin 1px lines; one card shadow and one
  cyan focus ring. No gradient primitives and no decorative glow.

## Other surfaces

- The phone app carries a parallel token system, `designSystem.ts`, which
  `tokens.css` mirrors in intent (high-contrast, minimal).
- The public marketing site (`public_site/assets/css/style.css`) defines its
  own separate scale — an `8px` base unit with a `--space-1` … `--space-12`
  step set — and is governed by neither the `--os-*` nor the `v1-tokens.css`
  set.
