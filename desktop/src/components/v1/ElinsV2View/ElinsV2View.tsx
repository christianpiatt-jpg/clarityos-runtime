// desktop/src/components/v1/ElinsV2View/ElinsV2View.tsx
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
//
// No new charting libraries. Inline SVG only where it carries weight.

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
import { ApiError } from "../../../lib/api";
import styles from "./ElinsV2View.module.css";

interface Props {
  /** Pre-computed envelope (e.g., already-stored ingestion-bus output). */
  envelope?: ElinsV2Envelope | null;
  /** Text + region to run /elins/v2/run against. If omitted, component is
   *  controlled-only. */
  runOn?: { rawText: string; region?: string | null } | null;
  /** Optional callback fired on every successful run, including initial. */
  onRun?: (env: ElinsV2Envelope) => void;
}

export default function ElinsV2View({ envelope, runOn, onRun }: Props) {
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

  // Auto-fetch on mount when uncontrolled.
  useEffect(() => {
    if (envelope || !canRerun) return;
    void doRun();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-sync when envelope prop changes.
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
      <CollapseBlock collapse={outputs.collapse_state} />
      <P0P8Block grid={outputs.P0_P8} />
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
  // Compact ETF summary: three "survival fractions" at 1y / 10y / 50y.
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

function AttractorBlock({
  distribution, attractor,
}: {
  distribution: Record<Attractor, number>;
  attractor: Attractor;
}) {
  const states: Attractor[] = ["S1", "S2", "S3", "S4"];
  return (
    <div className={styles.section}>
      <div className={styles.sectionLabel}>Attractor</div>
      <div className={styles.attractorRow}>
        {states.map((s) => {
          const v = clamp01(distribution[s] ?? 0);
          const isAttractor = s === attractor;
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
      <div className={styles.subtle}>
        attractor: <strong>{attractor}</strong> · {stateDescriptor(attractor)}
      </div>
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
      <div className={styles.sectionLabel}>Collapse</div>
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

function P0P8Block({ grid }: { grid: Record<PKey, number> }) {
  // 3x3 grid: rows are resolution (peaceful / contested / ruptured),
  // columns are timescale (near / mid / far).
  // Mapping: P0..P8 with resolution outer, timescale inner.
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
          <span>mid</span>
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
  // Range [1.0, 2.0]. Visualize as a filled bar where 1.0 = empty, 2.0 = full.
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
