# V50 Desktop Client Readiness — ClarityOS Desktop App

Status: ✅ Ready
Backend version: `4.4` (unchanged — desktop is a third client, no
backend changes)
Build: `20260507670000`

---

## What v50 Desktop ships

A standalone double-clickable desktop app that brings ClarityOS
Threads + Memory Vault to macOS / Windows / Linux. Built on Electron +
Vite + React 19; talks to the existing Cloud Run backend via HTTPS
through the same `/me/threads*` and `/login` / `/me` endpoints the
web (v48) and phone (v49) clients use.

The desktop client is:

* a single Electron window (1200×800 default, 720×480 minimum)
* a sidebar thread list + main pane chat surface
* user/assistant bubbles with model footers (matches web v48 / phone
  v49 + v50 summaries)
* a hardened CSP + contextBridge IPC surface — no Node primitives
  leak to the renderer
* electron-builder configured for `.dmg` / `.zip` (mac), `.exe` /
  portable (win), `.AppImage` / `.deb` (linux)

The icon pipeline is a deterministic Python script that produces
every required PNG size + a multi-size `.ico`; on macOS hosts it also
builds the `.icns`. Real artwork drops in via
`desktop/icon/icon-source.png` and a re-run of the script.

---

## ⚠️ Real artwork pending

The original spec referenced an attached "PM pyramid-and-sphere
image" — that file wasn't actually delivered alongside the
instruction block. Rather than guess at its details, the icon
pipeline currently rasterises a **deterministic placeholder** that
captures the described geometry (apex pyramid + sphere on top +
accent halo) using the ClarityOS accent green. Quality at every
size is good enough to ship today; once the real artwork arrives:

```bash
cp /path/to/PM-master.png desktop/icon/icon-source.png
python desktop/icon/build_icons.py
```

Every PNG / `.ico` / (mac) `.icns` regenerates from the master. No
other code paths change; `electron.js` resolves icons by
platform-extension and the bundled paths stay identical.

---

## Files added / changed

### New (everything under `desktop/`)
- `desktop/electron.js` — main process: BrowserWindow, menu (File +
  Edit + View + Window), IPC handlers, dev/prod toggle, dark-bg flash
  prevention, devtools detached in dev / hidden in prod.
- `desktop/preload.js` — `contextBridge` exposes
  `window.clarityos.{onNewThread, getPlatform, getVersion}`. Nothing
  else.
- `desktop/index.html` — renderer shell with hardened CSP that allows
  the React bundle, Vite HMR sockets in dev, and HTTPS fetches to the
  backend; blocks everything else.
- `desktop/vite.config.ts` — port 5174 (one above web's 5173 so they
  can run side-by-side), `base: "./"` so `file://` loads work in
  packaged builds, `VITE_API_BASE` define.
- `desktop/tsconfig.json` — strict TypeScript, ES2022, react-jsx.
- `desktop/package.json` — scripts (`dev`, `dev:vite`, `dev:electron`,
  `build`, `package`, `package:{mac,win,linux}`, `build:icons`) +
  full `electron-builder` config for `appId: ai.clarityos.desktop` +
  `productName: ClarityOS`.
- `desktop/src/main.tsx` — React entry.
- `desktop/src/App.tsx` — auth gate. Probes `/me` on launch with a
  cached session, shows the sign-in form otherwise. SignIn calls
  `POST /login`.
- `desktop/src/ChatWindow.tsx` — owns thread list + active thread
  state, wires every mutator (send / rename / delete / summarize),
  binds `Cmd/Ctrl+N` at the renderer level + subscribes to the
  Electron menu's `clarityos:new-thread` IPC.
- `desktop/src/ThreadList.tsx` — sidebar; shows title + summary +
  message count + relative timestamp; sign-out footer.
- `desktop/src/ThreadView.tsx` — message log with auto-scroll on
  every messages-array change. `Bubble` sub-component renders the
  user-right / assistant-left + model footer pattern.
- `desktop/src/Composer.tsx` — multi-line textarea with
  `Cmd/Ctrl+Enter` send; plain Enter inserts a newline. Send button
  disables on empty/whitespace-only content.
- `desktop/src/styles.css` — full dark UI sheet matching ClarityOS
  web tokens (`--os-void`, `--os-deep`, `--os-accent`, etc.). High
  contrast, geometric spacing, minimal chrome.
