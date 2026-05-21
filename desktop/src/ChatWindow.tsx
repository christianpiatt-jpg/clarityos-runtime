// ClarityOS desktop — top-level chat shell.
//
// v51 bootstrap behaviour preserved verbatim. Surface 3 (v54-era):
// render routed through DesktopShell so the v1 surface (TopBar +
// OperatorSidebar with 6 NavItems + CenterColumn + InsightsPanel)
// wraps the chat. The sidebar renders the projects + threads content
// below the NavItems (B1-thread-below-nav). The insights panel hosts
// the summary card + thread meta + action buttons.
//
// All hooks / state / handlers are byte-equivalent to the v51 shell;
// only the return JSX has been rewritten.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ACTIVE_PROJECT_BOOTSTRAP,
  ACTIVE_PROJECT_DEFAULT_THREAD_TITLE,
  ACTIVE_PROJECT_ID,
  ApiError,
  clearSession,
  createProject,
  createThread,
  deleteThread,
  getLastActiveThreadId,
  getThread,
  getUser,
  listProjects,
  listThreads,
  postThreadMessage,
  renameThread,
  setLastActiveThreadId,
  summarizeThread,
  type ProjectMeta,
  type ThreadMessage,
  type ThreadMeta,
} from "./lib/api";
import type { ElinsV2Envelope } from "./lib/elinsV2";
import type { EmotionalPhysicsResponse } from "./lib/emotionalPhysics";
import Composer from "./Composer";
import ThreadView from "./ThreadView";
import DesktopShell from "./DesktopShell";
import ElinsV2View from "./components/v1/ElinsV2View/ElinsV2View";
import EmotionalPhysicsView from "./components/v1/EmotionalPhysicsView/EmotionalPhysicsView";

interface ChatWindowProps {
  onSignOut: () => void;
  /** Sidebar nav-item click handler (provided by App.tsx view switcher). */
  onNavigate?: (label: string) => void;
}

