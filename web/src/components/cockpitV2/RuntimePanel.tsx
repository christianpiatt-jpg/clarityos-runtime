/**
 * RuntimePanel — global runtime envelope for CockpitV2.
 * Reuses the existing components/runtime/EnvelopeRenderer (props-driven) and
 * feeds it the RuntimeEnvelope held in the runtime slice.
 *
 * Spec §7 said every 10 s WHILE OPEN; the envelope is 62.5 KB and a sitting
 * pulled it 18 times, so the poll is now RUNTIME_POLL_MS (60 s) while open.
 * Collapsed by default; the poll starts on open and is cleared on close and
 * on unmount. THE CALLER, named: this panel -> cockpit.runtime.actions.load
 * (state/cockpitStore.ts) -> services/runtime.fetchRuntimeEnvelope -> GET
 * /runtime/envelope. Nothing else in web/src POLLS that route; the one other
 * reader, hooks/useEnvelope.ts (components/cockpit/RuntimePanel, mounted by
 * routes/Cockpit.tsx at /admin/cockpit -- the admin's V1 cockpit, which
 * App.tsx still routes), fetches it once per mount and has no interval.
 */
import { useEffect, useState } from "react";

import { useCockpit, cockpit } from "../../state/cockpitStore";
import EnvelopeRenderer from "../runtime/EnvelopeRenderer";

/** How often the OPEN panel re-reads /runtime/envelope. Never below 60 s. */
export const RUNTIME_POLL_MS = 60_000;

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
    }, RUNTIME_POLL_MS);
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
