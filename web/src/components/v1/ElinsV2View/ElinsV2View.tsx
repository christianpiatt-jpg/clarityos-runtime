// web/src/components/v1/ElinsV2View/ElinsV2View.tsx
//
// Web mirror of desktop/src/components/v1/ElinsV2View/ElinsV2View.tsx.
// Was a verbatim copy; at #180a the web copy renders what the wire
// carries (domain, signature, survival table, forecast, provenance) and
// the desktop mirror is BEHIND. The relative imports (../../../lib/elinsV2,
// ../../../lib/api) still resolve identically in both projects.
//
// Compact ELINS v2 view for the v1 InsightsPanel. Renders the analytical
// heads from /elins/v2/run as a somatic, structural summary — not a
// debug dump. 320px-width compatible (no fixed widths, no horizontal
// scrolling, no large numbers).
//
// ★ #180a -- THE DROP LEDGER, leg A. The wire carries 116 leaf keys; this
// panel read 28 and 77 arrived and died here. Every carried key now ends
// A (rendered, its instrument named in the caption, its internal path in
// a title attribute) or C (dropped, one-line reason in a comment beside
// the accessor). Absent -> an em dash; no number is invented where the
// wire has none. no_signal:true collapses the whole rail to one line
// (#110c).
//
//   C: input.* -- the request echoed back; the member typed it (#180a h).
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
  type PrimitiveKey,
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

// -----------------------------------------------------------------
// #180a -- reading the wire without inventing anything
// -----------------------------------------------------------------

type Obj = Record<string, unknown>;
const DASH = "—";

function obj(v: unknown): Obj {
  return v !== null && typeof v === "object" && !Array.isArray(v) ? (v as Obj) : {};
}
function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}
function str(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v : null;
}
function numList(v: unknown): number[] | null {
  return Array.isArray(v) && v.length > 0
    && v.every((x) => typeof x === "number" && Number.isFinite(x))
    ? (v as number[]) : null;
}
/** A reading, or the dash. Integers stay integers. */
function fmt(n: number | null, digits = 3): string {
  if (n === null) return DASH;
  return Number.isInteger(n) ? String(n) : n.toFixed(digits);
}
function pct(n: number | null): string {
  return n === null ? DASH : `${Math.round(n * 100)}%`;
}
/** "elins.v34.1" -> "elins v34.1"; "forecast.v34.1" -> "forecast v34.1". */
function versionWord(v: string | null): string | null {
  return v ? v.replace(/^([A-Za-z]+)\.(v)/, "$1 $2") : null;
}

const PRIMITIVES: PrimitiveKey[] = [
  "pressure", "tension", "trust", "drift", "contradiction", "alignment",
];
const HORIZONS = ["365", "3650", "18250"] as const;
const DOMAINS = [
  "geopolitical", "institutional", "personal", "social", "technological",
] as const;
/** The seven domain envelopes as the forecast engine names them. Absent
 *  on the wire -> the row shows a dash under the same name. */
