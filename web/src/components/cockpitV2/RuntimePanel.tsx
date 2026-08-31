/**
 * RuntimePanel — global runtime envelope for CockpitV2.
 * Reuses the existing components/runtime/EnvelopeRenderer (props-driven) and
 * feeds it the RuntimeEnvelope held in the runtime slice.
 *
 * Spec §7 — refreshes every 10s WHILE OPEN. Collapsed by default; the poll
 * starts on open and is cleared on close and on unmount.
 */
import { useEffect, useState } from "react";

import { useCockpit, cockpit } from "../../state/cockpitStore";
import EnvelopeRenderer from "../runtime/EnvelopeRenderer";

export default function RuntimePanel() {
  const runtime = useCockpit((s) => s.runtime);
  // Collapsed by default. The 32-key ladder is a diagnostic surface, and it
  // pushed the panels above it off the column.
  const [open, setOpen] = useState(false);

  // ★ THE POLL IS TIED TO THE PANEL, NOT THE MOUNT. It used to run
  // unconditionally at 10s for the life of the session: 373 of 416 requests
  // in the 10:19 capture (89.7%), ~8.5 MB/hr, for a panel nobody had open.
  // Closed panel, no timer, no request.
  useEffect(() => {
    if (!open) return;
    void cockpit.runtime.actions.load();   // first paint has data
    const id = window.setInterval(() => {
      void cockpit.runtime.actions.load();
    }, 10_000);
    return () => window.clearInterval(id);
  }, [open]);

  return (
    <section className="cv2-panel">
      <button
        type="button"
        className="cv2-panel-head cv2-panel-head-toggle"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <span>Runtime</span>
        <span className="cv2-muted">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="cv2-panel-body">
          {runtime.status === "loading" && <p className="cv2-muted">Loading…</p>}
          {runtime.status === "error" && <p className="cv2-err">{runtime.error}</p>}
          <EnvelopeRenderer envelope={runtime.envelope} />
        </div>
      )}
    </section>
  );
}
