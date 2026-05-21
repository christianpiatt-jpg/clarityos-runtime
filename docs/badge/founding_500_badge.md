# Founding 500 Badge

## Overview

`web/src/routes/Unit84/Founding500Badge.tsx` (v74 / Unit 84) is an atomic
component — a single inline-flex pill. It is part of the Founding 500
Subscription Gate (`/founding500/confirm`).

## Content

The badge renders two fixed strings:

- Header — `Founding 500`.
- Body — `Fixed lifetime pricing. Founder's Circle membership.`

Both are constants in the component. The badge takes no props and holds no
state. It carries `role="status"` and `aria-label="Founding 500 membership
badge"`.

## Visual

Styled by `Unit84.module.css` (`.badge`): a black (`--os-void`) inline-flex pill
with a 1px cyan (`--os-focus`) border, cyan text, monospace type, uppercase,
`0.20em` letter-spacing. It pulses opacity `1.0 → 0.7 → 1.0` on a two-second
cycle and carries a cyan glow (`box-shadow: 0 0 15px rgba(0,240,255,0.55)`) —
the only glow permitted by the Unit 84 "Somatic" design system.

## What the badge is not

There is no pentagon frame, no "cyan nucleus," and no serial number. There are
no badge tiers and no badge-progression system. The badge is a single fixed
pill.
