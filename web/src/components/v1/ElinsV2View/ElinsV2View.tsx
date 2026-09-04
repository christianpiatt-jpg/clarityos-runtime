// web/src/components/v1/ElinsV2View/ElinsV2View.tsx
//
// Web mirror of desktop/src/components/v1/ElinsV2View/ElinsV2View.tsx.
// Verbatim copy — the relative imports (../../../lib/elinsV2,
// ../../../lib/api) resolve identically in both projects, and the v1
// shell + tokens are surface-symmetric.
//
// Compact ELINS v2 view for the v1 InsightsPanel. Renders the six
// analytical heads from /elins/v2/run as a somatic, structural
// summary — not a debug dump. 320px-width compatible (no fixed widths,
// no horizontal scrolling, no large numbers).
//
// Two modes:
//   - controlled:  caller passes `envelope` directly (e.g., from an
//                  already-stored ingestion-bus output). Component
//                  renders and offers Re-run if `runOn` is also given.
//   - uncontrolled: caller passes `runOn` only. Component fetches on
//                   mount and on every Re-run click.

import { useCallback, useEffect, useState } from "react";
import {
  runElinsV2,
  type ElinsV2Envelope,
  type ElinsV2RunRequest,
  type Attractor,
  type CollapseState,
  type GeographyTier,
  type PKey,
} from "../../../lib/elinsV2";
import { ApiError, type TrustSignal } from "../../../lib/api";
import { labelFor } from "../../../lib/labels";
import { basinHopLine } from "../../../lib/trustSignal";
import SendToCorpus from "./SendToCorpus";
import { compressionIndex, compressionWord } from "../../../lib/compressionIndex";
import styles from "./ElinsV2View.module.css";
import {
  attractorVerdict,
  INDETERMINATE_LABEL,
  indeterminateDetail,
} from "../../../lib/attractor";

interface Props {
  /** Pre-computed envelope (e.g., already-stored ingestion-bus output). */
  envelope?: ElinsV2Envelope | null;
  /** Text + region to run /elins/v2/run against. If omitted, component is
   *  controlled-only. */
  runOn?: { rawText: string; region?: string | null } | null;
  /** Optional callback fired on every successful run, including initial. */
  onRun?: (env: ElinsV2Envelope) => void;
  /** #162 (d) -- the relationship's trust signal (#23), when the caller
   *  has one. The math rail's basin_hop row speaks its status. Absent ->
   *  the row reads as it always did. */
  trust?: TrustSignal | null;
}

