// components/dashboard/RegionalGrid.tsx
// 6-tile grid of regional dashboard sections.

import type { V38DashboardSection } from "../../lib/api";
import { Link } from "react-router-dom";

const REGION_ORDER: string[] = ["US", "EU", "MEA", "APAC", "Markets", "Tech"];

export interface RegionalGridProps {
  regional: Record<string, V38DashboardSection>;
}

export default function RegionalGrid({ regional }: RegionalGridProps) {
  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Regional</h2>
        <Link to="/founder" style={mutedLinkStyle}>open regional surface →</Link>
      </header>
      <div style={gridStyle}>
        {REGION_ORDER.map((region) => {
          const s = regional[region];
          if (!s) return null;
          return (
            <div key={region} style={cardStyle}>
              <div style={cardHeaderStyle}>
                <strong style={{ fontSize: 13 }}>{region}</strong>
                {s.has_eso ? (
                  <span style={esoOnStyle}>ESO</span>
                ) : null}
              </div>
              {s.available ? (
                <div>
                  <Row label="EP mean" value={s.ep_mean.toFixed(3)} />
                  <Row label="Top primitive" value={s.top_primitives[0]?.key || "—"} />
                  {s.forecast.length > 0 && (
                    <MiniForecast values={s.forecast} />
                  )}
                </div>
              ) : (
                <div style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)", marginTop: 6 }}>
                  No runs yet
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MiniForecast({ values }: { values: number[] }) {
  const ymax = Math.max(0.001, ...values.map(Math.abs));
  return (
    <div style={{ display: "flex", alignItems: "flex-end", gap: 2, marginTop: 6, height: 24 }}>
      {values.map((v, i) => (
        <div
          key={i}
          style={{
            flex: 1,
            height: Math.max(2, Math.round((Math.abs(v) / ymax) * 24)),
            background: v < 0 ? "var(--os-boundary, #E02020)" : "var(--os-focus, #00F0FF)",
            borderRadius: 2,
          }}
        />
      ))}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "1px 0", fontSize: 11 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{value}</span>
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
const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
  gap: 8,
};
const cardStyle: React.CSSProperties = {
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  padding: 8,
  background: "var(--os-deep, #0a0a0a)",
};
const cardHeaderStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "center",
};
const esoOnStyle: React.CSSProperties = {
  fontSize: 9, padding: "1px 6px", borderRadius: "var(--radius-pill, 999px)",
  border: "1px solid var(--os-focus, #00F0FF)",
  color: "var(--os-focus, #00F0FF)",
};
const mutedLinkStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-focus, #00F0FF)", textDecoration: "none",
};
