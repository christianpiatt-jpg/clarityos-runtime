// components/founder/regional/RegionalMapStub.tsx
// Grid of region cards showing the latest summary per region.
// "Map" is intentional shorthand — no real cartography needed in this
// pass; the grid layout is the basin-level view.

import type {
  V35RegionalListItem,
  V35RegionCode,
} from "../../../lib/api";

export interface RegionalMapStubProps {
  items: V35RegionalListItem[];
  selected: V35RegionCode | null;
  onSelect: (region: V35RegionCode) => void;
}

export default function RegionalMapStub({ items, selected, onSelect }: RegionalMapStubProps) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
        gap: 8,
      }}
    >
      {items.map((item) => {
        const active = selected === item.region_code;
        const summary = item.latest;
        return (
          <button
            key={item.region_code}
            type="button"
            onClick={() => onSelect(item.region_code)}
            style={{
              textAlign: "left",
              padding: 10,
              border: `1px solid ${active ? "var(--os-focus, #00F0FF)" : "var(--os-line-strong, rgba(255,255,255,0.16))"}`,
              borderRadius: "var(--radius-md, 8px)",
              background: active ? "var(--os-elevated, #1a1a1a)" : "var(--os-surface, #111)",
              color: "var(--os-text-primary, #fff)",
              cursor: "pointer",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <strong style={{ fontSize: 13 }}>{item.region_code}</strong>
              {summary?.external_present ? (
                <span style={{
                  fontSize: 9, padding: "1px 6px",
                  borderRadius: "var(--radius-pill, 999px)",
                  border: "1px solid var(--os-focus, #00F0FF)",
                  color: "var(--os-focus, #00F0FF)",
                }}>ESO</span>
              ) : null}
            </div>
            {summary ? (
              <div style={{ marginTop: 6, fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)" }}>
                <div>top: <span style={{ color: "var(--os-text-primary, #fff)" }}>
                  {(summary.summary as { top_primitive?: string })?.top_primitive || "—"}
                </span></div>
                <div>signal: <span style={{ color: "var(--os-text-primary, #fff)" }}>
                  {(summary.summary as { signal?: string })?.signal || "—"}
                </span></div>
                <div>day: <span style={{ fontFamily: "var(--font-mono, monospace)" }}>
                  {summary.day}
                </span></div>
              </div>
            ) : (
              <div style={{ marginTop: 6, fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>
                No runs yet
              </div>
            )}
          </button>
        );
      })}
    </div>
  );
}
