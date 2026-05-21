// v72 / Unit 80 — Anomalies (desktop).

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getElInsAnomalies,
  getUser,
  type ElInsAnomaly,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const DEFAULT_LIMIT = 100;

interface Props { onSignOut: () => void; onNavigate: (l: string) => void; }

export default function OperatorElinsAnomaliesShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [anomalies, setAnomalies] = useState<ElInsAnomaly[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      const r = await getElInsAnomalies(DEFAULT_LIMIT);
      setAnomalies(r.anomalies);
    } catch (e: unknown) {
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [handleAuthError]);

  useEffect(() => { void load(); }, [load]);

  const handleSignOut = () => { clearSession(); onSignOut(); };
  // v72 / Unit 80 — header anomaly indicator: red if any anomaly in last 24h.
  const cutoff = Date.now() / 1000 - 60 * 60 * 24;
  const hasNew = !!anomalies?.some((a) => a.timestamp >= cutoff);

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="EL/INS Anomalies"
      sidebar={<div style={signOutContainerStyle}>
        <button type="button" onClick={handleSignOut} style={signOutBtnStyle}>Sign out</button>
      </div>}
      center={<DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={containerStyle}>
          <div style={panelStyle}>
            <h1 style={h1Style}>
              EL/INS ANOMALIES
              {hasNew ? <span style={newDot} title="new anomalies in last 24h" /> : null}
            </h1>
            <p style={mutedStyle}>
              Newest-first list of detected anomalies. Triggered by EL &gt; 7.5,
              INS &lt; 2.0, TSI &gt; 85, or a diagonal quadrant jump.
            </p>
            {userName ? <div style={authedBadgeStyle}>Authed as <span style={authedBadgeNameStyle}>{userName}</span></div> : null}
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
              <button type="button" onClick={() => void load()} disabled={loading} style={btnSecondary}>REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={panelStyle}>
            {loading && !anomalies ? (
              <div>Loading…</div>
            ) : !anomalies || anomalies.length === 0 ? (
              <div style={emptyStyle}>No anomalies on record.</div>
            ) : (
              <table style={tableStyle}>
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
                      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>
                        {formatTimestamp(a.timestamp)}
                      </td>
                      <td style={{ ...tdStyle, color: typeColor(a.type) }}>{a.type}</td>
                      <td style={tdStyle}><span style={{ ...sevChip, background: sevColor(a.severity) }}>{a.severity}</span></td>
                      <td style={tdStyle}>{a.message}</td>
                      <td style={{ ...tdStyle, fontFamily: "monospace", fontSize: 11 }}>{a.thread_id || "—"}</td>
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

function typeColor(t: string): string {
  if (t === "quadrant_jump") return "#ef4444";
  if (t === "tsi_spike") return "#f59e0b";
  return "var(--color-text-primary)";
}

function sevColor(n: number): string {
  if (n >= 5) return "#ef4444";
  if (n >= 4) return "#f59e0b";
  return "#10b981";
}

function formatTimestamp(ts: number): string {
  if (!ts) return "—";
  try { return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19); }
  catch { return String(ts); }
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
const sevChip: React.CSSProperties = { display: "inline-block", padding: "2px 6px", color: "#04121b", fontFamily: "monospace", fontSize: 11, fontWeight: 700 };
const newDot: React.CSSProperties = { display: "inline-block", width: 8, height: 8, borderRadius: 4, background: "#ef4444", marginLeft: 8, verticalAlign: "middle" };
const signOutContainerStyle: React.CSSProperties = { marginTop: "auto", padding: 10, borderTop: "1px solid rgba(255,255,255,0.15)", display: "flex", justifyContent: "flex-end" };
const signOutBtnStyle: React.CSSProperties = { background: "transparent", border: "1px solid var(--color-text-secondary)", color: "var(--color-text-secondary)", padding: "4px 10px", fontSize: 11, cursor: "pointer", borderRadius: 0 };
