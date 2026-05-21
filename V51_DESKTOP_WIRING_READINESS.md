# V51 Desktop Client — Wiring against the project layer

Status: ✅ Ready
Backend version: `4.5` (unchanged — desktop-only pass)
Build: `20260507700000`

---

## What this pass ships

The Electron desktop client is now wired against the real v51
backend project layer. On launch it:

1. Loads the user's projects.
2. Creates `VA_LITIGATION` if it doesn't exist (via the literal
   `POST /me/projects` body the spec defined).
3. Filters threads through the new `?project_id=VA_LITIGATION`
   query.
4. Creates a starter `MSJ_OPPOSITION` thread if it doesn't exist.
5. Resumes the user's last-active thread (when it still exists)
   via localStorage; otherwise selects `MSJ_OPPOSITION`.

Every message post includes `{content, project_id}` — using the
backend's actual field name (`content`, per v47), not the typo
`text` from the early spec. The backend validates the
`project_id` against the thread's stored project_id and uses the
project's `default_model` to route the assistant call. Smoke
test confirmed the chosen model is `anthropic:claude-3.7`
(resolved from the alias `claude` in the project meta).

The sidebar gets a static **Projects** section above the
**Threads** list with a single always-selected `VA_LITIGATION`
row. No multi-project UI, no dropdown, no skill or plugin
machinery — exactly per the architecture boundary
(`/ARCHITECTURE.md`).

No backend / web / phone changes.

---

## Files added / changed

### New
- `V51_DESKTOP_WIRING_READINESS.md` (this file).

### Modified
- `desktop/src/lib/api.ts`:
  - New constants `ACTIVE_PROJECT_ID = "VA_LITIGATION"`,
    `ACTIVE_PROJECT_BOOTSTRAP` (the literal create-project body),
    `ACTIVE_PROJECT_DEFAULT_THREAD_TITLE = "MSJ_OPPOSITION"`.
  - New types: `ProjectMeta`, `CreateProjectRequest` (accepts
    `readonly` arrays so `as const` bodies pass through cleanly).
  - New helpers: `listProjects()`, `createProject(payload)`.
  - `listThreads(project_id?)` — query param when set.
  - `createThread(title, project_id?)` — sends `{title, project_id}`
    when set.
  - `postThreadMessage(thread_id, content, project_id?)` — sends
    `{content, project_id}` when set; field name is `content` per
    v47.
  - `ThreadMeta` extended with `project_id: string | null`.
  - New persistence helpers `getLastActiveThreadId(project_id)` /
    `setLastActiveThreadId(project_id, thread_id)` —
    project-scoped localStorage keys (`clarityos_desktop_last_thread:{pid}`).
- `desktop/src/ChatWindow.tsx`:
  - State: `activeProject: ProjectMeta | null`, `bootstrapping: bool`,
    `bootstrapError: string | null`.
  - `refreshList()` now calls `listThreads(ACTIVE_PROJECT_ID)` and
    returns the sorted list (so the bootstrap effect can chain off
    it).
  - New bootstrap effect on mount: `listProjects` → find/create
    `VA_LITIGATION` → fetch filtered threads → resume persisted
    last-active or auto-create `MSJ_OPPOSITION` → set selection +
    persist.
  - `handleNewThread` now calls `createThread(null, ACTIVE_PROJECT_ID)`
    and persists the new thread id.
  - `handleSend` now calls `postThreadMessage(selectedId, trimmed,
    ACTIVE_PROJECT_ID)`.
  - `handleDelete` clears the persisted last-active thread.
  - New `selectThread(thread_id)` wrapper around `setSelectedId`
    that persists the choice.
  - 401/403 handling consolidated into `handleAuthError(e)`.
  - Render: full-pane "preparing workspace…" while bootstrapping;
    full-pane error pane with Retry button if bootstrap fails.
  - `<ThreadList>` now receives `activeProject` prop.
- `desktop/src/ThreadList.tsx`:
  - Two new sections (`.sidebar-section`): "Projects" + "Threads".
  - Static project row showing `activeProject.name` (or
    `ACTIVE_PROJECT_ID` while bootstrapping), the project_id in
    monospace, and `model: claude` when the project carries a
    `default_model`.
  - Project row is always-selected (`active` + `aria-current`),
    not interactive.
  - `+ New` CTA disabled while `activeProject` is null.
- `desktop/src/styles.css`:
  - New `.sidebar-section` + `.sidebar-section-label` rules.
  - New `.project-row` / `.project-dot` / `.project-meta` /
    `.project-name` / `.project-id` / `.project-model` rules.
- `BUILD_VERSION` — `20260507700000`.

No backend, web, or phone code touched. `Composer.tsx` and
`ThreadView.tsx` unchanged — `Composer` still emits just
`onSend(content: string)`, and `ChatWindow.handleSend` plumbs
`ACTIVE_PROJECT_ID` into the API call.

---

## Step-by-step coverage of the spec

