// v73 / Unit 83 — Org-level timeline route.
//
// Three-tab view (24h / 7d / 30d). Founder-cohort gated server-side
// — non-founder users get a 403 banner. Surfaces only masked
// operator IDs + summarised payloads (never raw fields, never
// thread_ids).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getOrgTimeline,
  type OrgTimelineEntry,
  type OrgTimelineWindow,
} from "../lib/api";

const WINDOWS: readonly OrgTimelineWindow[] = ["24h", "7d", "30d"] as const;
const WINDOW_LABELS: Record<OrgTimelineWindow, string> = {
  "24h": "Last 24h",
  "7d":  "Last 7d",
  "30d": "Last 30d",
};

export default function OrgTimeline() {
  const [window_, setWindow] = useState<OrgTimelineWindow>("24h");
  const [data, setData] = useState<OrgTimelineEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getOrgTimeline(window_);
      setData(r.entries);
    } catch (e: unknown) {
      setError(formatError(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [window_]);

  useEffect(() => { void load(); }, [load]);

  return (
    <div>
      <div className="panel">
        <h1>ORG TIMELINE</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Read-only aggregated view of operator events. Operator IDs are
          masked (last 6 characters) and payloads are summarised — no
          raw fields, no thread IDs. Founder cohort required.
        </p>
        <div className="row" style={{ gap: 8, marginTop: 8 }} data-testid="el-ins-org-tabs">
          {WINDOWS.map((w) => (
            <button
              key={w}
              type="button"
              className={`btn btn-sm ${w === window_ ? "" : "btn-secondary"}`}
              onClick={() => setWindow(w)}
              disabled={loading}
              data-testid={`el-ins-org-tab-${w}`}
            >
              {WINDOW_LABELS[w]}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => void load()}
            disabled={loading}
            data-testid="el-ins-org-refresh"
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="el-ins-org-error">
            {error}
          </div>
        ) : null}
      </div>

      <div className="panel">
        {loading && !data ? (
          <div><span className="spinner" /> Loading…</div>
        ) : !data || data.length === 0 ? (
          <div className="empty" data-testid="el-ins-org-empty">
            No events in this window.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }} data-testid="el-ins-org-table">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                <th style={thStyle}>Timestamp</th>
                <th style={thStyle}>Operator (masked)</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Summary</th>
              </tr>
            </thead>
            <tbody>
              {data.map((e, i) => (
                <tr
                  key={`${e.timestamp_ms}-${i}`}
                  style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}
                >
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {formatTimestamp(e.timestamp_ms)}
                  </td>
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {e.operator_id}
                  </td>
                  <td style={{ ...tdStyle, color: typeColor(e.event_type) }}>
                    {e.event_type}
                  </td>
                  <td style={tdStyle}>{summariseOrgEntry(e)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export function summariseOrgEntry(e: OrgTimelineEntry): string {
  const p = e.payload_summary || {};
  if (e.event_type === "record") {
    const el = typeof p.el === "number" ? (p.el as number).toFixed(2) : "—";
    const ins = typeof p.ins === "number" ? (p.ins as number).toFixed(2) : "—";
    const tsi = typeof p.tsi === "number" ? p.tsi : "—";
    return `EL ${el} · INS ${ins} · TSI ${tsi}`;
  }
  if (e.event_type === "anomaly") {
    const sev = typeof p.severity === "number" ? p.severity : "?";
    const rule = typeof p.rule === "string" ? p.rule : "?";
    return `${rule} · severity ${sev}`;
  }
  if (e.event_type === "rollup") {
    const w = typeof p.window === "string" ? p.window : "?";
    const el = typeof p.avg_el === "number" ? (p.avg_el as number).toFixed(2) : "—";
    const ins = typeof p.avg_ins === "number" ? (p.avg_ins as number).toFixed(2) : "—";
    return `${w} · avg EL ${el} · avg INS ${ins}`;
  }
  return "system";
}

function typeColor(t: string): string {
  if (t === "anomaly") return "var(--os-err, #ef4444)";
  if (t === "rollup")  return "var(--os-warn, #f59e0b)";
  if (t === "record")  return "var(--os-accent, #00f0ff)";
  return "var(--os-text-muted, #888)";
}

function formatTimestamp(ts_ms: number): string {
  if (!ts_ms) return "—";
  try {
    return new Date(ts_ms).toISOString().replace("T", " ").slice(0, 19);
  } catch {
    return String(ts_ms);
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
