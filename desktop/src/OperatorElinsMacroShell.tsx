// v69 / Unit 74 — Macro-EL/INS view (desktop).

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiError,
  clearSession,
  getElInsMacro,
  getUser,
  type ElInsRatioClassification,
  type ElInsRecord,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

interface WindowChoice { label: string; sinceSecondsAgo: number | null; }
const WINDOWS: readonly WindowChoice[] = [
  { label: "Last 24h",  sinceSecondsAgo: 60 * 60 * 24 },
  { label: "Last 7d",   sinceSecondsAgo: 60 * 60 * 24 * 7 },
  { label: "Last 30d",  sinceSecondsAgo: 60 * 60 * 24 * 30 },
  { label: "All time",  sinceSecondsAgo: null },
] as const;

interface Props {
  onSignOut: () => void;
  onNavigate: (label: string) => void;
}

export default function OperatorElinsMacroShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [windowIdx, setWindowIdx] = useState<number>(2);
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
      if (handleAuthError(e)) return;
      setError(formatError(e));
    } finally {
      setLoading(false);
    }
  }, [windowIdx, handleAuthError]);

  useEffect(() => { void fetchMacro(); }, [fetchMacro]);

  const stats = useMemo(() => computeStats(records || []), [records]);

  const handleSignOut = () => { clearSession(); onSignOut(); };

  return (
    <DesktopShell
      userName={userName}
      onNavigate={onNavigate}
      activeNav="EL/INS Macro"
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
            <h1 style={h1Style}>EL/INS MACRO</h1>
            <p style={mutedStyle}>
              Aggregate reasoning-stability stats over a rolling window
              for this operator.
            </p>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
              <select
                value={String(windowIdx)}
                onChange={(ev) => setWindowIdx(Number(ev.target.value))}
                disabled={loading}
                style={inputStyle}
              >
                {WINDOWS.map((w, i) => (
                  <option key={w.label} value={String(i)}>{w.label}</option>
                ))}
              </select>
              <div style={{ flex: 1, fontSize: 12, color: "var(--color-text-secondary)" }}>
                {lastChecked ? `last checked ${lastChecked}` : ""}
              </div>
              <button
                type="button"
                onClick={() => void fetchMacro()}
                disabled={loading}
                style={btnSecondary}
              >REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={panelStyle}>
            <h2 style={h2Style}>STATS</h2>
            {loading && !records ? (
              <div>Loading…</div>
            ) : (
              <div style={kvGrid}>
                <div style={kvK}>total records</div>
                <div style={kvV}>{stats.total}</div>
                <div style={kvK}>% balanced</div>
                <div style={kvV}>{stats.pct.balanced.toFixed(1)}%</div>
                <div style={kvK}>% high_el</div>
                <div style={kvV}>{stats.pct.high_el.toFixed(1)}%</div>
                <div style={kvK}>% high_ins</div>
                <div style={kvV}>{stats.pct.high_ins.toFixed(1)}%</div>
                <div style={kvK}>avg EL score</div>
                <div style={kvV}>{stats.avg_el.toFixed(2)}</div>
                <div style={kvK}>avg INS score</div>
                <div style={kvV}>{stats.avg_ins.toFixed(2)}</div>
              </div>
            )}
          </div>

          <div style={panelStyle}>
            <h2 style={h2Style}>RECORDS</h2>
            {!records || records.length === 0 ? (
              <div style={emptyStyle}>No records in this window.</div>
            ) : (
              <table style={tableStyle}>
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

// ---------- helpers ----------
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
  if (cls === "high_el")  return "#ef4444";
  if (cls === "high_ins") return "#f59e0b";
  return "#10b981";
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
const mutedStyle: React.CSSProperties = {
  margin: "4px 0", color: "var(--color-text-secondary)", fontSize: 13,
};
const inputStyle: React.CSSProperties = {
  background: "var(--color-bg-void)",
  border: "1px solid var(--color-border)",
  color: "var(--color-text-primary)",
  padding: 6, fontFamily: "inherit",
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
const kvGrid: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "auto 1fr", rowGap: 4, columnGap: 12,
  fontSize: 13,
};
const kvK: React.CSSProperties = {
  color: "var(--color-text-secondary)", fontSize: 12,
};
const kvV: React.CSSProperties = {
  color: "var(--color-text-primary)", fontFamily: "var(--font-mono)", fontSize: 12,
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