export default function ElinsV2View({ envelope, runOn, onRun, trust }: Props) {
  const [view, setView] = useState<ElinsV2Envelope | null>(envelope ?? null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updatedAtMs, setUpdatedAtMs] = useState<number | null>(
    envelope ? Date.now() : null,
  );

  const canRerun = !!runOn && typeof runOn.rawText === "string"
    && runOn.rawText.trim().length > 0;

  const doRun = useCallback(async () => {
    if (!canRerun || !runOn) return;
    setLoading(true);
    setError(null);
    try {
      const req: ElinsV2RunRequest = {
        region: runOn.region ?? null,
        input: { raw_text: runOn.rawText },
      };
      const env = await runElinsV2(req);
      setView(env);
      setUpdatedAtMs(Date.now());
      onRun?.(env);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [canRerun, runOn, onRun]);

  useEffect(() => {
    if (envelope || !canRerun) return;
    void doRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (envelope) {
      setView(envelope);
      setUpdatedAtMs(Date.now());
      setError(null);
    }
  }, [envelope]);

  if (!view && loading) {
    return (
      <section className={styles.root} aria-label="ELINS v2 view loading">
        <Heading title="ELINS v2" subtitle="running…" />
      </section>
    );
  }

  if (!view) {
    return (
      <section className={styles.root} aria-label="ELINS v2 view">
        <Heading title="ELINS v2" subtitle={error ?? "no payload"} />
        {canRerun ? (
          <button
            type="button"
            className={styles.actionBtn}
            onClick={doRun}
            disabled={loading}
          >
            {loading ? "running…" : "Re-run ELINS"}
          </button>
        ) : null}
      </section>
    );
  }

  const { outputs } = view;

  return (
    <section className={styles.root} aria-label="ELINS v2 view">
      <Heading
        title="ELINS v2"
        subtitle={`engine: ${view.meta.engine}`}
      />

      <EtfBlock view={view} />
      <AttractorBlock
        distribution={outputs.state_distribution}
        attractor={outputs.attractor}
      />
      <MathRail view={view} trust={trust} />
      <CollapseBlock collapse={outputs.collapse_state} />
      <P0P8Block grid={outputs.P0_P8} timeline={outputs.timeline} />
      <GeographyBlock tier={outputs.geography_tier} />
      <MultiplierBlock multiplier={outputs.multiplier} />

      <footer className={styles.footer}>
        {updatedAtMs ? (
          <span className={styles.updatedAt}>
            updated {relativeTime(updatedAtMs)}
          </span>
        ) : null}
        {canRerun ? (
          <button
            type="button"
            className={styles.actionBtn}
            onClick={doRun}
            disabled={loading}
            aria-label="Re-run ELINS v2"
          >
            {loading ? "running…" : "Re-run ELINS"}
          </button>
        ) : null}
        {/* ★ "send to corpus". The run's INPUT text -- runOn.rawText, the
            same text the diagnostic was run on -- goes through the same
            front door as the cockpit box. Rendered only when that text is
            in hand; a button that could send nothing is not offered. */}
        {/* key={text}: the control's "sent" state belongs to THIS text. When
            the transcript changes (new turn, other thread) it remounts fresh,
            so it never claims the new text was sent. Trimmed gate matches
            canRerun: whitespace-only input offers nothing. */}
        {runOn?.rawText?.trim() ? (
          <SendToCorpus key={runOn.rawText} text={runOn.rawText} region={runOn.region ?? null} />
        ) : null}
      </footer>

      {error ? (
        <div role="alert" className={styles.error}>
          {error}
        </div>
      ) : null}
    </section>
  );
}

// -----------------------------------------------------------------
// Sub-blocks
// -----------------------------------------------------------------

function Heading({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className={styles.heading}>
      <span className={styles.title}>{title}</span>
      {subtitle ? <span className={styles.subtitle}>{subtitle}</span> : null}
    </header>
  );
}

function EtfBlock({ view }: { view: ElinsV2Envelope }) {
  const agg = view.pipeline.L8_temporal.etf_agg;
  return (
    <div className={styles.section}>
      <div className={styles.sectionLabel}>ETF · survival</div>
      <div className={styles.etfRow}>
        <EtfPill label="1y" value={agg.n_365} />
        <EtfPill label="10y" value={agg.n_3650} />
        <EtfPill label="50y" value={agg.n_18250} />
      </div>
    </div>
  );
}

function EtfPill({ label, value }: { label: string; value: number }) {
  const pct = Math.round((isFinite(value) ? value : 0) * 100);
  return (
    <div className={styles.etfPill}>
      <span className={styles.etfLabel}>{label}</span>
      <span className={styles.etfValue}>{pct}%</span>
    </div>
  );
}

// ★★ THE MATH RAIL -- which numbers are measured, which are waiting, and
// what a flat reading means. Ruled 2026-08-27 (ORDER_math_rail), built
// 2026-09-03. Reads `outputs` and `pipeline` already in scope: NO fetch.
//
// The attractor caption says "indeterminate" on a tie, and as a WINNER
// statement that is correct. It is not a verdict on the distribution. A
// flat distribution is CI = 0 -- maximum entropy, minimum curvature -- the
// most resilient reading the instrument returns, and until this rail the
// panel called it a non-result. Same screen printed intensities of 0.000
// where edge_count was 0, i.e. where nothing had been measured at all.
//
// ★ Every WAITING quantity is rendered, one line each, with its named
// blocker. A hidden waiting row is the defect this rail ends.
function MathRail({ view, trust }: { view: ElinsV2Envelope; trust?: TrustSignal | null }) {
  const { outputs, pipeline } = view;
  const weights = Object.values(outputs.state_distribution ?? {}).filter(
    (x): x is number => typeof x === "number" && Number.isFinite(x),
  );
  const cx = compressionIndex(weights);
  // A flat read at n != 4 lands at -2e-16, not 0 -- float noise where H and
  // H_max differ in the last bit. "-0.0000" is not a reading. Display-side
  // only; the math and the word are taken from the true value.
  const ciShown = cx.kind === "ci" ? (Math.abs(cx.ci) < 1e-12 ? 0 : cx.ci) : 0;
  // #162 (e) -- the WORDS come from the one dictionary; the keys stay, and
  // the DOM ids (data-testid) are fixed slugs per key, so a word can change
  // in labels.ts without moving an identifier.
  const layers: Array<{ key: string; slug: string; label: string }> = [
    { key: "L5_pressure",  slug: "pressure",  label: labelFor("L5_pressure").word  },
    { key: "L6_drift",     slug: "drift",     label: labelFor("L6_drift").word     },
    { key: "L9_alignment", slug: "alignment", label: labelFor("L9_alignment").word },
  ];
  // ElinsV2Pipeline is a closed interface (no index signature); the rail reads
  // it by string key on purpose so a missing layer degrades to "no edges".
  const pipe = (pipeline ?? {}) as unknown as Record<string, unknown>;
  return (
    <div className={styles.section} data-testid="math-rail">
      <div className={styles.sectionLabel}>Math rail · measured / waiting</div>

      {cx.kind === "ci" ? (
        <div
          className={styles.railRow}
          data-testid="math-rail-ci"
          data-word={compressionWord(cx.ci)}
        >
          <span className={styles.railKey}>CI</span>
          <span className={styles.railVal}>{ciShown.toFixed(4)}</span>
          <span className={styles.railWord}>{compressionWord(cx.ci)}</span>
          {cx.ci < 0.1 ? (
            <span className={styles.railNote}>
              flat is maximum entropy -- a measurement, not a non-result
            </span>
          ) : null}
        </div>
      ) : (
        // ★ D5: no basis is a different KIND. Never NaN, never a number
        // that could be mistaken for a real CI.
        <div className={styles.railRow} data-testid="math-rail-ci" data-word="none">
          <span className={styles.railKey}>CI</span>
          <span className={styles.railVal}>--</span>
          <span className={styles.railNote}>
            {cx.reason === "single_attractor"
              ? `n = ${cx.n}: one attractor cannot be spread`
              : "no weight in the distribution"}
          </span>
        </div>
      )}

      {cx.kind === "ci" ? (
        <div className={styles.railRow} data-testid="math-rail-entropy">
          <span className={styles.railKey}>H</span>
          <span className={styles.railVal}>{cx.h.toFixed(4)}</span>
          <span className={styles.railKey}>{`H_max = ln ${cx.n}`}</span>
          <span className={styles.railVal}>{cx.hMax.toFixed(4)}</span>
        </div>
      ) : null}

      {layers.map(({ key, slug, label }) => {
        const layer = pipe[key] as { intensity?: unknown; edge_count?: unknown } | undefined;
        const edges =
          typeof layer?.edge_count === "number" && Number.isFinite(layer.edge_count)
            ? layer.edge_count : 0;
        const intensity =
          typeof layer?.intensity === "number" && Number.isFinite(layer.intensity)
            ? layer.intensity : null;
        return (
          <div
            key={key}
            className={styles.railRow}
            data-testid={`math-rail-${slug}`}
            data-edges={edges}
          >
            <span className={styles.railKey} title={key}>{label}</span>
            {edges > 0 && intensity !== null ? (
              <>
                <span className={styles.railVal}>{intensity.toFixed(3)}</span>
                <span className={styles.railNote}>
                  {edges} edge{edges === 1 ? "" : "s"}
                </span>
              </>
            ) : edges > 0 ? (
              // Edges exist but no finite intensity arrived: saying "no edges"
              // here would be false. Name what is actually missing.
              <span className={styles.railNote}>
                {edges} edge{edges === 1 ? "" : "s"} · intensity unavailable
              </span>
            ) : (
              // ★ edge_count 0 means nothing was measured. "0.000" would be a
              // confident reading with no measurement behind it.
              <span className={styles.railNote}>no edges</span>
            )}
          </div>
        );
      })}

      <div className={styles.railWaiting} data-testid="math-rail-waiting">
        {/* #162 (d) -- bound to the relationship's trust_signal (#23). */}
        <div data-testid="math-rail-basin-hop">{basinHopLine(trust)}</div>
        <div>fog_of_war -- awaiting PRO-tier ingest</div>
        <div>cohesion -- awaiting PRO-tier ingest</div>
        <div>E/r curvature -- awaiting a region graph</div>
      </div>
    </div>
  );
}

function AttractorBlock({
  distribution, attractor,
}: {
  distribution: Record<Attractor, number>;
  attractor: Attractor;
}) {
  const states: Attractor[] = ["S1", "S2", "S3", "S4"];
  // ★★ THE SECOND CONSUMER. The tie-break shipped to PersonalElins in
  // cdae4ba and missed this view, which kept printing the raw backend
  // value -- so CT-1's 2026-08-27 walk saw "attractor: S1 · aligned
  // coherence" rendered directly beneath a 25/25/25/25 distribution.
  // Same threshold, same copy, same testid: imported, not reimplemented.
  const verdict = attractorVerdict(
    distribution as unknown as Record<string, number>, attractor,
  );
  return (
    <div className={styles.section}>
      <div className={styles.sectionLabel} title="attractor">{labelFor("attractor").word}</div>
      <div className={styles.attractorRow}>
        {states.map((s) => {
          const v = clamp01(distribution[s] ?? 0);
          // ★ On a tie no column is "the" attractor -- highlighting one
          // would re-assert in the bars exactly what the caption declines
          // to say in words.
          const isAttractor = verdict.determinate && s === verdict.state;
          return (
            <div
              key={s}
              className={
                isAttractor ? styles.stateColActive : styles.stateCol
              }
              aria-current={isAttractor ? "true" : undefined}
            >
              <div className={styles.stateBarOuter}>
                <div
                  className={styles.stateBarInner}
                  style={{ height: `${Math.round(v * 100)}%` }}
                />
              </div>
              <div className={styles.stateLabel}>{s}</div>
              <div className={styles.stateValue}>
                {Math.round(v * 100)}
              </div>
            </div>
          );
        })}
      </div>
      {verdict.determinate ? (
        <div className={styles.subtle} data-testid="attractor-determinate">
          attractor: <strong>{verdict.state}</strong> ·{" "}
          {stateDescriptor(verdict.state)}
        </div>
      ) : (
        <div className={styles.subtle} data-testid="attractor-indeterminate">
          <strong>{INDETERMINATE_LABEL}</strong>
          <div>{indeterminateDetail(verdict.leaders)}</div>
        </div>
      )}
    </div>
  );
}

function stateDescriptor(s: Attractor): string {
  switch (s) {
    case "S1": return "aligned coherence";
    case "S2": return "pressured coherence";
    case "S3": return "fragmented";
    case "S4": return "collapse trajectory";
  }
}

function CollapseBlock({ collapse }: { collapse: CollapseState }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionLabel} title="collapse_state">{labelFor("collapse_state").word}</div>
      <div className={styles.collapseRow}>
        <span className={styles.collapseValue} data-state={collapse}>
          {collapse}
        </span>
        <span className={styles.subtle}>{collapseDescriptor(collapse)}</span>
      </div>
    </div>
  );
}

