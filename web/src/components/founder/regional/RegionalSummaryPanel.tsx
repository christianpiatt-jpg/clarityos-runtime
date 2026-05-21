// components/founder/regional/RegionalSummaryPanel.tsx
// EP mean, top primitives, domain vector bars, ESO presence indicator.

import type { V35RegionalELINS } from "../../../lib/api";

const PRIMITIVE_COLORS: Record<string, string> = {
  pressure:      "#ff7b72",
  tension:       "#f59e0b",
  trust:         "#4ade80",
  drift:         "#a78bfa",
  contradiction: "#fb7185",
  alignment:     "#22d3ee",
};

export interface RegionalSummaryPanelProps {
  elins: V35RegionalELINS;
}

export default function RegionalSummaryPanel({ elins }: RegionalSummaryPanelProps) {
  const intensities = elins.primitives.intensities;
  const sorted = Object.entries(intensities).sort((a, b) => b[1] - a[1]);
  const ep = elins.ep_field_summary;
  const ext = elins.external_signals;
  const domainScores = elins.domain_mapping.scores || {};
  const sortedDomains = Object.entries(domainScores)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6);
  const maxDomain = Math.max(0.001, ...sortedDomains.map(([, v]) => v));
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <strong style={{ fontSize: 14 }}>{elins.region_code}</strong>
          <span style={{ marginLeft: 8, color: "var(--os-text-secondary, #A0A0A0)", fontSize: 12 }}>
            {elins.synthesis.signal} · trend {elins.synthesis.trend}
          </span>
        </div>
        <ESOBadge present={ext.present} mock={ext.mock} />
      </div>

      <Row label="EP intensity mean" value={ep.intensity_mean.toFixed(3)} />
      <Row label="Stress / Relief" value={`${ep.stress_total.toFixed(3)} / ${ep.relief_total.toFixed(3)}`} />
      <Row label="Top primitive" value={`${elins.synthesis.top_primitive} (${elins.synthesis.top_primitive_intensity.toFixed(3)})`} />
      <Row label="Domain" value={elins.synthesis.domain || "—"} />

      <h4 style={subHeader}>Top primitives</h4>
      {sorted.slice(0, 6).map(([k, v]) => (
        <div key={k} style={{ marginBottom: 4 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
            <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{k}</span>
            <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{v.toFixed(3)}</span>
          </div>
          <div style={{ height: 6, background: "var(--os-deep, #0a0a0a)", borderRadius: 3 }}>
            <div
              style={{
                width: `${Math.min(100, v * 100)}%`,
                height: "100%",
                background: PRIMITIVE_COLORS[k] || "#ccc",
                borderRadius: 3,
              }}
            />
          </div>
        </div>
      ))}

      <h4 style={subHeader}>Domain vector</h4>
      {sortedDomains.length === 0 ? (
        <div style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>No domain scores</div>
      ) : (
        sortedDomains.map(([k, v]) => (
          <div key={k} style={{ marginBottom: 3 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
              <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{k}</span>
              <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{v.toFixed(2)}</span>
            </div>
            <div style={{ height: 4, background: "var(--os-deep, #0a0a0a)", borderRadius: 2 }}>
              <div
                style={{
                  width: `${Math.min(100, (v / maxDomain) * 100)}%`,
                  height: "100%",
                  background: "var(--os-focus, #00F0FF)",
                  borderRadius: 2,
                }}
              />
            </div>
          </div>
        ))
      )}

      {ext.present && ext.anchors.length > 0 && (
        <div style={{ marginTop: 10 }}>
          <h4 style={subHeader}>External anchors (ESO)</h4>
          <ul style={{ paddingLeft: 16, margin: 0, fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)" }}>
            {ext.anchors.map((a) => <li key={a}>{a}</li>)}
          </ul>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, padding: "2px 0" }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{value}</span>
    </div>
  );
}

function ESOBadge({ present, mock }: { present: boolean; mock?: boolean }) {
  if (!present) {
    return (
      <span style={{
        fontSize: 10, padding: "2px 8px", borderRadius: "var(--radius-pill, 999px)",
        border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
        color: "var(--os-text-tertiary, #585858)",
      }}>ESO off</span>
    );
  }
  return (
    <span style={{
      fontSize: 10, padding: "2px 8px", borderRadius: "var(--radius-pill, 999px)",
      border: "1px solid var(--os-focus, #00F0FF)",
      background: "rgba(0, 240, 255, 0.1)",
      color: "var(--os-focus, #00F0FF)",
    }}>{mock ? "ESO (mock)" : "ESO live"}</span>
  );
}

const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 10, marginBottom: 4, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
