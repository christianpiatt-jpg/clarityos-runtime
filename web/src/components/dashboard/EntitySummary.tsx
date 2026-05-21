// components/dashboard/EntitySummary.tsx
// Top entities + counts from the latest entity-graph snapshot.

import { Link } from "react-router-dom";
import type { V38DashboardSnapshot } from "../../lib/api";

export interface EntitySummaryProps {
  entityGraph: V38DashboardSnapshot["entity_graph"];
}

export default function EntitySummary({ entityGraph }: EntitySummaryProps) {
  const top = entityGraph.top_entities || [];
  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Entity graph</h2>
        <Link to="/founder" style={mutedLinkStyle}>open entity graph →</Link>
      </header>
      {entityGraph.available ? (
        <div>
          <div style={statsRowStyle}>
            <Stat label="Entities" value={String(entityGraph.entity_count)} />
            <Stat label="Edges" value={String(entityGraph.edge_count)} />
            <Stat
              label="Updated"
              value={entityGraph.updated_ts ? new Date(entityGraph.updated_ts * 1000).toISOString().slice(0, 10) : "—"}
            />
          </div>
          <h3 style={subHeader}>Top entities</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {top.map((e) => (
              <li key={e.name} style={rowStyle}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <strong style={{ fontSize: 12 }}>{e.name}</strong>
                  <span style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)", fontFamily: "var(--font-mono, monospace)" }}>
                    deg {e.degree} · ep {e.ep_mean.toFixed(3)}
                  </span>
                </div>
                {e.top_domains.length > 0 && (
                  <div style={{ marginTop: 2, fontSize: 10, color: "var(--os-text-secondary, #A0A0A0)" }}>
                    {e.top_domains.join(" · ")}
                  </div>
                )}
              </li>
            ))}
            {top.length === 0 && (
              <li style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>
                No entities yet
              </li>
            )}
          </ul>
        </div>
      ) : (
        <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>
          No graph snapshot yet
        </div>
      )}
    </section>
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
const statsRowStyle: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 8,
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 8, marginBottom: 4, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const rowStyle: React.CSSProperties = {
  padding: "5px 6px",
  marginBottom: 3,
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  background: "var(--os-deep, #0a0a0a)",
};
const mutedLinkStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-focus, #00F0FF)", textDecoration: "none",
};
