// v73 / Unit 83 — Org timeline (desktop).
//
// Three-tab view (24h / 7d / 30d). Founder-gated server-side.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getOrgTimeline,
  getUser,
  type OrgTimelineEntry,
  type OrgTimelineWindow,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const WINDOWS: readonly OrgTimelineWindow[] = ["24h", "7d", "30d"] as const;
const WINDOW_LABELS: Record<OrgTimelineWindow, string> = {
  "24h": "Last 24h", "7d": "Last 7d", "30d": "Last 30d",
};

interface Props { onSignOut: () => void; onNavigate: (l: string) => void; }

export default function OrgTimelineShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [window_, setWindow] = useState<OrgTimelineWindow>("24h");
  const [data, setData] = useState<OrgTimelineEntry[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleAuthError = useCallback((e: unknown): boolean => {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      // 403 (non-founder) is NOT an auth-loss — surface inline instead
      // of bouncing to SignIn.
      if (e.status === 401) {
        clearSession();
        onSignOut();
        return true;
      }
    }
    return false;
  }, [onSignOut]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await getOrgTimeline(window_);
      setData(r.entries);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [window_, handleAuthError]);

  useEffect(() => { void load(); }, [load]);

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="Org Timeline"
      sidebar={<div style={signOutContainerStyle}>
        <button type="button" onClick={handleSignOut} style={signOutBtnStyle}>Sign out</button>
      </div>}
      center={<DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={containerStyle}>
          <div style={panelStyle}>
            <h1 style={h1Style}>ORG TIMELINE</h1>
            <p style={mutedStyle}>
              Read-only aggregated view of operator events. Operator IDs
              are masked (last 6 characters); payloads are summarised.
              Founder cohort required.
            </p>
            {userName ? <div style={authedBadgeStyle}>Authed as <span style={authedBadgeNameStyle}>{userName}</span></div> : null}
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
              {WINDOWS.map((w) => (
                <button
                  key={w}
                  type="button"
                  onClick={() => setWindow(w)}
                  disabled={loading}
                  style={w === window_ ? btnPrimary : btnSecondary}
                >
                  {WINDOW_LABELS[w]}
                </button>
              ))}
              <div style={{ flex: 1 }} />
              <button type="button" onClick={() => void load()} disabled={loading} style={btnSecondary}>REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={panelStyle}>
            {loading && !data ? (
              <div>Loading…</div>
            ) : !data || data.length === 0 ? (
              <div style={emptyStyle}>No events in this window.</div>
            ) : (
              <table style={tableStyle}>
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
                    <tr key={`${e.timestamp_ms}-${i}`} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
                        {formatTimestamp(e.timestamp_ms)}
                      </td>
                      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>{e.operator_id}</td>
                      <td style={{ ...tdStyle, color: typeColor(e.event_type) }}>{e.event_type}</td>
                      <td style={tdStyle}>{summariseOrgEntry(e)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </DesktopAuthGate>}
      insights={null}
    />
  );
}

function summariseOrgEntry(e: OrgTimelineEntry): string {
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
const btnPrimary: React.CSSProperties = { padding: "6px 12px", background: "var(--color-accent-cyan, #00f0ff)", border: "none", color: "#000", fontSize: 12, fontWeight: 700, cursor: "pointer" };
const btnSecondary: React.CSSProperties = { padding: "6px 12px", background: "transparent", border: "1px solid var(--color-text-secondary)", color: "var(--color-text-secondary)", fontSize: 12, cursor: "pointer" };
const tableStyle: React.CSSProperties = { width: "100%", borderCollapse: "collapse" };
const thStyle: React.CSSProperties = { textAlign: "left", padding: "8px 10px", fontWeight: 600, fontSize: 11, letterSpacing: "0.5px", color: "var(--color-text-secondary)" };
const tdStyle: React.CSSProperties = { padding: "8px 10px", verticalAlign: "middle", fontSize: 12, color: "var(--color-text-primary)" };
const bannerStyle: React.CSSProperties = { marginTop: 8, padding: 8, background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12 };
const emptyStyle: React.CSSProperties = { color: "var(--color-text-secondary)", fontStyle: "italic" };
const signOutContainerStyle: React.CSSProperties = { marginTop: "auto", padding: 10, borderTop: "1px solid rgba(255,255,255,0.15)", display: "flex", justifyContent: "flex-end" };
const signOutBtnStyle: React.CSSProperties = { background: "transparent", border: "1px solid var(--color-text-secondary)", color: "var(--color-text-secondary)", padding: "4px 10px", fontSize: 11, cursor: "pointer", borderRadius: 0 };
