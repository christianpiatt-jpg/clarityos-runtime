// components/founder/operator/OperatorTimeline.tsx
// Renders the user's ELINS + #G history side-by-side. Metadata only;
// raw scenario text never leaves the server.

import type { V39OperatorState } from "../../../lib/api";

export interface OperatorTimelineProps {
  state: V39OperatorState;
}

export default function OperatorTimeline({ state }: OperatorTimelineProps) {
  const elinsRows = [...(state.elins_history || [])].sort((a, b) => b.ts - a.ts).slice(0, 50);
  const gRows = [...(state.g_history || [])].sort((a, b) => b.ts - a.ts).slice(0, 50);
  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Timeline</h2>
        <span style={mutedStyle}>
          {elinsRows.length} ELINS · {gRows.length} #G
        </span>
      </header>
      <div style={gridStyle}>
        <div>
          <h3 style={subHeader}>ELINS history</h3>
          {elinsRows.length === 0 ? (
            <div style={emptyStyle}>No ELINS interactions yet</div>
          ) : (
            <ul style={listStyle}>
              {elinsRows.map((row, i) => (
                <li key={`${row.ts}-${i}`} style={rowStyle}>
                  <div style={rowHeadStyle}>
                    <strong style={{ fontSize: 12 }}>{row.region || "global"}</strong>
                    <span style={tsStyle}>{fmtTs(row.ts)}</span>
                  </div>
                  {row.topic && <div style={topicStyle}>{row.topic}</div>}
                  <code style={codeStyle}>{row.kind} · {row.elins_id || "—"}</code>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h3 style={subHeader}>#G history</h3>
          {gRows.length === 0 ? (
            <div style={emptyStyle}>No #G runs yet</div>
          ) : (
            <ul style={listStyle}>
              {gRows.map((row, i) => (
                <li key={`${row.ts}-${i}`} style={rowStyle}>
                  <div style={rowHeadStyle}>
                    <strong style={{ fontSize: 12 }}>#{row.mode}</strong>
                    <span style={tsStyle}>{fmtTs(row.ts)}</span>
                  </div>
                  {row.topic && <div style={topicStyle}>{row.topic}</div>}
                  {row.g_id && <code style={codeStyle}>{row.g_id}</code>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

function fmtTs(ts: number): string {
  if (!ts || ts <= 0) return "—";
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
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
const subHeader: React.CSSProperties = {
  fontSize: 11, marginBottom: 6, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const gridStyle: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12,
};
const listStyle: React.CSSProperties = { listStyle: "none", padding: 0, margin: 0 };
const rowStyle: React.CSSProperties = {
  padding: 6, marginBottom: 4,
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  background: "var(--os-deep, #0a0a0a)",
};
const rowHeadStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "baseline",
};
const tsStyle: React.CSSProperties = {
  fontSize: 10, color: "var(--os-text-tertiary, #585858)",
  fontFamily: "var(--font-mono, monospace)",
};
const topicStyle: React.CSSProperties = {
  marginTop: 2, fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)",
};
const codeStyle: React.CSSProperties = {
  display: "block", marginTop: 2, fontSize: 10,
  color: "var(--os-text-tertiary, #585858)",
};
const emptyStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)", fontStyle: "italic",
};
const mutedStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)",
  fontFamily: "var(--font-mono, monospace)",
};
