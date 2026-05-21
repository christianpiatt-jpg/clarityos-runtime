// v73 / Unit 82 — Operator timeline route.
//
// Newest-first table of timeline events. Click-to-expand opens a
// JSON-payload modal. Auth-gated via RequireAuth.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getTimeline,
  type TimelineEvent,
} from "../lib/api";

const DEFAULT_LIMIT = 200;

export default function OperatorTimeline() {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TimelineEvent | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getTimeline(DEFAULT_LIMIT);
      setEvents(r.events);
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
        <h1>OPERATOR TIMELINE</h1>
        <p className="muted" style={{ marginTop: 4 }}>
          Newest-first chronological log of EL/INS records, anomalies,
          and roll-up reviews for the authed operator. Click a row to
          inspect the raw payload.
        </p>
        <div className="row" style={{ marginTop: 8, gap: 8 }}>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={() => void load()}
            disabled={loading}
            data-testid="el-ins-timeline-refresh"
          >
            REFRESH
          </button>
        </div>
        {error ? (
          <div className="banner err" style={{ marginTop: 8 }} data-testid="el-ins-timeline-error">
            {error}
          </div>
        ) : null}
      </div>

      <div className="panel">
        {loading && !events ? (
          <div><span className="spinner" /> Loading…</div>
        ) : !events || events.length === 0 ? (
          <div className="empty" data-testid="el-ins-timeline-empty">
            No timeline events yet.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }} data-testid="el-ins-timeline-table">
            <thead>
              <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
                <th style={thStyle}>Timestamp</th>
                <th style={thStyle}>Type</th>
                <th style={thStyle}>Summary</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr
                  key={e.id}
                  onClick={() => setSelected(e)}
                  style={{
                    borderBottom: "1px solid rgba(255,255,255,0.05)",
                    cursor: "pointer",
                  }}
                  data-testid={`el-ins-timeline-row-${e.id}`}
                >
                  <td style={{ ...tdStyle, fontFamily: "var(--font-mono)", fontSize: 11 }}>
                    {formatTimestamp(e.timestamp_ms)}
                  </td>
                  <td style={{ ...tdStyle, color: typeColor(e.event_type) }}>
                    {e.event_type}
                  </td>
                  <td style={tdStyle}>{summariseEvent(e)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected ? (
        <PayloadModal event={selected} onClose={() => setSelected(null)} />
      ) : null}
    </div>
  );
}

function PayloadModal({ event, onClose }: { event: TimelineEvent; onClose: () => void }) {
  return (
    <div
      data-testid="el-ins-timeline-modal"
      onClick={onClose}
      style={{
        position: "fixed", inset: 0,
        background: "rgba(0,0,0,0.5)",
        display: "flex", alignItems: "center", justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: "var(--os-bg-elev, #1a1f2e)",
          padding: 16,
          maxWidth: 600,
          maxHeight: "80vh",
          overflow: "auto",
          border: "1px solid rgba(255,255,255,0.15)",
        }}
      >
        <div className="row row-between" style={{ marginBottom: 8 }}>
          <h3 style={{ margin: 0, fontSize: 14, letterSpacing: "0.5px" }}>
            {event.event_type.toUpperCase()} · {formatTimestamp(event.timestamp_ms)}
          </h3>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            onClick={onClose}
            data-testid="el-ins-timeline-modal-close"
          >
            CLOSE
          </button>
        </div>
        <pre
          data-testid="el-ins-timeline-modal-payload"
          style={{
            margin: 0,
            padding: 12,
            background: "rgba(0,0,0,0.4)",
            fontFamily: "var(--font-mono)",
            fontSize: 11,
            whiteSpace: "pre-wrap",
          }}
        >
          {JSON.stringify(event.payload, null, 2)}
        </pre>
      </div>
    </div>
  );
}

// ---------- helpers ----------
export function summariseEvent(e: TimelineEvent): string {
  const p = e.payload || {};
  if (e.event_type === "record") {
    const el = typeof p.el === "number" ? (p.el as number).toFixed(2) : "—";
    const ins = typeof p.ins === "number" ? (p.ins as number).toFixed(2) : "—";
    const tsi = typeof p.tsi === "number" ? p.tsi : null;
    const mode = typeof p.reasoning_mode === "string" ? p.reasoning_mode : null;
    const parts = [`EL ${el}`, `INS ${ins}`];
    if (tsi !== null) parts.push(`TSI ${tsi}`);
    if (mode) parts.push(mode);
    return parts.join(" · ");
  }
  if (e.event_type === "anomaly") {
    const sev = typeof p.severity === "number" ? p.severity : "?";
    const t = typeof p.type === "string" ? p.type : "?";
    return `${t} · severity ${sev}`;
  }
  if (e.event_type === "rollup") {
    const w = typeof p.window === "string" ? p.window : "?";
    const el = typeof p.avg_el === "number" ? (p.avg_el as number).toFixed(2) : "—";
    const ins = typeof p.avg_ins === "number" ? (p.avg_ins as number).toFixed(2) : "—";
    const tsi = typeof p.avg_tsi === "number" ? p.avg_tsi : "—";
    return `${w} · EL ${el} · INS ${ins} · TSI ${tsi}`;
  }
  return "system event";
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
