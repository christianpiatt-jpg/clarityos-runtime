// components/founder/macro/MacroRunsList.tsx
// Renders the recent macro-ELINS runs with timestamp, ESO mode,
// region count, EP mean (from the global run summary if present).

import { useCallback, useEffect, useState } from "react";
import {
  founderMacroRunsList, founderMacroRunNow,
  type V36MacroRun,
} from "../../../lib/api";

export interface MacroRunsListProps {
  selectedId: string | null;
  onSelect: (run_id: string) => void;
  refreshNonce?: number;
}

export default function MacroRunsList({ selectedId, onSelect, refreshNonce = 0 }: MacroRunsListProps) {
  const [rows, setRows] = useState<V36MacroRun[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setBusy("load"); setError(null);
    try {
      const r = await founderMacroRunsList(20);
      setRows(r.runs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void load(); }, [load, refreshNonce]);

  const runNow = useCallback(async () => {
    setBusy("run"); setError(null);
    try {
      const r = await founderMacroRunNow();
      if (r.summary.ran && r.summary.run_id) onSelect(r.summary.run_id);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [load, onSelect]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <h3 style={{ margin: 0, fontSize: 13, color: "var(--os-text-secondary, #A0A0A0)", textTransform: "uppercase", letterSpacing: 0.5 }}>
          Recent macro runs
        </h3>
        <button
          type="button"
          onClick={() => void runNow()}
          disabled={busy !== null}
          style={{ fontSize: 11, padding: "3px 10px" }}
        >
          {busy === "run" ? "Running…" : "Run macro now"}
        </button>
      </div>
      {error && <div style={errorStyle}>{error}</div>}
      {rows.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>
          {busy === "load" ? "Loading…" : "No macro runs yet."}
        </div>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {rows.map((r) => {
            const active = r.run_id === selectedId;
            const date = new Date(r.ts * 1000);
            return (
              <li key={r.run_id}>
                <button
                  type="button"
                  onClick={() => onSelect(r.run_id)}
                  style={{
                    width: "100%",
                    textAlign: "left",
                    padding: 8,
                    marginBottom: 4,
                    background: active ? "var(--os-elevated, #1a1a1a)" : "var(--os-surface, #111)",
                    border: `1px solid ${active ? "var(--os-focus, #00F0FF)" : "var(--os-line-strong, rgba(255,255,255,0.16))"}`,
                    borderRadius: "var(--radius-sm, 4px)",
                    color: "var(--os-text-primary, #fff)",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <strong style={{ fontSize: 12, fontFamily: "var(--font-mono, monospace)" }}>{r.run_id}</strong>
                    <span style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)" }}>
                      {date.toISOString().replace("T", " ").slice(0, 19)}
                    </span>
                  </div>
                  <div style={{ marginTop: 2, fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)" }}>
                    {r.regions.length} regions · ESO {r.external_signal_mode || "—"}
                  </div>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5", marginBottom: 8,
};
