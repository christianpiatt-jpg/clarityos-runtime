// v73 / Unit 82 — Operator timeline (desktop).
//
// Newest-first event log with click-to-expand JSON modal.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getTimeline,
  getUser,
  type TimelineEvent,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const DEFAULT_LIMIT = 200;

interface Props { onSignOut: () => void; onNavigate: (l: string) => void; }

export default function OperatorTimelineShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TimelineEvent | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      clearSession();
      onSignOut();
      return true;
    }
    return false;
  }, [onSignOut]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getTimeline(DEFAULT_LIMIT);
      setEvents(r.events);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => { void load(); }, [load]);

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Timeline"
      sidebar={<div style={signOutContainerStyle}>
        <button type="button" onClick={handleSignOut} style={signOutBtnStyle}>Sign out</button>
      </div>}
      center={<DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={containerStyle}>
          <div style={panelStyle}>
            <h1 style={h1Style}>OPERATOR TIMELINE</h1>
            <p style={mutedStyle}>
              Newest-first chronological log of EL/INS records, anomalies,
              and roll-up reviews. Click a row to inspect the raw payload.
            </p>
            {userName ? <div style={authedBadgeStyle}>Authed as <span style={authedBadgeNameStyle}>{userName}</span></div> : null}
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
              <button type="button" onClick={() => void load()} disabled={loading} style={btnSecondary}>REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={panelStyle}>
            {loading && !events ? (
              <div>Loading…</div>
            ) : !events || events.length === 0 ? (
              <div style={emptyStyle}>No timeline events yet.</div>
            ) : (
              <table style={tableStyle}>
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
                      style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", cursor: "pointer" }}
                    >
                      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
                        {formatTimestamp(e.timestamp_ms)}
                      </td>
                      <td style={{ ...tdStyle, color: typeColor(e.event_type) }}>{e.event_type}</td>
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
      </DesktopAuthGate>}
      insights={null}
    />
  );
}

function PayloadModal({ event, onClose }: { event: TimelineEvent; onClose: () => void }) {
  return (
    <div onClick={onClose} style={modalBackdropStyle}>
      <div onClick={(e) => e.stopPropagation()} style={modalStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
          <h3 style={{ margin: 0, fontSize: 14, letterSpacing: "0.5px", color: "var(--color-text-primary)" }}>
            {event.event_type.toUpperCase()} · {formatTimestamp(event.timestamp_ms)}
          </h3>
          <button type="button" onClick={onClose} style={btnSecondary}>CLOSE</button>
        </div>
        <pre style={preStyle}>{JSON.stringify(event.payload, null, 2)}</pre>
      </div>
    </div>
  );
}

function summariseEvent(e: TimelineEvent): string {
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
  if (t === "anomaly") return "#ef4444";
  if (t === "rollup")  return "#f59e0b";
  if (t === "record")  return "#00f0ff";
  return "var(--color-text-secondary)";
}

function formatTimestamp(ts_ms: number): string {
  if (!ts_ms) return "—";
  try { return new Date(ts_ms).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts_ms); }
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

const containerStyle: React.CSSProperties = { flex: 1, padding: 24, overflowY: "auto", display: "flex", flexDirection: "column", gap: 16 };
const panelStyle: React.CSSProperties = { background: "var(--color-bg-surface)", padding: 16 };
const h1Style: React.CSSProperties = { margin: 0, fontSize: 18, color: "var(--color-text-primary)" };
const mutedStyle: React.CSSProperties = { margin: "4px 0", color: "var(--color-text-secondary)", fontSize: 13 };
const authedBadgeStyle: React.CSSProperties = { fontSize: 11, color: "var(--color-text-secondary)", marginTop: 8, letterSpacing: "0.5px" };
const authedBadgeNameStyle: React.CSSProperties = { color: "var(--color-text-primary)", fontFamily: "var(--font-mono)" };
const btnSecondary: React.CSSProperties = { padding: "6px 12px", background: "transparent", border: "1px solid var(--color-text-secondary)", color: "var(--color-text-secondary)", fontSize: 12, cursor: "pointer" };
const tableStyle: React.CSSProperties = { width: "100%", borderCollapse: "collapse" };
const thStyle: React.CSSProperties = { textAlign: "left", padding: "8px 10px", fontWeight: 600, fontSize: 11, letterSpacing: "0.5px", color: "var(--color-text-secondary)" };
const tdStyle: React.CSSProperties = { padding: "8px 10px", verticalAlign: "middle", fontSize: 12, color: "var(--color-text-primary)" };
const bannerStyle: React.CSSProperties = { marginTop: 8, padding: 8, background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12 };
const emptyStyle: React.CSSProperties = { color: "var(--color-text-secondary)", fontStyle: "italic" };
const modalBackdropStyle: React.CSSProperties = { position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 };
const modalStyle: React.CSSProperties = { background: "var(--color-bg-surface)", padding: 16, maxWidth: 600, maxHeight: "80vh", overflow: "auto", border: "1px solid rgba(255,255,255,0.15)" };
const preStyle: React.CSSProperties = { margin: 0, padding: 12, background: "rgba(0,0,0,0.4)", fontFamily: "monospace", fontSize: 11, whiteSpace: "pre-wrap", color: "var(--color-text-primary)" };
const signOutContainerStyle: React.CSSProperties = { marginTop: "auto", padding: 10, borderTop: "1px solid rgba(255,255,255,0.15)", display: "flex", justifyContent: "flex-end" };
const signOutBtnStyle: React.CSSProperties = { background: "transparent", border: "1px solid var(--color-text-secondary)", color: "var(--color-text-secondary)", padding: "4px 10px", fontSize: 11, cursor: "pointer", borderRadius: 0 };
