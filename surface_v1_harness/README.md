# ClarityOS — Surface v1 Harness

Isolated Vite + React 18 harness for visually verifying the v1
Computer Surface module set. Renders `<ClarityOSSurface />` against
the canonical `tokens.css` in a blank shell.

## Install

```bash
npm install
```

## Run

```bash
npm run dev
# open http://127.0.0.1:5173
```

## Typecheck

```bash
npm run typecheck
```

## Build

```bash
npm run build
```

## Scope

This harness exists to prove geometry before any integration.
Out of scope: routing, auth, API client, animations, real backend
data, production build optimizations beyond Vite defaults.

Integration into the desktop client is Surface 3.
Integration into the web client is Surface 4.
