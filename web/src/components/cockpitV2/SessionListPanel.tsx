/**
 * SessionListPanel — selectable session list for CockpitV2.
 * The existing components/cockpit/SessionList takes no props and supports no
 * selection, so this wrapper reuses the same service function (fetchSessions,
 * via the session slice) and renders a store-driven selectable list.
 */
import { useCockpit, cockpit } from "../../state/cockpitStore";

export default function SessionListPanel() {
  const session = useCockpit((s) => s.session);

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head">Sessions</header>
      <div className="cv2-panel-body">
        {session.status === "loading" && <p className="cv2-muted">Loading…</p>}
        {session.status === "error" && <p className="cv2-err">{session.error}</p>}
        {session.status === "ready" && session.items.length === 0 && (
          <p className="cv2-muted">No sessions.</p>
        )}

        <ul className="cv2-list">
          {session.items.map((s) => (
            <li key={s.session_id}>
              <button
                type="button"
                className={
                  "cv2-list-row" + (s.session_id === session.selectedId ? " is-selected" : "")
                }
                onClick={() => cockpit.session.actions.select(s.session_id)}
              >
                <span className="cv2-mono">{s.session_id}</span>
                <span className="cv2-muted">{s.state_count} states</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
