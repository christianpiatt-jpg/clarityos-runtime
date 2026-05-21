// v72 / Unit 81 — Roll-up (desktop).
//
// Three-card grid (24h / 7d / 30d). Each card: avg EL/INS/TSI,
// reasoning-mode SVG pie, record count.

import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  clearSession,
  getElInsRollup,
  getUser,
  type ElInsRollupResult,
  type ElInsRollupWindow,
} from "./lib/api";
import DesktopShell from "./DesktopShell";
import DesktopAuthGate from "./components/DesktopAuthGate";

const WINDOWS: readonly ElInsRollupWindow[] = ["24h", "7d", "30d"] as const;

interface Props { onSignOut: () => void; onNavigate: (l: string) => void; }

export default function OperatorElinsRollupShell({ onSignOut, onNavigate }: Props) {
  const userName = getUser();
  const [data, setData] = useState<Record<ElInsRollupWindow, ElInsRollupResult | null>>({
    "24h": null, "7d": null, "30d": null,
  });
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
      const results = await Promise.all(WINDOWS.map((w) => getElInsRollup(w)));
      const next: Record<ElInsRollupWindow, ElInsRollupResult | null> = {
        "24h": null, "7d": null, "30d": null,
      };
      WINDOWS.forEach((w, i) => { next[w] = results[i]; });
      setData(next);
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
      activeNav="EL/INS Roll-Up"
      sidebar={<div style={signOutContainerStyle}>
        <button type="button" onClick={handleSignOut} style={signOutBtnStyle}>Sign out</button>
      </div>}
      center={<DesktopAuthGate onRequestSignIn={handleSignOut}>
        <div style={containerStyle}>
          <div style={panelStyle}>
            <h1 style={h1Style}>EL/INS ROLL-UP</h1>
            <p style={mutedStyle}>
              Aggregate EL/INS + reasoning-mode statistics over three rolling
              windows. Deterministic — no LLM.
            </p>
            {userName ? <div style={authedBadgeStyle}>Authed as <span style={authedBadgeNameStyle}>{userName}</span></div> : null}
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8 }}>
              <button type="button" onClick={() => void load()} disabled={loading} style={btnSecondary}>REFRESH</button>
            </div>
            {error ? <div style={bannerStyle}>{error}</div> : null}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
            {WINDOWS.map((w) => <RollupCard key={w} window={w} result={data[w]} loading={loading} />)}
          </div>
        </div>
      </DesktopAuthGate>}
      insights={null}
    />
  );
}

function RollupCard({ window: window_, result, loading }: {
  window: ElInsRollupWindow; result: ElInsRollupResult | null; loading: boolean;
}) {
  return (
    <div style={cardStyle}>
      <h3 style={cardH3Style}>Last {window_}</h3>
      {loading && !result ? (
        <div style={{ color: "var(--color-text-secondary)" }}>Loading…</div>
      ) : !result ? (
        <div style={{ color: "var(--color-text-secondary)" }}>—</div>
      ) : (
        <>
          <div style={kvGrid}>
            <div style={kvK}>records</div>
            <div style={kvV}>{result.record_count}</div>
            <div style={kvK}>avg EL</div>
            <div style={kvV}>{result.avg_el.toFixed(2)}</div>
            <div style={kvK}>avg INS</div>
            <div style={kvV}>{result.avg_ins.toFixed(2)}</div>
            <div style={kvK}>avg TSI</div>
            <div style={kvV}>{result.avg_tsi}/100</div>
          </div>
          <h4 style={cardH4Style}>REASONING MODES</h4>
          <ReasoningModePie distribution={result.reasoning_mode_distribution} />
        </>
      )}
    </div>
  );
}

