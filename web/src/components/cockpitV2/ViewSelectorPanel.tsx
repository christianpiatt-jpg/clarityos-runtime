/**
 * ViewSelectorPanel — chooses what the centre and right columns render.
 *
 * ★ A VIEW SWITCH, not a tab and not a nav link. The cockpit chrome stays
 * exactly where it is; only the two right-hand columns change. Personal
 * ELINS is deliberately NOT an entry in the Sessions list — it is not a
 * session, and putting it there would say it was one.
 */
import { useCockpit, cockpit, type CockpitView } from "../../state/cockpitStore";

const VIEWS: Array<{ id: CockpitView; label: string }> = [
  { id: "thread", label: "Thread" },
  { id: "personal", label: "Personal ELINS" },
];

export default function ViewSelectorPanel() {
  const view = useCockpit((s) => s.view);

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head">View</header>
      <div className="cv2-panel-body">
        <ul className="cv2-list">
          {VIEWS.map((v) => (
            <li key={v.id}>
              <button
                type="button"
                className={"cv2-list-row" + (v.id === view ? " is-selected" : "")}
                aria-pressed={v.id === view}
                onClick={() => cockpit.view.actions.select(v.id)}
              >
                <span>{v.label}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
