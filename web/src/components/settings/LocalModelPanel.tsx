// components/settings/LocalModelPanel.tsx
// v45 — Local model runtime panel. Shows whether a path is configured,
// whether the runtime is loaded, the backend in use, the per-user
// inference count, and the fallback behaviour when the path isn't set.
//
// Reads via GET /me/local_model. The component never tries to drive a
// load itself (the runtime warm-starts on first kernel use); refresh
// pulls the latest snapshot.

import { useCallback, useEffect, useState } from "react";
import { meLocalModel, type V45LocalModelMe } from "../../lib/api";

export default function LocalModelPanel() {
  const [data, setData] = useState<V45LocalModelMe | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await meLocalModel();
      setData(r);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  return (
    <div style={panelStyle}>
      <header style={headerStyle}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Local model</h2>
        <button
          type="button"
          onClick={() => void load()}
          disabled={busy !== null}
          style={refreshStyle}
        >{busy === "load" ? "…" : "Refresh"}</button>
      </header>

      {error && <div style={errorStyle}>{error}</div>}

      {data && (
        <>
          <p style={helpStyle}>
            On-device inference for <code>local:llama3.1</code>. Configured
            via the <code>CLARITYOS_LOCAL_MODEL_PATH</code> environment
            variable. When unset, the kernel falls back to a deterministic
            mock so routing logic still works.
          </p>

          <div style={statRowStyle}>
            <Stat
              label="Configured"
              value={data.runtime.configured ? "yes" : "no"}
              tone={data.runtime.configured ? "ok" : "muted"}
            />
            <Stat
              label="Loaded"
              value={data.runtime.loaded ? "yes" : "cold"}
              tone={data.runtime.loaded ? "ok" : "muted"}
            />
            <Stat
              label="Backend"
              value={data.runtime.backend || "—"}
            />
            <Stat
              label="Real / mock"
              value={data.runtime.mock ? "mock" : "real"}
              tone={data.runtime.mock ? "muted" : "ok"}
            />
          </div>

          <div style={subRowStyle}>
            <Stat
              label="Path"
              value={data.runtime.path || "(none)"}
              wide
            />
          </div>

          <div style={statRowStyle}>
            <Stat
              label="Memory footprint"
              value={`${data.runtime.memory_footprint_mb.toFixed(1)} MB`}
            />
            <Stat
              label="Inference count (process)"
              value={String(data.runtime.inference_count)}
            />
            <Stat
              label="Your local-model usage"
              value={String(data.usage.local_model_usage_count)}
            />
            <Stat
              label="Preferred?"
              value={data.usage.is_local_preferred ? "yes" : "no"}
              tone={data.usage.is_local_preferred ? "ok" : "muted"}
            />
          </div>

          {data.runtime.fallback && (
            <p style={fallbackStyle}>
              <strong style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>Fallback:</strong>{" "}
              <code>{data.runtime.fallback}</code>
            </p>
          )}

          {data.runtime.last_error && (
            <p style={fallbackStyle}>
              <strong style={{ color: "#fca5a5" }}>Last error:</strong>{" "}
              <code>{data.runtime.last_error}</code>
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Stat({
  label, value, tone, wide,
}: { label: string; value: string; tone?: "ok" | "muted"; wide?: boolean }) {
  const color = tone === "ok"
    ? "var(--os-ok, #4ade80)"
    : tone === "muted"
      ? "var(--os-text-tertiary, #585858)"
      : "var(--os-text-primary, #fff)";
  return (
    <div style={wide ? wideStatStyle : undefined}>
      <div style={statLabelStyle}>{label}</div>
      <code style={{ ...statValueStyle, color }}>{value}</code>
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
const helpStyle: React.CSSProperties = {
  fontSize: 12, color: "var(--os-text-secondary, #A0A0A0)", margin: "0 0 10px 0",
};
const statRowStyle: React.CSSProperties = {
  display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
  gap: 8, marginTop: 6,
};
const subRowStyle: React.CSSProperties = {
  marginTop: 8,
};
const wideStatStyle: React.CSSProperties = {
  gridColumn: "1 / -1",
};
const statLabelStyle: React.CSSProperties = {
  fontSize: 10, color: "var(--os-text-tertiary, #585858)",
  textTransform: "uppercase", letterSpacing: 0.5,
};
const statValueStyle: React.CSSProperties = {
  fontSize: 12, color: "var(--os-text-primary, #fff)",
  fontFamily: "var(--font-mono, monospace)",
  display: "block", marginTop: 2, wordBreak: "break-all",
};
const fallbackStyle: React.CSSProperties = {
  fontSize: 11, marginTop: 10,
  color: "var(--os-text-tertiary, #585858)",
};
const errorStyle: React.CSSProperties = {
  padding: 6, marginBottom: 8,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
