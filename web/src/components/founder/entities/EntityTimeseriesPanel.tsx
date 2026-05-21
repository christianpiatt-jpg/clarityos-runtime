// components/founder/entities/EntityTimeseriesPanel.tsx
// Plots EP-mean per appearance for the selected entity. Reuses the
// minimalist SVG idiom from the v34 forecast charts.

import { useCallback, useEffect, useState } from "react";
import {
  elinsEntityTimeseries,
  type V37EntityAppearance,
} from "../../../lib/api";

export interface EntityTimeseriesPanelProps {
  entity: string | null;
}

export default function EntityTimeseriesPanel({ entity }: EntityTimeseriesPanelProps) {
  const [series, setSeries] = useState<V37EntityAppearance[]>([]);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!entity) return;
    setBusy(true); setError(null); setSeries([]);
    try {
      const r = await elinsEntityTimeseries(entity);
      setSeries(r.timeseries);
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
      <h3 style={titleStyle}>EP timeseries</h3>
      {error && <div style={errorStyle}>{error}</div>}
      {busy && series.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>Loading…</div>
      ) : series.length === 0 ? (
        <div style={{ fontSize: 12, color: "var(--os-text-tertiary, #585858)" }}>No appearances</div>
      ) : (
        <Chart series={series} />
      )}
      {series.length > 0 && (
        <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0 0" }}>
          {series.slice(-6).reverse().map((a, i) => (
            <li key={i} style={{ display: "flex", justifyContent: "space-between", padding: "2px 0", fontSize: 11 }}>
              <span style={{ color: "var(--os-text-secondary, #A0A0A0)", fontFamily: "var(--font-mono, monospace)" }}>
                {fmtTs(a.ts)}
              </span>
              <span>
                <span style={{ color: "var(--os-text-tertiary, #585858)", marginRight: 6 }}>
                  [{a.cluster}]
                </span>
                <span style={{ fontFamily: "var(--font-mono, monospace)" }}>
                  ep {a.ep_mean.toFixed(3)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Chart({ series }: { series: V37EntityAppearance[] }) {
  const w = 480, h = 140, padX = 24, padY = 20;
  const innerW = w - padX * 2;
  const innerH = h - padY * 2;
  const ymax = Math.max(0.001, ...series.map((s) => s.ep_mean));
  const xAt = (i: number) =>
    padX + (innerW * i) / Math.max(1, series.length - 1);
  const yAt = (v: number) =>
    padY + innerH - (v / ymax) * innerH;
  const path = series.map((s, i) =>
    `${i === 0 ? "M" : "L"} ${xAt(i)} ${yAt(s.ep_mean)}`,
  ).join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="Entity EP timeseries"
      style={{ width: "100%", height: "auto", display: "block" }}
    >
      <rect x={0} y={0} width={w} height={h} fill="var(--os-deep, #0a0a0a)" />
      <path d={path} fill="none" stroke="var(--os-focus, #00F0FF)" strokeWidth={2} />
      {series.map((s, i) => (
        <circle key={i} cx={xAt(i)} cy={yAt(s.ep_mean)} r={2.5} fill="var(--os-focus, #00F0FF)" />
      ))}
      <line
        x1={padX} x2={w - padX} y1={padY + innerH} y2={padY + innerH}
        stroke="var(--os-line-strong, rgba(255,255,255,0.16))"
      />
    </svg>
  );
}

function fmtTs(ts: number): string {
  if (!ts || ts <= 0) return "—";
  return new Date(ts * 1000).toISOString().slice(0, 19).replace("T", " ");
}

const titleStyle: React.CSSProperties = {
  margin: "0 0 6px 0", fontSize: 14, fontWeight: 600, color: "var(--os-text-primary, #fff)",
};

const errorStyle: React.CSSProperties = {
  padding: 6,
  background: "rgba(224, 32, 32, 0.1)",
  border: "1px solid var(--os-boundary, #E02020)",
  borderRadius: "var(--radius-sm, 4px)",
  fontSize: 12, color: "#fca5a5",
};
