/**
 * SessionListPanel -- the member's list, read from the THREAD substrate.
 *
 * It used to read the session slice, which loads GET /sessions. That endpoint
 * is healthy, but app.py:9511 reads markov_states_store -- the legacy v28
 * store. The member product writes through the v47 thread runtime
 * (/me/threads -> run_thread_message), which never writes that store. So
 * {"sessions":[],"count":0} was TRUE, and this panel rendered "No sessions."
 * correctly, forever. Not a stale interface: a stale STORE.
 *
 * A member's sessions ARE their threads. No new request is made -- 
 * threadSlice.init() already fetches the full list to pick the newest thread,
 * and now keeps it instead of discarding it.
 *
 * The label stays "Sessions". Showing threads under it means "session" now
 * means "thread" in the member product; that collision is CT-1's to rule on,
 * not something to paper over with a rename here.
 */
import { useCockpit, cockpit } from "../../state/cockpitStore";

export default function SessionListPanel() {
  const status = useCockpit((s) => s.thread.status);
  const items = useCockpit((s) => s.thread.items);
  const activeId = useCockpit((s) => s.thread.meta?.thread_id ?? null);
  const error = useCockpit((s) => s.thread.error);

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head">Sessions</header>
      <div className="cv2-panel-body">
        {status === "loading" && items.length === 0 && <p className="cv2-muted">Loading…</p>}
        {status === "error" && <p className="cv2-err">{error}</p>}
        {status !== "loading" && items.length === 0 && (
          <p className="cv2-muted">No sessions.</p>
        )}

        <ul className="cv2-list">
          {items.map((t) => (
            <li key={t.thread_id}>
              <button
                type="button"
                className={
                  "cv2-list-row" + (t.thread_id === activeId ? " is-selected" : "")
                }
                onClick={() => void cockpit.thread.actions.open(t.thread_id)}
              >
                <span className="cv2-mono">{t.title || t.thread_id}</span>
                <span className="cv2-muted">{t.message_count} messages</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
