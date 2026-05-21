// components/founder/forecast/MultiEnvelopeChart.tsx
//
// Static SVG area chart for the magnitude-weighted multi-primitive envelope.
// One curve, filled. No animation. No external dep.

import { EmptyChart } from "./PrimitiveEnvelopeChart";

export interface MultiEnvelopeChartProps {
  values: number[];
  height?: number;
}

export default function MultiEnvelopeChart({ values, height = 160 }: MultiEnvelopeChartProps) {
  if (!Array.isArray(values) || values.length === 0) {
    return <EmptyChart label="No multi envelope" height={height} />;
  }
  const w = 480, h = height, padX = 32, padY = 20;
  const innerW = w - padX * 2;
  const innerH = h - padY * 2;
  const ymax = Math.max(0.001, ...values.map(Math.abs));
  const ymin = Math.min(0, ...values);
  const span = Math.max(0.001, ymax - Math.min(0, ymin));
  const xAt = (i: number) =>
    padX + (innerW * i) / Math.max(1, values.length - 1);
  const yAt = (v: number) =>
    padY + innerH - ((v - Math.min(0, ymin)) / span) * innerH;

  const top = values.map((v, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${yAt(v)}`).join(" ");
  const bottomY = yAt(Math.min(0, ymin));
  const area = `${top} L ${xAt(values.length - 1)} ${bottomY} L ${xAt(0)} ${bottomY} Z`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      role="img" aria-label="Multi-primitive envelope chart"
      style={{ width: "100%", height: "auto", display: "block" }}
    >
      <rect x={0} y={0} width={w} height={h} fill="var(--os-deep, #0a0a0a)" />
      <path d={area} fill="rgba(0,240,255,0.15)" />
      <path d={top} fill="none" stroke="var(--os-focus, #00F0FF)" strokeWidth={2} />
      {values.map((v, i) => (
        <g key={`mp-${i}`}>
          <circle cx={xAt(i)} cy={yAt(v)} r={3} fill="var(--os-focus, #00F0FF)" />
          <text
            x={xAt(i)} y={yAt(v) - 6} textAnchor="middle"
            fontSize="9" fill="var(--os-text-secondary, #A0A0A0)"
            fontFamily="var(--font-mono, monospace)"
          >
            {v.toFixed(3)}
          </text>
          <text
            x={xAt(i)} y={h - 4} textAnchor="middle"
            fontSize="9" fill="var(--os-text-tertiary, #585858)"
            fontFamily="var(--font-mono, monospace)"
          >
            D+{i}
          </text>
        </g>
      ))}
    </svg>
  );
}
