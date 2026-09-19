// v69 / Unit 74 — Macro-EL/INS view.
//
// Per-operator aggregate stats over the macro data set. Reads
// /el_ins/macro with an optional ``since`` cutoff (UI exposes
// "last 24h / 7d / 30d / all time"). Shows:
//   - total record count
//   - distribution of ratio_classification (% balanced / high_el / high_ins)
//   - average el_score / ins_score
//   - a chronological list of the underlying records for inspection

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  getElInsMacro,
  type ElInsRatioClassification,
  type ElInsRecord,
} from "../lib/api";
import { readsNeeded } from "../lib/counts";
import { elInsClassColor, elInsClassWord } from "../lib/labels";

interface WindowChoice { label: string; sinceSecondsAgo: number | null; }
const WINDOWS: readonly WindowChoice[] = [
  { label: "Last 24h",  sinceSecondsAgo: 60 * 60 * 24 },
  { label: "Last 7d",   sinceSecondsAgo: 60 * 60 * 24 * 7 },
  { label: "Last 30d",  sinceSecondsAgo: 60 * 60 * 24 * 30 },
  { label: "All time",  sinceSecondsAgo: null },
] as const;

export default function OperatorElinsMacro() {
  const [windowIdx, setWindowIdx] = useState<number>(2); // default 30d
  const [records, setRecords] = useState<ElInsRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const fetchMacro = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const w = WINDOWS[windowIdx];
      const since = w.sinceSecondsAgo === null
        ? undefined
        : (Date.now() / 1000) - w.sinceSecondsAgo;
      const r = await getElInsMacro(since ?? null);
      setRecords(r.records);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [windowIdx]);

  useEffect(() => { void fetchMacro(); }, [fetchMacro]);

  const stats = useMemo(() => computeStats(records || []), [records]);

  return (
    <div>
      <div className="panel">
        <h1>EL/INS MACRO</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Aggregate reasoning-stability stats for this operator over a
          rolling window. The cockpit indicator shows the most recent
          single record; this surface shows the distribution.
        </p>
        <div className="row" style={{ gap: 8, marginTop: 8, alignItems: "center" }}>
          <select
            className="input"
            style={{ flex: 0 }}
            value={String(windowIdx)}
            onChange={(ev) => setWindowIdx(Number(ev.target.value))}
            disabled={loading}
            data-testid="el-ins-macro-window"
          >
            {WINDOWS.map((w, i) => (
              <option key={w.label} value={String(i)}>{w.label}</option>
            ))}
          </select>
          <div className="muted" style={{ flex: 1, fontSize: 12 }}>
            {lastChecked ? `last checked ${lastChecked}` : ""}
          </div>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => void fetchMacro()}
            disabled={loading}
            data-testid="el-ins-macro-refresh"
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="el-ins-macro-error">
            {error}
          </div>
        ) : null}
      </div>

      <div className="panel">
        <h2>STATS</h2>
        {loading && !records ? (
          <div><span className="spinner" /> Loading…</div>
        ) : (
          <div data-testid="el-ins-macro-stats">
            <div className="kv">
              <div className="k">total records</div>
              <div className="v">{stats.total}</div>
              {/* #374 -- the records that carried NO reading are named, and
                  they are named BEFORE the percentages, because they are
                  what the percentages are not about. Silence here is what
                  made three numbers add to under 100 with no explanation. */}
              <div className="k">no reading (0/0)</div>
              <div className="v" data-testid="el-ins-macro-unmapped">
                {stats.unmapped > 0
                  ? `${stats.unmapped} of ${stats.total}`
                  : "none"}
              </div>
              {/* F -- a percentage of one read is that read: say the count.
                  #374 -- the gate is on MAPPED reads, not on total: a page of
                  0/0 records has no split to show however many there are. */}
              {stats.mapped < 2 ? (
                <>
                  <div className="k">classification split</div>
                  <div className="v" data-testid="el-ins-macro-needs2">{readsNeeded(stats.mapped)}</div>
                </>
              ) : (
                <>
                  <div className="k" title="share of the reads that carried a reading">% balanced</div>
                  <div className="v">{stats.pct.balanced.toFixed(1)}%</div>
                  <div className="k">% high_el</div>
                  <div className="v">{stats.pct.high_el.toFixed(1)}%</div>
                  <div className="k">% high_ins</div>
                  <div className="v">{stats.pct.high_ins.toFixed(1)}%</div>
                </>
              )}
              <div className="k">avg EL score</div>
              <div className="v">{stats.avg_el.toFixed(2)}</div>
              <div className="k">avg INS score</div>
              <div className="v">{stats.avg_ins.toFixed(2)}</div>
            </div>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>RECORDS</h2>
        {!records || records.length === 0 ? (
          <div className="empty">No records in this window.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }} data-testid="el-ins-macro-table">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(20, 24, 28, 0.08)" }}>
                <th style={thStyle}>Timestamp</th>
                <th style={thStyle}>Thread</th>
                <th style={thStyle}>Classification</th>
                <th style={thStyle}>EL</th>
                <th style={thStyle}>INS</th>
                <th style={thStyle}>Source</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec, i) => (
                <tr key={`${rec.timestamp}-${i}`} style={{ borderBottom: "1px solid rgba(20, 24, 28, 0.05)" }}>
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {formatTimestamp(rec.timestamp)}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {rec.thread_id || "—"}
                  </td>
                  <td style={{ ...tdStyle, color: classColor(rec.result.analysis.ratio_classification) }}>
                    {elInsClassWord(rec.result.analysis.ratio_classification)}
                  </td>
                  <td style={tdStyle}>{rec.result.analysis.el_score.toFixed(2)}</td>
                  <td style={tdStyle}>{rec.result.analysis.ins_score.toFixed(2)}</td>
                  <td style={tdStyle}>{rec.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ---------- compute ----------
interface MacroStats {
  /** every record looked at */
  total: number;
  /** #374 -- records that carried a reading; the denominator of `pct` */
  mapped: number;
  /** #374 -- records with no reading at all (0/0) */
  unmapped: number;
  // ★ pct is NOT Record<ElInsRatioClassification, number> any more: that
  // union gained UNMAPPED in #374, and there is no such thing as "the
  // percentage of readings that were not readings". The three real classes
  // are named explicitly so the type cannot drift back.
  pct:   { balanced: number; high_el: number; high_ins: number };
  avg_el:  number;
  avg_ins: number;
}

function computeStats(records: ElInsRecord[]): MacroStats {
  if (records.length === 0) {
    return {
      total: 0, mapped: 0, unmapped: 0,
      pct:   { balanced: 0, high_el: 0, high_ins: 0 },
      avg_el:  0,
      avg_ins: 0,
    };
  }
  // ★ #374 -- THE COUNTER WAS CLOSED AT THREE KEYS WHILE THE WIRE CARRIED
  // FOUR. `counts[ratio_classification] += 1` on an UNMAPPED record indexed a
  // key that did not exist, so `undefined + 1` wrote NaN to a phantom entry
  // and the record left the distribution entirely -- while `total` still
  // counted it. The three percentages then divided by a denominator that
  // included records none of them represented, so they summed to well under
  // 100 with nothing on the page saying why. That is #355's own defect
  // wearing a percentage.
  const counts = { balanced: 0, high_el: 0, high_ins: 0, UNMAPPED: 0 } as
    Record<ElInsRatioClassification, number>;
  let sum_el = 0;
  let sum_ins = 0;
  for (const r of records) {
    const cls = r.result.analysis.ratio_classification;
    // an unrecognised value counts as unmapped rather than vanishing
    if (cls in counts) counts[cls] += 1;
    else counts.UNMAPPED += 1;
    sum_el += r.result.analysis.el_score;
    sum_ins += r.result.analysis.ins_score;
  }
  const n = records.length;
  // ★ THE DENOMINATOR IS THE MAPPED COUNT. The three classes are a
  // distribution OVER the records that carried a reading, not over every
  // record looked at; `total` and `unmapped` report the rest honestly.
  const mapped = n - counts.UNMAPPED;
  // #374-W -- an earlier draft also carried `const d = mapped || 1`. It was
  // DEAD: the ternaries below already return 0 when mapped is 0, so the
  // `|| 1` could never be reached, and a test that claimed to guard it could
  // not fail. One guard, in one place.
  return {
    total: n,
    mapped,
    unmapped: counts.UNMAPPED,
    pct: {
      balanced: mapped ? (counts.balanced / mapped) * 100 : 0,
      high_el:  mapped ? (counts.high_el / mapped) * 100 : 0,
      high_ins: mapped ? (counts.high_ins / mapped) * 100 : 0,
    },
    avg_el:  sum_el / n,
    avg_ins: sum_ins / n,
  };
}

function formatTimestamp(ts: number): string {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
  } catch {
    return String(ts);
  }
}

// #374 -- the private copy is GONE. It fell through to the OK green for
// any value it did not recognise, so #355's new UNMAPPED rendered in the
// colour of a healthy balanced reading. One rule, one implementation.
const classColor = elInsClassColor;

function formatError(e: unknown): string {
  if (e instanceof ApiError) {
    if (typeof e.body === "object" && e.body && "detail" in (e.body as Record<string, unknown>)) {
      const d = (e.body as Record<string, unknown>).detail;
      if (typeof d === "string") return d;
    }
    return `${e.code}: ${e.message}`;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}

const thStyle: React.CSSProperties = {
  textAlign: "left", padding: "8px 10px", fontWeight: 600,
  fontSize: 11, letterSpacing: "0.5px",
  color: "var(--os-text-muted, #888)",
};
const tdStyle: React.CSSProperties = {
  padding: "8px 10px", verticalAlign: "middle", fontSize: 12,
};
