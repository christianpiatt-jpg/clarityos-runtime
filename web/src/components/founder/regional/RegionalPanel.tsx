// components/founder/regional/RegionalPanel.tsx
// Composite — list + selector + summary + forecast for the current region.

import { useCallback, useEffect, useState } from "react";
import {
  elinsRegionalList, elinsRegionalRun,
  type V35RegionalELINS, type V35RegionalListItem, type V35RegionCode,
} from "../../../lib/api";
import RegionalSelector from "./RegionalSelector";
import RegionalMapStub from "./RegionalMapStub";
import RegionalSummaryPanel from "./RegionalSummaryPanel";
import RegionalForecastPanel from "./RegionalForecastPanel";

export default function RegionalPanel() {
  const [items, setItems] = useState<V35RegionalListItem[]>([]);
  const [region, setRegion] = useState<V35RegionCode | null>(null);
  const [topic, setTopic] = useState<string>("");
  const [elins, setElins] = useState<V35RegionalELINS | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadList = useCallback(async () => {
    setBusy("list"); setError(null);
    try {
      const r = await elinsRegionalList();
      setItems(r.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, []);

  useEffect(() => { void loadList(); }, [loadList]);

  const run = useCallback(async () => {
    if (!region) return;
    setBusy("run"); setError(null);
    try {
      const r = await elinsRegionalRun(region, topic.trim() || undefined);
      setElins(r.elins);
      // refresh list so the latest summary updates
      void loadList();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(null); }
  }, [region, topic, loadList]);

  return (
    <section style={panelStyle}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Regional ELINS</h2>
        <span style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>
          v35 · {items.length} regions
        </span>
      </header>

      <div style={{ display: "grid", gap: 12 }}>
        <RegionalMapStub items={items} selected={region} onSelect={setRegion} />

        <div>
          <h3 style={subHeader}>Run new pass</h3>
          <RegionalSelector selected={region} onSelect={setRegion} disabled={busy !== null} />
          <input
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            placeholder="Optional topic hint…"
            style={{
              marginTop: 6, width: "100%", padding: "6px 8px",
              border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
              background: "var(--os-deep, #0a0a0a)",
              color: "var(--os-text-primary, #fff)",
              fontSize: 12, borderRadius: "var(--radius-sm, 4px)",
              boxSizing: "border-box",
            }}
            maxLength={2000}
          />
          <button
            type="button"
            disabled={!region || busy !== null}
            onClick={() => void run()}
            style={{
              marginTop: 6, padding: "4px 12px", fontSize: 12,
              cursor: !region || busy !== null ? "not-allowed" : "pointer",
            }}
          >
            {busy === "run" ? "Running…" : `Run ${region || "—"}`}
          </button>
        </div>

        {error && (
          <div style={errorStyle}>{error}</div>
        )}

        {elins && (
          <div style={{
            display: "grid",
            gridTemplateColumns: "minmax(260px, 1fr) minmax(320px, 2fr)",
            gap: 12,
          }}>
            <div style={cardStyle}>
              <RegionalSummaryPanel elins={elins} />
            </div>
            <div style={cardStyle}>
              <RegionalForecastPanel elins={elins} />
            </div>
          </div>
        )}
      </div>
    </section>
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

const cardStyle: React.CSSProperties = {
  border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
  borderRadius: "var(--radius-sm, 4px)",
  padding: 10,
  background: "var(--os-deep, #0a0a0a)",
};

const subHeader: React.CSSProperties = {
  fontSize: 11, marginTop: 4, marginBottom: 6, textTransform: "uppercase",
  letterSpacing: 0.5, color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12,
  color: "#fca5a5",
};
