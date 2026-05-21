# V49 Readiness — Phone Threads UI

Status: ✅ Ready
Backend version: `4.3` (unchanged — phone-only pass)
Build: `20260507650000`

---

## What v49 ships

The mobile (Expo / React Native) surface for the v47 threads backend.
ClarityOS is now interactive across all three surfaces (backend → web →
phone) for threaded conversations: the user can list / create /
read / send-into / rename / delete threads from their device, with
the same encrypted vault persistence + kernel telemetry as the web
flow.

The list screen mirrors `memory_vault.tsx`'s shape (header card +
list of tappable rows). The detail screen uses
`session/[id].tsx`'s `KeyboardAvoidingView` pattern so the composer
stays above the keyboard, plus a native `Modal` for rename and an
`Alert.alert` confirmation for delete (matches mobile conventions —
the web flow used `window.confirm`).

No backend changes. No web changes.

---

## Files added / changed

### New
- `phone/app/threads.tsx` — list view: header (count + "+ NEW" CTA),
  scrollable card of tappable rows showing title +
  `N messages · relative timestamp`. Uses `useFocusEffect` so the
  list re-fetches when popping back from the detail screen.
- `phone/app/thread/[id].tsx` — detail view: header card (title +
  meta + Rename/Delete pill actions), scrollable message log with
  `Bubble` sub-component (user right-aligned, assistant left-aligned
  with model footer), composer at bottom inside `KeyboardAvoidingView`,
  rename `Modal`, delete via `Alert.alert` with destructive style.
- `V49_READINESS.md` (this file).

### Modified
- `phone/lib/api.ts`:
  - New types: `ThreadMeta`, `ThreadMessage`, `ThreadDetail`,
    `ThreadMessageResult`.
  - New helpers: `listThreads`, `createThread`, `getThread`,
    `postThreadMessage`, `renameThread`, `deleteThread`. Same
    `request()` wrapper as the rest of the file.
- `phone/app/_layout.tsx`:
  - `<Stack.Screen name="threads" options={{ title: "Threads" }} />`
  - `<Stack.Screen name="thread/[id]" options={{ title: "Thread" }} />`
- `phone/app/settings.tsx`:
  - New "Threads" card under "Memory Vault" routing to `/threads`.
- `BUILD_VERSION` — `20260507650000`.

No other phone files touched. No web or backend files touched.

---

## API helpers (mirror of web)

```ts
// phone/lib/api.ts (new exports)
export interface ThreadMeta {
  thread_id: string;
  title: string | null;
  created_at: number;
  updated_at: number;
  message_count: number;
  archived: boolean;
}

export interface ThreadMessage {
  role: "user" | "assistant" | "system";
  content: string;
  ts_ms: number;
  model: string | null;
}

export interface ThreadDetail        { meta: ThreadMeta; messages: ThreadMessage[] }
export interface ThreadMessageResult {
  meta: ThreadMeta;
  user_message: ThreadMessage;
  assistant_message: ThreadMessage;
  model_id?: string | null;
}

listThreads():                                Promise<ThreadMeta[]>
createThread(title?: string | null):          Promise<ThreadMeta>
getThread(thread_id):                         Promise<ThreadDetail>
postThreadMessage(thread_id, content):        Promise<ThreadMessageResult>
renameThread(thread_id, title):               Promise<ThreadMeta>
deleteThread(thread_id):                      Promise<void>
```

Identical signatures + types to the web client's helpers (v48). The
phone tests (when wired) can mock them the same way.

---

## Screen layout

### `/threads` (list)

* Header row: page title (`Threads`) + version subtitle
  (`v47 · N threads`) on the left; **+ NEW** pill button on the right.
  Tapping it calls `createThread(null)` and pushes to
  `/thread/{new_id}`.
* Empty state: `"No threads yet. Tap + NEW to start a conversation."`.
* Each thread row:
  * Title (fallback: `"Untitled Thread"`)
  * Meta: `N messages · relative timestamp`
  * Right chevron `›` for affordance.
  * Tappable; pushes `/thread/{thread_id}`.
* Refreshes via `useFocusEffect` so a delete on the detail screen
  reflects immediately when the user pops back.

### `/thread/{id}` (detail)

