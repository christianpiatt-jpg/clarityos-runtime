// components/dashboard/DashboardRoot.tsx
// Composite — single-screen ELINS intelligence surface.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { elinsDashboard, type V38DashboardSnapshot } from "../../lib/api";
import GlobalPanel from "./GlobalPanel";
import RegionalGrid from "./RegionalGrid";
import MacroSummary from "./MacroSummary";
import EntitySummary from "./EntitySummary";
import ContinuityCard from "./ContinuityCard";

export default function DashboardRoot() {
  const [snapshot, setSnapshot] = useState<V38DashboardSnapshot | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await elinsDashboard();
      setSnapshot(r.snapshot);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div style={containerStyle}>
      <header style={pageHeaderStyle}>
        <div>
          <h1 style={{ margin: 0, fontSize: 22 }}>ELINS dashboard</h1>
          <p style={{ margin: "4px 0 0 0", color: "var(--os-text-secondary, #A0A0A0)", fontSize: 13 }}>
            Global · Regional · Macro · Entity graph
          </p>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {snapshot && (
            <span style={metaStyle}>
              {snapshot.date} · {new Date(snapshot.ts * 1000).toISOString().slice(11, 19)}Z
            </span>
          )}
          <button type="button" onClick={() => void load()} disabled={busy} style={refreshStyle}>
            {busy ? "…" : "Refresh"}
          </button>
        </div>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {!snapshot && busy && <DashboardSkeleton />}

      {snapshot && (
        <div style={layoutStyle}>
          <div style={{ gridColumn: "1 / span 2" }}>
            <GlobalPanel section={snapshot.global} />
          </div>
          <div style={{ gridColumn: "1 / span 2" }}>
            <RegionalGrid regional={snapshot.regional} />
          </div>
          <MacroSummary macro={snapshot.macro} />
          <EntitySummary entityGraph={snapshot.entity_graph} />
          <div style={{ gridColumn: "1 / span 2" }}>
            <ContinuityCard continuity={snapshot.continuity} />
          </div>
        </div>
      )}

      <footer style={footerStyle}>
        <Link to="/elins" style={footerLinkStyle}>Cockpit ELINS feed →</Link>
        <Link to="/founder" style={footerLinkStyle}>Founder console →</Link>
      </footer>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div style={layoutStyle} aria-label="Loading dashboard">
      <div style={{ gridColumn: "1 / span 2" }}>
        <SkeletonCard height={220} />
      </div>
      <div style={{ gridColumn: "1 / span 2" }}>
        <SkeletonCard height={180} />
      </div>
      <SkeletonCard height={140} />
      <SkeletonCard height={140} />
      <div style={{ gridColumn: "1 / span 2" }}>
        <SkeletonCard height={140} />
      </div>
    </div>
  );
}

function SkeletonCard({ height }: { height: number }) {
  return (
    <div
      style={{
        height, padding: 12,
        background: "var(--os-surface, #111)",
        border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
        borderRadius: "var(--radius-md, 8px)",
      }}
    >
      <div style={{ height: 12, width: "30%", background: "var(--os-deep, #0a0a0a)", borderRadius: 3, marginBottom: 10 }} />
      <div style={{ height: 8, width: "80%", background: "var(--os-deep, #0a0a0a)", borderRadius: 3, marginBottom: 6 }} />
      <div style={{ height: 8, width: "60%", background: "var(--os-deep, #0a0a0a)", borderRadius: 3, marginBottom: 6 }} />
      <div style={{ height: 8, width: "70%", background: "var(--os-deep, #0a0a0a)", borderRadius: 3 }} />
    </div>
  );
}

const containerStyle: React.CSSProperties = {
  maxWidth: 1080, margin: "0 auto",
};
const pageHeaderStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "flex-end",
  marginBottom: 16,
};
const layoutStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 12,
  alignItems: "start",
};
const metaStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)",
  fontFamily: "var(--font-mono, monospace)",
};
const refreshStyle: React.CSSProperties = {
  fontSize: 11, padding: "4px 12px",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
  borderRadius: "var(--radius-pill, 999px)",
  cursor: "pointer",
};
const errorStyle: React.CSSProperties = {
  padding: 8, marginBottom: 12,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
const footerStyle: React.CSSProperties = {
  marginTop: 24, display: "flex", gap: 16,
};
const footerLinkStyle: React.CSSProperties = {
  fontSize: 12, color: "var(--os-focus, #00F0FF)", textDecoration: "none",
};
