// components/cockpit/ElinsQuicklook.tsx
// v43 — small inline panel that surfaces the active ESO mode + last
// macro-run timestamp + EP mean. The cockpit header CTA links to
// /dashboard for the full surface; this card gives the cockpit a
// glance-able status before the user clicks through.

import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  elinsDashboard,
  meBilling,            // not strictly needed; kept consistent
  type V38DashboardSnapshot,
} from "../../lib/api";
import { me as fetchMe } from "../../lib/api";

export default function ElinsQuicklook() {
  const [snap, setSnap] = useState<V38DashboardSnapshot | null>(null);
  const [esoMode, setEsoMode] = useState<"cloud_only" | "cloud_perplexity" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<boolean>(false);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const [d, m] = await Promise.all([
        elinsDashboard().catch(() => null),
        fetchMe().catch(() => null),
      ]);
      if (d) setSnap(d.snapshot);
      const meAny = m as unknown as { external_signal_mode?: "cloud_only" | "cloud_perplexity" } | null;
      if (meAny?.external_signal_mode) setEsoMode(meAny.external_signal_mode);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
    // ``meBilling`` import is unused at runtime; ensure the bundler
    // tree-shakes it cleanly without a TS unused-symbol warning.
    void meBilling;
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (busy && !snap) {
    return <Skeleton />;
  }

  const lastTs = snap?.macro?.last_run_ts ?? null;
  const ep = snap?.macro?.ep_mean ?? snap?.global?.ep_mean ?? null;

  return (
    <div style={cardStyle}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <strong style={{ fontSize: 13 }}>ELINS</strong>
        <Link to="/dashboard" style={ctaStyle} title="Open the unified ELINS dashboard">
          Open dashboard →
        </Link>
      </div>
      {error && <div style={errorStyle}>{error}</div>}

      <div style={{ marginTop: 6, fontSize: 12, color: "#444" }}>
        {lastTs ? (
          <>
            <span style={{ color: "#888" }}>last macro run </span>
            <code>{new Date(lastTs * 1000).toISOString().slice(0, 19).replace("T", " ")}</code>
            {ep !== null && (
              <>
                <span style={{ color: "#888" }}> · ep </span>
                <code>{ep.toFixed(3)}</code>
              </>
            )}
          </>
        ) : (
          <span style={{ color: "#888", fontStyle: "italic" }}>
            No macro runs yet — kick one off from the founder console or wait for the next scheduled tick.
          </span>
        )}
      </div>

      {esoMode && (
        <div style={{ marginTop: 6 }}>
          <EsoPill mode={esoMode} />
        </div>
      )}
    </div>
  );
}

function EsoPill({ mode }: { mode: "cloud_only" | "cloud_perplexity" }) {
  const label = mode === "cloud_perplexity" ? "ESO perplexity" : "ESO off";
  const bg = mode === "cloud_perplexity" ? "#ecfdf5" : "#f3f4f6";
  const fg = mode === "cloud_perplexity" ? "#15803d" : "#6b7280";
  return (
    <span style={{
      display: "inline-block",
      padding: "2px 8px",
      borderRadius: 999,
      fontSize: 11, fontWeight: 600, letterSpacing: 0.4,
      background: bg, color: fg,
      border: `1px solid ${fg}`,
    }}>{label}</span>
  );
}

function Skeleton() {
  return (
    <div style={cardStyle} aria-label="Loading ELINS quicklook">
      <div style={{ height: 12, width: "30%", background: "#eee", borderRadius: 3, marginBottom: 6 }} />
      <div style={{ height: 10, width: "70%", background: "#eee", borderRadius: 3 }} />
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 6,
  padding: 8,
  background: "#fafafa",
  marginBottom: 12,
};
const ctaStyle: React.CSSProperties = {
  fontSize: 12, fontWeight: 600, color: "#2563eb", textDecoration: "none",
};
const errorStyle: React.CSSProperties = {
  marginTop: 6,
  padding: 6,
  background: "#fee",
  border: "1px solid #f99",
  borderRadius: 4,
  fontSize: 11,
};
