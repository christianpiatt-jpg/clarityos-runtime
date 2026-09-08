// components/settings/KernelFacts.tsx
//
// #180b (3) -- /me's kernel block, capability list and vault flag on a
// MEMBER surface. The order named "the cockpit welcome card"; that card
// (components/cockpit/OperatorWelcome.tsx) mounts only in the ADMIN cockpit
// since #145, so for a member the nineteen /me keys still arrived and died.
// This block sits in /membership's account fold (#141), where the member's
// own facts live. A value as it came; the dash when the server sent none;
// a boolean as its word. Every row carries its wire key in a title.

import { Fragment, useSyncExternalStore } from "react";
import { getAuthSnapshot, subscribeAuth } from "../../lib/auth";

const DASH = "—";

function val(v: unknown): string {
  if (v === null || v === undefined) return DASH;
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : DASH;
  return String(v) || DASH;
}
function fmtMs(ms: unknown): string {
  if (typeof ms !== "number" || !Number.isFinite(ms) || ms <= 0) return DASH;
  try { return new Date(ms).toISOString().replace("T", " ").slice(0, 16) + "Z"; }
  catch { return DASH; }
}
function fmtS(s: unknown): string {
  if (typeof s !== "number" || !Number.isFinite(s) || s <= 0) return DASH;
  try { return new Date(s * 1000).toISOString().slice(0, 10); }
  catch { return DASH; }
}

export default function KernelFacts() {
  const auth = useSyncExternalStore(subscribeAuth, getAuthSnapshot, getAuthSnapshot);
  const p = auth.profile;
  const k = p?.intelligence_kernel ?? null;
  const caps = p?.capabilities ?? [];
  const rows: Array<[string, unknown, string]> = [
    ["Last model", k?.last_model_used, "intelligence_kernel.last_model_used"],
    ["Kernel", k?.version, "intelligence_kernel.version"],
    ["Threads", k?.thread_count, "intelligence_kernel.thread_count"],
    ["Notes", k?.notes_count, "intelligence_kernel.notes_count"],
    ["Embeddings", k?.embeddings_count, "intelligence_kernel.embeddings_count"],
    ["Vault keys", k?.vault_keys, "intelligence_kernel.vault_keys"],
    ["Signal mode", k?.external_signal_mode ?? p?.external_signal_mode, "intelligence_kernel.external_signal_mode · external_signal_mode"],
    ["ESO source", k?.eso_source ?? p?.eso_source, "intelligence_kernel.eso_source · eso_source"],
    ["Preferred model", k?.preferred_model, "intelligence_kernel.preferred_model"],
    ["Local model uses", k?.local_model_usage_count, "intelligence_kernel.local_model_usage_count"],
  ];
  return (
    <section style={sectionStyle} data-testid="kernel-facts">
      <h2 style={h2Style} title="intelligence_kernel">Runtime</h2>
      <div style={gridStyle}>
        {rows.map(([label, v, path]) => (
          <Fragment key={path}>
            <span style={kStyle} title={path}>{label}</span>
            <span data-testid={`kf-${path.split(" ")[0].split(".").pop()}`}>{val(v)}</span>
          </Fragment>
        ))}
        <span style={kStyle} title="intelligence_kernel.last_thread_updated_at">Last thread</span>
        <span data-testid="kf-last_thread_updated_at">{fmtMs(k?.last_thread_updated_at)}</span>
        <span style={kStyle} title="vault_ready">Vault</span>
        <span data-testid="kf-vault_ready">{p?.vault_ready === true ? "ready" : p?.vault_ready === false ? "not ready" : DASH}</span>
        <span style={kStyle} title="tier">Tier</span>
        <span data-testid="kf-tier">{p?.tier ?? DASH}</span>
        <span style={kStyle} title="billing_expires_at">Renewal</span>
        <span data-testid="kf-billing_expires_at">{fmtS(p?.billing_expires_at)}</span>
      </div>
      {/* capabilities[] as the server lists them; every route in the 09-04
          list exists in app.py (checked by decorator). id + route in the
          title, the label as the text, one line. */}
      <p style={pStyle} title="capabilities[]" data-testid="kf-capabilities">
        {caps.length === 0 ? DASH : caps.map((c, i) => (
          <span key={c.id} title={`capabilities[].id ${c.id} · capabilities[].label · capabilities[].route ${c.route}`}>
            {i > 0 ? " · " : ""}{c.label}
          </span>
        ))}
      </p>
    </section>
  );
}

const sectionStyle: React.CSSProperties = {
  border: "1px solid #ddd",
  borderRadius: 6,
  padding: 16,
  background: "#fff",
  marginBottom: 16,
};
const h2Style: React.CSSProperties = { margin: "0 0 8px 0", fontSize: 16 };
const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "auto 1fr",
  gap: "4px 16px",
  fontSize: 13,
};
const kStyle: React.CSSProperties = { color: "#666" };
const pStyle: React.CSSProperties = { color: "#555", fontSize: 12, marginTop: 10, marginBottom: 0, lineHeight: 1.6 };
