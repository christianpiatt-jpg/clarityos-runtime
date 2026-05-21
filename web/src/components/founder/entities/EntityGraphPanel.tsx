// components/founder/entities/EntityGraphPanel.tsx
// Composite — search + neighbours + timeseries for the selected entity.

import { useState } from "react";
import EntitySearch from "./EntitySearch";
import EntityNeighborsPanel from "./EntityNeighborsPanel";
import EntityTimeseriesPanel from "./EntityTimeseriesPanel";

export default function EntityGraphPanel() {
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <section style={panelStyle}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Entity graph</h2>
        <span style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>
          v37 cross-cluster network
        </span>
      </header>

      <div style={gridStyle}>
        <div style={cardStyle}>
          <EntitySearch selected={selected} onSelect={setSelected} />
        </div>
        <div style={cardStyle}>
          <EntityNeighborsPanel entity={selected} onSelect={setSelected} />
        </div>
        <div style={cardStyle}>
          <EntityTimeseriesPanel entity={selected} />
        </div>
      </div>
    </section>
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

const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "minmax(220px, 1fr) minmax(260px, 1fr) minmax(280px, 1.2fr)",
  gap: 12,
  alignItems: "start",
};

const cardStyle: React.CSSProperties = {
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  padding: 10,
  background: "var(--os-deep, #0a0a0a)",
  minHeight: 200,
};
