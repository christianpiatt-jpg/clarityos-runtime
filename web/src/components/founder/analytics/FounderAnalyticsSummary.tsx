// components/founder/analytics/FounderAnalyticsSummary.tsx
// v43 — single panel summarising users / billing / intelligence
// metrics. Lightweight (no heavy charts) — small bars + key numbers.

import { useCallback, useEffect, useState } from "react";
import {
  founderAnalyticsSummary,
  type V43FounderAnalyticsSummary,
} from "../../../lib/api";

export default function FounderAnalyticsSummary() {
  const [data, setData] = useState<V43FounderAnalyticsSummary | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await founderAnalyticsSummary();
      setData(r.summary);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Analytics</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={busy}
          style={refreshStyle}
        >{busy ? "…" : "Refresh"}</button>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {!data && busy && <SkeletonRows />}

      {data && (
        <div style={gridStyle}>
          {/* Users */}
          <div style={cardStyle}>
            <h3 style={subHeader}>Users</h3>
            <Stat label="Total" value={data.users.total} />
            <BarRow label="Active 7d" value={data.users.active_7d} max={Math.max(1, data.users.total)} />
            <BarRow label="Active 30d" value={data.users.active_30d} max={Math.max(1, data.users.total)} />
          </div>

          {/* Billing */}
          <div style={cardStyle}>
            <h3 style={subHeader}>Billing</h3>
            <ModePill mode={data.billing.mode} />
            <Stat label="Active subs" value={data.billing.active_subscriptions} />
            <Stat label="Past due" value={data.billing.past_due} warn={data.billing.past_due > 0} />
            <Stat label="Canceled" value={data.billing.canceled} />
          </div>

          {/* Intelligence */}
          <div style={cardStyle}>
            <h3 style={subHeader}>Intelligence (7d)</h3>
            <Stat label="ELINS runs" value={data.intelligence.elins_runs_7d} />
            <Stat label="#G runs" value={data.intelligence.g_runs_7d} />
            <Stat label="Macro runs" value={data.intelligence.macro_runs_7d} />
            <RateBar
              label="ESO usage"
              rate={data.intelligence.eso_usage_rate_7d}
            />
          </div>
        </div>
      )}

      {data && (
        <div style={metaStyle}>
          v43 · {new Date(data.ts * 1000).toISOString().slice(0, 19).replace("T", " ")}
        </div>
      )}
    </section>
  );
}

function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "3px 0", fontSize: 12 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      <span style={{
        fontFamily: "var(--font-mono, monospace)",
        color: warn ? "var(--os-boundary, #E02020)" : "var(--os-text-primary, #fff)",
        fontWeight: warn ? 600 : 400,
      }}>{value}</span>
    </div>
  );
}

function BarRow({ label, value, max }: { label: string; value: number; max: number }) {
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
        <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
        <span style={{ fontFamily: "var(--font-mono, monospace)" }}>
          {value} <span style={{ color: "var(--os-text-tertiary, #585858)" }}>/ {max}</span>
        </span>
      </div>
      <div style={{ height: 5, background: "var(--os-deep, #0a0a0a)", borderRadius: 3 }}>
        <div
          style={{
            width: `${Math.min(100, (value / Math.max(1, max)) * 100)}%`,
            height: "100%", background: "var(--os-focus, #00F0FF)", borderRadius: 3,
          }}
        />
      </div>
    </div>
  );
}

function RateBar({ label, rate }: { label: string; rate: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, rate)) * 100);
  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
        <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
        <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{pct}%</span>
      </div>
      <div style={{ height: 5, background: "var(--os-deep, #0a0a0a)", borderRadius: 3 }}>
        <div
          style={{
            width: `${pct}%`, height: "100%",
            background: "#fbbf24", borderRadius: 3,
          }}
        />
      </div>
    </div>
  );
}

function ModePill({ mode }: { mode: "test" | "live" | "disabled" }) {
  const palette: Record<string, [string, string]> = {
    live:     ["#dc2626", "#fff"],
    test:     ["#2563eb", "#fff"],
    disabled: ["#374151", "#fff"],
  };
  const [bg, fg] = palette[mode] || palette.disabled;
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 10px",
      background: bg, color: fg,
      fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
      borderRadius: "var(--radius-pill, 999px)",
      marginBottom: 6,
    }}>{mode.toUpperCase()}</span>
  );
}

function SkeletonRows() {
  return (
    <div style={gridStyle}>
      {[0, 1, 2].map((i) => (
        <div key={i} style={cardStyle}>
          <div style={{ height: 11, background: "var(--os-deep, #0a0a0a)", marginBottom: 8, width: "60%", borderRadius: 2 }} />
          <div style={{ height: 28, background: "var(--os-deep, #0a0a0a)", marginBottom: 6, borderRadius: 2 }} />
          <div style={{ height: 16, background: "var(--os-deep, #0a0a0a)", marginBottom: 6, borderRadius: 2 }} />
          <div style={{ height: 16, background: "var(--os-deep, #0a0a0a)", borderRadius: 2 }} />
        </div>
      ))}
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-md, 8px)",
  padding: 12,
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
  marginBottom: 12,
};
const headerStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8,
};
const refreshStyle: React.CSSProperties = {
  fontSize: 11, padding: "3px 10px",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
  borderRadius: "var(--radius-pill, 999px)",
};
const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
  gap: 12,
};
const cardStyle: React.CSSProperties = {
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  padding: 10,
  background: "var(--os-deep, #0a0a0a)",
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 0, marginBottom: 6, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const errorStyle: React.CSSProperties = {
  padding: 6, marginBottom: 8,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
const metaStyle: React.CSSProperties = {
  marginTop: 8, fontSize: 10, color: "var(--os-text-tertiary, #585858)",
  fontFamily: "var(--font-mono, monospace)", textAlign: "right",
};
