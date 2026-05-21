// components/founder/forecast/DomainEnvelopeChart.tsx
//
// Static SVG small-multiple chart — one mini line per spec-named domain
// (Economic_Markets ... Environmental). No animation.

import { EmptyChart } from "./PrimitiveEnvelopeChart";

const DOMAIN_COLORS: Record<string, string> = {
  Economic_Markets:   "#fbbf24",
  Geopolitical:       "#ff7b72",
  Social_Cultural:    "#22d3ee",
  Security_Military:  "#ef4444",
  Legal_Justice:      "#a78bfa",
  Science_Technology: "#4ade80",
  Environmental:      "#34d399",
};

export interface DomainEnvelopeChartProps {
  domains: Record<string, number[]>;
  height?: number;
}

export default function DomainEnvelopeChart({ domains, height = 220 }: DomainEnvelopeChartProps) {
  const entries = Object.entries(domains).filter(([, vs]) => Array.isArray(vs) && vs.length > 0);
  if (entries.length === 0) {
    return <EmptyChart label="No domain envelopes" height={height} />;
  }
  const cols = Math.min(entries.length, 4);
  const rows = Math.ceil(entries.length / cols);
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: `repeat(${cols}, 1fr)`,
        gap: 8,
      }}
    >
      {entries.map(([name, values]) => (
        <Sparkline
          key={name}
          name={name}
          values={values}
          color={DOMAIN_COLORS[name] || "#ccc"}
          height={Math.round(height / rows) - 4}
        />
      ))}
    </div>
  );
}

function Sparkline({
  name, values, color, height,
}: { name: string; values: number[]; color: string; height: number }) {
  const ymax = Math.max(0.001, ...values.map(Math.abs));
  const w = 160, h = height, padX = 6, padY = 18;
  const innerW = w - padX * 2;
  const innerH = h - padY - 6;
  const xAt = (i: number) => padX + (innerW * i) / Math.max(1, values.length - 1);
  const yAt = (v: number) => padY + innerH / 2 - (v / ymax) * (innerH / 2);
  const path = values.map((v, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${yAt(v)}`).join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      role="img"
      aria-label={`${name} domain envelope`}
      style={{
        width: "100%",
        height: "auto",
        background: "var(--os-deep, #0a0a0a)",
        border: "1px solid var(--os-line, rgba(255,255,255,0.06))",
        borderRadius: "var(--radius-sm, 4px)",
      }}
    >
      <text
        x={padX} y={12} fontSize="10" fill="var(--os-text-secondary, #A0A0A0)"
      >{name.replace("_", " ")}</text>
      <text
        x={w - padX} y={12} textAnchor="end" fontSize="9"
        fill="var(--os-text-tertiary, #585858)" fontFamily="var(--font-mono, monospace)"
      >
        {values[0]?.toFixed(3)} → {values[values.length - 1]?.toFixed(3)}
      </text>
      <line
        x1={padX} x2={w - padX} y1={padY + innerH / 2} y2={padY + innerH / 2}
        stroke="var(--os-line-strong, rgba(255,255,255,0.16))" strokeDasharray="2 3"
      />
      <path d={path} fill="none" stroke={color} strokeWidth={1.5} />
    </svg>
  );
}