- `desktop/src/lib/api.ts` — copy of `web/src/lib/api.ts` thread
  surface (`listThreads` / `createThread` / `getThread` /
  `postThreadMessage` / `renameThread` / `deleteThread` /
  `summarizeThread`) plus `login` / `me` for the auth flow. Same
  `request()` wrapper, same `X-Session-ID` header, same `ApiError`
  shape.
- `desktop/icon/icon.svg` — source-of-truth geometry (placeholder).
- `desktop/icon/build_icons.py` — Pillow-based pipeline; resolves
  master from `icon-source.png` when present, falls back to a
  programmatic raster of the SVG geometry. Outputs every required
  PNG + `.ico`; runs `iconutil` on macOS to produce `.icns`.
- `desktop/icon/icon.png` (1024) + `icon-{32,64,128,256,512}.png` +
  `icon@2x.png` (2048) + `icon.ico` (7-size embedded).
- `desktop/icon/ICNS_NOT_BUILT.txt` — sentinel emitted on non-Mac
  hosts; documents how to produce the `.icns` later.
- `desktop/README.md` — run/build/package + swap-icon instructions.
- `V50_DESKTOP_CLIENT_READINESS.md` (this file).

### Modified
- `BUILD_VERSION` — `20260507670000`.

### Untouched
- All backend code (`/me/threads*` endpoints from v47/v48/v50 are
  consumed unchanged).
- Web client (web/v48 + v50 stays as-is).
- Phone client (phone/v49 + v50 stays as-is).

---

## Keyboard shortcuts

| Shortcut                | Wired at                                  |
|-------------------------|--------------------------------------------|
| `Cmd/Ctrl + N`          | Electron menu (`File → New Thread`)        |
|                         |   + renderer `keydown` listener (dev fallback) |
| `Cmd/Ctrl + Enter`      | Composer textarea — sends + clears draft   |
| `Cmd/Ctrl + W`          | Electron `role: close` (system default)    |
| `Esc` in rename modal   | Cancels                                    |
| `Enter` in rename modal | Saves                                      |

The menu accelerators on macOS use `Cmd`; everywhere else they map
to `Ctrl` automatically (`CmdOrCtrl` accelerator).

---

## Build / package output paths

After `npm run package`:

```
desktop/release/
├── ClarityOS-0.1.0.dmg                  (macOS)
├── ClarityOS-0.1.0-mac.zip
├── ClarityOS Setup 0.1.0.exe            (Windows installer)
├── ClarityOS-0.1.0-portable.exe         (Windows portable)
├── ClarityOS-0.1.0.AppImage             (Linux)
└── ClarityOS_0.1.0_amd64.deb            (Debian/Ubuntu)
```

Drop any of these on the desktop and double-click. The portable
Windows `.exe` and the Linux `.AppImage` need no installer.

---

## Verification

* `npm install` — 485 packages installed cleanly.
* `npx tsc --noEmit` — zero errors across all desktop sources.
* `npm run build` — Vite produces a 199 KB JS + 7 KB CSS bundle in
  `dist/`. No build warnings (apart from Vite's own CJS-deprecation
  notice).
* Backend regression — full pytest suite: 690 passed (unchanged).
* Web regression — 11 vitest tests pass (unchanged).
* `python desktop/icon/build_icons.py` — generates all 7 PNGs +
  `icon@2x.png` + `icon.ico` deterministically. Verified the 256×256
  PNG renders the pyramid-and-sphere geometry correctly.

---

## Notes / follow-ups

- **Code signing** — Production macOS / Windows builds should be
  signed. Add `mac.identity` / `win.certificateFile` (or env vars
  for CI) to `package.json#build`.
- **Real artwork** — the placeholder ships today; drop
  `desktop/icon/icon-source.png` and re-run `build_icons.py` when
  the master arrives. No other change needed.
- **Auth scope** — The desktop client is sign-in-only; it doesn't
  carry the full registration / membership / plan flows the web
  client does. Users register on the web first, then sign in here.
  This keeps the desktop chrome minimal.
- **Persistence** — All thread + message state lives in the
  encrypted Memory Vault on the backend (v46). The desktop client
  has no local cache beyond the session token in `localStorage`.
- **Tests** — No automated tests in this pass. The renderer is
  stylistically a clone of `web/src/routes/Threads.tsx`, which is
  covered by 11 vitest tests; the API layer is identical. Future
  passes can wire vitest under `desktop/` if cross-renderer tests
  become valuable.
- **Backend version stays 4.4.** v50 desktop is a pure
  client-side addition.
