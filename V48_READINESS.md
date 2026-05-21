# V48 Readiness — Web Threads UI

Status: ✅ Ready
Backend version: `4.3` (unchanged — frontend-only pass)
Build: `20260507640000`

---

## What v48 ships

A web client surface for the v47 threaded-interaction backend. Adds
six API helpers, a new `/threads` route with a two-column layout
(thread list ↔ detail/composer), nav rail entry, and a vitest test
harness with eight passing tests for the route.

The page reads `/me/threads`, lets the user create / select / send /
rename / delete threads, and shows assistant replies with the model
id under each bubble. Style matches the existing Account / Vault
panels (CSS classes like `.panel`, `.panel-grid`, `.list-item`,
`.btn`, `.input`, `.banner err` from `app.css`) — no new design
system added.

A first-class web test runner (vitest + @testing-library/react +
jsdom) is now wired into the project; previous passes had no test
infrastructure on the web side.

---

## Files added / changed

### New
- `web/src/routes/Threads.tsx` — two-column page, list + detail +
  composer, rename modal, delete with confirm, optimistic list
  update on send.
- `web/src/routes/__tests__/Threads.test.tsx` — 8 vitest tests.
- `web/src/test-setup.ts` — jest-dom matchers + `scrollIntoView`
  jsdom shim.
- `V48_READINESS.md` (this file).

### Modified
- `web/src/lib/api.ts`:
  - New types: `ThreadMeta`, `ThreadMessage`, `ThreadDetail`,
    `ThreadMessageResult`.
  - New helpers: `listThreads`, `createThread`, `getThread`,
    `postThreadMessage`, `renameThread`, `deleteThread`. Same
    `request()` wrapper as the rest of the file (auth header,
    error envelope, retry-able).
- `web/src/App.tsx`:
  - Imports `Threads` route.
  - `/threads` registered behind `RequireAuth`.
- `web/src/components/Layout.tsx`:
  - New `CONVERSE` rail section with `Threads` link.
- `web/package.json`:
  - Added devDependencies: `vitest`, `@testing-library/react`,
    `@testing-library/jest-dom`, `@testing-library/user-event`,
    `jsdom`.
  - Added scripts: `"test": "vitest run"`, `"test:watch": "vitest"`.
- `web/vite.config.ts`:
  - `/// <reference types="vitest" />` triple-slash directive.
  - `test` block: `environment: "jsdom"`, `globals: true`,
    `setupFiles: ["./src/test-setup.ts"]`,
    `include: ["src/**/*.test.{ts,tsx}"]`, `css: false`.
- `BUILD_VERSION` — `20260507640000`.

No backend changes. No other web files touched.

---

## API helpers

```ts
// web/src/lib/api.ts (new exports)
export interface ThreadMeta {
  thread_id: string
  title: string | null
  created_at: number
  updated_at: number
  message_count: number
  archived: boolean
}

export interface ThreadMessage {
  role: "user" | "assistant" | "system"
  content: string
  ts_ms: number
  model: string | null
}

export interface ThreadDetail        { meta: ThreadMeta; messages: ThreadMessage[] }
export interface ThreadMessageResult {
  meta: ThreadMeta
  user_message: ThreadMessage
  assistant_message: ThreadMessage
  model_id?: string | null
}

listThreads():                                 Promise<ThreadMeta[]>
createThread(title?: string | null):           Promise<ThreadMeta>
getThread(thread_id):                          Promise<ThreadDetail>
postThreadMessage(thread_id, content):         Promise<ThreadMessageResult>
renameThread(thread_id, title):                Promise<ThreadMeta>
deleteThread(thread_id):                       Promise<void>
```

All helpers go through the same `request()` wrapper as the rest of
the file — auth header, JSON envelope, network-error → ApiError.

---

## Route layout

`/threads` (auth) — two-column grid via `panel-grid`:

* **Left column — Thread list**
  * Header panel with title, count badge, and `+ NEW` button.
  * Scrollable `list-item` buttons sorted by `updated_at` desc.
  * Each row shows: tag pill (`thread`), relative timestamp,
    title (`Untitled Thread` fallback), message count.
  * Selected row gets `--os-elevated` background + `--os-focus` border.

