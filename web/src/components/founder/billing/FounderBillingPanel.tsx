// components/founder/billing/FounderBillingPanel.tsx
// v42 — Stripe mode badge + recent events + webhook health.

import { useCallback, useEffect, useState } from "react";
import {
  founderBillingStatus,
  type V42FounderBillingStatus,
} from "../../../lib/api";

export default function FounderBillingPanel() {
  const [status, setStatus] = useState<V42FounderBillingStatus | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy(true); setError(null);
    try {
      const r = await founderBillingStatus();
      setStatus(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Billing</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={busy}
          style={refreshStyle}
        >{busy ? "…" : "Refresh"}</button>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {status && (
        <div>
          <div style={modeRowStyle}>
            <ModeBadge mode={status.stripe.mode} live={status.live_mode} />
            <span style={runtimeStyle}>runtime {status.runtime_billing_mode}</span>
          </div>

          <div style={{ marginTop: 8 }}>
            <Row label="Secret key" value={status.stripe.has_secret ? "configured" : "missing"} ok={status.stripe.has_secret} />
            <Row label="Webhook secret" value={status.stripe.has_webhook_secret ? "configured" : "missing"} ok={status.stripe.has_webhook_secret} />
            <Row label="Last webhook" value={fmtTs(status.last_event_ts)} />
            <Row label="Billing enabled" value={status.stripe.billing_enabled ? "yes" : "no"} ok={status.stripe.billing_enabled} />
          </div>

          {!status.stripe.billing_enabled && (
            <div style={disabledNoticeStyle}>
              Billing is disabled. New checkout sessions will be rejected until
              <code> CLARITYOS_STRIPE_SECRET_KEY </code> + <code> CLARITYOS_STRIPE_WEBHOOK_SECRET </code>
              are set.
            </div>
          )}

          <h3 style={subHeader}>Recent events ({status.recent_events.length})</h3>
          {status.recent_events.length === 0 ? (
            <div style={emptyStyle}>No webhook traffic yet.</div>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {status.recent_events.slice(0, 12).map((e, i) => (
                <li key={`${e.event_id || i}-${e.ts}`} style={eventStyle}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong style={{ fontSize: 12 }}>{e.event_type}</strong>
                    <span style={tsStyle}>{fmtTs(e.ts)}</span>
                  </div>
                  <div style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)", fontFamily: "var(--font-mono, monospace)" }}>
                    mode={e.mode} {e.user_id ? `· user=${e.user_id}` : ""} {e.event_id ? `· evt=${e.event_id.slice(0, 16)}` : ""}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

function ModeBadge({ mode }: { mode: string; live: boolean }) {
  let bg = "var(--os-text-tertiary, #585858)";
  let label = "DISABLED";
  if (mode === "live") {
    bg = "#dc2626"; label = "LIVE";
  } else if (mode === "test") {
    bg = "#2563eb"; label = "TEST";
  }
  return (
    <span style={{
      display: "inline-block",
      padding: "3px 12px",
      background: bg,
      color: "#fff",
      fontSize: 11,
      fontWeight: 700,
      letterSpacing: 0.6,
      borderRadius: "var(--radius-pill, 999px)",
    }}>{label}</span>
  );
}

function fmtTs(ts: number | null): string {
  if (!ts || ts <= 0) return "—";
  return new Date(ts * 1000).toISOString().replace("T", " ").slice(0, 19);
}

function Row({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  const color = ok === true
    ? "var(--os-ok, #4ade80)"
    : ok === false
    ? "var(--os-boundary, #E02020)"
    : "var(--os-text-primary, #fff)";
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", fontSize: 12 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      <span style={{ color, fontFamily: "var(--font-mono, monospace)" }}>{value}</span>
    </div>
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
const headerStyle: React.CSSProperties = {
  display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8,
};
const refreshStyle: React.CSSProperties = {
  fontSize: 11, padding: "3px 10px",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  background: "var(--os-surface, #111)",
  color: "var(--os-text-primary, #fff)",
  borderRadius: "var(--radius-pill, 999px)",
};
const modeRowStyle: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: 8,
};
const runtimeStyle: React.CSSProperties = {
  fontSize: 10, color: "var(--os-text-tertiary, #585858)",
  fontFamily: "var(--font-mono, monospace)",
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 12, marginBottom: 4, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const eventStyle: React.CSSProperties = {
  padding: 6, marginBottom: 4,
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  background: "var(--os-deep, #0a0a0a)",
};
const tsStyle: React.CSSProperties = {
  fontSize: 10, color: "var(--os-text-tertiary, #585858)",
  fontFamily: "var(--font-mono, monospace)",
};
const errorStyle: React.CSSProperties = {
  padding: 6, marginBottom: 8,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
const emptyStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)", fontStyle: "italic",
};
const disabledNoticeStyle: React.CSSProperties = {
  marginTop: 10, padding: 8,
  background: "rgba(224, 32, 32, 0.08)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "var(--os-text-primary, #fff)",
};
