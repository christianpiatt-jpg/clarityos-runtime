/**
 * PersonalElinsComposerPanel — the CENTRE column when view === "personal".
 *
 * Mirrors the thread view's own shape: input and the primary read sit in
 * the middle, derived reads go right. So this panel holds the seed
 * composer and section 1; sections 2-4 render in
 * PersonalElinsInsightsPanel.
 *
 * ★ NOTHING HERE IS REIMPLEMENTED. SeedComposer and SectionEmotionalPhysics
 * are imported from routes/PersonalElins.tsx, which remains the staging
 * surface at /personal-elins. One definition each; a second copy is the
 * vocabulary drift this build exists to stop.
 */
import { useEffect } from "react";

import { useCockpit, cockpit } from "../../state/cockpitStore";
import {
  SeedComposer,
  SectionEmotionalPhysics,
} from "../../routes/PersonalElins";
import AddToCorpusBox from "./AddToCorpusBox";

export default function PersonalElinsComposerPanel() {
  const personal = useCockpit((s) => s.personal);
  const loading = personal.status === "loading";

  // First selection runs the default seed, matching the route (which runs
  // DEFAULT_SEED on the first choice of a field). #303 A4 -- not before a
  // field is chosen: a run without one is refused by construction, so an
  // idle view waits for the choice instead of knocking on the door.
  useEffect(() => {
    if (personal.status === "idle" && personal.whoseField) void cockpit.personal.actions.run();
  }, [personal.status, personal.whoseField]);

  return (
    <section className="cv2-panel cv2-chat">
      <header className="cv2-panel-head">Personal ELINS</header>
      <div className="cv2-chat-scroll">
        {personal.status === "error" && (
          <p className="cv2-err">{personal.error}</p>
        )}
        <SeedComposer
          seed={personal.seed}
          onSeedChange={(s) => cockpit.personal.actions.setSeed(s)}
          onReRun={() => void cockpit.personal.actions.run()}
          loading={loading}
          whoseField={personal.whoseField}
          onWhoseFieldChange={(w) => cockpit.personal.actions.setWhoseField(w)}
        />
        {loading && <p className="cv2-muted">running…</p>}
        {/* #303 A4 -- the door's refusal rides in the section, in the #238
            shape; the field the member chose rides in the title. */}
        <SectionEmotionalPhysics ep={personal.ep} refusal={personal.refusal} whoseField={personal.whoseField} />
        {/* The corpus front door: same panel as the seed composer, no new
            route. Diagnostic boxes discard their input; this one keeps it. */}
        <AddToCorpusBox />
      </div>
    </section>
  );
}