function ReasoningModePie({ distribution }: { distribution: Record<string, number> }) {
  const total = Object.values(distribution).reduce((acc, v) => acc + v, 0);
  if (total === 0) return <div style={{ fontSize: 11, color: "var(--color-text-secondary)" }}>no records</div>;
  const entries = Object.entries(distribution).sort((a, b) => b[1] - a[1]);
  const palette: Record<string, string> = {
    grounding: "#ef4444", analysis: "#f59e0b", structured_reflection: "#00f0ff",
    stabilization: "#888", extended_reasoning: "#10b981", normal: "#ccc",
  };
  const size = 120; const cx = size / 2; const cy = size / 2; const r = size / 2 - 4;
  let angle = -Math.PI / 2;
  const paths: React.ReactElement[] = [];
  for (const [mode, value] of entries) {
    if (value <= 0) continue;
    const sweep = (value / total) * Math.PI * 2;
    const x1 = cx + r * Math.cos(angle); const y1 = cy + r * Math.sin(angle);
    angle += sweep;
    const x2 = cx + r * Math.cos(angle); const y2 = cy + r * Math.sin(angle);
    const la = sweep > Math.PI ? 1 : 0;
    paths.push(<path key={mode} d={`M ${cx} ${cy} L ${x1} ${y1} A ${r} ${r} 0 ${la} 1 ${x2} ${y2} Z`} fill={palette[mode] || "#ccc"} />);
  }
  return (
    <div>
      <svg width={size} height={size}>{paths}<circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.08)" /></svg>
      <ul style={{ listStyle: "none", padding: 0, margin: "4px 0 0", fontSize: 11, color: "var(--color-text-primary)" }}>
        {entries.map(([mode, value]) => (
          <li key={mode} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <span style={{ display: "inline-block", width: 8, height: 8, background: palette[mode] || "#ccc" }} />
            <span style={{ fontFamily: "monospace" }}>{mode}: {value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
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
const cardStyle: React.CSSProperties = { background: "var(--color-bg-surface)", padding: 12 };
const cardH3Style: React.CSSProperties = { margin: 0, fontSize: 14, letterSpacing: "0.5px", color: "var(--color-text-primary)" };
const cardH4Style: React.CSSProperties = { margin: "12px 0 4px", fontSize: 11, letterSpacing: "0.5px", color: "var(--color-text-secondary)" };
const h1Style: React.CSSProperties = { margin: 0, fontSize: 18, color: "var(--color-text-primary)" };
const mutedStyle: React.CSSProperties = { margin: "4px 0", color: "var(--color-text-secondary)", fontSize: 13 };
const authedBadgeStyle: React.CSSProperties = { fontSize: 11, color: "var(--color-text-secondary)", marginTop: 8, letterSpacing: "0.5px" };
const authedBadgeNameStyle: React.CSSProperties = { color: "var(--color-text-primary)", fontFamily: "var(--font-mono)" };
const btnSecondary: React.CSSProperties = { padding: "6px 12px", background: "transparent", border: "1px solid var(--color-text-secondary)", color: "var(--color-text-secondary)", fontSize: 12, cursor: "pointer" };
const bannerStyle: React.CSSProperties = { marginTop: 8, padding: 8, background: "rgba(239,68,68,0.12)", color: "#ef4444", fontSize: 12 };
const kvGrid: React.CSSProperties = { display: "grid", gridTemplateColumns: "auto 1fr", rowGap: 4, columnGap: 12, fontSize: 13, marginTop: 8 };
const kvK: React.CSSProperties = { color: "var(--color-text-secondary)", fontSize: 12 };
const kvV: React.CSSProperties = { color: "var(--color-text-primary)", fontFamily: "monospace", fontSize: 12 };
const signOutContainerStyle: React.CSSProperties = { marginTop: "auto", padding: 10, borderTop: "1px solid rgba(255,255,255,0.15)", display: "flex", justifyContent: "flex-end" };
const signOutBtnStyle: React.CSSProperties = { background: "transparent", border: "1px solid var(--color-text-secondary)", color: "var(--color-text-secondary)", padding: "4px 10px", fontSize: 11, cursor: "pointer", borderRadius: 0 };
