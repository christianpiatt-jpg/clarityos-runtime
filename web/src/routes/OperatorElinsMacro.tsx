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
              <div className="k">% balanced</div>
              <div className="v">{stats.pct.balanced.toFixed(1)}%</div>
              <div className="k">% high_el</div>
              <div className="v">{stats.pct.high_el.toFixed(1)}%</div>
              <div className="k">% high_ins</div>
              <div className="v">{stats.pct.high_ins.toFixed(1)}%</div>
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
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
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
                <tr key={`${rec.timestamp}-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {formatTimestamp(rec.timestamp)}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {rec.thread_id || "—"}
                  </td>
                  <td style={{ ...tdStyle, color: classColor(rec.result.analysis.ratio_classification) }}>
                    {rec.result.analysis.ratio_classification}
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
  total: number;
  pct:   Record<ElInsRatioClassification, number>;
  avg_el:  number;
  avg_ins: number;
}

function computeStats(records: ElInsRecord[]): MacroStats {
  if (records.length === 0) {
    return {
      total: 0,
      pct:   { balanced: 0, high_el: 0, high_ins: 0 },
      avg_el:  0,
      avg_ins: 0,
    };
  }
  const counts = { balanced: 0, high_el: 0, high_ins: 0 } as Record<ElInsRatioClassification, number>;
  let sum_el = 0;
  let sum_ins = 0;
  for (const r of records) {
    counts[r.result.analysis.ratio_classification] += 1;
    sum_el += r.result.analysis.el_score;
    sum_ins += r.result.analysis.ins_score;
  }
  const n = records.length;
  return {
    total: n,
    pct: {
      balanced: (counts.balanced / n) * 100,
      high_el:  (counts.high_el / n) * 100,
      high_ins: (counts.high_ins / n) * 100,
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

function classColor(cls: string): string {
  if (cls === "high_el")  return "var(--os-err, #ef4444)";
  if (cls === "high_ins") return "var(--os-warn, #f59e0b)";
  return "var(--os-ok, #10b981)";
}

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
