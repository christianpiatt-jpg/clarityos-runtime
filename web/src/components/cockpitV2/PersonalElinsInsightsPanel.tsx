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
 *
 * #23 W2 -- when a relationship is selected, a RELATIONSHIP header sits
 * above the run panels: its name, how many turns it has saved, the trust
 * signal AS THE BACKEND RETURNS IT ("no_prior_yet" at n=0 is a string,
 * never 0.0; a value carries a direction only from the second scored turn),
 * the last sealed timestamp, and the windowed turns with their seal /
 * observe stamps. The run panels below show THIS relationship's last run,
 * or say there is none yet.
 */
import { useCockpit } from "../../state/cockpitStore";
import type { TrustSignal, TurnRecord } from "../../lib/api";
import { basinHopLine } from "../../lib/trustSignal";
import {
  SectionAttractor,
  SectionCollapseRisk,
  SectionFieldWeather,
} from "../../routes/PersonalElins";

/** The trust signal as a label. The status STRING is the reading at n=0
 *  and when undefined; a value shows its rate, and its direction only when
 *  the backend sent one. */
export function trustLabel(sig: TrustSignal | null | undefined): string {
  if (!sig) return "—";
  if (sig.status !== "value" || typeof sig.value !== "number") return sig.status;
  const dir = sig.direction ? ` · ${sig.direction}` : "";
  return `${sig.value}${dir} (${sig.scored_turns} scored)`;
}

/** ts_* are nanoseconds (time.time_ns). */
function stamp(ns: number | null | undefined): string {
  if (typeof ns !== "number" || !Number.isFinite(ns)) return "—";
  return new Date(Math.floor(ns / 1e6)).toISOString().slice(0, 16).replace("T", " ");
}

function lastSealed(turns: TurnRecord[]): string {
  if (!turns.length) return "—";
  return stamp(Math.max(...turns.map((t) => t.ts_sealed ?? 0)));
}

export default function PersonalElinsInsightsPanel() {
  const personal = useCockpit((s) => s.personal);
  const rel = useCockpit((s) => s.relationships);
  const activeId = rel.activeId;
  const active = activeId ? rel.items.find((t) => t.thread_id === activeId) ?? null : null;
  const detail = activeId ? rel.detail[activeId] ?? null : null;
  const noRunYet =
    !!activeId && personal.status !== "loading" && personal.status !== "error"
    && !personal.ep && !personal.elins;

  return (
    <section className="cv2-panel cv2-panel-insights">
      <header className="cv2-panel-head">Insights</header>
      <div className="cv2-panel-body">
        {activeId && (
          <div className="cv2-rel-head" data-testid="relationship-header">
            <div className="cv2-mono" data-testid="rel-name">
              {active?.title || activeId}
            </div>
            {!detail && rel.detailStatus === "loading" && (
              <p className="cv2-muted">reading what it saved…</p>
            )}
            {!detail && rel.detailStatus === "error" && (
              <p className="cv2-err">{rel.detailError}</p>
            )}
            {detail && (
              <>
                <dl className="cv2-kv">
                  <div className="cv2-kv-row">
                    <dt>turns</dt>
                    <dd className="cv2-mono" data-testid="rel-turn-count">{detail.turn_count}</dd>
                  </div>
                  <div className="cv2-kv-row">
                    <dt>trust</dt>
                    <dd className="cv2-mono" data-testid="rel-trust">{trustLabel(detail.trust_signal)}</dd>
                  </div>
                  <div className="cv2-kv-row">
                    <dt>last sealed</dt>
                    <dd className="cv2-mono" data-testid="rel-last-sealed">{lastSealed(detail.turns)}</dd>
                  </div>
                </dl>
                {/* #162 (d) -- the awaiting rail speaks the status. */}
                <div className="cv2-muted cv2-mono" data-testid="math-rail-basin-hop">
                  {basinHopLine(detail.trust_signal)}
                </div>
                {detail.turns.length > 0 && (
                  <ul className="cv2-rel-turns" data-testid="rel-turns">
                    {detail.turns.map((t) => (
                      <li key={`${t.turn_index}-${t.ts_sealed}`} className="cv2-muted">
                        #{t.turn_index} · sealed {stamp(t.ts_sealed)} ·{" "}
                        {t.ts_observed == null ? "awaiting return" : `observed ${stamp(t.ts_observed)}`}
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
        )}
        {personal.status === "loading" && !personal.elins && (
          <p className="cv2-muted">running…</p>
        )}
        {noRunYet && (
          <p className="cv2-muted" data-testid="no-run-yet">
            No run yet on this relationship. Run the seed to read it.
          </p>
        )}
        <SectionAttractor elins={personal.elins} />
        <SectionCollapseRisk elins={personal.elins} />
        <SectionFieldWeather elins={personal.elins} />
      </div>
    </section>
  );
}