export default function ChatWindow({ onSignOut, onNavigate }: ChatWindowProps) {
  // v51 — active project. Set by the bootstrap effect on mount; the
  // rest of the component blocks on it being non-null (guarded
  // through ``bootstrapping``).
  const [activeProject, setActiveProject] = useState<ProjectMeta | null>(null);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  const [threads, setThreads] = useState<ThreadMeta[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeMeta, setActiveMeta] = useState<ThreadMeta | null>(null);
  const [messages, setMessages] = useState<ThreadMessage[]>([]);

  const [listLoading, setListLoading] = useState(true);
  const [threadLoading, setThreadLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [renameOpen, setRenameOpen] = useState(false);
  const [renameDraft, setRenameDraft] = useState("");

  // v54-followup — per-thread ELINS v2 envelope + Emotional Physics
  // response, cached in ChatWindow so toggling away from a tab and
  // back doesn't re-fetch. Both are cleared whenever the user switches
  // threads (the kernel is keyed by thread content, so a new thread
  // means the cached result is stale).
  const [threadElinsEnv, setThreadElinsEnv] =
    useState<ElinsV2Envelope | null>(null);
  const [threadEpRes, setThreadEpRes] =
    useState<EmotionalPhysicsResponse | null>(null);

  // Active tab inside the InsightsPanel. THREAD is the default (the
  // legacy meta + summary + action buttons surface). ELINS and PHYSICS
  // mount the v1 ELINS v2 and Emotional Physics views respectively,
  // wired against the active thread's composed transcript.
  type InsightsTab = "thread" | "elins" | "physics";
  const [insightsTab, setInsightsTab] = useState<InsightsTab>("thread");

  // Signed-in user name for the TopBar identity chip.
  const userName = getUser();

  // ------------ 401/403 sign-out helper ------------
  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  // ---------------- Load list (filtered by active project) ----------------
  const refreshList = useCallback(async (): Promise<ThreadMeta[]> => {
    setListLoading(true); setError(null);
    try {
      const t = await listThreads(ACTIVE_PROJECT_ID);
      const sorted = [...t].sort(
        (a, b) => (b.updated_at || 0) - (a.updated_at || 0),
      );
      setThreads(sorted);
      return sorted;
    } catch (e) {
      if (handleAuthError(e)) return [];
      setError(e instanceof ApiError ? e.message : String(e));
      return [];
    } finally {
      setListLoading(false);
    }
  }, [handleAuthError]);

  // ---------------- v51 — Project + threads bootstrap ----------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      setBootstrapping(true);
      setBootstrapError(null);
      try {
        let project: ProjectMeta | null = null;
        const projects = await listProjects();
        const existing = projects.find(
          (p) => p.project_id === ACTIVE_PROJECT_ID,
        );
        if (existing) {
          project = existing;
        } else {
          project = await createProject({ ...ACTIVE_PROJECT_BOOTSTRAP });
        }
        if (cancelled) return;
        setActiveProject(project);

        const list = await refreshList();
        if (cancelled) return;

        const persisted = getLastActiveThreadId(ACTIVE_PROJECT_ID);
        const persistedStillExists =
          persisted && list.some((t) => t.thread_id === persisted);
        if (persistedStillExists) {
          setSelectedId(persisted);
          return;
        }

        const starter = list.find(
          (t) => (t.title || "").trim() === ACTIVE_PROJECT_DEFAULT_THREAD_TITLE,
        );
        if (starter) {
          setSelectedId(starter.thread_id);
          setLastActiveThreadId(ACTIVE_PROJECT_ID, starter.thread_id);
          return;
        }

        const created = await createThread(
          ACTIVE_PROJECT_DEFAULT_THREAD_TITLE,
          ACTIVE_PROJECT_ID,
        );
        if (cancelled) return;
        await refreshList();
        if (cancelled) return;
        setSelectedId(created.thread_id);
        setLastActiveThreadId(ACTIVE_PROJECT_ID, created.thread_id);
      } catch (e) {
        if (cancelled) return;
        if (handleAuthError(e)) return;
        setBootstrapError(e instanceof ApiError ? e.message : String(e));
      } finally {
        if (!cancelled) setBootstrapping(false);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------- Load thread ----------------
  const loadThread = useCallback(async (thread_id: string) => {
    setThreadLoading(true); setError(null);
    try {
      const r = await getThread(thread_id);
      setActiveMeta(r.meta);
      setMessages(r.messages);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      setActiveMeta(null);
      setMessages([]);
    } finally {
      setThreadLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId) void loadThread(selectedId);
    else {
      setActiveMeta(null);
      setMessages([]);
    }
    // Clear cached ELINS + EP results whenever the active thread
    // changes; the kernel inputs are thread-keyed, so old results are
    // stale. Tab selection persists across thread switches.
    setThreadElinsEnv(null);
    setThreadEpRes(null);
  }, [selectedId, loadThread]);

  // ---------------- Mutators ----------------
  const handleNewThread = useCallback(async () => {
    if (busy) return;
    setBusy("new"); setError(null);
    try {
      const meta = await createThread(null, ACTIVE_PROJECT_ID);
      await refreshList();
      setSelectedId(meta.thread_id);
      setLastActiveThreadId(ACTIVE_PROJECT_ID, meta.thread_id);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [busy, refreshList]);

  const handleSend = useCallback(async (content: string) => {
    if (!selectedId) return;
    const trimmed = content.trim();
    if (!trimmed || busy) return;
    setBusy("send"); setError(null);
    try {
      const r = await postThreadMessage(selectedId, trimmed, ACTIVE_PROJECT_ID);
      setActiveMeta(r.meta);
      setMessages((cur) => [...cur, r.user_message, r.assistant_message]);
      setThreads((cur) => {
        const others = cur.filter((t) => t.thread_id !== r.meta.thread_id);
        return [r.meta, ...others];
      });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [selectedId, busy]);

  const startRename = useCallback(() => {
    if (!activeMeta) return;
    setRenameDraft(activeMeta.title || "");
    setRenameOpen(true);
  }, [activeMeta]);

  const cancelRename = useCallback(() => {
    setRenameOpen(false);
    setRenameDraft("");
  }, []);

  const commitRename = useCallback(async () => {
    if (!activeMeta || busy) return;
    setBusy("rename"); setError(null);
    try {
      const meta = await renameThread(activeMeta.thread_id, renameDraft.trim());
      setActiveMeta(meta);
      setThreads((cur) =>
        cur.map((t) => (t.thread_id === meta.thread_id ? meta : t)),
      );
      setRenameOpen(false);
      setRenameDraft("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [activeMeta, busy, renameDraft]);

  const handleDelete = useCallback(async () => {
    if (!activeMeta || busy) return;
    const display = activeMeta.title || "Untitled Thread";
    // eslint-disable-next-line no-alert
    if (!window.confirm(`Delete "${display}"? This cannot be undone.`)) return;
    setBusy("delete"); setError(null);
    try {
      const removedId = activeMeta.thread_id;
      await deleteThread(removedId);
      setActiveMeta(null);
      setMessages([]);
      setSelectedId(null);
      setThreads((cur) => cur.filter((t) => t.thread_id !== removedId));
      setLastActiveThreadId(ACTIVE_PROJECT_ID, null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [activeMeta, busy]);

  const selectThread = useCallback((thread_id: string) => {
    setSelectedId(thread_id);
    setLastActiveThreadId(ACTIVE_PROJECT_ID, thread_id);
  }, []);

  const handleSummarize = useCallback(async () => {
    if (!activeMeta || busy) return;
    setBusy("summarize"); setError(null);
    try {
      const meta = await summarizeThread(activeMeta.thread_id);
      setActiveMeta(meta);
      setThreads((cur) =>
        cur.map((t) => (t.thread_id === meta.thread_id ? meta : t)),
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [activeMeta, busy]);

  // Compose the active thread's transcript once per messages change.
  // Cap to 6KB so we don't blow the backend's text limit. Empty string
  // when there are no messages yet (the views then render their empty
  // state without firing a request).
  const threadText = useMemo(() => {
    const composed = messages
      .map((m) => `${m.role}: ${m.content}`)
      .join("\n")
      .slice(0, 6000);
    return composed.trim();
  }, [messages]);

  // ---------------- Keyboard shortcuts ----------------
  const newThreadRef = useRef(handleNewThread);
  newThreadRef.current = handleNewThread;
  useEffect(() => {
    const off = window.clarityos?.onNewThread?.(() => {
      void newThreadRef.current();
    });
    return () => { off?.(); };
  }, []);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "n") {
        e.preventDefault();
        void newThreadRef.current();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const headerMeta = useMemo(() => {
    if (!activeMeta) return "";
    const n = activeMeta.message_count;
    return `${n} message${n === 1 ? "" : "s"} · updated ${
      relativeTime(activeMeta.updated_at)
    }`;
  }, [activeMeta]);

  // ---------------- Bootstrap full-pane states ----------------
  // These render BEFORE the v1 shell — same as the v51 behaviour: a
  // small full-pane indicator while the project bootstrap is in flight.
  if (bootstrapping && !activeProject) {
    return (
      <div className="placeholder">
        <span>preparing workspace…</span>
      </div>
    );
  }
  if (bootstrapError && !activeProject) {
    return (
      <div className="placeholder" style={{ flexDirection: "column", gap: 12 }}>
        <span>workspace unavailable: {bootstrapError}</span>
        <button
          type="button"
          className="btn"
          onClick={() => window.location.reload()}
        >Retry</button>
      </div>
    );
  }

  // ---------------- Slot content ----------------
  const projectLabel =
    (activeProject?.name && activeProject.name.trim()) || ACTIVE_PROJECT_ID;
  const projectModel = activeProject?.default_model || null;

  const sidebarContent = (
    <>
      <div className="sidebar-section" aria-label="Projects">
        <div className="sidebar-section-label">Projects</div>
        <div
          className="project-row active"
          aria-current="true"
          data-testid="active-project"
        >
          <span className="project-dot" aria-hidden />
          <div className="project-meta">
            <div className="project-name">{projectLabel}</div>
            <div className="project-id">{ACTIVE_PROJECT_ID}</div>
            {projectModel ? (
              <div className="project-model">model: {projectModel}</div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="sidebar-section" aria-label="Threads">
        <div
          className="sidebar-section-label"
          style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
        >
          <span>Threads</span>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleNewThread}
            disabled={busy === "new" || listLoading || !activeProject}
            title="New thread (Cmd/Ctrl+N)"
            style={{ padding: "2px 8px", fontSize: 11 }}
          >+ New</button>
        </div>
        <div className="sidebar-list selectable">
          {listLoading && threads.length === 0 ? (
            <div className="placeholder" style={{ padding: 16 }}>Loading…</div>
          ) : threads.length === 0 ? (
            <div className="placeholder" style={{ padding: 16 }}>
              No threads yet.<br/>Click + New to start.
            </div>
          ) : (
            threads.map((t) => (
              <button
                key={t.thread_id}
                type="button"
                className={
                  "thread-row" + (t.thread_id === selectedId ? " active" : "")
                }
                onClick={() => selectThread(t.thread_id)}
                aria-label={`Open thread ${t.title || "Untitled Thread"}`}
              >
                <div className="thread-title">
                  {t.title?.trim() || "Untitled Thread"}
                </div>
                {t.summary ? (
                  <div className="thread-summary">{t.summary}</div>
                ) : null}
                <div className="thread-meta">
                  {t.message_count} message{t.message_count === 1 ? "" : "s"}
                  {" · "}{relativeTime(t.updated_at)}
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      <div
        style={{
          marginTop: "auto",
          padding: 10,
          borderTop: "1px solid rgba(255,255,255,0.15)",
          display: "flex", justifyContent: "flex-end",
        }}
      >
        <button
          type="button"
          className="btn"
          onClick={onSignOut}
          title="Clear the local session"
        >Sign out</button>
      </div>
    </>
  );

  const centerContent = !selectedId ? (
    <div className="placeholder">
      Pick a thread on the left, or press <strong>Cmd/Ctrl+N</strong>{" "}
      to start a new conversation.
    </div>
  ) : threadLoading && !activeMeta ? (
    <div className="placeholder">Loading thread…</div>
  ) : !activeMeta ? (
    <div className="placeholder">Thread not found.</div>
  ) : (
    <>
      <header
        className="main-header"
        style={{ padding: "12px 16px", borderBottom: "1px solid rgba(255,255,255,0.15)" }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 style={{ margin: 0, fontSize: 16 }}>
            {activeMeta.title || "Untitled Thread"}
          </h1>
          <div className="meta" style={{ fontSize: 11, opacity: 0.7 }}>
            {headerMeta}
          </div>
        </div>
      </header>

      {error ? <div className="banner err">{error}</div> : null}

      <ThreadView messages={messages} />

      <Composer
        onSend={handleSend}
        disabled={busy !== null}
        sending={busy === "send"}
      />
    </>
  );

  // Stable runOn payload for the ELINS / Physics tabs. We only pass
  // it when there's text to analyse, so the view shows its empty state
  // (with no Re-run button) on an empty thread instead of firing a
  // backend request against the empty string.
  const insightsRunOn = threadText
    ? { rawText: threadText, region: null }
    : null;

  const insightsContent = !activeMeta ? (
    <div className="placeholder" style={{ padding: 16, fontSize: 12 }}>
      No thread selected.
    </div>
  ) : (
    <>
      {/* v54-followup — InsightsPanel tab strip. THREAD is the legacy
          meta + summary + actions surface; ELINS and PHYSICS mount the
          v1 ELINS v2 and Emotional Physics views against the active
          thread's composed transcript. Tab choice persists across
          thread switches, but the cached envelopes do not. */}
      <div
        role="tablist"
        aria-label="Insights view selector"
        data-testid="insights-tabs"
        style={{
          display: "flex",
          gap: 4,
          borderBottom: "1px solid rgba(255,255,255,0.10)",
          paddingBottom: 4,
          marginBottom: 4,
        }}
      >
        {(["thread", "elins", "physics"] as const).map((tab) => {
          const active = insightsTab === tab;
          const label =
            tab === "thread" ? "Thread"
            : tab === "elins"  ? "ELINS"
            :                    "Physics";
          return (
            <button
              key={tab}
              type="button"
              role="tab"
              aria-selected={active}
              data-testid={`insights-tab-${tab}`}
              onClick={() => setInsightsTab(tab)}
              style={{
                flex: 1,
                padding: "4px 6px",
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                letterSpacing: "0.06em",
                textTransform: "uppercase",
                background: "transparent",
                border: "1px solid",
                borderColor: active
                  ? "var(--color-accent-cyan)"
                  : "rgba(255,255,255,0.10)",
                color: active
                  ? "var(--color-accent-cyan)"
                  : "var(--color-text-secondary)",
                cursor: "pointer",
                borderRadius: 3,
              }}
            >
              {label}
            </button>
          );
        })}
      </div>

      {insightsTab === "thread" ? (
        <>
          <div
            className="thread-meta-block"
            style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--color-text-secondary)" }}
          >
            <div>messages: {activeMeta.message_count}</div>
            <div>updated: {relativeTime(activeMeta.updated_at)}</div>
            {activeMeta.summary_ts_ms ? (
              <div>summary: {relativeTime(activeMeta.summary_ts_ms)}</div>
            ) : null}
          </div>

          {activeMeta.summary ? (
            <div className="summary-card">
              <div className="label">Summary</div>
              <div className="body selectable">{activeMeta.summary}</div>
            </div>
          ) : (
            <div className="placeholder" style={{ padding: 12, fontSize: 12 }}>
              No summary yet.
            </div>
          )}

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button
              type="button"
              className="btn"
              onClick={handleSummarize}
              disabled={busy !== null}
            >{busy === "summarize" ? "Summarizing…" : "Summarize"}</button>
            <button
              type="button"
              className="btn"
              onClick={startRename}
              disabled={busy !== null}
            >Rename</button>
            <button
              type="button"
              className="btn btn-danger"
              onClick={handleDelete}
              disabled={busy !== null}
            >{busy === "delete" ? "Deleting…" : "Delete"}</button>
          </div>
        </>
      ) : insightsTab === "elins" ? (
        insightsRunOn ? (
          <ElinsV2View
            envelope={threadElinsEnv}
            runOn={insightsRunOn}
            onRun={setThreadElinsEnv}
          />
        ) : (
          <div
            className="placeholder"
            style={{ padding: 12, fontSize: 12 }}
            data-testid="insights-elins-empty"
          >
            No messages yet — add a turn to run ELINS on this thread.
          </div>
        )
      ) : (
        insightsRunOn ? (
          <EmotionalPhysicsView
            response={threadEpRes}
            text={insightsRunOn.rawText}
            onAnalyze={setThreadEpRes}
          />
        ) : (
          <div
            className="placeholder"
            style={{ padding: 12, fontSize: 12 }}
            data-testid="insights-physics-empty"
          >
            No messages yet — add a turn to analyse this thread.
          </div>
        )
      )}
    </>
  );

  return (
    <>
      <DesktopShell
        userName={userName}
        sidebar={sidebarContent}
        center={centerContent}
        insights={insightsContent}
        onNavigate={onNavigate}
        activeNav="Threads"
      />

      {/* Rename modal — top-level so it isn't constrained by panes. */}
      {renameOpen ? (
        <div className="modal-backdrop" onClick={cancelRename}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <h2>Rename thread</h2>
            <input
              type="text"
              value={renameDraft}
              onChange={(e) => setRenameDraft(e.target.value)}
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") void commitRename();
                if (e.key === "Escape") cancelRename();
              }}
            />
            <div className="modal-actions">
              <button
                type="button"
                className="btn"
                onClick={cancelRename}
                disabled={busy === "rename"}
              >Cancel</button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={commitRename}
                disabled={busy === "rename"}
              >{busy === "rename" ? "Saving…" : "Save"}</button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------
function relativeTime(ts_ms: number): string {
  if (!ts_ms) return "—";
  const diff = Date.now() - ts_ms;
  if (diff < 0) return new Date(ts_ms).toLocaleTimeString();
  const s = Math.floor(diff / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(ts_ms).toLocaleDateString();
}
