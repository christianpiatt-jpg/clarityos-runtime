// components/founder/entities/EntityNeighborsPanel.tsx
// Shows the selected entity's summary + its top neighbours.

import { useCallback, useEffect, useState } from "react";
import {
  elinsEntityNeighbors,
  type V37EntityNeighbor, type V37EntitySummary,
} from "../../../lib/api";

export interface EntityNeighborsPanelProps {
  entity: string | null;
  onSelect: (name: string) => void;
}

export default function EntityNeighborsPanel({ entity, onSelect }: EntityNeighborsPanelProps) {
  const [summary, setSummary] = useState<V37EntitySummary | null>(null);
  const [neighbors, setNeighbors] = useState<V37EntityNeighbor[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!entity) return;
    setBusy(true); setError(null); setSummary(null); setNeighbors([]);
    try {
      const r = await elinsEntityNeighbors(entity, 30);
      setSummary(r.summary);
      setNeighbors(r.neighbors);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  }, [entity]);

  useEffect(() => { void load(); }, [load]);

  if (!entity) {
    return <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>Select an entity</div>;
  }
  return (
    <div>
      <h3 style={titleStyle}>{entity}</h3>
      {summary && (
        <div style={{ marginBottom: 8 }}>
          <Row label="Degree" value={String(summary.degree)} />
          <Row label="EP mean" value={summary.ep_mean.toFixed(3)} />
          <Row label="Clusters" value={(summary.clusters || []).join(", ") || "—"} />
          {Object.keys(summary.domains || {}).length > 0 && (
            <div style={{ marginTop: 4 }}>
              <h4 style={subHeader}>Top domains</h4>
              {Object.entries(summary.domains)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 6)
                .map(([k, v]) => (
                  <Row key={k} label={k} value={v.toFixed(2)} />
                ))}
            </div>
          )}
        </div>
      )}

      {error && <div style={errorStyle}>{error}</div>}
      {busy && <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>Loading…</div>}

      <h4 style={subHeader}>Neighbors ({neighbors.length})</h4>
      {neighbors.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>None</div>
      ) : (
        <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {neighbors.map((n) => (
            <li key={n.name}>
              <button
                type="button"
                onClick={() => onSelect(n.name)}
                style={neighborStyle}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <strong style={{ fontSize: 12 }}>{n.name}</strong>
                  <span style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)", fontFamily: "var(--font-mono, monospace)" }}>
                    w {n.weight.toFixed(2)} · co {n.co_occurrences}
                  </span>
                </div>
                {n.top_domains.length > 0 && (
                  <div style={{ marginTop: 2, fontSize: 10, color: "var(--os-text-secondary, #A0A0A0)" }}>
                    {n.top_domains.join(" · ")}
                  </div>
                )}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", fontSize: 11 }}>
      <span style={{ color: "var(--os-text-secondary, #A0A0A0)" }}>{label}</span>
      <span style={{ fontFamily: "var(--font-mono, monospace)" }}>{value}</span>
    </div>
  );
}

const titleStyle: React.CSSProperties = {
  margin: "0 0 6px 0", fontSize: 14, fontWeight: 600, color: "var(--os-text-primary, #fff)",
};

const subHeader: React.CSSProperties = {
  fontSize: 11, margin: "8px 0 4px 0", textTransform: "uppercase", letterSpacing: 0.5,
  color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};

const neighborStyle: React.CSSProperties = {
  width: "100%",
  textAlign: "left",
  padding: 6,
  marginBottom: 3,
  background: "var(--os-surface, #111)",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  borderRadius: "var(--radius-sm, 4px)",
  color: "var(--os-text-primary, #fff)",
  cursor: "pointer",
};

const errorStyle: React.CSSProperties = {
  marginTop: 6, padding: 6,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