const DOMAIN_ENVELOPES = [
  "Economic_Markets", "Geopolitical", "Social_Cultural", "Security_Military",
  "Legal_Justice", "Science_Technology", "Environmental",
];

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
  const pipe = obj(view.pipeline);
  const l8 = obj(pipe.L8_temporal);
  const engine = obj(l8.forecast_engine);
  const signatureLayer = obj(pipe.L10_signature);
  const signature = obj(signatureLayer.summary);
  // The versions on the wire name the instruments; the dictionary's are the
  // fallback when a layer arrives without one.
  const sigVersion = versionWord(str(signatureLayer.version));
  const fcVersion = versionWord(str(engine.version));
  const sigInstrument = sigVersion ?? labelFor("L10_signature").instrument;
  const fcInstrument = fcVersion ? `elins ${fcVersion}` : labelFor("etf_table").instrument;
  // #110c -- no signal is a different KIND: the whole rail is one line.
  const noSignal = signature.no_signal === true;

  const actions = (
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
  );

  if (noSignal) {
    return (
      <section className={styles.root} aria-label="ELINS v2 view">
        <Heading title="ELINS v2" subtitle={`engine: ${view.meta.engine}`} />
        {/* #110c -- CT-1: no signal means NOTHING ELSE is a reading. One
            line, the instrument named, no numbers from a run that found
            none. The actions below are the way to run again. */}
        <div
          className={styles.subtle}
          data-testid="elins-no-signal"
          title="pipeline.L10_signature.summary.no_signal"
        >
          no signal {DASH} {sigInstrument}
        </div>
        {actions}
        {error ? (
          <div role="alert" className={styles.error}>
            {error}
          </div>
        ) : null}
      </section>
    );
  }

  return (
    <section className={styles.root} aria-label="ELINS v2 view">
      <Heading
        title="ELINS v2"
        subtitle={`engine: ${view.meta.engine}`}
      />

      <DomainBlock domain={obj(pipe.L3_domain)} />
      <SignatureLine summary={signature} instrument={sigInstrument} />
      <SurvivalTable
        table={obj(l8.etf_table)}
        agg={obj(l8.etf_agg)}
        instrument={fcInstrument}
      />
      <AttractorBlock
        distribution={outputs.state_distribution}
        attractor={outputs.attractor}
      />
      <MathRail view={view} trust={trust} />
      <CollapseBlock collapse={outputs.collapse_state} />
      <ForecastRow f5={obj(l8.forecast_5day)} engine={engine} instrument={fcInstrument} />
      <P0P8Block grid={outputs.P0_P8} timeline={outputs.timeline} />
      <GeographyBlock tier={outputs.geography_tier} />
      <MultiplierBlock multiplier={outputs.multiplier} />
      <Provenance view={view} sigVersion={sigVersion} fcVersion={fcVersion} />

      {actions}

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

/** #180a -- a section caption: CT-1's word, the instrument that produced
 *  the reading, and the wire path in the title. */
function Caption({
  k, path, instrument,
}: {
  k: string;
  path: string;
  instrument?: string | null;
}) {
  const l = labelFor(k);
  const inst = instrument ?? l.instrument;
  return (
    <div className={styles.sectionLabel} title={path}>
      {l.word}
      {inst ? <span className={styles.instrument}>{" · "}{inst}</span> : null}
    </div>
  );
}

/** #180a (a) -- L3_domain: five bars, the top in bold. */
function DomainBlock({ domain }: { domain: Obj }) {
  const scores = obj(domain.scores);
  const top = str(domain.top);
  const effective = str(domain.effective_top);
  // The bold bar is the EFFECTIVE top when the pipeline moved it; the raw
  // top is named beside it in that case.
  const lead = effective ?? top;
  // C: L3_domain.hint -- an echo of the input's domain hint, not a reading (#180a h)
  const values = DOMAINS.map((d) => num(scores[d]));
  const max = Math.max(0, ...values.map((v) => v ?? 0));
  return (
    <div className={styles.section} data-testid="domain-row">
      <Caption k="L3_domain" path="pipeline.L3_domain.scores" />
      <div className={styles.domainRows}>
        {DOMAINS.map((d, i) => {
          const v = values[i];
          const isLead = d === lead;
          const width = v !== null && max > 0 ? Math.round((v / max) * 100) : 0;
          return (
            <div
              key={d}
              className={styles.domainRow}
              data-testid={`domain-${d}`}
              data-top={isLead ? "true" : undefined}
            >
              <span
                className={isLead ? styles.domainNameTop : styles.domainName}
                title={isLead
                  ? `pipeline.L3_domain.scores.${d} · pipeline.L3_domain.top${effective ? " · pipeline.L3_domain.effective_top" : ""}`
                  : `pipeline.L3_domain.scores.${d}`}
              >
                {d}
              </span>
              <span className={styles.domainBarOuter} aria-hidden="true">
                <span className={styles.domainBarInner} style={{ width: `${width}%` }} />
              </span>
              <span className={styles.domainValue}>{fmt(v, 2)}</span>
            </div>
          );
        })}
      </div>
      {effective && top && effective !== top ? (
        <div
          className={styles.subtle}
          data-testid="domain-effective"
          title="pipeline.L3_domain.top · pipeline.L3_domain.effective_top"
        >
          top {top} {"→"} effective {effective}
        </div>
      ) : null}
    </div>
  );
}

/** #180a (b) -- L10_signature.summary as one line. */
function SignatureLine({ summary, instrument }: { summary: Obj; instrument: string }) {
  const topP = str(summary.top_primitive);
  const topI = num(summary.top_primitive_intensity);
  const tokens: Array<{ key: string; path: string; label: string; value: string }> = [
    { key: "signal", path: "pipeline.L10_signature.summary.signal", label: "signal", value: str(summary.signal) ?? DASH },
    { key: "trend", path: "pipeline.L10_signature.summary.trend", label: "trend", value: str(summary.trend) ?? DASH },
    { key: "stress_score", path: "pipeline.L10_signature.summary.stress_score", label: "stress", value: fmt(num(summary.stress_score)) },
    { key: "relief_score", path: "pipeline.L10_signature.summary.relief_score", label: "relief", value: fmt(num(summary.relief_score)) },
    {
      key: "top_primitive",
      path: "pipeline.L10_signature.summary.top_primitive · pipeline.L10_signature.summary.top_primitive_intensity",
      label: "top",
      value: topP ? (topI !== null ? `${topP} (${fmt(topI)})` : topP) : DASH,
    },
    { key: "domain", path: "pipeline.L10_signature.summary.domain", label: "domain", value: str(summary.domain) ?? DASH },
  ];
  return (
    <div className={styles.section} data-testid="elins-signature">
      <Caption k="L10_signature" path="pipeline.L10_signature.summary" instrument={instrument} />
      <div className={styles.signature}>
        {tokens.map((t, i) => (
          <span key={t.key} title={t.path} data-testid={`sig-${t.key}`}>
            {i > 0 ? " · " : ""}
            {t.label} <strong>{t.value}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

/** #180a (c) -- etf_table: six primitives x three horizons, then the
 *  aggregate the old pills showed. Replaces the literal "ETF · survival".
 *
 *  UNITS. A table cell is the PROJECTED INTENSITY of that primitive at that
 *  horizon (elins_v2_view.py compute_etf: ep0 * exp(-lambda * n)), shown as
 *  the intensity it is. The aggregate row is the FRACTION surviving
 *  (_etf_agg: mean of cell / ep0), shown as a percent, as the old pills
 *  showed it. Two units, two formats, one table; the title on each cell
 *  names its key. */
function SurvivalTable({
  table, agg, instrument,
}: {
  table: Obj;
  agg: Obj;
  instrument: string;
}) {
  return (
    <div className={styles.section} data-testid="survival-table">
      <Caption k="etf_table" path="pipeline.L8_temporal.etf_table" instrument={instrument} />
      <div className={styles.survival} role="table" aria-label="survival by primitive and horizon">
        <div className={styles.survivalHead} role="row">
          <span />
          {HORIZONS.map((h) => <span key={h} role="columnheader">{h}d</span>)}
        </div>
        {PRIMITIVES.map((p) => {
          const row = obj(table[p]);
          return (
            <div key={p} className={styles.survivalRow} role="row" data-testid={`survival-${p}`}>
              <span className={styles.survivalName} title={`pipeline.L8_temporal.etf_table.${p}`}>{p}</span>
              {HORIZONS.map((h) => (
                <span
                  key={h}
                  role="cell"
                  className={styles.survivalCell}
                  title={`pipeline.L8_temporal.etf_table.${p}.${h}`}
                >
                  {fmt(num(row[h]))}
                </span>
              ))}
            </div>
          );
        })}
        <div className={styles.survivalRow} role="row" data-testid="survival-all">
          <span className={styles.survivalName} title="pipeline.L8_temporal.etf_agg">all</span>
          {(["n_365", "n_3650", "n_18250"] as const).map((k) => (
            <span
              key={k}
              role="cell"
              className={styles.survivalCell}
              title={`pipeline.L8_temporal.etf_agg.${k}`}
            >
              {pct(num(agg[k]))}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/** #180a (d) -- forecast_5day as one sparkline row; forecast_engine's
 *  envelopes folded beneath it. */
function ForecastRow({
  f5, engine, instrument,
}: {
  f5: Obj;
  engine: Obj;
  instrument: string;
}) {
  const days = Array.isArray(f5.days) ? f5.days.map((d) => obj(d)) : [];
  const nets = days.map((d) => num(d.projected_net));
  const points = nets.filter((n): n is number => n !== null);
  const start = num(f5.starting_net);
  const end = num(f5.ending_net);
  const trend = str(f5.trend);
  const nDays = num(engine.days);

  let path: string | null = null;
  if (points.length >= 2) {
    const min = Math.min(...points);
    const max = Math.max(...points);
    const span = max - min;
    const W = 100;
    const H = 24;
    path = points.map((v, i) => {
      const x = (i / (points.length - 1)) * W;
      const y = span > 0 ? H - 2 - ((v - min) / span) * (H - 4) : H / 2;
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  }

  return (
    <div className={styles.section} data-testid="forecast-row">
      <Caption k="forecast_5day" path="pipeline.L8_temporal.forecast_5day" instrument={instrument} />
      <div className={styles.forecastRow}>
        {path ? (
          <svg
            className={styles.spark}
            viewBox="0 0 100 24"
            preserveAspectRatio="none"
            aria-label="projected net by day"
            data-testid="forecast-spark"
          >
            <path d={path} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          </svg>
        ) : (
          <span className={styles.subtle} data-testid="forecast-spark-absent">{DASH}</span>
        )}
        <span className={styles.subtle} data-testid="forecast-nets">
          <span title="pipeline.L8_temporal.forecast_5day.starting_net">start {fmt(start)}</span>
          {" → "}
          <span title="pipeline.L8_temporal.forecast_5day.ending_net">end {fmt(end)}</span>
          {" · "}
          <span title="pipeline.L8_temporal.forecast_5day.trend">trend {trend ?? DASH}</span>
        </span>
      </div>
      <div
        className={styles.phases}
        data-testid="forecast-phases"
        title="pipeline.L8_temporal.forecast_5day.days[].day · phase · projected_net"
      >
        {days.length > 0 ? days.map((d, i) => {
          // The day number is the wire's, never the array index: an entry
          // without one reads a dash, not an invented ordinal.
          const dn = num(d.day);
          return (
            <span key={i}>
              {dn !== null ? `d${dn}` : DASH} {str(d.phase) ?? DASH} {fmt(nets[i], 2)}
            </span>
          );
        }) : <span>{DASH}</span>}
      </div>
      <details className={styles.envelopes} data-testid="forecast-envelopes">
        <summary title="pipeline.L8_temporal.forecast_engine">
          {labelFor("forecast_engine").word}{" · "}{instrument}
          {nDays !== null ? (
            <span title="pipeline.L8_temporal.forecast_engine.days" data-testid="env-days">{` · ${nDays} days`}</span>
          ) : null}
        </summary>
        <EnvelopeRows
          group="primitive_envelopes"
          keys={PRIMITIVES}
          data={obj(engine.primitive_envelopes)}
        />
        <EnvelopeRows
          group="domain_envelopes"
          keys={DOMAIN_ENVELOPES}
          data={obj(engine.domain_envelopes)}
        />
        <div className={styles.envelopeGroup}>
          <EnvelopeLine name="multi" path="pipeline.L8_temporal.forecast_engine.multi_envelope" value={engine.multi_envelope} />
          <EnvelopeLine name="chain" path="pipeline.L8_temporal.forecast_engine.chain" value={engine.chain} />
          <EnvelopeLine name="chain envelope" path="pipeline.L8_temporal.forecast_engine.chain_envelope" value={engine.chain_envelope} />
        </div>
      </details>
    </div>
  );
}

function EnvelopeRows({
  group, keys, data,
}: {
  group: string;
  keys: readonly string[];
  data: Obj;
}) {
  return (
    <div className={styles.envelopeGroup} title={`pipeline.L8_temporal.forecast_engine.${group}`}>
      {keys.map((k) => (
        <EnvelopeLine
          key={k}
          name={k}
          path={`pipeline.L8_temporal.forecast_engine.${group}.${k}`}
          value={data[k]}
        />
      ))}
    </div>
  );
}

/** One envelope: a list of numbers to two decimals, a scalar as itself, an
 *  object by its size, nothing as a dash. */
function EnvelopeLine({ name, path, value }: { name: string; path: string; value: unknown }) {
  let text: string;
  const list = numList(value);
  if (list) text = list.map((n) => n.toFixed(2)).join(" ");
  else if (value === null || value === undefined) text = DASH;
  else if (typeof value === "number" || typeof value === "string") text = String(value);
  else if (Array.isArray(value)) text = `[${value.length}]`;
  else text = `{${Object.keys(obj(value)).length}}`;
  return (
    <div className={styles.envelopeRow} data-testid={`env-${name.replace(/\s+/g, "_")}`}>
      <span title={path}>{name}</span>
      <span className={styles.envelopeVals} title={text}>{text}</span>
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
//
// C: L5_pressure.primitive / L6_drift.primitive / L9_alignment.primitive --
//    the row's own name, already the row's label (#180a h).
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

/** #180a (e) -- the timeline's three horizons caption the P-grid's three
 *  columns; the section carries its instrument. */
function TimelineDays({
  days, testid, path,
}: {
  days: unknown;
  testid: string;
  path: string;
}) {
  const n = num(days);
  if (n === null) return null;
  return (
    <span className={styles.railNote} data-testid={testid} title={path}>
      {" · "}{n}d
    </span>
  );
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
  const tl = obj(timeline);
  return (
    <div className={styles.section}>
      <Caption k="P0_P8" path="outputs.P0_P8" />
      <div className={styles.pGrid} role="table" aria-label="P0 to P8 grid">
        <div className={styles.pGridHeader} role="row">
          <span />
          <span>
            near
            <TimelineDays days={tl.short_term_days} testid="pgrid-near-days" path="outputs.timeline.short_term_days" />
          </span>
          <span>
            mid
            {/* ★ The timeline MIDDLE, beside the P-grid MID band, so "the
                missing middle" (P1/P4/P7 resolution) and mid_term_days stop
                being conflated -- they are different axes that share a word. */}
            <TimelineDays days={tl.mid_term_days} testid="pgrid-mid-days" path="outputs.timeline.mid_term_days" />
          </span>
          <span>
            far
            <TimelineDays days={tl.long_term_days} testid="pgrid-far-days" path="outputs.timeline.long_term_days" />
          </span>
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
      {/* #180a (g) -- the key in the title, the instrument in the caption. */}
      <Caption k="geography_tier" path="outputs.geography_tier" />
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
  // #180a -- an absent or non-finite multiplier is a dash, not "1.00x": a
  // neutral multiplier is a reading the wire has to send.
  const m = num(multiplier);
  const pct = m === null ? 0 : Math.max(0, Math.min(1, (m - 1.0)));
  return (
    <div className={styles.section}>
      {/* #180a (g) -- the key in the title, the instrument in the caption. */}
      <Caption k="multiplier" path="outputs.multiplier" />
      <div className={styles.multRow}>
        <span className={styles.multValue} data-testid="multiplier-value">
          {m === null ? DASH : `${m.toFixed(2)}×`}
        </span>
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

/** #180a (f) -- one provenance footer: what was run, by which versions,
 *  on how much text, through which view. */
function Provenance({
  view, sigVersion, fcVersion,
}: {
  view: ElinsV2Envelope;
  sigVersion: string | null;
  fcVersion: string | null;
}) {
  const pipe = obj(view.pipeline);
  const l1 = obj(pipe.L1_ingest);
  const l2 = obj(pipe.L2_normalize);
  const l4 = obj(pipe.L4_narrative);
  const l7 = obj(pipe.L7_basin);
  const l10 = obj(pipe.L10_signature);
  // C: L1_ingest.domain_hint -- an echo of the input's domain hint (#180a h)
  // C: L2_normalize.note -- a code comment carried as data, not a reading (#180a h)
  const scenario = str(l10.scenario_id) ?? str(l1.scenario_id);
  const chars = num(l1.char_count);
  const words = num(l1.word_count);
  const edges = num(l4.edge_count);
  const threshold = num(l4.threshold);
  // available is a VALUE, not an absence: false reads "unavailable"; only a
  // missing flag reads a dash.
  const available = typeof l7.available === "boolean" ? l7.available : null;
  const basin = str(l7.region);
  const normalized = typeof l2.normalized === "boolean" ? l2.normalized : null;
  const count = (n: number | null) => (n === null ? DASH : n.toLocaleString("en-US"));
  const tokens: Array<{ testid: string; path: string; text: string }> = [
    {
      testid: "prov-scenario",
      path: "pipeline.L10_signature.scenario_id · pipeline.L1_ingest.scenario_id",
      text: `scenario ${scenario ?? DASH}`,
    },
    { testid: "prov-elins-version", path: "elins_version", text: str(view.elins_version) ?? DASH },
    { testid: "prov-signature-version", path: "pipeline.L10_signature.version", text: sigVersion ?? DASH },
    { testid: "prov-forecast-version", path: "pipeline.L8_temporal.forecast_engine.version", text: fcVersion ?? DASH },
    {
      testid: "prov-size",
      path: "pipeline.L1_ingest.char_count · pipeline.L1_ingest.word_count",
      text: `${count(chars)} chars / ${count(words)} words`,
    },
    { testid: "prov-view", path: "meta.view_kind", text: `view ${str(obj(view.meta).view_kind) ?? DASH}` },
    {
      testid: "prov-edges",
      path: "pipeline.L4_narrative.edge_count · pipeline.L4_narrative.threshold",
      text: `edges ${fmt(edges)} · threshold ${fmt(threshold)}`,
    },
    {
      testid: "prov-basin",
      path: "pipeline.L7_basin.available · pipeline.L7_basin.region",
      text: `basin ${available === null ? DASH : available ? (basin ?? DASH) : "unavailable"}`,
    },
    { testid: "prov-region", path: "region", text: `region ${str(view.region) ?? DASH}` },
    {
      testid: "prov-normalized",
      path: "pipeline.L2_normalize.normalized",
      text: normalized === null ? DASH : normalized ? "normalized" : "not normalized",
    },
  ];
  return (
    <div className={styles.provenance} data-testid="elins-provenance">
      <Caption k="provenance" path="pipeline · outputs · meta" />
      <div className={styles.provenanceLine}>
        {tokens.map((t, i) => (
          <span key={t.testid} title={t.path} data-testid={t.testid}>
            {i > 0 ? " · " : ""}{t.text}
          </span>
        ))}
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
