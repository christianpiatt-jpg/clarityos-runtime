// v72 / Unit 80 — Anomalies route.
//
// Newest-first table of the authed operator's EL/INS anomalies.
// Columns: timestamp, type, severity, message, thread_id, record_id.
// Auth-gated via RequireAuth.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getElInsAnomalies,
  type ElInsAnomaly,
} from "../lib/api";

const DEFAULT_LIMIT = 100;

export default function OperatorElinsAnomalies() {
  const [anomalies, setAnomalies] = useState<ElInsAnomaly[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getElInsAnomalies(DEFAULT_LIMIT);
      setAnomalies(r.anomalies);
    } catch (e: unknown) {
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div>
      <div className="panel">
        <h1>EL/INS ANOMALIES</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Newest-first list of detected EL/INS anomalies for the authed
          operator. Triggered by EL &gt; 7.5 (high_el), INS &lt; 2.0
          (low_ins), TSI &gt; 85 (tsi_spike), or a diagonal quadrant
          jump between consecutive records (quadrant_jump). Detection
          runs after each per-turn EL/INS analysis.
        </p>
        <div className="row" style={{ marginTop: 8, gap: 8 }}>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => void load()}
            disabled={loading}
            data-testid="el-ins-anomalies-refresh"
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="el-ins-anomalies-error">
            {error}
          </div>
        ) : null}
      </div>

      <div className="panel">
        {loading && !anomalies ? (
          <div><span className="spinner" /> Loading…</div>
        ) : !anomalies || anomalies.length === 0 ? (
          <div className="empty" data-testid="el-ins-anomalies-empty">
            No anomalies on record.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }} data-testid="el-ins-anomalies-table">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                <th style={thStyle}>Timestamp</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Severity</th>
                <th style={thStyle}>Message</th>
                <th style={thStyle}>Thread</th>
              </tr>
            </thead>
            <tbody>
              {anomalies.map((a) => (
                <tr key={a.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {formatTimestamp(a.timestamp)}
                  </td>
                  <td style={{ ...tdStyle, color: typeColor(a.type) }}>{a.type}</td>
                  <td style={tdStyle}>
                    <SeverityChip n={a.severity} />
                  </td>
                  <td style={tdStyle}>{a.message}</td>
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {a.thread_id || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function SeverityChip({ n }: { n: number }) {
  const colour = n >= 5 ? "var(--os-err, #ef4444)"
    : n >= 4 ? "var(--os-warn, #f59e0b)"
    : "var(--os-ok, #10b981)";
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 6px",
      background: colour,
      color: "#04121b",
      fontFamily: "var(--font-mono)",
      fontSize: 11,
      fontWeight: 700,
    }}>{n}</span>
  );
}

function typeColor(t: string): string {
  if (t === "quadrant_jump") return "var(--os-err, #ef4444)";
  if (t === "tsi_spike")     return "var(--os-warn, #f59e0b)";
  return "var(--os-text, #fff)";
}

function formatTimestamp(ts: number): string {
  if (!ts) return "—";
  try {
    return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
  } catch {
    return String(ts);
  }
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
