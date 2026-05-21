// v70 / Unit 77 — Operator-level EL/INS dashboard (desktop).
//
// Mirror of web/src/routes/OperatorElinsDashboard.tsx. Pure SVG
// charts. Wrapped in DesktopAuthGate.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getElInsOperatorSummary,
  getElInsRecent,
  getUser,
  type ElInsOperatorSummaryResponse,
  type ElInsRecord,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const DEFAULT_SAMPLE = 20;

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function OperatorElinsDashboardShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [summary, setSummary] = useState<ElInsOperatorSummaryResponse | null>(null);
  const [records, setRecords] = useState<ElInsRecord[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

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
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => { void fetchAll(); }, [fetchAll]);

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="EL/INS Dashboard"
      sidebar={
        <div style={signOutContainerStyle}>
          <button type="button" onClick={handleSignOut} style={signOutBtnStyle}>
            Sign out
          </button>
        </div>
      }
      center={
        <DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={containerStyle}>
          <div style={panelStyle}>
            <h1 style={h1Style}>EL/INS DASHBOARD</h1>
            <p style={mutedStyle}>
              Consolidated reasoning-stability view for this operator.
              Pulls the last {DEFAULT_SAMPLE} records for distribution + TSI trend.
            </p>
            {userName ? (
              <div style={authedBadgeStyle}>
                Authed as <span style={authedBadgeNameStyle}>{userName}</span>
              </div>
            ) : null}
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
              <div style={{ flex: 1, fontSize: 12, color: "var(--color-text-secondary)" }}>
                {lastChecked ? `last checked ${lastChecked}` : ""}
              </div>
              <button
                type="button"
                onClick={() => void fetchAll()}
                disabled={loading}
                style={btnSecondary}
              >REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          {summary ? (
            <div style={panelStyle}>
              <h2 style={h2Style}>SUMMARY</h2>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
                <div>
                  <h3 style={subHeadingStyle}>CLASSIFICATION DISTRIBUTION</h3>
                  <PieChart
                    size={140}
                    data={[
                      { label: "balanced", value: summary.recent_classification_distribution.balanced, color: "#10b981" },
                      { label: "high_el",  value: summary.recent_classification_distribution.high_el,  color: "#ef4444" },
                      { label: "high_ins", value: summary.recent_classification_distribution.high_ins, color: "#f59e0b" },
                    ]}
                  />
                  <Legend items={[
                    { label: "balanced", color: "#10b981" },
                    { label: "high_el",  color: "#ef4444" },
                    { label: "high_ins", color: "#f59e0b" },
                  ]} />
                </div>
                <div>
                  <h3 style={subHeadingStyle}>TSI OVER TIME</h3>
                  <LineChart
                    values={tsiSeries(records || [])}
                    width={280}
                    height={120}
                    color="#00f0ff"
                  />
                  <div style={{ marginTop: 8, fontSize: 12, color: "var(--color-text-primary)" }}>
                    <span style={mutedInline}>avg TSI:</span>{" "}
                    <span style={mono}>{summary.avg_tsi}/100</span>
                    {"  ·  "}
                    <span style={mutedInline}>trend:</span>{" "}
                    <span style={{ ...mono, color: trendColor(summary.trend) }}>
                      {summary.trend.toUpperCase()}
                    </span>
                    {"  ·  "}
                    <span style={mutedInline}>sample:</span>{" "}
                    <span style={mono}>{summary.sample_size}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : null}

          <div style={panelStyle}>
            <h2 style={h2Style}>LAST {DEFAULT_SAMPLE} RECORDS</h2>
            {!records || records.length === 0 ? (
              <div style={emptyStyle}>No EL/INS records yet for this operator.</div>
            ) : (
              <table style={tableStyle}>
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
                      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
                        {formatTimestamp(rec.timestamp)}
                      </td>
                      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
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
                          : <span style={mutedInline}>—</span>}
                      </td>
                      <td style={tdStyle}>{rec.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
        </DesktopAuthGate>
      }
      insights={null}
    />
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
      <svg width={size} height={size}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.12)" />
        <text x={cx} y={cy} textAnchor="middle" dominantBaseline="middle"
              fill="var(--color-text-secondary)" fontSize={11}>no data</text>
      </svg>
    );
  }
  let angle = -Math.PI / 2;
  const paths: React.ReactElement[] = [];
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
    <svg width={size} height={size}>
      {paths}
      <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.08)" />
    </svg>
  );
}

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0", fontSize: 11 }}>
      {items.map((it) => (
        <li key={it.label} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2, color: "var(--color-text-primary)" }}>
          <span style={{ display: "inline-block", width: 10, height: 10, background: it.color }} />
          <span style={{ fontFamily: "monospace" }}>{it.label}</span>
        </li>
      ))}
    </ul>
  );
}