function collapseDescriptor(c: CollapseState): string {
  switch (c) {
    case "none": return "no collapse trajectory";
    case "soft": return "soft pressure boundary";
    case "hard": return "hard collapse signal";
  }
}

function P0P8Block({
  grid, timeline,
}: {
  grid: Record<PKey, number>;
  timeline?: ElinsV2Envelope["outputs"]["timeline"];
}) {
  const rows: Array<{
    label: string;
    cells: Array<{ key: PKey; cellLabel: string }>;
  }> = [
    {
      label: "peaceful",
      cells: [
        { key: "P0", cellLabel: "near" },
        { key: "P1", cellLabel: "mid"  },
        { key: "P2", cellLabel: "far"  },
      ],
    },
    {
      label: "contested",
      cells: [
        { key: "P3", cellLabel: "near" },
        { key: "P4", cellLabel: "mid"  },
        { key: "P5", cellLabel: "far"  },
      ],
    },
    {
      label: "ruptured",
      cells: [
        { key: "P6", cellLabel: "near" },
        { key: "P7", cellLabel: "mid"  },
        { key: "P8", cellLabel: "far"  },
      ],
    },
  ];
  return (
    <div className={styles.section}>
      <div className={styles.sectionLabel}>P0–P8 · resolution × timescale</div>
      <div className={styles.pGrid} role="table" aria-label="P0 to P8 grid">
        <div className={styles.pGridHeader} role="row">
          <span />
          <span>near</span>
          <span>
            mid
            {/* ★ The timeline MIDDLE, beside the P-grid MID band, so "the
                missing middle" (P1/P4/P7 resolution) and mid_term_days stop
                being conflated -- they are different axes that share a word. */}
            {timeline && Number.isFinite(timeline.mid_term_days) ? (
              <span className={styles.railNote} data-testid="pgrid-mid-days">
                {" · "}{timeline.mid_term_days}d
              </span>
            ) : null}
          </span>
          <span>far</span>
        </div>
        {rows.map((row) => (
          <div key={row.label} className={styles.pGridRow} role="row">
            <span className={styles.pRowLabel}>{row.label}</span>
            {row.cells.map(({ key }) => {
              const v = clamp01(grid[key] ?? 0);
              const pct = Math.round(v * 100);
              return (
                <span
                  key={key}
                  className={styles.pCell}
                  style={{ opacity: 0.15 + 0.85 * v }}
                  role="cell"
                  aria-label={`${key}: ${pct}%`}
                  title={`${key}: ${pct}%`}
                >
                  <span className={styles.pCellKey}>{key}</span>
                  <span className={styles.pCellValue}>{pct}</span>
                </span>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

function GeographyBlock({ tier }: { tier: GeographyTier | null }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionLabel}>Geography tier</div>
      <div className={styles.geoRow}>
        <span className={styles.tier} data-tier={tier ?? "none"}>
          {tier ?? "—"}
        </span>
        <span className={styles.subtle}>
          {tier ? tierDescriptor(tier) : "no regional context"}
        </span>
      </div>
    </div>
  );
}

function tierDescriptor(t: GeographyTier): string {
  switch (t) {
    case "T1": return "high coherence basin";
    case "T2": return "stable basin";
    case "T3": return "stressed basin";
    case "T4": return "fragile basin";
  }
}

function MultiplierBlock({ multiplier }: { multiplier: number }) {
  const m = isFinite(multiplier) ? multiplier : 1.0;
  const pct = Math.max(0, Math.min(1, (m - 1.0)));
  return (
    <div className={styles.section}>
      <div className={styles.sectionLabel}>Multiplier</div>
      <div className={styles.multRow}>
        <span className={styles.multValue}>{m.toFixed(2)}×</span>
        <div className={styles.multBarOuter}>
          <div
            className={styles.multBarInner}
            style={{ width: `${pct * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// -----------------------------------------------------------------
// Utils
// -----------------------------------------------------------------

function clamp01(v: number): number {
  if (!isFinite(v)) return 0;
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v;
}

function relativeTime(tsMs: number): string {
  const diff = Date.now() - tsMs;
  if (diff < 0) return "just now";
  const s = Math.floor(diff / 1000);
  if (s < 5) return "just now";
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
