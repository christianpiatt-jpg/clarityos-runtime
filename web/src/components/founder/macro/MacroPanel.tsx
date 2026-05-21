// components/founder/macro/MacroPanel.tsx
// Composite — runs list (left) + run detail (middle) + scheduler config (right).

import { useCallback, useState } from "react";
import MacroRunsList from "./MacroRunsList";
import MacroRunDetail from "./MacroRunDetail";
import MacroSchedulerConfig from "./MacroSchedulerConfig";

export default function MacroPanel() {
  const [selected, setSelected] = useState<string | null>(null);
  const [refreshNonce, setRefreshNonce] = useState<number>(0);

  const onSelect = useCallback((run_id: string) => {
    setSelected(run_id);
    setRefreshNonce((n) => n + 1);
  }, []);

  return (
    <section style={panelStyle}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Macro-ELINS automation</h2>
        <span style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>v36 scheduler</span>
      </header>

      <div style={gridStyle}>
        <div style={cardStyle}>
          <MacroRunsList selectedId={selected} onSelect={onSelect} refreshNonce={refreshNonce} />
        </div>
        <div style={cardStyle}>
          <MacroRunDetail runId={selected} />
        </div>
        <div style={cardStyle}>
          <MacroSchedulerConfig />
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
  gridTemplateColumns: "minmax(220px, 1fr) minmax(280px, 1.5fr) minmax(220px, 1fr)",
  gap: 12,
  alignItems: "start",
};

const cardStyle: React.CSSProperties = {
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  padding: 10,
  background: "var(--os-deep, #0a0a0a)",
};