function LineChart({ values, width, height, color }: {
  values: number[]; width: number; height: number; color: string;
}) {
  if (values.length === 0) {
    return (
      <svg width={width} height={height}>
        <rect x={0} y={0} width={width} height={height} fill="none" stroke="rgba(255,255,255,0.08)" />
        <text x={width / 2} y={height / 2} textAnchor="middle" dominantBaseline="middle"
              fill="var(--color-text-secondary)" fontSize={11}>no data</text>
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
    <svg width={width} height={height}>
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
  if (cls === "high_el")  return "#ef4444";
  if (cls === "high_ins") return "#f59e0b";
  return "#10b981";
}

function trendColor(t: string): string {
  if (t === "improving") return "#10b981";
  if (t === "declining") return "#ef4444";
  return "var(--color-text-secondary)";
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

// ---------- styles ----------
const containerStyle: React.CSSProperties = {
  flex: 1, padding: 24, overflowY: "auto",
  display: "flex", flexDirection: "column", gap: 16,
};
const panelStyle: React.CSSProperties = {
  background: "var(--color-bg-surface)", padding: 16,
};
const h1Style: React.CSSProperties = {
  margin: 0, fontSize: 18, color: "var(--color-text-primary)",
};
const h2Style: React.CSSProperties = {
  margin: "0 0 8px", fontSize: 14, color: "var(--color-text-primary)",
};
const subHeadingStyle: React.CSSProperties = {
  margin: "0 0 8px", fontSize: 11, letterSpacing: "0.5px",
  color: "var(--color-text-secondary)",
};
const mutedStyle: React.CSSProperties = {
  margin: "4px 0", color: "var(--color-text-secondary)", fontSize: 13,
};
const mutedInline: React.CSSProperties = {
  color: "var(--color-text-secondary)",
};
const mono: React.CSSProperties = {
  fontFamily: "monospace",
  color: "var(--color-text-primary)",
};
const authedBadgeStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--color-text-secondary)", marginTop: 8, letterSpacing: "0.5px",
};
const authedBadgeNameStyle: React.CSSProperties = {
  color: "var(--color-text-primary)", fontFamily: "var(--font-mono)",
};
const btnSecondary: React.CSSProperties = {
  padding: "6px 12px", background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-secondary)", fontSize: 12, cursor: "pointer",
};
const tableStyle: React.CSSProperties = { width: "100%", borderCollapse: "collapse" };
const thStyle: React.CSSProperties = {
  textAlign: "left", padding: "8px 10px", fontWeight: 600,
  fontSize: 11, letterSpacing: "0.5px",
  color: "var(--color-text-secondary)",
};
const tdStyle: React.CSSProperties = {
  padding: "8px 10px", verticalAlign: "middle", fontSize: 12,
  color: "var(--color-text-primary)",
};
const bannerStyle: React.CSSProperties = {
  marginTop: 8, padding: 8,
  background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12,
};
const emptyStyle: React.CSSProperties = {
  color: "var(--color-text-secondary)", fontStyle: "italic",
};
const signOutContainerStyle: React.CSSProperties = {
  marginTop: "auto", padding: 10,
  borderTop: "1px solid rgba(255,255,255,0.15)",
  display: "flex", justifyContent: "flex-end",
};
const signOutBtnStyle: React.CSSProperties = {
  background: "transparent",
  border: "1px solid var(--color-text-secondary)",
  color: "var(--color-text-secondary)",
  padding: "4px 10px", fontSize: 11, cursor: "pointer", borderRadius: 0,
};
