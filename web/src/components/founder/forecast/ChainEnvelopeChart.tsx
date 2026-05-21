// components/founder/forecast/ChainEnvelopeChart.tsx
//
// Static SVG chart for the causal-chain envelope: a stepped line for the
// summed chain envelope and small chips for each link's attenuation.

import { EmptyChart } from "./PrimitiveEnvelopeChart";

export interface ChainEnvelopeChartProps {
  values: number[] | null;
  chain: Array<{ key: string; intensity: number; lambda?: number; attenuation?: number }> | null;
  height?: number;
}

export default function ChainEnvelopeChart({ values, chain, height = 200 }: ChainEnvelopeChartProps) {
  if (!values || values.length === 0 || !chain || chain.length === 0) {
    return <EmptyChart label="No causal chain detected" height={height} />;
  }
  const w = 480, h = height, padX = 32, padY = 28;
  const innerW = w - padX * 2;
  const innerH = h - padY * 2;
  const ymax = Math.max(0.001, ...values.map(Math.abs));
  const xAt = (i: number) =>
    padX + (innerW * i) / Math.max(1, values.length - 1);
  const yAt = (v: number) =>
    padY + innerH - (v / ymax) * innerH;
  const path = values.map((v, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${yAt(v)}`).join(" ");

  return (
    <div>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        role="img" aria-label="Chain envelope chart"
        style={{ width: "100%", height: "auto", display: "block" }}
      >
        <rect x={0} y={0} width={w} height={h} fill="var(--os-deep, #0a0a0a)" />
        <path d={path} fill="none" stroke="var(--os-boundary, #E02020)" strokeWidth={2} />
        {values.map((v, i) => (
          <g key={`chp-${i}`}>
            <circle cx={xAt(i)} cy={yAt(v)} r={3} fill="var(--os-boundary, #E02020)" />
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
      <div style={{
        marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6,
        fontSize: 11, color: "var(--os-text-secondary, #A0A0A0)",
      }}>
        {chain.map((link, i) => (
          <div
            key={`link-${i}`}
            style={{
              padding: "3px 8px",
              border: "1px solid var(--os-line-strong, rgba(255,255,255,0.16))",
              borderRadius: "var(--radius-pill, 999px)",
              background: "var(--os-surface, #111)",
            }}
          >
            <strong style={{ color: "var(--os-text-primary, #fff)" }}>{link.key}</strong>
            {" "}
            <span style={{ fontFamily: "var(--font-mono, monospace)" }}>
              i={link.intensity?.toFixed(3)}
            </span>
            {typeof link.attenuation === "number" && (
              <>
                {" · "}
                <span style={{ fontFamily: "var(--font-mono, monospace)" }}>
                  α={link.attenuation.toFixed(2)}
                </span>
              </>
            )}
            {i < chain.length - 1 && (
              <span style={{ marginLeft: 6, color: "var(--os-text-tertiary, #585858)" }}>→</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