| Spec step | Status | Implementation |
|---|---|---|
| **STEP 1** — `ACTIVE_PROJECT_ID = "VA_LITIGATION"` constant | ✅ | `desktop/src/lib/api.ts` exports the constant + the bootstrap body + the starter thread title. |
| **STEP 2** — On startup ensure project exists | ✅ | `ChatWindow` bootstrap effect: `listProjects()` → `createProject(ACTIVE_PROJECT_BOOTSTRAP)` if missing. Threads only fetched after `activeProject` is set. |
| **STEP 3** — Static Projects section in sidebar | ✅ | `ThreadList.tsx` renders `<div className="sidebar-section">Projects → VA_LITIGATION (active)</div>` above the threads list. No dropdown, no switching. |
| **STEP 4** — Filter ThreadList by `?project_id=` | ✅ | `refreshList()` calls `listThreads(ACTIVE_PROJECT_ID)`; the API helper builds `GET /me/threads?project_id=VA_LITIGATION`. |
| **STEP 5** — Auto-create `MSJ_OPPOSITION` if missing | ✅ | Bootstrap finds the starter by title; if absent, calls `createThread("MSJ_OPPOSITION", ACTIVE_PROJECT_ID)` and selects it. |
| **STEP 6** — Always include `project_id` on messages, use `content` | ✅ | `postThreadMessage(thread_id, content, ACTIVE_PROJECT_ID)` posts `{content, project_id}` — backend field is `content` per v47. |
| **STEP 7** — Minimal persistence | ✅ | `setLastActiveThreadId(ACTIVE_PROJECT_ID, thread_id)` on every selection / new-thread / send-from-new; bootstrap reads it via `getLastActiveThreadId`. Project-scoped localStorage key. |

---

## Smoke test (live in-process backend)

Ran the desktop client's exact call sequence against the real
FastAPI app via the test harness. Output:

```
initial projects: []
created project: VA_LITIGATION default_model: claude
initial threads in project: 0
created starter thread: MSJ_OPPOSITION project_id: VA_LITIGATION
message round-trip ok; model_id: anthropic:claude-3.7
  user msg: draft the opposition
  asst msg: [mock anthropic:claude-3.7] user: draft the opposi
mismatched project_id status: 400
```

Confirms:

* `POST /me/projects` accepts the literal bootstrap body.
* `GET /me/threads?project_id=VA_LITIGATION` returns `[]`
  initially.
* `POST /me/threads {title, project_id}` creates the starter
  thread tagged with `project_id`.
* `POST /me/threads/{tid}/message {content, project_id}` —
  field name `content` is correct; assistant reply routes
  through `anthropic:claude-3.7` (resolved from `"claude"` alias).
* Mismatched `project_id` returns `400` (matches the v51 kernel
  contract).

---

## Build / type-check

* `npx tsc --noEmit` — zero errors across all desktop sources.
* `npm run build` — Vite produces 201 KB JS + 8 KB CSS in
  `dist/`. 751ms build, no warnings (apart from Vite's own
  CJS-deprecation notice).
* Backend regression: **730 pytest tests pass** (unchanged
  from v51).
* Web regression: **11 vitest tests pass** (unchanged).

---

## Behaviour on first vs subsequent launches

### First launch (fresh user)
1. Auth completes.
2. Bootstrap: `listProjects()` returns `[]`. The client posts
   `ACTIVE_PROJECT_BOOTSTRAP`. `activeProject` is set.
3. `listThreads(VA_LITIGATION)` returns `[]`. The client creates
   the `MSJ_OPPOSITION` thread.
4. `selectedId` is set to the new thread's id; persisted to
   localStorage.
5. The chat surface lands directly in the litigation workspace.

### Subsequent launches
1. Auth completes.
2. Bootstrap: `listProjects()` returns `[VA_LITIGATION]`. The
   client uses it directly (no POST).
3. `listThreads(VA_LITIGATION)` returns the existing threads.
4. The persisted `last_thread_id` is checked; if it's still in
   the list, that's the selection. Otherwise the
   `MSJ_OPPOSITION` thread is selected (or auto-created if
   it was deleted).
5. The chat surface resumes where the user left off.

---

## Notes / follow-ups

- The desktop client honours the no-skills architectural boundary:
  no `/skills_export/` imports, no plugin loading, no manifest
  parsing. Only the v51 endpoints are called.
- Persistence is project-scoped (`clarityos_desktop_last_thread:VA_LITIGATION`)
  even though there's only one project today. When multi-project UI
  lands, no migration is needed — each project remembers its own
  selection automatically.
- `bootstrapping` blocks the entire shell with a single-line
  "preparing workspace…" placeholder. This deliberately doesn't
  leak intermediate states (empty sidebar, empty chat pane) into
  view; the user sees the litigation workspace fully formed or a
  retry-able error.
- The `+ New` CTA stays disabled until `activeProject` is set, so
  pressing it during the bootstrap flicker can't post against an
  un-resolved project.
- `Composer.tsx` and `ThreadView.tsx` were intentionally not
  touched — their contracts already work for the v51 wiring.
- Backend version stays `4.5`. The Electron + Vite renderer is the
  only thing this pass changes.
