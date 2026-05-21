# ClarityOS — Desktop Client

Double-click launcher for ClarityOS Threads + Memory Vault. The
desktop client is an Electron app that hosts a small React chat UI
talking to the existing ClarityOS Cloud Run backend.

```
desktop/
├── electron.js          ← Electron main process (window + menu + IPC)
├── preload.js           ← contextBridge — narrow IPC surface
├── index.html           ← renderer shell with hardened CSP
├── vite.config.ts       ← renderer build config (port 5174)
├── tsconfig.json
├── package.json         ← scripts + electron-builder config
├── icon/
│   ├── icon.svg          ← source artwork (placeholder — swap with the real PM file)
│   ├── icon-source.png   ← (optional) drop a real 1024×1024 PNG here
│   ├── build_icons.py    ← deterministic icon-set generator (PIL)
│   ├── icon.png          ← 1024×1024 (Linux + cross-platform fallback)
│   ├── icon@2x.png       ← 2048×2048 (retina)
│   ├── icon-{32,64,128,256,512}.png
│   ├── icon.ico          ← Windows multi-size .ico
│   └── icon.icns         ← macOS bundle (built on Mac with iconutil)
└── src/
    ├── main.tsx
    ├── App.tsx           ← auth gate + sign-in screen
    ├── ChatWindow.tsx    ← shell: sidebar + main pane + rename modal
    ├── ThreadList.tsx
    ├── ThreadView.tsx    ← message log with auto-scroll
    ├── Composer.tsx      ← Cmd/Ctrl+Enter to send
    ├── styles.css
    └── lib/
        └── api.ts        ← /me + /me/threads + /me/threads/{id}/summarize
```

---

## First-time setup

```bash
cd desktop
npm install
```

This pulls in Electron, Vite, React, and the test/build chain (~485
packages, mostly dev-only).

You'll also need the icon set:

```bash
python icon/build_icons.py
```

That produces every PNG size + the `.ico`. On macOS it also builds
`icon.icns` via `iconutil` (no-op on Windows / Linux — see
`icon/ICNS_NOT_BUILT.txt`).

---

## Configuration

The renderer reads the backend URL from `VITE_API_BASE`. For local
development pointing at a Cloud Run deploy:

```bash
# desktop/.env.local
VITE_API_BASE=https://clarity-engine-xxxxxx.run.app
```

Without this, the build falls back to a placeholder URL and the chat
shell will surface a clear error on first list-threads call.

---

## Running in development

```bash
npm run dev
```

This runs Vite on `http://localhost:5174` and Electron in parallel
(via `concurrently`). The Electron window loads the dev server with
DevTools open. Hot-reload works on the React side; restart the dev
script to pick up Electron main-process changes.

If you'd rather run them separately (debugging Electron alone):

```bash
npm run dev:vite          # one terminal
npm run dev:electron      # another (waits on the dev server)
```

---

## Building a production package

The full pipeline is `npm run package`:

```bash
npm run package           # current platform
npm run package:mac
npm run package:win
npm run package:linux
```

Outputs land in `desktop/release/`:

* `ClarityOS-0.1.0.dmg`        (macOS)
* `ClarityOS-Setup-0.1.0.exe`  (Windows installer)
* `ClarityOS-0.1.0.exe`        (Windows portable)
* `ClarityOS-0.1.0.AppImage`   (Linux)
* `ClarityOS-0.1.0.deb`        (Debian/Ubuntu)

Drop any of these on the desktop and double-click to launch.

`electron-builder` config lives in `package.json#build`. The icon
paths there assume the `icon/` directory has been populated by
`build_icons.py` first.

---

## Swapping in the real PM artwork

The repo ships a deterministic placeholder icon (pyramid + sphere +
accent halo) so the build pipeline works out of the box. To use the
real PM artwork:

1. Drop the master file into `desktop/icon/icon-source.png`. A
   square 1024×1024 transparent-background PNG is ideal; the script
   accepts non-square sources and pads to square.
2. Re-run `python icon/build_icons.py`.

Every PNG size, the `.ico`, and (on macOS) the `.icns` regenerate
from your master. The `icon.svg` stays in place as documentation —
update or replace it freely; only `icon-source.png` (when present)
drives the raster output.

If you'd rather use the SVG path: install `cairosvg` and add a
`cairosvg.svg2png(...)` branch at the top of `_resolve_master()` in
`build_icons.py`. The current rasteriser keeps the dependency
footprint small (Pillow only).

---

## Keyboard shortcuts

| Shortcut                | Action                          |
|-------------------------|---------------------------------|
| `Cmd/Ctrl + N`          | New thread                      |
| `Cmd/Ctrl + Enter`      | Send message                    |
| `Cmd/Ctrl + W`          | Close window (system default)   |
| `Esc` (in rename modal) | Cancel rename                   |

`Cmd/Ctrl + N` is bound at two layers:

* The Electron main process menu (`File → New Thread`) emits an IPC
  message; the renderer subscribes via the preload bridge.
* The React tree also installs a `keydown` listener so the same
  shortcut works in browser-mode dev where the Electron menu isn't
  attached.

---

## Backend integration

The renderer talks directly to the existing ClarityOS backend via
HTTPS — no IPC for API calls. Same routes as `web/src/lib/api.ts`:

* `POST /login`
* `GET  /me`
* `GET  /me/threads`
* `POST /me/threads`
* `GET  /me/threads/{id}`
* `POST /me/threads/{id}/message`
* `POST /me/threads/{id}/rename`
* `POST /me/threads/{id}/delete`
* `POST /me/threads/{id}/summarize`

Auth uses the same `X-Session-ID` header as the web client. No local
persistence of message data — every read/write hits the vault on the
server. Session token is held in `localStorage` when available
(jsdom-style fallback to in-memory when not).

No backend changes were needed for v50 desktop — it consumes the
existing v47–v50 thread endpoints unchanged.

---

## Troubleshooting

* **Sign-in fails with `network_error`** — `VITE_API_BASE` isn't set,
  or the backend is unreachable. Set it in `desktop/.env.local` and
  rebuild (`npm run build`) or restart `npm run dev`.
* **App launches with broken icon** — `build_icons.py` hasn't been
  run. Run it; restart `npm run package`.
* **macOS won't run the unsigned `.app`** — Gatekeeper. Right-click
  → Open the first time, or sign with `codesign` before packaging.
  Production deploys should add a signing identity to
  `package.json#build.mac.identity`.
* **Cmd/Ctrl+N does nothing** — make sure DevTools isn't focused
  (it eats the shortcut). Closing the detached DevTools window
  restores the shortcut.

---

## Versioning

This client is part of the ClarityOS v50 line:

* `BUILD_VERSION` (root) → `20260507670000`
* `V50_DESKTOP_CLIENT_READINESS.md` documents the full deliverable.
* Backend version stays at `4.4` (Threads + Summaries from v47/v48/v50).
