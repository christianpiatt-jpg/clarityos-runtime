// ClarityOS desktop — sidebar thread list. Stateless; ChatWindow
// owns the loaded threads + selection. The list shows title, optional
// summary (v50), message count + relative timestamp.
//
// v51 — adds a static "Projects" section above the thread list. The
// only project shown is the hardwired ACTIVE_PROJECT_ID
// (VA_LITIGATION); it's always-selected and not user-changeable in
// this phase. No dropdown, no multi-project logic.

import { ACTIVE_PROJECT_ID, type ProjectMeta, type ThreadMeta } from "./lib/api";

interface Props {
  threads: ThreadMeta[];
  loading: boolean;
  selectedId: string | null;
  onSelect: (thread_id: string) => void;
  onNewThread: () => void;
  onSignOut: () => void;
  busy: boolean;
  activeProject: ProjectMeta | null;
}

export default function ThreadList({
  threads, loading, selectedId, onSelect, onNewThread, onSignOut, busy,
  activeProject,
}: Props) {
  // Project label — prefer the human-friendly ``name`` from the
  // backend meta, fall back to the raw project_id while the
  // bootstrap is in flight.
  const projectLabel =
    (activeProject?.name && activeProject.name.trim()) || ACTIVE_PROJECT_ID;
  const projectModel = activeProject?.default_model || null;

  return (
    <aside className="sidebar">
      <header className="sidebar-header">
        <span className="sidebar-title">
          <span className="brand-mark" aria-hidden />
          ClarityOS
        </span>
        <button
          type="button"
          className="btn btn-primary"
          onClick={onNewThread}
          disabled={busy || loading || !activeProject}
          title="New thread (Cmd/Ctrl+N)"
        >+ New</button>
      </header>

      {/* v51 — Projects section. Static, single-project, always selected. */}
      <div className="sidebar-section" aria-label="Projects">
        <div className="sidebar-section-label">Projects</div>
        <div className="project-row active" aria-current="true" data-testid="active-project">
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
        <div className="sidebar-section-label">Threads</div>
        <div className="sidebar-list selectable">
          {loading && threads.length === 0 ? (
            <div className="placeholder" style={{ padding: 24 }}>Loading…</div>
          ) : threads.length === 0 ? (
            <div className="placeholder" style={{ padding: 24 }}>
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
                onClick={() => onSelect(t.thread_id)}
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

      <footer
        style={{
          padding: 10,
          borderTop: "1px solid var(--os-line)",
          display: "flex", justifyContent: "flex-end",
        }}
      >
        <button
          type="button"
          className="btn"
          onClick={onSignOut}
          title="Clear the local session"
        >Sign out</button>
      </footer>
    </aside>
  );
}

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
