/**
 * SessionListPanel -- the member's left list, VIEW-SCOPED.
 *
 *   view "thread"    -> threads        (label "Sessions")
 *   view "personal"  -> relationships  (label "Relationships")
 *
 * ★ ONE IMPLEMENTATION OF THE ROW. The two lists differ in what they read
 * and what a click does, not in how a row looks -- so the row is written
 * once, below, and both branches feed it. A sibling panel would have been
 * a second definition of the same thing, which is the drift this build
 * exists to stop.
 *
 * ★★ A relationship IS a thread. It carries the reserved project id
 * (RELATIONSHIP_PROJECT), so it reuses the thread minter, the thread
 * store and the thread list route. The partition is client-side: nothing
 * that reads GET /me/threads today changes.
 *
 * ★★★ THE NAME IS REQUIRED when minting a relationship. Production thread
 * rows currently render raw hex because `t.title || t.thread_id` falls
 * through on null titles -- a list of hex is a list of nothing. The
 * thread branch keeps its null-title behaviour untouched; only the
 * relationship branch demands a name, because only it has somewhere
 * useful to put one.
 *
 * WHY THIS PANEL READS THREADS AT ALL (kept from the previous revision):
 * it used to read the session slice, which loads GET /sessions. That
 * endpoint is healthy, but app.py:9511 reads markov_states_store -- the
 * legacy v28 store the member product never writes. So {"sessions":[]}
 * was TRUE and this panel rendered "No sessions." correctly, forever.
 * Not a stale interface: a stale STORE.
 */
import { useState } from "react";

import { useCockpit, cockpit } from "../../state/cockpitStore";
import type { ThreadMeta } from "../../lib/api";

/** The one row. Both lists render through this. */
function ListRow({
  item,
  selected,
  onOpen,
}: {
  item: ThreadMeta;
  selected: boolean;
  onOpen: () => void;
}) {
  return (
    <li key={item.thread_id}>
      <button
        type="button"
        className={"cv2-list-row" + (selected ? " is-selected" : "")}
        onClick={onOpen}
      >
        <span className="cv2-mono">{item.title || item.thread_id}</span>
        <span className="cv2-muted">{item.message_count} messages</span>
      </button>
    </li>
  );
}

export default function SessionListPanel() {
  const view = useCockpit((s) => s.view);
  const isPersonal = view === "personal";

  // Both branches are read unconditionally: hooks cannot be called behind
  // a condition, and reading a slice this panel is not showing costs
  // nothing.
  const threadStatus = useCockpit((s) => s.thread.status);
  const threadBusy = useCockpit((s) => s.thread.busy);
  const threadItems = useCockpit((s) => s.thread.items);
  const threadActive = useCockpit((s) => s.thread.meta?.thread_id ?? null);
  const threadError = useCockpit((s) => s.thread.error);

  const relStatus = useCockpit((s) => s.relationships.status);
  const relItems = useCockpit((s) => s.relationships.items);
  const relActive = useCockpit((s) => s.relationships.activeId);
  const relError = useCockpit((s) => s.relationships.error);

  const [naming, setNaming] = useState(false);
  const [draftName, setDraftName] = useState("");

  const heading = isPersonal ? "Relationships" : "Sessions";
  const items = isPersonal ? relItems : threadItems;
  const activeId = isPersonal ? relActive : threadActive;
  const error = isPersonal ? relError : threadError;
  const loading = isPersonal ? relStatus === "loading" : threadStatus === "loading";
  const failed = isPersonal ? relStatus === "error" : threadStatus === "error";

  // ★ The empty state names WHICH KIND is empty. "No sessions." shown on
  // the relationships list would send a member looking for the wrong
  // thing entirely.
  const emptyText = isPersonal
    ? "No relationships yet. Name one to start."
    : "No sessions.";

  function openItem(id: string): void {
    if (isPersonal) cockpit.relationships.actions.open(id);
    else void cockpit.thread.actions.open(id);
  }

  async function submitName(): Promise<void> {
    const name = draftName.trim();
    if (!name) return;             // required -- the button is disabled too
    await cockpit.relationships.actions.create(name);
    setDraftName("");
    setNaming(false);
  }

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head cv2-panel-head-row">
        <span>{heading}</span>
        <button
          type="button"
          className="cv2-btn"
          disabled={!isPersonal && threadBusy}
          onClick={() => {
            if (isPersonal) setNaming((v) => !v);
            // Paste-then-send: one click lands an empty thread, active,
            // with the composer ready. Null title, like the v1 route.
            else void cockpit.thread.actions.create();
          }}
        >
          + NEW
        </button>
      </header>

      <div className="cv2-panel-body">
        {/* ★★ Minting a relationship asks for the name FIRST. There is no
            path here that creates an unnamed one. */}
        {isPersonal && naming && (
          <div className="cv2-row-form">
            <input
              className="cv2-input"
              autoFocus
              value={draftName}
              placeholder="me and Ava · Ava and Sproesser"
              onChange={(e) => setDraftName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void submitName();
                if (e.key === "Escape") { setNaming(false); setDraftName(""); }
              }}
            />
            <button
              type="button"
              className="cv2-btn"
              disabled={!draftName.trim()}
              onClick={() => void submitName()}
            >
              Create
            </button>
          </div>
        )}

        {loading && items.length === 0 && <p className="cv2-muted">Loading…</p>}
        {failed && <p className="cv2-err">{error}</p>}
        {!loading && items.length === 0 && (
          <p className="cv2-muted">{emptyText}</p>
        )}

        <ul className="cv2-list">
          {items.map((t) => (
            <ListRow
              key={t.thread_id}
              item={t}
              selected={t.thread_id === activeId}
              onOpen={() => openItem(t.thread_id)}
            />
          ))}
        </ul>
      </div>
    </section>
  );
}
