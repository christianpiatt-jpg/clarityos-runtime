// components/founder/models/FounderModelStatusPanel.tsx
// v44 — provider status + founder global override.

import { useCallback, useEffect, useState } from "react";
import {
  founderModelsOverride, founderModelsStatus, V44_MODEL_IDS,
  type V44ModelId, type V44RouterStatus,
} from "../../../lib/api";

export default function FounderModelStatusPanel() {
  const [router, setRouter] = useState<V44RouterStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await founderModelsStatus();
      setRouter(r.router);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const apply = useCallback(async (next: V44ModelId | "") => {
    setBusy("save"); setError(null);
    try {
      const value = next === "" ? null : next;
      const r = await founderModelsOverride(value);
      setRouter(r.router);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  return (
    <section style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Model status</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={busy !== null}
          style={refreshStyle}
        >{busy === "load" ? "…" : "Refresh"}</button>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {router && (
        <>
          <h3 style={subHeader}>Providers</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: 6 }}>
            {Object.entries(router.providers).map(([provider, info]) => (
              <div key={provider} style={providerCardStyle}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: 12 }}>{provider}</strong>
                  <span style={{
                    fontSize: 10, fontWeight: 700, letterSpacing: 0.5,
                    color: info.configured ? "var(--os-ok, #4ade80)" : "var(--os-text-tertiary, #585858)",
                  }}>{info.configured ? "READY" : "NO KEY"}</span>
                </div>
              </div>
            ))}
          </div>

          <h3 style={subHeader}>Global default override</h3>
          <p style={helpStyle}>
            When set, the router prefers this model over per-user
            preferences (but explicit per-call overrides still win).
            Set to <code>(none)</code> to fall back to per-user
            preferences + task defaults.
          </p>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <select
              value={router.founder_default_model || ""}
              onChange={(e) => void apply(e.target.value as V44ModelId | "")}
              disabled={busy !== null}
              style={selectStyle}
            >
              <option value="">(none)</option>
              {V44_MODEL_IDS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
            {busy === "save" && <span style={mutedStyle}>saving…</span>}
          </div>

          <h3 style={subHeader}>Task defaults</h3>
          <ul style={{ listStyle: "none", padding: 0, margin: 0, fontSize: 11 }}>
            {Object.entries(router.task_defaults).map(([task, model]) => (
              <li key={task} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0" }}>
                <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{task}</span>
                <code style={{ color: "var(--os-text-primary, #fff)" }}>{model}</code>
              </li>
            ))}
          </ul>

          {router.local_runtime && (
            <>
              <h3 style={subHeader}>Local model runtime</h3>
              <div style={localRuntimeStyle}>
                <LocalRow k="path" v={router.local_runtime.path || "(unset)"} />
                <LocalRow k="loaded" v={router.local_runtime.loaded ? "yes" : "cold"} />
                <LocalRow k="backend" v={router.local_runtime.backend || "—"} />
                <LocalRow k="mock" v={router.local_runtime.mock ? "yes" : "no"} />
                <LocalRow
                  k="memory footprint"
                  v={`${router.local_runtime.memory_footprint_mb.toFixed(1)} MB`}
                />
                <LocalRow
                  k="inferences (process)"
                  v={String(router.local_runtime.inference_count)}
                />
                {router.local_runtime.last_error && (
                  <LocalRow k="last error" v={router.local_runtime.last_error} />
                )}
              </div>
            </>
          )}
        </>
      )}
    </section>
  );
}

function LocalRow({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", gap: 8 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)", fontSize: 11 }}>{k}</span>
      <code style={{ color: "var(--os-text-primary, #fff)", fontSize: 11, wordBreak: "break-all" }}>{v}</code>
    </div>
  );
}

const localRuntimeStyle: React.CSSProperties = {
  padding: 8,
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  background: "var(--os-deep, #0a0a0a)",
};

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
const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 12, marginBottom: 6, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};
const helpStyle: React.CSSProperties = {
  fontSize: 12, color: "var(--os-text-secondary, #A0A0A0)", margin: "0 0 6px 0",
};
const providerCardStyle: React.CSSProperties = {
  padding: 8,
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  background: "var(--os-deep, #0a0a0a)",
};
const selectStyle: React.CSSProperties = {
  flex: 1, padding: "6px 8px",
  background: "var(--os-deep, #0a0a0a)",
  color: "var(--os-text-primary, #fff)",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12,
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
