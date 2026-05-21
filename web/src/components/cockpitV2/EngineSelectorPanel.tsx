/**
 * EngineSelectorPanel — wraps the existing components/cockpit/EngineSelector
 * (a props-driven controlled component) and binds value/onChange to the
 * engine slice of the cockpit store.
 */
import { useCockpit, cockpit } from "../../state/cockpitStore";
import EngineSelector from "../cockpit/EngineSelector";

export default function EngineSelectorPanel() {
  const selected = useCockpit((s) => s.engine.selected);

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head">Engine</header>
      <div className="cv2-panel-body">
        <EngineSelector value={selected} onChange={(id) => cockpit.engine.actions.select(id)} />
      </div>
    </section>
  );
}