* **Right column — Active thread**
  * Empty placeholder when no thread selected: "Pick a thread on
    the left, or click + NEW to start a new one."
  * `Loading thread…` spinner while `getThread` is in flight.
  * "Thread not found" if the call returns null.
  * Active panel:
    * Header: title (h2) + meta line (`N messages · updated Xm ago`)
      with `RENAME` + `DELETE` actions.
    * Rename mode replaces the header with an inline input + SAVE/CANCEL.
    * Message log: `Bubble` per turn. User bubbles right-aligned,
      assistant bubbles left-aligned, model id rendered in dim
      monospace under assistant bubbles.
    * Composer: textarea + SEND button + char counter.
    * Cmd/Ctrl + Enter sends; plain Enter inserts a newline.

* On send, the active thread's meta is bumped and pushed to the top
  of the list optimistically (matches what the backend will return
  on the next list refresh).
* On delete, the thread is removed from the list and the right pane
  returns to the placeholder.

---

## Nav

Rail nav (left side) gets a new section:

```
CONVERSE
  Threads → /threads
```

Sits below `OPERATOR ENVELOPE`. Visible to authenticated users (the
route itself is gated by `RequireAuth`).

---

## Tests

```
web/src/routes/__tests__/Threads.test.tsx — 8 tests, all pass
$ npm test
  Test Files  1 passed (1)
       Tests  8 passed (8)
```

Coverage:

1. **List renders threads in `updated_at` desc order**
   Two threads → newer renders before older; header count badge
   shows `2 threads`.
2. **Clicking a thread loads its messages**
   `getThread` is called with the right id; rendered bubbles include
   user + assistant content + assistant model line.
3. **Sending a message renders the assistant reply**
   Composer accepts input, `postThreadMessage` is called with
   `(thread_id, content)`, both bubbles appear after the await.
4. **Creating a new thread refreshes the list and selects it**
   Empty initial list → `+ NEW` triggers `createThread`; new thread
   is auto-selected; null-titled detail header shows
   "Untitled Thread".
5. **Rename updates the thread title**
   Rename form replaces the header → typing + SAVE calls
   `renameThread(id, "New name")` → header re-renders with the new
   title.
6. **Delete removes the thread from the list**
   `window.confirm` stubbed to true; `deleteThread(id)` is called;
   list excludes the deleted thread; right pane returns to the
   "Pick a thread" placeholder.
7. **Send button is disabled while composer is empty**
   Whitespace-only content keeps SEND disabled; non-empty content
   enables it.
8. **Empty state copy renders when no threads exist**
   `No threads yet. Click + NEW to start a conversation.`

API helpers are mocked at module scope via
`vi.mock("../../lib/api", ...)`. The tests don't hit the real
`request()` wrapper or any storage / fetch.

### Test infrastructure (new)

This pass also adds the missing web test runner. Previous passes
shipped no `*.test.tsx` files because no framework was installed.
After `npm install`:

* `npm test` runs the suite once (`vitest run`).
* `npm run test:watch` runs in watch mode.
* `vite.config.ts` has a `test` block enabling `jsdom`,
  `globals: true`, `setupFiles: ["./src/test-setup.ts"]`.
* `src/test-setup.ts` imports `@testing-library/jest-dom/vitest`
  matchers and shims `Element.prototype.scrollIntoView` (jsdom
  doesn't ship it; `Threads.tsx` calls it after every send).

The TS strict-mode type check (`npx tsc --noEmit`) reports
zero errors in any v48 file. Pre-existing v41/v42/v43 errors in
`ElinsQuicklook.tsx`, `FounderBillingPanel.tsx`, and `ELINSInspector.tsx`
are unchanged.

---

## Notes / follow-ups

- The composer uses Cmd/Ctrl + Enter for send (familiar from chat
  apps). Plain Enter inserts a newline so multi-line prompts don't
  surprise-send. If a future UX pass wants a "send on Enter" toggle
  it goes in `onComposerKeyDown` — single line change.
- The list's optimistic reorder on send mirrors the server's
  `updated_at`-desc behaviour. If the user rapidly fires N sends in
  different threads, the local order tracks the backend without
  needing a full list refresh.
- Rename uses an inline form (no modal). Delete uses the native
  `window.confirm` (mirrors Vault.tsx's pattern).
- The `model_id` from `postThreadMessage` is wired through to the
  assistant bubble's footer (small dim mono text). The backend
  always returns it for v47, so the UI doesn't gate on the field.
- Backend version stays `4.3`. Only `BUILD_VERSION` bumps for the
  frontend-only deploy.
