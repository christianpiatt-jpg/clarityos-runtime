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

export default function PersonalElinsComposerPanel() {
  const personal = useCockpit((s) => s.personal);
  const loading = personal.status === "loading";

  // First selection runs the default seed, matching the route's mount
  // behaviour (routes/PersonalElins.tsx runs DEFAULT_SEED on mount). A
  // member selecting the view sees a read rather than an empty frame.
  useEffect(() => {
    if (personal.status === "idle") void cockpit.personal.actions.run();
  }, [personal.status]);

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
        />
        {loading && <p className="cv2-muted">running…</p>}
        <SectionEmotionalPhysics ep={personal.ep} />
      </div>
    </section>
  );
}