* On mount: `getThread(id)` populates `meta` + `messages`.
* While loading: full-pane `ActivityIndicator` + "Loading thread…".
* On load failure: error pane with `Retry` CTA.
* Header card:
  * Title (`Untitled Thread` fallback) + meta line
    (`N messages · updated Xm ago`).
  * Action pills: **Rename** (opens modal) and **Delete** (red border,
    triggers `Alert.alert` confirmation).
  * The native nav header title is set via `navigation.setOptions`
    so the OS-level back button shows the thread title.
* Message log:
  * `ScrollView` with `onContentSizeChange` → auto-scrolls to bottom
    after sends + initial load.
  * `Bubble` per turn:
    * user → right-aligned, elevated background.
    * assistant → left-aligned, deep background, model id rendered
      in dim Menlo under the bubble.
  * Empty: `"No messages yet — say something below to start."`.
* Composer (fixed at the bottom inside `KeyboardAvoidingView`):
  * `multiline` `TextInput` (40–140 px tall).
  * `Send` pill button. Disabled while empty / whitespace-only /
    `busy === "send"`.
  * On send: `postThreadMessage(id, draft.trim())`, append both
    messages locally, scroll to bottom.
* Rename modal:
  * Native `Modal` (transparent backdrop + centered card).
  * `TextInput` with current title pre-filled, `Cancel` / `Save`.
* Delete:
  * `Alert.alert` with destructive `Delete` action.
  * On success: `router.back()` returns to the list (which
    re-fetches via `useFocusEffect`).

---

## Navigation

```
phone/app/_layout.tsx
  + <Stack.Screen name="threads"      options={{ title: "Threads" }} />
  + <Stack.Screen name="thread/[id]"  options={{ title: "Thread"  }} />

phone/app/settings.tsx
  + Threads card → router.push("/threads" as any)
```

The `as any` cast on `router.push` matches the existing pattern
elsewhere in `phone/app` — expo-router's typegen runs as part of
`expo prebuild` and isn't always fresh in CI; every other custom
screen in the codebase uses the same cast (see `/operator_profile`,
`/macro_runs`, `/memory_vault`, etc.).

---

## Type-check

`npx tsc --noEmit` reports zero errors in any v49 file
(`phone/lib/api.ts` thread block, `phone/app/threads.tsx`,
`phone/app/thread/[id].tsx`, `phone/app/_layout.tsx`,
`phone/app/settings.tsx`). Pre-existing errors in unrelated screens
(`/macro_runs`, `/regional`, etc. — all expo-router typegen casts the
codebase already had) are unchanged.

---

## Tests

Phone tests are explicitly optional in the v49 spec because the
project ships no test runner. None added in this pass; if a future
pass wires Jest + RN Testing Library, the v49 surfaces are easy to
test the same way the v48 web tests are written:

* mock `phone/lib/api.ts` at module scope
* render `<ThreadsScreen />` → assert list + tap behaviour
* render `<ThreadDetailScreen />` with `useLocalSearchParams` mocked
  → assert send + rename + delete flows

Backend regression: 667 backend tests still pass. Web regression:
8 v48 tests still pass. Nothing broke.

---

## Cross-surface parity check

| Capability                  | Backend | Web    | Phone  |
|-----------------------------|---------|--------|--------|
| List threads                | v47     | v48    | v49    |
| Create thread               | v47     | v48    | v49    |
| Open thread → messages      | v47     | v48    | v49    |
| Send message + assistant    | v47     | v48    | v49    |
| Rename thread               | v47     | v48    | v49    |
| Delete thread               | v47     | v48    | v49    |
| Encrypted vault storage     | v46     | n/a    | n/a    |
| Kernel-routed model picker  | v44/v47 | passes through | passes through |
| Model footer on assistant   | —       | v48    | v49    |

ClarityOS is now fully interactive across all three surfaces for
threaded conversations.

---

## Notes / follow-ups

- The composer uses the standard mobile send button (no Cmd/Ctrl+Enter
  keyboard shortcut — keyboards on phones don't have those reliably).
- Delete uses `Alert.alert` with `destructive` style instead of a
  custom modal — matches platform UX conventions and gives the
  system-level "Delete" red text on iOS automatically.
- The `useFocusEffect`-on-return pattern keeps the list authoritative
  without an explicit refresh button. If the user goes back-forward
  rapidly it re-fetches each time, which is fine at vault scale.
- Rename uses a transparent `Modal` because the navigation header
  is already busy with title + back button. A future pass could
  replace it with a header right-aligned text-input swap, but the
  modal pattern keeps the screen clean.
- Backend stays `4.3`. Only `BUILD_VERSION` bumps for the phone-only
  deploy.
