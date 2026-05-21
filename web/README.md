# ClarityOS Web — operator surface (SPA)

React + Vite SPA. Replaces the prior static HTML site. Talks to the
existing Cloud Run backend over HTTP — no backend route changes.

## Layout

```
web/
  package.json, vite.config.ts, tsconfig.json, index.html
  src/
    main.tsx                React entry
    App.tsx                 routes
    styles/
      tokens.css            design tokens (cockpit palette)
      app.css               component + layout styles
    components/
      Layout.tsx            cockpit shell (top bar, left rail, status bar)
      RequireAuth.tsx       auth gate for protected routes
    lib/
      api.ts                fetch wrapper, X-Session-ID, retry, profile cache
      auth.ts               auth store + subscribe
      config.ts             API base resolution (localStorage → env → default)
      vault.ts              localStorage vault (mirrors phone schema)
      continuity.ts         localStorage continuity + thread reads
    routes/
      Home.tsx              landing
      Login.tsx             POST /login
      Operator.tsx          admin: invite minting, envelope, Terrace-1 cap
      Markov.tsx            POST /markov + history; pushes MQC to status bar
      System.tsx            /health + /config + env + API base override
      Account.tsx           /me view + sign-out
      Sessions.tsx          local conversation threads (read-only)
      Continuity.tsx        local resume options
      Vault.tsx             local notes/sessions browser
      Library.tsx           placeholder
      Plans.tsx             tiers + Terrace-1 state
      NotFound.tsx          404
  dev_proxy.py              kept for legacy Python-based dev server use
  README.md
```

## Run it

```bash
cd web
npm install
npm run dev
```

Vite serves at `http://localhost:5173`. The dev server proxies `/api/*` to
the Cloud Run backend you specify via `VITE_API_TARGET` (or it falls back
to the placeholder URL — set this).

### Configure the backend URL

Three layers, last wins:

1. **localStorage** override — set in System → API base override (per-browser).
2. **`VITE_API_BASE`** — env var read at build time, used as the absolute URL.
3. **Default** in `src/lib/config.ts` — currently `https://clarity-engine-PLACEHOLDER.run.app`. Replace before shipping.

For local dev the easiest path is:

```bash
echo "VITE_API_TARGET=https://clarity-engine-xxxxx.run.app" > .env.local
```

Then visit `http://localhost:5173` and use the System screen to confirm the probe is green.

## Backend coupling (existing endpoints only)

| Route | Used by | Auth |
|---|---|---|
| `POST /login` | Login | no |
| `GET /me` | Layout, Account, Operator | yes |
| `GET /config` | Operator, Plans, System | yes |
| `GET /health` | Layout (status bar), System | no |
| `POST /markov` | Markov QC | yes |
| `POST /invite/create` | Operator (admin) | yes (founder cohort) |

Sessions, Continuity, Vault, Library are **local-only** — same shape as
the phone app's stores so a future sync layer would unify them without
schema changes. No new backend routes were added.

## Build for production

```bash
npm run build
```

Output goes to `dist/`. Deploy with any static host:

- **Cloud Storage static website** — `gsutil rsync -r dist gs://your-bucket/`
- **Cloud Run** — sibling service that serves `dist/` via nginx
- **Netlify / Cloudflare Pages / Vercel** — point at the `dist/` folder

For SPA routing on a static host, configure a fallback to `index.html`
so deep links like `/operator` resolve client-side.

## What was retired

The previous static HTML pages (`*.html`) and `assets/{js,css}` modules
were replaced by this SPA. `dev_proxy.py` is kept as a legacy
Python-based dev server option for anyone who prefers that path; the
Vite dev server (`npm run dev`) is the primary tool now.
