// components/settings/ModelPreferences.tsx
// v44 — user-facing model preference picker. Reads /me to get the
// router status + the user's current preferred_model + last_model_used,
// writes via /me/operator_state/model.

import { useCallback, useEffect, useState } from "react";
import {
  me as fetchMe,
  meOperatorStateModel,
  V44_MODEL_IDS,
  type V44ModelId,
  type V44RouterStatus,
} from "../../lib/api";

interface KernelBlock {
  preferred_model?: V44ModelId | null;
  last_model_used?: V44ModelId | null;
}

export default function ModelPreferences() {
  const [pref, setPref] = useState<V44ModelId | "">("");
  const [last, setLast] = useState<V44ModelId | null>(null);
  const [router, setRouter] = useState<V44RouterStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const meResp = await fetchMe();
      const ik = (meResp as unknown as { intelligence_kernel?: KernelBlock }).intelligence_kernel;
      setPref((ik?.preferred_model as V44ModelId | null) ?? "");
      setLast((ik?.last_model_used as V44ModelId | null) ?? null);
      // The /me capability list contains the router status indirectly;
      // for the v44 UI we use the founder-status endpoint when available
      // but fall back to the static list for non-founder users.
      const routerStatus = (meResp as unknown as { intelligence_kernel?: { models?: V44RouterStatus } });
      setRouter(routerStatus.intelligence_kernel?.models ?? null);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const apply = useCallback(async (next: V44ModelId | "") => {
    setBusy("save"); setError(null);
    try {
      const value = next === "" || next === "auto" ? null : next;
      await meOperatorStateModel(value as V44ModelId | null);
      setPref(next);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  return (
    <div style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Model preferences</h2>
        <span style={mutedStyle}>v44 router</span>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      <p style={helpStyle}>
        Pick the model the kernel routes your runs through. <code>auto</code>
        defers to the system default (usually a deterministic Anthropic
        model for analysis tasks and a fast model for #c).
      </p>

      <label style={labelStyle}>Preferred model</label>
      <select
        value={pref}
        onChange={(e) => void apply(e.target.value as V44ModelId | "")}
        disabled={busy !== null}
        style={selectStyle}
      >
        <option value="">(use system default)</option>
        {V44_MODEL_IDS.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>

      <div style={statRowStyle}>
        <Stat label="Current preference" value={pref || "system default"} />
        <Stat label="Last model used" value={last || "—"} />
      </div>

      {router && (
        <div style={{ marginTop: 12 }}>
          <h3 style={subHeader}>Provider status</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: 6 }}>
            {Object.entries(router.providers).map(([provider, info]) => (
              <ProviderPill key={provider} provider={provider} configured={info.configured} />
            ))}
          </div>
          {router.founder_default_model && (
            <p style={{ ...mutedStyle, marginTop: 8 }}>
              Founder default in effect:&nbsp;
              <code>{router.founder_default_model}</code>
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={statLabelStyle}>{label}</div>
      <code style={statValueStyle}>{value}</code>
    </div>
  );
}

function ProviderPill({ provider, configured }: { provider: string; configured: boolean }) {
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: "4px 8px",
      border: `1px solid ${configured ? "var(--os-ok, #4ade80)" : "var(--os-line-strong, rgba(255,255,255,0.16))"}`,
      borderRadius: "var(--radius-pill, 999px)",
      background: "var(--os-deep, #0a0a0a)",
      color: configured ? "var(--os-text-primary, #fff)" : "var(--os-text-tertiary, #585858)",
      fontSize: 11,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: 3,
        background: configured ? "var(--os-ok, #4ade80)" : "var(--os-text-tertiary, #585858)",
      }} />
      {provider}
    </span>
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
const helpStyle: React.CSSProperties = {
  fontSize: 12, color: "var(--os-text-secondary, #A0A0A0)", margin: "0 0 8px 0",
};
const labelStyle: React.CSSProperties = {
  display: "block", fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)",
  textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 4,
};
const selectStyle: React.CSSProperties = {
  width: "100%", padding: "6px 8px",
  background: "var(--os-deep, #0a0a0a)",
  color: "var(--os-text-primary, #fff)",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 13,
};
const statRowStyle: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 10,
};
const statLabelStyle: React.CSSProperties = {
  fontSize: 10, color: "var(--os-text-tertiary, #585858)",
  textTransform: "uppercase", letterSpacing: 0.5,
};
const statValueStyle: React.CSSProperties = {
  fontSize: 12, color: "var(--os-text-primary, #fff)",
  fontFamily: "var(--font-mono, monospace)",
};
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 0, marginBottom: 6, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const mutedStyle: React.CSSProperties = {
  fontSize: 11, color: "var(--os-text-tertiary, #585858)",
};
const errorStyle: React.CSSProperties = {
  padding: 6, marginBottom: 8,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
