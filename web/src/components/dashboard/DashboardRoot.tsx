// components/dashboard/DashboardRoot.tsx
// Composite — single-screen ELINS intelligence surface.

import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { elinsDashboard, type V38DashboardSnapshot } from "../../lib/api";
import { useIsController } from "../RequireAdmin";
import GlobalPanel from "./GlobalPanel";
import RegionalGrid from "./RegionalGrid";
import MacroSummary from "./MacroSummary";
import EntitySummary from "./EntitySummary";
import ContinuityCard from "./ContinuityCard";

export default function DashboardRoot() {
  const [snapshot, setSnapshot] = useState<V38DashboardSnapshot | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  // #145 -- the page is the WINDOW every member may look through; the
  // doors are the admin's. #308 -- the four card links are in-page anchors
  // now (/dashboard#regional etc.), no longer doors into /founder; the
  // footer keeps the one /founder door.
  const admin = useIsController();

  // #308 -- a react-router Link rewrites the URL and never scrolls to a
  // fragment, and on a cold load the cards render after the fetch, so the
  // fragment has nothing to land on: this walks to the card once the
  // snapshot has rendered (the ids are on the wrappers below) -- ONCE per
  // navigation (location.key), so a Refresh, which replaces the snapshot,
  // does not drag the page back to the card.
  const { hash, key: navKey } = useLocation();
  const walked = useRef<string | null>(null);
  useEffect(() => {
    if (!hash || !snapshot || walked.current === navKey) return;
    const el = document.getElementById(hash.slice(1));
    if (!el) return;
    el.scrollIntoView({ block: "start" });
    walked.current = navKey;
  }, [hash, navKey, snapshot]);

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
            <span style={metaStyle} data-testid="dash-provenance">
              {snapshot.date} · {new Date(snapshot.ts * 1000).toISOString().slice(11, 19)}Z
              {/* #180b (7) -- the scenario the global read was built on and the
                  snapshot version: provenance, beside the stamp. */}
              {" · "}
              <span title="snapshot.global.scenario_id">scenario {snapshot.global?.scenario_id ?? "—"}</span>
              {" · "}
              <span title="snapshot.version">{snapshot.version || "—"}</span>
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
          <div id="global" style={{ gridColumn: "1 / span 2" }}>
            {/* #308 -- the ESO badge reads the flag the macro card reads */}
            <GlobalPanel section={snapshot.global} esoMode={snapshot.macro?.external_signal_mode ?? null} />
          </div>
          <div id="regional" style={{ gridColumn: "1 / span 2" }}>
            <RegionalGrid regional={snapshot.regional} />
          </div>
          <div id="macro">
            <MacroSummary macro={snapshot.macro} />
          </div>
          <div id="entities">
            <EntitySummary entityGraph={snapshot.entity_graph} />
          </div>
          <div id="continuity" style={{ gridColumn: "1 / span 2" }}>
            <ContinuityCard continuity={snapshot.continuity} />
          </div>
        </div>
      )}

      {admin ? (
        <footer style={footerStyle}>
          <Link to="/elins" style={footerLinkStyle}>Cockpit ELINS feed →</Link>
          <Link to="/founder" style={footerLinkStyle}>Founder console →</Link>
        </footer>
      ) : null}
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
        border: "1px solid var(--os-line-strong, rgba(20, 24, 28, 0.12))",
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
  border: "1px solid var(--os-line-strong, rgba(20, 24, 28, 0.12))",
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
