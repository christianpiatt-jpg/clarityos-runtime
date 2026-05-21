// components/dashboard/MacroSummary.tsx
// Last macro-pass card: run id, ts, ESO mode, regions count, EP mean.

import { Link } from "react-router-dom";
import type { V38DashboardSnapshot } from "../../lib/api";

export interface MacroSummaryProps {
  macro: V38DashboardSnapshot["macro"];
}

export default function MacroSummary({ macro }: MacroSummaryProps) {
  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Macro-ELINS</h2>
        <Link to="/founder" style={mutedLinkStyle}>open macro view →</Link>
      </header>
      {macro.last_run_id ? (
        <div>
          <Row label="Last run" value={macro.last_run_id} mono />
          <Row label="Timestamp" value={fmtTs(macro.last_run_ts)} mono />
          <Row label="EP mean" value={macro.ep_mean !== null ? macro.ep_mean.toFixed(3) : "—"} mono />
          <Row label="Regions" value={String(macro.regions_count ?? "—")} mono />
          <Row label="ESO mode" value={macro.external_signal_mode || "—"} />
        </div>
      ) : (
        <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>
          No macro runs yet
        </div>
      )}
    </section>
  );
}

function fmtTs(ts: number | null): string {
  if (!ts || ts <= 0) return "—";
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", fontSize: 12 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      <span style={{ fontFamily: mono ? "var(--font-mono, monospace)" : undefined }}>{value}</span>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-md, 8px)",
  padding: 12,
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
};
const headerStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8,
};
const mutedLinkStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-focus, #00F0FF)", textDecoration: "none",
};
