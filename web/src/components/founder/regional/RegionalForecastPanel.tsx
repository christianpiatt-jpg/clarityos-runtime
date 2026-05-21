// components/founder/regional/RegionalForecastPanel.tsx
// Reuses the v34 ForecastPanel + 4 sub-charts to render the
// region-tuned forecast block. Lambda-overlay annotation surfaces the
// region-specific decay tuning.

import ForecastPanel from "../forecast/ForecastPanel";
import type { V35RegionalELINS } from "../../../lib/api";

export interface RegionalForecastPanelProps {
  elins: V35RegionalELINS;
}

export default function RegionalForecastPanel({ elins }: RegionalForecastPanelProps) {
  const block = elins.forecast_engine;
  if (!block) {
    return (
      <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>
        No forecast block on regional run.
      </div>
    );
  }
  const overlayKeys = Object.keys(
    (block as { lambda_overlay?: Record<string, number> }).lambda_overlay || {},
  );
  return (
    <div>
      <ForecastPanel block={block} title={`Forecast — ${elins.region_code}`} compact />
      {overlayKeys.length > 0 && (
        <div style={{ fontSize: 11, color: "var(--os-text-tertiary, #585858)" }}>
          λ overlay: {overlayKeys.join(", ")}
        </div>
      )}
    </div>
  );
}
