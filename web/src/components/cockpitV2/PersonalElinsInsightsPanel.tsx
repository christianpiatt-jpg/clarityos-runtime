/**
 * PersonalElinsInsightsPanel — the RIGHT column when view === "personal".
 *
 * Sections 2, 3 and 4: Attractor State, Collapse Risk (P0-P3), Field
 * Weather. These are built and working in routes/PersonalElins.tsx and
 * have never appeared in the member product — this is the first surface
 * that puts them in front of a member.
 *
 * ★ Imported, not rebuilt. Same three components the staging route
 * renders, reading the same envelope from the personal slice.
 */
import { useCockpit } from "../../state/cockpitStore";
import {
  SectionAttractor,
  SectionCollapseRisk,
  SectionFieldWeather,
} from "../../routes/PersonalElins";

export default function PersonalElinsInsightsPanel() {
  const personal = useCockpit((s) => s.personal);

  return (
    <section className="cv2-panel cv2-panel-insights">
      <header className="cv2-panel-head">Insights</header>
      <div className="cv2-panel-body">
        {personal.status === "loading" && !personal.elins && (
          <p className="cv2-muted">running…</p>
        )}
        <SectionAttractor elins={personal.elins} />
        <SectionCollapseRisk elins={personal.elins} />
        <SectionFieldWeather elins={personal.elins} />
      </div>
    </section>
  );
}
