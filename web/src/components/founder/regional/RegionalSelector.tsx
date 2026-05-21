// components/founder/regional/RegionalSelector.tsx
// Pill row of region codes. Single-select; calls onSelect(code) on click.

import { V35_REGION_CODES, type V35RegionCode } from "../../../lib/api";

export interface RegionalSelectorProps {
  selected: V35RegionCode | null;
  onSelect: (region: V35RegionCode) => void;
  disabled?: boolean;
}

export default function RegionalSelector({
  selected, onSelect, disabled,
}: RegionalSelectorProps) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {V35_REGION_CODES.map((r) => {
        const active = selected === r;
        return (
          <button
            key={r}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(r)}
            style={{
              fontSize: 12,
              padding: "4px 12px",
              border: `1px solid ${active ? "var(--os-focus, #00F0FF)" : "var(--os-line-strong, rgba(255,255,255,0.16))"}`,
              borderRadius: "var(--radius-pill, 999px)",
              background: active ? "var(--os-elevated, #1a1a1a)" : "var(--os-surface, #111)",
              color: active ? "var(--os-focus, #00F0FF)" : "var(--os-text-primary, #fff)",
              cursor: disabled ? "not-allowed" : "pointer",
              opacity: disabled ? 0.5 : 1,
              fontWeight: active ? 600 : 400,
            }}
          >
            {r}
          </button>
        );
      })}
    </div>
  );
}
