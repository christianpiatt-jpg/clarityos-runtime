// components/dashboard/ContinuityCard.tsx
// v39 — small continuity slice on the main /dashboard. Surfaces the
// last topics + inferred preferences without exposing raw scenarios.

import { Link } from "react-router-dom";
import type { V38DashboardSnapshot } from "../../lib/api";

export interface ContinuityCardProps {
  continuity: V38DashboardSnapshot["continuity"];
}

export default function ContinuityCard({ continuity }: ContinuityCardProps) {
  const c = continuity;
  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Continuity</h2>
        <Link to="/founder" style={mutedLinkStyle}>operator profile →</Link>
      </header>
      {!c || c.history_count === 0 ? (
        <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>
          No prior interactions yet.
        </div>
      ) : (
        <div>
          <h3 style={subHeader}>Last topics</h3>
          {c.last_topics.length === 0 ? (
            <div style={emptyStyle}>—</div>
          ) : (
            <ul style={{ paddingLeft: 16, margin: 0, fontSize: 11 }}>
              {c.last_topics.map((t) => <li key={t}>{t}</li>)}
            </ul>
          )}
          <h3 style={subHeader}>Preferred regions</h3>
          {c.preferred_regions.length === 0 ? (
            <div style={emptyStyle}>—</div>
          ) : (
            <PrefRow rows={c.preferred_regions} accent="#fbbf24" />
          )}
          <h3 style={subHeader}>Preferred domains</h3>
          {c.preferred_domains.length === 0 ? (
            <div style={emptyStyle}>—</div>
          ) : (
            <PrefRow rows={c.preferred_domains} accent="var(--os-focus, #00F0FF)" />
          )}
          <div style={{ marginTop: 8, fontSize: 10, color: "var(--os-text-tertiary, #585858)" }}>
            ESO {c.external_signal_mode === "cloud_perplexity" ? "on" : "off"} · {c.history_count} ELINS · {c.g_count} #G
          </div>
        </div>
      )}
    </section>
  );
}

function PrefRow({ rows, accent }: {
  rows: Array<{ name: string; weight: number }>; accent: string;
}) {
  const max = Math.max(0.001, ...rows.map((r) => r.weight));
  return (
    <div>
      {rows.slice(0, 4).map((r) => (
        <div key={r.name} style={{ marginBottom: 3 }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11 }}>
            <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{r.name}</span>
            <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{r.weight.toFixed(2)}</span>
          </div>
          <div style={{ height: 4, background: "var(--os-deep, #0a0a0a)", borderRadius: 2 }}>
            <div
              style={{
                width: `${Math.min(100, (r.weight / max) * 100)}%`,
                height: "100%", background: accent, borderRadius: 2,
              }}
            />
          </div>
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
};
const headerStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8,
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 8, marginBottom: 4, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const emptyStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)", fontStyle: "italic",
};
const mutedLinkStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-focus, #00F0FF)", textDecoration: "none",
};
