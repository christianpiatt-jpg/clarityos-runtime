// components/founder/macro/MacroSchedulerConfig.tsx
// Toggle enabled, pick cadence, pick external_signal_mode for the
// scheduler's synthetic system user. Backed by
// /founder/elins/scheduler/{status,config}.

import { useCallback, useEffect, useState } from "react";
import {
  founderSchedulerConfig, founderSchedulerStatus,
  type V36Cadence, type V36SchedulerConfig, type V36SignalMode,
} from "../../../lib/api";

export default function MacroSchedulerConfig() {
  const [cfg, setCfg] = useState<V36SchedulerConfig | null>(null);
  const [running, setRunning] = useState<boolean>(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await founderSchedulerStatus();
      setCfg(r.config);
      setRunning(r.running);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const apply = useCallback(async (updates: Partial<V36SchedulerConfig>) => {
    setBusy("save"); setError(null);
    try {
      const r = await founderSchedulerConfig(updates);
      setCfg(r.config);
      setRunning(r.running);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  if (!cfg) {
    return <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>Loading scheduler…</div>;
  }
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <h3 style={{ margin: 0, fontSize: 13, color: "var(--os-text-secondary, #A0A0A0)", textTransform: "uppercase", letterSpacing: 0.5 }}>
          Scheduler config
        </h3>
        <span style={{ fontSize: 11, color: running ? "var(--os-ok, #4ade80)" : "var(--os-text-tertiary, #585858)" }}>
          {running ? "● running" : "○ stopped"}
        </span>
      </div>
      {error && <div style={errorStyle}>{error}</div>}

      <Row label="Enabled">
        <button
          type="button"
          onClick={() => void apply({ enabled: !cfg.enabled })}
          disabled={busy !== null}
          style={toggleStyle(cfg.enabled)}
        >
          {cfg.enabled ? "Enabled" : "Disabled"}
        </button>
      </Row>

      <Row label="Cadence">
        <select
          value={cfg.cadence}
          onChange={(e) => void apply({ cadence: e.target.value as V36Cadence })}
          disabled={busy !== null}
          style={selectStyle}
        >
          {(["off","daily","3x_week","weekly"] as V36Cadence[]).map((c) => (
            <option key={c} value={c}>{c}</option>
          ))}
        </select>
      </Row>

      <Row label="External signal mode">
        <select
          value={cfg.external_signal_mode}
          onChange={(e) => void apply({ external_signal_mode: e.target.value as V36SignalMode })}
          disabled={busy !== null}
          style={selectStyle}
        >
          {(["cloud_only","cloud_perplexity"] as V36SignalMode[]).map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </Row>

      <Row label="System user">
        <code style={{ fontSize: 11 }}>{cfg.system_user}</code>
      </Row>

      <Row label="Last run">
        <code style={{ fontSize: 11 }}>
          {cfg.last_run_ts > 0 ? new Date(cfg.last_run_ts * 1000).toISOString().slice(0, 19) : "—"}
        </code>
      </Row>
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 0", fontSize: 12 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      {children}
    </div>
  );
}

function toggleStyle(active: boolean): React.CSSProperties {
  return {
    fontSize: 11, padding: "3px 12px",
    border: `1px solid ${active ? "var(--os-focus, #00F0FF)" : "var(--os-line-strong, rgba(255,255,255,0.16))"}`,
    background: active ? "var(--os-elevated, #1a1a1a)" : "var(--os-surface, #111)",
    color: active ? "var(--os-focus, #00F0FF)" : "var(--os-text-primary, #fff)",
    borderRadius: "var(--radius-pill, 999px)",
    cursor: "pointer",
  };
}

const selectStyle: React.CSSProperties = {
  fontSize: 11, padding: "2px 6px",
  background: "var(--os-deep, #0a0a0a)",
  color: "var(--os-text-primary, #fff)",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-sm, 4px)",
};

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5", marginBottom: 8,
};
