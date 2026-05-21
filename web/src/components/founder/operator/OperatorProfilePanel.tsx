// components/founder/operator/OperatorProfilePanel.tsx
// Inferred preferences + signal-mode + lifetime stats.

import type { V39OperatorState } from "../../../lib/api";

export interface OperatorProfilePanelProps {
  state: V39OperatorState;
}

export default function OperatorProfilePanel({ state }: OperatorProfilePanelProps) {
  const domains = Object.entries(state.preferred_domains || {})
    .sort((a, b) => b[1] - a[1]).slice(0, 8);
  const regions = Object.entries(state.preferred_regions || {})
    .sort((a, b) => b[1] - a[1]).slice(0, 8);
  const dmax = Math.max(0.001, ...domains.map(([, v]) => v));
  const rmax = Math.max(0.001, ...regions.map(([, v]) => v));

  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Profile</h2>
        <span style={mutedStyle}>
          ESO {state.external_signal_mode === "cloud_perplexity" ? "on" : "off"}
        </span>
      </header>

      <div style={statsRowStyle}>
        <Stat label="ELINS runs" value={String(state.elins_history?.length || 0)} />
        <Stat label="#G runs" value={String(state.g_history?.length || 0)} />
        <Stat label="Active" value={fmtTs(state.last_active_ts)} />
      </div>

      <h3 style={subHeader}>Preferred domains</h3>
      {domains.length === 0 ? (
        <div style={emptyStyle}>No preferences inferred yet</div>
      ) : (
        domains.map(([k, v]) => (
          <PrefRow key={k} name={k} weight={v} max={dmax} accent="var(--os-focus, #00F0FF)" />
        ))
      )}

      <h3 style={subHeader}>Preferred regions</h3>
      {regions.length === 0 ? (
        <div style={emptyStyle}>No regional preferences yet</div>
      ) : (
        regions.map(([k, v]) => (
          <PrefRow key={k} name={k} weight={v} max={rmax} accent="#fbbf24" />
        ))
      )}

      <h3 style={subHeader}>Account</h3>
      <Row label="user_id" value={state.user_id} mono />
      <Row label="created" value={fmtTs(state.created_ts)} mono />
      <Row label="signal mode" value={state.external_signal_mode} />
    </section>
  );
}

function PrefRow({ name, weight, max, accent }: {
  name: string; weight: number; max: number; accent: string;
}) {
  return (
    <div style={{ marginBottom: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
        <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{name}</span>
        <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{weight.toFixed(2)}</span>
      </div>
      <div style={{ height: 5, background: "var(--os-deep, #0a0a0a)", borderRadius: 3 }}>
        <div
          style={{
            width: `${Math.min(100, (weight / max) * 100)}%`,
            height: "100%", background: accent, borderRadius: 3,
          }}
        />
      </div>
    </div>
  );
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", fontSize: 12 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      <span style={{ fontFamily: mono ? "var(--font-mono, monospace)" : undefined }}>{value}</span>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)", textTransform: "uppercase", letterSpacing: 0.5 }}>{label}</div>
      <div style={{ fontSize: 14, fontFamily: "var(--font-mono, monospace)", color: "var(--os-text-primary, #fff)" }}>{value}</div>
    </div>
  );
}

function fmtTs(ts: number): string {
  if (!ts || ts <= 0) return "—";
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 16);
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
const statsRowStyle: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 10,
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 10, marginBottom: 4, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const emptyStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)", fontStyle: "italic",
};
const mutedStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)",
  fontFamily: "var(--font-mono, monospace)",
};
