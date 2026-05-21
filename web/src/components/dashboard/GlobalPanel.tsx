// components/dashboard/GlobalPanel.tsx
// Global section of the v38 dashboard: EP mean, top domains,
// top primitives, multi-envelope forecast spark, ESO badge.

import type { V38DashboardSection } from "../../lib/api";

const PRIMITIVE_COLORS: Record<string, string> = {
  pressure:      "#ff7b72",
  tension:       "#f59e0b",
  trust:         "#4ade80",
  drift:         "#a78bfa",
  contradiction: "#fb7185",
  alignment:     "#22d3ee",
};

export interface GlobalPanelProps {
  section: V38DashboardSection;
}

export default function GlobalPanel({ section }: GlobalPanelProps) {
  if (!section.available) {
    return (
      <section style={panelStyle}>
        <header style={headerStyle}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Global</h2>
          <span style={mutedStyle}>No global run yet</span>
        </header>
      </section>
    );
  }
  const sortedDomains = Object.entries(section.domains || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5);
  const ymax = Math.max(0.001, ...sortedDomains.map(([, v]) => v));
  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Global</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={mutedStyle}>{section.day || "today"}</span>
          {section.has_eso ? (
            <span style={esoOnStyle}>ESO</span>
          ) : (
            <span style={esoOffStyle}>ESO off</span>
          )}
        </div>
      </header>

      <div style={statsRowStyle}>
        <Stat label="EP mean" value={section.ep_mean.toFixed(3)} />
        <Stat label="Top primitive" value={section.top_primitives[0]?.key || "—"} />
        <Stat label="Forecast horizon" value={`${section.forecast.length} days`} />
      </div>

      <h3 style={subHeader}>Top primitives</h3>
      <div>
        {section.top_primitives.map((p) => (
          <div key={p.key} style={{ marginBottom: 4 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
              <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{p.key}</span>
              <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{p.intensity.toFixed(3)}</span>
            </div>
            <div style={{ height: 6, background: "var(--os-deep, #0a0a0a)", borderRadius: 3 }}>
              <div
                style={{
                  width: `${Math.min(100, p.intensity * 100)}%`,
                  height: "100%",
                  background: PRIMITIVE_COLORS[p.key] || "#ccc",
                  borderRadius: 3,
                }}
              />
            </div>
          </div>
        ))}
      </div>

      {sortedDomains.length > 0 && (
        <>
          <h3 style={subHeader}>Top domains</h3>
          <div>
            {sortedDomains.map(([k, v]) => (
              <div key={k} style={{ marginBottom: 3 }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
                  <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{k}</span>
                  <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{v.toFixed(2)}</span>
                </div>
                <div style={{ height: 4, background: "var(--os-deep, #0a0a0a)", borderRadius: 2 }}>
                  <div
                    style={{
                      width: `${Math.min(100, (v / ymax) * 100)}%`,
                      height: "100%",
                      background: "var(--os-focus, #00F0FF)",
                      borderRadius: 2,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {section.forecast.length > 0 && (
        <>
          <h3 style={subHeader}>Multi-envelope forecast</h3>
          <ForecastSpark values={section.forecast} />
        </>
      )}
    </section>
  );
}

function ForecastSpark({ values }: { values: number[] }) {
  const w = 360, h = 80, padX = 16, padY = 16;
  const innerW = w - padX * 2;
  const innerH = h - padY * 2;
  const ymax = Math.max(0.001, ...values.map(Math.abs));
  const xAt = (i: number) =>
    padX + (innerW * i) / Math.max(1, values.length - 1);
  const yAt = (v: number) =>
    padY + innerH - (Math.abs(v) / ymax) * innerH;
  const path = values.map((v, i) =>
    `${i === 0 ? "M" : "L"} ${xAt(i)} ${yAt(v)}`,
  ).join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="Global multi-envelope forecast"
      style={{ width: "100%", height: "auto", display: "block" }}
    >
      <rect x={0} y={0} width={w} height={h} fill="var(--os-deep, #0a0a0a)" />
      <path d={path} fill="none" stroke="var(--os-focus, #00F0FF)" strokeWidth={2} />
      {values.map((v, i) => (
        <circle key={i} cx={xAt(i)} cy={yAt(v)} r={2.5} fill="var(--os-focus, #00F0FF)" />
      ))}
      {values.map((_, i) => (
        <text
          key={`xt-${i}`} x={xAt(i)} y={h - 2} textAnchor="middle"
          fontSize="9" fill="var(--os-text-tertiary, #585858)"
          fontFamily="var(--font-mono, monospace)"
        >
          D+{i}
        </text>
      ))}
    </svg>
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
  display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginBottom: 10,
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 10, marginBottom: 4, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const mutedStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)",
  fontFamily: "var(--font-mono, monospace)",
};
const esoOnStyle: React.CSSProperties = {
  fontSize: 10, padding: "2px 8px", borderRadius: "var(--radius-pill, 999px)",
  border: "1px solid var(--os-focus, #00F0FF)",
  background: "rgba(0, 240, 255, 0.1)", color: "var(--os-focus, #00F0FF)",
};
const esoOffStyle: React.CSSProperties = {
  fontSize: 10, padding: "2px 8px", borderRadius: "var(--radius-pill, 999px)",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  color: "var(--os-text-tertiary, #585858)",
};
