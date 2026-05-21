// v70 / Unit 77 — Operator-level EL/INS dashboard.
//
// One canonical view for the operator's EL/INS state over time:
//   - classification distribution (pie chart)
//   - TSI over time (line chart)
//   - trend indicator (improving / declining / stable)
//   - last 20 records (table)
//
// Pure SVG charts, no external chart deps. Auth-gated via RequireAuth.

import { useCallback, useEffect, useState, type ReactElement } from "react";
import {
  ApiError,
  getElInsOperatorSummary,
  getElInsRecent,
  type ElInsOperatorSummaryResponse,
  type ElInsRecord,
} from "../lib/api";

const DEFAULT_SAMPLE = 20;

export default function OperatorElinsDashboard() {
  const [summary, setSummary] = useState<ElInsOperatorSummaryResponse | null>(null);
  const [records, setRecords] = useState<ElInsRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, r] = await Promise.all([
        getElInsOperatorSummary(DEFAULT_SAMPLE),
        getElInsRecent(DEFAULT_SAMPLE),
      ]);
      setSummary(s);
      setRecords(r.records);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  return (
    <div>
      <div className="panel">
        <h1>EL/INS DASHBOARD</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Consolidated reasoning-stability view for the authed operator.
          Pulls the last {DEFAULT_SAMPLE} records for distribution + TSI
          trend. Drill into a single thread via the per-user surface.
        </p>
        <div className="row" style={{ gap: 8, marginTop: 8, alignItems: "center" }}>
          <div className="muted" style={{ flex: 1, fontSize: 12 }}>
            {lastChecked ? `last checked ${lastChecked}` : ""}
          </div>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => void fetchAll()}
            disabled={loading}
            data-testid="el-ins-dashboard-refresh"
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="el-ins-dashboard-error">
            {error}
          </div>
        ) : null}
      </div>

      {summary ? (
        <div className="panel" data-testid="el-ins-dashboard-summary">
          <h2>SUMMARY</h2>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            <div>
              <h3 style={{ margin: "0 0 8px", fontSize: 12, letterSpacing: "0.5px", color: "var(--os-text-muted, #888)" }}>
                CLASSIFICATION DISTRIBUTION
              </h3>
              <PieChart
                size={140}
                data={[
                  { label: "balanced", value: summary.recent_classification_distribution.balanced, color: "var(--os-ok, #10b981)" },
                  { label: "high_el",  value: summary.recent_classification_distribution.high_el,  color: "var(--os-err, #ef4444)" },
                  { label: "high_ins", value: summary.recent_classification_distribution.high_ins, color: "var(--os-warn, #f59e0b)" },
                ]}
              />
              <Legend
                items={[
                  { label: "balanced", color: "var(--os-ok, #10b981)" },
                  { label: "high_el",  color: "var(--os-err, #ef4444)" },
                  { label: "high_ins", color: "var(--os-warn, #f59e0b)" },
                ]}
              />
            </div>
            <div>
              <h3 style={{ margin: "0 0 8px", fontSize: 12, letterSpacing: "0.5px", color: "var(--os-text-muted, #888)" }}>
                TSI OVER TIME
              </h3>
              <LineChart
                values={tsiSeries(records || [])}
                width={280}
                height={120}
                color="var(--os-accent, #00f0ff)"
                data-testid="el-ins-dashboard-tsi-chart"
              />
              <div style={{ marginTop: 8, fontSize: 12 }}>
                <span className="muted">avg TSI:</span>{" "}
                <span style={{ fontFamily: "var(--font-mono)" }}>{summary.avg_tsi}/100</span>
                {"  ·  "}
                <span className="muted">trend:</span>{" "}
                <span
                  data-testid="el-ins-dashboard-trend"
                  style={{
                    fontFamily: "var(--font-mono)",
                    color: trendColor(summary.trend),
                  }}
                >
                  {summary.trend.toUpperCase()}
                </span>
                {"  ·  "}
                <span className="muted">sample:</span>{" "}
                <span style={{ fontFamily: "var(--font-mono)" }}>{summary.sample_size}</span>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="panel">
        <h2>LAST {DEFAULT_SAMPLE} RECORDS</h2>
        {!records || records.length === 0 ? (
          <div className="empty">No EL/INS records yet for this operator.</div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }} data-testid="el-ins-dashboard-table">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                <th style={thStyle}>Timestamp</th>
                <th style={thStyle}>Thread</th>
                <th style={thStyle}>Classification</th>
                <th style={thStyle}>EL</th>
                <th style={thStyle}>INS</th>
                <th style={thStyle}>TSI</th>
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
                  <td style={tdStyle}>
                    {typeof (rec as ElInsRecord & { tsi?: number }).tsi === "number"
                      ? (rec as ElInsRecord & { tsi: number }).tsi
                      : <span className="muted">—</span>}
                  </td>
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

// ---------- SVG primitives ----------
interface PieSlice { label: string; value: number; color: string; }
function PieChart({ size, data }: { size: number; data: PieSlice[] }) {
  const total = data.reduce((acc, d) => acc + d.value, 0);
  const cx = size / 2;
  const cy = size / 2;
  const r = size / 2 - 4;
  if (total === 0) {
    return (
      <svg width={size} height={size} role="img" aria-label="empty distribution">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.12)" />
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle"
              fill="var(--os-text-muted, #888)" fontSize={11}>no data</text>
      </svg>
    );
  }
  let angle = -Math.PI / 2;
  const paths: ReactElement[] = [];
  for (const slice of data) {
    if (slice.value <= 0) continue;
    const sweep = (slice.value / total) * Math.PI * 2;
    const x1 = cx + r * Math.cos(angle);
    const y1 = cy + r * Math.sin(angle);
    angle += sweep;
    const x2 = cx + r * Math.cos(angle);
    const y2 = cy + r * Math.sin(angle);
    const largeArc = sweep > Math.PI ? 1 : 0;
    paths.push(
      <path
        key={slice.label}
        d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2} Z`}
        fill={slice.color}
      />,
    );
  }
  return (
    <svg width={size} height={size} role="img" aria-label="classification distribution">
      {paths}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.08)" />
    </svg>
  );
}

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", fontSize: 11 }}>
      {items.map((it) => (
        <li key={it.label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
          <span style={{ display: "inline-block", width: 10, height: 10, background: it.color }} />
          <span style={{ fontFamily: "var(--font-mono)" }}>{it.label}</span>
        </li>
      ))}
    </ul>
  );
}

function LineChart({ values, width, height, color, ...props }: {
  values: number[]; width: number; height: number; color: string;
  [key: string]: unknown;
}) {
  if (values.length === 0) {
    return (
      <svg width={width} height={height} {...props} role="img" aria-label="no tsi data">
        <rect x={0} y={0} width={width} height={height} fill="none" stroke="rgba(255,255,255,0.08)" />
        <text x={width / 2} y={height / 2} textAnchor="middle" dominantBaseline="middle"
              fill="var(--os-text-muted, #888)" fontSize={11}>no data</text>
      </svg>
    );
  }
  const pad = 6;
  const xs = values.length === 1
    ? [width / 2]
    : values.map((_, i) => pad + (i * (width - 2 * pad)) / (values.length - 1));
  const ys = values.map((v) => height - pad - ((v / 100) * (height - 2 * pad)));
  const points = xs.map((x, i) => `${x.toFixed(2)},${ys[i].toFixed(2)}`).join(" ");
  return (
    <svg width={width} height={height} {...props} role="img" aria-label="tsi over time">
      <rect x={0} y={0} width={width} height={height} fill="none" stroke="rgba(255,255,255,0.08)" />
      <polyline fill="none" stroke={color} strokeWidth={1.5} points={points} />
      {xs.map((x, i) => (
        <circle key={i} cx={x} cy={ys[i]} r={2} fill={color} />
      ))}
    </svg>
  );
}

// ---------- helpers ----------
function tsiSeries(records: ElInsRecord[]): number[] {
  // Records arrive newest-first; the chart wants chronological order.
  // Drop records without a tsi (records stored without thread_id never
  // get one).
  return [...records]
    .reverse()
    .map((r) => (r as ElInsRecord & { tsi?: number }).tsi)
    .filter((t): t is number => typeof t === "number");
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

function trendColor(t: string): string {
  if (t === "improving") return "var(--os-ok, #10b981)";
  if (t === "declining") return "var(--os-err, #ef4444)";
  return "var(--os-text-muted, #888)";
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
