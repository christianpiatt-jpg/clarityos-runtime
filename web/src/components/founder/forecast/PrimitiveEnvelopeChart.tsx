// components/founder/forecast/PrimitiveEnvelopeChart.tsx
//
// Static SVG line chart for a single primitive's D+0..D+N envelope.
// One curve per primitive. No animation. Mobile-friendly viewBox.

import { useMemo } from "react";

const PRIMITIVE_COLORS: Record<string, string> = {
  pressure:      "#ff7b72",
  tension:       "#f59e0b",
  trust:         "#4ade80",
  drift:         "#a78bfa",
  contradiction: "#fb7185",
  alignment:     "#22d3ee",
};

export interface PrimitiveEnvelopeChartProps {
  envelopes: Record<string, number[]>;
  highlight?: string | null;
  height?: number;
}

export default function PrimitiveEnvelopeChart({
  envelopes, highlight = null, height = 180,
}: PrimitiveEnvelopeChartProps) {
  const series = useMemo(() => {
    const out: Array<{ key: string; values: number[] }> = [];
    for (const key of Object.keys(envelopes)) {
      const values = envelopes[key];
      if (!Array.isArray(values) || values.length === 0) continue;
      out.push({ key, values });
    }
    return out;
  }, [envelopes]);

  if (series.length === 0) {
    return <EmptyChart label="No primitives" height={height} />;
  }

  const maxLen = Math.max(...series.map((s) => s.values.length));
  const allVals = series.flatMap((s) => s.values);
  const ymax = Math.max(0.001, ...allVals.map(Math.abs));
  const w = 480, h = height, padX = 32, padY = 20;
  const innerW = w - padX * 2;
  const innerH = h - padY * 2;

  const xAt = (i: number) =>
    padX + (innerW * i) / Math.max(1, maxLen - 1);
  const yAt = (v: number) =>
    padY + innerH / 2 - (v / ymax) * (innerH / 2);

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label="Primitive envelope chart"
      style={{ width: "100%", height: "auto", display: "block" }}
    >
      <rect x={0} y={0} width={w} height={h} fill="var(--os-deep, #0a0a0a)" />
      {/* zero baseline */}
      <line
        x1={padX} x2={w - padX} y1={padY + innerH / 2} y2={padY + innerH / 2}
        stroke="var(--os-line-strong, rgba(255,255,255,0.16))" strokeDasharray="2 3"
      />
      {/* x-axis ticks (D+0..D+N) */}
      {Array.from({ length: maxLen }).map((_, i) => (
        <text
          key={`xt-${i}`} x={xAt(i)} y={h - 4} textAnchor="middle"
          fontSize="9" fill="var(--os-text-tertiary, #585858)"
          fontFamily="var(--font-mono, monospace)"
        >
          D+{i}
        </text>
      ))}
      {series.map(({ key, values }) => {
        const dimmed = highlight !== null && highlight !== key;
        const color = PRIMITIVE_COLORS[key] || "#ccc";
        const path = values.map((v, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${yAt(v)}`).join(" ");
        return (
          <g key={key} opacity={dimmed ? 0.25 : 1}>
            <path d={path} fill="none" stroke={color} strokeWidth={2} />
            {values.map((v, i) => (
              <circle key={`p-${key}-${i}`} cx={xAt(i)} cy={yAt(v)} r={2.5} fill={color} />
            ))}
          </g>
        );
      })}
      {/* legend */}
      <g>
        {series.map(({ key }, i) => {
          const lx = padX + i * 70;
          const ly = padY - 8;
          return (
            <g key={`lg-${key}`} transform={`translate(${lx} ${ly})`}>
              <rect x={0} y={0} width={8} height={8} fill={PRIMITIVE_COLORS[key] || "#ccc"} />
              <text x={12} y={8} fontSize="9" fill="var(--os-text-secondary, #A0A0A0)">
                {key}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}

export function EmptyChart({ label, height = 180 }: { label: string; height?: number }) {
  return (
    <div style={{
      height, display: "flex", alignItems: "center", justifyContent: "center",
      border: "1px dashed var(--os-line-strong, rgba(255,255,255,0.16))",
      color: "var(--os-text-tertiary, #585858)", fontSize: 12,
      borderRadius: "var(--radius-sm, 4px)",
    }}>{label}</div>
  );
}
