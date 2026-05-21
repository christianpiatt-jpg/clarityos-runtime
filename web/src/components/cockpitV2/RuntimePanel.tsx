/**
 * RuntimePanel — global runtime envelope for CockpitV2.
 * Reuses the existing components/runtime/EnvelopeRenderer (props-driven) and
 * feeds it the RuntimeEnvelope held in the runtime slice.
 *
 * Spec §7 — loads runtime on mount and refreshes every 10s.
 */
import { useEffect } from "react";

import { useCockpit, cockpit } from "../../state/cockpitStore";
import EnvelopeRenderer from "../runtime/EnvelopeRenderer";

export default function RuntimePanel() {
  const runtime = useCockpit((s) => s.runtime);

  useEffect(() => {
    void cockpit.runtime.actions.load();
    const id = window.setInterval(() => {
      void cockpit.runtime.actions.load();
    }, 10_000);
    return () => window.clearInterval(id);
  }, []);

  return (
    <section className="cv2-panel">
      <header className="cv2-panel-head">Runtime</header>
      <div className="cv2-panel-body">
        {runtime.status === "loading" && <p className="cv2-muted">Loading…</p>}
        {runtime.status === "error" && <p className="cv2-err">{runtime.error}</p>}
        <EnvelopeRenderer envelope={runtime.envelope} />
      </div>
    </section>
  );
}
