# ClarityOS Phone

React Native + Expo wrapper for the ClarityOS runtime. Mirrors the
website's visual identity (orb, dark surface, cyan↔violet accent) and
talks to the same Cloud Run backend over HTTPS.

## Layout

```
phone/
  package.json, app.json, tsconfig.json, babel.config.js
  app/                       Expo Router (file-based) — each file is a route
    _layout.tsx              root stack, theme, auth bootstrap
    index.tsx                Home: orb, node status, engine mode, sessions list
    login.tsx                Sign in / register
    session/[id].tsx         Session detail: console + paste / send-to-AI / done
    settings.tsx             Backend URL, account, AI provider, vault, mode model
    vault.tsx                On-device vault: list of saved notes + sessions
  components/
    Orb.tsx                  SVG orb (animated halo)
    NodeStatus.tsx           local + cloud node cards with status pill
    EngineToggle.tsx         segmented control (mode #c / #G + engine choice)
    ConsoleLine.tsx          single log line in the runtime console
    TagSaveModal.tsx         preview + suggested tags + comma-separated tags
    Toast.tsx                fading snackbar
  lib/
    api.ts                   fetch wrapper, X-Session-ID, error envelope
    config.ts                API base URL (env > app.json > placeholder)
    storage.ts               AsyncStorage keys + getAIProvider/setAIProvider
    theme.ts                 design tokens — mirrors web/.../clarityos.css
    vault.ts                 expo-file-system store for notes + sessions
    providers/               AI provider routing layer
      types.ts               AIProvider, ProviderId, ProviderResult
      ClaudeProvider.ts      claude.ai/new + clipboard
      ChatGPTProvider.ts     chat.openai.com + clipboard
      GeminiProvider.ts      gemini.google.com + clipboard
      CopilotProvider.ts     copilot.microsoft.com + clipboard
      LocalProvider.ts       on-device LLM stub
      index.ts               getProviders / getProviderById
```

## Run it

You need Node 20+ and Expo CLI (or use `npx`). On Windows you can use
PowerShell or Git Bash.

```bash
cd phone
npm install
npx expo start
```

Then either:

- Press **i** to open the iOS simulator (macOS only, needs Xcode).
- Press **a** to open the Android emulator (needs Android Studio AVD).
- Press **w** to run as a web app in your browser.
- Or scan the QR code in the **Expo Go** app on your physical phone.

## Configure the backend URL

Three layers, last wins:

1. **Default**: hard-coded placeholder in `app.json` under
   `extra.apiBase`. Replace `clarity-engine-PLACEHOLDER.run.app` with
   your real Cloud Run URL before shipping.
2. **Build-time env override**: set `EXPO_PUBLIC_CLARITYOS_API_BASE` in
   the shell where you run `expo start` / build. Inlined at bundle time.
3. **Runtime override**: open Settings inside the app and paste a URL.
   Persists in AsyncStorage so it survives restarts. Useful for QA
   builds pointing at staging.

```bash
# Build-time:
EXPO_PUBLIC_CLARITYOS_API_BASE=https://clarity-engine-xxxxx.run.app npx expo start
```

## Local vs cloud compute

The mode toggle (`#c` / `#G`) appears in the Home screen and again in
each session's toolbar. Selection persists in AsyncStorage.

- **`#c` — local compute**: calls `localCompute(engine, text)` in
  `lib/api.ts`. Today this is a deliberate stub that mirrors the
  backend's stub envelope shape so the UI handles both paths
  uniformly. Replace the body of `localCompute` when you have a real
  on-device engine (ONNX, executorch, llama.cpp via a native module,
  etc.). The contract stays the same.
- **`#G` — cloud compute**: calls `api.markov / galileo / tizzy` which
  hit the Cloud Run backend with `X-Session-ID`. No conditional code
  in the screens — the toggle picks which function runs.

Threads are local-first: every conversation lives in AsyncStorage under
`clarityos_threads`. The cloud only sees what you forward via a `#G`
prompt. Switching mode mid-thread is fine — engines are stateless and
context belongs to the device.

## Universal AI client + local vault

The phone app is a routing layer over multiple external AI providers
plus a private on-device vault. Nothing in this section talks to the
ClarityOS Cloud Run backend.

### AI provider selection (Settings → AI Provider)

