// components/founder/entities/EntitySearch.tsx
// Substring search box + result list. Selecting a row pushes
// onSelect(name) up to the orchestrator panel.

import { useCallback, useEffect, useRef, useState } from "react";
import { elinsEntitiesSearch, type V37EntitySearchHit } from "../../../lib/api";

export interface EntitySearchProps {
  selected: string | null;
  onSelect: (name: string) => void;
}

export default function EntitySearch({ selected, onSelect }: EntitySearchProps) {
  const [q, setQ] = useState<string>("");
  const [rows, setRows] = useState<V37EntitySearchHit[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [graphTs, setGraphTs] = useState<number>(0);
  const reqId = useRef<number>(0);

  const load = useCallback(async (query: string) => {
    const myId = ++reqId.current;
    setBusy(true); setError(null);
    try {
      const r = await elinsEntitiesSearch(query, 50);
      if (myId !== reqId.current) return;       // stale
      setRows(r.entities);
      setGraphTs(r.graph_updated_ts);
    } catch (e: unknown) {
      if (myId !== reqId.current) return;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (myId === reqId.current) setBusy(false);
    }
  }, []);

  // Initial load (top entities by degree).
  useEffect(() => { void load(""); }, [load]);

  // Debounced re-fetch on query change.
  useEffect(() => {
    const t = setTimeout(() => void load(q), 200);
    return () => clearTimeout(t);
  }, [q, load]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
        <h3 style={subHeader}>Search entities</h3>
        <span style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)" }}>
          {graphTs > 0 ? new Date(graphTs * 1000).toISOString().slice(0, 19) : "no graph yet"}
        </span>
      </div>
      <input
        type="text"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="e.g. Iran, Federal Reserve, Senate…"
        style={inputStyle}
        maxLength={200}
      />
      {error && <div style={errorStyle}>{error}</div>}
      <div style={{ marginTop: 6 }}>
        {rows.length === 0 ? (
          <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>
            {busy ? "Loading…" : (q ? "No matches" : "No entities yet")}
          </div>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {rows.map((r) => {
              const active = selected === r.name;
              return (
                <li key={r.name}>
                  <button
                    type="button"
                    onClick={() => onSelect(r.name)}
                    style={rowStyle(active)}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                      <strong style={{ fontSize: 12 }}>{r.name}</strong>
                      <span style={{ fontSize: 10, color: "var(--os-text-tertiary, #585858)", fontFamily: "var(--font-mono, monospace)" }}>
                        deg {r.degree} · ep {r.ep_mean.toFixed(3)}
                      </span>
                    </div>
                    {(r.top_domains.length > 0 || r.clusters.length > 0) && (
                      <div style={{ marginTop: 2, fontSize: 10, color: "var(--os-text-secondary, #A0A0A0)" }}>
                        {r.top_domains.length > 0 && <span>{r.top_domains.join(" · ")}</span>}
                        {r.top_domains.length > 0 && r.clusters.length > 0 && " · "}
                        {r.clusters.length > 0 && <span>[{r.clusters.join(",")}]</span>}
                      </div>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}

function rowStyle(active: boolean): React.CSSProperties {
  return {
    width: "100%",
    textAlign: "left",
    padding: 8,
    marginBottom: 4,
    background: active ? "var(--os-elevated, #1a1a1a)" : "var(--os-surface, #111)",
    border: `1px solid ${active ? "var(--os-focus, #00F0FF)" : "var(--os-line-strong, rgba(255,255,255,0.16))"}`,
    borderRadius: "var(--radius-sm, 4px)",
    color: "var(--os-text-primary, #fff)",
    cursor: "pointer",
  };
}

const subHeader: React.CSSProperties = {
  fontSize: 11, margin: 0, textTransform: "uppercase", letterSpacing: 0.5,
  color: "var(--os-text-secondary, #A0A0A0)", fontWeight: 600,
};

const inputStyle: React.CSSProperties = {
  width: "100%", padding: "6px 8px",
  border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
  background: "var(--os-deep, #0a0a0a)",
  color: "var(--os-text-primary, #fff)",
  fontSize: 12, borderRadius: "var(--radius-sm, 4px)",
  boxSizing: "border-box",
};

const errorStyle: React.CSSProperties = {
  marginTop: 6, padding: 6,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