Pick one of: Claude, ChatGPT, Gemini, Copilot, Local. The choice
persists in AsyncStorage under `clarityos.aiProvider`. Today none of
the consumer AI sites accept a prefilled prompt via URL, so each
provider:

1. Copies the prompt to the clipboard via `expo-clipboard`.
2. Opens the provider's `/new` (or root) URL via `Linking.openURL`.
3. Returns a message like *"Opened Claude. Prompt copied to clipboard
   — paste to send."*

Each provider file in `lib/providers/` has a `TODO` marking where to
swap in a real deep-link scheme (e.g. `claude://chat?prompt=...`,
`copilot.microsoft.com?q=...`) when one becomes available. The
`AIProvider` interface is small enough that swapping is a few-line
change with no UI knock-on.

`LocalProvider` is a stub that returns `{ success: false, message:
"Local provider not implemented yet" }`. When a real on-device LLM
ships (executorch / llama.cpp via a native module / WebGPU on Expo
Web, etc.) it goes here, contract unchanged.

### "Send to AI" (Session screen)

Type into the input, then tap **Send to {provider}** in the action
row. Reads the current text and the chosen provider, calls
`provider.sendMessage(text)`. If no provider is set, an alert offers
to open Settings. Nothing is stored beyond the current session
buffer.

### "Paste from clipboard" → Tag/Save (Session screen)

Tap **Paste**. The app reads the current clipboard via
`Clipboard.getStringAsync()` (one-shot — no polling, no background
listener), then opens `TagSaveModal` with the clipboard text as the
candidate note. On Save → `saveNote()` writes JSON under
`FileSystem.documentDirectory + 'vault/notes/{id}.json'` with
`source: 'ai'` and `providerId` set to the active provider. On
Cancel → modal closes, you stay on the screen.

### "Done / finished?" → Tag/Save session (Session screen)

Tap **Done** or use the system back gesture. If the session has any
log content, the same `TagSaveModal` opens prefilled with the joined
log text. On Save → `saveSession()` writes under `vault/sessions/`
and the screen pops. On Cancel → discards (per spec) and pops anyway.

The intercept is wired through React Navigation's `beforeRemove`
event in `app/session/[id].tsx`. An `allowLeaveRef` flag prevents an
infinite loop when we re-dispatch the pending nav action after the
user makes a choice.

### Vault (`/vault`)

Lists notes and sessions newest-first by `createdAt`, showing the
first non-empty line plus type and tags. Tapping an item opens a
modal with the full content. Reads from
`FileSystem.documentDirectory + 'vault/{notes,sessions}/'` on every
focus.

Storage is **strictly local**:
- No network calls.
- No sync.
- Vault is not cleared on sign-out (sign-out only removes session
  token, threads, and active-thread pointer).
- Wipe by uninstalling the app, or programmatically by deleting
  `FileSystem.documentDirectory + 'vault/'`.

## New dependencies

| Package | Purpose |
|---|---|
| `expo-clipboard@~6.0.3` | One-shot read/write of system clipboard for paste + provider hand-off |
| `expo-file-system@~17.0.1` | App-private JSON files for the local vault |

Both are Expo SDK 51 modules — auto-linked, no manual native config.
After pulling, run `npm install` once.

## Backend coupling

The mobile app calls these existing routes:

| Route | Method | Auth |
|---|---|---|
| `/login`, `/register` | POST | no |
| `/me`, `/config` | GET | yes |
| `/markov`, `/galileo`, `/tizzy` | POST | yes |
| `/library` (wired in `api.ts`, no UI yet) | POST | yes |
| `/health` | GET | no (probe on Home) |

No new routes. No backend changes. CORS doesn't apply on native
clients, so you do **not** need to add the phone to
`CLARITYOS_CORS_ORIGINS`.

## Why Expo + Expo Router

- Zero native toolchain needed for first run — `npx expo start` and a
  phone with Expo Go is enough.
- Expo Router gives file-based navigation that matches the website's
  page-per-file mental model, so the two surfaces stay shaped the same.
- Ejectable with `npx expo prebuild` if you ever need raw iOS/Android.
- Web target works as a fallback (`expo start --web`) — useful for
  rapid iteration on layout without booting a simulator.

## Visual identity parity

`lib/theme.ts` mirrors `web/assets/css/clarityos.css` `:root` tokens
verbatim. If you have authoritative tokens from Gemini's phone design,
update both files; every component pulls from `theme.ts` so a swap
ripples through the whole app.
